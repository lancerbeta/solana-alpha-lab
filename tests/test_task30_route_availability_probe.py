from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    from solana_alpha_lab.task30_route_availability_probe import validate_probe_policy
except ModuleNotFoundError:
    validate_probe_policy = None


POLICY_PATH = ROOT / "configs" / "task30_route_availability_probe_v1.yaml"
SCHEMA_PATH = ROOT / "catalog" / "schemas" / "task30_route_availability_probe.schema.json"
FROZEN_PATH = ROOT / "configs" / "task28_rc001_registry_freeze_v1.yaml"


def load_yaml(path: Path) -> dict[str, object]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def frozen_group() -> dict[str, object]:
    registry = load_yaml(FROZEN_PATH)
    groups = registry["hypothesis_groups"]
    assert isinstance(groups, list)
    return next(
        group
        for group in groups
        if group["group_id"] == "RC001-H07-H01-LIQUIDITY-RETENTION"
    )


class Task30RouteAvailabilityProbeTests(unittest.TestCase):
    def test_tracked_policy_binds_frozen_15m_group_a10_and_zero_authority(self) -> None:
        self.assertIsNotNone(validate_probe_policy, "policy validator is missing")
        policy = load_yaml(POLICY_PATH)
        jsonschema.validate(policy, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
        validate_probe_policy(policy, frozen_group())
        self.assertEqual(policy["probe_shape"]["boundaries"], 3)
        self.assertEqual(policy["probe_shape"]["offset_seconds"], [0, 15, 30, 60])
        self.assertEqual(policy["authority"]["provider_api_rpc_wss_calls"], 0)


if __name__ == "__main__":
    unittest.main()
