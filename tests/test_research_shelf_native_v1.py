"""Source-bound integration on existing synthetic native fixture writers."""
from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from solana_alpha_lab.factory import research_shelf as wire
from solana_alpha_lab.factory import research_shelf_context as context
from solana_alpha_lab.factory import research_shelf_native as native
from solana_alpha_lab.factory.research_store import ResearchStore, ExistingResearchStoreReader
from tests import test_forge_research_flow_reliability_v1 as flow
from tests import test_research_fragments_v1 as fragment_fixture

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-10-24T00:00:00Z"


def shelf_snapshot(*revisions, commit="a" * 40):
    files = {wire.revision_path(wire.decode(raw)): raw for raw in revisions}
    return dict(wire.fold(files), commit=commit, files=files)


class NativeShelfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Freeze a separate fully observed synthetic corpus before any look.
        # The flow fixture deliberately has a missing outcome; do not weaken
        # the production 1.4 readiness gate to replay that incomplete corpus.
        cls.holder = tempfile.TemporaryDirectory()
        cls.template = Path(cls.holder.name) / "template"
        table = {**flow.TABLE, "r7": ("AB", True, -.05)}
        with patch.object(flow, "TABLE", table):
            flow.create_episode_fixture(cls.template)

    tearDownClass = classmethod(flow.EpisodeFlowTests.tearDownClass.__func__)
    setUp = flow.EpisodeFlowTests.setUp
    cli = flow.EpisodeFlowTests.cli
    write = flow.EpisodeFlowTests.write
    preflight = flow.EpisodeFlowTests.preflight
    look = flow.EpisodeFlowTests.look
    authored_draft = flow.EpisodeFlowTests.authored_draft
    persist_and_freeze = flow.EpisodeFlowTests.persist_and_freeze
    seed = fragment_fixture.FragmentVerticalTests.seed
    plan = fragment_fixture.FragmentVerticalTests.plan

    def test_existing_native_candidate_link_and_metadata_only_recovery(self):
        # First an actual saved advisory prior, then capture intent BEFORE the
        # consumer draft/freeze/Critic. Shelf refs never enter scientific priors.
        self.seed()
        prior_ref = self.card["_record_id"]
        raw = wire.capture(product="SMIAL", title="Deferred native question",
            statement="Reuse the saved B-or-C advisory contrast; E1800 to E14400, execution costs UNKNOWN.", now=NOW)
        captured = wire.decode(raw)
        captured.pop("revision_sha256")
        captured["origin_refs"] = [native.record_ref(native.record_index(ExistingResearchStoreReader(self.plane))[prior_ref][0])]
        raw = wire.prepare(captured)
        from tests import test_hfic_list_aware_vertical_v1 as lav
        from tests.test_hfic_cli import critic_result_from_packet_only
        focus = "SHELF_MEASURED_PRIOR_CONSUMER"
        evidence, scope, _, initial = self.look(focus, lav.draft("LIST_CONTRAST", list_condition={"clauses": [{"all_of": ["B"]}, {"all_of": ["C"]}]}))
        draft, pre = self.authored_draft(evidence, scope, focus, preflight_receipt=initial)
        draft["candidates"][0]["claim"] += " " + wire.decode(raw)["statement"]
        draft["candidates"][0]["prior_work_refs"] = [wire.decode(raw)["origin_refs"][0]["entity_id"]]
        draft["candidates"][0]["execution_capacity_risks"] = ["UNKNOWN_EXECUTION_COSTS"]
        draft["non_claims"].append("SHELF_SOURCE_NONCLAIM_LITERAL")
        _, frozen = self.persist_and_freeze(draft, pre)
        identity = dict(session_id=frozen["session_id"], candidate_id=frozen["selected_candidate_id"], definition_sha256=frozen["selected_definition_sha256"])
        original = wire.decode(raw)
        partial = native.prepare_link(shelf_snapshot(raw), original["item_id"], original["revision_sha256"],
            store=ExistingResearchStoreReader(self.plane), identity=identity, request_id="ONE-SYNTHETIC-REQUEST",
            now=NOW, mutation_id=str(uuid4()))
        self.assertEqual(wire.decode(partial["prepared"])["native_links"][0]["verification"], "PARTIAL")
        critic = critic_result_from_packet_only(frozen["critic_input_packet"], terminal="KILL_STATISTICALLY_UNIDENTIFIABLE")
        critic["material_defects"] = ["SHELF_LITERAL_DEFECT: insufficient independent observations."]
        critic["attack_matrix"] = {"statistical_identifiability": {"verdict": "FAIL", "reason": "ONE_SYNTHETIC_DAY_IS_NOT_REPLICATION"}}
        critic["non_claims"].append("NO_STRATEGY_PROMOTION_FROM_SYNTHETIC_CRITIC")
        self.cli("finalize", "--session-id", frozen["session_id"], "--critic-result", self.write("shelf-consumer-critic.json", critic))
        reader = ExistingResearchStoreReader(self.plane)
        before = self.store.diagnostics().committed_inventory_sha256
        dossier = native.native_dossier(reader, identity)
        self.assertEqual(dossier["status"], "COMPLETE_SOURCE_TRACE", dossier)
        self.assertEqual(dossier["grounded_result_sha256"], evidence["result_sha256"])
        self.assertEqual(dossier["grounded_evidence"]["result"], dossier["grounded_result"])
        self.assertEqual(dossier["critic_terminal"], "KILL_STATISTICALLY_UNIDENTIFIABLE")
        self.assertEqual(dossier["critic_findings"]["material_defects"], critic["material_defects"])
        self.assertEqual(dossier["critic_findings"]["attack_matrix"], critic["attack_matrix"])
        self.assertEqual(dossier["source_non_claims"]["critic"], critic["non_claims"])
        self.assertTrue(any("SHELF_SOURCE_NONCLAIM_LITERAL" in source["non_claims"] for source in dossier["source_non_claims"]["drafts"]))
        self.assertIn("missing_or_forward_only_data", dossier["source_restrictions"])
        prior = next(source for cap in dossier["prior_memory"]["capsules"]
            for source in cap.get("source_detail", {}).get("research_fragments", []) if source["source_ref"] == prior_ref)
        self.assertEqual(prior["allowed_use"], "RESEARCH_ADVISORY")
        self.assertEqual(prior["evidence_blocks"][0]["exposure"], "EXPLORATORY_REUSE")
        self.assertIn("execution costs UNKNOWN", dossier["source_definition"]["claim"])
        self.assertEqual(dossier["source_restrictions"]["execution_capacity_risks"], ["UNKNOWN_EXECUTION_COSTS"])
        self.assertEqual(dossier["source_definition"]["decision_timestamp"], "E1800")
        self.assertEqual(dossier["grounded_result"]["downside"]["negative_n"], 4)
        self.assertAlmostEqual(dossier["grounded_result"]["mean_target"], -0.55 / 6, places=9)
        self.assertEqual(dossier["grounded_result"]["experiment_recipe"]["frozen_input"][0]["evidence_role"], "EXPLORATORY_REUSE")
        original = wire.decode(raw)
        snapshot = shelf_snapshot(raw, partial["prepared"], commit="e" * 40)
        request = dict(store=reader, identity=identity, request_id="ONE-SYNTHETIC-REQUEST", now=NOW, mutation_id=str(uuid4()))
        first = native.prepare_link(snapshot, original["item_id"], original["revision_sha256"], **request)
        # Simulate failure after native result: discard publication only, then
        # recover using the exact saved identities; forbid the scientific owners.
        with patch("solana_alpha_lab.factory.research_fragments.run_due", side_effect=AssertionError("No repeat science")):
            recovered = native.prepare_link(snapshot, original["item_id"], original["revision_sha256"], **request)
        self.assertEqual(first["prepared"], recovered["prepared"])
        versions = [raw, partial["prepared"], recovered["prepared"]]
        linked = shelf_snapshot(*versions, commit="b" * 40)
        self.assertEqual(native.prepare_link(linked, original["item_id"], original["revision_sha256"], **request)["status"], "ALREADY_LINKED")
        pointed = native.resolve_item(linked, original["item_id"], git_read=lambda ref: raw)
        self.assertEqual(pointed["adopted_sources"][0]["revision"]["statement"], original["statement"])
        found = native.find_native(linked, dossier["candidate_record_refs"][0])
        self.assertEqual(found["status"], "FOUND")
        self.assertEqual(len(found["matches"]), 1)
        self.assertEqual(len(found["matches"][0]["historical_relations"]), 1)
        closed = wire.revise(linked, original["item_id"], dict(state="CLOSED", closure=dict(reason="HANDED_OFF", evidence_refs=[], successor=None),
            statement="Today's wording must not replace adopted content", change_reason="Administrative handoff."), now=NOW, mutation_id=str(uuid4()))
        closed_snapshot = shelf_snapshot(*versions, closed, commit="c" * 40)
        self.assertEqual(native.resolve_item(closed_snapshot, original["item_id"], git_read=lambda ref: raw)["adopted_sources"][0]["revision"]["statement"], original["statement"])
        revoked = wire.revise(closed_snapshot, original["item_id"], dict(native_links=[], change_reason="Wrong association explicitly retracted.",
            last_decision=dict(at=NOW, disposition="RETRACT_LINK", reason="Exact synthetic correction", evidence_refs=[])), now=NOW, mutation_id=str(uuid4()))
        history = shelf_snapshot(*versions, closed, revoked, commit="d" * 40)
        self.assertEqual(native.find_native(history, dossier["candidate_record_refs"][0])["matches"][0]["status"], "RETRACTED_SOURCE_LINK")
        self.assertEqual(before, self.store.diagnostics().committed_inventory_sha256)
        # Actual success-capable public Forge read, under the same code/native
        # inputs; only the unrelated shelf metadata is changed between reads.
        from solana_alpha_lab.factory.hfic_session import load_session_bundle
        from solana_alpha_lab.factory.hfic_generation_context import collect_verified_priors, archive_fingerprint
        from solana_alpha_lab.factory.document_runner import repository_git_snapshot
        shelf_path = self.work / "shelf-snapshot.json"
        cutoff = datetime.now(UTC)
        scientific_before = (repository_git_snapshot(ROOT), archive_fingerprint(collect_verified_priors(self.store, as_of=cutoff)),
                             load_session_bundle(self.store, identity["session_id"]))
        with patch.dict(os.environ, {"SMIAL_RESEARCH_SHELF_SNAPSHOT": str(shelf_path)}):
            context.write_snapshot(shelf_path, context.export_snapshot(snapshot))
            run_before = self.cli("forge-run", "--collection", "OPPORTUNITY_EPISODES", "--owner-focus", "FRAGMENT_SYNTH_SEED", "--no-write", "--format", "json")
            context.write_snapshot(shelf_path, context.export_snapshot(closed_snapshot))
            run_after = self.cli("forge-run", "--collection", "OPPORTUNITY_EPISODES", "--owner-focus", "FRAGMENT_SYNTH_SEED", "--no-write", "--format", "json")
        self.assertEqual(run_before["receipt_sha256"], run_after["receipt_sha256"])
        self.assertEqual(run_before["next_action"], run_after["next_action"])
        self.assertNotEqual(run_before["shelf_summary"]["totals"], run_after["shelf_summary"]["totals"])
        scientific_after = (repository_git_snapshot(ROOT), archive_fingerprint(collect_verified_priors(self.store, as_of=cutoff)),
                            load_session_bundle(self.store, identity["session_id"]))
        self.assertEqual(scientific_before, scientific_after)
        self.assertEqual(before, self.store.diagnostics().committed_inventory_sha256)
        event = dict(kind="NATIVE_STATUS", source=dict(kind="NATIVE_ENTITY", owner="SMIAL", entity_kind="RESEARCH_FRAGMENT",
            entity_id=self.card["fragment_version_id"]), condition="DISABLED", acknowledged_ref=None)
        self.assertEqual(native.event_read(event, now=NOW, store=reader)["status"], "MET")
        self.assertEqual(native.event_read(event, now=NOW)["status"], "UNKNOWN")
        self._strategy_vertical(identity, evidence, dossier, raw, closed_snapshot)

    def _strategy_vertical(self, identity, evidence, dossier, raw, linked_snapshot):
        """Genuine native saved replay, then explicitly synthetic PROMOTE fixtures.

        The fixture decisions exercise transport; the native KILL is retained
        and never claimed to justify a scientific promotion or trading action.
        """
        from tests.test_hfic_temporal_production_runner_v1 import _bind_experiment
        from tests import test_science_to_strategy_handoff_v1 as handoff_fixture
        from solana_alpha_lab.factory.document_runner import DocumentRunner, RunContext
        from solana_alpha_lab.factory.operational_store import OperationalStore
        from solana_alpha_lab.factory.lane_classifier import classify_lane
        from solana_alpha_lab.factory.run_passport import experiment_spec_sha256
        from solana_alpha_lab.factory.promotion_handoff import freeze_promotion_handoff_manifest, render_strategy_version
        at = datetime.now(UTC).replace(microsecond=0) + timedelta(minutes=1)
        spec = _bind_experiment(evidence["result"]["experiment_recipe"], self.plane)
        spec.update(schema_version="1.4", population="OPPORTUNITY_EPISODES", experiment_id="EXP-SHELF-SYNTHETIC-001",
            hypothesis_version="HYP-" + identity["candidate_id"], as_of=at.isoformat().replace("+00:00", "Z"),
            availability_cutoff=at.isoformat().replace("+00:00", "Z"),
            observation_request=dict(collection_mode="REUSE_ONLY", requested_evidence_role="EXPLORATORY_REUSE"),
            required_outcomes=[dict(point_id="E14400", field_ids=["FIELD-USD-PRICE-001"], role="PRIMARY")])
        spec["parameters"]["hfic_replay_session_id"] = identity["session_id"]
        spec["data_bindings"] = [binding for binding in spec["data_bindings"] if binding["source_kind"] == "DATASET_MANIFEST"]
        spec["holdout_policy"] = "EXPLORATORY_REUSE; synthetic metadata transport fixture, no scientific promotion."
        canonical_digest = experiment_spec_sha256(spec)
        lane = classify_lane(dict(experiment_spec=spec, hypothesis_definition_sha256=identity["definition_sha256"]),
                             root=ROOT, data_root=self.plane, as_of=at)
        self.assertEqual(lane.terminal, "FAST_LANE_READY", lane.reason_codes)
        ops = OperationalStore(self.work / "replay-ops.sqlite")
        try:
            replay = DocumentRunner(root=ROOT, store=ops).start_document(spec, spec_sha256=canonical_digest,
                run_context=RunContext(self.plane, identity["definition_sha256"], lane, classifier_evaluated_at=at))
        finally:
            ops.close()
        self.assertEqual(replay["status"], "COMPLETE", replay)
        records = native.record_index(ExistingResearchStoreReader(self.plane))
        run, passport = next((r, p) for r, p in records.values() if str(getattr(r.record_kind, "value", r.record_kind)) == "RUN_COMPLETED"
                             and p.get("experiment_id") == spec["experiment_id"])
        self.assertEqual(passport["source_lineage"]["critic_result_sha256"], dossier["critic_result_sha256"])
        self.assertFalse(passport["source_lineage"]["new_scientific_look"])
        schema_root = handoff_fixture._schema_root(self.work / "strategy-reader")
        shutil.copy(ROOT / "catalog/schemas/experiment_spec_v1_4.schema.json", schema_root / "catalog/schemas/experiment_spec_v1_4.schema.json")
        spec_path = "configs/experiment_specs/shelf_synthetic.json"
        path = schema_root / spec_path
        path.parent.mkdir(parents=True)
        path.write_bytes(wire.canonical(spec) + b"\n")
        file_digest = wire.sha256(path.read_bytes())
        self.assertNotEqual(file_digest, canonical_digest)  # two distinct existing hash domains
        with patch.object(handoff_fixture, "EXPERIMENT_ID", spec["experiment_id"]), patch.object(handoff_fixture, "POPULATION_REF", spec["population"]), patch.object(handoff_fixture, "_spec_digest", return_value=file_digest):
            binding = handoff_fixture._execution_binding(cost_ref_record=run.record_id, cost_ref_digest=run.payload_sha256)
        source = dict(locator=dict(entity_id=spec["experiment_id"]), tested=dict(hypothesis_version_id=spec["hypothesis_version"], population=spec["population"]),
            experiment_spec_binding=dict(source_kind="git_path", source_value=spec_path, spec_sha256=file_digest),
            evidence_snapshot_sha256="a" * 64, direct_evidence=[dict(record_id=run.record_id, payload_sha256=run.payload_sha256)],
            obligations=[dict(code="SYNTHETIC_TRANSPORT_ONLY", status="PRESENT")])
        decisions, manifests = [], []
        for index in (1, 2):
            moment = at + timedelta(minutes=index)
            decision_id = f"DEC-SHELF-SYNTHETIC-{index:03d}"
            manifest = freeze_promotion_handoff_manifest(source, root=ROOT, decision_event_id=decision_id,
                decision_effective_at=moment.isoformat().replace("+00:00", "Z"), execution_evidence_binding=binding)
            event = handoff_fixture._event(record_id=decision_id, record_kind="DECISION_EVENT", entity_id=decision_id,
                hypothesis_version_id=spec["hypothesis_version"], transaction_id=f"RESEARCH-TXN-SHELF-STRATEGY-{index:03d}",
                payload=dict(decision_event_id=decision_id, decision_kind="PROMOTE", experiment_id=spec["experiment_id"],
                             promotion_handoff_manifest=manifest, execution_evidence_binding=binding, fixture_only=True))
            event = event.model_copy(update=dict(effective_at=moment, first_reliable_available_at=moment, created_at=moment))
            self.store.append([event], transaction_id=event.transaction_id)
            decisions.append(decision_id)
            manifests.append(manifest)
        strategy = render_strategy_version(root=ROOT, manifest=manifests[0], decision_event_id=decisions[0],
            created_at=manifests[0]["decision_effective_at"], execution_inputs=handoff_fixture.EXECUTION_INPUTS, execution_evidence_binding=binding)
        resolved = native.resolve_strategy(linked_snapshot, strategy, store=ExistingResearchStoreReader(self.plane), root=schema_root, git_read=lambda ref: raw)
        self.assertEqual(resolved["status"], "COMPLETE_SOURCE_TRACE", resolved)
        self.assertEqual(resolved["decision_ref"]["entity_id"], decisions[0])
        self.assertEqual(resolved["manifest_sha256"], manifests[0]["manifest_sha256"])
        self.assertNotEqual(resolved["manifest_sha256"], manifests[1]["manifest_sha256"])
        self.assertEqual(resolved["native"]["critic_terminal"], "KILL_STATISTICALLY_UNIDENTIFIABLE")
        self.assertEqual(resolved["native"]["critic_findings"], dossier["critic_findings"])
        self.assertEqual(resolved["native"]["source_non_claims"], dossier["source_non_claims"])
        self.assertEqual(resolved["native"]["source_restrictions"]["missing_or_forward_only_data"], dossier["source_restrictions"]["missing_or_forward_only_data"])
        self.assertEqual(resolved["shelf"]["adopted_sources"][0]["revision"]["statement"], wire.decode(raw)["statement"])
        # Matching conflict/invalid is not retraction. The actual downstream
        # consumer must refuse a unique origin even with one healthy current.
        competitor = wire.capture(product="SMIAL", title="Competing origin", statement="Separate synthetic intent", now=NOW)
        other = wire.decode(competitor)
        other_snapshot = shelf_snapshot(competitor)
        relation = copy.deepcopy(linked_snapshot["items"][wire.decode(raw)["item_id"]]["current"]["native_links"][0])
        relation.update(adoption_key="independent-competing-intent",
            adopted_item_revision=native.adopted_ref(other_snapshot, other["item_id"], other["revision_sha256"]))
        attached = wire.revise(other_snapshot, other["item_id"], dict(state="FOLLOWING", native_links=[relation],
            change_reason="Synthetic second association."), now=NOW, mutation_id=str(uuid4()))
        files = dict(linked_snapshot["files"])
        for encoded in (competitor, attached):
            files[wire.revision_path(wire.decode(encoded))] = encoded
        both = dict(wire.fold(files), files=files, commit="9" * 40)
        self.assertEqual(native.find_native(both, dossier["candidate_record_refs"][0])["status"], "AMBIGUOUS_SOURCE_LINK")
        for text in ("Administrative fork left", "Administrative fork right"):
            fork = wire.revise(both, other["item_id"], dict(statement=text, change_reason="Explicit synthetic fork."),
                now=NOW, mutation_id=str(uuid4()))
            files[wire.revision_path(wire.decode(fork))] = fork
        for invalid in (False, True):
            if invalid:
                files[f"{wire.PREFIX}/{other['item_id']}/invalid.json"] = b"{}"
            uncertain = dict(wire.fold(files), files=files, commit="9" * 40)
            refused = native.resolve_strategy(uncertain, strategy, store=ExistingResearchStoreReader(self.plane),
                root=schema_root, git_read=lambda ref: raw)
            self.assertEqual(refused["status"], "UNRESOLVED")
            self.assertIn("AMBIGUOUS_SOURCE_LINK", refused["gaps"])
        altered = copy.deepcopy(strategy)
        altered["source_decision_asset_id"] = "DEC-MISSING-EXACT"
        self.assertEqual(native.resolve_strategy(linked_snapshot, altered, store=ExistingResearchStoreReader(self.plane), root=schema_root)["status"], "UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
