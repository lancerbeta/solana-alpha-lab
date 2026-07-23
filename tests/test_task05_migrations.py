from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

import duckdb
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.contracts.migration_ledger import (  # noqa: E402
    MigrationLedger,
    MigrationLedgerError,
    assert_ledger_evolution,
    load_ledger,
    verify_ledger_files,
)

LEDGER_PATH = ROOT / "migrations" / "ledger_v1.json"
MIGRATION_PATH = ROOT / "migrations" / "0001_canonical_schema_v1.sql"
SCHEMA_PATH = ROOT / "schemas" / "schema_v1.sql"

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


def model_from_payload(payload: dict[str, object]) -> MigrationLedger:
    return MigrationLedger.model_validate_json(
        json.dumps(payload, separators=(",", ":"))
    )


def appended_entry(
    operation: str = "ADD_NULLABLE_COLUMN",
    *,
    from_type: str | None = None,
    to_type: str | None = "VARCHAR",
) -> dict[str, object]:
    return {
        "migration_id": "T05-0002-SAFE-EVOLUTION",
        "migration_order": 2,
        "migration_kind": "DDL",
        "schema_version": "1.1",
        "sql_path": "migrations/0002_safe_evolution.sql",
        "content_sha256": (
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        ),
        "application_state": "DECLARED",
        "changes": [
            {
                "operation": operation,
                "relation": "canonical_observations",
                "column": "future_nullable_column",
                "from_type": from_type,
                "to_type": to_type,
            }
        ],
    }


class Task05MigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
        cls.ledger = load_ledger(LEDGER_PATH)

    def test_ledger_is_strict_ordered_and_content_addressed(self) -> None:
        self.assertEqual(self.ledger.ledger_version, "1.0")
        self.assertEqual(len(self.ledger.migrations), 1)
        entry = self.ledger.migrations[0]
        self.assertEqual(entry.migration_id, "T05-0001-CANONICAL-SCHEMA-V1")
        self.assertEqual(entry.migration_order, 1)
        self.assertEqual(entry.sql_path, "migrations/0001_canonical_schema_v1.sql")
        self.assertEqual(
            entry.content_sha256,
            hashlib.sha256(MIGRATION_PATH.read_bytes()).hexdigest(),
        )
        verify_ledger_files(self.ledger, ROOT)

    def test_migration_0001_is_exact_immutable_schema_snapshot(self) -> None:
        self.assertEqual(MIGRATION_PATH.read_bytes(), SCHEMA_PATH.read_bytes())

    def test_fresh_rebuild_creates_exact_schema_inventory(self) -> None:
        connection = duckdb.connect(":memory:")
        try:
            connection.execute(MIGRATION_PATH.read_text(encoding="utf-8"))
            tables = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'main'
                    """
                ).fetchall()
            }
            self.assertEqual(tables, EXPECTED_TABLES)
            macro_count = connection.execute(
                """
                SELECT count(*)
                FROM duckdb_functions()
                WHERE function_name = 'decision_safe_observations'
                  AND function_type = 'table_macro'
                """
            ).fetchone()[0]
            self.assertEqual(macro_count, 1)
        finally:
            connection.close()

    def test_duplicate_ids_orders_and_gaps_fail_closed(self) -> None:
        duplicate_id = copy.deepcopy(self.payload)
        second = appended_entry()
        second["migration_id"] = duplicate_id["migrations"][0]["migration_id"]
        duplicate_id["migrations"].append(second)
        with self.assertRaisesRegex(ValidationError, "duplicate_migration_id"):
            model_from_payload(duplicate_id)

        duplicate_order = copy.deepcopy(self.payload)
        second = appended_entry()
        second["migration_order"] = 1
        duplicate_order["migrations"].append(second)
        with self.assertRaisesRegex(ValidationError, "duplicate_migration_order"):
            model_from_payload(duplicate_order)

        order_gap = copy.deepcopy(self.payload)
        second = appended_entry()
        second["migration_order"] = 3
        order_gap["migrations"].append(second)
        with self.assertRaisesRegex(
            ValidationError,
            "migration_order_not_contiguous",
        ):
            model_from_payload(order_gap)

    def test_unsafe_evolution_operations_fail_closed(self) -> None:
        for operation in ("NARROW_TYPE", "DROP_COLUMN", "MAKE_REQUIRED"):
            with self.subTest(operation=operation):
                payload = copy.deepcopy(self.payload)
                payload["migrations"].append(
                    appended_entry(
                        operation,
                        from_type="BIGINT",
                        to_type="INTEGER",
                    )
                )
                with self.assertRaisesRegex(
                    MigrationLedgerError,
                    "unsafe_schema_change",
                ):
                    model_from_payload(payload)

    def test_invalid_widening_fails_and_safe_widenings_pass(self) -> None:
        for source, target in (
            ("BIGINT", "INTEGER"),
            ("VARCHAR", "BIGINT"),
            ("DECIMAL(38,18)", "DECIMAL(18,6)"),
            ("DECIMAL(18,6)", "DECIMAL(18,7)"),
        ):
            with self.subTest(source=source, target=target):
                payload = copy.deepcopy(self.payload)
                payload["migrations"].append(
                    appended_entry(
                        "WIDEN_TYPE",
                        from_type=source,
                        to_type=target,
                    )
                )
                with self.assertRaisesRegex(
                    MigrationLedgerError,
                    "invalid_widening",
                ):
                    model_from_payload(payload)

        for source, target in (
            ("INTEGER", "BIGINT"),
            ("UBIGINT", "HUGEINT"),
            ("DECIMAL(18,6)", "DECIMAL(38,18)"),
        ):
            with self.subTest(source=source, target=target):
                payload = copy.deepcopy(self.payload)
                payload["migrations"].append(
                    appended_entry(
                        "WIDEN_TYPE",
                        from_type=source,
                        to_type=target,
                    )
                )
                self.assertEqual(len(model_from_payload(payload).migrations), 2)

    def test_history_is_append_only_and_existing_payload_is_immutable(self) -> None:
        candidate_payload = copy.deepcopy(self.payload)
        candidate_payload["migrations"].append(appended_entry())
        candidate = model_from_payload(candidate_payload)
        assert_ledger_evolution(self.ledger, candidate)

        mutated_payload = copy.deepcopy(candidate_payload)
        mutated_payload["migrations"][0]["schema_version"] = "9.9"
        with self.assertRaisesRegex(
            MigrationLedgerError,
            "migration_history_mutated",
        ):
            assert_ledger_evolution(
                self.ledger,
                model_from_payload(mutated_payload),
            )

        with self.assertRaisesRegex(
            MigrationLedgerError,
            "migration_history_deleted",
        ):
            assert_ledger_evolution(candidate, self.ledger)

    def test_applied_and_terminal_states_cannot_be_rewritten(self) -> None:
        applied_payload = copy.deepcopy(self.payload)
        applied_payload["migrations"][0]["application_state"] = "APPLIED"
        applied = model_from_payload(applied_payload)

        failed_payload = copy.deepcopy(applied_payload)
        failed_payload["migrations"][0]["application_state"] = "FAILED"
        failed = model_from_payload(failed_payload)
        with self.assertRaisesRegex(
            MigrationLedgerError,
            "applied_migration_mutated",
        ):
            assert_ledger_evolution(applied, failed)

    def test_path_traversal_and_checksum_drift_fail_closed(self) -> None:
        traversal = copy.deepcopy(self.payload)
        traversal["migrations"][0]["sql_path"] = "../outside.sql"
        with self.assertRaisesRegex(ValidationError, "unsafe_migration_sql_path"):
            model_from_payload(traversal)

        checksum_drift = copy.deepcopy(self.payload)
        checksum_drift["migrations"][0]["content_sha256"] = "0" * 64
        with self.assertRaisesRegex(
            MigrationLedgerError,
            "migration_checksum_mismatch",
        ):
            verify_ledger_files(model_from_payload(checksum_drift), ROOT)


if __name__ == "__main__":
    unittest.main()
