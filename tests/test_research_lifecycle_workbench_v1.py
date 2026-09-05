from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.application import FactoryApplication
from solana_alpha_lab.factory.data_root import resolve_existing_data_root
from solana_alpha_lab.factory.lifecycle_projection import (
    _entity,
    _merge_entities,
    build_lifecycle_projection,
)
from solana_alpha_lab.factory.research_store import (
    ExistingResearchStoreReader,
    ResearchEvent,
    ResearchStore,
    ResearchStoreError,
)
from solana_alpha_lab.factory.research_workbench import (
    LifecycleEntityLocatorV1,
    ResearchWorkbenchError,
    build_research_detail,
    compose_research_detail,
    compose_research_overview,
    parse_locator,
)
from solana_alpha_lab.factory.workbench import _research_overview_html, serve
from solana_alpha_lab.factory_semantic_operability import (
    load_semantic_catalog_views,
    load_semantic_projection,
    resolve_semantic_route,
    search_semantic_routes,
)
from validate_catalog import load_and_validate

TRIAL_ID = "TRIAL-RC002-H11-NEXT-GTA-TARGET-001"
EXPERIMENT_ID = "EXP-ORDINARY-PRICE-PATH-HYPOTHESIS-001"
NEGATIVE_ID = "NEGATIVE-T30-CURRENT-DATA-ROUTE-001"
NOW = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)


def _event(
    *,
    record_id: str,
    record_kind: str,
    entity_id: str,
    payload: dict,
    hypothesis_version_id: str | None = None,
    transaction_id: str,
) -> ResearchEvent:
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return ResearchEvent(
        record_id=record_id,
        record_kind=record_kind,
        entity_id=entity_id,
        hypothesis_version_id=hypothesis_version_id,
        run_id=None,
        transaction_id=transaction_id,
        effective_at=NOW,
        first_reliable_available_at=NOW,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        producer_git_sha="a" * 40,
        created_at=NOW,
    )


def _inventory(path: Path) -> dict[str, str]:
    digest: dict[str, str] = {}
    if not path.exists():
        return digest
    for item in sorted(path.rglob("*")):
        if item.is_file():
            digest[item.relative_to(path).as_posix()] = hashlib.sha256(
                item.read_bytes()
            ).hexdigest()
    return digest


def _get(app: FactoryApplication, path: str) -> tuple[int, str, dict[str, str]]:
    server = serve(app, host="127.0.0.1", port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        conn = HTTPConnection(host, port, timeout=8)
        conn.request("GET", path)
        response = conn.getresponse()
        headers = {key.lower(): value for key, value in response.getheaders()}
        body = response.read().decode("utf-8")
        status = response.status
        conn.close()
        return status, body, headers
    finally:
        server.shutdown()
        server.server_close()


class ResearchLifecycleWorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.projection = build_lifecycle_projection(
            ROOT, projected_at="2026-09-05T21:00:00Z"
        )
        cls.overview = compose_research_overview(cls.projection)
        cls.missing_root = ROOT / "local" / "factory_v1" / "research_workbench_absent"
        cls.app = FactoryApplication(
            root=ROOT,
            spec_relative="configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml",
            research_data_root=cls.missing_root,
        )

    def test_real_trial_memory(self) -> None:
        ids = {item["locator"]["entity_id"] for item in self.overview["universe"]}
        self.assertIn(TRIAL_ID, ids)
        locator = LifecycleEntityLocatorV1(TRIAL_ID, "GIT", "TRIAL")
        detail = compose_research_detail(self.projection, locator, root=ROOT)
        self.assertEqual(detail["fields"]["native outcome"], "PASS")
        self.assertNotEqual(detail["fields"]["native outcome"], "POSITIVE")
        self.assertEqual(detail["fields"]["created_at"], "2026-08-15T22:00:00Z")
        self.assertIn("EVIDENCE-T38-RC002-H11-NEXT-GTA-001", detail["fields"]["evidence asset IDs"])
        outbound = detail["lineage"]["outbound"]
        hyp = [
            item
            for item in outbound
            if item["relation_type"] == "REFERENCES_HYPOTHESIS_VERSION"
        ]
        self.assertEqual(hyp[0]["to_entity_id"], "HYP-RC002-H11-LIFECYCLE-CLOCK-V1")
        self.assertEqual(hyp[0]["resolution"], "TARGET_GAP")
        self.assertNotIn("HYP-RC002-H11-LIFECYCLE-CLOCK-V1", ids)

    def test_real_experiment_detail(self) -> None:
        locator = LifecycleEntityLocatorV1(EXPERIMENT_ID, "GIT", "EXPERIMENT_SPEC")
        detail = compose_research_detail(self.projection, locator, root=ROOT)
        self.assertIn("buy-pressure", str(detail["fields"]["QUESTION"]))
        self.assertTrue(detail["fields"]["ESTIMAND"])
        self.assertTrue(detail["fields"]["POPULATION"])
        self.assertTrue(detail["fields"]["FALSIFIER"])
        self.assertEqual(detail["header"]["truth_plane"], "GIT")
        hyp = [
            item
            for item in detail["lineage"]["outbound"]
            if item["relation_type"] == "REFERENCES_HYPOTHESIS_VERSION"
        ]
        self.assertEqual(hyp[0]["resolution"], "TARGET_GAP")

    def test_real_negative_is_not_killed(self) -> None:
        locator = LifecycleEntityLocatorV1(NEGATIVE_ID, "GIT", "NEGATIVE_RESULT")
        detail = compose_research_detail(self.projection, locator, root=ROOT)
        self.assertIn("UNKNOWN is not inactive", str(detail["fields"]["summary"]))
        self.assertNotEqual(detail["header"]["state"], "KILLED")
        self.assertFalse(
            any(
                item["relation_type"] == "REFERENCES_HYPOTHESIS_VERSION"
                for item in detail["lineage"]["outbound"]
            )
        )
        self.assertIn(
            "EVIDENCE-T30-A19-TERMINAL-ROUTE-DECISION-001",
            detail["fields"]["evidence asset IDs"],
        )

    def test_http_overview_and_click_detail(self) -> None:
        status, body, headers = _get(self.app, "/research")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("cache-control"), "no-store")
        self.assertIn(TRIAL_ID, body)
        self.assertIn(EXPERIMENT_ID, body)
        self.assertIn(NEGATIVE_ID, body)
        self.assertIn("STEEL_SIGNAL", body)
        self.assertIn("--surface-void", body)
        self.assertIn("data-visual-os-consumed=\"true\"", body)
        self.assertNotIn("CREATE", body)
        self.assertNotIn("FREEZE", body)
        self.assertNotIn("PROMOTE", body)
        href = (
            f"/research?entity_id={EXPERIMENT_ID}"
            "&truth_plane=GIT&native_kind=EXPERIMENT_SPEC"
        )
        status, detail, _ = _get(self.app, href)
        self.assertEqual(status, 200)
        self.assertIn("EVIDENCE_EDITORIAL", detail)
        self.assertIn("QUESTION", detail)
        self.assertIn("TRACE", detail.upper() + detail)
        self.assertIn("computational-field", detail)
        self.assertIn("semantic-unknown", detail)
        wrong = (
            f"/research?entity_id={EXPERIMENT_ID}"
            "&truth_plane=RUNTIME&native_kind=EXPERIMENT_SPEC"
        )
        _, wrong_body, _ = _get(self.app, wrong)
        self.assertIn("LOCATOR_NOT_IN_PROJECTION", wrong_body)

    def test_locator_rejects_paths_and_requires_plane(self) -> None:
        with self.assertRaises(ResearchWorkbenchError):
            parse_locator("../etc/passwd", "GIT", "TRIAL")
        with self.assertRaises(ResearchWorkbenchError):
            parse_locator("catalog/assets/core.yaml", "GIT", "TRIAL")
        with self.assertRaises(ResearchWorkbenchError):
            parse_locator(TRIAL_ID, None, "TRIAL")
        parsed = parse_locator(TRIAL_ID, "GIT", "TRIAL")
        self.assertEqual(parsed.as_tuple(), (TRIAL_ID, "GIT", "TRIAL"))

    def test_existing_research_store_read_is_non_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ResearchStore(data_root)
            store.append(
                [
                    _event(
                        record_id="HYP-EVENT-WB-001",
                        record_kind="HYPOTHESIS_VERSION",
                        entity_id="HYP-WB-FIXTURE-V1",
                        hypothesis_version_id="HYP-WB-FIXTURE-V1",
                        payload={
                            "hypothesis_version_id": "HYP-WB-FIXTURE-V1",
                            "claim": "workbench fixture",
                            "mechanism": "fixture-mechanism",
                            "falsifier": "fixture-falsifier",
                        },
                        transaction_id="RESEARCH-TXN-WB-001",
                    )
                ],
                transaction_id="RESEARCH-TXN-WB-001",
            )
            store.append(
                [
                    _event(
                        record_id="TRIAL-EVENT-WB-001",
                        record_kind="TRIAL",
                        entity_id="TRIAL-WB-001",
                        hypothesis_version_id="HYP-WB-FIXTURE-V1",
                        payload={"trial_id": "TRIAL-WB-001", "outcome": "INCONCLUSIVE"},
                        transaction_id="RESEARCH-TXN-WB-002",
                    )
                ],
                transaction_id="RESEARCH-TXN-WB-002",
            )
            store.append(
                [
                    _event(
                        record_id="DECISION-EVENT-WB-001",
                        record_kind="DECISION_EVENT",
                        entity_id="DECISION-WB-001",
                        hypothesis_version_id="HYP-WB-FIXTURE-V1",
                        payload={
                            "decision_event_id": "DECISION-WB-001",
                            "trial_id": "TRIAL-WB-001",
                            "decision_kind": "PARK",
                        },
                        transaction_id="RESEARCH-TXN-WB-003",
                    )
                ],
                transaction_id="RESEARCH-TXN-WB-003",
            )
            before = _inventory(data_root)
            reader = ExistingResearchStoreReader(data_root)
            projection = build_lifecycle_projection(
                ROOT,
                research_store=reader,
                projected_at="2026-09-05T21:00:00Z",
            )
            overview = compose_research_overview(projection)
            ids = {item["locator"]["entity_id"] for item in overview["universe"]}
            self.assertIn("TRIAL-WB-001", ids)
            detail = compose_research_detail(
                projection,
                LifecycleEntityLocatorV1("TRIAL-WB-001", "EVIDENCE", "TRIAL"),
                root=ROOT,
            )
            self.assertEqual(detail["fields"]["trial outcome"], "INCONCLUSIVE")
            self.assertNotIn("decision kind", detail["fields"])
            self.assertEqual(detail["lineage"]["outbound"][0]["resolution"], "RESOLVED")
            after = _inventory(data_root)
            self.assertEqual(before, after)
            self.assertFalse(any("writer" in name or "lease" in name for name in after))

    def test_missing_research_store_stays_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            missing = repo / "local" / "factory_v1" / "data_plane"
            discovered = resolve_existing_data_root(repo)
            self.assertEqual(discovered.status, "NOT_PRESENT")
            self.assertFalse(missing.exists())
            with self.assertRaises(ResearchStoreError):
                ExistingResearchStoreReader(missing)
            self.assertFalse(missing.exists())
            projection = build_lifecycle_projection(
                ROOT,
                research_discovery_status="NOT_PRESENT",
                projected_at="2026-09-05T21:00:00Z",
            )
            overview = compose_research_overview(projection)
            self.assertEqual(overview["completeness"], "PARTIAL")
            self.assertTrue(overview["degraded"])
            self.assertIn("unavailable to this Workbench", overview["degraded_copy"] or "")
            research = next(
                item
                for item in overview["sources"]
                if item["source_id"] == "SRC-RESEARCH-STORE"
            )
            self.assertEqual(research["status"], "NOT_PRESENT")
            self.assertFalse(missing.exists())

    def test_plane_conflict_locators_stay_distinct(self) -> None:
        runtime = _entity(
            entity_id="JOB-SHARED-ID",
            projection_class="EXPERIMENT",
            native_kind="EXPERIMENT_RUN",
            native_state="RUNNING",
            source_owner="SRC-OPERATIONAL-STORE",
            source_ref={"kind": "sqlite", "value": "ops"},
            truth_plane="RUNTIME",
            contributing_source_ids=["SRC-OPERATIONAL-STORE"],
        )
        evidence = _entity(
            entity_id="JOB-SHARED-ID",
            projection_class="EXPERIMENT",
            native_kind="EXPERIMENT_RUN",
            native_state="COMPLETED",
            source_owner="SRC-RESEARCH-STORE",
            source_ref={"kind": "research_store", "value": "injected"},
            truth_plane="EVIDENCE",
            contributing_source_ids=["SRC-RESEARCH-STORE"],
        )
        merged, gaps = _merge_entities([runtime, evidence])
        self.assertEqual(len(merged), 2)
        self.assertTrue(any(item["gap_code"] == "IDENTITY_CONFLICT" for item in gaps))
        projection = {
            "schema": "smial.owner-lifecycle-projection",
            "completeness": "PARTIAL",
            "sources": [],
            "entities": merged,
            "relations": [
                {
                    "relation_type": "JOB_FOR_EXPERIMENT",
                    "from_entity_id": "JOB-SHARED-ID",
                    "to_entity_id": EXPERIMENT_ID,
                    "resolution": "CONFLICT",
                    "source_ref": {"kind": "sqlite", "value": "ops"},
                    "derivation_method": "EXPLICIT_CONTRACT_KEY",
                }
            ],
            "gaps": gaps,
        }
        overview = compose_research_overview(projection)
        locators = [tuple(item["locator"].values()) for item in overview["universe"]]
        self.assertIn(("JOB-SHARED-ID", "RUNTIME", "EXPERIMENT_RUN"), locators)
        self.assertIn(("JOB-SHARED-ID", "EVIDENCE", "EXPERIMENT_RUN"), locators)
        runtime_detail = compose_research_detail(
            projection,
            LifecycleEntityLocatorV1("JOB-SHARED-ID", "RUNTIME", "EXPERIMENT_RUN"),
            root=ROOT,
        )
        self.assertEqual(runtime_detail["header"]["state"], "RUNNING")
        self.assertEqual(runtime_detail["lineage"]["outbound"][0]["resolution"], "CONFLICT")
        evidence_detail = compose_research_detail(
            projection,
            LifecycleEntityLocatorV1("JOB-SHARED-ID", "EVIDENCE", "EXPERIMENT_RUN"),
            root=ROOT,
        )
        self.assertEqual(evidence_detail["header"]["state"], "COMPLETED")
        self.assertNotEqual(runtime_detail["header"]["truth_plane"], evidence_detail["header"]["truth_plane"])

    def test_degraded_corrupt_source_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "registries"
            ledger.mkdir()
            (ledger / "global_trial_ledger.yaml").write_text("{", encoding="utf-8")
            # Isolated root lacks the contract; use real ROOT with injected invalid reader.
            class _Broken:
                def iter_committed_records(self):
                    raise RuntimeError("corrupt")

            projection = build_lifecycle_projection(
                ROOT,
                research_store=_Broken(),
                projected_at="2026-09-05T21:00:00Z",
            )
            source = next(
                item for item in projection["sources"] if item["source_id"] == "SRC-RESEARCH-STORE"
            )
            self.assertEqual(source["status"], "INVALID")
            overview = compose_research_overview(projection)
            self.assertEqual(overview["completeness"], "PARTIAL")
            self.assertTrue(overview["degraded"])
            self.assertGreaterEqual(overview["counters"]["ATTENTION"], 1)
            self.assertTrue(
                any(
                    item.get("kind") == "SOURCE"
                    and item.get("native_state") == "SOURCE_INVALID"
                    for item in overview["needs_attention"]
                )
            )
            research = next(
                item
                for item in overview["sources"]
                if item["source_id"] == "SRC-RESEARCH-STORE"
            )
            self.assertEqual(research["status"], "INVALID")
            self.assertEqual(research.get("error"), "RuntimeError")
            ids = {item["locator"]["entity_id"] for item in overview["universe"] if item.get("locator")}
            self.assertIn(TRIAL_ID, ids)
            self.assertIn(EXPERIMENT_ID, ids)

    def test_get_research_does_not_create_sqlite_or_research_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "no-rdp"
            app = FactoryApplication(
                root=ROOT,
                spec_relative="configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml",
                research_data_root=missing,
            )
            status, body, _ = _get(app, "/research")
            self.assertEqual(status, 200)
            self.assertIn("RESEARCH", body)
            self.assertFalse(missing.exists())
            self.assertIsNone(app._operational_store)
            self.assertIsNone(app._paper_plane_store)

    def test_split_brain_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            default = repo / "local" / "factory_v1" / "data_plane"
            other = Path(tmp) / "other"
            default.mkdir(parents=True)
            other.mkdir()
            discovered = resolve_existing_data_root(
                repo, env={"SMIAL_DATA_ROOT": str(other)}
            )
            self.assertEqual(discovered.status, "UNAVAILABLE")
            self.assertEqual(discovered.error, "DATA_ROOT_SPLIT_BRAIN")

    def test_visual_os_tokens_and_no_framework(self) -> None:
        _, body, _ = _get(self.app, "/research")
        self.assertIn("--accent-signal", body)
        self.assertIn("#080A0C", body)
        self.assertIn("DARK_ONLY", body)
        self.assertNotIn("react", body.casefold())
        self.assertNotIn("tailwind", body.casefold())
        self.assertNotIn("https://fonts.", body)
        text = (ROOT / "src/solana_alpha_lab/factory/workbench.py").read_text(encoding="utf-8")
        self.assertIn("visual_os_css", text)
        self.assertNotIn("#66D4F2", text)

    def test_operations_commands_remain(self) -> None:
        text = (ROOT / "src/solana_alpha_lab/factory/workbench.py").read_text(encoding="utf-8")
        for command in (
            "PAUSE_NEW_ENTRIES",
            "RESUME_NEW_ENTRIES",
            "REQUEST_CLOSE_POSITION",
            "REQUEST_CLOSE_ALL",
            "STOP_BOT",
        ):
            self.assertIn(command, text)
        self.assertIn("apply_paper_operator_command", text)
        self.assertIn("expected_open_position_set_sha256", text)
        self.assertIn("CLOSE_ALL_CONFIRMATION_REQUIRED", text)

    def test_semantic_discovery_and_anti_hijack(self) -> None:
        snapshot = load_and_validate(allow_generated_drift=True)
        semantic = load_semantic_projection(ROOT)
        assets, bindings, _queries = load_semantic_catalog_views(ROOT)
        self.assertIn("ACTIVE-RESEARCH-LIFECYCLE-WORKBENCH", bindings)
        payload = resolve_semantic_route(
            semantic,
            "SEM-OWNER-LIFECYCLE",
            assets=snapshot.assets,
            bindings=bindings,
        )
        targets = [item["target_asset_id"] for item in payload["root_bindings"]]
        self.assertIn("CONFIG-OWNER-LIFECYCLE-PROJECTION-001", targets)
        self.assertIn("DOC-RESEARCH-LIFECYCLE-WORKBENCH-001", targets)
        self.assertIs(payload["authority_granted"], False)
        positives = [
            "What research objects exist?",
            "What have we tested?",
            "Where is the Research Workbench?",
            "что сейчас исследуется?",
            "что уже проверяли?",
        ]
        for query in positives:
            hits = search_semantic_routes(
                semantic, query, assets=assets, bindings=bindings, limit=5
            )
            self.assertEqual(hits[0]["semantic_route_id"], "SEM-OWNER-LIFECYCLE", query)
        anti = [
            ("generate hypothesis", "SEM-HYPOTHESIS-FORGE"),
            ("Has mechanism X been tested before?", "SEM-PRIOR-WORK"),
            ("What colors should Workbench use?", "SEM-VISUAL-OPERATING-SYSTEM"),
            ("Is the VPS healthy?", "SEM-REMOTE-OPS-RECOVERY"),
            ("May I deploy?", "SEM-AUTHORITY-BOUNDARIES"),
        ]
        for query, expected in anti:
            hits = search_semantic_routes(
                semantic, query, assets=assets, bindings=bindings, limit=5
            )
            self.assertEqual(hits[0]["semantic_route_id"], expected, query)
        prior = snapshot.assets["REGISTRY-GLOBAL-TRIAL-LEDGER-001"]
        self.assertEqual(prior["status"], "VALIDATED_ACTIVE")

    def test_missing_activity_sources_are_not_shown_as_zero(self) -> None:
        projection = {
            "schema": "smial.owner-lifecycle-projection",
            "completeness": "PARTIAL",
            "sources": [
                {
                    "source_id": "SRC-RESEARCH-STORE",
                    "status": "NOT_PRESENT",
                    "truth_plane": "EVIDENCE",
                    "error": None,
                },
                {
                    "source_id": "SRC-OPERATIONAL-STORE",
                    "status": "UNAVAILABLE",
                    "truth_plane": "RUNTIME",
                    "error": "RESEARCH_STORE_UNAVAILABLE",
                },
                {
                    "source_id": "SRC-EXPERIMENT-SPECS",
                    "status": "AVAILABLE",
                    "truth_plane": "GIT",
                    "error": None,
                },
            ],
            "entities": [],
            "relations": [],
            "gaps": [
                {
                    "gap_code": "SOURCE_UNAVAILABLE",
                    "source_id": "SRC-OPERATIONAL-STORE",
                    "reason": "runtime unreadable",
                    "source_ref": {"kind": "sqlite", "value": "ops"},
                    "impact": "ops_jobs_unreadable",
                    "next_safe_action": "FAIL_CLOSED_FOR_SOURCE",
                }
            ],
        }
        overview = compose_research_overview(projection)
        self.assertIsNone(overview["counters"]["ACTIVE NOW"])
        self.assertEqual(overview["counters"]["TRIALS"], 0)
        self.assertGreaterEqual(overview["counters"]["ATTENTION"], 1)
        self.assertEqual(overview["needs_attention"][0]["kind"], "SOURCE")
        self.assertEqual(overview["needs_attention"][0]["next_safe_action"], "FAIL_CLOSED_FOR_SOURCE")
        html = _research_overview_html(overview)
        self.assertIn("NOT AVAILABLE", html)
        self.assertNotIn("<h3>Current activity</h3><p class=\"empty\">NONE</p>", html)
        self.assertIn("FAIL_CLOSED_FOR_SOURCE", html)

    def test_blocker_none_is_not_attention(self) -> None:
        idle = _entity(
            entity_id="JOB-IDLE-NONE",
            projection_class="EXPERIMENT",
            native_kind="EXPERIMENT_RUN",
            native_state="COMPLETED",
            source_owner="SRC-OPERATIONAL-STORE",
            source_ref={"kind": "sqlite", "value": "ops"},
            truth_plane="RUNTIME",
            contributing_source_ids=["SRC-OPERATIONAL-STORE"],
        )
        idle["blocker"] = "NONE"
        projection = {
            "schema": "smial.owner-lifecycle-projection",
            "completeness": "PARTIAL",
            "sources": [
                {
                    "source_id": "SRC-OPERATIONAL-STORE",
                    "status": "AVAILABLE",
                    "truth_plane": "RUNTIME",
                }
            ],
            "entities": [idle],
            "relations": [],
            "gaps": [],
        }
        overview = compose_research_overview(projection)
        self.assertEqual(overview["counters"]["ATTENTION"], 0)
        self.assertEqual(overview["needs_attention"], [])
        self.assertFalse(overview["universe"][0]["attention"])
        self.assertIsNone(overview["universe"][0]["blocker"])

    def test_evidence_detail_does_not_match_foreign_keys_or_rescan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ResearchStore(data_root)
            store.append(
                [
                    _event(
                        record_id="DECISION-EVENT-FK-001",
                        record_kind="DECISION_EVENT",
                        entity_id="DECISION-FK-001",
                        hypothesis_version_id="HYP-FK-V1",
                        payload={
                            "decision_event_id": "DECISION-FK-001",
                            "trial_id": "TRIAL-FK-001",
                            "decision_kind": "PARK",
                            "claim": "decision must not win trial detail",
                        },
                        transaction_id="RESEARCH-TXN-FK-001",
                    )
                ],
                transaction_id="RESEARCH-TXN-FK-001",
            )
            store.append(
                [
                    _event(
                        record_id="TRIAL-EVENT-FK-001",
                        record_kind="TRIAL",
                        entity_id="TRIAL-FK-001",
                        hypothesis_version_id="HYP-FK-V1",
                        payload={"trial_id": "TRIAL-FK-001", "outcome": "INCONCLUSIVE"},
                        transaction_id="RESEARCH-TXN-FK-002",
                    )
                ],
                transaction_id="RESEARCH-TXN-FK-002",
            )

            class _CountingReader:
                def __init__(self, inner: ExistingResearchStoreReader) -> None:
                    self._inner = inner
                    self.calls = 0

                def iter_committed_records(self):
                    self.calls += 1
                    return self._inner.iter_committed_records()

            reader = _CountingReader(ExistingResearchStoreReader(data_root))
            detail = build_research_detail(
                ROOT,
                LifecycleEntityLocatorV1("TRIAL-FK-001", "EVIDENCE", "TRIAL"),
                research_store=reader,
                projected_at="2026-09-05T21:00:00Z",
            )
            self.assertEqual(reader.calls, 1)
            self.assertEqual(detail["fields"]["trial outcome"], "INCONCLUSIVE")
            self.assertNotEqual(detail["fields"].get("decision kind"), "PARK")
            self.assertNotIn("decision must not win trial detail", str(detail["fields"]))

    def test_lineage_does_not_mix_planes_for_same_id(self) -> None:
        git_trial = _entity(
            entity_id="TRIAL-SHARED-ID",
            projection_class="RESEARCH",
            native_kind="TRIAL",
            native_state="PASS",
            source_owner="SRC-GLOBAL-TRIAL-LEDGER",
            source_ref={"kind": "git_path", "value": "registries/global_trial_ledger.yaml"},
            truth_plane="GIT",
            contributing_source_ids=["SRC-GLOBAL-TRIAL-LEDGER"],
        )
        evidence_trial = _entity(
            entity_id="TRIAL-SHARED-ID",
            projection_class="RESEARCH",
            native_kind="TRIAL",
            native_state="INCONCLUSIVE",
            source_owner="SRC-RESEARCH-STORE",
            source_ref={"kind": "research_store", "value": "injected"},
            truth_plane="EVIDENCE",
            contributing_source_ids=["SRC-RESEARCH-STORE"],
            source_owned_fields={"trial outcome": "INCONCLUSIVE"},
        )
        projection = {
            "schema": "smial.owner-lifecycle-projection",
            "completeness": "PARTIAL",
            "sources": [],
            "entities": [git_trial, evidence_trial],
            "relations": [
                {
                    "relation_type": "REFERENCES_HYPOTHESIS_VERSION",
                    "from_entity_id": "TRIAL-SHARED-ID",
                    "to_entity_id": "HYP-GIT-ONLY",
                    "resolution": "TARGET_GAP",
                    "source_ref": {"kind": "git_path", "value": "registries/global_trial_ledger.yaml"},
                    "derivation_method": "EXPLICIT_SOURCE_FIELD",
                },
                {
                    "relation_type": "RESEARCH_TRIAL_LINK",
                    "from_entity_id": "DECISION-EVIDENCE",
                    "to_entity_id": "TRIAL-SHARED-ID",
                    "resolution": "RESOLVED",
                    "source_ref": {"kind": "research_store", "value": "injected"},
                    "derivation_method": "EXPLICIT_SOURCE_FIELD",
                },
            ],
            "gaps": [
                {
                    "gap_code": "IDENTITY_CONFLICT",
                    "affected_entity_id": "TRIAL-SHARED-ID",
                    "reason": "same id on two planes",
                    "source_ref": {"kind": "git_path", "value": "registries/global_trial_ledger.yaml"},
                    "impact": "IDENTITY_OR_STATE_CONFLICT",
                    "next_safe_action": "DO_NOT_UNIFY_ACROSS_PLANES",
                },
                {
                    "gap_code": "RELATION_TARGET_GAP",
                    "affected_entity_id": "TRIAL-SHARED-ID",
                    "reason": "target HYP-GIT-ONLY is not materialized",
                    "source_ref": {"kind": "git_path", "value": "registries/global_trial_ledger.yaml"},
                    "impact": "explicit_edge_retained_without_synthetic_target",
                    "next_safe_action": "DO_NOT_SYNTHESIZE_TARGET",
                },
            ],
        }
        git_detail = compose_research_detail(
            projection,
            LifecycleEntityLocatorV1("TRIAL-SHARED-ID", "GIT", "TRIAL"),
            root=ROOT,
        )
        evidence_detail = compose_research_detail(
            projection,
            LifecycleEntityLocatorV1("TRIAL-SHARED-ID", "EVIDENCE", "TRIAL"),
            root=ROOT,
        )
        self.assertEqual(
            [item["relation_type"] for item in git_detail["lineage"]["outbound"]],
            ["REFERENCES_HYPOTHESIS_VERSION"],
        )
        self.assertEqual(
            [item["relation_type"] for item in evidence_detail["lineage"]["inbound"]],
            ["RESEARCH_TRIAL_LINK"],
        )
        self.assertFalse(git_detail["lineage"]["inbound"])
        self.assertFalse(evidence_detail["lineage"]["outbound"])
        self.assertEqual(evidence_detail["fields"]["trial outcome"], "INCONCLUSIVE")
        self.assertTrue(
            any(item["gap_code"] == "IDENTITY_CONFLICT" for item in evidence_detail["gaps"])
        )
        self.assertFalse(
            any(item["gap_code"] == "RELATION_TARGET_GAP" for item in evidence_detail["gaps"])
        )

    def test_no_env_leak_in_durable_contract(self) -> None:
        contract = (ROOT / "docs/contracts/research_lifecycle_workbench_v1.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn(str(ROOT), contract)
        self.assertNotIn(os.path.expanduser("~"), contract)


if __name__ == "__main__":
    unittest.main()
