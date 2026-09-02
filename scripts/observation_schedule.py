#!/usr/bin/env python3
"""ObservationSchedule operator CLI. No arbitrary URLs, SQL, or output paths."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    ObservationScheduleError,
    load_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule_compiler import (  # noqa: E402
    compile_schedule_document,
)
from solana_alpha_lab.factory.observation_schedule_lifecycle import (  # noqa: E402
    ObservationLifecycleError,
    _require_live_authority,
    activate_schedule,
    abort_schedule,
    authorize_schedule,
    pause_schedule,
    register_schedule,
    resume_schedule,
    rollover_schedule,
    snapshot_schedule,
    status_schedule,
)
from solana_alpha_lab.factory.observation_schedule_runtime import (  # noqa: E402
    DEFAULT_RUNTIME_RELATIVE,
    ObservationRuntimeError,
    build_opener,
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


def main(argv: list[str] | None = None) -> int:
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
        if name in {"authorize", "activate", "pause", "abort", "resume", "snapshot", "status"}:
            cmd.add_argument("--schedule-sha256")
        if name == "status":
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
            result = status_schedule(
                store,
                schedule_sha256=getattr(args, "schedule_sha256", None) or config.get("schedule_sha256"),
                activation_id=getattr(args, "activation_id", None) or config.get("activation_id"),
                now=now,
                deploy_git_sha=producer,
            )
            return _emit(result, 0)
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
                build_collector_read_model,
            )

            unresolved = store.restore_marker_unresolved()
            activations = store.list_activations()
            live = any(row["state"] == "ACTIVE" for row in activations)
            collector = build_collector_read_model(
                store,
                now=now,
                schedule_sha256=getattr(args, "schedule_sha256", None)
                or config.get("schedule_sha256"),
                activation_id=getattr(args, "activation_id", None)
                or config.get("activation_id"),
                deploy_git_sha=producer,
            )
            if unresolved:
                return _emit(
                    {
                        "terminal": "DOCTOR_RESTORE_MARKER_UNRESOLVED",
                        "live_activation": live,
                        "restore_marker_unresolved": True,
                        "activation_count": len(activations),
                        "collector": collector,
                        "next_action": "RESOLVE_RESTORE_MARKER",
                    },
                    2,
                )
            aborted = any(row["state"] == "ABORTED_SAFETY" for row in activations)
            if aborted and not live:
                return _emit(
                    {
                        "terminal": "DOCTOR_ABORTED_SAFETY",
                        "live_activation": False,
                        "restore_marker_unresolved": False,
                        "activation_count": len(activations),
                        "collector": collector,
                        "next_action": "MUST_NOT_RESUME",
                    },
                    2,
                )
            paused = any(row["state"] == "PAUSED_OPERATOR" for row in activations)
            if paused and not live:
                must_not_resume = any(
                    dict(row.get("payload") or {}).get("must_not_resume") is True
                    or str(dict(row.get("payload") or {}).get("abort_reason") or "").strip()
                    for row in activations
                    if row["state"] == "PAUSED_OPERATOR"
                )
                return _emit(
                    {
                        "terminal": "DOCTOR_PAUSED",
                        "live_activation": False,
                        "restore_marker_unresolved": False,
                        "activation_count": len(activations),
                        "collector": collector,
                        "next_action": "MUST_NOT_RESUME" if must_not_resume else "RESUME",
                    },
                    2,
                )
            if not live:
                return _emit(
                    {
                        "terminal": "DOCTOR_NO_LIVE_ACTIVATION",
                        "live_activation": False,
                        "restore_marker_unresolved": False,
                        "activation_count": len(activations),
                        "collector": collector,
                        "next_action": "REGISTER_AUTHORIZE_ACTIVATE",
                    },
                    2,
                )
            health = list(collector.get("health_flags") or [])
            terminal = "DOCTOR_OK"
            next_action = "TICK_ONCE"
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
                    "terminal": terminal,
                    "live_activation": True,
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

                if config.get("fake_provider_fixture"):
                    opener = build_opener(ROOT, config)
                    credential_loader = _load
                else:
                    # The exact authority check above precedes the sole secret read.
                    opener = build_opener(ROOT, config, credential=_load())
                    credential_loader = None
                result = tick_once(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    schedule=registered["document"],
                    activation_id=activation_id,
                    now=now,
                    opener=opener,
                    credential_loader=credential_loader,
                    producer_git_sha=producer,
                    clock=(
                        (lambda: datetime.now(UTC))
                        if not config.get("fake_provider_fixture")
                        else None
                    ),
                    fault_after=os.environ.get("OBSERVATION_SCHEDULE_PUBLISH_FAULT")
                    or config.get("publish_fault_after"),
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
    ) as exc:
        return _emit({"terminal": str(exc)}, 2)
    finally:
        if "store" in locals():
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
