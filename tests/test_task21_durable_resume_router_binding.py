from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "task21_durable_resume_router_binding_v1.yaml"
FINAL_CONFIG_PATH = ROOT / "configs" / "task21_final_owner_pulse_v1.yaml"
MARKER_PATH = ROOT / "control" / "active_time_gates.json"
ACCEPTANCE_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task21"
    / "durable_resume_router_binding_acceptance_v1.json"
)
AGENTS_PATH = ROOT / "AGENTS.md"
OWNER_PULSE_SCRIPT = ROOT / "scripts" / "show_task21_final_owner_pulse.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task21DurableResumeRouterBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.marker = json.loads(MARKER_PATH.read_text(encoding="utf-8"))
        cls.router = cls.marker["resume_router"]

    def test_single_discovery_chain_is_exact(self) -> None:
        agents = AGENTS_PATH.read_text(encoding="utf-8")
        self.assertIn("## ACTIVE_TIME_GATE_CHECK", agents)
        self.assertIn("control/active_time_gates.json", agents)
        self.assertEqual(self.router["router_id"], self.config["router_id"])
        self.assertEqual(self.router["router_version"], "1.0")
        self.assertEqual(
            self.router["status"],
            "A7_ACCEPTED_PENDING_REPOSITORY_DELIVERY",
        )
        self.assertEqual(
            self.router["entry_rule"],
            "READ_MARKER_THEN_RUN_FINAL_OWNER_PULSE_BEFORE_TASK21_CONTINUATION",
        )

    def test_router_binds_exact_config_and_owner_pulse_entrypoint(self) -> None:
        binding = self.router["binding"]
        self.assertEqual(
            binding["config"]["path"],
            "configs/task21_final_owner_pulse_v1.yaml",
        )
        self.assertEqual(binding["config"]["sha256"], _sha256(FINAL_CONFIG_PATH))
        self.assertEqual(
            binding["owner_pulse_entrypoint"]["sha256"],
            _sha256(OWNER_PULSE_SCRIPT),
        )
        self.assertEqual(binding["marker_hash_policy"], "DYNAMIC_SEMANTIC")

    def test_read_only_command_and_fallback_paths_are_relative(self) -> None:
        self.assertEqual(
            self.router["read_only_command"],
            [
                "uv",
                "run",
                "--locked",
                "--managed-python",
                "python",
                "-B",
                "scripts/show_task21_final_owner_pulse.py",
                "--json",
            ],
        )
        for value in self.router["fallback_read_set"]:
            path = Path(value)
            self.assertFalse(path.is_absolute())
            self.assertTrue((ROOT / path).is_file(), value)

    def test_due_gate_precedence_is_clear_after_h24_resolution(self) -> None:
        self.assertEqual(
            self.router["due_gate_precedence"],
            "AT_OR_AFTER_EARLIEST_AT_ROUTE_REQUIRED_NEXT_ATOM_BEFORE_NEW_MUTATION",
        )
        active = [
            gate for gate in self.marker["gates"] if gate["status"] == "ACTIVE_WAITING"
        ]
        self.assertEqual(active, [])
        self.assertIsNone(self.router["active_gate_id"])
        h24 = next(
            gate
            for gate in self.marker["gates"]
            if gate["gate_id"] == "TASK21-H24-2026-08-01T07-50-34Z"
        )
        self.assertEqual(h24["status"], "RESOLVED_WITH_EVIDENCE")
        self.assertEqual(
            h24["required_next_atom"],
            "T21-A6S_H24_FOREGROUND_CAPTURE_V1",
        )
        self.assertEqual(h24["latest_at"], None)
        self.assertEqual(
            h24["future_chain"]["status"], "DEFERRED_TRIGGER_ONLY"
        )

    def test_router_grants_zero_authority(self) -> None:
        for key, value in self.router["authority_granted_by_router"].items():
            if isinstance(value, bool):
                self.assertFalse(value, key)
            else:
                self.assertEqual(value, 0, key)

    def test_transport_truth_is_not_overclaimed(self) -> None:
        transport = self.router["transport_visibility"]
        self.assertEqual(transport["same_checkout"], "IMMEDIATE")
        self.assertEqual(
            transport["fresh_clone"], "REQUIRES_FUTURE_COMMIT_AND_TRANSPORT"
        )
        self.assertFalse(transport["commit_authorized_by_router"])

    def test_acceptance_binds_exact_forward_candidate(self) -> None:
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(
            receipt["verdict"],
            "DURABLE_RESUME_ROUTER_BOUND_TO_MANDATORY_MARKER_AND_OWNER_PULSE",
        )
        self.assertEqual(receipt["targeted_validation"], "31_OF_31_PASS")
        forward_evolved = {
            "control/active_time_gates.json",
            "tests/test_task21_durable_resume_router_binding.py",
            "tests/test_task21_post_h6_gap_sentinel_value_rebase.py",
        }
        for artifact in receipt["artifacts"]:
            if artifact["path"] in forward_evolved:
                continue
            self.assertEqual(
                _sha256(ROOT / artifact["path"]), artifact["sha256"], artifact["path"]
            )
        for artifact in receipt["protected_inputs"]:
            self.assertEqual(
                _sha256(ROOT / artifact["path"]), artifact["sha256"], artifact["path"]
            )
        for value in receipt["actual_actions"].values():
            if isinstance(value, bool):
                self.assertFalse(value)
            else:
                self.assertEqual(value, 0)


if __name__ == "__main__":
    unittest.main()
