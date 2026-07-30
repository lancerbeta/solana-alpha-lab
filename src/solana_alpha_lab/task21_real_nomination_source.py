"""Offline replay of retained TASK-21 T1 nomination source evidence."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.task21_live_shakedown import (
    Task21LiveShakedownError,
    validate_recovery_freshness,
)
from solana_alpha_lab.task21_real_nomination import canonical_json_bytes

TASK_ID = "TASK-21"
PARENT_ATOM_ID = "T21-A6S_BOUNDED_REAL_NOMINATION_AND_COLLECTION_LAUNCH_V1"
SOURCE_ATOM_ID = "T21-A6S_T1_SOURCE_RESELECTION_V1"
ATOM_ID = "T21-A6S_T1_TOKEN2022_REPLAY_AND_BACKUP_V1"
STAGE = "T1_ONLY"
EXTERNAL_AUTHORITY_PHRASE = ATOM_ID
SOURCE_VERSION = "DEXSCREENER-LATEST-PROFILES-SOLANA-RPC-MINT-V1.1"
COHORT_ID = "DEXSCREENER_LATEST_PROFILE_SOLANA_CONTROL_ONLY"
HYPOTHESIS_ID = "HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1"
WATCHLIST_POLICY_VERSION = "1.0"
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
DEXSCREENER_URL = "https://api.dexscreener.com/token-profiles/latest/v1"
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
ALLOWED_TOKEN_PROGRAMS = frozenset({TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID})
REFERENCE_MINTS = frozenset(
    {
        "So11111111111111111111111111111111111111112",
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    }
)


class Task21NominationSourceError(RuntimeError):
    """The frozen replay or retained-evidence boundary was violated."""


class Task21NominationSourceAuthorityRequired(Task21NominationSourceError):
    """The exact replay authority phrase is absent or invalid."""


@dataclass(frozen=True, slots=True)
class Task21NominationSourceGate:
    authority_phrase: str

    def __post_init__(self) -> None:
        if self.authority_phrase != EXTERNAL_AUTHORITY_PHRASE:
            raise Task21NominationSourceAuthorityRequired(
                "task21_t1_token2022_replay_authority_phrase_mismatch"
            )


@dataclass(frozen=True, slots=True)
class StructuralCandidate:
    mint: str
    mint_decimals: int
    token_program: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "mint": self.mint,
            "mint_decimals": self.mint_decimals,
            "token_program": self.token_program,
        }


@dataclass(frozen=True, slots=True)
class T1ReplayResult:
    partition_path: Path
    partition_sha256: str
    partition_bytes: int
    nomination_count: int
    anchor_at: str
    t1_close_at: str
    retained_partition_sha256: str

    def safe_receipt(self, repo_root: Path) -> dict[str, Any]:
        return {
            "schema": "smial.task21.t1-token2022-replay-safe-receipt",
            "schema_version": "1.0",
            "task_id": TASK_ID,
            "parent_atom_id": PARENT_ATOM_ID,
            "source_atom_id": SOURCE_ATOM_ID,
            "atom_id": ATOM_ID,
            "stage": STAGE,
            "status": "LOCAL_DERIVED_PARTITION_READY_FOR_EXACT_DRIVE_BACKUP",
            "partition_path": self.partition_path.relative_to(repo_root).as_posix(),
            "partition_sha256": self.partition_sha256,
            "partition_bytes": self.partition_bytes,
            "retained_partition_sha256": self.retained_partition_sha256,
            "provider_api_rpc_wss_calls_this_stage": 0,
            "task21_external_requests_cumulative": 4,
            "real_candidate_nominations": self.nomination_count,
            "real_candidate_admissions": 0,
            "jupiter_api_calls": 0,
            "wss_calls": 0,
            "cash_spend_usd_cents": 0,
            "credentials_used": 0,
            "drive_writes": 0,
            "drive_reads_by_local_replay": 0,
            "scheduler_or_background_process": False,
            "wallet_signer_transaction_actions": 0,
            "anchor_at": self.anchor_at,
            "t1_close_at": self.t1_close_at,
        }


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task21NominationSourceError("config_root_must_be_mapping")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Task21NominationSourceError("json_root_must_be_mapping")
    return value


def _utc_text(value: datetime) -> str:
    return (
        value.astimezone(UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _decode_base58(value: str) -> bytes | None:
    number = 0
    for character in value:
        index = BASE58_ALPHABET.find(character)
        if index < 0:
            return None
        number = number * 58 + index
    width = (number.bit_length() + 7) // 8
    payload = number.to_bytes(width, "big") if width else b""
    leading_zeros = len(value) - len(value.lstrip("1"))
    return b"\x00" * leading_zeros + payload


def _valid_solana_pubkey(value: object) -> bool:
    if not isinstance(value, str) or not 32 <= len(value) <= 44:
        return False
    decoded = _decode_base58(value)
    return decoded is not None and len(decoded) == 32


def validate_config(config: Mapping[str, Any], repo_root: Path) -> None:
    if (
        config.get("task_id") != TASK_ID
        or config.get("parent_atom_id") != PARENT_ATOM_ID
        or config.get("source_atom_id") != SOURCE_ATOM_ID
        or config.get("atom_id") != ATOM_ID
        or config.get("stage") != STAGE
        or config.get("status") != "FROZEN_TOKEN2022_REPLAY_AND_BACKUP_BOUNDARY"
    ):
        raise Task21NominationSourceError("config_identity_or_status_drift")
    authority = config.get("authority")
    expected_authority = {
        "gate_phrase": EXTERNAL_AUTHORITY_PHRASE,
        "provider_api_rpc_wss_calls": 0,
        "dexscreener_api_calls": 0,
        "solana_public_rpc_calls": 0,
        "jupiter_api_calls": 0,
        "wss_calls": 0,
        "old_drive_raw_inline_readbacks_max": 1,
        "local_derived_partition_writes_max": 1,
        "new_drive_file_uploads_max": 1,
        "new_drive_metadata_readbacks_max": 1,
        "new_drive_raw_readbacks_max": 1,
        "real_candidate_nominations_max": 3,
        "real_candidate_admissions": 0,
        "credentials": 0,
        "cash_spend_usd_cents": 0,
        "retries": 0,
        "concurrency": 1,
        "scheduler_or_background_process": False,
        "wallet_signer_transaction_actions": 0,
        "commit": False,
        "push": False,
        "pull_request": False,
        "merge": False,
        "destructive_actions": False,
    }
    if not isinstance(authority, Mapping) or any(
        authority.get(key) != value for key, value in expected_authority.items()
    ):
        raise Task21NominationSourceError("authority_cap_drift")
    source = config.get("source")
    profile = source.get("profile_endpoint") if isinstance(source, Mapping) else None
    rpc = source.get("mint_validation_rpc") if isinstance(source, Mapping) else None
    if (
        not isinstance(source, Mapping)
        or source.get("cohort_id") != COHORT_ID
        or source.get("authentication") != "NONE"
        or not isinstance(profile, Mapping)
        or profile.get("url") != DEXSCREENER_URL
        or not isinstance(rpc, Mapping)
        or rpc.get("url") != SOLANA_RPC_URL
        or rpc.get("method") != "getMultipleAccounts"
        or rpc.get("data_slice") != {"offset": 0, "length": 82}
    ):
        raise Task21NominationSourceError("source_contract_drift")
    selection = config.get("selection")
    if (
        not isinstance(selection, Mapping)
        or selection.get("nomination_source_class")
        != "PREDECLARED_CONTROL_COHORT"
        or selection.get("cohort_id") != COHORT_ID
        or selection.get("tranche_id") != "T1"
        or selection.get("target_nomination_count") != 3
        or selection.get("rpc_candidate_mints_max") != 100
        or set(selection.get("allowed_token_programs", []))
        != ALLOWED_TOKEN_PROGRAMS
        or set(selection.get("excluded_mints", [])) != REFERENCE_MINTS
    ):
        raise Task21NominationSourceError("selection_contract_drift")
    replay = config.get("replay")
    retained = (
        replay.get("retained_source_partition")
        if isinstance(replay, Mapping)
        else None
    )
    if (
        not isinstance(replay, Mapping)
        or replay.get("network_calls") != 0
        or replay.get("output_root") != "local/task21_forward/t1_replay"
        or replay.get("write_behavior") != "CREATE_ONLY_CONTENT_ADDRESSED"
        or not isinstance(retained, Mapping)
        or not isinstance(retained.get("path"), str)
        or not retained["path"].startswith("local/task21_forward/t1_nomination/")
        or not isinstance(retained.get("sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", retained["sha256"]) is None
        or isinstance(retained.get("bytes"), bool)
        or not isinstance(retained.get("bytes"), int)
        or retained["bytes"] <= 0
        or not isinstance(retained.get("drive_file_id"), str)
        or not retained["drive_file_id"]
        or retained.get("drive_exact_raw_readback") is not True
    ):
        raise Task21NominationSourceError("retained_partition_contract_drift")
    budget = config.get("budget_reconciliation")
    if (
        not isinstance(budget, Mapping)
        or budget.get("accepted_task21_external_request_ceiling") != 192
        or budget.get("source_requests_whole_task_max") != 8
        or budget.get("quote_requests_whole_task_max") != 184
        or budget.get("external_requests_consumed_before_replay") != 4
        or budget.get("external_requests_in_replay") != 0
        or 8 + 184 != 192
    ):
        raise Task21NominationSourceError("budget_reconciliation_drift")
    frozen = config.get("frozen_inputs")
    if not isinstance(frozen, list) or not frozen:
        raise Task21NominationSourceError("frozen_inputs_missing")
    for item in frozen:
        if not isinstance(item, Mapping):
            raise Task21NominationSourceError("frozen_input_invalid")
        relative = item.get("path")
        expected = item.get("sha256")
        if (
            not isinstance(relative, str)
            or not isinstance(expected, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected) is None
        ):
            raise Task21NominationSourceError("frozen_input_identity_invalid")
        actual = sha256_file(repo_root / relative)
        if actual != expected:
            raise Task21NominationSourceError(
                f"frozen_input_hash_drift:{relative}:{expected}:{actual}"
            )


def validate_recovery_destination(
    receipt: Mapping[str, Any],
    *,
    now: datetime,
) -> str:
    try:
        validate_recovery_freshness(receipt, now=now)
    except Task21LiveShakedownError as exc:
        raise Task21NominationSourceError(str(exc)) from exc
    drive = receipt.get("google_drive")
    folder = drive.get("folder") if isinstance(drive, Mapping) else None
    if not isinstance(folder, Mapping):
        raise Task21NominationSourceError("recovery_drive_folder_missing")
    folder_id = folder.get("id")
    if (
        not isinstance(folder_id, str)
        or not folder_id
        or folder.get("name") != "SOLANA_ALPHA_LAB_TASK21_RECOVERY_V1"
        or folder.get("shared") is not False
        or folder.get("visibility") != "not_shared"
    ):
        raise Task21NominationSourceError("recovery_drive_folder_drift")
    return folder_id


def select_profile_mints(
    *,
    profile_document: object,
    config: Mapping[str, Any],
) -> list[str]:
    """Select only Solana mint identities; marketing fields remain sealed."""

    if not isinstance(profile_document, list):
        raise Task21NominationSourceError("dexscreener_profile_root_invalid")
    rows_max = config["source"]["profile_endpoint"]["response_rows_max"]
    if len(profile_document) > rows_max:
        raise Task21NominationSourceError("dexscreener_profile_row_cap_exceeded")
    mints: set[str] = set()
    for row in profile_document:
        if not isinstance(row, Mapping) or row.get("chainId") != "solana":
            continue
        mint = row.get("tokenAddress")
        if _valid_solana_pubkey(mint) and mint not in REFERENCE_MINTS:
            mints.add(mint)
    return sorted(mints)[: config["selection"]["rpc_candidate_mints_max"]]


def _mint_header_decimals(raw: bytes) -> int | None:
    if len(raw) != 82:
        return None
    mint_authority_option = int.from_bytes(raw[0:4], "little")
    freeze_authority_option = int.from_bytes(raw[46:50], "little")
    if mint_authority_option not in {0, 1}:
        return None
    if mint_authority_option == 0 and any(raw[4:36]):
        return None
    if freeze_authority_option not in {0, 1}:
        return None
    if freeze_authority_option == 0 and any(raw[50:82]):
        return None
    if raw[45] != 1 or raw[44] > 30:
        return None
    return raw[44]


def validate_rpc_mints(
    *,
    rpc_document: object,
    requested_mints: Sequence[str],
    config: Mapping[str, Any],
) -> tuple[list[StructuralCandidate], int]:
    """Validate legacy and Token-2022 owners against the common Mint header."""

    if not isinstance(rpc_document, Mapping) or rpc_document.get("id") != 1:
        raise Task21NominationSourceError("solana_rpc_root_or_id_invalid")
    if "error" in rpc_document:
        raise Task21NominationSourceError("solana_rpc_returned_error")
    result = rpc_document.get("result")
    if not isinstance(result, Mapping):
        raise Task21NominationSourceError("solana_rpc_result_missing")
    context = result.get("context")
    values = result.get("value")
    if (
        not isinstance(context, Mapping)
        or isinstance(context.get("slot"), bool)
        or not isinstance(context.get("slot"), int)
        or not isinstance(values, list)
        or len(values) != len(requested_mints)
    ):
        raise Task21NominationSourceError("solana_rpc_result_shape_invalid")
    allowed_programs = set(config["selection"]["allowed_token_programs"])
    valid: list[StructuralCandidate] = []
    for mint, account in zip(requested_mints, values, strict=True):
        if not isinstance(account, Mapping):
            continue
        owner = account.get("owner")
        data = account.get("data")
        space = account.get("space")
        if (
            owner not in allowed_programs
            or account.get("executable") is not False
            or isinstance(space, bool)
            or not isinstance(space, int)
            or space < 82
            or (owner == TOKEN_PROGRAM_ID and space != 82)
            or not isinstance(data, list)
            or len(data) != 2
            or data[1] != "base64"
            or not isinstance(data[0], str)
        ):
            continue
        try:
            raw = base64.b64decode(data[0], validate=True)
        except (ValueError, base64.binascii.Error):
            continue
        decimals = _mint_header_decimals(raw)
        if decimals is None:
            continue
        valid.append(
            StructuralCandidate(
                mint=mint,
                mint_decimals=decimals,
                token_program=owner,
            )
        )
        if len(valid) == config["selection"]["target_nomination_count"]:
            break
    return valid, context["slot"]


def _rpc_request_bytes(mints: Sequence[str]) -> bytes:
    return canonical_json_bytes(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getMultipleAccounts",
            "params": [
                list(mints),
                {
                    "commitment": "finalized",
                    "encoding": "base64",
                    "dataSlice": {"offset": 0, "length": 82},
                },
            ],
        }
    )


def _decode_capture(
    capture: object,
    *,
    expected_kind: str,
) -> tuple[bytes, bytes]:
    if not isinstance(capture, Mapping):
        raise Task21NominationSourceError("retained_capture_invalid")
    if (
        capture.get("request_kind") != expected_kind
        or capture.get("status") != 200
    ):
        raise Task21NominationSourceError("retained_capture_identity_or_status_drift")
    try:
        request_body = base64.b64decode(
            capture["request_body_base64"],
            validate=True,
        )
        response_body = base64.b64decode(
            capture["response_body_base64"],
            validate=True,
        )
    except (KeyError, TypeError, ValueError, base64.binascii.Error) as exc:
        raise Task21NominationSourceError("retained_capture_base64_invalid") from exc
    if (
        len(request_body) != capture.get("request_bytes")
        or sha256_bytes(request_body) != capture.get("request_sha256")
        or len(response_body) != capture.get("response_bytes")
        or sha256_bytes(response_body) != capture.get("response_sha256")
    ):
        raise Task21NominationSourceError("retained_capture_hash_or_size_drift")
    return request_body, response_body


def _json_bytes(name: str, raw: bytes) -> object:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Task21NominationSourceError(f"{name}_invalid_json") from exc


def _load_retained_partition(
    *,
    repo_root: Path,
    config: Mapping[str, Any],
) -> tuple[dict[str, Any], bytes, str]:
    retained = config["replay"]["retained_source_partition"]
    path = repo_root / retained["path"]
    raw = path.read_bytes()
    actual_sha256 = sha256_bytes(raw)
    if len(raw) != retained["bytes"] or actual_sha256 != retained["sha256"]:
        raise Task21NominationSourceError("retained_partition_hash_or_size_drift")
    try:
        partition = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Task21NominationSourceError("retained_partition_invalid_json") from exc
    if (
        not isinstance(partition, dict)
        or partition.get("schema") != "smial.task21.t1-nomination-partition"
        or partition.get("task_id") != TASK_ID
        or partition.get("atom_id") != SOURCE_ATOM_ID
        or partition.get("status") != "T1_SOURCE_INSUFFICIENT_STOPPED"
        or partition.get("contains_secrets") is not False
    ):
        raise Task21NominationSourceError("retained_partition_identity_drift")
    observation = partition.get("source_observation")
    observation_sha = partition.get("source_observation_sha256")
    if (
        not isinstance(observation, dict)
        or not isinstance(observation_sha, str)
        or sha256_bytes(canonical_json_bytes(observation)) != observation_sha
    ):
        raise Task21NominationSourceError("retained_source_observation_hash_drift")
    return partition, raw, actual_sha256


def build_nomination_events(
    *,
    selected: Sequence[StructuralCandidate],
    replayed_at: datetime,
    source_observation_sha256: str,
) -> list[dict[str, Any]]:
    source_observation_id = f"T21-DSRPC-T1-{source_observation_sha256[:20]}"
    source_asset_id = f"SOURCE-T21-DSRPC-T1-{source_observation_sha256[:20]}"
    replayed_text = _utc_text(replayed_at)
    events: list[dict[str, Any]] = []
    for ordinal, candidate in enumerate(selected, start=1):
        identity_payload = {
            "ordinal": ordinal,
            "mint": candidate.mint,
            "source_observation_sha256": source_observation_sha256,
            "replayed_at": replayed_text,
        }
        event_suffix = sha256_bytes(canonical_json_bytes(identity_payload))[:12]
        program_reason = (
            "TOKEN_2022_MINT"
            if candidate.token_program == TOKEN_2022_PROGRAM_ID
            else "LEGACY_SPL_TOKEN_MINT"
        )
        events.append(
            {
                "nomination_event_id": f"T21-T1-NOM-{ordinal:03d}-{event_suffix}",
                "source_asset_id": source_asset_id,
                "source_version": SOURCE_VERSION,
                "source_content_sha256": source_observation_sha256,
                "observed_at": replayed_text,
                "first_reliable_available_at": replayed_text,
                "hypothesis_version_id": HYPOTHESIS_ID,
                "watchlist_policy_version": WATCHLIST_POLICY_VERSION,
                "exact_rule_input_values": {
                    "mint": candidate.mint,
                    "mint_decimals": candidate.mint_decimals,
                    "nomination_source_class": "PREDECLARED_CONTROL_COHORT",
                    "tranche_id": "T1",
                    "source_observation_id": source_observation_id,
                    "selection_basis_codes": [
                        "DEXSCREENER_LATEST_PROFILE_SOLANA_SET",
                        "DETERMINISTIC_MINT_ASC",
                        "RPC_TOKEN_PROGRAM_AND_MINT_HEADER_VERIFIED",
                    ],
                    "prior_relevant_quote_outcome_exposure": False,
                    "uses_task21_quote_route_or_price_outcome": False,
                },
                "reason_codes": [
                    "PREDECLARED_CONTROL_COHORT",
                    COHORT_ID,
                    program_reason,
                    "STRUCTURAL_IDENTITY_AND_MINT_HEADER_ONLY",
                    "T1_FORWARD_NOMINATION",
                ],
                "evidence_checkpoint": f"sha256:{source_observation_sha256}",
            }
        )
    return events


def _preflight_disk(repo_root: Path, required_after_write: int) -> None:
    if shutil.disk_usage(repo_root).free <= required_after_write:
        raise Task21NominationSourceError("disk_pressure_blocks_t1_replay")


def replay_t1_from_retained_partition(
    *,
    gate: Task21NominationSourceGate,
    repo_root: Path,
    config_path: Path,
    recovery_receipt_path: Path,
    now: datetime,
) -> T1ReplayResult:
    """Create one T1 partition from retained responses without network calls."""

    if not isinstance(gate, Task21NominationSourceGate):
        raise Task21NominationSourceAuthorityRequired(
            "task21_t1_token2022_replay_gate_required"
        )
    if now.tzinfo is None or now.utcoffset() is None:
        raise Task21NominationSourceError("runtime_now_must_be_timezone_aware")
    replayed_at = now.astimezone(UTC)
    config = _load_yaml(config_path)
    validate_config(config, repo_root)
    recovery = _load_json(recovery_receipt_path)
    validate_recovery_destination(recovery, now=replayed_at)
    _preflight_disk(repo_root, config["runtime"]["min_free_space_bytes_after_write"])
    output_root = repo_root / config["replay"]["output_root"]
    if output_root.exists() and any(output_root.iterdir()):
        raise Task21NominationSourceError("t1_replay_output_already_exists")

    source_partition, source_raw, source_partition_sha = _load_retained_partition(
        repo_root=repo_root,
        config=config,
    )
    observation = source_partition["source_observation"]
    captures = observation.get("captures")
    if not isinstance(captures, list) or len(captures) != 2:
        raise Task21NominationSourceError("retained_capture_count_drift")
    dex_request, dex_response = _decode_capture(
        captures[0],
        expected_kind="DEXSCREENER_LATEST_TOKEN_PROFILES",
    )
    rpc_request, rpc_response = _decode_capture(
        captures[1],
        expected_kind="SOLANA_GET_MULTIPLE_ACCOUNTS",
    )
    if dex_request != b"":
        raise Task21NominationSourceError("retained_dex_request_body_not_empty")
    profile_document = _json_bytes("retained_dex_response", dex_response)
    requested_mints = select_profile_mints(
        profile_document=profile_document,
        config=config,
    )
    if rpc_request != _rpc_request_bytes(requested_mints):
        raise Task21NominationSourceError("retained_rpc_request_contract_drift")
    rpc_document = _json_bytes("retained_rpc_response", rpc_response)
    selected, rpc_context_slot = validate_rpc_mints(
        rpc_document=rpc_document,
        requested_mints=requested_mints,
        config=config,
    )
    if len(selected) != config["selection"]["target_nomination_count"]:
        raise Task21NominationSourceError(
            "retained_responses_still_insufficient_for_three_nominations"
        )
    source_observation_sha = source_partition["source_observation_sha256"]
    nomination_events = build_nomination_events(
        selected=selected,
        replayed_at=replayed_at,
        source_observation_sha256=source_observation_sha,
    )
    t1_close = replayed_at + timedelta(days=7)
    derived = {
        "schema": "smial.task21.t1-token2022-replay-partition",
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "parent_atom_id": PARENT_ATOM_ID,
        "source_atom_id": SOURCE_ATOM_ID,
        "atom_id": ATOM_ID,
        "stage": STAGE,
        "status": "T1_NOMINATIONS_FROZEN_AWAITING_CLOSE",
        "cohort_id": COHORT_ID,
        "claim_scope": COHORT_ID,
        "contains_market_data": True,
        "contains_secrets": False,
        "source_partition_lineage": {
            "path": config["replay"]["retained_source_partition"]["path"],
            "bytes": len(source_raw),
            "sha256": source_partition_sha,
            "drive_file_id": (
                config["replay"]["retained_source_partition"]["drive_file_id"]
            ),
            "drive_exact_raw_readback": True,
        },
        "retained_source_observation": deepcopy(observation),
        "source_observation_sha256": source_observation_sha,
        "rpc_context_slot": rpc_context_slot,
        "structural_projection": [item.as_dict() for item in selected],
        "nomination_events": nomination_events,
        "timeline": {
            "source_capture_completed_at": captures[-1]["captured_at"],
            "replayed_at": _utc_text(replayed_at),
            "anchor_at": _utc_text(replayed_at),
            "t1_close_at": _utc_text(t1_close),
            "backdating_allowed": False,
            "evaluation_before_t1_close_allowed": False,
            "quote_collection_before_t1_close_allowed": False,
        },
        "actual_actions": {
            "provider_api_rpc_wss_calls_this_stage": 0,
            "dexscreener_api_calls_this_stage": 0,
            "solana_public_rpc_calls_this_stage": 0,
            "task21_external_requests_cumulative": 4,
            "real_candidate_nominations": len(nomination_events),
            "real_candidate_admissions": 0,
            "jupiter_api_calls": 0,
            "wss_calls": 0,
            "local_derived_partition_writes": 1,
            "drive_writes": 0,
            "credentials_used": 0,
            "cash_spend_usd_cents": 0,
            "scheduler_or_background_process": False,
            "wallet_signer_transaction_actions": 0,
        },
        "backup": {
            "status": "PENDING_EXACT_CREATE_ONLY_DRIVE_BACKUP",
            "object_count_required": 1,
            "exact_raw_readback_required": True,
        },
        "next_boundary": {
            "atom_id": (
                "T21-A6S_T1_CLOSE_EVALUATION_AND_"
                "BOUNDED_PANEL_CAPTURE_V1"
            ),
            "earliest_at": _utc_text(t1_close),
            "authorized": False,
        },
        "non_claims": [
            "NO_MARKET_WIDE_REPRESENTATIVENESS_CLAIM",
            "NO_ALPHA_CLAIM",
            "NO_WATCHLIST_ADMISSION",
            "NO_JUPITER_QUOTE_OR_ROUTE_CHECK",
            "NO_TRADE_OR_POSITION_ACTION",
            "NO_SOURCE_API_OR_RPC_CALL_DURING_REPLAY",
        ],
    }
    derived_bytes = canonical_json_bytes(derived)
    derived_sha = sha256_bytes(derived_bytes)
    filename = f"TASK21_T1_TOKEN2022_REPLAY_PARTITION_v1_{derived_sha}.json"
    output_root.mkdir(parents=True, exist_ok=True)
    partition_path = output_root / filename
    try:
        with partition_path.open("xb") as handle:
            handle.write(derived_bytes)
    except FileExistsError as exc:
        raise Task21NominationSourceError(
            "t1_replay_partition_already_exists"
        ) from exc
    return T1ReplayResult(
        partition_path=partition_path,
        partition_sha256=derived_sha,
        partition_bytes=len(derived_bytes),
        nomination_count=len(nomination_events),
        anchor_at=_utc_text(replayed_at),
        t1_close_at=_utc_text(t1_close),
        retained_partition_sha256=source_partition_sha,
    )


def build_offline_acceptance(
    *,
    repo_root: Path,
    config_path: Path,
    fixture_path: Path,
) -> dict[str, Any]:
    config = _load_yaml(config_path)
    validate_config(config, repo_root)
    fixture = _load_json(fixture_path)
    profiles = fixture.get("dexscreener_response")
    rpc = fixture.get("solana_rpc_response")
    if (
        fixture.get("synthetic_only") is not True
        or fixture.get("contains_market_data") is not False
        or not isinstance(profiles, list)
        or not isinstance(rpc, Mapping)
    ):
        raise Task21NominationSourceError("offline_fixture_scope_invalid")
    requested = select_profile_mints(profile_document=profiles, config=config)
    selected, slot = validate_rpc_mints(
        rpc_document=rpc,
        requested_mints=requested,
        config=config,
    )
    mutated = deepcopy(profiles)
    mutated.reverse()
    for row in mutated:
        if isinstance(row, dict):
            row["url"] = "https://ignored.invalid/changed"
            row["icon"] = "https://ignored.invalid/icon"
            row["header"] = "https://ignored.invalid/header"
            row["description"] = "changed"
            row["links"] = [{"label": "changed", "url": "https://ignored.invalid"}]
    changed_requested = select_profile_mints(
        profile_document=mutated,
        config=config,
    )
    stable = requested == changed_requested
    by_program: dict[str, int] = {}
    for item in selected:
        by_program[item.token_program] = by_program.get(item.token_program, 0) + 1
    return {
        "schema": "smial.task21.real-nomination-source-offline-receipt",
        "schema_version": "1.1",
        "task_id": TASK_ID,
        "parent_atom_id": PARENT_ATOM_ID,
        "source_atom_id": SOURCE_ATOM_ID,
        "atom_id": ATOM_ID,
        "stage": STAGE,
        "status": "PASS" if len(selected) == 3 and stable else "FAIL",
        "cohort_id": COHORT_ID,
        "synthetic_only": True,
        "contains_market_data": False,
        "rpc_context_slot": slot,
        "rpc_candidate_count": len(requested),
        "selected_count": len(selected),
        "selected_by_program": dict(sorted(by_program.items())),
        "selected_structural_candidates": [item.as_dict() for item in selected],
        "selection_ignores_profile_marketing_fields": stable,
        "selection_ignores_response_order": stable,
        "mint_header_requires_initialized_state": True,
        "legacy_requires_exact_82_byte_account": True,
        "token2022_requires_program_owner_and_valid_82_byte_mint_header": True,
        "actual_actions": {
            "network_calls": 0,
            "provider_api_rpc_wss_calls": 0,
            "drive_reads": 0,
            "drive_writes": 0,
            "real_candidate_nominations": 0,
            "real_candidate_admissions": 0,
            "cash_spend_usd_cents": 0,
            "credentials_used": 0,
            "wallet_signer_transaction_actions": 0,
        },
    }
