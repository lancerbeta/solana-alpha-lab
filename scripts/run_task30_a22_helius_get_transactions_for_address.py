#!/usr/bin/env python3
"""Execute the single authorized TASK-30 A22 Helius request."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_helius_get_transactions_for_address import (  # noqa: E402
    A22Error,
    A22TerminalError,
    credential_free_preflight,
    execute_once,
)


AUTHORITY_PHRASE = "OK T30-A22 HELIUS_GET_TRANSACTIONS_FOR_ADDRESS_ONE_SHOT"
CONFIG_PATH = ROOT / "configs/task30_a22_helius_get_transactions_for_address_one_shot_v1.yaml"
RAW_ROOT = ROOT / "local/task30_a22_helius_get_transactions_for_address"
RUNTIME_RECEIPT_PATH = ROOT / "docs/evidence/task30/a22_helius_get_transactions_for_address_runtime_receipt_v1.json"


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise A22Error(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _format_utc(value: datetime) -> str:
    _require(value.tzinfo is not None, "CLOCK_INVALID")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_policy() -> dict[str, object]:
    value = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "POLICY_INVALID")
    return value


def _load_credential(name: str) -> str:
    try:
        value = os.environ[name]
    except KeyError as exc:
        raise A22Error("HELIUS_API_KEY_MISSING_OR_EXPIRED") from exc
    _require(bool(value.strip()), "HELIUS_API_KEY_MISSING_OR_EXPIRED")
    return value


def _validate_preflight(preflight: Mapping[str, Any]) -> None:
    _require(
        preflight.get("schema")
        == "smial.task30.helius-get-transactions-for-address.credential-free-preflight",
        "PREFLIGHT_INVALID",
    )
    _require(preflight.get("schema_version") == "1.0", "PREFLIGHT_INVALID")
    _require(preflight.get("host") == "mainnet.helius-rpc.com" and preflight.get("port") == 443, "PREFLIGHT_ROUTE_DRIFT")
    _require(
        preflight.get("dns_resolved") is True
        and preflight.get("tcp_443") is True
        and preflight.get("tls_verified") is True,
        "PREFLIGHT_FAILED",
    )
    _require(preflight.get("credential_reads") == 0, "PREFLIGHT_CREDENTIAL_READ_DRIFT")
    _require(preflight.get("provider_requests") == 0, "PREFLIGHT_PROVIDER_REQUEST_DRIFT")


def _terminal_from_error(code: str) -> str:
    if code == "HTTP_STATUS_ERROR":
        return "PROVIDER_TYPED_FAILURE"
    return "TRANSPORT_OR_COVERAGE_UNKNOWN"


def _write_create_only(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise A22Error("RUNTIME_RECEIPT_ALREADY_EXISTS") from exc


def run_capture(
    *,
    authority_phrase: str,
    policy: Mapping[str, Any] | None = None,
    raw_root: Path = RAW_ROOT,
    receipt_path: Path = RUNTIME_RECEIPT_PATH,
    preflight_fn: Callable[..., Mapping[str, Any]] = credential_free_preflight,
    credential_loader: Callable[[str], str] = _load_credential,
    executor: Callable[..., Mapping[str, Any]] = execute_once,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    nonce_factory: Callable[[], str] = lambda: secrets.token_hex(4),
) -> dict[str, object]:
    """Preflight, read one key, execute once and retain a safe tracked receipt."""

    _require(authority_phrase == AUTHORITY_PHRASE, "AUTHORITY_PHRASE_INVALID")
    selected_policy = policy or _load_policy()
    external_authority = _mapping(selected_policy.get("external_authority"), "EXTERNAL_AUTHORITY_INVALID")
    _require(external_authority.get("capture_authorized") is True, "CAPTURE_NOT_AUTHORIZED")
    _require(external_authority.get("owner_phrase") == AUTHORITY_PHRASE, "AUTHORITY_POLICY_DRIFT")
    observed_at = _format_utc(clock())
    preflight = dict(preflight_fn(selected_policy, observed_at=observed_at))
    _validate_preflight(preflight)
    credential_value = credential_loader("HELIUS_API_KEY")
    _require(
        type(credential_value) is str and bool(credential_value.strip()),
        "HELIUS_API_KEY_MISSING_OR_EXPIRED",
    )
    run_id = observed_at.replace("-", "").replace(":", "").replace("Z", "Z-") + nonce_factory()
    try:
        execution = dict(
            executor(
                selected_policy,
                credential_value,
                raw_root,
                run_id=run_id,
                observed_at=observed_at,
            )
        )
        transport = dict(_mapping(execution.get("transport"), "TRANSPORT_EVIDENCE_INVALID"))
        raw_manifest = dict(_mapping(execution.get("raw_manifest"), "RAW_MANIFEST_INVALID"))
        projection = dict(_mapping(execution.get("projection"), "PROJECTION_INVALID"))
        terminal_error: str | None = None
        terminal_outcome = str(projection.get("terminal_outcome"))
    except A22TerminalError as exc:
        evidence = exc.evidence
        transport = dict(_mapping(evidence.get("transport"), "TRANSPORT_EVIDENCE_INVALID"))
        raw_value = evidence.get("raw_manifest")
        raw_manifest = dict(_mapping(raw_value, "RAW_MANIFEST_INVALID")) if raw_value is not None else {}
        projection = {}
        terminal_error = str(exc)
        terminal_outcome = _terminal_from_error(terminal_error)
    receipt: dict[str, object] = {
        "schema": "smial.task30.helius-get-transactions-for-address.runtime-receipt",
        "schema_version": "1.0",
        "receipt_id": "EVIDENCE-T30-A22P-HELIUS-GET-TRANSACTIONS-FOR-ADDRESS-001",
        "task_id": "TASK-30",
        "atom_id": selected_policy.get("atom_id"),
        "route_id": _mapping(selected_policy.get("provider_route"), "PROVIDER_ROUTE_INVALID").get("route_id"),
        "observed_at": observed_at,
        "terminal_outcome": terminal_outcome,
        "terminal_error": terminal_error,
        "preflight": preflight,
        "transport": transport,
        "raw_retention": {
            "raw_retained": bool(raw_manifest),
            "manifest": raw_manifest or None,
        },
        "transaction_count": projection.get("transaction_count"),
        "pagination_token_present": projection.get("pagination_token_present"),
        "route_fit_for_raw_batch": projection.get("route_fit_for_raw_batch", False),
        "projection": projection or None,
        "authority": {
            "basis": "EXACT_OWNER_PHRASE",
            "credential_free_preflights": 1,
            "credential_reads": 1,
            "provider_requests": transport.get("request_count", 1),
            "retries": 0,
            "fallbacks": 0,
            "pagination_requests": 0,
            "second_provider_requests": 0,
            "cash_spend_usd_cents": 0,
        },
        "claims": dict(_mapping(selected_policy.get("claims"), "CLAIMS_INVALID")),
        "task30_state": "BLOCKED_DATA",
    }
    _write_create_only(receipt_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument("--authority", required=True)
    args = parser.parse_args()
    try:
        receipt = run_capture(authority_phrase=args.authority)
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0
    except A22Error as exc:
        print(json.dumps({"result": "STOP", "error": str(exc)}, sort_keys=True))
        return 2
    except Exception:
        print(json.dumps({"result": "STOP", "error": "UNCLASSIFIED_LOCAL_FAILURE"}, sort_keys=True))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
