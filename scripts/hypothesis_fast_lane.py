#!/usr/bin/env python3
"""Deterministic operator CLI for the governed hypothesis Fast Lane."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.experiment_spec import (  # noqa: E402
    ExperimentSpecError,
    validate_experiment_document,
)
from solana_alpha_lab.factory.lane_classifier import Lane, classify_lane  # noqa: E402
from solana_alpha_lab.factory.operational_store import OperationalStore  # noqa: E402
from solana_alpha_lab.factory.prior_work import (  # noqa: E402
    PriorWorkError,
    query_data_plane_prior_work,
    query_hypotheses,
)
from solana_alpha_lab.factory.research_store import (  # noqa: E402
    RESEARCH_PROJECTION_LOCATION,
    RecordKind,
    ResearchStore,
    ResearchStoreError,
)
from solana_alpha_lab.factory.run_passport import (  # noqa: E402
    RunPassport,
    RunPassportError,
    canonical_sha256,
    experiment_spec_sha256,
    validate_run_passport,
)
from solana_alpha_lab.factory.commissioning_fixture import (  # noqa: E402
    COMMISSIONING_DATASET_MANIFEST_ID,
    publish_commissioning_dataset,
)
from solana_alpha_lab.factory.fast_lane_cold_copy import (  # noqa: E402
    ColdCopyError,
    backup_committed_inventory,
    load_run_result_artifact,
    prove_cold_copy,
)
from solana_alpha_lab.factory.fast_lane_snapshot import (  # noqa: E402
    SnapshotError,
    export_snapshot,
    restore_snapshot,
)
from solana_alpha_lab.factory.data_root import (  # noqa: E402
    DataRootError,
    resolve_data_root,
)
from solana_alpha_lab.factory.document_runner import (  # noqa: E402
    DocumentRunner,
    ExperimentRunnerError,
    RunContext,
    repository_git_snapshot,
    repository_status_bytes,
)

DEFAULT_AS_OF = "2026-08-25T00:00:00Z"
PROMOTION_ARTIFACT_PREFIX = "research/artifacts/promotion-packets"


class FastLaneCliError(Exception):
    """Typed CLI failure surfaced on stderr without a traceback."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def parse_as_of(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise FastLaneCliError("AS_OF_INVALID")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError as exc:
        raise FastLaneCliError("AS_OF_INVALID") from exc


def load_packet(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise FastLaneCliError("PACKET_UNAVAILABLE")
    text = path.read_text(encoding="utf-8")
    if path.suffix.casefold() in {".yaml", ".yml"}:
        loaded = yaml.safe_load(text)
    else:
        loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise FastLaneCliError("PACKET_INVALID")
    return loaded


def owner_fields(
    *,
    lane: str,
    status: str,
    scientific_terminal: str,
    reason_codes: list[str],
    run_id_or_null: str | None,
    git_mutation_count: int,
    provider_calls_actual: int,
    next_action: str,
) -> dict[str, Any]:
    return {
        "lane": lane,
        "status": status,
        "scientific_terminal": scientific_terminal,
        "reason_codes": reason_codes,
        "run_id_or_null": run_id_or_null,
        "git_mutation_count": git_mutation_count,
        "provider_calls_actual": provider_calls_actual,
        "next_action": next_action,
    }


def emit(payload: dict[str, Any], *, exit_code: int = 0) -> int:
    print(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    return exit_code


def emit_error(code: str, *, exit_code: int = 1) -> int:
    print(code, file=sys.stderr)
    return exit_code


def blocked_exit_code(payload: Mapping[str, Any]) -> int:
    lane = payload.get("lane")
    status = payload.get("status")
    if lane in {Lane.DENY.value, Lane.CHANGE_LANE.value, Lane.PROMOTION_LANE.value}:
        return 2
    if status in {
        "FAST_LANE_OWNER_GATE_REQUIRED",
        "BLOCKED_AUTHORITY",
        "BLOCKED_DATA",
        "DENY_INVALID_SPEC",
        "INVALID_EVIDENCE",
    }:
        return 2
    if payload.get("scientific_terminal") == "INVALID" and lane != Lane.FAST_LANE.value:
        return 2
    return 0


def decision_payload(decision: Any) -> dict[str, Any]:
    scientific_terminal = "INCONCLUSIVE"
    if decision.lane in {Lane.DENY, Lane.CHANGE_LANE, Lane.PROMOTION_LANE}:
        scientific_terminal = "INVALID"
    return owner_fields(
        lane=decision.lane.value,
        status=decision.terminal,
        scientific_terminal=scientific_terminal,
        reason_codes=list(decision.reason_codes),
        run_id_or_null=decision.prior_run_id,
        git_mutation_count=0,
        provider_calls_actual=0,
        next_action=decision.next_action,
    )


def runner_payload(result: dict[str, Any]) -> dict[str, Any]:
    return owner_fields(
        lane=str(result["lane"]),
        status=str(result["status"]),
        scientific_terminal=str(result["scientific_terminal"]),
        reason_codes=[str(item) for item in result.get("reason_codes") or []],
        run_id_or_null=result.get("run_id_or_null"),
        git_mutation_count=int(result.get("git_mutation_count") or 0),
        provider_calls_actual=int(result.get("provider_calls_actual") or 0),
        next_action=str(result["next_action"]),
    )


def store_diagnostics_payload(store: ResearchStore) -> dict[str, Any]:
    diagnostics = store.diagnostics()
    return {
        "committed_inventory_sha256": diagnostics.committed_inventory_sha256,
        "orphan_partition_count": diagnostics.orphan_partition_count,
        "writer_lease_state": diagnostics.writer_lease_state,
        "projection_digest_sha256": diagnostics.projection_digest_sha256,
        "cold_rebuild_possible": diagnostics.cold_rebuild_possible,
        "partition_count": diagnostics.partition_count,
        "record_count": diagnostics.record_count,
    }


def cmd_doctor(root: Path, data_root: Path) -> int:
    store = ResearchStore(data_root)
    payload = {
        **owner_fields(
            lane=Lane.FAST_LANE.value,
            status="DOCTOR_OK",
            scientific_terminal="INCONCLUSIVE",
            reason_codes=[],
            run_id_or_null=None,
            git_mutation_count=0,
            provider_calls_actual=0,
            next_action="VERIFY_STORE",
        ),
        **store_diagnostics_payload(store),
    }
    return emit(payload)


def cmd_verify_store(root: Path, data_root: Path) -> int:
    store = ResearchStore(data_root)
    diagnostics = store.diagnostics()
    verified = diagnostics.cold_rebuild_possible and diagnostics.orphan_partition_count == 0
    payload = {
        **owner_fields(
            lane=Lane.FAST_LANE.value,
            status="VERIFY_STORE_OK" if verified else "VERIFY_STORE_FAILED",
            scientific_terminal="INCONCLUSIVE" if verified else "INVALID",
            reason_codes=[] if verified else ["STORE_VERIFICATION_FAILED"],
            run_id_or_null=None,
            git_mutation_count=0,
            provider_calls_actual=0,
            next_action="REBUILD_PROJECTION" if verified else "DOCTOR",
        ),
        **store_diagnostics_payload(store),
        "verified": verified,
    }
    return emit(payload, exit_code=0 if verified else 2)


def execute_classify(
    root: Path,
    data_root: Path,
    packet_path: Path,
    as_of: datetime,
) -> dict[str, Any]:
    packet = load_packet(packet_path)
    decision = classify_lane(packet, root=root, data_root=data_root, as_of=as_of)
    payload = decision_payload(decision)
    payload["run_key_sha256"] = decision.run_key_sha256
    return payload


def execute_submit(
    root: Path,
    data_root: Path,
    packet_path: Path,
    as_of: datetime,
    *,
    run: bool,
    authority_phrase: str | None,
) -> dict[str, Any]:
    packet = load_packet(packet_path)
    decision = classify_lane(packet, root=root, data_root=data_root, as_of=as_of)
    if not run:
        payload = decision_payload(decision)
        payload["run_key_sha256"] = decision.run_key_sha256
        return payload

    spec = packet.get("experiment_spec")
    if not isinstance(spec, dict):
        raise FastLaneCliError("PACKET_SPEC_INVALID")
    hypothesis_definition_sha256 = packet.get("hypothesis_definition_sha256")
    if (
        not isinstance(hypothesis_definition_sha256, str)
        or len(hypothesis_definition_sha256) != 64
    ):
        raise FastLaneCliError("HYPOTHESIS_DEFINITION_SHA256_INVALID")

    validated = validate_experiment_document(spec, root=root)
    ops = OperationalStore(data_root / "ops" / "operational_state.sqlite")
    try:
        runner = DocumentRunner(root=root, store=ops)
        result = runner.start_document(
            validated,
            spec_sha256=experiment_spec_sha256(validated),
            run_context=RunContext(
                data_root=data_root,
                hypothesis_definition_sha256=hypothesis_definition_sha256,
                lane_decision=decision,
            ),
            authority_phrase=authority_phrase,
        )
    finally:
        ops.close()

    payload = runner_payload(result)
    payload["run_key_sha256"] = result.get("run_key_sha256")
    return payload


def execute_rebuild_projection(data_root: Path) -> dict[str, Any]:
    store = ResearchStore(data_root)
    receipt = store.rebuild_projection()
    return {
        **owner_fields(
            lane=Lane.FAST_LANE.value,
            status="REBUILD_PROJECTION_OK",
            scientific_terminal="INCONCLUSIVE",
            reason_codes=[],
            run_id_or_null=None,
            git_mutation_count=0,
            provider_calls_actual=0,
            next_action="VERIFY_STORE",
        ),
        "projection_digest_sha256": receipt.projection_digest_sha256,
        "record_count": receipt.record_count,
        "partition_count": receipt.partition_count,
        "logical_uri": receipt.logical_uri,
    }


def execute_search_prior_work(
    data_root: Path,
    query: dict[str, Any],
) -> dict[str, Any]:
    projection_path = data_root / RESEARCH_PROJECTION_LOCATION
    result = query_data_plane_prior_work(projection_path, query)
    return {
        **owner_fields(
            lane=Lane.FAST_LANE.value,
            status="SEARCH_PRIOR_WORK_OK",
            scientific_terminal="INCONCLUSIVE",
            reason_codes=[],
            run_id_or_null=None,
            git_mutation_count=0,
            provider_calls_actual=0,
            next_action="SHOW_RUN",
        ),
        **result,
    }


REQUIRED_RUN_RECORD_COUNTS = {
    RecordKind.RUN_STARTED: 1,
    RecordKind.RUN_COMPLETED: 1,
    RecordKind.EXPERIMENT_METRIC: 1,
    RecordKind.RESEARCH_ARTIFACT: 1,
    RecordKind.EVIDENCE_BINDING: 1,
}
RUN_PASSPORT_REQUIRED_FIELDS = tuple(RunPassport.model_fields)


def verify_commissioning_records(store: ResearchStore, run_id: str) -> dict[str, Any]:
    counts: dict[str, int] = {kind.value: 0 for kind in REQUIRED_RUN_RECORD_COUNTS}
    hypothesis_version_count = 0
    for record in store.iter_committed_records():
        kind_name = getattr(record.record_kind, "value", record.record_kind)
        if kind_name == RecordKind.HYPOTHESIS_VERSION.value:
            hypothesis_version_count += 1
        if record.run_id != run_id:
            continue
        kind_name = getattr(record.record_kind, "value", record.record_kind)
        if kind_name in counts:
            counts[kind_name] = counts.get(kind_name, 0) + 1
    if hypothesis_version_count < 1:
        raise FastLaneCliError("COMMISSION_HYPOTHESIS_VERSION_MISSING")
    for kind, minimum in REQUIRED_RUN_RECORD_COUNTS.items():
        if counts[kind.value] < minimum:
            raise FastLaneCliError(f"COMMISSION_RECORD_MISSING:{kind.value}")
    return {
        "run_id": run_id,
        "hypothesis_version_count": hypothesis_version_count,
        "record_counts": counts,
    }


def verify_commissioning_passport(passport: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in RUN_PASSPORT_REQUIRED_FIELDS if field not in passport]
    if missing:
        raise FastLaneCliError("COMMISSION_PASSPORT_INCOMPLETE")
    try:
        validated = validate_run_passport(passport)
    except RunPassportError as exc:
        raise FastLaneCliError("COMMISSION_PASSPORT_INVALID") from exc
    return dict(validated.payload)


def verify_result_integrity(data_root: Path, run_id: str) -> dict[str, Any]:
    row = _run_row(data_root, run_id)
    passport = row["passport"]
    artifact = load_run_result_artifact(data_root, passport)
    recomputed_digest = canonical_sha256(artifact["capability_result"])
    stored_digest = str(passport.get("result_digest_sha256") or "")
    matches = bool(stored_digest) and recomputed_digest == stored_digest
    return {
        **owner_fields(
            lane=Lane.FAST_LANE.value,
            status="RESULT_INTEGRITY_OK" if matches else "RESULT_INTEGRITY_MISMATCH",
            scientific_terminal=str(row["scientific_terminal"]),
            reason_codes=[] if matches else ["RESULT_DIGEST_MISMATCH"],
            run_id_or_null=run_id,
            git_mutation_count=0,
            provider_calls_actual=int(passport.get("provider_calls_actual") or 0),
            next_action="PREPARE_PROMOTION" if matches else "SHOW_RUN",
        ),
        "result_digest_sha256": stored_digest,
        "recomputed_result_digest_sha256": recomputed_digest,
        "result_integrity_matches": matches,
        "result_artifact_id": passport.get("result_artifact_id"),
    }


def execute_replay(data_root: Path, run_id: str) -> dict[str, Any]:
    """Backward-compatible alias for independent result integrity verification."""

    return verify_result_integrity(data_root, run_id)


def cmd_classify(
    root: Path,
    data_root: Path,
    packet_path: Path,
    as_of: datetime,
) -> int:
    payload = execute_classify(root, data_root, packet_path, as_of)
    return emit(payload, exit_code=blocked_exit_code(payload))


def cmd_submit(
    root: Path,
    data_root: Path,
    packet_path: Path,
    as_of: datetime,
    *,
    run: bool,
    authority_phrase: str | None,
) -> int:
    payload = execute_submit(
        root,
        data_root,
        packet_path,
        as_of,
        run=run,
        authority_phrase=authority_phrase,
    )
    return emit(payload, exit_code=blocked_exit_code(payload))


def cmd_show_hypothesis(
    data_root: Path,
    hypothesis_version_id: str,
    as_of: datetime,
) -> int:
    projection_path = data_root / RESEARCH_PROJECTION_LOCATION
    rows = query_hypotheses(projection_path, as_of.isoformat().replace("+00:00", "Z"))
    matched = [
        row for row in rows if row["hypothesis_version_id"] == hypothesis_version_id
    ]
    payload = {
        **owner_fields(
            lane=Lane.FAST_LANE.value,
            status="SHOW_HYPOTHESIS_OK" if matched else "SHOW_HYPOTHESIS_NOT_FOUND",
            scientific_terminal="INCONCLUSIVE" if matched else "INVALID",
            reason_codes=[] if matched else ["HYPOTHESIS_NOT_FOUND"],
            run_id_or_null=None,
            git_mutation_count=0,
            provider_calls_actual=0,
            next_action="SEARCH_PRIOR_WORK" if matched else "SUBMIT",
        ),
        "hypothesis_version_id": hypothesis_version_id,
        "matches": matched,
    }
    return emit(payload, exit_code=0 if matched else 2)


def _run_row(data_root: Path, run_id: str) -> dict[str, Any]:
    projection_path = data_root / RESEARCH_PROJECTION_LOCATION
    if not projection_path.is_file():
        raise FastLaneCliError("PROJECTION_UNAVAILABLE")
    import duckdb

    connection = duckdb.connect(
        str(projection_path),
        read_only=True,
        config={
            "enable_external_access": "false",
            "allow_unsigned_extensions": "false",
        },
    )
    try:
        row = connection.execute(
            """
            SELECT payload_json, run_key_sha256, trial_outcome, scientific_terminal
            FROM experiment_runs
            WHERE run_id = ?
              AND run_event_kind = 'RUN_COMPLETED'
            ORDER BY record_id
            LIMIT 1
            """,
            [run_id],
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise FastLaneCliError("RUN_NOT_FOUND")
    payload = json.loads(row[0])
    if not isinstance(payload, dict):
        raise FastLaneCliError("RUN_PASSPORT_INVALID")
    return {
        "run_id": run_id,
        "run_key_sha256": row[1],
        "trial_outcome": row[2],
        "scientific_terminal": row[3],
        "passport": payload,
    }


def cmd_show_run(data_root: Path, run_id: str) -> int:
    row = _run_row(data_root, run_id)
    payload = {
        **owner_fields(
            lane=Lane.FAST_LANE.value,
            status="SHOW_RUN_OK",
            scientific_terminal=str(row["scientific_terminal"]),
            reason_codes=[],
            run_id_or_null=run_id,
            git_mutation_count=0,
            provider_calls_actual=int(row["passport"].get("provider_calls_actual") or 0),
            next_action="REPLAY",
        ),
        "run": row,
    }
    return emit(payload)


def cmd_search_prior_work(data_root: Path, query: dict[str, Any]) -> int:
    try:
        payload = execute_search_prior_work(data_root, query)
    except PriorWorkError as exc:
        raise FastLaneCliError(str(exc)) from exc
    return emit(payload)


def cmd_replay(data_root: Path, run_id: str) -> int:
    payload = verify_result_integrity(data_root, run_id)
    return emit(payload, exit_code=0 if payload["result_integrity_matches"] else 2)


def cmd_prepare_promotion(data_root: Path, run_id: str) -> int:
    row = _run_row(data_root, run_id)
    passport = row["passport"]
    packet_id = f"PROMOTION-PACKET-{uuid.uuid4().hex[:16].upper()}"
    packet = {
        "promotion_packet_id": packet_id,
        "hypothesis_version_id": passport.get("hypothesis_version_id"),
        "run_id": run_id,
        "run_key_sha256": passport.get("run_key_sha256"),
        "result_digest_sha256": passport.get("result_digest_sha256"),
        "artifact_manifest_sha256": passport.get("artifact_manifest_sha256"),
        "evidence_hashes": sorted(
            {
                str(item)
                for item in (
                    passport.get("dataset_fingerprints") or []
                )
                if item
            }
            | {
                str(item)
                for item in (passport.get("query_recipe_sha256s") or [])
                if item
            }
        ),
        "promotion_rationale": "Fast Lane prepare-only nomination packet",
        "limitations": list(passport.get("limitations") or []),
        "invalidating_conditions": list(passport.get("non_claims") or []),
        "shadow_paper_live_target_class": "SHADOW",
        "proposed_acceptance_criteria": ["OWNER_PROMOTION_REVIEW"],
        "required_owner_decisions": ["PROMOTION_APPROVAL"],
        "proposed_git_write_set": [],
        "rollback_condition": "Owner rejects promotion packet",
    }
    logical_location = f"{PROMOTION_ARTIFACT_PREFIX}/{packet_id}.json"
    artifact_path = data_root / logical_location
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    payload = {
        **owner_fields(
            lane=Lane.PROMOTION_LANE.value,
            status="PROMOTION_PACKET_PREPARED",
            scientific_terminal=str(row["scientific_terminal"]),
            reason_codes=[],
            run_id_or_null=run_id,
            git_mutation_count=0,
            provider_calls_actual=int(passport.get("provider_calls_actual") or 0),
            next_action="OWNER_PROMOTION_REVIEW",
        ),
        "promotion_packet_id": packet_id,
        "logical_uri": f"smial-data://{logical_location}",
    }
    return emit(payload)


def cmd_rebuild_projection(data_root: Path) -> int:
    return emit(execute_rebuild_projection(data_root))


def execute_commission_offline(root: Path, data_root: Path, packet_path: Path) -> dict[str, Any]:
    publish_commissioning_dataset(data_root)
    git_before = repository_git_snapshot(root)
    submit_payload = execute_submit(
        root,
        data_root,
        packet_path,
        parse_as_of(DEFAULT_AS_OF),
        run=True,
        authority_phrase=None,
    )
    if blocked_exit_code(submit_payload) != 0 or submit_payload.get("status") != "COMPLETE":
        raise FastLaneCliError("COMMISSION_SUBMIT_FAILED")
    git_after = repository_git_snapshot(root)
    if not git_before.unchanged(git_after):
        raise FastLaneCliError("GIT_MUTATION_DETECTED")

    rebuild_payload = execute_rebuild_projection(data_root)
    if rebuild_payload.get("status") != "REBUILD_PROJECTION_OK":
        raise FastLaneCliError("COMMISSION_REBUILD_FAILED")

    packet = load_packet(packet_path)
    spec = packet["experiment_spec"]
    if not isinstance(spec, dict):
        raise FastLaneCliError("PACKET_SPEC_INVALID")
    hypothesis_version_id = str(spec.get("hypothesis_version") or "")
    search_query = {
        "query_id": "COMMISSION-OFFLINE-SEARCH",
        "as_of": DEFAULT_AS_OF,
        "max_results": 10,
        "predicates": {
            "hypothesis_version_ids": [hypothesis_version_id],
            "capability_ids": [str(spec.get("capability_id") or "")],
        },
    }
    search_payload = execute_search_prior_work(data_root, search_query)
    if not search_payload.get("results"):
        raise FastLaneCliError("COMMISSION_SEARCH_FAILED")

    store = ResearchStore(data_root)
    diagnostics = store.diagnostics()
    run_id = submit_payload.get("run_id_or_null")
    if not isinstance(run_id, str):
        raise FastLaneCliError("COMMISSION_RUN_ID_MISSING")

    record_receipt = verify_commissioning_records(store, run_id)
    integrity_payload = verify_result_integrity(data_root, run_id)
    integrity_matches = bool(integrity_payload.get("result_integrity_matches"))
    if not integrity_matches:
        raise FastLaneCliError("COMMISSION_RESULT_INTEGRITY_FAILED")

    passport_row = store.find_completed_run_by_id(run_id)
    if passport_row is None:
        raise FastLaneCliError("COMMISSION_PASSPORT_MISSING")
    passport = verify_commissioning_passport(dict(passport_row.payload))
    passport_fields = {
        field: passport.get(field) for field in RUN_PASSPORT_REQUIRED_FIELDS
    }
    passport_fields["query_recipe_binding"] = passport.get("query_recipe_binding")

    backup_root = data_root / "_cold_copy_backup"
    restored_root = data_root / "_cold_copy_restored"
    try:
        backup = backup_committed_inventory(data_root, backup_root)
        proof = prove_cold_copy(
            data_root,
            backup.backup_root,
            run_id=run_id,
            restored_root=restored_root,
        )
        cold_copy_proof = {
            "inventory_digest_matches": (
                proof.source_inventory_sha256 == proof.restored_inventory_sha256
            ),
            "projection_digest_matches": (
                proof.source_projection_digest_sha256
                == proof.restored_projection_digest_sha256
            ),
            "result_digest_matches": (
                proof.source_result_digest_sha256
                == proof.restored_result_digest_sha256
            ),
            "result_payload_matches": (
                proof.source_result_payload_sha256
                == proof.restored_result_payload_sha256
            ),
            "backup_file_count": backup.file_count,
            "snapshot_id": backup.snapshot_id,
        }
    except ColdCopyError as exc:
        raise FastLaneCliError(str(exc)) from exc

    payload = {
        **owner_fields(
            lane=Lane.FAST_LANE.value,
            status="COMMISSION_OFFLINE_OK",
            scientific_terminal=str(submit_payload.get("scientific_terminal") or "INCONCLUSIVE"),
            reason_codes=[],
            run_id_or_null=run_id,
            git_mutation_count=0,
            provider_calls_actual=0,
            next_action="VERIFY_STORE",
        ),
        "terminal": "FOUNDATION_VALIDATION_REPAIR_COMPLETE",
        "git_snapshot_unchanged": git_before.unchanged(git_after),
        "git_head_sha": git_after.head_sha,
        "git_symbolic_ref": git_after.symbolic_ref,
        "provider_calls_actual": 0,
        "projection_digest_sha256": rebuild_payload.get("projection_digest_sha256"),
        "prior_work_match_count": len(search_payload.get("results") or []),
        "result_integrity_matches": integrity_matches,
        "committed_inventory_sha256": diagnostics.committed_inventory_sha256,
        "commissioning_dataset_manifest_id": COMMISSIONING_DATASET_MANIFEST_ID,
        "record_receipt": record_receipt,
        "passport_fields": passport_fields,
        "proof_matrix": {
            "no_git_write_fence": git_before.unchanged(git_after),
            "append_only_records": all(
                record_receipt["record_counts"][kind.value]
                >= minimum
                for kind, minimum in REQUIRED_RUN_RECORD_COUNTS.items()
            )
            and record_receipt["hypothesis_version_count"] >= 1,
            "passport_fields_populated": all(
                field in passport_fields for field in RUN_PASSPORT_REQUIRED_FIELDS
            ),
            "deterministic_dataset_bound": COMMISSIONING_DATASET_MANIFEST_ID
            in list(passport_fields.get("dataset_manifest_ids") or []),
            "cold_copy_proof": cold_copy_proof,
        },
        "cold_copy_proof": cold_copy_proof,
    }
    return payload


def cmd_commission_offline(root: Path, data_root: Path, packet_path: Path) -> int:
    return emit(execute_commission_offline(root, data_root, packet_path))


def cmd_backup_export(data_root: Path, destination: Path) -> int:
    try:
        exported = export_snapshot(data_root, destination)
    except SnapshotError as exc:
        raise FastLaneCliError(str(exc)) from exc
    payload = {
        **owner_fields(
            lane=Lane.FAST_LANE.value,
            status="BACKUP_EXPORT_OK",
            scientific_terminal="INCONCLUSIVE",
            reason_codes=[],
            run_id_or_null=None,
            git_mutation_count=0,
            provider_calls_actual=0,
            next_action="RESTORE_SNAPSHOT",
        ),
        "snapshot_id": exported.snapshot_id,
        "snapshot_root": exported.snapshot_root.name,
        "inventory_sha256": exported.inventory_sha256,
        "committed_inventory_sha256": exported.committed_inventory_sha256,
        "created_at": exported.created_at,
        "entry_count": exported.entry_count,
    }
    return emit(payload)


def cmd_restore_snapshot(source: Path, destination: Path) -> int:
    try:
        restored = restore_snapshot(source, destination)
        rebuild = ResearchStore(destination).rebuild_projection()
    except (SnapshotError, ResearchStoreError) as exc:
        raise FastLaneCliError(str(exc)) from exc
    payload = {
        **owner_fields(
            lane=Lane.FAST_LANE.value,
            status="RESTORE_OK",
            scientific_terminal="INCONCLUSIVE",
            reason_codes=[],
            run_id_or_null=None,
            git_mutation_count=0,
            provider_calls_actual=0,
            next_action="VERIFY_STORE",
        ),
        "snapshot_id": restored.snapshot_id,
        "inventory_sha256": restored.inventory_sha256,
        "committed_inventory_sha256": restored.committed_inventory_sha256,
        "entry_count": restored.entry_count,
        "projection_digest_sha256": rebuild.projection_digest_sha256,
    }
    return emit(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hypothesis_fast_lane")
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository root for Git-bound resolution",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor")
    subparsers.add_parser("verify-store")
    subparsers.add_parser("rebuild-projection")
    subparsers.add_parser("commission-offline").add_argument(
        "--packet",
        type=Path,
        required=True,
    )

    classify = subparsers.add_parser("classify")
    classify.add_argument("--packet", type=Path, required=True)
    classify.add_argument("--as-of", default=DEFAULT_AS_OF)

    submit = subparsers.add_parser("submit")
    submit.add_argument("--packet", type=Path, required=True)
    submit.add_argument("--as-of", default=DEFAULT_AS_OF)
    submit.add_argument("--run", action="store_true")
    submit.add_argument("--authority-phrase")

    show_hypothesis = subparsers.add_parser("show-hypothesis")
    show_hypothesis.add_argument("--hypothesis-version-id", required=True)
    show_hypothesis.add_argument("--as-of", default=DEFAULT_AS_OF)

    show_run = subparsers.add_parser("show-run")
    show_run.add_argument("--run-id", required=True)

    replay = subparsers.add_parser("replay")
    replay.add_argument("--run-id", required=True)

    prepare = subparsers.add_parser("prepare-promotion")
    prepare.add_argument("--run-id", required=True)

    search = subparsers.add_parser("search-prior-work")
    search.add_argument("--as-of", default=DEFAULT_AS_OF)
    search.add_argument("--max-results", type=int, required=True)
    search.add_argument("--query-id", default="FAST-LANE-SEARCH")
    search.add_argument("--hypothesis-version-id", action="append", default=[])
    search.add_argument("--capability-id", action="append", default=[])
    search.add_argument("--trial-outcome", action="append", default=[])
    search.add_argument("--scientific-terminal", action="append", default=[])

    backup = subparsers.add_parser("backup")
    backup_sub = backup.add_subparsers(dest="backup_command", required=True)
    backup_export = backup_sub.add_parser("export")
    backup_export.add_argument("--destination", type=Path, required=True)

    restore = subparsers.add_parser("restore")
    restore.add_argument("--source", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        data_root = resolve_data_root(root)
    except DataRootError as exc:
        return emit_error(str(exc))
    try:
        if args.command == "doctor":
            return cmd_doctor(root, data_root)
        if args.command == "verify-store":
            return cmd_verify_store(root, data_root)
        if args.command == "rebuild-projection":
            return cmd_rebuild_projection(data_root)
        if args.command == "classify":
            return cmd_classify(
                root,
                data_root,
                args.packet.resolve(),
                parse_as_of(args.as_of),
            )
        if args.command == "submit":
            return cmd_submit(
                root,
                data_root,
                args.packet.resolve(),
                parse_as_of(args.as_of),
                run=bool(args.run),
                authority_phrase=args.authority_phrase,
            )
        if args.command == "show-hypothesis":
            return cmd_show_hypothesis(
                data_root,
                args.hypothesis_version_id,
                parse_as_of(args.as_of),
            )
        if args.command == "show-run":
            return cmd_show_run(data_root, args.run_id)
        if args.command == "replay":
            return cmd_replay(data_root, args.run_id)
        if args.command == "prepare-promotion":
            return cmd_prepare_promotion(data_root, args.run_id)
        if args.command == "search-prior-work":
            predicates: dict[str, Any] = {}
            if args.hypothesis_version_id:
                predicates["hypothesis_version_ids"] = args.hypothesis_version_id
            if args.capability_id:
                predicates["capability_ids"] = args.capability_id
            if args.trial_outcome:
                predicates["trial_outcomes"] = args.trial_outcome
            if args.scientific_terminal:
                predicates["scientific_terminals"] = args.scientific_terminal
            query = {
                "query_id": args.query_id,
                "as_of": args.as_of,
                "max_results": args.max_results,
                "predicates": predicates,
            }
            return cmd_search_prior_work(data_root, query)
        if args.command == "commission-offline":
            return cmd_commission_offline(
                root,
                data_root,
                args.packet.resolve(),
            )
        if args.command == "backup":
            if args.backup_command == "export":
                return cmd_backup_export(data_root, args.destination.resolve())
            raise FastLaneCliError("COMMAND_UNSUPPORTED")
        if args.command == "restore":
            return cmd_restore_snapshot(
                args.source.resolve(),
                args.destination.resolve(),
            )
        raise FastLaneCliError("COMMAND_UNSUPPORTED")
    except FastLaneCliError as exc:
        return emit_error(exc.code)
    except (
        ExperimentSpecError,
        ExperimentRunnerError,
        ResearchStoreError,
        PriorWorkError,
    ) as exc:
        return emit_error(str(exc))
    except json.JSONDecodeError:
        return emit_error("PACKET_JSON_INVALID")
    except yaml.YAMLError:
        return emit_error("PACKET_YAML_INVALID")


if __name__ == "__main__":
    raise SystemExit(main())
