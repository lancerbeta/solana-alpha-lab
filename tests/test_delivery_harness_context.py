from __future__ import annotations

import copy
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/delivery_harness.py"
RECEIPT_SCHEMA = ROOT / "catalog/schemas/delivery_harness_context_receipt.schema.json"
TASK_CONTRACT = "docs/superpowers/specs/2026-08-13-delivery-harness-design.md"
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
        self.assertIn("DELIVERY_EVIDENCE", deferred)
        self.assertTrue(all(gap["state"] == "EXPLICIT_GAP" for gap in receipt["gaps"]))

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
