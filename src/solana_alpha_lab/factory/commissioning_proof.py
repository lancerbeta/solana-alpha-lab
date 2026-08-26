"""Shared Fast Lane / HFIC commissioning proof. One implementation, fail-closed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.commissioning_fixture import (
    COMMISSIONING_DATASET_MANIFEST_ID,
)
from solana_alpha_lab.factory.fast_lane_cold_copy import (
    ColdCopyError,
    load_run_result_artifact,
)
from solana_alpha_lab.factory.research_store import RecordKind, ResearchStore, ResearchStoreError
from solana_alpha_lab.factory.run_passport import (
    RunPassport,
    RunPassportError,
    canonical_sha256,
    validate_run_passport,
)


class CommissioningProofError(ValueError):
    """Fail-closed commissioning proof error with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


REQUIRED_RUN_RECORD_COUNTS = {
    RecordKind.RUN_STARTED: 1,
    RecordKind.RUN_COMPLETED: 1,
    RecordKind.EXPERIMENT_METRIC: 1,
    RecordKind.RESEARCH_ARTIFACT: 1,
    RecordKind.EVIDENCE_BINDING: 1,
}
RUN_PASSPORT_REQUIRED_FIELDS = tuple(RunPassport.model_fields)


def _kind_name(record: Any) -> str:
    return str(getattr(record.record_kind, "value", record.record_kind))


def _payload(record: Any) -> dict[str, Any]:
    loaded = json.loads(record.payload_json)
    if not isinstance(loaded, dict):
        raise CommissioningProofError("COMMISSION_RECORD_PAYLOAD_INVALID")
    return loaded


def _manifest_ids(payload: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("dataset_manifest_ids", "ordered_input_dataset_manifest_ids"):
        items = payload.get(key)
        if isinstance(items, list):
            values.extend(str(item) for item in items if isinstance(item, str))
    return values


def verify_commissioning_passport(passport: dict[str, Any]) -> dict[str, Any]:
    raw_git = passport.get("git_mutation_count")
    if raw_git is not None and int(raw_git) != 0:
        raise CommissioningProofError("COMMISSION_GIT_MUTATION")
    missing = [field for field in RUN_PASSPORT_REQUIRED_FIELDS if field not in passport]
    if missing:
        raise CommissioningProofError("COMMISSION_PASSPORT_INCOMPLETE")
    try:
        validated = validate_run_passport(passport)
    except RunPassportError as exc:
        raise CommissioningProofError("COMMISSION_PASSPORT_INVALID") from exc
    payload = dict(validated.payload)
    provider_calls = payload.get("provider_calls_actual")
    if provider_calls is None or int(provider_calls) != 0:
        raise CommissioningProofError("COMMISSION_PROVIDER_CALLS")
    if COMMISSIONING_DATASET_MANIFEST_ID not in _manifest_ids(payload):
        raise CommissioningProofError("COMMISSION_DATASET_MANIFEST_MISSING")
    return payload


def verify_commissioning_records(
    store: ResearchStore,
    run_id: str,
    *,
    hypothesis_version_id: str | None = None,
) -> dict[str, Any]:
    counts: dict[str, int] = {kind.value: 0 for kind in REQUIRED_RUN_RECORD_COUNTS}
    completed: Any | None = None
    completed_payload: dict[str, Any] | None = None
    for record in store.iter_committed_records():
        if record.run_id != run_id:
            continue
        kind_name = _kind_name(record)
        if kind_name in counts:
            counts[kind_name] += 1
        if kind_name == RecordKind.RUN_COMPLETED.value:
            completed = record
            completed_payload = _payload(record)
    if completed is None or completed_payload is None:
        raise CommissioningProofError("COMMISSION_RECORD_MISSING:RUN_COMPLETED")
    bound_hypothesis = str(
        hypothesis_version_id
        or completed_payload.get("hypothesis_version_id")
        or completed.hypothesis_version_id
        or ""
    )
    if not bound_hypothesis:
        raise CommissioningProofError("COMMISSION_HYPOTHESIS_VERSION_MISSING")
    hypothesis_bound = False
    for record in store.iter_committed_records():
        if _kind_name(record) != RecordKind.HYPOTHESIS_VERSION.value:
            continue
        payload = _payload(record)
        hyp_id = str(
            payload.get("hypothesis_version_id") or record.entity_id or ""
        )
        if hyp_id != bound_hypothesis:
            continue
        same_run = record.run_id == run_id
        same_txn = record.transaction_id == completed.transaction_id
        same_passport_link = record.hypothesis_version_id == bound_hypothesis
        if same_run or same_txn or (
            same_passport_link and record.transaction_id == completed.transaction_id
        ):
            hypothesis_bound = True
            break
    if not hypothesis_bound:
        raise CommissioningProofError("COMMISSION_HYPOTHESIS_VERSION_MISSING")
    for kind, minimum in REQUIRED_RUN_RECORD_COUNTS.items():
        if counts[kind.value] < minimum:
            raise CommissioningProofError(f"COMMISSION_RECORD_MISSING:{kind.value}")
    return {
        "run_id": run_id,
        "hypothesis_version_id": bound_hypothesis,
        "hypothesis_version_count": 1,
        "record_counts": counts,
    }


def verify_result_integrity(data_root: Path, run_id: str) -> dict[str, Any]:
    try:
        row = ResearchStore(Path(data_root)).find_completed_run_by_id(run_id)
    except ResearchStoreError as exc:
        raise CommissioningProofError("COMMISSION_PASSPORT_MISSING") from exc
    if row is None:
        raise CommissioningProofError("RUN_NOT_FOUND")
    passport = dict(row.payload)
    try:
        artifact = load_run_result_artifact(Path(data_root), passport)
    except ColdCopyError as exc:
        raise CommissioningProofError("COMMISSION_RESULT_ARTIFACT_MISSING") from exc
    recomputed_digest = canonical_sha256(artifact["capability_result"])
    stored_digest = str(passport.get("result_digest_sha256") or "")
    if not stored_digest or recomputed_digest != stored_digest:
        raise CommissioningProofError("COMMISSION_RESULT_INTEGRITY_FAILED")
    return {
        "run_id": run_id,
        "result_digest_sha256": stored_digest,
        "recomputed_result_digest_sha256": recomputed_digest,
        "result_integrity_matches": True,
        "result_artifact_id": passport.get("result_artifact_id"),
        "provider_calls_actual": int(passport.get("provider_calls_actual") or 0),
        "git_mutation_count": int(passport.get("git_mutation_count") or 0),
        "scientific_terminal": str(passport.get("scientific_terminal") or ""),
    }


def prove_fast_lane_commissioned(data_root: Path) -> dict[str, Any]:
    try:
        store = ResearchStore(Path(data_root))
    except ResearchStoreError as exc:
        raise CommissioningProofError("FAST_LANE_NOT_COMMISSIONED") from exc
    candidates: list[tuple[Any, dict[str, Any]]] = []
    for record in store.iter_committed_records():
        if _kind_name(record) != RecordKind.RUN_COMPLETED.value:
            continue
        payload = _payload(record)
        if COMMISSIONING_DATASET_MANIFEST_ID not in _manifest_ids(payload):
            continue
        candidates.append((record, payload))
    if not candidates:
        raise CommissioningProofError("FAST_LANE_NOT_COMMISSIONED")
    last_error = "FAST_LANE_NOT_COMMISSIONED"
    for record, payload in candidates:
        try:
            passport = verify_commissioning_passport(payload)
            run_id = str(passport["run_id"])
            records = verify_commissioning_records(
                store,
                run_id,
                hypothesis_version_id=str(passport["hypothesis_version_id"]),
            )
            integrity = verify_result_integrity(Path(data_root), run_id)
        except CommissioningProofError as exc:
            last_error = str(exc)
            continue
        return {
            "status": "NO_GIT_FAST_LANE_PROVEN",
            "commissioning_dataset_manifest_id": COMMISSIONING_DATASET_MANIFEST_ID,
            "provider_calls_actual": 0,
            "git_mutation_count": 0,
            "run_id": run_id,
            "hypothesis_version_id": records["hypothesis_version_id"],
            "result_artifact_id": integrity.get("result_artifact_id"),
            "result_digest_sha256": integrity.get("result_digest_sha256"),
            "store_inventory_digest": store.diagnostics().committed_inventory_sha256,
            "research_memory_as_of": str(passport.get("completed_at") or ""),
        }
    raise CommissioningProofError(last_error)
