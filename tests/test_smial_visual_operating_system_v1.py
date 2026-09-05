from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory_semantic_operability import (  # noqa: E402
    load_semantic_catalog_views,
    load_semantic_projection,
    resolve_semantic_route,
    search_semantic_routes,
    validate_semantic_projection,
)
from validate_catalog import load_and_validate  # noqa: E402

CONTRACT = ROOT / "configs/smial_visual_operating_system_v1.yaml"
SCHEMA = ROOT / "catalog/schemas/smial_visual_operating_system.schema.json"
HUMAN = ROOT / "docs/contracts/smial_visual_operating_system_v1.md"
OUT_OF_SCOPE_PRODUCT = (
    ROOT / "src/solana_alpha_lab/factory/workbench.py",
    ROOT / "src/solana_alpha_lab/factory/cockpit.py",
)
def _rel_luminance(hex_color: str) -> float:
    raw = hex_color.removeprefix("#")
    channels = [int(raw[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linearized = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linearized[0] + 0.7152 * linearized[1] + 0.0722 * linearized[2]


def _contrast(fg: str, bg: str) -> float:
    lighter, darker = sorted((_rel_luminance(fg), _rel_luminance(bg)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


class SmialVisualOperatingSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        cls.snapshot = load_and_validate(allow_generated_drift=True)
        cls.projection = load_semantic_projection(ROOT)
        cls.assets, cls.bindings, cls.queries = load_semantic_catalog_views(ROOT)

    def test_machine_contract_validates(self) -> None:
        Draft202012Validator(self.schema).validate(self.contract)
        self.assertIs(self.contract["authority_granted"], False)
        self.assertEqual(self.contract["appearance"], "DARK_ONLY")
        self.assertEqual(self.contract["identity"]["base"], "STEEL_SIGNAL")
        self.assertFalse(self.contract["identity"]["selectable_themes"])
        self.assertFalse(self.contract["identity"]["light_theme"])
        self.assertFalse(self.contract["state_invariants"]["owns_domain_states"])
        self.assertTrue(self.contract["state_invariants"]["unknown_is_not_zero"])
        self.assertTrue(self.contract["state_invariants"]["evidence_class_never_color_only"])
        unknown = self.contract["semantic_color_roles"]["semantic.unknown"]
        self.assertIn("zero", unknown["must_not_resemble"])
        self.assertIn("healthy", unknown["must_not_resemble"])
        labels = self.contract["state_invariants"]["evidence_class_labels_required"]
        self.assertEqual(labels, ["MODEL", "BACKTEST", "PAPER", "SHADOW", "LIVE"])

    def test_human_companion_exists_and_names_one_system(self) -> None:
        text = HUMAN.read_text(encoding="utf-8")
        self.assertIn("STEEL SIGNAL", text)
        self.assertIn("COMPUTATIONAL FIELD", text)
        self.assertIn("EVIDENCE EDITORIAL", text)
        self.assertIn("CONTROL SURFACE", text)
        self.assertIn("DARK_ONLY", text)
        self.assertIn("authority_granted = false", text)
        self.assertIn("UNKNOWN", text)
        self.assertNotIn("four selectable themes", text.casefold())

    def test_primary_text_meets_wcag_aa_on_surfaces(self) -> None:
        palette = self.contract["palette"]
        primary = palette["text"]["primary"]
        secondary = palette["text"]["secondary"]
        for surface in palette["surface"].values():
            self.assertGreaterEqual(_contrast(primary, surface), 4.5)
            self.assertGreaterEqual(_contrast(secondary, surface), 4.5)
        unknown = palette["semantic"]["unknown"]
        positive = palette["semantic"]["positive"]
        self.assertGreaterEqual(_contrast(unknown, palette["surface"]["base"]), 3.0)
        self.assertNotEqual(unknown.casefold(), positive.casefold())
        self.assertNotEqual(unknown.casefold(), palette["text"]["primary"].casefold())

    def test_catalog_binding_and_assets_resolve(self) -> None:
        binding = self.bindings["ACTIVE-SMIAL-VISUAL-OPERATING-SYSTEM"]
        self.assertEqual(
            binding["target_asset_id"],
            "CONFIG-SMIAL-VISUAL-OPERATING-SYSTEM-001",
        )
        self.assertIn("CONFIG-SMIAL-VISUAL-OPERATING-SYSTEM-001", self.snapshot.assets)
        self.assertIn("DOC-SMIAL-VISUAL-OPERATING-SYSTEM-001", self.snapshot.assets)
        self.assertIn("SCHEMA-SMIAL-VISUAL-OPERATING-SYSTEM-001", self.snapshot.assets)
        config = self.snapshot.assets["CONFIG-SMIAL-VISUAL-OPERATING-SYSTEM-001"]
        self.assertEqual(
            (config.get("location") or {}).get("repository_path"),
            "configs/smial_visual_operating_system_v1.yaml",
        )

    def test_semantic_route_resolves_without_authority(self) -> None:
        errors = validate_semantic_projection(
            self.projection,
            assets=self.snapshot.assets,
            bindings=self.bindings,
            queries=self.snapshot.queries,
        )
        self.assertEqual(errors, [])
        payload = resolve_semantic_route(
            self.projection,
            "SEM-VISUAL-OPERATING-SYSTEM",
            assets=self.snapshot.assets,
            bindings=self.bindings,
        )
        self.assertIs(payload["authority_granted"], False)
        targets = [item["target_asset_id"] for item in payload["root_bindings"]]
        self.assertIn("CONFIG-SMIAL-VISUAL-OPERATING-SYSTEM-001", targets)
        asset_ids = [item["asset_id"] for item in payload["root_assets"]]
        self.assertIn("DOC-SMIAL-VISUAL-OPERATING-SYSTEM-001", asset_ids)
        self.assertEqual(payload["status_plane"], "CAPABILITY")

    def test_visual_queries_rank_visual_route(self) -> None:
        queries = (
            "How should I design an SMIAL owner-facing surface?",
            "What visual system does SMIAL use?",
            "How should Workbench UI look?",
            "what colors mean warning danger unknown",
            "How should I style an experiment or evidence screen?",
            "style the owner-facing operations surface",
            "How should Telegram service messages look?",
            "какой брендбук / визуальный стиль проекта",
            "как оформлять интерфейс SMIAL",
            "smial brandbook",
        )
        for query in queries:
            with self.subTest(query=query):
                hits = search_semantic_routes(
                    self.projection,
                    query,
                    assets=self.snapshot.assets,
                    bindings=self.bindings,
                    limit=5,
                )
                assert isinstance(hits, list)
                self.assertTrue(hits, msg=query)
                self.assertEqual(hits[0]["semantic_route_id"], "SEM-VISUAL-OPERATING-SYSTEM")
                self.assertIs(hits[0]["authority_granted"], False)

    def test_domain_questions_are_not_hijacked(self) -> None:
        cases = (
            "What positions are open?",
            "What is the current risk state?",
            "Is runtime healthy?",
            "What is current PnL?",
        )
        for query in cases:
            with self.subTest(query=query):
                hits = search_semantic_routes(
                    self.projection,
                    query,
                    assets=self.snapshot.assets,
                    bindings=self.bindings,
                    limit=5,
                )
                assert isinstance(hits, list)
                if hits:
                    self.assertNotEqual(
                        hits[0]["semantic_route_id"],
                        "SEM-VISUAL-OPERATING-SYSTEM",
                        msg=query,
                    )

    def test_no_new_ui_dependency_and_product_ui_untouched_in_contract(self) -> None:
        blob = " ".join(
            [
                CONTRACT.read_text(encoding="utf-8").casefold(),
                HUMAN.read_text(encoding="utf-8").casefold(),
                SCHEMA.read_text(encoding="utf-8").casefold(),
            ]
        )
        leaked = tuple(
            token
            for token in (
                "react",
                "vue",
                "svelte",
                "tailwindcss",
                "chart.js",
                "chartjs",
            )
            if token in blob
        )
        self.assertEqual(leaked, ())
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").casefold()
        for token in ("react", "tailwindcss", "svelte", "vue"):
            self.assertNotIn(token, pyproject)
        for path in OUT_OF_SCOPE_PRODUCT:
            self.assertTrue(path.is_file())
        lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
        self.assertNotIn("tailwind", lock.casefold())


if __name__ == "__main__":
    unittest.main()
