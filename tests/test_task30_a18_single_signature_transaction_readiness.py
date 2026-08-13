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

from solana_alpha_lab.provider_route_capability_registry_v3 import (  # noqa: E402
    ProviderRouteRegistryError,
    resolve_provider_route_v3,
    validate_provider_route_capability_registry_v3,
)
from solana_alpha_lab.task30_a18_single_signature_transaction_readiness import (  # noqa: E402
    A18Error,
    BASE_MINT,
    POOL_ADDRESS,
    QUOTE_MINT,
    REQUEST_ID,
    SIGNATURE,
    bind_get_transaction,
    classify_get_transaction_response,
)

REGISTRY_PATH = ROOT / "configs/provider_route_capability_registry_v3.yaml"
REGISTRY_SCHEMA_PATH = ROOT / "catalog/schemas/provider_route_capability_registry_v3.schema.json"
CONFIG_PATH = ROOT / "configs/task30_a18_single_signature_transaction_readiness_v1.yaml"
CONFIG_SCHEMA_PATH = ROOT / "catalog/schemas/task30_a18_single_signature_transaction_readiness.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task30/single_signature_transaction_readiness_v1.json"
ACCEPTANCE_PATH = ROOT / "docs/evidence/task30/a18_single_signature_transaction_readiness_acceptance_v1.json"
CATALOG_PATH = ROOT / "catalog/assets/core.yaml"


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


def _token_balance(account_index: int, mint: str, amount: str) -> dict[str, object]:
    return {
        "accountIndex": account_index,
        "mint": mint,
        "owner": "TraderOwner111111111111111111111111111111111111",
        "programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "uiTokenAmount": {
            "amount": amount,
            "decimals": 6 if mint == BASE_MINT else 9,
            "uiAmount": None,
            "uiAmountString": "0",
        },
    }


def _response(*, candidate: bool = True) -> bytes:
    pre_base, post_base = ("1000000", "1500000") if candidate else ("1000000", "1000000")
    pre_quote, post_quote = ("2000000000", "1900000000") if candidate else ("2000000000", "2000000000")
    body = {
        "jsonrpc": "2.0",
        "id": REQUEST_ID,
        "result": {
            "blockTime": 1786600000,
            "meta": {
                "err": None,
                "fee": 5000,
                "preBalances": [1000000000, 2000000000],
                "postBalances": [999995000, 2000000000],
                "preTokenBalances": [
                    _token_balance(1, BASE_MINT, pre_base),
                    _token_balance(2, QUOTE_MINT, pre_quote),
                ],
                "postTokenBalances": [
                    _token_balance(1, BASE_MINT, post_base),
                    _token_balance(2, QUOTE_MINT, post_quote),
                ],
                "loadedAddresses": {"readonly": [], "writable": []},
                "logMessages": ["Program success"],
            },
            "slot": 123,
            "transaction": {
                "message": {
                    "accountKeys": [POOL_ADDRESS, "TraderOwner111111111111111111111111111111111111"],
                    "instructions": [],
                    "recentBlockhash": "Blockhash111111111111111111111111111111111111",
                },
                "signatures": [SIGNATURE],
            },
            "version": 0,
        },
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


class Task30A18Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = _load_yaml(REGISTRY_PATH)
        cls.config = _load_yaml(CONFIG_PATH)
        cls.fixture = _load_json(FIXTURE_PATH)

    def test_registry_v3_preserves_v2_and_resolves_observed_standard_rpc_route(self) -> None:
        routes = validate_provider_route_capability_registry_v3(self.registry)
        self.assertEqual(len(routes), 4)
        route = resolve_provider_route_v3(self.registry, "SOLANA-STANDARD-GET-TRANSACTION-001")
        self.assertEqual(route["provider"], "SOLANA_STANDARD_RPC")
        self.assertEqual(route["operation"], "GET_TRANSACTION")
        self.assertEqual(route["last_observation"]["terminal_class"], "HTTP_SUCCESS")
        self.assertEqual(route["known_failures"][0]["fingerprint"], "GET_TRANSACTION_RESULT_KEYS_DRIFT")

    def test_registry_gap_is_not_provider_unavailability(self) -> None:
        with self.assertRaisesRegex(ProviderRouteRegistryError, "REGISTRY_GAP"):
            resolve_provider_route_v3(self.registry, "HELIUS-SOLANA-GET-TRANSACTION-001")

    def test_schema_and_config_are_closed(self) -> None:
        registry_schema = _load_json(REGISTRY_SCHEMA_PATH)
        config_schema = _load_json(CONFIG_SCHEMA_PATH)
        jsonschema.Draft202012Validator.check_schema(registry_schema)
        jsonschema.Draft202012Validator.check_schema(config_schema)
        jsonschema.validate(self.registry, registry_schema)
        jsonschema.validate(self.config, config_schema)
        self.assertIn("T30-A18_SINGLE_SIGNATURE_TRANSACTION_READINESS_V1;", self.config["owner_gate_phrase"])

    def test_request_is_exact_and_secret_free(self) -> None:
        request = bind_get_transaction(SIGNATURE)
        document = json.loads(request.body)
        self.assertEqual(request.request_id, REQUEST_ID)
        self.assertEqual(document["method"], "getTransaction")
        self.assertEqual(document["params"][0], SIGNATURE)
        self.assertEqual(document["params"][1], {"commitment": "confirmed", "encoding": "json", "maxSupportedTransactionVersion": 0})
        safe = json.dumps(request.safe_receipt(), sort_keys=True)
        self.assertNotIn("api-key", safe)
        self.assertNotIn("HELIUS", safe)

    def test_happy_path_is_trade_data_candidate_but_not_price_or_volume(self) -> None:
        result = classify_get_transaction_response(_response(), expected_signature=SIGNATURE)
        self.assertEqual(result["terminal_state"], "TRADE_DATA_CANDIDATE")
        self.assertEqual(result["token_deltas_atomic"], {BASE_MINT: 500000, QUOTE_MINT: -100000000})
        self.assertTrue(result["target_bound"])
        self.assertFalse(result["price"])
        self.assertFalse(result["volume"])
        self.assertFalse(result["numeric_netreturn"])
        self.assertFalse(result["task30_trial"])

    def test_present_transaction_without_delta_is_not_zero(self) -> None:
        result = classify_get_transaction_response(_response(candidate=False), expected_signature=SIGNATURE)
        self.assertEqual(result["terminal_state"], "TRANSACTION_PRESENT_NO_TRADE_PROJECTION")
        self.assertIsNone(result["token_deltas_atomic"])
        self.assertFalse(result["zero_volume"])

    def test_null_and_provider_error_remain_explicit(self) -> None:
        null_body = json.dumps({"jsonrpc": "2.0", "id": REQUEST_ID, "result": None}).encode()
        self.assertEqual(classify_get_transaction_response(null_body, expected_signature=SIGNATURE)["terminal_state"], "TRANSACTION_NULL_OR_UNAVAILABLE")
        error_body = json.dumps({"jsonrpc": "2.0", "id": REQUEST_ID, "error": {"code": -32000, "message": "not found"}}).encode()
        self.assertEqual(classify_get_transaction_response(error_body, expected_signature=SIGNATURE)["terminal_state"], "PROVIDER_TYPED_FAILURE")

    def test_target_signature_or_pool_mismatch_is_rejected(self) -> None:
        wrong = json.loads(_response())
        wrong["result"]["transaction"]["signatures"] = ["11111111111111111111111111111111"]
        with self.assertRaisesRegex(A18Error, "SIGNATURE_MISMATCH"):
            classify_get_transaction_response(json.dumps(wrong).encode(), expected_signature=SIGNATURE)
        wrong = json.loads(_response())
        wrong["result"]["transaction"]["message"]["accountKeys"] = ["Other111111111111111111111111111111111111111"]
        with self.assertRaisesRegex(A18Error, "TARGET_POOL_NOT_BOUND"):
            classify_get_transaction_response(json.dumps(wrong).encode(), expected_signature=SIGNATURE)

    def test_missing_or_duplicate_balance_is_ambiguous_not_zero(self) -> None:
        duplicate = json.loads(_response())
        duplicate["result"]["meta"]["preTokenBalances"].append(copy.deepcopy(duplicate["result"]["meta"]["preTokenBalances"][0]))
        with self.assertRaisesRegex(A18Error, "BALANCE_DUPLICATE"):
            classify_get_transaction_response(json.dumps(duplicate).encode(), expected_signature=SIGNATURE)
        missing = json.loads(_response())
        missing["result"]["meta"]["postTokenBalances"] = [missing["result"]["meta"]["postTokenBalances"][0]]
        result = classify_get_transaction_response(json.dumps(missing).encode(), expected_signature=SIGNATURE)
        self.assertEqual(result["terminal_state"], "TRANSACTION_PRESENT_NO_TRADE_PROJECTION")
        self.assertIsNone(result["token_deltas_atomic"])
        self.assertFalse(result["zero_volume"])

    def test_acceptance_bindings_and_catalog_ids_exist(self) -> None:
        receipt = _load_json(ACCEPTANCE_PATH)
        self.assertEqual(receipt["state_change"], "NONE")
        for binding in receipt["artifact_bindings"].values():
            path = ROOT / binding["path"]
            self.assertEqual(binding["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        catalog = _load_yaml(CATALOG_PATH)
        ids = {record["asset_id"] for record in catalog["records"]}
        self.assertTrue({
            "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-003",
            "SCHEMA-PROVIDER-ROUTE-CAPABILITY-REGISTRY-003",
            "MODULE-PROVIDER-ROUTE-CAPABILITY-REGISTRY-003",
            "CONTRACT-T30-A18-SINGLE-SIGNATURE-TRANSACTION-001",
            "CONFIG-T30-A18-SINGLE-SIGNATURE-TRANSACTION-001",
            "SCHEMA-T30-A18-SINGLE-SIGNATURE-TRANSACTION-001",
            "FIXTURE-T30-A18-SINGLE-SIGNATURE-TRANSACTION-001",
            "MODULE-T30-A18-SINGLE-SIGNATURE-TRANSACTION-001",
            "TEST-T30-A18-SINGLE-SIGNATURE-TRANSACTION-001",
            "EVIDENCE-T30-A18-SINGLE-SIGNATURE-TRANSACTION-001",
            "TEST-CATALOG-SEARCH-001",
        }.issubset(ids))


if __name__ == "__main__":
    unittest.main()
