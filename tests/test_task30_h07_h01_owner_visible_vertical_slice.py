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
    from solana_alpha_lab.task30_h07_h01_owner_visible_vertical_slice import (
        evaluate_owner_visible_slice,
        render_owner_readout,
        validate_owner_visible_slice,
    )
except ModuleNotFoundError:
    evaluate_owner_visible_slice = None
    render_owner_readout = None
    validate_owner_visible_slice = None


CONFIG_PATH = ROOT / "configs/task30_h07_h01_owner_visible_vertical_slice_v1.yaml"
FROZEN_CONFIG_PATH = ROOT / "configs/task28_rc001_registry_freeze_v1.yaml"
READOUT_SCRIPT_PATH = ROOT / "scripts/show_task30_h07_h01_owner_readout.py"
READOUT_REPORT_PATH = ROOT / "docs/reports/task30/h07_h01_owner_readout_v1.md"
TASK_PATH = ROOT / "docs/tasks/TASK-30-h07-h01-owner-visible-vertical-slice.md"
CONTRACT_PATH = ROOT / "docs/contracts/task30_h07_h01_owner_visible_vertical_slice_contract_v1.md"
MODULE_PATH = ROOT / "src/solana_alpha_lab/task30_h07_h01_owner_visible_vertical_slice.py"
ACCEPTANCE_PATH = ROOT / "docs/evidence/task30/a7_h07_h01_owner_visible_vertical_slice_acceptance_v1.json"
INPUT_EVIDENCE_HASHES = {
    "task27_route_close": "e901a59a72da29b3eb4a90e24a7d3bde91a4fc00c023310086376747ebe47e6d",
    "task26b_execution_witness": "86cd5d33f3e29f9c3d365afc1aca511b212d6a809fa7be3ea2c6e65ffebd4b73",
    "task30_a6_forward_capture": "e40b3fc46762c015f439a453f68939859114f8f498e1791a0a68f1790829e036",
}


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
    assert receipt["schema"] == "smial.task30.h07-h01-owner-visible-vertical-slice.acceptance"
    assert receipt["schema_version"] == "1.0"
    assert receipt["task_id"] == "TASK-30"
    assert receipt["atom_id"] == "T30-A7_H07_H01_OWNER_VISIBLE_VERTICAL_SLICE_V1"
    assert receipt["decision"]["value"] == "CAPTURE_REQUIRED"
    assert (
        receipt["decision"]["next_boundary"]
        == "EXACT_H07_H01_DATA_CONTRACT_ENTRY_GATE"
    )
    assert receipt["decision"]["state_change"] == "NONE"
    assert receipt["factory_fit_review"] == "FULL_REVIEW"
    assert receipt["factory_fit"]["verdict"] == "PASS_WITH_LIMITATIONS"
    assert receipt["project_sources_disposition"]["kind"] == "NO_CHANGE"

    artifact_paths = {
        "task": TASK_PATH,
        "contract": CONTRACT_PATH,
        "configuration": CONFIG_PATH,
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

    for evidence_id, expected_hash in INPUT_EVIDENCE_HASHES.items():
        binding = receipt["input_evidence"][evidence_id]
        config_binding = load_yaml(CONFIG_PATH)["input_evidence"][evidence_id]
        assert binding == config_binding
        assert binding["sha256"] == expected_hash

    for value in receipt["authority"].values():
        assert value in (0, False)
    for value in receipt["side_effect_counters"].values():
        assert value in (0, False)
    for value in receipt["non_claims"].values():
        assert value is False


class Task30H07H01OwnerVisibleSliceTests(unittest.TestCase):
    def test_current_evidence_requires_capture(self) -> None:
        """Price/transport feasibility cannot become a H07/H01 diagnostic trial."""
        self.assertIsNotNone(
            evaluate_owner_visible_slice,
            "owner-visible evaluator must exist before H07/H01 can be promoted",
        )
        assert evaluate_owner_visible_slice is not None

        result = evaluate_owner_visible_slice(load_yaml(CONFIG_PATH), h07_h01_group())

        self.assertEqual(result["decision"], "CAPTURE_REQUIRED")
        self.assertEqual(
            result["blocker_codes"],
            [
                "CONTINUOUS_PIT_PRICE_HISTORY_UNAVAILABLE",
                "SETTLED_EXECUTION_TRUTH_UNAVAILABLE",
            ],
        )
        self.assertEqual(
            result["next_boundary"], "EXACT_H07_H01_DATA_CONTRACT_ENTRY_GATE"
        )

    def test_config_binds_the_three_prior_receipts(self) -> None:
        """The owner decision cannot silently detach from prior negative evidence."""
        config = load_yaml(CONFIG_PATH)
        input_evidence = config["input_evidence"]
        self.assertEqual(
            config["frozen_definition"]["definition_sha256"],
            h07_h01_group()["definition_sha256"],
        )
        for evidence_id, expected_hash in INPUT_EVIDENCE_HASHES.items():
            with self.subTest(evidence_id=evidence_id):
                item = input_evidence[evidence_id]
                path = ROOT / item["path"]
                self.assertTrue(path.is_file())
                self.assertEqual(item["sha256"], expected_hash)
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), expected_hash
                )

    def test_unsafe_promotions_are_rejected(self) -> None:
        """A missing input, quote or plan must not acquire a stronger meaning."""
        self.assertIsNotNone(
            validate_owner_visible_slice,
            "owner-visible validator must reject unsafe research promotions",
        )
        assert validate_owner_visible_slice is not None
        config = load_yaml(CONFIG_PATH)
        cases = {
            "price_only_to_trial": ("current_evidence", "trial_admissible", True),
            "quote_to_settlement": (
                "current_evidence",
                "settled_execution_truth",
                "AVAILABLE",
            ),
            "missing_to_zero": ("missingness_policy", "missing_to_zero", "ALLOWED"),
            "wrong_frozen_group": (
                "frozen_definition",
                "group_id",
                "RC001-H13-COMPOSITE-VETO",
            ),
            "provider_authority": ("authority", "provider_api_rpc_wss_calls", 1),
        }

        for case_id, (section, field, replacement) in cases.items():
            with self.subTest(case_id=case_id):
                candidate = copy.deepcopy(config)
                candidate[section][field] = replacement
                with self.assertRaises(ValueError):
                    validate_owner_visible_slice(candidate, h07_h01_group())

    def test_read_only_cli_and_checked_in_report_match_the_evaluator(self) -> None:
        """The owner gets one stable decision without a new control plane."""
        self.assertIsNotNone(render_owner_readout)
        assert render_owner_readout is not None

        json_run = subprocess.run(
            [sys.executable, "-B", str(READOUT_SCRIPT_PATH), "--format", "json"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(json_run.returncode, 0, json_run.stderr)
        payload = json.loads(json_run.stdout)
        self.assertEqual(payload["decision"], "CAPTURE_REQUIRED")
        self.assertEqual(
            payload["blocker_codes"],
            [
                "CONTINUOUS_PIT_PRICE_HISTORY_UNAVAILABLE",
                "SETTLED_EXECUTION_TRUTH_UNAVAILABLE",
            ],
        )
        self.assertEqual(
            payload["next_boundary"], "EXACT_H07_H01_DATA_CONTRACT_ENTRY_GATE"
        )

        markdown_run = subprocess.run(
            [sys.executable, "-B", str(READOUT_SCRIPT_PATH), "--format", "markdown"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(markdown_run.returncode, 0, markdown_run.stderr)
        self.assertIn("не готов к запуску", markdown_run.stdout)
        self.assertIn("Провайдер не выбран", markdown_run.stdout)
        self.assertTrue(READOUT_REPORT_PATH.is_file())
        expected = render_owner_readout(
            evaluate_owner_visible_slice(load_yaml(CONFIG_PATH), h07_h01_group())
        )
        self.assertEqual(READOUT_REPORT_PATH.read_text(encoding="utf-8"), expected + "\n")

    def test_acceptance_receipt_is_hash_bound_and_rejects_promotion(self) -> None:
        """The current decision remains traceable and cannot grant new authority."""
        self.assertTrue(ACCEPTANCE_PATH.is_file(), "acceptance receipt must exist")
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        assert_valid_acceptance(receipt)

        mutations = {
            "bound_hash": (("artifact_bindings", "configuration", "sha256"), "0" * 64),
            "provider_call": (("side_effect_counters", "provider_api_rpc_wss_calls"), 1),
            "task30_acceptance": (("non_claims", "task30_acceptance"), True),
            "state_change": (("decision", "state_change"), "DONE"),
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
