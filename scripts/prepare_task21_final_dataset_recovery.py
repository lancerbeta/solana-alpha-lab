#!/usr/bin/env python3
"""Create and locally restore the exact TASK-21 final-dataset archive."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_forward_recovery import (  # noqa: E402
    build_source_inventory,
    canonical_json_bytes,
    materialize_archive,
    sha256_bytes,
    verify_and_restore_archive,
)


CONFIG_PATH = ROOT / "configs" / "task21_final_dataset_recovery_v1.yaml"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory_summary(source_roots: list[str]) -> dict[str, object]:
    rows = build_source_inventory(
        repository_root=ROOT,
        source_roots=source_roots,
    )
    return {
        "root_count": len(source_roots),
        "file_count": len(rows),
        "stored_bytes": sum(int(row["bytes"]) for row in rows),
        "source_inventory_sha256": sha256_bytes(canonical_json_bytes(rows)),
    }


def require_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise RuntimeError(f"{label}_drift:{actual!r}!={expected!r}")


def main() -> int:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    for item in config["protected_inputs"]:
        path = ROOT / item["path"]
        require_equal(sha256_file(path), item["sha256"], item["role"])

    all_roots: list[str] = []
    components: list[dict[str, object]] = []
    for component in config["components"]:
        roots = list(component["source_roots"])
        summary = inventory_summary(roots)
        expected_keys = {
            "file_count": "expected_file_count",
            "stored_bytes": "expected_stored_bytes",
            "source_inventory_sha256": "expected_inventory_sha256",
        }
        for key, expected_key in expected_keys.items():
            require_equal(summary[key], component[expected_key], key)
        components.append({"component_id": component["component_id"], **summary})
        all_roots.extend(roots)
    require_equal(len(all_roots), len(set(all_roots)), "source_root_uniqueness")

    full = inventory_summary(all_roots)
    for key, expected in config["full_dataset_identity"].items():
        if key in {
            "root_count",
            "file_count",
            "stored_bytes",
            "source_inventory_sha256",
        }:
            require_equal(full[key], expected, f"full_{key}")

    local = config["local_recovery"]
    package = materialize_archive(
        repository_root=ROOT,
        source_roots=all_roots,
        output_directory=ROOT / local["package_root"],
        atom_id=config["atom_id"],
        archive_prefix=local["archive_prefix"],
    )
    restore_root = (
        ROOT
        / local["local_restore_root"]
        / package["sha256"]
        / "local-build-proof"
    )
    restored = verify_and_restore_archive(
        archive_path=package["path"],
        expected_archive_sha256=package["sha256"],
        restore_root=restore_root,
        source_repository_root=ROOT,
    )
    require_equal(restored["restored_file_count"], full["file_count"], "restore_file_count")
    require_equal(restored["restored_stored_bytes"], full["stored_bytes"], "restore_bytes")
    require_equal(
        restored["restored_inventory_sha256"],
        full["source_inventory_sha256"],
        "restore_inventory",
    )
    output = {
        "status": "PASS_LOCAL_PACKAGE_AND_RESTORE",
        "task_id": config["task_id"],
        "atom_id": config["atom_id"],
        "components": components,
        "full_dataset": full,
        "archive": {
            "repository_relative_path": package["path"].relative_to(ROOT).as_posix(),
            "filename": package["filename"],
            "created": package["created"],
            "bytes": package["bytes"],
            "sha256": package["sha256"],
            "md5": package["md5"],
        },
        "local_restore": {
            "repository_relative_root": restore_root.relative_to(ROOT).as_posix(),
            "restored_file_count": restored["restored_file_count"],
            "restored_stored_bytes": restored["restored_stored_bytes"],
            "restored_inventory_sha256": restored["restored_inventory_sha256"],
            "source_unchanged": restored["source_unchanged"],
            "source_mutations": restored["source_mutations"],
            "source_deletions": restored["source_deletions"],
            "restore_overwrites": 0,
        },
        "remote_recovery_status": "PENDING_DRIVE_UPLOAD_READBACK_RESTORE",
        "provider_api_rpc_wss_calls": 0,
        "cash_spend_usd_cents": 0,
        "wallet_signer_transaction_actions": 0,
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
