"""One owner path from the next mature unimported cohort to Forge readiness.

Orchestrates existing closure, bounded dependency, mirror, build, seal, and
import primitives. It does not materialize on a capture host and does not run
``/hypothesis-forge``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from solana_alpha_lab.factory.bounded_cohort_materialization import (
    inspect_member_target,
    resolve_observation_panel_location,
    select_member_batches,
    select_observation_batches,
)
from solana_alpha_lab.factory.live_cohort_discovery_release import (
    LiveCohortReleaseError,
    _apply_closure_receipt,
    _lineage_from_rdp,
    _parse_utc,
    build_live_observation_source_from_rdp,
    campaign_cohort_windows,
    import_live_cohort,
    last_bounded_research_rels,
    seal_live_cohort,
    verify_live_cohort,
)
from solana_alpha_lab.factory.live_cohort_source_bundle import sha256_file_streaming
from solana_alpha_lab.factory.live_cohort_to_forge import (
    CONTROL_NEXT,
    default_sealed_release_root,
    forge_control_ready,
)
from solana_alpha_lab.factory.observation_publication_jobs import completed_job_path
from solana_alpha_lab.factory.observation_schedule import canonical_sha256, parse_utc

TERMINAL = "FORGE_CONTROL_READY"


def select_next_mature_unimported_cohort(
    *,
    activations: list[Mapping[str, Any]],
    rollovers: list[Mapping[str, Any]],
    imported_cohort_ids: set[str],
    as_of: datetime,
) -> dict[str, Any] | None:
    """First mature closure window still owned by its activation and not imported.

    A predecessor activation does not keep a synthetic window that starts at or
    after its rollover cutover. That window belongs to the successor activation.
    """

    cutover_by_predecessor: dict[tuple[str, str], datetime] = {}
    for item in rollovers:
        key = (
            str(item.get("predecessor_schedule_sha256") or ""),
            str(item.get("predecessor_activation_id") or ""),
        )
        if not key[0] or not key[1]:
            continue
        cutover = parse_utc(str(item.get("cutover_at") or ""))
        previous = cutover_by_predecessor.get(key)
        if previous is None or cutover < previous:
            cutover_by_predecessor[key] = cutover
    found: list[dict[str, Any]] = []
    for activation in activations:
        schedule_sha = str(activation.get("schedule_sha256") or "")
        activation_id = str(activation.get("activation_id") or "")
        if not schedule_sha or not activation_id:
            continue
        starts = parse_utc(str(activation.get("starts_at") or ""))
        stops = parse_utc(str(activation.get("stops_admitting_at") or ""))
        cutover = cutover_by_predecessor.get((schedule_sha, activation_id))
        for cohort_id, window_start, window_end in campaign_cohort_windows(starts, stops):
            if cutover is not None and window_start >= cutover:
                continue
            if cohort_id in imported_cohort_ids:
                continue
            mature_at = window_end + timedelta(days=1)
            if as_of < mature_at:
                continue
            found.append(
                {
                    "cohort_id": cohort_id,
                    "schedule_sha256": schedule_sha,
                    "activation_id": activation_id,
                    "window_start": window_start,
                    "window_end": window_end,
                    "mature_at": mature_at,
                }
            )
    found.sort(key=lambda item: (item["window_start"], item["cohort_id"]))
    return found[0] if found else None


def _add_file(entries: dict[str, dict[str, Any]], root: Path, relative: str, source_class: str) -> None:
    text = str(relative).replace("\\", "/")
    if not text or text in entries:
        return
    path = root / text
    if not path.is_file() or path.is_symlink():
        raise LiveCohortReleaseError(f"DEPENDENCY_MISSING:{text}")
    entries[text] = {
        "bytes": int(path.stat().st_size),
        "path": text,
        "sha256": sha256_file_streaming(path),
        "source_class": source_class,
    }


def collect_bounded_transfer_manifest(
    *,
    observation_rdp: Path,
    schedule_sha256: str,
    activation_id: str,
    cohort_id: str,
    closure_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """File list for one cohort, taken from the plan's selected batches."""

    root = Path(observation_rdp)
    flags = _apply_closure_receipt(
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        cohort_id=cohort_id,
        closure_receipt=closure_receipt,
    )
    cutoff = _parse_utc(str(flags["closure_cutoff_at"]))
    _doc, _producer, rows = _lineage_from_rdp(
        root,
        schedule_sha256=schedule_sha256,
        activation_id=activation_id,
        window_start=parse_utc(str(closure_receipt["window_start"])),
        closure_cutoff=cutoff,
    )
    selected_members, _predecessors = select_member_batches(
        rows,
        window_start=parse_utc(str(closure_receipt["window_start"])),
        closure_cutoff=cutoff,
    )
    member_ids = {
        str((row.get("payload") or {}).get("dataset_manifest_id") or "")
        for row in selected_members
        if isinstance(row.get("payload"), Mapping)
    }
    member_ids.discard("")
    selected_obs = select_observation_batches(
        rows,
        window_start=parse_utc(str(closure_receipt["window_start"])),
        closure_cutoff=cutoff,
        member_dataset_ids=member_ids,
    )
    entries: dict[str, dict[str, Any]] = {}
    for relative in last_bounded_research_rels():
        candidate = root / relative
        if candidate.is_file() and not candidate.is_symlink():
            _add_file(entries, root, relative, "research_bounded_partition")
    for row in selected_members:
        payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
        location = str(payload.get("member_location") or "")
        if not location:
            continue
        info = inspect_member_target(root, location)
        unit = info.get("unit") if isinstance(info.get("unit"), Mapping) else None
        seq = info.get("seq")
        if unit is None or seq is None:
            _add_file(entries, root, location, "member_location")
            continue
        for publication in unit.get("publications") or []:
            if not isinstance(publication, Mapping):
                continue
            try:
                pub_seq = int(publication.get("seq"))
            except (TypeError, ValueError):
                continue
            if pub_seq > int(seq):
                continue
            rel = str(publication.get("rel") or "")
            if rel:
                _add_file(entries, root, rel, "member_prefix")
                layout = str(Path(rel).with_name("members.layout.json").as_posix())
                if (root / layout).is_file():
                    _add_file(entries, root, layout, "member_layout")
            mid = str(publication.get("dataset_manifest_id") or "")
            if mid:
                _add_file(entries, root, f"datasets/manifests/{mid}.json", "dataset_manifest")
                published = f"datasets/manifests/{mid}.published"
                if (root / published).is_file():
                    _add_file(entries, root, published, "dataset_published")
    for row in selected_obs:
        payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
        _path, location = resolve_observation_panel_location(root, payload, partition_index=None)
        _add_file(entries, root, location, "observation_parquet")
        mid = str(payload.get("dataset_manifest_id") or "")
        if mid:
            manifest_rel = f"datasets/manifests/{mid}.json"
            if (root / manifest_rel).is_file():
                _add_file(entries, root, manifest_rel, "dataset_manifest")
            published = f"datasets/manifests/{mid}.published"
            if (root / published).is_file():
                _add_file(entries, root, published, "dataset_published")
        content = str(payload.get("dataset_fingerprint") or payload.get("content_sha256") or "")
        if len(content) == 64:
            job = completed_job_path(root, content)
            if job.is_file():
                _add_file(
                    entries,
                    root,
                    job.relative_to(root).as_posix(),
                    "publication_receipt",
                )
    ordered = [entries[key] for key in sorted(entries)]
    body = {
        "kind": "LIVE_COHORT_BOUNDED_TRANSFER_MANIFEST",
        "schema_version": "1",
        "activation_id": activation_id,
        "cohort_id": cohort_id,
        "entries": ordered,
        "schedule_sha256": schedule_sha256,
    }
    body["manifest_sha256"] = canonical_sha256(body)
    return body


def classify_mirror(
    manifest: Mapping[str, Any],
    mirror_root: Path,
) -> dict[str, Any]:
    reused = missing = conflicts = 0
    missing_bytes = 0
    missing_paths: list[str] = []
    for entry in manifest.get("entries") or []:
        if not isinstance(entry, Mapping):
            continue
        relative = str(entry.get("path") or "")
        path = Path(mirror_root) / relative
        size = int(entry.get("bytes") or 0)
        if not path.is_file() or path.is_symlink():
            missing += 1
            missing_bytes += size
            missing_paths.append(relative)
            continue
        digest = sha256_file_streaming(path)
        if digest == entry.get("sha256") and path.stat().st_size == size:
            reused += 1
            continue
        conflicts += 1
    return {
        "conflicts": conflicts,
        "missing_bytes": missing_bytes,
        "missing_files": missing,
        "missing_paths": missing_paths,
        "reused_files": reused,
        "status": "CONFLICT" if conflicts else "READY",
    }


def place_missing(
    *,
    manifest: Mapping[str, Any],
    source_root: Path,
    mirror_root: Path,
    classification: Mapping[str, Any],
) -> int:
    if int(classification.get("conflicts") or 0):
        raise LiveCohortReleaseError("MIRROR_CONFLICT")
    by_path = {
        str(item.get("path")): item
        for item in (manifest.get("entries") or [])
        if isinstance(item, Mapping)
    }
    moved = 0
    for relative in classification.get("missing_paths") or []:
        entry = by_path[str(relative)]
        src = Path(source_root) / str(relative)
        digest = sha256_file_streaming(src)
        if digest != entry.get("sha256"):
            raise LiveCohortReleaseError(f"TRANSFER_SHA_MISMATCH:{relative}")
        dest = Path(mirror_root) / str(relative)
        if dest.exists():
            raise LiveCohortReleaseError(f"MIRROR_CONFLICT:{relative}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            raise LiveCohortReleaseError(f"TRANSFER_SHA_MISMATCH:{relative}")
        moved += 1
    return moved


def imported_cohort_ids(data_root: Path) -> set[str]:
    path = Path(data_root) / "datasets" / "live_lifecycle_corpus" / "lineage.json"
    if not path.is_file():
        return set()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(item.get("cohort_id"))
        for item in (loaded.get("cohorts") or [])
        if isinstance(item, Mapping) and item.get("cohort_id")
    }


def unpack_next_live_cohort(
    *,
    observation_rdp: Path,
    data_root: Path,
    repo_root: Path,
    activations: list[Mapping[str, Any]],
    rollovers: list[Mapping[str, Any]],
    closure_receipt: Mapping[str, Any],
    as_of: datetime,
    mirror_root: Path | None = None,
    source_root: Path | None = None,
    release_builder_git_sha: str | None = None,
    plan_only: bool = False,
) -> dict[str, Any]:
    """Local half of the owner path. Capture/export supplies the frozen receipt."""

    chosen = select_next_mature_unimported_cohort(
        activations=activations,
        rollovers=rollovers,
        imported_cohort_ids=imported_cohort_ids(data_root),
        as_of=as_of,
    )
    if chosen is None:
        raise LiveCohortReleaseError("NO_MATURE_UNIMPORTED_COHORT")
    if (
        chosen["cohort_id"] != closure_receipt.get("cohort_id")
        or chosen["schedule_sha256"] != closure_receipt.get("schedule_sha256")
        or chosen["activation_id"] != closure_receipt.get("activation_id")
    ):
        raise LiveCohortReleaseError("CLOSURE_COHORT_MISMATCH")
    manifest = collect_bounded_transfer_manifest(
        observation_rdp=observation_rdp,
        schedule_sha256=str(chosen["schedule_sha256"]),
        activation_id=str(chosen["activation_id"]),
        cohort_id=str(chosen["cohort_id"]),
        closure_receipt=closure_receipt,
    )
    mirror = Path(mirror_root or observation_rdp)
    classification = classify_mirror(manifest, mirror)
    if classification["status"] == "CONFLICT":
        raise LiveCohortReleaseError("MIRROR_CONFLICT")
    placed = 0
    if classification["missing_files"] and source_root is not None and Path(source_root) != mirror:
        placed = place_missing(
            manifest=manifest,
            source_root=Path(source_root),
            mirror_root=mirror,
            classification=classification,
        )
        classification = classify_mirror(manifest, mirror)
        if classification["missing_files"] or classification["conflicts"]:
            raise LiveCohortReleaseError("MIRROR_INCOMPLETE")
    plan = build_live_observation_source_from_rdp(
        observation_rdp_root=mirror,
        schedule_sha256=str(chosen["schedule_sha256"]),
        activation_id=str(chosen["activation_id"]),
        cohort_id=str(chosen["cohort_id"]),
        closure_receipt=closure_receipt,
        ops_store=None,
        plan_only=True,
    )
    if plan.get("work_class") != "BOUNDED_COHORT_WINDOW":
        raise LiveCohortReleaseError(str(plan.get("work_class") or "UNBOUNDED_PLAN"))
    for key, expected in (
        ("historical_independent_reconstruct_calls", 0),
        ("global_historical_observation_glob", False),
        ("full_historical_research_payload_scan", False),
        ("slow_fallback_required", False),
        ("research_event_partitions_opened_unknown_bounds", 0),
        ("observation_partition_index_files_read", 0),
    ):
        if plan.get(key) != expected:
            raise LiveCohortReleaseError(f"PLAN_GATE:{key}")
    if plan_only:
        return {
            "terminal": "PLAN_READY",
            "next": CONTROL_NEXT,
            "cohort": chosen,
            "plan": plan,
            "transfer_manifest_sha256": manifest["manifest_sha256"],
            "mirror": classification,
            "placed_files": placed,
        }
    build_live_observation_source_from_rdp(
        observation_rdp_root=mirror,
        schedule_sha256=str(chosen["schedule_sha256"]),
        activation_id=str(chosen["activation_id"]),
        cohort_id=str(chosen["cohort_id"]),
        closure_receipt=closure_receipt,
        ops_store=None,
        plan_only=False,
    )
    release_root = default_sealed_release_root(mirror, str(chosen["cohort_id"]))
    if not (release_root / "release_manifest.json").is_file():
        seal_live_cohort(
            observation_rdp_root=mirror,
            cohort_id=str(chosen["cohort_id"]),
            release_root=release_root,
            as_of=as_of,
            release_builder_git_sha=release_builder_git_sha,
        )
    verified = verify_live_cohort(release_root)
    imported = import_live_cohort(release_root=release_root, data_root=Path(data_root))
    ready = forge_control_ready(
        data_root=Path(data_root),
        repo_root=Path(repo_root),
        imported_cohort_id=str(chosen["cohort_id"]),
    )
    return {
        "terminal": ready.get("terminal"),
        "next": ready.get("next"),
        "cohort_id": chosen["cohort_id"],
        "release_id": verified.get("release_id"),
        "import_status": imported.get("status"),
        "forge_runnable": bool(
            (ready.get("forge_input_receipt") or {}).get("forge_runnable")
            if isinstance(ready.get("forge_input_receipt"), Mapping)
            else False
        ),
        "transfer_manifest_sha256": manifest["manifest_sha256"],
        "placed_files": placed,
    }
