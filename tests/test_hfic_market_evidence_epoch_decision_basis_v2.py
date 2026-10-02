"""Scientific epoch/occupancy proofs on disposable production-import worlds."""
from __future__ import annotations

import copy
import hashlib
import shutil
import json
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tests.test_live_corpus_manifest_contract_repair_v1 import _seal_week
from solana_alpha_lab.factory.live_cohort_discovery_release import import_live_cohort
from solana_alpha_lab.factory.hfic_evidence_identity import (
    EvidenceIdentityError,
    compute_market_epoch_for_data_root,
    compute_capability_epoch_for_repo,
    _v1_publication_basis,
    _validated_v1_epoch,
    market_evidence_epoch_sha256,
    resolve_scientific_admission,
    scientific_slot_sha256,
    _CAPABILITY_PROTOCOL_FILES,
    _OPERATOR_PACK,
)
from solana_alpha_lab.contracts.schema_v1 import DatasetManifest, PartitionManifest
from solana_alpha_lab.storage.manifests import (
    build_partition_manifest, build_dataset_manifest, compute_dataset_manifest_id,
    compute_dataset_fingerprint, canonical_manifest_bytes, verify_dataset_manifest,
)
from solana_alpha_lab.factory.hfic_preflight import epoch_search_budget_usage, select_forge_packet_datasets
from solana_alpha_lab.factory.hfic_session import focus_key_sha256
from tests.test_live_cohort_discovery_release_series import _snapshot_for_week


class ScientificMarketV2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.data = self.base / "rdp"
        self.data.mkdir()
        for week in range(3):
            self.import_week(week)

    def import_week(self, week):
        release, _, _ = _seal_week(self.base, week)
        return import_live_cohort(
            release_root=release, data_root=self.data,
            import_time=datetime(2026, 2, 10 + week, tzinfo=UTC),
        )

    def current(self):
        return compute_market_epoch_for_data_root(ROOT, self.data)

    def labels_path(self):
        mid = json.loads((self.data / "datasets/live_lifecycle_corpus/lineage.json").read_bytes())["current_dataset_manifest_id"]
        return self.data / "datasets/manifests" / (mid + ".labels.json")

    @staticmethod
    def session(epoch, basis):
        return {"session_id": "SCRATCH_CONSUMED_AUTO", "owner_focus": "AUTO",
                "focus_key_sha256": focus_key_sha256("AUTO"),
                "session_state": "SYNTHESIS_COMPLETE",
                "ladder_representation_id": "BASE",
                "representation_semantic_version": "HFIC-V1.2",
                "scientific_slot_sha256": scientific_slot_sha256(market_evidence_epoch_sha256=epoch, representation_id="BASE", representation_semantic_version="HFIC-V1.2", owner_focus="AUTO"),
                "market_evidence_epoch_sha256": epoch,
                "market_evidence_basis": copy.deepcopy(basis)}

    def test_imported_at_only_preserves_epoch_and_budget(self):
        epoch, basis = self.current()
        self.assertEqual(basis["basis_version"], "MARKET_EVIDENCE_BASIS_V2")
        session = self.session(epoch, basis)
        before = epoch_search_budget_usage([session], evidence_epoch=epoch, market_evidence_basis=basis)
        path = self.labels_path()
        labels = json.loads(path.read_bytes())
        labels["imported_at"] = "2099-01-01T00:00:00Z"
        path.write_text(json.dumps(labels), encoding="utf-8")
        after_epoch, after_basis = self.current()
        self.assertEqual(epoch, after_epoch)
        self.assertNotEqual(basis["datasets"], after_basis["datasets"])
        self.assertEqual(before, epoch_search_budget_usage([session], evidence_epoch=after_epoch, market_evidence_basis=after_basis))

    def test_incomplete_scientific_projection_is_not_a_new_market(self):
        _, basis = self.current()
        for mutation in ("dataset_identity", "partition_sha", "partition_bounds", "derived", "live_fence", "wrapper"):
            with self.subTest(mutation=mutation):
                broken = copy.deepcopy(basis)
                projection = broken["scientific_projection"]
                dataset = projection["datasets"][0]
                if mutation == "dataset_identity":
                    dataset["dataset_id"] = "UNBOUND_DATASET"
                elif mutation == "partition_sha":
                    dataset["partitions"][0]["content_sha256"] = "invalid"
                elif mutation == "partition_bounds":
                    del dataset["partitions"][0]["min_available_to_strategy_at"]
                elif mutation == "derived":
                    del dataset["derived"]["feature_usable"]
                elif mutation == "live_fence":
                    dataset["admissibility"]["confirmatory_reuse_forbidden"] = None
                else:
                    projection["published_at"] = "2099-01-01T00:00:00Z"
                with self.assertRaisesRegex(EvidenceIdentityError, "MARKET_EVIDENCE_BASIS_INCOMPLETE"):
                    market_evidence_epoch_sha256(broken)

    def test_decision_label_change_changes_epoch(self):
        epoch, _ = self.current()
        path = self.labels_path()
        labels = json.loads(path.read_bytes())
        labels["yield_eligible"] += 1
        path.write_text(json.dumps(labels), encoding="utf-8")
        self.assertNotEqual(epoch, self.current()[0])

    def test_incomplete_live_labels_stop_instead_of_granting_budget(self):
        from solana_alpha_lab.factory.hfic_evidence_identity import build_market_evidence_basis
        from solana_alpha_lab.factory.hfic_preflight import enumerate_rdp_datasets
        epoch, basis = self.current()
        dataset = enumerate_rdp_datasets(self.data)[0]
        current_row = next(row for row in dataset if row["dataset_manifest_id"] == basis["current_dataset_manifest_id"])
        broken_row = copy.deepcopy(current_row)
        del broken_row["labels"]["confirmatory_reuse_forbidden"]
        with self.assertRaisesRegex(EvidenceIdentityError, "MARKET_EVIDENCE_BASIS_INCOMPLETE"):
            build_market_evidence_basis(datasets=[broken_row], visible_cohort_ids=basis["visible_cohort_ids"], lineage_bindings=basis["lineage_bindings"], current_dataset_manifest_id=basis["current_dataset_manifest_id"], corpus_version=basis["corpus_version"])
        path = self.labels_path()
        original = path.read_bytes()
        for mutation in ("missing_file", "confirmatory_reuse_forbidden", "yield_eligible", "yield_missing", "feature_families", "dataset_terminal", "corpus_version", "is_current_corpus_version", "null_counter", "bool_counter", "removed_profile"):
            with self.subTest(mutation=mutation):
                path.write_bytes(original)
                labels = json.loads(original)
                if mutation == "missing_file":
                    path.unlink()
                else:
                    if mutation == "null_counter":
                        labels["yield_eligible"] = None
                    elif mutation == "bool_counter":
                        labels["yield_eligible"] = False
                    elif mutation == "removed_profile":
                        for key in ("evidence_role", "logical_dataset_id", "confirmatory_reuse_forbidden"):
                            del labels[key]
                    else:
                        del labels[mutation]
                    path.write_text(json.dumps(labels), encoding="utf-8")
                with self.assertRaisesRegex(EvidenceIdentityError, "MARKET_EVIDENCE_BASIS_INCOMPLETE"):
                    self.current()
        path.write_bytes(original)
        self.assertEqual(epoch, self.current()[0])

    def test_reservation_explicit_null_basis_is_not_restored(self):
        from solana_alpha_lab.factory.hfic_evidence_identity import _reservation_with_market_basis
        epoch, basis = self.current()
        session = self.session(epoch, basis)
        reservation = {**session, "market_evidence_basis": None}
        self.assertIs(_reservation_with_market_basis(reservation, [session]), reservation)
        self.assertIsNone(reservation["market_evidence_basis"])
        self.import_week(3)
        new_epoch, new_basis = self.current()
        with self.assertRaisesRegex(EvidenceIdentityError, "MARKET_EPOCH_CONTINUITY_UNRESOLVED"):
            epoch_search_budget_usage([session], reservations=[reservation], evidence_epoch=new_epoch, market_evidence_basis=new_basis)

    def test_continuity_stop_explains_owner_recovery(self):
        from solana_alpha_lab.factory.hfic_representation_ladder import format_forge_run_owner_readout
        body = {"no_write": True, "next_action": "OBSERVABILITY_BLOCKED", "owner_class": "OBSERVABILITY_BLOCKED", "blocking_reason_codes": ["MARKET_EPOCH_CONTINUITY_UNRESOLVED"]}
        readout = format_forge_run_owner_readout(body)
        self.assertIn("PROVE_MARKET_CONTINUITY", readout)
        self.assertIn("keep budget blocked", readout)
        self.assertIn("do not create a session", readout)
        self.assertIn("docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md", readout)

    def test_generic_optional_reuse_flag_uses_effective_consumer_default(self):
        from solana_alpha_lab.factory.hfic_evidence_identity import build_market_evidence_basis
        from solana_alpha_lab.factory.hfic_preflight import enumerate_rdp_datasets
        _, current = self.current()
        row = copy.deepcopy(next(item for item in enumerate_rdp_datasets(self.data)[0] if item["dataset_manifest_id"] == current["current_dataset_manifest_id"]))
        row["dataset_id"] = "DATASET-GENERIC"
        row["evidence_role"] = "GENERIC_DISCOVERY"
        row["labels"] = {"logical_dataset_id": "DATASET-GENERIC", "confirmatory_reuse_forbidden": False}
        kwargs = {"visible_cohort_ids": current["visible_cohort_ids"], "lineage_bindings": current["lineage_bindings"], "current_dataset_manifest_id": current["current_dataset_manifest_id"], "corpus_version": current["corpus_version"]}
        before = build_market_evidence_basis(datasets=[row], **kwargs)
        del row["labels"]["confirmatory_reuse_forbidden"]
        after = build_market_evidence_basis(datasets=[row], **kwargs)
        epoch = market_evidence_epoch_sha256(before)
        self.assertEqual(epoch, market_evidence_epoch_sha256(after))
        session = self.session(epoch, before)
        self.assertEqual(epoch_search_budget_usage([session], evidence_epoch=epoch, market_evidence_basis=before), epoch_search_budget_usage([session], evidence_epoch=epoch, market_evidence_basis=after))

    def test_new_synthetic_cohort_changes_epoch(self):
        epoch, basis = self.current()
        session = self.session(epoch, basis)
        self.import_week(3)
        new_epoch, new_basis = self.current()
        self.assertNotEqual(epoch, new_epoch)
        usage = epoch_search_budget_usage([session], evidence_epoch=new_epoch, market_evidence_basis=new_basis)
        self.assertEqual(usage["auto_sessions_used"], 0)
        reservation = {**session, "phase": "RESERVED"}
        reservation.pop("market_evidence_basis")
        history = copy.deepcopy(reservation)
        with_reservation = epoch_search_budget_usage([session], reservations=[reservation], evidence_epoch=new_epoch, market_evidence_basis=new_basis)
        self.assertEqual(with_reservation["auto_sessions_used"], 0)
        admission = resolve_scientific_admission([session], reservations=[reservation], market_evidence_epoch=new_epoch, market_evidence_basis=new_basis, representation_id="BASE", representation_semantic_version="HFIC-V1.2", owner_focus="AUTO", repo_root=ROOT)
        self.assertEqual(admission["action"], "START_NEW_SESSION")
        self.assertEqual(reservation, history)

    def test_empty_history_cannot_admit_mismatched_basis(self):
        _, basis = self.current()
        admission = resolve_scientific_admission([], market_evidence_epoch="f" * 64, market_evidence_basis=basis, representation_id="BASE", representation_semantic_version="HFIC-V1.2", owner_focus="AUTO", repo_root=ROOT)
        self.assertEqual(admission["action"], "STOP")
        self.assertEqual(admission["reason_code"], "MARKET_EVIDENCE_BASIS_INCOMPLETE")
        with self.assertRaisesRegex(EvidenceIdentityError, "MARKET_EVIDENCE_BASIS_INCOMPLETE"):
            epoch_search_budget_usage([], evidence_epoch="f" * 64, market_evidence_basis=basis)

    def test_lifecycle_basis_preserves_explicit_unknown_and_conflict(self):
        from solana_alpha_lab.factory.hfic_session import list_hfic_sessions
        epoch, basis = self.current()
        initial = {**self.session(epoch, basis), "hfic_protocol": "HFIC-V1.2", "phase": "FROZEN_AWAITING_CRITIC", "hfic_cycle_seq": 1}
        for mode in ("absent", "unknown", "conflicting"):
            with self.subTest(mode=mode):
                latest = {**copy.deepcopy(initial), "hfic_cycle_seq": 2}
                if mode == "absent":
                    latest.pop("market_evidence_basis")
                elif mode == "unknown":
                    latest["market_evidence_basis"] = None
                else:
                    latest["market_evidence_basis"]["scientific_projection"]["datasets"][0]["derived"]["yield_eligible"] += 1
                records = [SimpleNamespace(record_kind="RESEARCH_CYCLE", payload_json=json.dumps(payload), effective_at="2026-10-02T00:00:00Z", record_id="CYCLE-" + str(n)) for n, payload in enumerate((initial, latest))]
                original_bytes = [record.payload_json for record in records]
                rows = list_hfic_sessions(SimpleNamespace(iter_committed_records=lambda: iter(records)))
                self.assertEqual(len(rows), 1)
                if mode == "absent":
                    self.assertEqual(rows[0]["market_evidence_basis"], basis)
                    self.assertNotEqual(rows[0].get("identity_binding_status"), "CONFLICT")
                else:
                    self.assertEqual(rows[0]["market_evidence_basis"], latest["market_evidence_basis"])
                    self.assertEqual(rows[0]["identity_binding_status"], "CONFLICT")
                    self.assertIn("market_evidence_basis", rows[0]["identity_conflict_fields"])
                    admission = resolve_scientific_admission(rows, market_evidence_epoch=epoch, market_evidence_basis=basis, representation_id="BASE", representation_semantic_version="HFIC-V1.2", owner_focus="AUTO", repo_root=ROOT)
                    self.assertEqual(admission["action"], "STOP")
                self.assertEqual(original_bytes, [record.payload_json for record in records])

    def test_conflicting_v1_history_cannot_disappear_after_wrapper_republish(self):
        from solana_alpha_lab.factory.hfic_session import list_hfic_sessions

        _, original_basis = self.current()
        old_v1_basis = _v1_publication_basis(original_basis)
        old_v1_epoch = _validated_v1_epoch(old_v1_basis)
        earlier = {**self.session(old_v1_epoch, old_v1_basis),
                   "hfic_protocol": "HFIC-V1.2", "phase": "SYNTHESIS_COMPLETE",
                   "hfic_cycle_seq": 1}
        other_data = self.base / "other-scientific-market"
        shutil.copytree(self.data, other_data)
        release, _, _ = _seal_week(self.base, 3)
        import_live_cohort(release_root=release, data_root=other_data,
                          import_time=datetime(2026, 2, 13, tzinfo=UTC))
        other_epoch, other_basis = compute_market_epoch_for_data_root(ROOT, other_data)
        later = {**self.session(other_epoch, other_basis),
                 "hfic_protocol": "HFIC-V1.2", "phase": "SYNTHESIS_COMPLETE",
                 "hfic_cycle_seq": 2}
        self.republish_metadata()
        epoch, basis = self.current()
        self.assertNotEqual(old_v1_epoch, _validated_v1_epoch(_v1_publication_basis(basis)))
        self.assertNotEqual(epoch, other_epoch)
        records = [SimpleNamespace(record_kind="RESEARCH_CYCLE", payload_json=json.dumps(payload),
                   effective_at="2026-10-02T00:00:00Z", record_id="CYCLE-" + str(n))
                   for n, payload in enumerate((earlier, later))]
        original_bytes = [record.payload_json for record in records]
        rows = list_hfic_sessions(SimpleNamespace(iter_committed_records=lambda: iter(records)))
        self.assertEqual(rows[0]["identity_binding_status"], "CONFLICT")
        admission = resolve_scientific_admission(rows, market_evidence_epoch=epoch,
                    market_evidence_basis=basis, representation_id="BASE",
                    representation_semantic_version="HFIC-V1.2", owner_focus="AUTO", repo_root=ROOT)
        self.assertEqual(admission["action"], "STOP")
        self.assertEqual(admission["reason_code"], "MARKET_EPOCH_CONTINUITY_UNRESOLVED")
        with self.assertRaisesRegex(EvidenceIdentityError, "MARKET_EPOCH_CONTINUITY_UNRESOLVED"):
            epoch_search_budget_usage(rows, evidence_epoch=epoch, market_evidence_basis=basis)
        self.assertEqual(original_bytes, [record.payload_json for record in records])

    def test_invalid_extra_canonical_dataset_cannot_disappear_into_fresh_budget(self):
        manifests = self.data / "datasets/manifests"
        mid = json.loads((self.data / "datasets/live_lifecycle_corpus/lineage.json").read_bytes())["current_dataset_manifest_id"]
        current = DatasetManifest.model_validate_json((manifests / (mid + ".json")).read_bytes())
        receipt = json.loads((manifests / (mid + ".validation.json")).read_bytes())
        part = PartitionManifest.model_validate_json((manifests / "partitions" / (receipt["partition_manifest_ids"][0] + ".json")).read_bytes())
        claim = part.model_dump()
        for key in ("dataset_manifest_id", "partition_manifest_id", "schema_version"):
            claim.pop(key, None)
        claim["partition_id"] = "EXTRA-PART"
        extra_part = build_partition_manifest(dataset_id="DATASET-EXTRA", dataset_version="v1", **claim)
        receipt_bytes = json.dumps({"partition_manifest_ids": [extra_part.partition_manifest_id]}, sort_keys=True, separators=(",", ":")).encode()
        extra = build_dataset_manifest(dataset_id="DATASET-EXTRA", dataset_version="v1", schema_id=current.schema_id, schema_sha256=current.schema_sha256, generation_task_id=current.generation_task_id, generation_run_id=current.generation_run_id, validation_receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(), first_reliable_available_at=current.first_reliable_available_at, created_at=current.created_at, partitions=[extra_part])
        root_path = manifests / (extra.dataset_manifest_id + ".json")
        receipt_path = manifests / (extra.dataset_manifest_id + ".validation.json")
        (manifests / "partitions" / (extra_part.partition_manifest_id + ".json")).write_bytes(canonical_manifest_bytes(extra_part))
        root_path.write_bytes(canonical_manifest_bytes(extra))
        receipt_path.write_bytes(receipt_bytes)
        epoch, basis = self.current()
        self.assertEqual(len(basis["datasets"]), 2)
        stable_path = manifests / "MID-EXTRA.json"
        root_path.rename(stable_path)
        with self.assertRaisesRegex(EvidenceIdentityError, "MARKET_EVIDENCE_BASIS_INCOMPLETE"):
            self.current()
        stable_path.write_bytes(b"{corrupted")
        with self.assertRaisesRegex(EvidenceIdentityError, "MARKET_EVIDENCE_BASIS_INCOMPLETE"):
            self.current()
        stable_path.unlink()
        for mutation in ("root_fingerprint", "missing_receipt", "broken_receipt"):
            with self.subTest(mutation=mutation):
                root_path.write_bytes(canonical_manifest_bytes(extra))
                receipt_path.write_bytes(receipt_bytes)
                if mutation == "root_fingerprint":
                    payload = json.loads(root_path.read_bytes())
                    payload["dataset_fingerprint"] = "f" * 64
                    root_path.write_text(json.dumps(payload), encoding="utf-8")
                elif mutation == "missing_receipt":
                    receipt_path.unlink()
                else:
                    receipt_path.write_bytes(b"{}")
                with self.assertRaisesRegex(EvidenceIdentityError, "MARKET_EVIDENCE_BASIS_INCOMPLETE"):
                    self.current()

    def test_ordinary_gate_translates_integrity_failure(self):
        from solana_alpha_lab.factory.hfic_ordinary_operation import (
            _admit, _assert_preflight_journal, OrdinaryOperationError,
        )
        from solana_alpha_lab.factory.research_store import ResearchStore
        epoch, _ = self.current()
        path = self.labels_path()
        path.write_bytes(b"{corrupted")
        with self.assertRaisesRegex(OrdinaryOperationError, "MARKET_EVIDENCE_BASIS_INCOMPLETE"):
            _admit(ResearchStore(self.data), {"market_evidence_epoch_sha256": epoch, "owner_focus": "AUTO"}, repo_root=ROOT, data_root=self.data)
        with self.assertRaisesRegex(OrdinaryOperationError, "MARKET_EVIDENCE_BASIS_INCOMPLETE"):
            _assert_preflight_journal(
                ResearchStore(self.data),
                {"market_evidence_epoch_sha256": epoch, "owner_focus": "AUTO"},
                "UNUSED-BECAUSE-INTEGRITY-STOPS-FIRST",
                repo_root=ROOT, data_root=self.data,
            )

    def test_lineage_tamper_is_incomplete_not_new_market(self):
        path = self.data / "datasets/live_lifecycle_corpus/lineage.json"
        lineage = json.loads(path.read_bytes())
        lineage["cohorts"][0]["content_sha256"] = "f" * 64
        path.write_text(json.dumps(lineage), encoding="utf-8")
        with self.assertRaisesRegex(EvidenceIdentityError, "MARKET_EVIDENCE_BASIS_INCOMPLETE"):
            self.current()

    def test_packet_cap_ignores_publication_id_order(self):
        rows = [{"dataset_id": "DATASET-" + name, "dataset_manifest_id": "MID-" + name} for name in ("A", "B", "C")]
        old, _ = select_forge_packet_datasets(rows, max_datasets=2)
        rows[0]["dataset_manifest_id"] = "MID-Z-REPUBLISHED"
        new, _ = select_forge_packet_datasets(rows, max_datasets=2)
        self.assertEqual([r["dataset_id"] for r in old], [r["dataset_id"] for r in new])

    def republish_metadata(self, *, pit_change=False):
        """Pure TASK-06 builders publish a new wrapper on unchanged fixture parquet.

        This deliberately does not invoke the LIVE repair implementation.
        """
        manifests = self.data / "datasets/manifests"
        lineage_path = self.data / "datasets/live_lifecycle_corpus/lineage.json"
        lineage = json.loads(lineage_path.read_bytes())
        old_mid = lineage["current_dataset_manifest_id"]
        old = DatasetManifest.model_validate_json((manifests / (old_mid + ".json")).read_bytes())
        receipt = json.loads((manifests / (old_mid + ".validation.json")).read_bytes())
        version = old.dataset_version.removesuffix(".canonical-v1") + ".schema-B.canonical-v1"
        mid = compute_dataset_manifest_id(old.dataset_id, version)
        clock = datetime(2026, 10, 1, tzinfo=UTC)
        publication_at = clock.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        parts = []
        for part_id in receipt["partition_manifest_ids"]:
            old_part = PartitionManifest.model_validate_json((manifests / "partitions" / (part_id + ".json")).read_bytes())
            claim = old_part.model_dump()
            claim.pop("dataset_manifest_id")
            claim.pop("partition_manifest_id")
            claim.pop("schema_version", None)
            claim["created_at"] = clock
            claim["first_reliable_available_at"] = clock
            if pit_change:
                if claim["min_available_to_strategy_at"] is not None:
                    claim["min_available_to_strategy_at"] -= timedelta(seconds=1)
                else:
                    claim["min_available_to_strategy_at"] = datetime(2026, 1, 1, tzinfo=UTC)
                    claim["max_available_to_strategy_at"] = datetime(2026, 1, 1, tzinfo=UTC)
            part = build_partition_manifest(dataset_id=old.dataset_id, dataset_version=version, **claim)
            parts.append(part)
            (manifests / "partitions" / (part.partition_manifest_id + ".json")).write_bytes(canonical_manifest_bytes(part))
        schema_sha = "b" * 64
        fp = compute_dataset_fingerprint(dataset_id=old.dataset_id, dataset_version=version, schema_id=old.schema_id, schema_sha256=schema_sha, partitions=parts)
        receipt.update(dataset_manifest_id=mid, dataset_fingerprint=fp,
                       dataset_version=version, schema_sha256=schema_sha,
                       published_at=publication_at,
                       partition_manifest_ids=[p.partition_manifest_id for p in parts])
        receipt_bytes = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        new = build_dataset_manifest(dataset_id=old.dataset_id, dataset_version=version, schema_id=old.schema_id, schema_sha256=schema_sha,
                                     generation_task_id=old.generation_task_id, generation_run_id=old.generation_run_id,
                                     validation_receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
                                     first_reliable_available_at=clock, created_at=clock, partitions=parts)
        verify_dataset_manifest(new, partitions=parts)
        (manifests / (mid + ".json")).write_bytes(canonical_manifest_bytes(new))
        (manifests / (mid + ".validation.json")).write_bytes(receipt_bytes)
        (manifests / (mid + ".publication-clock.json")).write_text(json.dumps({
            "created_at": publication_at, "first_reliable_available_at": publication_at,
        }), encoding="utf-8")
        labels = json.loads((manifests / (old_mid + ".labels.json")).read_bytes())
        labels["is_current_corpus_version"] = False
        (manifests / (old_mid + ".labels.json")).write_text(json.dumps(labels), encoding="utf-8")
        labels.update(is_current_corpus_version=True, dataset_version=version, imported_at=clock.isoformat())
        (manifests / (mid + ".labels.json")).write_text(json.dumps(labels), encoding="utf-8")
        published = json.loads((manifests / (old_mid + ".published")).read_bytes())
        published.update(dataset_manifest_id=mid, dataset_fingerprint=fp,
                         metadata_clock_at=publication_at, published_at=publication_at)
        (manifests / (mid + ".published")).write_text(json.dumps(published), encoding="utf-8")
        lineage["current_dataset_manifest_id"] = mid
        lineage["cohorts"][-1].update(dataset_manifest_id=mid, dataset_version=version)
        lineage_path.write_text(json.dumps(lineage), encoding="utf-8")
        return old, new

    def test_schema_republish_preserves_science_and_budget(self):
        epoch, basis = self.current()
        session = self.session(epoch, basis)
        before = epoch_search_budget_usage([session], evidence_epoch=epoch, market_evidence_basis=basis)
        hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.data.rglob("*.parquet")}
        old, new = self.republish_metadata()
        self.assertNotEqual(old.dataset_manifest_id, new.dataset_manifest_id)
        self.assertNotEqual(old.dataset_fingerprint, new.dataset_fingerprint)
        self.assertNotEqual(old.schema_sha256, new.schema_sha256)
        after_epoch, after_basis = self.current()
        self.assertEqual(epoch, after_epoch)
        self.assertEqual(basis["scientific_projection"], after_basis["scientific_projection"])
        self.assertNotEqual(basis["datasets"], after_basis["datasets"])
        self.assertEqual(before, epoch_search_budget_usage([session], evidence_epoch=after_epoch, market_evidence_basis=after_basis))
        self.assertEqual(hashes, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.data.rglob("*.parquet")})

    def test_pit_semantics_change_changes_market(self):
        epoch, _ = self.current()
        self.republish_metadata(pit_change=True)
        self.assertNotEqual(epoch, self.current()[0])

    def test_parquet_tamper_is_incomplete(self):
        path = next(self.data.rglob("*.parquet"))
        path.write_bytes(path.read_bytes() + b"tamper")
        with self.assertRaisesRegex(EvidenceIdentityError, "MARKET_EVIDENCE_BASIS_INCOMPLETE"):
            self.current()

    def test_v1_migration_preserves_occupancy_and_history(self):
        epoch, basis = self.current()
        v1_basis = _v1_publication_basis(basis)
        v1_epoch = _validated_v1_epoch(v1_basis)
        session = self.session(v1_epoch, v1_basis)
        history = copy.deepcopy(session)
        before = epoch_search_budget_usage([session], evidence_epoch=v1_epoch)
        after = epoch_search_budget_usage([session], evidence_epoch=epoch, market_evidence_basis=basis)
        before.pop("evidence_epoch_sha256")
        after.pop("evidence_epoch_sha256")
        self.assertEqual(before, after)
        self.assertEqual(session, history)
        admission = resolve_scientific_admission([session], market_evidence_epoch=epoch, market_evidence_basis=basis, representation_id="BASE", representation_semantic_version="HFIC-V1.2", owner_focus="AUTO", repo_root=ROOT)
        self.assertEqual(admission["action"], "RETURN_EXISTING_SESSION")
        self.assertEqual(admission["session_id"], session["session_id"])
        without_basis = resolve_scientific_admission([session], market_evidence_epoch=epoch, representation_id="BASE", representation_semantic_version="HFIC-V1.2", owner_focus="AUTO", repo_root=ROOT)
        self.assertEqual(without_basis["action"], "STOP")
        self.assertEqual(without_basis["reason_code"], "MARKET_EPOCH_CONTINUITY_UNRESOLVED")

    def test_verified_changed_schedule_content_changes_market(self):
        epoch, basis = self.current()
        alternate = self.base / "changed_source"
        alternate.mkdir()
        data = alternate / "rdp"
        data.mkdir()

        def changed_snapshot(week):
            snapshot = _snapshot_for_week(week)
            if week != 0:
                return snapshot
            old_sha = snapshot["schedule_sha256"]
            def replace(value):
                if isinstance(value, dict):
                    return {key: replace(item) for key, item in value.items()}
                if isinstance(value, list):
                    return [replace(item) for item in value]
                return "f" * 64 if value == old_sha else value
            return replace(snapshot)

        with patch("tests.test_live_corpus_manifest_contract_repair_v1._snapshot_for_week", side_effect=changed_snapshot):
            for week in range(3):
                release, _, _ = _seal_week(alternate, week)
                import_live_cohort(release_root=release, data_root=data, import_time=datetime(2026, 2, 10 + week, tzinfo=UTC))
        changed_epoch, changed_basis = compute_market_epoch_for_data_root(ROOT, data)
        self.assertEqual(basis["visible_cohort_ids"], changed_basis["visible_cohort_ids"])
        self.assertNotEqual(basis["lineage_bindings"], changed_basis["lineage_bindings"])
        self.assertNotEqual(epoch, changed_epoch)
        v1 = _v1_publication_basis(basis)
        session = self.session(_validated_v1_epoch(v1), v1)
        usage = epoch_search_budget_usage([session], evidence_epoch=changed_epoch, market_evidence_basis=changed_basis)
        self.assertEqual(usage["auto_sessions_used"], 0)

    def test_ambiguous_v1_never_frees_capacity(self):
        _, basis = self.current()
        v1_basis = _v1_publication_basis(basis)
        v1_epoch = _validated_v1_epoch(v1_basis)
        session = self.session(v1_epoch, v1_basis)
        self.republish_metadata()
        epoch, basis = self.current()
        with self.assertRaisesRegex(EvidenceIdentityError, "MARKET_EPOCH_CONTINUITY_UNRESOLVED"):
            epoch_search_budget_usage([session], evidence_epoch=epoch, market_evidence_basis=basis)
        result = resolve_scientific_admission([session], market_evidence_epoch=epoch, market_evidence_basis=basis, representation_id="BASE", representation_semantic_version="HFIC-V1.2", owner_focus="NEW_FOCUS", repo_root=ROOT)
        self.assertEqual(result["action"], "STOP")
        self.assertEqual(result["reason_code"], "MARKET_EPOCH_CONTINUITY_UNRESOLVED")

    def test_capability_only_change_does_not_change_market(self):
        epoch, _ = self.current()
        cap_before, _ = compute_capability_epoch_for_repo(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            for name in (*_CAPABILITY_PROTOCOL_FILES, _OPERATOR_PACK):
                destination = repo / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, destination)
            shutil.copytree(ROOT / "catalog", repo / "catalog", dirs_exist_ok=True)
            shutil.copyfile(ROOT / "configs/factory_semantic_operability_v1.yaml", repo / "configs/factory_semantic_operability_v1.yaml")
            path = repo / "configs/hypothesis_forge_independent_critic_v1.yaml"
            path.write_text("different protocol", encoding="utf-8")
            cap_after, _ = compute_capability_epoch_for_repo(repo)
        self.assertNotEqual(cap_before, cap_after)
        self.assertEqual(epoch, self.current()[0])


if __name__ == "__main__":
    unittest.main()
