"""Canonical Forge input/visibility receipt.

Scientific observability of what /hypothesis-forge may currently see.
Does not run preflight, persist packets, start sessions, or synthesize.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.cohort_import_readback import build_cohort_import_readback
from solana_alpha_lab.factory.data_root import instance_fingerprint
from solana_alpha_lab.factory.live_cohort_discovery_release import (
    CORPUS_DATASET_ID,
    LiveCohortReleaseError,
    load_live_corpus_lineage,
)
from solana_alpha_lab.factory.run_passport import canonical_sha256

SCHEMA = "smial.forge-input-receipt"
SCHEMA_VERSION = "1.0"
OWNER_CLASS_READY = "FORGE_INPUT_READY"
OWNER_CLASS_INPUT_NOT_READY = "INPUT_NOT_READY"
OWNER_CLASS_OBSERVABILITY_BLOCKED = "OBSERVABILITY_BLOCKED"
CURRENT_CORPUS_MISSING = "CURRENT_CORPUS_MISSING"
CURRENT_CORPUS_EXCLUDED_FROM_PACKET = "CURRENT_CORPUS_EXCLUDED_FROM_CONTROL_PACKET"
FORGE_VISION_INTEGRITY_BLOCKED = "FORGE_VISION_INTEGRITY_BLOCKED"
IMPORTED_COHORT_MISSING = "IMPORTED_COHORT_MISSING"
DUPLICATE_LINEAGE = "DUPLICATE_LINEAGE"
CONTROL_CORPUS_MANIFEST_MISMATCH = "CONTROL_CORPUS_MANIFEST_MISMATCH"
HISTORICAL_CALIBRATION_INVALID = "SELECTION_GATE_RECEIPT_UNUSABLE"
PROBE_CONTRACT_RELATIVE = (
    "docs/contracts/normalized_trajectory_representation_probe_v1.md"
)
BASE_REPRESENTATION = "BASE"
TRAJECTORY_REPRESENTATION = "NORMALIZED_TRAJECTORY_V1"
READY_STATUS = "READY"
TRAJECTORY_STATUS = "RUNTIME_READY_NOT_EXECUTED"


def format_forge_input_owner_block(receipt: Mapping[str, Any]) -> str:
    """Owner-facing FORGE INPUT block. Not raw JSON."""

    active = receipt.get("active_evidence_set") or {}
    ids = [str(item) for item in (active.get("visible_cohort_ids") or [])]
    visible = ", ".join(ids) if ids else "(none)"
    mid = str(active.get("current_dataset_manifest_id") or "(none)")
    version = active.get("corpus_version")
    historical = list(receipt.get("historical_calibration") or [])
    if not historical:
        hist_text = "none"
    else:
        parts = []
        for item in historical:
            router = str(item.get("router_decision") or "")
            integrity = str(item.get("integrity") or "")
            cohort = item.get("cohort_scope") or "C1"
            scope = item.get("eligibility_scope") or ""
            if router and integrity == "PASS":
                parts.append(
                    f"{cohort} {scope} integrity={integrity} caveat_router={router}"
                )
            elif router:
                parts.append(
                    f"{cohort} {scope} integrity={integrity} router={router}"
                )
            else:
                parts.append(f"{cohort} {scope} integrity={integrity}".strip())
        hist_text = "; ".join(parts)
    vis = receipt.get("visibility") or {}
    vis_bits = []
    for key in (
        "corpus_binding",
        "lineage",
        "pit_semantics",
        "missingness_visible",
        "prior_memory",
        "feature_grounding",
        "packet_vision",
    ):
        vis_bits.append(f"{key}={vis.get(key)}")
    vis_bits.append(f"material_truncation={bool(vis.get('material_truncation'))}")
    reps = []
    for item in receipt.get("representations") or []:
        if isinstance(item, Mapping):
            reps.append(
                f"{item.get('representation_id')} {item.get('status')}"
            )
    lines = [
        "FORGE INPUT",
        f"visible_cohorts: {visible}",
        f"active_evidence_set: manifest={mid} corpus_version={version}",
        (
            "market_evidence_epoch: "
            + (
                str(receipt.get("market_evidence_epoch_sha256"))
                if isinstance(receipt.get("market_evidence_epoch_sha256"), str)
                and len(str(receipt.get("market_evidence_epoch_sha256"))) == 64
                else "(unset)"
            )
            + "  # admission/budget key"
        ),
        (
            "capability_epoch: "
            + (
                str(receipt.get("capability_epoch_sha256"))
                if isinstance(receipt.get("capability_epoch_sha256"), str)
                and len(str(receipt.get("capability_epoch_sha256"))) == 64
                else "(unset)"
            )
            + "  # protocol; does not free market budget"
        ),
        f"historical_calibration: {hist_text}",
        f"visibility: {', '.join(vis_bits)}",
        f"representations: {'; '.join(reps) if reps else '(none)'}",
        f"forge_runnable: {bool(receipt.get('forge_runnable'))}",
        (
            "forge_input_readiness: READY — market input admitted; "
            "STOP_BEFORE_SYNTHESIS is the phase boundary"
            if bool(receipt.get("forge_runnable"))
            else "forge_input_readiness: NOT_READY — resolve the typed blocker"
        ),
        f"owner_class: {receipt.get('owner_class')}",
        f"forge_input_next: {forge_input_owner_next(receipt)}",
        "evidence_surface_mode: "
        + str(receipt.get("evidence_surface_mode") or "ordinary"),
        "writes: research_store={store} forge_context={context} session={session}".format(
            store=int((receipt.get("writes") or {}).get("research_store") or 0),
            context=int((receipt.get("writes") or {}).get("forge_context") or 0),
            session=int((receipt.get("writes") or {}).get("session") or 0),
        ),
    ]
    codes = [str(item) for item in (receipt.get("blocking_reason_codes") or [])]
    if codes:
        lines.append("blocking_reason_codes: " + ", ".join(codes))
    return "\n".join(lines)


def forge_input_owner_next(receipt: Mapping[str, Any]) -> str:
    """Typed owner next for the FORGE INPUT surface. Not slash authority."""

    if bool(receipt.get("forge_runnable")):
        return "STOP_BEFORE_SYNTHESIS"
    codes = [str(item) for item in (receipt.get("blocking_reason_codes") or [])]
    owner = str(receipt.get("owner_class") or "")
    if owner == OWNER_CLASS_OBSERVABILITY_BLOCKED:
        return "STOP_OBSERVABILITY"
    if CURRENT_CORPUS_MISSING in codes or owner == OWNER_CLASS_INPUT_NOT_READY:
        return "WAIT_FOR_IMPORT_OR_STOP"
    return "WAIT_FOR_IMPORT_OR_STOP"


def _pass_fail(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _evidence_set_sha256(
    *,
    current_dataset_manifest_id: str | None,
    visible_cohort_ids: Sequence[str],
    corpus_version: object,
) -> str:
    payload = {
        "current_dataset_manifest_id": current_dataset_manifest_id,
        "visible_cohort_ids": list(visible_cohort_ids),
        "corpus_version": corpus_version,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_readback(data_root: Path) -> dict[str, Any] | None:
    try:
        lineage = load_live_corpus_lineage(Path(data_root))
    except (LiveCohortReleaseError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    if not isinstance(lineage, Mapping):
        return None
    return build_cohort_import_readback(Path(data_root), lineage=lineage)


def _historical_calibration(
    data_root: Path, *, repo_root: Path
) -> tuple[list[dict[str, Any]], str | None]:
    from solana_alpha_lab.factory.hfic_selection_robustness_gate import (
        load_applicable_gate_receipt,
    )
    from solana_alpha_lab.factory.scientific_eligibility_projection import (
        ELIGIBILITY_SCOPE_FULL_LIFECYCLE,
    )

    loaded = load_applicable_gate_receipt(Path(data_root), root=Path(repo_root))
    if loaded is None:
        return [], None
    integrity = "INVALID" if loaded.get("integrity_invalid") else "PASS"
    row = {
        "scope": "HISTORICAL_CALIBRATION",
        "calibration_id": "HFIC_SELECTION_ROBUSTNESS_GATE_V1",
        "cohort_scope": "C1",
        "eligibility_scope": ELIGIBILITY_SCOPE_FULL_LIFECYCLE,
        "receipt_sha256": str(loaded.get("receipt_sha256") or ""),
        "router_decision": loaded.get("router_decision"),
        "integrity": integrity,
    }
    if integrity == "INVALID":
        return [row], str(loaded.get("integrity_reason") or HISTORICAL_CALIBRATION_INVALID)
    return [row], None


def _prior_memory_ok(data_root: Path, *, repo_root: Path) -> bool:
    from solana_alpha_lab.factory.hfic_memory_policy import quarantined_session_ids
    from solana_alpha_lab.factory.hfic_prior_memory import build_prior_memory_snapshot
    from solana_alpha_lab.factory.research_store import (
        ExistingResearchStoreReader,
        ResearchStoreError,
    )

    try:
        store = ExistingResearchStoreReader(Path(data_root))
    except ResearchStoreError:
        return True
    snapshot = build_prior_memory_snapshot(
        store,
        store_inventory_digest="0" * 64,
        repo_root=Path(repo_root),
    )
    blocked = set(quarantined_session_ids(store))
    for capsule in snapshot.get("capsules") or []:
        if not isinstance(capsule, Mapping):
            continue
        session_id = capsule.get("session_id")
        if isinstance(session_id, str) and session_id and session_id in blocked:
            return False
    return True


def build_forge_input_receipt(
    data_root: Path,
    *,
    repo_root: Path,
    imported_cohort_id: str | None = None,
    evidence_surface_mode: str | None = None,
    owner_focus: str = "AUTO",
) -> dict[str, Any]:
    """Build the canonical Forge input/visibility receipt. No writes."""

    from solana_alpha_lab.factory.hfic_preflight import (
        enumerate_rdp_datasets,
        is_live_corpus_dataset,
        preview_forge_packet_vision,
        select_forge_packet_datasets,
    )
    from solana_alpha_lab.factory.live_cohort_discovery_release import (
        select_current_datasets_for_forge,
    )

    blocking: list[str] = []
    owner_class = OWNER_CLASS_READY
    readback = _load_readback(Path(data_root))
    visible_ids: list[str] = []
    current_mid = None
    corpus_version = None
    lineage_ok = False
    if readback is not None:
        visible_ids = [
            str(item.get("cohort_id"))
            for item in (readback.get("visible_cohorts") or [])
            if isinstance(item, Mapping) and item.get("cohort_id")
        ]
        current_mid = readback.get("current_dataset_manifest_id")
        if isinstance(current_mid, str) and current_mid:
            current_mid = str(current_mid)
        else:
            current_mid = None
        corpus_version = readback.get("corpus_version")
        lineage_ok = str(readback.get("lineage_integrity") or "") == "PASS"
        if str(readback.get("lineage_integrity") or "") == "DUPLICATE_LINEAGE":
            blocking.append(DUPLICATE_LINEAGE)
            owner_class = OWNER_CLASS_OBSERVABILITY_BLOCKED
    else:
        blocking.append(CURRENT_CORPUS_MISSING)
        owner_class = OWNER_CLASS_INPUT_NOT_READY

    if readback is not None and not lineage_ok:
        # The visible corpus may be present while its current lineage is
        # UNKNOWN/FAIL.  That is an observability stop, never a market epoch.
        blocking.append("LINEAGE_INTEGRITY_UNVERIFIED")
        owner_class = OWNER_CLASS_OBSERVABILITY_BLOCKED

    if imported_cohort_id and imported_cohort_id not in visible_ids:
        blocking.append(IMPORTED_COHORT_MISSING)
        if owner_class == OWNER_CLASS_READY:
            owner_class = OWNER_CLASS_INPUT_NOT_READY

    datasets, _warnings = enumerate_rdp_datasets(Path(data_root))
    selected, trunc = select_forge_packet_datasets(datasets)
    current_datasets = list(select_current_datasets_for_forge(datasets))
    live_in_packet = bool(trunc.get("live_corpus_in_packet"))
    current_live = [item for item in current_datasets if is_live_corpus_dataset(item)]
    chosen = None
    for item in selected:
        if is_live_corpus_dataset(item):
            chosen = item
            break
    if chosen is None and current_live:
        blocking.append(CURRENT_CORPUS_EXCLUDED_FROM_PACKET)
        owner_class = OWNER_CLASS_OBSERVABILITY_BLOCKED
    elif chosen is None and CURRENT_CORPUS_MISSING not in blocking:
        blocking.append(CURRENT_CORPUS_MISSING)
        if owner_class == OWNER_CLASS_READY:
            owner_class = OWNER_CLASS_INPUT_NOT_READY
    if chosen is not None and current_mid:
        chosen_mid = str(chosen.get("dataset_manifest_id") or "")
        if chosen_mid != str(current_mid):
            blocking.append(CONTROL_CORPUS_MANIFEST_MISMATCH)
            owner_class = OWNER_CLASS_OBSERVABILITY_BLOCKED

    historical, hist_reason = _historical_calibration(
        Path(data_root), repo_root=Path(repo_root)
    )
    if hist_reason:
        blocking.append(hist_reason)
        if owner_class == OWNER_CLASS_READY:
            owner_class = OWNER_CLASS_OBSERVABILITY_BLOCKED

    material_truncation = bool(current_live) and not live_in_packet
    corpus_binding = chosen is not None and not material_truncation
    prior_ok = _prior_memory_ok(Path(data_root), repo_root=Path(repo_root))
    probe_ok = (Path(repo_root) / PROBE_CONTRACT_RELATIVE).is_file()
    vision = preview_forge_packet_vision(
        Path(repo_root),
        Path(data_root),
        live_corpus_in_packet=live_in_packet,
        material_truncation=material_truncation,
        evidence_surface_mode=evidence_surface_mode,
        owner_focus=owner_focus,
    )
    visibility = {
        "corpus_binding": _pass_fail(corpus_binding),
        "lineage": _pass_fail(lineage_ok if readback is not None else False),
        "pit_semantics": "NOT_EVALUATED",
        "missingness_visible": "NOT_EVALUATED",
        "prior_memory": _pass_fail(prior_ok),
        "feature_grounding": str(vision.get("feature_grounding") or "FAIL"),
        "packet_vision": str(vision.get("packet_vision") or "FAIL"),
        "material_truncation": material_truncation,
    }
    if not prior_ok:
        blocking.append("QUARANTINED_MEMORY_ELIGIBLE")
        owner_class = OWNER_CLASS_OBSERVABILITY_BLOCKED
    if material_truncation and CURRENT_CORPUS_EXCLUDED_FROM_PACKET not in blocking:
        blocking.append(CURRENT_CORPUS_EXCLUDED_FROM_PACKET)
        owner_class = OWNER_CLASS_OBSERVABILITY_BLOCKED
    vision_integrity = vision.get("vision_integrity") or {}
    if str(vision_integrity.get("status") or "") != "PASS":
        blocking.append(FORGE_VISION_INTEGRITY_BLOCKED)
        owner_class = OWNER_CLASS_OBSERVABILITY_BLOCKED

    representations = [
        {"representation_id": BASE_REPRESENTATION, "status": READY_STATUS},
        {
            "representation_id": TRAJECTORY_REPRESENTATION,
            "status": TRAJECTORY_STATUS if probe_ok else "PROBE_CONTRACT_MISSING",
        },
    ]
    live_corpus = None
    if chosen is not None:
        labels = dict(chosen.get("labels") or {})
        live_corpus = {
            "dataset_id": CORPUS_DATASET_ID,
            "dataset_manifest_id": chosen.get("dataset_manifest_id"),
            "dataset_version": chosen.get("dataset_version") or labels.get("dataset_version"),
            "corpus_version": labels.get("corpus_version", corpus_version),
            "yield_eligible": labels.get("yield_eligible", chosen.get("yield_eligible")),
        }

    forge_runnable = owner_class == OWNER_CLASS_READY and not blocking
    if not forge_runnable and owner_class == OWNER_CLASS_READY:
        owner_class = OWNER_CLASS_INPUT_NOT_READY
        if not blocking:
            blocking.append(CURRENT_CORPUS_MISSING)

    from solana_alpha_lab.factory.hfic_evidence_identity import (
        EvidenceIdentityError,
        build_market_evidence_basis,
        compute_capability_epoch_for_repo,
        lineage_cohort_bindings,
        market_evidence_epoch_sha256 as _hash_market_basis,
    )

    market_basis = build_market_evidence_basis(
        # Packet membership remains bounded; market identity covers every
        # current logical dataset so an out-of-packet decision-bearing source
        # cannot change without changing the admission epoch.
        datasets=current_datasets,
        visible_cohort_ids=visible_ids,
        current_dataset_manifest_id=current_mid,
        corpus_version=corpus_version,
        lineage_bindings=lineage_cohort_bindings(
            Path(data_root),
            verified_dataset_manifest_ids={
                str(item.get("dataset_manifest_id") or "")
                for item in datasets
                if isinstance(item, Mapping) and item.get("dataset_manifest_id")
            },
        ),
    )
    market_epoch: str | None = None
    if lineage_ok and readback is not None:
        try:
            market_epoch = _hash_market_basis(market_basis)
        except EvidenceIdentityError:
            if "MARKET_EVIDENCE_BASIS_INCOMPLETE" not in blocking:
                blocking.append("MARKET_EVIDENCE_BASIS_INCOMPLETE")
            forge_runnable = False
            if owner_class == OWNER_CLASS_READY:
                owner_class = OWNER_CLASS_INPUT_NOT_READY
    else:
        forge_runnable = False
    capability_epoch: str | None
    try:
        capability_epoch, _cap_basis = compute_capability_epoch_for_repo(Path(repo_root))
    except Exception:
        capability_epoch = None
        blocking.append("CAPABILITY_IDENTITY_UNAVAILABLE")
        forge_runnable = False
        owner_class = OWNER_CLASS_OBSERVABILITY_BLOCKED

    body = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "owner_class": owner_class,
        "active_evidence_set": {
            "scope": "ACTIVE_EVIDENCE_SET",
            "current_dataset_manifest_id": current_mid,
            "visible_cohort_ids": visible_ids,
            "corpus_version": corpus_version,
            "evidence_set_sha256": _evidence_set_sha256(
                current_dataset_manifest_id=current_mid,
                visible_cohort_ids=visible_ids,
                corpus_version=corpus_version,
            ),
        },
        "market_evidence_basis": market_basis,
        "historical_calibration": historical,
        "representation_input_scope": {
            "scope": "REPRESENTATION_INPUT_SCOPE",
            "status": "DECLARED",
        },
        "experiment_data_scope": {
            "scope": "EXPERIMENT_DATA_SCOPE",
            "status": "NOT_STARTED",
        },
        "visibility": visibility,
        "representations": representations,
        "packet": {
            "live_corpus_in_packet": live_in_packet,
            "live_corpus_protected": bool(trunc.get("live_corpus_protected")),
            "truncated": bool(trunc.get("truncated")),
            "bounded_dataset_count": len(selected),
            "selection_policy": str(
                trunc.get("selection_policy") or "control_protect_live_corpus_then_cap"
            ),
        },
        "live_corpus": live_corpus,
        "evidence_surface_mode": evidence_surface_mode,
        "forge_runnable": forge_runnable,
        "blocking_reason_codes": list(dict.fromkeys(blocking)),
        "writes": {"research_store": 0, "forge_context": 0, "session": 0},
        "data_root_instance_fingerprint_sha256": instance_fingerprint(Path(data_root)),
    }
    if market_epoch is not None:
        body["market_evidence_epoch_sha256"] = market_epoch
    if capability_epoch is not None:
        body["capability_epoch_sha256"] = capability_epoch
    hashed = dict(body)
    hashed["receipt_sha256"] = canonical_sha256(body)
    return hashed


__all__ = [
    "CURRENT_CORPUS_EXCLUDED_FROM_PACKET",
    "CURRENT_CORPUS_MISSING",
    "FORGE_VISION_INTEGRITY_BLOCKED",
    "OWNER_CLASS_INPUT_NOT_READY",
    "OWNER_CLASS_OBSERVABILITY_BLOCKED",
    "OWNER_CLASS_READY",
    "SCHEMA",
    "SCHEMA_VERSION",
    "build_forge_input_receipt",
    "format_forge_input_owner_block",
    "forge_input_owner_next",
]
