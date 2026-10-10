"""Contract/readback regressions. Native producer proof lives in pinned replay."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory.experiment_evidence import compose_experiment_dossier, classify_record
from solana_alpha_lab.factory.experiment_spec import load_experiment_spec
from solana_alpha_lab.factory.lifecycle_projection import build_lifecycle_projection
from solana_alpha_lab.factory.operational_store import OperationalStore
from solana_alpha_lab.factory.run_passport import experiment_spec_sha256, validate_run_passport, RunPassportError
from solana_alpha_lab.factory.workbench import _dossier_html
from tests.test_experiment_evidence_decision_v1 import (
    EXPERIMENT_ID, HYPOTHESIS_ID, LOCATOR, _event, _eligible_run, _scientific_payload,
)
from tests.test_fast_lane_classifier import completed_run_payload


class ExecutionIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.projection = build_lifecycle_projection(ROOT, projected_at="2026-10-10T00:00:00Z")
        cls.spec = load_experiment_spec(ROOT, "configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml")
        cls.digest = experiment_spec_sha256(cls.spec)

    def dossier(self, records, status="AVAILABLE"):
        return compose_experiment_dossier(self.projection, LOCATOR, root=ROOT,
                                          records=records, records_status=status)

    def legacy(self, **changes):
        payload = completed_run_payload("RUN-LEGACY-EXACT-001", "c" * 64)
        payload.update(experiment_spec_sha256=self.digest, hypothesis_version_id=HYPOTHESIS_ID)
        payload.update(changes)
        return _event(record_id="RUN-LEGACY-ROW-001", record_kind="RUN_COMPLETED",
                      entity_id="RUN-LEGACY-EXACT-001", run_id="RUN-LEGACY-EXACT-001",
                      hypothesis_version_id=HYPOTHESIS_ID, payload=payload,
                      transaction_id="RESEARCH-TXN-LEGACY-EXACT-001")

    def test_valid_legacy_passport_exact_hash_and_forward_extra_identity(self):
        legacy = self.legacy()
        before = legacy.payload_json
        dossier = self.dossier((legacy,))
        self.assertEqual(dossier["planes"]["execution"], "COMPLETED")
        self.assertEqual(legacy.payload_json, before)
        self.assertFalse(dossier["science_guard"]["allowed"])
        forward = self.legacy(experiment_id=EXPERIMENT_ID)
        passport = validate_run_passport(json.loads(forward.payload_json))
        self.assertEqual(passport.model_dump(mode="json")["experiment_id"], EXPERIMENT_ID)
        bad = json.loads(forward.payload_json)
        bad["experiment_id"] = "bad id"
        with self.assertRaises(RunPassportError):
            validate_run_passport(bad)

    def test_explicit_foreign_identity_cannot_borrow_own_run_or_science(self):
        own = _eligible_run()
        foreign = _event(record_id="METRIC-FOREIGN-COLLISION-001", record_kind="EXPERIMENT_METRIC",
                         entity_id="METRIC-FOREIGN-COLLISION-001", run_id=own.run_id,
                         hypothesis_version_id=HYPOTHESIS_ID,
                         payload=_scientific_payload(experiment_id="EXP-FOREIGN-001"),
                         transaction_id="RESEARCH-TXN-FOREIGN-COLLISION-001")
        dossier = self.dossier((own, foreign))
        self.assertEqual(dossier["planes"]["execution"], "COMPLETED")
        self.assertNotIn(foreign.record_id, {c["record_id"] for c in dossier["direct_evidence"]})
        self.assertFalse(dossier["science_guard"]["allowed"])
        self.assertIsNone(classify_record(foreign, experiment_id=EXPERIMENT_ID,
                         hypothesis_version_id=HYPOTHESIS_ID,
                         direct_run_ids={own.run_id}, direct_trial_ids=set()))

    def test_changed_spec_conflicting_alias_and_unverified_legacy_are_unknown(self):
        for changes in ({"experiment_spec_sha256": "f" * 64},
                        {"experiment_id": EXPERIMENT_ID, "experiment_spec_id": "EXP-FOREIGN-001"},
                        {"run_id": "RUN-FOREIGN-001"},
                        {"runner_git_sha": "not-a-sha"}):
            with self.subTest(changes=changes):
                dossier = self.dossier((self.legacy(**changes),))
                self.assertEqual(dossier["planes"]["execution"], "UNKNOWN")
                self.assertTrue(dossier["execution_relation_gaps"])
                self.assertFalse(dossier["science_guard"]["allowed"])
                self.assertIn("принадлежность", _dossier_html(dossier))

    def test_run_payload_poison_is_not_scientific_evidence_and_version_invalidates_snapshot(self):
        payload = json.loads(self.legacy(experiment_id=EXPERIMENT_ID).payload_json)
        payload.update(_scientific_payload())
        poisoned = self.legacy(**payload)
        dossier = self.dossier((poisoned,))
        self.assertEqual(dossier["planes"]["execution"], "COMPLETED")
        self.assertFalse(dossier["science_guard"]["allowed"])
        self.assertIn("POPULATION_N", dossier["science_guard"]["blocked_codes"])
        mismatched = self.dossier((self.legacy(experiment_id=EXPERIMENT_ID,
                                             experiment_spec_sha256="f" * 64),))
        self.assertNotEqual(dossier["evidence_snapshot_sha256"], mismatched["evidence_snapshot_sha256"])

    def test_unavailable_is_unknown_absent_is_no_run(self):
        self.assertEqual(self.dossier((), "UNAVAILABLE")["planes"]["execution"], "UNKNOWN")
        self.assertEqual(self.dossier((), "NOT_PRESENT")["planes"]["execution"], "NO_RUN")


class CurrentReadTests(unittest.TestCase):
    def test_child_commit_barriers_old_snapshot_new_consumers_and_oracle_canary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            shutil.copytree(ROOT / "catalog/schemas", root / "catalog/schemas")
            (root / "configs").mkdir()
            shutil.copy(ROOT / "configs/owner_lifecycle_projection_v1.yaml", root / "configs")
            (root / "configs/factory_v1_product_kernel_v1.yaml").write_text(
                "operational_store:\n  relative_path: ops.sqlite\n", encoding="utf-8")
            script = """import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from solana_alpha_lab.factory.operational_store import OperationalStore
s=OperationalStore(Path(sys.argv[2]))
j=dict(job_id='JOB-WAL-FTC-001',experiment_id='EXP-WAL-FTC-001',spec_relative='configs/experiment_specs/a.yaml',spec_sha256='a'*64,status='RUNNING',blocker='',terminal=None,evidence={})
s.upsert_job(j);s._conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
print('RUNNING_COMMITTED',flush=True)
for line in sys.stdin:
    status=line.strip()
    if status=='EXIT': break
    s.upsert_job({**j,'status':status})
    print(status+'_COMMITTED',flush=True)
s.close()
"""
            child = subprocess.Popen([sys.executable, "-B", "-u", "-c", script,
                                      str(ROOT / "src"), str(root / "ops.sqlite")],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            reference = None
            try:
                self.assertEqual(child.stdout.readline().strip(), "RUNNING_COMMITTED")
                path = root / "ops.sqlite"
                reference = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
                reference.execute("BEGIN")
                self.assertEqual(reference.execute("SELECT status FROM jobs").fetchone()[0], "RUNNING")
                child.stdin.write("COMPLETE\n"); child.stdin.flush()
                self.assertEqual(child.stdout.readline().strip(), "COMPLETE_COMMITTED")
                self.assertIsNone(child.poll())
                self.assertEqual(reference.execute("SELECT status FROM jobs").fetchone()[0], "RUNNING")
                reference.rollback()
                self.assertEqual(reference.execute("SELECT status FROM jobs").fetchone()[0], "COMPLETE")
                stale = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
                try:
                    # A real wrong observer result, not assert-False: detects the old defect.
                    self.assertEqual(stale.execute("SELECT status FROM jobs").fetchone()[0], "RUNNING")
                finally:
                    stale.close()
                before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (path, Path(str(path) + "-wal"))}
                reader = OperationalStore(path, readonly=True)
                try:
                    self.assertEqual(reader.get_job("JOB-WAL-FTC-001")["status"], "COMPLETE")
                    with self.assertRaises(sqlite3.OperationalError):
                        reader._conn.execute("DELETE FROM jobs")
                    projection = build_lifecycle_projection(root, projected_at="2026-10-10T00:00:00Z")
                    entity = next(e for e in projection["entities"] if e["entity_id"] == "JOB-WAL-FTC-001")
                    self.assertEqual(entity["native_state"], "COMPLETE")
                    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (path, Path(str(path) + "-wal"))}
                    self.assertEqual(before, after)
                    child.stdin.write("RUNNING\n"); child.stdin.flush()
                    self.assertEqual(child.stdout.readline().strip(), "RUNNING_COMMITTED")
                    self.assertEqual(reader.get_job("JOB-WAL-FTC-001")["status"], "RUNNING")
                finally:
                    reader.close()
            finally:
                if reference:
                    reference.close()
                if child.poll() is None:
                    child.stdin.write("EXIT\n"); child.stdin.flush()
                _, error = child.communicate(timeout=15)
                self.assertEqual(child.returncode, 0, error)


if __name__ == "__main__":
    unittest.main()
