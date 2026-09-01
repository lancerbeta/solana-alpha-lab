"""Zero-network campaign schedule proposal + authority packet (no authorize)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.collector_schedulability_oracle import (
    DEFAULT_LIFECYCLE_Y_SECONDS,
    SEARCH_BUNDLE,
    STOP_FREE_TIER_CAPACITY_NOT_PROVEN,
    classify_discovery_coverage,
    evaluate_schedulability,
    select_x_point,
)
from solana_alpha_lab.factory.observation_schedule import (
    render_utc,
    schedule_sha256,
    validate_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule_lifecycle import build_authority_request

CAMPAIGN_DAYS = 21
COHORT_DAYS = 7
SANCTIONED_CREDENTIAL_ENV = "JUPITER_FREE_API_KEY"
CREDENTIAL_ALIAS_ENV = "JUPITER_API_KEY"


def _y_points(offsets: Sequence[int]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for offset in offsets:
        lateness = 120 if offset <= 900 else min(300, max(120, offset // 30))
        points.append(
            {
                "point_id": f"Y{offset}",
                "due_offset_seconds": int(offset),
                "allowed_lateness_seconds": int(lateness),
                "bundle_ids": [SEARCH_BUNDLE],
            }
        )
    return points


def build_campaign_schedule_document(
    *,
    starts_at: datetime,
    schedule_key: str = "OBS-ALWAYS-ON-TOKENS-V2-LIFECYCLE-21D-001",
    max_members_per_utc_day: int = 150,
    max_candidates_per_utc_day: int = 2000,
    inclusion_probability: str = "0.075",
    timing_evidence_seconds: Sequence[int] | None = None,
    seed: str = "ALWAYS-ON-LIFECYCLE-COLLECTOR-V1",
) -> dict[str, Any]:
    """Render the preferred 21d Tokens V2 search-only lifecycle schedule."""

    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=UTC)
    starts_at = starts_at.astimezone(UTC)
    stops_at = starts_at + timedelta(days=CAMPAIGN_DAYS)
    x_seconds, _basis = select_x_point(timing_evidence_seconds=timing_evidence_seconds)
    document: dict[str, Any] = {
        "schema": "smial.observation-schedule",
        "schema_version": "1.0",
        "schedule_key": schedule_key,
        "activation": {
            "starts_at": render_utc(starts_at),
            "stops_admitting_at": render_utc(stops_at),
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
            "seed": seed,
            "inclusion_probability": str(inclusion_probability),
            "max_candidates_per_utc_day": int(max_candidates_per_utc_day),
            "max_members_per_utc_day": int(max_members_per_utc_day),
            "overflow_state": "NOT_SELECTED_CAPACITY",
        },
        "x_point": {
            "point_id": f"X{x_seconds}",
            "due_offset_seconds": int(x_seconds),
            "allowed_lateness_seconds": 300,
            "bundle_ids": [SEARCH_BUNDLE],
        },
        "y_points": _y_points(DEFAULT_LIFECYCLE_Y_SECONDS),
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
            "raw_bytes_per_utc_day_max": 1073741824,
            "canonical_bytes_lifetime_max": 5368709120,
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
    return document


def _apply_oracle_budgets(document: dict[str, Any], oracle: Mapping[str, Any]) -> None:
    day = int(oracle["predicted_provider_calls_per_day"])
    life = int(oracle["predicted_provider_calls_lifetime_21d"])
    # Material headroom: declare caps above predicted load but below pace bound.
    pace_bound = int(oracle["pace_bound_calls_per_day"])
    day_cap = min(pace_bound, max(day + max(1, day // 4), day + 1))
    life_cap = max(life + max(1, life // 4), life + 1)
    document["budgets"]["provider_calls_per_utc_day_max"] = day_cap
    document["budgets"]["provider_calls_lifetime_max"] = life_cap
    document["budgets"]["modeled_provider_credits_per_utc_day_max"] = day_cap
    document["sampling"]["max_members_per_utc_day"] = int(
        oracle["recommended_max_members_per_utc_day"]
    )
    document["sampling"]["inclusion_probability"] = str(
        oracle["recommended_inclusion_probability"]
    )


def run_campaign_preflight(
    *,
    root: Path,
    starts_at: datetime,
    schedule_key: str = "OBS-ALWAYS-ON-TOKENS-V2-LIFECYCLE-21D-001",
    max_members_per_utc_day: int = 150,
    candidate_launches_per_utc_day: int = 2000,
    timing_evidence_seconds: Sequence[int] | None = None,
    empirical_overlap_seconds: int | None = None,
) -> dict[str, Any]:
    """Propose schedule + authority packet; never authorize or activate."""

    draft = build_campaign_schedule_document(
        starts_at=starts_at,
        schedule_key=schedule_key,
        max_members_per_utc_day=max_members_per_utc_day,
        max_candidates_per_utc_day=candidate_launches_per_utc_day,
        timing_evidence_seconds=timing_evidence_seconds,
    )
    probe = deepcopy(draft)
    # Seed budgets high enough for compiler envelope computation during probe.
    probe["budgets"]["provider_calls_per_utc_day_max"] = 100000
    probe["budgets"]["provider_calls_lifetime_max"] = 5000000
    probe["budgets"]["modeled_provider_credits_per_utc_day_max"] = 100000
    oracle = evaluate_schedulability(
        root=root,
        schedule=probe,
        candidate_launches_per_utc_day=candidate_launches_per_utc_day,
        timing_evidence_seconds=timing_evidence_seconds,
    ).as_dict()
    if oracle["terminal"] == STOP_FREE_TIER_CAPACITY_NOT_PROVEN:
        return {
            "terminal": STOP_FREE_TIER_CAPACITY_NOT_PROVEN,
            "authority_status": "PROPOSED_NOT_AUTHORITY",
            "live_authority_granted": False,
            "schedulability": oracle,
            "credential_runtime": {
                "sanctioned_env": SANCTIONED_CREDENTIAL_ENV,
                "compat_alias_env": CREDENTIAL_ALIAS_ENV,
                "operator_instruction": (
                    f"Set {SANCTIONED_CREDENTIAL_ENV} in the sanctioned secrets "
                    f"path only. Optional compat: if unset, runtime may read "
                    f"{CREDENTIAL_ALIAS_ENV}. Never put values in Git/chat/receipt."
                ),
            },
            "discovery_coverage_class": classify_discovery_coverage(
                period_seconds=60,
                empirical_overlap_seconds=empirical_overlap_seconds,
            ),
            "deploy_readiness_blockers": [
                "FREE_TIER_CAPACITY_NOT_PROVEN",
                "AUTHORITY_NOT_GRANTED",
                "VPS_ACTIVATE_OUT_OF_SCOPE_FOR_A2",
            ],
            "network_calls": 0,
            "credential_reads": 0,
        }

    _apply_oracle_budgets(draft, oracle)
    # Re-evaluate on the tightened envelope.
    oracle = evaluate_schedulability(
        root=root,
        schedule=draft,
        candidate_launches_per_utc_day=candidate_launches_per_utc_day,
        timing_evidence_seconds=timing_evidence_seconds,
    ).as_dict()
    validated = validate_observation_schedule(draft, root=root)
    digest = schedule_sha256(validated)
    validated["schedule_sha256"] = digest
    authority = build_authority_request(root=root, document=validated)
    starts = validated["activation"]["starts_at"]
    stops = validated["activation"]["stops_admitting_at"]
    cohort_boundaries = []
    start_dt = datetime.fromisoformat(str(starts).replace("Z", "+00:00"))
    for index in range(3):
        c_start = start_dt + timedelta(days=index * COHORT_DAYS)
        c_end = start_dt + timedelta(days=(index + 1) * COHORT_DAYS)
        cohort_boundaries.append(
            {
                "cohort_id": f"COHORT-{index + 1}",
                "starts_at": render_utc(c_start),
                "ends_at": render_utc(c_end),
            }
        )
    return {
        "terminal": "CAMPAIGN_PREFLIGHT_PROPOSED",
        "authority_status": "PROPOSED_NOT_AUTHORITY",
        "live_authority_granted": False,
        "schedule": validated,
        "schedule_sha256": digest,
        "activation_id": "ACT-PROPOSED-NOT-ACTIVATED",
        "campaign_dates": {"starts_at": starts, "stops_admitting_at": stops},
        "cohort_boundaries": cohort_boundaries,
        "point_offsets": {
            "x": validated["x_point"]["due_offset_seconds"],
            "y": [item["due_offset_seconds"] for item in validated["y_points"]],
        },
        "sampling": dict(validated["sampling"]),
        "provider_caps": dict(validated["budgets"]),
        "schedulability": oracle,
        "authority_request": authority,
        "credential_runtime": {
            "sanctioned_env": SANCTIONED_CREDENTIAL_ENV,
            "compat_alias_env": CREDENTIAL_ALIAS_ENV,
            "operator_instruction": (
                f"Set {SANCTIONED_CREDENTIAL_ENV} in /etc/solana-alpha-lab/secrets.env "
                f"(or the sanctioned process env). Optional compat alias "
                f"{CREDENTIAL_ALIAS_ENV} is read only when the sanctioned name is "
                "unset. Never put values in Git/chat/receipt."
            ),
        },
        "discovery_coverage_class": classify_discovery_coverage(
            period_seconds=int(validated["source_poll"]["period_seconds"]),
            empirical_overlap_seconds=empirical_overlap_seconds,
        ),
        "deploy_readiness_blockers": [
            "AUTHORITY_NOT_GRANTED",
            "VPS_ACTIVATE_OUT_OF_SCOPE_FOR_A2",
            "NO_LIVE_PROVIDER_CALLS_IN_A2",
        ],
        "network_calls": 0,
        "credential_reads": 0,
    }


__all__ = [
    "CAMPAIGN_DAYS",
    "CREDENTIAL_ALIAS_ENV",
    "SANCTIONED_CREDENTIAL_ENV",
    "build_campaign_schedule_document",
    "run_campaign_preflight",
]
