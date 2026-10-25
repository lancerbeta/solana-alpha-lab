"""PRD wire oracle + actual Git races. No native store, provider or science calls."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from solana_alpha_lab.factory import research_shelf as shelf
from solana_alpha_lab.factory.research_shelf_git import BRANCH, ShelfGit

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/research_shelf_v1/genesis.json"
NOW = "2026-10-24T00:00:00Z"


def genesis(**changes):
    body = json.loads(FIXTURE.read_bytes())
    body.pop("revision_sha256")
    body.update(changes)
    return shelf.prepare(body)


def files(*revisions):
    return {shelf.revision_path(shelf.decode(raw)): raw for raw in revisions}


def publish(git, *revisions):
    return git.publish(files(*revisions), expected_heads={
        shelf.decode(raw)["item_id"]: shelf.decode(raw)["parents"] for raw in revisions})


def update(snapshot, item, **changes):
    return shelf.revise(snapshot, item, dict(changes, change_reason="Substantive synthetic review."),
                        now="2026-10-25T00:00:00Z", mutation_id=str(uuid4()))


class WireTests(unittest.TestCase):
    def test_shared_opaque_mutation_and_native_uri_vertical(self):
        fixture = json.loads((FIXTURE.parent / "compatibility.json").read_bytes())
        revisions = []
        for row in fixture["revisions"]:
            raw = row["raw"].encode("utf-8")
            body = shelf.decode(raw)
            self.assertEqual(shelf.sha256(raw), row["file_sha256"])
            self.assertEqual(body["mutation_id"], row["mutation_id"])
            self.assertEqual(shelf.prepare(body), raw)
            revisions.append(raw)
        snapshot = shelf.fold(files(*revisions))
        self.assertTrue(snapshot["identity_scope_complete"])
        self.assertEqual({r["status"] for r in snapshot["items"].values()}, {"READY"})
        self.assertEqual(shelf.attention(snapshot, now=NOW)["totals"], {"WAITING": 2})
        for invalid in ("", " \t", None, 1):
            with self.subTest(invalid_type=type(invalid).__name__):
                with self.assertRaises(shelf.ShelfError):
                    genesis(mutation_id=invalid)
        # Exact-string reservations also apply when the old body is invalid.
        first = shelf.decode(revisions[0])
        invalid = shelf.canonical(dict(first, title=17)) + b"\n"
        other = genesis(item_id="RSI-SCOUT-00000000-0000-4000-8000-000000000099",
                        mutation_id=first["mutation_id"])
        conflict = shelf.fold({shelf.revision_path(first): invalid} | files(other))
        self.assertTrue(conflict["identity_scope_complete"])
        self.assertTrue(all("MUTATION_ID_CONFLICT" in r["reasons"] for r in conflict["items"].values()))

    def test_prd_independent_hash_oracle(self):
        raw = FIXTURE.read_bytes()
        body = shelf.decode(raw)
        self.assertEqual(body["revision_sha256"], "264ecdb2f41c005e7766dc065ae52d2c845e338beb07418607e33f24bb168465")
        self.assertEqual(shelf.sha256(raw), "dd7dde379c136e401e2647a6e1f022f689e14c0d18036bd8a98a38c7d82224e9")
        self.assertEqual(shelf.prepare(body), raw)

    def test_canonical_privacy_schema_and_resource_guards(self):
        body = json.loads(FIXTURE.read_bytes())
        for name, changes, code in [
            ("version", {"schema_version": "2.0"}, "UNSUPPORTED_WIRE_VERSION"),
            ("extra", {"unexpected": "preserve or refuse"}, "WIRE_SCHEMA_INVALID"),
            ("local path", {"statement": "Private C:" + "\\Users\\person\\data"}, "PHYSICAL_PATH_REFUSED"),
            ("private body", {"statement": ("g" + "hp_") + "A" * 36}, "SECRET_REFUSED"),
            ("clock", {"updated_at": "2026-10-24T03:00:00+03:00"}, "WIRE_SCHEMA_INVALID"),
            ("missing closure", {"state": "CLOSED"}, "WIRE_SCHEMA_INVALID"),
            ("oversize", {"statement": "A" * shelf.MAX_REVISION_BYTES}, "REVISION_SIZE_LIMIT"),
        ]:
            with self.subTest(name=name):
                candidate = dict(body, **changes)
                candidate.pop("revision_sha256")
                with self.assertRaisesRegex(shelf.ShelfError, code):
                    shelf.prepare(candidate)
        for raw in (FIXTURE.read_bytes().replace(b'"1.0"', b'"1.1"'), b"\xef\xbb\xbf" + FIXTURE.read_bytes(),
                    json.dumps(body).encode(), FIXTURE.read_bytes() + b"\n"):
            with self.assertRaises(shelf.ShelfError):
                shelf.decode(raw)
        with self.assertRaisesRegex(shelf.ShelfError, "WIRE_JSON_INVALID"):
            shelf.prepare(dict(body, not_a_number=float("nan")))

    def test_capture_incomplete_thought_has_no_fabricated_evidence(self):
        body = shelf.decode(shelf.capture(product="SMIAL", title="Вопрос", statement="Непроверенная идея", now=NOW))
        self.assertEqual(body["origin_refs"], [])
        self.assertEqual(body["native_links"], [])
        self.assertIsNone(body["next_action"])
        snapshot = shelf.fold(files(shelf.canonical(body) + b"\n"))
        self.assertEqual(shelf.attention(snapshot, now=NOW)["totals"], {"NEEDS_TRIAGE": 1})

    def test_logical_https_and_native_refs_are_not_windows_paths(self):
        refs = [dict(kind="REFERENCE", locator="https://example.invalid/home/research", description="Source hint",
                     observed_at=NOW, verification="UNVERIFIED"),
                dict(kind="NATIVE", owner="SMIAL", entity_kind="FRAGMENT", entity_id="RFV-SYNTHETIC",
                     payload_sha256=None, locator="smial-data://research/var/result")]
        self.assertEqual(shelf.decode(genesis(origin_refs=refs))["origin_refs"], refs)

    def test_local_path_checks_root_first_before_visiting_any_link_descendant(self):
        from solana_alpha_lab.factory.research_shelf_git import _local_path
        alias = ROOT / "local" / "synthetic-network-alias"
        leaf = alias / "child" / "remote.git"
        visited = []
        def inspect(path):
            visited.append(path)
            if alias in path.parents:
                raise AssertionError("Attempted descendant I/O before detecting indirect ancestor")
            return path == alias
        with patch.object(Path, "is_symlink", new=inspect), patch.object(Path, "is_junction", return_value=False):
            with patch.object(Path, "resolve", side_effect=AssertionError("Link must be refused before resolution")):
                with self.assertRaisesRegex(shelf.ShelfError, "INDIRECT_PATH_REFUSED"):
                    _local_path(leaf)
        self.assertEqual(visited[-1], alias)
        self.assertNotIn(leaf, visited)

    def test_invalid_nested_clock_is_isolated_at_validation(self):
        body = json.loads(FIXTURE.read_bytes())
        body.pop("revision_sha256")
        body["review"]["review_at"] = "2026-13-31T00:00:00Z"
        with self.assertRaisesRegex(shelf.ShelfError, "UTC_CLOCK_INVALID"):
            shelf.prepare(body)
        body["revision_sha256"] = shelf.sha256(shelf.canonical(body))
        bad = shelf.canonical(body) + b"\n"
        good = shelf.capture(product="SMIAL", title="Independent", statement="Unmeasured", now=NOW)
        snapshot = shelf.fold({shelf.revision_path(body): bad} | files(good))
        self.assertEqual(shelf.attention(snapshot, now=NOW)["totals"], {"ITEM_INVALID": 1, "NEEDS_TRIAGE": 1})

    def test_invalid_change_reason_has_safe_typed_refusal(self):
        snapshot = shelf.fold(files(FIXTURE.read_bytes()))
        item = next(iter(snapshot["items"]))
        for reason in (None, 7, [], {}, " "):
            with self.subTest(reason_type=type(reason).__name__):
                with self.assertRaisesRegex(shelf.ShelfError, "CHANGE_REASON_REQUIRED"):
                    shelf.revise(snapshot, item, dict(change_reason=reason), now=NOW, mutation_id=str(uuid4()))

    def test_missing_parent_and_invalid_item_do_not_hide_independent_item(self):
        bad = genesis(parents=["a" * 64])
        good = shelf.capture(product="SMIAL", title="Independent", statement="Idea", now=NOW)
        snapshot = shelf.fold(files(bad, good))
        self.assertEqual(snapshot["items"][shelf.decode(bad)["item_id"]]["status"], "ITEM_INVALID")
        self.assertEqual(snapshot["items"][shelf.decode(good)["item_id"]]["status"], "READY")
        result = shelf.attention(snapshot, now=NOW)
        self.assertEqual(result["totals"], {"ITEM_INVALID": 1, "NEEDS_TRIAGE": 1})

    def test_unknown_wire_is_item_invalid_and_incomplete_never_empty_ready(self):
        raw = FIXTURE.read_bytes().replace(b'"1.0"', b'"2.0"')
        snapshot = shelf.fold({shelf.revision_path(json.loads(FIXTURE.read_bytes())): raw}, complete=False)
        self.assertEqual(snapshot["status"], "INCOMPLETE")
        self.assertIn("UNSUPPORTED_WIRE_VERSION", next(iter(snapshot["items"].values()))["reasons"])

    def test_utc_attention_boundaries_manual_and_unknown(self):
        # Hand table, independent of the projection implementation.
        raw = genesis(review={"review_at": "2026-10-31T00:00:00Z", "review_by": "2026-11-02T00:00:00Z", "event": None})
        snapshot = shelf.fold(files(raw))
        for now, status in [("2026-10-30T23:59:59Z", "WAITING"), ("2026-10-31T00:00:00Z", "DUE_REVIEW"),
                            ("2026-11-02T00:00:00Z", "OVERDUE_REVIEW")]:
            self.assertEqual(shelf.attention(snapshot, now=now)["items"][0]["status"], status)
        self.assertEqual(shelf.attention(shelf.fold(files(FIXTURE.read_bytes())), now=NOW)["items"][0]["status"], "WAITING")
        event = {"kind": "NATIVE_STATUS", "source": None, "condition": "READY", "acknowledged_ref": None}
        unknown = genesis(review={"review_at": None, "review_by": None, "event": event})
        row = shelf.attention(shelf.fold(files(unknown)), now=NOW)["items"][0]
        self.assertEqual((row["status"], row["source_status"]), ("SOURCE_READBACK_REQUIRED", "UNKNOWN"))
        late = genesis(review={"review_at": "2026-12-01T00:00:00Z", "review_by": "2026-10-24T00:00:00Z", "event": event})
        self.assertEqual(shelf.attention(shelf.fold(files(late)), now=NOW)["items"][0]["status"], "OVERDUE_REVIEW")
        manual = dict(kind="MANUAL", source=None, condition="Owner review required", acknowledged_ref=None)
        last_date_only = genesis(review={"review_at": None, "review_by": "2026-11-20T00:00:00Z", "event": manual})
        self.assertEqual(shelf.attention(shelf.fold(files(last_date_only)), now=NOW)["totals"], {"NEEDS_TRIAGE": 1})
        self.assertEqual(shelf.attention(shelf.fold(files(last_date_only)), now="2026-11-20T00:00:00Z")["totals"], {"OVERDUE_REVIEW": 1})

    def test_fold_fork_reconcile_all_parents_and_preserve_old_content(self):
        raw = FIXTURE.read_bytes()
        item = shelf.decode(raw)["item_id"]
        initial = shelf.fold(files(raw))
        left = update(initial, item, statement="Left semantic answer.")
        right = update(initial, item, statement="Right semantic answer.")
        fork = shelf.fold(files(raw, left, right))
        self.assertEqual(fork["items"][item]["status"], "ITEM_CONFLICT")
        self.assertIsNone(fork["items"][item]["current"])
        with self.assertRaisesRegex(shelf.ShelfError, "ITEM_NOT_WRITABLE"):
            update(fork, item, title="Do not select a winner")
        editable = {k: v for k, v in shelf.decode(left).items() if k not in
                    {*shelf.IDENTITY, "schema_version", "revision_sha256", "parents", "mutation_id", "updated_at"}}
        editable["change_reason"] = "Owner selected the left formulation; keep both histories."
        merged = shelf.revise(fork, item, editable, now="2026-10-26T00:00:00Z", mutation_id=str(uuid4()), reconcile=True)
        result = shelf.fold(files(raw, left, right, merged))["items"][item]
        self.assertEqual(result["status"], "READY")
        self.assertEqual(len(result["revisions"]), 4)
        self.assertEqual(shelf.decode(merged)["parents"], sorted([shelf.decode(left)["revision_sha256"], shelf.decode(right)["revision_sha256"]]))
        self.assertEqual(result["revisions"][shelf.decode(raw)["revision_sha256"]]["statement"], shelf.decode(raw)["statement"])

    def test_identity_mutation_and_origin_conflicts_include_closed_history(self):
        raw = genesis(origin_key="native/exact/follow-up")
        item = shelf.decode(raw)["item_id"]
        snapshot = shelf.fold(files(raw))
        with self.assertRaisesRegex(shelf.ShelfError, "IMMUTABLE_OR_TOOL_FIELD_UPDATE"):
            update(snapshot, item, origin_key="changed")
        closed = update(snapshot, item, state="CLOSED", closure={"reason": "ADMIN_CANCELLED", "evidence_refs": [], "successor": None})
        other = genesis(item_id=f"RSI-SCOUT-{uuid4()}", mutation_id=str(uuid4()), origin_key="native/exact/follow-up")
        result = shelf.fold(files(raw, closed, other))
        self.assertTrue(all(r["status"] == "ITEM_CONFLICT" for r in result["items"].values()))
        changed = json.loads(raw)
        changed.pop("revision_sha256")
        changed.update(parents=[shelf.decode(raw)["revision_sha256"]], title="Conflicting mutation bytes")
        result = shelf.fold(files(raw, shelf.prepare(changed)))
        self.assertIn("MUTATION_ID_CONFLICT", result["items"][item]["reasons"])

    def test_summary_counts_omissions_and_closed(self):
        revisions = [shelf.capture(product="SMIAL", title=f"Idea {i}", statement="No measurement", now=NOW) for i in range(7)]
        snapshot = shelf.fold(files(*revisions))
        result = shelf.attention(snapshot, now=NOW)
        self.assertEqual((len(result["items"]), result["omitted_count"], result["totals"]), (5, 2, {"NEEDS_TRIAGE": 7}))
        self.assertEqual(len(shelf.attention(snapshot, now=NOW, limit=None)["items"]), 7)
        item = shelf.decode(revisions[0])["item_id"]
        closed = update(snapshot, item, state="CLOSED", closure={"reason": "Administrative", "evidence_refs": [], "successor": None})
        result = shelf.attention(shelf.fold(files(*revisions, closed)), now=NOW)
        self.assertEqual(result["totals"], {"CLOSED": 1, "NEEDS_TRIAGE": 6})

    def test_attention_keeps_snapshot_pin_completeness_and_stale_reason(self):
        snapshot = shelf.fold(files(FIXTURE.read_bytes()))
        snapshot.update(commit="a" * 40, status="STALE_AS_OF", complete=False,
                        source_freshness="STALE_AS_OF", reason="GIT_UNAVAILABLE")
        result = shelf.attention(snapshot, now=NOW)
        self.assertEqual(result["snapshot_commit"], "a" * 40)
        self.assertFalse(result["snapshot_complete"])
        self.assertEqual(result["source_freshness"], "STALE_AS_OF")
        self.assertEqual(result["reason"], "GIT_UNAVAILABLE")
        self.assertEqual(result["attention_as_of"], NOW)


class GitVerticalTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "local").mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="research-shelf-", dir=ROOT / "local")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.remote = self.root / "remote.git"
        ShelfGit._run(None, "init", "--bare", "--quiet", str(self.remote))
        self.a = ShelfGit.init_local(self.root / "a.git", self.remote)
        self.b = ShelfGit.init_local(self.root / "b.git", self.remote)
        self.raw = FIXTURE.read_bytes()
        self.item = shelf.decode(self.raw)["item_id"]

    def test_invalid_history_keeps_identity_reservations_and_exact_retry(self):
        from uuid import uuid4
        original = json.loads(genesis(origin_key="reserved-invalid-history", mutation_id="synthetic:opaque:reserved"))
        bad = dict(original, title=17)  # Invalid body, readable negative identity claims.
        bad_raw = shelf.canonical(bad) + b"\n"
        head = self.a._commit(None, {shelf.revision_path(original): bad_raw})
        self.assertEqual(self.a._push(head).returncode, 0)
        self.assertEqual(self.a.refresh()["items"][self.item]["status"], "ITEM_INVALID")
        for changes in (dict(origin_key=original["origin_key"], mutation_id=str(uuid4())),
                        dict(origin_key=None, mutation_id=original["mutation_id"])):
            new = genesis(item_id="RSI-SCOUT-" + str(uuid4()), **changes)
            with self.subTest(reservation=changes):
                with self.assertRaisesRegex(shelf.ShelfError, "BATCH_LINEAGE_INVALID"):
                    publish(self.a, new)
                self.assertEqual(self.a.remote_head(), head)
        independent = genesis(item_id="RSI-SCOUT-" + str(uuid4()), mutation_id=str(uuid4()), origin_key="independent")
        landed = publish(self.a, independent)
        self.assertEqual(landed["status"], "PUBLISHED")
        # Unparseable bytes leave the reservation domain unknown, not empty.
        unknown_item = "RSI-SCOUT-" + str(uuid4())
        unknown = self.a._commit(landed["commit"], {f"{shelf.PREFIX}/{unknown_item}/{'f'*64}.json": b"not-json"})
        self.assertEqual(self.a._push(unknown).returncode, 0)
        self.assertEqual(publish(self.a, independent)["status"], "ALREADY_PUBLISHED")
        with self.assertRaisesRegex(shelf.ShelfError, "IDENTITY_HISTORY_UNRESOLVED"):
            publish(self.a, genesis(item_id="RSI-SCOUT-" + str(uuid4()), mutation_id=str(uuid4())))

    def test_public_writer_keeps_private_origin_after_metadata_removes_refs(self):
        from solana_alpha_lab.factory import research_shelf_context as context
        from solana_alpha_lab.factory.research_shelf_git import ScopedShelfGit
        from uuid import uuid4
        class LocalScoped(ScopedShelfGit):
            # Exercise the production guard/CAS on a disposable local remote.
            # Code acceptance and network gates are tested separately; no network.
            def __init__(self, cache):
                self.scope = {}
                ShelfGit.__init__(self, cache)
            def _accepted_policy(self, action):
                pass
            def _local_remote(self):
                return ShelfGit._local_remote(self)
        writer = LocalScoped(self.a.cache)
        body = shelf.decode(self.raw)
        body.pop("revision_sha256")
        body.update(product="SMIAL", item_id=body["item_id"].replace("SCOUT", "SMIAL"),
            origin_refs=[dict(kind="GIT", repository="lancerbeta/marcopolo-scout", commit="a"*40, path="saved/source.json", sha256="b"*64)])
        first = shelf.prepare(body)
        def approval(raw):
            digest = shelf.sha256(shelf.canonical(shelf.decode(raw)))
            return {digest: dict(disposition="EXPLICIT_MINIMAL_PUBLIC_DISCLOSURE", payload_sha256=digest)}
        first_body = shelf.decode(first)
        result = writer.publish(files(first), expected_heads={first_body["item_id"]: []}, disclosures=approval(first))
        state = writer.read(result["commit"])
        stripped = shelf.revise(state, first_body["item_id"], dict(origin_refs=[], statement="PRIVATE_SENTINEL",
            change_reason="Ordinary edit cannot declassify history."), now=NOW, mutation_id=str(uuid4()))
        with self.assertRaisesRegex(shelf.ShelfError, "PRIVATE_SOURCE_PUBLIC_DISCLOSURE_REQUIRED"):
            publish(writer, stripped)
        self.assertEqual(writer.remote_head(), result["commit"])
        clean = shelf.revise(state, first_body["item_id"], dict(origin_refs=[], statement="Minimal approved public wording.",
            change_reason="Explicit minimal public payload review, no declassification."), now=NOW, mutation_id=str(uuid4()))
        body = shelf.decode(clean)
        confirmed = writer.publish(files(clean), expected_heads={body["item_id"]: body["parents"]}, disclosures=approval(clean))
        self.assertEqual(confirmed["status"], "PUBLISHED")
        self.assertTrue(context.historically_private(writer.read(confirmed["commit"]), body["item_id"]))
        context.public_payload_guard(dict(statement="Independent public SMIAL text"))

    def test_capture_git_cold_read_and_no_code_checkout_effects(self):
        before = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True, check=True).stdout
        self.assertEqual(self.a.refresh()["status"], "NOT_INITIALIZED")
        receipt = publish(self.a, self.raw)
        self.assertEqual(receipt["status"], "PUBLISHED")
        cold = self.b.refresh()
        self.assertEqual(cold["commit"], receipt["commit"])
        self.assertEqual(cold["files"], files(self.raw))
        cache_refs = self.b._git("show-ref").stdout
        objects = self.b._git("count-objects", "-v").stdout
        with patch.object(self.b, "remote_head", side_effect=AssertionError("read must not fetch")):
            self.assertEqual(shelf.attention(self.b.read(receipt["commit"]), now="2026-10-31T00:00:00Z")["totals"], {"DUE_REVIEW": 1})
        self.assertEqual(self.b._git("show-ref").stdout, cache_refs)
        self.assertEqual(self.b._git("count-objects", "-v").stdout, objects)
        after = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True, check=True).stdout
        self.assertEqual(before, after)

    def test_two_real_writers_different_items_retry_without_loss(self):
        # Force both writers to commit from the same real branch head before pushing.
        publish(self.a, self.raw)
        barrier = threading.Barrier(2)
        for git in (self.a, self.b):
            original = git._push
            calls = [0]
            def racing(commit, original=original, calls=calls):
                calls[0] += 1
                if calls[0] == 1:
                    barrier.wait(timeout=15)
                return original(commit)
            git._push = racing
        left = shelf.capture(product="SMIAL", title="Left", statement="Independent", now=NOW)
        right = shelf.capture(product="SMIAL", title="Right", statement="Independent", now=NOW)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda pair: publish(*pair), [(self.a, left), (self.b, right)]))
        self.assertEqual({r["status"] for r in results}, {"PUBLISHED"})
        self.assertEqual(sorted(r["retries"] for r in results), [0, 1])
        snapshot = self.a.refresh()
        self.assertEqual(len(snapshot["items"]), 3)
        self.assertEqual(set(snapshot["files"]), set(files(self.raw, left, right)))

    def test_same_item_concurrent_write_refuses_stale_and_keeps_draft(self):
        publish(self.a, self.raw)
        snapshot = self.b.refresh()
        left, right = update(snapshot, self.item, title="Left"), update(snapshot, self.item, title="Right")
        barrier = threading.Barrier(2)
        original_a, original_b = self.a._push, self.b._push
        def a_push(commit):
            result = original_a(commit)
            barrier.wait(timeout=15)
            return result
        def b_push(commit):
            barrier.wait(timeout=15)
            return original_b(commit)
        self.a._push, self.b._push = a_push, b_push
        with ThreadPoolExecutor(max_workers=2) as pool:
            future = pool.submit(publish, self.a, left)
            with self.assertRaisesRegex(shelf.ShelfError, "STALE_ITEM_REVISION"):
                publish(self.b, right)
            self.assertEqual(future.result()["status"], "PUBLISHED")
        self.assertEqual(shelf.decode(right)["title"], "Right")
        self.assertEqual(self.a.refresh()["items"][self.item]["current"]["title"], "Left")

    def test_lost_push_reply_and_historical_retry_do_not_duplicate(self):
        original = self.a._push
        def lost_reply(commit):
            self.assertEqual(original(commit).returncode, 0)
            raise shelf.ShelfError("GIT_TIMEOUT", "push")
        with patch.object(self.a, "_push", side_effect=lost_reply):
            result = publish(self.a, self.raw)
        self.assertEqual(result["status"], "ALREADY_PUBLISHED")
        snapshot = self.a.refresh()
        revised = update(snapshot, self.item, title="After original reply")
        publish(self.a, revised)
        head = self.a.remote_head()
        self.assertEqual(publish(self.b, self.raw)["status"], "ALREADY_PUBLISHED")
        self.assertEqual(self.a.remote_head(), head)
        self.assertEqual(len(self.a.refresh()["files"]), 2)

    def test_new_origin_is_rechecked_after_competing_genesis_and_close(self):
        raw = genesis(origin_key="source/follow-up")
        publish(self.a, raw)
        closed = update(self.a.refresh(), self.item, state="CLOSED",
            closure={"reason": "HANDED_OFF", "evidence_refs": [], "successor": None})
        publish(self.a, closed)
        duplicate = genesis(item_id=f"RSI-SCOUT-{uuid4()}", mutation_id=str(uuid4()), origin_key="source/follow-up")
        with self.assertRaisesRegex(shelf.ShelfError, "ORIGIN_ALREADY_EXISTS"):
            publish(self.b, duplicate)
        self.assertEqual(len(self.a.refresh()["items"]), 1)

    def test_publication_failure_and_uncertain_readback_preserve_prepared(self):
        with patch.object(self.a, "_push", side_effect=shelf.ShelfError("GIT_TIMEOUT", "push")):
            self.assertEqual(publish(self.a, self.raw)["status"], "PENDING_PUBLICATION")
        with patch.object(self.a, "_push", return_value=subprocess.CompletedProcess([], 1, b"", b"denied")):
            with self.assertRaisesRegex(shelf.ShelfError, "PUBLICATION_FAILED"):
                publish(self.a, self.raw)
        self.assertEqual(shelf.decode(self.raw)["mutation_id"], "00000000-0000-4000-8000-000000000002")

    def test_offline_stale_and_limited_listing_not_empty(self):
        receipt = publish(self.a, self.raw)
        self.a.refresh()
        with patch.object(self.a, "remote_head", side_effect=shelf.ShelfError("GIT_UNAVAILABLE")):
            snapshot = self.a.refresh()
        self.assertEqual((snapshot["status"], snapshot["commit"], snapshot["complete"]), ("STALE_AS_OF", receipt["commit"], False))
        self.assertEqual(len(snapshot["items"]), 1)
        self.assertEqual(self.a.read(receipt["commit"], max_bytes=1)["status"], "INCOMPLETE")
        with self.assertRaisesRegex(shelf.ShelfError, "EXACT_COMMIT_REQUIRED"):
            self.a.read("research-log")

    def test_network_and_code_checkout_are_outside_stage_one(self):
        self.a._git("remote", "set-url", "origin", "https://example.invalid/repository.git")
        with self.assertRaisesRegex(shelf.ShelfError, "NETWORK_TRANSPORT_NOT_COMMISSIONED"):
            publish(self.a, self.raw)
        with self.assertRaisesRegex(shelf.ShelfError, "BARE_CACHE_REQUIRED"):
            ShelfGit(ROOT)

    def test_unc_is_refused_before_any_filesystem_resolution(self):
        for remote in (Path(r"\\server\share\remote.git"), Path("//server/share/remote.git"), Path(r"\\?\UNC\server\share\remote.git")):
            with self.subTest(remote_form=str(remote)[:8]):
                with patch.object(Path, "resolve", side_effect=AssertionError("Must refuse before filesystem I/O")):
                    with self.assertRaisesRegex(shelf.ShelfError, "NETWORK_PATH_REFUSED"):
                        ShelfGit.init_local(self.root / "new-cache.git", remote)
        if os.name == "nt":
            with patch("solana_alpha_lab.factory.research_shelf_git._drive_type", return_value=4):
                with patch.object(Path, "resolve", side_effect=AssertionError("Mapped drive must be refused before resolution")):
                    with self.assertRaisesRegex(shelf.ShelfError, "NETWORK_PATH_REFUSED"):
                        ShelfGit.init_local(self.root / "new-cache.git", Path("Z:/remote.git"))

    def test_cli_prepare_apply_pinned_review_and_truthful_draft_receipt(self):
        request = self.root / "request.json"
        request.write_text(json.dumps(dict(title="Отложенный вопрос", statement="Без измерения")), encoding="utf-8")
        prepared = self.root / "draft.json"
        def cli(*args):
            result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/research_shelf.py"), *map(str, args)],
                                    cwd=self.root, capture_output=True, text=True, encoding="utf-8", check=True)
            return json.loads(result.stdout)
        result = cli("capture", "--input", request, "--output", prepared, "--now", NOW)
        self.assertEqual((result["status"], result["saved_in_git"]), ("PREPARED_LOCAL_ONLY", False))
        result = cli("apply", "--cache", self.a.cache, "--input", prepared)
        self.assertEqual(result["status"], "PUBLISHED")
        review = cli("review", "--cache", self.a.cache, "--commit", result["commit"], "--now", NOW)
        self.assertEqual(review["totals"], {"NEEDS_TRIAGE": 1})
        self.assertEqual(review["scientific_admission"], "NOT_EVALUATED")

    def test_cli_conflict_exposes_both_formulations_and_exact_revision(self):
        publish(self.a, self.raw)
        snapshot = self.a.refresh()
        left, right = update(snapshot, self.item, title="Left"), update(snapshot, self.item, title="Right")
        publish(self.a, left)
        injected = self.a._commit(self.a.remote_head(), files(right))
        self.assertEqual(self.a._push(injected).returncode, 0)
        commit = self.a.remote_head()
        command = [sys.executable, "-B", str(ROOT / "scripts/research_shelf.py"), "show", "--cache", str(self.a.cache),
                   "--commit", commit, "--item", self.item]
        result = subprocess.run(command, capture_output=True, check=False)
        shown = json.loads(result.stdout)
        self.assertEqual(result.returncode, 2)
        self.assertEqual({r["title"] for r in shown["competing_revisions"].values()}, {"Left", "Right"})
        selected = subprocess.run(command + ["--revision", shelf.decode(left)["revision_sha256"]], capture_output=True, check=True)
        self.assertEqual(json.loads(selected.stdout)["revision"]["title"], "Left")
        fork = self.a.read(commit)
        editable = {k: v for k, v in shelf.decode(left).items() if k not in
                    {*shelf.IDENTITY, "schema_version", "revision_sha256", "parents", "mutation_id", "updated_at"}}
        editable["change_reason"] = "Explicit choice after reading both competing versions."
        merged = shelf.revise(fork, self.item, editable, now="2026-10-26T00:00:00Z", mutation_id=str(uuid4()), reconcile=True)
        publish(self.a, merged)
        final = self.a.refresh()["items"][self.item]
        self.assertEqual((final["status"], len(final["revisions"])), ("READY", 4))


if __name__ == "__main__":
    unittest.main()
