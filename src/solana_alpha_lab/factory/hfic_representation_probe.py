"""Dormant HFIC representation challenger adapter.

The adapter is deliberately separate from ordinary ``hfic_preflight`` and
``hfic_session``.  It validates an already-produced current CONTROL receipt,
clones its exact critic packet, and carries the compact representation in a
bounded challenger envelope.  It never reads ResearchStore, runs a session, or
changes the ordinary Forge budget.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from solana_alpha_lab.factory.hfic_control_integrity import (
    CASE_A_TERMINALS,
    CASE_C_KILL_TERMINALS,
    CURRENT_REPRESENTATION_CONTROL_V1,
    PROBE_PERMIT_TERMINALS,
    control_packet_has_raw_sequences,
    control_probe_permitted,
    effective_control_terminal,
)
from solana_alpha_lab.factory.early_market_panel_importer import (
    MIN_USABLE_YIELD_ELIGIBLE,
)
from solana_alpha_lab.factory.hfic_preflight import MAX_PACKET_BYTES
from solana_alpha_lab.factory.hfic_session import PROMPT_VERSION
from solana_alpha_lab.factory.normalized_trajectory_v1 import (
    ALLOWED_X_POINTS,
    DECISION_T_DUE_OFFSET_SECONDS,
    DECLARED_Y_POINTS,
    FIELD_IDS,
    MIN_MOTIF_STEPS,
    PACKET_KEY,
    PREFERRED_SCHEDULE_ID,
    REPRESENTATION_ID,
    REPRESENTATION_VERSION,
    NormalizedTrajectoryRepresentation,
)
from solana_alpha_lab.factory.run_passport import canonical_json_bytes, canonical_sha256


REPRESENTATION_PROBE_SCHEMA = "smial.hypothesis-representation-challenger"
REPRESENTATION_PROBE_VERSION = "1.0"
REPRESENTATION_PROBE_KIND = "REPRESENTATION_CHALLENGER"
MAX_CHALLENGER_RUNS_PER_CONTROL_EPOCH = 1
STATUS_CONTROL_REQUIRED = "CONTROL_REQUIRED"
STATUS_ELIGIBLE = "NORMALIZED_TRAJECTORY_V1_ELIGIBLE"
STATUS_MARKET_FALSIFIER_FIRST = "MARKET_FALSIFIER_FIRST"
STATUS_OBSERVABILITY_BLOCKED = "OBSERVABILITY_BLOCKED"
STATUS_RUNNER_UP_PAUSE = "RUNNER_UP_PAUSE"
STATUS_ALREADY_EXISTS = "REPRESENTATION_PROBE_ALREADY_EXISTS"
STATUS_COMPLETE = "REPRESENTATION_PROBE_COMPLETE"

CONTROL_REQUIRED = "CONTROL_REQUIRED"
INVALID_CONTROL_NOT_RUN = "INVALID_CONTROL_NOT_RUN"
INVALID_CONTROL_MODE = "INVALID_CONTROL_MODE"
INVALID_CONTROL_TRAJECTORY = "INVALID_CONTROL_TRAJECTORY"
INVALID_CONTROL_PACKET_HASH = "INVALID_CONTROL_PACKET_HASH"
INVALID_CONTROL_FOCUS = "INVALID_CONTROL_FOCUS"
INVALID_EVIDENCE_EPOCH_MISMATCH = "INVALID_EVIDENCE_EPOCH_MISMATCH"
INVALID_MEMORY_BASELINE_DRIFT = "INVALID_MEMORY_BASELINE_DRIFT"
INVALID_PACKET_BUDGET = "INVALID_PACKET_BUDGET"
INVALID_REPRESENTATION_ID = "INVALID_REPRESENTATION_ID"
INVALID_REPRESENTATION_HASH = "INVALID_REPRESENTATION_HASH"
INVALID_MINT_IDENTITY = "INVALID_MINT_IDENTITY"
INVALID_PROBE_IDENTITY = "INVALID_PROBE_IDENTITY"
INVALID_TRIGGER_NOT_MET = "INVALID_TRIGGER_NOT_MET"
INVALID_CASE_C_OBSERVABILITY = "INVALID_CASE_C_OBSERVABILITY"
INVALID_OBSERVABILITY_INPUT = "INVALID_OBSERVABILITY_INPUT"
INVALID_COHORT_READINESS_RECEIPT = "INVALID_COHORT_READINESS_RECEIPT"
REPRESENTATION_PROBE_ALREADY_EXISTS = "REPRESENTATION_PROBE_ALREADY_EXISTS"
INVALID_REPRESENTATION_SCHEMA = "INVALID_REPRESENTATION_SCHEMA"

_HASH64_RE = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_CONTROL_KEYS = {
    "observations",
    "sequences",
    "trajectory",
    "normalized_trajectory_v1",
    "raw_rows",
    "motif",
    "parquet_rows",
}
_FORBIDDEN_IDENTITY_KEYS = {
    "member_id",
    "mint",
    "mint_address",
    "wallet",
    "token_address",
}
_VERIFIED_BASELINE_TOKEN = object()
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_HFIC_PACKET_SCHEMA_PATH = (
    _REPOSITORY_ROOT / "catalog/schemas/hypothesis_critic_input_v1.schema.json"
)
_HFIC_SESSION_RECEIPT_SCHEMA_PATH = (
    _REPOSITORY_ROOT / "catalog/schemas/hypothesis_forge_session_receipt_v1_3.schema.json"
)
_REPRESENTATION_PAYLOAD_KEYS = {
    "anonymous",
    "eligible_member_count",
    "field_ids",
    "histogram",
    "histogram_member_count",
    "histogram_truncation",
    "motif",
    "normalization",
    "packet_schema",
    "payload_sha256",
    "pit",
    "representation_id",
    "representation_version",
    "schedule",
    "volume_mode",
}
_COHORT_READINESS_RECEIPT_KEYS = {
    "schema",
    "schema_version",
    "source_kind",
    "release_id",
    "manifest_sha256",
    "schedule_sha256",
    "readiness_state",
    "discovery_coverage_class",
    "first_fresh_cohort_sealed_verified_imported",
    "confirmatory_reuse_forbidden",
    "yield_eligible",
    "receipt_sha256",
}


class RepresentationProbeError(ValueError):
    """Fail-closed adapter error whose string is a stable terminal code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _hash64(name: str, value: object) -> str:
    if not isinstance(value, str) or _HASH64_RE.fullmatch(value) is None:
        raise RepresentationProbeError(f"{name.upper()}_INVALID")
    return value


def _nonempty_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RepresentationProbeError(f"{name.upper()}_INVALID")
    return value


def _contains_key(value: object, keys: set[str]) -> bool:
    if isinstance(value, Mapping):
        if any(str(key).lower() in keys for key in value):
            return True
        return any(_contains_key(child, keys) for child in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_key(child, keys) for child in value)
    return False


def _contains_scalar(value: object, needle: str) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_scalar(child, needle) for child in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_scalar(child, needle) for child in value)
    return value == needle


def _require_exact_keys(value: object, expected: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
    return value


def _require_nonnegative_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
    return value


def _validate_json_schema(
    value: Mapping[str, Any], path: Path, error_code: str
) -> None:
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema).iter_errors(dict(value)))
    except (OSError, json.JSONDecodeError, TypeError):
        raise RepresentationProbeError(error_code) from None
    if errors:
        raise RepresentationProbeError(error_code)


def _validate_serialized_representation_payload(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the closed, anonymous representation packet schema."""

    payload = deepcopy(dict(value))
    _require_exact_keys(payload, _REPRESENTATION_PAYLOAD_KEYS)
    if payload["packet_schema"] != "smial.normalized-trajectory-v1":
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
    if payload["representation_id"] != REPRESENTATION_ID:
        raise RepresentationProbeError(INVALID_REPRESENTATION_ID)
    if payload["representation_version"] != REPRESENTATION_VERSION:
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
    if payload["anonymous"] is not True or _contains_key(
        payload, _FORBIDDEN_IDENTITY_KEYS
    ):
        raise RepresentationProbeError(INVALID_MINT_IDENTITY)

    schedule = _require_exact_keys(
        payload["schedule"],
        {
            "schedule_id",
            "x_due_offset_seconds",
            "declared_y_due_offset_seconds",
            "prefix_due_offset_seconds",
            "decision_t_due_offset_seconds",
            "schedule_sha256",
        },
    )
    if schedule["schedule_id"] != PREFERRED_SCHEDULE_ID:
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
    if (
        isinstance(schedule["x_due_offset_seconds"], bool)
        or not isinstance(schedule["x_due_offset_seconds"], int)
        or schedule["x_due_offset_seconds"] not in ALLOWED_X_POINTS
    ):
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
    if schedule["declared_y_due_offset_seconds"] != list(DECLARED_Y_POINTS):
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
    expected_prefix = sorted(
        [schedule["x_due_offset_seconds"]]
        + [
            point
            for point in DECLARED_Y_POINTS
            if point <= DECISION_T_DUE_OFFSET_SECONDS
        ]
    )
    if schedule["prefix_due_offset_seconds"] != expected_prefix:
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
    if len(expected_prefix) != MIN_MOTIF_STEPS + 1:
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
    if schedule["decision_t_due_offset_seconds"] != DECISION_T_DUE_OFFSET_SECONDS:
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
    _hash64("schedule_sha256", schedule["schedule_sha256"])
    expected_schedule_sha256 = canonical_sha256(
        {
            "schedule_id": schedule["schedule_id"],
            "x_due_offset_seconds": schedule["x_due_offset_seconds"],
            "y_due_offset_seconds": schedule["declared_y_due_offset_seconds"],
            "decision_t_due_offset_seconds": schedule[
                "decision_t_due_offset_seconds"
            ],
        }
    )
    if schedule["schedule_sha256"] != expected_schedule_sha256:
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)

    if payload["pit"] != {
        "cutoff": "member_anchor_plus_Y1800",
        "first_reliable_available_at_le_cutoff": True,
        "future_points_in_denominator": False,
        "lateness_window_does_not_extend_T": True,
    }:
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
    if payload["normalization"] != {
        "kind": "OWN_HISTORY_LOG_RATIO",
        "first_value": "first_admissible_prefix_point_with_strictly_positive_finite_observed_value",
        "invalid_or_nonpositive": "M",
        "interpolation": False,
        "imputation": False,
    }:
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)

    volume_mode = payload["volume_mode"]
    if volume_mode == "TAKER_OBSERVED":
        channels = ["PRICE", "LIQUIDITY", "VOLUME", "TRADERS"]
    elif volume_mode == "ACTIVITY_VOLUME_OBSERVED_BUY_PLUS_SELL":
        channels = ["PRICE", "LIQUIDITY", "VOLUME_BUY", "VOLUME_SELL", "TRADERS"]
    elif volume_mode == "UNAVAILABLE":
        channels = ["PRICE", "LIQUIDITY", "VOLUME", "TRADERS"]
    else:
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
    motif = _require_exact_keys(
        payload["motif"],
        {"channels", "alphabet", "min_steps", "flat_rule", "missing_stays_missing"},
    )
    if motif != {
        "channels": channels,
        "alphabet": ["U", "F", "D", "M"],
        "min_steps": 2,
        "flat_rule": "EXACT_ZERO_CHANGE_ONLY",
        "missing_stays_missing": True,
    }:
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
    if payload["field_ids"] != {channel: FIELD_IDS[channel] for channel in channels}:
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)

    _require_nonnegative_int(payload["eligible_member_count"])
    histogram_member_count = _require_nonnegative_int(payload["histogram_member_count"])
    histogram = payload["histogram"]
    if not isinstance(histogram, list) or len(histogram) > 8:
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
    eligible_member_count = _require_nonnegative_int(payload["eligible_member_count"])
    total_histogram_count = 0
    previous_sort_key: tuple[int, bytes] | None = None
    seen_motifs: set[bytes] = set()
    for item in histogram:
        item_mapping = _require_exact_keys(item, {"motif", "count"})
        item_motif = _require_exact_keys(item_mapping["motif"], set(channels))
        motif_bytes = canonical_json_bytes(dict(item_motif))
        if motif_bytes in seen_motifs:
            raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
        seen_motifs.add(motif_bytes)
        for symbol in item_motif.values():
            if (
                not isinstance(symbol, str)
                or any(step not in {"U", "F", "D", "M"} for step in symbol.split("-"))
                or len(symbol.split("-")) != MIN_MOTIF_STEPS
            ):
                raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
        count = _require_nonnegative_int(item_mapping["count"])
        if count == 0:
            raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
        sort_key = (-count, motif_bytes)
        if previous_sort_key is not None and sort_key < previous_sort_key:
            raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
        previous_sort_key = sort_key
        total_histogram_count += count
    if histogram_member_count != total_histogram_count:
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
    if histogram_member_count > eligible_member_count:
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
    truncation = _require_exact_keys(
        payload["histogram_truncation"],
        {
            "max_distinct_motif_tuples",
            "retained_order",
            "dropped_lowest_count_tuples",
            "m_heavy_members_retained",
        },
    )
    if (
        truncation["max_distinct_motif_tuples"] != 8
        or truncation["retained_order"] != "count_desc_then_canonical_motif"
        or not isinstance(truncation["m_heavy_members_retained"], bool)
    ):
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
    dropped_tuples = _require_nonnegative_int(truncation["dropped_lowest_count_tuples"])
    if (
        (dropped_tuples == 0 and len(histogram) > 8)
        or (dropped_tuples > 0 and len(histogram) != 8)
        or truncation["m_heavy_members_retained"] is not True
    ):
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)

    declared_hash = _hash64("payload_sha256", payload["payload_sha256"])
    base = {key: item for key, item in payload.items() if key != "payload_sha256"}
    if declared_hash != canonical_sha256(base):
        raise RepresentationProbeError(INVALID_REPRESENTATION_HASH)
    return payload


def _packet_from_receipt(receipt: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in ("critic_input_packet", "control_packet"):
        packet = receipt.get(key)
        if isinstance(packet, Mapping):
            return packet
    # A forge context is not a critic packet.  Accept it only when a fixture
    # explicitly places the complete critic shape there.
    context = receipt.get("forge_context_packet")
    if isinstance(context, Mapping) and (
        "selected_candidate" in context or "packet_version" in context
    ):
        return context
    return None


def _validate_control_receipt_contract(
    receipt: Mapping[str, Any], packet: Mapping[str, Any]
) -> None:
    _validate_json_schema(packet, _HFIC_PACKET_SCHEMA_PATH, INVALID_CONTROL_PACKET_HASH)
    session_receipt = receipt.get("session_receipt")
    if not isinstance(session_receipt, Mapping):
        raise RepresentationProbeError(INVALID_CONTROL_NOT_RUN)
    _validate_json_schema(
        session_receipt,
        _HFIC_SESSION_RECEIPT_SCHEMA_PATH,
        INVALID_CONTROL_NOT_RUN,
    )
    for key in (
        "session_id",
        "evidence_epoch_sha256",
        "prompt_version",
        "critic_input_packet_sha256",
    ):
        if session_receipt.get(key) != receipt.get(key):
            raise RepresentationProbeError(INVALID_CONTROL_PACKET_HASH)
    if session_receipt.get("critic_input_packet_sha256") != canonical_sha256(packet):
        raise RepresentationProbeError(INVALID_CONTROL_PACKET_HASH)
    if session_receipt.get("evidence_surface_mode") != CURRENT_REPRESENTATION_CONTROL_V1:
        raise RepresentationProbeError(INVALID_CONTROL_MODE)
    if session_receipt.get("final_session_terminal") != receipt.get(
        "final_session_terminal"
    ) or session_receipt.get("critic_terminal") != receipt.get("critic_terminal"):
        raise RepresentationProbeError(INVALID_CONTROL_PACKET_HASH)


def _validate_cohort_readiness_receipt(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _COHORT_READINESS_RECEIPT_KEYS:
        raise RepresentationProbeError(INVALID_COHORT_READINESS_RECEIPT)
    receipt = deepcopy(dict(value))
    if (
        receipt["schema"] != "smial.normalized-trajectory-v1-readiness-receipt"
        or receipt["schema_version"] != "1.0"
        or receipt["source_kind"] != "LIVE_COHORT_RELEASE_MANIFEST"
        or not isinstance(receipt["release_id"], str)
        or not receipt["release_id"].strip()
        or receipt["readiness_state"]
        not in {"READY_VALID", "READY_VALID_WITH_COVERAGE_LIMITATION"}
        or not isinstance(receipt["discovery_coverage_class"], str)
        or not receipt["discovery_coverage_class"].strip()
        or receipt["first_fresh_cohort_sealed_verified_imported"] is not True
        or receipt["confirmatory_reuse_forbidden"] is not True
        or isinstance(receipt["yield_eligible"], bool)
        or not isinstance(receipt["yield_eligible"], int)
        or receipt["yield_eligible"] < 0
    ):
        raise RepresentationProbeError(INVALID_COHORT_READINESS_RECEIPT)
    _hash64("manifest_sha256", receipt["manifest_sha256"])
    _hash64("schedule_sha256", receipt["schedule_sha256"])
    _hash64("receipt_sha256", receipt["receipt_sha256"])
    base = {key: item for key, item in receipt.items() if key != "receipt_sha256"}
    if receipt["receipt_sha256"] != canonical_sha256(base):
        raise RepresentationProbeError(INVALID_COHORT_READINESS_RECEIPT)
    return receipt


def _memory_baseline_sha256(
    packet: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> str:
    eligibility = receipt.get(
        "memory_eligibility_sha256", packet.get("memory_eligibility_sha256")
    )
    if eligibility is not None:
        _hash64("memory_eligibility_sha256", eligibility)
    basis = {
        "memory_eligibility_sha256": eligibility,
        "prior_memory": deepcopy(packet.get("prior_memory")),
        "research_memory_as_of": packet.get("research_memory_as_of"),
        "prior_work_queries": deepcopy(packet.get("prior_work_queries")),
    }
    return canonical_sha256(basis)


def control_memory_baseline_sha256(receipt: Mapping[str, Any]) -> str:
    """Compute the recorded memory baseline for a verified CONTROL fixture."""

    if not isinstance(receipt, Mapping):
        raise RepresentationProbeError(INVALID_CONTROL_NOT_RUN)
    packet = _packet_from_receipt(receipt)
    if packet is None:
        raise RepresentationProbeError(INVALID_CONTROL_NOT_RUN)
    return _memory_baseline_sha256(packet, receipt)


@dataclass(frozen=True)
class ControlBaseline:
    """Hash-bound, trajectory-blind CONTROL context used by the adapter."""

    session_id: str
    terminal: str
    evidence_epoch_sha256: str
    prompt_version: str
    packet: Mapping[str, Any]
    packet_sha256: str
    memory_baseline_sha256: str
    memory_eligibility_sha256: str | None = None
    focus_key_sha256: str | None = None
    search_key_sha256: str | None = None
    receipt_verified: bool = False
    _verification_token: object | None = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if (
            not self.receipt_verified
            or self._verification_token is not _VERIFIED_BASELINE_TOKEN
        ):
            raise RepresentationProbeError(INVALID_CONTROL_NOT_RUN)
        _nonempty_text("session_id", self.session_id)
        _nonempty_text("terminal", self.terminal)
        _hash64("evidence_epoch_sha256", self.evidence_epoch_sha256)
        _hash64("packet_sha256", self.packet_sha256)
        _hash64("memory_baseline_sha256", self.memory_baseline_sha256)
        if self.memory_eligibility_sha256 is not None:
            _hash64("memory_eligibility_sha256", self.memory_eligibility_sha256)
        if self.focus_key_sha256 is not None:
            _hash64("focus_key_sha256", self.focus_key_sha256)
        if self.search_key_sha256 is not None:
            _hash64("search_key_sha256", self.search_key_sha256)
        if not isinstance(self.packet, Mapping):
            raise RepresentationProbeError("CONTROL_PACKET_INVALID")
        object.__setattr__(self, "packet", deepcopy(dict(self.packet)))


def control_baseline_from_receipt(receipt: Mapping[str, Any]) -> ControlBaseline:
    """Extract and verify the exact current CONTROL packet from a receipt."""

    if not isinstance(receipt, Mapping):
        raise RepresentationProbeError(INVALID_CONTROL_NOT_RUN)
    packet = _packet_from_receipt(receipt)
    if packet is None:
        raise RepresentationProbeError(INVALID_CONTROL_NOT_RUN)
    if control_packet_has_raw_sequences(packet) or _contains_key(packet, _FORBIDDEN_CONTROL_KEYS):
        raise RepresentationProbeError(INVALID_CONTROL_TRAJECTORY)
    _validate_control_receipt_contract(receipt, packet)

    if receipt.get("evidence_surface_mode") != CURRENT_REPRESENTATION_CONTROL_V1:
        raise RepresentationProbeError(INVALID_CONTROL_MODE)
    packet_mode = packet.get("evidence_surface_mode")
    if packet_mode is not None and packet_mode != CURRENT_REPRESENTATION_CONTROL_V1:
        raise RepresentationProbeError(INVALID_CONTROL_MODE)

    epoch = receipt.get("evidence_epoch_sha256")
    prompt = receipt.get("prompt_version")
    session_id = receipt.get("session_id")
    if not isinstance(epoch, str) or not _HASH64_RE.fullmatch(epoch):
        raise RepresentationProbeError("EVIDENCE_EPOCH_SHA256_INVALID")
    if prompt != PROMPT_VERSION:
        raise RepresentationProbeError("PROMPT_VERSION_MISMATCH")
    if not isinstance(session_id, str) or not session_id:
        raise RepresentationProbeError("SESSION_ID_INVALID")
    for packet_key, expected in (
        ("evidence_epoch_sha256", epoch),
        ("generator_prompt_version", prompt),
        ("session_id", session_id),
    ):
        packet_value = packet.get(packet_key)
        if packet_value is not None and packet_value != expected:
            raise RepresentationProbeError(INVALID_EVIDENCE_EPOCH_MISMATCH if packet_key == "evidence_epoch_sha256" else INVALID_CONTROL_PACKET_HASH)

    computed_packet_sha256 = canonical_sha256(packet)
    recorded_packet_sha256 = receipt.get("critic_input_packet_sha256")
    if not isinstance(recorded_packet_sha256, str) or not _HASH64_RE.fullmatch(recorded_packet_sha256):
        raise RepresentationProbeError(INVALID_CONTROL_PACKET_HASH)
    if recorded_packet_sha256 != computed_packet_sha256:
        raise RepresentationProbeError(INVALID_CONTROL_PACKET_HASH)
    packet_declared_hash = packet.get("packet_sha256")
    if packet_declared_hash is not None and packet_declared_hash != computed_packet_sha256:
        raise RepresentationProbeError(INVALID_CONTROL_PACKET_HASH)

    recorded_memory_sha256 = receipt.get("memory_baseline_sha256")
    if not isinstance(recorded_memory_sha256, str) or not _HASH64_RE.fullmatch(recorded_memory_sha256):
        raise RepresentationProbeError(INVALID_MEMORY_BASELINE_DRIFT)
    computed_memory_sha256 = _memory_baseline_sha256(packet, receipt)
    if recorded_memory_sha256 != computed_memory_sha256:
        raise RepresentationProbeError(INVALID_MEMORY_BASELINE_DRIFT)
    if _contains_scalar(packet.get("prior_memory"), session_id):
        raise RepresentationProbeError(INVALID_MEMORY_BASELINE_DRIFT)
    terminal = effective_control_terminal(receipt)
    if not terminal:
        raise RepresentationProbeError(INVALID_CONTROL_NOT_RUN)

    return ControlBaseline(
        session_id=session_id,
        terminal=terminal,
        evidence_epoch_sha256=epoch,
        prompt_version=prompt,
        packet=packet,
        packet_sha256=computed_packet_sha256,
        memory_baseline_sha256=computed_memory_sha256,
        memory_eligibility_sha256=receipt.get(
            "memory_eligibility_sha256", packet.get("memory_eligibility_sha256")
        ),
        focus_key_sha256=receipt.get("focus_key_sha256", packet.get("focus_key_sha256")),
        search_key_sha256=receipt.get("search_key_sha256", packet.get("search_key_sha256")),
        receipt_verified=True,
        _verification_token=_VERIFIED_BASELINE_TOKEN,
    )


def representation_search_key_sha256(
    *,
    evidence_epoch_sha256: str,
    owner_focus: str,
    prompt_version: str,
    memory_baseline_sha256: str,
    representation_id: str = REPRESENTATION_ID,
    representation_payload_sha256: str | None = None,
    control_packet_sha256: str | None = None,
) -> str:
    """Build a distinct, bounded identity without changing ordinary HFIC keys."""

    _hash64("evidence_epoch_sha256", evidence_epoch_sha256)
    _hash64("memory_baseline_sha256", memory_baseline_sha256)
    _hash64("representation_payload_sha256", representation_payload_sha256)
    if control_packet_sha256 is not None:
        _hash64("control_packet_sha256", control_packet_sha256)
    _nonempty_text("owner_focus", owner_focus)
    _nonempty_text("prompt_version", prompt_version)
    _nonempty_text("representation_id", representation_id)
    return canonical_sha256(
        {
            "identity_kind": "REGISTERED_REPRESENTATION_PROBE",
            "evidence_epoch_sha256": evidence_epoch_sha256,
            "owner_focus": owner_focus,
            "prompt_version": prompt_version,
            "memory_baseline_sha256": memory_baseline_sha256,
            "representation_id": representation_id,
            "representation_payload_sha256": representation_payload_sha256,
            "control_packet_sha256": control_packet_sha256,
        }
    )


def representation_probe_identity_sha256(
    *,
    control_session_id: str,
    evidence_epoch_sha256: str,
    representation_id: str,
    representation_search_key: str,
    representation_payload_sha256: str | None = None,
) -> str:
    """Identity for the one registered representation run per CONTROL/epoch."""

    _nonempty_text("control_session_id", control_session_id)
    _hash64("evidence_epoch_sha256", evidence_epoch_sha256)
    _hash64("representation_search_key", representation_search_key)
    _hash64("representation_payload_sha256", representation_payload_sha256)
    _nonempty_text("representation_id", representation_id)
    return canonical_sha256(
        {
            "identity_kind": "REGISTERED_REPRESENTATION_PROBE",
            "control_session_id": control_session_id,
            "evidence_epoch_sha256": evidence_epoch_sha256,
            "representation_id": representation_id,
            "representation_search_key_sha256": representation_search_key,
            "representation_payload_sha256": representation_payload_sha256,
        }
    )


def _representation_payload(
    representation: NormalizedTrajectoryRepresentation,
) -> dict[str, Any]:
    if not isinstance(representation, NormalizedTrajectoryRepresentation):
        raise RepresentationProbeError("REPRESENTATION_INVALID")
    return _validate_serialized_representation_payload(representation.payload)


def build_challenger_packet(
    control: ControlBaseline | Mapping[str, Any],
    representation: NormalizedTrajectoryRepresentation,
    *,
    owner_focus: str | None = None,
    registered_probe_identity_sha256: str | None = None,
) -> dict[str, Any]:
    """Build a bounded challenger envelope around exact CONTROL context.

    The nested ``critic_input_packet`` remains byte-for-byte the CONTROL
    packet.  The representation is an explicit sibling in the adapter
    envelope, avoiding a silent mutation of the historical HFIC schema.
    """

    baseline = (
        control
        if isinstance(control, ControlBaseline)
        else control_baseline_from_receipt(control)
    )
    if isinstance(control, ControlBaseline) and (
        not baseline.receipt_verified
        or baseline._verification_token is not _VERIFIED_BASELINE_TOKEN
    ):
        raise RepresentationProbeError(INVALID_CONTROL_NOT_RUN)
    if not control_probe_permitted(baseline.terminal):
        raise RepresentationProbeError(INVALID_TRIGGER_NOT_MET)
    if not baseline.packet:
        raise RepresentationProbeError(INVALID_CONTROL_NOT_RUN)
    if control_packet_has_raw_sequences(baseline.packet) or _contains_key(
        baseline.packet, _FORBIDDEN_CONTROL_KEYS
    ):
        raise RepresentationProbeError(INVALID_CONTROL_TRAJECTORY)
    if canonical_sha256(baseline.packet) != baseline.packet_sha256:
        raise RepresentationProbeError(INVALID_CONTROL_PACKET_HASH)

    payload = _representation_payload(representation)
    payload_sha256 = payload.get("payload_sha256")
    _hash64("representation_payload_sha256", payload_sha256)
    bound_focus = str(
        baseline.packet.get("owner_focus", baseline.focus_key_sha256 or "CONTROL")
    )
    if owner_focus is not None and owner_focus != bound_focus:
        raise RepresentationProbeError(INVALID_CONTROL_FOCUS)
    focus = bound_focus
    search_key = representation_search_key_sha256(
        evidence_epoch_sha256=baseline.evidence_epoch_sha256,
        owner_focus=focus,
        prompt_version=baseline.prompt_version,
        memory_baseline_sha256=baseline.memory_baseline_sha256,
        representation_id=REPRESENTATION_ID,
        representation_payload_sha256=payload_sha256,
        control_packet_sha256=baseline.packet_sha256,
    )
    probe_identity = representation_probe_identity_sha256(
        control_session_id=baseline.session_id,
        evidence_epoch_sha256=baseline.evidence_epoch_sha256,
        representation_id=REPRESENTATION_ID,
        representation_search_key=search_key,
        representation_payload_sha256=payload_sha256,
    )
    if registered_probe_identity_sha256 is not None:
        _hash64("registered_probe_identity_sha256", registered_probe_identity_sha256)
        if registered_probe_identity_sha256 != probe_identity:
            raise RepresentationProbeError(INVALID_PROBE_IDENTITY)
        raise RepresentationProbeError(REPRESENTATION_PROBE_ALREADY_EXISTS)
    challenger: dict[str, Any] = {
        "packet_schema": REPRESENTATION_PROBE_SCHEMA,
        "packet_version": REPRESENTATION_PROBE_VERSION,
        "probe_kind": REPRESENTATION_PROBE_KIND,
        "probe_state": "DORMANT_PACKET_ONLY",
        "representation_id": REPRESENTATION_ID,
        "representation_packet_key": PACKET_KEY,
        "control_session_id": baseline.session_id,
        "evidence_epoch_sha256": baseline.evidence_epoch_sha256,
        "control_packet_sha256": baseline.packet_sha256,
        "memory_baseline_sha256": baseline.memory_baseline_sha256,
        "memory_eligibility_sha256": baseline.memory_eligibility_sha256,
        "owner_focus": bound_focus,
        "representation_payload_sha256": payload_sha256,
        "prompt_version": baseline.prompt_version,
        "representation_search_key_sha256": search_key,
        "probe_identity_sha256": probe_identity,
        "ordinary_search_budget_unchanged": True,
        "max_challenger_runs_per_representation_control_epoch": MAX_CHALLENGER_RUNS_PER_CONTROL_EPOCH,
        "max_packet_bytes": MAX_PACKET_BYTES,
        "critic_input_packet": deepcopy(dict(baseline.packet)),
        PACKET_KEY: payload,
        "non_claims": [
            "NO_PROBE_EXECUTION",
            "NO_ALPHA",
            "NO_CURRENT_COHORT_SCIENTIFIC_READ",
        ],
    }
    challenger["packet_bytes"] = 0
    for _ in range(4):
        packet_size = len(canonical_json_bytes(challenger))
        if packet_size > MAX_PACKET_BYTES:
            raise RepresentationProbeError(INVALID_PACKET_BUDGET)
        if challenger["packet_bytes"] == packet_size:
            break
        challenger["packet_bytes"] = packet_size
    if len(canonical_json_bytes(challenger)) > MAX_PACKET_BYTES:
        raise RepresentationProbeError(INVALID_PACKET_BUDGET)
    if challenger["packet_bytes"] != len(canonical_json_bytes(challenger)):
        raise RepresentationProbeError(INVALID_PACKET_BUDGET)
    return challenger


def _validate_challenger_packet(
    challenger_packet: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Revalidate every identity-bearing field before fixture transport."""

    expected_keys = {
        "packet_schema",
        "packet_version",
        "probe_kind",
        "probe_state",
        "representation_id",
        "representation_packet_key",
        "control_session_id",
        "evidence_epoch_sha256",
        "control_packet_sha256",
        "memory_baseline_sha256",
        "memory_eligibility_sha256",
        "owner_focus",
        "representation_payload_sha256",
        "prompt_version",
        "representation_search_key_sha256",
        "probe_identity_sha256",
        "ordinary_search_budget_unchanged",
        "max_challenger_runs_per_representation_control_epoch",
        "max_packet_bytes",
        "critic_input_packet",
        PACKET_KEY,
        "non_claims",
        "packet_bytes",
    }
    packet = dict(_require_exact_keys(challenger_packet, expected_keys))
    if (
        packet["packet_schema"] != REPRESENTATION_PROBE_SCHEMA
        or packet["packet_version"] != REPRESENTATION_PROBE_VERSION
        or packet["probe_kind"] != REPRESENTATION_PROBE_KIND
        or packet["probe_state"] != "DORMANT_PACKET_ONLY"
        or packet["representation_id"] != REPRESENTATION_ID
        or packet["representation_packet_key"] != PACKET_KEY
        or packet["prompt_version"] != PROMPT_VERSION
        or packet["ordinary_search_budget_unchanged"] is not True
        or packet["max_challenger_runs_per_representation_control_epoch"]
        != MAX_CHALLENGER_RUNS_PER_CONTROL_EPOCH
        or packet["max_packet_bytes"] != MAX_PACKET_BYTES
        or packet["non_claims"]
        != ["NO_PROBE_EXECUTION", "NO_ALPHA", "NO_CURRENT_COHORT_SCIENTIFIC_READ"]
    ):
        raise RepresentationProbeError(INVALID_REPRESENTATION_SCHEMA)
    _nonempty_text("control_session_id", packet["control_session_id"])
    _hash64("evidence_epoch_sha256", packet["evidence_epoch_sha256"])
    _hash64("control_packet_sha256", packet["control_packet_sha256"])
    _hash64("memory_baseline_sha256", packet["memory_baseline_sha256"])
    _nonempty_text("owner_focus", packet["owner_focus"])

    control_packet = packet["critic_input_packet"]
    if not isinstance(control_packet, Mapping):
        raise RepresentationProbeError(INVALID_CONTROL_PACKET_HASH)
    if control_packet_has_raw_sequences(control_packet) or _contains_key(
        control_packet, _FORBIDDEN_CONTROL_KEYS
    ):
        raise RepresentationProbeError(INVALID_CONTROL_TRAJECTORY)
    if canonical_sha256(control_packet) != packet["control_packet_sha256"]:
        raise RepresentationProbeError(INVALID_CONTROL_PACKET_HASH)
    eligibility = packet["memory_eligibility_sha256"]
    if eligibility is not None:
        _hash64("memory_eligibility_sha256", eligibility)
    if _memory_baseline_sha256(
        control_packet, {"memory_eligibility_sha256": eligibility}
    ) != packet["memory_baseline_sha256"]:
        raise RepresentationProbeError(INVALID_MEMORY_BASELINE_DRIFT)

    representation = _validate_serialized_representation_payload(packet[PACKET_KEY])
    if representation["payload_sha256"] != packet["representation_payload_sha256"]:
        raise RepresentationProbeError(INVALID_REPRESENTATION_HASH)
    _hash64("representation_payload_sha256", packet["representation_payload_sha256"])
    expected_search_key = representation_search_key_sha256(
        evidence_epoch_sha256=packet["evidence_epoch_sha256"],
        owner_focus=packet["owner_focus"],
        prompt_version=packet["prompt_version"],
        memory_baseline_sha256=packet["memory_baseline_sha256"],
        representation_id=packet["representation_id"],
        representation_payload_sha256=packet["representation_payload_sha256"],
        control_packet_sha256=packet["control_packet_sha256"],
    )
    if expected_search_key != packet["representation_search_key_sha256"]:
        raise RepresentationProbeError(INVALID_PROBE_IDENTITY)
    expected_identity = representation_probe_identity_sha256(
        control_session_id=packet["control_session_id"],
        evidence_epoch_sha256=packet["evidence_epoch_sha256"],
        representation_id=packet["representation_id"],
        representation_search_key=packet["representation_search_key_sha256"],
        representation_payload_sha256=packet["representation_payload_sha256"],
    )
    if expected_identity != packet["probe_identity_sha256"]:
        raise RepresentationProbeError(INVALID_PROBE_IDENTITY)
    if packet["packet_bytes"] != len(canonical_json_bytes(packet)):
        raise RepresentationProbeError(INVALID_PACKET_BUDGET)
    if packet["packet_bytes"] > MAX_PACKET_BYTES:
        raise RepresentationProbeError(INVALID_PACKET_BUDGET)
    return packet, representation


def existing_hfic_packet(challenger_packet: Mapping[str, Any]) -> dict[str, Any]:
    """Return the unchanged critic packet for an existing HFIC lifecycle fixture."""

    validated, _representation = _validate_challenger_packet(challenger_packet)
    return deepcopy(dict(validated["critic_input_packet"]))


def existing_hfic_lifecycle_fixture_input(
    challenger_packet: Mapping[str, Any],
) -> dict[str, Any]:
    """Bridge the outer dormant envelope into the unchanged HFIC fixture seam.

    The existing critic packet stays byte-for-byte unchanged.  The fixture
    receives representation context as a sibling envelope, so ordinary HFIC
    schema validation and lifecycle code remain untouched.
    """

    validated, representation = _validate_challenger_packet(challenger_packet)
    packet = existing_hfic_packet(validated)
    return {
        "lifecycle_mode": REPRESENTATION_PROBE_KIND,
        "probe_state": validated["probe_state"],
        "representation_id": validated["representation_id"],
        "representation": representation,
        "probe_identity_sha256": validated["probe_identity_sha256"],
        "control_session_id": validated["control_session_id"],
        "evidence_epoch_sha256": validated["evidence_epoch_sha256"],
        "ordinary_search_budget_unchanged": validated["ordinary_search_budget_unchanged"],
        "critic_input_packet": packet,
    }


prepare_existing_hfic_lifecycle_fixture = existing_hfic_lifecycle_fixture_input


def _value_or(snapshot: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in snapshot:
            return snapshot[key]
    return default


def _status_binding_reason(
    snapshot: Mapping[str, Any],
    receipt: Mapping[str, Any] | None,
) -> str | None:
    """Require explicit, hash-bound CONTROL anchors before eligibility."""

    if snapshot.get("evidence_epoch_matches") is not True:
        return INVALID_EVIDENCE_EPOCH_MISMATCH
    if snapshot.get("control_mode") != CURRENT_REPRESENTATION_CONTROL_V1:
        return INVALID_CONTROL_MODE

    if receipt is None:
        return INVALID_CONTROL_NOT_RUN
    try:
        baseline = control_baseline_from_receipt(receipt)
    except RepresentationProbeError as exc:
        return str(exc)
    expected = {
        "control_session_id": baseline.session_id,
        "evidence_epoch_sha256": baseline.evidence_epoch_sha256,
        "control_packet_sha256": baseline.packet_sha256,
        "memory_baseline_sha256": baseline.memory_baseline_sha256,
    }
    for key, value in expected.items():
        supplied = snapshot.get(key)
        if key not in snapshot or supplied != value:
            if key == "memory_baseline_sha256":
                return INVALID_MEMORY_BASELINE_DRIFT
            if key == "evidence_epoch_sha256":
                return INVALID_EVIDENCE_EPOCH_MISMATCH
            return INVALID_CONTROL_PACKET_HASH
    declared_terminal = _value_or(
        snapshot, "effective_control_terminal", "control_terminal"
    )
    if declared_terminal is not None and declared_terminal != baseline.terminal:
        return INVALID_CONTROL_PACKET_HASH
    return None


def _status_probe_identity_reason(
    snapshot: Mapping[str, Any],
    baseline: ControlBaseline,
    *,
    require_execution: bool = False,
) -> str | None:
    """Require a complete, baseline-bound receipt for declared prior state."""

    receipt = snapshot.get("representation_probe_receipt")
    if not isinstance(receipt, Mapping) or receipt.get("receipt_verified") is not True:
        return INVALID_PROBE_IDENTITY
    if receipt.get("representation_packet_key") != PACKET_KEY:
        return INVALID_PROBE_IDENTITY
    if require_execution:
        if (
            receipt.get("probe_state") != "EXECUTED"
            or receipt.get("probe_executed") is not True
            or receipt.get("execution_terminal") != "REPRESENTATION_PROBE_EXECUTED"
        ):
            return INVALID_PROBE_IDENTITY
        try:
            _hash64(
                "execution_result_sha256", receipt.get("execution_result_sha256")
            )
        except RepresentationProbeError:
            return INVALID_PROBE_IDENTITY
    elif receipt.get("probe_state") not in {"DORMANT_PACKET_ONLY", "REGISTERED"}:
        return INVALID_PROBE_IDENTITY
    try:
        representation = _validate_serialized_representation_payload(
            receipt[PACKET_KEY]
        )
        payload_sha256 = representation["payload_sha256"]
        expected_search_key = representation_search_key_sha256(
            evidence_epoch_sha256=baseline.evidence_epoch_sha256,
            owner_focus=str(
                baseline.packet.get("owner_focus", baseline.focus_key_sha256 or "CONTROL")
            ),
            prompt_version=baseline.prompt_version,
            memory_baseline_sha256=baseline.memory_baseline_sha256,
            representation_id=REPRESENTATION_ID,
            representation_payload_sha256=payload_sha256,
            control_packet_sha256=baseline.packet_sha256,
        )
        expected_identity = representation_probe_identity_sha256(
            control_session_id=baseline.session_id,
            evidence_epoch_sha256=baseline.evidence_epoch_sha256,
            representation_id=REPRESENTATION_ID,
            representation_search_key=expected_search_key,
            representation_payload_sha256=payload_sha256,
        )
    except (KeyError, RepresentationProbeError):
        return INVALID_PROBE_IDENTITY
    for key, expected in {
        "control_session_id": baseline.session_id,
        "evidence_epoch_sha256": baseline.evidence_epoch_sha256,
        "control_packet_sha256": baseline.packet_sha256,
        "memory_baseline_sha256": baseline.memory_baseline_sha256,
        "representation_payload_sha256": payload_sha256,
        "representation_search_key_sha256": expected_search_key,
        "probe_identity_sha256": expected_identity,
    }.items():
        if receipt.get(key) != expected:
            return INVALID_PROBE_IDENTITY
    return None


def representation_status(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Return read-only eligibility/status; never executes or reads runtime state."""

    if not isinstance(snapshot, Mapping):
        raise RepresentationProbeError("STATUS_INPUT_INVALID")
    receipt = snapshot.get("control_receipt")
    receipt_mapping = receipt if isinstance(receipt, Mapping) else None
    control_present = _value_or(
        snapshot,
        "control_present",
        "control_packet_present",
        default=(receipt_mapping is not None),
    )
    if control_present is not True or receipt_mapping is None:
        status = STATUS_CONTROL_REQUIRED
        reason = INVALID_CONTROL_NOT_RUN
        return {
            "representation_id": REPRESENTATION_ID,
            "status": status,
            "reason_code": reason,
            "read_only": True,
            "probe_executed": False,
            "ordinary_hypothesis_forge_unchanged": True,
            "alpha_claim": False,
            "message_ru": "Сначала нужен текущий CONTROL Forge на том же evidence epoch.",
        }
    try:
        baseline = control_baseline_from_receipt(receipt_mapping)
    except RepresentationProbeError as exc:
        status = STATUS_OBSERVABILITY_BLOCKED
        reason = str(exc)
        return {
            "representation_id": REPRESENTATION_ID,
            "status": status,
            "reason_code": reason,
            "read_only": True,
            "probe_executed": False,
            "ordinary_hypothesis_forge_unchanged": True,
            "alpha_claim": False,
            "message_ru": "Representation probe заблокирован проблемой наблюдаемости или целостности.",
        }
    binding_reason = _status_binding_reason(snapshot, receipt_mapping)
    if binding_reason is not None:
        status = (
            STATUS_CONTROL_REQUIRED
            if binding_reason == INVALID_CONTROL_NOT_RUN
            else STATUS_OBSERVABILITY_BLOCKED
        )
        return {
            "representation_id": REPRESENTATION_ID,
            "status": status,
            "reason_code": binding_reason,
            "read_only": True,
            "probe_executed": False,
            "ordinary_hypothesis_forge_unchanged": True,
            "alpha_claim": False,
            "message_ru": "Representation probe заблокирован проблемой наблюдаемости или целостности.",
        }

    existing_state = _value_or(
        snapshot,
        "representation_probe_state",
        "probe_state",
        "existing_probe_state",
    )
    if existing_state in {"COMPLETE", STATUS_COMPLETE, "PASS", "PROBE_EXECUTED"}:
        identity_reason = _status_probe_identity_reason(
            snapshot, baseline, require_execution=True
        )
        if identity_reason is not None:
            status = STATUS_OBSERVABILITY_BLOCKED
            reason = identity_reason
        else:
            status = STATUS_COMPLETE
            reason = "REPRESENTATION_PROBE_ALREADY_COMPLETED"
    elif (
        existing_state in {"EXISTS", STATUS_ALREADY_EXISTS, "RUNNING", "REGISTERED"}
        or _value_or(
            snapshot, "representation_probe_exists", "probe_exists", default=False
        )
    ):
        identity_reason = _status_probe_identity_reason(snapshot, baseline)
        if identity_reason is not None:
            status = STATUS_OBSERVABILITY_BLOCKED
            reason = identity_reason
        else:
            status = STATUS_ALREADY_EXISTS
            reason = REPRESENTATION_PROBE_ALREADY_EXISTS
    else:
        terminal = baseline.terminal
        if terminal == "RUNNER_UP_REVISION_REQUIRED":
            status = STATUS_RUNNER_UP_PAUSE
            reason = "RUNNER_UP_REVISION_REQUIRED"
        elif terminal in CASE_A_TERMINALS:
            status = STATUS_MARKET_FALSIFIER_FIRST
            reason = "CASE_A_CONTROL_PASS"
        elif terminal in CASE_C_KILL_TERMINALS:
            status = STATUS_OBSERVABILITY_BLOCKED
            reason = INVALID_CASE_C_OBSERVABILITY
        elif not control_probe_permitted(terminal):
            status = STATUS_OBSERVABILITY_BLOCKED
            reason = INVALID_TRIGGER_NOT_MET
        else:
            readiness = _value_or(snapshot, "readiness", "readiness_class")
            coverage = _value_or(snapshot, "discovery_coverage_class", default="")
            yield_eligible = _value_or(snapshot, "yield_eligible", default=None)
            try:
                readiness_receipt = _validate_cohort_readiness_receipt(
                    snapshot.get("cohort_readiness_receipt")
                )
            except RepresentationProbeError as exc:
                readiness_receipt = None
                invalid_readiness_reason = str(exc)
            else:
                invalid_readiness_reason = None
            if readiness_receipt is not None:
                readiness = readiness_receipt["readiness_state"]
                coverage = readiness_receipt["discovery_coverage_class"]
                yield_eligible = readiness_receipt["yield_eligible"]
                cohort_imported = readiness_receipt[
                    "first_fresh_cohort_sealed_verified_imported"
                ]
            else:
                cohort_imported = False
            invalid_reason: str | None = _status_binding_reason(
                snapshot, receipt_mapping
            )
            if invalid_reason is None and invalid_readiness_reason is not None:
                invalid_reason = invalid_readiness_reason
            elif (
                invalid_reason is None
                and (
                    not isinstance(cohort_imported, bool)
                    or isinstance(yield_eligible, bool)
                    or not isinstance(yield_eligible, int)
                )
            ):
                invalid_reason = INVALID_OBSERVABILITY_INPUT
            elif invalid_reason is None and not cohort_imported:
                invalid_reason = INVALID_CASE_C_OBSERVABILITY
            elif invalid_reason is None and readiness not in {
                "READY_VALID",
                "READY_VALID_WITH_COVERAGE_LIMITATION",
            }:
                invalid_reason = "INVALID_COVERAGE_BROKEN"
            elif invalid_reason is None and coverage == "GAP_CONFIRMED":
                invalid_reason = "INVALID_COVERAGE_BROKEN"
            elif invalid_reason is None and yield_eligible < MIN_USABLE_YIELD_ELIGIBLE:
                invalid_reason = "INVALID_INSUFFICIENT_YIELD"
            if invalid_reason == INVALID_CONTROL_NOT_RUN:
                status = STATUS_CONTROL_REQUIRED
                reason = invalid_reason
            elif invalid_reason is not None:
                status = STATUS_OBSERVABILITY_BLOCKED
                reason = invalid_reason
            else:
                status = STATUS_ELIGIBLE
                reason = "CONTROL_TERMINAL_PERMITS_PROBE"

    return {
        "representation_id": REPRESENTATION_ID,
        "status": status,
        "reason_code": reason,
        "read_only": True,
        "probe_executed": status == STATUS_COMPLETE,
        "ordinary_hypothesis_forge_unchanged": True,
        "alpha_claim": False,
        "message_ru": {
            STATUS_CONTROL_REQUIRED: "Сначала нужен текущий CONTROL Forge на том же evidence epoch.",
            STATUS_ELIGIBLE: "NORMALIZED_TRAJECTORY_V1 допускается к отдельному bounded probe; запуск не выполнен.",
            STATUS_MARKET_FALSIFIER_FIRST: "CONTROL дал Case A: сначала cheapest market falsifier.",
            STATUS_OBSERVABILITY_BLOCKED: "Representation probe заблокирован проблемой наблюдаемости или целостности.",
            STATUS_RUNNER_UP_PAUSE: "CONTROL требует runner-up revision; representation probe на паузе.",
            STATUS_ALREADY_EXISTS: "Для этого CONTROL/epoch уже зарегистрирован representation probe.",
            STATUS_COMPLETE: "Representation probe уже имеет runtime result; этот вызов только читает статус.",
        }[status],
    }


def build_representation_probe_packet(
    control: ControlBaseline | Mapping[str, Any],
    representation: NormalizedTrajectoryRepresentation,
    *,
    owner_focus: str | None = None,
    registered_probe_identity_sha256: str | None = None,
) -> dict[str, Any]:
    """Explicit name for the dormant challenger packet boundary."""

    return build_challenger_packet(
        control,
        representation,
        owner_focus=owner_focus,
        registered_probe_identity_sha256=registered_probe_identity_sha256,
    )


get_representation_status = representation_status


__all__ = [
    "CASE_A_TERMINALS",
    "CASE_C_KILL_TERMINALS",
    "CONTROL_REQUIRED",
    "ControlBaseline",
    "CURRENT_REPRESENTATION_CONTROL_V1",
    "INVALID_CASE_C_OBSERVABILITY",
    "INVALID_CONTROL_FOCUS",
    "INVALID_CONTROL_MODE",
    "INVALID_CONTROL_NOT_RUN",
    "INVALID_CONTROL_PACKET_HASH",
    "INVALID_CONTROL_TRAJECTORY",
    "INVALID_EVIDENCE_EPOCH_MISMATCH",
    "INVALID_MEMORY_BASELINE_DRIFT",
    "INVALID_COHORT_READINESS_RECEIPT",
    "INVALID_OBSERVABILITY_INPUT",
    "INVALID_PACKET_BUDGET",
    "INVALID_PROBE_IDENTITY",
    "INVALID_REPRESENTATION_SCHEMA",
    "INVALID_TRIGGER_NOT_MET",
    "MAX_CHALLENGER_RUNS_PER_CONTROL_EPOCH",
    "PROBE_PERMIT_TERMINALS",
    "REPRESENTATION_PROBE_ALREADY_EXISTS",
    "RepresentationProbeError",
    "STATUS_ALREADY_EXISTS",
    "STATUS_COMPLETE",
    "STATUS_CONTROL_REQUIRED",
    "STATUS_ELIGIBLE",
    "STATUS_MARKET_FALSIFIER_FIRST",
    "STATUS_OBSERVABILITY_BLOCKED",
    "STATUS_RUNNER_UP_PAUSE",
    "build_challenger_packet",
    "build_representation_probe_packet",
    "control_baseline_from_receipt",
    "control_memory_baseline_sha256",
    "existing_hfic_lifecycle_fixture_input",
    "existing_hfic_packet",
    "prepare_existing_hfic_lifecycle_fixture",
    "representation_probe_identity_sha256",
    "representation_search_key_sha256",
    "representation_status",
    "get_representation_status",
]
