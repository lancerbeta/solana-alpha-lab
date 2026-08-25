from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "hypothesis_fast_lane.py"
CATALOG_SHA = hashlib.sha256(
    (ROOT / "catalog/schemas/experiment_spec.schema.json").read_bytes()
).hexdigest()
OWNER_FIELDS = (
    "lane",
    "status",
    "scientific_terminal",
    "reason_codes",
    "run_id_or_null",
    "git_mutation_count",
    "provider_calls_actual",
    "next_action",
)
GOLDEN_OFFLINE = (
    "configs/experiment_specs/quote_native_admissible_friction_audition_offline_v1.yaml"
)
HYPOTHESIS_DEFINITION_SHA256 = "1" * 64


def run_cli(
    *args: str,
    data_root: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged = dict(os.environ)
    if env:
        merged.update(env)
    merged["SMIAL_DATA_ROOT"] = str(data_root)
    return subprocess.run(
        [
            "uv",
            "run",
            "--locked",
            "--managed-python",
            "python",
            "-B",
            str(CLI),
            "--root",
            str(ROOT),
            *args,
        ],
        cwd=ROOT,
        env=merged,
        capture_output=True,
        text=True,
        check=False,
    )


def offline_submission_packet() -> dict[str, object]:
    import yaml

    base = yaml.safe_load((ROOT / GOLDEN_OFFLINE).read_text(encoding="utf-8"))
    base["schema_version"] = "1.1"
    base["data_bindings"] = [
        {
            "binding_id": "BINDING-CANONICAL-RECEIPT-001",
            "source_kind": "CATALOG_ASSET",
            "stable_id": "SCHEMA-EXPERIMENT-SPEC-001",
            "expected_content_sha256_or_dataset_fingerprint": CATALOG_SHA,
        }
    ]
    base["query_recipe_ids"] = []
    base["capability_id"] = "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"
    base["parameter_schema_asset_id"] = "SCHEMA-EXPERIMENT-SPEC-001"
    base["as_of"] = "2026-08-25T00:00:00Z"
    base["availability_cutoff"] = "2026-08-25T00:00:00Z"
    base["what_changed"] = ["INITIAL_FAST_LANE_CLI_FIXTURE"]
    return {
        "experiment_spec": base,
        "hypothesis_definition_sha256": HYPOTHESIS_DEFINITION_SHA256,
        "available_data_binding_ids": ["BINDING-CANONICAL-RECEIPT-001"],
        "completed_runs": {},
        "promotion_requested": False,
    }


def packet_fixture_path(directory: Path) -> Path:
    path = directory / "offline_submission.json"
    path.write_text(
        json.dumps(offline_submission_packet(), indent=2),
        encoding="utf-8",
    )
    return path


class FastLaneCliTests(unittest.TestCase):
    def assert_owner_contract(self, payload: dict[str, object]) -> None:
        for field in OWNER_FIELDS:
            self.assertIn(field, payload)
        self.assertIsInstance(payload["reason_codes"], list)
        rendered = json.dumps(payload, sort_keys=True)
        self.assertNotIn(str(ROOT), rendered)
        self.assertNotIn("SMIAL_DATA_ROOT", rendered)
        self.assertNotIn(":\\", rendered)

    def test_doctor_on_empty_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            completed = run_cli("doctor", data_root=Path(tmp))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assert_owner_contract(payload)
            self.assertEqual(payload["status"], "DOCTOR_OK")
            self.assertIn("committed_inventory_sha256", payload)
            self.assertIn("cold_rebuild_possible", payload)

    def test_verify_store_on_empty_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            completed = run_cli("verify-store", data_root=Path(tmp))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertTrue(payload["verified"])

    def test_classify_offline_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            packet = packet_fixture_path(data_root)
            completed = run_cli("classify", "--packet", str(packet), data_root=data_root)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assert_owner_contract(payload)
            self.assertEqual(payload["lane"], "FAST_LANE")
            self.assertEqual(payload["status"], "FAST_LANE_READY")

    def test_classify_missing_capability_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            packet = packet_fixture_path(data_root)
            document = json.loads(packet.read_text(encoding="utf-8"))
            document["experiment_spec"]["capability_id"] = (
                "CAP-FIXTURE-NOT-REGISTERED-001"
            )
            document["experiment_spec"]["capabilities"] = [
                "CAP-FIXTURE-NOT-REGISTERED-001"
            ]
            bad_packet = data_root / "bad.json"
            bad_packet.write_text(json.dumps(document), encoding="utf-8")
            completed = run_cli("classify", "--packet", str(bad_packet), data_root=data_root)
            self.assertEqual(completed.returncode, 2, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["lane"], "CHANGE_LANE")

    def test_commission_offline_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            packet = packet_fixture_path(data_root)
            completed = run_cli(
                "commission-offline",
                "--packet",
                str(packet),
                data_root=data_root,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assert_owner_contract(payload)
            self.assertEqual(payload["status"], "COMMISSION_OFFLINE_OK")
            self.assertTrue(payload["git_status_unchanged"])
            self.assertEqual(payload["provider_calls_actual"], 0)
            self.assertTrue(payload["replay_digest_matches"])
            self.assertGreaterEqual(payload["prior_work_match_count"], 1)
            self.assertIsNotNone(payload["run_id_or_null"])

    def test_prepare_promotion_is_prepare_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            packet = packet_fixture_path(data_root)
            commission = run_cli(
                "commission-offline",
                "--packet",
                str(packet),
                data_root=data_root,
            )
            self.assertEqual(commission.returncode, 0, commission.stderr)
            run_id = json.loads(commission.stdout)["run_id_or_null"]
            self.assertIsInstance(run_id, str)
            completed = run_cli(
                "prepare-promotion",
                "--run-id",
                run_id,
                data_root=data_root,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assert_owner_contract(payload)
            self.assertEqual(payload["lane"], "PROMOTION_LANE")
            self.assertEqual(payload["status"], "PROMOTION_PACKET_PREPARED")
            self.assertTrue(
                str(payload["logical_uri"]).startswith("smial-data://research/")
            )

    def test_rebuild_and_search_after_commission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            packet = packet_fixture_path(data_root)
            commission = run_cli(
                "commission-offline",
                "--packet",
                str(packet),
                data_root=data_root,
            )
            self.assertEqual(commission.returncode, 0, commission.stderr)
            run_id = json.loads(commission.stdout)["run_id_or_null"]
            rebuild = run_cli("rebuild-projection", data_root=data_root)
            self.assertEqual(rebuild.returncode, 0, rebuild.stderr)
            show_run = run_cli("show-run", "--run-id", run_id, data_root=data_root)
            self.assertEqual(show_run.returncode, 0, show_run.stderr)
            replay = run_cli("replay", "--run-id", run_id, data_root=data_root)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            search = run_cli(
                "search-prior-work",
                "--as-of",
                "2026-08-25T00:00:00Z",
                "--max-results",
                "5",
                "--hypothesis-version-id",
                "HYP-QUOTE-NATIVE-FRICTION-H900-V1",
                data_root=data_root,
            )
            self.assertEqual(search.returncode, 0, search.stderr)
            payload = json.loads(search.stdout)
            self.assertGreaterEqual(len(payload["results"]), 1)


if __name__ == "__main__":
    unittest.main()
