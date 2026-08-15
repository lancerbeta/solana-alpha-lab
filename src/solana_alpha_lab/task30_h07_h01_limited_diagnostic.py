"""Offline measurability diagnostic of the frozen H07/H01 estimand for TASK-30 A25.

The atom answers one question: can the frozen ``RC001-H07-H01-LIQUIDITY-RETENTION``
estimand be computed honestly from the A24 96-slot panel, and if so with what
precision. It never restates the estimand; both frozen owners are read and
cross-bound, and every declared absence is proved against the actual panel shape.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any

from solana_alpha_lab.task28_rc001_registry_freeze import canonical_definition_hash
from solana_alpha_lab.task30_raw_to_pit_admissibility import (
    execute_admissibility,
)
from solana_alpha_lab.task30_raw_to_pit_admissibility import (
    load_policy as load_upstream_policy,
)

ATOM_ID = "T30-A25_H07_H01_FROZEN_LIMITED_DIAGNOSTIC_AND_MEASURABILITY_VERDICT_V1"
SCHEMA = "smial.task30.h07-h01-limited-diagnostic.policy"
RESULT_SCHEMA = "smial.task30.a25-h07-h01-limited-diagnostic.result"
TERMINAL_OUTCOMES = (
    "ESTIMAND_MEASURABLE_AND_DECISIVE_ON_FROZEN_PANEL",
    "ESTIMAND_MEASURABLE_UNDERPOWERED_WITH_EXACT_DATA_SPEC",
    "ESTIMAND_NOT_COMPUTABLE_TARGETED_CAPABILITY_GAP_PROVEN",
    "STOP_INTEGRITY_CONFLICT",
)
SUPPLY_STATES = ("SUPPLIED", "PARTIAL_TYPED_GAP", "NOT_SUPPLIED")
COMPUTABILITY_STATES = (
    "COMPUTABLE",
    "COMPUTABLE_WITH_TYPED_GAPS",
    "NOT_COMPUTABLE",
)
SUPPLY_KINDS = (
    "PANEL_CONSTANT",
    "PIT_FIELD",
    "ROW_FIELD",
    "ROW_FIELD_FRESH_ONLY",
    "IDENTIFIER_ONLY_NOT_AN_OBSERVATION",
    "ABSENT",
)
RATE_QUANTUM = Decimal("0.000001")


class A25Error(ValueError):
    """Policy, frozen-binding or projection identity is invalid."""


class A25IntegrityError(A25Error):
    """Frozen truth cannot be reconciled with the retained panel."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise A25Error(code)


def _integrity(condition: bool, code: str) -> None:
    if not condition:
        raise A25IntegrityError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _sequence(value: object, code: str) -> Sequence[Any]:
    _require(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes)),
        code,
    )
    return value


def _text(value: object, code: str) -> str:
    _require(isinstance(value, str) and bool(value), code)
    return value


def _int(value: object, code: str) -> int:
    _require(isinstance(value, int) and not isinstance(value, bool), code)
    return value


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def format_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalize_definition_input(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _rate(numerator: int, denominator: int) -> str:
    _require(denominator > 0, "RATE_DENOMINATOR_INVALID")
    quotient = Decimal(numerator) / Decimal(denominator)
    return format(quotient.quantize(RATE_QUANTUM, rounding=ROUND_HALF_EVEN), "f")


def _resolve(document: Mapping[str, Any], dotted: str) -> tuple[bool, Any]:
    current: Any = document
    for part in dotted.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _leaf_names(value: Any, sink: set[str]) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            sink.add(str(key))
            _leaf_names(item, sink)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            _leaf_names(item, sink)


def load_policy(path: Path) -> dict[str, Any]:
    import yaml

    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    policy = dict(_mapping(document, "POLICY_INVALID"))
    _require(policy.get("schema") == SCHEMA, "POLICY_SCHEMA_DRIFT")
    _require(policy.get("schema_version") == "1.0", "POLICY_VERSION_DRIFT")
    _require(policy.get("atom_id") == ATOM_ID, "POLICY_ATOM_DRIFT")
    _require(
        list(policy.get("terminal_outcomes") or []) == list(TERMINAL_OUTCOMES),
        "POLICY_TERMINAL_OUTCOME_DRIFT",
    )
    supply = _mapping(policy.get("lane_field_supply"), "LANE_SUPPLY_INVALID")
    for lane, fields in supply.items():
        for field, spec in _mapping(fields, f"LANE_FIELDS_INVALID:{lane}").items():
            kind = _text(
                _mapping(spec, f"FIELD_SPEC_INVALID:{lane}.{field}").get("kind"),
                f"FIELD_KIND_INVALID:{lane}.{field}",
            )
            _require(kind in SUPPLY_KINDS, f"FIELD_KIND_UNKNOWN:{lane}.{field}:{kind}")
    return policy


def read_frozen_estimand(repo_root: Path, policy: Mapping[str, Any]) -> dict[str, Any]:
    """Read both frozen owners of the H07/H01 estimand and cross-bind them.

    Nothing here restates the estimand: the RC001 freeze owns the target metrics,
    definition inputs and falsifier, and the A8 entry-gate policy owns the lane
    field contracts. A disagreement between them is an integrity conflict.
    """
    import yaml

    frozen = _mapping(policy.get("frozen_definition"), "FROZEN_DEFINITION_INVALID")
    expected_hash = _text(frozen.get("definition_sha256"), "FROZEN_HASH_INVALID")
    group_id = _text(frozen.get("group_id"), "FROZEN_GROUP_INVALID")

    freeze_path = repo_root / _text(frozen.get("path"), "FROZEN_PATH_INVALID")
    freeze_document = _mapping(
        yaml.safe_load(freeze_path.read_text(encoding="utf-8")),
        "RC001_FREEZE_INVALID",
    )
    group: Mapping[str, Any] | None = None
    for candidate in _sequence(
        freeze_document.get("hypothesis_groups"), "RC001_GROUPS_INVALID"
    ):
        mapped = _mapping(candidate, "RC001_GROUP_INVALID")
        if mapped.get("group_id") == group_id:
            group = mapped
            break
    _integrity(group is not None, "RC001_GROUP_MISSING")
    assert group is not None
    _integrity(group.get("definition_sha256") == expected_hash, "RC001_DEFINITION_DRIFT")
    _integrity(
        canonical_definition_hash(group) == expected_hash,
        "RC001_CANONICAL_HASH_DRIFT",
    )

    gate_path = repo_root / _text(
        frozen.get("entry_gate_policy_path"), "ENTRY_GATE_PATH_INVALID"
    )
    gate = _mapping(
        yaml.safe_load(gate_path.read_text(encoding="utf-8")),
        "ENTRY_GATE_INVALID",
    )
    _integrity(
        gate.get("atom_id") == frozen.get("entry_gate_atom_id"),
        "ENTRY_GATE_ATOM_DRIFT",
    )
    gate_frozen = _mapping(
        gate.get("frozen_definition"), "ENTRY_GATE_FROZEN_INVALID"
    )
    _integrity(
        gate_frozen.get("definition_sha256") == expected_hash
        and gate_frozen.get("group_id") == group_id,
        "FROZEN_OWNER_DISAGREEMENT",
    )
    _integrity(
        list(gate_frozen.get("definition_inputs") or [])
        == list(group.get("definition_inputs") or []),
        "FROZEN_DEFINITION_INPUT_DRIFT",
    )

    lanes: dict[str, list[str]] = {}
    for lane_name, lane in _mapping(gate.get("lanes"), "GATE_LANES_INVALID").items():
        mapped = _mapping(lane, f"GATE_LANE_INVALID:{lane_name}")
        fields = mapped.get("required_fields")
        if fields is None:
            continue
        lanes[str(lane_name)] = [
            _text(item, f"GATE_LANE_FIELD_INVALID:{lane_name}")
            for item in _sequence(fields, f"GATE_LANE_FIELDS_INVALID:{lane_name}")
        ]
    gate_requirements = _mapping(
        gate.get("requirements"), "GATE_REQUIREMENTS_INVALID"
    )
    for derived_name, derived in _mapping(
        policy.get("derived_lanes"), "DERIVED_LANES_INVALID"
    ).items():
        mapped = _mapping(derived, f"DERIVED_LANE_INVALID:{derived_name}")
        requirement = _mapping(
            gate_requirements.get(
                _text(
                    mapped.get("entry_gate_requirement"),
                    f"DERIVED_LANE_REQUIREMENT_INVALID:{derived_name}",
                )
            ),
            f"DERIVED_LANE_REQUIREMENT_MISSING:{derived_name}",
        )
        source_key = _text(
            mapped.get("field_source_key"),
            f"DERIVED_LANE_SOURCE_INVALID:{derived_name}",
        )
        lanes[str(derived_name)] = [
            _text(item, f"DERIVED_LANE_FIELD_INVALID:{derived_name}")
            for item in _sequence(
                requirement.get(source_key),
                f"DERIVED_LANE_FIELDS_INVALID:{derived_name}",
            )
        ]

    input_lanes = _mapping(
        policy.get("definition_input_lanes"), "DEFINITION_INPUT_LANES_INVALID"
    )
    definition_inputs = [
        _text(item, "DEFINITION_INPUT_INVALID")
        for item in _sequence(group.get("definition_inputs"), "DEFINITION_INPUTS_INVALID")
    ]
    _integrity(
        set(input_lanes) == set(definition_inputs),
        "DEFINITION_INPUT_LANE_COVERAGE_DRIFT",
    )
    input_bindings: dict[str, dict[str, str]] = {}
    for definition_input in definition_inputs:
        requirement_key = _normalize_definition_input(definition_input)
        requirement = _mapping(
            gate_requirements.get(requirement_key),
            f"DEFINITION_INPUT_REQUIREMENT_MISSING:{requirement_key}",
        )
        declared_lane = _text(
            input_lanes.get(definition_input), "DEFINITION_INPUT_LANE_INVALID"
        )
        derived_lanes = _mapping(policy.get("derived_lanes"), "DERIVED_LANES_INVALID")
        if declared_lane in derived_lanes:
            _integrity(
                _mapping(
                    derived_lanes.get(declared_lane), "DERIVED_LANE_INVALID"
                ).get("entry_gate_requirement")
                == requirement_key,
                f"DEFINITION_INPUT_DERIVED_LANE_DRIFT:{requirement_key}",
            )
        else:
            _integrity(
                requirement.get("lane") == declared_lane,
                f"DEFINITION_INPUT_LANE_DRIFT:{requirement_key}",
            )
        input_bindings[definition_input] = {
            "entry_gate_requirement": requirement_key,
            "lane": declared_lane,
            "state": _text(requirement.get("state"), "REQUIREMENT_STATE_INVALID"),
        }

    for requirement_key, expectation in _mapping(
        policy.get("structurally_unsupported_requirements"),
        "UNSUPPORTED_REQUIREMENTS_INVALID",
    ).items():
        requirement = _mapping(
            gate_requirements.get(requirement_key),
            f"UNSUPPORTED_REQUIREMENT_MISSING:{requirement_key}",
        )
        mapped = _mapping(expectation, f"UNSUPPORTED_EXPECTATION_INVALID:{requirement_key}")
        _integrity(
            requirement.get("state") == mapped.get("expected_state")
            and requirement.get("future_capture_capable")
            is mapped.get("expected_future_capture_capable"),
            f"UNSUPPORTED_REQUIREMENT_DRIFT:{requirement_key}",
        )

    parameter_policy = _mapping(
        group.get("parameter_policy"), "PARAMETER_POLICY_INVALID"
    )
    return {
        "group_id": group_id,
        "definition_sha256": expected_hash,
        "definition_inputs": definition_inputs,
        "definition_input_bindings": input_bindings,
        "falsifier": _text(group.get("falsifier"), "FALSIFIER_INVALID"),
        "target_metrics": [
            _text(item, "TARGET_METRIC_INVALID")
            for item in _sequence(group.get("target_metrics"), "TARGET_METRICS_INVALID")
        ],
        "allowed_parameter_ids": [
            _text(item, "ALLOWED_PARAMETER_INVALID")
            for item in _sequence(
                parameter_policy.get("allowed_parameter_ids"), "ALLOWED_PARAMETERS_INVALID"
            )
        ],
        "forbidden_parameters": [
            _text(item, "FORBIDDEN_PARAMETER_INVALID")
            for item in _sequence(
                parameter_policy.get("forbidden"), "FORBIDDEN_PARAMETERS_INVALID"
            )
        ],
        "expected_admissibility_state": _text(
            _mapping(
                group.get("expected_admissibility"), "EXPECTED_ADMISSIBILITY_INVALID"
            ).get("state"),
            "EXPECTED_ADMISSIBILITY_STATE_INVALID",
        ),
        "lanes": lanes,
        "gate_document": gate,
        "freeze_document": freeze_document,
    }


def verify_lane_coverage(policy: Mapping[str, Any], frozen: Mapping[str, Any]) -> None:
    """Every frozen lane field must be classified exactly once, with no additions."""
    supply = _mapping(policy.get("lane_field_supply"), "LANE_SUPPLY_INVALID")
    lanes = _mapping(frozen.get("lanes"), "FROZEN_LANES_INVALID")
    for lane_name, fields in supply.items():
        frozen_fields = lanes.get(lane_name)
        _integrity(frozen_fields is not None, f"LANE_NOT_FROZEN:{lane_name}")
        _integrity(
            set(_mapping(fields, "LANE_FIELDS_INVALID")) == set(frozen_fields or []),
            f"LANE_FIELD_COVERAGE_DRIFT:{lane_name}",
        )


def reproduce_panel(
    *,
    repo_root: Path,
    policy: Mapping[str, Any],
    a22_payload: bytes,
    a23_payload: bytes,
    measured_as_of: datetime,
) -> dict[str, Any]:
    """Recompute the A24 panel from the retained bytes; never fork its decoder."""
    upstream = _mapping(policy.get("upstream_panel"), "UPSTREAM_PANEL_INVALID")
    upstream_policy = load_upstream_policy(
        repo_root / _text(upstream.get("policy_path"), "UPSTREAM_PATH_INVALID")
    )
    _integrity(
        upstream_policy.get("atom_id") == upstream.get("atom_id"),
        "UPSTREAM_ATOM_DRIFT",
    )
    result = execute_admissibility(
        repo_root=repo_root,
        policy=upstream_policy,
        a22_payload=a22_payload,
        a23_payload=a23_payload,
        measured_as_of=measured_as_of,
    )
    upstream_cause = _mapping(result.get("decision"), "UPSTREAM_DECISION_INVALID").get(
        "integrity_error"
    )
    _integrity(
        result.get("terminal_decision") == upstream.get("required_terminal_decision"),
        f"UPSTREAM_TERMINAL_DRIFT:{result.get('terminal_decision')}:{upstream_cause}",
    )
    panel = list(_sequence(result.get("panel_96_slots"), "UPSTREAM_PANEL_ROWS_INVALID"))
    _integrity(
        len(panel) == _int(upstream.get("panel_row_count"), "PANEL_ROW_COUNT_INVALID"),
        "UPSTREAM_PANEL_ROW_COUNT_DRIFT",
    )
    result["upstream_policy"] = upstream_policy
    return result


def slot_state_counts(panel: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in panel:
        state = _text(_mapping(row, "PANEL_ROW_INVALID").get("state"), "SLOT_STATE_INVALID")
        counts[state] = counts.get(state, 0) + 1
    return counts


def verify_orientation(
    policy: Mapping[str, Any], result: Mapping[str, Any]
) -> dict[str, Any]:
    """Fail closed if the reproduced batch drifts from the frozen A24 orientation."""
    expected = _mapping(policy.get("orientation_constants"), "ORIENTATION_INVALID")
    reconciliation = _mapping(result.get("reconciliation"), "RECONCILIATION_INVALID")
    for key, value in expected.items():
        if key == "slot_state_counts":
            continue
        _integrity(
            reconciliation.get(key) == value,
            f"ORIENTATION_DRIFT:{key}:{reconciliation.get(key)}",
        )
    observed_states = slot_state_counts(
        _sequence(result.get("panel_96_slots"), "PANEL_INVALID")
    )
    expected_states = _mapping(
        expected.get("slot_state_counts"), "ORIENTATION_SLOT_STATES_INVALID"
    )
    for state, value in expected_states.items():
        _integrity(
            observed_states.get(str(state), 0) == value,
            f"ORIENTATION_SLOT_STATE_DRIFT:{state}:{observed_states.get(str(state), 0)}",
        )
    return {
        "reconciliation": {
            str(key): reconciliation.get(key)
            for key in expected
            if key != "slot_state_counts"
        },
        "slot_state_counts": {
            str(state): observed_states.get(str(state), 0) for state in expected_states
        },
    }


def evaluate_lane_supply(
    policy: Mapping[str, Any], result: Mapping[str, Any]
) -> dict[str, dict[str, dict[str, Any]]]:
    """Classify every frozen lane field against the reproduced panel shape.

    A field declared ``ABSENT`` is proved absent: the union of leaf names across
    the panel rows, the PIT block and the reference subject must not contain any
    of its declared equivalents.
    """
    panel = [
        _mapping(row, "PANEL_ROW_INVALID")
        for row in _sequence(result.get("panel_96_slots"), "PANEL_INVALID")
    ]
    pit = _mapping(result.get("pit"), "PIT_INVALID")
    subject = _mapping(
        _mapping(result.get("upstream_policy"), "UPSTREAM_POLICY_INVALID").get(
            "reference_subject"
        ),
        "SUBJECT_INVALID",
    )
    leaves: set[str] = set()
    _leaf_names(panel, leaves)
    _leaf_names(pit, leaves)
    _leaf_names(subject, leaves)

    report: dict[str, dict[str, dict[str, Any]]] = {}
    for lane_name, fields in _mapping(
        policy.get("lane_field_supply"), "LANE_SUPPLY_INVALID"
    ).items():
        lane_report: dict[str, dict[str, Any]] = {}
        for field_name, raw_spec in _mapping(fields, "LANE_FIELDS_INVALID").items():
            spec = _mapping(raw_spec, "FIELD_SPEC_INVALID")
            kind = _text(spec.get("kind"), "FIELD_KIND_INVALID")
            entry: dict[str, Any] = {"kind": kind, "observation_rows": len(panel)}
            if kind == "ABSENT":
                for leaf in _sequence(
                    spec.get("equivalent_leaf_names"), "EQUIVALENT_LEAVES_INVALID"
                ):
                    _integrity(
                        _text(leaf, "EQUIVALENT_LEAF_INVALID") not in leaves,
                        f"DECLARED_ABSENT_FIELD_PRESENT:{lane_name}.{field_name}:{leaf}",
                    )
                entry.update(
                    supply="NOT_SUPPLIED",
                    non_null_observations=0,
                    reason=_text(spec.get("reason"), "FIELD_REASON_INVALID"),
                )
            elif kind == "IDENTIFIER_ONLY_NOT_AN_OBSERVATION":
                found, value = _resolve(subject, _text(spec.get("source"), "SRC_INVALID"))
                _integrity(found and value not in (None, ""), f"IDENTIFIER_MISSING:{field_name}")
                entry.update(
                    supply="NOT_SUPPLIED",
                    non_null_observations=0,
                    reason=_text(spec.get("reason"), "FIELD_REASON_INVALID"),
                )
            elif kind in {"PANEL_CONSTANT", "PIT_FIELD"}:
                document = subject if kind == "PANEL_CONSTANT" else pit
                found, value = _resolve(document, _text(spec.get("source"), "SRC_INVALID"))
                _integrity(found, f"CONSTANT_SOURCE_MISSING:{lane_name}.{field_name}")
                _integrity(
                    value not in (None, ""),
                    f"CONSTANT_SOURCE_EMPTY:{lane_name}.{field_name}",
                )
                entry.update(
                    supply="SUPPLIED",
                    non_null_observations=len(panel),
                    observation_rows=len(panel),
                )
            elif kind in {"ROW_FIELD", "ROW_FIELD_FRESH_ONLY"}:
                source = _text(spec.get("source"), "SRC_INVALID")
                eligible = 0
                non_null = 0
                for row in panel:
                    found, value = _resolve(row, source)
                    _integrity(found, f"ROW_SOURCE_MISSING:{lane_name}.{field_name}")
                    if kind == "ROW_FIELD_FRESH_ONLY":
                        stale_found, stale = _resolve(
                            row, _text(spec.get("staleness_flag"), "STALE_FLAG_INVALID")
                        )
                        _integrity(
                            stale_found and isinstance(stale, bool),
                            f"STALENESS_FLAG_INVALID:{lane_name}.{field_name}",
                        )
                        if stale:
                            continue
                    eligible += 1
                    if value is not None:
                        non_null += 1
                entry.update(
                    supply=(
                        "SUPPLIED"
                        if non_null == len(panel)
                        else "PARTIAL_TYPED_GAP"
                        if non_null
                        else "NOT_SUPPLIED"
                    ),
                    non_null_observations=non_null,
                    eligible_rows=eligible,
                )
            else:  # pragma: no cover - load_policy already closes the enum
                raise A25Error(f"FIELD_KIND_UNKNOWN:{kind}")
            _require(entry["supply"] in SUPPLY_STATES, "SUPPLY_STATE_INVALID")
            lane_report[str(field_name)] = entry
        report[str(lane_name)] = lane_report
    return report


def assess_metric_computability(
    policy: Mapping[str, Any],
    frozen: Mapping[str, Any],
    supply: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, dict[str, Any]]:
    """Decide computability per frozen target metric, justified by the frozen gate."""
    requirements = _mapping(
        policy.get("target_metric_requirements"), "METRIC_REQUIREMENTS_INVALID"
    )
    _integrity(
        set(requirements) == set(frozen["target_metrics"]),
        "TARGET_METRIC_SET_DRIFT",
    )
    gate = _mapping(frozen.get("gate_document"), "GATE_DOCUMENT_INVALID")
    assessment: dict[str, dict[str, Any]] = {}
    for metric in sorted(requirements):
        spec = _mapping(requirements[metric], f"METRIC_SPEC_INVALID:{metric}")
        justification = _mapping(
            spec.get("frozen_justification"), f"METRIC_JUSTIFICATION_INVALID:{metric}"
        )
        found, value = _resolve(
            gate, _text(justification.get("path"), "JUSTIFICATION_PATH_INVALID")
        )
        _integrity(found, f"METRIC_JUSTIFICATION_MISSING:{metric}")
        if "must_equal" in justification:
            _integrity(
                value == justification["must_equal"],
                f"METRIC_JUSTIFICATION_DRIFT:{metric}",
            )
        if "must_contain" in justification:
            _integrity(
                isinstance(value, Sequence)
                and not isinstance(value, (str, bytes))
                and justification["must_contain"] in value,
                f"METRIC_JUSTIFICATION_DRIFT:{metric}",
            )
        missing: list[str] = []
        typed_gaps: list[str] = []
        lanes = [
            _text(item, "METRIC_LANE_INVALID")
            for item in _sequence(spec.get("required_lanes"), "METRIC_LANES_INVALID")
        ]
        for lane in lanes:
            lane_report = supply.get(lane)
            _integrity(lane_report is not None, f"METRIC_LANE_UNKNOWN:{metric}:{lane}")
            for field in sorted(lane_report or {}):
                state = (lane_report or {})[field]["supply"]
                if state == "NOT_SUPPLIED":
                    missing.append(f"{lane}.{field}")
                elif state == "PARTIAL_TYPED_GAP":
                    typed_gaps.append(f"{lane}.{field}")
        computability = (
            "NOT_COMPUTABLE"
            if missing
            else "COMPUTABLE_WITH_TYPED_GAPS"
            if typed_gaps
            else "COMPUTABLE"
        )
        _require(computability in COMPUTABILITY_STATES, "COMPUTABILITY_STATE_INVALID")
        assessment[metric] = {
            "computability": computability,
            "required_lanes": lanes,
            "missing_fields": missing,
            "typed_gap_fields": typed_gaps,
        }
    return assessment


def resolve_frozen_parameters(
    policy: Mapping[str, Any],
    frozen: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Report which frozen allowed parameters actually resolve to bytes."""
    declared = _mapping(
        policy.get("frozen_parameter_resolution"), "PARAMETER_RESOLUTION_INVALID"
    )
    _integrity(
        set(declared) == set(frozen["allowed_parameter_ids"]),
        "ALLOWED_PARAMETER_COVERAGE_DRIFT",
    )
    freeze_document = _mapping(frozen.get("freeze_document"), "FREEZE_DOCUMENT_INVALID")
    freeze_leaves: set[str] = set()
    _leaf_names(freeze_document, freeze_leaves)
    window = _mapping(
        _mapping(result.get("upstream_policy"), "UPSTREAM_POLICY_INVALID").get(
            "pilot_window"
        ),
        "WINDOW_INVALID",
    )
    resolution: dict[str, dict[str, Any]] = {}
    for parameter in sorted(declared):
        spec = _mapping(declared[parameter], f"PARAMETER_SPEC_INVALID:{parameter}")
        resolved = spec.get("resolved")
        _require(isinstance(resolved, bool), f"PARAMETER_RESOLVED_INVALID:{parameter}")
        if resolved:
            _integrity(
                spec.get("resolved_as_seconds")
                == window.get("interval_seconds"),
                f"PARAMETER_BINDING_DRIFT:{parameter}",
            )
            resolution[parameter] = {
                "resolved": True,
                "resolved_as_seconds": spec.get("resolved_as_seconds"),
                "binding": _text(spec.get("binding"), "PARAMETER_BINDING_INVALID"),
            }
            continue
        _integrity(
            parameter not in freeze_leaves,
            f"PARAMETER_DECLARED_UNRESOLVED_BUT_DEFINED:{parameter}",
        )
        _integrity(
            spec.get("resolved_bucket_count") is None,
            f"PARAMETER_UNRESOLVED_BUT_COUNTED:{parameter}",
        )
        resolution[parameter] = {
            "resolved": False,
            "resolved_bucket_count": None,
            "unresolved_code": _text(
                spec.get("unresolved_code"), "PARAMETER_CODE_INVALID"
            ),
            "owner_document": _text(
                spec.get("owner_document"), "PARAMETER_OWNER_INVALID"
            ),
            "non_adopted_observed_convention": _text(
                spec.get("non_adopted_observed_convention"),
                "PARAMETER_CONVENTION_INVALID",
            ),
        }
    return resolution


def missingness_statistics(
    policy: Mapping[str, Any], result: Mapping[str, Any]
) -> dict[str, Any]:
    """Compute the one frozen metric the panel can carry, with explicit clustering.

    ``STATE_PERSISTENCE_PROVEN`` slots are typed gaps, never observed trades, and
    carried-forward reserves are never fresh liquidity observations.
    """
    consumption = _mapping(
        policy.get("statistic_slot_consumption"), "SLOT_CONSUMPTION_INVALID"
    )
    _integrity(
        consumption.get("state_persistence_counts_as_observed_trade") is False
        and consumption.get("carry_forward_counts_as_fresh_liquidity_observation")
        is False,
        "SLOT_CONSUMPTION_POLICY_DRIFT",
    )
    observed_states = {
        _text(item, "OBSERVED_STATE_INVALID")
        for item in _sequence(consumption.get("observed_states"), "OBSERVED_STATES_INVALID")
    }
    gap_states = {
        _text(item, "GAP_STATE_INVALID")
        for item in _sequence(consumption.get("typed_gap_states"), "GAP_STATES_INVALID")
    }
    unknown_states = {
        _text(item, "UNKNOWN_STATE_INVALID")
        for item in _sequence(consumption.get("unknown_states"), "UNKNOWN_STATES_INVALID")
    }
    _integrity(
        not (observed_states & gap_states)
        and not (observed_states & unknown_states)
        and not (gap_states & unknown_states),
        "SLOT_CONSUMPTION_OVERLAP",
    )
    panel = [
        _mapping(row, "PANEL_ROW_INVALID")
        for row in _sequence(result.get("panel_96_slots"), "PANEL_INVALID")
    ]
    total = len(panel)
    counts = slot_state_counts(panel)
    _integrity(
        set(counts) <= observed_states | gap_states | unknown_states,
        "SLOT_STATE_OUTSIDE_CONSUMPTION_POLICY",
    )
    observed = sum(counts.get(state, 0) for state in observed_states)
    gaps = sum(counts.get(state, 0) for state in gap_states)
    unknown = sum(counts.get(state, 0) for state in unknown_states)
    _integrity(observed + gaps + unknown == total, "SLOT_CONSUMPTION_TOTAL_DRIFT")
    _integrity(unknown == 0, "UNKNOWN_COVERAGE_PRESENT")
    fresh_liquidity = sum(
        1
        for row in panel
        if _mapping(row.get("reserves"), "RESERVES_INVALID").get("carry_forward") is False
        and _mapping(row.get("reserves"), "RESERVES_INVALID").get(
            "raw_quote_reserve_atomic"
        )
        is not None
    )
    carried_liquidity = sum(
        1
        for row in panel
        if _mapping(row.get("reserves"), "RESERVES_INVALID").get("carry_forward") is True
    )
    return {
        "metric": "MISSINGNESS_RATE",
        "lane": "PIT_MARKET",
        "slots_total": total,
        "slots_consumed_as_observed": observed,
        "slots_consumed_as_typed_gap": gaps,
        "slots_consumed_as_unknown": unknown,
        "consumed_slot_states": {state: counts.get(state, 0) for state in sorted(counts)},
        "ohlc_missingness_numerator": gaps,
        "ohlc_missingness_denominator": total,
        "ohlc_missingness_rate": _rate(gaps, total),
        "fresh_liquidity_observation_slots": fresh_liquidity,
        "carried_forward_liquidity_slots": carried_liquidity,
        "fresh_liquidity_observation_rate": _rate(fresh_liquidity, total),
        "carry_forward_is_an_observation": False,
    }


def precision_and_power(
    policy: Mapping[str, Any], statistics: Mapping[str, Any]
) -> dict[str, Any]:
    """State precision honestly: one pool-day is one cluster, not 96 observations."""
    design = _mapping(policy.get("cluster_design"), "CLUSTER_DESIGN_INVALID")
    pools = _int(design.get("pools"), "CLUSTER_POOLS_INVALID")
    days = _int(design.get("days"), "CLUSTER_DAYS_INVALID")
    clusters = _int(design.get("independent_clusters"), "CLUSTER_COUNT_INVALID")
    _integrity(clusters == pools * days, "CLUSTER_COUNT_DRIFT")
    _integrity(
        design.get("slots_are_independent_replicates") is False,
        "SLOT_INDEPENDENCE_CLAIM_FORBIDDEN",
    )
    _integrity(
        _int(design.get("slots_per_cluster"), "SLOTS_PER_CLUSTER_INVALID")
        == _int(statistics.get("slots_total"), "SLOTS_TOTAL_INVALID"),
        "CLUSTER_SLOT_COUNT_DRIFT",
    )
    total = _int(statistics.get("ohlc_missingness_denominator"), "DENOMINATOR_INVALID")
    numerator = _int(statistics.get("ohlc_missingness_numerator"), "NUMERATOR_INVALID")
    proportion = Decimal(numerator) / Decimal(total)
    naive_variance = proportion * (Decimal(1) - proportion) / Decimal(total)
    naive_se = naive_variance.sqrt()
    return {
        "cluster_unit": _text(design.get("cluster_unit"), "CLUSTER_UNIT_INVALID"),
        "pools": pools,
        "days": days,
        "independent_clusters": clusters,
        "effective_sample_size_for_the_estimand": clusters,
        "between_cluster_degrees_of_freedom": max(clusters - 1, 0),
        "standard_error": None,
        "standard_error_status": "UNDEFINED_SINGLE_CLUSTER_ZERO_BETWEEN_CLUSTER_DF",
        "confidence_interval": None,
        "naive_binomial_se_if_slots_were_independent": format(
            naive_se.quantize(RATE_QUANTUM, rounding=ROUND_HALF_EVEN), "f"
        ),
        "naive_binomial_se_validity": "INVALID_SLOTS_ARE_NOT_INDEPENDENT_REPLICATES",
        "naive_binomial_se_usage": "REPORTED_ONLY_TO_BE_REFUSED_NEVER_AS_PRECISION",
        "slot_dependence_reason": _text(
            design.get("slot_dependence_reason"), "SLOT_DEPENDENCE_REASON_INVALID"
        ),
    }


def build_required_data_specification(
    policy: Mapping[str, Any],
    frozen: Mapping[str, Any],
    supply: Mapping[str, Mapping[str, Mapping[str, Any]]],
    parameters: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Name the exact fields and minimum cluster scale a decisive test would need."""
    spec = _mapping(
        policy.get("required_data_specification"), "REQUIRED_DATA_SPEC_INVALID"
    )
    missing_fields = sorted(
        f"{lane}.{field}"
        for lane, fields in supply.items()
        for field, entry in fields.items()
        if entry["supply"] == "NOT_SUPPLIED"
    )
    typed_gap_fields = sorted(
        f"{lane}.{field}"
        for lane, fields in supply.items()
        for field, entry in fields.items()
        if entry["supply"] == "PARTIAL_TYPED_GAP"
    )
    unresolved = sorted(
        name for name, entry in parameters.items() if entry.get("resolved") is False
    )
    bucket_parameter = _text(
        spec.get("notional_bucket_parameter"), "SPEC_BUCKET_PARAMETER_INVALID"
    )
    _integrity(
        bucket_parameter in parameters, f"SPEC_BUCKET_PARAMETER_UNKNOWN:{bucket_parameter}"
    )
    bucket_count = parameters[bucket_parameter].get("resolved_bucket_count")
    _integrity(
        spec.get("decisive_scale_derivable_from_this_panel") is False,
        "DECISIVE_SCALE_CLAIM_FORBIDDEN",
    )
    return {
        "cluster_unit": _text(spec.get("cluster_unit"), "SPEC_CLUSTER_UNIT_INVALID"),
        "minimum_clusters_for_defined_between_cluster_variance": _int(
            spec.get("minimum_clusters_for_defined_between_cluster_variance"),
            "SPEC_MIN_VARIANCE_CLUSTERS_INVALID",
        ),
        "minimum_clusters_for_two_group_cluster_level_test": _int(
            spec.get("minimum_clusters_for_two_group_cluster_level_test"),
            "SPEC_MIN_TEST_CLUSTERS_INVALID",
        ),
        "slots_per_cluster": _int(
            spec.get("slots_per_cluster"), "SPEC_SLOTS_INVALID"
        ),
        "slot_interval_seconds": _int(
            spec.get("slot_interval_seconds"), "SPEC_INTERVAL_INVALID"
        ),
        "slot_coverage_policy": _text(
            spec.get("slot_coverage_policy"), "SPEC_COVERAGE_INVALID"
        ),
        "route_evaluations_per_cluster_formula": _text(
            spec.get("route_evaluations_per_cluster_formula"), "SPEC_FORMULA_INVALID"
        ),
        "notional_bucket_parameter": bucket_parameter,
        "notional_bucket_count": bucket_count,
        "required_fields_currently_absent": missing_fields,
        "required_fields_with_typed_gaps": typed_gap_fields,
        "unresolved_frozen_parameters": unresolved,
        "decisive_scale_derivable_from_this_panel": False,
        "decisive_scale_blocker": _text(
            spec.get("decisive_scale_blocker"), "SPEC_BLOCKER_INVALID"
        ),
        "next_measurement_purpose": _text(
            spec.get("next_measurement_purpose"), "SPEC_PURPOSE_INVALID"
        ),
        "frozen_falsifier": _text(frozen.get("falsifier"), "FALSIFIER_INVALID"),
    }


def issue_verdict(
    *,
    policy: Mapping[str, Any],
    frozen: Mapping[str, Any],
    supply: Mapping[str, Mapping[str, Mapping[str, Any]]],
    metrics: Mapping[str, Mapping[str, Any]],
    parameters: Mapping[str, Mapping[str, Any]],
    power: Mapping[str, Any],
    specification: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail-closed selection of exactly one terminal outcome."""
    not_computable = sorted(
        metric
        for metric, entry in metrics.items()
        if entry["computability"] == "NOT_COMPUTABLE"
    )
    ambiguities = sorted(
        f"FROZEN_PARAMETER_UNRESOLVED:{name}"
        for name, entry in parameters.items()
        if entry.get("resolved") is False
    )
    clusters = _int(
        power.get("independent_clusters"), "POWER_CLUSTER_COUNT_INVALID"
    )
    minimum_clusters = _int(
        specification.get("minimum_clusters_for_two_group_cluster_level_test"),
        "SPEC_MIN_TEST_CLUSTERS_INVALID",
    )
    missing_capabilities = sorted(
        {
            lane
            for lane, fields in supply.items()
            if any(entry["supply"] == "NOT_SUPPLIED" for entry in fields.values())
        }
    )
    if not_computable:
        terminal = "ESTIMAND_NOT_COMPUTABLE_TARGETED_CAPABILITY_GAP_PROVEN"
    elif ambiguities or clusters < minimum_clusters:
        terminal = "ESTIMAND_MEASURABLE_UNDERPOWERED_WITH_EXACT_DATA_SPEC"
    else:
        terminal = "ESTIMAND_MEASURABLE_AND_DECISIVE_ON_FROZEN_PANEL"
    _require(terminal in TERMINAL_OUTCOMES, "TERMINAL_OUTCOME_INVALID")
    return {
        "terminal_decision": terminal,
        "not_computable_metrics": not_computable,
        "computable_metrics": sorted(
            metric
            for metric, entry in metrics.items()
            if entry["computability"] != "NOT_COMPUTABLE"
        ),
        "missing_capability_lanes": missing_capabilities,
        "frozen_definition_ambiguities": ambiguities,
        "task_state": "BLOCKED_DATA",
        "rc001_promoted": False,
        "limitations": [
            "SINGLE_POOL_DAY_IS_ONE_CLUSTER_NOT_NINETY_SIX_OBSERVATIONS",
            "BETWEEN_CLUSTER_VARIANCE_UNIDENTIFIED_NO_VALID_STANDARD_ERROR",
            "STATE_PERSISTENCE_SLOTS_ARE_TYPED_GAPS_NOT_OBSERVED_TRADES",
            "NO_ROUTE_FEASIBILITY_LANE_OBSERVATION_IN_A_TRADE_ONLY_PANEL",
            "NO_MIGRATION_BOUNDARY_CONTINUITY_IN_A_SINGLE_DAY_WINDOW",
            "RETROSPECTIVE_ONLY_NO_PROSPECTIVE_PIT_ROUTE",
            "REPRESENTATIVENESS_OF_THE_SUBJECT_POOL_NOT_ESTABLISHED",
        ],
        "next_owner_decision": (
            "Decide whether to fund a variance-calibration capture that adds the "
            "named route-feasibility lane over at least the minimum cluster count, "
            "or to retire RC001-H07-H01. This is not a trial, alpha or acceptance."
        ),
    }


def execute_diagnostic(
    *,
    repo_root: Path,
    policy: Mapping[str, Any],
    a22_payload: bytes,
    a23_payload: bytes,
    measured_as_of: datetime,
) -> dict[str, Any]:
    integrity_error: str | None = None
    try:
        frozen = read_frozen_estimand(repo_root, policy)
        verify_lane_coverage(policy, frozen)
        result = reproduce_panel(
            repo_root=repo_root,
            policy=policy,
            a22_payload=a22_payload,
            a23_payload=a23_payload,
            measured_as_of=measured_as_of,
        )
        orientation = verify_orientation(policy, result)
        supply = evaluate_lane_supply(policy, result)
        metrics = assess_metric_computability(policy, frozen, supply)
        parameters = resolve_frozen_parameters(policy, frozen, result)
        statistics = missingness_statistics(policy, result)
        power = precision_and_power(policy, statistics)
        specification = build_required_data_specification(
            policy, frozen, supply, parameters
        )
        verdict = issue_verdict(
            policy=policy,
            frozen=frozen,
            supply=supply,
            metrics=metrics,
            parameters=parameters,
            power=power,
            specification=specification,
        )
        estimand = {
            "group_id": frozen["group_id"],
            "definition_sha256": frozen["definition_sha256"],
            "definition_inputs": frozen["definition_inputs"],
            "definition_input_bindings": frozen["definition_input_bindings"],
            "target_metrics": frozen["target_metrics"],
            "falsifier": frozen["falsifier"],
            "allowed_parameter_ids": frozen["allowed_parameter_ids"],
            "forbidden_parameters": frozen["forbidden_parameters"],
            "expected_admissibility_state": frozen["expected_admissibility_state"],
        }
        pit = dict(_mapping(result.get("pit"), "PIT_INVALID"))
        _integrity(
            pit.get("chain_block_time_used_as_availability") is False
            and pit.get("prospective_pit_route_usable") is False,
            "PIT_DISCIPLINE_REGRESSION",
        )
    except (A25IntegrityError, A25Error) as exc:
        if str(exc) in {
            "POLICY_SCHEMA_DRIFT",
            "POLICY_VERSION_DRIFT",
            "POLICY_ATOM_DRIFT",
            "POLICY_TERMINAL_OUTCOME_DRIFT",
        }:
            raise
        integrity_error = str(exc)
        estimand = {"integrity_error": integrity_error}
        orientation = {"integrity_error": integrity_error}
        supply = {}
        metrics = {}
        parameters = {}
        statistics = {"integrity_error": integrity_error}
        power = {"integrity_error": integrity_error}
        specification = {"integrity_error": integrity_error}
        pit = {
            "retrospective_market_history_usable": False,
            "prospective_pit_route_usable": False,
        }
        verdict = {
            "terminal_decision": "STOP_INTEGRITY_CONFLICT",
            "integrity_error": integrity_error,
            "task_state": "BLOCKED_DATA",
            "rc001_promoted": False,
            "limitations": ["STOP_NO_HEURISTIC_RECOVERY"],
        }
    return {
        "schema": RESULT_SCHEMA,
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "terminal_decision": verdict["terminal_decision"],
        "measured_as_of": format_utc(measured_as_of),
        "frozen_estimand": estimand,
        "orientation": orientation,
        "lane_field_supply": supply,
        "metric_computability": metrics,
        "frozen_parameter_resolution": parameters,
        "statistics": statistics,
        "precision_and_power": power,
        "required_data_specification": specification,
        "pit": pit,
        "verdict": verdict,
        "claims": dict(_mapping(policy.get("claims"), "CLAIMS_INVALID")),
        "side_effects": {
            "provider_requests": 0,
            "credential_reads": 0,
            "retries": 0,
            "fallbacks": 0,
            "cash_spend_usd_cents": 0,
        },
    }


def write_local_projection(
    result: Mapping[str, Any],
    directory: Path,
    *,
    repo_root: Path,
) -> dict[str, str]:
    if directory.exists():
        raise A25Error("LOCAL_PROJECTION_ALREADY_EXISTS")
    directory.mkdir(parents=True, exist_ok=False)
    supply_path = directory / "lane_field_supply.json"
    metric_path = directory / "metric_computability.json"
    manifest_path = directory / "projection_manifest.json"
    supply_path.write_bytes(canonical_json(result["lane_field_supply"]))
    metric_path.write_bytes(canonical_json(result["metric_computability"]))
    manifest = {
        "schema": "smial.task30.a25-h07-h01-limited-diagnostic.projection-manifest",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "terminal_decision": result["terminal_decision"],
        "lane_field_supply_sha256": sha256_bytes(supply_path.read_bytes()),
        "metric_computability_sha256": sha256_bytes(metric_path.read_bytes()),
        "create_only": True,
    }
    manifest_path.write_bytes(canonical_json(manifest))

    def _relative(path: Path) -> str:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()

    return {
        "lane_field_supply": _relative(supply_path),
        "metric_computability": _relative(metric_path),
        "projection_manifest": _relative(manifest_path),
    }
