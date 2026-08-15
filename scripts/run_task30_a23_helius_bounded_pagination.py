#!/usr/bin/env python3
"""Execute the authorized TASK-30 A23 bounded Helius continuation."""

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

from solana_alpha_lab.task30_helius_bounded_pagination import (  # noqa: E402
    A23Error,
    A23TerminalError,
    credential_free_preflight,
    execute_bounded_pagination,
    verify_first_page_binding,
)


AUTHORITY_PHRASE = "OK T30-A23 HELIUS_BOUNDED_PAGINATION_COMPLETE_BATCH"
CONFIG_PATH = ROOT / "configs/task30_a23_helius_bounded_pagination_complete_batch_v1.yaml"
RAW_ROOT = ROOT / "local/task30_a23_helius_bounded_pagination"
RUNTIME_RECEIPT_PATH = ROOT / "docs/evidence/task30/a23_helius_bounded_pagination_runtime_receipt_v1.json"


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise A23Error(code)


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
        raise A23Error("HELIUS_API_KEY_MISSING_OR_EXPIRED") from exc
    _require(bool(value.strip()), "HELIUS_API_KEY_MISSING_OR_EXPIRED")
    return value


def _validate_preflight(preflight: Mapping[str, Any]) -> None:
    _require(
        preflight.get("schema")
        == "smial.task30.helius-get-transactions-for-address.credential-free-preflight",
        "PREFLIGHT_INVALID",
    )
    _require(preflight.get("schema_version") == "1.0", "PREFLIGHT_INVALID")
    _require(
        preflight.get("host") == "mainnet.helius-rpc.com"
        and preflight.get("port") == 443,
        "PREFLIGHT_ROUTE_DRIFT",
    )
    _require(
        preflight.get("dns_resolved") is True
        and preflight.get("tcp_443") is True
        and preflight.get("tls_verified") is True,
        "PREFLIGHT_FAILED",
    )
    _require(preflight.get("credential_reads") == 0, "PREFLIGHT_CREDENTIAL_READ_DRIFT")
    _require(preflight.get("provider_requests") == 0, "PREFLIGHT_PROVIDER_REQUEST_DRIFT")


def _write_create_only(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise A23Error("RUNTIME_RECEIPT_ALREADY_EXISTS") from exc


def _default_a22_path(policy: Mapping[str, Any]) -> Path:
    binding = _mapping(policy.get("first_page_binding"), "FIRST_PAGE_BINDING_INVALID")
    raw_path = binding.get("raw_path")
    _require(type(raw_path) is str and raw_path, "A22_FIRST_PAGE_PATH_INVALID")
    selected = (ROOT / raw_path).resolve()
    _require(selected.is_relative_to(ROOT.resolve()), "A22_FIRST_PAGE_PATH_INVALID")
    return selected


def run_capture(
    *,
    authority_phrase: str,
    policy: Mapping[str, Any] | None = None,
    a22_raw_path: Path | None = None,
    raw_root: Path = RAW_ROOT,
    receipt_path: Path = RUNTIME_RECEIPT_PATH,
    preflight_fn: Callable[..., Mapping[str, Any]] = credential_free_preflight,
    first_page_verifier: Callable[[Mapping[str, Any], Path], object] = verify_first_page_binding,
    credential_loader: Callable[[str], str] = _load_credential,
    executor: Callable[..., Mapping[str, Any]] = execute_bounded_pagination,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    nonce_factory: Callable[[], str] = lambda: secrets.token_hex(4),
) -> dict[str, object]:
    """Preflight, read one key, paginate within caps and retain a safe receipt."""

    _require(authority_phrase == AUTHORITY_PHRASE, "AUTHORITY_PHRASE_INVALID")
    selected_policy = policy or _load_policy()
    external = _mapping(selected_policy.get("external_authority"), "EXTERNAL_AUTHORITY_INVALID")
    _require(external.get("capture_authorized") is True, "CAPTURE_NOT_AUTHORIZED")
    _require(external.get("owner_phrase") == AUTHORITY_PHRASE, "AUTHORITY_POLICY_DRIFT")
    observed_at = _format_utc(clock())
    preflight = dict(preflight_fn(selected_policy, observed_at=observed_at))
    _validate_preflight(preflight)
    selected_a22_path = a22_raw_path or _default_a22_path(selected_policy)
    first_page_verifier(selected_policy, selected_a22_path)
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
                selected_a22_path,
                raw_root,
                run_id=run_id,
                observed_at=observed_at,
            )
        )
        terminal_error: str | None = None
        terminal_outcome = str(execution.get("terminal_outcome"))
    except A23TerminalError as exc:
        execution = dict(exc.evidence)
        terminal_error = str(exc)
        if terminal_error == "PROVIDER_TYPED_FAILURE":
            terminal_outcome = "PROVIDER_TYPED_FAILURE"
        else:
            terminal_outcome = "TRANSPORT_OR_VALIDATION_STOP"
    provider_requests = execution.get("provider_requests", 0)
    _require(type(provider_requests) is int and 0 <= provider_requests <= 2, "PROVIDER_REQUEST_CAP_EXCEEDED")
    receipt: dict[str, object] = {
        "schema": "smial.task30.helius-bounded-pagination.runtime-receipt",
        "schema_version": "1.0",
        "receipt_id": "EVIDENCE-T30-A23P-HELIUS-BOUNDED-PAGINATION-001",
        "run_id": run_id,
        "task_id": "TASK-30",
        "atom_id": selected_policy.get("atom_id"),
        "route_id": _mapping(selected_policy.get("provider_route"), "PROVIDER_ROUTE_INVALID").get("route_id"),
        "observed_at": observed_at,
        "terminal_outcome": terminal_outcome,
        "terminal_error": terminal_error,
        "preflight": preflight,
        "a22_first_page_reused": execution.get("a22_first_page_reused", True),
        "a22_first_page_refetched": execution.get("a22_first_page_refetched", False),
        "provider_requests": provider_requests,
        "total_transaction_count": execution.get("total_transaction_count"),
        "new_response_bytes": execution.get("new_response_bytes", 0),
        "credits_upper_bound": execution.get("credits_upper_bound", 0),
        "page_summaries": execution.get("page_summaries", []),
        "raw_manifests": execution.get("raw_manifests", []),
        "complete_raw_batch_candidate": execution.get("complete_raw_batch_candidate", False),
        "authority": {
            "basis": "EXACT_OWNER_PHRASE",
            "credential_free_preflights": 1,
            "credential_reads": 1,
            "provider_requests": provider_requests,
            "retries": 0,
            "redirects": 0,
            "fallbacks": 0,
            "second_provider_requests": 0,
            "purchase_or_plan_changes": 0,
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
    except A23Error as exc:
        print(json.dumps({"result": "STOP", "error": str(exc)}, sort_keys=True))
        return 2
    except Exception:
        print(json.dumps({"result": "STOP", "error": "UNCLASSIFIED_LOCAL_FAILURE"}, sort_keys=True))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
