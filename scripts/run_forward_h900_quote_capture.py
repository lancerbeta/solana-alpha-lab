#!/usr/bin/env python3
"""CLI for reusable forward H900 quote capture and offline mix scoring."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.document_runner import repository_git_snapshot  # noqa: E402
from solana_alpha_lab.factory.forward_h900_quote_capture import (  # noqa: E402
    AUTHORITY_PHRASE,
    ForwardCaptureError,
    complete_marker,
    credential_free_capture_preflight,
    freeze_contract,
    run_forward_capture,
)
from solana_alpha_lab.factory.forward_mix_offline import score_frozen_mix_dataset  # noqa: E402
from solana_alpha_lab.quote_native_evidence_channel_qualification import (  # noqa: E402
    load_process_credential,
)


def _emit(payload: dict[str, object], exit_code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_forward_h900_quote_capture")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--data-root", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight")
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--owner-phrase", required=True)
    capture = sub.add_parser("capture")
    capture.add_argument("--owner-phrase", required=True)
    capture.add_argument("--excluded-mints-file", type=Path, default=None)
    score = sub.add_parser("score")
    args = parser.parse_args(argv)
    repo_root = args.root.resolve()
    data_root = args.data_root
    try:
        if args.command == "preflight":
            return _emit(credential_free_capture_preflight(repo_root))
        if args.command == "freeze":
            if args.owner_phrase != AUTHORITY_PHRASE:
                return _emit({"status": "AUTHORITY_PHRASE_INVALID", "provider_requests": 0}, 2)
            snap = repository_git_snapshot(repo_root)
            return _emit(freeze_contract(repo_root=repo_root, data_root=data_root, git_sha=snap.head_sha))
        if args.command == "capture":
            extra: set[str] = set()
            if args.excluded_mints_file is not None:
                extra = {
                    line.strip()
                    for line in args.excluded_mints_file.read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.startswith("#")
                }
            receipt = run_forward_capture(
                repo_root=repo_root,
                data_root=data_root,
                authority_phrase=args.owner_phrase,
                excluded_mints=extra,
                credential_loader=lambda: load_process_credential(os.environ),
            )
            return _emit(receipt)
        if args.command == "score":
            if not complete_marker(data_root).is_file():
                return _emit({"status": "CAPTURE_RECEIPT_MISSING"}, 2)
            receipt = json.loads(complete_marker(data_root).read_text(encoding="utf-8"))
            scored = score_frozen_mix_dataset(receipt.get("rows") or [])
            from solana_alpha_lab.factory.forward_h900_quote_capture import (
                _canonical_json,
                _write_create_only,
            )

            score_path = complete_marker(data_root).with_name("SCORE.json")
            _write_create_only(
                score_path,
                _canonical_json(
                    {
                        "schema": "smial.forward-h900-quote-capture.offline-score",
                        "schema_version": "1.0",
                        "capture_terminal": receipt.get("terminal_outcome"),
                        "offline_score": scored,
                    }
                ),
            )
            return _emit(scored)
    except ForwardCaptureError as exc:
        return _emit(
            {
                "status": str(exc),
                "provider_requests": int(getattr(exc, "provider_requests", 0) or 0),
                "credential_reads": 0,
            },
            2,
        )
    return _emit({"status": "HFIC_COMMAND_NOT_READY"}, 2)


if __name__ == "__main__":
    sys.exit(main())
