"""Offline MEU reproject for early-path H900 Failed-to-get-quotes bodies."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.ordinary_recent_early_path_h900_audition import (
    ATOM_ID as EARLY_PATH_ATOM_ID,
    CLOSE_TERMINAL,
    score_audition,
)
from solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition import (
    MARKET_EXECUTION_UNAVAILABLE,
    QUOTE_OBSERVED,
    UNKNOWN_TYPED_FAILURE,
)
from solana_alpha_lab.quote_native_evidence_fit_panel import project_quote

ATOM_ID = "ORDINARY_RECENT_EARLY_PATH_H900_FAILED_QUOTES_MEU_REPROJECT_V1"
POLICY_SCHEMA = "smial.ordinary-recent-early-path-h900-failed-quotes-meu-reproject"
RECEIPT_SCHEMA = "smial.ordinary-recent-early-path-h900-failed-quotes-meu-reproject.runtime-receipt"
ACCEPTANCE_SCHEMA = "smial.ordinary-recent-early-path-h900-failed-quotes-meu-reproject.acceptance"
FAILED_QUOTES_MESSAGE = "FAILED TO GET QUOTES"


class FailedQuotesMeuError(ValueError):
    """Bounded offline reproject cannot be satisfied."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise FailedQuotesMeuError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    _require(all(type(key) is str for key in value), code)
    return value


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def validate_policy(policy: Mapping[str, Any], *, root: Path) -> None:
    _require(policy.get("schema") == POLICY_SCHEMA, "POLICY_SCHEMA_DRIFT")
    _require(policy.get("atom_id") == ATOM_ID, "ATOM_DRIFT")
    authority = _mapping(policy.get("external_authority"), "AUTHORITY_INVALID")
    _require(authority.get("capture_authorized") is False, "CAPTURE_MUST_STAY_FALSE")
    _require(authority.get("provider_api_rpc_wss_calls") is False, "PROVIDER_MUST_STAY_FALSE")
    _require(authority.get("credential_reads") is False, "CREDENTIAL_READ_NOT_FORBIDDEN")
    _require(authority.get("dotenv_reads") is False, "DOTENV_READ_NOT_FORBIDDEN")
    _require(int(authority.get("cash_cap_usd_cents", -1)) == 0, "CASH_CAP_DRIFT")
    bindings = _mapping(policy.get("bindings"), "BINDINGS_INVALID")
    receipt_rel = str(bindings.get("source_runtime_receipt") or "")
    fixtures_rel = str(bindings.get("fixture_index") or "")
    config_rel = str(bindings.get("early_path_policy") or "")
    _require(receipt_rel.endswith(".json"), "SOURCE_RECEIPT_PATH_INVALID")
    _require(fixtures_rel.endswith(".json"), "FIXTURE_INDEX_PATH_INVALID")
    _require(config_rel.endswith(".yaml"), "EARLY_PATH_POLICY_PATH_INVALID")
    receipt_path = root / receipt_rel
    fixtures_path = root / fixtures_rel
    config_path = root / config_rel
    _require(receipt_path.is_file(), "SOURCE_RECEIPT_MISSING")
    _require(fixtures_path.is_file(), "FIXTURE_INDEX_MISSING")
    _require(config_path.is_file(), "EARLY_PATH_POLICY_MISSING")
    expected = _mapping(bindings.get("expected_hashes"), "EXPECTED_HASHES_INVALID")
    _require(
        _sha256_file(receipt_path) == str(expected.get("source_runtime_receipt_sha256")),
        "SOURCE_RECEIPT_HASH_DRIFT",
    )
    _require(
        _sha256_file(fixtures_path) == str(expected.get("fixture_index_sha256")),
        "FIXTURE_INDEX_HASH_DRIFT",
    )
    _require(
        _sha256_file(config_path) == str(expected.get("early_path_policy_sha256")),
        "EARLY_PATH_POLICY_HASH_DRIFT",
    )


def load_fixture_bodies(index_path: Path, *, root: Path) -> dict[str, bytes]:
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    _require(isinstance(payload, Mapping), "FIXTURE_INDEX_SHAPE")
    bodies = payload.get("bodies")
    _require(isinstance(bodies, list) and bodies, "FIXTURE_BODIES_MISSING")
    out: dict[str, bytes] = {}
    for item in bodies:
        entry = _mapping(item, "FIXTURE_ENTRY_INVALID")
        sha = str(entry.get("response_sha256") or "")
        _require(len(sha) == 64, "FIXTURE_SHA_INVALID")
        body_path = root / "docs/evidence/ordinary_recent_early_path_h900_failed_quotes_meu_reproject/fixtures" / f"{sha}.body"
        raw = body_path.read_bytes()
        _require(_sha256_bytes(raw) == sha, "FIXTURE_BODY_HASH_MISMATCH")
        out[sha] = raw
    _require(len(out) == len(bodies), "FIXTURE_SHA_COLLISION")
    return out


def remap_observation(
    row: Mapping[str, Any],
    *,
    bodies_by_sha: Mapping[str, bytes],
) -> dict[str, Any]:
    remapped = dict(row)
    terminal = remapped.get("h900_terminal")
    if terminal == QUOTE_OBSERVED or terminal in {None, "NOT_ATTEMPTED"}:
        remapped["h900_terminal_before"] = terminal
        remapped["h900_remap"] = "UNCHANGED"
        return remapped
    h900 = remapped.get("h900")
    _require(isinstance(h900, Mapping), "H900_BLOCK_MISSING")
    transport = h900.get("transport")
    _require(isinstance(transport, Mapping), "H900_TRANSPORT_MISSING")
    sha = str(transport.get("response_sha256") or "")
    http_status = transport.get("http_status")
    _require(sha in bodies_by_sha, "H900_BODY_FIXTURE_MISSING")
    _require(http_status == 400, "H900_HTTP_STATUS_DRIFT")
    classified = project_quote(bodies_by_sha[sha])
    error_code = classified.get("error_code")
    normalized = " ".join(str(error_code or "").upper().split())
    _require(normalized == FAILED_QUOTES_MESSAGE, "FIXTURE_ERROR_MESSAGE_DRIFT")
    _require(
        classified.get("terminal_class") == MARKET_EXECUTION_UNAVAILABLE,
        "FAILED_QUOTES_NOT_BOUND_AS_MEU",
    )
    remapped["h900_terminal_before"] = terminal
    remapped["h900_terminal"] = MARKET_EXECUTION_UNAVAILABLE
    remapped["h900_remap"] = "FAILED_QUOTES_TO_MARKET_EXECUTION_UNAVAILABLE"
    remapped["h900_error_code"] = error_code
    return remapped


def reproject(
    *,
    root: Path,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    validate_policy(policy, root=root)
    bindings = _mapping(policy.get("bindings"), "BINDINGS_INVALID")
    receipt_path = root / str(bindings["source_runtime_receipt"])
    fixtures_path = root / str(bindings["fixture_index"])
    early_path_policy_path = root / str(bindings["early_path_policy"])
    source_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    _require(isinstance(source_receipt, Mapping), "SOURCE_RECEIPT_SHAPE")
    _require(
        source_receipt.get("atom_id") == EARLY_PATH_ATOM_ID,
        "SOURCE_ATOM_DRIFT",
    )
    observations = source_receipt.get("observations")
    _require(isinstance(observations, list) and observations, "SOURCE_OBSERVATIONS_MISSING")
    bodies = load_fixture_bodies(fixtures_path, root=root)
    remapped_rows: list[dict[str, Any]] = []
    for row in observations:
        _require(isinstance(row, Mapping), "OBSERVATION_NOT_MAPPING")
        remapped_rows.append(remap_observation(row, bodies_by_sha=bodies))
    early_path_policy = yaml.safe_load(early_path_policy_path.read_text(encoding="utf-8"))
    rule = _mapping(early_path_policy.get("decision_rule"), "DECISION_RULE_MISSING")
    score = score_audition(
        remapped_rows,
        min_decision_time_eligible=int(rule["min_decision_time_eligible"]),
        min_rankable_h900=int(rule["min_rankable_h900"]),
        tau_floor=float(rule["tau_b_floor"]),
        leave_one_out_positive_share=float(rule["leave_one_out_positive_share"]),
        close_terminal=CLOSE_TERMINAL,
    )
    remapped_count = sum(
        1
        for row in remapped_rows
        if row.get("h900_remap") == "FAILED_QUOTES_TO_MARKET_EXECUTION_UNAVAILABLE"
    )
    _require(remapped_count == len(bodies), "REMAP_COUNT_DRIFT")
    _require(score.get("terminal") == CLOSE_TERMINAL, "REPROJECT_TERMINAL_NOT_CLOSE")
    _require(score.get("selected_market_execution_unavailable") is True, "SELECTED_MEU_EXPECTED")
    return {
        "schema": RECEIPT_SCHEMA,
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "source_atom_id": EARLY_PATH_ATOM_ID,
        "source_runtime_receipt": str(bindings["source_runtime_receipt"]),
        "source_runtime_receipt_sha256": _sha256_file(receipt_path),
        "fixture_index": str(bindings["fixture_index"]),
        "fixture_index_sha256": _sha256_file(fixtures_path),
        "early_path_policy": str(bindings["early_path_policy"]),
        "early_path_policy_sha256": _sha256_file(early_path_policy_path),
        "provider_requests": 0,
        "credential_reads": 0,
        "cash_spend_usd_cents": 0,
        "failed_quotes_remapped_to_meu": remapped_count,
        "score": score,
        "observations": remapped_rows,
        "non_claims": [
            "NO_NEW_PROVIDER_CAPTURE",
            "NO_EARN_FRESH_OOS",
            "NO_ALPHA",
            "NO_NETRETURN",
            "NO_STRATEGY_OR_SHADOW",
            "HISTORICAL_INVALID_EVIDENCE_YIELD_NOT_REWRITTEN",
        ],
    }


def build_acceptance(runtime_receipt: Mapping[str, Any]) -> dict[str, Any]:
    score = _mapping(runtime_receipt.get("score"), "SCORE_MISSING")
    return {
        "schema": ACCEPTANCE_SCHEMA,
        "schema_version": "1.0",
        "acceptance_id": "EVIDENCE-ORDINARY-RECENT-EARLY-PATH-H900-FAILED-QUOTES-MEU-REPROJECT-001",
        "as_of": "2026-08-21",
        "atom_id": ATOM_ID,
        "owner_decision": CLOSE_TERMINAL,
        "runtime_terminal": score.get("terminal"),
        "project_sources_disposition": {"kind": "NO_CHANGE"},
        "source_atom_id": runtime_receipt.get("source_atom_id"),
        "source_runtime_receipt": runtime_receipt.get("source_runtime_receipt"),
        "source_runtime_receipt_sha256": runtime_receipt.get("source_runtime_receipt_sha256"),
        "failed_quotes_remapped_to_meu": runtime_receipt.get("failed_quotes_remapped_to_meu"),
        "selected_market_execution_unavailable": score.get(
            "selected_market_execution_unavailable"
        ),
        "selected_top_quartile_non_quote": score.get("selected_top_quartile_non_quote"),
        "decision_time_eligible": score.get("decision_time_eligible"),
        "rankable_h900": score.get("rankable_h900"),
        "score_observed_not_applied_as_earn": {
            "tau_b": score.get("tau_b"),
            "top_quartile_median_y": score.get("top_quartile_median_y"),
            "rest_median_y": score.get("rest_median_y"),
            "leave_one_out_positive_share": score.get("leave_one_out_positive_share"),
            "note": (
                "Frozen EARN thresholds are not applied: selected top-X quartile "
                "contains MARKET_EXECUTION_UNAVAILABLE after Failed-to-get-quotes bind."
            ),
        },
        "cheapest_falsifier": "SELECTED_TOP_QUARTILE_MARKET_EXECUTION_UNAVAILABLE",
        "cheapest_falsifier_result": "TRIGGERED",
        "side_effects": {
            "cash_spend_usd_cents": 0,
            "credential_reads": 0,
            "provider_requests": 0,
            "execute_calls": 0,
            "fallbacks": 0,
            "retries": 0,
            "wallet_signer_transaction_actions": 0,
        },
        "non_claims": list(runtime_receipt.get("non_claims") or []),
        "historical_source_owner_decision_preserved": "INVALID_EVIDENCE_REPLAN",
        "taxonomy_bind": {
            "jupiter_error_message": "Failed to get quotes",
            "terminal_class": MARKET_EXECUTION_UNAVAILABLE,
            "prior_misclass": UNKNOWN_TYPED_FAILURE,
        },
    }
