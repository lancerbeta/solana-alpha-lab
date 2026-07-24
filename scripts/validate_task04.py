#!/usr/bin/env python3
"""Fail-closed validation for the bounded TASK-04 Atom 5A candidate."""

from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import json
import re
import tempfile
import tomllib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from pydantic import AwareDatetime, BaseModel, ConfigDict, StrictBytes, StrictInt, StrictStr

from validate_catalog import load_and_validate

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs/decisions/TASK04_component_candidate_matrix_v1.json"
REGISTRY_PATH = ROOT / "registries/reuse_candidates.yaml"
ADR_PATH = ROOT / "docs/decisions/ADR-002-mvp-stack.md"
EVIDENCE_MANIFEST_PATH = ROOT / "docs/evidence/task04/EVIDENCE_MANIFEST.json"
A4R_SBOM_PATH = ROOT / "docs/evidence/task04/a4r/SBOM.cdx.json"
A5A_SBOM_PATH = ROOT / "docs/evidence/task04/a5a/SBOM.cdx.json"
CANDIDATE_RECEIPT_PATH = ROOT / "docs/evidence/task04/TASK04_A5A_CANDIDATE_RECEIPT.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task04/pit_fixture_v1.json"

EXPECTED_RUNTIME_DEPENDENCIES = {
    "PyYAML==6.0.3",
    "jsonschema==4.26.0",
    "duckdb==1.5.5",
    "pyarrow==25.0.0",
    "pydantic==2.13.4",
    "solana==0.40.1",
    "solders==0.28.0",
    "prometheus-client==0.25.0",
}
EXPECTED_RUNTIME_VERSIONS = {
    "PyYAML": "6.0.3",
    "jsonschema": "4.26.0",
    "duckdb": "1.5.5",
    "pyarrow": "25.0.0",
    "pydantic": "2.13.4",
    "pydantic-core": "2.46.4",
    "solana": "0.40.1",
    "solders": "0.28.0",
    "prometheus-client": "0.25.0",
}
EXPECTED_SECURITY_GROUP = ["pip-audit==2.10.1"]
EXPECTED_VERDICT_COUNTS = {
    "ADOPT": 13,
    "WRAP": 8,
    "FORK": 0,
    "BUILD": 8,
    "DEFER": 15,
    "REJECT": 8,
}
EXPECTED_MATRIX_DECISION_DIGEST = "144a7819b6a0989a33f8551645ab96af9613688644dc82e60b7e6a5f8bade195"
EXPECTED_CRITICAL_PINS = {
    "REUSE-T04-UV-001": "0.11.29",
    "REUSE-T04-JSONSCHEMA-001": "4.26.0",
    "REUSE-T04-LOGGING-001": "3.13.14",
    "REUSE-T04-UNITTEST-001": "3.13.14",
    "REUSE-T04-UV-CYCLONEDX-001": "0.11.29",
    "REUSE-T04-DUCKDB-MULTIWRITER-001": "PENDING_NOT_APPLICABLE_REJECTED_ARCHITECTURE",
    "REUSE-T04-ALEMBIC-001": "PENDING_IF_AUXILIARY_SQLALCHEMY_STORE",
}
EXPECTED_A4R_SBOM_SHA256 = "4db108ab39ea41339949ca4fc74383e80aa040855b5222f6b9892f257f81aeb6"
EXPECTED_A4R_NORMALIZED_GRAPH_SHA256 = "e970bdc62a01229b926f7e734acfcd2deefb56addb0807641729962e151a772f"
EXPECTED_CATALOG_CHECKPOINTS = {
    ("0.3.0", 82, 5),
    ("0.4.0", 110, 7),
    ("0.4.1", 111, 7),
    ("0.5.0", 128, 7),
    ("0.5.1", 128, 7),
}
EXPECTED_MATRIX_FIELDS = {
    "candidate_id", "verdict", "decision_status", "component_area",
    "candidate_name", "pin", "decision_owner", "maintenance_owner",
    "named_consumers", "integration_boundary", "primary_evidence", "as_of",
    "license_terms_state", "pit_replay", "security_signer", "maintenance_sbom",
    "tco", "lock_in", "exit_path", "falsifier", "next_validation",
}
OFFLINE_NETWORK_POLICY = "DENY"
EXTENSION_SETTINGS = {
    "allow_community_extensions": "false",
    "autoinstall_known_extensions": "false",
    "autoload_known_extensions": "false",
}
MIGRATION_SCHEMA_VERSION = "1.0"
MIGRATIONS = (
    {
        "migration_id": "T04-0001-CREATE-MIGRATION-LEDGER",
        "order": 1,
        "schema_version": MIGRATION_SCHEMA_VERSION,
        "sql": (
            "CREATE TABLE _migration_ledger (migration_id VARCHAR PRIMARY KEY, "
            "migration_order INTEGER NOT NULL UNIQUE, sql_sha256 VARCHAR NOT NULL, "
            "schema_version VARCHAR NOT NULL, applied_state VARCHAR NOT NULL, "
            "result_state VARCHAR NOT NULL)"
        ),
        "applied_state": "APPLIED",
        "result_state": "PASS",
    },
    {
        "migration_id": "T04-0002-INGEST-IMMUTABLE-PARQUET",
        "order": 2,
        "schema_version": MIGRATION_SCHEMA_VERSION,
        "sql": "CREATE TABLE observations AS SELECT * FROM read_parquet(?)",
        "applied_state": "APPLIED",
        "result_state": "PASS",
    },
)


class Observation(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    observation_id: StrictStr
    value: StrictInt | None
    payload: StrictBytes
    event_time: AwareDatetime
    observed_at: AwareDatetime
    available_to_strategy_at: AwareDatetime
    ingested_at: AwareDatetime
    first_reliable_available_at: AwareDatetime
    source: StrictStr
    source_version: StrictStr
    revision: StrictInt


ARROW_SCHEMA = pa.schema(
    [
        pa.field("observation_id", pa.string(), nullable=False),
        pa.field("value", pa.int64(), nullable=True),
        pa.field("payload", pa.binary(), nullable=False),
        pa.field("event_time", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("observed_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("available_to_strategy_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("ingested_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("first_reliable_available_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("source", pa.string(), nullable=False),
        pa.field("source_version", pa.string(), nullable=False),
        pa.field("revision", pa.int64(), nullable=False),
    ]
)


class Task04ValidationError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task04ValidationError(f"json_root_not_object:{path.name}")
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task04ValidationError(f"yaml_root_not_object:{path.name}")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise Task04ValidationError("timestamp_must_be_timezone_aware")
    return parsed.astimezone(timezone.utc)


def load_replay_fixture(order: str = "source") -> tuple[datetime, list[Observation]]:
    document = load_json(FIXTURE_PATH)
    raw_items = document.get("observations")
    if not isinstance(raw_items, list):
        raise Task04ValidationError("fixture_observations_missing")
    if order == "reverse":
        raw_items = list(reversed(raw_items))
    elif order != "source":
        raise Task04ValidationError("fixture_order_unsupported")
    observations = []
    for item in raw_items:
        prepared = dict(item)
        prepared["payload"] = bytes.fromhex(prepared.pop("payload_hex"))
        for key in (
            "event_time",
            "observed_at",
            "available_to_strategy_at",
            "ingested_at",
            "first_reliable_available_at",
        ):
            prepared[key] = parse_timestamp(prepared[key])
        observations.append(Observation.model_validate(prepared))
    return parse_timestamp(document["decision_as_of"]), observations


def accepted_observations(order: str = "source") -> tuple[list[Observation], list[str]]:
    decision_as_of, observations = load_replay_fixture(order)
    accepted = sorted(
        (
            item
            for item in observations
            if item.available_to_strategy_at <= decision_as_of
            and item.first_reliable_available_at <= decision_as_of
        ),
        key=lambda item: item.observation_id,
    )
    excluded = sorted(
        item.observation_id for item in observations if item not in accepted
    )
    return accepted, excluded


def observation_json_row(item: Observation) -> dict[str, Any]:
    result = item.model_dump()
    result["payload"] = item.payload.hex()
    for key in (
        "event_time",
        "observed_at",
        "available_to_strategy_at",
        "ingested_at",
        "first_reliable_available_at",
    ):
        result[key] = (
            getattr(item, key)
            .astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
    return result


def canonical_observation_digest(items: list[Observation]) -> str:
    rows = [
        observation_json_row(item)
        for item in sorted(items, key=lambda value: value.observation_id)
    ]
    return sha256_bytes(canonical_json_bytes(rows))


def observation_table(items: list[Observation]) -> pa.Table:
    rows = [
        {**item.model_dump(), "payload": item.payload}
        for item in sorted(items, key=lambda value: value.observation_id)
    ]
    return pa.Table.from_pylist(rows, schema=ARROW_SCHEMA)


def immutable_write(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() != data:
            raise Task04ValidationError("immutable_artifact_replacement_denied")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def deterministic_parquet_bytes(items: list[Observation]) -> bytes:
    sink = pa.BufferOutputStream()
    pq.write_table(
        observation_table(items),
        sink,
        compression="NONE",
        use_dictionary=False,
        write_statistics=True,
        version="2.6",
        data_page_version="1.0",
        coerce_timestamps="us",
        allow_truncated_timestamps=False,
        store_schema=True,
    )
    return sink.getvalue().to_pybytes()


def dataset_manifest_bytes(
    parquet_data: bytes, items: list[Observation], canonical_input_digest: str
) -> bytes:
    document = {
        "schema_version": "1.0",
        "dataset_id": "FIXTURE-T04-PIT-001-ACCEPTED",
        "parquet_logical_name": "observations.parquet",
        "parquet_sha256": sha256_bytes(parquet_data),
        "canonical_input_sha256": canonical_input_digest,
        "row_count": len(items),
        "observation_ids": [item.observation_id for item in items],
        "arrow_schema": str(ARROW_SCHEMA),
    }
    return canonical_json_bytes(document) + b"\n"


def migration_ledger_document() -> dict[str, Any]:
    entries = []
    for migration in MIGRATIONS:
        entry = dict(migration)
        entry["sql_sha256"] = sha256_bytes(entry["sql"].encode("utf-8"))
        entries.append(entry)
    return {
        "schema_version": MIGRATION_SCHEMA_VERSION,
        "ledger_id": "T04-CORE-STACK-MIGRATIONS-001",
        "immutable": True,
        "migrations": entries,
    }


def migration_ledger_bytes() -> bytes:
    return canonical_json_bytes(migration_ledger_document()) + b"\n"


def validate_migration_ledger(data: bytes) -> list[dict[str, Any]]:
    try:
        document = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Task04ValidationError("migration_ledger_invalid_json") from exc
    migrations = document.get("migrations") if isinstance(document, dict) else None
    if not isinstance(migrations, list):
        raise Task04ValidationError("migration_ledger_missing")
    expected = migration_ledger_document()
    expected_by_id = {
        item["migration_id"]: item for item in expected["migrations"]
    }
    observed_ids = [item.get("migration_id") for item in migrations]
    if len(observed_ids) != len(set(observed_ids)):
        raise Task04ValidationError("migration_id_reuse_denied")
    for item in migrations:
        migration_id = item.get("migration_id")
        expected_item = expected_by_id.get(migration_id)
        if expected_item is None:
            raise Task04ValidationError(f"migration_id_unapproved:{migration_id}")
        sql = item.get("sql")
        if (
            sql != expected_item["sql"]
            or item.get("sql_sha256") != sha256_bytes(str(sql).encode("utf-8"))
            or item.get("sql_sha256") != expected_item["sql_sha256"]
        ):
            raise Task04ValidationError(
                f"migration_redefinition_denied:{migration_id}"
            )
    if document != expected or data != migration_ledger_bytes():
        raise Task04ValidationError("migration_ledger_contract_mismatch")
    return migrations


def write_replay_artifacts(
    items: list[Observation], root: Path
) -> tuple[Path, Path, Path, dict[str, str]]:
    canonical_input_digest = canonical_observation_digest(items)
    parquet_data = deterministic_parquet_bytes(items)
    manifest_data = dataset_manifest_bytes(
        parquet_data, items, canonical_input_digest
    )
    ledger_data = migration_ledger_bytes()
    parquet_path = root / "observations.parquet"
    manifest_path = root / "dataset_manifest.json"
    ledger_path = root / "migration_ledger.json"
    immutable_write(parquet_path, parquet_data)
    immutable_write(manifest_path, manifest_data)
    immutable_write(ledger_path, ledger_data)
    return parquet_path, manifest_path, ledger_path, {
        "canonical_input_sha256": canonical_input_digest,
        "parquet_sha256": sha256_bytes(parquet_data),
        "dataset_manifest_sha256": sha256_bytes(manifest_data),
        "migration_ledger_sha256": sha256_bytes(ledger_data),
    }


def configure_duckdb(
    connection: duckdb.DuckDBPyConnection,
    extension_directory: Path,
    isolated_extension_root: Path,
) -> None:
    resolved_directory = extension_directory.resolve()
    resolved_root = isolated_extension_root.resolve()
    if resolved_directory == resolved_root or resolved_root not in resolved_directory.parents:
        raise Task04ValidationError("external_extension_directory_not_allowed")
    if extension_directory.exists() and any(extension_directory.iterdir()):
        raise Task04ValidationError("isolated_extension_directory_not_empty")
    extension_directory.mkdir(parents=True, exist_ok=True)
    escaped = str(resolved_directory).replace("'", "''")
    connection.execute(f"SET extension_directory='{escaped}'")
    for name, value in EXTENSION_SETTINGS.items():
        connection.execute(f"SET {name}={value}")
    observed = {
        row[0]: str(row[1])
        for row in connection.execute(
            "SELECT name, value FROM duckdb_settings() WHERE name IN "
            "('extension_directory','allow_community_extensions',"
            "'autoinstall_known_extensions','autoload_known_extensions')"
        ).fetchall()
    }
    for name, expected in EXTENSION_SETTINGS.items():
        if observed.get(name, "").lower() != expected:
            raise Task04ValidationError(f"duckdb_extension_policy_mismatch:{name}")
    if Path(observed.get("extension_directory", "")).resolve() != resolved_directory:
        raise Task04ValidationError("duckdb_extension_directory_mismatch")
    try:
        connection.execute("LOAD httpfs")
    except duckdb.Error:
        pass
    else:
        raise Task04ValidationError("unapproved_httpfs_load_succeeded")


def rebuild_from_artifacts(
    parquet_path: Path,
    manifest_path: Path,
    ledger_path: Path,
    database_path: Path,
    extension_directory: Path,
    isolated_extension_root: Path,
    *,
    source_mode: str = "PARQUET",
) -> str:
    if source_mode != "PARQUET":
        raise Task04ValidationError("parquet_source_required")
    if not parquet_path.is_file():
        raise Task04ValidationError("parquet_artifact_required")
    if not manifest_path.is_file():
        raise Task04ValidationError("dataset_manifest_required")
    if not ledger_path.is_file():
        raise Task04ValidationError("migration_ledger_required")
    if database_path.exists():
        raise Task04ValidationError("fresh_database_required")

    parquet_data = parquet_path.read_bytes()
    manifest_data = manifest_path.read_bytes()
    manifest = json.loads(manifest_data)
    if manifest.get("parquet_logical_name") != "observations.parquet":
        raise Task04ValidationError("dataset_manifest_parquet_identity_mismatch")
    if manifest.get("parquet_sha256") != sha256_bytes(parquet_data):
        raise Task04ValidationError("dataset_manifest_parquet_hash_mismatch")
    migrations = validate_migration_ledger(ledger_path.read_bytes())

    connection = duckdb.connect(str(database_path))
    try:
        configure_duckdb(connection, extension_directory, isolated_extension_root)
        for migration in migrations:
            migration_id = migration["migration_id"]
            if migration["order"] == 1:
                connection.execute(migration["sql"])
            elif migration["order"] == 2:
                connection.execute(migration["sql"], [str(parquet_path.resolve())])
            else:
                raise Task04ValidationError(
                    f"migration_order_unapproved:{migration['order']}"
                )
            connection.execute(
                "INSERT INTO _migration_ledger VALUES (?, ?, ?, ?, ?, ?)",
                [
                    migration_id,
                    migration["order"],
                    migration["sql_sha256"],
                    migration["schema_version"],
                    migration["applied_state"],
                    migration["result_state"],
                ],
            )
        observed_ledger = connection.execute(
            "SELECT migration_id, migration_order, sql_sha256, schema_version, "
            "applied_state, result_state FROM _migration_ledger "
            "ORDER BY migration_order"
        ).fetchall()
        expected_ledger = [
            (
                item["migration_id"],
                item["order"],
                item["sql_sha256"],
                item["schema_version"],
                item["applied_state"],
                item["result_state"],
            )
            for item in migrations
        ]
        if observed_ledger != expected_ledger:
            raise Task04ValidationError("database_migration_ledger_mismatch")
        rows = connection.execute(
            "SELECT observation_id, value, payload, CAST(event_time AS VARCHAR), "
            "CAST(observed_at AS VARCHAR), CAST(available_to_strategy_at AS VARCHAR), "
            "CAST(ingested_at AS VARCHAR), CAST(first_reliable_available_at AS VARCHAR), "
            "source, source_version, revision FROM observations ORDER BY observation_id"
        ).fetchall()
    finally:
        connection.close()

    columns = [field.name for field in ARROW_SCHEMA]
    rebuilt = []
    for values in rows:
        prepared = dict(zip(columns, values, strict=True))
        for key in (
            "event_time",
            "observed_at",
            "available_to_strategy_at",
            "ingested_at",
            "first_reliable_available_at",
        ):
            prepared[key] = parse_timestamp(prepared[key])
        rebuilt.append(Observation.model_validate(prepared))
    result_digest = canonical_observation_digest(rebuilt)
    if result_digest != manifest.get("canonical_input_sha256"):
        raise Task04ValidationError("rebuild_result_digest_mismatch")
    if len(rebuilt) != manifest.get("row_count"):
        raise Task04ValidationError("rebuild_row_count_mismatch")
    return result_digest


def run_replay_contract(order: str, root: Path) -> bytes:
    items, excluded = accepted_observations(order)
    parquet_path, manifest_path, ledger_path, hashes = write_replay_artifacts(
        items, root / "artifacts"
    )
    isolated_extension_root = root / "isolated_extensions"
    first = rebuild_from_artifacts(
        parquet_path,
        manifest_path,
        ledger_path,
        root / "first.duckdb",
        isolated_extension_root / "first",
        isolated_extension_root,
    )
    second = rebuild_from_artifacts(
        parquet_path,
        manifest_path,
        ledger_path,
        root / "second.duckdb",
        isolated_extension_root / "second",
        isolated_extension_root,
    )
    if first != second or first != hashes["canonical_input_sha256"]:
        raise Task04ValidationError("fresh_rebuild_digest_mismatch")
    receipt = {
        "schema_version": "1.0",
        "fixture_id": "FIXTURE-T04-PIT-001",
        "network_policy": OFFLINE_NETWORK_POLICY,
        "extension_policy": {
            **EXTENSION_SETTINGS,
            "extension_directory": "ISOLATED_PER_FRESH_REBUILD",
            "unapproved_httpfs_load": "DENY",
        },
        "accepted_observation_ids": [item.observation_id for item in items],
        "excluded_observation_ids": excluded,
        **hashes,
        "first_fresh_duckdb_result_sha256": first,
        "second_fresh_duckdb_result_sha256": second,
        "bounded_query": "OBSERVATIONS_ORDERED_BY_OBSERVATION_ID",
        "checks": {
            "source_is_exact_parquet_artifact": True,
            "migration_ledger_applied": True,
            "binary_payload_round_trip": True,
            "future_observation_excluded": True,
            "missing_remains_null": True,
            "timestamps_round_trip": True,
        },
    }
    return canonical_json_bytes(receipt) + b"\n"


def validate_replay_contract() -> str:
    with tempfile.TemporaryDirectory(prefix="task04_replay_source_") as source_dir:
        source_receipt = run_replay_contract("source", Path(source_dir))
    with tempfile.TemporaryDirectory(prefix="task04_replay_reverse_") as reverse_dir:
        reverse_receipt = run_replay_contract("reverse", Path(reverse_dir))
    if source_receipt != reverse_receipt:
        raise Task04ValidationError("replay_input_order_nondeterministic")
    receipt = json.loads(source_receipt)
    if receipt["first_fresh_duckdb_result_sha256"] != receipt[
        "second_fresh_duckdb_result_sha256"
    ]:
        raise Task04ValidationError("replay_fresh_database_mismatch")
    return sha256_bytes(source_receipt)


def validate_dependency_contract(document: dict[str, Any]) -> None:
    project = document.get("project", {})
    if set(project.get("dependencies", [])) != EXPECTED_RUNTIME_DEPENDENCIES:
        raise Task04ValidationError("runtime_dependency_contract_mismatch")
    if "pydantic-core==2.46.4" in project.get("dependencies", []):
        raise Task04ValidationError("pydantic_core_must_remain_transitive")
    groups = document.get("dependency-groups", {})
    if groups != {"security": EXPECTED_SECURITY_GROUP}:
        raise Task04ValidationError("security_dependency_group_mismatch")
    uv = document.get("tool", {}).get("uv", {})
    local = document.get("tool", {}).get("solana-alpha-lab", {})
    if uv.get("required-version") != "==0.11.29":
        raise Task04ValidationError("uv_pin_mismatch")
    expected_tool = {
        "exact_python_pin": "3.13.14",
        "exact_powershell_pin": "7.6.3",
        "provider_calls_allowed": False,
        "real_money_allowed": False,
    }
    if local != expected_tool:
        raise Task04ValidationError("tool_metadata_contract_mismatch")
    if {"task", "stage", "catalog_version"} & set(local):
        raise Task04ValidationError("stale_mutable_tool_metadata")


def validate_lock() -> None:
    with (ROOT / "uv.lock").open("rb") as handle:
        lock = tomllib.load(handle)
    versions = {
        package["name"].lower(): package["version"]
        for package in lock["package"]
        if "version" in package
    }
    for distribution, expected in EXPECTED_RUNTIME_VERSIONS.items():
        observed = versions.get(distribution.lower())
        if observed != expected:
            raise Task04ValidationError(f"lock_pin_mismatch:{distribution}:{observed}")
    if versions.get("pip-audit") != "2.10.1":
        raise Task04ValidationError("lock_security_pin_mismatch")


def matrix_decision_digest(rows: list[dict[str, Any]]) -> str:
    data = "\n".join(
        f"{row['candidate_id']}:{row['verdict']}:{row['decision_status']}"
        for row in rows
    ).encode()
    return sha256_bytes(data)


def matrix_full_row_digest(rows: list[dict[str, Any]]) -> str:
    canonical_rows = sorted(rows, key=lambda row: row["candidate_id"])
    return sha256_bytes(canonical_json_bytes(canonical_rows))


def validate_matrix(matrix: dict[str, Any]) -> None:
    rows = matrix.get("rows")
    if not isinstance(rows, list) or len(rows) != 52 or matrix.get("row_count") != 52:
        raise Task04ValidationError("matrix_row_count_mismatch")
    ids = [row.get("candidate_id") for row in rows]
    if len(ids) != len(set(ids)):
        raise Task04ValidationError("matrix_duplicate_candidate_id")
    counts = Counter(row.get("verdict") for row in rows)
    observed_counts = {key: counts.get(key, 0) for key in EXPECTED_VERDICT_COUNTS}
    if observed_counts != EXPECTED_VERDICT_COUNTS or matrix.get("verdict_counts") != EXPECTED_VERDICT_COUNTS:
        raise Task04ValidationError("matrix_verdict_count_mismatch")
    if matrix_decision_digest(rows) != EXPECTED_MATRIX_DECISION_DIGEST:
        raise Task04ValidationError("matrix_identity_verdict_status_drift")
    by_id = {row["candidate_id"]: row for row in rows}
    if not set(EXPECTED_CRITICAL_PINS).issubset(by_id):
        raise Task04ValidationError("matrix_critical_pin_id_missing")
    for candidate_id, expected_pin in EXPECTED_CRITICAL_PINS.items():
        observed_pin = by_id[candidate_id].get("pin")
        if observed_pin != expected_pin:
            raise Task04ValidationError(
                f"matrix_critical_pin_mismatch:{candidate_id}:{observed_pin}"
            )
    for row in rows:
        missing = EXPECTED_MATRIX_FIELDS - set(row)
        if missing:
            raise Task04ValidationError(f"matrix_required_field_missing:{row.get('candidate_id')}:{sorted(missing)}")
        pin = row["pin"]
        if not (re.fullmatch(r"\d+\.\d+\.\d+", pin) or pin.startswith("PENDING_")):
            raise Task04ValidationError(f"matrix_pin_not_exact_or_pending:{row['candidate_id']}")
        if row["as_of"] != "2026-07-22":
            raise Task04ValidationError(f"matrix_as_of_mismatch:{row['candidate_id']}")


def validate_registry(registry: dict[str, Any], matrix: dict[str, Any]) -> None:
    if registry.get("schema_version") != "1.1" or registry.get("truth_owner") != "TASK-04":
        raise Task04ValidationError("reuse_registry_header_mismatch")
    records = registry.get("records")
    if not isinstance(records, list) or len(records) != 52:
        raise Task04ValidationError("reuse_registry_count_mismatch")
    ids = [record.get("record_id") for record in records]
    if len(ids) != len(set(ids)):
        raise Task04ValidationError("reuse_registry_duplicate_record_id")
    by_id = {row["candidate_id"]: row for row in matrix["rows"]}
    if set(ids) != set(by_id):
        raise Task04ValidationError("matrix_registry_id_mismatch")
    for record in records:
        row = by_id[record["record_id"]]
        expected = {
            "record_kind": "reuse_candidate",
            "derived_from": "PRE-GIT-TASK01-A024",
            "component_area": row["component_area"],
            "candidate_name": row["candidate_name"],
            "verdict": row["verdict"],
            "decision_status": row["decision_status"],
            "pin": row["pin"],
            "decision_owner": row["decision_owner"],
            "named_consumers": row["named_consumers"],
            "matrix_asset_id": "MATRIX-T04-MVP-STACK-001",
            "next_validation": row["next_validation"],
            "status": "REJECTED" if row["verdict"] == "REJECT" else "RECORDED",
        }
        for key, value in expected.items():
            if record.get(key) != value:
                raise Task04ValidationError(f"matrix_registry_reconciliation:{record['record_id']}:{key}")


def normalized_sbom(sbom: dict[str, Any]) -> bytes:
    value = copy.deepcopy(sbom)
    value.pop("serialNumber", None)
    value.get("metadata", {}).pop("timestamp", None)
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def validate_sbom() -> tuple[str, str]:
    a4r_raw = A4R_SBOM_PATH.read_bytes()
    a4r = json.loads(a4r_raw)
    if sha256_bytes(a4r_raw) != EXPECTED_A4R_SBOM_SHA256:
        raise Task04ValidationError("a4r_sbom_raw_hash_mismatch")
    if sha256_bytes(normalized_sbom(a4r)) != EXPECTED_A4R_NORMALIZED_GRAPH_SHA256:
        raise Task04ValidationError("a4r_sbom_normalized_hash_mismatch")
    candidate_raw = A5A_SBOM_PATH.read_bytes()
    candidate = json.loads(candidate_raw)
    if candidate.get("bomFormat") != "CycloneDX" or candidate.get("specVersion") != "1.5":
        raise Task04ValidationError("candidate_sbom_format_mismatch")
    if len(candidate.get("components", [])) != 57 or len(candidate.get("dependencies", [])) != 58:
        raise Task04ValidationError("candidate_sbom_graph_count_mismatch")
    return sha256_bytes(candidate_raw), sha256_bytes(normalized_sbom(candidate))


def validate_license_disclosures(text: str) -> None:
    required = (
        "jsonalias==0.1.1",
        "solders==0.28.0",
        "Exact artifact license metadata is missing",
        "project-level MIT claim for",
        "no stronger official solders project-level claim",
    )
    if any(marker not in text for marker in required):
        raise Task04ValidationError("license_discrepancy_disclosure_missing")


def validate_evidence_manifest() -> None:
    manifest = load_json(EVIDENCE_MANIFEST_PATH)
    files = manifest.get("files", [])
    if len(files) != 9:
        raise Task04ValidationError("evidence_manifest_count_mismatch")
    for item in files:
        path = ROOT / item["path"]
        if not path.is_file() or sha256_path(path) != item["sha256"]:
            raise Task04ValidationError(f"evidence_hash_mismatch:{item['path']}")
    a4r = load_json(ROOT / "docs/evidence/task04/a4r/TASK04_A4R_VALIDATION_RECEIPT.json")
    work = load_json(ROOT / "docs/evidence/task04/a4r/TASK04_A4R_WORK_ACCEPTANCE_RECEIPT.json")
    if a4r.get("verdict") != "PASS" or work.get("prototype_gate") != "CLOSED":
        raise Task04ValidationError("prototype_receipt_contract_mismatch")
    if a4r.get("provider_api_rpc_calls") != 0 or work.get("cash_spend_usd") != 0:
        raise Task04ValidationError("prototype_external_effect_claim")


def validate_candidate_receipt(
    sbom_raw: str,
    sbom_normalized: str,
    matrix_full_digest: str,
    replay_receipt_sha256: str,
) -> None:
    receipt = load_json(CANDIDATE_RECEIPT_PATH)
    validate_zero_effect_receipt(receipt)
    if receipt.get("result") != "PASS_REPAIR1_LOCAL_GATES":
        raise Task04ValidationError("candidate_repair_result_mismatch")
    if receipt.get("canonical_task_status") != "READY" or receipt.get("repository_candidate_state") != "IMPLEMENTED_UNVERIFIED":
        raise Task04ValidationError("candidate_status_authority_mismatch")
    if receipt.get("candidate_sbom_raw_sha256") != sbom_raw or receipt.get("candidate_sbom_normalized_graph_sha256") != sbom_normalized:
        raise Task04ValidationError("candidate_sbom_receipt_mismatch")
    if receipt.get("matrix_full_row_sha256") != matrix_full_digest:
        raise Task04ValidationError("candidate_matrix_full_row_digest_mismatch")
    if receipt.get("replay_receipt_sha256") != replay_receipt_sha256:
        raise Task04ValidationError("candidate_replay_receipt_digest_mismatch")
    if receipt.get("vulnerability_database") != "NOT_QUERIED_BY_POLICY":
        raise Task04ValidationError("vulnerability_policy_mismatch")


def validate_zero_effect_receipt(receipt: dict[str, Any]) -> None:
    expected_zero = {
        "commits": 0,
        "pushes": 0,
        "provider_api_rpc_calls": 0,
        "external_service_writes": 0,
        "cash_spend_usd": 0,
    }
    for key, value in expected_zero.items():
        if receipt.get(key) != value:
            raise Task04ValidationError(f"candidate_external_effect_claim:{key}")


def validate_bridge() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    protocol = (ROOT / "docs/agent/HANDOFF_PROTOCOL.md").read_text(encoding="utf-8")
    for marker in (
        "INPUT=DIRECT_PROMPT", "LOCAL_HANDOFF:", "ACCEPT_LOCAL_HANDOFF:",
        "Never search for the newest", "Work owns canonical",
    ):
        if marker not in agents:
            raise Task04ValidationError(f"agents_bridge_marker_missing:{marker}")
    for marker in (
        ".smial-handoff/work-to-codex/", ".smial-handoff/codex-to-work/",
        "absolute paths", "parent traversal", "symlink", "Never discover",
        "read access only", "Work owns canonical",
    ):
        if marker not in protocol:
            raise Task04ValidationError(f"protocol_marker_missing:{marker}")
    if "TASK-04 is not active" in agents or "TASK-03 —" in agents:
        raise Task04ValidationError("agents_stale_task_binding")


def validate_runtime_versions() -> None:
    for distribution, expected in EXPECTED_RUNTIME_VERSIONS.items():
        observed = importlib.metadata.version(distribution)
        if observed != expected:
            raise Task04ValidationError(f"runtime_version_mismatch:{distribution}:{observed}")
    try:
        importlib.metadata.version("pip-audit")
    except importlib.metadata.PackageNotFoundError:
        return
    raise Task04ValidationError("security_group_leaked_into_runtime")


def validate_catalog_checkpoint(
    version: object,
    asset_count: int,
    query_count: int,
) -> None:
    checkpoint = (str(version), asset_count, query_count)
    if checkpoint not in EXPECTED_CATALOG_CHECKPOINTS:
        raise Task04ValidationError(
            "catalog_checkpoint_mismatch:"
            f"{checkpoint[0]}:{checkpoint[1]}:{checkpoint[2]}"
        )


def validate() -> tuple[str, str]:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        validate_dependency_contract(tomllib.load(handle))
    validate_lock()
    validate_runtime_versions()
    matrix = load_json(MATRIX_PATH)
    validate_matrix(matrix)
    full_row_digest = matrix_full_row_digest(matrix["rows"])
    registry = load_yaml(REGISTRY_PATH)
    validate_registry(registry, matrix)
    for relative in (
        "research_cycles.yaml", "hypotheses.yaml", "global_trial_ledger.yaml",
        "feature_catalog.yaml", "holdout_consumption.yaml", "strategies.yaml",
        "bot_instances.yaml", "decisions_negative_results.yaml",
    ):
        document = load_yaml(ROOT / "registries" / relative)
        if document.get("schema_version") != "1.0" or document.get("records") != []:
            raise Task04ValidationError(f"production_registry_changed:{relative}")
    validate_license_disclosures(ADR_PATH.read_text(encoding="utf-8"))
    validate_evidence_manifest()
    raw, normalized = validate_sbom()
    replay_receipt_sha256 = validate_replay_contract()
    validate_candidate_receipt(
        raw,
        normalized,
        full_row_digest,
        replay_receipt_sha256,
    )
    validate_bridge()
    snapshot = load_and_validate()
    validate_catalog_checkpoint(
        snapshot.manifest.get("catalog_version"),
        len(snapshot.assets),
        len(snapshot.queries),
    )
    required = {
        "CTRL-TASK-04-001", "CTRL-HANDOFF-PROTOCOL-001", "ADR-MVP-STACK-002",
        "MATRIX-T04-MVP-STACK-001", "EVIDENCE-T04-RESEARCH-ACCEPTANCE-001",
        "PROTOTYPE-T04-CORE-NATIVE-STACK-001", "FIXTURE-T04-PIT-001",
        "EVIDENCE-T04-A4R-WORK-ACCEPTANCE-001", "SBOM-T04-CORE-STACK-001",
        "VALIDATOR-T04-ARCHITECTURE-001", "EVIDENCE-T04-A5A-CANDIDATE-001",
    }
    if not required.issubset(snapshot.assets):
        raise Task04ValidationError("catalog_mandatory_task04_asset_missing")
    return full_row_digest, replay_receipt_sha256


def main() -> int:
    print("=== TASK-04 ATOM 5A VALIDATION ===")
    try:
        full_row_digest, replay_receipt_sha256 = validate()
    except Exception as exc:
        print("TASK04_RESULT: FAIL")
        print(f"ERROR_TYPE: {type(exc).__name__}")
        print(f"ERROR: {exc}")
        return 1
    print("dependency_group_separation: PASS")
    print("matrix_rows: 52")
    print("reuse_decision_record_count: 52")
    print("production_lifecycle_record_count: 0")
    print("prototype_and_sbom: PASS")
    print(f"matrix_full_row_sha256: {full_row_digest}")
    print(f"replay_receipt_sha256: {replay_receipt_sha256}")
    print("provider_api_rpc_calls: 0")
    print("cash_spend_usd: 0")
    print("TASK04_RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
