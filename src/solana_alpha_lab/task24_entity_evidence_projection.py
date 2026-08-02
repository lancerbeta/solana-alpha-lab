"""Deterministic offline TASK-24 projection from frozen TASK-11 raw evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from solana_alpha_lab.entity_input_replay import replay_entity_probe
from solana_alpha_lab.entity_input_transport import (
    load_entity_pilot_plan,
    parse_largest_accounts,
    parse_owner_accounts,
    parse_token_supply,
)
from solana_alpha_lab.storage import canonical_raw_event_rows_bytes
from solana_alpha_lab.storage.parquet_store import _events_from_table


PRE_READ_MANIFEST_SHA256 = (
    "f889c0f28d3259cc61681ba6cc56dc53686d2375ce98826ca572dc5d5720846d"
)
PROJECTION_SCHEMA_VERSION = "1.0"
RULE_VERSION = "TASK24_GRAPH_PROJECTION_V1.0"
PSEUDONYM_NAMESPACE = "TASK24_ENTITY_GRAPH_V1"
ALLOWED_EDGE_TYPES = frozenset(
    {"RAW_TOKEN_ACCOUNT_FOR_MINT", "RAW_TOKEN_ACCOUNT_OWNER"}
)


class Task24ProjectionError(ValueError):
    """Frozen inputs or projected claims violate the TASK-24 boundary."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Task24ProjectionError(message)


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _canonical_jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical_json_bytes(row) for row in rows)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Task24ProjectionError("json_input_invalid") from exc
    _require(isinstance(value, Mapping), "json_input_must_be_mapping")
    return value


def _iso(value: datetime) -> str:
    _require(
        value.tzinfo is not None and value.utcoffset() is not None,
        "timestamp_must_be_aware",
    )
    return value.isoformat()


def _stable_digest(node_type: str, raw_public_key: str) -> str:
    material = f"{PSEUDONYM_NAMESPACE}|{node_type}|{raw_public_key}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _node(
    *,
    node_type: str,
    raw_public_key: str,
    event: Any,
    quality_flags: Sequence[str],
) -> dict[str, Any]:
    digest = _stable_digest(node_type, raw_public_key)
    payload: dict[str, Any] = {
        "node_id": f"t24-{node_type.lower().replace('_', '-')}-{digest}",
        "node_type": node_type,
        "business_key": f"{node_type}:{digest}",
        "event_at": _iso(event.event_time),
        "observed_at": _iso(event.observed_at),
        "first_reliable_available_at": _iso(
            event.first_reliable_available_at
        ),
        "available_to_strategy_at": _iso(event.available_to_strategy_at),
        "ingested_at": _iso(event.ingested_at),
        "source": event.source,
        "source_version": event.source_version,
        "evidence_class": "RAW_ONCHAIN",
        "revision_number": event.revision_number,
        "revision_of": event.revision_of,
        "quality_flags": sorted(set(quality_flags)),
    }
    payload["content_sha256"] = _sha256_bytes(_canonical_json_bytes(payload))
    return payload


def _edge(
    *,
    edge_type: str,
    source_node: Mapping[str, Any],
    target_node: Mapping[str, Any],
    event: Any,
    quality_flags: Sequence[str],
) -> dict[str, Any]:
    _require(edge_type in ALLOWED_EDGE_TYPES, "edge_type_not_allowed_in_a3")
    identity_material = "|".join(
        (
            RULE_VERSION,
            edge_type,
            str(source_node["node_id"]),
            str(target_node["node_id"]),
            event.raw_event_id,
        )
    )
    edge_digest = hashlib.sha256(identity_material.encode("utf-8")).hexdigest()
    payload: dict[str, Any] = {
        "edge_id": f"t24-edge-{edge_digest}",
        "source_node_id": source_node["node_id"],
        "source_node_type": source_node["node_type"],
        "target_node_id": target_node["node_id"],
        "target_node_type": target_node["node_type"],
        "edge_type": edge_type,
        "evidence_class": "RAW_ONCHAIN",
        "confidence_class": "DIRECT",
        "rule_version": RULE_VERSION,
        "supporting_raw_event_ids": [event.raw_event_id],
        "supporting_edge_ids": [],
        "event_at": _iso(event.event_time),
        "observed_at": _iso(event.observed_at),
        "first_reliable_available_at": _iso(
            event.first_reliable_available_at
        ),
        "available_to_strategy_at": _iso(event.available_to_strategy_at),
        "ingested_at": _iso(event.ingested_at),
        "source": event.source,
        "source_version": event.source_version,
        "revision_number": event.revision_number,
        "revision_of": event.revision_of,
        "quality_flags": sorted(set(quality_flags)),
        "conflict_set_id": None,
    }
    payload["content_sha256"] = _sha256_bytes(_canonical_json_bytes(payload))
    return payload


def _verify_manifest_inputs(
    *, repo_root: Path, manifest: Mapping[str, Any]
) -> dict[str, Path]:
    _require(manifest["status"] == "PASS_ADMISSIBLE_LOCAL_INPUTS", "manifest_not_pass")
    gate = manifest["projection_gate"]
    _require(gate["admissible_local_inputs"] is True, "inputs_not_admissible")
    _require(
        gate["projection_authorized"] == "PARTIAL_RAW_RELATIONS_ONLY",
        "projection_authority_drift",
    )
    boundary = manifest["no_r3_no_outcome_assertion"]
    for key in (
        "r3_paths_allowed",
        "outcome_fields_allowed",
        "strategy_identity_allowed",
        "pnl_netreturn_cashflow_allowed",
        "future_labels_allowed",
    ):
        _require(boundary[key] is False, f"forbidden_boundary_enabled:{key}")
    authority = manifest["authority"]
    _require(authority["offline_local_value_read"] is True, "offline_read_not_authorized")
    for key in (
        "provider_api_rpc_wss_calls",
        "credential_uses",
        "r3_or_outcome_reads",
        "wallet_signer_transaction_actions",
        "cash_spend_usd_cents",
        "dependency_changes",
        "catalog_or_registry_mutation",
    ):
        _require(authority[key] == 0, f"external_authority_enabled:{key}")
    scope = manifest["scope"]
    _require(
        set(scope["allowed_projection"]) == ALLOWED_EDGE_TYPES,
        "allowed_projection_drift",
    )
    privacy = manifest["privacy_and_output_policy"]
    _require(
        privacy["raw_owner_addresses_may_be_persisted_in_git"] is False,
        "owner_address_persistence_enabled",
    )
    _require(
        privacy["raw_token_account_addresses_may_be_persisted_in_git"] is False,
        "token_account_address_persistence_enabled",
    )

    resolved_root = repo_root.resolve()
    result: dict[str, Path] = {}
    for item in manifest["inputs"]:
        role = item["role"]
        _require(role not in result, "duplicate_input_role")
        relative = Path(item["exact_local_path"])
        _require(not relative.is_absolute(), "absolute_input_path_forbidden")
        lowered_parts = {part.lower() for part in relative.parts}
        _require("r3" not in lowered_parts, "r3_input_path_forbidden")
        _require("outcomes" not in lowered_parts, "outcome_input_path_forbidden")
        path = repo_root / relative
        resolved = path.resolve()
        _require(resolved.is_relative_to(resolved_root), "input_escapes_repository")
        _require(path.is_file() and not path.is_symlink(), "input_missing_or_unsafe")
        data = path.read_bytes()
        _require(len(data) == item["bytes"], f"input_size_drift:{role}")
        _require(_sha256_bytes(data) == item["sha256"], f"input_hash_drift:{role}")
        result[role] = path
    _require(
        set(result)
        == {
            "PILOT_PLAN",
            "RUNTIME_RECEIPT",
            "TOKEN_SUPPLY_RAW_EVENT",
            "LARGEST_TOKEN_ACCOUNTS_RAW_EVENT",
            "TOKEN_ACCOUNT_OWNER_RAW_EVENT",
        },
        "input_roles_drift",
    )
    return result


def _load_raw_event(path: Path, expected: Mapping[str, Any]) -> Any:
    try:
        rows = _events_from_table(pq.ParquetFile(path).read())
    except Exception as exc:
        raise Task24ProjectionError("raw_partition_decode_failed") from exc
    _require(len(rows) == 1, "raw_partition_row_count_drift")
    event = rows[0]
    content_sha256 = _sha256_bytes(canonical_raw_event_rows_bytes(rows))
    _require(content_sha256 == expected["content_sha256"], "raw_content_hash_drift")
    _require(event.raw_event_id == expected["raw_event_id"], "raw_event_id_drift")
    _require(event.endpoint_or_method == expected["method"], "raw_method_drift")
    return event


def _write_bytes(output_dir: Path, name: str, value: bytes) -> Path:
    path = output_dir / name
    resolved_dir = output_dir.resolve()
    resolved_path = path.resolve()
    _require(resolved_path.is_relative_to(resolved_dir), "output_path_escape")
    _require(not path.is_symlink(), "output_symlink_forbidden")
    path.write_bytes(value)
    return path


def _artifact_record(repo_root: Path, path: Path, rows: int | None) -> dict[str, Any]:
    data = path.read_bytes()
    record: dict[str, Any] = {
        "path": path.relative_to(repo_root).as_posix(),
        "bytes": len(data),
        "sha256": _sha256_bytes(data),
    }
    if rows is not None:
        record["rows"] = rows
    return record


def build_task24_projection(
    *, repo_root: Path, manifest_path: Path, output_dir: Path
) -> Mapping[str, Any]:
    """Validate frozen bytes, read allowed values, and write sanitized outputs."""

    repo_root = repo_root.resolve()
    manifest_path = manifest_path.resolve()
    output_dir = output_dir.resolve()
    _require(manifest_path.is_relative_to(repo_root), "manifest_outside_repository")
    _require(output_dir.is_relative_to(repo_root), "output_outside_repository")
    _require(_sha256_file(manifest_path) == PRE_READ_MANIFEST_SHA256, "manifest_hash_drift")
    manifest = _load_json(manifest_path)
    paths = _verify_manifest_inputs(repo_root=repo_root, manifest=manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    _require(not output_dir.is_symlink(), "output_directory_symlink_forbidden")

    plan = load_entity_pilot_plan(paths["PILOT_PLAN"])
    scope = manifest["scope"]
    _require(plan.dataset_id == scope["dataset_id"], "dataset_id_drift")
    _require(plan.dataset_version == scope["dataset_version"], "dataset_version_drift")
    _require(plan.selected_mint == scope["selected_mint"], "selected_mint_drift")

    replay = replay_entity_probe(
        raw_root=(repo_root / "data/raw").resolve(),
        plan=plan,
        run_id=scope["run_id"],
    )
    input_by_role = {item["role"]: item for item in manifest["inputs"]}
    supply_event = _load_raw_event(
        paths["TOKEN_SUPPLY_RAW_EVENT"], input_by_role["TOKEN_SUPPLY_RAW_EVENT"]
    )
    largest_event = _load_raw_event(
        paths["LARGEST_TOKEN_ACCOUNTS_RAW_EVENT"],
        input_by_role["LARGEST_TOKEN_ACCOUNTS_RAW_EVENT"],
    )
    owner_event = _load_raw_event(
        paths["TOKEN_ACCOUNT_OWNER_RAW_EVENT"],
        input_by_role["TOKEN_ACCOUNT_OWNER_RAW_EVENT"],
    )
    supply = parse_token_supply(
        supply_event.redacted_body,
        expected_id=1,
        expected_decimals=plan.selected_mint_decimals,
    )
    largest = parse_largest_accounts(
        largest_event.redacted_body,
        expected_id=2,
        expected_decimals=plan.selected_mint_decimals,
    )
    owners = parse_owner_accounts(
        owner_event.redacted_body,
        expected_id=3,
        expected_mint=plan.selected_mint,
        expected_accounts=largest.accounts,
    )
    _require(len(largest.accounts) == replay["top_account_count"], "top_account_count_drift")
    _require(len(owners.owners) == replay["owner_resolution_count"], "owner_count_drift")
    _require(supply.amount_atomic == replay["supply_atomic"], "supply_drift")

    nodes_by_id: dict[str, dict[str, Any]] = {}
    mint_node = _node(
        node_type="TOKEN_MINT",
        raw_public_key=plan.selected_mint,
        event=supply_event,
        quality_flags=("CURRENT_FORWARD_ONLY", "RAW_REQUEST_BOUND_MINT"),
    )
    nodes_by_id[mint_node["node_id"]] = mint_node
    edges: list[dict[str, Any]] = []
    for account, owner in zip(largest.accounts, owners.owners, strict=True):
        _require(account.address == owner.token_account, "owner_join_account_drift")
        token_node = _node(
            node_type="TOKEN_ACCOUNT",
            raw_public_key=account.address,
            event=largest_event,
            quality_flags=("CURRENT_FORWARD_ONLY", "TOP20_ACCOUNT"),
        )
        wallet_node = _node(
            node_type="WALLET",
            raw_public_key=owner.owner,
            event=owner_event,
            quality_flags=("CURRENT_FORWARD_ONLY", "TOKEN_ACCOUNT_OWNER_FIELD"),
        )
        nodes_by_id[token_node["node_id"]] = token_node
        nodes_by_id[wallet_node["node_id"]] = wallet_node
        edges.append(
            _edge(
                edge_type="RAW_TOKEN_ACCOUNT_FOR_MINT",
                source_node=token_node,
                target_node=mint_node,
                event=largest_event,
                quality_flags=("CURRENT_FORWARD_ONLY", "REQUEST_BOUND_MINT"),
            )
        )
        edges.append(
            _edge(
                edge_type="RAW_TOKEN_ACCOUNT_OWNER",
                source_node=token_node,
                target_node=wallet_node,
                event=owner_event,
                quality_flags=("CURRENT_FORWARD_ONLY", "OWNER_FIELD_AT_OBSERVED_SLOT"),
            )
        )

    nodes = sorted(nodes_by_id.values(), key=lambda row: (row["node_type"], row["node_id"]))
    edges.sort(key=lambda row: (row["edge_type"], row["edge_id"]))
    _require(len(nodes) == 41, "node_count_drift")
    _require(len(edges) == 40, "edge_count_drift")
    _require(
        {edge["edge_type"] for edge in edges} == ALLOWED_EDGE_TYPES,
        "projected_edge_set_drift",
    )

    candidates: dict[str, Any] = {
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "status": "NOT_TESTABLE_NO_ADMISSIBLE_LINKAGE_EVIDENCE",
        "records": [],
        "missing_evidence": [
            "DEPLOYER",
            "IMMEDIATE_FUNDER",
            "ULTIMATE_FUNDER",
            "AUTHORITATIVE_BUNDLE_ID",
            "COMMON_OWNERSHIP_CORROBORATION",
        ],
        "vendor_or_project_inferences_created": 0,
    }
    adjusted: dict[str, Any] = {
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "status": "NOT_AVAILABLE_EXCLUSION_INVENTORY_INCOMPLETE",
        "raw_top_accounts_supply_share": replay["raw_top_accounts_supply_share"],
        "adjusted_top_accounts_supply_share": None,
        "exclusion_inventory_complete": False,
        "unresolved_exclusion_account_count": replay[
            "unresolved_exclusion_account_count"
        ],
        "raw_metric_preserved": True,
        "holder_exclusions_changed": 0,
    }

    nodes_path = _write_bytes(
        output_dir, "entity_nodes_v1.jsonl", _canonical_jsonl_bytes(nodes)
    )
    edges_path = _write_bytes(
        output_dir, "entity_edges_v1.jsonl", _canonical_jsonl_bytes(edges)
    )
    candidates_path = _write_bytes(
        output_dir, "entity_candidates_v1.json", _canonical_json_bytes(candidates)
    )
    adjusted_path = _write_bytes(
        output_dir,
        "entity_adjusted_concentration_v1.json",
        _canonical_json_bytes(adjusted),
    )
    artifacts = {
        "entity_nodes_v1": _artifact_record(repo_root, nodes_path, len(nodes)),
        "entity_edges_v1": _artifact_record(repo_root, edges_path, len(edges)),
        "entity_candidates_v1": _artifact_record(repo_root, candidates_path, 0),
        "entity_adjusted_concentration_v1": _artifact_record(
            repo_root, adjusted_path, 1
        ),
    }
    projection_manifest: dict[str, Any] = {
        "manifest_id": "T24-A3-DETERMINISTIC-ENTITY-EVIDENCE-PROJECTION-001",
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "task_id": "TASK-24",
        "atom": "T24-A3_DETERMINISTIC_ENTITY_EVIDENCE_FEASIBILITY_AND_PROJECTION_V1",
        "as_of": manifest["as_of"],
        "status": "PASS_PARTIAL_RAW_RELATION_PROJECTION",
        "pre_read_manifest_sha256": PRE_READ_MANIFEST_SHA256,
        "input_dataset_id": scope["dataset_id"],
        "input_run_id": scope["run_id"],
        "pseudonym_rule": manifest["privacy_and_output_policy"][
            "stable_pseudonym_rule"
        ],
        "raw_public_addresses_persisted": 0,
        "counts": {
            "nodes": len(nodes),
            "token_mints": sum(row["node_type"] == "TOKEN_MINT" for row in nodes),
            "token_accounts": sum(
                row["node_type"] == "TOKEN_ACCOUNT" for row in nodes
            ),
            "wallets": sum(row["node_type"] == "WALLET" for row in nodes),
            "edges": len(edges),
            "raw_token_account_for_mint": sum(
                row["edge_type"] == "RAW_TOKEN_ACCOUNT_FOR_MINT" for row in edges
            ),
            "raw_token_account_owner": sum(
                row["edge_type"] == "RAW_TOKEN_ACCOUNT_OWNER" for row in edges
            ),
            "entity_candidates": 0,
        },
        "artifacts": artifacts,
        "owner_decision": "EXTEND_EVIDENCE",
        "not_testable": [
            "DEPLOYER",
            "IMMEDIATE_OR_ULTIMATE_FUNDER",
            "BUNDLE_MEMBERSHIP",
            "COMMON_OWNERSHIP",
            "FALSE_POSITIVE_AUDIT",
            "ADJUSTED_CONCENTRATION",
        ],
        "non_claims": [
            "OWNERSHIP_TRUTH",
            "INSIDER_OR_BUNDLER_GROUND_TRUTH",
            "STRATEGY_VETO",
            "ALPHA_OR_GENERALIZATION",
            "EXECUTION_PNL_NETRETURN_OR_CASHFLOW",
            "TASK24_DONE",
        ],
        "authority": {
            "provider_api_rpc_wss_calls": 0,
            "credential_uses": 0,
            "r3_or_outcome_reads": 0,
            "wallet_signer_transaction_actions": 0,
            "cash_spend_usd_cents": 0,
        },
    }
    manifest_path_out = _write_bytes(
        output_dir,
        "projection_manifest_v1.json",
        _canonical_json_bytes(projection_manifest),
    )
    return {
        "status": projection_manifest["status"],
        "owner_decision": projection_manifest["owner_decision"],
        "projection_manifest": _artifact_record(repo_root, manifest_path_out, 1),
        "counts": projection_manifest["counts"],
    }
