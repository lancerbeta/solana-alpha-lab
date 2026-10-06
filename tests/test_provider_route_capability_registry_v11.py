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

from solana_alpha_lab.provider_route_capability_registry_v11 import (  # noqa: E402
    CATEGORY_ROUTE_SPECS,
    LIMITS_PATH,
    LIMITS_SHA256,
    RECEIPT_PATH,
    RECEIPT_SHA256,
    SEARCH_ROUTE_ID,
    V10_SHA256,
    resolve_provider_route_v11,
    validate_provider_route_capability_registry_v11,
)


V10_PATH = ROOT / "configs/provider_route_capability_registry_v10.yaml"
V11_PATH = ROOT / "configs/provider_route_capability_registry_v11.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/provider_route_capability_registry_v11.schema.json"


class ProviderRouteRegistryV11Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.v10 = yaml.safe_load(V10_PATH.read_text(encoding="utf-8"))
        self.v11 = yaml.safe_load(V11_PATH.read_text(encoding="utf-8"))
        self.v10_sha = hashlib.sha256(V10_PATH.read_bytes()).hexdigest()

    def _validate(self, registry: dict[str, object]) -> tuple[object, ...]:
        return validate_provider_route_capability_registry_v11(
            registry,
            predecessor=self.v10,
            predecessor_sha256=self.v10_sha,
        )

    def test_v10_bytes_are_the_append_only_predecessor(self) -> None:
        self.assertEqual(self.v10_sha, V10_SHA256)

    def test_schema_validates_and_twelve_routes_are_preserved_byte_semantically(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(self.v11)
        routes = self._validate(self.v11)

        self.assertEqual(list(routes[:12]), self.v10["routes"][:12])
        self.assertEqual(len(routes), 16)

    def test_committed_evidence_bytes_match_registry_pins(self) -> None:
        receipt = (ROOT / RECEIPT_PATH).read_bytes()
        limits = (ROOT / LIMITS_PATH).read_bytes()

        self.assertEqual(hashlib.sha256(receipt).hexdigest(), RECEIPT_SHA256)
        self.assertEqual(hashlib.sha256(limits).hexdigest(), LIMITS_SHA256)
        parsed = json.loads(limits)
        self.assertEqual(parsed["applies_to_receipt_sha256"], RECEIPT_SHA256)
        self.assertEqual(parsed["account_pace_discipline"], "UNPROVEN_FAILED_OVERLAP_WITH_LEGACY")
        self.assertEqual(parsed["provider_calls_authorized_by_this_record"], 0)
        self.assertIs(parsed["authority_granted"], False)

    def test_each_route_mirrors_exactly_one_receipt_call(self) -> None:
        receipt = json.loads((ROOT / RECEIPT_PATH).read_text(encoding="utf-8"))
        calls = {item["endpoint_family"]: item for item in receipt["receipts"]}
        routes = {route["route_id"]: route for route in self._validate(self.v11)}
        expected = {SEARCH_ROUTE_ID: "tokens/v2/search"}
        expected.update({route_id: endpoint for route_id, endpoint, _operation in CATEGORY_ROUTE_SPECS})

        self.assertEqual(set(expected.values()), set(calls))
        for route_id, endpoint in expected.items():
            call = calls[endpoint]
            observed = routes[route_id]["last_success"]
            self.assertEqual(routes[route_id]["endpoint_family"], endpoint)
            self.assertEqual(observed["response_sha256"], call["response_canonical_sha256"])
            self.assertEqual(observed["response_bytes"], call["response_canonical_bytes"])
            self.assertEqual(observed["rows"], call["rows"])
            self.assertEqual(observed["observed_at"], call["response_received_at"])
            self.assertEqual(observed["http_status"], call["http_status"])

    def test_search_route_only_claims_the_single_object_shape(self) -> None:
        search = resolve_provider_route_v11(
            self.v11,
            SEARCH_ROUTE_ID,
            predecessor=self.v10,
            predecessor_sha256=self.v10_sha,
        )

        self.assertEqual(search["evidence"]["search_shape_coverage"], "SINGLE_OBJECT_USDC_PUBLIC_MINT_ONLY")
        self.assertEqual(search["last_success"]["rows"], 1)
        self.assertIsNot(search["execution_policy"]["authority_granted"], True)

    def test_resolver_does_not_return_a_different_route(self) -> None:
        with self.assertRaisesRegex(Exception, "REGISTRY_GAP"):
            resolve_provider_route_v11(
                self.v11,
                "JUPITER-SOLANA-TOKENS-V2-TOPTRADED-5M-FREE-API-KEY-999",
                predecessor=self.v10,
                predecessor_sha256=self.v10_sha,
            )

    def test_overlap_failure_cannot_be_dropped_or_upgraded(self) -> None:
        for mutation in ("PROVEN", None):
            tampered = copy.deepcopy(self.v11)
            if mutation is None:
                del tampered["routes"][13]["evidence"]["account_pace_discipline"]
            else:
                tampered["routes"][13]["evidence"]["account_pace_discipline"] = mutation
            with self.assertRaisesRegex(Exception, "OBSERVED_PACE_CLAIM_DRIFT"):
                self._validate(tampered)

    def test_tampering_fails_closed(self) -> None:
        cases = (
            ("PRESERVED_ROUTE_DRIFT", lambda r: r["routes"][0].__setitem__("provider", "OTHER")),
            ("TRANSITIONED_HASH_DRIFT", lambda r: r["supersedes"]["transitioned_route_semantic_sha256"].update({SEARCH_ROUTE_ID: "0" * 64})),
            ("OBSERVED_AUTHORITY_DRIFT", lambda r: r["routes"][14]["execution_policy"].__setitem__("authority_granted", True)),
            ("OBSERVED_RECEIPT_SHA_DRIFT", lambda r: r["routes"][15]["evidence"].__setitem__("last_observation_receipt_sha256", "1" * 64)),
            ("SEARCH_SHAPE_CLAIM_DRIFT", lambda r: r["routes"][12]["evidence"].__setitem__("search_shape_coverage", "BATCH100")),
            ("ROUTE_COUNT_DRIFT", lambda r: r["routes"].pop()),
        )
        for code, mutate in cases:
            tampered = copy.deepcopy(self.v11)
            mutate(tampered)
            with self.subTest(code=code), self.assertRaisesRegex(Exception, code):
                self._validate(tampered)


if __name__ == "__main__":
    unittest.main()
