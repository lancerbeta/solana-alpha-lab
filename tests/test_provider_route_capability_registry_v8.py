from __future__ import annotations

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

from solana_alpha_lab.provider_route_capability_registry_v7 import V6_SHA256  # noqa: E402
from solana_alpha_lab.provider_route_capability_registry_v8 import (  # noqa: E402
    RECENT_ROUTE_ID,
    RUNTIME_RECEIPT_SHA256,
    TRADED_ROUTE_ID,
    V7_SHA256,
    resolve_provider_route_v8,
    validate_provider_route_capability_registry_v8,
)


V6_PATH = ROOT / "configs/provider_route_capability_registry_v6.yaml"
V7_PATH = ROOT / "configs/provider_route_capability_registry_v7.yaml"
V8_PATH = ROOT / "configs/provider_route_capability_registry_v8.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/provider_route_capability_registry_v8.schema.json"
RECEIPT_PATH = (
    ROOT
    / "docs/evidence/quote_native_live_variation_campaign"
    / "a1_quote_native_live_variation_campaign_runtime_receipt_v1.json"
)


class ProviderRouteRegistryV8Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.v6 = yaml.safe_load(V6_PATH.read_text(encoding="utf-8"))
        self.v7 = yaml.safe_load(V7_PATH.read_text(encoding="utf-8"))
        self.v8 = yaml.safe_load(V8_PATH.read_text(encoding="utf-8"))
        self.v6_sha = hashlib.sha256(V6_PATH.read_bytes()).hexdigest()
        self.v7_sha = hashlib.sha256(V7_PATH.read_bytes()).hexdigest()

    def test_v7_bytes_unchanged(self) -> None:
        self.assertEqual(self.v6_sha, V6_SHA256)
        self.assertEqual(self.v7_sha, V7_SHA256)

    def test_schema_and_token_routes(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(self.v8)
        routes = validate_provider_route_capability_registry_v8(
            self.v8,
            predecessor=self.v7,
            predecessor_sha256=self.v7_sha,
            v6_registry=self.v6,
            v6_sha256=self.v6_sha,
        )
        self.assertEqual(len(routes), 9)
        recent = resolve_provider_route_v8(
            self.v8,
            RECENT_ROUTE_ID,
            predecessor=self.v7,
            predecessor_sha256=self.v7_sha,
            v6_registry=self.v6,
            v6_sha256=self.v6_sha,
        )
        traded = resolve_provider_route_v8(
            self.v8,
            TRADED_ROUTE_ID,
            predecessor=self.v7,
            predecessor_sha256=self.v7_sha,
            v6_registry=self.v6,
            v6_sha256=self.v6_sha,
        )
        self.assertEqual(recent["last_observation"]["terminal_class"], "TOKEN_LIST_OBSERVED")
        self.assertEqual(traded["last_observation"]["terminal_class"], "TOKEN_LIST_OBSERVED")
        receipt_sha = hashlib.sha256(RECEIPT_PATH.read_bytes()).hexdigest()
        self.assertEqual(receipt_sha, RUNTIME_RECEIPT_SHA256)
        self.assertEqual(recent["evidence"]["last_observation_receipt_sha256"], receipt_sha)
        self.assertEqual(traded["evidence"]["last_observation_receipt_sha256"], receipt_sha)


if __name__ == "__main__":
    unittest.main()
