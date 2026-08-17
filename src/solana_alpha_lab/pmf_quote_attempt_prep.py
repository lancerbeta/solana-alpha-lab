"""Offline PMF quote attempt-prep packet. No provider, wallet, execute or fill."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

ATOM_ID = "PMF-QUOTE-ATTEMPT-PREP-V1"
AUTHORITY_PHRASE = (
    "OK PMF-QUOTE-ATTEMPT-PREP: offline attempt contract only, no wallet, "
    "no execute, no provider"
)
CONFIG_RELATIVE = "configs/pmf_quote_attempt_prep_v1.yaml"
EXPECTED_OUTPUT_MINT = "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK"
EXPECTED_INPUT_MINT = "So11111111111111111111111111111111111111112"
EXPECTED_NOTIONAL = "10000000"
EXPECTED_ROUTE_ID = "JUPITER-SOLANA-SWAP-V2-ORDER-001"
EXPECTED_FORK_RUNTIME_SHA256 = (
    "e76e25aab611b77ab11e97ad4e6849a1f15dbd5f0f4fcc48d77bc8aa9395b1be"
)
EXPECTED_FORK_ACCEPTANCE_SHA256 = (
    "2b2bac38eb87fe36d32a40d5817b6c4e37a9f23b4a3c4fe28c1db3e15ec9a2c4"
)
EXPECTED_TASK26_CONTRACT_SHA256 = (
    "aac003cf7ba2742d310893c81af3ae4a032a52b719f2f56d80171a6486351efd"
)
FORK_TERMINAL = "QUOTE_OWNER_FORK_MISSING_FACTS_NAMED"
TERMINAL_OUTCOMES = (
    "QUOTE_ATTEMPT_PREP_BOUND_NOT_ATTEMPTED",
    "QUOTE_ATTEMPT_PREP_PREREQUISITES_DRIFT",
)
UNPAID_OWNER_PHRASES = (
    "OK PMF-QUOTE-ATTEMPT: keyed /order with taker pubkey only, no /execute, no seed in git",
)
FORBIDDEN_FOLLOW_ONS = (
    "JUPITER_EXECUTE_OR_BUILD",
    "TAKER_OR_SIGNER_SUPPLIED",
    "SEED_OR_PRIVATE_KEY_IN_GIT",
    "TRANSACTION_BYTES_IN_GIT",
    "FROZEN_QUOTE_USED_AS_ATTEMPT_QUOTE",
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
    "`ATTEMPT`",
    "`NOT_ATTEMPTED`",
    "`QUOTE` does not imply\n`ATTEMPT`",
    "attempt_id",
    "ENTRY",
)
LATER_CALL = "KEYED_JUPITER_V2_ORDER_WITH_TAKER_PUBKEY"
TAKER_LATER_SHAPE = "PUBLIC_KEY_ONLY"


class QuoteAttemptPrepError(ValueError):
    """The attempt-prep packet cannot be bound fail-closed."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise QuoteAttemptPrepError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    _require(all(type(key) is str for key in value), code)
    return value


def _sha256_file(path: Path, code: str) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise QuoteAttemptPrepError(code) from exc


def _load_yaml(path: Path, code: str) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise QuoteAttemptPrepError(code) from exc
    return dict(_mapping(document, code))


def _load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QuoteAttemptPrepError(code) from exc
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
            lowered.replace("no /execute", " ")
            .replace("no execute", " ")
            .replace("non-execute", " ")
        )
        if "execute" in remainder or "/execute" in remainder:
            return True
    return False


def decide_attempt_prep_terminal(result: Mapping[str, Any]) -> str:
    phrases = result.get("unpaid_owner_phrases")
    bound = (
        result.get("owner_phrase") == AUTHORITY_PHRASE
        and result.get("execute") == "FORBIDDEN"
        and result.get("build") == "FORBIDDEN"
        and result.get("taker") == "OMITTED_QUOTE_ONLY"
        and result.get("taker_later_shape") == TAKER_LATER_SHAPE
        and result.get("execute_phrase_status") == "INELIGIBLE"
        and result.get("attempt_status") == "NOT_ATTEMPTED"
        and result.get("attempt_id") == "RESERVED_NOT_ISSUED"
        and result.get("intent_id") == "RESERVED_NOT_ISSUED"
        and result.get("phase") == "ENTRY"
        and result.get("frozen_quote_is_attempt_quote") is False
        and result.get("later_call") == LATER_CALL
        and result.get("later_credential_read") is False
        and result.get("transaction_bytes_in_git") == "FORBIDDEN"
        and result.get("seed_in_git") == "FORBIDDEN"
        and result.get("provider_requests") == 0
        and result.get("credential_reads") == 0
        and result.get("local_raw_used_as_git_truth") is False
        and result.get("owner_fork_terminal") == FORK_TERMINAL
        and result.get("output_mint") == EXPECTED_OUTPUT_MINT
        and result.get("input_mint") == EXPECTED_INPUT_MINT
        and result.get("notional_atomic") == EXPECTED_NOTIONAL
        and isinstance(phrases, list)
        and phrases == list(UNPAID_OWNER_PHRASES)
        and not _phrase_authorizes_execute(phrases)
    )
    if bound:
        return "QUOTE_ATTEMPT_PREP_BOUND_NOT_ATTEMPTED"
    return "QUOTE_ATTEMPT_PREP_PREREQUISITES_DRIFT"


def bind_pmf_quote_attempt_prep(root: Path) -> dict[str, Any]:
    resolved = Path(root)
    policy = _load_yaml(resolved / CONFIG_RELATIVE, "ATTEMPT_PREP_POLICY_INVALID")
    _require(policy.get("atom_id") == ATOM_ID, "ATOM_DRIFT")
    _require(policy.get("owner_phrase") == AUTHORITY_PHRASE, "AUTHORITY_POLICY_DRIFT")
    _require(policy.get("execute") == "FORBIDDEN", "EXECUTE_NOT_FORBIDDEN")
    _require(policy.get("build") == "FORBIDDEN", "BUILD_NOT_FORBIDDEN")
    _require(policy.get("taker") == "OMITTED_QUOTE_ONLY", "TAKER_NOT_OMITTED")
    _require(
        policy.get("taker_later_shape") == TAKER_LATER_SHAPE,
        "TAKER_LATER_SHAPE_DRIFT",
    )
    _require(
        policy.get("execute_phrase_status") == "INELIGIBLE",
        "EXECUTE_PHRASE_NOT_INELIGIBLE",
    )
    _require(policy.get("attempt_status") == "NOT_ATTEMPTED", "ATTEMPT_ALREADY_ISSUED")
    _require(policy.get("attempt_id") == "RESERVED_NOT_ISSUED", "ATTEMPT_ID_ISSUED")
    _require(policy.get("intent_id") == "RESERVED_NOT_ISSUED", "INTENT_ID_ISSUED")
    _require(policy.get("phase") == "ENTRY", "PHASE_DRIFT")
    _require(
        policy.get("frozen_quote_is_attempt_quote") is False,
        "FROZEN_QUOTE_USED_AS_ATTEMPT_QUOTE",
    )
    _require(policy.get("later_call") == LATER_CALL, "LATER_CALL_DRIFT")
    _require(policy.get("later_credential_read") is False, "CREDENTIAL_READ_NOW")
    _require(
        policy.get("transaction_bytes_in_git") == "FORBIDDEN",
        "TX_BYTES_NOT_FORBIDDEN",
    )
    _require(policy.get("seed_in_git") == "FORBIDDEN", "SEED_NOT_FORBIDDEN")
    _require(int(policy.get("provider_requests_max", 1)) == 0, "PROVIDER_BUDGET_DRIFT")
    _require(int(policy.get("credential_reads_max", 1)) == 0, "CREDENTIAL_BUDGET_DRIFT")
    _require(policy.get("local_raw_as_git_truth") is False, "RAW_GIT_TRUTH_NOT_FORBIDDEN")
    identity = _nested(policy, "identity", "IDENTITY_INVALID")
    _require(identity.get("output_mint") == EXPECTED_OUTPUT_MINT, "OUTPUT_MINT_DRIFT")
    _require(identity.get("input_mint") == EXPECTED_INPUT_MINT, "INPUT_MINT_DRIFT")
    _require(str(identity.get("notional_atomic")) == EXPECTED_NOTIONAL, "NOTIONAL_DRIFT")
    _require(identity.get("route_id") == EXPECTED_ROUTE_ID, "ROUTE_ID_DRIFT")
    fork = _nested(policy, "owner_fork", "OWNER_FORK_SPEC_INVALID")
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

    runtime_path = resolved / str(fork.get("runtime_receipt"))
    acceptance_path = resolved / str(fork.get("acceptance"))
    task26_path = resolved / str(vocabulary.get("contract"))
    observed_runtime_sha = _sha256_file(runtime_path, "FORK_RUNTIME_UNREADABLE")
    observed_acceptance_sha = _sha256_file(
        acceptance_path, "FORK_ACCEPTANCE_UNREADABLE"
    )
    observed_task26_sha = _sha256_file(task26_path, "TASK26_UNREADABLE")
    _require(
        observed_runtime_sha == EXPECTED_FORK_RUNTIME_SHA256,
        "FORK_RUNTIME_HASH_DRIFT",
    )
    _require(
        observed_acceptance_sha == EXPECTED_FORK_ACCEPTANCE_SHA256,
        "FORK_ACCEPTANCE_HASH_DRIFT",
    )
    _require(
        observed_task26_sha == EXPECTED_TASK26_CONTRACT_SHA256,
        "TASK26_HASH_DRIFT",
    )
    _require(
        observed_runtime_sha == str(fork["runtime_receipt_sha256"]),
        "FORK_RUNTIME_POLICY_HASH_DRIFT",
    )
    _require(
        observed_acceptance_sha == str(fork["acceptance_sha256"]),
        "FORK_ACCEPTANCE_POLICY_HASH_DRIFT",
    )
    _require(
        observed_task26_sha == str(vocabulary["contract_sha256"]),
        "TASK26_POLICY_HASH_DRIFT",
    )

    task26_text = task26_path.read_text(encoding="utf-8")
    for marker in TASK26_REQUIRED_MARKERS:
        _require(marker in task26_text, "TASK26_VOCABULARY_DRIFT")

    runtime = _load_json(runtime_path, "FORK_RUNTIME_INVALID")
    acceptance = _load_json(acceptance_path, "FORK_ACCEPTANCE_INVALID")
    _require(runtime.get("terminal") == FORK_TERMINAL, "FORK_RUNTIME_TERMINAL_DRIFT")
    _require(acceptance.get("terminal") == FORK_TERMINAL, "FORK_ACCEPTANCE_TERMINAL_DRIFT")
    _require(acceptance.get("execute") == "FORBIDDEN", "FORK_EXECUTE_NOT_FORBIDDEN")
    _require(acceptance.get("output_mint") == EXPECTED_OUTPUT_MINT, "FORK_MINT_DRIFT")
    _require(
        str(acceptance.get("notional_atomic")) == EXPECTED_NOTIONAL,
        "FORK_NOTIONAL_DRIFT",
    )
    _require(
        acceptance.get("execute_phrase_status") == "INELIGIBLE",
        "FORK_EXECUTE_PHRASE_NOT_INELIGIBLE",
    )
    facts = _nested(acceptance, "missing_facts", "FORK_FACTS_INVALID")
    fillable = _nested(facts, "fillable", "FORK_FILLABLE_INVALID")
    fees = _nested(facts, "fees", "FORK_FEES_INVALID")
    _require(fillable.get("state") == "NOT_EVIDENCED", "FILLABLE_PROMOTED")
    _require(fees.get("state") == "NOT_COMPUTABLE", "FEES_PROMOTED")
    _require(fees.get("missing_is_not_zero") is True, "FEE_ABSENCE_TREATED_AS_ZERO")

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
        "taker_later_shape": TAKER_LATER_SHAPE,
        "execute_phrase_status": "INELIGIBLE",
        "attempt_status": "NOT_ATTEMPTED",
        "attempt_id": "RESERVED_NOT_ISSUED",
        "intent_id": "RESERVED_NOT_ISSUED",
        "phase": "ENTRY",
        "frozen_quote_is_attempt_quote": False,
        "later_call": LATER_CALL,
        "later_credential_named": policy.get("later_credential_named"),
        "later_credential_read": False,
        "transaction_bytes_in_git": "FORBIDDEN",
        "seed_in_git": "FORBIDDEN",
        "provider_requests": 0,
        "credential_reads": 0,
        "local_raw_used_as_git_truth": False,
        "owner_fork_runtime_sha256": observed_runtime_sha,
        "owner_fork_acceptance_sha256": observed_acceptance_sha,
        "task26_contract_sha256": observed_task26_sha,
        "owner_fork_terminal": FORK_TERMINAL,
        "observed_out_amount": acceptance.get("observed_out_amount"),
        "observed_at": acceptance.get("observed_at"),
        "unpaid_owner_phrases": list(UNPAID_OWNER_PHRASES),
        "forbidden_follow_ons": list(policy.get("forbidden_follow_ons") or []),
        "h13_or_h02_started": False,
        "h11_unparked": False,
    }
    result["terminal"] = decide_attempt_prep_terminal(result)
    return result


def format_owner_readout(result: Mapping[str, Any]) -> str:
    terminal = str(result.get("terminal"))
    bound = terminal == "QUOTE_ATTEMPT_PREP_BOUND_NOT_ATTEMPTED"
    heading = (
        "# PMF — attempt-prep: попытка ещё не начата\n"
        if bound
        else "# PMF — attempt-prep prerequisites drifted\n"
    )
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
        + "Это **бумажный контракт попытки**, не кошелёк, не `/order`, не "
        "Touch, не Fillable, не execute, не alpha и не canonical DONE.\n"
        + "\n"
        + "## Что остаётся истинным\n"
        + "\n"
        + f"- owner-fork terminal: `{result.get('owner_fork_terminal')}`\n"
        + f"- mint: `{result.get('output_mint')}`\n"
        + f"- notional: `{result.get('notional_atomic')}`\n"
        + f"- утренняя котировка outAmount: `{result.get('observed_out_amount')}` "
        f"в `{result.get('observed_at')}` — это **не** quote попытки\n"
        + f"- attempt: `{result.get('attempt_status')}` / "
        f"`{result.get('attempt_id')}`\n"
        + "- taker сейчас: `OMITTED_QUOTE_ONLY`\n"
        + "- execute: `FORBIDDEN` / `INELIGIBLE`\n"
        + f"- provider_requests: `{result.get('provider_requests')}`\n"
        + "\n"
        + "## Что можно сделать вечером (этот атом это не делает)\n"
        + "\n"
        + f"- later call: `{result.get('later_call')}`\n"
        + f"- taker later: `{result.get('taker_later_shape')}` — только pubkey, "
        "не seed\n"
        + f"- credential later: named `{result.get('later_credential_named')}`, "
        "здесь не читается\n"
        + "- `/execute` и `/build` запрещены\n"
        + "- байты транзакции не в git\n"
        + "\n"
        + "## Неоплаченная следующая фраза\n"
        + "\n"
        + f"{phrase_lines}\n"
        + "\n"
        + "## Не делать\n"
        + "\n"
        + "- `JUPITER_EXECUTE_OR_BUILD`\n"
        + "- `SEED_OR_PRIVATE_KEY_IN_GIT`\n"
        + "- `TRANSACTION_BYTES_IN_GIT`\n"
        + "- `FROZEN_QUOTE_USED_AS_ATTEMPT_QUOTE`\n"
        + "- `TAKER_OR_SIGNER_SUPPLIED` в этом пакете\n"
        + "- `H11_UNPARK_OR_SAMPLE_CAMPAIGN`\n"
    )
