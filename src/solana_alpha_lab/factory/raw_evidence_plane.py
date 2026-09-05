"""HOT raw evidence plane: canonical JSON bodies in time-partitioned Parquet."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from solana_alpha_lab.factory.observation_schedule import canonical_json_bytes, canonical_sha256

RAW_PLANE_REL = "datasets/raw_evidence"


class RawEvidencePlaneError(ValueError):
    """Typed HOT raw plane failure."""


def materialize_canonical_raw(
    data_root: Path,
    *,
    utc_day: str,
    call_occurrence_id: str,
    request_sha256: str,
    response_sha256: str,
    body: object,
    first_reliable_available_at: str,
    event_time: str,
    primitive_id: str,
) -> dict[str, Any]:
    encoded = canonical_json_bytes(body)
    extracted = canonical_sha256(body)
    expected = str(response_sha256)
    if extracted != expected:
        raise RawEvidencePlaneError("RAW_RESPONSE_SHA256_MISMATCH")
    rel = f"{RAW_PLANE_REL}/{utc_day}/occurrences.parquet"
    path = data_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    unique_rel = f"{RAW_PLANE_REL}/{utc_day}/bodies/{extracted}.bin"
    unique_path = data_root / unique_rel
    unique_path.parent.mkdir(parents=True, exist_ok=True)
    if unique_path.is_file():
        if unique_path.read_bytes() != encoded:
            raise RawEvidencePlaneError("RAW_BODY_IDENTITY_CONFLICT")
    else:
        unique_path.write_bytes(encoded)
    row = {
        "call_occurrence_id": call_occurrence_id,
        "request_sha256": request_sha256,
        "response_sha256": expected,
        "body_rel": unique_rel,
        "first_reliable_available_at": first_reliable_available_at,
        "event_time": event_time,
        "primitive_id": primitive_id,
        "utc_day": utc_day,
    }
    existing: list[dict[str, Any]] = []
    if path.is_file():
        existing = [dict(item) for item in pq.read_table(path).to_pylist()]
    if any(item.get("call_occurrence_id") == call_occurrence_id for item in existing):
        raise RawEvidencePlaneError("RAW_OCCURRENCE_CONFLICT")
    existing.append(row)
    table = pa.Table.from_pylist(existing)
    tmp = path.with_suffix(".parquet.tmp")
    pq.write_table(table, tmp, compression="zstd", compression_level=3)
    tmp.replace(path)
    return {
        "occurrence": row,
        "extracted_sha256": extracted,
        "bytes": len(encoded),
        "occurrences_rel": rel,
    }


def extract_canonical_body(data_root: Path, occurrence: Mapping[str, Any]) -> bytes:
    rel = str(occurrence.get("body_rel") or "")
    path = data_root / rel
    if path.is_file() is False:
        raise RawEvidencePlaneError("RAW_BODY_MISSING")
    payload = path.read_bytes()
    body = json.loads(payload.decode("utf-8"))
    if canonical_sha256(body) != str(occurrence.get("response_sha256") or ""):
        raise RawEvidencePlaneError("RAW_RESPONSE_SHA256_MISMATCH")
    return payload


def raw_materialized_for_occurrence(data_root: Path, call_occurrence_id: str, utc_day: str) -> bool:
    path = data_root / RAW_PLANE_REL / utc_day / "occurrences.parquet"
    if path.is_file() is False:
        return False
    return any(
        str(item.get("call_occurrence_id") or "") == call_occurrence_id
        for item in pq.read_table(path).to_pylist()
    )
