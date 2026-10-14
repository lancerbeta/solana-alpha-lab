#!/usr/bin/env python3
"""ObservationSchedule operator CLI. No arbitrary URLs, SQL, or output paths."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.collector_read_model import (  # noqa: E402
    project_activation_as_of,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    ObservationScheduleError,
    load_observation_schedule,
    parse_utc,
)
from solana_alpha_lab.factory.observation_account_budget import (  # noqa: E402
    AccountBudgetError,
    account_budget_status,
    apply_account_budget,
    prepare_account_budget,
    revise_account_budget_policy,
)
from solana_alpha_lab.factory.observation_schedule_compiler import (  # noqa: E402
    compile_schedule_document,
)
from solana_alpha_lab.factory.managed_collection import (  # noqa: E402
    ManagedCollectionError,
    apply_profile,
    collection_status,
    plan_profile,
    reconcile_once,
    record_backup_health,
    rollback_profile,
    stop_intake,
    update_hold_incident,
)
from solana_alpha_lab.factory.observation_schedule_lifecycle import (  # noqa: E402
    ObservationLifecycleError,
    _require_live_authority,
    activation_transition_research_event_proven,
    activate_schedule,
    abort_schedule,
    authorize_schedule,
    pause_schedule,
    stop_episode_intake,
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


def _tick_candidates_as_of(
    rows: list[dict], now: datetime
) -> list[tuple[str, str]]:
    """Select live tick rows using the command entrypoint's captured clock."""

    candidates = []
    for row in rows:
        projected = project_activation_as_of(row, now)
        state = str(projected.get("state") or "")
        if state in {"ACTIVE", "DRAINING"}:
            candidates.append(
                (state != "DRAINING", str(row["schedule_sha256"]), str(row["activation_id"]))
            )
    # Committed tails (DRAINING) are served before any ACTIVE intake so a new
    # activation cannot spend the shared account quota a due tail needs now.
    return [(digest, activation_id) for _, digest, activation_id in sorted(candidates)]


# A tick before ``starts_at`` makes no provider call and is an honest idle, not a failure.
_IDLE_OK_TICK_TERMINALS = frozenset({"TICK_COMPLETE", "NOT_YET_ACTIVE"})


def _bind_runtime(
    args: argparse.Namespace, *, config: dict | None = None
) -> tuple[dict, Path, ObservationScheduleStore]:
    if config is None:
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


def _account_budget_command(args: argparse.Namespace, *, config: dict, store, now: datetime) -> int:
    """Shared managed-account budget OPERATE surface; never reads a credential value."""

    limits = {
        key: getattr(args, key, None)
        for key in (
            "provider_calls_per_utc_day_max",
            "modeled_credits_per_utc_day_max",
            "provider_calls_lifetime_max",
        )
    }
    # The logical credential slot name binds the account; its value is never read.
    locator = str(config.get("credential_env") or "")
    try:
        if args.command == "account-budget-status":
            result = account_budget_status(store, now=now)
            return _emit(result, 0 if result["mode"] != "CORRUPT" else 2)
        if args.command == "account-budget-prepare":
            result = prepare_account_budget(
                store, account_scope_id=args.account_scope_id, credential_locator=locator,
                limits=limits, now=now,
            )
            return _emit(result, 0 if result["terminal"] == "ACCOUNT_BUDGET_PLAN_READY" else 2)
        if args.command == "account-budget-apply":
            result = apply_account_budget(
                store, account_scope_id=args.account_scope_id, credential_locator=locator,
                limits=limits, expected_plan_sha256=args.expected_plan_sha256, now=now,
            )
            return _emit(result, 0)
        result = revise_account_budget_policy(
            store, expected_revision=args.expected_revision, limits=limits,
            reason=args.reason, now=now,
        )
        return _emit(result, 0)
    except AccountBudgetError as exc:
        return _emit({"terminal": str(exc), "next_action": "INSPECT_ACCOUNT_BUDGET_STATUS"}, 2)


_CANDIDATE_EXCEPTIONS = (
    ObservationLifecycleError,
    ObservationRuntimeError,
    ObservationSchedulerError,
    ObservationScheduleError,
    ObservationScheduleStoreError,
    ObservationPanelPublisherError,
    PublicationFault,
    PrimitiveRegistryError,
    CompositionParityError,
)


_RECONCILE_FAILURE_TERMINALS = frozenset(
    {"RECONCILE_FAILED", "RECONCILE_UNEXPECTED_ERROR", "RECONCILE_CHILD_STEP_FAILED"}
)


def _fresh_now(config: dict, physical_overrides: TickPhysicalOverrides | None, fallback: datetime) -> datetime:
    """Clock for work that follows provider ticks. A fixed test clock stays fixed."""

    if physical_overrides is not None:
        # The physical clock already moved while earlier activations ticked; a drain committed
        # at that later instant must be visible to the controller step that follows.
        reading = getattr(physical_overrides.pacing_clock, "now", None)
        try:
            return max(fallback, reading()) if callable(reading) else fallback
        except Exception:  # noqa: BLE001 - a stubbed clock never blocks the controller
            return fallback
    try:
        return max(fallback, resolve_clock(config))
    except ObservationRuntimeError:
        return fallback


def _tick_one_candidate(
    digest: str,
    activation_id: str,
    *,
    config: dict,
    data_root: Path,
    store: ObservationScheduleStore,
    now: datetime,
    producer: str,
    physical_overrides: TickPhysicalOverrides | None,
) -> dict:
    """Tick one live activation. Refusals are returned as the historical payload dicts."""

    registered = store.get_registered_schedule(digest)
    activation = store.get_activation(digest, activation_id)
    if registered is None or activation is None:
        if registered is None and activation is None:
            return {
                "terminal": "TICK_REFUSED_NO_LIVE_DEFAULT",
                "schedule_sha256": digest,
                "activation_id": activation_id,
                "provider_calls": 0,
                "credential_reads": 0,
            }
        return {
            "terminal": "TICK_REFUSED_AMBIGUOUS_SELECTION",
            "schedule_sha256": digest,
            "activation_id": activation_id,
        }
    projected = project_activation_as_of(activation, now)
    projected_state = str(projected.get("state") or "")
    if projected.get("future_transition_pending") is True and projected_state not in {"ACTIVE", "DRAINING"}:
        return {
            "terminal": "TICK_REFUSED_FUTURE_TRANSITION_PENDING",
            "schedule_sha256": digest,
            "activation_id": activation_id,
            "provider_calls": 0,
            "credential_reads": 0,
            "next_action": "WAIT_OR_INSPECT_SCHEDULED_CUTOVER",
            "pending_activations": [
                {
                    "schedule_sha256": digest,
                    "activation_id": activation_id,
                    "projected_state": projected_state,
                }
            ],
        }
    activation_state = projected_state or str(activation["state"])
    if activation_state == "PAUSED_OPERATOR":
        return {
            "terminal": "PAUSED_OPERATOR",
            "reason": "activation is paused; resume before tick",
            "schedule_sha256": digest,
            "activation_id": activation_id,
            "next_action": "RESUME",
        }
    if activation_state == "ACTIVE":
        try:
            active_transition_proven = activation_transition_research_event_proven(
                data_root, activation, now=now
            )
        except Exception:
            active_transition_proven = False
        if not active_transition_proven:
            return {
                "terminal": "TICK_REFUSED_ACTIVE_TRANSITION_PROOF_UNAVAILABLE",
                "schedule_sha256": digest,
                "activation_id": activation_id,
                "provider_calls": 0,
                "credential_reads": 0,
                "next_action": "RECONCILE_ACTIVE_TRANSITION_PROOF",
            }
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
            transition_effective_at = parse_utc(str(transition_payload["transition_effective_at"]))
        except (KeyError, TypeError, ValueError):
            return {
                "terminal": "TICK_REFUSED_DRAINING_TRANSITION_PROOF_UNAVAILABLE",
                "schedule_sha256": digest,
                "activation_id": activation_id,
                "provider_calls": 0,
                "credential_reads": 0,
                "next_action": "RECONCILE_DRAINING_TRANSITION_PROOF",
            }
        if transition_effective_at > now and not activation_transition_research_event_proven(
            data_root, activation, now=now
        ):
            return {
                "terminal": "TICK_REFUSED_FUTURE_TRANSITION_PENDING",
                "schedule_sha256": digest,
                "activation_id": activation_id,
                "provider_calls": 0,
                "credential_reads": 0,
                "next_action": "WAIT_OR_INSPECT_SCHEDULED_CUTOVER",
            }
    try:
        _require_live_authority(
            store,
            root=ROOT,
            document=registered["document"],
            schedule_sha256=digest,
            now=now,
            receipt_sha256=str(activation.get("authority_receipt_sha256") or ""),
        )
    except ObservationLifecycleError as exc:
        return {"terminal": str(exc), "schedule_sha256": digest, "activation_id": activation_id}
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
        fault_after=os.environ.get("OBSERVATION_SCHEDULE_PUBLISH_FAULT") or config.get("publish_fault_after"),
        provider_call_wall_seconds=resolve_provider_call_wall_seconds(config),
    )
    result["schedule_sha256"] = digest
    result["activation_id"] = activation_id
    return result


def _run_candidates(
    candidates: list[tuple[str, str]],
    *,
    isolate: bool,
    **context,
) -> list[dict]:
    """Tick candidates in order. With ``isolate`` one blocked activation never starves the rest."""

    results: list[dict] = []
    for digest, activation_id in candidates:
        try:
            results.append(_tick_one_candidate(digest, activation_id, **context))
        except _CANDIDATE_EXCEPTIONS as exc:
            if not isolate:
                raise
            failed = {"terminal": str(exc), "schedule_sha256": digest, "activation_id": activation_id}
            next_action = owner_next_action_for_lifecycle_error(str(exc))
            if next_action is not None:
                failed["next_action"] = next_action
            results.append(failed)
    return results


def _tick_command(
    args: argparse.Namespace,
    *,
    config: dict,
    data_root: Path,
    store: ObservationScheduleStore,
    now: datetime,
    producer: str,
    physical_overrides: TickPhysicalOverrides | None,
) -> int:
    if store.restore_marker_unresolved():
        return _emit(
            {"terminal": "RESTORE_MARKER_UNRESOLVED", "provider_calls": 0, "credential_reads": 0},
            2,
        )
    requested_digest = args.schedule_sha256
    requested_activation = args.activation_id
    activation_rows = store.list_activations()
    explicit = bool(requested_digest and requested_activation)
    if explicit:
        candidates = [(str(requested_digest), str(requested_activation))]
    elif requested_digest or requested_activation:
        return _emit(
            {
                "terminal": "TICK_REFUSED_AMBIGUOUS_SELECTION",
                "reason": "schedule and activation overrides must be supplied together",
            },
            2,
        )
    else:
        candidates = _tick_candidates_as_of(activation_rows, now)
    # Minimal operator stores (and older builds) have no managed tables: unmanaged by definition.
    lineages_of = getattr(store, "managed_lineages", None)
    managed = (not explicit) and callable(lineages_of) and bool(lineages_of())
    context = {
        "config": config,
        "data_root": data_root,
        "store": store,
        "producer": producer,
        "physical_overrides": physical_overrides,
    }
    results: list[dict] = []
    reconcile_report: dict | None = None
    if candidates:
        results = _run_candidates(candidates, isolate=managed, now=now, **context)
    if managed:
        # Order: committed tails first, then one bounded controller step, then the new child's
        # own first tick. The controller never calls a provider or reads a credential.
        fresh = _fresh_now(config, physical_overrides, now)
        try:
            reconcile_report = reconcile_once(
                root=ROOT, data_root=data_root, store=store, now=fresh, producer_git_sha=producer
            )
        except (ManagedCollectionError,) + _CANDIDATE_EXCEPTIONS as exc:
            reconcile_report = {"terminal": "RECONCILE_FAILED", "reason": str(exc)}
        activated = reconcile_report.get("activated")
        if isinstance(activated, dict):
            results += _run_candidates(
                [(str(activated["schedule_sha256"]), str(activated["activation_id"]))],
                isolate=True,
                now=fresh,
                **context,
            )
    if managed and results:
        try:
            update_hold_incident(store, results, _fresh_now(config, physical_overrides, now))
        except ObservationScheduleStoreError:
            pass  # never fail committed ticks over incident bookkeeping; the next tick retries
    if not results:
        pending_future = []
        for row in activation_rows:
            projected = project_activation_as_of(row, now)
            projected_state = str(projected.get("state") or "")
            if projected.get("future_transition_pending") is True and projected_state not in {"ACTIVE", "DRAINING"}:
                pending_future.append(
                    {
                        "schedule_sha256": str(row.get("schedule_sha256") or ""),
                        "activation_id": str(row.get("activation_id") or ""),
                        "projected_state": projected_state,
                    }
                )
        if pending_future:
            return _emit(
                {
                    "terminal": "TICK_REFUSED_FUTURE_TRANSITION_PENDING",
                    "provider_calls": 0,
                    "credential_reads": 0,
                    "next_action": "WAIT_OR_INSPECT_SCHEDULED_CUTOVER",
                    "pending_activations": sorted(
                        pending_future,
                        key=lambda item: (item["schedule_sha256"], item["activation_id"]),
                    ),
                    **({"managed": reconcile_report} if reconcile_report else {}),
                },
                2,
            )
        if reconcile_report is not None:
            # Managed and nothing live: the controller owns the next step; not a manual register.
            waiting = str(reconcile_report.get("terminal") or "").startswith(("RECONCILE_WAIT", "RECONCILE_VALIDITY"))
            return _emit(
                {
                    "terminal": "TICK_COMPLETE" if waiting else "TICK_REFUSED_NO_LIVE_DEFAULT",
                    "provider_calls": 0,
                    "credential_reads": 0,
                    "next_action": "NONE" if waiting else "INSPECT_MANAGED_STATE",
                    "managed": reconcile_report,
                },
                0 if waiting else 2,
            )
        return _emit(
            {
                "terminal": "TICK_REFUSED_NO_LIVE_DEFAULT",
                "provider_calls": 0,
                "credential_reads": 0,
                "next_action": "REGISTER_AUTHORIZE_ACTIVATE",
            },
            2,
        )
    extra = {"managed": reconcile_report} if reconcile_report else {}
    if len(results) == 1 and not extra:
        result = results[0]
        return _emit(result, 0 if result.get("terminal") in _IDLE_OK_TICK_TERMINALS else 2)
    ok = all(item.get("terminal") in _IDLE_OK_TICK_TERMINALS for item in results)
    reconcile_terminal = str((reconcile_report or {}).get("terminal") or "")
    if reconcile_terminal in _RECONCILE_FAILURE_TERMINALS or reconcile_terminal.startswith("RECONCILE_BLOCKED_MANAGED_GRANT"):
        ok = False  # a failed controller step must be visible to exit-code wrappers too
    return _emit(
        {
            "terminal": "TICK_COMPLETE" if ok else "TICK_PARTIAL",
            "activations": results,
            "provider_calls": sum(int(item.get("provider_calls", 0)) for item in results),
            "credential_reads": sum(int(item.get("credential_reads", 0)) for item in results),
            **extra,
        },
        0 if ok else 2,
    )


def _collection_params(args: argparse.Namespace) -> dict:
    limits = {
        key: getattr(args, key)
        for key in (
            "admissions_per_utc_day",
            "rolling_24h_admissions",
            "active_episode_cap",
            "provider_calls_per_utc_day",
            "modeled_credits_per_utc_day",
            "cumulative_calls",
        )
        if getattr(args, key, None) is not None
    }
    acceptance = None
    if getattr(args, "target_acceptance_sha256", None):
        acceptance = {
            "acceptance_sha256": args.target_acceptance_sha256,
            "max_projected_bytes": args.target_acceptance_max_projected_bytes,
        }
    return {
        "limits": limits,
        "account_scope_id": args.account_scope_id,
        "storage_basis_activation_id": args.storage_basis_activation_id,
        "validity_mode": args.validity,
        "intake_until": args.intake_until,
        "bootstrap_not_before": args.bootstrap_not_before,
        "protected_bridge_activation_id": args.protected_bridge_activation_id,
        "planning_horizon_days": args.planning_horizon_days,
        "backup_receipt_relative": args.backup_receipt_relative,
        "backup_max_age_seconds": args.backup_max_age_seconds,
        "measured_growth_bytes_per_day": args.measured_growth_bytes_per_day,
        "target_acceptance": acceptance,
        "expected_revision": args.expected_revision,
    }


def _sole_lineage(store: ObservationScheduleStore, requested: str | None) -> str:
    lineages = store.managed_lineages()
    if requested:
        if requested not in lineages:
            raise ManagedCollectionError("MANAGED_LINEAGE_UNKNOWN")
        return requested
    if len(lineages) != 1:
        raise ManagedCollectionError("MANAGED_LINEAGE_SELECTOR_REQUIRED" if lineages else "MANAGED_UNMANAGED")
    return lineages[0]


def _collection_command(
    args: argparse.Namespace,
    *,
    config: dict,
    data_root: Path,
    store: ObservationScheduleStore,
    now: datetime,
    producer: str,
) -> int:
    """Managed continuity OPERATE surface. No provider call, no credential read."""

    try:
        if args.command == "collection-status":
            return _emit(
                collection_status(
                    store=store, data_root=data_root, now=now, measure_storage=args.measure_storage
                ),
                0,
            )
        if args.command == "collection-plan":
            result = plan_profile(
                root=ROOT,
                store=store,
                template_schedule_sha256=args.template_schedule_sha256,
                params=_collection_params(args),
                now=now,
            )
            return _emit(result, 0 if result["terminal"] == "MANAGED_PLAN_READY" else 2)
        if args.command == "collection-apply":
            return _emit(
                apply_profile(
                    root=ROOT,
                    store=store,
                    template_schedule_sha256=args.template_schedule_sha256,
                    params=_collection_params(args),
                    expected_proposal_sha256=args.expected_proposal_sha256,
                    phrase=args.phrase,
                    now=now,
                ),
                0,
            )
        if args.command == "collection-reconcile":
            report = reconcile_once(
                root=ROOT, data_root=data_root, store=store, now=now, producer_git_sha=producer
            )
            return _emit(report, 0)
        if args.command == "collection-stop-intake":
            return _emit(
                stop_intake(
                    root=ROOT,
                    data_root=data_root,
                    store=store,
                    lineage=_sole_lineage(store, args.lineage),
                    expected_revision=args.expected_revision,
                    now=now,
                    producer_git_sha=producer,
                ),
                0,
            )
        if args.command == "collection-rollback":
            return _emit(
                rollback_profile(
                    store=store,
                    lineage=_sole_lineage(store, args.lineage),
                    to_revision=args.to_revision,
                    expected_revision=args.expected_revision,
                    now=now,
                    phrase=args.phrase,
                ),
                0,
            )
        if args.command == "collection-record-backup":
            lineage = _sole_lineage(store, args.lineage)
            revision = int(store.managed_control(lineage)["current_revision"])
            relative = store.managed_profile(lineage, revision)["payload"]["profile"]["resource_policy"][
                "backup_receipt_relative"
            ]
            return _emit(
                {
                    "terminal": "MANAGED_BACKUP_RECEIPT_RECORDED",
                    "receipt": record_backup_health(
                        data_root=data_root,
                        relative=relative,
                        checkpoint_at=parse_utc(args.checkpoint_at),
                        artifact_sha256=args.artifact_sha256,
                        coverage=args.coverage,
                        now=now,
                    ),
                    "authenticates_remote_content": False,
                },
                0,
            )
    except ManagedCollectionError as exc:
        hints = {
            "MANAGED_PROPOSAL_MISMATCH": "RERUN_COLLECTION_PLAN_AND_USE_ITS_PROPOSAL_SHA256",
            "BLOCKED_AUTHORITY": "COPY_EXACT_OWNER_PHRASE_FROM_COLLECTION_PLAN",
            "MANAGED_REVISION_CONFLICT": "READ_COLLECTION_STATUS_AND_USE_ITS_REVISION",
            "ROLLBACK_NOT_RESTRICTIVE_PHRASE_REQUIRED": "RERUN_ROLLBACK_WITH_THE_EXACT_PHRASE_OF_THE_NEW_REVISION",
        }
        return _emit({"terminal": str(exc), "reason": str(exc),
                      "next_action": hints.get(str(exc), "INSPECT_COLLECTION_STATUS")}, 2)
    return _emit({"terminal": "COMMAND_UNKNOWN"}, 2)


def _collection_readonly(args: argparse.Namespace, *, config: dict, now: datetime) -> int:
    """status/plan never create the store, tables, events, keys or network calls."""

    explicit = getattr(args, "data_root", None)
    if explicit:
        resolved = Path(explicit)
        if not resolved.is_absolute():
            raise ObservationRuntimeError("DATA_ROOT_NOT_ABSOLUTE")
        ops = resolved / "observation_schedule_state.sqlite"
    else:
        resolved = resolve_data_root(ROOT, str(config["data_root"]))
        ops = resolve_data_root(ROOT, str(config["ops_store_relative"]))
    try:
        store = ObservationScheduleStore(ops, readonly=True, immutable=False)
    except ObservationScheduleStoreError as exc:
        return _emit({"terminal": str(exc), "next_action": "INSPECT_OPS_STORE_PRESENCE"}, 2)
    try:
        return _collection_command(
            args, config=config, data_root=resolved, store=store, now=now, producer=""
        )
    finally:
        store.close()


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
        "stop-intake",
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
        if name == "activate":
            cmd.add_argument("--episode-storage-commissioning", type=Path)
        if name in {"activate", "pause", "stop-intake", "abort", "resume", "snapshot"}:
            cmd.add_argument("--activation-id", required=True)
        if name == "abort":
            cmd.add_argument("--reason", required=True)
        if name == "rollover":
            cmd.add_argument("--predecessor-schedule-sha256", required=True)
            cmd.add_argument("--predecessor-activation-id", required=True)
            cmd.add_argument("--successor-schedule-sha256", required=True)
            cmd.add_argument("--successor-activation-id", required=True)
            cmd.add_argument("--cutover-at", required=True)
        if name in {"authorize", "activate", "pause", "stop-intake", "abort", "resume", "snapshot", "status"}:
            cmd.add_argument("--schedule-sha256")
        if name == "status":
            cmd.add_argument("--activation-id")
    for name in ("account-budget-prepare", "account-budget-apply", "account-budget-revise",
                 "account-budget-status"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--runtime-config", default=DEFAULT_RUNTIME_RELATIVE)
        cmd.add_argument("--data-root")
        if name in {"account-budget-prepare", "account-budget-apply"}:
            cmd.add_argument("--account-scope-id", required=True)
        if name != "account-budget-status":
            cmd.add_argument("--provider-calls-per-utc-day-max", type=int, required=True)
            cmd.add_argument("--modeled-credits-per-utc-day-max", type=int, required=True)
            cmd.add_argument("--provider-calls-lifetime-max", type=int, required=True)
        if name == "account-budget-apply":
            cmd.add_argument("--expected-plan-sha256", required=True)
        if name == "account-budget-revise":
            cmd.add_argument("--expected-revision", type=int, required=True)
            cmd.add_argument("--reason", required=True)
    for name in (
        "collection-status",
        "collection-plan",
        "collection-apply",
        "collection-reconcile",
        "collection-stop-intake",
        "collection-rollback",
        "collection-record-backup",
    ):
        cmd = sub.add_parser(name)
        cmd.add_argument("--runtime-config", default=DEFAULT_RUNTIME_RELATIVE)
        cmd.add_argument("--data-root")
        if name == "collection-status":
            cmd.add_argument("--measure-storage", action="store_true")
        if name in {"collection-plan", "collection-apply"}:
            cmd.add_argument("--template-schedule-sha256", required=True)
            cmd.add_argument("--account-scope-id", required=True)
            cmd.add_argument("--storage-basis-activation-id", required=True)
            cmd.add_argument("--expected-revision", type=int)
            cmd.add_argument("--admissions-per-utc-day", type=int)
            cmd.add_argument("--rolling-24h-admissions", type=int)
            cmd.add_argument("--active-episode-cap", type=int)
            cmd.add_argument("--provider-calls-per-utc-day", type=int)
            cmd.add_argument("--modeled-credits-per-utc-day", type=int)
            cmd.add_argument("--cumulative-calls", type=int)
            cmd.add_argument("--validity", choices=("UNTIL_REVOKED", "UNTIL_DATE"), default="UNTIL_REVOKED")
            cmd.add_argument("--intake-until")
            cmd.add_argument("--bootstrap-not-before")
            cmd.add_argument("--protected-bridge-activation-id")
            cmd.add_argument("--planning-horizon-days", type=int, default=180)
            cmd.add_argument("--backup-receipt-relative")
            cmd.add_argument("--backup-max-age-seconds", type=int)
            cmd.add_argument("--measured-growth-bytes-per-day", type=int)
            cmd.add_argument("--target-acceptance-sha256")
            cmd.add_argument("--target-acceptance-max-projected-bytes", type=int)
        if name == "collection-apply":
            cmd.add_argument("--expected-proposal-sha256", required=True)
            cmd.add_argument("--phrase", required=True)
        if name == "collection-reconcile":
            cmd.add_argument("--once", action="store_true", required=True)
        if name in {"collection-stop-intake", "collection-rollback", "collection-record-backup"}:
            cmd.add_argument("--lineage")
        if name in {"collection-stop-intake", "collection-rollback"}:
            cmd.add_argument("--expected-revision", type=int, required=True)
        if name == "collection-rollback":
            cmd.add_argument("--to-revision", type=int, required=True)
            cmd.add_argument("--phrase")
        if name == "collection-record-backup":
            cmd.add_argument("--checkpoint-at", required=True)
            cmd.add_argument("--artifact-sha256", required=True)
            cmd.add_argument("--coverage", required=True)
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
        relative = getattr(args, "runtime_config", None) or DEFAULT_RUNTIME_RELATIVE
        runtime_config = load_runtime_config(ROOT, relative)
        if physical_overrides is not None:
            now = physical_overrides.now
        else:
            now = resolve_clock(runtime_config)
        if args.command in {"collection-status", "collection-plan"}:
            return _collection_readonly(args, config=runtime_config, now=now)
        config, data_root, store = _bind_runtime(args, config=runtime_config)
        producer = git_sha(ROOT, config.get("producer_git_sha"))
        if args.command.startswith("account-budget-"):
            return _account_budget_command(args, config=config, store=store, now=now)
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
            storage_commissioning = None
            if args.episode_storage_commissioning is not None:
                try:
                    path = args.episode_storage_commissioning
                    if path.stat().st_size > 65536 or path.is_symlink():
                        raise ValueError()
                    with path.open("rb") as handle:
                        raw = handle.read(65537)
                    if len(raw) > 65536:
                        raise ValueError()
                    storage_commissioning = json.loads(raw)
                except (OSError, ValueError, RecursionError):
                    return _emit({"terminal": "EPISODE_STORAGE_BINDING_INVALID"}, 2)
            result = activate_schedule(
                root=ROOT,
                data_root=data_root,
                store=store,
                schedule_sha256=digest,
                activation_id=args.activation_id,
                now=now,
                producer_git_sha=producer,
                storage_commissioning=storage_commissioning,
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
        if args.command == "stop-intake":
            digest = args.schedule_sha256 or config.get("schedule_sha256")
            if not digest and args.schedule:
                digest = load_observation_schedule(ROOT, args.schedule)["schedule_sha256"]
            if not digest:
                return _emit({"terminal": "SCHEDULE_SHA256_REQUIRED"}, 2)
            result = stop_episode_intake(
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
                classify_doctor_current_activation,
            )

            unresolved = store.restore_marker_unresolved()
            activations = store.list_activations()
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
                activations,
                recovery_proofs=recovery_proofs,
                now=now,
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
            if current_state == "ACTIVE":
                current_row = next(
                    (
                        row
                        for row in activations
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
            return _tick_command(
                args,
                config=config,
                data_root=data_root,
                store=store,
                now=now,
                producer=producer,
                physical_overrides=physical_overrides,
            )
        if args.command.startswith("collection-"):
            return _collection_command(
                args, config=config, data_root=data_root, store=store, now=now, producer=producer
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
