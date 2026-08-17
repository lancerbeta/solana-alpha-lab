"""Offline PMF quote owner-fork packet. No provider calls, execute or fill claims."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

ATOM_ID = "PMF-QUOTE-OWNER-FORK-V1"
AUTHORITY_PHRASE = (
    "OK PMF-QUOTE-OWNER-FORK: overlay receipt only, name missing "
    "Touch/Fillable/fee facts, no execute"
)
CONFIG_RELATIVE = "configs/pmf_quote_owner_fork_v1.yaml"
EXPECTED_OUTPUT_MINT = "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK"
EXPECTED_INPUT_MINT = "So11111111111111111111111111111111111111112"
EXPECTED_NOTIONAL = "10000000"
EXPECTED_ROUTE_ID = "JUPITER-SOLANA-SWAP-V2-ORDER-001"
EXPECTED_OVERLAY_RUNTIME_SHA256 = (
    "2b9240d3d29f46365f3b3e594cd55067ccd53fa17dede1d45e06deb59fe44397"
)
EXPECTED_OVERLAY_ACCEPTANCE_SHA256 = (
    "ecbe30d4ba9f14eed6d6dbde1b2424ad594edab7a8e1e6d828d5879d4834d49b"
)
EXPECTED_OVERLAY_CONFIG_SHA256 = (
    "bfe6d8e7d5fea2b00d7c35fde0d52594045332514b0150ca7b649be1ce94d9ea"
)
EXPECTED_TASK26_CONTRACT_SHA256 = (
    "aac003cf7ba2742d310893c81af3ae4a032a52b719f2f56d80171a6486351efd"
)
TASK26_CONTRACT_RELATIVE = (
    "docs/contracts/task26_execution_cost_and_netreturn_contract_v1.md"
)
OVERLAY_TERMINAL = "QUOTE_COST_OVERLAY_BOUND_FILLABLE_NOT_EVIDENCED"
TERMINAL_OUTCOMES = (
    "QUOTE_OWNER_FORK_MISSING_FACTS_NAMED",
    "QUOTE_OWNER_FORK_PREREQUISITES_DRIFT",
)
UNPAID_OWNER_PHRASES = (
    "OK PMF-QUOTE-STAY-OVERLAY: accept Touch/Fillable/fees not evidenced",
    "OK PMF-QUOTE-TOUCH-FACT: authorize a non-execute Touch observation",
    "OK PMF-QUOTE-FEE-FACT: authorize a quote-layer fee-field observation, no execute",
)
FORBIDDEN_FOLLOW_ONS = (
    "JUPITER_EXECUTE_OR_BUILD",
    "TAKER_OR_SIGNER_SUPPLIED",
    "PROMOTE_QUOTE_TO_TOUCH_OR_FILLABLE",
    "MISSING_FEE_TREATED_AS_ZERO",
    "NETRETURN_OR_CASHFLOW_CLAIM",
    "LOCAL_RAW_USED_AS_GIT_TRUTH",
    "H11_UNPARK_OR_SAMPLE_CAMPAIGN",
    "H13_TRIAL",
    "H02_H10_H14_TRIAL",
    "LIVE_PIT_OR_CASHFLOW_CLAIM",
    "EXECUTE_PHRASE_OFFERED_AS_AUTHORIZED",
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
MISSING_FACTS = {
    "touch": {
        "state": "NOT_EVIDENCED",
        "observed_reason": "QUOTE_IS_NOT_TOUCH",
        "task26_layer": "QUOTE",
        "missing_fact": (
            "PIT_SAFE_TOUCH_OBSERVATION_NOT_ANOTHER_ORDER_QUOTE_AND_NOT_EXECUTE"
        ),
        "does_not_prove": ("FILLABLE", "FEES", "NETRETURN"),
    },
    "fillable": {
        "state": "NOT_EVIDENCED",
        "observed_reason": "NO_TAKER_NO_TRANSACTION_NO_SIMULATE",
        "task26_layer": "ATTEMPT",
        "missing_fact": (
            "TYPED_ATTEMPT_OR_SIMULATE_WITH_TAKER_NOT_AUTHORIZED_HERE"
        ),
        "does_not_prove": ("FILL", "FEES", "NETRETURN"),
    },
    "fees": {
        "state": "NOT_COMPUTABLE",
        "observed_reason": "SANITIZED_RECEIPT_HAS_NO_FEE_COMPONENTS",
        "task26_layer": "FEES",
        "missing_fact": (
            "TYPED_FEE_COMPONENTS_WITH_SOURCE_AND_CONFIDENCE_ABSENCE_IS_NOT_ZERO"
        ),
        "does_not_prove": ("NETRETURN",),
        "missing_is_not_zero": True,
    },
}


class QuoteOwnerForkError(ValueError):
    """The owner-fork packet cannot be bound fail-closed."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise QuoteOwnerForkError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    _require(all(type(key) is str for key in value), code)
    return value


def _sha256_file(path: Path, code: str) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise QuoteOwnerForkError(code) from exc


def _load_yaml(path: Path, code: str) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise QuoteOwnerForkError(code) from exc
    return dict(_mapping(document, code))


def _load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QuoteOwnerForkError(code) from exc
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
        remainder = (
            lowered.replace("no execute", " ").replace("non-execute", " ")
        )
        if "execute" in remainder or "/execute" in remainder:
            return True
    return False


def decide_owner_fork_terminal(result: Mapping[str, Any]) -> str:
    facts = _nested(result, "missing_facts", "MISSING_FACTS_INVALID")
    touch = _nested(facts, "touch", "TOUCH_FACT_INVALID")
    fillable = _nested(facts, "fillable", "FILLABLE_FACT_INVALID")
    fees = _nested(facts, "fees", "FEES_FACT_INVALID")
    phrases = result.get("unpaid_owner_phrases")
    bound = (
        result.get("owner_phrase") == AUTHORITY_PHRASE
        and result.get("execute") == "FORBIDDEN"
        and result.get("build") == "FORBIDDEN"
        and result.get("taker") == "OMITTED_QUOTE_ONLY"
        and result.get("execute_phrase_status") == "INELIGIBLE"
        and result.get("provider_requests") == 0
        and result.get("credential_reads") == 0
        and result.get("local_raw_used_as_git_truth") is False
        and result.get("overlay_terminal") == OVERLAY_TERMINAL
        and touch.get("state") == "NOT_EVIDENCED"
        and fillable.get("state") == "NOT_EVIDENCED"
        and fees.get("state") == "NOT_COMPUTABLE"
        and fees.get("missing_is_not_zero") is True
        and result.get("output_mint") == EXPECTED_OUTPUT_MINT
        and result.get("input_mint") == EXPECTED_INPUT_MINT
        and result.get("notional_atomic") == EXPECTED_NOTIONAL
        and isinstance(phrases, list)
        and phrases == list(UNPAID_OWNER_PHRASES)
        and not _phrase_authorizes_execute(phrases)
    )
    if bound:
        return "QUOTE_OWNER_FORK_MISSING_FACTS_NAMED"
    return "QUOTE_OWNER_FORK_PREREQUISITES_DRIFT"


def bind_pmf_quote_owner_fork(root: Path) -> dict[str, Any]:
    resolved = Path(root)
    policy = _load_yaml(resolved / CONFIG_RELATIVE, "OWNER_FORK_POLICY_INVALID")
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
    identity = _nested(policy, "identity", "IDENTITY_INVALID")
    _require(identity.get("output_mint") == EXPECTED_OUTPUT_MINT, "OUTPUT_MINT_DRIFT")
    _require(identity.get("input_mint") == EXPECTED_INPUT_MINT, "INPUT_MINT_DRIFT")
    _require(str(identity.get("notional_atomic")) == EXPECTED_NOTIONAL, "NOTIONAL_DRIFT")
    _require(identity.get("route_id") == EXPECTED_ROUTE_ID, "ROUTE_ID_DRIFT")
    overlay = _nested(policy, "overlay", "OVERLAY_SPEC_INVALID")
    vocabulary = _nested(policy, "task26_vocabulary", "TASK26_SPEC_INVALID")
    _require(vocabulary.get("wrap") is True, "TASK26_WRAP_REQUIRED")
    _require(
        vocabulary.get("invoke_synthetic_engine") is False,
        "SYNTHETIC_ENGINE_FORBIDDEN",
    )
    unpaid = policy.get("unpaid_owner_phrases")
    _require(
        isinstance(unpaid, list) and unpaid == list(UNPAID_OWNER_PHRASES),
        "UNPAID_PHRASE_DRIFT",
    )
    _require(not _phrase_authorizes_execute(unpaid), "EXECUTE_PHRASE_OFFERED")

    runtime_path = resolved / str(overlay.get("runtime_receipt"))
    acceptance_path = resolved / str(overlay.get("acceptance"))
    overlay_config_path = resolved / str(overlay.get("config"))
    task26_path = resolved / str(vocabulary.get("contract"))
    observed_runtime_sha = _sha256_file(runtime_path, "OVERLAY_RUNTIME_UNREADABLE")
    observed_acceptance_sha = _sha256_file(
        acceptance_path, "OVERLAY_ACCEPTANCE_UNREADABLE"
    )
    observed_overlay_config_sha = _sha256_file(
        overlay_config_path, "OVERLAY_CONFIG_UNREADABLE"
    )
    observed_task26_sha = _sha256_file(task26_path, "TASK26_UNREADABLE")
    _require(
        observed_runtime_sha == EXPECTED_OVERLAY_RUNTIME_SHA256,
        "OVERLAY_RUNTIME_HASH_DRIFT",
    )
    _require(
        observed_acceptance_sha == EXPECTED_OVERLAY_ACCEPTANCE_SHA256,
        "OVERLAY_ACCEPTANCE_HASH_DRIFT",
    )
    _require(
        observed_overlay_config_sha == EXPECTED_OVERLAY_CONFIG_SHA256,
        "OVERLAY_CONFIG_HASH_DRIFT",
    )
    _require(
        observed_task26_sha == EXPECTED_TASK26_CONTRACT_SHA256,
        "TASK26_HASH_DRIFT",
    )
    _require(
        observed_runtime_sha == str(overlay["runtime_receipt_sha256"]),
        "OVERLAY_RUNTIME_POLICY_HASH_DRIFT",
    )
    _require(
        observed_acceptance_sha == str(overlay["acceptance_sha256"]),
        "OVERLAY_ACCEPTANCE_POLICY_HASH_DRIFT",
    )
    _require(
        observed_overlay_config_sha == str(overlay["config_sha256"]),
        "OVERLAY_CONFIG_POLICY_HASH_DRIFT",
    )
    _require(
        observed_task26_sha == str(vocabulary["contract_sha256"]),
        "TASK26_POLICY_HASH_DRIFT",
    )

    task26_text = task26_path.read_text(encoding="utf-8")
    for marker in TASK26_REQUIRED_MARKERS:
        _require(marker in task26_text, "TASK26_VOCABULARY_DRIFT")

    runtime = _load_json(runtime_path, "OVERLAY_RUNTIME_INVALID")
    acceptance = _load_json(acceptance_path, "OVERLAY_ACCEPTANCE_INVALID")
    _require(runtime.get("terminal") == OVERLAY_TERMINAL, "OVERLAY_RUNTIME_TERMINAL_DRIFT")
    _require(
        acceptance.get("terminal") == OVERLAY_TERMINAL,
        "OVERLAY_ACCEPTANCE_TERMINAL_DRIFT",
    )
    _require(acceptance.get("execute") == "FORBIDDEN", "OVERLAY_EXECUTE_NOT_FORBIDDEN")
    _require(acceptance.get("output_mint") == EXPECTED_OUTPUT_MINT, "OVERLAY_MINT_DRIFT")
    _require(
        str(acceptance.get("notional_atomic")) == EXPECTED_NOTIONAL,
        "OVERLAY_NOTIONAL_DRIFT",
    )
    layers = _nested(acceptance, "layers", "OVERLAY_LAYERS_INVALID")
    quote = _nested(layers, "quote", "OVERLAY_QUOTE_INVALID")
    touch = _nested(layers, "touch", "OVERLAY_TOUCH_INVALID")
    fillable = _nested(layers, "fillable", "OVERLAY_FILLABLE_INVALID")
    fees = _nested(layers, "fees", "OVERLAY_FEES_INVALID")
    _require(quote.get("state") == "OBSERVED", "QUOTE_NOT_OBSERVED")
    _require(touch.get("state") == "NOT_EVIDENCED", "TOUCH_PROMOTED")
    _require(touch.get("reason") == "QUOTE_IS_NOT_TOUCH", "TOUCH_REASON_DRIFT")
    _require(fillable.get("state") == "NOT_EVIDENCED", "FILLABLE_PROMOTED")
    _require(
        fillable.get("reason") == "NO_TAKER_NO_TRANSACTION_NO_SIMULATE",
        "FILLABLE_REASON_DRIFT",
    )
    _require(fees.get("state") == "NOT_COMPUTABLE", "FEES_PROMOTED")
    _require(fees.get("missing_is_not_zero") is True, "FEE_ABSENCE_TREATED_AS_ZERO")
    _require(
        fees.get("reason") == "SANITIZED_RECEIPT_HAS_NO_FEE_COMPONENTS",
        "FEES_REASON_DRIFT",
    )

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
        "overlay_runtime_sha256": observed_runtime_sha,
        "overlay_acceptance_sha256": observed_acceptance_sha,
        "overlay_config_sha256": observed_overlay_config_sha,
        "task26_contract_sha256": observed_task26_sha,
        "overlay_terminal": OVERLAY_TERMINAL,
        "observed_out_amount": acceptance.get("observed_out_amount"),
        "observed_at": acceptance.get("observed_at"),
        "missing_facts": {
            "touch": dict(MISSING_FACTS["touch"]),
            "fillable": dict(MISSING_FACTS["fillable"]),
            "fees": dict(MISSING_FACTS["fees"]),
        },
        "unpaid_owner_phrases": list(UNPAID_OWNER_PHRASES),
        "forbidden_follow_ons": list(policy.get("forbidden_follow_ons") or []),
        "h13_or_h02_started": False,
        "h11_unparked": False,
    }
    result["terminal"] = decide_owner_fork_terminal(result)
    return result


def format_owner_readout(result: Mapping[str, Any]) -> str:
    terminal = str(result.get("terminal"))
    bound = terminal == "QUOTE_OWNER_FORK_MISSING_FACTS_NAMED"
    heading = (
        "# PMF — owner-fork: missing Touch/Fillable/fee facts named\n"
        if bound
        else "# PMF — owner-fork prerequisites drifted\n"
    )
    facts = result.get("missing_facts") if isinstance(result.get("missing_facts"), Mapping) else {}

    def _fact(name: str) -> Mapping[str, Any]:
        item = facts.get(name) if isinstance(facts, Mapping) else None
        return item if isinstance(item, Mapping) else {}

    touch = _fact("touch")
    fillable = _fact("fillable")
    fees = _fact("fees")
    phrases = result.get("unpaid_owner_phrases")
    phrase_lines = ""
    if isinstance(phrases, list):
        phrase_lines = "\n".join(f"- `{item}`" for item in phrases)
    return (
        heading
        + "\n"
        + f"**Терминальное решение:** `{terminal}`\n"
        + f"**Фраза владельца:** `{result.get('owner_phrase')}`\n"
        + "\n"
        + "Это **неоплаченный owner-fork поверх merged overlay-receipt**, "
        "не Touch, не Fillable, не execute, не alpha, не PIT и не canonical DONE.\n"
        + "\n"
        + "## Overlay, который остаётся истинным\n"
        + "\n"
        + f"- overlay terminal: `{result.get('overlay_terminal')}`\n"
        + f"- outAmount: `{result.get('observed_out_amount')}`\n"
        + f"- observed_at: `{result.get('observed_at')}`\n"
        + f"- mint: `{result.get('output_mint')}`\n"
        + f"- notional: `{result.get('notional_atomic')}`\n"
        + "- execute: `FORBIDDEN` / `INELIGIBLE` в этом пакете\n"
        + f"- provider_requests: `{result.get('provider_requests')}`\n"
        + "\n"
        + "## Какого факта не хватает\n"
        + "\n"
        + f"- Touch: `{touch.get('state')}` (`{touch.get('observed_reason')}`). "
        f"TASK-26 слой `{touch.get('task26_layer')}`. "
        f"Нужен `{touch.get('missing_fact')}`. Quote не есть Touch.\n"
        + f"- Fillable: `{fillable.get('state')}` (`{fillable.get('observed_reason')}`). "
        f"TASK-26 слой `{fillable.get('task26_layer')}`. "
        f"Нужен `{fillable.get('missing_fact')}`. Taker/execute здесь не разрешены.\n"
        + f"- fees: `{fees.get('state')}` (`{fees.get('observed_reason')}`). "
        f"TASK-26 слой `{fees.get('task26_layer')}`. "
        f"Нужен `{fees.get('missing_fact')}`. отсутствие не есть ноль.\n"
        + "\n"
        + "## Неоплаченные следующие фразы (этот атом их не исполняет)\n"
        + "\n"
        + f"{phrase_lines}\n"
        + "\n"
        + "## Можно ли execute?\n"
        + "\n"
        + "Нет. В этом пакете execute-фраза `INELIGIBLE`. `/execute` и `/build` запрещены.\n"
        + "\n"
        + "## Не делать\n"
        + "\n"
        + "- `JUPITER_EXECUTE_OR_BUILD`\n"
        + "- `TAKER_OR_SIGNER_SUPPLIED`\n"
        + "- `PROMOTE_QUOTE_TO_TOUCH_OR_FILLABLE`\n"
        + "- `MISSING_FEE_TREATED_AS_ZERO`\n"
        + "- `EXECUTE_PHRASE_OFFERED_AS_AUTHORIZED`\n"
        + "- `H11_UNPARK_OR_SAMPLE_CAMPAIGN`\n"
        + "- `H13_TRIAL`\n"
        + "- `H02_H10_H14_TRIAL`\n"
    )
