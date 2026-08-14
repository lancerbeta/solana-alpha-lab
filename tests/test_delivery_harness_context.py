from __future__ import annotations

import copy
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest import mock

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/delivery_harness.py"
RECEIPT_SCHEMA = ROOT / "catalog/schemas/delivery_harness_context_receipt.schema.json"
TASK_CONTRACT = "docs/tasks/CTRL-DELIVERY-HARNESS-V1.md"
TASK_ID = "CTRL-DELIVERY-HARNESS-V1"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("delivery_harness", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("delivery harness script is not loadable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeliveryHarnessContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()
        cls.schema = json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8"))

    def receipt(self, route: str = "DIRECT_CODEX_DELIVERY") -> dict:
        return self.module.build_context_receipt(
            ROOT,
            task_id=TASK_ID,
            task_contract=TASK_CONTRACT,
            route=route,
        )

    def test_github_pr_detached_checkout_uses_exact_head_ref(self) -> None:
        values = {
            ("rev-parse", "HEAD"): "a" * 40,
            ("rev-parse", "HEAD^{tree}"): "b" * 40,
            ("branch", "--show-current"): "",
            ("status", "--porcelain=v1"): "",
        }
        with (
            mock.patch.object(
                self.module,
                "git_text",
                side_effect=lambda _root, *args: values[args],
            ),
            mock.patch.dict(
                os.environ,
                {
                    "GITHUB_ACTIONS": "true",
                    "GITHUB_HEAD_REF": "ctrl-delivery-harness-v1",
                },
                clear=False,
            ),
        ):
            identity = self.module.git_identity(ROOT)
        self.assertEqual(identity["branch"], "ctrl-delivery-harness-v1")

    def test_receipt_is_closed_valid_and_self_hashing(self) -> None:
        receipt = self.receipt()
        jsonschema.validate(receipt, self.schema)
        self.assertEqual(self.module.validate_context_receipt(receipt), [])
        unsigned = copy.deepcopy(receipt)
        observed_hash = unsigned.pop("receipt_sha256")
        self.assertEqual(
            observed_hash,
            self.module.sha256_bytes(self.module.canonical_json_bytes(unsigned)),
        )
        receipt["unexpected"] = True
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(receipt, self.schema)

    def test_cursor_and_codex_resolve_equivalent_context(self) -> None:
        codex = self.receipt("DIRECT_CODEX_DELIVERY")
        cursor = self.receipt("DIRECT_CURSOR_DELIVERY")
        for value in (codex, cursor):
            value.pop("receipt_sha256")
            value.pop("route")
        self.assertEqual(codex, cursor)

    def test_cloud_bundle_is_not_selected_as_working_context(self) -> None:
        receipt = self.receipt()
        self.assertFalse(
            any(
                item["path"].startswith("docs/project_sources/")
                for item in receipt["selected"]
            )
        )
        roadmap_gap = next(
            gap for gap in receipt["gaps"] if gap["semantic_role"] == "PRODUCT_ROADMAP"
        )
        self.assertEqual(roadmap_gap["reason_code"], "NO_EXACT_GIT_ROADMAP_BOUND")
        self.assertEqual(receipt["cloud_bundle_mode"], "OWNER_MANAGED_OPTIONAL_EXPORT")

    def test_task_id_must_match_exact_contract_frontmatter(self) -> None:
        with self.assertRaisesRegex(ValueError, "TASK_ID_CONTRACT_MISMATCH"):
            self.module.build_context_receipt(
                ROOT,
                task_id="FAKE-TASK-ID",
                task_contract=TASK_CONTRACT,
                route="DIRECT_CODEX_DELIVERY",
            )

    def test_duplicate_yaml_keys_in_task_contract_fail_closed(self) -> None:
        with self.assertRaisesRegex(yaml.YAMLError, "duplicate key 'git_binding'"):
            self.module.load_yaml_unique(
                "task_id: TEST-TASK\n"
                "git_binding: {expected_base: '" + ("a" * 40) + "'}\n"
                "git_binding: {expected_base: '" + ("b" * 40) + "'}\n"
            )

    def test_task_git_binding_is_checked_fail_closed(self) -> None:
        metadata = self.module.parse_task_contract(ROOT, TASK_CONTRACT, TASK_ID)
        identity = self.module.git_identity(ROOT)
        self.module.validate_task_git_binding(ROOT, metadata, identity)
        changed = copy.deepcopy(metadata)
        changed["git_binding"]["expected_upstream_oid"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "TASK_UPSTREAM_OID_MISMATCH"):
            self.module.validate_task_git_binding(ROOT, changed, identity)
        changed = copy.deepcopy(metadata)
        changed["git_binding"]["expected_branch"] = "wrong-branch"
        with self.assertRaisesRegex(ValueError, "TASK_BRANCH_MISMATCH"):
            self.module.validate_task_git_binding(ROOT, changed, identity)

        original = self.module.git_text

        def wrong_fork_base(root: Path, *args: str) -> str:
            if args[:3] == ("merge-base", "HEAD", metadata["git_binding"]["expected_upstream"]):
                return "0" * 40
            return original(root, *args)

        with mock.patch.object(self.module, "git_text", side_effect=wrong_fork_base):
            with self.assertRaisesRegex(ValueError, "TASK_EXPECTED_BASE_MISMATCH"):
                self.module.validate_task_git_binding(ROOT, metadata, identity)

    def test_repository_identity_is_bound_to_live_origin(self) -> None:
        self.module.validate_repository_origin(ROOT, "lancerbeta/solana-alpha-lab")
        self.assertEqual(
            self.module.github_repository_from_origin(
                "ssh://git@github.com/lancerbeta/solana-alpha-lab.git"
            ),
            "lancerbeta/solana-alpha-lab",
        )
        with mock.patch.object(
            self.module,
            "git_text",
            return_value="git@github.com:someone/other.git",
        ):
            with self.assertRaisesRegex(ValueError, "TASK_REPOSITORY_ORIGIN_MISMATCH"):
                self.module.validate_repository_origin(
                    ROOT, "lancerbeta/solana-alpha-lab"
                )

    def test_non_task_document_cannot_be_used_as_task_contract(self) -> None:
        with self.assertRaisesRegex(ValueError, "TASK_CONTRACT_SCHEMA_INVALID"):
            self.module.build_context_receipt(
                ROOT,
                task_id=TASK_ID,
                task_contract="README.md",
                route="DIRECT_CODEX_DELIVERY",
            )

    def test_default_context_does_not_load_l2_provider_registry(self) -> None:
        receipt = self.receipt()
        self.assertFalse(
            any(
                item["semantic_role"] == "EXTERNAL_ROUTE_KNOWLEDGE"
                for item in receipt["selected"]
            )
        )
        gap = next(
            item
            for item in receipt["gaps"]
            if item["semantic_role"] == "EXTERNAL_ROUTE_KNOWLEDGE"
        )
        self.assertEqual(gap["reason_code"], "DEFERRED_ON_DEMAND")

    def test_task_catalog_relations_are_bounded_to_exact_task_asset(self) -> None:
        receipt = self.receipt()
        catalog_items = [
            item
            for item in receipt["selected"]
            if item["semantic_role"] == "STABLE_ASSETS_AND_RELATIONS"
        ]
        self.assertTrue(catalog_items)
        self.assertTrue(
            all(item["stable_id"] != "SMIAL-PROJECT-ASSET-CATALOG" for item in catalog_items)
        )
        self.assertIn("CTRL-DELIVERY-HARNESS-001", {item["stable_id"] for item in catalog_items})

    def test_selected_entries_are_stable_bounded_references(self) -> None:
        receipt = self.receipt()
        keys = [
            (
                item["lane"],
                item["semantic_role"],
                item["stable_id"] or "",
                item["path"],
            )
            for item in receipt["selected"]
        ]
        self.assertEqual(keys, sorted(keys))
        for item in receipt["selected"]:
            self.assertFalse(Path(item["path"]).is_absolute())
            self.assertNotIn("content", item)
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
            self.assertIn(item["inclusion"], {"REFERENCE_ONLY", "METADATA_ONLY"})
        self.assertLessEqual(
            len(self.module.canonical_json_bytes(receipt)),
            receipt["budgets"]["ordinary_receipt_max_bytes"],
        )

    def test_exact_contract_is_required_and_unsafe_discovery_is_rejected(self) -> None:
        for value in ("", "../TASK.md", "C:/private/TASK.md", "latest", "newest"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "TASK_CONTRACT"):
                    self.module.build_context_receipt(
                        ROOT,
                        task_id=TASK_ID,
                        task_contract=value,
                        route="DIRECT_CODEX_DELIVERY",
                    )

    def test_missing_optional_owner_is_explicit_gap(self) -> None:
        receipt = self.receipt()
        deferred = {gap["semantic_role"] for gap in receipt["gaps"]}
        self.assertIn("HISTORICAL_CONTEXT", deferred)
        selected_roles = {item["semantic_role"] for item in receipt["selected"]}
        self.assertIn("ARCHITECTURE_DECISIONS", selected_roles)
        self.assertIn("DELIVERY_EVIDENCE", selected_roles)
        required = {"ARCHITECTURE_DECISIONS", "DELIVERY_EVIDENCE"}
        self.assertFalse(
            any(gap["semantic_role"] in required for gap in receipt["gaps"])
        )
        self.assertTrue(all(gap["state"] == "EXPLICIT_GAP" for gap in receipt["gaps"]))

    def test_required_role_without_exact_path_fails_closed(self) -> None:
        metadata = self.module.parse_task_contract(ROOT, TASK_CONTRACT, TASK_ID)
        metadata["context_requirements"]["exact_role_paths"][
            "ARCHITECTURE_DECISIONS"
        ] = []
        with self.assertRaisesRegex(
            ValueError, "REQUIRED_CONTEXT_REFERENCE_NOT_BOUND:ARCHITECTURE_DECISIONS"
        ):
            self.module.resolve_required_context(
                ROOT,
                metadata,
                self.module.load_closed_document(
                    ROOT / "delivery-harness/context-map.yaml",
                    ROOT / "catalog/schemas/delivery_harness_context_map.schema.json",
                ),
                max_inline_bytes=102400,
            )

    def test_cloud_source_history_cannot_be_relabelled_as_delivery_evidence(self) -> None:
        metadata = self.module.parse_task_contract(ROOT, TASK_CONTRACT, TASK_ID)
        metadata["context_requirements"]["exact_role_paths"][
            "DELIVERY_EVIDENCE"
        ] = ["docs/project_sources/release_registry_v1.yaml"]
        with self.assertRaisesRegex(ValueError, "SOURCE_HISTORY_ROLE_MISMATCH"):
            self.module.resolve_required_context(
                ROOT,
                metadata,
                self.module.load_closed_document(
                    ROOT / "delivery-harness/context-map.yaml",
                    ROOT / "catalog/schemas/delivery_harness_context_map.schema.json",
                ),
                max_inline_bytes=102400,
            )

    def test_dirty_state_is_reported_and_local_root_is_not_serialized(self) -> None:
        receipt = self.receipt()
        self.assertIsInstance(receipt["repository"]["dirty"], bool)
        serialized = self.module.canonical_json_bytes(receipt).decode("utf-8")
        self.assertNotIn(str(ROOT), serialized)
        username = os.environ.get("USERNAME", "__missing_username__")
        self.assertNotIn(f"C:/Users/{username}", serialized)
        self.assertNotIn(f"C:\\\\Users\\\\{username}", serialized)

    def test_default_build_writes_nothing_and_explicit_write_is_local_only(self) -> None:
        before = set((ROOT / "local").rglob("*")) if (ROOT / "local").exists() else set()
        receipt = self.receipt()
        after = set((ROOT / "local").rglob("*")) if (ROOT / "local").exists() else set()
        self.assertEqual(before, after)
        path = self.module.write_context_receipt(ROOT, receipt)
        try:
            self.assertTrue(path.is_file())
            self.assertEqual(
                path.parent.relative_to(ROOT).as_posix(),
                "local/delivery_harness/context",
            )
        finally:
            path.unlink(missing_ok=True)
            for parent in (path.parent, path.parent.parent, path.parent.parent.parent):
                try:
                    parent.rmdir()
                except OSError:
                    pass

    def test_large_file_is_never_inlined(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.bin"
            path.write_bytes(b"x" * (102400 + 1))
            item = self.module.reference_for_path(
                Path(directory),
                "large.bin",
                semantic_role="DELIVERY_EVIDENCE",
                lane="L2",
                truth_owner="FIXTURE",
                stable_id=None,
                max_inline_bytes=102400,
            )
            self.assertEqual(item["inclusion"], "REFERENCE_ONLY")
            self.assertNotIn("content", item)


if __name__ == "__main__":
    unittest.main()
