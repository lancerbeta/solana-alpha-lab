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
    ACTION_SEARCH_EXHAUSTED,
    evaluate_forge_run,
)
from solana_alpha_lab.factory.hfic_session import (
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
        journal = str(shown["search_key_sha256"])
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            run_recorded_discovery_query,
        )

        rows = SnapshotTargetTests()._rows_legal()
        census = [_census()]
        binding = _binding_mixed()
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
            )
        self.assertEqual(_forge_run_count(store), 0)
        return {
            "store": store,
            "git": git,
            "draft": draft,
            "frozen": frozen,
            "receipt": receipt,
            "shown": shown,
            "journal": journal,
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
            closed = close_repair_continuation(
                store,
                applied["disposition"]["disposition_sha256"],
                git_sha=opened["git"].head_sha,
            )
            self.assertEqual(closed["status"], "CLOSED")
            self.assertTrue(closed.get("forge_run_receipt_sha256"))
            self.assertEqual(len(_mains(store, opened["journal"])), before_looks)
            self.assertEqual(_forge_run_count(store), 1)

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
