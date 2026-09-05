from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SRC))

from catalog_cli import search_assets  # noqa: E402
from solana_alpha_lab.catalog_discovery import (  # noqa: E402
    IDENTITY_ASSET_ID,
    IDENTITY_BINDING_ID,
    IDENTITY_PATH,
    BINDING_TARGET_BONUS,
    BindingValidationError,
    CatalogDiscoveryError,
    related_catalog_assets,
    resolve_canonical_binding,
    search_catalog_assets,
    validate_canonical_bindings,
)
from validate_catalog import load_and_validate  # noqa: E402

GOLD_PATH = ROOT / "catalog/fixtures/discovery_gold_queries_v1.yaml"
MANIFEST_SCHEMA = ROOT / "catalog/schemas/catalog_manifest.schema.json"


def _asset(
    asset_id: str,
    *,
    path: str = "",
    logical_uri: str = "",
    purpose: str = "",
    search_terms: list[str] | None = None,
    status: str = "VALIDATED_ACTIVE",
    asset_type: str = "configuration",
    consumers: list[str] | None = None,
    relations: list[dict[str, str]] | None = None,
) -> dict:
    location: dict[str, str] = {"repository_path": path}
    if logical_uri:
        location["logical_uri"] = logical_uri
    return {
        "asset_id": asset_id,
        "asset_type": asset_type,
        "purpose": purpose,
        "status": status,
        "location": location,
        "consumers": consumers or [],
        "relations": relations or [],
        "evidence": [],
        "search_terms": search_terms or [],
    }


BINDINGS = {
    "ACTIVE-PROVIDER-ROUTE-CAPABILITY-REGISTRY": {
        "target_asset_id": "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010",
        "expected_asset_type": "configuration",
        "semantics": "CURRENT_AT_COMMIT",
        "rationale": "Current used provider route capability lineage head",
        "current_use_evidence_asset_ids": ["MODULE-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010"],
    }
}


class CanonicalBindingSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))
        self.validator = Draft202012Validator(self.schema)

    def test_legacy_1_0_manifest_without_bindings_is_valid(self) -> None:
        live = yaml.safe_load((ROOT / "catalog/catalog_manifest.yaml").read_text(encoding="utf-8"))
        legacy = copy.deepcopy(live)
        legacy["schema_version"] = "1.0"
        legacy.pop("canonical_bindings", None)
        commands = legacy["root_resolver"]["commands"]
        for key in (
            "resolve_binding",
            "search_assets",
            "related_assets",
            "search_routes",
            "resolve_route",
            "list_routes",
        ):
            commands.pop(key, None)
        self.validator.validate(legacy)

    def test_live_1_1_requires_bindings_and_new_commands(self) -> None:
        live = yaml.safe_load((ROOT / "catalog/catalog_manifest.yaml").read_text(encoding="utf-8"))
        self.assertEqual(live["schema_version"], "1.1")
        self.validator.validate(live)
        missing = copy.deepcopy(live)
        del missing["canonical_bindings"]
        errors = list(self.validator.iter_errors(missing))
        self.assertTrue(errors)
        commands = live["root_resolver"]["commands"]
        self.assertNotIn("prior_work_references", commands)
        self.assertNotIn(
            "prior_work_references",
            self.schema["properties"]["root_resolver"]["properties"]["commands"]["properties"],
        )

    def test_unverified_binding_without_evidence_fails_semantics(self) -> None:
        assets = {
            "CONFIG-X-001": _asset("CONFIG-X-001", status="IMPLEMENTED_UNVERIFIED"),
        }
        manifest = {
            "schema_version": "1.1",
            "canonical_bindings": {
                "ACTIVE-X": {
                    "target_asset_id": "CONFIG-X-001",
                    "semantics": "CURRENT_AT_COMMIT",
                    "rationale": "Needs current-use evidence",
                }
            },
        }
        with self.assertRaisesRegex(BindingValidationError, "binding_unverified_evidence_missing"):
            validate_canonical_bindings(manifest, assets)

    def test_unverified_binding_with_evidence_passes_semantics(self) -> None:
        assets = {
            "CONFIG-X-001": _asset("CONFIG-X-001", status="IMPLEMENTED_UNVERIFIED"),
            "MODULE-X-001": _asset("MODULE-X-001", asset_type="script"),
        }
        manifest = {
            "schema_version": "1.1",
            "canonical_bindings": {
                "ACTIVE-X": {
                    "target_asset_id": "CONFIG-X-001",
                    "expected_asset_type": "configuration",
                    "semantics": "CURRENT_AT_COMMIT",
                    "rationale": "Current-use evidence present",
                    "current_use_evidence_asset_ids": ["MODULE-X-001"],
                }
            },
        }
        validate_canonical_bindings(manifest, assets)


class RankedSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assets = {
            "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-003": _asset(
                "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-003",
                path="configs/provider_route_capability_registry_v3.yaml",
                purpose="Historical v3 provider-route registry",
                search_terms=["PROVIDER_ROUTE", "REGISTRY_V3"],
            ),
            "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010": _asset(
                "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010",
                path="configs/provider_route_capability_registry_v10.yaml",
                purpose="Current v10 provider-route registry",
                search_terms=["PROVIDER_ROUTE", "current provider route registry"],
                status="IMPLEMENTED_UNVERIFIED",
            ),
            "MODULE-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010": _asset(
                "MODULE-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010",
                path="src/solana_alpha_lab/provider_route_capability_registry_v10.py",
                purpose="v10 resolver",
                asset_type="script",
                status="IMPLEMENTED_UNVERIFIED",
            ),
            "DOC-OTHER-001": _asset(
                "DOC-OTHER-001",
                path="docs/other.md",
                purpose="Unrelated document",
                asset_type="control_document",
                status="DEPRECATED",
            ),
        }

    def test_exact_asset_id_beats_current_binding(self) -> None:
        hits = search_catalog_assets(
            self.assets,
            "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-003",
            bindings=BINDINGS,
        )
        assert isinstance(hits, list)
        self.assertEqual(hits[0]["asset_id"], "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-003")
        self.assertEqual(hits[0]["score"], IDENTITY_ASSET_ID)

    def test_exact_historical_path_is_identity(self) -> None:
        hits = search_catalog_assets(
            self.assets,
            "configs/provider_route_capability_registry_v3.yaml",
            bindings=BINDINGS,
        )
        assert isinstance(hits, list)
        self.assertEqual(hits[0]["asset_id"], "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-003")
        self.assertEqual(hits[0]["score"], IDENTITY_PATH)

    def test_exact_binding_id_returns_target(self) -> None:
        hits = search_catalog_assets(
            self.assets,
            "ACTIVE-PROVIDER-ROUTE-CAPABILITY-REGISTRY",
            bindings=BINDINGS,
        )
        assert isinstance(hits, list)
        self.assertEqual(hits[0]["asset_id"], "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010")
        self.assertEqual(hits[0]["score"], IDENTITY_BINDING_ID)

    def test_generic_current_query_ranks_bound_target_above_v3(self) -> None:
        hits = search_catalog_assets(
            self.assets,
            "current provider route registry",
            bindings=BINDINGS,
        )
        assert isinstance(hits, list)
        self.assertEqual(hits[0]["asset_id"], "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010")
        ids = [item["asset_id"] for item in hits]
        if "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-003" in ids:
            self.assertLess(
                ids.index("CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010"),
                ids.index("CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-003"),
            )

    def test_binding_bonus_does_not_beat_exact_id(self) -> None:
        hits = search_catalog_assets(
            self.assets,
            "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-003",
            bindings=BINDINGS,
        )
        assert isinstance(hits, list)
        self.assertEqual(hits[0]["asset_id"], "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-003")
        self.assertEqual(hits[0]["score"], IDENTITY_ASSET_ID)
        self.assertLess(IDENTITY_BINDING_ID, IDENTITY_ASSET_ID)
        self.assertLess(BINDING_TARGET_BONUS + 20000, IDENTITY_PATH)

    def test_nfkc_and_casefold_are_deterministic(self) -> None:
        first = search_catalog_assets(self.assets, "PROVIDER‐ROUTE", bindings=BINDINGS, match="any")
        second = search_catalog_assets(self.assets, "provider-route", bindings=BINDINGS, match="any")
        assert isinstance(first, list)
        assert isinstance(second, list)
        self.assertEqual(
            [(item["asset_id"], item["score"]) for item in first],
            [(item["asset_id"], item["score"]) for item in second],
        )

    def test_all_versus_any_are_distinct(self) -> None:
        all_hits = search_catalog_assets(
            self.assets, "provider unrelated-token", bindings=BINDINGS, match="all"
        )
        any_hits = search_catalog_assets(
            self.assets, "provider unrelated-token", bindings=BINDINGS, match="any"
        )
        assert isinstance(all_hits, list)
        assert isinstance(any_hits, list)
        self.assertEqual(all_hits, [])
        self.assertTrue(any_hits)

    def test_match_all_does_not_accept_token_substrings(self) -> None:
        assets = {
            "ASSET-ROUTER-001": _asset("ASSET-ROUTER-001", search_terms=["router"]),
            "ASSET-ROUTE-001": _asset("ASSET-ROUTE-001", search_terms=["route"]),
        }
        hits = search_catalog_assets(assets, "route", match="all")
        assert isinstance(hits, list)
        self.assertEqual([item["asset_id"] for item in hits], ["ASSET-ROUTE-001"])

    def test_logical_uri_is_identity_and_indexed(self) -> None:
        assets = {
            "ASSET-URI-001": _asset(
                "ASSET-URI-001",
                path="configs/example.yaml",
                logical_uri="repo://configs/example.yaml",
                search_terms=["unrelated"],
            )
        }
        identity = search_catalog_assets(assets, "repo://configs/example.yaml")
        assert isinstance(identity, list)
        self.assertEqual(identity[0]["asset_id"], "ASSET-URI-001")
        self.assertEqual(identity[0]["score"], IDENTITY_PATH)
        self.assertEqual(identity[0]["matched_by"][0]["component"], "EXACT_LOGICAL_URI")
        conceptual = search_catalog_assets(assets, "repo configs example", match="all")
        assert isinstance(conceptual, list)
        self.assertEqual(conceptual[0]["asset_id"], "ASSET-URI-001")

    def test_filters_apply_before_rank(self) -> None:
        hits = search_catalog_assets(
            self.assets,
            "provider route",
            bindings=BINDINGS,
            status="VALIDATED_ACTIVE",
            match="all",
        )
        assert isinstance(hits, list)
        self.assertEqual(
            [item["asset_id"] for item in hits],
            ["CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-003"],
        )

    def test_limit_and_depth_bounds(self) -> None:
        with self.assertRaisesRegex(CatalogDiscoveryError, "LIMIT_OUT_OF_RANGE"):
            search_catalog_assets(self.assets, "provider", limit=0)
        with self.assertRaisesRegex(CatalogDiscoveryError, "LIMIT_OUT_OF_RANGE"):
            search_catalog_assets(self.assets, "provider", limit=51)
        with self.assertRaisesRegex(CatalogDiscoveryError, "DEPTH_OUT_OF_RANGE"):
            related_catalog_assets(self.assets, "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010", depth=0)
        with self.assertRaisesRegex(CatalogDiscoveryError, "DEPTH_OUT_OF_RANGE"):
            related_catalog_assets(self.assets, "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010", depth=3)

    def test_explain_envelope_and_byte_stable_rerun(self) -> None:
        first = search_catalog_assets(
            self.assets, "provider route", bindings=BINDINGS, explain=True
        )
        second = search_catalog_assets(
            self.assets, "provider route", bindings=BINDINGS, explain=True
        )
        self.assertIn("results", first)
        self.assertEqual(
            json.dumps(first, sort_keys=True, ensure_ascii=False),
            json.dumps(second, sort_keys=True, ensure_ascii=False),
        )


class RelatedAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assets = {
            "ASSET-A-001": _asset(
                "ASSET-A-001",
                relations=[
                    {"relation_type": "depends_on", "target_asset_id": "ASSET-B-001"},
                    {"relation_type": "advises", "target_asset_id": "ASSET-D-001"},
                ],
            ),
            "ASSET-B-001": _asset(
                "ASSET-B-001",
                relations=[
                    {"relation_type": "depends_on", "target_asset_id": "ASSET-C-001"},
                    {"relation_type": "governed_by", "target_asset_id": "ASSET-E-001"},
                ],
            ),
            "ASSET-C-001": _asset(
                "ASSET-C-001",
                relations=[{"relation_type": "validated_by", "target_asset_id": "ASSET-A-001"}],
            ),
            "ASSET-D-001": _asset("ASSET-D-001"),
            "ASSET-E-001": _asset("ASSET-E-001"),
            "ASSET-Z-001": _asset(
                "ASSET-Z-001",
                relations=[
                    {"relation_type": "advises", "target_asset_id": "ASSET-X-001"},
                    {"relation_type": "contains", "target_asset_id": "ASSET-Y-001"},
                ],
            ),
            "ASSET-X-001": _asset(
                "ASSET-X-001",
                relations=[{"relation_type": "depends_on", "target_asset_id": "ASSET-T-001"}],
            ),
            "ASSET-Y-001": _asset(
                "ASSET-Y-001",
                relations=[{"relation_type": "depends_on", "target_asset_id": "ASSET-T-001"}],
            ),
            "ASSET-T-001": _asset("ASSET-T-001"),
        }

    def test_direction_and_depth(self) -> None:
        out1 = related_catalog_assets(self.assets, "ASSET-A-001", depth=1, direction="out")
        both2 = related_catalog_assets(self.assets, "ASSET-A-001", depth=2, direction="both")
        incoming = related_catalog_assets(self.assets, "ASSET-A-001", depth=1, direction="in")
        self.assertEqual({item["asset_id"] for item in out1["results"]}, {"ASSET-B-001", "ASSET-D-001"})
        self.assertIn("ASSET-C-001", {item["asset_id"] for item in both2["results"]})
        self.assertEqual({item["asset_id"] for item in incoming["results"]}, {"ASSET-C-001"})
        self.assertFalse(both2["authority_inferred"])

    def test_cycle_terminates(self) -> None:
        payload = related_catalog_assets(self.assets, "ASSET-A-001", depth=2, direction="both")
        ids = [item["asset_id"] for item in payload["results"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn("ASSET-A-001", ids)

    def test_equal_shortest_path_is_lexicographic(self) -> None:
        payload = related_catalog_assets(self.assets, "ASSET-Z-001", depth=2, direction="out")
        target = next(item for item in payload["results"] if item["asset_id"] == "ASSET-T-001")
        self.assertEqual(
            [hop["asset_id"] for hop in target["path"]],
            ["ASSET-X-001", "ASSET-T-001"],
        )

    def test_relation_filter_and_truncation(self) -> None:
        filtered = related_catalog_assets(
            self.assets, "ASSET-A-001", depth=1, direction="out", relation="advises"
        )
        self.assertEqual([item["asset_id"] for item in filtered["results"]], ["ASSET-D-001"])
        truncated = related_catalog_assets(
            self.assets, "ASSET-A-001", depth=2, direction="both", limit=1
        )
        self.assertTrue(truncated["truncated"])
        self.assertEqual(len(truncated["results"]), 1)


class ResolveBindingTests(unittest.TestCase):
    def _snapshot(self) -> SimpleNamespace:
        target_id = "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010"
        return SimpleNamespace(
            manifest={
                "catalog_version": "0.120.0",
                "canonical_bindings": BINDINGS,
            },
            assets={
                target_id: _asset(
                    target_id,
                    path="configs/provider_route_capability_registry_v1.yaml",
                    status="IMPLEMENTED_UNVERIFIED",
                ),
                "MODULE-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010": _asset(
                    "MODULE-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010",
                    asset_type="script",
                ),
            },
        )

    def test_resolve_success_emits_unverified_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "configs/provider_route_capability_registry_v1.yaml"
            target.parent.mkdir(parents=True)
            target.write_text("route: current\n", encoding="utf-8")
            snapshot = self._snapshot()
            with mock.patch(
                "solana_alpha_lab.catalog_discovery.git_head",
                return_value="a" * 40,
            ), mock.patch(
                "solana_alpha_lab.catalog_discovery.dirty_paths",
                return_value=[],
            ):
                payload = resolve_canonical_binding(
                    snapshot,
                    "ACTIVE-PROVIDER-ROUTE-CAPABILITY-REGISTRY",
                    root=root,
                    shard_paths=["catalog/assets/core.yaml"],
                )
        self.assertEqual(payload["asset_id"], "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010")
        self.assertTrue(payload["relevant_bytes_clean"])
        self.assertEqual(payload["repository_commit"], "a" * 40)
        self.assertEqual(
            payload["verification_warning"],
            "IMPLEMENTED_UNVERIFIED_CURRENT_USE_EVIDENCE_PRESENT",
        )
        self.assertEqual(
            payload["current_use_evidence_asset_ids"],
            ["MODULE-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010"],
        )

    def test_resolve_missing_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(CatalogDiscoveryError, "BINDING_NOT_FOUND"):
                resolve_canonical_binding(
                    self._snapshot(),
                    "ACTIVE-MISSING",
                    root=Path(temporary),
                    shard_paths=[],
                )

    def test_resolve_dirty_bytes_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "configs/provider_route_capability_registry_v1.yaml"
            target.parent.mkdir(parents=True)
            target.write_text("route: current\n", encoding="utf-8")
            with mock.patch(
                "solana_alpha_lab.catalog_discovery.dirty_paths",
                return_value=["catalog/catalog_manifest.yaml"],
            ):
                with self.assertRaisesRegex(
                    CatalogDiscoveryError, "BINDING_RELEVANT_BYTES_DIRTY"
                ):
                    resolve_canonical_binding(
                        self._snapshot(),
                        "ACTIVE-PROVIDER-ROUTE-CAPABILITY-REGISTRY",
                        root=root,
                        shard_paths=["catalog/assets/core.yaml"],
                    )


class LiveCatalogDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = load_and_validate()
        cls.bindings = cls.snapshot.manifest["canonical_bindings"]

    def test_live_bindings_include_atom_a_and_semantic_roots(self) -> None:
        self.assertLessEqual(len(self.bindings), 11)
        self.assertIn("ACTIVE-PROVIDER-ROUTE-CAPABILITY-REGISTRY", self.bindings)
        self.assertIn("ACTIVE-FACTORY-MARKET-FEATURE-SURFACE", self.bindings)
        self.assertIn("ACTIVE-FACTORY-SEMANTIC-OPERABILITY", self.bindings)
        self.assertIn("ACTIVE-SMIAL-VISUAL-OPERATING-SYSTEM", self.bindings)
        self.assertIn("ACTIVE-OWNER-LIFECYCLE-PROJECTION", self.bindings)
        self.assertEqual(
            self.bindings["ACTIVE-OWNER-LIFECYCLE-PROJECTION"]["target_asset_id"],
            "CONFIG-OWNER-LIFECYCLE-PROJECTION-001",
        )
        self.assertEqual(
            self.bindings["ACTIVE-SMIAL-VISUAL-OPERATING-SYSTEM"]["target_asset_id"],
            "CONFIG-SMIAL-VISUAL-OPERATING-SYSTEM-001",
        )
        self.assertEqual(
            self.bindings["ACTIVE-PROVIDER-ROUTE-CAPABILITY-REGISTRY"]["target_asset_id"],
            "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-010",
        )
        self.assertEqual(
            self.bindings["ACTIVE-FACTORY-MARKET-FEATURE-SURFACE"]["target_asset_id"],
            "CONFIG-FACTORY-V1-COMMON-MARKET-FEATURE-SURFACE-001",
        )
        self.assertEqual(
            self.bindings["ACTIVE-FACTORY-OPERATIONAL-READINESS"]["target_asset_id"],
            "CONFIG-FACTORY-V1-OPERATIONAL-READINESS-001",
        )

    def test_legacy_search_assets_wrapper_still_accepts_old_call(self) -> None:
        matches = search_assets(self.snapshot.assets, "active pool route yield", asset_type="evidence")
        assert isinstance(matches, list)
        self.assertTrue(matches)
        self.assertIn("score", matches[0])

    def test_gold_queries(self) -> None:
        fixture = yaml.safe_load(GOLD_PATH.read_text(encoding="utf-8"))
        queries = fixture["queries"]
        self.assertEqual(len(queries), 26)
        ids = [item["query_id"] for item in queries]
        self.assertEqual(len(ids), len(set(ids)))
        first = []
        second = []
        for case in queries:
            kwargs = {
                "bindings": self.bindings,
                "match": case.get("match", "all"),
                "limit": int(case.get("limit", 20)),
                "asset_type": (case.get("filters") or {}).get("asset_type"),
                "status": (case.get("filters") or {}).get("status"),
                "consumer": (case.get("filters") or {}).get("consumer"),
                "relation": (case.get("filters") or {}).get("relation"),
            }
            hits = search_catalog_assets(self.snapshot.assets, case["query"], **kwargs)
            assert isinstance(hits, list)
            payload = [item["asset_id"] for item in hits]
            first.append(payload)
            ranked = payload[:5]
            if case.get("required_empty"):
                self.assertEqual(payload, [])
                continue
            for required in case.get("required_top_5") or []:
                self.assertIn(required, ranked, msg=case["query_id"])
            for historical, target in (case.get("forbidden_above") or {}).items():
                if historical in payload and target in payload:
                    self.assertLess(
                        payload.index(target),
                        payload.index(historical),
                        msg=case["query_id"],
                    )
        for case in queries:
            kwargs = {
                "bindings": self.bindings,
                "match": case.get("match", "all"),
                "limit": int(case.get("limit", 20)),
                "asset_type": (case.get("filters") or {}).get("asset_type"),
                "status": (case.get("filters") or {}).get("status"),
                "consumer": (case.get("filters") or {}).get("consumer"),
                "relation": (case.get("filters") or {}).get("relation"),
            }
            hits = search_catalog_assets(self.snapshot.assets, case["query"], **kwargs)
            assert isinstance(hits, list)
            second.append([item["asset_id"] for item in hits])
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
