from __future__ import annotations

import copy
import json
import re
import unittest
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "schema_v1.sql"
CONTRACT_PATH = ROOT / "docs" / "contracts" / "data_contract_v1.md"
FIXTURE_PATH = (
    ROOT / "tests" / "fixtures" / "task05" / "schema_contract_fixture_v1.json"
)

EXPECTED_TABLES = {
    "raw_api_events",
    "canonical_observations",
    "token_lifecycle_events",
    "pool_state_snapshots",
    "trade_orderflow_inputs",
    "entity_input_snapshots",
    "feature_observations",
    "regime_observations",
    "signal_decision_events",
    "quote_attempts",
    "execution_attempts",
    "strategy_outcomes",
    "dataset_manifests",
    "partition_manifests",
    "migration_manifests",
}


def insert_row(
    connection: duckdb.DuckDBPyConnection,
    table: str,
    row: dict[str, object],
) -> None:
    prepared = dict(row)
    if "redacted_body_hex" in prepared:
        prepared["redacted_body"] = bytes.fromhex(
            str(prepared.pop("redacted_body_hex"))
        )
    columns = list(prepared)
    placeholders = ", ".join("?" for _ in columns)
    connection.execute(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
        [prepared[column] for column in columns],
    )


class Task05SchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        cls.contract = CONTRACT_PATH.read_text(encoding="utf-8")
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def setUp(self) -> None:
        self.connection = duckdb.connect(":memory:")
        self.connection.execute(self.schema_sql)

    def tearDown(self) -> None:
        self.connection.close()

    def insert_raw_events(self) -> None:
        for row in self.fixture["raw_events"]:
            insert_row(self.connection, "raw_api_events", row)

    def insert_quotes(self) -> None:
        self.insert_raw_events()
        for row in self.fixture["quotes"]:
            insert_row(self.connection, "quote_attempts", row)

    def insert_observations(self) -> None:
        for row in self.fixture["observations"]:
            insert_row(self.connection, "canonical_observations", row)

    def execution_row(self, fixture_row: dict[str, object]) -> dict[str, object]:
        return {
            "execution_attempt_id": fixture_row["execution_attempt_id"],
            "idempotency_key": f"idem-{fixture_row['execution_attempt_id']}",
            "business_key": f"attempt-{fixture_row['execution_attempt_id']}",
            "quote_attempt_id": None,
            "signal_decision_id": None,
            "side": "BUY",
            "input_mint": "mint-quote-fixture",
            "requested_input_atomic": 1000000,
            "input_decimals": 6,
            "output_mint": "mint-token-fixture",
            "output_decimals": 6,
            "submitted_at": fixture_row["submitted_at"],
            "terminal_at": "2026-07-23T12:02:00Z",
            "observed_at": "2026-07-23T12:02:01Z",
            "available_to_strategy_at": "2026-07-23T12:02:02Z",
            "ingested_at": "2026-07-23T12:02:03Z",
            "first_reliable_available_at": "2026-07-23T12:02:02Z",
            "terminal_state": fixture_row["terminal_state"],
            "processed_on_chain": fixture_row["processed_on_chain"],
            "transaction_signature": fixture_row["transaction_signature"],
            "realized_input_atomic": fixture_row["realized_input_atomic"],
            "realized_output_atomic": fixture_row["realized_output_atomic"],
            "actual_network_fee_lamports": fixture_row[
                "actual_network_fee_lamports"
            ],
            "actual_relay_tip_lamports": None,
            "actual_ata_rent_lamports": None,
            "fee_payer_mint": fixture_row["fee_payer_mint"],
            "error_class": fixture_row["error_class"],
            "reconciliation_reference": fixture_row["reconciliation_reference"],
            "source": "synthetic_execution_fixture",
            "source_version": "1.0",
            "content_sha256": self.fixture["hashes"]["a"],
            "schema_version": "1.0",
            "revision_number": 1,
            "revision_of": None,
            "raw_event_id": None,
            "quality_flags": "SYNTHETIC",
        }

    def signal_decision_row(
        self,
        decision: str,
        side: str | None,
    ) -> dict[str, object]:
        return {
            "signal_decision_id": f"signal-{decision.lower()}",
            "idempotency_key": f"signal-idem-{decision.lower()}",
            "business_key": f"strategy-fixture:{decision.lower()}",
            "strategy_id": "strategy-fixture",
            "strategy_version": "1.0",
            "entity_id": "mint-token-fixture",
            "decision": decision,
            "side": side,
            "decision_as_of": "2026-07-23T12:00:01Z",
            "event_time": "2026-07-23T12:00:00Z",
            "observed_at": "2026-07-23T12:00:00Z",
            "available_to_strategy_at": "2026-07-23T12:00:00Z",
            "ingested_at": "2026-07-23T12:00:00.001Z",
            "first_reliable_available_at": "2026-07-23T12:00:00Z",
            "source": "synthetic_signal_fixture",
            "source_version": "1.0",
            "schema_version": "1.0",
            "revision_number": 1,
            "revision_of": None,
            "feature_set_fingerprint": self.fixture["hashes"]["a"],
            "content_sha256": self.fixture["hashes"]["b"],
            "quality_flags": "SYNTHETIC",
        }

    def test_schema_executes_in_fresh_duckdb_and_has_bounded_inventory(self) -> None:
        tables = {
            row[0]
            for row in self.connection.execute(
                "SELECT table_name FROM duckdb_tables() WHERE internal = FALSE"
            ).fetchall()
        }
        self.assertEqual(tables, EXPECTED_TABLES)
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM decision_safe_observations("
                "TIMESTAMPTZ '2026-07-23T12:00:00Z')"
            ).fetchone()[0],
            0,
        )

    def test_revision_rows_coexist_and_link_to_retained_original(self) -> None:
        rows = self.fixture["observations"][:2]
        for row in rows:
            insert_row(self.connection, "canonical_observations", row)
        observed = self.connection.execute(
            "SELECT observation_id, revision_number, revision_of "
            "FROM canonical_observations ORDER BY revision_number"
        ).fetchall()
        self.assertEqual(
            observed,
            [
                ("obs-alpha-original", 1, None),
                ("obs-alpha-revision", 2, "obs-alpha-original"),
            ],
        )

    def test_provider_disagreement_coexists_without_overwrite(self) -> None:
        for index in (0, 2):
            insert_row(
                self.connection,
                "canonical_observations",
                self.fixture["observations"][index],
            )
        rows = self.connection.execute(
            "SELECT source, CAST(value_decimal AS VARCHAR) "
            "FROM canonical_observations ORDER BY source"
        ).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            {source for source, _ in rows},
            {"synthetic_provider_alpha", "synthetic_provider_beta"},
        )
        self.assertNotEqual(rows[0][1], rows[1][1])

    def test_duplicate_idempotency_is_rejected_without_deleting_original(self) -> None:
        original = self.fixture["observations"][0]
        insert_row(self.connection, "canonical_observations", original)
        replay = copy.deepcopy(original)
        replay["observation_id"] = "obs-replay-duplicate"
        replay["value_decimal"] = "7.700000000000000000"
        with self.assertRaises(duckdb.ConstraintException):
            insert_row(self.connection, "canonical_observations", replay)
        self.assertEqual(
            self.connection.execute(
                "SELECT observation_id, CAST(value_decimal AS VARCHAR) "
                "FROM canonical_observations"
            ).fetchall(),
            [("obs-alpha-original", "1.100000000000000000")],
        )

    def test_decision_safe_macro_excludes_future_availability(self) -> None:
        self.insert_observations()
        accepted_ids = {
            row[0]
            for row in self.connection.execute(
                "SELECT observation_id FROM decision_safe_observations("
                "TIMESTAMPTZ '2026-07-23T12:00:00Z')"
            ).fetchall()
        }
        self.assertIn("obs-alpha-original", accepted_ids)
        self.assertIn("obs-missing", accepted_ids)
        self.assertNotIn("obs-future", accepted_ids)

    def test_missing_numeric_value_round_trips_as_null_not_zero(self) -> None:
        missing = self.fixture["observations"][3]
        insert_row(self.connection, "canonical_observations", missing)
        observed = self.connection.execute(
            "SELECT value_decimal, value_atomic FROM canonical_observations "
            "WHERE observation_id = 'obs-missing'"
        ).fetchone()
        self.assertEqual(observed, (None, None))

    def test_quote_available_and_no_route_fixtures_are_distinct_valid_states(
        self,
    ) -> None:
        self.insert_quotes()
        rows = self.connection.execute(
            "SELECT status, output_quoted_atomic, route_id, route_count "
            "FROM quote_attempts ORDER BY quote_attempt_id"
        ).fetchall()
        self.assertEqual(
            rows,
            [
                ("QUOTE_AVAILABLE", 2500000, "route-fixture-1", 1),
                ("NO_ROUTE", None, None, 0),
            ],
        )

    def test_no_route_cannot_pretend_to_have_executable_output_or_route(
        self,
    ) -> None:
        self.insert_raw_events()
        invalid = copy.deepcopy(self.fixture["quotes"][1])
        invalid["quote_attempt_id"] = "quote-invalid-no-route"
        invalid["idempotency_key"] = "quote-idem-invalid-no-route"
        invalid["output_quoted_atomic"] = 0
        invalid["route_id"] = "fake-route"
        invalid["route_count"] = 1
        with self.assertRaises(duckdb.ConstraintException):
            insert_row(self.connection, "quote_attempts", invalid)

    def test_enter_requires_non_null_side(self) -> None:
        invalid = self.signal_decision_row("ENTER", None)
        with self.assertRaises(duckdb.ConstraintException):
            insert_row(self.connection, "signal_decision_events", invalid)

    def test_exit_requires_non_null_side(self) -> None:
        invalid = self.signal_decision_row("EXIT", None)
        with self.assertRaises(duckdb.ConstraintException):
            insert_row(self.connection, "signal_decision_events", invalid)

    def test_no_route_requires_non_null_zero_route_count(self) -> None:
        self.insert_raw_events()
        invalid = copy.deepcopy(self.fixture["quotes"][1])
        invalid["route_count"] = None
        with self.assertRaises(duckdb.ConstraintException):
            insert_row(self.connection, "quote_attempts", invalid)

    def test_atomic_observation_requires_non_null_decimals(self) -> None:
        invalid = copy.deepcopy(self.fixture["observations"][0])
        invalid["observation_id"] = "obs-invalid-atomic-decimals"
        invalid["idempotency_key"] = "obs-idem-invalid-atomic-decimals"
        invalid["value_decimal"] = None
        invalid["value_atomic"] = 1
        invalid["unit"] = "ATOMIC"
        invalid["amount_mint"] = "mint-token-fixture"
        invalid["amount_decimals"] = None
        with self.assertRaises(duckdb.ConstraintException):
            insert_row(self.connection, "canonical_observations", invalid)

    def test_all_five_execution_terminal_states_are_accepted(self) -> None:
        fixture_states = self.fixture["execution_terminal_states"]
        for row in fixture_states:
            insert_row(self.connection, "execution_attempts", self.execution_row(row))
        observed = {
            row[0]
            for row in self.connection.execute(
                "SELECT terminal_state FROM execution_attempts"
            ).fetchall()
        }
        self.assertEqual(
            observed,
            {
                "REJECTED_BEFORE_SEND",
                "DROPPED_OR_EXPIRED_NOT_PROCESSED",
                "LANDED_FAILED",
                "LANDED_SUCCESS",
                "UNKNOWN_REQUIRES_RECONCILIATION",
            },
        )

    def test_execution_terminal_state_contradictions_hard_fail(self) -> None:
        invalid_cases: list[dict[str, object]] = []

        rejected = self.execution_row(self.fixture["execution_terminal_states"][0])
        rejected["execution_attempt_id"] = "exec-invalid-rejected-fee"
        rejected["idempotency_key"] = "idem-exec-invalid-rejected-fee"
        rejected["actual_network_fee_lamports"] = 0
        rejected["fee_payer_mint"] = "mint-native-fixture"
        invalid_cases.append(rejected)

        landed_success = self.execution_row(
            self.fixture["execution_terminal_states"][3]
        )
        landed_success["execution_attempt_id"] = "exec-invalid-partial"
        landed_success["idempotency_key"] = "idem-exec-invalid-partial"
        landed_success["realized_output_atomic"] = None
        invalid_cases.append(landed_success)

        unknown = self.execution_row(self.fixture["execution_terminal_states"][4])
        unknown["execution_attempt_id"] = "exec-invalid-unknown-success"
        unknown["idempotency_key"] = "idem-exec-invalid-unknown-success"
        unknown["processed_on_chain"] = True
        invalid_cases.append(unknown)

        for row in invalid_cases:
            with self.subTest(row=row["execution_attempt_id"]):
                with self.assertRaises(duckdb.ConstraintException):
                    insert_row(self.connection, "execution_attempts", row)

    def test_rejected_before_send_requires_false_processed_on_chain(self) -> None:
        invalid = self.execution_row(self.fixture["execution_terminal_states"][0])
        invalid["processed_on_chain"] = None
        with self.assertRaises(duckdb.ConstraintException):
            insert_row(self.connection, "execution_attempts", invalid)

    def test_landed_state_requires_true_processed_on_chain(self) -> None:
        invalid = self.execution_row(self.fixture["execution_terminal_states"][3])
        invalid["processed_on_chain"] = None
        with self.assertRaises(duckdb.ConstraintException):
            insert_row(self.connection, "execution_attempts", invalid)

    def test_unresolved_inventory_requires_amount_and_ordered_recovery_bounds(
        self,
    ) -> None:
        self.insert_quotes()
        valid = self.fixture["unresolved_outcome"]
        insert_row(self.connection, "strategy_outcomes", valid)
        observed = self.connection.execute(
            "SELECT inventory_state, remaining_inventory_atomic, "
            "CAST(recovery_lower_bound_decimal AS VARCHAR), "
            "CAST(recovery_upper_bound_decimal AS VARCHAR) "
            "FROM strategy_outcomes"
        ).fetchone()
        self.assertEqual(observed[0], "UNRESOLVED_REQUIRES_RECOVERY")
        self.assertEqual(observed[1], 2500000)
        self.assertLessEqual(observed[2], observed[3])
        self.assertTrue(
            self.connection.execute(
                "SELECT measured_as_of <= available_to_strategy_at "
                "FROM strategy_outcomes"
            ).fetchone()[0]
        )

        invalid = copy.deepcopy(valid)
        invalid["strategy_outcome_id"] = "outcome-invalid-bounds"
        invalid["idempotency_key"] = "outcome-idem-invalid-bounds"
        invalid["remaining_inventory_atomic"] = 0
        invalid["recovery_lower_bound_decimal"] = "0.500000000000000000"
        invalid["recovery_upper_bound_decimal"] = "0.400000000000000000"
        with self.assertRaises(duckdb.ConstraintException):
            insert_row(self.connection, "strategy_outcomes", invalid)

    def test_unresolved_inventory_requires_non_null_failed_exit_state(
        self,
    ) -> None:
        self.insert_quotes()
        invalid = copy.deepcopy(self.fixture["unresolved_outcome"])
        invalid["failed_exit_state"] = None
        with self.assertRaises(duckdb.ConstraintException):
            insert_row(self.connection, "strategy_outcomes", invalid)

    def test_outcome_availability_cannot_precede_measurement_cutoff(
        self,
    ) -> None:
        self.insert_quotes()
        invalid = copy.deepcopy(self.fixture["unresolved_outcome"])
        invalid["available_to_strategy_at"] = "2026-07-23T12:09:00Z"
        invalid["ingested_at"] = "2026-07-23T12:09:01Z"
        invalid["first_reliable_available_at"] = "2026-07-23T12:09:00Z"
        with self.assertRaises(duckdb.ConstraintException):
            insert_row(self.connection, "strategy_outcomes", invalid)

    def test_manifest_fixtures_accept_valid_and_reject_invalid_bounds(self) -> None:
        manifests = self.fixture["manifests"]
        insert_row(self.connection, "dataset_manifests", manifests["dataset"])
        insert_row(self.connection, "partition_manifests", manifests["partition"])
        insert_row(self.connection, "migration_manifests", manifests["migration"])
        self.assertEqual(
            self.connection.execute(
                "SELECT "
                "(SELECT count(*) FROM dataset_manifests), "
                "(SELECT count(*) FROM partition_manifests), "
                "(SELECT count(*) FROM migration_manifests)"
            ).fetchone(),
            (1, 1, 1),
        )

        invalid = copy.deepcopy(manifests["partition"])
        invalid["partition_manifest_id"] = "partition-manifest-invalid"
        invalid["partition_id"] = "date=2026-07-24"
        invalid["logical_location"] = (
            "dataset-fixture/date=2026-07-24/part-000.parquet"
        )
        invalid["min_event_time"] = "2026-07-24T12:00:00Z"
        invalid["max_event_time"] = "2026-07-24T11:00:00Z"
        with self.assertRaises(duckdb.ConstraintException):
            insert_row(self.connection, "partition_manifests", invalid)

    def test_contract_names_every_relation_macro_and_later_consumers(self) -> None:
        for name in sorted(EXPECTED_TABLES | {"decision_safe_observations"}):
            with self.subTest(name=name):
                self.assertIn(f"`{name}`", self.contract)
        for task_range in (
            "TASK-06",
            "TASK-07",
            "TASK-08",
            "TASK-09",
            "TASK-10",
            "TASK-11",
            "TASK-12",
            "TASK-13",
            "TASK-18/19",
            "TASK-20..24",
            "TASK-25/26",
            "TASK-28..35",
            "TASK-36..40",
            "TASK-43..47",
        ):
            with self.subTest(task_range=task_range):
                self.assertIn(task_range, self.contract)

    def test_schema_contract_and_fixture_have_no_secret_or_machine_path(self) -> None:
        texts = {
            "schema": self.schema_sql,
            "contract": self.contract,
            "fixture": FIXTURE_PATH.read_text(encoding="utf-8"),
        }
        prohibited = {
            "windows_absolute_path": re.compile(r"(?i)\b[a-z]:[\\/]"),
            "user_home_path": re.compile(r"(?i)/(?:users|home)/[^/\s]+"),
            "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
            "credential_assignment": re.compile(
                r"(?i)\b(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*"
                r"[\"'][^\"']+[\"']"
            ),
        }
        for label, text in texts.items():
            for pattern_name, pattern in prohibited.items():
                with self.subTest(file=label, pattern=pattern_name):
                    self.assertIsNone(pattern.search(text))


if __name__ == "__main__":
    unittest.main()
