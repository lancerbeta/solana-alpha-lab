"""HFIC preflight: commissioning proof, evidence epoch, and session budget."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import duckdb
import yaml

from solana_alpha_lab.factory.commissioning_fixture import (
    COMMISSIONING_DATASET_MANIFEST_ID,
    commissioning_dataset_fingerprint,
)
from solana_alpha_lab.factory.hfic_session import (
    PENDING_STATES,
    PROMPT_VERSION,
    evidence_epoch_sha256,
    focus_key_sha256,
    list_hfic_sessions,
    load_session_bundle,
    pick_session,
    search_key_sha256,
)
from solana_alpha_lab.factory.research_store import (
    RESEARCH_PROJECTION_LOCATION,
    RecordKind,
    ResearchStore,
    ResearchStoreError,
)
from solana_alpha_lab.factory.run_passport import (
    RunPassportError,
    canonical_sha256,
    validate_run_passport,
)
from solana_alpha_lab.factory.fast_lane_cold_copy import (
    ColdCopyError,
    load_run_result_artifact,
)


AUTO_FOCUS = "AUTO"
AUTO_SESSIONS_PER_EPOCH = 1
MAX_DISTINCT_FOCUSES_PER_EPOCH = 3
GOLDEN_OFFLINE_SPEC = (
    "configs/experiment_specs/quote_native_admissible_friction_audition_offline_v1.yaml"
)
HYPOTHESIS_DEFINITION_SHA256 = "1" * 64
_EPOCH_FILES = (
    "catalog/catalog_manifest.yaml",
    "catalog/query_recipes.yaml",
    "configs/hypothesis_forge_independent_critic_v1.yaml",
    "catalog/schemas/hypothesis_critic_input_v1.schema.json",
    "catalog/schemas/experiment_spec.schema.json",
)


class HficPreflightError(ValueError):
    """Fail-closed preflight / commissioning proof error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def prove_fast_lane_commissioned(data_root: Path) -> dict[str, Any]:
    try:
        store = ResearchStore(Path(data_root))
    except ResearchStoreError as exc:
        raise HficPreflightError("FAST_LANE_NOT_COMMISSIONED") from exc
    completed: dict[str, Any] | None = None
    has_metric = False
    has_binding = False
    has_hypothesis = False
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if kind == RecordKind.EXPERIMENT_METRIC.value:
            has_metric = True
        elif kind == RecordKind.EVIDENCE_BINDING.value:
            has_binding = True
        elif kind == RecordKind.HYPOTHESIS_VERSION.value:
            has_hypothesis = True
        if kind != RecordKind.RUN_COMPLETED.value:
            continue
        try:
            payload = json.loads(record.payload_json)
        except (ValueError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        manifests = list(payload.get("dataset_manifest_ids") or []) + list(
            payload.get("ordered_input_dataset_manifest_ids") or []
        )
        encoded = json.dumps(payload, ensure_ascii=False)
        if COMMISSIONING_DATASET_MANIFEST_ID not in manifests and (
            COMMISSIONING_DATASET_MANIFEST_ID not in encoded
        ):
            continue
        completed = payload
    if (
        completed is None
        or not has_metric
        or not has_binding
        or not has_hypothesis
    ):
        raise HficPreflightError("FAST_LANE_NOT_COMMISSIONED")
    try:
        passport = dict(validate_run_passport(completed).payload)
    except RunPassportError as exc:
        raise HficPreflightError("FAST_LANE_NOT_COMMISSIONED") from exc
    if int(passport.get("provider_calls_actual") or 0) != 0:
        raise HficPreflightError("FAST_LANE_NOT_COMMISSIONED")
    try:
        artifact = load_run_result_artifact(Path(data_root), passport)
    except ColdCopyError as exc:
        raise HficPreflightError("FAST_LANE_NOT_COMMISSIONED") from exc
    stored_digest = str(passport.get("result_digest_sha256") or "")
    recomputed = canonical_sha256(artifact["capability_result"])
    if not stored_digest or recomputed != stored_digest:
        raise HficPreflightError("FAST_LANE_NOT_COMMISSIONED")
    return {
        "status": "NO_GIT_FAST_LANE_PROVEN",
        "commissioning_dataset_manifest_id": COMMISSIONING_DATASET_MANIFEST_ID,
        "provider_calls_actual": 0,
        "git_mutation_count": int(passport.get("git_mutation_count") or 0),
        "run_id": passport.get("run_id"),
        "result_artifact_id": passport.get("result_artifact_id"),
    }


def is_fast_lane_commissioned(data_root: Path) -> bool:
    try:
        prove_fast_lane_commissioned(data_root)
    except HficPreflightError:
        return False
    return True


def store_inventory_digest(data_root: Path) -> str | None:
    try:
        return ResearchStore(Path(data_root)).diagnostics().committed_inventory_sha256
    except ResearchStoreError:
        return None


def evidence_epoch_material(
    repo_root: Path,
    data_root: Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root)
    hashes = [
        hashlib.sha256((root / relative).read_bytes()).hexdigest()
        for relative in _EPOCH_FILES
    ]
    prior_parts: list[str] = []
    if data_root is not None:
        try:
            store = ResearchStore(Path(data_root))
            for record in store.iter_committed_records():
                payload = json.loads(record.payload_json)
                if payload.get("hfic_protocol"):
                    continue
                prior_parts.append(f"{record.record_id}:{record.payload_sha256}")
        except (ResearchStoreError, ValueError, json.JSONDecodeError):
            prior_parts = []
    prior_digest = hashlib.sha256(
        "\n".join(sorted(prior_parts)).encode("utf-8")
        if prior_parts
        else b"HFIC-EPOCH-CATALOG-BINDING-V1"
    ).hexdigest()
    return {
        "catalog_root_hashes": hashes,
        "dataset_manifest_ids": [COMMISSIONING_DATASET_MANIFEST_ID],
        "dataset_fingerprints": [commissioning_dataset_fingerprint(root)],
        "lifecycle_terminals": ["NO_GIT_FAST_LANE_PROVEN"],
        "scientific_terminals": ["INCONCLUSIVE"],
        "capability_schema_hashes": [hashes[-1]],
        "accepted_query_recipe_hashes": [hashes[1]],
        "prior_work_digest": prior_digest,
    }


def build_offline_commission_packet(repo_root: Path) -> dict[str, Any]:
    root = Path(repo_root)
    spec_path = root / GOLDEN_OFFLINE_SPEC
    catalog_sha = hashlib.sha256(
        (root / "catalog/schemas/experiment_spec.schema.json").read_bytes()
    ).hexdigest()
    base = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(base, dict):
        raise HficPreflightError("COMMISSION_PACKET_INVALID")
    base["schema_version"] = "1.1"
    base["data_bindings"] = [
        {
            "binding_id": "BINDING-CANONICAL-RECEIPT-001",
            "source_kind": "CATALOG_ASSET",
            "stable_id": "SCHEMA-EXPERIMENT-SPEC-001",
            "expected_content_sha256_or_dataset_fingerprint": catalog_sha,
        },
        {
            "binding_id": "BINDING-COMMISSIONING-DATASET-001",
            "source_kind": "DATASET_MANIFEST",
            "stable_id": COMMISSIONING_DATASET_MANIFEST_ID,
            "expected_content_sha256_or_dataset_fingerprint": (
                commissioning_dataset_fingerprint(root)
            ),
        },
    ]
    base["query_recipe_ids"] = []
    base["capability_id"] = "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"
    base["parameter_schema_asset_id"] = "SCHEMA-EXPERIMENT-SPEC-001"
    base["as_of"] = "2026-08-25T00:00:00Z"
    base["availability_cutoff"] = "2026-08-25T00:00:00Z"
    base["what_changed"] = ["INITIAL_FAST_LANE_CLI_FIXTURE"]
    return {
        "experiment_spec": base,
        "hypothesis_definition_sha256": HYPOTHESIS_DEFINITION_SHA256,
        "available_data_binding_ids": ["BINDING-CANONICAL-RECEIPT-001"],
        "completed_runs": {},
        "promotion_requested": False,
    }


def _query_hfic_sessions(data_root: Path) -> list[dict[str, Any]]:
    projection = Path(data_root) / RESEARCH_PROJECTION_LOCATION
    if not projection.is_file() or projection.is_symlink():
        return _sessions_from_store(data_root)
    connection = duckdb.connect(
        str(projection),
        read_only=True,
        config={
            "enable_external_access": "false",
            "allow_unsigned_extensions": "false",
        },
    )
    try:
        try:
            rows = connection.execute(
                """
                SELECT
                    session_id,
                    session_state,
                    evidence_epoch_sha256,
                    focus_key_sha256,
                    search_key_sha256,
                    prompt_version,
                    owner_focus
                FROM hfic_sessions
                """
            ).fetchall()
        except duckdb.Error:
            return _sessions_from_store(data_root)
    finally:
        connection.close()
    sessions = []
    for row in rows:
        sessions.append(
            {
                "session_id": row[0],
                "session_state": row[1],
                "evidence_epoch_sha256": row[2],
                "focus_key_sha256": row[3],
                "search_key_sha256": row[4],
                "prompt_version": row[5],
                "owner_focus": row[6],
            }
        )
    return sessions


def _sessions_from_store(data_root: Path) -> list[dict[str, Any]]:
    try:
        store = ResearchStore(Path(data_root))
    except ResearchStoreError:
        return []
    return list_hfic_sessions(store)


def _is_auto_focus(owner_focus: str) -> bool:
    return owner_focus.strip().casefold() == AUTO_FOCUS.casefold()


def decide_preflight_action(
    sessions: list[Mapping[str, Any]],
    *,
    search_key: str,
    evidence_epoch: str,
    focus_key: str,
    owner_focus: str,
) -> tuple[str, str | None]:
    same_focus = [
        item
        for item in sessions
        if item.get("evidence_epoch_sha256") == evidence_epoch
        and item.get("focus_key_sha256") == focus_key
    ]
    if same_focus:
        chosen = pick_session(same_focus)
        state = str(chosen.get("session_state") or "")
        session_id = str(chosen.get("session_id") or "")
        if state == "CRITIC_RESULT_READY":
            return ("RESUME_FINALIZE", session_id)
        if state in PENDING_STATES:
            return ("RESUME_CRITIC", session_id)
        return ("RETURN_EXISTING_SESSION", session_id)

    matching = [
        item for item in sessions if item.get("search_key_sha256") == search_key
    ]
    if matching:
        chosen = pick_session(matching)
        return ("RETURN_EXISTING_SESSION", str(chosen.get("session_id") or ""))

    same_epoch = [
        item
        for item in sessions
        if item.get("evidence_epoch_sha256") == evidence_epoch
    ]
    if _is_auto_focus(owner_focus):
        auto_count = sum(
            1
            for item in same_epoch
            if _is_auto_focus(str(item.get("owner_focus") or AUTO_FOCUS))
        )
        if auto_count >= AUTO_SESSIONS_PER_EPOCH:
            return ("STOP", "SEARCH_BUDGET_EXHAUSTED")
        return ("START_NEW_SESSION", None)

    distinct = {
        str(item.get("focus_key_sha256") or "")
        for item in same_epoch
        if item.get("focus_key_sha256")
    }
    if focus_key not in distinct and len(distinct) >= MAX_DISTINCT_FOCUSES_PER_EPOCH:
        return ("STOP", "SEARCH_BUDGET_EXHAUSTED")
    return ("START_NEW_SESSION", None)


def run_preflight(
    repo_root: Path,
    data_root: Path,
    *,
    owner_focus: str,
    auto_commission: bool,
    commission_fn: Callable[[Path, Path], Mapping[str, Any]] | None = None,
    git_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        proof = prove_fast_lane_commissioned(data_root)
        commissioned_now = False
    except HficPreflightError:
        if not auto_commission or commission_fn is None:
            raise HficPreflightError("FAST_LANE_NOT_COMMISSIONABLE")
        commission_fn(Path(repo_root), Path(data_root))
        proof = prove_fast_lane_commissioned(data_root)
        commissioned_now = True

    try:
        store = ResearchStore(Path(data_root))
        store.rebuild_projection()
        digest = store.diagnostics().committed_inventory_sha256
    except ResearchStoreError as exc:
        raise HficPreflightError(str(exc)) from exc

    epoch = evidence_epoch_sha256(evidence_epoch_material(repo_root, data_root))
    focus = owner_focus if owner_focus.strip() else AUTO_FOCUS
    focus_key = focus_key_sha256(focus)
    search_key = search_key_sha256(epoch, focus, PROMPT_VERSION)
    sessions = _query_hfic_sessions(data_root)
    action, bound_session = decide_preflight_action(
        sessions,
        search_key=search_key,
        evidence_epoch=epoch,
        focus_key=focus_key,
        owner_focus=focus,
    )
    live_git_head = "0" * 40
    git_composite = None
    if isinstance(git_snapshot, Mapping):
        head = git_snapshot.get("head_sha")
        if isinstance(head, str) and len(head) == 40:
            live_git_head = head.lower()
        composite = git_snapshot.get("composite_sha256")
        if isinstance(composite, str) and len(composite) == 64:
            git_composite = composite

    receipt_body = {
        "receipt_id": "HFIC-PREFLIGHT-" + search_key[:16].upper(),
        "action": action,
        "terminal": (
            bound_session
            if action == "STOP" and bound_session == "SEARCH_BUDGET_EXHAUSTED"
            else proof["status"]
            if action != "STOP"
            else bound_session or "FAST_LANE_NOT_COMMISSIONABLE"
        ),
        "owner_focus": focus,
        "prompt_version": PROMPT_VERSION,
        "evidence_epoch_sha256": epoch,
        "focus_key_sha256": focus_key,
        "search_key_sha256": search_key,
        "live_git_head": live_git_head,
        "git_composite_sha256": git_composite,
        "store_inventory_digest": digest,
        "session_id": bound_session if action != "STOP" else None,
        "commissioning": {
            "status": proof["status"],
            "auto_commissioned": commissioned_now,
            "provider_calls_actual": int(proof.get("provider_calls_actual") or 0),
            "git_mutation_count": int(proof.get("git_mutation_count") or 0),
            "run_id": proof.get("run_id"),
        },
        "forge_context_packet": {
            "prompt_version": PROMPT_VERSION,
            "owner_focus": focus,
            "evidence_epoch_sha256": epoch,
            "search_key_sha256": search_key,
            "related_prior_recipe_ids": [
                "QUERY-HFIC-EXACT-RELATED-PRIOR-001",
                "QUERY-HFIC-SESSION-BY-SEARCH-KEY-001",
                "QUERY-HFIC-PENDING-SESSION-001",
            ],
            "truth_roots_used": [
                "repo://catalog/catalog_manifest.yaml",
                "repo://configs/hypothesis_forge_independent_critic_v1.yaml",
            ],
            "commissioning_status": proof["status"],
            "ranked_prior_candidate_ids": [],
        },
        "authority": {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
        },
    }
    if action == "STOP" and bound_session == "SEARCH_BUDGET_EXHAUSTED":
        receipt_body["terminal"] = "SEARCH_BUDGET_EXHAUSTED"
        receipt_body["session_id"] = None
    prior_ids: list[str] = []
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if kind != RecordKind.HYPOTHESIS_VERSION.value:
            continue
        payload = json.loads(record.payload_json)
        hyp_id = payload.get("hypothesis_version_id")
        if isinstance(hyp_id, str) and hyp_id not in prior_ids:
            prior_ids.append(hyp_id)
        if len(prior_ids) >= 5:
            break
    receipt_body["forge_context_packet"]["ranked_prior_candidate_ids"] = prior_ids
    if bound_session and action in {
        "RESUME_CRITIC",
        "RESUME_FINALIZE",
        "RETURN_EXISTING_SESSION",
    }:
        bundle = load_session_bundle(store, bound_session)
        if bundle is not None:
            if bundle.get("critic_input_packet"):
                receipt_body["critic_input_packet"] = bundle["critic_input_packet"]
                receipt_body["critic_input_packet_sha256"] = bundle.get(
                    "critic_input_packet_sha256"
                )
            if action == "RESUME_FINALIZE" and bundle.get("critic_result"):
                receipt_body["critic_result"] = bundle["critic_result"]
            if action == "RETURN_EXISTING_SESSION":
                receipt_body["session_state"] = bundle.get("session_state")
                receipt_body["critic_terminal"] = bundle.get("critic_terminal")
                receipt_body["next"] = bundle.get("next")
    receipt_body["preflight_receipt_sha256"] = canonical_sha256(receipt_body)
    return receipt_body
