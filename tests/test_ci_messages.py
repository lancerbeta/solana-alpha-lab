from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


messages = load_module("ci_fail_closed_messages", "scripts/ci_fail_closed_messages.py")
ci = load_module("validate_ci", "scripts/validate_ci.py")
harness_sync = load_module("harness_sync", "scripts/harness_sync.py")


class DerivedHashDriftMessageTests(unittest.TestCase):
    def test_detects_baton_catalog_mismatch(self) -> None:
        text = "ERROR: canonical_catalog_hash_mismatch:CATALOG-ROOT-001:core:foo:dead!=beef"
        self.assertTrue(messages.is_derived_hash_drift(text))

    def test_detects_catalog_sha256_mismatch(self) -> None:
        text = "ERROR: sha256_mismatch:CATALOG-ROOT-001"
        self.assertTrue(messages.is_derived_hash_drift(text))

    def test_detects_navigation_stale_output(self) -> None:
        self.assertTrue(messages.is_derived_hash_drift("STALE_OUTPUTS: docs/PROJECT_MAP.md"))

    def test_unrelated_failure_is_not_mapped(self) -> None:
        self.assertFalse(messages.is_derived_hash_drift("ERROR: workflow_exact_contract_mismatch"))

    def test_summary_contains_actionable_command(self) -> None:
        summary = messages.derived_hash_drift_summary()
        self.assertIn("DERIVED_HASH_DRIFT:", summary)
        self.assertIn("scripts/harness_sync.py --apply", summary)

    def test_apply_command_with_explicit_base_ref(self) -> None:
        cmd = messages.harness_sync_apply_command(
            base_ref="5c0efd1619f048c61e6f056b83449571e0abfdae"
        )
        self.assertIn(
            "--base-ref 5c0efd1619f048c61e6f056b83449571e0abfdae",
            cmd,
        )
        self.assertNotIn("RECOVERY", cmd)

    def test_apply_command_without_base_ref_marks_recovery(self) -> None:
        cmd = messages.harness_sync_apply_command(
            base_ref=None,
            root=Path("/nonexistent-empty-root"),
        )
        self.assertIn("RECOVERY_FULL_ORACLE", cmd)

    def test_task_contract_path_resolves_expected_base(self) -> None:
        from harness_sync import _expected_base_from_task_contract

        base = _expected_base_from_task_contract(
            "docs/tasks/COLLECTOR_SAMPLING_ORACLE_APPLIED_PROBABILITY_REPAIR_V1.md",
            root=ROOT,
        )
        self.assertEqual(base, "5c0efd1619f048c61e6f056b83449571e0abfdae")
        summary = messages.derived_hash_drift_summary(
            root=ROOT,
        )
        if messages.routine_harness_sync_base_ref(root=ROOT) is not None:
            self.assertIn("--base-ref 5c0efd1619f048c61e6f056b83449571e0abfdae", summary)
        else:
            self.assertIn("RECOVERY_FULL_ORACLE", summary)

    def test_emit_writes_to_stderr(self) -> None:
        buffer = io.StringIO()
        messages.emit_derived_hash_drift_summary(stream=buffer)
        self.assertIn("DERIVED_HASH_DRIFT:", buffer.getvalue())


class ValidateCiDriftPresentationTests(unittest.TestCase):
    def test_run_checked_prints_summary_before_child_output(self) -> None:
        child_stdout = "\n".join(
            [
                "BATON_VALIDATION: FAIL",
                "ERROR_TYPE: BatonValidationError",
                "ERROR: canonical_catalog_hash_mismatch:asset:path:dead!=beef",
            ]
        )
        completed = subprocess.CompletedProcess([], 1, child_stdout, "")

        def runner(*_args, **_kwargs):
            return completed

        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            with self.assertRaises(ci.CiValidationError):
                ci.run_checked("BATON_VALIDATION", ["synthetic"], runner=runner)
        lines = stdout.getvalue().splitlines()
        self.assertEqual(lines[0], messages.derived_hash_drift_summary())
        self.assertIn("canonical_catalog_hash_mismatch", stdout.getvalue())

    def test_run_checked_leaves_unrelated_failures_unmapped(self) -> None:
        completed = subprocess.CompletedProcess([], 1, "RESULT: FAIL\nERROR: uv_lock_mutated", "")
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            with self.assertRaises(ci.CiValidationError):
                ci.run_checked("PYTHON_LOCK", ["synthetic"], runner=mock.Mock(return_value=completed))
        self.assertNotIn("DERIVED_HASH_DRIFT:", stdout.getvalue())


class HarnessSyncStagingScopeTests(unittest.TestCase):
    def test_unrelated_staged_path_skips_drift_check(self) -> None:
        scopes = harness_sync.drift_scopes_for_paths({"local/noncatalog.tmp"})
        self.assertEqual(scopes, {"assets": False, "checkpoint": False, "navigation": False})
        self.assertEqual(harness_sync.check_drift(scoped_paths={"local/noncatalog.tmp"}), [])

    def test_staged_catalog_asset_triggers_asset_scope(self) -> None:
        scopes = harness_sync.drift_scopes_for_paths({"catalog/assets/core.yaml"})
        self.assertTrue(scopes["assets"])
        self.assertTrue(scopes["checkpoint"])
        self.assertTrue(scopes["navigation"])


if __name__ == "__main__":
    unittest.main()
