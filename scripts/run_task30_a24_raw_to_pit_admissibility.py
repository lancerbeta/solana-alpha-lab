#!/usr/bin/env python3
"""Execute the authorized TASK-30 A24 offline raw-to-PIT admissibility panel."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_raw_to_pit_admissibility import (  # noqa: E402
    A24Error,
    ATOM_ID,
    execute_admissibility,
    load_policy,
    sha256_bytes,
    write_local_projection,
    _canonical_json,
    _format_utc,
)

AUTHORITY_PHRASE = "OK T30-A24 RAW_TO_PIT_ADMISSIBILITY_OWNER_PANEL"
CONFIG_PATH = ROOT / "configs/task30_a24_raw_to_pit_admissibility_owner_panel_v1.yaml"
RUNTIME_RECEIPT_PATH = (
    ROOT / "docs/evidence/task30/a24_raw_to_pit_admissibility_runtime_receipt_v1.json"
)
ACCEPTANCE_PATH = (
    ROOT / "docs/evidence/task30/a24_raw_to_pit_admissibility_acceptance_v1.json"
)
READOUT_PATH = (
    ROOT / "docs/reports/task30/a24_raw_to_pit_admissibility_owner_readout_v1.md"
)


def _run_id(measured: datetime, identity_sha: str) -> str:
    stamp = measured.strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{identity_sha[:8]}"


def main() -> int:
    policy = load_policy(CONFIG_PATH)
    if policy["external_authority"]["owner_phrase"] != AUTHORITY_PHRASE:
        raise A24Error("OWNER_PHRASE_DRIFT")
    bindings = policy["input_bindings"]
    a22_path = ROOT / bindings["a22_raw"]["path"]
    a23_path = ROOT / bindings["a23_terminal_page"]["path"]
    a22_payload = a22_path.read_bytes()
    a23_payload = a23_path.read_bytes()
    measured = datetime.now(UTC).replace(microsecond=0)
    result = execute_admissibility(
        repo_root=ROOT,
        policy=policy,
        a22_payload=a22_payload,
        a23_payload=a23_payload,
        measured_as_of=measured,
    )
    identity_sha = sha256_bytes(
        (result["identity"]["a22_sha256"] + result["identity"]["a23_sha256"]).encode()
    )
    run_id = _run_id(measured, identity_sha)
    local_root = ROOT / policy["retention"]["raw_root"] / f"run={run_id}"
    local_paths = write_local_projection(result, local_root, repo_root=ROOT)
    runtime = {
        "schema": "smial.task30.a24-raw-to-pit-admissibility.runtime",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "observed_at": _format_utc(measured),
        "terminal_decision": result["terminal_decision"],
        "identity": result["identity"],
        "reconciliation": result["reconciliation"],
        "pit": result["pit"],
        "decision": result["decision"],
        "claims": result["claims"],
        "side_effects": result["side_effects"],
        "local_projection": local_paths,
        "slot_state_counts": _slot_counts(result["panel_96_slots"]),
    }
    RUNTIME_RECEIPT_PATH.write_bytes(_canonical_json(runtime))
    acceptance = {
        "schema": "smial.task30.a24-raw-to-pit-admissibility.acceptance",
        "schema_version": "1.0",
        "receipt_id": "EVIDENCE-T30-A24-RAW-TO-PIT-001",
        "task_id": "TASK-30",
        "atom_id": ATOM_ID,
        "as_of": "2026-08-15",
        "decision": result["terminal_decision"],
        "task_state": "BLOCKED_DATA",
        "named_consumer": "RC001-H07-H01-LIQUIDITY-RETENTION",
        "runtime_receipt_sha256": sha256_bytes(RUNTIME_RECEIPT_PATH.read_bytes()),
        "identity": result["identity"],
        "reconciliation": result["reconciliation"],
        "pit": result["pit"],
        "slot_state_counts": runtime["slot_state_counts"],
        "limitations": result["decision"].get("limitations"),
        "provider_gap": result["decision"].get("provider_gap"),
        "project_sources_disposition": {"kind": "NO_CHANGE"},
        "claims": result["claims"],
        "side_effects": result["side_effects"],
        "non_claims": [
            "NO_TASK30_ACCEPTANCE",
            "NO_H07_H01_TRIAL",
            "NO_ALPHA",
            "NO_FORWARD_FILL",
            "NO_MISSING_TO_ZERO",
        ],
    }
    ACCEPTANCE_PATH.write_bytes(_canonical_json(acceptance))
    READOUT_PATH.write_text(_readout(runtime, acceptance), encoding="utf-8")
    print(json.dumps({"terminal_decision": result["terminal_decision"], "run_id": run_id}, sort_keys=True))
    return 0


def _slot_counts(panel: object) -> dict[str, int]:
    counts = {
        "OBSERVED_TARGET_TRADES": 0,
        "PROVEN_NO_TARGET_TRADE": 0,
        "STATE_PERSISTENCE_PROVEN": 0,
        "UNKNOWN_COVERAGE": 0,
    }
    if not isinstance(panel, list):
        return counts
    for item in panel:
        if isinstance(item, dict) and item.get("state") in counts:
            counts[str(item["state"])] += 1
    return counts


def _readout(runtime: dict[str, object], acceptance: dict[str, object]) -> str:
    recon = runtime["reconciliation"]
    slots = runtime["slot_state_counts"]
    decision = str(runtime["terminal_decision"])
    lines = [
        "# TASK-30 A24 — решение по admissibility raw→PIT",
        "",
        f"**Терминальное решение:** `{decision}`",
        "",
        "Уже оплаченный нулём batch превращён в типизированную 96-слотовую панель.",
        "Это не trial, не alpha и не принятие TASK-30.",
        "",
        "## Покрытие",
        "",
        f"- Транзакции: `{recon.get('successful_transactions')}`",
        f"- Target buy/sell: `{recon.get('target_buy_events')}` / `{recon.get('target_sell_events')}`",
        f"- Other-pool trades (исключения): `{recon.get('other_pool_trade_events')}`",
        f"- CloseUserVolumeAccumulatorEvent: `{recon.get('close_user_volume_accumulator_events')}`",
        f"- Truncated logs: `{recon.get('log_truncated_transactions')}`",
        f"- OBSERVED_TARGET_TRADES: `{slots['OBSERVED_TARGET_TRADES']}`",
        f"- PROVEN_NO_TARGET_TRADE: `{slots['PROVEN_NO_TARGET_TRADE']}`",
        f"- STATE_PERSISTENCE_PROVEN: `{slots['STATE_PERSISTENCE_PROVEN']}`",
        f"- UNKNOWN_COVERAGE: `{slots['UNKNOWN_COVERAGE']}`",
        "",
        "## PIT",
        "",
        "- Исторический retrieval **не** задран к `blockTime`.",
        "- Ретроспективная market-history usability: да.",
        "- Проспективная PIT-route usability: нет.",
        "",
        "## Ограничения",
        "",
    ]
    limitations = acceptance.get("limitations") or []
    if isinstance(limitations, list):
        lines.extend(f"- `{item}`" for item in limitations)
    lines.extend(
        [
            "",
            "## Что дальше",
            "",
            _next_ru(str(runtime.get("terminal_decision"))),
            "",
        ]
    )
    return "\n".join(lines)


def _next_ru(decision: str) -> str:
    if decision == "LIMITED_DIAGNOSTIC_PANEL_READY":
        return (
            "Решить, запускать ли один frozen H07/H01 limited diagnostic "
            "по новому точному контракту. Это не trial и не alpha."
        )
    if decision == "TARGETED_PROVIDER_CAPABILITY_GAP_PROVEN":
        return (
            "Начать targeted provider research только по названному "
            "отсутствующему полю, completeness, availability или universe."
        )
    if decision == "REDESIGN_DATA":
        return "Решить, менять ли data estimand или остановить RC001."
    return "Сохранить evidence и вернуть наименьшее нерешённое truth-решение."


if __name__ == "__main__":
    raise SystemExit(main())
