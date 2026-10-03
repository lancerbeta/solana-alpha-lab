"""Append-only Forge research-universe policy.

ResearchStore owns the active profile. Git owns this validator. A missing
or invalid profile does not mean unfiltered search.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from solana_alpha_lab.factory.hfic_clock import (
    Clock,
    HficClockError,
    capture_stage_time,
    render_canonical_utc,
)
from solana_alpha_lab.factory.research_store import (
    RecordKind,
    ResearchEvent,
    ResearchStore,
    ResearchStoreError,
)
from solana_alpha_lab.factory.run_passport import canonical_sha256


SCHEMA = "smial.forge-research-universe-policy"
SCHEMA_VERSION = "1.0"
ARTIFACT_KIND = "FORGE_RESEARCH_UNIVERSE_POLICY"
HOLDER_FIELD_ID = "FIELD-HOLDER-COUNT-001"
LIQUIDITY_FIELD_ID = "FIELD-LIQUIDITY-USD-001"
GENESIS_HEAD_SHA256 = "0" * 64
REASON_OWNER_ACTIVATION = "OWNER_UNIVERSE_ACTIVATION"
STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_UNKNOWN = "UNKNOWN"
PRODUCER = "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"
NO_CHANGE = "NO_CHANGE"
APPENDED = "APPENDED"


class UniversePolicyError(ValueError):
    """Fail-closed research-universe policy error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _authority_zero() -> dict[str, int]:
    return {
        "git_mutation": 0,
        "experiment_execution": 0,
        "provider_api_rpc_wss_calls": 0,
    }


def canonical_number(value: object, *, integer: bool) -> str:
    """Lossless canonical text. 5000 and 5000.0 match; a finer fraction does not."""

    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise UniversePolicyError("UNIVERSE_POLICY_INVALID")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise UniversePolicyError("UNIVERSE_POLICY_INVALID") from exc
    if not number.is_finite() or number < 0:
        raise UniversePolicyError("UNIVERSE_POLICY_INVALID")
    if integer and number != number.to_integral_value():
        raise UniversePolicyError("UNIVERSE_POLICY_INVALID")
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def profile_definition(min_holders: object, min_liquidity_usd: object) -> dict[str, str]:
    return {
        "holder_field_id": HOLDER_FIELD_ID,
        "liquidity_field_id": LIQUIDITY_FIELD_ID,
        "min_holders": canonical_number(min_holders, integer=True),
        "min_liquidity_usd": canonical_number(min_liquidity_usd, integer=False),
        "rule": "ALL_OF_AT_DECISION_TIME",
    }


def semantic_sha256(definition: Mapping[str, Any]) -> str:
    body = profile_definition(definition.get("min_holders"), definition.get("min_liquidity_usd"))
    if any(definition.get(key) != body[key] for key in body):
        raise UniversePolicyError("UNIVERSE_POLICY_INVALID")
    return canonical_sha256(body)


def _check_cell(cell: Mapping[str, Any], minimum: str, *, below: str, unknown: str) -> tuple[str, str]:
    if str(cell.get("status") or "") == "OBSERVED":
        try:
            observed = Decimal(str(cell.get("value")))
        except (InvalidOperation, ValueError) as exc:
            raise UniversePolicyError("UNIVERSE_POLICY_INVALID") from exc
        if not observed.is_finite():
            return STATUS_UNKNOWN, unknown
        if observed < Decimal(minimum):
            return STATUS_FAIL, below
        return STATUS_PASS, ""
    return STATUS_UNKNOWN, unknown


def classify_universe_cells(
    holder_cell: Mapping[str, Any],
    liquidity_cell: Mapping[str, Any],
    definition: Mapping[str, Any],
) -> dict[str, Any]:
    """One terminal status. A confirmed fail wins over an unknown check."""

    body = profile_definition(definition.get("min_holders"), definition.get("min_liquidity_usd"))
    holder_status, holder_reason = _check_cell(
        holder_cell,
        body["min_holders"],
        below="HOLDER_BELOW_MIN",
        unknown="HOLDER_UNKNOWN",
    )
    liquidity_status, liquidity_reason = _check_cell(
        liquidity_cell,
        body["min_liquidity_usd"],
        below="LIQUIDITY_BELOW_MIN",
        unknown="LIQUIDITY_UNKNOWN",
    )
    reasons = [item for item in (holder_reason, liquidity_reason) if item]
    if STATUS_FAIL in (holder_status, liquidity_status):
        status = STATUS_FAIL
    elif STATUS_UNKNOWN in (holder_status, liquidity_status):
        status = STATUS_UNKNOWN
    else:
        status = STATUS_PASS
    return {"status": status, "reasons": reasons}


def claim_fields(result: Mapping[str, Any] | None) -> dict[str, str]:
    """Card labels that must match a saved result. Empty for a legacy result."""

    if not isinstance(result, Mapping):
        return {}
    policy = result.get("universe_policy")
    if not isinstance(policy, Mapping) or not policy.get("semantic_sha256"):
        return {}
    return {
        "universe_policy_semantic_sha256": str(policy["semantic_sha256"]),
        "min_holders": str(policy["min_holders"]),
        "min_liquidity_usd": str(policy["min_liquidity_usd"]),
    }


def admitted_with_policy(admitted: Mapping[str, Any], definition: Mapping[str, Any] | None) -> dict[str, Any]:
    body = dict(admitted)
    if definition is None:
        return body
    body["universe_policy_semantic_sha256"] = semantic_sha256(definition)
    return body


def recipe_policy(recipe: Mapping[str, Any] | None) -> dict[str, str] | None:
    """Exact snapshot from a frozen recipe. Absence is the legacy population."""

    if not isinstance(recipe, Mapping) or "universe_policy" not in recipe:
        return None
    raw = recipe.get("universe_policy")
    if not isinstance(raw, Mapping):
        raise UniversePolicyError("UNIVERSE_POLICY_BINDING_MISMATCH")
    definition = profile_definition(raw.get("min_holders"), raw.get("min_liquidity_usd"))
    if str(raw.get("semantic_sha256") or "") != semantic_sha256(definition):
        raise UniversePolicyError("UNIVERSE_POLICY_BINDING_MISMATCH")
    if raw.get("holder_field_id") not in (None, HOLDER_FIELD_ID):
        raise UniversePolicyError("UNIVERSE_POLICY_BINDING_MISMATCH")
    if raw.get("liquidity_field_id") not in (None, LIQUIDITY_FIELD_ID):
        raise UniversePolicyError("UNIVERSE_POLICY_BINDING_MISMATCH")
    return definition


def _payload(record: Any) -> dict[str, Any]:
    raw = getattr(record, "payload_json", "") or ""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def load_policy_records(store: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for record in store.iter_committed_records():
        if str(getattr(record, "record_kind", "")) != RecordKind.RESEARCH_ARTIFACT.value:
            continue
        payload = _payload(record)
        if payload.get("artifact_kind") != ARTIFACT_KIND:
            continue
        if payload.get("schema") != SCHEMA:
            continue
        found.append(payload)
    found.sort(key=lambda item: int(item.get("policy_sequence") or 0))
    return found


def effective_policy(store: Any) -> dict[str, Any]:
    records = load_policy_records(store)
    if not records:
        return {
            "state": "ABSENT",
            "definition": None,
            "semantic_sha256": None,
            "policy_head_sha256": GENESIS_HEAD_SHA256,
            "policy_sequence": 0,
            "next_action": "PREVIEW_THEN_AUTHORIZED_APPLY",
        }
    head = records[-1]
    definition = profile_definition(
        (head.get("definition") or {}).get("min_holders"),
        (head.get("definition") or {}).get("min_liquidity_usd"),
    )
    if str(head.get("semantic_sha256") or "") != semantic_sha256(definition):
        raise UniversePolicyError("UNIVERSE_POLICY_BINDING_MISMATCH")
    return {
        "state": "ACTIVE",
        "definition": definition,
        "semantic_sha256": head["semantic_sha256"],
        "policy_head_sha256": head["policy_sha256"],
        "policy_sequence": int(head.get("policy_sequence") or 0),
        "reason_code": head.get("reason_code"),
        "next_action": "NEW_FORGE_RUNS_USE_THIS_PROFILE",
    }


def _open_operations(store: Any) -> list[dict[str, Any]]:
    from solana_alpha_lab.factory.hfic_ordinary_operation import list_operations

    latest: dict[str, dict[str, Any]] = {}
    for item in list_operations(store):
        digest = str(item.get("operation_sha256") or "")
        previous = latest.get(digest)
        if previous is None or str(item.get("_recorded_at") or "") >= str(previous.get("_recorded_at") or ""):
            latest[digest] = item
    return [item for item in latest.values() if item.get("status") == "OPEN"]


def _deny_pending(store: Any) -> None:
    if _open_operations(store):
        raise UniversePolicyError("UNIVERSE_POLICY_PENDING_OPERATION")


def _deny_exhausted_preview(store: Any) -> None:
    from solana_alpha_lab.factory.hfic_ordinary_operation import owner_allowance

    for operation in _open_operations(store):
        if owner_allowance(store, operation, "preview") < 1:
            raise UniversePolicyError("OWNER_CAP_EXHAUSTED")


def status_payload(store: Any) -> dict[str, Any]:
    head = effective_policy(store)
    definition = head.get("definition") or {}
    return {
        "action": "UNIVERSE_POLICY_STATUS",
        "state": head["state"],
        "min_holders": definition.get("min_holders"),
        "min_liquidity_usd": definition.get("min_liquidity_usd"),
        "holder_field_id": HOLDER_FIELD_ID,
        "liquidity_field_id": LIQUIDITY_FIELD_ID,
        "semantic_sha256": head.get("semantic_sha256"),
        "policy_head_sha256": head["policy_head_sha256"],
        "policy_sequence": head["policy_sequence"],
        "next_action": head["next_action"],
        "claim_boundary": "Thresholds are owner market-scale settings, not a return result and not strategy promotion.",
        "authority": _authority_zero(),
        "writes": {"research_store": 0},
    }


def _proposal(
    store: Any,
    *,
    min_holders: object,
    min_liquidity_usd: object,
) -> dict[str, Any]:
    head = effective_policy(store)
    definition = profile_definition(min_holders, min_liquidity_usd)
    proposal = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "base_policy_head_sha256": head["policy_head_sha256"],
        "base_store_inventory_digest": store.diagnostics().committed_inventory_sha256,
        "definition": definition,
        "semantic_sha256": semantic_sha256(definition),
        "reason_code": REASON_OWNER_ACTIVATION,
    }
    proposal["proposal_sha256"] = canonical_sha256(proposal)
    return proposal


def preview_universe_policy(
    store: Any,
    *,
    min_holders: object,
    min_liquidity_usd: object,
    counts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if counts is not None:
        _deny_exhausted_preview(store)
    head = effective_policy(store)
    proposal = _proposal(store, min_holders=min_holders, min_liquidity_usd=min_liquidity_usd)
    definition = proposal["definition"]
    before = head.get("definition") or {}
    return {
        "action": "UNIVERSE_POLICY_PREVIEW",
        "status": "NO_CHANGE" if proposal["semantic_sha256"] == head.get("semantic_sha256") else "PROPOSED",
        "before": {
            "min_holders": before.get("min_holders"),
            "min_liquidity_usd": before.get("min_liquidity_usd"),
            "semantic_sha256": head.get("semantic_sha256"),
        },
        "after": {
            "min_holders": definition["min_holders"],
            "min_liquidity_usd": definition["min_liquidity_usd"],
            "semantic_sha256": proposal["semantic_sha256"],
        },
        "counts": dict(counts) if counts is not None else None,
        "counts_read_future_outcomes": False,
        "proposal": proposal,
        "proposal_sha256": proposal["proposal_sha256"],
        "expected_policy_head_sha256": head["policy_head_sha256"],
        "claim_boundary": "Coverage is eligibility only. It is not a ranked profile and not a market-quality verdict.",
        "next_action": "AUTHORIZED_APPLY" if proposal["semantic_sha256"] != head.get("semantic_sha256") else "READ_ACTIVE_PROFILE",
        "authority": _authority_zero(),
        "writes": {"research_store": 0},
    }


def apply_universe_policy(
    store: ResearchStore,
    *,
    repo_root: Any,
    proposal: Mapping[str, Any],
    confirm_append_only: bool,
    clock: Clock | None = None,
) -> dict[str, Any]:
    if not confirm_append_only:
        raise UniversePolicyError("UNIVERSE_POLICY_CONFIRM_REQUIRED")
    expected = dict(proposal)
    observed_hash = expected.pop("proposal_sha256", None)
    if canonical_sha256(expected) != observed_hash:
        raise UniversePolicyError("UNIVERSE_POLICY_INVALID")
    if expected.get("reason_code") != REASON_OWNER_ACTIVATION:
        raise UniversePolicyError("UNIVERSE_POLICY_INVALID")
    definition = profile_definition(
        (expected.get("definition") or {}).get("min_holders"),
        (expected.get("definition") or {}).get("min_liquidity_usd"),
    )
    if expected.get("definition") != definition:
        raise UniversePolicyError("UNIVERSE_POLICY_INVALID")
    if expected.get("semantic_sha256") != semantic_sha256(definition):
        raise UniversePolicyError("UNIVERSE_POLICY_INVALID")
    head = effective_policy(store)
    inventory = store.diagnostics().committed_inventory_sha256
    if expected.get("base_policy_head_sha256") != head["policy_head_sha256"]:
        raise UniversePolicyError("UNIVERSE_POLICY_PREVIEW_STALE")
    if expected.get("base_store_inventory_digest") != inventory:
        raise UniversePolicyError("UNIVERSE_POLICY_PREVIEW_STALE")
    if head.get("semantic_sha256") == expected["semantic_sha256"]:
        return {
            "action": "UNIVERSE_POLICY_APPLY",
            "status": NO_CHANGE,
            "appended": False,
            "semantic_sha256": head.get("semantic_sha256"),
            "policy_head_sha256": head["policy_head_sha256"],
            "min_holders": definition["min_holders"],
            "min_liquidity_usd": definition["min_liquidity_usd"],
            "authority": _authority_zero(),
            "writes": {"research_store": 0},
        }
    _deny_pending(store)
    try:
        now = capture_stage_time(clock)
        created_at = render_canonical_utc(now)
    except HficClockError as exc:
        raise UniversePolicyError(str(exc)) from exc
    from solana_alpha_lab.factory.document_runner import repository_git_snapshot

    git = repository_git_snapshot(repo_root)
    sequence = int(head.get("policy_sequence") or 0) + 1
    unsigned = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "policy_id": f"FORGE-UNIVERSE-{sequence:04d}",
        "policy_sequence": sequence,
        "previous_policy_sha256": head["policy_head_sha256"],
        "definition": definition,
        "semantic_sha256": expected["semantic_sha256"],
        "reason_code": REASON_OWNER_ACTIVATION,
        "created_at": created_at,
        "producer_git_sha": git.head_sha.lower(),
        "authority": _authority_zero(),
        "non_claims": [
            "NOT_A_RETURN_OPTIMUM",
            "NOT_STRATEGY_PROMOTION",
            "NOT_A_NEW_SCIENTIFIC_LOOK",
            "NEW_FORGE_OPERATIONS_ONLY",
        ],
    }
    policy_sha = canonical_sha256(unsigned)
    body = {**unsigned, "policy_sha256": policy_sha}
    record_id = f"FORGE-UNIVERSE-{policy_sha[:16].upper()}"
    transaction_id = f"RESEARCH-TXN-FORGE-UNIVERSE-{sequence:04d}"
    artifact = {
        "research_artifact_id": record_id,
        "artifact_kind": ARTIFACT_KIND,
        **body,
    }
    encoded = json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    event = ResearchEvent(
        record_id=record_id,
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=record_id,
        hypothesis_version_id=None,
        run_id=None,
        transaction_id=transaction_id,
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=encoded,
        payload_sha256=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id=PRODUCER,
        producer_git_sha=git.head_sha.lower(),
        created_at=now,
    )
    try:
        store.append([event], transaction_id=transaction_id)
    except ResearchStoreError as exc:
        raise UniversePolicyError(str(exc)) from exc
    store.rebuild_projection()
    return {
        "action": "UNIVERSE_POLICY_APPLY",
        "status": APPENDED,
        "appended": True,
        "semantic_sha256": definition and expected["semantic_sha256"],
        "policy_head_sha256": policy_sha,
        "policy_sequence": sequence,
        "min_holders": definition["min_holders"],
        "min_liquidity_usd": definition["min_liquidity_usd"],
        "created_at": created_at,
        "authority": _authority_zero(),
        "writes": {"research_store": 1},
    }


def ensure_profile(
    store: ResearchStore,
    *,
    repo_root: Any,
    min_holders: object,
    min_liquidity_usd: object,
) -> dict[str, Any]:
    """Preview and apply through the production owner. Same values are a readback."""

    wanted = profile_definition(min_holders, min_liquidity_usd)
    current = effective_policy(store)
    if current.get("semantic_sha256") == semantic_sha256(wanted):
        return {
            "action": "UNIVERSE_POLICY_APPLY",
            "status": NO_CHANGE,
            "semantic_sha256": current["semantic_sha256"],
            "min_holders": wanted["min_holders"],
            "min_liquidity_usd": wanted["min_liquidity_usd"],
        }
    preview = preview_universe_policy(
        store,
        min_holders=wanted["min_holders"],
        min_liquidity_usd=wanted["min_liquidity_usd"],
    )
    return apply_universe_policy(
        store,
        repo_root=repo_root,
        proposal=preview["proposal"],
        confirm_append_only=True,
    )


def snapshot(definition: Mapping[str, Any]) -> dict[str, str]:
    body = profile_definition(definition.get("min_holders"), definition.get("min_liquidity_usd"))
    return {**body, "semantic_sha256": semantic_sha256(body)}
