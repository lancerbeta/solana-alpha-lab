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

REGISTRY_PATH = ROOT / "configs/provider_route_capability_registry_v6.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/provider_route_capability_registry_v6.schema.json"
RUNTIME_PATH = ROOT / "docs/evidence/task30/a23_helius_bounded_pagination_runtime_receipt_v1.json"
ACCEPTANCE_PATH = ROOT / "docs/evidence/task30/a23_provider_route_capability_registry_acceptance_v1.json"
MODULE_NAME = "solana_alpha_lab.provider_route_capability_registry_v6"
ROUTE_ID = "HELIUS-SOLANA-GET-TRANSACTIONS-FOR-ADDRESS-001"
V5_SHA256 = "8875fcc28ae763360f183cf644c1048ba4ec3950fb31406c0f0b1e3ee22231d0"
V5_HELIUS_SHA256 = "05279d47cde9e0447f845a7324106dab8edc90abf08b52b60aebd177f5c7a440"
RUNTIME_SHA256 = "7aa03c53222f64a462270994304fe512a4b5d91e5fc3781e31ce50e26a5dbeca"
UNCHANGED_ROUTE_HASHES = {
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


class ProviderRouteCapabilityRegistryV6Tests(unittest.TestCase):
    def test_acceptance_binds_the_updated_route_and_v6_artifacts(self) -> None:
        self.assertTrue(ACCEPTANCE_PATH.is_file(), ACCEPTANCE_PATH)
        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(acceptance["decision"], "REGISTER_COMPLETE_RAW_BATCH_CANDIDATE_NO_PIT_PROMOTION")
        self.assertEqual(acceptance["updated_route"]["route_id"], ROUTE_ID)
        self.assertTrue(acceptance["updated_route"]["complete_raw_batch_candidate"])
        self.assertFalse(acceptance["updated_route"]["authority_granted"])
        for binding in acceptance["artifact_bindings"].values():
            path = ROOT / binding["path"]
            self.assertTrue(path.is_file(), path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), binding["sha256"])

    def test_v6_schema_preserves_five_routes_and_binds_updated_helius(self) -> None:
        for path in (REGISTRY_PATH, SCHEMA_PATH):
            self.assertTrue(path.is_file(), path)
        module = importlib.import_module(MODULE_NAME)
        registry = _load_yaml(REGISTRY_PATH)
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(registry, schema)
        routes = module.validate_provider_route_capability_registry_v6(registry)

        self.assertEqual(len(routes), 6)
        self.assertEqual(registry["supersedes"]["sha256"], V5_SHA256)
        self.assertEqual(
            registry["supersedes"]["preserved_route_semantic_sha256"],
            UNCHANGED_ROUTE_HASHES,
        )
        self.assertEqual(
            registry["supersedes"]["updated_route_prior_semantic_sha256"],
            {ROUTE_ID: V5_HELIUS_SHA256},
        )

    def test_observation_records_complete_raw_batch_without_pit_promotion(self) -> None:
        module = importlib.import_module(MODULE_NAME)
        registry = _load_yaml(REGISTRY_PATH)
        runtime = json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))
        route = module.resolve_provider_route_v6(registry, ROUTE_ID)

        self.assertEqual(route["runtime"]["observed_result"], "HTTP_200_COMPLETE_RAW_BATCH_CANDIDATE")
        self.assertEqual(route["last_observation"]["terminal_class"], "COMPLETE_RAW_BATCH_CANDIDATE")
        self.assertEqual(route["last_observation"]["total_transaction_count"], 520)
        self.assertEqual(route["last_observation"]["continuation_requests"], 1)
        self.assertFalse(route["last_observation"]["final_pagination_token_present"])
        self.assertTrue(route["last_observation"]["complete_raw_batch_candidate"])
        self.assertEqual(route["evidence"]["last_observation_receipt_sha256"], RUNTIME_SHA256)
        self.assertEqual(hashlib.sha256(RUNTIME_PATH.read_bytes()).hexdigest(), RUNTIME_SHA256)
        self.assertEqual(runtime["terminal_outcome"], "COMPLETE_RAW_BATCH_CANDIDATE")
        self.assertFalse(runtime["claims"]["pit_admissible"])
        self.assertFalse(route["non_claims"]["data_completeness"])

    def test_mutations_cannot_rewrite_history_or_promote_authority(self) -> None:
        module = importlib.import_module(MODULE_NAME)
        registry = _load_yaml(REGISTRY_PATH)
        legacy = copy.deepcopy(registry)
        legacy["routes"][0]["provider"] = "OTHER"
        with self.assertRaisesRegex(module.ProviderRouteRegistryError, "LEGACY_ROUTE_SEMANTICS_DRIFT"):
            module.validate_provider_route_capability_registry_v6(legacy)
        prior = copy.deepcopy(registry)
        prior["supersedes"]["updated_route_prior_semantic_sha256"][ROUTE_ID] = "0" * 64
        with self.assertRaisesRegex(module.ProviderRouteRegistryError, "SUPERSEDES_BINDING_DRIFT"):
            module.validate_provider_route_capability_registry_v6(prior)
        authority = copy.deepcopy(registry)
        authority["routes"][5]["execution_policy"]["authority_granted"] = True
        with self.assertRaisesRegex(module.ProviderRouteRegistryError, "HELIUS_ROUTE_DRIFT"):
            module.validate_provider_route_capability_registry_v6(authority)

    def test_registry_gap_stays_unknown_not_unavailable(self) -> None:
        module = importlib.import_module(MODULE_NAME)
        registry = _load_yaml(REGISTRY_PATH)
        with self.assertRaisesRegex(module.ProviderRouteRegistryError, "REGISTRY_GAP"):
            module.resolve_provider_route_v6(registry, "UNOBSERVED-PROVIDER-ROUTE-001")


if __name__ == "__main__":
    unittest.main()
