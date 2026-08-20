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

from solana_alpha_lab.provider_route_capability_registry_v10 import (  # noqa: E402
    SEARCH_ROUTE_ID,
    V9_SHA256,
    resolve_provider_route_v10,
    validate_provider_route_capability_registry_v10,
)


V9_PATH = ROOT / "configs/provider_route_capability_registry_v9.yaml"
V10_PATH = ROOT / "configs/provider_route_capability_registry_v10.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/provider_route_capability_registry_v10.schema.json"


class ProviderRouteRegistryV10Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.v9 = yaml.safe_load(V9_PATH.read_text(encoding="utf-8"))
        self.v10 = yaml.safe_load(V10_PATH.read_text(encoding="utf-8"))
        self.v9_sha = hashlib.sha256(V9_PATH.read_bytes()).hexdigest()

    def _validate(self, registry: dict[str, object]) -> tuple[object, ...]:
        return validate_provider_route_capability_registry_v10(
            registry,
            predecessor=self.v9,
            predecessor_sha256=self.v9_sha,
        )

    def test_v9_bytes_are_the_append_only_predecessor(self) -> None:
        self.assertEqual(self.v9_sha, V9_SHA256)

    def test_search_route_is_named_but_not_claimed_observed_before_capture(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(self.v10)
        routes = self._validate(self.v10)

        self.assertEqual(list(routes[:12]), self.v9["routes"])
        search = routes[12]
        self.assertEqual(search["route_id"], SEARCH_ROUTE_ID)
        self.assertEqual(search["endpoint_family"], "tokens/v2/search")
        self.assertEqual(search["runtime"]["observed_result"], "AUTHORIZED_UNOBSERVED")
        self.assertIsNone(search["last_success"])
        self.assertIsNone(search["last_observation"])
        self.assertEqual(search["evidence"]["raw_retention"], "PENDING_FIRST_OBSERVATION")

    def test_resolver_does_not_return_a_different_route(self) -> None:
        route = resolve_provider_route_v10(
            self.v10,
            SEARCH_ROUTE_ID,
            predecessor=self.v9,
            predecessor_sha256=self.v9_sha,
        )

        self.assertEqual(route["route_id"], SEARCH_ROUTE_ID)
        with self.assertRaisesRegex(Exception, "REGISTRY_GAP"):
            resolve_provider_route_v10(
                self.v10,
                "JUPITER-SOLANA-TOKENS-V2-SEARCH-FREE-API-KEY-999",
                predecessor=self.v9,
                predecessor_sha256=self.v9_sha,
            )

    def test_tampering_with_preserved_v9_route_fails_closed(self) -> None:
        tampered = copy.deepcopy(self.v10)
        tampered["routes"][0]["provider"] = "OTHER"

        with self.assertRaisesRegex(Exception, "PRESERVED_ROUTE_DRIFT"):
            self._validate(tampered)


if __name__ == "__main__":
    unittest.main()
