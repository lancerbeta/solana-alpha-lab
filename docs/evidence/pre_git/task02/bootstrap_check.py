#!/usr/bin/env python3
"""
TASK-02 workstation bootstrap validator.

Safe properties:
- read-only except for writing three evidence files next to this script;
- no provider/API/RPC calls;
- no repository creation;
- no secrets, usernames, hostnames, IP addresses, serials, or absolute paths
  are collected or written;
- Docker test uses the already cached official hello-world image with
  --pull=never and removes the container with --rm.
"""

from __future__ import annotations

import ctypes
import datetime as dt
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ENV_REPORT_PATH = SCRIPT_DIR / "env_report.txt"
TOOL_VERSIONS_PATH = SCRIPT_DIR / "tool_versions.json"
RECEIPT_PATH = SCRIPT_DIR / "validation_receipt.json"

EXPECTED_MIN_PYTHON = (3, 12)
DOCKER_TEST_CONTAINER = "smial-task02-validator-hello-world"


def decode_output(data: bytes) -> str:
    """Decode Windows command output without assuming one encoding."""
    if not data:
        return ""

    # WSL commonly emits UTF-16LE when captured from Windows PowerShell/Python.
    if data.count(b"\x00") > max(2, len(data) // 8):
        try:
            return data.decode("utf-16le", errors="replace").strip()
        except Exception:
            pass

    for encoding in ("utf-8", "cp866", "cp1251", "mbcs"):
        try:
            return data.decode(encoding).strip()
        except (UnicodeDecodeError, LookupError):
            continue

    return data.decode("utf-8", errors="replace").strip()


def run(command: list[str], timeout: int = 60) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        return {
            "exit_code": completed.returncode,
            "output": decode_output(completed.stdout),
        }
    except FileNotFoundError:
        return {"exit_code": 127, "output": "NOT_FOUND"}
    except subprocess.TimeoutExpired:
        return {"exit_code": 124, "output": "TIMEOUT"}


def first_line(result: dict[str, Any]) -> str:
    output = str(result.get("output", "")).strip()
    return output.splitlines()[0].strip() if output else "NO_OUTPUT"


def powershell_json(expression: str) -> dict[str, Any]:
    command = (
        "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); "
        "$OutputEncoding = [Console]::OutputEncoding; "
        + expression
    )
    result = run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        timeout=30,
    )
    if result["exit_code"] != 0:
        return {"_error": result["output"], "_exit_code": result["exit_code"]}
    try:
        return json.loads(result["output"])
    except json.JSONDecodeError:
        return {"_error": "INVALID_JSON", "_raw": result["output"]}


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def memory_total_gb() -> float | None:
    try:
        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return round(status.ullTotalPhys / (1024**3), 1)
    except Exception:
        return None


def parse_version_tuple(value: str) -> tuple[int, ...]:
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", value)
    if not match:
        return ()
    return tuple(int(part) for part in match.groups(default="0"))


def parse_wsl_version(output: str) -> str:
    match = re.search(r"\b(\d+\.\d+\.\d+\.\d+)\b", output)
    return match.group(1) if match else "UNKNOWN"


def redaction_scan(payloads: list[str]) -> tuple[bool, list[str]]:
    joined = "\n".join(payloads)
    findings: list[str] = []

    patterns = {
        "USER_HOME_PATH": re.compile(r"(?i)[A-Z]:\\Users\\"),
        "EMAIL_ADDRESS": re.compile(r"(?i)\b[\w.+-]+@[\w.-]+\.[A-Z]{2,}\b"),
        "SECRET_TERM": re.compile(
            r"(?i)\b(api[_-]?key|access[_-]?token|private[_-]?key|seed[_-]?phrase|password)\b"
        ),
    }

    for label, pattern in patterns.items():
        if pattern.search(joined):
            findings.append(label)

    return not findings, findings


def main() -> int:
    observed_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    os_info = powershell_json(
        """
        $os = Get-CimInstance Win32_OperatingSystem
        $cs = Get-CimInstance Win32_ComputerSystem
        $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
        $svc = Get-CimInstance Win32_Service -Filter "Name='W32Time'"
        $wslType = (
          Get-ItemProperty `
            "HKLM:\\SYSTEM\\CurrentControlSet\\Services\\W32Time\\Parameters" `
            -Name Type `
            -ErrorAction SilentlyContinue
        ).Type
        [pscustomobject]@{
          os = [string]$os.Caption
          version = [string]$os.Version
          build = [string]$os.BuildNumber
          os_architecture = [string]$os.OSArchitecture
          process_architecture = [string]$env:PROCESSOR_ARCHITECTURE
          timezone = [string](Get-TimeZone).Id
          time_service_state = [string]$svc.State
          time_service_start_mode = [string]$svc.StartMode
          time_mode = $(if ($wslType) { [string]$wslType } else { "UNKNOWN" })
          hypervisor_present = [bool]$cs.HypervisorPresent
          virtualization_firmware_enabled = [bool]$cpu.VirtualizationFirmwareEnabled
        } | ConvertTo-Json -Compress
        """
    )

    system_drive = os.environ.get("SystemDrive", "C:") + "\\"
    disk = shutil.disk_usage(system_drive)
    ram_gb = memory_total_gb()

    time_status = run(["w32tm.exe", "/query", "/status"], timeout=30)

    wsl_version_result = run(["wsl.exe", "--version"], timeout=30)
    wsl_status_result = run(["wsl.exe", "--status"], timeout=30)

    uv_result = run(["uv.exe", "--version"], timeout=30)
    uv_python_result = run(["uv.exe", "python", "find", "3.14"], timeout=30)
    git_result = run(["git.exe", "--version"], timeout=30)
    docker_client_result = run(
        ["docker.exe", "version", "--format", "{{.Client.Version}}"], timeout=30
    )
    docker_server_result = run(
        [
            "docker.exe",
            "version",
            "--format",
            "{{.Server.Version}} / {{.Server.Os}} / {{.Server.Arch}}",
        ],
        timeout=30,
    )
    compose_result = run(
        ["docker.exe", "compose", "version", "--short"], timeout=30
    )

    # Bounded, cached, official test image. No network pull is permitted.
    docker_test_result = run(
        [
            "docker.exe",
            "run",
            "--rm",
            "--pull=never",
            "--name",
            DOCKER_TEST_CONTAINER,
            "hello-world:latest",
        ],
        timeout=90,
    )
    residual_result = run(
        [
            "docker.exe",
            "ps",
            "-a",
            "--filter",
            f"name=^/{DOCKER_TEST_CONTAINER}$",
            "--format",
            "{{.ID}}",
        ],
        timeout=30,
    )
    residual_container = bool(residual_result["output"].strip())

    python_info = {
        "version": platform.python_version(),
        "architecture": platform.machine(),
        "implementation": sys.implementation.name,
        "venv_active": sys.prefix != sys.base_prefix,
    }

    checks = {
        "windows_os": platform.system() == "Windows",
        "python_3_12_plus": sys.version_info[:2] >= EXPECTED_MIN_PYTHON,
        "python_64_bit": platform.architecture()[0] == "64bit",
        "uv_available": uv_result["exit_code"] == 0,
        "uv_resolves_python_3_14": uv_python_result["exit_code"] == 0,
        "git_available": git_result["exit_code"] == 0,
        "windows_time_query": time_status["exit_code"] == 0,
        "wsl_available": wsl_status_result["exit_code"] == 0,
        "docker_client_available": docker_client_result["exit_code"] == 0,
        "docker_engine_healthy": docker_server_result["exit_code"] == 0,
        "docker_compose_available": compose_result["exit_code"] == 0,
        "docker_cached_hello_world": docker_test_result["exit_code"] == 0
        and "Hello from Docker!" in docker_test_result["output"],
        "no_residual_test_container": residual_result["exit_code"] == 0
        and not residual_container,
    }

    tool_versions = {
        "schema_version": "1.0",
        "task_id": "TASK-02",
        "observed_at_utc": observed_at,
        "os": {
            "name": os_info.get("os", platform.platform()),
            "version": os_info.get("version", platform.version()),
            "build": os_info.get("build", platform.version()),
            "architecture": os_info.get("os_architecture", platform.architecture()[0]),
            "process_architecture": os_info.get(
                "process_architecture", platform.machine()
            ),
        },
        "resources": {
            "ram_gb": ram_gb,
            "system_disk_total_gb": round(disk.total / (1024**3), 1),
            "system_disk_free_gb": round(disk.free / (1024**3), 1),
            "disk_acceptance_rule": "OBSERVED_NO_UNIVERSAL_THRESHOLD",
        },
        "time": {
            "timezone": os_info.get("timezone", "UNKNOWN"),
            "service_state": os_info.get("time_service_state", "UNKNOWN"),
            "service_start_mode": os_info.get(
                "time_service_start_mode", "UNKNOWN"
            ),
            "mode": os_info.get("time_mode", "UNKNOWN"),
            "status_query": "PASS"
            if time_status["exit_code"] == 0
            else f"FAIL_EXIT_{time_status['exit_code']}",
        },
        "virtualization": {
            "hypervisor_present": os_info.get("hypervisor_present", "UNKNOWN"),
            "virtualization_firmware_enabled": os_info.get(
                "virtualization_firmware_enabled", "UNKNOWN"
            ),
            "wsl_version": parse_wsl_version(wsl_version_result["output"]),
            "wsl_status": "PASS"
            if wsl_status_result["exit_code"] == 0
            else f"FAIL_EXIT_{wsl_status_result['exit_code']}",
            "user_linux_distribution_required": False,
        },
        "python": python_info,
        "tools": {
            "uv": first_line(uv_result),
            "git": first_line(git_result),
            "docker_client": first_line(docker_client_result),
            "docker_server": first_line(docker_server_result),
            "docker_compose": first_line(compose_result),
            "editor": "NOT_INSTALLED_NOT_REQUIRED_FOR_TASK02",
        },
        "runtime_tests": {
            "docker_hello_world_cached": "PASS"
            if checks["docker_cached_hello_world"]
            else "FAIL",
            "residual_test_container": "NONE"
            if checks["no_residual_test_container"]
            else "PRESENT_OR_UNKNOWN",
        },
        "scope_assertions": {
            "cash_spend_usd": 0,
            "provider_accounts_created": 0,
            "provider_api_rpc_calls": 0,
            "repository_created": False,
            "vps_created": False,
            "wallet_or_signer_configured": False,
        },
        "checks": checks,
    }

    report_lines = [
        "TASK-02 WORKSTATION ENVIRONMENT REPORT",
        f"observed_at_utc={observed_at}",
        "",
        "[OS]",
        f"name={tool_versions['os']['name']}",
        f"version={tool_versions['os']['version']}",
        f"build={tool_versions['os']['build']}",
        f"architecture={tool_versions['os']['architecture']}",
        f"process_architecture={tool_versions['os']['process_architecture']}",
        "",
        "[RESOURCES]",
        f"ram_gb={ram_gb}",
        f"system_disk_total_gb={tool_versions['resources']['system_disk_total_gb']}",
        f"system_disk_free_gb={tool_versions['resources']['system_disk_free_gb']}",
        "disk_acceptance_rule=OBSERVED_NO_UNIVERSAL_THRESHOLD",
        "",
        "[TIME]",
        f"timezone={tool_versions['time']['timezone']}",
        f"service_state={tool_versions['time']['service_state']}",
        f"service_start_mode={tool_versions['time']['service_start_mode']}",
        f"mode={tool_versions['time']['mode']}",
        f"status_query={tool_versions['time']['status_query']}",
        "",
        "[VIRTUALIZATION]",
        f"hypervisor_present={tool_versions['virtualization']['hypervisor_present']}",
        "virtualization_firmware_enabled="
        f"{tool_versions['virtualization']['virtualization_firmware_enabled']}",
        f"wsl_version={tool_versions['virtualization']['wsl_version']}",
        f"wsl_status={tool_versions['virtualization']['wsl_status']}",
        "user_linux_distribution_required=false",
        "",
        "[PYTHON]",
        f"runtime={python_info['version']} / {python_info['architecture']} / "
        f"{python_info['implementation']}",
        f"default_venv_active={str(python_info['venv_active']).lower()}",
        "project_dependency_policy=UV_MANAGED_ENVIRONMENT_ONLY",
        "",
        "[TOOLS]",
        f"uv={tool_versions['tools']['uv']}",
        f"git={tool_versions['tools']['git']}",
        f"docker_client={tool_versions['tools']['docker_client']}",
        f"docker_server={tool_versions['tools']['docker_server']}",
        f"docker_compose={tool_versions['tools']['docker_compose']}",
        f"editor={tool_versions['tools']['editor']}",
        "",
        "[RUNTIME_TESTS]",
        f"docker_hello_world_cached={tool_versions['runtime_tests']['docker_hello_world_cached']}",
        f"residual_test_container={tool_versions['runtime_tests']['residual_test_container']}",
        "",
        "[SCOPE]",
        "cash_spend_usd=0",
        "provider_accounts_created=0",
        "provider_api_rpc_calls=0",
        "repository_created=false",
        "vps_created=false",
        "wallet_or_signer_configured=false",
    ]
    report_text = "\n".join(report_lines) + "\n"

    json_text = json.dumps(tool_versions, indent=2, ensure_ascii=False) + "\n"
    redaction_ok, redaction_findings = redaction_scan([report_text, json_text])

    checks["redaction_scan"] = redaction_ok
    tool_versions["checks"] = checks
    tool_versions["redaction"] = {
        "status": "PASS" if redaction_ok else "FAIL",
        "findings": redaction_findings,
        "policy": "ALLOWLISTED_NON_SECRET_FIELDS_ONLY",
    }
    json_text = json.dumps(tool_versions, indent=2, ensure_ascii=False) + "\n"

    all_pass = all(checks.values())

    receipt = {
        "schema_version": "1.0",
        "task_id": "TASK-02",
        "validated_at_utc": observed_at,
        "result": "PASS" if all_pass else "FAIL",
        "checks": checks,
        "outputs": [
            "env_report.txt",
            "tool_versions.json",
            "validation_receipt.json",
        ],
        "notes": [
            "No username, hostname, IP, serial/device ID, token, or secret collected.",
            "No repository, provider account, API/RPC request, VPS, wallet, or signer created.",
            "Docker hello-world executed from local cache with --pull=never and --rm.",
        ],
    }

    ENV_REPORT_PATH.write_text(report_text, encoding="utf-8", newline="\n")
    TOOL_VERSIONS_PATH.write_text(json_text, encoding="utf-8", newline="\n")
    RECEIPT_PATH.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print("=== TASK-02 BOOTSTRAP VALIDATION ===")
    for name, passed in checks.items():
        print(f"{name}: {'PASS' if passed else 'FAIL'}")
    print(f"RESULT: {'PASS' if all_pass else 'FAIL'}")
    print("OUTPUTS: env_report.txt, tool_versions.json, validation_receipt.json")

    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
