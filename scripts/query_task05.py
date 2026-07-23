#!/usr/bin/env python3
"""Bounded read-only PIT/as-of queries for TASK-05 DuckDB projections."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

MAX_RECORDS = 100
DUCKDB_UTC_TIMESTAMP = re.compile(
    r"^([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]+)?)[+]00(?::00)?$"
)

# Identifiers are selected only from this static allow-list and never accepted
# as arbitrary SQL fragments.
RELATION_POLICIES: dict[str, tuple[str, str, str]] = {
    "raw_api_events": (
        "raw_event_id",
        "available_to_strategy_at <= ? AND first_reliable_available_at <= ?",
        "* EXCLUDE (redacted_body)",
    ),
    "canonical_observations": (
        "observation_id",
        "available_to_strategy_at <= ? AND first_reliable_available_at <= ?",
        "*",
    ),
    "token_lifecycle_events": (
        "lifecycle_event_id",
        "available_to_strategy_at <= ? AND first_reliable_available_at <= ?",
        "*",
    ),
    "pool_state_snapshots": (
        "pool_snapshot_id",
        "available_to_strategy_at <= ? AND first_reliable_available_at <= ?",
        "*",
    ),
    "trade_orderflow_inputs": (
        "trade_input_id",
        "available_to_strategy_at <= ? AND first_reliable_available_at <= ?",
        "*",
    ),
    "entity_input_snapshots": (
        "entity_snapshot_id",
        "available_to_strategy_at <= ? AND first_reliable_available_at <= ?",
        "*",
    ),
    "feature_observations": (
        "feature_observation_id",
        "available_to_strategy_at <= ? AND first_reliable_available_at <= ?",
        "*",
    ),
    "regime_observations": (
        "regime_observation_id",
        "available_to_strategy_at <= ? AND first_reliable_available_at <= ?",
        "*",
    ),
    "signal_decision_events": (
        "signal_decision_id",
        "available_to_strategy_at <= ? AND first_reliable_available_at <= ?",
        "*",
    ),
    "quote_attempts": (
        "quote_attempt_id",
        "available_to_strategy_at <= ? AND first_reliable_available_at <= ?",
        "*",
    ),
    "execution_attempts": (
        "execution_attempt_id",
        "available_to_strategy_at <= ? AND first_reliable_available_at <= ?",
        "*",
    ),
    "strategy_outcomes": (
        "strategy_outcome_id",
        "available_to_strategy_at <= ? AND first_reliable_available_at <= ?",
        "*",
    ),
    "dataset_manifests": (
        "dataset_manifest_id",
        "created_at <= ? AND first_reliable_available_at <= ?",
        "*",
    ),
    "partition_manifests": (
        "partition_manifest_id",
        "created_at <= ? AND first_reliable_available_at <= ?",
        "*",
    ),
    "migration_manifests": (
        "migration_manifest_id",
        "created_at <= ? AND first_reliable_available_at <= ?",
        "*",
    ),
}


class QueryContractError(ValueError):
    """Fail-closed input or output contract violation."""


def parse_utc_timestamp(value: str) -> datetime:
    """Parse an aware UTC RFC3339 timestamp without accepting local time."""

    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise QueryContractError("invalid_as_of_timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise QueryContractError("as_of_must_be_utc")
    return parsed.astimezone(timezone.utc)


def parse_limit(value: str | int) -> int:
    """Require an explicit small positive output bound."""

    if isinstance(value, bool):
        raise QueryContractError("invalid_limit")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise QueryContractError("invalid_limit") from exc
    if str(parsed) != str(value) or not 1 <= parsed <= MAX_RECORDS:
        raise QueryContractError("limit_out_of_bounds")
    return parsed


def resolve_database_path(value: str) -> Path:
    """Resolve one existing local DuckDB file without echoing machine paths."""

    candidate = Path(value)
    if ".." in candidate.parts:
        raise QueryContractError("database_parent_traversal")
    if candidate.suffix.lower() != ".duckdb":
        raise QueryContractError("database_suffix_not_duckdb")
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise QueryContractError("database_not_found") from exc
    if not resolved.is_file():
        raise QueryContractError("database_not_file")
    return resolved


def connect_readonly(database_path: Path) -> duckdb.DuckDBPyConnection:
    """Open a projection with filesystem/network extensions disabled."""

    connection = duckdb.connect(
        str(database_path),
        read_only=True,
        config={
            "enable_external_access": "false",
            "allow_unsigned_extensions": "false",
        },
    )
    connection.execute("SET TimeZone = 'UTC'")
    connection.execute("SET lock_configuration = true")
    return connection


def json_value(value: Any) -> Any:
    """Convert typed DuckDB scalars to deterministic JSON-safe values."""

    if isinstance(value, datetime):
        return (
            value.astimezone(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        raise QueryContractError("binary_output_forbidden")
    if isinstance(value, str):
        timestamp = DUCKDB_UTC_TIMESTAMP.fullmatch(value)
        if timestamp:
            return timestamp.group(1).replace(" ", "T") + "Z"
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_value(item) for item in value]
    return value


def rows_from_json(
    cursor: duckdb.DuckDBPyConnection,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for (payload,) in cursor.fetchall():
        decoded = json.loads(payload, parse_float=Decimal)
        if not isinstance(decoded, dict):
            raise QueryContractError("duckdb_row_json_not_object")
        result.append(json_value(decoded))
    return result


def query_pit_relation(
    database_path: str,
    relation: str,
    as_of: str,
    limit: str | int,
) -> dict[str, Any]:
    """Return a bounded deterministic relation sample eligible at one cutoff."""

    try:
        primary_key, predicate, projection = RELATION_POLICIES[relation]
    except KeyError as exc:
        raise QueryContractError("relation_not_allowed") from exc
    cutoff = parse_utc_timestamp(as_of)
    bounded_limit = parse_limit(limit)
    path = resolve_database_path(database_path)
    connection = connect_readonly(path)
    try:
        cursor = connection.execute(
            f"""
            SELECT to_json(result_row)
            FROM (
                SELECT {projection}
                FROM "{relation}"
                WHERE {predicate}
                ORDER BY "{primary_key}"
                LIMIT ?
            ) AS result_row
            """,
            [cutoff, cutoff, bounded_limit],
        )
        rows = rows_from_json(cursor)
    except duckdb.Error as exc:
        raise QueryContractError("duckdb_query_failed") from exc
    finally:
        connection.close()
    return {
        "schema_version": "1.0",
        "query": "pit-relation",
        "relation": relation,
        "as_of": json_value(cutoff),
        "limit": bounded_limit,
        "record_count": len(rows),
        "rows": rows,
    }


def query_decision_safe_observations(
    database_path: str,
    as_of: str,
    limit: str | int,
) -> dict[str, Any]:
    """Read the canonical decision-safe macro with a hard output bound."""

    cutoff = parse_utc_timestamp(as_of)
    bounded_limit = parse_limit(limit)
    path = resolve_database_path(database_path)
    connection = connect_readonly(path)
    try:
        cursor = connection.execute(
            """
            SELECT to_json(result_row)
            FROM (
                SELECT *
                FROM decision_safe_observations(?)
                ORDER BY observation_id
                LIMIT ?
            ) AS result_row
            """,
            [cutoff, bounded_limit],
        )
        rows = rows_from_json(cursor)
    except duckdb.Error as exc:
        raise QueryContractError("duckdb_query_failed") from exc
    finally:
        connection.close()
    return {
        "schema_version": "1.0",
        "query": "decision-safe-observations",
        "relation": "canonical_observations",
        "as_of": json_value(cutoff),
        "limit": bounded_limit,
        "record_count": len(rows),
        "rows": rows,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="query", required=True)

    relation = subparsers.add_parser("pit-relation")
    relation.add_argument("--database-path", required=True)
    relation.add_argument("--relation", required=True, choices=RELATION_POLICIES)
    relation.add_argument("--as-of", required=True)
    relation.add_argument("--limit", required=True)

    observations = subparsers.add_parser("decision-safe-observations")
    observations.add_argument("--database-path", required=True)
    observations.add_argument("--as-of", required=True)
    observations.add_argument("--limit", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.query == "pit-relation":
            result = query_pit_relation(
                args.database_path,
                args.relation,
                args.as_of,
                args.limit,
            )
        else:
            result = query_decision_safe_observations(
                args.database_path,
                args.as_of,
                args.limit,
            )
    except QueryContractError as exc:
        print(
            json.dumps(
                {"schema_version": "1.0", "status": "ERROR", "error": str(exc)},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
