from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_h07_h01_liquidity_retention_park import (  # noqa: E402
    ATOM_ID,
    AUTHORITY_PHRASE,
    TERMINAL_OUTCOMES,
    A27IntegrityError,
    bind_frozen_a26,
    bind_rc001_freeze,
    bind_retained_evidence,
    execute_park,
    format_owner_readout,
    load_policy,
    refuse_forbidden_follow_ons,
)

CONFIG_PATH = ROOT / "configs/task30_a27_h07_h01_liquidity_retention_park_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task30_a27_h07_h01_liquidity_retention_park.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task30/h07_h01_liquidity_retention_park_v1.json"
MODULE_PATH = ROOT / "src/solana_alpha_lab/task30_h07_h01_liquidity_retention_park.py"
RUNNER_PATH = ROOT / "scripts/run_task30_a27_h07_h01_liquidity_retention_park.py"


class Task30A27LiquidityRetentionParkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_policy(CONFIG_PATH)
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_policy_matches_closed_schema(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(
            yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        )
        self.assertEqual(self.policy["atom_id"], ATOM_ID)
        self.assertEqual(tuple(self.policy["terminal_outcomes"]), TERMINAL_OUTCOMES)
        self.assertEqual(
            self.policy["external_authority"]["owner_phrase"],
            AUTHORITY_PHRASE,
        )

    def test_frozen_a26_terminal_and_hash_bind(self) -> None:
        a26 = bind_frozen_a26(ROOT, self.policy)
        expected = self.fixture["expected"]
        self.assertEqual(a26["decision"], expected["a26_terminal"])
        self.assertEqual(a26["task_state"], expected["task_state"])
        self.assertTrue(a26["retire_option_present"])

    def test_a26_hash_drift_fails_closed(self) -> None:
        policy = copy.deepcopy(dict(self.policy))
        policy["frozen_a26"]["sha256"] = "0" * 64
        with self.assertRaises(A27IntegrityError):
            bind_frozen_a26(ROOT, policy)

    def test_owner_phrase_drift_fails_closed(self) -> None:
        policy = copy.deepcopy(dict(self.policy))
        policy["external_authority"]["owner_phrase"] = "OK T30-A26 FREEZE_NOTIONAL_BUCKET_SET_V1"
        with self.assertRaises(A27IntegrityError):
            bind_frozen_a26(ROOT, policy)

    def test_retained_a24_a25_a26_evidence_stays(self) -> None:
        retained = bind_retained_evidence(ROOT, self.policy)
        self.assertEqual(len(retained), 3)
        self.assertEqual(
            [item["asset_id"] for item in retained],
            [
                "EVIDENCE-T30-A24-RAW-TO-PIT-001",
                "EVIDENCE-T30-A25-H07-H01-MEASURABILITY-001",
                "EVIDENCE-T30-A26-H07-H01-OWNER-FORK-001",
            ],
        )
        self.assertTrue(all(item["disposition"] == "RETAINED" for item in retained))

    def test_retained_evidence_hash_drift_fails_closed(self) -> None:
        policy = copy.deepcopy(dict(self.policy))
        policy["retained_evidence"][0]["sha256"] = "0" * 64
        with self.assertRaises(A27IntegrityError):
            bind_retained_evidence(ROOT, policy)

    def test_rc001_freeze_is_unchanged(self) -> None:
        freeze = bind_rc001_freeze(ROOT, self.policy)
        expected = self.fixture["expected"]
        self.assertEqual(freeze["group_id"], expected["rc001_group_id"])
        self.assertEqual(freeze["definition_sha256"], expected["rc001_definition_sha256"])
        self.assertFalse(freeze["mutation_authorized"])
        self.assertEqual(freeze["admissibility_state"], "BLOCKED_DATA")

    def test_rc001_definition_drift_fails_closed(self) -> None:
        policy = copy.deepcopy(dict(self.policy))
        policy["rc001_freeze"]["required_definition_sha256"] = "0" * 64
        with self.assertRaises(A27IntegrityError):
            bind_rc001_freeze(ROOT, policy)

    def test_notional_freeze_or_trial_claims_fail_closed(self) -> None:
        policy = copy.deepcopy(dict(self.policy))
        policy["claims"]["notional_buckets_frozen"] = True
        with self.assertRaises(A27IntegrityError):
            refuse_forbidden_follow_ons(policy)
        policy = copy.deepcopy(dict(self.policy))
        policy["claims"]["h13_trial"] = True
        with self.assertRaises(A27IntegrityError):
            refuse_forbidden_follow_ons(policy)
        policy = copy.deepcopy(dict(self.policy))
        policy["claims"]["route_feasibility"] = True
        with self.assertRaises(A27IntegrityError):
            refuse_forbidden_follow_ons(policy)

    def test_park_keeps_task30_blocked_data_and_retains_science(self) -> None:
        result = execute_park(ROOT, self.policy)
        expected = self.fixture["expected"]
        self.assertEqual(result["terminal_decision"], expected["terminal_decision"])
        self.assertEqual(result["task_state"], expected["task_state"])
        self.assertEqual(result["family_status"], expected["family_status"])
        self.assertEqual(result["selected_fork"], expected["selected_fork"])
        self.assertEqual(result["priority_disposition"], expected["priority_disposition"])
        self.assertEqual(result["science_disposition"], expected["science_disposition"])
        self.assertFalse(result["deletion"])
        self.assertEqual(result["side_effects"]["cash_spend_usd_cents"], 0)
        self.assertEqual(result["side_effects"]["provider_requests"], 0)
        self.assertFalse(result["claims"]["task30_canonical_done"])
        self.assertFalse(result["claims"]["science_deleted"])

    def test_owner_readout_is_russian_and_keeps_canonical_enums(self) -> None:
        result = execute_park(ROOT, self.policy)
        readout = format_owner_readout(result)
        self.assertIn("паркуем", readout)
        self.assertIn("RC001_H07_H01_PARKED_FROM_PRIORITY_SCIENCE_RETAINED", readout)
        self.assertIn("PARKED_FROM_PRIORITY", readout)
        self.assertIn("BLOCKED_DATA", readout)
        self.assertIn("EVIDENCE-T30-A24-RAW-TO-PIT-001", readout)
        self.assertIn("EVIDENCE-T30-A25-H07-H01-MEASURABILITY-001", readout)
        self.assertIn("EVIDENCE-T30-A26-H07-H01-OWNER-FORK-001", readout)
        self.assertIn("H13_TRIAL", readout)
        self.assertNotIn("None", readout)

    def test_module_and_runner_stay_offline(self) -> None:
        blob = MODULE_PATH.read_text(encoding="utf-8") + "\n" + RUNNER_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "import urllib.request",
            "import httpx",
            "import requests",
            "socket.create_connection",
        ):
            self.assertNotIn(forbidden, blob)


if __name__ == "__main__":
    unittest.main()
