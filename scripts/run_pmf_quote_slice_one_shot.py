#!/usr/bin/env python3
"""Execute the single authorized PMF Jupiter V2 quote-only GET."""

from __future__ import annotations

import argparse
import hashlib
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

from solana_alpha_lab.pmf_quote_slice import (  # noqa: E402
    EXPECTED_INPUT_MINT,
    EXPECTED_NOTIONAL,
    EXPECTED_OUTPUT_MINT,
)
from solana_alpha_lab.pmf_quote_slice_one_shot import (  # noqa: E402
    ATOM_ID,
    AUTHORITY_PHRASE,
    CONFIG_RELATIVE,
    CREDENTIAL_ALIAS,
    CREDENTIAL_NAME,
    QuoteShotError,
    QuoteShotTerminalError,
    bind_one_shot_prerequisites,
    credential_free_preflight,
    execute_once,
)

CONFIG_PATH = ROOT / CONFIG_RELATIVE
RAW_ROOT = ROOT / "local/pmf_quote_slice_one_shot"
RUNTIME_RECEIPT_PATH = (
    ROOT / "docs/evidence/pmf_quote_slice/a1_pmf_quote_slice_one_shot_runtime_receipt_v1.json"
)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise QuoteShotError(code)


def _load_policy() -> dict[str, object]:
    value = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "POLICY_INVALID")
    return value


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        key = name.strip()
        if key not in {CREDENTIAL_NAME, CREDENTIAL_ALIAS}:
            continue
        if key in os.environ and os.environ[key].strip():
            continue
        parsed = value.strip().strip("'").strip('"')
        if parsed:
            os.environ[key] = parsed


def _load_credential() -> str:
    _load_dotenv(ROOT / ".env")
    primary = os.environ.get(CREDENTIAL_NAME, "")
    alias = os.environ.get(CREDENTIAL_ALIAS, "")
    return primary.strip() or alias.strip()


def _format_utc(value: datetime) -> str:
    _require(value.tzinfo is not None, "CLOCK_INVALID")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_create_only(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise QuoteShotError("RUNTIME_RECEIPT_ALREADY_EXISTS") from exc


def _write_raw(raw_root: Path, run_id: str, body: bytes | None) -> dict[str, object] | None:
    if body is None:
        return None
    directory = raw_root / f"run={run_id}"
    directory.mkdir(parents=True, exist_ok=True)
    payload_path = directory / "order_response.json"
    payload_path.write_bytes(body)
    try:
        stored = payload_path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        stored = payload_path.name
    return {
        "path": stored,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "retention": "A4_OUTSIDE_GIT",
    }


def run_capture(
    *,
    authority_phrase: str,
    policy: Mapping[str, Any] | None = None,
    raw_root: Path = RAW_ROOT,
    receipt_path: Path = RUNTIME_RECEIPT_PATH,
    preflight_fn: Callable[..., Mapping[str, Any]] = credential_free_preflight,
    credential_loader: Callable[[], str] = _load_credential,
    executor: Callable[..., Mapping[str, Any]] = execute_once,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    nonce_factory: Callable[[], str] = lambda: secrets.token_hex(4),
    opener: object | None = None,
) -> dict[str, object]:
    _require(authority_phrase == AUTHORITY_PHRASE, "AUTHORITY_PHRASE_INVALID")
    selected_policy = dict(policy or _load_policy())
    bind_one_shot_prerequisites(ROOT, selected_policy)
    observed_at = _format_utc(clock())
    preflight = dict(preflight_fn(selected_policy, observed_at=observed_at))
    _require(preflight.get("credential_reads") == 0, "PREFLIGHT_CREDENTIAL_READ_DRIFT")
    credential_value = credential_loader()
    credential_used = bool(credential_value.strip())
    run_id = observed_at.replace("-", "").replace(":", "").replace("Z", "Z-") + nonce_factory()
    terminal_error: str | None = None
    quote: dict[str, object] | None = None
    raw_manifest: dict[str, object] | None = None
    try:
        execution = dict(
            executor(selected_policy, credential_value, opener=opener)
        )
        transport = dict(execution["transport"])
        quote = dict(execution["quote"])
        terminal_outcome = str(execution["terminal_outcome"])
        raw_manifest = _write_raw(raw_root, run_id, execution.get("body"))  # type: ignore[arg-type]
    except QuoteShotTerminalError as exc:
        evidence = exc.evidence
        transport = dict(evidence.get("transport") or {})
        raw_manifest = _write_raw(raw_root, run_id, evidence.get("body"))  # type: ignore[arg-type]
        terminal_error = str(exc)
        terminal_outcome = (
            "PROVIDER_TYPED_FAILURE" if terminal_error == "HTTP_STATUS_ERROR" else "TRANSPORT_OR_QUOTE_UNKNOWN"
        )
    request_policy = selected_policy.get("request")
    _require(isinstance(request_policy, dict), "REQUEST_INVALID")
    receipt: dict[str, object] = {
        "schema": "smial.pmf-quote-slice-one-shot.runtime-receipt",
        "schema_version": "1.0",
        "receipt_id": "EVIDENCE-PMF-QUOTE-SLICE-ONE-SHOT-001",
        "atom_id": ATOM_ID,
        "route_id": "JUPITER-SOLANA-SWAP-V2-ORDER-001",
        "observed_at": observed_at,
        "terminal_outcome": terminal_outcome,
        "terminal_error": terminal_error,
        "preflight": preflight,
        "request": {
            "input_mint": EXPECTED_INPUT_MINT,
            "output_mint": EXPECTED_OUTPUT_MINT,
            "amount": EXPECTED_NOTIONAL,
            "slippage_bps": int(request_policy["slippageBps"]),
            "taker": "OMITTED_QUOTE_ONLY",
        },
        "transport": transport,
        "quote": quote,
        "raw_retention": {
            "raw_retained": bool(raw_manifest),
            "manifest": raw_manifest,
        },
        "authority": {
            "basis": "EXACT_OWNER_PHRASE",
            "credential_free_preflights": 1,
            "credential_reads": 1 if credential_used else 0,
            "access_class": "LOCAL_ENV_CREDENTIAL" if credential_used else "KEYLESS",
            "provider_requests": transport.get("request_count", 1),
            "retries": 0,
            "fallbacks": 0,
            "execute_calls": 0,
            "build_calls": 0,
            "taker_supplied": False,
        },
        "non_claims": [
            "NO_EXECUTE",
            "NO_BUILD",
            "NO_TAKER_OR_SIGNER",
            "NO_TRANSACTION_BYTES_IN_GIT",
            "NO_ALPHA",
            "NO_LIVE_PIT",
            "NO_CASHFLOW",
            "NO_CANONICAL_DONE",
        ],
    }
    _write_create_only(receipt_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-phrase", required=True)
    args = parser.parse_args()
    try:
        receipt = run_capture(authority_phrase=args.authority_phrase)
    except QuoteShotError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 2
    print(
        json.dumps(
            {
                "ok": True,
                "terminal_outcome": receipt.get("terminal_outcome"),
                "http_status": (receipt.get("transport") or {}).get("http_status")
                if isinstance(receipt.get("transport"), dict)
                else None,
                "quote_present": receipt.get("quote") is not None,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
