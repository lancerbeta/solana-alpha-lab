"""Forward-only TASK-21 Finish Gate read model after accepted A8 delivery."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from solana_alpha_lab.task21_final_owner_pulse import build_final_owner_pulse


JsonObject = dict[str, Any]


class T21FinishGateError(RuntimeError):
    """The post-A8 Finish Gate truth is missing or internally inconsistent."""


def _load_json(path: Path) -> JsonObject:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise T21FinishGateError(f"json_root_not_mapping:{path.as_posix()}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_t21_finish_gate_pulse(
    *,
    repository_root: Path,
    as_of: datetime | None = None,
    free_disk_bytes: int | None = None,
) -> JsonObject:
    root = repository_root.resolve()
    observed_at = (as_of or datetime.now(UTC)).astimezone(UTC)
    pulse = copy.deepcopy(
        build_final_owner_pulse(
            repository_root=root,
            as_of=observed_at,
            free_disk_bytes=free_disk_bytes,
        )
    )
    marker_path = root / "control/active_time_gates.json"
    acceptance_path = root / "docs/evidence/task21/a7_acceptance_catalog_factory_fit_v1.json"
    marker = _load_json(marker_path)
    acceptance = _load_json(acceptance_path)
    router = marker.get("resume_router")
    if not isinstance(router, dict):
        raise T21FinishGateError("resume_router_missing")
    if router.get("status") != "A8_MERGED_PENDING_TASK21_FINISH_SOURCE_ACTIVATION":
        raise T21FinishGateError("post_a8_router_status_missing")
    delivery = router.get("a8_resolution")
    if not isinstance(delivery, dict) or delivery.get("status") != "MERGED_MAIN_CI_PASS":
        raise T21FinishGateError("a8_delivery_not_accepted")
    if delivery.get("task22_started") is not False:
        raise T21FinishGateError("task22_state_not_closed")
    if acceptance.get("status") != "PASS":
        raise T21FinishGateError("a7_acceptance_missing")
    if acceptance["product_vision_reconciliation"]["terminal_result"] != (
        "CANONICALIZED_WITH_PATCH"
    ):
        raise T21FinishGateError("product_vision_terminal_result_missing")

    pulse.update(
        {
            "schema": "smial.task21.finish-gate-owner-pulse",
            "schema_version": "1.0",
            "read_model_id": "OWNER-PULSE-T21-FINISH-001",
            "atom_id": "TASK21_FINISH_GATE_RECONCILIATION_V1",
            "as_of": observed_at.isoformat().replace("+00:00", "Z"),
            "active_time_gates": [],
            "attention": [
                {
                    "severity": "INFO",
                    "code": "A8_MERGED_PENDING_FINISH_SOURCE_ACTIVATION",
                    "action": "ACTIVATE_TASK21_FINISH_SOURCE_BUNDLE_AND_RUN_SMOKE",
                }
            ],
        }
    )
    pulse["task21_forward_state"].update(
        {
            "state": "A8_MERGED_PENDING_FINISH_SOURCE_ACTIVATION",
            "task22_started": False,
        }
    )
    pulse["repository_delivery"] = copy.deepcopy(delivery)
    pulse["recovery_and_storage"].update(
        {
            "dataset_freeze_state": "A7_ACCEPTED_AND_A8_MERGED",
            "analysis_promotion_blocker": (
                "TASK21_FINISH_SOURCE_ACTIVATION_THEN_TASK22_ENTRY_GATE"
            ),
        }
    )
    pulse["a7_acceptance"].update(
        {
            "next_atom": "TASK21_FINISH_SOURCE_ACTIVATION_AND_SMOKE",
            "next_atom_authorized": False,
            "task22_eligible_after_finish": True,
        }
    )
    pulse["finish_gate"] = {
        "status": "FINALIZATION_REQUIRED_PENDING_PROJECT_SOURCE_ACTIVATION",
        "factory_fit": "PASS_WITH_DURABLE_FOLLOWUPS",
        "product_vision_terminal_result": "CANONICALIZED_WITH_PATCH",
        "source_activation": "PENDING_REPLACEMENT_BUNDLE_AND_USER_SMOKE",
        "task22_started": False,
        "evidence_sources": [
            {"path": marker_path.relative_to(root).as_posix(), "sha256": _sha256(marker_path)},
            {
                "path": acceptance_path.relative_to(root).as_posix(),
                "sha256": _sha256(acceptance_path),
            },
        ],
    }
    return pulse


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def render_t21_finish_gate_text(pulse: JsonObject) -> str:
    delivery = pulse["repository_delivery"]
    state = pulse["task21_forward_state"]
    return "\n".join(
        [
            "TASK-21: A8 смерджен, main CI прошёл; код и frozen dataset приняты.",
            (
                f"Repository: PR #{delivery['pull_request']} / main "
                f"{delivery['merge_commit']} / tree {delivery['merge_tree']}."
            ),
            f"Dataset: {state['owner_verdict']}.",
            "Следующий шаг: активировать replacement bundle постоянной памяти и получить SMOKE=PASS.",
            "TASK-22 не запущен; read model не выдаёт внешнюю authority.",
        ]
    ) + "\n"
