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
    cohort_family_key as schedule_cohort_family_key,
    parse_utc,
    render_utc,
    schedule_sha256 as compute_schedule_sha256,
    validate_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule_compiler import compile_schedule_document
from solana_alpha_lab.factory.observation_schedule_store import (
    ObservationScheduleStore,
    ObservationScheduleStoreError,
    rollover_id_for,
    transition_event_id_for,
)
from solana_alpha_lab.factory.research_store import (
    RecordKind,
    ResearchEvent,
    ResearchStore,
    ResearchStoreError,
)

AUTHORITY_SCHEMA_RELATIVE = "catalog/schemas/observation_schedule_authority_v1.schema.json"
PRODUCER_CAPABILITY = "CAP-OBSERVATION-SCHEDULE-COMPILE-BIND-001"
APPROVED_CAPABILITY = "CAP-OBSERVATION-SCHEDULE-COMPILE-BIND-001"
OPS_STORE_FILENAME = "observation_schedule_state.sqlite"
FIXTURE_PRODUCER_GIT_SHA = "c" * 40


def observation_ops_store_path(data_root: Path) -> Path:
    return Path(data_root) / OPS_STORE_FILENAME


def _activation_window_matches_registered(
    row: Mapping[str, Any], document: Mapping[str, Any]
) -> bool:
    """Compare mutable activation window fields with its immutable registration."""

    try:
        registered = document["activation"]
        return (
            parse_utc(str(row["starts_at"]))
            == parse_utc(str(registered["starts_at"]))
            and parse_utc(str(row["stops_admitting_at"]))
            == parse_utc(str(registered["stops_admitting_at"]))
        )
    except (KeyError, TypeError, ValueError):
        return False


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


_OWNER_NEXT_ACTION_BY_LIFECYCLE_ERROR = {
    "ACTIVATION_WINDOW_MISMATCH": "RECONCILE_REGISTERED_ACTIVATION_WINDOW",
    "LATE_SUCCESSOR_RECOVERY_UNPROVEN": "REVALIDATE_DRAINING_RECOVERY_PROOF",
    "LATE_SUCCESSOR_BACKDATED": "REGISTER_AUTHORIZE_FORWARD_SUCCESSOR_FROM_LATE_RECOVERY",
    "ACTIVATION_BEFORE_STARTS_AT": "WAIT_UNTIL_SUCCESSOR_STARTS_AT",
    "COHORT_CUTOVER_REQUIRED": "REGISTER_AUTHORIZE_ROLLOVER_SUCCESSOR",
    "ROLLOVER_IMMUTABLE_PROOF_UNAVAILABLE": "INSPECT_IMMUTABLE_ROLLOVER_PROOF_AND_OPEN_RECOVERY_ATOM",
    "ROLLOVER_CUTOVER_IN_PAST": "REGISTER_AUTHORIZE_FORWARD_SUCCESSOR_FROM_LATE_RECOVERY",
}


def owner_next_action_for_lifecycle_error(error_code: str) -> str | None:
    """Map a fail-closed lifecycle denial to one owner-readable next action."""

    return _OWNER_NEXT_ACTION_BY_LIFECYCLE_ERROR.get(str(error_code or ""))


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
    effective_at: datetime | None = None,
) -> ResearchEvent:
    effective = effective_at or now
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
        effective_at=effective,
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
    registered = store.get_registered_schedule(schedule_sha256)
    if registered is None:
        raise ObservationLifecycleError("SCHEDULE_NOT_REGISTERED")
    if not _activation_window_matches_registered(existing, registered["document"]):
        raise ObservationLifecycleError("ACTIVATION_WINDOW_MISMATCH")
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
    pending_bindings = [
        pending
        for pending in load_pending_observation_bindings(data_root)
        if pending.get("state") == "WAITING_FOR_PANEL"
        and str(pending.get("covering_schedule_sha256") or "") == schedule_sha256
    ]
    if not pending_bindings:
        return outcomes
    coverage = load_coverage_from_rdp(data_root)

    def _due_prove(required_points: Sequence[str]) -> bool:
        return store.due_points_prove_required(
            schedule_sha256=schedule_sha256,
            activation_id=activation_id,
            required_points=required_points,
            now=now,
        )

    publication_complete = not has_open_publication_jobs(
        data_root=data_root,
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
    )
    for pending in pending_bindings:
        covering = schedule_sha256
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
                due_prove=_due_prove,
                now=now,
            ):
                proving_snapshot = item
                break
        if proving_snapshot is None:
            if not pending_consumer_satisfiable(
                data_root=data_root,
                covering_schedule_sha256=covering,
                required_points=required,
                due_prove=_due_prove,
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
                due_prove=_due_prove,
                now=now,
            ):
                continue
        else:
            if not pending_consumer_satisfiable(
                data_root=data_root,
                covering_schedule_sha256=covering,
                required_points=required,
                due_prove=_due_prove,
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


def require_live_authority(
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


# Preserve the existing internal import used by the scheduler while exposing
# the lifecycle authority check to other modules through a stable public name.
_require_live_authority = require_live_authority


def cohort_family_key(document: Mapping[str, Any]) -> str:
    """Identity of the scientific cohort, independent of Y horizon / schedule_key."""

    return schedule_cohort_family_key(document)


def _cohort_family_key(document: Mapping[str, Any]) -> str:
    """Compatibility alias; prefer cohort_family_key."""

    return cohort_family_key(document)


def _activation_is_non_admitting(
    row: Mapping[str, Any],
    *,
    now: datetime,
) -> bool:
    """True only when a peer is proven unable to admit new members.

    Minimum proof: DRAINING, now >= stops_admitting_at, and admission closed
    under canonical lifecycle semantics. A loose payload flag alone never
    overrides canonical time/state that still allows admission.
    """

    if str(row.get("state") or "") != "DRAINING":
        return False
    stops_raw = row.get("stops_admitting_at")
    if not isinstance(stops_raw, str) or not stops_raw:
        return False
    try:
        stops = parse_utc(stops_raw)
    except Exception:
        return False
    if now < stops:
        return False
    payload = dict(row.get("payload") or {})
    if payload.get("admission_window_closed") is not True:
        return False
    return True


def _draining_transition_evidence(
    data_root: Path,
    row: Mapping[str, Any],
    *,
    now: datetime,
) -> tuple[datetime, bool] | None:
    """Return the append-only DRAINING transition evidence.

    ``schedule_activations.payload_json`` is an operational projection and is
    not the authority for a late handover timestamp. The DRAINING transition
    is also emitted as an immutable ``ResearchEvent``. Its ``effective_at``
    and immutable closure flag are the lifecycle proof.
    Missing, malformed, or uncommitted evidence stays fail-closed.
    """

    schedule_sha256 = str(row.get("schedule_sha256") or "")
    activation_id = str(row.get("activation_id") or "")
    event_id = str(row.get("last_transition_event_id") or "")
    starts_raw = row.get("starts_at")
    stops_raw = row.get("stops_admitting_at")
    if not schedule_sha256 or not activation_id or not event_id:
        return None
    if not isinstance(starts_raw, str) or not starts_raw:
        return None
    if not isinstance(stops_raw, str) or not stops_raw:
        return None
    try:
        starts = parse_utc(starts_raw)
        stops = parse_utc(stops_raw)
    except Exception:
        return None
    try:
        records, _telemetry = ResearchStore(
            data_root, create_if_missing=False
        ).iter_lifecycle_records_bounded(
            schedule_sha256=schedule_sha256,
            activation_id=activation_id,
            # Rollover may drain before the predecessor admission window
            # closes.  The immutable activation start is the smallest
            # lifecycle boundary needed to recover that committed event.
            window_start=starts,
            # A committed rollover may be scheduled later in the predecessor
            # window.  Its immutable event is available now even when its
            # canonical effective_at is the future cutover.
            closure_cutoff=max(now, stops),
        )
    except ResearchStoreError:
        return None
    for record in records:
        if str(record.record_id) != event_id:
            continue
        if str(record.record_kind) != str(RecordKind.OBSERVATION_SCHEDULE_STATE):
            return None
        if (
            str(record.entity_id) != schedule_sha256
            or str(record.run_id or "") != activation_id
            or str(record.transaction_id)
            != f"RESEARCH-TXN-{event_id.upper()}"
            or str(record.producer_capability_id) != PRODUCER_CAPABILITY
            or record.created_at.astimezone(UTC) > now
            or record.first_reliable_available_at.astimezone(UTC) > now
        ):
            return None
        try:
            payload = json.loads(record.payload_json)
        except (TypeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, Mapping):
            return None
        try:
            transition_sequence = int(payload["transition_sequence"])
            expected_event_id = transition_event_id_for(
                schedule_sha256=schedule_sha256,
                activation_id=activation_id,
                prior_state=str(payload.get("prior_state") or ""),
                new_state=str(
                    payload.get("new_state") or payload.get("state") or ""
                ),
                transition_sequence=transition_sequence,
                effective_at=render_utc(record.effective_at.astimezone(UTC)),
                authority_receipt_sha256=str(
                    payload.get("authority_receipt_sha256") or ""
                ),
            )
        except (KeyError, TypeError, ValueError):
            return None
        if expected_event_id != event_id:
            return None
        if (
            str(payload.get("state_event_id") or "") != event_id
            or str(payload.get("schedule_sha256") or "") != schedule_sha256
            or str(payload.get("activation_id") or "") != activation_id
            or str(payload.get("state") or "") != "DRAINING"
            or str(payload.get("prior_state") or "") != "ACTIVE"
        ):
            return None
        admission_window_closed = payload.get("admission_window_closed")
        rollover_id = str(payload.get("rollover_id") or "")
        cutover_raw = str(payload.get("cutover_at") or "")
        predecessor_schedule = str(
            payload.get("predecessor_schedule_sha256") or ""
        )
        predecessor_activation = str(
            payload.get("predecessor_activation_id") or ""
        )
        successor_schedule = str(payload.get("successor_schedule_sha256") or "")
        successor_activation = str(payload.get("successor_activation_id") or "")
        rollover_authority = str(
            payload.get("rollover_authority_receipt_sha256") or ""
        )
        successor_starts_raw = str(payload.get("successor_starts_at") or "")
        successor_stops_raw = str(
            payload.get("successor_stops_admitting_at") or ""
        )
        effective = record.effective_at.astimezone(UTC)
        if admission_window_closed is True and effective > now:
            return None
        rollover_proof = False
        if all(
            (
                rollover_id,
                cutover_raw,
                predecessor_schedule == schedule_sha256,
                predecessor_activation == activation_id,
                successor_schedule,
                successor_activation,
                successor_schedule != schedule_sha256
                or successor_activation != activation_id,
                successor_starts_raw,
                successor_stops_raw,
                rollover_authority,
            )
        ):
            try:
                cutover = parse_utc(cutover_raw)
                successor_starts = parse_utc(successor_starts_raw)
                successor_stops = parse_utc(successor_stops_raw)
            except Exception:
                return None
            if (
                rollover_id
                != rollover_id_for(
                    predecessor_schedule_sha256=schedule_sha256,
                    predecessor_activation_id=activation_id,
                    successor_schedule_sha256=successor_schedule,
                    successor_activation_id=successor_activation,
                    cutover_at=render_utc(cutover),
                    authority_receipt_sha256=rollover_authority,
                )
                or str(payload.get("cutover_at") or "") != render_utc(cutover)
            ):
                return None
            rollover_proof = (
                effective == cutover
                and starts <= cutover <= stops
                and successor_starts <= cutover < successor_stops
            )
        if admission_window_closed is True:
            admission_closed = True
        elif rollover_proof:
            admission_closed = False
        else:
            return None
        if admission_closed and effective < stops:
            return None
        return effective, admission_closed
    return None


def _non_admitting_recovery_at(
    data_root: Path,
    row: Mapping[str, Any],
    *,
    now: datetime,
) -> datetime | None:
    """Return the append-only lifecycle timestamp that closed admission."""

    evidence = _draining_transition_evidence(data_root, row, now=now)
    if evidence is None or evidence[1] is not True:
        return None
    return evidence[0]


def rollover_research_event_proven(
    data_root: Path | None,
    *,
    item: Mapping[str, Any],
    predecessor_document: Mapping[str, Any],
    successor_document: Mapping[str, Any],
    now: datetime,
    predecessor_transition_event_id: str | None,
    successor_transition_event_id: str | None,
) -> bool:
    """Require the immutable state event behind a prepared rollover row."""

    if data_root is None:
        return False
    predecessor_schedule = str(item.get("predecessor_schedule_sha256") or "")
    predecessor_activation = str(item.get("predecessor_activation_id") or "")
    successor_schedule = str(item.get("successor_schedule_sha256") or "")
    successor_activation = str(item.get("successor_activation_id") or "")
    authority_receipt = str(item.get("authority_receipt_sha256") or "")
    rollover_id = str(item.get("rollover_id") or "")
    expected_predecessor_event_id = str(predecessor_transition_event_id or "")
    expected_successor_event_id = str(successor_transition_event_id or "")
    if not expected_predecessor_event_id or not expected_successor_event_id:
        return False
    try:
        predecessor_starts = parse_utc(
            str(predecessor_document["activation"]["starts_at"])
        )
        predecessor_stops = parse_utc(
            str(predecessor_document["activation"]["stops_admitting_at"])
        )
        successor_starts = parse_utc(
            str(successor_document["activation"]["starts_at"])
        )
        successor_stops = parse_utc(
            str(successor_document["activation"]["stops_admitting_at"])
        )
        cutover = parse_utc(str(item["cutover_at"]))
    except (KeyError, TypeError, ValueError):
        return False
    if str(item.get("cutover_at") or "") != render_utc(cutover):
        return False
    if (
        not predecessor_schedule
        or not predecessor_activation
        or not successor_schedule
        or not successor_activation
        or not authority_receipt
        or not rollover_id
        or (
            predecessor_schedule == successor_schedule
            and predecessor_activation == successor_activation
        )
        or not predecessor_starts <= cutover <= predecessor_stops
        or not successor_starts <= cutover < successor_stops
        or rollover_id
        != rollover_id_for(
            predecessor_schedule_sha256=predecessor_schedule,
            predecessor_activation_id=predecessor_activation,
            successor_schedule_sha256=successor_schedule,
            successor_activation_id=successor_activation,
            cutover_at=render_utc(cutover),
            authority_receipt_sha256=authority_receipt,
        )
    ):
        return False
    try:
        records, _telemetry = ResearchStore(
            data_root, create_if_missing=False
        ).iter_lifecycle_records_bounded(
            schedule_sha256=predecessor_schedule,
            activation_id=predecessor_activation,
            window_start=predecessor_starts,
            closure_cutoff=max(now, predecessor_stops),
        )
    except ResearchStoreError:
        return False
    expected_cutover = render_utc(cutover)
    expected_successor_starts = render_utc(successor_starts)
    expected_successor_stops = render_utc(successor_stops)
    expected_transaction_prefix = "RESEARCH-TXN-"
    for record in records:
        if (
            str(record.record_kind) != str(RecordKind.OBSERVATION_SCHEDULE_STATE)
            or str(record.entity_id) != predecessor_schedule
            or str(record.run_id or "") != predecessor_activation
            or str(record.transaction_id)
            != f"{expected_transaction_prefix}{record.record_id.upper()}"
            or str(record.record_id) != expected_predecessor_event_id
            or str(record.producer_capability_id) != PRODUCER_CAPABILITY
            or record.created_at.astimezone(UTC) > now
            or record.first_reliable_available_at.astimezone(UTC) > now
            or record.effective_at.astimezone(UTC) != cutover
        ):
            continue
        try:
            payload = json.loads(record.payload_json)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, Mapping):
            continue
        try:
            transition_sequence = int(payload["transition_sequence"])
            expected_event_id = transition_event_id_for(
                schedule_sha256=predecessor_schedule,
                activation_id=predecessor_activation,
                prior_state=str(payload.get("prior_state") or ""),
                new_state=str(
                    payload.get("new_state") or payload.get("state") or ""
                ),
                transition_sequence=transition_sequence,
                effective_at=render_utc(record.effective_at.astimezone(UTC)),
                authority_receipt_sha256=str(
                    payload.get("authority_receipt_sha256") or ""
                ),
            )
        except (KeyError, TypeError, ValueError):
            continue
        if (
            expected_event_id != str(record.record_id)
            or str(record.record_id) != expected_predecessor_event_id
            or str(payload.get("state_event_id") or "") != str(record.record_id)
            or str(payload.get("schedule_sha256") or "") != predecessor_schedule
            or str(payload.get("activation_id") or "") != predecessor_activation
            or str(payload.get("state") or "") != "DRAINING"
            or str(payload.get("prior_state") or "") != "ACTIVE"
            or payload.get("admission_window_closed") is not False
            or str(payload.get("rollover_id") or "") != rollover_id
            or str(payload.get("cutover_at") or "") != expected_cutover
            or str(payload.get("rollover_authority_receipt_sha256") or "")
            != authority_receipt
            or str(payload.get("predecessor_schedule_sha256") or "")
            != predecessor_schedule
            or str(payload.get("predecessor_activation_id") or "")
            != predecessor_activation
            or str(payload.get("successor_schedule_sha256") or "")
            != successor_schedule
            or str(payload.get("successor_activation_id") or "")
            != successor_activation
            or str(payload.get("successor_starts_at") or "")
            != expected_successor_starts
            or str(payload.get("successor_stops_admitting_at") or "")
            != expected_successor_stops
        ):
            continue
        break
    else:
        return False

    try:
        successor_records, _telemetry = ResearchStore(
            data_root, create_if_missing=False
        ).iter_lifecycle_records_bounded(
            schedule_sha256=successor_schedule,
            activation_id=successor_activation,
            window_start=successor_starts,
            closure_cutoff=max(now, successor_stops),
        )
    except ResearchStoreError:
        return False
    for record in successor_records:
        if (
            str(record.record_kind) != str(RecordKind.OBSERVATION_SCHEDULE_STATE)
            or str(record.entity_id) != successor_schedule
            or str(record.run_id or "") != successor_activation
            or str(record.record_id) != expected_successor_event_id
            or str(record.transaction_id)
            != f"{expected_transaction_prefix}{record.record_id.upper()}"
            or str(record.producer_capability_id) != PRODUCER_CAPABILITY
            or record.created_at.astimezone(UTC) > now
            or record.first_reliable_available_at.astimezone(UTC) > now
            or record.effective_at.astimezone(UTC) != cutover
        ):
            continue
        try:
            payload = json.loads(record.payload_json)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, Mapping):
            continue
        try:
            transition_sequence = int(payload["transition_sequence"])
            expected_event_id = transition_event_id_for(
                schedule_sha256=successor_schedule,
                activation_id=successor_activation,
                prior_state=str(payload.get("prior_state") or ""),
                new_state=str(
                    payload.get("new_state") or payload.get("state") or ""
                ),
                transition_sequence=transition_sequence,
                effective_at=render_utc(record.effective_at.astimezone(UTC)),
                authority_receipt_sha256=str(
                    payload.get("authority_receipt_sha256") or ""
                ),
            )
        except (KeyError, TypeError, ValueError):
            continue
        if (
            expected_event_id != str(record.record_id)
            or str(payload.get("state_event_id") or "") != str(record.record_id)
            or str(payload.get("schedule_sha256") or "") != successor_schedule
            or str(payload.get("activation_id") or "") != successor_activation
            or str(payload.get("state") or "") != "ACTIVE"
            or str(payload.get("prior_state") or "")
            not in {"UNREGISTERED", "PAUSED_OPERATOR"}
            or payload.get("admission_window_closed") is not None
            or str(payload.get("rollover_id") or "") != rollover_id
            or str(payload.get("cutover_at") or "") != expected_cutover
            or str(payload.get("authority_receipt_sha256") or "")
            != authority_receipt
            or str(payload.get("rollover_authority_receipt_sha256") or "")
            != authority_receipt
            or str(payload.get("predecessor_schedule_sha256") or "")
            != predecessor_schedule
            or str(payload.get("predecessor_activation_id") or "")
            != predecessor_activation
            or str(payload.get("successor_schedule_sha256") or "")
            != successor_schedule
            or str(payload.get("successor_activation_id") or "")
            != successor_activation
            or str(payload.get("successor_starts_at") or "")
            != expected_successor_starts
            or str(payload.get("successor_stops_admitting_at") or "")
            != expected_successor_stops
        ):
            continue
        return True
    return False


def resolve_late_recovery_proof(
    data_root: Path,
    row: Mapping[str, Any],
    *,
    now: datetime,
) -> dict[str, str | None]:
    """Project owner-readable recovery proof from the append-only event.

    ``NOT_REQUIRED`` means the committed DRAINING transition was not an
    admission-close transition (for example, an in-window rollover). It is
    distinct from ``UNKNOWN``, which means the lifecycle proof is unavailable.
    """

    evidence = _draining_transition_evidence(data_root, row, now=now)
    event_id = str(row.get("last_transition_event_id") or "") or None
    if evidence is None:
        return {
            "late_recovery_at": None,
            "late_recovery_proof": "UNKNOWN",
            "late_recovery_event_id": event_id,
        }
    effective, admission_closed = evidence
    if admission_closed:
        return {
            "late_recovery_at": render_utc(effective),
            "late_recovery_proof": "APPEND_ONLY_DRAINING_TRANSITION",
            "late_recovery_event_id": event_id,
        }
    return {
        "late_recovery_at": None,
        "late_recovery_proof": "NOT_REQUIRED",
        "late_recovery_event_id": event_id,
    }


def activation_transition_research_event_proven(
    data_root: Path | None,
    row: Mapping[str, Any],
    *,
    now: datetime,
) -> bool:
    """Prove that an ACTIVE projection matches its committed transition.

    SQLite is a mutable operational projection. It may label a transition
    ACTIVE before the effective time, or without the ResearchStore event that
    establishes when that lifecycle change became available. Neither case is
    proof that the activation is currently ACTIVE.
    """

    if data_root is None or str(row.get("state") or "") != "ACTIVE":
        return False
    schedule_sha256 = str(row.get("schedule_sha256") or "")
    activation_id = str(row.get("activation_id") or "")
    event_id = str(row.get("last_transition_event_id") or "")
    if not schedule_sha256 or not activation_id or not event_id:
        return False
    payload = row.get("payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            return False
    if not isinstance(payload, Mapping):
        return False
    if (
        str(payload.get("new_state") or "") != "ACTIVE"
        or str(payload.get("transition_event_id") or "") != event_id
    ):
        return False
    try:
        transition_sequence = int(payload["transition_sequence"])
        effective = parse_utc(str(payload["transition_effective_at"]))
        starts = parse_utc(str(row["starts_at"]))
        stops = parse_utc(str(row["stops_admitting_at"]))
        if int(row.get("transition_sequence") or 0) != transition_sequence:
            return False
        authority_receipt_sha256 = str(
            payload.get("authority_receipt_sha256") or ""
        )
        if (
            not authority_receipt_sha256
            or effective > now
            or render_utc(effective) != str(payload["transition_effective_at"])
        ):
            return False
        expected_event_id = transition_event_id_for(
            schedule_sha256=schedule_sha256,
            activation_id=activation_id,
            prior_state=str(payload["prior_state"]),
            new_state="ACTIVE",
            transition_sequence=transition_sequence,
            effective_at=render_utc(effective),
            authority_receipt_sha256=authority_receipt_sha256,
        )
    except (KeyError, TypeError, ValueError):
        return False
    if expected_event_id != event_id:
        return False
    try:
        records, _telemetry = ResearchStore(
            data_root, create_if_missing=False
        ).iter_lifecycle_records_bounded(
            schedule_sha256=schedule_sha256,
            activation_id=activation_id,
            window_start=starts,
            closure_cutoff=max(now, stops),
        )
    except ResearchStoreError:
        return False
    for record in records:
        if (
            str(record.record_id) != event_id
            or str(record.record_kind)
            != str(RecordKind.OBSERVATION_SCHEDULE_STATE)
            or str(record.entity_id) != schedule_sha256
            or str(record.run_id or "") != activation_id
            or str(record.transaction_id)
            != f"RESEARCH-TXN-{event_id.upper()}"
            or str(record.producer_capability_id) != PRODUCER_CAPABILITY
            or record.created_at.astimezone(UTC) > now
            or record.first_reliable_available_at.astimezone(UTC) > now
            or record.effective_at.astimezone(UTC) != effective
        ):
            continue
        try:
            event_payload = json.loads(record.payload_json)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(event_payload, Mapping):
            continue
        try:
            event_sequence = int(event_payload["transition_sequence"])
            event_authority = str(
                event_payload.get("authority_receipt_sha256") or ""
            )
            recomputed_event_id = transition_event_id_for(
                schedule_sha256=schedule_sha256,
                activation_id=activation_id,
                prior_state=str(event_payload["prior_state"]),
                new_state=str(event_payload["state"]),
                transition_sequence=event_sequence,
                effective_at=render_utc(record.effective_at.astimezone(UTC)),
                authority_receipt_sha256=event_authority,
            )
        except (KeyError, TypeError, ValueError):
            continue
        if (
            recomputed_event_id == event_id
            and event_sequence == transition_sequence
            and event_authority == authority_receipt_sha256
            and str(event_payload.get("state_event_id") or "") == event_id
            and str(event_payload.get("schedule_sha256") or "")
            == schedule_sha256
            and str(event_payload.get("activation_id") or "") == activation_id
            and str(event_payload.get("state") or "") == "ACTIVE"
            and str(event_payload.get("prior_state") or "")
            == str(payload.get("prior_state") or "")
        ):
            return True
    return False


def _require_cohort_cutover_or_unique(
    store: ObservationScheduleStore,
    *,
    data_root: Path,
    document: Mapping[str, Any],
    schedule_sha256: str,
    activation_id: str,
    now: datetime,
    authority_receipt_sha256: str,
) -> None:
    """Enforce at most one same-family admitting activation.

    Same-family ACTIVE/admission-capable DRAINING peers still require an exact
    rollover cutover. A proven NON_ADMITTING DRAINING predecessor does not
    block late post-window successor activation, but a backdated successor
    window (starts_at before the predecessor's stops_admitting_at) is denied.
    """

    family = _cohort_family_key(document)
    successor_starts = parse_utc(str(document["activation"]["starts_at"]))
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
        if not _activation_window_matches_registered(row, other["document"]):
            raise ObservationLifecycleError("ACTIVATION_WINDOW_MISMATCH")
        if _activation_is_non_admitting(row, now=now):
            peer_stops = parse_utc(str(row["stops_admitting_at"]))
            recovery_at = _non_admitting_recovery_at(data_root, row, now=now)
            if recovery_at is None or recovery_at > now:
                raise ObservationLifecycleError("LATE_SUCCESSOR_RECOVERY_UNPROVEN")
            if successor_starts > now:
                raise ObservationLifecycleError("ACTIVATION_BEFORE_STARTS_AT")
            if successor_starts < peer_stops or successor_starts < recovery_at:
                raise ObservationLifecycleError("LATE_SUCCESSOR_BACKDATED")
            continue
        allowed = any(
            str(item["successor_schedule_sha256"]) == schedule_sha256
            and str(item["successor_activation_id"]) == activation_id
            and str(item["predecessor_schedule_sha256"]) == str(row["schedule_sha256"])
            and str(item["predecessor_activation_id"]) == str(row["activation_id"])
            and str(item.get("authority_receipt_sha256") or "")
            == authority_receipt_sha256
            and rollover_research_event_proven(
                data_root,
                item=item,
                predecessor_document=other["document"],
                successor_document=document,
                now=now,
                predecessor_transition_event_id=str(
                    row.get("last_transition_event_id") or ""
                )
                or None,
                successor_transition_event_id=str(
                    (
                        store.get_activation(schedule_sha256, activation_id)
                        or {}
                    ).get("last_transition_event_id")
                    or ""
                )
                or None,
            )
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
            data_root=data_root,
            document=document,
            schedule_sha256=schedule_sha256,
            activation_id=activation_id,
            now=now,
            authority_receipt_sha256=receipt["receipt_sha256"],
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
    open_states = ("PENDING", "DUE", "CLAIMED")
    unresolved_states = ("IN_FLIGHT_CALL_INDETERMINATE", "BLOCKED_BUDGET")
    if store.count_due_in_states(
        open_states + unresolved_states,
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
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
            if not rollover_research_event_proven(
                data_root,
                item=matching_rollover,
                predecessor_document=predecessor_document,
                successor_document=successor_document,
                now=now,
                predecessor_transition_event_id=str(
                    predecessor.get("last_transition_event_id") or ""
                )
                or None,
                successor_transition_event_id=str(
                    successor_existing.get("last_transition_event_id") or ""
                )
                or None,
            ):
                raise ObservationLifecycleError(
                    "ROLLOVER_IMMUTABLE_PROOF_UNAVAILABLE"
                )
            return {
                "terminal": "ROLLOVER_REPLAY",
                "rollover_id": matching_rollover["rollover_id"],
                "cutover_at": cutover_text,
                "predecessor_state": "DRAINING",
                "successor_state": "ACTIVE",
            }
    if predecessor["state"] == "DRAINING":
        raise ObservationLifecycleError("ROLLOVER_IMMUTABLE_PROOF_UNAVAILABLE")
    if cutover < now:
        raise ObservationLifecycleError("ROLLOVER_CUTOVER_IN_PAST")
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
                "rollover_authority_receipt_sha256": (
                    successor_receipt["receipt_sha256"]
                ),
                "admission_window_closed": (
                    False if transition["state"] == "DRAINING" else None
                ),
                "predecessor_schedule_sha256": predecessor_schedule_sha256,
                "predecessor_activation_id": predecessor_activation_id,
                "successor_schedule_sha256": successor_schedule_sha256,
                "successor_activation_id": successor_activation_id,
                "successor_starts_at": successor_document["activation"]["starts_at"],
                "successor_stops_admitting_at": successor_document["activation"][
                    "stops_admitting_at"
                ],
            },
            now=now,
            producer_git_sha=producer_git_sha,
            run_id=transition["activation_id"],
            transaction_id=f"RESEARCH-TXN-{transition['event_id'].upper()}",
            effective_at=cutover,
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
                "transition_event_id": (
                    str(row.get("last_transition_event_id") or "") or "UNKNOWN"
                ),
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
    "cohort_family_key",
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
