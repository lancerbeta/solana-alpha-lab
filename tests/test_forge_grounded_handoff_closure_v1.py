"""Fresh transport invariants; scientific relations and old readers stay distinct."""
from __future__ import annotations

import copy
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from solana_alpha_lab.factory import hfic_grounded_discovery as gd
from solana_alpha_lab.factory import hfic_research_scope as rs
from solana_alpha_lab.factory import hfic_session as session
from solana_alpha_lab.factory.hfic_identity import candidate_identity

SCOPE = {
    "population": "OPPORTUNITY_EPISODES",
    "decision_timestamp": "E1800",
    "target": "PRICE_RELATIVE_PROXY:E1800:E14400:FIELD-USD-PRICE-001",
    "estimand": "price_relative_proxy",
    "explanatory_condition": "LIST_CONTRAST",
}


def card():
    template = json.loads((ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text())
    return {**template["candidates"][0], **SCOPE, "claim_form": "PREDICTIVE"}


class FreshCardTests(unittest.TestCase):
    def test_zero_candidate_and_unselected_unmeasured_portfolios_have_no_selected_ref(self):
        for candidates in ([], [{"population": "BASE_X", "decision_timestamp": "Y3600"}]):
            session._validate_fresh_draft_scopes({"candidates": candidates}, store=None, identities=[])

    def test_public_example_uses_fresh_semantic_guard_and_actual_schema(self):
        from jsonschema import Draft202012Validator

        example = json.loads((ROOT / "tests/fixtures/forge_grounded_handoff_closure_v1/flat_card.json").read_text())
        schema = json.loads((ROOT / "catalog/schemas/hypothesis_forge_draft_v1_2.schema.json").read_text())
        Draft202012Validator(schema["properties"]["candidates"]["items"]).validate(example)
        gd.validate_fresh_card_scope(example, look_scope=gd.card_claim_scope(example), require_look_axes=True)

    def test_nested_only_is_typed_refusal_and_literal_placement_preserves_identity(self):
        malformed = card()
        malformed["candidate_scope"] = dict(SCOPE)
        for key in ("target", "explanatory_condition"):
            del malformed[key]
        with self.assertRaises(gd.GroundedDiscoveryError) as caught:
            gd.validate_fresh_card_scope(malformed, look_scope=SCOPE, require_look_axes=True)
        self.assertEqual(caught.exception.code, "CANDIDATE_SCOPE_FIELDS_REQUIRED")
        self.assertEqual(caught.exception.detail["missing_top_level"], ["target", "explanatory_condition"])
        fixed = copy.deepcopy(malformed)
        for key in caught.exception.detail["missing_top_level"]:
            fixed[key] = malformed["candidate_scope"][key]
        self.assertEqual(candidate_identity(malformed).full_sha256, candidate_identity(fixed).full_sha256)
        self.assertEqual(gd.validate_fresh_card_scope(fixed, look_scope=SCOPE, require_look_axes=True), SCOPE)

    def test_conflict_and_malformed_runner_scope_never_silently_fall_back(self):
        for nested, code in (({**SCOPE, "target": "other"}, "CANDIDATE_SCOPE_FIELDS_CONFLICT"),
                             ([], "CANDIDATE_SCOPE_INVALID"),
                             ({"target": 7}, "CANDIDATE_SCOPE_INVALID")):
            with self.subTest(nested=nested), self.assertRaises(gd.GroundedDiscoveryError) as caught:
                gd.validate_fresh_card_scope({**card(), "candidate_scope": nested})
            self.assertEqual(caught.exception.code, code)

    def test_required_bound_representation_and_list_axes_are_explicit(self):
        look = {**SCOPE, "representation_scope": "BASE", "research_scope_rule_sha256": "a" * 64}
        with self.assertRaises(gd.GroundedDiscoveryError) as caught:
            gd.validate_fresh_card_scope(card(), look_scope=look, require_look_axes=True)
        self.assertEqual(caught.exception.detail["missing_top_level"],
                         ["representation_scope", "research_scope_rule_sha256", "research_scope_statement"])

    def test_invalid_scope_types_name_exact_fields_and_recovery(self):
        cases = (({"candidate_scope": []}, ["candidate_scope"], "object"),
                 ({"candidate_scope": {"target": 7}}, ["candidate_scope.target"], "non_empty_string"),
                 ({"target": 7}, ["target"], "non_empty_string"))
        for extra, fields, expected in cases:
            with self.subTest(fields=fields), self.assertRaises(gd.GroundedDiscoveryError) as caught:
                gd.validate_fresh_card_scope({**card(), **extra})
            self.assertEqual(caught.exception.detail["invalid_fields"], fields)
            self.assertEqual(caught.exception.detail["expected_type"], expected)
            self.assertEqual(caught.exception.detail["next_action"], "CORRECT_DECLARED_FIELD_TYPES_REUSE_SAVED_LOOK")

    def test_already_detached_runner_keeps_original_contextual_refs(self):
        packet = {"grounded_evidence": {"candidate_scope": SCOPE,
                  "look_confirms_selected": False, "look_context_result_refs": ["HFIC-LOOK-ORIGINAL"]}}
        session._rebind_runner_up_grounded_evidence(packet, {**card(), "target": "other"})
        self.assertEqual(packet["grounded_evidence"]["look_context_result_refs"], ["HFIC-LOOK-ORIGINAL"])
        self.assertFalse(packet["grounded_evidence"]["look_confirms_selected"])

    def test_complete_but_narrower_claim_and_unmeasured_idea_remain_distinct(self):
        narrower = {**card(), "target": "different-supported-target"}
        gd.validate_fresh_card_scope(narrower, look_scope=SCOPE, require_look_axes=True)
        self.assertEqual(gd.relate_look_scope(SCOPE, gd.card_claim_scope(narrower)), "LOOK_SCOPE_NARROWER")
        idea = {"population": "OPPORTUNITY_EPISODES", "claim_form": "CAUSAL"}
        self.assertEqual(gd.validate_fresh_card_scope(idea), gd.card_claim_scope(idea))
        # Historical extraction stays a pure reader, never a fresh guard/migration.
        self.assertEqual(gd.card_claim_scope({"candidate_scope": SCOPE}), {})

    def test_selected_projection_keeps_scope_and_predictive_form(self):
        authored = card()
        identity = candidate_identity(authored)
        block = session._selected_candidate_block(identity, authored, packet_version="1.3")
        for key, value in SCOPE.items():
            self.assertEqual(block[key], value)
        self.assertEqual(block["claim_form"], "PREDICTIVE")

    def test_critic_binding_transport_preserves_typed_sources_losslessly(self):
        from jsonschema import Draft202012Validator

        typed = {"dataset_manifest_id": "dataset-source", "observations_sha256": "a" * 64,
                 "nested": {"coverage": ["OBSERVED", None], "label": "источник"}}
        authored = {**card(), "available_data_bindings": ["legacy narrative", typed]}
        before = copy.deepcopy(authored)
        identity = candidate_identity(authored)
        block = session._selected_candidate_block(identity, authored, packet_version="1.3")
        schema = json.loads((ROOT / "catalog/schemas/hypothesis_critic_input_v1.schema.json").read_text())
        binding_schema = schema["properties"]["selected_candidate"]["properties"]["available_data_bindings"]
        errors = list(Draft202012Validator(binding_schema).iter_errors(block["available_data_bindings"]))
        self.assertEqual([error.validator for error in errors], [])
        self.assertEqual(block["available_data_bindings"][0], "legacy narrative")
        self.assertEqual(json.loads(block["available_data_bindings"][1]), typed)
        self.assertEqual(authored, before)
        self.assertEqual(candidate_identity(authored).full_sha256, identity.full_sha256)

    def test_critic_binding_transport_keeps_malformed_outer_shape_invalid(self):
        for malformed in ("not-an-array", {"dataset_manifest_id": "not-an-array"}, [42]):
            with self.subTest(malformed=malformed):
                authored = {**card(), "available_data_bindings": malformed}
                block = session._selected_candidate_block(candidate_identity(authored), authored)
                self.assertEqual(block["available_data_bindings"], malformed)

    def test_runner_up_own_scope_does_not_inherit_foreign_list_evidence(self):
        primary_scope = {**SCOPE, "research_scope_rule_sha256": "a" * 64,
                         "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1"}
        runner = {**card(), "research_scope_rule_sha256": "b" * 64,
                  "research_scope_statement": "different rule", "evidence_surface_mode": primary_scope["evidence_surface_mode"]}
        packet = {"grounded_evidence": {"candidate_scope": primary_scope, "result": {"n": 3},
                                       "result_sha256": "c" * 64, "result_refs": ["primary-result"],
                                       "look_confirms_selected": True, "look_scope_relation": "LOOK_SCOPE_MATCH"}}
        session._rebind_runner_up_grounded_evidence(packet, runner)
        evidence = packet["grounded_evidence"]
        self.assertNotIn("result", evidence)
        self.assertNotIn("result_refs", evidence)
        self.assertEqual(evidence["candidate_scope"]["research_scope_rule_sha256"], "b" * 64)
        self.assertFalse(evidence["look_confirms_selected"])
        self.assertEqual(evidence["look_scope_relation"], "LOOK_SCOPE_NARROWER")
        self.assertEqual(evidence["look_context_result_refs"], ["primary-result"])
        self.assertTrue(session._foreign_look_blocks_scientific_terminal(
            {"critic_input_packet": packet}, {}))


class CanonicalIngressTests(unittest.TestCase):
    def setUp(self):
        self.evidence = rs.MembershipEvidence()
        for letter in "ABC":
            self.evidence.definitions[f"L:{letter}"] = {
                "definition_sha256": letter.lower() * 64, "aliases": [letter],
            }
        self.raw = {
            "hypothesis_kind": "LIST_CONTRAST",
            "research_scope": {"universe_selector": {"clauses": [{"any_of": ["A", "B"]}]}},
            "list_condition": {"clauses": [{"all_of": ["A"], "none_of": ["C"]}]},
            "diagnostic_slices": [{"slice_id": "known-tautology", "selector": {
                "clauses": [{"count": {"of": ["A", "C"], "min": 0, "max": 2}}],
            }}],
        }

    def test_full_nested_closure_round_trips_and_keeps_coverage(self):
        canonical = rs.canonicalize_query_scope(self.raw, self.evidence)
        again = rs.canonicalize_query_scope(canonical, self.evidence)
        self.assertEqual(canonical, again)
        self.assertEqual(rs.rule_sha256_of_body(canonical), rs.rule_sha256_of_body(again))
        selector = again["diagnostic_slices"][0]["selector"]
        self.assertEqual(selector["required_observed_lists"], ["L:A", "L:C"])
        self.assertEqual(rs.evaluate_selector(selector, {"L:A": rs.TRUE}), rs.UNKNOWN)

    def test_each_reserved_pin_refuses_tampering_and_partial_canonical_never_raw_falls_back(self):
        canonical = rs.canonicalize_query_scope(self.raw, self.evidence)
        for location in ("scope", "condition", "slice"):
            for mutation in ("hash", "coverage", "missing-pin"):
                altered = copy.deepcopy(canonical)
                selected = altered["research_scope"] if location == "scope" else (
                    altered["list_condition"] if location == "condition" else altered["diagnostic_slices"][0]["selector"])
                selector = selected["universe_selector"] if location == "scope" else selected
                if mutation == "hash":
                    selected["definition_refs"][next(iter(selected["definition_refs"]))] = "0" * 64
                elif mutation == "coverage":
                    selector["required_observed_lists"] = []
                else:
                    del selected["definition_refs"]
                with self.subTest(location=location, mutation=mutation), self.assertRaises(rs.ResearchScopeError):
                    rs.canonicalize_query_scope(altered, self.evidence)

    def test_partial_canonical_on_otherwise_raw_input_refuses(self):
        raw = copy.deepcopy(self.raw)
        raw["list_condition"]["required_observed_lists"] = ["L:A", "L:C"]
        with self.assertRaises(rs.ResearchScopeError):
            rs.canonicalize_query_scope(raw, self.evidence)

    def test_public_normalized_consumer_refuses_corrupt_pin_before_value_loader(self):
        from scripts.hypothesis_forge import main
        from tests.test_hfic_list_aware_vertical_v1 import draft, AC

        evidence = rs.MembershipEvidence()
        for name in ("JUPITER:toporganicscore:5m", "JUPITER:toptrending:5m"):
            evidence.definitions[name] = {"definition_sha256": "a" * 64, "aliases": []}
        query = rs.canonicalize_query_scope(draft("LIST_CONTRAST", list_condition=AC), evidence)
        query["list_condition"]["definition_refs"]["JUPITER:toptrending:5m"] = "b" * 64
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "corrupt.json"
            path.write_text(json.dumps(query))
            with patch.object(session, "load_session_bundle", return_value={"session_id": "HFIC-TEST"}), \
                 patch.object(rs, "load_corpus_membership", return_value=evidence), \
                 patch.object(gd, "load_admitted_partition_rows", side_effect=AssertionError("value loader")) as loader, \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                result = main(["--root", str(ROOT), "--data-root", temporary,
                               "episode-normalized-view", "--spec", str(path),
                               "--parent-session-id", "HFIC-TEST", "--explicit-request", "--format", "json"])
            self.assertEqual(result, 2)
            self.assertEqual(json.loads(output.getvalue())["reason_code"], "LIST_DEFINITION_DRIFT")
            loader.assert_not_called()


class RevisionScopeTests(unittest.TestCase):
    def test_wording_revision_keeps_scope_and_rejects_nonidentity_axis_change(self):
        from solana_alpha_lab.factory.research_store import ResearchStore
        from tests.test_hfic_session import valid_draft, _preflight_receipt, _critic_result

        for changed in (None, "target", "explanatory_condition", "claim_form"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as temporary:
                store = ResearchStore(Path(temporary))
                original = valid_draft()
                original["candidates"][0].update(SCOPE, claim_form="PREDICTIVE")
                frozen = session.freeze_draft(original, preflight_receipt=_preflight_receipt())
                critique = _critic_result(frozen, "REVISE_ONCE")
                critique["revision_receipt"] = {"scope": "claim_wording", "attempt": 1}
                session.finalize_session(frozen, critique, store=store, repo_root=ROOT)
                revised = copy.deepcopy(original)
                revised["candidates"][0]["claim"] += "; wording clarified"
                if changed:
                    revised["candidates"][0][changed] = "CAUSAL" if changed == "claim_form" else "changed-axis"
                    with self.assertRaises(session.HficSessionError) as caught:
                        session.apply_revision(session.load_session_bundle(store, frozen["session_id"]),
                                               revised, store=store, repo_root=ROOT)
                    self.assertEqual(caught.exception.code, "REVISION_MECHANISM_CHANGED")
                else:
                    output = session.apply_revision(session.load_session_bundle(store, frozen["session_id"]),
                                                    revised, store=store, repo_root=ROOT)
                    selected = output["critic_input_packet"]["selected_candidate"]
                    self.assertEqual(gd.card_claim_scope(selected), SCOPE)
                    self.assertEqual(selected["claim_form"], "PREDICTIVE")


class ContextDependencyTests(unittest.TestCase):
    def test_published_orphan_reservation_with_pending_lookup_recovers_in_append(self):
        import hashlib
        from datetime import datetime, timezone
        from solana_alpha_lab.factory import hfic_preflight as preflight
        from solana_alpha_lab.factory.research_store import ResearchStore
        from solana_alpha_lab.factory.research_write_lookup import WriteLookup
        from tests.test_hfic_session import _preflight_receipt

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ResearchStore(root)
            store.prepare_write_lookup()
            binding = {**_preflight_receipt(), "session_id": "HFIC-SESS-ORPHAN-RECOVERY"}
            binding["forge_context_packet_sha256"] = preflight.persist_forge_context_packet(
                root, binding["forge_context_packet"], store=store, repo_root=ROOT)
            now = datetime(2026, 8, 27, 12, tzinfo=timezone.utc)
            _, admission = session._build_scientific_slot_admission_event(binding, repo_root=ROOT,
                transaction_id="RESEARCH-TXN-ORPHAN-SLOT", stage_time=now)
            with patch.object(WriteLookup, "finish", side_effect=RuntimeError("injected post-publication crash")):
                with self.assertRaises(RuntimeError):
                    store.append([admission], transaction_id=admission.transaction_id)
            pending = list(root.rglob("pending.json"))
            self.assertEqual(len(pending), 1)
            pending_bytes = pending[0].read_bytes()
            cold = ResearchStore(root)
            self.assertIsNone(session.load_session_bundle(cold, binding["session_id"]))
            self.assertEqual(len(session.list_scientific_slot_admissions(cold)), 1)
            self.assertEqual(pending[0].read_bytes(), pending_bytes)
            record_id = "HFIC-ART-ORPHAN-RECOVERY-LIFECYCLE"
            payload = json.dumps({"research_artifact_id": record_id,
                                  "artifact_kind": "SCRIPTED_RECOVERY_TEST"}, sort_keys=True, separators=(",", ":"))
            tx = "RESEARCH-TXN-ORPHAN-RECOVERY-LIFECYCLE"
            lifecycle = admission.model_copy(update={"record_id": record_id, "entity_id": record_id,
                "transaction_id": tx, "payload_json": payload,
                "payload_sha256": hashlib.sha256(payload.encode()).hexdigest()})
            session._append_session_records_with_slot(cold, [lifecycle], transaction_id=tx,
                binding=binding, repo_root=ROOT, stage_time=now,
                representation_registry=None, reserve_slot=True)
            self.assertFalse(pending[0].exists())
            self.assertEqual(len(session.list_scientific_slot_admissions(cold)), 1)
            self.assertEqual(cold.find_record(admission.record_id).transaction_id, admission.transaction_id)
            self.assertEqual(cold.find_record(record_id).transaction_id, tx)

    def test_identical_concurrent_session_transaction_replays_whole_record_set(self):
        from datetime import datetime, timezone
        from solana_alpha_lab.factory import hfic_preflight as preflight
        from solana_alpha_lab.factory.research_store import ResearchStore
        from tests.test_hfic_session import _preflight_receipt

        with tempfile.TemporaryDirectory() as temporary:
            store = ResearchStore(Path(temporary))
            store.prepare_write_lookup()
            binding = {**_preflight_receipt(), "session_id": "HFIC-SESS-CONCURRENT"}
            binding["forge_context_packet_sha256"] = preflight.persist_forge_context_packet(
                store._root, binding["forge_context_packet"], store=store, repo_root=ROOT)
            now = datetime(2026, 8, 27, 12, tzinfo=timezone.utc)
            tx = "RESEARCH-TXN-CONCURRENT-SESSION"
            _, template = session._build_scientific_slot_admission_event(
                binding, repo_root=ROOT, transaction_id=tx, stage_time=now)
            lifecycle_id = "HFIC-ART-CONCURRENT-LIFECYCLE"
            payload = json.dumps({"research_artifact_id": lifecycle_id,
                                  "artifact_kind": "SCRIPTED_REPLAY_TEST"}, sort_keys=True, separators=(",", ":"))
            import hashlib
            lifecycle = template.model_copy(update={
                "record_id": lifecycle_id, "entity_id": lifecycle_id,
                "payload_json": payload, "payload_sha256": hashlib.sha256(payload.encode()).hexdigest(),
            })
            records_to_commit = [lifecycle]
            original_append = store.append
            receipts = []

            def competitor_commits_first(records, *, transaction_id, before_commit):
                # Another identical caller commits after our outside-lease read.
                with patch.object(store, "append", side_effect=original_append):
                    session._append_session_records_with_slot(store, records_to_commit, transaction_id=tx,
                        binding=binding, repo_root=ROOT, stage_time=now,
                        representation_registry=None, reserve_slot=True)
                receipts.append(store.diagnostics().committed_inventory_sha256)
                return original_append(records, transaction_id=transaction_id, before_commit=before_commit)

            with patch.object(session, "_assert_scientific_admission", return_value={}), \
                 patch.object(store, "append", side_effect=competitor_commits_first):
                session._append_session_records_with_slot(store, records_to_commit, transaction_id=tx,
                    binding=binding, repo_root=ROOT, stage_time=now,
                    representation_registry=None, reserve_slot=True)
            self.assertEqual(len(receipts), 1)
            self.assertEqual(store.diagnostics().committed_inventory_sha256, receipts[0])
            self.assertEqual(len(session.list_scientific_slot_admissions(store)), 1)

    def test_context_failure_at_session_commit_never_leaves_a_new_slot(self):
        from solana_alpha_lab.factory import hfic_preflight as preflight
        from solana_alpha_lab.factory.hfic_identity import assign_portfolio_ids
        from solana_alpha_lab.factory.research_store import ResearchStore
        from tests.test_hfic_session import valid_draft, _preflight_receipt

        with tempfile.TemporaryDirectory() as temporary:
            store = ResearchStore(Path(temporary))
            store.prepare_write_lookup()
            draft = valid_draft()
            frozen = session.freeze_draft(draft, preflight_receipt=_preflight_receipt())
            context = _preflight_receipt()["forge_context_packet"]
            digest = preflight.persist_forge_context_packet(store._root, context, store=store, repo_root=ROOT)
            frozen["forge_context_packet_sha256"] = digest
            expected_slot = session._execution_identity_fields(frozen)["scientific_slot_sha256"]
            identities = assign_portfolio_ids(draft["candidates"])
            blob = preflight._forge_context_blob_path(store._root, digest)
            original_bytes = blob.read_bytes()
            original_append = store.append
            before = store.diagnostics().committed_inventory_sha256

            def fail_at_lifecycle_commit(records, *, transaction_id, before_commit=None):
                def hook():
                    if any(not item.record_id.startswith("HFIC-ART-SLOT-ADMISSION-") for item in records):
                        blob.write_text('{"corrupted":true}', encoding="utf-8")
                    if before_commit is not None:
                        before_commit()
                return original_append(records, transaction_id=transaction_id, before_commit=hook)

            with patch.object(session, "_assert_scientific_admission", return_value={}), \
                 patch.object(store, "append", side_effect=fail_at_lifecycle_commit):
                with self.assertRaises(session.HficSessionError) as caught:
                    session.persist_frozen_session(store, frozen, repo_root=ROOT, identities=identities, draft=draft)
            self.assertEqual(caught.exception.code, "FORGE_CONTEXT_HASH_MISMATCH")
            self.assertEqual(store.diagnostics().committed_inventory_sha256, before)
            self.assertEqual(session.list_scientific_slot_admissions(store), [])
            blob.write_bytes(original_bytes)
            with patch.object(session, "_assert_scientific_admission", return_value={}):
                session.persist_frozen_session(store, frozen, repo_root=ROOT, identities=identities, draft=draft)
                after = store.diagnostics().committed_inventory_sha256
                session.persist_frozen_session(store, frozen, repo_root=ROOT, identities=identities, draft=draft)
                self.assertEqual(store.diagnostics().committed_inventory_sha256, after)
            self.assertEqual(len(session.list_scientific_slot_admissions(store)), 1)
            self.assertEqual(session.list_scientific_slot_admissions(store)[0]["scientific_slot_sha256"], expected_slot)

    def test_existing_owner_checks_blob_committed_record_inline_and_root(self):
        from solana_alpha_lab.factory import hfic_preflight as preflight
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ResearchStore(root / "correct")
            store.prepare_write_lookup()
            packet = {"vision_integrity": {"status": "PASS"}, "fixture": "context-only"}
            digest = preflight.persist_forge_context_packet(store._root, packet, store=store, repo_root=ROOT)
            binding = {"forge_context_packet_sha256": digest, "forge_context_packet": packet}
            session._verify_required_context_dependency(store, binding)
            with self.assertRaises(session.HficSessionError) as caught:
                session._verify_required_context_dependency(store, {**binding, "forge_context_packet": {"tampered": True}})
            self.assertEqual(caught.exception.code, "FORGE_CONTEXT_HASH_MISMATCH")
            # Durable freeze must check the receipt inline used to build the
            # packet, even though the frozen envelope carries only its digest.
            with patch.object(session, "load_session_bundle", return_value=None), \
                 patch.object(session, "_assert_scientific_admission", return_value={}):
                with self.assertRaises(session.HficSessionError) as caught:
                    session.persist_frozen_session(store,
                        {"session_id": "HFIC-SESS-INLINE-TAMPER", "forge_context_packet_sha256": digest},
                        repo_root=ROOT, identities=[],
                        preflight_receipt={**binding, "forge_context_packet": {"tampered": True}})
                self.assertEqual(caught.exception.code, "FORGE_CONTEXT_HASH_MISMATCH")
            other = ResearchStore(root / "other")
            other.prepare_write_lookup()
            destination = preflight._forge_context_blob_path(other._root, digest)
            destination.parent.mkdir(parents=True)
            destination.write_bytes(preflight._forge_context_blob_path(store._root, digest).read_bytes())
            with self.assertRaises(session.HficSessionError) as caught:
                session._verify_required_context_dependency(other, binding)
            self.assertEqual(caught.exception.code, "FORGE_CONTEXT_ARTIFACT_MISSING")
            original = preflight._forge_context_blob_path(store._root, digest)
            original.write_text('{"tampered":true}', encoding="utf-8")
            with self.assertRaises(session.HficSessionError) as caught:
                session._verify_required_context_dependency(store, binding)
            self.assertEqual(caught.exception.code, "FORGE_CONTEXT_HASH_MISMATCH")

    def test_missing_context_before_direct_durable_frozen_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = Mock(_root=Path(temporary))
            frozen = {"session_id": "HFIC-SESS-DEPENDENCY", "forge_context_packet_sha256": "a" * 64}
            with patch.object(session, "load_session_bundle", return_value=None), \
                 patch.object(session, "_assert_scientific_admission", return_value={}):
                with self.assertRaises(session.HficSessionError) as caught:
                    session.persist_frozen_session(store, frozen, repo_root=ROOT, identities=[])
                self.assertEqual(caught.exception.code, "FORGE_CONTEXT_ARTIFACT_MISSING")
            store.append.assert_not_called()


if __name__ == "__main__":
    unittest.main()
