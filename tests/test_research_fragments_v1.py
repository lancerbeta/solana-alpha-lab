"""One synthetic native vertical. No real research or numerical replay."""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from tests import test_forge_research_flow_reliability_v1 as flow
from tests import test_hfic_list_aware_vertical_v1 as lav
from tests.test_hfic_cli import critic_result_from_packet_only
from solana_alpha_lab.factory import research_fragments as f
from solana_alpha_lab.factory.research_store import ResearchStore
from solana_alpha_lab.factory.run_passport import canonical_sha256

ROOT = Path(__file__).resolve().parents[1]
GIT_SHA = "a" * 40


class FragmentVerticalTests(unittest.TestCase):
    setUpClass = classmethod(flow.EpisodeFlowTests.setUpClass.__func__)
    tearDownClass = classmethod(flow.EpisodeFlowTests.tearDownClass.__func__)
    setUp = flow.EpisodeFlowTests.setUp
    cli = flow.EpisodeFlowTests.cli
    write = flow.EpisodeFlowTests.write
    preflight = flow.EpisodeFlowTests.preflight
    look = flow.EpisodeFlowTests.look
    authored_draft = flow.EpisodeFlowTests.authored_draft
    persist_and_freeze = flow.EpisodeFlowTests.persist_and_freeze

    def seed(self):
        evidence, scope, query, initial = self.look("FRAGMENT_SYNTH_SEED")
        body, pre = self.authored_draft(evidence, scope, initial["owner_focus"])
        _, frozen = self.persist_and_freeze(body, pre)
        critic = critic_result_from_packet_only(frozen["critic_input_packet"], terminal="KILL_STATISTICALLY_UNIDENTIFIABLE")
        self.cli("finalize", "--session-id", frozen["session_id"], "--critic-result", self.write("critic.json", critic))
        self.store = ResearchStore(self.plane)
        request = {"session_id": frozen["session_id"], "candidate_id": frozen["selected_candidate_id"],
            "definition_sha256": frozen["selected_definition_sha256"], "result_ref": evidence["result_refs"][0],
            "result_sha256": evidence["result_sha256"], "title": "Synthetic bounded observation", "role": "CONTEXT_FILTER"}
        self.card = f.register(self.store, request, git_sha=GIT_SHA)["fragment"]
        return request, evidence

    def plan(self):
        start = lav.DAY_B
        request = {"fragment_version_id": self.card["fragment_version_id"],
            "data_root_identity_sha256": f.root_identity(self.store), "enabled": True,
            "windows": [{"start": start.isoformat(), "end": (start+timedelta(days=1)).isoformat(),
                         "input_closed_at": (start+timedelta(days=4, hours=1)).isoformat()}],
            "execution_deadline": (start+timedelta(days=11)).isoformat(), "max_evaluations": 1, "max_input_rows": 100000,
            "information_rule": {"min_matched": 2, "min_days": 1, "min_tail_mass": .2, "adverse_es10_delta": .1},
            "scientific_use": "EXPLORATORY_MONITORING", "source_roles": ["EXPLORATORY_REUSE"],
            "access_boundary": {"forge": "EXPOSED_OR_UNKNOWN", "scout": "EXPOSED_OR_UNKNOWN", "confirmatory_claims": False, "protected_holdouts": "EXCLUDE"},
            "owner_scope_ref": "SYNTHETIC_AUTHORIZED_FIXED_WINDOW"}
        at = start-timedelta(days=1)
        preview = f.plan_preview(self.store, request, now=at)
        return request, f.apply_plan(self.store, preview, git_sha=GIT_SHA, now=at)

    def test_registration_projection_prior_actual_import_and_cold_resume(self):
        from solana_alpha_lab.factory.lifecycle_projection import build_lifecycle_projection
        from solana_alpha_lab.factory.research_workbench import compose_research_overview, compose_research_detail, parse_locator
        from solana_alpha_lab.factory.workbench import _research_overview_html, _research_detail_html
        from solana_alpha_lab.factory.hfic_generation_context import collect_verified_priors, select_working_snapshot, archive_fingerprint
        from solana_alpha_lab.factory.hfic_ordinary_operation import journal_occupancy
        request, evidence = self.seed()
        before = self.store.diagnostics().committed_inventory_sha256
        self.assertEqual(f.register(self.store, request, git_sha=GIT_SHA)["status"], "ALREADY_PRESENT_EXACT")
        view = f.source_snapshot(self.store)[0]
        self.assertEqual(view["source"]["result_sha256"], evidence["result_sha256"])
        self.assertEqual(view["check"]["status"], "DISABLED")
        projection = build_lifecycle_projection(ROOT, research_store=self.store)
        shelf = compose_research_overview(projection, kind="fragments")
        self.assertEqual(len(shelf["universe"]), 1)
        self.assertIn("Фрагменты", _research_overview_html(shelf))
        locator = parse_locator(self.card["fragment_version_id"], "EVIDENCE", "RESEARCH_FRAGMENT")
        detail = compose_research_detail(projection, locator, root=ROOT)
        self.assertIn("Baseline ES10", _research_detail_html(detail))
        from solana_alpha_lab.factory.application import FactoryApplication
        from tests.test_research_lifecycle_workbench_v1 import _get
        app = FactoryApplication(root=ROOT, research_data_root=self.plane,
            spec_relative="configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml")
        status, page, _ = _get(app, "/research?kind=fragments")
        self.assertEqual(status, 200)
        self.assertIn(self.card["fragment_version_id"], page)
        status, page, _ = _get(app, "/research?entity_id=" + self.card["fragment_version_id"] + "&truth_plane=EVIDENCE&native_kind=RESEARCH_FRAGMENT")
        self.assertEqual(status, 200)
        self.assertIn("Baseline ES10", page)
        archive = collect_verified_priors(self.store, as_of=None)
        memory = select_working_snapshot(archive, query={}, inventory_digest=before, consulted_refs=[self.card["fragment_version_id"]])
        self.assertEqual(memory["mandatory_count"], 1)
        self.assertEqual(memory["capsules"][0]["source_detail"]["research_fragments"][0]["source_ref"], self.card["_record_id"])
        self.assertEqual(before, self.store.diagnostics().committed_inventory_sha256)
        with self.assertRaisesRegex(f.FragmentError, "FRAGMENT_RESULT_HASH_MISMATCH"):
            f.register(self.store, {**request, "result_sha256": "0"*64}, git_sha=GIT_SHA)
        with self.assertRaisesRegex(f.FragmentError, "HOLDOUT_UNRESOLVED"):
            self.plan()
        self.assertEqual(before, self.store.diagnostics().committed_inventory_sha256)
        shutil.copytree(self.source/"protection", self.plane/"protection")
        plan_request, _ = self.plan()
        reader_pre = self.preflight("FRAGMENT_ORDINARY_PRIOR_CONSUMER")
        working = reader_pre["forge_context_packet"]["prior_memory_working_view"]
        detail = self.cli("prior", "--context-view", "--preflight-receipt", self.write("reader-pre.json", reader_pre),
                          "--selection-query-sha256", working["selection_query_sha256"], "--source-ref", self.card["fragment_version_id"], "--format", "json")
        self.assertEqual(detail["view"]["mandatory_count"], 1)
        reader_evidence, reader_scope, _, reader_pre = self.look(reader_pre["owner_focus"],
            lav.draft("LIST_CONTRAST", list_condition={"clauses": [{"all_of": ["B"]}]}), preflight_receipt=reader_pre)
        draft, _ = self.authored_draft(reader_evidence, reader_scope, reader_pre["owner_focus"], preflight_receipt=reader_pre)
        draft["candidates"][0]["claim"] += " Source-bound advisory construction, no independent confirmation."
        draft["candidates"][0]["prior_work_refs"] = [self.card["_record_id"]]
        _, frozen = self.persist_and_freeze(draft, reader_pre)
        frozen_source = frozen["critic_input_packet"]["prior_memory"]["capsules"][0]["source_detail"]["research_fragments"][0]
        self.assertEqual(frozen_source["source_ref"], self.card["_record_id"])
        critic = critic_result_from_packet_only(frozen["critic_input_packet"], terminal="KILL_STATISTICALLY_UNIDENTIFIABLE")
        self.cli("finalize", "--session-id", frozen["session_id"], "--critic-result", self.write("reader-critic.json", critic))
        (self.plane/"protection").rename(self.work/"saved-protection")
        blocked = f.run_due(self.store, repo_root=ROOT, git_sha=GIT_SHA)
        self.assertEqual(blocked["fragments"][0]["reason"], "FRAGMENT_WINDOW_INPUTS_NOT_COMPLETE")
        imported = lav._consume(self.packets[1:], source=self.source, mirror=self.work/"mirror", plane=self.plane)
        self.assertEqual(imported["_exit_code"], 0, imported)
        blocked = f.run_due(self.store, repo_root=ROOT, git_sha=GIT_SHA)
        self.assertEqual(blocked["fragments"][0]["reason"], "HOLDOUT_UNRESOLVED")
        # Current source completeness is a real synthetic native inventory,
        # including a protected nomination, not a fabricated empty document.
        (self.work/"saved-protection").rename(self.plane/"protection")
        tiny = {**plan_request, "max_input_rows": 1}
        f.apply_plan(self.store, f.plan_preview(self.store, tiny), git_sha=GIT_SHA)
        too_big = f.run_due(self.store, repo_root=ROOT, git_sha=GIT_SHA)
        self.assertEqual(too_big["fragments"][0]["reason"], "FRAGMENT_COMPUTE_ROW_CAP_EXCEEDED")
        self.assertEqual(journal_occupancy(self.store, f.journal_for(self.card["fragment_version_id"]))["main"]["occupied"], 0)
        f.apply_plan(self.store, f.plan_preview(self.store, plan_request), git_sha=GIT_SHA)
        from solana_alpha_lab.factory.opportunity_episode_release import load_episode_lineage, import_episode_release
        release = self.plane / load_episode_lineage(self.plane)["cohorts"][-1]["release_dir_rel"]
        from solana_alpha_lab.factory import hfic_grounded_discovery as discovery
        with patch.object(discovery, "load_admitted_partition_rows", side_effect=RuntimeError("synthetic crash before values")):
            pending = import_episode_release(release_root=release, data_root=self.plane)
        self.assertEqual(pending["fragment_refresh"]["status"], "BLOCKED")
        self.assertEqual(journal_occupancy(self.store, f.journal_for(self.card["fragment_version_id"]))["main"]["pending"], 1)
        from solana_alpha_lab.factory.hfic_evidence_identity import compute_split_identity
        old_epoch = compute_split_identity(ROOT, self.plane)["market_evidence_epoch_sha256"]
        from tests.test_opportunity_episodes_vertical_v1 import _import_legacy
        _import_legacy(self.plane, self.work/"compatible-legacy")
        self.assertNotEqual(old_epoch, compute_split_identity(ROOT, self.plane)["market_evidence_epoch_sha256"])
        from solana_alpha_lab.factory import hfic_evidence_identity as identity
        with patch.object(identity, "compute_capability_epoch_for_repo", return_value=("0"*64, {})):
            changed_code = f.run_due(self.store, repo_root=ROOT, git_sha=GIT_SHA)
        self.assertEqual(changed_code["fragments"][0]["reason"], "FRAGMENT_EXECUTION_BINDING_CHANGED")
        self.assertEqual(journal_occupancy(self.store, f.journal_for(self.card["fragment_version_id"]))["main"]["pending"], 1)
        with patch.object(f, "_link_check", side_effect=RuntimeError("synthetic crash after native result")):
            crashed = import_episode_release(release_root=release, data_root=self.plane)
        self.assertEqual(crashed["status"], "PASS_ALREADY_PRESENT_EXACT")
        self.assertEqual(crashed["fragment_refresh"]["status"], "BLOCKED")
        occupancy = journal_occupancy(self.store, f.journal_for(self.card["fragment_version_id"]))
        self.assertEqual(occupancy["main"]["completed"], 1, imported)
        paused = {**plan_request, "enabled": False}
        f.apply_plan(self.store, f.plan_preview(self.store, paused), git_sha=GIT_SHA)
        completed = subprocess.run([sys.executable, "-B", str(ROOT/"scripts/research_fragments.py"), "run-due", "--data-root", str(self.plane), "--confirm-append-only"],
            capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"}, check=True)
        self.assertEqual(json.loads(completed.stdout)["status"], "RECOVERED_LANDED_RESULT")
        cold = ResearchStore(self.plane, create_if_missing=False)
        f.apply_plan(cold, f.plan_preview(cold, plan_request), git_sha=GIT_SHA)
        checks = [r for r in f.documents(cold) if r["artifact_kind"] == f.CHECK]
        self.assertEqual(len(checks), 1)
        inventory = cold.diagnostics().committed_inventory_sha256
        again = lav._consume(self.packets[1:], source=self.source, mirror=self.work/"mirror", plane=self.plane)
        self.assertEqual(again["_exit_code"], 0, again)
        self.assertEqual(inventory, cold.diagnostics().committed_inventory_sha256)
        blocks = f.source_snapshot(cold)[0]["evidence_blocks"]
        self.assertEqual(len(blocks), 2)
        # Independent literal oracle for the two authored B outcomes: -.40,+.05;
        # no A members. A sparse/missing matched tail cannot become a pass.
        self.assertEqual(blocks[1]["summary"]["matched"]["downside"]["observed_n"], 0)
        self.assertEqual(blocks[1]["summary"]["baseline"]["downside"]["observed_n"], 2)
        self.assertAlmostEqual(blocks[1]["summary"]["baseline"]["downside"]["es10_return"], -.4)
        self.assertEqual(blocks[1]["assessment"], "INCONCLUSIVE")
        self.assertEqual(blocks[1]["exposure"], "EXPLORATORY_MONITORING")
        self.assertNotEqual(blocks[0]["result_ref"], blocks[1]["result_ref"])
        self.assertEqual(journal_occupancy(cold, f.journal_for(self.card["fragment_version_id"]))["main"]["completed"], 1)
        historical = collect_verified_priors(cold, as_of=working["research_log_cutoff"])
        self.assertEqual(archive_fingerprint(historical), working["eligible_archive_sha256"])


class FragmentDamagedItemTests(unittest.TestCase):
    def test_generic_scalar_and_damaged_identity_preserve_item_boundary(self):
        from types import SimpleNamespace
        at = datetime.now(UTC)
        body = {"artifact_kind": f.CARD, "schema_version": "1.0"}
        wrapper = {"artifact_kind": f.CARD, "payload_canonical": json.dumps(body), "payload_sha256": canonical_sha256(body)}
        records = [SimpleNamespace(record_kind="RESEARCH_ARTIFACT", first_reliable_available_at=at, effective_at=at,
            entity_id="BROKEN-FRAGMENT", record_id="BROKEN-FRAGMENT", payload_json=json.dumps(wrapper)),
            SimpleNamespace(record_kind="RESEARCH_ARTIFACT", first_reliable_available_at=at, effective_at=at,
            entity_id="GENERIC-ARTIFACT", record_id="GENERIC-ARTIFACT", payload_json="[]")]
        store = SimpleNamespace(iter_committed_records=lambda: iter(records))
        self.assertEqual(len(f.source_snapshot(store)), 1)
        self.assertEqual(f.source_snapshot(store)[0]["error"], "FRAGMENT_ARTIFACT_INTEGRITY_INVALID")
        due = f.run_due(store, repo_root=ROOT, git_sha=GIT_SHA)
        self.assertEqual(due["fragments"][0]["reason"], "FRAGMENT_ARTIFACT_INTEGRITY_INVALID")
        self.assertFalse(due["new_look"])


if __name__ == "__main__":
    unittest.main()
