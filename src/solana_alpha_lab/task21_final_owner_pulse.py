"""Final TASK-21 owner pulse overlay over accepted A7 truth."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from solana_alpha_lab.task21_owner_pulse import build_owner_pulse


JsonObject = dict[str, Any]


class Task21FinalOwnerPulseError(RuntimeError):
    """Final accepted evidence is missing or internally inconsistent."""


def _load_json(path: Path) -> JsonObject:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise Task21FinalOwnerPulseError(f"json_root_not_mapping:{path.as_posix()}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_final_owner_pulse(
    *,
    repository_root: Path,
    as_of: datetime | None = None,
    free_disk_bytes: int | None = None,
) -> JsonObject:
    root = repository_root.resolve()
    observed_at = (as_of or datetime.now(UTC)).astimezone(UTC)
    base = build_owner_pulse(
        repository_root=root,
        as_of=observed_at,
        free_disk_bytes=free_disk_bytes,
    )
    relative_paths = {
        "freeze": "docs/evidence/task21/final_dataset_freeze_manifest_v1.json",
        "sample": "docs/evidence/task21/effective_sample_summary_v1.json",
        "recovery": "docs/evidence/task21/final_dataset_recovery_acceptance_v1.json",
        "acceptance": "docs/evidence/task21/a7_acceptance_catalog_factory_fit_v1.json",
    }
    documents = {key: _load_json(root / value) for key, value in relative_paths.items()}
    if documents["freeze"].get("status") != "FROZEN_ACCEPTED_LOCAL_CANDIDATE":
        raise Task21FinalOwnerPulseError("dataset_not_frozen")
    if documents["sample"].get("status") != "PASS_WITH_LIMITATIONS":
        raise Task21FinalOwnerPulseError("effective_sample_not_accepted")
    if documents["recovery"].get("status") != "PASS_REMOTE_RECOVERY_PROVEN":
        raise Task21FinalOwnerPulseError("remote_recovery_not_proven")
    if documents["acceptance"].get("status") != "PASS":
        raise Task21FinalOwnerPulseError("a7_not_accepted")
    if documents["freeze"]["source_inventory_sha256"] != (
        documents["recovery"]["full_dataset"]["source_inventory_sha256"]
    ):
        raise Task21FinalOwnerPulseError("freeze_recovery_identity_drift")

    pulse = copy.deepcopy(base)
    pulse.update(
        {
            "schema": "smial.task21.final-owner-pulse",
            "schema_version": "1.0",
            "read_model_id": "OWNER-PULSE-T21-FINAL-001",
            "atom_id": "T21-A7_DATASET_FREEZE_ACCEPTANCE_CATALOG_FACTORY_FIT_V1",
            "as_of": observed_at.isoformat().replace("+00:00", "Z"),
            "truth_ownership": "DERIVED_READ_MODEL_ONLY",
            "active_time_gates": [],
            "attention": [
                {
                    "severity": "INFO",
                    "code": "A7_ACCEPTED_PENDING_REPOSITORY_DELIVERY",
                    "action": "AUTHORIZE_T21_A8_REPOSITORY_DELIVERY",
                }
            ],
        }
    )
    pulse["evidence_sources"] = [
        {"path": relative, "sha256": _sha256(root / relative)}
        for relative in relative_paths.values()
    ]
    pulse["task21_forward_state"] = {
        "state": "A7_ACCEPTED_LOCAL_CANDIDATE_PENDING_A8",
        "dataset_inventory_sha256": documents["freeze"]["source_inventory_sha256"],
        "local_dataset_bytes": documents["freeze"]["stored_bytes"],
        "real_nominations": 8,
        "real_admissions": 8,
        "complete_members": 5,
        "complete_member_clusters": 2,
        "panels_captured": 22,
        "quote_pairs": 88,
        "quote_attempts": 176,
        "explicit_missing_panels": 3,
        "outcomes_opened": False,
        "owner_verdict": documents["sample"]["owner_verdict"],
        "task22_started": False,
    }
    pulse["cost_and_authority"] = {
        "collection_external_requests_used": 184,
        "collection_external_requests_cap": 192,
        "separate_shakedown_requests": 8,
        "task21_provider_api_rpc_wss_calls_total": 192,
        "modeled_quote_credits": 184,
        "provider_billed_credit_claim": "NOT_AVAILABLE_KEYLESS_NO_ACCOUNT",
        "received_bytes_total": 348741,
        "drive_reads_historical": 34,
        "drive_writes_historical": 6,
        "cash_spend_usd_cents": 0,
        "credentials_or_permission_changes": 0,
        "wallet_signer_transaction_actions": 0,
        "external_authority_granted_by_pulse": False,
    }
    pulse["recovery_and_storage"] = {
        "health_state": "FINAL_DATASET_REMOTE_RECOVERY_PROVEN",
        "dataset_freeze_state": "A7_ACCEPTED_LOCAL_CANDIDATE",
        "dataset_freeze_allowed": True,
        "dataset_analysis_promotion_allowed": False,
        "analysis_promotion_blocker": "A8_AND_TASK21_FINISH_GATE_THEN_TASK22_ENTRY_GATE",
        "archive_sha256": documents["recovery"]["content_addressed_archive"]["sha256"],
        "remote_file_id": documents["recovery"]["google_drive"]["file"]["id"],
        "exact_remote_readback": True,
        "isolated_full_restore": True,
        "restored_file_count": documents["recovery"]["isolated_restore"]["restored_file_count"],
        "alerts": [],
    }
    pulse["a7_acceptance"] = {
        "status": "PASS",
        "factory_fit": documents["acceptance"]["factory_fit"]["verdict"],
        "catalog_version": documents["acceptance"]["catalog"]["version"],
        "product_vision_terminal_result": documents["acceptance"]
        ["product_vision_reconciliation"]["terminal_result"],
        "next_atom": "T21-A8_REPOSITORY_DELIVERY_V1",
        "next_atom_authorized": False,
        "task22_eligible_after_finish": True,
    }
    pulse["side_effects"] = {
        "network_calls": 0,
        "provider_api_rpc_wss_calls": 0,
        "drive_reads": 0,
        "drive_writes": 0,
        "raw_or_dataset_writes": 0,
        "cash_spend_usd_cents": 0,
        "credentials_used": 0,
        "wallet_signer_transaction_actions": 0,
        "scheduler_or_background_process": False,
    }
    return pulse


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def render_final_owner_pulse_text(pulse: JsonObject) -> str:
    state = pulse["task21_forward_state"]
    recovery = pulse["recovery_and_storage"]
    return "\n".join(
        [
            "TASK-21: A7 принят локально; следующий шаг — отдельное разрешение A8.",
            (
                "Dataset: 91 файл / 1 263 895 байт / 5 полных участников "
                "в 2 кластерах / 22 панели / 88 пар котировок."
            ),
            f"Вердикт: {state['owner_verdict']}.",
            (
                "Recovery: "
                f"{recovery['health_state']}; remote read-back и полный restore PASS."
            ),
            "Ограничение: не market-wide, не cross-regime, не alpha и не NetReturn.",
            "Внешняя authority этим read model не выдаётся; TASK-22 не запущен.",
        ]
    ) + "\n"
