from __future__ import annotations

import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from statistics import median

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
from solana_alpha_lab.factory.operational_store import OperationalStore
from solana_alpha_lab.factory.t0_friction_screen import (
    CUTOFF_N_COMPLETE_XY,
    FORBIDDEN_PEEKED_CUTOFF_TEXT,
    FROZEN_X_CUTOFF,
    FROZEN_X_CUTOFF_TEXT,
    SOURCE_RECEIPT_SHA256,
    classify_prior_git_t0_friction_screen,
    load_t0_friction_screen_rule,
)
from solana_alpha_lab.quote_native_admissible_friction_audition import (
    T0_FRICTION_SCREEN_ATOM_ID,
    T0_FRICTION_SCREEN_AUTHORITY_PHRASE,
    canonical_json,
    validate_policy,
)


SPEC_RELATIVE = "configs/experiment_specs/prior_git_t0_friction_screen_v1.yaml"
POLICY_RELATIVE = "configs/quote_native_prior_git_t0_friction_screen_audition_v1.yaml"
RULE_RELATIVE = "configs/prior_git_t0_friction_screen_rule_v1.yaml"
SELECTOR = ROOT / "configs/factory_v1_prior_git_t0_friction_screen_v1.yaml"
SELECTOR_SCHEMA = ROOT / "catalog/schemas/factory_v1_prior_git_t0_friction_screen.schema.json"
SPEC_SCHEMA = ROOT / "catalog/schemas/experiment_spec.schema.json"
RUNNER = ROOT / "src/solana_alpha_lab/factory/runner.py"
ATOM5_RUNTIME = (
    "docs/evidence/fresh_oos_friction_veto/a5_fresh_oos_friction_veto_runtime_receipt_v1.json"
)


def _copy(root: Path, relative: str) -> None:
    src = ROOT / relative
    dst = root / relative
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())


def isolated_t0_root(tmp: Path) -> Path:
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
        "configs/factory_v1_prior_git_t0_friction_screen_v1.yaml",
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


class PriorGitT0FrictionScreenTests(unittest.TestCase):
    def test_frozen_configs_are_composition_not_vps(self) -> None:
        selector = yaml.safe_load(SELECTOR.read_text(encoding="utf-8"))
        jsonschema.validate(
            selector, json.loads(SELECTOR_SCHEMA.read_text(encoding="utf-8"))
        )
        spec = yaml.safe_load((ROOT / SPEC_RELATIVE).read_text(encoding="utf-8"))
        jsonschema.validate(spec, json.loads(SPEC_SCHEMA.read_text(encoding="utf-8")))
        policy = yaml.safe_load((ROOT / POLICY_RELATIVE).read_text(encoding="utf-8"))
        validate_policy(policy, root=ROOT)
        self.assertEqual(policy["atom_id"], T0_FRICTION_SCREEN_ATOM_ID)
        self.assertEqual(
            policy["external_authority"]["owner_phrase"],
            T0_FRICTION_SCREEN_AUTHORITY_PHRASE,
        )
        self.assertEqual(
            spec["parameters"]["required_owner_phrase"],
            T0_FRICTION_SCREEN_AUTHORITY_PHRASE,
        )
        self.assertEqual(spec["method"], "classify_prior_git_t0_friction_screen")
        ids = [item["requirement_id"] for item in spec["data_requirements"]]
        self.assertIn("EXCLUSION_ATOM5", ids)
        dumped = yaml.safe_dump(selector) + yaml.safe_dump(spec)
        self.assertNotIn("FACTORY_V1_OPERATIONAL_READY", dumped)
        self.assertNotIn("VPS", spec["question"])

    def test_generic_runner_file_is_untouched(self) -> None:
        text = RUNNER.read_text(encoding="utf-8")
        self.assertIn("Contains no hypothesis business logic", text)
        self.assertNotIn("t0_friction_screen", text)
        self.assertNotIn("FROZEN_PRIOR_GIT", text)

    def test_frozen_cutoff_matches_prior_git_complete_xy_median(self) -> None:
        xs: list[Decimal] = []
        for relative, digest in SOURCE_RECEIPT_SHA256.items():
            payload = (ROOT / relative).read_bytes()
            self.assertEqual(__import__("hashlib").sha256(payload).hexdigest(), digest)
            receipt = json.loads(payload.decode("utf-8"))
            for cell in (receipt.get("mechanism") or {}).get("cells") or []:
                if cell.get("x_status") != "OBSERVED" or cell.get("y_status") != "OBSERVED":
                    continue
                x_value = cell.get("x_quoted_roundtrip_friction")
                y_value = cell.get("y_quoted_liquidation_recovery")
                if x_value is None or y_value is None:
                    continue
                xs.append(Decimal(str(x_value)))
        self.assertEqual(len(xs), CUTOFF_N_COMPLETE_XY)
        self.assertEqual(median(xs), FROZEN_X_CUTOFF)
        self.assertEqual(str(median(xs)), FROZEN_X_CUTOFF_TEXT)
        atom5 = json.loads((ROOT / ATOM5_RUNTIME).read_text(encoding="utf-8"))
        peeked = str((atom5.get("veto") or {}).get("x_median") or "")
        self.assertEqual(peeked, FORBIDDEN_PEEKED_CUTOFF_TEXT)
        self.assertNotEqual(FROZEN_X_CUTOFF_TEXT, peeked)

    def test_missing_phrase_is_blocked_authority_with_zero_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_t0_root(Path(tmp) / "src")
            spec = load_experiment_spec(root, SPEC_RELATIVE)
            derived = execute_capability(spec, root=root, authority_phrase=None)
            self.assertEqual(derived["status"], "BLOCKED_AUTHORITY")
            self.assertEqual(derived["blocker"], "OWNER_PHRASE_MISSING")
            self.assertEqual(derived["provider_api_rpc_wss_calls"], 0)
            self.assertEqual(derived["credential_reads"], 0)

    def test_wrong_phrase_including_go_is_blocked_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_t0_root(Path(tmp) / "src")
            spec = load_experiment_spec(root, SPEC_RELATIVE)
            derived = execute_capability(spec, root=root, authority_phrase="го")
            self.assertEqual(derived["status"], "BLOCKED_AUTHORITY")
            self.assertEqual(derived["blocker"], "AUTHORITY_PHRASE_INVALID")
            self.assertEqual(derived["provider_api_rpc_wss_calls"], 0)
            self.assertEqual(derived["credential_reads"], 0)

    def test_screen_improves_when_worse_friction_has_worse_recovery(self) -> None:
        result = classify_prior_git_t0_friction_screen(
            mechanism={
                "cells": [
                    _cell("r-bad", "-0.04", "-0.10"),
                    _cell("r-good", "-0.01", "-0.02"),
                    _cell("t-bad", "-0.05", "-0.12"),
                    _cell("t-good", "-0.01", "-0.03"),
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
        self.assertEqual(result["frozen_x_cutoff"], FROZEN_X_CUTOFF_TEXT)
        self.assertEqual(result["vetoed_n"], 2)
        self.assertEqual(result["kept_n"], 2)

    def test_screen_closes_family_without_uplift(self) -> None:
        result = classify_prior_git_t0_friction_screen(
            mechanism={
                "cells": [
                    _cell("r-bad", "-0.04", "-0.02"),
                    _cell("r-good", "-0.01", "-0.10"),
                    _cell("t-bad", "-0.05", "-0.03"),
                    _cell("t-good", "-0.01", "-0.12"),
                ]
            },
            frozen_cells=[
                _frozen("r-bad", "RECENT"),
                _frozen("r-good", "RECENT"),
                _frozen("t-bad", "TRADED"),
                _frozen("t-good", "TRADED"),
            ],
        )
        self.assertEqual(result["terminal"], "CLOSE_EXACT_T0_FRICTION_SCREEN_FAMILY")
        self.assertEqual(result["reason"], "NO_MEDIAN_OR_TAIL_UPLIFT")

    def test_one_stratum_kept_is_unstable_fail(self) -> None:
        result = classify_prior_git_t0_friction_screen(
            mechanism={
                "cells": [
                    _cell("r1", "-0.04", "-0.02"),
                    _cell("r2", "-0.05", "-0.03"),
                    _cell("t-good", "-0.01", "-0.01"),
                ]
            },
            frozen_cells=[
                _frozen("r1", "RECENT"),
                _frozen("r2", "RECENT"),
                _frozen("t-good", "TRADED"),
            ],
        )
        self.assertEqual(result["terminal"], "CLOSE_EXACT_T0_FRICTION_SCREEN_FAMILY")
        self.assertEqual(result["reason"], "STRATUM_UNSTABLE")

    def test_yaml_rule_binds_the_executed_projector(self) -> None:
        rule = load_t0_friction_screen_rule(ROOT, RULE_RELATIVE)
        result = classify_prior_git_t0_friction_screen(
            mechanism={
                "cells": [
                    _cell("r-bad", "-0.04", "-0.10"),
                    _cell("r-good", "-0.01", "-0.02"),
                    _cell("t-bad", "-0.05", "-0.12"),
                    _cell("t-good", "-0.01", "-0.03"),
                ]
            },
            frozen_cells=[
                _frozen("r-bad", "RECENT"),
                _frozen("r-good", "RECENT"),
                _frozen("t-bad", "TRADED"),
                _frozen("t-good", "TRADED"),
            ],
            rule=rule,
        )
        self.assertEqual(result["terminal"], "EXTEND_TO_SHADOW")

    def test_spec_exclusions_cover_a1_move2_commissioning_and_atom5(self) -> None:
        spec = load_experiment_spec(ROOT, SPEC_RELATIVE)
        excluded = excluded_mints_from_spec(spec, root=ROOT)
        self.assertGreaterEqual(len(excluded), 24)
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
        relative = (
            "docs/evidence/prior_git_t0_friction_screen/"
            "a6_prior_git_t0_friction_screen_runtime_receipt_v1.json"
        )
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            canonical_json(
                {
                    "atom_id": T0_FRICTION_SCREEN_ATOM_ID,
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

    def test_factory_readout_applies_screen_over_synthetic_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_t0_root(Path(tmp) / "src")
            self._write_runtime(
                root,
                terminal="DIRECTIONAL_HINT_NOT_CONFIRMATION",
                cells=[
                    _cell("r-bad", "-0.04", "-0.10"),
                    _cell("r-good", "-0.01", "-0.02"),
                    _cell("t-bad", "-0.05", "-0.12"),
                    _cell("t-good", "-0.01", "-0.03"),
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
            root = isolated_t0_root(Path(tmp) / "src")
            self._write_runtime(
                root,
                terminal="DIRECTIONAL_HINT_NOT_CONFIRMATION",
                cells=[
                    _cell("r-bad", "-0.04", "-0.02"),
                    _cell("r-good", "-0.01", "-0.10"),
                    _cell("t-bad", "-0.05", "-0.03"),
                    _cell("t-good", "-0.01", "-0.12"),
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
            self.assertEqual(derived["terminal"], "CLOSE_EXACT_T0_FRICTION_SCREEN_FAMILY")

    def test_unscored_capture_terminal_is_not_replaced_by_screen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_t0_root(Path(tmp) / "src")
            self._write_runtime(
                root,
                terminal="PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE",
                cells=[],
                frozen=[],
            )
            spec = load_experiment_spec(root, SPEC_RELATIVE)
            derived = execute_capability(spec, root=root, authority_phrase=None)
            self.assertEqual(
                derived["terminal"],
                "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE",
            )

    def test_application_default_spec_is_the_frozen_t0_screen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = OperationalStore(Path(tmp) / "ops.sqlite")
            try:
                app = FactoryApplication(root=ROOT, store=store)
                self.assertEqual(app.spec_relative, SPEC_RELATIVE)
                model = app.read_model()
                self.assertEqual(model["status"], "NOT_STARTED")
                after = app.start()
                self.assertEqual(after["status"], "BLOCKED_AUTHORITY")
                self.assertEqual(after["blocker"], "OWNER_PHRASE_MISSING")
                self.assertEqual(after["terminal_result"], "BLOCKED_AUTHORITY")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
