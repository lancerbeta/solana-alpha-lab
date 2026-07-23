from __future__ import annotations

import copy
import json
import re
import sys
import unittest
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Annotated, get_args, get_origin

import duckdb
from pydantic import AwareDatetime, ValidationError

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.contracts.schema_v1 import (  # noqa: E402
    RELATION_INSERTION_ORDER,
    RELATION_MODELS,
    duckdb_row,
    validate_relation_json,
)

SCHEMA_PATH = ROOT / "schemas" / "schema_v1.sql"
FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task05"
    / "schema_model_roundtrip_fixture_v1.json"
)

EXPECTED_RELATIONS = (
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
)


def insert_row(
    connection: duckdb.DuckDBPyConnection,
    relation: str,
    row: dict[str, object],
) -> None:
    columns = list(row)
    placeholders = ", ".join("?" for _ in columns)
    connection.execute(
        f"INSERT INTO {relation} ({', '.join(columns)}) VALUES ({placeholders})",
        [row[column] for column in columns],
    )


def allows_none(annotation: object) -> bool:
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    return type(None) in get_args(annotation)


def python_storage_type(annotation: object) -> type[object]:
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    if type(None) in get_args(annotation):
        annotation = next(item for item in get_args(annotation) if item is not type(None))
        while get_origin(annotation) is Annotated:
            annotation = get_args(annotation)[0]
    if annotation is AwareDatetime:
        return datetime
    if isinstance(annotation, type) and issubclass(annotation, StrEnum):
        return str
    if annotation in {str, int, bool, bytes, Decimal, datetime}:
        return annotation
    raise AssertionError(f"unsupported_model_storage_type:{annotation!r}")


def contract_enum_type(annotation: object) -> type[StrEnum] | None:
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    if type(None) in get_args(annotation):
        annotation = next(item for item in get_args(annotation) if item is not type(None))
        while get_origin(annotation) is Annotated:
            annotation = get_args(annotation)[0]
    if isinstance(annotation, type) and issubclass(annotation, StrEnum):
        return annotation
    return None


DUCKDB_STORAGE_TYPES = {
    "VARCHAR": str,
    "BLOB": bytes,
    "BOOLEAN": bool,
    "INTEGER": int,
    "BIGINT": int,
    "HUGEINT": int,
    "UBIGINT": int,
    "DECIMAL(38,18)": Decimal,
    "TIMESTAMP WITH TIME ZONE": datetime,
}


class Task05StrictModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.rows = cls.fixture["rows"]

    def test_relation_inventory_is_exact_and_ordered(self) -> None:
        self.assertEqual(tuple(RELATION_MODELS), EXPECTED_RELATIONS)
        self.assertEqual(RELATION_INSERTION_ORDER, EXPECTED_RELATIONS)
        self.assertEqual(tuple(self.rows), EXPECTED_RELATIONS)

    def test_all_model_fields_are_explicitly_required(self) -> None:
        for relation, model in RELATION_MODELS.items():
            with self.subTest(relation=relation):
                self.assertTrue(model.model_fields)
                self.assertTrue(
                    all(field.is_required() for field in model.model_fields.values())
                )

    def test_models_match_ddl_columns_nullability_and_storage_families(self) -> None:
        connection = duckdb.connect(":memory:")
        try:
            connection.execute(self.schema_sql)
            for relation, model in RELATION_MODELS.items():
                with self.subTest(relation=relation):
                    ddl_columns = connection.execute(
                        f"PRAGMA table_info('{relation}')"
                    ).fetchall()
                    self.assertEqual(
                        [column[1] for column in ddl_columns],
                        list(model.model_fields),
                    )
                    for column in ddl_columns:
                        name = column[1]
                        ddl_type = str(column[2])
                        ddl_python_type = (
                            Decimal
                            if ddl_type.startswith("DECIMAL(")
                            else DUCKDB_STORAGE_TYPES[ddl_type]
                        )
                        ddl_nullable = not bool(column[3])
                        annotation = model.model_fields[name].annotation
                        self.assertEqual(
                            allows_none(annotation),
                            ddl_nullable,
                            f"{relation}.{name}: nullability",
                        )
                        self.assertEqual(
                            python_storage_type(annotation),
                            ddl_python_type,
                            f"{relation}.{name}: storage type",
                        )
        finally:
            connection.close()

    def test_models_match_ddl_enum_sets(self) -> None:
        for relation, model in RELATION_MODELS.items():
            table_match = re.search(
                rf"CREATE TABLE {relation} \((.*?)\n\);",
                self.schema_sql,
                flags=re.DOTALL,
            )
            self.assertIsNotNone(table_match, relation)
            table_ddl = table_match.group(1)
            for name, field in model.model_fields.items():
                enum_type = contract_enum_type(field.annotation)
                if enum_type is None:
                    continue
                with self.subTest(relation=relation, field=name):
                    ddl_values = set(
                        re.findall(
                            rf"\b{name}\s*=\s*'([^']+)'",
                            table_ddl,
                        )
                    )
                    for values_block in re.findall(
                        rf"\b{name}\s+IN\s+\((.*?)\)",
                        table_ddl,
                        flags=re.DOTALL,
                    ):
                        ddl_values.update(re.findall(r"'([^']+)'", values_block))
                    self.assertEqual(
                        ddl_values,
                        {member.value for member in enum_type},
                    )

    def test_every_relation_validates_and_roundtrips_through_duckdb(self) -> None:
        connection = duckdb.connect(":memory:")
        try:
            connection.execute(self.schema_sql)
            for relation in RELATION_INSERTION_ORDER:
                raw_row = self.rows[relation]
                model = validate_relation_json(
                    relation,
                    json.dumps(raw_row, separators=(",", ":")),
                )
                insert_row(connection, relation, duckdb_row(model))
                self.assertEqual(
                    connection.execute(
                        f"SELECT count(*) FROM {relation}"
                    ).fetchone()[0],
                    1,
                    relation,
                )
            observed = connection.execute(
                """
                SELECT value_decimal, value_atomic
                FROM canonical_observations
                WHERE observation_id = 'observation-roundtrip'
                """
            ).fetchone()
            self.assertIsNone(observed[0])
            self.assertEqual(observed[1], 0)
        finally:
            connection.close()

    def test_unknown_relation_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown_relation"):
            validate_relation_json("not_a_relation", "{}")

    def test_extra_fields_and_python_scalar_coercion_are_rejected(self) -> None:
        raw = copy.deepcopy(self.rows["raw_api_events"])
        raw["undeclared"] = "forbidden"
        with self.assertRaises(ValidationError):
            RELATION_MODELS["raw_api_events"].model_validate(raw)

        raw = copy.deepcopy(self.rows["raw_api_events"])
        raw["revision_number"] = "1"
        with self.assertRaises(ValidationError):
            RELATION_MODELS["raw_api_events"].model_validate(raw)

    def test_timestamp_must_be_timezone_aware_and_pit_ordered(self) -> None:
        raw = copy.deepcopy(self.rows["raw_api_events"])
        raw["observed_at"] = "2026-07-23T11:59:00"
        with self.assertRaises(ValidationError):
            validate_relation_json("raw_api_events", json.dumps(raw))

        raw = copy.deepcopy(self.rows["raw_api_events"])
        raw["first_reliable_available_at"] = "2026-07-23T11:59:02Z"
        with self.assertRaisesRegex(
            ValidationError,
            "first_reliable_availability_after_strategy_availability",
        ):
            validate_relation_json("raw_api_events", json.dumps(raw))

    def test_atomic_amount_provenance_and_zero_are_not_conflated(self) -> None:
        observation = copy.deepcopy(self.rows["canonical_observations"])
        observation["amount_mint"] = None
        with self.assertRaisesRegex(
            ValidationError,
            "atomic_amount_requires_mint_and_decimals",
        ):
            validate_relation_json("canonical_observations", json.dumps(observation))

        observation = copy.deepcopy(self.rows["canonical_observations"])
        observation["value_atomic"] = None
        observation["amount_mint"] = None
        observation["amount_decimals"] = None
        model = validate_relation_json(
            "canonical_observations",
            json.dumps(observation),
        )
        self.assertIsNone(model.value_atomic)

        entity = copy.deepcopy(self.rows["entity_input_snapshots"])
        entity["token_mint"] = None
        with self.assertRaisesRegex(
            ValidationError,
            "atomic_metric_requires_mint_and_decimals",
        ):
            validate_relation_json("entity_input_snapshots", json.dumps(entity))

    def test_atomic_entity_provenance_is_also_enforced_by_duckdb(self) -> None:
        connection = duckdb.connect(":memory:")
        try:
            connection.execute(self.schema_sql)
            raw = validate_relation_json(
                "raw_api_events",
                json.dumps(self.rows["raw_api_events"]),
            )
            insert_row(connection, "raw_api_events", duckdb_row(raw))
            entity = copy.deepcopy(self.rows["entity_input_snapshots"])
            entity["token_mint"] = None
            with self.assertRaises(duckdb.ConstraintException):
                insert_row(connection, "entity_input_snapshots", entity)
        finally:
            connection.close()

    def test_action_side_and_terminal_states_fail_closed(self) -> None:
        signal = copy.deepcopy(self.rows["signal_decision_events"])
        signal["decision"] = "HOLD"
        with self.assertRaisesRegex(
            ValidationError,
            "non_action_decision_forbids_side",
        ):
            validate_relation_json("signal_decision_events", json.dumps(signal))

        execution = copy.deepcopy(self.rows["execution_attempts"])
        execution["processed_on_chain"] = False
        with self.assertRaisesRegex(
            ValidationError,
            "execution_terminal_state_incoherent",
        ):
            validate_relation_json("execution_attempts", json.dumps(execution))

    def test_raw_success_and_quote_fee_provenance_fail_closed(self) -> None:
        raw = copy.deepcopy(self.rows["raw_api_events"])
        raw["error_class"] = "IMPOSSIBLE"
        with self.assertRaisesRegex(ValidationError, "success_cannot_have_error"):
            validate_relation_json("raw_api_events", json.dumps(raw))

        quote = copy.deepcopy(self.rows["quote_attempts"])
        quote["fee_mint"] = None
        with self.assertRaisesRegex(
            ValidationError,
            "quote_fee_provenance_incoherent",
        ):
            validate_relation_json("quote_attempts", json.dumps(quote))

    def test_hashes_require_lowercase_hexadecimal(self) -> None:
        raw = copy.deepcopy(self.rows["raw_api_events"])
        raw["request_hash"] = "z" * 64
        with self.assertRaises(ValidationError):
            validate_relation_json("raw_api_events", json.dumps(raw))


if __name__ == "__main__":
    unittest.main()
