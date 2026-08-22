"""VPS-shaped production-lite runtime. Owns no scientific truth."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

import yaml

from solana_alpha_lab.factory.application import (
    FactoryApplication,
    commissioning_spec_relative,
    ops_store_path,
)
from solana_alpha_lab.factory.capabilities import resolve_data_requirements
from solana_alpha_lab.factory.experiment_spec import load_experiment_spec
from solana_alpha_lab.factory.operational_store import OperationalStore, OperationalStoreError

RUNTIME_CONFIG_RELATIVE = "configs/factory_v1_production_lite_runtime_v1.yaml"
FORBIDDEN_HEALTHY = "HEALTHY"


class RuntimeError(ValueError):
    """Raised when the Linux-shaped runtime cannot proceed fail-closed."""


def load_runtime_config(root: Path) -> dict[str, Any]:
    path = root / RUNTIME_CONFIG_RELATIVE
    if path.is_file() is False:
        raise RuntimeError("RUNTIME_CONFIG_MISSING")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RuntimeError("RUNTIME_CONFIG_INVALID")
    schema_path = root / "catalog/schemas/factory_v1_production_lite_runtime.schema.json"
    if schema_path.is_file():
        import jsonschema

        jsonschema.validate(loaded, json.loads(schema_path.read_text(encoding="utf-8")))
    return loaded


def _safe_relative(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise RuntimeError("RUNTIME_PATH_UNSAFE")
    return (root / candidate).resolve()


def git_evidence_status(root: Path) -> str:
    try:
        spec_relative = commissioning_spec_relative(root)
        spec = load_experiment_spec(root, spec_relative)
        coverage = resolve_data_requirements(spec, root=root)
    except Exception:
        return "MISSING"
    available = set(coverage.get("available") or [])
    if coverage.get("missing"):
        return "MISSING"
    if "RUNTIME_RECEIPT" in available and "ACCEPTANCE" in available:
        return "HASH_BOUND"
    return "PARTIAL"


def _active_version(config: Mapping[str, Any], events: list[Mapping[str, Any]]) -> str:
    version = str(config["deploy_version"])
    for event in reversed(events):
        if event["kind"] in {"VERSION_PIN", "ROLLBACK"}:
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            pinned = payload.get("active_deploy_version")
            if pinned:
                return str(pinned)
            break
    return version


def project_runtime_health(
    *,
    root: Path,
    store: OperationalStore,
    process_alive: bool,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    loaded = dict(config) if config is not None else load_runtime_config(root)
    events = store.runtime_events()
    kinds = {str(event["kind"]) for event in events}
    version = _active_version(loaded, events)
    evidence = git_evidence_status(root)
    snapshot_relative = str(loaded["operational_store"]["snapshot_relative_path"])
    snapshot_path = root / snapshot_relative
    local_snapshot = "PRESENT" if snapshot_path.is_file() else "MISSING"
    backup_status = str(loaded["health"]["backup_status_when_unproved"])
    proofs = {
        "restart_recovery": "RESTART" in kinds,
        "rollback": "ROLLBACK" in kinds,
        "rehost": "REHOST" in kinds,
        "version_visible": bool(version),
    }
    if process_alive is False:
        verdict = "UNHEALTHY_NOT_RUNNING"
        next_safe_action = "START_RUNTIME_PROCESS"
    elif not version:
        verdict = "UNHEALTHY_VERSION_MISSING"
        next_safe_action = "PIN_DEPLOY_VERSION"
    elif evidence != "HASH_BOUND":
        verdict = "UNHEALTHY_EVIDENCE_MISSING"
        next_safe_action = "RESOLVE_MISSING_EVIDENCE"
    elif not all(proofs[name] for name in ("restart_recovery", "rollback", "rehost")):
        verdict = "DEGRADED_PROCESS_ALIVE_BACKUP_UNKNOWN"
        next_safe_action = "RUN_RUNTIME_PROOFS"
    else:
        verdict = "RUNTIME_PROVED_BACKUP_UNKNOWN"
        next_safe_action = "INSPECT_RUNTIME_OR_LATER_VPS_GATE"
    if verdict == FORBIDDEN_HEALTHY or (
        process_alive and evidence != "HASH_BOUND" and verdict.startswith("RUNTIME_PROVED")
    ):
        raise RuntimeError("HEALTHY_FROM_PROCESS_ALIVE_FORBIDDEN")
    return {
        "verdict": verdict,
        "process_alive": process_alive,
        "deploy_version": version,
        "previous_deploy_version": str(loaded["previous_deploy_version"]),
        "git_evidence": evidence,
        "backup_status": backup_status,
        "local_rollback_snapshot": local_snapshot,
        "proofs": proofs,
        "rpo_max": loaded["rpo_max"],
        "rto_max": loaded["rto_max"],
        "purchase": loaded["target"]["purchase"],
        "implementation": loaded["implementation"],
        "next_safe_action": next_safe_action,
        "terminal": (
            "PRODUCTION_LITE_LINUX_RUNTIME_PROOF_PASS"
            if verdict == "RUNTIME_PROVED_BACKUP_UNKNOWN"
            else verdict
        ),
    }


def copy_rehost_allowlist(*, src_root: Path, dst_root: Path, relatives: list[str]) -> None:
    dst_root.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")
    for relative in relatives:
        source = _safe_relative(src_root, relative.rstrip("/"))
        destination = dst_root / relative.rstrip("/")
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True, ignore=ignore)
            continue
        if source.is_file() is False:
            raise RuntimeError("REHOST_SOURCE_MISSING")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


class FactoryRuntime:
    def __init__(
        self,
        *,
        root: Path,
        store: OperationalStore | None = None,
        process_alive: bool = False,
    ) -> None:
        self.root = root
        self.config = load_runtime_config(root)
        self.store = store or OperationalStore(ops_store_path(root))
        self.app = FactoryApplication(root=root, store=self.store)
        self.process_alive = process_alive

    def close(self) -> None:
        self.store.close()
        self.process_alive = False

    def health(self) -> dict[str, Any]:
        return project_runtime_health(
            root=self.root,
            store=self.store,
            process_alive=self.process_alive,
            config=self.config,
        )

    def start_process(self) -> dict[str, Any]:
        self.process_alive = True
        self.store.record_runtime_event(
            kind="START",
            payload={"deploy_version": self.config["deploy_version"]},
        )
        self.store.record_runtime_event(
            kind="VERSION_PIN",
            payload={"active_deploy_version": self.config["deploy_version"]},
        )
        return self.health()

    def stop_process(self) -> dict[str, Any]:
        self.process_alive = False
        self.store.record_runtime_event(kind="STOP", payload={})
        return self.health()

    def restart(self) -> dict[str, Any]:
        path = self.store.path
        self.store.close()
        self.store = OperationalStore(path)
        self.app = FactoryApplication(root=self.root, store=self.store)
        self.process_alive = True
        self.store.record_runtime_event(
            kind="RESTART",
            payload={"deploy_version": self.config["deploy_version"]},
        )
        model = self.app.start()
        health = self.health()
        health["experiment_status"] = model["status"]
        health["experiment_terminal"] = model.get("terminal_result")
        return health

    def snapshot(self) -> Path:
        dest = _safe_relative(self.root, str(self.config["operational_store"]["snapshot_relative_path"]))
        self.store.backup_to(dest)
        self.store.record_runtime_event(
            kind="SNAPSHOT",
            payload={"snapshot_relative": self.config["operational_store"]["snapshot_relative_path"]},
        )
        return dest

    def rollback(self) -> dict[str, Any]:
        dest = _safe_relative(self.root, str(self.config["operational_store"]["snapshot_relative_path"]))
        try:
            self.store.restore_from(dest)
        except OperationalStoreError as exc:
            raise RuntimeError(str(exc)) from exc
        self.app = FactoryApplication(root=self.root, store=self.store)
        self.process_alive = True
        self.store.record_runtime_event(
            kind="ROLLBACK",
            payload={
                "active_deploy_version": self.config["previous_deploy_version"],
                "snapshot_relative": self.config["operational_store"]["snapshot_relative_path"],
            },
        )
        model = self.app.read_model()
        health = self.health()
        health["experiment_status"] = model["status"]
        health["experiment_terminal"] = model.get("terminal_result")
        return health

    def rehost(self, dest_root: Path) -> "FactoryRuntime":
        copy_rehost_allowlist(
            src_root=self.root,
            dst_root=dest_root,
            relatives=list(self.config["rehost_relative_paths"]),
        )
        hosted = FactoryRuntime(root=dest_root)
        hosted.start_process()
        model = hosted.app.start()
        hosted.store.record_runtime_event(
            kind="REHOST",
            payload={
                "experiment_status": model["status"],
                "provider_api_rpc_wss_calls": int(
                    ((hosted.store.latest_job() or {}).get("evidence") or {}).get(
                        "provider_api_rpc_wss_calls"
                    )
                    or 0
                ),
            },
        )
        self.store.record_runtime_event(
            kind="REHOST",
            payload={"destination_kind": "ISOLATED_ROOT"},
        )
        return hosted

    def prove(self) -> dict[str, Any]:
        started = self.app.start()
        if started["status"] != "COMPLETE":
            raise RuntimeError("RUNTIME_PROOF_REQUIRES_GIT_COMPLETE")
        self.start_process()
        self.snapshot()
        restarted = self.restart()
        if restarted.get("experiment_status") != "COMPLETE":
            raise RuntimeError("RESTART_DID_NOT_RECOVER_COMPLETE")
        rolled = self.rollback()
        if rolled.get("experiment_status") != "COMPLETE":
            raise RuntimeError("ROLLBACK_DID_NOT_RECOVER_COMPLETE")
        with tempfile.TemporaryDirectory() as tmp:
            hosted = self.rehost(Path(tmp) / "rehost")
            try:
                if hosted.app.read_model()["status"] != "COMPLETE":
                    raise RuntimeError("REHOST_DID_NOT_PROJECT_COMPLETE")
            finally:
                hosted.close()
        packet = self.health()
        if packet["verdict"] != "RUNTIME_PROVED_BACKUP_UNKNOWN":
            raise RuntimeError("RUNTIME_PROOF_INCOMPLETE")
        return packet
