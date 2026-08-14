from __future__ import annotations

import copy
import hashlib
import importlib
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

REGISTRY_PATH = ROOT / "configs/provider_route_capability_registry_v4.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/provider_route_capability_registry_v4.schema.json"
RUNTIME_PATH = ROOT / "docs/evidence/task30/a20p_bitquery_named_partial_pit_route_capture_runtime_receipt_v1.json"
ACCEPTANCE_PATH = ROOT / "docs/evidence/task30/a20r1_provider_route_capability_registry_acceptance_v1.json"
CATALOG_PATH = ROOT / "catalog/assets/core.yaml"
MODULE_NAME = "solana_alpha_lab.provider_route_capability_registry_v4"
BITQUERY_ROUTE_ID = "BITQUERY-SOLANA-PUMPSWAP-OHLCV-001"
V3_SHA256 = "dfab094593c061fc2dcbe344b2e7977942927f833c2d2a83e50aa5a3e27cd95e"
RUNTIME_SHA256 = "fd7a52e6952e12fc48b9a88ed13b6dcfb28dbc9324cb767642fb28806897a185"
V3_ROUTE_HASHES = {
    "DEXSCREENER-SOLANA-TOKEN-PAIRS-KEYLESS-001": "c5d7861a4f3074784d1ecfa5614e1617be37dde2fb3e7c28f03ec5d3dd8e0055",
    "HELIUS-SOLANA-GET-SIGNATURES-001": "8852673f88c310d9e9c098a03fdcb2360150a2cfc242cf346637ac5fdd44f46d",
    "HELIUS-SOLANA-LOGS-SUBSCRIBE-001": "97cef2d76835cf484ddd24a378db3a7cb47a91eac6d5d6f179a8090c4c9514cb",
    "SOLANA-STANDARD-GET-TRANSACTION-001": "b00b7c58edebd331e6908ff19b1a4b066678b9b371362d55157c599633db4ae7",
}


def _load_yaml(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(path)
    return value


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(path)
    return value


class ProviderRouteCapabilityRegistryV4Tests(unittest.TestCase):
    def _module(self):
        try:
            return importlib.import_module(MODULE_NAME)
        except ModuleNotFoundError as exc:
            self.fail(f"production module missing: {exc}")

    def _artifacts(self) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        for path in (REGISTRY_PATH, SCHEMA_PATH, RUNTIME_PATH):
            self.assertTrue(path.is_file(), f"missing artifact: {path.relative_to(ROOT)}")
        return _load_yaml(REGISTRY_PATH), _load_json(SCHEMA_PATH), _load_json(RUNTIME_PATH)

    def test_v4_schema_preserves_exact_v3_and_adds_one_route(self) -> None:
        module = self._module()
        registry, schema, _runtime = self._artifacts()
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(registry, schema)
        routes = module.validate_provider_route_capability_registry_v4(registry)
        self.assertEqual(len(routes), 5)
        self.assertEqual(registry["supersedes"]["sha256"], V3_SHA256)
        self.assertEqual(registry["supersedes"]["preserved_route_semantic_sha256"], V3_ROUTE_HASHES)

    def test_bitquery_route_records_unknown_stop_without_invented_success(self) -> None:
        module = self._module()
        registry, _schema, runtime = self._artifacts()
        route = module.resolve_provider_route_v4(registry, BITQUERY_ROUTE_ID)
        self.assertEqual(route["provider"], "BITQUERY")
        self.assertEqual(route["runtime"]["observed_result"], "ROUTE_UNKNOWN_STOP")
        self.assertIsNone(route["last_success"])
        self.assertEqual(route["last_observation"]["terminal_class"], "ROUTE_UNKNOWN_STOP")
        self.assertEqual(route["last_observation"]["observed_at_semantics"], "RECEIPT_RECORDED_AT")
        self.assertEqual(route["last_observation"]["attempt_time_precision"], "BOUNDED_NOT_EXACT_PREPATCH")
        self.assertIsNone(route["last_observation"]["http_status"])
        self.assertIsNone(route["last_observation"]["response_bytes"])
        self.assertEqual(route["known_failures"][0]["fingerprint"], "PREPATCH_HTTPERROR_OR_TRANSPORT_COLLAPSE")
        self.assertEqual(route["evidence"]["last_observation_receipt_sha256"], RUNTIME_SHA256)
        self.assertEqual(hashlib.sha256(RUNTIME_PATH.read_bytes()).hexdigest(), RUNTIME_SHA256)
        self.assertEqual(runtime["terminal_outcome"], "ROUTE_UNKNOWN_STOP")
        self.assertIsNone(runtime["panel_counts"]["slots_observed"])

    def test_mutations_cannot_rewrite_history_or_promote_authority(self) -> None:
        module = self._module()
        registry, _schema, _runtime = self._artifacts()
        cases: list[tuple[str, dict[str, object], str]] = []
        legacy = copy.deepcopy(registry)
        legacy["routes"][0]["provider"] = "OTHER"
        cases.append(("legacy", legacy, "LEGACY_ROUTE_SEMANTICS_DRIFT"))
        success = copy.deepcopy(registry)
        success["routes"][4]["last_success"] = {
            "observed_at": "2026-08-14T12:26:53Z",
            "http_status": 200,
        }
        cases.append(("success", success, "BITQUERY_ROUTE_DRIFT"))
        authority = copy.deepcopy(registry)
        authority["routes"][4]["execution_policy"]["authority_granted"] = True
        cases.append(("authority", authority, "BITQUERY_ROUTE_DRIFT"))
        for case_id, mutated, expected in cases:
            with self.subTest(case_id=case_id):
                with self.assertRaisesRegex(module.ProviderRouteRegistryError, expected):
                    module.validate_provider_route_capability_registry_v4(mutated)

    def test_registry_gap_stays_unknown_not_unavailable(self) -> None:
        module = self._module()
        registry, _schema, _runtime = self._artifacts()
        with self.assertRaisesRegex(module.ProviderRouteRegistryError, "REGISTRY_GAP"):
            module.resolve_provider_route_v4(registry, "UNOBSERVED-PROVIDER-ROUTE-001")

    def test_registry_acceptance_bindings_and_catalog_ids_exist(self) -> None:
        acceptance = _load_json(ACCEPTANCE_PATH)
        for binding in acceptance["artifact_bindings"].values():
            path = ROOT / binding["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), binding["sha256"])
        catalog = _load_yaml(CATALOG_PATH)
        ids = {record["asset_id"] for record in catalog["records"]}
        self.assertTrue(
            {
                "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-004",
                "SCHEMA-PROVIDER-ROUTE-CAPABILITY-REGISTRY-004",
                "MODULE-PROVIDER-ROUTE-CAPABILITY-REGISTRY-004",
                "TEST-PROVIDER-ROUTE-CAPABILITY-REGISTRY-004",
                "EVIDENCE-T30-A20R1-PROVIDER-ROUTE-REGISTRY-001",
            }.issubset(ids)
        )


if __name__ == "__main__":
    unittest.main()
