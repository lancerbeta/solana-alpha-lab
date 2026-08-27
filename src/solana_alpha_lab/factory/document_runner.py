"""Document Fast Lane runner. Leaves the generic ExperimentRunner bytes unchanged."""

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

from solana_alpha_lab.factory.capabilities import CapabilityError, execute_capability
from solana_alpha_lab.factory.data_resolver import (
    EvidenceResolutionError,
    resolve_evidence_bindings,
    resolve_query_recipe_hashes,
)
from solana_alpha_lab.factory.git_write_fence import (
    RepositoryGitSnapshot,
    repository_git_snapshot,
    repository_status_bytes,
)
from solana_alpha_lab.factory.lane_classifier import Lane, LaneDecision
from solana_alpha_lab.factory.research_store import (
    RecordKind,
    ResearchEvent,
    ResearchStore,
    ResearchStoreError,
)
from solana_alpha_lab.factory.run_passport import (
    RunPassportError,
    canonical_sha256,
    validate_run_passport,
)
from solana_alpha_lab.factory.runner import ExperimentRunner, ExperimentRunnerError


@dataclass(frozen=True, slots=True)
class RunContext:
    data_root: Path
    hypothesis_definition_sha256: str
    lane_decision: LaneDecision


def _git_head_sha(root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ExperimentRunnerError("RUNNER_GIT_SHA_UNAVAILABLE")
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


def _event_time(spec: Mapping[str, Any]) -> datetime:
    raw = spec.get("as_of") or spec.get("availability_cutoff")
    if not isinstance(raw, str):
        raise ExperimentRunnerError("EXPERIMENT_AS_OF_INVALID")
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC)


class DocumentRunner(ExperimentRunner):
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

        git_before = repository_git_snapshot(self.root)
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
        git_after = repository_git_snapshot(self.root)
        git_mutation_count = 0 if git_before.unchanged(git_after) else 1

        run_id = _run_id(lane.run_key_sha256)
        capability_id = str(spec["capability_id"])
        producer_git_sha = _git_head_sha(self.root)
        now = _event_time(spec)
        transaction_id = f"RESEARCH-TXN-{uuid.uuid4().hex[:16].upper()}"

        if git_mutation_count:
            invalid_payload = {
                "run_id": run_id,
                "run_key_sha256": lane.run_key_sha256,
                "reason_code": "GIT_MUTATION_DETECTED",
                "git_snapshot_before_sha256": git_before.composite_sha256,
                "git_snapshot_after_sha256": git_after.composite_sha256,
                "git_head_before": git_before.head_sha,
                "git_head_after": git_after.head_sha,
                "git_symbolic_ref_before": git_before.symbolic_ref,
                "git_symbolic_ref_after": git_after.symbolic_ref,
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

        query_recipe_ids = list(spec.get("query_recipe_ids") or [])
        if query_recipe_ids:
            resolved_recipes = resolve_query_recipe_hashes(
                query_recipe_ids,
                root=self.root,
            )
            query_recipe_sha256s = [recipe_sha for _, recipe_sha in resolved_recipes]
            query_recipe_binding = {
                "status": "BOUND",
                "recipes": [
                    {
                        "recipe_id": recipe_id,
                        "query_recipe_sha256": recipe_sha,
                    }
                    for recipe_id, recipe_sha in resolved_recipes
                ],
            }
        else:
            query_recipe_sha256s = []
            query_recipe_binding = {
                "status": "NOT_APPLICABLE",
                "reason": "CAPABILITY_DESCRIPTOR_QUERY_RECIPE_NOT_REQUIRED",
            }

        result_artifact_id = f"RESULT-ARTIFACT-{run_id.removeprefix('RUN-')}"
        result_artifact_logical_uri = (
            f"smial-data://research/artifacts/results/{result_artifact_id}.json"
        )
        result_artifact_payload = {
            "research_artifact_id": result_artifact_id,
            "logical_uri": result_artifact_logical_uri,
            "artifact_kind": "CAPABILITY_RESULT",
            "capability_result": capability_result,
            "first_reliable_available_at": now.isoformat().replace("+00:00", "Z"),
        }
        result_artifact_path = (
            run_context.data_root
            / "research"
            / "artifacts"
            / "results"
            / f"{result_artifact_id}.json"
        )
        result_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        result_artifact_path.write_text(
            json.dumps(
                result_artifact_payload,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            ),
            encoding="utf-8",
        )

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
            "query_recipe_ids": query_recipe_ids,
            "query_recipe_sha256s": query_recipe_sha256s,
            "query_recipe_binding": query_recipe_binding,
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
            "result_artifact_id": result_artifact_id,
            "result_artifact_logical_uri": result_artifact_logical_uri,
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
                record_id=f"HYPOTHESIS-VERSION-{transaction_id[-16:]}",
                record_kind=RecordKind.HYPOTHESIS_VERSION,
                entity_id=str(spec["hypothesis_version"]),
                hypothesis_version_id=str(spec["hypothesis_version"]),
                run_id=None,
                transaction_id=transaction_id,
                effective_at=now,
                payload={
                    "hypothesis_version_id": str(spec["hypothesis_version"]),
                    "family_id": "HYP-FAMILY-FAST-LANE-001",
                    "version_ordinal": 1,
                    "origin_id": "HYP-ORIGIN-FAST-LANE-001",
                    "origin_kind": "DATA_ANALYSIS",
                    "research_cycle_id": "RESEARCH-CYCLE-FAST-LANE-001",
                    "definition_sha256": run_context.hypothesis_definition_sha256,
                    "statement": str(spec.get("question") or ""),
                    "mechanism": str(spec.get("method") or ""),
                    "falsifier": str(spec.get("falsifier") or ""),
                    "expected_regime_terms": [],
                    "what_changed": (
                        str(spec["what_changed"][0])
                        if isinstance(spec.get("what_changed"), list)
                        and spec["what_changed"]
                        else "FAST_LANE_RUN"
                    ),
                },
                producer_capability_id=capability_id,
                producer_git_sha=producer_git_sha,
            ),
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
                payload={
                    **passport.model_dump(mode="json"),
                    "git_mutation_count": git_mutation_count,
                },
                producer_capability_id=capability_id,
                producer_git_sha=producer_git_sha,
            ),
        ]
        metric_id = f"METRIC-TERMINAL-MATCH-{transaction_id[-8:]}"
        records.append(
            _research_event(
                record_id=metric_id,
                record_kind=RecordKind.EXPERIMENT_METRIC,
                entity_id=metric_id,
                hypothesis_version_id=str(spec["hypothesis_version"]),
                run_id=run_id,
                transaction_id=transaction_id,
                effective_at=now,
                payload={
                    "metric_id": metric_id,
                    "metric_name": "accepted_terminal_match",
                    "scalar_value": (
                        1.0
                        if capability_result.get("terminal")
                        == capability_result.get("accepted_terminal")
                        else 0.0
                    ),
                    "unit": "boolean",
                    "run_id": run_id,
                },
                producer_capability_id=capability_id,
                producer_git_sha=producer_git_sha,
            )
        )
        records.append(
            _research_event(
                record_id=result_artifact_id,
                record_kind=RecordKind.RESEARCH_ARTIFACT,
                entity_id=result_artifact_id,
                hypothesis_version_id=str(spec["hypothesis_version"]),
                run_id=run_id,
                transaction_id=transaction_id,
                effective_at=now,
                payload={
                    "research_artifact_id": result_artifact_id,
                    "logical_uri": result_artifact_logical_uri,
                    "artifact_kind": "CAPABILITY_RESULT",
                    "content_sha256": canonical_sha256(
                        result_artifact_payload["capability_result"]
                    ),
                    "result_digest_sha256": passport_payload["result_digest_sha256"],
                    "capability_result": capability_result,
                },
                producer_capability_id=capability_id,
                producer_git_sha=producer_git_sha,
            )
        )
        for index, item in enumerate(evidence):
            binding_record_id = f"EVIDENCE-BINDING-{index + 1:03d}-{transaction_id[-8:]}"
            binding_payload = dict(item.to_payload())
            binding_payload["evidence_binding_id"] = binding_record_id
            records.append(
                _research_event(
                    record_id=binding_record_id,
                    record_kind=RecordKind.EVIDENCE_BINDING,
                    entity_id=binding_record_id,
                    hypothesis_version_id=str(spec["hypothesis_version"]),
                    run_id=run_id,
                    transaction_id=transaction_id,
                    effective_at=now,
                    payload=binding_payload,
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


__all__ = [
    "DocumentRunner",
    "ExperimentRunnerError",
    "RunContext",
    "repository_git_snapshot",
    "repository_status_bytes",
]
