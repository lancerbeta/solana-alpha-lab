from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    from solana_alpha_lab.task30_forward_raw_trade_route import (
        ForwardRawTradeRouteError,
        evaluate_forward_coverage,
        render_forward_raw_trade_route_readout,
        validate_forward_raw_trade_route_policy,
    )
except ModuleNotFoundError:
    ForwardRawTradeRouteError = ValueError
    evaluate_forward_coverage = None
    render_forward_raw_trade_route_readout = None
    validate_forward_raw_trade_route_policy = None


POLICY_PATH = ROOT / "configs" / "task30_forward_raw_trade_route_contract_v1.yaml"
SCHEMA_PATH = ROOT / "catalog" / "schemas" / "task30_forward_raw_trade_route.schema.json"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "task30" / "forward_raw_trade_route_v1.json"
FROZEN_PATH = ROOT / "configs" / "task28_rc001_registry_freeze_v1.yaml"
MODULE_PATH = ROOT / "src" / "solana_alpha_lab" / "task30_forward_raw_trade_route.py"
SCRIPT_PATH = ROOT / "scripts" / "show_task30_forward_raw_trade_route.py"
REPORT_PATH = ROOT / "docs" / "reports" / "task30" / "forward_raw_trade_route_readout_v1.md"


def load_yaml(path: Path) -> dict[str, object]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def frozen_group() -> dict[str, object]:
    groups = load_yaml(FROZEN_PATH)["hypothesis_groups"]
    assert isinstance(groups, list)
    return next(
        group
        for group in groups
        if group["group_id"] == "RC001-H07-H01-LIQUIDITY-RETENTION"
    )


def policy() -> dict[str, object]:
    return load_yaml(POLICY_PATH)


def fixture() -> dict[str, object]:
    loaded = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


class Task30ForwardRawTradeRouteTests(unittest.TestCase):
    def test_forward_raw_trade_route_module_is_available(self) -> None:
        self.assertIsNotNone(
            validate_forward_raw_trade_route_policy,
            "missing pure offline forward-route evaluator",
        )

    def test_policy_binds_frozen_consumer_and_zero_authority(self) -> None:
        self.assertIsNotNone(validate_forward_raw_trade_route_policy)
        loaded = policy()
        jsonschema.validate(loaded, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
        validate_forward_raw_trade_route_policy(loaded, frozen_group())
        authority = loaded["authority"]
        assert isinstance(authority, dict)
        self.assertTrue(all(value in (0, False) for value in authority.values()))

    def test_complete_synthetic_coverage_stays_pre_external(self) -> None:
        self.assertIsNotNone(evaluate_forward_coverage)
        result = evaluate_forward_coverage(policy(), frozen_group(), fixture()["complete_events"])
        self.assertEqual(result["coverage_state"], "COMPLETE")
        self.assertEqual(result["projection_state"], "OFFLINE_CONTRACT_VALIDATED")
        self.assertFalse(result["interval_projectable"])
        self.assertFalse(result["external_capture_authorized"])
        self.assertEqual(result["execution_disposition"], "OWNER_PACKET_REQUIRED")

    def test_unknown_interval_cannot_be_projected_as_empty_or_complete(self) -> None:
        self.assertIsNotNone(evaluate_forward_coverage)
        result = evaluate_forward_coverage(
            policy(), frozen_group(), fixture()["transport_loss_events"]
        )
        self.assertEqual(result["coverage_state"], "UNKNOWN")
        self.assertEqual(result["projection_state"], "UNKNOWN")
        self.assertFalse(result["interval_projectable"])
        self.assertEqual(result["execution_disposition"], "STOP_RUN")

    def test_adversarial_records_fail_closed(self) -> None:
        self.assertIsNotNone(evaluate_forward_coverage)
        cases = fixture()["rejected_cases"]
        assert isinstance(cases, list)
        for case in cases:
            assert isinstance(case, dict)
            with self.subTest(case_id=case["case_id"]):
                with self.assertRaisesRegex(
                    ForwardRawTradeRouteError, str(case["expected_error"])
                ):
                    evaluate_forward_coverage(policy(), frozen_group(), case["events"])

    def test_readout_is_deterministic_and_contains_no_external_surface(self) -> None:
        self.assertIsNotNone(render_forward_raw_trade_route_readout)
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
        for forbidden_text in ("https://", "http://", "api_key", "raw JSON", "price", "volume"):
            self.assertNotIn(forbidden_text, completed.stdout)


if __name__ == "__main__":
    unittest.main()
