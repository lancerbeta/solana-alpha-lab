from __future__ import annotations

import importlib.util
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/delivery_harness.py"
REPOSITORY = "example/project"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("delivery_harness_bootstrap", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("delivery harness script is not loadable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def initialize_repository(
    target: Path,
    repository: str = REPOSITORY,
    default_branch: str = "main",
) -> None:
    subprocess.run(
        ["git", "init", "--initial-branch", default_branch],
        cwd=target,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", f"https://github.com/{repository}.git"],
        cwd=target, check=True, capture_output=True,
    )
    subprocess.run(
        [
            "git", "symbolic-ref", "refs/remotes/origin/HEAD",
            f"refs/remotes/origin/{default_branch}",
        ],
        cwd=target, check=True, capture_output=True,
    )


class DeliveryHarnessBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_preview_is_zero_write_and_apply_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            initialize_repository(target)
            before = list(target.rglob("*"))
            plan = self.module.plan_initialization(
                target, ROOT, repository=REPOSITORY
            )
            self.assertEqual(list(target.rglob("*")), before)
            self.assertEqual(plan["decision"], "APPLY_ALLOWED")
            self.assertTrue(plan["plan_sha256"])
            self.assertTrue(plan["creates"])
            receipt = self.module.apply_initialization(target, plan)
            self.assertEqual(receipt["decision"], "APPLIED")
            self.assertEqual(receipt["plan_sha256"], plan["plan_sha256"])
            second = self.module.plan_initialization(
                target, ROOT, repository=REPOSITORY
            )
            self.assertTrue(second["idempotent"])
            self.assertEqual(second["creates"], [])
            self.assertEqual(second["replaces"], [])
            self.assertEqual(second["removes"], [])
            check = self.module.check_harness(target)
            self.assertEqual(check["status"], "PASS", check)
            self.assertFalse(check["delivery_gate_ready"])

    def test_profile_is_consumed_and_missing_profile_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            initialize_repository(target)
            with self.assertRaisesRegex(ValueError, "PORTABLE_PROFILE_NOT_FOUND"):
                self.module.plan_initialization(
                    target, ROOT, repository=REPOSITORY,
                    profile_path="delivery-harness/templates/missing.yaml"
                )

    def test_installed_portable_cli_runs_check_and_exact_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            initialize_repository(target)
            subprocess.run(["git", "config", "user.name", "Harness Test"], cwd=target, check=True)
            subprocess.run(["git", "config", "user.email", "harness@example.invalid"], cwd=target, check=True)
            marker = target / "README.md"
            marker.write_text("portable target\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=target, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=target, check=True, capture_output=True)
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=target, check=True,
                capture_output=True, text=True,
            ).stdout.strip()
            branch = subprocess.run(
                ["git", "branch", "--show-current"], cwd=target, check=True,
                capture_output=True, text=True,
            ).stdout.strip()

            plan = self.module.plan_initialization(
                target, ROOT, repository=REPOSITORY
            )
            self.module.apply_initialization(target, plan)
            evidence = target / "docs/evidence/portable_acceptance.json"
            evidence.parent.mkdir(parents=True)
            evidence.write_text("{}\n", encoding="utf-8")
            task = target / "docs/tasks/PORTABLE-TEST.md"
            task.parent.mkdir(parents=True)
            task_metadata = {
                "task_id": "PORTABLE-TEST",
                "task_version": "1.0",
                "status": "READY",
                "as_of": "2026-08-14",
                "owner": "GOAL_OWNER",
                "allowed_routes": ["DIRECT_CURSOR_DELIVERY", "DIRECT_CODEX_DELIVERY"],
                "expected_repository": "example/project",
                "git_binding": {
                    "expected_base": head,
                    "expected_upstream": "HEAD",
                    "expected_upstream_oid": head,
                    "expected_branch": branch,
                    "dirty_mode": "ALLOW_REPORTED",
                },
                "objective": "Prove the installed portable harness runs from exact Git task context.",
                "managed_write_set": ["docs/tasks/PORTABLE-TEST.md"],
                "external_caps": {
                    "network": False,
                    "credentials": False,
                    "external_system": False,
                    "signing_or_financial_action": False,
                    "cash_spend": False,
                    "deployment": False,
                },
                "stop_conditions": ["TASK_SCOPE_DRIFT"],
                "context_requirements": {
                    "catalog_asset_ids": [],
                    "l2_roles": ["DELIVERY_EVIDENCE"],
                    "l3_roles": [],
                    "roadmap_path": None,
                    "exact_role_paths": {
                        "LIFECYCLE": [],
                        "EXTERNAL_ROUTE_KNOWLEDGE": [],
                        "ARCHITECTURE_DECISIONS": [],
                        "DELIVERY_EVIDENCE": ["docs/evidence/portable_acceptance.json"],
                        "HISTORICAL_CONTEXT": [],
                    },
                },
            }
            task.write_text(
                "---\n"
                + json.dumps(task_metadata, ensure_ascii=False, sort_keys=True)
                + "\n---\n\n# Portable test\n",
                encoding="utf-8",
            )
            script = target / "scripts/delivery_harness.py"
            prefix = [sys.executable, "-S"]
            checked = subprocess.run(
                [*prefix, str(script), "check", "--root", str(target)],
                cwd=target, check=False, capture_output=True, text=True,
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertEqual(json.loads(checked.stdout)["status"], "PASS")
            self.assertFalse(json.loads(checked.stdout)["delivery_gate_ready"])
            projected = subprocess.run(
                [
                    *prefix, str(script), "context", "--root", str(target),
                    "--task-id", "PORTABLE-TEST", "--contract", "docs/tasks/PORTABLE-TEST.md",
                    "--route", "DIRECT_CURSOR_DELIVERY",
                ],
                cwd=target, check=False, capture_output=True, text=True,
            )
            self.assertEqual(projected.returncode, 0, projected.stdout + projected.stderr)
            receipt = json.loads(projected.stdout)
            self.assertEqual(receipt["task"]["task_id"], "PORTABLE-TEST")
            self.assertEqual(receipt["repository"]["head"], head)
            self.assertEqual(receipt["cloud_bundle_mode"], "OWNER_MANAGED_OPTIONAL_EXPORT")
            self.assertIn(
                "DELIVERY_EVIDENCE",
                {item["semantic_role"] for item in receipt["selected"]},
            )
            self.assertRegex(receipt["receipt_sha256"], r"^[0-9a-f]{64}$")

            profile_path = target / "delivery-harness/project-profile.yaml"
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            profile["bindings"]["historical_cloud_bundle_registry"] = (
                "docs/cloud-history/release_registry.json"
            )
            profile_path.write_text(
                json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            source_history = target / "docs/cloud-history/release_registry.json"
            source_history.parent.mkdir(parents=True)
            source_history.write_text("{}\n", encoding="utf-8")
            task_metadata["context_requirements"]["exact_role_paths"][
                "DELIVERY_EVIDENCE"
            ] = ["docs/cloud-history/release_registry.json"]
            task.write_text(
                "---\n"
                + json.dumps(task_metadata, ensure_ascii=False, sort_keys=True)
                + "\n---\n\n# Portable test\n",
                encoding="utf-8",
            )
            relabelled = subprocess.run(
                [
                    *prefix, str(script), "context", "--root", str(target),
                    "--task-id", "PORTABLE-TEST", "--contract", "docs/tasks/PORTABLE-TEST.md",
                    "--route", "DIRECT_CURSOR_DELIVERY",
                ],
                cwd=target, check=False, capture_output=True, text=True,
            )
            self.assertEqual(relabelled.returncode, 2)
            self.assertEqual(
                json.loads(relabelled.stdout)["reason"],
                "SOURCE_HISTORY_ROLE_MISMATCH",
            )

            task_metadata["context_requirements"]["l2_roles"] = []
            task_metadata["context_requirements"]["l3_roles"] = ["HISTORICAL_CONTEXT"]
            task_metadata["context_requirements"]["exact_role_paths"][
                "DELIVERY_EVIDENCE"
            ] = []
            task_metadata["context_requirements"]["exact_role_paths"][
                "HISTORICAL_CONTEXT"
            ] = ["docs/cloud-history/release_registry.json"]
            task.write_text(
                "---\n"
                + json.dumps(task_metadata, ensure_ascii=False, sort_keys=True)
                + "\n---\n\n# Portable test\n",
                encoding="utf-8",
            )
            historical = subprocess.run(
                [
                    *prefix, str(script), "context", "--root", str(target),
                    "--task-id", "PORTABLE-TEST", "--contract", "docs/tasks/PORTABLE-TEST.md",
                    "--route", "DIRECT_CURSOR_DELIVERY",
                ],
                cwd=target, check=False, capture_output=True, text=True,
            )
            self.assertEqual(historical.returncode, 0, historical.stdout + historical.stderr)
            self.assertIn(
                "HISTORICAL_CONTEXT",
                {item["semantic_role"] for item in json.loads(historical.stdout)["selected"]},
            )

    def test_portable_task_contract_is_nested_closed_shape_and_type_strict(self) -> None:
        portable_script = (
            ROOT
            / "delivery-harness/templates/portable-core/scripts/delivery_harness.py"
        )
        spec = importlib.util.spec_from_file_location(
            "portable_delivery_harness_contract_test", portable_script
        )
        if spec is None or spec.loader is None:
            self.fail("portable delivery harness is not loadable")
        portable = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(portable)
        oid = "a" * 40
        valid = {
            "task_id": "PORTABLE-TEST",
            "task_version": "1.0",
            "status": "READY",
            "as_of": "2026-08-14",
            "owner": "GOAL_OWNER",
            "allowed_routes": ["DIRECT_CURSOR_DELIVERY"],
            "expected_repository": "example/project",
            "git_binding": {
                "expected_base": oid,
                "expected_upstream": "origin/main",
                "expected_upstream_oid": oid,
                "expected_branch": "task/portable",
                "dirty_mode": "ALLOW_REPORTED",
            },
            "objective": "Prove a portable exact task contract safely.",
            "managed_write_set": ["docs/tasks/PORTABLE-TEST.md"],
            "external_caps": {
                "network": False,
                "credentials": False,
                "external_system": False,
                "signing_or_financial_action": False,
                "cash_spend": False,
                "deployment": False,
            },
            "stop_conditions": ["TASK_SCOPE_DRIFT"],
            "context_requirements": {
                "catalog_asset_ids": [],
                "l2_roles": [],
                "l3_roles": [],
                "roadmap_path": None,
                "exact_role_paths": {
                    "LIFECYCLE": [],
                    "EXTERNAL_ROUTE_KNOWLEDGE": [],
                    "ARCHITECTURE_DECISIONS": [],
                    "DELIVERY_EVIDENCE": [],
                    "HISTORICAL_CONTEXT": [],
                },
            },
        }
        portable.validate_task(valid, "PORTABLE-TEST")
        mutations = []
        unknown_cap = copy.deepcopy(valid)
        unknown_cap["external_caps"]["shell"] = False
        mutations.append(unknown_cap)
        numeric_bool = copy.deepcopy(valid)
        numeric_bool["external_caps"]["network"] = 1
        mutations.append(numeric_bool)
        invalid_write_set = copy.deepcopy(valid)
        invalid_write_set["managed_write_set"] = [True]
        mutations.append(invalid_write_set)
        invalid_stop = copy.deepcopy(valid)
        invalid_stop["stop_conditions"] = [1]
        mutations.append(invalid_stop)
        unknown_nested = copy.deepcopy(valid)
        unknown_nested["context_requirements"]["exact_role_paths"]["UNKNOWN"] = []
        mutations.append(unknown_nested)
        for mutated in mutations:
            with self.subTest(mutated=mutated):
                with self.assertRaisesRegex(ValueError, "TASK_CONTRACT_SCHEMA_INVALID"):
                    portable.validate_task(mutated, "PORTABLE-TEST")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = root / "docs/tasks/PORTABLE-TEST.md"
            task.parent.mkdir(parents=True)
            encoded = json.dumps(valid, ensure_ascii=False, sort_keys=True)
            duplicate = encoded.replace(
                '"git_binding":',
                '"git_binding": {"expected_base": "' + oid + '"}, "git_binding":',
                1,
            )
            task.write_text(
                "---\n" + duplicate + "\n---\n\n# Duplicate authority\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError, "TASK_CONTRACT_JSON_FRONTMATTER_REQUIRED"
            ):
                portable.parse_task(root, "PORTABLE-TEST", "docs/tasks/PORTABLE-TEST.md")

    def test_installed_check_rejects_duplicate_or_missing_context_roles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            initialize_repository(target)
            plan = self.module.plan_initialization(target, ROOT, repository=REPOSITORY)
            self.module.apply_initialization(target, plan)
            context_path = target / "delivery-harness/context-map.yaml"
            context_map = json.loads(context_path.read_text(encoding="utf-8"))
            context_map["roles"][-1]["semantic_role"] = "DELIVERY_EVIDENCE"
            context_path.write_text(
                json.dumps(context_map, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            checked = subprocess.run(
                [
                    sys.executable, "-S",
                    str(target / "scripts/delivery_harness.py"),
                    "check", "--root", str(target),
                ],
                cwd=target, check=False, capture_output=True, text=True,
            )
            self.assertEqual(checked.returncode, 2)
            self.assertIn("CORE_CONTRACT_INVALID", json.loads(checked.stdout)["errors"])

    def test_portable_core_contracts_reject_nested_authority_and_shape_drift(self) -> None:
        cases = (
            (
                "delivery-harness/harness.yaml",
                lambda value: value["external_authority"].__setitem__(
                    "external_system", True
                ),
            ),
            (
                "delivery-harness/project-profile.yaml",
                lambda value: value["authority"].__setitem__("unknown", False),
            ),
            (
                "delivery-harness/context-map.yaml",
                lambda value: value["roles"][0]["resolver"].__setitem__(
                    "fallback", "latest"
                ),
            ),
            (
                "control/owner_attention_gate_v2.yaml",
                lambda value: value["invariants"].__setitem__(
                    "external_authority", True
                ),
            ),
            (
                "delivery-harness/capability-radar.yaml",
                lambda value: value["authority"].__setitem__("install", True),
            ),
        )
        for relative, mutate in cases:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "project"
                target.mkdir()
                initialize_repository(target)
                plan = self.module.plan_initialization(
                    target, ROOT, repository=REPOSITORY
                )
                self.module.apply_initialization(target, plan)
                path = target / relative
                document = json.loads(path.read_text(encoding="utf-8"))
                mutate(document)
                path.write_text(json.dumps(document), encoding="utf-8")
                portable_spec = importlib.util.spec_from_file_location(
                    "installed_portable_core_contract_test",
                    target / "scripts/delivery_harness.py",
                )
                if portable_spec is None or portable_spec.loader is None:
                    self.fail("installed portable harness is not loadable")
                portable = importlib.util.module_from_spec(portable_spec)
                portable_spec.loader.exec_module(portable)
                checked = portable.check(target)
                self.assertEqual(checked["status"], "PENDING")
                self.assertIn("CORE_CONTRACT_INVALID", checked["errors"])

    def test_plan_is_bound_to_target_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first"
            second = Path(directory) / "second"
            first.mkdir()
            second.mkdir()
            for target in (first, second):
                initialize_repository(target)
            plan = self.module.plan_initialization(
                first, ROOT, repository=REPOSITORY
            )
            with self.assertRaisesRegex(ValueError, "INITIALIZATION_TARGET_MISMATCH"):
                self.module.apply_initialization(second, plan)

    def test_nested_cursor_or_agent_target_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "project"
            nested = repo / ".cursor/rules"
            nested.mkdir(parents=True)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            with self.assertRaisesRegex(ValueError, "GLOBAL_CONFIG_TARGET_FORBIDDEN"):
                self.module.plan_initialization(
                    nested, ROOT, repository=REPOSITORY
                )

    def test_conflicting_target_refuses_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            initialize_repository(target)
            conflict = target / "delivery-harness/project-profile.yaml"
            conflict.parent.mkdir(parents=True)
            conflict.write_text("user-owned: true\n", encoding="utf-8")
            before = conflict.read_bytes()
            plan = self.module.plan_initialization(
                target, ROOT, repository=REPOSITORY
            )
            self.assertEqual(plan["decision"], "CONFLICT_REFUSAL")
            with self.assertRaisesRegex(ValueError, "INITIALIZATION_NOT_ALLOWED"):
                self.module.apply_initialization(target, plan)
            self.assertEqual(conflict.read_bytes(), before)

    def test_file_ancestor_obstruction_refuses_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            initialize_repository(target)
            obstruction = target / ".cursor"
            obstruction.write_text("user-owned file\n", encoding="utf-8")
            before = {
                path.relative_to(target).as_posix(): path.read_bytes()
                for path in target.rglob("*")
                if path.is_file() and ".git" not in path.relative_to(target).parts
            }
            plan = self.module.plan_initialization(
                target, ROOT, repository=REPOSITORY
            )
            self.assertEqual(plan["decision"], "CONFLICT_REFUSAL")
            self.assertTrue(
                any(path.startswith(".cursor/") for path in plan["conflicts"])
            )
            with self.assertRaisesRegex(ValueError, "INITIALIZATION_NOT_ALLOWED"):
                self.module.apply_initialization(target, plan)
            after = {
                path.relative_to(target).as_posix(): path.read_bytes()
                for path in target.rglob("*")
                if path.is_file() and ".git" not in path.relative_to(target).parts
            }
            self.assertEqual(after, before)

    def test_plan_drift_refuses_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            initialize_repository(target)
            plan = self.module.plan_initialization(
                target, ROOT, repository=REPOSITORY
            )
            drift = target / "delivery-harness/project-profile.yaml"
            drift.parent.mkdir(parents=True)
            drift.write_text("drift: true\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "PLAN_DRIFT"):
                self.module.apply_initialization(target, plan)

    def test_global_or_unsafe_target_is_rejected(self) -> None:
        for relative in (".cursor", ".codex", ".agents"):
            with tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / relative
                target.mkdir()
                with self.assertRaisesRegex(ValueError, "GLOBAL_CONFIG_TARGET_FORBIDDEN"):
                    self.module.plan_initialization(
                        target, ROOT, repository=REPOSITORY
                    )

    def test_user_home_repository_root_is_never_an_initialization_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "home"
            target.mkdir()
            initialize_repository(target)
            with mock.patch.object(
                self.module.Path, "home", return_value=target.resolve()
            ):
                with self.assertRaisesRegex(
                    ValueError, "GLOBAL_CONFIG_TARGET_FORBIDDEN"
                ):
                    self.module.plan_initialization(
                        target, ROOT, repository=REPOSITORY
                    )

    def test_reparse_boundary_is_rejected_before_target_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            initialize_repository(target)
            with mock.patch.object(
                self.module, "has_reparse_boundary", return_value=True
            ):
                with self.assertRaisesRegex(
                    ValueError, "INITIALIZATION_REPARSE_TARGET_FORBIDDEN"
                ):
                    self.module.plan_initialization(
                        target, ROOT, repository=REPOSITORY
                    )

    def test_portable_output_has_no_solana_specific_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            initialize_repository(target)
            plan = self.module.plan_initialization(
                target, ROOT, repository=REPOSITORY
            )
            self.module.apply_initialization(target, plan)
            text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in target.rglob("*")
                if path.is_file() and ".git" not in path.relative_to(target).parts
            ).casefold()
            for forbidden in (
                "solana",
                "lancerbeta",
                "task-30",
                "helius",
                "wallet",
            ):
                self.assertNotIn(forbidden, text)

    def test_repository_identity_is_single_source_for_portable_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            initialize_repository(target, "acme/research")
            plan = self.module.plan_initialization(
                target, ROOT, repository="acme/research"
            )
            self.module.apply_initialization(target, plan)
            profile = (target / "delivery-harness/project-profile.yaml").read_text(
                encoding="utf-8"
            )
            policy = (target / "control/owner_attention_gate_v2.yaml").read_text(
                encoding="utf-8"
            )
            bootstrap = (target / "delivery-harness/bootstrap-prompt.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(json.loads(profile)["repository"]["name"], "acme/research")
            self.assertEqual(json.loads(policy)["repository"], "acme/research")
            self.assertIn("https://github.com/acme/research", bootstrap)
            self.assertNotIn("example/project", profile + policy + bootstrap)
            self.assertNotIn("lancerbeta/solana-alpha-lab", bootstrap)

    def test_repository_identity_is_required_and_origin_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)
            with self.assertRaisesRegex(ValueError, "INITIALIZATION_REPOSITORY_REQUIRED"):
                self.module.plan_initialization(
                    target, ROOT, repository="acme/research"
                )
            with self.assertRaisesRegex(ValueError, "INITIALIZATION_REPOSITORY_REQUIRED"):
                self.module.plan_initialization(target, ROOT)
            subprocess.run(
                ["git", "remote", "add", "origin", "https://github.com/acme/other.git"],
                cwd=target, check=True,
            )
            with self.assertRaisesRegex(ValueError, "INITIALIZATION_REPOSITORY_MISMATCH"):
                self.module.plan_initialization(
                    target, ROOT, repository="acme/research"
                )

    def test_bundle_manifest_covers_every_portable_template(self) -> None:
        manifest = json.loads(
            (ROOT / "delivery-harness/templates/portable-bundle-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        records = self.module.load_portable_bundle_manifest(ROOT)
        self.assertEqual(records, manifest["files"])
        self.assertEqual(
            len({record["destination"] for record in records}), len(records)
        )

    def test_manifest_blocks_tampered_source_before_initialization(self) -> None:
        manifest = json.loads(
            (ROOT / "delivery-harness/templates/portable-bundle-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory) / "source"
            manifest_target = source_root / self.module.PORTABLE_MANIFEST_PATH
            manifest_target.parent.mkdir(parents=True)
            shutil.copy2(
                ROOT / self.module.PORTABLE_MANIFEST_PATH,
                manifest_target,
            )
            for record in manifest["files"]:
                destination = source_root / record["source"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / record["source"], destination)
            tampered = source_root / manifest["files"][0]["source"]
            tampered.write_bytes(tampered.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "PORTABLE_TEMPLATE_HASH_MISMATCH"):
                self.module.load_portable_bundle_manifest(source_root)

    def test_manifest_is_the_single_portable_execution_inventory_owner(self) -> None:
        harness = self.module.load_mapping(ROOT / "delivery-harness/harness.yaml")
        portable = harness["portable_bundle"]
        self.assertEqual(
            portable["execution_inventory_owner"], "PORTABLE_BUNDLE_MANIFEST"
        )
        self.assertEqual(
            portable["manifest_path"], self.module.PORTABLE_MANIFEST_PATH
        )
        self.assertEqual(
            set(portable["entry_artifacts"]),
            {
                "delivery-harness/templates/portable-project-profile.yaml",
                "delivery-harness/templates/bootstrap-prompt.md",
            },
        )
        plan = (
            ROOT / "docs/superpowers/plans/2026-08-13-delivery-harness-v1.md"
        ).read_text(encoding="utf-8")
        self.assertIn("single closed execution inventory", plan)
        self.assertIn("portable-bundle-manifest.json", plan)

    def test_initializer_preview_is_stdlib_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            initialize_repository(target)
            result = subprocess.run(
                [
                    sys.executable,
                    "-S",
                    str(SCRIPT),
                    "init",
                    "--target",
                    str(target),
                    "--repository",
                    REPOSITORY,
                    "--default-branch",
                    "main",
                    "--preview",
                    "--format",
                    "json",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["decision"], "APPLY_ALLOWED")

    def test_initializer_renders_exact_non_main_default_branch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            initialize_repository(target, default_branch="trunk")
            plan = self.module.plan_initialization(
                target, ROOT, repository=REPOSITORY
            )
            self.assertEqual(plan["default_branch"], "trunk")
            self.module.apply_initialization(target, plan)
            profile = json.loads(
                (target / "delivery-harness/project-profile.yaml").read_text(
                    encoding="utf-8"
                )
            )
            prompt = (target / "delivery-harness/bootstrap-prompt.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(profile["repository"]["default_branch"], "trunk")
            self.assertIn("Fetch `trunk`", prompt)
            self.assertNotIn("Fetch `main`", prompt)
            self.assertNotIn("base `main`", prompt)
            with self.assertRaisesRegex(
                ValueError, "INITIALIZATION_DEFAULT_BRANCH_MISMATCH"
            ):
                self.module.plan_initialization(
                    target,
                    ROOT,
                    repository=REPOSITORY,
                    default_branch="main",
                )

    def test_missing_origin_head_requires_explicit_branch_not_feature_head(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            initialize_repository(target)
            subprocess.run(
                ["git", "symbolic-ref", "--delete", "refs/remotes/origin/HEAD"],
                cwd=target, check=True, capture_output=True,
            )
            subprocess.run(
                ["git", "symbolic-ref", "HEAD", "refs/heads/feature/experiment"],
                cwd=target, check=True, capture_output=True,
            )
            with self.assertRaisesRegex(
                ValueError, "INITIALIZATION_DEFAULT_BRANCH_REQUIRED"
            ):
                self.module.plan_initialization(
                    target, ROOT, repository=REPOSITORY
                )
            plan = self.module.plan_initialization(
                target,
                ROOT,
                repository=REPOSITORY,
                default_branch="main",
            )
            self.assertEqual(plan["default_branch"], "main")

    def test_python311_compatible_reparse_attribute_is_fail_closed(self) -> None:
        attributes = getattr(self.module.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        with mock.patch.object(
            self.module.os,
            "lstat",
            return_value=SimpleNamespace(st_file_attributes=attributes),
        ):
            self.assertTrue(self.module.is_reparse_point(Path("junction")))

    def test_active_baton_script_reference_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            initialize_repository(target)
            plan = self.module.plan_initialization(
                target, ROOT, repository=REPOSITORY
            )
            self.module.apply_initialization(target, plan)
            command = target / ".cursor/commands/reactivate.md"
            for text in (
                "Run python scripts/baton_preflight.py now.\n",
                "Run python -m scripts.baton_preflight now.\n",
                "import baton_preflight; baton_preflight.main()\n",
            ):
                with self.subTest(text=text):
                    command.write_text(text, encoding="utf-8")
                    checked = self.module.check_harness(target)
                    self.assertEqual(checked["status"], "PENDING")
                    self.assertIn("ACTIVE_BATON_REFERENCE", checked["errors"])
            command.unlink()
            agent = target / ".cursor/agents/custom-reviewer.md"
            agent.parent.mkdir(parents=True, exist_ok=True)
            agent.write_text(
                "Run python -m scripts.baton_preflight now.\n",
                encoding="utf-8",
            )
            checked = self.module.check_harness(target)
            self.assertEqual(checked["status"], "PENDING")
            self.assertIn("ACTIVE_BATON_REFERENCE", checked["errors"])
            agent.unlink()
            agents = target / "AGENTS.md"
            agents.write_text(
                agents.read_text(encoding="utf-8")
                + "\nUse GITHUB_BATON for this delivery.\n",
                encoding="utf-8",
            )
            checked = self.module.check_harness(target)
            self.assertEqual(checked["status"], "PENDING")
            self.assertIn("ACTIVE_BATON_REFERENCE", checked["errors"])

    def test_bootstrap_prompt_is_exact_current_repo_entrypoint(self) -> None:
        prompt = (
            ROOT / "delivery-harness/templates/bootstrap-prompt.md"
        ).read_text(encoding="utf-8")
        self.assertIn("https://github.com/lancerbeta/solana-alpha-lab", prompt)
        self.assertIn("DELIVERY_HARNESS_BOOTSTRAP=PASS", prompt)
        self.assertIn("DELIVERY_HARNESS_BOOTSTRAP=BLOCKED:", prompt)
        self.assertIn("one repository or worktree root", prompt)
        self.assertIn("Fetch `main`", prompt)
        self.assertNotIn("{{DEFAULT_BRANCH}}", prompt)
        self.assertNotIn("search latest", prompt.casefold())
        self.assertNotIn("install plugin", prompt.casefold())

    def test_owner_docs_expose_exact_preview_then_apply_initializer(self) -> None:
        expected_preview = (
            "python -B scripts/delivery_harness.py init --target <NEW_REPOSITORY_ROOT> "
            "--repository <OWNER/REPOSITORY> --default-branch <DEFAULT_BRANCH> "
            "--preview --format json"
        )
        expected_apply = (
            "python -B scripts/delivery_harness.py init --target <NEW_REPOSITORY_ROOT> "
            "--repository <OWNER/REPOSITORY> --default-branch <DEFAULT_BRANCH> "
            "--apply --plan-sha256 <PLAN_SHA256> "
            "--format json"
        )
        for path in (ROOT / "README.md", ROOT / "docs/agent/DELIVERY_HARNESS_BOOTSTRAP.md"):
            text = path.read_text(encoding="utf-8")
            self.assertIn(expected_preview, text, path)
            self.assertIn(expected_apply, text, path)
            self.assertIn("standard", text, path)
            self.assertIn("library", text, path)


if __name__ == "__main__":
    unittest.main()
