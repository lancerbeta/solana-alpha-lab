from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/generate_navigation.py"
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
spec = importlib.util.spec_from_file_location("generate_navigation", MODULE_PATH)
assert spec and spec.loader
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


def asset(asset_id: str, relations: list[dict[str, str]]) -> dict:
    return {
        "asset_id": asset_id,
        "asset_type": "architecture_intent" if asset_id == "ARCH-INTENT-001" else "script",
        "status": (
            "ACCEPTED_DIRECTION_NOT_IMPLEMENTED"
            if asset_id == "ARCH-INTENT-001"
            else "IMPLEMENTED_UNVERIFIED"
        ),
        "purpose": f"Synthetic navigation fixture for {asset_id}.",
        "location": {"logical_uri": f"repo://fixtures/{asset_id}"},
        "relations": relations,
        "integrity": {"kind": "sha256", "sha256": "0" * 64},
        "evidence": [{"reference": "SYNTHETIC-EVIDENCE-MARKER"}],
    }


class GenerateNavigationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = SimpleNamespace(
            manifest={"catalog_id": "SMIAL-PROJECT-ASSET-CATALOG"},
            assets={
                "ARCH-INTENT-001": asset(
                    "ARCH-INTENT-001",
                    [{"relation_type": "advises", "target_asset_id": "TARGET-001"}],
                ),
                "TARGET-001": asset("TARGET-001", []),
            },
        )

    def test_write_is_deterministic_and_idempotent(self) -> None:
        outputs = generator.expected_outputs(self.snapshot)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertTrue(generator.write_outputs(root, outputs))
            first = {path: (root / path).read_bytes() for path in outputs}
            self.assertFalse(generator.write_outputs(root, outputs))
            second = {path: (root / path).read_bytes() for path in outputs}
            self.assertEqual(first, second)

    def test_check_passes_fresh_and_fails_on_drift(self) -> None:
        outputs = generator.expected_outputs(self.snapshot)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            generator.write_outputs(root, outputs)
            self.assertEqual(generator.check_outputs(root, outputs), [])
            (root / generator.PROJECT_MAP_PATH).write_bytes(b"drift\n")
            self.assertEqual(
                generator.check_outputs(root, outputs),
                [generator.PROJECT_MAP_PATH],
            )

    def test_project_map_contains_architecture_intent_without_evidence(self) -> None:
        rendered = generator.render_project_map(self.snapshot).decode("utf-8")
        self.assertIn("ARCH-INTENT-001", rendered)
        self.assertIn("ACCEPTED_DIRECTION_NOT_IMPLEMENTED", rendered)
        self.assertNotIn('"sha256"', rendered)
        self.assertNotIn("SYNTHETIC-EVIDENCE-MARKER", rendered)

    def test_edges_reference_only_known_catalog_ids(self) -> None:
        payload = json.loads(generator.render_edge_projection(self.snapshot))
        known_ids = set(self.snapshot.assets)
        for edge in payload["edges"]:
            self.assertIn(edge["source_asset_id"], known_ids)
            self.assertIn(edge["target_asset_id"], known_ids)


if __name__ == "__main__":
    unittest.main()
