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

from solana_alpha_lab.provider_route_capability_registry import (
    ProviderRouteRegistryError,
    resolve_provider_route,
    validate_provider_route_capability_registry,
)


REGISTRY = ROOT / "configs/provider_route_capability_registry_v1.yaml"
SCHEMA = ROOT / "catalog/schemas/provider_route_capability_registry.schema.json"
MODULE = ROOT / "src/solana_alpha_lab/provider_route_capability_registry.py"
TEST = ROOT / "tests/test_provider_route_capability_registry.py"
AGENTS = ROOT / "AGENTS.md"
ACCEPTANCE = (
    ROOT
    / "docs/evidence/task30/a16r1_provider_route_capability_registry_acceptance_v1.json"
)
CATALOG_CORE = ROOT / "catalog/assets/core.yaml"
REQUIRED_CATALOG_ASSETS = {
    "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-001": REGISTRY,
    "SCHEMA-PROVIDER-ROUTE-CAPABILITY-REGISTRY-001": SCHEMA,
    "MODULE-PROVIDER-ROUTE-CAPABILITY-REGISTRY-001": MODULE,
    "TEST-PROVIDER-ROUTE-CAPABILITY-REGISTRY-001": TEST,
    "EVIDENCE-T30-A16R1-PROVIDER-ROUTE-CAPABILITY-REGISTRY-001": ACCEPTANCE,
    "EVIDENCE-T30-A16P-POOL-ACTIVITY-DISCRIMINATOR-RUNTIME-002": (
        ROOT
        / "docs/evidence/task30/a16p_pool_activity_discriminator_runtime_receipt_v2.json"
    ),
}


def registry() -> dict[str, object]:
    value = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError("registry fixture must be a mapping")
    return value


def schema() -> dict[str, object]:
    value = json.loads(SCHEMA.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError("schema fixture must be a mapping")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ProviderRouteCapabilityRegistryTests(unittest.TestCase):
    def test_registry_validates_and_resolves_two_observed_routes(self) -> None:
        routes = validate_provider_route_capability_registry(registry())
        self.assertEqual(
            [route["route_id"] for route in routes],
            [
                "DEXSCREENER-SOLANA-TOKEN-PAIRS-KEYLESS-001",
                "HELIUS-SOLANA-GET-SIGNATURES-001",
            ],
        )
        selected = resolve_provider_route(
            registry(), "DEXSCREENER-SOLANA-TOKEN-PAIRS-KEYLESS-001"
        )
        self.assertEqual(
            selected["last_observation"]["terminal_class"], "HTTP_SUCCESS"
        )

    def test_schema_closes_registry_and_routes(self) -> None:
        document = schema()
        jsonschema.Draft202012Validator.check_schema(document)
        jsonschema.validate(instance=registry(), schema=document)

    def test_registry_rejects_security_and_authority_widening(self) -> None:
        def secret_value(value: dict[str, object]) -> None:
            routes = value["routes"]
            assert isinstance(routes, list)
            routes[1]["evidence"]["last_observation_receipt"] = (
                "https://example.invalid/route?api" + "-key=fixture"
            )

        def authority(value: dict[str, object]) -> None:
            routes = value["routes"]
            assert isinstance(routes, list)
            routes[0]["execution_policy"]["authority_granted"] = True

        def retry(value: dict[str, object]) -> None:
            routes = value["routes"]
            assert isinstance(routes, list)
            routes[0]["execution_policy"]["retry"] = True

        def market_layer(value: dict[str, object]) -> None:
            routes = value["routes"]
            assert isinstance(routes, list)
            routes[1]["last_observation"]["layer"] = "MARKET"

        cases = {
            "SECRET_VALUE_FORBIDDEN": secret_value,
            "AUTHORITY_PROMOTION": authority,
            "RETRY_PROMOTION": retry,
            "FAILURE_LAYER_CONFLATION": market_layer,
        }
        for expected, mutate in cases.items():
            with self.subTest(expected=expected):
                candidate = copy.deepcopy(registry())
                mutate(candidate)
                with self.assertRaisesRegex(ProviderRouteRegistryError, expected):
                    validate_provider_route_capability_registry(candidate)

    def test_registry_rejects_identity_time_hash_and_path_drift(self) -> None:
        def duplicate_id(value: dict[str, object]) -> None:
            routes = value["routes"]
            assert isinstance(routes, list)
            routes[1]["route_id"] = routes[0]["route_id"]

        def non_utc(value: dict[str, object]) -> None:
            routes = value["routes"]
            assert isinstance(routes, list)
            routes[0]["last_observation"]["observed_at"] = "2026-08-12 21:17:48"

        def malformed_hash(value: dict[str, object]) -> None:
            routes = value["routes"]
            assert isinstance(routes, list)
            routes[0]["last_success"]["response_sha256"] = "abc"

        def absolute_path(value: dict[str, object]) -> None:
            routes = value["routes"]
            assert isinstance(routes, list)
            routes[0]["evidence"]["last_observation_receipt"] = (
                "C:\\Users\\operator\\raw.json"
            )

        def hash_without_bytes(value: dict[str, object]) -> None:
            routes = value["routes"]
            assert isinstance(routes, list)
            routes[0]["last_observation"]["response_bytes"] = 0

        def observation_before_success(value: dict[str, object]) -> None:
            routes = value["routes"]
            assert isinstance(routes, list)
            routes[1]["last_observation"]["observed_at"] = (
                "2026-08-12T20:00:00Z"
            )

        def bool_as_bytes(value: dict[str, object]) -> None:
            routes = value["routes"]
            assert isinstance(routes, list)
            routes[0]["last_success"]["response_bytes"] = False

        cases = {
            "DUPLICATE_ROUTE_ID": duplicate_id,
            "TIMESTAMP_INVALID": non_utc,
            "SHA256_INVALID": malformed_hash,
            "ABSOLUTE_PATH_FORBIDDEN": absolute_path,
            "RESPONSE_HASH_WITHOUT_BYTES": hash_without_bytes,
            "LAST_OBSERVATION_BEFORE_SUCCESS": observation_before_success,
            "TYPE_INVALID": bool_as_bytes,
        }
        for expected, mutate in cases.items():
            with self.subTest(expected=expected):
                candidate = copy.deepcopy(registry())
                mutate(candidate)
                with self.assertRaisesRegex(ProviderRouteRegistryError, expected):
                    validate_provider_route_capability_registry(candidate)

    def test_unknown_route_is_registry_gap_not_unavailability(self) -> None:
        with self.assertRaisesRegex(ProviderRouteRegistryError, "REGISTRY_GAP"):
            resolve_provider_route(registry(), "UNKNOWN-ROUTE")

    def test_external_route_policy_points_to_registry_before_transport(self) -> None:
        agents = AGENTS.read_text(encoding="utf-8")
        self.assertIn("PROVIDER_ROUTE_CAPABILITY_REGISTRY_V1", agents)
        self.assertIn("configs/provider_route_capability_registry_v1.yaml", agents)
        self.assertIn("REGISTRY_GAP", agents)

    def test_acceptance_binds_registry_schema_module_and_test(self) -> None:
        receipt = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
        self.assertEqual(
            receipt["decision"], "REGISTRY_VALIDATED_NO_RUNTIME_AUTHORITY"
        )
        self.assertEqual(
            receipt["runtime_observation"]["provider_calls"],
            {"dexscreener_keyless_get": 1, "helius_rpc": 1, "helius_wss": 0},
        )
        for binding in receipt["artifact_bindings"].values():
            artifact = ROOT / binding["path"]
            self.assertTrue(artifact.is_file(), binding["path"])
            self.assertEqual(binding["sha256"], sha256(artifact))

    def test_catalog_resolves_registry_and_a16p_v2_assets_by_stable_id(self) -> None:
        catalog = yaml.safe_load(CATALOG_CORE.read_text(encoding="utf-8"))
        self.assertIsInstance(catalog, dict)
        catalog_records = catalog["records"]
        self.assertIsInstance(catalog_records, list)
        records = {record["asset_id"]: record for record in catalog_records}
        for asset_id, path in REQUIRED_CATALOG_ASSETS.items():
            with self.subTest(asset_id=asset_id):
                self.assertIn(asset_id, records)
                self.assertEqual(
                    records[asset_id]["integrity"]["sha256"], sha256(path)
                )


if __name__ == "__main__":
    unittest.main()
