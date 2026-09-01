"""Producer SHA resolution for exact-SHA no-.git ObservationSchedule deploys."""

from __future__ import annotations

import json
import os
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
    ObservationRuntimeError,
    git_sha,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)

DEPLOY_SHA = "96f32177e9f01b7865647923f5da9a36b3a5bfe1"
EXPLICIT = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def _init_git_repo_with_head(root: Path) -> str:
    """Create a minimal Git worktree with one commit; return HEAD SHA."""
    subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "ci@example.com"],
        cwd=str(root),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "ci"],
        cwd=str(root),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "seed"],
        cwd=str(root),
        check=True,
        capture_output=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(root),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class ProducerShaResolutionTests(unittest.TestCase):
    def test_explicit_valid_producer_sha_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(git_sha(root, EXPLICIT), EXPLICIT)

    def test_explicit_malformed_producer_sha_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            ObservationRuntimeError, "PRODUCER_GIT_SHA_UNAVAILABLE"
        ):
            git_sha(Path("."), "NOT_A_SHA")
        with self.assertRaisesRegex(
            ObservationRuntimeError, "PRODUCER_GIT_SHA_UNAVAILABLE"
        ):
            git_sha(Path("."), "A" * 40)

    def test_git_worktree_resolves_head(self) -> None:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(len(head), 40)
        self.assertEqual(git_sha(ROOT, None), head)

    def test_no_git_valid_factory_deploy_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / DEPLOY_SHA_NAME).write_text(DEPLOY_SHA + "\n", encoding="utf-8")
            self.assertFalse((root / ".git").exists())
            self.assertEqual(git_sha(root, None), DEPLOY_SHA)

    def test_missing_git_and_missing_deploy_pin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(
                ObservationRuntimeError, "PRODUCER_GIT_SHA_UNAVAILABLE"
            ):
                git_sha(root, None)

    def test_malformed_deploy_pin_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / DEPLOY_SHA_NAME).write_text("not-hex\n", encoding="utf-8")
            with self.assertRaisesRegex(
                ObservationRuntimeError, "PRODUCER_GIT_SHA_UNAVAILABLE"
            ):
                git_sha(root, None)
            (root / DEPLOY_SHA_NAME).write_text("A" * 40 + "\n", encoding="utf-8")
            with self.assertRaisesRegex(
                ObservationRuntimeError, "PRODUCER_GIT_SHA_UNAVAILABLE"
            ):
                git_sha(root, None)
            (root / DEPLOY_SHA_NAME).write_text("", encoding="utf-8")
            with self.assertRaisesRegex(
                ObservationRuntimeError, "PRODUCER_GIT_SHA_UNAVAILABLE"
            ):
                git_sha(root, None)

    def test_symlink_deploy_marker_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "outside.sha"
            target.write_text(DEPLOY_SHA + "\n", encoding="utf-8")
            marker = root / DEPLOY_SHA_NAME
            try:
                marker.symlink_to(target)
            except OSError:
                self.skipTest("symlinks unavailable on this host")
            with self.assertRaisesRegex(
                ObservationRuntimeError, "PRODUCER_GIT_SHA_UNAVAILABLE"
            ):
                git_sha(root, None)

    def test_git_head_beats_deploy_pin_when_both_present(self) -> None:
        """Precedence B before C: root Git HEAD wins over .factory_deploy_sha."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / DEPLOY_SHA_NAME).write_text(DEPLOY_SHA + "\n", encoding="utf-8")
            head = _init_git_repo_with_head(root)
            self.assertEqual(len(head), 40)
            self.assertNotEqual(head, DEPLOY_SHA)
            self.assertEqual(git_sha(root, None), head)

    def test_nested_no_git_does_not_inherit_parent_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "deploy"
            nested.mkdir()
            (nested / DEPLOY_SHA_NAME).write_text(DEPLOY_SHA + "\n", encoding="utf-8")
            # Parent git would succeed on walk-up without the root .git guard.
            _init_git_repo_with_head(root)
            self.assertFalse((nested / ".git").exists())
            self.assertEqual(git_sha(nested, None), DEPLOY_SHA)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / DEPLOY_SHA_NAME).write_text(DEPLOY_SHA + "\n", encoding="utf-8")
            value = git_sha(root, None)
            self.assertEqual(value, DEPLOY_SHA)
            # Fallback returns identity only — no authority receipt synthesis.
            self.assertNotIn("AUTHORIZE", value)
            self.assertEqual(len(value), 40)

    def test_no_live_tick_on_synthetic_no_git_deploy_root(self) -> None:
        """Cheapest vertical falsifier matching sanctioned VPS layout."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / DEPLOY_SHA_NAME).write_text(DEPLOY_SHA + "\n", encoding="utf-8")
            # Minimal package layout for CLI imports + store + runtime config.
            for rel in (
                "src/solana_alpha_lab",
                "scripts",
                "configs",
                "catalog/schemas",
                "local/factory_v1/observation_rdp",
            ):
                (root / rel).mkdir(parents=True, exist_ok=True)
            # Copy only what the CLI needs to import and validate runtime config.
            shutil.copytree(
                ROOT / "src" / "solana_alpha_lab",
                root / "src" / "solana_alpha_lab",
                dirs_exist_ok=True,
            )
            shutil.copy2(
                ROOT / "scripts" / "observation_schedule.py",
                root / "scripts" / "observation_schedule.py",
            )
            shutil.copy2(
                ROOT / "configs" / "observation_schedule_runtime_v1.yaml",
                root / "configs" / "observation_schedule_runtime_v1.yaml",
            )
            shutil.copy2(
                ROOT / "catalog" / "schemas" / "observation_schedule_runtime_v1.schema.json",
                root / "catalog" / "schemas" / "observation_schedule_runtime_v1.schema.json",
            )
            store = ObservationScheduleStore(
                root / "local" / "factory_v1" / "observation_schedule_state.sqlite"
            )
            store.close()
            env = {**os.environ, "PYTHONPATH": str(root / "src")}
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "scripts/observation_schedule.py",
                    "tick",
                    "--once",
                    "--runtime-config",
                    "configs/observation_schedule_runtime_v1.yaml",
                ],
                cwd=str(root),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertTrue(completed.stdout.strip(), completed.stderr)
            payload = json.loads(completed.stdout.strip().splitlines()[-1])
            self.assertEqual(payload.get("terminal"), "TICK_REFUSED_NO_LIVE_DEFAULT")
            self.assertEqual(int(payload.get("provider_calls", -1)), 0)
            self.assertEqual(int(payload.get("credential_reads", -1)), 0)
            self.assertNotEqual(payload.get("terminal"), "PRODUCER_GIT_SHA_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
