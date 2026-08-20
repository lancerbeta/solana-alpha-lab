from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.application import FactoryApplication
from solana_alpha_lab.factory.capabilities import (
    capture_quote_native_free_key,
    excluded_mints_from_spec,
    execute_capability,
)
from solana_alpha_lab.factory.experiment_spec import load_experiment_spec
from solana_alpha_lab.factory.operational_store import OperationalStore
from solana_alpha_lab.quote_native_admissible_friction_audition import (
    CONFIRMATORY_ATOM_ID,
    CONFIRMATORY_AUTHORITY_PHRASE,
    RETENTION_AUTHORITY_PHRASE,
    validate_policy,
)


SPEC_RELATIVE = "configs/experiment_specs/quote_surface_retention_confirmatory_v1.yaml"
POLICY_RELATIVE = "configs/quote_native_quote_surface_retention_confirmatory_audition_v1.yaml"
SELECTOR = ROOT / "configs/factory_v1_quote_surface_retention_confirmatory_v1.yaml"
SELECTOR_SCHEMA = ROOT / "catalog/schemas/factory_v1_quote_surface_retention_confirmatory.schema.json"
SPEC_SCHEMA = ROOT / "catalog/schemas/experiment_spec.schema.json"
RUNNER = ROOT / "src/solana_alpha_lab/factory/runner.py"
PR156 = (
    ROOT
    / "docs/evidence/quote_surface_retention_falsifier"
    / "a1_quote_surface_retention_falsifier_runtime_receipt_v1.json"
)
FALSIFIER_SPEC = "configs/experiment_specs/quote_surface_retention_falsifier_v1.yaml"


def _copy(root: Path, relative: str) -> None:
    src = ROOT / relative
    dst = root / relative
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())


def isolated_confirmatory_root(tmp: Path) -> Path:
    _copy(tmp, "catalog/schemas/experiment_spec.schema.json")
    _copy(tmp, SPEC_RELATIVE)
    _copy(tmp, POLICY_RELATIVE)
    spec_text = yaml.safe_load((ROOT / SPEC_RELATIVE).read_text(encoding="utf-8"))
    for item in spec_text["data_requirements"]:
        if item["kind"] == "PROVIDER_BOUNDED_CAPTURE":
            item.pop("sha256", None)
            continue
        _copy(tmp, item["path"])
    spec_dst = tmp / SPEC_RELATIVE
    spec_dst.parent.mkdir(parents=True, exist_ok=True)
    spec_dst.write_text(yaml.safe_dump(spec_text, sort_keys=False), encoding="utf-8")
    for relative in (
        "registries/hypotheses.yaml",
        "registries/research_cycles.yaml",
        "configs/provider_route_capability_registry_v6.yaml",
        "configs/provider_route_capability_registry_v7.yaml",
        "configs/provider_route_capability_registry_v8.yaml",
        "configs/provider_route_capability_registry_v9.yaml",
        "configs/factory_v1_quote_surface_retention_confirmatory_v1.yaml",
        "configs/factory_v1_product_kernel_v1.yaml",
    ):
        _copy(tmp, relative)
    return tmp


class QuoteSurfaceRetentionConfirmatoryTests(unittest.TestCase):
    def test_selector_and_spec_are_schema_valid(self) -> None:
        selector = yaml.safe_load(SELECTOR.read_text(encoding="utf-8"))
        schema = json.loads(SELECTOR_SCHEMA.read_text(encoding="utf-8"))
        jsonschema.validate(selector, schema)
        spec = yaml.safe_load((ROOT / SPEC_RELATIVE).read_text(encoding="utf-8"))
        spec_schema = json.loads(SPEC_SCHEMA.read_text(encoding="utf-8"))
        jsonschema.validate(spec, spec_schema)
        self.assertEqual(selector["atom_id"], CONFIRMATORY_ATOM_ID)
        self.assertEqual(spec["parameters"]["required_owner_phrase"], CONFIRMATORY_AUTHORITY_PHRASE)

    def test_policy_phrase_matches_constant_and_validates(self) -> None:
        policy = yaml.safe_load((ROOT / POLICY_RELATIVE).read_text(encoding="utf-8"))
        self.assertEqual(policy["atom_id"], CONFIRMATORY_ATOM_ID)
        self.assertEqual(
            policy["external_authority"]["owner_phrase"],
            CONFIRMATORY_AUTHORITY_PHRASE,
        )
        validate_policy(policy, root=ROOT)

    def test_missing_and_wrong_phrases_are_blocked_with_zero_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_confirmatory_root(Path(tmp) / "src")
            spec = load_experiment_spec(root, SPEC_RELATIVE)
            missing = execute_capability(spec, root=root, authority_phrase=None)
            self.assertEqual(missing["status"], "BLOCKED_AUTHORITY")
            self.assertEqual(missing["blocker"], "OWNER_PHRASE_MISSING")
            self.assertEqual(missing["provider_api_rpc_wss_calls"], 0)
            wrong = execute_capability(spec, root=root, authority_phrase="го")
            self.assertEqual(wrong["blocker"], "AUTHORITY_PHRASE_INVALID")
            self.assertEqual(wrong["provider_api_rpc_wss_calls"], 0)
            reused = execute_capability(
                spec,
                root=root,
                authority_phrase=RETENTION_AUTHORITY_PHRASE,
            )
            self.assertEqual(reused["blocker"], "AUTHORITY_PHRASE_INVALID")
            self.assertEqual(reused["provider_api_rpc_wss_calls"], 0)

    def test_exclusions_include_pr156_and_prior_cohorts(self) -> None:
        spec = load_experiment_spec(ROOT, SPEC_RELATIVE)
        excluded = excluded_mints_from_spec(spec, root=ROOT)
        pr156 = json.loads(PR156.read_text(encoding="utf-8"))
        consumed = {
            str(cell["mint"])
            for cell in pr156.get("frozen_cells") or []
            if isinstance(cell, dict) and cell.get("mint")
        }
        self.assertEqual(len(consumed), 12)
        self.assertTrue(consumed.issubset(excluded))
        self.assertGreaterEqual(len(excluded), 60)

    def test_consumed_156_overlay_still_pins_scientific_terminal(self) -> None:
        spec = load_experiment_spec(ROOT, FALSIFIER_SPEC)
        result = capture_quote_native_free_key(spec, root=ROOT)
        self.assertEqual(result["terminal"], "SAMPLE_INVALID_REPLAN_REQUIRED")
        self.assertEqual(result["provider_api_rpc_wss_calls"], 62)

    def test_application_default_spec_is_confirmatory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = OperationalStore(Path(tmp) / "ops.sqlite")
            try:
                app = FactoryApplication(root=ROOT, store=store)
                self.assertEqual(app.spec_relative, SPEC_RELATIVE)
            finally:
                store.close()
            root = isolated_confirmatory_root(Path(tmp) / "src")
            store = OperationalStore(Path(tmp) / "ops-isolated.sqlite")
            try:
                app = FactoryApplication(root=root, store=store)
                self.assertEqual(app.spec_relative, SPEC_RELATIVE)
                after = app.start()
                self.assertEqual(after["status"], "BLOCKED_AUTHORITY")
                self.assertEqual(after["blocker"], "OWNER_PHRASE_MISSING")
            finally:
                store.close()

    def test_runner_still_has_no_retention_logic(self) -> None:
        text = RUNNER.read_text(encoding="utf-8")
        self.assertNotIn("RETENTION_DELTA", text)
        self.assertNotIn("QUOTE_SURFACE_RETENTION", text)

    def test_live_receipt_closes_family_without_pr156_reuse(self) -> None:
        receipt_path = (
            ROOT
            / "docs/evidence/quote_surface_retention_confirmatory"
            / "c1_quote_surface_retention_confirmatory_runtime_receipt_v1.json"
        )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        pr156 = json.loads(PR156.read_text(encoding="utf-8"))
        consumed = {
            str(cell["mint"])
            for cell in pr156.get("frozen_cells") or []
            if isinstance(cell, dict) and cell.get("mint")
        }
        frozen = {
            str(cell["mint"])
            for cell in receipt.get("frozen_cells") or []
            if isinstance(cell, dict) and cell.get("mint")
        }
        self.assertEqual(receipt["atom_id"], CONFIRMATORY_ATOM_ID)
        self.assertEqual(
            receipt["terminal"],
            "CLOSE_EXACT_QUOTE_SURFACE_RETENTION_FAMILY",
        )
        self.assertEqual(receipt["provider_requests"], 62)
        self.assertEqual(receipt["credential_reads"], 1)
        self.assertFalse(consumed & frozen)
        self.assertTrue(consumed.issubset(set(receipt.get("excluded_prior_mints") or [])))
        retention = receipt["retention"]
        self.assertGreaterEqual(retention["recent_valid_n"], 4)
        self.assertGreaterEqual(retention["traded_valid_n"], 4)
        self.assertEqual(retention["reason"], "NO_MEDIAN_OR_TAIL_UPLIFT")
        self.assertNotIn("api_key=", receipt_path.read_text(encoding="utf-8"))



if __name__ == "__main__":
    unittest.main()
