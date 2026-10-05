"""Prepared writer integrity, cold lookup, crash visibility and legacy rollback."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_research_store import event_fixture
from solana_alpha_lab.factory.research_store import ResearchStore, ResearchStoreError
from solana_alpha_lab.factory.research_write_lookup import RELATIVE, WriteLookup, WriteLookupError


class WriteLookupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "rdp"
        self.store = ResearchStore(self.root)
        self.store.prepare_write_lookup()

    def append(self, name="A", *, record_id=None):
        txn = f"RESEARCH-TXN-{name}"
        event = event_fixture(record_id=record_id or name, transaction_id=txn)
        return self.store.append([event], transaction_id=txn)

    def test_fresh_lookup_replay_conflict_and_global_record_identity(self):
        receipt = self.append()
        cold = ResearchStore(self.root)
        with patch.object(ResearchStore, "_committed_manifests", side_effect=AssertionError("FULL_SCAN")):
            self.assertEqual(cold.find_record("A").record_id, "A")
            self.assertIsNone(cold.find_record("ABSENT"))
            self.assertEqual(self.append().manifest, receipt.manifest)
            with self.assertRaisesRegex(ResearchStoreError, "DUPLICATE_RECORD_ID"):
                self.append("B", record_id="A")
        with self.assertRaisesRegex(ResearchStoreError, "TRANSACTION_CONFLICT"):
            self.store.append([event_fixture(record_id="A", payload={"changed": True},
                                            transaction_id="RESEARCH-TXN-A")], transaction_id="RESEARCH-TXN-A")

    def test_hit_verifies_canonical_parquet_bytes(self):
        receipt = self.append()
        path = self.root / receipt.manifest.logical_location
        raw = bytearray(path.read_bytes())
        raw[0] ^= 1
        path.write_bytes(raw)
        with self.assertRaisesRegex(ResearchStoreError, "COMMITTED_PARQUET"):
            self.store.find_record("A")

    def test_missing_and_corrupt_nodes_cannot_mean_absent(self):
        self.append()
        state = json.loads((self.root / RELATIVE / "state.json").read_bytes())
        sha = state["records"]
        node = self.root / RELATIVE / f"nodes/{sha[:2]}/{sha}.json"
        original = node.read_bytes()
        for raw in (None, b'{"leaf":{}}'):
            if raw is None:
                node.unlink()
            else:
                node.write_bytes(raw)
            with self.assertRaisesRegex(ResearchStoreError, "WRITE_LOOKUP_CORRUPT"):
                self.store.find_record("ABSENT")
            node.write_bytes(original)

    def test_manifest_last_reader_never_sees_pending_identity(self):
        original = WriteLookup.begin
        def fail_after_begin(lookup, *args):
            original(lookup, *args)
            raise RuntimeError("CRASH_BEFORE_MANIFEST")
        with patch.object(WriteLookup, "begin", fail_after_begin):
            with self.assertRaisesRegex(RuntimeError, "CRASH_BEFORE_MANIFEST"):
                self.append()
        self.assertEqual(list(self.store.iter_committed_records()), [])
        with self.assertRaisesRegex(ResearchStoreError, "WRITE_LOOKUP_PENDING"):
            self.store.find_record("A")
        self.append()
        self.assertEqual(len(list(self.store.iter_committed_records())), 1)

    def test_crash_after_manifest_before_stamp_requires_explicit_reconciliation(self):
        with patch.object(WriteLookup, "published", side_effect=RuntimeError("CRASH_AFTER_MANIFEST")):
            with self.assertRaisesRegex(RuntimeError, "CRASH_AFTER_MANIFEST"):
                self.append()
        self.assertEqual(len(list(self.store.iter_committed_records())), 1)
        with self.assertRaisesRegex(ResearchStoreError, "WRITE_LOOKUP_PENDING_RECONCILIATION_REQUIRED"):
            self.append()
        before = sorted(p.read_bytes() for p in (self.root / "research/manifests/partitions").glob("*.json"))
        self.store.prepare_write_lookup()
        self.append()
        self.assertEqual(before, sorted(p.read_bytes() for p in (self.root / "research/manifests/partitions").glob("*.json")))

    def test_crash_after_published_stamp_recovers_without_history_walk(self):
        with patch.object(WriteLookup, "finish", side_effect=RuntimeError("CRASH_AFTER_STAMP")):
            with self.assertRaisesRegex(RuntimeError, "CRASH_AFTER_STAMP"):
                self.append()
        with patch.object(ResearchStore, "_committed_manifests", side_effect=AssertionError("FULL_SCAN")):
            self.append()
        self.assertEqual(len(list(self.store.iter_committed_records())), 1)

    def test_legacy_writer_invalidates_without_breaking_old_readability(self):
        self.append()
        # The predecessor path remains unchanged and knows no derived artifact.
        with patch.object(ResearchStore, "_write_lookup", return_value=None):
            self.append("B")
        self.assertEqual(len(list(self.store.iter_committed_records())), 2)
        with self.assertRaisesRegex(ResearchStoreError, "WRITE_LOOKUP_STALE_PREPARATION_REQUIRED"):
            self.append("C")
        self.store.prepare_write_lookup()
        self.assertEqual(self.store.find_record("B").record_id, "B")

    def test_pending_canonical_source_unreadable_is_typed_and_preserved(self):
        with patch.object(WriteLookup, "finish", side_effect=RuntimeError("CRASH_AFTER_STAMP")):
            with self.assertRaisesRegex(RuntimeError, "CRASH_AFTER_STAMP"):
                self.append()
        pending = self.root / RELATIVE / "pending.json"
        saved = pending.read_bytes()
        manifest = next((self.root / "research/manifests/partitions").glob("*.json"))
        canonical = manifest.read_bytes()
        original_lstat = Path.lstat
        def denied(path, *args, **kwargs):
            if path == manifest:
                raise PermissionError("SYNTHETIC_PENDING_SOURCE_DENIED")
            return original_lstat(path, *args, **kwargs)
        with patch.object(Path, "lstat", denied):
            with self.assertRaisesRegex(ResearchStoreError, "WRITE_LOOKUP_SOURCE_UNREADABLE"):
                self.append()
        self.assertEqual(pending.read_bytes(), saved)
        self.assertEqual(manifest.read_bytes(), canonical)

    def test_missing_state_never_triggers_a_hidden_rebuild(self):
        self.append()
        (self.root / RELATIVE / "state.json").unlink()
        with self.assertRaisesRegex(ResearchStoreError, "WRITE_LOOKUP_CORRUPT"):
            self.append("B")

    def test_split_leaves_preserve_every_id_and_authenticated_absence(self):
        for index in range(40):
            self.append(f"ITEM-{index}")
        cold = ResearchStore(self.root)
        self.assertIsNone(cold.find_record("MISSING"))
        for index in range(40):
            self.assertEqual(cold.find_record(f"ITEM-{index}").record_id, f"ITEM-{index}")

    def test_malformed_signed_state_and_pending_are_typed_and_preserved(self):
        self.append()
        path = self.root / RELATIVE / "state.json"
        original = path.read_bytes()
        value = json.loads(original)
        value.pop("sha256")
        value.pop("transactions")
        path.write_bytes(json.dumps(WriteLookup(self.root, lambda *a, **k: None)._signed(value)).encode())
        with self.assertRaisesRegex(ResearchStoreError, "WRITE_LOOKUP_CORRUPT"):
            self.store.find_record("A")
        path.write_bytes(original)
        pending = self.root / RELATIVE / "pending.json"
        raw = json.dumps(WriteLookup(self.root, lambda *a, **k: None)._signed({"previous": {}, "next": {}})).encode()
        pending.write_bytes(raw)
        with self.assertRaisesRegex(ResearchStoreError, "WRITE_LOOKUP_CORRUPT"):
            self.append("B")
        self.assertEqual(pending.read_bytes(), raw)
        self.assertEqual(path.read_bytes(), original)

    def test_write_open_failure_is_typed(self):
        from solana_alpha_lab.factory.research_store import _target_path
        lookup = WriteLookup(self.root, _target_path)
        with patch("solana_alpha_lab.factory.research_write_lookup.os.open", side_effect=PermissionError()):
            with self.assertRaisesRegex(WriteLookupError, "WRITE_LOOKUP_WRITE_FAILED"):
                lookup._atomic("probe.json", {})

    def test_deep_json_and_unreadable_reused_node_are_typed_and_preserved(self):
        from solana_alpha_lab.factory.research_store import _target_path
        self.append()
        state = self.root / RELATIVE / "state.json"
        original = state.read_bytes()
        malformed = b'{"x":' + b'[' * 30000 + b'0' + b']' * 30000 + b'}'
        state.write_bytes(malformed)
        with self.assertRaisesRegex(ResearchStoreError, "WRITE_LOOKUP_CORRUPT"):
            self.store.find_record("ABSENT")
        self.assertEqual(state.read_bytes(), malformed)
        state.write_bytes(original)
        lookup = WriteLookup(self.root, _target_path)
        node = {"leaf": {}}
        lookup._save_node(node)
        original_open = Path.open
        def unreadable(path, *args, **kwargs):
            if "nodes" in path.parts and args and args[0] == "rb":
                raise PermissionError("SYNTHETIC_UNREADABLE_NODE")
            return original_open(path, *args, **kwargs)
        with patch.object(Path, "open", unreadable):
            with self.assertRaisesRegex(WriteLookupError, "WRITE_LOOKUP_CORRUPT"):
                lookup._save_node(node)

    def test_oversized_reused_node_is_refused_before_payload_read(self):
        from solana_alpha_lab.factory.research_store import _target_path
        from solana_alpha_lab.factory.research_write_lookup import MAX_NODE_BYTES
        lookup = WriteLookup(self.root, _target_path)
        sha = lookup._save_node({"leaf": {}})
        node = self.root / RELATIVE / f"nodes/{sha[:2]}/{sha}.json"
        node.write_bytes(b'x' * (MAX_NODE_BYTES + 1))
        with patch.object(Path, "open", side_effect=AssertionError("UNBOUNDED_READ")):
            with self.assertRaisesRegex(WriteLookupError, "WRITE_LOOKUP_CORRUPT"):
                lookup._save_node({"leaf": {}})

    def test_public_lookup_existence_and_preparation_initialization_are_typed(self):
        with patch.object(Path, "lstat", side_effect=PermissionError("SYNTHETIC_LOOKUP_STAT_DENIED")):
            with self.assertRaisesRegex(ResearchStoreError, "WRITE_LOOKUP_CORRUPT"):
                self.store.find_record("ABSENT")
        with patch.object(WriteLookup, "stamp", side_effect=WriteLookupError("WRITE_LOOKUP_SOURCE_UNREADABLE")):
            with self.assertRaisesRegex(ResearchStoreError, "WRITE_LOOKUP_SOURCE_UNREADABLE"):
                self.store.prepare_write_lookup()

    def test_preparation_cli_initialization_failure_is_json_refused(self):
        import io
        from contextlib import redirect_stdout
        from scripts.prepare_research_write_lookup import main
        output=io.StringIO()
        with patch("sys.argv", ["prepare_research_write_lookup.py", "--data-root", str(self.root.resolve()), "--isolated-copy"]):
            with patch.object(WriteLookup, "stamp", side_effect=WriteLookupError("WRITE_LOOKUP_SOURCE_UNREADABLE")):
                with redirect_stdout(output):
                    self.assertEqual(main(), 2)
        self.assertEqual(json.loads(output.getvalue()),
            {"status":"REFUSED", "reason":"WRITE_LOOKUP_SOURCE_UNREADABLE"})

    def test_preparation_cannot_bless_a_stale_packet_inventory(self):
        from solana_alpha_lab.factory.research_store import _lifecycle_read_cache
        self.append("A")
        old_inventory = self.store._committed_manifests()
        self.append("B")
        token = _lifecycle_read_cache.set({(str(self.root.resolve()), "manifests"): old_inventory})
        try:
            prepared = self.store.prepare_write_lookup()
            self.assertEqual(prepared["record_count"], 2)
            self.assertEqual(self.store.find_record("B").record_id, "B")
            with self.assertRaisesRegex(ResearchStoreError, "DUPLICATE_RECORD_ID"):
                self.append("C", record_id="B")
        finally:
            _lifecycle_read_cache.reset(token)

    def test_nested_state_tree_requires_identity_pointers(self):
        from solana_alpha_lab.factory.research_store import _target_path
        lookup = WriteLookup(self.root, _target_path)
        lookup.load()
        nested = lookup._save_node({"leaf": {"EVENT": {"root": None}}})
        lookup.state["states"] = lookup._save_node({"leaf": {"SCHEDULE": {"root": nested}}})
        lookup.save()
        with self.assertRaisesRegex(WriteLookupError, "WRITE_LOOKUP_CORRUPT"):
            lookup.state_pointers("SCHEDULE")


if __name__ == "__main__":
    unittest.main()
