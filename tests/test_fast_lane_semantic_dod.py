from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.commissioning_fixture import (  # noqa: E402
    publish_commissioning_dataset,
)
from solana_alpha_lab.factory.document_runner import (  # noqa: E402
    DocumentRunner,
    RunContext,
    repository_git_snapshot,
)
from solana_alpha_lab.factory.fast_lane_cold_copy import (  # noqa: E402
    load_run_result_artifact,
    prove_cold_copy,
)
from solana_alpha_lab.factory.fast_lane_snapshot import (  # noqa: E402
    SnapshotError,
    _is_link_destination,
    export_snapshot,
    restore_snapshot,
)
from solana_alpha_lab.factory.git_write_fence import (  # noqa: E402
    GitFenceError,
    RepositoryGitSnapshot,
    repository_git_snapshot as fence_snapshot,
)
from solana_alpha_lab.factory.lane_classifier import classify_lane  # noqa: E402
from solana_alpha_lab.factory.operational_store import OperationalStore  # noqa: E402
from solana_alpha_lab.factory.research_store import RecordKind, ResearchStore  # noqa: E402
from solana_alpha_lab.factory.run_passport import experiment_spec_sha256  # noqa: E402
from tests.test_fast_lane_cli import (  # noqa: E402
    CLI,
    HYPOTHESIS_DEFINITION_SHA256,
    offline_submission_packet,
    run_cli,
)


class FastLaneSemanticDoDTests(unittest.TestCase):
    def test_git_snapshot_tracks_head_and_refs_not_only_porcelain(self) -> None:
        snapshot = repository_git_snapshot(ROOT)
        self.assertEqual(len(snapshot.head_sha), 40)
        self.assertTrue(snapshot.symbolic_ref)
        self.assertRegex(snapshot.porcelain_sha256, r"^[0-9a-f]{64}$")
        self.assertRegex(snapshot.index_worktree_sha256, r"^[0-9a-f]{64}$")
        self.assertRegex(snapshot.refs_digest_sha256, r"^[0-9a-f]{64}$")
        self.assertRegex(snapshot.composite_sha256, r"^[0-9a-f]{64}$")

    def test_commissioning_run_persists_metric_evidence_and_retrievable_result(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            publish_commissioning_dataset(data_root)
            packet_path = data_root / "packet.json"
            packet_path.write_text(
                json.dumps(offline_submission_packet()),
                encoding="utf-8",
            )
            completed = run_cli(
                "commission-offline",
                "--packet",
                str(packet_path),
                data_root=data_root,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            run_id = payload["run_id_or_null"]
            self.assertIsInstance(run_id, str)

            store = ResearchStore(data_root)
            all_kinds = {record.record_kind for record in store.iter_committed_records()}
            run_kinds = {
                record.record_kind
                for record in store.iter_committed_records()
                if record.run_id == run_id
            }
            self.assertIn(RecordKind.HYPOTHESIS_VERSION, all_kinds)
            self.assertIn(RecordKind.RUN_STARTED, run_kinds)
            self.assertIn(RecordKind.RUN_COMPLETED, run_kinds)
            self.assertIn(RecordKind.EXPERIMENT_METRIC, run_kinds)
            self.assertIn(RecordKind.EVIDENCE_BINDING, run_kinds)
            self.assertIn(RecordKind.RESEARCH_ARTIFACT, run_kinds)

            passport = store.find_completed_run_by_id(run_id)
            self.assertIsNotNone(passport)
            assert passport is not None
            passport_payload = dict(passport.payload)
            self.assertEqual(
                passport_payload["experiment_spec_sha256"],
                experiment_spec_sha256(
                    offline_submission_packet()["experiment_spec"]  # type: ignore[arg-type]
                ),
            )
            self.assertEqual(len(passport_payload["runner_git_sha"]), 40)
            self.assertTrue(passport_payload["dataset_fingerprints"])
            self.assertEqual(
                passport_payload["query_recipe_binding"]["status"],
                "NOT_APPLICABLE",
            )

            artifact = load_run_result_artifact(data_root, passport_payload)
            self.assertIn("capability_result", artifact)
            self.assertIn("terminal", artifact["capability_result"])

    def test_replay_verifies_independent_result_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            publish_commissioning_dataset(data_root)
            packet_path = data_root / "packet.json"
            packet_path.write_text(
                json.dumps(offline_submission_packet()),
                encoding="utf-8",
            )
            commission = run_cli(
                "commission-offline",
                "--packet",
                str(packet_path),
                data_root=data_root,
            )
            self.assertEqual(commission.returncode, 0, commission.stderr)
            run_id = json.loads(commission.stdout)["run_id_or_null"]
            replay = run_cli("replay", "--run-id", run_id, data_root=data_root)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            payload = json.loads(replay.stdout)
            self.assertTrue(payload["result_integrity_matches"])
            self.assertEqual(
                payload["result_digest_sha256"],
                payload["recomputed_result_digest_sha256"],
            )

    def test_snapshot_export_restore_between_local_temp_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_root = Path(tmp) / "source"
            export_parent = Path(tmp) / "exports"
            restored_root = Path(tmp) / "restored"
            source_root.mkdir()
            publish_commissioning_dataset(source_root)
            packet_path = source_root / "packet.json"
            packet_path.write_text(
                json.dumps(offline_submission_packet()),
                encoding="utf-8",
            )
            commission = run_cli(
                "commission-offline",
                "--packet",
                str(packet_path),
                data_root=source_root,
            )
            self.assertEqual(commission.returncode, 0, commission.stderr)
            run_id = json.loads(commission.stdout)["run_id_or_null"]

            exported = export_snapshot(source_root, export_parent)
            self.assertTrue(exported.snapshot_root.is_dir())
            self.assertRegex(exported.snapshot_id, r"^SNAPSHOT-")
            self.assertRegex(exported.inventory_sha256, r"^[0-9a-f]{64}$")

            restored = restore_snapshot(exported.snapshot_root, restored_root)
            self.assertEqual(restored.snapshot_id, exported.snapshot_id)
            self.assertEqual(
                restored.committed_inventory_sha256,
                exported.committed_inventory_sha256,
            )
            self.assertFalse((restored_root / "projections").exists())
            self.assertFalse((restored_root / "ops").exists())
            self.assertFalse((restored_root / "locks").exists())

            restored_store = ResearchStore(restored_root)
            restored_store.rebuild_projection()
            source_store = ResearchStore(source_root)
            self.assertEqual(
                source_store.diagnostics().committed_inventory_sha256,
                restored_store.diagnostics().committed_inventory_sha256,
            )

    def test_cold_copy_proof_matches_independent_restored_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            publish_commissioning_dataset(data_root)
            packet_path = data_root / "packet.json"
            packet_path.write_text(
                json.dumps(offline_submission_packet()),
                encoding="utf-8",
            )
            commission = run_cli(
                "commission-offline",
                "--packet",
                str(packet_path),
                data_root=data_root,
            )
            self.assertEqual(commission.returncode, 0, commission.stderr)
            run_id = json.loads(commission.stdout)["run_id_or_null"]
            backup_root = data_root / "exports"
            restored_root = data_root / "restored"
            exported = export_snapshot(data_root, backup_root)
            restore_snapshot(exported.snapshot_root, restored_root)
            sentinel = restored_root / "CALLER_SENTINEL"
            sentinel.write_text("do-not-delete", encoding="utf-8")
            proof = prove_cold_copy(
                data_root,
                exported.snapshot_root,
                run_id=run_id,
                restored_root=restored_root,
            )
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "do-not-delete")
            self.assertEqual(
                proof.source_inventory_sha256,
                proof.restored_inventory_sha256,
            )
            self.assertEqual(
                proof.source_projection_digest_sha256,
                proof.restored_projection_digest_sha256,
            )
            self.assertEqual(
                proof.source_result_payload_sha256,
                proof.restored_result_payload_sha256,
            )

    def test_git_mutation_detected_when_head_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            publish_commissioning_dataset(data_root)
            packet = offline_submission_packet()
            decision = classify_lane(
                packet,
                root=ROOT,
                data_root=data_root,
                as_of=__import__("datetime").datetime.fromisoformat(
                    "2026-08-25T00:00:00+00:00"
                ),
            )
            ops = OperationalStore(data_root / "ops" / "operational_state.sqlite")
            runner = DocumentRunner(root=ROOT, store=ops)
            before = repository_git_snapshot(ROOT)
            after = RepositoryGitSnapshot(
                head_sha="f" * 40,
                symbolic_ref=before.symbolic_ref,
                porcelain_sha256=before.porcelain_sha256,
                index_worktree_sha256="a" * 64,
                refs_digest_sha256=before.refs_digest_sha256,
                composite_sha256="b" * 64,
            )
            try:
                with mock.patch(
                    "solana_alpha_lab.factory.document_runner.repository_git_snapshot",
                    side_effect=[before, after],
                ), mock.patch(
                    "solana_alpha_lab.factory.document_runner.execute_capability",
                    return_value={
                        "status": "COMPLETE",
                        "terminal": "INCONCLUSIVE",
                        "accepted_terminal": "INCONCLUSIVE",
                        "provider_api_rpc_wss_calls": 0,
                    },
                ):
                    result = runner.start_document(
                        packet["experiment_spec"],  # type: ignore[arg-type]
                        spec_sha256=experiment_spec_sha256(
                            packet["experiment_spec"]  # type: ignore[arg-type]
                        ),
                        run_context=RunContext(
                            data_root=data_root,
                            hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                            lane_decision=decision,
                        ),
                    )
            finally:
                ops.close()
            self.assertEqual(result["reason_codes"], ["GIT_MUTATION_DETECTED"])


def _commission_and_export(tmp: Path) -> tuple[Path, Path, str]:
    source_root = tmp / "source"
    export_parent = tmp / "exports"
    source_root.mkdir()
    publish_commissioning_dataset(source_root)
    packet_path = source_root / "packet.json"
    packet_path.write_text(json.dumps(offline_submission_packet()), encoding="utf-8")
    commission = run_cli(
        "commission-offline",
        "--packet",
        str(packet_path),
        data_root=source_root,
    )
    if commission.returncode != 0:
        raise AssertionError(commission.stderr)
    run_id = json.loads(commission.stdout)["run_id_or_null"]
    exported = export_snapshot(source_root, export_parent)
    return source_root, exported.snapshot_root, run_id


def _listing_digest(path: Path) -> dict[str, str]:
    digest: dict[str, str] = {}
    if not path.exists() or path.is_symlink():
        return digest
    for child in sorted(path.rglob("*")):
        if child.is_file() and not child.is_symlink():
            digest[child.relative_to(path).as_posix()] = hashlib.sha256(
                child.read_bytes()
            ).hexdigest()
    return digest


def _safety_receipt(
    *,
    case: str,
    deny_code: str,
    destination: Path,
    existed_before: bool,
    listing_before: dict[str, str],
    listing_after: dict[str, str],
    symlink_before: bool,
) -> dict[str, object]:
    receipt = {
        "case": case,
        "deny_code": deny_code,
        "destination_existed_before": existed_before,
        "destination_symlink_before": symlink_before,
        "destination_exists_after": destination.exists() or destination.is_symlink(),
        "destination_listing_unchanged": listing_before == listing_after,
        "no_partial_publish": existed_before or not destination.exists(),
        "provider_calls": 0,
        "two_rung": "NOT_STARTED",
    }
    return receipt


class FastLaneRestoreSafetyTests(unittest.TestCase):
    def test_corrupted_snapshot_leaves_existing_destination_sentinel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, snapshot_root, _ = _commission_and_export(tmp_path)
            object_file = next(
                path
                for path in (snapshot_root / "objects").rglob("*")
                if path.is_file()
            )
            object_file.write_bytes(b"corrupted-object")
            destination = tmp_path / "existing-dest"
            destination.mkdir()
            sentinel = destination / "SENTINEL"
            sentinel.write_text("keep", encoding="utf-8")
            listing_before = _listing_digest(destination)
            with self.assertRaises(SnapshotError) as ctx:
                restore_snapshot(snapshot_root, destination)
            self.assertEqual(str(ctx.exception), "SNAPSHOT_OBJECT_HASH_MISMATCH")
            listing_after = _listing_digest(destination)
            receipt = _safety_receipt(
                case="corrupted_snapshot",
                deny_code=str(ctx.exception),
                destination=destination,
                existed_before=True,
                listing_before=listing_before,
                listing_after=listing_after,
                symlink_before=False,
            )
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
            self.assertTrue(receipt["destination_listing_unchanged"])
            self.assertTrue(receipt["no_partial_publish"])

    def test_nonempty_destination_is_denied_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, snapshot_root, _ = _commission_and_export(tmp_path)
            destination = tmp_path / "occupied"
            destination.mkdir()
            keep = destination / "keep.json"
            keep.write_text('{"keep":true}', encoding="utf-8")
            listing_before = _listing_digest(destination)
            with self.assertRaises(SnapshotError) as ctx:
                restore_snapshot(snapshot_root, destination)
            self.assertEqual(str(ctx.exception), "DESTINATION_EXISTS")
            listing_after = _listing_digest(destination)
            receipt = _safety_receipt(
                case="nonempty_destination",
                deny_code=str(ctx.exception),
                destination=destination,
                existed_before=True,
                listing_before=listing_before,
                listing_after=listing_after,
                symlink_before=False,
            )
            self.assertEqual(keep.read_text(encoding="utf-8"), '{"keep":true}')
            self.assertTrue(receipt["destination_listing_unchanged"])

    def test_source_destination_overlap_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, snapshot_root, _ = _commission_and_export(tmp_path)
            nested = snapshot_root / "nested-dest"
            with self.assertRaises(SnapshotError) as ctx:
                restore_snapshot(snapshot_root, nested)
            self.assertEqual(str(ctx.exception), "SNAPSHOT_DESTINATION_OVERLAP")
            receipt = _safety_receipt(
                case="source_destination_overlap",
                deny_code=str(ctx.exception),
                destination=nested,
                existed_before=False,
                listing_before={},
                listing_after=_listing_digest(nested),
                symlink_before=False,
            )
            self.assertFalse(nested.exists())
            self.assertTrue(receipt["no_partial_publish"])

    def test_symlink_destination_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, snapshot_root, _ = _commission_and_export(tmp_path)
            real = tmp_path / "real-target"
            real.mkdir()
            sentinel = real / "SENTINEL"
            sentinel.write_text("link-target", encoding="utf-8")
            destination = tmp_path / "dest-link"
            try:
                destination.symlink_to(real, target_is_directory=True)
            except OSError:
                completed = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(destination), str(real)],
                    capture_output=True,
                    check=False,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(destination.exists())
            listing_before = _listing_digest(real)
            with self.assertRaises(SnapshotError) as ctx:
                restore_snapshot(snapshot_root, destination)
            self.assertEqual(str(ctx.exception), "DESTINATION_SYMLINK")
            listing_after = _listing_digest(real)
            receipt = _safety_receipt(
                case="symlink_destination",
                deny_code=str(ctx.exception),
                destination=destination,
                existed_before=True,
                listing_before=listing_before,
                listing_after=listing_after,
                symlink_before=True,
            )
            self.assertTrue(_is_link_destination(destination))
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "link-target")
            self.assertTrue(receipt["destination_listing_unchanged"])

    def test_escaped_logical_path_is_denied_before_dest_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, snapshot_root, _ = _commission_and_export(tmp_path)
            inventory_path = snapshot_root / "INVENTORY.json"
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory[0]["logical_path"] = "C:/Windows/Temp/escaped"
            inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
            destination = tmp_path / "escaped-dest"
            with self.assertRaises(SnapshotError) as ctx:
                restore_snapshot(snapshot_root, destination)
            self.assertEqual(str(ctx.exception), "LOGICAL_PATH_UNSAFE")
            self.assertFalse(destination.exists())

    def test_successful_restore_into_absent_fresh_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_root, snapshot_root, _ = _commission_and_export(tmp_path)
            destination = tmp_path / "fresh-restored"
            self.assertFalse(destination.exists())
            restored = restore_snapshot(snapshot_root, destination)
            self.assertTrue(destination.is_dir())
            self.assertFalse(destination.is_symlink())
            self.assertEqual(
                ResearchStore(source_root).diagnostics().committed_inventory_sha256,
                restored.committed_inventory_sha256,
            )
            leftovers = list(destination.parent.glob(".*.restore-*"))
            self.assertEqual(leftovers, [])

    def test_publish_failure_does_not_leave_partial_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, snapshot_root, _ = _commission_and_export(tmp_path)
            destination = tmp_path / "never-published"
            with mock.patch(
                "solana_alpha_lab.factory.fast_lane_snapshot.os.replace",
                side_effect=OSError("publish-denied"),
            ):
                with self.assertRaises(SnapshotError) as ctx:
                    restore_snapshot(snapshot_root, destination)
            self.assertEqual(str(ctx.exception), "RESTORE_PUBLISH_FAILED")
            self.assertFalse(destination.exists())
            leftovers = list(destination.parent.glob(".*.restore-*"))
            receipt = _safety_receipt(
                case="failure_before_publish",
                deny_code=str(ctx.exception),
                destination=destination,
                existed_before=False,
                listing_before={},
                listing_after=_listing_digest(destination),
                symlink_before=False,
            )
            self.assertEqual(leftovers, [])
            self.assertTrue(receipt["no_partial_publish"])


class FastLaneGitFenceWorktreeTests(unittest.TestCase):
    def test_git_command_failure_is_fail_closed(self) -> None:
        failed = subprocess.CompletedProcess(
            args=["git"],
            returncode=128,
            stdout=b"",
            stderr=b"fatal",
        )
        with mock.patch(
            "solana_alpha_lab.factory.git_write_fence.subprocess.run",
            return_value=failed,
        ):
            with self.assertRaises(GitFenceError) as ctx:
                fence_snapshot(ROOT)
        self.assertIn("GIT_COMMAND_FAILED", str(ctx.exception))

    def test_linked_worktree_ref_change_updates_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            linked = Path(tmp) / "linked"
            repo.mkdir()
            subprocess.check_call(["git", "init", "-b", "main"], cwd=repo)
            subprocess.check_call(["git", "config", "user.email", "fence@test"], cwd=repo)
            subprocess.check_call(["git", "config", "user.name", "fence"], cwd=repo)
            (repo / "README.md").write_text("fence\n", encoding="utf-8")
            subprocess.check_call(["git", "add", "README.md"], cwd=repo)
            subprocess.check_call(["git", "commit", "-m", "init"], cwd=repo)
            self.assertTrue((repo / ".git").is_dir())
            clone_snapshot = fence_snapshot(repo)
            self.assertEqual(len(clone_snapshot.head_sha), 40)

            subprocess.check_call(
                ["git", "worktree", "add", str(linked), "-b", "linked-branch"],
                cwd=repo,
            )
            try:
                self.assertTrue((linked / ".git").is_file())
                before = fence_snapshot(linked)
                subprocess.check_call(
                    ["git", "update-ref", "refs/heads/probe-ref", "HEAD"],
                    cwd=linked,
                )
                after = fence_snapshot(linked)
                self.assertNotEqual(before.refs_digest_sha256, after.refs_digest_sha256)
                self.assertFalse(before.unchanged(after))
            finally:
                subprocess.check_call(
                    ["git", "worktree", "remove", "--force", str(linked)],
                    cwd=repo,
                )


if __name__ == "__main__":
    unittest.main()
