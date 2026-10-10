"""Real Git transitions: accepted incoming whitespace versus new candidate flaws."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ENTRY = Path(__file__).resolve().parents[1] / "scripts/precommit_diff_check.py"


class PrecommitDiffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "-q", "-b", "main")
        (self.root / "base.txt").write_text("base\n")
        self.git("add", ".")
        self.commit("base")
        self.git("branch", "task")
        (self.root / "historical.txt").write_text("accepted upstream whitespace \n")
        self.git("add", ".")
        self.commit("accepted upstream")
        self.main = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("update-ref", "refs/remotes/origin/main", self.main)
        self.git("checkout", "-q", "task")
        (self.root / "task.txt").write_text("new task\n")
        self.git("add", ".")
        self.commit("task")

    def git(self, *args, check=True):
        return subprocess.run(["git", *args], cwd=self.root, text=True,
                              capture_output=True, check=check)

    def commit(self, message):
        self.git("-c", "user.name=FtcTest", "-c", "user.email=ftc-test@example.invalid",
                 "commit", "-q", "-m", message)

    def check(self):
        result = subprocess.run([sys.executable, "-B", str(ENTRY)], cwd=self.root,
                                capture_output=True, text=True, timeout=15)
        return result.returncode, json.loads(result.stdout.splitlines()[0])

    def test_exact_main_merge_retains_history_and_rejects_new_candidate_whitespace(self):
        self.git("merge", "--no-commit", "--no-ff", "main")
        code, report = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(report["base"], self.main)
        self.assertEqual((self.root / "historical.txt").read_text(), "accepted upstream whitespace \n")
        (self.root / "task.txt").write_text("new task defect \n")
        self.git("add", "task.txt")
        self.assertNotEqual(self.check()[0], 0)

    def test_nonmain_merge_cannot_adopt_that_baseline(self):
        # Incoming object is the same, but it is not the exact current origin/main.
        self.git("update-ref", "refs/remotes/origin/main", "task")
        self.git("merge", "--no-commit", "--no-ff", "main")
        code, report = self.check()
        self.assertNotEqual(code, 0)
        self.assertEqual(report["scope"], "ORDINARY_STAGED_DIFF")

    def test_ordinary_staged_whitespace_remains_denied(self):
        (self.root / "task.txt").write_text("ordinary defect \n")
        self.git("add", "task.txt")
        code, report = self.check()
        self.assertNotEqual(code, 0)
        self.assertIsNone(report["base"])


if __name__ == "__main__":
    unittest.main()
