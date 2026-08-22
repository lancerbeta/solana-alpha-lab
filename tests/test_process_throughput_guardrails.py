from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


efficiency = load_module("delivery_efficiency", "scripts/delivery_efficiency.py")
factory_static = load_module("validate_factory_static", "scripts/validate_factory_static.py")


class DeliveryEfficiencyTests(unittest.TestCase):
    def test_classify_control_only_commit(self) -> None:
        bucket = efficiency.classify_commit(
            paths={"delivery-harness/harness.yaml"},
            subject="extend control prefixes",
        )
        self.assertEqual(bucket, "control_only")

    def test_classify_repair_commit_by_path(self) -> None:
        bucket = efficiency.classify_commit(
            paths={"catalog/assets/core.yaml"},
            subject="sync catalog hash",
        )
        self.assertEqual(bucket, "repair")

    def test_classify_substantive_commit(self) -> None:
        bucket = efficiency.classify_commit(
            paths={"src/solana_alpha_lab/factory/paper_plane.py"},
            subject="wire paper lifecycle",
        )
        self.assertEqual(bucket, "substantive")

    def test_schema_accepts_delivery_efficiency_block(self) -> None:
        schema = json.loads(
            (ROOT / "catalog/schemas/delivery_harness_completion_evidence.schema.json").read_text(
                encoding="utf-8"
            )
        )
        sample = {
            "schema": "smial.delivery-completion-evidence",
            "schema_version": "1.0",
            "acceptance_id": "TEST-EFFICIENCY-001",
            "as_of": "2026-08-22",
            "task_id": "TEST-EFFICIENCY-V1",
            "state_change": "IMPLEMENTED_UNVERIFIED",
            "base_main": "8b4b80c1446e0ce102ea9cbcd8302671e7d1e21b",
            "cloud_bundle_mode": "OWNER_MANAGED_OPTIONAL_EXPORT",
            "cloud_bundle_required_by_harness": False,
            "cloud_bundle_smoke_required": False,
            "implementation_bindings": {"README.md": "0" * 64},
            "active_stop_conditions": [],
            "owner_attention_triggers": {
                "auth_or_access_recovery": False,
                "material_owner_decision": False,
                "user_only_activation": False,
                "external_material_action": False,
                "unresolved_safety_or_truth_conflict": False,
            },
            "factory_fit": {
                "path": "docs/evidence/control/delivery_harness_factory_fit_v1.json",
                "sha256": "0" * 64,
                "verdict": "PASS",
            },
            "validation": {
                "targeted": "PASS_TARGETED",
                "independent_review": {
                    "path": "docs/evidence/control/delivery_harness_independent_review_v1.json",
                    "sha256": "0" * 64,
                    "verdict": "PASS",
                },
                "full_gate": "ENFORCED_BY_PROJECT_BOUND_VALIDATION",
                "github_ci": "ENFORCED_LIVE_AT_GUARDED_MERGE",
                "project_checks": ["PASS_SAMPLE"],
            },
            "non_claims": ["NO_ALPHA"],
            "side_effects": {"provider_calls": 0},
            "delivery_efficiency": {
                "substantive_commits": 2,
                "repair_commits": 0,
                "control_only_commits": 1,
                "repair_ratio": 0.3333,
            },
        }
        jsonschema.validate(sample, schema)

    def test_git_helper_on_harness_sync_range(self) -> None:
        payload = efficiency.compute_delivery_efficiency(
            base="364c9b025167d1c203fb52941f35845761427d45",
            head="8b4b80c1446e0ce102ea9cbcd8302671e7d1e21b",
        )
        self.assertGreaterEqual(payload["total_commits"], 2)
        self.assertIn("repair_ratio", payload)


class FactoryStaticGateTests(unittest.TestCase):
    def test_factory_static_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts/validate_factory_static.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("FACTORY_STATIC: PASS", completed.stdout)

    def test_factory_static_disables_ruff_cache(self) -> None:
        source = (ROOT / "scripts/validate_factory_static.py").read_text(encoding="utf-8")
        self.assertIn('"--no-cache"', source)


class ProcessPolicyTests(unittest.TestCase):
    def test_domain_policy_names_freeze_and_kill_switch(self) -> None:
        text = (ROOT / "delivery-harness/policies/solana-alpha-lab.md").read_text(encoding="utf-8")
        self.assertIn("CONTROL_PLANE_FREEZE_AND_CEREMONY_TAX", text)
        self.assertIn("five substantive product or research atoms", text)
        self.assertIn("repair_commits >= 2", text)
        self.assertIn("repair_ratio > 0.30", text)

    def test_owner_ux_critic_is_registered_with_triggers(self) -> None:
        critic = (ROOT / ".cursor/agents/owner-ux-critic.md").read_text(encoding="utf-8")
        protocol = (ROOT / "docs/agent/DELIVERY_HARNESS_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("owner-ux-critic", critic)
        self.assertIn("owner-operable", critic.casefold())
        self.assertIn("owner-ux-critic", protocol)
        self.assertIn("owner-operable surfaces", protocol.casefold())


if __name__ == "__main__":
    unittest.main()
