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
    drop_excluded_rows,
    excluded_mints_from_spec,
    execute_capability,
)
from solana_alpha_lab.factory.experiment_spec import load_experiment_spec
from solana_alpha_lab.factory.friction_veto import (
    classify_baseline_vs_friction_veto,
    load_friction_veto_rule,
)
from solana_alpha_lab.factory.operational_store import OperationalStore
from solana_alpha_lab.quote_native_admissible_friction_audition import (
    FRICTION_VETO_ATOM_ID,
    FRICTION_VETO_AUTHORITY_PHRASE,
    canonical_json,
    validate_policy,
)


SPEC_RELATIVE = "configs/experiment_specs/fresh_oos_baseline_vs_friction_veto_v1.yaml"
POLICY_RELATIVE = "configs/quote_native_fresh_oos_friction_veto_audition_v1.yaml"
RULE_RELATIVE = "configs/friction_veto_rule_v1.yaml"
SELECTOR = ROOT / "configs/factory_v1_friction_veto_v1.yaml"
SELECTOR_SCHEMA = ROOT / "catalog/schemas/factory_v1_friction_veto.schema.json"
SPEC_SCHEMA = ROOT / "catalog/schemas/experiment_spec.schema.json"
RUNNER = ROOT / "src/solana_alpha_lab/factory/runner.py"


def _copy(root: Path, relative: str) -> None:
    src = ROOT / relative
    dst = root / relative
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())


def isolated_veto_root(tmp: Path) -> Path:
    _copy(tmp, "catalog/schemas/experiment_spec.schema.json")
    _copy(tmp, SPEC_RELATIVE)
    _copy(tmp, POLICY_RELATIVE)
    spec = yaml.safe_load((ROOT / SPEC_RELATIVE).read_text(encoding="utf-8"))
    for item in spec["data_requirements"]:
        if item["kind"] == "PROVIDER_BOUNDED_CAPTURE":
            continue
        _copy(tmp, item["path"])
    for relative in (
        "registries/hypotheses.yaml",
        "registries/research_cycles.yaml",
        "configs/provider_route_capability_registry_v6.yaml",
        "configs/provider_route_capability_registry_v7.yaml",
        "configs/provider_route_capability_registry_v8.yaml",
        "configs/provider_route_capability_registry_v9.yaml",
        "configs/factory_v1_friction_veto_v1.yaml",
        "configs/factory_v1_product_kernel_v1.yaml",
    ):
        _copy(tmp, relative)
    return tmp


def _cell(identity: str, x: str, y: str) -> dict[str, str]:
    return {
        "identity_id": identity,
        "x_status": "OBSERVED",
        "y_status": "OBSERVED",
        "x_quoted_roundtrip_friction": x,
        "y_quoted_liquidation_recovery": y,
    }


def _frozen(identity: str, stratum: str) -> dict[str, str]:
    return {"identity_id": identity, "stratum": stratum, "mint": identity}


class FreshOosBaselineVsFrictionVetoTests(unittest.TestCase):
    def test_frozen_configs_are_composition_not_vps(self) -> None:
        selector = yaml.safe_load(SELECTOR.read_text(encoding="utf-8"))
        jsonschema.validate(
            selector, json.loads(SELECTOR_SCHEMA.read_text(encoding="utf-8"))
        )
        spec = yaml.safe_load((ROOT / SPEC_RELATIVE).read_text(encoding="utf-8"))
        jsonschema.validate(spec, json.loads(SPEC_SCHEMA.read_text(encoding="utf-8")))
        policy = yaml.safe_load((ROOT / POLICY_RELATIVE).read_text(encoding="utf-8"))
        validate_policy(policy, root=ROOT)
        self.assertEqual(policy["atom_id"], FRICTION_VETO_ATOM_ID)
        self.assertEqual(policy["external_authority"]["owner_phrase"], FRICTION_VETO_AUTHORITY_PHRASE)
        self.assertEqual(spec["parameters"]["required_owner_phrase"], FRICTION_VETO_AUTHORITY_PHRASE)
        self.assertEqual(spec["method"], "classify_baseline_vs_friction_veto")
        self.assertIn("EXCLUSION_COMMISSIONING", [item["requirement_id"] for item in spec["data_requirements"]])
        dumped = yaml.safe_dump(selector) + yaml.safe_dump(spec)
        self.assertNotIn("FACTORY_V1_OPERATIONAL_READY", dumped)

    def test_generic_runner_file_is_untouched(self) -> None:
        text = RUNNER.read_text(encoding="utf-8")
        self.assertIn("Contains no hypothesis business logic", text)
        self.assertNotIn("friction_veto", text)
        self.assertNotIn("VETO_IF_X", text)

    def test_missing_phrase_is_blocked_authority_with_zero_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_veto_root(Path(tmp) / "src")
            spec = load_experiment_spec(root, SPEC_RELATIVE)
            derived = execute_capability(spec, root=root, authority_phrase=None)
            self.assertEqual(derived["status"], "BLOCKED_AUTHORITY")
            self.assertEqual(derived["blocker"], "OWNER_PHRASE_MISSING")
            self.assertEqual(derived["provider_api_rpc_wss_calls"], 0)
            self.assertEqual(derived["credential_reads"], 0)

    def test_wrong_phrase_is_blocked_authority_with_zero_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_veto_root(Path(tmp) / "src")
            spec = load_experiment_spec(root, SPEC_RELATIVE)
            derived = execute_capability(spec, root=root, authority_phrase="го")
            self.assertEqual(derived["status"], "BLOCKED_AUTHORITY")
            self.assertEqual(derived["blocker"], "AUTHORITY_PHRASE_INVALID")
            self.assertEqual(derived["provider_api_rpc_wss_calls"], 0)
            self.assertEqual(derived["credential_reads"], 0)

    def test_veto_improves_when_worse_friction_has_worse_recovery(self) -> None:
        result = classify_baseline_vs_friction_veto(
            mechanism={
                "cells": [
                    _cell("r-bad", "-0.04", "-0.10"),
                    _cell("r-good", "-0.01", "-0.02"),
                    _cell("t-bad", "-0.05", "-0.12"),
                    _cell("t-good", "-0.02", "-0.03"),
                ]
            },
            frozen_cells=[
                _frozen("r-bad", "RECENT"),
                _frozen("r-good", "RECENT"),
                _frozen("t-bad", "TRADED"),
                _frozen("t-good", "TRADED"),
            ],
        )
        self.assertEqual(result["terminal"], "EXTEND_TO_SHADOW")
        self.assertEqual(result["vetoed_n"], 2)
        self.assertEqual(result["kept_n"], 2)

    def test_veto_closes_family_without_uplift(self) -> None:
        result = classify_baseline_vs_friction_veto(
            mechanism={
                "cells": [
                    _cell("r-bad", "-0.04", "-0.02"),
                    _cell("r-good", "-0.01", "-0.10"),
                    _cell("t-bad", "-0.05", "-0.03"),
                    _cell("t-good", "-0.02", "-0.12"),
                ]
            },
            frozen_cells=[
                _frozen("r-bad", "RECENT"),
                _frozen("r-good", "RECENT"),
                _frozen("t-bad", "TRADED"),
                _frozen("t-good", "TRADED"),
            ],
        )
        self.assertEqual(result["terminal"], "CLOSE_EXACT_FRICTION_VETO_FAMILY")
        self.assertEqual(result["reason"], "NO_MEDIAN_OR_TAIL_UPLIFT")

    def test_one_stratum_kept_is_unstable_fail(self) -> None:
        result = classify_baseline_vs_friction_veto(
            mechanism={
                "cells": [
                    _cell("r1", "-0.01", "-0.02"),
                    _cell("r2", "-0.02", "-0.03"),
                    _cell("t-bad", "-0.09", "-0.20"),
                ]
            },
            frozen_cells=[
                _frozen("r1", "RECENT"),
                _frozen("r2", "RECENT"),
                _frozen("t-bad", "TRADED"),
            ],
        )
        self.assertEqual(result["terminal"], "CLOSE_EXACT_FRICTION_VETO_FAMILY")
        self.assertEqual(result["reason"], "STRATUM_UNSTABLE")

    def test_yaml_rule_binds_the_executed_projector(self) -> None:
        rule = load_friction_veto_rule(ROOT, RULE_RELATIVE)
        result = classify_baseline_vs_friction_veto(
            mechanism={"cells": [_cell("r-bad", "-0.04", "-0.10"), _cell("r-good", "-0.01", "-0.02"), _cell("t-bad", "-0.05", "-0.12"), _cell("t-good", "-0.02", "-0.03")]},
            frozen_cells=[_frozen("r-bad", "RECENT"), _frozen("r-good", "RECENT"), _frozen("t-bad", "TRADED"), _frozen("t-good", "TRADED")],
            rule=rule,
        )
        self.assertEqual(result["terminal"], "EXTEND_TO_SHADOW")

    def test_spec_exclusions_cover_a1_move2_and_commissioning_mints(self) -> None:
        spec = load_experiment_spec(ROOT, SPEC_RELATIVE)
        excluded = excluded_mints_from_spec(spec, root=ROOT)
        self.assertGreaterEqual(len(excluded), 12)
        for item in spec["data_requirements"]:
            if item["kind"] != "GIT_CANONICAL_RECEIPT":
                continue
            receipt = json.loads((ROOT / item["path"]).read_text(encoding="utf-8"))
            mints = {
                str(cell["mint"])
                for cell in receipt.get("frozen_cells") or []
                if isinstance(cell, dict) and cell.get("mint")
            }
            self.assertTrue(mints)
            self.assertTrue(mints.issubset(excluded), item["requirement_id"])
        kept = drop_excluded_rows(
            [{"id": sorted(excluded)[0]}, {"id": "fresh-mint-not-in-prior-receipts"}],
            excluded,
        )
        self.assertEqual([row["id"] for row in kept], ["fresh-mint-not-in-prior-receipts"])

    def _write_runtime(self, root: Path, *, terminal: str, cells: list, frozen: list) -> None:
        relative = "docs/evidence/fresh_oos_friction_veto/a5_fresh_oos_friction_veto_runtime_receipt_v1.json"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            canonical_json(
                {
                    "atom_id": FRICTION_VETO_ATOM_ID,
                    "terminal_outcome": terminal,
                    "mechanism": {"scored": True, "cells": cells, "verdict": terminal},
                    "frozen_cells": frozen,
                    "h3600_role": "PREDECLARED_ROBUSTNESS_NOT_SEARCHABLE_Y",
                    "provider_requests": 0,
                    "credential_reads": 0,
                    "non_claims": ["NO_ALPHA"],
                }
            )
        )

    def test_factory_readout_applies_veto_over_synthetic_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_veto_root(Path(tmp) / "src")
            self._write_runtime(
                root,
                terminal="DIRECTIONAL_HINT_NOT_CONFIRMATION",
                cells=[
                    _cell("r-bad", "-0.04", "-0.10"),
                    _cell("r-good", "-0.01", "-0.02"),
                    _cell("t-bad", "-0.05", "-0.12"),
                    _cell("t-good", "-0.02", "-0.03"),
                ],
                frozen=[
                    _frozen("r-bad", "RECENT"),
                    _frozen("r-good", "RECENT"),
                    _frozen("t-bad", "TRADED"),
                    _frozen("t-good", "TRADED"),
                ],
            )
            spec = load_experiment_spec(root, SPEC_RELATIVE)
            derived = execute_capability(spec, root=root, authority_phrase=None)
            self.assertEqual(derived["status"], "COMPLETE")
            self.assertEqual(derived["terminal"], "EXTEND_TO_SHADOW")
            self.assertEqual(derived["provider_api_rpc_wss_calls"], 0)
            self.assertEqual(derived["credential_reads"], 0)

    def test_factory_readout_closes_family_without_uplift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_veto_root(Path(tmp) / "src")
            self._write_runtime(
                root,
                terminal="DIRECTIONAL_HINT_NOT_CONFIRMATION",
                cells=[
                    _cell("r-bad", "-0.04", "-0.02"),
                    _cell("r-good", "-0.01", "-0.10"),
                    _cell("t-bad", "-0.05", "-0.03"),
                    _cell("t-good", "-0.02", "-0.12"),
                ],
                frozen=[
                    _frozen("r-bad", "RECENT"),
                    _frozen("r-good", "RECENT"),
                    _frozen("t-bad", "TRADED"),
                    _frozen("t-good", "TRADED"),
                ],
            )
            spec = load_experiment_spec(root, SPEC_RELATIVE)
            derived = execute_capability(spec, root=root, authority_phrase=None)
            self.assertEqual(derived["terminal"], "CLOSE_EXACT_FRICTION_VETO_FAMILY")

    def test_unscored_capture_terminal_is_not_replaced_by_veto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_veto_root(Path(tmp) / "src")
            self._write_runtime(
                root,
                terminal="PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE",
                cells=[],
                frozen=[],
            )
            spec = load_experiment_spec(root, SPEC_RELATIVE)
            derived = execute_capability(spec, root=root, authority_phrase=None)
            self.assertEqual(derived["terminal"], "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE")

    def test_application_default_spec_is_the_frozen_veto_experiment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = OperationalStore(Path(tmp) / "ops.sqlite")
            try:
                app = FactoryApplication(root=ROOT, store=store)
                self.assertEqual(app.spec_relative, SPEC_RELATIVE)
                model = app.read_model()
                self.assertTrue(model["git_archaeology_required"])
                self.assertEqual(model["cockpit"]["terminal"], "OWNER_COCKPIT_LITE_BLOCKED")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
