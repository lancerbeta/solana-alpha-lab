from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


domain = load("validate_execution_domain", "scripts/validate_execution_domain.py")
runner = load("run_ci_execution_domain", "scripts/run_ci_execution_domain.py")
shard_runner = load("run_ci_test_shard", "scripts/run_ci_test_shard.py")
partition = load("ci_test_partition", "scripts/ci_test_partition.py")
MANIFEST_PATH = ROOT / "configs/execution_domain_v1.json"


class ExecutionDomainModularityTests(unittest.TestCase):
    def test_live_manifest_passes_boundary(self) -> None:
        manifest = domain.load_execution_domain(MANIFEST_PATH)
        report = domain.validate_execution_domain(manifest, root=ROOT)
        self.assertEqual(report["domain_id"], "FACTORY_PAPER_SHADOW_EXECUTION_V1")
        self.assertIn("tests/test_factory_strategy_execution_boundary_v1.py", report["direct_test_importers"])

    def test_paper_plane_to_application_is_rejected_in_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src/solana_alpha_lab/factory").mkdir(parents=True)
            (root / "catalog/schemas").mkdir(parents=True)
            for name in (
                "strategy_version_v1_1.schema.json",
                "signal_decision_v1.schema.json",
                "exit_decision_v1.schema.json",
            ):
                (root / "catalog/schemas" / name).write_text("{}", encoding="utf-8")
            (root / "src/solana_alpha_lab/factory/strategy_runtime.py").write_text(
                "VALUE = 1\n",
                encoding="utf-8",
            )
            (root / "src/solana_alpha_lab/factory/application.py").write_text(
                "VALUE = 2\n",
                encoding="utf-8",
            )
            (root / "src/solana_alpha_lab/factory/paper_plane.py").write_text(
                "from solana_alpha_lab.factory import application\n",
                encoding="utf-8",
            )
            (root / "src/solana_alpha_lab/factory/paper_shadow_operations.py").write_text(
                "from solana_alpha_lab.factory.paper_plane import PaperPlaneStore\n",
                encoding="utf-8",
            )
            (root / "src/solana_alpha_lab/factory/paper_shadow_commands.py").write_text(
                "from solana_alpha_lab.factory.paper_plane import PaperPlaneStore\n",
                encoding="utf-8",
            )
            (root / "tests").mkdir()
            (root / "tests/test_meta.py").write_text("import unittest\n", encoding="utf-8")
            manifest = {
                "schema": "smial.execution-domain.v1",
                "domain_id": "FACTORY_PAPER_SHADOW_EXECUTION_V1",
                "contract_paths": [
                    "catalog/schemas/strategy_version_v1_1.schema.json",
                    "catalog/schemas/signal_decision_v1.schema.json",
                    "catalog/schemas/exit_decision_v1.schema.json",
                ],
                "source_modules": [
                    {"path": "src/solana_alpha_lab/factory/strategy_runtime.py", "allowed_factory_imports": []},
                    {
                        "path": "src/solana_alpha_lab/factory/paper_plane.py",
                        "allowed_factory_imports": ["solana_alpha_lab.factory.strategy_runtime"],
                    },
                    {
                        "path": "src/solana_alpha_lab/factory/paper_shadow_operations.py",
                        "allowed_factory_imports": ["solana_alpha_lab.factory.paper_plane"],
                    },
                    {
                        "path": "src/solana_alpha_lab/factory/paper_shadow_commands.py",
                        "allowed_factory_imports": [
                            "solana_alpha_lab.factory.paper_plane",
                            "solana_alpha_lab.factory.paper_shadow_operations",
                        ],
                    },
                ],
                "adapter_consumers": ["src/solana_alpha_lab/factory/application.py"],
                "required_fast_test_modules": ["tests/test_meta.py"],
                "test_inventory_policy": "EXACTLY_ONCE_ACROSS_EXECUTION_AND_GENERAL_SHARDS",
                "runtime_mode_scope": ["PAPER", "SHADOW"],
                "live_authority": False,
            }
            with self.assertRaises(domain.ExecutionDomainError) as ctx:
                domain.validate_execution_domain(manifest, root=root)
            self.assertIn("UNDECLARED_FACTORY_IMPORT", str(ctx.exception))

    def test_relative_import_to_application_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src/solana_alpha_lab/factory").mkdir(parents=True)
            (root / "catalog/schemas").mkdir(parents=True)
            for name in (
                "strategy_version_v1_1.schema.json",
                "signal_decision_v1.schema.json",
                "exit_decision_v1.schema.json",
            ):
                (root / "catalog/schemas" / name).write_text("{}", encoding="utf-8")
            (root / "src/solana_alpha_lab/factory/strategy_runtime.py").write_text(
                "VALUE = 1\n", encoding="utf-8"
            )
            (root / "src/solana_alpha_lab/factory/application.py").write_text(
                "VALUE = 2\n", encoding="utf-8"
            )
            (root / "src/solana_alpha_lab/factory/paper_plane.py").write_text(
                "from solana_alpha_lab.factory.strategy_runtime import VALUE\n"
                "from . import application\n",
                encoding="utf-8",
            )
            (root / "src/solana_alpha_lab/factory/paper_shadow_operations.py").write_text(
                "from solana_alpha_lab.factory.paper_plane import VALUE as P\n",
                encoding="utf-8",
            )
            (root / "src/solana_alpha_lab/factory/paper_shadow_commands.py").write_text(
                "from solana_alpha_lab.factory.paper_plane import VALUE as P\n"
                "from solana_alpha_lab.factory.paper_shadow_operations import P as O\n",
                encoding="utf-8",
            )
            (root / "tests").mkdir()
            (root / "tests/test_meta.py").write_text("import unittest\n", encoding="utf-8")
            manifest = {
                "schema": "smial.execution-domain.v1",
                "domain_id": "FACTORY_PAPER_SHADOW_EXECUTION_V1",
                "contract_paths": [
                    "catalog/schemas/strategy_version_v1_1.schema.json",
                    "catalog/schemas/signal_decision_v1.schema.json",
                    "catalog/schemas/exit_decision_v1.schema.json",
                ],
                "source_modules": [
                    {"path": "src/solana_alpha_lab/factory/strategy_runtime.py", "allowed_factory_imports": []},
                    {
                        "path": "src/solana_alpha_lab/factory/paper_plane.py",
                        "allowed_factory_imports": ["solana_alpha_lab.factory.strategy_runtime"],
                    },
                    {
                        "path": "src/solana_alpha_lab/factory/paper_shadow_operations.py",
                        "allowed_factory_imports": ["solana_alpha_lab.factory.paper_plane"],
                    },
                    {
                        "path": "src/solana_alpha_lab/factory/paper_shadow_commands.py",
                        "allowed_factory_imports": [
                            "solana_alpha_lab.factory.paper_plane",
                            "solana_alpha_lab.factory.paper_shadow_operations",
                        ],
                    },
                ],
                "adapter_consumers": ["src/solana_alpha_lab/factory/application.py"],
                "required_fast_test_modules": ["tests/test_meta.py"],
                "test_inventory_policy": "EXACTLY_ONCE_ACROSS_EXECUTION_AND_GENERAL_SHARDS",
                "runtime_mode_scope": ["PAPER", "SHADOW"],
                "live_authority": False,
            }
            with self.assertRaises(domain.ExecutionDomainError) as ctx:
                domain.validate_execution_domain(manifest, root=root)
            self.assertIn("UNDECLARED_FACTORY_IMPORT", str(ctx.exception))
            self.assertIn("application", str(ctx.exception))

    def test_missing_contract_path_fails_closed(self) -> None:
        manifest = domain.load_execution_domain(MANIFEST_PATH)
        broken = dict(manifest)
        broken["contract_paths"] = list(manifest["contract_paths"]) + [
            "catalog/schemas/missing_contract.json"
        ]
        with self.assertRaises(domain.ExecutionDomainError):
            domain.validate_execution_domain(broken, root=ROOT)

    def test_duplicate_manifest_paths_fail_closed(self) -> None:
        manifest = domain.load_execution_domain(MANIFEST_PATH)
        broken = dict(manifest)
        broken["required_fast_test_modules"] = list(manifest["required_fast_test_modules"])
        broken["required_fast_test_modules"].append(
            manifest["required_fast_test_modules"][0]
        )
        with self.assertRaises(domain.ExecutionDomainError):
            domain.validate_execution_domain(broken, root=ROOT)

    def test_parent_traversal_path_rejected(self) -> None:
        with self.assertRaises(domain.ExecutionDomainError):
            domain.normalize_repo_relative("../secrets.env")

    def test_undeclared_test_importer_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            (root / "tests/test_sneaky.py").write_text(
                "from solana_alpha_lab.factory.paper_plane import PaperPlaneStore\n",
                encoding="utf-8",
            )
            importers = domain.direct_test_importers(
                {
                    "src/solana_alpha_lab/factory/paper_plane.py",
                },
                root=root,
            )
            self.assertIn("tests/test_sneaky.py", importers)

    def test_execution_runner_selects_manifest_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "tests"
            tests.mkdir()
            (root / "src/solana_alpha_lab/factory").mkdir(parents=True)
            (root / "catalog/schemas").mkdir(parents=True)
            for name in (
                "strategy_version_v1_1.schema.json",
                "signal_decision_v1.schema.json",
                "exit_decision_v1.schema.json",
            ):
                (root / "catalog/schemas" / name).write_text("{}", encoding="utf-8")
            (root / "src/solana_alpha_lab/factory/strategy_runtime.py").write_text(
                "VALUE = 1\n", encoding="utf-8"
            )
            (root / "src/solana_alpha_lab/factory/paper_plane.py").write_text(
                "from solana_alpha_lab.factory.strategy_runtime import VALUE\n",
                encoding="utf-8",
            )
            (root / "src/solana_alpha_lab/factory/paper_shadow_operations.py").write_text(
                "from solana_alpha_lab.factory.paper_plane import VALUE as P\n",
                encoding="utf-8",
            )
            (root / "src/solana_alpha_lab/factory/paper_shadow_commands.py").write_text(
                "from solana_alpha_lab.factory.paper_plane import VALUE as P\n"
                "from solana_alpha_lab.factory.paper_shadow_operations import P as O\n",
                encoding="utf-8",
            )
            (root / "src/solana_alpha_lab/factory/application.py").write_text(
                "VALUE = 2\n", encoding="utf-8"
            )
            (tests / "test_fast.py").write_text(
                textwrap.dedent(
                    """\
                    import unittest
                    class Fast(unittest.TestCase):
                        def test_ok(self):
                            self.assertTrue(True)
                    """
                ),
                encoding="utf-8",
            )
            (tests / "test_other.py").write_text(
                textwrap.dedent(
                    """\
                    import unittest
                    class Other(unittest.TestCase):
                        def test_ok(self):
                            self.assertTrue(True)
                    """
                ),
                encoding="utf-8",
            )
            manifest = {
                "schema": "smial.execution-domain.v1",
                "domain_id": "FACTORY_PAPER_SHADOW_EXECUTION_V1",
                "contract_paths": [
                    "catalog/schemas/strategy_version_v1_1.schema.json",
                    "catalog/schemas/signal_decision_v1.schema.json",
                    "catalog/schemas/exit_decision_v1.schema.json",
                ],
                "source_modules": [
                    {"path": "src/solana_alpha_lab/factory/strategy_runtime.py", "allowed_factory_imports": []},
                    {
                        "path": "src/solana_alpha_lab/factory/paper_plane.py",
                        "allowed_factory_imports": ["solana_alpha_lab.factory.strategy_runtime"],
                    },
                    {
                        "path": "src/solana_alpha_lab/factory/paper_shadow_operations.py",
                        "allowed_factory_imports": ["solana_alpha_lab.factory.paper_plane"],
                    },
                    {
                        "path": "src/solana_alpha_lab/factory/paper_shadow_commands.py",
                        "allowed_factory_imports": [
                            "solana_alpha_lab.factory.paper_plane",
                            "solana_alpha_lab.factory.paper_shadow_operations",
                        ],
                    },
                ],
                "adapter_consumers": ["src/solana_alpha_lab/factory/application.py"],
                "required_fast_test_modules": ["tests/test_fast.py"],
                "test_inventory_policy": "EXACTLY_ONCE_ACROSS_EXECUTION_AND_GENERAL_SHARDS",
                "runtime_mode_scope": ["PAPER", "SHADOW"],
                "live_authority": False,
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            code = runner.run_execution_domain(manifest_path=manifest_path, root=root)
            self.assertEqual(code, 0)

    def test_execution_runner_rejects_missing_reserved_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            manifest = domain.load_execution_domain(MANIFEST_PATH)
            manifest = dict(manifest)
            manifest["required_fast_test_modules"] = [
                "tests/test_missing_execution_module.py"
            ]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            try:
                runner.run_execution_domain(manifest_path=manifest_path, root=ROOT)
            except Exception as exc:
                self.assertIn("PATH_MISSING", str(exc))
            else:
                self.fail("missing reserved module should fail closed")

    def test_general_shards_exclude_reserved_modules(self) -> None:
        manifest = domain.load_execution_domain(MANIFEST_PATH)
        reserved = set(manifest["required_fast_test_modules"])
        plan = partition.load_plan(ROOT / "configs/ci_test_shards_v1.json")
        current = sorted(
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "tests").glob("test_*.py")
            if path.is_file()
        )
        current_general = [path for path in current if path not in reserved]
        covered: list[str] = []
        for shard_index in range(4):
            covered.extend(
                partition.select_modules_for_shard(
                    current_general,
                    plan=plan,
                    index=shard_index,
                    count=4,
                )
            )
        self.assertFalse(reserved & set(covered))
        self.assertEqual(set(covered) | reserved, set(current))

    def test_subtract_reserved_modules_fails_on_stale_manifest_entry(self) -> None:
        with self.assertRaises(partition.PartitionError):
            partition.subtract_reserved_modules(
                {"tests/test_a.py": 1.0},
                ["tests/test_missing.py"],
            )

    def test_subtract_reserved_modules_removes_only_declared_modules(self) -> None:
        modules = {
            "tests/test_a.py": 1.0,
            "tests/test_b.py": 2.0,
            "tests/test_c.py": 3.0,
        }
        result = partition.subtract_reserved_modules(
            modules,
            ["tests/test_b.py"],
        )
        self.assertEqual(result, {"tests/test_a.py": 1.0, "tests/test_c.py": 3.0})


if __name__ == "__main__":
    unittest.main()
