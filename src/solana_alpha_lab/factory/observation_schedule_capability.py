"""Fast Lane capability: compile/register/bind ObservationSchedule without provider calls."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.observation_panel_publisher import (
    build_panel_snapshot,
    persist_observation_schedule,
    persist_panel_snapshot_binding,
)
from solana_alpha_lab.factory.observation_schedule_compiler import compile_observation_request
from solana_alpha_lab.factory.run_passport import canonical_sha256, validate_run_passport


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
) -> dict[str, Any]:
    result = compile_observation_request(
        spec,
        root=root,
        coverage=coverage,
        closed_family=closed_family,
        data_root=data_root,
    )
    passport_bindings: dict[str, str] = {}
    if result.schedule_sha256:
        passport_bindings["observation_schedule_sha256"] = result.schedule_sha256
    if result.snapshot_sha256:
        passport_bindings["observation_panel_snapshot_sha256"] = result.snapshot_sha256
    clock = now or datetime.now(UTC)
    git_sha = producer_git_sha or ("c" * 40)
    if data_root is not None and result.schedule is not None:
        persist_observation_schedule(
            data_root=data_root,
            schedule=result.schedule,
            now=clock,
            producer_git_sha=git_sha,
            activation_id=run_id,
        )
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
            result.terminal == "PANEL_REUSE_READY"
            and snapshot_record
            and snapshot_record.get("dataset_manifest_ids")
            and snapshot_record.get("dataset_fingerprints")
        ):
            cutoff = snapshot_record["availability_cutoff"]
            snapshot = build_panel_snapshot(
                schedule_sha256=str(
                    result.covering_schedule_sha256 or result.schedule_sha256
                ),
                availability_cutoff=cutoff,
                dataset_manifest_ids=list(snapshot_record["dataset_manifest_ids"]),
                dataset_fingerprints=list(snapshot_record["dataset_fingerprints"]),
            )
            if snapshot["snapshot_sha256"] != result.snapshot_sha256:
                raise ValueError("SNAPSHOT_IDENTITY_MISMATCH")
            persist_panel_snapshot_binding(
                data_root=data_root,
                schedule=result.schedule,
                snapshot=snapshot,
                now=clock,
                producer_git_sha=git_sha,
                evidence_role=result.evidence_role,
                hypothesis_version_id=hypothesis_version_id,
                run_id=run_id,
            )
    return {
        "status": "COMPLETE" if result.terminal not in {
            "DENY_OUTCOME_LEAKAGE",
            "DENY_RETROACTIVE_MUTATION",
            "DENY_UNSAFE_RUNTIME_CODE",
        } else "FAILED",
        "blocker": "NONE" if result.schedule_sha256 else result.terminal,
        "terminal": result.terminal,
        "result": result.terminal,
        "provider_api_rpc_wss_calls": 0,
        "credential_reads": 0,
        "schedule_sha256": result.schedule_sha256,
        "snapshot_sha256": result.snapshot_sha256,
        "evidence_role": result.evidence_role,
        "next_action": result.next_action,
        "reason_codes": list(result.reason_codes),
        "passport_bindings": passport_bindings,
        "result_digest_sha256": canonical_sha256(
            {
                "terminal": result.terminal,
                "schedule_sha256": result.schedule_sha256,
                "snapshot_sha256": result.snapshot_sha256,
            }
        ),
    }


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
