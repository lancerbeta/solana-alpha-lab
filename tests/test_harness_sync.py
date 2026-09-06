from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from harness_sync import (  # noqa: E402
    HarnessSyncError,
    _rewrite_block,
    check_drift,
)


def _run(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)


def _init_repo(worktree: Path) -> None:
    worktree.mkdir(parents=True, exist_ok=True)
    assert _run(["git", "init", "-b", "main"], cwd=worktree).returncode == 0
    _run(["git", "-C", str(worktree), "config", "user.email", "sync@test"], cwd=worktree)
    _run(["git", "-C", str(worktree), "config", "user.name", "sync"], cwd=worktree)


def _commit_all(worktree: Path, message: str) -> None:
    _run(["git", "-C", str(worktree), "add", "-A"], cwd=worktree)
    result = _run(["git", "-C", str(worktree), "commit", "-m", message], cwd=worktree)
    assert result.returncode == 0, result.stderr


class RewriteBlockTests(unittest.TestCase):
    def test_inline_field_rewritten(self) -> None:
        text = (
            "- asset_id: A-1\n"
            "  purpose: x\n"
            "  integrity: {kind: sha256, sha256: " + "0" * 64 + "}\n"
        )
        out = _rewrite_block(text, "A-1", "a" * 64)
        self.assertIn("sha256: " + "a" * 64 + "}", out)

    def test_block_field_rewritten(self) -> None:
        text = (
            "- asset_id: A-1\n"
            "  integrity:\n"
            "    kind: sha256\n"
            "    sha256: " + "0" * 64 + "\n"
        )
        out = _rewrite_block(text, "A-1", "a" * 64)
        self.assertIn("sha256: " + "a" * 64, out)

    def test_ambiguous_block_fails_closed(self) -> None:
        text = (
            "- asset_id: A-1\n"
            "  integrity: {kind: sha256, sha256: " + "0" * 64 + "}\n"
            "- asset_id: A-1\n"
            "  integrity: {kind: sha256, sha256: " + "0" * 64 + "}\n"
        )
        with self.assertRaisesRegex(HarnessSyncError, "ASSET_BLOCK_NOT_UNIQUE:A-1"):
            _rewrite_block(text, "A-1", "a" * 64)

    def test_missing_block_raises(self) -> None:
        with self.assertRaisesRegex(HarnessSyncError, "ASSET_BLOCK_NOT_UNIQUE:NOPE"):
            _rewrite_block("", "NOPE", "a" * 64)


class CanonicalHashTests(unittest.TestCase):
    def test_lf_canonization_matches_guard_policy(self) -> None:
        # The guard's worktree candidate conversion accepts identity or CRLF->LF;
        # the canonical bytes it hashes therefore always end with LF line endings.
        raw = b"line1\r\nline2\r\n"
        self.assertEqual(raw.replace(b"\r\n", b"\n"), b"line1\nline2\n")


class SyncGoldenTests(unittest.TestCase):
    """End-to-end sync against a minimal seeded catalog copy."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.worktree = Path(self._tmp.name) / "repo"
        self.addCleanup(self._tmp.cleanup)
        self._build_fixture()

    def _build_fixture(self) -> None:
        wt = self.worktree
        _init_repo(wt)
        for relative in [
            "scripts/validate_catalog.py",
            "scripts/generate_navigation.py",
            "scripts/harness_sync.py",
            "scripts/validate_baseline.py",
        ]:
            (wt / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, wt / relative)
        # The navigation generator imports a domain module; copy its minimal
        # import surface so the fixture can render projections.
        (wt / "src/solana_alpha_lab").mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            ROOT / "src/solana_alpha_lab/task34a_documentation_foundation.py",
            wt / "src/solana_alpha_lab/task34a_documentation_foundation.py",
        )
        shutil.copy2(
            ROOT / "src/solana_alpha_lab/catalog_discovery.py",
            wt / "src/solana_alpha_lab/catalog_discovery.py",
        )
        (wt / "src/solana_alpha_lab/__init__.py").write_text("", encoding="utf-8")
        sources_dir = wt / "docs/project_sources"
        sources_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            ROOT / "docs/project_sources/release_registry_v1.yaml",
            sources_dir / "release_registry_v1.yaml",
        )
        release_registry = yaml.safe_load(
            (sources_dir / "release_registry_v1.yaml").read_text(encoding="utf-8")
        )
        # Build a self-consistent minimal active release so the navigation
        # generator can render without the real Project Sources tree.
        manifest_relative = "docs/project_sources/releases/FIXTURE/canonical_manifest.yaml"
        receipt_relative = (
            "docs/project_sources/releases/FIXTURE/activation_receipt.json"
        )
        active_release = {
            "release_id": "PSR-FIXTURE-001",
            "task_id": "TASK-99",
            "status": "ACTIVATED_BY_OWNER_SMOKE",
            "bundle_path": "docs/project_sources/releases/FIXTURE",
            "activation_receipt": receipt_relative,
            "source_set": {"expected_source_count": 1, "mutable_roles": ["canonical_manifest"], "immutable_roles": {}},
            "artifact_bindings": {
                "canonical_manifest": {
                    "path": manifest_relative,
                    "sha256": "PENDING",
                }
            },
        }
        release_registry["active_ui_release_id"] = "PSR-FIXTURE-001"
        release_registry["active_ui_state"] = "REGISTRY_ACTIVATION_CONFIRMED"
        release_registry["releases"] = [active_release]
        bundle = sources_dir / "releases" / "FIXTURE"
        bundle.mkdir(parents=True, exist_ok=True)
        manifest_bytes = (
            b"schema: solana_alpha_lab.canonical_manifest\n"
            b"canonical:\n"
            b"  active_task:\n"
            b"    task_id: TASK-99\n"
            b"    current_filename: task.md\n"
            b"    required_header: '# TASK-99'\n"
            b"  canonical_manifest:\n"
            b"    current_filename: canonical_manifest.yaml\n"
            b"    required_header: 'schema: solana_alpha_lab.canonical_manifest'\n"
            b"  operating_system:\n"
            b"    current_filename: os.md\n"
            b"    required_header_contains: OS\n"
            b"  research_blueprint:\n"
            b"    current_filename: research.md\n"
            b"    required_header_contains: Research\n"
            b"  roadmap:\n"
            b"    current_filename: roadmap.md\n"
            b"    required_header_contains: Roadmap\n"
            b"  current_system_state:\n"
            b"    current_filename: state.md\n"
            b"    required_header_contains: State\n"
            b"  phase_archive:\n"
            b"    current_filename: archive.md\n"
            b"    required_header_contains: Archive\n"
        )
        (bundle / "canonical_manifest.yaml").write_bytes(manifest_bytes)
        for name, header in [
            ("os.md", "# OS"),
            ("research.md", "# Research"),
            ("roadmap.md", "# Roadmap"),
            ("state.md", "# State"),
            ("archive.md", "# Archive"),
            ("task.md", "# TASK-99"),
        ]:
            (bundle / name).write_bytes(header.encode("utf-8") + b"\n")
        # Immutable role hashes are pinned inside the canonical manifest itself.
        manifest_text = (bundle / "canonical_manifest.yaml").read_text(encoding="utf-8")
        for name in ["os.md", "research.md", "roadmap.md", "state.md", "archive.md"]:
            key = {
                "os.md": "operating_system",
                "research.md": "research_blueprint",
                "roadmap.md": "roadmap",
                "state.md": "current_system_state",
                "archive.md": "phase_archive",
            }[name]
            digest = hashlib.sha256((bundle / name).read_bytes()).hexdigest()
            manifest_text = manifest_text.replace(
                f"    current_filename: {name}\n",
                f"    current_filename: {name}\n    sha256: {digest}\n",
            )
        task_digest = hashlib.sha256((bundle / "task.md").read_bytes()).hexdigest()
        manifest_text = manifest_text.replace(
            "    task_id: TASK-99\n",
            f"    task_id: TASK-99\n    sha256: {task_digest}\n",
        )
        (bundle / "canonical_manifest.yaml").write_bytes(manifest_text.encode("utf-8"))
        manifest_binding = {
            "path": manifest_relative,
            "sha256": hashlib.sha256(
                (bundle / "canonical_manifest.yaml").read_bytes()
            ).hexdigest(),
        }
        active_release["artifact_bindings"]["canonical_manifest"] = manifest_binding
        (sources_dir / "release_registry_v1.yaml").write_text(
            yaml.safe_dump(release_registry, sort_keys=False), encoding="utf-8"
        )
        (bundle / "activation_receipt.json").write_text(
            json.dumps(
                {
                    "schema": "smial.project_sources.activation.receipt",
                    "release_id": "PSR-FIXTURE-001",
                    "activation_evidence": {
                        "class": "OWNER_ATTESTATION",
                        "smoke_outcome": "PASS",
                    },
                    "manifest_binding": manifest_binding,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        for relative in [
            "catalog/schemas/catalog_manifest.schema.json",
            "catalog/schemas/asset_catalog.schema.json",
            "catalog/schemas/query_recipe.schema.json",
            "catalog/schemas/lifecycle_registry.schema.json",
        ]:
            (wt / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, wt / relative)
        # The canonical reader requires this repository's EOL policy attributes.
        (wt / ".gitattributes").write_bytes(
            (ROOT / ".gitattributes").read_bytes()
        )

        target = wt / "docs/generated_target.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"alpha\nbeta\n")

        real_manifest = yaml.safe_load(
            (ROOT / "catalog/catalog_manifest.yaml").read_text(encoding="utf-8")
        )
        commands = real_manifest["root_resolver"]["commands"]
        legacy_commands = {
            key: commands[key]
            for key in (
                "validate",
                "resolve_asset",
                "resolve_query",
                "generate_navigation",
                "check_generated_navigation",
            )
        }
        fixture_manifest = {
            "schema_version": "1.0",
            "catalog_id": real_manifest["catalog_id"],
            "catalog_version": "0.1.0",
            "as_of": "2026-08-22",
            "implementation_status": real_manifest["implementation_status"],
            "current_checkpoint": {
                "assets": 10,
                "asset_registries": 1,
                "schemas": 4,
                "queries": 1,
                "lifecycle_registries": 9,
                "lifecycle_records": 84,
            },
            "root_resolver": {
                "asset_registries": ["catalog/assets/core.yaml"],
                "query_registries": real_manifest["root_resolver"]["query_registries"],
                "lifecycle_registries": real_manifest["root_resolver"][
                    "lifecycle_registries"
                ],
                "schemas": list(real_manifest["root_resolver"]["schemas"])[:4],
                "commands": legacy_commands,
            },
            "policies": real_manifest["policies"],
            "mandatory_asset_ids": ["CATALOG-ASSET-REGISTRY-CORE-001"],
            "deferred_capabilities": real_manifest["deferred_capabilities"],
        }
        (wt / "catalog/catalog_manifest.yaml").write_text(
            yaml.safe_dump(fixture_manifest, sort_keys=False), encoding="utf-8"
        )
        (wt / "catalog/query_recipes.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema_version": "1.0",
                    "registry_id": "CATALOG-QUERY-REGISTRY-001",
                    "as_of": "2026-08-22",
                    "recipes": [
                        {
                            "recipe_id": "QUERY-FIXTURE-CHECK-001",
                            "record_version": "1.0",
                            "purpose": "Fixture recipe validating the fixture catalog.",
                            "kind": "local_command",
                            "read_only": True,
                            "bounded": True,
                            "network_required": False,
                            "write_effects": "NONE",
                            "timeout_seconds": 60,
                            "command": [
                                sys.executable,
                                "-B",
                                "scripts/validate_catalog.py",
                            ],
                            "parameters": [],
                            "target_asset_ids": ["TEST-TARGET-001"],
                            "output_contract": {"format": "text", "max_records": 100},
                        }
                    ],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        registries_dir = wt / "registries"
        registries_dir.mkdir(exist_ok=True)
        for name in [
            "research_cycles.yaml",
            "hypotheses.yaml",
            "global_trial_ledger.yaml",
            "feature_catalog.yaml",
            "holdout_consumption.yaml",
            "strategies.yaml",
            "bot_instances.yaml",
            "reuse_candidates.yaml",
            "decisions_negative_results.yaml",
        ]:
            registry_data = yaml.safe_load(
                (ROOT / "registries" / name).read_text(encoding="utf-8")
            )
            # The fixture needs only the registry skeleton, not the historical
            # record graph that references catalog assets we did not copy.
            registry_data["source_asset_ids"] = []
            registry_data["records"] = []
            body = yaml.safe_dump(registry_data, sort_keys=False)
            (registries_dir / name).write_text(body, encoding="utf-8")
        # The fixture manifest lists no asset registry for lifecycle records;
        # lifecycle validation only runs over registered asset registries, so
        # no lifecycle shard file is needed in the fixture.

        stale_sha = "f" * 64
        core = (
            "schema_version: '1.1'\n"
            "registry_id: CATALOG-ASSET-REGISTRY-CORE-001\n"
            "as_of: '2026-08-22'\n"
            "records:\n"
            "- asset_id: CATALOG-ASSET-REGISTRY-CORE-001\n"
            "  record_version: '1.0'\n"
            "  asset_type: catalog_registry\n"
            "  purpose: fixture core registry self-registration\n"
            "  status: IMPLEMENTED_UNVERIFIED\n"
            "  origin: REPOSITORY\n"
            "  as_of: '2026-08-22'\n"
            "  truth_owner: TASK-99\n"
            "  location:\n"
            "    kind: git_path\n"
            "    logical_uri: repo://catalog/assets/core.yaml\n"
            "    repository_path: catalog/assets/core.yaml\n"
            "  integrity:\n"
            "    kind: catalog_commit\n"
            "    note: fixture registry self-registration\n"
            "  access:\n"
            "    mode: read_only\n"
            "    method: file\n"
            "    network_required: false\n"
            "    secrets_required: false\n"
            "  relations: []\n"
            "  consumers: [TASK-99]\n"
            "  evidence: []\n"
            "  classification:\n"
            "    contains_secrets: false\n"
            "    contains_raw_data: false\n"
            "    sensitivity: INTERNAL_NON_SECRET\n"
            "- asset_id: CATALOG-ASSET-REGISTRY-LIFECYCLE-001\n"
            "  record_version: '1.0'\n"
            "  asset_type: catalog_registry\n"
            "  purpose: fixture lifecycle shard registration\n"
            "  status: IMPLEMENTED_UNVERIFIED\n"
            "  origin: REPOSITORY\n"
            "  as_of: '2026-08-22'\n"
            "  truth_owner: TASK-99\n"
            "  location:\n"
            "    kind: git_path\n"
            "    logical_uri: repo://catalog/assets/lifecycle.yaml\n"
            "    repository_path: catalog/assets/lifecycle.yaml\n"
            "  integrity:\n"
            "    kind: catalog_commit\n"
            "    note: fixture registry self-registration\n"
            "  access:\n"
            "    mode: read_only\n"
            "    method: file\n"
            "    network_required: false\n"
            "    secrets_required: false\n"
            "  relations: []\n"
            "  consumers: [TASK-99]\n"
            "  evidence: []\n"
            "  classification:\n"
            "    contains_secrets: false\n"
            "    contains_raw_data: false\n"
            "    sensitivity: INTERNAL_NON_SECRET\n"
            "- asset_id: TEST-TARGET-001\n"
            "  record_version: '1.0'\n"
            "  asset_type: evidence\n"
            "  purpose: golden fixture with stale inline sha " + stale_sha[:8] + "\n"
            "  status: IMPLEMENTED_UNVERIFIED\n"
            "  origin: REPOSITORY\n"
            "  as_of: '2026-08-22'\n"
            "  truth_owner: TASK-99\n"
            "  location:\n"
            "    kind: git_path\n"
            "    logical_uri: repo://docs/generated_target.txt\n"
            "    repository_path: docs/generated_target.txt\n"
            "  integrity:\n"
            "    kind: sha256\n"
            f"    sha256: {stale_sha}\n"
            "  access:\n"
            "    mode: read_only\n"
            "    method: file\n"
            "    network_required: false\n"
            "    secrets_required: false\n"
            "  relations: []\n"
            "  consumers: [TASK-99]\n"
            "  evidence: []\n"
            "  classification:\n"
            "    contains_secrets: false\n"
            "    contains_raw_data: false\n"
            "    sensitivity: INTERNAL_NON_SECRET\n"
        )
        # The catalog validator requires every expected lifecycle registry to be
        # registered as a lifecycle_registry asset. Emit one minimal record per
        # registry with the correct skeleton hash.
        lifecycle_records = []
        for name in [
            "research_cycles.yaml",
            "hypotheses.yaml",
            "global_trial_ledger.yaml",
            "feature_catalog.yaml",
            "holdout_consumption.yaml",
            "strategies.yaml",
            "bot_instances.yaml",
            "reuse_candidates.yaml",
            "decisions_negative_results.yaml",
        ]:
            asset_id = (
                "REGISTRY-"
                + name.replace(".yaml", "").replace("_", " ").title().replace(" ", "-").upper()
                + "-001"
            )
            actual = hashlib.sha256(
                (registries_dir / name).read_bytes()
            ).hexdigest()
            lifecycle_records.append(
                f"- asset_id: {asset_id}\n"
                "  record_version: '1.0'\n"
                "  asset_type: lifecycle_registry\n"
                f"  purpose: fixture registration for registries/{name}\n"
                "  status: VALIDATED_ACTIVE\n"
                "  origin: REPOSITORY\n"
                "  as_of: '2026-08-22'\n"
                "  truth_owner: TASK-99\n"
                "  location:\n"
                "    kind: git_path\n"
                f"    logical_uri: repo://registries/{name}\n"
                f"    repository_path: registries/{name}\n"
                "  integrity:\n"
                "    kind: sha256\n"
                f"    sha256: {actual}\n"
                "  access:\n"
                "    mode: read_only\n"
                "    method: file\n"
                "    network_required: false\n"
                "    secrets_required: false\n"
                "  relations: []\n"
                "  consumers: [TASK-99]\n"
                "  evidence: []\n"
                "  classification:\n"
                "    contains_secrets: false\n"
                "    contains_raw_data: false\n"
                "    sensitivity: INTERNAL_NON_SECRET\n"
            )
        core += "\n".join(lifecycle_records)
        (wt / "catalog/assets").mkdir(exist_ok=True)
        shutil.copy2(ROOT / "catalog/assets/lifecycle.yaml", wt / "catalog/assets/lifecycle.yaml")
        # CRLF bytes on purpose: the drift class that broke CI on 2026-08-21.
        (wt / "catalog/assets/core.yaml").write_bytes(
            core.encode("utf-8").replace(b"\n", b"\r\n")
        )
        _commit_all(wt, "fixture baseline")

    def test_apply_repairs_drift_and_is_idempotent(self) -> None:
        first = _run(
            [sys.executable, "-B", "scripts/harness_sync.py", "--apply"],
            cwd=self.worktree,
        )
        self.assertEqual(first.returncode, 0, first.stderr or first.stdout)
        payload = json.loads(first.stdout)
        self.assertEqual(payload["idempotency"], "PASS_SECOND_PASS_NOOP")

        registry_bytes = (self.worktree / "catalog/assets/core.yaml").read_bytes()
        expected = hashlib.sha256(
            (self.worktree / "docs/generated_target.txt").read_bytes()
        ).hexdigest()
        self.assertNotIn(b"\r\n", registry_bytes)
        self.assertIn(expected.encode(), registry_bytes)

    def test_check_passes_after_apply_and_flags_drift_before(self) -> None:
        pre = _run(
            [sys.executable, "-B", "scripts/harness_sync.py", "--check"],
            cwd=self.worktree,
        )
        self.assertEqual(pre.returncode, 1, pre.stdout)
        self.assertIn("DERIVED_HASH_DRIFT", pre.stderr)

        applied = _run(
            [sys.executable, "-B", "scripts/harness_sync.py", "--apply"],
            cwd=self.worktree,
        )
        self.assertEqual(applied.returncode, 0, applied.stderr)

        post = _run(
            [sys.executable, "-B", "scripts/harness_sync.py", "--check"],
            cwd=self.worktree,
        )
        self.assertEqual(post.returncode, 0, post.stderr)
        self.assertIn("HARNESS_SYNC_CHECK: PASS", post.stdout)

    def test_primary_file_mutation_is_never_written_by_sync(self) -> None:
        target = self.worktree / "docs/generated_target.txt"
        before = target.read_bytes()
        applied = _run(
            [sys.executable, "-B", "scripts/harness_sync.py", "--apply"],
            cwd=self.worktree,
        )
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual(before, target.read_bytes())

    def test_apply_twice_is_cross_invocation_noop(self) -> None:
        first = _run(
            [sys.executable, "-B", "scripts/harness_sync.py", "--apply"],
            cwd=self.worktree,
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        status_after_first = _run(["git", "status", "--porcelain"], cwd=self.worktree).stdout
        second = _run(
            [sys.executable, "-B", "scripts/harness_sync.py", "--apply"],
            cwd=self.worktree,
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        status_after_second = _run(["git", "status", "--porcelain"], cwd=self.worktree).stdout
        self.assertEqual(status_after_first, status_after_second)
        self.assertNotEqual(status_after_first.strip(), "")


class IncrementalSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.worktree = Path(self._tmp.name) / "repo"
        self.addCleanup(self._tmp.cleanup)
        SyncGoldenTests._build_fixture(self)
        first = _run(
            [sys.executable, "-B", "scripts/harness_sync.py", "--apply"],
            cwd=self.worktree,
        )
        self.assertEqual(first.returncode, 0, first.stderr or first.stdout)
        _commit_all(self.worktree, "synced fixture")
        self.base = _run(["git", "rev-parse", "HEAD"], cwd=self.worktree).stdout.strip()
        self.assertRegex(self.base, r"^[0-9a-f]{40}$")
        for index in range(8):
            dummy = self.worktree / f"docs/unrelated_{index}.txt"
            dummy.write_bytes(f"unrelated-{index}\n".encode("utf-8"))
            core = (self.worktree / "catalog/assets/core.yaml").read_text(encoding="utf-8")
            digest = hashlib.sha256(dummy.read_bytes()).hexdigest()
            core += (
                f"- asset_id: UNRELATED-{index:03d}\n"
                "  record_version: '1.0'\n"
                "  asset_type: evidence\n"
                "  purpose: unrelated filler for work-count contract\n"
                "  status: IMPLEMENTED_UNVERIFIED\n"
                "  origin: REPOSITORY\n"
                "  as_of: '2026-08-22'\n"
                "  truth_owner: TASK-99\n"
                "  location:\n"
                "    kind: git_path\n"
                f"    logical_uri: repo://docs/unrelated_{index}.txt\n"
                f"    repository_path: docs/unrelated_{index}.txt\n"
                "  integrity:\n"
                "    kind: sha256\n"
                f"    sha256: {digest}\n"
                "  access:\n"
                "    mode: read_only\n"
                "    method: file\n"
                "    network_required: false\n"
                "    secrets_required: false\n"
                "  relations: []\n"
                "  consumers: [TASK-99]\n"
                "  evidence: []\n"
                "  classification:\n"
                "    contains_secrets: false\n"
                "    contains_raw_data: false\n"
                "    sensitivity: INTERNAL_NON_SECRET\n"
            )
            (self.worktree / "catalog/assets/core.yaml").write_text(core, encoding="utf-8")
        filler = _run(
            [sys.executable, "-B", "scripts/harness_sync.py", "--apply"],
            cwd=self.worktree,
        )
        self.assertEqual(filler.returncode, 0, filler.stderr or filler.stdout)
        _commit_all(self.worktree, "unrelated filler assets")
        self.base = _run(["git", "rev-parse", "HEAD"], cwd=self.worktree).stdout.strip()

    def _apply_incremental(self) -> dict:
        result = _run(
            [
                sys.executable,
                "-B",
                "scripts/harness_sync.py",
                "--apply",
                "--base-ref",
                self.base,
            ],
            cwd=self.worktree,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def _apply_full(self) -> dict:
        result = _run(
            [sys.executable, "-B", "scripts/harness_sync.py", "--apply", "--full"],
            cwd=self.worktree,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def test_t1_one_registered_source_skips_navigation(self) -> None:
        target = self.worktree / "docs/generated_target.txt"
        target.write_bytes(b"alpha\nbeta\ngamma\n")
        payload = self._apply_incremental()
        self.assertEqual(payload["mode"], "incremental")
        self.assertFalse(payload["full_fallback"])
        self.assertEqual(payload["navigation_runs"], 0)
        self.assertEqual(payload["hashed_assets"], 1)
        self.assertLess(payload["hashed_assets"], payload["registered_sha_assets_total"])
        self.assertIn(
            hashlib.sha256(target.read_bytes()).hexdigest().encode(),
            (self.worktree / "catalog/assets/core.yaml").read_bytes(),
        )

    def test_t3_unregistered_file_is_noop(self) -> None:
        (self.worktree / "docs/scratch_unregistered.txt").write_bytes(b"scratch\n")
        before = (self.worktree / "catalog/assets/core.yaml").read_bytes()
        payload = self._apply_incremental()
        self.assertEqual(payload["mode"], "incremental")
        self.assertEqual(payload["hashed_assets"], 0)
        self.assertEqual(payload["navigation_runs"], 0)
        self.assertEqual(before, (self.worktree / "catalog/assets/core.yaml").read_bytes())

    def test_t4_semantic_registry_edit_requires_navigation(self) -> None:
        core = (self.worktree / "catalog/assets/core.yaml").read_text(encoding="utf-8")
        core = core.replace(
            "purpose: golden fixture with stale inline sha",
            "purpose: golden fixture purpose changed",
            1,
        )
        (self.worktree / "catalog/assets/core.yaml").write_text(core, encoding="utf-8")
        payload = self._apply_incremental()
        self.assertTrue(payload["impact_plan"]["navigation_required"])
        self.assertGreaterEqual(payload["navigation_runs"], 1)

    def test_t5_nav_output_drift_forces_navigation(self) -> None:
        project_map = self.worktree / "docs/PROJECT_MAP.md"
        if not project_map.is_file():
            self.skipTest("project map not generated in fixture")
        project_map.write_bytes(project_map.read_bytes() + b"\n")
        payload = self._apply_incremental()
        self.assertTrue(payload["impact_plan"]["navigation_required"])
        self.assertIn("NAV_OUTPUT_DRIFT", payload["impact_plan"]["navigation_reason"])

    def test_t10_staged_only_is_in_candidate_inventory(self) -> None:
        target = self.worktree / "docs/generated_target.txt"
        original = target.read_bytes()
        target.write_bytes(b"staged-only\n")
        _run(["git", "add", "docs/generated_target.txt"], cwd=self.worktree)
        target.write_bytes(original)
        from harness_sync import candidate_paths

        paths = candidate_paths(self.base, root=self.worktree)
        self.assertIn("docs/generated_target.txt", paths)

    def test_t5b_integrity_only_registry_skips_navigation(self) -> None:
        core = self.worktree / "catalog/assets/core.yaml"
        text = core.read_text(encoding="utf-8")
        # Flip one hex nibble in an existing sha256 pin without semantic edits.
        import re as _re

        match = _re.search(r"sha256: ([0-9a-f]{64})", text)
        self.assertIsNotNone(match)
        old = match.group(1)
        flipped = ("0" if old[0] != "0" else "1") + old[1:]
        core.write_text(text.replace(old, flipped, 1), encoding="utf-8")
        payload = self._apply_incremental()
        self.assertEqual(payload["mode"], "incremental")
        self.assertFalse(payload["full_fallback"])
        self.assertEqual(payload["navigation_runs"], 0)
        self.assertFalse(payload["impact_plan"]["navigation_required"])
        self.assertGreaterEqual(payload["hashed_assets"], 1)
        self.assertLess(payload["hashed_assets"], 50)

    def test_t6_generator_source_requires_navigation(self) -> None:
        generator = self.worktree / "scripts/generate_navigation.py"
        generator.write_bytes(generator.read_bytes() + b"\n")
        payload = self._apply_incremental()
        self.assertTrue(payload["impact_plan"]["navigation_required"])
        self.assertGreaterEqual(payload["navigation_runs"], 1)

    def test_t11_invalid_base_falls_back_full(self) -> None:
        result = _run(
            [
                sys.executable,
                "-B",
                "scripts/harness_sync.py",
                "--apply",
                "--base-ref",
                "0" * 40,
            ],
            cwd=self.worktree,
        )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("BASE_REF_UNRESOLVABLE", result.stderr)

    def test_t12_second_incremental_is_noop(self) -> None:
        (self.worktree / "docs/generated_target.txt").write_bytes(b"alpha\nbeta\ndelta\n")
        first = self._apply_incremental()
        self.assertEqual(first["mode"], "incremental")
        second = self._apply_incremental()
        self.assertEqual(second["mode"], "incremental")
        self.assertEqual(second["idempotency"], "PASS_IMPACTED_CLOSURE_NOOP")
        self.assertEqual(second["navigation_runs"], 0)

    def test_t13_full_flag_preserved(self) -> None:
        payload = self._apply_full()
        self.assertEqual(payload["mode"], "apply")
        self.assertGreaterEqual(payload["navigation_runs"], 3)

    def test_t14_incremental_matches_full_oracle_bytes(self) -> None:
        target = self.worktree / "docs/generated_target.txt"
        target.write_bytes(b"alpha\nbeta\noracle\n")
        incremental = self._apply_incremental()
        self.assertEqual(incremental["mode"], "incremental")
        derived = [
            "catalog/assets/core.yaml",
            "catalog/catalog_manifest.yaml",
            "docs/PROJECT_MAP.md",
            "catalog/generated/asset_edges.json",
            "docs/OPERATOR_NAVIGATION.md",
        ]
        after_incremental = {
            relative: (self.worktree / relative).read_bytes()
            for relative in derived
            if (self.worktree / relative).is_file()
        }
        _run(["git", "checkout", "--", "."], cwd=self.worktree)
        target.write_bytes(b"alpha\nbeta\noracle\n")
        full = self._apply_full()
        self.assertEqual(full["mode"], "apply")
        for relative, expected in after_incremental.items():
            self.assertEqual(
                expected,
                (self.worktree / relative).read_bytes(),
                relative,
            )

    def test_t16_staged_check_still_fail_closed(self) -> None:
        target = self.worktree / "docs/generated_target.txt"
        target.write_bytes(b"alpha\nbeta\nstaged\n")
        _run(["git", "add", "docs/generated_target.txt"], cwd=self.worktree)
        checked = _run(
            [
                sys.executable,
                "-B",
                "scripts/harness_sync.py",
                "--check",
                "--paths-from-staging",
            ],
            cwd=self.worktree,
        )
        self.assertEqual(checked.returncode, 1)
        self.assertIn("DERIVED_HASH_DRIFT", checked.stderr)

    def test_check_rejects_apply_flags(self) -> None:
        checked = _run(
            [
                sys.executable,
                "-B",
                "scripts/harness_sync.py",
                "--check",
                "--base-ref",
                self.base,
            ],
            cwd=self.worktree,
        )
        self.assertEqual(checked.returncode, 2)
        self.assertIn("CHECK_MODE_REJECTS_APPLY_FLAGS", checked.stderr)

    def test_t17_primary_source_not_overwritten(self) -> None:
        target = self.worktree / "docs/generated_target.txt"
        payload_bytes = b"alpha\nbeta\nkeep-primary\n"
        target.write_bytes(payload_bytes)
        self._apply_incremental()
        self.assertEqual(payload_bytes, target.read_bytes())


def _append_sha_record(worktree: Path, asset_id: str, relative: str, digest: str) -> None:
    core = worktree / "catalog/assets/core.yaml"
    core.write_text(
        core.read_text(encoding="utf-8")
        + (
            f"- asset_id: {asset_id}\n"
            "  record_version: '1.0'\n"
            "  asset_type: evidence\n"
            "  purpose: hash-scope fixture member\n"
            "  status: IMPLEMENTED_UNVERIFIED\n"
            "  origin: REPOSITORY\n"
            "  as_of: '2026-09-06'\n"
            "  truth_owner: TASK-99\n"
            "  location:\n"
            "    kind: git_path\n"
            f"    logical_uri: repo://{relative}\n"
            f"    repository_path: {relative}\n"
            "  integrity:\n"
            "    kind: sha256\n"
            f"    sha256: {digest}\n"
            "  access:\n"
            "    mode: read_only\n"
            "    method: file\n"
            "    network_required: false\n"
            "    secrets_required: false\n"
            "  relations: []\n"
            "  consumers: [TASK-99]\n"
            "  evidence: []\n"
            "  classification:\n"
            "    contains_secrets: false\n"
            "    contains_raw_data: false\n"
            "    sensitivity: INTERNAL_NON_SECRET\n"
        ),
        encoding="utf-8",
    )


NAV_OUTPUTS = (
    "docs/PROJECT_MAP.md",
    "catalog/generated/asset_edges.json",
    "docs/OPERATOR_NAVIGATION.md",
)


def _run_with_spy(
    args: list[str], *, cwd: Path, spy: Path
) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "HARNESS_SYNC_SHA256_SPY": str(spy),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, env=env)


def _cataloged_nav_paths(worktree: Path) -> set[str]:
    found: set[str] = set()
    for relative in (
        "catalog/assets/core.yaml",
        "catalog/assets/lifecycle.yaml",
        "catalog/assets/architecture.yaml",
        "catalog/assets/pre_git.yaml",
    ):
        path = worktree / relative
        if not path.is_file():
            continue
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            continue
        for record in document.get("records") or []:
            if not isinstance(record, dict):
                continue
            location = record.get("location") or {}
            repo_path = location.get("repository_path")
            if isinstance(repo_path, str) and repo_path.replace("\\", "/") in NAV_OUTPUTS:
                found.add(repo_path.replace("\\", "/"))
    return found


def _unique_spy_paths(spy: Path) -> set[str]:
    if not spy.is_file():
        return set()
    return {
        line.strip().replace("\\", "/")
        for line in spy.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


class HashScopeThroughputTests(unittest.TestCase):
    MEMBER_COUNT = 200

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.worktree = Path(self._tmp.name) / "repo"
        self.addCleanup(self._tmp.cleanup)
        SyncGoldenTests._build_fixture(self)
        first = _run(
            [sys.executable, "-B", "scripts/harness_sync.py", "--apply"],
            cwd=self.worktree,
        )
        self.assertEqual(first.returncode, 0, first.stderr or first.stdout)
        _commit_all(self.worktree, "synced fixture")
        seed = _run(["git", "rev-parse", "HEAD"], cwd=self.worktree).stdout.strip()
        for index in range(self.MEMBER_COUNT):
            relative = f"docs/hash_scope_{index:03d}.txt"
            path = self.worktree / relative
            path.write_bytes(f"member-{index}\n".encode("utf-8"))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            _append_sha_record(self.worktree, f"HASH-SCOPE-{index:03d}", relative, digest)
        filler = _run(
            [
                sys.executable,
                "-B",
                "scripts/harness_sync.py",
                "--apply",
                "--base-ref",
                seed,
            ],
            cwd=self.worktree,
        )
        self.assertEqual(filler.returncode, 0, filler.stderr or filler.stdout)
        _commit_all(self.worktree, "hash-scope baseline")
        self.base = _run(["git", "rev-parse", "HEAD"], cwd=self.worktree).stdout.strip()

    def _assert_hash_scope(
        self,
        spy: Path,
        *,
        affected: set[str],
        nav: bool,
        stderr: str,
        impact_class: str,
    ) -> None:
        expected = set(affected)
        if nav:
            expected.update(_cataloged_nav_paths(self.worktree))
        unique = _unique_spy_paths(spy)
        self.assertEqual(unique, expected)
        self.assertLessEqual(len(unique), 8)
        self.assertNotIn("docs/hash_scope_001.txt", unique)
        plan_line = next(
            (line for line in stderr.splitlines() if line.startswith("HARNESS_SYNC_PLAN:")),
            "",
        )
        self.assertTrue(plan_line, stderr)
        self.assertIn(f"class={impact_class}", plan_line)
        self.assertIn(f"hashed={len(expected)}", plan_line)

    def test_record_add_new_file_does_not_hash_neighbors(self) -> None:
        relative = "docs/hash_scope_new.txt"
        path = self.worktree / relative
        path.write_bytes(b"brand-new\n")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        stale = "ab" * 32
        _append_sha_record(self.worktree, "HASH-SCOPE-NEW", relative, stale)
        spy = self.worktree / "sha256.spy"
        result = _run_with_spy(
            [
                sys.executable,
                "-B",
                "scripts/harness_sync.py",
                "--apply",
                "--base-ref",
                self.base,
            ],
            cwd=self.worktree,
            spy=spy,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertNotIn("HARNESS_SYNC_PLAN_REQUIRED_BEFORE_HASH", result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["mode"], "incremental")
        self.assertFalse(payload["full_fallback"])
        self._assert_hash_scope(
            spy,
            affected={relative},
            nav=True,
            stderr=result.stderr,
            impact_class="RECORD_ADD_OR_MOVE",
        )
        self.assertEqual(payload["hashed_unique_paths"], len(_unique_spy_paths(spy)))
        core = (self.worktree / "catalog/assets/core.yaml").read_text(encoding="utf-8")
        self.assertIn(digest, core)
        self.assertNotIn(stale, core)
        plan_ids = payload["impact_plan"]["direct_sha_assets"]
        self.assertIn("HASH-SCOPE-NEW", plan_ids)
        self.assertNotIn("HASH-SCOPE-000", plan_ids)

    def test_record_add_existing_path_does_not_hash_neighbors(self) -> None:
        relative = "docs/hash_scope_000.txt"
        digest = hashlib.sha256((self.worktree / relative).read_bytes()).hexdigest()
        stale = "ef" * 32
        _append_sha_record(self.worktree, "HASH-SCOPE-DUP", relative, stale)
        spy = self.worktree / "sha256.spy"
        result = _run_with_spy(
            [
                sys.executable,
                "-B",
                "scripts/harness_sync.py",
                "--apply",
                "--base-ref",
                self.base,
            ],
            cwd=self.worktree,
            spy=spy,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self._assert_hash_scope(
            spy,
            affected={relative},
            nav=True,
            stderr=result.stderr,
            impact_class="RECORD_ADD_OR_MOVE",
        )
        core = (self.worktree / "catalog/assets/core.yaml").read_text(encoding="utf-8")
        self.assertEqual(core.count(digest), 2)
        self.assertNotIn(stale, core)
        self.assertIn("HASH-SCOPE-DUP", payload["impact_plan"]["direct_sha_assets"])
        self.assertNotIn("HASH-SCOPE-001", payload["impact_plan"]["direct_sha_assets"])

    def test_staged_registry_check_does_not_hash_neighbors(self) -> None:
        relative = "docs/hash_scope_staged.txt"
        path = self.worktree / relative
        path.write_bytes(b"staged-new\n")
        stale = "cd" * 32
        _append_sha_record(self.worktree, "HASH-SCOPE-STAGED", relative, stale)
        _run(["git", "add", "catalog/assets/core.yaml"], cwd=self.worktree)
        spy = self.worktree / "sha256.spy"
        checked = _run_with_spy(
            [
                sys.executable,
                "-B",
                "scripts/harness_sync.py",
                "--check",
                "--paths-from-staging",
            ],
            cwd=self.worktree,
            spy=spy,
        )
        self.assertEqual(checked.returncode, 1, checked.stderr)
        self.assertIn("class=RECORD_ADD_OR_MOVE", checked.stderr)
        self.assertIn("sha256_mismatch:HASH-SCOPE-STAGED", checked.stderr)
        self.assertNotIn("sha256_mismatch:HASH-SCOPE-000", checked.stderr)
        self._assert_hash_scope(
            spy,
            affected={relative},
            nav=True,
            stderr=checked.stderr,
            impact_class="RECORD_ADD_OR_MOVE",
        )

    def test_staged_registry_check_classifies_index_not_worktree(self) -> None:
        relative = "docs/hash_scope_index.txt"
        path = self.worktree / relative
        path.write_bytes(b"index-only\n")
        stale = "a1" * 32
        _append_sha_record(self.worktree, "HASH-SCOPE-INDEX", relative, stale)
        _run(["git", "add", "catalog/assets/core.yaml"], cwd=self.worktree)
        head_core = subprocess.run(
            ["git", "show", "HEAD:catalog/assets/core.yaml"],
            cwd=str(self.worktree),
            capture_output=True,
            check=False,
        )
        self.assertEqual(head_core.returncode, 0, head_core.stderr)
        (self.worktree / "catalog/assets/core.yaml").write_bytes(head_core.stdout)
        index_core = subprocess.run(
            ["git", "ls-files", "-s", "--", "catalog/assets/core.yaml"],
            cwd=str(self.worktree),
            capture_output=True,
            check=False,
        )
        self.assertEqual(index_core.returncode, 0, index_core.stderr)
        index_oid = index_core.stdout.decode("ascii", errors="replace").split()[1]
        index_blob = subprocess.run(
            ["git", "cat-file", "blob", index_oid],
            cwd=str(self.worktree),
            capture_output=True,
            check=False,
        )
        self.assertIn(b"HASH-SCOPE-INDEX", index_blob.stdout)
        worktree_core = (self.worktree / "catalog/assets/core.yaml").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("HASH-SCOPE-INDEX", worktree_core)
        spy = self.worktree / "sha256.spy"
        checked = _run_with_spy(
            [
                sys.executable,
                "-B",
                "scripts/harness_sync.py",
                "--check",
                "--paths-from-staging",
            ],
            cwd=self.worktree,
            spy=spy,
        )
        self.assertEqual(checked.returncode, 1, checked.stderr)
        self.assertIn("sha256_mismatch:HASH-SCOPE-INDEX", checked.stderr)
        self.assertIn(
            "class=RECORD_ADD_OR_MOVE",
            checked.stderr,
            checked.stderr,
        )
        self._assert_hash_scope(
            spy,
            affected={relative},
            nav=True,
            stderr=checked.stderr,
            impact_class="RECORD_ADD_OR_MOVE",
        )

    def test_purpose_only_does_not_hash_registry(self) -> None:
        core = self.worktree / "catalog/assets/core.yaml"
        text = core.read_text(encoding="utf-8")
        core.write_text(
            text.replace(
                "purpose: hash-scope fixture member",
                "purpose: hash-scope fixture member retitled",
                1,
            ),
            encoding="utf-8",
        )
        spy = self.worktree / "sha256.spy"
        result = _run_with_spy(
            [
                sys.executable,
                "-B",
                "scripts/harness_sync.py",
                "--apply",
                "--base-ref",
                self.base,
            ],
            cwd=self.worktree,
            spy=spy,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self._assert_hash_scope(
            spy,
            affected=set(),
            nav=True,
            stderr=result.stderr,
            impact_class="SEMANTIC_NAV",
        )
        self.assertNotIn("HASH-SCOPE-000", payload["impact_plan"]["direct_sha_assets"])


if __name__ == "__main__":
    unittest.main()
