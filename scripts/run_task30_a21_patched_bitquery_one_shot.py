#!/usr/bin/env python3
"""Run the A21 credential-free preflight or one patched Bitquery capture."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_bitquery_named_partial_pit_route_capture import (  # noqa: E402
    CaptureContractError,
    CaptureTerminalError,
    build_unknown_stop_receipt,
    credential_free_preflight,
    execute_after_preflight,
)


CONFIG_PATH = ROOT / "configs/task30_a21_patched_bitquery_one_shot_v1.yaml"
RAW_ROOT = ROOT / "local/task30_a21_bitquery_one_shot"
PREFLIGHT_PATH = RAW_ROOT / "preflight_receipt_v1.json"
RUNTIME_RECEIPT_PATH = (
    ROOT / "docs/evidence/task30/a21p_patched_bitquery_one_shot_runtime_receipt_v1.json"
)
A21_RECEIPT_ID = "EVIDENCE-T30-A21P-PATCHED-BITQUERY-ONE-SHOT-001"
A21_ATOM_ID = "T30-A21_PATCHED_BITQUERY_ONE_SHOT_V1"
A20_RUNTIME_MARKER = "a20p_bitquery_named_partial_pit_route_capture_runtime_receipt_v1.json"


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _run_id(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def _load_policy() -> dict[str, object]:
    value = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CaptureContractError("POLICY_INVALID")
    return value


def _write_json_exclusive(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise CaptureContractError("OUTPUT_ALREADY_EXISTS") from exc


def _read_preflight() -> dict[str, object]:
    try:
        value = json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CaptureContractError("PREFLIGHT_REQUIRED") from exc
    except json.JSONDecodeError as exc:
        raise CaptureContractError("PREFLIGHT_INVALID") from exc
    if not isinstance(value, dict):
        raise CaptureContractError("PREFLIGHT_INVALID")
    return value


def _load_token_once(name: str) -> str:
    value = os.environ.pop(name, None)
    if not value:
        raise KeyError(name)
    return value


def _require_a21_paths() -> None:
    runtime = str(RUNTIME_RECEIPT_PATH).replace("\\", "/")
    if runtime.endswith(A20_RUNTIME_MARKER) or A20_RUNTIME_MARKER in runtime:
        raise CaptureContractError("A20_RECEIPT_MUTATION_ATTEMPTED")


def _require_capture_authorized(policy: dict[str, object]) -> None:
    authority = policy.get("external_authority")
    if not isinstance(authority, dict) or authority.get("capture_authorized") is not True:
        raise CaptureContractError("CAPTURE_NOT_AUTHORIZED")
    if authority.get("provider_api_graphql_calls_authorized") != 1:
        raise CaptureContractError("CAPTURE_NOT_AUTHORIZED")


def _a21_receipt_ids(receipt: dict[str, object]) -> dict[str, object]:
    receipt["receipt_id"] = A21_RECEIPT_ID
    receipt["atom_id"] = A21_ATOM_ID
    receipt["task_id"] = "TASK-30"
    return receipt


def run_preflight() -> dict[str, object]:
    observed_at = _timestamp(_now_utc())
    receipt = credential_free_preflight(_load_policy(), observed_at=observed_at)
    _write_json_exclusive(PREFLIGHT_PATH, receipt)
    return {
        "result": "PREFLIGHT_PASS",
        "observed_at": observed_at,
        "host": receipt["host"],
        "dns_resolved": receipt["dns_resolved"],
        "tcp_443": receipt["tcp_443"],
        "tls_verified": receipt["tls_verified"],
    }


def run_capture() -> dict[str, object]:
    _require_a21_paths()
    if RUNTIME_RECEIPT_PATH.exists():
        raise CaptureContractError("OUTPUT_ALREADY_EXISTS")
    captured_at = _now_utc()
    observed_at = _timestamp(captured_at)
    policy = _load_policy()
    _require_capture_authorized(policy)
    preflight = _read_preflight()
    try:
        execution = execute_after_preflight(
            policy,
            preflight,
            _load_token_once,
            RAW_ROOT,
            run_id=_run_id(captured_at),
            observed_at=observed_at,
        )
    except CaptureTerminalError as exc:
        receipt = _a21_receipt_ids(
            build_unknown_stop_receipt(
                policy,
                preflight,
                observed_at=observed_at,
                terminal_error=exc,
            )
        )
        _write_json_exclusive(RUNTIME_RECEIPT_PATH, receipt)
        transport = receipt["transport"]
        return {
            "result": "CAPTURE_TERMINAL",
            "observed_at": observed_at,
            "terminal_outcome": receipt["terminal_outcome"],
            "terminal_error": receipt["terminal_error"],
            "request_count": transport["request_count"],
            "raw_retained": receipt["raw_retention"]["raw_retained"],
        }
    projection = execution["projection"]
    if not isinstance(projection, dict):
        raise CaptureContractError("PROJECTION_INVALID")
    receipt = _a21_receipt_ids(
        {
            "schema": "smial.task30.bitquery-named-partial-pit-route-capture.runtime-receipt",
            "schema_version": "1.0",
            "receipt_id": A21_RECEIPT_ID,
            "task_id": "TASK-30",
            "atom_id": A21_ATOM_ID,
            "observed_at": observed_at,
            "route_id": projection["route_id"],
            "terminal_outcome": projection["terminal_outcome"],
            "preflight": execution["preflight"],
            "transport": execution["transport"],
            "raw_manifest": execution["raw_manifest"],
            "authority": execution["authority"],
            "projection": projection,
            "non_claims": {
                "pit_admissible": False,
                "h07_h01_evidence": False,
                "route_feasibility": False,
                "fillability": False,
                "execution": False,
                "settlement": False,
                "pnl": False,
                "numeric_netreturn": False,
                "alpha": False,
                "strategy": False,
                "task30_acceptance": False,
                "missing_is_zero_or_flat": False,
            },
            "project_sources_disposition": {"kind": "NO_CHANGE"},
        }
    )
    _write_json_exclusive(RUNTIME_RECEIPT_PATH, receipt)
    counts = projection["counts"]
    return {
        "result": "CAPTURE_TERMINAL",
        "observed_at": observed_at,
        "terminal_outcome": projection["terminal_outcome"],
        "counts": counts,
        "response_bytes": execution["transport"]["response_bytes"],
        "raw_sha256": execution["raw_manifest"]["raw_sha256"],
        "request_count": execution["transport"]["request_count"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "capture"))
    args = parser.parse_args()
    try:
        result = run_preflight() if args.command == "preflight" else run_capture()
    except CaptureContractError as exc:
        print(json.dumps({"result": "STOP", "error": str(exc)}, sort_keys=True))
        return 2
    except KeyError:
        print(json.dumps({"result": "STOP", "error": "CREDENTIAL_REQUIRED"}, sort_keys=True))
        return 2
    except Exception:
        print(json.dumps({"result": "STOP", "error": "UNCLASSIFIED_LOCAL_FAILURE"}, sort_keys=True))
        return 3
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
