from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_forward_collector import (  # noqa: E402
    ATOM_ID,
    MIN_FREE_SPACE_AFTER_WRITE,
    Task21CollectorError,
    build_offline_run,
    load_json,
    materialize_create_once,
)

CONFIG = ROOT / "configs/task21_thin_collector_offline_v1.yaml"
POPULATION = (
    ROOT / "tests/fixtures/task21/forward_collector_offline_population_v1.json"
)
RECOVERY = ROOT / "docs/evidence/task21/runtime_recovery_gate_receipt_v1.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(**kwargs):
    return build_offline_run(
        repo_root=ROOT,
        config_path=CONFIG,
        population_path=POPULATION,
        recovery_receipt_path=RECOVERY,
        **kwargs,
    )


class Task21ForwardCollectorOfflineTests(unittest.TestCase):
    def test_config_identity_hashes_and_zero_authority(self) -> None:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["atom_id"], ATOM_ID)
        for item in config["frozen_inputs"]:
            self.assertEqual(digest(ROOT / item["path"]), item["sha256"])
        population = config["population"]
        self.assertEqual(POPULATION.stat().st_size, population["bytes"])
        self.assertEqual(digest(POPULATION), population["sha256"])
        authority = config["authority"]
        for field in (
            "network_calls",
            "provider_api_rpc_wss_calls",
            "drive_reads",
            "drive_writes",
            "credential_use",
            "real_candidate_admissions",
            "live_collector_executions",
            "forward_raw_or_dataset_writes",
            "cash_spend_usd_cents",
            "provider_credits",
            "dependency_changes",
        ):
            self.assertEqual(authority[field], 0)

    def test_base_run_is_deterministic_and_complete(self) -> None:
        first = build()
        second = build()
        self.assertEqual(first.file_bytes, second.file_bytes)
        receipt = first.receipt
        self.assertEqual(receipt["evaluated_candidates"], 8)
        self.assertEqual(receipt["active_members"], 5)
        self.assertEqual(receipt["complete_panels"], 15)
        self.assertEqual(receipt["complete_quote_pairs"], 60)
        self.assertEqual(receipt["offline_adapter_calls"], 120)
        self.assertEqual(receipt["provider_api_rpc_wss_calls"], 0)
        self.assertEqual(receipt["missing_windows"], [])
        self.assertEqual(receipt["terminal_counts"], {"QUOTE_AVAILABLE": 120})

    def test_dependent_sell_uses_exact_buy_output(self) -> None:
        run = build()
        for line in run.records_bytes.splitlines():
            pair = json.loads(line)
            buy = pair["buy"]["quote_attempt"]
            sell = pair["sell"]["quote_attempt"]
            self.assertEqual(
                sell["input_requested_atomic"],
                buy["output_quoted_atomic"],
            )

    def test_exact_restart_deduplicates_without_overwrite(self) -> None:
        run = build()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "run"
            self.assertEqual(
                materialize_create_once(run, output),
                "CREATED_AND_READBACK_VERIFIED",
            )
            before = {
                path.name: (path.stat().st_mtime_ns, path.read_bytes())
                for path in output.iterdir()
            }
            self.assertEqual(
                materialize_create_once(run, output),
                "EXACT_DUPLICATE_RESTART_DEDUPLICATED",
            )
            after = {
                path.name: (path.stat().st_mtime_ns, path.read_bytes())
                for path in output.iterdir()
            }
            self.assertEqual(before, after)

    def test_incomplete_and_conflicting_restart_fail_closed(self) -> None:
        run = build()
        with tempfile.TemporaryDirectory() as temporary:
            incomplete = Path(temporary) / "incomplete"
            incomplete.mkdir()
            (incomplete / "records.jsonl").write_bytes(run.records_bytes)
            with self.assertRaisesRegex(
                Task21CollectorError, "incomplete_or_extra"
            ):
                materialize_create_once(run, incomplete)
            conflict = Path(temporary) / "conflict"
            self.assertEqual(
                materialize_create_once(run, conflict),
                "CREATED_AND_READBACK_VERIFIED",
            )
            (conflict / "manifest.json").write_bytes(b"{}\n")
            with self.assertRaisesRegex(
                Task21CollectorError, "conflicting_restart"
            ):
                materialize_create_once(run, conflict)

    def test_missing_window_is_explicit_and_not_rescheduled(self) -> None:
        missing = frozenset({"T21-SYNTH-MEMBER-01-W2"})
        run = build(missing_windows=missing)
        receipt = run.receipt
        self.assertEqual(receipt["complete_panels"], 14)
        self.assertEqual(receipt["complete_quote_pairs"], 56)
        self.assertEqual(receipt["offline_adapter_calls"], 112)
        self.assertEqual(len(receipt["missing_windows"]), 1)
        self.assertEqual(
            receipt["missing_windows"][0]["disposition"],
            "RETAIN_EXPLICIT_COVERAGE_LOSS_NO_SILENT_RESCHEDULE",
        )
        with self.assertRaisesRegex(
            Task21CollectorError, "missing_window_identity_invalid"
        ):
            build(missing_windows=frozenset({"UNKNOWN-W1"}))

    def test_late_evidence_is_retained_and_flagged(self) -> None:
        run = build(late_slots=frozenset({1, 120}))
        self.assertEqual(run.receipt["late_evidence_count"], 2)
        rows = [json.loads(line) for line in run.records_bytes.splitlines()]
        flags = [
            leg["late_evidence"]
            for row in rows
            for leg in (row["buy"], row["sell"])
        ]
        self.assertEqual(sum(flags), 2)
        self.assertEqual(len(flags), 120)

    def test_disk_and_call_cap_block_before_materialization(self) -> None:
        with self.assertRaisesRegex(Task21CollectorError, "disk_pressure"):
            build(available_disk_bytes=MIN_FREE_SPACE_AFTER_WRITE)
        with self.assertRaisesRegex(Task21CollectorError, "call_cap_exhaustion"):
            build(call_cap=119)

    def test_unhealthy_recovery_and_outcome_field_are_rejected(self) -> None:
        unhealthy = load_json(RECOVERY)
        unhealthy["health"]["health_state"] = "DEGRADED"
        with self.assertRaisesRegex(Task21CollectorError, "unhealthy"):
            build(recovery_override=unhealthy)
        population = load_json(POPULATION)
        population["candidates"][0]["pnl"] = 1
        with self.assertRaisesRegex(Task21CollectorError, "outcome_field"):
            build(population_override=population)

    def test_manifest_is_content_addressed_and_receipt_is_zero_external(self) -> None:
        run = build()
        manifest = run.manifest
        self.assertEqual(
            manifest["files"][0]["sha256"],
            hashlib.sha256(run.records_bytes).hexdigest(),
        )
        receipt = run.receipt
        self.assertEqual(
            receipt["manifest_sha256"],
            hashlib.sha256(run.manifest_bytes).hexdigest(),
        )
        for field in (
            "network_calls",
            "provider_api_rpc_wss_calls",
            "provider_credits",
            "cash_spend_usd_cents",
            "wallet_signer_transaction_actions",
            "drive_reads",
            "drive_writes",
            "forward_raw_or_dataset_writes",
            "real_candidate_admissions",
        ):
            self.assertEqual(receipt[field], 0)

    def test_tracked_receipt_matches_base_run(self) -> None:
        expected = ROOT / (
            "docs/evidence/task21/"
            "thin_collector_offline_dry_run_receipt_v1.json"
        )
        self.assertTrue(expected.is_file())
        receipt = json.loads(expected.read_text(encoding="utf-8"))
        self.assertEqual(receipt["dry_run"], build().receipt)
        self.assertEqual(
            receipt["runtime_artifact_receipt_sha256"],
            hashlib.sha256(build().receipt_bytes).hexdigest(),
        )
        required_faults = {
            "EXACT_DUPLICATE_RESTART_DEDUPLICATED",
            "INCOMPLETE_RESTART_FAILS_CLOSED",
            "CONFLICTING_RESTART_FAILS_CLOSED",
            "MISSING_WINDOW_RETAINED_NO_SILENT_RESCHEDULE",
            "LATE_EVIDENCE_RETAINED",
            "DISK_PRESSURE_BLOCKS_BEFORE_EXECUTION",
            "CALL_CAP_EXHAUSTION_BLOCKS_BEFORE_MATERIALIZATION",
            "UNHEALTHY_RECOVERY_GATE_BLOCKS",
            "OUTCOME_FIELD_REJECTED",
            "DETERMINISTIC_MANIFESTS_BYTE_IDENTICAL",
        }
        self.assertEqual(set(receipt["offline_fault_acceptance"]), required_faults)
        self.assertEqual(
            set(receipt["offline_fault_acceptance"].values()),
            {"PASS"},
        )

    def test_next_atom_is_separate_external_boundary(self) -> None:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(
            config["next_atom"]["atom_id"],
            "T21-A5_BOUNDED_LIVE_SHAKEDOWN_V1",
        )
        self.assertFalse(config["next_atom"]["authorized_by_atom4"])
        self.assertFalse(config["authority"]["commit"])
        self.assertFalse(config["authority"]["push"])
        self.assertFalse(config["authority"]["pull_request"])
        self.assertFalse(config["authority"]["merge"])


if __name__ == "__main__":
    unittest.main()
