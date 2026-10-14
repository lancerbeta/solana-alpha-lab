"""Managed collection continuity for OPPORTUNITY_EPISODES (I3).

One owner-approved *profile revision* is a standing grant. Inside it the
controller derives short frozen child schedules (one UTC admission day each),
derives their authority from the grant, activates them under the existing
lifecycle owners and keeps committed tails alive. It never edits a frozen
child, never fabricates an owner phrase, never calls a provider and never reads
a credential. Accounting stays in the per-activation counters summed by the
shared-account owner (``observation_account_budget``).

State lives in the OPS store (``managed_*`` tables). Every step is idempotent:
the child intent (exact schedule bytes, window, storage envelope) is persisted
once per ``(lineage, UTC day)`` and a crash is repaired by replaying the
remaining lifecycle steps from that intent.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import shutil
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.collector_read_model import project_activation_as_of
from solana_alpha_lab.factory.hot90_storage_admission import (
    EPISODE_STORAGE_KIND_V2_MANAGED,
    HARD_BYTES,
    HORIZON_DAYS,
    TARGET_BYTES,
    episode_drain_reserve,
    producer_root_identity,
)
from solana_alpha_lab.factory.observation_account_budget import account_budget_status
from solana_alpha_lab.factory.observation_schedule import (
    canonical_sha256,
    parse_utc,
    render_utc,
    validate_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule_lifecycle import (
    ObservationLifecycleError,
    _activation_is_non_admitting,
    _cohort_family_key,
    _non_admitting_recovery_at,
    _used_provider_route_ids,
    activate_schedule,
    activation_transition_research_event_proven,
    authorize_schedule_from_standing_grant,
    ensure_authority_event,
    register_schedule,
    stop_episode_intake,
)
from solana_alpha_lab.factory.observation_schedule_store import (
    ObservationScheduleStore,
    ObservationScheduleStoreError,
)
from solana_alpha_lab.factory.opportunity_episodes import (
    ROUNDS_PER_DAY,
    collection_lineage_id,
    episode_cohort_family_key,
    episode_point_ids,
    is_episode_schedule,
    round_quota,
)

PROFILE_KIND = "smial.managed-collection-profile"
PROFILE_VERSION = "1.0"
ADAPTER = "MANAGED_EPISODE_ADAPTER_V1"
V1_ADMISSION_CEILING = 100  # the frozen V1 episode validator ceiling, not a managed policy
VALIDITY_MODES = ("UNTIL_REVOKED", "UNTIL_DATE")
DEFAULT_BACKUP_SOURCE = "OFFHOST_VERIFIED"
DEFAULT_BACKUP_MAX_AGE_SECONDS = 30 * 3600
# Re-evaluating a blocked resource decision walks the data root; do it at most this often.
BLOCKED_RECHECK_SECONDS = 300
INTAKE_MISSING_GRACE_SECONDS = 600

_DAY = timedelta(days=1)
_CHILD_NON_TERMINAL = ("PLANNED", "REGISTERED", "AUTHORIZED_DERIVED")
_CHILD_TERMINAL = frozenset({"TAIL_COMPLETE", "CANCELLED", "EXPIRED_BEFORE_ACTIVATION", "ABORTED", "SUPERSEDED"})
_ACTIVATION_TO_CHILD_STATE = {
    "ACTIVE": "ACTIVATED",
    "DRAINING": "INTAKE_COMPLETE",
    "COMPLETE": "TAIL_COMPLETE",
    "PAUSED_OPERATOR": "PAUSED",
    "ABORTED_SAFETY": "ABORTED",
}


class ManagedCollectionError(ValueError):
    """Typed refusal; the message is a canonical terminal."""


def _hex64(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _day_start(moment: datetime) -> datetime:
    moment = moment.astimezone(UTC)
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


def _floor_seconds(moment: datetime) -> datetime:
    return moment.astimezone(UTC).replace(microsecond=0)


def derived_authority_basis_text(grant_sha256: str, envelope_phrase: str) -> str:
    """Text whose hash is the child's ``phrase_sha256``. It is not an owner phrase."""

    return f"DERIVED FROM STANDING GRANT {grant_sha256} CHILD ENVELOPE {envelope_phrase}"


# --------------------------------------------------------------------------
# Profile / grant


def grant_phrase(body: Mapping[str, Any]) -> str:
    """The one exact owner phrase approving this profile revision."""

    validity = body["validity"]
    limits = body["limits"]
    until = f" UNTIL {validity['intake_until']}" if validity["mode"] == "UNTIL_DATE" else ""
    return (
        "AUTHORIZE MANAGED COLLECTION "
        f"{str(body['collection_lineage_id'])[:16]} REVISION {int(body['revision'])} "
        f"PROFILE {canonical_sha256(body)} "
        f"VALIDITY {validity['mode']}{until} "
        f"ADMISSIONS {limits['admissions_per_utc_day']}/DAY ROLLING {limits['rolling_24h_admissions']} "
        f"ACTIVE {limits['active_episode_cap']} ACCOUNT {limits['shared_account_scope']} "
        f"CALLS {limits['provider_calls_per_utc_day']}/{limits['modeled_credits_per_utc_day']}/"
        f"{limits['cumulative_calls']} CASH 0 RETRY NO FALLBACK NO"
    )


def _limits_from(template: Mapping[str, Any], overrides: Mapping[str, Any], scope: str) -> dict[str, Any]:
    sampling = template["sampling"]
    budgets = template["budgets"]
    limits = {
        "admissions_per_utc_day": overrides.get("admissions_per_utc_day") or int(sampling["daily_normal_ceiling"]),
        "rolling_24h_admissions": overrides.get("rolling_24h_admissions")
        or overrides.get("admissions_per_utc_day")
        or int(sampling["rolling_24h_max"]),
        "active_episode_cap": overrides.get("active_episode_cap") or int(sampling["active_episode_cap"]),
        "shared_account_scope": scope,
        "provider_calls_per_utc_day": overrides.get("provider_calls_per_utc_day")
        or int(budgets["provider_calls_per_utc_day_max"]),
        "modeled_credits_per_utc_day": overrides.get("modeled_credits_per_utc_day")
        or int(budgets["modeled_provider_credits_per_utc_day_max"]),
        "cumulative_calls": overrides.get("cumulative_calls") or int(budgets["provider_calls_lifetime_max"]),
        "cash_usd_max": "0",
    }
    return limits


def build_profile(
    *,
    root: Path,
    template_document: Mapping[str, Any],
    revision: int,
    previous_revision: int | None,
    limits: Mapping[str, Any],
    account_scope_id: str,
    validity_mode: str = "UNTIL_REVOKED",
    intake_until: str | None = None,
    planning_horizon_days: int = 180,
    bootstrap_not_before: str | None = None,
    protected_bridge: Mapping[str, Any] | None = None,
    storage_basis: Mapping[str, Any],
    backup_source: str = DEFAULT_BACKUP_SOURCE,
    backup_max_age_seconds: int = DEFAULT_BACKUP_MAX_AGE_SECONDS,
    target_bytes: int = TARGET_BYTES,
    hard_bytes: int = HARD_BYTES,
    target_acceptance: Mapping[str, Any] | None = None,
    measured_growth_bytes_per_day: int | None = None,
) -> dict[str, Any]:
    """Build one profile revision body. Deterministic: no clock, no randomness."""

    if not is_episode_schedule(template_document):
        raise ManagedCollectionError("MANAGED_TEMPLATE_NOT_EPISODE_SCHEDULE")
    template = copy.deepcopy(dict(template_document))
    template.pop("schedule_sha256", None)
    template.pop("activation", None)
    resolved = _limits_from(template, limits, account_scope_id)
    template["sampling"]["daily_normal_ceiling"] = resolved["admissions_per_utc_day"]
    template["sampling"]["rolling_24h_max"] = resolved["rolling_24h_admissions"]
    template["sampling"]["active_episode_cap"] = resolved["active_episode_cap"]
    template["budgets"]["provider_calls_per_utc_day_max"] = resolved["provider_calls_per_utc_day"]
    template["budgets"]["modeled_provider_credits_per_utc_day_max"] = resolved["modeled_credits_per_utc_day"]
    template["budgets"]["provider_calls_lifetime_max"] = resolved["cumulative_calls"]
    probe = copy.deepcopy(template)
    probe["activation"] = {"starts_at": "2099-01-01T00:00:00Z", "stops_admitting_at": "2099-01-02T00:00:00Z"}
    probe = validate_observation_schedule(probe, root=root)
    _primitives, routes = _used_provider_route_ids(root, probe)
    body: dict[str, Any] = {
        "kind": PROFILE_KIND,
        "version": PROFILE_VERSION,
        "revision": int(revision),
        "previous_revision": previous_revision,
        "collection_lineage_id": collection_lineage_id(template),
        "desired_state": "RUN",
        "validity": {
            "mode": validity_mode,
            "intake_until": intake_until if validity_mode == "UNTIL_DATE" else None,
            "planning_horizon_days": int(planning_horizon_days),
        },
        "semantics": {
            "cohort_family_key": episode_cohort_family_key(template),
            "adapter": ADAPTER,
            "template_schedule_key": str(template["schedule_key"]),
        },
        "provider_route_ids": sorted(routes),
        "limits": resolved,
        "template": template,
        "resource_policy": {
            "target_bytes": int(target_bytes),
            "hard_bytes": int(hard_bytes),
            "backup_source": backup_source,
            "backup_max_age_seconds": int(backup_max_age_seconds),
            "storage_basis": dict(storage_basis),
            "target_acceptance": dict(target_acceptance) if target_acceptance else None,
            "measured_growth_bytes_per_day": measured_growth_bytes_per_day,
        },
        "continuation": {
            "automatic": True,
            "child_boundary": "UTC_ADMISSION_DAY",
            "bootstrap_not_before": bootstrap_not_before,
            "protected_bridge": dict(protected_bridge) if protected_bridge else None,
        },
        "recovery": {
            "resume_after_temporary_hold": "SAME_SEMANTICS_ONLY",
            "resource_profile_rollback": "LAST_APPROVED_SAFE_REVISION",
        },
        "notifications": {"incidents_and_recovery": True},
    }
    validate_profile(body)
    return body


_PROFILE_KEYS = {
    "kind", "version", "revision", "previous_revision", "collection_lineage_id", "desired_state",
    "validity", "semantics", "provider_route_ids", "limits", "template", "resource_policy",
    "continuation", "recovery", "notifications",
}
_STORAGE_BASIS_KEYS = {
    "copy_rehearsal_sha256", "factory_storage_receipt_sha256", "volume_bindings_sha256",
    "search_call_local_bytes_max", "nomination_call_local_bytes_max", "slot_metadata_local_bytes_max",
    "fixed_local_reserve_bytes", "local_safety_bytes", "source_ref",
}


def validate_profile(body: Mapping[str, Any]) -> None:
    if not isinstance(body, Mapping) or set(body) != _PROFILE_KEYS:
        raise ManagedCollectionError("MANAGED_PROFILE_SHAPE_INVALID")
    if body["kind"] != PROFILE_KIND or body["version"] != PROFILE_VERSION or body["desired_state"] != "RUN":
        raise ManagedCollectionError("MANAGED_PROFILE_SHAPE_INVALID")
    revision = body["revision"]
    previous = body["previous_revision"]
    if type(revision) is not int or revision < 1 or previous != (revision - 1 or None):
        raise ManagedCollectionError("MANAGED_PROFILE_REVISION_INVALID")
    validity = body["validity"]
    if validity.get("mode") not in VALIDITY_MODES:
        raise ManagedCollectionError("MANAGED_VALIDITY_INVALID")
    if validity["mode"] == "UNTIL_DATE":
        try:
            parse_utc(str(validity.get("intake_until")))
        except Exception as exc:
            raise ManagedCollectionError("MANAGED_VALIDITY_INVALID") from exc
    elif validity.get("intake_until") is not None:
        raise ManagedCollectionError("MANAGED_VALIDITY_INVALID")
    limits = body["limits"]
    for key in (
        "admissions_per_utc_day", "rolling_24h_admissions", "active_episode_cap",
        "provider_calls_per_utc_day", "modeled_credits_per_utc_day", "cumulative_calls",
    ):
        if type(limits.get(key)) is not int or limits[key] <= 0:
            raise ManagedCollectionError("MANAGED_LIMIT_INVALID")
    if limits["rolling_24h_admissions"] > limits["admissions_per_utc_day"] or limits["cash_usd_max"] != "0":
        raise ManagedCollectionError("MANAGED_LIMIT_INVALID")
    if limits["admissions_per_utc_day"] > V1_ADMISSION_CEILING:
        # The V1 episode validator is frozen. A larger rate needs a measured managed adapter
        # and is refused here with the numeric reason, never silently clipped.
        raise ManagedCollectionError("MANAGED_ADAPTER_V1_ADMISSION_CEILING")
    if set(body["resource_policy"]["storage_basis"]) != _STORAGE_BASIS_KEYS:
        raise ManagedCollectionError("MANAGED_STORAGE_BASIS_INVALID")
    for key in ("copy_rehearsal_sha256", "factory_storage_receipt_sha256", "volume_bindings_sha256"):
        if not _hex64(body["resource_policy"]["storage_basis"][key]):
            raise ManagedCollectionError("MANAGED_STORAGE_BASIS_INVALID")
    policy = body["resource_policy"]
    if not 0 < policy["target_bytes"] <= policy["hard_bytes"] or policy.get("backup_source") not in _BACKUP_SOURCES:
        raise ManagedCollectionError("MANAGED_RESOURCE_POLICY_INVALID")
    if body["continuation"].get("bootstrap_not_before") is not None:
        parse_utc(str(body["continuation"]["bootstrap_not_before"]))


def _approval_valid(store: ObservationScheduleStore, lineage: str, row: Mapping[str, Any]) -> bool:
    """A revision is owner-approved by its exact phrase, or by rollback to an approved one."""

    payload = row["payload"]
    body = payload["profile"]
    approval = payload["approval"]
    if canonical_sha256(body) != str(row["profile_sha256"]):
        return False
    if approval.get("kind") == "OWNER_PHRASE":
        return str(approval.get("phrase_sha256")) == hashlib.sha256(
            grant_phrase(body).encode("utf-8")
        ).hexdigest()
    if approval.get("kind") == "ROLLBACK_TO_APPROVED":
        target = store.managed_profile(lineage, int(approval["rollback_to_revision"]))
        if target is None or target["payload"]["approval"].get("kind") != "OWNER_PHRASE":
            return False
        if not _approval_valid(store, lineage, target):
            return False
        strip = lambda item: {k: v for k, v in item.items() if k not in {"revision", "previous_revision"}}  # noqa: E731
        previous = store.managed_profile(lineage, int(body["previous_revision"]))
        return (
            previous is not None
            and strip(body) == strip(target["payload"]["profile"])
            and _not_wider(body, previous["payload"]["profile"])
        )
    return False


def _not_wider(new: Mapping[str, Any], old: Mapping[str, Any]) -> bool:
    """True when ``new`` grants nothing ``old`` did not: limits, validity, routes, resources, scope."""

    if not _restrictive(new["limits"], old["limits"]) or new["limits"]["shared_account_scope"] != old["limits"]["shared_account_scope"]:
        return False
    nv, ov = new["validity"], old["validity"]
    if ov["mode"] == "UNTIL_DATE" and (
        nv["mode"] != "UNTIL_DATE" or parse_utc(str(nv["intake_until"])) > parse_utc(str(ov["intake_until"]))
    ):
        return False
    if not set(new["provider_route_ids"]).issubset(set(old["provider_route_ids"])):
        return False
    np_, op_ = new["resource_policy"], old["resource_policy"]
    if np_["hard_bytes"] > op_["hard_bytes"] or np_["target_bytes"] > op_["target_bytes"] or np_[
        "backup_max_age_seconds"
    ] > op_["backup_max_age_seconds"]:
        return False
    oa, na = op_.get("target_acceptance"), np_.get("target_acceptance")
    if na and (not oa or int(na.get("max_projected_bytes", 0)) > int(oa.get("max_projected_bytes", 0))):
        return False
    if new["semantics"] != old["semantics"] or new["recovery"] != old["recovery"] or new["notifications"] != old["notifications"]:
        return False
    # Protection, exclusions, grid, filters, outputs and authority profile may not change; only the
    # numeric limits already compared above may differ inside the frozen template.
    if _template_core(new["template"]) != _template_core(old["template"]):
        return False
    nc, oc = new["continuation"], old["continuation"]
    if nc.get("protected_bridge") != oc.get("protected_bridge") or nc.get("automatic") != oc.get("automatic"):
        return False
    new_start, old_start = nc.get("bootstrap_not_before"), oc.get("bootstrap_not_before")
    if old_start is not None and (new_start is None or parse_utc(str(new_start)) < parse_utc(str(old_start))):
        return False  # an earlier handover could compete with a bridge the owner protected
    return True


def _template_core(template: Mapping[str, Any]) -> dict[str, Any]:
    core = copy.deepcopy(dict(template))
    for key in ("daily_normal_ceiling", "rolling_24h_max", "active_episode_cap"):
        core["sampling"].pop(key, None)
    for key in ("provider_calls_per_utc_day_max", "modeled_provider_credits_per_utc_day_max",
                "provider_calls_lifetime_max"):
        core["budgets"].pop(key, None)
    return core


def _restrictive(new: Mapping[str, Any], old: Mapping[str, Any]) -> bool:
    return all(
        int(new[key]) <= int(old[key])
        for key in (
            "admissions_per_utc_day", "rolling_24h_admissions", "active_episode_cap",
            "provider_calls_per_utc_day", "modeled_credits_per_utc_day", "cumulative_calls",
        )
    )


def verified_profile(store: ObservationScheduleStore, lineage: str, revision: int) -> dict[str, Any]:
    row = store.managed_profile(lineage, revision)
    if row is None:
        raise ManagedCollectionError("MANAGED_GRANT_MISSING")
    try:
        validate_profile(row["payload"]["profile"])
    except ManagedCollectionError as exc:
        raise ManagedCollectionError("MANAGED_GRANT_TAMPERED") from exc
    if not _approval_valid(store, lineage, row):
        raise ManagedCollectionError("MANAGED_GRANT_TAMPERED")
    return row["payload"]["profile"]


def require_child_within_standing_grant(
    store: ObservationScheduleStore,
    *,
    receipt: Mapping[str, Any],
    document: Mapping[str, Any],
    routes: list[str],
    issuing_at: datetime | None = None,
) -> None:
    """Child authority must be a subset of the approved parent grant.

    ``issuing_at`` adds the issue-time gates (current revision, not revoked,
    inside validity). At tick time only the immutable fit is required, so a
    revoked or ended grant never kills an already issued, committed tail.
    """

    if (
        receipt.get("authority_basis") != "STANDING_GRANT"
        or not _hex64(receipt.get("standing_grant_sha256"))
        or type(receipt.get("standing_grant_revision")) is not int
    ):
        raise ManagedCollectionError("MANAGED_GRANT_MISSING")
    if not is_episode_schedule(document):
        raise ManagedCollectionError("MANAGED_CHILD_SEMANTICS_MISMATCH")
    lineage = collection_lineage_id(document)
    revision = int(receipt["standing_grant_revision"])
    body = verified_profile(store, lineage, revision)
    if canonical_sha256(body) != str(receipt["standing_grant_sha256"]):
        raise ManagedCollectionError("MANAGED_GRANT_TAMPERED")
    if (
        episode_cohort_family_key(document) != body["semantics"]["cohort_family_key"]
        or str(document["schedule_key"]) != body["semantics"]["template_schedule_key"]
    ):
        raise ManagedCollectionError("MANAGED_CHILD_SEMANTICS_MISMATCH")
    if not set(routes).issubset(set(body["provider_route_ids"])):
        raise ManagedCollectionError("MANAGED_CHILD_EXCEEDS_GRANT")
    limits = body["limits"]
    sampling = document["sampling"]
    budgets = document["budgets"]
    if (
        int(sampling["daily_normal_ceiling"]) > limits["admissions_per_utc_day"]
        or int(sampling["rolling_24h_max"]) > limits["rolling_24h_admissions"]
        or int(sampling["active_episode_cap"]) > limits["active_episode_cap"]
        or int(budgets["provider_calls_per_utc_day_max"]) > limits["provider_calls_per_utc_day"]
        or int(budgets["modeled_provider_credits_per_utc_day_max"]) > limits["modeled_credits_per_utc_day"]
        or int(budgets["provider_calls_lifetime_max"]) > limits["cumulative_calls"]
        or str(budgets["cash_usd_max"]) != "0"
    ):
        raise ManagedCollectionError("MANAGED_CHILD_EXCEEDS_GRANT")
    starts = parse_utc(str(document["activation"]["starts_at"]))
    stops = parse_utc(str(document["activation"]["stops_admitting_at"]))
    if body["validity"]["mode"] == "UNTIL_DATE" and stops > parse_utc(str(body["validity"]["intake_until"])):
        raise ManagedCollectionError("MANAGED_CHILD_EXCEEDS_GRANT")
    # Everything the owner approved is the frozen template: protection, exclusions, grid,
    # filters, outputs and authority profile may not differ in a derived child.
    if {key: value for key, value in document.items() if key not in {"activation", "schedule_sha256"}} != body["template"]:
        raise ManagedCollectionError("MANAGED_CHILD_SEMANTICS_MISMATCH")
    if issuing_at is None:
        return
    control = store.managed_control(lineage)
    if control is None or int(control["current_revision"]) != revision:
        raise ManagedCollectionError("MANAGED_GRANT_SUPERSEDED")
    if str(control["desired_state"]) != "RUN" or control.get("intake_revoked_at"):
        raise ManagedCollectionError("MANAGED_GRANT_REVOKED")
    if body["validity"]["mode"] == "UNTIL_DATE" and starts >= parse_utc(str(body["validity"]["intake_until"])):
        raise ManagedCollectionError("MANAGED_GRANT_EXPIRED")


# --------------------------------------------------------------------------
# Capacity geometry (numbers a plan must show before an owner approves)


def capacity_geometry(template: Mapping[str, Any], limits: Mapping[str, Any]) -> dict[str, Any]:
    """Lower-bound workload geometry for an admission rate. Refuses with named axes."""

    admissions = int(limits["admissions_per_utc_day"])
    nomination = template["nomination"]
    schedule = template["observation_schedule"]
    period = int(nomination["round_period_seconds"])
    nomination_calls = (86400 // period) * len(nomination["sources"])
    post_t0_points = len(episode_point_ids()) - 1
    batch = int(schedule["max_batch_size"])
    horizon_days = math.ceil(int(schedule["horizon_seconds"]) / 86400)
    points_per_day = post_t0_points * admissions
    batches_lower_bound = math.ceil(points_per_day / batch)
    calls_lower_bound = nomination_calls + batches_lower_bound
    active_episodes = horizon_days * admissions
    dense_per_slot = (int(schedule["dense_until_seconds"]) // int(schedule["dense_step_seconds"])) * (
        admissions * int(schedule["dense_step_seconds"]) / 86400
    )
    hourly_points = int(schedule["horizon_seconds"]) // int(schedule["hourly_step_seconds"]) - (
        int(schedule["dense_until_seconds"]) // int(schedule["hourly_step_seconds"])
    )
    hourly_per_hour = hourly_points * admissions / 24
    worst_slot_points = dense_per_slot + hourly_per_hour
    scopes = horizon_days + 1  # intake child plus the draining tails, none of which can share a send
    sends_worst_slot = scopes * math.ceil(worst_slot_points / scopes / batch)
    pace = int(template["budgets"]["min_provider_pace_seconds"])
    window = int(schedule["dispatch_window_seconds"])
    pace_span = max(0, sends_worst_slot - 1) * pace
    refusals: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if admissions > V1_ADMISSION_CEILING:
        refusals.append({"axis": "MANAGED_ADAPTER_V1_ADMISSION_CEILING", "limit": V1_ADMISSION_CEILING,
                         "requested": admissions})
    if calls_lower_bound > int(limits["provider_calls_per_utc_day"]):
        refusals.append({"axis": "PROVIDER_CALLS_PER_UTC_DAY", "limit": int(limits["provider_calls_per_utc_day"]),
                         "lower_bound": calls_lower_bound})
    if calls_lower_bound > int(limits["modeled_credits_per_utc_day"]):
        refusals.append({"axis": "MODELED_CREDITS_PER_UTC_DAY", "limit": int(limits["modeled_credits_per_utc_day"]),
                         "lower_bound": calls_lower_bound})
    if pace_span > window:
        refusals.append({"axis": "PACE_DISPATCH_WINDOW", "dispatch_window_seconds": window,
                         "required_seconds": pace_span, "sends_worst_slot": sends_worst_slot, "pace_seconds": pace})
    if active_episodes > int(limits["active_episode_cap"]):
        warnings.append({"axis": "ACTIVE_EPISODE_CAP", "cap": int(limits["active_episode_cap"]),
                         "steady_state_active": active_episodes, "effect": "ADMISSION_PAUSES_AT_CAP"})
    return {
        "verdict": "REFUSED" if refusals else "FEASIBLE_LOWER_BOUND",
        "basis": "LOWER_BOUND_NOT_A_MEASURED_PRODUCTION_FORECAST",
        "admissions_per_utc_day": admissions,
        "steady_state_active_episodes": active_episodes,
        "post_t0_points_per_day": points_per_day,
        "nomination_calls_per_day": nomination_calls,
        "provider_calls_per_day_lower_bound": calls_lower_bound,
        "worst_slot_points": round(worst_slot_points, 1),
        "worst_slot_sends": sends_worst_slot,
        "worst_slot_pace_span_seconds": pace_span,
        "lifetime_runway_days_at_lower_bound": int(limits["cumulative_calls"]) // max(1, calls_lower_bound),
        "refusals": refusals,
        "warnings": warnings,
    }


# --------------------------------------------------------------------------
# Resource decision (storage / backup / physical tail), no PASS forgery


_UNKNOWN = "UNKNOWN"
_BACKUP_SOURCES = ("OFFHOST_VERIFIED", "LOCAL_BUNDLE")


def _file_bytes(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def measure_whole_factory(
    *, store: ObservationScheduleStore, data_root: Path, root: Path, environ: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """Non-overlapping resident and transient bytes of the whole same-volume factory.

    Reuses the collector packet's own measurements (RDP inventory with open publication
    jobs as transient staging, OPS SQLite plus WAL, the existing backup sink). An OPS store
    nested inside the RDP is counted once. Any unreadable part is UNKNOWN and fails closed.
    """

    from solana_alpha_lab.factory.collector_operational_packet import (
        _rdp_inventory_bytes,
        _tree_bytes,
        resident_rdp_bytes,
    )
    from solana_alpha_lab.factory.remote_ops import load_config, resolve_backup_sink

    sqlite_path = Path(store.path)
    sqlite_bytes = _file_bytes(sqlite_path) + _file_bytes(Path(str(sqlite_path) + "-wal"))
    total, _open_count, open_bytes, _science = _rdp_inventory_bytes(Path(data_root))
    resident = resident_rdp_bytes(total, open_bytes)
    nested = False
    try:
        nested = Path(data_root).resolve() in sqlite_path.resolve().parents
    except OSError:
        nested = False
    if isinstance(resident, int) and nested:
        resident = max(0, resident - sqlite_bytes)
    sink_bytes: Any = _UNKNOWN
    try:
        sink = resolve_backup_sink(Path(root), load_config(Path(root)), environ if environ is not None else os.environ)
        measured = _tree_bytes(sink)
        sink_bytes = 0 if measured is None else int(measured)
    except Exception:  # noqa: BLE001 - an unresolvable sink is UNKNOWN, never zero
        sink_bytes = _UNKNOWN
    return {
        "sqlite_bytes": sqlite_bytes,
        "resident_rdp_bytes": resident if isinstance(resident, int) else _UNKNOWN,
        "backup_sink_bytes": sink_bytes,
        "staging_bytes": int(open_bytes) if isinstance(open_bytes, int) else _UNKNOWN,
        "ops_nested_in_rdp": nested,
    }


def read_verified_backup(
    *, root: Path, policy: Mapping[str, Any], now: datetime, environ: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """Backup health from the existing backup owners only; nothing here is attested by hand.

    ``OFFHOST_VERIFIED``: the off-host receipt owner reports state CURRENT with a verified
    checkpoint. ``LOCAL_BUNDLE``: the newest published BACKUP bundle of the independent sink.
    """

    from solana_alpha_lab.factory.offhost_backup import offhost_health_snapshot
    from solana_alpha_lab.factory.remote_ops import _backup_newest, load_config, resolve_backup_sink

    source = str(policy.get("backup_source") or "")
    max_age = int(policy["backup_max_age_seconds"])
    if source not in _BACKUP_SOURCES:
        return {"state": "INVALID", "source": source}
    try:
        if source == "OFFHOST_VERIFIED":
            snapshot = offhost_health_snapshot(Path(root), now=now)
            if not snapshot.get("configured"):
                return {"state": "UNCONFIGURED", "source": source}
            checkpoint = snapshot.get("offhost_last_verified_at")
            artifact = snapshot.get("offhost_last_sha256")
            owner_state = str(snapshot.get("offhost_backup_state") or "")
            coverage = "OFFHOST_VERIFIED_CHECKPOINT"
        else:
            sink = resolve_backup_sink(Path(root), load_config(Path(root)), environ if environ is not None else os.environ)
            newest = _backup_newest(sink)
            if newest is None:
                return {"state": "MISSING", "source": source}
            checkpoint = newest.get("mtime")
            artifact = newest.get("sha256")
            owner_state = "CURRENT"
            coverage = "LOCAL_PUBLISHED_BUNDLE"
        if not checkpoint:
            return {"state": "MISSING", "source": source}
        age = (now - parse_utc(str(checkpoint))).total_seconds()
    except Exception:  # noqa: BLE001 - unreadable owner output never counts as fresh
        return {"state": "INVALID", "source": source}
    if not _hex64(artifact):
        return {"state": "INVALID", "source": source}
    if owner_state != "CURRENT":
        state = "OWNER_" + (owner_state or "UNKNOWN")
    else:
        state = "FRESH" if 0 <= age <= max_age else "STALE"
    return {
        "state": state, "source": source, "age_seconds": int(age), "max_age_seconds": max_age,
        "artifact_sha256": artifact, "checkpoint_at": render_utc(parse_utc(str(checkpoint))), "coverage": coverage,
    }


def _pending_obligations(store: ObservationScheduleStore, batch: int) -> dict[str, int]:
    slots = groups = 0
    for row in store.list_activations():
        if str(row["state"]) in {"ACTIVE", "DRAINING"}:
            part = store.episode_remaining_call_groups(
                schedule_sha256=str(row["schedule_sha256"]), activation_id=str(row["activation_id"]),
                batch_size=batch)
            slots += part["remaining_slots"]
            groups += part["remaining_call_groups"]
    return {"remaining_slots": slots, "remaining_call_groups": groups}


_MEASURE = object()


def managed_storage_decision(
    *,
    store: ObservationScheduleStore,
    body: Mapping[str, Any],
    data_root: Path,
    root: Path,
    now: datetime,
    free_bytes: Any = _MEASURE,
    footprint: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Physical + owner-policy decision for starting a new intake child.

    Three independent checks, never merged: (1) physical free-space reserve for the committed
    tail and next round, (2) projected whole-factory peak against HARD and TARGET (resident
    OPS/RDP/backup plus transient staging plus the prospective write peak), (3) verified
    backup freshness. Semantics/authority are never decided here. A block stops new intake
    only; committed tails keep running.
    """

    policy = body["resource_policy"]
    basis = policy["storage_basis"]
    template = body["template"]
    batch = int(template["observation_schedule"]["max_batch_size"])
    if free_bytes is _MEASURE:
        try:
            free_bytes = shutil.disk_usage(data_root).free
        except OSError:
            free_bytes = None
    measured = dict(footprint) if footprint is not None else measure_whole_factory(
        store=store, data_root=data_root, root=root, environ=environ)
    admissions = int(body["limits"]["admissions_per_utc_day"])
    # Same unit as the tick's own gate: one round's quota, re-evaluated every round.
    prospective = max(round_quota(admissions, index) for index in range(ROUNDS_PER_DAY)) * (
        len(episode_point_ids()) - 1
    )
    nomination_calls = (86400 // int(template["nomination"]["round_period_seconds"])) * len(
        template["nomination"]["sources"]
    )
    local = {key: basis[key] for key in _STORAGE_BASIS_KEYS if key.endswith("_bytes_max") or key.endswith("_bytes")}
    local["envelope_sha256"] = canonical_sha256(basis)
    reserve = episode_drain_reserve(
        **_pending_obligations(store, batch), prospective_slots=prospective,
        prospective_call_groups=prospective, remaining_nomination_calls=nomination_calls,
        local_envelope=local, free_bytes=free_bytes)
    backup = read_verified_backup(root=root, policy=policy, now=now, environ=environ)
    reasons: list[str] = []
    hard = int(policy["hard_bytes"])
    target = int(policy["target_bytes"])
    required = int(reserve["required_free_bytes"])
    parts = [measured.get(key) for key in ("sqlite_bytes", "resident_rdp_bytes", "backup_sink_bytes", "staging_bytes")]
    known = all(isinstance(item, int) for item in parts)
    growth = policy.get("measured_growth_bytes_per_day")
    horizon_bytes = int(growth) * HORIZON_DAYS if growth else 0
    prospective_peak = (
        int(reserve["committed_drain_reserve_bytes"]) + int(reserve["prospective_reserve_bytes"])
        + int(reserve["future_nomination_reserve_bytes"])
    )
    resident_total = sum(parts) - (parts[3] if known else 0) if known else None
    projected = (sum(parts) + horizon_bytes + prospective_peak) if known else None
    if not known:
        reasons.append("FOOTPRINT_UNKNOWN")
    elif projected >= hard:
        reasons.append("HARD_BYTES")
    if reserve["status"] != "LOCAL_HEADROOM":
        reasons.append("PHYSICAL_TAIL_RESERVE")
    if backup["state"] != "FRESH":
        reasons.append("BACKUP_" + backup["state"])
    acceptance = policy.get("target_acceptance")
    health = "OK"
    if known and projected >= target:
        accepted = (
            isinstance(acceptance, Mapping)
            and _hex64(acceptance.get("acceptance_sha256"))
            and projected <= min(int(acceptance.get("max_projected_bytes", 0)), hard - 1)
        )
        if accepted:
            health = "DEGRADED_TARGET"
        else:
            reasons.append("TARGET_EXCEEDED_UNACCEPTED")
    # Optional intake must never spend the budget that committed tails still need.
    account = account_budget_status(store, now=now)
    budget_state = "UNMANAGED"
    if account.get("mode") == "MANAGED":
        pending = _pending_obligations(store, batch)["remaining_call_groups"]
        needed = pending + capacity_geometry(template, body["limits"])["provider_calls_per_day_lower_bound"]
        remaining = account["remaining"]
        budget_state = "TAIL_COVERED"
        if remaining["lifetime_provider_calls"] < needed or remaining["day_provider_calls"] <= 0:
            reasons.append("BUDGET_TAIL_RISK")
            budget_state = "TAIL_AT_RISK"
    allowed = not reasons
    grant_sha = canonical_sha256(body)
    runway = _runway(policy, resident_total, int(body["validity"]["planning_horizon_days"]))
    return {
        "decision": ("ALLOW" if health == "OK" else "ALLOW_WITH_ACCEPTED_TARGET_RISK") if allowed else "BLOCK",
        "storage_health": health if allowed else "BLOCKED",
        "hard_constraints": "FAIL" if ("HARD_BYTES" in reasons or "FOOTPRINT_UNKNOWN" in reasons) else "PASS",
        "physical_tail_reserve": "FAIL" if "PHYSICAL_TAIL_RESERVE" in reasons else "PASS",
        "target_acceptance": dict(acceptance) if allowed and health == "DEGRADED_TARGET" else None,
        "grant_sha256": grant_sha,
        "reasons": reasons,
        "footprint": {**measured, "resident_total_bytes": resident_total, "incremental_horizon_bytes": horizon_bytes,
                      "prospective_peak_bytes": prospective_peak, "projected_peak_bytes": projected},
        "factory_bytes": resident_total,
        "projected_peak_bytes": projected,
        "free_bytes": free_bytes,
        "required_free_bytes": required,
        "target_bytes": target,
        "hard_bytes": hard,
        "backup": backup,
        "budget_tail": budget_state,
        "runway": runway,
        "decided_at": render_utc(now),
    }


def _runway(policy: Mapping[str, Any], resident_bytes: int | None, horizon_days: int) -> dict[str, Any]:
    growth = policy.get("measured_growth_bytes_per_day")
    hard = int(policy["hard_bytes"])
    out: dict[str, Any] = {
        "planning_horizon_days": horizon_days,
        "resident_hot_bytes": resident_bytes,
        "new_useful_bytes_per_day": growth,
        "upload_bytes_per_day": None,
        "remote_retained_bytes": None,
        "peak_transient_bytes": None,
        "expected_i2_savings_applied_bytes": 0,
    }
    if not growth or resident_bytes is None:
        out.update({"days_to_hard": None, "status": "UNKNOWN_GROWTH_NOT_MEASURED",
                    "i2_action": "MEASURE_NEW_BYTES_PER_DAY_AND_APPLY_I2_PACKAGING"})
        return out
    days = max(0, (hard - resident_bytes)) // int(growth)
    out.update({"days_to_hard": days, "status": "COVERS_HORIZON" if days >= horizon_days else "SHORT_OF_HORIZON",
                "i2_action": None if days >= horizon_days else "APPLY_I2_PACKAGING_OR_RETENTION_BEFORE_HORIZON"})
    return out


def build_child_storage_commissioning(
    body: Mapping[str, Any], *, data_root: Path, schedule_sha256: str, activation_id: str,
    decision: Mapping[str, Any],
) -> dict[str, Any]:
    basis = body["resource_policy"]["storage_basis"]
    grant_sha = canonical_sha256(body)
    subset = {key: decision[key] for key in (
        "decision", "storage_health", "hard_constraints", "physical_tail_reserve", "target_acceptance",
        "grant_sha256", "factory_bytes", "free_bytes", "required_free_bytes", "decided_at")}
    envelope = {
        "kind": EPISODE_STORAGE_KIND_V2_MANAGED,
        "schedule_sha256": schedule_sha256,
        "activation_id": activation_id,
        "producer_root_identity": producer_root_identity(Path(data_root)),
        "storage_decision": subset,
        "verified_backup_sha256": decision["backup"]["artifact_sha256"],
        "copy_rehearsal_sha256": basis["copy_rehearsal_sha256"],
        "factory_storage_receipt_sha256": basis["factory_storage_receipt_sha256"],
        "volume_bindings_sha256": basis["volume_bindings_sha256"],
        "operate_authority_ref": f"MANAGED-GRANT-{grant_sha[:16].upper()}",
        "search_call_local_bytes_max": basis["search_call_local_bytes_max"],
        "nomination_call_local_bytes_max": basis["nomination_call_local_bytes_max"],
        "slot_metadata_local_bytes_max": basis["slot_metadata_local_bytes_max"],
        "fixed_local_reserve_bytes": basis["fixed_local_reserve_bytes"],
        "local_safety_bytes": basis["local_safety_bytes"],
    }
    return {**envelope, "envelope_sha256": canonical_sha256(envelope)}


# --------------------------------------------------------------------------
# Plan / apply / rollback / stop


def storage_basis_from_activation(row: Mapping[str, Any]) -> dict[str, Any]:
    """Reuse the already commissioned (V1 or V2) local bounds of a running activation."""

    envelope = dict((row.get("payload") or {}).get("storage_commissioning") or {})
    keys = _STORAGE_BASIS_KEYS - {"source_ref"}
    if not envelope or not keys.issubset(envelope):
        raise ManagedCollectionError("MANAGED_STORAGE_BASIS_UNAVAILABLE")
    basis = {key: envelope[key] for key in keys}
    basis["source_ref"] = f"ACTIVATION:{row['activation_id']}:ENVELOPE:{envelope['envelope_sha256'][:16]}"
    return basis


def plan_profile(
    *, root: Path, store: ObservationScheduleStore, template_schedule_sha256: str, params: Mapping[str, Any],
    now: datetime,
) -> dict[str, Any]:
    """Read-only proposal. Writes nothing and calls nothing external."""

    registered = store.get_registered_schedule(template_schedule_sha256)
    if registered is None:
        raise ManagedCollectionError("MANAGED_TEMPLATE_NOT_REGISTERED")
    document = registered["document"]
    lineage = collection_lineage_id(document)
    control = store.managed_control(lineage)
    current = int(control["current_revision"]) if control else 0
    expected = params.get("expected_revision")
    expected = current if expected is None else int(expected)
    if expected != current:
        raise ManagedCollectionError("MANAGED_REVISION_CONFLICT")
    scope = str(params["account_scope_id"])
    early = capacity_geometry(document, _limits_from(document, params.get("limits") or {}, scope))
    if any(item["axis"] == "MANAGED_ADAPTER_V1_ADMISSION_CEILING" for item in early["refusals"]):
        return {
            "terminal": "MANAGED_PLAN_REFUSED", "proposal_sha256": None, "collection_lineage_id": lineage,
            "expected_revision": current, "revision": current + 1, "profile": None, "capacity": early,
            "refusals": early["refusals"], "exact_owner_phrase": None,
            "authority_status": "PROPOSED_NOT_AUTHORITY", "provider_calls": 0, "credential_reads": 0,
        }
    basis_activation = params.get("storage_basis_activation_id")
    if basis_activation:
        # The commissioned local bounds may come from any running activation of the store
        # (the template may be a bridge that has not activated yet).
        matches = [row for row in store.list_activations() if str(row["activation_id"]) == str(basis_activation)]
        if len(matches) != 1:
            raise ManagedCollectionError("MANAGED_STORAGE_BASIS_UNAVAILABLE")
        basis = storage_basis_from_activation(matches[0])
    else:
        raise ManagedCollectionError("MANAGED_STORAGE_BASIS_REQUIRED")
    bridge = None
    if params.get("protected_bridge_activation_id"):
        bridge = {"schedule_sha256": template_schedule_sha256,
                  "activation_id": str(params["protected_bridge_activation_id"])}
    body = build_profile(
        root=root, template_document=document, revision=current + 1,
        previous_revision=current or None, limits=params.get("limits") or {}, account_scope_id=scope,
        validity_mode=str(params.get("validity_mode") or "UNTIL_REVOKED"),
        intake_until=params.get("intake_until"),
        planning_horizon_days=int(params.get("planning_horizon_days") or 180),
        bootstrap_not_before=params.get("bootstrap_not_before"), protected_bridge=bridge,
        storage_basis=basis,
        backup_source=str(params.get("backup_source") or DEFAULT_BACKUP_SOURCE),
        backup_max_age_seconds=int(params.get("backup_max_age_seconds") or DEFAULT_BACKUP_MAX_AGE_SECONDS),
        target_acceptance=params.get("target_acceptance"),
        measured_growth_bytes_per_day=params.get("measured_growth_bytes_per_day"),
    )
    geometry = capacity_geometry(body["template"], body["limits"])
    bridge_findings = _bridge_findings(store, body, now)
    account = account_budget_status(store, now=now)
    account_findings = _account_findings(body, account)
    refusals = list(geometry["refusals"]) + bridge_findings + account_findings
    proposal_sha = canonical_sha256(body)
    return {
        "terminal": "MANAGED_PLAN_READY" if not refusals else "MANAGED_PLAN_REFUSED",
        "proposal_sha256": proposal_sha,
        "collection_lineage_id": lineage,
        "expected_revision": current,
        "revision": current + 1,
        "profile": body,
        "capacity": geometry,
        "refusals": refusals,
        "account_budget": {k: account.get(k) for k in ("mode", "account_scope_id", "limits", "remaining")},
        "exact_owner_phrase": grant_phrase(body) if not refusals else None,
        "authority_status": "PROPOSED_NOT_AUTHORITY",
        "provider_calls": 0,
        "credential_reads": 0,
        "owner_burden": {"approvals_for_this_profile": 1, "approvals_per_child_schedule": 0,
                         "approvals_for_rollback_to_approved_restrictive_revision": 0},
    }


def _bridge_findings(store: ObservationScheduleStore, body: Mapping[str, Any], now: datetime) -> list[dict[str, Any]]:
    """The handover boundary must not precede any same-family window that is already planned."""

    family = body["semantics"]["cohort_family_key"]
    not_before = body["continuation"].get("bootstrap_not_before")
    handover = parse_utc(not_before) if not_before else None
    findings: list[dict[str, Any]] = []
    for digest in store.list_registered_schedule_digests():
        registered = store.get_registered_schedule(digest)
        if registered is None or not is_episode_schedule(registered["document"]):
            continue
        document = registered["document"]
        if _cohort_family_key(document) != family:
            continue
        stops = parse_utc(str(document["activation"]["stops_admitting_at"]))
        if stops > now and (handover is None or handover < stops):
            findings.append({"axis": "HANDOVER_BEFORE_PEER_STOPS", "peer_schedule_sha256": digest,
                             "peer_stops_admitting_at": render_utc(stops),
                             "bootstrap_not_before": not_before})
    return findings


def _account_findings(body: Mapping[str, Any], account: Mapping[str, Any]) -> list[dict[str, Any]]:
    if account.get("mode") != "MANAGED":
        return [{"axis": "SHARED_ACCOUNT_BUDGET_NOT_COMMISSIONED", "mode": account.get("mode"),
                 "required_scope": body["limits"]["shared_account_scope"]}]
    findings: list[dict[str, Any]] = []
    if account["account_scope_id"] != body["limits"]["shared_account_scope"]:
        findings.append({"axis": "SHARED_ACCOUNT_SCOPE_MISMATCH", "store_scope": account["account_scope_id"]})
    limits = account["limits"]
    for key, field in (("provider_calls_per_utc_day_max", "provider_calls_per_utc_day"),
                       ("modeled_credits_per_utc_day_max", "modeled_credits_per_utc_day"),
                       ("provider_calls_lifetime_max", "cumulative_calls")):
        if int(body["limits"][field]) > int(limits[key]):
            findings.append({"axis": "PROFILE_EXCEEDS_SHARED_ACCOUNT_" + key.upper(),
                             "profile": int(body["limits"][field]), "account": int(limits[key])})
    return findings


def apply_profile(
    *, root: Path, store: ObservationScheduleStore, template_schedule_sha256: str, params: Mapping[str, Any],
    expected_proposal_sha256: str, phrase: str, now: datetime,
) -> dict[str, Any]:
    plan = plan_profile(root=root, store=store, template_schedule_sha256=template_schedule_sha256,
                        params=params, now=now)
    if plan["terminal"] != "MANAGED_PLAN_READY":
        raise ManagedCollectionError("MANAGED_PLAN_REFUSED")
    body = plan["profile"]
    if plan["proposal_sha256"] != expected_proposal_sha256:
        raise ManagedCollectionError("MANAGED_PROPOSAL_MISMATCH")
    if phrase != grant_phrase(body):
        raise ManagedCollectionError("BLOCKED_AUTHORITY")
    command = canonical_sha256({"op": "APPLY", "profile_sha256": plan["proposal_sha256"],
                                "expected_revision": plan["expected_revision"]})
    payload = {
        "profile": body,
        "approval": {"kind": "OWNER_PHRASE",
                     "phrase_sha256": hashlib.sha256(phrase.encode("utf-8")).hexdigest(),
                     "approved_at": render_utc(now)},
    }
    try:
        outcome = store.managed_commit_profile(
            lineage=body["collection_lineage_id"], revision=body["revision"],
            expected_revision=plan["expected_revision"], profile_sha256=plan["proposal_sha256"],
            command_sha256=command, payload=payload, clock=now)
    except ObservationScheduleStoreError as exc:
        raise ManagedCollectionError(str(exc)) from exc
    return {"terminal": "MANAGED_APPLIED" if outcome == "COMMITTED" else "MANAGED_APPLY_REPLAY",
            "collection_lineage_id": body["collection_lineage_id"], "revision": body["revision"],
            "grant_sha256": plan["proposal_sha256"], "next_action": "AUTOMATIC_RECONCILE_ON_TICK"}


def rollback_profile(
    *, store: ObservationScheduleStore, lineage: str, to_revision: int, expected_revision: int,
    now: datetime, phrase: str | None = None,
) -> dict[str, Any]:
    """New revision with the settings of an earlier approved one. Debt and episodes stay."""

    control = store.managed_control(lineage)
    if control is None or int(control["current_revision"]) != int(expected_revision):
        raise ManagedCollectionError("MANAGED_REVISION_CONFLICT")
    current_body = verified_profile(store, lineage, int(expected_revision))
    target_body = verified_profile(store, lineage, int(to_revision))
    new_body = copy.deepcopy(target_body)
    new_body["revision"] = int(expected_revision) + 1
    new_body["previous_revision"] = int(expected_revision)
    if _not_wider(new_body, current_body):
        approval: dict[str, Any] = {"kind": "ROLLBACK_TO_APPROVED", "rollback_to_revision": int(to_revision),
                                    "approved_at": render_utc(now)}
    else:
        if phrase != grant_phrase(new_body):
            raise ManagedCollectionError("ROLLBACK_NOT_RESTRICTIVE_PHRASE_REQUIRED")
        approval = {"kind": "OWNER_PHRASE", "phrase_sha256": hashlib.sha256(phrase.encode("utf-8")).hexdigest(),
                    "approved_at": render_utc(now)}
    validate_profile(new_body)
    command = canonical_sha256({"op": "ROLLBACK", "profile_sha256": canonical_sha256(new_body),
                                "expected_revision": int(expected_revision)})
    try:
        outcome = store.managed_commit_profile(
            lineage=lineage, revision=new_body["revision"], expected_revision=int(expected_revision),
            profile_sha256=canonical_sha256(new_body), command_sha256=command,
            payload={"profile": new_body, "approval": approval}, resume=False, clock=now)
    except ObservationScheduleStoreError as exc:
        raise ManagedCollectionError(str(exc)) from exc
    return {"terminal": "MANAGED_ROLLED_BACK" if outcome == "COMMITTED" else "MANAGED_ROLLBACK_REPLAY",
            "revision": new_body["revision"], "restored_from_revision": int(to_revision),
            "effective": "NEXT_CHILD_AT_UTC_BOUNDARY", "existing_children_unchanged": True,
            "desired_state": store.managed_control(lineage)["desired_state"],
            "resume_requires": "collection-plan and collection-apply with the exact owner phrase",
            "debt_and_admitted_episodes_preserved": True}


def stop_intake(
    *, root: Path, data_root: Path, store: ObservationScheduleStore, lineage: str, expected_revision: int,
    now: datetime, producer_git_sha: str,
) -> dict[str, Any]:
    """Stop NEW intake. Already committed tails and the issued child authority stay valid."""

    try:
        outcome = store.managed_set_desired(
            lineage, expected_revision=int(expected_revision), desired_state="STOP_INTAKE",
            intake_revoked_at=render_utc(now), clock=now)
    except ObservationScheduleStoreError as exc:
        raise ManagedCollectionError(str(exc)) from exc
    stopped = _enforce_stop(store, data_root, lineage, now, producer_git_sha)
    return {"terminal": "MANAGED_INTAKE_STOPPED", "desired": outcome, "children_stopped": stopped,
            "tails": "CONTINUE_UNDER_ISSUED_CHILD_AUTHORITY"}


def _enforce_stop(store: ObservationScheduleStore, data_root: Path, lineage: str, now: datetime,
                  producer: str) -> list[str]:
    stopped: list[str] = []
    for child in store.managed_children(lineage):
        if child["state"] in _CHILD_TERMINAL:
            continue
        activation = store.get_activation(child["schedule_sha256"], child["activation_id"])
        if activation is not None and str(activation["state"]) == "ACTIVE":
            stop_episode_intake(data_root=data_root, store=store, schedule_sha256=child["schedule_sha256"],
                                activation_id=child["activation_id"], now=now, producer_git_sha=producer)
            stopped.append(child["activation_id"])
        elif activation is None and child["state"] in _CHILD_NON_TERMINAL:
            store.managed_upsert_child(
                lineage=lineage, utc_day=child["utc_day"], state="CANCELLED",
                profile_revision=child["profile_revision"], schedule_sha256=child["schedule_sha256"],
                activation_id=child["activation_id"], payload=child["payload"], clock=now)
    return stopped


# --------------------------------------------------------------------------
# Reconcile


def _child_window(
    store: ObservationScheduleStore, data_root: Path, body: Mapping[str, Any], now: datetime, today: str
) -> tuple[datetime, datetime] | tuple[None, str]:
    """Lawful forward window for the one child of ``today`` or the reason to wait."""

    family = body["semantics"]["cohort_family_key"]
    day_start = _day_start(now)
    floor = [day_start]
    own_ids = {c["activation_id"] for c in store.managed_children(body["collection_lineage_id"])
               if c["utc_day"] == today}
    for row in store.list_activations():
        if str(row["activation_id"]) in own_ids:
            continue
        projected = project_activation_as_of(row, now)
        state = str(projected.get("state") or "")
        if state not in {"ACTIVE", "DRAINING"}:
            continue
        registered = store.get_registered_schedule(str(row["schedule_sha256"]))
        if registered is None:
            return None, "WAIT_PEER_REGISTRATION_UNAVAILABLE"
        if _cohort_family_key(registered["document"]) != family:
            continue
        stops = parse_utc(str(row["stops_admitting_at"]))
        if state == "ACTIVE":
            return None, "WAIT_PEER_ACTIVE" if now < stops else "WAIT_PEER_CLOSURE"
        if not _activation_is_non_admitting(row, now=now):
            return None, "WAIT_PEER_CLOSURE"
        recovery = _non_admitting_recovery_at(data_root, row, now=now)
        if recovery is None or recovery > now:
            return None, "WAIT_PEER_CLOSURE_PROOF"
        floor += [stops, recovery]
    # The window opens when the controller can lawfully admit (never backdated, never
    # before a proven peer closure); the gap before it stays visible in the data.
    starts = max(floor + [_floor_seconds(now)])
    stops_at = day_start + _DAY
    validity = body["validity"]
    if validity["mode"] == "UNTIL_DATE":
        stops_at = min(stops_at, parse_utc(str(validity["intake_until"])))
    if starts >= stops_at:
        return None, "WAIT_NEXT_BOUNDARY" if validity["mode"] == "UNTIL_REVOKED" else "VALIDITY_ENDED"
    return starts, stops_at


def _sync_child_states(store: ObservationScheduleStore, lineage: str, now: datetime) -> None:
    for child in store.managed_children(lineage):
        if child["state"] in _CHILD_TERMINAL:
            continue
        activation = store.get_activation(child["schedule_sha256"], child["activation_id"])
        if activation is None:
            continue
        mapped = _ACTIVATION_TO_CHILD_STATE.get(str(activation["state"]))
        if mapped and mapped != child["state"] and child["state"] not in {"TAIL_COMPLETE"}:
            store.managed_upsert_child(
                lineage=lineage, utc_day=child["utc_day"], state=mapped,
                profile_revision=child["profile_revision"], schedule_sha256=child["schedule_sha256"],
                activation_id=child["activation_id"], payload=child["payload"], clock=now)


def _plan_child(
    *, root: Path, store: ObservationScheduleStore, data_root: Path, body: Mapping[str, Any],
    window: tuple[datetime, datetime], today: str, now: datetime,
) -> dict[str, Any]:
    document = copy.deepcopy(body["template"])
    document["activation"] = {"starts_at": render_utc(window[0]), "stops_admitting_at": render_utc(window[1])}
    document = validate_observation_schedule(document, root=root)
    schedule_sha = str(document["schedule_sha256"])
    activation_id = "ACT-" + schedule_sha[:16].upper()
    decision = managed_storage_decision(store=store, body=body, data_root=data_root, root=root, now=now)
    if decision["decision"] == "BLOCK":
        return {"blocked": True, "decision": decision}
    envelope = build_child_storage_commissioning(
        body, data_root=data_root, schedule_sha256=schedule_sha, activation_id=activation_id, decision=decision)
    return {
        "blocked": False,
        "schedule_sha256": schedule_sha,
        "activation_id": activation_id,
        "payload": {
            "document": document,
            "storage_commissioning": envelope,
            "storage_decision": {k: decision[k] for k in ("decision", "storage_health", "reasons", "decided_at")},
            "window": {"starts_at": document["activation"]["starts_at"],
                       "stops_admitting_at": document["activation"]["stops_admitting_at"]},
            "grant_sha256": canonical_sha256(body),
            "planned_at": render_utc(now),
        },
    }


def _drive_child(
    *, root: Path, store: ObservationScheduleStore, data_root: Path, lineage: str, child: Mapping[str, Any],
    body: Mapping[str, Any], now: datetime, producer: str,
) -> str:
    """Replay the remaining lifecycle steps from the persisted intent. Idempotent."""

    payload = dict(child["payload"])
    sha = str(child["schedule_sha256"])
    activation_id = str(child["activation_id"])
    state = str(child["state"])

    def advance(new_state: str) -> None:
        nonlocal state
        state = new_state
        store.managed_upsert_child(
            lineage=lineage, utc_day=child["utc_day"], state=new_state,
            profile_revision=child["profile_revision"], schedule_sha256=sha, activation_id=activation_id,
            payload=payload, clock=now)

    if state == "PLANNED":
        registered = register_schedule(root=root, data_root=data_root, store=store,
                                       document=payload["document"], now=now, producer_git_sha=producer)
        if registered.get("schedule_sha256") != sha:
            raise ManagedCollectionError("MANAGED_CHILD_REGISTRATION_MISMATCH")
        advance("REGISTERED")
    if state == "REGISTERED":
        existing = store.latest_authority_for_schedule(sha)
        if existing and existing.get("authority_basis") == "STANDING_GRANT" and existing.get(
                "standing_grant_sha256") == payload["grant_sha256"]:
            # A kill between the SQL commit and the ResearchEvent append leaves a receipt
            # without its immutable event: rebuild the very same event, never a new receipt.
            ensure_authority_event(data_root=data_root, store=store, receipt_sha256=str(existing["receipt_sha256"]),
                                   now=now, producer_git_sha=producer)
        else:
            authorize_schedule_from_standing_grant(
                root=root, data_root=data_root, store=store, schedule_sha256=sha,
                standing_grant_sha256=payload["grant_sha256"],
                standing_grant_revision=int(child["profile_revision"]), now=now, producer_git_sha=producer)
        advance("AUTHORIZED_DERIVED")
    if state == "AUTHORIZED_DERIVED":
        result = activate_schedule(
            root=root, data_root=data_root, store=store, schedule_sha256=sha, activation_id=activation_id,
            now=now, producer_git_sha=producer, storage_commissioning=payload["storage_commissioning"],
            managed_binding={"collection_lineage_id": lineage, "grant_sha256": payload["grant_sha256"],
                             "profile_revision": int(child["profile_revision"]), "utc_day": child["utc_day"]})
        if result["terminal"] not in {"ACTIVATED", "ACTIVATE_REPLAY"}:
            raise ManagedCollectionError("MANAGED_CHILD_ACTIVATION_" + str(result["terminal"]))
        advance("ACTIVATED")
    return state


def reconcile_once(
    *, root: Path, data_root: Path, store: ObservationScheduleStore, now: datetime, producer_git_sha: str,
) -> dict[str, Any]:
    """One bounded, idempotent controller step. Never calls a provider or reads a credential."""

    lineages = store.managed_lineages()
    base = {"provider_calls": 0, "credential_reads": 0}
    if not lineages:
        return {"terminal": "RECONCILE_NOT_MANAGED", **base}
    if store.restore_marker_unresolved():
        # A restored older store may have lost debits or a newer revoke: no new intake until the
        # restore is reconciled by its owner.
        return {"terminal": "RECONCILE_RESTORE_MARKER_UNRESOLVED", "next_action": "RESOLVE_RESTORE_MARKER", **base}
    token = store.acquire_lease("managed-reconcile", clock=now)
    if token is None:
        return {"terminal": "RECONCILE_DEFERRED_WRITER_BUSY", **base}
    try:
        reports = [_reconcile_isolated(root=root, data_root=data_root, store=store, lineage=lineage, now=now,
                                       producer=producer_git_sha) for lineage in lineages]
    finally:
        store.release_lease(token)
    first = reports[0]
    return {"terminal": first["terminal"], "lineages": reports, **base,
            **({"activated": first["activated"]} if first.get("activated") else {})}


def _reconcile_isolated(
    *, root: Path, data_root: Path, store: ObservationScheduleStore, lineage: str, now: datetime, producer: str,
) -> dict[str, Any]:
    """A controller bug or a killed step must not stop the committed tails already served."""

    try:
        report = _reconcile_lineage(root=root, data_root=data_root, store=store, lineage=lineage, now=now,
                                    producer=producer)
        _recover_all(store, lineage, ("RECONCILE_UNEXPECTED_ERROR:",), now)
        return report
    except Exception as exc:  # noqa: BLE001 - class name only; the next tick resumes from the intent
        store.managed_incident_open(
            "RECONCILE_UNEXPECTED_ERROR:" + lineage,
            {"reason": type(exc).__name__, "scope": "NEW_INTAKE", "automatic_action": "RETRY_NEXT_TICK"},
            clock=now)
        return {"collection_lineage_id": lineage, "terminal": "RECONCILE_UNEXPECTED_ERROR",
                "reason": type(exc).__name__}


def _reconcile_lineage(
    *, root: Path, data_root: Path, store: ObservationScheduleStore, lineage: str, now: datetime, producer: str,
) -> dict[str, Any]:
    control = store.managed_control(lineage)
    report: dict[str, Any] = {"collection_lineage_id": lineage}
    try:
        body = verified_profile(store, lineage, int(control["current_revision"]))
    except ManagedCollectionError as exc:
        store.managed_incident_open("GRANT_INVALID:" + lineage, {"reason": str(exc), "scope": "NEW_INTAKE"}, clock=now)
        return {**report, "terminal": "RECONCILE_BLOCKED_" + str(exc)}
    _recover_all(store, lineage, ("GRANT_INVALID:",), now)
    _sync_child_states(store, lineage, now)
    revision = int(control["current_revision"])
    report["revision"] = revision
    if str(control["desired_state"]) != "RUN":
        stopped = _enforce_stop(store, data_root, lineage, now, producer)
        return {**report, "terminal": "RECONCILE_INTAKE_STOPPED", "children_stopped": stopped}
    not_before = body["continuation"].get("bootstrap_not_before")
    if not_before and now < parse_utc(not_before):
        return {**report, "terminal": "RECONCILE_WAIT_BOOTSTRAP_NOT_BEFORE", "not_before": not_before}
    today = _day_start(now).strftime("%Y-%m-%d")
    child = store.managed_child(lineage, today)
    if child is not None and (
        (child["state"] in _CHILD_NON_TERMINAL and int(child["profile_revision"]) != revision)
        or child["state"] == "CANCELLED"
    ):
        # Before the first admission a newer revision (or a re-applied RUN) may replace the
        # intent. After activation the day owner is never replaced.
        store.managed_supersede_child(lineage, today, clock=now)
        child = None
    if child is not None and now >= parse_utc(child["payload"]["window"]["stops_admitting_at"]):
        if child["state"] in _CHILD_NON_TERMINAL:
            store.managed_upsert_child(
                lineage=lineage, utc_day=today, state="EXPIRED_BEFORE_ACTIVATION",
                profile_revision=child["profile_revision"], schedule_sha256=child["schedule_sha256"],
                activation_id=child["activation_id"], payload=child["payload"], clock=now)
        _recover_all(store, lineage, ("INTAKE_OWNER_MISSING:",), now)
        return {**report, "terminal": "RECONCILE_VALIDITY_ENDED", "utc_day": today}
    if child is None:
        blocked = store.managed_incident("STORAGE_BLOCKED:" + lineage)
        if (blocked is not None and blocked["state"] == "OPEN"
                and (now - parse_utc(blocked["updated_at"])).total_seconds() < BLOCKED_RECHECK_SECONDS):
            return {**report, "terminal": "RECONCILE_BLOCKED_NEW_INTAKE",
                    "reasons": list(blocked["payload"].get("reasons") or []), "cached": True}
        window = _child_window(store, data_root, body, now, today)
        if window[0] is None:
            return _finish_wait(store, body, lineage, report, str(window[1]), now)
        planned = _plan_child(root=root, store=store, data_root=data_root, body=body, window=window,  # type: ignore[arg-type]
                              today=today, now=now)
        if planned["blocked"]:
            return _finish_blocked(store, lineage, report, planned["decision"], now)
        child = store.managed_upsert_child(
            lineage=lineage, utc_day=today, state="PLANNED", profile_revision=revision,
            schedule_sha256=planned["schedule_sha256"], activation_id=planned["activation_id"],
            payload=planned["payload"], clock=now)
        _recover_all(store, lineage, ("STORAGE_BLOCKED:",), now)
    if child["state"] in _CHILD_NON_TERMINAL:
        try:
            _drive_child(root=root, store=store, data_root=data_root, lineage=lineage, child=child, body=body,
                         now=now, producer=producer)
        except (ObservationLifecycleError, ManagedCollectionError, ObservationScheduleStoreError) as exc:
            store.managed_incident_open("CHILD_STEP_FAILED:" + lineage, {"reason": str(exc), "utc_day": today,
                                        "scope": "NEW_INTAKE"}, clock=now)
            return {**report, "terminal": "RECONCILE_CHILD_STEP_FAILED", "reason": str(exc), "utc_day": today}
        _recover_all(store, lineage, ("CHILD_STEP_FAILED:", "INTAKE_OWNER_MISSING:"), now)
        return {**report, "terminal": "RECONCILE_CHILD_ACTIVATED", "utc_day": today,
                "activated": {"schedule_sha256": child["schedule_sha256"], "activation_id": child["activation_id"]}}
    if child["state"] == "ACTIVATED":
        activation = store.get_activation(child["schedule_sha256"], child["activation_id"])
        repaired = False
        if activation is not None and str(activation["state"]) == "ACTIVE" and not (
            activation_transition_research_event_proven(data_root, activation, now=now)
        ):
            # Crash between the activation commit and its ResearchEvent: replay appends it.
            repaired = bool(activate_schedule(
                root=root, data_root=data_root, store=store, schedule_sha256=child["schedule_sha256"],
                activation_id=child["activation_id"], now=now, producer_git_sha=producer,
                storage_commissioning=child["payload"]["storage_commissioning"]).get("event_repaired"))
        _recover_all(store, lineage, ("INTAKE_OWNER_MISSING:", "STORAGE_BLOCKED:", "CHILD_STEP_FAILED:"), now)
        return {**report, "terminal": "RECONCILE_INTAKE_OK", "utc_day": today,
                **({"event_repaired": True, "activated": {"schedule_sha256": child["schedule_sha256"],
                                                          "activation_id": child["activation_id"]}}
                   if repaired else {})}
    # The day owner closed before its window ended (operator stop, abort, pause or drain): the
    # day is never fragmented; a new child starts at the next UTC boundary.
    store.managed_incident_open(
        "INTAKE_OWNER_MISSING:" + lineage,
        {"reason": "DAY_OWNER_CLOSED_" + str(child["state"]), "utc_day": today,
         "scope": "NEW_INTAKE_UNTIL_NEXT_UTC_DAY", "automatic_action": "NEW_CHILD_AT_NEXT_UTC_BOUNDARY"},
        clock=now)
    return {**report, "terminal": "RECONCILE_DAY_OWNER_CLOSED", "utc_day": today, "state": child["state"]}


def update_hold_incident(
    store: ObservationScheduleStore, tick_results: list[Mapping[str, Any]], now: datetime
) -> dict[str, Any] | None:
    """Raise or clear the durable HOLD incident from what the managed child's own tick reported."""

    lineages = store.managed_lineages()
    if not lineages:
        return None
    held = [item for item in tick_results if str(item.get("stop_reason") or "").endswith("_HOLD")]
    outcome = None
    for lineage in lineages:
        outcome = _update_hold_for(store, lineage, tick_results, held, now) or outcome
    return outcome


def _update_hold_for(store, lineage, tick_results, held, now):  # noqa: ANN001
    key = "INTAKE_HELD:" + lineage
    if held:
        reserve = dict(held[0].get("drain_headroom") or {})
        store.managed_incident_open(
            key,
            {"reasons": [str(held[0]["stop_reason"])], "scope": "NEW_INTAKE_THIS_ROUND_SAME_CHILD",
             "required_free_bytes": reserve.get("required_free_bytes"), "free_bytes": reserve.get("free_bytes"),
             "automatic_action": "RESUME_ADMISSION_WHEN_FREE_SPACE_RETURNS"},
            clock=now)
        return {"incident": key, "state": "OPEN"}
    if any(str(item.get("activation_state")) == "ACTIVE" and not item.get("stop_reason") for item in tick_results):
        _recover_all(store, lineage, ("INTAKE_HELD:",), now)
    return None


def _recover_all(store: ObservationScheduleStore, lineage: str, prefixes: tuple[str, ...], now: datetime) -> None:
    for prefix in prefixes:
        incident = store.managed_incident(prefix + lineage)
        if incident is not None and incident["state"] == "OPEN":
            store.managed_incident_recover(prefix + lineage, clock=now)


def _finish_wait(store, body, lineage, report, reason: str, now: datetime) -> dict[str, Any]:  # noqa: ANN001
    day_age = (now - _day_start(now)).total_seconds()
    if reason in {"WAIT_PEER_ACTIVE", "WAIT_NEXT_BOUNDARY", "VALIDITY_ENDED"}:
        return {**report, "terminal": "RECONCILE_" + reason}
    if day_age > INTAKE_MISSING_GRACE_SECONDS:
        store.managed_incident_open(
            "INTAKE_OWNER_MISSING:" + lineage,
            {"reason": reason, "scope": "NEW_INTAKE", "utc_day": _day_start(now).strftime("%Y-%m-%d")}, clock=now)
    return {**report, "terminal": "RECONCILE_" + reason}


def _finish_blocked(store, lineage, report, decision: Mapping[str, Any], now: datetime) -> dict[str, Any]:  # noqa: ANN001
    key = "STORAGE_BLOCKED:" + lineage
    payload = {"reasons": decision["reasons"], "scope": "NEW_INTAKE_ONLY", "committed_tails": "CONTINUE",
               "factory_bytes": decision["factory_bytes"], "free_bytes": decision["free_bytes"],
               "projected_peak_bytes": decision["projected_peak_bytes"], "footprint": decision["footprint"],
               "required_free_bytes": decision["required_free_bytes"], "backup": decision["backup"],
               "runway": decision["runway"]}
    store.managed_incident_open(key, payload, clock=now)
    return {**report, "terminal": "RECONCILE_BLOCKED_NEW_INTAKE", "reasons": decision["reasons"]}


# --------------------------------------------------------------------------
# Read-only status


def collection_status(
    *, store: ObservationScheduleStore, data_root: Path, root: Path, now: datetime, measure_storage: bool = False,
) -> dict[str, Any]:
    lineages = store.managed_lineages()
    if not lineages:
        return {"terminal": "MANAGED_UNMANAGED", "mode": "UNMANAGED",
                "next_action": "COLLECTION_PLAN_UNDER_OPERATE_GATE", "provider_calls": 0}
    out = []
    for lineage in lineages:
        control = store.managed_control(lineage)
        revision = int(control["current_revision"])
        try:
            body = verified_profile(store, lineage, revision)
            grant = {"state": "VALID", "grant_sha256": canonical_sha256(body)}
        except ManagedCollectionError as exc:
            out.append({"collection_lineage_id": lineage, "revision": revision, "grant": {"state": str(exc)},
                        "next_action": "INSPECT_GRANT_INTEGRITY"})
            continue
        children = store.managed_children(lineage)
        activations = {
            (str(r["schedule_sha256"]), str(r["activation_id"])): project_activation_as_of(r, now)
            for r in store.list_activations()
        }
        view = [
            {"utc_day": c["utc_day"], "state": c["state"], "activation_id": c["activation_id"],
             "profile_revision": c["profile_revision"],
             "activation_state": str(activations.get((c["schedule_sha256"], c["activation_id"]), {}).get("state") or "ABSENT"),
             "window": c["payload"].get("window")}
            for c in children[-8:]
        ]
        today = _day_start(now).strftime("%Y-%m-%d")
        current = next((c for c in view if c["utc_day"] == today), None)
        incidents = store.managed_incidents(open_only=True)
        item: dict[str, Any] = {
            "collection_lineage_id": lineage,
            "revision": revision,
            "desired_state": control["desired_state"],
            "intake_revoked_at": control.get("intake_revoked_at"),
            "grant": grant,
            "validity": body["validity"],
            "limits": body["limits"],
            "current_intake": current,
            "recent_children": view,
            "tails_outstanding": [c["activation_id"] for c in view if c["activation_state"] == "DRAINING"],
            "protected_bridge": body["continuation"].get("protected_bridge"),
            "bootstrap_not_before": body["continuation"].get("bootstrap_not_before"),
            "open_incidents": [{"incident_key": i["incident_key"], **i["payload"]} for i in incidents],
            "capacity": capacity_geometry(body["template"], body["limits"]),
            "backup": read_verified_backup(root=root, policy=body["resource_policy"], now=now),
        }
        if measure_storage:
            footprint = measure_whole_factory(store=store, data_root=data_root, root=root)
            known = all(isinstance(footprint[key], int) for key in ("sqlite_bytes", "resident_rdp_bytes", "backup_sink_bytes"))
            item["footprint"] = footprint
            item["runway"] = _runway(
                body["resource_policy"],
                footprint["sqlite_bytes"] + footprint["resident_rdp_bytes"] + footprint["backup_sink_bytes"] if known else None,
                int(body["validity"]["planning_horizon_days"]))
        out.append(item)
    account = account_budget_status(store, now=now)
    return {
        "terminal": "MANAGED_STATUS",
        "mode": "MANAGED",
        "lineages": out,
        "account_budget": {k: account.get(k) for k in ("mode", "account_scope_id", "limits", "shared_usage",
                                                       "remaining", "unbound_live_activations")},
        "observed_at": render_utc(now),
        "provider_calls": 0,
        "credential_reads": 0,
        "next_action": "NONE" if not any(i["open_incidents"] for i in out) else "INSPECT_OPEN_INCIDENTS",
    }
