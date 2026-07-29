#!/usr/bin/env python3
"""Materialize the deterministic TASK-18 raw backup archive."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task18_backup_restore import (  # noqa: E402
    materialize_archive,
)

REPAIR_CONTRACT_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task18"
    / "content_addressed_backup_restore_contract_v1.json"
)
OUTPUT_DIRECTORY = ROOT / "local" / "task18_backup"


def main() -> int:
    result = materialize_archive(
        repository_root=ROOT,
        repair_contract_path=REPAIR_CONTRACT_PATH,
        output_directory=OUTPUT_DIRECTORY,
    )
    print(
        json.dumps(
            {
                "filename": result["filename"],
                "repository_relative_path": result["path"]
                .relative_to(ROOT)
                .as_posix(),
                "bytes": result["bytes"],
                "sha256": result["sha256"],
                "md5": result["md5"],
                "source_file_count": result["manifest"]["file_count"],
                "source_stored_bytes": result["manifest"]["stored_bytes"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
