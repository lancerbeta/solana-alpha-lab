"""Shared Forge market/capability identity and admission rules (A5).

Splits decision-bearing market evidence from protocol/capability provenance.
Scientific budgets follow market slots; Git/docs/model provenance alone does
not reset quota. Legacy combined ``evidence_epoch_sha256`` remains readable.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from solana_alpha_lab.factory.run_passport import canonical_sha256

MARKET_BASIS_VERSION = "MARKET_EVIDENCE_BASIS_V1"
CAPABILITY_BASIS_VERSION = "CAPABILITY_EPOCH_BASIS_V1"
SCIENTIFIC_SLOT_VERSION = "SCIENTIFIC_SLOT_V1"
EXECUTION_BINDING_VERSION = "EXECUTION_BINDING_V1"
RUN_IDENTITY_VERSION = "FORGE_RUN_IDENTITY_V2"
LEGACY_EPOCH_INTERPRETATION = "LEGACY_COMBINED_EVIDENCE_EPOCH_V1"

# Protocol / executable surfaces that define capability semantics.
_CAPABILITY_PROTOCOL_FILES = (
    "configs/hypothesis_forge_independent_critic_v1.yaml",
    "configs/hfic_representation_ladder_v1.yaml",
    "catalog/schemas/hypothesis_critic_input_v1.schema.json",
    "catalog/schemas/experiment_spec.schema.json",
    "catalog/schemas/forge_run_receipt_v1.schema.json",
    "catalog/query_recipes.yaml",
    "docs/contracts/normalized_trajectory_v1_capability_contract.md",
    "docs/contracts/normalized_trajectory_representation_probe_v1.md",
)

_OPERATOR_PACK = (
    "docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md"
)
_PROMPT_SECTION_RE = re.compile(
    r"BEGIN PROMPT ([ABC]).*?END PROMPT \1",
    re.DOTALL | re.IGNORECASE,
)

DISPOSITION_COMPATIBLE = "COMPATIBLE_FOR_EXACT_REUSE_OR_RESUME"
DISPOSITION_HISTORICAL_ONLY = "HISTORICAL_ONLY"
DISPOSITION_UNRESOLVED = "UNRESOLVED_BINDING"


class EvidenceIdentityError(ValueError):
    """Fail-closed market/capability identity error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(root: Path, relative: str) -> str | None:
    path = root / relative
    if not path.is_file():
        return None
    return _sha256_bytes(path.read_bytes())


def _prompt_section_digests(repo_root: Path) -> dict[str, str]:
    path = Path(repo_root) / _OPERATOR_PACK
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for match in _PROMPT_SECTION_RE.finditer(text):
        letter = match.group(1).upper()
        out[f"prompt_{letter.lower()}_sha256"] = _sha256_bytes(
            match.group(0).encode("utf-8")
        )
    return dict(sorted(out.items()))


def lineage_cohort_bindings(data_root: Path | None) -> list[dict[str, str]]:
    """Canonical cohort→source bindings from live corpus lineage (if present)."""

    if data_root is None:
        return []
    try:
        from solana_alpha_lab.factory.live_cohort_discovery_release import (
            load_live_corpus_lineage,
        )

        lineage = load_live_corpus_lineage(Path(data_root))
    except Exception:
        return []
    if not isinstance(lineage, Mapping):
        return []
    rows: list[dict[str, str]] = []
    for item in lineage.get("cohorts") or []:
        if not isinstance(item, Mapping):
            continue
        cohort_id = str(item.get("cohort_id") or "").strip()
        if not cohort_id:
            continue
        rows.append(
            {
                "cohort_id": cohort_id,
                "release_id": str(item.get("release_id") or ""),
                "source_sha256": str(item.get("source_sha256") or ""),
            }
        )
    rows.sort(key=lambda row: row["cohort_id"])
    return rows


def build_market_evidence_basis(
    *,
    datasets: Sequence[Mapping[str, Any]] | None = None,
    visible_cohort_ids: Sequence[str] | None = None,
    current_dataset_manifest_id: str | None = None,
    corpus_version: Any = None,
    lineage_bindings: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Decision-bearing market evidence set. Excludes Git/Catalog/protocol bytes."""

    dataset_rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in datasets or ():
        if not isinstance(item, Mapping):
            continue
        mid = str(item.get("dataset_manifest_id") or "").strip()
        fp = str(item.get("dataset_fingerprint") or "").strip()
        if not mid or not fp or mid in seen:
            continue
        seen.add(mid)
        dataset_rows.append(
            {
                "dataset_manifest_id": mid,
                "dataset_fingerprint": fp,
                "dataset_id": str(item.get("dataset_id") or ""),
            }
        )
    dataset_rows.sort(key=lambda row: row["dataset_manifest_id"])

    cohorts = sorted(
        {
            str(item).strip()
            for item in (visible_cohort_ids or ())
            if str(item).strip()
        }
    )
    bindings: list[dict[str, str]] = []
    for item in lineage_bindings or ():
        if not isinstance(item, Mapping):
            continue
        cohort_id = str(item.get("cohort_id") or "").strip()
        if not cohort_id:
            continue
        if cohorts and cohort_id not in cohorts:
            continue
        bindings.append(
            {
                "cohort_id": cohort_id,
                "release_id": str(item.get("release_id") or ""),
                "source_sha256": str(item.get("source_sha256") or ""),
            }
        )
    bindings.sort(key=lambda row: row["cohort_id"])

    return {
        "basis_version": MARKET_BASIS_VERSION,
        "current_dataset_manifest_id": current_dataset_manifest_id,
        "corpus_version": corpus_version,
        "visible_cohort_ids": cohorts,
        "datasets": dataset_rows,
        "lineage_bindings": bindings,
    }


def market_evidence_epoch_sha256(basis: Mapping[str, Any]) -> str:
    if not isinstance(basis, Mapping) or not basis.get("datasets"):
        if not (basis or {}).get("visible_cohort_ids") and not (
            basis or {}
        ).get("lineage_bindings"):
            raise EvidenceIdentityError("MARKET_EVIDENCE_BASIS_INCOMPLETE")
    return canonical_sha256(dict(basis))


def build_capability_epoch_basis(repo_root: Path) -> dict[str, Any]:
    """Narrow protocol/capability projection. Not a market epoch."""

    from solana_alpha_lab.factory.hfic_session import PROMPT_VERSION
    from solana_alpha_lab.factory_semantic_operability import (
        SemanticOperabilityError,
        semantic_capability_digest_for_repo,
    )

    root = Path(repo_root)
    protocol_files: list[dict[str, str]] = []
    for relative in _CAPABILITY_PROTOCOL_FILES:
        digest = _file_sha256(root, relative)
        if digest is None:
            continue
        protocol_files.append({"path": relative, "sha256": digest})
    try:
        semantic = semantic_capability_digest_for_repo(root)
    except SemanticOperabilityError:
        semantic = _sha256_bytes(b"SEMANTIC-DIGEST-UNAVAILABLE")
    return {
        "basis_version": CAPABILITY_BASIS_VERSION,
        "prompt_version": PROMPT_VERSION,
        "protocol_files": protocol_files,
        "prompt_sections": _prompt_section_digests(root),
        "semantic_capability_digest_sha256": semantic,
    }


def capability_epoch_sha256(basis: Mapping[str, Any]) -> str:
    return canonical_sha256(dict(basis))


def scientific_slot_sha256(
    *,
    market_evidence_epoch_sha256: str,
    representation_id: str,
    representation_semantic_version: str,
    owner_focus: str,
) -> str:
    from solana_alpha_lab.factory.hfic_identity import normalize_text

    return canonical_sha256(
        {
            "slot_version": SCIENTIFIC_SLOT_VERSION,
            "market_evidence_epoch_sha256": market_evidence_epoch_sha256,
            "representation_id": str(representation_id),
            "representation_semantic_version": str(representation_semantic_version),
            "focus_key_sha256": hashlib.sha256(
                normalize_text(owner_focus).encode("utf-8")
            ).hexdigest(),
        }
    )


def execution_binding_sha256(
    *,
    scientific_slot_sha256: str,
    capability_epoch_sha256: str,
    representation_payload_sha256: str | None = None,
    memory_eligibility_sha256: str | None = None,
    model_provenance_sha256: str | None = None,
) -> str:
    return canonical_sha256(
        {
            "binding_version": EXECUTION_BINDING_VERSION,
            "scientific_slot_sha256": scientific_slot_sha256,
            "capability_epoch_sha256": capability_epoch_sha256,
            "representation_payload_sha256": representation_payload_sha256,
            "memory_eligibility_sha256": memory_eligibility_sha256,
            "model_provenance_sha256": model_provenance_sha256,
        }
    )


def forge_run_identity_sha256(
    *,
    market_evidence_epoch_sha256: str,
    frozen_representation_ids: Sequence[str],
    owner_focus: str,
) -> str:
    """Immutable run admission identity. Excludes session/progress artifacts."""

    return canonical_sha256(
        {
            "identity_version": RUN_IDENTITY_VERSION,
            "market_evidence_epoch_sha256": market_evidence_epoch_sha256,
            "frozen_representation_ids": list(frozen_representation_ids),
            "owner_focus": owner_focus,
        }
    )


def compute_market_epoch_for_data_root(
    repo_root: Path,
    data_root: Path | None,
    *,
    store: Any = None,
    visible_cohort_ids: Sequence[str] | None = None,
    current_dataset_manifest_id: str | None = None,
    corpus_version: Any = None,
) -> tuple[str, dict[str, Any]]:
    """Build market basis from A3-compatible dataset enumeration + lineage."""

    del store  # store is not a market truth owner; datasets/lineage are.
    datasets: list[Mapping[str, Any]] = []
    mid = current_dataset_manifest_id
    version = corpus_version
    cohorts = list(visible_cohort_ids or [])
    if data_root is not None:
        from solana_alpha_lab.factory.hfic_preflight import (
            enumerate_rdp_datasets,
            select_forge_packet_datasets,
        )

        enumerated, _warnings = enumerate_rdp_datasets(Path(data_root))
        selected, _trunc = select_forge_packet_datasets(enumerated)
        datasets = list(selected)
        if not cohorts or mid is None:
            try:
                from solana_alpha_lab.factory.cohort_import_readback import (
                    build_cohort_import_readback,
                )

                readback = build_cohort_import_readback(Path(data_root))
            except Exception:
                readback = None
            if isinstance(readback, Mapping):
                if not cohorts:
                    cohorts = [
                        str(item.get("cohort_id"))
                        for item in (readback.get("visible_cohorts") or [])
                        if isinstance(item, Mapping) and item.get("cohort_id")
                    ]
                if mid is None:
                    raw_mid = readback.get("current_dataset_manifest_id")
                    mid = str(raw_mid) if isinstance(raw_mid, str) and raw_mid else None
                if version is None:
                    version = readback.get("corpus_version")
    bindings = lineage_cohort_bindings(data_root)
    basis = build_market_evidence_basis(
        datasets=datasets,
        visible_cohort_ids=cohorts,
        current_dataset_manifest_id=mid,
        corpus_version=version,
        lineage_bindings=bindings,
    )
    if not basis["datasets"] and not basis["visible_cohort_ids"]:
        # Empty commissioning / no corpus: stable empty-market sentinel.
        basis = {
            **basis,
            "datasets": [
                {
                    "dataset_manifest_id": "COMMISSIONING_EMPTY",
                    "dataset_fingerprint": "0" * 64,
                    "dataset_id": "COMMISSIONING",
                }
            ],
        }
    return market_evidence_epoch_sha256(basis), basis


def compute_capability_epoch_for_repo(repo_root: Path) -> tuple[str, dict[str, Any]]:
    basis = build_capability_epoch_basis(Path(repo_root))
    return capability_epoch_sha256(basis), basis


def compute_split_identity(
    repo_root: Path,
    data_root: Path | None = None,
    *,
    store: Any = None,
    visible_cohort_ids: Sequence[str] | None = None,
    current_dataset_manifest_id: str | None = None,
    corpus_version: Any = None,
) -> dict[str, Any]:
    """One shared identity snapshot for preflight / forge-run / freeze."""

    from solana_alpha_lab.factory.hfic_preflight import evidence_epoch_material
    from solana_alpha_lab.factory.hfic_session import evidence_epoch_sha256 as legacy_hash

    market_epoch, market_basis = compute_market_epoch_for_data_root(
        Path(repo_root),
        Path(data_root) if data_root is not None else None,
        store=store,
        visible_cohort_ids=visible_cohort_ids,
        current_dataset_manifest_id=current_dataset_manifest_id,
        corpus_version=corpus_version,
    )
    capability_epoch, capability_basis = compute_capability_epoch_for_repo(
        Path(repo_root)
    )
    legacy_material = evidence_epoch_material(
        Path(repo_root),
        Path(data_root) if data_root is not None else None,
        store=store,
    )
    legacy_epoch = legacy_hash(legacy_material)
    return {
        "market_evidence_epoch_sha256": market_epoch,
        "capability_epoch_sha256": capability_epoch,
        "legacy_combined_evidence_epoch_sha256": legacy_epoch,
        "legacy_epoch_interpretation": LEGACY_EPOCH_INTERPRETATION,
        # Admission / budget key for new sessions: market only.
        "evidence_epoch_sha256": market_epoch,
        "market_evidence_basis": market_basis,
        "capability_epoch_basis": {
            "basis_version": capability_basis.get("basis_version"),
            "prompt_version": capability_basis.get("prompt_version"),
            "semantic_capability_digest_sha256": capability_basis.get(
                "semantic_capability_digest_sha256"
            ),
            "protocol_file_count": len(capability_basis.get("protocol_files") or []),
            "prompt_section_keys": sorted(
                (capability_basis.get("prompt_sections") or {}).keys()
            ),
        },
    }


def classify_legacy_session_disposition(
    session: Mapping[str, Any],
    *,
    current_market_epoch: str,
    current_visible_cohort_ids: Sequence[str],
    require_control_mode: bool = False,
) -> dict[str, Any]:
    """Read-only disposition for a historical session against current input."""

    from solana_alpha_lab.factory.hfic_control_integrity import (
        CURRENT_REPRESENTATION_CONTROL_V1,
        session_evidence_surface_mode,
    )

    frozen_market = session.get("market_evidence_epoch_sha256")
    frozen_legacy = str(session.get("evidence_epoch_sha256") or "")
    mode = session_evidence_surface_mode(session)
    packet = session.get("forge_context_packet")
    bound: list[str] = []
    if isinstance(packet, Mapping):
        raw = packet.get("bound_visible_cohort_ids") or packet.get("visible_cohort_ids")
        if isinstance(raw, list):
            bound = [str(item) for item in raw if item]
    current = [str(item) for item in current_visible_cohort_ids if item]

    reasons: list[str] = []
    if require_control_mode and mode != CURRENT_REPRESENTATION_CONTROL_V1:
        reasons.append("NOT_CONTROL_SURFACE")
    if isinstance(frozen_market, str) and frozen_market:
        if frozen_market == current_market_epoch:
            disposition = DISPOSITION_COMPATIBLE
        else:
            disposition = DISPOSITION_HISTORICAL_ONLY
            reasons.append("MARKET_EPOCH_MISMATCH")
    elif frozen_legacy and bound and current and set(bound) == set(current):
        # Legacy without split fields: cohort equality alone is insufficient for
        # current reuse; mark unresolved unless exact market field exists.
        disposition = DISPOSITION_UNRESOLVED
        reasons.append("LEGACY_EPOCH_WITHOUT_MARKET_SPLIT")
    elif frozen_legacy:
        disposition = DISPOSITION_HISTORICAL_ONLY
        reasons.append("LEGACY_COMBINED_EPOCH_ONLY")
    else:
        disposition = DISPOSITION_UNRESOLVED
        reasons.append("MISSING_EPOCH_BINDING")

    if bound and current and set(bound) != set(current):
        if disposition == DISPOSITION_COMPATIBLE:
            disposition = DISPOSITION_HISTORICAL_ONLY
        reasons.append("FROZEN_SCOPE_NE_CURRENT_VISIBLE")

    return {
        "session_id": session.get("session_id"),
        "disposition": disposition,
        "reasons": reasons,
        "frozen_market_evidence_epoch_sha256": frozen_market,
        "frozen_evidence_epoch_sha256": frozen_legacy or None,
        "frozen_bound_cohort_ids": bound,
        "evidence_surface_mode": mode,
        "session_state": session.get("session_state"),
        "effective_terminal": session.get("critic_terminal")
        or session.get("effective_terminal"),
    }


def sessions_for_market_budget(
    sessions: Sequence[Mapping[str, Any]],
    *,
    market_evidence_epoch: str,
) -> list[Mapping[str, Any]]:
    """Sessions that consume scientific budget for the current market epoch."""

    matched: list[Mapping[str, Any]] = []
    for item in sessions:
        stamped = item.get("market_evidence_epoch_sha256")
        if isinstance(stamped, str) and stamped:
            if stamped == market_evidence_epoch:
                matched.append(item)
            continue
        # Legacy sessions: only count when their combined epoch equals the
        # current market key (new admissions stamp market into evidence_epoch).
        if item.get("evidence_epoch_sha256") == market_evidence_epoch:
            matched.append(item)
    return matched


__all__ = [
    "CAPABILITY_BASIS_VERSION",
    "DISPOSITION_COMPATIBLE",
    "DISPOSITION_HISTORICAL_ONLY",
    "DISPOSITION_UNRESOLVED",
    "EvidenceIdentityError",
    "LEGACY_EPOCH_INTERPRETATION",
    "MARKET_BASIS_VERSION",
    "RUN_IDENTITY_VERSION",
    "build_capability_epoch_basis",
    "build_market_evidence_basis",
    "capability_epoch_sha256",
    "classify_legacy_session_disposition",
    "compute_capability_epoch_for_repo",
    "compute_market_epoch_for_data_root",
    "compute_split_identity",
    "execution_binding_sha256",
    "forge_run_identity_sha256",
    "lineage_cohort_bindings",
    "market_evidence_epoch_sha256",
    "scientific_slot_sha256",
    "sessions_for_market_budget",
]
