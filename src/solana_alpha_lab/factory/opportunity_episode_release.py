"""OPPORTUNITY_EPISODES collection strategy for the split-host release path.

Capture host: maturity by obligations, frozen closure receipt, bounded export
bundle and transfer manifest. Workstation: bounded source build from the
mirrored publications, immutable release 1.2, verify and import into the
separate episode corpus. Entry points are the existing owners
(``live_cohort_vanilla_path`` / ``live_cohort_discovery_release``); this module
is their collection-specific strategy, not a second importer or service.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from solana_alpha_lab.factory.discovery_evidence_release import _publish_bytes
from solana_alpha_lab.factory.live_cohort_schedule_artifact import (
    OBSERVATION_SCHEDULE_ARTIFACT_NAME,
    RELEASE_SCHEMA_VERSION_EPISODES,
    decode_schedule_artifact,
    encode_schedule_artifact,
)
from solana_alpha_lab.factory.live_cohort_source_bundle import sha256_file_streaming
from solana_alpha_lab.factory.observation_schedule import (
    canonical_sha256,
    parse_utc,
    render_utc,
)
from solana_alpha_lab.factory.opportunity_episodes import (
    ANCHOR_KIND,
    assignment_document_sha256,
    COLLECTION,
    LOGICAL_DATASET_ID,
    POPULATION,
    POPULATION_CONTRACT,
    SCHEDULE_CONTRACT,
    WITNESS_POINT,
    admission_content_sha256,
    cohort_day_bounds,
    episode_point_ids,
    is_episode_schedule,
    schedule_binding,
)
from solana_alpha_lab.factory.tokens_v2_typed_projection import (
    FEATURE_FAMILY_MISSINGNESS,
    FEATURE_FAMILY_ORDER,
    FIELD_TO_FAMILY,
    PROJECTION_ID,
    PROJECTION_VERSION,
)

RELEASE_SCHEMA = "smial.live-cohort-discovery-release"
RELEASE_MANIFEST_NAME = "release_manifest.json"
CENSUS_NAME = "census.parquet"
OBSERVATIONS_NAME = "observations.parquet"
CLOSURE_NAME = "closure_receipt.json"
FRAMES_NAME = "frames.json"
PROTECTION_DIR = "protection"
RAW_DIR = "raw"
EXPORT_ROOT = "exports/opportunity_episodes"
CORPUS_DIR = "datasets/opportunity_episodes_corpus"
CORPUS_LINEAGE_REL = f"{CORPUS_DIR}/lineage.json"
CORPUS_SCHEMA_ID = "SCHEMA-OPPORTUNITY-EPISODES-DISCOVERY-CORPUS-001"
EVIDENCE_ROLE = "EXPLORATORY_REUSE"
CLOSURE_KIND = "OPPORTUNITY_EPISODES_COHORT_CLOSURE_V1"
TRANSFER_KIND = "OPPORTUNITY_EPISODES_BOUNDED_TRANSFER_MANIFEST"
IMPORT_GENERATION_TASK = "OPPORTUNITY-EPISODES-JUPITER-VERTICAL-SLICE-V1"
OPEN_SLOT_STATES = ("PENDING", "DUE", "CLAIMED")
EXPECTED_POINTS = episode_point_ids()
PASS_ALREADY_PRESENT_EXACT = "PASS_ALREADY_PRESENT_EXACT"

EPISODE_CENSUS_COLUMNS = (
    "release_id",
    "cohort_id",
    "collection",
    "population",
    "population_contract",
    "anchor_kind",
    "schedule_sha256",
    "activation_id",
    "episode_id",
    "mint",
    "t0",
    "cycle_start",
    "ticket_priority",
    "collection_lineage_id",
    "round_id",
    "frame_sha256",
    "protection_fingerprint",
    "asset_class",
    "witness_source_id",
    "witness_rank",
    "witness_object_sha256",
    "witness_call_occurrence_id",
    "witness_request_started_at",
    "witness_response_received_at",
    "witness_first_reliable_available_at",
    "witness_response_sha256",
    "admission_content_sha256",
    "membership_state",
    "evidence_role",
)
EPISODE_CENSUS_SCHEMA = pa.schema([pa.field(name, pa.string()) for name in EPISODE_CENSUS_COLUMNS])
EPISODE_OBS_SCHEMA = pa.schema(
    [
        pa.field("release_id", pa.string()),
        pa.field("cohort_id", pa.string()),
        pa.field("episode_id", pa.string()),
        pa.field("mint", pa.string()),
        pa.field("point_id", pa.string()),
        pa.field("primitive_id", pa.string()),
        pa.field("field_id", pa.string()),
        pa.field("value_kind", pa.string()),
        pa.field("typed_value", pa.string()),
        pa.field("state", pa.string()),
        pa.field("missing_reason", pa.string()),
        pa.field("event_time", pa.string()),
        pa.field("nominal_due_at", pa.string()),
        pa.field("assigned_at", pa.string()),
        pa.field("request_not_before", pa.string()),
        pa.field("availability_deadline", pa.string()),
        pa.field("request_started_at", pa.string()),
        pa.field("response_received_at", pa.string()),
        pa.field("first_reliable_available_at", pa.string()),
        pa.field("request_sha256", pa.string()),
        pa.field("response_sha256", pa.string()),
        pa.field("call_occurrence_id", pa.string()),
        pa.field("http_status", pa.int64()),
        pa.field("http_class", pa.string()),
        pa.field("observation_clock_policy", pa.string()),
        pa.field("source_price_event_time", pa.string()),
        pa.field("member_anchor", pa.string()),
        pa.field("raw_body_rel", pa.string()),
        pa.field("evidence_role", pa.string()),
        pa.field("confirmatory_reuse_forbidden", pa.bool_()),
    ]
)
_TERMINAL_ROW_STATES = frozenset(
    {
        "OBSERVED",
        "MISSING_TYPED",
        "EXCLUDED_AMBIGUOUS",
        "DISAPPEARED",
        "CENSORED",
        "CENSORED_LATE",
        "IN_FLIGHT_CALL_INDETERMINATE",
        "DEPENDENCY_MISSING",
        "BLOCKED_BUDGET",
    }
)


from solana_alpha_lab.factory.live_cohort_discovery_release import (  # noqa: E402
    LiveCohortReleaseError,
)


class EpisodeReleaseError(LiveCohortReleaseError):
    """Typed fail-closed episode release failure (ordinary release terminal)."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise EpisodeReleaseError(code)


def _safe_rel(rel: str) -> str:
    text = str(rel or "").replace("\\", "/")
    posix = PurePosixPath(text)
    _require(bool(text) and not posix.is_absolute() and ".." not in posix.parts, "PATH_ESCAPE")
    _require(":" not in text.split("/")[0], "PATH_ESCAPE")
    return text


def _contained(root: Path, rel: str) -> Path:
    path = Path(root) / _safe_rel(rel)
    resolved_root = Path(root).resolve()
    _require(path.resolve().is_relative_to(resolved_root), "PATH_ESCAPE")
    for item in (path, *path.parents):
        if item == Path(root):
            break
        _require(not item.is_symlink(), "PATH_ESCAPE")
    return path


def _write_json(path: Path, payload: Mapping[str, Any] | list[Any]) -> bytes:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    _publish_bytes(path, data)
    return data


# --------------------------------------------------------------------------
# Capture host: maturity, closure receipt, export bundle, transfer manifest


def episode_activations(store) -> list[dict[str, Any]]:
    found = []
    for row in store.list_activations():
        registered = store.get_registered_schedule(str(row["schedule_sha256"]))
        if registered is not None and is_episode_schedule(registered["document"]):
            found.append({**dict(row), "document": registered["document"]})
    return found


def _cohort_status(store, *, data_root: Path, schedule_sha256: str, activation_id: str, cohort_id: str, as_of: datetime) -> dict[str, Any]:
    from solana_alpha_lab.factory.observation_panel_publisher import has_open_publication_jobs

    _start, end = cohort_day_bounds(cohort_id)
    admissions = store.list_episode_admissions(
        schedule_sha256=schedule_sha256, activation_id=activation_id, cohort_id=cohort_id
    )
    episode_ids = [str(item["episode_id"]) for item in admissions]
    slot_counts = store.episode_slot_state_counts(
        schedule_sha256=schedule_sha256, activation_id=activation_id, episode_ids=episode_ids
    )
    open_slots = sum(int(slot_counts.get(state, 0)) for state in OPEN_SLOT_STATES)
    unpublished = store.episode_unpublished_count(
        schedule_sha256=schedule_sha256, activation_id=activation_id, cohort_id=cohort_id
    )
    open_jobs = has_open_publication_jobs(
        data_root=Path(data_root), schedule_sha256=schedule_sha256, activation_id=activation_id
    )
    reasons = []
    if as_of < end:
        reasons.append("ADMISSION_DAY_OPEN")
    if open_slots:
        reasons.append("SLOT_OBLIGATIONS_OPEN")
    if unpublished:
        reasons.append("OUTBOX_UNPUBLISHED")
    if open_jobs:
        reasons.append("PUBLICATION_JOB_OPEN")
    if not admissions:
        reasons.append("COHORT_EMPTY")
    return {
        "admissions": admissions,
        "slot_state_counts": dict(sorted(slot_counts.items())),
        "open_slots": open_slots,
        "unpublished_outbox": unpublished,
        "open_publication_jobs": bool(open_jobs),
        "mature": not reasons,
        "blocking_reasons": reasons,
    }


def select_next_mature_episode_cohort(
    *,
    ops_store: Path,
    observation_rdp: Path,
    imported: set[str],
    as_of: datetime,
) -> dict[str, Any] | None:
    """Oldest mature unimported (collection, cohort) by real obligations."""

    from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore

    store = ObservationScheduleStore(Path(ops_store))
    try:
        candidates = []
        pending = []
        cohort_scopes: dict[str, set[tuple[str, str]]] = {}
        for activation in episode_activations(store):
            digest = str(activation["schedule_sha256"])
            activation_id = str(activation["activation_id"])
            cohort_ids = sorted(
                {str(item["cohort_id"]) for item in store.list_episode_admissions(schedule_sha256=digest, activation_id=activation_id)}
            )
            for cohort_id in cohort_ids:
                cohort_scopes.setdefault(cohort_id, set()).add((digest, activation_id))
                if cohort_id in imported:
                    continue
                status = _cohort_status(
                    store,
                    data_root=Path(observation_rdp),
                    schedule_sha256=digest,
                    activation_id=activation_id,
                    cohort_id=cohort_id,
                    as_of=as_of,
                )
                item = {
                    "collection": COLLECTION,
                    "cohort_id": cohort_id,
                    "schedule_sha256": digest,
                    "activation_id": activation_id,
                    "blocking_reasons": status["blocking_reasons"],
                }
                (candidates if status["mature"] else pending).append(item)
        _require(all(len(scopes) == 1 for scopes in cohort_scopes.values()),
                 "EPISODE_COHORT_FRAGMENTED_UNSUPPORTED")
        candidates.sort(key=lambda item: (item["cohort_id"], item["schedule_sha256"], item["activation_id"]))
        if not candidates:
            return {"terminal": "NO_MATURE_UNIMPORTED_COHORT", "pending": pending} if pending else None
        chosen = dict(candidates[0])
        chosen["terminal"] = "MATURE"
        return chosen
    finally:
        store.close()


def build_episode_closure_receipt(
    *,
    ops_store: Path,
    observation_rdp: Path,
    schedule_sha256: str,
    activation_id: str,
    cohort_id: str,
    as_of: datetime,
) -> dict[str, Any]:
    """Frozen closure from producer state. Never built by a consumer."""

    from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore

    store = ObservationScheduleStore(Path(ops_store))
    try:
        registered = store.get_registered_schedule(schedule_sha256)
        _require(registered is not None and is_episode_schedule(registered["document"]), "EPISODE_SCHEDULE_UNREGISTERED")
        scopes = {(str(item["schedule_sha256"]), str(item["activation_id"]))
                  for item in episode_activations(store)
                  if any(str(row["cohort_id"]) == cohort_id for row in store.list_episode_admissions(
                      schedule_sha256=str(item["schedule_sha256"]), activation_id=str(item["activation_id"])))}
        _require(scopes == {(schedule_sha256, activation_id)}, "EPISODE_COHORT_FRAGMENTED_UNSUPPORTED")
        status = _cohort_status(
            store,
            data_root=Path(observation_rdp),
            schedule_sha256=schedule_sha256,
            activation_id=activation_id,
            cohort_id=cohort_id,
            as_of=as_of,
        )
        start, end = cohort_day_bounds(cohort_id)
        publications = store.episode_publications_for_cohort(
            schedule_sha256=schedule_sha256, activation_id=activation_id, cohort_id=cohort_id
        )
        rounds = store.list_episode_rounds(
            schedule_sha256=schedule_sha256,
            activation_id=activation_id,
            started_from=start,
            started_before=end,
        )
        document = dict(registered["document"])
    finally:
        store.close()
    episodes = [
        {
            "episode_id": str(item["episode_id"]),
            "mint": str(item["mint"]),
            "t0": str(item["t0"]),
            "admission_content_sha256": str(item["content_sha256"]),
        }
        for item in status["admissions"]
    ]
    receipt = {
        "kind": CLOSURE_KIND,
        "collection": COLLECTION,
        "schedule_sha256": schedule_sha256,
        "schedule_contract": SCHEDULE_CONTRACT,
        "activation_id": activation_id,
        "cohort_id": cohort_id,
        "window_start": render_utc(start),
        "window_end_exclusive": render_utc(end),
        "as_of": render_utc(as_of),
        "admissions_n": len(episodes),
        "episodes": episodes,
        "slot_state_counts": status["slot_state_counts"],
        "open_slots": status["open_slots"],
        "unpublished_outbox": status["unpublished_outbox"],
        "open_publication_jobs": status["open_publication_jobs"],
        "closure_ready": bool(status["mature"]),
        "blocking_reasons": status["blocking_reasons"],
        "publications": [
            {
                "content_sha256": str(item["content_sha256"]),
                "dataset_manifest_id": str(item["dataset_manifest_id"]),
            }
            for item in publications
        ],
        "rounds": [
            {
                "round_id": str(item["round_id"]),
                "round_started_at": str(item["round_started_at"]),
                "state": str(item["state"]),
                "frame_sha256": (item.get("frame") or {}).get("frame_sha256"),
            }
            for item in rounds
        ],
        "protection_sources": list(document["protection"]["assignment_sources"]),
        "schedule_binding": schedule_binding(document),
    }
    receipt["closure_receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def assert_episode_closure_ready(receipt: Mapping[str, Any]) -> None:
    _require(receipt.get("kind") == CLOSURE_KIND, "CLOSURE_KIND_MISMATCH")
    body = {key: value for key, value in receipt.items() if key != "closure_receipt_sha256"}
    _require(canonical_sha256(body) == receipt.get("closure_receipt_sha256"), "CLOSURE_RECEIPT_TAMPERED")
    if not receipt.get("closure_ready"):
        reasons = list(receipt.get("blocking_reasons") or ["COHORT_NOT_CLOSED"])
        raise EpisodeReleaseError(str(reasons[0]))


def export_dir_rel(receipt: Mapping[str, Any]) -> str:
    return (
        f"{EXPORT_ROOT}/{str(receipt['schedule_sha256'])[:16]}/"
        f"{receipt['activation_id']}/{receipt['cohort_id']}"
    )


def pinned_protection_sources(sources: object) -> list[dict[str, str]]:
    """The protection sources frozen into the schedule: id + semantic sha, unique, non-empty."""

    _require(isinstance(sources, (list, tuple)) and len(sources) > 0, "FROZEN_PROTECTION_SOURCES_EMPTY")
    pinned: dict[str, str] = {}
    for item in sources:
        _require(isinstance(item, Mapping), "FROZEN_PROTECTION_PIN_INVALID")
        assignment_id = str(item.get("assignment_id") or "")
        sha = str(item.get("sha256") or "")
        _require(
            bool(assignment_id) and not any(ch in assignment_id for ch in "/\\:") and ".." not in assignment_id
            and len(sha) == 64 and all(ch in "0123456789abcdef" for ch in sha),
            "FROZEN_PROTECTION_PIN_INVALID",
        )
        _require(assignment_id not in pinned, "FROZEN_PROTECTION_PIN_DUPLICATE")
        pinned[assignment_id] = sha
    return [{"assignment_id": key, "sha256": pinned[key]} for key in sorted(pinned)]


def load_pinned_assignment(directory: Path, source: Mapping[str, str]) -> tuple[Mapping[str, Any], bytes]:
    """One frozen assignment: exists, regular file, readable, exact semantic identity.

    A current file never stands in for the admission-time policy: its semantic
    hash must equal the pin frozen in the schedule.
    """

    assignment_id = str(source["assignment_id"])
    path = Path(directory) / f"{assignment_id}.json"
    _require(path.is_file() and not path.is_symlink(), f"FROZEN_PROTECTION_MISSING:{assignment_id}")
    try:
        raw = path.read_bytes()
        document = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EpisodeReleaseError(f"FROZEN_PROTECTION_UNREADABLE:{assignment_id}") from exc
    _require(isinstance(document, Mapping), f"FROZEN_PROTECTION_UNREADABLE:{assignment_id}")
    _require(str(document.get("assignment_id") or "") == assignment_id, f"FROZEN_PROTECTION_IDENTITY_MISMATCH:{assignment_id}")
    _require(assignment_document_sha256(document) == str(source["sha256"]), f"FROZEN_PROTECTION_HASH_MISMATCH:{assignment_id}")
    completeness = document.get("completeness")
    _require(
        isinstance(completeness, Mapping) and completeness.get("complete") is True,
        f"FROZEN_PROTECTION_INCOMPLETE:{assignment_id}",
    )
    return document, raw


def frozen_protection_from_release(
    root: Path,
    *,
    listed: Mapping[str, Any] | None = None,
    expected_schedule_sha256: str | None = None,
) -> list[Mapping[str, Any]]:
    """Independently confirm the release carries exactly the pinned assignments.

    The pins come from the schedule artifact and must equal the closure's; the
    protection directory (and the manifest listing when given) holds exactly
    those files, each with its pinned semantics.
    """

    root = Path(root)
    closure = json.loads((root / CLOSURE_NAME).read_text(encoding="utf-8"))
    if expected_schedule_sha256 is not None:
        # The schedule this release was sealed and imported under, not whichever
        # closure sits in the directory.
        _require(str(closure.get("schedule_sha256") or "") == str(expected_schedule_sha256), "FROZEN_PROTECTION_SCHEDULE_MISMATCH")
    try:
        schedule_document = decode_schedule_artifact(
            (root / OBSERVATION_SCHEDULE_ARTIFACT_NAME).read_bytes(),
            wanted_sha=str(closure.get("schedule_sha256") or ""),
        )
    except ValueError as exc:
        raise EpisodeReleaseError(str(exc)) from exc
    pinned = pinned_protection_sources((schedule_document.get("protection") or {}).get("assignment_sources"))
    _require(pinned == pinned_protection_sources(closure.get("protection_sources")), "FROZEN_PROTECTION_CLOSURE_MISMATCH")
    expected = {f"{PROTECTION_DIR}/{item['assignment_id']}.json" for item in pinned}
    if listed is not None:
        _require({rel for rel in listed if rel.startswith(PROTECTION_DIR + "/")} == expected, "FROZEN_PROTECTION_SET_MISMATCH")
    directory = root / PROTECTION_DIR
    present = {f"{PROTECTION_DIR}/{path.name}" for path in directory.iterdir()} if directory.is_dir() else set()
    _require(present == expected, "FROZEN_PROTECTION_SET_MISMATCH")
    return [load_pinned_assignment(directory, item)[0] for item in pinned]


def write_episode_export(*, observation_rdp: Path, ops_store: Path, receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Capture-produced bundle: receipt, schedule artifact, frames, protection."""

    from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore

    root = Path(observation_rdp)
    base = _contained(root, export_dir_rel(receipt))
    store = ObservationScheduleStore(Path(ops_store))
    try:
        registered = store.get_registered_schedule(str(receipt["schedule_sha256"]))
        _require(registered is not None, "EPISODE_SCHEDULE_UNREGISTERED")
        document = dict(registered["document"])
        start, end = cohort_day_bounds(str(receipt["cohort_id"]))
        rounds = store.list_episode_rounds(
            schedule_sha256=str(receipt["schedule_sha256"]),
            activation_id=str(receipt["activation_id"]),
            started_from=start,
            started_before=end,
        )
    finally:
        store.close()
    _validated, artifact_bytes, artifact_sha = encode_schedule_artifact(
        document, wanted_sha=str(receipt["schedule_sha256"])
    )
    # Admission-time policy only: the schedule's frozen pins, read from the
    # registered assignment files, before any export byte exists.
    pinned = pinned_protection_sources((document.get("protection") or {}).get("assignment_sources"))
    _require(pinned == pinned_protection_sources(receipt.get("protection_sources")), "FROZEN_PROTECTION_RECEIPT_MISMATCH")
    assignment_dir = _contained(root, "protection/assignments")
    frozen_assignments = [(item, *load_pinned_assignment(assignment_dir, item)) for item in pinned]
    base.mkdir(parents=True, exist_ok=True)
    _write_json(base / CLOSURE_NAME, receipt)
    schedule_path = base / OBSERVATION_SCHEDULE_ARTIFACT_NAME
    schedule_path.parent.mkdir(parents=True, exist_ok=True)
    _publish_bytes(schedule_path, artifact_bytes)
    frames = [
        {"round_id": item["round_id"], "state": item["state"], "frame": item.get("frame")}
        for item in rounds
    ]
    _write_json(base / FRAMES_NAME, frames)
    for item, _document, raw in frozen_assignments:
        dest = base / PROTECTION_DIR / f"{item['assignment_id']}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        _publish_bytes(dest, raw)
    return {"export_rel": export_dir_rel(receipt), "schedule_artifact_sha256": artifact_sha}


def _publication_files(root: Path, publication: Mapping[str, Any]) -> tuple[str, str, list[str]]:
    """(observations_rel, member_location, metadata rels) from the completed job."""

    from solana_alpha_lab.factory.observation_publication_jobs import completed_job_path

    content = str(publication["content_sha256"])
    mid = str(publication["dataset_manifest_id"])
    job_path = completed_job_path(Path(root), content)
    job_rel = job_path.relative_to(Path(root)).as_posix()
    _require(job_path.is_file() and not job_path.is_symlink(), f"DEPENDENCY_MISSING:{job_rel}")
    job = json.loads(job_path.read_text(encoding="utf-8"))
    _require(
        isinstance(job, Mapping)
        and str(job.get("dataset_manifest_id") or "") == mid
        and str(job.get("content_sha256") or "") == content
        and str(job.get("stage") or "") == "COMPLETE",
        "PUBLICATION_JOB_MISMATCH",
    )
    obs_rel = _safe_rel(str(job.get("parquet_rel") or ""))
    member_rel = _safe_rel(str(job.get("member_rel") or ""))
    obs_path = _contained(Path(root), obs_rel)
    _require(obs_path.is_file(), f"DEPENDENCY_MISSING:{obs_rel}")
    _require(sha256_file_streaming(obs_path) == str(job.get("file_sha256") or ""), f"PUBLICATION_HASH_MISMATCH:{obs_rel}")
    metadata = [job_rel]
    for rel in (f"datasets/manifests/{mid}.json", f"datasets/manifests/{mid}.published"):
        _require((Path(root) / rel).is_file(), f"DEPENDENCY_MISSING:{rel}")
        metadata.append(rel)
    return obs_rel, member_rel, metadata


def _read_observation_rows(root: Path, obs_rel: str) -> list[dict[str, Any]]:
    path = _contained(root, obs_rel)
    _require(path.is_file(), f"DEPENDENCY_MISSING:{obs_rel}")
    return [dict(row) for row in pq.read_table(path).to_pylist()]


def _read_member_rows(root: Path, member_rel: str) -> list[dict[str, Any]]:
    from solana_alpha_lab.factory.members_snapshot_delta import iter_member_row_batches_for_location

    rows: list[dict[str, Any]] = []
    for batch in iter_member_row_batches_for_location(Path(root), member_rel):
        rows.extend(dict(item) for item in batch)
    return rows


def collect_episode_transfer_manifest(*, observation_rdp: Path, receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Exactly the bytes one cohort needs: export bundle, publications, raw."""

    from solana_alpha_lab.factory.live_cohort_vanilla_path import _add_file, add_member_location_entries

    root = Path(observation_rdp)
    entries: dict[str, dict[str, Any]] = {}
    export_rel = export_dir_rel(receipt)
    export_root = _contained(root, export_rel)
    _require(export_root.is_dir(), "EXPORT_BUNDLE_MISSING")
    for path in sorted(export_root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            _add_file(entries, root, path.relative_to(root).as_posix(), "episode_export")
    cohort_id = str(receipt["cohort_id"])
    raw_rels: set[str] = set()
    for publication in receipt.get("publications") or []:
        obs_rel, member_rel, metadata = _publication_files(root, publication)
        for rel in metadata:
            _add_file(entries, root, rel, "publication_metadata")
        _add_file(entries, root, obs_rel, "observation_parquet")
        add_member_location_entries(entries, root, member_rel)
        for row in _read_observation_rows(root, obs_rel):
            if str(row.get("cohort_id") or "") != cohort_id:
                continue
            rel = row.get("raw_body_rel")
            if isinstance(rel, str) and rel:
                raw_rels.add(rel)
    for rel in sorted(raw_rels):
        _add_file(entries, root, _safe_rel(rel), "raw_body")
    ordered = [entries[key] for key in sorted(entries)]
    body = {
        "kind": TRANSFER_KIND,
        "schema_version": "1",
        "collection": COLLECTION,
        "activation_id": receipt["activation_id"],
        "cohort_id": cohort_id,
        "closure_receipt_sha256": receipt["closure_receipt_sha256"],
        "entries": ordered,
        "schedule_sha256": receipt["schedule_sha256"],
    }
    body["manifest_sha256"] = canonical_sha256(body)
    return body


def capture_freeze_export_episodes(
    *,
    observation_rdp: Path,
    ops_store: Path,
    imported_cohort_ids: set[str],
    as_of: datetime,
) -> dict[str, Any]:
    """Capture phase for the episode collection. No materialization/seal/import."""

    chosen = select_next_mature_episode_cohort(
        ops_store=Path(ops_store),
        observation_rdp=Path(observation_rdp),
        imported=set(imported_cohort_ids),
        as_of=as_of,
    )
    if chosen is None or chosen.get("terminal") != "MATURE":
        raise LiveCohortReleaseError("NO_MATURE_UNIMPORTED_COHORT")
    receipt = build_episode_closure_receipt(
        ops_store=Path(ops_store),
        observation_rdp=Path(observation_rdp),
        schedule_sha256=str(chosen["schedule_sha256"]),
        activation_id=str(chosen["activation_id"]),
        cohort_id=str(chosen["cohort_id"]),
        as_of=as_of,
    )
    assert_episode_closure_ready(receipt)
    closure_path = _contained(Path(observation_rdp), export_dir_rel(receipt)) / CLOSURE_NAME
    if closure_path.exists():
        _require(not closure_path.is_symlink() and closure_path.is_file(), "CLOSURE_FROZEN_UNSAFE")
        try:
            frozen = json.loads(closure_path.read_bytes())
            _require(isinstance(frozen, dict), "CLOSURE_FROZEN_UNREADABLE")
        except (OSError, ValueError) as exc:
            raise EpisodeReleaseError("CLOSURE_FROZEN_UNREADABLE") from exc
        assert_episode_closure_ready(frozen)
        identity_keys = set(receipt) - {"as_of", "closure_receipt_sha256"}
        _require(set(frozen) == set(receipt)
                 and all(frozen.get(key) == receipt[key] for key in identity_keys),
                 "CLOSURE_FROZEN_STATE_CONFLICT")
        _require(parse_utc(str(frozen["as_of"])) <= as_of, "CLOSURE_AS_OF_REGRESSION")
        receipt = frozen
    export = write_episode_export(observation_rdp=Path(observation_rdp), ops_store=Path(ops_store), receipt=receipt)
    manifest = collect_episode_transfer_manifest(observation_rdp=Path(observation_rdp), receipt=receipt)
    return {
        "collection": COLLECTION,
        "activations": [],
        "rollovers": [],
        "closure_receipt": receipt,
        "cohort_id": receipt["cohort_id"],
        "export": export,
        "transfer_manifest": manifest,
    }


# --------------------------------------------------------------------------
# Workstation: bounded source build from the mirror


def _row_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row.get("episode_id") or row.get("entity_id") or ""), str(row.get("point_id") or "")


def build_episode_source(*, mirror_root: Path, receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Members + observation rows of exactly one cohort, integrity-checked."""

    assert_episode_closure_ready(receipt)
    root = Path(mirror_root)
    cohort_id = str(receipt["cohort_id"])
    expected = {str(item["episode_id"]): item for item in receipt.get("episodes") or []}
    members: dict[str, dict[str, Any]] = {}
    observations: dict[tuple[str, str], dict[str, Any]] = {}
    duplicate_copies = 0
    for publication in receipt.get("publications") or []:
        obs_rel, member_rel, _metadata = _publication_files(root, publication)
        for row in _read_member_rows(root, member_rel):
            if str(row.get("cohort_id") or "") != cohort_id:
                continue
            episode_id = str(row.get("episode_id") or "")
            normalized = dict(row)
            previous = members.get(episode_id)
            if previous is not None:
                _require(admission_content_sha256(previous) == admission_content_sha256(normalized), "MEMBER_COPY_CONFLICT")
                continue
            members[episode_id] = normalized
        for row in _read_observation_rows(root, obs_rel):
            if str(row.get("cohort_id") or "") != cohort_id:
                continue
            key = _row_key(row)
            previous_obs = observations.get(key)
            if previous_obs is not None:
                _require(canonical_sha256(previous_obs) == canonical_sha256(row), "OBSERVATION_COPY_CONFLICT")
                duplicate_copies += 1
                continue
            observations[key] = row
    _require(set(members) == set(expected), "ADMISSION_SET_MISMATCH")
    for episode_id, item in expected.items():
        _require(
            admission_content_sha256(members[episode_id]) == str(item["admission_content_sha256"]),
            "ADMISSION_CONTENT_MISMATCH",
        )
    for episode_id in expected:
        points = {point for (ep, point) in observations if ep == episode_id}
        _require(points == set(EXPECTED_POINTS), "OBSERVATION_OBLIGATIONS_INCOMPLETE")
        for point in EXPECTED_POINTS:
            _require(str(observations[(episode_id, point)].get("state") or "") in _TERMINAL_ROW_STATES, "OBSERVATION_NOT_TERMINAL")
    _require(not any(ep not in expected for ep, _point in observations), "OBSERVATION_UNADMITTED_EPISODE")
    source_sha = canonical_sha256(
        {
            "members": [members[key] for key in sorted(members)],
            "observations": [canonical_sha256(observations[key]) for key in sorted(observations)],
        }
    )
    return {
        "receipt": dict(receipt),
        "members": [members[key] for key in sorted(members)],
        "observations": [observations[key] for key in sorted(observations)],
        "source_sha256": source_sha,
        "duplicate_copies": duplicate_copies,
    }


# --------------------------------------------------------------------------
# Immutable release 1.2


def release_id_for_episodes(receipt: Mapping[str, Any], source_sha256: str) -> str:
    return canonical_sha256(
        {
            "schema": RELEASE_SCHEMA,
            "schema_version": RELEASE_SCHEMA_VERSION_EPISODES,
            "collection": COLLECTION,
            "cohort_id": receipt["cohort_id"],
            "schedule_sha256": receipt["schedule_sha256"],
            "activation_id": receipt["activation_id"],
            "closure_receipt_sha256": receipt["closure_receipt_sha256"],
            "source_sha256": source_sha256,
            "projection_id": PROJECTION_ID,
            "projection_version": PROJECTION_VERSION,
        }
    )


def _census_rows(source: Mapping[str, Any], release_id: str) -> list[dict[str, Any]]:
    rows = []
    for member in source["members"]:
        row = {name: None for name in EPISODE_CENSUS_COLUMNS}
        for key in EPISODE_CENSUS_COLUMNS:
            if key in member and member[key] is not None:
                row[key] = str(member[key])
        row.update(
            release_id=release_id,
            cohort_id=str(source["receipt"]["cohort_id"]),
            collection=COLLECTION,
            population=POPULATION,
            population_contract=POPULATION_CONTRACT,
            anchor_kind=ANCHOR_KIND,
            admission_content_sha256=admission_content_sha256(member),
            membership_state="ADMITTED",
            evidence_role=EVIDENCE_ROLE,
        )
        rows.append(row)
    return rows


def _release_raw_rel(rel: object) -> str | None:
    if not isinstance(rel, str) or not rel:
        return None
    return f"{RAW_DIR}/{PurePosixPath(rel).name}"


def _observation_rows(source: Mapping[str, Any], release_id: str) -> list[dict[str, Any]]:
    rows = []
    cohort_id = str(source["receipt"]["cohort_id"])
    for obs in source["observations"]:
        http_status = obs.get("http_status")
        try:
            http_status = None if http_status in (None, "") else int(http_status)
        except (TypeError, ValueError):
            http_status = None
        for value in obs.get("field_values") or []:
            rows.append(
                {
                    "release_id": release_id,
                    "cohort_id": cohort_id,
                    "episode_id": str(obs.get("episode_id") or obs.get("entity_id")),
                    "mint": str(obs.get("mint")),
                    "point_id": str(obs.get("point_id")),
                    "primitive_id": obs.get("primitive_id"),
                    "field_id": value.get("field_id"),
                    "value_kind": value.get("value_kind"),
                    "typed_value": value.get("typed_value_or_null"),
                    "state": value.get("state"),
                    "missing_reason": value.get("missing_reason"),
                    "event_time": obs.get("event_time"),
                    "nominal_due_at": obs.get("nominal_due_at"),
                    "assigned_at": obs.get("assigned_at"),
                    "request_not_before": obs.get("request_not_before"),
                    "availability_deadline": obs.get("availability_deadline"),
                    "request_started_at": obs.get("request_started_at"),
                    "response_received_at": obs.get("response_received_at"),
                    "first_reliable_available_at": obs.get("first_reliable_available_at"),
                    "request_sha256": obs.get("request_sha256"),
                    "response_sha256": obs.get("response_sha256"),
                    "call_occurrence_id": obs.get("call_occurrence_id"),
                    "http_status": http_status,
                    "http_class": obs.get("http_class"),
                    "observation_clock_policy": obs.get("observation_clock_policy"),
                    "source_price_event_time": obs.get("source_price_event_time"),
                    "member_anchor": obs.get("member_anchor"),
                    "raw_body_rel": _release_raw_rel(obs.get("raw_body_rel")),
                    "evidence_role": EVIDENCE_ROLE,
                    "confirmatory_reuse_forbidden": True,
                }
            )
    rows.sort(key=lambda row: (row["episode_id"], int(str(row["point_id"])[1:]), str(row["field_id"])))
    return rows


def _write_table(path: Path, rows: Sequence[Mapping[str, Any]], schema: pa.Schema) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist([dict(row) for row in rows], schema=schema)
    tmp = path.with_name(f".{path.name}.tmp")
    pq.write_table(table, tmp, compression="zstd", compression_level=3)
    tmp.replace(path)
    return sha256_file_streaming(path)


def _feature_families(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    observed: set[str] = set()
    missing = False
    for row in rows:
        family = FIELD_TO_FAMILY.get(str(row.get("field_id") or ""))
        if row.get("state") == "OBSERVED" and family is not None:
            observed.add(family)
        elif row.get("state") != "OBSERVED":
            missing = True
    if missing:
        observed.add(FEATURE_FAMILY_MISSINGNESS)
    return [item for item in FEATURE_FAMILY_ORDER if item in observed]


def episode_release_files(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The one dependency resolver for hash, verify, transport, import and cold package."""

    files = manifest.get("files")
    _require(isinstance(files, list) and files, "RELEASE_FILES_MISSING")
    seen: set[str] = set()
    resolved = []
    for item in files:
        _require(isinstance(item, Mapping), "RELEASE_FILES_INVALID")
        rel = _safe_rel(str(item.get("path") or ""))
        _require(rel not in seen, "RELEASE_FILES_DUPLICATE")
        seen.add(rel)
        sha = str(item.get("sha256") or "")
        _require(len(sha) == 64, "RELEASE_FILES_INVALID")
        resolved.append({"path": rel, "sha256": sha, "bytes": int(item.get("bytes") or 0)})
    return resolved


def seal_episode_cohort(
    *,
    mirror_root: Path,
    receipt: Mapping[str, Any],
    release_root: Path,
    sealed_at: datetime,
    release_builder_git_sha: str | None = None,
) -> dict[str, Any]:
    source = build_episode_source(mirror_root=mirror_root, receipt=receipt)
    release_id = release_id_for_episodes(receipt, source["source_sha256"])
    root = Path(release_root)
    existing = root / RELEASE_MANIFEST_NAME
    if existing.is_file():
        manifest = json.loads(existing.read_text(encoding="utf-8"))
        _require(manifest.get("release_id") == release_id, "RELEASE_IDENTITY_CONFLICT")
        verify_episode_release(root)
        return manifest
    root.mkdir(parents=True, exist_ok=True)
    mirror = Path(mirror_root)
    export_root = _contained(mirror, export_dir_rel(receipt))
    census = _census_rows(source, release_id)
    obs_rows = _observation_rows(source, release_id)
    files: list[dict[str, Any]] = []

    def add(rel: str, path: Path) -> None:
        files.append({"path": rel, "sha256": sha256_file_streaming(path), "bytes": int(path.stat().st_size)})

    census_sha = _write_table(root / CENSUS_NAME, census, EPISODE_CENSUS_SCHEMA)
    obs_sha = _write_table(root / OBSERVATIONS_NAME, obs_rows, EPISODE_OBS_SCHEMA)
    add(CENSUS_NAME, root / CENSUS_NAME)
    add(OBSERVATIONS_NAME, root / OBSERVATIONS_NAME)
    schedule_bytes = (export_root / OBSERVATION_SCHEDULE_ARTIFACT_NAME).read_bytes()
    decode_schedule_artifact(schedule_bytes, wanted_sha=str(receipt["schedule_sha256"]))
    _publish_bytes(root / OBSERVATION_SCHEDULE_ARTIFACT_NAME, schedule_bytes)
    add(OBSERVATION_SCHEDULE_ARTIFACT_NAME, root / OBSERVATION_SCHEDULE_ARTIFACT_NAME)
    for name in (CLOSURE_NAME, FRAMES_NAME):
        _publish_bytes(root / name, (export_root / name).read_bytes())
        add(name, root / name)
    sealed_schedule = decode_schedule_artifact(schedule_bytes, wanted_sha=str(receipt["schedule_sha256"]))
    pinned = pinned_protection_sources((sealed_schedule.get("protection") or {}).get("assignment_sources"))
    _require(pinned == pinned_protection_sources(receipt.get("protection_sources")), "FROZEN_PROTECTION_CLOSURE_MISMATCH")
    export_protection = export_root / PROTECTION_DIR
    exported = {path.name for path in export_protection.iterdir()} if export_protection.is_dir() else set()
    _require(exported == {f"{item['assignment_id']}.json" for item in pinned}, "FROZEN_PROTECTION_SET_MISMATCH")
    for item in pinned:
        _document, raw = load_pinned_assignment(export_protection, item)
        rel = f"{PROTECTION_DIR}/{item['assignment_id']}.json"
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        _publish_bytes(dest, raw)
        add(rel, dest)
    raw_needed = sorted(
        {str(obs.get("raw_body_rel")) for obs in source["observations"] if obs.get("raw_body_rel")}
        | {str(member.get("witness_raw_body_rel")) for member in source["members"] if member.get("witness_raw_body_rel")}
    )
    raw_added: set[str] = set()
    for rel in raw_needed:
        src = _contained(mirror, rel)
        _require(src.is_file(), f"RAW_DEPENDENCY_MISSING:{PurePosixPath(rel).name}")
        dest_rel = _release_raw_rel(rel)
        assert dest_rel is not None
        dest = root / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.is_file():
            _publish_bytes(dest, src.read_bytes())
        _require(sha256_file_streaming(dest) == sha256_file_streaming(src), "RAW_BODY_IDENTITY_CONFLICT")
        if dest_rel not in raw_added:
            raw_added.add(dest_rel)
            add(dest_rel, dest)
    counts: dict[str, int] = {}
    for row in obs_rows:
        counts[str(row["state"])] = counts.get(str(row["state"]), 0) + 1
    mints = [str(row["mint"]) for row in census]
    manifest = {
        "schema": RELEASE_SCHEMA,
        "schema_version": RELEASE_SCHEMA_VERSION_EPISODES,
        "collection": COLLECTION,
        "release_id": release_id,
        "cohort_id": receipt["cohort_id"],
        "sealed_at": render_utc(sealed_at),
        "schedule_sha256": receipt["schedule_sha256"],
        "schedule_contract": SCHEDULE_CONTRACT,
        "activation_id": receipt["activation_id"],
        "population": POPULATION,
        "population_contract": POPULATION_CONTRACT,
        "anchor_kind": ANCHOR_KIND,
        "logical_dataset_id": LOGICAL_DATASET_ID,
        "source_sha256": source["source_sha256"],
        "closure_receipt_sha256": receipt["closure_receipt_sha256"],
        "evidence_role": EVIDENCE_ROLE,
        "confirmatory_reuse_forbidden": True,
        "census_sha256": census_sha,
        "observations_sha256": obs_sha,
        "census_row_count": len(census),
        "observation_row_count": len(obs_rows),
        "admissions_n": len(census),
        "distinct_mint_n": len(set(mints)),
        "repeated_mint_n": len(mints) - len(set(mints)),
        "observation_field_state_counts": dict(sorted(counts.items())),
        "feature_families": _feature_families(obs_rows),
        "observation_schedule_artifact": OBSERVATION_SCHEDULE_ARTIFACT_NAME,
        "observation_schedule_sha256": sha256_file_streaming(root / OBSERVATION_SCHEDULE_ARTIFACT_NAME),
        "schedule_binding": dict(receipt["schedule_binding"]),
        "projection_id": PROJECTION_ID,
        "projection_version": PROJECTION_VERSION,
        "duplicate_delivery_copies": int(source["duplicate_copies"]),
        "files": sorted(files, key=lambda item: item["path"]),
    }
    if release_builder_git_sha:
        manifest["release_builder_git_sha"] = str(release_builder_git_sha)
    _write_json(root / RELEASE_MANIFEST_NAME, manifest)
    return manifest


def verify_episode_release(release_root: Path) -> dict[str, Any]:
    root = Path(release_root)
    manifest_path = root / RELEASE_MANIFEST_NAME
    _require(manifest_path.is_file() and not manifest_path.is_symlink(), "RELEASE_MANIFEST_MISSING")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EpisodeReleaseError("RELEASE_MANIFEST_CORRUPT") from exc
    _require(isinstance(manifest, Mapping), "RELEASE_MANIFEST_CORRUPT")
    _require(manifest.get("schema") == RELEASE_SCHEMA, "RELEASE_SCHEMA_MISMATCH")
    _require(manifest.get("schema_version") == RELEASE_SCHEMA_VERSION_EPISODES, "RELEASE_SCHEMA_MISMATCH")
    _require(manifest.get("collection") == COLLECTION, "RELEASE_COLLECTION_MISMATCH")
    _require(manifest.get("population") == POPULATION and manifest.get("anchor_kind") == ANCHOR_KIND, "RELEASE_POPULATION_MISMATCH")
    _require(manifest.get("evidence_role") == EVIDENCE_ROLE and manifest.get("confirmatory_reuse_forbidden") is True, "EVIDENCE_ROLE_MISMATCH")
    listed = {item["path"]: item for item in episode_release_files(manifest)}
    for required in (CENSUS_NAME, OBSERVATIONS_NAME, OBSERVATION_SCHEDULE_ARTIFACT_NAME, CLOSURE_NAME, FRAMES_NAME):
        _require(required in listed, "RELEASE_FILES_INCOMPLETE")
    for rel, item in listed.items():
        path = _contained(root, rel)
        _require(path.is_file() and not path.is_symlink(), f"RELEASE_DEPENDENCY_MISSING:{rel}")
        _require(sha256_file_streaming(path) == item["sha256"], f"RELEASE_HASH_MISMATCH:{rel}")
    _require(listed[CENSUS_NAME]["sha256"] == manifest.get("census_sha256"), "CENSUS_HASH_MISMATCH")
    _require(listed[OBSERVATIONS_NAME]["sha256"] == manifest.get("observations_sha256"), "OBSERVATIONS_HASH_MISMATCH")
    schedule_bytes = (root / OBSERVATION_SCHEDULE_ARTIFACT_NAME).read_bytes()
    _require(listed[OBSERVATION_SCHEDULE_ARTIFACT_NAME]["sha256"] == manifest.get("observation_schedule_sha256"), "SCHEDULE_ARTIFACT_HASH_MISMATCH")
    try:
        decode_schedule_artifact(schedule_bytes, wanted_sha=str(manifest.get("schedule_sha256") or ""))
    except ValueError as exc:
        raise EpisodeReleaseError(str(exc)) from exc
    closure = json.loads((root / CLOSURE_NAME).read_text(encoding="utf-8"))
    assert_episode_closure_ready(closure)
    _require(closure.get("closure_receipt_sha256") == manifest.get("closure_receipt_sha256"), "CLOSURE_BINDING_MISMATCH")
    frozen_protection_from_release(root, listed=listed, expected_schedule_sha256=str(manifest.get("schedule_sha256") or ""))
    census = pq.read_table(root / CENSUS_NAME, columns=["schedule_sha256", "episode_id", "release_id"]).to_pylist()
    _require({row["schedule_sha256"] for row in census} == {manifest["schedule_sha256"]}, "CENSUS_SCHEDULE_SHA_MISMATCH")
    _require({row["release_id"] for row in census} == {manifest["release_id"]}, "IDENTITY_CONFLICT")
    _require({row["episode_id"] for row in census} == {item["episode_id"] for item in closure["episodes"]}, "ADMISSION_SET_MISMATCH")
    return dict(manifest)


# --------------------------------------------------------------------------
# Import into the separate episode corpus


def load_episode_lineage(data_root: Path) -> dict[str, Any]:
    path = Path(data_root) / CORPUS_LINEAGE_REL
    if not path.is_file():
        return {"corpus_dataset_id": LOGICAL_DATASET_ID, "collection": COLLECTION, "cohorts": []}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(loaded, Mapping) and loaded.get("corpus_dataset_id") == LOGICAL_DATASET_ID, "CORPUS_LINEAGE_CORRUPT")
    return dict(loaded)


def imported_episode_cohort_ids(data_root: Path) -> set[str]:
    return {str(item.get("cohort_id")) for item in load_episode_lineage(data_root).get("cohorts") or []}


def episode_corpus_schema_sha256() -> str:
    return canonical_sha256(
        {
            "schema_id": CORPUS_SCHEMA_ID,
            "census": [{"name": field.name, "type": str(field.type)} for field in EPISODE_CENSUS_SCHEMA],
            "observations": [{"name": field.name, "type": str(field.type)} for field in EPISODE_OBS_SCHEMA],
        }
    )


REQUIRED_EPISODE_LABELS = {
    "evidence_role": EVIDENCE_ROLE,
    "confirmatory_reuse_forbidden": True,
    "holdout": False,
    "outcome_previously_consumed": False,
    "population": POPULATION,
    "population_contract": POPULATION_CONTRACT,
    "anchor_kind": ANCHOR_KIND,
    "logical_dataset_id": LOGICAL_DATASET_ID,
    "collection": COLLECTION,
}


def _install_verified(src: Path, dest: Path, expected_sha: str) -> None:
    """Copy one release dependency; identical bytes are reused, others conflict."""

    dest.parent.mkdir(parents=True, exist_ok=True)
    _require(not dest.is_symlink(), "CANONICAL_TARGET_CONFLICT")
    if dest.is_file():
        _require(sha256_file_streaming(dest) == expected_sha, "CANONICAL_TARGET_CONFLICT")
        return
    tmp = dest.with_name(f".{dest.name}.tmp")
    shutil.copyfile(src, tmp)
    if sha256_file_streaming(tmp) != expected_sha:
        tmp.unlink(missing_ok=True)
        raise EpisodeReleaseError("TRANSPORT_HASH_MISMATCH")
    tmp.replace(dest)


def import_episode_release(
    *,
    release_root: Path,
    data_root: Path,
    import_time: datetime | None = None,
) -> dict[str, Any]:
    from solana_alpha_lab.storage.manifests import (
        build_dataset_manifest,
        build_partition_manifest,
        compute_dataset_manifest_id,
    )

    manifest = verify_episode_release(release_root)
    imported_at = (import_time or datetime.now(tz=UTC)).astimezone(UTC)
    _require(imported_at >= parse_utc(str(manifest["sealed_at"])), "IMPORT_BEFORE_SEAL")
    lineage = load_episode_lineage(data_root)
    cohorts = [dict(item) for item in lineage.get("cohorts") or []]
    release_id = str(manifest["release_id"])
    cohort_id = str(manifest["cohort_id"])
    for prior in cohorts:
        if prior.get("release_id") == release_id:
            _require(
                prior.get("census_sha256") == manifest["census_sha256"]
                and prior.get("observations_sha256") == manifest["observations_sha256"],
                "CANONICAL_TARGET_CONFLICT",
            )
            return {
                "status": PASS_ALREADY_PRESENT_EXACT,
                "collection": COLLECTION,
                "cohort_id": cohort_id,
                "release_id": release_id,
                "corpus_version": prior.get("corpus_version"),
                "dataset_manifest_id": lineage.get("current_dataset_manifest_id"),
                "epoch_bump": False,
            }
        _require(prior.get("cohort_id") != cohort_id, "COHORT_ALREADY_IMPORTED")
    base_rel = f"{CORPUS_DIR}/cohorts/{cohort_id}/{release_id[:16]}"
    base = _contained(Path(data_root), base_rel)
    for item in episode_release_files(manifest) + [{"path": RELEASE_MANIFEST_NAME, "sha256": sha256_file_streaming(Path(release_root) / RELEASE_MANIFEST_NAME)}]:
        src = _contained(Path(release_root), item["path"])
        dest = base / item["path"]
        _install_verified(src, dest, str(item["sha256"]))
    version_n = len(cohorts) + 1
    dataset_version = f"opportunity-episodes-v{version_n}-{cohort_id}"
    dataset_manifest_id = compute_dataset_manifest_id(LOGICAL_DATASET_ID, dataset_version)
    # The import instant is fixed once per corpus version before any manifest
    # byte exists, so repeating a torn import with any --as-of rewrites the
    # same bytes instead of conflicting with its own partial output.
    intent_path = _contained(Path(data_root), f"{CORPUS_DIR}/import_intents/{dataset_version}.json")
    if intent_path.is_file():
        intent = json.loads(intent_path.read_bytes())
        _require(
            isinstance(intent, dict)
            and intent.get("release_id") == release_id
            and intent.get("cohort_id") == cohort_id
            and isinstance(intent.get("imported_at"), str),
            "CANONICAL_TARGET_CONFLICT",
        )
        imported_at = parse_utc(str(intent["imported_at"]))
    else:
        imported_at = parse_utc(render_utc(imported_at))
        _publish_bytes(
            intent_path,
            json.dumps(
                {"cohort_id": cohort_id, "release_id": release_id, "imported_at": render_utc(imported_at)},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
        )
    component = {
        "cohort_id": cohort_id,
        "release_id": release_id,
        "collection": COLLECTION,
        "corpus_version": version_n,
        "sealed_at": manifest["sealed_at"],
        "imported_at": render_utc(imported_at),
        "census_rel": f"{base_rel}/{CENSUS_NAME}",
        "obs_rel": f"{base_rel}/{OBSERVATIONS_NAME}",
        "census_sha256": manifest["census_sha256"],
        "observations_sha256": manifest["observations_sha256"],
        "release_dir_rel": base_rel,
        "schedule_sha256": manifest["schedule_sha256"],
        "schedule_binding": manifest["schedule_binding"],
        "admissions_n": int(manifest["admissions_n"]),
        "distinct_mint_n": int(manifest["distinct_mint_n"]),
        "observation_field_state_counts": manifest["observation_field_state_counts"],
        "feature_families": manifest["feature_families"],
        "closure_receipt_sha256": manifest["closure_receipt_sha256"],
        "source_sha256": manifest["source_sha256"],
        "evidence_role": EVIDENCE_ROLE,
    }
    cumulative = cohorts + [component]
    partitions = []
    for item in cumulative:
        for kind, rel_key, sha_key in (("CENSUS", "census_rel", "census_sha256"), ("OBS", "obs_rel", "observations_sha256")):
            part = build_partition_manifest(
                dataset_id=LOGICAL_DATASET_ID,
                dataset_version=dataset_version,
                partition_id=f"PARTITION-OPPORTUNITY-EPISODES-{item['cohort_id']}-{kind}",
                logical_location=str(item[rel_key]),
                file_sha256=str(item[sha_key]),
                content_sha256=str(item[sha_key]),
                row_count=int(item["admissions_n"]) if kind == "CENSUS" else int(sum(int(v) for v in item["observation_field_state_counts"].values())),
                first_reliable_available_at=imported_at,
                created_at=imported_at,
            )
            partitions.append(part)
    manifests = Path(data_root) / "datasets" / "manifests"
    validation_receipt = {
        "schema": "smial.opportunity-episodes-dataset-validation-receipt",
        "schema_version": "1.0",
        "dataset_id": LOGICAL_DATASET_ID,
        "dataset_version": dataset_version,
        "partition_manifest_ids": sorted(part.partition_manifest_id for part in partitions),
        "corpus_composition": [
            {
                "cohort_id": i["cohort_id"],
                "release_id": i["release_id"],
                "content_sha256": i["source_sha256"],
            }
            for i in cumulative
        ],
    }
    validation_bytes = json.dumps(validation_receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    validation_sha = __import__("hashlib").sha256(validation_bytes).hexdigest()
    dataset = build_dataset_manifest(
        dataset_id=LOGICAL_DATASET_ID,
        dataset_version=dataset_version,
        schema_id=CORPUS_SCHEMA_ID,
        schema_sha256=episode_corpus_schema_sha256(),
        generation_task_id=IMPORT_GENERATION_TASK,
        generation_run_id=f"import-{release_id[:16]}",
        validation_receipt_sha256=validation_sha,
        first_reliable_available_at=imported_at,
        created_at=imported_at,
        partitions=partitions,
    )
    for part in partitions:
        path = manifests / "partitions" / f"{part.partition_manifest_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        _publish_bytes(path, part.model_dump_json().encode("utf-8"))
    _publish_bytes(manifests / f"{dataset.dataset_manifest_id}.validation.json", validation_bytes)
    _publish_bytes(manifests / f"{dataset.dataset_manifest_id}.json", dataset.model_dump_json().encode("utf-8"))
    labels = {
        **REQUIRED_EPISODE_LABELS,
        "dataset_version": dataset_version,
        "corpus_version": version_n,
        "cohort_lineage": [str(item["cohort_id"]) for item in cumulative],
        "admissions_n_cumulative": sum(int(item["admissions_n"]) for item in cumulative),
        "feature_families": sorted({fam for item in cumulative for fam in item["feature_families"]}, key=FEATURE_FAMILY_ORDER.index),
        "imported_at": render_utc(imported_at),
        "is_current_corpus_version": True,
        "projection_id": PROJECTION_ID,
        "projection_version": PROJECTION_VERSION,
        "provider_calls_for_bind": 0,
        "yield_eligible": sum(int(item["admissions_n"]) for item in cumulative),
        "yield_missing": 0,
        "dataset_terminal": "IMPORTED_VALID",
        "yield_semantics": "ADMISSIONS_DENOMINATOR_NOT_OBSERVED_YIELD",
    }
    _publish_bytes(
        manifests / f"{dataset.dataset_manifest_id}.labels.json",
        json.dumps(labels, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )
    # Currentness is derived from the lineage pointer, as for the LIVE corpus:
    # earlier versions lose the administrative flag before lineage moves, so a
    # torn import is a fail-closed manifest mismatch, never a silent choice.
    current_labels_path = manifests / f"{dataset.dataset_manifest_id}.labels.json"
    for previous_path in sorted(manifests.glob("*.labels.json")):
        if previous_path == current_labels_path:
            continue
        try:
            previous = json.loads(previous_path.read_bytes())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if (
            isinstance(previous, dict)
            and previous.get("logical_dataset_id") == LOGICAL_DATASET_ID
            and previous.get("is_current_corpus_version") is not False
        ):
            previous["is_current_corpus_version"] = False
            tmp_previous = previous_path.with_name(f"{previous_path.name}.tmp")
            tmp_previous.write_bytes(json.dumps(previous, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            tmp_previous.replace(previous_path)
    _publish_bytes(
        manifests / f"{dataset.dataset_manifest_id}.published",
        json.dumps(
            {
                "dataset_manifest_id": dataset.dataset_manifest_id,
                "dataset_fingerprint": dataset.dataset_fingerprint,
                "published_at": render_utc(imported_at),
                "metadata_clock_at": render_utc(imported_at),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8"),
    )
    lineage_out = {
        "corpus_dataset_id": LOGICAL_DATASET_ID,
        "collection": COLLECTION,
        "population": POPULATION,
        "current_corpus_version": version_n,
        "current_dataset_manifest_id": dataset.dataset_manifest_id,
        "cohorts": cumulative,
    }
    path = Path(data_root) / CORPUS_LINEAGE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_bytes(json.dumps(lineage_out, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    tmp.replace(path)
    return {
        "status": "IMPORTED",
        "collection": COLLECTION,
        "cohort_id": cohort_id,
        "release_id": release_id,
        "corpus_version": version_n,
        "dataset_id": LOGICAL_DATASET_ID,
        "dataset_manifest_id": dataset.dataset_manifest_id,
        "imported_at": render_utc(imported_at),
        "epoch_bump": True,
    }


def default_episode_release_root(mirror_root: Path, receipt: Mapping[str, Any]) -> Path:
    return (
        Path(mirror_root)
        / "sealed_releases"
        / COLLECTION
        / f"{str(receipt['schedule_sha256'])[:16]}-{receipt['activation_id']}"
        / str(receipt["cohort_id"])
    )


def unpack_next_episode_cohort(
    *,
    mirror_root: Path,
    data_root: Path,
    repo_root: Path,
    closure_receipt: Mapping[str, Any],
    manifest: Mapping[str, Any],
    as_of: datetime,
    release_builder_git_sha: str | None = None,
) -> dict[str, Any]:
    """Workstation half: verified mirror → seal (reused) → verify → import → card."""

    from solana_alpha_lab.factory.live_cohort_vanilla_path import classify_mirror

    assert_episode_closure_ready(closure_receipt)
    _require(manifest.get("closure_receipt_sha256") == closure_receipt.get("closure_receipt_sha256"), "CLOSURE_COHORT_MISMATCH")
    classification = classify_mirror(manifest, Path(mirror_root))
    _require(classification["status"] != "CONFLICT", "MIRROR_CONFLICT")
    _require(not classification["missing_files"], "MIRROR_INCOMPLETE")
    release_root = default_episode_release_root(Path(mirror_root), closure_receipt)
    sealed = seal_episode_cohort(
        mirror_root=Path(mirror_root),
        receipt=closure_receipt,
        release_root=release_root,
        sealed_at=as_of,
        release_builder_git_sha=release_builder_git_sha,
    )
    verified = verify_episode_release(release_root)
    imported = import_episode_release(release_root=release_root, data_root=Path(data_root), import_time=as_of)
    card = build_population_card(Path(data_root))
    return {
        "terminal": "EPISODE_COHORT_IMPORTED" if imported["status"] == "IMPORTED" else imported["status"],
        "collection": COLLECTION,
        "next": "ORDINARY_FORGE_PREFLIGHT_COLLECTION_OPPORTUNITY_EPISODES",
        "cohort_id": closure_receipt["cohort_id"],
        "release_id": verified["release_id"],
        "sealed_at": sealed["sealed_at"],
        "import_status": imported["status"],
        "population_card": card,
        "transfer_manifest_sha256": manifest.get("manifest_sha256"),
    }


# --------------------------------------------------------------------------
# Population card (generated by import/readback; metadata-only)


def _cohort_window(cohort_id: str) -> dict[str, str]:
    start, end = cohort_day_bounds(cohort_id)
    return {"start": render_utc(start), "end_exclusive": render_utc(end)}


def build_population_card(data_root: Path) -> dict[str, Any]:
    """Generated card. Reads release metadata only; never typed values."""

    lineage = load_episode_lineage(Path(data_root))
    cohorts = list(lineage.get("cohorts") or [])
    if not cohorts:
        return {"population": POPULATION, "state": "NO_IMPORTED_COHORT", "next": "UNPACK_NEXT_LIVE_COHORT_COLLECTION_OPPORTUNITY_EPISODES"}
    admissions = sum(int(item["admissions_n"]) for item in cohorts)
    state_counts: dict[str, int] = {}
    for item in cohorts:
        for key, value in (item.get("observation_field_state_counts") or {}).items():
            state_counts[key] = state_counts.get(key, 0) + int(value)
    mints: list[str] = []
    repeated = 0
    for item in cohorts:
        release_dir = Path(data_root) / str(item["release_dir_rel"])
        census = pq.read_table(release_dir / CENSUS_NAME, columns=["mint"]).to_pylist()
        mints.extend(str(row["mint"]) for row in census)
    repeated = len(mints) - len(set(mints))
    binding = cohorts[-1].get("schedule_binding") or {}
    return {
        "population": POPULATION,
        "population_contract": POPULATION_CONTRACT,
        "anchor_kind": ANCHOR_KIND,
        "anchor_explanation": "T0 = durable admission commit instant; not birth/pool creation; not the whole Solana universe",
        "logical_dataset_id": LOGICAL_DATASET_ID,
        "corpus_version": lineage.get("current_corpus_version"),
        "dataset_manifest_id": lineage.get("current_dataset_manifest_id"),
        "membership": {
            "admissions_n": admissions,
            "episodes_n": admissions,
            "distinct_mint_n": len(set(mints)),
            "repeated_mint_n": repeated,
            "cohorts": [
                {
                    "cohort_id": item["cohort_id"],
                    "release_id": item["release_id"],
                    "admissions_n": item["admissions_n"],
                    "admission_window_utc": _cohort_window(str(item["cohort_id"])),
                }
                for item in cohorts
            ],
            "selection_explanation": (
                "Jupiter category nominations are read every round; a mint is admitted only when every "
                "registered source answered, its protection decision is ALLOW and its deterministic "
                "weekly ticket wins within the round, day and active quotas"
            ),
            "denominator_explanation": (
                "every committed admission counts; a value that was not observed is an explicit gap "
                "state, never zero, and never removes the episode from the base"
            ),
        },
        "time": {
            "schedule_contract": SCHEDULE_CONTRACT,
            "schedule_sha256": sorted({str(item["schedule_sha256"]) for item in cohorts}),
            "witness_point": WITNESS_POINT,
            "nominal_horizon_seconds": int(binding.get("horizon_seconds") or 0),
            "points_stored": len(EXPECTED_POINTS),
            "max_query_points": 8,
            "availability_grace_seconds": binding.get("availability_grace_seconds"),
            "time_feature_clock": "FIRST_RELIABLE_AVAILABLE_AT",
        },
        "data_support": {
            # All points, including those after any decision point: metadata,
            # not a basis for choosing a question.
            "observation_field_state_counts": dict(sorted(state_counts.items())),
            "observation_field_state_counts_scope": "ALL_POINTS_POST_OUTCOME_METADATA",
            "numeric_fields": ["FIELD-USD-PRICE-001", "FIELD-LIQUIDITY-USD-001", "FIELD-HOLDER-COUNT-001"],
            "time_features": ["elapsed_seconds", "utc_hour"],
            "unsupported_numeric": ["volume", "market_cap", "audit", "tags"],
            "joint_support": "VALUE_DEPENDENT_USE_ORDINARY_PREVIEW",
        },
        "scientific_context": {
            "evidence_role": EVIDENCE_ROLE,
            "confirmatory_reuse_forbidden": True,
            "research_profile": "SELECT_THROUGH_UNIVERSE_POLICY_OWNER",
        },
        "state": "IMPORTED_VALID",
        "next": "ORDINARY_FORGE_PREFLIGHT_COLLECTION_OPPORTUNITY_EPISODES",
        "automatic_scientific_look": False,
    }


def iter_release_package_files(release_root: Path) -> Iterator[tuple[str, Path]]:
    manifest = verify_episode_release(release_root)
    yield RELEASE_MANIFEST_NAME, Path(release_root) / RELEASE_MANIFEST_NAME
    for item in episode_release_files(manifest):
        yield item["path"], _contained(Path(release_root), item["path"])
