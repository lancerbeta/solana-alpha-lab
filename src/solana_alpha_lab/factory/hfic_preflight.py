"""HFIC preflight: commissioning proof, evidence epoch, and session budget."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import yaml

from solana_alpha_lab.factory.commissioning_fixture import (
    COMMISSIONING_DATASET_MANIFEST_ID,
    commissioning_dataset_fingerprint,
)
from solana_alpha_lab.factory.early_market_panel_importer import (
    CLOSED_FAMILY,
    MIN_USABLE_YIELD_ELIGIBLE,
    SAMPLE_INVALID,
    is_link_path,
)
from solana_alpha_lab.factory.commissioning_proof import (
    CommissioningProofError,
    apply_legacy_commissioning_hypothesis_link,
    prove_fast_lane_commissioned as _prove_fast_lane_commissioned,
)
from solana_alpha_lab.factory.hfic_clock import (
    Clock,
    HficClockError,
    capture_stage_time,
    render_canonical_utc,
)
from solana_alpha_lab.factory.hfic_provenance import is_hfic_record
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
from solana_alpha_lab.factory.hfic_suppression_semantics import (
    classify_source_payload,
    dedupe_suppression_ledger,
)
from solana_alpha_lab.factory.research_store import (
    RESEARCH_PROJECTION_LOCATION,
    RecordKind,
    ResearchEvent,
    ResearchStore,
    ResearchStoreError,
)
from solana_alpha_lab.factory.run_passport import canonical_json_bytes, canonical_sha256
from solana_alpha_lab.contracts.schema_v1 import DatasetManifest, PartitionManifest


AUTO_FOCUS = "AUTO"
AUTO_SESSIONS_PER_EPOCH = 1
MAX_DISTINCT_FOCUSES_PER_EPOCH = 3
MAX_RANKED_PRIORS = 8
MAX_DATASETS = 8
MAX_FEATURE_HINTS = 8
MAX_CLOSED_FAMILIES = 8
MAX_CAPABILITIES = 16
MAX_PACKET_BYTES = 16384
FORGE_CONTEXT_ARTIFACT_DIR = "research/artifacts/forge_context"
FORGE_CONTEXT_ARTIFACT_KIND = "FORGE_CONTEXT_PACKET"
CAPABILITY_REGISTRY_RELATIVE = "configs/experiment_capability_registry_v1.yaml"
NEGATIVE_RESULTS_RELATIVE = "registries/decisions_negative_results.yaml"
CLOSED_FAMILY_ACCEPTANCE_RELATIVE = (
    "docs/evidence/early_valuation_liquidity_divergence_confirmation/"
    "a1_acceptance_v1.json"
)
_CLOSED_PARK_RE = re.compile(r"\b((?:CLOSE|PARK)_[A-Z0-9_]+)\b")
_TYPED_RUNTIME_RECEIPT_RE = re.compile(
    r"^smial\.[a-z0-9]+(?:[.-][a-z0-9]+)*\.runtime-receipt$"
)
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
        return _prove_fast_lane_commissioned(Path(data_root))
    except CommissioningProofError as exc:
        raise HficPreflightError(str(exc)) from exc


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
                try:
                    payload = json.loads(record.payload_json)
                except (ValueError, json.JSONDecodeError):
                    continue
                if not isinstance(payload, dict):
                    continue
                if is_hfic_record(record, payload):
                    continue
                prior_parts.append(f"{record.record_id}:{record.payload_sha256}")
        except ResearchStoreError:
            prior_parts = []
    prior_digest = hashlib.sha256(
        "\n".join(sorted(prior_parts)).encode("utf-8")
        if prior_parts
        else b"HFIC-EPOCH-CATALOG-BINDING-V1"
    ).hexdigest()
    dataset_manifest_ids = [COMMISSIONING_DATASET_MANIFEST_ID]
    dataset_fingerprints = [commissioning_dataset_fingerprint(root)]
    lifecycle_terminals = ["NO_GIT_FAST_LANE_PROVEN"]
    if data_root is not None:
        enumerated, _warnings = enumerate_rdp_datasets(Path(data_root))
        if enumerated:
            dataset_manifest_ids = [item["dataset_manifest_id"] for item in enumerated]
            dataset_fingerprints = [item["dataset_fingerprint"] for item in enumerated]
    lifecycle_terminals.extend(
        item["terminal"]
        for item in enumerate_closed_park_terminals(root, data_root)
    )
    lifecycle_terminals = list(dict.fromkeys(lifecycle_terminals))
    return {
        "catalog_root_hashes": hashes,
        "dataset_manifest_ids": dataset_manifest_ids,
        "dataset_fingerprints": dataset_fingerprints,
        "lifecycle_terminals": lifecycle_terminals,
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
        if state == "REVISION_REQUIRED":
            return ("RESUME_REVISE", session_id)
        if state == "AWAITING_CLASSIFICATION":
            return ("RESUME_CLASSIFY", session_id)
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


def _term_set(value: str) -> set[str]:
    return {token for token in value.casefold().replace("_", " ").replace("-", " ").split() if token}


def rank_prior_candidate_ids(
    store: ResearchStore,
    *,
    owner_focus: str,
    feature_hints: list[str],
    limit: int = MAX_RANKED_PRIORS,
) -> tuple[list[str], int]:
    focus_terms = _term_set(owner_focus)
    feature_terms = set()
    for hint in feature_hints:
        feature_terms.update(_term_set(hint))
    if feature_hints:
        feature_terms.update(
            {"taker", "volume", "mix", "valuation", "liquidity", "divergence"}
        )
    scored: list[tuple[int, str]] = []
    seen: set[str] = set()
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if kind != RecordKind.HYPOTHESIS_VERSION.value:
            continue
        payload = json.loads(record.payload_json)
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
        score = 3 * len(tokens & feature_terms) + 2 * len(tokens & focus_terms)
        scored.append((score, hyp_id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    kept = [item[1] for item in scored[:limit]]
    dropped = max(0, len(scored) - len(kept))
    return kept, dropped


def _is_symlink_path(path: Path) -> bool:
    return is_link_path(path)


def enumerate_rdp_datasets(
    data_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manifests_dir = Path(data_root) / "datasets" / "manifests"
    warnings: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    if not manifests_dir.is_dir():
        return [], warnings
    for path in sorted(manifests_dir.glob("*.json")):
        if path.name.endswith(".labels.json") or path.name.endswith(".decision.json"):
            continue
        canonical = bool(re.fullmatch(r"dataset-[0-9a-f]{64}\.json", path.name))
        stable = bool(re.fullmatch(r"[A-Z][A-Z0-9]+(?:-[A-Z0-9]+)*\.json", path.name))
        if not canonical and not stable:
            continue
        if _is_symlink_path(path):
            warnings.append(
                {
                    "code": "DATASET_MANIFEST_SYMLINK",
                    "dataset_manifest_id": path.stem,
                }
            )
            continue
        try:
            manifest = DatasetManifest.model_validate_json(path.read_bytes())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, Exception):
            if canonical:
                warnings.append(
                    {
                        "code": "DATASET_MANIFEST_CORRUPT",
                        "dataset_manifest_id": path.stem,
                    }
                )
            continue
        labels_path = manifests_dir / f"{manifest.dataset_manifest_id}.labels.json"
        labels: dict[str, Any] | None = None
        if labels_path.exists() or labels_path.is_symlink():
            if _is_symlink_path(labels_path):
                warnings.append(
                    {
                        "code": "DATASET_LABELS_SYMLINK",
                        "dataset_manifest_id": manifest.dataset_manifest_id,
                    }
                )
                continue
            try:
                loaded_labels = json.loads(labels_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                warnings.append(
                    {
                        "code": "DATASET_LABELS_CORRUPT",
                        "dataset_manifest_id": manifest.dataset_manifest_id,
                    }
                )
                continue
            if not isinstance(loaded_labels, dict):
                warnings.append(
                    {
                        "code": "DATASET_LABELS_CORRUPT",
                        "dataset_manifest_id": manifest.dataset_manifest_id,
                    }
                )
                continue
            labels = loaded_labels
        partition_dir = manifests_dir / "partitions"
        matching: list[Path] = []
        if partition_dir.is_dir():
            for part_path in sorted(partition_dir.glob("*.json")):
                if _is_symlink_path(part_path):
                    warnings.append(
                        {
                            "code": "PARTITION_MANIFEST_SYMLINK",
                            "dataset_manifest_id": manifest.dataset_manifest_id,
                        }
                    )
                    matching = []
                    break
                try:
                    part = PartitionManifest.model_validate_json(part_path.read_bytes())
                except (OSError, UnicodeDecodeError, json.JSONDecodeError, Exception):
                    continue
                if part.dataset_manifest_id == manifest.dataset_manifest_id:
                    matching.append(part_path)
                    parquet_path = Path(data_root) / part.logical_location
                    if (
                        not parquet_path.is_file()
                        or _is_symlink_path(parquet_path)
                        or hashlib.sha256(parquet_path.read_bytes()).hexdigest()
                        != part.file_sha256
                    ):
                        warnings.append(
                            {
                                "code": "DATASET_PARTITION_CORRUPT",
                                "dataset_manifest_id": manifest.dataset_manifest_id,
                            }
                        )
                        matching = []
                        break
        if not matching:
            if not any(
                item.get("dataset_manifest_id") == manifest.dataset_manifest_id
                and item.get("code") == "DATASET_PARTITION_CORRUPT"
                for item in warnings
            ):
                warnings.append(
                    {
                        "code": "DATASET_MANIFEST_PARTIAL",
                        "dataset_manifest_id": manifest.dataset_manifest_id,
                    }
                )
            continue
        evidence_role = "UNSPECIFIED"
        if labels is not None:
            role = labels.get("evidence_role")
            if isinstance(role, str) and role:
                evidence_role = role
        yield_eligible = int((labels or {}).get("yield_eligible") or 0)
        feature_usable = yield_eligible >= MIN_USABLE_YIELD_ELIGIBLE
        published_path = manifests_dir / f"{manifest.dataset_manifest_id}.published"
        if labels is not None:
            if not published_path.is_file() or _is_symlink_path(published_path):
                warnings.append(
                    {
                        "code": "DATASET_PUBLICATION_INCOMPLETE",
                        "dataset_manifest_id": manifest.dataset_manifest_id,
                    }
                )
                continue
            try:
                published = json.loads(published_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                warnings.append(
                    {
                        "code": "DATASET_PUBLICATION_CORRUPT",
                        "dataset_manifest_id": manifest.dataset_manifest_id,
                    }
                )
                continue
            if (
                not isinstance(published, dict)
                or published.get("dataset_fingerprint") != manifest.dataset_fingerprint
            ):
                warnings.append(
                    {
                        "code": "DATASET_PUBLICATION_MISMATCH",
                        "dataset_manifest_id": manifest.dataset_manifest_id,
                    }
                )
                continue
        dataset_terminal = (labels or {}).get("dataset_terminal")
        if not isinstance(dataset_terminal, str):
            dataset_terminal = (
                "SAMPLE_VALID" if feature_usable else SAMPLE_INVALID
            )
        entries.append(
            {
                "dataset_manifest_id": manifest.dataset_manifest_id,
                "dataset_fingerprint": manifest.dataset_fingerprint,
                "evidence_role": evidence_role,
                "labels": labels,
                "yield_eligible": yield_eligible,
                "yield_missing": int((labels or {}).get("yield_missing") or 0),
                "feature_usable": feature_usable,
                "dataset_terminal": dataset_terminal,
                "feature_hint": (labels or {}).get("feature_hint"),
            }
        )
    unique: dict[str, dict[str, Any]] = {}
    for item in entries:
        unique.setdefault(str(item["dataset_manifest_id"]), item)
    entries = list(unique.values())
    entries.sort(key=lambda item: item["dataset_manifest_id"])
    return entries, warnings


def enumerate_accepted_capabilities(repo_root: Path) -> list[dict[str, Any]]:
    path = Path(repo_root) / CAPABILITY_REGISTRY_RELATIVE
    if not path.is_file() or _is_symlink_path(path):
        raise HficPreflightError("CAPABILITY_REGISTRY_MISSING")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise HficPreflightError("CAPABILITY_REGISTRY_INVALID")
    rows = loaded.get("capabilities")
    if not isinstance(rows, list):
        raise HficPreflightError("CAPABILITY_REGISTRY_INVALID")
    entries: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if row.get("status") != "ACCEPTED":
            continue
        cap_id = row.get("capability_id")
        if not isinstance(cap_id, str) or not cap_id:
            continue
        entries.append(
            {
                "capability_id": cap_id,
                "effect_class": row.get("effect_class"),
                "supports_pit": bool(row.get("supports_pit")),
                "max_provider_calls": int(row.get("max_provider_calls") or 0),
            }
        )
    entries.sort(key=lambda item: item["capability_id"])
    return entries


def _dedupe_closed_families(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return dedupe_suppression_ledger(items)


def _is_rdp_closed_family_source(source: str) -> bool:
    return source.startswith("datasets/")


def select_closed_family_ledger_for_packet(
    items: list[dict[str, Any]],
    *,
    limit: int = MAX_CLOSED_FAMILIES,
) -> list[dict[str, Any]]:
    """Keep typed RDP hard-closes, then other hard-closes, then visible memory.

    Git scrape can already fill MAX_CLOSED_FAMILIES. Alphabetical truncation
    would otherwise drop an authoritative datasets/*.decision.json terminal.
    Owner-priority parks remain on the consumer packet even when hard-closes
    already occupy the cap: Prompt A / freeze read this packet, not the
    untruncated enumerator.
    """
    rdp_hard = [
        item
        for item in items
        if _is_rdp_closed_family_source(str(item.get("source_receipt") or ""))
        and item.get("reopen_forbidden") is True
    ]
    git_hard = [
        item
        for item in items
        if not _is_rdp_closed_family_source(str(item.get("source_receipt") or ""))
        and item.get("reopen_forbidden") is True
    ]
    visible = [item for item in items if item.get("reopen_forbidden") is not True]
    rdp_hard.sort(key=lambda item: str(item["terminal"]))
    git_hard.sort(key=lambda item: str(item["terminal"]))
    visible.sort(key=lambda item: str(item["terminal"]))
    if len(rdp_hard) >= limit:
        selected: list[dict[str, Any]] = list(rdp_hard)
    else:
        selected = list(rdp_hard)
        for item in git_hard:
            if len(selected) >= limit:
                break
            selected.append(item)
    seen = {str(item.get("terminal") or "") for item in selected}
    for item in visible:
        terminal = str(item.get("terminal") or "")
        if not terminal or terminal in seen:
            continue
        selected.append(item)
        seen.add(terminal)
    return selected


def enumerate_rdp_closed_family_terminals(data_root: Path) -> list[dict[str, Any]]:
    datasets, _warnings = enumerate_rdp_datasets(Path(data_root))
    found: list[dict[str, Any]] = []
    manifests_dir = Path(data_root) / "datasets" / "manifests"
    for item in datasets:
        manifest_id = str(item.get("dataset_manifest_id") or "")
        if not manifest_id:
            continue
        decision_path = manifests_dir / f"{manifest_id}.decision.json"
        if not decision_path.is_file() or _is_symlink_path(decision_path):
            continue
        published_path = manifests_dir / f"{manifest_id}.published"
        if not published_path.is_file() or _is_symlink_path(published_path):
            continue
        try:
            decision = json.loads(decision_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(decision, dict):
            continue
        schema = decision.get("schema")
        if not isinstance(schema, str) or _TYPED_RUNTIME_RECEIPT_RE.fullmatch(schema) is None:
            continue
        terminal = decision.get("scientific_terminal")
        if not isinstance(terminal, str) or _CLOSED_PARK_RE.fullmatch(terminal) is None:
            continue
        if decision.get("outcome_consumed") is not True:
            continue
        if decision.get("dataset_fingerprint") != item.get("dataset_fingerprint"):
            continue
        source = f"datasets/manifests/{manifest_id}.decision.json"
        found.append(classify_source_payload(decision, terminal=terminal, source_receipt=source))
    return found


def enumerate_closed_park_terminals(
    repo_root: Path,
    data_root: Path | None = None,
) -> list[dict[str, Any]]:
    root = Path(repo_root)
    found: dict[tuple[str, str], dict[str, Any]] = {}

    def _add(terminal: str, source: str, payload: Mapping[str, Any] | None) -> None:
        if _CLOSED_PARK_RE.fullmatch(terminal) is None:
            return
        key = (terminal, source)
        found[key] = classify_source_payload(
            payload,
            terminal=terminal,
            source_receipt=source,
        )

    registry = root / NEGATIVE_RESULTS_RELATIVE
    if registry.is_file() and not _is_symlink_path(registry):
        loaded = yaml.safe_load(registry.read_text(encoding="utf-8"))
        records = loaded.get("records") if isinstance(loaded, Mapping) else None
        if isinstance(records, list):
            for row in records:
                if not isinstance(row, Mapping):
                    continue
                blob = " ".join(
                    str(row.get(key) or "")
                    for key in ("record_id", "summary", "status")
                )
                for match in _CLOSED_PARK_RE.findall(blob):
                    _add(match, NEGATIVE_RESULTS_RELATIVE, row)
    evidence_root = root / "docs" / "evidence"
    for path in sorted(evidence_root.rglob("*acceptance*.json")) if evidence_root.is_dir() else []:
        if _is_symlink_path(path) or not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, Mapping):
            continue
        relative = path.relative_to(root).as_posix()
        for key in (
            "scientific_terminal",
            "verdict",
            "owner_decision",
            "product_terminal",
            "confirmatory_scientific_terminal",
            "runtime_terminal",
            "terminal",
        ):
            value = payload.get(key)
            if isinstance(value, str):
                _add(value, relative, payload)
    if data_root is not None:
        for item in enumerate_rdp_closed_family_terminals(Path(data_root)):
            found[(str(item["terminal"]), str(item["source_receipt"]))] = dict(item)
    return _dedupe_closed_families(list(found.values()))


def _forge_context_blob_path(data_root: Path, digest: str) -> Path:
    return Path(data_root) / FORGE_CONTEXT_ARTIFACT_DIR / f"{digest}.json"


def _lookup_forge_context_artifact(
    store: ResearchStore,
    digest: str,
) -> dict[str, Any] | None:
    for record in store.iter_committed_records():
        kind = getattr(record.record_kind, "value", record.record_kind)
        if kind != RecordKind.RESEARCH_ARTIFACT.value:
            continue
        payload = json.loads(record.payload_json)
        if payload.get("artifact_kind") != FORGE_CONTEXT_ARTIFACT_KIND:
            continue
        if payload.get("payload_sha256") != digest:
            continue
        return payload
    return None


def persist_forge_context_packet(
    data_root: Path,
    packet: Mapping[str, Any],
    *,
    store: ResearchStore | None = None,
    repo_root: Path | None = None,
    stage_time: datetime | None = None,
    clock: Clock | None = None,
) -> str:
    body = canonical_json_bytes(packet)
    digest = hashlib.sha256(body).hexdigest()
    if digest != canonical_sha256(packet):
        raise HficPreflightError("FORGE_CONTEXT_CANONICALIZER_DRIFT")
    blob = _forge_context_blob_path(data_root, digest)
    if blob.is_symlink():
        raise HficPreflightError("FORGE_CONTEXT_ARTIFACT_INVALID")
    blob.parent.mkdir(parents=True, exist_ok=True)
    if blob.is_file():
        if blob.read_bytes() != body:
            raise HficPreflightError("FORGE_CONTEXT_HASH_CONFLICT")
    else:
        blob.write_bytes(body)
    active = store if store is not None else ResearchStore(Path(data_root))
    existing = _lookup_forge_context_artifact(active, digest)
    if existing is not None:
        raw = existing.get("payload_canonical")
        if not isinstance(raw, str) or raw.encode("utf-8") != body:
            raise HficPreflightError("FORGE_CONTEXT_HASH_CONFLICT")
        return digest
    try:
        now = stage_time if stage_time is not None else capture_stage_time(clock)
        render_canonical_utc(now)
    except HficClockError as exc:
        raise HficPreflightError(str(exc)) from exc
    git_sha = "0" * 40
    if repo_root is not None:
        from solana_alpha_lab.factory.document_runner import repository_git_snapshot

        git_sha = repository_git_snapshot(Path(repo_root)).head_sha.lower()
    artifact_payload = {
        "research_artifact_id": f"HFIC-ART-FORGE-CONTEXT-{digest[:16].upper()}",
        "hfic_protocol": PROMPT_VERSION,
        "artifact_kind": FORGE_CONTEXT_ARTIFACT_KIND,
        "payload_canonical": body.decode("utf-8"),
        "payload_sha256": digest,
    }
    payload_json = json.dumps(
        artifact_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    transaction_id = f"RESEARCH-TXN-FORGECTX-{digest[:16].upper()}"
    event = ResearchEvent(
        record_id=f"HFIC-ART-FORGE-CONTEXT-{digest[:16].upper()}",
        record_kind=RecordKind.RESEARCH_ARTIFACT,
        entity_id=f"HFIC-ART-FORGE-CONTEXT-{digest[:16].upper()}",
        hypothesis_version_id=None,
        run_id=None,
        transaction_id=transaction_id,
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        producer_git_sha=git_sha,
        created_at=now,
    )
    active.append([event], transaction_id=transaction_id)
    active.rebuild_projection()
    return digest


def verify_forge_context_packet(data_root: Path, digest: str) -> dict[str, Any]:
    if not isinstance(digest, str) or len(digest) != 64:
        raise HficPreflightError("FORGE_CONTEXT_HASH_MISMATCH")
    blob = _forge_context_blob_path(data_root, digest)
    if blob.is_symlink():
        raise HficPreflightError("FORGE_CONTEXT_ARTIFACT_INVALID")
    if not blob.is_file():
        raise HficPreflightError("FORGE_CONTEXT_ARTIFACT_MISSING")
    body = blob.read_bytes()
    if hashlib.sha256(body).hexdigest() != digest:
        raise HficPreflightError("FORGE_CONTEXT_HASH_MISMATCH")
    try:
        loaded = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HficPreflightError("FORGE_CONTEXT_ARTIFACT_INVALID") from exc
    if not isinstance(loaded, dict):
        raise HficPreflightError("FORGE_CONTEXT_ARTIFACT_INVALID")
    if canonical_sha256(loaded) != digest:
        raise HficPreflightError("FORGE_CONTEXT_HASH_MISMATCH")
    try:
        store = ResearchStore(Path(data_root))
        artifact = _lookup_forge_context_artifact(store, digest)
    except ResearchStoreError as exc:
        raise HficPreflightError("FORGE_CONTEXT_ARTIFACT_MISSING") from exc
    if artifact is None:
        raise HficPreflightError("FORGE_CONTEXT_ARTIFACT_MISSING")
    raw = artifact.get("payload_canonical")
    if not isinstance(raw, str):
        raise HficPreflightError("FORGE_CONTEXT_ARTIFACT_INVALID")
    if hashlib.sha256(raw.encode("utf-8")).hexdigest() != digest:
        raise HficPreflightError("FORGE_CONTEXT_HASH_MISMATCH")
    return loaded


def build_forge_context_packet(
    repo_root: Path,
    data_root: Path,
    *,
    owner_focus: str,
    evidence_epoch: str,
    search_key: str,
    commissioning_status: str,
    research_memory_as_of: str,
    store: ResearchStore,
    stage_time: datetime | None = None,
    clock: Clock | None = None,
) -> tuple[dict[str, Any], str]:
    datasets, warnings = enumerate_rdp_datasets(Path(data_root))
    if not datasets:
        datasets = [
            {
                "dataset_manifest_id": COMMISSIONING_DATASET_MANIFEST_ID,
                "dataset_fingerprint": commissioning_dataset_fingerprint(repo_root),
                "evidence_role": "COMMISSIONING_FIXTURE",
                "labels": None,
                "yield_eligible": 0,
                "yield_missing": 0,
                "feature_usable": False,
                "dataset_terminal": None,
                "feature_hint": None,
            }
        ]
    capabilities = enumerate_accepted_capabilities(repo_root)
    closed_family_ledger = enumerate_closed_park_terminals(repo_root, data_root)
    if not any(item["terminal"] == CLOSED_FAMILY for item in closed_family_ledger):
        closed_family_ledger.append(
            classify_source_payload(
                {
                    "scientific_terminal": CLOSED_FAMILY,
                    "verdict": CLOSED_FAMILY,
                    "family_close": True,
                },
                terminal=CLOSED_FAMILY,
                source_receipt=CLOSED_FAMILY_ACCEPTANCE_RELATIVE,
            )
        )
        closed_family_ledger.sort(
            key=lambda item: (item["terminal"], item["source_receipt"])
        )
    feature_hints: list[dict[str, Any]] = []
    for item in datasets:
        hint_id = item.get("feature_hint")
        if not isinstance(hint_id, str) or not hint_id:
            continue
        usable = bool(item.get("feature_usable"))
        feature_hints.append(
            {
                "feature_id": hint_id,
                "availability": "R0_ONLY" if usable else "UNAVAILABLE",
                "usable": usable,
                "yield_eligible": item["yield_eligible"],
                "yield_missing": item["yield_missing"],
                "evidence_role": item["evidence_role"],
                "dataset_terminal": item.get("dataset_terminal"),
                "confirmatory_reuse_forbidden": bool(
                    (item.get("labels") or {}).get("confirmatory_reuse_forbidden")
                ),
                "accepted_hypothesis_id": (item.get("labels") or {}).get(
                    "accepted_hypothesis_id"
                ),
            }
        )
    feature_hints.sort(key=lambda item: (str(item["feature_id"]), str(item.get("dataset_terminal") or "")))
    usable_hint_ids = [
        str(item["feature_id"]) for item in feature_hints if item.get("usable")
    ]
    ranked, dropped_priors = rank_prior_candidate_ids(
        store,
        owner_focus=owner_focus,
        feature_hints=usable_hint_ids,
    )
    truth_roots = [
        "catalog/catalog_manifest.yaml",
        "configs/hypothesis_forge_independent_critic_v1.yaml",
        CAPABILITY_REGISTRY_RELATIVE,
        NEGATIVE_RESULTS_RELATIVE,
    ]
    prior_work_receipts = [
        "QUERY-HFIC-EXACT-RELATED-PRIOR-001",
        "QUERY-HFIC-SESSION-BY-SEARCH-KEY-001",
        "QUERY-HFIC-PENDING-SESSION-001",
        *ranked,
    ][:8]
    truncation = {
        "truncated": False,
        "kept_priors": len(ranked),
        "dropped_priors": dropped_priors,
        "tie_break": "stable_id_asc",
        "max_priors": MAX_RANKED_PRIORS,
        "max_datasets": MAX_DATASETS,
        "max_closed_families": MAX_CLOSED_FAMILIES,
        "max_feature_hints": MAX_FEATURE_HINTS,
        "max_capabilities": MAX_CAPABILITIES,
        "max_packet_bytes": MAX_PACKET_BYTES,
    }
    if len(datasets) > MAX_DATASETS:
        datasets = datasets[:MAX_DATASETS]
        truncation["truncated"] = True
    if len(feature_hints) > MAX_FEATURE_HINTS:
        feature_hints = feature_hints[:MAX_FEATURE_HINTS]
        truncation["truncated"] = True
    if len(capabilities) > MAX_CAPABILITIES:
        capabilities = capabilities[:MAX_CAPABILITIES]
        truncation["truncated"] = True
    packet_ledger = select_closed_family_ledger_for_packet(closed_family_ledger)
    if len(packet_ledger) < len(closed_family_ledger):
        truncation["truncated"] = True
        truncation["dropped_closed_families"] = len(closed_family_ledger) - len(
            packet_ledger
        )
        truncation["kept_rdp_closed_families"] = sum(
            1
            for item in packet_ledger
            if _is_rdp_closed_family_source(str(item.get("source_receipt") or ""))
        )
        packet_terminals = {str(item.get("terminal") or "") for item in packet_ledger}
        truncation["dropped_visible_prior_work"] = sum(
            1
            for item in closed_family_ledger
            if item.get("reopen_forbidden") is not True
            and str(item.get("terminal") or "") not in packet_terminals
        )
    closed_family_ledger = packet_ledger
    if dropped_priors:
        truncation["truncated"] = True
    if warnings:
        truncation["context_warnings"] = len(warnings)
    packet = {
        "prompt_version": PROMPT_VERSION,
        "owner_focus": owner_focus,
        "evidence_epoch_sha256": evidence_epoch,
        "search_key_sha256": search_key,
        "related_prior_recipe_ids": [
            "QUERY-HFIC-EXACT-RELATED-PRIOR-001",
            "QUERY-HFIC-SESSION-BY-SEARCH-KEY-001",
            "QUERY-HFIC-PENDING-SESSION-001",
        ],
        "truth_roots_used": truth_roots,
        "commissioning_status": commissioning_status,
        "research_memory_as_of": research_memory_as_of,
        "prior_work_receipts": prior_work_receipts,
        "dataset_manifest_ids": [item["dataset_manifest_id"] for item in datasets],
        "dataset_fingerprints": [item["dataset_fingerprint"] for item in datasets],
        "dataset_entries": [
            {
                "dataset_manifest_id": item["dataset_manifest_id"],
                "dataset_fingerprint": item["dataset_fingerprint"],
                "evidence_role": item["evidence_role"],
            }
            for item in datasets
        ],
        "capability_ids": [item["capability_id"] for item in capabilities],
        "capability_entries": capabilities,
        "feature_hints": feature_hints,
        "closed_family_ledger": closed_family_ledger,
        "context_warnings": warnings,
        "ranked_prior_candidate_ids": ranked,
        "truncation_receipt": truncation,
    }
    encoded = canonical_json_bytes(packet)
    if len(encoded) > MAX_PACKET_BYTES:
        packet["ranked_prior_candidate_ids"] = ranked[:3]
        packet["prior_work_receipts"] = prior_work_receipts[:5]
        packet["truncation_receipt"] = {
            **truncation,
            "truncated": True,
            "kept_priors": min(3, len(ranked)),
            "reason": "MAX_PACKET_BYTES",
        }
        encoded = canonical_json_bytes(packet)
        if len(encoded) > MAX_PACKET_BYTES:
            raise HficPreflightError("PACKET_SIZE_EXCEEDED")
    digest = persist_forge_context_packet(
        data_root,
        packet,
        store=store,
        repo_root=repo_root,
        stage_time=stage_time,
        clock=clock,
    )
    verify_forge_context_packet(data_root, digest)
    return packet, digest


def run_preflight(
    repo_root: Path,
    data_root: Path,
    *,
    owner_focus: str,
    auto_commission: bool,
    commission_fn: Callable[[Path, Path], Mapping[str, Any]] | None = None,
    git_snapshot: Mapping[str, Any] | None = None,
    clock: Clock | None = None,
) -> dict[str, Any]:
    compatibility_repair: dict[str, Any] = {"status": "NONE", "appended": 0}
    try:
        proof = prove_fast_lane_commissioned(data_root)
        commissioned_now = False
    except HficPreflightError as exc:
        code = str(exc)
        if code == "COMMISSION_HYPOTHESIS_VERSION_MISSING":
            try:
                now = capture_stage_time(clock)
            except HficClockError as clock_exc:
                raise HficPreflightError(str(clock_exc)) from clock_exc
            try:
                repair = apply_legacy_commissioning_hypothesis_link(
                    Path(data_root),
                    now=now,
                )
            except CommissioningProofError as repair_exc:
                raise HficPreflightError(str(repair_exc)) from repair_exc
            compatibility_repair = {
                "status": str(repair.get("status") or "NONE"),
                "appended": int(repair.get("appended") or 0),
            }
            if compatibility_repair["status"] == "NO_REPAIRABLE_CANDIDATE":
                raise HficPreflightError("COMMISSION_HYPOTHESIS_VERSION_MISSING")
            proof = prove_fast_lane_commissioned(data_root)
            commissioned_now = False
        elif (
            auto_commission
            and commission_fn is not None
            and code == "FAST_LANE_NOT_COMMISSIONED"
        ):
            commission_fn(Path(repo_root), Path(data_root))
            proof = prove_fast_lane_commissioned(data_root)
            commissioned_now = True
        elif not auto_commission or commission_fn is None:
            raise HficPreflightError("FAST_LANE_NOT_COMMISSIONABLE")
        else:
            raise

    try:
        store = ResearchStore(Path(data_root))
        store.rebuild_projection()
        digest = store.diagnostics().committed_inventory_sha256
    except ResearchStoreError as exc:
        raise HficPreflightError(str(exc)) from exc

    try:
        session_started = capture_stage_time(clock)
        session_started_text = render_canonical_utc(session_started)
    except HficClockError as exc:
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
        "data_root_fingerprint_sha256": digest,
        "research_memory_as_of": str(
            proof.get("research_memory_as_of") or "2026-08-25T00:00:00Z"
        ),
        "session_started_at": session_started_text,
        "session_id": bound_session if action != "STOP" else None,
        "commissioning": {
            "status": proof["status"],
            "auto_commissioned": commissioned_now,
            "provider_calls_actual": int(proof.get("provider_calls_actual") or 0),
            "git_mutation_count": int(proof.get("git_mutation_count") or 0),
            "run_id": proof.get("run_id"),
            "compatibility_repair": compatibility_repair,
        },
        "forge_context_packet": {},
        "authority": {
            "git_mutation": 0,
            "experiment_execution": 0,
            "provider_api_rpc_wss_calls": 0,
        },
    }
    if action == "STOP" and bound_session == "SEARCH_BUDGET_EXHAUSTED":
        receipt_body["terminal"] = "SEARCH_BUDGET_EXHAUSTED"
        receipt_body["session_id"] = None
    packet, packet_digest = build_forge_context_packet(
        repo_root,
        data_root,
        owner_focus=focus,
        evidence_epoch=epoch,
        search_key=search_key,
        commissioning_status=str(proof["status"]),
        research_memory_as_of=str(
            proof.get("research_memory_as_of") or "2026-08-25T00:00:00Z"
        ),
        store=store,
        stage_time=session_started,
    )
    receipt_body["forge_context_packet"] = packet
    receipt_body["forge_context_packet_sha256"] = packet_digest
    try:
        digest = store.diagnostics().committed_inventory_sha256
    except ResearchStoreError as exc:
        raise HficPreflightError(str(exc)) from exc
    receipt_body["store_inventory_digest"] = digest
    receipt_body["data_root_fingerprint_sha256"] = digest
    if bound_session and action in {
        "RESUME_CRITIC",
        "RESUME_FINALIZE",
        "RESUME_REVISE",
        "RESUME_CLASSIFY",
        "RETURN_EXISTING_SESSION",
    }:
        bundle = load_session_bundle(store, bound_session)
        if bundle is not None:
            actual_state = str(bundle.get("session_state") or "")
            if action == "RETURN_EXISTING_SESSION" and actual_state != "SYNTHESIS_COMPLETE":
                if actual_state == "REVISION_REQUIRED":
                    action = "RESUME_REVISE"
                elif actual_state == "AWAITING_CLASSIFICATION":
                    action = "RESUME_CLASSIFY"
                elif actual_state == "CRITIC_RESULT_READY":
                    action = "RESUME_FINALIZE"
                else:
                    action = "RESUME_CRITIC"
                receipt_body["action"] = action
            if bundle.get("critic_input_packet"):
                receipt_body["critic_input_packet"] = bundle["critic_input_packet"]
                receipt_body["critic_input_packet_sha256"] = bundle.get(
                    "critic_input_packet_sha256"
                )
            if action in {"RESUME_FINALIZE", "RESUME_CLASSIFY"} and bundle.get(
                "critic_result"
            ):
                receipt_body["critic_result"] = bundle["critic_result"]
            if action == "RETURN_EXISTING_SESSION":
                receipt_body["session_state"] = bundle.get("session_state")
                receipt_body["critic_terminal"] = bundle.get("critic_terminal")
                receipt_body["next"] = bundle.get("next")
    receipt_body["preflight_receipt_sha256"] = canonical_sha256(receipt_body)
    return receipt_body
