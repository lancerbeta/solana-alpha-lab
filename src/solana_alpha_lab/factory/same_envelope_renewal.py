"""Renew one identical observation envelope by shifting its admission window.

The successor is registered, authorized, and rolled over with
``effective_at`` at the predecessor boundary. ``activate_schedule`` is not
used: that path admits at the current clock.
"""

from __future__ import annotations

import copy
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.collector_read_model import project_activation_as_of
from solana_alpha_lab.factory.observation_schedule import (
    canonical_sha256,
    parse_utc,
    render_utc,
    schedule_from_observation_request,
)
from solana_alpha_lab.factory.observation_schedule_compiler import (
    compile_schedule_document,
)
from solana_alpha_lab.factory.observation_schedule_lifecycle import (
    ObservationLifecycleError,
    _authority_policy,
    _minimum_expiry,
    _used_provider_route_ids,
    authorize_schedule,
    cohort_family_key,
    expected_authority_phrase,
    register_schedule,
    rollover_research_event_proven,
    rollover_schedule,
)
from solana_alpha_lab.factory.observation_schedule_store import (
    ObservationScheduleStore,
    ObservationScheduleStoreError,
)

RENEW_LEAD = timedelta(hours=72)

_SUCCESS_TERMINALS = frozenset({"TOO_EARLY", "ALREADY_PROVEN", "RENEWED"})


def successor_activation_id(schedule_sha256: str) -> str:
    return "ACT-" + schedule_sha256[:16].upper()


def renew_same_envelope(
    *,
    root: Path,
    data_root: Path,
    store: ObservationScheduleStore,
    now: datetime,
    producer_git_sha: str,
    lease_wait_seconds: int = 600,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Return a terminal. Never include the authorize phrase."""

    clock = now.astimezone(now.tzinfo) if now.tzinfo is not None else now
    if clock.tzinfo is None:
        raise ObservationLifecycleError("TIMESTAMP_INVALID")
    predecessor = _single_projected_active(store, clock)
    if predecessor is None:
        return _result("REFUSED_AMBIGUOUS")
    schedule_sha256 = str(predecessor.get("schedule_sha256") or "")
    activation_id = str(predecessor.get("activation_id") or "")
    registered = store.get_registered_schedule(schedule_sha256)
    if registered is None or not activation_id:
        return _result("REFUSED_PROOF", predecessor)
    document = registered["document"]
    try:
        stops = parse_utc(str(document["activation"]["stops_admitting_at"]))
        starts = parse_utc(str(document["activation"]["starts_at"]))
    except (KeyError, TypeError, ValueError):
        return _result("REFUSED_PROOF", predecessor)
    if str(predecessor.get("stops_admitting_at") or "") != str(
        document["activation"]["stops_admitting_at"]
    ):
        return _result("REFUSED_PROOF", predecessor)
    remaining = stops - clock
    if remaining <= timedelta(0):
        return _result("REFUSED_PAST_CUTOVER", predecessor)
    if remaining > RENEW_LEAD:
        return _result("TOO_EARLY", predecessor)
    shifted = _shift_source(document)
    if shifted is None:
        return _result("REFUSED_NOT_PURE_SHIFT", predecessor)
    if not _budgets_match(root, document, shifted):
        return _result("REFUSED_NOT_PURE_SHIFT", predecessor)
    compiled = compile_schedule_document(shifted, root=root)
    if compiled.schedule is None or not compiled.schedule_sha256:
        return _result("REFUSED_NOT_PURE_SHIFT", predecessor)
    successor_sha = str(compiled.schedule_sha256)
    cutover_at = render_utc(stops)
    if _rollover_already_proven(
        store,
        data_root=data_root,
        predecessor_sha=schedule_sha256,
        predecessor_id=activation_id,
        successor_sha=successor_sha,
        cutover_at=cutover_at,
        now=clock,
    ):
        return _result(
            "ALREADY_PROVEN",
            predecessor,
            successor_sha=successor_sha,
            cutover_at=cutover_at,
        )
    token = _acquire_lease(
        store, lease_wait_seconds=lease_wait_seconds, sleep=sleep
    )
    if token is None:
        return _result("REFUSED_PROOF", predecessor, detail="WRITER_BUSY")
    try:
        if store.get_registered_schedule(successor_sha) is None:
            registered_result = register_schedule(
                root=root,
                data_root=data_root,
                store=store,
                document=shifted,
                now=clock,
                producer_git_sha=producer_git_sha,
            )
            if str(registered_result.get("schedule_sha256") or "") != successor_sha:
                return _result("REFUSED_NOT_PURE_SHIFT", predecessor)
        stored = store.get_registered_schedule(successor_sha)
        if stored is None:
            return _result("REFUSED_NOT_PURE_SHIFT", predecessor)
        authorize_schedule(
            root=root,
            data_root=data_root,
            store=store,
            schedule_sha256=successor_sha,
            phrase=_phrase(root, stored["document"]),
            now=clock,
            producer_git_sha=producer_git_sha,
        )
        successor_id = successor_activation_id(successor_sha)
        rollover_schedule(
            root=root,
            data_root=data_root,
            store=store,
            predecessor_schedule_sha256=schedule_sha256,
            predecessor_activation_id=activation_id,
            successor_schedule_sha256=successor_sha,
            successor_activation_id=successor_id,
            cutover_at=cutover_at,
            now=clock,
            producer_git_sha=producer_git_sha,
        )
    except (ObservationLifecycleError, ObservationScheduleStoreError) as exc:
        return _result("REFUSED_PROOF", predecessor, detail=str(exc))
    finally:
        store.release_lease(token)
    return _result(
        "RENEWED",
        predecessor,
        successor_sha=successor_sha,
        cutover_at=cutover_at,
    )


def exit_code(terminal: str) -> int:
    return 0 if terminal in _SUCCESS_TERMINALS else 2


def _result(
    terminal: str,
    predecessor: dict[str, Any] | None = None,
    *,
    successor_sha: str | None = None,
    cutover_at: str | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"terminal": terminal}
    if predecessor is not None:
        payload["predecessor_schedule_sha256"] = str(
            predecessor.get("schedule_sha256") or ""
        )
        payload["predecessor_activation_id"] = str(
            predecessor.get("activation_id") or ""
        )
    if successor_sha is not None:
        payload["successor_schedule_sha256"] = successor_sha
        payload["successor_activation_id"] = successor_activation_id(successor_sha)
    if cutover_at is not None:
        payload["cutover_at"] = cutover_at
    if detail is not None:
        payload["detail"] = detail
    return payload


def _acquire_lease(
    store: ObservationScheduleStore,
    *,
    lease_wait_seconds: int,
    sleep: Callable[[float], None],
) -> str | None:
    """Wait out a live tick. Each attempt uses wall time, not a frozen clock."""

    waited = 0
    while True:
        token = store.acquire_lease("same-envelope-renewal")
        if token is not None:
            return token
        if waited >= lease_wait_seconds:
            return None
        step = min(5, lease_wait_seconds - waited)
        sleep(step)
        waited += step


def _single_projected_active(
    store: ObservationScheduleStore, now: datetime
) -> dict[str, Any] | None:
    found: list[dict[str, Any]] = []
    for row in store.list_activations():
        projected = project_activation_as_of(row, now)
        if str(projected.get("state") or "") == "ACTIVE":
            found.append(dict(row))
    if len(found) != 1:
        return None
    return found[0]


def _shift_source(document: dict[str, Any]) -> dict[str, Any] | None:
    try:
        source = schedule_from_observation_request(document)
        starts = parse_utc(str(source["activation"]["starts_at"]))
        stops = parse_utc(str(source["activation"]["stops_admitting_at"]))
    except (KeyError, TypeError, ValueError):
        return None
    duration = stops - starts
    if duration <= timedelta(0):
        return None
    shifted = copy.deepcopy(source)
    shifted["activation"]["starts_at"] = render_utc(stops)
    shifted["activation"]["stops_admitting_at"] = render_utc(stops + duration)
    shifted.pop("schedule_sha256", None)
    return shifted


def _blank_window(document: dict[str, Any]) -> dict[str, Any]:
    blanked = copy.deepcopy(document)
    blanked.pop("schedule_sha256", None)
    activation = dict(blanked["activation"])
    activation["starts_at"] = "START"
    activation["stops_admitting_at"] = "STOP"
    blanked["activation"] = activation
    return blanked


def _budgets_match(
    root: Path, current: dict[str, Any], shifted: dict[str, Any]
) -> bool:
    current_source = schedule_from_observation_request(current)
    current_source.pop("schedule_sha256", None)
    if _blank_window(current_source) != _blank_window(shifted):
        return False
    left = compile_schedule_document(current_source, root=root)
    right = compile_schedule_document(shifted, root=root)
    if (
        left.schedule is None
        or right.schedule is None
        or left.budget is None
        or right.budget is None
    ):
        return False
    if left.budget != right.budget:
        return False
    try:
        return cohort_family_key(left.schedule) == cohort_family_key(right.schedule)
    except (KeyError, TypeError, ValueError):
        return False


def _phrase(root: Path, document: dict[str, Any]) -> str:
    _primitives, routes = _used_provider_route_ids(root, document)
    del _primitives
    expires_at = render_utc(_minimum_expiry(document))
    policy = _authority_policy(
        root=root,
        document=document,
        schedule_key=str(document["schedule_key"]),
        expires_at=expires_at,
    )
    return expected_authority_phrase(
        schedule_sha256=str(document["schedule_sha256"]),
        schedule_key=str(document["schedule_key"]),
        activation_starts_at=str(document["activation"]["starts_at"]),
        activation_stops_admitting_at=str(document["activation"]["stops_admitting_at"]),
        provider_route_ids=routes,
        expires_at=expires_at,
        policy_digest=canonical_sha256(policy),
    )


def _rollover_already_proven(
    store: ObservationScheduleStore,
    *,
    data_root: Path,
    predecessor_sha: str,
    predecessor_id: str,
    successor_sha: str,
    cutover_at: str,
    now: datetime,
) -> bool:
    successor_id = successor_activation_id(successor_sha)
    predecessor = store.get_activation(predecessor_sha, predecessor_id)
    successor = store.get_activation(successor_sha, successor_id)
    predecessor_document = store.get_registered_schedule(predecessor_sha)
    successor_document = store.get_registered_schedule(successor_sha)
    if (
        predecessor is None
        or successor is None
        or predecessor_document is None
        or successor_document is None
    ):
        return False
    for item in store.list_rollovers():
        if str(item.get("predecessor_schedule_sha256") or "") != predecessor_sha:
            continue
        if str(item.get("predecessor_activation_id") or "") != predecessor_id:
            continue
        if str(item.get("successor_schedule_sha256") or "") != successor_sha:
            continue
        if str(item.get("successor_activation_id") or "") != successor_id:
            continue
        if str(item.get("cutover_at") or "") != cutover_at:
            continue
        if rollover_research_event_proven(
            data_root,
            item=item,
            predecessor_document=predecessor_document["document"],
            successor_document=successor_document["document"],
            now=now,
            predecessor_transition_event_id=str(
                predecessor.get("last_transition_event_id") or ""
            )
            or None,
            successor_transition_event_id=str(
                successor.get("last_transition_event_id") or ""
            )
            or None,
        ):
            return True
    return False
