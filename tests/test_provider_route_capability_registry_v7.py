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

from solana_alpha_lab.provider_route_capability_registry_v7 import (  # noqa: E402
    JUPITER_ROUTE_ID,
    V6_SHA256,
    resolve_provider_route_v7,
    validate_provider_route_capability_registry_v7,
)


V6_PATH = ROOT / "configs/provider_route_capability_registry_v6.yaml"
V7_PATH = ROOT / "configs/provider_route_capability_registry_v7.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/provider_route_capability_registry_v7.schema.json"
RECEIPT_PATH = ROOT / "docs/evidence/pmf_quote_slice/a1_pmf_quote_slice_one_shot_runtime_receipt_v1.json"


class ProviderRouteRegistryV7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.v6 = yaml.safe_load(V6_PATH.read_text(encoding="utf-8"))
        self.v7 = yaml.safe_load(V7_PATH.read_text(encoding="utf-8"))
        self.v6_sha = hashlib.sha256(V6_PATH.read_bytes()).hexdigest()

    def test_v6_bytes_unchanged(self) -> None:
        self.assertEqual(self.v6_sha, V6_SHA256)

    def test_schema_and_jupiter_route(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(self.v7)
        routes = validate_provider_route_capability_registry_v7(
            self.v7, predecessor=self.v6, predecessor_sha256=self.v6_sha
        )
        self.assertEqual(len(routes), 7)
        jupiter = resolve_provider_route_v7(
            self.v7,
            JUPITER_ROUTE_ID,
            predecessor=self.v6,
            predecessor_sha256=self.v6_sha,
        )
        self.assertEqual(jupiter["last_observation"]["terminal_class"], "QUOTE_OBSERVED")
        receipt_sha = hashlib.sha256(RECEIPT_PATH.read_bytes()).hexdigest()
        self.assertEqual(
            jupiter["evidence"]["last_observation_receipt_sha256"],
            receipt_sha,
        )


if __name__ == "__main__":
    unittest.main()
