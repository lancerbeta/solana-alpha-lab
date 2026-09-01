"""Executable-surface regression for collector_owner_pulse CLI git_sha binding."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_schedule_runtime import (  # noqa: E402
    DEPLOY_SHA_NAME,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)

DEPLOY_SHA = "96f32177e9f01b7865647923f5da9a36b3a5bfe1"
CONFIGURED_SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
SHA40 = re.compile(r"^[0-9a-f]{40}$")

_COPY_RELATIVES = (
    "scripts/collector_owner_pulse.py",
    "configs/observation_schedule_runtime_v1.yaml",
    "configs/factory_remote_operations_v1_1.yaml",
    "catalog/schemas/observation_schedule_runtime_v1.schema.json",
    "catalog/schemas/factory_remote_operations_v1_1.schema.json",
)


def _seed_synthetic_root(root: Path, *, deploy_sha: str | None) -> None:
    for rel in (
        "src/solana_alpha_lab",
        "scripts",
        "configs",
        "catalog/schemas",
        "local/factory_v1/observation_rdp",
    ):
        (root / rel).mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        ROOT / "src" / "solana_alpha_lab",
        root / "src" / "solana_alpha_lab",
        dirs_exist_ok=True,
    )
    for rel in _COPY_RELATIVES:
        shutil.copy2(ROOT / rel, root / rel)
    store = ObservationScheduleStore(
        root / "local" / "factory_v1" / "observation_schedule_state.sqlite"
    )
    store.close()
    if deploy_sha is not None:
        (root / DEPLOY_SHA_NAME).write_text(deploy_sha + "\n", encoding="utf-8")


def _run_pulse_cli(
    *,
    cwd: Path,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PYTHONPATH": str(cwd / "src"),
        # Fail closed if anything tries live Telegram/Jupiter env values.
        "JUPITER_FREE_API_KEY": "",
        "JUPITER_API_KEY": "",
        "FACTORY_TELEGRAM_BOT_TOKEN": "",
        "FACTORY_TELEGRAM_CHAT_ID": "",
    }
    return subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/collector_owner_pulse.py",
            "--mode",
            "dry-run",
            "--json",
            *(extra_args or []),
        ],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _parse_json_blob(stdout: str) -> dict:
    text = stdout.strip()
    # CLI prints summary JSON then packet JSON when --json.
    decoder = json.JSONDecoder()
    first, idx = decoder.raw_decode(text)
    rest = text[idx:].lstrip()
    second, _ = decoder.raw_decode(rest)
    assert isinstance(first, dict)
    assert isinstance(second, dict)
    packet = second.get("packet")
    assert isinstance(packet, dict)
    return {"summary": first, "packet": packet}


class CollectorOwnerPulseCliGitShaRepairTests(unittest.TestCase):
    def test_a_checkout_dry_run_renders(self) -> None:
        """A) Normal repository checkout reaches successful dry-run render."""
        completed = _run_pulse_cli(cwd=ROOT)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("TypeError", completed.stderr)
        self.assertNotIn(
            "git_sha() missing 1 required positional argument",
            completed.stderr + completed.stdout,
        )
        parsed = _parse_json_blob(completed.stdout)
        summary = parsed["summary"]
        packet = parsed["packet"]
        self.assertEqual(summary.get("mode"), "dry-run")
        self.assertEqual(int(summary.get("network_calls", -1)), 0)
        self.assertEqual(int(summary.get("credential_value_reads", -1)), 0)
        self.assertEqual(int(summary.get("jupiter_credentials_read", -1)), 0)
        self.assertIn("FACTORY / DAILY", summary.get("text") or "")
        producer = str(packet.get("deploy_git_sha") or "")
        self.assertRegex(producer, SHA40)
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(producer, head)

    def test_b_no_git_deploy_sha_resolves(self) -> None:
        """B) Sanctioned no-.git exact-SHA layout resolves producer SHA."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_synthetic_root(root, deploy_sha=DEPLOY_SHA)
            self.assertFalse((root / ".git").exists())
            completed = _run_pulse_cli(cwd=root)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            parsed = _parse_json_blob(completed.stdout)
            summary = parsed["summary"]
            packet = parsed["packet"]
            self.assertEqual(summary.get("mode"), "dry-run")
            self.assertEqual(int(summary.get("network_calls", -1)), 0)
            self.assertEqual(int(summary.get("credential_value_reads", -1)), 0)
            self.assertEqual(int(summary.get("jupiter_credentials_read", -1)), 0)
            self.assertEqual(packet.get("deploy_git_sha"), DEPLOY_SHA)
            self.assertIn("FACTORY / DAILY", summary.get("text") or "")

    def test_configured_producer_git_sha_beats_head_and_deploy_pin(self) -> None:
        """Decision-delta falsifier: runtime producer_git_sha wins via CLI adapter."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_synthetic_root(root, deploy_sha=DEPLOY_SHA)
            cfg_path = root / "configs" / "observation_schedule_runtime_v1.yaml"
            text = cfg_path.read_text(encoding="utf-8")
            if "producer_git_sha:" not in text:
                text = text.rstrip() + f"\nproducer_git_sha: '{CONFIGURED_SHA}'\n"
                cfg_path.write_text(text, encoding="utf-8")
            # Discriminate against git_sha(ROOT, None): pin and HEAD differ.
            self.assertNotEqual(CONFIGURED_SHA, DEPLOY_SHA)
            completed = _run_pulse_cli(cwd=root)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            parsed = _parse_json_blob(completed.stdout)
            summary = parsed["summary"]
            packet = parsed["packet"]
            self.assertEqual(packet.get("deploy_git_sha"), CONFIGURED_SHA)
            self.assertEqual(int(summary.get("network_calls", -1)), 0)
            self.assertEqual(int(summary.get("credential_value_reads", -1)), 0)
            self.assertEqual(int(summary.get("jupiter_credentials_read", -1)), 0)

    def test_c_no_git_missing_deploy_sha_fails_closed(self) -> None:
        """C) no-.git + missing deploy SHA fails closed with producer error."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_synthetic_root(root, deploy_sha=None)
            self.assertFalse((root / ".git").exists())
            self.assertFalse((root / DEPLOY_SHA_NAME).exists())
            completed = _run_pulse_cli(cwd=root)
            self.assertNotEqual(completed.returncode, 0)
            combined = completed.stderr + completed.stdout
            self.assertIn("PRODUCER_GIT_SHA_UNAVAILABLE", combined)

    def test_c_no_git_malformed_deploy_sha_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_synthetic_root(root, deploy_sha="NOT_A_SHA")
            completed = _run_pulse_cli(cwd=root)
            self.assertNotEqual(completed.returncode, 0)
            combined = completed.stderr + completed.stdout
            self.assertIn("PRODUCER_GIT_SHA_UNAVAILABLE", combined)


if __name__ == "__main__":
    unittest.main()
