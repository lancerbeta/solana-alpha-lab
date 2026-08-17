"""Offline PMF quote-cost overlay. No provider calls, execute or fill claims."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

ATOM_ID = "PMF-QUOTE-COST-OVERLAY-V1"
AUTHORITY_PHRASE = (
    "OK PMF-QUOTE-COST-OVERLAY: consume one-shot receipt only, no execute"
)
CONFIG_RELATIVE = "configs/pmf_quote_cost_overlay_v1.yaml"
EXPECTED_OUTPUT_MINT = "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK"
EXPECTED_INPUT_MINT = "So11111111111111111111111111111111111111112"
EXPECTED_NOTIONAL = "10000000"
EXPECTED_ROUTE_ID = "JUPITER-SOLANA-SWAP-V2-ORDER-001"
EXPECTED_RECEIPT_SHA256 = (
    "2ee2b71115b67b5129e44d08f7c29becefefd8979ad130c3174614ba7f64ba2c"
)
EXPECTED_ACCEPTANCE_SHA256 = (
    "76346f1d47ffc08afd1d5534c4b0a55820104c52c3e096fa41e5b382d77aa4a8"
)
EXPECTED_ONE_SHOT_CONFIG_SHA256 = (
    "4cbae0cb6ba69a1e3fc30912a72915d3e65e1d9f1f4d8e470c0e90a2b1a28830"
)
EXPECTED_TASK26_CONTRACT_SHA256 = (
    "aac003cf7ba2742d310893c81af3ae4a032a52b719f2f56d80171a6486351efd"
)
TASK26_CONTRACT_RELATIVE = (
    "docs/contracts/task26_execution_cost_and_netreturn_contract_v1.md"
)
TERMINAL_OUTCOMES = (
    "QUOTE_COST_OVERLAY_BOUND_FILLABLE_NOT_EVIDENCED",
    "QUOTE_COST_OVERLAY_PREREQUISITES_DRIFT",
)
FORBIDDEN_FOLLOW_ONS = (
    "JUPITER_EXECUTE_OR_BUILD",
    "SUPPLY_TAKER_OR_SIGNER",
    "PROMOTE_QUOTE_TO_TOUCH_OR_FILLABLE",
    "MISSING_FEE_TREATED_AS_ZERO",
    "NETRETURN_OR_CASHFLOW_CLAIM",
    "LOCAL_RAW_USED_AS_GIT_TRUTH",
    "H11_UNPARK_OR_SAMPLE_CAMPAIGN",
    "H13_TRIAL",
    "H02_H10_H14_TRIAL",
    "LIVE_PIT_OR_CASHFLOW_CLAIM",
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


class QuoteCostOverlayError(ValueError):
    """The overlay cannot be bound fail-closed."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise QuoteCostOverlayError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    _require(all(type(key) is str for key in value), code)
    return value


def _sha256_file(path: Path, code: str) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise QuoteCostOverlayError(code) from exc


def _load_yaml(path: Path, code: str) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise QuoteCostOverlayError(code) from exc
    return dict(_mapping(document, code))


def _load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QuoteCostOverlayError(code) from exc
    return dict(_mapping(document, code))


def _nested(mapping: Mapping[str, Any], key: str, code: str) -> Mapping[str, Any]:
    return dict(_mapping(mapping.get(key), code))


def decide_overlay_terminal(result: Mapping[str, Any]) -> str:
    layers = _nested(result, "layers", "LAYERS_INVALID")
    quote = _nested(layers, "quote", "QUOTE_LAYER_INVALID")
    touch = _nested(layers, "touch", "TOUCH_LAYER_INVALID")
    fillable = _nested(layers, "fillable", "FILLABLE_LAYER_INVALID")
    realized = _nested(layers, "realized_vwap", "REALIZED_LAYER_INVALID")
    fees = _nested(layers, "fees", "FEES_LAYER_INVALID")
    netreturn = _nested(layers, "netreturn", "NETRETURN_LAYER_INVALID")
    bound = (
        result.get("owner_phrase") == AUTHORITY_PHRASE
        and result.get("execute") == "FORBIDDEN"
        and result.get("build") == "FORBIDDEN"
        and result.get("taker") == "OMITTED_QUOTE_ONLY"
        and result.get("provider_requests") == 0
        and result.get("credential_reads") == 0
        and result.get("local_raw_used_as_git_truth") is False
        and quote.get("state") == "OBSERVED"
        and touch.get("state") == "NOT_EVIDENCED"
        and fillable.get("state") == "NOT_EVIDENCED"
        and realized.get("state") == "NOT_EVIDENCED"
        and fees.get("state") == "NOT_COMPUTABLE"
        and fees.get("missing_is_not_zero") is True
        and netreturn.get("state") == "NOT_COMPUTABLE"
        and result.get("output_mint") == EXPECTED_OUTPUT_MINT
        and result.get("input_mint") == EXPECTED_INPUT_MINT
        and result.get("notional_atomic") == EXPECTED_NOTIONAL
    )
    if bound:
        return "QUOTE_COST_OVERLAY_BOUND_FILLABLE_NOT_EVIDENCED"
    return "QUOTE_COST_OVERLAY_PREREQUISITES_DRIFT"


def bind_pmf_quote_cost_overlay(root: Path) -> dict[str, Any]:
    resolved = Path(root)
    policy = _load_yaml(resolved / CONFIG_RELATIVE, "OVERLAY_POLICY_INVALID")
    _require(policy.get("atom_id") == ATOM_ID, "ATOM_DRIFT")
    _require(policy.get("owner_phrase") == AUTHORITY_PHRASE, "AUTHORITY_POLICY_DRIFT")
    _require(policy.get("execute") == "FORBIDDEN", "EXECUTE_NOT_FORBIDDEN")
    _require(policy.get("build") == "FORBIDDEN", "BUILD_NOT_FORBIDDEN")
    _require(policy.get("taker") == "OMITTED_QUOTE_ONLY", "TAKER_NOT_OMITTED")
    _require(int(policy.get("provider_requests_max", 1)) == 0, "PROVIDER_BUDGET_DRIFT")
    _require(int(policy.get("credential_reads_max", 1)) == 0, "CREDENTIAL_BUDGET_DRIFT")
    _require(policy.get("local_raw_as_git_truth") is False, "RAW_GIT_TRUTH_NOT_FORBIDDEN")
    identity = _nested(policy, "identity", "IDENTITY_INVALID")
    _require(identity.get("output_mint") == EXPECTED_OUTPUT_MINT, "OUTPUT_MINT_DRIFT")
    _require(identity.get("input_mint") == EXPECTED_INPUT_MINT, "INPUT_MINT_DRIFT")
    _require(str(identity.get("notional_atomic")) == EXPECTED_NOTIONAL, "NOTIONAL_DRIFT")
    _require(identity.get("route_id") == EXPECTED_ROUTE_ID, "ROUTE_ID_DRIFT")

    one_shot = _nested(policy, "one_shot", "ONE_SHOT_BINDER_INVALID")
    vocabulary = _nested(policy, "task26_vocabulary", "TASK26_BINDER_INVALID")
    _require(vocabulary.get("wrap") is True, "TASK26_WRAP_REQUIRED")
    _require(vocabulary.get("invoke_synthetic_engine") is False, "TASK26_ENGINE_FORBIDDEN")

    receipt_path = resolved / str(one_shot["runtime_receipt"])
    acceptance_path = resolved / str(one_shot["acceptance"])
    one_shot_config_path = resolved / str(one_shot["config"])
    task26_path = resolved / str(vocabulary["contract"])
    observed_receipt_sha = _sha256_file(receipt_path, "ONE_SHOT_RECEIPT_UNREADABLE")
    observed_acceptance_sha = _sha256_file(acceptance_path, "ONE_SHOT_ACCEPTANCE_UNREADABLE")
    observed_config_sha = _sha256_file(one_shot_config_path, "ONE_SHOT_CONFIG_UNREADABLE")
    observed_task26_sha = _sha256_file(task26_path, "TASK26_CONTRACT_UNREADABLE")
    _require(observed_receipt_sha == EXPECTED_RECEIPT_SHA256, "ONE_SHOT_RECEIPT_HASH_DRIFT")
    _require(
        observed_acceptance_sha == EXPECTED_ACCEPTANCE_SHA256,
        "ONE_SHOT_ACCEPTANCE_HASH_DRIFT",
    )
    _require(
        observed_config_sha == EXPECTED_ONE_SHOT_CONFIG_SHA256,
        "ONE_SHOT_CONFIG_HASH_DRIFT",
    )
    _require(
        observed_task26_sha == EXPECTED_TASK26_CONTRACT_SHA256,
        "TASK26_CONTRACT_HASH_DRIFT",
    )
    _require(
        observed_receipt_sha == str(one_shot["runtime_receipt_sha256"]),
        "ONE_SHOT_RECEIPT_POLICY_HASH_DRIFT",
    )
    _require(
        observed_acceptance_sha == str(one_shot["acceptance_sha256"]),
        "ONE_SHOT_ACCEPTANCE_POLICY_HASH_DRIFT",
    )
    _require(
        observed_task26_sha == str(vocabulary["contract_sha256"]),
        "TASK26_POLICY_HASH_DRIFT",
    )

    task26_text = task26_path.read_text(encoding="utf-8")
    for marker in TASK26_REQUIRED_MARKERS:
        _require(marker in task26_text, "TASK26_VOCABULARY_DRIFT")

    receipt = _load_json(receipt_path, "ONE_SHOT_RECEIPT_INVALID")
    acceptance = _load_json(acceptance_path, "ONE_SHOT_ACCEPTANCE_INVALID")
    quote = _nested(receipt, "quote", "RECEIPT_QUOTE_INVALID")
    request = _nested(receipt, "request", "RECEIPT_REQUEST_INVALID")
    authority = _nested(receipt, "authority", "RECEIPT_AUTHORITY_INVALID")
    _require(receipt.get("terminal_outcome") == "QUOTE_OBSERVED", "QUOTE_NOT_OBSERVED")
    _require(acceptance.get("terminal") == "QUOTE_OBSERVED", "ACCEPTANCE_NOT_OBSERVED")
    _require(acceptance.get("execute") == "FORBIDDEN", "ACCEPTANCE_EXECUTE_NOT_FORBIDDEN")
    _require(quote.get("transaction_present") is False, "TRANSACTION_PRESENT")
    _require(request.get("taker") == "OMITTED_QUOTE_ONLY", "TAKER_PRESENT")
    _require(request.get("output_mint") == EXPECTED_OUTPUT_MINT, "RECEIPT_OUTPUT_MINT_DRIFT")
    _require(request.get("input_mint") == EXPECTED_INPUT_MINT, "RECEIPT_INPUT_MINT_DRIFT")
    _require(str(request.get("amount")) == EXPECTED_NOTIONAL, "RECEIPT_NOTIONAL_DRIFT")
    _require(receipt.get("route_id") == EXPECTED_ROUTE_ID, "RECEIPT_ROUTE_DRIFT")
    _require(type(quote.get("out_amount")) is str and bool(quote.get("out_amount")), "OUT_AMOUNT_MISSING")
    _require(type(quote.get("in_amount")) is str and bool(quote.get("in_amount")), "IN_AMOUNT_MISSING")
    _require("fee" not in {key.lower() for key in quote}, "FEE_FIELD_IN_SANITIZED_QUOTE")
    _require(authority.get("execute_calls") == 0, "EXECUTE_CALLS_PRESENT")
    _require(authority.get("taker_supplied") is False, "TAKER_SUPPLIED")
    observed_at = receipt.get("observed_at")
    _require(type(observed_at) is str and bool(observed_at), "OBSERVED_AT_MISSING")

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
        "provider_requests": 0,
        "credential_reads": 0,
        "local_raw_used_as_git_truth": False,
        "one_shot_receipt_sha256": observed_receipt_sha,
        "one_shot_acceptance_sha256": observed_acceptance_sha,
        "task26_contract_sha256": observed_task26_sha,
        "observed_at": observed_at,
        "slippage_bps": request.get("slippage_bps"),
        "observed_in_amount": quote.get("in_amount"),
        "observed_out_amount": quote.get("out_amount"),
        "observed_router": quote.get("router"),
        "observed_mode": quote.get("mode"),
        "transaction_present": False,
        "layers": {
            "quote": {
                "state": "OBSERVED",
                "reason": "ONE_SHOT_RECEIPT_QUOTE_OBSERVED",
            },
            "touch": {
                "state": "NOT_EVIDENCED",
                "reason": "QUOTE_IS_NOT_TOUCH",
            },
            "fillable": {
                "state": "NOT_EVIDENCED",
                "reason": "NO_TAKER_NO_TRANSACTION_NO_SIMULATE",
            },
            "realized_vwap": {
                "state": "NOT_EVIDENCED",
                "reason": "NO_FILL",
            },
            "fees": {
                "state": "NOT_COMPUTABLE",
                "reason": "SANITIZED_RECEIPT_HAS_NO_FEE_COMPONENTS",
                "missing_is_not_zero": True,
            },
            "netreturn": {
                "state": "NOT_COMPUTABLE",
                "reason": "NO_FILL_NO_FEES_NO_INVENTORY",
            },
        },
        "forbidden_follow_ons": list(policy.get("forbidden_follow_ons") or []),
        "h13_or_h02_started": False,
        "h11_unparked": False,
    }
    result["terminal"] = decide_overlay_terminal(result)
    return result


def format_owner_readout(result: Mapping[str, Any]) -> str:
    terminal = str(result.get("terminal"))
    bound = terminal == "QUOTE_COST_OVERLAY_BOUND_FILLABLE_NOT_EVIDENCED"
    heading = (
        "# PMF — quote overlay bound, Fillable not evidenced\n"
        if bound
        else "# PMF — quote-cost overlay prerequisites drifted\n"
    )
    layers = result.get("layers") if isinstance(result.get("layers"), Mapping) else {}
    def _state(name: str) -> str:
        item = layers.get(name) if isinstance(layers, Mapping) else None
        if not isinstance(item, Mapping):
            return "UNKNOWN"
        return f"{item.get('state')} ({item.get('reason')})"

    return (
        heading
        + "\n"
        f"**Терминальное решение:** `{terminal}`\n"
        f"**Фраза владельца:** `{AUTHORITY_PHRASE}`\n"
        "\n"
        "Это **офлайн-проекция наблюдаемой котировки на слои TASK-26**, "
        "не Touch, не Fillable, не execute, не alpha, не PIT и не canonical DONE.\n"
        "\n"
        "## Что спроецировано\n"
        "\n"
        f"- QUOTE: `{_state('quote')}`\n"
        f"- Touch: `{_state('touch')}`\n"
        f"- Fillable: `{_state('fillable')}`\n"
        f"- RealizedVWAP: `{_state('realized_vwap')}`\n"
        f"- fees: `{_state('fees')}`\n"
        f"- NetReturn: `{_state('netreturn')}`\n"
        f"- inAmount: `{result.get('observed_in_amount')}` lamports SOL\n"
        f"- outAmount: `{result.get('observed_out_amount')}` A24 base mint\n"
        f"- router: `{result.get('observed_router')}`\n"
        f"- observed_at: `{result.get('observed_at')}`\n"
        f"- mint: `{result.get('output_mint')}`\n"
        f"- notional: `{result.get('notional_atomic')}`\n"
        f"- execute: `{result.get('execute')}`\n"
        f"- provider_requests: `{result.get('provider_requests')}`\n"
        "\n"
        "## Почему Fillable не следует из quote\n"
        "\n"
        "TASK-26: `QUOTE` не подразумевает `ATTEMPT` или `FILL`. "
        "В one-shot `taker` опущен, `transaction` отсутствует, simulate не было. "
        "В sanitized receipt нет fee-компонентов; отсутствие не есть ноль.\n"
        "\n"
        "## Можно ли execute?\n"
        "\n"
        "Нет. `/execute` и `/build` запрещены. Это не fill и не деньги после издержек.\n"
        "\n"
        "## Не делать\n"
        "\n"
        + "\n".join(f"- `{item}`" for item in result.get("forbidden_follow_ons") or [])
        + "\n"
    )
