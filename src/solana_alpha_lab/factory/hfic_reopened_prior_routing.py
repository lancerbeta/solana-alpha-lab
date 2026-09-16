"""Legacy reopenable-prior bridge: Git parks → search-memory + Prompt A bodies.

One-time/idempotent commissioning. Future HFIC-born HYPOTHESIS_VERSION records
do not use this adapter. No new database, ranker, or memory service.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.factory.hfic_clock import Clock, capture_stage_time
from solana_alpha_lab.factory.hfic_memory_policy import (
    REASON_PRE_CAPABILITY_BASELINE,
    eligible_counts,
    iter_search_memory_hypothesis_payloads,
    preview_memory_policy,
)
from solana_alpha_lab.factory.hfic_preflight import (
    AUTO_FOCUS,
    MAX_PACKET_BYTES,
    MAX_RANKED_PRIORS,
    PROMPT_VERSION,
    decide_preflight_action,
    enumerate_closed_park_terminals,
    enumerate_rdp_datasets,
    evidence_epoch_material,
    select_forge_packet_datasets,
)
from solana_alpha_lab.factory.hfic_prior_memory import (
    compact_forge_prior_entry,
    compact_prior_entry,
    prior_memory_bounds,
)
from solana_alpha_lab.factory.hfic_provenance import is_hfic_record
from solana_alpha_lab.factory.hfic_session import (
    evidence_epoch_sha256,
    focus_key_sha256,
    search_key_sha256,
)
from solana_alpha_lab.factory.research_store import (
    RecordKind,
    ResearchEvent,
    ResearchStore,
)
from solana_alpha_lab.factory.run_passport import canonical_json_bytes, canonical_sha256

SCHEMA = "smial.hfic-reopened-prior-hypothesis-version"
SCHEMA_VERSION = "1.0"
COMMISSIONING_SCHEMA = "smial.hfic-reopened-prior-commissioning"
PRODUCER_CAPABILITY_ID = "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"
DEFECTIVE_CONTROL_SESSION_ID = "HFIC-SESS-8F4A703030408365"
READY_TERMINAL = "CONTROL_RECONSIDERATION_READY_AFTER_COMMISSION"
BODY_INCOMPLETE = "RANKED_PRIOR_BODY_CONTEXT_INCOMPLETE"
BODY_UNRESOLVABLE = "STOP_REOPENED_PRIOR_BODY_UNRESOLVABLE"
IDENTITY_CONFLICT = "STOP_REOPENED_PRIOR_IDENTITY_CONFLICT"
NO_CHANGE = "NO_CHANGE"


class ReopenedPriorRoutingError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def reopened_inventory(
    repo_root: Path,
    data_root: Path | None = None,
) -> list[dict[str, Any]]:
    items = enumerate_closed_park_terminals(Path(repo_root), data_root)
    return [
        dict(item)
        for item in items
        if item.get("visible_as_prior_work") is True
        and item.get("reopen_forbidden") is not True
    ]


def resolve_reopened_prior(
    repo_root: Path,
    item: Mapping[str, Any],
) -> dict[str, Any]:
    root = Path(repo_root)
    source = str(item.get("source_receipt") or "")
    if not source or source.startswith("datasets/"):
        raise ReopenedPriorRoutingError(BODY_UNRESOLVABLE)
    source_path = root / source
    if not source_path.is_file():
        raise ReopenedPriorRoutingError(BODY_UNRESOLVABLE)
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ReopenedPriorRoutingError(BODY_UNRESOLVABLE)
    identity = _identity_from_payload(payload)
    if not identity:
        raise ReopenedPriorRoutingError(BODY_UNRESOLVABLE)
    config_path, group = _select_scientific_config(root, identity, payload)
    definition = _project_definition(identity, payload, config_path, group, item)
    config_rel = config_path.relative_to(root).as_posix()
    source_paths = [source, config_rel]
    hashes = {rel: _file_sha(root / rel) for rel in source_paths}
    yaml_hash = hashes[config_rel]
    freeze_meta = payload.get("task28_freeze")
    if isinstance(freeze_meta, Mapping):
        declared_yaml = freeze_meta.get("freeze_sha256")
        if isinstance(declared_yaml, str) and declared_yaml != yaml_hash:
            raise ReopenedPriorRoutingError(BODY_UNRESOLVABLE)
    declared_def = None
    if isinstance(group, Mapping) and isinstance(group.get("definition_sha256"), str):
        declared_def = str(group["definition_sha256"])
    nested = payload.get("return_prerequisites")
    if isinstance(nested, Mapping) and isinstance(nested.get("definition_sha256"), str):
        park_def = str(nested["definition_sha256"])
        if declared_def and park_def != declared_def:
            raise ReopenedPriorRoutingError(BODY_UNRESOLVABLE)
        declared_def = declared_def or park_def
    frozen_hash = declared_def or yaml_hash
    if not _legacy_body_present(definition.get("legacy_definition")):
        raise ReopenedPriorRoutingError(BODY_UNRESOLVABLE)
    claim = definition.get("claim")
    binding = {
        "hypothesis_identity": identity,
        "source_paths": source_paths,
        "source_content_sha256": hashes,
        "frozen_definition_sha256": frozen_hash,
        "park_status": str(item.get("terminal") or ""),
        "suppression_class": str(item.get("suppression_class") or ""),
        "reopen_forbidden": False,
        "commissioning_schema": COMMISSIONING_SCHEMA,
        "commissioning_schema_version": SCHEMA_VERSION,
    }
    hv = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "hypothesis_version_id": identity,
        "claim": claim if isinstance(claim, str) and claim.strip() else None,
        "mechanism": definition.get("mechanism"),
        "actor_counterparty": definition.get("actor_counterparty"),
        "population": definition.get("population"),
        "decision_timestamp": definition.get("decision_timestamp"),
        "primary_x_family": definition.get("primary_x_family"),
        "primary_y": definition.get("primary_y"),
        "horizon_notional": definition.get("horizon_notional"),
        "negative_control": definition.get("negative_control"),
        "cheapest_falsifier": definition.get("cheapest_falsifier"),
        "definition_sha256": frozen_hash,
        "legacy_definition": definition.get("legacy_definition") or {},
        "provenance": binding,
    }
    digest = canonical_sha256(
        {"identity": identity, "hashes": hashes, "frozen": frozen_hash}
    )
    return {
        "hypothesis_version_id": identity,
        "payload": hv,
        "provenance": binding,
        "record_id": "HV-REOPENED-" + digest[:16].upper(),
        "binding_digest": digest,
    }


def resolve_all_reopened_priors(
    repo_root: Path,
    data_root: Path | None = None,
) -> list[dict[str, Any]]:
    resolved = [
        resolve_reopened_prior(repo_root, item)
        for item in reopened_inventory(repo_root, data_root)
    ]
    resolved.sort(key=lambda item: str(item["hypothesis_version_id"]))
    return resolved


def overlay_search_payloads(
    store: Any,
    extra_payloads: Sequence[Mapping[str, Any]],
    extra_quarantine: Sequence[str],
) -> list[dict[str, Any]]:
    extra_q = {str(item) for item in extra_quarantine if str(item).strip()}
    by_id: dict[str, dict[str, Any]] = {}
    for payload in iter_search_memory_hypothesis_payloads(store):
        session_id = payload.get("session_id")
        if isinstance(session_id, str) and session_id in extra_q:
            continue
        hyp_id = str(payload.get("hypothesis_version_id") or "")
        if hyp_id:
            by_id[hyp_id] = dict(payload)
    for payload in extra_payloads:
        hyp_id = str(payload.get("hypothesis_version_id") or "")
        if hyp_id:
            by_id[hyp_id] = dict(payload)
    return [by_id[key] for key in sorted(by_id)]


def ranked_prior_entries_for_ids(
    ranked_ids: Sequence[str],
    payloads: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {
        str(item.get("hypothesis_version_id") or ""): item
        for item in payloads
        if isinstance(item, Mapping)
    }
    entries: list[dict[str, Any]] = []
    for hyp_id in ranked_ids:
        payload = by_id.get(str(hyp_id))
        if payload is None or not _decision_useful_payload(payload):
            raise ReopenedPriorRoutingError(BODY_INCOMPLETE)
        # Gate usefulness on the canonical source body only. Forge projection
        # deliberately omits Critic-only fields; re-checking the lean entry with
        # the Critic usefulness predicate would mislabel capacity/projection
        # outcomes as RANKED_PRIOR_BODY_CONTEXT_INCOMPLETE.
        entry = compact_forge_prior_entry(str(hyp_id), payload)
        if str(entry.get("hypothesis_version_id") or "") != str(hyp_id):
            raise ReopenedPriorRoutingError(BODY_INCOMPLETE)
        entries.append(entry)
    if {item["hypothesis_version_id"] for item in entries} != set(ranked_ids):
        raise ReopenedPriorRoutingError(BODY_INCOMPLETE)
    return entries


def planned_prior_work_digest(
    store: Any,
    extra_records: Sequence[tuple[str, str]],
) -> str:
    parts: list[str] = []
    if store is not None:
        for record in store.iter_committed_records():
            try:
                payload = json.loads(record.payload_json)
            except (ValueError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict) or is_hfic_record(record, payload):
                continue
            parts.append(f"{record.record_id}:{record.payload_sha256}")
    for record_id, payload_sha in extra_records:
        parts.append(f"{record_id}:{payload_sha}")
    return hashlib.sha256(
        "\n".join(sorted(parts)).encode("utf-8")
        if parts
        else b"HFIC-EPOCH-CATALOG-BINDING-V1"
    ).hexdigest()


def commission_reopened_priors(
    store: ResearchStore,
    repo_root: Path,
    *,
    git_sha: str,
    clock: Clock | None = None,
    confirm_append_only: bool = False,
) -> dict[str, Any]:
    if not confirm_append_only:
        raise ReopenedPriorRoutingError("CONFIRM_APPEND_ONLY_REQUIRED")
    resolved = resolve_all_reopened_priors(repo_root, Path(store._root))
    existing = _latest_hv_by_id(store)
    planned: list[dict[str, Any]] = []
    skipped = 0
    for item in resolved:
        hyp_id = str(item["hypothesis_version_id"])
        current = existing.get(hyp_id)
        if current is not None:
            if _equivalent_binding(current, item["payload"]):
                skipped += 1
                continue
            raise ReopenedPriorRoutingError(IDENTITY_CONFLICT)
        planned.append(item)
    if not planned:
        return {
            "status": NO_CHANGE,
            "appended": 0,
            "skipped_equivalent": skipped,
            "hypothesis_version_ids": [item["hypothesis_version_id"] for item in resolved],
        }
    now = capture_stage_time(clock)
    digest = canonical_sha256(
        [item["binding_digest"] for item in planned]
    )
    txn = f"RESEARCH-TXN-REOPENED-{digest[:12].upper()}"
    events = [
        _event(item, transaction_id=txn, now=now, git_sha=git_sha) for item in planned
    ]
    store.append(events, transaction_id=txn)
    return {
        "status": "APPENDED",
        "appended": len(events),
        "skipped_equivalent": skipped,
        "transaction_id": txn,
        "record_ids": [item["record_id"] for item in planned],
        "hypothesis_version_ids": [item["hypothesis_version_id"] for item in planned],
    }


def preview_control_reconsideration(
    store: ResearchStore,
    repo_root: Path,
    *,
    data_root: Path,
    defective_session_id: str = DEFECTIVE_CONTROL_SESSION_ID,
    owner_focus: str = AUTO_FOCUS,
) -> dict[str, Any]:
    from solana_alpha_lab.factory.early_market_panel_importer import (
        MIN_USABLE_YIELD_ELIGIBLE,
    )
    from solana_alpha_lab.factory.hfic_control_integrity import (
        CURRENT_REPRESENTATION_CONTROL_V1,
        control_packet_has_raw_sequences,
        resolve_control_corpus_yield,
    )
    from solana_alpha_lab.factory.live_cohort_discovery_release import CORPUS_DATASET_ID

    from solana_alpha_lab.factory.hfic_preflight import _query_hfic_sessions

    inventory = reopened_inventory(repo_root, data_root)
    resolved = [resolve_reopened_prior(repo_root, item) for item in inventory]
    identities = {str(item["hypothesis_version_id"]) for item in resolved}
    current_payloads = list(iter_search_memory_hypothesis_payloads(store))
    current_ids = {
        str(item.get("hypothesis_version_id") or "") for item in current_payloads
    }
    extra = [item["payload"] for item in resolved]
    existing = _latest_hv_by_id(store)
    extra_records = [
        _stored_payload_ref(item)
        for item in resolved
        if not (
            str(item["hypothesis_version_id"]) in existing
            and _equivalent_binding(
                existing[str(item["hypothesis_version_id"])],
                item["payload"],
            )
        )
    ]
    planned_payloads = overlay_search_payloads(
        store, extra, [defective_session_id]
    )
    policy = preview_memory_policy(
        store,
        repo_root=repo_root,
        quarantine_session_ids=[defective_session_id],
        reason_code=REASON_PRE_CAPABILITY_BASELINE,
    )
    current_epoch_material = evidence_epoch_material(repo_root, data_root)
    planned_epoch_material = dict(current_epoch_material)
    planned_epoch_material["prior_work_digest"] = planned_prior_work_digest(
        store, extra_records
    )
    old_epoch = evidence_epoch_sha256(current_epoch_material)
    new_epoch = evidence_epoch_sha256(planned_epoch_material)
    old_eligibility = str(policy["memory_eligibility_sha256_before"])
    new_eligibility = str(policy["memory_eligibility_sha256_after"])
    datasets, _warnings = enumerate_rdp_datasets(Path(data_root))
    selected, _trunc = (
        select_forge_packet_datasets(
            datasets, evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1
        )
        if datasets
        else ([], {})
    )
    from solana_alpha_lab.factory.hfic_preflight import build_forge_context_packet

    planned_search_key = search_key_sha256(
        new_epoch,
        owner_focus,
        PROMPT_VERSION,
        new_eligibility,
        CURRENT_REPRESENTATION_CONTROL_V1,
    )
    packet, _digest = build_forge_context_packet(
        Path(repo_root),
        Path(data_root),
        owner_focus=owner_focus,
        evidence_epoch=new_epoch,
        search_key=planned_search_key,
        commissioning_status="FAST_LANE_COMMISSIONED",
        research_memory_as_of="2026-09-15T00:00:00Z",
        store=store,
        persist=False,
        search_payloads=planned_payloads,
        evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1,
    )
    ranked = list(packet.get("ranked_prior_candidate_ids") or [])
    entries = list(packet.get("ranked_prior_entries") or [])
    usable_hints = [
        str(item.get("feature_id") or "")
        for item in (packet.get("feature_hints") or [])
        if isinstance(item, Mapping) and item.get("usable")
    ]
    usable_hints = [item for item in usable_hints if item]
    _kept, details = rank_prior_candidate_details(
        planned_payloads,
        owner_focus=owner_focus,
        feature_hints=usable_hints,
        limit=MAX_RANKED_PRIORS,
    )
    packet_bytes = len(canonical_json_bytes(packet))
    if {item["hypothesis_version_id"] for item in entries} != set(ranked):
        raise ReopenedPriorRoutingError(BODY_INCOMPLETE)
    records_bound, bytes_bound = prior_memory_bounds(repo_root)
    planned_eligible = len(planned_payloads)
    planned_capsules = [
        compact_prior_entry(str(item.get("hypothesis_version_id") or ""), item)
        for item in planned_payloads
    ]
    prior_bytes = len(canonical_json_bytes({"capsules": planned_capsules}))
    gate, yield_eligible = resolve_control_corpus_yield(
        selected or datasets,
        corpus_dataset_id=CORPUS_DATASET_ID,
        min_usable_yield_eligible=MIN_USABLE_YIELD_ELIGIBLE,
    )
    sessions = _query_hfic_sessions(Path(data_root))
    session = next(
        (item for item in sessions if item.get("session_id") == defective_session_id),
        None,
    )
    action, _bound = decide_preflight_action(
        sessions,
        search_key=planned_search_key,
        evidence_epoch=new_epoch,
        focus_key=focus_key_sha256(owner_focus),
        owner_focus=owner_focus,
        memory_eligibility_sha256=new_eligibility,
        evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1,
    )
    live_present = any(
        str(item.get("dataset_id") or "") == CORPUS_DATASET_ID
        or str(item.get("dataset_manifest_id") or "").startswith("dataset-")
        for item in (selected or datasets)
    )
    trajectory_leak = control_packet_has_raw_sequences(packet)
    freeze_smoke = freeze_reopened_prior_compat_smoke(repo_root)
    h11_id = "HYP-RC002-H11-LIFECYCLE-CLOCK-V1"
    h13_id = "RC001-H13-COMPOSITE-VETO"
    session_epoch = (
        str(session.get("evidence_epoch_sha256") or "")
        if session is not None
        else old_epoch
    )
    session_eligibility = (
        str(session.get("memory_eligibility_sha256") or "")
        if session is not None
        else old_eligibility
    )
    session_search = (
        str(session.get("search_key_sha256") or "") if session is not None else ""
    )
    identity_changed = (
        session_epoch != new_epoch
        or session_eligibility != new_eligibility
        or session_search != planned_search_key
    )
    dropped_priors = int((packet.get("truncation_receipt") or {}).get("dropped_priors") or 0)
    blockers: list[str] = []
    if session is None or str(session.get("session_state") or "") != "SYNTHESIS_COMPLETE":
        blockers.append("DEFECT_SESSION_NOT_SYNTHESIS_COMPLETE")
    if h11_id not in identities or h13_id not in identities:
        blockers.append("REOPENABLE_INVENTORY_MISSING_H11_H13")
    if h11_id not in set(ranked) or h13_id not in set(ranked):
        blockers.append("H11_H13_NOT_IN_PROMPT_A_SET")
    if packet_bytes > MAX_PACKET_BYTES:
        blockers.append("FORGE_CONTEXT_PACKET_OVERSIZE")
    if planned_eligible > records_bound or prior_bytes > bytes_bound:
        blockers.append("PRIOR_MEMORY_CAPACITY")
    if action != "START_NEW_SESSION":
        blockers.append("PREFLIGHT_ACTION_NOT_START_NEW_SESSION")
    if gate != "OK" or yield_eligible < MIN_USABLE_YIELD_ELIGIBLE:
        blockers.append("CONTROL_CORPUS_YIELD")
    if not identity_changed:
        blockers.append("DEFECTIVE_CONTROL_IDENTITY_UNCHANGED")
    if trajectory_leak:
        blockers.append("CONTROL_RAW_SEQUENCE_FORBIDDEN")
    if freeze_smoke.get("status") != "PASS":
        blockers.append("FREEZE_COMPAT_SMOKE")
    if dropped_priors:
        blockers.append("SILENT_REOPENED_PRIOR_TRUNCATION")
    ready = not blockers
    counts = eligible_counts(store)
    return {
        "CURRENT_DEFECT_SESSION": {
            "session_id": defective_session_id,
            "found": session is not None,
            "session_state": None if session is None else session.get("session_state"),
        },
        "CURRENT_REOPENABLE_INVENTORY": [
            {
                "terminal": item.get("terminal"),
                "hypothesis_version_id": resolve_reopened_prior(repo_root, item)[
                    "hypothesis_version_id"
                ],
                "reopen_forbidden": item.get("reopen_forbidden"),
                "visible_as_prior_work": item.get("visible_as_prior_work"),
                "source_receipt": item.get("source_receipt"),
            }
            for item in inventory
        ],
        "CANONICAL_BODY_RESOLUTION": "PASS",
        "CURRENT_SEARCH_MEMORY": {
            "h11": h11_id in current_ids,
            "h13": h13_id in current_ids,
        },
        "PLANNED_REHYDRATION": [
            {
                "record_id": item["record_id"],
                "hypothesis_version_id": item["hypothesis_version_id"],
                "source_hashes": item["provenance"]["source_content_sha256"],
            }
            for item in resolved
        ],
        "PLANNED_QUARANTINE": {
            "session_id": defective_session_id,
            "reason": REASON_PRE_CAPABILITY_BASELINE,
            "existing_memory_policy_reused": True,
        },
        "POST_PLAN_ELIGIBLE_MEMORY": planned_eligible,
        "CURRENT_ELIGIBLE_COUNT": counts["total_eligible_prior_memory_count"],
        "POST_PLAN_PRIOR_MEMORY_CAPACITY": (
            "PASS"
            if planned_eligible <= records_bound and prior_bytes <= bytes_bound
            else "BLOCKED"
        ),
        "POST_PLAN_RANKING": details,
        "POST_PLAN_PRIOR_BODIES": [
            item["hypothesis_version_id"] for item in entries
        ],
        "H11_IN_PROMPT_A_SET": h11_id in set(ranked),
        "H13_IN_PROMPT_A_SET": h13_id in set(ranked),
        "POST_PLAN_FORGE_CONTEXT_BYTES": packet_bytes,
        "MAX_PACKET_BYTES": MAX_PACKET_BYTES,
        "PRIOR_MEMORY_COUNT_AFTER": planned_eligible,
        "PRIOR_MEMORY_BYTES_AFTER": prior_bytes,
        "OLD_EVIDENCE_EPOCH": session_epoch,
        "PLANNED_NEW_EVIDENCE_EPOCH": new_epoch,
        "OLD_MEMORY_ELIGIBILITY": session_eligibility or old_eligibility,
        "PLANNED_NEW_MEMORY_ELIGIBILITY": new_eligibility,
        "PLANNED_PREFLIGHT_ACTION": action,
        "POST_PLAN_CONTROL_CORPUS": {
            "gate": gate,
            "live_present": live_present,
            "yield_eligible": yield_eligible,
            "min_usable_yield_eligible": MIN_USABLE_YIELD_ELIGIBLE,
        },
        "CONTROL_TRAJECTORY_BLIND_FENCE": not trajectory_leak,
        "NO_RAW_TRAJECTORY_LEAK": not trajectory_leak,
        "POST_PLAN_FREEZE_COMPAT_SMOKE": freeze_smoke.get("status"),
        "C1_CORPUS_IDENTITY": {
            "corpus_dataset_id": CORPUS_DATASET_ID,
            "dataset_ids": [
                str(item.get("dataset_id") or "") for item in (selected or datasets)
            ],
            "dataset_manifest_ids": [
                str(item.get("dataset_manifest_id") or "")
                for item in (selected or datasets)
            ],
            "dataset_fingerprints": [
                str(item.get("dataset_fingerprint") or "")
                for item in (selected or datasets)
            ],
        },
        "POST_PLAN_TRUNCATION": packet.get("truncation_receipt") or {},
        "terminal": READY_TERMINAL if ready else "CONTROL_RECONSIDERATION_NOT_READY",
        "BLOCKER_NEXT": None if ready else blockers[0],
        "blockers": blockers,
        "authority": {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
            "rdp_mutation": 0,
        },
    }


def freeze_reopened_prior_compat_smoke(repo_root: Path) -> dict[str, Any]:
    from solana_alpha_lab.factory.hfic_session import freeze_draft

    root = Path(repo_root)
    draft_path = root / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json"
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    resolved = resolve_all_reopened_priors(root)
    prior = next(
        (
            item
            for item in resolved
            if item["hypothesis_version_id"] == "RC001-H13-COMPOSITE-VETO"
        ),
        None,
    )
    if prior is None:
        return {"status": "FAIL", "reason": BODY_UNRESOLVABLE}
    card = dict(draft["candidates"][2])
    card["prior_work_refs"] = [str(prior["hypothesis_version_id"])]
    legacy = prior["payload"].get("legacy_definition")
    if isinstance(legacy, Mapping):
        hist = legacy.get("historical_expected_admissibility")
        if isinstance(hist, Mapping) and hist.get("state"):
            card["unresolved_requirements"] = [
                f"historical_{hist.get('state')} remains typed; current grounding decides usability"
            ]
    if not card.get("unresolved_requirements"):
        card["unresolved_requirements"] = [
            "current decision-time composite-veto inputs remain unavailable"
        ]
    draft["candidates"][2] = card
    try:
        frozen = freeze_draft(
            draft,
            preflight_receipt={
                "receipt_id": "HFIC-PREFLIGHT-FIXTURE-001",
                "forge_context_packet_sha256": "ab" * 32,
                "forge_context_packet": {
                    "capability_ids": ["CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"],
                    "vision_integrity": {"status": "PASS"},
                },
            },
            repo_root=root,
        )
    except Exception as exc:
        return {"status": "FAIL", "reason": str(exc)}
    grounded_list = frozen.get("grounded_candidates") or []
    selected = next(
        (
            item
            for item in grounded_list
            if isinstance(item, Mapping) and item.get("label") == card.get("label")
        ),
        None,
    )
    if not isinstance(selected, Mapping):
        return {"status": "FAIL", "reason": "GROUNDED_CANDIDATE_MISSING"}
    grounding = selected.get("grounding") if isinstance(selected.get("grounding"), Mapping) else {}
    bindings = grounding.get("feature_bindings") or []
    fabricated = [
        str(item.get("feature_id") or "")
        for item in bindings
        if isinstance(item, Mapping)
        and str(item.get("feature_id") or "").startswith("FEAT-")
        and str(item.get("feature_id") or "")
        not in set(card.get("required_feature_ids") or [])
    ]
    if fabricated:
        return {"status": "FAIL", "reason": "FABRICATED_FEATURE_ID"}
    return {
        "status": "PASS",
        "grounding_terminal": grounding.get("terminal"),
        "unresolved_requirements": list(grounding.get("unresolved_requirements") or []),
        "feature_ids": [
            str(item.get("feature_id") or "")
            for item in bindings
            if isinstance(item, Mapping)
        ],
        "critic_packet_version": (frozen.get("critic_input_packet") or {}).get(
            "packet_version"
        ),
    }


def _stored_payload_ref(item: Mapping[str, Any]) -> tuple[str, str]:
    payload_json = _payload_json(item["payload"])
    return str(item["record_id"]), hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def _payload_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def rank_prior_candidate_details(
    payloads: Sequence[Mapping[str, Any]],
    *,
    owner_focus: str,
    feature_hints: Sequence[str],
    limit: int = MAX_RANKED_PRIORS,
) -> tuple[list[str], list[dict[str, Any]]]:
    from solana_alpha_lab.factory.hfic_preflight import _term_set

    focus_terms = _term_set(owner_focus)
    feature_terms: set[str] = set()
    for hint in feature_hints:
        feature_terms.update(_term_set(str(hint)))
    if feature_hints:
        feature_terms.update(
            {"taker", "volume", "mix", "valuation", "liquidity", "divergence"}
        )
    scored: list[tuple[int, str, dict[str, Any]]] = []
    seen: set[str] = set()
    for payload in payloads:
        hyp_id = payload.get("hypothesis_version_id")
        if not isinstance(hyp_id, str) or hyp_id in seen:
            continue
        seen.add(hyp_id)
        blob = " ".join(
            str(payload.get(key) or "")
            for key in (
                "hypothesis_version_id",
                "claim",
                "statement",
                "mechanism",
                "primary_x_family",
            )
        )
        tokens = _term_set(blob)
        feature_hit = sorted(tokens & feature_terms)
        focus_hit = sorted(tokens & focus_terms)
        score = 3 * len(feature_hit) + 2 * len(focus_hit)
        scored.append(
            (
                score,
                hyp_id,
                {
                    "hypothesis_version_id": hyp_id,
                    "score": score,
                    "feature_term_hits": feature_hit,
                    "focus_term_hits": focus_hit,
                },
            )
        )
    scored.sort(key=lambda item: (-item[0], item[1]))
    kept = [item[1] for item in scored[:limit]]
    details = [item[2] for item in scored]
    return kept, details


def _identity_from_payload(payload: Mapping[str, Any]) -> str | None:
    for key in ("hypothesis_id", "group_id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    nested = payload.get("return_prerequisites")
    if isinstance(nested, Mapping):
        group = nested.get("group_id")
        if isinstance(group, str) and group.strip():
            return group.strip()
    return None


def _select_scientific_config(
    root: Path,
    identity: str,
    payload: Mapping[str, Any],
) -> tuple[Path, Mapping[str, Any] | None]:
    explicit: list[Path] = []
    for rel in _iter_config_paths(payload):
        path = root / rel
        if path.is_file():
            explicit.append(path)
    consumer = payload.get("consumer")
    consumer_text = consumer.strip() if isinstance(consumer, str) else None
    matches: list[tuple[Path, Mapping[str, Any] | None]] = []
    search_paths = explicit or sorted((root / "configs").glob("*.yaml"))
    for path in search_paths:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, Mapping):
            continue
        group = _matching_group(loaded, identity)
        if group is not None:
            matches.append((path, group))
            continue
        screen = loaded.get("screen_protocol")
        if (
            isinstance(screen, Mapping)
            and isinstance(screen.get("primary_question"), str)
            and screen["primary_question"].strip()
            and consumer_text
            and loaded.get("consumer") == consumer_text
        ):
            matches.append((path, None))
    unique: dict[str, tuple[Path, Mapping[str, Any] | None]] = {}
    for path, group in matches:
        unique[path.as_posix()] = (path, group)
    if len(unique) != 1:
        raise ReopenedPriorRoutingError(BODY_UNRESOLVABLE)
    path, group = next(iter(unique.values()))
    return path, group


def _matching_group(
    loaded: Mapping[str, Any], identity: str
) -> Mapping[str, Any] | None:
    groups = loaded.get("hypothesis_groups")
    if not isinstance(groups, list):
        return None
    found = [
        item
        for item in groups
        if isinstance(item, Mapping) and item.get("group_id") == identity
    ]
    if len(found) != 1:
        return None
    return found[0]


def _project_definition(
    identity: str,
    park_payload: Mapping[str, Any],
    config_path: Path,
    group: Mapping[str, Any] | None,
    ledger_item: Mapping[str, Any],
) -> dict[str, Any]:
    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise ReopenedPriorRoutingError(BODY_UNRESOLVABLE)
    screen = loaded.get("screen_protocol")
    if not isinstance(screen, Mapping):
        screen = {}
    legacy: dict[str, Any] = {
        "park_terminal": ledger_item.get("terminal"),
        "park_hypothesis_verdict": park_payload.get("hypothesis_verdict"),
        "science_disposition": park_payload.get("science_disposition"),
        "priority_disposition": park_payload.get("priority_disposition"),
    }
    if group is not None:
        inputs = group.get("definition_inputs")
        requirements = group.get("requirements")
        expected = group.get("expected_admissibility")
        legacy.update(
            {
                "frozen_definition_id": group.get("frozen_definition_id"),
                "feature_id": group.get("feature_id"),
                "group_id": group.get("group_id") or identity,
                "falsifier": group.get("falsifier"),
                "definition_inputs": inputs,
                "historical_requirements": requirements,
                "historical_expected_admissibility": expected,
                "target_metrics": group.get("target_metrics"),
            }
        )
        return {
            "claim": None,
            "mechanism": None,
            "actor_counterparty": None,
            "population": None,
            "decision_timestamp": None,
            "primary_x_family": None,
            "primary_y": None,
            "horizon_notional": None,
            "negative_control": None,
            "cheapest_falsifier": None,
            "legacy_definition": _compact_legacy(legacy),
        }
    question = str(screen.get("primary_question") or "").strip() or None
    features = screen.get("primary_features")
    if isinstance(features, list):
        legacy["primary_features"] = features
    legacy.update(
        {
            "primary_question": question,
            "family": screen.get("family"),
            "universe": screen.get("universe"),
            "data_semantics": screen.get("data_semantics"),
            "live_PIT_claim": screen.get("live_PIT_claim"),
            "baseline": screen.get("baseline"),
            "outcome_horizon_seconds": screen.get("outcome_horizon_seconds"),
        }
    )
    return {
        "claim": None,
        "mechanism": None,
        "actor_counterparty": None,
        "population": None,
        "decision_timestamp": None,
        "primary_x_family": None,
        "primary_y": None,
        "horizon_notional": None,
        "negative_control": None,
        "cheapest_falsifier": None,
        "legacy_definition": _compact_legacy(legacy),
    }


def _iter_config_paths(payload: Mapping[str, Any]) -> list[str]:
    found: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                if key in {"path", "freeze_path", "config_path", "spec_path"}:
                    if (
                        isinstance(value, str)
                        and value.startswith("configs/")
                        and value.endswith((".yaml", ".yml"))
                    ):
                        found.append(value.replace("\\", "/"))
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return list(dict.fromkeys(found))


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _latest_hv_by_id(store: ResearchStore) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if str(kind) != RecordKind.HYPOTHESIS_VERSION.value:
            continue
        try:
            payload = json.loads(record.payload_json)
        except (ValueError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        hyp_id = str(
            payload.get("hypothesis_version_id")
            or record.hypothesis_version_id
            or record.entity_id
            or ""
        )
        if hyp_id:
            latest[hyp_id] = payload
    return latest


def _equivalent_binding(existing: Mapping[str, Any], incoming: Mapping[str, Any]) -> bool:
    return _body_fingerprint(existing) == _body_fingerprint(incoming)


def _body_fingerprint(payload: Mapping[str, Any]) -> str:
    provenance = (
        payload.get("provenance") if isinstance(payload.get("provenance"), Mapping) else {}
    )
    return canonical_sha256(
        {
            "source_content_sha256": provenance.get("source_content_sha256"),
            "frozen_definition_sha256": provenance.get("frozen_definition_sha256"),
            "scientific": {
                field: payload.get(field)
                for field in (
                    "claim",
                    "mechanism",
                    "actor_counterparty",
                    "population",
                    "decision_timestamp",
                    "primary_x_family",
                    "primary_y",
                    "horizon_notional",
                    "negative_control",
                    "cheapest_falsifier",
                    "definition_sha256",
                )
            },
            "legacy_definition": payload.get("legacy_definition") or {},
        }
    )


def _compact_legacy(legacy: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in legacy.items()
        if value not in (None, "", [], {})
    }


def _legacy_body_present(legacy: object) -> bool:
    if not isinstance(legacy, Mapping):
        return False
    markers = (
        "primary_question",
        "falsifier",
        "frozen_definition_id",
        "park_terminal",
    )
    return any(
        str(legacy.get(key) or "").strip()
        for key in markers
    )


def _decision_useful_payload(payload: Mapping[str, Any]) -> bool:
    for field in (
        "claim",
        "mechanism",
        "actor_counterparty",
        "population",
        "decision_timestamp",
        "primary_x_family",
        "primary_y",
        "horizon_notional",
        "negative_control",
        "cheapest_falsifier",
    ):
        if str(payload.get(field) or "").strip():
            return True
    return _legacy_body_present(payload.get("legacy_definition"))


def _event(
    item: Mapping[str, Any],
    *,
    transaction_id: str,
    now: datetime,
    git_sha: str,
) -> ResearchEvent:
    payload_json = _payload_json(item["payload"])
    return ResearchEvent(
        record_id=str(item["record_id"]),
        record_kind=RecordKind.HYPOTHESIS_VERSION,
        entity_id=str(item["hypothesis_version_id"]),
        hypothesis_version_id=str(item["hypothesis_version_id"]),
        run_id=None,
        transaction_id=transaction_id,
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version=SCHEMA_VERSION,
        producer_capability_id=PRODUCER_CAPABILITY_ID,
        producer_git_sha=git_sha,
        created_at=now,
    )
