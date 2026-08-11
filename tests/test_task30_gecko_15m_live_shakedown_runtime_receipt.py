from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
A11C_CONTRACT = ROOT / "docs" / "contracts" / "task30_two_slot_live_shakedown_runtime_contract_v1.md"
RUNTIME_RECEIPT = ROOT / "docs" / "evidence" / "task30" / "a11e_gecko_15m_live_shakedown_runtime_receipt_v1.json"
FACTORY_FIT = ROOT / "docs" / "evidence" / "task30" / "a11e_gecko_15m_live_shakedown_factory_fit_v1.json"
CATALOG = ROOT / "catalog" / "assets" / "core.yaml"


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


class Task30Gecko15mLiveShakedownRuntimeReceiptTests(unittest.TestCase):
    def test_live_typed_gap_closes_only_the_fast_freshness_route(self) -> None:
        receipt = load_json(RUNTIME_RECEIPT)

        self.assertEqual(receipt["provider_calls_attempted"], 4)
        self.assertEqual(receipt["slot_index"], 1)
        self.assertEqual(receipt["terminal_state"], "SLOT_TECHNICAL_INCONCLUSIVE")
        self.assertEqual(receipt["expected_interval_start"], 1786440600)
        self.assertEqual(receipt["route_disposition"], "CLOSE_CURRENT_15M_FAST_FRESHNESS_ROUTE")
        self.assertEqual(receipt["a11c_contract_sha256"], hashlib.sha256(A11C_CONTRACT.read_bytes()).hexdigest())
        self.assertEqual(receipt["a4_slot_receipt"]["sha256"], "88606d9ffa16830003b584916158c027678b82ca2287a3929e233aa8fae0fba9")
        self.assertEqual(receipt["a4_final_raw_manifest"]["sha256"], "9765ed20c655cf6d7176d2ac5211c2108975e59154025e88c265c31b59e5d131")
        observations = receipt["observations"]
        self.assertEqual([item["offset_seconds"] for item in observations], [0, 15, 30, 60])
        self.assertTrue(all(item["http_status"] == 200 for item in observations))
        self.assertTrue(all(item["classification"] == "TYPED_GAP" for item in observations))
        self.assertTrue(all(item["returned_interval_start"] == 1786438800 for item in observations))
        self.assertFalse(receipt["claims"]["pit_admissible"])
        self.assertFalse(receipt["claims"]["missing_is_zero_or_flat"])
        self.assertFalse(receipt["claims"]["provider_globally_unusable"])
        self.assertTrue(receipt["stop_conditions_applied"]["second_slot_not_started"])
        self.assertTrue(receipt["stop_conditions_applied"]["no_retry"])
        self.assertTrue(receipt["stop_conditions_applied"]["no_fallback"])
        self.assertEqual(receipt["project_sources_disposition"], "NO_CHANGE")

    def test_factory_fit_and_catalog_keep_the_route_close_bounded(self) -> None:
        runtime = load_json(RUNTIME_RECEIPT)
        factory_fit = load_json(FACTORY_FIT)
        catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
        catalog_ids = {record["asset_id"] for record in catalog["records"]}

        self.assertEqual(factory_fit["review_scope"], "FULL_REVIEW")
        self.assertEqual(factory_fit["verdict"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(factory_fit["reuse_first_decision"], "STOP_CURRENT_ROUTE_NO_NEW_PROVIDER_READ")
        self.assertEqual(factory_fit["runtime_receipt_sha256"], hashlib.sha256(RUNTIME_RECEIPT.read_bytes()).hexdigest())
        self.assertEqual(runtime["project_sources_disposition"], "NO_CHANGE")
        self.assertTrue(factory_fit["next_provider_gate_required"])
        self.assertTrue(
            {
                "EVIDENCE-T30-A11E-GECKO-LIVE-SHAKEDOWN-RUNTIME-001",
                "TEST-T30-A11E-GECKO-LIVE-SHAKEDOWN-RUNTIME-001",
                "EVIDENCE-T30-A11E-GECKO-LIVE-SHAKEDOWN-FACTORY-FIT-001",
            }.issubset(catalog_ids)
        )


if __name__ == "__main__":
    unittest.main()
