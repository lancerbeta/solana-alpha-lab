"""Shared zero-network PathRisk live-window fixtures for successor identity tests."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from solana_alpha_lab.factory.pathrisk_calibration import TERMINAL_BELOW_FLOOR, load_policy
from solana_alpha_lab.factory.pathrisk_live import (
    REPLACEMENT_REASON_PRE_EVIDENCE_OPERATIONAL_FAILURE,
    render_successor_owner_phrase,
    resolve_live_window_identity,
    runtime_live_dir,
)

ACT_001 = "ACT-PATHRISK-LIVE-001"
ACT_002 = "ACT-PATHRISK-LIVE-002"
ACT_003 = "ACT-PATHRISK-LIVE-003"
ACT_004 = "ACT-PATHRISK-LIVE-004"


def successor_identity(
    *,
    activation_id: str = ACT_003,
    predecessor_activation_id: str = ACT_002,
    policy=None,
):
    return resolve_live_window_identity(
        policy or load_policy(ROOT),
        activation_id,
        predecessor_activation_id,
    )


def successor_phrase(
    *,
    activation_id: str = ACT_003,
    predecessor_activation_id: str = ACT_002,
    policy=None,
) -> str:
    loaded = policy or load_policy(ROOT)
    return render_successor_owner_phrase(
        loaded,
        successor_identity(
            activation_id=activation_id,
            predecessor_activation_id=predecessor_activation_id,
            policy=loaded,
        ),
    )


def seed_window_journal(
    data_root: Path,
    *,
    activation_id: str,
    stage: str,
    terminal: str | None = None,
    predecessor_activation_id: str | None = None,
    replacement_reason: str | None = None,
    extra: dict | None = None,
    binding_activation_id: str | None = None,
) -> Path:
    directory = runtime_live_dir(data_root, activation_id)
    directory.mkdir(parents=True, exist_ok=True)
    payload: dict = {"stage": stage}
    if terminal is not None:
        payload["terminal"] = terminal
    if predecessor_activation_id is not None:
        payload["activation_id"] = activation_id
        payload["predecessor_activation_id"] = predecessor_activation_id
        payload["replacement_reason"] = replacement_reason
        payload["resume_of_predecessor"] = False
    if extra:
        payload.update(extra)
    (directory / "journal.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    bind_id = binding_activation_id if binding_activation_id is not None else activation_id
    (directory / "runtime_binding.json").write_text(
        json.dumps(
            {
                "activation_id": bind_id,
                "schedule_sha256": "fixture-binding",
                "starts_at": "2026-08-31T12:00:00Z",
                "stops_admitting_at": "2026-08-31T12:03:00Z",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (directory / "runtime_schedule.yaml").write_text(
        "schedule_key: OBS-EARLY-QUOTE-SURFACE-PATHRISK-LIVE-001\n",
        encoding="utf-8",
    )
    return directory


def seed_act001_recent_done(data_root: Path) -> Path:
    return seed_window_journal(
        data_root,
        activation_id=ACT_001,
        stage="RECENT_DONE",
        extra={"predecessor_canary": "ACT-001-ONLY"},
    )


def seed_act002_below_floor(data_root: Path) -> Path:
    return seed_window_journal(
        data_root,
        activation_id=ACT_002,
        stage="BELOW_FLOOR",
        terminal=TERMINAL_BELOW_FLOOR,
        predecessor_activation_id=ACT_001,
        replacement_reason=REPLACEMENT_REASON_PRE_EVIDENCE_OPERATIONAL_FAILURE,
    )


def ensure_act002_below_floor(data_root: Path) -> Path:
    journal = Path(data_root) / "pathrisk_live" / ACT_002 / "journal.json"
    if journal.is_file():
        return journal.parent
    return seed_act002_below_floor(data_root)


def live_identity_kwargs(
    *,
    activation_id: str = ACT_003,
    predecessor_activation_id: str = ACT_002,
) -> dict[str, str]:
    return {
        "activation_id": activation_id,
        "predecessor_activation_id": predecessor_activation_id,
    }
