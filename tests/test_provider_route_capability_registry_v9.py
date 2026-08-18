from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.provider_route_capability_registry import ProviderRouteRegistryError  # noqa: E402
from solana_alpha_lab.provider_route_capability_registry_v7 import V6_SHA256  # noqa: E402
from solana_alpha_lab.provider_route_capability_registry_v8 import V7_SHA256  # noqa: E402
from solana_alpha_lab.provider_route_capability_registry_v9 import (  # noqa: E402
    FREE_KEY_ROUTE_IDS,
    V8_SHA256,
    resolve_provider_route_v9,
    validate_provider_route_capability_registry_v9,
)


V6_PATH = ROOT / "configs/provider_route_capability_registry_v6.yaml"
V7_PATH = ROOT / "configs/provider_route_capability_registry_v7.yaml"
V8_PATH = ROOT / "configs/provider_route_capability_registry_v8.yaml"
V9_PATH = ROOT / "configs/provider_route_capability_registry_v9.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/provider_route_capability_registry_v9.schema.json"
QUALIFICATION_RUNTIME_PATH = (
    ROOT
    / "docs/evidence/quote_native_evidence_channel_qualification"
    / "a1_quote_native_evidence_channel_qualification_runtime_receipt_v1.json"
)
TIMING_RECOVERY_PATH = (
    ROOT
    / "docs/evidence/quote_native_evidence_channel_qualification"
    / "a1_quote_native_evidence_channel_qualification_timing_recovery_v1.json"
)
CLOSURE_PATH = (
    ROOT
    / "docs/evidence/quote_native_live_variation_campaign"
    / "a2_replan_closure_v1.json"
)
PRIOR_RUNTIME_PATH = (
    ROOT
    / "docs/evidence/quote_native_live_variation_campaign"
    / "a1_quote_native_live_variation_campaign_runtime_receipt_v1.json"
)
PRIOR_ACCEPTANCE_PATH = (
    ROOT
    / "docs/evidence/quote_native_live_variation_campaign"
    / "a1_quote_native_live_variation_campaign_acceptance_v1.json"
)
PRIOR_TASK_PATH = ROOT / "docs/tasks/QUOTE_NATIVE_LIVE_VARIATION_CAMPAIGN_V1.md"


def _frontmatter(path: Path) -> dict[str, object]:
    _, frontmatter, _ = path.read_text(encoding="utf-8").split("---", 2)
    loaded = yaml.safe_load(frontmatter)
    if not isinstance(loaded, dict):
        raise AssertionError("frontmatter")
    return loaded


class ProviderRouteRegistryV9Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.v6 = yaml.safe_load(V6_PATH.read_text(encoding="utf-8"))
        self.v7 = yaml.safe_load(V7_PATH.read_text(encoding="utf-8"))
        self.v8 = yaml.safe_load(V8_PATH.read_text(encoding="utf-8"))
        self.v9 = yaml.safe_load(V9_PATH.read_text(encoding="utf-8"))
        self.v6_sha = hashlib.sha256(V6_PATH.read_bytes()).hexdigest()
        self.v7_sha = hashlib.sha256(V7_PATH.read_bytes()).hexdigest()
        self.v8_sha = hashlib.sha256(V8_PATH.read_bytes()).hexdigest()

    def _validate(self, registry: dict[str, object]) -> tuple[object, ...]:
        return validate_provider_route_capability_registry_v9(
            registry,
            predecessor=self.v8,
            predecessor_sha256=self.v8_sha,
            v7_registry=self.v7,
            v7_sha256=self.v7_sha,
            v6_registry=self.v6,
            v6_sha256=self.v6_sha,
        )

    def test_v8_bytes_remain_the_bound_predecessor(self) -> None:
        self.assertEqual(self.v6_sha, V6_SHA256)
        self.assertEqual(self.v7_sha, V7_SHA256)
        self.assertEqual(self.v8_sha, V8_SHA256)

    def test_schema_preserves_v8_and_records_three_observed_free_key_routes(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(self.v9)

        routes = self._validate(self.v9)
        self.assertEqual(len(routes), 12)
        self.assertEqual(self.v9["routes"][:9], self.v8["routes"])
        added = self.v9["routes"][9:]
        self.assertEqual(tuple(route["route_id"] for route in added), FREE_KEY_ROUTE_IDS)
        self.assertEqual(
            {route["access_class"] for route in added},
            {"LOCAL_ENV_CREDENTIAL"},
        )
        self.assertEqual(
            {route["endpoint_family"] for route in added},
            {"tokens/v2/recent", "tokens/v2/toptraded/1h", "swap/v2/order"},
        )
        runtime_sha = hashlib.sha256(QUALIFICATION_RUNTIME_PATH.read_bytes()).hexdigest()
        recovery_sha = hashlib.sha256(TIMING_RECOVERY_PATH.read_bytes()).hexdigest()
        self.assertTrue(
            all(route["last_success"]["http_status"] == 200 for route in added)
        )
        self.assertTrue(
            all(route["last_observation"]["http_status"] == 200 for route in added)
        )
        self.assertTrue(
            all(
                route["last_observation"]["observed_at_semantics"]
                == "LOCAL_RAW_WRITE_COMPLETE_UPPER_BOUND"
                for route in added
            )
        )
        self.assertTrue(
            all(
                route["evidence"]["last_observation_receipt_sha256"] == runtime_sha
                for route in added
            )
        )
        self.assertTrue(
            all(
                route["evidence"]["timing_recovery_receipt_sha256"] == recovery_sha
                for route in added
            )
        )
        order = added[2]
        self.assertEqual(order["evidence"]["observed_request_count"], 48)
        self.assertEqual(order["evidence"]["http_status_counts"], {"200": 42, "400": 6})
        self.assertTrue(
            all(route["execution_policy"]["authority_granted"] is False for route in added)
        )

    def test_rejects_access_class_drift_for_a_free_key_route(self) -> None:
        tampered = copy.deepcopy(self.v9)
        tampered["routes"][9]["access_class"] = "KEYLESS"

        with self.assertRaisesRegex(ProviderRouteRegistryError, "FREE_KEY_ACCESS_DRIFT"):
            self._validate(tampered)

    def test_resolves_each_free_key_route_only_after_predecessor_validation(self) -> None:
        for route_id in FREE_KEY_ROUTE_IDS:
            route = resolve_provider_route_v9(
                self.v9,
                route_id,
                predecessor=self.v8,
                predecessor_sha256=self.v8_sha,
                v7_registry=self.v7,
                v7_sha256=self.v7_sha,
                v6_registry=self.v6,
                v6_sha256=self.v6_sha,
            )
            self.assertEqual(route["route_id"], route_id)
            self.assertEqual(route["execution_policy"]["retry"], False)
            self.assertEqual(route["execution_policy"]["fallback"], False)

    def test_replan_closure_preserves_the_prior_sample_invalid_evidence(self) -> None:
        closure = json.loads(CLOSURE_PATH.read_text(encoding="utf-8"))
        prior_task = _frontmatter(PRIOR_TASK_PATH)
        runtime_sha = hashlib.sha256(PRIOR_RUNTIME_PATH.read_bytes()).hexdigest()
        acceptance_sha = hashlib.sha256(PRIOR_ACCEPTANCE_PATH.read_bytes()).hexdigest()

        self.assertEqual(prior_task["status"], "DONE")
        self.assertEqual(closure["prior_task_id"], "QUOTE_NATIVE_LIVE_VARIATION_CAMPAIGN_V1")
        self.assertEqual(
            closure["prior_terminal"],
            "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY",
        )
        self.assertEqual(
            closure["replan_task_id"],
            "QUOTE_NATIVE_EVIDENCE_CHANNEL_QUALIFICATION_V1",
        )
        self.assertEqual(closure["prior_runtime_sha256"], runtime_sha)
        self.assertEqual(closure["prior_acceptance_sha256"], acceptance_sha)
        self.assertFalse(closure["alpha_claim"])
        self.assertFalse(closure["move_2_earned"])
        self.assertFalse(closure["historical_receipts_rewritten"])


if __name__ == "__main__":
    unittest.main()
