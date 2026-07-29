from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT
    / "docs"
    / "contracts"
    / "task19_point_in_time_replay_contract_v1.md"
)
FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task19"
    / "point_in_time_replay_contract_v1.json"
)
TASK17A_AUDIT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task17a"
    / "execution_capacity_quote_panel_audit_v1.json"
)
EXPECTED_FIXTURE_SHA256 = (
    "c2485b17ae2fd7daac08c6a433b95d842a9552fe74d6f5df8d52d4786f3abce0"
)
EXPECTED_MANAGED_FILES = [
    "docs/contracts/task19_point_in_time_replay_contract_v1.md",
    "tests/fixtures/task19/point_in_time_replay_contract_v1.json",
    "tests/test_task19_point_in_time_replay_contract.py",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task19PointInTimeReplayContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_bytes = FIXTURE_PATH.read_bytes()
        cls.fixture = json.loads(cls.fixture_bytes)
        cls.contract = CONTRACT_PATH.read_text(encoding="utf-8")
        cls.task17a_audit = json.loads(
            TASK17A_AUDIT_PATH.read_text(encoding="utf-8")
        )

    def test_fixture_identity_and_fingerprint_are_frozen(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.fixture_bytes).hexdigest(),
            EXPECTED_FIXTURE_SHA256,
        )
        self.assertEqual(
            self.fixture["contract_id"],
            "CONTRACT-T19-POINT-IN-TIME-REPLAY-001",
        )
        self.assertEqual(self.fixture["task_id"], "TASK-19")
        self.assertEqual(
            self.fixture["atom_id"],
            "T19-A2_FROZEN_POINT_IN_TIME_REPLAY_CONTRACT_V1",
        )
        self.assertEqual(self.fixture["status"], "FROZEN_OFFLINE_CONTRACT")

    def test_entry_gate_binds_exact_base_catalog_and_raw_readback(self) -> None:
        gate = self.fixture["entry_gate"]
        self.assertEqual(gate["verdict"], "START_AS_WRITTEN")
        self.assertEqual(
            gate["source_activation"],
            "ACTIVATION_CONFIRMED_USER_SMOKE",
        )
        self.assertEqual(
            gate["accepted_base_commit"],
            "7daa7702895f90844a488337dd74ddf26dbfa00b",
        )
        self.assertEqual(
            gate["accepted_base_tree"],
            "43b4c493396114ff075723fc54496e3d5f920ed7",
        )
        self.assertEqual(
            (
                gate["catalog_version"],
                gate["catalog_assets"],
                gate["catalog_shards"],
                gate["catalog_schemas"],
                gate["catalog_queries"],
            ),
            ("0.23.0", 321, 4, 4, 8),
        )
        self.assertEqual(gate["raw_files_present"], 12)
        self.assertEqual(gate["raw_rows_present"], 32)
        self.assertEqual(gate["raw_stored_bytes"], 179_208)
        self.assertEqual(gate["raw_hash_readback"], "PASS_12_OF_12")
        self.assertTrue(gate["local_backup_present"])

    def test_tracked_inputs_match_exact_repository_bytes(self) -> None:
        expected_paths = {
            row["path"]: ROOT / Path(row["path"])
            for row in self.fixture["tracked_inputs"]
        }
        self.assertEqual(len(expected_paths), 7)
        for row in self.fixture["tracked_inputs"]:
            with self.subTest(asset_id=row["asset_id"]):
                path = expected_paths[row["path"]]
                self.assertTrue(path.is_file())
                self.assertEqual(row["sha256"], sha256(path))

    def test_estimand_and_membership_are_narrow_and_exact(self) -> None:
        estimand = self.fixture["estimand"]
        membership = self.fixture["membership"]
        self.assertEqual(
            estimand["hypothesis_version_id"],
            self.task17a_audit["hypothesis_version_id"],
        )
        self.assertEqual(
            estimand["accepted_windows"],
            [
                "T17A-WINDOW-01",
                "T17A-WINDOW-03",
                "T17A-WINDOW-04-REPAIR-01",
            ],
        )
        self.assertEqual(
            membership["accepted_window_order"],
            estimand["accepted_windows"],
        )
        self.assertEqual(
            estimand["excluded_retained_windows"],
            ["T17A-WINDOW-02"],
        )
        self.assertEqual(membership["excluded_window_id"], "T17A-WINDOW-02")
        self.assertEqual(
            membership["excluded_reason"],
            "TRIGGER_SEPARATION_SHORTFALL_0_007854_SECONDS",
        )
        self.assertFalse(membership["availability_may_override_exclusion"])
        self.assertFalse(membership["post_hoc_tolerance_allowed"])
        self.assertFalse(membership["reclassification_allowed"])
        self.assertEqual(estimand["accepted_attempts"], 24)
        self.assertEqual(estimand["excluded_retained_attempts"], 8)
        self.assertEqual(estimand["complete_quote_pairs"], 12)
        self.assertFalse(estimand["promotion_authorized"])

    def test_literal_cutoffs_cannot_move_with_runtime_rows(self) -> None:
        time_contract = self.fixture["time_contract"]
        self.assertEqual(time_contract["timezone"], "UTC")
        self.assertEqual(
            time_contract["cutoff_source"],
            "FROZEN_LITERAL_NOT_RUNTIME_MAXIMUM",
        )
        self.assertFalse(time_contract["runtime_cutoff_extension_allowed"])
        self.assertEqual(
            time_contract["eligibility_fields"],
            [
                "first_reliable_available_at",
                "available_to_strategy_at",
                "ingested_at",
            ],
        )
        self.assertFalse(time_contract["event_time_grants_eligibility"])
        self.assertFalse(time_contract["requested_at_grants_eligibility"])
        self.assertFalse(time_contract["response_at_grants_eligibility"])
        self.assertEqual(
            time_contract["ordered_source_fields"],
            [
                "requested_at",
                "response_at",
                "first_reliable_available_at",
                "available_to_strategy_at",
                "ingested_at",
            ],
        )

        cutoffs = {
            row["window_id"]: row
            for row in time_contract["window_cutoffs"]
        }
        self.assertEqual(
            cutoffs["T17A-WINDOW-01"]["decision_at"],
            "2026-07-29T14:17:06.203260Z",
        )
        self.assertEqual(
            cutoffs["T17A-WINDOW-03"]["decision_at"],
            "2026-07-29T15:17:10.046218Z",
        )
        self.assertEqual(
            cutoffs["T17A-WINDOW-04-REPAIR-01"]["decision_at"],
            "2026-07-29T15:47:24.921906Z",
        )
        self.assertEqual(
            time_contract["final_evaluation_decision_at"],
            cutoffs["T17A-WINDOW-04-REPAIR-01"]["decision_at"],
        )
        self.assertEqual(
            cutoffs["T17A-WINDOW-02"]["expected_eligible_rows"],
            0,
        )
        self.assertTrue(time_contract["backfill_availability_forbidden"])

    def test_ordering_pairing_and_arithmetic_are_deterministic(self) -> None:
        ordering = self.fixture["ordering"]
        pairing = self.fixture["pairing"]
        self.assertFalse(ordering["input_file_order_is_authority"])
        self.assertEqual(
            ordering["window_order_source"],
            "FROZEN_ACCEPTED_WINDOW_ORDER",
        )
        self.assertEqual(
            ordering["within_window_keys"],
            [
                "call_ordinal",
                "quote_attempt.quote_attempt_id",
                "raw_event.raw_event_id",
                "request_hash",
                "idempotency_key",
            ],
        )
        self.assertFalse(ordering["silent_deduplication_allowed"])
        self.assertEqual(pairing["notionals_usd"], [10, 25, 50, 100])
        self.assertEqual(
            pairing["ordinal_pairs"],
            [[1, 2], [3, 4], [5, 6], [7, 8]],
        )
        self.assertEqual(pairing["first_side"], "BUY")
        self.assertEqual(pairing["second_side"], "SELL")
        self.assertTrue(pairing["dependent_sell_input_equals_buy_output"])
        self.assertEqual(pairing["arithmetic"], "INTEGER_ATOMIC_UNITS_PLUS_DECIMAL")
        self.assertEqual(pairing["quantum"], "0.0001")
        self.assertEqual(pairing["rounding"], "ROUND_HALF_EVEN")

    def test_expected_output_matches_accepted_task17a_audit(self) -> None:
        output = self.fixture["expected_output"]
        audit = self.task17a_audit
        audit_windows = {
            row["window_id"]: row for row in audit["windows"]
        }
        self.assertEqual(output["accepted_rows"], 24)
        self.assertEqual(output["excluded_retained_rows"], 8)
        self.assertEqual(output["complete_quote_pairs"], 12)
        self.assertEqual(output["complete_monotonic_panels"], 3)
        self.assertEqual(output["complete_panels"], 3)

        for window_id, expected in output["cost_bps_by_window"].items():
            with self.subTest(window_id=window_id):
                audit_window = audit_windows[window_id]
                self.assertEqual(
                    {key: expected[key] for key in ("10", "25", "50", "100")},
                    audit_window["cost_bps_by_notional"],
                )
                self.assertEqual(
                    expected["delta_100_minus_10"],
                    audit_window["delta_cost_bps_usd100_minus_usd10"],
                )

        evaluation = audit["hypothesis_evaluation"]
        self.assertEqual(
            output["median_delta_cost_bps"],
            evaluation["median_delta_cost_bps"],
        )
        self.assertEqual(
            output["hypothesis_result"],
            evaluation["result"],
        )
        self.assertEqual(output["hypothesis_state"], "PAUSED")
        self.assertFalse(output["promotion_authorized"])
        self.assertTrue(output["repeat_output_sha256_must_match"])
        self.assertTrue(output["shuffle_output_sha256_must_match"])

    def test_adversarial_vectors_cover_future_rows_and_fail_closed_inputs(
        self,
    ) -> None:
        mode = self.fixture["adversarial_test_mode"]
        self.assertTrue(mode["synthetic_rows_only_after_base_integrity_passes"])
        self.assertFalse(mode["synthetic_rows_are_production_evidence"])
        self.assertFalse(mode["physical_raw_changes_allowed"])

        vectors = {
            row["vector_id"]: row["expected_outcome"]
            for row in self.fixture["adversarial_vectors"]
        }
        self.assertEqual(
            vectors,
            {
                "T19-FUTURE-ROW-AFTER-CUTOFF-001": (
                    "IGNORED_AND_BASE_OUTPUT_SHA256_UNCHANGED"
                ),
                "T19-BACKFILL-TRAP-001": (
                    "IGNORED_AND_BASE_OUTPUT_SHA256_UNCHANGED"
                ),
                "T19-SHUFFLED-INPUT-001": "BASE_OUTPUT_SHA256_UNCHANGED",
                "T19-EXCLUDED-WINDOW-BEFORE-FINAL-CUTOFF-001": (
                    "EXCLUDED_ROWS_RETAINED_AND_OUTPUT_UNCHANGED"
                ),
                "T19-DUPLICATE-IDENTITY-001": "EVIDENCE_UNAVAILABLE",
                "T19-CHANGED-REVISION-001": "EVIDENCE_UNAVAILABLE",
                "T19-MISSING-AVAILABILITY-001": "EVIDENCE_UNAVAILABLE",
                "T19-IMPOSSIBLE-TIME-ORDER-001": "EVIDENCE_UNAVAILABLE",
                "T19-INCOMPLETE-PAIR-001": "EVIDENCE_UNAVAILABLE",
                "T19-PHYSICAL-RAW-DRIFT-001": (
                    "EVIDENCE_UNAVAILABLE_BEFORE_REPLAY"
                ),
            },
        )

    def test_verdict_precedence_is_fail_closed_and_result_independent(
        self,
    ) -> None:
        verdicts = self.fixture["verdicts"]
        self.assertEqual(
            verdicts["precedence"],
            [
                "EVIDENCE_UNAVAILABLE",
                "LEAKAGE_DETECTED",
                "REPLAY_SAFE_WITH_LIMITATIONS",
                "REPLAY_SAFE",
            ],
        )
        self.assertFalse(verdicts["hypothesis_result_may_select_verdict"])
        self.assertFalse(verdicts["majority_vote_allowed"])
        for verdict in verdicts["precedence"]:
            self.assertIn(verdict, verdicts)

    def test_reuse_is_thin_and_catalog_transaction_is_deferred(self) -> None:
        reuse = self.fixture["reuse"]
        self.assertIn("QUERY-T05-PIT-RELATION-001", reuse["adopt"])
        self.assertIn(
            "MODULE-T17A-EXECUTION-CAPACITY-AUDIT-001",
            reuse["wrap"],
        )
        self.assertIn("MODULE-T18-DATA-QUALITY-001", reuse["wrap"])
        self.assertEqual(reuse["fork"], [])
        self.assertEqual(reuse["new_dependency_count"], 0)
        self.assertFalse(reuse["generic_backtester"])
        self.assertFalse(reuse["general_event_platform"])

        catalog = self.fixture["catalog"]
        self.assertFalse(catalog["registered_in_atom2"])
        self.assertEqual(
            catalog["status"],
            "CATALOG_TRANSACTION_PENDING_T19_A4",
        )
        self.assertFalse(catalog["blocks_contract_freeze"])
        self.assertTrue(catalog["blocks_task19_done"])
        self.assertEqual(
            catalog["planned_asset_ids"],
            [
                "CONTRACT-T19-POINT-IN-TIME-REPLAY-001",
                "FIXTURE-T19-POINT-IN-TIME-REPLAY-001",
                "TEST-T19-POINT-IN-TIME-REPLAY-CONTRACT-001",
            ],
        )

    def test_a2_authority_is_exact_local_write_only(self) -> None:
        authority = self.fixture["authority"]
        self.assertEqual(authority["class"], "LOCAL_WRITE_ONLY")
        self.assertEqual(authority["source"], "EXPLICIT_USER")
        self.assertEqual(authority["managed_files"], EXPECTED_MANAGED_FILES)
        for field in (
            "network_calls",
            "provider_api_rpc_wss_calls",
            "drive_reads",
            "drive_writes",
            "credential_use",
            "collector_executions",
            "raw_data_writes",
            "cash_spend_usd_cents",
            "provider_credits",
            "dependency_changes",
        ):
            with self.subTest(field=field):
                self.assertEqual(authority[field], 0)
        for field in (
            "commit",
            "push",
            "pull_request",
            "merge",
            "ui_changes",
            "destructive_actions",
        ):
            with self.subTest(field=field):
                self.assertFalse(authority[field])

        next_atom = self.fixture["next_atom"]
        self.assertEqual(
            next_atom["atom_id"],
            "T19-A3_DETERMINISTIC_OFFLINE_REPLAY_AND_LEAKAGE_TESTS_V1",
        )
        self.assertFalse(next_atom["implementation_authorized"])
        self.assertFalse(next_atom["external_calls_authorized"])
        self.assertFalse(next_atom["raw_mutation_authorized"])

    def test_contract_contains_decision_changing_boundaries(self) -> None:
        for marker in (
            "FROZEN_LITERAL_NOT_RUNTIME_MAXIMUM",
            "2026-07-29T15:47:24.921906Z",
            "0.007854-second trigger",
            "old event/request time but future reliable availability",
            "Synthetic vectors are permitted only in tests",
            "EVIDENCE_UNAVAILABLE",
            "LEAKAGE_DETECTED",
            "REPLAY_SAFE_WITH_LIMITATIONS",
            "REPLAY_SAFE",
            "generic backtester",
            "T19-A3_DETERMINISTIC_OFFLINE_REPLAY_AND_LEAKAGE_TESTS_V1",
            "authorizes no provider/API/RPC/WSS call",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.contract)

    def test_tracked_contract_artifacts_are_sanitized(self) -> None:
        texts = {
            "contract": self.contract,
            "fixture": self.fixture_bytes.decode("utf-8"),
            "test": Path(__file__).read_text(encoding="utf-8"),
        }
        prohibited = {
            "windows_absolute_path": re.compile(r"(?i)\b[a-z]:[\\/]"),
            "user_home_path": re.compile(r"(?i)/(?:users|home)/[^/\s]+"),
            "private_key_block": re.compile(
                r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
            ),
            "credential_assignment": re.compile(
                r"(?i)\b(?:api[_-]?key|access[_-]?token|password|secret)"
                r"\s*[:=]\s*[\"'][^\"']+[\"']"
            ),
        }
        for label, text in texts.items():
            for pattern_name, pattern in prohibited.items():
                with self.subTest(file=label, pattern=pattern_name):
                    self.assertIsNone(pattern.search(text))


if __name__ == "__main__":
    unittest.main()
