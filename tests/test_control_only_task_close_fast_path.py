from __future__ import annotations

import copy
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "control/control_only_task_close_fast_path_v1.yaml"
MODULE_PATH = ROOT / "scripts/control_only_task_close_fast_path.py"


def load_module():
    spec = importlib.util.spec_from_file_location("control_only_task_close_fast_path", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fast_path = load_module()


def policy() -> dict:
    return yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))


def eligible_changes() -> list[tuple[str, str]]:
    return [
        (
            "A",
            "docs/evidence/task29/a4_project_sources_activation_and_task_close_acceptance_v1.json",
        ),
        ("M", "docs/project_sources/release_registry_v1.yaml"),
        ("M", "catalog/assets/core.yaml"),
        ("M", "catalog/assets/lifecycle.yaml"),
        ("M", "catalog/catalog_manifest.yaml"),
        ("M", "catalog/generated/asset_edges.json"),
        ("M", "docs/PROJECT_MAP.md"),
    ]


def synthetic_registry() -> dict:
    return {
        "active_ui_release_id": "PSR-0004-T29-EXAMPLE",
        "active_ui_state": "REGISTRY_ACTIVATION_CONFIRMED",
        "latest_candidate_release_id": None,
        "releases": [
            {
                "release_id": "PSR-0004-T29-EXAMPLE",
                "task_id": "TASK-29",
                "status": "ACTIVATED_BY_OWNER_SMOKE",
                "activation_receipt": (
                    "docs/evidence/task29/"
                    "a4_project_sources_activation_and_task_close_acceptance_v1.json"
                ),
                "artifact_bindings": {
                    "canonical_manifest": {
                        "path": (
                            "docs/project_sources/releases/"
                            "PSR-0004-T29-EXAMPLE/canonical_manifest.yaml"
                        ),
                        "sha256": "a" * 64,
                    }
                },
            }
        ],
    }


def synthetic_receipt() -> dict:
    terminal = "TASK29_SOURCE_SMOKE=PASS; OWNER_DONE_ACCEPTANCE"
    return {
        "schema": "smial.project_sources.activation.receipt",
        "schema_version": "1.0",
        "task_id": "TASK-29",
        "release_id": "PSR-0004-T29-EXAMPLE",
        "status": "ACTIVATED_BY_OWNER_SMOKE",
        "owner_terminal": {
            "source_smoke": "TASK29_SOURCE_SMOKE=PASS",
            "done_acceptance": "OWNER_DONE_ACCEPTANCE",
            "reported_terminal": terminal,
        },
        "activation_evidence": {
            "class": "OWNER_ATTESTATION",
            "smoke_outcome": "PASS",
            "reported_terminal": terminal,
        },
        "manifest_binding": synthetic_registry()["releases"][0]["artifact_bindings"][
            "canonical_manifest"
        ],
        "decision": {
            "task_status": "DONE",
            "canonical_task_done": True,
            "next_task_selected": False,
        },
        "authority": {
            "provider_api_rpc_wss_calls": 0,
            "credential_uses": 0,
            "r2_r3_reads": 0,
            "wallet_signer_transaction_actions": 0,
            "cash_spend_usd_cents": 0,
            "dependency_changes": 0,
            "project_sources_ui_changes": 0,
        },
        "factory_fit": {"verdict": "PASS_WITH_LIMITATIONS"},
        "project_sources_disposition": {
            "kind": "ACTIVATION_RECEIPT",
            "release_id": "PSR-0004-T29-EXAMPLE",
            "registry_path": "docs/project_sources/release_registry_v1.yaml",
        },
    }


class ChangeSetClassificationTests(unittest.TestCase):
    def test_exact_combined_close_change_set_is_eligible(self) -> None:
        result = fast_path.classify_change_set(eligible_changes(), policy())
        self.assertTrue(result.eligible)
        self.assertEqual(
            result.receipt_path,
            "docs/evidence/task29/a4_project_sources_activation_and_task_close_acceptance_v1.json",
        )
        self.assertEqual(result.errors, ())

    def test_material_or_ambiguous_change_sets_fail_closed(self) -> None:
        mutations = {
            "product": eligible_changes() + [("M", "src/solana_alpha_lab/model.py")],
            "test": eligible_changes() + [("M", "tests/test_example.py")],
            "schema": eligible_changes() + [("M", "catalog/schemas/example.json")],
            "workflow": eligible_changes() + [("M", ".github/workflows/ci.yml")],
            "release_bytes": eligible_changes()
            + [("M", "docs/project_sources/releases/PSR-0004-T29-EXAMPLE/roadmap.md")],
            "second_receipt": eligible_changes()
            + [
                (
                    "A",
                    "docs/evidence/task30/a4_project_sources_activation_and_task_close_acceptance_v1.json",
                )
            ],
            "delete": [("D", path) if index == 1 else (status, path) for index, (status, path) in enumerate(eligible_changes())],
            "rename": [("R100", eligible_changes()[0][1])] + eligible_changes()[1:],
            "missing_registry": [item for item in eligible_changes() if item[1] != "docs/project_sources/release_registry_v1.yaml"],
            "unexpected_catalog": eligible_changes() + [("M", "catalog/query_recipes.yaml")],
        }
        for label, changes in mutations.items():
            with self.subTest(label=label):
                result = fast_path.classify_change_set(changes, policy())
                self.assertFalse(result.eligible)
                self.assertTrue(result.errors)


class CombinedReceiptTests(unittest.TestCase):
    def test_exact_future_combined_receipt_passes(self) -> None:
        errors = fast_path.validate_combined_receipt(
            synthetic_receipt(), synthetic_registry(), policy()
        )
        self.assertEqual(errors, set())

    def test_missing_or_false_truth_fails_closed(self) -> None:
        cases: dict[str, dict] = {}

        missing_smoke = synthetic_receipt()
        del missing_smoke["owner_terminal"]["source_smoke"]
        cases["missing_smoke"] = missing_smoke

        missing_done = synthetic_receipt()
        del missing_done["owner_terminal"]["done_acceptance"]
        cases["missing_done"] = missing_done

        wrong_manifest = synthetic_receipt()
        wrong_manifest["manifest_binding"]["sha256"] = "b" * 64
        cases["wrong_manifest"] = wrong_manifest

        next_task = synthetic_receipt()
        next_task["decision"]["next_task_selected"] = True
        cases["next_task"] = next_task

        missing_zero = synthetic_receipt()
        del missing_zero["authority"]["cash_spend_usd_cents"]
        cases["missing_zero"] = missing_zero

        factory_fail = synthetic_receipt()
        factory_fail["factory_fit"]["verdict"] = "FAIL"
        cases["factory_fail"] = factory_fail

        for label, receipt in cases.items():
            with self.subTest(label=label):
                self.assertTrue(
                    fast_path.validate_combined_receipt(
                        receipt, synthetic_registry(), policy()
                    )
                )

        candidate_registry = copy.deepcopy(synthetic_registry())
        candidate_registry["releases"][0]["status"] = (
            "VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING"
        )
        candidate_registry["active_ui_release_id"] = None
        self.assertTrue(
            fast_path.validate_combined_receipt(
                synthetic_receipt(), candidate_registry, policy()
            )
        )


class RepositoryRunnerTests(unittest.TestCase):
    def make_root(self, temporary: str) -> Path:
        root = Path(temporary)
        (root / "control").mkdir(parents=True)
        (root / "docs/project_sources").mkdir(parents=True)
        receipt_path = root / eligible_changes()[0][1]
        receipt_path.parent.mkdir(parents=True)
        (root / "control/control_only_task_close_fast_path_v1.yaml").write_text(
            POLICY_PATH.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (root / "docs/project_sources/release_registry_v1.yaml").write_text(
            yaml.safe_dump(synthetic_registry(), sort_keys=False), encoding="utf-8"
        )
        receipt_path.write_text(
            json.dumps(synthetic_receipt()), encoding="utf-8"
        )
        return root

    def test_forbidden_diff_runs_no_child_validation(self) -> None:
        calls: list[list[str]] = []

        def runner(command, **_kwargs):
            calls.append(command)
            if command[:3] == ["git", "status", "--porcelain=v1"]:
                return subprocess.CompletedProcess(command, 0, "", "")
            if command[:3] == ["git", "rev-parse", "HEAD"]:
                return subprocess.CompletedProcess(command, 0, "c" * 40, "")
            if command[:3] == ["git", "show", "-s"]:
                return subprocess.CompletedProcess(command, 0, "d" * 40, "")
            if command[:2] == ["git", "merge-base"]:
                return subprocess.CompletedProcess(command, 0, "b" * 40, "")
            if command[:3] == ["git", "diff", "--name-status"]:
                diff = "M\tsrc/solana_alpha_lab/model.py\n"
                return subprocess.CompletedProcess(command, 0, diff, "")
            raise AssertionError(f"unexpected command after ineligible diff: {command}")

        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_root(temporary)
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(
                    fast_path.FastPathError, "FAST_PATH_INELIGIBLE"
                ):
                    fast_path.run_fast_path(root=root, runner=runner)

        self.assertEqual(len(calls), 5)

    def test_eligible_diff_runs_exact_focused_checks(self) -> None:
        calls: list[list[str]] = []

        def runner(command, **_kwargs):
            calls.append(command)
            if command[:3] == ["git", "status", "--porcelain=v1"]:
                return subprocess.CompletedProcess(command, 0, "", "")
            if command[:3] == ["git", "rev-parse", "HEAD"]:
                return subprocess.CompletedProcess(command, 0, "c" * 40, "")
            if command[:3] == ["git", "show", "-s"]:
                return subprocess.CompletedProcess(command, 0, "d" * 40, "")
            if command[:2] == ["git", "merge-base"]:
                return subprocess.CompletedProcess(command, 0, "b" * 40, "")
            if command[:3] == ["git", "diff", "--name-status"]:
                diff = "\n".join(
                    f"{status}\t{path}" for status, path in eligible_changes()
                )
                return subprocess.CompletedProcess(command, 0, diff, "")
            return subprocess.CompletedProcess(command, 0, "PASS", "")

        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_root(temporary)
            with contextlib.redirect_stdout(io.StringIO()):
                result = fast_path.run_fast_path(root=root, runner=runner)

        self.assertEqual(result["decision"], "ELIGIBLE_FOCUSED_GATE_PASS")
        focused = calls[5:]
        self.assertEqual(focused[0][:3], ["git", "diff", "--check"])
        self.assertEqual(
            focused[1],
            [
                sys.executable,
                "-B",
                "scripts/secret_scan.py",
                "--self-test",
                "--scan-repository",
            ],
        )
        self.assertEqual(focused[2][-1], "scripts/validate_catalog.py")
        self.assertEqual(focused[3][-1], "--check")
        self.assertEqual(focused[4][3:5], ["unittest", "tests.test_project_sources_release_registry"])


if __name__ == "__main__":
    unittest.main()
