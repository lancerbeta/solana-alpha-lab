"""Generic ExperimentRunner. Contains no hypothesis business logic."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from solana_alpha_lab.factory.capabilities import (
    CapabilityError,
    execute_capability,
    resolve_data_requirements,
)
from solana_alpha_lab.factory.experiment_spec import (
    ExperimentSpecError,
    load_experiment_spec,
    spec_sha256,
)
from solana_alpha_lab.factory.operational_store import OperationalStore


class ExperimentRunnerError(ValueError):
    """Raised when the generic runner cannot proceed fail-closed."""


def job_id_for(experiment_id: str) -> str:
    return f"JOB-{experiment_id}"


class ExperimentRunner:
    def __init__(self, *, root: Path, store: OperationalStore) -> None:
        self.root = root
        self.store = store

    def _job_record(
        self,
        spec: Mapping[str, Any],
        spec_relative: str,
        digest: str,
        *,
        status: str,
        blocker: str,
        terminal: str | None,
        evidence: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "job_id": job_id_for(str(spec["experiment_id"])),
            "experiment_id": spec["experiment_id"],
            "spec_relative": spec_relative,
            "spec_sha256": digest,
            "status": status,
            "blocker": blocker,
            "terminal": terminal,
            "evidence": dict(evidence),
        }

    def start(self, spec_relative: str) -> dict[str, Any]:
        try:
            spec = load_experiment_spec(self.root, spec_relative)
            digest = spec_sha256(self.root, spec_relative)
        except ExperimentSpecError as exc:
            raise ExperimentRunnerError(str(exc)) from exc
        existing = self.store.get_job(job_id_for(str(spec["experiment_id"])))
        if existing and existing["status"] in {"STOPPED", "PARKED"}:
            raise ExperimentRunnerError("JOB_NOT_RUNNABLE")
        coverage = resolve_data_requirements(spec, root=self.root)
        running = self._job_record(
            spec,
            spec_relative,
            digest,
            status="RUNNING",
            blocker="NONE" if coverage["sufficient"] else "BLOCKED_DATA",
            terminal=None,
            evidence={"coverage": coverage},
        )
        self.store.upsert_job(running)
        self.store.record_command(job_id=running["job_id"], kind="START", payload={"spec": spec_relative})
        if not coverage["sufficient"]:
            blocked = dict(running)
            blocked["status"] = "BLOCKED_DATA"
            blocked["blocker"] = "MISSING_OR_MISMATCHED_EVIDENCE"
            self.store.upsert_job(blocked)
            return blocked
        try:
            result = execute_capability(spec, root=self.root)
        except CapabilityError as exc:
            failed = dict(running)
            failed["status"] = "FAILED"
            failed["blocker"] = str(exc)
            self.store.upsert_job(failed)
            return failed
        finished = self._job_record(
            spec,
            spec_relative,
            digest,
            status=str(result["status"]),
            blocker=str(result.get("blocker") or "NONE"),
            terminal=result.get("terminal"),
            evidence=result,
        )
        self.store.upsert_job(finished)
        return finished

    def stop(self, experiment_id: str) -> dict[str, Any]:
        job = self.store.get_job(job_id_for(experiment_id))
        if job is None:
            raise ExperimentRunnerError("JOB_NOT_FOUND")
        job["status"] = "STOPPED"
        job["blocker"] = "OWNER_STOP"
        self.store.upsert_job(job)
        self.store.record_command(job_id=job["job_id"], kind="STOP", payload={})
        return job

    def park(self, experiment_id: str) -> dict[str, Any]:
        job = self.store.get_job(job_id_for(experiment_id))
        if job is None:
            raise ExperimentRunnerError("JOB_NOT_FOUND")
        job["status"] = "PARKED"
        job["blocker"] = "OWNER_PARK"
        self.store.upsert_job(job)
        self.store.record_command(job_id=job["job_id"], kind="PARK", payload={})
        return job
