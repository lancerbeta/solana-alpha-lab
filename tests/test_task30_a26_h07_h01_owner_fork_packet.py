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

from solana_alpha_lab.task30_h07_h01_owner_fork_packet import (  # noqa: E402
    ATOM_ID,
    ILLUSTRATIVE_N1_EVALUATIONS,
    TERMINAL_OUTCOMES,
    A26IntegrityError,
    assess_spend,
    bind_frozen_a25,
    bind_registries,
    bind_reuse_candidate,
    execute_packet,
    format_owner_readout,
    load_policy,
)

CONFIG_PATH = ROOT / "configs/task30_a26_h07_h01_owner_fork_packet_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task30_a26_h07_h01_owner_fork_packet.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task30/h07_h01_owner_fork_packet_v1.json"
MODULE_PATH = ROOT / "src/solana_alpha_lab/task30_h07_h01_owner_fork_packet.py"
RUNNER_PATH = ROOT / "scripts/run_task30_a26_h07_h01_owner_fork_packet.py"


class Task30A26OwnerForkPacketTests(unittest.TestCase):
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

    def test_frozen_a25_terminal_and_hash_bind(self) -> None:
        a25 = bind_frozen_a25(ROOT, self.policy)
        expected = self.fixture["expected"]
        self.assertEqual(a25["decision"], expected["a25_terminal"])
        self.assertEqual(a25["independent_clusters"], expected["independent_clusters"])
        self.assertEqual(
            a25["minimum_clusters_for_variance_calibration"],
            expected["minimum_clusters_for_variance_calibration"],
        )
        self.assertIsNone(a25["notional_bucket_count"])
        self.assertEqual(len(a25["missing_route_feasibility_fields"]), 13)

    def test_a25_hash_drift_fails_closed(self) -> None:
        policy = copy.deepcopy(dict(self.policy))
        policy["frozen_a25"]["sha256"] = "0" * 64
        with self.assertRaises(A26IntegrityError):
            bind_frozen_a25(ROOT, policy)

    def test_current_and_predecessor_registries_have_no_quote_route(self) -> None:
        registries = bind_registries(ROOT, self.policy)
        self.assertEqual(
            registries["route_feasibility_registry_status"],
            self.fixture["expected"]["route_feasibility_registry_status"],
        )
        self.assertFalse(registries["jupiter_or_quote_route_present"])
        self.assertNotIn("JUPITER", registries["providers"])
        self.assertEqual(
            registries["helius_operations"],
            [
                "GET_SIGNATURES_FOR_ADDRESS",
                "GET_TRANSACTIONS_FOR_ADDRESS_FULL",
                "LOGS_SUBSCRIBE_MENTIONS",
            ],
        )

    def test_invented_quote_operation_fails_closed(self) -> None:
        policy = copy.deepcopy(dict(self.policy))
        policy["helius_operations"] = ["GET_QUOTE"]
        with self.assertRaises(A26IntegrityError):
            bind_registries(ROOT, policy)

    def test_reuse_candidate_does_not_grant_a_live_quote_route(self) -> None:
        reuse = bind_reuse_candidate(ROOT, self.policy)
        self.assertEqual(reuse["verdict"], "WRAP")
        self.assertEqual(reuse["decision_status"], "ACCEPT_CONTRACT_RUNTIME_DEFERRED")
        self.assertFalse(reuse["grants_quote_route"])

    def test_five_dollars_cannot_falsify_and_n1_is_not_a_parameter(self) -> None:
        result = execute_packet(ROOT, self.policy)
        expected = self.fixture["expected"]
        self.assertEqual(result["terminal_decision"], expected["terminal_decision"])
        self.assertEqual(result["task_state"], expected["task_state"])
        spend = result["proposed_spend"]
        self.assertFalse(spend["falsifies_estimand"])
        self.assertFalse(spend["can_supply_route_feasibility_fields"])
        self.assertFalse(spend["can_create_four_pool_day_clusters"])
        self.assertEqual(spend["usd_cents"], 500)
        budget = spend["quote_call_budget"]
        self.assertIsNone(budget["quote_evaluations_lower_bound"])
        self.assertEqual(budget["illustrative_n1_evaluations"], ILLUSTRATIVE_N1_EVALUATIONS)
        self.assertEqual(budget["illustrative_n1_usage"], expected["illustrative_n1_usage"])
        self.assertEqual(result["owner_forks"]["selected"], expected["owner_fork_selected"])
        self.assertEqual(result["side_effects"]["cash_spend_usd_cents"], 0)
        self.assertEqual(result["side_effects"]["provider_requests"], 0)

    def test_treating_spend_as_a_falsifier_fails_closed(self) -> None:
        a25 = bind_frozen_a25(ROOT, self.policy)
        registries = bind_registries(ROOT, self.policy)
        spend = assess_spend(self.policy, a25, registries)
        spend["falsifies_estimand"] = True
        from solana_alpha_lab.task30_h07_h01_owner_fork_packet import issue_verdict

        with self.assertRaises(A26IntegrityError):
            issue_verdict(spend)

    def test_owner_readout_is_russian_and_keeps_canonical_enums(self) -> None:
        result = execute_packet(ROOT, self.policy)
        readout = format_owner_readout(result)
        self.assertIn("не фальсифицирует", readout)
        self.assertIn("FIVE_DOLLAR_HELIUS_CANNOT_FALSIFY_OWNER_FORK_READY", readout)
        self.assertIn("REGISTRY_GAP", readout)
        self.assertIn("OK T30-A26 RETIRE_RC001_H07_H01_LIQUIDITY_RETENTION", readout)
        self.assertIn("INELIGIBLE_UNTIL_PRECONDITIONS", readout)
        self.assertIn("BLOCKED_DATA", readout)
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
