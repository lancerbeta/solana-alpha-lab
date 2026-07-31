"""Deterministic TASK-21 real-candidate nomination policy evaluator.

The evaluator is pure and provider-free. Synthetic acceptance proves ordering
and state transitions but cannot create a real nomination or watchlist member.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

TASK_ID = "TASK-21"
ATOM_ID = "T21-A6R_FROZEN_REAL_NOMINATION_POLICY_V1"
HYPOTHESIS_ID = "HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1"
POLICY_VERSION = "1.0"
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
FORBIDDEN_NOMINATION_KEYS = frozenset(
    {
        "alpha",
        "costbps",
        "pnl",
        "price",
        "profit",
        "quoteoutput",
        "quotestatus",
        "return",
        "roi",
        "routeavailable",
        "score",
        "sharpe",
        "terminalclass",
        "tokenrank",
    }
)
FORBIDDEN_SELECTION_CODE_FRAGMENTS = frozenset(
    {
        "alpha",
        "cost",
        "pnl",
        "price",
        "profit",
        "quoteoutput",
        "quotestatus",
        "rank",
        "return",
        "roi",
        "route",
        "score",
        "sharpe",
        "terminal",
    }
)


class NominationPolicyError(RuntimeError):
    """The frozen nomination policy or input contract was violated."""


@dataclass(frozen=True, slots=True)
class NominationEvaluation:
    """Canonical evaluation bytes and decoded convenience access."""

    receipt_bytes: bytes

    @property
    def receipt(self) -> dict[str, Any]:
        return json.loads(self.receipt_bytes)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise NominationPolicyError("value_must_be_canonical_json") from exc


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise NominationPolicyError("yaml_document_must_be_mapping")
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise NominationPolicyError("json_document_must_be_mapping")
    return value


def _aware_utc(name: str, value: object) -> datetime:
    if not isinstance(value, str):
        raise NominationPolicyError(f"{name}_must_be_text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise NominationPolicyError(f"{name}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise NominationPolicyError(f"{name}_must_be_timezone_aware")
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _validate_sha256(name: str, value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise NominationPolicyError(f"{name}_invalid")
    return value


def _normalized_key(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _reject_forbidden_nomination_fields(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise NominationPolicyError("nomination_key_must_be_text")
            if _normalized_key(key) in FORBIDDEN_NOMINATION_KEYS:
                raise NominationPolicyError("outcome_dependent_nomination_field")
            _reject_forbidden_nomination_fields(item)
    elif isinstance(value, list):
        for item in value:
            _reject_forbidden_nomination_fields(item)


def _decode_base58(value: str) -> bytes | None:
    number = 0
    for character in value:
        index = BASE58_ALPHABET.find(character)
        if index < 0:
            return None
        number = number * 58 + index
    width = (number.bit_length() + 7) // 8
    payload = number.to_bytes(width, "big") if width else b""
    leading_zeros = len(value) - len(value.lstrip("1"))
    return b"\x00" * leading_zeros + payload


def _valid_solana_pubkey(value: object) -> bool:
    if not isinstance(value, str) or not 32 <= len(value) <= 44:
        return False
    decoded = _decode_base58(value)
    return decoded is not None and len(decoded) == 32


def validate_config(config: Mapping[str, Any], repo_root: Path) -> None:
    if (
        config.get("task_id") != TASK_ID
        or config.get("atom_id") != ATOM_ID
        or config.get("policy_version") != POLICY_VERSION
        or config.get("status") != "FROZEN_POLICY_NO_REAL_NOMINATIONS"
    ):
        raise NominationPolicyError("config_identity_or_status_drift")
    entry = config.get("entry_gate")
    if (
        not isinstance(entry, Mapping)
        or entry.get("verdict") != "START_WITH_PATCH"
        or entry.get("patch", {}).get("actual_candidate_selection_in_atom")
        is not False
    ):
        raise NominationPolicyError("entry_patch_invalid")
    supply = config.get("supply")
    if (
        not isinstance(supply, Mapping)
        or supply.get("maximum_evaluated_nominations") != 8
        or supply.get("minimum_active_members_for_dataset_sufficiency") != 5
        or supply.get("maximum_active_members") != 8
    ):
        raise NominationPolicyError("supply_bounds_drift")
    tranches = config.get("tranches")
    if not isinstance(tranches, Mapping):
        raise NominationPolicyError("tranche_policy_missing")
    tranche_rows = tranches.get("order")
    expected = [
        {
            "tranche_id": "T1",
            "start_day_inclusive": 0,
            "end_day_exclusive": 7,
            "active_member_cap": 3,
        },
        {
            "tranche_id": "T2",
            "start_day_inclusive": 7,
            "end_day_exclusive": 14,
            "active_member_cap": 3,
        },
        {
            "tranche_id": "T3",
            "start_day_inclusive": 14,
            "end_day_exclusive": 21,
            "active_member_cap": 2,
        },
    ]
    if tranche_rows != expected or tranches.get(
        "unused_tranche_capacity_transfer_allowed"
    ) is not False:
        raise NominationPolicyError("tranche_policy_drift")
    authority = config.get("authority")
    if not isinstance(authority, Mapping):
        raise NominationPolicyError("authority_missing")
    zero_fields = (
        "network_calls",
        "provider_api_rpc_wss_calls",
        "drive_reads",
        "drive_writes",
        "credential_use",
        "real_candidate_nominations",
        "real_candidate_admissions",
        "live_collector_executions",
        "forward_raw_or_dataset_writes",
        "provider_credits",
        "cash_spend_usd_cents",
        "dependency_changes",
    )
    if any(authority.get(field) != 0 for field in zero_fields):
        raise NominationPolicyError("local_authority_external_value_nonzero")
    if authority.get("scheduler_or_background_process") is not False:
        raise NominationPolicyError("scheduler_not_authorized")
    frozen = config.get("frozen_inputs")
    if not isinstance(frozen, list) or not frozen:
        raise NominationPolicyError("frozen_inputs_missing")
    for item in frozen:
        if not isinstance(item, Mapping) or not isinstance(item.get("path"), str):
            raise NominationPolicyError("frozen_input_invalid")
        expected_hash = _validate_sha256(
            "frozen_input_sha256", item.get("sha256")
        )
        actual_hash = sha256_file(repo_root / item["path"])
        if actual_hash != expected_hash:
            raise NominationPolicyError(
                f"frozen_input_hash_drift:{item['path']}:{expected_hash}:{actual_hash}"
            )


def _deduplicate_events(events: object, maximum: int) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(events, list) or not 1 <= len(events) <= maximum:
        raise NominationPolicyError("nomination_count_outside_bounds")
    accepted: dict[str, tuple[bytes, dict[str, Any]]] = {}
    duplicate_count = 0
    for raw in events:
        if not isinstance(raw, dict):
            raise NominationPolicyError("nomination_event_must_be_mapping")
        identity = raw.get("nomination_event_id")
        if not isinstance(identity, str) or not identity:
            raise NominationPolicyError("nomination_event_id_invalid")
        encoded = canonical_json_bytes(raw)
        previous = accepted.get(identity)
        if previous is None:
            accepted[identity] = (encoded, raw)
        elif previous[0] == encoded:
            duplicate_count += 1
        else:
            raise NominationPolicyError("conflicting_duplicate_nomination_event")
    if len(accepted) > maximum:
        raise NominationPolicyError("unique_nomination_count_exceeds_cap")
    return [item[1] for item in accepted.values()], duplicate_count


def _validate_batch_identity(
    batch: Mapping[str, Any],
    config: Mapping[str, Any],
) -> tuple[datetime, dict[str, datetime]]:
    if (
        batch.get("task_id") != TASK_ID
        or batch.get("atom_id") != ATOM_ID
        or batch.get("synthetic_only") is not True
        or batch.get("contains_market_data") is not False
        or batch.get("hypothesis_outcome_unsealed") is not False
    ):
        raise NominationPolicyError("batch_identity_or_scope_invalid")
    anchor = _aware_utc("anchor_at", batch.get("anchor_at"))
    closes_raw = batch.get("tranche_closed_at")
    if not isinstance(closes_raw, Mapping) or set(closes_raw) != {"T1", "T2", "T3"}:
        raise NominationPolicyError("tranche_close_map_invalid")
    closes = {
        tranche_id: _aware_utc(
            f"{tranche_id}_closed_at", closes_raw[tranche_id]
        )
        for tranche_id in closes_raw
    }
    for row in config["tranches"]["order"]:
        expected = anchor + timedelta(days=row["end_day_exclusive"])
        if closes[row["tranche_id"]] != expected:
            raise NominationPolicyError("tranche_close_time_drift")
    return anchor, closes


def _validate_event_contract(
    event: Mapping[str, Any],
    config: Mapping[str, Any],
) -> None:
    required_root = set(config["nomination_event"]["required_root_fields"])
    if set(event) != required_root:
        raise NominationPolicyError("nomination_root_fields_drift")
    _validate_sha256("source_content_sha256", event["source_content_sha256"])
    if (
        event["hypothesis_version_id"] != HYPOTHESIS_ID
        or event["watchlist_policy_version"] != POLICY_VERSION
    ):
        raise NominationPolicyError("hypothesis_or_policy_binding_drift")
    for field in (
        "source_asset_id",
        "source_version",
        "evidence_checkpoint",
    ):
        if not isinstance(event[field], str) or not event[field]:
            raise NominationPolicyError(f"{field}_invalid")
    reason_codes = event["reason_codes"]
    if (
        not isinstance(reason_codes, list)
        or not reason_codes
        or len(reason_codes) > config["nomination_event"]["maximum_reason_codes"]
        or any(not isinstance(item, str) or not item for item in reason_codes)
    ):
        raise NominationPolicyError("reason_codes_invalid")
    inputs = event["exact_rule_input_values"]
    if (
        not isinstance(inputs, Mapping)
        or set(inputs)
        != set(config["nomination_event"]["required_exact_rule_input_fields"])
    ):
        raise NominationPolicyError("exact_rule_input_fields_drift")
    basis = inputs["selection_basis_codes"]
    if (
        not isinstance(basis, list)
        or not basis
        or len(basis)
        > config["nomination_event"]["maximum_selection_basis_codes"]
        or any(not isinstance(item, str) or not item for item in basis)
    ):
        raise NominationPolicyError("selection_basis_codes_invalid")
    if any(
        forbidden in _normalized_key(code)
        for code in basis
        for forbidden in FORBIDDEN_SELECTION_CODE_FRAGMENTS
    ):
        raise NominationPolicyError("outcome_dependent_selection_basis_code")
    if (
        not isinstance(inputs["prior_relevant_quote_outcome_exposure"], bool)
        or not isinstance(inputs["uses_task21_quote_route_or_price_outcome"], bool)
        or not isinstance(inputs["source_observation_id"], str)
        or not inputs["source_observation_id"]
    ):
        raise NominationPolicyError("rule_input_type_invalid")
    _reject_forbidden_nomination_fields(event)


def _member_identity(
    *,
    policy_id: str,
    nomination_event_id: str,
    mint: str,
) -> str:
    claim = {
        "mint": mint,
        "nomination_event_id": nomination_event_id,
        "policy_id": policy_id,
        "policy_version": POLICY_VERSION,
    }
    return f"T21-WATCH-{sha256_bytes(canonical_json_bytes(claim))[:20]}"


def evaluate_offline_batch(
    *,
    repo_root: Path,
    config_path: Path,
    batch_path: Path,
    batch_override: Mapping[str, Any] | None = None,
) -> NominationEvaluation:
    """Evaluate a synthetic nomination batch without creating real members."""

    config = load_yaml(config_path)
    validate_config(config, repo_root)
    batch = (
        deepcopy(batch_override)
        if batch_override is not None
        else load_json(batch_path)
    )
    anchor, tranche_closes = _validate_batch_identity(batch, config)
    events, exact_duplicates = _deduplicate_events(
        batch.get("nomination_events"),
        config["supply"]["maximum_evaluated_nominations"],
    )
    tranche_policy = {
        row["tranche_id"]: row for row in config["tranches"]["order"]
    }
    events_by_tranche: dict[str, list[dict[str, Any]]] = {
        tranche_id: [] for tranche_id in tranche_policy
    }
    for event in events:
        _validate_event_contract(event, config)
        tranche_id = event["exact_rule_input_values"]["tranche_id"]
        if tranche_id not in events_by_tranche:
            raise NominationPolicyError("tranche_id_invalid")
        events_by_tranche[tranche_id].append(event)

    evaluations: list[dict[str, Any]] = []
    memberships: list[dict[str, Any]] = []
    seen_mints: set[str] = set()
    source_counts: Counter[str] = Counter()
    state_counts: Counter[str] = Counter()
    active_by_tranche: Counter[str] = Counter()
    allowed_sources = set(config["supply"]["allowed_source_classes"])
    reference_assets = set(config["eligibility"]["reference_assets_excluded"])

    for tranche_id in ("T1", "T2", "T3"):
        row = tranche_policy[tranche_id]
        start = anchor + timedelta(days=row["start_day_inclusive"])
        close = tranche_closes[tranche_id]
        ordered = sorted(
            events_by_tranche[tranche_id],
            key=lambda item: (
                _aware_utc(
                    "first_reliable_available_at",
                    item["first_reliable_available_at"],
                ),
                _aware_utc("observed_at", item["observed_at"]),
                item["nomination_event_id"],
            ),
        )
        for event in ordered:
            inputs = event["exact_rule_input_values"]
            mint = inputs["mint"]
            observed = _aware_utc("observed_at", event["observed_at"])
            reliable = _aware_utc(
                "first_reliable_available_at",
                event["first_reliable_available_at"],
            )
            reasons: list[str] = []
            state = "WATCHLIST_ACTIVE"
            if reliable < observed:
                raise NominationPolicyError(
                    "first_reliable_available_before_observed"
                )
            if not start <= observed < close or reliable > close:
                state = "EVALUATED_REJECTED"
                reasons.append("OUTSIDE_DECLARED_TRANCHE")
            if not isinstance(mint, str) or not _valid_solana_pubkey(mint):
                state = "EVALUATED_REJECTED"
                reasons.append("INVALID_SOLANA_MINT")
            elif mint in seen_mints:
                state = "EVALUATED_REJECTED"
                reasons.append("DUPLICATE_MINT_FIRST_NOMINATION_WINS")
            seen_mints.add(mint) if isinstance(mint, str) else None
            source_class = inputs["nomination_source_class"]
            if source_class not in allowed_sources:
                state = "EVALUATED_REJECTED"
                reasons.append("SOURCE_CLASS_NOT_ALLOWED")
            else:
                source_counts[source_class] += 1
            decimals = inputs["mint_decimals"]
            if decimals is None and state == "WATCHLIST_ACTIVE":
                state = "EVALUATED_NOT_EVALUABLE"
                reasons.append("MINT_DECIMALS_UNKNOWN")
            elif (
                decimals is not None
                and (
                    isinstance(decimals, bool)
                    or not isinstance(decimals, int)
                    or not 0 <= decimals <= 30
                )
            ):
                raise NominationPolicyError("mint_decimals_invalid")
            if mint in reference_assets:
                state = "EVALUATED_REJECTED"
                reasons.append("REFERENCE_ASSET_EXCLUDED")
            if inputs["prior_relevant_quote_outcome_exposure"]:
                state = "EVALUATED_REJECTED"
                reasons.append("PRIOR_RELEVANT_QUOTE_OUTCOME_EXPOSURE")
            if inputs["uses_task21_quote_route_or_price_outcome"]:
                state = "EVALUATED_REJECTED"
                reasons.append("OUTCOME_DEPENDENT_SELECTION_FORBIDDEN")
            if (
                state == "WATCHLIST_ACTIVE"
                and active_by_tranche[tranche_id] >= row["active_member_cap"]
            ):
                state = "EVALUATED_REJECTED"
                reasons.append("TRANCHE_ACTIVE_MEMBER_CAP_REACHED")
            if state == "WATCHLIST_ACTIVE":
                active_by_tranche[tranche_id] += 1
                member_id = _member_identity(
                    policy_id=config["policy_id"],
                    nomination_event_id=event["nomination_event_id"],
                    mint=mint,
                )
                memberships.append(
                    {
                        "member_id": member_id,
                        "mint": mint,
                        "mint_decimals": decimals,
                        "nomination_event_id": event["nomination_event_id"],
                        "hypothesis_version_id": HYPOTHESIS_ID,
                        "policy_version": POLICY_VERSION,
                        "entered_at": _utc_text(close),
                        "exited_at": None,
                        "first_reliable_available_at": _utc_text(close),
                        "reason_codes": ["POLICY_ELIGIBLE_PREOUTCOME_NOMINATION"],
                        "evidence_checkpoint": event["evidence_checkpoint"],
                    }
                )
                reasons.append("POLICY_ELIGIBLE_PREOUTCOME_NOMINATION")
            state_counts[state] += 1
            evaluations.append(
                {
                    "nomination_event_id": event["nomination_event_id"],
                    "mint": mint,
                    "tranche_id": tranche_id,
                    "evaluation_state": state,
                    "reason_codes": reasons,
                }
            )

    active_tranches = sum(active_by_tranche[item] > 0 for item in ("T1", "T2", "T3"))
    synthetically_sufficient = (
        len(memberships)
        >= config["supply"]["minimum_active_members_for_dataset_sufficiency"]
        and active_tranches
        >= config["tranches"][
            "minimum_distinct_active_tranches_for_dataset_sufficiency"
        ]
    )
    receipt = {
        "schema": "smial.task21.real-nomination-policy-offline-receipt",
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "atom_id": ATOM_ID,
        "policy_id": config["policy_id"],
        "policy_version": POLICY_VERSION,
        "status": "PASS",
        "synthetic_only": True,
        "contains_market_data": False,
        "config_sha256": sha256_file(config_path),
        "batch_sha256": sha256_file(batch_path),
        "ordering": [
            "tranche_id",
            "first_reliable_available_at",
            "observed_at",
            "nomination_event_id",
        ],
        "evaluated_nominations": len(events),
        "exact_duplicate_events_deduplicated": exact_duplicates,
        "state_counts": dict(sorted(state_counts.items())),
        "active_members": len(memberships),
        "active_members_by_tranche": {
            item: active_by_tranche[item] for item in ("T1", "T2", "T3")
        },
        "active_tranches": active_tranches,
        "synthetic_dataset_population_sufficient": synthetically_sufficient,
        "source_class_counts": dict(sorted(source_counts.items())),
        "evaluations": evaluations,
        "membership_events": memberships,
        "real_world_state": {
            "real_candidate_nominations_created": 0,
            "real_candidate_admissions_created": 0,
            "real_watchlist_member_count": 0,
            "real_collection_authorized": False,
        },
        "actual_actions": {
            "network_calls": 0,
            "provider_api_rpc_wss_calls": 0,
            "drive_reads": 0,
            "drive_writes": 0,
            "credential_use": 0,
            "provider_credits": 0,
            "cash_spend_usd_cents": 0,
            "scheduler_or_background_process": False,
            "wallet_signer_transaction_actions": 0,
        },
        "non_claims": [
            "NO_REAL_TOKEN_SELECTED",
            "NO_REAL_TASK21_NOMINATION_OR_MEMBER_CREATED",
            "NO_PROVIDER_ROUTE_AVAILABILITY_PRECHECK",
            "NO_FORWARD_COLLECTION_STARTED",
            "NO_HYPOTHESIS_OUTCOME_UNSEALED",
            "NO_A7_CATALOG_TRANSACTION",
        ],
        "next_boundary": {
            "atom_id": "T21-A6S_BOUNDED_REAL_NOMINATION_AND_COLLECTION_LAUNCH_V1",
            "authorized": False,
            "real_candidate_input_required": True,
            "external_authority_required": True,
        },
    }
    return NominationEvaluation(receipt_bytes=canonical_json_bytes(receipt) + b"\n")
