#!/usr/bin/env python3
"""Create and locally prove the exact TASK-21 H0/H1/H6 recovery archive."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_forward_recovery import (  # noqa: E402
    materialize_archive,
    sha256_file,
    verify_and_restore_archive,
)


def main() -> int:
    config = yaml.safe_load(
        (ROOT / "configs/task21_pre_h24_recovery_refresh_v1.yaml").read_text(
            encoding="utf-8"
        )
    )
    result = materialize_archive(
        repository_root=ROOT,
        source_roots=config["source_roots"],
        output_directory=ROOT / config["local"]["package_root"],
    )
    expected = config["expected_source"]
    manifest = result["manifest"]
    if manifest["file_count"] != expected["file_count"]:
        raise RuntimeError("source_file_count_drift")
    if manifest["stored_bytes"] != expected["stored_bytes"]:
        raise RuntimeError("source_stored_bytes_drift")
    for relative, expected_hash in (
        (
            config["source_roots"][0] + "/runtime_receipt.json",
            expected["h0_runtime_receipt_sha256"],
        ),
        (
            config["source_roots"][1] + "/runtime_receipt.json",
            expected["h1_runtime_receipt_sha256"],
        ),
        (
            config["source_roots"][2] + "/gap_receipt.json",
            expected["h6_gap_receipt_sha256"],
        ),
    ):
        if sha256_file(ROOT / relative) != expected_hash:
            raise RuntimeError(f"critical_source_hash_drift:{relative}")
    restore_root = (
        ROOT
        / config["local"]["isolated_restore_root"]
        / result["sha256"]
        / "local-build-proof"
    )
    restored = verify_and_restore_archive(
        archive_path=result["path"],
        expected_archive_sha256=result["sha256"],
        restore_root=restore_root,
        source_repository_root=ROOT,
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "archive": {
                    key: (value.as_posix() if isinstance(value, Path) else value)
                    for key, value in result.items()
                    if key != "manifest"
                },
                "source_inventory_sha256": manifest["source_inventory_sha256"],
                "source_file_count": manifest["file_count"],
                "source_stored_bytes": manifest["stored_bytes"],
                "local_restore": {
                    key: value
                    for key, value in restored.items()
                    if key != "manifest"
                },
                "provider_api_rpc_wss_calls": 0,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
