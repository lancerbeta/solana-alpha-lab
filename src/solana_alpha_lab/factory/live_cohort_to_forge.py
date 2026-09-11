"""Cohort-scoped closure, transport, one-shot publish, and Forge CONTROL readback.

Zero provider calls. Does not pause the collector, rewrite Observation RDP, or
run /hypothesis-forge.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import shutil
import sys
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.discovery_evidence_release import DiscoveryReleaseError
from solana_alpha_lab.factory.early_market_panel_importer import (
    MIN_USABLE_YIELD_ELIGIBLE,
)
from solana_alpha_lab.factory.hfic_preflight import (
    AUTO_FOCUS,
    HficPreflightError,
    _query_hfic_sessions,
    decide_preflight_action,
    enumerate_rdp_datasets,
    evidence_epoch_material,
    is_live_corpus_dataset,
    prove_fast_lane_commissioned,
    select_forge_packet_datasets,
)
from solana_alpha_lab.factory.hfic_control_integrity import (
    CURRENT_REPRESENTATION_CONTROL_V1,
)
from solana_alpha_lab.factory.hfic_memory_policy import effective_policy, quarantined_session_ids
from solana_alpha_lab.factory.hfic_session import (
    PROMPT_VERSION,
    evidence_epoch_sha256,
    focus_key_sha256,
    search_key_sha256,
)
from solana_alpha_lab.factory.hfic_prior_memory import (
    MEMORY_HARD_CLOSE,
    MEMORY_PARK,
    build_prior_memory_snapshot,
)
from solana_alpha_lab.factory.live_cohort_discovery_release import (
    CORPUS_DATASET_ID,
    RELEASE_MANIFEST_NAME,
    LiveCohortReleaseError,
    bound_schedule_from_rdp,
    build_live_observation_source_from_rdp,
    campaign_cohort_windows,
    classify_cohort_admission_clock,
    classify_cohort_readiness,
    cohort_snapshot_path,
    cohort_window_bounds,
    import_live_cohort,
    latest_c1_observation_manifest_at,
    live_cohort_status,
    load_observation_rdp_source,
    release_id_for,
    resolve_cohort_admission_instant,
    seal_live_cohort,
    select_current_datasets_for_forge,
    verify_live_cohort,
)
from solana_alpha_lab.factory.observation_publication_jobs import (
    iter_open_job_paths,
    journal_stats,
)
from solana_alpha_lab.factory.observation_schedule import parse_utc, render_utc
from solana_alpha_lab.factory.research_store import ExistingResearchStoreReader, ResearchStoreError
from solana_alpha_lab.factory.run_passport import canonical_sha256

REQUIRED_PYTHON = "3.13.14"
PROBE_CONTRACT_RELATIVE = "docs/contracts/normalized_trajectory_representation_probe_v1.md"
CONTROL_NEXT = "/hypothesis-forge CURRENT_REPRESENTATION_CONTROL"
BROKEN_SESSION_STATES = frozenset(
    {
        "REVISION_REQUIRED",
        "RUNNER_UP_REVISION_REQUIRED",
        "CRITIC_RESULT_READY",
        "AWAITING_CLASSIFICATION",
        "FROZEN_AWAITING_CRITIC",
        "REVISED_AWAITING_CRITIC",
        "RUNNER_UP_AWAITING_CRITIC",
    }
)
_OPEN_DUE = frozenset({"PENDING", "DUE", "CLAIMED"})
_IN_FLIGHT = frozenset({"CLAIMED", "IN_FLIGHT", "IN_FLIGHT_CALL_INDETERMINATE"})
_SAMPLED = frozenset({"ADMITTED", "SAMPLED_MEMBER", "X_ELIGIBLE", "X_POPULATION_INELIGIBLE"})
_ADMISSION_REQUIRED_STATES = _SAMPLED | frozenset(
    {
        "NOT_SELECTED_HASH_SAMPLE",
        "NOT_SELECTED_CAPACITY",
        "NOT_SELECTED_PREDICATE",
        "ANCHOR_UNKNOWN",
    }
)
_CLOSURE_IDENTITY_KEYS = (
    "schema",
    "schema_version",
    "schedule_sha256",
    "activation_id",
    "cohort_id",
    "window_start",
    "window_end_exclusive",
    "members_total",
    "entity_ids",
    "member_identity_sha256",
    "due_states",
    "pending_due_for_cohort",
    "pending_future",
    "claimed_or_in_flight",
    "deadline_missed",
    "budget_blocked",
    "cohort_open_count",
    "ambiguous_open_count",
    "open_publication",
    "closure_cutoff_at",
    "unresolved_due",
    "in_flight",
)

RELEASE_FILES = (
    "release_manifest.json",
    "source_inventory.json",
    "census.parquet",
    "observations.parquet",
)
SEALED_RELEASES_DIRNAME = "live_cohort_releases"


def default_sealed_release_root(observation_rdp: Path, cohort_id: str) -> Path:
    """Durable sealed tree: sibling of Observation RDP, never process-owned temp."""
    return Path(observation_rdp).resolve().parent / SEALED_RELEASES_DIRNAME / cohort_id


class LiveCohortToForgeError(LiveCohortReleaseError):
    """Typed one-shot / readback failures."""


def resolve_operator_path(repo_root: Path, value: str | Path) -> Path:
    """Resolve relative operator paths against the repository root."""
    path = Path(value)
    if not path.is_absolute():
        path = (Path(repo_root) / path)
    try:
        return path.resolve()
    except OSError as exc:
        raise LiveCohortToForgeError("PATH_UNRESOLVABLE") from exc


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return parse_utc(value)
    except Exception:
        return None


def _require(cond: bool, code: str) -> None:
    if not cond:
        raise LiveCohortToForgeError(code)


def hash_release_tree(release_root: Path) -> dict[str, str]:
    root = Path(release_root)
    out: dict[str, str] = {}
    for name in RELEASE_FILES:
        path = root / name
        _require(path.is_file() and not path.is_symlink(), "RELEASE_TREE_INCOMPLETE")
        out[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def verify_transported_release(*, source_root: Path, dest_root: Path) -> dict[str, str]:
    """Copy sealed bytes then require identical content hashes on dest."""
    src = Path(source_root)
    dest = Path(dest_root)
    dest.mkdir(parents=True, exist_ok=True)
    source_hashes = hash_release_tree(src)
    for name in RELEASE_FILES:
        shutil.copy2(src / name, dest / name)
    dest_hashes = hash_release_tree(dest)
    _require(source_hashes == dest_hashes, "TRANSPORT_HASH_MISMATCH")
    verify_live_cohort(dest)
    return dest_hashes


def _candidate_admission(payload: Mapping[str, Any]) -> datetime | None:
    return resolve_cohort_admission_instant(payload)


def _job_in_cohort(job: Mapping[str, Any], *, start: datetime, end: datetime) -> bool | None:
    members = job.get("members")
    if not isinstance(members, list) or not members:
        return None
    hits = 0
    known = 0
    for row in members:
        if not isinstance(row, Mapping):
            continue
        admission = resolve_cohort_admission_instant(row)
        if admission is None:
            continue
        known += 1
        if start <= admission < end:
            hits += 1
    if known == 0:
        return None
    return hits > 0


def _member_identity_sha256(rows: Sequence[tuple[str, str, str]]) -> str:
    payload = {
        "members": [
            {"entity_id": entity_id, "state": state, "admission_at": admission}
            for entity_id, state, admission in sorted(rows)
        ]
    }
    return canonical_sha256(payload)


def collect_open_publication(
    observation_rdp: Path,
    *,
    schedule_sha256: str,
    activation_id: str,
    window_start: datetime,
    window_end: datetime,
) -> dict[str, Any]:
    stats = journal_stats(observation_rdp)
    open_total = int(stats.get("publication_jobs_open_count") or 0)
    cohort_open = 0
    ambiguous = 0
    for path in iter_open_job_paths(observation_rdp):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            ambiguous += 1
            continue
        if not isinstance(job, dict):
            ambiguous += 1
            continue
        if str(job.get("schedule_sha256") or "") != schedule_sha256:
            continue
        act = job.get("activation_id")
        if act not in {None, activation_id}:
            continue
        scoped = _job_in_cohort(job, start=window_start, end=window_end)
        if scoped is True:
            cohort_open += 1
        elif scoped is None:
            ambiguous += 1
    return {
        "publication_jobs_open_count": open_total,
        "cohort_open_count": cohort_open,
        "ambiguous_open_count": ambiguous,
        "open_publication": bool(cohort_open or ambiguous),
    }


def build_closure_receipt(
    *,
    ops_store: Path,
    observation_rdp: Path,
    schedule_sha256: str,
    activation_id: str,
    cohort_id: str,
    as_of: datetime,
) -> dict[str, Any]:
    """Cohort-scoped operational closure evidence from SQLite + publication jobs."""
    as_of = as_of.astimezone(UTC)
    start, end = cohort_window_bounds(cohort_id)
    mature_at = end + timedelta(seconds=86400)
    path = Path(ops_store)
    _require(path.is_file() and not path.is_symlink(), "CLOSED_RECEIPT_STORE_MISSING")
    conn = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        _require(integrity == "ok", "CLOSED_RECEIPT_SQLITE_CORRUPT")
        candidates = conn.execute(
            """
            SELECT entity_id, state, payload_json
            FROM candidate_members
            WHERE schedule_sha256 = ? AND activation_id = ?
            """,
            (schedule_sha256, activation_id),
        ).fetchall()
        cohort_entities: set[str] = set()
        member_states: Counter[str] = Counter()
        member_identity_rows: list[tuple[str, str, str]] = []
        admission_invalid = 0
        admission_missing_sampled = 0
        for row in candidates:
            payload = json.loads(row["payload_json"] or "{}")
            clock_status = classify_cohort_admission_clock(payload)
            state = str(row["state"])
            if clock_status == "invalid":
                admission_invalid += 1
                continue
            if clock_status == "missing":
                if state in _ADMISSION_REQUIRED_STATES:
                    admission_missing_sampled += 1
                continue
            admission = _candidate_admission(payload)
            if admission is None or not (start <= admission < end):
                continue
            entity_id = str(row["entity_id"])
            cohort_entities.add(entity_id)
            member_identity_rows.append((entity_id, state, render_utc(admission)))
            member_states[state] += 1
        due_states: Counter[str] = Counter()
        pending_due_by_mature = 0
        pending_future = 0
        claimed_or_in_flight = 0
        actually_overdue = 0
        deadline_missed = 0
        budget_blocked = 0
        cutoff = mature_at
        dues = conn.execute(
            """
            SELECT entity_id, point_id, state, due_at, deadline_at, updated_at
            FROM due_observations
            WHERE schedule_sha256 = ? AND activation_id = ?
            """,
            (schedule_sha256, activation_id),
        ).fetchall()
        for row in dues:
            if str(row["entity_id"]) not in cohort_entities:
                continue
            state = str(row["state"])
            due_states[state] += 1
            due_at = _parse_utc(row["due_at"])
            if state == "CENSORED_LATE":
                deadline_missed += 1
            if state in _IN_FLIGHT:
                claimed_or_in_flight += 1
            if state == "BLOCKED_BUDGET":
                budget_blocked += 1
            if state in _OPEN_DUE and due_at is not None:
                if due_at <= mature_at:
                    pending_due_by_mature += 1
                else:
                    pending_future += 1
                if due_at <= as_of:
                    actually_overdue += 1
            updated = _parse_utc(row["updated_at"])
            if (
                updated is not None
                and state not in _OPEN_DUE
                and state not in _IN_FLIGHT
                and updated > cutoff
            ):
                cutoff = updated
    finally:
        conn.close()
    horizon = latest_c1_observation_manifest_at(
        observation_rdp,
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        cohort_mints=cohort_entities,
        not_after=as_of,
    )
    if horizon is not None and horizon > cutoff:
        cutoff = horizon
    publication = collect_open_publication(
        observation_rdp,
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        window_start=start,
        window_end=end,
    )
    body = {
        "schema": "smial.live-cohort-closure-receipt",
        "schema_version": "1.0",
        "schedule_sha256": schedule_sha256,
        "activation_id": activation_id,
        "cohort_id": cohort_id,
        "as_of": render_utc(as_of),
        "window_start": render_utc(start),
        "window_end_exclusive": render_utc(end),
        "mature_at": render_utc(mature_at),
        "now_ge_mature_at": as_of >= mature_at,
        "members_total": len(cohort_entities),
        "entity_ids": sorted(cohort_entities),
        "member_identity_sha256": _member_identity_sha256(member_identity_rows),
        "admission_clock_invalid_count": admission_invalid,
        "admission_clock_missing_sampled_count": admission_missing_sampled,
        "member_states": dict(member_states),
        "due_states": dict(due_states),
        "pending_due_for_cohort": pending_due_by_mature,
        "pending_future": pending_future,
        "claimed_or_in_flight": claimed_or_in_flight,
        "actually_overdue": actually_overdue,
        "deadline_missed": deadline_missed,
        "budget_blocked": budget_blocked > 0,
        "publication_jobs_open_count": publication["publication_jobs_open_count"],
        "cohort_open_count": publication["cohort_open_count"],
        "ambiguous_open_count": publication["ambiguous_open_count"],
        "open_publication": publication["open_publication"],
        "closure_cutoff_at": render_utc(cutoff),
        "unresolved_due": pending_due_by_mature > 0,
        "in_flight": claimed_or_in_flight > 0,
    }
    return _attach_closure_hashes(body)


def _attach_closure_hashes(body: dict[str, Any]) -> dict[str, Any]:
    identity = {key: body[key] for key in _CLOSURE_IDENTITY_KEYS}
    body["closure_identity_sha256"] = canonical_sha256(identity)
    hashed = {key: value for key, value in body.items() if key != "receipt_sha256"}
    body["receipt_sha256"] = canonical_sha256(hashed)
    return body


def assert_closure_ready(receipt: Mapping[str, Any]) -> None:
    _require("now_ge_mature_at" in receipt, "CLOSED_RECEIPT_INCOMPLETE")
    _require(bool(receipt.get("now_ge_mature_at")), "NOT_MATURE")
    _require("members_total" in receipt, "CLOSED_RECEIPT_INCOMPLETE")
    _require(int(receipt["members_total"]) > 0, "CLOSED_RECEIPT_INCOMPLETE")
    invalid_count = receipt.get("admission_clock_invalid_count")
    missing_count = receipt.get("admission_clock_missing_sampled_count")
    _require(type(invalid_count) is int, "CLOSED_RECEIPT_INCOMPLETE")
    _require(type(missing_count) is int, "CLOSED_RECEIPT_INCOMPLETE")
    _require(invalid_count == 0, "ADMISSION_CLOCK_INVALID")
    _require(missing_count == 0, "ADMISSION_CLOCK_MISSING")
    _require(isinstance(receipt.get("due_states"), dict), "CLOSED_RECEIPT_INCOMPLETE")
    due_total = sum(int(v) for v in receipt["due_states"].values())
    _require(due_total > 0, "CLOSED_RECEIPT_INCOMPLETE")
    for key in (
        "pending_due_for_cohort",
        "claimed_or_in_flight",
        "open_publication",
        "in_flight",
        "budget_blocked",
    ):
        _require(key in receipt, "CLOSED_RECEIPT_INCOMPLETE")
    _require(int(receipt["pending_due_for_cohort"]) == 0, "COHORT_DUE_OPEN")
    _require(int(receipt.get("pending_future") or 0) == 0, "COHORT_PENDING_FUTURE")
    _require(int(receipt["claimed_or_in_flight"]) == 0, "COHORT_DUE_OPEN")
    _require(receipt["in_flight"] is False, "COHORT_DUE_OPEN")
    _require(receipt["open_publication"] is False, "PUBLICATION_OPEN")
    _require(receipt["budget_blocked"] is False, "RELEASE_BLOCKED_BUDGET")


def assert_source_matches_receipt(
    source: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> None:
    source_mints = sorted(
        str(item.get("mint") or "")
        for item in (source.get("members") or [])
        if isinstance(item, Mapping)
    )
    receipt_ids = sorted(str(item) for item in (receipt.get("entity_ids") or []))
    _require(source_mints == receipt_ids, "CLOSED_RECEIPT_INCOMPLETE")
    _require(
        len(source.get("members") or []) == int(receipt["members_total"]),
        "CLOSED_RECEIPT_INCOMPLETE",
    )
    _require(
        str(source.get("closure_cutoff_at") or "") == str(receipt.get("closure_cutoff_at") or ""),
        "CLOSED_RECEIPT_INCOMPLETE",
    )
    start = parse_utc(str(receipt.get("window_start") or ""))
    end = parse_utc(str(receipt.get("window_end_exclusive") or ""))
    identity_rows: list[tuple[str, str, str]] = []
    for item in source.get("members") or []:
        if not isinstance(item, Mapping):
            continue
        admission = resolve_cohort_admission_instant(item)
        _require(admission is not None, "CLOSED_RECEIPT_INCOMPLETE")
        _require(start <= admission < end, "C2_ROW_IN_C1")
        identity_rows.append(
            (
                str(item.get("mint") or ""),
                str(item.get("candidate_state") or ""),
                render_utc(admission),
            )
        )
    _require(
        str(source.get("closure_receipt_sha256") or "")
        == str(receipt.get("closure_identity_sha256") or receipt.get("receipt_sha256") or ""),
        "CLOSED_RECEIPT_INCOMPLETE",
    )
    source_identity = _member_identity_sha256(identity_rows)
    _require(
        source_identity == str(receipt.get("member_identity_sha256") or ""),
        "STALE_MEMBER_STATE",
    )


def _imported_cohort_ids(data_root: Path | None) -> set[str]:
    if data_root is None:
        return set()
    lineage_path = Path(data_root) / "datasets" / "live_lifecycle_corpus" / "lineage.json"
    if not lineage_path.is_file():
        return set()
    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    return {
        str(item.get("cohort_id"))
        for item in (lineage.get("cohorts") or [])
        if isinstance(item, Mapping) and item.get("cohort_id")
    }


def list_live_cohorts(
    *,
    observation_rdp: Path,
    ops_store: Path,
    schedule_sha256: str,
    activation_id: str,
    data_root: Path | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """Read-only campaign windows, closure, and next mature unimported cohort."""
    now = (as_of or datetime.now(tz=UTC)).astimezone(UTC)
    schedule_doc, _, _ = bound_schedule_from_rdp(
        Path(observation_rdp),
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
    )
    activation = schedule_doc.get("activation")
    _require(isinstance(activation, Mapping), "LIVE_SOURCE_ACTIVATION_MISSING")
    starts = parse_utc(str(activation.get("starts_at") or ""))
    stops = parse_utc(str(activation.get("stops_at") or activation.get("stops_admitting_at") or ""))
    imported = _imported_cohort_ids(data_root)
    rows: list[dict[str, Any]] = []
    next_id = None
    for cohort_id, start, end in campaign_cohort_windows(starts, stops):
        receipt = build_closure_receipt(
            ops_store=ops_store,
            observation_rdp=observation_rdp,
            schedule_sha256=schedule_sha256,
            activation_id=activation_id,
            cohort_id=cohort_id,
            as_of=now,
        )
        mature = bool(receipt.get("now_ge_mature_at"))
        imported_flag = cohort_id in imported
        blocked = None
        if mature and not imported_flag:
            try:
                assert_closure_ready(receipt)
            except (LiveCohortReleaseError, DiscoveryReleaseError) as exc:
                blocked = str(exc)
        rows.append(
            {
                "cohort_id": cohort_id,
                "window_start": render_utc(start),
                "window_end_exclusive": render_utc(end),
                "mature": mature,
                "imported": imported_flag,
                "members_total": receipt.get("members_total"),
                "blocker": blocked,
            }
        )
        if next_id is None and mature and not imported_flag and blocked is None:
            next_id = cohort_id
    return {
        "schedule_sha256": schedule_sha256,
        "activation_id": activation_id,
        "cohorts": rows,
        "next_unimported_mature": next_id,
    }


def python_runtime_ok() -> bool:
    actual = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return actual == REQUIRED_PYTHON


def forge_control_ready(
    *,
    data_root: Path,
    repo_root: Path,
    imported_cohort_id: str | None = None,
) -> dict[str, Any]:
    """Read-only Forge CONTROL readiness. Does not invoke /hypothesis-forge."""
    _require(python_runtime_ok(), "HFIC_RUNTIME_PYTHON_VERSION_INCOMPATIBLE")
    probe = Path(repo_root) / PROBE_CONTRACT_RELATIVE
    _require(probe.is_file(), "CONTROL_PROBE_CONTRACT_MISSING")
    datasets, warnings = enumerate_rdp_datasets(Path(data_root))
    bounded, trunc = select_forge_packet_datasets(
        datasets,
        evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1,
    )
    current = [item for item in bounded if is_live_corpus_dataset(item)]
    if not current:
        all_current = [
            item
            for item in select_current_datasets_for_forge(datasets)
            if is_live_corpus_dataset(item)
        ]
        _require(not all_current, "CURRENT_CORPUS_EXCLUDED_FROM_CONTROL_PACKET")
        _require(False, "CURRENT_CORPUS_MISSING")
    chosen = current[0]
    labels = dict(chosen.get("labels") or {})
    if imported_cohort_id:
        lineage_path = Path(data_root) / "datasets" / "live_lifecycle_corpus" / "lineage.json"
        _require(lineage_path.is_file(), "CORPUS_LINEAGE_INCOMPLETE")
        lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
        ids = [
            str(c.get("cohort_id"))
            for c in (lineage.get("cohorts") or [])
            if isinstance(c, Mapping)
        ]
        _require(imported_cohort_id in ids, "IMPORTED_COHORT_MISSING")
        current_mid = str(lineage.get("current_dataset_manifest_id") or "")
        _require(bool(current_mid), "CORPUS_LINEAGE_INCOMPLETE")
        _require(
            str(chosen.get("dataset_manifest_id") or "") == current_mid,
            "CONTROL_CORPUS_MANIFEST_MISMATCH",
        )
    else:
        lineage_path = Path(data_root) / "datasets" / "live_lifecycle_corpus" / "lineage.json"
        if lineage_path.is_file():
            lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
            current_mid = str(lineage.get("current_dataset_manifest_id") or "")
            if current_mid:
                _require(
                    str(chosen.get("dataset_manifest_id") or "") == current_mid,
                    "CONTROL_CORPUS_MANIFEST_MISMATCH",
                )
    yield_eligible = int(labels.get("yield_eligible") or chosen.get("yield_eligible") or 0)
    coverage = str(labels.get("discovery_coverage_class") or "")
    _require(coverage != "GAP_CONFIRMED", "COVERAGE_CONFIRMED_BROKEN")
    _require(yield_eligible >= MIN_USABLE_YIELD_ELIGIBLE, "LOW_YIELD")
    material = evidence_epoch_material(repo_root=repo_root, data_root=data_root)
    epoch = evidence_epoch_sha256(material)
    sessions = _query_hfic_sessions(Path(data_root))
    blocking = [
        item
        for item in sessions
        if str(item.get("session_state") or "") in BROKEN_SESSION_STATES
        and str(item.get("evidence_epoch_sha256") or "") == epoch
    ]
    _require(not blocking, "HFIC_SESSION_BLOCKED")
    store: ExistingResearchStoreReader | None
    try:
        store = ExistingResearchStoreReader(Path(data_root))
    except ResearchStoreError:
        store = None
        prior = {"capsules": [], "eligible_count": 0}
        blocked = set()
    else:
        prior = build_prior_memory_snapshot(
            store,
            store_inventory_digest=str(material.get("store_inventory_digest") or "0" * 64),
            repo_root=repo_root,
        )
        blocked = set(quarantined_session_ids(store))
    for capsule in prior.get("capsules") or []:
        if not isinstance(capsule, Mapping):
            continue
        session_id = capsule.get("session_id")
        if isinstance(session_id, str) and session_id:
            _require(session_id not in blocked, "QUARANTINED_MEMORY_ELIGIBLE")
        status = str(capsule.get("memory_status") or "")
        _require(status not in {MEMORY_HARD_CLOSE, MEMORY_PARK}, "QUARANTINED_MEMORY_ELIGIBLE")
    try:
        prove_fast_lane_commissioned(Path(data_root))
    except HficPreflightError as exc:
        raise LiveCohortToForgeError(str(exc) or "FAST_LANE_NOT_COMMISSIONED") from exc
    policy_head = effective_policy(store)
    focus = AUTO_FOCUS
    focus_key = focus_key_sha256(focus)
    memory_eligibility = str(policy_head.get("memory_eligibility_sha256") or "0" * 64)
    search_key = search_key_sha256(
        epoch, focus, PROMPT_VERSION, memory_eligibility, CURRENT_REPRESENTATION_CONTROL_V1
    )
    action, _bound = decide_preflight_action(
        sessions,
        search_key=search_key,
        evidence_epoch=epoch,
        focus_key=focus_key,
        owner_focus=focus,
        memory_eligibility_sha256=memory_eligibility,
        evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1,
    )
    _require(action != "STOP", "SEARCH_BUDGET_EXHAUSTED")
    _require(
        action
        in {
            "START_NEW_SESSION",
            "RESUME_FINALIZE",
            "RESUME_REVISE",
            "RESUME_CLASSIFY",
            "RESUME_CRITIC",
            "RETURN_EXISTING_SESSION",
        },
        "CONTROL_SESSION_NOT_ENTERABLE",
    )
    return {
        "terminal": "FORGE_CONTROL_READY",
        "dataset_id": CORPUS_DATASET_ID,
        "dataset_manifest_id": chosen.get("dataset_manifest_id"),
        "dataset_version": chosen.get("dataset_version") or labels.get("dataset_version"),
        "corpus_version": labels.get("corpus_version"),
        "yield_eligible": yield_eligible,
        "min_usable_yield_eligible": MIN_USABLE_YIELD_ELIGIBLE,
        "evidence_epoch_sha256": epoch,
        "discovery_coverage_class": coverage or None,
        "enumerate_warnings": list(warnings),
        "next": CONTROL_NEXT,
        "control_run_required_first": True,
        "normalized_trajectory_executed": False,
        "live_corpus_in_packet": bool(trunc.get("live_corpus_in_packet")),
        "control_search_action": action,
        "bounded_dataset_count": len(bounded),
    }


def publish_live_cohort(
    *,
    repo_root: Path,
    observation_rdp: Path,
    ops_store: Path,
    schedule_sha256: str,
    activation_id: str,
    cohort_id: str | None = None,
    data_root: Path,
    release_root: Path | None = None,
    as_of: datetime | None = None,
    release_builder_git_sha: str | None = None,
    discovery_coverage_class: str | None = None,
) -> dict[str, Any]:
    """One bounded owner path: mature cohort → verified import → Forge CONTROL."""
    now = (as_of or datetime.now(tz=UTC)).astimezone(UTC)
    observation_rdp = Path(observation_rdp)
    ops_store = Path(ops_store)
    data_root = Path(data_root)
    try:
        if not cohort_id:
            listed = list_live_cohorts(
                observation_rdp=observation_rdp,
                ops_store=ops_store,
                schedule_sha256=schedule_sha256,
                activation_id=activation_id,
                data_root=data_root,
                as_of=now,
            )
            cohort_id = listed.get("next_unimported_mature")
            if not cohort_id:
                for row in listed.get("cohorts") or []:
                    if row.get("mature") and not row.get("imported") and row.get("blocker"):
                        raise LiveCohortToForgeError(str(row["blocker"]))
                raise LiveCohortToForgeError("NOT_MATURE")
        return _publish_live_cohort_inner(
            repo_root=repo_root,
            observation_rdp=observation_rdp,
            ops_store=ops_store,
            schedule_sha256=schedule_sha256,
            activation_id=activation_id,
            cohort_id=cohort_id,
            data_root=data_root,
            release_root=release_root,
            now=now,
            release_builder_git_sha=release_builder_git_sha,
            discovery_coverage_class=discovery_coverage_class,
        )
    except (LiveCohortReleaseError, DiscoveryReleaseError) as exc:
        mapped = {
            "COHORT_ALREADY_IMPORTED": "IMPORT_CONFLICT",
            "CANONICAL_TARGET_CONFLICT": "IMPORT_CONFLICT",
            "LIVE_SOURCE_ACTIVATION_MISSING": "IDENTITY_CONFLICT",
            "LIVE_SOURCE_ACTIVATION_MISMATCH": "IDENTITY_CONFLICT",
            "CLOSED_RECEIPT_IDENTITY_MISMATCH": "IDENTITY_CONFLICT",
        }.get(str(exc), str(exc))
        raise LiveCohortToForgeError(mapped) from exc


def _publish_live_cohort_inner(
    *,
    repo_root: Path,
    observation_rdp: Path,
    ops_store: Path,
    schedule_sha256: str,
    activation_id: str,
    cohort_id: str,
    data_root: Path,
    release_root: Path | None,
    now: datetime,
    release_builder_git_sha: str | None,
    discovery_coverage_class: str | None = None,
) -> dict[str, Any]:
    receipt = build_closure_receipt(
        ops_store=ops_store,
        observation_rdp=observation_rdp,
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        cohort_id=cohort_id,
        as_of=now,
    )
    assert_closure_ready(receipt)
    epoch_before = None
    if (Path(data_root) / "datasets" / "manifests").exists():
        try:
            epoch_before = evidence_epoch_sha256(
                evidence_epoch_material(repo_root=repo_root, data_root=data_root)
            )
        except Exception:
            epoch_before = None
    source = build_live_observation_source_from_rdp(
        observation_rdp_root=observation_rdp,
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        cohort_id=cohort_id,
        as_of=now,
        closure_receipt=receipt,
        discovery_coverage_class=discovery_coverage_class,
    )
    status = live_cohort_status(
        observation_rdp_root=observation_rdp,
        cohort_id=cohort_id,
        as_of=now,
    )
    readiness = status["readiness"]
    state = str(readiness.get("state") or "")
    if state == "NOT_MATURE" or state == "MATURING" or state == "COLLECTING":
        raise LiveCohortToForgeError("NOT_MATURE" if state != "COLLECTING" else "NOT_MATURE")
    if state == "COVERAGE_CONFIRMED_BROKEN":
        raise LiveCohortToForgeError("COVERAGE_CONFIRMED_BROKEN")
    if state == "READY_LOW_YIELD":
        raise LiveCohortToForgeError("LOW_YIELD")
    if state not in {"READY_VALID", "READY_VALID_WITH_COVERAGE_LIMITATION"}:
        raise LiveCohortToForgeError(state)
    assert_source_matches_receipt(source, receipt)
    this_yield = int((readiness.get("denominator") or {}).get("observed") or 0)
    already_imported = False
    current_yield = 0
    lineage_path = Path(data_root) / "datasets" / "live_lifecycle_corpus" / "lineage.json"
    if lineage_path.is_file():
        lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
        cohorts = [
            item
            for item in (lineage.get("cohorts") or [])
            if isinstance(item, Mapping)
        ]
        already_imported = any(str(item.get("cohort_id")) == cohort_id for item in cohorts)
        current_yield = sum(int(item.get("yield_eligible") or 0) for item in cohorts)
    if not already_imported and current_yield + this_yield < MIN_USABLE_YIELD_ELIGIBLE:
        raise LiveCohortToForgeError("LOW_YIELD")
    sealed_root = (
        Path(release_root)
        if release_root is not None
        else default_sealed_release_root(observation_rdp, cohort_id)
    )
    transport_dir = None
    try:
        manifest = _reuse_or_seal_release(
            observation_rdp=observation_rdp,
            cohort_id=cohort_id,
            source=source,
            sealed_root=sealed_root,
            now=now,
            release_builder_git_sha=release_builder_git_sha,
        )
        verify_live_cohort(sealed_root)
        transport_dir = Path(tempfile.mkdtemp(prefix="live-cohort-transport-"))
        verify_transported_release(source_root=sealed_root, dest_root=transport_dir)
        imported = import_live_cohort(
            release_root=transport_dir,
            data_root=data_root,
            import_time=now,
        )
        epoch_after = evidence_epoch_sha256(
            evidence_epoch_material(repo_root=repo_root, data_root=data_root)
        )
        if imported.get("status") == "IDEMPOTENT_REIMPORT":
            _require(epoch_before is None or epoch_after == epoch_before, "EPOCH_BUMP_ON_REIMPORT")
        else:
            _require(epoch_before is None or epoch_after != epoch_before, "EVIDENCE_EPOCH_UNCHANGED")
        control = forge_control_ready(
            data_root=data_root,
            repo_root=repo_root,
            imported_cohort_id=cohort_id,
        )
        return {
            "terminal": "LIVE_COHORT_PUBLISHED_TO_FORGE",
            "cohort_id": cohort_id,
            "release_id": manifest.get("release_id"),
            "sealed_release_root": str(sealed_root.as_posix()),
            "import": imported,
            "source_sha256": source.get("source_sha256"),
            "closure_receipt_sha256": receipt.get("closure_identity_sha256"),
            "readiness": readiness,
            "epoch_before": epoch_before,
            "epoch_after": epoch_after,
            "forge": control,
            "next": CONTROL_NEXT,
            "snapshot": str(cohort_snapshot_path(observation_rdp, cohort_id).as_posix()),
        }
    finally:
        if transport_dir is not None:
            shutil.rmtree(transport_dir, ignore_errors=True)


def _reuse_or_seal_release(
    *,
    observation_rdp: Path,
    cohort_id: str,
    source: Mapping[str, Any],
    sealed_root: Path,
    now: datetime,
    release_builder_git_sha: str | None,
) -> dict[str, Any]:
    """Keep an existing same-identity sealed tree; do not rewrite sealed_at."""
    expected_id = release_id_for(source, cohort_id)
    manifest_path = Path(sealed_root) / RELEASE_MANIFEST_NAME
    if manifest_path.is_file():
        existing = verify_live_cohort(sealed_root)
        if (
            existing.get("release_id") == expected_id
            and existing.get("source_sha256") == source.get("source_sha256")
            and existing.get("cohort_id") == cohort_id
        ):
            return existing
        raise LiveCohortToForgeError("IDENTITY_CONFLICT")
    return seal_live_cohort(
        observation_rdp_root=observation_rdp,
        cohort_id=cohort_id,
        release_root=sealed_root,
        sealed_at=now,
        as_of=now,
        release_builder_git_sha=release_builder_git_sha,
    )


def synthetic_closed_receipt(
    *,
    schedule_sha256: str,
    activation_id: str,
    cohort_id: str,
    as_of: datetime,
    members_total: int = 10,
) -> dict[str, Any]:
    start, end = cohort_window_bounds(cohort_id)
    mature_at = end + timedelta(seconds=86400)
    body = {
        "schema": "smial.live-cohort-closure-receipt",
        "schema_version": "1.0",
        "schedule_sha256": schedule_sha256,
        "activation_id": activation_id,
        "cohort_id": cohort_id,
        "as_of": render_utc(as_of.astimezone(UTC)),
        "window_start": render_utc(start),
        "window_end_exclusive": render_utc(end),
        "mature_at": render_utc(mature_at),
        "now_ge_mature_at": as_of.astimezone(UTC) >= mature_at,
        "members_total": members_total,
        "entity_ids": [],
        "member_identity_sha256": _member_identity_sha256([]),
        "admission_clock_invalid_count": 0,
        "admission_clock_missing_sampled_count": 0,
        "member_states": {},
        "due_states": {},
        "pending_due_for_cohort": 0,
        "pending_future": 0,
        "claimed_or_in_flight": 0,
        "actually_overdue": 0,
        "deadline_missed": 0,
        "budget_blocked": False,
        "publication_jobs_open_count": 0,
        "cohort_open_count": 0,
        "ambiguous_open_count": 0,
        "open_publication": False,
        "closure_cutoff_at": render_utc(mature_at),
        "unresolved_due": False,
        "in_flight": False,
    }
    return _attach_closure_hashes(body)


__all__ = [
    "CONTROL_NEXT",
    "SEALED_RELEASES_DIRNAME",
    "LiveCohortToForgeError",
    "assert_closure_ready",
    "assert_source_matches_receipt",
    "build_closure_receipt",
    "default_sealed_release_root",
    "forge_control_ready",
    "hash_release_tree",
    "publish_live_cohort",
    "list_live_cohorts",
    "resolve_operator_path",
    "synthetic_closed_receipt",
    "verify_transported_release",
]
