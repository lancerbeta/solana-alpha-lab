"""Offline trial: Create 195 six-field pubkeys vs TASK-40 named mint/curve.

No provider calls. Does not mutate the pinned TASK-08 decoder.
Does not call decode_pump_program_data. TASK-40/39 receipts stay immutable.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from solana_alpha_lab.pump_event_decoder import (
    MAX_EVENT_PAYLOAD_BYTES,
    MAX_STRING_BYTES,
    PROGRAM_DATA_PREFIX,
    load_pinned_pump_event_plan,
)
from solana_alpha_lab.rc002_h11_create_early_six_field_layout import (
    GETTX_FIXTURE_RELATIVE,
    gettransaction_fixture_row,
)
from solana_alpha_lab.rc002_h11_older_idl_clock_body import LOG_TRUNCATED_MARKER
from solana_alpha_lab.rc002_h11_truncation_vs_absence import (
    EXPECTED_PAGE_SHA256,
    IDL_RELATIVE,
    RETAINED_A4_RELATIVE,
    TASK40_RUNTIME_RELATIVE,
)

ATOM_ID = "RC002-H11-CREATE-SIX-FIELD-PUBKEY-IDENTITY-OFFLINE-V1"
CREATE_EVENT = "CreateEvent"
EXPECTED_NAMED_MINT = "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK"
EXPECTED_BONDING_CURVE = "ENz3D4ZoarzHZCsGeFTfswAKrSo5sHX9UUut1FLS6WgC"
TASK40_ACCEPTANCE_RELATIVE = (
    "docs/evidence/task40/a1_h11_bonding_curve_pda_gta_acceptance_v1.json"
)
TERMINAL_OUTCOMES = (
    "CREATE_PUBKEYS_MATCH_NAMED_MINT_AND_BONDING_CURVE",
    "CREATE_PUBKEYS_MISMATCH",
    "CREATE_BODY_NOT_SIX_FIELD",
    "CREATE_BODY_ABSENT",
)
SOLANA_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

_INVOKE_RE = re.compile(
    r"^Program ([1-9A-HJ-NP-Za-km-z]{32,44}) invoke \[([1-9][0-9]*)\]$"
)
_COMPLETE_RE = re.compile(
    r"^Program ([1-9A-HJ-NP-Za-km-z]{32,44}) "
    r"(?:success|failed(?:: .*)?)$"
)


class CreateSixFieldPubkeyIdentityError(ValueError):
    """A fixture, page or TASK-40 identity cannot be classified fail-closed."""


class _AttributionAbort(Exception):
    """Stack identity is corrupt; remaining logs of this transaction are dropped."""


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CreateSixFieldPubkeyIdentityError(code)
    return value


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _bump(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def encode_solana_base58(value: bytes) -> str:
    zero_prefix = len(value) - len(value.lstrip(b"\0"))
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = SOLANA_BASE58_ALPHABET[remainder] + encoded
    return ("1" * zero_prefix) + encoded


def load_task40_named_identities(repo_root: Path) -> dict[str, str]:
    path = repo_root / TASK40_ACCEPTANCE_RELATIVE
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CreateSixFieldPubkeyIdentityError("TASK40_ACCEPTANCE_JSON_INVALID") from exc
    payload = dict(_mapping(document, "TASK40_ACCEPTANCE_ROOT_INVALID"))
    named_mint = payload.get("named_mint")
    bonding_curve = payload.get("bonding_curve")
    if named_mint != EXPECTED_NAMED_MINT or bonding_curve != EXPECTED_BONDING_CURVE:
        raise CreateSixFieldPubkeyIdentityError("TASK40_IDENTITY_DRIFT")
    return {
        "named_mint": str(named_mint),
        "bonding_curve": str(bonding_curve),
    }


def _create_discriminator(repo_root: Path) -> tuple[bytes, str]:
    plan = load_pinned_pump_event_plan(repo_root / IDL_RELATIVE)
    schema = next((event for event in plan.events if event.name == CREATE_EVENT), None)
    if schema is None:
        raise CreateSixFieldPubkeyIdentityError("PINNED_CREATE_EVENT_MISSING")
    return schema.discriminator, plan.program_id


def parse_six_field_create_payload(
    payload: bytes,
    *,
    discriminator: bytes,
) -> dict[str, Any]:
    if len(payload) < 8 or payload[:8] != discriminator:
        return {"status": "DISCRIMINATOR_MISMATCH"}
    body = payload[8:]
    offset = 0
    strings: list[str] = []
    for _ in range(3):
        if offset + 4 > len(body):
            return {"status": "TRUNCATED"}
        length = int.from_bytes(body[offset : offset + 4], "little")
        offset += 4
        if length > MAX_STRING_BYTES or offset + length > len(body):
            return {"status": "TRUNCATED"}
        raw = body[offset : offset + length]
        offset += length
        try:
            strings.append(raw.decode("utf-8"))
        except UnicodeDecodeError:
            return {"status": "INVALID_UTF8"}
    remaining = len(body) - offset
    if remaining < 96:
        return {"status": "TRUNCATED"}
    mint = body[offset : offset + 32]
    bonding_curve = body[offset + 32 : offset + 64]
    user = body[offset + 64 : offset + 96]
    offset += 96
    if offset != len(body):
        return {"status": "TRAILING"}
    return {
        "status": "OK",
        "name": strings[0],
        "symbol": strings[1],
        "uri": strings[2],
        "mint": encode_solana_base58(mint),
        "bonding_curve": encode_solana_base58(bonding_curve),
        "user": encode_solana_base58(user),
    }


def decide_identity_terminal(result: Mapping[str, Any]) -> str:
    payload_len = list(result.get("payload_len") or [])
    statuses = list(result.get("parse_status") or [])
    observed = list(result.get("observed") or [])
    if not payload_len:
        return "CREATE_BODY_ABSENT"
    if any(status != "OK" for status in statuses):
        return "CREATE_BODY_NOT_SIX_FIELD"
    named_mint = result.get("named_mint")
    bonding_curve = result.get("bonding_curve")
    for fields in observed:
        mapping = dict(_mapping(fields, "OBSERVED_FIELDS_INVALID"))
        if mapping.get("mint") != named_mint or mapping.get("bonding_curve") != bonding_curve:
            return "CREATE_PUBKEYS_MISMATCH"
    return "CREATE_PUBKEYS_MATCH_NAMED_MINT_AND_BONDING_CURVE"


def identify_create_payloads(
    payloads: Sequence[bytes],
    *,
    discriminator: bytes,
    named_mint: str,
    bonding_curve: str,
) -> dict[str, Any]:
    observed: list[dict[str, str]] = []
    statuses: list[str] = []
    for payload in payloads:
        parsed = parse_six_field_create_payload(payload, discriminator=discriminator)
        statuses.append(str(parsed["status"]))
        if parsed["status"] == "OK":
            observed.append(
                {
                    "name": str(parsed["name"]),
                    "symbol": str(parsed["symbol"]),
                    "uri": str(parsed["uri"]),
                    "mint": str(parsed["mint"]),
                    "bonding_curve": str(parsed["bonding_curve"]),
                    "user": str(parsed["user"]),
                }
            )
    result = {
        "named_mint": named_mint,
        "bonding_curve": bonding_curve,
        "payload_len": [len(item) for item in payloads],
        "parse_status": statuses,
        "observed": observed,
    }
    result["terminal"] = decide_identity_terminal(result)
    return result


def _event_payload(log_line: str) -> bytes | None:
    if not log_line.startswith(PROGRAM_DATA_PREFIX):
        return None
    encoded = log_line[len(PROGRAM_DATA_PREFIX) :]
    if not encoded or encoded.strip() != encoded:
        raise _AttributionAbort("program_data_base64_not_canonical")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise _AttributionAbort("program_data_base64_invalid") from exc
    if len(payload) < 8:
        raise _AttributionAbort("program_data_discriminator_missing")
    if len(payload) > MAX_EVENT_PAYLOAD_BYTES:
        raise _AttributionAbort("program_data_payload_too_large")
    return payload


def extract_create_payloads_from_logs(
    logs: Sequence[str],
    *,
    program_id: str,
    discriminator: bytes,
    transaction_succeeded: bool,
) -> dict[str, Any]:
    stack: list[str] = []
    payloads: list[bytes] = []
    attribution_errors: dict[str, int] = {}
    for line in logs:
        if line == LOG_TRUNCATED_MARKER:
            _bump(attribution_errors, "log_truncated_marker")
            break
        invoke = _INVOKE_RE.fullmatch(line)
        if invoke:
            invoked = invoke.group(1)
            depth = int(invoke.group(2))
            if depth != len(stack) + 1:
                _bump(attribution_errors, "program_invoke_depth_invalid")
                break
            stack.append(invoked)
            continue
        complete = _COMPLETE_RE.fullmatch(line)
        if complete:
            completed = complete.group(1)
            if not stack or stack[-1] != completed:
                _bump(attribution_errors, "program_completion_stack_mismatch")
                break
            stack.pop()
            continue
        try:
            payload = _event_payload(line)
        except _AttributionAbort as exc:
            _bump(attribution_errors, str(exc))
            break
        if payload is None:
            continue
        if not stack:
            _bump(attribution_errors, "program_data_without_invocation")
            break
        if stack[-1] != program_id:
            continue
        if not transaction_succeeded:
            continue
        if payload[:8] != discriminator:
            continue
        payloads.append(payload)
    return {"payloads": payloads, "attribution_errors": attribution_errors}


def _row_logs(row: Mapping[str, Any]) -> tuple[list[str], bool]:
    mapping = dict(_mapping(row, "ROW_INVALID"))
    transaction = dict(_mapping(mapping.get("transaction") or {}, "TRANSACTION_INVALID"))
    dict(_mapping(transaction.get("message") or {}, "MESSAGE_INVALID"))
    meta = dict(_mapping(mapping.get("meta") or {}, "META_INVALID"))
    logs = meta.get("logMessages") or []
    if not isinstance(logs, Sequence) or isinstance(logs, (str, bytes)):
        raise CreateSixFieldPubkeyIdentityError("LOG_MESSAGES_INVALID")
    return [str(item) for item in logs], meta.get("err") is None


def identify_create_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    program_id: str,
    discriminator: bytes,
    named_mint: str,
    bonding_curve: str,
) -> dict[str, Any]:
    payloads: list[bytes] = []
    attribution_errors: dict[str, int] = {}
    for row in rows:
        logs, succeeded = _row_logs(row)
        extracted = extract_create_payloads_from_logs(
            logs,
            program_id=program_id,
            discriminator=discriminator,
            transaction_succeeded=succeeded,
        )
        payloads.extend(extracted["payloads"])
        for key, value in extracted["attribution_errors"].items():
            attribution_errors[key] = attribution_errors.get(key, 0) + int(value)
    identified = identify_create_payloads(
        payloads,
        discriminator=discriminator,
        named_mint=named_mint,
        bonding_curve=bonding_curve,
    )
    identified["attribution_errors"] = attribution_errors
    return identified


def classify_gettransaction_fixture_identity(repo_root: Path) -> dict[str, Any]:
    identities = load_task40_named_identities(repo_root)
    discriminator, program_id = _create_discriminator(repo_root)
    path = repo_root / GETTX_FIXTURE_RELATIVE
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CreateSixFieldPubkeyIdentityError("GETTX_FIXTURE_JSON_INVALID") from exc
    row = gettransaction_fixture_row(dict(_mapping(document, "GETTX_FIXTURE_ROOT_INVALID")))
    return identify_create_rows(
        [row],
        program_id=program_id,
        discriminator=discriminator,
        named_mint=identities["named_mint"],
        bonding_curve=identities["bonding_curve"],
    )


def _page_rows(body: bytes) -> list[dict[str, Any]]:
    try:
        document = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CreateSixFieldPubkeyIdentityError("RAW_PAGE_JSON_INVALID") from exc
    payload = dict(_mapping(document, "RAW_PAGE_ROOT_INVALID"))
    if "error" in payload:
        return []
    result = dict(_mapping(payload.get("result"), "RAW_PAGE_RESULT_INVALID"))
    rows = result.get("data")
    if not isinstance(rows, list):
        raise CreateSixFieldPubkeyIdentityError("RAW_PAGE_DATA_INVALID")
    return [dict(_mapping(row, "ROW_INVALID")) for row in rows]


def _expected_page_bytes(repo_root: Path) -> dict[int, int]:
    receipt = json.loads((repo_root / TASK40_RUNTIME_RELATIVE).read_text(encoding="utf-8"))
    pages = receipt["scan"]["pages"]
    expected: dict[int, int] = {}
    for page in pages:
        expected[int(page["page_number"])] = int(page["response_bytes"])
    return expected


def _load_retained_a4_rows(repo_root: Path) -> dict[str, Any]:
    raw_root = repo_root / RETAINED_A4_RELATIVE
    if not raw_root.exists():
        return {
            "pages_status": "RETAINED_A4_PAGES_NOT_IN_CHECKOUT",
            "raw_root": RETAINED_A4_RELATIVE,
            "rows": None,
            "page_count": 0,
            "pages": [],
        }
    bodies = sorted(raw_root.rglob("raw_response.json"))
    if not bodies:
        return {
            "pages_status": "RETAINED_A4_PAGES_NOT_IN_CHECKOUT",
            "raw_root": RETAINED_A4_RELATIVE,
            "rows": None,
            "page_count": 0,
            "pages": [],
        }
    expected_bytes = _expected_page_bytes(repo_root)
    if set(expected_bytes) != set(EXPECTED_PAGE_SHA256):
        raise CreateSixFieldPubkeyIdentityError("TASK40_PAGE_SET_DRIFT")
    observed_pages: dict[int, Path] = {}
    for path in bodies:
        match = re.search(r"page=(\d+)", path.as_posix())
        if match is None:
            raise CreateSixFieldPubkeyIdentityError("RAW_PAGE_NUMBER_MISSING")
        observed_pages[int(match.group(1))] = path
    if set(observed_pages) != set(expected_bytes):
        raise CreateSixFieldPubkeyIdentityError(
            f"RAW_PAGE_SET_INCOMPLETE:{sorted(observed_pages)}:{sorted(expected_bytes)}"
        )
    rows: list[dict[str, Any]] = []
    page_bindings: list[dict[str, Any]] = []
    for page_number in sorted(observed_pages):
        path = observed_pages[page_number]
        payload = path.read_bytes()
        observed = len(payload)
        expected = expected_bytes[page_number]
        digest = _sha256_bytes(payload)
        if expected != observed:
            raise CreateSixFieldPubkeyIdentityError(
                f"RAW_PAGE_SIZE_DRIFT:{page_number}:{expected}:{observed}"
            )
        if digest != EXPECTED_PAGE_SHA256[page_number]:
            raise CreateSixFieldPubkeyIdentityError(f"RAW_PAGE_HASH_DRIFT:{page_number}")
        page_bindings.append(
            {
                "page_number": page_number,
                "response_bytes": observed,
                "raw_sha256": digest,
            }
        )
        rows.extend(_page_rows(payload))
    return {
        "pages_status": "SCANNED",
        "raw_root": RETAINED_A4_RELATIVE,
        "rows": rows,
        "page_count": len(bodies),
        "pages": page_bindings,
    }


def scan_retained_a4_create_pubkey_identity(repo_root: Path) -> dict[str, Any]:
    identities = load_task40_named_identities(repo_root)
    discriminator, program_id = _create_discriminator(repo_root)
    gettx = classify_gettransaction_fixture_identity(repo_root)
    loaded_pages = _load_retained_a4_rows(repo_root)
    if loaded_pages["pages_status"] != "SCANNED":
        return {
            "pages_status": loaded_pages["pages_status"],
            "raw_root": loaded_pages["raw_root"],
            "scan": None,
            "gettransaction_fixture": gettx,
            "page_count": 0,
            "pages": [],
            "named_mint": identities["named_mint"],
            "bonding_curve": identities["bonding_curve"],
        }
    rows = list(loaded_pages["rows"] or [])
    scan = identify_create_rows(
        rows,
        program_id=program_id,
        discriminator=discriminator,
        named_mint=identities["named_mint"],
        bonding_curve=identities["bonding_curve"],
    )
    return {
        "pages_status": "SCANNED",
        "raw_root": loaded_pages["raw_root"],
        "page_count": loaded_pages["page_count"],
        "pages": loaded_pages["pages"],
        "scan": scan,
        "gettransaction_fixture": gettx,
        "named_mint": identities["named_mint"],
        "bonding_curve": identities["bonding_curve"],
    }
