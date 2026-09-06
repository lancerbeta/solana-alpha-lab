"""One machine-readable collector operational packet.

Composes ObservationSchedule collector truth, remote-ops health/backup/disk,
and live-release readiness. Does not own a second monitoring platform.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from solana_alpha_lab.factory.collector_read_model import build_collector_read_model
from solana_alpha_lab.factory.due_pressure import backlog_risk_from_due_pressure
from solana_alpha_lab.factory.hot90_activation import load_hot90_activation
from solana_alpha_lab.factory.hot90_closed_day_loop import archive_backlog, read_receipt
from solana_alpha_lab.factory.hot90_mutable_backup import mutable_backup_sources
from solana_alpha_lab.factory.hot90_storage_admission import project_storage_runway
from solana_alpha_lab.factory.live_cohort_discovery_release import (
    CORPUS_DATASET_ID,
    load_observation_rdp_source,
)
from solana_alpha_lab.factory.observation_publication_jobs import (
    journal_stats,
    project_7d_disk_used,
    rdp_bytes_excluding_publication_jobs,
)
from solana_alpha_lab.factory.observation_schedule import parse_utc, render_utc
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
from solana_alpha_lab.factory.offhost_backup import offhost_health_snapshot
from solana_alpha_lab.factory.remote_ops import (
    _backup_newest,
    _disk_used_percent,
    backup_domain_for,
    load_config,
    resolve_backup_sink,
)

UNKNOWN = "UNKNOWN"
NOT_APPLICABLE = "NOT_APPLICABLE"

DISK_WARNING_EARLY_PCT = 70
DISK_WARNING_PCT = 80
DISK_CRITICAL_PCT = 85  # hard safety reference; matches remote-ops max

STORAGE_HISTORY_RELATIVE = "local/factory_v1/collector_storage_history.jsonl"

HEALTH_CLASSES = (
    "PROCESS_OK",
    "DATA_STALE",
    "PROVIDER_AUTH_FAILED",
    "PROVIDER_RATE_LIMITED",
    "PROVIDER_FAILED",
    "DISCOVERY_GAP",
    "DISCOVERY_COVERAGE_UNKNOWN",
    "BACKLOG_RISK",
    "BUDGET_BLOCKED",
    "RDP_PUBLICATION_STALE",
    "BACKUP_DEGRADED",
    "OFFHOST_BACKUP_STALE",
    "OFFHOST_BACKUP_FAILED",
    "IMMUTABLE_ARCHIVE_STALE",
    "IMMUTABLE_ARCHIVE_HASH_MISMATCH",
    "MUTABLE_BACKUP_FULL_RDP_UNEXPECTED",
    "DISK_WARNING",
    "DISK_CRITICAL",
    "DISK_RUNWAY_TARGET40",
    "DISK_RUNWAY_HARD50",
    "RELEASE_BLOCKED",
)


def _safe_parse(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return parse_utc(raw)
    except Exception:
        return None


def _tree_bytes(path: Path) -> int | None:
    if not path.exists():
        return None
    if path.is_file():
        try:
            return int(path.stat().st_size)
        except OSError:
            return None
    total = 0
    try:
        for child in path.rglob("*"):
            if child.is_file() and not child.is_symlink():
                try:
                    total += int(child.stat().st_size)
                except OSError:
                    continue
    except OSError:
        return None
    return total


def _newest_publish_at(observation_rdp: Path) -> str | None:
    markers = list(observation_rdp.glob("datasets/manifests/*.published"))
    if not markers:
        return None
    newest = max(markers, key=lambda p: p.stat().st_mtime)
    return (
        datetime.fromtimestamp(newest.stat().st_mtime, UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _disk_free_bytes(path: Path) -> int | None:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    return int(usage.free)


def _load_storage_history(root: Path) -> list[dict[str, Any]]:
    path = root / STORAGE_HISTORY_RELATIVE
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            loaded = json.loads(line)
            if isinstance(loaded, dict):
                rows.append(loaded)
    except (OSError, json.JSONDecodeError):
        return []
    return rows


def append_storage_history(
    root: Path,
    *,
    observed_at: str,
    disk_used_pct: int | None,
    sqlite_bytes: int | None,
    rdp_bytes: int | None,
) -> Path:
    path = root / STORAGE_HISTORY_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "observed_at": observed_at,
        "disk_used_pct": disk_used_pct,
        "sqlite_bytes": sqlite_bytes,
        "rdp_bytes": rdp_bytes,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return path


def _normalized_24h_growth(
    *,
    prior: Mapping[str, Any],
    latest: Mapping[str, Any],
    span_h: float,
    current_disk_pct: int | None,
) -> tuple[Any, Any]:
    """Scale sqlite+RDP and disk-pct deltas onto an exact 24h window."""

    if span_h < 12:
        return UNKNOWN, UNKNOWN
    scale = 24.0 / span_h
    old_pct = prior.get("disk_used_pct")
    new_pct = current_disk_pct if isinstance(current_disk_pct, int) else latest.get("disk_used_pct")
    if not isinstance(old_pct, int) or not isinstance(new_pct, int):
        disk_growth: Any = UNKNOWN
    else:
        disk_growth = round((new_pct - old_pct) * scale, 3)
    old_bytes = prior.get("sqlite_bytes")
    new_bytes = latest.get("sqlite_bytes")
    old_rdp = prior.get("rdp_bytes")
    new_rdp = latest.get("rdp_bytes")
    data_growth: Any = UNKNOWN
    if (
        isinstance(old_bytes, int)
        and isinstance(new_bytes, int)
        and isinstance(old_rdp, int)
        and isinstance(new_rdp, int)
    ):
        delta = (new_bytes + new_rdp) - (old_bytes + old_rdp)
        data_growth = int(round(delta * scale))
    return disk_growth, data_growth


def _growth_and_projection(
    history: list[dict[str, Any]],
    *,
    now: datetime,
    current_disk_pct: int | None,
) -> tuple[Any, Any, Any]:
    """Return (disk_growth_24h_pct_points, data_growth_24h_bytes, projected_80pct)."""

    if current_disk_pct is None:
        return UNKNOWN, UNKNOWN, UNKNOWN
    window_start = now - timedelta(hours=24)
    prior: dict[str, Any] | None = None
    for row in history:
        at = _safe_parse(row.get("observed_at"))
        if at is None:
            continue
        if at <= window_start:
            prior = row
        elif prior is None:
            # first observation after window still usable as nearest older peer
            break
    if prior is None:
        dated = [
            (_safe_parse(r.get("observed_at")), r)
            for r in history
            if _safe_parse(r.get("observed_at")) is not None
        ]
        dated = [(t, r) for t, r in dated if t is not None]
        if len(dated) < 2:
            return UNKNOWN, UNKNOWN, UNKNOWN
        dated.sort(key=lambda item: item[0])
        oldest_t, oldest = dated[0]
        newest_t, newest = dated[-1]
        disk_growth, data_growth = _normalized_24h_growth(
            prior=oldest,
            latest=newest,
            span_h=(newest_t - oldest_t).total_seconds() / 3600.0,
            current_disk_pct=current_disk_pct,
        )
    else:
        latest = history[-1] if history else {}
        prior_at = _safe_parse(prior.get("observed_at"))
        latest_at = _safe_parse(latest.get("observed_at")) or now
        span_h = (
            (latest_at - prior_at).total_seconds() / 3600.0 if prior_at is not None else 0.0
        )
        disk_growth, data_growth = _normalized_24h_growth(
            prior=prior,
            latest=latest,
            span_h=span_h,
            current_disk_pct=current_disk_pct,
        )

    projected: Any = UNKNOWN
    if isinstance(disk_growth, (int, float)) and disk_growth > 0:
        remaining = DISK_WARNING_PCT - current_disk_pct
        if remaining <= 0:
            projected = "ALREADY_AT_OR_ABOVE_80"
        else:
            days = remaining / float(disk_growth)
            if days > 3650:
                projected = UNKNOWN
            else:
                projected = {
                    "threshold_pct": DISK_WARNING_PCT,
                    "estimated_days": round(days, 1),
                }
    return disk_growth, data_growth, projected


def _count_x_eligible_24h(
    store: ObservationScheduleStore,
    *,
    digest: str,
    act_id: str,
    window_start: datetime,
    now: datetime,
) -> Any:
    if not digest or not act_id:
        return UNKNOWN
    seen = 0
    found_x = False
    for row in store.due_in_states(
        (
            "OBSERVED",
            "X_POPULATION_INELIGIBLE",
            "MISSING_TYPED",
            "DISAPPEARED",
            "CENSORED",
            "CENSORED_LATE",
        ),
        due_at_max=now + timedelta(days=365),
    ):
        if str(row.get("schedule_sha256")) != digest:
            continue
        if str(row.get("activation_id")) != act_id:
            continue
        point = str(row.get("point_id") or "")
        if not point.upper().startswith("X"):
            continue
        found_x = True
        updated = _safe_parse(row.get("updated_at"))
        if updated is None or updated < window_start:
            continue
        if str(row.get("state")) == "OBSERVED":
            seen += 1
    if not found_x:
        return NOT_APPLICABLE
    return seen


def _live_release_fields(
    observation_rdp: Path,
    *,
    now: datetime,
    scientific_rdp_root: Path | None = None,
) -> dict[str, Any]:
    """Best-effort live cohort / corpus fields without inventing zeros."""

    out: dict[str, Any] = {
        "cohort_id": UNKNOWN,
        "cohort_readiness_state": UNKNOWN,
        "release_state": UNKNOWN,
        "last_sealed_release_id": UNKNOWN,
        "current_live_corpus_version": UNKNOWN,
        "release_blocked_reasons": [],
    }
    snapshot_path = observation_rdp / "live_observation_rebuild" / "source_snapshot.json"
    if not snapshot_path.is_file():
        return out
    try:
        source = load_observation_rdp_source(observation_rdp)
    except Exception:
        out["release_state"] = "RELEASE_INVALID_SOURCE_INTEGRITY"
        return out

    # Derive current UTC week cohort id from admission clock when possible.
    members = list(source.get("members") or [])
    if not members:
        out["cohort_readiness_state"] = "COLLECTING"
        out["release_state"] = "COLLECTING"
        return out

    # Prefer readiness flags already on snapshot.
    open_pub = bool(source.get("open_publication"))
    unresolved = bool(source.get("unresolved_due"))
    in_flight = bool(source.get("in_flight"))
    budget = bool(source.get("budget_blocked"))
    blockers = []
    if open_pub:
        blockers.append("RELEASE_BLOCKED_OPEN_PUBLICATION")
    if unresolved:
        blockers.append("RELEASE_BLOCKED_UNRESOLVED_DUE")
    if in_flight:
        blockers.append("RELEASE_BLOCKED_IN_FLIGHT")
    if budget:
        blockers.append("RELEASE_BLOCKED_BUDGET")
    out["release_blocked_reasons"] = blockers
    coverage = source.get("discovery_coverage_class")
    if blockers:
        out["release_state"] = "RELEASE_BLOCKED"
        out["cohort_readiness_state"] = "RELEASE_BLOCKED"
    else:
        out["release_state"] = str(coverage or "COLLECTING")
        out["cohort_readiness_state"] = str(coverage or "COLLECTING")

    # Sealed releases under optional scientific RDP root.
    search_root = scientific_rdp_root or observation_rdp
    sealed: list[Path] = []
    direct = search_root / "release_manifest.json"
    if direct.is_file():
        sealed.append(direct)
    sealed.extend(sorted(search_root.glob("**/live_cohort_release_*/release_manifest.json")))
    sealed.extend(sorted(search_root.glob("**/release_manifest.json")))
    # de-dupe preserving order
    seen: set[str] = set()
    unique: list[Path] = []
    for path in sealed:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    sealed = unique
    if sealed:
        latest = sealed[-1]
        try:
            manifest = json.loads(latest.read_text(encoding="utf-8"))
            out["last_sealed_release_id"] = str(
                manifest.get("release_id") or latest.parent.name
            )
            version = manifest.get("corpus_version")
            if version is not None:
                out["current_live_corpus_version"] = version
            labels = manifest.get("labels") if isinstance(manifest.get("labels"), dict) else {}
            if isinstance(labels, dict) and labels.get("corpus_version") is not None:
                out["current_live_corpus_version"] = labels.get("corpus_version")
            if isinstance(labels, dict) and labels.get("logical_dataset_id"):
                out["corpus_dataset_id"] = labels.get("logical_dataset_id")
            else:
                out["corpus_dataset_id"] = CORPUS_DATASET_ID
        except (OSError, json.JSONDecodeError):
            out["last_sealed_release_id"] = latest.parent.name
    else:
        out["corpus_dataset_id"] = CORPUS_DATASET_ID
    _ = now  # reserved for future cohort-id derivation
    return out


def compose_health_classes(packet: Mapping[str, Any]) -> list[str]:
    flags: list[str] = []
    activation_state = str(packet.get("activation_state") or "")
    if activation_state == "ACTIVE":
        flags.append("PROCESS_OK")

    age = packet.get("source_poll_age")
    period = packet.get("period_seconds")
    if isinstance(age, int) and isinstance(period, int) and age > period * 3:
        flags.append("DATA_STALE")

    http_401 = int(packet.get("HTTP_401_24h") or 0)
    http_403 = int(packet.get("HTTP_403_24h") or 0)
    http_429 = int(packet.get("HTTP_429_24h") or 0)
    http_5xx = int(packet.get("HTTP_5XX_24h") or 0)
    timeouts = int(packet.get("TIMEOUT_24h") or 0)
    transport = int(packet.get("TRANSPORT_ERROR_24h") or 0)
    if http_401 or http_403:
        flags.append("PROVIDER_AUTH_FAILED")
    if http_429:
        flags.append("PROVIDER_RATE_LIMITED")
    if http_5xx or timeouts or transport:
        flags.append("PROVIDER_FAILED")
    # Zero eligible market supply must NOT become provider failure (handled by absence).

    coverage = str(packet.get("discovery_coverage_class") or "")
    if coverage == "GAP_CONFIRMED":
        flags.append("DISCOVERY_GAP")
    elif coverage in {"GAP_SUSPECTED", "UNKNOWN", ""}:
        if coverage != "COVERED" and coverage != "NOT_APPLICABLE":
            if coverage in {"GAP_SUSPECTED", "UNKNOWN", ""}:
                flags.append("DISCOVERY_COVERAGE_UNKNOWN")

    due_pressure = packet.get("due_pressure") or {}
    if backlog_risk_from_due_pressure(due_pressure):
        flags.append("BACKLOG_RISK")
    if int(packet.get("blocked_budget") or 0) > 0:
        flags.append("BUDGET_BLOCKED")

    publish_at = packet.get("observation_rdp_last_publish_at")
    if publish_at in (None, UNKNOWN):
        if activation_state == "ACTIVE":
            flags.append("RDP_PUBLICATION_STALE")
    else:
        pub = _safe_parse(publish_at)
        now = _safe_parse(str(packet.get("observed_at") or "")) or datetime.now(UTC)
        if pub is not None and (now - pub).total_seconds() > 6 * 3600:
            flags.append("RDP_PUBLICATION_STALE")

    backup_domain = packet.get("backup_domain")
    backup_age = packet.get("backup_age_seconds")
    if packet.get("restore_marker_unresolved") is True:
        flags.append("BACKUP_DEGRADED")
    elif backup_domain in (None, UNKNOWN):
        flags.append("BACKUP_DEGRADED")
    elif backup_age in (None, UNKNOWN) or packet.get("last_backup_at") in (
        None,
        UNKNOWN,
    ):
        flags.append("BACKUP_DEGRADED")
    elif isinstance(backup_age, int) and backup_age > 24 * 3600:
        flags.append("BACKUP_DEGRADED")

    offhost_state = str(packet.get("offhost_backup_state") or "")
    if offhost_state == "FAILED":
        flags.append("OFFHOST_BACKUP_FAILED")
    elif offhost_state in {"DEGRADED", "HARD_ATTENTION", "MISSING"}:
        flags.append("OFFHOST_BACKUP_STALE")

    if int(packet.get("immutable_archive_backlog_days") or 0) > 0:
        age = packet.get("immutable_archive_oldest_backlog_age_seconds")
        if isinstance(age, int) and age > 86400:
            flags.append("IMMUTABLE_ARCHIVE_STALE")
    if str(packet.get("immutable_archive_last_terminal") or "") == "HASH_MISMATCH":
        flags.append("IMMUTABLE_ARCHIVE_HASH_MISMATCH")
    if packet.get("mutable_backup_includes_full_observation_rdp") is True and str(
        packet.get("hot90_activation_stage") or ""
    ) in {"DURABILITY_CUTOVER", "RETENTION_ACTIVE"}:
        flags.append("MUTABLE_BACKUP_FULL_RDP_UNEXPECTED")

    disk = packet.get("filesystem_disk_used_pct")
    if isinstance(disk, int):
        if disk >= DISK_CRITICAL_PCT:
            flags.append("DISK_CRITICAL")
        elif disk >= DISK_WARNING_PCT:
            flags.append("DISK_WARNING")
        # >=70% early warning is pulse-text only; remote-ops hard boundary stays 85%.

    runway = str(packet.get("projected_97d_status") or "")
    if runway == "ACTION_REQUIRED":
        flags.append("DISK_RUNWAY_HARD50")
    elif runway == "DEGRADED":
        flags.append("DISK_RUNWAY_TARGET40")

    if str(packet.get("release_state") or "").startswith("RELEASE_BLOCKED"):
        flags.append("RELEASE_BLOCKED")
    if packet.get("release_blocked_reasons"):
        if "RELEASE_BLOCKED" not in flags:
            flags.append("RELEASE_BLOCKED")

    # Preserve order of HEALTH_CLASSES
    ordered = [name for name in HEALTH_CLASSES if name in set(flags)]
    return ordered


def collector_verdict(health_classes: list[str]) -> str:
    action = {
        "PROVIDER_AUTH_FAILED",
        "DISK_CRITICAL",
        "BACKUP_DEGRADED",
        "OFFHOST_BACKUP_FAILED",
        "OFFHOST_BACKUP_STALE",
        "IMMUTABLE_ARCHIVE_HASH_MISMATCH",
        "MUTABLE_BACKUP_FULL_RDP_UNEXPECTED",
        "DISK_RUNWAY_HARD50",
        "RELEASE_BLOCKED",
        "BUDGET_BLOCKED",
    }
    degraded = {
        "DATA_STALE",
        "PROVIDER_RATE_LIMITED",
        "PROVIDER_FAILED",
        "DISCOVERY_GAP",
        "BACKLOG_RISK",
        "RDP_PUBLICATION_STALE",
        "DISK_WARNING",
        "IMMUTABLE_ARCHIVE_STALE",
        "DISK_RUNWAY_TARGET40",
    }
    classes = set(health_classes)
    if classes & action:
        return "ACTION_REQUIRED"
    if classes & degraded:
        return "DEGRADED"
    if "PROCESS_OK" in classes or not classes:
        return "OK"
    return "DEGRADED"


def build_collector_operational_packet(
    *,
    root: Path,
    store: ObservationScheduleStore,
    now: datetime | None = None,
    schedule_sha256: str | None = None,
    activation_id: str | None = None,
    deploy_git_sha: str | None = None,
    period_seconds: int = 60,
    empirical_overlap_seconds: int | None = None,
    observation_rdp: Path | None = None,
    remote_config: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
    scientific_rdp_root: Path | None = None,
    campaign_id: str | None = None,
    cohort_id: str | None = None,
) -> dict[str, Any]:
    clock = now or datetime.now(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    clock = clock.astimezone(UTC)
    observed_at = render_utc(clock)

    base = build_collector_read_model(
        store,
        now=clock,
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        deploy_git_sha=deploy_git_sha,
        period_seconds=period_seconds,
        empirical_overlap_seconds=empirical_overlap_seconds,
    )

    loaded = dict(remote_config) if remote_config is not None else None
    try:
        if loaded is None:
            loaded = load_config(root)
    except Exception:
        loaded = None

    env = environ if environ is not None else {}
    rdp = observation_rdp
    if rdp is None and loaded is not None:
        # Prefer recursive backup observation_rdp path when present.
        recursive = list(loaded.get("backup", {}).get("recursive_relative_paths") or [])
        if recursive:
            rdp = root / str(recursive[0])
    if rdp is None:
        rdp = root / "local/factory_v1/observation_rdp"

    sqlite_path = Path(store.path) if getattr(store, "path", None) is not None else None
    if sqlite_path is None and loaded is not None:
        rel = loaded.get("stores", {}).get("observation_schedule_relative")
        if rel:
            sqlite_path = root / str(rel)

    disk_pct: Any = UNKNOWN
    disk_free: Any = UNKNOWN
    try:
        disk_pct = _disk_used_percent(root)
        free = _disk_free_bytes(root)
        disk_free = free if free is not None else UNKNOWN
    except Exception:
        disk_pct = UNKNOWN
        disk_free = UNKNOWN

    sqlite_bytes: Any = UNKNOWN
    if sqlite_path is not None and sqlite_path.is_file():
        try:
            sqlite_bytes = int(sqlite_path.stat().st_size)
            wal = Path(str(sqlite_path) + "-wal")
            if wal.is_file():
                sqlite_bytes += int(wal.stat().st_size)
        except OSError:
            sqlite_bytes = UNKNOWN

    rdp_bytes: Any = UNKNOWN
    measured = _tree_bytes(rdp)
    if measured is not None:
        rdp_bytes = measured

    jobs = journal_stats(rdp)
    rdp_science_bytes: Any = UNKNOWN
    try:
        rdp_science_bytes = rdp_bytes_excluding_publication_jobs(rdp)
    except OSError:
        rdp_science_bytes = UNKNOWN

    declared_raw: Any = UNKNOWN
    remaining_canonical: Any = UNKNOWN
    elapsed_days: float | None = None
    digest = str(base.get("schedule_sha256") or "")
    act_id = str(base.get("activation_id") or "")
    if digest:
        try:
            registered = store.get_registered_schedule(digest)
        except Exception:
            registered = None
        document = (registered or {}).get("document") if registered else None
        budgets = (document or {}).get("budgets") if isinstance(document, dict) else {}
        if isinstance(budgets, dict) and "raw_bytes_per_utc_day_max" in budgets:
            try:
                declared_raw = int(budgets["raw_bytes_per_utc_day_max"])
            except (TypeError, ValueError):
                declared_raw = UNKNOWN
        if isinstance(budgets, dict) and "canonical_bytes_lifetime_max" in budgets:
            try:
                life = store.load_lifetime(
                    schedule_sha256=digest, activation_id=act_id
                )
                remaining_canonical = max(
                    0,
                    int(budgets["canonical_bytes_lifetime_max"])
                    - int(life["canonical_bytes"]),
                )
            except Exception:
                remaining_canonical = UNKNOWN
        try:
            activation = store.get_activation(digest, act_id) if act_id else None
            starts = (activation or {}).get("starts_at")
            if starts:
                elapsed_days = max(
                    (clock - parse_utc(str(starts))).total_seconds() / 86400.0, 0.0
                )
        except Exception:
            elapsed_days = None

    disk_total: int | None = None
    disk_used: int | None = None
    try:
        usage = shutil.disk_usage(root)
        disk_total = int(usage.total)
        disk_used = int(usage.used)
    except OSError:
        disk_total = None
        disk_used = None

    backup_at: Any = UNKNOWN
    backup_sha: Any = UNKNOWN
    backup_age: Any = UNKNOWN
    backup_domain: Any = UNKNOWN
    backup_sink_bytes: Any = UNKNOWN
    if loaded is not None:
        try:
            sink = resolve_backup_sink(root, loaded, env)
            backup = _backup_newest(sink)
            backup_domain = backup_domain_for(root, loaded, sink, env)
            if backup:
                backup_at = backup.get("mtime") or UNKNOWN
                backup_sha = backup.get("sha256") or UNKNOWN
                at = _safe_parse(backup_at)
                backup_age = (
                    int((clock - at).total_seconds()) if at is not None else UNKNOWN
                )
            sink_size = _tree_bytes(sink)
            backup_sink_bytes = sink_size if sink_size is not None else UNKNOWN
        except Exception:
            backup_domain = UNKNOWN

    offhost = offhost_health_snapshot(root, now=clock)

    publish_at = _newest_publish_at(rdp)
    if publish_at is None:
        publish_at_value: Any = UNKNOWN
    else:
        publish_at_value = publish_at

    window_start = clock - timedelta(hours=24)
    x_eligible = _count_x_eligible_24h(
        store,
        digest=str(base.get("schedule_sha256") or ""),
        act_id=str(base.get("activation_id") or ""),
        window_start=window_start,
        now=clock,
    )

    history = _load_storage_history(root)
    # Include a virtual current point for growth math without requiring a write.
    history_with_now = list(history) + [
        {
            "observed_at": observed_at,
            "disk_used_pct": disk_pct if isinstance(disk_pct, int) else None,
            "sqlite_bytes": sqlite_bytes if isinstance(sqlite_bytes, int) else None,
            "rdp_bytes": rdp_bytes if isinstance(rdp_bytes, int) else None,
        }
    ]
    disk_growth, data_growth, projected = _growth_and_projection(
        history_with_now,
        now=clock,
        current_disk_pct=disk_pct if isinstance(disk_pct, int) else None,
    )
    history_growth = data_growth if isinstance(data_growth, int) else None
    week_proj = project_7d_disk_used(
        disk_total_bytes=disk_total,
        disk_used_bytes=disk_used,
        sqlite_bytes=sqlite_bytes if isinstance(sqlite_bytes, int) else None,
        rdp_science_bytes=rdp_science_bytes if isinstance(rdp_science_bytes, int) else None,
        job_open_bytes=int(jobs["publication_jobs_open_bytes"]),
        job_completed_bytes=int(jobs["publication_jobs_completed_bytes"]),
        job_legacy_bytes=int(jobs["publication_jobs_legacy_full_bytes"]),
        elapsed_campaign_days=elapsed_days,
        declared_raw_bytes_per_day=declared_raw if isinstance(declared_raw, int) else None,
        history_data_growth_24h_bytes=history_growth,
    )

    release = _live_release_fields(
        rdp, now=clock, scientific_rdp_root=scientific_rdp_root
    )
    if cohort_id:
        release["cohort_id"] = cohort_id

    packet: dict[str, Any] = {
        "schema": "smial.collector-operational-packet",
        "schema_version": "1.0",
        "observed_at": observed_at,
        "period_seconds": period_seconds,
        # IDENTITY
        "deploy_git_sha": base.get("deploy_git_sha") or UNKNOWN,
        "schedule_sha256": base.get("schedule_sha256") or UNKNOWN,
        "activation_id": base.get("activation_id") or UNKNOWN,
        "activation_state": base.get("activation_state") or UNKNOWN,
        "campaign_id": campaign_id or UNKNOWN,
        "cohort_id": release.get("cohort_id") or UNKNOWN,
        # COLLECTION
        "last_tick_at": base.get("last_tick_at") or UNKNOWN,
        "last_source_poll_attempt_at": base.get("last_source_poll_attempt_at") or UNKNOWN,
        "last_source_poll_success_at": base.get("last_source_poll_success_at")
        or UNKNOWN,
        "source_poll_age": (
            base.get("source_poll_age")
            if base.get("source_poll_age") is not None
            else UNKNOWN
        ),
        "discovery_coverage_class": base.get("discovery_coverage_class") or UNKNOWN,
        "last_search_success_at": base.get("last_search_success_at") or UNKNOWN,
        "candidates_24h": base.get("candidate_count_24h"),
        "sampled_members_24h": base.get("sampled_member_count_24h"),
        "x_eligible_24h": x_eligible,
        "observations_24h": base.get("observations_24h"),
        "typed_missing_24h": base.get("typed_missing_24h"),
        "censored_late_24h": base.get("censored_late_24h"),
        "pending_due": base.get("pending_due_count"),
        "oldest_due_age": base.get("oldest_due_age_seconds"),
        "due_pressure": base.get("due_pressure"),
        "in_flight_indeterminate": base.get("in_flight_indeterminate_count"),
        "blocked_budget": base.get("blocked_budget_count"),
        # PROVIDER
        "HTTP_401_24h": base.get("HTTP_401_24h"),
        "HTTP_403_24h": base.get("HTTP_403_24h"),
        "HTTP_429_24h": base.get("HTTP_429_24h"),
        "HTTP_5XX_24h": base.get("HTTP_5XX_24h"),
        "TIMEOUT_24h": base.get("TIMEOUT_24h"),
        "TRANSPORT_ERROR_24h": base.get("TRANSPORT_ERROR_24h"),
        # STORAGE
        "filesystem_disk_used_pct": disk_pct,
        "filesystem_disk_free_bytes": disk_free,
        "observation_sqlite_bytes": sqlite_bytes,
        "observation_rdp_bytes": rdp_bytes,
        "observation_rdp_bytes_excluding_publication_jobs": rdp_science_bytes,
        "publication_jobs_open_count": jobs["publication_jobs_open_count"],
        "publication_jobs_open_bytes": jobs["publication_jobs_open_bytes"],
        "publication_jobs_completed_count": jobs["publication_jobs_completed_count"],
        "publication_jobs_completed_bytes": jobs["publication_jobs_completed_bytes"],
        "publication_jobs_legacy_full_count": jobs["publication_jobs_legacy_full_count"],
        "publication_jobs_legacy_full_bytes": jobs["publication_jobs_legacy_full_bytes"],
        "publication_jobs_unmigrated_flat_count": jobs[
            "publication_jobs_unmigrated_flat_count"
        ],
        "publication_jobs_unmigrated_flat_bytes": jobs[
            "publication_jobs_unmigrated_flat_bytes"
        ],
        "declared_raw_bytes_per_utc_day_max": declared_raw,
        "canonical_bytes_lifetime_remaining": remaining_canonical,
        "projected_7d_disk_used_pct": week_proj.get("projected_7d_disk_used_pct"),
        "projected_7d_disk_used_pass_70": week_proj.get("projected_7d_disk_used_pass_70"),
        "projected_7d_projection_basis": week_proj.get("projection_basis"),
        "backup_sink_bytes": backup_sink_bytes,
        "disk_growth_24h_pct_points": disk_growth,
        "data_growth_24h_bytes": data_growth,
        "projected_disk_80pct": projected,
        "disk_policy": {
            "normal_lt": DISK_WARNING_EARLY_PCT,
            "warning_early_gte": DISK_WARNING_EARLY_PCT,
            "warning_gte": DISK_WARNING_PCT,
            "critical_gte": DISK_CRITICAL_PCT,
            "remote_ops_hard_max_pct": DISK_CRITICAL_PCT,
        },
        # SCIENTIFIC PUBLICATION
        "observation_rdp_last_publish_at": publish_at_value,
        "cohort_readiness_state": release.get("cohort_readiness_state"),
        "release_state": release.get("release_state"),
        "last_sealed_release_id": release.get("last_sealed_release_id"),
        "current_live_corpus_version": release.get("current_live_corpus_version"),
        "corpus_dataset_id": release.get("corpus_dataset_id", CORPUS_DATASET_ID),
        "release_blocked_reasons": release.get("release_blocked_reasons") or [],
        # DURABILITY
        "last_backup_at": backup_at,
        "last_backup_sha256": backup_sha,
        "backup_age_seconds": backup_age,
        "backup_domain": backup_domain,
        "offhost_backup_state": offhost.get("offhost_backup_state"),
        "offhost_last_verified_at": offhost.get("offhost_last_verified_at"),
        "offhost_backup_age_seconds": offhost.get("offhost_backup_age_seconds"),
        "offhost_last_filename": offhost.get("offhost_last_filename"),
        "offhost_last_sha256": offhost.get("offhost_last_sha256"),
        "offhost_remote": offhost.get("offhost_remote"),
        "durability_domain": offhost.get("durability_domain"),
        "offhost_backup_payload_bytes_30d": offhost.get("offhost_backup_payload_bytes_30d"),
        "projected_offhost_backup_payload_bytes_30d": offhost.get(
            "projected_offhost_backup_payload_bytes_30d"
        ),
        "offhost_payload_budget_class": offhost.get("budget_class"),
        "offhost_egress_policy_pressure": offhost.get("offhost_egress_policy_pressure"),
        "application_payload_is_billing_truth": False,
        "restore_marker_unresolved": bool(base.get("restore_marker_unresolved")),
        "raw_retention_substrate": (
            "DECODED_CANONICAL_PROVIDER_JSON_IN_CALL_LEDGER_NOT_BYTE_IDENTICAL_HTTP"
        ),
        "due_counts": base.get("due_counts") or {},
    }
    try:
        activation = load_hot90_activation(root)
    except Exception:
        activation = {}
    packet["hot90_activation_stage"] = activation.get("activation_stage") or UNKNOWN
    packet["hot90_activation_source"] = activation.get("activation_source") or UNKNOWN
    try:
        selected = mutable_backup_sources(
            (loaded or {}).get("backup") or {},
            activation_stage=str(activation.get("activation_stage") or "CURRENT_SAFE"),
        )
        packet["mutable_backup_includes_full_observation_rdp"] = selected.get(
            "includes_full_observation_rdp"
        )
    except Exception:
        packet["mutable_backup_includes_full_observation_rdp"] = UNKNOWN
    try:
        backlog = archive_backlog(root, now=clock)
    except Exception:
        backlog = {
            "backlog_days": UNKNOWN,
            "latest_verified_day": UNKNOWN,
            "oldest_backlog_age_seconds": UNKNOWN,
            "eligible_unverified_days": [],
            "stuck_hash_mismatch_days": [],
        }
    packet["immutable_archive_latest_verified_day"] = backlog.get("latest_verified_day")
    packet["immutable_archive_backlog_days"] = backlog.get("backlog_days")
    packet["immutable_archive_oldest_backlog_age_seconds"] = backlog.get(
        "oldest_backlog_age_seconds"
    )
    last_terminal = None
    latest = backlog.get("latest_verified_day")
    unverified = backlog.get("eligible_unverified_days") or []
    stuck = backlog.get("stuck_hash_mismatch_days") or []
    probe_day = stuck[0] if stuck else (unverified[0] if unverified else latest)
    if probe_day:
        receipt = read_receipt(root, str(probe_day))
        if receipt:
            last_terminal = receipt.get("terminal")
    packet["immutable_archive_last_terminal"] = last_terminal
    incremental = data_growth if isinstance(data_growth, int) and data_growth >= 0 else 0
    current_bytes = 0
    for item in (sqlite_bytes, rdp_bytes):
        if isinstance(item, int):
            current_bytes += item
    try:
        runway = project_storage_runway(
            incremental_compressed_bytes_per_day=incremental,
            current_same_volume_factory_bytes=current_bytes,
            mutable_backup_peak_bytes=int(backup_sink_bytes)
            if isinstance(backup_sink_bytes, int)
            else 0,
            staging_peak_bytes=0,
            retention_class="HOT90_RESIDENT",
        )
        packet["projected_97d_bytes"] = runway["projected_total_same_volume_bytes"]
        packet["projected_97d_status"] = runway["status"]
    except Exception:
        packet["projected_97d_bytes"] = UNKNOWN
        packet["projected_97d_status"] = UNKNOWN
    health = compose_health_classes(packet)
    packet["health_classes"] = health
    packet["collector_verdict"] = collector_verdict(health)
    return packet


__all__ = [
    "DISK_CRITICAL_PCT",
    "DISK_WARNING_EARLY_PCT",
    "DISK_WARNING_PCT",
    "HEALTH_CLASSES",
    "NOT_APPLICABLE",
    "STORAGE_HISTORY_RELATIVE",
    "UNKNOWN",
    "append_storage_history",
    "build_collector_operational_packet",
    "collector_verdict",
    "compose_health_classes",
]
