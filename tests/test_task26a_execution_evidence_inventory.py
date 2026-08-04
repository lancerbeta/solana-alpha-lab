from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task26a_execution_evidence_inventory import (  # noqa: E402
    RESULT_EXTEND,
    Task26AInventoryError,
    build_inventory,
    canonical_json_bytes,
    sha256_bytes,
)


INVENTORY_PATH = ROOT / "docs/evidence/task26a/a1_execution_evidence_inventory_v1.json"
ACCEPTANCE_PATH = (
    ROOT / "docs/evidence/task26a/a1_execution_evidence_inventory_acceptance_v1.json"
)
FIXTURE_PATH = ROOT / "tests/fixtures/task26a/execution_evidence_inventory_v1.json"


class Task26AInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inventory = build_inventory(ROOT)

    def test_01_decision_is_extend_without_netreturn(self) -> None:
        self.assertEqual(self.inventory["decision"]["result"], RESULT_EXTEND)
        self.assertFalse(self.inventory["decision"]["promotion_authority"])
        self.assertFalse(self.inventory["decision"]["task27_authority"])
        summary = self.inventory["population_summary"]
        self.assertEqual(summary["quote_pairs"], 36)
        self.assertEqual(summary["quote_cost_input_ready_pairs"], 35)
        self.assertEqual(summary["latency_blocked_pairs"], 1)
        self.assertEqual(summary["pairs_with_complete_fee_evidence"], 0)
        self.assertEqual(summary["pairs_with_settled_cashflow"], 0)
        self.assertEqual(summary["numeric_modeled_netreturn_claims"], 0)
        self.assertEqual(summary["observed_netreturn_claims"], 0)

    def test_02_required_components_are_missing_or_unknown(self) -> None:
        by_id = {
            row["component_id"]: row for row in self.inventory["component_inventory"]
        }
        self.assertEqual(by_id["fee_chargeability"]["availability_status"], "MISSING")
        self.assertEqual(by_id["send_attempt"]["availability_status"], "MISSING")
        self.assertEqual(by_id["landing"]["availability_status"], "MISSING")
        self.assertEqual(by_id["inventory"]["availability_status"], "UNKNOWN")
        self.assertEqual(by_id["settlement"]["availability_status"], "MISSING")
        for row in by_id.values():
            self.assertNotIn(row["missingness_reason"], {"0", "false", "flat", "settled"})

    def test_03_side_effects_are_zero(self) -> None:
        for key, value in self.inventory["side_effect_counters"].items():
            with self.subTest(key=key):
                self.assertEqual(value, 0)

    def test_04_written_inventory_matches_builder_and_fixture(self) -> None:
        built = canonical_json_bytes(self.inventory)
        written = INVENTORY_PATH.read_bytes()
        fixture = FIXTURE_PATH.read_bytes()
        self.assertEqual(written, built)
        self.assertEqual(fixture, built)
        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            acceptance["artifact_bindings"]["inventory"]["sha256"],
            sha256_bytes(built),
        )
        self.assertEqual(
            acceptance["decision"]["result"],
            RESULT_EXTEND,
        )

    def test_05_input_hash_drift_fails_closed(self) -> None:
        with self.assertRaises(Task26AInventoryError):
            # Temporarily corrupt by pointing through a wrong expected hash via monkeypatch
            import solana_alpha_lab.task26a_execution_evidence_inventory as mod

            original = mod._read_bound

            def broken(repo_root, path, expected_sha256):  # type: ignore[no-untyped-def]
                return original(repo_root, path, "0" * 64)

            mod._read_bound = broken  # type: ignore[assignment]
            try:
                build_inventory(ROOT)
            finally:
                mod._read_bound = original  # type: ignore[assignment]


if __name__ == "__main__":
    unittest.main()
