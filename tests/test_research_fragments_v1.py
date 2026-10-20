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
        evidence, scope, query, initial = self.look("FRAGMENT_SYNTH_SEED", lav.draft("LIST_CONTRAST", list_condition={"clauses": [{"all_of": ["B"]}, {"all_of": ["C"]}]}))
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
        start = lav.DAY_A
        request = {"fragment_version_id": self.card["fragment_version_id"],
            "data_root_identity_sha256": f.root_identity(self.store), "enabled": True,
            "windows": [{"start": day.isoformat(), "end": (day+timedelta(days=1)).isoformat(),
                         "input_closed_at": (day+timedelta(days=4, hours=1)).isoformat()} for day in (lav.DAY_A, lav.DAY_B)],
            "execution_deadline": (lav.DAY_B+timedelta(days=11)).isoformat(), "max_evaluations": 2, "max_input_rows": 100000,
            "information_rule": {"min_matched": 2, "min_days": 2, "min_tail_mass": .2, "adverse_es10_delta": .1},
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
        shutil.rmtree(self.plane / "protection")  # controlled fixture: current authority missing
        with self.assertRaisesRegex(f.FragmentError, "HOLDOUT_UNRESOLVED"):
            self.plan()
        self.assertEqual(before, self.store.diagnostics().committed_inventory_sha256)
        # No local assignments: all controlled native owners prove complete-empty.
        # Frozen release dependencies remain byte-for-byte inside each release.
        from tests.test_opportunity_episodes_vertical_v1 import install_current_fixture
        install_current_fixture(self.plane)
        self.assertTrue(f.current_protection_status(self.store)["complete_empty"])
        plan_request, _ = self.plan()
        current_pointer_bytes = (self.plane / "protection/current_research.json").read_bytes()
        current_versions = sorted(p.name for p in (self.plane / "protection/assignments").glob("CURRENT-RESEARCH-*.json"))
        reader_pre = self.preflight("FRAGMENT_ORDINARY_PRIOR_CONSUMER")
        working = reader_pre["forge_context_packet"]["prior_memory_working_view"]
        detail = self.cli("prior", "--context-view", "--preflight-receipt", self.write("reader-pre.json", reader_pre),
                          "--selection-query-sha256", working["selection_query_sha256"], "--source-ref", self.card["fragment_version_id"], "--format", "json")
        self.assertEqual(detail["view"]["mandatory_count"], 1)
        reader_evidence, reader_scope, _, reader_pre = self.look(reader_pre["owner_focus"],
            lav.draft("LIST_CONTRAST", list_condition={"clauses": [{"all_of": ["A"]}]}), preflight_receipt=reader_pre)
        draft, _ = self.authored_draft(reader_evidence, reader_scope, reader_pre["owner_focus"], preflight_receipt=reader_pre)
        draft["candidates"][0]["claim"] += " Source-bound advisory construction, no independent confirmation."
        draft["candidates"][0]["prior_work_refs"] = [self.card["_record_id"]]
        _, frozen = self.persist_and_freeze(draft, reader_pre)
        frozen_source = frozen["critic_input_packet"]["prior_memory"]["capsules"][0]["source_detail"]["research_fragments"][0]
        self.assertEqual(frozen_source["source_ref"], self.card["_record_id"])
        critic = critic_result_from_packet_only(frozen["critic_input_packet"], terminal="KILL_STATISTICALLY_UNIDENTIFIABLE")
        self.cli("finalize", "--session-id", frozen["session_id"], "--critic-result", self.write("reader-critic.json", critic))
        from solana_alpha_lab.factory import hfic_grounded_discovery as discovery
        from solana_alpha_lab.factory import hfic_evidence_identity as identity
        from solana_alpha_lab.factory.hfic_ordinary_operation import effective_open_operations
        # First window: a real native reservation, no result. Pause retains it;
        # expiry makes it visible, never refunds it or invents a CHECK.
        with patch.object(identity, "compute_capability_epoch_for_repo", return_value=("0"*64, {})):
            f.apply_plan(self.store, f.plan_preview(self.store, plan_request), git_sha=GIT_SHA)
            with patch.object(discovery, "load_admitted_partition_rows", side_effect=RuntimeError("first window interrupted")):
                with self.assertRaises(RuntimeError):
                    f.run_due(self.store, repo_root=ROOT, git_sha=GIT_SHA)
        paused = {**plan_request, "enabled": False}
        f.apply_plan(self.store, f.plan_preview(self.store, paused), git_sha=GIT_SHA)
        paused_read = f.source_snapshot(self.store)[0]["check"]
        self.assertEqual(paused_read["status"], "DISABLED")
        first = paused_read["attempts_without_result"][0]
        self.assertEqual(first["effective_state"], "OPEN")
        self.assertTrue(first["holds_universe_gate"])
        self.assertEqual(len(first["unresolved_reservation_spec_sha256"]), 1)
        f.apply_plan(self.store, f.plan_preview(self.store, plan_request), git_sha=GIT_SHA)
        active = f.current_plan(f.documents(self.store), self.card["fragment_version_id"])
        expired = f.plan_status(self.store, self.card, active, rows=f.documents(self.store),
                                now=f._time(active["execution_deadline"])+timedelta(seconds=1))
        self.assertEqual(expired["status"], "EXPIRED")
        self.assertEqual(expired["attempts_without_result"][0]["operation_sha256"], first["operation_sha256"])
        # Explicit accepted plan rebind does not make the original attempt
        # compatible with a different executor. The existing native STOP is
        # the supported no-result exit; its reservation remains charged.
        rebound = f.run_due(self.store, repo_root=ROOT, git_sha=GIT_SHA)
        self.assertEqual(rebound["fragments"][0]["reason"], "FRAGMENT_PENDING_NATIVE_STOP_REQUIRED")
        self.assertFalse(rebound["fragments"][0]["attempts_without_result"][0]["execution_binding_matches_plan"])
        stop = self.cli("operation-stop-preview", "--operation-sha256", first["operation_sha256"],
                        "--owner-request-text", "Synthetic incompatible pending attempt; retain reservation, continue next fixed window")
        self.assertFalse(stop["effect"]["quota_returned"])
        self.cli("operation-stop", "--proposal", self.write("stop-first.json", stop["proposal"]), "--confirm-append-only")
        self.assertEqual(effective_open_operations(self.store), [])
        self.assertEqual([r for r in f.documents(self.store) if r["artifact_kind"] == f.CHECK], [])
        f.apply_plan(self.store, f.plan_preview(self.store, plan_request), git_sha=GIT_SHA)
        after_stop = f.source_snapshot(self.store)[0]["check"]
        self.assertEqual(after_stop["window_index"], 1)
        self.assertEqual(after_stop["native_spend"]["pending"], 1)
        self.assertEqual(after_stop["attempts_without_result"][0]["effective_state"], "STOPPED")
        (self.plane/"protection").rename(self.work/"saved-protection")
        blocked = f.run_due(self.store, repo_root=ROOT, git_sha=GIT_SHA)
        self.assertEqual(blocked["fragments"][0]["reason"], "FRAGMENT_WINDOW_INPUTS_NOT_COMPLETE")
        imported = lav._consume(self.packets[1:], source=self.source, mirror=self.work/"mirror", plane=self.plane, install_protection=False)
        self.assertEqual(imported["_exit_code"], 0, imported)
        blocked = f.run_due(self.store, repo_root=ROOT, git_sha=GIT_SHA)
        self.assertEqual(blocked["fragments"][0]["reason"], "HOLDOUT_UNRESOLVED")
        blocked_projection = build_lifecycle_projection(ROOT, research_store=self.store)
        blocked_shelf = compose_research_overview(blocked_projection, kind="fragments")
        self.assertIn("Нет актуального полного protection inventory", _research_overview_html(blocked_shelf))
        blocked_view = f.source_snapshot(self.store)[0]
        self.assertEqual(blocked_view["check"]["reason"], "HOLDOUT_UNRESOLVED")
        # Restore the original proved-empty current metadata; the imported
        # cohort independently retains its native frozen protection dependencies.
        (self.work/"saved-protection").rename(self.plane/"protection")
        self.assertEqual((self.plane / "protection/current_research.json").read_bytes(), current_pointer_bytes)
        self.assertEqual(sorted(p.name for p in (self.plane / "protection/assignments").glob("CURRENT-RESEARCH-*.json")), current_versions)
        self.assertEqual(f.current_protection_status(self.store)["status"], "ALLOW")
        tiny = {**plan_request, "max_input_rows": 1}
        f.apply_plan(self.store, f.plan_preview(self.store, tiny), git_sha=GIT_SHA)
        too_big = f.run_due(self.store, repo_root=ROOT, git_sha=GIT_SHA)
        self.assertEqual(too_big["fragments"][0]["reason"], "FRAGMENT_COMPUTE_ROW_CAP_EXCEEDED")
        self.assertEqual(journal_occupancy(self.store, f.journal_for(self.card["fragment_version_id"]))["main"]["occupied"], 1)
        f.apply_plan(self.store, f.plan_preview(self.store, plan_request), git_sha=GIT_SHA)
        from solana_alpha_lab.factory.opportunity_episode_release import load_episode_lineage, import_episode_release
        release = self.plane / load_episode_lineage(self.plane)["cohorts"][-1]["release_dir_rel"]
        from solana_alpha_lab.factory import hfic_grounded_discovery as discovery
        with patch.object(discovery, "load_admitted_partition_rows", side_effect=RuntimeError("synthetic crash before values")):
            pending = import_episode_release(release_root=release, data_root=self.plane)
        self.assertEqual(pending["fragment_refresh"]["status"], "BLOCKED")
        self.assertEqual(journal_occupancy(self.store, f.journal_for(self.card["fragment_version_id"]))["main"]["pending"], 2)
        from solana_alpha_lab.factory.hfic_evidence_identity import compute_split_identity
        old_epoch = compute_split_identity(ROOT, self.plane)["market_evidence_epoch_sha256"]
        from tests.test_opportunity_episodes_vertical_v1 import _import_legacy
        _import_legacy(self.plane, self.work/"compatible-legacy")
        self.assertNotEqual(old_epoch, compute_split_identity(ROOT, self.plane)["market_evidence_epoch_sha256"])
        from solana_alpha_lab.factory import hfic_evidence_identity as identity
        with patch.object(identity, "compute_capability_epoch_for_repo", return_value=("0"*64, {})):
            changed_code = f.run_due(self.store, repo_root=ROOT, git_sha=GIT_SHA)
        self.assertEqual(changed_code["fragments"][0]["reason"], "FRAGMENT_EXECUTION_BINDING_CHANGED")
        self.assertEqual(journal_occupancy(self.store, f.journal_for(self.card["fragment_version_id"]))["main"]["pending"], 2)
        with patch.object(f, "_link_check", side_effect=RuntimeError("synthetic crash after native result")):
            crashed = import_episode_release(release_root=release, data_root=self.plane)
        self.assertEqual(crashed["status"], "PASS_ALREADY_PRESENT_EXACT")
        self.assertEqual(crashed["fragment_refresh"]["status"], "BLOCKED")
        occupancy = journal_occupancy(self.store, f.journal_for(self.card["fragment_version_id"]))
        self.assertEqual(occupancy["main"]["completed"], 1, imported)
        recovery = f.source_snapshot(self.store)[0]["check"]
        self.assertEqual(recovery["status"], "DUE")
        self.assertEqual(recovery["reason"], "FRAGMENT_RECOVER_LANDED_RESULT")
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
        # Independent literal oracle: the two B outcomes are -.40,+.05.
        # A real nonzero matched check carries day support and rule grounds.
        self.assertEqual(blocks[1]["summary"]["matched"]["downside"]["observed_n"], 2)
        self.assertEqual(blocks[1]["summary"]["baseline"]["downside"]["observed_n"], 2)
        self.assertAlmostEqual(blocks[1]["summary"]["baseline"]["downside"]["es10_return"], -.4)
        self.assertEqual(blocks[1]["assessment"], "INCONCLUSIVE")
        self.assertAlmostEqual(blocks[1]["summary"]["matched"]["downside"]["es10_return"], -.4)
        day_support = blocks[1]["summary"]["details"]["by_calendar_block"]
        self.assertEqual(len(day_support), 1)
        self.assertEqual(day_support[0]["downside"]["observed_n"], 2)
        self.assertEqual(blocks[1]["information_basis"]["criteria"]["min_days"]["observed"], 1)
        self.assertFalse(blocks[1]["information_basis"]["enough"])
        self.assertEqual(blocks[1]["information_basis"]["criteria"]["min_matched"]["reason"], "MET")
        self.assertEqual(blocks[1]["information_basis"]["criteria"]["min_days"]["reason"], "BELOW_REQUIRED")
        self.assertFalse(blocks[1]["summary"]["dependence"]["mint_overlap_known"])
        self.assertFalse(blocks[1]["summary"]["dependence"]["cohort_independent_replication"])
        self.assertEqual(effective_open_operations(cold), [])
        final_spend = journal_occupancy(cold, f.journal_for(self.card["fragment_version_id"]))["main"]
        self.assertEqual((final_spend["completed"], final_spend["pending"], final_spend["occupied"]), (1, 1, 2))
        final_view = f.source_snapshot(cold)[0]
        self.assertEqual(final_view["source"]["result_sha256"], evidence["result_sha256"])
        self.assertEqual(final_view["check"]["attempts_without_result"][0]["effective_state"], "STOPPED")
        support_page = _research_detail_html(compose_research_detail(build_lifecycle_projection(ROOT, research_store=cold), locator, root=ROOT))
        self.assertIn("Поддержка по дням", support_page)
        self.assertIn("Основание information rule", support_page)
        self.assertIn(first["operation_sha256"], support_page)
        self.assertEqual(blocks[1]["exposure"], "EXPLORATORY_MONITORING")
        self.assertNotEqual(blocks[0]["result_ref"], blocks[1]["result_ref"])
        self.assertEqual(journal_occupancy(cold, f.journal_for(self.card["fragment_version_id"]))["main"]["completed"], 1)
        historical = collect_verified_priors(cold, as_of=working["research_log_cutoff"])
        self.assertEqual(archive_fingerprint(historical), working["eligible_archive_sha256"])
        # Corrupt execution metadata must not erase verified scientific evidence.
        broken_plan = {k: v for k, v in f.current_plan(f.documents(cold), self.card["fragment_version_id"]).items()
                       if not k.startswith("_") and k not in {"max_evaluations", "plan_sha256"}}
        broken_plan["plan_sha256"] = canonical_sha256(broken_plan)
        f._append(cold, broken_plan, git_sha=GIT_SHA, now=datetime.now(UTC))
        saved_view = f.source_snapshot(cold)[0]
        self.assertNotIn("error", saved_view)
        self.assertEqual(saved_view["check"]["reason"], "FRAGMENT_PLAN_SHAPE_INVALID")
        self.assertEqual(saved_view["evidence_blocks"], blocks)
        remembered = collect_verified_priors(cold, as_of=None)
        source_cap = next(c for c in remembered["capsules"] if c["hypothesis_version_id"] == self.card["source"]["candidate_id"])
        self.assertEqual(source_cap["source_detail"]["research_fragments"][0]["evidence_blocks"], blocks)
        # CHECK and PLAN share plan_sha256. Neither CHECK-first ordering nor
        # missing/corrupt original PLAN may discard hash-verified results.
        original = next(p for p in f.documents(cold) if p["artifact_kind"] == f.PLAN
                        and p["plan_sha256"] == checks[0]["plan_sha256"])
        rows = f.documents(cold)
        reordered = sorted(rows, key=lambda r: r["artifact_kind"] != f.CHECK)
        with patch.object(f, "documents", return_value=reordered):
            self.assertEqual(f.source_snapshot(cold)[0]["evidence_blocks"], blocks)
        for damage in ("MISSING", "CORRUPT", "STALE_INNER_HASH"):
            missing = [r for r in rows if r["_record_id"] != original["_record_id"]]
            if damage == "CORRUPT":
                missing.insert(0, {**original, "_error": "FRAGMENT_ARTIFACT_INTEGRITY_INVALID"})
            if damage == "STALE_INNER_HASH":
                missing.insert(0, {**original, "information_rule": {**original["information_rule"], "min_days": 999}})
            with patch.object(f, "documents", return_value=missing):
                views = f.source_snapshot(cold)
                self.assertEqual(len(views), 1)
                retained = views[0]
                self.assertEqual(len(retained["evidence_blocks"]), 2)
                self.assertEqual(retained["evidence_blocks"][1]["summary"], blocks[1]["summary"])
                self.assertEqual(retained["evidence_blocks"][1]["information_basis"]["status"], "UNKNOWN")
                self.assertEqual(retained["check"]["status"], "BLOCKED")
                remembered = collect_verified_priors(cold, as_of=None)
                cap = next(c for c in remembered["capsules"] if c["hypothesis_version_id"] == self.card["source"]["candidate_id"])
                self.assertEqual(cap["source_detail"]["research_fragments"][0]["evidence_blocks"], retained["evidence_blocks"])
                page = _research_detail_html(compose_research_detail(build_lifecycle_projection(ROOT, research_store=cold), locator, root=ROOT))
                self.assertIn(blocks[1]["result_ref"], page)
                self.assertIn("UNKNOWN", page)

    def test_late_deny_after_native_reservation_stops_before_loader_and_pause_survives_unknown(self):
        import pyarrow.parquet as pq
        from solana_alpha_lab.factory import hfic_ordinary_operation as operations
        from solana_alpha_lab.factory import hfic_grounded_discovery as discovery
        from solana_alpha_lab.factory.opportunity_episode_release import load_episode_lineage
        from tests.test_opportunity_episodes_harness_v1 import write_assignment
        _request, evidence = self.seed()
        plan_request, _applied = self.plan()
        item = load_episode_lineage(self.plane)["cohorts"][0]
        mint = pq.read_table(self.plane / item["census_rel"], columns=["mint"]).column("mint")[0].as_py()
        original = operations.authorize_temporal_attempt
        def late_deny(*args, **kwargs):
            result = original(*args, **kwargs)
            write_assignment(self.plane, [{"identity_kind": "MINT", "identity": mint,
                "role": "UNTOUCHED_FORWARD_HOLDOUT", "scope": {"kind": "ALL_TIME"}}])
            return result
        with patch.object(operations, "authorize_temporal_attempt", side_effect=late_deny), patch.object(
                discovery, "load_admitted_partition_rows", side_effect=AssertionError("unsafe value loader")) as loader:
            result = f.run_due(self.store, repo_root=ROOT, git_sha=GIT_SHA)
        self.assertEqual(result["fragments"][0]["reason"], "HOLDOUT_PROTECTED")
        self.assertFalse(result["fragments"][0]["values_loaded"])
        loader.assert_not_called()
        occupancy = operations.journal_occupancy(self.store, f.journal_for(self.card["fragment_version_id"]))["main"]
        self.assertEqual((occupancy["pending"], occupancy["completed"]), (1, 0))
        self.assertEqual([r for r in f.documents(self.store) if r["artifact_kind"] == f.CHECK], [])
        self.assertEqual(f.source_snapshot(self.store)[0]["source"]["result_sha256"], evidence["result_sha256"])
        # Unknown current source still permits disabling and saved readback.
        directory = self.plane / "protection/assignments"
        (directory / "UNKNOWN.json").write_text(json.dumps({"schema": "UNKNOWN", "entries": []}), encoding="utf-8")
        for defect in ("unknown_assignment", "missing_store", "unsupported_version", "unknown_link"):
            if defect != "unknown_assignment": (directory/"UNKNOWN.json").unlink()
            if defect == "missing_store":
                secondary = self.plane.parent/"fast_lane_research_data_plane"
                secondary.rename(self.plane.parent/"temporarily-missing-secondary")
            if defect == "unsupported_version":
                from tests.test_opportunity_episodes_harness_v1 import ASSIGNMENT_ID
                path = directory/(ASSIGNMENT_ID+".json")
                broken = json.loads(path.read_bytes()); broken["schema_version"] = "99.0"
                (directory/"UNKNOWN.json").write_text(json.dumps(broken), encoding="utf-8")
            if defect == "unknown_link":
                declaration = CurrentProtectionTests(); declaration.store = self.store
                declaration.append_native_critic({"schema": "smial.hypothesis-critic-result", "schema_version": "1.1"},
                    name="RUNNER-UNKNOWN-LINK", header={"assignment_sources": [{"owner": "UNKNOWN", "ref": "UNKNOWN_SCOPE"}]})
            with patch.object(discovery, "load_admitted_partition_rows", side_effect=AssertionError("unsafe value loader")) as sentinel:
                refused = f.run_due(self.store, repo_root=ROOT, git_sha=GIT_SHA)
            report = refused["fragments"][0]
            self.assertEqual(report["reason"], "HOLDOUT_UNRESOLVED", report)
            self.assertTrue(report["source_reason"])
            self.assertEqual(report["source_ref"], "research-record://RUNNER-UNKNOWN-LINK" if defect == "unknown_link" else
                "smial-data://fast_lane_researchstore" if defect == "missing_store" else "protection/assignments/UNKNOWN.json")
            self.assertFalse(report["values_loaded"])
            if defect == "unknown_link":
                self.assertEqual(report["source_reason"], "PROTECTION_DECLARATION_OWNER_UNSUPPORTED")
                self.assertEqual(report["observed_form"], "CRITIC_RESULT")
            if defect == "unsupported_version":
                self.assertEqual(report["observed_version"], "99.0")
                self.assertEqual(report["source_reason"], "PROTECTION_ASSIGNMENT_VERSION_UNKNOWN")
            sentinel.assert_not_called()
            self.assertEqual(operations.journal_occupancy(self.store, f.journal_for(self.card["fragment_version_id"]))["main"], occupancy)
            if defect == "missing_store":
                (self.plane.parent/"temporarily-missing-secondary").rename(secondary)
                (directory/"UNKNOWN.json").write_text(json.dumps({"schema": "UNKNOWN", "entries": []}), encoding="utf-8")
        paused = f.plan_preview(self.store, {**plan_request, "enabled": False})
        self.assertEqual(paused["current_protection"]["status"], "UNRESOLVED_SCOPE")
        f.apply_plan(self.store, paused, git_sha=GIT_SHA)
        view = f.source_snapshot(self.store)[0]
        self.assertEqual(view["check"]["status"], "DISABLED")
        self.assertEqual(view["source"]["result_sha256"], evidence["result_sha256"])
        self.assertEqual(operations.journal_occupancy(self.store, f.journal_for(self.card["fragment_version_id"]))["main"]["pending"], 1)


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




class CurrentProtectionTests(unittest.TestCase):
    """Small source/installer oracles; the existing vertical owns evaluation."""
    def setUp(self):
        import tempfile
        from solana_alpha_lab.factory import episode_current_protection as protection
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name); self.plane = self.work / "plane"
        self.store = ResearchStore(self.plane)
        ResearchStore(self.work / "fast_lane_research_data_plane")
        self.p = protection

    def preview(self, *, repo_root=None):
        return self.p.preview_reconciliation(self.plane, repo_root=repo_root)

    def apply(self, preview, *, repo_root=None):
        authority = {"proposal_sha256": preview["proposal_sha256"], "read_scope": preview["proposal"]["read_scope"],
            "source_frontier_sha256": canonical_sha256(preview["proposal"]["source_frontier"]),
            "mutation": "VERSIONED_PROTECTION_METADATA_ONLY", "owner_scope_ref": "SYNTHETIC_METADATA_ONLY"}
        return self.p.apply_reconciliation(self.store, preview, authority=authority, repo_root=repo_root)

    def metadata_repo(self):
        """Actual source closure only: no checkout, market partitions or fake collector."""
        repo = self.work / "metadata-repo"
        refs = [self.p.CONFIG, "registries/holdout_consumption.yaml",
            "docs/evidence/task22/a6_split_resolution_acceptance_catalog_factory_fit_v1.json",
            "docs/evidence/task22/dataset_split_manifest_v2.json",
            "docs/evidence/task22/holdout_access_ledger_v1.json",
            "docs/evidence/task22/holdout_access_ledger_v2.json",
            "configs/task22_task23_consumer_time_profile_v1.yaml",
            "configs/list_a_chronological_confirmation_v1.yaml"]
        refs += ["catalog/schemas/experiment_spec_v1_1.schema.json", "catalog/schemas/experiment_spec.schema.json", "catalog/schemas/experiment_spec_v1_4.schema.json", "catalog/schemas/experiment_spec_v1_5.schema.json"]
        refs += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT/"configs/experiment_specs").iterdir())]
        for ref in refs:
            target = repo/ref; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT/ref, target)
        self.assertLess(sum(p.stat().st_size for p in repo.rglob("*") if p.is_file()), 1_048_576)
        self.assertFalse((repo/".git").exists())
        return repo

    def test_native_policy_change_and_scope_extension_keep_current_protection(self):
        from solana_alpha_lab.factory import hfic_research_policy as policy
        self.apply(self.preview()); pointer = (self.plane/self.p.POINTER).read_bytes()
        change = policy.preview_policy_change(self.store, limits_delta={"main_total": 7})
        policy.apply_policy_change(self.store, proposal=change["proposal"], confirm_append_only=True)
        status, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["status"], "ALLOW", status)
        scope = "a1"*32
        policy.ensure_scope_snapshot(self.store, scope)
        extension = policy.propose_run_extension(self.store, scope_key=scope,
            parent_operation_sha256="1"*64, limits_delta={"main_total": 8})
        policy.apply_run_extension(self.store, proposal=extension, confirm_append_only=True)
        status, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["status"], "ALLOW", status)
        self.assertEqual(policy.limits_for_frozen_run(self.store, scope)["main_total"], 8)
        self.assertEqual((self.plane/self.p.POINTER).read_bytes(), pointer)

    def test_new_supported_spec_instance_revalidates_without_installation(self):
        repo = self.metadata_repo()
        self.apply(self.preview(repo_root=repo), repo_root=repo)
        before, _ = self.p.resolve_current_research_protection(self.plane, repo_root=repo)
        pointer = (self.plane/self.p.POINTER).read_bytes()
        ref = "configs/experiment_specs/another_supported_question_v1.yml"
        import yaml
        spec = yaml.safe_load((repo/"configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml").read_bytes())
        spec["experiment_id"] = "EXP-ANOTHER-SUPPORTED-QUESTION-V1"
        spec["question"] = "A new question using the same supported protection meaning."
        (repo/ref).write_text(yaml.safe_dump(spec), encoding="utf-8")
        shutil.copy2(repo/ref, repo/"configs/experiment_specs/another_supported_copy.yaml")
        after, _ = self.p.resolve_current_research_protection(self.plane, repo_root=repo)
        self.assertEqual(after["status"], "ALLOW", after)
        self.assertEqual(after["installed_assignment_sha256"], before["installed_assignment_sha256"])
        self.assertEqual(after["inventory_sha256"], before["inventory_sha256"])
        self.assertNotEqual(after["context_sha256"], before["context_sha256"])
        source = next(s for s in after["sources"] if s["owner"] == "EXPERIMENT_POLICIES")
        self.assertIn(ref, [d["ref"] for d in source["policy_refs"]])
        real_iterdir = Path.iterdir
        def reordered(directory):
            entries = list(real_iterdir(directory))
            return iter(reversed(entries)) if directory == repo/"configs/experiment_specs" else iter(entries)
        with patch.object(Path, "iterdir", reordered):
            again, _ = self.p.resolve_current_research_protection(self.plane, repo_root=repo)
        self.assertEqual(after, again)
        self.assertEqual((self.plane/self.p.POINTER).read_bytes(), pointer)

    def test_native_legacy_decision_entity_identity_is_not_unknown_protection(self):
        from tests.test_hfic_critic_prior_memory_closure_v1 import _event
        from solana_alpha_lab.factory.research_store import RecordKind
        self.apply(self.preview()); pointer = (self.plane/self.p.POINTER).read_bytes()
        body = {"hypothesis_version_id": "HYP-NATIVE-LEGACY", "decision_kind": "PARK", "reason_code": "PARK_UNTIL_EVIDENCE"}
        at = datetime.now(UTC)
        event = _event(record_id="LEGACY-DECISION", kind=RecordKind.DECISION_EVENT,
            entity_id="LEGACY-DECISION", hypothesis_version_id="HYP-NATIVE-LEGACY", payload=body, created=at)
        self.store.append([event], transaction_id=event.transaction_id)
        status, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["status"], "ALLOW", status)
        self.assertEqual((self.plane/self.p.POINTER).read_bytes(), pointer)
        bad = _event(record_id="LEGACY-DECISION-UNKNOWN-LINK", kind=RecordKind.DECISION_EVENT,
            entity_id="LEGACY-DECISION-UNKNOWN-LINK", hypothesis_version_id="HYP-NATIVE-LEGACY",
            payload={**body, "assignment_sources": ["UNKNOWN"]}, created=at,
            transaction_id="RESEARCH-TXN-LEGACY-UNKNOWN")
        self.store.append([bad], transaction_id=bad.transaction_id)
        self.assertEqual(self.p.resolve_current_research_protection(self.plane)[0]["reason"], "PROTECTION_DECLARATION_OWNER_UNSUPPORTED")

    def test_different_known_spec_aliases_in_one_record_are_unresolved(self):
        import yaml
        from tests.test_fast_lane_runner import offline_v1_1_spec
        self.apply(self.preview()); pointer = (self.plane/self.p.POINTER).read_bytes()
        config = yaml.safe_load((ROOT/self.p.CONFIG).read_bytes())
        episode = {"schema": "smial.experiment-spec", "schema_version": "1.4", "population": "OPPORTUNITY_EPISODES",
            "holdout_policy": config["embedded_exploratory_policy"],
            "observation_request": {"collection_mode": "REUSE_ONLY", "requested_evidence_role": "EXPLORATORY_REUSE"}}
        self.append_native_critic({"schema": "smial.hypothesis-critic-result", "schema_version": "1.1",
            "experiment_spec": offline_v1_1_spec(), "experiment_spec_packet": episode}, name="DUAL-KNOWN-DIFFERENT-MEANINGS")
        status, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["reason"], "PROTECTION_EXPERIMENT_DECLARATION_UNKNOWN")
        self.assertEqual(status["source_ref"], "research-record://DUAL-KNOWN-DIFFERENT-MEANINGS")
        self.assertIsNone(status["complete_empty"])
        self.assertEqual((self.plane/self.p.POINTER).read_bytes(), pointer)

    def test_nested_spec_envelope_unknown_authority_and_version_are_not_discarded(self):
        import yaml
        config = yaml.safe_load((ROOT/self.p.CONFIG).read_bytes())
        spec = {"schema": "smial.experiment-spec", "schema_version": "1.4", "population": "OPPORTUNITY_EPISODES",
            "holdout_policy": config["embedded_exploratory_policy"],
            "observation_request": {"collection_mode": "REUSE_ONLY", "requested_evidence_role": "EXPLORATORY_REUSE"}}
        for alias in ("experiment_spec", "experiment_spec_packet"):
            for key, value, reason in (("assignment_sources", [{"owner": "UNKNOWN", "ref": "UNKNOWN_SCOPE"}], "PROTECTION_DECLARATION_OWNER_UNSUPPORTED"),
                    ("holdout_consumption_ids", ["UNKNOWN"], "PROTECTION_CONSUMPTION_LINK_UNRESOLVED"),
                    ("schema_version", "99.0", "PROTECTION_DECLARATION_VERSION_UNKNOWN"),
                    ("prompt_version", "UNKNOWN", "PROTECTION_DECLARATION_VERSION_UNKNOWN")):
                with self.subTest(alias=alias, key=key):
                    name = (alias+"-"+key).upper()
                    self.store = ResearchStore(self.work/name)
                    self.append_native_critic({"schema": "smial.hypothesis-critic-result", "schema_version": "1.1",
                        alias: {"experiment_spec": spec, key: value}}, name=name)
                    status, _ = self.p.resolve_current_research_protection(self.store.root)
                    self.assertEqual(status["reason"], reason, status)
                    self.assertEqual(status["source_ref"], "research-record://"+name)
                    if key in {"schema_version", "prompt_version"}:
                        self.assertEqual(status["observed_version"], value)
                    self.assertIsNone(status["complete_empty"])
                    self.assertFalse(status["values_loaded"])
                    self.assertFalse((self.store.root/self.p.POINTER).exists())

    def test_pointer_cas_conflict_requests_fresh_preview_and_keeps_winner(self):
        first = self.preview(); winner = self.preview()
        self.assertNotEqual(first["proposal_sha256"], winner["proposal_sha256"])
        self.apply(winner); pointer = (self.plane/self.p.POINTER).read_bytes()
        with self.assertRaisesRegex(self.p.CurrentProtectionError, "PROTECTION_HEAD_CHANGED") as caught:
            self.apply(first)
        self.assertEqual(caught.exception.detail["source_ref"], self.p.POINTER)
        self.assertEqual(caught.exception.detail["next_action"], "REFRESH_SOURCE_STATUS_AND_PREVIEW")
        self.assertEqual((self.plane/self.p.POINTER).read_bytes(), pointer)
        self.assertEqual(self.p.resolve_current_research_protection(self.plane)[0]["status"], "ALLOW")
        fresh = self.preview()
        self.assertEqual(fresh["status"], "UNCHANGED")
        self.assertNotIn("proposal", fresh)
        self.assertEqual(fresh["current"]["proposal_sha256"], winner["proposal_sha256"])

    def test_missing_baseline_declaration_names_the_lost_record(self):
        import yaml
        config = yaml.safe_load((ROOT/self.p.CONFIG).read_bytes())
        self.append_native_critic({"schema": "smial.hypothesis-critic-result", "schema_version": "1.1",
            "experiment_spec": {"schema": "smial.experiment-spec", "schema_version": "1.4", "population": "OPPORTUNITY_EPISODES",
                "holdout_policy": config["embedded_exploratory_policy"],
                "observation_request": {"collection_mode": "REUSE_ONLY", "requested_evidence_role": "EXPLORATORY_REUSE"}}}, name="BASELINE-SPEC")
        self.apply(self.preview()); pointer = (self.plane/self.p.POINTER).read_bytes()
        # Simulate loss of the committed record namespace, never manufacture ALLOW.
        real = self.p._store_projection
        with patch.object(self.p, "_store_projection", lambda root, config, repo: [] if root == self.plane else real(root, config, repo)):
            status, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["reason"], "PROTECTION_BASELINE_SOURCE_MISSING")
        self.assertEqual(status["owner"], "CANONICAL_RESEARCHSTORE")
        self.assertEqual(status["source_ref"], "research-record://BASELINE-SPEC")
        self.assertIsNone(status["complete_empty"])
        self.assertEqual((self.plane/self.p.POINTER).read_bytes(), pointer)

    def test_native_legacy_spec_binding_version_preserves_known_policy_meaning(self):
        from tests.test_fast_lane_runner import offline_v1_1_spec
        self.apply(self.preview()); pointer = (self.plane/self.p.POINTER).read_bytes()
        spec = offline_v1_1_spec()
        self.append_native_critic({"schema": "smial.hypothesis-critic-result", "schema_version": "1.1",
            "experiment_spec_packet": {"experiment_spec": spec}}, name="NATIVE-SPEC-11")
        status, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["status"], "ALLOW", status)
        self.assertEqual((self.plane/self.p.POINTER).read_bytes(), pointer)
        spec["holdout_policy"] = "UNKNOWN_RESERVED_HOLDOUT"
        self.append_native_critic({"schema": "smial.hypothesis-critic-result", "schema_version": "1.1",
            "experiment_spec_packet": {"experiment_spec": spec}}, name="NATIVE-SPEC-11-UNKNOWN")
        refused, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(refused["reason"], "PROTECTION_EXPERIMENT_DECLARATION_UNKNOWN")
        self.assertEqual(refused["observed_version"], "1.1")
        self.assertEqual(refused["source_ref"], "research-record://NATIVE-SPEC-11-UNKNOWN")

    def test_historical_copy_is_not_current_and_proven_empty_is_stable(self):
        from tests.test_opportunity_episodes_harness_v1 import write_assignment
        from solana_alpha_lab.factory.opportunity_episodes import inventory_from_documents
        pin = write_assignment(self.plane, [])
        doc = json.loads((self.plane / "protection/assignments" / (pin["assignment_id"] + ".json")).read_bytes())
        self.assertEqual(inventory_from_documents([doc]).status, "ALLOW")
        status, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["reason"], "CURRENT_PROTECTION_NOT_INSTALLED")
        self.assertIsNone(status["complete_empty"])
        preview = self.preview(); self.assertTrue(preview["assessment"]["complete_empty"])
        first = self.apply(preview); self.assertEqual(first["status"], "APPLIED")
        self.assertEqual(self.apply(preview)["receipt"], first["receipt"])
        status, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["status"], "ALLOW")
        self.assertEqual(self.preview()["status"], "UNCHANGED")
        from datetime import datetime as RealDatetime
        class Tomorrow(RealDatetime):
            @classmethod
            def now(cls, tz=None):
                return RealDatetime.now(tz) + timedelta(days=1)
        with patch.object(self.p, "datetime", Tomorrow):
            tomorrow, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["context_sha256"], tomorrow["context_sha256"])
        self.assertEqual(status["installed_assignment_sha256"], tomorrow["installed_assignment_sha256"])

    def test_source_change_cas_deny_and_missing_owner(self):
        from tests.test_opportunity_episodes_harness_v1 import write_assignment
        from solana_alpha_lab.factory.opportunity_episodes import protection_decision
        preview = self.preview()
        write_assignment(self.plane, [{"identity_kind": "MINT", "identity": "ProtectedSyntheticMint",
            "role": "UNTOUCHED_FORWARD_HOLDOUT", "scope": {"kind": "ALL_TIME"}}])
        with self.assertRaisesRegex(self.p.CurrentProtectionError, "PROTECTION_SOURCE_CHANGED"):
            self.apply(preview)
        self.assertFalse((self.plane / self.p.POINTER).exists())
        self.apply(self.preview())
        status, inventory = self.p.resolve_current_research_protection(self.plane)
        self.assertFalse(status["complete_empty"])
        at = datetime.now(UTC)
        self.assertEqual(protection_decision(inventory, "ProtectedSyntheticMint", interval_start=at, interval_end=at+timedelta(days=1))[0], "DENY_PROTECTED")
        (self.work / "fast_lane_research_data_plane").rename(self.work / "missing-secondary")
        status, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["status"], "UNRESOLVED_SCOPE")
        self.assertEqual(status["owner"], "FAST_LANE_RESEARCHSTORE")
        self.assertIsNone(status["complete_empty"])

    def test_baseline_disappearance_revocation_and_scalar_scope_are_unresolved(self):
        from tests.test_opportunity_episodes_harness_v1 import write_assignment, ASSIGNMENT_ID
        entry = {"identity_kind": "MINT", "identity": "BaselineSyntheticDeny",
                 "role": "UNTOUCHED_FORWARD_HOLDOUT", "scope": {"kind": "ALL_TIME"}}
        write_assignment(self.plane, [entry]); self.apply(self.preview())
        path = self.plane / self.p.ASSIGNMENT_DIR / (ASSIGNMENT_ID + ".json")
        original = path.read_bytes(); path.unlink()
        status, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["reason"], "PROTECTION_BASELINE_SOURCE_MISSING")
        self.assertEqual(status["source_ref"], self.p.ASSIGNMENT_DIR+"/"+ASSIGNMENT_ID+".json")
        self.assertIsNone(status["complete_empty"])
        path.write_bytes(original); write_assignment(self.plane, [])
        status, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["reason"], "PROTECTION_BASELINE_RESTRICTION_REMOVED")
        write_assignment(self.plane, [{**entry, "scope": "UNKNOWN_SCALAR"}])
        status, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["reason"], "PROTECTION_SCOPE_UNKNOWN")
        self.assertEqual(status["owner"], "LOCAL_ASSIGNMENTS")
        self.assertIsNone(status["complete_empty"])

    def test_unknown_native_owner_and_opaque_form_are_not_empty(self):
        import hashlib
        from solana_alpha_lab.factory.research_store import ResearchEvent, RecordKind
        at = datetime.now(UTC)
        for ordinal, producer in enumerate(("CAP-UNKNOWN-PROTECTION-OWNER", "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001")):
            root = self.work / ("unknown" + str(ordinal)); store = ResearchStore(root)
            payload = json.dumps({"protection_declaration": {"assignment_sources": ["UNRESOLVED"]}}, sort_keys=True, separators=(",", ":"))
            event = ResearchEvent(record_id="UNKNOWN-DECLARATION", record_kind=RecordKind.RESEARCH_ARTIFACT,
                entity_id="UNKNOWN-DECLARATION", hypothesis_version_id=None, run_id=None,
                transaction_id="RESEARCH-TXN-UNKNOWN", effective_at=at, first_reliable_available_at=at,
                supersedes_record_id=None, payload_json=payload, payload_sha256=hashlib.sha256(payload.encode()).hexdigest(),
                schema_version="1.0", producer_capability_id=producer, producer_git_sha=GIT_SHA, created_at=at)
            store.append([event], transaction_id=event.transaction_id)
            status, _ = self.p.resolve_current_research_protection(root)
            self.assertEqual(status["reason"], "PROTECTION_DECLARATION_OWNER_UNKNOWN" if ordinal == 0 else "PROTECTION_DECLARATION_FORM_UNKNOWN")
            self.assertEqual(status["owner"], "CANONICAL_RESEARCHSTORE")
            self.assertIsNone(status["complete_empty"])

    def test_unknown_native_packet_version_is_unresolved(self):
        import hashlib
        from solana_alpha_lab.factory.research_store import ResearchEvent, RecordKind
        body = {"packet_schema": "smial.hypothesis-forge-draft", "packet_version": "UNKNOWN",
                "candidates": []}
        payload = json.dumps({"artifact_kind": "FORGE_DRAFT", "payload_canonical": json.dumps(body, sort_keys=True, separators=(",", ":"))},
                             sort_keys=True, separators=(",", ":"))
        at = datetime.now(UTC)
        event = ResearchEvent(record_id="UNKNOWN-VERSION", record_kind=RecordKind.RESEARCH_ARTIFACT,
            entity_id="UNKNOWN-VERSION", hypothesis_version_id=None, run_id=None,
            transaction_id="RESEARCH-TXN-UNKNOWN-VERSION", effective_at=at, first_reliable_available_at=at,
            supersedes_record_id=None, payload_json=payload, payload_sha256=hashlib.sha256(payload.encode()).hexdigest(),
            schema_version="1.0", producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001", producer_git_sha=GIT_SHA, created_at=at)
        self.store.append([event], transaction_id=event.transaction_id)
        status, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["reason"], "PROTECTION_DECLARATION_VERSION_UNKNOWN")
        self.assertEqual(status["source_ref"], "research-record://UNKNOWN-VERSION")
        self.assertEqual(status["observed_version"], "UNKNOWN")
        self.assertIsNone(status["complete_empty"])

    def append_native_critic(self, body, *, name, form="CRITIC_RESULT", header=None):
        import hashlib
        from solana_alpha_lab.factory.research_store import ResearchEvent, RecordKind
        raw_body = json.dumps(body, sort_keys=True, separators=(",", ":"))
        payload = json.dumps({"artifact_kind": form, "payload_canonical": raw_body, **(header or {})}, sort_keys=True, separators=(",", ":"))
        at = datetime.now(UTC)
        event = ResearchEvent(record_id=name, record_kind=RecordKind.RESEARCH_ARTIFACT, entity_id=name,
            hypothesis_version_id=None, run_id=None, transaction_id="RESEARCH-TXN-"+name,
            effective_at=at, first_reliable_available_at=at, supersedes_record_id=None,
            payload_json=payload, payload_sha256=hashlib.sha256(payload.encode()).hexdigest(), schema_version="1.0",
            producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001", producer_git_sha=GIT_SHA, created_at=at)
        self.store.append([event], transaction_id=event.transaction_id)

    def test_native_spec_packet_aliases_revalidate_and_conflict_is_not_empty(self):
        import yaml
        config = yaml.safe_load((ROOT/self.p.CONFIG).read_text(encoding="utf-8"))
        spec = {"schema": "smial.experiment-spec", "schema_version": "1.4", "population": "OPPORTUNITY_EPISODES",
                "holdout_policy": config["embedded_exploratory_policy"],
                "observation_request": {"collection_mode": "REUSE_ONLY", "requested_evidence_role": "EXPLORATORY_REUSE"}}
        self.apply(self.preview()); original = (self.plane/self.p.POINTER).read_bytes()
        inventory_before = self.p.resolve_current_research_protection(self.plane)[0]["inventory_sha256"]
        for ordinal, (field, wrapped) in enumerate((("experiment_spec", False), ("experiment_spec", True), ("experiment_spec_packet", False), ("experiment_spec_packet", True))):
            body = {"schema": "smial.hypothesis-critic-result", "schema_version": "1.1",
                    field: {"experiment_spec": spec} if wrapped else spec}
            self.append_native_critic(body, name="KNOWN-SPEC-"+str(ordinal))
            status, _ = self.p.resolve_current_research_protection(self.plane)
            self.assertEqual(status["status"], "ALLOW")
            self.assertEqual((self.plane/self.p.POINTER).read_bytes(), original)
            # New service declarations must not change an unchanged protection
            # meaning or invalidate an already stored scientific binding.
            self.assertEqual(status["inventory_sha256"], inventory_before)
        body = {"schema": "smial.hypothesis-critic-result", "schema_version": "1.1", "experiment_spec": spec,
                "experiment_spec_packet": {"experiment_spec": {**spec, "holdout_policy": "UNRESOLVED_RESTRICTION"}}}
        self.append_native_critic(body, name="CONFLICT-SPEC")
        status, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["reason"], "PROTECTION_EXPERIMENT_DECLARATION_UNKNOWN")
        self.assertIsNone(status["complete_empty"])

    def test_wrapper_body_identity_and_wrapper_version_are_consistent(self):
        body = {"schema": "smial.hfic-scientific-disposition", "schema_version": "1.0"}
        self.append_native_critic(body, name="BAD-FORM", form="FORGE_DRAFT", header={"hfic_protocol": "UNKNOWN"})
        status, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["reason"], "PROTECTION_DECLARATION_FORM_UNKNOWN")
        self.assertIsNone(status["complete_empty"])

    def test_unknown_wrapper_protocol_version_is_unresolved(self):
        body = {"packet_schema": "smial.hypothesis-forge-draft", "packet_version": "1.3", "candidates": []}
        self.append_native_critic(body, name="BAD-WRAPPER-VERSION", form="FORGE_DRAFT", header={"hfic_protocol": "UNKNOWN"})
        status, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["reason"], "PROTECTION_DECLARATION_VERSION_UNKNOWN")
        self.assertIsNone(status["complete_empty"])

    def test_unknown_unmarked_native_body_version_is_unresolved(self):
        import hashlib
        from solana_alpha_lab.factory.research_store import ResearchEvent, RecordKind
        self.apply(self.preview()); pointer = (self.plane/self.p.POINTER).read_bytes()
        payload = json.dumps({"hypothesis_version_id": "SYNTHETIC-HV", "schema_version": "99.0"}, sort_keys=True, separators=(",", ":"))
        at = datetime.now(UTC)
        event = ResearchEvent(record_id="UNKNOWN-HV-BODY-VERSION", record_kind=RecordKind.HYPOTHESIS_VERSION,
            entity_id="SYNTHETIC-HV", hypothesis_version_id="SYNTHETIC-HV", run_id=None,
            transaction_id="RESEARCH-TXN-UNKNOWN-HV", effective_at=at, first_reliable_available_at=at,
            supersedes_record_id=None, payload_json=payload, payload_sha256=hashlib.sha256(payload.encode()).hexdigest(),
            schema_version="1.0", producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001", producer_git_sha=GIT_SHA, created_at=at)
        self.store.append([event], transaction_id=event.transaction_id)
        status, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["status"], "UNRESOLVED_SCOPE")
        self.assertEqual(status["reason"], "PROTECTION_DECLARATION_VERSION_UNKNOWN")
        self.assertEqual(status["owner"], "CANONICAL_RESEARCHSTORE")
        self.assertIsNone(status["complete_empty"])
        self.assertEqual((self.plane/self.p.POINTER).read_bytes(), pointer)

    def test_wrapper_authoritative_link_is_not_empty(self):
        self.apply(self.preview())
        self.append_native_critic({"schema": "smial.hypothesis-critic-result", "schema_version": "1.1"},
            name="WRAPPER-UNKNOWN-AUTHORITY", header={"assignment_sources": [{"owner": "UNKNOWN", "ref": "UNKNOWN_SCOPE"}]})
        status, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["reason"], "PROTECTION_DECLARATION_OWNER_UNSUPPORTED")
        self.assertEqual(status["owner"], "CANONICAL_RESEARCHSTORE")
        self.assertIsNone(status["complete_empty"])

    def test_malformed_or_foreign_derived_receipt_cannot_hide_as_output(self):
        self.apply(self.preview())
        snapshot = self.p.collect_current_sources(self.plane)
        for ordinal, defect in enumerate(("owner", "read_scope", "context", "entries")):
            doc = self.p._document(snapshot, checked_at=(datetime.now(UTC)-timedelta(seconds=ordinal+1)).isoformat(), predecessor=None)
            if defect == "owner": doc["owner"] = "UNKNOWN_FOREIGN_OWNER"
            elif defect == "read_scope": doc["completeness"].pop("read_scope")
            elif defect == "context": doc["completeness"]["source_set_sha256"] = "0"*64
            else: doc["entries"] = [{"identity_kind": "MINT", "identity": "SyntheticUnknown", "scope": {"kind": "UNKNOWN"}}]
            path = self.plane/self.p.ASSIGNMENT_DIR/(doc["assignment_id"]+".json")
            path.write_text(json.dumps(doc), encoding="utf-8")
            try:
                with self.subTest(defect=defect):
                    status, _ = self.p.resolve_current_research_protection(self.plane)
                    self.assertEqual(status["status"], "UNRESOLVED_SCOPE")
                    self.assertEqual(status["owner"], "LOCAL_ASSIGNMENTS")
                    self.assertIsNone(status["complete_empty"])
            finally: path.unlink()
        self.assertEqual(self.p.resolve_current_research_protection(self.plane)[0]["status"], "ALLOW")

    def test_spec_unknown_role_binding_and_baseline_deletion_replacement_fail_closed(self):
        import yaml
        repo = self.metadata_repo(); self.apply(self.preview(repo_root=repo), repo_root=repo)
        ref = "configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml"
        path = repo/ref; original = path.read_bytes()
        for defect in ("role", "policy", "replacement", "deletion"):
            value = yaml.safe_load(original)
            if defect == "role": value["observation_request"] = {"collection_mode": "REUSE_ONLY", "requested_evidence_role": "UNKNOWN"}
            elif defect == "policy": value["holdout_policy"] = "UNKNOWN_RESERVED_ASSIGNMENT"
            elif defect == "replacement": value["question"] += " changed"
            if defect == "deletion": path.unlink()
            else: path.write_text(yaml.safe_dump(value), encoding="utf-8")
            status, _ = self.p.resolve_current_research_protection(self.plane, repo_root=repo)
            with self.subTest(defect=defect):
                self.assertEqual(status["status"], "UNRESOLVED_SCOPE")
                self.assertEqual(status["source_ref"], ref)
                self.assertIsNone(status["complete_empty"])
            path.write_bytes(original)
        ref = "configs/experiment_specs/list_a_chronological_confirmation_v1.yaml"
        path = repo/ref; value = yaml.safe_load(path.read_bytes())
        value["parameters"]["protocol_core_sha256"] = "0"*64
        path.write_text(yaml.safe_dump(value), encoding="utf-8")
        status, _ = self.p.resolve_current_research_protection(self.plane, repo_root=repo)
        self.assertEqual(status["source_reason"], "EXPERIMENT_POLICY_INTERPRETATION_UNKNOWN")
        self.assertEqual(status["source_ref"], ref)

    def test_recovery_detail_missing_file_unknown_record_and_version(self):
        unsafe = self.p.CurrentProtectionError("PROTECTION_SOURCE_UNAVAILABLE",
            source_ref="C:/private/source", observed_form="https://private.invalid/source").detail
        self.assertNotIn("private", json.dumps(unsafe))
        repo = self.metadata_repo(); self.apply(self.preview(repo_root=repo), repo_root=repo)
        missing_ref = "registries/holdout_consumption.yaml"
        (repo/missing_ref).unlink()
        missing, _ = self.p.resolve_current_research_protection(self.plane, repo_root=repo)
        self.assertEqual(missing["source_ref"], missing_ref)
        self.assertEqual(missing["source_reason"], "PROTECTION_SOURCE_UNAVAILABLE")
        self.assertEqual(missing["next_action"], "RESTORE_OR_REPAIR_NAMED_SOURCE_THEN_RETRY")
        shutil.copy2(ROOT/missing_ref, repo/missing_ref)
        self.append_native_critic({"schema": "smial.hypothesis-critic-result", "schema_version": "1.1"},
            name="DETAIL-UNKNOWN-LINK", header={"assignment_sources": [{"owner": "UNKNOWN", "ref": "UNKNOWN_SCOPE"}]})
        unknown, _ = self.p.resolve_current_research_protection(self.plane, repo_root=repo)
        self.assertEqual(unknown["source_ref"], "research-record://DETAIL-UNKNOWN-LINK")
        self.assertEqual(unknown["observed_form"], "CRITIC_RESULT")
        self.assertEqual(unknown["observed_version"], "1.1")
        self.assertEqual(unknown["next_action"], "RESOLVE_NAMED_AUTHORITY_INTERPRETATION")

    def test_ungranted_authority_draft_cannot_install(self):
        preview = self.preview()
        authority = {"proposal_sha256": preview["proposal_sha256"], "read_scope": preview["proposal"]["read_scope"],
            "source_frontier_sha256": canonical_sha256(preview["proposal"]["source_frontier"]),
            "mutation": "VERSIONED_PROTECTION_METADATA_ONLY", "owner_scope_ref": "OWNER_APPROVAL_REQUIRED_NOT_GRANTED"}
        with self.assertRaisesRegex(self.p.CurrentProtectionError, "PROTECTION_INSTALLATION_AUTHORITY_REQUIRED"):
            self.p.apply_reconciliation(self.store, preview, authority=authority)
        self.assertFalse((self.plane/self.p.POINTER).exists())
        self.assertFalse((self.plane/self.p.ASSIGNMENT_DIR).exists())

    def test_cli_relative_root_recovers_input_without_requesting_scope(self):
        result = subprocess.run([sys.executable, "-B", str(ROOT/"scripts/research_fragments.py"),
            "protection-status", "--data-root", "relative"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["reason"], "FRAGMENT_ABSOLUTE_DATA_ROOT_REQUIRED")
        self.assertEqual(body["owner"], "INPUT")
        self.assertEqual(body["next_action"], "CORRECT_ABSOLUTE_DATA_ROOT")

    def test_task22_scope_requires_actual_time_nonintersection(self):
        from solana_alpha_lab.factory.opportunity_episodes import LOGICAL_DATASET_ID
        self.apply(self.preview())
        status, _ = self.p.resolve_current_research_protection(self.plane)
        binding = {"dataset_id": LOGICAL_DATASET_ID, "evidence_role": "EXPLORATORY_REUSE",
                   "cohort_id": "REL-20261007T000000Z-20261008T000000Z"}
        self.p.assert_input_scope(status, [binding])
        with self.assertRaisesRegex(self.p.CurrentProtectionError, "TASK22_SOURCE_OVERLAP_LINK_UNRESOLVED"):
            self.p.assert_input_scope(status, [{**binding, "cohort_id": "REL-20260801T000000Z-20260802T000000Z"}])

    def test_crash_before_and_after_pointer_retries_same_effect(self):
        preview = self.preview()
        with patch.object(self.p.os, "replace", side_effect=InterruptedError("synthetic crash before pointer")):
            with self.assertRaises(InterruptedError): self.apply(preview)
        self.assertFalse((self.plane / self.p.POINTER).exists())
        applied = self.apply(preview)
        self.assertEqual(self.apply(preview)["receipt"], applied["receipt"])
        self.assertEqual(len(list((self.plane / "protection/assignments").glob("CURRENT-RESEARCH-*.json"))), 1)
        from tests.test_opportunity_episodes_harness_v1 import write_assignment
        write_assignment(self.plane, [])
        second = self.preview()
        real_replace = self.p.os.replace
        def publish_then_crash(source, target):
            real_replace(source, target)
            raise InterruptedError("synthetic crash after pointer")
        with patch.object(self.p.os, "replace", side_effect=publish_then_crash):
            with self.assertRaises(InterruptedError): self.apply(second)
        self.assertEqual(self.apply(second)["status"], "ALREADY_APPLIED")
        self.assertEqual(len(list((self.plane / "protection/assignments").glob("CURRENT-RESEARCH-*.json"))), 2)

    def test_ambiguous_scope_and_transplanted_proof_fail_closed(self):
        from tests.test_opportunity_episodes_harness_v1 import write_assignment
        self.apply(self.preview())
        other = self.work / "other"; other.mkdir()
        shutil.copytree(self.plane / "protection", other / "protection")
        status, _ = self.p.resolve_current_research_protection(other)
        self.assertEqual(status["reason"], "CURRENT_PROTECTION_BINDING_INVALID")
        write_assignment(self.plane, [{"identity_kind": "MINT", "identity": "AmbiguousSyntheticMint",
            "role": "UNTOUCHED_FORWARD_HOLDOUT", "scope": {"kind": "UNKNOWN"}}])
        status, _ = self.p.resolve_current_research_protection(self.plane)
        self.assertEqual(status["reason"], "PROTECTION_SCOPE_UNKNOWN")
        self.assertEqual(status["owner"], "LOCAL_ASSIGNMENTS")
        self.assertIsNone(status["complete_empty"])

class FrozenArchiveFingerprintTests(unittest.TestCase):
    def test_summary_readout_projection_keeps_frozen_view_fingerprint(self):
        # A view frozen before the shelf summary gained readout projections
        # must still match; a material change of the bound result must not.
        from solana_alpha_lab.factory.hfic_generation_context import archive_fingerprint
        block = {"kind": "DISCOVERY", "result_sha256": "a" * 64, "summary": {"matched": {"n": 5}}}
        frozen = {"capsules": [{"hypothesis_version_id": "HFIC-CAND-X", "source_detail": {
            "research_fragments": [{"fragment_version_id": "RFV-X", "evidence_blocks": [block]}]}}]}
        later = copy.deepcopy(frozen)
        later["capsules"][0]["source_detail"]["research_fragments"][0]["evidence_blocks"][0]["summary"].update(
            research_scope={"contrast": {"comparator": {"n": 7}}}, scientific_identity={"research_scope_rule_sha256": "b" * 64})
        self.assertEqual(archive_fingerprint(later), archive_fingerprint(frozen))
        self.assertIn("research_scope", later["capsules"][0]["source_detail"]["research_fragments"][0]["evidence_blocks"][0]["summary"])
        changed = copy.deepcopy(later)
        changed["capsules"][0]["source_detail"]["research_fragments"][0]["evidence_blocks"][0]["result_sha256"] = "c" * 64
        self.assertNotEqual(archive_fingerprint(changed), archive_fingerprint(frozen))


if __name__ == "__main__":
    unittest.main()
