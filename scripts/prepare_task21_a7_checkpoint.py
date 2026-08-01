#!/usr/bin/env python3
"""Evaluate and locally preserve the exact TASK-21 bounded checkpoint."""

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

from solana_alpha_lab.task21_bounded_panel_checkpoint import (  # noqa: E402
    evaluate_checkpoint,
    materialize_checkpoint_archive,
    verify_and_restore_checkpoint,
)
from solana_alpha_lab.task21_owner_pulse import build_owner_pulse  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    config = yaml.safe_load(
        (ROOT / "configs/task21_bounded_panel_checkpoint_v1.yaml").read_bytes()
    )
    for binding in config["frozen_inputs"].values():
        if not isinstance(binding, dict) or "sha256" not in binding:
            continue
        path = ROOT / binding["path"]
        if sha256(path) != binding["sha256"]:
            raise RuntimeError(f"frozen_input_hash_drift:{binding['path']}")

    run_plan = yaml.safe_load(
        (ROOT / config["frozen_inputs"]["run_plan"]["path"]).read_bytes()
    )
    pulse = build_owner_pulse(repository_root=ROOT)
    decision = evaluate_checkpoint(
        run_plan=run_plan,
        owner_pulse=pulse,
        observed=config["observed_operational_evidence"],
    )
    if decision["disposition"] != config["decision"]["disposition"]:
        raise RuntimeError("checkpoint_disposition_drift")

    recovery = config["local_recovery"]
    package = materialize_checkpoint_archive(
        repository_root=ROOT,
        source_roots=config["source_roots"],
        decision=decision,
        output_directory=ROOT / recovery["package_root"],
        archive_prefix=recovery["archive_prefix"],
    )
    restore_root = (
        ROOT
        / recovery["isolated_restore_root"]
        / package["sha256"]
        / "local-build-proof"
    )
    restored = verify_and_restore_checkpoint(
        archive_path=package["path"],
        expected_archive_sha256=package["sha256"],
        restore_root=restore_root,
        source_repository_root=ROOT,
    )
    output = {
        "status": "PASS",
        "decision": decision,
        "archive": {
            key: value.as_posix() if isinstance(value, Path) else value
            for key, value in package.items()
            if key != "manifest"
        },
        "source_file_count": package["manifest"]["file_count"],
        "source_stored_bytes": package["manifest"]["stored_bytes"],
        "source_inventory_sha256": package["manifest"][
            "source_inventory_sha256"
        ],
        "local_restore": restored,
        "remote_recovery_status": recovery["remote_status_after_local_pass"],
        "provider_api_rpc_wss_calls": 0,
        "drive_reads": 0,
        "drive_writes": 0,
        "cash_spend_usd_cents": 0,
        "wallet_signer_transaction_actions": 0,
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
