"""Derived science→strategy handoff. Owns no durable truth."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import jsonschema

from solana_alpha_lab.factory.strategy_runtime import (
    canonical_spec_sha256,
    validate_and_hash_strategy,
)


SCHEMA_RELATIVE = "catalog/schemas/promotion_handoff_manifest_v1.schema.json"
STRATEGY_ROOT = "configs/strategies"
MANIFEST_SCHEMA = "smial.promotion-handoff-manifest"
HANDOFF_SCHEMA = "smial.science-to-strategy-handoff"
STATES = (
    "NOT_PROMOTED",
    "BLOCKED",
    "READY_TO_MATERIALIZE",
    "MATERIALIZED",
    "CONFLICT",
)
BLOCKER_CODES = (
    "LEGACY_PROVENANCE_GAP",
    "HANDOFF_MANIFEST_INVALID",
    "EXPERIMENT_SPEC_BINDING_GAP",
    "EVIDENCE_RELATION_GAP",
    "EVIDENCE_HASH_CONFLICT",
    "EXECUTION_INPUT_GAP",
    "STRATEGY_IDENTITY_CONFLICT",
    "STRATEGY_CONTENT_CONFLICT",
    "SOURCE_UNAVAILABLE",
)
FIXED_SIGNAL_CONTRACT = "smial.signal-decision"
FIXED_SIGNAL_VERSION = "1.0"
FIXED_EXIT_CONTRACT = "smial.exit-decision"
FIXED_EXIT_VERSION = "1.0"
FIXED_AUTHORITY_CLASS = "PAPER_SHADOW_ONLY"
REQUIRED_EXECUTION_INPUTS = (
    "max_age_seconds",
    "notional_usd",
    "fee_bps",
    "max_open_positions",
    "shadow",
)
FIELD_PROVENANCE = {
    "source_decision_asset_id": "SCIENCE_DERIVED",
    "source_hypothesis_refs": "SCIENCE_DERIVED",
    "population_ref": "SCIENCE_DERIVED",
    "title": "SCIENCE_DERIVED",
    "strategy_id": "SCIENCE_DERIVED",
    "strategy_version": "SCIENCE_DERIVED",
    "signal_input.contract": "EXECUTION_CONTRACT_FIXED",
    "signal_input.contract_version": "EXECUTION_CONTRACT_FIXED",
    "signal_input.enter_actions": "EXECUTION_CONTRACT_FIXED",
    "exit_input.contract": "EXECUTION_CONTRACT_FIXED",
    "exit_input.contract_version": "EXECUTION_CONTRACT_FIXED",
    "mode_eligibility.paper": "EXECUTION_CONTRACT_FIXED",
    "mode_eligibility.micro_live": "EXECUTION_CONTRACT_FIXED",
    "authority_class": "EXECUTION_CONTRACT_FIXED",
    "signal_input.max_age_seconds": "EXPLICIT_EXECUTION_INPUT",
    "notional_policy.notional_usd": "EXPLICIT_EXECUTION_INPUT",
    "notional_policy.fee_bps": "EXPLICIT_EXECUTION_INPUT",
    "risk_policy.max_open_positions": "EXPLICIT_EXECUTION_INPUT",
    "mode_eligibility.shadow": "EXPLICIT_EXECUTION_INPUT",
    "created_at": "SCIENCE_DERIVED",
    "schema": "EXECUTION_CONTRACT_FIXED",
    "schema_version": "EXECUTION_CONTRACT_FIXED",
}


class PromotionHandoffError(ValueError):
    """Fail-closed handoff / materialization error."""


def canonical_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_dumps(value).encode("utf-8")).hexdigest()


def _load_schema(root: Path) -> dict[str, Any]:
    path = root / SCHEMA_RELATIVE
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise PromotionHandoffError("HANDOFF_MANIFEST_SCHEMA_INVALID")
    return loaded


def unsigned_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in dict(manifest).items() if key != "manifest_sha256"}


def manifest_sha256(manifest: Mapping[str, Any]) -> str:
    return _sha256_json(unsigned_manifest(manifest))


def validate_promotion_handoff_manifest(
    manifest: Mapping[str, Any],
    *,
    root: Path,
) -> dict[str, Any]:
    if not isinstance(manifest, Mapping):
        raise PromotionHandoffError("HANDOFF_MANIFEST_INVALID")
    try:
        jsonschema.validate(dict(manifest), _load_schema(root))
    except jsonschema.ValidationError as exc:
        raise PromotionHandoffError("HANDOFF_MANIFEST_INVALID") from exc
    claimed = str(manifest.get("manifest_sha256") or "")
    actual = manifest_sha256(manifest)
    if claimed != actual:
        raise PromotionHandoffError("HANDOFF_MANIFEST_INVALID")
    return dict(manifest)


def freeze_promotion_handoff_manifest(
    dossier: Mapping[str, Any],
    *,
    root: Path,
) -> dict[str, Any]:
    locator = dossier.get("locator") if isinstance(dossier.get("locator"), Mapping) else {}
    tested = dossier.get("tested") if isinstance(dossier.get("tested"), Mapping) else {}
    binding = (
        dossier.get("experiment_spec_binding")
        if isinstance(dossier.get("experiment_spec_binding"), Mapping)
        else {}
    )
    experiment_id = _text(locator.get("entity_id"))
    hypothesis_version_id = _text(tested.get("hypothesis_version_id"))
    source_kind = _text(binding.get("source_kind"))
    source_value = _text(binding.get("source_value"))
    spec_digest = _text(binding.get("spec_sha256"))
    snapshot = _text(dossier.get("evidence_snapshot_sha256"))
    population = tested.get("population")
    population_ref = _text(population) if isinstance(population, str) else None
    if (
        not experiment_id
        or not hypothesis_version_id
        or source_kind != "git_path"
        or not source_value
        or not spec_digest
        or not snapshot
        or not population_ref
    ):
        raise PromotionHandoffError("EXPERIMENT_SPEC_BINDING_GAP")
    direct: list[dict[str, str]] = []
    for card in dossier.get("direct_evidence") or []:
        if not isinstance(card, Mapping):
            continue
        record_id = _text(card.get("record_id"))
        payload_digest = _text(card.get("payload_sha256"))
        if not record_id or not payload_digest:
            raise PromotionHandoffError("EVIDENCE_RELATION_GAP")
        direct.append({"record_id": record_id, "payload_sha256": payload_digest})
    if not direct:
        raise PromotionHandoffError("EVIDENCE_RELATION_GAP")
    direct.sort(key=lambda item: item["record_id"])
    obligations = [
        {"code": str(item.get("code") or ""), "status": str(item.get("status") or "")}
        for item in dossier.get("obligations") or []
        if isinstance(item, Mapping) and item.get("code")
    ]
    obligations.sort(key=lambda item: item["code"])
    if not obligations:
        raise PromotionHandoffError("EVIDENCE_RELATION_GAP")
    packet = _text(dossier.get("promotion_packet_sha256"))
    unsigned = {
        "schema": MANIFEST_SCHEMA,
        "schema_version": "1.0",
        "experiment_id": experiment_id,
        "hypothesis_version_id": hypothesis_version_id,
        "experiment_spec_source_kind": "git_path",
        "experiment_spec_source_value": source_value,
        "experiment_spec_sha256": spec_digest,
        "evidence_snapshot_sha256": snapshot,
        "direct_evidence": direct,
        "obligations": obligations,
        "promotion_packet_sha256": packet,
        "population_ref": population_ref,
    }
    frozen = dict(unsigned)
    frozen["manifest_sha256"] = manifest_sha256(unsigned)
    return validate_promotion_handoff_manifest(frozen, root=root)


def strategy_id_from_experiment(experiment_id: str) -> str:
    raw = experiment_id.strip()
    if raw.startswith("EXP-"):
        rest = raw[4:]
    else:
        rest = raw
    candidate = f"STRAT-{rest}"
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")
    if not candidate.startswith("STRAT-") or any(ch not in allowed for ch in candidate):
        raise PromotionHandoffError("STRATEGY_IDENTITY_CONFLICT")
    return candidate


def _payload(record: Any) -> dict[str, Any]:
    raw = getattr(record, "payload_json", None)
    if isinstance(raw, str) and raw:
        try:
            loaded = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return loaded if isinstance(loaded, dict) else {}
    payload = getattr(record, "payload", None)
    return dict(payload) if isinstance(payload, Mapping) else {}


def _promote_records(records: Sequence[Any], experiment_id: str) -> list[Any]:
    out: list[Any] = []
    for record in records:
        kind = str(getattr(getattr(record, "record_kind", ""), "value", getattr(record, "record_kind", "")) or "")
        if kind != "DECISION_EVENT":
            continue
        payload = _payload(record)
        if payload.get("decision_kind") != "PROMOTE":
            continue
        if payload.get("target_entity_id") != experiment_id:
            continue
        out.append(record)
    out.sort(
        key=lambda item: (
            str(getattr(item, "effective_at", "") or ""),
            str(getattr(item, "record_id", "") or ""),
        )
    )
    return out


def _created_at(record: Any) -> str:
    stamp = getattr(record, "effective_at", None)
    text = str(stamp or "")
    if hasattr(stamp, "strftime"):
        text = stamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    if text.endswith("+00:00"):
        text = text[:-6] + "Z"
    if "." in text and text.endswith("Z"):
        text = text.split(".", 1)[0] + "Z"
    return text


def _iter_strategy_files(root: Path) -> list[str]:
    directory = root / STRATEGY_ROOT
    if not directory.is_dir():
        return []
    out: list[str] = []
    for path in sorted(directory.glob("*.yaml")):
        rel = path.relative_to(root).as_posix()
        if Path(rel).is_absolute() or ".." in Path(rel).parts:
            continue
        out.append(rel)
    return out


def load_existing_strategies(root: Path) -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = []
    for relative in _iter_strategy_files(root):
        try:
            from solana_alpha_lab.factory.strategy_runtime import load_strategy_version

            loaded.append(load_strategy_version(root, relative))
        except Exception:  # noqa: BLE001
            continue
    return loaded


def _execution_gaps(inputs: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(inputs, Mapping):
        return ["EXECUTION_INPUT_GAP"]
    missing = [key for key in REQUIRED_EXECUTION_INPUTS if key not in inputs or inputs.get(key) is None]
    return ["EXECUTION_INPUT_GAP"] if missing else []


def _source_revalidation(
    manifest: Mapping[str, Any],
    records: Sequence[Any],
    records_status: str,
) -> tuple[str, list[str]]:
    if records_status in {"UNAVAILABLE", "INVALID"}:
        return "UNAVAILABLE", ["SOURCE_UNAVAILABLE"]
    by_id = {str(getattr(item, "record_id", "") or ""): item for item in records}
    notes: list[str] = []
    for ref in manifest.get("direct_evidence") or []:
        if not isinstance(ref, Mapping):
            continue
        record_id = str(ref.get("record_id") or "")
        expected = str(ref.get("payload_sha256") or "")
        current = by_id.get(record_id)
        if current is None:
            notes.append("SOURCE_UNAVAILABLE")
            continue
        actual = str(getattr(current, "payload_sha256", "") or "")
        if actual != expected:
            return "CONFLICT", ["EVIDENCE_HASH_CONFLICT"]
    if notes:
        return "UNAVAILABLE", ["SOURCE_UNAVAILABLE"]
    return "AVAILABLE", []


def _lookup_strategy(
    root: Path, strategy_id: str, strategy_version: str
) -> dict[str, Any] | None:
    for existing in load_existing_strategies(root):
        if str(existing.get("strategy_id")) != strategy_id:
            continue
        if str(existing.get("strategy_version")) != strategy_version:
            continue
        return existing
    return None


def _strategy_relation(
    *,
    root: Path,
    strategy_id: str,
    strategy_version: str,
    decision_event_id: str | None,
    candidate: Mapping[str, Any] | None,
) -> tuple[str | None, str | None, list[str]]:
    identity = f"{strategy_id}@{strategy_version}"
    existing = _lookup_strategy(root, strategy_id, strategy_version)
    if existing is None:
        return None, None, []
    if candidate is not None:
        unsigned_existing = {key: value for key, value in existing.items() if key != "spec_sha256"}
        unsigned_candidate = {key: value for key, value in dict(candidate).items() if key != "spec_sha256"}
        if canonical_dumps(unsigned_existing) == canonical_dumps(unsigned_candidate):
            return identity, "MATERIALIZED", []
        return identity, "CONFLICT", ["STRATEGY_CONTENT_CONFLICT"]
    source = str(existing.get("source_decision_asset_id") or "")
    if decision_event_id and source == decision_event_id:
        return identity, "MATERIALIZED", []
    return identity, "CONFLICT", ["STRATEGY_IDENTITY_CONFLICT"]


def check_materialization(
    *,
    root: Path,
    manifest: Mapping[str, Any],
    execution_inputs: Mapping[str, Any] | None,
    decision_event_id: str | None = None,
    existing_blockers: Sequence[str] | None = None,
) -> dict[str, Any]:
    strategy_id = strategy_id_from_experiment(str(manifest["experiment_id"]))
    blockers = list(existing_blockers or [])
    identity, state, collision = _strategy_relation(
        root=root,
        strategy_id=strategy_id,
        strategy_version="V1",
        decision_event_id=decision_event_id,
        candidate=None,
    )
    blockers.extend(collision)
    if state == "CONFLICT":
        return {
            "handoff_state": "CONFLICT",
            "blocker_codes": sorted(set(blockers)),
            "strategy_id": strategy_id,
            "strategy_version": "V1",
            "strategy_identity": f"{strategy_id}@V1",
        }
    if state == "MATERIALIZED":
        return {
            "handoff_state": "MATERIALIZED",
            "blocker_codes": [],
            "strategy_id": strategy_id,
            "strategy_version": "V1",
            "strategy_identity": identity,
        }
    blockers.extend(_execution_gaps(execution_inputs))
    if blockers:
        return {
            "handoff_state": "BLOCKED",
            "blocker_codes": sorted(set(blockers)),
            "strategy_id": strategy_id,
            "strategy_version": "V1",
            "strategy_identity": None,
        }
    return {
        "handoff_state": "READY_TO_MATERIALIZE",
        "blocker_codes": [],
        "strategy_id": strategy_id_from_experiment(str(manifest["experiment_id"])),
        "strategy_version": "V1",
        "strategy_identity": None,
    }


def render_strategy_version(
    *,
    root: Path,
    manifest: Mapping[str, Any],
    decision_event_id: str,
    created_at: str,
    execution_inputs: Mapping[str, Any],
) -> dict[str, Any]:
    gaps = _execution_gaps(execution_inputs)
    if gaps:
        raise PromotionHandoffError("EXECUTION_INPUT_GAP")
    validate_promotion_handoff_manifest(manifest, root=root)
    strategy_id = strategy_id_from_experiment(str(manifest["experiment_id"]))
    unsigned = {
        "schema": "smial.strategy-version",
        "schema_version": "1.1",
        "strategy_id": strategy_id,
        "strategy_version": "V1",
        "title": str(manifest["experiment_id"]),
        "source_decision_asset_id": decision_event_id,
        "source_hypothesis_refs": [str(manifest["hypothesis_version_id"])],
        "population_ref": str(manifest["population_ref"]),
        "signal_input": {
            "contract": FIXED_SIGNAL_CONTRACT,
            "contract_version": FIXED_SIGNAL_VERSION,
            "enter_actions": ["ENTER"],
            "max_age_seconds": int(execution_inputs["max_age_seconds"]),
        },
        "exit_input": {
            "contract": FIXED_EXIT_CONTRACT,
            "contract_version": FIXED_EXIT_VERSION,
        },
        "notional_policy": {
            "notional_usd": float(execution_inputs["notional_usd"]),
            "fee_bps": int(execution_inputs["fee_bps"]),
        },
        "risk_policy": {
            "max_open_positions": int(execution_inputs["max_open_positions"]),
        },
        "mode_eligibility": {
            "paper": True,
            "shadow": bool(execution_inputs["shadow"]),
            "micro_live": False,
        },
        "authority_class": FIXED_AUTHORITY_CLASS,
        "created_at": created_at,
    }
    candidate = dict(unsigned)
    candidate["spec_sha256"] = canonical_spec_sha256(unsigned)
    return verify_strategy_version(root, candidate)


def verify_strategy_version(root: Path, candidate: Mapping[str, Any]) -> dict[str, Any]:
    return validate_and_hash_strategy(root, candidate)


def materialize_strategy_candidate(
    *,
    root: Path,
    manifest: Mapping[str, Any],
    decision_event_id: str,
    created_at: str,
    execution_inputs: Mapping[str, Any] | None,
) -> dict[str, Any]:
    gaps = _execution_gaps(execution_inputs)
    if gaps:
        check = check_materialization(
            root=root,
            manifest=manifest,
            execution_inputs=execution_inputs,
            decision_event_id=decision_event_id,
        )
        return {**check, "candidate": None, "disposition": check["handoff_state"]}
    candidate = render_strategy_version(
        root=root,
        manifest=manifest,
        decision_event_id=decision_event_id,
        created_at=created_at,
        execution_inputs=execution_inputs or {},
    )
    identity, state, collision = _strategy_relation(
        root=root,
        strategy_id=str(candidate["strategy_id"]),
        strategy_version=str(candidate["strategy_version"]),
        decision_event_id=decision_event_id,
        candidate=candidate,
    )
    if state == "CONFLICT":
        return {
            "handoff_state": "CONFLICT",
            "blocker_codes": collision,
            "strategy_id": candidate["strategy_id"],
            "strategy_version": candidate["strategy_version"],
            "strategy_identity": identity,
            "candidate": None,
            "disposition": "CONFLICT",
        }
    if state == "MATERIALIZED":
        return {
            "handoff_state": "MATERIALIZED",
            "blocker_codes": [],
            "strategy_id": candidate["strategy_id"],
            "strategy_version": candidate["strategy_version"],
            "strategy_identity": identity,
            "candidate": candidate,
            "disposition": "REPLAY_IDENTICAL",
        }
    return {
        "handoff_state": "READY_TO_MATERIALIZE",
        "blocker_codes": [],
        "strategy_id": candidate["strategy_id"],
        "strategy_version": candidate["strategy_version"],
        "strategy_identity": None,
        "candidate": candidate,
        "disposition": "RENDERED",
        "field_provenance": dict(FIELD_PROVENANCE),
        "authority_granted": False,
        "activation_created": False,
    }


def compose_science_to_strategy_handoff(
    *,
    root: Path,
    experiment_id: str,
    records: Sequence[Any] | None,
    records_status: str,
    execution_inputs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    store_records = tuple(records or ())
    promotes = _promote_records(store_records, experiment_id)
    empty = {
        "schema": HANDOFF_SCHEMA,
        "schema_version": "1.0",
        "authority_granted": False,
        "activation_created": False,
        "identity": {
            "decision_event_id": None,
            "experiment_id": experiment_id,
            "hypothesis_version_id": None,
        },
        "science": {
            "decision_kind": None,
            "decision_effective_at": None,
            "evidence_snapshot_sha256": None,
            "handoff_manifest_sha256": None,
            "obligations": [],
        },
        "provenance": {
            "manifest_status": "ABSENT",
            "source_revalidation": "UNKNOWN",
            "direct_evidence": [],
            "experiment_spec_binding": None,
        },
        "materialization": {
            "strategy_relation": "ABSENT",
            "strategy_id": None,
            "strategy_version": None,
        },
        "state": {
            "handoff_state": "NOT_PROMOTED",
            "blocker_codes": [],
            "next_safe_action": "NO_SCIENTIFIC_PROMOTE",
        },
        "authority": {"authority_granted": False, "activation_created": False},
        "field_provenance": dict(FIELD_PROVENANCE),
    }
    if not promotes:
        if records_status in {"UNAVAILABLE", "INVALID"}:
            empty["state"] = {
                "handoff_state": "BLOCKED",
                "blocker_codes": ["SOURCE_UNAVAILABLE"],
                "next_safe_action": "RESOLVE_RESEARCH_STORE",
            }
            empty["provenance"]["source_revalidation"] = "UNAVAILABLE"
        return empty
    record = promotes[-1]
    payload = _payload(record)
    decision_event_id = str(
        payload.get("decision_event_id") or getattr(record, "record_id", "") or ""
    )
    snapshot = _text(payload.get("evidence_snapshot_sha256"))
    raw_manifest = payload.get("promotion_handoff_manifest")
    identity = {
        "decision_event_id": decision_event_id,
        "experiment_id": experiment_id,
        "hypothesis_version_id": payload.get("hypothesis_version_id"),
    }
    science = {
        "decision_kind": "PROMOTE",
        "decision_effective_at": _created_at(record),
        "evidence_snapshot_sha256": snapshot,
        "handoff_manifest_sha256": None,
        "obligations": [],
    }
    if not isinstance(raw_manifest, Mapping):
        return {
            **empty,
            "identity": identity,
            "science": science,
            "provenance": {
                "manifest_status": "LEGACY_ABSENT",
                "source_revalidation": "NOT_APPLICABLE",
                "direct_evidence": [],
                "experiment_spec_binding": None,
            },
            "state": {
                "handoff_state": "BLOCKED",
                "blocker_codes": ["LEGACY_PROVENANCE_GAP"],
                "next_safe_action": "DO_NOT_RECONSTRUCT_DECISION_TIME_EVIDENCE",
            },
        }
    try:
        manifest = validate_promotion_handoff_manifest(raw_manifest, root=root)
    except PromotionHandoffError:
        return {
            **empty,
            "identity": identity,
            "science": science,
            "provenance": {
                "manifest_status": "INVALID",
                "source_revalidation": "UNKNOWN",
                "direct_evidence": [],
                "experiment_spec_binding": None,
            },
            "state": {
                "handoff_state": "BLOCKED",
                "blocker_codes": ["HANDOFF_MANIFEST_INVALID"],
                "next_safe_action": "FAIL_CLOSED_INVALID_MANIFEST",
            },
        }
    science["handoff_manifest_sha256"] = manifest["manifest_sha256"]
    science["obligations"] = list(manifest.get("obligations") or [])
    revalidation, revalidation_codes = _source_revalidation(
        manifest, store_records, records_status
    )
    blockers = [code for code in revalidation_codes if code == "EVIDENCE_HASH_CONFLICT"]
    check = check_materialization(
        root=root,
        manifest=manifest,
        execution_inputs=execution_inputs,
        decision_event_id=decision_event_id,
        existing_blockers=blockers,
    )
    next_action = {
        "NOT_PROMOTED": "NO_SCIENTIFIC_PROMOTE",
        "BLOCKED": _blocked_next(check["blocker_codes"]),
        "READY_TO_MATERIALIZE": "BOUNDED_GIT_MATERIALIZATION_STEP",
        "MATERIALIZED": "INSPECT_STRATEGY_VERSION_NO_ACTIVATION",
        "CONFLICT": "DO_NOT_OVERWRITE_STRATEGY_VERSION",
    }[check["handoff_state"]]
    informational = [code for code in revalidation_codes if code == "SOURCE_UNAVAILABLE"]
    return {
        "schema": HANDOFF_SCHEMA,
        "schema_version": "1.0",
        "authority_granted": False,
        "activation_created": False,
        "identity": identity,
        "science": science,
        "provenance": {
            "manifest_status": "VALID",
            "source_revalidation": revalidation,
            "direct_evidence": list(manifest.get("direct_evidence") or []),
            "experiment_spec_binding": {
                "source_kind": manifest["experiment_spec_source_kind"],
                "source_value": manifest["experiment_spec_source_value"],
                "spec_sha256": manifest["experiment_spec_sha256"],
            },
            "informational_codes": informational,
        },
        "materialization": {
            "strategy_relation": (
                "PRESENT" if check["handoff_state"] == "MATERIALIZED" else "ABSENT"
            ),
            "strategy_id": check.get("strategy_id"),
            "strategy_version": check.get("strategy_version"),
            "strategy_identity": check.get("strategy_identity"),
        },
        "state": {
            "handoff_state": check["handoff_state"],
            "blocker_codes": check["blocker_codes"],
            "next_safe_action": next_action,
        },
        "authority": {"authority_granted": False, "activation_created": False},
        "field_provenance": dict(FIELD_PROVENANCE),
        "manifest": manifest,
        "decision_effective_at": science["decision_effective_at"],
    }


def _blocked_next(codes: Sequence[str]) -> str:
    if "EVIDENCE_HASH_CONFLICT" in codes:
        return "FAIL_CLOSED_EVIDENCE_HASH_CONFLICT"
    if "EXECUTION_INPUT_GAP" in codes:
        return "SUPPLY_EXPLICIT_EXECUTION_INPUTS"
    if "LEGACY_PROVENANCE_GAP" in codes:
        return "DO_NOT_RECONSTRUCT_DECISION_TIME_EVIDENCE"
    if "HANDOFF_MANIFEST_INVALID" in codes:
        return "FAIL_CLOSED_INVALID_MANIFEST"
    if "SOURCE_UNAVAILABLE" in codes:
        return "RESOLVE_RESEARCH_STORE"
    return "INSPECT_HANDOFF_BLOCKER"


def handoff_overview_counters(
    projection: Mapping[str, Any],
    *,
    research_status: str,
) -> dict[str, int | None]:
    if research_status not in {"AVAILABLE", "EMPTY"}:
        return {
            "SCIENTIFIC PROMOTE": None,
            "READY TO STRATEGY": None,
            "HANDOFF BLOCKED": None,
            "STRATEGY MATERIALIZED": None,
        }
    promotes = 0
    with_manifest = 0
    for entity in projection.get("entities") or []:
        if not isinstance(entity, Mapping):
            continue
        if entity.get("native_kind") != "DECISION_EVENT":
            continue
        fields = entity.get("source_owned_fields") if isinstance(
            entity.get("source_owned_fields"), Mapping
        ) else {}
        kind = str(fields.get("decision kind") or entity.get("native_state") or "")
        if kind != "PROMOTE":
            continue
        promotes += 1
        if fields.get("promotion_handoff_manifest_sha256"):
            with_manifest += 1
    materialized = 0
    known = {str(item.get("entity_id") or "") for item in projection.get("entities") or []}
    for rel in projection.get("relations") or []:
        if not isinstance(rel, Mapping):
            continue
        if rel.get("relation_type") != "REFERENCES_DECISION_ASSET":
            continue
        if rel.get("resolution") == "RESOLVED" and rel.get("to_entity_id") in known:
            materialized += 1
    blocked = max(promotes - materialized, 0)
    ready = 0
    return {
        "SCIENTIFIC PROMOTE": promotes,
        "READY TO STRATEGY": ready,
        "HANDOFF BLOCKED": blocked,
        "STRATEGY MATERIALIZED": materialized,
    }
