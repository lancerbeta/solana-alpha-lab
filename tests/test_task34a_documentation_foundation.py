from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from solana_alpha_lab.task34a_documentation_foundation import (
    ContextBindingError,
    evaluate_context,
    render_context_text,
)
from generate_navigation import render_operator_navigation
from validate_catalog import load_and_validate


CONFIG_PATH = ROOT / "configs/task34a_documentation_foundation_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task34a_documentation_foundation.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task34a/documentation_foundation_v1.json"
CONTEXT_SCRIPT_PATH = ROOT / "scripts/show_task34a_context.py"
OPERATOR_NAVIGATION_PATH = ROOT / "docs/OPERATOR_NAVIGATION.md"
RUNBOOK_PATHS = (
    ROOT / "docs/runbooks/task_entry_and_resume.md",
    ROOT / "docs/runbooks/source_mirror_drift.md",
    ROOT / "docs/runbooks/external_authority_stop.md",
)
EXPECTED_MIRROR_STATES = [
    "MIRROR_MATCHES_ACTIVE_RELEASE",
    "STALE_MIRROR_ACTIVE_RELEASE_CONFIRMED",
    "MIRROR_UNAVAILABLE",
    "MIRROR_CONFLICT_REQUIRES_CONTROL_REVIEW",
]


def write_yaml(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False, allow_unicode=True), encoding="utf-8")


def sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_synthetic_active_release(root: Path) -> tuple[Path, Path]:
    """Build only test bytes; no production release or user directory is used."""
    release_id = "PSR-TEST-ACTIVE"
    bundle = root / "docs/project_sources/releases" / release_id
    bundle.mkdir(parents=True)
    source_bytes = {
        "Solana_Memecoin_Intraday_Alpha_Lab_Operating_System_v8_5.md": (
            "# SYNTHETIC OPERATING SYSTEM v1\n".encode("utf-8")
        ),
        "research.md": "Synthetic Blueprint v1\n".encode("utf-8"),
        "roadmap.md": "Synthetic Roadmap v1\n".encode("utf-8"),
        "state.md": "Synthetic State v1\n".encode("utf-8"),
        "archive.md": "Synthetic Archive v1\n".encode("utf-8"),
        "task.md": "# TASK-SYNTHETIC — Test task\n".encode("utf-8"),
    }
    for filename, content in source_bytes.items():
        (bundle / filename).write_bytes(content)

    canonical: dict[str, dict[str, object]] = {
        "canonical_manifest": {
            "current_filename": "canonical_manifest.yaml",
            "semantic_version": "1.0",
            "required_header": "schema: solana_alpha_lab.canonical_manifest",
            "self_checksum_policy": "CHECKSUMS_SHA256",
        },
        "operating_system": {
            "current_filename": "Solana_Memecoin_Intraday_Alpha_Lab_Operating_System_v8_5.md",
            "semantic_version": "1.0",
            "required_header": "# SYNTHETIC OPERATING SYSTEM v1",
            "sha256": sha256(bundle / "Solana_Memecoin_Intraday_Alpha_Lab_Operating_System_v8_5.md"),
        },
        "research_blueprint": {
            "current_filename": "research.md",
            "semantic_version": "1.0",
            "required_header_contains": "Synthetic Blueprint v1",
            "sha256": sha256(bundle / "research.md"),
        },
        "roadmap": {
            "current_filename": "roadmap.md",
            "semantic_version": "1.0",
            "required_header_contains": "Synthetic Roadmap v1",
            "sha256": sha256(bundle / "roadmap.md"),
        },
        "current_system_state": {
            "current_filename": "state.md",
            "semantic_version": "1.0",
            "required_header_contains": "Synthetic State v1",
            "sha256": sha256(bundle / "state.md"),
        },
        "phase_archive": {
            "current_filename": "archive.md",
            "semantic_version": "1.0",
            "required_header_contains": "Synthetic Archive v1",
            "sha256": sha256(bundle / "archive.md"),
        },
        "active_task": {
            "task_id": "TASK-SYNTHETIC",
            "current_filename": "task.md",
            "semantic_version": "1.0",
            "required_header": "# TASK-SYNTHETIC — Test task",
            "sha256": sha256(bundle / "task.md"),
        },
    }
    manifest_path = bundle / "canonical_manifest.yaml"
    write_yaml(
        manifest_path,
        {
            "schema": "solana_alpha_lab.canonical_manifest",
            "schema_version": "1.0",
            "canonical": canonical,
        },
    )

    receipt_path = root / "docs/evidence/test/activation.json"
    write_yaml(
        root / "docs/project_sources/release_registry_v1.yaml",
        {
            "schema": "smial.project_sources.release_registry",
            "active_ui_release_id": release_id,
            "active_ui_state": "REGISTRY_ACTIVATION_CONFIRMED",
            "releases": [
                {
                    "release_id": release_id,
                    "status": "ACTIVATED_BY_OWNER_SMOKE",
                    "bundle_path": f"docs/project_sources/releases/{release_id}",
                    "activation_receipt": "docs/evidence/test/activation.json",
                    "artifact_bindings": {
                        "canonical_manifest": {
                            "path": f"docs/project_sources/releases/{release_id}/canonical_manifest.yaml",
                            "sha256": sha256(manifest_path),
                        }
                    },
                }
            ],
        },
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(
            {
                "schema": "smial.project_sources.activation.receipt",
                "release_id": release_id,
                "activation_evidence": {
                    "class": "OWNER_ATTESTATION",
                    "smoke_outcome": "PASS",
                },
                "manifest_binding": {
                    "path": f"docs/project_sources/releases/{release_id}/canonical_manifest.yaml",
                    "sha256": sha256(manifest_path),
                },
            }
        ),
        encoding="utf-8",
    )
    mirror = root / "synthetic-mirror"
    shutil.copytree(bundle, mirror)
    return bundle, mirror


class Task34aDocumentationFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.synthetic_root = Path(self.tempdir.name) / "repository"
        self.synthetic_bundle, self.matching_mirror = build_synthetic_active_release(
            self.synthetic_root
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_policy_is_schema_valid_and_freezes_the_four_mirror_states(self) -> None:
        """Catches an unsafe or underspecified mirror-state policy."""
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertFalse(list(Draft202012Validator(schema).iter_errors(policy)))
        self.assertEqual(policy["authority"]["provider_api_rpc_wss_calls"], False)
        self.assertEqual(policy["mirror_states"], EXPECTED_MIRROR_STATES)

    def test_fixture_binds_the_activated_release_without_a_local_path(self) -> None:
        """Catches a fixture that leaks a user directory or unbinds the release."""
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(fixture["active_release_id"], "PSR-0003-T28-RC001-FREEZE")
        self.assertNotIn("C:\\Users", json.dumps(fixture, ensure_ascii=False))
        self.assertEqual(fixture["expected_mirror_states"], EXPECTED_MIRROR_STATES)

    def test_matching_mirror_is_classified_without_exposing_its_path(self) -> None:
        """Catches a context card that treats local diagnostics as truth or leaks paths."""
        result = evaluate_context(self.synthetic_root, self.matching_mirror)

        self.assertEqual(result["mirror_state"], "MIRROR_MATCHES_ACTIVE_RELEASE")
        self.assertTrue(result["task_selection_allowed"])
        self.assertNotIn(str(self.matching_mirror), json.dumps(result))
        self.assertNotIn(str(self.matching_mirror), render_context_text(result))

    def test_stale_and_missing_mirrors_preserve_the_activated_release(self) -> None:
        """Catches an ordinary stale mirror incorrectly blocking a proven activation."""
        stale_mirror = self.synthetic_root / "stale-mirror"
        shutil.copytree(self.matching_mirror, stale_mirror)
        (stale_mirror / "roadmap.md").write_text("Synthetic Roadmap v0\n", encoding="utf-8")

        stale = evaluate_context(self.synthetic_root, stale_mirror)
        absent = evaluate_context(self.synthetic_root, None)

        self.assertEqual(stale["mirror_state"], "STALE_MIRROR_ACTIVE_RELEASE_CONFIRMED")
        self.assertEqual(absent["mirror_state"], "MIRROR_UNAVAILABLE")
        self.assertEqual(stale["active_release_id"], "PSR-TEST-ACTIVE")
        self.assertTrue(stale["task_selection_allowed"])
        self.assertTrue(absent["task_selection_allowed"])

    def test_duplicate_role_requires_control_review(self) -> None:
        """Catches ambiguity rather than selecting a convenient duplicate mirror file."""
        shutil.copy2(
            self.matching_mirror / "roadmap.md",
            self.matching_mirror / "duplicate-roadmap.md",
        )

        result = evaluate_context(self.synthetic_root, self.matching_mirror)

        self.assertEqual(result["mirror_state"], "MIRROR_CONFLICT_REQUIRES_CONTROL_REVIEW")
        self.assertFalse(result["task_selection_allowed"])

    def test_header_mismatch_is_stale_not_a_false_match(self) -> None:
        """Catches filename-only source selection after a semantic header changed."""
        (self.matching_mirror / "task.md").write_text(
            "# TASK-SYNTHETIC — Changed header\n", encoding="utf-8"
        )

        result = evaluate_context(self.synthetic_root, self.matching_mirror)

        self.assertEqual(result["mirror_state"], "STALE_MIRROR_ACTIVE_RELEASE_CONFIRMED")
        self.assertEqual(result["mirror_role_status"]["active_task"], "STALE_OR_MISSING")

    def test_registry_or_receipt_contradiction_fails_closed(self) -> None:
        """Catches a false active registry pointer before any task can be selected."""
        receipt_path = self.synthetic_root / "docs/evidence/test/activation.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["activation_evidence"]["smoke_outcome"] = "FAIL"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

        with self.assertRaisesRegex(ContextBindingError, "ACTIVATION_RECEIPT"):
            evaluate_context(self.synthetic_root, None)

    def test_cli_exposes_the_current_context_without_user_paths(self) -> None:
        """Catches a runbook command that is absent, unsafe, or not machine-readable."""
        result = subprocess.run(
            [sys.executable, "-B", str(CONTEXT_SCRIPT_PATH), "--format", "json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        context = json.loads(result.stdout)
        self.assertEqual(context["active_release_id"], "PSR-0003-T28-RC001-FREEZE")
        self.assertEqual(context["mirror_state"], "MIRROR_UNAVAILABLE")
        self.assertNotIn("C:\\Users", result.stdout)

    def test_generated_navigation_is_current_and_has_no_absolute_user_path(self) -> None:
        """Catches a stale operator card or accidental local path in a generated view."""
        expected = render_operator_navigation(ROOT, load_and_validate())

        self.assertEqual(OPERATOR_NAVIGATION_PATH.read_bytes(), expected)
        self.assertNotIn(b"C:\\Users\\", expected)
        self.assertIn(b"PSR-0003-T28-RC001-FREEZE", expected)
        self.assertIn(b"show_task34a_context.py", expected)

    def test_runbooks_link_to_context_command_and_external_stop(self) -> None:
        """Catches prose-only procedures that bypass the deterministic context card."""
        for path in RUNBOOK_PATHS:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("show_task34a_context.py", text)
        self.assertIn(
            "Do not make a provider call",
            RUNBOOK_PATHS[-1].read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
