from __future__ import annotations

import copy
import hashlib
import json
import re
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from solana_alpha_lab.task22_dataset_split import (
    ACCEPTANCE_PATH,
    LEDGER_PATH,
    LEDGER_SCHEMA_PATH,
    SPLIT_PATH,
    SPLIT_SCHEMA_PATH,
    SPEC_PATH,
    SPEC_SHA256,
    Task22SplitError,
    append_consumption_event,
    artifact_bytes,
    build_all,
    canonical_json_bytes,
    load_json,
    sha256_bytes,
    validate_append_only_extension,
)


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task22DeterministicSplitAndLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest, cls.ledger, cls.acceptance = build_all(ROOT)
        cls.actual_manifest = load_json(ROOT / SPLIT_PATH)
        cls.actual_ledger = load_json(ROOT / LEDGER_PATH)
        cls.actual_acceptance = load_json(ROOT / ACCEPTANCE_PATH)

    def test_a2_spec_and_frozen_inputs_are_exact(self) -> None:
        self.assertEqual(sha256(ROOT / SPEC_PATH), SPEC_SHA256)
        self.assertEqual(
            self.manifest["content_addressing"]["dataset_inventory_sha256"],
            "aaa605eabdb62c38d218b40e768669db460c6fa419c4086d5412547b7f2fffae",
        )

    def test_generated_artifacts_are_exact_deterministic_rebuilds(self) -> None:
        self.assertEqual(artifact_bytes(self.manifest), (ROOT / SPLIT_PATH).read_bytes())
        self.assertEqual(artifact_bytes(self.ledger), (ROOT / LEDGER_PATH).read_bytes())
        self.assertEqual(
            artifact_bytes(self.acceptance),
            (ROOT / ACCEPTANCE_PATH).read_bytes(),
        )

    def test_manifest_and_ledger_validate_against_additive_schemas(self) -> None:
        for instance, schema_path in (
            (self.manifest, SPLIT_SCHEMA_PATH),
            (self.ledger, LEDGER_SCHEMA_PATH),
        ):
            schema = load_json(ROOT / schema_path)
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(
                schema,
                format_checker=FormatChecker(),
            ).validate(instance)

    def test_split_identity_is_content_addressed(self) -> None:
        addressing = self.manifest["content_addressing"]
        self.assertEqual(
            addressing["split_content_sha256"],
            sha256_bytes(canonical_json_bytes(addressing["identity_payload"])),
        )
        self.assertEqual(
            self.ledger["split_binding"]["sha256"],
            sha256_bytes(artifact_bytes(self.manifest)),
        )
        self.assertEqual(
            self.ledger["split_binding"]["split_content_sha256"],
            addressing["split_content_sha256"],
        )

    def test_roles_preserve_groups_and_do_not_invent_validation(self) -> None:
        roles = self.manifest["roles"]
        self.assertEqual(roles["development"]["batch_id"], "T21-R2")
        self.assertEqual(roles["development"]["member_count"], 3)
        self.assertEqual(roles["validation"], {
            "state": "NONE",
            "batch_id": None,
            "member_ids": [],
        })
        self.assertEqual(roles["holdout"]["state"], "UNASSIGNED_UNOPENED")
        self.assertEqual(roles["holdout"]["access"], "DENY")
        self.assertEqual(roles["holdout_candidate"]["batch_id"], "T21-R3")
        self.assertEqual(roles["holdout_candidate"]["member_count"], 2)
        self.assertTrue(
            set(roles["development"]["member_ids"]).isdisjoint(
                roles["holdout_candidate"]["member_ids"]
            )
        )

    def test_missing_time_contract_fails_closed_to_extend_evidence(self) -> None:
        self.assertEqual(self.manifest["owner_verdict"], "EXTEND_EVIDENCE")
        self.assertEqual(
            self.manifest["chronology"]["source_start_gap_seconds"],
            6797.239863,
        )
        self.assertFalse(
            self.manifest["chronology"]["consumer_time_contract_present"]
        )
        self.assertEqual(self.manifest["chronology"]["purge_status"], "NOT_COMPUTABLE")
        self.assertIn(
            "SOURCE_START_GAP_LT_MAX_PROJECT_HORIZON",
            self.manifest["reason_codes"],
        )

    def test_outcomes_remain_sealed_and_access_is_denied(self) -> None:
        self.assertEqual(self.manifest["outcome_seal"]["state"], "UNOPENED")
        self.assertFalse(self.manifest["outcome_seal"]["outcome_values_read"])
        self.assertEqual(self.manifest["outcome_seal"]["outcome_paths_opened"], [])
        self.assertFalse(self.manifest["outcome_seal"]["analysis_access_allowed"])
        self.assertEqual(self.ledger["state"]["current"], "UNASSIGNED_UNOPENED")
        self.assertEqual(self.ledger["records"], [])

    def test_companion_event_projects_to_unchanged_base_registry_schema(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        ledger["state"]["current"] = "UNTOUCHED"
        event = self._sample_event()
        next_ledger = append_consumption_event(
            ledger=ledger,
            event=event,
            prior_ledger_sha256=sha256_bytes(artifact_bytes(ledger)),
        )
        validate_append_only_extension(previous=ledger, current=next_ledger)
        extension_schema = load_json(ROOT / LEDGER_SCHEMA_PATH)
        Draft202012Validator(extension_schema).validate(next_ledger)

        base_registry = {
            "schema_version": "1.0",
            "registry_id": "SMIAL-REGISTRY-HOLDOUT-CONSUMPTION",
            "registry_type": "holdout_consumption",
            "as_of": "2026-08-01",
            "truth_owner": "TASK-03",
            "source_asset_ids": [],
            "records": [event["base_registry_record"]],
        }
        lifecycle_schema = load_json(
            ROOT / "catalog/schemas/lifecycle_registry.schema.json"
        )
        Draft202012Validator(
            lifecycle_schema,
            format_checker=FormatChecker(),
        ).validate(base_registry)

    def test_append_only_guard_rejects_history_mutation_and_reset(self) -> None:
        ledger = copy.deepcopy(self.ledger)
        ledger["state"]["current"] = "UNTOUCHED"
        next_ledger = append_consumption_event(
            ledger=ledger,
            event=self._sample_event(),
            prior_ledger_sha256=sha256_bytes(artifact_bytes(ledger)),
        )
        mutated = copy.deepcopy(next_ledger)
        mutated["records"][0]["access_receipt"]["reason"] = "changed history"
        with self.assertRaisesRegex(Task22SplitError, "historical_ledger_record_mutation"):
            validate_append_only_extension(previous=next_ledger, current={
                **mutated,
                "ledger_version": next_ledger["ledger_version"] + 1,
                "previous_ledger_sha256": sha256_bytes(artifact_bytes(next_ledger)),
                "records": mutated["records"] + [self._sample_event(sequence=2)],
            })
        with self.assertRaisesRegex(Task22SplitError, "holdout_not_untouched"):
            append_consumption_event(
                ledger=next_ledger,
                event=self._sample_event(sequence=2),
                prior_ledger_sha256=sha256_bytes(artifact_bytes(next_ledger)),
            )

    def test_acceptance_records_exact_authority_and_no_catalog_promotion(self) -> None:
        self.assertEqual(self.acceptance["status"], "PASS_EXTEND_EVIDENCE")
        self.assertEqual(self.acceptance["owner_verdict"], "EXTEND_EVIDENCE")
        self.assertEqual(
            self.acceptance["acceptance"]["catalog_registration"],
            "DEFERRED_T22_A4",
        )
        authority = self.acceptance["authority"]
        self.assertEqual(authority["managed_file_count"], 8)
        for field in (
            "network_calls",
            "provider_api_rpc_wss_calls",
            "drive_reads",
            "drive_writes",
            "credential_use",
            "outcome_reads",
            "raw_or_dataset_writes",
            "cash_spend_usd_cents",
            "dependency_changes",
            "wallet_signer_transaction_actions",
        ):
            with self.subTest(field=field):
                self.assertEqual(authority[field], 0)

    def test_authored_files_are_sanitized(self) -> None:
        paths = [
            ROOT / SPLIT_SCHEMA_PATH,
            ROOT / LEDGER_SCHEMA_PATH,
            ROOT / "src/solana_alpha_lab/task22_dataset_split.py",
            ROOT / "scripts/build_task22_dataset_split.py",
            ROOT / SPLIT_PATH,
            ROOT / LEDGER_PATH,
            ROOT / ACCEPTANCE_PATH,
            Path(__file__),
        ]
        prohibited = {
            "windows_absolute_path": re.compile(r"(?i)\\b[a-z]:[\\\\/]"),
            "user_home_path": re.compile(r"(?i)/(?:users|home)/[^/\\s]+"),
            "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        }
        for path in paths:
            with self.subTest(path=path.as_posix()):
                value = path.read_bytes()
                self.assertFalse(value.startswith(b"\xef\xbb\xbf"))
                self.assertNotIn(b"\r", value)
                self.assertTrue(value.endswith(b"\n"))
                text = value.decode("utf-8")
                self.assertTrue(all(line.rstrip(" \t") == line for line in text.splitlines()))
                for pattern in prohibited.values():
                    self.assertIsNone(pattern.search(text))

    @staticmethod
    def _sample_event(sequence: int = 1) -> dict[str, object]:
        timestamp = "2026-08-01T15:00:00Z"
        return {
            "event_sequence": sequence,
            "prior_state": "UNTOUCHED",
            "resulting_state": "CONSUMED",
            "base_registry_record": {
                "record_kind": "holdout_consumption",
                "record_id": "HOLDOUT-CONSUMPTION-T22-001",
                "status": "RECORDED",
                "created_at": timestamp,
                "evidence_asset_ids": ["DATA-T22-SPLIT-MANIFEST-001"],
                "research_cycle_id": "RESEARCH-CYCLE-T22-001",
                "consumed_at": timestamp,
            },
            "access_receipt": {
                "split_id": "T22-SPLIT-T21-FROZEN-001",
                "dataset_inventory_sha256": "a" * 64,
                "holdout_partition_sha256": "b" * 64,
                "hypothesis_id": "HYPOTHESIS-T22-001",
                "hypothesis_version": "1.0",
                "trial_id": "TRIAL-T22-001",
                "actor_id": "ACTOR-LOCAL-WORK-001",
                "opened_at": timestamp,
                "reason": "approved outcome evaluation",
                "exact_query_or_code_sha256": "c" * 64,
                "decision_receipt_id": "DECISION-T22-001",
                "outcome_paths_opened": ["sealed/outcomes.parquet"],
            },
        }


if __name__ == "__main__":
    unittest.main()
