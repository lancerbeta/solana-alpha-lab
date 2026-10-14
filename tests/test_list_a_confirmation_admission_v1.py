"""Pre-values counterexamples and exact reservation continuity."""
from __future__ import annotations

import copy
import contextlib
import io
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
from scripts import list_a_confirmation as cli


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
        with patch.object(pq, "read_table", reader.read):
            self.assertEqual(renamed["status"], "ALREADY_RESERVED")
            self.assertEqual(renamed["scientific_charge"], 1)
            self.assertEqual(renamed["prior_scientific_checkpoint"]["execution_binding_sha256"], self.p["binding_id"])
            self.assertFalse((self.store.root / ("confirmation/bindings/" + renamed["binding_id"] + ".json")).exists())
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

    def test_native_bad_observations_keep_charge_and_never_complete(self):
        from tests.fixtures.list_a_confirmation_v1 import native
        original = native.write_native_confirmation_sample
        for variant, reason in (("foreign", "FOREIGN_OBSERVATION_IDENTITY"),
                                ("conflict", "OBSERVATION_CELL_CONFLICT"),
                                ("late", "OBSERVED_CLOCK_OR_VALUE_INVALID")):
            with self.subTest(variant=variant):
                def ingress(**kwargs):
                    rows = copy.deepcopy(kwargs["observations"])
                    if variant == "foreign":
                        rows[0]["episode_id"] = "FOREIGN-EPISODE"
                    elif variant == "conflict":
                        duplicate = copy.deepcopy(rows[0])
                        duplicate["typed_value"] = "10"
                        rows.append(duplicate)
                    else:
                        rows[0]["first_reliable_available_at"] = "2027-01-31T00:00:00Z"
                    return original(**{**kwargs, "observations": rows})
                with patch.object(native, "write_native_confirmation_sample", ingress):
                    spec, prepared, _ = bound(self.store, source_id="SYNTH-BAD-" + variant.upper())
                reader = ValueReader(self.store)
                with patch.object(pq, "read_table", reader.read), self.assertRaisesRegex(ConfirmationError, reason):
                    execute_capability(spec, root=ROOT, capture_hooks={"execution_context": {
                        "binding_id": prepared["binding_id"], "data_root": self.store.root, "now": NOW}})
                self.assertTrue(reader.reads)
                reservation = next(r["payload"] for r in records(self.store) if r["kind"] == "RUN_STARTED" and
                    r["payload"].get("execution_binding_sha256") == prepared["binding_id"])
                saved = read_confirmation(self.store, trial_id=reservation["trial_id"], root=ROOT)
                self.assertEqual(saved["status"], "INVALID_AFTER_RESERVE")
                self.assertEqual(saved["reason_codes"], [reason])
                self.assertEqual(saved["scientific_charge"], 1)
                self.assertFalse(any(r["kind"] == "RUN_COMPLETED" and r["payload"].get("trial_id") == reservation["trial_id"] for r in records(self.store)))

    def test_revoke_after_values_blocks_completion_without_new_charge(self):
        grant = next(r for r in records(self.store) if r["payload"].get("type") == "CONFIRMATION_GRANT")
        def revoke(phase):
            if phase == "AFTER_VALUES":
                txn = "RESEARCH-TXN-LA-AFTER-VALUES-REVOKE"
                self.store.append([event(ROOT, record_id="LA-AFTER-VALUES-REVOKE", kind=RecordKind.RESEARCH_ARTIFACT,
                    transaction_id=txn, payload={"type": "GRANT_REVOKED", "grant_id": grant["record_id"]})], transaction_id=txn)
        with self.assertRaisesRegex(ConfirmationError, "GRANT_REVOKED"):
            self.execute(revoke)
        reservation = next(r["payload"] for r in records(self.store) if r["kind"] == "RUN_STARTED")
        saved = read_confirmation(self.store, trial_id=reservation["trial_id"], root=ROOT)
        self.assertEqual(saved["status"], "INVALID_AFTER_RESERVE")
        self.assertEqual(saved["reason_codes"], ["GRANT_REVOKED"])
        self.assertEqual(saved["scientific_charge"], 1)
        self.assertFalse(any(r["kind"] == "RUN_COMPLETED" for r in records(self.store)))
        self.assertEqual(sum(r["kind"] == "RUN_STARTED" for r in records(self.store)), 1)

    def assert_cli_checkpoint(self, binding_id, charge, terminal, trial_id=None):
        reader = ValueReader(self.store)
        before = self.store.diagnostics().committed_inventory_sha256
        with patch.object(pq, "read_table", reader.read), patch(
                "solana_alpha_lab.factory.list_a_confirmation.calculate_list_a", side_effect=AssertionError("NO_EVALUATOR")), patch.object(
                ResearchStore, "append", side_effect=AssertionError("NO_WRITES")):
            for command in ("classify", "submit"):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = cli.main([command, "--data-root", str(self.store.root), "--binding-id", binding_id,
                                     "--as-of", "2027-01-04T00:00:00Z"])
                self.assertEqual(code, 0)
                response = json.loads(output.getvalue())
                checkpoint = response["confirmation_checkpoint"] if command == "classify" else response
                self.assertEqual(checkpoint["scientific_charge"], charge)
                self.assertEqual(checkpoint.get("trial_id"), trial_id)
                self.assertEqual(response["terminal" if command == "classify" else "status"], terminal)
        self.assertEqual(reader.reads, [])
        self.assertEqual(before, self.store.diagnostics().committed_inventory_sha256)

    def test_cli_revoke_retains_reserved_identity_charge_and_no_new_look(self):
        def fail(phase):
            if phase == "AFTER_RESERVATION":
                raise RuntimeError("CONTROLLED_PRE_VALUE_CRASH")
        with self.assertRaises(RuntimeError):
            self.execute(fail)
        reservation = next(r["payload"] for r in records(self.store) if r["kind"] == "RUN_STARTED")
        grant = next(r for r in records(self.store) if r["payload"].get("type") == "CONFIRMATION_GRANT")
        preview = self.cli_response("revoke", "--binding-id", self.p["binding_id"])
        self.assertEqual((preview["status"], preview["scientific_charge"]), ("REVOKE_REQUESTED", 1))
        revoked = self.cli_response("revoke", "--binding-id", self.p["binding_id"], "--owner-phrase", preview["owner_phrase"])
        self.assertEqual((revoked["status"], revoked["grant_id"], revoked["scientific_charge"]), ("REVOKED", grant["record_id"], 1))
        self.assert_cli_checkpoint(self.p["binding_id"], 1, "BLOCKED_AFTER_RESERVE", reservation["trial_id"])
        self.assert_cli_checkpoint("0" * 64, 0, "BLOCKED_BEFORE_RESERVE")
        with patch.object(ResearchStore, "iter_committed_records", side_effect=RuntimeError("UNAVAILABLE")):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(cli.main(["submit", "--data-root", str(self.store.root), "--binding-id", self.p["binding_id"]]), 2)
            self.assertIsNone(json.loads(output.getvalue())["scientific_charge"])

    def cli_response(self, command, *arguments, expected_code=0):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = cli.main([command, "--data-root", str(self.store.root), "--as-of", "2027-01-04T00:00:00Z", *arguments])
        self.assertEqual(code, expected_code)
        return json.loads(output.getvalue())

    def test_cli_revoke_exact_phrase_pre_values_and_idempotent(self):
        reader = ValueReader(self.store)
        before = self.store.diagnostics().committed_inventory_sha256
        with patch.object(pq, "read_table", reader.read):
            preview = self.cli_response("revoke", "--binding-id", self.p["binding_id"])
            self.assertEqual(before, self.store.diagnostics().committed_inventory_sha256)
            refused = self.cli_response("revoke", "--binding-id", self.p["binding_id"], "--owner-phrase", "approved:true", expected_code=2)
            self.assertEqual(refused["reason_codes"], ["EXACT_REVOKE_PHRASE_REQUIRED"])
            self.assertEqual(before, self.store.diagnostics().committed_inventory_sha256)
            revoked = self.cli_response("revoke", "--binding-id", self.p["binding_id"], "--owner-phrase", preview["owner_phrase"])
            self.assertEqual((revoked["status"], revoked["scientific_charge"]), ("REVOKED", 0))
            after = self.store.diagnostics().committed_inventory_sha256
            with patch.object(ResearchStore, "append", side_effect=AssertionError("REVOKE_REPEAT_NO_WRITE")):
                repeated = self.cli_response("revoke", "--binding-id", self.p["binding_id"], "--owner-phrase", preview["owner_phrase"])
            self.assertEqual(repeated["status"], "REVOKED")
            self.assertEqual(after, self.store.diagnostics().committed_inventory_sha256)
        self.assertEqual(reader.reads, [])
        self.assert_cli_checkpoint(self.p["binding_id"], 0, "BLOCKED_BEFORE_RESERVE")

    def test_native_numeric_refusals_are_terminal_with_consumed_charge(self):
        from tests.fixtures.list_a_confirmation_v1 import native
        original = native.write_native_confirmation_sample
        for reason, decision, target in (("TEMPORAL_TARGET_NONFINITE", "1e-308", "1e308"),
                ("TEMPORAL_TARGET_UNREPRESENTABLE", "1", "1." + "0" * 399 + "1")):
            with self.subTest(reason=reason):
                def ingress(**kwargs):
                    rows = copy.deepcopy(kwargs["observations"])
                    for row in rows:
                        row["typed_value"] = decision if row["point_id"] == "E1800" else target
                    return original(**{**kwargs, "observations": rows})
                with patch.object(native, "write_native_confirmation_sample", ingress):
                    spec, prepared, _ = bound(self.store, source_id="SYNTH-" + reason.replace("_", "-"))
                with patch("solana_alpha_lab.factory.list_a_confirmation.calculate_list_a", side_effect=AssertionError("NO_BOOTSTRAP")), self.assertRaisesRegex(
                        ConfirmationError, reason):
                    execute_capability(spec, root=ROOT, capture_hooks={"execution_context": {
                        "binding_id": prepared["binding_id"], "data_root": self.store.root, "now": NOW}})
                reservation = next(r["payload"] for r in records(self.store) if r["kind"] == "RUN_STARTED" and
                    r["payload"].get("execution_binding_sha256") == prepared["binding_id"])
                saved = read_confirmation(self.store, trial_id=reservation["trial_id"], root=ROOT)
                self.assertEqual((saved["status"], saved["scientific_charge"], saved["reason_codes"]),
                                 ("INVALID_AFTER_RESERVE", 1, [reason]))
                self.assert_cli_checkpoint(prepared["binding_id"], 1, "BLOCKED_AFTER_RESERVE", reservation["trial_id"])
                reader = ValueReader(self.store)
                before = self.store.diagnostics().committed_inventory_sha256
                with patch.object(pq, "read_table", reader.read), patch.object(ResearchStore, "append", side_effect=AssertionError("NO_REOPEN")):
                    for command, arguments in (("prepare", ["--sample-ref", "confirmation/sources/SYNTH-" + reason.replace("_", "-") + "/sample.json"]),
                            ("authorize", ["--binding-id", prepared["binding_id"], "--valid-until", "2027-02-01T00:00:00Z",
                                "--owner-phrase", "AUTHORIZE SYNTHETIC LIST A " + prepared["request_sha256"]])):
                        repeated = self.cli_response(command, *arguments)
                        self.assertEqual((repeated["status"], repeated["scientific_charge"]), ("ALREADY_RESERVED", 1))
                        self.assertEqual(repeated["prior_scientific_checkpoint"]["trial_id"], reservation["trial_id"])
                self.assertEqual(reader.reads, [])
                self.assertEqual(before, self.store.diagnostics().committed_inventory_sha256)
                self.assertFalse(any(r["kind"] == "RUN_COMPLETED" for r in records(self.store)))
