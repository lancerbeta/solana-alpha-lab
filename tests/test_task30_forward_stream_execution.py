from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/task30_forward_stream_execution_adapter_v1.yaml"
SCHEMA_PATH = (
    ROOT / "catalog/schemas/task30_forward_stream_execution_adapter.schema.json"
)
FIXTURE_PATH = (
    ROOT / "tests/fixtures/task30/forward_stream_execution_adapter_v1.json"
)


def expected_policy() -> dict[str, object]:
    return {
        "schema": "smial.task30.forward-stream-execution-adapter.policy",
        "schema_version": "1.0",
        "task_id": "TASK-30",
        "atom_id": "T30-A14P_FORWARD_STREAM_EXECUTION_ADAPTER_V1",
        "consumer": "EXACT_OWNER_FORWARD_STREAM_EXTERNAL_GATE",
        "runtime_policy": "configs/task30_forward_stream_runtime_harness_v1.yaml",
        "retention": {
            "class": "A4",
            "logical_root": "local/task30_forward_stream",
            "started_receipt": "attempt_started.json",
            "manifest": "raw_manifest.json",
            "terminal_receipt": "terminal_receipt.json",
            "create_only": True,
        },
        "credential": {
            "environment_variable": "HELIUS_API_KEY",
            "read_after_started_receipt": True,
        },
        "execution": {
            "max_attempts": 1,
            "retry": False,
            "reconnect": False,
            "fallback": False,
            "scheduler": False,
        },
        "authority": {
            "provider_api_rpc_wss_calls": 0,
            "credential_read": False,
            "raw_external_data_write": False,
        },
        "decision": "OFFLINE_EXECUTION_ADAPTER_PENDING_IMPLEMENTATION",
        "project_sources_disposition": "NO_CHANGE",
    }


class Task30ForwardStreamExecutionPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.validator = Draft202012Validator(self.schema)

    def assert_rejected(self, candidate: dict[str, object]) -> None:
        self.assertNotEqual(list(self.validator.iter_errors(candidate)), [])

    def test_policy_schema_and_fixture_freeze_exact_offline_contract(self) -> None:
        self.assertEqual(self.policy, expected_policy())
        self.assertEqual(self.fixture, expected_policy())
        self.assertEqual(list(self.validator.iter_errors(self.policy)), [])

    def test_schema_closes_every_object_layer(self) -> None:
        stack = [self.schema]
        object_nodes = []
        while stack:
            node = stack.pop()
            if not isinstance(node, dict):
                continue
            if node.get("type") == "object":
                object_nodes.append(node)
            stack.extend(node.values())
        self.assertGreaterEqual(len(object_nodes), 5)
        self.assertTrue(
            all(node.get("additionalProperties") is False for node in object_nodes)
        )

    def test_schema_rejects_extra_keys_and_alternate_local_bindings(self) -> None:
        mutations = []

        extra = copy.deepcopy(self.policy)
        extra["notes"] = "not allowed"
        mutations.append(extra)

        alternate_root = copy.deepcopy(self.policy)
        alternate_root["retention"]["logical_root"] = "local/elsewhere"  # type: ignore[index]
        mutations.append(alternate_root)

        alternate_environment = copy.deepcopy(self.policy)
        alternate_environment["credential"]["environment_variable"] = "OTHER_KEY"  # type: ignore[index]
        mutations.append(alternate_environment)

        for candidate in mutations:
            with self.subTest(candidate=candidate):
                self.assert_rejected(candidate)

    def test_schema_rejects_type_confusion_and_any_offline_authority(self) -> None:
        mutations = []

        boolean_attempts = copy.deepcopy(self.policy)
        boolean_attempts["execution"]["max_attempts"] = True  # type: ignore[index]
        mutations.append(boolean_attempts)

        for key, value in (
            ("provider_api_rpc_wss_calls", 1),
            ("credential_read", True),
            ("raw_external_data_write", True),
        ):
            candidate = copy.deepcopy(self.policy)
            candidate["authority"][key] = value  # type: ignore[index]
            mutations.append(candidate)

        for candidate in mutations:
            with self.subTest(candidate=candidate):
                self.assert_rejected(candidate)


if __name__ == "__main__":
    unittest.main()
