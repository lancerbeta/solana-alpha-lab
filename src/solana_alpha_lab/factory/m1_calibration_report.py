"""Deterministic M1 calibration projection/report from immutable RDP lineage.

The final M1 scientific input originates exclusively from
immutable/snapshot/sealed Observation RDP lineage (published Parquet panels
plus sealed manifests), never from moving operational SQLite. This module
builds the smallest M1-specific calibration report consistent with existing
repository evidence patterns.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.m1_execution_reality import (
    M1_CAPABILITY_ID,
    M1_SCHEMA_VERSION,
    M1_NOTIONALS,
    NOTIONAL_10_USD,
    NOTIONAL_100_USD,
    NOTIONAL_ATOMIC,
    NOTIONAL_ENTRY_PRIMITIVE,
    NOTIONAL_REVERSE_PRIMITIVE,
    OUTCOME_TWO_WAY,
    classify_execution_outcome,
    cross_notional_transition,
    cross_notional_transition_counts,
    friction_summary,
    leg_class,
    notional_outcome_counts,
    normalized_entry_size_linearity,
    quote_implied_roundtrip_friction,
    verify_denominatorInvariant,
)
from solana_alpha_lab.factory.observation_panel_publisher import (
    rebuild_observation_panel_from_rdp,
)

M1_REPORT_SCHEMA = "smial.m1-calibration-report"
M1_REPORT_SCHEMA_VERSION = "1.0"
M1_REPORT_RULE_VERSION = "M1_CALIBRATION_REPORT_V1.0"

# Decision-time covariates retained from the existing Tokens V2 search
# evidence (§11); each is an already-registered field id.
M1_COVARIATE_FIELDS = (
    "FIELD-USD-PRICE-001",
    "FIELD-LIQUIDITY-USD-001",
    "FIELD-MARKET-CAP-USD-001",
    "FIELD-HOLDER-COUNT-001",
    "FIELD-STATS5M-BUY-VOLUME-001",
    "FIELD-STATS5M-SELL-VOLUME-001",
    "FIELD-STATS5M-TAKER-VOLUME-001",
    "FIELD-STATS5M-NUM-BUYS-001",
    "FIELD-STATS5M-NUM-SELLS-001",
    "FIELD-STATS5M-NUM-TRADERS-001",
    "FIELD-STATS5M-NUM-NET-BUYERS-001",
)

M1_NON_CLAIMS = (
    "NO_REALIZED_COST",
    "NO_REALIZED_FILL",
    "NO_REALIZED_SLIPPAGE",
    "NO_REALIZED_NETRETURN",
    "NO_ALPHA",
    "NO_ADMISSION_RULE",
    "NO_SIGNAL_FEATURE",
    "NO_AUTOMATIC_EXECUTION_EVIDENCE_BINDING",
    "NO_FABRICATED_EXPERIMENT_IDENTITY",
)

_FORBIDDEN_SQLITE_HINTS = ("sqlite", ".db")


class M1CalibrationReportError(ValueError):
    """Typed M1 calibration report failure."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise M1CalibrationReportError(code)


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _leg_from_observation(
    observation: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if observation is None:
        return None
    return {
        "state": str(observation.get("state") or ""),
        "missing_reason": observation.get("missing_reason"),
        "buy_out_amount": observation.get("buy_out_amount"),
        "sell_out_amount": observation.get("sell_out_amount"),
    }


def _decimal_median(values: Sequence[str]) -> str | None:
    from decimal import Decimal

    parsed = sorted(Decimal(v) for v in values)  # noqa: E741
    if not parsed:
        return None
    mid = len(parsed) // 2
    if len(parsed) % 2 == 1:
        return str(parsed[mid])
    return str((parsed[mid - 1] + parsed[mid]) / Decimal(2))


def _covariate_summary(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Typed presence/value summary of decision-time covariates."""

    summary: dict[str, Any] = {}
    field_values = observation.get("field_values")
    by_id = {
        str(item.get("field_id")): item
        for item in (field_values if isinstance(field_values, list) else [])
        if isinstance(item, Mapping)
    }
    for field_id in M1_COVARIATE_FIELDS:
        item = by_id.get(field_id)
        if item is None:
            summary[field_id] = {"state": "FIELD_ABSENT", "value": None}
            continue
        summary[field_id] = {
            "state": str(item.get("state") or "FIELD_ABSENT"),
            "missing_reason": item.get("missing_reason"),
            "value": item.get("typed_value_or_null"),
        }
    return summary


def build_m1_calibration_report(
    *,
    data_root: Path,
    schedule_sha256: str,
    activation_id: str,
    availability_cutoff: datetime,
    population_ref: str,
    sampling_identity: Mapping[str, Any],
    source_lineage: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the deterministic M1 calibration report from frozen RDP lineage.

    ``source_lineage`` must carry immutable source references and hashes
    (e.g. ``dataset_manifest_ids``, ``dataset_fingerprints``); a moving
    operational store path is rejected fail-closed.
    """

    for key, value in source_lineage.items():
        rendered = json.dumps(value, default=str).casefold()
        for hint in _FORBIDDEN_SQLITE_HINTS:
            _require(hint not in rendered, "MOVING_SQLITE_REJECTED_AS_M1_EVIDENCE")
    panel = rebuild_observation_panel_from_rdp(
        data_root=data_root,
        schedule_sha256=schedule_sha256,
    )
    members = [
        row
        for row in panel.get("members") or []
        if str(row.get("activation_id") or "") == activation_id
    ]
    observations_by_member: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    for row in panel.get("observations") or []:
        if str(row.get("activation_id") or "") != activation_id:
            continue
        member = str(row.get("entity_id") or "")
        observations_by_member.setdefault(member, {})[
            (str(row.get("point_id") or ""), str(row.get("primitive_id") or ""))
        ] = row

    # X eligibility gate: primary M1 denominator requires the member to be a
    # canonical X-eligible member (never X_POPULATION_INELIGIBLE).
    primary_members: list[Mapping[str, Any]] = []
    excluded = []
    for member in members:
        payload = member.get("payload") if isinstance(member.get("payload"), Mapping) else {}
        state = str(member.get("membership_state") or member.get("state") or "")
        x_eligibility = str(payload.get("x_eligibility_state") or "")
        if x_eligibility == "X_ELIGIBLE" or state == "X_ELIGIBLE":
            primary_members.append(member)
        else:
            excluded.append(
                {
                    "entity_id": str(member.get("entity_id") or ""),
                    "state": state or None,
                    "x_eligibility_state": x_eligibility or None,
                }
            )

    outcomes_by_notional: dict[str, list[str]] = {n: [] for n in M1_NOTIONALS}
    transitions: list[str] = []
    frictions: dict[str, list[str]] = {n: [] for n in M1_NOTIONALS}
    covariate_summaries: list[dict[str, Any]] = []
    size_linearity_values: list[str] = []
    paired_members = 0
    for member in primary_members:
        entity_id = str(member.get("entity_id") or "")
        rows = observations_by_member.get(entity_id, {})
        member_evidence: dict[str, dict[str, dict[str, Any] | None]] = {}
        entry_outs: dict[str, str | None] = {}
        for notional in M1_NOTIONALS:
            entry_rows = [
                row
                for (point_id, primitive_id), row in rows.items()
                if primitive_id == NOTIONAL_ENTRY_PRIMITIVE[notional]
            ]
            reverse_rows = [
                row
                for (point_id, primitive_id), row in rows.items()
                if primitive_id == NOTIONAL_REVERSE_PRIMITIVE[notional]
            ]
            entry = entry_rows[-1] if entry_rows else None
            reverse = reverse_rows[-1] if reverse_rows else None
            member_evidence[notional] = {
                "entry": _leg_from_observation(entry),
                "reverse": _leg_from_observation(reverse),
            }
            entry_outs[notional] = (
                str(entry.get("buy_out_amount"))
                if entry is not None and entry.get("buy_out_amount") is not None
                else None
            )
        member_outcomes: dict[str, str] = {}
        for notional in M1_NOTIONALS:
            legs = member_evidence[notional]
            entry_leg = leg_class(
                state=(legs["entry"] or {}).get("state"),
                missing_reason=(legs["entry"] or {}).get("missing_reason"),
            )
            reverse_evidence = legs["reverse"]
            reverse_leg = (
                None
                if reverse_evidence is None
                else leg_class(
                    state=reverse_evidence.get("state"),
                    missing_reason=reverse_evidence.get("missing_reason"),
                )
            )
            member_outcomes[notional] = classify_execution_outcome(entry_leg, reverse_leg)
            outcomes_by_notional[notional].append(member_outcomes[notional])
        transitions.append(
            cross_notional_transition(
                outcome_10=member_outcomes[NOTIONAL_10_USD],
                outcome_100=member_outcomes[NOTIONAL_100_USD],
            )
        )
        if (
            member_outcomes[NOTIONAL_10_USD] == OUTCOME_TWO_WAY
            and member_outcomes[NOTIONAL_100_USD] == OUTCOME_TWO_WAY
        ):
            paired_members += 1
        for notional in M1_NOTIONALS:
            if member_outcomes[notional] != OUTCOME_TWO_WAY:
                continue
            reverse = member_evidence[notional]["reverse"] or {}
            reverse_out = reverse.get("sell_out_amount")
            if isinstance(reverse_out, str) and reverse_out:
                frictions[notional].append(
                    quote_implied_roundtrip_friction(
                        entry_notional_atomic=NOTIONAL_ATOMIC[notional],
                        entry_out_amount=str(
                            member_evidence[notional]["entry"].get("buy_out_amount")
                        ),
                        reverse_out_amount=reverse_out,
                    )
                )
        if (
            entry_outs[NOTIONAL_10_USD]
            and entry_outs[NOTIONAL_100_USD]
        ):
            size_linearity_values.append(
                normalized_entry_size_linearity(
                    entry_out_10=entry_outs[NOTIONAL_10_USD],
                    entry_out_100=entry_outs[NOTIONAL_100_USD],
                )
            )
        # Decision-time covariates from the X search observation.
        search_rows = [
            row
            for (point_id, primitive_id), row in rows.items()
            if primitive_id == "PRIM-JUPITER-TOKENS-V2-SEARCH-001"
        ]
        if search_rows:
            covariate_summaries.append(
                {
                    "entity_id": entity_id,
                    "fields": _covariate_summary(search_rows[-1]),
                }
            )

    counts_by_notional = {
        notional: notional_outcome_counts(outcomes)
        for notional, outcomes in outcomes_by_notional.items()
    }
    for notional, counts in counts_by_notional.items():
        verify_denominatorInvariant(
            population_n=len(primary_members),
            counts=counts,
        )
    friction_summaries = {
        notional: friction_summary(values) if values else None
        for notional, values in frictions.items()
    }
    linearity_summary = (
        {
            "n": len(size_linearity_values),
            "median": _decimal_median(size_linearity_values),
        }
        if size_linearity_values
        else None
    )
    report: dict[str, Any] = {
        "schema": M1_REPORT_SCHEMA,
        "schema_version": M1_REPORT_SCHEMA_VERSION,
        "capability_id": M1_CAPABILITY_ID,
        "rule_version": M1_REPORT_RULE_VERSION,
        "m1_identity": {
            "m1_schema_version": M1_SCHEMA_VERSION,
            "schedule_sha256": schedule_sha256,
            "activation_id": activation_id,
        },
        "source_lineage": {
            "dataset_manifest_ids": list(
                source_lineage.get("dataset_manifest_ids") or []
            ),
            "dataset_fingerprints": list(
                source_lineage.get("dataset_fingerprints") or []
            ),
            "evidence_class": "IMMUTABLE_OBSERVATION_RDP_LINEAGE",
        },
        "availability_cutoff": availability_cutoff.astimezone(UTC).isoformat().replace(
            "+00:00", "Z"
        ),
        "population_ref": population_ref,
        "sampling_identity": dict(sampling_identity),
        "sample_accounting": {
            "primary_members_n": len(primary_members),
            "excluded_members": excluded,
            "paired_two_way_members_n": paired_members,
        },
        "regime_counts": {
            "notional_10_usd": counts_by_notional[NOTIONAL_10_USD],
            "notional_100_usd": counts_by_notional[NOTIONAL_100_USD],
        },
        "friction_summaries": {
            "notional_10_usd": friction_summaries[NOTIONAL_10_USD],
            "notional_100_usd": friction_summaries[NOTIONAL_100_USD],
        },
        "cross_notional_transitions": cross_notional_transition_counts(transitions),
        "decision_time_covariates": {
            "members_with_search_evidence": len(covariate_summaries),
            "summaries": covariate_summaries,
        },
        "execution_diagnostics": {
            "entry_size_linearity": linearity_summary,
            "interpretation": "EXECUTION_DIAGNOSTIC",
        },
        "limitations_non_claims": list(M1_NON_CLAIMS),
        "token_program": "TOKEN_PROGRAM_NOT_CAPTURED",
    }
    report["report_sha256"] = _sha256(_canonical_json_bytes(report))
    return report


__all__ = [
    "M1_REPORT_RULE_VERSION",
    "M1_REPORT_SCHEMA",
    "M1_REPORT_SCHEMA_VERSION",
    "M1CalibrationReportError",
    "build_m1_calibration_report",
]
