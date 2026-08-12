from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
CONFIG = ROOT / "configs" / "task30_standard_pool_logs_route_v1.yaml"
SCHEMA = ROOT / "catalog" / "schemas" / "task30_standard_pool_logs_route.schema.json"
FIXTURE = ROOT / "tests" / "fixtures" / "task30" / "standard_pool_logs_route_v1.json"


def policy() -> dict[str, object]:
    loaded = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


class Task30StandardPoolLogsRouteTests(unittest.TestCase):
    def test_policy_is_closed_and_exact(self) -> None:
        document = policy()
        Draft202012Validator(
            json.loads(SCHEMA.read_text(encoding="utf-8"))
        ).validate(document)
        self.assertEqual(document["target"]["pool_address"], POOL)
        self.assertEqual(document["wire"]["method"], "logsSubscribe")
        self.assertEqual(document["wire"]["mentions"], [POOL])
        self.assertEqual(document["wire"]["commitment"], "confirmed")
        self.assertEqual(document["execution_controls"]["rpc_followups"], 0)


if __name__ == "__main__":
    unittest.main()
