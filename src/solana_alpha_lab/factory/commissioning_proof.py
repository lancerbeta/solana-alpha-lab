"""Shared Fast Lane / HFIC commissioning proof. One implementation, fail-closed."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.commissioning_fixture import (
    COMMISSIONING_DATASET_MANIFEST_ID,
)
from solana_alpha_lab.factory.fast_lane_cold_copy import (
    ColdCopyError,
    load_run_result_artifact,
)
from solana_alpha_lab.factory.research_store import (
    RecordKind,
    ResearchEvent,
    ResearchStore,
    ResearchStoreError,
)
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
RUN_PASSPORT_REQUIRED_FIELDS = tuple(
    name
    for name, field in RunPassport.model_fields.items()
    if field.is_required()
)
COMPAT_HYPOTHESIS_LINK_KIND = "HFIC-COMPAT-HVLINK-V1"


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
    if "git_mutation_count" not in passport:
        raise CommissioningProofError("COMMISSION_GIT_MUTATION_COUNT_MISSING")
    raw_git = passport.get("git_mutation_count")
    if int(raw_git) != 0:
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


def _count_run_records(store: ResearchStore, run_id: str) -> dict[str, int]:
    counts: dict[str, int] = {kind.value: 0 for kind in REQUIRED_RUN_RECORD_COUNTS}
    for record in store.iter_committed_records():
        if record.run_id != run_id:
            continue
        kind_name = _kind_name(record)
        if kind_name in counts:
            counts[kind_name] += 1
    return counts


def _required_run_records_complete(counts: dict[str, int]) -> bool:
    return all(
        counts.get(kind.value, 0) >= minimum
        for kind, minimum in REQUIRED_RUN_RECORD_COUNTS.items()
    )


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
    if "git_mutation_count" not in passport:
        raise CommissioningProofError("COMMISSION_GIT_MUTATION_COUNT_MISSING")
    git_mutation_count = int(passport["git_mutation_count"])
    if git_mutation_count != 0:
        raise CommissioningProofError("COMMISSION_GIT_MUTATION")
    return {
        "run_id": run_id,
        "result_digest_sha256": stored_digest,
        "recomputed_result_digest_sha256": recomputed_digest,
        "result_integrity_matches": True,
        "result_artifact_id": passport.get("result_artifact_id"),
        "provider_calls_actual": int(passport.get("provider_calls_actual") or 0),
        "git_mutation_count": int(passport["git_mutation_count"]),
        "scientific_terminal": str(passport.get("scientific_terminal") or ""),
    }


def _iter_commissioning_completed(
    store: ResearchStore,
) -> list[tuple[Any, dict[str, Any]]]:
    candidates: list[tuple[Any, dict[str, Any]]] = []
    for record in store.iter_committed_records():
        if _kind_name(record) != RecordKind.RUN_COMPLETED.value:
            continue
        payload = _payload(record)
        if COMMISSIONING_DATASET_MANIFEST_ID not in _manifest_ids(payload):
            continue
        candidates.append((record, payload))
    return candidates


def _select_unique_hypothesis_source(
    sources: list[Any],
) -> Any:
    if not sources:
        raise CommissioningProofError("REAL_DATA_MIGRATION_AMBIGUOUS")
    hashes = {str(record.payload_sha256) for record in sources}
    if len(hashes) != 1:
        raise CommissioningProofError("REAL_DATA_MIGRATION_AMBIGUOUS")
    return sources[0]


def apply_legacy_commissioning_hypothesis_link(
    data_root: Path,
    *,
    now: datetime,
) -> dict[str, Any]:
    """Append-only unique HYPOTHESIS_VERSION proof-link for a legacy run.

    Copies an already-committed payload byte-for-byte. Invents no hypothesis
    identity. Idempotent via a deterministic record_id.
    """

    try:
        store = ResearchStore(Path(data_root))
    except ResearchStoreError as exc:
        raise CommissioningProofError("FAST_LANE_NOT_COMMISSIONED") from exc

    proven = 0
    missing_link: list[tuple[dict[str, Any], Any]] = []
    for record, payload in _iter_commissioning_completed(store):
        try:
            passport = verify_commissioning_passport(payload)
            run_id = str(passport["run_id"])
            verify_commissioning_records(
                store,
                run_id,
                hypothesis_version_id=str(passport["hypothesis_version_id"]),
            )
            verify_result_integrity(Path(data_root), run_id)
        except CommissioningProofError as exc:
            if str(exc) != "COMMISSION_HYPOTHESIS_VERSION_MISSING":
                continue
            try:
                passport = verify_commissioning_passport(payload)
                run_id = str(passport["run_id"])
                if not _required_run_records_complete(
                    _count_run_records(store, run_id)
                ):
                    continue
                verify_result_integrity(Path(data_root), run_id)
            except CommissioningProofError:
                continue
            missing_link.append((passport, record))
            continue
        proven += 1

    if proven:
        return {"status": "ALREADY_PROVEN", "appended": 0}

    if not missing_link:
        return {"status": "NO_REPAIRABLE_CANDIDATE", "appended": 0}

    hyp_ids = {
        str(passport["hypothesis_version_id"]) for passport, _record in missing_link
    }
    if len(hyp_ids) != 1:
        raise CommissioningProofError("REAL_DATA_MIGRATION_AMBIGUOUS")
    hyp_id = next(iter(hyp_ids))

    sources: list[Any] = []
    for record in store.iter_committed_records():
        if _kind_name(record) != RecordKind.HYPOTHESIS_VERSION.value:
            continue
        payload = _payload(record)
        source_id = str(payload.get("hypothesis_version_id") or record.entity_id or "")
        if source_id != hyp_id:
            continue
        sources.append(record)
    source = _select_unique_hypothesis_source(sources)
    source_payload = _payload(source)
    source_definition = str(source_payload.get("definition_sha256") or "")
    passport_definitions = {
        str(passport.get("hypothesis_definition_sha256") or "")
        for passport, _record in missing_link
    }
    if source_definition and any(
        definition and definition != source_definition
        for definition in passport_definitions
    ):
        raise CommissioningProofError("REAL_DATA_MIGRATION_AMBIGUOUS")

    appended = 0
    existing_ids = {str(record.record_id) for record in store.iter_committed_records()}
    for passport, _completed in missing_link:
        run_id = str(passport["run_id"])
        digest = hashlib.sha256(
            "\n".join(
                (
                    COMPAT_HYPOTHESIS_LINK_KIND,
                    run_id,
                    hyp_id,
                    str(source.payload_sha256),
                )
            ).encode("utf-8")
        ).hexdigest()
        token = digest[:16].upper()
        record_id = f"HYPOTHESIS-VERSION-COMPAT-{token}"
        transaction_id = f"RESEARCH-TXN-HFIC-COMPAT-{token}"
        if record_id in existing_ids:
            continue
        event = ResearchEvent(
            record_id=record_id,
            record_kind=RecordKind.HYPOTHESIS_VERSION,
            entity_id=hyp_id,
            hypothesis_version_id=hyp_id,
            run_id=run_id,
            transaction_id=transaction_id,
            effective_at=now,
            first_reliable_available_at=now,
            supersedes_record_id=None,
            payload_json=source.payload_json,
            payload_sha256=source.payload_sha256,
            schema_version=source.schema_version,
            producer_capability_id=source.producer_capability_id,
            producer_git_sha=source.producer_git_sha,
            created_at=now,
        )
        try:
            store.append([event], transaction_id=transaction_id)
        except ResearchStoreError as exc:
            if str(exc) in {"DUPLICATE_RECORD_ID", "TRANSACTION_CONFLICT"}:
                continue
            raise CommissioningProofError(str(exc)) from exc
        existing_ids.add(record_id)
        appended += 1

    return {
        "status": "APPLIED" if appended else "ALREADY_BOUND",
        "appended": appended,
        "hypothesis_version_id": hyp_id,
        "compatibility_kind": COMPAT_HYPOTHESIS_LINK_KIND,
    }


def prove_fast_lane_commissioned(data_root: Path) -> dict[str, Any]:
    try:
        store = ResearchStore(Path(data_root))
    except ResearchStoreError as exc:
        raise CommissioningProofError("FAST_LANE_NOT_COMMISSIONED") from exc
    candidates = _iter_commissioning_completed(store)
    if not candidates:
        raise CommissioningProofError("FAST_LANE_NOT_COMMISSIONED")
    last_error = "FAST_LANE_NOT_COMMISSIONED"
    missing_link_only = False
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
            if str(exc) == "COMMISSION_HYPOTHESIS_VERSION_MISSING":
                try:
                    passport = verify_commissioning_passport(payload)
                    run_id = str(passport["run_id"])
                    if _required_run_records_complete(
                        _count_run_records(store, run_id)
                    ):
                        verify_result_integrity(Path(data_root), run_id)
                        missing_link_only = True
                except CommissioningProofError:
                    pass
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
    if missing_link_only:
        raise CommissioningProofError("COMMISSION_HYPOTHESIS_VERSION_MISSING")
    raise CommissioningProofError(last_error)
