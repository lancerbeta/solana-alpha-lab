from __future__ import annotations

import copy
import hashlib
import re
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from solana_alpha_lab.task22_split_resolution import (
    LEDGER_PATH,
    PROFILE_PATH,
    SCHEMA_PATH,
    SPLIT_PATH,
    Task22ResolutionError,
    _resolve,
    artifact_bytes,
    build_all,
    canonical_json_bytes,
    load_json,
    load_yaml,
    sha256_bytes,
    validate_inputs,
)


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task22ConsumerTimeProfileResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = load_yaml(ROOT / PROFILE_PATH)
        cls.manifest, cls.ledger = build_all(ROOT)
        cls.actual_manifest = load_json(ROOT / SPLIT_PATH)
        cls.actual_ledger = load_json(ROOT / LEDGER_PATH)

    def test_frozen_metadata_inputs_are_exact_and_outcome_blind(self) -> None:
        validate_inputs(ROOT, self.profile)
        self.assertEqual(
            self.profile["accepted_baseline"]["a4_receipt"]["sha256"],
            "23e11802e9239f3f97b9395f28beffc190e85dcad2c51c7403a875077accd7c3",
        )
        self.assertEqual(len(self.profile["frozen_timing_inputs"]), 6)
        self.assertEqual(self.profile["authority"]["outcome_reads"], 0)

    def test_generated_artifacts_are_exact_deterministic_rebuilds(self) -> None:
        self.assertEqual(
            artifact_bytes(self.manifest),
            (ROOT / SPLIT_PATH).read_bytes(),
        )
        self.assertEqual(
            artifact_bytes(self.ledger),
            (ROOT / LEDGER_PATH).read_bytes(),
        )

    def test_outputs_validate_against_additive_schema(self) -> None:
        schema = load_json(ROOT / SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        )
        validator.validate(self.manifest)
        validator.validate(self.ledger)

    def test_consumer_profile_uses_actual_time_not_nominal_labels(self) -> None:
        consumer = self.manifest["consumer_profile"]
        self.assertEqual(consumer["feature_max_lookback_seconds"], 0)
        self.assertEqual(consumer["label_horizon_seconds"], 5400)
        self.assertEqual(
            consumer["elapsed_time_semantics"],
            "ACTUAL_EVENT_TIMESTAMPS_NEVER_NOMINAL_PANEL_LABELS",
        )
        self.assertFalse(consumer["exact_horizon_claims_allowed"])
        self.assertIn(
            "EXACT_15_MINUTE_OUTCOME",
            self.manifest["claim_boundary"]["forbidden"],
        )
        self.assertIn(
            "EXACT_60_MINUTE_OUTCOME",
            self.manifest["claim_boundary"]["forbidden"],
        )

    def test_temporal_resolution_has_a_real_embargo_and_no_purge(self) -> None:
        temporal = self.manifest["temporal_resolution"]
        self.assertEqual(
            temporal["development_label_available_at"],
            "2026-08-01T13:11:54.057142Z",
        )
        self.assertEqual(
            temporal["holdout_selection_at"],
            "2026-08-01T13:40:15.363386Z",
        )
        self.assertEqual(temporal["pre_embargo_gap_seconds"], 1701.306244)
        self.assertEqual(temporal["required_embargo_seconds"], 900)
        self.assertAlmostEqual(
            temporal["post_embargo_slack_seconds"],
            801.306244,
            places=6,
        )
        self.assertEqual(temporal["purged_development_members"], [])
        self.assertTrue(temporal["actual_timestamps_used"])
        self.assertFalse(temporal["source_start_gap_alone_used"])

    def test_group_roles_are_resolved_without_inventing_validation(self) -> None:
        roles = self.manifest["roles"]
        self.assertEqual(roles["development"]["batch_id"], "T21-R2")
        self.assertEqual(roles["development"]["state"], "ASSIGNED")
        self.assertEqual(
            roles["validation"],
            {"state": "NONE", "batch_id": None, "member_ids": []},
        )
        self.assertEqual(roles["holdout"]["batch_id"], "T21-R3")
        self.assertEqual(roles["holdout"]["state"], "UNTOUCHED")
        self.assertEqual(roles["holdout"]["access"], "DENY")
        self.assertTrue(
            set(roles["development"]["member_ids"]).isdisjoint(
                roles["holdout"]["member_ids"]
            )
        )

    def test_split_and_ledger_are_content_addressed_and_append_only(self) -> None:
        addressing = self.manifest["content_addressing"]
        self.assertEqual(
            addressing["split_content_sha256"],
            sha256_bytes(canonical_json_bytes(addressing["identity_payload"])),
        )
        self.assertEqual(
            self.ledger["split_binding"]["sha256"],
            sha256_bytes(artifact_bytes(self.manifest)),
        )
        self.assertEqual(self.ledger["ledger_version"], 2)
        self.assertEqual(
            self.ledger["previous_ledger"]["sha256"],
            "d21bf93227cf77895a29d1f6e02559c1ac94c40d803e4dd073003e7ce5d0ddfd",
        )
        receipt = self.ledger["assignment_receipt"]
        self.assertEqual(receipt["prior_state"], "UNASSIGNED_UNOPENED")
        self.assertEqual(receipt["resulting_state"], "UNTOUCHED")
        self.assertFalse(receipt["outcome_values_read"])
        self.assertEqual(self.ledger["records"], [])

    def test_outcomes_and_external_authority_remain_zero(self) -> None:
        self.assertEqual(self.manifest["outcome_seal"]["state"], "UNOPENED")
        self.assertFalse(self.manifest["outcome_seal"]["outcome_values_read"])
        self.assertEqual(self.manifest["outcome_seal"]["outcome_paths_opened"], [])
        self.assertFalse(self.manifest["acceptance"]["outcome_access_authorized"])
        for field in (
            "network_calls",
            "provider_api_rpc_wss_calls",
            "drive_reads",
            "drive_writes",
            "credential_use",
            "outcome_reads",
            "raw_or_dataset_writes",
            "additional_collection",
            "cash_spend_usd_cents",
            "dependency_changes",
            "wallet_signer_transaction_actions",
        ):
            with self.subTest(field=field):
                self.assertEqual(self.profile["authority"][field], 0)

    def test_catalog_is_deliberately_deferred_to_atom6(self) -> None:
        for artifact in (self.manifest, self.ledger):
            self.assertFalse(artifact["catalog"]["registered_in_atom5"])
            self.assertEqual(
                artifact["catalog"]["status"],
                "CATALOG_TRANSACTION_PENDING_T22_A6",
            )

    def test_unsafe_consumer_profiles_fail_closed(self) -> None:
        cases = (
            ("feature_max_lookback_seconds", 1, "unproven_feature_lookback"),
            (
                "optimization_or_strategy_selection_allowed",
                True,
                "strategy_optimization_not_allowed",
            ),
            (
                "exact_horizon_claims_allowed",
                True,
                "nominal_horizon_claim_not_allowed",
            ),
        )
        for key, value, error in cases:
            profile = copy.deepcopy(self.profile)
            profile["consumer"][key] = value
            with self.subTest(key=key):
                with self.assertRaisesRegex(Task22ResolutionError, error):
                    validate_inputs(ROOT, profile)

    def test_short_horizon_or_insufficient_embargo_fails_closed(self) -> None:
        development = copy.deepcopy(self.manifest["roles"]["development"])
        holdout = copy.deepcopy(self.manifest["roles"]["holdout"])

        short = copy.deepcopy(self.profile)
        short["consumer"]["label_horizon_seconds"] = 60
        with self.assertRaisesRegex(
            Task22ResolutionError,
            "declared_label_horizon_too_short",
        ):
            _resolve(profile=short, development=development, holdout=holdout)

        excessive = copy.deepcopy(self.profile)
        excessive["consumer"]["embargo_seconds"] = 1800
        with self.assertRaisesRegex(
            Task22ResolutionError,
            "temporal_envelope_not_splittable",
        ):
            _resolve(profile=excessive, development=development, holdout=holdout)

    def test_authored_files_are_sanitized(self) -> None:
        paths = [
            ROOT / PROFILE_PATH,
            ROOT / SCHEMA_PATH,
            ROOT / "src/solana_alpha_lab/task22_split_resolution.py",
            ROOT / "scripts/build_task22_split_resolution.py",
            ROOT / SPLIT_PATH,
            ROOT / LEDGER_PATH,
            Path(__file__),
        ]
        prohibited = {
            "windows_absolute_path": re.compile(r"(?i)\\b[a-z]:[\\\\/]"),
            "user_home_path": re.compile(r"(?i)/(?:users|home)/[^/\\s]+"),
            "private_key_block": re.compile(
                r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
            ),
        }
        for path in paths:
            with self.subTest(path=path.as_posix()):
                value = path.read_bytes()
                self.assertFalse(value.startswith(b"\xef\xbb\xbf"))
                self.assertNotIn(b"\r", value)
                self.assertTrue(value.endswith(b"\n"))
                text = value.decode("utf-8")
                self.assertTrue(
                    all(
                        line.rstrip(" \t") == line
                        for line in text.splitlines()
                    )
                )
                for pattern in prohibited.values():
                    self.assertIsNone(pattern.search(text))


if __name__ == "__main__":
    unittest.main()
