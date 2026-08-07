from __future__ import annotations

import copy
import hashlib
import json
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs/contracts/task27_price_volume_research_screen_contract_v1.md"
CONFIG_PATH = ROOT / "configs/task27_price_volume_research_screen_contract_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task27_price_volume_research_screen.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task27/price_volume_research_screen_v1.json"
RECEIPT_PATH = (
    ROOT / "docs/evidence/task27/a0a2_price_volume_research_screen_contract_acceptance_v1.json"
)
REQUIRED_PATHS = [
    CONTRACT_PATH,
    CONFIG_PATH,
    SCHEMA_PATH,
    FIXTURE_PATH,
    RECEIPT_PATH,
]
EXPECTED_WRITE_SET = [
    "docs/contracts/task27_price_volume_research_screen_contract_v1.md",
    "configs/task27_price_volume_research_screen_contract_v1.yaml",
    "catalog/schemas/task27_price_volume_research_screen.schema.json",
    "tests/fixtures/task27/price_volume_research_screen_v1.json",
    "tests/test_task27_price_volume_research_screen_contract.py",
    "docs/evidence/task27/a0a2_price_volume_research_screen_contract_acceptance_v1.json",
]
EXPECTED_ADVERSARIAL_ERRORS = {
    "MISSING_IS_NOT_ZERO",
    "CARRIED_FORWARD_PRICE_FORBIDDEN",
    "NONCONTIGUOUS_FORWARD_WINDOW",
    "PIT_AVAILABILITY_UNKNOWN",
    "POOL_TOKEN_IDENTITY_MISMATCH",
    "PRICE_LABEL_IS_NOT_EXECUTION",
    "INCOMPLETE_FORWARD_WINDOW_UNKNOWN",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def apply_json_pointer(document: dict[str, Any], pointer: str, value: Any) -> None:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    target: Any = document
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    final = parts[-1]
    if isinstance(target, list):
        target[int(final)] = copy.deepcopy(value)
    else:
        target[final] = copy.deepcopy(value)


def semantic_errors(panel: dict[str, Any]) -> set[str]:
    errors: set[str] = set()
    identity = panel["identity"]
    bars = panel["bars"]
    label = panel["label"]

    if identity["observation_scope"] != "POOL":
        errors.add("POOL_TOKEN_IDENTITY_MISMATCH")
    if label["claim_scope"] != "RESEARCH_SCREEN_ONLY":
        errors.add("PRICE_LABEL_IS_NOT_EXECUTION")

    starts = [parse_time(bar["interval_start_at"]) for bar in bars]
    if any(
        right - left != timedelta(seconds=panel["interval_seconds"])
        for left, right in zip(starts, starts[1:])
    ):
        errors.add("NONCONTIGUOUS_FORWARD_WINDOW")

    complete_observed_window = len(bars) == 5
    for bar in bars:
        state = bar["data_state"]
        prices = [bar[field] for field in ("open", "high", "low", "close")]
        if state == "MISSING_UNKNOWN":
            complete_observed_window = False
            if bar["volume"] == "0":
                errors.add("MISSING_IS_NOT_ZERO")
            if bar["carried_forward"]:
                errors.add("CARRIED_FORWARD_PRICE_FORBIDDEN")
            if any(value is not None for value in prices):
                errors.add("UNOBSERVED_OHLC_FORBIDDEN")
        if state != "OBSERVED":
            complete_observed_window = False
        if bar["available_at"] is None:
            errors.add("PIT_AVAILABILITY_UNKNOWN")
            complete_observed_window = False
        elif parse_time(bar["event_time"]) > parse_time(bar["observed_at"]) or (
            parse_time(bar["observed_at"]) > parse_time(bar["available_at"])
            or parse_time(bar["available_at"]) > parse_time(bar["ingested_at"])
        ):
            errors.add("PIT_ORDER_INVALID")
            complete_observed_window = False
        if state == "OBSERVED":
            decimal_prices = [Decimal(str(value)) for value in prices]
            if (
                any(value <= 0 for value in decimal_prices)
                or decimal_prices[2] > min(decimal_prices[0], decimal_prices[3])
                or decimal_prices[1] < max(decimal_prices[0], decimal_prices[3])
            ):
                errors.add("OBSERVED_OHLC_INVALID")

    if not complete_observed_window and label["state"] == "KNOWN":
        errors.add("INCOMPLETE_FORWARD_WINDOW_UNKNOWN")
    if complete_observed_window and label["state"] == "KNOWN":
        entry_close = Decimal(bars[0]["close"])
        terminal_close = Decimal(bars[-1]["close"])
        expected = ((terminal_close - entry_close) / entry_close).quantize(
            Decimal("0.000001")
        )
        if Decimal(label["value_decimal"]) != expected:
            errors.add("FORWARD_RETURN_VALUE_INVALID")
    if label["state"] == "UNKNOWN" and label["value_decimal"] is not None:
        errors.add("UNKNOWN_LABEL_HAS_VALUE")
    return errors


class Task27PriceVolumeResearchScreenContractTests(unittest.TestCase):
    def test_all_required_artifacts_exist(self) -> None:
        for path in REQUIRED_PATHS:
            with self.subTest(path=path):
                self.assertTrue(path.exists(), path)

    def test_fixture_passes_schema_and_is_synthetic_only(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        self.assertEqual([error.message for error in validator.iter_errors(fixture)], [])
        self.assertEqual(fixture["fixture_kind"], "SYNTHETIC_GOLDEN_ONLY")

    def test_complete_observed_window_yields_hand_derived_label(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        panel = fixture["valid_panels"][0]
        self.assertEqual(panel["label"]["state"], "KNOWN")
        self.assertEqual(panel["label"]["value_decimal"], "0.050000")
        self.assertEqual(semantic_errors(panel), set())

    def test_adversarial_matrix_rejects_each_forbidden_inference(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        expected_errors = {case["expected_error"] for case in fixture["adversarial_cases"]}
        self.assertEqual(expected_errors, EXPECTED_ADVERSARIAL_ERRORS)
        base = fixture["valid_panels"][0]
        for case in fixture["adversarial_cases"]:
            with self.subTest(case_id=case["case_id"]):
                changed = copy.deepcopy(base)
                for mutation in case["mutations"]:
                    apply_json_pointer(changed, mutation["json_pointer"], mutation["replacement"])
                self.assertIn(case["expected_error"], semantic_errors(changed))

    def test_config_freezes_scope_authority_and_label(self) -> None:
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(config["managed_write_set"], EXPECTED_WRITE_SET)
        self.assertEqual(config["data_contract"]["interval_seconds"], 900)
        self.assertEqual(config["data_contract"]["primary_label"], "FORWARD_CLOSE_RETURN_1H")
        self.assertEqual(config["data_contract"]["successor_intervals_required"], 4)
        self.assertEqual(config["data_contract"]["missing_result"], "UNKNOWN")
        for key in (
            "provider_api_rpc_wss_calls",
            "r2_value_reads",
            "r3_value_or_path_reads",
            "wallet_signer_transaction_actions",
            "cash_spend_usd_cents",
        ):
            self.assertEqual(config["authority"][key], 0, key)
        self.assertFalse(config["authority"]["catalog_or_registry_mutation"])
        self.assertFalse(config["authority"]["project_source_changes"])

    def test_receipt_binds_current_artifacts_and_zero_external_actions(self) -> None:
        self.assertTrue(RECEIPT_PATH.exists(), RECEIPT_PATH)
        receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        bindings = receipt["artifact_bindings"]
        for key, path in {
            "contract": CONTRACT_PATH,
            "config": CONFIG_PATH,
            "schema": SCHEMA_PATH,
            "fixture": FIXTURE_PATH,
        }.items():
            self.assertEqual(bindings[key]["path"], path.relative_to(ROOT).as_posix())
            self.assertEqual(bindings[key]["sha256"], sha256(path))
        self.assertEqual(receipt["managed_write_set"], EXPECTED_WRITE_SET)
        self.assertEqual(receipt["validation"]["targeted_tests_run"], 7)
        self.assertEqual(receipt["validation"]["adversarial_cases_rejected"], 7)
        for key in (
            "provider_api_rpc_wss_calls",
            "r2_value_reads",
            "r3_value_or_path_reads",
            "wallet_signer_transaction_actions",
            "cash_spend_usd_cents",
        ):
            self.assertEqual(receipt["measured_boundary"][key], 0, key)
        self.assertEqual(receipt["state_change"], "NONE")

    def test_artifacts_are_normalized(self) -> None:
        for path in REQUIRED_PATHS:
            with self.subTest(path=path):
                payload = path.read_bytes()
                self.assertTrue(payload.endswith(b"\n"))
                self.assertNotIn(b"\r\n", payload)
                self.assertFalse(payload.startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
