#!/usr/bin/env python3
"""ObservationSchedule operator CLI. No arbitrary URLs, SQL, or output paths."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    ObservationScheduleError,
    load_observation_schedule,
    parse_utc,
)
from solana_alpha_lab.factory.observation_schedule_compiler import (  # noqa: E402
    compile_schedule_document,
)
from solana_alpha_lab.factory.observation_schedule_lifecycle import (  # noqa: E402
    ObservationLifecycleError,
    _require_live_authority,
    activate_schedule,
    activation_transition_research_event_proven,
    abort_schedule,
    authorize_schedule,
    pause_schedule,
    register_schedule,
    resolve_late_recovery_proof,
    resume_schedule,
    rollover_schedule,
    snapshot_schedule,
    status_schedule,
    owner_next_action_for_lifecycle_error,
)
from solana_alpha_lab.factory.observation_schedule_composition import (  # noqa: E402
    CompositionParityError,
    TickPhysicalOverrides,
    materialize_tick_physical_dependencies,
)
from solana_alpha_lab.factory.observation_provider_wall_deadline import (  # noqa: E402
    resolve_provider_call_wall_seconds,
)
from solana_alpha_lab.factory.observation_schedule_runtime import (  # noqa: E402
    DEFAULT_RUNTIME_RELATIVE,
    ObservationRuntimeError,
    git_sha,
    load_credential_after_activation,
    load_runtime_config,
    resolve_clock,
    resolve_data_root,
)
from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    ObservationPanelPublisherError,
    PublicationFault,
)
from solana_alpha_lab.factory.observation_primitive_registry import (  # noqa: E402
    PrimitiveRegistryError,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
    ObservationScheduleStoreError,
)
from solana_alpha_lab.factory.observation_scheduler import (  # noqa: E402
    ObservationSchedulerError,
    tick_once,
)

SAFE_PREFIXES = ("local/", "tests/fixtures/observation_schedule/", "configs/")


def _safe_relative(root: Path, relative: str) -> Path:
    path = Path(relative)
    posix = PurePosixPath(relative)
    windows = PureWindowsPath(relative)
    if (
        path.is_absolute()
        or posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or ".." in posix.parts
        or ".." in windows.parts
    ):
        raise SystemExit("PATH_UNSAFE")
    normalized = relative.replace("\\", "/")
    if not normalized.startswith(SAFE_PREFIXES) and not normalized.startswith("tests/fixtures/"):
        raise SystemExit("PATH_UNSAFE")
    return root / relative


def _emit(payload: dict, code: int) -> int:
    print(json.dumps(payload, sort_keys=True))
    return code


def _bind_runtime(args: argparse.Namespace) -> tuple[dict, Path, ObservationScheduleStore]:
    relative = getattr(args, "runtime_config", None) or DEFAULT_RUNTIME_RELATIVE
    config = load_runtime_config(ROOT, relative)
    explicit = getattr(args, "data_root", None)
    if explicit:
        resolved = Path(explicit)
        if resolved.is_absolute() is False:
            raise ObservationRuntimeError("DATA_ROOT_NOT_ABSOLUTE")
        ops = resolved / "observation_schedule_state.sqlite"
    else:
        resolved = resolve_data_root(ROOT, str(config["data_root"]))
        ops = resolve_data_root(ROOT, str(config["ops_store_relative"]))
    store = ObservationScheduleStore(ops)
    return config, resolved, store


def main(
    argv: list[str] | None = None,
    *,
    physical_overrides: TickPhysicalOverrides | None = None,
) -> int:
    """Operator entrypoint. physical_overrides is process-local / keyword-only."""

    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in (
        "validate",
        "compile",
        "register",
        "authorize",
        "activate",
        "pause",
        "abort",
        "resume",
        "rollover",
        "status",
        "snapshot",
        "doctor",
    ):
        cmd = sub.add_parser(name)
        cmd.add_argument("--schedule")
        cmd.add_argument("--runtime-config", default=DEFAULT_RUNTIME_RELATIVE)
        cmd.add_argument("--data-root")
        if name == "authorize":
            cmd.add_argument("--phrase", required=True)
        if name in {"activate", "pause", "abort", "resume", "snapshot"}:
            cmd.add_argument("--activation-id", required=True)
        if name == "abort":
            cmd.add_argument("--reason", required=True)
        if name == "rollover":
            cmd.add_argument("--predecessor-schedule-sha256", required=True)
            cmd.add_argument("--predecessor-activation-id", required=True)
            cmd.add_argument("--successor-schedule-sha256", required=True)
            cmd.add_argument("--successor-activation-id", required=True)
            cmd.add_argument("--cutover-at", required=True)
        if name in {
            "authorize",
            "activate",
            "pause",
            "abort",
            "resume",
            "snapshot",
            "status",
            "doctor",
        }:
            cmd.add_argument("--schedule-sha256")
        if name in {"status", "doctor"}:
            cmd.add_argument("--activation-id")
    tick = sub.add_parser("tick")
    tick.add_argument("--once", action="store_true", required=True)
    tick.add_argument("--runtime-config", default=DEFAULT_RUNTIME_RELATIVE)
    tick.add_argument("--data-root")
    tick.add_argument("--schedule-sha256")
    tick.add_argument("--activation-id")
    args = parser.parse_args(argv)
    try:
        if args.command in {"validate", "compile"}:
            if not args.schedule:
                return _emit({"terminal": "SCHEDULE_PATH_REQUIRED"}, 2)
            document = load_observation_schedule(ROOT, args.schedule)
            if args.command == "validate":
                return _emit(
                    {"terminal": "VALIDATED", "schedule_sha256": document["schedule_sha256"]},
                    0,
                )
            result = compile_schedule_document(document, root=ROOT)
            return _emit(
                {
                    "terminal": result.terminal,
                    "schedule_sha256": result.schedule_sha256,
                    "next_action": result.next_action,
                },
                0 if result.schedule_sha256 else 2,
            )
        config, data_root, store = _bind_runtime(args)
        if physical_overrides is not None:
            now = physical_overrides.now
        else:
            now = resolve_clock(config)
        producer = git_sha(ROOT, config.get("producer_git_sha"))
        if args.command == "register":
            if not args.schedule:
                return _emit({"terminal": "SCHEDULE_PATH_REQUIRED"}, 2)
            document = load_observation_schedule(ROOT, args.schedule)
            result = register_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                document=document,
                now=now,
                producer_git_sha=producer,
            )
            code = 0 if result.get("schedule_sha256") else 2
            return _emit(result, code)
        if args.command == "authorize":
            digest = args.schedule_sha256
            if not digest and args.schedule:
                digest = load_observation_schedule(ROOT, args.schedule)["schedule_sha256"]
            if not digest:
                return _emit({"terminal": "SCHEDULE_SHA256_REQUIRED"}, 2)
            result = authorize_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                phrase=args.phrase,
                now=now,
                producer_git_sha=producer,
            )
            return _emit(result, 0)
        if args.command == "activate":
            digest = args.schedule_sha256 or config.get("schedule_sha256")
            if not digest and args.schedule:
                digest = load_observation_schedule(ROOT, args.schedule)["schedule_sha256"]
            if not digest:
                return _emit({"terminal": "SCHEDULE_SHA256_REQUIRED"}, 2)
            result = activate_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id=args.activation_id,
                now=now,
                producer_git_sha=producer,
            )
            code = 0 if result.get("terminal") in {"ACTIVATED", "ACTIVATE_REPLAY"} else 2
            return _emit(result, code)
        if args.command == "pause":
            digest = args.schedule_sha256 or config.get("schedule_sha256")
            if not digest and args.schedule:
                digest = load_observation_schedule(ROOT, args.schedule)["schedule_sha256"]
            if not digest:
                return _emit({"terminal": "SCHEDULE_SHA256_REQUIRED"}, 2)
            result = pause_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id=args.activation_id,
                now=now,
                producer_git_sha=producer,
            )
            return _emit(result, 0)
        if args.command == "abort":
            digest = args.schedule_sha256 or config.get("schedule_sha256")
            if not digest and args.schedule:
                digest = load_observation_schedule(ROOT, args.schedule)["schedule_sha256"]
            if not digest:
                return _emit({"terminal": "SCHEDULE_SHA256_REQUIRED"}, 2)
            result = abort_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id=args.activation_id,
                reason=args.reason,
                now=now,
                producer_git_sha=producer,
            )
            return _emit(result, 0)
        if args.command == "resume":
            digest = args.schedule_sha256 or config.get("schedule_sha256")
            if not digest and args.schedule:
                digest = load_observation_schedule(ROOT, args.schedule)["schedule_sha256"]
            if not digest:
                return _emit({"terminal": "SCHEDULE_SHA256_REQUIRED"}, 2)
            result = resume_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id=args.activation_id,
                now=now,
                producer_git_sha=producer,
            )
            code = 0 if result.get("terminal") in {"RESUMED", "RESUME_REPLAY"} else 2
            return _emit(result, code)
        if args.command == "rollover":
            result = rollover_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                predecessor_schedule_sha256=args.predecessor_schedule_sha256,
                predecessor_activation_id=args.predecessor_activation_id,
                successor_schedule_sha256=args.successor_schedule_sha256,
                successor_activation_id=args.successor_activation_id,
                cutover_at=args.cutover_at,
                now=now,
                producer_git_sha=producer,
            )
            code = (
                0
                if result.get("terminal")
                in {"ROLLOVER_COMMITTED", "ROLLOVER_REPLAY"}
                else 2
            )
            return _emit(result, code)
        if args.command == "status":
            cli_digest = getattr(args, "schedule_sha256", None)
            cli_activation = getattr(args, "activation_id", None)
            if bool(cli_digest) != bool(cli_activation):
                return _emit(
                    {
                        "terminal": "STATUS_SELECTOR_INCOMPLETE",
                        "next_action": (
                            "PROVIDE_BOTH_SCHEDULE_SHA256_AND_ACTIVATION_ID"
                        ),
                    },
                    2,
                )
            # Status defaults to the store's deterministic current
            # ACTIVE/DRAINING selection.  Runtime config is not an authority
            # for choosing a historical activation.
            explicit_digest = (
                str(cli_digest) if cli_digest and cli_activation else None
            )
            explicit_activation = (
                str(cli_activation) if cli_digest and cli_activation else None
            )
            result = status_schedule(
                store,
                schedule_sha256=explicit_digest,
                activation_id=explicit_activation,
                data_root=data_root,
                now=now,
                deploy_git_sha=producer,
            )
            return _emit(
                result,
                0 if result.get("terminal") == "STATUS" else 2,
            )
        if args.command == "snapshot":
            digest = args.schedule_sha256 or config.get("schedule_sha256")
            if not digest and args.schedule:
                digest = load_observation_schedule(ROOT, args.schedule)["schedule_sha256"]
            if not digest:
                return _emit({"terminal": "SCHEDULE_SHA256_REQUIRED"}, 2)
            result = snapshot_schedule(
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id=args.activation_id,
                now=now,
                producer_git_sha=producer,
            )
            return _emit(result, 0)
        if args.command == "doctor":
            from solana_alpha_lab.factory.collector_read_model import (
                activation_rows_with_family_keys,
                build_collector_read_model,
                classify_doctor_current_activation,
            )

            unresolved = store.restore_marker_unresolved()
            activations = activation_rows_with_family_keys(
                store, store.list_activations()
            )
            cli_digest = getattr(args, "schedule_sha256", None)
            cli_activation = getattr(args, "activation_id", None)
            if bool(cli_digest) != bool(cli_activation):
                return _emit(
                    {
                        "terminal": "DOCTOR_SELECTOR_INCOMPLETE",
                        "next_action": (
                            "PROVIDE_BOTH_SCHEDULE_SHA256_AND_ACTIVATION_ID"
                        ),
                    },
                    2,
                )
            selection_activations = activations
            explicit_scope = bool(cli_digest and cli_activation)
            if explicit_scope:
                selection_activations = [
                    row
                    for row in activations
                    if str(row.get("schedule_sha256") or "") == str(cli_digest)
                    and str(row.get("activation_id") or "") == str(cli_activation)
                ]
                if not selection_activations:
                    return _emit(
                        {
                            "terminal": "DOCTOR_SELECTOR_NOT_FOUND",
                            "schedule_sha256": str(cli_digest),
                            "activation_id": str(cli_activation),
                            "next_action": "VERIFY_SCHEDULE_AND_ACTIVATION_SELECTOR",
                        },
                        2,
                    )
            recovery_proofs = {
                (
                    str(row.get("schedule_sha256") or ""),
                    str(row.get("activation_id") or ""),
                ): resolve_late_recovery_proof(data_root, row, now=now)
                for row in activations
                if str(row.get("state") or "") == "DRAINING"
                and str(row.get("activation_id") or "")
            }
            current_report = classify_doctor_current_activation(
                selection_activations,
                recovery_proofs=recovery_proofs,
                now=now,
                explicit_scope=explicit_scope,
            )
            current_state = str(current_report.get("current_activation_state") or "")
            live = bool(current_report.get("live_activation"))
            current_timing = {
                "stops_admitting_at": current_report.get("stops_admitting_at"),
                "late_recovery_at": current_report.get("late_recovery_at"),
                "late_recovery_proof": current_report.get("late_recovery_proof"),
                "late_recovery_event_id": current_report.get(
                    "late_recovery_event_id"
                ),
            }
            if cli_digest and cli_activation:
                collector_digest = str(cli_digest)
                collector_activation = str(cli_activation)
            else:
                collector_digest = (
                    str(current_report.get("current_schedule_sha256") or "") or None
                )
                collector_activation = (
                    str(current_report.get("current_activation_id") or "") or None
                )
            collector = build_collector_read_model(
                store,
                now=now,
                schedule_sha256=collector_digest,
                activation_id=collector_activation,
                deploy_git_sha=producer,
            )
            if unresolved:
                return _emit(
                    {
                        **current_timing,
                        "terminal": "DOCTOR_RESTORE_MARKER_UNRESOLVED",
                        "live_activation": live,
                        "current_activation_id": current_report.get(
                            "current_activation_id"
                        ),
                        "current_activation_state": current_state or None,
                        "restore_marker_unresolved": True,
                        "activation_count": len(activations),
                        "collector": collector,
                        "next_action": "RESOLVE_RESTORE_MARKER",
                    },
                    2,
                )
            if current_report["terminal"] == "DOCTOR_ABORTED_SAFETY":
                return _emit(
                    {
                        **current_timing,
                        "terminal": "DOCTOR_ABORTED_SAFETY",
                        "live_activation": False,
                        "current_activation_id": current_report.get(
                            "current_activation_id"
                        ),
                        "current_activation_state": current_state,
                        "restore_marker_unresolved": False,
                        "activation_count": len(activations),
                        "collector": collector,
                        "next_action": "MUST_NOT_RESUME",
                    },
                    2,
                )
            if current_report["terminal"] == "DOCTOR_PAUSED":
                must_not_resume = any(
                    dict(row.get("payload") or {}).get("must_not_resume") is True
                    or str(dict(row.get("payload") or {}).get("abort_reason") or "").strip()
                    for row in activations
                    if row["state"] == "PAUSED_OPERATOR"
                    and str(row.get("activation_id") or "")
                    == str(current_report.get("current_activation_id") or "")
                )
                return _emit(
                    {
                        **current_timing,
                        "terminal": "DOCTOR_PAUSED",
                        "live_activation": False,
                        "current_activation_id": current_report.get(
                            "current_activation_id"
                        ),
                        "current_activation_state": current_state,
                        "restore_marker_unresolved": False,
                        "activation_count": len(activations),
                        "collector": collector,
                        "next_action": "MUST_NOT_RESUME" if must_not_resume else "RESUME",
                    },
                    2,
                )
            if current_report["terminal"] == "DOCTOR_RECOVERY_PROOF_UNAVAILABLE":
                return _emit(
                    {
                        **current_timing,
                        "terminal": "DOCTOR_RECOVERY_PROOF_UNAVAILABLE",
                        "live_activation": False,
                        "current_activation_id": current_report.get(
                            "current_activation_id"
                        ),
                        "current_activation_state": current_state,
                        "restore_marker_unresolved": False,
                        "activation_count": len(activations),
                        "collector": collector,
                        "next_action": "REPAIR_DRAINING_RECOVERY_PROOF",
                    },
                    2,
                )
            if current_report["terminal"] == "DOCTOR_ACTIVATION_SCOPE_AMBIGUOUS":
                return _emit(
                    {
                        **current_timing,
                        "terminal": "DOCTOR_ACTIVATION_SCOPE_AMBIGUOUS",
                        "live_activation": False,
                        "current_activation_id": None,
                        "current_activation_state": "UNKNOWN",
                        "activation_selection_status": "AMBIGUOUS",
                        "restore_marker_unresolved": False,
                        "activation_count": len(activations),
                        "collector": collector,
                        "next_action": "RECONCILE_ACTIVATION_FAMILY_SCOPE",
                    },
                    2,
                )
            if current_report["terminal"] == "DOCTOR_ACTIVATION_SELECTION_UNKNOWN":
                return _emit(
                    {
                        **current_timing,
                        "terminal": "DOCTOR_ACTIVATION_SELECTION_UNKNOWN",
                        "live_activation": False,
                        "current_activation_id": None,
                        "current_activation_state": "UNKNOWN",
                        "activation_selection_status": "UNKNOWN",
                        "restore_marker_unresolved": False,
                        "activation_count": len(activations),
                        "collector": collector,
                        "next_action": "RECONCILE_FUTURE_ACTIVATION_TRANSITION",
                    },
                    2,
                )
            if current_state == "ACTIVE":
                current_row = next(
                    (
                        row
                        for row in selection_activations
                        if str(row.get("schedule_sha256") or "")
                        == str(current_report.get("current_schedule_sha256") or "")
                        and str(row.get("activation_id") or "")
                        == str(current_report.get("current_activation_id") or "")
                    ),
                    None,
                )
                try:
                    active_transition_proven = (
                        current_row is not None
                        and activation_transition_research_event_proven(
                            data_root, current_row, now=now
                        )
                    )
                except Exception:
                    active_transition_proven = False
                if not active_transition_proven:
                    return _emit(
                        {
                            **current_timing,
                            "terminal": "DOCTOR_ACTIVE_TRANSITION_PROOF_UNAVAILABLE",
                            "live_activation": False,
                            "current_activation_id": current_report.get(
                                "current_activation_id"
                            ),
                            "current_activation_state": "UNKNOWN",
                            "activation_selection_status": "UNKNOWN",
                            "restore_marker_unresolved": False,
                            "activation_count": len(activations),
                            "collector": collector,
                            "next_action": "RECONCILE_ACTIVE_TRANSITION_PROOF",
                        },
                        2,
                    )
            if current_report["terminal"] == "DOCTOR_NO_LIVE_ACTIVATION":
                return _emit(
                    {
                        **current_timing,
                        "terminal": "DOCTOR_NO_LIVE_ACTIVATION",
                        "live_activation": False,
                        "current_activation_id": current_report.get(
                            "current_activation_id"
                        ),
                        "current_activation_state": current_state or None,
                        "restore_marker_unresolved": False,
                        "activation_count": len(activations),
                        "collector": collector,
                        "next_action": "REGISTER_AUTHORIZE_ACTIVATE",
                    },
                    2,
                )
            health = list(collector.get("health_flags") or [])
            terminal = "DOCTOR_OK"
            next_action = str(current_report.get("next_action") or "TICK_ONCE")
            if "PROVIDER_FAILED" in health:
                terminal = "DOCTOR_PROVIDER_FAILED"
                next_action = "INSPECT_HTTP_CLASS"
            elif "DISCOVERY_GAP" in health or "DATA_STALE" in health:
                terminal = "DOCTOR_DISCOVERY_GAP"
                next_action = "INSPECT_SOURCE_POLL"
            elif "BACKLOG_RISK" in health:
                terminal = "DOCTOR_BACKLOG_RISK"
                next_action = "INSPECT_DUE_WORK"
            # DISCOVERY_COVERAGE_UNKNOWN is machine-visible commissioning signal,
            # not a hard doctor failure (unknown ≠ confirmed gap).
            code = 0 if terminal == "DOCTOR_OK" else 2
            return _emit(
                {
                    **current_timing,
                    "terminal": terminal,
                    "live_activation": live,
                    "current_activation_id": current_report.get("current_activation_id"),
                    "current_activation_state": current_state,
                    "restore_marker_unresolved": False,
                    "activation_count": len(activations),
                    "collector": collector,
                    "next_action": next_action,
                },
                code,
            )
        if args.command == "tick":
            if store.restore_marker_unresolved():
                return _emit(
                    {
                        "terminal": "RESTORE_MARKER_UNRESOLVED",
                        "provider_calls": 0,
                        "credential_reads": 0,
                    },
                    2,
                )
            requested_digest = args.schedule_sha256
            requested_activation = args.activation_id
            if requested_digest and requested_activation:
                candidates = [
                    (str(requested_digest), str(requested_activation))
                ]
            elif requested_digest or requested_activation:
                return _emit(
                    {
                        "terminal": "TICK_REFUSED_AMBIGUOUS_SELECTION",
                        "reason": "schedule and activation overrides must be supplied together",
                    },
                    2,
                )
            else:
                candidates = sorted(
                    (
                        str(row["schedule_sha256"]),
                        str(row["activation_id"]),
                    )
                    for row in store.list_activations()
                    if str(row["state"]) in {"ACTIVE", "DRAINING"}
                )
            if not candidates:
                return _emit(
                    {
                        "terminal": "TICK_REFUSED_NO_LIVE_DEFAULT",
                        "provider_calls": 0,
                        "credential_reads": 0,
                        "next_action": "REGISTER_AUTHORIZE_ACTIVATE",
                    },
                    2,
                )
            results: list[dict] = []
            for digest, activation_id in candidates:
                registered = store.get_registered_schedule(digest)
                activation = store.get_activation(digest, activation_id)
                if registered is None or activation is None:
                    if registered is None and activation is None:
                        return _emit(
                            {
                                "terminal": "TICK_REFUSED_NO_LIVE_DEFAULT",
                                "schedule_sha256": digest,
                                "activation_id": activation_id,
                                "provider_calls": 0,
                                "credential_reads": 0,
                            },
                            2,
                        )
                    return _emit(
                        {
                            "terminal": "TICK_REFUSED_AMBIGUOUS_SELECTION",
                            "schedule_sha256": digest,
                            "activation_id": activation_id,
                        },
                        2,
                    )
                if str(activation["state"]) == "PAUSED_OPERATOR":
                    return _emit(
                        {
                            "terminal": "PAUSED_OPERATOR",
                            "reason": "activation is paused; resume before tick",
                            "schedule_sha256": digest,
                            "activation_id": activation_id,
                            "next_action": "RESUME",
                        },
                        2,
                    )
                activation_state = str(activation["state"])
                if activation_state == "ACTIVE":
                    try:
                        active_transition_proven = (
                            activation_transition_research_event_proven(
                                data_root, activation, now=now
                            )
                        )
                    except Exception:
                        active_transition_proven = False
                    if not active_transition_proven:
                        return _emit(
                            {
                                "terminal": "TICK_REFUSED_ACTIVE_TRANSITION_PROOF_UNAVAILABLE",
                                "schedule_sha256": digest,
                                "activation_id": activation_id,
                                "provider_calls": 0,
                                "credential_reads": 0,
                                "next_action": "RECONCILE_ACTIVE_TRANSITION_PROOF",
                            },
                            2,
                        )
                elif activation_state == "DRAINING":
                    transition_payload = activation.get("payload")
                    if isinstance(transition_payload, str):
                        try:
                            transition_payload = json.loads(transition_payload)
                        except json.JSONDecodeError:
                            transition_payload = None
                    try:
                        if not isinstance(transition_payload, dict):
                            raise ValueError("TRANSITION_PAYLOAD_UNAVAILABLE")
                        transition_effective_at = parse_utc(
                            str(transition_payload["transition_effective_at"])
                        )
                        if (
                            str(transition_payload.get("new_state") or "")
                            != "DRAINING"
                            or str(transition_payload.get("prior_state") or "")
                            != "ACTIVE"
                        ):
                            raise ValueError("TRANSITION_PAYLOAD_INVALID")
                    except (KeyError, TypeError, ValueError):
                        return _emit(
                            {
                                "terminal": "TICK_REFUSED_DRAINING_TRANSITION_PROOF_UNAVAILABLE",
                                "schedule_sha256": digest,
                                "activation_id": activation_id,
                                "provider_calls": 0,
                                "credential_reads": 0,
                                "next_action": "RECONCILE_DRAINING_TRANSITION_PROOF",
                            },
                            2,
                        )
                    if transition_effective_at > now:
                        try:
                            active_transition_proven = (
                                activation_transition_research_event_proven(
                                    data_root, activation, now=now
                                )
                            )
                        except Exception:
                            active_transition_proven = False
                        if not active_transition_proven:
                            return _emit(
                                {
                                    "terminal": "TICK_REFUSED_ACTIVE_TRANSITION_PROOF_UNAVAILABLE",
                                    "schedule_sha256": digest,
                                    "activation_id": activation_id,
                                    "provider_calls": 0,
                                    "credential_reads": 0,
                                    "next_action": "RECONCILE_ACTIVE_TRANSITION_PROOF",
                                },
                                2,
                            )
                    else:
                        try:
                            draining_proof = resolve_late_recovery_proof(
                                data_root, activation, now=now
                            )
                        except Exception:
                            draining_proof = {"late_recovery_proof": "UNKNOWN"}
                        if draining_proof.get("late_recovery_proof") == "UNKNOWN":
                            return _emit(
                                {
                                    "terminal": "TICK_REFUSED_DRAINING_TRANSITION_PROOF_UNAVAILABLE",
                                    "schedule_sha256": digest,
                                    "activation_id": activation_id,
                                    "provider_calls": 0,
                                    "credential_reads": 0,
                                    "next_action": "RECONCILE_DRAINING_TRANSITION_PROOF",
                                },
                                2,
                            )
                try:
                    authority = _require_live_authority(
                        store,
                        root=ROOT,
                        document=registered["document"],
                        schedule_sha256=digest,
                        now=now,
                        receipt_sha256=str(
                            activation.get("authority_receipt_sha256") or ""
                        ),
                    )
                except ObservationLifecycleError as exc:
                    return _emit({"terminal": str(exc)}, 2)
                credential_holder: dict[str, str] = {}

                def _load() -> str:
                    if "value" not in credential_holder:
                        credential_holder["value"] = load_credential_after_activation(config)
                    return credential_holder["value"]

                # Authority precedes credential/transport materialization.
                physical = materialize_tick_physical_dependencies(
                    root=ROOT,
                    config=config,
                    load_credential=_load,
                    physical_overrides=physical_overrides,
                )
                result = tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=registered["document"],
                    activation_id=activation_id,
                    now=now,
                    opener=physical.opener,
                    credential_loader=physical.credential_loader,
                    producer_git_sha=producer,
                    clock=physical.pacing_clock,
                    fault_after=os.environ.get("OBSERVATION_SCHEDULE_PUBLISH_FAULT")
                    or config.get("publish_fault_after"),
                    provider_call_wall_seconds=resolve_provider_call_wall_seconds(config),
                )
                result["schedule_sha256"] = digest
                result["activation_id"] = activation_id
                results.append(result)
            if len(results) == 1:
                result = results[0]
                return _emit(
                    result,
                    0 if result.get("terminal") == "TICK_COMPLETE" else 2,
                )
            return _emit(
                {
                    "terminal": "TICK_COMPLETE"
                    if all(item.get("terminal") == "TICK_COMPLETE" for item in results)
                    else "TICK_PARTIAL",
                    "activations": results,
                    "provider_calls": sum(int(item.get("provider_calls", 0)) for item in results),
                    "credential_reads": sum(int(item.get("credential_reads", 0)) for item in results),
                },
                0 if all(item.get("terminal") == "TICK_COMPLETE" for item in results) else 2,
            )
        return _emit({"terminal": "COMMAND_UNKNOWN"}, 2)
    except (
        ObservationLifecycleError,
        ObservationRuntimeError,
        ObservationSchedulerError,
        ObservationScheduleError,
        ObservationScheduleStoreError,
        ObservationPanelPublisherError,
        PublicationFault,
        PrimitiveRegistryError,
        CompositionParityError,
    ) as exc:
        payload = {"terminal": str(exc)}
        next_action = owner_next_action_for_lifecycle_error(str(exc))
        if next_action is not None:
            payload["next_action"] = next_action
        return _emit(payload, 2)
    finally:
        if "store" in locals():
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
