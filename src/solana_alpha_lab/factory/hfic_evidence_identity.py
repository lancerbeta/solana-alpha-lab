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
BASE_REPRESENTATION_ID = "BASE"
BASE_REPRESENTATION_VERSION = "HFIC-V1.2"

# Protocol / executable surfaces that define capability semantics.
_CAPABILITY_PROTOCOL_FILES = (
    "configs/hypothesis_forge_independent_critic_v1.yaml",
    "configs/hfic_representation_ladder_v1.yaml",
    "catalog/schemas/hypothesis_critic_input_v1.schema.json",
    "catalog/schemas/forge_input_receipt_v1.schema.json",
    "catalog/schemas/experiment_spec.schema.json",
    "catalog/schemas/forge_run_receipt_v1.schema.json",
    "catalog/schemas/hypothesis_forge_session_receipt_v1.schema.json",
    "catalog/schemas/hypothesis_forge_session_receipt_v1_2.schema.json",
    "catalog/schemas/hypothesis_forge_session_receipt_v1_3.schema.json",
    "schemas/research_memory_projection_v1.sql",
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
                # A3's canonical live-corpus lineage names the immutable
                # release payload `content_sha256`; older fixture/readback
                # surfaces expose the same binding as `source_sha256`.
                "source_sha256": str(
                    item.get("source_sha256")
                    or item.get("content_sha256")
                    or ""
                ),
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
    if not isinstance(basis, Mapping):
        raise EvidenceIdentityError("MARKET_EVIDENCE_BASIS_INCOMPLETE")

    # A market epoch is an admission identity, not a checksum over whatever
    # labels happened to be available.  The current manifest, visible release
    # lineage and dataset fingerprints must form one complete A3 readback.
    if basis.get("basis_version") != MARKET_BASIS_VERSION:
        raise EvidenceIdentityError("MARKET_EVIDENCE_BASIS_INCOMPLETE")
    current_mid = str(basis.get("current_dataset_manifest_id") or "").strip()
    visible = {
        str(item).strip()
        for item in (basis.get("visible_cohort_ids") or ())
        if str(item).strip()
    }
    datasets = basis.get("datasets")
    bindings = basis.get("lineage_bindings")
    if basis.get("corpus_version") is None or not current_mid:
        raise EvidenceIdentityError("MARKET_EVIDENCE_BASIS_INCOMPLETE")
    if not isinstance(datasets, Sequence) or isinstance(datasets, (str, bytes)):
        raise EvidenceIdentityError("MARKET_EVIDENCE_BASIS_INCOMPLETE")
    if not isinstance(bindings, Sequence) or isinstance(bindings, (str, bytes)):
        raise EvidenceIdentityError("MARKET_EVIDENCE_BASIS_INCOMPLETE")
    if not visible or not datasets or not bindings:
        raise EvidenceIdentityError("MARKET_EVIDENCE_BASIS_INCOMPLETE")

    dataset_mids: set[str] = set()
    for item in datasets:
        if not isinstance(item, Mapping):
            raise EvidenceIdentityError("MARKET_EVIDENCE_BASIS_INCOMPLETE")
        mid = str(item.get("dataset_manifest_id") or "").strip()
        dataset_id = str(item.get("dataset_id") or "").strip()
        fingerprint = str(item.get("dataset_fingerprint") or "").strip()
        if (
            not mid
            or not dataset_id
            or not re.fullmatch(r"[0-9a-f]{64}", fingerprint)
            or mid in dataset_mids
        ):
            raise EvidenceIdentityError("MARKET_EVIDENCE_BASIS_INCOMPLETE")
        dataset_mids.add(mid)
    if current_mid not in dataset_mids:
        raise EvidenceIdentityError("MARKET_EVIDENCE_BASIS_INCOMPLETE")

    binding_ids: set[str] = set()
    for item in bindings:
        if not isinstance(item, Mapping):
            raise EvidenceIdentityError("MARKET_EVIDENCE_BASIS_INCOMPLETE")
        cohort_id = str(item.get("cohort_id") or "").strip()
        release_id = str(item.get("release_id") or "").strip()
        source_sha = str(item.get("source_sha256") or "").strip()
        if (
            not cohort_id
            or not release_id
            or not re.fullmatch(r"[0-9a-f]{64}", source_sha)
            or cohort_id in binding_ids
        ):
            raise EvidenceIdentityError("MARKET_EVIDENCE_BASIS_INCOMPLETE")
        binding_ids.add(cohort_id)
    if binding_ids != visible:
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
    missing_protocol_files: list[str] = []
    for relative in _CAPABILITY_PROTOCOL_FILES:
        digest = _file_sha256(root, relative)
        if digest is None:
            missing_protocol_files.append(relative)
            continue
        protocol_files.append({"path": relative, "sha256": digest})
    if missing_protocol_files:
        # A capability identity is an admission binding, not a best-effort
        # inventory.  Omitting a protocol surface would make an incomplete
        # repository look like a valid but different capability epoch.
        raise EvidenceIdentityError("CAPABILITY_PROTOCOL_SURFACE_INCOMPLETE")
    try:
        semantic = semantic_capability_digest_for_repo(root)
    except SemanticOperabilityError:
        raise EvidenceIdentityError("CAPABILITY_SEMANTIC_SURFACE_INCOMPLETE") from None
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
    control_session_id: str | None = None,
    representation_payload_sha256: str | None = None,
    memory_eligibility_sha256: str | None = None,
    model_provenance_sha256: str | None = None,
) -> str:
    return canonical_sha256(
        {
            "binding_version": EXECUTION_BINDING_VERSION,
            "scientific_slot_sha256": scientific_slot_sha256,
            "capability_epoch_sha256": capability_epoch_sha256,
            "control_session_id": control_session_id,
            "representation_payload_sha256": representation_payload_sha256,
            "memory_eligibility_sha256": memory_eligibility_sha256,
            "model_provenance_sha256": model_provenance_sha256,
        }
    )


def representation_identity_from_session(
    session: Mapping[str, Any],
) -> tuple[str | None, str | None]:
    """Return the persisted representation identity without guessing legacy data."""

    if not isinstance(session, Mapping):
        return None, None
    raw_representation = (
        session.get("ladder_representation_id")
        or session.get("representation_id")
    )
    if not isinstance(raw_representation, str) or not raw_representation.strip():
        return None, None
    representation = raw_representation.strip()
    if representation in {"CURRENT_REPRESENTATION_CONTROL_V1", "ORDINARY_BASE"}:
        representation = BASE_REPRESENTATION_ID
    raw_version = (
        session.get("representation_semantic_version")
        or session.get("semantic_version")
        or session.get("representation_version")
    )
    version = str(raw_version).strip() if raw_version is not None else ""
    return representation, version or None


def session_scientific_slot_sha256(session: Mapping[str, Any]) -> str | None:
    """Read an explicit slot, or derive it only from complete split fields.

    A legacy row with a market stamp but without the new slot/provenance fields
    deliberately returns ``None``.  Callers must still count that row as a
    known historical market look; absence of the new stamp is not proof that
    the market slot was free.
    """

    if not isinstance(session, Mapping):
        return None
    explicit = session.get("scientific_slot_sha256")
    explicit_is_present = explicit not in (None, "")
    if explicit_is_present and (
        not isinstance(explicit, str)
        or re.fullmatch(r"[0-9a-f]{64}", explicit) is None
    ):
        return None
    market = session.get("market_evidence_epoch_sha256")
    representation, version = representation_identity_from_session(session)
    focus = session.get("owner_focus")
    if not isinstance(market, str) or re.fullmatch(r"[0-9a-f]{64}", market) is None:
        return None
    if not representation or not version or not isinstance(focus, str) or not focus:
        return None
    from solana_alpha_lab.factory.hfic_identity import normalize_text

    derived_focus_key = hashlib.sha256(
        normalize_text(focus).encode("utf-8")
    ).hexdigest()
    focus_key = session.get("focus_key_sha256")
    if isinstance(focus_key, str) and len(focus_key) == 64 and focus_key != derived_focus_key:
        return None
    derived = scientific_slot_sha256(
        market_evidence_epoch_sha256=market,
        representation_id=representation,
        representation_semantic_version=version,
        owner_focus=focus,
    )
    # A persisted stamp is an assertion about its source fields.  Do not use
    # an arbitrary 64-hex value as occupancy evidence when it cannot be
    # reproduced from the durable market/representation/focus identity.
    if explicit_is_present and explicit != derived:
        return None
    return derived


def _session_slot_identity_is_invalid(session: Mapping[str, Any]) -> bool:
    """Return true for a present slot stamp that cannot be recomputed."""

    if not isinstance(session, Mapping):
        return False
    if session.get("identity_binding_status") == "CONFLICT":
        return True
    explicit = session.get("scientific_slot_sha256")
    if explicit in (None, ""):
        return False
    return session_scientific_slot_sha256(session) is None


def _session_slot_focus_key(session: Mapping[str, Any]) -> str | None:
    value = session.get("focus_key_sha256")
    if isinstance(value, str) and len(value) == 64:
        return value
    owner_focus = session.get("owner_focus")
    if isinstance(owner_focus, str) and owner_focus.strip():
        from solana_alpha_lab.factory.hfic_identity import normalize_text

        return hashlib.sha256(normalize_text(owner_focus).encode("utf-8")).hexdigest()
    return None


def _session_slot_matches_execution_context(
    session: Mapping[str, Any],
    *,
    memory_eligibility_sha256: str | None,
    evidence_surface_mode: str | None,
) -> bool:
    if memory_eligibility_sha256 is not None and session.get(
        "memory_eligibility_sha256"
    ) != memory_eligibility_sha256:
        return False
    if evidence_surface_mode is not None and session.get(
        "evidence_surface_mode"
    ) != evidence_surface_mode:
        return False
    return True


def resolve_scientific_admission(
    sessions: Sequence[Mapping[str, Any]],
    *,
    market_evidence_epoch: str,
    representation_id: str,
    representation_semantic_version: str,
    owner_focus: str,
    reservations: Sequence[Mapping[str, Any]] | None = None,
    memory_eligibility_sha256: str | None = None,
    evidence_surface_mode: str | None = None,
    auto_sessions_per_market: int = 1,
    max_distinct_focuses: int = 3,
) -> dict[str, Any]:
    """Resolve one shared market-slot admission decision.

    The helper is intentionally storage-agnostic.  Preflight and ladder
    callers feed it the same projected sessions, so resume/reuse and budget
    cannot silently diverge between the two entry points.
    """

    representation = str(representation_id or BASE_REPRESENTATION_ID)
    version = str(representation_semantic_version or "").strip()
    if not version:
        raise EvidenceIdentityError("REPRESENTATION_SEMANTIC_VERSION_REQUIRED")
    target_slot = scientific_slot_sha256(
        market_evidence_epoch_sha256=market_evidence_epoch,
        representation_id=representation,
        representation_semantic_version=version,
        owner_focus=owner_focus,
    )
    observed_rows: list[Mapping[str, Any]] = []
    seen_rows: set[tuple[str, str]] = set()
    all_rows = [*(sessions or []), *(reservations or [])]
    invalid_rows = [
        item
        for item in all_rows
        if isinstance(item, Mapping) and _session_slot_identity_is_invalid(item)
    ]
    if invalid_rows:
        reason = (
            "SCIENTIFIC_IDENTITY_CONFLICT"
            if any(
                item.get("identity_binding_status") == "CONFLICT"
                for item in invalid_rows
            )
            else "SCIENTIFIC_SLOT_IDENTITY_INVALID"
        )
        return {
            "action": "STOP",
            "reason_code": reason,
            "session_id": None,
            "scientific_slot_sha256": target_slot,
            "occupancy": "UNRESOLVED_BINDING",
        }
    for item in all_rows:
        if not isinstance(item, Mapping):
            continue
        identity = (
            str(item.get("session_id") or ""),
            str(session_scientific_slot_sha256(item) or ""),
        )
        if identity in seen_rows and identity[0] and identity[1]:
            continue
        if identity[0] and identity[1]:
            seen_rows.add(identity)
        observed_rows.append(item)
    market_rows = list(
        sessions_for_market_budget(
            observed_rows,
            market_evidence_epoch=market_evidence_epoch,
        )
    )
    same_slot = [
        item
        for item in market_rows
        if session_scientific_slot_sha256(item) == target_slot
    ]
    same_slot.sort(
        key=lambda item: (
            int(item.get("hfic_cycle_seq") or 0),
            str(item.get("effective_at") or ""),
            str(item.get("record_id") or ""),
        ),
        reverse=True,
    )
    if same_slot:
        chosen = same_slot[0]
        session_id = str(chosen.get("session_id") or "") or None
        lifecycle_slot_ids = {
            str(item.get("session_id") or "")
            for item in (sessions or [])
            if isinstance(item, Mapping)
            and str(item.get("session_id") or "")
            and session_scientific_slot_sha256(item) == target_slot
        }
        # A reservation is durable occupancy, but it is not a resumable
        # lifecycle row.  Do not turn an orphan reservation into a fresh
        # session or pretend that its phase is readable after restart.
        if session_id is None or session_id not in lifecycle_slot_ids:
            return {
                "action": "STOP",
                "reason_code": "SCIENTIFIC_SLOT_OCCUPIED_READBACK_MISSING",
                "session_id": session_id,
                "scientific_slot_sha256": target_slot,
                "occupancy": "OCCUPIED_UNRESOLVED",
            }
        if _session_slot_matches_execution_context(
            chosen,
            memory_eligibility_sha256=memory_eligibility_sha256,
            evidence_surface_mode=evidence_surface_mode,
        ):
            state = str(chosen.get("session_state") or chosen.get("phase") or "")
            pending = {
                "PREFLIGHT_PROVEN",
                "DRAFT_VALIDATED",
                "FROZEN_AWAITING_CRITIC",
                "REVISED_AWAITING_CRITIC",
                "RUNNER_UP_AWAITING_CRITIC",
                "REVISION_REQUIRED",
                "AWAITING_CLASSIFICATION",
                "CRITIC_RESULT_READY",
                "RESERVED",
            }
            action = "RESUME_EXISTING_SESSION" if state in pending else "RETURN_EXISTING_SESSION"
            return {
                "action": action,
                "reason_code": state or "SCIENTIFIC_SLOT_OCCUPIED",
                "session_id": session_id,
                "scientific_slot_sha256": target_slot,
                "occupancy": "OCCUPIED",
            }
        return {
            "action": "STOP",
            "reason_code": "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING",
            "session_id": session_id,
            "scientific_slot_sha256": target_slot,
            "occupancy": "OCCUPIED",
        }

    matching_representation = [
        item
        for item in market_rows
        if representation_identity_from_session(item) == (representation, version)
    ]
    if representation != BASE_REPRESENTATION_ID and matching_representation:
        return {
            "action": "STOP",
            "reason_code": "REPRESENTATION_SLOT_OCCUPIED",
            "session_id": str(matching_representation[0].get("session_id") or "") or None,
            "scientific_slot_sha256": target_slot,
            "occupancy": "REPRESENTATION_OCCUPIED",
        }

    if representation == BASE_REPRESENTATION_ID:
        auto_count = sum(
            1
            for item in market_rows
            if str(item.get("owner_focus") or "AUTO").strip().casefold() == "auto"
        )
        if str(owner_focus or "").strip().casefold() == "auto":
            if auto_count >= auto_sessions_per_market:
                return {
                    "action": "STOP",
                    "reason_code": "SEARCH_BUDGET_EXHAUSTED",
                    "session_id": None,
                    "scientific_slot_sha256": target_slot,
                    "occupancy": "MARKET_BUDGET_EXHAUSTED",
                }
        else:
            distinct = {
                value
                for value in (_session_slot_focus_key(item) for item in market_rows)
                if value
            }
            from solana_alpha_lab.factory.hfic_identity import normalize_text

            requested = hashlib.sha256(
                normalize_text(str(owner_focus)).encode("utf-8")
            ).hexdigest()
            if requested not in distinct and len(distinct) >= max_distinct_focuses:
                return {
                    "action": "STOP",
                    "reason_code": "SEARCH_BUDGET_EXHAUSTED",
                    "session_id": None,
                    "scientific_slot_sha256": target_slot,
                    "occupancy": "MARKET_BUDGET_EXHAUSTED",
                }

    return {
        "action": "START_NEW_SESSION",
        "reason_code": "SCIENTIFIC_SLOT_AVAILABLE",
        "session_id": None,
        "scientific_slot_sha256": target_slot,
        "occupancy": "AVAILABLE",
    }


def forge_run_identity_sha256(
    *,
    market_evidence_epoch_sha256: str,
    frozen_representation_ids: Sequence[str],
    owner_focus: str,
    frozen_representation_versions: Sequence[str] | None = None,
) -> str:
    """Immutable run admission identity. Excludes session/progress artifacts."""

    payload: dict[str, Any] = {
        "identity_version": RUN_IDENTITY_VERSION,
        "market_evidence_epoch_sha256": market_evidence_epoch_sha256,
        "frozen_representation_ids": list(frozen_representation_ids),
        "owner_focus": owner_focus,
    }
    if frozen_representation_versions is not None:
        payload["frozen_representation_versions"] = list(frozen_representation_versions)
    return canonical_sha256(payload)


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
    # Empty/incomplete market is not a scientific admission digest.
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
    representation_id: str | None = None,
    representation_semantic_version: str | None = None,
) -> list[Mapping[str, Any]]:
    """Sessions that consume scientific budget for the current market epoch."""

    matched: list[Mapping[str, Any]] = []
    for item in sessions:
        if not session_matches_market_epoch(item, market_evidence_epoch):
            continue
        if representation_id is not None:
            observed = representation_identity_from_session(item)
            wanted = (str(representation_id), str(representation_semantic_version or ""))
            if observed != wanted:
                # A split-era BASE row may have a market stamp but no new slot
                # fields. It still occupies the known BASE market look.
                if not (
                    wanted[0] == BASE_REPRESENTATION_ID
                    and observed == (None, None)
                ):
                    continue
        matched.append(item)
    return matched


def session_matches_market_epoch(
    session: Mapping[str, Any], market_evidence_epoch: str
) -> bool:
    """True when session occupies budget for this market epoch.

    Fail-closed: only an explicit ``market_evidence_epoch_sha256`` stamp matches.
    Legacy combined ``evidence_epoch_sha256`` alone never admits or budgets;
    use ``classify_legacy_session_disposition`` for historical readback.
    """

    stamped = session.get("market_evidence_epoch_sha256")
    if isinstance(stamped, str) and len(stamped) == 64:
        return stamped == market_evidence_epoch
    return False


def session_matches_epoch_for_lookup(
    session: Mapping[str, Any], epoch: str
) -> bool:
    """Exact resume/lookup match.

    Prefer market stamp. Unstamped pre-split sessions may match on
    ``evidence_epoch_sha256`` for exact-bytes resume only — never via budget
    counters (``sessions_for_market_budget``).
    """

    if session_matches_market_epoch(session, epoch):
        return True
    stamped = session.get("market_evidence_epoch_sha256")
    if isinstance(stamped, str) and stamped:
        return False
    return session.get("evidence_epoch_sha256") == epoch


__all__ = [
    "CAPABILITY_BASIS_VERSION",
    "BASE_REPRESENTATION_ID",
    "BASE_REPRESENTATION_VERSION",
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
    "session_scientific_slot_sha256",
    "representation_identity_from_session",
    "resolve_scientific_admission",
    "session_matches_epoch_for_lookup",
    "session_matches_market_epoch",
    "sessions_for_market_budget",
]
