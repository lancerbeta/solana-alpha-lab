from __future__ import annotations

import copy
import hashlib
import json
import subprocess
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

try:
    from solana_alpha_lab.task30_h07_h01_exact_data_contract_entry_gate import (
        render_data_contract_readout,
    )
except (ImportError, ModuleNotFoundError):
    render_data_contract_readout = None

CONFIG_PATH = ROOT / "configs/task30_h07_h01_exact_data_contract_entry_gate_v1.yaml"
FROZEN_CONFIG_PATH = ROOT / "configs/task28_rc001_registry_freeze_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task30_h07_h01_exact_data_contract_entry_gate.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task30/h07_h01_exact_data_contract_entry_gate_v1.json"
READOUT_SCRIPT_PATH = ROOT / "scripts/show_task30_h07_h01_data_contract_readout.py"
READOUT_REPORT_PATH = ROOT / "docs/reports/task30/h07_h01_exact_data_contract_readout_v1.md"
TASK_PATH = ROOT / "docs/tasks/TASK-30-h07-h01-exact-data-contract-entry-gate.md"
CONTRACT_PATH = ROOT / "docs/contracts/task30_h07_h01_exact_data_contract_entry_gate_contract_v1.md"
MODULE_PATH = ROOT / "src/solana_alpha_lab/task30_h07_h01_exact_data_contract_entry_gate.py"
ACCEPTANCE_PATH = ROOT / "docs/evidence/task30/a8_h07_h01_exact_data_contract_entry_gate_acceptance_v1.json"


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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_valid_acceptance(receipt: dict) -> None:
    assert receipt["schema"] == "smial.task30.h07-h01-exact-data-contract-entry-gate.acceptance"
    assert receipt["schema_version"] == "1.0"
    assert receipt["task_id"] == "TASK-30"
    assert receipt["atom_id"] == "T30-A8_H07_H01_EXACT_DATA_CONTRACT_ENTRY_GATE_V1"
    assert receipt["decision"]["value"] == "PREPARE_PARTIAL_PIT_CAPTURE_CONTRACT"
    assert receipt["decision"]["trial_admissible"] is False
    assert receipt["decision"]["state_change"] == "NONE"
    assert receipt["factory_fit_review"] == "FULL_REVIEW"
    assert receipt["project_sources_disposition"]["kind"] == "NO_CHANGE"
    assert receipt["audit_assimilation"]["input_sha256"] == (
        "9ef775756f35199b073acfea0e52db228da9b4d08c30b1194e3d7b1b88886da1"
    )

    artifact_paths = {
        "task": TASK_PATH,
        "contract": CONTRACT_PATH,
        "configuration": CONFIG_PATH,
        "schema": SCHEMA_PATH,
        "fixture": FIXTURE_PATH,
        "module": MODULE_PATH,
        "script": READOUT_SCRIPT_PATH,
        "report": READOUT_REPORT_PATH,
        "test": Path(__file__),
    }
    assert set(receipt["artifact_bindings"]) == set(artifact_paths)
    for artifact_id, path in artifact_paths.items():
        binding = receipt["artifact_bindings"][artifact_id]
        assert binding["path"] == path.relative_to(ROOT).as_posix()
        assert binding["sha256"] == sha256(path)

    for evidence_id, binding in load_yaml(CONFIG_PATH)["input_evidence"].items():
        assert receipt["input_evidence"][evidence_id] == binding
        path = ROOT / binding["path"]
        assert path.is_file()
        assert sha256(path) == binding["sha256"]
    for value in receipt["authority"].values():
        assert value in (0, False)
    for value in receipt["side_effect_counters"].values():
        assert value in (0, False)
    for value in receipt["non_claims"].values():
        assert value is False


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

    def test_owner_readout_explains_the_partial_boundary_in_russian(self) -> None:
        self.assertIsNotNone(
            render_data_contract_readout,
            "A8 must render a short owner readout before a later capture gate",
        )
        assert evaluate_data_contract is not None
        assert render_data_contract_readout is not None

        readout = render_data_contract_readout(
            evaluate_data_contract(load_yaml(CONFIG_PATH), h07_h01_group())
        )

        self.assertIn("частичный PIT", readout)
        self.assertIn("не является trial", readout)
        self.assertIn("не доказывает settlement", readout)
        self.assertIn("OWNER_GATE_FOR_NAMED_PARTIAL_PIT_OR_ROUTE_CAPTURE", readout)

    def test_read_only_cli_and_checked_in_report_match_the_evaluator(self) -> None:
        self.assertTrue(
            READOUT_SCRIPT_PATH.is_file(),
            "A8 needs a read-only owner CLI before the report can be trusted",
        )
        assert evaluate_data_contract is not None
        assert render_data_contract_readout is not None

        json_run = subprocess.run(
            [sys.executable, "-B", str(READOUT_SCRIPT_PATH), "--format", "json"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(json_run.returncode, 0, json_run.stderr)
        self.assertEqual(
            json.loads(json_run.stdout)["decision"],
            "PREPARE_PARTIAL_PIT_CAPTURE_CONTRACT",
        )
        self.assertTrue(READOUT_REPORT_PATH.is_file())
        expected = render_data_contract_readout(
            evaluate_data_contract(load_yaml(CONFIG_PATH), h07_h01_group())
        )
        self.assertEqual(
            READOUT_REPORT_PATH.read_text(encoding="utf-8"), expected + "\n"
        )

    def test_acceptance_receipt_is_hash_bound_and_retains_audit_triggers(self) -> None:
        self.assertTrue(
            ACCEPTANCE_PATH.is_file(),
            "A8 needs a hash-bound acceptance receipt before it can be delivered",
        )
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        assert_valid_acceptance(receipt)

        mutations = {
            "artifact_hash": (("artifact_bindings", "configuration", "sha256"), "0" * 64),
            "provider_call": (("side_effect_counters", "provider_api_rpc_wss_calls"), 1),
            "trial_admission": (("decision", "trial_admissible"), True),
            "audit_hash": (("audit_assimilation", "input_sha256"), "0" * 64),
        }
        for case_id, (path, replacement) in mutations.items():
            with self.subTest(case_id=case_id):
                candidate = copy.deepcopy(receipt)
                target = candidate
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = replacement
                with self.assertRaises(AssertionError):
                    assert_valid_acceptance(candidate)


if __name__ == "__main__":
    unittest.main()
