from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.operational_readiness_closeout import (  # noqa: E402
    evaluate_closeout,
)

SCRIPT = ROOT / "scripts/delivery_harness.py"
READINESS = ROOT / "configs/factory_v1_operational_readiness_v1.yaml"
PROFILE = ROOT / "delivery-harness/project-profile.yaml"
CLOSEOUT = ROOT / "configs/factory_v1_operational_readiness_closeout_v1.yaml"


def load_harness():
    spec = importlib.util.spec_from_file_location("delivery_harness", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("delivery harness import unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FactoryV1ReadinessRecertificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_harness()

    def test_profile_already_binds_readiness_contract(self) -> None:
        profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
        self.assertEqual(
            profile["factory_v1_readiness_contract"],
            "configs/factory_v1_operational_readiness_v1.yaml",
        )

    def test_closeout_requires_stamp_and_profile_bind(self) -> None:
        closeout = yaml.safe_load(CLOSEOUT.read_text(encoding="utf-8"))
        by_id = {item["id"]: item for item in closeout["predicates"]}
        self.assertEqual(
            by_id["ENTRY_GATE_RESOLVES_READINESS_CONTRACT"]["require_yaml"],
            {
                "domain_policy_integration.entry_gate_resolves_this_file": True,
                "domain_policy_integration.live_invariant_owner": (
                    "scripts/delivery_harness.py"
                ),
            },
        )
        self.assertEqual(
            by_id["ENTRY_GATE_PROFILE_BINDS_READINESS_CONTRACT"]["require_yaml"],
            {
                "factory_v1_readiness_contract": (
                    "configs/factory_v1_operational_readiness_v1.yaml"
                )
            },
        )

    def test_check_harness_still_passes_after_stamp_flip(self) -> None:
        result = self.module.check_harness(ROOT)
        self.assertEqual(result["status"], "PASS")
        self.assertNotIn("FACTORY_V1_READINESS_CONTRACT_OWNER_MISMATCH", result["errors"])

    def test_false_stamp_reopens_closeout_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in (
                "configs/factory_v1_operational_readiness_v1.yaml",
                "configs/factory_v1_operational_readiness_closeout_v1.yaml",
                "delivery-harness/project-profile.yaml",
                "src/solana_alpha_lab/factory/runner.py",
            ):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            readiness = yaml.safe_load(
                (root / "configs/factory_v1_operational_readiness_v1.yaml").read_text(
                    encoding="utf-8"
                )
            )
            readiness["domain_policy_integration"]["entry_gate_resolves_this_file"] = False
            (root / "configs/factory_v1_operational_readiness_v1.yaml").write_text(
                yaml.safe_dump(readiness, sort_keys=False),
                encoding="utf-8",
            )
            # Copy remaining evidence referenced by closeout so only the stamp fails.
            closeout = yaml.safe_load(
                (root / "configs/factory_v1_operational_readiness_closeout_v1.yaml").read_text(
                    encoding="utf-8"
                )
            )
            for pred in closeout["predicates"]:
                rel = pred["evidence_path"]
                source = ROOT / rel
                if source.is_file() and not (root / rel).is_file():
                    (root / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, root / rel)
                schema_rel = pred.get("schema_path")
                if isinstance(schema_rel, str) and (ROOT / schema_rel).is_file():
                    (root / schema_rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / schema_rel, root / schema_rel)
            gate = evaluate_closeout(root)
            gap_ids = {item.split(":", 1)[0] for item in gate["named_gaps"]}
            self.assertIn("ENTRY_GATE_RESOLVES_READINESS_CONTRACT", gap_ids)
            self.assertFalse(gate["factory_v1_operational_ready"])
            self.assertEqual(gate["foundation_freeze"], "INACTIVE")

    def test_live_closeout_is_ready_and_frozen(self) -> None:
        gate = evaluate_closeout(ROOT)
        self.assertEqual(gate["terminal"], "FACTORY_V1_OPERATIONAL_READY")
        self.assertTrue(gate["factory_v1_operational_ready"])
        self.assertEqual(gate["foundation_freeze"], "ACTIVE")
        self.assertEqual(gate["named_gaps"], [])


if __name__ == "__main__":
    unittest.main()
