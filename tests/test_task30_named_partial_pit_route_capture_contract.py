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
    from solana_alpha_lab.task30_named_partial_pit_route_capture_contract import (
        evaluate_capture_contract,
        render_capture_contract_readout,
        validate_capture_contract,
    )
except ModuleNotFoundError:
    evaluate_capture_contract = None
    render_capture_contract_readout = None
    validate_capture_contract = None

CONFIG_PATH = ROOT / "configs/task30_named_partial_pit_route_capture_contract_v1.yaml"
FROZEN_CONFIG_PATH = ROOT / "configs/task28_rc001_registry_freeze_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task30_named_partial_pit_route_capture_contract.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task30/named_partial_pit_route_capture_contract_v1.json"
READOUT_SCRIPT_PATH = ROOT / "scripts/show_task30_named_partial_pit_route_capture_contract.py"
READOUT_REPORT_PATH = ROOT / "docs/reports/task30/named_partial_pit_route_capture_contract_readout_v1.md"
TASK_PATH = ROOT / "docs/tasks/TASK-30-named-partial-pit-route-capture-contract.md"
CONTRACT_PATH = ROOT / "docs/contracts/task30_named_partial_pit_route_capture_contract_v1.md"
MODULE_PATH = ROOT / "src/solana_alpha_lab/task30_named_partial_pit_route_capture_contract.py"
ACCEPTANCE_PATH = ROOT / "docs/evidence/task30/a9_named_partial_pit_route_capture_contract_acceptance_v1.json"
CATALOG_CORE_PATH = ROOT / "catalog/assets/core.yaml"

ARTIFACT_PATHS = {
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
CATALOG_ASSET_IDS = {
    "CONTRACT-T30-NAMED-PARTIAL-CAPTURE-001": CONTRACT_PATH,
    "CONFIG-T30-NAMED-PARTIAL-CAPTURE-001": CONFIG_PATH,
    "SCHEMA-T30-NAMED-PARTIAL-CAPTURE-001": SCHEMA_PATH,
    "FIXTURE-T30-NAMED-PARTIAL-CAPTURE-001": FIXTURE_PATH,
    "MODULE-T30-NAMED-PARTIAL-CAPTURE-001": MODULE_PATH,
    "SCRIPT-T30-NAMED-PARTIAL-CAPTURE-001": READOUT_SCRIPT_PATH,
    "REPORT-T30-NAMED-PARTIAL-CAPTURE-001": READOUT_REPORT_PATH,
    "TEST-T30-NAMED-PARTIAL-CAPTURE-001": Path(__file__),
    "EVIDENCE-T30-A9-NAMED-PARTIAL-CAPTURE-001": ACCEPTANCE_PATH,
}


def load_yaml(path: Path) -> dict:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def frozen_group() -> dict:
    document = load_yaml(FROZEN_CONFIG_PATH)
    for group in document["hypothesis_groups"]:
        if group["group_id"] == "RC001-H07-H01-LIQUIDITY-RETENTION":
            assert isinstance(group, dict)
            return group
    raise AssertionError("frozen H07/H01 group missing")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_valid_acceptance(receipt: dict) -> None:
    assert receipt["schema"] == "smial.task30.named-partial-pit-route-capture.acceptance"
    assert receipt["schema_version"] == "1.0"
    assert receipt["task_id"] == "TASK-30"
    assert receipt["atom_id"] == "T30-A9_NAMED_PARTIAL_PIT_AND_ROUTE_CAPTURE_CONTRACT_V1"
    assert receipt["decision"]["value"] == "OWNER_PACKET_READY_EXTERNAL_AUTHORITY_REQUIRED"
    assert receipt["decision"]["trial_admissible"] is False
    assert receipt["decision"]["state_change"] == "NONE"
    assert receipt["factory_fit_review"] == "FULL_REVIEW"
    assert receipt["project_sources_disposition"]["kind"] == "NO_CHANGE"
    assert receipt["frozen_definition"] == {
        "group_id": "RC001-H07-H01-LIQUIDITY-RETENTION",
        "definition_sha256": "14a7387148d05773dedcb5ad6a8110a0dcab7e49da4dec77328903a5b7577df7",
    }
    assert receipt["upstream_a8"] == load_yaml(CONFIG_PATH)["upstream_a8"]
    assert set(receipt["artifact_bindings"]) == set(ARTIFACT_PATHS)
    for artifact_id, path in ARTIFACT_PATHS.items():
        binding = receipt["artifact_bindings"][artifact_id]
        assert binding["path"] == path.relative_to(ROOT).as_posix()
        assert binding["sha256"] == sha256(path)
    for value in receipt["authority"].values():
        assert value in (0, False)
    for value in receipt["side_effect_counters"].values():
        assert value in (0, False)
    assert receipt["non_claims"]["technical_pilot_is_h07_h01_evidence"] is False
    assert receipt["non_claims"]["external_capture_authorized"] is False


class Task30NamedPartialCaptureContractTests(unittest.TestCase):
    def test_evaluator_returns_only_a_future_owner_packet_decision(self) -> None:
        self.assertIsNotNone(
            evaluate_capture_contract,
            "A9 must provide a pure evaluator before it claims any owner-packet readiness",
        )
        assert evaluate_capture_contract is not None

        result = evaluate_capture_contract(load_yaml(CONFIG_PATH), frozen_group())

        self.assertEqual(result, json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))
        self.assertTrue(result["technical_pilot_only"])
        self.assertFalse(result["external_capture_authorized"])
        self.assertFalse(result["trial_admissible"])

    def test_policy_schema_and_future_authority_boundary_are_closed(self) -> None:
        self.assertTrue(SCHEMA_PATH.is_file())
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            schema["$id"],
            "https://solana-alpha-lab.local/schemas/task30_named_partial_pit_route_capture_contract.schema.json",
        )
        config = load_yaml(CONFIG_PATH)
        self.assertEqual(config["reference_subject"]["target_role"], "TECHNICAL_DATA_ROUTE_PILOT")
        self.assertEqual(config["reference_subject"]["representativeness"], "NOT_ESTABLISHED")
        self.assertEqual(config["pilot_window"]["expected_closed_intervals"], 96)
        self.assertEqual(config["pilot_window"]["slot_outcome_policy"], "OBSERVATION_OR_TYPED_GAP_REQUIRED")
        self.assertEqual(config["external_owner_packet"]["provider_selection"], "OWNER_INPUT_REQUIRED")
        self.assertFalse(config["external_owner_packet"]["provider_api_rpc_wss_calls_authorized"])

    def test_promotion_and_authority_bypasses_fail_closed(self) -> None:
        self.assertIsNotNone(
            validate_capture_contract,
            "A9 must reject a promotion before an owner can mistake preparation for authority",
        )
        assert validate_capture_contract is not None
        config = load_yaml(CONFIG_PATH)
        cases = {
            "representativeness": (("reference_subject", "representativeness"), "ESTABLISHED", "PILOT_PROMOTION"),
            "notional": (("route_feasibility", "notional_buckets"), [100, 1000], "UNNAMED_NOTIONALS"),
            "provider": (("external_owner_packet", "provider_selection"), "BIRDEYE", "PROVIDER_PRESELECTION"),
            "recovery": (("external_owner_packet", "backup_or_tracked_waiver"), False, "RECOVERY_PROTECTION_REQUIRED"),
            "provider_call": (("authority", "provider_api_rpc_wss_calls"), 1, "AUTHORITY_PROMOTION"),
            "panel_shape": (("pilot_window", "expected_closed_intervals"), 95, "PANEL_SHAPE_MISMATCH"),
            "missingness": (("pilot_window", "slot_outcome_policy"), "OBSERVATION_REQUIRED", "MISSINGNESS_COERCION"),
            "fallback": (("external_owner_packet", "fallback_policy"), "ALLOWED", "FALLBACK_FORBIDDEN"),
            "pilot_claim": (("non_claims", "technical_pilot_is_h07_h01_evidence"), True, "PILOT_PROMOTION"),
            "raw_write": (("authority", "raw_data_writes"), 1, "AUTHORITY_PROMOTION"),
        }
        for case_id, (path, replacement, error_code) in cases.items():
            with self.subTest(case_id=case_id):
                candidate = copy.deepcopy(config)
                target = candidate
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = replacement
                with self.assertRaisesRegex(ValueError, error_code):
                    validate_capture_contract(candidate, frozen_group())

    def test_russian_readout_and_cli_do_not_turn_readiness_into_authority(self) -> None:
        self.assertIsNotNone(render_capture_contract_readout)
        assert evaluate_capture_contract is not None
        assert render_capture_contract_readout is not None
        readout = render_capture_contract_readout(
            evaluate_capture_contract(load_yaml(CONFIG_PATH), frozen_group())
        )
        self.assertIn("готово к рассмотрению внешнего owner gate", readout)
        self.assertIn("не разрешает внешний запрос", readout)
        self.assertIn("96", readout)
        self.assertIn("типизированный gap", readout)

        for output_format in ("json", "markdown"):
            completed = subprocess.run(
                [sys.executable, "-B", str(READOUT_SCRIPT_PATH), "--format", output_format],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(READOUT_REPORT_PATH.read_text(encoding="utf-8"), readout + "\n")

    def test_acceptance_receipt_is_hash_bound_and_keeps_external_authority_closed(self) -> None:
        self.assertTrue(
            ACCEPTANCE_PATH.is_file(),
            "A9 needs a hash-bound receipt before the offline contract can be delivered",
        )
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        assert_valid_acceptance(receipt)
        mutations = {
            "configuration_hash": (("artifact_bindings", "configuration", "sha256"), "0" * 64),
            "upstream_a8_hash": (("upstream_a8", "sha256"), "0" * 64),
            "provider_call": (("side_effect_counters", "provider_api_rpc_wss_calls"), 1),
            "external_authority": (("non_claims", "external_capture_authorized"), True),
            "h07_h01_evidence": (("non_claims", "technical_pilot_is_h07_h01_evidence"), True),
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

    def test_catalog_registers_every_a9_asset_from_its_owner(self) -> None:
        catalog = load_yaml(CATALOG_CORE_PATH)
        records = {record["asset_id"]: record for record in catalog["records"]}
        for asset_id, path in CATALOG_ASSET_IDS.items():
            with self.subTest(asset_id=asset_id):
                self.assertEqual(
                    records[asset_id]["location"]["repository_path"],
                    path.relative_to(ROOT).as_posix(),
                )
        self.assertIn(
            {
                "relation_type": "validated_by",
                "target_asset_id": "TEST-T30-NAMED-PARTIAL-CAPTURE-001",
            },
            records["EVIDENCE-T30-A9-NAMED-PARTIAL-CAPTURE-001"]["relations"],
        )


if __name__ == "__main__":
    unittest.main()
