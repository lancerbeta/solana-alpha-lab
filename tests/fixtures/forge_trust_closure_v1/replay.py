"""Pinned offline replay using the existing audit runtime; no new bootstrap."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = "90ba76e37515b3d521478a6d05a149fb0f1d2b75"
AUDIT = "ea4afb52b9d188c378d2a9850ba1b26c85496821"
IMAGE = "smial-baa-v1-snapshot:local"
IMAGE_ID = "sha256:b1a9aeff235915d05f6b6d0436972e5609b631a6c77e2a9e0a664a04d36e96bb"


def call(argv, **kwargs):
    return subprocess.run(argv, check=True, **kwargs)


def git(*args):
    return call(["git", "-C", str(ROOT), *args], capture_output=True).stdout


def verify_receipt(path: Path, expected: str) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("RECEIPT_HASH_MISMATCH")
    receipt = json.loads(raw)
    for relative, digest in receipt["artifacts"].items():
        candidate = (path.parent / relative).resolve()
        if not candidate.is_relative_to(path.parent.resolve()) or candidate.is_symlink():
            raise ValueError("ARTIFACT_PATH_REJECTED")
        if hashlib.sha256(candidate.read_bytes()).hexdigest() != digest:
            raise ValueError("ARTIFACT_HASH_MISMATCH")
    return receipt


def terminal_exit_code(status: str, process_exit_code: int) -> int:
    """Only a graded PASS may report shell success."""
    if status == "TIMEOUT":
        return 124
    if status == "INTERRUPTED":
        return 130
    if status == "PASS":
        return process_exit_code
    return process_exit_code or 2


def terminal_status(state: dict, start_returncode: int | None, interrupted: str | None,
                    safety_pass: bool, summary_present: bool) -> str:
    if interrupted:
        return interrupted
    if state["OOMKilled"]:
        return "INTERRUPTED_RESOURCE_OR_SIGNAL"
    if start_returncode != 0 or state["Running"]:
        return "HARNESS_ERROR"
    if state["ExitCode"] in {137, 143}:
        return "INTERRUPTED_RESOURCE_OR_SIGNAL"
    if not safety_pass:
        return "HARNESS_ERROR"
    if not summary_present:
        return "HARNESS_ERROR_NO_TERMINAL_EVIDENCE"
    return "PASS" if state["ExitCode"] == 0 else "PRODUCT_TEST_FAILURE"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-commit")
    p.add_argument("--phase", choices=("wal", "producer", "bridge", "residual", "joint"))
    p.add_argument("--attempt")
    p.add_argument("--output-root", type=Path)
    p.add_argument("--verify", type=Path)
    p.add_argument("--expected-receipt-sha256")
    p.add_argument("--producer-volume")
    p.add_argument("--residual-group", choices=["all", "closure"], default="all")
    p.add_argument("--timeout-seconds", type=int, default=1800)
    p.add_argument("--docker", default="docker")
    a = p.parse_args()
    if a.verify:
        if not re.fullmatch(r"[0-9a-f]{64}", a.expected_receipt_sha256 or ""):
            p.error("EXACT_RECEIPT_HASH_REQUIRED")
        receipt = verify_receipt(a.verify, a.expected_receipt_sha256)
        print(json.dumps({"integrity": "PASS", "replay_status": receipt.get("status", "UNKNOWN"),
                          "claim": "RECEIPT_AND_ARTIFACT_INTEGRITY_ONLY"}))
        return 0
    if not all((a.source_commit, a.phase, a.attempt, a.output_root)):
        p.error("SOURCE_PHASE_ATTEMPT_OUTPUT_REQUIRED")
    if a.producer_volume and a.phase not in {"bridge", "joint"}:
        p.error("PRODUCER_VOLUME_FOR_CONSUMER_PHASES_ONLY")
    if not 1 <= a.timeout_seconds <= 1800:
        p.error("TIME_BOUND_OUTSIDE_ENVELOPE")
    if not re.fullmatch(r"[0-9a-f]{40}", a.source_commit) or not re.fullmatch(r"[a-z0-9-]{1,32}", a.attempt):
        p.error("INVALID_SOURCE_OR_ATTEMPT")
    if git("rev-parse", "HEAD").decode().strip() != a.source_commit:
        p.error("SOURCE_MUST_BE_EXACT_CURRENT_COMMITTED_HEAD")
    if git("diff", "HEAD", "--name-only").strip():
        p.error("SOURCE_TRACKED_BYTES_MUST_BE_CLEAN")
    git("merge-base", "--is-ancestor", BASE, a.source_commit)
    parent = call([a.docker, "image", "inspect", IMAGE], capture_output=True, text=True)
    if json.loads(parent.stdout)[0]["Id"] != IMAGE_ID:
        p.error("LOCKED_AUDIT_RUNTIME_NOT_AVAILABLE_NO_DOWNLOAD_AUTHORITY")
    output_root = a.output_root.resolve()
    if output_root == ROOT or output_root in ROOT.parents:
        p.error("INVALID_OUTPUT_OWNER_ROOT")
    out = output_root / f"{a.source_commit[:12]}-{a.phase}-{a.attempt}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "terminal.json").write_text(json.dumps({"status": "NOT_RUN", "stage": "SETUP"}), encoding="utf-8")
    name = f"ftc-{a.source_commit[:12]}-{a.phase}-{a.attempt}"
    volume = name + "-evidence"
    existing = call([a.docker, "container", "ls", "--all", "--format", "{{.Names}}"],
                    capture_output=True, text=True).stdout.splitlines()
    volumes = call([a.docker, "volume", "ls", "--format", "{{.Name}}"],
                   capture_output=True, text=True).stdout.splitlines()
    if name in existing or volume in volumes:
        p.error("ATTEMPT_ALREADY_EXISTS")
    if a.phase in {"bridge", "joint"}:
        if not a.producer_volume or not re.fullmatch(r"ftc-[a-z0-9-]+-evidence", a.producer_volume):
            p.error("OWNED_PRODUCER_VOLUME_REQUIRED")
        producer = json.loads(call([a.docker, "volume", "inspect", a.producer_volume],
                                  capture_output=True, text=True).stdout)[0]
        if producer.get("Labels", {}).get("ftc.campaign") != "FORGE_TRUST_CLOSURE_V1":
            p.error("PRODUCER_VOLUME_OWNER_MISMATCH")
    kit = out / "kit"
    kit.mkdir()
    archive = git("archive", AUDIT, "tests/fixtures/big_agentic_audit_v1")
    originals = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar.getmembers():
            if member.isdir():
                continue
            if not member.isfile() or Path(member.name).name != member.name.split("/")[-1]:
                p.error("AUDIT_MEMBER_INVALID")
            filename = member.name.removeprefix("tests/fixtures/big_agentic_audit_v1/")
            if "/" in filename or "\\" in filename:
                p.error("AUDIT_MEMBER_OUTSIDE_KIT")
            data = tar.extractfile(member).read()
            originals[filename] = hashlib.sha256(data).hexdigest()
            # A new campaign binding, never an edit to historical audit assets.
            if filename.endswith(".py"):
                data = data.replace(BASE.encode(), a.source_commit.encode())
            (kit / filename).write_bytes(data)
    if a.phase in {"residual", "joint"}:
        data = (ROOT / f"tests/fixtures/forge_trust_closure_v1/{a.phase}.py").read_bytes()
        (kit / f"{a.phase}.py").write_bytes(data)
    snapshot = IMAGE
    if a.source_commit != BASE:
        build = out / "build"
        build.mkdir()
        git("bundle", "create", str(build / "candidate.bundle"), "HEAD", "^" + BASE)
        (build / "Dockerfile").write_text(
            f"FROM {IMAGE}\nUSER 1000:1000\n"
            "COPY --chown=1000:1000 candidate.bundle /tmp/candidate.bundle\n"
            "RUN git -C /repo fetch /tmp/candidate.bundle HEAD && "
            f"git -C /repo checkout --detach {a.source_commit} && "
            "git -C /repo diff --exit-code HEAD\n", encoding="utf-8")
        snapshot = "ftc-candidate-" + a.source_commit[:12] + ":local"
        call([a.docker, "build", "--network", "none", "--pull=false", "-t", snapshot, str(build)],
             stdout=(out / "snapshot-build.log").open("wb"), stderr=subprocess.STDOUT)
    call([a.docker, "volume", "create", "--label", "ftc.campaign=FORGE_TRUST_CLOSURE_V1", volume], capture_output=True)
    call([a.docker, "run", "--rm", "--network", "none", "--read-only", "--user", "0:0",
          "--cap-drop", "ALL", "--cap-add", "CHOWN", "--mount",
          f"type=volume,source={volume},target=/audit", snapshot, "/bin/chown", "1000:1000", "/audit"])
    entry = {"wal": "product_probes.py", "producer": "run_campaign.py",
             "bridge": "bridge_probe.py", "residual": "residual.py", "joint": "joint.py"}[a.phase]
    argv = [a.docker, "create", "--name", name, "--label", "ftc.campaign=FORGE_TRUST_CLOSURE_V1",
            "--network", "none", "--read-only", "--user", "1000:1000", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--pids-limit", "128", "--memory", "2g",
            "--cpus", "2", "--init", "--tmpfs", "/tmp:rw,nosuid,noexec,size=134217728",
            "--mount", f"type=bind,source={kit},target=/kit,readonly",
            "--mount", f"type=volume,source={volume},target=/audit",
            "--env", "SIMULATION_ONLY=1", "--env", "OMP_NUM_THREADS=1", "--env", "OPENBLAS_NUM_THREADS=1"]
    if a.producer_volume:
        argv += ["--mount", f"type=volume,source={a.producer_volume},target=/input,readonly"]
    argv += [snapshot, "/opt/venv/bin/python", "-B", "/kit/" + entry]
    if a.phase not in {"bridge", "joint"}:
        argv += ["--phase", a.phase, "--output", "/audit/" + a.phase]
    if a.phase == "residual":
        argv += ["--group", a.residual_group]
    call(argv, capture_output=True)
    inspect = json.loads(call([a.docker, "inspect", name], capture_output=True, text=True).stdout)[0]
    manifest = dict(campaign_id="FORGE_TRUST_CLOSURE_V1", source_commit=a.source_commit,
                    baseline_product_commit=BASE, baseline_audit_head=AUDIT,
                    source_image=inspect["Image"], parent_runtime_image=IMAGE_ID,
                    original_kit_hashes=originals,
                    active_kit_hashes={f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in kit.iterdir()},
                    phase=a.phase, attempt=a.attempt, container=name, volume=volume,
                    timeout_seconds=a.timeout_seconds,
                    producer_volume=a.producer_volume, containment=inspect["HostConfig"],
                    external_model_calls=0, product_network="NONE")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    # Runtime preflight inside each pinned entry probes real UID/mount/egress/children.
    interrupted = None
    start_returncode = None
    with (out / "run.log").open("wb") as log:
        try:
            result = subprocess.run([a.docker, "start", "--attach", name],
                                    stdout=log, stderr=subprocess.STDOUT, timeout=a.timeout_seconds)
            start_returncode = result.returncode
        except subprocess.TimeoutExpired:
            interrupted = "TIMEOUT"
        except KeyboardInterrupt:
            interrupted = "INTERRUPTED"
        if interrupted:
            call([a.docker, "stop", "--time", "10", name], capture_output=True, timeout=30)
    state = json.loads(call([a.docker, "inspect", name], capture_output=True, text=True).stdout)[0]["State"]
    if state["Running"]:
        # A failed attach/transport must not leave our product process running.
        call([a.docker, "stop", "--time", "10", name], capture_output=True, timeout=30)
        state = json.loads(call([a.docker, "inspect", name], capture_output=True, text=True).stdout)[0]["State"]
        start_returncode = start_returncode or 2
    terminal = dict(status="INCOMPLETE",
                    state=state, start_returncode=start_returncode)
    files = {"wal": "wal/probes-summary.json", "producer": "producer/producer-summary.json",
             "bridge": "bridge-summary.json", "residual": "residual/residual-summary.json",
             "joint": "joint-summary.json"}
    for native, local in ((files[a.phase], "summary.json"), ("safety-preflight.json", "safety-preflight.json")):
        subprocess.run([a.docker, "cp", name + ":/audit/" + native, str(out / local)],
                       capture_output=True, check=False)
    safety = json.loads((out / "safety-preflight.json").read_text()) if (out / "safety-preflight.json").exists() else {}
    terminal["status"] = terminal_status(state, start_returncode, interrupted,
                                         bool(safety.get("pass")), (out / "summary.json").exists())
    terminal["next_safe_action"] = (
        "INSPECT_DECLARED_PROOF_SCOPE" if terminal["status"] == "PASS"
        else "INSPECT_RETAINED_LOG_SUMMARY_AND_SAFETY_BEFORE_NEW_ATTEMPT"
    )
    (out / "terminal.json").write_text(json.dumps(terminal, indent=2), encoding="utf-8")
    receipt = {"source_commit": a.source_commit, "status": terminal["status"], "artifacts": {
        f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir()
        if f.is_file() and f.name != "receipt.json"}}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    launcher_exit_code = terminal_exit_code(terminal["status"], state["ExitCode"])
    print(json.dumps(dict(container=name, volume=volume, status=terminal["status"],
                          process_exit_code=state["ExitCode"], exit_code=launcher_exit_code,
                          terminal_artifact="terminal.json", next_safe_action=terminal["next_safe_action"],
                          receipt_sha256=hashlib.sha256((out / "receipt.json").read_bytes()).hexdigest())))
    return launcher_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
