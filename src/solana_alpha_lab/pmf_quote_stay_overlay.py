"""Offline PMF quote stay-overlay packet. No provider calls, execute or fill claims."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

import yaml

ATOM_ID = "PMF-QUOTE-STAY-OVERLAY-V1"
AUTHORITY_PHRASE = (
    "OK PMF-QUOTE-STAY-OVERLAY: accept Touch/Fillable/fees not evidenced"
)
CONFIG_RELATIVE = "configs/pmf_quote_stay_overlay_v1.yaml"
EXPECTED_OUTPUT_MINT = "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK"
EXPECTED_INPUT_MINT = "So11111111111111111111111111111111111111112"
EXPECTED_NOTIONAL = "10000000"
EXPECTED_ROUTE_ID = "JUPITER-SOLANA-SWAP-V2-ORDER-001"
EXPECTED_OWNER_FORK_RUNTIME_SHA256 = (
    "e76e25aab611b77ab11e97ad4e6849a1f15dbd5f0f4fcc48d77bc8aa9395b1be"
)
EXPECTED_OWNER_FORK_ACCEPTANCE_SHA256 = (
    "2b2bac38eb87fe36d32a40d5817b6c4e37a9f23b4a3c4fe28c1db3e15ec9a2c4"
)
EXPECTED_OWNER_FORK_CONFIG_SHA256 = (
    "edcf412f589248f0a7d88dc525b6c5a92fb245f2fd8a306df9401bab80c50a85"
)
EXPECTED_CONFIRMATORY_RUNTIME_SHA256 = (
    "35c19fd8566db93d77a811ef255835243cbdac62c94023041c274d6a1ab4c6c5"
)
EXPECTED_CONFIRMATORY_ACCEPTANCE_SHA256 = (
    "a3042173201e93c84a79df6e81fbf9e954da63ace9b68b0a7451fa64513d0bce"
)
EXPECTED_TASK26_CONTRACT_SHA256 = (
    "aac003cf7ba2742d310893c81af3ae4a032a52b719f2f56d80171a6486351efd"
)
TASK26_CONTRACT_RELATIVE = (
    "docs/contracts/task26_execution_cost_and_netreturn_contract_v1.md"
)
OWNER_FORK_TERMINAL = "QUOTE_OWNER_FORK_MISSING_FACTS_NAMED"
OVERLAY_TERMINAL = "QUOTE_COST_OVERLAY_BOUND_FILLABLE_NOT_EVIDENCED"
CONFIRMATORY_TERMINAL = "CLOSE_EXACT_QUOTE_SURFACE_RETENTION_FAMILY"
TERMINAL_OUTCOMES = (
    "QUOTE_STAY_OVERLAY_BOUND_SCREENING_EXHAUSTED",
    "QUOTE_STAY_OVERLAY_PREREQUISITES_DRIFT",
)
REMAINING_UNPAID_OWNER_PHRASES = (
    "OK PMF-QUOTE-TOUCH-FACT: authorize a non-execute Touch observation",
    "OK PMF-QUOTE-FEE-FACT: authorize a quote-layer fee-field observation, no execute",
)
FORBIDDEN_FOLLOW_ONS = (
    "JUPITER_EXECUTE_OR_BUILD",
    "TAKER_OR_SIGNER_SUPPLIED",
    "PROMOTE_QUOTE_TO_TOUCH_OR_FILLABLE",
    "FILLABLE_NAMED_KEEP_ON_QUOTE_ONLY",
    "QUOTE_ONLY_KEEP_SCREENING_REOPENED",
    "QUOTED_PATH_QUALITY_6_PLUS_6_WITHOUT_NEW_PHRASE",
    "TOUCH_FACT_AUTO_STARTED",
    "FEE_FACT_AUTO_STARTED",
    "MISSING_FEE_TREATED_AS_ZERO",
    "NETRETURN_OR_CASHFLOW_CLAIM",
    "LOCAL_RAW_USED_AS_GIT_TRUTH",
    "H11_UNPARK_OR_SAMPLE_CAMPAIGN",
    "H13_TRIAL",
    "H02_H10_H14_TRIAL",
    "LIVE_PIT_OR_CASHFLOW_CLAIM",
    "EXECUTE_PHRASE_OFFERED_AS_AUTHORIZED",
    "ATOM_2_FROM_RETENTION",
    "FACTORY_V1_OPERATIONAL_READY_CLAIM",
)
TASK26_REQUIRED_MARKERS = (
    "`QUOTE`",
    "`ATTEMPT`",
    "`FILL`",
    "`FEES`",
    "`CASHFLOW / NETRETURN`",
    "`QUOTE` does not imply",
    "absent component is zero",
)
EXPECTED_HOP1 = {"RECENT": 6, "TRADED": 3}
EXPECTED_Y_PATH_RISK_TRUE_N = 0


class QuoteStayOverlayError(ValueError):
    """The stay-overlay packet cannot be bound fail-closed."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise QuoteStayOverlayError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    _require(all(type(key) is str for key in value), code)
    return value


def _sha256_file(path: Any, code: str) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise QuoteStayOverlayError(code) from exc


def _load_yaml(path: Any, code: str) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise QuoteStayOverlayError(code) from exc
    return dict(_mapping(document, code))


def _load_json(path: Any, code: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QuoteStayOverlayError(code) from exc
    return dict(_mapping(document, code))


def _nested(mapping: Mapping[str, Any], key: str, code: str) -> Mapping[str, Any]:
    return dict(_mapping(mapping.get(key), code))


def _phrase_authorizes_execute(phrases: object) -> bool:
    if not isinstance(phrases, list):
        return True
    for phrase in phrases:
        if not isinstance(phrase, str):
            return True
        lowered = phrase.casefold()
        remainder = lowered.replace("no execute", " ").replace("non-execute", " ")
        if "execute" in remainder or "/execute" in remainder:
            return True
    return False


def _buy_h900_hop1_counts(runtime: Mapping[str, Any]) -> dict[str, int]:
    observations = runtime.get("observations")
    _require(isinstance(observations, list), "CONFIRMATORY_OBSERVATIONS_INVALID")
    counts = {"RECENT": 0, "TRADED": 0}
    buy_n = 0
    for item in observations:
        row = _mapping(item, "CONFIRMATORY_OBSERVATION_INVALID")
        if row.get("kind") != "BUY_H900":
            continue
        buy_n += 1
        stratum = str(row.get("stratum") or "")
        _require(stratum in counts, "BUY_H900_STRATUM_INVALID")
        quote = _nested(row, "quote", "BUY_H900_QUOTE_INVALID")
        route_plan = _nested(quote, "route_plan", "BUY_H900_ROUTE_PLAN_INVALID")
        if route_plan.get("hop_count") == 1:
            counts[stratum] += 1
    _require(buy_n == 12, "BUY_H900_COUNT_DRIFT")
    return counts


def _y_path_risk_true_n(runtime: Mapping[str, Any]) -> int:
    mechanism = _nested(runtime, "mechanism", "CONFIRMATORY_MECHANISM_INVALID")
    cells = mechanism.get("cells")
    _require(isinstance(cells, list) and len(cells) == 12, "CONFIRMATORY_CELLS_DRIFT")
    return sum(
        1
        for item in cells
        if _mapping(item, "CONFIRMATORY_CELL_INVALID").get("y_path_risk") is True
    )


def decide_stay_overlay_terminal(result: Mapping[str, Any]) -> str:
    facts = _nested(result, "missing_facts", "MISSING_FACTS_INVALID")
    touch = _nested(facts, "touch", "TOUCH_FACT_INVALID")
    fillable = _nested(facts, "fillable", "FILLABLE_FACT_INVALID")
    fees = _nested(facts, "fees", "FEES_FACT_INVALID")
    probe = _nested(result, "design_probe", "DESIGN_PROBE_INVALID")
    hop1 = _nested(probe, "buy_h900_hop_count_eq_1", "HOP1_PROBE_INVALID")
    phrases = result.get("remaining_unpaid_owner_phrases")
    bound = (
        result.get("owner_phrase") == AUTHORITY_PHRASE
        and result.get("execute") == "FORBIDDEN"
        and result.get("build") == "FORBIDDEN"
        and result.get("taker") == "OMITTED_QUOTE_ONLY"
        and result.get("execute_phrase_status") == "INELIGIBLE"
        and result.get("provider_requests") == 0
        and result.get("credential_reads") == 0
        and result.get("local_raw_used_as_git_truth") is False
        and result.get("owner_fork_terminal") == OWNER_FORK_TERMINAL
        and result.get("overlay_terminal") == OVERLAY_TERMINAL
        and result.get("confirmatory_scientific_terminal") == CONFIRMATORY_TERMINAL
        and result.get("confirmatory_product_terminal") == CONFIRMATORY_TERMINAL
        and result.get("quote_only_keep_screening") == "EXHAUSTED"
        and result.get("fillable_named_keep_on_quote_only") == "FORBIDDEN"
        and result.get("quoted_path_quality_6_plus_6") == "NOT_AUTHORIZED"
        and result.get("touch_fact_status") == "UNPAID_NOT_STARTED"
        and result.get("fee_fact_status") == "UNPAID_NOT_STARTED"
        and result.get("attempt_status") == "FROZEN_OFFLINE_NOT_STARTED"
        and result.get("factory_v1_operational_ready") is False
        and result.get("atom_2") is False
        and touch.get("state") == "NOT_EVIDENCED"
        and fillable.get("state") == "NOT_EVIDENCED"
        and fees.get("state") == "NOT_COMPUTABLE"
        and fees.get("missing_is_not_zero") is True
        and result.get("output_mint") == EXPECTED_OUTPUT_MINT
        and hop1.get("RECENT") == EXPECTED_HOP1["RECENT"]
        and hop1.get("TRADED") == EXPECTED_HOP1["TRADED"]
        and probe.get("science") is False
        and probe.get("y_path_risk_true_n") == EXPECTED_Y_PATH_RISK_TRUE_N
        and isinstance(phrases, list)
        and phrases == list(REMAINING_UNPAID_OWNER_PHRASES)
        and AUTHORITY_PHRASE not in phrases
        and not _phrase_authorizes_execute(phrases)
    )
    if bound:
        return "QUOTE_STAY_OVERLAY_BOUND_SCREENING_EXHAUSTED"
    return "QUOTE_STAY_OVERLAY_PREREQUISITES_DRIFT"


def bind_pmf_quote_stay_overlay(root: Any) -> dict[str, Any]:
    from pathlib import Path

    resolved = Path(root)
    policy = _load_yaml(resolved / CONFIG_RELATIVE, "STAY_OVERLAY_POLICY_INVALID")
    _require(policy.get("atom_id") == ATOM_ID, "ATOM_DRIFT")
    _require(policy.get("owner_phrase") == AUTHORITY_PHRASE, "AUTHORITY_POLICY_DRIFT")
    _require(policy.get("execute") == "FORBIDDEN", "EXECUTE_NOT_FORBIDDEN")
    _require(policy.get("build") == "FORBIDDEN", "BUILD_NOT_FORBIDDEN")
    _require(policy.get("taker") == "OMITTED_QUOTE_ONLY", "TAKER_NOT_OMITTED")
    _require(
        policy.get("execute_phrase_status") == "INELIGIBLE",
        "EXECUTE_PHRASE_NOT_INELIGIBLE",
    )
    _require(int(policy.get("provider_requests_max", 1)) == 0, "PROVIDER_BUDGET_DRIFT")
    _require(int(policy.get("credential_reads_max", 1)) == 0, "CREDENTIAL_BUDGET_DRIFT")
    _require(policy.get("local_raw_as_git_truth") is False, "RAW_GIT_TRUTH_NOT_FORBIDDEN")
    _require(policy.get("quote_only_keep_screening") == "EXHAUSTED", "SCREENING_NOT_EXHAUSTED")
    _require(
        policy.get("fillable_named_keep_on_quote_only") == "FORBIDDEN",
        "FILLABLE_KEEP_NOT_FORBIDDEN",
    )
    _require(
        policy.get("quoted_path_quality_6_plus_6") == "NOT_AUTHORIZED",
        "QUOTED_PATH_KEEP_AUTHORIZED",
    )
    _require(policy.get("touch_fact_status") == "UNPAID_NOT_STARTED", "TOUCH_FACT_STARTED")
    _require(policy.get("fee_fact_status") == "UNPAID_NOT_STARTED", "FEE_FACT_STARTED")
    _require(
        policy.get("attempt_status") == "FROZEN_OFFLINE_NOT_STARTED",
        "ATTEMPT_STARTED",
    )
    _require(policy.get("factory_v1_operational_ready") is False, "OPERATIONAL_READY_CLAIMED")
    _require(policy.get("atom_2") is False, "ATOM_2_CLAIMED")
    identity = _nested(policy, "identity", "IDENTITY_INVALID")
    _require(identity.get("output_mint") == EXPECTED_OUTPUT_MINT, "OUTPUT_MINT_DRIFT")
    _require(identity.get("input_mint") == EXPECTED_INPUT_MINT, "INPUT_MINT_DRIFT")
    _require(str(identity.get("notional_atomic")) == EXPECTED_NOTIONAL, "NOTIONAL_DRIFT")
    _require(identity.get("route_id") == EXPECTED_ROUTE_ID, "ROUTE_ID_DRIFT")
    owner_fork = _nested(policy, "owner_fork", "OWNER_FORK_SPEC_INVALID")
    confirmatory = _nested(policy, "confirmatory", "CONFIRMATORY_SPEC_INVALID")
    vocabulary = _nested(policy, "task26_vocabulary", "TASK26_SPEC_INVALID")
    _require(vocabulary.get("wrap") is True, "TASK26_WRAP_REQUIRED")
    _require(
        vocabulary.get("invoke_synthetic_engine") is False,
        "SYNTHETIC_ENGINE_FORBIDDEN",
    )
    unpaid = policy.get("remaining_unpaid_owner_phrases")
    _require(
        isinstance(unpaid, list) and unpaid == list(REMAINING_UNPAID_OWNER_PHRASES),
        "UNPAID_PHRASE_DRIFT",
    )
    _require(not _phrase_authorizes_execute(unpaid), "EXECUTE_PHRASE_OFFERED")
    _require(AUTHORITY_PHRASE not in unpaid, "STAY_PHRASE_STILL_UNPAID")

    owner_fork_runtime_path = resolved / str(owner_fork.get("runtime_receipt"))
    owner_fork_acceptance_path = resolved / str(owner_fork.get("acceptance"))
    owner_fork_config_path = resolved / str(owner_fork.get("config"))
    confirmatory_runtime_path = resolved / str(confirmatory.get("runtime_receipt"))
    confirmatory_acceptance_path = resolved / str(confirmatory.get("acceptance"))
    task26_path = resolved / str(vocabulary.get("contract"))

    observed_owner_fork_runtime_sha = _sha256_file(
        owner_fork_runtime_path, "OWNER_FORK_RUNTIME_UNREADABLE"
    )
    observed_owner_fork_acceptance_sha = _sha256_file(
        owner_fork_acceptance_path, "OWNER_FORK_ACCEPTANCE_UNREADABLE"
    )
    observed_owner_fork_config_sha = _sha256_file(
        owner_fork_config_path, "OWNER_FORK_CONFIG_UNREADABLE"
    )
    observed_confirmatory_runtime_sha = _sha256_file(
        confirmatory_runtime_path, "CONFIRMATORY_RUNTIME_UNREADABLE"
    )
    observed_confirmatory_acceptance_sha = _sha256_file(
        confirmatory_acceptance_path, "CONFIRMATORY_ACCEPTANCE_UNREADABLE"
    )
    observed_task26_sha = _sha256_file(task26_path, "TASK26_UNREADABLE")

    _require(
        observed_owner_fork_runtime_sha == EXPECTED_OWNER_FORK_RUNTIME_SHA256,
        "OWNER_FORK_RUNTIME_HASH_DRIFT",
    )
    _require(
        observed_owner_fork_acceptance_sha == EXPECTED_OWNER_FORK_ACCEPTANCE_SHA256,
        "OWNER_FORK_ACCEPTANCE_HASH_DRIFT",
    )
    _require(
        observed_owner_fork_config_sha == EXPECTED_OWNER_FORK_CONFIG_SHA256,
        "OWNER_FORK_CONFIG_HASH_DRIFT",
    )
    _require(
        observed_confirmatory_runtime_sha == EXPECTED_CONFIRMATORY_RUNTIME_SHA256,
        "CONFIRMATORY_RUNTIME_HASH_DRIFT",
    )
    _require(
        observed_confirmatory_acceptance_sha == EXPECTED_CONFIRMATORY_ACCEPTANCE_SHA256,
        "CONFIRMATORY_ACCEPTANCE_HASH_DRIFT",
    )
    _require(
        observed_task26_sha == EXPECTED_TASK26_CONTRACT_SHA256,
        "TASK26_HASH_DRIFT",
    )
    _require(
        observed_owner_fork_runtime_sha == str(owner_fork["runtime_receipt_sha256"]),
        "OWNER_FORK_RUNTIME_POLICY_HASH_DRIFT",
    )
    _require(
        observed_owner_fork_acceptance_sha == str(owner_fork["acceptance_sha256"]),
        "OWNER_FORK_ACCEPTANCE_POLICY_HASH_DRIFT",
    )
    _require(
        observed_owner_fork_config_sha == str(owner_fork["config_sha256"]),
        "OWNER_FORK_CONFIG_POLICY_HASH_DRIFT",
    )
    _require(
        observed_confirmatory_runtime_sha == str(confirmatory["runtime_receipt_sha256"]),
        "CONFIRMATORY_RUNTIME_POLICY_HASH_DRIFT",
    )
    _require(
        observed_confirmatory_acceptance_sha == str(confirmatory["acceptance_sha256"]),
        "CONFIRMATORY_ACCEPTANCE_POLICY_HASH_DRIFT",
    )
    _require(
        observed_task26_sha == str(vocabulary["contract_sha256"]),
        "TASK26_POLICY_HASH_DRIFT",
    )
    _require(
        confirmatory.get("scientific_terminal") == CONFIRMATORY_TERMINAL,
        "CONFIRMATORY_POLICY_TERMINAL_DRIFT",
    )
    _require(
        confirmatory.get("product_terminal") == CONFIRMATORY_TERMINAL,
        "CONFIRMATORY_POLICY_PRODUCT_TERMINAL_DRIFT",
    )

    task26_text = task26_path.read_text(encoding="utf-8")
    for marker in TASK26_REQUIRED_MARKERS:
        _require(marker in task26_text, "TASK26_VOCABULARY_DRIFT")

    owner_fork_runtime = _load_json(
        owner_fork_runtime_path, "OWNER_FORK_RUNTIME_INVALID"
    )
    owner_fork_acceptance = _load_json(
        owner_fork_acceptance_path, "OWNER_FORK_ACCEPTANCE_INVALID"
    )
    confirmatory_runtime = _load_json(
        confirmatory_runtime_path, "CONFIRMATORY_RUNTIME_INVALID"
    )
    confirmatory_acceptance = _load_json(
        confirmatory_acceptance_path, "CONFIRMATORY_ACCEPTANCE_INVALID"
    )
    _require(
        owner_fork_runtime.get("terminal") == OWNER_FORK_TERMINAL,
        "OWNER_FORK_RUNTIME_TERMINAL_DRIFT",
    )
    _require(
        owner_fork_acceptance.get("terminal") == OWNER_FORK_TERMINAL,
        "OWNER_FORK_ACCEPTANCE_TERMINAL_DRIFT",
    )
    _require(owner_fork_acceptance.get("execute") == "FORBIDDEN", "OWNER_FORK_EXECUTE")
    _require(
        owner_fork_acceptance.get("overlay_terminal") == OVERLAY_TERMINAL,
        "OVERLAY_TERMINAL_DRIFT",
    )
    missing = _nested(
        owner_fork_acceptance, "missing_facts", "OWNER_FORK_MISSING_FACTS_INVALID"
    )
    touch = _nested(missing, "touch", "OWNER_FORK_TOUCH_INVALID")
    fillable = _nested(missing, "fillable", "OWNER_FORK_FILLABLE_INVALID")
    fees = _nested(missing, "fees", "OWNER_FORK_FEES_INVALID")
    _require(touch.get("state") == "NOT_EVIDENCED", "TOUCH_PROMOTED")
    _require(touch.get("observed_reason") == "QUOTE_IS_NOT_TOUCH", "TOUCH_REASON_DRIFT")
    _require(fillable.get("state") == "NOT_EVIDENCED", "FILLABLE_PROMOTED")
    _require(
        fillable.get("observed_reason") == "NO_TAKER_NO_TRANSACTION_NO_SIMULATE",
        "FILLABLE_REASON_DRIFT",
    )
    _require(fees.get("state") == "NOT_COMPUTABLE", "FEES_PROMOTED")
    _require(fees.get("missing_is_not_zero") is True, "FEE_ABSENCE_TREATED_AS_ZERO")
    _require(
        confirmatory_acceptance.get("scientific_terminal") == CONFIRMATORY_TERMINAL,
        "CONFIRMATORY_SCIENTIFIC_TERMINAL_DRIFT",
    )
    _require(
        confirmatory_acceptance.get("product_terminal") == CONFIRMATORY_TERMINAL,
        "CONFIRMATORY_PRODUCT_TERMINAL_DRIFT",
    )
    _require(confirmatory_acceptance.get("atom_2") is False, "CONFIRMATORY_ATOM_2")
    _require(
        confirmatory_acceptance.get("factory_v1_operational_ready") is False,
        "CONFIRMATORY_OPERATIONAL_READY",
    )
    hop1 = _buy_h900_hop1_counts(confirmatory_runtime)
    _require(hop1 == EXPECTED_HOP1, "DESIGN_PROBE_HOP1_DRIFT")
    y_path_risk_true_n = _y_path_risk_true_n(confirmatory_runtime)
    _require(y_path_risk_true_n == EXPECTED_Y_PATH_RISK_TRUE_N, "DESIGN_PROBE_PATH_RISK_DRIFT")
    design_probe = _nested(policy, "design_probe", "DESIGN_PROBE_POLICY_INVALID")
    _require(design_probe.get("science") is False, "DESIGN_PROBE_CLAIMED_AS_SCIENCE")
    probe_hop1 = _nested(
        design_probe, "buy_h900_hop_count_eq_1", "DESIGN_PROBE_HOP1_POLICY_INVALID"
    )
    _require(int(probe_hop1.get("RECENT")) == hop1["RECENT"], "DESIGN_PROBE_HOP1_RECENT_POLICY")
    _require(int(probe_hop1.get("TRADED")) == hop1["TRADED"], "DESIGN_PROBE_HOP1_TRADED_POLICY")
    _require(
        int(design_probe.get("y_path_risk_true_n")) == y_path_risk_true_n,
        "DESIGN_PROBE_PATH_RISK_POLICY",
    )

    missing_facts = {
        "touch": dict(touch),
        "fillable": dict(fillable),
        "fees": dict(fees),
    }
    result = {
        "owner_phrase": AUTHORITY_PHRASE,
        "adoption_route": policy.get("adoption_route"),
        "route_id": EXPECTED_ROUTE_ID,
        "output_mint": EXPECTED_OUTPUT_MINT,
        "input_mint": EXPECTED_INPUT_MINT,
        "notional_atomic": EXPECTED_NOTIONAL,
        "execute": "FORBIDDEN",
        "build": "FORBIDDEN",
        "taker": "OMITTED_QUOTE_ONLY",
        "execute_phrase_status": "INELIGIBLE",
        "provider_requests": 0,
        "credential_reads": 0,
        "local_raw_used_as_git_truth": False,
        "owner_fork_runtime_sha256": observed_owner_fork_runtime_sha,
        "owner_fork_acceptance_sha256": observed_owner_fork_acceptance_sha,
        "owner_fork_config_sha256": observed_owner_fork_config_sha,
        "confirmatory_runtime_sha256": observed_confirmatory_runtime_sha,
        "confirmatory_acceptance_sha256": observed_confirmatory_acceptance_sha,
        "task26_contract_sha256": observed_task26_sha,
        "owner_fork_terminal": OWNER_FORK_TERMINAL,
        "overlay_terminal": OVERLAY_TERMINAL,
        "confirmatory_scientific_terminal": CONFIRMATORY_TERMINAL,
        "confirmatory_product_terminal": CONFIRMATORY_TERMINAL,
        "quote_only_keep_screening": "EXHAUSTED",
        "fillable_named_keep_on_quote_only": "FORBIDDEN",
        "quoted_path_quality_6_plus_6": "NOT_AUTHORIZED",
        "touch_fact_status": "UNPAID_NOT_STARTED",
        "fee_fact_status": "UNPAID_NOT_STARTED",
        "attempt_status": "FROZEN_OFFLINE_NOT_STARTED",
        "factory_v1_operational_ready": False,
        "atom_2": False,
        "missing_facts": missing_facts,
        "design_probe": {
            "science": False,
            "buy_h900_hop_count_eq_1": dict(hop1),
            "y_path_risk_true_n": y_path_risk_true_n,
            "why_not_quoted_path_keep": design_probe.get("why_not_quoted_path_keep"),
        },
        "remaining_unpaid_owner_phrases": list(REMAINING_UNPAID_OWNER_PHRASES),
        "forbidden_follow_ons": list(policy.get("forbidden_follow_ons") or []),
        "h13_or_h02_started": False,
        "h11_unparked": False,
    }
    result["terminal"] = decide_stay_overlay_terminal(result)
    return result


def format_owner_readout(result: Mapping[str, Any]) -> str:
    terminal = str(result.get("terminal"))
    bound = terminal == "QUOTE_STAY_OVERLAY_BOUND_SCREENING_EXHAUSTED"
    heading = (
        "# PMF — stay-overlay: quote-only KEEP screening exhausted\n"
        if bound
        else "# PMF — stay-overlay prerequisites drifted\n"
    )
    facts = result.get("missing_facts") if isinstance(result.get("missing_facts"), Mapping) else {}

    def _fact(name: str) -> Mapping[str, Any]:
        item = facts.get(name) if isinstance(facts, Mapping) else None
        return item if isinstance(item, Mapping) else {}

    touch = _fact("touch")
    fillable = _fact("fillable")
    fees = _fact("fees")
    probe = result.get("design_probe") if isinstance(result.get("design_probe"), Mapping) else {}
    hop1 = probe.get("buy_h900_hop_count_eq_1") if isinstance(probe, Mapping) else {}
    hop1 = hop1 if isinstance(hop1, Mapping) else {}
    phrases = result.get("remaining_unpaid_owner_phrases")
    phrase_lines = ""
    if isinstance(phrases, list):
        phrase_lines = "\n".join(f"- `{item}`" for item in phrases)
    return (
        heading
        + "\n"
        + f"**Терминальное решение:** `{terminal}`\n"
        + f"**Фраза владельца:** `{result.get('owner_phrase')}`\n"
        + "\n"
        + "Это **stay-overlay поверх owner-fork и confirmatory family-close**, "
        "не Touch, не Fillable, не новый 6+6, не execute, не alpha и не canonical DONE.\n"
        + "\n"
        + "## Что остаётся истинным\n"
        + "\n"
        + f"- owner-fork terminal: `{result.get('owner_fork_terminal')}`\n"
        + f"- overlay terminal: `{result.get('overlay_terminal')}`\n"
        + f"- confirmatory scientific terminal: `{result.get('confirmatory_scientific_terminal')}`\n"
        + f"- quote-only KEEP screening: `{result.get('quote_only_keep_screening')}`\n"
        + f"- fillable-named KEEP on quote-only: `{result.get('fillable_named_keep_on_quote_only')}`\n"
        + f"- quoted-path 6+6: `{result.get('quoted_path_quality_6_plus_6')}`\n"
        + "- execute: `FORBIDDEN` / `INELIGIBLE` в этом пакете\n"
        + f"- provider_requests: `{result.get('provider_requests')}`\n"
        + f"- factory_v1_operational_ready: `{result.get('factory_v1_operational_ready')}`\n"
        + f"- atom_2: `{result.get('atom_2')}`\n"
        + "\n"
        + "## Слои, которые quote по-прежнему не доказывает\n"
        + "\n"
        + f"- Touch: `{touch.get('state')}` (`{touch.get('observed_reason')}`). Quote не есть Touch.\n"
        + f"- Fillable: `{fillable.get('state')}` (`{fillable.get('observed_reason')}`). "
        "KEEP с именем fillable над `/order` запрещён.\n"
        + f"- fees: `{fees.get('state')}` (`{fees.get('observed_reason')}`). отсутствие не есть ноль.\n"
        + "\n"
        + "## Дизайн-зонд (не наука, не новый KEEP)\n"
        + "\n"
        + "На confirmatory C1 path-risk как KEEP не имеет контраста, а hop_count==1 "
        "не даёт мощности на свежий 6+6.\n"
        + "\n"
        + f"- science: `{probe.get('science')}`\n"
        + f"- y_path_risk true n: `{probe.get('y_path_risk_true_n')}`\n"
        + f"- BUY_H900 hop_count==1 RECENT/TRADED: `{hop1.get('RECENT')}` / `{hop1.get('TRADED')}`\n"
        + f"- why not quoted-path KEEP: `{probe.get('why_not_quoted_path_keep')}`\n"
        + "\n"
        + "## Оставшиеся неоплаченные фразы (этот атом их не исполняет)\n"
        + "\n"
        + f"{phrase_lines}\n"
        + "\n"
        + "## Jupiter / execute\n"
        + "\n"
        + "Нет. Stay-overlay не стартует Free-key 6+6. `/execute` и `/build` запрещены.\n"
        + "\n"
        + "## Не делать\n"
        + "\n"
        + "- `FILLABLE_NAMED_KEEP_ON_QUOTE_ONLY`\n"
        + "- `QUOTE_ONLY_KEEP_SCREENING_REOPENED`\n"
        + "- `QUOTED_PATH_QUALITY_6_PLUS_6_WITHOUT_NEW_PHRASE`\n"
        + "- `TOUCH_FACT_AUTO_STARTED` / `FEE_FACT_AUTO_STARTED`\n"
        + "- `PROMOTE_QUOTE_TO_TOUCH_OR_FILLABLE`\n"
        + "- `ATOM_2_FROM_RETENTION`\n"
        + "- `FACTORY_V1_OPERATIONAL_READY_CLAIM`\n"
        + "- `JUPITER_EXECUTE_OR_BUILD`\n"
    )
