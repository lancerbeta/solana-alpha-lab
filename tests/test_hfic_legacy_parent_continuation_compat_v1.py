"""Completed NO_WORTHY without an aggregate FORGE_RUN_RECEIPT."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import hashlib
import importlib.util
import json
from contextlib import redirect_stdout
from datetime import UTC, datetime
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

from solana_alpha_lab.factory.document_runner import repository_git_snapshot
from solana_alpha_lab.factory.hfic_clock import FrozenClock
from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks
from solana_alpha_lab.factory.hfic_identity import assign_portfolio_ids, normalize_text
from solana_alpha_lab.factory.hfic_preflight import persist_forge_context_packet
from solana_alpha_lab.factory.hfic_repair_continuation import (
    RepairContinuationError,
    read_repair_result_receipt,
    spent_looks_from_journal,
)
from solana_alpha_lab.factory.hfic_representation_ladder import (
    ACTION_OWNER_CANDIDATE,
    ACTION_RETURN_EXISTING,
    ACTION_SEARCH_EXHAUSTED,
    evaluate_forge_run,
)
from solana_alpha_lab.factory.hfic_session import (
    HficSessionError,
    _lookup_existing_freeze_session,
    apply_classification,
    finalize_session,
    freeze_draft,
    persist_frozen_session,
    persist_no_worthy_session,
    show_session,
)
from solana_alpha_lab.factory.research_store import ResearchStore
from tests.test_fast_lane_classifier import submission
from tests.test_hfic_cli import critic_result_from_packet_only
from tests.test_hfic_one_frozen_runner_up_failover_v1 import (
    _happy_with_pit_runner_up,
    _with_selected_feats,
)
from tests.test_hfic_temporal_operability_repair_v1 import (
    SnapshotTargetTests,
    _binding_mixed,
    _census,
    _spec_snapshot,
)

_CLI_PATH = ROOT / "scripts" / "hypothesis_forge.py"
_CLI_SPEC = importlib.util.spec_from_file_location("hypothesis_forge_cli", _CLI_PATH)
assert _CLI_SPEC and _CLI_SPEC.loader
CLI = importlib.util.module_from_spec(_CLI_SPEC)
_CLI_SPEC.loader.exec_module(CLI)


def _payloads(store: ResearchStore) -> dict[str, str]:
    found: dict[str, str] = {}
    for record in store.iter_committed_records():
        found[str(record.record_id)] = str(record.payload_sha256)
    return found


def _forge_run_count(store: ResearchStore) -> int:
    count = 0
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if kind != "RESEARCH_ARTIFACT":
            continue
        payload = json.loads(record.payload_json)
        if payload.get("artifact_kind") == "FORGE_RUN_RECEIPT":
            count += 1
    return count


def _mains(store: ResearchStore, journal: str) -> list[dict]:
    return [
        item
        for item in list_discovery_looks(store, journal)
        if item.get("look_class") == "MAIN" and item.get("new_look") is not False
    ]


class LegacyParentContinuationCompatTests(TestCase):
    def _recorded_gate(self, store, journal: str, market: str, focus: str) -> dict[str, str]:
        from solana_alpha_lab.factory.hfic_ordinary_operation import (
            list_operations,
            record_operation,
        )

        focus = focus or "AUTO"
        found = [
            item
            for item in list_operations(store)
            if item.get("journal_scope") == journal
            and item.get("market_evidence_epoch_sha256") == market
            and item.get("owner_focus") == focus
        ]
        recorded = found[-1] if found else record_operation(
            store,
            {
                "owner_request_text": "legacy recorded-query gate",
                "owner_focus": focus,
                "journal_scope": journal,
                "market_evidence_epoch_sha256": market,
                "owner_cap": {"main": None, "adaptive": None, "preview": None},
                "requested_completion": "LIMITED_RESULT",
            },
        )
        return {
            "operation_sha256": str(recorded["operation_sha256"]),
            "verified_market": market,
        }

    def _open_parent(self, data_root: Path, *, queries: int = 2) -> dict:
        git = repository_git_snapshot(ROOT)
        draft = json.loads(
            (ROOT / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1.json").read_text(
                encoding="utf-8"
            )
        )
        focus = hashlib.sha256(normalize_text("AUTO").encode("utf-8")).hexdigest()
        started = datetime(2026, 8, 27, 12, 0, 0, tzinfo=UTC)
        store = ResearchStore(data_root)
        packet = {
            "schema": "smial.forge-context-packet",
            "owner_focus": "AUTO",
            "evidence_epoch_sha256": "11" * 32,
            "market_evidence_epoch_sha256": "11" * 32,
        }
        ctx = persist_forge_context_packet(
            data_root,
            packet,
            store=store,
            repo_root=ROOT,
            clock=FrozenClock(started),
        )
        receipt = {
            "receipt_id": "HFIC-PREFLIGHT-LEGACY-PARENT-001",
            "evidence_epoch_sha256": "11" * 32,
            "market_evidence_epoch_sha256": "11" * 32,
            "focus_key_sha256": focus,
            "search_key_sha256": "33" * 32,
            "owner_focus": "AUTO",
            "session_started_at": "2026-08-27T12:00:00Z",
            "live_git_head": git.head_sha.lower(),
            "git_composite_sha256": git.composite_sha256,
            "forge_context_packet_sha256": ctx,
            "store_inventory_digest": "ee" * 32,
        }
        journal = "33" * 32
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            run_recorded_discovery_query,
        )

        rows = SnapshotTargetTests()._rows_legal()
        census = [_census()]
        binding = _binding_mixed()
        gate = self._recorded_gate(store, journal, "11" * 32, "AUTO")
        for index in range(queries):
            spec = _spec_snapshot(
                query_id=f"legacy-prior-{index}",
                all=[{"feature": "mark", "op": "gte", "value": index / 10}],
            )
            run_recorded_discovery_query(
                store,
                census=census,
                observations=rows,
                spec=spec,
                binding=binding,
                journal_scope=journal,
                candidate_scope={"schema": "test", "target": spec["target"]},
                git_sha=git.head_sha,
                **gate,
            )
        frozen = freeze_draft(draft, preflight_receipt=receipt)
        persist_no_worthy_session(
            store,
            frozen,
            repo_root=ROOT,
            identities=assign_portfolio_ids(draft["candidates"]),
            draft=draft,
            preflight_receipt=receipt,
        )
        shown = show_session(store, str(frozen["session_id"]), repo_root=ROOT)
        self.assertEqual(str(shown["search_key_sha256"]), journal)
        self.assertEqual(_forge_run_count(store), 0)
        return {
            "store": store,
            "git": git,
            "draft": draft,
            "frozen": frozen,
            "receipt": receipt,
            "shown": shown,
            "journal": journal,
            "market": "11" * 32,
            "focus": "AUTO",
            "rows": rows,
            "census": census,
            "binding": binding,
        }

    def _cli_json(self, fn, **kwargs) -> dict:
        buffer = StringIO()
        try:
            with redirect_stdout(buffer):
                code = fn(**kwargs)
        except RepairContinuationError as exc:
            return {"reason_code": str(exc), "writes": False, "_exit": 2}
        payload = json.loads(buffer.getvalue())
        payload["_exit"] = code
        return payload

    def _draft_via_cli(self, data_root: Path, session_id: str, *, run_id: str | None = None) -> dict:
        out = data_root.parent / "legacy-draft.json"
        payload = self._cli_json(
            CLI.cmd_repair_continuation_draft,
            repo_root=ROOT,
            explicit_data_root=data_root,
            parent_session_id=session_id,
            owner_authorization_id="OWNER-AUTH-LEGACY-PARENT",
            technical_gap_code="PROVIDER_REPORTED_SNAPSHOT_CLOCK_GAP",
            spent_main_looks=None,
            spent_adaptive_looks=None,
            spent_preview_looks=None,
            parent_run_id=run_id,
            terminal_receipt_sha256=None,
            journal_scope=None,
            output_path=out,
        )
        payload["_path"] = out
        return payload

    def test_draft_plan_apply_and_close_before_execution_writes_nothing(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            opened = self._open_parent(data_root)
            store = opened["store"]
            before = store.diagnostics().committed_inventory_sha256
            drafted = self._draft_via_cli(data_root, opened["shown"]["session_id"])
            self.assertEqual(drafted["_exit"], 0, drafted)
            self.assertEqual(drafted["parent_proof_mode"], "LEGACY_PARENT_BINDING")
            self.assertTrue(drafted["draft"]["parent_run_id"].startswith("LEGACY-PARENT-"))
            self.assertNotIn("FORGE-RUN-", drafted["draft"]["parent_run_id"])
            binding = drafted["draft"]["evidence_mapping"]["legacy_parent_binding"]
            self.assertEqual(binding["provenance"], "ESTABLISHED_NOW")
            self.assertEqual(binding["aggregate_receipt"], "ABSENT")
            self.assertEqual(
                binding["source"]["executed_representation_ids"],
                ["BASE"],
            )
            self.assertEqual(binding["source"]["model_provenance_status"], "NOT_RECOVERED")
            self.assertEqual(
                binding["source"]["execution_binding_status"], "NOT_RECOVERED"
            )
            planned = self._cli_json(
                CLI.cmd_repair_continuation_plan,
                repo_root=ROOT,
                explicit_data_root=data_root,
                draft_path=drafted["_path"],
                parent_session_id=None,
            )
            self.assertEqual(planned["status"], "READY", planned)
            self.assertFalse(planned["writes"])
            self.assertEqual(
                store.diagnostics().committed_inventory_sha256, before
            )
            applied = self._cli_json(
                CLI.cmd_repair_continuation_apply,
                repo_root=ROOT,
                explicit_data_root=data_root,
                draft_path=drafted["_path"],
                parent_session_id=None,
                confirm_append_only=True,
            )
            self.assertEqual(applied["status"], "APPLIED", applied)
            self.assertEqual(_forge_run_count(store), 0)
            with self.assertRaises(RepairContinuationError) as raised:
                from solana_alpha_lab.factory.hfic_repair_continuation import (
                    close_repair_continuation,
                )

                close_repair_continuation(
                    store,
                    applied["disposition"]["disposition_sha256"],
                    git_sha=opened["git"].head_sha,
                )
            self.assertEqual(raised.exception.code, "REPAIR_EXECUTION_NOT_COMPLETE")
            self.assertEqual(_forge_run_count(store), 0)
            still = [
                item
                for item in __import__(
                    "solana_alpha_lab.factory.hfic_repair_continuation",
                    fromlist=["list_repair_continuation_dispositions"],
                ).list_repair_continuation_dispositions(store)
            ]
            self.assertEqual(still[0]["status"], "AUTHORIZED")

    def test_no_worthy_close_readback_budget_and_replay(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            opened = self._open_parent(data_root)
            store = opened["store"]
            historical = _payloads(store)
            self.assertEqual(len(_mains(store, opened["journal"])), 2)
            drafted = self._draft_via_cli(data_root, opened["shown"]["session_id"])
            claimed = self._draft_via_cli(
                data_root,
                opened["shown"]["session_id"],
                run_id="FORGE-RUN-1CEB81C6C91AC1A8",
            )
            self.assertEqual(claimed.get("reason_code"), "PARENT_RUN_UNPROVEN")
            applied = self._cli_json(
                CLI.cmd_repair_continuation_apply,
                repo_root=ROOT,
                explicit_data_root=data_root,
                draft_path=drafted["_path"],
                parent_session_id=None,
                confirm_append_only=True,
            )
            from solana_alpha_lab.factory.hfic_grounded_discovery import (
                run_recorded_discovery_query,
            )

            third = _spec_snapshot(
                query_id="legacy-cont-3",
                all=[{"feature": "mark", "op": "gte", "value": 0.2}],
            )
            run_recorded_discovery_query(
                store,
                census=opened["census"],
                observations=opened["rows"],
                spec=third,
                binding=opened["binding"],
                journal_scope=opened["journal"],
                candidate_scope={"schema": "test", "target": third["target"]},
                git_sha=opened["git"].head_sha,
                **self._recorded_gate(
                    store, opened["journal"], opened["market"], opened["focus"]
                ),
            )
            self.assertEqual(len(_mains(store, opened["journal"])), 3)
            persist_no_worthy_session(
                store,
                {**opened["frozen"], **opened["receipt"]},
                repo_root=ROOT,
                identities=assign_portfolio_ids(opened["draft"]["candidates"]),
                draft=opened["draft"],
                preflight_receipt=opened["receipt"],
            )
            closed = self._cli_json(
                CLI.cmd_repair_continuation_close,
                repo_root=ROOT,
                explicit_data_root=data_root,
                disposition_sha256=applied["disposition"]["disposition_sha256"],
                reason_code="CONTINUATION_TERMINAL_REACHED",
                confirm_append_only=True,
            )
            self.assertEqual(closed["status"], "CLOSED", closed)
            self.assertTrue(closed.get("forge_run_receipt_sha256"))
            result = read_repair_result_receipt(store, applied["disposition"])
            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result.get("owner_final"), ACTION_SEARCH_EXHAUSTED)
            self.assertEqual(
                result.get("run_identity_sha256"),
                drafted["draft"]["evidence_mapping"]["legacy_parent_binding"][
                    "binding_sha256"
                ],
            )
            self.assertEqual(
                result.get("frozen_representation_ids"),
                ["BASE"],
            )
            replay_close = self._cli_json(
                CLI.cmd_repair_continuation_close,
                repo_root=ROOT,
                explicit_data_root=data_root,
                disposition_sha256=applied["disposition"]["disposition_sha256"],
                reason_code="CONTINUATION_TERMINAL_REACHED",
                confirm_append_only=True,
            )
            self.assertEqual(replay_close["status"], "ALREADY_CLOSED")
            self.assertEqual(len(_mains(store, opened["journal"])), 3)
            for record_id, digest in historical.items():
                self.assertEqual(_payloads(store).get(record_id), digest, record_id)
            run_recorded_discovery_query(
                store,
                census=opened["census"],
                observations=opened["rows"],
                spec=third,
                binding=opened["binding"],
                journal_scope=opened["journal"],
                candidate_scope={"schema": "test", "target": third["target"]},
                git_sha=opened["git"].head_sha,
                **self._recorded_gate(
                    store, opened["journal"], opened["market"], opened["focus"]
                ),
            )
            self.assertEqual(len(_mains(store, opened["journal"])), 3)
            self.assertEqual(spent_looks_from_journal(store, opened["journal"])["spent_main_looks"], 3)
            forge_input = {
                "schema": "smial.forge-input-receipt",
                "owner_class": "SEARCH",
                "market_evidence_epoch_sha256": "11" * 32,
                "capability_epoch_sha256": "aa" * 32,
                "active_evidence_set": {"visible_cohort_ids": []},
                "forge_runnable": True,
            }
            with patch(
                "solana_alpha_lab.factory.hfic_representation_ladder.build_forge_input_receipt",
                return_value=forge_input,
            ), patch(
                "solana_alpha_lab.factory.hfic_representation_ladder._session_applicable_to_current_market",
                return_value=True,
            ):
                readback = evaluate_forge_run(
                    ROOT,
                    data_root,
                    owner_focus="AUTO",
                    persist=False,
                )
            self.assertEqual(readback.get("owner_final"), ACTION_SEARCH_EXHAUSTED)
            self.assertNotEqual(
                readback.get("blocking_reason_codes"),
                ["SCIENTIFIC_IDENTITY_CONFLICT"],
            )
            self.assertEqual(readback.get("writes"), {"research_store": 0, "forge_run": 0, "session": 0})

    def test_runner_up_pass_readback_uses_pinned_binding(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            opened = self._open_parent(data_root)
            drafted = self._draft_via_cli(data_root, opened["shown"]["session_id"])
            applied = self._cli_json(
                CLI.cmd_repair_continuation_apply,
                repo_root=ROOT,
                explicit_data_root=data_root,
                draft_path=drafted["_path"],
                parent_session_id=None,
                confirm_append_only=True,
            )
            repair_disp = applied["disposition"]["disposition_sha256"]
            from tests import test_hfic_session as session_tests

            source = _happy_with_pit_runner_up()
            selected_receipt = dict(session_tests._preflight_receipt())
            selected_receipt["market_evidence_epoch_sha256"] = "11" * 32
            selected_receipt["evidence_epoch_sha256"] = "11" * 32
            selected_receipt["search_key_sha256"] = opened["journal"]
            selected = freeze_draft(
                source,
                preflight_receipt=selected_receipt,
                repo_root=ROOT,
            )
            selected["session_id"] = opened["shown"]["session_id"]
            selected["repair_continuation_disposition_sha256"] = repair_disp
            persist_frozen_session(
                opened["store"],
                selected,
                repo_root=ROOT,
                identities=assign_portfolio_ids(source["candidates"]),
                draft=source,
            )
            pending = finalize_session(
                selected,
                critic_result_from_packet_only(
                    selected["critic_input_packet"], "KILL_DATA_INFEASIBLE"
                ),
                store=opened["store"],
                repo_root=ROOT,
            )
            self.assertEqual(pending["session_state"], "RUNNER_UP_AWAITING_CRITIC")
            with self.assertRaises(RepairContinuationError) as raised:
                from solana_alpha_lab.factory.hfic_repair_continuation import (
                    close_repair_continuation,
                )

                close_repair_continuation(
                    opened["store"], repair_disp, git_sha=opened["git"].head_sha
                )
            self.assertEqual(raised.exception.code, "REPAIR_EXECUTION_NOT_COMPLETE")
            waiting = finalize_session(
                {**pending, "repair_continuation_disposition_sha256": repair_disp},
                critic_result_from_packet_only(
                    pending["critic_input_packet"], "PASS_TO_CLASSIFICATION"
                ),
                store=opened["store"],
                repo_root=ROOT,
            )
            packet = _with_selected_feats(
                submission(),
                selected["runner_up_critic_input_packet"],
            )
            packet["hypothesis_definition_sha256"] = selected["runner_up_definition_sha256"]
            done = apply_classification(
                {**waiting, "repair_continuation_disposition_sha256": repair_disp},
                packet,
                store=opened["store"],
                repo_root=ROOT,
                data_root=data_root,
            )
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            closed = self._cli_json(
                CLI.cmd_repair_continuation_close,
                repo_root=ROOT,
                explicit_data_root=data_root,
                disposition_sha256=repair_disp,
                reason_code="CONTINUATION_TERMINAL_REACHED",
                confirm_append_only=True,
            )
            self.assertEqual(closed["status"], "CLOSED", closed)
            result = read_repair_result_receipt(opened["store"], applied["disposition"])
            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result.get("owner_final"), ACTION_OWNER_CANDIDATE)
            stage = (result.get("stages") or [{}])[0]
            self.assertEqual(
                stage.get("selected_candidate_id"),
                selected["runner_up_candidate_id"],
            )
            self.assertEqual(
                result.get("run_identity_sha256"),
                drafted["draft"]["evidence_mapping"]["legacy_parent_binding"][
                    "binding_sha256"
                ],
            )

    def test_close_crash_retries_without_a_new_look(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            opened = self._open_parent(data_root)
            store = opened["store"]
            drafted = self._draft_via_cli(data_root, opened["shown"]["session_id"])
            applied = self._cli_json(
                CLI.cmd_repair_continuation_apply,
                repo_root=ROOT,
                explicit_data_root=data_root,
                draft_path=drafted["_path"],
                parent_session_id=None,
                confirm_append_only=True,
            )
            persist_no_worthy_session(
                store,
                {**opened["frozen"], **opened["receipt"]},
                repo_root=ROOT,
                identities=assign_portfolio_ids(opened["draft"]["candidates"]),
                draft=opened["draft"],
                preflight_receipt=opened["receipt"],
            )
            before_looks = len(_mains(store, opened["journal"]))
            original = store.append
            calls = {"n": 0}

            def flaky(records, *args, **kwargs):
                calls["n"] += 1
                if calls["n"] == 2:
                    raise RepairContinuationError("INJECTED_CLOSE_FAILURE")
                return original(records, *args, **kwargs)

            store.append = flaky  # type: ignore[method-assign]
            from solana_alpha_lab.factory.hfic_repair_continuation import (
                close_repair_continuation,
            )

            with self.assertRaises(RepairContinuationError) as raised:
                close_repair_continuation(
                    store,
                    applied["disposition"]["disposition_sha256"],
                    git_sha=opened["git"].head_sha,
                )
            self.assertEqual(raised.exception.code, "INJECTED_CLOSE_FAILURE")
            store.append = original  # type: ignore[method-assign]
            from solana_alpha_lab.factory.hfic_repair_continuation import (
                list_repair_continuation_dispositions,
            )

            disposition_sha = applied["disposition"]["disposition_sha256"]
            open_rows = [
                item
                for item in list_repair_continuation_dispositions(store)
                if item.get("disposition_sha256") == disposition_sha
            ]
            self.assertEqual([item.get("status") for item in open_rows], ["AUTHORIZED"])
            self.assertEqual(_forge_run_count(store), 1)
            crashed_preflight = self._cli_json(
                CLI.cmd_preflight,
                repo_root=ROOT,
                owner_focus="AUTO",
                auto_commission=True,
                explicit_data_root=data_root,
                control_current_representation=False,
                model_provenance_sha256=None,
            )
            self.assertEqual(crashed_preflight.get("_exit"), 0, crashed_preflight)
            self.assertEqual(
                crashed_preflight.get("action"), "RESUME_REPAIR_CONTINUATION"
            )
            crashed_forge = self._cli_json(
                CLI.cmd_forge_run,
                repo_root=ROOT,
                explicit_data_root=data_root,
                owner_focus="AUTO",
                persist=False,
                saved_draft_sha256=None,
                model_provenance_sha256=None,
                control_current_representation=False,
            )
            self.assertNotEqual(crashed_forge.get("next_action"), ACTION_RETURN_EXISTING)
            self.assertNotEqual(crashed_forge.get("owner_final"), ACTION_SEARCH_EXHAUSTED)
            self.assertEqual(len(_mains(store, opened["journal"])), before_looks)
            closed = close_repair_continuation(
                store,
                applied["disposition"]["disposition_sha256"],
                git_sha=opened["git"].head_sha,
            )
            self.assertEqual(closed["status"], "CLOSED")
            self.assertTrue(closed.get("forge_run_receipt_sha256"))
            self.assertEqual(len(_mains(store, opened["journal"])), before_looks)
            self.assertEqual(_forge_run_count(store), 1)
            readback = self._reopen_forge_run(data_root)
            self.assertEqual(readback.get("_exit"), 0, readback)
            self.assertEqual(readback.get("next_action"), ACTION_RETURN_EXISTING)
            self.assertEqual(readback.get("owner_final"), ACTION_SEARCH_EXHAUSTED)
            self.assertEqual(len(_mains(store, opened["journal"])), before_looks)
            self.assertEqual(_forge_run_count(store), 1)

    def test_capability_drift_freeze_is_store_disposition_not_parent_terminal(self) -> None:
        import tempfile

        from solana_alpha_lab.factory.hfic_evidence_identity import (
            _closed_repair_readback,
        )
        from solana_alpha_lab.factory.hfic_repair_continuation import (
            list_repair_continuation_dispositions,
        )

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            opened = self._open_parent(data_root)
            store = opened["store"]
            drifted = {
                **opened["receipt"],
                "capability_epoch_sha256": "ab" * 32,
                "action": "RESUME_REPAIR_CONTINUATION",
            }
            with self.assertRaises(HficSessionError) as blocked:
                _lookup_existing_freeze_session(store, drifted, draft={"candidates": []})
            self.assertEqual(
                blocked.exception.code,
                "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING",
            )
            drafted = self._draft_via_cli(data_root, opened["shown"]["session_id"])
            applied = self._cli_json(
                CLI.cmd_repair_continuation_apply,
                repo_root=ROOT,
                explicit_data_root=data_root,
                draft_path=drafted["_path"],
                parent_session_id=None,
                confirm_append_only=True,
            )
            self.assertEqual(applied["status"], "APPLIED", applied)
            # First selected freeze is the repair execution, not a second slot.
            self.assertIsNone(
                _lookup_existing_freeze_session(
                    store,
                    drifted,
                    draft={"selected_candidate_ref": "HFIC-V12-C1"},
                )
            )
            self.assertIsNone(
                _lookup_existing_freeze_session(
                    store, drifted, draft={"candidates": []}
                )
            )
            with self.assertRaises(HficSessionError) as freeze_blocked:
                freeze_draft(
                    opened["draft"],
                    preflight_receipt=drifted,
                    store=store,
                    repo_root=ROOT,
                    verify_current_market_identity=True,
                )
            self.assertNotEqual(
                freeze_blocked.exception.code,
                "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING",
            )
            evidence = {
                "result_sha256": "cd" * 32,
                "result_refs": ["HFIC-ART-DISCOVERY-BOUND"],
            }
            repair_draft = {**opened["draft"], "grounded_evidence": evidence}
            before = _payloads(store)
            persist_no_worthy_session(
                store,
                {**opened["frozen"], **opened["receipt"]},
                repo_root=ROOT,
                identities=assign_portfolio_ids(opened["draft"]["candidates"]),
                draft=repair_draft,
                preflight_receipt=opened["receipt"],
            )
            shown = show_session(store, opened["shown"]["session_id"], repo_root=ROOT)
            self.assertEqual(
                shown["repair_continuation_disposition_sha256"],
                applied["disposition"]["disposition_sha256"],
            )
            self.assertNotEqual(
                shown["session_receipt_sha256"],
                opened["shown"]["session_receipt_sha256"],
            )
            self.assertEqual(shown["grounded_result_sha256"], evidence["result_sha256"])
            self.assertEqual(shown["grounded_result_refs"], evidence["result_refs"])
            written = _payloads(store)
            self.assertNotEqual(written, before)
            persist_no_worthy_session(
                store,
                {**opened["frozen"], **opened["receipt"]},
                repo_root=ROOT,
                identities=assign_portfolio_ids(opened["draft"]["candidates"]),
                draft=repair_draft,
                preflight_receipt=opened["receipt"],
            )
            self.assertEqual(_payloads(store), written)
            replay = _lookup_existing_freeze_session(
                store, drifted, draft={"grounded_evidence": evidence}
            )
            self.assertEqual(
                replay["repair_continuation_disposition_sha256"],
                applied["disposition"]["disposition_sha256"],
            )
            with self.assertRaises(HficSessionError) as selected_after:
                _lookup_existing_freeze_session(
                    store,
                    drifted,
                    draft={
                        "selected_candidate_ref": "HFIC-V12-C1",
                        "grounded_evidence": evidence,
                    },
                )
            self.assertEqual(
                selected_after.exception.code,
                "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING",
            )
            with self.assertRaises(HficSessionError) as changed:
                _lookup_existing_freeze_session(
                    store,
                    drifted,
                    draft={
                        "grounded_evidence": {
                            "result_sha256": "ef" * 32,
                            "result_refs": evidence["result_refs"],
                        }
                    },
                )
            self.assertEqual(changed.exception.code, "GROUNDED_RESULT_MISMATCH")
            matched = {
                key: value
                for key, value in drifted.items()
                if key != "capability_epoch_sha256"
            }
            with self.assertRaises(HficSessionError) as matched_changed:
                _lookup_existing_freeze_session(
                    store,
                    matched,
                    draft={
                        "grounded_evidence": {
                            "result_sha256": "ef" * 32,
                            "result_refs": evidence["result_refs"],
                        }
                    },
                )
            self.assertEqual(
                matched_changed.exception.code, "GROUNDED_RESULT_MISMATCH"
            )
            self.assertEqual(_payloads(store), written)
            from solana_alpha_lab.factory.hfic_repair_continuation import (
                close_repair_continuation,
            )

            closed = close_repair_continuation(
                store,
                applied["disposition"]["disposition_sha256"],
                git_sha=opened["git"].head_sha,
            )
            self.assertEqual(closed["status"], "CLOSED")
            again = close_repair_continuation(
                store,
                applied["disposition"]["disposition_sha256"],
                git_sha=opened["git"].head_sha,
            )
            self.assertEqual(again["status"], "ALREADY_CLOSED")
            self.assertFalse(again["writes"])
            listed = [
                item
                for item in list_repair_continuation_dispositions(store)
                if item.get("disposition_sha256")
                == applied["disposition"]["disposition_sha256"]
            ]
            readback = _closed_repair_readback(
                listed,
                shown,
                scientific_slot_sha256=shown["scientific_slot_sha256"],
            )
            self.assertEqual(
                readback["disposition_sha256"],
                applied["disposition"]["disposition_sha256"],
            )
            from solana_alpha_lab.factory.hfic_evidence_identity import (
                resolve_scientific_admission,
            )
            from solana_alpha_lab.factory.hfic_session import (
                list_hfic_sessions,
                list_scientific_slot_admissions,
            )

            closed_shown = show_session(
                store, opened["shown"]["session_id"], repo_root=ROOT
            )
            admission = resolve_scientific_admission(
                list_hfic_sessions(store),
                market_evidence_epoch=str(
                    closed_shown["market_evidence_epoch_sha256"]
                ),
                representation_id="BASE",
                representation_semantic_version="HFIC-V1.2",
                owner_focus="AUTO",
                reservations=list_scientific_slot_admissions(store),
                execution_context={"capability_epoch_sha256": "ab" * 32},
                repair_continuations=list_repair_continuation_dispositions(store),
            )
            self.assertEqual(admission["action"], "RETURN_EXISTING_SESSION")
            self.assertEqual(admission["session_id"], closed_shown["session_id"])
            self.assertEqual(admission["occupancy"], "REPAIR_CLOSED_READBACK")
            self.assertNotEqual(admission["action"], "START_NEW_SESSION")
            self.assertNotEqual(admission["action"], "RESUME_REPAIR_CONTINUATION")

    def test_foreign_binding_conflict_and_exhausted_budget_are_refused(self) -> None:
        import tempfile

        from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            opened = self._open_parent(data_root)
            store = opened["store"]
            foreign = {
                "schema": "smial.forge-run-receipt",
                "schema_version": "1.0",
                "run_id": "FORGE-RUN-FOREIGN",
                "run_identity_sha256": "ab" * 32,
                "session_id": "HFIC-SESS-OTHER",
                "scientific_slot_sha256": opened["shown"]["scientific_slot_sha256"],
                "owner_final": "SEARCH_EXHAUSTED_CURRENT_EVIDENCE",
            }
            body = json.dumps(foreign, sort_keys=True, separators=(",", ":"))
            wrapper = {
                "artifact_kind": "FORGE_RUN_RECEIPT",
                "payload_canonical": body,
                "payload_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            }
            payload_json = json.dumps(wrapper, sort_keys=True, separators=(",", ":"))
            now = datetime(2026, 8, 27, 12, 0, 0, tzinfo=UTC)
            store.append(
                [
                    ResearchEvent(
                        record_id="HFIC-ART-FORGE-RUN-FOREIGN",
                        record_kind=RecordKind.RESEARCH_ARTIFACT,
                        entity_id="FORGE-RUN-FOREIGN",
                        hypothesis_version_id=None,
                        run_id="FORGE-RUN-FOREIGN",
                        transaction_id="RESEARCH-TXN-FOREIGN",
                        effective_at=now,
                        first_reliable_available_at=now,
                        supersedes_record_id=None,
                        payload_json=payload_json,
                        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
                        schema_version="1.0",
                        producer_capability_id="CAP-TEST",
                        producer_git_sha=opened["git"].head_sha,
                        created_at=now,
                    )
                ],
                transaction_id="RESEARCH-TXN-FOREIGN",
            )
            blocked = self._draft_via_cli(data_root, opened["shown"]["session_id"])
            self.assertEqual(blocked.get("reason_code"), "PARENT_RECEIPT_CONFLICT")

        with tempfile.TemporaryDirectory() as tmp:
            from solana_alpha_lab.factory.hfic_grounded_discovery import (
                _append_discovery_look,
            )

            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            opened = self._open_parent(data_root)
            prior = list_discovery_looks(opened["store"], opened["journal"])
            binding_sha = str(prior[0]["data_binding_sha256"])
            refs = list(prior[0].get("data_refs") or [])
            clock = datetime(2026, 9, 28, tzinfo=UTC)
            for index in range(4):
                _append_discovery_look(
                    opened["store"],
                    record_id=f"HFIC-ART-DISCOVERY-EXTRA{index:02d}" + ("0" * 16),
                    journal_scope=opened["journal"],
                    spec={"query_id": f"extra-{index}"},
                    spec_sha256=f"{index + 3:064x}",
                    binding_sha=binding_sha,
                    data_refs=refs,
                    digest=f"{index + 20:064x}",
                    identity=f"{index + 7:02x}" + ("b" * 62),
                    summary={"calculation_version": "HFIC_TEMPORAL_DISCOVERY_CALC_V3"},
                    look={
                        "look_class": "MAIN",
                        "new_look": True,
                        "search_tier": "COMPOUND_SCREEN",
                        "main_count": index + 3,
                    },
                    git_sha=opened["git"].head_sha,
                    clock=clock,
                )
            blocked = self._draft_via_cli(data_root, opened["shown"]["session_id"])
            drafted_ok = blocked["_exit"] == 0
            if drafted_ok:
                planned = self._cli_json(
                    CLI.cmd_repair_continuation_plan,
                    repo_root=ROOT,
                    explicit_data_root=data_root,
                    draft_path=blocked["_path"],
                    parent_session_id=None,
                )
                self.assertEqual(planned.get("reason_code"), "SPENT_BUDGET_EXHAUSTED")
            else:
                self.assertEqual(blocked.get("reason_code"), "SPENT_BUDGET_EXHAUSTED")

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            opened = self._open_parent(data_root)
            drafted = self._draft_via_cli(data_root, opened["shown"]["session_id"])
            raw = json.loads(drafted["_path"].read_text(encoding="utf-8"))
            raw["evidence_mapping"]["legacy_parent_binding"]["source"]["cohort_ids"] = [
                "REL-CHANGED"
            ]
            drafted["_path"].write_text(json.dumps(raw), encoding="utf-8")
            planned = self._cli_json(
                CLI.cmd_repair_continuation_plan,
                repo_root=ROOT,
                explicit_data_root=data_root,
                draft_path=drafted["_path"],
                parent_session_id=None,
            )
            self.assertEqual(planned.get("reason_code"), "PARENT_BINDING_MISMATCH")
            raw["journal_scope"] = "44" * 32
            raw["evidence_mapping"] = drafted["draft"]["evidence_mapping"]
            drafted["_path"].write_text(json.dumps(raw), encoding="utf-8")
            planned = self._cli_json(
                CLI.cmd_repair_continuation_plan,
                repo_root=ROOT,
                explicit_data_root=data_root,
                draft_path=drafted["_path"],
                parent_session_id=None,
            )
            self.assertIn(
                planned.get("reason_code"),
                {"JOURNAL_SCOPE_MISMATCH", "PARENT_BINDING_MISMATCH"},
            )
            self.assertEqual(_forge_run_count(opened["store"]), 0)

    def _preflight_body(self, payload: dict) -> dict:
        body = dict(payload)
        body.pop("_exit", None)
        return body

    def _production_preflight(self, data_root: Path) -> dict:
        return self._cli_json(
            CLI.cmd_preflight,
            repo_root=ROOT,
            owner_focus="AUTO",
            auto_commission=True,
            explicit_data_root=data_root,
            control_current_representation=False,
            model_provenance_sha256=None,
        )

    def _open_parent_on_current_corpus(
        self,
        data_root: Path,
        *,
        omit_capability_epoch: bool = False,
        extra_specs: list[dict] | None = None,
    ) -> dict:
        from tests.test_hfic_cli import seed_minimal_market_basis

        seed_minimal_market_basis(data_root)
        live = self._production_preflight(data_root)
        self.assertEqual(live.get("_exit"), 0, live)
        self.assertEqual(live.get("action"), "START_NEW_SESSION", live)
        current = self._preflight_body(live)
        # Historical parent shape: same market and search identity as the
        # current corpus, without a stored aggregate receipt or a fresh
        # discovery-contract freeze.
        receipt = {
            "receipt_id": current["receipt_id"],
            "evidence_epoch_sha256": current["evidence_epoch_sha256"],
            "market_evidence_epoch_sha256": current.get(
                "market_evidence_epoch_sha256"
            ),
            "focus_key_sha256": current["focus_key_sha256"],
            "search_key_sha256": current["search_key_sha256"],
            "owner_focus": current.get("owner_focus") or "AUTO",
            "session_started_at": current.get("session_started_at"),
            "live_git_head": current.get("live_git_head"),
            "git_composite_sha256": current.get("git_composite_sha256"),
            "forge_context_packet_sha256": current.get("forge_context_packet_sha256"),
            "store_inventory_digest": current.get("store_inventory_digest"),
            "memory_eligibility_sha256": current.get("memory_eligibility_sha256"),
            "capability_epoch_sha256": current.get("capability_epoch_sha256"),
            "prompt_version": current.get("prompt_version"),
        }
        if omit_capability_epoch:
            receipt.pop("capability_epoch_sha256", None)
        draft = json.loads(
            (ROOT / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1.json").read_text(
                encoding="utf-8"
            )
        )
        store = ResearchStore(data_root)
        journal = str(current["search_key_sha256"])
        market = str(current.get("market_evidence_epoch_sha256") or "")
        focus = str(current.get("owner_focus") or "AUTO")
        git = repository_git_snapshot(ROOT)
        rows = SnapshotTargetTests()._rows_legal()
        census = [_census()]
        binding = _binding_mixed()
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            run_recorded_discovery_query,
        )

        discovery_evidence = []
        gate = self._recorded_gate(store, journal, market, focus)
        setup_specs = [
            _spec_snapshot(
                query_id=f"legacy-corpus-{index}",
                all=[{"feature": "mark", "op": "gte", "value": index / 10}],
            )
            for index in range(2)
        ]
        setup_specs.extend(extra_specs or [])
        for spec in setup_specs:
            discovery_evidence.append(
                run_recorded_discovery_query(
                    store,
                    census=census,
                    observations=rows,
                    spec=spec,
                    binding=binding,
                    journal_scope=journal,
                    candidate_scope={"schema": "test", "target": spec["target"]},
                    git_sha=git.head_sha,
                    **gate,
                )
            )
        frozen = freeze_draft(draft, preflight_receipt=receipt, repo_root=ROOT)
        persist_no_worthy_session(
            store,
            frozen,
            repo_root=ROOT,
            identities=assign_portfolio_ids(draft["candidates"]),
            draft=draft,
            preflight_receipt=receipt,
        )
        shown = show_session(store, str(frozen["session_id"]), repo_root=ROOT)
        self.assertEqual(str(shown["search_key_sha256"]), journal)
        self.assertEqual(
            shown.get("market_evidence_epoch_sha256"),
            current.get("market_evidence_epoch_sha256"),
        )
        self.assertEqual(len(_mains(store, journal)), len(setup_specs))
        self.assertEqual(_forge_run_count(store), 0)
        return {
            "store": store,
            "git": git,
            "draft": draft,
            "frozen": frozen,
            "receipt": receipt,
            "shown": shown,
            "journal": journal,
            "market": market,
            "focus": focus,
            "rows": rows,
            "census": census,
            "binding": binding,
            "discovery_evidence": discovery_evidence,
        }

    def _continue_from_preflight(
        self,
        store: ResearchStore,
        draft: dict,
        preflight: dict,
        *,
        frozen: dict | None = None,
    ) -> dict:
        from tests.test_hfic_cli import bind_draft

        receipt = self._preflight_body(preflight)
        if draft.get("selected_candidate_ref"):
            bound = bind_draft(dict(draft), receipt)
            return freeze_draft(
                bound,
                preflight_receipt=receipt,
                store=store,
                repo_root=ROOT,
            )
        if frozen is None:
            raise AssertionError("NO_WORTHY continuation requires the parent freeze")
        return persist_no_worthy_session(
            store,
            frozen,
            repo_root=ROOT,
            identities=assign_portfolio_ids(draft["candidates"]),
            draft=draft,
            preflight_receipt=receipt,
        )

    def _apply_ordinary_repair(self, data_root: Path, opened: dict) -> dict:
        drafted = self._draft_via_cli(data_root, opened["shown"]["session_id"])
        self.assertEqual(drafted["_exit"], 0, drafted)
        planned = self._cli_json(
            CLI.cmd_repair_continuation_plan,
            repo_root=ROOT,
            explicit_data_root=data_root,
            draft_path=drafted["_path"],
            parent_session_id=None,
        )
        self.assertEqual(planned["status"], "READY", planned)
        self.assertFalse(planned["writes"])
        applied = self._cli_json(
            CLI.cmd_repair_continuation_apply,
            repo_root=ROOT,
            explicit_data_root=data_root,
            draft_path=drafted["_path"],
            parent_session_id=None,
            confirm_append_only=True,
        )
        self.assertEqual(applied["status"], "APPLIED", applied)
        preflight = self._production_preflight(data_root)
        self.assertEqual(preflight.get("_exit"), 0, preflight)
        self.assertEqual(preflight.get("action"), "RESUME_REPAIR_CONTINUATION")
        self.assertEqual(preflight.get("session_id"), opened["shown"]["session_id"])
        return {"drafted": drafted, "applied": applied, "preflight": preflight}

    def _spend_one_main(
        self,
        opened: dict,
        *,
        query_id: str,
        spec: dict | None = None,
        candidate_scope: dict | None = None,
    ):
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            run_recorded_discovery_query,
        )

        spec = spec or _spec_snapshot(
            query_id=query_id,
            all=[{"feature": "mark", "op": "gte", "value": 0.2}],
        )
        return run_recorded_discovery_query(
            opened["store"],
            census=opened["census"],
            observations=opened["rows"],
            spec=spec,
            binding=opened["binding"],
            journal_scope=opened["journal"],
            candidate_scope=candidate_scope
            or {"schema": "test", "target": spec["target"]},
            git_sha=opened["git"].head_sha,
            **self._recorded_gate(
                opened["store"], opened["journal"], opened["market"], opened["focus"]
            ),
        )

    def _reopen_forge_run(self, data_root: Path) -> dict:
        ResearchStore(data_root, create_if_missing=False)
        readback = self._cli_json(
            CLI.cmd_forge_run,
            repo_root=ROOT,
            explicit_data_root=data_root,
            owner_focus="AUTO",
            persist=False,
            saved_draft_sha256=None,
            model_provenance_sha256=None,
            control_current_representation=False,
        )
        return readback

    def _freeze_cli(self, data_root: Path, draft_path: Path, preflight_path: Path) -> dict:
        try:
            return self._cli_json(
                CLI.cmd_freeze,
                repo_root=ROOT,
                draft_path=draft_path,
                preflight_path=preflight_path,
                explicit_data_root=data_root,
                next_action_path=None,
            )
        except HficSessionError as exc:
            return {"reason_code": exc.code, "writes": False, "_exit": 2}

    def _repair_draft(self, preflight: dict, evidence: dict, path: Path) -> dict:
        from tests.test_hfic_cli import bind_draft

        receipt = self._preflight_body(preflight)
        draft = bind_draft(
            {
                "packet_schema": "smial.hypothesis-forge-draft",
                "packet_version": "1.2",
                "generator_prompt_version": "HFIC-V1.2",
                "owner_focus": receipt.get("owner_focus") or "AUTO",
                "authority": {
                    "git_mutation": 0,
                    "experiment_execution": 0,
                    "provider_api_rpc_wss_calls": 0,
                },
                "candidates": [],
                "pareto_factors": ["grounding"],
                "non_claims": ["NO_ALPHA", "NO_WORTHY_HYPOTHESIS"],
                "grounded_evidence": evidence,
            },
            receipt,
        )
        path.write_text(json.dumps(draft), encoding="utf-8")
        return draft

    def test_cli_capability_drift_freeze_close_and_readback(self) -> None:
        import tempfile

        from solana_alpha_lab.factory.hfic_repair_continuation import (
            close_repair_continuation,
            list_repair_continuation_dispositions,
        )

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            compound_spec = _spec_snapshot(
                query_id="legacy-compound",
                search_tier="COMPOUND_SCREEN",
                all=[{"feature": "mark", "op": "gte", "value": 0.5}],
            )
            opened = self._open_parent_on_current_corpus(
                data_root,
                omit_capability_epoch=True,
                extra_specs=[compound_spec],
            )
            self.assertIsNone(opened["shown"].get("capability_epoch_sha256"))
            self.assertEqual(_forge_run_count(opened["store"]), 0)
            self.assertEqual(len(opened["discovery_evidence"]), 3)
            evidence = opened["discovery_evidence"][-1]
            prepared = self._apply_ordinary_repair(data_root, opened)
            self.assertNotEqual(
                prepared["preflight"].get("capability_epoch_sha256"),
                opened["shown"].get("capability_epoch_sha256"),
            )
            other = opened["discovery_evidence"][0]
            self.assertNotEqual(evidence["result_sha256"], other["result_sha256"])
            preflight_path = data_root.parent / "repair-preflight.json"
            preflight_path.write_text(
                json.dumps(self._preflight_body(prepared["preflight"])),
                encoding="utf-8",
            )
            draft_path = data_root.parent / "repair-draft.json"
            self._repair_draft(prepared["preflight"], evidence, draft_path)
            before_mains = len(_mains(opened["store"], opened["journal"]))
            frozen = self._freeze_cli(data_root, draft_path, preflight_path)
            self.assertEqual(frozen.get("_exit"), 0, frozen)
            shown = show_session(
                opened["store"], opened["shown"]["session_id"], repo_root=ROOT
            )
            self.assertEqual(
                shown["repair_continuation_disposition_sha256"],
                prepared["applied"]["disposition"]["disposition_sha256"],
            )
            self.assertNotEqual(
                shown["session_receipt_sha256"],
                opened["shown"]["session_receipt_sha256"],
            )
            self.assertEqual(shown["grounded_result_sha256"], evidence["result_sha256"])
            self.assertEqual(shown["session_id"], opened["shown"]["session_id"])
            self.assertEqual(
                shown["scientific_slot_sha256"],
                opened["shown"]["scientific_slot_sha256"],
            )
            self.assertEqual(shown["search_key_sha256"], opened["journal"])
            self.assertEqual(len(_mains(opened["store"], opened["journal"])), before_mains)
            written = _payloads(opened["store"])
            replay = self._freeze_cli(data_root, draft_path, preflight_path)
            self.assertEqual(replay.get("_exit"), 0, replay)
            self.assertEqual(replay.get("current_market_identity"), "VERIFIED")
            self.assertEqual(replay.get("repair_readback_status"), "AUTHORIZED")
            self.assertEqual(
                replay.get("session_receipt_sha256"), shown["session_receipt_sha256"]
            )
            self.assertEqual(_payloads(opened["store"]), written)
            historical = freeze_draft(
                json.loads(draft_path.read_text(encoding="utf-8")),
                preflight_receipt=self._preflight_body(prepared["preflight"]),
                store=ResearchStore(data_root, create_if_missing=False),
                repo_root=ROOT,
                verify_current_market_identity=False,
            )
            self.assertEqual(historical.get("current_market_identity"), "NOT_VERIFIED")
            self.assertEqual(_payloads(opened["store"]), written)
            corrupt_path = data_root.parent / "corrupt-preflight.json"
            corrupt = self._preflight_body(prepared["preflight"])
            corrupt["preflight_receipt_sha256"] = "00" * 32
            corrupt_path.write_text(json.dumps(corrupt), encoding="utf-8")
            refused = self._freeze_cli(data_root, draft_path, corrupt_path)
            self.assertEqual(refused.get("_exit"), 2, refused)
            self.assertEqual(
                refused.get("reason_code"), "PREFLIGHT_RECEIPT_HASH_MISMATCH"
            )
            self.assertEqual(_payloads(opened["store"]), written)
            lineage = (
                data_root / "datasets" / "live_lifecycle_corpus" / "lineage.json"
            )
            original_lineage = lineage.read_bytes()
            changed_lineage = json.loads(original_lineage)
            cohorts = changed_lineage.get("cohorts") or []
            self.assertTrue(cohorts)
            source_key = (
                "source_sha256"
                if cohorts[0].get("source_sha256")
                else "content_sha256"
            )
            digest = str(cohorts[0][source_key])
            cohorts[0][source_key] = ("0" if digest[0] != "0" else "1") + digest[1:]
            lineage.write_text(json.dumps(changed_lineage), encoding="utf-8")
            try:
                drifted_market = self._freeze_cli(data_root, draft_path, preflight_path)
            finally:
                lineage.write_bytes(original_lineage)
            self.assertEqual(drifted_market.get("_exit"), 2, drifted_market)
            self.assertIn(
                drifted_market.get("reason_code"),
                {"MARKET_IDENTITY_DRIFT", "MARKET_EVIDENCE_BASIS_INCOMPLETE"},
            )
            self.assertEqual(_payloads(opened["store"]), written)
            fresh = self._production_preflight(data_root)
            self.assertEqual(fresh.get("_exit"), 0, fresh)
            self.assertEqual(fresh.get("action"), "RESUME_REPAIR_CONTINUATION")
            self.assertEqual(fresh.get("session_id"), opened["shown"]["session_id"])
            self.assertEqual(
                fresh.get("market_evidence_epoch_sha256"),
                opened["shown"]["market_evidence_epoch_sha256"],
            )
            fresh_draft = data_root.parent / "fresh-draft.json"
            fresh_preflight = data_root.parent / "fresh-preflight.json"
            fresh_preflight.write_text(
                json.dumps(self._preflight_body(fresh)), encoding="utf-8"
            )
            self._repair_draft(fresh, evidence, fresh_draft)
            before_reread = _payloads(ResearchStore(data_root, create_if_missing=False))
            reread = self._freeze_cli(data_root, fresh_draft, fresh_preflight)
            self.assertEqual(reread.get("_exit"), 0, reread)
            self.assertEqual(reread.get("repair_readback_status"), "AUTHORIZED")
            again = show_session(
                ResearchStore(data_root, create_if_missing=False),
                opened["shown"]["session_id"],
                repo_root=ROOT,
            )
            self.assertEqual(
                again["session_receipt_sha256"], shown["session_receipt_sha256"]
            )
            self.assertEqual(again["scientific_slot_sha256"], shown["scientific_slot_sha256"])
            self.assertEqual(again["search_key_sha256"], opened["journal"])
            self.assertEqual(len(_mains(opened["store"], opened["journal"])), before_mains)
            self.assertEqual(
                _payloads(ResearchStore(data_root, create_if_missing=False)),
                before_reread,
            )
            other_draft = data_root.parent / "other-draft.json"
            self._repair_draft(prepared["preflight"], other, other_draft)
            mismatched = self._freeze_cli(data_root, other_draft, preflight_path)
            self.assertEqual(mismatched.get("_exit"), 2, mismatched)
            self.assertEqual(mismatched.get("reason_code"), "GROUNDED_RESULT_MISMATCH")
            self.assertEqual(
                show_session(
                    ResearchStore(data_root, create_if_missing=False),
                    opened["shown"]["session_id"],
                    repo_root=ROOT,
                )["session_receipt_sha256"],
                shown["session_receipt_sha256"],
            )
            store = ResearchStore(data_root, create_if_missing=False)
            original_append = store.append
            calls = {"n": 0}

            def flaky(records, *args, **kwargs):
                calls["n"] += 1
                if calls["n"] == 2:
                    raise RepairContinuationError("INJECTED_CLOSE_FAILURE")
                return original_append(records, *args, **kwargs)

            store.append = flaky  # type: ignore[method-assign]
            with self.assertRaises(RepairContinuationError) as raised:
                close_repair_continuation(
                    store,
                    prepared["applied"]["disposition"]["disposition_sha256"],
                    git_sha=opened["git"].head_sha,
                )
            self.assertEqual(raised.exception.code, "INJECTED_CLOSE_FAILURE")
            store.append = original_append  # type: ignore[method-assign]
            disposition_sha = prepared["applied"]["disposition"]["disposition_sha256"]
            open_rows = [
                item
                for item in list_repair_continuation_dispositions(store)
                if item.get("disposition_sha256") == disposition_sha
            ]
            self.assertEqual([item.get("status") for item in open_rows], ["AUTHORIZED"])
            self.assertEqual(
                _forge_run_count(ResearchStore(data_root, create_if_missing=False)),
                1,
            )
            interrupted = self._production_preflight(data_root)
            self.assertEqual(interrupted.get("action"), "RESUME_REPAIR_CONTINUATION")
            self.assertEqual(
                interrupted.get("session_id"), opened["shown"]["session_id"]
            )
            resumed = close_repair_continuation(
                ResearchStore(data_root, create_if_missing=False),
                disposition_sha,
                git_sha=opened["git"].head_sha,
            )
            self.assertEqual(resumed["status"], "CLOSED")
            idle = close_repair_continuation(
                ResearchStore(data_root, create_if_missing=False),
                disposition_sha,
                git_sha=opened["git"].head_sha,
            )
            self.assertEqual(idle["status"], "ALREADY_CLOSED")
            self.assertFalse(idle["writes"])
            closed_payloads = _payloads(
                ResearchStore(data_root, create_if_missing=False)
            )
            closed_replay = self._freeze_cli(data_root, draft_path, preflight_path)
            self.assertEqual(closed_replay.get("_exit"), 0, closed_replay)
            self.assertEqual(closed_replay.get("repair_readback_status"), "CLOSED")
            self.assertEqual(closed_replay.get("current_market_identity"), "VERIFIED")
            self.assertEqual(
                closed_replay.get("session_receipt_sha256"),
                shown["session_receipt_sha256"],
            )
            self.assertEqual(
                _payloads(ResearchStore(data_root, create_if_missing=False)),
                closed_payloads,
            )
            blocked = self._freeze_cli(data_root, other_draft, preflight_path)
            self.assertEqual(blocked.get("_exit"), 2, blocked)
            self.assertEqual(blocked.get("reason_code"), "GROUNDED_RESULT_MISMATCH")
            self.assertEqual(len(_mains(opened["store"], opened["journal"])), before_mains)
            readback_preflight = self._production_preflight(data_root)
            self.assertEqual(
                readback_preflight.get("action"), "RETURN_EXISTING_SESSION"
            )
            self.assertEqual(
                readback_preflight.get("session_id"), opened["shown"]["session_id"]
            )
            self.assertNotEqual(readback_preflight.get("action"), "START_NEW_SESSION")
            self.assertNotEqual(
                readback_preflight.get("action"), "RESUME_REPAIR_CONTINUATION"
            )
            readback = self._reopen_forge_run(data_root)
            self.assertEqual(readback.get("_exit"), 0, readback)
            self.assertEqual(readback.get("next_action"), ACTION_RETURN_EXISTING)
            self.assertEqual(readback.get("owner_final"), ACTION_SEARCH_EXHAUSTED)
            self.assertEqual(readback.get("session_id"), opened["shown"]["session_id"])
            self.assertNotEqual(readback.get("next_action"), "START_BASE")

    def test_ordinary_no_worthy_readback_after_reopen(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            opened = self._open_parent_on_current_corpus(data_root)
            historical = _payloads(opened["store"])
            self.assertEqual(len(_mains(opened["store"], opened["journal"])), 2)
            self.assertEqual(_forge_run_count(opened["store"]), 0)
            prepared = self._apply_ordinary_repair(data_root, opened)
            binding = prepared["drafted"]["draft"]["evidence_mapping"][
                "legacy_parent_binding"
            ]
            self._spend_one_main(opened, query_id="legacy-ordinary-3")
            self.assertEqual(len(_mains(opened["store"], opened["journal"])), 3)
            continued = self._continue_from_preflight(
                opened["store"],
                opened["draft"],
                prepared["preflight"],
                frozen=opened["frozen"],
            )
            self.assertEqual(continued["session_id"], opened["shown"]["session_id"])
            closed = self._cli_json(
                CLI.cmd_repair_continuation_close,
                repo_root=ROOT,
                explicit_data_root=data_root,
                disposition_sha256=prepared["applied"]["disposition"]["disposition_sha256"],
                reason_code="CONTINUATION_TERMINAL_REACHED",
                confirm_append_only=True,
            )
            self.assertEqual(closed["status"], "CLOSED", closed)
            readback = self._reopen_forge_run(data_root)
            self.assertEqual(readback.get("_exit"), 0, readback)
            self.assertEqual(readback.get("owner_final"), ACTION_SEARCH_EXHAUSTED)
            self.assertEqual(readback.get("run_identity_sha256"), binding["binding_sha256"])
            self.assertEqual(readback.get("frozen_representation_ids"), ["BASE"])
            self.assertTrue(readback.get("repair_continuation_disposition_sha256"))
            self.assertEqual(
                readback.get("writes"),
                {"research_store": 0, "forge_run": 0, "session": 0},
            )
            self._spend_one_main(opened, query_id="legacy-ordinary-3")
            self.assertEqual(len(_mains(opened["store"], opened["journal"])), 3)
            for record_id, digest in historical.items():
                self.assertEqual(_payloads(opened["store"]).get(record_id), digest, record_id)

    def test_ordinary_runner_up_readback_after_reopen(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            opened = self._open_parent_on_current_corpus(data_root)
            historical = _payloads(opened["store"])
            prepared = self._apply_ordinary_repair(data_root, opened)
            binding = prepared["drafted"]["draft"]["evidence_mapping"][
                "legacy_parent_binding"
            ]
            from solana_alpha_lab.factory.hfic_grounded_discovery import (
                scope_bound_to_spec,
            )

            spec = _spec_snapshot(
                query_id="legacy-ordinary-runner",
                all=[{"feature": "mark", "op": "gte", "value": 0.2}],
            )
            source = _happy_with_pit_runner_up()
            selected_card = next(
                card
                for card in source["candidates"]
                if card["label"] == source["selected_candidate_ref"]
            )
            selected_card.pop("representation_scope", None)
            if not selected_card.get("explanatory_condition"):
                selected_card["explanatory_condition"] = (
                    "decision-time mark versus the spec exit"
                )
            declared_scope = {
                "estimand": selected_card["estimand"],
                "explanatory_condition": selected_card["explanatory_condition"],
                "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
            }
            bound_scope = scope_bound_to_spec(spec, declared_scope)
            selected_card["population"] = bound_scope["population"]
            selected_card["decision_timestamp"] = bound_scope["decision_timestamp"]
            selected_card["target"] = bound_scope["target"]
            runner_card = next(
                card
                for card in source["candidates"]
                if card["label"] == source["runner_up_candidate_ref"]
            )
            runner_card["population"] = bound_scope["population"]
            runner_card["decision_timestamp"] = bound_scope["decision_timestamp"]
            runner_card["target"] = bound_scope["target"]
            runner_card["estimand"] = selected_card["estimand"]
            runner_card["explanatory_condition"] = selected_card["explanatory_condition"]
            evidence = self._spend_one_main(
                opened,
                query_id="legacy-ordinary-runner",
                spec=spec,
                candidate_scope=declared_scope,
            )
            self.assertEqual(len(_mains(opened["store"], opened["journal"])), 3)
            repair_disp = prepared["applied"]["disposition"]["disposition_sha256"]
            source["grounded_evidence"] = evidence
            selected = self._continue_from_preflight(
                opened["store"],
                source,
                prepared["preflight"],
            )
            self.assertEqual(selected["session_id"], opened["shown"]["session_id"])
            pending = finalize_session(
                selected,
                critic_result_from_packet_only(
                    selected["critic_input_packet"], "KILL_DATA_INFEASIBLE"
                ),
                store=opened["store"],
                repo_root=ROOT,
            )
            self.assertEqual(pending["session_state"], "RUNNER_UP_AWAITING_CRITIC")
            waiting = finalize_session(
                pending,
                critic_result_from_packet_only(
                    pending["critic_input_packet"], "PASS_TO_CLASSIFICATION"
                ),
                store=opened["store"],
                repo_root=ROOT,
            )
            packet = _with_selected_feats(
                submission(),
                selected["runner_up_critic_input_packet"],
            )
            packet["hypothesis_definition_sha256"] = selected["runner_up_definition_sha256"]
            done = apply_classification(
                waiting,
                packet,
                store=opened["store"],
                repo_root=ROOT,
                data_root=data_root,
            )
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            closed = self._cli_json(
                CLI.cmd_repair_continuation_close,
                repo_root=ROOT,
                explicit_data_root=data_root,
                disposition_sha256=repair_disp,
                reason_code="CONTINUATION_TERMINAL_REACHED",
                confirm_append_only=True,
            )
            self.assertEqual(closed["status"], "CLOSED", closed)
            readback = self._reopen_forge_run(data_root)
            self.assertEqual(readback.get("_exit"), 0, readback)
            self.assertEqual(readback.get("owner_final"), ACTION_OWNER_CANDIDATE)
            self.assertEqual(readback.get("run_identity_sha256"), binding["binding_sha256"])
            stage = (readback.get("stages") or [{}])[0]
            self.assertEqual(
                stage.get("selected_candidate_id"),
                selected["runner_up_candidate_id"],
            )
            self.assertEqual(
                readback.get("writes"),
                {"research_store": 0, "forge_run": 0, "session": 0},
            )
            self._spend_one_main(opened, query_id="legacy-ordinary-runner")
            self.assertEqual(len(_mains(opened["store"], opened["journal"])), 3)
            for record_id, digest in historical.items():
                self.assertEqual(_payloads(opened["store"]).get(record_id), digest, record_id)
