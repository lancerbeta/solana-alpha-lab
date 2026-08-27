from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

CLI = ROOT / "scripts" / "hypothesis_forge.py"


def bind_draft(draft: dict, receipt: dict) -> dict:
    bound = dict(draft)
    bound["preflight_receipt_id"] = receipt["receipt_id"]
    bound["preflight_receipt_sha256"] = receipt["preflight_receipt_sha256"]
    bound["research_memory_as_of"] = receipt["research_memory_as_of"]
    context = receipt.get("forge_context_packet") or {}
    bound["truth_roots_used"] = list(context.get("truth_roots_used") or bound.get("truth_roots_used") or [])
    bound["prior_work_receipts"] = list(
        context.get("prior_work_receipts") or bound.get("prior_work_receipts") or []
    )
    bound["owner_focus"] = receipt.get("owner_focus") or bound.get("owner_focus")
    return bound


def run_cli(*args: str, data_root: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    # Nested uv inside GitHub's 10-minute validate job blows the budget.
    # CLI tests must exec the current interpreter with -B only.
    merged = dict(os.environ)
    if env:
        merged.update(env)
    merged["SMIAL_DATA_ROOT"] = str(data_root)
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
        env=merged,
        capture_output=True,
        text=True,
        check=False,
    )


class HficCliContractTests(unittest.TestCase):
    def test_cli_exposes_required_commands(self) -> None:
        completed = run_cli("--help", data_root=Path(tempfile.gettempdir()))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        for command in (
            "preflight",
            "freeze",
            "finalize",
            "show-session",
            "prior",
            "pending",
            "revise",
            "classify",
            "backfill-legacy",
            "prove-runtime",
            "inventory-placeholder-times",
            "apply-provenance-correction",
        ):
            self.assertIn(command, completed.stdout)

    def test_apply_provenance_correction_requires_confirm_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            completed = run_cli(
                "apply-provenance-correction",
                "--format",
                "json",
                data_root=Path(tmp),
            )
        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        self.assertIn("PROVENANCE_CORRECTION_CONFIRM_REQUIRED", completed.stderr)

    def test_cli_help_documents_placeholder_inventory_and_correction(self) -> None:
        completed = run_cli(
            "apply-provenance-correction",
            "--help",
            data_root=Path(tempfile.gettempdir()),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--confirm-append-only", completed.stdout)
        inventory = run_cli(
            "inventory-placeholder-times",
            "--help",
            data_root=Path(tempfile.gettempdir()),
        )
        self.assertEqual(inventory.returncode, 0, inventory.stderr)
        self.assertIn("placeholder", inventory.stdout.casefold())

    def test_preflight_json_never_leaks_physical_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            completed = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                "--no-auto-commission",
                data_root=data_root,
            )
            rendered = completed.stdout + completed.stderr
            self.assertNotIn(str(data_root), rendered)
            self.assertNotIn(str(ROOT), rendered)
            if completed.returncode == 0:
                payload = json.loads(completed.stdout)
                self.assertIn(payload.get("action"), {
                    "START_NEW_SESSION",
                    "RESUME_CRITIC",
                    "RESUME_FINALIZE",
                    "RESUME_REVISE",
                    "RESUME_CLASSIFY",
                    "RETURN_EXISTING_SESSION",
                    "STOP",
                })

    def test_c3_c4_mismatch_is_blocked_before_critic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            receipt = Path(tmp) / "preflight.json"
            receipt.write_text(
                json.dumps(
                    {
                        "evidence_epoch_sha256": "aa" * 32,
                        "focus_key_sha256": "bb" * 32,
                        "search_key_sha256": "cc" * 32,
                        "owner_focus": "AUTO",
                    }
                ),
                encoding="utf-8",
            )
            completed = run_cli(
                "freeze",
                "--draft",
                str(ROOT / "tests/fixtures/hypothesis_forge/draft_c3_c4_mismatch_v1.json"),
                "--preflight-receipt",
                str(receipt),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertNotEqual(completed.returncode, 0, completed.stdout)
            self.assertIn("CROSS_REFERENCE_MISMATCH", completed.stderr)

    def test_show_session_prior_and_prove_are_not_stubs(self) -> None:
        completed = run_cli("show-session", "--help", data_root=Path(tempfile.gettempdir()))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        completed = run_cli("prior", "--help", data_root=Path(tempfile.gettempdir()))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        completed = run_cli(
            "prove-runtime",
            "--help",
            data_root=Path(tempfile.gettempdir()),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


class HficTempRootE2ETests(unittest.TestCase):
    def test_preflight_freeze_finalize_replay_snapshot_restore(self) -> None:
        from solana_alpha_lab.factory.document_runner import repository_git_snapshot
        from solana_alpha_lab.factory.fast_lane_snapshot import (
            export_snapshot,
            restore_snapshot,
        )
        from solana_alpha_lab.factory.research_store import ResearchStore

        git_before = repository_git_snapshot(ROOT)
        happy = ROOT / "tests/fixtures/hypothesis_forge/draft_happy_path_v1.json"
        mismatch = ROOT / "tests/fixtures/hypothesis_forge/draft_c3_c4_mismatch_v1.json"
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            snapshot_root = Path(tmp) / "snapshot"
            restore_root = Path(tmp) / "restored"
            preflight = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            preflight_payload = json.loads(preflight.stdout)
            self.assertEqual(preflight_payload["action"], "START_NEW_SESSION")
            self.assertEqual(preflight_payload["commissioning"]["provider_calls_actual"], 0)
            self.assertNotIn(str(data_root), preflight.stdout)
            receipt_path = Path(tmp) / "preflight.json"
            receipt_path.write_text(preflight.stdout, encoding="utf-8")
            happy_bound = Path(tmp) / "draft_bound.json"
            happy_bound.write_text(
                json.dumps(bind_draft(json.loads(happy.read_text(encoding="utf-8")), preflight_payload)),
                encoding="utf-8",
            )
            mismatch_bound = Path(tmp) / "draft_mismatch.json"
            mismatch_bound.write_text(
                json.dumps(bind_draft(json.loads(mismatch.read_text(encoding="utf-8")), preflight_payload)),
                encoding="utf-8",
            )

            blocked = run_cli(
                "freeze",
                "--draft",
                str(mismatch_bound),
                "--preflight-receipt",
                str(receipt_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertNotEqual(blocked.returncode, 0, blocked.stdout)
            self.assertIn("CROSS_REFERENCE_MISMATCH", blocked.stderr)

            frozen_run = run_cli(
                "freeze",
                "--draft",
                str(happy_bound),
                "--preflight-receipt",
                str(receipt_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(frozen_run.returncode, 0, frozen_run.stderr)
            frozen = json.loads(frozen_run.stdout)
            self.assertEqual(frozen["session_state"], "FROZEN_AWAITING_CRITIC")
            packet = frozen["critic_input_packet"]
            self.assertTrue(packet["truth_roots_used"])
            self.assertFalse(str(packet["research_memory_as_of"]).startswith("1970-01-01"))
            self.assertGreaterEqual(len(frozen["candidate_ids"]), 4)
            session_id = frozen["session_id"]
            search_key = preflight_payload["search_key_sha256"]

            pending = run_cli(
                "pending",
                "--search-key",
                search_key,
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(pending.returncode, 0, pending.stderr)
            pending_payload = json.loads(pending.stdout)
            self.assertGreaterEqual(pending_payload["match_count"], 1)
            self.assertEqual(pending_payload["sessions"][0]["session_id"], session_id)

            by_key = run_cli(
                "show-session",
                "--search-key",
                search_key,
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(by_key.returncode, 0, by_key.stderr)
            shown_frozen = json.loads(by_key.stdout)
            self.assertEqual(shown_frozen["session_id"], session_id)
            self.assertIn("critic_input_packet", shown_frozen)
            self.assertTrue(shown_frozen["candidates_retrievable"])
            self.assertTrue(shown_frozen["artifacts_retrievable"])

            freeze_again = run_cli(
                "freeze",
                "--draft",
                str(happy_bound),
                "--preflight-receipt",
                str(receipt_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(freeze_again.returncode, 0, freeze_again.stderr)
            self.assertEqual(json.loads(freeze_again.stdout)["session_id"], session_id)

            forged = dict(preflight_payload)
            forged["preflight_receipt_sha256"] = "ff" * 32
            forged_path = Path(tmp) / "forged_preflight.json"
            forged_path.write_text(json.dumps(forged), encoding="utf-8")
            forged_draft = bind_draft(
                json.loads(happy.read_text(encoding="utf-8")),
                preflight_payload,
            )
            forged_draft["preflight_receipt_sha256"] = "ff" * 32
            forged_draft_path = Path(tmp) / "forged_draft.json"
            forged_draft_path.write_text(json.dumps(forged_draft), encoding="utf-8")
            forged_run = run_cli(
                "freeze",
                "--draft",
                str(forged_draft_path),
                "--preflight-receipt",
                str(forged_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertNotEqual(forged_run.returncode, 0, forged_run.stdout)
            self.assertIn("PREFLIGHT_RECEIPT_HASH_MISMATCH", forged_run.stderr)

            resume = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(resume.returncode, 0, resume.stderr)
            resume_payload = json.loads(resume.stdout)
            self.assertEqual(resume_payload["action"], "RESUME_CRITIC")
            self.assertEqual(resume_payload["session_id"], session_id)
            self.assertIn("critic_input_packet", resume_payload)

            critic = {
                "schema": "smial.hypothesis-critic-result",
                "schema_version": "1.1",
                "session_id": session_id,
                "critic_input_packet_sha256": frozen["critic_input_packet_sha256"],
                "selected_candidate_id": frozen["selected_candidate_id"],
                "selected_definition_sha256": frozen["selected_definition_sha256"],
                "critic_prompt_version": "HFIC-V1.1",
                "isolated_context_attestation": "NEW_CONTEXT_REQUIRED",
                "critic_terminal": "KILL_PREPARATORY_LOOP",
                "next": "STOP",
                "authority": {
                    "git_mutation": 0,
                    "experiment_execution": 0,
                    "provider_api_rpc_wss_calls": 0,
                },
                "non_claims": ["NO_ALPHA", "FIXTURE_CRITIC"],
            }
            critic_path = Path(tmp) / "critic.json"
            critic_path.write_text(json.dumps(critic), encoding="utf-8")
            finalized = run_cli(
                "finalize",
                "--session-id",
                session_id,
                "--critic-result",
                str(critic_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(finalized.returncode, 0, finalized.stderr)
            receipt = json.loads(finalized.stdout)
            self.assertEqual(receipt["session_state"], "SYNTHESIS_COMPLETE")
            self.assertEqual(receipt["critic_terminal"], "KILL_PREPARATORY_LOOP")
            selected = receipt["selected_candidate_id"]
            self.assertEqual(
                receipt["decisions"][selected]["decision_kind"],
                "REJECT",
            )
            for candidate_id, decision in receipt["decisions"].items():
                if candidate_id != selected:
                    self.assertEqual(decision["decision_kind"], "PAUSE")

            shown = run_cli(
                "show-session",
                "--session-id",
                session_id,
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(shown.returncode, 0, shown.stderr)
            shown_payload = json.loads(shown.stdout)
            self.assertTrue(shown_payload["candidates_retrievable"])
            self.assertTrue(shown_payload["artifacts_retrievable"])

            prior = run_cli(
                "prior",
                "--query",
                "ROUTE_FRAGMENTATION",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(prior.returncode, 0, prior.stderr)
            self.assertGreaterEqual(json.loads(prior.stdout)["match_count"], 1)

            replay = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(replay.returncode, 0, replay.stderr)
            replay_payload = json.loads(replay.stdout)
            self.assertEqual(replay_payload["action"], "RETURN_EXISTING_SESSION")
            self.assertEqual(replay_payload["session_id"], session_id)

            proved = run_cli(
                "prove-runtime",
                "--session-id",
                session_id,
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(proved.returncode, 0, proved.stderr)
            proof = json.loads(proved.stdout)
            self.assertEqual(proof["provider_calls_actual"], 0)
            self.assertTrue(proof["git_composite_unchanged"])

            exported = export_snapshot(data_root, snapshot_root)
            restore_snapshot(exported.snapshot_root, restore_root)
            restored_store = ResearchStore(restore_root)
            restored_store.rebuild_projection()
            restored = run_cli(
                "show-session",
                "--session-id",
                session_id,
                "--format",
                "json",
                data_root=restore_root,
            )
            self.assertEqual(restored.returncode, 0, restored.stderr)
            restored_payload = json.loads(restored.stdout)
            self.assertEqual(restored_payload["session_state"], "SYNTHESIS_COMPLETE")
            self.assertEqual(restored_payload["critic_terminal"], "KILL_PREPARATORY_LOOP")
            self.assertEqual(restored_payload["next"], "STOP")
            self.assertTrue(restored_payload["candidates_retrievable"])
            self.assertTrue(restored_payload["artifacts_retrievable"])
            self.assertIn("critic_input_packet", restored_payload)

        git_after = repository_git_snapshot(ROOT)
        self.assertTrue(git_before.unchanged(git_after))
