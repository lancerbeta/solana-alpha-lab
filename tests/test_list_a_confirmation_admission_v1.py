"""Pre-values counterexamples and exact reservation continuity."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pyarrow.parquet as pq

from solana_alpha_lab.factory.capabilities import execute_capability
from solana_alpha_lab.factory.experiment_spec import validate_experiment_document, ExperimentSpecError
from solana_alpha_lab.factory.list_a_confirmation import current_context, read_confirmation
from solana_alpha_lab.factory.list_a_confirmation_inputs import (
    ConfirmationError, inspect_confirmation, prepare_confirmation, authorize_confirmation, records, event,
)
from solana_alpha_lab.factory.list_a_confirmation_method import finite_bytes, digest
from solana_alpha_lab.factory.research_store import ResearchStore, RecordKind
from tests.test_list_a_confirmation_vertical_v1 import ROOT, bound, ValueReader
from tests.fixtures.list_a_confirmation_v1.native import NOW


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="list-a-unit-")
        self.addCleanup(self.tmp.cleanup)
        self.store = ResearchStore(Path(self.tmp.name) / "plane")
        self.spec, self.p, _ = bound(self.store)
        self.sample = "confirmation/sources/SYNTH-LIST-A-V1/sample.json"
        self.ctx = {"binding_id": self.p["binding_id"], "data_root": self.store.root, "now": NOW}

    def execute(self, phase=None):
        return execute_capability(self.spec, root=ROOT, capture_hooks={"execution_context": self.ctx, "phase": phase})

    def mutate_sample(self, mutate):
        path = self.store.root / self.sample
        document = json.loads(path.read_bytes())
        mutate(document)
        path.write_bytes(finite_bytes(document))

    def test_closed_definition_unknown_version_and_outcome(self):
        for mutate in (lambda s: s.update(extra=True), lambda s: s.update(schema_version="1.6"),
                       lambda s: s["required_outcomes"][0].update(role="EXPLORATORY"),
                       lambda s: s["parameters"].update(estimator="MEAN_CLUSTER_MEANS")):
            spec = copy.deepcopy(self.spec)
            mutate(spec)
            with self.assertRaises(ExperimentSpecError):
                validate_experiment_document(spec, root=ROOT)

    def test_metadata_refusals_do_not_decode_observations_or_charge(self):
        original = (self.store.root / self.sample).read_bytes()
        variants = [
            (lambda s: s.update(role="EXPLORATORY_REUSE"), "CONFIRMATORY_REUSE_FORBIDDEN"),
            (lambda s: s["exposure"].update(confirmatory_reuse_forbidden=True), "CONFIRMATORY_REUSE_FORBIDDEN"),
            (lambda s: s["exposure"].update(inventory_complete=False), "EXPOSURE_INVENTORY_INCOMPLETE"),
            (lambda s: s["exposure"].update(preregistered_at=s["information_start"]), "CHRONOLOGY_INVALID"),
            (lambda s: s.update(census_rel="../foreign.parquet"), "SOURCE_AUTHORITY_UNBOUND"),
            (lambda s: s.update(unexpected_target_counts={"A": 120}), "INPUT_CONTRACT_INVALID"),
        ]
        reader = ValueReader(self.store)
        for mutate, reason in variants:
            with self.subTest(reason=reason):
                (self.store.root / self.sample).write_bytes(original)
                self.mutate_sample(mutate)
                with patch.object(pq, "read_table", reader.read), self.assertRaisesRegex(ConfirmationError, reason):
                    inspect_confirmation(self.spec, self.sample, root=ROOT, data_root=self.store.root, now=NOW)
        self.assertEqual(reader.reads, [])
        self.assertFalse(any(r["payload"].get("scientific_charge") == 1 for r in records(self.store)))

    def test_exact_grant_phrase_no_approved_flag(self):
        with self.assertRaisesRegex(ConfirmationError, "EXACT_GRANT_PHRASE_REQUIRED"):
            authorize_confirmation(self.spec, self.p["binding_id"], root=ROOT, store=self.store, now=NOW,
                valid_until="2027-02-01T00:00:00Z", owner_phrase="approved:true")

    def test_current_protection_revoke_is_independent(self):
        txn = "RESEARCH-TXN-LA-TEST-REVOKE"
        self.store.append([event(ROOT, record_id="LA-PROTECTION-TEST-REVOKE", kind=RecordKind.RESEARCH_ARTIFACT,
            transaction_id=txn, payload={"type": "PROTECTION", "source_id": "SYNTH-LIST-A-V1", "status": "DENY"})], transaction_id=txn)
        reader = ValueReader(self.store)
        with patch.object(pq, "read_table", reader.read), self.assertRaisesRegex(ConfirmationError, "CURRENT_PROTECTION_DENY"):
            self.execute()
        self.assertEqual(reader.reads, [])
        self.assertFalse(any(r["kind"] == "RUN_STARTED" for r in records(self.store)))

    def test_committed_reservation_crash_then_exact_resume_no_second_charge(self):
        def fail(phase):
            if phase == "AFTER_RESERVATION":
                raise RuntimeError("CONTROLLED_PRE_VALUE_CRASH")
        reader = ValueReader(self.store)
        with patch.object(pq, "read_table", reader.read), self.assertRaisesRegex(RuntimeError, "CONTROLLED"):
            self.execute(fail)
        self.assertEqual(reader.reads, [])
        ctx = current_context(self.spec, self.p["binding_id"], root=ROOT, store=self.store, now=NOW)
        saved = read_confirmation(self.store, trial_id=ctx["trial_id"], root=ROOT)
        self.assertEqual(saved["status"], "INTERRUPTED")
        self.assertEqual(saved["scientific_charge"], 1)
        result = self.execute()
        self.assertEqual(result["scientific_charge"], 1)
        reservations = [r for r in records(self.store) if r["kind"] == "RESEARCH_ARTIFACT" and r["payload"].get("type") == "CONFIRMATION_RESERVATION"]
        self.assertEqual(len(reservations), 1)

    def test_chronology_development_equality_is_denied(self):
        from solana_alpha_lab.factory.list_a_confirmation_inputs import Sample, validate_exposure
        sample = json.loads((self.store.root / self.sample).read_bytes())
        sample["exposure"].update(empirical_development=True,
            development_decision_max="2026-11-01T19:50:00Z", development_target_available_max="2026-11-02T00:00:00Z")
        with self.assertRaisesRegex(ConfirmationError, "CHRONOLOGY_INFORMATION_OVERLAP"):
            validate_exposure(Sample.model_validate(sample))

    def test_native_global_protection_deny_and_incomplete_before_values(self):
        path = self.store.root / "protection/assignments/SYNTHETIC-NATIVE-CAPTURE.json"
        document = json.loads(path.read_bytes())
        mint = pq.read_table(self.store.root / "confirmation/sources/SYNTH-LIST-A-V1/census.parquet", columns=["mint"]).to_pylist()[0]["mint"]
        document["entries"] = [{"identity_kind": "MINT", "identity": mint, "role": "REVOKED", "scope": {"kind": "ALL_TIME"}}]
        path.write_bytes(finite_bytes(document))
        reader = ValueReader(self.store)
        with patch.object(pq, "read_table", reader.read), self.assertRaisesRegex(ConfirmationError, "CURRENT_NATIVE_PROTECTION_DENY"):
            self.execute()
        document["completeness"]["complete"] = False
        path.write_bytes(finite_bytes(document))
        with patch.object(pq, "read_table", reader.read), self.assertRaisesRegex(ConfirmationError, "CURRENT_NATIVE_PROTECTION_UNRESOLVED"):
            self.execute()
        self.assertEqual(reader.reads, [])

    def test_renamed_source_cannot_reset_reserved_acquisition(self):
        def fail(phase):
            if phase == "AFTER_RESERVATION":
                raise RuntimeError("CONTROLLED_PRE_VALUE_CRASH")
        with self.assertRaises(RuntimeError):
            self.execute(fail)
        spec, renamed, _ = bound(self.store, source_id="SYNTH-RENAMED-SAME-ACQUISITION", origin_label="SYNTH-LIST-A-V1")
        reader = ValueReader(self.store)
        with patch.object(pq, "read_table", reader.read), self.assertRaisesRegex(ConfirmationError, "SCIENTIFIC_ALLOWANCE_EXHAUSTED"):
            execute_capability(spec, root=ROOT, capture_hooks={"execution_context": {
                "data_root": self.store.root, "binding_id": renamed["binding_id"], "now": NOW}})
        self.assertEqual(reader.reads, [])
        self.assertEqual(sum(r["kind"] == "RUN_STARTED" for r in records(self.store)), 1)

    def test_native_witness_rejects_census_clock_alias(self):
        import pyarrow as pa
        from solana_alpha_lab.factory.list_a_confirmation_inputs import Sample, source_metadata, file_sha
        sample = Sample.model_validate(json.loads((self.store.root / self.sample).read_bytes()))
        rows = pq.read_table(self.store.root / sample.census_rel).to_pylist()
        rows[0]["admission_request_started_at"] = "2026-11-02T00:14:58Z"
        relative = "confirmation/census-clock-alias.parquet"
        pq.write_table(pa.Table.from_pylist(rows), self.store.root / relative)
        hashes = {k:v for k,v in sample.source_hashes.items() if k != sample.census_rel}
        hashes[relative] = file_sha(self.store.root / relative)
        alias = sample.model_copy(update={"census_rel":relative,"source_hashes":hashes})
        with self.assertRaisesRegex(ConfirmationError, "NATIVE_ADMISSION_CLOCK_CONFLICT"):
            source_metadata(alias,root=ROOT,data_root=self.store.root)

    def test_exact_grant_structure_before_values(self):
        from solana_alpha_lab.factory.list_a_confirmation_inputs import validate_exact_grant, load_json
        record = next(r for r in records(self.store) if r["payload"].get("type")=="CONFIRMATION_GRANT")
        binding = load_json(self.store.root / ("confirmation/bindings/"+self.p["binding_id"]+".json"))
        for mutate in (lambda r:r.update(producer="FOREIGN"),lambda r:r.update(kind="RUN_COMPLETED"),
                       lambda r:r["payload"].update(plane="HOST"),lambda r:r["payload"].update(request_sha256="0"*64),
                       lambda r:r["payload"].update(approved=True)):
            forged = copy.deepcopy(record)
            mutate(forged)
            with self.assertRaisesRegex(ConfirmationError,"EXACT_GRANT_INVALID"):
                validate_exact_grant(forged,binding,self.p["binding_id"])

    def test_post_admission_target_tail_protection(self):
        from solana_alpha_lab.factory.list_a_confirmation_inputs import Sample, source_metadata, purpose_protection
        from solana_alpha_lab.factory.opportunity_episodes import inventory_from_documents
        sample = Sample.model_validate(json.loads((self.store.root/self.sample).read_bytes()))
        sample = sample.model_copy(update={"interval_end_exclusive":"2027-01-03T02:00:01Z"})
        metadata = source_metadata(sample,root=ROOT,data_root=self.store.root)
        last = max(metadata["census"],key=lambda r:r["t0"])
        doc={"schema":"smial.protected-identity-assignment","schema_version":"1.0","assignment_id":"TAIL",
            "completeness":{"complete":True},"entries":[{"identity_kind":"MINT","identity":last["mint"],"role":"REVOKED",
                "scope":{"kind":"INTERVAL","start":sample.interval_end_exclusive,"end":"2027-01-04T00:00:00Z"}}]}
        inventory=inventory_from_documents([doc])
        for stage in ("FROZEN","CURRENT"):
            with self.assertRaisesRegex(ConfirmationError,stage+"_NATIVE_PROTECTION_DENY"):
                purpose_protection(sample,metadata,inventory,stage)
