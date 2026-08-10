from __future__ import annotations

import hashlib
import json
import copy
import subprocess
import sys
import unittest
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    from solana_alpha_lab.task30_route_availability_probe import validate_probe_policy
except ModuleNotFoundError:
    validate_probe_policy = None

try:
    from solana_alpha_lab.task30_route_availability_probe import evaluate_probe
except ImportError:
    evaluate_probe = None

from solana_alpha_lab.task30_route_availability_probe import RouteAvailabilityProbeError


POLICY_PATH = ROOT / "configs" / "task30_route_availability_probe_v1.yaml"
SCHEMA_PATH = ROOT / "catalog" / "schemas" / "task30_route_availability_probe.schema.json"
FROZEN_PATH = ROOT / "configs" / "task28_rc001_registry_freeze_v1.yaml"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "task30" / "route_availability_probe_v1.json"
SCRIPT_PATH = ROOT / "scripts" / "show_task30_route_availability_probe.py"
REPORT_PATH = ROOT / "docs" / "reports" / "task30" / "route_availability_probe_readout_v1.md"
TASK_PATH = ROOT / "docs" / "tasks" / "TASK-30-route-availability-probe.md"
CONTRACT_PATH = ROOT / "docs" / "contracts" / "task30_route_availability_probe_contract_v1.md"
MODULE_PATH = ROOT / "src" / "solana_alpha_lab" / "task30_route_availability_probe.py"
DESIGN_PATH = ROOT / "docs" / "superpowers" / "specs" / "2026-08-11-task30-15m-route-availability-probe-design.md"
PLAN_PATH = ROOT / "docs" / "superpowers" / "plans" / "2026-08-11-task30-route-availability-probe.md"
ACCEPTANCE_PATH = ROOT / "docs" / "evidence" / "task30" / "a11_route_availability_probe_acceptance_v1.json"
CATALOG_CORE_PATH = ROOT / "catalog" / "assets" / "core.yaml"

ARTIFACT_PATHS = {
    "task": TASK_PATH,
    "contract": CONTRACT_PATH,
    "configuration": POLICY_PATH,
    "schema": SCHEMA_PATH,
    "fixture": FIXTURE_PATH,
    "module": MODULE_PATH,
    "script": SCRIPT_PATH,
    "report": REPORT_PATH,
    "test": Path(__file__),
    "design": DESIGN_PATH,
    "plan": PLAN_PATH,
}
CATALOG_ASSET_IDS = {
    "CONTRACT-T30-ROUTE-AVAILABILITY-PROBE-001": CONTRACT_PATH,
    "CONFIG-T30-ROUTE-AVAILABILITY-PROBE-001": POLICY_PATH,
    "SCHEMA-T30-ROUTE-AVAILABILITY-PROBE-001": SCHEMA_PATH,
    "FIXTURE-T30-ROUTE-AVAILABILITY-PROBE-001": FIXTURE_PATH,
    "MODULE-T30-ROUTE-AVAILABILITY-PROBE-001": MODULE_PATH,
    "SCRIPT-T30-ROUTE-AVAILABILITY-PROBE-001": SCRIPT_PATH,
    "REPORT-T30-ROUTE-AVAILABILITY-PROBE-001": REPORT_PATH,
    "TEST-T30-ROUTE-AVAILABILITY-PROBE-001": Path(__file__),
    "EVIDENCE-T30-A11-ROUTE-AVAILABILITY-PROBE-001": ACCEPTANCE_PATH,
}


def load_yaml(path: Path) -> dict[str, object]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def frozen_group() -> dict[str, object]:
    registry = load_yaml(FROZEN_PATH)
    groups = registry["hypothesis_groups"]
    assert isinstance(groups, list)
    return next(
        group
        for group in groups
        if group["group_id"] == "RC001-H07-H01-LIQUIDITY-RETENTION"
    )


def policy() -> dict[str, object]:
    return load_yaml(POLICY_PATH)


def stable_records(first_visible: list[int]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for slot_start, first_offset in zip((1800, 2700, 3600), first_visible, strict=True):
        for offset_seconds in (0, 15, 30, 60):
            record: dict[str, object] = {
                "slot_start": slot_start,
                "offset_seconds": offset_seconds,
                "capture_state": "TYPED_GAP" if offset_seconds < first_offset else "VALID_OBSERVATION",
            }
            if offset_seconds >= first_offset:
                record.update(
                    {
                        "expected_interval_start": slot_start,
                        "observed_interval_start": slot_start,
                        "candle_fingerprint": f"synthetic-candle-{slot_start}",
                    }
                )
            records.append(record)
    return records


def records_with(capture_state: str) -> list[dict[str, object]]:
    records = stable_records([0, 0, 0])
    records[0]["capture_state"] = capture_state
    return records


def assert_non_promoting(test_case: unittest.TestCase, result: dict[str, object]) -> None:
    claims = result["claims"]
    assert isinstance(claims, dict)
    test_case.assertTrue(claims["technical_route_only"])
    for name in ("pit_admissible", "h07_h01_evidence", "task30_trial", "execution", "numeric_netreturn"):
        test_case.assertFalse(claims[name])


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_acceptance(receipt: dict[str, object]) -> None:
    assert receipt["schema"] == "smial.task30.route-availability-probe.acceptance"
    assert receipt["schema_version"] == "1.0"
    assert receipt["task_id"] == "TASK-30"
    assert receipt["atom_id"] == "T30-A11A_ROUTE_AVAILABILITY_PROBE_OFFLINE_V1"
    assert receipt["validation_status"] == "PASS_WITH_LIMITATIONS"
    assert receipt["factory_fit_review"] == "FULL_REVIEW"
    assert receipt["state_change"] == "NONE"
    assert receipt["project_sources_disposition"]["kind"] == "NO_CHANGE"
    assert receipt["frozen_definition"]["group_id"] == "RC001-H07-H01-LIQUIDITY-RETENTION"
    assert receipt["upstream_a10"]["decision"] == "START_LABELED"
    assert set(receipt["artifact_bindings"]) == set(ARTIFACT_PATHS)
    for artifact_id, path in ARTIFACT_PATHS.items():
        binding = receipt["artifact_bindings"][artifact_id]
        assert binding["path"] == path.relative_to(ROOT).as_posix()
        assert binding["sha256"] == sha256(path)
    for value in receipt["authority"].values():
        assert value in (0, False)
    for value in receipt["side_effect_counters"].values():
        assert value in (0, False)
    for value in receipt["non_claims"].values():
        assert value is False


class Task30RouteAvailabilityProbeTests(unittest.TestCase):
    def test_tracked_policy_binds_frozen_15m_group_a10_and_zero_authority(self) -> None:
        self.assertIsNotNone(validate_probe_policy, "policy validator is missing")
        policy = load_yaml(POLICY_PATH)
        jsonschema.validate(policy, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
        validate_probe_policy(policy, frozen_group())
        self.assertEqual(policy["probe_shape"]["boundaries"], 3)
        self.assertEqual(policy["probe_shape"]["offset_seconds"], [0, 15, 30, 60])
        self.assertEqual(policy["authority"]["provider_api_rpc_wss_calls"], 0)

    def test_three_stable_boundaries_choose_latest_first_availability_as_fixed_delay(self) -> None:
        self.assertIsNotNone(evaluate_probe, "probe evaluator is missing")
        result = evaluate_probe(policy(), frozen_group(), stable_records([15, 30, 30]))
        self.assertEqual(result["decision"], "READY_FOR_FIXED_DELAY_24H_TECHNICAL_CAPTURE")
        self.assertEqual(result["recommended_fixed_delay_seconds"], 30)
        self.assertEqual(result["execution_disposition"], "CONTINUE")

    def test_process_or_monitoring_failure_stops_instead_of_becoming_a_gap(self) -> None:
        self.assertIsNotNone(evaluate_probe, "probe evaluator is missing")
        result = evaluate_probe(policy(), frozen_group(), records_with("MONITORING_LOST"))
        self.assertEqual(result["decision"], "INCONCLUSIVE")
        self.assertEqual(result["execution_disposition"], "STOP_RUN")

    def test_stable_boundaries_can_require_a_sixty_second_delay(self) -> None:
        result = evaluate_probe(policy(), frozen_group(), stable_records([60, 60, 60]))
        self.assertEqual(result["decision"], "READY_FOR_FIXED_DELAY_24H_TECHNICAL_CAPTURE")
        self.assertEqual(result["recommended_fixed_delay_seconds"], 60)
        assert_non_promoting(self, result)

    def test_later_candle_revision_rejects_fixed_delay_capture(self) -> None:
        records = stable_records([0, 0, 0])
        records[1]["candle_fingerprint"] = "synthetic-revision"
        result = evaluate_probe(policy(), frozen_group(), records)
        self.assertEqual(result["decision"], "ROUTE_NOT_READY_FOR_FIXED_DELAY_CAPTURE")
        self.assertEqual(result["execution_disposition"], "CONTINUE")
        assert_non_promoting(self, result)

    def test_wrong_interval_start_rejects_fixed_delay_capture(self) -> None:
        records = stable_records([0, 0, 0])
        records[0]["observed_interval_start"] = 900
        result = evaluate_probe(policy(), frozen_group(), records)
        self.assertEqual(result["decision"], "ROUTE_NOT_READY_FOR_FIXED_DELAY_CAPTURE")
        assert_non_promoting(self, result)

    def test_typed_gap_after_publication_is_inconclusive(self) -> None:
        records = stable_records([0, 0, 0])
        records[1]["capture_state"] = "TYPED_GAP"
        result = evaluate_probe(policy(), frozen_group(), records)
        self.assertEqual(result["decision"], "INCONCLUSIVE")
        self.assertEqual(result["execution_disposition"], "CONTINUE")
        assert_non_promoting(self, result)

    def test_duplicate_slot_offset_is_rejected_before_result(self) -> None:
        records = stable_records([0, 0, 0])
        records[-1]["slot_start"] = 1800
        records[-1]["offset_seconds"] = 0
        with self.assertRaisesRegex(RouteAvailabilityProbeError, "DUPLICATE_SLOT_OFFSET"):
            evaluate_probe(policy(), frozen_group(), records)

    def test_missing_offset_is_rejected_before_result(self) -> None:
        records = stable_records([0, 0, 0])[:-1]
        with self.assertRaisesRegex(RouteAvailabilityProbeError, "RECORD_COUNT_INVALID"):
            evaluate_probe(policy(), frozen_group(), records)

    def test_retry_and_fallback_are_rejected_before_result(self) -> None:
        for field in ("retry", "fallback"):
            with self.subTest(field=field):
                records = stable_records([0, 0, 0])
                records[0][field] = True
                with self.assertRaisesRegex(RouteAvailabilityProbeError, field.upper() + "_FORBIDDEN"):
                    evaluate_probe(policy(), frozen_group(), records)

    def test_all_capture_health_failures_stop_the_run(self) -> None:
        for state in (
            "PROCESS_NOT_STARTED",
            "RECEIPT_WRITE_FAILED",
            "PRIOR_MANIFEST_UNREADABLE",
            "MONITORING_LOST",
        ):
            with self.subTest(state=state):
                result = evaluate_probe(policy(), frozen_group(), records_with(state))
                self.assertEqual(result["decision"], "INCONCLUSIVE")
                self.assertEqual(result["execution_disposition"], "STOP_RUN")
                assert_non_promoting(self, result)

    def test_unknown_capture_state_is_rejected_before_result(self) -> None:
        records = stable_records([0, 0, 0])
        records[0]["capture_state"] = "ZERO_IS_NOT_A_STATE"
        with self.assertRaisesRegex(RouteAvailabilityProbeError, "CAPTURE_STATE_INVALID"):
            evaluate_probe(policy(), frozen_group(), records)

    def test_synthetic_fixture_reproduces_the_tracked_ready_decision(self) -> None:
        self.assertTrue(FIXTURE_PATH.exists(), "synthetic availability fixture is missing")
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        result = evaluate_probe(policy(), frozen_group(), fixture["records"])
        self.assertEqual(result, fixture["expected_result"])

    def test_cli_and_checked_in_russian_readout_are_deterministic(self) -> None:
        self.assertTrue(SCRIPT_PATH.exists(), "owner readout script is missing")
        completed = subprocess.run(
            [sys.executable, "-B", str(SCRIPT_PATH), "--format", "markdown"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(REPORT_PATH.read_text(encoding="utf-8"), completed.stdout)
        self.assertIn("не разрешает внешний запрос", completed.stdout)
        for forbidden_text in ("https://", "http://", "api_key", "raw JSON"):
            self.assertNotIn(forbidden_text, completed.stdout)

    def test_acceptance_is_hash_bound_and_cannot_promote_external_authority(self) -> None:
        self.assertTrue(ACCEPTANCE_PATH.is_file(), "A11 needs a hash-bound offline acceptance receipt")
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        assert_acceptance(receipt)
        mutations = {
            "artifact_hash": (("artifact_bindings", "configuration", "sha256"), "0" * 64),
            "authority": (("authority", "provider_api_rpc_wss_calls"), 1),
            "side_effect": (("side_effect_counters", "scheduler_or_background_processes"), 1),
            "non_claim": (("non_claims", "execution"), True),
        }
        for case_id, (path, replacement) in mutations.items():
            with self.subTest(case_id=case_id):
                candidate = copy.deepcopy(receipt)
                target = candidate
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = replacement
                with self.assertRaises(AssertionError):
                    assert_acceptance(candidate)

    def test_catalog_registers_every_a11_owner_asset(self) -> None:
        catalog = load_yaml(CATALOG_CORE_PATH)
        records = {record["asset_id"]: record for record in catalog["records"]}
        for asset_id, path in CATALOG_ASSET_IDS.items():
            with self.subTest(asset_id=asset_id):
                self.assertEqual(records[asset_id]["location"]["repository_path"], path.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    unittest.main()
