from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.document_runner import repository_git_snapshot
from solana_alpha_lab.factory.hfic_identity import assign_portfolio_ids
from solana_alpha_lab.factory.hfic_preflight import evidence_epoch_material, evidence_epoch_sha256
from solana_alpha_lab.factory.hfic_prospects import (
    HficProspectError,
    load_prospect_portfolio,
    query_prospects,
    validate_next_action_draft,
)
from solana_alpha_lab.factory.hfic_session import (
    HficSessionError,
    bind_next_epistemic_action,
    freeze_draft,
    load_session_bundle,
    prove_runtime,
    show_session,
)
from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent, ResearchStore
from tests.test_early_market_panel_importer import write_temp_capture
from solana_alpha_lab.factory.early_market_panel_importer import import_early_market_panel

CLI = ROOT / "scripts/hypothesis_forge.py"
NO_WORTHY = ROOT / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1.json"
HAPPY = ROOT / "tests/fixtures/hypothesis_forge/draft_happy_path_v1.json"
WAIT = ROOT / "tests/fixtures/hypothesis_forge/next_action_wait_valid_v1.json"
FORWARD = ROOT / "tests/fixtures/hypothesis_forge/next_action_forward_valid_v1.json"
CAPABILITY = ROOT / "tests/fixtures/hypothesis_forge/next_action_capability_valid_v1.json"
INVALID = ROOT / "tests/fixtures/hypothesis_forge/next_action_invalid_v1.json"
RESEARCH = ROOT / "docs/architecture/prospects/HFIC_SCIENTIFIC_DISCOVERY_ENGINE_RESEARCH_V1.md"
SKILL = ROOT / ".agents/skills/hypothesis-forge/SKILL.md"
OPERATOR = ROOT / "docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md"
COMMAND = ROOT / ".cursor/commands/hypothesis-forge.md"
CONFIG = ROOT / "configs/hypothesis_forge_independent_critic_v1.yaml"


def bind_draft(draft: dict, receipt: dict) -> dict:
    bound = dict(draft)
    bound["preflight_receipt_id"] = receipt["receipt_id"]
    bound["preflight_receipt_sha256"] = receipt["preflight_receipt_sha256"]
    bound["research_memory_as_of"] = receipt["research_memory_as_of"]
    context = receipt.get("forge_context_packet") or {}
    bound["truth_roots_used"] = list(context.get("truth_roots_used") or [])
    bound["prior_work_receipts"] = list(context.get("prior_work_receipts") or [])
    bound["owner_focus"] = receipt.get("owner_focus") or bound.get("owner_focus")
    return bound


def run_cli(*args: str, data_root: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["SMIAL_DATA_ROOT"] = str(data_root)
    return subprocess.run(
        [
            sys.executable,
            "-B",
            str(CLI),
            "--root",
            str(ROOT),
            "--data-root",
            str(data_root),
            *args,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _identities() -> list:
    draft = json.loads(NO_WORTHY.read_text(encoding="utf-8"))
    return assign_portfolio_ids(draft["candidates"])


def _frozen_stub(identities) -> dict[str, object]:
    return {
        "session_id": "HFIC-SESS-TESTNEXT0001",
        "critic_terminal": "NO_WORTHY_HYPOTHESIS",
        "selected_candidate_id": None,
        "evidence_epoch_sha256": "aa" * 32,
        "focus_key_sha256": "bb" * 32,
        "search_key_sha256": "cc" * 32,
        "forge_context_packet_sha256": "dd" * 32,
        "candidate_ids": [item.candidate_id for item in identities],
        "session_started_at": "2026-08-27T12:00:00Z",
    }


class ProspectPortfolioTests(unittest.TestCase):
    def test_portfolio_has_exactly_twenty_three_unique_records(self) -> None:
        portfolio = load_prospect_portfolio(ROOT)
        records = portfolio["records"]
        self.assertEqual(len(records), 23)
        ids = [item["prospect_id"] for item in records]
        ranks = [item["rank"] for item in records]
        self.assertEqual(ids, [f"HFIC-PROSPECT-{i:03d}" for i in range(1, 24)])
        self.assertEqual(ranks, list(range(1, 24)))
        self.assertEqual(len(set(ids)), 23)
        dispositions = {item["prospect_id"]: item["disposition"] for item in records}
        expected = {
            "HFIC-PROSPECT-001": "ADOPT_NOW",
            "HFIC-PROSPECT-002": "WATCH_TRIGGERED_ONLY",
            "HFIC-PROSPECT-003": "WATCH_TRIGGERED_ONLY",
            "HFIC-PROSPECT-004": "WATCH_TRIGGERED_ONLY",
            "HFIC-PROSPECT-005": "WATCH_TRIGGERED_ONLY",
            "HFIC-PROSPECT-006": "DEFERRED_CURRENT_HORIZON",
            "HFIC-PROSPECT-007": "WATCH_TRIGGERED_ONLY",
            "HFIC-PROSPECT-008": "PREREQUISITE_BLOCKED",
            "HFIC-PROSPECT-009": "PREREQUISITE_BLOCKED",
            "HFIC-PROSPECT-010": "WATCH_TRIGGERED_ONLY",
            "HFIC-PROSPECT-011": "WATCH_TRIGGERED_ONLY",
            "HFIC-PROSPECT-012": "PREREQUISITE_BLOCKED",
            "HFIC-PROSPECT-013": "WATCH_TRIGGERED_ONLY",
            "HFIC-PROSPECT-014": "PREREQUISITE_BLOCKED",
            "HFIC-PROSPECT-015": "PREREQUISITE_BLOCKED",
            "HFIC-PROSPECT-016": "DEFERRED_CURRENT_HORIZON",
            "HFIC-PROSPECT-017": "PREREQUISITE_BLOCKED",
            "HFIC-PROSPECT-018": "PREREQUISITE_BLOCKED",
            "HFIC-PROSPECT-019": "PREREQUISITE_BLOCKED",
            "HFIC-PROSPECT-020": "DEFERRED_CURRENT_HORIZON",
            "HFIC-PROSPECT-021": "DEFERRED_CURRENT_HORIZON",
            "HFIC-PROSPECT-022": "PREREQUISITE_BLOCKED",
            "HFIC-PROSPECT-023": "REJECTED_CURRENT_HORIZON",
        }
        self.assertEqual(dispositions, expected)
        for value in portfolio["authority"].values():
            self.assertIs(value, False)

    def test_query_returns_at_most_three_and_excludes_blocked(self) -> None:
        payload = query_prospects(ROOT, trigger="POST_NO_WORTHY_REVIEW", max_results=3)
        self.assertEqual(payload["returned_count"], 3)
        ids = [item["prospect_id"] for item in payload["records"]]
        self.assertEqual(ids, ["HFIC-PROSPECT-001", "HFIC-PROSPECT-004", "HFIC-PROSPECT-005"])
        rendered = json.dumps(payload)
        self.assertNotIn("Quality-Diversity mechanism map is a full MAP-Elites", rendered)
        research = RESEARCH.read_text(encoding="utf-8")
        self.assertGreater(len(research.encode("utf-8")), 30000)
        self.assertNotIn(research[:80], rendered)
        self.assertFalse(payload["authority"]["provider_read"])
        self.assertEqual(payload["default_forge_visibility"], "HIDDEN")
        blocked = {"HFIC-PROSPECT-008", "HFIC-PROSPECT-006", "HFIC-PROSPECT-023"}
        self.assertTrue(blocked.isdisjoint(ids))

    def test_query_rejects_invalid_trigger_and_max_results(self) -> None:
        with self.assertRaises(HficProspectError) as raised:
            query_prospects(ROOT, trigger="NOT_A_TRIGGER", max_results=3)
        self.assertEqual(str(raised.exception), "HFIC_PROSPECT_PORTFOLIO_INVALID")
        with self.assertRaises(HficProspectError):
            query_prospects(ROOT, trigger="POST_NO_WORTHY_REVIEW", max_results=4)

    def test_research_bytes_match_binding(self) -> None:
        raw = RESEARCH.read_bytes()
        self.assertEqual(len(raw), 36074)
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "1a2ac80b02e0a77a892d7ea27b2cff8a03ca99c3a1805c95c5d2611423cabf67",
        )
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r\n", raw)

    def test_prospects_cli_is_read_only_json(self) -> None:
        git_before = repository_git_snapshot(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            completed = run_cli(
                "prospects",
                "--trigger",
                "POST_NO_WORTHY_REVIEW",
                "--max-results",
                "3",
                "--format",
                "json",
                data_root=Path(tmp),
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["returned_count"], 3)
        git_after = repository_git_snapshot(ROOT)
        self.assertTrue(git_before.unchanged(git_after))


class NextActionBindingTests(unittest.TestCase):
    def test_valid_conditional_payloads_bind(self) -> None:
        identities = _identities()
        frozen = _frozen_stub(identities)
        for path, expected in (
            (WAIT, "WAIT_FOR_NEW_EVIDENCE"),
            (FORWARD, "FORWARD_DATA_OPTION_READY"),
            (CAPABILITY, "CAPABILITY_OPTION_READY"),
        ):
            draft = json.loads(path.read_text(encoding="utf-8"))
            action = bind_next_epistemic_action(
                draft,
                frozen_no_worthy=frozen,
                identities=identities,
                repo_root=ROOT,
            )
            self.assertEqual(action["action_type"], expected)
            self.assertEqual(action["generation_mode"], "MODEL_VALIDATED")
            self.assertTrue(action["action_id"].startswith("HFIC-NEXT-"))
            self.assertEqual(action["hfic_protocol"], "HFIC-V1.1")
            self.assertEqual(action["prompt_version"], "HFIC-NEXT-V1.0")

    def test_unknown_prospect_fails_closed(self) -> None:
        identities = _identities()
        draft = json.loads(INVALID.read_text(encoding="utf-8"))
        with self.assertRaises(HficSessionError) as raised:
            bind_next_epistemic_action(
                draft,
                frozen_no_worthy=_frozen_stub(identities),
                identities=identities,
                repo_root=ROOT,
            )
        self.assertEqual(str(raised.exception), "HFIC_PROSPECT_REF_UNKNOWN")

    def test_watch_without_post_and_blocked_prospects_fail_closed(self) -> None:
        identities = _identities()
        frozen = _frozen_stub(identities)
        for prospect_id in ("HFIC-PROSPECT-002", "HFIC-PROSPECT-008", "HFIC-PROSPECT-023"):
            draft = json.loads(WAIT.read_text(encoding="utf-8"))
            draft["prospect_ids"] = [prospect_id]
            with self.assertRaises(HficSessionError) as raised:
                bind_next_epistemic_action(
                    draft,
                    frozen_no_worthy=frozen,
                    identities=identities,
                    repo_root=ROOT,
                )
            self.assertEqual(str(raised.exception), "HFIC_PROSPECT_REF_UNKNOWN")

    def test_missing_draft_uses_deterministic_wait(self) -> None:
        identities = _identities()
        action = bind_next_epistemic_action(
            None,
            frozen_no_worthy=_frozen_stub(identities),
            identities=identities,
            repo_root=ROOT,
        )
        self.assertEqual(action["action_type"], "WAIT_FOR_NEW_EVIDENCE")
        self.assertEqual(action["reason_code"], "NEXT_ACTION_GENERATION_FALLBACK")
        self.assertEqual(action["generation_mode"], "DETERMINISTIC_SAFE_FALLBACK")
        self.assertEqual(action["action_payload"]["wake_on"], ["EVIDENCE_EPOCH_CHANGED"])
        for claim in (
            "NO_ALPHA",
            "NO_AUTONOMOUS_GENERATOR",
            "NO_DISCOVERY_RANKER_TRIGGER_PROVEN",
            "NO_ARCH_INTENT_006_FULL_IMPLEMENTATION",
            "NO_QUALITY_DIVERSITY_ENGINE",
            "NO_VOI_SCHEDULER",
            "NO_SEQUENTIAL_INFERENCE_ENGINE",
            "NO_PROVIDER_OR_EXPERIMENT_AUTHORITY",
        ):
            self.assertIn(claim, action["non_claims"])

    def test_selected_path_rejects_next_action(self) -> None:
        draft = json.loads(HAPPY.read_text(encoding="utf-8"))
        next_action = json.loads(WAIT.read_text(encoding="utf-8"))
        with self.assertRaises(HficSessionError) as raised:
            freeze_draft(draft, repo_root=ROOT, next_action_draft=next_action)
        self.assertEqual(str(raised.exception), "HFIC_NEXT_ACTION_FORBIDDEN_FOR_SELECTED")

    def test_packet_too_large_is_typed(self) -> None:
        draft = json.loads(WAIT.read_text(encoding="utf-8"))
        draft["evidence_gap"] = "x" * (32 * 1024)
        with self.assertRaises(HficProspectError) as raised:
            validate_next_action_draft(draft, repo_root=ROOT)
        self.assertEqual(str(raised.exception), "HFIC_NEXT_ACTION_PACKET_TOO_LARGE")


class NextActionPersistTests(unittest.TestCase):
    _tmp: tempfile.TemporaryDirectory[str] | None = None
    _template: Path
    _receipt: dict

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        source = Path(cls._tmp.name) / "source"
        write_temp_capture(source, eligible=10)
        data_root = Path(cls._tmp.name) / "rdp"
        data_root.mkdir()
        import_early_market_panel(
            source_root=source,
            data_root=data_root,
            source_receipt_path=source / "source_receipt.json",
        )
        preflight = run_cli(
            "preflight",
            "--owner-focus",
            "AUTO",
            "--format",
            "json",
            data_root=data_root,
        )
        if preflight.returncode != 0:
            raise AssertionError(preflight.stderr)
        receipt = json.loads(preflight.stdout)
        if "HFIC-PROSPECT-001" in json.dumps(receipt):
            raise AssertionError("prospect_leaked_into_preflight")
        if "HFIC-NEXT-V1.0" in json.dumps(receipt.get("forge_context_packet") or {}):
            raise AssertionError("next_prompt_leaked_into_preflight")
        template = Path(cls._tmp.name) / "template"
        shutil.copytree(data_root, template)
        cls._template = template
        cls._receipt = receipt

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._tmp is not None:
            cls._tmp.cleanup()
            cls._tmp = None

    def _clone_store(self, tmp: str) -> Path:
        data_root = Path(tmp) / "rdp"
        shutil.copytree(self._template, data_root)
        return data_root

    def test_no_worthy_wait_persists_atomically_and_replays(self) -> None:
        git_before = repository_git_snapshot(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            data_root = self._clone_store(tmp)
            receipt = self._receipt
            epoch_before = evidence_epoch_sha256(evidence_epoch_material(ROOT, data_root))
            inventory_before = ResearchStore(data_root).diagnostics().committed_inventory_sha256
            receipt_path = Path(tmp) / "preflight.json"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            draft_path = Path(tmp) / "draft.json"
            draft_path.write_text(
                json.dumps(bind_draft(json.loads(NO_WORTHY.read_text(encoding="utf-8")), receipt)),
                encoding="utf-8",
            )
            wait_path = Path(tmp) / "wait.json"
            wait_path.write_text(WAIT.read_text(encoding="utf-8"), encoding="utf-8")
            frozen_run = run_cli(
                "freeze",
                "--draft",
                str(draft_path),
                "--preflight-receipt",
                str(receipt_path),
                "--next-action",
                str(wait_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(frozen_run.returncode, 0, frozen_run.stderr)
            frozen = json.loads(frozen_run.stdout)
            self.assertEqual(frozen["critic_terminal"], "NO_WORTHY_HYPOTHESIS")
            self.assertEqual(frozen["next"], "WAIT_FOR_NEW_EVIDENCE")
            self.assertEqual(frozen["next_action_status"], "RECORDED")
            self.assertIsNone(frozen["selected_candidate_id"])
            self.assertFalse(frozen["critic_launched"])
            action_id = frozen["next_action"]["action_id"]
            action_sha = frozen["next_action"]["action_id"]
            replay = run_cli("preflight", "--owner-focus", "AUTO", "--format", "json", data_root=data_root)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            replayed = json.loads(replay.stdout)
            self.assertEqual(replayed["action"], "RETURN_EXISTING_SESSION")
            self.assertEqual(replayed["session_id"], frozen["session_id"])
            shown = run_cli(
                "show-session",
                "--session-id",
                frozen["session_id"],
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(shown.returncode, 0, shown.stderr)
            shown_payload = json.loads(shown.stdout)
            self.assertEqual(shown_payload["next"], "WAIT_FOR_NEW_EVIDENCE")
            self.assertEqual(shown_payload["next_action"]["action_id"], action_id)
            proved = run_cli(
                "prove-runtime",
                "--session-id",
                frozen["session_id"],
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(proved.returncode, 0, proved.stderr)
            proof = json.loads(proved.stdout)
            self.assertEqual(proof["provider_calls_actual"], 0)
            self.assertTrue(proof["git_composite_unchanged"])
            epoch_after = evidence_epoch_sha256(evidence_epoch_material(ROOT, data_root))
            self.assertEqual(epoch_before, epoch_after)
            self.assertNotEqual(
                inventory_before,
                ResearchStore(data_root).diagnostics().committed_inventory_sha256,
            )
            del action_sha
        git_after = repository_git_snapshot(ROOT)
        self.assertTrue(git_before.unchanged(git_after))

    def test_invalid_next_action_does_not_mutate_rdp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = self._clone_store(tmp)
            receipt = self._receipt
            store = ResearchStore(data_root)
            inventory_before = store.diagnostics().committed_inventory_sha256
            draft = bind_draft(json.loads(NO_WORTHY.read_text(encoding="utf-8")), receipt)
            with self.assertRaises(HficSessionError) as raised:
                freeze_draft(
                    draft,
                    preflight_receipt=receipt,
                    store=store,
                    repo_root=ROOT,
                    next_action_draft=json.loads(INVALID.read_text(encoding="utf-8")),
                )
            self.assertEqual(str(raised.exception), "HFIC_PROSPECT_REF_UNKNOWN")
            self.assertEqual(inventory_before, store.diagnostics().committed_inventory_sha256)

    def test_missing_draft_falls_back_to_wait(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = self._clone_store(tmp)
            receipt = self._receipt
            frozen = freeze_draft(
                bind_draft(json.loads(NO_WORTHY.read_text(encoding="utf-8")), receipt),
                preflight_receipt=receipt,
                store=ResearchStore(data_root),
                repo_root=ROOT,
            )
            self.assertEqual(frozen["next"], "WAIT_FOR_NEW_EVIDENCE")
            self.assertEqual(frozen["next_action"]["generation_mode"], "DETERMINISTIC_SAFE_FALLBACK")

    def test_forward_and_capability_do_not_execute(self) -> None:
        for fixture, expected in (
            (FORWARD, "FORWARD_DATA_OPTION_READY"),
            (CAPABILITY, "CAPABILITY_OPTION_READY"),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                data_root = self._clone_store(tmp)
                receipt = self._receipt
                frozen = freeze_draft(
                    bind_draft(json.loads(NO_WORTHY.read_text(encoding="utf-8")), receipt),
                    preflight_receipt=receipt,
                    store=ResearchStore(data_root),
                    repo_root=ROOT,
                    next_action_draft=json.loads(fixture.read_text(encoding="utf-8")),
                )
                self.assertEqual(frozen["next"], expected)
                self.assertEqual(
                    frozen["next_action"]["owner_gate"]["phrase_status"],
                    "PROPOSED_NOT_AUTHORITY",
                )
                self.assertEqual(frozen["next_action"]["authority"]["experiment_execution"], 0)
                self.assertEqual(frozen["next_action"]["authority"]["provider_api_rpc_wss_calls"], 0)

    def test_corrupt_action_blob_fails_closed(self) -> None:
        from solana_alpha_lab.factory.hfic_session import _load_artifact_by_sha

        expected = "ab" * 32
        with self.assertRaises(HficSessionError) as raised:
            _load_artifact_by_sha(
                [
                    (
                        {
                            "artifact_kind": "NEXT_EPISTEMIC_ACTION",
                            "payload_sha256": expected,
                        },
                        '{"action_type":"WAIT_FOR_NEW_EVIDENCE"}',
                    )
                ],
                artifact_kind="NEXT_EPISTEMIC_ACTION",
                expected_sha=expected,
            )
        self.assertEqual(str(raised.exception), "HFIC_NEXT_ACTION_ARTIFACT_HASH_MISMATCH")
        with self.assertRaises(HficSessionError) as missing:
            _load_artifact_by_sha(
                [],
                artifact_kind="NEXT_EPISTEMIC_ACTION",
                expected_sha=expected,
            )
        self.assertEqual(str(missing.exception), "HFIC_NEXT_ACTION_ARTIFACT_MISSING")

    def test_historical_stop_is_legacy_not_recorded(self) -> None:
        from solana_alpha_lab.factory.hfic_preflight import FORGE_CONTEXT_ARTIFACT_DIR
        from solana_alpha_lab.factory.run_passport import canonical_sha256

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ResearchStore(data_root)
            now = datetime(2026, 8, 20, tzinfo=UTC)
            session_id = "HFIC-SESS-LEGACYSTOP0001"
            packet = {"legacy_historical": True, "session_id": session_id}
            from solana_alpha_lab.factory.run_passport import canonical_json_bytes

            packet_bytes = canonical_json_bytes(packet).decode("utf-8")
            context_digest = canonical_sha256(packet)
            blob = data_root / FORGE_CONTEXT_ARTIFACT_DIR / f"{context_digest}.json"
            blob.parent.mkdir(parents=True, exist_ok=True)
            blob.write_bytes(canonical_json_bytes(packet))
            receipt = {
                "session_id": session_id,
                "session_state": "SYNTHESIS_COMPLETE",
                "evidence_epoch_sha256": "11" * 32,
                "focus_key_sha256": "22" * 32,
                "search_key_sha256": "33" * 32,
                "prompt_version": "HFIC-V1.1",
                "live_git_head": "0" * 40,
                "store_inventory_digest": "44" * 32,
                "candidate_ids": [f"HFIC-CAND-{i:012X}" for i in range(4)],
                "selected_candidate_id": None,
                "runner_up_candidate_id": "HFIC-CAND-000000000001",
                "critic_input_packet_sha256": None,
                "critic_result_sha256": None,
                "critic_launched": False,
                "critic_terminal": "NO_WORTHY_HYPOTHESIS",
                "lane_classifier_terminal": None,
                "decision_event_ids": [f"HFIC-DEC-{session_id}-NO-WORTHY"],
                "next": "STOP",
                "forge_context_packet_sha256": context_digest,
                "authority": {
                    "git_mutation": 0,
                    "experiment_execution": 0,
                    "provider_api_rpc_wss_calls": 0,
                },
                "no_git_fence_receipt": {
                    "preflight_git_composite_sha256": "66" * 32,
                    "final_git_composite_sha256": "66" * 32,
                    "provider_calls_actual": 0,
                },
                "created_at": "2026-08-20T00:00:00Z",
                "session_started_at": "2026-08-20T00:00:00Z",
            }
            receipt_bytes = json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            receipt_sha = hashlib.sha256(receipt_bytes.encode("utf-8")).hexdigest()

            def event(record_id: str, kind: RecordKind, entity_id: str, payload: dict) -> ResearchEvent:
                payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                return ResearchEvent(
                    record_id=record_id,
                    record_kind=kind,
                    entity_id=entity_id,
                    hypothesis_version_id=payload.get("hypothesis_version_id"),
                    run_id=None,
                    transaction_id=f"RESEARCH-TXN-{session_id}",
                    effective_at=now,
                    first_reliable_available_at=now,
                    supersedes_record_id=None,
                    payload_json=payload_json,
                    payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
                    schema_version="1.0",
                    producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
                    producer_git_sha="0" * 40,
                    created_at=now,
                )

            records = [
                event(
                    f"HFIC-CYCLE-{session_id}-NO-WORTHY",
                    RecordKind.RESEARCH_CYCLE,
                    session_id,
                    {
                        "research_cycle_id": f"{session_id}-NO-WORTHY",
                        "session_id": session_id,
                        "phase": "SYNTHESIS_COMPLETE",
                        "hfic_protocol": "HFIC-V1.1",
                        "prompt_version": "HFIC-V1.1",
                        "owner_focus": "AUTO",
                        "evidence_epoch_sha256": "11" * 32,
                        "focus_key_sha256": "22" * 32,
                        "search_key_sha256": "33" * 32,
                        "selected_candidate_id": None,
                        "candidate_ids": receipt["candidate_ids"],
                        "critic_launched": False,
                        "critic_terminal": "NO_WORTHY_HYPOTHESIS",
                        "next": "STOP",
                        "session_receipt_sha256": receipt_sha,
                        "forge_context_packet_sha256": context_digest,
                    },
                ),
                event(
                    f"HFIC-ART-FORGE-CONTEXT-{session_id}",
                    RecordKind.RESEARCH_ARTIFACT,
                    f"HFIC-ART-FORGE-CONTEXT-{session_id}",
                    {
                        "research_artifact_id": f"HFIC-ART-FORGE-CONTEXT-{session_id}",
                        "session_id": session_id,
                        "hfic_protocol": "HFIC-V1.1",
                        "artifact_kind": "FORGE_CONTEXT_PACKET",
                        "payload_canonical": packet_bytes,
                        "payload_sha256": context_digest,
                    },
                ),
                event(
                    f"HFIC-DEC-{session_id}-NO-WORTHY",
                    RecordKind.DECISION_EVENT,
                    f"HFIC-DEC-{session_id}-NO-WORTHY",
                    {
                        "decision_event_id": f"HFIC-DEC-{session_id}-NO-WORTHY",
                        "session_id": session_id,
                        "hfic_protocol": "HFIC-V1.1",
                        "decision_kind": "REJECT",
                        "reason_code": "NO_WORTHY_HYPOTHESIS",
                        "hypothesis_version_id": None,
                    },
                ),
                event(
                    f"HFIC-ART-SESSION-RECEIPT-{session_id}",
                    RecordKind.RESEARCH_ARTIFACT,
                    f"HFIC-ART-SESSION-RECEIPT-{session_id}",
                    {
                        "research_artifact_id": f"HFIC-ART-SESSION-RECEIPT-{session_id}",
                        "session_id": session_id,
                        "hfic_protocol": "HFIC-V1.1",
                        "artifact_kind": "SESSION_RECEIPT",
                        "payload_canonical": receipt_bytes,
                        "payload_sha256": receipt_sha,
                    },
                ),
            ]
            for index, candidate_id in enumerate(receipt["candidate_ids"]):
                records.append(
                    event(
                        f"HFIC-HYP-{candidate_id}",
                        RecordKind.HYPOTHESIS_VERSION,
                        candidate_id,
                        {
                            "hypothesis_version_id": candidate_id,
                            "session_id": session_id,
                            "hfic_protocol": "HFIC-V1.1",
                            "statement": f"legacy-{index}",
                            "claim": f"legacy-{index}",
                            "role_in_session": "CONSIDERED_UNSELECTED",
                        },
                    )
                )
            store.append(records, transaction_id=f"RESEARCH-TXN-{session_id}")
            bundle = load_session_bundle(store, session_id)
            self.assertIsNotNone(bundle)
            assert bundle is not None
            self.assertEqual(bundle["next"], "STOP")
            self.assertIsNone(bundle["next_action"])
            self.assertEqual(bundle["next_action_status"], "LEGACY_NOT_RECORDED")
            shown = show_session(store, session_id, repo_root=ROOT)
            self.assertEqual(shown["next_action_status"], "LEGACY_NOT_RECORDED")
            from solana_alpha_lab.factory.hfic_session import persist_no_worthy_session

            replayed = persist_no_worthy_session(
                store,
                {"session_id": session_id, "next": "STOP"},
                repo_root=ROOT,
                identities=[],
            )
            self.assertEqual(replayed["action_type"], "STOP")
            self.assertIsNone(load_session_bundle(store, session_id)["next_action"])


class OperatorContractTests(unittest.TestCase):
    def test_prompt_c_and_hidden_prospects(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        operator = OPERATOR.read_text(encoding="utf-8")
        command = COMMAND.read_text(encoding="utf-8")
        config = CONFIG.read_text(encoding="utf-8")
        for text in (skill, operator, command, config):
            self.assertIn("HFIC-NEXT-V1.0", text)
            self.assertIn("ZERO_MID_CYCLE_OWNER_INTERVENTION", text)
        self.assertIn("prompt_version: HFIC-V1.1", config)
        self.assertIn("HFIC-V1.1", skill)
        self.assertIn("NO_WORTHY", skill)
        self.assertIn("--next-action", skill)
        self.assertIn("POST_NO_WORTHY_REVIEW", skill)
        self.assertNotIn("MAP-Elites implementation", skill)


if __name__ == "__main__":
    unittest.main()
