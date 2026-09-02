"""Persistent ObservationSchedule lifecycle commands."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jsonschema

from solana_alpha_lab.factory.observation_panel_publisher import (
    build_panel_snapshot,
    has_open_publication_jobs,
    load_pending_observation_bindings,
    persist_observation_schedule,
    persist_panel_snapshot_binding,
    satisfy_pending_observation_binding,
)
from solana_alpha_lab.factory.observation_primitive_registry import (
    load_observation_primitive_registry,
)
from solana_alpha_lab.factory.observation_schedule import (
    canonical_sha256,
    parse_utc,
    render_utc,
    schedule_sha256 as compute_schedule_sha256,
    validate_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule_compiler import compile_schedule_document
from solana_alpha_lab.factory.observation_schedule_store import (
    ObservationScheduleStore,
    ObservationScheduleStoreError,
)
from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent, ResearchStore

AUTHORITY_SCHEMA_RELATIVE = "catalog/schemas/observation_schedule_authority_v1.schema.json"
PRODUCER_CAPABILITY = "CAP-OBSERVATION-SCHEDULE-COMPILE-BIND-001"
APPROVED_CAPABILITY = "CAP-OBSERVATION-SCHEDULE-COMPILE-BIND-001"
OPS_STORE_FILENAME = "observation_schedule_state.sqlite"
FIXTURE_PRODUCER_GIT_SHA = "c" * 40


def observation_ops_store_path(data_root: Path) -> Path:
    return Path(data_root) / OPS_STORE_FILENAME


def require_production_producer_git_sha(producer_git_sha: str | None) -> str:
    """Fail closed when a durable write has no explicit producer Git SHA.

    An explicit 40-hex value is required. The implicit fixture fallback is
    forbidden. Test-only callers may pass a fixture SHA themselves.
    """

    if not isinstance(producer_git_sha, str) or len(producer_git_sha) != 40:
        raise ObservationLifecycleError("PRODUCER_GIT_SHA_REQUIRED")
    if producer_git_sha == FIXTURE_PRODUCER_GIT_SHA:
        raise ObservationLifecycleError("FIXTURE_PRODUCER_GIT_SHA_FORBIDDEN")
    return producer_git_sha


class ObservationLifecycleError(ValueError):
    """Typed lifecycle failure."""


def _research_event(
    *,
    record_id: str,
    record_kind: RecordKind,
    entity_id: str,
    payload: Mapping[str, Any],
    now: datetime,
    producer_git_sha: str,
    run_id: str | None,
    transaction_id: str,
) -> ResearchEvent:
    payload_json = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return ResearchEvent(
        record_id=record_id,
        record_kind=record_kind,
        entity_id=entity_id,
        hypothesis_version_id=None,
        run_id=run_id,
        transaction_id=transaction_id,
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id=PRODUCER_CAPABILITY,
        producer_git_sha=producer_git_sha,
        created_at=now,
    )


def _append_or_replay(data_root: Path, event: ResearchEvent) -> None:
    store = ResearchStore(data_root)
    try:
        store.append([event], transaction_id=event.transaction_id)
    except Exception:
        existing = list(store.iter_committed_records())
        match = next((item for item in existing if item.record_id == event.record_id), None)
        if match is None:
            raise
        if match.payload_sha256 != event.payload_sha256:
            raise ObservationLifecycleError("SCHEDULE_IDENTITY_CONFLICT")


def _used_provider_route_ids(
    root: Path,
    document: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    registry = load_observation_primitive_registry(root)
    primitive_ids = [str(document["source_poll"]["primitive_id"])]
    for point in [document["x_point"], *list(document["y_points"])]:
        for bundle_id in point["bundle_ids"]:
            primitive_ids.append(
                str(registry.require_bundle(str(bundle_id))["primitive_id"])
            )
    unique_primitives = sorted(set(primitive_ids))
    routes = sorted(
        {
            str(route)
            for primitive_id in unique_primitives
            for route in registry.require_primitive(primitive_id)["provider_route_ids"]
        }
    )
    return unique_primitives, routes


def _authority_policy(
    *,
    root: Path,
    document: Mapping[str, Any],
    schedule_key: str,
    expires_at: str,
) -> dict[str, Any]:
    primitive_ids, routes = _used_provider_route_ids(root, document)
    registry = load_observation_primitive_registry(root)
    authority_profile = registry.require_authority_profile(
        str(document["authority"]["profile_id"])
    )
    allowed_routes = {
        str(route) for route in authority_profile.get("allowed_route_ids") or []
    }
    if not set(routes).issubset(allowed_routes):
        raise ObservationLifecycleError("BLOCKED_AUTHORITY")
    return {
        "schedule_sha256": str(document["schedule_sha256"]),
        "schedule_key": schedule_key,
        "activation_starts_at": document["activation"]["starts_at"],
        "activation_stops_admitting_at": document["activation"]["stops_admitting_at"],
        "used_primitive_ids": primitive_ids,
        "provider_route_ids": routes,
        "provider_calls_per_utc_day_max": int(
            document["budgets"]["provider_calls_per_utc_day_max"]
        ),
        "provider_calls_lifetime_max": int(
            document["budgets"]["provider_calls_lifetime_max"]
        ),
        "modeled_provider_credits_per_utc_day_max": int(
            document["budgets"]["modeled_provider_credits_per_utc_day_max"]
        ),
        "cash_usd_max": "0",
        "retry": False,
        "fallback": False,
        "build_execute_wallet_signer_transaction": False,
        "expiry": expires_at,
        "approved_capability_ids": [APPROVED_CAPABILITY],
        "allowed_credential_class": "LOCAL_ENV_CREDENTIAL",
        "policy_digest_version": "OBSERVATION_AUTHORITY_POLICY_V1",
    }


def _minimum_expiry(document: Mapping[str, Any]) -> datetime:
    points = [document["x_point"], *list(document["y_points"])]
    horizon = max(
        int(point["due_offset_seconds"]) + int(point["allowed_lateness_seconds"])
        for point in points
    )
    return parse_utc(document["activation"]["stops_admitting_at"]) + timedelta(
        seconds=horizon
    )


def expected_authority_phrase(
    *,
    schedule_sha256: str,
    schedule_key: str,
    activation_starts_at: str,
    activation_stops_admitting_at: str,
    provider_route_ids: Sequence[str],
    expires_at: str,
    policy_digest: str,
) -> str:
    """Return the one exact owner phrase accepted for this envelope."""
    routes = ",".join(sorted(str(route) for route in provider_route_ids))
    return (
        "AUTHORIZE OBSERVATION SCHEDULE "
        f"{schedule_sha256} KEY {schedule_key} "
        f"STARTS {activation_starts_at} STOPS {activation_stops_admitting_at} "
        f"ROUTES {routes} EXPIRES {expires_at} POLICY {policy_digest}"
    )


def register_schedule(
    *,
    root: Path,
    data_root: Path,
    store: ObservationScheduleStore,
    document: Mapping[str, Any],
    now: datetime,
    producer_git_sha: str,
) -> dict[str, Any]:
    registry = load_observation_primitive_registry(root)
    registry.verify_implementation_hashes()
    compiled = compile_schedule_document(document, root=root)
    if compiled.schedule is None or compiled.schedule_sha256 is None:
        return {
            "terminal": compiled.terminal,
            "reason_codes": list(compiled.reason_codes),
            "schedule_sha256": None,
        }
    validated = validate_observation_schedule(compiled.schedule, root=root)
    digest = str(validated["schedule_sha256"])
    if digest != compiled.schedule_sha256:
        raise ObservationLifecycleError("INVALID_IDENTITY")
    try:
        outcome = store.persist_registered_schedule(
            schedule_sha256=digest,
            schedule_key=str(validated["schedule_key"]),
            document=validated,
            clock=now,
        )
    except ObservationScheduleStoreError as exc:
        raise ObservationLifecycleError(str(exc)) from exc
    canonical_registered = store.get_registered_schedule(digest)
    if canonical_registered is None:
        raise ObservationLifecycleError("SCHEDULE_NOT_PERSISTED")
    persist_observation_schedule(
        data_root=data_root,
        schedule=canonical_registered["document"],
        now=now,
        producer_git_sha=producer_git_sha,
    )
    terminal = (
        "REGISTER_REPLAY"
        if outcome == "REGISTER_REPLAY"
        else "ATTACHED_TO_EXISTING_PLAN"
        if outcome == "ATTACHED_TO_EXISTING_PLAN"
        else "REGISTERED"
    )
    return {
        "terminal": terminal,
        "schedule_sha256": digest,
        "schedule_key": validated["schedule_key"],
        "next_action": compiled.next_action,
    }


def build_authority_request(
    *,
    root: Path,
    document: Mapping[str, Any],
    predecessor_schedule_sha256: str | None = None,
    successor_schedule_sha256: str | None = None,
    cutover_at: str | None = None,
) -> dict[str, Any]:
    """Build the exact owner-authority envelope without authorizing."""

    digest = str(document["schedule_sha256"])
    _primitive_ids, routes = _used_provider_route_ids(root, document)
    del _primitive_ids
    minimum_expiry = _minimum_expiry(document)
    expires = render_utc(minimum_expiry)
    policy = _authority_policy(
        root=root,
        document=document,
        schedule_key=str(document["schedule_key"]),
        expires_at=expires,
    )
    policy_digest = canonical_sha256(policy)
    phrase = expected_authority_phrase(
        schedule_sha256=digest,
        schedule_key=str(document["schedule_key"]),
        activation_starts_at=str(document["activation"]["starts_at"]),
        activation_stops_admitting_at=str(document["activation"]["stops_admitting_at"]),
        provider_route_ids=routes,
        expires_at=expires,
        policy_digest=policy_digest,
    )
    request = {
        "schedule_sha256": digest,
        "schedule_key": str(document["schedule_key"]),
        "activation_starts_at": document["activation"]["starts_at"],
        "activation_stops_admitting_at": document["activation"]["stops_admitting_at"],
        "provider_route_ids": routes,
        "provider_calls_per_utc_day_max": int(
            document["budgets"]["provider_calls_per_utc_day_max"]
        ),
        "provider_calls_lifetime_max": int(
            document["budgets"]["provider_calls_lifetime_max"]
        ),
        "modeled_provider_credits_per_utc_day_max": int(
            document["budgets"]["modeled_provider_credits_per_utc_day_max"]
        ),
        "minimum_expiry_at": expires,
        "cash_usd_max": "0",
        "retry": False,
        "fallback": False,
        "exact_owner_phrase": phrase,
        "authority_status": "PROPOSED_NOT_AUTHORITY",
        "policy_digest": policy_digest,
    }
    if predecessor_schedule_sha256:
        request["predecessor_schedule_sha256"] = predecessor_schedule_sha256
    if successor_schedule_sha256:
        request["successor_schedule_sha256"] = successor_schedule_sha256
    if cutover_at:
        request["cutover_at"] = cutover_at
    return request


def prepare_schedule_authority(
    *,
    root: Path,
    data_root: Path,
    store: ObservationScheduleStore,
    document: Mapping[str, Any],
    now: datetime,
    producer_git_sha: str,
    predecessor_schedule_sha256: str | None = None,
) -> dict[str, Any]:
    """Register the compiled schedule and return a PROPOSED_NOT_AUTHORITY packet."""

    registered = register_schedule(
        root=root,
        data_root=data_root,
        store=store,
        document=document,
        now=now,
        producer_git_sha=producer_git_sha,
    )
    if registered.get("schedule_sha256") is None:
        return {
            "terminal": registered.get("terminal") or "BLOCKED_AUTHORITY",
            "operational_registered": False,
            "authority_receipt_exists": False,
            "authority_status": "PROPOSED_NOT_AUTHORITY",
            "provider_calls": 0,
            "credential_reads": 0,
            "authority_request": None,
        }
    canonical = store.get_registered_schedule(str(registered["schedule_sha256"]))
    if canonical is None:
        raise ObservationLifecycleError("SCHEDULE_NOT_PERSISTED")
    successor = None
    cutover = None
    if predecessor_schedule_sha256:
        successor = str(registered["schedule_sha256"])
        cutover = str(canonical["document"]["activation"]["starts_at"])
    request = build_authority_request(
        root=root,
        document=canonical["document"],
        predecessor_schedule_sha256=predecessor_schedule_sha256,
        successor_schedule_sha256=successor,
        cutover_at=cutover,
    )
    request["activation_id"] = "ACT-" + str(registered["schedule_sha256"])[:16].upper()
    if predecessor_schedule_sha256:
        predecessor_activation_id = _unique_live_activation_id(
            store, predecessor_schedule_sha256
        )
        if predecessor_activation_id is not None:
            request["predecessor_activation_id"] = predecessor_activation_id
    return {
        "terminal": registered["terminal"],
        "operational_registered": True,
        "authority_receipt_exists": False,
        "authority_status": "PROPOSED_NOT_AUTHORITY",
        "schedule_sha256": registered["schedule_sha256"],
        "schedule_key": registered["schedule_key"],
        "provider_calls": 0,
        "credential_reads": 0,
        "authority_request": request,
        "exact_owner_phrase": request["exact_owner_phrase"],
    }


def _unique_live_activation_id(
    store: ObservationScheduleStore, schedule_sha256: str
) -> str | None:
    rows = [
        row
        for row in store.list_activations()
        if str(row.get("schedule_sha256") or "") == schedule_sha256
        and str(row.get("state") or "") in {"ACTIVE", "DRAINING"}
    ]
    if len(rows) != 1:
        return None
    activation_id = str(rows[0].get("activation_id") or "")
    return activation_id or None


def drain_expired_admission(
    *,
    data_root: Path,
    store: ObservationScheduleStore,
    schedule_sha256: str,
    activation_id: str,
    now: datetime,
    producer_git_sha: str,
) -> dict[str, Any] | None:
    """ACTIVE -> DRAINING when the authorized admission window has closed."""

    existing = store.get_activation(schedule_sha256, activation_id)
    if existing is None:
        return None
    if existing["state"] != "ACTIVE":
        return {
            "terminal": "NOT_ACTIVE",
            "state": existing["state"],
            "activation_id": activation_id,
            "schedule_sha256": schedule_sha256,
        }
    stops = parse_utc(str(existing["stops_admitting_at"]))
    if now < stops:
        return {
            "terminal": "ADMISSION_OPEN",
            "state": "ACTIVE",
            "activation_id": activation_id,
            "schedule_sha256": schedule_sha256,
        }
    rollover_before_cutover = any(
        str(item["predecessor_schedule_sha256"]) == schedule_sha256
        and str(item["predecessor_activation_id"]) == activation_id
        and now < parse_utc(str(item["cutover_at"]))
        for item in store.list_rollovers()
    )
    if rollover_before_cutover:
        return {
            "terminal": "ROLLOVER_CUTOVER_PENDING",
            "state": "ACTIVE",
            "activation_id": activation_id,
            "schedule_sha256": schedule_sha256,
        }
    transition = store.transition_activation(
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        new_state="DRAINING",
        authority_receipt_sha256=existing.get("authority_receipt_sha256"),
        effective_at=render_utc(now),
        payload={"admission_window_closed": True},
        clock=now,
    )
    event = _research_event(
        record_id=str(transition["event_id"]),
        record_kind=RecordKind.OBSERVATION_SCHEDULE_STATE,
        entity_id=schedule_sha256,
        payload={
            "state_event_id": transition["event_id"],
            "activation_id": activation_id,
            "state": "DRAINING",
            "schedule_sha256": schedule_sha256,
            "prior_state": transition["prior_state"],
            "transition_sequence": transition["transition_sequence"],
            "authority_receipt_sha256": existing.get("authority_receipt_sha256"),
            "admission_window_closed": True,
        },
        now=now,
        producer_git_sha=producer_git_sha,
        run_id=activation_id,
        transaction_id=f"RESEARCH-TXN-{transition['event_id'].upper()}",
    )
    _append_or_replay(data_root, event)
    return {
        "terminal": "DRAIN_REPLAY" if transition.get("replayed") else "DRAINED",
        "state": "DRAINING",
        "activation_id": activation_id,
        "schedule_sha256": schedule_sha256,
        "transition_event_id": transition["event_id"],
    }


def materialize_pending_observation_snapshots(
    *,
    data_root: Path,
    store: ObservationScheduleStore,
    schedule_sha256: str,
    activation_id: str,
    now: datetime,
    producer_git_sha: str,
) -> list[dict[str, Any]]:
    """Materialize the exact snapshot needed by named pending consumers."""

    from solana_alpha_lab.factory.observation_panel_coverage import (
        load_coverage_from_rdp,
        pending_consumer_satisfiable,
        required_point_ids,
        snapshot_proves_required_points,
    )

    outcomes: list[dict[str, Any]] = []
    coverage = load_coverage_from_rdp(data_root)
    due_rows = store.due_in_states(
        tuple(
            {
                "OBSERVED",
                "MISSING_TYPED",
                "DISAPPEARED",
                "CENSORED",
                "CENSORED_LATE",
                "X_POPULATION_INELIGIBLE",
                "DEPENDENCY_MISSING",
                "PENDING",
                "DUE",
                "CLAIMED",
                "IN_FLIGHT_CALL_INDETERMINATE",
                "BLOCKED_BUDGET",
            }
        )
    )
    publication_complete = not has_open_publication_jobs(
        data_root=data_root,
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
    )
    for pending in load_pending_observation_bindings(data_root):
        if pending.get("state") != "WAITING_FOR_PANEL":
            continue
        covering = str(pending.get("covering_schedule_sha256") or "")
        if covering != schedule_sha256:
            continue
        required = required_point_ids(pending)
        proving_snapshot = None
        for item in coverage.snapshots.values():
            schedule = item.get("schedule")
            if not isinstance(schedule, Mapping):
                continue
            digest = str(schedule.get("schedule_sha256") or "")
            if digest != schedule_sha256:
                continue
            snap_cutoff = item.get("availability_cutoff")
            if isinstance(snap_cutoff, datetime):
                evaluation = now.astimezone(UTC) if now.tzinfo is not None else now
                if snap_cutoff < evaluation:
                    continue
            if snapshot_proves_required_points(
                data_root=data_root,
                snapshot=item,
                covering_schedule_sha256=covering,
                required_points=required,
                due_rows=due_rows,
                now=now,
            ):
                proving_snapshot = item
                break
        if proving_snapshot is None:
            if not pending_consumer_satisfiable(
                data_root=data_root,
                covering_schedule_sha256=covering,
                required_points=required,
                due_rows=due_rows,
                snapshot=None,
                publication_complete=publication_complete,
                now=now,
            ):
                continue
            try:
                snapshot = snapshot_schedule(
                    data_root=data_root,
                    store=store,
                    schedule_sha256=schedule_sha256,
                    activation_id=activation_id,
                    now=now,
                    producer_git_sha=producer_git_sha,
                    hypothesis_version_id=pending.get("hypothesis_version_id")
                    if isinstance(pending.get("hypothesis_version_id"), str)
                    else None,
                )
            except ObservationLifecycleError as exc:
                if str(exc) == "SNAPSHOT_NO_PUBLISHED_PANEL":
                    continue
                raise
            proving_snapshot = {
                "snapshot_sha256": snapshot["snapshot_sha256"],
                "dataset_manifest_ids": snapshot.get("dataset_manifest_ids") or [],
                "schedule": {"schedule_sha256": schedule_sha256},
            }
            if not snapshot_proves_required_points(
                data_root=data_root,
                snapshot=proving_snapshot,
                covering_schedule_sha256=covering,
                required_points=required,
                due_rows=due_rows,
                now=now,
            ):
                continue
        else:
            if not pending_consumer_satisfiable(
                data_root=data_root,
                covering_schedule_sha256=covering,
                required_points=required,
                due_rows=due_rows,
                snapshot=proving_snapshot,
                publication_complete=publication_complete,
                now=now,
            ):
                continue
            snapshot = {
                "terminal": "SNAPSHOT_REPLAY",
                "snapshot_sha256": proving_snapshot["snapshot_sha256"],
            }
        satisfied = satisfy_pending_observation_binding(
            data_root=data_root,
            pending_binding_sha256=str(pending["pending_binding_sha256"]),
            snapshot_sha256=str(snapshot["snapshot_sha256"]),
            now=now,
            producer_git_sha=producer_git_sha,
            run_id=activation_id,
        )
        outcomes.append({**snapshot, **satisfied})
    return outcomes


def authorize_schedule(
    *,
    root: Path,
    data_root: Path,
    store: ObservationScheduleStore,
    schedule_sha256: str,
    phrase: str,
    now: datetime,
    producer_git_sha: str,
    expires_at: str | None = None,
) -> dict[str, Any]:
    registered = store.get_registered_schedule(schedule_sha256)
    if registered is None:
        raise ObservationLifecycleError("SCHEDULE_NOT_REGISTERED")
    document = registered["document"]
    primitive_ids, routes = _used_provider_route_ids(root, document)
    minimum_expiry = _minimum_expiry(document)
    expires = expires_at or render_utc(
        minimum_expiry
    )
    try:
        if parse_utc(expires) < minimum_expiry:
            raise ObservationLifecycleError("BLOCKED_AUTHORITY")
    except ValueError as exc:
        raise ObservationLifecycleError("BLOCKED_AUTHORITY") from exc
    policy = _authority_policy(
        root=root,
        document=document,
        schedule_key=str(document["schedule_key"]),
        expires_at=expires,
    )
    policy_digest = canonical_sha256(policy)
    expected_phrase = expected_authority_phrase(
        schedule_sha256=schedule_sha256,
        schedule_key=str(document["schedule_key"]),
        activation_starts_at=str(document["activation"]["starts_at"]),
        activation_stops_admitting_at=str(document["activation"]["stops_admitting_at"]),
        provider_route_ids=routes,
        expires_at=expires,
        policy_digest=policy_digest,
    )
    if phrase != expected_phrase:
        raise ObservationLifecycleError("BLOCKED_AUTHORITY")
    phrase_digest = hashlib.sha256(phrase.encode("utf-8")).hexdigest()
    receipt = {
        "schema": "smial.observation-schedule-authority",
        "schema_version": "1.0",
        "authority_id": f"AUTHZ-OBS-{schedule_sha256[:12].upper()}",
        "schedule_sha256": schedule_sha256,
        "schedule_key": document["schedule_key"],
        "activation_starts_at": document["activation"]["starts_at"],
        "activation_stops_admitting_at": document["activation"]["stops_admitting_at"],
        "used_primitive_ids": primitive_ids,
        "provider_route_ids": routes,
        "provider_calls_per_utc_day_max": int(document["budgets"]["provider_calls_per_utc_day_max"]),
        "provider_calls_lifetime_max": int(document["budgets"]["provider_calls_lifetime_max"]),
        "modeled_provider_credits_per_utc_day_max": int(
            document["budgets"]["modeled_provider_credits_per_utc_day_max"]
        ),
        "cash_usd_max": "0",
        "retry": False,
        "fallback": False,
        "build_execute_wallet_signer_transaction": False,
        "expires_at": expires,
        "phrase_sha256": phrase_digest,
        "minimum_expiry_at": render_utc(minimum_expiry),
        "policy_digest": policy_digest,
        "approved_capability_ids": [APPROVED_CAPABILITY],
        "allowed_credential_class": "LOCAL_ENV_CREDENTIAL",
    }
    receipt["receipt_sha256"] = canonical_sha256(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )
    schema = json.loads((root / AUTHORITY_SCHEMA_RELATIVE).read_text(encoding="utf-8"))
    jsonschema.validate(receipt, schema)
    try:
        outcome = store.persist_authority(receipt, clock=now)
    except ObservationScheduleStoreError as exc:
        raise ObservationLifecycleError(str(exc)) from exc
    event = _research_event(
        record_id=f"OBS-AUTHZ-{receipt['receipt_sha256'][:16].upper()}",
        record_kind=RecordKind.OBSERVATION_SCHEDULE_AUTHORITY,
        entity_id=schedule_sha256,
        payload=receipt,
        now=now,
        producer_git_sha=producer_git_sha,
        run_id=None,
        transaction_id=f"RESEARCH-TXN-OBS-AUTHZ-{receipt['receipt_sha256'][:12].upper()}",
    )
    _append_or_replay(data_root, event)
    terminal = "AUTHORIZE_REPLAY" if outcome == "AUTHORIZE_REPLAY" else "AUTHORIZED"
    return {
        "terminal": terminal,
        "schedule_sha256": schedule_sha256,
        "receipt_sha256": receipt["receipt_sha256"],
        "authority_id": receipt["authority_id"],
        "expires_at": expires,
    }


def _require_live_authority(
    store: ObservationScheduleStore,
    *,
    root: Path,
    document: Mapping[str, Any],
    schedule_sha256: str,
    now: datetime,
    receipt_sha256: str | None = None,
) -> dict[str, Any]:
    if compute_schedule_sha256(document) != schedule_sha256:
        raise ObservationLifecycleError("AUTHORITY_MISMATCH")
    receipt = (
        store.get_authority(receipt_sha256)
        if receipt_sha256 is not None
        else store.latest_authority_for_schedule(schedule_sha256)
    )
    if receipt is None:
        raise ObservationLifecycleError("AUTHORITY_MISSING")
    if (
        receipt_sha256 is not None
        and str(receipt.get("receipt_sha256")) != str(receipt_sha256)
    ):
        raise ObservationLifecycleError("AUTHORITY_MISMATCH")
    if str(receipt.get("schedule_sha256")) != schedule_sha256:
        raise ObservationLifecycleError("AUTHORITY_MISMATCH")
    if str(receipt.get("authority_id")) != (
        f"AUTHZ-OBS-{schedule_sha256[:12].upper()}"
    ):
        raise ObservationLifecycleError("AUTHORITY_MISMATCH")
    if str(receipt.get("schedule_key")) != str(document["schedule_key"]):
        raise ObservationLifecycleError("AUTHORITY_MISMATCH")
    if (
        str(receipt.get("activation_starts_at"))
        != str(document["activation"]["starts_at"])
        or str(receipt.get("activation_stops_admitting_at"))
        != str(document["activation"]["stops_admitting_at"])
    ):
        raise ObservationLifecycleError("AUTHORITY_MISMATCH")
    if parse_utc(receipt["expires_at"]) <= now:
        raise ObservationLifecycleError("AUTHORITY_EXPIRED")
    stored = store.get_authority(str(receipt["receipt_sha256"]))
    if stored != receipt:
        raise ObservationLifecycleError("AUTHORITY_MISMATCH")
    receipt_digest = canonical_sha256(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )
    if receipt_digest != str(receipt.get("receipt_sha256")):
        raise ObservationLifecycleError("AUTHORITY_MISMATCH")
    try:
        schema = json.loads((root / AUTHORITY_SCHEMA_RELATIVE).read_text(encoding="utf-8"))
        jsonschema.validate(receipt, schema)
    except (OSError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
        raise ObservationLifecycleError("AUTHORITY_MISMATCH") from exc
    expected_policy = _authority_policy(
        root=root,
        document=document,
        schedule_key=str(document["schedule_key"]),
        expires_at=str(receipt["expires_at"]),
    )
    expected_policy_digest = canonical_sha256(expected_policy)
    if str(receipt.get("policy_digest")) != expected_policy_digest:
        raise ObservationLifecycleError("AUTHORITY_MISMATCH")
    for key in (
        "used_primitive_ids",
        "provider_route_ids",
        "provider_calls_per_utc_day_max",
        "provider_calls_lifetime_max",
        "modeled_provider_credits_per_utc_day_max",
        "cash_usd_max",
        "retry",
        "fallback",
        "build_execute_wallet_signer_transaction",
        "approved_capability_ids",
        "allowed_credential_class",
    ):
        if receipt.get(key) != expected_policy.get(key):
            raise ObservationLifecycleError("AUTHORITY_MISMATCH")
    expected_phrase = expected_authority_phrase(
        schedule_sha256=schedule_sha256,
        schedule_key=str(document["schedule_key"]),
        activation_starts_at=str(document["activation"]["starts_at"]),
        activation_stops_admitting_at=str(document["activation"]["stops_admitting_at"]),
        provider_route_ids=expected_policy["provider_route_ids"],
        expires_at=str(receipt["expires_at"]),
        policy_digest=expected_policy_digest,
    )
    if hashlib.sha256(expected_phrase.encode("utf-8")).hexdigest() != str(
        receipt.get("phrase_sha256")
    ):
        raise ObservationLifecycleError("AUTHORITY_MISMATCH")
    required_minimum_expiry = _minimum_expiry(document)
    if str(receipt.get("minimum_expiry_at")) != render_utc(required_minimum_expiry):
        raise ObservationLifecycleError("BLOCKED_AUTHORITY")
    if parse_utc(str(receipt["expires_at"])) < required_minimum_expiry:
        raise ObservationLifecycleError("BLOCKED_AUTHORITY")
    return receipt


def _cohort_family_key(document: Mapping[str, Any]) -> str:
    """Identity of the scientific cohort, independent of Y horizon / schedule_key."""
    population = document["population"]
    return canonical_sha256(
        {
            "seed": document["sampling"]["seed"],
            "source_poll": document["source_poll"],
            "source_predicates": population["source_predicates"],
            "x_eligibility_predicates": population["x_eligibility_predicates"],
            "x_point": document["x_point"],
        }
    )


def _require_cohort_cutover_or_unique(
    store: ObservationScheduleStore,
    *,
    document: Mapping[str, Any],
    schedule_sha256: str,
    activation_id: str,
) -> None:
    family = _cohort_family_key(document)
    for row in store.list_activations():
        if str(row["state"]) not in {"ACTIVE", "DRAINING"}:
            continue
        if str(row["schedule_sha256"]) == schedule_sha256:
            continue
        other = store.get_registered_schedule(str(row["schedule_sha256"]))
        if other is None:
            continue
        if _cohort_family_key(other["document"]) != family:
            continue
        allowed = any(
            str(item["successor_schedule_sha256"]) == schedule_sha256
            and str(item["successor_activation_id"]) == activation_id
            and str(item["predecessor_schedule_sha256"]) == str(row["schedule_sha256"])
            and str(item["predecessor_activation_id"]) == str(row["activation_id"])
            for item in store.list_rollovers()
        )
        if not allowed:
            raise ObservationLifecycleError("COHORT_CUTOVER_REQUIRED")


def activate_schedule(
    *,
    root: Path | None = None,
    data_root: Path,
    store: ObservationScheduleStore,
    schedule_sha256: str,
    activation_id: str,
    now: datetime,
    producer_git_sha: str,
) -> dict[str, Any]:
    registered = store.get_registered_schedule(schedule_sha256)
    if registered is None:
        raise ObservationLifecycleError("SCHEDULE_NOT_REGISTERED")
    document = registered["document"]
    existing = store.get_activation(schedule_sha256, activation_id)
    authority_root = root or Path(__file__).resolve().parents[3]
    receipt = _require_live_authority(
        store,
        root=authority_root,
        document=document,
        schedule_sha256=schedule_sha256,
        now=now,
        receipt_sha256=(
            str(existing.get("authority_receipt_sha256") or "")
            if existing is not None
            else None
        ),
    )
    if existing is None:
        siblings = [
            row
            for row in store.list_activations()
            if row["schedule_sha256"] == schedule_sha256
        ]
        if siblings:
            raise ObservationLifecycleError("ACTIVATION_ALREADY_LIVE")
        _require_cohort_cutover_or_unique(
            store,
            document=document,
            schedule_sha256=schedule_sha256,
            activation_id=activation_id,
        )
    if existing is not None:
        if str(existing.get("authority_receipt_sha256")) != receipt["receipt_sha256"]:
            raise ObservationLifecycleError("ACTIVATION_IDENTITY_CONFLICT")
        if existing["state"] != "ACTIVE":
            return {
                "terminal": "ACTIVATE_STILL_PAUSED"
                if existing["state"] == "PAUSED_OPERATOR"
                else "ACTIVATE_NOT_ACTIVE",
                "activation_id": activation_id,
                "schedule_sha256": schedule_sha256,
                "state": existing["state"],
                "next_action": "RESUME"
                if existing["state"] == "PAUSED_OPERATOR"
                else "STATUS",
            }
        return {
            "terminal": "ACTIVATE_REPLAY",
            "activation_id": activation_id,
            "schedule_sha256": schedule_sha256,
            "state": existing["state"],
            "transition_event_id": existing.get("last_transition_event_id"),
        }
    transition = store.transition_activation(
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        new_state="ACTIVE",
        authority_receipt_sha256=receipt["receipt_sha256"],
        effective_at=render_utc(now),
        starts_at=document["activation"]["starts_at"],
        stops_admitting_at=document["activation"]["stops_admitting_at"],
        schedule_key=str(document["schedule_key"]),
        payload={"receipt_sha256": receipt["receipt_sha256"]},
        clock=now,
    )
    event = _research_event(
        record_id=str(transition["event_id"]),
        record_kind=RecordKind.OBSERVATION_SCHEDULE_STATE,
        entity_id=schedule_sha256,
        payload={
            "state_event_id": transition["event_id"],
            "activation_id": activation_id,
            "state": "ACTIVE",
            "schedule_sha256": schedule_sha256,
            "prior_state": transition["prior_state"],
            "transition_sequence": transition["transition_sequence"],
            "authority_receipt_sha256": receipt["receipt_sha256"],
        },
        now=now,
        producer_git_sha=producer_git_sha,
        run_id=activation_id,
        transaction_id=f"RESEARCH-TXN-{transition['event_id'].upper()}",
    )
    _append_or_replay(data_root, event)
    persisted = store.get_activation(schedule_sha256, activation_id)
    if persisted is None or persisted["state"] != "ACTIVE":
        raise ObservationLifecycleError("ACTIVATION_NOT_PERSISTED")
    return {
        "terminal": "ACTIVATED",
        "activation_id": activation_id,
        "schedule_sha256": schedule_sha256,
        "state": "ACTIVE",
        "receipt_sha256": receipt["receipt_sha256"],
    }


def pause_schedule(
    *,
    data_root: Path,
    store: ObservationScheduleStore,
    schedule_sha256: str,
    activation_id: str,
    now: datetime,
    producer_git_sha: str,
) -> dict[str, Any]:
    existing = store.get_activation(schedule_sha256, activation_id)
    if existing is None:
        raise ObservationLifecycleError("ACTIVATION_MISSING")
    transition = store.transition_activation(
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        new_state="PAUSED_OPERATOR",
        authority_receipt_sha256=existing.get("authority_receipt_sha256"),
        effective_at=render_utc(now),
        payload={"paused": True},
        clock=now,
    )
    event = _research_event(
        record_id=str(transition["event_id"]),
        record_kind=RecordKind.OBSERVATION_SCHEDULE_STATE,
        entity_id=schedule_sha256,
        payload={
            "state_event_id": transition["event_id"],
            "activation_id": activation_id,
            "state": "PAUSED_OPERATOR",
            "schedule_sha256": schedule_sha256,
            "prior_state": transition["prior_state"],
            "transition_sequence": transition["transition_sequence"],
            "authority_receipt_sha256": existing.get("authority_receipt_sha256"),
        },
        now=now,
        producer_git_sha=producer_git_sha,
        run_id=activation_id,
        transaction_id=f"RESEARCH-TXN-{transition['event_id'].upper()}",
    )
    _append_or_replay(data_root, event)
    paused = store.get_activation(schedule_sha256, activation_id)
    if paused is None or paused["state"] != "PAUSED_OPERATOR":
        raise ObservationLifecycleError("PAUSE_NOT_PERSISTED")
    return {
        "terminal": "PAUSE_REPLAY" if transition.get("replayed") else "PAUSED",
        "activation_id": activation_id,
        "schedule_sha256": schedule_sha256,
        "state": "PAUSED_OPERATOR",
        "transition_event_id": transition["event_id"],
    }


def _activation_must_not_resume(activation: Mapping[str, Any]) -> bool:
    payload = dict(activation.get("payload") or {})
    if payload.get("must_not_resume") is True:
        return True
    if str(payload.get("abort_reason") or "").strip():
        return True
    return False


def abort_schedule(
    *,
    data_root: Path,
    store: ObservationScheduleStore,
    schedule_sha256: str,
    activation_id: str,
    reason: str,
    now: datetime,
    producer_git_sha: str,
) -> dict[str, Any]:
    existing = store.get_activation(schedule_sha256, activation_id)
    if existing is None:
        raise ObservationLifecycleError("ACTIVATION_MISSING")
    if existing["state"] == "ABORTED_SAFETY":
        return {
            "terminal": "ABORT_REPLAY",
            "activation_id": activation_id,
            "schedule_sha256": schedule_sha256,
            "state": "ABORTED_SAFETY",
            "abort_reason": dict(existing.get("payload") or {}).get("abort_reason"),
        }
    if existing["state"] not in {"PAUSED_OPERATOR", "ACTIVE", "DRAINING"}:
        raise ObservationLifecycleError("ABORT_NOT_ALLOWED")
    reason_text = str(reason or "").strip()
    if not reason_text:
        raise ObservationLifecycleError("ABORT_REASON_REQUIRED")
    transition = store.transition_activation(
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        new_state="ABORTED_SAFETY",
        authority_receipt_sha256=existing.get("authority_receipt_sha256"),
        effective_at=render_utc(now),
        payload={
            "abort_reason": reason_text,
            "must_not_resume": True,
            "aborted_from": existing["state"],
        },
        clock=now,
    )
    event = _research_event(
        record_id=str(transition["event_id"]),
        record_kind=RecordKind.OBSERVATION_SCHEDULE_STATE,
        entity_id=schedule_sha256,
        payload={
            "state_event_id": transition["event_id"],
            "activation_id": activation_id,
            "state": "ABORTED_SAFETY",
            "schedule_sha256": schedule_sha256,
            "prior_state": transition["prior_state"],
            "abort_reason": reason_text,
            "must_not_resume": True,
        },
        now=now,
        producer_git_sha=producer_git_sha,
        run_id=activation_id,
        transaction_id=f"RESEARCH-TXN-{transition['event_id'].upper()}",
    )
    _append_or_replay(data_root, event)
    aborted = store.get_activation(schedule_sha256, activation_id)
    if aborted is None or aborted["state"] != "ABORTED_SAFETY":
        raise ObservationLifecycleError("ABORT_NOT_PERSISTED")
    return {
        "terminal": "ABORT_REPLAY" if transition.get("replayed") else "ABORTED",
        "activation_id": activation_id,
        "schedule_sha256": schedule_sha256,
        "state": "ABORTED_SAFETY",
        "abort_reason": reason_text,
        "transition_event_id": transition["event_id"],
    }


def resume_schedule(
    *,
    data_root: Path,
    store: ObservationScheduleStore,
    schedule_sha256: str,
    activation_id: str,
    now: datetime,
    producer_git_sha: str,
) -> dict[str, Any]:
    existing = store.get_activation(schedule_sha256, activation_id)
    if existing is None:
        raise ObservationLifecycleError("ACTIVATION_MISSING")
    if existing["state"] == "ACTIVE":
        return {
            "terminal": "RESUME_REPLAY",
            "activation_id": activation_id,
            "schedule_sha256": schedule_sha256,
            "state": "ACTIVE",
        }
    if existing["state"] != "PAUSED_OPERATOR":
        raise ObservationLifecycleError("RESUME_NOT_PAUSED")
    if _activation_must_not_resume(existing):
        raise ObservationLifecycleError("MUST_NOT_RESUME")
    registered = store.get_registered_schedule(schedule_sha256)
    if registered is None:
        raise ObservationLifecycleError("SCHEDULE_NOT_REGISTERED")
    receipt = _require_live_authority(
        store,
        root=Path(__file__).resolve().parents[3],
        document=registered["document"],
        schedule_sha256=schedule_sha256,
        now=now,
        receipt_sha256=str(existing["authority_receipt_sha256"]),
    )
    transition = store.transition_activation(
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        new_state="ACTIVE",
        authority_receipt_sha256=receipt["receipt_sha256"],
        effective_at=render_utc(now),
        payload={"resumed": True},
        clock=now,
    )
    event = _research_event(
        record_id=str(transition["event_id"]),
        record_kind=RecordKind.OBSERVATION_SCHEDULE_STATE,
        entity_id=schedule_sha256,
        payload={
            "state_event_id": transition["event_id"],
            "activation_id": activation_id,
            "state": "ACTIVE",
            "schedule_sha256": schedule_sha256,
            "prior_state": transition["prior_state"],
            "transition_sequence": transition["transition_sequence"],
            "authority_receipt_sha256": receipt["receipt_sha256"],
        },
        now=now,
        producer_git_sha=producer_git_sha,
        run_id=activation_id,
        transaction_id=f"RESEARCH-TXN-{transition['event_id'].upper()}",
    )
    _append_or_replay(data_root, event)
    resumed = store.get_activation(schedule_sha256, activation_id)
    if resumed is None or resumed["state"] != "ACTIVE":
        raise ObservationLifecycleError("RESUME_NOT_PERSISTED")
    return {
        "terminal": "RESUME_REPLAY" if transition.get("replayed") else "RESUMED",
        "activation_id": activation_id,
        "schedule_sha256": schedule_sha256,
        "state": "ACTIVE",
        "receipt_sha256": receipt["receipt_sha256"],
        "transition_event_id": transition["event_id"],
    }


def complete_draining_schedule(
    *,
    data_root: Path,
    store: ObservationScheduleStore,
    schedule_sha256: str,
    activation_id: str,
    now: datetime,
    producer_git_sha: str,
) -> dict[str, Any]:
    """Complete a drained activation only after every obligation is resolved."""
    existing = store.get_activation(schedule_sha256, activation_id)
    if existing is None:
        raise ObservationLifecycleError("ACTIVATION_MISSING")
    if existing["state"] == "COMPLETE":
        return {
            "terminal": "COMPLETE_REPLAY",
            "activation_id": activation_id,
            "schedule_sha256": schedule_sha256,
            "state": "COMPLETE",
        }
    if existing["state"] != "DRAINING":
        raise ObservationLifecycleError("ACTIVATION_NOT_DRAINING")
    if has_open_publication_jobs(
        data_root=data_root,
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
    ):
        return {
            "terminal": "DRAINING_PENDING",
            "activation_id": activation_id,
            "schedule_sha256": schedule_sha256,
            "state": "DRAINING",
        }
    open_states = {"PENDING", "DUE", "CLAIMED"}
    unresolved_states = {"IN_FLIGHT_CALL_INDETERMINATE", "BLOCKED_BUDGET"}
    due_rows = store.due_in_states(tuple(open_states | unresolved_states))
    if any(
        str(row["schedule_sha256"]) == schedule_sha256
        and str(row["activation_id"]) == activation_id
        and str(row["state"]) in open_states | unresolved_states
        for row in due_rows
    ):
        return {
            "terminal": "DRAINING_PENDING",
            "activation_id": activation_id,
            "schedule_sha256": schedule_sha256,
            "state": "DRAINING",
        }
    transition = store.transition_activation(
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        new_state="COMPLETE",
        authority_receipt_sha256=existing.get("authority_receipt_sha256"),
        effective_at=render_utc(now),
        payload={"drained": True},
        clock=now,
    )
    event = _research_event(
        record_id=str(transition["event_id"]),
        record_kind=RecordKind.OBSERVATION_SCHEDULE_STATE,
        entity_id=schedule_sha256,
        payload={
            "state_event_id": transition["event_id"],
            "activation_id": activation_id,
            "state": "COMPLETE",
            "schedule_sha256": schedule_sha256,
            "prior_state": transition["prior_state"],
            "transition_sequence": transition["transition_sequence"],
            "authority_receipt_sha256": existing.get("authority_receipt_sha256"),
        },
        now=now,
        producer_git_sha=producer_git_sha,
        run_id=activation_id,
        transaction_id=f"RESEARCH-TXN-{transition['event_id'].upper()}",
    )
    _append_or_replay(data_root, event)
    return {
        "terminal": "COMPLETE_REPLAY"
        if transition.get("replayed")
        else "COMPLETED",
        "activation_id": activation_id,
        "schedule_sha256": schedule_sha256,
        "state": "COMPLETE",
        "transition_event_id": transition["event_id"],
    }


def rollover_schedule(
    *,
    root: Path,
    data_root: Path,
    store: ObservationScheduleStore,
    predecessor_schedule_sha256: str,
    predecessor_activation_id: str,
    successor_schedule_sha256: str,
    successor_activation_id: str,
    cutover_at: str,
    now: datetime,
    producer_git_sha: str,
) -> dict[str, Any]:
    """Cut over future admission while preserving predecessor due work."""
    predecessor = store.get_activation(
        predecessor_schedule_sha256, predecessor_activation_id
    )
    successor_registered = store.get_registered_schedule(successor_schedule_sha256)
    predecessor_registered = store.get_registered_schedule(predecessor_schedule_sha256)
    if predecessor is None or predecessor_registered is None:
        raise ObservationLifecycleError("PREDECESSOR_ACTIVATION_MISSING")
    if successor_registered is None:
        raise ObservationLifecycleError("SUCCESSOR_NOT_REGISTERED")
    if (
        predecessor_schedule_sha256 == successor_schedule_sha256
        and predecessor_activation_id == successor_activation_id
    ):
        raise ObservationLifecycleError("ROLLOVER_IDENTITY_CONFLICT")
    if predecessor["state"] not in {"ACTIVE", "DRAINING"}:
        raise ObservationLifecycleError("PREDECESSOR_NOT_ACTIVE")
    cutover = parse_utc(cutover_at)
    cutover_text = render_utc(cutover)
    predecessor_document = predecessor_registered["document"]
    successor_document = successor_registered["document"]
    if not (
        parse_utc(predecessor_document["activation"]["starts_at"])
        <= cutover
        <= parse_utc(predecessor_document["activation"]["stops_admitting_at"])
    ):
        raise ObservationLifecycleError("ROLLOVER_CUTOVER_OUT_OF_RANGE")
    if not (
        parse_utc(successor_document["activation"]["starts_at"])
        <= cutover
        < parse_utc(successor_document["activation"]["stops_admitting_at"])
    ):
        raise ObservationLifecycleError("ROLLOVER_CUTOVER_OUT_OF_RANGE")
    matching_rollover: dict[str, Any] | None = None
    for existing_rollover in store.list_rollovers():
        same_predecessor = (
            str(existing_rollover["predecessor_schedule_sha256"])
            == predecessor_schedule_sha256
            and str(existing_rollover["predecessor_activation_id"])
            == predecessor_activation_id
        )
        same_successor = (
            str(existing_rollover["successor_schedule_sha256"])
            == successor_schedule_sha256
            and str(existing_rollover["successor_activation_id"])
            == successor_activation_id
        )
        if same_predecessor or same_successor:
            if (
                same_predecessor
                and same_successor
                and str(existing_rollover["cutover_at"]) == cutover_text
            ):
                matching_rollover = dict(existing_rollover)
                continue
            raise ObservationLifecycleError("ROLLOVER_IDENTITY_CONFLICT")
    if matching_rollover is not None and predecessor["state"] == "DRAINING":
        successor_existing = store.get_activation(
            successor_schedule_sha256, successor_activation_id
        )
        if (
            successor_existing is not None
            and successor_existing["state"] == "ACTIVE"
            and str(successor_existing.get("authority_receipt_sha256") or "")
            == str(matching_rollover["authority_receipt_sha256"])
        ):
            return {
                "terminal": "ROLLOVER_REPLAY",
                "rollover_id": matching_rollover["rollover_id"],
                "cutover_at": cutover_text,
                "predecessor_state": "DRAINING",
                "successor_state": "ACTIVE",
            }
    _require_live_authority(
        store,
        root=root,
        document=predecessor_document,
        schedule_sha256=predecessor_schedule_sha256,
        now=now,
        receipt_sha256=str(predecessor["authority_receipt_sha256"] or ""),
    )
    successor_existing = store.get_activation(
        successor_schedule_sha256, successor_activation_id
    )
    successor_receipt = _require_live_authority(
        store,
        root=root,
        document=successor_registered["document"],
        schedule_sha256=successor_schedule_sha256,
        now=now,
        receipt_sha256=(
            str(successor_existing.get("authority_receipt_sha256") or "")
            if successor_existing is not None
            else None
        ),
    )
    if (
        matching_rollover is not None
        and str(matching_rollover["authority_receipt_sha256"])
        != str(successor_receipt["receipt_sha256"])
    ):
        raise ObservationLifecycleError("ROLLOVER_IDENTITY_CONFLICT")
    rollover_id = store.persist_rollover(
        predecessor_schedule_sha256=predecessor_schedule_sha256,
        predecessor_activation_id=predecessor_activation_id,
        successor_schedule_sha256=successor_schedule_sha256,
        successor_activation_id=successor_activation_id,
        cutover_at=cutover_text,
        authority_receipt_sha256=successor_receipt["receipt_sha256"],
        clock=now,
    )
    predecessor_already_draining = predecessor["state"] == "DRAINING"
    predecessor_transition = None
    if not predecessor_already_draining:
        predecessor_transition = store.transition_activation(
            schedule_sha256=predecessor_schedule_sha256,
            activation_id=predecessor_activation_id,
            new_state="DRAINING",
            authority_receipt_sha256=predecessor.get("authority_receipt_sha256"),
            effective_at=cutover_text,
            payload={
                "cutover_at": cutover_text,
                "successor_schedule_sha256": successor_schedule_sha256,
            },
            clock=now,
        )
    successor_transition = store.transition_activation(
        schedule_sha256=successor_schedule_sha256,
        activation_id=successor_activation_id,
        new_state="ACTIVE",
        authority_receipt_sha256=successor_receipt["receipt_sha256"],
        effective_at=cutover_text,
        starts_at=successor_document["activation"]["starts_at"],
        stops_admitting_at=successor_document["activation"]["stops_admitting_at"],
        schedule_key=str(successor_document["schedule_key"]),
        payload={
            "cutover_at": cutover_text,
            "predecessor_schedule_sha256": predecessor_schedule_sha256,
        },
        clock=now,
    )
    transitions_to_write: list[tuple[dict[str, Any], str]] = [
        (successor_transition, successor_schedule_sha256),
    ]
    if predecessor_transition is not None:
        transitions_to_write.insert(
            0, (predecessor_transition, predecessor_schedule_sha256)
        )
    for transition, digest in transitions_to_write:
        event = _research_event(
            record_id=str(transition["event_id"]),
            record_kind=RecordKind.OBSERVATION_SCHEDULE_STATE,
            entity_id=digest,
            payload={
                "state_event_id": transition["event_id"],
                "activation_id": transition["activation_id"],
                "state": transition["state"],
                "prior_state": transition["prior_state"],
                "transition_sequence": transition["transition_sequence"],
                "schedule_sha256": digest,
                "cutover_at": cutover_text,
                "rollover_id": rollover_id,
                "authority_receipt_sha256": transition[
                    "authority_receipt_sha256"
                ],
            },
            now=now,
            producer_git_sha=producer_git_sha,
            run_id=transition["activation_id"],
            transaction_id=f"RESEARCH-TXN-{transition['event_id'].upper()}",
        )
        _append_or_replay(data_root, event)
    return {
        "terminal": "ROLLOVER_REPLAY"
        if (
            successor_transition.get("replayed")
            and (
                predecessor_already_draining
                or (
                    predecessor_transition is not None
                    and predecessor_transition.get("replayed")
                )
            )
        )
        else "ROLLOVER_COMMITTED",
        "rollover_id": rollover_id,
        "cutover_at": render_utc(cutover),
        "predecessor_state": "DRAINING",
        "successor_state": "ACTIVE",
    }


def status_schedule(
    store: ObservationScheduleStore,
    *,
    schedule_sha256: str | None,
    activation_id: str | None,
    now: datetime | None = None,
    deploy_git_sha: str | None = None,
) -> dict[str, Any]:
    activations = store.list_activations()
    if schedule_sha256 and activation_id:
        row = store.get_activation(schedule_sha256, activation_id)
        if row is None:
            raise ObservationLifecycleError("ACTIVATION_MISSING")
        activations = [row]
    from solana_alpha_lab.factory.collector_read_model import build_collector_read_model

    clock = now or datetime.now(UTC)
    collector = build_collector_read_model(
        store,
        now=clock,
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        deploy_git_sha=deploy_git_sha,
    )
    return {
        "terminal": "STATUS",
        "activations": [
            {
                "schedule_sha256": row["schedule_sha256"],
                "activation_id": row["activation_id"],
                "state": row["state"],
            }
            for row in activations
        ],
        "due_counts": store.due_counts(),
        "restore_marker_unresolved": store.restore_marker_unresolved(),
        "collector": collector,
    }


def snapshot_schedule(
    *,
    data_root: Path,
    store: ObservationScheduleStore,
    schedule_sha256: str,
    activation_id: str,
    now: datetime,
    producer_git_sha: str,
    hypothesis_version_id: str | None = None,
) -> dict[str, Any]:
    registered = store.get_registered_schedule(schedule_sha256)
    if registered is None:
        raise ObservationLifecycleError("SCHEDULE_NOT_REGISTERED")
    if store.get_activation(schedule_sha256, activation_id) is None:
        raise ObservationLifecycleError("ACTIVATION_MISSING")
    from solana_alpha_lab.factory.observation_panel_coverage import (
        derive_first_y_available_at,
    )

    research = ResearchStore(data_root)
    batch_ids: list[str] = []
    member_ids: set[str] = set()
    for record in research.iter_committed_records():
        payload = json.loads(record.payload_json)
        if payload.get("schedule_sha256") != schedule_sha256:
            continue
        kind = str(record.record_kind)
        if kind == "OBSERVATION_BATCH":
            batch_ids.append(str(payload["dataset_manifest_id"]))
        if kind == "OBSERVATION_MEMBER_BATCH":
            member_ids.add(str(payload["dataset_manifest_id"]))
    dataset_ids = [item for item in batch_ids if item in member_ids]
    if not dataset_ids:
        raise ObservationLifecycleError("SNAPSHOT_NO_PUBLISHED_PANEL")
    marker_dir = data_root / "datasets" / "manifests"
    fingerprints: list[str] = []
    kept: list[str] = []
    for dataset_id in dataset_ids:
        marker_path = marker_dir / f"{dataset_id}.published"
        if not marker_path.is_file():
            continue
        loaded = json.loads(marker_path.read_text(encoding="utf-8"))
        fingerprints.append(str(loaded["dataset_fingerprint"]))
        kept.append(dataset_id)
    if not kept:
        raise ObservationLifecycleError("SNAPSHOT_NO_PUBLISHED_PANEL")
    snapshot = build_panel_snapshot(
        schedule_sha256=schedule_sha256,
        availability_cutoff=now,
        dataset_manifest_ids=kept,
        dataset_fingerprints=fingerprints,
    )
    _first_y, proven = derive_first_y_available_at(data_root, schedule_sha256)
    evidence_role = None if proven else "EXPLORATORY_REUSE"
    persist_panel_snapshot_binding(
        data_root=data_root,
        schedule=registered["document"],
        snapshot=snapshot,
        now=now,
        producer_git_sha=producer_git_sha,
        evidence_role=evidence_role,
        hypothesis_version_id=hypothesis_version_id,
        run_id=activation_id,
    )
    return {
        "terminal": "SNAPSHOT",
        "snapshot_sha256": snapshot["snapshot_sha256"],
        "dataset_manifest_ids": kept,
        "first_y_proven": proven,
        "evidence_role": evidence_role,
    }


__all__ = [
    "ObservationLifecycleError",
    "activate_schedule",
    "abort_schedule",
    "authorize_schedule",
    "build_authority_request",
    "drain_expired_admission",
    "expected_authority_phrase",
    "materialize_pending_observation_snapshots",
    "observation_ops_store_path",
    "pause_schedule",
    "prepare_schedule_authority",
    "register_schedule",
    "require_production_producer_git_sha",
    "rollover_schedule",
    "resume_schedule",
    "snapshot_schedule",
    "status_schedule",
]
