from __future__ import annotations

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
    export_snapshot,
    restore_snapshot,
)
from solana_alpha_lab.factory.git_write_fence import RepositoryGitSnapshot  # noqa: E402
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
            proof = prove_cold_copy(
                data_root,
                exported.snapshot_root,
                run_id=run_id,
                restored_root=restored_root,
            )
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


if __name__ == "__main__":
    unittest.main()
