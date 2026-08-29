from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

CLI = ROOT / "scripts" / "hypothesis_forge.py"


def critic_result_from_packet_only(
    packet: dict,
    terminal: str = "KILL_MECHANISM",
) -> dict:
    from solana_alpha_lab.factory.hfic_identity import candidate_identity
    from solana_alpha_lab.factory.hfic_session import _canonical_json_hash

    selected = packet["selected_candidate"]
    identity = candidate_identity(
        {
            "claim": selected["claim"],
            "mechanism": selected["mechanism"],
            "actor_counterparty": selected["actor_counterparty"],
            "population": selected["population"],
            "decision_timestamp": selected["decision_timestamp"],
            "primary_x_family": selected["primary_x"],
            "primary_y": selected["primary_y"],
            "horizon_notional": selected["horizon_notional"],
            "negative_control": selected["negative_control"],
            "cheapest_falsifier": selected["cheapest_falsifier"],
        }
    )
    return {
        "schema": "smial.hypothesis-critic-result",
        "schema_version": "1.1",
        "session_id": packet["session_id"],
        "critic_input_packet_sha256": _canonical_json_hash(packet),
        "selected_candidate_id": selected["candidate_id"],
        "selected_definition_sha256": identity.full_sha256,
        "critic_prompt_version": "HFIC-V1.1",
        "isolated_context_attestation": "NEW_CONTEXT_REQUIRED",
        "critic_terminal": terminal,
        "next": "STOP",
        "authority": {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
        },
        "non_claims": ["NO_ALPHA", "PACKET_ONLY_CRITIC"],
    }


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
            "prospects",
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

    def test_preflight_accepts_multiline_owner_focus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            completed = run_cli(
                "preflight",
                "--owner-focus",
                "SMOKE_VALIDATION_ONLY:\nUse existing declarative primitives only.",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["action"], "START_NEW_SESSION")
            self.assertNotIn(str(data_root), completed.stdout)
            self.assertNotIn(str(ROOT), completed.stdout)

    def test_preflight_does_not_misclassify_url_as_windows_path(self) -> None:
        for owner_focus in (
            "Inspect https://example.invalid/research only as a textual focus.",
            "Inspect x://example.invalid/research only as a textual focus.",
            "Compare horizon D:1/2 vs D:2/3 on the existing panel.",
            "primary_x:wallet/cluster remains a textual family token.",
        ):
            with self.subTest(owner_focus=owner_focus), tempfile.TemporaryDirectory() as tmp:
                completed = run_cli(
                    "preflight",
                    "--owner-focus",
                    owner_focus,
                    "--format",
                    "json",
                    "--no-auto-commission",
                    data_root=Path(tmp) / "rdp",
                )
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertNotIn("PHYSICAL_PATH_LEAK", completed.stderr)
                self.assertEqual(
                    json.loads(completed.stdout)["terminal"],
                    "FAST_LANE_NOT_COMMISSIONABLE",
                )

    def test_preflight_rejects_raw_windows_path_before_rdp_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            completed = run_cli(
                "preflight",
                "--owner-focus",
                r"focus C:\private\path",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertNotEqual(completed.returncode, 0, completed.stdout)
            self.assertIn("PHYSICAL_PATH_LEAK", completed.stderr)
            self.assertFalse(data_root.exists())

    def test_preflight_rejects_windows_slash_and_unc_paths(self) -> None:
        for owner_focus in (
            "focus C:/private/path",
            r"focus C:relative\path",
            r"focus \\server\share\path",
            r"focus \\?\C:\private\path",
            "focus //server/share/path",
            r"focus //server\share",
            r"focus //server\share\path",
            "focus //./PhysicalDrive0",
            r"focus \Device\HarddiskVolume1",
            r"focus \rooted\path",
        ):
            with self.subTest(owner_focus=owner_focus), tempfile.TemporaryDirectory() as tmp:
                completed = run_cli(
                    "preflight",
                    "--owner-focus",
                    owner_focus,
                    "--format",
                    "json",
                    "--no-auto-commission",
                    data_root=Path(tmp) / "rdp",
                )
                self.assertNotEqual(completed.returncode, 0, completed.stdout)
                self.assertIn("PHYSICAL_PATH_LEAK", completed.stderr)

    def test_backfill_rejects_paths_before_emit_or_persist(self) -> None:
        fixture = json.loads(
            (
                ROOT / "tests/fixtures/hypothesis_forge/draft_happy_path_v1.json"
            ).read_text(encoding="utf-8")
        )
        for persist in (False, True):
            with self.subTest(persist=persist), tempfile.TemporaryDirectory() as tmp:
                packet = {
                    "phase": "LEGACY_PARTIAL",
                    "source": "OWNER_SUPPLIED_TRANSCRIPT",
                    "candidates": fixture["candidates"],
                    "owner_focus": "focus C:/private/path",
                }
                packet_path = Path(tmp) / "legacy.json"
                packet_path.write_text(json.dumps(packet), encoding="utf-8")
                data_root = Path(tmp) / "rdp"
                args = [
                    "backfill-legacy",
                    "--packet",
                    str(packet_path),
                    "--format",
                    "json",
                ]
                if persist:
                    args.append("--persist")
                completed = run_cli(*args, data_root=data_root)
                rendered = completed.stdout + completed.stderr
                self.assertNotEqual(completed.returncode, 0, rendered)
                self.assertIn("PHYSICAL_PATH_LEAK", completed.stderr)
                self.assertNotIn(packet["owner_focus"], rendered)
                self.assertFalse(data_root.exists())

    def test_persistence_commands_reject_path_input_before_rdp_open(self) -> None:
        fixture = json.loads(
            (
                ROOT / "tests/fixtures/hypothesis_forge/draft_happy_path_v1.json"
            ).read_text(encoding="utf-8")
        )
        for command in ("freeze", "finalize", "revise", "classify"):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                data_root = workspace / "rdp"
                payload_path = workspace / "payload.json"
                if command in {"freeze", "revise"}:
                    payload = dict(fixture)
                    payload["owner_focus"] = "focus C:/private/path"
                else:
                    payload = {"untrusted_value": "focus C:/private/path"}
                payload_path.write_text(json.dumps(payload), encoding="utf-8")
                if command == "freeze":
                    receipt_path = workspace / "preflight.json"
                    receipt_path.write_text("{}", encoding="utf-8")
                    args = (
                        "freeze",
                        "--draft",
                        str(payload_path),
                        "--preflight-receipt",
                        str(receipt_path),
                        "--format",
                        "json",
                    )
                elif command == "finalize":
                    args = (
                        "finalize",
                        "--session-id",
                        "HFIC-SESS-UNUSED",
                        "--critic-result",
                        str(payload_path),
                        "--format",
                        "json",
                    )
                elif command == "revise":
                    args = (
                        "revise",
                        "--session-id",
                        "HFIC-SESS-UNUSED",
                        "--draft",
                        str(payload_path),
                        "--format",
                        "json",
                    )
                else:
                    args = (
                        "classify",
                        "--session-id",
                        "HFIC-SESS-UNUSED",
                        "--experiment-spec",
                        str(payload_path),
                        "--format",
                        "json",
                    )
                completed = run_cli(*args, data_root=data_root)
                self.assertNotEqual(completed.returncode, 0, completed.stdout)
                self.assertIn("PHYSICAL_PATH_LEAK", completed.stderr)
                self.assertFalse(data_root.exists())

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

    def test_runtime_gate_is_stdlib_only_and_before_factory_imports(self) -> None:
        text = CLI.read_text(encoding="utf-8")
        gate_call = text.index("\nenforce_hfic_runtime_python()\n")
        factory_import = text.index("from solana_alpha_lab.factory")
        self.assertLess(gate_call, factory_import)
        self.assertIn('HFIC_REQUIRED_PYTHON = "3.13.14"', text)
        prefix = text[:gate_call]
        self.assertNotIn("solana_alpha_lab", prefix)
        self.assertNotIn("datetime", prefix)

    def test_runtime_gate_rejects_noncanonical_python_without_factory_import(self) -> None:
        # In-process exec of the stdlib prefix only. Do not spawn uv or persist RDP.
        text = CLI.read_text(encoding="utf-8")
        prefix, sep, remainder = text.partition("\nenforce_hfic_runtime_python()\n")
        self.assertTrue(sep)
        self.assertTrue(remainder.lstrip().startswith("ROOT = Path"))
        namespace: dict[str, object] = {"__name__": "hfic_runtime_gate_test"}
        exec(compile(prefix, str(CLI), "exec"), namespace, namespace)
        fake = type("VersionInfo", (), {"major": 3, "minor": 10, "micro": 11})()
        terminal = namespace["hfic_runtime_python_terminal"]
        enforce = namespace["enforce_hfic_runtime_python"]
        self.assertEqual(terminal(fake), "HFIC_RUNTIME_PYTHON_VERSION_INCOMPATIBLE")
        self.assertIsNone(terminal())
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as raised:
                enforce(fake)
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("HFIC_RUNTIME_PYTHON_VERSION_INCOMPATIBLE", stderr.getvalue())


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

    def test_preflight_freeze_packet_only_kill_finalize(self) -> None:
        from solana_alpha_lab.factory.document_runner import repository_git_snapshot

        git_before = repository_git_snapshot(ROOT)
        happy = ROOT / "tests/fixtures/hypothesis_forge/draft_happy_path_v1.json"
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
            preflight_payload = json.loads(preflight.stdout)
            self.assertEqual(preflight_payload["action"], "START_NEW_SESSION")
            receipt_path = Path(tmp) / "preflight.json"
            receipt_path.write_text(preflight.stdout, encoding="utf-8")
            happy_bound = Path(tmp) / "draft_bound.json"
            happy_bound.write_text(
                json.dumps(bind_draft(json.loads(happy.read_text(encoding="utf-8")), preflight_payload)),
                encoding="utf-8",
            )
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
            packet = json.loads(json.dumps(frozen["critic_input_packet"]))
            outer_session = frozen["session_id"]
            self.assertEqual(packet["packet_version"], "1.1")
            self.assertEqual(packet["session_id"], outer_session)
            del frozen
            critic = critic_result_from_packet_only(packet, "KILL_MECHANISM")
            self.assertEqual(critic["session_id"], packet["session_id"])
            critic_path = Path(tmp) / "critic_packet_only.json"
            critic_path.write_text(json.dumps(critic), encoding="utf-8")
            finalized = run_cli(
                "finalize",
                "--session-id",
                str(packet["session_id"]),
                "--critic-result",
                str(critic_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(finalized.returncode, 0, finalized.stderr)
            receipt = json.loads(finalized.stdout)
            self.assertEqual(receipt["session_state"], "SYNTHESIS_COMPLETE")
            self.assertEqual(receipt["critic_terminal"], "KILL_MECHANISM")
            self.assertEqual(receipt["session_id"], outer_session)
            self.assertEqual(receipt["session_id"], packet["session_id"])
        git_after = repository_git_snapshot(ROOT)
        self.assertTrue(git_before.unchanged(git_after))
