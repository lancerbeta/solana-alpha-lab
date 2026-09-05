from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.application import FactoryApplication  # noqa: E402
from solana_alpha_lab.factory.lifecycle_projection import (  # noqa: E402
    build_lifecycle_projection,
    load_projection_contract,
    validate_lifecycle_projection,
)
from solana_alpha_lab.factory.operational_store import OperationalStore  # noqa: E402
from solana_alpha_lab.factory.paper_plane import (  # noqa: E402
    PaperPlaneStore,
    accept_signal_decision,
)
from solana_alpha_lab.factory.research_store import ResearchEvent, ResearchStore  # noqa: E402
from solana_alpha_lab.factory.strategy_runtime import load_strategy_version  # noqa: E402
from solana_alpha_lab.factory_semantic_operability import (  # noqa: E402
    load_semantic_catalog_views,
    load_semantic_projection,
    search_semantic_routes,
)
from validate_catalog import load_and_validate  # noqa: E402

CONTRACT = ROOT / "configs/owner_lifecycle_projection_v1.yaml"
SCHEMA = ROOT / "catalog/schemas/owner_lifecycle_projection_v1.schema.json"
HUMAN = ROOT / "docs/contracts/owner_lifecycle_projection_spine_v1.md"
WORKBENCH = ROOT / "src/solana_alpha_lab/factory/workbench.py"
NEGATIVE_ID = "NEGATIVE-T30-CURRENT-DATA-ROUTE-001"
EXPERIMENT_ID = "EXP-ORDINARY-PRICE-PATH-HYPOTHESIS-001"
HYPOTHESIS_ID = "HYP-ORDINARY-PRICE-PATH-BUY-PRESSURE-V1"
STRATEGY_ENTITY = "STRAT-V-EARLY-LIQ-FLOOR@V1"
NOW = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
LEGACY_STRAT = "configs/strategies/STRAT-V-EARLY-LIQ-FLOOR-COMMISSIONING-V1.yaml"
V11_STRAT = "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml"
SIGNAL_DECISION = (
    ROOT / "tests/fixtures/factory_strategy_execution_boundary/signal_decision_enter_a.json"
)
EMPTY_REGISTRIES = (
    "registries/hypotheses.yaml",
    "registries/research_cycles.yaml",
    "registries/strategies.yaml",
    "registries/bot_instances.yaml",
)


def _event(
    *,
    record_id: str,
    record_kind: str,
    entity_id: str,
    payload: dict,
    hypothesis_version_id: str | None = None,
    run_id: str | None = None,
    transaction_id: str = "RESEARCH-TXN-LIFECYCLE-001",
) -> ResearchEvent:
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return ResearchEvent(
        record_id=record_id,
        record_kind=record_kind,
        entity_id=entity_id,
        hypothesis_version_id=hypothesis_version_id,
        run_id=run_id,
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


def _ids(projection: dict, *, native_kind: str | None = None) -> set[str]:
    return {
        item["entity_id"]
        for item in projection["entities"]
        if native_kind is None or item["native_kind"] == native_kind
    }


def _relations(projection: dict, relation_type: str) -> list[dict]:
    return [item for item in projection["relations"] if item["relation_type"] == relation_type]


def _source(projection: dict, source_id: str) -> dict:
    return next(item for item in projection["sources"] if item["source_id"] == source_id)


class OwnerLifecycleProjectionSpineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_projection_contract(ROOT)
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        cls.projection = build_lifecycle_projection(ROOT, projected_at="2026-09-05T17:00:00Z")

    def test_contract_and_schema_forbid_authority_and_inference(self) -> None:
        Draft202012Validator(self.schema).validate(self.contract)
        self.assertIs(self.contract["authority_granted"], False)
        self.assertFalse(self.contract["owns_source_truth"])
        self.assertFalse(self.contract["persist_projection"])
        self.assertIs(self.contract["resolved_requires_unambiguous_endpoint_identity"], True)
        self.assertIn("INFERRED_BY_NAME", self.contract["forbidden_derivation_methods"])
        invalid = copy.deepcopy(self.projection)
        invalid["authority_granted"] = True
        with self.assertRaises(ValidationError):
            Draft202012Validator(self.schema).validate(invalid)
        bad_relation = copy.deepcopy(self.projection)
        bad_relation["relations"] = [
            {
                "relation_type": "GUESSED",
                "from_entity_id": "A",
                "to_entity_id": "B",
                "resolution": "RESOLVED",
                "source_ref": {"kind": "git_path", "value": "x"},
                "derivation_method": "INFERRED_BY_NAME",
            }
        ]
        with self.assertRaises((ValidationError, ValueError)):
            validate_lifecycle_projection(bad_relation, root=ROOT)
        bad_status = copy.deepcopy(self.projection)
        bad_status["sources"][0]["status"] = "HEALTHY"
        with self.assertRaises(ValidationError):
            Draft202012Validator(self.schema).validate(bad_status)

    def test_human_companion_names_current_owners_and_future_move(self) -> None:
        text = HUMAN.read_text(encoding="utf-8")
        self.assertIn("LifecycleProjectionV1", text)
        self.assertIn("authority_granted = false", text)
        self.assertIn("TARGET_GAP", text)
        self.assertIn("RESOLVED = endpoint identity unambiguous in current projection", text)
        self.assertIn("RESEARCH_LIFECYCLE_WORKBENCH_V1", text)
        self.assertIn("EMPTY envelope", text)
        self.assertIn("`INFERRED_BY_NAME`", text)
        self.assertIn("Do not auto-start Move 1", text)

    def test_case_a_negative_result_without_invented_hypothesis(self) -> None:
        self.assertIn(NEGATIVE_ID, _ids(self.projection, native_kind="NEGATIVE_RESULT"))
        entity = next(item for item in self.projection["entities"] if item["entity_id"] == NEGATIVE_ID)
        self.assertEqual(entity["source_ref"]["value"], "registries/decisions_negative_results.yaml")
        self.assertEqual(entity["truth_plane"], "GIT")
        self.assertTrue(entity["summary"])
        invented = [
            item
            for item in self.projection["relations"]
            if item["from_entity_id"] == NEGATIVE_ID
            and item["relation_type"] == "REFERENCES_HYPOTHESIS_VERSION"
        ]
        self.assertEqual(invented, [])

    def test_case_b_experiment_spec_explicit_hypothesis_target_gap(self) -> None:
        self.assertIn(EXPERIMENT_ID, _ids(self.projection, native_kind="EXPERIMENT_SPEC"))
        edges = [
            item
            for item in _relations(self.projection, "REFERENCES_HYPOTHESIS_VERSION")
            if item["from_entity_id"] == EXPERIMENT_ID
        ]
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["to_entity_id"], HYPOTHESIS_ID)
        self.assertEqual(edges[0]["derivation_method"], "EXPLICIT_SOURCE_FIELD")
        self.assertEqual(edges[0]["resolution"], "TARGET_GAP")
        self.assertNotIn(HYPOTHESIS_ID, _ids(self.projection))
        filename_guess = [
            item
            for item in self.projection["relations"]
            if "ordinary_price_path" in item["from_entity_id"].lower()
            or "ordinary_price_path" in item["to_entity_id"].lower()
        ]
        self.assertEqual(filename_guess, [])

    def test_case_c_strategy_version_provenance_without_registry_backfill(self) -> None:
        self.assertIn(STRATEGY_ENTITY, _ids(self.projection, native_kind="STRATEGY_VERSION"))
        hyp_edges = [
            item
            for item in _relations(self.projection, "REFERENCES_HYPOTHESIS_VERSION")
            if item["from_entity_id"] == STRATEGY_ENTITY
        ]
        self.assertEqual(hyp_edges[0]["to_entity_id"], "HYP-EARLY-STATE-LIQ-FLOOR-V1")
        self.assertEqual(hyp_edges[0]["resolution"], "TARGET_GAP")
        decision_edges = [
            item
            for item in _relations(self.projection, "REFERENCES_DECISION_ASSET")
            if item["from_entity_id"] == STRATEGY_ENTITY
        ]
        self.assertEqual(
            decision_edges[0]["to_entity_id"],
            "EVIDENCE-EARLY-STATE-PAPER-RUNTIME-001",
        )
        strategies = yaml.safe_load((ROOT / "registries/strategies.yaml").read_text(encoding="utf-8"))
        self.assertEqual(strategies.get("records") or [], [])

    def test_legacy_registries_remain_empty_and_are_not_complete_truth(self) -> None:
        for relative in EMPTY_REGISTRIES:
            doc = yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
            self.assertEqual(doc.get("records") or [], [])
        empty_sources = [
            item
            for item in self.projection["sources"]
            if str(item["source_id"]).startswith("SRC-LEGACY-")
        ]
        self.assertEqual({item["status"] for item in empty_sources}, {"EMPTY"})
        self.assertGreater(len(_ids(self.projection, native_kind="EXPERIMENT_SPEC")), 0)
        self.assertGreater(len(_ids(self.projection, native_kind="STRATEGY_VERSION")), 0)
        self.assertGreater(len(_ids(self.projection, native_kind="NEGATIVE_RESULT")), 0)
        self.assertEqual(self.projection["completeness"], "PARTIAL")
        self.assertIs(self.projection["authority_granted"], False)

    def test_missing_runtime_is_not_present_not_empty_healthy(self) -> None:
        paper = _source(self.projection, "SRC-PAPER-PLANE")
        research = _source(self.projection, "SRC-RESEARCH-STORE")
        paper_path = ROOT / "local/factory_v1/paper_plane_state.sqlite"
        if paper_path.is_file():
            self.assertIn(paper["status"], {"AVAILABLE", "EMPTY"})
        else:
            self.assertEqual(paper["status"], "NOT_PRESENT")
            self.assertTrue(
                any(
                    item["gap_code"] == "SOURCE_NOT_PRESENT"
                    and item.get("source_id") == "SRC-PAPER-PLANE"
                    for item in self.projection["gaps"]
                )
            )
        self.assertEqual(research["status"], "NOT_PRESENT")

    def test_case_d_paper_runtime_lineage_from_foreign_keys(self) -> None:
        strategy = load_strategy_version(ROOT, LEGACY_STRAT)
        v11 = load_strategy_version(ROOT, V11_STRAT)
        decision = json.loads(SIGNAL_DECISION.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                bot = store.start_bot(strategy, mode="PAPER")
                position_id = store.open_position(
                    bot_instance_id=bot["bot_instance_id"],
                    mint="So11111111111111111111111111111111111111112",
                    signal_kind="SIMULATED_FILL",
                )
                store.fill_paper(
                    bot_instance_id=bot["bot_instance_id"],
                    mint="So11111111111111111111111111111111111111112",
                    notional_usd=Decimal("100"),
                )
                accept_signal_decision(
                    ROOT,
                    store,
                    strategy=v11,
                    signal_decision=decision,
                    known_activation_epochs={"ACTIVATION-EPOCH-BOUNDARY-PAPER-001": {"mode": "PAPER"}},
                )
                projection = build_lifecycle_projection(
                    ROOT,
                    paper_plane_store=store,
                    projected_at="2026-09-05T17:00:00Z",
                )
            finally:
                store.close()
        self.assertIn(bot["bot_instance_id"], _ids(projection, native_kind="BOT_INSTANCE"))
        self.assertIn(position_id, _ids(projection, native_kind="POSITION"))
        bot_strategy = [
            item
            for item in _relations(projection, "IMPLEMENTS_STRATEGY_VERSION")
            if item["from_entity_id"] == bot["bot_instance_id"]
        ]
        self.assertEqual(bot_strategy[0]["to_entity_id"], STRATEGY_ENTITY)
        self.assertEqual(bot_strategy[0]["resolution"], "RESOLVED")
        self.assertEqual(bot_strategy[0]["derivation_method"], "EXPLICIT_CONTRACT_KEY")
        owned = [
            item
            for item in _relations(projection, "POSITION_OWNED_BY_BOT")
            if item["from_entity_id"] == position_id
        ]
        self.assertEqual(owned[0]["to_entity_id"], bot["bot_instance_id"])
        self.assertEqual(owned[0]["resolution"], "RESOLVED")
        signal_edges = _relations(projection, "FROM_SIGNAL_DECISION")
        self.assertTrue(signal_edges)
        self.assertEqual(signal_edges[0]["derivation_method"], "EXPLICIT_FOREIGN_KEY")
        self.assertEqual(signal_edges[0]["resolution"], "TARGET_GAP")
        epoch_edges = _relations(projection, "HAS_ACTIVATION_EPOCH")
        self.assertTrue(epoch_edges)
        self.assertEqual(epoch_edges[0]["to_entity_id"], "ACTIVATION-EPOCH-BOUNDARY-PAPER-001")
        self.assertEqual(epoch_edges[0]["resolution"], "TARGET_GAP")
        paper = next(
            item
            for item in projection["sources"]
            if item["source_id"] == "SRC-PAPER-PLANE"
        )
        self.assertEqual(paper["status"], "AVAILABLE")
        self.assertEqual(paper["source_ref"], {"kind": "injected", "value": "PaperPlaneStore"})

    def test_case_e_research_store_explicit_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ResearchStore(data_root)
            store.append(
                [
                    _event(
                        record_id="HYP-EVENT-LIFECYCLE-001",
                        record_kind="HYPOTHESIS_VERSION",
                        entity_id="HYP-LIFECYCLE-FIXTURE-V1",
                        hypothesis_version_id="HYP-LIFECYCLE-FIXTURE-V1",
                        payload={"hypothesis_version_id": "HYP-LIFECYCLE-FIXTURE-V1", "claim": "fixture"},
                    )
                ],
                transaction_id="RESEARCH-TXN-LIFECYCLE-001",
            )
            store.append(
                [
                    _event(
                        record_id="TRIAL-EVENT-LIFECYCLE-001",
                        record_kind="TRIAL",
                        entity_id="TRIAL-LIFECYCLE-001",
                        hypothesis_version_id="HYP-LIFECYCLE-FIXTURE-V1",
                        payload={"trial_id": "TRIAL-LIFECYCLE-001", "status": "COMPLETED"},
                        transaction_id="RESEARCH-TXN-LIFECYCLE-002",
                    )
                ],
                transaction_id="RESEARCH-TXN-LIFECYCLE-002",
            )
            store.append(
                [
                    _event(
                        record_id="DECISION-EVENT-LIFECYCLE-001",
                        record_kind="DECISION_EVENT",
                        entity_id="DECISION-EVENT-LIFECYCLE-001",
                        hypothesis_version_id="HYP-LIFECYCLE-FIXTURE-V1",
                        payload={
                            "decision_event_id": "DECISION-EVENT-LIFECYCLE-001",
                            "trial_id": "TRIAL-LIFECYCLE-001",
                            "status": "RECORDED",
                        },
                        transaction_id="RESEARCH-TXN-LIFECYCLE-003",
                    )
                ],
                transaction_id="RESEARCH-TXN-LIFECYCLE-003",
            )
            projection = build_lifecycle_projection(
                ROOT,
                research_store=store,
                projected_at="2026-09-05T17:00:00Z",
            )
        self.assertIn("HYP-LIFECYCLE-FIXTURE-V1", _ids(projection, native_kind="HYPOTHESIS_VERSION"))
        self.assertIn("TRIAL-LIFECYCLE-001", _ids(projection, native_kind="TRIAL"))
        self.assertIn("DECISION-EVENT-LIFECYCLE-001", _ids(projection, native_kind="DECISION_EVENT"))
        trial_link = [
            item
            for item in _relations(projection, "RESEARCH_HYPOTHESIS_LINK")
            if item["from_entity_id"] == "TRIAL-LIFECYCLE-001"
        ]
        self.assertEqual(trial_link[0]["to_entity_id"], "HYP-LIFECYCLE-FIXTURE-V1")
        self.assertEqual(trial_link[0]["resolution"], "RESOLVED")
        decision_trial = [
            item
            for item in _relations(projection, "RESEARCH_TRIAL_LINK")
            if item["from_entity_id"] == "DECISION-EVENT-LIFECYCLE-001"
        ]
        self.assertEqual(decision_trial[0]["to_entity_id"], "TRIAL-LIFECYCLE-001")
        self.assertEqual(decision_trial[0]["resolution"], "RESOLVED")

    def test_conflicting_state_does_not_use_timestamp_winner(self) -> None:
        projection = copy.deepcopy(self.projection)
        entity = next(item for item in projection["entities"] if item["entity_id"] == EXPERIMENT_ID)
        clone = copy.deepcopy(entity)
        clone["native_state"] = "OTHER_STATE"
        clone["contributing_source_ids"] = ["SRC-CONFLICT"]
        projection["entities"].append(clone)
        # Re-run merge by building with a monkeypatched second spec is heavy; assert helper semantics via rebuild path.
        from solana_alpha_lab.factory.lifecycle_projection import _merge_entities

        merged, gaps = _merge_entities([entity, clone])
        self.assertEqual(merged[0]["display_state"], "CONFLICT")
        self.assertEqual(merged[0]["state_derivation"], "UNKNOWN")
        self.assertIsNone(merged[0]["native_state"])
        self.assertTrue(any(item["gap_code"] == "STATE_CONFLICT" for item in gaps))

    def test_application_api_independent_of_selected_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ops = OperationalStore(Path(tmp) / "ops.sqlite")
            try:
                app = FactoryApplication(
                    root=ROOT,
                    store=ops,
                    spec_relative="configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml",
                )
                projection = app.lifecycle_projection()
                model = app.read_model()
            finally:
                ops._conn.close()
        self.assertEqual(projection["schema"], "smial.owner-lifecycle-projection")
        self.assertIn(EXPERIMENT_ID, _ids(projection))
        self.assertIn(STRATEGY_ENTITY, _ids(projection))
        self.assertNotEqual(projection.get("entities"), model.get("entities", None))
        self.assertIn(NEGATIVE_ID, _ids(projection))

    def test_application_lifecycle_projection_does_not_open_runtime_stores(self) -> None:
        app = FactoryApplication(
            root=ROOT,
            spec_relative="configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml",
        )
        projection = app.lifecycle_projection()
        self.assertIsNone(app._operational_store)
        self.assertIsNone(app._paper_plane_store)
        self.assertIsNone(app._runner)
        self.assertEqual(projection["schema"], "smial.owner-lifecycle-projection")

    def test_cross_plane_same_id_is_not_unified(self) -> None:
        from solana_alpha_lab.factory.lifecycle_projection import _entity, _merge_entities

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
            evidence_class="MODEL",
        )
        merged, gaps = _merge_entities([runtime, evidence])
        self.assertEqual(len(merged), 2)
        self.assertEqual({item["truth_plane"] for item in merged}, {"RUNTIME", "EVIDENCE"})
        self.assertTrue(any(item["gap_code"] == "IDENTITY_CONFLICT" for item in gaps))

    def test_ambiguous_cross_plane_endpoint_is_conflict_not_resolved(self) -> None:
        from solana_alpha_lab.factory.lifecycle_projection import (
            _entity,
            _entity_id_planes,
            _finalize_relations,
            _merge_entities,
            _relation,
        )

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
            evidence_class="MODEL",
        )
        origin = _entity(
            entity_id="EXP-UNAMBIGUOUS",
            projection_class="EXPERIMENT",
            native_kind="EXPERIMENT_SPEC",
            native_state="READY",
            source_owner="SRC-EXPERIMENT-SPEC",
            source_ref={"kind": "git_path", "value": "configs/experiment_specs/unambiguous.yaml"},
            truth_plane="GIT",
            contributing_source_ids=["SRC-EXPERIMENT-SPEC"],
        )
        merged, gaps = _merge_entities([runtime, evidence, origin])
        self.assertEqual(sum(1 for item in merged if item["entity_id"] == "JOB-SHARED-ID"), 2)
        self.assertEqual(
            {item["truth_plane"] for item in merged if item["entity_id"] == "JOB-SHARED-ID"},
            {"RUNTIME", "EVIDENCE"},
        )
        self.assertTrue(any(item["gap_code"] == "IDENTITY_CONFLICT" for item in gaps))
        preliminary = _relation(
            relation_type="JOB_FOR_EXPERIMENT",
            from_entity_id="EXP-UNAMBIGUOUS",
            to_entity_id="JOB-SHARED-ID",
            source_ref={"kind": "git_path", "value": "configs/experiment_specs/unambiguous.yaml"},
            derivation_method="EXPLICIT_CONTRACT_KEY",
            known_ids={"JOB-SHARED-ID", "EXP-UNAMBIGUOUS"},
        )
        self.assertEqual(preliminary["resolution"], "RESOLVED")
        finalized, relation_gaps = _finalize_relations([preliminary], _entity_id_planes(merged))
        self.assertEqual(len(finalized), 1)
        self.assertNotEqual(finalized[0]["resolution"], "RESOLVED")
        self.assertEqual(finalized[0]["resolution"], "CONFLICT")
        self.assertTrue(
            any(
                item["gap_code"] == "IDENTITY_CONFLICT"
                and item.get("relation_type") == "JOB_FOR_EXPERIMENT"
                for item in relation_gaps
            )
        )
        self.assertTrue(any(item["gap_code"] == "IDENTITY_CONFLICT" for item in gaps))

    def test_execution_event_without_id_is_gap_not_synthetic(self) -> None:
        class _FakePaper:
            def bots(self) -> list[dict]:
                return []

            def positions(self) -> list[dict]:
                return []

            def execution_events(self) -> list[dict]:
                return [{"event_type": "FILL", "bot_instance_id": "BOT-X", "created_at": "t"}]

        projection = build_lifecycle_projection(
            ROOT,
            paper_plane_store=_FakePaper(),  # type: ignore[arg-type]
            projected_at="2026-09-05T17:00:00Z",
        )
        self.assertNotIn("EXEC-EVENT-0000", _ids(projection))
        self.assertFalse(_ids(projection, native_kind="EXECUTION_EVENT"))
        self.assertTrue(
            any(item["gap_code"] == "MISSING_STABLE_ID" for item in projection["gaps"])
        )

    def test_global_trial_ledger_preserves_native_outcome(self) -> None:
        self.assertIn(
            "TRIAL-RC002-H11-NEXT-GTA-TARGET-001",
            _ids(self.projection, native_kind="TRIAL"),
        )
        entity = next(
            item
            for item in self.projection["entities"]
            if item["entity_id"] == "TRIAL-RC002-H11-NEXT-GTA-TARGET-001"
        )
        self.assertEqual(entity["truth_plane"], "GIT")
        self.assertEqual(entity["native_state"], "RECORDED")
        self.assertIn("outcome=PASS", entity["summary"] or "")
        self.assertNotIn("POSITIVE", entity["summary"] or "")
        hyp = [
            item
            for item in _relations(self.projection, "REFERENCES_HYPOTHESIS_VERSION")
            if item["from_entity_id"] == "TRIAL-RC002-H11-NEXT-GTA-TARGET-001"
        ]
        self.assertEqual(hyp[0]["to_entity_id"], "HYP-RC002-H11-LIFECYCLE-CLOCK-V1")
        self.assertEqual(hyp[0]["resolution"], "TARGET_GAP")
        self.assertNotIn("HYP-RC002-H11-LIFECYCLE-CLOCK-V1", _ids(self.projection))

    def test_workbench_does_not_own_lifecycle_joins(self) -> None:
        text = WORKBENCH.read_text(encoding="utf-8")
        self.assertNotIn("INFERRED_BY_NAME", text)
        self.assertIn("research_overview", text)

    def test_catalog_binding_and_semantic_route(self) -> None:
        snapshot = load_and_validate(allow_generated_drift=True)
        semantic = load_semantic_projection(ROOT)
        assets, bindings, _queries = load_semantic_catalog_views(ROOT)
        self.assertIn("ACTIVE-OWNER-LIFECYCLE-PROJECTION", bindings)
        self.assertEqual(
            bindings["ACTIVE-OWNER-LIFECYCLE-PROJECTION"]["target_asset_id"],
            "CONFIG-OWNER-LIFECYCLE-PROJECTION-001",
        )
        self.assertLessEqual(len(bindings), 12)
        self.assertIn("CONFIG-OWNER-LIFECYCLE-PROJECTION-001", snapshot.assets)
        positives = [
            "What lifecycle objects currently exist?",
            "How are hypothesis, experiment, strategy and position connected?",
            "Where is lifecycle truth?",
            "Show the research-to-execution lineage.",
            "What is linked to this StrategyVersion?",
            "What is the owner lifecycle projection?",
            "какие lifecycle-объекты сейчас существуют?",
            "как связаны гипотеза эксперимент стратегия и позиция?",
            "где смотреть research → execution lineage?",
            "где каноническая карта lifecycle?",
        ]
        for query in positives:
            hits = search_semantic_routes(
                semantic,
                query,
                assets=assets,
                bindings=bindings,
                limit=5,
            )
            self.assertTrue(hits, query)
            self.assertEqual(hits[0]["semantic_route_id"], "SEM-OWNER-LIFECYCLE", query)
            self.assertIs(hits[0]["authority_granted"], False)
        anti = [
            ("Is the VPS healthy?", "SEM-REMOTE-OPS-RECOVERY"),
            ("What provider route exists?", "SEM-PROVIDER-ROUTES"),
            ("How do I design the UI?", "SEM-VISUAL-OPERATING-SYSTEM"),
            ("How do I generate a hypothesis?", "SEM-HYPOTHESIS-FORGE"),
            ("Am I authorized to deploy?", "SEM-AUTHORITY-BOUNDARIES"),
        ]
        for query, expected in anti:
            hits = search_semantic_routes(
                semantic,
                query,
                assets=assets,
                bindings=bindings,
                limit=5,
            )
            self.assertTrue(hits, query)
            self.assertEqual(hits[0]["semantic_route_id"], expected, query)

    def test_deterministic_sort(self) -> None:
        again = build_lifecycle_projection(ROOT, projected_at="2026-09-05T17:00:00Z")
        self.assertEqual(self.projection["entities"], again["entities"])
        self.assertEqual(self.projection["relations"], again["relations"])
        self.assertEqual(self.projection["gaps"], again["gaps"])
        classes = [
            (item["projection_class"], item["native_kind"], item["entity_id"])
            for item in self.projection["entities"]
        ]
        self.assertEqual(classes, sorted(classes))


if __name__ == "__main__":
    unittest.main()
