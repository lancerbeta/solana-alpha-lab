"""Crash-safe one-shot ObservationSchedule tick. systemd is the only time trigger."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from solana_alpha_lab.factory.observation_panel_publisher import (
    PublicationFault,
    publish_observation_batch,
    repair_open_publication_jobs,
)
from solana_alpha_lab.factory.observation_primitive_registry import (
    PrimitiveRegistryError,
    load_observation_primitive_registry,
)
from solana_alpha_lab.factory.observation_primitives import (
    BUY_AMOUNT,
    RECENT_URL,
    SOL_MINT,
    execute_primitive,
    parse_anchor,
    parse_first_seen,
    quote_url,
    request_sha256,
    search_url,
)
from solana_alpha_lab.factory.observation_schedule import (
    parse_utc,
    render_utc,
    schedule_sha256,
)
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore

OWNER = "tick-once"
SEARCH = "PRIM-JUPITER-TOKENS-V2-SEARCH-001"
DISCOVERY = "PRIM-JUPITER-TOKENS-V2-RECENT-001"
BUNDLE_TO_PRIMITIVE = {
    "BUNDLE-JUPITER-TOKEN-SEARCH-SNAPSHOT-001": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
    "BUNDLE-JUPITER-QUOTE-BUY-001": "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-001",
    "BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-001": "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001",
}
SCHEMA_REQUIRED_KEYS = {
    "PRIM-JUPITER-TOKENS-V2-RECENT-001": ("id",),
    "PRIM-JUPITER-TOKENS-V2-SEARCH-001": ("id",),
    "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-001": ("outAmount",),
    "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001": ("outAmount",),
}
DEPENDENT_SELL = "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001"
QUOTE_BUY = "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-001"


class ObservationSchedulerError(ValueError):
    """Typed scheduler failure."""


def _sample_included(*, seed: str, entity_id: str, schedule_digest: str, probability: str) -> bool:
    digest = hashlib.sha256(f"{seed}|{entity_id}|{schedule_digest}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF
    return bucket <= float(probability)


def poll_slot_id(*, primitive_id: str, query_profile_id: str, period_seconds: int, now: datetime) -> str:
    epoch = int(now.astimezone(UTC).timestamp())
    slot = epoch - (epoch % int(period_seconds))
    return hashlib.sha256(
        f"{primitive_id}|{query_profile_id}|{period_seconds}|{slot}".encode("utf-8")
    ).hexdigest()


def _due_times(anchor: datetime, offset: int, lateness: int) -> tuple[str, str]:
    due = anchor + timedelta(seconds=offset)
    deadline = due + timedelta(seconds=lateness)
    return render_utc(due), render_utc(deadline)


def _row_field(row: Mapping[str, Any], field_id: str) -> object:
    first_pool = row.get("firstPool") if isinstance(row.get("firstPool"), Mapping) else {}
    mapping = {
        "FIELD-TOKEN-MINT-001": row.get("id") or row.get("mint"),
        "FIELD-FIRST-POOL-CREATED-AT-001": first_pool.get("createdAt") if isinstance(first_pool, Mapping) else None,
        "FIELD-FIRST-POOL-SOURCE-001": first_pool.get("source") if isinstance(first_pool, Mapping) else row.get("source"),
        "FIELD-LIQUIDITY-USD-001": row.get("liquidity") or row.get("liquidityUsd"),
        "FIELD-FIRST-SEEN-AT-001": row.get("first_seen_at"),
    }
    return mapping.get(field_id)


def _predicate_holds(predicate: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    value = _row_field(row, str(predicate["field_id"]))
    if value is None:
        return False
    operator = str(predicate["operator"])
    if "value_text" in predicate and predicate["value_text"] is not None:
        if operator not in {"EQ", "NEQ"}:
            return False
        left = str(value)
        right = str(predicate["value_text"])
        return left == right if operator == "EQ" else left != right
    if "value_decimal" in predicate and predicate["value_decimal"] is not None:
        try:
            left = Decimal(str(value))
            right = Decimal(str(predicate["value_decimal"]))
        except (InvalidOperation, KeyError, TypeError):
            return False
        mapping = {
            "EQ": left == right,
            "NEQ": left != right,
            "GT": left > right,
            "GTE": left >= right,
            "LT": left < right,
            "LTE": left <= right,
        }
        return bool(mapping.get(operator, False))
    return False


def _population_eligible(schedule: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    population = schedule["population"]
    for predicate in list(population["source_predicates"]) + list(population["x_eligibility_predicates"]):
        if not _predicate_holds(predicate, row):
            return False
    return True


class _Accounting:
    def __init__(
        self,
        store: ObservationScheduleStore,
        schedule: Mapping[str, Any],
        activation_id: str,
        now: datetime,
    ) -> None:
        self.store = store
        self.now = now
        self.activation_id = activation_id
        self.digest = str(schedule["schedule_sha256"])
        self.utc_day = now.strftime("%Y-%m-%d")
        self.day = store.load_accounting(
            schedule_sha256=self.digest, activation_id=activation_id, utc_day=self.utc_day
        )
        self.life = store.load_lifetime(schedule_sha256=self.digest, activation_id=activation_id)
        self.tick_calls = 0
        self.budgets = schedule["budgets"]
        self.pace = int(self.budgets["min_provider_pace_seconds"])

    def gate(self, *, extra_calls: int = 1, extra_credits: int = 1, extra_raw: int = 1) -> str | None:
        if str(self.budgets.get("cash_usd_max")) != "0":
            return "CHANGE_LANE_SAFETY_CONTRACT_GAP"
        if self.budgets.get("retry") is not False or self.budgets.get("fallback") is not False:
            return "CHANGE_LANE_SAFETY_CONTRACT_GAP"
        if self.tick_calls + extra_calls > int(self.budgets["provider_calls_per_tick_max"]):
            return "BLOCKED_BUDGET"
        if int(self.day["provider_calls"]) + extra_calls > int(
            self.budgets["provider_calls_per_utc_day_max"]
        ):
            return "BLOCKED_BUDGET"
        if int(self.life["provider_calls"]) + extra_calls > int(
            self.budgets["provider_calls_lifetime_max"]
        ):
            return "BLOCKED_BUDGET"
        if int(self.day["modeled_credits"]) + extra_credits > int(
            self.budgets["modeled_provider_credits_per_utc_day_max"]
        ):
            return "BLOCKED_BUDGET"
        if int(self.day["raw_bytes"]) + extra_raw > int(self.budgets["raw_bytes_per_utc_day_max"]):
            return "BLOCKED_BUDGET"
        if int(self.life["canonical_bytes"]) + extra_raw > int(
            self.budgets["canonical_bytes_lifetime_max"]
        ):
            return "BLOCKED_BUDGET"
        last = self.day.get("last_provider_call_at")
        if last:
            try:
                elapsed = (self.now - parse_utc(str(last))).total_seconds()
            except Exception:
                elapsed = self.pace
            if elapsed > 0 and elapsed < self.pace:
                return "PACE_WAIT"
        return None

    def note(self, *, raw_bytes: int = 1, credits: int = 1) -> None:
        self.tick_calls += 1
        self.day["provider_calls"] = int(self.day["provider_calls"]) + 1
        self.day["modeled_credits"] = int(self.day["modeled_credits"]) + credits
        self.day["raw_bytes"] = int(self.day["raw_bytes"]) + raw_bytes
        self.day["last_provider_call_at"] = render_utc(self.now)
        self.life["provider_calls"] = int(self.life["provider_calls"]) + 1
        self.life["canonical_bytes"] = int(self.life["canonical_bytes"]) + raw_bytes
        self.store.save_accounting(
            schedule_sha256=self.digest,
            activation_id=self.activation_id,
            utc_day=self.utc_day,
            values=self.day,
            clock=self.now,
        )
        self.store.save_lifetime(
            schedule_sha256=self.digest,
            activation_id=self.activation_id,
            provider_calls=int(self.life["provider_calls"]),
            canonical_bytes=int(self.life["canonical_bytes"]),
            clock=self.now,
        )


def _entity_terminal(
    result: Mapping[str, Any],
    entity_id: str,
    *,
    previously_observed: bool,
) -> tuple[str, str | None]:
    entities = result.get("entities")
    if isinstance(entities, Mapping) and entity_id in entities:
        row = entities[entity_id]
        status = str(row.get("status") or "MISSING_TYPED")
        reason = row.get("missing_reason")
        if status != "OBSERVED" and previously_observed:
            return "DISAPPEARED", str(reason or "ENTITY_ABSENT_FROM_RESPONSE")
        if status != "OBSERVED":
            return "MISSING_TYPED", str(reason or "ENTITY_ABSENT_FROM_RESPONSE")
        return "OBSERVED", None
    if previously_observed:
        return "DISAPPEARED", str(result.get("missing_reason") or "ENTITY_ABSENT_FROM_RESPONSE")
    return "MISSING_TYPED", str(result.get("missing_reason") or "ENTITY_ABSENT_FROM_RESPONSE")


def _mints_from_search_url(url: str) -> set[str]:
    query = parse_qs(urlsplit(url).query).get("query", [""])[0]
    return {item for item in query.split(",") if item}


def _resolve_search_ledger(
    store: ObservationScheduleStore,
    live_ids: Sequence[str],
) -> tuple[str, str, str | None]:
    url = search_url(list(live_ids))
    digest = request_sha256(method="GET", url=url, body=None, primitive_version="1.0")
    prior = store.call_state(digest)
    if prior is not None:
        return url, digest, prior
    live_set = {str(item) for item in live_ids}
    for row in store.list_calls(primitive_id=SEARCH):
        payload = row.get("payload") or {}
        stored_url = str(payload.get("url") or "")
        stored_mints = _mints_from_search_url(stored_url)
        if not stored_mints:
            continue
        if live_set <= stored_mints:
            return stored_url, str(row["request_sha256"]), str(row["state"])
    return url, digest, None


def _discover(
    *,
    store: ObservationScheduleStore,
    schedule: Mapping[str, Any],
    activation_id: str,
    now: datetime,
    opener: object,
    credential_loader: Callable[[], str] | None,
    redact_with: str | None,
    accounts: _Accounting,
) -> tuple[list[Mapping[str, Any]], str | None, int, str | None, bool]:
    slot = poll_slot_id(
        primitive_id=str(schedule["source_poll"]["primitive_id"]),
        query_profile_id=str(schedule["source_poll"]["query_profile_id"]),
        period_seconds=int(schedule["source_poll"]["period_seconds"]),
        now=now,
    )
    cached = store.load_poll_slot(slot)
    if cached is not None:
        rows = list(cached["payload"].get("rows") or [])
        return rows, None, 0, redact_with, True
    blocked = accounts.gate()
    if blocked:
        return [], blocked, 0, redact_with, False
    holder = redact_with
    credential_reads = 0
    if holder is None and credential_loader is not None:
        holder = credential_loader()
        credential_reads = 1
    digest = request_sha256(method="GET", url=RECENT_URL, body=None, primitive_version="1.0")
    result = execute_primitive(
        primitive_id=DISCOVERY,
        primitive_version="1.0",
        method="GET",
        url=RECENT_URL,
        opener=opener,
        clock=lambda: now,
        redact_with=holder,
    )
    accounts.note(raw_bytes=len(json.dumps(result.get("body"), default=str)))
    body = result.get("body")
    rows = body if isinstance(body, list) else []
    store.save_poll_slot(
        poll_slot_id=slot,
        request_sha256=digest,
        payload={"rows": rows, "response_sha256": result.get("response_sha256")},
        clock=now,
    )
    return list(rows), None, credential_reads, holder, False


def tick_once(
    *,
    root,
    data_root,
    store: ObservationScheduleStore,
    schedule: Mapping[str, Any],
    activation_id: str,
    now: datetime,
    opener: object | None = None,
    credential_loader: Callable[[], str] | None = None,
    producer_git_sha: str,
    max_claims: int = 60,
    discovery_rows: Sequence[Mapping[str, Any]] | None = None,
    last_tick_at: datetime | None = None,
    redact_with: str | None = None,
    fault_after: str | None = None,
) -> dict[str, Any]:
    if now.tzinfo is None:
        raise ObservationSchedulerError("TIMESTAMP_INVALID")
    now = now.astimezone(UTC)
    if last_tick_at is not None and now < last_tick_at.astimezone(UTC):
        raise ObservationSchedulerError("CLOCK_WENT_BACKWARDS")
    if store.restore_marker_unresolved():
        raise ObservationSchedulerError("RESTORE_MARKER_UNRESOLVED")
    digest = str(schedule.get("schedule_sha256") or schedule_sha256(schedule))
    if schedule_sha256(schedule) != digest:
        raise ObservationSchedulerError("INVALID_IDENTITY")
    activation = store.get_activation(digest, activation_id)
    if activation is None:
        raise ObservationSchedulerError("ACTIVATION_MISSING")
    state = str(activation["state"])
    if state in {"PAUSED_OPERATOR", "ABORTED_SAFETY", "BLOCKED_AUTHORITY", "BLOCKED_BUDGET"}:
        return {"terminal": state, "provider_calls": 0, "credential_reads": 0}
    if not store.acquire_lease(OWNER, clock=now):
        raise ObservationSchedulerError("WRITER_BUSY")
    credential_reads = 0
    provider_calls = 0
    published_rows: list[dict[str, Any]] = []
    stop_reason: str | None = None
    source_poll_reused = False
    try:
        try:
            load_observation_primitive_registry(root).verify_implementation_hashes()
        except PrimitiveRegistryError as exc:
            raise ObservationSchedulerError(str(exc)) from exc
        repair_open_publication_jobs(
            data_root=data_root,
            root=root,
            schedule=schedule,
            activation_id=activation_id,
            now=now,
            producer_git_sha=producer_git_sha,
            fault_after=fault_after,
        )
        accounts = _Accounting(store, schedule, activation_id, now)
        if discovery_rows is None and opener is not None and state == "ACTIVE":
            discovery_rows, stop_reason, credential_reads, holder_disc, source_poll_reused = (
                _discover(
                    store=store,
                    schedule=schedule,
                    activation_id=activation_id,
                    now=now,
                    opener=opener,
                    credential_loader=credential_loader,
                    redact_with=redact_with,
                    accounts=accounts,
                )
            )
            if holder_disc is not None:
                redact_with = holder_disc
            if stop_reason in {"BLOCKED_BUDGET", "CHANGE_LANE_SAFETY_CONTRACT_GAP"}:
                store.upsert_activation(
                    {
                        "schedule_sha256": digest,
                        "activation_id": activation_id,
                        "schedule_key": activation["schedule_key"],
                        "state": stop_reason,
                        "authority_receipt_sha256": activation.get("authority_receipt_sha256"),
                        "starts_at": activation["starts_at"],
                        "stops_admitting_at": activation["stops_admitting_at"],
                        "payload": {"reason": stop_reason},
                    },
                    clock=now,
                )
                return {
                    "terminal": stop_reason,
                    "provider_calls": accounts.tick_calls,
                    "credential_reads": credential_reads,
                    "source_poll_reused": source_poll_reused,
                }
        if discovery_rows is not None and state == "ACTIVE":
            _admit_candidates(
                store=store,
                schedule=schedule,
                activation_id=activation_id,
                rows=discovery_rows,
                now=now,
                accounts=accounts,
            )
        recovered = store.due_in_states(("CLAIMED",), due_at_max=now)
        claims = recovered + store.claim_due(limit=max_claims, now=now, owner=OWNER)
        holder = redact_with
        batch_size = int(
            load_observation_primitive_registry(root)
            .require_primitive(SEARCH)
            .get("max_batch_size")
            or 1
        )
        search_claims = [item for item in claims if str(item["primitive_id"]) == SEARCH]
        for index in range(0, len(search_claims), max(1, batch_size)):
            chunk = search_claims[index : index + max(1, batch_size)]
            live = []
            for claim in chunk:
                if now > parse_utc(claim["deadline_at"]):
                    store.insert_due(
                        _due_copy(
                            claim, state="CENSORED", payload={"missing_reason": "CENSORED_LATE"}
                        ),
                        clock=now,
                    )
                else:
                    live.append(claim)
            if not live:
                continue
            url, request_digest, prior = _resolve_search_ledger(
                store, [str(item["entity_id"]) for item in live]
            )
            if prior == "STARTED":
                for claim in live:
                    store.insert_due(
                        _due_copy(
                            claim,
                            state="IN_FLIGHT_CALL_INDETERMINATE",
                            request_sha256=request_digest,
                            payload={"missing_reason": "IN_FLIGHT_CALL_INDETERMINATE"},
                        ),
                        clock=now,
                    )
                    published_rows.append(
                        _observation_row(
                            claim, "IN_FLIGHT_CALL_INDETERMINATE", now, request_digest
                        )
                    )
                continue
            if prior == "COMPLETED":
                ledger_payload = store.call_payload(request_digest) or {}
                recovered_result = {
                    "status": ledger_payload.get("status"),
                    "missing_reason": ledger_payload.get("missing_reason"),
                    "entities": ledger_payload.get("entities") or {},
                    "response_sha256": ledger_payload.get("response_sha256"),
                }
                for claim in live:
                    previously = str(claim.get("payload", {}).get("previously_observed") or "") == "1"
                    terminal_state, missing_reason = _entity_terminal(
                        recovered_result,
                        str(claim["entity_id"]),
                        previously_observed=previously,
                    )
                    store.insert_due(
                        _due_copy(
                            claim,
                            state=terminal_state,
                            request_sha256=request_digest,
                            payload={
                                "missing_reason": missing_reason
                                or ledger_payload.get("missing_reason")
                                or "RECOVERED_COMPLETED_LEDGER",
                                "response_sha256": ledger_payload.get("response_sha256"),
                            },
                        ),
                        clock=now,
                    )
                    published_rows.append(
                        _observation_row(claim, terminal_state, now, request_digest)
                    )
                continue
            if opener is None:
                continue
            blocked = accounts.gate()
            if blocked:
                stop_reason = blocked
                break
            if holder is None and credential_loader is not None:
                holder = credential_loader()
                credential_reads += 1
            attempt_id = f"ATT-{uuid4().hex[:12].upper()}"
            start_state = store.start_call(
                request_sha256=request_digest,
                attempt_id=attempt_id,
                primitive_id=SEARCH,
                payload={"url": url},
                clock=now,
            )
            if start_state != "STARTED":
                continue
            result = execute_primitive(
                primitive_id=SEARCH,
                primitive_version="1.0",
                method="GET",
                url=url,
                opener=opener,
                clock=lambda: now,
                redact_with=holder,
                expected_entities=[str(item["entity_id"]) for item in live],
                schema_required_keys=SCHEMA_REQUIRED_KEYS.get(SEARCH),
            )
            if result.get("request_sha256") != request_digest:
                raise ObservationSchedulerError("REQUEST_HASH_MISMATCH")
            accounts.note(raw_bytes=len(json.dumps(result.get("body"), default=str)))
            provider_calls = accounts.tick_calls
            entity_payload = result.get("entities") or {}
            store.complete_call(
                request_sha256=request_digest,
                attempt_id=attempt_id,
                payload={
                    "response_sha256": result.get("response_sha256"),
                    "status": result.get("status"),
                    "entities": entity_payload,
                    "buy_out_amount": None,
                },
                clock=now,
            )
            for claim in live:
                previously = str(claim.get("payload", {}).get("previously_observed") or "") == "1"
                terminal_state, missing_reason = _entity_terminal(
                    result,
                    str(claim["entity_id"]),
                    previously_observed=previously,
                )
                store.insert_due(
                    _due_copy(
                        claim,
                        state=terminal_state,
                        request_sha256=request_digest,
                        payload={
                            "missing_reason": missing_reason or result.get("missing_reason"),
                            "response_sha256": result.get("response_sha256"),
                        },
                    ),
                    clock=now,
                )
                published_rows.append(
                    _observation_row(claim, terminal_state, now, request_digest)
                )
        for claim in claims:
            if str(claim["primitive_id"]) == SEARCH:
                continue
            deadline = parse_utc(claim["deadline_at"])
            if now > deadline:
                store.insert_due(
                    _due_copy(claim, state="CENSORED", payload={"missing_reason": "CENSORED_LATE"}),
                    clock=now,
                )
                continue
            url_result = _url_for_claim(schedule, claim)
            if url_result is None:
                store.insert_due(
                    _due_copy(
                        claim,
                        state="DEPENDENCY_MISSING",
                        payload={"missing_reason": "DEPENDENCY_MISSING"},
                    ),
                    clock=now,
                )
                published_rows.append(_observation_row(claim, "DEPENDENCY_MISSING", now, None))
                continue
            url, version = url_result
            request_digest = request_sha256(
                method="GET",
                url=url,
                body=None,
                primitive_version=version,
            )
            prior = store.call_state(request_digest)
            if prior == "STARTED":
                store.insert_due(
                    _due_copy(
                        claim,
                        state="IN_FLIGHT_CALL_INDETERMINATE",
                        request_sha256=request_digest,
                        payload={"missing_reason": "IN_FLIGHT_CALL_INDETERMINATE"},
                    ),
                    clock=now,
                )
                published_rows.append(
                    _observation_row(claim, "IN_FLIGHT_CALL_INDETERMINATE", now, request_digest)
                )
                continue
            if prior == "COMPLETED":
                ledger_payload = store.call_payload(request_digest) or {}
                previously = str(claim.get("payload", {}).get("previously_observed") or "") == "1"
                recovered_state, recovered_reason = _entity_terminal(
                    {
                        "status": ledger_payload.get("status"),
                        "missing_reason": ledger_payload.get("missing_reason"),
                        "entities": ledger_payload.get("entities") or {},
                    },
                    str(claim["entity_id"]),
                    previously_observed=previously,
                )
                store.insert_due(
                    _due_copy(
                        claim,
                        state=recovered_state,
                        request_sha256=request_digest,
                        payload={
                            "missing_reason": recovered_reason
                            or ledger_payload.get("missing_reason")
                            or "RECOVERED_COMPLETED_LEDGER",
                            "response_sha256": ledger_payload.get("response_sha256"),
                            "buy_out_amount": (ledger_payload.get("entities") or {})
                            .get(str(claim["entity_id"]), {})
                            .get("buy_out_amount")
                            or ledger_payload.get("buy_out_amount"),
                        },
                    ),
                    clock=now,
                )
                published_rows.append(
                    _observation_row(
                        claim,
                        recovered_state,
                        now,
                        request_digest,
                        ledger_payload.get("buy_out_amount"),
                    )
                )
                continue
            if opener is None:
                continue
            blocked = accounts.gate()
            if blocked:
                stop_reason = blocked
                break
            if holder is None and credential_loader is not None:
                holder = credential_loader()
                credential_reads += 1
            attempt_id = f"ATT-{uuid4().hex[:12].upper()}"
            start_state = store.start_call(
                request_sha256=request_digest,
                attempt_id=attempt_id,
                primitive_id=str(claim["primitive_id"]),
                payload={"url": url},
                clock=now,
            )
            if start_state != "STARTED":
                store.insert_due(
                    _due_copy(
                        claim,
                        state=start_state,
                        request_sha256=request_digest,
                        payload={"missing_reason": start_state},
                    ),
                    clock=now,
                )
                continue
            result = execute_primitive(
                primitive_id=str(claim["primitive_id"]),
                primitive_version=version,
                method="GET",
                url=url,
                opener=opener,
                clock=lambda: now,
                redact_with=holder,
                expected_entities=[str(claim["entity_id"])],
                schema_required_keys=SCHEMA_REQUIRED_KEYS.get(str(claim["primitive_id"])),
            )
            if result.get("request_sha256") != request_digest:
                raise ObservationSchedulerError("REQUEST_HASH_MISMATCH")
            accounts.note(raw_bytes=len(json.dumps(result.get("body"), default=str)))
            provider_calls = accounts.tick_calls
            buy_out = None
            body = result.get("body")
            if isinstance(body, Mapping):
                buy_out = body.get("outAmount")
            entity_map = result.get("entities") or {
                str(claim["entity_id"]): {"status": result.get("status"), "buy_out_amount": buy_out}
            }
            store.complete_call(
                request_sha256=request_digest,
                attempt_id=attempt_id,
                payload={
                    "response_sha256": result.get("response_sha256"),
                    "status": result.get("status"),
                    "buy_out_amount": buy_out,
                    "entities": entity_map,
                },
                clock=now,
            )
            terminal_state, missing_reason = _entity_terminal(
                result,
                str(claim["entity_id"]),
                previously_observed=False,
            )
            store.insert_due(
                _due_copy(
                    claim,
                    state=terminal_state,
                    request_sha256=request_digest,
                    payload={
                        "missing_reason": missing_reason or result.get("missing_reason"),
                        "late_seconds": max(
                            0,
                            int((now - parse_utc(claim["due_at"])).total_seconds()),
                        ),
                        "response_sha256": result.get("response_sha256"),
                        "buy_out_amount": buy_out,
                    },
                ),
                clock=now,
            )
            if terminal_state == "OBSERVED" and str(claim["primitive_id"]) == QUOTE_BUY and buy_out:
                _propagate_buy_out(
                    store,
                    schedule=schedule,
                    activation_id=activation_id,
                    entity_id=str(claim["entity_id"]),
                    buy_out_amount=str(buy_out),
                    now=now,
                )
                for later in claims:
                    if (
                        later.get("entity_id") == claim["entity_id"]
                        and later.get("primitive_id") == DEPENDENT_SELL
                    ):
                        payload = dict(later.get("payload") or {})
                        payload["buy_out_amount"] = str(buy_out)
                        later["payload"] = payload
            published_rows.append(
                _observation_row(claim, terminal_state, now, request_digest, buy_out)
            )
        members = _member_snapshot(
            store, digest=digest, activation_id=activation_id, now=now
        )
        if members and published_rows:
            publish_observation_batch(
                data_root=data_root,
                root=root,
                schedule=schedule,
                activation_id=activation_id,
                now=now,
                producer_git_sha=producer_git_sha,
                members=members,
                observations=published_rows,
                fault_after=fault_after,
            )
        store.record_event(
            "TICK",
            {
                "schedule_sha256": digest,
                "provider_calls": provider_calls,
                "credential_reads": credential_reads,
                "claims": len(claims),
            },
            clock=now,
        )
        return {
            "terminal": stop_reason or "TICK_COMPLETE",
            "provider_calls": accounts.tick_calls,
            "credential_reads": credential_reads,
            "claims": len(claims),
            "published": len(published_rows),
            "source_poll_reused": source_poll_reused,
        }
    finally:
        store.release_lease(OWNER)


def _member_snapshot(
    store: ObservationScheduleStore,
    *,
    digest: str,
    activation_id: str,
    now: datetime,
) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    dues = store.due_in_states(
        (
            "PENDING",
            "DUE",
            "CLAIMED",
            "OBSERVED",
            "MISSING_TYPED",
            "DISAPPEARED",
            "CENSORED",
            "IN_FLIGHT_CALL_INDETERMINATE",
            "DEPENDENCY_MISSING",
        )
    )
    due_by_entity: dict[str, list[dict[str, Any]]] = {}
    for row in dues:
        if row["schedule_sha256"] == digest and row["activation_id"] == activation_id:
            due_by_entity.setdefault(str(row["entity_id"]), []).append(row)
    for candidate in store.list_candidates(schedule_sha256=digest, activation_id=activation_id):
        entity_id = str(candidate["entity_id"])
        payload = candidate.get("payload") or {}
        points = due_by_entity.get(entity_id) or []
        membership_state = str(candidate["state"])
        state_map = {
            "CANDIDATE": "DISCOVERED",
            "NOT_SELECTED_PREDICATE": "PREDICATE_REJECTED",
            "NOT_SELECTED_HASH_SAMPLE": "PREDICATE_REJECTED",
            "NOT_SELECTED_CAPACITY": "CAPACITY_EXCLUDED",
            "ADMITTED": "ADMITTED",
            "ANCHOR_UNKNOWN": "PREDICATE_REJECTED",
        }
        membership_state = state_map.get(membership_state, membership_state)
        if any(item["state"] == "OBSERVED" for item in points):
            membership_state = "OBSERVED"
        elif any(item["state"] == "DISAPPEARED" for item in points):
            membership_state = "DISAPPEARED"
        elif any(item["state"] == "MISSING_TYPED" for item in points):
            membership_state = "MISSING_TYPED"
        elif any(item["state"] == "CENSORED" for item in points):
            membership_state = "CENSORED"
        elif any(item["state"] in {"PENDING", "DUE", "CLAIMED"} for item in points):
            membership_state = "SCHEDULED"
        members.append(
            {
                "schedule_sha256": digest,
                "activation_id": activation_id,
                "entity_id": entity_id,
                "membership_state": membership_state,
                "candidate_state": candidate["state"],
                "authoritative_anchor": payload.get("anchor_event_time"),
                "provisional_due": bool(payload.get("provisional_due")),
                "inclusion_probability": payload.get("inclusion_probability"),
                "sampling_seed": payload.get("sampling_seed"),
                "event_time": payload.get("anchor_event_time"),
                "first_reliable_available_at": render_utc(now),
            }
        )
    return members


def _due_copy(
    claim: Mapping[str, Any],
    *,
    state: str,
    payload: Mapping[str, Any],
    request_sha256: str | None = None,
) -> dict[str, Any]:
    return {
        "schedule_sha256": claim["schedule_sha256"],
        "activation_id": claim["activation_id"],
        "entity_id": claim["entity_id"],
        "point_id": claim["point_id"],
        "primitive_id": claim["primitive_id"],
        "due_at": claim["due_at"],
        "deadline_at": claim["deadline_at"],
        "state": state,
        "request_sha256": request_sha256,
        "payload": dict(payload),
    }


def _observation_row(
    claim: Mapping[str, Any],
    state: str,
    now: datetime,
    request_digest: str | None,
    buy_out: object | None = None,
) -> dict[str, Any]:
    payload = claim.get("payload") or {}
    anchor = payload.get("anchor_event_time")
    provisional = bool(payload.get("provisional_due"))
    if isinstance(anchor, str) and anchor:
        event_time = anchor
    elif provisional:
        event_time = None
    else:
        event_time = claim["due_at"]
    return {
        "schedule_sha256": claim["schedule_sha256"],
        "activation_id": claim["activation_id"],
        "entity_id": claim["entity_id"],
        "point_id": claim["point_id"],
        "primitive_id": claim["primitive_id"],
        "state": state,
        "event_time": event_time,
        "first_reliable_available_at": render_utc(now),
        "request_sha256": request_digest,
        "buy_out_amount": buy_out,
        "provisional_due": provisional,
        "authoritative_anchor": anchor,
    }


def _url_for_claim(schedule: Mapping[str, Any], claim: Mapping[str, Any]) -> tuple[str, str] | None:
    primitive_id = str(claim["primitive_id"])
    entity_id = str(claim["entity_id"])
    if primitive_id == "PRIM-JUPITER-TOKENS-V2-RECENT-001":
        return RECENT_URL, "1.0"
    if primitive_id == "PRIM-JUPITER-TOKENS-V2-SEARCH-001":
        return search_url([entity_id]), "1.0"
    if primitive_id == QUOTE_BUY:
        return quote_url(input_mint=SOL_MINT, output_mint=entity_id, amount=BUY_AMOUNT), "1.0"
    if primitive_id == DEPENDENT_SELL:
        payload = claim.get("payload") or {}
        amount = payload.get("buy_out_amount")
        if not amount:
            return None
        return quote_url(input_mint=entity_id, output_mint=SOL_MINT, amount=str(amount)), "1.0"
    raise ObservationSchedulerError("CHANGE_LANE_PRIMITIVE_GAP")


def _propagate_buy_out(
    store: ObservationScheduleStore,
    *,
    schedule: Mapping[str, Any],
    activation_id: str,
    entity_id: str,
    buy_out_amount: str,
    now: datetime,
) -> None:
    digest = str(schedule["schedule_sha256"])
    pending = store.due_in_states(("PENDING", "DUE", "CLAIMED"))
    for row in pending:
        if (
            row["schedule_sha256"] == digest
            and row["activation_id"] == activation_id
            and row["entity_id"] == entity_id
            and row["primitive_id"] == DEPENDENT_SELL
        ):
            store.merge_due_payload(row, {"buy_out_amount": buy_out_amount}, clock=now)


def _admit_candidates(
    *,
    store: ObservationScheduleStore,
    schedule: Mapping[str, Any],
    activation_id: str,
    rows: Sequence[Mapping[str, Any]],
    now: datetime,
    accounts: _Accounting,
) -> None:
    digest = str(schedule["schedule_sha256"])
    sampling = schedule["sampling"]
    member_cap = int(sampling["max_members_per_utc_day"])
    candidate_cap = int(sampling["max_candidates_per_utc_day"])
    day_members = int(accounts.day.get("members") or 0)
    day_candidates = int(accounts.day.get("candidates") or 0)
    stops = parse_utc(schedule["activation"]["stops_admitting_at"])
    if now >= stops:
        return
    for row in rows:
        entity_id = str(row.get("id") or row.get("mint") or "")
        if not entity_id:
            continue
        inserted = store.insert_candidate(
            {
                "schedule_sha256": digest,
                "activation_id": activation_id,
                "entity_id": entity_id,
                "state": "CANDIDATE",
                "payload": {
                    "first_seen_at": render_utc(now),
                    "inclusion_probability": sampling["inclusion_probability"],
                    "sampling_seed": sampling["seed"],
                },
            },
            clock=now,
        )
        if inserted is False:
            continue
        day_candidates += 1
        accounts.day["candidates"] = day_candidates
        accounts.store.save_accounting(
            schedule_sha256=digest,
            activation_id=activation_id,
            utc_day=accounts.utc_day,
            values=accounts.day,
            clock=now,
        )
        if day_candidates > candidate_cap:
            store.set_candidate_state(
                {
                    "schedule_sha256": digest,
                    "activation_id": activation_id,
                    "entity_id": entity_id,
                    "state": "NOT_SELECTED_CAPACITY",
                    "payload": {"reason": "MAX_CANDIDATES_PER_UTC_DAY", "discovered": day_candidates},
                },
                clock=now,
            )
            continue
        if not _population_eligible(schedule, row):
            store.set_candidate_state(
                {
                    "schedule_sha256": digest,
                    "activation_id": activation_id,
                    "entity_id": entity_id,
                    "state": "NOT_SELECTED_PREDICATE",
                    "payload": {"reason": "POPULATION_PREDICATE_FAIL_CLOSED"},
                },
                clock=now,
            )
            continue
        if not _sample_included(
            seed=str(sampling["seed"]),
            entity_id=entity_id,
            schedule_digest=digest,
            probability=str(sampling["inclusion_probability"]),
        ):
            store.set_candidate_state(
                {
                    "schedule_sha256": digest,
                    "activation_id": activation_id,
                    "entity_id": entity_id,
                    "state": "NOT_SELECTED_HASH_SAMPLE",
                    "payload": {"inclusion_probability": sampling["inclusion_probability"]},
                },
                clock=now,
            )
            continue
        if day_members >= member_cap:
            store.set_candidate_state(
                {
                    "schedule_sha256": digest,
                    "activation_id": activation_id,
                    "entity_id": entity_id,
                    "state": "NOT_SELECTED_CAPACITY",
                    "payload": {"universe_count": len(rows), "admitted": day_members},
                },
                clock=now,
            )
            continue
        anchor = parse_anchor(row)
        provisional = False
        if anchor is None and str(schedule["population"]["scheduling_fallback"]) == "FIRST_SEEN_AT_ONLY":
            seen = parse_first_seen(row)
            if seen is None and isinstance(row.get("first_seen_at"), str) is False:
                seen = now
            if seen is not None:
                anchor = seen
                provisional = True
        if anchor is None:
            store.set_candidate_state(
                {
                    "schedule_sha256": digest,
                    "activation_id": activation_id,
                    "entity_id": entity_id,
                    "state": "ANCHOR_UNKNOWN",
                    "payload": {"scheduling_fallback": schedule["population"]["scheduling_fallback"]},
                },
                clock=now,
            )
            continue
        day_members += 1
        accounts.day["members"] = day_members
        accounts.store.save_accounting(
            schedule_sha256=digest,
            activation_id=activation_id,
            utc_day=accounts.utc_day,
            values=accounts.day,
            clock=now,
        )
        store.set_candidate_state(
            {
                "schedule_sha256": digest,
                "activation_id": activation_id,
                "entity_id": entity_id,
                "state": "ADMITTED",
                "payload": {
                    "anchor_event_time": None if provisional else render_utc(anchor),
                    "provisional_due": provisional,
                    "provisional_due_at": render_utc(anchor) if provisional else None,
                },
            },
            clock=now,
        )
        _enqueue_points(
            store,
            schedule,
            activation_id,
            entity_id,
            anchor,
            now,
            provisional=provisional,
        )


def _enqueue_points(
    store: ObservationScheduleStore,
    schedule: Mapping[str, Any],
    activation_id: str,
    entity_id: str,
    anchor: datetime,
    now: datetime,
    *,
    provisional: bool = False,
) -> None:
    digest = str(schedule["schedule_sha256"])
    points = [schedule["x_point"], *list(schedule["y_points"])]
    for point in points:
        for bundle_id in point["bundle_ids"]:
            primitive_id = BUNDLE_TO_PRIMITIVE[str(bundle_id)]
            due_at, deadline_at = _due_times(
                anchor,
                int(point["due_offset_seconds"]),
                int(point["allowed_lateness_seconds"]),
            )
            store.insert_due(
                {
                    "schedule_sha256": digest,
                    "activation_id": activation_id,
                    "entity_id": entity_id,
                    "point_id": str(point["point_id"]),
                    "primitive_id": primitive_id,
                    "state": "PENDING",
                    "due_at": due_at,
                    "deadline_at": deadline_at,
                    "payload": {
                        "anchor_event_time": None if provisional else render_utc(anchor),
                        "provisional_due": provisional,
                    },
                },
                clock=now,
            )


def apply_recovery_gap(store: ObservationScheduleStore, *, cutoff: datetime) -> int:
    return store.mark_recovery_gap(cutoff=cutoff)


__all__ = [
    "ObservationSchedulerError",
    "apply_recovery_gap",
    "poll_slot_id",
    "tick_once",
]
