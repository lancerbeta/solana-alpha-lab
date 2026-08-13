from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_terminal_route_decision import (  # noqa: E402
    DECISION,
    TerminalRouteDecisionError,
    evaluate_terminal_decision,
    render_terminal_readout,
    validate_terminal_decision,
)

CONFIG = ROOT / "configs/task30_terminal_route_decision_v1.yaml"
SCHEMA = ROOT / "catalog/schemas/task30_terminal_route_decision.schema.json"
FIXTURE = ROOT / "tests/fixtures/task30/terminal_route_decision_v1.json"
MODULE = ROOT / "src/solana_alpha_lab/task30_terminal_route_decision.py"
SCRIPT = ROOT / "scripts/show_task30_terminal_route_decision.py"
REPORT = ROOT / "docs/reports/task30/terminal_route_decision_readout_v1.md"
TASK = ROOT / "docs/tasks/TASK-30-terminal-route-decision.md"
CONTRACT = ROOT / "docs/contracts/task30_terminal_route_decision_contract_v1.md"
ACCEPTANCE = ROOT / "docs/evidence/task30/a19_terminal_route_decision_acceptance_v1.json"
CATALOG = ROOT / "catalog/assets/core.yaml"
NEGATIVE = ROOT / "registries/decisions_negative_results.yaml"

EVIDENCE = {
    "task30_a5r1_birdeye": "a4f69df4dcff2afe88c06828884ec9155af8bfe91b659080cfed74ab1acbcdf1",
    "task30_a11e_gecko": "28d246c97a7e6866760683c6e63296f9d310a2cce35ac98be61e107af9f7bcdb",
    "task30_a14p_r2": "179c2b26c6a6d325388ec04c388fae8efa4adc8ba01639c85c70e5626e405604",
    "task30_a15p": "ee40a42a49bb470b4cde81d5d7b59bbb3209ecfa8aecd9e73b92f01a0beffbf7",
    "task30_a16p": "32868bff924719ba364ec0ed07e63436764a4c86032b6624f1e6439656edfe52",
    "task30_a17": "3647b41e13ed4e16da9927de196c39c4feac17bc062f8d17df22d61a2c1bc48e",
    "task30_a18_readiness": "fdad06e5e88f06334c31899416010980e3a2961820640f8e3af65f248a8e6c46",
    "task30_a18_runtime": "eea7b1e1a45aa862bd2a8fb65ba32e430ceeb525c8f8870169986930c6b67448",
}


def load_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task30TerminalRouteDecisionTests(unittest.TestCase):
    def test_policy_schema_and_evaluator_are_exact(self) -> None:
        config = load_yaml(CONFIG)
        jsonschema.validate(config, json.loads(SCHEMA.read_text(encoding="utf-8")))
        validate_terminal_decision(config)
        result = evaluate_terminal_decision(config)
        self.assertEqual(result["decision"], DECISION)
        self.assertEqual(result["h07_h01_state"], "BLOCKED_DATA")
        self.assertFalse(result["hypothesis_closed"])
        self.assertFalse(result["provider_globally_unavailable"])

    def test_all_eight_prior_receipts_are_hash_bound(self) -> None:
        config = load_yaml(CONFIG)
        self.assertEqual(set(config["evidence"]), set(EVIDENCE))
        for evidence_id, expected_hash in EVIDENCE.items():
            binding = config["evidence"][evidence_id]
            path = ROOT / binding["path"]
            self.assertTrue(path.is_file(), evidence_id)
            self.assertEqual(binding["sha256"], expected_hash)
            self.assertEqual(digest(path), expected_hash)

    def test_route_close_does_not_close_hypothesis_or_provider_universe(self) -> None:
        config = load_yaml(CONFIG)
        for field, replacement in {
            "decision": "CLOSE_ROUTE",
            "hypothesis_closed": True,
            "provider_globally_unavailable": True,
            "h07_h01_state": "STOPPED",
            "trial_admissible": True,
        }.items():
            candidate = copy.deepcopy(config)
            candidate[field] = replacement
            with self.subTest(field=field), self.assertRaises(TerminalRouteDecisionError):
                validate_terminal_decision(candidate)

    def test_authority_and_claim_promotions_are_rejected(self) -> None:
        config = load_yaml(CONFIG)
        for section, field, replacement in (
            ("authority", "provider_api_rpc_wss_calls", 1),
            ("authority", "cash_spend_usd_cents", 1),
            ("claims", "missing_is_zero_or_flat", True),
            ("claims", "numeric_netreturn", True),
        ):
            candidate = copy.deepcopy(config)
            candidate[section][field] = replacement
            with self.subTest(section=section, field=field), self.assertRaises(TerminalRouteDecisionError):
                validate_terminal_decision(candidate)

    def test_schema_is_closed_against_extra_evidence_or_authority(self) -> None:
        config = load_yaml(CONFIG)
        config["evidence"]["notes"] = "must reject"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(config, json.loads(SCHEMA.read_text(encoding="utf-8")))

    def test_fixture_and_readout_are_deterministic(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        result = evaluate_terminal_decision(load_yaml(CONFIG))
        for key, value in fixture["expected"].items():
            self.assertEqual(result[key], value)
        expected_report = render_terminal_readout(result)
        self.assertEqual(REPORT.read_text(encoding="utf-8"), expected_report)
        for output_format in ("json", "markdown"):
            completed = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "--format", output_format],
                cwd=ROOT,
                text=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", errors="replace"))
            stdout = completed.stdout.decode("utf-8").replace("\r\n", "\n")
            if output_format == "markdown":
                self.assertEqual(stdout, expected_report + "\n")
            else:
                self.assertEqual(json.loads(stdout)["decision"], DECISION)

    def test_negative_registry_preserves_limited_scope(self) -> None:
        registry = load_yaml(NEGATIVE)
        record = next(item for item in registry["records"] if item["record_id"] == "NEGATIVE-T30-CURRENT-DATA-ROUTE-001")
        self.assertEqual(record["status"], "RECORDED")
        self.assertIn("H07/H01", record["summary"])
        self.assertIn("not a claim about all providers", record["summary"])

    def test_acceptance_bindings_and_catalog_are_present(self) -> None:
        receipt = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
        self.assertEqual(receipt["decision"], DECISION)
        self.assertEqual(receipt["state_change"], "NONE")
        self.assertEqual(receipt["factory_fit_review"], "FULL_REVIEW")
        for binding in receipt["artifact_bindings"].values():
            path = ROOT / binding["path"]
            self.assertEqual(binding["sha256"], digest(path))
        catalog = load_yaml(CATALOG)
        ids = {record["asset_id"] for record in catalog["records"]}
        self.assertTrue({
            "CONTRACT-T30-TERMINAL-ROUTE-DECISION-001",
            "CONFIG-T30-TERMINAL-ROUTE-DECISION-001",
            "SCHEMA-T30-TERMINAL-ROUTE-DECISION-001",
            "FIXTURE-T30-TERMINAL-ROUTE-DECISION-001",
            "MODULE-T30-TERMINAL-ROUTE-DECISION-001",
            "SCRIPT-T30-TERMINAL-ROUTE-DECISION-001",
            "REPORT-T30-TERMINAL-ROUTE-DECISION-001",
            "TEST-T30-TERMINAL-ROUTE-DECISION-001",
            "EVIDENCE-T30-A19-TERMINAL-ROUTE-DECISION-001",
        }.issubset(ids))


if __name__ == "__main__":
    unittest.main()
