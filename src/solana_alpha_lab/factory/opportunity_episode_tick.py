"""OPPORTUNITY_EPISODES branch of the one ObservationSchedule tick.

Called only by ``observation_scheduler.tick_once`` after live authority has
passed. Reuses the writer lease, call ledger, accounting/pacing, wall
deadline, HOT raw plane, typed Tokens V2 mapper and the production panel
publisher. Order inside one tick: publication recovery, admitted slots
(obligations first), one nomination round, publication, admission drain.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from solana_alpha_lab.factory.observation_panel_publisher import (
    publish_observation_batch,
    repair_open_publication_jobs,
)
from solana_alpha_lab.factory.observation_primitive_registry import (
    ObservationPrimitiveRegistry,
    PrimitiveRegistryError,
    load_observation_primitive_registry,
)
from solana_alpha_lab.factory.observation_primitives import (
    call_occurrence_id,
    category_url,
    execute_primitive,
    request_sha256,
    search_url,
)
from solana_alpha_lab.factory.observation_provider_pacing import (
    ClockSleepRequiredError,
    ProviderTickContext,
    require_sleep_capable_clock,
)
from solana_alpha_lab.factory.observation_provider_wall_deadline import (
    DEFAULT_PROVIDER_CALL_WALL_SECONDS,
    wrap_opener_with_wall_deadline,
)
from solana_alpha_lab.factory.observation_schedule import (
    canonical_json_bytes,
    canonical_sha256,
    canonical_sha256_members_observations,
    parse_utc,
    render_utc,
)
from solana_alpha_lab.factory.observation_schedule_store import (
    LEASE_SECONDS,
    ObservationScheduleStore,
    ObservationScheduleStoreError,
)
from solana_alpha_lab.factory.opportunity_episodes import (
    NOMINATION_PRIMITIVE,
    SEARCH_PRIMITIVE,
    WITNESS_POINT,
    admission_content_sha256,
    admission_record,
    build_frame,
    collection_lineage_id,
    cycle_start,
    episode_point_ids,
    final_availability_deadline,
    frame_receipt,
    load_protection_inventory,
    resolve_point,
    round_id,
    round_index,
    round_quota,
    round_start,
    schedule_binding,
    select_admissions,
    witness_age_ok,
)
from solana_alpha_lab.factory.raw_evidence_plane import (
    RawEvidencePlaneError,
    materialize_canonical_raw,
)
from solana_alpha_lab.factory.tokens_v2_typed_projection import (
    STATE_OBSERVED,
    TOKENS_V2_FIELD_KINDS,
    project_tokens_v2_field,
)

OWNER = "tick-once-episodes"
SNAPSHOT_POLICY = "PROVIDER_REPORTED_SNAPSHOT_V1"
SLOT_NOT_EXECUTED = "SLOT_NOT_EXECUTED"
ATTEMPT_OUTCOME_UNKNOWN = "ATTEMPT_OUTCOME_UNKNOWN"
MINT_ABSENT_IN_RESPONSE = "MINT_ABSENT_IN_RESPONSE"
SCHEMA_REQUIRED_KEYS = ("id",)


from solana_alpha_lab.factory.observation_scheduler import (  # noqa: E402
    ObservationSchedulerError,
    _Accounting,
)


class EpisodeTickError(ObservationSchedulerError):
    """Typed episode tick failure (surfaces as the ordinary tick terminal)."""


def _registered_fields(registry: ObservationPrimitiveRegistry, primitive_id: str) -> list[tuple[str, str]]:
    try:
        primitive = registry.require_primitive(primitive_id)
        return [
            (str(field_id), str(registry.require_field(str(field_id))["value_kind"]))
            for field_id in primitive.get("output_field_ids") or []
        ]
    except PrimitiveRegistryError as exc:
        raise EpisodeTickError("TYPED_VALUE_REGISTRY_INVALID") from exc


def typed_values(
    *,
    registry: ObservationPrimitiveRegistry,
    primitive_id: str,
    point_id: str,
    state: str,
    row: Mapping[str, Any] | None,
    missing_reason: str | None,
    event_time: str | None,
    first_reliable_available_at: str | None,
    request_sha256_value: str | None,
    call_occurrence_id_value: str | None,
) -> list[dict[str, Any]]:
    """Typed values through the single Tokens V2 mapper. Null is never zero."""

    values: list[dict[str, Any]] = []
    for field_id, value_kind in _registered_fields(registry, primitive_id):
        if state == "OBSERVED" and isinstance(row, Mapping) and field_id in TOKENS_V2_FIELD_KINDS:
            value, typed_state, typed_missing = project_tokens_v2_field(row, field_id)
            present = typed_state == STATE_OBSERVED
            field_state = STATE_OBSERVED if present else typed_state
            field_missing = None if present else (typed_missing or "FIELD_ABSENT")
        else:
            value, present = None, False
            field_state = state if state != "OBSERVED" else "MISSING_TYPED"
            field_missing = missing_reason or "FIELD_ABSENT"
        values.append(
            {
                "field_id": field_id,
                "value_kind": value_kind,
                "typed_value_or_null": str(value) if present else None,
                "state": field_state,
                "missing_reason": field_missing,
                "primitive_id": primitive_id,
                "point_id": point_id,
                "event_time": event_time,
                "first_reliable_available_at": first_reliable_available_at,
                "request_sha256": request_sha256_value,
                "call_occurrence_id": call_occurrence_id_value,
            }
        )
    return values


def observation_row(
    *,
    registry: ObservationPrimitiveRegistry,
    schedule_sha256: str,
    activation_id: str,
    admission: Mapping[str, Any],
    point_id: str,
    primitive_id: str,
    state: str,
    missing_reason: str | None,
    row: Mapping[str, Any] | None,
    timing: Mapping[str, Any] | None,
    window: Mapping[str, Any],
) -> dict[str, Any]:
    timing = timing or {}
    available = timing.get("first_reliable_available_at")
    request_digest = timing.get("request_sha256")
    occurrence = timing.get("call_occurrence_id")
    anchor = str(admission["t0"])
    return {
        "schedule_sha256": schedule_sha256,
        "activation_id": activation_id,
        "entity_id": str(admission["episode_id"]),
        "episode_id": str(admission["episode_id"]),
        "mint": str(admission["mint"]),
        "cohort_id": str(admission["cohort_id"]),
        "point_id": point_id,
        "primitive_id": primitive_id,
        "state": state,
        "event_time": anchor,
        "first_reliable_available_at": available,
        "request_started_at": timing.get("request_started_at"),
        "response_received_at": timing.get("response_received_at"),
        "request_sha256": request_digest,
        "call_occurrence_id": occurrence,
        "response_sha256": timing.get("response_sha256"),
        "raw_body_rel": timing.get("raw_body_rel"),
        "http_status": timing.get("http_status"),
        "http_class": timing.get("http_class"),
        "buy_out_amount": None,
        "sell_out_amount": None,
        "provisional_due": False,
        "authoritative_anchor": anchor,
        "member_anchor": anchor,
        "observation_clock_policy": SNAPSHOT_POLICY,
        "source_price_event_time": "UNKNOWN",
        "missing_reason": missing_reason,
        "nominal_due_at": window.get("nominal_due_at"),
        "assigned_at": window.get("assigned_at"),
        "request_not_before": window.get("request_not_before"),
        "availability_deadline": window.get("availability_deadline"),
        "field_values": typed_values(
            registry=registry,
            primitive_id=primitive_id,
            point_id=point_id,
            state=state,
            row=row,
            missing_reason=missing_reason,
            event_time=anchor,
            first_reliable_available_at=available,
            request_sha256_value=request_digest,
            call_occurrence_id_value=occurrence,
        ),
    }


def _window_payload(binding: Mapping[str, Any], t0: datetime, point_id: str) -> dict[str, Any]:
    window = resolve_point(binding, t0, point_id)
    return {
        "nominal_due_at": render_utc(window.nominal_due),
        "assigned_at": None if window.assigned_at is None else render_utc(window.assigned_at),
        "request_not_before": render_utc(window.request_not_before),
        "dispatch_deadline": None
        if window.dispatch_deadline is None
        else render_utc(window.dispatch_deadline),
        "availability_deadline": render_utc(window.availability_deadline),
    }


def _store_raw(
    data_root: Path,
    *,
    result: Mapping[str, Any],
    occurrence: str,
    primitive_id: str,
) -> str | None:
    if result.get("status") != "OBSERVED" or result.get("response_sha256") is None:
        return None
    available = str(result.get("first_reliable_available_at"))
    try:
        stored = materialize_canonical_raw(
            Path(data_root),
            utc_day=parse_utc(available).strftime("%Y%m%d"),
            call_occurrence_id=occurrence,
            request_sha256=str(result["request_sha256"]),
            response_sha256=str(result["response_sha256"]),
            body=result.get("body"),
            first_reliable_available_at=available,
            event_time=available,
            primitive_id=primitive_id,
        )
    except RawEvidencePlaneError as exc:
        if str(exc) == "RAW_OCCURRENCE_CONFLICT":
            day = parse_utc(available).strftime("%Y%m%d")
            return f"datasets/raw_evidence/{day}/bodies/{result['response_sha256']}.bin"
        raise EpisodeTickError(str(exc)) from exc
    return str(stored["occurrence"]["body_rel"])


WITNESS_EXTRACT_SCHEMA = "smial.opportunity-episode-witness-extract"


def _store_witness_extract(data_root: Path, candidate: Mapping[str, Any]) -> str | None:
    """The E0 raw dependency: only the admitted object, hash-linked to its source.

    A nomination response also lists protected or unresolved identities with
    their values; it stays on the capture host and no published row names it.
    """

    obj = candidate.get("object")
    available = candidate.get("selected_first_reliable_available_at")
    if not isinstance(obj, Mapping) or not available:
        return None
    body = json.dumps(
        {
            "schema": WITNESS_EXTRACT_SCHEMA,
            "schema_version": "1.0",
            "mint": candidate.get("mint"),
            "object": dict(obj),
            "object_sha256": candidate.get("selected_object_sha256"),
            "source_id": candidate.get("selected_source_id"),
            "source_rank": candidate.get("selected_rank"),
            "source_call_occurrence_id": candidate.get("selected_call_occurrence_id"),
            "source_response_sha256": candidate.get("selected_response_sha256"),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = __import__("hashlib").sha256(body).hexdigest()
    day = parse_utc(str(available)).strftime("%Y%m%d")
    rel = f"datasets/raw_evidence/{day}/witness/{digest}.json"
    path = Path(data_root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_bytes() != body:
            raise EpisodeTickError("WITNESS_EXTRACT_CONFLICT")
        return rel
    tmp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    tmp.write_bytes(body)
    tmp.replace(path)
    return rel


def _load_raw_body(data_root: Path, body_rel: str | None) -> object | None:
    if not isinstance(body_rel, str) or not body_rel:
        return None
    path = Path(data_root) / body_rel
    if not path.is_file() or path.is_symlink():
        return None
    return json.loads(path.read_bytes().decode("utf-8"))


def _ledger_payload(result: Mapping[str, Any], *, raw_body_rel: str | None, entities: Mapping[str, Any] | None) -> dict[str, Any]:
    return {
        "status": result.get("status"),
        "missing_reason": result.get("missing_reason"),
        "http_status": result.get("http_status"),
        "http_class": result.get("http_class"),
        "request_started_at": result.get("request_started_at"),
        "response_received_at": result.get("response_received_at"),
        "first_reliable_available_at": result.get("first_reliable_available_at"),
        "response_sha256": result.get("response_sha256"),
        "request_sha256": result.get("request_sha256"),
        "raw_body_rel": raw_body_rel,
        "entities": dict(entities or {}),
    }


def admission_quota(
    store: ObservationScheduleStore,
    *,
    lineage_id: str,
    sampling: Mapping[str, Any],
    round_started_at: datetime,
    round_period_seconds: int,
    round_id_value: str,
    now: datetime,
) -> dict[str, int]:
    """Round quota k_j bounded by the UTC day, rolling 24h and active caps.

    A resumed round keeps its own quota: earlier commits of the same round
    count against k_j, so a crash never admits more than the round allows.
    """

    ceiling = int(sampling["daily_normal_ceiling"])
    index = round_index(round_started_at, round_period_seconds)
    day_start = datetime(round_started_at.year, round_started_at.month, round_started_at.day, tzinfo=UTC)
    day_used = store.episode_admission_count(
        lineage_id=lineage_id, window_start=day_start, window_end=day_start + timedelta(days=1)
    )
    rolling_used = store.episode_admission_count(
        lineage_id=lineage_id,
        window_start=now - timedelta(hours=24),
        window_end=now + timedelta(seconds=1),
    )
    active = store.count_active_episodes(lineage_id=lineage_id, now=now)
    committed_in_round = store.episode_admissions_in_round(round_id_value)
    quota = max(
        0,
        min(
            round_quota(ceiling, index) - committed_in_round,
            ceiling - day_used,
            int(sampling["rolling_24h_max"]) - rolling_used,
            int(sampling["active_episode_cap"]) - active,
        ),
    )
    return {
        "quota": quota,
        "round_quota": round_quota(ceiling, index),
        "day_used": day_used,
        "rolling_used": rolling_used,
        "active": active,
        "committed_in_round": committed_in_round,
    }


class _EpisodeTick:
    def __init__(
        self,
        *,
        root: Path,
        data_root: Path,
        store: ObservationScheduleStore,
        schedule: Mapping[str, Any],
        activation: Mapping[str, Any],
        now: datetime,
        opener: object | None,
        credential_loader: Callable[[], str] | None,
        producer_git_sha: str,
        clock: object,
        fault_after: str | None,
        provider_call_wall_seconds: int | None,
        redact_with: str | None,
    ) -> None:
        self.root = Path(root)
        self.data_root = Path(data_root)
        self.store = store
        self.schedule = schedule
        self.activation = activation
        self.activation_id = str(activation["activation_id"])
        self.digest = str(schedule["schedule_sha256"])
        self.now = now
        self.producer = producer_git_sha
        self.fault_after = fault_after
        self.credential_loader = credential_loader
        self.holder = redact_with
        self.credential_reads = 0
        self.binding = schedule_binding(schedule)
        self.lineage = collection_lineage_id(schedule)
        try:
            injectable = require_sleep_capable_clock(clock)  # type: ignore[arg-type]
        except ClockSleepRequiredError as exc:
            raise EpisodeTickError(str(exc)) from exc
        self.provider_ctx = ProviderTickContext(
            tick_start=now,
            pace_seconds=int(schedule["budgets"]["min_provider_pace_seconds"]),
            injectable_clock=injectable,
        )
        wall = (
            DEFAULT_PROVIDER_CALL_WALL_SECONDS
            if provider_call_wall_seconds is None
            else int(provider_call_wall_seconds)
        )
        if wall <= 0 or wall >= LEASE_SECONDS:
            raise EpisodeTickError("PROVIDER_CALL_WALL_SECONDS_MUST_BE_BELOW_LEASE")
        self.opener = wrap_opener_with_wall_deadline(
            opener,
            wall_seconds=wall,
            heartbeat=lambda: store.renew_held_lease(clock=self.provider_ctx.now()),
        )
        self.has_opener = opener is not None
        try:
            self.registry = load_observation_primitive_registry(self.root)
            self.registry.verify_implementation_hashes()
        except PrimitiveRegistryError as exc:
            raise EpisodeTickError(str(exc)) from exc
        credit_costs = {
            primitive_id: int((primitive.get("modeled_credit_cost") or {}).get("credits_per_request", 1))
            for primitive_id, primitive in self.registry.primitives.items()
        }
        self.accounts = _Accounting(store, schedule, self.activation_id, now, credit_costs=credit_costs)
        self.report: dict[str, Any] = {
            "terminal": "TICK_COMPLETE",
            "collection": "OPPORTUNITY_EPISODES",
            "provider_calls": 0,
            "credential_reads": 0,
            "slots_terminalized": {},
            "admissions": [],
            "round": None,
            "publications": [],
            "stop_reason": None,
        }

    # ------------------------------------------------------------------
    def _prime_account_pace(self) -> None:
        """Account-wide minimum pace across every lane sharing this store."""

        latest = self.store.latest_provider_call_any()
        if not latest:
            return
        target = parse_utc(latest) + timedelta(seconds=self.provider_ctx.pace_seconds)
        current = self.provider_ctx.now()
        if current < target:
            sleeper = getattr(self.provider_ctx._injectable, "sleep", None)
            if callable(sleeper):
                sleeper((target - current).total_seconds())

    def _credential(self) -> None:
        if self.holder is None and self.credential_loader is not None:
            self.holder = self.credential_loader()
            self.credential_reads += 1

    def _call(
        self,
        *,
        primitive_id: str,
        url: str,
        occurrence: str,
        expected_entities: Sequence[str] | None,
        claim_identity: Sequence[str],
    ) -> tuple[str, dict[str, Any] | None]:
        """One durable call-ledger occurrence. Returns (terminal, result)."""

        request_digest = request_sha256(method="GET", url=url, body=None, primitive_version="1.0")
        prior = self.store.call_state(occurrence)
        if prior == "COMPLETED":
            payload = self.store.call_payload(occurrence) or {}
            recovered = dict(payload)
            recovered["body"] = _load_raw_body(self.data_root, payload.get("raw_body_rel"))
            recovered["recovered_from_ledger"] = True
            return "RECOVERED", recovered
        if prior is not None:
            return ATTEMPT_OUTCOME_UNKNOWN, None
        if not self.has_opener:
            return "TRANSPORT_UNAVAILABLE", None
        blocked = self.provider_ctx.wait_for_provider_slot(
            self.accounts,
            extra_credits=max(1, int(self.accounts.credit_costs.get(primitive_id, 1))),
        )
        if blocked:
            return blocked, None
        self._credential()
        attempt_id = f"ATT-{uuid4().hex[:12].upper()}"
        started = self.store.start_call(
            request_sha256=request_digest,
            call_occurrence_id=occurrence,
            attempt_id=attempt_id,
            primitive_id=primitive_id,
            payload={"url": url, "call_occurrence_id": occurrence, "claim_identity_set": sorted(claim_identity)},
            clock=self.provider_ctx.now(),
        )
        if started != "STARTED":
            return ATTEMPT_OUTCOME_UNKNOWN, None
        if self.fault_after == "EPISODE_AFTER_CALL_START":
            raise EpisodeTickError("FAULT_INJECTED:EPISODE_AFTER_CALL_START")
        result = execute_primitive(
            primitive_id=primitive_id,
            primitive_version="1.0",
            method="GET",
            url=url,
            opener=self.opener,
            clock=self.provider_ctx.clock(),
            redact_with=self.holder,
            expected_entities=list(expected_entities) if expected_entities else None,
            # An empty category list is a valid frame source; the closed frame
            # owns row shape (non-list body, rows without identity).
            schema_required_keys=SCHEMA_REQUIRED_KEYS if expected_entities else None,
        )
        if result.get("request_sha256") != request_digest:
            raise EpisodeTickError("REQUEST_HASH_MISMATCH")
        body_limit = int(self.schedule["budgets"]["response_decoded_bytes_max"])
        raw_len = len(canonical_json_bytes(result.get("body"))) if result.get("status") == "OBSERVED" else 0
        if raw_len > body_limit:
            result = {
                **result,
                "status": "MISSING_TYPED",
                "missing_reason": "RESPONSE_BODY_TOO_LARGE",
                "body": None,
                "entities": {},
                "response_sha256": None,
            }
        completion_raw = result.get("first_reliable_available_at") or result.get("response_received_at")
        completion = parse_utc(str(completion_raw)) if isinstance(completion_raw, str) else self.provider_ctx.now()
        self.provider_ctx.record_provider_completion(
            self.accounts,
            raw_bytes=max(1, raw_len),
            credits=max(1, int(self.accounts.credit_costs.get(primitive_id, 1))),
            completed_at=completion,
        )
        raw_rel = _store_raw(self.data_root, result=result, occurrence=occurrence, primitive_id=primitive_id)
        result["raw_body_rel"] = raw_rel
        result["call_occurrence_id"] = occurrence
        self.store.complete_call(
            request_sha256=request_digest,
            call_occurrence_id=occurrence,
            attempt_id=attempt_id,
            payload=_ledger_payload(result, raw_body_rel=raw_rel, entities=result.get("entities")),
            clock=completion,
        )
        if self.fault_after == "EPISODE_AFTER_CALL_COMPLETE":
            raise EpisodeTickError("FAULT_INJECTED:EPISODE_AFTER_CALL_COMPLETE")
        return "CALLED", result

    # ------------------------------------------------------------------
    def _terminalize(
        self,
        claim: Mapping[str, Any],
        *,
        state: str,
        missing_reason: str | None,
        row: Mapping[str, Any] | None,
        timing: Mapping[str, Any] | None,
    ) -> None:
        payload = dict(claim.get("payload") or {})
        admission = {
            "episode_id": claim["entity_id"],
            "mint": payload["mint"],
            "t0": payload["t0"],
            "cohort_id": payload["cohort_id"],
        }
        obs = observation_row(
            registry=self.registry,
            schedule_sha256=self.digest,
            activation_id=self.activation_id,
            admission=admission,
            point_id=str(claim["point_id"]),
            primitive_id=SEARCH_PRIMITIVE,
            state=state,
            missing_reason=missing_reason,
            row=row,
            timing=timing,
            window=payload,
        )
        outcome = self.store.terminalize_episode_slot(
            due_row=claim,
            state=state,
            request_sha256=(timing or {}).get("request_sha256"),
            call_occurrence_id=(timing or {}).get("call_occurrence_id"),
            payload={"missing_reason": missing_reason, "terminal_reason": missing_reason or state},
            outbox_row={
                "outbox_id": f"OBS:{claim['entity_id']}:{int(str(claim['point_id'])[1:]):07d}",
                "schedule_sha256": self.digest,
                "activation_id": self.activation_id,
                "kind": "OBSERVATION",
                "episode_id": str(claim["entity_id"]),
                "point_id": str(claim["point_id"]),
                "cohort_id": str(payload["cohort_id"]),
                "row": obs,
            },
            clock=self.provider_ctx.now(),
        )
        if outcome == "TERMINALIZED":
            counts = self.report["slots_terminalized"]
            key = state if missing_reason is None else f"{state}:{missing_reason}"
            counts[key] = int(counts.get(key, 0)) + 1

    def process_slots(self) -> None:
        """Admitted obligations before new intake. No catch-up for past slots."""

        claimed: list[dict[str, Any]] = []
        for page in self.store.iter_due_in_states_pages(
            ("CLAIMED",),
            schedule_sha256=self.digest,
            activation_id=self.activation_id,
            due_at_max=self.now,
            page_size=256,
        ):
            claimed.extend(dict(item) for item in page)
        claimed.extend(
            self.store.claim_due(
                limit=100000,
                now=self.now,
                owner=OWNER,
                schedule_sha256=self.digest,
                activation_id=self.activation_id,
            )
        )
        by_assigned: dict[str, list[dict[str, Any]]] = {}
        by_recorded: dict[str, list[dict[str, Any]]] = {}
        for claim in claimed:
            payload = dict(claim.get("payload") or {})
            recorded = payload.get("call_occurrence_id")
            if isinstance(recorded, str) and recorded:
                # A call intent was recorded before a crash: never re-request.
                by_recorded.setdefault(recorded, []).append(claim)
                continue
            dispatch_deadline = parse_utc(str(payload["dispatch_deadline"]))
            if self.provider_ctx.now() >= dispatch_deadline:
                self._terminalize(claim, state="CENSORED", missing_reason=SLOT_NOT_EXECUTED, row=None, timing=None)
                continue
            by_assigned.setdefault(str(claim["due_at"]), []).append(claim)
        for occurrence in sorted(by_recorded):
            self._recover_recorded(occurrence, by_recorded[occurrence])
        batch_size = int(self.schedule["observation_schedule"]["max_batch_size"])
        for assigned in sorted(by_assigned):
            claims = sorted(by_assigned[assigned], key=lambda item: (str(item["payload"]["mint"]), str(item["entity_id"])))
            for index in range(0, len(claims), batch_size):
                self._process_batch(assigned, claims[index : index + batch_size])

    def _process_batch(self, assigned: str, claims: Sequence[Mapping[str, Any]]) -> None:
        live = []
        for claim in claims:
            payload = dict(claim.get("payload") or {})
            if self.provider_ctx.now() >= parse_utc(str(payload["dispatch_deadline"])):
                self._terminalize(claim, state="CENSORED", missing_reason=SLOT_NOT_EXECUTED, row=None, timing=None)
            else:
                live.append(claim)
        if not live:
            return
        mints = sorted({str(item["payload"]["mint"]) for item in live})
        url = search_url(mints)
        request_digest = request_sha256(method="GET", url=url, body=None, primitive_version="1.0")
        identity = [f"{item['entity_id']}:{item['point_id']}" for item in live]
        occurrence = call_occurrence_id(
            schedule_sha256=self.digest,
            activation_id=self.activation_id,
            primitive_id=SEARCH_PRIMITIVE,
            point_id="EPISODE-SLOT",
            due_at=assigned,
            claim_identity_set=identity,
            request_digest=request_digest,
        )
        for claim in live:
            self.store.merge_due_payload(
                claim,
                {"call_occurrence_id": occurrence, "request_sha256": request_digest, "batch_url_sha256": canonical_sha256({"url": url})},
                clock=self.provider_ctx.now(),
            )
        terminal, result = self._call(
            primitive_id=SEARCH_PRIMITIVE,
            url=url,
            occurrence=occurrence,
            expected_entities=mints,
            claim_identity=identity,
        )
        self._apply_batch_result(live, terminal, result, request_digest=request_digest, occurrence=occurrence)

    def _recover_recorded(self, occurrence: str, claims: Sequence[Mapping[str, Any]]) -> None:
        state = self.store.call_state(occurrence)
        request_digest = str(dict(claims[0].get("payload") or {}).get("request_sha256") or "")
        if state == "COMPLETED":
            payload = self.store.call_payload(occurrence) or {}
            result = dict(payload)
            result["body"] = _load_raw_body(self.data_root, payload.get("raw_body_rel"))
            if result.get("status") == "OBSERVED" and result.get("body") is None:
                for claim in claims:
                    self._terminalize(claim, state="CENSORED", missing_reason="RAW_DEPENDENCY_MISSING", row=None, timing=None)
                return
            self._apply_batch_result(claims, "RECOVERED", result, request_digest=request_digest, occurrence=occurrence)
            return
        if state is None:
            # Intent recorded but the call never started: a no-request gap.
            self._apply_batch_result(claims, "NOT_STARTED", None, request_digest=request_digest, occurrence=occurrence)
            return
        self._apply_batch_result(claims, ATTEMPT_OUTCOME_UNKNOWN, None, request_digest=request_digest, occurrence=occurrence)

    def _apply_batch_result(
        self,
        live: Sequence[Mapping[str, Any]],
        terminal: str,
        result: Mapping[str, Any] | None,
        *,
        request_digest: str,
        occurrence: str,
    ) -> None:
        if result is None:
            reason = ATTEMPT_OUTCOME_UNKNOWN if terminal == ATTEMPT_OUTCOME_UNKNOWN else f"{SLOT_NOT_EXECUTED}:{terminal}"
            timing = {"request_sha256": request_digest, "call_occurrence_id": occurrence} if terminal == ATTEMPT_OUTCOME_UNKNOWN else None
            for claim in live:
                self._terminalize(claim, state="CENSORED", missing_reason=reason, row=None, timing=timing)
            if terminal in {"BLOCKED_BUDGET", "PACE_WAIT"}:
                self.report["stop_reason"] = terminal
            return
        timing = {
            "request_started_at": result.get("request_started_at"),
            "response_received_at": result.get("response_received_at"),
            "first_reliable_available_at": result.get("first_reliable_available_at"),
            "request_sha256": result.get("request_sha256") or request_digest,
            "call_occurrence_id": occurrence,
            "response_sha256": result.get("response_sha256"),
            "raw_body_rel": result.get("raw_body_rel"),
            "http_status": result.get("http_status"),
            "http_class": result.get("http_class"),
        }
        entities = result.get("entities") or {}
        body = result.get("body")
        indexed: dict[str, Mapping[str, Any]] = {}
        if isinstance(body, list):
            for row in body:
                if isinstance(row, Mapping):
                    mint = str(row.get("id") or row.get("mint") or "")
                    if mint:
                        indexed[mint] = row
        for claim in live:
            payload = dict(claim.get("payload") or {})
            mint = str(payload["mint"])
            if result.get("status") != "OBSERVED":
                reason = str(result.get("http_class") or result.get("missing_reason") or "HTTP_ERROR")
                if result.get("missing_reason"):
                    reason = str(result.get("missing_reason"))
                    if result.get("http_class") and result.get("http_class") != "HTTP_OK":
                        reason = f"{reason}:{result.get('http_class')}"
                self._terminalize(claim, state="CENSORED", missing_reason=reason, row=None, timing=timing)
                continue
            available = parse_utc(str(timing["first_reliable_available_at"]))
            if available > parse_utc(str(payload["availability_deadline"])):
                self._terminalize(claim, state="CENSORED_LATE", missing_reason="CENSORED_LATE", row=None, timing=timing)
                continue
            entity = entities.get(mint) if isinstance(entities, Mapping) else None
            row = indexed.get(mint)
            if row is None or (isinstance(entity, Mapping) and entity.get("status") != "OBSERVED"):
                self._terminalize(claim, state="DISAPPEARED", missing_reason=MINT_ABSENT_IN_RESPONSE, row=None, timing=timing)
                continue
            self._terminalize(claim, state="OBSERVED", missing_reason=None, row=row, timing=timing)

    # ------------------------------------------------------------------
    def nomination_round(self) -> None:
        nomination = self.schedule["nomination"]
        now = self.provider_ctx.now()
        started = round_start(now, int(nomination["round_period_seconds"]))
        rid = round_id(self.activation_id, started)
        slack = int(nomination["round_slack_seconds"])
        existing = self.store.get_episode_round(rid)
        if existing is not None and str(existing["state"]) != "STARTED":
            self.report["round"] = {"round_id": rid, "state": existing["state"], "replay": True}
            return
        if now > started + timedelta(seconds=slack):
            if existing is None:
                self.store.record_episode_round(
                    round_id=rid,
                    schedule_sha256=self.digest,
                    activation_id=self.activation_id,
                    lineage_id=self.lineage,
                    round_started_at=render_utc(started),
                    state="MISSED_NO_REQUEST",
                    frame={"round_id": rid, "terminal": "MISSED_NO_REQUEST"},
                    clock=now,
                )
            self.report["round"] = {"round_id": rid, "state": "MISSED_NO_REQUEST"}
            return
        if existing is None:
            self.store.record_episode_round(
                round_id=rid,
                schedule_sha256=self.digest,
                activation_id=self.activation_id,
                lineage_id=self.lineage,
                round_started_at=render_utc(started),
                state="STARTED",
                frame={"round_id": rid},
                clock=now,
            )
        source_results: list[dict[str, Any]] = []
        for source in nomination["sources"]:
            url = category_url(category=str(source["category"]), interval=str(source["interval"]), limit=int(source["limit"]))
            request_digest = request_sha256(method="GET", url=url, body=None, primitive_version="1.0")
            occurrence = call_occurrence_id(
                schedule_sha256=self.digest,
                activation_id=self.activation_id,
                primitive_id=NOMINATION_PRIMITIVE,
                point_id=f"ROUND:{source['source_id']}",
                due_at=render_utc(started),
                claim_identity_set=[rid],
                request_digest=request_digest,
            )
            terminal, result = self._call(
                primitive_id=NOMINATION_PRIMITIVE,
                url=url,
                occurrence=occurrence,
                expected_entities=None,
                claim_identity=[rid],
            )
            if result is None:
                source_results.append({"source_id": source["source_id"], "status": terminal, "missing_reason": terminal, "call_occurrence_id": occurrence})
                if terminal in {"BLOCKED_BUDGET", "PACE_WAIT"}:
                    self.report["stop_reason"] = terminal
                continue
            if result.get("recovered_from_ledger") and result.get("status") == "OBSERVED" and result.get("body") is None:
                source_results.append({"source_id": source["source_id"], "status": "RAW_DEPENDENCY_MISSING", "call_occurrence_id": occurrence})
                continue
            source_results.append(
                {
                    "source_id": source["source_id"],
                    "status": result.get("status"),
                    "missing_reason": result.get("missing_reason"),
                    "body": result.get("body"),
                    "request_sha256": result.get("request_sha256") or request_digest,
                    "request_started_at": result.get("request_started_at"),
                    "response_received_at": result.get("response_received_at"),
                    "first_reliable_available_at": result.get("first_reliable_available_at"),
                    "response_sha256": result.get("response_sha256"),
                    "raw_body_rel": result.get("raw_body_rel"),
                    "call_occurrence_id": occurrence,
                    "http_class": result.get("http_class"),
                }
            )
        inventory = load_protection_inventory(self.data_root, self.schedule["protection"]["assignment_sources"])
        frame = build_frame(
            document=self.schedule,
            activation_id=self.activation_id,
            round_started_at=started,
            source_results=source_results,
            inventory=inventory,
        )
        receipt = frame_receipt(frame)
        if not frame.get("complete"):
            self.store.record_episode_round(
                round_id=rid,
                schedule_sha256=self.digest,
                activation_id=self.activation_id,
                lineage_id=self.lineage,
                round_started_at=render_utc(started),
                state="INCOMPLETE",
                frame=receipt,
                clock=self.provider_ctx.now(),
            )
            self.report["round"] = {"round_id": rid, "state": "INCOMPLETE", "frame_sha256": receipt["frame_sha256"]}
            return
        sampling = self.schedule["sampling"]
        commit_now = self.provider_ctx.now()
        quota_state = admission_quota(
            self.store,
            lineage_id=self.lineage,
            sampling=sampling,
            round_started_at=started,
            round_period_seconds=int(nomination["round_period_seconds"]),
            round_id_value=rid,
            now=commit_now,
        )
        quota = quota_state["quota"]
        day_used = quota_state["day_used"]
        rolling_used = quota_state["rolling_used"]
        active = quota_state["active"]
        committed_in_round = quota_state["committed_in_round"]
        cycle = cycle_start(started)
        blocked = self.store.episode_blocked_mints(lineage_id=self.lineage, cycle_start=render_utc(cycle), now=commit_now)
        selection = select_admissions(
            frame=frame,
            seed=str(sampling["seed"]),
            cycle=cycle,
            quota=quota,
            blocked_mints=blocked,
        )
        admitted: list[str] = []
        witness_stale: list[str] = []
        for winner in selection["winners"]:
            t0 = self.provider_ctx.now()
            record = admission_record(
                document=self.schedule,
                activation_id=self.activation_id,
                lineage_id=self.lineage,
                cycle=cycle,
                mint=str(winner["mint"]),
                t0=t0,
                ticket_priority_value=str(winner["ticket_priority"]),
                candidate=winner["candidate"],
                frame_sha256=str(receipt["frame_sha256"]),
                protection_fingerprint=str(frame["protection_fingerprint"]),
                round_id_value=rid,
            )
            if not witness_age_ok(record, self.binding):
                witness_stale.append(str(winner["mint"]))
                continue
            # The published E0 dependency is the admitted object only.
            winner["candidate"] = {
                **winner["candidate"],
                "selected_raw_body_rel": _store_witness_extract(self.data_root, winner["candidate"]),
            }
            record = {**record, "witness_raw_body_rel": winner["candidate"]["selected_raw_body_rel"]}
            self._commit_admission(record, winner["candidate"], t0)
            admitted.append(str(record["episode_id"]))
        summary = {
            **receipt,
            "selection": {
                "quota": selection["quota"],
                "eligible_pending": selection["eligible_pending"],
                "winners": [item["mint"] for item in selection["winners"]],
                "not_selected": selection["not_selected"],
                "witness_stale": witness_stale,
                "admitted_episode_ids": admitted,
                "day_used_before": day_used,
                "rolling_used_before": rolling_used,
                "active_before": active,
                "committed_in_round_before": committed_in_round,
            },
        }
        self.store.record_episode_round(
            round_id=rid,
            schedule_sha256=self.digest,
            activation_id=self.activation_id,
            lineage_id=self.lineage,
            round_started_at=render_utc(started),
            state="CLOSED",
            frame=summary,
            clock=self.provider_ctx.now(),
        )
        self.report["round"] = {
            "round_id": rid,
            "state": "CLOSED",
            "frame_sha256": receipt["frame_sha256"],
            "quota": selection["quota"],
            "admitted": len(admitted),
        }
        self.report["admissions"].extend(admitted)

    def _commit_admission(self, record: Mapping[str, Any], candidate: Mapping[str, Any], t0: datetime) -> None:
        content = admission_content_sha256(record)
        final_deadline = final_availability_deadline(self.binding, t0)
        due_rows = []
        for point in episode_point_ids():
            if point == WITNESS_POINT:
                continue
            window = _window_payload(self.binding, t0, point)
            due_rows.append(
                {
                    "schedule_sha256": self.digest,
                    "activation_id": self.activation_id,
                    "entity_id": record["episode_id"],
                    "point_id": point,
                    "primitive_id": SEARCH_PRIMITIVE,
                    "due_at": window["assigned_at"],
                    "deadline_at": window["availability_deadline"],
                    "payload": {
                        **window,
                        "mint": record["mint"],
                        "t0": record["t0"],
                        "cohort_id": record["cohort_id"],
                        "episode_id": record["episode_id"],
                    },
                }
            )
        witness_timing = {
            "request_started_at": record.get("witness_request_started_at"),
            "response_received_at": record.get("witness_response_received_at"),
            "first_reliable_available_at": record.get("witness_first_reliable_available_at"),
            "request_sha256": record.get("witness_request_sha256"),
            "call_occurrence_id": record.get("witness_call_occurrence_id"),
            "response_sha256": record.get("witness_response_sha256"),
            "raw_body_rel": record.get("witness_raw_body_rel"),
            "http_status": 200,
            "http_class": "HTTP_OK",
        }
        witness = observation_row(
            registry=self.registry,
            schedule_sha256=self.digest,
            activation_id=self.activation_id,
            admission=record,
            point_id=WITNESS_POINT,
            primitive_id=NOMINATION_PRIMITIVE,
            state="OBSERVED",
            missing_reason=None,
            row=candidate.get("object") if isinstance(candidate.get("object"), Mapping) else None,
            timing=witness_timing,
            window=_window_payload(self.binding, t0, WITNESS_POINT),
        )
        outbox = [
            {
                "outbox_id": f"MEM:{record['episode_id']}",
                "schedule_sha256": self.digest,
                "activation_id": self.activation_id,
                "kind": "MEMBER",
                "episode_id": record["episode_id"],
                "point_id": None,
                "cohort_id": record["cohort_id"],
                "row": dict(record),
            },
            {
                "outbox_id": f"OBS:{record['episode_id']}:{0:07d}",
                "schedule_sha256": self.digest,
                "activation_id": self.activation_id,
                "kind": "OBSERVATION",
                "episode_id": record["episode_id"],
                "point_id": WITNESS_POINT,
                "cohort_id": record["cohort_id"],
                "row": witness,
            },
        ]
        if self.fault_after == "EPISODE_BEFORE_ADMISSION_COMMIT":
            raise EpisodeTickError("FAULT_INJECTED:EPISODE_BEFORE_ADMISSION_COMMIT")
        self.store.commit_episode_admission(
            record=record,
            content_sha256=content,
            final_deadline_at=render_utc(final_deadline),
            due_rows=due_rows,
            outbox_rows=outbox,
            clock=t0,
        )
        if self.fault_after == "EPISODE_AFTER_ADMISSION_COMMIT":
            raise EpisodeTickError("FAULT_INJECTED:EPISODE_AFTER_ADMISSION_COMMIT")

    # ------------------------------------------------------------------
    def publish_outbox(self) -> None:
        pending = self.store.pending_episode_outbox(schedule_sha256=self.digest, activation_id=self.activation_id)
        if not pending:
            return
        episode_ids = sorted({str(item["episode_id"]) for item in pending})
        members = []
        for episode_id in episode_ids:
            admission = self.store.get_episode_admission(episode_id)
            if admission is None:
                raise EpisodeTickError("EPISODE_OUTBOX_ADMISSION_MISSING")
            members.append(dict(admission["record"]))
        members.sort(key=lambda row: str(row["entity_id"]))
        observations = [dict(item["row"]) for item in pending if item["kind"] == "OBSERVATION"]
        content = canonical_sha256_members_observations(iter(members), iter(observations))
        if self.fault_after == "EPISODE_BEFORE_PUBLISH":
            raise EpisodeTickError("FAULT_INJECTED:EPISODE_BEFORE_PUBLISH")
        published = publish_observation_batch(
            data_root=self.data_root,
            root=self.root,
            schedule=self.schedule,
            activation_id=self.activation_id,
            now=self.provider_ctx.now(),
            producer_git_sha=self.producer,
            members=members,
            observations=observations,
            fault_after=self.fault_after,
            content_sha256=content,
        )
        if self.fault_after == "EPISODE_AFTER_PUBLISH_BEFORE_MARK":
            raise EpisodeTickError("FAULT_INJECTED:EPISODE_AFTER_PUBLISH_BEFORE_MARK")
        cohorts = sorted({str(item["cohort_id"]) for item in pending})
        self.store.mark_episode_outbox_published(
            schedule_sha256=self.digest,
            activation_id=self.activation_id,
            outbox_ids=[str(item["outbox_id"]) for item in pending],
            content_sha256=content,
            dataset_manifest_id=str(published["dataset_manifest_id"]),
            cohort_ids=cohorts,
            publication={
                "dataset_manifest_id": published["dataset_manifest_id"],
                "dataset_fingerprint": published.get("dataset_fingerprint"),
                "member_count": len(members),
                "observation_count": len(observations),
                "replay": bool(published.get("replay")),
            },
            clock=self.provider_ctx.now(),
        )
        self.report["publications"].append(
            {"content_sha256": content, "cohorts": cohorts, "rows": len(observations), "replay": bool(published.get("replay"))}
        )

    # ------------------------------------------------------------------
    def run(self, *, admission_open: bool) -> dict[str, Any]:
        repair_open_publication_jobs(
            data_root=self.data_root,
            root=self.root,
            schedule=self.schedule,
            activation_id=self.activation_id,
            now=self.now,
            producer_git_sha=self.producer,
            fault_after=self.fault_after,
        )
        self.publish_outbox()
        self._prime_account_pace()
        self.process_slots()
        if admission_open and self.report["stop_reason"] is None:
            self.nomination_round()
        self.publish_outbox()
        self.report["provider_calls"] = self.accounts.tick_calls
        self.report["credential_reads"] = self.credential_reads
        if self.report["stop_reason"] is not None:
            self.report["terminal"] = "TICK_PARTIAL"
        return self.report


def tick_episode_schedule(
    *,
    root,
    data_root,
    store: ObservationScheduleStore,
    schedule: Mapping[str, Any],
    activation_id: str,
    now: datetime,
    opener: object | None,
    credential_loader: Callable[[], str] | None,
    producer_git_sha: str,
    clock: object,
    fault_after: str | None = None,
    provider_call_wall_seconds: int | None = None,
    redact_with: str | None = None,
) -> dict[str, Any]:
    """One episode tick under the global writer lease (authority already passed)."""

    from solana_alpha_lab.factory.observation_schedule_lifecycle import (
        complete_draining_schedule,
        drain_expired_admission,
    )

    activation = store.get_activation(str(schedule["schedule_sha256"]), activation_id)
    if activation is None:
        raise EpisodeTickError("ACTIVATION_MISSING")
    lease_token = store.acquire_lease(f"{OWNER}-{uuid4().hex[:12]}", clock=now)
    if not lease_token:
        raise EpisodeTickError("WRITER_BUSY")
    try:
        drained = drain_expired_admission(
            data_root=Path(data_root),
            store=store,
            schedule_sha256=str(schedule["schedule_sha256"]),
            activation_id=activation_id,
            now=now,
            producer_git_sha=producer_git_sha,
        )
        state = str((drained or {}).get("state") or activation["state"])
        admission_open = state == "ACTIVE" and now < parse_utc(str(activation["stops_admitting_at"]))
        tick = _EpisodeTick(
            root=Path(root),
            data_root=Path(data_root),
            store=store,
            schedule=schedule,
            activation=activation,
            now=now,
            opener=opener,
            credential_loader=credential_loader,
            producer_git_sha=producer_git_sha,
            clock=clock,
            fault_after=fault_after,
            provider_call_wall_seconds=provider_call_wall_seconds,
            redact_with=redact_with,
        )
        report = tick.run(admission_open=admission_open)
        report["activation_state"] = state
        if state == "DRAINING":
            completion = complete_draining_schedule(
                data_root=Path(data_root),
                store=store,
                schedule_sha256=str(schedule["schedule_sha256"]),
                activation_id=activation_id,
                now=tick.provider_ctx.now(),
                producer_git_sha=producer_git_sha,
            )
            report["activation_state"] = completion.get("state")
            report["completion"] = completion.get("terminal")
        return report
    except ObservationScheduleStoreError as exc:
        raise EpisodeTickError(str(exc)) from exc
    finally:
        store.release_lease(lease_token)
