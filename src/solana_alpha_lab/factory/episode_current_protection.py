"""Source-owned current protection for local exploratory episode research.

Frozen parsing stays in opportunity_episodes. This owner reads declarations only,
never market values, grants no science, and publishes only on explicit apply.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.factory.opportunity_episodes import (
    ALLOW, ASSIGNMENT_DIR, ASSIGNMENT_SCHEMA, ProtectionInventory,
    assignment_document_sha256, inventory_from_documents,
)
from solana_alpha_lab.factory.research_store import ResearchStore, ResearchStoreError, publish_immutable_artifact
from solana_alpha_lab.factory.run_passport import canonical_sha256

CONTRACT = "EPISODE_CURRENT_PROTECTION_V1"
CONFIG = "configs/episode_current_protection_sources_v1.yaml"
POINTER = "protection/current_research.json"
REPO = Path(__file__).resolve().parents[3]
ROLES = ("LOCAL_ASSIGNMENTS", "CANONICAL_RESEARCHSTORE", "FAST_LANE_RESEARCHSTORE",
         "CONSUMPTION_REGISTRY", "TASK22_ACCEPTED_SPLIT", "EXPERIMENT_POLICIES", "LIST_A_PROTOCOL")


def _public_identifier(value: Any) -> str | None:
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", value) else None


def _public_ref(value: Any) -> str | None:
    # Only repository-relative refs or our logical identities, never a raw URL,
    # absolute machine path, exception string or untrusted payload.
    if not isinstance(value, str):
        return None
    for prefix in ("research-record://", "smial-data://", "authority://"):
        if value.startswith(prefix):
            return value if _public_identifier(value[len(prefix):]) else None
    if (re.fullmatch(r"[A-Za-z0-9_./-]{1,240}", value) and not value.startswith("/")
            and not any(part in {"", ".", ".."} for part in value.split("/"))):
        return value
    return None


def _recovery_action(code: str) -> str:
    if code == "CURRENT_PROTECTION_NOT_INSTALLED":
        return "PREPARE_EXACT_METADATA_INSTALLATION_PROPOSAL"
    if code == "PROTECTION_INSTALLATION_AUTHORITY_REQUIRED":
        return "REQUEST_AUTHORITY_FOR_EXACT_METADATA_PROPOSAL"
    if code in {"PROTECTION_SOURCE_CHANGED", "PROTECTION_PROPOSAL_CHANGED", "CURRENT_PROTECTION_SOURCE_SET_CHANGED"}:
        return "REFRESH_SOURCE_STATUS_AND_PREVIEW"
    if any(part in code for part in ("UNKNOWN", "UNSUPPORTED", "UNRESOLVED")):
        return "RESOLVE_NAMED_AUTHORITY_INTERPRETATION"
    return "RESTORE_OR_REPAIR_NAMED_SOURCE_THEN_RETRY"


class CurrentProtectionError(ValueError):
    def __init__(self, code: str, *, owner: str | None = None, source_ref: str | None = None,
                 observed_form: str | None = None, observed_version: str | None = None) -> None:
        super().__init__(code)
        self.code, self.owner = code, owner
        self.source_ref = _public_ref(source_ref)
        self.observed_form = _public_identifier(observed_form)
        self.observed_version = _public_identifier(observed_version)

    @property
    def detail(self) -> dict[str, Any]:
        return {"source_reason": self.code, "owner": self.owner or "SOURCE_SET",
                "source_ref": self.source_ref or {"LOCAL_ASSIGNMENTS": POINTER,
                    "CANONICAL_RESEARCHSTORE": "smial-data://canonical_researchstore",
                    "FAST_LANE_RESEARCHSTORE": "smial-data://fast_lane_researchstore",
                    "CONSUMPTION_REGISTRY": "registries/holdout_consumption.yaml",
                    "TASK22_ACCEPTED_SPLIT": "docs/evidence/task22/a6_split_resolution_acceptance_catalog_factory_fit_v1.json",
                    "EXPERIMENT_POLICIES": "configs/experiment_specs",
                    "LIST_A_PROTOCOL": "configs/list_a_chronological_confirmation_v1.yaml"}.get(self.owner, CONFIG),
                **({"observed_form": self.observed_form} if self.observed_form else {}),
                **({"observed_version": self.observed_version} if self.observed_version else {}),
                "next_action": _recovery_action(self.code)}


def _require(ok: Any, code: str, owner: str | None = None, *, source_ref: str | None = None) -> None:
    if not ok:
        raise CurrentProtectionError(code, owner=owner, source_ref=source_ref)


def _owned(role: str, operation, *, source_ref: str | None = None):
    try:
        return operation()
    except CurrentProtectionError as exc:
        if exc.owner is None:
            exc.owner = role
        if exc.source_ref is None:
            exc.source_ref = _public_ref(source_ref)
        raise
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError, ResearchStoreError) as exc:
        raise CurrentProtectionError("PROTECTION_SOURCE_UNAVAILABLE", owner=role, source_ref=source_ref) from exc


def _safe(root: Path, relative: str) -> Path:
    _require(isinstance(relative, str) and relative and not Path(relative).is_absolute()
             and not any(p in {"..", "."} for p in relative.replace("\\", "/").split("/")),
             "PROTECTION_SOURCE_PATH_INVALID")
    path = root / relative
    _require(path.resolve().is_relative_to(root.resolve()), "PROTECTION_SOURCE_PATH_INVALID")
    for candidate in [root, path, *path.parents]:
        if candidate == root.parent:
            break
        _require(not candidate.is_symlink() and not candidate.is_junction(), "PROTECTION_SOURCE_PATH_INVALID")
    return path


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "PROTECTION_SOURCE_JSON_INVALID")
        result[key] = value
    return result


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes(), object_pairs_hook=_pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(CurrentProtectionError("PROTECTION_SOURCE_JSON_INVALID")))
    _require(isinstance(value, dict), "PROTECTION_SOURCE_JSON_INVALID")
    return value


def root_identity(root: Path) -> str:
    return canonical_sha256({"data_root": str(root.resolve())})


def _scope(root: Path) -> dict[str, str]:
    return {"collection": "OPPORTUNITY_EPISODES", "evidence_role": "EXPLORATORY_REUSE",
            "data_root_identity_sha256": root_identity(root)}


def _config(repo: Path) -> dict[str, Any]:
    value = yaml.safe_load(_safe(repo, CONFIG).read_bytes())
    _require(isinstance(value, dict) and value.get("schema") == "smial.episode-current-protection-sources"
             and value.get("schema_version") == "1.0" and value.get("interpretation_version") == "1.0"
             and value.get("collection") == "OPPORTUNITY_EPISODES" and value.get("evidence_role") == "EXPLORATORY_REUSE"
             and value.get("required_roles") == list(ROLES)
             and value.get("secondary_store") == "fast_lane_research_data_plane", "PROTECTION_SOURCE_SET_UNSUPPORTED")
    # These three administrative meanings belong to the native policy owner.
    # Resolve every form/schema/version check from the same native constants;
    # budgets, CAS chains and limits remain that owner's responsibility.
    from solana_alpha_lab.factory import hfic_research_policy as policy
    meanings = {policy.ARTIFACT_KIND: policy.SCHEMA, policy.SNAPSHOT_KIND: policy.SNAPSHOT_SCHEMA,
                policy.EXTENSION_KIND: policy.EXTENSION_SCHEMA}
    value["native_envelope_owners"][policy.PRODUCER] = {"RESEARCH_ARTIFACT": list(meanings)}
    for form, schema in meanings.items():
        value["body_schema_by_form"][form] = [schema]
        value["body_artifact_marker_forms"].append(form)
        value["store_body_versions"][form] = [policy.SCHEMA_VERSION]
        value["store_body_versions"][schema] = [policy.SCHEMA_VERSION]
    return value


def _assignment_documents(root: Path) -> list[dict[str, Any]]:
    directory = _safe(root, ASSIGNMENT_DIR)
    # The namespace is optional, not a missing mandatory registry. Its absence
    # alone never proves completeness: every other canonical owner is required.
    if not directory.exists():
        return []
    _require(directory.is_dir(), "PROTECTION_ASSIGNMENT_SOURCE_INVALID")
    result = []
    for path in sorted(directory.iterdir()):
        _require(not path.is_symlink() and not path.is_junction() and path.is_file(), "PROTECTION_ASSIGNMENT_SOURCE_INVALID")
        if path.suffix != ".json":
            # Native atomic publication may leave an inactive temporary file.
            _require(path.name.startswith(".") and path.name.endswith(".tmp"), "PROTECTION_ASSIGNMENT_SOURCE_UNKNOWN")
            continue
        doc = {}
        try:
            doc = _json(_safe(root, path.relative_to(root).as_posix()))
            if doc.get("schema") == ASSIGNMENT_SCHEMA:
                _require(doc.get("schema_version") == "1.0" and doc.get("interpretation_version") == "1.0",
                         "PROTECTION_ASSIGNMENT_VERSION_UNKNOWN")
            metadata = doc.get("completeness") or {}
            _require(inventory_from_documents([doc]).status == ALLOW, "PROTECTION_ASSIGNMENT_SOURCE_INVALID")
            _require(doc.get("interpretation_version") == "1.0" and isinstance(doc.get("entries"), list),
                     "PROTECTION_ASSIGNMENT_VERSION_UNKNOWN")
            _require(path.stem == doc.get("assignment_id"), "PROTECTION_ASSIGNMENT_IDENTITY_MISMATCH")
            for entry in doc["entries"]:
                scope = entry.get("scope") or {}
                _require(isinstance(scope, Mapping), "PROTECTION_SCOPE_UNKNOWN")
                _require(scope.get("kind") in {"ALL_TIME", "INTERVAL"}, "PROTECTION_SCOPE_UNKNOWN")
                if scope["kind"] == "INTERVAL":
                    _require(_time(scope.get("start")) < _time(scope.get("end")), "PROTECTION_SCOPE_INVALID")
            if isinstance(metadata, Mapping) and "current_contract" in metadata:
                _require(metadata["current_contract"] == CONTRACT, "CURRENT_PROTECTION_VERSION_UNKNOWN")
                _require(doc.get("schema") == ASSIGNMENT_SCHEMA and doc.get("schema_version") == "1.0"
                         and doc.get("interpretation_version") == "1.0" and metadata.get("complete") is True,
                         "CURRENT_PROTECTION_RECEIPT_INVALID")
                _require(set(doc) == {"schema", "schema_version", "interpretation_version", "assignment_id", "owner", "completeness", "entries"}
                         and doc.get("owner") == "OPPORTUNITY_EPISODES"
                         and set(metadata) == {"complete", "current_contract", "checked_at", "read_scope", "source_set_sha256", "source_frontier", "context_sha256", "predecessor", "boundary"}
                         and metadata.get("boundary") == "LOCAL_EPISODE_EXPLORATORY_ONLY; ADVISORY_SCOPE_UNKNOWN; NO_CONFIRMATORY_OR_SCOUT_GRANT",
                         "CURRENT_PROTECTION_RECEIPT_INVALID")
                _require(metadata.get("read_scope") == _scope(root), "CURRENT_PROTECTION_BINDING_INVALID")
                digest = lambda value: isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
                frontier = metadata["source_frontier"]
                _require(digest(metadata["source_set_sha256"]) and (metadata["predecessor"] is None or digest(metadata["predecessor"]))
                         and isinstance(frontier, list) and all(isinstance(item, Mapping) for item in frontier)
                         and [item.get("owner") for item in frontier] == list(ROLES)
                         and all(isinstance(item.get("ref"), str) and bool(item["ref"]) and digest(item.get("semantic_sha256")) for item in frontier),
                         "CURRENT_PROTECTION_RECEIPT_INVALID")
                context = {"contract": CONTRACT, "read_scope": metadata["read_scope"], "source_set_sha256": metadata["source_set_sha256"],
                           "source_frontier": frontier, "effective_restrictions_sha256": canonical_sha256(doc["entries"])}
                _require(metadata["context_sha256"] == canonical_sha256(context), "CURRENT_PROTECTION_RECEIPT_INVALID")
                basis = canonical_sha256({"context": metadata["context_sha256"], "checked_at": metadata["checked_at"],
                                          "predecessor": metadata["predecessor"]})
                _require(doc.get("assignment_id") == path.stem == "CURRENT-RESEARCH-" + basis[:32].upper(),
                         "CURRENT_PROTECTION_RECEIPT_INVALID")
                _require(_time(metadata["checked_at"]) <= datetime.now(UTC), "CURRENT_PROTECTION_TIME_INVALID")
                # Only correctly formed derived receipts are excluded, never a
                # foreign primary assignment carrying an arbitrary output marker.
                continue
            if isinstance(metadata, Mapping) and "as_of" in metadata:
                value = metadata["as_of"]
                _require(isinstance(value, str), "PROTECTION_SOURCE_TIME_INVALID")
                stamp = _time(value + "T00:00:00Z" if len(value) == 10 else value)
                _require(stamp <= datetime.now(UTC), "PROTECTION_SOURCE_TIME_INVALID")
            result.append(doc)
        except (CurrentProtectionError, OSError, ValueError, KeyError, TypeError) as exc:
            error = exc if isinstance(exc, CurrentProtectionError) else CurrentProtectionError("PROTECTION_ASSIGNMENT_SOURCE_INVALID")
            error.source_ref = _public_ref(path.relative_to(root).as_posix())
            error.observed_form = _public_identifier(doc.get("schema"))
            error.observed_version = _public_identifier(doc.get("schema_version"))
            raise error from None
    return result


def _time(value: Any) -> datetime:
    _require(isinstance(value, str), "PROTECTION_SOURCE_TIME_INVALID")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        _require(stamp.tzinfo is not None and stamp.utcoffset().total_seconds() == 0, "PROTECTION_SOURCE_TIME_INVALID")
        return stamp.astimezone(UTC)
    except (ValueError, TypeError, OverflowError):
        raise CurrentProtectionError("PROTECTION_SOURCE_TIME_INVALID") from None


def _store_projection(root: Path, config: Mapping[str, Any], repo: Path) -> list[dict[str, Any]]:
    _require(root.is_dir() and not root.is_symlink() and not root.is_junction(), "PROTECTION_RESEARCHSTORE_MISSING")
    projection = []
    # Native committed Parquet + manifests are truth; no projection rebuild or
    # operational database open, and no whole-store digest used as freshness.
    for record in ResearchStore(root, create_if_missing=False).iter_committed_records(fresh=True):
        wrapper, body = {}, {}
        try:
            wrapper = json.loads(record.payload_json)
            _require(isinstance(wrapper, dict), "PROTECTION_DECLARATION_INVALID")
            owners = config["native_envelope_owners"]
            _require(record.producer_capability_id in owners, "PROTECTION_DECLARATION_OWNER_UNKNOWN")
            forms = owners[record.producer_capability_id]
            kind = str(record.record_kind)
            _require(kind in forms, "PROTECTION_DECLARATION_FORM_UNKNOWN")
            form = wrapper.get("artifact_kind") if kind == "RESEARCH_ARTIFACT" else "NATIVE_DIRECT"
            _require(isinstance(form, str) and form in forms[kind], "PROTECTION_DECLARATION_FORM_UNKNOWN")
            _require("payload_canonical" not in wrapper or isinstance(wrapper["payload_canonical"], str),
                     "PROTECTION_DECLARATION_FORM_UNKNOWN")
            body = json.loads(wrapper["payload_canonical"]) if isinstance(wrapper.get("payload_canonical"), str) else wrapper
            _require(isinstance(body, dict) and body, "PROTECTION_DECLARATION_INVALID")
            identity = form if kind == "RESEARCH_ARTIFACT" else kind
            _require(body.get("schema") in config["body_schema_by_form"].get(identity, [None])
                     and body.get("kind") is None
                     and body.get("artifact_kind") == (identity if identity in config["body_artifact_marker_forms"] else None)
                     and body.get("packet_schema") == config["body_packet_schema_by_form"].get(identity),
                     "PROTECTION_DECLARATION_FORM_UNKNOWN")
            required = config["unmarked_body_identity_fields"].get(identity)
            if required is not None:
                # Native prior-memory/session readers also accept legacy direct
                # decisions whose identity is the ResearchEvent entity. The
                # hypothesis link and decision fields must still be interpretable.
                legacy_decision = (identity == "DECISION_EVENT" and "decision_event_id" not in body
                    and isinstance(record.entity_id, str) and bool(record.entity_id)
                    and body.get("hypothesis_version_id") == record.hypothesis_version_id
                    and all(isinstance(body.get(key), str) and bool(body[key])
                            for key in ("hypothesis_version_id", "decision_kind", "reason_code")))
                _require(isinstance(required, list) and bool(required)
                         and (all(key in body for key in required) or legacy_decision),
                         "PROTECTION_DECLARATION_FORM_UNKNOWN")
            if isinstance(wrapper.get("payload_canonical"), str):
                _require(all(wrapper.get(key) is None for key in ("schema", "schema_version", "kind", "packet_schema", "packet_version")),
                         "PROTECTION_DECLARATION_FORM_UNKNOWN")
            _require(record.schema_version in config["store_record_versions"], "PROTECTION_RESEARCH_EVENT_VERSION_UNKNOWN")
            if "packet_schema" in body or "packet_version" in body:
                _require(body.get("packet_schema") in config["native_packet_versions"]
                         and body.get("packet_version") in config["native_packet_versions"][body["packet_schema"]],
                         "PROTECTION_DECLARATION_VERSION_UNKNOWN")
            for field, versions in config["native_text_versions"].items():
                for layer in (wrapper, body):
                    if field in layer:
                        _require(layer[field] in versions, "PROTECTION_DECLARATION_VERSION_UNKNOWN")
            # Native unmarked bodies are unversioned; an added schema version
            # is a new interpretation, never evidence of an empty declaration.
            _require("schema_version" not in body or any(body.get(key) is not None for key in ("artifact_kind", "kind", "schema")),
                     "PROTECTION_DECLARATION_VERSION_UNKNOWN")
            for marker_key in ("artifact_kind", "kind", "schema"):
                marker = body.get(marker_key)
                if marker is not None:
                    _require(isinstance(marker, str) and marker in config["store_body_versions"]
                             and body.get("schema_version") in config["store_body_versions"][marker],
                             "PROTECTION_DECLARATION_VERSION_UNKNOWN")
            for layer in (wrapper, body):
                if layer.get("schema") == ASSIGNMENT_SCHEMA or any(k in layer for k in
                        ("protection_assignments", "protected_assignments", "holdout_assignments", "assignment_sources",
                         "holdout", "protected", "assignment", "split", "holdout_policy")):
                    # Neither native layer has an assignment writer in this
                    # interpretation; an unknown link cannot disappear as empty.
                    raise CurrentProtectionError("PROTECTION_DECLARATION_OWNER_UNSUPPORTED")
                _require(not layer.get("holdout_consumption_ids"), "PROTECTION_CONSUMPTION_LINK_UNRESOLVED")
            _require(wrapper is body or not any(key in wrapper for key in ("experiment_spec", "experiment_spec_packet")),
                     "PROTECTION_EXPERIMENT_DECLARATION_UNKNOWN")
            declarations = {}
            # These are the two native owner spellings, each wrapped or bare.
            # Validate every supplied protection declaration, including conflicting
            # duplicates; scientific parameters do not become assignment authority.
            for field in ("experiment_spec", "experiment_spec_packet"):
                submission = body.get(field)
                if submission is None:
                    continue
                _require(isinstance(submission, Mapping), "PROTECTION_EXPERIMENT_DECLARATION_UNKNOWN")
                spec = submission.get("experiment_spec", submission)
                try:
                    _require(isinstance(spec, Mapping), "PROTECTION_EXPERIMENT_DECLARATION_UNKNOWN")
                    if spec.get("schema_version") == "1.1":
                        # Native 1.1 adds input bindings to the same legacy
                        # protection meaning; it is not a fresh holdout grant.
                        from solana_alpha_lab.factory.experiment_spec import validate_experiment_document
                        validate_experiment_document(spec, root=repo)
                    meaning = _experiment_meaning(spec, config, repo)
                except ValueError:
                    raise CurrentProtectionError("PROTECTION_EXPERIMENT_DECLARATION_UNKNOWN",
                        observed_form=spec.get("schema") if isinstance(spec, Mapping) else None,
                        observed_version=spec.get("schema_version") if isinstance(spec, Mapping) else None) from None
                value = {"record_id": record.record_id, "policy": meaning["holdout_policy"],
                         "population": meaning["population"], "observation_request": meaning.get("observation_request")}
                if spec["schema_version"] == "1.1":
                    value.update(native_spec_version="1.1", data_bindings=spec["data_bindings"])
                declarations[canonical_sha256(value)] = value
            _require(len(declarations) <= 1, "PROTECTION_EXPERIMENT_DECLARATION_UNKNOWN")
            projection.extend(declarations.values())
        except (CurrentProtectionError, ValueError, KeyError, TypeError) as exc:
            error = exc if isinstance(exc, CurrentProtectionError) else CurrentProtectionError("PROTECTION_DECLARATION_INVALID")
            error.source_ref = _public_ref("research-record://" + record.record_id)
            error.observed_form = error.observed_form or _public_identifier(wrapper.get("artifact_kind") if isinstance(wrapper, Mapping) else None) or str(record.record_kind)
            if isinstance(body, Mapping):
                error.observed_version = error.observed_version or _public_identifier(body.get("schema_version") or body.get("packet_version"))
            raise error from None
    # holdouts_not_touched is advisory source assertion, never assignment or
    # proof of empty. Its unresolved referent is retained in the boundary text.
    return sorted(projection, key=lambda item: item["record_id"])


def _task22(repo: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    from solana_alpha_lab import task22_split_resolution as owner
    expected = {"SPLIT_PATH": "docs/evidence/task22/dataset_split_manifest_v2.json",
                "LEDGER_PATH": "docs/evidence/task22/holdout_access_ledger_v2.json",
                "PROFILE_PATH": "configs/task22_task23_consumer_time_profile_v1.yaml"}
    _require(all(getattr(owner, key) == value for key, value in expected.items()), "TASK22_SOURCE_OWNER_VERSION_UNKNOWN")
    directory = _safe(repo, "docs/evidence/task22")
    _require({p.name for p in directory.glob("holdout_access_ledger*.json")} ==
             {"holdout_access_ledger_v1.json", "holdout_access_ledger_v2.json"}, "TASK22_SOURCE_VERSION_UNKNOWN")
    import hashlib
    read_bytes = lambda rel: _owned("TASK22_ACCEPTED_SPLIT", lambda: _safe(repo, rel).read_bytes(), source_ref=rel)
    read_json = lambda rel: _owned("TASK22_ACCEPTED_SPLIT", lambda: _json(_safe(repo, rel)), source_ref=rel)
    _require(hashlib.sha256(read_bytes(str(config["task22_acceptance_ref"]))).hexdigest() == config["task22_acceptance_sha256"], "TASK22_ACCEPTANCE_BINDING_CHANGED")
    receipt = read_json(str(config["task22_acceptance_ref"]))
    split = read_json(owner.SPLIT_PATH); ledger = read_json(owner.LEDGER_PATH)
    sha = lambda rel: hashlib.sha256(read_bytes(rel)).hexdigest()
    accepted = receipt["accepted_result"]
    _require(receipt.get("status") == "PASS_SPLIT_READY_WITH_LIMITATIONS"
             and split.get("schema") == "smial.task22.dataset-split-manifest-v2" and split.get("schema_version") == "2.0"
             and ledger.get("schema") == "smial.task22.holdout-ledger-extension-v2" and ledger.get("ledger_version") == 2,
             "TASK22_SOURCE_VERSION_UNKNOWN")
    bindings = {item["path"]: item["sha256"] for item in receipt["frozen_a5_artifacts"]}
    _require(all(bindings.get(rel) == sha(rel) for rel in expected.values())
             and accepted["split_manifest_sha256"] == sha(owner.SPLIT_PATH)
             and ledger["split_binding"]["sha256"] == sha(owner.SPLIT_PATH), "TASK22_SOURCE_BINDING_CHANGED")
    _require(accepted["dataset_inventory_sha256"] == split["content_addressing"]["dataset_inventory_sha256"], "TASK22_DATASET_IDENTITY_CONFLICT")
    _require(ledger["assignment_receipt"]["assignment_id"] == "T22-HOLDOUT-ASSIGNMENT-001"
             and ledger["assignment_receipt"]["holdout_batch_id"] == split["roles"]["holdout"]["batch_id"] == "T21-R3"
             and ledger["state"]["current"] == "UNTOUCHED" and ledger["state"]["access_default"] == "DENY"
             and split["roles"]["holdout"]["state"] == "UNTOUCHED" and split["roles"]["holdout"]["access"] == "DENY"
             and not ledger["records"] and split["outcome_seal"]["state"] == "UNOPENED", "TASK22_SOURCE_STATE_UNKNOWN")
    return {"split_ref": owner.SPLIT_PATH, "split_sha256": sha(owner.SPLIT_PATH),
            "ledger_ref": owner.LEDGER_PATH, "ledger_sha256": sha(owner.LEDGER_PATH),
            "profile_ref": owner.PROFILE_PATH, "profile_sha256": sha(owner.PROFILE_PATH),
            "dataset_inventory_sha256": accepted["dataset_inventory_sha256"],
            "restricted_batch": "T21-R3", "restriction": "UNTOUCHED_DENY",
            "selection_at": split["roles"]["holdout"]["selection_observed_at"],
            "labels_available_at": split["roles"]["holdout"]["label_first_reliable_available_at"],
            "applicability": "TASK21_FROZEN_DATASET_ONLY_NOT_GLOBAL_MINT_BAN"}


def _experiment_meaning(value: Mapping[str, Any], config: Mapping[str, Any], repo: Path) -> dict[str, Any]:
    _require(value.get("schema") == "smial.experiment-spec", "EXPERIMENT_POLICY_INTERPRETATION_UNKNOWN")
    projection = {k: value.get(k) for k in ("schema", "schema_version", "population", "holdout_policy")}
    _require(not any(key in value for key in ("protection_assignments", "protected_assignments", "holdout_assignments",
        "assignment_sources", "holdout", "protected", "assignment", "split", "holdout_consumption_ids")),
        "EXPERIMENT_POLICY_INTERPRETATION_UNKNOWN")
    if value["schema_version"] == "1.4":
        observation = value.get("observation_request")
        _require(value.get("population") == "OPPORTUNITY_EPISODES"
                 and value.get("holdout_policy") == config["embedded_exploratory_policy"]
                 and observation == {"collection_mode": "REUSE_ONLY", "requested_evidence_role": "EXPLORATORY_REUSE"},
                 "EXPERIMENT_POLICY_INTERPRETATION_UNKNOWN")
        projection["observation_request"] = observation
    elif value["schema_version"] in config["legacy_experiment_policy_versions"]:
        _require({**projection, "schema_version": "1.0"} in config["legacy_experiment_policy_meanings"] and "observation_request" not in value,
                 "EXPERIMENT_POLICY_INTERPRETATION_UNKNOWN")
    elif value["schema_version"] == "1.5":
        _require(projection in config["legacy_experiment_policy_meanings"] and "observation_request" not in value,
                 "EXPERIMENT_POLICY_INTERPRETATION_UNKNOWN")
        protocol_ref = "configs/list_a_chronological_confirmation_v1.yaml"
        protocol = yaml.safe_load(_safe(repo, protocol_ref).read_bytes())
        parameters = value["parameters"]
        _require(parameters.get("protocol_ref") == "repo://" + protocol_ref
                 and parameters.get("protocol_core_sha256") == canonical_sha256(protocol["protocol_core"]),
                 "EXPERIMENT_POLICY_AUTHORITY_BINDING_UNKNOWN")
        projection["parameters"] = parameters
    else:
        raise CurrentProtectionError("EXPERIMENT_POLICY_INTERPRETATION_UNKNOWN")
    return projection


def _experiment_policy(path: Path, repo: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    from solana_alpha_lab.factory.experiment_spec import validate_experiment_document, ExperimentSpecError
    import hashlib
    ref = path.relative_to(repo).as_posix()
    _require(path.is_file(), "EXPERIMENT_POLICY_INTERPRETATION_UNKNOWN")
    value = yaml.safe_load(_safe(repo, ref).read_bytes())
    _require(isinstance(value, dict), "EXPERIMENT_POLICY_INTERPRETATION_UNKNOWN")
    try:
        try:
            validate_experiment_document(value, root=repo)
        except ExperimentSpecError:
            raise CurrentProtectionError("EXPERIMENT_POLICY_INTERPRETATION_UNKNOWN",
                observed_form=value.get("schema"), observed_version=value.get("schema_version")) from None
        projection = _experiment_meaning(value, config, repo)
        return {"ref": ref, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "semantic_sha256": canonical_sha256(projection), **projection}
    except CurrentProtectionError as exc:
        exc.observed_form = _public_identifier(value.get("schema"))
        exc.observed_version = _public_identifier(value.get("schema_version"))
        raise



def collect_current_sources(data_root: Path, *, repo_root: Path | None = None) -> dict[str, Any]:
    """One source-specific vector. Does not claim cross-root atomicity."""
    root, repo = Path(data_root), Path(repo_root or REPO)
    _require(root.is_absolute() and root.is_dir(), "PROTECTION_DATA_ROOT_INVALID")
    _safe(root, "research")
    config = _owned("SOURCE_SET", lambda: _config(repo), source_ref=CONFIG)
    frontier = []
    entries = []
    def add(role, ref, payload, **detail):
        frontier.append({"owner": role, "ref": ref, "semantic_sha256": canonical_sha256(payload), **detail})
    primary = _owned("LOCAL_ASSIGNMENTS", lambda: _assignment_documents(root), source_ref=ASSIGNMENT_DIR)
    for doc in primary:
        entries.extend(doc["entries"])
    add("LOCAL_ASSIGNMENTS", ASSIGNMENT_DIR, [{"assignment_id": d["assignment_id"],
        "sha256": assignment_document_sha256(d)} for d in primary], assignment_document_count=len(primary),
        assignment_refs=[{"assignment_id": d["assignment_id"], "sha256": assignment_document_sha256(d)} for d in primary])
    secondary = root.parent / config["secondary_store"]
    for role, source_root in (("CANONICAL_RESEARCHSTORE", root), ("FAST_LANE_RESEARCHSTORE", secondary)):
        _owned(role, lambda: _safe(source_root, "research"))
        declarations = _owned(role, lambda: _store_projection(source_root, config, repo), source_ref="smial-data://" + role.lower())
        native = _owned(role, lambda: _assignment_documents(source_root), source_ref=ASSIGNMENT_DIR) if role == "FAST_LANE_RESEARCHSTORE" else []
        for doc in native:
            entries.extend(doc["entries"])
        add(role, "smial-data://" + role.lower(), {"root_identity": root_identity(source_root),
            "declarations": declarations, "assignments": native}, declaration_count=len(declarations),
            declaration_refs=[{"record_id": d["record_id"], "semantic_sha256": canonical_sha256(d)} for d in declarations],
            assignment_refs=[{"assignment_id": d["assignment_id"], "sha256": assignment_document_sha256(d)} for d in native])
    registry = _owned("CONSUMPTION_REGISTRY", lambda: yaml.safe_load(_safe(repo, "registries/holdout_consumption.yaml").read_bytes()), source_ref="registries/holdout_consumption.yaml")
    _require(isinstance(registry, dict) and registry.get("schema_version") == "1.0"
             and registry.get("registry_id") == "SMIAL-REGISTRY-HOLDOUT-CONSUMPTION"
             and registry.get("truth_owner") == "TASK-03" and registry.get("records") == [], "CONSUMPTION_SOURCE_SCOPE_UNKNOWN", "CONSUMPTION_REGISTRY")
    add("CONSUMPTION_REGISTRY", "registries/holdout_consumption.yaml", {k: registry[k] for k in
        ("schema_version", "registry_id", "truth_owner", "records")}, interpretation="CONSUMPTION_ONLY_NOT_ASSIGNMENT_ABSENCE")
    task22 = _owned("TASK22_ACCEPTED_SPLIT", lambda: _task22(repo, config), source_ref=config["task22_acceptance_ref"])
    add("TASK22_ACCEPTED_SPLIT", config["task22_acceptance_ref"], task22)
    policies = []
    directory = _owned("EXPERIMENT_POLICIES", lambda: _safe(repo, "configs/experiment_specs"), source_ref="configs/experiment_specs")
    _require(directory.is_dir(), "EXPERIMENT_POLICY_SOURCE_MISSING", "EXPERIMENT_POLICIES", source_ref="configs/experiment_specs")
    paths = _owned("EXPERIMENT_POLICIES", lambda: sorted(directory.iterdir()), source_ref="configs/experiment_specs")
    for path in paths:
        ref = path.relative_to(repo).as_posix()
        policies.append(_owned("EXPERIMENT_POLICIES", lambda: _experiment_policy(path, repo, config), source_ref=ref))
    add("EXPERIMENT_POLICIES", "configs/experiment_specs", policies,
        policy_refs=[{k: item[k] for k in ("ref", "sha256", "semantic_sha256")} for item in policies])
    protocol = _owned("LIST_A_PROTOCOL", lambda: yaml.safe_load(_safe(repo, "configs/list_a_chronological_confirmation_v1.yaml").read_bytes()), source_ref="configs/list_a_chronological_confirmation_v1.yaml")
    _require(isinstance(protocol, dict), "LIST_A_SOURCE_VERSION_UNKNOWN", "LIST_A_PROTOCOL")
    _require(protocol.get("schema") == "smial.list-a-confirmation-protocol" and protocol.get("schema_version") == "1.0",
             "LIST_A_SOURCE_VERSION_UNKNOWN", "LIST_A_PROTOCOL")
    sample = protocol.get("sample_binding")
    core = protocol.get("protocol_core")
    _require(isinstance(sample, dict) and isinstance(core, dict), "LIST_A_SOURCE_VERSION_UNKNOWN", "LIST_A_PROTOCOL")
    future = core.get("future_execution_contract")
    _require(isinstance(future, dict), "LIST_A_SOURCE_VERSION_UNKNOWN", "LIST_A_PROTOCOL")
    _require(protocol.get("status") == "DESIGN_VALIDATED_BOUND_CONTRACT_NOT_READY"
             and sample.get("status") == "UNBOUND" and sample.get("sources") == []
             and all(k in sample and sample[k] is None for k in ("source_scope_ref", "interval_start", "interval_end_exclusive"))
             and future.get("value_read_authorized") is False and future.get("activation_authorized") is False,
             "LIST_A_BOUND_PROTECTION_SCOPE_UNRESOLVED", "LIST_A_PROTOCOL")
    add("LIST_A_PROTOCOL", "configs/list_a_chronological_confirmation_v1.yaml",
        {"schema": protocol["schema"], "schema_version": protocol["schema_version"], "sample_binding": sample,
         "future_execution_contract": future}, interpretation="UNBOUND_NO_CONFIRMATORY_GRANT_EXPLORATORY_LABELS_REQUIRED")
    _require([item["owner"] for item in frontier] == list(ROLES), "PROTECTION_SOURCE_SET_INCOMPLETE")
    # Assignment interpretation is validated above; a full inventory can carry
    # DENY entries. Per-mint native gates, not removal from denominator, decide.
    entries = sorted({canonical_sha256(e): e for e in entries}.values(), key=canonical_sha256)
    scope = _scope(root)
    context = {"contract": CONTRACT, "read_scope": scope, "source_set_sha256": canonical_sha256(config),
               "source_frontier": frontier, "effective_restrictions_sha256": canonical_sha256(entries)}
    return {**context, "context_sha256": canonical_sha256(context), "entries": entries, "scoped_restrictions": [task22],
            "assessment": {"status": ALLOW, "complete_empty": not entries,
                "boundary": "LOCAL_EPISODE_EXPLORATORY_ONLY; ADVISORY_SCOPE_UNKNOWN; NO_CONFIRMATORY_OR_SCOUT_GRANT"}}


def _snapshot(root: Path, repo: Path | None = None) -> dict[str, Any]:
    first = collect_current_sources(root, repo_root=repo)
    second = collect_current_sources(root, repo_root=repo)
    _require(first["context_sha256"] == second["context_sha256"], "PROTECTION_SOURCE_CHANGED", "SOURCE_SET")
    return second


def _head(root: Path) -> dict[str, Any] | None:
    path = _safe(root, POINTER)
    if not path.exists():
        return None
    pointer = _owned("LOCAL_ASSIGNMENTS", lambda: _json(path), source_ref=POINTER)
    unsigned = {k: v for k, v in pointer.items() if k != "pointer_sha256"}
    _require(pointer.get("contract") == CONTRACT and pointer.get("pointer_sha256") == canonical_sha256(unsigned),
             "CURRENT_PROTECTION_POINTER_INVALID", "LOCAL_ASSIGNMENTS", source_ref=POINTER)
    return pointer


def _installed(root: Path, snapshot: Mapping[str, Any], *, require_current_source_set: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    pointer = _head(root)
    _require(pointer is not None, "CURRENT_PROTECTION_NOT_INSTALLED", "LOCAL_ASSIGNMENTS", source_ref=POINTER)
    doc = _owned("LOCAL_ASSIGNMENTS", lambda: _json(_safe(root, pointer["assignment_ref"])), source_ref=pointer["assignment_ref"])
    _require(assignment_document_sha256(doc) == pointer["assignment_sha256"], "CURRENT_PROTECTION_RECEIPT_CHANGED")
    proof = doc.get("completeness") or {}
    _require(isinstance(proof, Mapping) and isinstance(doc.get("entries"), list), "CURRENT_PROTECTION_RECEIPT_INVALID", "LOCAL_ASSIGNMENTS")
    _require(doc.get("schema") == ASSIGNMENT_SCHEMA and doc.get("schema_version") == "1.0"
             and proof.get("complete") is True and proof.get("current_contract") == CONTRACT
             and proof.get("read_scope") == snapshot["read_scope"], "CURRENT_PROTECTION_BINDING_INVALID")
    if require_current_source_set:
        _require(proof.get("source_set_sha256") == snapshot["source_set_sha256"], "CURRENT_PROTECTION_SOURCE_SET_CHANGED")
    _require(_time(proof.get("checked_at")) <= datetime.now(UTC), "CURRENT_PROTECTION_TIME_INVALID")
    # The native namespaces are append-only. A previously evidenced source
    # cannot disappear, and baseline restrictions cannot be silently revoked.
    baseline = proof.get("source_frontier")
    _require(isinstance(baseline, list) and all(isinstance(item, Mapping) for item in baseline),
             "CURRENT_PROTECTION_RECEIPT_INVALID", "LOCAL_ASSIGNMENTS")
    fresh = {item["owner"]: item for item in snapshot["source_frontier"]}
    _require([item.get("owner") for item in baseline] == list(ROLES), "CURRENT_PROTECTION_RECEIPT_INVALID", "LOCAL_ASSIGNMENTS")
    for source in baseline:
        role = source["owner"]
        for key, identity in (("assignment_refs", "assignment_id"), ("declaration_refs", "record_id")):
            _require(isinstance(source.get(key, []), list) and all(isinstance(item, Mapping) for item in source.get(key, [])),
                     "CURRENT_PROTECTION_RECEIPT_INVALID", role)
            expected = {item[identity] for item in source.get(key, [])}
            present = {item[identity] for item in fresh[role].get(key, [])}
            _require(expected <= present, "PROTECTION_BASELINE_SOURCE_MISSING", role)
        if role == "EXPERIMENT_POLICIES":
            present_policies = {item["ref"]: item for item in fresh[role]["policy_refs"]}
            for item in source.get("policy_refs", []):
                ref = item["ref"]
                _require(ref in present_policies, "PROTECTION_BASELINE_SOURCE_MISSING", role, source_ref=ref)
                _require(present_policies[ref]["sha256"] == item["sha256"],
                         "PROTECTION_BASELINE_SOURCE_REPLACED", role, source_ref=ref)
    _require({canonical_sha256(entry) for entry in doc["entries"]} <=
             {canonical_sha256(entry) for entry in snapshot["entries"]},
             "PROTECTION_BASELINE_RESTRICTION_REMOVED", "LOCAL_ASSIGNMENTS")
    return pointer, doc


def resolve_current_research_protection(data_root: Path, *, repo_root: Path | None = None) -> tuple[dict[str, Any], ProtectionInventory]:
    """Read-only current admission. Historical complete=true cannot fill gaps."""
    try:
        root = Path(data_root)
        snapshot = _snapshot(root, repo_root)
        pointer, _doc = _installed(root, snapshot)
        ephemeral = {"schema": ASSIGNMENT_SCHEMA, "schema_version": "1.0", "interpretation_version": "1.0",
            "assignment_id": "CURRENT-RESEARCH-CONTEXT", "completeness": {"complete": True,
                "current_contract": CONTRACT, "read_scope": snapshot["read_scope"],
                "source_set_sha256": snapshot["source_set_sha256"],
                "effective_restrictions_sha256": canonical_sha256({"entries": snapshot["entries"],
                    "scoped_restrictions": snapshot["scoped_restrictions"]})}, "entries": snapshot["entries"]}
        inventory = inventory_from_documents([ephemeral])
        status = {"status": ALLOW, "reason": None, "sources": snapshot["source_frontier"],
            "inventory_sha256": inventory.fingerprint(), "context_sha256": snapshot["context_sha256"],
            "installed_assignment_sha256": pointer["assignment_sha256"], "complete_empty": not snapshot["entries"],
            "revalidation": "UNCHANGED" if _doc["completeness"]["context_sha256"] == snapshot["context_sha256"] else "REVALIDATED",
            "writes": False, "values_loaded": False, "read_scope": snapshot["read_scope"],
            "scoped_restrictions": snapshot["scoped_restrictions"],
            "permission_boundary": "COMPLETENESS_ONLY; EXACT_INPUT_AND_FROZEN_GATES_REQUIRED"}
        return status, inventory
    except (OSError, ValueError, KeyError, TypeError) as exc:
        error = exc if isinstance(exc, CurrentProtectionError) else CurrentProtectionError("PROTECTION_SOURCE_UNAVAILABLE")
        detail = error.detail
        return ({"status": "UNRESOLVED_SCOPE", "reason": error.code, **detail,
                 "sources": [], "complete_empty": None, "unresolved": [{"reason": error.code, **detail}],
                 "writes": False, "values_loaded": False},
                ProtectionInventory("UNRESOLVED_SCOPE", (), {}, error.code))


def _document(snapshot: Mapping[str, Any], *, checked_at: str, predecessor: str | None) -> dict[str, Any]:
    basis = canonical_sha256({"context": snapshot["context_sha256"], "checked_at": checked_at, "predecessor": predecessor})
    return {"schema": ASSIGNMENT_SCHEMA, "schema_version": "1.0", "interpretation_version": "1.0",
        "assignment_id": "CURRENT-RESEARCH-" + basis[:32].upper(), "owner": "OPPORTUNITY_EPISODES",
        "completeness": {"complete": True, "current_contract": CONTRACT, "checked_at": checked_at,
            "read_scope": snapshot["read_scope"], "source_set_sha256": snapshot["source_set_sha256"],
            "source_frontier": snapshot["source_frontier"], "context_sha256": snapshot["context_sha256"],
            "predecessor": predecessor, "boundary": snapshot["assessment"]["boundary"]}, "entries": snapshot["entries"]}


def preview_reconciliation(data_root: Path, *, repo_root: Path | None = None) -> dict[str, Any]:
    root = Path(data_root); snapshot = _snapshot(root, repo_root); head = _head(root)
    if head:
        pointer, existing = _installed(root, snapshot, require_current_source_set=False)
        if (existing["completeness"]["context_sha256"] == snapshot["context_sha256"]
                and existing["completeness"]["source_set_sha256"] == snapshot["source_set_sha256"]):
            return {"status": "UNCHANGED", "current": pointer, "assessment": snapshot["assessment"], "writes": False, "values_loaded": False}
    predecessor = head["pointer_sha256"] if head else None
    checked = datetime.now(UTC).isoformat()
    doc = _document(snapshot, checked_at=checked, predecessor=predecessor)
    proposal = {"contract": CONTRACT, "read_scope": snapshot["read_scope"], "source_set_sha256": snapshot["source_set_sha256"],
        "source_frontier": snapshot["source_frontier"], "context_sha256": snapshot["context_sha256"],
        "checked_at": checked, "predecessor": predecessor,
        "assignment_ref": ASSIGNMENT_DIR + "/" + doc["assignment_id"] + ".json",
        "assignment_sha256": assignment_document_sha256(doc)}
    return {"status": "PREVIEW_READY", "proposal": proposal, "proposal_sha256": canonical_sha256(proposal),
        "assessment": snapshot["assessment"], "writes": False, "values_loaded": False,
        "authority": "SEPARATE_EXACT_METADATA_ONLY_INSTALLATION_REQUIRED"}


def apply_reconciliation(store: ResearchStore, preview: Mapping[str, Any], *, authority: Mapping[str, Any],
                         repo_root: Path | None = None) -> dict[str, Any]:
    proposal = preview["proposal"]; digest = canonical_sha256(proposal)
    _require(digest == preview.get("proposal_sha256") and proposal.get("contract") == CONTRACT, "PROTECTION_PROPOSAL_CHANGED")
    _require(authority.get("proposal_sha256") == digest and authority.get("read_scope") == _scope(store.root)
             and authority.get("source_frontier_sha256") == canonical_sha256(proposal["source_frontier"])
             and authority.get("mutation") == "VERSIONED_PROTECTION_METADATA_ONLY"
             and isinstance(authority.get("owner_scope_ref"), str) and bool(authority["owner_scope_ref"].strip())
             and authority["owner_scope_ref"].strip() != "OWNER_APPROVAL_REQUIRED_NOT_GRANTED",
             "PROTECTION_INSTALLATION_AUTHORITY_REQUIRED", "INSTALLATION_AUTHORITY", source_ref="authority://" + CONTRACT)
    _require(_time(proposal["checked_at"]) <= datetime.now(UTC), "CURRENT_PROTECTION_TIME_INVALID")
    with store.writer_lease():
        snapshot = _snapshot(store.root, repo_root)
        _require(snapshot["read_scope"] == proposal["read_scope"] and snapshot["context_sha256"] == proposal["context_sha256"],
                 "PROTECTION_SOURCE_CHANGED", "SOURCE_SET")
        head = _head(store.root)
        if head and head.get("proposal_sha256") == digest:
            _installed(store.root, snapshot)
            return {"status": "ALREADY_APPLIED", "receipt": head, "values_loaded": False}
        _require((head["pointer_sha256"] if head else None) == proposal["predecessor"], "PROTECTION_HEAD_CHANGED", "LOCAL_ASSIGNMENTS")
        doc = _document(snapshot, checked_at=proposal["checked_at"], predecessor=proposal["predecessor"])
        _require(proposal["assignment_ref"] == ASSIGNMENT_DIR + "/" + doc["assignment_id"] + ".json"
                 and assignment_document_sha256(doc) == proposal["assignment_sha256"], "PROTECTION_PROPOSAL_CHANGED")
        raw = (json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        publish_immutable_artifact(store.root, proposal["assignment_ref"], raw)
        _require(_snapshot(store.root, repo_root)["context_sha256"] == snapshot["context_sha256"], "PROTECTION_SOURCE_CHANGED", "SOURCE_SET")
        _require((_head(store.root) or {}).get("pointer_sha256") == proposal["predecessor"], "PROTECTION_HEAD_CHANGED", "LOCAL_ASSIGNMENTS")
        pointer = {"contract": CONTRACT, "proposal_sha256": digest, "assignment_ref": proposal["assignment_ref"],
            "assignment_sha256": proposal["assignment_sha256"], "predecessor": proposal["predecessor"],
            "owner_scope_ref": authority["owner_scope_ref"]}
        pointer["pointer_sha256"] = canonical_sha256(pointer)
        target = _safe(store.root, POINTER); temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".current-", suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write((json.dumps(pointer, sort_keys=True, allow_nan=False) + "\n").encode()); handle.flush(); os.fsync(handle.fileno())
            os.replace(temporary, target)
            _require(_head(store.root) == pointer, "PROTECTION_PUBLICATION_UNVERIFIED")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return {"status": "APPLIED", "receipt": pointer, "values_loaded": False}


def with_frozen_protection(current: ProtectionInventory, documents) -> ProtectionInventory:
    """Keep current completeness and every immutable admission restriction."""
    if current.status != ALLOW:
        return current
    frozen = inventory_from_documents(documents)
    if frozen.status != ALLOW:
        return frozen
    identities = set(current.entries) | set(frozen.entries)
    return ProtectionInventory(ALLOW, (*current.sources, *frozen.sources),
        {key: (*current.entries.get(key, ()), *frozen.entries.get(key, ())) for key in identities}, None)


def assert_input_scope(status: Mapping[str, Any], bindings) -> None:
    """Prove the non-mint legacy restriction is disjoint before exact values.

    TASK-22 is a dataset/batch restriction, never an invented global mint ban.
    A native episode input with overlapping information time needs an explicit
    source linkage; different collection names alone cannot prove disjointness.
    """
    from datetime import timedelta
    from solana_alpha_lab.factory.opportunity_episodes import cohort_day_bounds, LOGICAL_DATASET_ID
    _require(status.get("status") == ALLOW, "CURRENT_PROTECTION_UNRESOLVED")
    for restriction in status["scoped_restrictions"]:
        _require(restriction.get("applicability") == "TASK21_FROZEN_DATASET_ONLY_NOT_GLOBAL_MINT_BAN",
                 "PROTECTION_RESTRICTION_VERSION_UNKNOWN", "TASK22_ACCEPTED_SPLIT")
        start, end = _time(restriction["selection_at"]), _time(restriction["labels_available_at"])
        _require(start < end, "PROTECTION_RESTRICTION_SCOPE_INVALID", "TASK22_ACCEPTED_SPLIT")
        for item in bindings:
            _require(item.get("dataset_id") == LOGICAL_DATASET_ID and item.get("evidence_role") == "EXPLORATORY_REUSE",
                     "PROTECTION_INPUT_SCOPE_UNKNOWN")
            try:
                first, last = cohort_day_bounds(item["cohort_id"])
            except (KeyError, ValueError):
                raise CurrentProtectionError("PROTECTION_INPUT_SCOPE_UNKNOWN") from None
            if first - timedelta(days=1) < end and start < last + timedelta(days=4):
                raise CurrentProtectionError("TASK22_SOURCE_OVERLAP_LINK_UNRESOLVED", owner="TASK22_ACCEPTED_SPLIT")
