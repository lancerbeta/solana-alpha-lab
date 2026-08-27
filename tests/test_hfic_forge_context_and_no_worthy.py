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

from solana_alpha_lab.contracts.schema_v1 import DatasetManifest, PartitionManifest
from solana_alpha_lab.factory.early_market_panel_importer import (
    CLOSED_FAMILY,
    DATASET_MANIFEST_ID,
    FEATURE_ID,
    SAMPLE_INVALID,
    SAMPLE_VALID,
    import_early_market_panel,
)
from solana_alpha_lab.factory.hfic_preflight import (
    FORGE_CONTEXT_ARTIFACT_DIR,
    evidence_epoch_material,
    evidence_epoch_sha256,
    rank_prior_candidate_ids,
    verify_forge_context_packet,
)
from solana_alpha_lab.storage.manifests import canonical_manifest_bytes
from tests.test_early_market_panel_importer import write_temp_capture
from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent, ResearchStore

CLI = ROOT / "scripts/hypothesis_forge.py"
FIXTURE = ROOT / "tests/fixtures/early_market_panel/temp_capture_v1"
NO_WORTHY = ROOT / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1.json"
HAPPY = ROOT / "tests/fixtures/hypothesis_forge/draft_happy_path_v1.json"
SECOND_DATASET_MANIFEST_ID = "DATASET-MANIFEST-SYNTHETIC-CONTEXT-002"
SECOND_CAPABILITY_ID = "CAP-FIXTURE-GIT-RECEIPT-WRITER-001"


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


def _hyp_event(store_root: Path, hyp_id: str, claim: str, created: datetime) -> ResearchEvent:
    payload = {
        "hypothesis_version_id": hyp_id,
        "claim": claim,
        "statement": claim,
        "mechanism": claim,
        "primary_x_family": claim,
    }
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return ResearchEvent(
        record_id=f"REC-{hyp_id}",
        record_kind=RecordKind.HYPOTHESIS_VERSION,
        entity_id=hyp_id,
        hypothesis_version_id=hyp_id,
        run_id=None,
        transaction_id="RESEARCH-TXN-RANK-001",
        effective_at=created,
        first_reliable_available_at=created,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        producer_git_sha="0" * 40,
        created_at=created,
    )


class RankedPriorTests(unittest.TestCase):
    def test_relevance_rank_not_first_five_iteration_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            now = datetime(2026, 8, 25, tzinfo=UTC)
            store.append(
                [
                    _hyp_event(Path(tmp), "HYP-AAA-UNRELATED-001", "holder concentration", now),
                    _hyp_event(Path(tmp), "HYP-ZZZ-UNRELATED-002", "route fragmentation", now),
                    _hyp_event(Path(tmp), "HYP-MMM-TAKER-VOLUME-001", "taker volume mix", now),
                    _hyp_event(Path(tmp), "HYP-BBB-TAKER-VOLUME-002", "taker volume mix", now),
                ],
                transaction_id="RESEARCH-TXN-RANK-001",
            )
            ranked, dropped = rank_prior_candidate_ids(
                store,
                owner_focus="AUTO",
                feature_hints=[FEATURE_ID],
            )
            self.assertGreaterEqual(len(ranked), 2)
            self.assertEqual(ranked[0], "HYP-BBB-TAKER-VOLUME-002")
            self.assertEqual(ranked[1], "HYP-MMM-TAKER-VOLUME-001")
            self.assertNotEqual(ranked[:2], ["HYP-AAA-UNRELATED-001", "HYP-ZZZ-UNRELATED-002"])
            self.assertEqual(dropped, 0)


class TempBindAndContextE2ETests(unittest.TestCase):
    def test_import_epoch_preflight_context_no_worthy_and_fail_closed(self) -> None:
        from solana_alpha_lab.factory.document_runner import repository_git_snapshot
        from solana_alpha_lab.factory.hfic_session import evidence_epoch_sha256

        git_before = repository_git_snapshot(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            preflight_before = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight_before.returncode, 0, preflight_before.stderr)
            before = json.loads(preflight_before.stdout)
            epoch_before = before["evidence_epoch_sha256"]
            self.assertEqual(before["commissioning"]["provider_calls_actual"], 0)
            self.assertNotIn(DATASET_MANIFEST_ID, before["forge_context_packet"]["dataset_manifest_ids"])

            first = import_early_market_panel(
                source_root=FIXTURE,
                data_root=data_root,
                source_receipt_path=FIXTURE / "source_receipt.json",
            )
            self.assertEqual(first["status"], "IMPORTED")
            epoch_after = evidence_epoch_sha256(
                evidence_epoch_material(ROOT, data_root)
            )
            self.assertNotEqual(epoch_after, epoch_before)
            second = import_early_market_panel(
                source_root=FIXTURE,
                data_root=data_root,
                source_receipt_path=FIXTURE / "source_receipt.json",
            )
            self.assertEqual(second["status"], "IDEMPOTENT_REUSE")
            self.assertEqual(
                evidence_epoch_sha256(evidence_epoch_material(ROOT, data_root)),
                epoch_after,
            )
            self.assertEqual(second["row_count"], first["row_count"])

            preflight_after = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight_after.returncode, 0, preflight_after.stderr)
            after = json.loads(preflight_after.stdout)
            packet = after["forge_context_packet"]
            self.assertIn(DATASET_MANIFEST_ID, packet["dataset_manifest_ids"])
            self.assertIn(first["dataset_fingerprint"], packet["dataset_fingerprints"])
            self.assertIn(
                "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
                packet["capability_ids"],
            )
            self.assertNotIn(
                "CAP-OFFLINE-HASH-VERIFIED-CAPTURE-IMPORT-001",
                packet["capability_ids"],
            )
            hints = packet["feature_hints"]
            panel_hints = [item for item in hints if item.get("feature_id") == FEATURE_ID]
            self.assertTrue(panel_hints)
            self.assertFalse(any(item.get("usable") for item in panel_hints))
            self.assertTrue(
                any(item.get("dataset_terminal") == SAMPLE_INVALID for item in panel_hints)
            )
            self.assertIn(SECOND_CAPABILITY_ID, packet["capability_ids"])
            self.assertTrue(
                any(item.get("terminal") == CLOSED_FAMILY for item in packet["closed_family_ledger"])
            )
            self.assertGreaterEqual(len(packet["closed_family_ledger"]), 2)
            self.assertIn("truncation_receipt", packet)
            ranked = packet.get("ranked_prior_candidate_ids") or []
            self.assertIsInstance(ranked, list)
            self.assertEqual(ranked, sorted(ranked))
            digest = after["forge_context_packet_sha256"]
            loaded = verify_forge_context_packet(data_root, digest)
            self.assertEqual(loaded["dataset_manifest_ids"], packet["dataset_manifest_ids"])
            self.assertEqual(after["commissioning"]["provider_calls_actual"], 0)
            self.assertNotIn("tau_b", preflight_after.stdout)
            self.assertNotIn("/hypothesis-forge", preflight_after.stdout)

            receipt_path = Path(tmp) / "preflight.json"
            receipt_path.write_text(preflight_after.stdout, encoding="utf-8")
            draft_path = Path(tmp) / "no_worthy.json"
            draft_path.write_text(
                json.dumps(bind_draft(json.loads(NO_WORTHY.read_text(encoding="utf-8")), after)),
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
            self.assertEqual(frozen["session_state"], "SYNTHESIS_COMPLETE")
            self.assertIsNone(frozen["selected_candidate_id"])
            self.assertIsNone(frozen.get("critic_input_packet"))
            self.assertEqual(frozen["critic_terminal"], "NO_WORTHY_HYPOTHESIS")
            self.assertFalse(frozen["critic_launched"])
            self.assertEqual(frozen["next"], "WAIT_FOR_NEW_EVIDENCE")
            self.assertEqual(frozen["next_action_status"], "RECORDED")
            self.assertEqual(frozen["forge_context_packet_sha256"], digest)

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
            self.assertEqual(replayed["action"], "RETURN_EXISTING_SESSION")
            self.assertEqual(replayed["session_id"], frozen["session_id"])
            self.assertEqual(replayed.get("critic_terminal"), "NO_WORTHY_HYPOTHESIS")
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
            self.assertEqual(proof["runtime_no_git"], "PROVEN")
            self.assertEqual(proof["provider_calls_actual"], 0)
            self.assertTrue(proof["artifacts_retrievable"])

            corrupt = Path(tmp) / "corrupt"
            shutil.copytree(FIXTURE, corrupt)
            body = corrupt / "DISCOVERY_SEARCH_R0.body"
            raw = body.read_bytes()
            body.write_bytes(raw[:-1] + bytes([raw[-1] ^ 0xFF]))
            from solana_alpha_lab.factory.early_market_panel_importer import (
                EarlyMarketPanelImportError,
            )

            with self.assertRaises(EarlyMarketPanelImportError):
                import_early_market_panel(
                    source_root=corrupt,
                    data_root=Path(tmp) / "other",
                    source_receipt_path=corrupt / "source_receipt.json",
                )

        git_after = repository_git_snapshot(ROOT)
        self.assertTrue(git_before.unchanged(git_after))

    def test_ten_eligible_rows_advertise_usable_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            write_temp_capture(source, eligible=10)
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            imported = import_early_market_panel(
                source_root=source,
                data_root=data_root,
                source_receipt_path=source / "source_receipt.json",
            )
            self.assertEqual(imported["dataset_terminal"], SAMPLE_VALID)
            self.assertTrue(imported["feature_usable"])
            preflight = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            packet = json.loads(preflight.stdout)["forge_context_packet"]
            hints = [
                item
                for item in packet["feature_hints"]
                if item.get("feature_id") == FEATURE_ID
            ]
            self.assertTrue(hints)
            self.assertTrue(any(item.get("usable") for item in hints))

    def test_second_registered_dataset_and_capability_appear_without_preflight_edit(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            commissioned = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(commissioned.returncode, 0, commissioned.stderr)
            _publish_second_synthetic_dataset(data_root)
            after = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(after.returncode, 0, after.stderr)
            packet = json.loads(after.stdout)["forge_context_packet"]
            self.assertIn(SECOND_DATASET_MANIFEST_ID, packet["dataset_manifest_ids"])
            self.assertIn(SECOND_CAPABILITY_ID, packet["capability_ids"])
            self.assertTrue(
                any(
                    item.get("capability_id") == SECOND_CAPABILITY_ID
                    and "effect_class" in item
                    and "supports_pit" in item
                    and "max_provider_calls" in item
                    for item in packet["capability_entries"]
                )
            )

    def test_deleted_context_artifact_breaks_prove_runtime_no_worthy(self) -> None:
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
            digest = receipt["forge_context_packet_sha256"]
            receipt_path = Path(tmp) / "preflight.json"
            receipt_path.write_text(preflight.stdout, encoding="utf-8")
            draft_path = Path(tmp) / "no_worthy.json"
            draft_path.write_text(
                json.dumps(bind_draft(json.loads(NO_WORTHY.read_text(encoding="utf-8")), receipt)),
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
            blob = data_root / FORGE_CONTEXT_ARTIFACT_DIR / f"{digest}.json"
            self.assertTrue(blob.is_file())
            blob.unlink()
            proved = run_cli(
                "prove-runtime",
                "--session-id",
                frozen["session_id"],
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertNotEqual(proved.returncode, 0)
            self.assertIn("FORGE_CONTEXT", proved.stderr + proved.stdout)

    def test_selected_path_resolves_context_and_fails_closed_on_corrupt_blob(self) -> None:
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
            digest = receipt["forge_context_packet_sha256"]
            receipt_path = Path(tmp) / "preflight.json"
            receipt_path.write_text(preflight.stdout, encoding="utf-8")
            draft_path = Path(tmp) / "selected.json"
            draft_path.write_text(
                json.dumps(bind_draft(json.loads(HAPPY.read_text(encoding="utf-8")), receipt)),
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
            self.assertIsNotNone(frozen.get("selected_candidate_id"))
            shown = run_cli(
                "show-session",
                "--session-id",
                frozen["session_id"],
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(shown.returncode, 0, shown.stderr)
            blob = data_root / FORGE_CONTEXT_ARTIFACT_DIR / f"{digest}.json"
            blob.write_bytes(blob.read_bytes() + b" ")
            broken = run_cli(
                "show-session",
                "--session-id",
                frozen["session_id"],
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertNotEqual(broken.returncode, 0)
            self.assertIn("FORGE_CONTEXT", broken.stderr + broken.stdout)


def _publish_second_synthetic_dataset(data_root: Path) -> None:
    created = datetime(2026, 8, 25, tzinfo=UTC)
    parquet_path = (
        data_root
        / "datasets"
        / "partitions"
        / "date=2026-08-25"
        / "PARTITION-SYNTHETIC-CONTEXT-002.parquet"
    )
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    from solana_alpha_lab.factory.commissioning_fixture import _deterministic_parquet_bytes

    parquet_bytes = _deterministic_parquet_bytes()
    parquet_path.write_bytes(parquet_bytes)
    file_sha = hashlib.sha256(parquet_bytes).hexdigest()
    partition = PartitionManifest(
        partition_manifest_id="PARTITION-MANIFEST-SYNTHETIC-CONTEXT-002",
        dataset_manifest_id=SECOND_DATASET_MANIFEST_ID,
        partition_id="PARTITION-SYNTHETIC-CONTEXT-002",
        logical_location=(
            "datasets/partitions/date=2026-08-25/"
            "PARTITION-SYNTHETIC-CONTEXT-002.parquet"
        ),
        file_sha256=file_sha,
        content_sha256=file_sha,
        row_count=3,
        min_event_time=created,
        max_event_time=created,
        min_available_to_strategy_at=created,
        max_available_to_strategy_at=created,
        first_reliable_available_at=created,
        created_at=created,
    )
    dataset = DatasetManifest(
        dataset_manifest_id=SECOND_DATASET_MANIFEST_ID,
        dataset_id="DATASET-SYNTHETIC-CONTEXT-002",
        dataset_version="1.0",
        schema_id="SCHEMA-SYNTHETIC-CONTEXT-002",
        schema_sha256="ab" * 32,
        dataset_fingerprint="cd" * 32,
        generation_task_id="HFIC_NEXT_EVIDENCE_BIND_AND_CONTEXT_V1",
        generation_run_id="RUN-SYNTHETIC-CONTEXT-002",
        validation_receipt_sha256="ef" * 32,
        first_reliable_available_at=created,
        created_at=created,
        content_sha256="aa" * 32,
    )
    part_path = (
        data_root
        / "datasets"
        / "manifests"
        / "partitions"
        / "PARTITION-MANIFEST-SYNTHETIC-CONTEXT-002.json"
    )
    part_path.parent.mkdir(parents=True, exist_ok=True)
    part_path.write_bytes(canonical_manifest_bytes(partition))
    manifest_path = (
        data_root / "datasets" / "manifests" / f"{SECOND_DATASET_MANIFEST_ID}.json"
    )
    manifest_path.write_bytes(canonical_manifest_bytes(dataset))


if __name__ == "__main__":
    unittest.main()
