"""Fast Lane capability: compile/register/bind ObservationSchedule without provider calls."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.observation_fast_lane_terminals import (
    ATTACHED_TO_ACTIVE_SCHEDULE,
    NEW_VERSION_FOR_FUTURE_COHORTS_REQUIRED,
    PANEL_REUSE_READY,
    SCHEDULE_ACTIVATION_REQUIRED,
    observation_fast_lane_routing,
)
from solana_alpha_lab.factory.observation_panel_publisher import (
    build_panel_snapshot,
    persist_observation_schedule,
    persist_panel_snapshot_binding,
    persist_pending_observation_binding,
)
from solana_alpha_lab.factory.observation_schedule import parse_utc, render_utc
from solana_alpha_lab.factory.observation_schedule_compiler import compile_observation_request
from solana_alpha_lab.factory.observation_schedule_lifecycle import (
    ObservationLifecycleError,
    activate_schedule,
    authorize_schedule,
    observation_ops_store_path,
    prepare_schedule_authority,
)
from solana_alpha_lab.factory.observation_schedule_store import ObservationScheduleStore
from solana_alpha_lab.factory.run_passport import canonical_sha256, validate_run_passport


def _capability_status(terminal: str, *, snapshot_ready: bool) -> str:
    if terminal == PANEL_REUSE_READY and snapshot_ready:
        return "COMPLETE"
    if terminal == ATTACHED_TO_ACTIVE_SCHEDULE:
        return "WAITING_FOR_PANEL"
    if terminal in {
        SCHEDULE_ACTIVATION_REQUIRED,
        NEW_VERSION_FOR_FUTURE_COHORTS_REQUIRED,
    }:
        return "BLOCKED_AUTHORITY"
    routing = observation_fast_lane_routing(terminal)
    if routing is not None and routing.persist_completed_run:
        return "COMPLETE" if snapshot_ready else "FAILED"
    return "FAILED"


def compile_and_bind_observation_schedule(
    spec: Mapping[str, Any],
    *,
    root: Path,
    coverage=None,
    closed_family: bool = False,
    data_root: Path | None = None,
    producer_git_sha: str | None = None,
    hypothesis_version_id: str | None = None,
    run_id: str | None = None,
    now: datetime | None = None,
    hypothesis_definition_sha256: str | None = None,
    experiment_spec_sha256: str | None = None,
    run_key_sha256: str | None = None,
    authority_phrase: str | None = None,
) -> dict[str, Any]:
    persist_clock = now or datetime.now(UTC)
    if persist_clock.tzinfo is None:
        raise ValueError("TIMESTAMP_INVALID")
    persist_clock = persist_clock.astimezone(UTC)
    version_id = hypothesis_version_id or (
        str(spec["hypothesis_version"]) if spec.get("hypothesis_version") else None
    )
    classifier_now = persist_clock
    result = compile_observation_request(
        spec,
        root=root,
        coverage=coverage,
        closed_family=closed_family,
        data_root=data_root,
        now=classifier_now,
        hypothesis_version_id=version_id,
        hypothesis_definition_sha256=hypothesis_definition_sha256,
    )
    passport_bindings: dict[str, str] = {}
    bound_schedule = result.covering_schedule_sha256 or result.schedule_sha256
    if bound_schedule:
        passport_bindings["observation_schedule_sha256"] = bound_schedule
    if result.snapshot_sha256:
        passport_bindings["observation_panel_snapshot_sha256"] = result.snapshot_sha256
    authority_request = None
    authority_status = None
    pending_binding = None
    git_sha = producer_git_sha
    if data_root is not None:
        if not isinstance(git_sha, str) or len(git_sha) != 40:
            raise ObservationLifecycleError("PRODUCER_GIT_SHA_REQUIRED")
        if result.schedule is not None:
            persist_observation_schedule(
                data_root=data_root,
                schedule=result.schedule,
                now=persist_clock,
                producer_git_sha=git_sha,
                activation_id=run_id,
            )
        if result.terminal in {
            SCHEDULE_ACTIVATION_REQUIRED,
            NEW_VERSION_FOR_FUTURE_COHORTS_REQUIRED,
        } and result.schedule is not None:
            store = ObservationScheduleStore(observation_ops_store_path(Path(data_root)))
            try:
                prepared = prepare_schedule_authority(
                    root=root,
                    data_root=Path(data_root),
                    store=store,
                    document=result.schedule,
                    now=persist_clock,
                    producer_git_sha=git_sha,
                    predecessor_schedule_sha256=result.covering_schedule_sha256
                    if result.terminal == NEW_VERSION_FOR_FUTURE_COHORTS_REQUIRED
                    else None,
                )
            finally:
                store.close()
            authority_request = prepared.get("authority_request")
            if authority_request is not None:
                authority_status = "PROPOSED_NOT_AUTHORITY"
            if authority_request is not None and authority_phrase:
                store = ObservationScheduleStore(observation_ops_store_path(Path(data_root)))
                try:
                    try:
                        authorize_schedule(
                            root=root,
                            data_root=Path(data_root),
                            store=store,
                            schedule_sha256=str(authority_request["schedule_sha256"]),
                            phrase=str(authority_phrase),
                            now=persist_clock,
                            producer_git_sha=git_sha,
                        )
                    except ObservationLifecycleError:
                        authority_status = "PROPOSED_NOT_AUTHORITY"
                    else:
                        try:
                            activate_schedule(
                                root=root,
                                data_root=Path(data_root),
                                store=store,
                                schedule_sha256=str(authority_request["schedule_sha256"]),
                                activation_id=str(authority_request["activation_id"]),
                                now=persist_clock,
                                producer_git_sha=git_sha,
                            )
                        except ObservationLifecycleError as exc:
                            if str(exc) == "COHORT_CUTOVER_REQUIRED":
                                authority_status = "AUTHORIZED"
                            else:
                                authority_status = "PROPOSED_NOT_AUTHORITY"
                        else:
                            authority_status = "AUTHORIZED"
                            result = compile_observation_request(
                                spec,
                                root=root,
                                coverage=coverage,
                                closed_family=closed_family,
                                data_root=data_root,
                                now=classifier_now,
                                hypothesis_version_id=version_id,
                                hypothesis_definition_sha256=hypothesis_definition_sha256,
                            )
                            passport_bindings = {}
                            bound_schedule = (
                                result.covering_schedule_sha256 or result.schedule_sha256
                            )
                            if bound_schedule:
                                passport_bindings["observation_schedule_sha256"] = (
                                    bound_schedule
                                )
                            if result.snapshot_sha256:
                                passport_bindings["observation_panel_snapshot_sha256"] = (
                                    result.snapshot_sha256
                                )
                finally:
                    store.close()
        if result.terminal == ATTACHED_TO_ACTIVE_SCHEDULE and result.schedule is not None:
            registered_at = result.hypothesis_registered_at
            pending_payload = {
                "hypothesis_version_id": version_id,
                "hypothesis_definition_sha256": hypothesis_definition_sha256,
                "experiment_spec_sha256": experiment_spec_sha256,
                "run_key_sha256": run_key_sha256,
                "requested_schedule_sha256": result.schedule_sha256,
                "covering_schedule_sha256": result.covering_schedule_sha256,
                "requested_availability_semantics": spec.get("availability_cutoff"),
                "required_x_point": dict(result.schedule["x_point"]),
                "required_y_points": [dict(item) for item in result.schedule["y_points"]],
                "evidence_role_basis": {
                    "hypothesis_registered_at": render_utc(registered_at)
                    if registered_at is not None
                    else None,
                },
                "state": "WAITING_FOR_PANEL",
            }
            pending = persist_pending_observation_binding(
                data_root=Path(data_root),
                payload=pending_payload,
                now=persist_clock,
                producer_git_sha=git_sha,
                run_id=run_id,
            )
            pending_binding = {
                **pending_payload,
                "pending_binding_sha256": pending["pending_binding_sha256"],
            }
        snapshot_record = None
        if result.snapshot_sha256:
            from solana_alpha_lab.factory.observation_panel_coverage import (
                load_coverage_from_rdp,
            )

            snapshot_record = dict(
                load_coverage_from_rdp(data_root).snapshots.get(result.snapshot_sha256)
                or {}
            )
        if (
            result.terminal == PANEL_REUSE_READY
            and snapshot_record
            and snapshot_record.get("dataset_manifest_ids")
            and snapshot_record.get("dataset_fingerprints")
        ):
            cutoff = snapshot_record["availability_cutoff"]
            snapshot = build_panel_snapshot(
                schedule_sha256=str(
                    result.covering_schedule_sha256 or result.schedule_sha256
                ),
                availability_cutoff=cutoff
                if isinstance(cutoff, datetime)
                else parse_utc(str(cutoff)),
                dataset_manifest_ids=list(snapshot_record["dataset_manifest_ids"]),
                dataset_fingerprints=list(snapshot_record["dataset_fingerprints"]),
            )
            if snapshot["snapshot_sha256"] != result.snapshot_sha256:
                raise ValueError("SNAPSHOT_IDENTITY_MISMATCH")
            snap_record_id = f"OBS-SNAP-{result.snapshot_sha256[:16].upper()}"
            from solana_alpha_lab.factory.research_store import ResearchStore

            already_durable = any(
                item.record_id == snap_record_id
                for item in ResearchStore(data_root).iter_committed_records()
            )
            if not already_durable:
                persist_panel_snapshot_binding(
                    data_root=data_root,
                    schedule=result.schedule,
                    snapshot=snapshot,
                    now=persist_clock,
                    producer_git_sha=git_sha,
                    evidence_role=result.evidence_role,
                    hypothesis_version_id=version_id,
                    run_id=run_id,
                )
    snapshot_ready = bool(
        result.terminal == PANEL_REUSE_READY
        and result.snapshot_sha256
        and passport_bindings.get("observation_panel_snapshot_sha256")
    )
    status = _capability_status(result.terminal, snapshot_ready=snapshot_ready)
    payload = {
        "status": status,
        "blocker": "NONE" if snapshot_ready else result.terminal,
        "terminal": result.terminal,
        "result": result.terminal,
        "provider_api_rpc_wss_calls": 0,
        "credential_reads": 0,
        "schedule_sha256": result.schedule_sha256,
        "covering_schedule_sha256": result.covering_schedule_sha256,
        "snapshot_sha256": result.snapshot_sha256,
        "evidence_role": result.evidence_role,
        "hypothesis_registered_at": render_utc(result.hypothesis_registered_at)
        if result.hypothesis_registered_at is not None
        else None,
        "experiment_as_of": render_utc(result.experiment_as_of)
        if result.experiment_as_of is not None
        else None,
        "classifier_evaluated_at": render_utc(result.classifier_evaluated_at)
        if result.classifier_evaluated_at is not None
        else None,
        "next_action": result.next_action,
        "reason_codes": list(result.reason_codes),
        "passport_bindings": passport_bindings,
        "authority_status": authority_status,
        "authority_request": authority_request,
        "pending_binding": pending_binding,
        "result_digest_sha256": canonical_sha256(
            {
                "terminal": result.terminal,
                "schedule_sha256": result.schedule_sha256,
                "snapshot_sha256": result.snapshot_sha256,
            }
        ),
    }
    return payload


def bind_observation_run_passport(
    payload: Mapping[str, Any],
    *,
    observation_schedule_sha256: str,
    observation_panel_snapshot_sha256: str,
) -> Any:
    bound = dict(payload)
    bound["observation_schedule_sha256"] = observation_schedule_sha256
    bound["observation_panel_snapshot_sha256"] = observation_panel_snapshot_sha256
    return validate_run_passport(bound)


__all__ = [
    "bind_observation_run_passport",
    "compile_and_bind_observation_schedule",
]
