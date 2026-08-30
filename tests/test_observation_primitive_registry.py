from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_primitive_registry import (  # noqa: E402
    PrimitiveRegistryError,
    load_observation_primitive_registry,
)


class ObservationPrimitiveRegistryTests(unittest.TestCase):
    def test_accepted_jupiter_primitives_load(self) -> None:
        registry = load_observation_primitive_registry(ROOT)
        for primitive_id in (
            "PRIM-JUPITER-TOKENS-V2-RECENT-001",
            "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
            "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-001",
            "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-001",
            "PRIM-JUPITER-SWAP-V2-QUOTE-BUY-1M-001",
            "PRIM-JUPITER-SWAP-V2-DEPENDENT-REVERSE-SELL-1M-001",
        ):
            primitive = registry.require_primitive(primitive_id)
            self.assertEqual(primitive["status"], "ACCEPTED")
            self.assertIs(primitive["retry"], False)
            self.assertIs(primitive["fallback"], False)
        self.assertEqual(
            registry.require_field("FIELD-QUOTE-SELL-OUT-AMOUNT-001")["availability_class"],
            "Y_TIME",
        )

    def test_unknown_field_and_bundle_are_primitive_gaps(self) -> None:
        registry = load_observation_primitive_registry(ROOT)
        with self.assertRaisesRegex(PrimitiveRegistryError, "CHANGE_LANE_PRIMITIVE_GAP"):
            registry.require_field("FIELD-DOES-NOT-EXIST-001")
        with self.assertRaisesRegex(PrimitiveRegistryError, "CHANGE_LANE_PRIMITIVE_GAP"):
            registry.require_bundle("BUNDLE-DOES-NOT-EXIST-001")
        with self.assertRaisesRegex(PrimitiveRegistryError, "CHANGE_LANE_PRIMITIVE_GAP"):
            registry.require_parser("MODULE-UNKNOWN-PARSER-001")

    def test_unknown_authority_is_blocked(self) -> None:
        registry = load_observation_primitive_registry(ROOT)
        with self.assertRaisesRegex(PrimitiveRegistryError, "BLOCKED_AUTHORITY"):
            registry.require_authority_profile("AUTH-DOES-NOT-EXIST-001")

    def test_retry_or_fallback_in_registry_is_rejected(self) -> None:
        source = yaml.safe_load(
            (ROOT / "configs/observation_primitive_registry_v1.yaml").read_text(
                encoding="utf-8"
            )
        )
        source["primitives"][0]["retry"] = True
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp)
            (fake / "configs").mkdir()
            (fake / "catalog/schemas").mkdir(parents=True)
            (fake / "configs/observation_primitive_registry_v1.yaml").write_text(
                yaml.safe_dump(source),
                encoding="utf-8",
            )
            for name in (
                "observation_primitive_registry_v1.schema.json",
                "observation_primitive_descriptor_v1.schema.json",
            ):
                (fake / "catalog/schemas" / name).write_bytes(
                    (ROOT / "catalog/schemas" / name).read_bytes()
                )
            with self.assertRaisesRegex(
                PrimitiveRegistryError, "PRIMITIVE_RETRY_OR_FALLBACK_FORBIDDEN"
            ):
                load_observation_primitive_registry(fake)


if __name__ == "__main__":
    unittest.main()
