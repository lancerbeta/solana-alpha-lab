from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.contracts.schema_v1 import DatasetManifest, PartitionManifest  # noqa: E402
from solana_alpha_lab.factory.commissioning_fixture import (  # noqa: E402
    _deterministic_parquet_bytes,
)
from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    evidence_epoch_material,
    enumerate_closed_park_terminals,
)
from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    HficSessionError,
    evidence_epoch_sha256,
    freeze_draft,
)
from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent, ResearchStore  # noqa: E402
from solana_alpha_lab.storage.manifests import canonical_manifest_bytes  # noqa: E402
from tests.test_hfic_cli import bind_draft, critic_result_from_packet_only, run_cli  # noqa: E402

HAPPY = ROOT / "tests/fixtures/hypothesis_forge/draft_happy_path_v1.json"
TAKER_FAMILY = "CLOSE_EARLY_TAKER_VOLUME_MIX_FAMILY"
LATE_FAMILY = "CLOSE_ZZZ_LATE_ALPHABET_FAMILY"
TAKER_MANIFEST_ID = "DATASET-MANIFEST-TAKER-MIX-CLOSURE-FIXTURE-001"
ARBITRARY_MANIFEST_ID = "DATASET-MANIFEST-ARBITRARY-LABEL-FIXTURE-001"
NEW_EVIDENCE_MANIFEST_ID = "DATASET-MANIFEST-EPOCH-ADVANCE-FIXTURE-001"
LATE_MANIFEST_ID = "DATASET-MANIFEST-LATE-ALPHABET-CLOSURE-001"
UNPUBLISHED_MANIFEST_ID = "DATASET-MANIFEST-UNPUBLISHED-CLOSURE-001"


def _publish_labeled_dataset(
    data_root: Path,
    *,
    manifest_id: str,
    fingerprint: str,
    labels: dict[str, object],
    decision: dict[str, object] | None = None,
) -> None:
    created = datetime(2026, 8, 28, tzinfo=UTC)
    parquet_bytes = _deterministic_parquet_bytes()
    file_sha = hashlib.sha256(parquet_bytes).hexdigest()
    partition_id = f"PARTITION-{manifest_id.removeprefix('DATASET-MANIFEST-')}"
    logical_location = f"datasets/partitions/date=2026-08-28/{partition_id}.parquet"
    parquet_path = data_root / logical_location
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    parquet_path.write_bytes(parquet_bytes)
    partition = PartitionManifest(
        partition_manifest_id=f"PARTITION-MANIFEST-{manifest_id.removeprefix('DATASET-MANIFEST-')}",
        dataset_manifest_id=manifest_id,
        partition_id=partition_id,
        logical_location=logical_location,
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
        dataset_manifest_id=manifest_id,
        dataset_id=f"DATASET-{manifest_id.removeprefix('DATASET-MANIFEST-')}",
        dataset_version="1.0",
        schema_id=f"SCHEMA-{manifest_id.removeprefix('DATASET-MANIFEST-')}",
        schema_sha256="ab" * 32,
        dataset_fingerprint=fingerprint,
        generation_task_id="HFIC_EPISTEMIC_MEMORY_SEMANTICS_V1",
        generation_run_id=f"RUN-{manifest_id.removeprefix('DATASET-MANIFEST-')}",
        validation_receipt_sha256="ef" * 32,
        first_reliable_available_at=created,
        created_at=created,
        content_sha256="aa" * 32,
    )
    manifests = data_root / "datasets" / "manifests"
    part_dir = manifests / "partitions"
    part_dir.mkdir(parents=True, exist_ok=True)
    (part_dir / f"{partition.partition_manifest_id}.json").write_bytes(
        canonical_manifest_bytes(partition)
    )
    (manifests / f"{manifest_id}.json").write_bytes(canonical_manifest_bytes(dataset))
    (manifests / f"{manifest_id}.labels.json").write_text(
        json.dumps(labels, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (manifests / f"{manifest_id}.published").write_text(
        json.dumps(
            {
                "commit_point": "HFIC_EPISTEMIC_MEMORY_SEMANTICS_V1",
                "dataset_manifest_id": manifest_id,
                "dataset_fingerprint": fingerprint,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if decision is not None:
        (manifests / f"{manifest_id}.decision.json").write_text(
            json.dumps(decision, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )


def _authoritative_taker_decision(fingerprint: str) -> dict[str, object]:
    return {
        "schema": "smial.early-icp-first-hit-mix-falsifier.runtime-receipt",
        "schema_version": "1.0",
        "atom_id": "EARLY_ICP_FIRST_HIT_MIX_FALSIFIER_V1",
        "scientific_terminal": TAKER_FAMILY,
        "internal_capture_state": "CAPTURE_COMPLETE",
        "outcome_consumed": True,
        "dataset_fingerprint": fingerprint,
        "score": {"tau_b": -0.157, "rankable_h900": 13},
    }


def _append_hfic_untagged_candidate(store: ResearchStore) -> None:
    payload = {
        "hypothesis_version_id": "HFIC-CAND-SELF-MEMORY-001",
        "claim": "endogenous forge candidate must not advance epoch",
        "primary_x_family": "SELF_MEMORY",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    now = datetime(2026, 8, 30, tzinfo=UTC)
    store.append(
        [
            ResearchEvent(
                record_id="HFIC-HYP-HFIC-CAND-SELF-MEMORY-001",
                record_kind=RecordKind.HYPOTHESIS_VERSION,
                entity_id="HFIC-CAND-SELF-MEMORY-001",
                hypothesis_version_id="HFIC-CAND-SELF-MEMORY-001",
                run_id=None,
                transaction_id="RESEARCH-TXN-HFIC-SELF-MEMORY-001",
                effective_at=now,
                first_reliable_available_at=now,
                supersedes_record_id=None,
                payload_json=encoded,
                payload_sha256=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
                schema_version="1.0",
                producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
                producer_git_sha="a" * 40,
                created_at=now,
            )
        ],
        transaction_id="RESEARCH-TXN-HFIC-SELF-MEMORY-001",
    )


class EpistemicMemorySemanticsTests(unittest.TestCase):
    def test_a1_hfic_self_memory_does_not_advance_epoch(self) -> None:
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
            before = json.loads(preflight.stdout)
            epoch = before["evidence_epoch_sha256"]
            self.assertEqual(before["action"], "START_NEW_SESSION")
            receipt_path = Path(tmp) / "preflight.json"
            receipt_path.write_text(preflight.stdout, encoding="utf-8")
            draft_path = Path(tmp) / "draft.json"
            draft_path.write_text(
                json.dumps(bind_draft(json.loads(HAPPY.read_text(encoding="utf-8")), before)),
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
            packet = frozen["critic_input_packet"]
            critic_path = Path(tmp) / "critic.json"
            critic_path.write_text(
                json.dumps(critic_result_from_packet_only(packet, "KILL_MECHANISM")),
                encoding="utf-8",
            )
            finalized = run_cli(
                "finalize",
                "--session-id",
                frozen["session_id"],
                "--critic-result",
                str(critic_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(finalized.returncode, 0, finalized.stderr)
            after_epoch = evidence_epoch_sha256(evidence_epoch_material(ROOT, data_root))
            self.assertEqual(after_epoch, epoch)
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
            self.assertNotEqual(replayed["action"], "START_NEW_SESSION")

    def test_untagged_hfic_identity_still_excluded_from_epoch(self) -> None:
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
            epoch = json.loads(preflight.stdout)["evidence_epoch_sha256"]
            _append_hfic_untagged_candidate(ResearchStore(data_root))
            self.assertEqual(
                evidence_epoch_sha256(evidence_epoch_material(ROOT, data_root)),
                epoch,
            )

    def test_a2_real_external_dataset_advances_epoch(self) -> None:
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
            epoch = json.loads(preflight.stdout)["evidence_epoch_sha256"]
            _publish_labeled_dataset(
                data_root,
                manifest_id=NEW_EVIDENCE_MANIFEST_ID,
                fingerprint="22" * 32,
                labels={
                    "evidence_role": "DISCOVERY_ONLY_SECOND_LOOK",
                    "yield_eligible": 0,
                },
            )
            changed = evidence_epoch_sha256(evidence_epoch_material(ROOT, data_root))
            self.assertNotEqual(changed, epoch)

    def test_a3_typed_rdp_decision_enters_closed_family_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            fingerprint = "33" * 32
            _publish_labeled_dataset(
                data_root,
                manifest_id=TAKER_MANIFEST_ID,
                fingerprint=fingerprint,
                labels={
                    "evidence_role": "PRIMARY_FORWARD_FALSIFIER",
                    "scientific_terminal": TAKER_FAMILY,
                    "outcome_previously_consumed": True,
                },
                decision=_authoritative_taker_decision(fingerprint),
            )
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
            match = [
                item
                for item in packet["closed_family_ledger"]
                if item.get("terminal") == TAKER_FAMILY
            ]
            self.assertEqual(len(match), 1)
            self.assertEqual(
                match[0]["source_receipt"],
                f"datasets/manifests/{TAKER_MANIFEST_ID}.decision.json",
            )
            self.assertTrue(match[0]["reopen_forbidden"])
            self.assertIn(
                TAKER_FAMILY,
                [
                    item["terminal"]
                    for item in enumerate_closed_park_terminals(ROOT, data_root)
                ],
            )

    def test_a4_arbitrary_label_cannot_close_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            fingerprint = "44" * 32
            _publish_labeled_dataset(
                data_root,
                manifest_id=ARBITRARY_MANIFEST_ID,
                fingerprint=fingerprint,
                labels={
                    "evidence_role": "UNSPECIFIED",
                    "notes": "please CLOSE_EARLY_TAKER_VOLUME_MIX_FAMILY now",
                    "scientific_terminal": TAKER_FAMILY,
                },
            )
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
            self.assertFalse(
                any(
                    item.get("terminal") == TAKER_FAMILY
                    and str(item.get("source_receipt") or "").startswith("datasets/")
                    for item in packet["closed_family_ledger"]
                )
            )
            _publish_labeled_dataset(
                data_root,
                manifest_id="DATASET-MANIFEST-INCOMPLETE-DECISION-001",
                fingerprint="55" * 32,
                labels={"scientific_terminal": TAKER_FAMILY},
                decision={
                    "schema": "not-a-runtime-receipt",
                    "scientific_terminal": TAKER_FAMILY,
                    "outcome_consumed": True,
                    "dataset_fingerprint": "55" * 32,
                },
            )
            second = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            ledger = json.loads(second.stdout)["forge_context_packet"]["closed_family_ledger"]
            self.assertFalse(
                any(
                    item.get("source_receipt")
                    == "datasets/manifests/DATASET-MANIFEST-INCOMPLETE-DECISION-001.decision.json"
                    for item in ledger
                )
            )

    def test_a3_late_alphabet_rdp_survives_packet_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            fingerprint = "77" * 32
            _publish_labeled_dataset(
                data_root,
                manifest_id=LATE_MANIFEST_ID,
                fingerprint=fingerprint,
                labels={
                    "evidence_role": "PRIMARY_FORWARD_FALSIFIER",
                    "scientific_terminal": LATE_FAMILY,
                },
                decision={
                    "schema": "smial.early-icp-first-hit-mix-falsifier.runtime-receipt",
                    "schema_version": "1.0",
                    "atom_id": "EARLY_ICP_FIRST_HIT_MIX_FALSIFIER_V1",
                    "scientific_terminal": LATE_FAMILY,
                    "internal_capture_state": "CAPTURE_COMPLETE",
                    "outcome_consumed": True,
                    "dataset_fingerprint": fingerprint,
                },
            )
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
            match = [
                item
                for item in packet["closed_family_ledger"]
                if item.get("terminal") == LATE_FAMILY
            ]
            self.assertEqual(len(match), 1)
            self.assertEqual(
                match[0]["source_receipt"],
                f"datasets/manifests/{LATE_MANIFEST_ID}.decision.json",
            )
            hard_in_packet = [
                item
                for item in packet["closed_family_ledger"]
                if item.get("reopen_forbidden") is True
            ]
            self.assertLessEqual(len(hard_in_packet), 8)
            self.assertTrue(
                packet["truncation_receipt"].get("truncated")
                or len(hard_in_packet) <= 8
            )

    def test_a4_unpublished_typed_decision_cannot_close(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            fingerprint = "88" * 32
            _publish_labeled_dataset(
                data_root,
                manifest_id=UNPUBLISHED_MANIFEST_ID,
                fingerprint=fingerprint,
                labels={
                    "evidence_role": "PRIMARY_FORWARD_FALSIFIER",
                    "scientific_terminal": TAKER_FAMILY,
                },
                decision=_authoritative_taker_decision(fingerprint),
            )
            manifests = data_root / "datasets" / "manifests"
            (manifests / f"{UNPUBLISHED_MANIFEST_ID}.labels.json").unlink()
            (manifests / f"{UNPUBLISHED_MANIFEST_ID}.published").unlink()
            preflight = run_cli(
                "preflight",
                "--owner-focus",
                "AUTO",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            ledger = json.loads(preflight.stdout)["forge_context_packet"][
                "closed_family_ledger"
            ]
            self.assertFalse(
                any(
                    item.get("source_receipt")
                    == f"datasets/manifests/{UNPUBLISHED_MANIFEST_ID}.decision.json"
                    for item in ledger
                )
            )

    def test_a5_frozen_packet_preserves_closed_family_and_rejects_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            fingerprint = "66" * 32
            _publish_labeled_dataset(
                data_root,
                manifest_id=TAKER_MANIFEST_ID,
                fingerprint=fingerprint,
                labels={
                    "evidence_role": "PRIMARY_FORWARD_FALSIFIER",
                    "scientific_terminal": TAKER_FAMILY,
                },
                decision=_authoritative_taker_decision(fingerprint),
            )
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
            self.assertTrue(
                any(
                    item.get("terminal") == TAKER_FAMILY
                    for item in receipt["forge_context_packet"]["closed_family_ledger"]
                )
            )
            happy = bind_draft(json.loads(HAPPY.read_text(encoding="utf-8")), receipt)
            receipt_path = Path(tmp) / "preflight.json"
            receipt_path.write_text(preflight.stdout, encoding="utf-8")
            draft_path = Path(tmp) / "draft.json"
            draft_path.write_text(json.dumps(happy), encoding="utf-8")
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
            packet = frozen["critic_input_packet"]
            self.assertIn(f"CLOSED_FAMILY:{TAKER_FAMILY}", packet["known_unknowns"])
            reopening = dict(happy)
            reopening["candidates"] = [
                {
                    **candidate,
                    "primary_x_family": "R0_TAKER_VOLUME_MIX",
                    "claim": "Early taker volume mix predicts H900 MEU.",
                }
                if candidate.get("display_ordinal") == 1
                else candidate
                for candidate in happy["candidates"]
            ]
            with self.assertRaises(HficSessionError) as raised:
                freeze_draft(
                    reopening,
                    preflight_receipt=receipt,
                    store=ResearchStore(data_root),
                    repo_root=ROOT,
                )
            self.assertEqual(str(raised.exception), "CLOSED_FAMILY_REOPEN")


if __name__ == "__main__":
    unittest.main()
