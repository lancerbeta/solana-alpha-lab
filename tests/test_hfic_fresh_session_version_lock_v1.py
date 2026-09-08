from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    HficSessionError,
    freeze_draft,
    list_hfic_sessions,
)
from solana_alpha_lab.factory.research_store import ResearchStore
from tests.test_hfic_cli import bind_draft, run_cli  # noqa: E402

DRAFT_V11 = ROOT / "tests/fixtures/hypothesis_forge/draft_happy_path_v1.json"
DRAFT_V12 = ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json"


def _record_ids(store: ResearchStore) -> list[str]:
    return sorted(str(record.record_id) for record in store.iter_committed_records())


def _hfic_session_or_candidate_ids(store: ResearchStore) -> list[str]:
    ids: list[str] = []
    for record in store.iter_committed_records():
        record_id = str(record.record_id)
        if record_id.startswith(("HFIC-SESS", "HFIC-HYP-", "HFIC-CAND", "HFIC-CYCLE")):
            ids.append(record_id)
            continue
        payload = json.loads(record.payload_json)
        if payload.get("hfic_protocol") is not None:
            ids.append(record_id)
    return sorted(ids)


class FreshSessionVersionLockTests(unittest.TestCase):
    def test_t1_fresh_downgrade_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            preflight = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            receipt = json.loads(preflight.stdout)
            self.assertEqual(receipt["action"], "START_NEW_SESSION")
            self.assertEqual(receipt["prompt_version"], "HFIC-V1.2")
            receipt_path = Path(tmp) / "preflight.json"
            receipt_path.write_text(preflight.stdout, encoding="utf-8")
            draft_path = Path(tmp) / "draft_v11.json"
            draft_path.write_text(
                json.dumps(bind_draft(json.loads(DRAFT_V11.read_text(encoding="utf-8")), receipt)),
                encoding="utf-8",
            )
            frozen = run_cli(
                "freeze",
                "--draft",
                str(draft_path),
                "--preflight-receipt",
                str(receipt_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertNotEqual(frozen.returncode, 0, frozen.stdout)
            self.assertIn("FRESH_SESSION_DRAFT_VERSION_MISMATCH", frozen.stderr)

    def test_t2_failed_downgrade_does_not_burn_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            preflight = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            receipt = json.loads(preflight.stdout)
            self.assertEqual(receipt["action"], "START_NEW_SESSION")
            store = ResearchStore(data_root)
            inventory_before = store.diagnostics().committed_inventory_sha256
            ids_before = _record_ids(store)
            session_ids_before = _hfic_session_or_candidate_ids(store)
            receipt_path = Path(tmp) / "preflight.json"
            receipt_path.write_text(preflight.stdout, encoding="utf-8")
            draft_path = Path(tmp) / "draft_v11.json"
            draft_path.write_text(
                json.dumps(bind_draft(json.loads(DRAFT_V11.read_text(encoding="utf-8")), receipt)),
                encoding="utf-8",
            )
            frozen = run_cli(
                "freeze",
                "--draft",
                str(draft_path),
                "--preflight-receipt",
                str(receipt_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertNotEqual(frozen.returncode, 0, frozen.stdout)
            self.assertIn("FRESH_SESSION_DRAFT_VERSION_MISMATCH", frozen.stderr)
            store_after = ResearchStore(data_root)
            self.assertEqual(
                inventory_before,
                store_after.diagnostics().committed_inventory_sha256,
            )
            self.assertEqual(ids_before, _record_ids(store_after))
            self.assertEqual(session_ids_before, _hfic_session_or_candidate_ids(store_after))
            self.assertEqual(list_hfic_sessions(store_after), [])
            replay = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(replay.returncode, 0, replay.stderr)
            replayed = json.loads(replay.stdout)
            self.assertEqual(replayed["action"], "START_NEW_SESSION")
            self.assertNotEqual(replayed["action"], "RETURN_EXISTING_SESSION")
            self.assertFalse(str(replayed["action"]).startswith("RESUME_"))
            self.assertNotEqual(replayed["action"], "SEARCH_BUDGET_EXHAUSTED")

    def test_t3_current_v12_succeeds_with_grounding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            preflight = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            receipt = json.loads(preflight.stdout)
            self.assertEqual(receipt["action"], "START_NEW_SESSION")
            self.assertEqual(receipt["prompt_version"], "HFIC-V1.2")
            receipt_path = Path(tmp) / "preflight.json"
            receipt_path.write_text(preflight.stdout, encoding="utf-8")
            draft_path = Path(tmp) / "draft_v12.json"
            draft_path.write_text(
                json.dumps(bind_draft(json.loads(DRAFT_V12.read_text(encoding="utf-8")), receipt)),
                encoding="utf-8",
            )
            frozen_run = run_cli(
                "freeze",
                "--draft",
                str(draft_path),
                "--preflight-receipt",
                str(receipt_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(frozen_run.returncode, 0, frozen_run.stderr)
            frozen = json.loads(frozen_run.stdout)
            self.assertEqual(frozen["session_state"], "FROZEN_AWAITING_CRITIC")
            self.assertEqual(frozen["prompt_version"], "HFIC-V1.2")
            packet = frozen["critic_input_packet"]
            self.assertEqual(packet["packet_version"], "1.3")
            self.assertEqual(packet["generator_prompt_version"], "HFIC-V1.2")
            grounded = frozen.get("grounded_candidates")
            self.assertIsInstance(grounded, list)
            self.assertGreaterEqual(len(grounded), 4)
            self.assertTrue(any(item.get("grounding") for item in grounded))

    def test_t4_historical_v11_readable_without_current_start(self) -> None:
        draft = json.loads(DRAFT_V11.read_text(encoding="utf-8"))
        frozen = freeze_draft(
            draft,
            preflight_receipt={"receipt_id": "HFIC-PREFLIGHT-FIXTURE-001"},
            repo_root=ROOT,
        )
        self.assertEqual(frozen["prompt_version"], "HFIC-V1.1")
        packet = frozen["critic_input_packet"]
        self.assertEqual(packet["packet_version"], "1.1")
        self.assertEqual(packet["generator_prompt_version"], "HFIC-V1.1")
        self.assertNotIn("grounded_candidates", frozen)

    def test_guard_does_not_auto_upgrade_v11_labels(self) -> None:
        draft = json.loads(DRAFT_V11.read_text(encoding="utf-8"))
        receipt = {
            "action": "START_NEW_SESSION",
            "prompt_version": "HFIC-V1.2",
        }
        with self.assertRaises(HficSessionError) as raised:
            freeze_draft(draft, preflight_receipt=receipt, repo_root=ROOT)
        self.assertEqual(str(raised.exception), "FRESH_SESSION_DRAFT_VERSION_MISMATCH")
        self.assertEqual(draft["packet_version"], "1.1")
        self.assertEqual(draft["generator_prompt_version"], "HFIC-V1.1")
