from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from solana_alpha_lab.task30_h07_h01_exact_data_contract_entry_gate import (
        evaluate_data_contract,
    )
except ModuleNotFoundError:
    evaluate_data_contract = None

try:
    from solana_alpha_lab.task30_h07_h01_exact_data_contract_entry_gate import (
        validate_data_contract,
    )
except (ImportError, ModuleNotFoundError):
    validate_data_contract = None

CONFIG_PATH = ROOT / "configs/task30_h07_h01_exact_data_contract_entry_gate_v1.yaml"
FROZEN_CONFIG_PATH = ROOT / "configs/task28_rc001_registry_freeze_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task30_h07_h01_exact_data_contract_entry_gate.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task30/h07_h01_exact_data_contract_entry_gate_v1.json"


def load_yaml(path: Path) -> dict:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def h07_h01_group() -> dict:
    document = load_yaml(FROZEN_CONFIG_PATH)
    groups = document["hypothesis_groups"]
    assert isinstance(groups, list)
    for group in groups:
        if group["group_id"] == "RC001-H07-H01-LIQUIDITY-RETENTION":
            assert isinstance(group, dict)
            return group
    raise AssertionError("frozen H07/H01 group missing")


class Task30H07H01ExactDataContractTests(unittest.TestCase):
    def test_partial_pit_capture_retains_execution_blocker(self) -> None:
        self.assertIsNotNone(
            evaluate_data_contract,
            "A8 must have a pure evaluator before it can claim a partial PIT capture path",
        )
        assert evaluate_data_contract is not None

        result = evaluate_data_contract(load_yaml(CONFIG_PATH), h07_h01_group())

        self.assertEqual(
            result["decision"], "PREPARE_PARTIAL_PIT_CAPTURE_CONTRACT"
        )
        self.assertIs(result["trial_admissible"], False)
        self.assertEqual(
            result["next_boundary"],
            "OWNER_GATE_FOR_NAMED_PARTIAL_PIT_OR_ROUTE_CAPTURE",
        )
        self.assertEqual(
            result["requirements"]["settled_execution_truth"]["state"],
            "UNSUPPORTED",
        )

    def test_schema_and_synthetic_golden_result_bind_the_partial_decision(self) -> None:
        self.assertTrue(SCHEMA_PATH.is_file())
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            schema["$id"],
            "https://solana-alpha-lab.local/schemas/task30_h07_h01_exact_data_contract_entry_gate.schema.json",
        )
        self.assertTrue(FIXTURE_PATH.is_file())
        expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        assert evaluate_data_contract is not None
        self.assertEqual(
            evaluate_data_contract(load_yaml(CONFIG_PATH), h07_h01_group()), expected
        )

    def test_false_promotions_and_missing_capture_safety_are_rejected(self) -> None:
        self.assertIsNotNone(
            validate_data_contract,
            "A8 must reject unsafe data-contract promotions before an owner gate",
        )
        assert validate_data_contract is not None
        config = load_yaml(CONFIG_PATH)
        cases = {
            "settlement_promotion": (
                ("requirements", "settled_execution_truth", "state"),
                "SUPPORTED",
                "SETTLEMENT_PROMOTION",
            ),
            "price_to_settlement": (
                ("lanes", "PIT_MARKET", "cannot_establish"),
                ["ROUTE_PERSISTENCE", "FILL"],
                "FALSE_PROMOTION",
            ),
            "missing_to_zero": (
                ("missingness_policy", "missing_to_zero"),
                "ALLOWED",
                "MISSINGNESS_COERCION",
            ),
            "unrecoverable_capture": (
                ("capture_safety", "backup_or_waiver", "required"),
                False,
                "UNRECOVERABLE_CAPTURE_WITHOUT_COVERAGE",
            ),
            "provider_authority": (
                ("authority", "provider_api_rpc_wss_calls"),
                1,
                "AUTHORITY_PROMOTION",
            ),
        }

        for case_id, (path, replacement, error_code) in cases.items():
            with self.subTest(case_id=case_id):
                candidate = copy.deepcopy(config)
                target = candidate
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = replacement
                with self.assertRaisesRegex(ValueError, error_code):
                    validate_data_contract(candidate, h07_h01_group())


if __name__ == "__main__":
    unittest.main()
