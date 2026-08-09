from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "contracts" / "task30_birdeye_v3_pair_history_pilot_contract_v1.md"
RUNTIME_RECEIPT = (
    ROOT / "docs" / "evidence" / "task30" / "a5r1_birdeye_v3_external_read_runtime_receipt_v1.json"
)
FACTORY_FIT = (
    ROOT / "docs" / "evidence" / "task30" / "a5r1_birdeye_v3_external_read_factory_fit_v1.json"
)
CATALOG = ROOT / "catalog" / "assets" / "core.yaml"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class Task30BirdeyeExternalReadRuntimeReceiptTests(unittest.TestCase):
    def test_two_read_outcome_is_bound_and_does_not_promote_history(self) -> None:
        receipt = load_json(RUNTIME_RECEIPT)

        self.assertEqual(receipt["provider_calls_attempted"], 2)
        self.assertEqual(receipt["reads"][0]["http_status"], 200)
        self.assertEqual(receipt["reads"][1]["http_status"], 429)
        self.assertEqual(
            receipt["decision"],
            "PAIR_IDENTITY_ACCEPTED_OHLCV_RATE_OR_QUOTA_LIMITED",
        )
        self.assertEqual(
            receipt["a4_raw_manifest"]["sha256"],
            "4a8877e957dd43d5fa10e738c9c5af9c2a4cfd3ae619d0f357b002af04c2a7d3",
        )
        self.assertEqual(
            receipt["a5_contract_sha256"],
            hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
        )
        self.assertFalse(receipt["claims"]["historical_panel"])
        self.assertFalse(receipt["claims"]["rest_15m_supported"])
        self.assertFalse(receipt["claims"]["pair_or_provider_unsupported"])
        self.assertTrue(receipt["stop_conditions_applied"]["no_retry_after_429"])
        self.assertTrue(receipt["stop_conditions_applied"]["no_fallback"])

    def test_factory_fit_and_catalog_keep_the_external_boundary_discoverable(self) -> None:
        runtime = load_json(RUNTIME_RECEIPT)
        factory_fit = load_json(FACTORY_FIT)
        catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
        catalog_ids = {record["asset_id"] for record in catalog["records"]}

        self.assertEqual(factory_fit["review_scope"], "FULL_REVIEW")
        self.assertEqual(factory_fit["verdict"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(
            factory_fit["decision"],
            "RATE_LIMITED_READ_CLOSE_NO_RETRY_OR_FALLBACK",
        )
        self.assertEqual(
            factory_fit["runtime_receipt_sha256"],
            hashlib.sha256(RUNTIME_RECEIPT.read_bytes()).hexdigest(),
        )
        self.assertEqual(runtime["project_sources_disposition"], "NO_CHANGE")
        self.assertTrue(
            {
                "EVIDENCE-T30-A5R1-BIRDEYE-EXTERNAL-READ-RUNTIME-001",
                "TEST-T30-A5R1-BIRDEYE-EXTERNAL-READ-RUNTIME-001",
                "EVIDENCE-T30-A5R1-BIRDEYE-EXTERNAL-READ-FACTORY-FIT-001",
            }.issubset(catalog_ids)
        )


if __name__ == "__main__":
    unittest.main()
