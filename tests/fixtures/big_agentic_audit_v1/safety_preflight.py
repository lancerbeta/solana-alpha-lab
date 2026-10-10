"""Harmless probes of the actual container boundary, never a real provider."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path


def check() -> dict:
    results = {}
    for name, path in (("source_readonly", "/repo/BAA_FORBIDDEN_WRITE"),
                       ("kit_readonly", "/kit/BAA_FORBIDDEN_WRITE"),
                       ("root_readonly", "/BAA_FORBIDDEN_WRITE")):
        try:
            Path(path).write_text("BAA", encoding="utf-8")
        except OSError:
            results[name] = True
        else:
            results[name] = False
    results["unprivileged"] = os.geteuid() != 0
    def visible(path: str) -> bool:
        try:
            return Path(path).exists()
        except PermissionError:
            return False
    results["no_accessible_socket_or_credentials"] = not any(
        visible(p) for p in ("/var/run/docker.sock", "/root/.ssh", "/root/.aws", "/repo/.env")
    )
    # Read the routing table before any attempted send. No packet is emitted.
    routes = Path("/proc/net/route").read_text().splitlines()[1:]
    results["no_external_route"] = not any(line.split()[1] == "00000000" for line in routes)
    results["only_loopback_interface"] = set(socket.if_nameindex()) == {(1, "lo")}
    # TEST-NET destination, only after route denial is proved. connect() then
    # fails locally with no routable interface; no real service is contacted.
    if results['no_external_route'] and results['only_loopback_interface']:
        import errno
        probe = socket.socket()
        try:
            probe.settimeout(1)
            probe.connect(('192.0.2.1', 9))
        except OSError as exc:
            results['egress_denied_before_routing'] = exc.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH)
        else:
            results['egress_denied_before_routing'] = False
        finally:
            probe.close()
    else:
        results['egress_denied_before_routing'] = False
    git_head = subprocess.run(['git', '-C', '/repo', 'rev-parse', 'HEAD'],
                              text=True, capture_output=True, check=True).stdout.strip()
    results['source_base_verified'] = git_head == '90ba76e37515b3d521478a6d05a149fb0f1d2b75'
    results['source_tracked_bytes_verified'] = subprocess.run(
        ['git', '-C', '/repo', 'diff', '--exit-code', 'HEAD'], capture_output=True).returncode == 0
    child = subprocess.run([sys.executable, "-B", "-c",
        "import os,pathlib; p=pathlib.Path('/repo/BAA_CHILD_FORBIDDEN'); "
        "\ntry: p.write_text('BAA'); denied=False"
        "\nexcept OSError: denied=True"
        "\nprint(int(os.geteuid()!=0 and denied))"], text=True, capture_output=True, check=True)
    results["child_inherits_readonly_uid"] = child.stdout.strip() == "1"
    Path("/audit/tmp").mkdir(parents=True, exist_ok=True)
    writable = Path("/audit/BAA_WRITE_CONTROL")
    writable.write_text("BAA", encoding="utf-8")
    results["test_root_writable"] = writable.read_text() == "BAA"
    writable.unlink()
    results["pass"] = all(results.values())
    results["scope"] = "OS_CONTAINER_BOUNDARY; host agent tools are outside this boundary"
    Path('/audit/safety-preflight.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    if not results['pass']:
        print(json.dumps({'audit_preflight': results}), flush=True)
    return results


if __name__ == "__main__":
    value = check()
    Path("/audit/safety-preflight.json").write_text(json.dumps(value, indent=2), encoding="utf-8")
    print(json.dumps(value))
    raise SystemExit(0 if value["pass"] else 2)
