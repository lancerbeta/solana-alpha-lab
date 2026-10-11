"""Compact offline reproduction with owned disposable roots and no external egress."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = "SMIAL_TRADING_CONTINUITY_AUDIT_REPAIR_V1"
SANDBOX = ROOT / "local/smial_trading_continuity_v1"
MANIFEST = ROOT / "local/smial_trading_continuity_resource_manifest_v1.json"
EVIDENCE = ROOT / "docs/evidence/smial_trading_continuity_v1"
NON_TARGETS = ("uv.lock", ".venv/pyvenv.cfg", "AGENTS.md",
    "configs/provider_route_capability_registry_v1.yaml",
    "configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml")
PROOF_INPUTS = tuple("src/solana_alpha_lab/factory/" + name + ".py" for name in (
    "episode_decision", "trading_runner", "paper_plane", "trading_operations", "paper_shadow_operations",
    "hfic_research_scope", "hfic_temporal_discovery", "observation_schedule_store", "opportunity_episode_release")) + (
    "scripts/trading_continuity.py", "scripts/prove_trading_continuity.py", "tests/test_trading_continuity_v1.py")
EGRESS_GUARD = '''import socket
_connect = socket.socket.connect
_getaddrinfo = socket.getaddrinfo
def _local(host):
    return str(host) in {"127.0.0.1", "::1", "localhost"}
def _guard(self, address):
    if not isinstance(address, tuple) or not _local(address[0]):
        raise RuntimeError("OFFLINE_EGRESS_DENIED")
    return _connect(self, address)
def _dns(host, *args, **kwargs):
    if not _local(host):
        raise RuntimeError("OFFLINE_EGRESS_DENIED")
    return _getaddrinfo(host, *args, **kwargs)
socket.socket.connect = _guard
socket.getaddrinfo = _dns
import json, os, pathlib, tempfile
_cleanup = tempfile.TemporaryDirectory.cleanup
def _measured_cleanup(self):
    journal = os.environ.get("OFFLINE_RESOURCE_JOURNAL")
    try:
        if journal:
            root = pathlib.Path(self.name)
            owned = pathlib.Path(os.environ["TEMP"])
            if root.exists() and root.absolute().is_relative_to(owned.absolute()):
                size = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
                with open(journal, "a", encoding="utf-8") as out:
                    out.write(json.dumps({"bytes_before_fixture_cleanup": size}) + "\\n")
    finally:
        return _cleanup(self)
tempfile.TemporaryDirectory.cleanup = _measured_cleanup
'''


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def non_target_fingerprints() -> dict:
    return {relative: {"exists": (ROOT / relative).is_file(),
        "sha256": digest(ROOT / relative) if (ROOT / relative).is_file() else None} for relative in NON_TARGETS}


def process_readback(pid: int) -> str:
    if os.name == "nt":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return "ABSENT" if ctypes.get_last_error() == 87 else "UNKNOWN_ACCESS"
        try:
            code = ctypes.c_ulong()
            kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                return "UNKNOWN_ACCESS"
            return "RUNNING" if code.value == 259 else "EXITED"
        finally:
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return "RUNNING_OR_PID_REUSED"
    except ProcessLookupError:
        return "ABSENT"
    except PermissionError:
        return "UNKNOWN_ACCESS"


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def owned(path: Path) -> None:
    resolved = path.resolve(strict=True)
    if resolved != path.absolute() or not resolved.is_relative_to(SANDBOX.resolve(strict=True)):
        raise RuntimeError("RESOURCE_PATH_ESCAPE")
    if (SANDBOX / ".owner").read_text(encoding="utf-8-sig").strip() != CAMPAIGN:
        raise RuntimeError("RESOURCE_OWNER_MISMATCH")
    for entry in [path, *path.rglob("*")]:
        if entry.is_symlink() or entry.is_junction():
            raise RuntimeError("RESOURCE_REPARSE_ESCAPE")


def bootstrap() -> None:
    """Record ownership before creating a fresh campaign root; never adopt one."""
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
        if manifest.get("campaign") != CAMPAIGN:
            raise RuntimeError("RESOURCE_OWNER_MISMATCH")
        owned(SANDBOX)
        return
    if SANDBOX.exists():
        raise RuntimeError("UNOWNED_CAMPAIGN_ROOT")
    local = (ROOT / "local").resolve(strict=True)
    if SANDBOX.resolve(strict=False) != SANDBOX.absolute() or not SANDBOX.is_relative_to(local):
        raise RuntimeError("RESOURCE_PATH_ESCAPE")
    write(MANIFEST, {"campaign": CAMPAIGN, "resources": [{"path": SANDBOX.relative_to(ROOT).as_posix(),
        "kind": "DISPOSABLE_CAMPAIGN_ROOT", "created_by_this_run": True, "baseline_existed": False,
        "marker": CAMPAIGN, "estimated_bytes": 10485760, "cleanup": "DELETE_AFTER_HASHED_SUMMARY"}]})
    SANDBOX.mkdir()
    (SANDBOX / ".owner").write_text(CAMPAIGN, encoding="utf-8")


def clean() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    if manifest.get("campaign") != CAMPAIGN:
        raise RuntimeError("RESOURCE_OWNER_MISMATCH")
    owned(SANDBOX)
    # Every remaining direct child must be covered by the exact recorded root.
    if not any(r.get("path") == SANDBOX.relative_to(ROOT).as_posix() and r.get("created_by_this_run")
               and r.get("baseline_existed") is False for r in manifest["resources"]):
        raise RuntimeError("CAMPAIGN_ROOT_OWNERSHIP_UNPROVEN")
    fingerprints_before = non_target_fingerprints()
    processes = {str(r["pid"]): process_readback(r["pid"]) for r in manifest["resources"] if r.get("pid")}
    if any(value in {"RUNNING", "RUNNING_OR_PID_REUSED"} for value in processes.values()):
        raise RuntimeError("CAMPAIGN_PROCESS_STILL_RUNNING")
    before = sum(p.stat().st_size for p in SANDBOX.rglob("*") if p.is_file())
    shutil.rmtree(SANDBOX)
    fingerprints_after = non_target_fingerprints()
    result = {"campaign": CAMPAIGN, "status": "CLEAN", "resources": manifest["resources"],
        "remaining_owned_bytes_before": before, "remaining_owned_bytes_after": 0,
        "campaign_root_absent": not SANDBOX.exists(),
        "non_target_fingerprints_before": fingerprints_before, "non_target_fingerprints_after": fingerprints_after,
        "non_target_preservation": "PASS" if fingerprints_after == fingerprints_before else "FAIL",
        "process_readback": processes, "created_containers_services_volumes": [],
        "retained_dependencies": "PREEXISTING_LOCKED_ENVIRONMENT_AND_SHARED_CACHE"}
    MANIFEST.unlink()
    result["manifest_absent"] = not MANIFEST.exists()
    if fingerprints_after != fingerprints_before:
        raise RuntimeError("NON_TARGET_FINGERPRINT_CHANGED")
    return result


def run(modules: list[str], *, phase: str) -> dict:
    input_bindings = {p: digest(ROOT / p) for p in PROOF_INPUTS}
    bootstrap()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    if manifest["campaign"] != CAMPAIGN:
        raise RuntimeError("RESOURCE_OWNER_MISMATCH")
    case = SANDBOX / (phase + "-" + uuid4().hex)
    if case.exists():
        raise RuntimeError("RESOURCE_COLLISION")
    allocation = {"path": case.relative_to(ROOT).as_posix(), "kind": "DISPOSABLE_CASE_ROOT",
                  "created_by_this_run": True, "baseline_existed": False, "marker": CAMPAIGN,
                  "estimated_bytes": 10485760, "cleanup": "DELETE_AFTER_HASHED_SUMMARY"}
    manifest["resources"].append(allocation)
    write(MANIFEST, manifest)
    case.mkdir()
    (case / ".owner").write_text(CAMPAIGN, encoding="utf-8")
    (case / "tmp").mkdir()
    (case / "sitecustomize.py").write_text(EGRESS_GUARD, encoding="utf-8")
    if phase in {"baseline-replay", "cost-before", "price-before", "transaction-before"}:
        frozen_root = case / "frozen-repo"
        frozen = frozen_root / "src" / "solana_alpha_lab" / "factory"
        frozen.mkdir(parents=True)
        base = {"baseline-replay": "d244af69bfd7ddc2850b9e5e5823323956e325c4",
                "cost-before": "160866d6b92e724b48e4c9dceb7b511043d22cb4",
                "price-before": "5db1b8200fe19c88fbaaee49496bcc26ec34c7f7",
                "transaction-before": "3f619f9264dda4d70e41eb01c304280b15bae8f3"}[phase]
        frozen_modules = (("paper_plane", "trading_runner") if phase == "transaction-before" else
            ("hfic_temporal_discovery", "episode_decision") if phase == "price-before" else
            ("paper_plane", "trading_operations", "paper_shadow_operations"))
        for name in frozen_modules:
            blob = subprocess.run(["git", "show", base + ":src/solana_alpha_lab/factory/" + name + ".py"],
                cwd=ROOT, capture_output=True, check=True).stdout
            (frozen / (name + ".py")).write_bytes(blob)
        if phase == "price-before":
            registry = frozen_root / "configs/observation_primitive_registry_v1.yaml"
            registry.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / "configs/observation_primitive_registry_v1.yaml", registry)
            for relative in ("catalog/schemas/observation_primitive_registry_v1.schema.json",
                             "catalog/schemas/observation_primitive_descriptor_v1.schema.json"):
                target = frozen_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
        with (case / "sitecustomize.py").open("a", encoding="utf-8") as hook:
            hook.write("\nimport solana_alpha_lab.factory as factory\nfactory.__path__.insert(0, " + repr(str(frozen)) + ")\n")
        tree = ast.parse((ROOT / "tests/test_trading_continuity_v1.py").read_text(encoding="utf-8"))
        probe = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ConfirmedBaselineDefects")
        prelude = '''import unittest
from contextlib import contextmanager
from unittest.mock import patch
from tests.test_paper_shadow_execution_integrity_vertical_v1 import StoreCase, ROOT, accept, open_filled, signal
from solana_alpha_lab.factory.paper_plane import PaperPlaneError, accept_signal_decision
from solana_alpha_lab.factory.paper_shadow_commands import apply_operator_command
from solana_alpha_lab.factory.paper_shadow_operations import build_operations_projection
from solana_alpha_lab.factory.trading_operations import _bot_context
'''
        (case / "baseline_probe.py").write_text(prelude + ast.unparse(probe) + "\n", encoding="utf-8")
        modules = ["baseline_probe"] if phase == "baseline-replay" else ["tests.test_trading_continuity_v1.OrdinarySourceTests.test_cumulative_cost_floor_clock_and_partial_exit_refusal"]
        if phase == "price-before":
            modules = ["tests.test_trading_continuity_v1.OrdinarySourceTests." + name for name in (
                "test_missing_decision_price_refuses_list_only",
                "test_missing_decision_price_refuses_positive_holder_delta",
                "test_late_decision_price_refuses_list_only_without_future_healing")]
        if phase == "transaction-before":
            modules = ["tests.test_trading_continuity_v1.OrdinarySourceTests." + name for name in (
                "test_ordinary_denied_admission_is_durable_and_idempotent",
                "test_ordinary_stale_replay_cancellation_survives_new_connection")]
    # Do not inherit provider keys, credentials, user profiles or arbitrary Python hooks.
    env = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "PATH", "COMSPEC") if key in os.environ}
    env.update(TEMP=str(case / "tmp"), TMP=str(case / "tmp"),
               PYTHONPATH=os.pathsep.join([str(case), str(ROOT), str(ROOT / "src"), str(ROOT / "tests")]),
               PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
               OFFLINE_RESOURCE_JOURNAL=str(case / "resource-sizes.jsonl"))
    started = time.monotonic()
    try:
        canary = subprocess.run([sys.executable, "-B", "-c",
            "import socket; socket.socket().connect(('192.0.2.1', 443))"],
            cwd=ROOT, env=env, capture_output=True, timeout=20)
        denied = canary.returncode != 0 and b"OFFLINE_EGRESS_DENIED" in canary.stderr
        if not denied:
            raise RuntimeError("S00_EGRESS_CANARY_FAILED")
        command = [sys.executable, "-B", "-m", "unittest", "-v", *modules]
        peak = 0
        with (case / "output.txt").open("wb") as log:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            allocation["pid"] = process.pid
            write(MANIFEST, manifest)
            try:
                while process.poll() is None:
                    if time.monotonic() - started > 600:
                        raise TimeoutError("OFFLINE_PROOF_TIMEOUT")
                    time.sleep(0.1)
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait()
        output = (case / "output.txt").read_bytes()
        journal = case / "resource-sizes.jsonl"
        measurements = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()] if journal.exists() else []
        peak = max((m["bytes_before_fixture_cleanup"] for m in measurements), default=0)
        cases = [{"test": name + " (" + module + ")", "status": status}
                 for name, module, status in re.findall(r"^(test\S+) \(([^\n]+)\).*?\.\.\. (ok|FAIL|ERROR|skipped[^\n]*)$", output.decode("utf-8", errors="replace").replace("\r", ""), re.MULTILINE)]
        allocation["observed_peak_bytes"] = peak
        inputs_unchanged = input_bindings == {p: digest(ROOT / p) for p in PROOF_INPUTS}
        result = {"phase": phase, "status": "PASS" if process.returncode == 0 and inputs_unchanged else "FAIL",
                  "exit_code": process.returncode, "test_modules": modules, "executed_cases": cases,
                  "observed_peak_bytes": peak, "peak_method": "PRE_TEMP_ROOT_CLEANUP_MAX_NOT_ABSOLUTE_MAXIMUM",
                  "resource_measurement_n": len(measurements), "owned_process_exit_code": process.returncode,
                  "output_sha256": hashlib.sha256(output).hexdigest(),
                  "elapsed_seconds": round(time.monotonic() - started, 3),
                  "egress_canary": "PASS", "environment": "ALLOWLIST",
                  "evidence_class": "SYNTHETIC_OFFLINE"}
        result["candidate_test_sha256"] = input_bindings["tests/test_trading_continuity_v1.py"]
        result["candidate_input_bindings"] = input_bindings
        result["candidate_inputs_unchanged"] = inputs_unchanged
        if phase in {"baseline-replay", "cost-before", "price-before", "transaction-before"}:
            result["baseline_binding"] = {"base": base, "frozen_modules": list(frozen_modules),
                "method": "FROZEN_BASE_MODULES_WITH_CURRENT_INDEPENDENT_BASELINE_PROBES", "remaining_dependencies": "UNCHANGED_BASE_OWNERS"}
            if phase == "price-before":
                result["baseline_binding"]["registry_dependency_sha256"] = digest(registry)
            blocks = re.findall(r"^(?:FAIL|ERROR): ([^\n]+)\n(.*?)(?=^={10,}|^Ran |\Z)",
                output.decode("utf-8", errors="replace").replace("\r", ""), re.MULTILINE | re.DOTALL)
            result["failure_boundaries"] = [[name, boundary] for name, block in blocks
                for boundary in re.findall(r"^AssertionError:[^\n]+", block, re.MULTILINE)]
        # Display diagnostics to the executor; retain only compact, safe evidence in Git.
        write(EVIDENCE / (phase + "-run.json"), result)
        if process.returncode:
            print(output.decode("utf-8", errors="replace"), end="")
        else:
            print(f"{phase}: {len(cases)} cases; offline egress canary PASS")
        return result
    finally:
        owned(case)
        allocation["actual_bytes_before_cleanup"] = sum(p.stat().st_size for p in case.rglob("*") if p.is_file())
        shutil.rmtree(case)
        allocation["deleted"] = not case.exists()
        write(MANIFEST, manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("baseline", "baseline-replay", "cost-before", "price-before", "git-boundary", "transaction-before", "transaction-after", "baseline-projection", "verify", "regression", "clean", "fresh"), default="verify")
    args = parser.parse_args()
    if args.phase == "clean":
        result = clean()
        if not (EVIDENCE / "cleanup-initial.json").exists():
            write(EVIDENCE / "cleanup-initial.json", result)
        write(EVIDENCE / "cleanup.json", result)
        print(json.dumps({key: value for key, value in result.items() if key != "resources"}, sort_keys=True))
        return 0
    if args.phase == "fresh" and (SANDBOX.exists() or MANIFEST.exists()):
        raise RuntimeError("CLEAN_ROOM_REQUIRES_ABSENT_CAMPAIGN_RESOURCES")
    modules = ["tests.test_trading_continuity_v1"]
    if args.phase == "git-boundary":
        modules = ["tests.test_trading_continuity_v1.OrdinarySourceTests.test_scientific_producer_requires_own_git_identity"]
    if args.phase == "transaction-after":
        modules = ["tests.test_trading_continuity_v1.OrdinarySourceTests." + name for name in (
            "test_ordinary_denied_admission_is_durable_and_idempotent",
            "test_ordinary_stale_replay_cancellation_survives_new_connection",
            "test_ordinary_paused_replay_cancellation_is_durable",
            "test_ordinary_disabled_policy_replay_cancellation_is_durable",
            "test_denial_re_evaluates_after_policy_revision_without_erasing_history",
            "test_ordinary_admission_real_errors_rollback_source_reservation_and_risk",
            "test_episode_replay_cannot_cancel_attempting_or_unknown",
            "test_independent_source_action_admission_terminal_sets")]
    if args.phase == "baseline-projection":
        modules = ["tests.test_trading_continuity_v1.ConfirmedBaselineDefects.test_mixed_mode_projection_has_no_combined_money_headline"]
    if args.phase == "regression":
        modules = ["tests.test_factory_strategy_execution_boundary_v1", "tests.test_paper_shadow_accounting_and_control_v1",
                   "tests.test_paper_shadow_execution_integrity_vertical_v1", "tests.test_trading_runtime_admission_concurrency_v1",
                   "tests.test_trading_runtime_policy_backup_restore_v1", "tests.test_trading_runtime_policy_v1",
                   "tests.test_hfic_research_scope_v1", "tests.test_opportunity_episodes_contract_v1",
                   "tests.test_execution_domain_modularity_and_fast_ci_v1",
                   "tests.test_science_to_strategy_handoff_v1", "tests.test_execution_evidence_seam_v1",
                   "tests.test_risk_and_economics_v1"]
    result = run(modules, phase=args.phase)
    if args.phase == "baseline":
        neighbors = run(["tests.test_science_to_strategy_handoff_v1", "tests.test_execution_evidence_seam_v1"], phase="baseline-neighbors")
        result["supported_handoff_neighbors"] = neighbors
        result["ordinary_chain"] = "PARTIAL_MISSING_PRODUCER_AND_RESULT_CALLER"
        result["base"] = "d244af69bfd7ddc2850b9e5e5823323956e325c4"
    write(EVIDENCE / (args.phase + ".json"), result)
    print(json.dumps({key: value for key, value in result.items() if key not in {"executed_cases", "candidate_input_bindings"}}, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
