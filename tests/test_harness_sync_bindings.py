from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import harness_sync  # noqa: E402
from owner_attention_gate import bound_delivery_evidence  # noqa: E402


def _run(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)


def _init_repo(worktree: Path) -> None:
    worktree.mkdir(parents=True, exist_ok=True)
    assert _run(["git", "init", "-b", "main"], cwd=worktree).returncode == 0
    _run(["git", "config", "user.email", "bindings@test"], cwd=worktree)
    _run(["git", "config", "user.name", "bindings"], cwd=worktree)
    _run(["git", "config", "core.autocrlf", "false"], cwd=worktree)


def _commit_all(worktree: Path, message: str) -> None:
    _run(["git", "-C", str(worktree), "add", "-A"], cwd=worktree)
    result = _run(["git", "-C", str(worktree), "commit", "-m", message], cwd=worktree)
    assert result.returncode == 0, result.stderr


class BindEvidenceIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.worktree = Path(self._tmp.name) / "repo"
        self.addCleanup(self._tmp.cleanup)
        self._build_fixture()

    def _build_fixture(self) -> None:
        wt = self.worktree
        _init_repo(wt)
        for relative in [
            "scripts/harness_sync.py",
            "scripts/owner_attention_gate.py",
            "scripts/validate_baseline.py",
        ]:
            target = wt / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        task_dir = wt / "docs/tasks"
        task_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            ROOT / "docs/tasks/CTRL-HARNESS-SYNC-DELIVERY-EVIDENCE-BINDINGS-V1.md",
            task_dir / "CTRL-HARNESS-SYNC-DELIVERY-EVIDENCE-BINDINGS-V1.md",
        )
        impl = wt / "scripts/harness_sync.py"
        impl.write_text(impl.read_text(encoding="utf-8") + "\n# fixture-base\n", encoding="utf-8")
        _commit_all(wt, "base")
        self.base = _run(["git", "-C", str(wt), "rev-parse", "HEAD"], cwd=wt).stdout.strip()
        _run(["git", "-C", str(wt), "branch", "origin/main", self.base], cwd=wt)
        evidence_dir = wt / "docs/evidence/control"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        for name in [
            "a1_harness_sync_delivery_evidence_bindings_completion_v1.json",
            "a1_harness_sync_delivery_evidence_bindings_review_v1.json",
            "a1_harness_sync_delivery_evidence_bindings_factory_fit_v1.json",
        ]:
            shutil.copy2(ROOT / "docs/evidence/control" / name, evidence_dir / name)
        impl.write_text(impl.read_text(encoding="utf-8") + "# fixture-change\n", encoding="utf-8")
        task_path = task_dir / "CTRL-HARNESS-SYNC-DELIVERY-EVIDENCE-BINDINGS-V1.md"
        task_text = task_path.read_text(encoding="utf-8")
        task_text = task_text.replace(
            "expected_base: 7e529058293c13381c7ef962d9d4a97ef3d220a5",
            f"expected_base: {self.base}",
        )
        task_text = task_text.replace(
            "expected_upstream_oid: 7e529058293c13381c7ef962d9d4a97ef3d220a5",
            f"expected_upstream_oid: {self.base}",
        )
        task_path.write_text(task_text, encoding="utf-8")
        completion_path = evidence_dir / "a1_harness_sync_delivery_evidence_bindings_completion_v1.json"
        completion = json.loads(completion_path.read_text(encoding="utf-8"))
        completion["base_main"] = self.base
        completion_path.write_text(json.dumps(completion, indent=2) + "\n", encoding="utf-8")
        _commit_all(wt, "task delta")
        self.head = _run(["git", "-C", str(wt), "rev-parse", "HEAD"], cwd=wt).stdout.strip()

    def _run_bind(self, *extra: str) -> subprocess.CompletedProcess:
        cmd = [
            sys.executable,
            "-B",
            str(self.worktree / "scripts/harness_sync.py"),
            "bind-evidence",
            "--task-id",
            "CTRL-HARNESS-SYNC-DELIVERY-EVIDENCE-BINDINGS-V1",
            *extra,
        ]
        return _run(cmd, cwd=self.worktree)

    def test_apply_then_verify_and_guard_readback(self) -> None:
        original_root = harness_sync.ROOT
        harness_sync.ROOT = self.worktree.resolve()
        self.addCleanup(setattr, harness_sync, "ROOT", original_root)
        apply = self._run_bind("--apply")
        self.assertEqual(apply.returncode, 0, apply.stderr)
        verify = self._run_bind("--verify")
        self.assertEqual(verify.returncode, 0, verify.stderr)
        completion = json.loads(
            (
                self.worktree
                / "docs/evidence/control/a1_harness_sync_delivery_evidence_bindings_completion_v1.json"
            ).read_text(encoding="utf-8")
        )
        review = json.loads(
            (
                self.worktree
                / "docs/evidence/control/a1_harness_sync_delivery_evidence_bindings_review_v1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(completion["base_main"], self.base)
        self.assertEqual(
            review["reviewed_bindings_sha256"],
            hashlib.sha256(
                json.dumps(
                    completion["implementation_bindings"],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            ).hexdigest(),
        )
        receipt = {
            "task": {"task_id": "CTRL-HARNESS-SYNC-DELIVERY-EVIDENCE-BINDINGS-V1"},
            "selected": [
                {
                    "semantic_role": "DELIVERY_EVIDENCE",
                    "path": "docs/evidence/control/a1_harness_sync_delivery_evidence_bindings_completion_v1.json",
                    "sha256": hashlib.sha256(
                        (
                            self.worktree
                            / "docs/evidence/control/a1_harness_sync_delivery_evidence_bindings_completion_v1.json"
                        ).read_bytes()
                    ).hexdigest(),
                }
            ],
        }
        evidence = bound_delivery_evidence(
            self.worktree,
            receipt,
            expected_base=self.base,
            head=self.head,
        )
        self.assertTrue(evidence["factory_fit_pass"])

    def test_scope_violation_fails_closed(self) -> None:
        original_root = harness_sync.ROOT
        harness_sync.ROOT = self.worktree.resolve()
        self.addCleanup(setattr, harness_sync, "ROOT", original_root)
        outsider = self.worktree / "outside.txt"
        outsider.write_text("outside\n", encoding="utf-8")
        _commit_all(self.worktree, "outside scope")
        result = self._run_bind("--apply")
        self.assertEqual(result.returncode, 2)
        self.assertIn("BINDING_SCOPE_VIOLATION", result.stderr)

    def test_second_apply_is_idempotent(self) -> None:
        original_root = harness_sync.ROOT
        harness_sync.ROOT = self.worktree.resolve()
        self.addCleanup(setattr, harness_sync, "ROOT", original_root)
        first = self._run_bind("--apply")
        self.assertEqual(first.returncode, 0, first.stderr)
        before = {
            relative: (self.worktree / relative).read_bytes()
            for relative in [
                "docs/evidence/control/a1_harness_sync_delivery_evidence_bindings_completion_v1.json",
                "docs/evidence/control/a1_harness_sync_delivery_evidence_bindings_review_v1.json",
                "docs/evidence/control/a1_harness_sync_delivery_evidence_bindings_factory_fit_v1.json",
            ]
        }
        second = self._run_bind("--apply")
        self.assertEqual(second.returncode, 0, second.stderr)
        for relative, content in before.items():
            self.assertEqual((self.worktree / relative).read_bytes(), content)

    def test_verify_all_delivered_reports_real_repo(self) -> None:
        original_root = harness_sync.ROOT
        harness_sync.ROOT = ROOT
        self.addCleanup(setattr, harness_sync, "ROOT", original_root)
        payload = harness_sync.verify_all_delivered_evidence()
        self.assertGreater(payload["total"], 0)
        self.assertIn("passed", payload)
        self.assertIn("mismatched", payload)


if __name__ == "__main__":
    unittest.main()
