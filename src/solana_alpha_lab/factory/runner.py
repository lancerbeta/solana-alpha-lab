"""Generic ExperimentRunner. Contains no hypothesis business logic."""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.capabilities import (
    CapabilityError,
    execute_capability,
    resolve_data_requirements,
)
from solana_alpha_lab.factory.data_resolver import (
    EvidenceResolutionError,
    resolve_evidence_bindings,
)
from solana_alpha_lab.factory.experiment_spec import (
    ExperimentSpecError,
    load_experiment_spec,
    spec_sha256,
    validate_experiment_document,
)
from solana_alpha_lab.factory.lane_classifier import Lane, LaneDecision, classify_lane
from solana_alpha_lab.factory.operational_store import OperationalStore
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
    experiment_spec_sha256,
    validate_run_passport,
)


class ExperimentRunnerError(ValueError):
    """Raised when the generic runner cannot proceed fail-closed."""


@dataclass(frozen=True, slots=True)
class RunContext:
    data_root: Path
    hypothesis_definition_sha256: str
    lane_decision: LaneDecision


def job_id_for(experiment_id: str) -> str:
    return f"JOB-{experiment_id}"


def repository_status_bytes(root: Path) -> bytes:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    return completed.stdout


def _git_head_sha(root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    value = completed.stdout.decode("ascii", errors="ignore").strip()
    if len(value) != 40:
        raise ExperimentRunnerError("RUNNER_GIT_SHA_UNAVAILABLE")
    return value


def _run_id(run_key_sha256: str) -> str:
    return f"RUN-{run_key_sha256[:24].upper()}"


def _payload_json(payload: Mapping[str, Any]) -> tuple[str, str]:
    text = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def _research_event(
    *,
    record_id: str,
    record_kind: RecordKind,
    entity_id: str,
    hypothesis_version_id: str | None,
    run_id: str | None,
    transaction_id: str,
    effective_at: datetime,
    payload: Mapping[str, Any],
    producer_capability_id: str,
    producer_git_sha: str,
) -> ResearchEvent:
    payload_json, payload_sha256 = _payload_json(payload)
    return ResearchEvent(
        record_id=record_id,
        record_kind=record_kind,
        entity_id=entity_id,
        hypothesis_version_id=hypothesis_version_id,
        run_id=run_id,
        transaction_id=transaction_id,
        effective_at=effective_at,
        first_reliable_available_at=effective_at,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=payload_sha256,
        schema_version="1.0",
        producer_capability_id=producer_capability_id,
        producer_git_sha=producer_git_sha,
        created_at=effective_at,
    )


def _scientific_outcome(
    capability_result: Mapping[str, Any],
) -> tuple[str, str, str]:
    status = str(capability_result.get("status") or "")
    if status == "BLOCKED_DATA":
        return "BLOCKED_DATA", "INVALID", "INVALID"
    if status != "COMPLETE":
        return "FAILED_INFRA", "INVALID", "INVALID"
    terminal = str(capability_result.get("terminal") or "")
    if terminal in {"FAIL", "FALSIFIED", "TERMINAL_MISMATCH"}:
        return "COMPLETE", "NEGATIVE", "REJECTED"
    if terminal in {"INCONCLUSIVE", "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY"}:
        return "COMPLETE", "INCONCLUSIVE", "INCONCLUSIVE"
    return "COMPLETE", "INCONCLUSIVE", "INCONCLUSIVE"


def _document_response(
    *,
    lane_decision: LaneDecision,
    execution_status: str,
    scientific_terminal: str,
    reason_codes: tuple[str, ...],
    run_id: str | None,
    git_mutation_count: int,
    provider_calls_actual: int,
    next_action: str,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "lane": lane_decision.lane.value,
        "status": execution_status,
        "scientific_terminal": scientific_terminal,
        "reason_codes": list(reason_codes),
        "run_id_or_null": run_id,
        "git_mutation_count": git_mutation_count,
        "provider_calls_actual": provider_calls_actual,
        "next_action": next_action,
        "run_key_sha256": lane_decision.run_key_sha256,
        "prior_run_id": lane_decision.prior_run_id,
    }
    if extra:
        payload.update(dict(extra))
    return payload


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

    def start(
        self,
        spec_relative: str,
        *,
        authority_phrase: str | None = None,
        capture_hooks: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            spec = load_experiment_spec(self.root, spec_relative)
            digest = spec_sha256(self.root, spec_relative)
        except ExperimentSpecError as exc:
            raise ExperimentRunnerError(str(exc)) from exc
        existing = self.store.get_job(job_id_for(str(spec["experiment_id"])))
        if existing and existing["status"] in {"STOPPED", "PARKED"}:
            raise ExperimentRunnerError("JOB_NOT_RUNNABLE")
        if existing and existing["status"] == "COMPLETE":
            return existing
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
        self.store.record_command(
            job_id=running["job_id"],
            kind="START",
            payload={"spec": spec_relative},
        )
        if not coverage["sufficient"]:
            blocked = dict(running)
            blocked["status"] = "BLOCKED_DATA"
            blocked["blocker"] = "MISSING_OR_MISMATCHED_EVIDENCE"
            self.store.upsert_job(blocked)
            return blocked
        try:
            result = execute_capability(
                spec,
                root=self.root,
                authority_phrase=authority_phrase,
                capture_hooks=capture_hooks,
            )
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

    def start_document(
        self,
        spec: Mapping[str, Any],
        *,
        spec_sha256: str,
        run_context: RunContext,
        authority_phrase: str | None = None,
        capture_hooks: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a classified Fast Lane document without mutating Git."""

        lane = run_context.lane_decision
        if lane.lane == Lane.PROMOTION_LANE:
            return _document_response(
                lane_decision=lane,
                execution_status="BLOCKED_AUTHORITY",
                scientific_terminal="INVALID",
                reason_codes=lane.reason_codes,
                run_id=None,
                git_mutation_count=0,
                provider_calls_actual=0,
                next_action=lane.next_action,
            )
        if lane.lane == Lane.CHANGE_LANE:
            return _document_response(
                lane_decision=lane,
                execution_status="FAILED_INFRA",
                scientific_terminal="INVALID",
                reason_codes=lane.reason_codes,
                run_id=None,
                git_mutation_count=0,
                provider_calls_actual=0,
                next_action=lane.next_action,
            )
        if lane.lane == Lane.DENY:
            return _document_response(
                lane_decision=lane,
                execution_status="INVALID_EVIDENCE",
                scientific_terminal="INVALID",
                reason_codes=lane.reason_codes,
                run_id=None,
                git_mutation_count=0,
                provider_calls_actual=0,
                next_action=lane.next_action,
            )
        if lane.terminal == "REPLAY_AVAILABLE":
            return _document_response(
                lane_decision=lane,
                execution_status="COMPLETE",
                scientific_terminal="INCONCLUSIVE",
                reason_codes=lane.reason_codes,
                run_id=lane.prior_run_id,
                git_mutation_count=0,
                provider_calls_actual=0,
                next_action=lane.next_action,
            )
        if lane.terminal == "BLOCKED_DATA":
            return _document_response(
                lane_decision=lane,
                execution_status="BLOCKED_DATA",
                scientific_terminal="INVALID",
                reason_codes=lane.reason_codes,
                run_id=None,
                git_mutation_count=0,
                provider_calls_actual=0,
                next_action=lane.next_action,
            )
        if lane.terminal == "FAST_LANE_OWNER_GATE_REQUIRED" and not authority_phrase:
            return _document_response(
                lane_decision=lane,
                execution_status="BLOCKED_AUTHORITY",
                scientific_terminal="INVALID",
                reason_codes=lane.reason_codes,
                run_id=None,
                git_mutation_count=0,
                provider_calls_actual=0,
                next_action=lane.next_action,
            )
        if lane.terminal not in {"FAST_LANE_READY", "FAST_LANE_OWNER_GATE_REQUIRED"}:
            return _document_response(
                lane_decision=lane,
                execution_status="FAILED_INFRA",
                scientific_terminal="INVALID",
                reason_codes=lane.reason_codes,
                run_id=None,
                git_mutation_count=0,
                provider_calls_actual=0,
                next_action=lane.next_action,
            )

        if lane.run_key_sha256 is None:
            raise ExperimentRunnerError("RUN_KEY_SHA256_REQUIRED")

        git_before = repository_status_bytes(self.root)
        try:
            capability_result = execute_capability(
                spec,
                root=self.root,
                authority_phrase=authority_phrase,
                capture_hooks=capture_hooks,
            )
        except CapabilityError as exc:
            return _document_response(
                lane_decision=lane,
                execution_status="FAILED_INFRA",
                scientific_terminal="INVALID",
                reason_codes=(str(exc),),
                run_id=None,
                git_mutation_count=0,
                provider_calls_actual=0,
                next_action="CORRECT_CAPABILITY_INPUT",
            )
        git_after = repository_status_bytes(self.root)
        git_mutation_count = 0 if git_before == git_after else 1

        run_id = _run_id(lane.run_key_sha256)
        capability_id = str(spec["capability_id"])
        producer_git_sha = _git_head_sha(self.root)
        now = datetime.now(tz=UTC)
        transaction_id = f"RESEARCH-TXN-{uuid.uuid4().hex[:16].upper()}"

        if git_mutation_count:
            invalid_payload = {
                "run_id": run_id,
                "run_key_sha256": lane.run_key_sha256,
                "reason_code": "GIT_MUTATION_DETECTED",
                "git_status_before_sha256": hashlib.sha256(git_before).hexdigest(),
                "git_status_after_sha256": hashlib.sha256(git_after).hexdigest(),
            }
            try:
                ResearchStore(run_context.data_root).append(
                    [
                        _research_event(
                            record_id=f"RUN-INVALID-{transaction_id[-16:]}",
                            record_kind=RecordKind.RUN_INVALID,
                            entity_id=run_id,
                            hypothesis_version_id=str(spec["hypothesis_version"]),
                            run_id=run_id,
                            transaction_id=transaction_id,
                            effective_at=now,
                            payload=invalid_payload,
                            producer_capability_id=capability_id,
                            producer_git_sha=producer_git_sha,
                        )
                    ],
                    transaction_id=transaction_id,
                )
            except ResearchStoreError:
                pass
            return _document_response(
                lane_decision=lane,
                execution_status="INVALID_EVIDENCE",
                scientific_terminal="INVALID",
                reason_codes=("GIT_MUTATION_DETECTED",),
                run_id=run_id,
                git_mutation_count=git_mutation_count,
                provider_calls_actual=int(
                    capability_result.get("provider_api_rpc_wss_calls") or 0
                ),
                next_action="INVESTIGATE_GIT_MUTATION",
            )

        execution_status, trial_outcome, scientific_terminal = _scientific_outcome(
            capability_result
        )
        provider_calls_actual = int(
            capability_result.get("provider_api_rpc_wss_calls") or 0
        )

        try:
            evidence = resolve_evidence_bindings(
                spec,
                root=self.root,
                data_root=run_context.data_root,
            )
        except EvidenceResolutionError:
            evidence = ()

        passport_payload: dict[str, Any] = {
            "run_id": run_id,
            "run_key_sha256": lane.run_key_sha256,
            "trial_id": f"TRIAL-{run_id.removeprefix('RUN-')}",
            "hypothesis_version_id": str(spec["hypothesis_version"]),
            "hypothesis_definition_sha256": run_context.hypothesis_definition_sha256,
            "experiment_spec_sha256": spec_sha256,
            "runner_capability_id": capability_id,
            "runner_git_sha": producer_git_sha,
            "capability_closure_sha256": canonical_sha256(
                {"capability_id": capability_id, "spec_sha256": spec_sha256}
            ),
            "uv_lock_sha256": hashlib.sha256(
                (self.root / "uv.lock").read_bytes()
            ).hexdigest(),
            "dataset_manifest_ids": [
                item.stable_id
                for item in evidence
                if item.source_kind == "DATASET_MANIFEST"
            ],
            "dataset_fingerprints": [
                item.dataset_fingerprint
                for item in evidence
                if item.dataset_fingerprint is not None
            ],
            "query_recipe_ids": list(spec.get("query_recipe_ids") or []),
            "query_recipe_sha256s": [],
            "config_sha256": canonical_sha256(spec.get("parameters") or {}),
            "as_of": spec["as_of"],
            "availability_cutoff": spec["availability_cutoff"],
            "holdout_consumption_ids": [],
            "random_seed_or_null": None,
            "started_at": now.isoformat().replace("+00:00", "Z"),
            "completed_at": now.isoformat().replace("+00:00", "Z"),
            "first_reliable_available_at": now.isoformat().replace("+00:00", "Z"),
            "provider_calls_planned": int(
                spec["evidence_budget"]["provider_api_rpc_wss_calls"]
            ),
            "provider_calls_actual": provider_calls_actual,
            "cash_spend_usd_cents": 0,
            "execution_status": execution_status,
            "trial_outcome": trial_outcome,
            "scientific_terminal": scientific_terminal,
            "result_digest_sha256": canonical_sha256(capability_result),
            "artifact_manifest_sha256": hashlib.sha256(
                json.dumps(
                    capability_result,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            "limitations": [],
            "non_claims": ["NO_ALPHA", "NO_NETRETURN"],
        }
        try:
            passport = validate_run_passport(passport_payload)
        except RunPassportError as exc:
            return _document_response(
                lane_decision=lane,
                execution_status="INVALID_EVIDENCE",
                scientific_terminal="INVALID",
                reason_codes=(str(exc),),
                run_id=run_id,
                git_mutation_count=0,
                provider_calls_actual=provider_calls_actual,
                next_action="CORRECT_RUN_PASSPORT",
            )

        records: list[ResearchEvent] = [
            _research_event(
                record_id=f"RUN-STARTED-{transaction_id[-16:]}",
                record_kind=RecordKind.RUN_STARTED,
                entity_id=run_id,
                hypothesis_version_id=str(spec["hypothesis_version"]),
                run_id=run_id,
                transaction_id=transaction_id,
                effective_at=now,
                payload={"run_id": run_id, "run_key_sha256": lane.run_key_sha256},
                producer_capability_id=capability_id,
                producer_git_sha=producer_git_sha,
            ),
            _research_event(
                record_id=f"RUN-COMPLETED-{transaction_id[-16:]}",
                record_kind=RecordKind.RUN_COMPLETED,
                entity_id=run_id,
                hypothesis_version_id=str(spec["hypothesis_version"]),
                run_id=run_id,
                transaction_id=transaction_id,
                effective_at=now,
                payload=dict(passport.model_dump(mode="json")),
                producer_capability_id=capability_id,
                producer_git_sha=producer_git_sha,
            ),
        ]
        for index, item in enumerate(evidence):
            records.append(
                _research_event(
                    record_id=f"EVIDENCE-BINDING-{index + 1:03d}-{transaction_id[-8:]}",
                    record_kind=RecordKind.EVIDENCE_BINDING,
                    entity_id=run_id,
                    hypothesis_version_id=str(spec["hypothesis_version"]),
                    run_id=run_id,
                    transaction_id=transaction_id,
                    effective_at=now,
                    payload=item.to_payload(),
                    producer_capability_id=capability_id,
                    producer_git_sha=producer_git_sha,
                )
            )

        store = ResearchStore(run_context.data_root)
        store.append(records, transaction_id=transaction_id)
        store.rebuild_projection()

        return _document_response(
            lane_decision=lane,
            execution_status=execution_status,
            scientific_terminal=scientific_terminal,
            reason_codes=(),
            run_id=run_id,
            git_mutation_count=0,
            provider_calls_actual=provider_calls_actual,
            next_action="SEARCH_PRIOR_WORK",
            extra={"passport": passport.payload, "capability_result": capability_result},
        )

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


__all__ = [
    "ExperimentRunner",
    "ExperimentRunnerError",
    "RunContext",
    "job_id_for",
    "repository_status_bytes",
]
