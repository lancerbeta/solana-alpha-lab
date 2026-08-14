from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import ModuleType

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/delivery_harness.py"
RADAR = ROOT / "delivery-harness/capability-radar.yaml"
CURRENT = ROOT / "tests/fixtures/delivery_harness/current_repo_events.yaml"
SYNTHETIC = ROOT / "tests/fixtures/delivery_harness/synthetic_capability_events.yaml"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("delivery_harness_radar", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("delivery harness script is not loadable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mapping(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"mapping required: {path}")
    return value


class DeliveryHarnessCapabilityRadarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()
        cls.radar = mapping(RADAR)
        cls.synthetic = mapping(SYNTHETIC)

    def test_current_repository_yields_none_and_no_authority(self) -> None:
        result = self.module.evaluate_capability_radar(
            self.radar, mapping(CURRENT)
        )
        self.assertEqual(
            result,
            {
                "decision": "NONE",
                "candidate": None,
                "install_authority": False,
                "matched_candidates": [],
            },
        )

    def test_each_complete_trigger_yields_exactly_one_candidate(self) -> None:
        expected = {
            "sentry": "SENTRY_OR_EQUIVALENT",
            "posthog": "POSTHOG_OR_EQUIVALENT",
            "clickhouse": "CLICKHOUSE_OR_REMOTE_ANALYTICS",
            "context7": "CONTEXT7_OR_DOCS_MCP",
        }
        for fixture_id, candidate_id in expected.items():
            with self.subTest(fixture=fixture_id):
                result = self.module.evaluate_capability_radar(
                    self.radar, self.synthetic["fixtures"][fixture_id]
                )
                self.assertEqual(result["decision"], "CANDIDATE")
                self.assertEqual(result["candidate"]["candidate_id"], candidate_id)
                self.assertFalse(result["install_authority"])
                self.assertEqual(result["matched_candidates"], [candidate_id])

    def test_partial_trigger_is_not_enough(self) -> None:
        partial = self.synthetic["fixtures"]["partial_unattended_runtime"]
        result = self.module.evaluate_capability_radar(self.radar, partial)
        self.assertEqual(result["decision"], "NONE")

    def test_multiple_candidates_require_replan_instead_of_list_order(self) -> None:
        result = self.module.evaluate_capability_radar(
            self.radar, self.synthetic["fixtures"]["multiple"]
        )
        self.assertEqual(result["decision"], "RADAR_REPLAN_REQUIRED")
        self.assertIsNone(result["candidate"])
        self.assertEqual(len(result["matched_candidates"]), 2)
        self.assertFalse(result["install_authority"])

    def test_unknown_or_wrong_typed_event_fails_closed(self) -> None:
        for events in (
            {"schema": "smial.delivery-harness-capability-events", "schema_version": "1.0", "events": {"unknown": True}},
            {"schema": "smial.delivery-harness-capability-events", "schema_version": "1.0", "events": {"first_unattended_runtime": 1}},
            {"schema": "wrong", "schema_version": "1.0", "events": {}},
        ):
            with self.subTest(events=events):
                with self.assertRaisesRegex(ValueError, "CAPABILITY_EVENTS_INVALID"):
                    self.module.evaluate_capability_radar(self.radar, events)


if __name__ == "__main__":
    unittest.main()
