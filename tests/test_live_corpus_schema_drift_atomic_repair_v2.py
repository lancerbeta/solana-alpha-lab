"""Production-shaped LIVE repair verticals; no real data-plane access."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tests.test_live_corpus_manifest_contract_repair_v1 import _seal_week
from tests import test_hfic_market_evidence_epoch_decision_basis_v2 as market_fixture
from solana_alpha_lab.factory import live_corpus_logical_rows as logical
from solana_alpha_lab.factory import live_corpus_manifest_publish as publish
from solana_alpha_lab.factory.live_cohort_discovery_release import (
    import_live_cohort, repair_live_corpus_manifests,
    load_live_corpus_lineage, select_current_datasets_for_forge,
    current_corpus_partition_rows,
)
from solana_alpha_lab.factory.hfic_preflight import enumerate_rdp_datasets, epoch_search_budget_usage
from solana_alpha_lab.factory.hfic_evidence_identity import compute_market_epoch_for_data_root
from solana_alpha_lab.factory.cohort_import_readback import build_cohort_import_readback
from solana_alpha_lab.factory.forge_input_receipt import build_forge_input_receipt


def inventory(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


class LiveCorpusAtomicRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.data = self.base / "rdp"
        self.data.mkdir()
        schema_a = {**logical.live_corpus_schema_projection(), "metadata_contract": "scratch-A"}
        # Change the real metadata contract projection, never production claims.
        with patch.object(logical, "live_corpus_schema_projection", return_value=schema_a):
            for week in range(3):
                self.import_week(week)
        self.old = load_live_corpus_lineage(self.data)["current_dataset_manifest_id"]
        self.before = inventory(self.data)
        self.releases = {f"rel_{n}": inventory(self.base / f"rel_{n}") for n in range(3)}
        self.epoch, self.basis = compute_market_epoch_for_data_root(ROOT, self.data)

    def import_week(self, week):
        release, _, _ = _seal_week(self.base, week)
        return import_live_cohort(release_root=release, data_root=self.data,
                                  import_time=datetime(2026, 2, 10 + week, tzinfo=UTC))

    def repair(self, **kwargs):
        return repair_live_corpus_manifests(data_root=self.data,
                    published_at=datetime(2026, 3, 1, tzinfo=UTC), **kwargs)

    def assert_old_visible(self):
        after = inventory(self.data)
        for path, content in self.before.items():
            self.assertEqual(after[path], content, path)
        self.assertEqual(load_live_corpus_lineage(self.data)["current_dataset_manifest_id"], self.old)
        self.assertEqual(compute_market_epoch_for_data_root(ROOT, self.data)[0], self.epoch)

    def assert_immutable_data(self):
        after = inventory(self.data)
        for path, content in self.before.items():
            if path.endswith(".parquet"):
                self.assertEqual(after[path], content, path)
        for name, contents in self.releases.items():
            self.assertEqual(inventory(self.base / name), contents)

    def test_already_canonical_schema_drift_preserves_science_and_budget(self):
        session = market_fixture.ScientificMarketV2Tests.session(self.epoch, self.basis)
        from solana_alpha_lab.factory.hfic_session import focus_key_sha256
        from solana_alpha_lab.factory.hfic_evidence_identity import scientific_slot_sha256
        focus = {**copy.deepcopy(session), "session_id": "SCRATCH_CONSUMED_FOCUS", "owner_focus": "EARLY_LIQUIDITY"}
        focus["focus_key_sha256"] = focus_key_sha256(focus["owner_focus"])
        focus["scientific_slot_sha256"] = scientific_slot_sha256(
            market_evidence_epoch_sha256=self.epoch, representation_id="BASE",
            representation_semantic_version="HFIC-V1.2", owner_focus=focus["owner_focus"])
        history = copy.deepcopy([session, focus])
        usage = epoch_search_budget_usage(history, evidence_epoch=self.epoch, market_evidence_basis=self.basis)
        result = self.repair()
        self.assertNotEqual(result["dataset_manifest_id"], self.old)
        self.assertEqual(result["corpus_version"], 3)
        self.assertEqual(result["status"], "REPAIRED")
        self.assertFalse(result["epoch_bump"])
        self.assertTrue(publish.inspect_canonical_root(self.data, result["dataset_manifest_id"])["complete"])
        after_epoch, after_basis = compute_market_epoch_for_data_root(ROOT, self.data)
        self.assertEqual(after_epoch, self.epoch)
        self.assertEqual(usage, epoch_search_budget_usage(history, evidence_epoch=after_epoch, market_evidence_basis=after_basis))
        self.assertEqual(history, [session, focus])
        for path, content in self.before.items():
            if path.startswith("datasets/manifests/") and not path.endswith(".labels.json"):
                self.assertEqual((self.data / path).read_bytes(), content)
        self.assert_immutable_data()
        stable = inventory(self.data)
        repeated = self.repair()
        self.assertEqual(repeated["status"], "IDEMPOTENT_REPAIR")
        self.assertEqual(repeated["logical_rows_measured_partitions"], 6)
        self.assertEqual(repeated["dataset_manifest_id"], result["dataset_manifest_id"])
        self.assertEqual(inventory(self.data), stable)

    def test_precommit_fault_preserves_visible_inventory_and_retry_converges(self):
        def crash():
            raise RuntimeError("scratch pre-commit interruption")
        with self.assertRaisesRegex(RuntimeError, "interruption"):
            self.repair(fault_before_visibility=crash)
        self.assert_old_visible()
        result = self.repair()
        self.assertEqual(result["status"], "REPAIRED")
        self.assertEqual(self.repair()["status"], "IDEMPOTENT_REPAIR")
        self.assert_immutable_data()

    def test_stale_labels_after_lineage_switch_cannot_select_old_root(self):
        def crash(**kwargs):
            raise RuntimeError("scratch after-switch interruption")
        with patch.object(publish, "_reconcile_current_labels", side_effect=crash):
            with self.assertRaisesRegex(RuntimeError, "after-switch"):
                self.repair()
        new = load_live_corpus_lineage(self.data)["current_dataset_manifest_id"]
        self.assertNotEqual(new, self.old)
        rows, warnings = enumerate_rdp_datasets(self.data)
        self.assertEqual(warnings, [])
        selected = select_current_datasets_for_forge(rows)
        self.assertEqual([row["dataset_manifest_id"] for row in selected], [new])
        self.assertEqual(compute_market_epoch_for_data_root(ROOT, self.data)[0], self.epoch)
        receipt = build_forge_input_receipt(self.data, repo_root=ROOT)
        self.assertEqual(receipt["active_evidence_set"]["current_dataset_manifest_id"], new)
        self.assertEqual(len(current_corpus_partition_rows(self.data)), 15)
        self.assertEqual(build_cohort_import_readback(self.data)["current_dataset_manifest_id"], new)
        self.assertEqual(self.repair()["status"], "IDEMPOTENT_REPAIR")
        self.assert_immutable_data()

    def test_preparation_fault_boundaries_leave_old_current_and_retry_reuses_identity(self):
        for boundary in (".labels.json", "partition-", ".validation.json", "DATASET_ROOT", ".published"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as tmp:
                import shutil
                data = Path(tmp) / "rdp"
                shutil.copytree(self.data, data)
                before = inventory(data)
                original = publish._publish_metadata
                hit = False
                def interrupted(root, path, payload):
                    nonlocal hit
                    original(root, path, payload)
                    if boundary == "partition-":
                        matches = path.name.startswith(boundary)
                    elif boundary == "DATASET_ROOT":
                        matches = path.name.startswith("dataset-") and path.name.endswith(".json") and not path.name.endswith((".labels.json", ".validation.json", ".publication-clock.json"))
                    else:
                        matches = path.name.endswith(boundary)
                    if matches and not hit:
                        hit = True
                        raise RuntimeError("scratch prepared interruption")
                with patch.object(publish, "_publish_metadata", side_effect=interrupted):
                    with self.assertRaisesRegex(RuntimeError, "prepared"):
                        repair_live_corpus_manifests(data_root=data)
                for path, content in before.items():
                    self.assertEqual((data / path).read_bytes(), content, path)
                self.assertEqual(compute_market_epoch_for_data_root(ROOT, data)[0], self.epoch)
                result = repair_live_corpus_manifests(data_root=data)
                self.assertEqual(result["status"], "REPAIRED")
                self.assertEqual(repair_live_corpus_manifests(data_root=data)["status"], "IDEMPOTENT_REPAIR")

    def test_conflicting_candidate_is_never_overwritten(self):
        from solana_alpha_lab.storage.manifests import compute_dataset_manifest_id
        old = publish._load_dataset_manifest(self.data, self.old)
        mid = compute_dataset_manifest_id(publish.CORPUS_DATASET_ID,
            publish.repair_dataset_version(old.dataset_version, logical.live_corpus_schema_sha256(),
                                           load_live_corpus_lineage(self.data)["cohorts"]))
        target = self.data / "datasets/manifests" / f"{mid}.json"
        target.write_bytes(b'{"incompatible_immutable_bytes":true}')
        before = inventory(self.data)
        with self.assertRaisesRegex(Exception, "CANONICAL_TARGET_CONFLICT"):
            self.repair()
        self.assertEqual(target.read_bytes(), before[target.relative_to(self.data).as_posix()])
        for path, content in self.before.items():
            self.assertEqual((self.data / path).read_bytes(), content, path)

    def test_parquet_byte_drift_stops_without_metadata_mutation(self):
        path = next(self.data.rglob("*.parquet"))
        content = path.read_bytes()
        path.write_bytes(content[:-1] + bytes([content[-1] ^ 1]))
        before = inventory(self.data)
        with self.assertRaisesRegex(Exception, "CORPUS_PARQUET_SHA_MISMATCH"):
            self.repair()
        self.assertEqual(inventory(self.data), before)

    def test_logical_reconstruction_failure_is_typed_and_has_no_writes(self):
        before = inventory(self.data)
        with patch.object(logical, "_table_from_batch", side_effect=ValueError("scratch invalid typed row")):
            with self.assertRaisesRegex(Exception, "LIVE_CORPUS_LOGICAL_CONTENT_NOT_RECONSTRUCTIBLE"):
                self.repair()
        self.assertEqual(inventory(self.data), before)

    def test_cleanup_failure_leaves_new_current_and_retry_is_idempotent(self):
        original = publish._atomic_replace_json
        def cleanup(path, payload):
            if path.name == f"{self.old}.labels.json":
                raise RuntimeError("scratch cleanup interrupted")
            original(path, payload)
        with patch.object(publish, "_atomic_replace_json", side_effect=cleanup):
            with self.assertRaisesRegex(RuntimeError, "cleanup"):
                self.repair()
        new = load_live_corpus_lineage(self.data)["current_dataset_manifest_id"]
        self.assertNotEqual(new, self.old)
        rows, _ = enumerate_rdp_datasets(self.data)
        self.assertEqual(select_current_datasets_for_forge(rows)[0]["dataset_manifest_id"], new)
        self.assertEqual(compute_market_epoch_for_data_root(ROOT, self.data)[0], self.epoch)
        self.assertEqual(self.repair()["status"], "IDEMPOTENT_REPAIR")

    def test_nonlexicographic_claim_order_import_keeps_exact_partition_integrity(self):
        self.repair()
        original = publish._claims_for_cohort
        def reverse_claims(**kwargs):
            return list(reversed(original(**kwargs)))
        with patch.object(publish, "_claims_for_cohort", side_effect=reverse_claims):
            result = self.import_week(3)
        self.assertEqual(result["corpus_version"], 4)
        self.assertTrue(publish.inspect_canonical_root(self.data, result["dataset_manifest_id"])["complete"])
        self.assert_immutable_data()

    def test_synthetic_next_import_after_repair_is_real_v4_once_each(self):
        repaired = self.repair()
        result = self.import_week(3)
        self.assertEqual(result["corpus_version"], 4)
        self.assertTrue(result["epoch_bump"])
        self.assertNotEqual(result["dataset_manifest_id"], repaired["dataset_manifest_id"])
        readback = build_cohort_import_readback(self.data)
        self.assertEqual(readback["duplicate_cohort_count"], 0)
        self.assertEqual(len(readback["visible_cohorts"]), 4)
        self.assertTrue(all(row["lineage_count"] == 1 for row in readback["visible_cohorts"]))
        self.assertTrue(publish.inspect_canonical_root(self.data, result["dataset_manifest_id"])["complete"])
        rows, warnings = enumerate_rdp_datasets(self.data)
        self.assertEqual(warnings, [])
        self.assertEqual(select_current_datasets_for_forge(rows)[0]["dataset_manifest_id"], result["dataset_manifest_id"])
        epoch, basis = compute_market_epoch_for_data_root(ROOT, self.data)
        self.assertNotEqual(epoch, self.epoch)
        history = [market_fixture.ScientificMarketV2Tests.session(self.epoch, self.basis)]
        self.assertEqual(epoch_search_budget_usage(history, evidence_epoch=epoch, market_evidence_basis=basis)["auto_sessions_used"], 0)
        self.assert_immutable_data()

    def test_existing_repair_cli_reports_repaired_then_idempotent(self):
        command = [sys.executable, "-X", "utf8", "-B", str(ROOT / "scripts/discovery_evidence_release.py"),
                   "repair-live-corpus-manifests", "--data-root", str(self.data)]
        first = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(first.returncode, 0, first.stderr)
        result = json.loads(first.stdout)["result"]
        self.assertEqual(result["status"], "REPAIRED")
        self.assertEqual(result["dataset_manifest_id_before"], self.old)
        self.assertTrue(result["lineage_switched"])
        second = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(second.stdout)["result"]["status"], "IDEMPOTENT_REPAIR")

    def test_invalid_new_current_is_stopped_without_history_regeneration(self):
        result = self.repair()
        marker = self.data / "datasets/manifests" / f"{result['dataset_manifest_id']}.published"
        marker.unlink()
        before = inventory(self.data)
        with self.assertRaisesRegex(Exception, "UNPUBLISHED"):
            self.repair()
        self.assertEqual(inventory(self.data), before)

    def test_candidate_corruption_before_verify_never_switches_lineage(self):
        def tamper():
            candidate = next(p for p in self.data.glob("datasets/manifests/*.labels.json")
                             if p.name not in {Path(path).name for path in self.before})
            labels = json.loads(candidate.read_bytes())
            labels["yield_eligible"] += 1
            candidate.write_text(json.dumps(labels), encoding="utf-8")
        with self.assertRaisesRegex(Exception, "CANDIDATE_VERIFICATION_FAILED"):
            self.repair(fault_before_visibility=tamper)
        self.assert_old_visible()

    def test_lineage_replace_failure_and_retry_keep_one_current_owner(self):
        original = Path.replace
        def interrupted(path, destination):
            if Path(destination).name == "lineage.json":
                raise OSError("scratch lineage replace failure")
            return original(path, destination)
        with patch.object(Path, "replace", autospec=True, side_effect=interrupted):
            with self.assertRaisesRegex(OSError, "lineage replace"):
                self.repair()
        self.assert_old_visible()
        self.assertEqual(self.repair()["candidate_disposition"], "REUSED")
        self.assertEqual(self.repair()["status"], "IDEMPOTENT_REPAIR")

    def test_incomplete_lineage_and_escaping_path_stop_with_no_writes(self):
        lineage_path = self.data / "datasets/live_lifecycle_corpus/lineage.json"
        original = lineage_path.read_bytes()
        for mutation, code in (("missing", "CORPUS_LINEAGE_INCOMPLETE"),
                               ("escape", "LIVE_CORPUS_PATH_INTEGRITY")):
            with self.subTest(mutation=mutation):
                lineage = json.loads(original)
                if mutation == "missing":
                    del lineage["cohorts"][0]["yield_eligible"]
                else:
                    lineage["cohorts"][0]["census_rel"] = "../outside.parquet"
                lineage_path.write_text(json.dumps(lineage), encoding="utf-8")
                before = inventory(self.data)
                with self.assertRaisesRegex(Exception, code):
                    self.repair()
                self.assertEqual(inventory(self.data), before)
        lineage_path.write_bytes(original)

    def test_broken_uncommitted_partition_cannot_poison_current_rows(self):
        original = publish._publish_metadata
        def interrupted(root, path, payload):
            original(root, path, payload)
            if path.name.startswith("partition-"):
                path.write_bytes(b"{scratch broken candidate partition")
                raise RuntimeError("scratch interrupted partition")
        with patch.object(publish, "_publish_metadata", side_effect=interrupted):
            with self.assertRaisesRegex(RuntimeError, "interrupted partition"):
                self.repair()
        self.assert_old_visible()
        # This reader must use only the validated current inventory, not scan
        # uncommitted metadata belonging to other roots.
        self.assertEqual(len(current_corpus_partition_rows(self.data)), 15)

    def test_schema_cycle_reuses_verified_historical_candidate_without_overwrite(self):
        first = self.repair()
        first_root = self.data / "datasets/manifests" / f"{first['dataset_manifest_id']}.json"
        first_bytes = first_root.read_bytes()
        schema_c = {**logical.live_corpus_schema_projection(), "metadata_contract": "scratch-C"}
        with patch.object(logical, "live_corpus_schema_projection", return_value=schema_c):
            middle = self.repair()
        self.assertNotEqual(first["dataset_manifest_id"], middle["dataset_manifest_id"])
        last = self.repair()
        self.assertEqual(last["dataset_manifest_id"], first["dataset_manifest_id"])
        self.assertEqual(last["candidate_disposition"], "REUSED")
        self.assertEqual(first_root.read_bytes(), first_bytes)
        self.assertEqual(compute_market_epoch_for_data_root(ROOT, self.data)[0], self.epoch)
        self.assertEqual(self.repair()["status"], "IDEMPOTENT_REPAIR")

    def test_invalid_uncommitted_dataset_does_not_block_old_market(self):
        def tamper():
            dataset = next(p for p in self.data.glob("datasets/manifests/dataset-*.json")
                           if p.name.endswith(".json") and p.name not in {Path(path).name for path in self.before}
                           and not p.name.endswith((".labels.json", ".validation.json", ".publication-clock.json")))
            dataset.write_bytes(b"{scratch broken candidate dataset")
        with self.assertRaisesRegex(Exception, "CANDIDATE_VERIFICATION_FAILED"):
            self.repair(fault_before_visibility=tamper)
        self.assert_old_visible()

    def test_partial_schema_cycle_converges_with_identical_target_bytes_and_budget(self):
        from solana_alpha_lab.storage.manifests import compute_dataset_manifest_id
        from solana_alpha_lab.factory.hfic_session import focus_key_sha256
        from solana_alpha_lab.factory.hfic_evidence_identity import scientific_slot_sha256
        session = market_fixture.ScientificMarketV2Tests.session(self.epoch, self.basis)
        focus = {**copy.deepcopy(session), "session_id": "SCRATCH_CONSUMED_FOCUS", "owner_focus": "EARLY_LIQUIDITY"}
        focus["focus_key_sha256"] = focus_key_sha256(focus["owner_focus"])
        focus["scientific_slot_sha256"] = scientific_slot_sha256(
            market_evidence_epoch_sha256=self.epoch, representation_id="BASE",
            representation_semantic_version="HFIC-V1.2", owner_focus=focus["owner_focus"])
        history = [session, focus]
        history_before = copy.deepcopy(history)
        usage = epoch_search_budget_usage(history, evidence_epoch=self.epoch, market_evidence_basis=self.basis)
        schema_c = {**logical.live_corpus_schema_projection(), "metadata_contract": "scratch-C"}
        for boundary in (".validation.json", "DATASET_ROOT"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as tmp:
                import shutil
                data = Path(tmp) / "rdp"
                shutil.copytree(self.data, data)
                current = publish._load_dataset_manifest(data, self.old)
                version_b = publish.repair_dataset_version(current.dataset_version,
                    logical.live_corpus_schema_sha256(), load_live_corpus_lineage(data)["cohorts"])
                target_b = compute_dataset_manifest_id(publish.CORPUS_DATASET_ID, version_b)
                original = publish._publish_metadata
                def interrupt(root, path, payload):
                    original(root, path, payload)
                    if path.name == (f"{target_b}.json" if boundary == "DATASET_ROOT" else f"{target_b}{boundary}"):
                        raise RuntimeError("scratch late B interruption")
                with patch.object(publish, "_publish_metadata", side_effect=interrupt):
                    with self.assertRaisesRegex(RuntimeError, "late B"):
                        repair_live_corpus_manifests(data_root=data)
                partial = inventory(data)
                immutable_b = {path: content for path, content in partial.items()
                    if path not in self.before and not path.endswith(".labels.json")}
                self.assertTrue(any(path.endswith(".validation.json") for path in immutable_b))
                for path, content in self.before.items():
                    self.assertEqual(partial[path], content, path)
                self.assertEqual(compute_market_epoch_for_data_root(ROOT, data)[0], self.epoch)
                with patch.object(logical, "live_corpus_schema_projection", return_value=schema_c):
                    middle = repair_live_corpus_manifests(data_root=data)
                self.assertNotEqual(middle["dataset_manifest_id"], target_b)
                final = repair_live_corpus_manifests(data_root=data)
                self.assertEqual(final["dataset_manifest_id"], target_b)
                self.assertEqual(final["candidate_disposition"], "REBUILT_PARTIAL")
                self.assertEqual(final["superseded_dataset_manifest_id"], middle["dataset_manifest_id"])
                self.assertEqual(final["corpus_version"], 3)
                for path, content in immutable_b.items():
                    self.assertEqual((data / path).read_bytes(), content, path)
                inspection = publish.inspect_canonical_root(data, target_b)
                self.assertTrue(inspection["complete"])
                self.assertEqual(inspection["dataset"].generation_run_id, f"repair-{target_b[8:]}")
                receipt = json.loads((data / f"datasets/manifests/{target_b}.validation.json").read_bytes())
                self.assertIsNone(receipt["superseded_dataset_manifest_id"])
                labels = json.loads((data / f"datasets/manifests/{target_b}.labels.json").read_bytes())
                self.assertNotIn("superseded_dataset_manifest_id", labels)
                stable = inventory(data)
                repeated = repair_live_corpus_manifests(data_root=data)
                self.assertEqual(repeated["status"], "IDEMPOTENT_REPAIR")
                self.assertEqual(repeated["superseded_dataset_manifest_id"], middle["dataset_manifest_id"])
                self.assertEqual(inventory(data), stable)
                after_epoch, after_basis = compute_market_epoch_for_data_root(ROOT, data)
                self.assertEqual(after_epoch, self.epoch)
                self.assertEqual(epoch_search_budget_usage(history, evidence_epoch=after_epoch,
                    market_evidence_basis=after_basis), usage)
                self.assertEqual(history, history_before)

    def test_imported_canonical_root_detects_receipt_contract_drift_at_same_schema(self):
        schema_a = {**logical.live_corpus_schema_projection(), "metadata_contract": "scratch-A"}
        with patch.object(logical, "live_corpus_schema_projection", return_value=schema_a):
            with patch.object(publish, "VALIDATION_RECEIPT_SCHEMA_VERSION", "scratch-new-version"):
                result = self.repair()
                self.assertEqual(result["status"], "REPAIRED")
                self.assertNotEqual(result["dataset_manifest_id"], self.old)
                self.assertEqual(result["corpus_version"], 3)
                self.assertTrue(publish.inspect_canonical_root(self.data, result["dataset_manifest_id"])["complete"])
                self.assertEqual(self.repair()["status"], "IDEMPOTENT_REPAIR")
        self.assertEqual(compute_market_epoch_for_data_root(ROOT, self.data)[0], self.epoch)
        self.assert_immutable_data()

    def test_bounded_metadata_contract_change_gets_new_identity_without_new_science(self):
        first = self.repair()
        with patch.object(publish, "VALIDATION_RECEIPT_SCHEMA_VERSION", "scratch-version-B"):
            second = self.repair()
            self.assertNotEqual(second["dataset_manifest_id"], first["dataset_manifest_id"])
            self.assertEqual(self.repair()["status"], "IDEMPOTENT_REPAIR")
            self.assertTrue(publish.inspect_canonical_root(self.data, second["dataset_manifest_id"])["complete"])
        self.assertEqual(self.repair()["dataset_manifest_id"], first["dataset_manifest_id"])
        self.assertEqual(compute_market_epoch_for_data_root(ROOT, self.data)[0], self.epoch)

    def test_repaired_target_rejects_valid_but_wrong_generation_or_receipt_contract(self):
        from solana_alpha_lab.storage.manifests import canonical_manifest_bytes
        import hashlib
        import shutil
        first = self.repair()
        schema_c = {**logical.live_corpus_schema_projection(), "metadata_contract": "scratch-C"}
        for location in ("CURRENT", "HISTORICAL_REUSE"):
            for mutation in ("GENERATION", "RECEIPT"):
                with self.subTest(location=location, mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                    data = Path(tmp) / "rdp"
                    shutil.copytree(self.data, data)
                    if location == "HISTORICAL_REUSE":
                        with patch.object(logical, "live_corpus_schema_projection", return_value=schema_c):
                            repair_live_corpus_manifests(data_root=data)
                    inspection = publish.inspect_canonical_root(data, first["dataset_manifest_id"])
                    dataset = inspection["dataset"]
                    receipt_path = data / f"datasets/manifests/{dataset.dataset_manifest_id}.validation.json"
                    receipt_bytes = receipt_path.read_bytes()
                    run_id = dataset.generation_run_id
                    if mutation == "GENERATION":
                        run_id = "SCRATCH-INVALID-TARGET-DERIVATION"
                    else:
                        receipt = json.loads(receipt_bytes)
                        receipt["schema_version"] = "SCRATCH-INVALID-TARGET-CONTRACT"
                        receipt_bytes = publish._canonical_receipt_bytes(receipt)
                        receipt_path.write_bytes(receipt_bytes)
                    wrong = publish._build_dataset(dataset_version=dataset.dataset_version,
                        schema_sha256=dataset.schema_sha256, partitions=inspection["partitions"],
                        validation_receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
                        published_at=dataset.created_at, generation_task_id=dataset.generation_task_id,
                        generation_run_id=run_id)
                    (data / f"datasets/manifests/{dataset.dataset_manifest_id}.json").write_bytes(canonical_manifest_bytes(wrong))
                    self.assertTrue(publish.inspect_canonical_root(data, dataset.dataset_manifest_id)["complete"])
                    before = inventory(data)
                    with self.assertRaisesRegex(Exception, "CANONICAL_TARGET_CONFLICT"):
                        repair_live_corpus_manifests(data_root=data)
                    self.assertEqual(inventory(data), before)
                    self.assertEqual(compute_market_epoch_for_data_root(ROOT, data)[0], self.epoch)

    def test_composition_content_changes_metadata_identity(self):
        old = publish._load_dataset_manifest(self.data, self.old)
        cohorts = load_live_corpus_lineage(self.data)["cohorts"]
        schema = logical.live_corpus_schema_sha256()
        first = publish.repair_dataset_version(old.dataset_version, schema, cohorts)
        changed = copy.deepcopy(cohorts)
        changed[0]["content_sha256"] = "f" * 64
        second = publish.repair_dataset_version(old.dataset_version, schema, changed)
        self.assertNotEqual(first, second)

    def test_candidate_clock_corruption_blocks_switch_and_has_typed_cli_stop(self):
        def tamper():
            candidate = next(p for p in self.data.glob("datasets/manifests/*.publication-clock.json")
                             if p.name not in {Path(path).name for path in self.before})
            candidate.write_text(json.dumps({"created_at": "2099-01-01T00:00:00.000000Z",
                "first_reliable_available_at": "2099-01-01T00:00:00.000000Z"}), encoding="utf-8")
        with self.assertRaisesRegex(Exception, "CANDIDATE_VERIFICATION_FAILED"):
            self.repair(fault_before_visibility=tamper)
        self.assert_old_visible()

        candidate = next(p for p in self.data.glob("datasets/manifests/*.publication-clock.json")
                         if p.name not in {Path(path).name for path in self.before})
        candidate.write_text(json.dumps({"created_at": "not-a-time",
            "first_reliable_available_at": "not-a-time"}), encoding="utf-8")
        result = subprocess.run([sys.executable, "-X", "utf8", "-B",
            str(ROOT / "scripts/discovery_evidence_release.py"), "repair-live-corpus-manifests",
            "--data-root", str(self.data)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["code"], "PUBLICATION_CLOCK_CORRUPT")
        self.assertNotIn("Traceback", result.stderr)
        self.assert_old_visible()

    def test_wrong_noncurrent_logical_group_cannot_poison_current_market(self):
        def tamper():
            candidate = next(p for p in self.data.glob("datasets/manifests/*.labels.json")
                             if p.name not in {Path(path).name for path in self.before})
            payload = json.loads(candidate.read_bytes())
            payload["logical_dataset_id"] = "SCRATCH-DIFFERENT-GROUP"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(Exception, "CANDIDATE_VERIFICATION_FAILED"):
            self.repair(fault_before_visibility=tamper)
        self.assert_old_visible()
        rows, warnings = enumerate_rdp_datasets(self.data)
        self.assertEqual(warnings, [])
        self.assertEqual([row["dataset_manifest_id"] for row in select_current_datasets_for_forge(rows)], [self.old])
        self.assertEqual(build_forge_input_receipt(self.data, repo_root=ROOT)["active_evidence_set"]["current_dataset_manifest_id"], self.old)

    def test_corrupt_uncommitted_labels_cannot_poison_current_market(self):
        def tamper():
            candidate = next(p for p in self.data.glob("datasets/manifests/*.labels.json")
                             if p.name not in {Path(path).name for path in self.before})
            candidate.write_bytes(b"{scratch broken candidate labels")
        with self.assertRaisesRegex(Exception, "CANDIDATE_VERIFICATION_FAILED"):
            self.repair(fault_before_visibility=tamper)
        self.assert_old_visible()
        before_retry = inventory(self.data)
        result = subprocess.run([sys.executable, "-X", "utf8", "-B",
            str(ROOT / "scripts/discovery_evidence_release.py"), "repair-live-corpus-manifests",
            "--data-root", str(self.data)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["code"], "CANONICAL_TARGET_CONFLICT")
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(inventory(self.data), before_retry)

    def test_reused_marker_corruption_blocks_switch_and_invalid_current_blocks_consumers(self):
        first = self.repair()
        schema_c = {**logical.live_corpus_schema_projection(), "metadata_contract": "scratch-C"}
        with patch.object(logical, "live_corpus_schema_projection", return_value=schema_c):
            middle = self.repair()
        old_lineage = (self.data / "datasets/live_lifecycle_corpus/lineage.json").read_bytes()
        def tamper():
            marker = self.data / "datasets/manifests" / f"{first['dataset_manifest_id']}.published"
            payload = json.loads(marker.read_bytes())
            payload["corpus_version"] = 999
            payload["release_id"] = "wrong"
            marker.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(Exception, "CANDIDATE_VERIFICATION_FAILED"):
            self.repair(fault_before_visibility=tamper)
        self.assertEqual((self.data / "datasets/live_lifecycle_corpus/lineage.json").read_bytes(), old_lineage)
        clock = self.data / "datasets/manifests" / f"{middle['dataset_manifest_id']}.publication-clock.json"
        clock.unlink()
        from solana_alpha_lab.factory.hfic_evidence_identity import EvidenceIdentityError
        with self.assertRaisesRegex(EvidenceIdentityError, "MARKET_EVIDENCE_BASIS_INCOMPLETE"):
            compute_market_epoch_for_data_root(ROOT, self.data)


if __name__ == "__main__":
    unittest.main()
