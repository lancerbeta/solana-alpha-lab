"""Offline A18 classifier for one known Solana transaction signature."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from .pumpswap_touch_probe import BoundRequest

POOL_ADDRESS = "AHTTzwf3GmVMJdxWM8v2MSxyjZj8rQR6hyAC3g9477Yj"
SIGNATURE = "65G9eRh9UpW5FcJqJpMmXvZ1Jtyi8SWCpj95JdDndn6w6KqUMVrU3GhtTgiQBoRRYZCvmNg9mEQexo6LWfw88B6v"
BASE_MINT = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
QUOTE_MINT = "So11111111111111111111111111111111111111112"
REQUEST_ID = "task30-a18-single-signature-get-transaction"
ROUTE_ID = "SOLANA-STANDARD-GET-TRANSACTION-001"
_BASE58 = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,88}$")


class A18Error(ValueError):
    """A response cannot be safely projected under the A18 contract."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise A18Error(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    _require(all(type(key) is str for key in value), code)
    return value


def _parse(body: bytes) -> Mapping[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        value = json.loads(body, object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise A18Error("JSON_INVALID") from exc
    return _mapping(value, "JSON_ROOT_INVALID")


def bind_get_transaction(signature: str = SIGNATURE) -> BoundRequest:
    _require(type(signature) is str and _BASE58.fullmatch(signature) is not None, "SIGNATURE_INVALID")
    body = json.dumps(
        {
            "id": REQUEST_ID,
            "jsonrpc": "2.0",
            "method": "getTransaction",
            "params": [
                signature,
                {"commitment": "confirmed", "encoding": "json", "maxSupportedTransactionVersion": 0},
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return BoundRequest(
        request_id=REQUEST_ID,
        transport="HTTP",
        method="POST",
        url="https://api.mainnet-beta.solana.com/",
        headers=(("accept", "application/json"), ("content-type", "application/json"), ("user-agent", "smial-task30-a18/1.0")),
        body=body,
    )


def _terminal(state: str, *, target_bound: bool = False, token_deltas: dict[str, int] | None = None) -> dict[str, object]:
    return {
        "terminal_state": state,
        "target_bound": target_bound,
        "token_deltas_atomic": token_deltas,
        "sol_delta_lamports": None,
        "price": False,
        "volume": False,
        "zero_volume": False,
        "numeric_netreturn": False,
        "task30_trial": False,
        "task30_acceptance": False,
        "alpha": False,
        "retry": False,
        "fallback": False,
        "replan": {
            "terminal_atom": True,
            "automatic_suffix_atom": False,
            "allowed_next_decisions": ["PIVOT", "ACCEPT_UNKNOWN", "DEFER", "CLOSE"],
        },
    }


def _amount(row: Mapping[str, Any]) -> int:
    token = _mapping(row.get("uiTokenAmount"), "BALANCE_AMOUNT_MISSING")
    amount = token.get("amount")
    _require(type(amount) is str and amount.isdigit(), "BALANCE_AMOUNT_INVALID")
    return int(amount)


def _balances(meta: Mapping[str, Any], field: str) -> dict[tuple[int, str], int]:
    rows = meta.get(field)
    _require(type(rows) is list, "BALANCE_LIST_INVALID")
    result: dict[tuple[int, str], int] = {}
    for row in rows:
        item = _mapping(row, "BALANCE_ROW_INVALID")
        index, mint = item.get("accountIndex"), item.get("mint")
        _require(type(index) is int and not isinstance(index, bool) and index >= 0, "BALANCE_INDEX_INVALID")
        _require(type(mint) is str and mint in {BASE_MINT, QUOTE_MINT}, "BALANCE_MINT_INVALID")
        key = (index, mint)
        _require(key not in result, "BALANCE_DUPLICATE")
        result[key] = _amount(item)
    return result


def classify_get_transaction_response(body: bytes, *, expected_signature: str = SIGNATURE) -> dict[str, object]:
    document = _parse(body)
    _require(document.get("jsonrpc") == "2.0" and document.get("id") == REQUEST_ID, "RESPONSE_IDENTITY_DRIFT")
    if "error" in document:
        _require(set(document) == {"jsonrpc", "id", "error"}, "ERROR_RESPONSE_SHAPE_DRIFT")
        return _terminal("PROVIDER_TYPED_FAILURE")
    _require(set(document) == {"jsonrpc", "id", "result"}, "RESPONSE_FIELDS_DRIFT")
    if document.get("result") is None:
        return _terminal("TRANSACTION_NULL_OR_UNAVAILABLE")
    result = _mapping(document.get("result"), "RESULT_INVALID")
    _require(set(result) == {"blockTime", "meta", "slot", "transaction", "version"} or set(result) == {"blockTime", "meta", "slot", "transaction", "transactionIndex", "version"}, "RESULT_FIELDS_DRIFT")
    transaction = _mapping(result.get("transaction"), "TRANSACTION_INVALID")
    signatures = transaction.get("signatures")
    _require(type(signatures) is list and all(type(item) is str for item in signatures), "SIGNATURES_INVALID")
    _require(expected_signature in signatures, "SIGNATURE_MISMATCH")
    message = _mapping(transaction.get("message"), "MESSAGE_INVALID")
    account_keys = message.get("accountKeys")
    _require(type(account_keys) is list and all(type(item) is str for item in account_keys), "ACCOUNT_KEYS_INVALID")
    _require(POOL_ADDRESS in account_keys, "TARGET_POOL_NOT_BOUND")
    meta = _mapping(result.get("meta"), "META_INVALID")
    _require(meta.get("err") is None, "TRANSACTION_FAILED")
    pre, post = _balances(meta, "preTokenBalances"), _balances(meta, "postTokenBalances")
    if any(mint not in {mint for _, mint in pre} or mint not in {mint for _, mint in post} for mint in (BASE_MINT, QUOTE_MINT)):
        return _terminal("TRANSACTION_PRESENT_NO_TRADE_PROJECTION", target_bound=True)
    deltas: dict[str, int] = {}
    for mint in (BASE_MINT, QUOTE_MINT):
        indices = {index for index, candidate in pre if candidate == mint} | {index for index, candidate in post if candidate == mint}
        if len(indices) != 1:
            return _terminal("TRANSACTION_PRESENT_NO_TRADE_PROJECTION", target_bound=True)
        index = next(iter(indices))
        delta = post.get((index, mint), 0) - pre.get((index, mint), 0)
        if delta == 0:
            return _terminal("TRANSACTION_PRESENT_NO_TRADE_PROJECTION", target_bound=True)
        deltas[mint] = delta
    _require(deltas[BASE_MINT] * deltas[QUOTE_MINT] < 0, "DELTA_DIRECTION_AMBIGUOUS")
    return _terminal("TRADE_DATA_CANDIDATE", target_bound=True, token_deltas=deltas)


def request_fingerprint(signature: str = SIGNATURE) -> str:
    return hashlib.sha256(bind_get_transaction(signature).body).hexdigest()
