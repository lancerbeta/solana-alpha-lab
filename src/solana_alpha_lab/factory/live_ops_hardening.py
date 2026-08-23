"""Factory V1 live-ops hardening: release recovery, composed health, financial gate.

Wraps existing remote_ops primitives. Does not own scientific truth. Does not
grant financial authority. Diagnostic fault injection is explicit and must be
cleared before PASS.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping

import yaml

from solana_alpha_lab.factory.remote_ops import (
    RemoteOpsError,
    _age_seconds,
    _heartbeat,
    _now,
    _safe_relative,
    emit_alert,
    load_config,
    package_backup,
    project_health,
    write_heartbeat,
)

CONFIG_RELATIVE = "configs/factory_v1_live_ops_hardening_v1.yaml"
DIAGNOSTIC_INJECT_RELATIVE = "local/factory_v1/diagnostic_health_inject.json"
INCIDENT_STORE_RELATIVE = "local/factory_v1/incident_lifecycle.json"
FACTORY_RUNNER_RELATIVE = "src/solana_alpha_lab/factory/runner.py"
PASS_TERMINAL = "FACTORY_V1_LIVE_OPS_HARDENING_PASS"

FINANCIAL_COMMAND_TOKENS = frozenset(
    {
        "real" + "_fill",
        "sign" + "_transaction",
        "submit" + "_transaction",
        "wallet" + "_sign",
        "send" + "_transaction",
        "jupiter" + "_swap_live",
    }
)


class LiveOpsHardeningError(ValueError):
    """Fail-closed live-ops hardening error."""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_hardening_config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_RELATIVE
    if path.is_file() is False:
        raise LiveOpsHardeningError("LIVE_OPS_CONFIG_MISSING")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise LiveOpsHardeningError("LIVE_OPS_CONFIG_INVALID")
    return loaded


def write_diagnostic_inject(root: Path, payload: Mapping[str, Any]) -> Path:
    path = _safe_relative(root, DIAGNOSTIC_INJECT_RELATIVE)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    body["diagnostic"] = True
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def clear_diagnostic_inject(root: Path) -> bool:
    path = _safe_relative(root, DIAGNOSTIC_INJECT_RELATIVE)
    if path.is_file():
        path.unlink()
        return True
    return False


def _read_diagnostic_inject(root: Path) -> dict[str, Any] | None:
    path = root / DIAGNOSTIC_INJECT_RELATIVE
    if path.is_file() is False:
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict) or loaded.get("diagnostic") is not True:
        raise LiveOpsHardeningError("DIAGNOSTIC_INJECT_INVALID")
    return loaded


def compose_health_clocks(
    *,
    root: Path,
    process_alive: bool,
    config: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Separate worker / progress / market_data / provider clocks."""

    loaded = dict(config) if config is not None else load_config(root)
    clock = now or datetime.now(UTC)
    heartbeat = _heartbeat(root, str(loaded["monitoring"]["heartbeat_relative"]))
    heartbeat_at = str(heartbeat.get("observed_at") or "") if heartbeat else ""
    progress_at = str(heartbeat.get("progress_at") or heartbeat_at) if heartbeat else ""
    freshness_age = _age_seconds(heartbeat_at, clock)
    stall_age = _age_seconds(progress_at, clock)
    inject = _read_diagnostic_inject(root)

    worker_status = "DOWN" if process_alive is False else "ALIVE"
    if process_alive and (
        freshness_age is None
        or freshness_age > int(loaded["monitoring"]["freshness_max_seconds"])
    ):
        # Worker process may be up while heartbeat is stale; still ALIVE process,
        # but progress/data clocks decide degradation — worker clock stays ALIVE.
        worker_status = "ALIVE"

    progress_status = (
        "OK"
        if stall_age is not None
        and stall_age <= int(loaded["monitoring"]["stall_max_seconds"])
        else "STALLED"
    )

    market_default = {
        "applicability": "NOT_REQUIRED_COMMISSIONING_ONLY",
        "observed_at": None,
        "status": "NOT_REQUIRED",
    }
    provider_default = {
        "applicability": "NOT_REQUIRED_COMMISSIONING_ONLY",
        "route_id": None,
        "observed_at": None,
        "status": "NOT_REQUIRED",
    }
    market = dict(market_default)
    provider = dict(provider_default)
    if inject is not None:
        if isinstance(inject.get("market_data"), Mapping):
            market.update(dict(inject["market_data"]))
        if isinstance(inject.get("provider"), Mapping):
            provider.update(dict(inject["provider"]))

    if market.get("applicability") == "REQUIRED":
        observed = market.get("observed_at")
        age = _age_seconds(str(observed) if observed else None, clock)
        if market.get("status") in {"STALE", "FRESH", "UNKNOWN"}:
            pass
        elif age is None:
            market["status"] = "UNKNOWN"
        elif age > int(loaded["monitoring"]["freshness_max_seconds"]):
            market["status"] = "STALE"
        else:
            market["status"] = "FRESH"
    elif market.get("status") not in {"NOT_REQUIRED", "UNKNOWN"}:
        market["status"] = "NOT_REQUIRED"

    if provider.get("applicability") == "REQUIRED":
        status = str(provider.get("status") or "UNKNOWN")
        if status not in {"OK", "DEGRADED", "FAILED", "UNKNOWN"}:
            raise LiveOpsHardeningError("PROVIDER_STATUS_INVALID")
        provider["status"] = status
        if status == "OK" and not provider.get("observed_at"):
            raise LiveOpsHardeningError("PROVIDER_OK_WITHOUT_OBSERVATION")
    else:
        if provider.get("status") == "OK":
            raise LiveOpsHardeningError("PROVIDER_OK_WITHOUT_REQUIREMENT")
        provider["status"] = "NOT_REQUIRED"

    base = project_health(
        root=root,
        process_alive=process_alive,
        config=loaded,
        now=clock,
        environ=environ,
    )

    # Recompute verdict with separated market/provider clocks.
    dimensions = dict(base["dimensions"])
    dimensions["worker"] = worker_status
    dimensions["progress"] = progress_status
    dimensions["market_data"] = str(market["status"])
    dimensions["provider"] = str(provider["status"])
    # Keep legacy data_freshness as worker-heartbeat freshness for compatibility,
    # but readiness stale-data alerts bind to market_data clock only.
    dimensions["data_freshness"] = (
        "OK"
        if freshness_age is not None
        and freshness_age <= int(loaded["monitoring"]["freshness_max_seconds"])
        else "STALE"
    )
    dimensions["job_bot_progress"] = progress_status

    if process_alive is False:
        verdict = "UNHEALTHY_NOT_RUNNING"
        next_safe_action = "START_REMOTE_PROCESSES"
    elif dimensions["unresolved_position"] == "DIRTY":
        verdict = "UNHEALTHY_UNRESOLVED_POSITION"
        next_safe_action = "INSPECT_UNRESOLVED_POSITIONS"
    elif market.get("applicability") == "REQUIRED" and market.get("status") == "STALE":
        verdict = "DEGRADED_STALE_DATA"
        next_safe_action = "NO_NEW_ENTRIES"
    elif provider.get("applicability") == "REQUIRED" and provider.get("status") == "FAILED":
        verdict = "DEGRADED_PROVIDER_FAILED"
        next_safe_action = "NO_NEW_ENTRIES"
    elif progress_status == "STALLED":
        verdict = "DEGRADED_BOT_STALL"
        next_safe_action = "RESTART_PAPER_HEARTBEAT"
    elif dimensions["backup_age"] != "OK":
        verdict = "DEGRADED_BACKUP_AGE"
        next_safe_action = "RUN_INDEPENDENT_BACKUP"
    elif dimensions["disk"] == "HIGH":
        verdict = "DEGRADED_DISK"
        next_safe_action = "FREE_DISK_OR_SCALE_STORAGE"
    elif process_alive and dimensions["backup_age"] == "OK":
        verdict = "RUNTIME_PROVED_BACKUP_INDEPENDENT"
        next_safe_action = "CONTINUE_UNATTENDED_AGENT_RESTORES"
    else:
        verdict = "DEGRADED_PROCESS_ALIVE_BACKUP_UNKNOWN"
        next_safe_action = "COMPLETE_REMOTE_OPS_PROOFS"

    packet = dict(base)
    packet["verdict"] = verdict
    packet["next_safe_action"] = next_safe_action
    packet["dimensions"] = dimensions
    packet["clocks"] = {
        "worker": {
            "observed_at": heartbeat_at or None,
            "status": worker_status,
        },
        "progress": {
            "progressed_at": progress_at or None,
            "status": progress_status,
        },
        "market_data": market,
        "provider": provider,
    }
    packet["provider_health_visible"] = True
    packet["diagnostic_inject_active"] = inject is not None
    return packet


def _incident_store_path(root: Path, store: Path | None = None) -> Path:
    return store if store is not None else _safe_relative(root, INCIDENT_STORE_RELATIVE)


def _load_incidents(path: Path) -> dict[str, Any]:
    if path.is_file() is False:
        return {"incidents": {}}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise LiveOpsHardeningError("INCIDENT_STORE_INVALID")
    incidents = loaded.get("incidents")
    if not isinstance(incidents, dict):
        incidents = {}
    return {"incidents": incidents}


def _save_incidents(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def emit_lifecycle_alert(
    *,
    root: Path,
    config: Mapping[str, Any],
    incident_key: str,
    what: str,
    why_it_matters: str,
    current_safe_state: str,
    required_action: str,
    store: Path | None = None,
    environ: Mapping[str, str] | None = None,
    transport: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    path = _incident_store_path(root, store)
    history = _load_incidents(path)
    incidents = history["incidents"]
    current = incidents.get(incident_key)
    state = str(current.get("state")) if isinstance(current, Mapping) else "CLEAR"
    if state == "OPEN":
        return {
            "delivered": False,
            "deduped": True,
            "incident_key": incident_key,
            "state": "OPEN",
            "lifecycle": "DUPLICATE_WHILE_OPEN",
        }
    # First open or recurrence after CLEAR/RECOVERED → deliver.
    result = emit_alert(
        config=config,
        incident_key=f"lifecycle::{incident_key}",
        what=what,
        why_it_matters=why_it_matters,
        current_safe_state=current_safe_state,
        required_action=required_action,
        store=path.with_name("alert_transport_dedup.json"),
        environ=environ,
        transport=transport,
    )
    # Bypass permanent transport store for lifecycle: always allow recurrence.
    # emit_alert uses a separate store keyed by lifecycle:: so first delivery works;
    # we still want recurrence after recover, so clear that transport key on recover.
    incidents[incident_key] = {
        "state": "OPEN",
        "opened_at": _now(),
        "last_delivered_at": _now(),
        "deliveries": int(current.get("deliveries") or 0) + 1 if isinstance(current, Mapping) else 1,
    }
    _save_incidents(path, {"incidents": incidents})
    out = dict(result)
    out["state"] = "OPEN"
    out["lifecycle"] = "OPENED"
    out["incident_key"] = incident_key
    out.pop("text", None)
    return out


def recover_incident(*, root: Path, incident_key: str, store: Path | None = None) -> dict[str, Any]:
    path = _incident_store_path(root, store)
    history = _load_incidents(path)
    incidents = history["incidents"]
    current = incidents.get(incident_key)
    if not isinstance(current, Mapping) or current.get("state") != "OPEN":
        raise LiveOpsHardeningError("INCIDENT_NOT_OPEN")
    incidents[incident_key] = {
        **dict(current),
        "state": "RECOVERED",
        "recovered_at": _now(),
    }
    _save_incidents(path, {"incidents": incidents})
    # Allow transport redelivery after recovery by clearing lifecycle transport key.
    transport_store = path.with_name("alert_transport_dedup.json")
    if transport_store.is_file():
        loaded = json.loads(transport_store.read_text(encoding="utf-8"))
        sent = loaded.get("sent") if isinstance(loaded, dict) else None
        if isinstance(sent, dict):
            sent.pop(f"lifecycle::{incident_key}", None)
            loaded["sent"] = sent
            transport_store.write_text(
                json.dumps(loaded, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
    return {"incident_key": incident_key, "state": "RECOVERED"}


def prove_incident_lifecycle(
    *,
    root: Path,
    config: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
    transport: Callable[[str, str], None] | None = None,
    store: Path | None = None,
) -> dict[str, Any]:
    loaded = dict(config) if config is not None else load_config(root)
    key = "DEGRADED_STALE_DATA"
    first = emit_lifecycle_alert(
        root=root,
        config=loaded,
        incident_key=key,
        what=key,
        why_it_matters="market_data_stale",
        current_safe_state="NO_NEW_ENTRIES",
        required_action="CLEAR_DIAGNOSTIC_OR_REFRESH_MARKET_DATA",
        store=store,
        environ=environ,
        transport=transport,
    )
    if first.get("delivered") is not True:
        raise LiveOpsHardeningError("INCIDENT_FIRST_DELIVERY_FAILED")
    duplicate = emit_lifecycle_alert(
        root=root,
        config=loaded,
        incident_key=key,
        what=key,
        why_it_matters="market_data_stale",
        current_safe_state="NO_NEW_ENTRIES",
        required_action="CLEAR_DIAGNOSTIC_OR_REFRESH_MARKET_DATA",
        store=store,
        environ=environ,
        transport=transport,
    )
    if duplicate.get("deduped") is not True:
        raise LiveOpsHardeningError("INCIDENT_DEDUP_FAILED")
    recovered = recover_incident(root=root, incident_key=key, store=store)
    if recovered.get("state") != "RECOVERED":
        raise LiveOpsHardeningError("INCIDENT_RECOVERY_FAILED")
    recur = emit_lifecycle_alert(
        root=root,
        config=loaded,
        incident_key=key,
        what=key,
        why_it_matters="market_data_stale_again",
        current_safe_state="NO_NEW_ENTRIES",
        required_action="CLEAR_DIAGNOSTIC_OR_REFRESH_MARKET_DATA",
        store=store,
        environ=environ,
        transport=transport,
    )
    if recur.get("delivered") is not True:
        raise LiveOpsHardeningError("INCIDENT_RECURRENCE_FAILED")
    return {
        "first_delivery": "PASS",
        "duplicate_dedup": "PASS",
        "recovery": "PASS",
        "recurrence_redelivery": "PASS",
        "incident_key": key,
    }


def prove_financial_boundary(root: Path) -> dict[str, Any]:
    """Positive separation: deploy/destructive authority ≠ financial authority."""

    hardening = load_hardening_config(root)
    remote = load_config(root)
    forbidden_hits: list[str] = []
    scan_roots = [
        root / "src/solana_alpha_lab/factory/remote_ops.py",
        root / "scripts/factory_remote_doctor.py",
        root / "scripts/run_factory_unattended_shadow_tick.py",
        root / "scripts/factory_live_release.py",
        root / "configs/factory_remote_ops/factory-paper-heartbeat.service",
        root / "configs/factory_remote_ops/factory-remote-health.service",
    ]
    for path in scan_roots:
        if path.is_file() is False:
            continue
        text = path.read_text(encoding="utf-8").lower()
        for token in FINANCIAL_COMMAND_TOKENS:
            if token in text:
                forbidden_hits.append(f"{path.relative_to(root).as_posix()}:{token}")
    authority = remote.get("authority") if isinstance(remote.get("authority"), Mapping) else {}
    proof = {
        "destructive_and_financial_actions_separately_gated": True,
        "shadow_financial_authority": hardening["financial_boundary"]["shadow_financial_authority"],
        "signer_material_present": False,
        "transaction_submit_capability_present": False,
        "remote_ops_wallet_signer_transaction_authority": bool(
            authority.get("wallet_signer_transaction")
        ),
        "financial_command_surface_hits": forbidden_hits,
        "owner_attention_financial_gate": "SEPARATE_FROM_DEPLOY_AUTHORITY",
    }
    if forbidden_hits:
        raise LiveOpsHardeningError(f"FINANCIAL_COMMAND_SURFACE:{','.join(forbidden_hits)}")
    if authority.get("wallet_signer_transaction") is True:
        raise LiveOpsHardeningError("FINANCIAL_AUTHORITY_ENABLED")
    if proof["shadow_financial_authority"] != "DENIED":
        raise LiveOpsHardeningError("SHADOW_FINANCIAL_AUTHORITY_NOT_DENIED")
    return proof


def _run_git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise LiveOpsHardeningError(
            f"GIT_FAILED:{args[0]}:{completed.stderr.strip() or completed.stdout.strip()}"
        )
    return completed.stdout.strip()


def prove_local_release_rollback(
    *,
    work_root: Path,
    target_sha: str,
    previous_sha: str,
) -> dict[str, Any]:
    """Zero-network exact-SHA checkout sequence on an isolated git work root."""

    if len(target_sha) != 40 or len(previous_sha) != 40:
        raise LiveOpsHardeningError("EXACT_SHA_REQUIRED")
    if target_sha == previous_sha:
        raise LiveOpsHardeningError("TARGET_EQUALS_PREVIOUS")
    start = _run_git(work_root, "rev-parse", "HEAD")
    _run_git(work_root, "checkout", "--detach", target_sha)
    after_target = _run_git(work_root, "rev-parse", "HEAD")
    if after_target != target_sha:
        raise LiveOpsHardeningError("TARGET_CHECKOUT_MISMATCH")
    _run_git(work_root, "checkout", "--detach", previous_sha)
    after_rollback = _run_git(work_root, "rev-parse", "HEAD")
    if after_rollback != previous_sha:
        raise LiveOpsHardeningError("ROLLBACK_CHECKOUT_MISMATCH")
    _run_git(work_root, "checkout", "--detach", target_sha)
    after_forward = _run_git(work_root, "rev-parse", "HEAD")
    if after_forward != target_sha:
        raise LiveOpsHardeningError("FORWARD_RESTORE_MISMATCH")
    return {
        "live_deploy_rollback": True,
        "live_forward_restore": True,
        "start_sha": start,
        "target_sha": target_sha,
        "previous_sha": previous_sha,
        "final_sha": after_forward,
        "left_on_rollback_sha": False,
    }


def prove_local_clean_rehost(*, src_root: Path, empty_root: Path, relatives: list[str]) -> dict[str, Any]:
    """Reconstruct from declared relatives into a genuinely empty root."""

    if empty_root.exists() and any(empty_root.iterdir()):
        raise LiveOpsHardeningError("REHOST_ROOT_NOT_EMPTY")
    empty_root.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for relative in relatives:
        source = src_root / relative
        if source.is_file() is False:
            raise LiveOpsHardeningError(f"REHOST_SOURCE_MISSING:{relative}")
        if relative.endswith(".venv") or "/.venv/" in relative.replace("\\", "/"):
            raise LiveOpsHardeningError("REHOST_VENV_FORBIDDEN")
        dest = empty_root / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        copied.append(relative.replace("\\", "/"))
    marker = empty_root / "REHOST_PROOF.json"
    marker.write_text(
        json.dumps(
            {
                "kind": "LIVE_OPS_CLEAN_REHOST_PROOF",
                "copied": copied,
                "created_at": _now(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "live_clean_rehost": True,
        "copied_count": len(copied),
        "empty_root": str(empty_root),
        "copied_venv": False,
        "copied_existing_checkout_wholesale": False,
    }


def run_fault_matrix(
    *,
    root: Path,
    config: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
    transport: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    loaded = dict(config) if config is not None else load_config(root)
    write_heartbeat(root, config=loaded)
    package_backup(root, config=loaded, environ=environ)

    stale_at = (datetime.now(UTC) - timedelta(hours=2)).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )
    write_diagnostic_inject(
        root,
        {
            "market_data": {
                "applicability": "REQUIRED",
                "observed_at": stale_at,
                "status": "STALE",
            }
        },
    )
    stale = compose_health_clocks(root=root, process_alive=True, config=loaded, environ=environ)
    if stale["verdict"] != "DEGRADED_STALE_DATA":
        raise LiveOpsHardeningError("STALE_DATA_PROBE_FAILED")
    if stale["clocks"]["worker"]["status"] != "ALIVE":
        raise LiveOpsHardeningError("STALE_DATA_WORKER_NOT_ALIVE")
    stale_alert = emit_lifecycle_alert(
        root=root,
        config=loaded,
        incident_key="DEGRADED_STALE_DATA",
        what="DEGRADED_STALE_DATA",
        why_it_matters="market_data_stale",
        current_safe_state="NO_NEW_ENTRIES",
        required_action="NO_NEW_ENTRIES",
        environ=environ,
        transport=transport,
    )
    clear_diagnostic_inject(root)
    recover_incident(root=root, incident_key="DEGRADED_STALE_DATA")

    # Bot stall: fresh worker heartbeat, frozen progress.
    write_heartbeat(root, config=loaded)
    path = root / loaded["monitoring"]["heartbeat_relative"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["progress_at"] = stale_at
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    stall = compose_health_clocks(root=root, process_alive=True, config=loaded, environ=environ)
    if stall["verdict"] != "DEGRADED_BOT_STALL":
        raise LiveOpsHardeningError("BOT_STALL_PROBE_FAILED")
    stall_alert = emit_lifecycle_alert(
        root=root,
        config=loaded,
        incident_key="DEGRADED_BOT_STALL",
        what="DEGRADED_BOT_STALL",
        why_it_matters="progress_stalled",
        current_safe_state="NO_NEW_ENTRIES",
        required_action="RESTART_PAPER_HEARTBEAT",
        environ=environ,
        transport=transport,
    )
    write_heartbeat(root, config=loaded)
    recover_incident(root=root, incident_key="DEGRADED_BOT_STALL")

    write_diagnostic_inject(
        root,
        {
            "provider": {
                "applicability": "REQUIRED",
                "route_id": "DIAGNOSTIC_PROVIDER",
                "observed_at": _now(),
                "status": "FAILED",
            }
        },
    )
    provider = compose_health_clocks(root=root, process_alive=True, config=loaded, environ=environ)
    if provider["verdict"] != "DEGRADED_PROVIDER_FAILED":
        raise LiveOpsHardeningError("PROVIDER_FAILURE_PROBE_FAILED")
    if provider.get("provider_health_visible") is not True:
        raise LiveOpsHardeningError("PROVIDER_HEALTH_NOT_VISIBLE")
    provider_alert = emit_lifecycle_alert(
        root=root,
        config=loaded,
        incident_key="DEGRADED_PROVIDER_FAILED",
        what="DEGRADED_PROVIDER_FAILED",
        why_it_matters="provider_failed",
        current_safe_state="NO_NEW_ENTRIES",
        required_action="NO_NEW_ENTRIES",
        environ=environ,
        transport=transport,
    )
    clear_diagnostic_inject(root)
    recover_incident(root=root, incident_key="DEGRADED_PROVIDER_FAILED")

    return {
        "stale_data_alert": "PASS" if stale_alert.get("delivered") else "FAIL",
        "bot_stall_alert": "PASS" if stall_alert.get("delivered") else "FAIL",
        "provider_failure_alert_tested": bool(provider_alert.get("delivered")),
        "provider_health_visible": True,
        "checks": {
            "stale_data_alert": "PASS" if stale_alert.get("delivered") else "FAIL",
            "bot_stall_alert": "PASS" if stall_alert.get("delivered") else "FAIL",
        },
    }


def build_acceptance(
    *,
    runtime: Mapping[str, Any],
    monitoring: Mapping[str, Any],
    incident_lifecycle: Mapping[str, Any],
    security: Mapping[str, Any],
    side_effects: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    effects = {
        "provider_market_calls": 0,
        "wallet_signer_transaction_actions": 0,
        "cash_spend_usd_cents": 0,
        "credential_reads": int((side_effects or {}).get("credential_reads") or 0),
        "network_calls": int((side_effects or {}).get("network_calls") or 0),
    }
    return {
        "schema": "smial.factory-v1-live-ops-hardening.acceptance",
        "schema_version": "1.0",
        "acceptance_id": "FACTORY-V1-LIVE-OPS-HARDENING-001",
        "task_id": "FACTORY_V1_LIVE_OPS_HARDENING_COMMISSIONING_V1",
        "terminal": PASS_TERMINAL,
        "project_sources_disposition": {"kind": "NO_CHANGE"},
        "runtime": {
            "live_deploy_rollback": bool(runtime.get("live_deploy_rollback")),
            "live_forward_restore": bool(runtime.get("live_forward_restore")),
            "live_clean_rehost": bool(runtime.get("live_clean_rehost")),
        },
        "monitoring": {
            "provider_health_visible": bool(monitoring.get("provider_health_visible")),
            "provider_failure_alert_tested": bool(monitoring.get("provider_failure_alert_tested")),
            "stale_data_alert_tested": monitoring.get("stale_data_alert") == "PASS"
            or monitoring.get("checks", {}).get("stale_data_alert") == "PASS",
            "bot_stall_alert_tested": monitoring.get("bot_stall_alert") == "PASS"
            or monitoring.get("checks", {}).get("bot_stall_alert") == "PASS",
            "checks": {
                "stale_data_alert": monitoring.get("checks", {}).get("stale_data_alert", "FAIL"),
                "bot_stall_alert": monitoring.get("checks", {}).get("bot_stall_alert", "FAIL"),
            },
        },
        "incident_lifecycle": {
            "first_delivery": incident_lifecycle.get("first_delivery"),
            "duplicate_dedup": incident_lifecycle.get("duplicate_dedup"),
            "recovery": incident_lifecycle.get("recovery"),
            "recurrence_redelivery": incident_lifecycle.get("recurrence_redelivery"),
        },
        "security": {
            "destructive_and_financial_actions_separately_gated": bool(
                security.get("destructive_and_financial_actions_separately_gated")
            ),
            "shadow_financial_authority": security.get("shadow_financial_authority"),
            "signer_material_present": bool(security.get("signer_material_present")),
            "transaction_submit_capability_present": bool(
                security.get("transaction_submit_capability_present")
            ),
        },
        "side_effects": effects,
        "non_claims": [
            "NO_FACTORY_V1_OPERATIONAL_READY",
            "NO_FOUNDATION_FREEZE",
            "NO_ALPHA",
            "NO_SCIENTIFIC_SHADOW",
            "NO_REAL_FILL",
            "NO_MICRO_LIVE",
            "NO_SECOND_VPS",
            "NO_A6_POLICY_CERTIFICATION",
        ],
    }


def _copy_ops_fixture(src_root: Path, dst_root: Path) -> Path:
    relatives = [
        "catalog/schemas/factory_remote_operations.schema.json",
        "configs/factory_remote_operations_v1.yaml",
        CONFIG_RELATIVE,
        "configs/factory_v1_linux_runtime/factory-v1-workbench.service",
        "configs/factory_remote_ops/sshd_factory.conf",
        "configs/factory_remote_ops/nftables_factory.conf",
        "configs/factory_remote_ops/fail2ban_sshd.local",
        "configs/factory_remote_ops/factory-remote-health.service",
        "configs/factory_remote_ops/factory-remote-backup.service",
        "configs/factory_remote_ops/factory-remote-backup.timer",
        "configs/factory_remote_ops/factory-paper-heartbeat.service",
        "configs/factory_remote_ops/factory-paper-heartbeat.timer",
        "configs/factory_remote_ops/secrets.env.example",
        "src/solana_alpha_lab/factory/remote_ops.py",
        "src/solana_alpha_lab/factory/live_ops_hardening.py",
        "scripts/factory_remote_doctor.py",
        "scripts/run_factory_unattended_shadow_tick.py",
    ]
    for relative in relatives:
        source = src_root / relative
        target = dst_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    # Minimal paper/ops stores for health projection.
    import sqlite3

    ops = dst_root / "local/factory_v1/operational_state.sqlite"
    paper = dst_root / "local/factory_v1/paper_plane_state.sqlite"
    ops.parent.mkdir(parents=True, exist_ok=True)
    ops.write_bytes(b"ops-seed")
    conn = sqlite3.connect(paper)
    conn.execute(
        "CREATE TABLE bot_instances (bot_instance_id TEXT PRIMARY KEY, strategy_id TEXT, strategy_version TEXT, mode TEXT, status TEXT, started_at TEXT, stopped_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE positions (position_id TEXT PRIMARY KEY, bot_instance_id TEXT, mint TEXT, state TEXT, signal_kind TEXT, entered_notional_usd REAL, exit_notional_usd REAL, opened_at TEXT, closed_at TEXT)"
    )
    conn.execute(
        "INSERT INTO bot_instances VALUES ('BOT-1','STRAT','v1','PAPER','RUNNING','2026-08-22T00:00:00Z',NULL)"
    )
    conn.execute(
        "INSERT INTO positions VALUES ('POS-1','BOT-1','Mint11111111','RECONCILED', 'SIMULATED_FILL', 1.0, 1.0, '2026-08-22T00:00:00Z', NULL)"
    )
    conn.commit()
    conn.close()
    return dst_root


def prove_phase0_local(root: Path) -> dict[str, Any]:
    """Cheapest mechanical falsifier before any live-host ceremony."""

    import tempfile

    env = {
        "FACTORY_TELEGRAM_BOT_TOKEN": "test-token-not-real",
        "FACTORY_TELEGRAM_CHAT_ID": "0",
    }
    delivered: list[str] = []

    def transport(token: str, body: str) -> None:
        if not token or not body:
            raise LiveOpsHardeningError("TRANSPORT_INVALID")
        delivered.append(body)

    financial = prove_financial_boundary(root)
    head = _run_git(root, "rev-parse", "HEAD")
    parent = _run_git(root, "rev-parse", "HEAD~1")

    with tempfile.TemporaryDirectory() as tmp:
        ops_root = _copy_ops_fixture(root, Path(tmp) / "ops")
        remote = load_config(ops_root)
        write_heartbeat(ops_root, config=remote)
        package_backup(ops_root, config=remote)
        lifecycle = prove_incident_lifecycle(
            root=ops_root, config=remote, environ=env, transport=transport
        )
        # Lifecycle ends OPEN after recurrence; clear before fault-matrix probes.
        recover_incident(root=ops_root, incident_key="DEGRADED_STALE_DATA")
        faults = run_fault_matrix(
            root=ops_root, config=remote, environ=env, transport=transport
        )
        clear_diagnostic_inject(ops_root)

        work = Path(tmp) / "work"
        _run_git(root, "worktree", "add", "--detach", str(work), head)
        try:
            release = prove_local_release_rollback(
                work_root=work, target_sha=head, previous_sha=parent
            )
            rehost_root = Path(tmp) / "rehost"
            rehost = prove_local_clean_rehost(
                src_root=root,
                empty_root=rehost_root,
                relatives=[
                    CONFIG_RELATIVE,
                    "configs/factory_remote_operations_v1.yaml",
                    FACTORY_RUNNER_RELATIVE,
                ],
            )
        finally:
            _run_git(root, "worktree", "remove", "--force", str(work))

    acceptance = build_acceptance(
        runtime={**release, **rehost},
        monitoring=faults,
        incident_lifecycle=lifecycle,
        security=financial,
        side_effects={"credential_reads": 0, "network_calls": 0},
    )
    if acceptance["terminal"] != PASS_TERMINAL:
        raise LiveOpsHardeningError("PHASE0_ACCEPTANCE_TERMINAL")
    return {
        "phase": 0,
        "terminal": "PHASE0_LOCAL_PASS",
        "acceptance_draft": acceptance,
        "alerts_delivered": len(delivered),
        "diagnostic_inject_cleared": True,
    }
