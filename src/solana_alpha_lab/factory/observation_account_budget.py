"""Shared managed-account budget: commissioning, policy revision and readout.

One ops store serves one runtime credential locator, hence at most one managed
account scope. The per-activation ``accounting_counters``/``lifetime_counters``
rows remain the only debit history; the shared gate in
``observation_scheduler._Accounting`` sums them over explicit membership.
Nothing here copies, seeds or resets counters, reads a credential value or
calls a provider. Commissioning is default-off: merge/deploy alone never
enables it.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from solana_alpha_lab.factory.observation_schedule import canonical_json_bytes, render_utc
from solana_alpha_lab.factory.observation_schedule_store import (
    ObservationScheduleStore,
    ObservationScheduleStoreError,
)

PROVIDER_LANE = "JUPITER"
LIMIT_KEYS = (
    "provider_calls_per_utc_day_max",
    "modeled_credits_per_utc_day_max",
    "provider_calls_lifetime_max",
)
COVERAGE = {
    "scope": "CONTROLLED_CALLERS_OF_THIS_OPS_STORE",
    "external_callers": "UNKNOWN",
    "global_account_proven": False,
}
PERIOD_BOUNDARY = "ALL_ACTIVATIONS_AND_COUNTER_SCOPES_IN_THIS_STORE_CONSERVATIVE"
_SCOPE_ID = re.compile(r"^[A-Z][A-Z0-9_.-]{2,63}$")
_LOCATOR = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")


class AccountBudgetError(ValueError):
    """Typed refusal; the message is a canonical terminal."""


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _limits(raw: Mapping[str, Any]) -> dict[str, int]:
    limits: dict[str, int] = {}
    for key in LIMIT_KEYS:
        value = raw.get(key)
        if type(value) is not int or value <= 0:
            raise AccountBudgetError("ACCOUNT_BUDGET_LIMIT_INVALID")
        limits[key] = value
    return limits


def _identity(account_scope_id: str, credential_locator: str) -> None:
    if not _SCOPE_ID.fullmatch(account_scope_id or ""):
        raise AccountBudgetError("ACCOUNT_SCOPE_ID_INVALID")
    # A schedule/activation identity is not an account identity.
    if account_scope_id.startswith(("ACT-", "OBS-")) or re.search(r"[0-9a-f]{32}", account_scope_id.lower()):
        raise AccountBudgetError("ACCOUNT_SCOPE_ID_INVALID")
    if not _LOCATOR.fullmatch(credential_locator or ""):
        raise AccountBudgetError("CREDENTIAL_LOCATOR_INVALID")


def _member_debits(store: ObservationScheduleStore, member: Mapping[str, Any], utc_day: str) -> dict[str, int]:
    day = store.load_accounting(
        schedule_sha256=member["schedule_sha256"], activation_id=member["activation_id"], utc_day=utc_day
    )
    life = store.load_lifetime(
        schedule_sha256=member["schedule_sha256"], activation_id=member["activation_id"]
    )
    return {
        "day_provider_calls": int(day["provider_calls"]),
        "day_modeled_credits": int(day["modeled_credits"]),
        "lifetime_provider_calls": int(life["provider_calls"]),
    }


def _remaining(limits: Mapping[str, int], usage: Mapping[str, int]) -> dict[str, Any]:
    pairs = (
        ("day_provider_calls", "provider_calls_per_utc_day_max"),
        ("day_modeled_credits", "modeled_credits_per_utc_day_max"),
        ("lifetime_provider_calls", "provider_calls_lifetime_max"),
    )
    return {
        "remaining": {used: max(0, int(limits[cap]) - int(usage[used])) for used, cap in pairs},
        "over_limit": sorted(used for used, cap in pairs if int(usage[used]) > int(limits[cap])),
    }


def prepare_account_budget(
    store: ObservationScheduleStore,
    *,
    account_scope_id: str,
    credential_locator: str,
    limits: Mapping[str, Any],
    now: datetime,
) -> dict[str, Any]:
    """Read-only commissioning plan; counters are shown live, never snapshotted."""

    _identity(account_scope_id, credential_locator)
    bounded = _limits(limits)
    utc_day = now.astimezone(UTC).strftime("%Y-%m-%d")
    existing = store.account_budget_scope()
    members = store.account_budget_candidate_members()
    totals = {"day_provider_calls": 0, "day_modeled_credits": 0, "lifetime_provider_calls": 0}
    rows = []
    for member in members:
        debits = _member_debits(store, member, utc_day)
        for key in totals:
            totals[key] += debits[key]
        rows.append({**member, **debits})
    identity = {
        "account_scope_id": account_scope_id,
        "provider_lane": PROVIDER_LANE,
        "credential_locator": credential_locator,
        "limits": bounded,
        "members": [[m["schedule_sha256"], m["activation_id"]] for m in members],
        "period_boundary": PERIOD_BOUNDARY,
    }
    plan_sha256 = _sha(identity)
    if existing is not None:
        terminal = (
            "ACCOUNT_BUDGET_ALREADY_APPLIED"
            if existing["account_scope_id"] == account_scope_id
            else "ACCOUNT_BUDGET_ALREADY_COMMISSIONED"
        )
    elif store.restore_marker_unresolved():
        terminal = "RESTORE_MARKER_UNRESOLVED"
    else:
        terminal = "ACCOUNT_BUDGET_PLAN_READY"
    return {
        "terminal": terminal,
        "mode_before": "UNMANAGED" if existing is None else "COMMISSIONED",
        **identity,
        "member_debits": rows,
        "member_count": len(rows),
        "utc_day": utc_day,
        "shared_usage_at_prepare": totals,
        **_remaining(bounded, totals),
        "coverage": COVERAGE,
        "plan_sha256": plan_sha256,
        "observed_at": render_utc(now),
        "counter_note": "LIVE_ROWS_NOT_SEEDED; debits after prepare are included at apply",
        "next_action": "ACCOUNT_BUDGET_APPLY_WITH_EXPECTED_PLAN_SHA256"
        if terminal == "ACCOUNT_BUDGET_PLAN_READY"
        else "INSPECT_ACCOUNT_BUDGET_STATUS",
    }


def apply_account_budget(
    store: ObservationScheduleStore,
    *,
    account_scope_id: str,
    credential_locator: str,
    limits: Mapping[str, Any],
    expected_plan_sha256: str,
    now: datetime,
) -> dict[str, Any]:
    """Bind the managed account exactly once under the writer lease."""

    existing = store.account_budget_scope()
    if existing is not None:
        if existing["commission_sha256"] != expected_plan_sha256:
            raise AccountBudgetError("ACCOUNT_BUDGET_ALREADY_COMMISSIONED")
        first = store.account_budget_policy_revision(str(existing["account_scope_id"]), 1)
        if (existing["account_scope_id"] != account_scope_id
                or existing["credential_locator"] != credential_locator
                or first is None
                or any(int(first[key]) != _limits(limits)[key] for key in LIMIT_KEYS)):
            # A mistyped scope or limit is never reported as "already applied".
            raise AccountBudgetError("ACCOUNT_BUDGET_REPLAY_MISMATCH")
        return {**account_budget_status(store, now=now), "terminal": "ACCOUNT_BUDGET_ALREADY_APPLIED",
                "replayed": True}
    lease = store.acquire_lease("ACCOUNT-BUDGET-COMMISSION", clock=now)
    if not lease:
        raise AccountBudgetError("WRITER_BUSY")
    try:
        plan = prepare_account_budget(
            store, account_scope_id=account_scope_id, credential_locator=credential_locator,
            limits=limits, now=now,
        )
        if plan["terminal"] != "ACCOUNT_BUDGET_PLAN_READY":
            raise AccountBudgetError(plan["terminal"])
        if plan["plan_sha256"] != expected_plan_sha256:
            raise AccountBudgetError("ACCOUNT_BUDGET_PLAN_STALE")
        bounded = _limits(limits)
        policy = {
            **bounded,
            "command_sha256": _sha({"commission_sha256": expected_plan_sha256, "revision": 1, **bounded}),
            "payload": {"reason": "COMMISSIONING"},
        }
        store.commission_account_budget(
            account_scope_id=account_scope_id,
            provider_lane=PROVIDER_LANE,
            credential_locator=credential_locator,
            commission_sha256=expected_plan_sha256,
            policy=policy,
            members=[tuple(item) for item in plan["members"]],
            payload={"period_boundary": PERIOD_BOUNDARY, "coverage": COVERAGE,
                     "credential_locator_kind": "RUNTIME_ENV_NAME_NOT_VALUE"},
            clock=now,
        )
    except ObservationScheduleStoreError as exc:
        raise AccountBudgetError(str(exc)) from exc
    finally:
        store.release_lease(lease)
    status = account_budget_status(store, now=now)
    return {**status, "terminal": "ACCOUNT_BUDGET_APPLIED", "replayed": False,
            "baseline_at_apply": status["shared_usage"]}


def revise_account_budget_policy(
    store: ObservationScheduleStore,
    *,
    expected_revision: int,
    limits: Mapping[str, Any],
    reason: str,
    now: datetime,
) -> dict[str, Any]:
    """Append a policy revision; debt and history are never rewritten."""

    scope = store.account_budget_scope()
    if scope is None:
        raise AccountBudgetError("ACCOUNT_BUDGET_NOT_COMMISSIONED")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", reason or ""):
        raise AccountBudgetError("ACCOUNT_BUDGET_REVISION_REASON_INVALID")
    bounded = _limits(limits)
    scope_id = str(scope["account_scope_id"])
    command = _sha({"account_scope_id": scope_id, "expected_revision": int(expected_revision), **bounded})
    replay = store.account_budget_policy_by_command(command)
    if replay is not None:
        return {**account_budget_status(store, now=now), "terminal": "ACCOUNT_BUDGET_POLICY_REVISED",
                "replayed": True, "revision": int(replay["revision"])}
    if store.restore_marker_unresolved():
        raise AccountBudgetError("RESTORE_MARKER_UNRESOLVED")
    lease = store.acquire_lease("ACCOUNT-BUDGET-REVISION", clock=now)
    if not lease:
        raise AccountBudgetError("WRITER_BUSY")
    try:
        revision = store.revise_account_budget_policy(
            account_scope_id=scope_id,
            expected_revision=int(expected_revision),
            policy={**bounded, "command_sha256": command, "payload": {"reason": reason}},
            clock=now,
        )
    except ObservationScheduleStoreError as exc:
        raise AccountBudgetError(str(exc)) from exc
    finally:
        store.release_lease(lease)
    return {**account_budget_status(store, now=now), "terminal": "ACCOUNT_BUDGET_POLICY_REVISED",
            "replayed": False, "revision": revision}


def account_budget_status(store: ObservationScheduleStore, *, now: datetime) -> dict[str, Any]:
    """Read-only shared-account readout; writes no counters."""

    utc_day = now.astimezone(UTC).strftime("%Y-%m-%d")
    scope = store.account_budget_scope()
    if scope is None:
        probe = store.account_budget_binding(schedule_sha256="", activation_id="")
        if probe["mode"] == "CORRUPT":
            return {"terminal": "ACCOUNT_BUDGET_CORRUPT", "mode": "CORRUPT", "reason": probe["reason"],
                    "next_action": "RECONCILE_ACCOUNT_BUDGET_BINDING"}
        return {"terminal": "ACCOUNT_BUDGET_UNMANAGED", "mode": "UNMANAGED",
                "enforcement": "ACTIVATION_LOCAL_CAPS_ONLY",
                "next_action": "ACCOUNT_BUDGET_PREPARE_UNDER_OPERATE_GATE"}
    scope_id = str(scope["account_scope_id"])
    policy = store.account_budget_policy(scope_id)
    if scope["scope_count"] != 1 or policy is None:
        return {"terminal": "ACCOUNT_BUDGET_CORRUPT", "mode": "CORRUPT", "account_scope_id": scope_id,
                "reason": "ACCOUNT_BUDGET_SCOPE_AMBIGUOUS" if scope["scope_count"] != 1
                else "ACCOUNT_BUDGET_POLICY_MISSING",
                "next_action": "RECONCILE_ACCOUNT_BUDGET_BINDING"}
    members = store.account_budget_members(scope_id)
    bound = {(m["schedule_sha256"], m["activation_id"]) for m in members}
    unbound_live = [
        {"schedule_sha256": str(row["schedule_sha256"]), "activation_id": str(row["activation_id"]),
         "state": str(row["state"])}
        for row in store.list_activations()
        if (str(row["schedule_sha256"]), str(row["activation_id"])) not in bound
        and str(row["state"]) in {"ACTIVE", "DRAINING"}
    ]
    usage = store.account_budget_usage(account_scope_id=scope_id, utc_day=utc_day)
    limits = {key: int(policy[key]) for key in LIMIT_KEYS}
    return {
        "terminal": "ACCOUNT_BUDGET_MANAGED" if not unbound_live else "ACCOUNT_BUDGET_CORRUPT",
        "mode": "MANAGED" if not unbound_live else "CORRUPT",
        "account_scope_id": scope_id,
        "provider_lane": scope["provider_lane"],
        "credential_locator": scope["credential_locator"],
        "commission_sha256": scope["commission_sha256"],
        "commissioned_at": scope["commissioned_at"],
        "policy_revision": int(policy["revision"]),
        "limits": limits,
        "utc_day": utc_day,
        "shared_usage": usage,
        **_remaining(limits, usage),
        "member_count": len(members),
        "members": members,
        "unbound_live_activations": unbound_live,
        "coverage": COVERAGE,
        "next_action": "NONE" if not unbound_live else "RECONCILE_ACCOUNT_BUDGET_BINDING",
    }
