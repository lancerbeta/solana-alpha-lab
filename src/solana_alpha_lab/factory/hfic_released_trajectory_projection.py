"""Non-synthetic NORMALIZED_TRAJECTORY_V1 projection/input receipt seam.

Closes the mechanical runtime gap: after a qualifying CONTROL, the exact
imported release/corpus is resolved from the canonical local data plane,
verified (release/source/census/observations/schedule/activation hashes), and
its typed lifecycle rows are mapped into the existing frozen projector.
No new representation semantics; no scientific execution happens here.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.hfic_representation_probe import (
    RepresentationProbeError,
)
from solana_alpha_lab.factory.live_cohort_discovery_release import (
    COHORT_ADMISSION_FIELD,
    verify_live_cohort,
)
from solana_alpha_lab.factory.normalized_trajectory_v1 import (
    DECLARED_Y_POINTS,
    DEFAULT_SCHEDULE,
    FIELD_IDS,
    PREFERRED_SCHEDULE_ID,
    PREFERRED_X_SECONDS,
    REPRESENTATION_ID,
    LifecycleCorpusBinding,
    LifecycleSchedule,
    TypedLifecycleObservation,
    project_normalized_trajectory,
)

INVALID_PROJECTION_PROVENANCE = "INVALID_PROJECTION_PROVENANCE"
FUTURE_POINT_LEAKAGE = "FUTURE_POINT_LEAKAGE"
MINT_IDENTITY_LEAK = "MINT_IDENTITY_LEAK"
UNSUPPORTED_POINT_SHAPE = "UNSUPPORTED_POINT_SHAPE"

_POINT_RE = re.compile(r"^([XY])([0-9]+)$")
_EPOCH_BOUND = timedelta(seconds=max(DECLARED_Y_POINTS) + 3600)
READBACK_VERIFIER = (
    "solana_alpha_lab.factory.live_cohort_discovery_release.verify_live_cohort"
)

_FIELD_IDS = frozenset(FIELD_IDS.values())


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _numeric(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _read_parquet_rows(path: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    return table.to_pylist()


def _anchor_key(mint: str) -> str:
    """Mint strings are internal grouping keys only; never emitted."""

    return hashlib.sha256(("mint-group:" + mint).encode("utf-8")).hexdigest()


def resolve_release_projection_input(release_root: Path) -> dict[str, Any]:
    """Verify one imported release and project it through the frozen lens.

    The release directory must contain the hash-verified
    ``release_manifest.json`` + ``census.parquet`` + ``observations.parquet``
    exactly as produced by the canonical seal/verify/import path.  The result
    carries the verified projection/input receipt (row provenance binding)
    and the anonymous representation payload — nothing else.
    """
    root = Path(release_root)
    if not root.is_dir():
        raise RepresentationProbeError("RELEASE_ROOT_NOT_FOUND")
    try:
        manifest = verify_live_cohort(root)
    except Exception as exc:  # noqa: BLE001 - typed translation below
        # Preserve the underlying typed code for operator diagnostics;
        # the terminal stays INVALID_PROJECTION_PROVENANCE.
        underlying = getattr(exc, "code", None)
        if isinstance(underlying, str) and underlying:
            raise RepresentationProbeError(
                f"{INVALID_PROJECTION_PROVENANCE}:{underlying}"
            ) from exc
        raise RepresentationProbeError(INVALID_PROJECTION_PROVENANCE) from exc

    binding = LifecycleCorpusBinding(
        release_id=str(manifest["release_id"]),
        cohort_id=str(manifest["cohort_id"]),
        schedule_sha256=str(manifest["schedule_sha256"]),
        activation_id=str(manifest["activation_id"]),
        producer_git_sha=str(
            manifest.get("schedule_producer_git_sha")
            or manifest.get("release_builder_git_sha")
            or manifest.get("producer_git_sha")
            or ""
        ),
        source_sha256=str(manifest["source_sha256"]),
        census_sha256=str(manifest["census_sha256"]),
        observations_sha256=str(manifest["observations_sha256"]),
    )
    schedule = LifecycleSchedule(
        schedule_sha256=binding.schedule_sha256,
        activation_id=binding.activation_id,
        corpus_binding=binding,
    )
    rows = _read_parquet_rows(root / "observations.parquet")
    # Canonical member anchors come from the verified census admission field
    # (authoritative_anchor, falling back to the admission instant itself),
    # never from per-observation wall-clock event_time.
    census_rows = _read_parquet_rows(root / "census.parquet")
    anchors: dict[str, datetime] = {}
    for row in census_rows:
        mint = str(row.get("mint") or row.get("entity_id") or "")
        anchor = _parse_utc(
            row.get("authoritative_anchor")
        ) or _parse_utc(row.get(COHORT_ADMISSION_FIELD))
        if mint and anchor is not None and mint not in anchors:
            anchors[_anchor_key(mint)] = anchor
    if not anchors:
        raise RepresentationProbeError(INVALID_PROJECTION_PROVENANCE)

    observations: list[TypedLifecycleObservation] = []
    for row in rows:
        field_id = str(row.get("field_id") or "")
        mint = str(row.get("mint") or row.get("entity_id") or "")
        member = _anchor_key(mint)
        point = _POINT_RE.fullmatch(str(row.get("point_id") or ""))
        if point is None or field_id not in _FIELD_IDS:
            continue
        due = int(point.group(2))
        if due not in schedule.all_due_offsets:
            raise RepresentationProbeError(UNSUPPORTED_POINT_SHAPE)
        anchor = anchors.get(member)
        if anchor is None:
            raise RepresentationProbeError(UNSUPPORTED_POINT_SHAPE)
        value = _numeric(row.get("typed_value"))
        state = str(row.get("state") or "")
        if state != "OBSERVED":
            value = None  # missingness stays M
        observed_at = _parse_utc(row.get("first_reliable_available_at"))
        if observed_at is not None:
            due_at = anchor + timedelta(seconds=due)
            # PIT cutoff frozen: available_at must not be after the point's
            # own due time extended by the schedule lateness bound.
            if observed_at > due_at + _EPOCH_BOUND:
                raise RepresentationProbeError(FUTURE_POINT_LEAKAGE)
        observations.append(
            TypedLifecycleObservation(
                member_id=member,
                member_anchor_at=anchors[member],
                due_offset_seconds=due,
                field_id=field_id,
                value=value,
                first_reliable_available_at=observed_at,
                schedule_sha256=binding.schedule_sha256,
                activation_id=binding.activation_id,
            )
        )

    representation = project_normalized_trajectory(observations, schedule=schedule)
    payload = representation.payload
    payload_text = repr(payload)
    for mint_marker in ("MINT", "mint_address", "member-"):
        if mint_marker in payload_text:
            raise RepresentationProbeError(MINT_IDENTITY_LEAK)

    receipt = {
        "schema": "smial.normalized-trajectory-v1-projection-input-receipt",
        "schema_version": "1.0",
        "representation_id": REPRESENTATION_ID,
        "source_kind": "VERIFIED_LIVE_COHORT_RELEASE_READBACK_V1",
        "readback_verified": True,
        "readback_verifier": READBACK_VERIFIER,
        "corpus_binding": binding.as_dict(),
        "schedule_sha256": binding.schedule_sha256,
        "activation_id": binding.activation_id,
        "observation_row_count": len(rows),
        "projected_observation_count": len(observations),
        "readiness_state": str(manifest["readiness_state"]),
        "discovery_coverage_class": str(manifest["discovery_coverage_class"]),
        "yield_eligible": int(manifest["yield_eligible"]),
        "first_fresh_cohort_sealed_verified_imported": True,
        "confirmatory_reuse_forbidden": True,
    }
    if any(
        isinstance(row, dict) and row.get("candidate_state")
        for row in census_rows
    ):
        from solana_alpha_lab.factory.scientific_eligibility_projection import (
            project_scientific_eligibility,
        )

        sanitized_obs = [
            {key: value for key, value in row.items() if key != "typed_value"}
            for row in rows
            if isinstance(row, dict)
        ]
        projected = project_scientific_eligibility(census_rows, sanitized_obs)
        receipt["base_x_population_n"] = int(projected["base_x_population"]["n"])
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(
            {k: v for k, v in receipt.items()}, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    return {
        "representation_id": REPRESENTATION_ID,
        "representation": representation,
        "projection_input_receipt": receipt,
        "eligible_member_count": int(payload.get("eligible_member_count") or 0),
        "packet_key": "normalized_trajectory_v1",
        "terminal": "NORMALIZED_TRAJECTORY_V1_RUNTIME_READY_NOT_EXECUTED",
    }


__all__ = [
    "FUTURE_POINT_LEAKAGE",
    "INVALID_PROJECTION_PROVENANCE",
    "MINT_IDENTITY_LEAK",
    "UNSUPPORTED_POINT_SHAPE",
    "resolve_release_projection_input",
]
