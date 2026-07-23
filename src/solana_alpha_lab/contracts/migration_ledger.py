"""Thin ordered immutable migration ledger for TASK-05."""

from __future__ import annotations

import hashlib
import re
from enum import StrEnum
from pathlib import Path, PurePosixPath

from pydantic import Field, model_validator

from .schema_v1 import (
    ApplicationState,
    Hash64,
    MigrationKind,
    PositiveInt,
    StrictContractModel,
)


class MigrationLedgerError(RuntimeError):
    """Fail-closed ledger or evolution contract violation."""


class EvolutionOperation(StrEnum):
    INITIAL_SCHEMA = "INITIAL_SCHEMA"
    ADD_NULLABLE_COLUMN = "ADD_NULLABLE_COLUMN"
    WIDEN_TYPE = "WIDEN_TYPE"
    MAKE_NULLABLE = "MAKE_NULLABLE"
    NARROW_TYPE = "NARROW_TYPE"
    DROP_COLUMN = "DROP_COLUMN"
    MAKE_REQUIRED = "MAKE_REQUIRED"


class SchemaChange(StrictContractModel):
    operation: EvolutionOperation
    relation: str | None
    column: str | None
    from_type: str | None
    to_type: str | None

    @model_validator(mode="after")
    def validate_shape(self) -> SchemaChange:
        if self.operation == EvolutionOperation.INITIAL_SCHEMA:
            if any(
                value is not None
                for value in (
                    self.relation,
                    self.column,
                    self.from_type,
                    self.to_type,
                )
            ):
                raise ValueError("initial_schema_change_must_be_unscoped")
        elif self.operation == EvolutionOperation.ADD_NULLABLE_COLUMN:
            if (
                self.relation is None
                or self.column is None
                or self.from_type is not None
                or self.to_type is None
            ):
                raise ValueError("add_nullable_column_shape_invalid")
        elif self.operation == EvolutionOperation.WIDEN_TYPE:
            if (
                self.relation is None
                or self.column is None
                or self.from_type is None
                or self.to_type is None
            ):
                raise ValueError("widen_type_shape_invalid")
        elif self.relation is None or self.column is None:
            raise ValueError("column_change_scope_missing")
        return self


class MigrationLedgerEntry(StrictContractModel):
    migration_id: str = Field(pattern=r"^T05-[0-9]{4}-[A-Z0-9-]+$")
    migration_order: PositiveInt
    migration_kind: MigrationKind
    schema_version: str
    sql_path: str
    content_sha256: Hash64
    application_state: ApplicationState
    changes: tuple[SchemaChange, ...]

    @model_validator(mode="after")
    def validate_path_and_changes(self) -> MigrationLedgerEntry:
        path = PurePosixPath(self.sql_path)
        if (
            path.is_absolute()
            or ".." in path.parts
            or not path.parts
            or path.parts[0] != "migrations"
            or path.suffix != ".sql"
        ):
            raise ValueError("unsafe_migration_sql_path")
        if not self.changes:
            raise ValueError("migration_change_set_empty")
        return self


class MigrationLedger(StrictContractModel):
    ledger_version: str
    migrations: tuple[MigrationLedgerEntry, ...]

    @model_validator(mode="after")
    def validate_inventory(self) -> MigrationLedger:
        if self.ledger_version != "1.0":
            raise ValueError("unsupported_ledger_version")
        if not self.migrations:
            raise ValueError("migration_ledger_empty")
        ids = [entry.migration_id for entry in self.migrations]
        orders = [entry.migration_order for entry in self.migrations]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_migration_id")
        if len(orders) != len(set(orders)):
            raise ValueError("duplicate_migration_order")
        if orders != list(range(1, len(orders) + 1)):
            raise ValueError("migration_order_not_contiguous")
        for entry in self.migrations:
            validate_change_set(entry.changes)
        return self


_SIGNED_INTEGER_RANK = {
    "TINYINT": 1,
    "SMALLINT": 2,
    "INTEGER": 3,
    "BIGINT": 4,
    "HUGEINT": 5,
}
_DECIMAL_PATTERN = re.compile(r"^DECIMAL\((\d+),\s*(\d+)\)$")


def _safe_widening(from_type: str, to_type: str) -> bool:
    source = from_type.upper()
    target = to_type.upper()
    if source in _SIGNED_INTEGER_RANK and target in _SIGNED_INTEGER_RANK:
        return _SIGNED_INTEGER_RANK[target] > _SIGNED_INTEGER_RANK[source]
    if source == "UBIGINT" and target == "HUGEINT":
        return True
    source_decimal = _DECIMAL_PATTERN.fullmatch(source)
    target_decimal = _DECIMAL_PATTERN.fullmatch(target)
    if source_decimal and target_decimal:
        source_precision, source_scale = map(int, source_decimal.groups())
        target_precision, target_scale = map(int, target_decimal.groups())
        return (
            target_scale >= source_scale
            and target_precision - target_scale
            >= source_precision - source_scale
            and (target_precision, target_scale)
            != (source_precision, source_scale)
        )
    return False


def validate_change_set(changes: tuple[SchemaChange, ...]) -> None:
    """Reject unsafe or mislabeled schema evolution operations."""

    forbidden = {
        EvolutionOperation.NARROW_TYPE,
        EvolutionOperation.DROP_COLUMN,
        EvolutionOperation.MAKE_REQUIRED,
    }
    for change in changes:
        if change.operation in forbidden:
            raise MigrationLedgerError(f"unsafe_schema_change:{change.operation}")
        if change.operation == EvolutionOperation.WIDEN_TYPE and not _safe_widening(
            str(change.from_type),
            str(change.to_type),
        ):
            raise MigrationLedgerError(
                f"invalid_widening:{change.from_type}->{change.to_type}"
            )


def load_ledger(path: Path) -> MigrationLedger:
    """Load one strict UTF-8 JSON ledger."""

    return MigrationLedger.model_validate_json(path.read_bytes())


def verify_ledger_files(ledger: MigrationLedger, root: Path) -> None:
    """Verify every ledger path remains bounded and content-addressed."""

    resolved_root = root.resolve()
    for entry in ledger.migrations:
        candidate = (resolved_root / entry.sql_path).resolve()
        try:
            candidate.relative_to(resolved_root)
        except ValueError as exc:
            raise MigrationLedgerError("migration_path_escapes_repository") from exc
        if not candidate.is_file():
            raise MigrationLedgerError(f"migration_file_missing:{entry.migration_id}")
        observed = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if observed != entry.content_sha256:
            raise MigrationLedgerError(
                f"migration_checksum_mismatch:{entry.migration_id}"
            )


def _immutable_entry_payload(entry: MigrationLedgerEntry) -> dict[str, object]:
    payload = entry.model_dump(mode="json")
    payload.pop("application_state")
    return payload


def assert_ledger_evolution(
    previous: MigrationLedger,
    candidate: MigrationLedger,
) -> None:
    """Permit append-only growth and declared-to-terminal state transitions."""

    previous_by_id = {entry.migration_id: entry for entry in previous.migrations}
    candidate_by_id = {entry.migration_id: entry for entry in candidate.migrations}
    if not previous_by_id.keys() <= candidate_by_id.keys():
        raise MigrationLedgerError("migration_history_deleted")

    for migration_id, prior in previous_by_id.items():
        current = candidate_by_id[migration_id]
        if _immutable_entry_payload(prior) != _immutable_entry_payload(current):
            raise MigrationLedgerError(f"migration_history_mutated:{migration_id}")
        if prior.application_state == ApplicationState.APPLIED and current != prior:
            raise MigrationLedgerError(f"applied_migration_mutated:{migration_id}")
        if (
            prior.application_state != current.application_state
            and prior.application_state != ApplicationState.DECLARED
        ):
            raise MigrationLedgerError(
                f"terminal_migration_state_mutated:{migration_id}"
            )

    previous_count = len(previous.migrations)
    for index, entry in enumerate(candidate.migrations[:previous_count]):
        if entry.migration_id != previous.migrations[index].migration_id:
            raise MigrationLedgerError("migration_history_reordered")
