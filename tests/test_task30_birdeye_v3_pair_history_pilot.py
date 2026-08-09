from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_birdeye_v3_pair_history_pilot import (
    BirdeyeV3PairHistoryPilotError,
    evaluate_birdeye_v3_pair_history_pilot,
)


CONFIG_PATH = ROOT / "configs/task30_birdeye_v3_pair_history_pilot_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task30_birdeye_v3_pair_history_pilot.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task30/birdeye_v3_pair_history_pilot_v1.json"
ACCEPTANCE_PATH = (
    ROOT / "docs/evidence/task30/a5_birdeye_v3_pair_history_pilot_preparation_acceptance_v1.json"
)
FACTORY_FIT_PATH = (
    ROOT / "docs/evidence/task30/a5_birdeye_v3_pair_history_pilot_preparation_factory_fit_v1.json"
)
CATALOG_CORE_PATH = ROOT / "catalog/assets/core.yaml"


def replace_pointer(record: dict[str, object], pointer: str, replacement: object) -> None:
    target: object = record
    parts = pointer.split(".")
    for part in parts[:-1]:
        if isinstance(target, list):
            target = target[int(part)]
        else:
            target = target[part]  # type: ignore[index]
    if isinstance(target, list):
        target[int(parts[-1])] = replacement
    else:
        target[parts[-1]] = replacement  # type: ignore[index]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task30BirdeyeV3PairHistoryPilotTests(unittest.TestCase):
    def test_offline_packet_is_schema_valid_and_preserves_owner_gate(self) -> None:
        """Catches a packet that looks ready but silently authorizes a provider call."""
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertFalse(list(Draft202012Validator(schema).iter_errors(config)))
        self.assertEqual(evaluate_birdeye_v3_pair_history_pilot(config), fixture["expected_result"])

    def test_future_reads_are_exactly_ordered_and_bounded(self) -> None:
        """Catches a changed route, third request, retry, or fallback before owner review."""
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        result = evaluate_birdeye_v3_pair_history_pilot(config)

        self.assertEqual(result["future_request_cap"], 2)
        self.assertEqual(
            result["future_read_ids"],
            ["PAIR_OVERVIEW_IDENTITY_READ", "PAIR_OHLCV_RANGE_READ"],
        )
        self.assertEqual(result["future_external_authority"], "NOT_GRANTED")

    def test_authority_transport_and_semantic_promotions_are_rejected(self) -> None:
        """Catches widened external access and false claims about the planned response."""
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        cases = (
            ("authority.provider_api_rpc_wss_calls", 1, "EXTERNAL_AUTHORITY_FORBIDDEN"),
            ("future_reads.1.max_attempts", 2, "RETRY_OR_FALLBACK_FORBIDDEN"),
            ("future_reads.1.endpoint_path", "/defi/ohlcv", "REQUEST_SHAPE_DRIFT"),
            ("future_reads.1.query.type", "1m", "REQUEST_SHAPE_DRIFT"),
            ("future_reads.1.stop_chain_on_non_200", False, "SEQUENCE_GUARD_DRIFT"),
            ("future_reads.1.raw_retention", "repo://raw.json", "RAW_DATA_FORBIDDEN"),
            ("semantic_state.price_unit", "USD_PROVEN", "SEMANTIC_PROMOTION_FORBIDDEN"),
            (
                "semantic_state.empty_interval_meaning",
                "NO_TRADE_PROVEN",
                "SEMANTIC_PROMOTION_FORBIDDEN",
            ),
            ("non_claims.pit_admissible", True, "PROMOTION_CLAIM_FORBIDDEN"),
            ("owner_authority.status", "GRANTED", "OWNER_AUTHORITY_DRIFT"),
            (
                "local_credential_presence.status",
                "ATTESTED_PRESENT",
                "CREDENTIAL_PRESENCE_DRIFT",
            ),
        )
        for pointer, replacement, expected_error in cases:
            with self.subTest(pointer=pointer):
                candidate = copy.deepcopy(config)
                replace_pointer(candidate, pointer, replacement)
                with self.assertRaisesRegex(
                    BirdeyeV3PairHistoryPilotError, expected_error
                ):
                    evaluate_birdeye_v3_pair_history_pilot(candidate)

        candidate = copy.deepcopy(config)
        candidate["credential_material"] = {"api_key": "not-a-real-key"}
        with self.assertRaisesRegex(
            BirdeyeV3PairHistoryPilotError, "CREDENTIAL_DISCLOSURE_FORBIDDEN"
        ):
            evaluate_birdeye_v3_pair_history_pilot(candidate)

    def test_receipts_bind_offline_packet_and_catalog_discovery(self) -> None:
        """Catches a delivered packet lacking evidence, full review, or future discovery."""
        self.assertTrue(ACCEPTANCE_PATH.exists())
        self.assertTrue(FACTORY_FIT_PATH.exists())
        if not ACCEPTANCE_PATH.exists() or not FACTORY_FIT_PATH.exists():
            return

        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        factory_fit = json.loads(FACTORY_FIT_PATH.read_text(encoding="utf-8"))
        catalog = yaml.safe_load(CATALOG_CORE_PATH.read_text(encoding="utf-8"))

        for binding in acceptance["artifact_bindings"].values():
            path = ROOT / binding["path"]
            self.assertEqual(binding["sha256"], sha256(path))
        self.assertTrue(
            all(value == 0 for value in acceptance["side_effect_counters"].values())
        )
        self.assertEqual(
            acceptance["decision"]["value"],
            "OFFLINE_PACKET_READY_FOR_OWNER_AUTHORITY_GATE",
        )
        self.assertEqual(acceptance["project_sources_disposition"]["kind"], "NO_CHANGE")
        self.assertEqual(factory_fit["review_scope"], "FULL_REVIEW")
        self.assertEqual(factory_fit["verdict"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(factory_fit["reuse_first"]["outcome"], "ADOPT_EXISTING")

        assets = {asset["asset_id"] for asset in catalog["records"]}
        self.assertTrue(
            {
                "CONTRACT-T30-BIRDEYE-V3-HISTORY-PILOT-001",
                "CONFIG-T30-BIRDEYE-V3-HISTORY-PILOT-001",
                "SCHEMA-T30-BIRDEYE-V3-HISTORY-PILOT-001",
                "FIXTURE-T30-BIRDEYE-V3-HISTORY-PILOT-001",
                "MODULE-T30-BIRDEYE-V3-HISTORY-PILOT-001",
                "TEST-T30-BIRDEYE-V3-HISTORY-PILOT-001",
                "EVIDENCE-T30-A5-BIRDEYE-V3-HISTORY-PILOT-001",
                "EVIDENCE-T30-A5-BIRDEYE-V3-HISTORY-PILOT-FACTORY-FIT-001",
            }.issubset(assets)
        )
