from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/task34a_documentation_foundation_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task34a_documentation_foundation.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task34a/documentation_foundation_v1.json"
EXPECTED_MIRROR_STATES = [
    "MIRROR_MATCHES_ACTIVE_RELEASE",
    "STALE_MIRROR_ACTIVE_RELEASE_CONFIRMED",
    "MIRROR_UNAVAILABLE",
    "MIRROR_CONFLICT_REQUIRES_CONTROL_REVIEW",
]


class Task34aDocumentationFoundationTests(unittest.TestCase):
    def test_policy_is_schema_valid_and_freezes_the_four_mirror_states(self) -> None:
        """Catches an unsafe or underspecified mirror-state policy."""
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertFalse(list(Draft202012Validator(schema).iter_errors(policy)))
        self.assertEqual(policy["authority"]["provider_api_rpc_wss_calls"], False)
        self.assertEqual(policy["mirror_states"], EXPECTED_MIRROR_STATES)

    def test_fixture_binds_the_activated_release_without_a_local_path(self) -> None:
        """Catches a fixture that leaks a user directory or unbinds the release."""
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(fixture["active_release_id"], "PSR-0003-T28-RC001-FREEZE")
        self.assertNotIn("C:\\Users", json.dumps(fixture, ensure_ascii=False))
        self.assertEqual(fixture["expected_mirror_states"], EXPECTED_MIRROR_STATES)


if __name__ == "__main__":
    unittest.main()
