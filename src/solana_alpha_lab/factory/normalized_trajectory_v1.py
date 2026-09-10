"""Pure, dormant NORMALIZED_TRAJECTORY_V1 projection.

This module intentionally has no collector, ResearchStore, HFIC, provider, or
CLI dependency.  It accepts already typed schedule-bound observations and
returns an anonymous, deterministic cohort motif histogram.  The public
payload contains no member identity and never exposes raw values.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import InitVar, dataclass, field
from datetime import UTC, datetime, timedelta
from numbers import Real
from types import MappingProxyType
from typing import Any

from solana_alpha_lab.factory.observation_schedule import (
    schedule_sha256 as canonical_observation_schedule_sha256,
)
from solana_alpha_lab.factory.run_passport import canonical_json_bytes, canonical_sha256

REPRESENTATION_ID = "NORMALIZED_TRAJECTORY_V1"
REPRESENTATION_VERSION = "1.0"
PACKET_KEY = "normalized_trajectory_v1"
PREFERRED_SCHEDULE_ID = "OBS-ALWAYS-ON-TOKENS-V2-LIFECYCLE-21D-001"
ALLOWED_X_POINTS = (300, 600, 900)
PREFERRED_X_SECONDS = 300
MIN_X_LIQUIDITY_USD = 1000.0
DECLARED_Y_POINTS = (900, 1800, 3600, 7200, 14400, 43200, 86400)
DECISION_T_DUE_OFFSET_SECONDS = 1800
MIN_MOTIF_STEPS = 2
MIN_PREFIX_SLOTS = 3
MAX_DISTINCT_MOTIF_TUPLES = 8
_HASH64_RE = re.compile(r"^[0-9a-f]{64}$")
_REPRESENTATION_CONSTRUCTION_TOKEN = object()

FIELD_IDS = {
    "PRICE": "FIELD-USD-PRICE-001",
    "LIQUIDITY": "FIELD-LIQUIDITY-USD-001",
    "VOLUME": "FIELD-STATS5M-TAKER-VOLUME-001",
    "VOLUME_BUY": "FIELD-STATS5M-BUY-VOLUME-001",
    "VOLUME_SELL": "FIELD-STATS5M-SELL-VOLUME-001",
    "TRADERS": "FIELD-STATS5M-NUM-TRADERS-001",
}
_FIELD_TO_CHANNEL = {value: key for key, value in FIELD_IDS.items()}
_BASE_CHANNELS = ("PRICE", "LIQUIDITY", "TRADERS")
_FORBIDDEN_OUTPUT_KEYS = {
    "member_id",
    "mint",
    "mint_address",
    "wallet",
    "raw_value",
    "raw_values",
    "observations",
    "sequences",
    "trajectory",
}

_CANONICAL_SCHEDULE_KEYS = frozenset(
    {
        "schema",
        "schema_version",
        "schedule_key",
        "activation",
        "source_poll",
        "population",
        "sampling",
        "x_point",
        "y_points",
        "missingness",
        "disappearance",
        "budgets",
        "retention",
        "authority",
        "outputs",
    }
)

# This is a deliberately synthetic, deterministic schedule used only by the
# pure fixture path when no imported corpus is supplied.  Imported callers
# must provide the full canonical ObservationSchedule document or its verified
# schedule/corpus binding; the representation never invents a live schedule
# digest from the four projection offsets.
_SYNTHETIC_SCHEDULE_DOCUMENT: dict[str, object] = {
    "schema": "smial.observation-schedule",
    "schema_version": "1.0",
    "schedule_key": PREFERRED_SCHEDULE_ID,
    "activation": {
        "starts_at": "2026-01-01T00:00:00Z",
        "stops_admitting_at": "2026-01-22T00:00:00Z",
        "cadence_alignment": "UTC_EPOCH",
    },
    "source_poll": {
        "primitive_id": "PRIM-JUPITER-TOKENS-V2-RECENT-001",
        "query_profile_id": "QUERY-JUPITER-PUMPFUN-RECENT-001",
        "period_seconds": 60,
        "enabled": True,
    },
    "population": {
        "entity_type": "TOKEN_MINT",
        "entity_key_field_id": "FIELD-TOKEN-MINT-001",
        "anchor_field_id": "FIELD-FIRST-POOL-CREATED-AT-001",
        "scheduling_fallback": "FIRST_SEEN_AT_ONLY",
        "source_predicates": [
            {
                "field_id": "FIELD-LAUNCHPAD-001",
                "operator": "EQ",
                "value_text": "pump.fun",
            }
        ],
        "x_eligibility_predicates": [
            {
                "field_id": "FIELD-LIQUIDITY-USD-001",
                "operator": "GTE",
                "value_decimal": "1000",
            }
        ],
    },
    "sampling": {
        "policy": "DETERMINISTIC_HASH_BERNOULLI",
        "seed": "SYNTHETIC-LIFECYCLE-FIXTURE-001",
        "inclusion_probability": "1.0",
        "max_candidates_per_utc_day": 1,
        "max_members_per_utc_day": 1,
        "overflow_state": "NOT_SELECTED_CAPACITY",
    },
    "x_point": {
        "point_id": "X300",
        "due_offset_seconds": PREFERRED_X_SECONDS,
        "allowed_lateness_seconds": 300,
        "bundle_ids": ["BUNDLE-FIXTURE-LIFECYCLE-001"],
    },
    "y_points": [
        {
            "point_id": f"Y{offset}",
            "due_offset_seconds": offset,
            "allowed_lateness_seconds": 300,
            "bundle_ids": ["BUNDLE-FIXTURE-LIFECYCLE-001"],
        }
        for offset in DECLARED_Y_POINTS
    ],
    "missingness": {
        "value_policy": "TYPED_NULL_NO_IMPUTATION",
        "unknown_is_zero": False,
        "missing_point_deletes_member": False,
        "continue_later_points_after_missing": True,
    },
    "disappearance": {
        "default": "CONTINUE_UNTIL_FINAL_HORIZON",
        "single_absence_is_terminal": False,
        "explicit_registered_terminal": "CENSOR_REMAINING_POINTS",
    },
    "budgets": {
        "cash_usd_max": "0",
        "provider_calls_per_tick_max": 60,
        "provider_calls_per_utc_day_max": 1,
        "provider_calls_lifetime_max": 1,
        "modeled_provider_credits_per_utc_day_max": 1,
        "raw_bytes_per_utc_day_max": 1,
        "canonical_bytes_lifetime_max": 1,
        "min_provider_pace_seconds": 3,
        "retry": False,
        "fallback": False,
    },
    "retention": {
        "raw_retention_days": 31,
        "canonical_panel_retention": "IMMUTABLE",
        "active_journal_backup": "REQUIRED",
    },
    "authority": {
        "profile_id": "AUTH-PROVIDER-READONLY-ZERO-CASH-SCHEDULE-V1",
        "activation_receipt_required": True,
    },
    "outputs": {
        "membership_schema_id": "SCHEMA-OBSERVATION-PANEL-MEMBER-001",
        "observation_index_schema_id": "SCHEMA-OBSERVATION-PANEL-INDEX-001",
        "partition_period": "UTC_DAY",
        "publication": "MANIFEST_LAST",
    },
}
_SYNTHETIC_SCHEDULE_SHA256 = canonical_observation_schedule_sha256(
    _SYNTHETIC_SCHEDULE_DOCUMENT
)
_SYNTHETIC_ACTIVATION_ID = "SYNTHETIC-ACTIVATION-001"


class NormalizedTrajectoryError(ValueError):
    """Fail-closed error for invalid typed input or frozen schedule shape."""


def _require_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise NormalizedTrajectoryError(f"{name.upper()}_INVALID")
    return value


def _require_aware_datetime(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise NormalizedTrajectoryError(f"{name.upper()}_MUST_BE_AWARE")
    return value.astimezone(UTC)


def _parse_datetime(name: str, value: object, *, allow_none: bool) -> datetime | None:
    if value is None and allow_none:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))  # noqa: FURB162
        except ValueError as exc:
            raise NormalizedTrajectoryError(f"{name.upper()}_INVALID") from exc
    if not isinstance(value, datetime):
        raise NormalizedTrajectoryError(f"{name.upper()}_INVALID")
    return _require_aware_datetime(name, value)


def _is_typed_numeric(value: object) -> bool:
    """Accept only already-typed numeric values; never coerce text to data."""

    return isinstance(value, Real) and not isinstance(value, bool)


def _is_positive_finite(value: object) -> bool:
    if not _is_typed_numeric(value):
        return False
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(numeric) and numeric > 0.0


def _is_finite_numeric(value: object) -> bool:
    if not _is_typed_numeric(value):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def _is_observed_at_cutoff(
    observation: TypedLifecycleObservation | None,
    *,
    cutoff: datetime,
) -> bool:
    """Distinguish an observed non-positive value from a missing channel."""

    if observation is None or not observation.observed:
        return False
    if observation.first_reliable_available_at is None:
        return False
    if observation.first_reliable_available_at > cutoff:
        return False
    return observation.value is not None and _is_finite_numeric(observation.value)


@dataclass(frozen=True)
class LifecycleCorpusBinding:
    """Release/readback identity carried with one representation input."""

    release_id: str
    cohort_id: str
    schedule_sha256: str
    activation_id: str
    producer_git_sha: str
    source_sha256: str
    census_sha256: str
    observations_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "release_id",
            "schedule_sha256",
            "source_sha256",
            "census_sha256",
            "observations_sha256",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or _HASH64_RE.fullmatch(value) is None:
                raise NormalizedTrajectoryError(f"{name.upper()}_INVALID")
        for name in ("cohort_id", "activation_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise NormalizedTrajectoryError(f"{name.upper()}_INVALID")
        if (
            not isinstance(self.producer_git_sha, str)
            or len(self.producer_git_sha) != 40
            or any(char not in "0123456789abcdef" for char in self.producer_git_sha)
        ):
            raise NormalizedTrajectoryError("PRODUCER_GIT_SHA_INVALID")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> LifecycleCorpusBinding:
        if not isinstance(value, Mapping):
            raise NormalizedTrajectoryError("CORPUS_BINDING_INVALID")
        expected = {
            "release_id",
            "cohort_id",
            "schedule_sha256",
            "activation_id",
            "producer_git_sha",
            "source_sha256",
            "census_sha256",
            "observations_sha256",
        }
        if set(value) != expected:
            raise NormalizedTrajectoryError("CORPUS_BINDING_INVALID")
        return cls(**{key: value[key] for key in expected})  # type: ignore[arg-type]

    def as_dict(self) -> dict[str, str]:
        return {
            "release_id": self.release_id,
            "cohort_id": self.cohort_id,
            "schedule_sha256": self.schedule_sha256,
            "activation_id": self.activation_id,
            "producer_git_sha": self.producer_git_sha,
            "source_sha256": self.source_sha256,
            "census_sha256": self.census_sha256,
            "observations_sha256": self.observations_sha256,
        }


def _synthetic_corpus_binding() -> LifecycleCorpusBinding:
    return LifecycleCorpusBinding(
        release_id=canonical_sha256(
            {
                "kind": "SYNTHETIC_LIFECYCLE_FIXTURE",
                "schedule_sha256": _SYNTHETIC_SCHEDULE_SHA256,
                "activation_id": _SYNTHETIC_ACTIVATION_ID,
            }
        ),
        cohort_id="SYNTHETIC-COHORT-001",
        schedule_sha256=_SYNTHETIC_SCHEDULE_SHA256,
        activation_id=_SYNTHETIC_ACTIVATION_ID,
        producer_git_sha="0" * 40,
        source_sha256=canonical_sha256({"kind": "SYNTHETIC_SOURCE"}),
        census_sha256=canonical_sha256({"kind": "SYNTHETIC_CENSUS"}),
        observations_sha256=canonical_sha256({"kind": "SYNTHETIC_OBSERVATIONS"}),
    )


@dataclass(frozen=True)
class LifecycleSchedule:
    """The imported ObservationSchedule shape needed by the frozen preregistration."""

    schedule_id: str = PREFERRED_SCHEDULE_ID
    x_due_offset_seconds: int = PREFERRED_X_SECONDS
    y_due_offset_seconds: tuple[int, ...] = DECLARED_Y_POINTS
    decision_t_due_offset_seconds: int = DECISION_T_DUE_OFFSET_SECONDS
    schedule_sha256: str = _SYNTHETIC_SCHEDULE_SHA256
    activation_id: str = _SYNTHETIC_ACTIVATION_ID
    corpus_binding: LifecycleCorpusBinding | Mapping[str, object] | None = None
    schedule_document: InitVar[Mapping[str, object] | None] = None

    def __post_init__(self, schedule_document: Mapping[str, object] | None) -> None:
        if not isinstance(self.schedule_id, str) or not self.schedule_id:
            raise NormalizedTrajectoryError("SCHEDULE_ID_INVALID")
        if self.schedule_id != PREFERRED_SCHEDULE_ID:
            raise NormalizedTrajectoryError("SCHEDULE_ID_NOT_FROZEN")
        x_point = _require_int("x_due_offset_seconds", self.x_due_offset_seconds)
        if x_point not in ALLOWED_X_POINTS:
            raise NormalizedTrajectoryError("INVALID_X_SELECTION")
        decision_t = _require_int(
            "decision_t_due_offset_seconds", self.decision_t_due_offset_seconds
        )
        if decision_t != DECISION_T_DUE_OFFSET_SECONDS:
            raise NormalizedTrajectoryError("DECISION_T_INVALID")
        y_points = tuple(
            _require_int("y_due_offset_seconds", point)
            for point in self.y_due_offset_seconds
        )
        if tuple(sorted(set(y_points))) != y_points:
            raise NormalizedTrajectoryError("Y_POINTS_NOT_SORTED_OR_UNIQUE")
        if y_points != DECLARED_Y_POINTS:
            raise NormalizedTrajectoryError("Y_POINTS_NOT_FROZEN")
        if 900 not in y_points or decision_t not in y_points:
            raise NormalizedTrajectoryError("REQUIRED_Y_POINTS_MISSING")
        if x_point >= 900 or len(self.prefix_due_offsets) < MIN_PREFIX_SLOTS:
            raise NormalizedTrajectoryError("INVALID_INSUFFICIENT_PREFIX")
        if x_point in y_points:
            raise NormalizedTrajectoryError("X_DUPLICATES_Y_POINT")
        if any(point <= 0 for point in y_points):
            raise NormalizedTrajectoryError("Y_POINT_INVALID")
        if not isinstance(self.schedule_sha256, str) or _HASH64_RE.fullmatch(
            self.schedule_sha256
        ) is None:
            raise NormalizedTrajectoryError("SCHEDULE_SHA256_INVALID")
        if (
            self.schedule_sha256 == _SYNTHETIC_SCHEDULE_SHA256
            and x_point != PREFERRED_X_SECONDS
        ):
            raise NormalizedTrajectoryError("SCHEDULE_SHA256_MISMATCH")
        if not isinstance(self.activation_id, str) or not self.activation_id.strip():
            raise NormalizedTrajectoryError("ACTIVATION_ID_INVALID")
        if schedule_document is not None:
            if not isinstance(schedule_document, Mapping) or not _CANONICAL_SCHEDULE_KEYS.issubset(
                schedule_document
            ):
                raise NormalizedTrajectoryError("SCHEDULE_DOCUMENT_INVALID")
            document_schedule_id = schedule_document.get("schedule_key")
            document_x_point = schedule_document.get("x_point")
            document_y_points = schedule_document.get("y_points")
            if (
                not isinstance(document_schedule_id, str)
                or not isinstance(document_x_point, Mapping)
                or not isinstance(document_y_points, (list, tuple))
            ):
                raise NormalizedTrajectoryError("SCHEDULE_DOCUMENT_INVALID")
            document_x_due = document_x_point.get("due_offset_seconds")
            document_y_due = tuple(
                point.get("due_offset_seconds")
                for point in document_y_points
                if isinstance(point, Mapping)
            )
            if (
                document_schedule_id != self.schedule_id
                or document_x_due != x_point
                or len(document_y_due) != len(document_y_points)
                or document_y_due != y_points
            ):
                raise NormalizedTrajectoryError(
                    "SCHEDULE_DOCUMENT_BINDING_MISMATCH"
                )
            try:
                expected_schedule_sha256 = canonical_observation_schedule_sha256(
                    schedule_document
                )
            except (TypeError, ValueError):
                raise NormalizedTrajectoryError("SCHEDULE_DOCUMENT_INVALID") from None
            if self.schedule_sha256 != expected_schedule_sha256:
                raise NormalizedTrajectoryError("SCHEDULE_SHA256_MISMATCH")
        elif self.schedule_sha256 != _SYNTHETIC_SCHEDULE_SHA256 and self.corpus_binding is None:
            raise NormalizedTrajectoryError("SCHEDULE_DOCUMENT_REQUIRED")

        binding = self.corpus_binding
        if binding is None:
            if (
                self.schedule_sha256 != _SYNTHETIC_SCHEDULE_SHA256
                or self.activation_id != _SYNTHETIC_ACTIVATION_ID
            ):
                raise NormalizedTrajectoryError("CORPUS_BINDING_REQUIRED")
            binding = _synthetic_corpus_binding()
        elif not isinstance(binding, LifecycleCorpusBinding):
            binding = LifecycleCorpusBinding.from_mapping(binding)
        if (
            binding.schedule_sha256 != self.schedule_sha256
            or binding.activation_id != self.activation_id
        ):
            raise NormalizedTrajectoryError("CORPUS_BINDING_MISMATCH")
        object.__setattr__(self, "corpus_binding", binding)

    @property
    def prefix_due_offsets(self) -> tuple[int, ...]:
        return tuple(
            sorted(
                (self.x_due_offset_seconds,)
                + tuple(
                    point
                    for point in self.y_due_offset_seconds
                    if point <= self.decision_t_due_offset_seconds
                )
            )
        )

    @property
    def all_due_offsets(self) -> tuple[int, ...]:
        return tuple(sorted((self.x_due_offset_seconds,) + self.y_due_offset_seconds))

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> LifecycleSchedule:
        if not isinstance(value, Mapping):
            raise NormalizedTrajectoryError("SCHEDULE_INVALID")
        y_points = value.get("y_due_offset_seconds")
        if y_points is None:
            y_points = value.get("declared_y_due_offset_seconds")
        if y_points is None and isinstance(value.get("y_points"), (list, tuple)):
            y_points = tuple(
                point.get("due_offset_seconds")
                for point in value["y_points"]
                if isinstance(point, Mapping)
            )
        if y_points is None:
            y_points = DECLARED_Y_POINTS
        if not isinstance(y_points, (list, tuple)):
            raise NormalizedTrajectoryError("Y_POINTS_INVALID")
        x_point = value.get("x_due_offset_seconds")
        if x_point is None and isinstance(value.get("x_point"), Mapping):
            x_point = value["x_point"].get("due_offset_seconds")
        schedule_id = value.get(
            "schedule_id", value.get("schedule_key", PREFERRED_SCHEDULE_ID)
        )
        if not isinstance(schedule_id, str):
            raise NormalizedTrajectoryError("SCHEDULE_ID_INVALID")
        canonical_document = None
        if _CANONICAL_SCHEDULE_KEYS.issubset(value):
            canonical_document = {
                key: deepcopy(value[key]) for key in _CANONICAL_SCHEDULE_KEYS
            }
        return cls(
            schedule_id=schedule_id,
            x_due_offset_seconds=(
                PREFERRED_X_SECONDS if x_point is None else x_point
            ),
            y_due_offset_seconds=tuple(y_points),
            decision_t_due_offset_seconds=value.get(
                "decision_t_due_offset_seconds", DECISION_T_DUE_OFFSET_SECONDS
            ),
            schedule_sha256=value.get("schedule_sha256", _SYNTHETIC_SCHEDULE_SHA256),
            activation_id=value.get("activation_id", _SYNTHETIC_ACTIVATION_ID),
            corpus_binding=value.get("corpus_binding"),
            schedule_document=canonical_document,
        )


DEFAULT_SCHEDULE = LifecycleSchedule()


@dataclass(frozen=True)
class TypedLifecycleObservation:
    """One schedule-bound typed observation.

    ``member_id`` is an internal grouping key only.  It is never copied into
    the representation payload.
    """

    member_id: str
    member_anchor_at: datetime
    due_offset_seconds: int
    field_id: str
    value: object | None
    first_reliable_available_at: datetime | None
    observed: bool = True
    schedule_sha256: str | None = None
    activation_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.member_id, str) or not self.member_id:
            raise NormalizedTrajectoryError("MEMBER_KEY_INVALID")
        object.__setattr__(
            self,
            "member_anchor_at",
            _require_aware_datetime("member_anchor_at", self.member_anchor_at),
        )
        object.__setattr__(
            self,
            "first_reliable_available_at",
            _require_aware_datetime(
                "first_reliable_available_at", self.first_reliable_available_at
            )
            if self.first_reliable_available_at is not None
            else None,
        )
        _require_int("due_offset_seconds", self.due_offset_seconds)
        if self.field_id not in _FIELD_TO_CHANNEL:
            raise NormalizedTrajectoryError("FIELD_ID_NOT_ALLOWED")
        if not isinstance(self.observed, bool):
            raise NormalizedTrajectoryError("OBSERVED_INVALID")
        if self.value is not None and not _is_typed_numeric(self.value):
            raise NormalizedTrajectoryError("VALUE_MUST_BE_TYPED_NUMERIC_OR_NULL")
        if not isinstance(self.schedule_sha256, str) or _HASH64_RE.fullmatch(
            self.schedule_sha256
        ) is None:
            raise NormalizedTrajectoryError("OBSERVATION_SCHEDULE_BINDING_MISSING")
        if not isinstance(self.activation_id, str) or not self.activation_id.strip():
            raise NormalizedTrajectoryError("OBSERVATION_ACTIVATION_BINDING_MISSING")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> TypedLifecycleObservation:
        if not isinstance(value, Mapping):
            raise NormalizedTrajectoryError("OBSERVATION_INVALID")
        member_id = value.get("member_id", value.get("member_key"))
        anchor = value.get("member_anchor_at", value.get("anchor_at"))
        due = value.get("due_offset_seconds")
        field_id = value.get("field_id")
        schedule_sha256 = value.get("schedule_sha256")
        activation_id = value.get("activation_id")
        if member_id is None or anchor is None or due is None or field_id is None:
            raise NormalizedTrajectoryError("OBSERVATION_REQUIRED_FIELD_MISSING")
        if not isinstance(member_id, str) or not member_id:
            raise NormalizedTrajectoryError("MEMBER_KEY_INVALID")
        if not isinstance(field_id, str):
            raise NormalizedTrajectoryError("FIELD_ID_NOT_ALLOWED")
        if schedule_sha256 is None or activation_id is None:
            raise NormalizedTrajectoryError("OBSERVATION_SCHEDULE_BINDING_MISSING")
        return cls(
            member_id=member_id,
            member_anchor_at=_parse_datetime("member_anchor_at", anchor, allow_none=False),
            due_offset_seconds=due,
            field_id=field_id,
            value=value.get("value"),
            first_reliable_available_at=_parse_datetime(
                "first_reliable_available_at",
                value.get("first_reliable_available_at"),
                allow_none=True,
            ),
            observed=value.get("observed", True),
            schedule_sha256=schedule_sha256,
            activation_id=activation_id,
        )


def _coerce_schedule(
    schedule: LifecycleSchedule | Mapping[str, object] | None,
) -> LifecycleSchedule:
    if schedule is None:
        return DEFAULT_SCHEDULE
    if isinstance(schedule, LifecycleSchedule):
        return schedule
    return LifecycleSchedule.from_mapping(schedule)


def _coerce_observation(value: TypedLifecycleObservation | Mapping[str, object]) -> TypedLifecycleObservation:
    if isinstance(value, TypedLifecycleObservation):
        return value
    return TypedLifecycleObservation.from_mapping(value)


def _valid_at_cutoff(
    observation: TypedLifecycleObservation | None,
    *,
    cutoff: datetime,
) -> bool:
    if observation is None or not observation.observed:
        return False
    available_at = observation.first_reliable_available_at
    if available_at is None or available_at > cutoff:
        return False
    return _is_positive_finite(observation.value)


def _transition_motif(
    rows: Mapping[int, TypedLifecycleObservation],
    *,
    prefix_slots: tuple[int, ...],
    cutoff: datetime,
) -> str:
    values: list[object | None] = []
    for slot in prefix_slots:
        row = rows.get(slot)
        values.append(row.value if _valid_at_cutoff(row, cutoff=cutoff) else None)

    first_value = next((value for value in values if _is_positive_finite(value)), None)
    normalized: list[float | None] = []
    for value in values:
        if not _is_positive_finite(value) or first_value is None:
            normalized.append(None)
            continue
        try:
            ratio = float(value) / float(first_value)
            normalized_value = math.log(ratio)
        except (TypeError, ValueError, OverflowError, ZeroDivisionError):
            normalized_value = math.nan
        normalized.append(normalized_value if math.isfinite(normalized_value) else None)

    symbols: list[str] = []
    for index in range(1, len(values)):
        previous = values[index - 1]
        current = values[index]
        previous_normalized = normalized[index - 1]
        current_normalized = normalized[index]
        if (
            previous is None
            or current is None
            or previous_normalized is None
            or current_normalized is None
        ):
            symbols.append("M")
        elif current == previous:
            symbols.append("F")
        elif current_normalized > previous_normalized:
            symbols.append("U")
        else:
            symbols.append("D")
    return "-".join(symbols)


def _missing_transition_count(
    motif: tuple[tuple[str, str], ...],
) -> int:
    return sum(symbol.split("-").count("M") for _channel, symbol in motif)


def _contains_forbidden_output_key(value: object) -> bool:
    if isinstance(value, Mapping):
        if any(str(key).lower() in _FORBIDDEN_OUTPUT_KEYS for key in value):
            return True
        return any(_contains_forbidden_output_key(child) for child in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_output_key(child) for child in value)
    return False


def _freeze_payload(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _freeze_payload(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_payload(item) for item in value)
    return value


def _thaw_payload(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_payload(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_payload(item) for item in value]
    return value


@dataclass(frozen=True)
class NormalizedTrajectoryRepresentation:
    """Immutable view over the anonymous representation payload."""

    _base_payload: Mapping[str, Any]
    _construction_token: object | None = field(default=None, repr=False, compare=False)
    _sealed_payload_sha256: str | None = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if self._construction_token is not _REPRESENTATION_CONSTRUCTION_TOKEN:
            raise NormalizedTrajectoryError("REPRESENTATION_CONSTRUCTION_FORBIDDEN")
        if not isinstance(self._base_payload, Mapping):
            raise NormalizedTrajectoryError("REPRESENTATION_PAYLOAD_INVALID")
        thawed = _thaw_payload(self._base_payload)
        if not isinstance(thawed, Mapping):
            raise NormalizedTrajectoryError("REPRESENTATION_PAYLOAD_INVALID")
        payload = deepcopy(dict(thawed))
        if _contains_forbidden_output_key(payload) or "payload_sha256" in payload:
            raise NormalizedTrajectoryError("IDENTITY_LEAK_IN_REPRESENTATION")
        payload_sha256 = canonical_sha256(payload)
        if (
            self._sealed_payload_sha256 is not None
            and self._sealed_payload_sha256 != payload_sha256
        ):
            raise NormalizedTrajectoryError("REPRESENTATION_PROVENANCE_DRIFT")
        object.__setattr__(self, "_base_payload", _freeze_payload(payload))
        object.__setattr__(self, "_sealed_payload_sha256", payload_sha256)

    @property
    def payload_sha256(self) -> str:
        assert self._sealed_payload_sha256 is not None
        return self._sealed_payload_sha256

    @property
    def payload(self) -> dict[str, Any]:
        thawed = _thaw_payload(self._base_payload)
        if not isinstance(thawed, dict):
            raise NormalizedTrajectoryError("REPRESENTATION_PAYLOAD_INVALID")
        payload = thawed
        payload["payload_sha256"] = self.payload_sha256
        return payload

    def as_packet(self) -> dict[str, Any]:
        return self.payload


def project_normalized_trajectory(
    observations: Sequence[TypedLifecycleObservation | Mapping[str, object]],
    *,
    schedule: LifecycleSchedule | Mapping[str, object] | None = None,
) -> NormalizedTrajectoryRepresentation:
    """Project typed observations into the frozen anonymous V1 representation."""

    bound_schedule = _coerce_schedule(schedule)
    typed = [_coerce_observation(item) for item in observations]
    prefix_slots = bound_schedule.prefix_due_offsets
    cutoff_delta = timedelta(seconds=bound_schedule.decision_t_due_offset_seconds)
    grouped: dict[str, dict[tuple[int, str], TypedLifecycleObservation]] = defaultdict(dict)

    for row in typed:
        if row.due_offset_seconds not in bound_schedule.all_due_offsets:
            raise NormalizedTrajectoryError("OBSERVATION_NOT_BOUND_TO_SCHEDULE")
        if row.schedule_sha256 != bound_schedule.schedule_sha256:
            raise NormalizedTrajectoryError("OBSERVATION_SCHEDULE_BINDING_MISMATCH")
        if row.activation_id != bound_schedule.activation_id:
            raise NormalizedTrajectoryError("OBSERVATION_ACTIVATION_BINDING_MISMATCH")
        key = (row.due_offset_seconds, row.field_id)
        if key in grouped[row.member_id]:
            raise NormalizedTrajectoryError("DUPLICATE_TYPED_OBSERVATION")
        grouped[row.member_id][key] = row

    for rows in grouped.values():
        anchors = {row.member_anchor_at for row in rows.values()}
        if len(anchors) != 1:
            raise NormalizedTrajectoryError("MEMBER_ANCHOR_DRIFT")

    future_only_members = sorted(
        member_id
        for member_id, rows in grouped.items()
        if not any(due in prefix_slots for due, _field_id in rows)
    )
    if future_only_members:
        raise NormalizedTrajectoryError("FUTURE_ONLY_MEMBER_NOT_BOUND_TO_PREFIX")

    def x_eligible(rows: Mapping[tuple[int, str], TypedLifecycleObservation]) -> bool:
        liquidity = rows.get(
            (bound_schedule.x_due_offset_seconds, FIELD_IDS["LIQUIDITY"])
        )
        if liquidity is None:
            return False
        anchor = next(iter(rows.values())).member_anchor_at
        x_cutoff = anchor + timedelta(seconds=bound_schedule.x_due_offset_seconds)
        return _valid_at_cutoff(liquidity, cutoff=x_cutoff) and float(
            liquidity.value
        ) >= MIN_X_LIQUIDITY_USD

    grouped = {
        member_id: rows
        for member_id, rows in grouped.items()
        if x_eligible(rows)
    }

    cutoff_by_member = {
        member_id: next(iter(rows.values())).member_anchor_at
        + cutoff_delta
        for member_id, rows in grouped.items()
    }

    def rows_for(member_id: str, field_id: str) -> dict[int, TypedLifecycleObservation]:
        return {
            due: row
            for (due, current_field_id), row in grouped[member_id].items()
            if current_field_id == field_id and due in prefix_slots
        }

    def field_has_observed_channel(field_id: str) -> bool:
        return any(
            _is_observed_at_cutoff(row, cutoff=cutoff_by_member[member_id])
            for member_id in grouped
            for row in rows_for(member_id, field_id).values()
        )

    taker_available = field_has_observed_channel(FIELD_IDS["VOLUME"])
    buy_available = field_has_observed_channel(FIELD_IDS["VOLUME_BUY"])
    sell_available = field_has_observed_channel(FIELD_IDS["VOLUME_SELL"])
    if taker_available:
        volume_channels = ("VOLUME",)
        volume_mode = "TAKER_OBSERVED"
    elif buy_available and sell_available:
        volume_channels = ("VOLUME_BUY", "VOLUME_SELL")
        volume_mode = "ACTIVITY_VOLUME_OBSERVED_BUY_PLUS_SELL"
    else:
        volume_channels = ("VOLUME",)
        volume_mode = "UNAVAILABLE"

    channels = (*_BASE_CHANNELS[:2], *volume_channels, _BASE_CHANNELS[2])
    motif_counts: dict[tuple[tuple[str, str], ...], int] = defaultdict(int)
    for member_id in sorted(grouped):
        cutoff = cutoff_by_member[member_id]
        motif: dict[str, str] = {}
        for channel in channels:
            field_id = FIELD_IDS[channel]
            motif[channel] = _transition_motif(
                rows_for(member_id, field_id),
                prefix_slots=prefix_slots,
                cutoff=cutoff,
            )
        motif_counts[tuple(motif.items())] += 1

    def motif_rank(item: tuple[tuple[tuple[str, str], ...], int]) -> tuple[object, ...]:
        return (-item[1], canonical_json_bytes(dict(item[0])))

    ranked = sorted(motif_counts.items(), key=motif_rank)
    retained = ranked[:MAX_DISTINCT_MOTIF_TUPLES]
    m_heavy_candidates = [
        item
        for item in ranked
        if _missing_transition_count(item[0]) > 0
    ]
    m_heavy = min(
        m_heavy_candidates,
        key=lambda item: (
            -_missing_transition_count(item[0]),
            motif_rank(item),
        ),
    ) if m_heavy_candidates else None
    if m_heavy is not None and not any(item[0] == m_heavy[0] for item in retained):
        if len(retained) < MAX_DISTINCT_MOTIF_TUPLES:
            retained.append(m_heavy)
        else:
            retained[-1] = m_heavy
        retained = sorted(retained, key=motif_rank)
    histogram = [
        {"motif": dict(motif_items), "count": count}
        for motif_items, count in retained
    ]
    kept_member_count = sum(item[1] for item in retained)
    base_payload: dict[str, Any] = {
        "packet_schema": "smial.normalized-trajectory-v1",
        "representation_id": REPRESENTATION_ID,
        "representation_version": REPRESENTATION_VERSION,
        "schedule": {
            "schedule_id": bound_schedule.schedule_id,
            "activation_id": bound_schedule.activation_id,
            "x_due_offset_seconds": bound_schedule.x_due_offset_seconds,
            "declared_y_due_offset_seconds": list(bound_schedule.y_due_offset_seconds),
            "prefix_due_offset_seconds": list(prefix_slots),
            "decision_t_due_offset_seconds": bound_schedule.decision_t_due_offset_seconds,
        },
        "pit": {
            "cutoff": "member_anchor_plus_Y1800",
            "first_reliable_available_at_le_cutoff": True,
            "future_points_in_denominator": False,
            "lateness_window_does_not_extend_T": True,
        },
        "normalization": {
            "kind": "OWN_HISTORY_LOG_RATIO",
            "first_value": "first_admissible_prefix_point_with_strictly_positive_finite_observed_value",
            "invalid_or_nonpositive": "M",
            "interpolation": False,
            "imputation": False,
        },
        "motif": {
            "channels": list(channels),
            "alphabet": ["U", "F", "D", "M"],
            "min_steps": MIN_MOTIF_STEPS,
            "flat_rule": "EXACT_ZERO_CHANGE_ONLY",
            "missing_stays_missing": True,
        },
        "field_ids": {channel: FIELD_IDS[channel] for channel in channels},
        "volume_mode": volume_mode,
        "eligible_member_count": len(grouped),
        "histogram_member_count": kept_member_count,
        "histogram": histogram,
        "histogram_truncation": {
            "max_distinct_motif_tuples": MAX_DISTINCT_MOTIF_TUPLES,
            "retained_order": "count_desc_then_canonical_motif",
            "dropped_lowest_count_tuples": max(0, len(ranked) - len(retained)),
            "m_heavy_members_retained": m_heavy is None
            or any(item[0] == m_heavy[0] for item in retained),
        },
        "anonymous": True,
        "corpus_binding": bound_schedule.corpus_binding.as_dict(),
    }
    base_payload["schedule"]["schedule_sha256"] = bound_schedule.schedule_sha256
    if _contains_forbidden_output_key(base_payload):
        raise NormalizedTrajectoryError("IDENTITY_LEAK_IN_REPRESENTATION")
    return NormalizedTrajectoryRepresentation(
        base_payload,
        _construction_token=_REPRESENTATION_CONSTRUCTION_TOKEN,
    )


def build_representation(
    observations: Sequence[TypedLifecycleObservation | Mapping[str, object]],
    *,
    schedule: LifecycleSchedule | Mapping[str, object] | None = None,
) -> NormalizedTrajectoryRepresentation:
    """Short alias used by callers that already selected the V1 capability."""

    return project_normalized_trajectory(observations, schedule=schedule)


__all__ = [
    "ALLOWED_X_POINTS",
    "DECISION_T_DUE_OFFSET_SECONDS",
    "DECLARED_Y_POINTS",
    "DEFAULT_SCHEDULE",
    "FIELD_IDS",
    "MAX_DISTINCT_MOTIF_TUPLES",
    "MIN_MOTIF_STEPS",
    "MIN_PREFIX_SLOTS",
    "PACKET_KEY",
    "PREFERRED_SCHEDULE_ID",
    "PREFERRED_X_SECONDS",
    "REPRESENTATION_ID",
    "REPRESENTATION_VERSION",
    "LifecycleCorpusBinding",
    "LifecycleSchedule",
    "MIN_X_LIQUIDITY_USD",
    "NormalizedTrajectoryError",
    "NormalizedTrajectoryRepresentation",
    "TypedLifecycleObservation",
    "build_representation",
    "project_normalized_trajectory",
]
