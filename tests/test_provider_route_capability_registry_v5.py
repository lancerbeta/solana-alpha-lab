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

REGISTRY_PATH = ROOT / "configs/provider_route_capability_registry_v5.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/provider_route_capability_registry_v5.schema.json"
RUNTIME_PATH = ROOT / "docs/evidence/task30/a22_helius_get_transactions_for_address_runtime_receipt_v1.json"
MODULE_NAME = "solana_alpha_lab.provider_route_capability_registry_v5"
ROUTE_ID = "HELIUS-SOLANA-GET-TRANSACTIONS-FOR-ADDRESS-001"
V4_SHA256 = "329d2590ff799688dfbe674ce34f5fa6cd2aa85230dfa6d8dcc22fa4980594e4"
RUNTIME_SHA256 = "bbb29e932ff2c2d68703f2f1693e8fe07a57b7ef24ffabea71c1a95436f97b15"
V4_ROUTE_HASHES = {
    "DEXSCREENER-SOLANA-TOKEN-PAIRS-KEYLESS-001": "c5d7861a4f3074784d1ecfa5614e1617be37dde2fb3e7c28f03ec5d3dd8e0055",
    "HELIUS-SOLANA-GET-SIGNATURES-001": "8852673f88c310d9e9c098a03fdcb2360150a2cfc242cf346637ac5fdd44f46d",
    "HELIUS-SOLANA-LOGS-SUBSCRIBE-001": "97cef2d76835cf484ddd24a378db3a7cb47a91eac6d5d6f179a8090c4c9514cb",
    "SOLANA-STANDARD-GET-TRANSACTION-001": "b00b7c58edebd331e6908ff19b1a4b066678b9b371362d55157c599633db4ae7",
    "BITQUERY-SOLANA-PUMPSWAP-OHLCV-001": "07140d5c257b00b9769be6d908f8e69f31739b7dfabeca1b69e0176dc410915a",
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


class ProviderRouteCapabilityRegistryV5Tests(unittest.TestCase):
    def _module(self):
        try:
            return importlib.import_module(MODULE_NAME)
        except ModuleNotFoundError as exc:
            self.fail(f"production module missing: {exc}")

    def _artifacts(self) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        for path in (REGISTRY_PATH, SCHEMA_PATH, RUNTIME_PATH):
            self.assertTrue(path.is_file(), f"missing artifact: {path.relative_to(ROOT)}")
        return _load_yaml(REGISTRY_PATH), _load_json(SCHEMA_PATH), _load_json(RUNTIME_PATH)

    def test_v5_schema_preserves_exact_v4_and_adds_one_route(self) -> None:
        module = self._module()
        registry, schema, _runtime = self._artifacts()
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(registry, schema)
        routes = module.validate_provider_route_capability_registry_v5(registry)
        self.assertEqual(len(routes), 6)
        self.assertEqual(registry["supersedes"]["sha256"], V4_SHA256)
        self.assertEqual(registry["supersedes"]["preserved_route_semantic_sha256"], V4_ROUTE_HASHES)

    def test_observation_separates_http_success_from_incomplete_one_shot(self) -> None:
        module = self._module()
        registry, _schema, runtime = self._artifacts()
        route = module.resolve_provider_route_v5(registry, ROUTE_ID)
        self.assertEqual(route["provider"], "HELIUS")
        self.assertEqual(route["operation"], "GET_TRANSACTIONS_FOR_ADDRESS_FULL")
        self.assertEqual(route["runtime"]["observed_result"], "HTTP_200_PAGINATION_REQUIRED_STOP")
        self.assertEqual(route["last_success"]["http_status"], 200)
        self.assertEqual(route["last_success"]["response_bytes"], 9_012_030)
        self.assertEqual(route["last_observation"]["terminal_class"], "PAGINATION_REQUIRED_STOP")
        self.assertEqual(route["last_observation"]["layer"], "DATA_COVERAGE")
        self.assertEqual(route["last_observation"]["transaction_count"], 520)
        self.assertTrue(route["last_observation"]["pagination_token_present"])
        self.assertEqual(route["known_failures"][0]["fingerprint"], "PAGINATION_TOKEN_PRESENT_AFTER_520_FULL_TRANSACTIONS")
        self.assertEqual(route["evidence"]["last_observation_receipt_sha256"], RUNTIME_SHA256)
        self.assertEqual(hashlib.sha256(RUNTIME_PATH.read_bytes()).hexdigest(), RUNTIME_SHA256)
        self.assertEqual(runtime["terminal_outcome"], "PAGINATION_REQUIRED_STOP")
        self.assertEqual(runtime["transaction_count"], 520)
        self.assertFalse(runtime["route_fit_for_raw_batch"])

    def test_mutations_cannot_rewrite_v4_or_promote_route_authority(self) -> None:
        module = self._module()
        registry, _schema, _runtime = self._artifacts()
        legacy = copy.deepcopy(registry)
        legacy["routes"][4]["provider"] = "OTHER"
        with self.assertRaisesRegex(module.ProviderRouteRegistryError, "LEGACY_ROUTE_SEMANTICS_DRIFT"):
            module.validate_provider_route_capability_registry_v5(legacy)
        authority = copy.deepcopy(registry)
        authority["routes"][5]["execution_policy"]["authority_granted"] = True
        with self.assertRaisesRegex(module.ProviderRouteRegistryError, "HELIUS_ROUTE_DRIFT"):
            module.validate_provider_route_capability_registry_v5(authority)
        complete = copy.deepcopy(registry)
        complete["routes"][5]["last_observation"]["terminal_class"] = "COMPLETE"
        with self.assertRaisesRegex(module.ProviderRouteRegistryError, "HELIUS_ROUTE_DRIFT"):
            module.validate_provider_route_capability_registry_v5(complete)

    def test_registry_gap_stays_unknown_not_unavailable(self) -> None:
        module = self._module()
        registry, _schema, _runtime = self._artifacts()
        with self.assertRaisesRegex(module.ProviderRouteRegistryError, "REGISTRY_GAP"):
            module.resolve_provider_route_v5(registry, "UNOBSERVED-PROVIDER-ROUTE-001")


if __name__ == "__main__":
    unittest.main()
