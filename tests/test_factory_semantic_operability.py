from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory_semantic_operability import (  # noqa: E402
    MAX_FORGE_SEMANTIC_BYTES,
    build_forge_semantic_capability_projection,
    list_semantic_routes,
    load_semantic_catalog_views,
    load_semantic_projection,
    resolve_semantic_route,
    search_semantic_routes,
    semantic_capability_digest_sha256,
    validate_semantic_projection,
)
from validate_catalog import load_and_validate  # noqa: E402

GOLD_PATH = ROOT / "catalog/fixtures/semantic_route_gold_queries_v1.yaml"
FORBIDDEN_PREFIXES = (
    "docs/tasks/",
    "docs/evidence/",
    "docs/reports/",
    "docs/project_sources/",
)


class FactorySemanticOperabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = load_and_validate(allow_generated_drift=True)
        cls.projection = load_semantic_projection(ROOT)
        cls.bindings = cls.snapshot.manifest.get("canonical_bindings") or {}

    def test_schema_and_reference_integrity(self) -> None:
        errors = validate_semantic_projection(
            self.projection,
            assets=self.snapshot.assets,
            bindings=self.bindings,
            queries=self.snapshot.queries,
        )
        self.assertEqual(errors, [])
        self.assertIs(self.projection["authority_granted"], False)
        route_ids = [
            route["semantic_route_id"] for route in self.projection["routes"]
        ]
        self.assertEqual(len(route_ids), len(set(route_ids)))
        self.assertGreaterEqual(len(route_ids), 10)
        self.assertLessEqual(len(route_ids), 12)
        self.assertLessEqual(len(self.bindings), 10)

    def test_current_roots_avoid_stale_planes(self) -> None:
        for route in self.projection["routes"]:
            for binding_id in route.get("root_binding_ids") or []:
                target = self.bindings[binding_id]["target_asset_id"]
                path = (
                    self.snapshot.assets[target].get("location") or {}
                ).get("repository_path") or ""
                self.assertFalse(
                    any(path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES),
                    msg=f"{route['semantic_route_id']} -> {path}",
                )
                self.assertNotEqual(
                    self.snapshot.assets[target].get("asset_type"),
                    "architecture_intent",
                )
        product = resolve_semantic_route(
            self.projection,
            "SEM-PRODUCT-STATE",
            assets=self.snapshot.assets,
            bindings=self.bindings,
        )
        targets = [
            item["target_asset_id"] for item in product["root_bindings"]
        ]
        self.assertIn("CONFIG-FACTORY-V1-OPERATIONAL-READINESS-001", targets)
        self.assertNotIn(
            "CONFIG-FACTORY-V1-OPERATIONAL-READINESS-CLOSEOUT-001", targets
        )
        closeout = self.snapshot.assets[
            "CONFIG-FACTORY-V1-OPERATIONAL-READINESS-CLOSEOUT-001"
        ]
        # Closeout remains discoverable history, but must not be the current binding target.
        self.assertNotEqual(
            self.bindings["ACTIVE-FACTORY-OPERATIONAL-READINESS"]["target_asset_id"],
            "CONFIG-FACTORY-V1-OPERATIONAL-READINESS-CLOSEOUT-001",
        )
        self.assertIn("closeout", str(closeout.get("purpose") or "").casefold())

    def test_gold_semantic_questions(self) -> None:
        fixture = yaml.safe_load(GOLD_PATH.read_text(encoding="utf-8"))
        for row in fixture["queries"]:
            with self.subTest(query_id=row["query_id"]):
                hits = search_semantic_routes(
                    self.projection,
                    row["query"],
                    assets=self.snapshot.assets,
                    bindings=self.bindings,
                    limit=5,
                )
                assert isinstance(hits, list)
                self.assertTrue(hits, msg=row["query"])
                self.assertEqual(
                    hits[0]["semantic_route_id"],
                    row["required_top_route"],
                    msg=row["query"],
                )
                self.assertIs(hits[0]["authority_granted"], False)

    def test_no_archaeology_and_size_bounds(self) -> None:
        overview = json.dumps(
            [
                resolve_semantic_route(
                    self.projection,
                    route["semantic_route_id"],
                    assets=self.snapshot.assets,
                    bindings=self.bindings,
                )
                for route in self.projection["routes"]
            ],
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
        self.assertLessEqual(len(overview), 16 * 1024)
        for route in self.projection["routes"]:
            payload = resolve_semantic_route(
                self.projection,
                route["semantic_route_id"],
                assets=self.snapshot.assets,
                bindings=self.bindings,
            )
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode(
                "utf-8"
            )
            self.assertLessEqual(len(encoded), 8 * 1024)
            text = encoded.decode("utf-8").casefold()
            self.assertNotIn("currently active", text)
            self.assertNotIn("current activation sha", text)
            self.assertNotIn("current backup age", text)
            self.assertIs(payload["authority_granted"], False)

    def test_missing_historical_roadmap_not_current_dependency(self) -> None:
        blob = json.dumps(self.projection, ensure_ascii=False).casefold()
        self.assertNotIn(
            "prd_ssd_forge_evidence_planes_vps_discovery_roadmap_v2", blob
        )
        self.assertFalse(
            (
                ROOT
                / "docs/tasks/PRD_SSD_FORGE_EVIDENCE_PLANES_VPS_DISCOVERY_ROADMAP_V2.md"
            ).exists()
        )

    def test_forge_semantic_context_and_digest_stability(self) -> None:
        slice_payload = build_forge_semantic_capability_projection(
            self.projection,
            assets=self.snapshot.assets,
            bindings=self.bindings,
        )
        self.assertLessEqual(len(slice_payload["semantic_capability_entries"]), 6)
        self.assertIs(slice_payload["authority_granted"], False)
        encoded = json.dumps(
            slice_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        self.assertLessEqual(len(encoded), MAX_FORGE_SEMANTIC_BYTES)
        digest_a = semantic_capability_digest_sha256(
            self.projection,
            assets=self.snapshot.assets,
            bindings=self.bindings,
        )
        include_routes = [
            route
            for route in self.projection["routes"]
            if route.get("forge_visibility") == "INCLUDE"
        ]
        self.assertTrue(include_routes)
        mutated = copy.deepcopy(self.projection)
        include_id = str(include_routes[0]["semantic_route_id"])
        for route in mutated["routes"]:
            if str(route.get("semantic_route_id")) != include_id:
                continue
            route["purpose"] = str(route.get("purpose") or "") + " wording"
            route["search_terms"] = list(route.get("search_terms") or []) + [
                "alias-only"
            ]
            route["owner_questions"] = list(route.get("owner_questions") or []) + [
                "wording-only question"
            ]
            break
        digest_b = semantic_capability_digest_sha256(
            mutated,
            assets=self.snapshot.assets,
            bindings=self.bindings,
        )
        self.assertEqual(digest_a, digest_b)
        assets_mut = copy.deepcopy(self.snapshot.assets)
        target = self.bindings["ACTIVE-EXPERIMENT-CAPABILITY-REGISTRY"][
            "target_asset_id"
        ]
        assets_mut[target]["integrity"] = {
            "kind": "sha256",
            "sha256": "ab" * 32,
        }
        digest_c = semantic_capability_digest_sha256(
            self.projection,
            assets=assets_mut,
            bindings=self.bindings,
        )
        self.assertNotEqual(digest_a, digest_c)

    def test_provider_route_does_not_grant_authority(self) -> None:
        payload = resolve_semantic_route(
            self.projection,
            "SEM-PROVIDER-ROUTES",
            assets=self.snapshot.assets,
            bindings=self.bindings,
        )
        self.assertEqual(
            payload.get("authority_boundary"),
            "ROUTE_EXISTS != CALL_AUTHORIZED",
        )
        self.assertIs(payload["authority_granted"], False)

    def test_catalog_views_match_validated_snapshot(self) -> None:
        assets, bindings, queries = load_semantic_catalog_views(ROOT)
        self.assertIn("CONFIG-FACTORY-SEMANTIC-OPERABILITY-001", assets)
        self.assertEqual(
            bindings["ACTIVE-FACTORY-SEMANTIC-OPERABILITY"]["target_asset_id"],
            "CONFIG-FACTORY-SEMANTIC-OPERABILITY-001",
        )
        self.assertIn("QUERY-HFIC-EXACT-RELATED-PRIOR-001", queries)

    def test_evidence_epoch_and_forge_slice_wire_semantic_digest(self) -> None:
        from solana_alpha_lab.factory.hfic_preflight import (
            MAX_PACKET_BYTES,
            build_forge_context_packet,
            evidence_epoch_material,
        )
        from solana_alpha_lab.factory.hfic_session import (
            _MATERIAL_EPOCH_KEYS,
            evidence_epoch_sha256,
        )
        from solana_alpha_lab.factory.research_store import ResearchStore
        from solana_alpha_lab.factory.run_passport import canonical_json_bytes
        from solana_alpha_lab.factory_semantic_operability import (
            forge_semantic_slice_for_repo,
        )

        self.assertIn("semantic_capability_digest_sha256", _MATERIAL_EPOCH_KEYS)
        material = evidence_epoch_material(ROOT)
        digest = material["semantic_capability_digest_sha256"]
        self.assertEqual(len(digest), 64)
        epoch_a = evidence_epoch_sha256(material)
        mutated = dict(material)
        mutated["semantic_capability_digest_sha256"] = "ab" * 32
        self.assertNotEqual(epoch_a, evidence_epoch_sha256(mutated))
        slice_payload = forge_semantic_slice_for_repo(ROOT)
        self.assertTrue(slice_payload["semantic_capability_entries"])
        self.assertLessEqual(len(slice_payload["semantic_capability_entries"]), 6)
        self.assertIs(slice_payload["authority_granted"], False)
        route_ids = {
            item["semantic_route_id"]
            for item in slice_payload["semantic_capability_entries"]
        }
        self.assertIn("SEM-EXPERIMENT-CAPABILITIES", route_ids)
        self.assertIn("SEM-MARKET-DATA-FEATURES", route_ids)
        self.assertNotIn("SEM-HYPOTHESIS-FORGE", route_ids)
        self.assertEqual(slice_payload["semantic_capability_digest_sha256"], digest)

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            store = ResearchStore(data_root)
            packet, _digest = build_forge_context_packet(
                ROOT,
                data_root,
                owner_focus="AUTO",
                evidence_epoch=epoch_a,
                search_key="0" * 64,
                commissioning_status="NO_GIT_FAST_LANE_PROVEN",
                research_memory_as_of="2026-09-02T00:00:00Z",
                store=store,
            )
            encoded = canonical_json_bytes(packet)
            self.assertLessEqual(len(encoded), MAX_PACKET_BYTES)
            self.assertIn("semantic_capability_entries", packet)
            self.assertTrue(packet["semantic_capability_entries"])
            self.assertTrue(
                any(
                    item["semantic_route_id"] == "SEM-EXPERIMENT-CAPABILITIES"
                    and "CONFIG-EXPERIMENT-CAPABILITY-REGISTRY-V2-001"
                    in item["root_asset_ids"]
                    for item in packet["semantic_capability_entries"]
                )
            )
            for item in packet["semantic_capability_entries"]:
                self.assertIs(item["authority_granted"], False)

    def test_architecture_intent_cannot_be_current_root_asset(self) -> None:
        mutated = copy.deepcopy(self.projection)
        for route in mutated["routes"]:
            if route["semantic_route_id"] == "SEM-PRODUCT-STATE":
                route["root_asset_ids"] = ["ARCH-INTENT-005"]
                break
        errors = validate_semantic_projection(
            mutated,
            assets=self.snapshot.assets,
            bindings=self.bindings,
            queries=self.snapshot.queries,
        )
        self.assertTrue(
            any(code.startswith("arch_intent_as_root_asset:") for code in errors)
        )

    def test_machine_packet_and_generated_map_surface(self) -> None:
        routes = self.projection["routes"]
        self.assertEqual(len(routes), 11)
        self.assertIs(self.projection["authority_granted"], False)
        map_path = ROOT / "docs/FACTORY_SEMANTIC_MAP.md"
        self.assertTrue(map_path.is_file())
        map_text = map_path.read_text(encoding="utf-8")
        self.assertLessEqual(len(map_text.encode("utf-8")), 24 * 1024)
        self.assertNotIn("PARTIAL_COVERAGE", map_text)
        self.assertNotIn("PRODUCT_ROADMAP", map_text)
        operator = (ROOT / "docs/OPERATOR_NAVIGATION.md").read_text(encoding="utf-8")
        self.assertIn("search-routes", operator)
        self.assertIn("QUERY-HFIC-EXACT-RELATED-PRIOR-001", operator)
        self.assertNotIn("current prior-work discovery remains PARTIAL_COVERAGE", operator)
        for route in routes:
            self.assertIs(self.projection["authority_granted"], False)
            for token in (
                "currently active",
                "currently healthy",
                "current activation sha",
                "current backup age",
            ):
                blob = json.dumps(route, ensure_ascii=False).casefold()
                self.assertNotIn(token, blob)
        overview = list_semantic_routes(
            self.projection,
            assets=self.snapshot.assets,
            bindings=self.bindings,
        )
        overview_bytes = json.dumps(
            overview, ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
        self.assertLessEqual(len(overview_bytes), 16 * 1024)
        sample = resolve_semantic_route(
            self.projection,
            "SEM-PRODUCT-STATE",
            assets=self.snapshot.assets,
            bindings=self.bindings,
        )
        self.assertLessEqual(
            len(json.dumps(sample, ensure_ascii=False).encode("utf-8")),
            8 * 1024,
        )
        self.assertNotIn("PROJECT_MAP", json.dumps(sample))


if __name__ == "__main__":
    unittest.main()
