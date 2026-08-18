#!/usr/bin/env python3
"""Recover bounded timing evidence from one completed qualification campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.quote_native_evidence_timing_recovery import (  # noqa: E402
    TimingRecoveryError,
    recover_timing,
)


RUNTIME_RECEIPT_PATH = (
    ROOT
    / "docs/evidence/quote_native_evidence_channel_qualification"
    / "a1_quote_native_evidence_channel_qualification_runtime_receipt_v1.json"
)
RAW_ROOT = ROOT / "local/quote_native_evidence_channel_qualification"
OUTPUT_PATH = (
    ROOT
    / "docs/evidence/quote_native_evidence_channel_qualification"
    / "a1_quote_native_evidence_channel_qualification_timing_recovery_v1.json"
)
REQUIRED_HORIZON_COUNTS = {"900": 12, "3600": 12}


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise TimingRecoveryError(code)


def _source_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def _write_create_only(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise TimingRecoveryError("TIMING_RECOVERY_RECEIPT_ALREADY_EXISTS") from exc


def run_recovery(
    *,
    runtime_path: Path = RUNTIME_RECEIPT_PATH,
    raw_root: Path = RAW_ROOT,
    output_path: Path = OUTPUT_PATH,
    required_horizon_counts: Mapping[str, int] = REQUIRED_HORIZON_COUNTS,
) -> dict[str, object]:
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    _require(isinstance(runtime, Mapping), "RUNTIME_RECEIPT_INVALID")
    recovered = recover_timing(runtime, raw_root=raw_root)
    _require(
        recovered["horizon_counts"] == dict(required_horizon_counts),
        "HORIZON_COUNT_DRIFT",
    )
    output: dict[str, object] = {
        **recovered,
        "recovery_id": "QUOTE-NATIVE-EVIDENCE-CHANNEL-QUALIFICATION-TIMING-RECOVERY-001",
        "source_runtime_receipt": _source_label(runtime_path),
        "source_runtime_receipt_sha256": hashlib.sha256(runtime_path.read_bytes()).hexdigest(),
        "required_horizon_counts": dict(required_horizon_counts),
        "side_effects": {
            "provider_requests": 0,
            "credential_reads": 0,
            "retries": 0,
            "fallbacks": 0,
            "cash_spend_usd_cents": 0,
            "wallet_signer_transaction_actions": 0,
        },
        "non_claims": [
            "NO_NEW_PROVIDER_CALL",
            "NO_CREDENTIAL_READ",
            "NO_RAW_BODY_IN_GIT",
            "NO_REMOTE_OBSERVED_AT_CLAIM",
        ],
    }
    _write_create_only(output_path, output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-path", type=Path, default=RUNTIME_RECEIPT_PATH)
    parser.add_argument("--raw-root", type=Path, default=RAW_ROOT)
    parser.add_argument("--output-path", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    try:
        result = run_recovery(
            runtime_path=args.runtime_path,
            raw_root=args.raw_root,
            output_path=args.output_path,
        )
    except TimingRecoveryError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(
        json.dumps(
            {
                "ok": True,
                "verdict": result["verdict"],
                "horizon_counts": result["horizon_counts"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
