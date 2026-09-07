"""OWNER_ATTENTION_AND_CHANGE_FEED_V1 vertical acceptance."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.application import ApplicationError, FactoryApplication  # noqa: E402
from solana_alpha_lab.factory.operational_store import OperationalStore  # noqa: E402
from solana_alpha_lab.factory.owner_daily_attention import (  # noqa: E402
    CHANGE_FEED_LIMIT,
    compose_owner_attention,
    persistable_watermarks,
)
from solana_alpha_lab.factory.owner_language import SURFACE_COPY  # noqa: E402
from solana_alpha_lab.factory.owner_review_cursor import (  # noqa: E402
    cursor_path,
    load_cursor,
    persist_cursor,
)
from solana_alpha_lab.factory.runtime import copy_rehost_allowlist, load_runtime_config  # noqa: E402
from solana_alpha_lab.factory.workbench import COMMANDS, _page, serve  # noqa: E402
from solana_alpha_lab.factory_semantic_operability import (  # noqa: E402
    load_semantic_catalog_views,
    load_semantic_projection,
    search_semantic_routes,
)

GET_PATHS = ("/", "/research", "/operations", "/economics", "/system")


def isolated_factory_root(tmp: Path) -> Path:
    config = load_runtime_config(ROOT)
    copy_rehost_allowlist(
        src_root=ROOT,
        dst_root=tmp,
        relatives=list(config["rehost_relative_paths"]),
    )
    return tmp


def _walk_relatives(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _get(app: FactoryApplication, path: str) -> str:
    server = serve(app, host="127.0.0.1", port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("GET", path)
        response = conn.getresponse()
        body = response.read().decode("utf-8")
        conn.close()
        assert response.status == 200, body
        return body
    finally:
        server.shutdown()
        server.server_close()


def _post(app: FactoryApplication, path: str, fields: dict[str, str]) -> str:
    server = serve(app, host="127.0.0.1", port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        body = urlencode(fields)
        conn = HTTPConnection(host, port, timeout=5)
        conn.request(
            "POST",
            path,
            body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = conn.getresponse()
        text = response.read().decode("utf-8")
        conn.close()
        assert response.status == 200, text
        return text
    finally:
        server.shutdown()
        server.server_close()


def _ops_attention(code: str, identity: str = "POS-1") -> dict[str, str]:
    return {
        "code": code,
        "source_native_identity": identity,
        "WHY_NOW": code,
        "IMPACT": "risk",
        "EVIDENCE": identity,
        "NEXT_SAFE_ACTION": "OPEN_OPERATIONS",
    }


class OwnerAttentionAndChangeFeedV1Tests(unittest.TestCase):
    def test_runtime_attention_is_not_global_spam(self) -> None:
        projection = compose_owner_attention(
            cockpit={
                "attention": [
                    {
                        "id": "RUNTIME_ATTENTION",
                        "WHY_NOW": "verdict",
                        "IMPACT": "process",
                        "EVIDENCE": "RUNTIME_PROVED_BACKUP_UNKNOWN",
                        "NEXT_SAFE_ACTION": "INSPECT_SYSTEM",
                    }
                ]
            },
            runtime={"verdict": "RUNTIME_PROVED_BACKUP_UNKNOWN"},
        )
        self.assertEqual(projection["current_attention"], [])
        self.assertFalse(projection["healthy_claim"])
        projection = compose_owner_attention(
            trading={
                "source_status": "PRESENT",
                "attention": [_ops_attention("UNRESOLVED_POSITION")],
                "recent_changes": [],
            }
        )
        item = projection["current_attention"][0]
        self.assertEqual(item["priority"], "P0")
        self.assertEqual(item["drilldown_target"], "/operations")
        self.assertEqual(item["attention_code"], "UNRESOLVED_POSITION")

    def test_a2_unavailable_source_is_p1(self) -> None:
        projection = compose_owner_attention(
            trading={
                "source_status": "UNAVAILABLE",
                "attention": [_ops_attention("RUNTIME_SOURCE_UNAVAILABLE", "STORE")],
            }
        )
        self.assertEqual(projection["current_attention"][0]["priority"], "P1")
        self.assertEqual(projection["coverage"][1]["CURRENT_STATE"], "UNAVAILABLE")

    def test_a3_scientific_decision_is_p2(self) -> None:
        projection = compose_owner_attention(
            cockpit={
                "attention": [
                    {
                        "id": "DECISION_AVAILABLE",
                        "WHY_NOW": "decision",
                        "IMPACT": "owner",
                        "EVIDENCE": "DECISION",
                        "NEXT_SAFE_ACTION": "OPEN_RESEARCH",
                    }
                ]
            }
        )
        self.assertEqual(projection["current_attention"][0]["priority"], "P2")
        self.assertEqual(projection["current_attention"][0]["drilldown_target"], "/research")

    def test_a4_a5_noise_gaps_are_not_global(self) -> None:
        projection = compose_owner_attention(
            trading={
                "source_status": "NOT_PRESENT",
                "attention": [
                    _ops_attention("ACTIVATION_PATH_GAP", "STRAT"),
                    _ops_attention("WATCHLIST_SOURCE_GAP", "WATCH"),
                    _ops_attention("SOURCE_NOT_PRESENT", "STORE"),
                ],
            }
        )
        self.assertEqual(projection["current_attention"], [])
        self.assertTrue(projection["all_clear"])
        self.assertFalse(projection["healthy_claim"])
        self.assertEqual(projection["coverage"][1]["CURRENT_STATE"], "NOT_PRESENT")

    def test_b_newness_uses_availability_not_effective_time(self) -> None:
        cursor = {
            "sources": {
                "RESEARCH": {
                    "change_available_at": "2026-09-06T00:00:00Z",
                    "native_identity": "REC-OLD",
                }
            }
        }
        projection = compose_owner_attention(
            research={"sources": [{"status": "AVAILABLE"}]},
            research_records=[
                {
                    "record_id": "REC-NEW",
                    "record_kind": "DECISION_EVENT",
                    "first_reliable_available_at": "2026-09-07T12:00:00Z",
                    "effective_at": "2026-09-06T08:00:00Z",
                }
            ],
            cursor=cursor,
            cursor_status="VALID",
        )
        self.assertEqual(len(projection["changes"]), 1)
        self.assertEqual(projection["changes"][0]["effective_at"], "2026-09-06T08:00:00Z")
        self.assertTrue(projection["changes"][0]["new_since_review"])

    def test_b4_system_has_no_fake_change_history(self) -> None:
        projection = compose_owner_attention(runtime={"verdict": "RUNTIME_PROVED_BACKUP_UNKNOWN"})
        system = projection["coverage"][2]
        self.assertEqual(system["CURRENT_STATE"], "PARTIAL")
        self.assertEqual(system["CHANGE_HISTORY"], "STATE_ONLY")
        self.assertEqual(projection["changes"], [])

    def test_b5_same_native_event_dedups(self) -> None:
        projection = compose_owner_attention(
            trading={
                "source_status": "PRESENT",
                "attention": [
                    _ops_attention("UNRESOLVED_POSITION", "POS-1"),
                    _ops_attention("UNRESOLVED_POSITION", "POS-1"),
                ],
            }
        )
        self.assertEqual(len(projection["current_attention"]), 1)

    def test_b6_unrelated_identities_stay_separate(self) -> None:
        projection = compose_owner_attention(
            trading={
                "source_status": "PRESENT",
                "attention": [
                    _ops_attention("UNRESOLVED_POSITION", "POS-A"),
                    _ops_attention("UNRESOLVED_POSITION", "POS-B"),
                ],
            }
        )
        self.assertEqual(len(projection["current_attention"]), 2)

    def test_c_review_stale_and_unresolved_remain(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            store = OperationalStore((root / "ops.sqlite").resolve())
            app = FactoryApplication(root=root, store=store)
            first = app.read_model(surface="HOME")
            attention = first["owner_attention"]
            self.assertEqual(
                attention["review"]["code"], "REVIEW_BASELINE_NOT_ESTABLISHED"
            )
            digest = attention["review_snapshot_sha256"]
            marked = app.mark_home_reviewed(digest)
            self.assertEqual(marked["status"], "MARKED")
            self.assertTrue(cursor_path(root).is_file())
            stale = app.mark_home_reviewed("0" * 64)
            self.assertEqual(stale["status"], "STALE_REVIEW_SNAPSHOT")
            self.assertEqual(stale["side_effects"], 0)
            loaded = json.loads(cursor_path(root).read_text(encoding="utf-8"))
            self.assertEqual(loaded["review_snapshot_sha256"], digest)

    def test_c4_reviewed_p0_remains(self) -> None:
        cursor = {
            "sources": {
                "OPERATIONS": {
                    "change_available_at": "2026-09-07T00:00:00Z",
                    "native_identity": "EVT-1",
                }
            }
        }
        projection = compose_owner_attention(
            trading={
                "source_status": "PRESENT",
                "attention": [_ops_attention("UNRESOLVED_POSITION", "POS-1")],
                "recent_changes": [
                    {
                        "event_id": "EVT-1",
                        "event_type": "POSITION_TRANSITION",
                        "created_at": "2026-09-07T00:00:00Z",
                    }
                ],
            },
            cursor=cursor,
            cursor_status="VALID",
        )
        self.assertEqual(projection["current_attention"][0]["priority"], "P0")
        self.assertFalse(projection["current_attention"][0].get("new_since_review"))

    def test_c6_unavailable_source_watermark_not_advanced(self) -> None:
        from solana_alpha_lab.factory.owner_daily_attention import persistable_watermarks

        previous = {
            "sources": {
                "RESEARCH": {
                    "change_available_at": "2026-09-01T00:00:00Z",
                    "native_identity": "REC-KEEP",
                }
            }
        }
        snapshot = {
            "sources": {
                "RESEARCH": {
                    "change_available_at": "2026-09-07T00:00:00Z",
                    "native_identity": "REC-NEW",
                },
                "OPERATIONS": {},
                "SYSTEM": {},
            }
        }
        coverage = [
            {"source_domain": "RESEARCH", "CURRENT_STATE": "UNAVAILABLE", "CHANGE_HISTORY": "UNAVAILABLE"},
            {"source_domain": "OPERATIONS", "CURRENT_STATE": "NOT_PRESENT", "CHANGE_HISTORY": "NOT_PRESENT"},
            {"source_domain": "SYSTEM", "CURRENT_STATE": "PARTIAL", "CHANGE_HISTORY": "STATE_ONLY"},
        ]
        out = persistable_watermarks(snapshot, previous=previous, coverage=coverage)
        self.assertEqual(out["RESEARCH"]["native_identity"], "REC-KEEP")

    def test_c7_get_home_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            before = _walk_relatives(root)
            app = FactoryApplication(root=root)
            for path in GET_PATHS:
                body = _get(app, path)
                if path == "/":
                    self.assertIn("REVIEW_BASELINE_NOT_ESTABLISHED", body)
                    self.assertIn("MARK_REVIEWED", body)
                    self.assertNotIn('value="START"', body)
                    self.assertNotIn('value="STOP"', body)
                    for command in COMMANDS:
                        self.assertNotIn(f'value="{command}"', body)
            after = _walk_relatives(root)
            self.assertEqual(before, after)
            self.assertFalse(cursor_path(root).is_file())

    def test_k_mark_reviewed_does_not_touch_git_or_paperplane(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            store = OperationalStore((root / "ops.sqlite").resolve())
            app = FactoryApplication(root=root, store=store)
            digest = app.read_model(surface="HOME")["owner_attention"]["review_snapshot_sha256"]
            git_before = {
                rel: hashlib.sha256((root / rel).read_bytes()).hexdigest()
                for rel in ("README.md", "docs/contracts/owner_attention_and_change_feed_v1.md")
                if (root / rel).is_file()
            }
            paper = root / "local/factory_v1/paper_plane_state.sqlite"
            self.assertFalse(paper.is_file())
            result = app.mark_home_reviewed(digest)
            self.assertEqual(result["status"], "MARKED")
            self.assertTrue(cursor_path(root).is_file())
            self.assertFalse(paper.is_file())
            git_after = {
                rel: hashlib.sha256((root / rel).read_bytes()).hexdigest()
                for rel in git_before
            }
            self.assertEqual(git_before, git_after)
            loaded = load_cursor(root)
            self.assertEqual(loaded["status"], "VALID")

    def test_home_post_mark_reviewed_and_stale(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            store = OperationalStore((root / "ops.sqlite").resolve())
            app = FactoryApplication(root=root, store=store)
            home = _get(app, "/")
            self.assertIn("expected_review_snapshot_sha256", home)
            digest = app.read_model(surface="HOME")["owner_attention"]["review_snapshot_sha256"]
            _post(
                app,
                "/",
                {
                    "command": "MARK_REVIEWED",
                    "expected_review_snapshot_sha256": digest,
                },
            )
            self.assertTrue(cursor_path(root).is_file())
            body = _post(
                app,
                "/",
                {
                    "command": "MARK_REVIEWED",
                    "expected_review_snapshot_sha256": "ab" * 32,
                },
            )
            self.assertIn("STALE_REVIEW_SNAPSHOT", body)

    def test_research_fail_is_p1_not_all_clear(self) -> None:
        projection = compose_owner_attention(
            research={"completeness": "UNAVAILABLE", "sources": [], "needs_attention": []}
        )
        self.assertEqual(projection["coverage"][0]["CURRENT_STATE"], "UNAVAILABLE")
        self.assertEqual(projection["coverage"][0]["CHANGE_HISTORY"], "UNAVAILABLE")
        self.assertEqual(projection["current_attention"][0]["priority"], "P1")
        self.assertEqual(projection["current_attention"][0]["attention_code"], "SOURCE_UNAVAILABLE")
        self.assertFalse(projection["all_clear"])
        body = _page(
            {"owner_attention": projection, "cockpit": {}, "runtime": {}},
            surface="HOME",
        ).decode("utf-8")
        self.assertNotIn(SURFACE_COPY["HOME"]["do_nothing"], body)

    def test_git_panel_does_not_mark_research_change_history(self) -> None:
        projection = compose_owner_attention(
            research={
                "sources": [
                    {"source_id": "SRC-EXPERIMENT-SPECS", "status": "AVAILABLE"},
                    {"source_id": "SRC-RESEARCH-STORE", "status": "NOT_PRESENT"},
                ]
            }
        )
        research = projection["coverage"][0]
        self.assertEqual(research["CURRENT_STATE"], "PARTIAL")
        self.assertEqual(research["CHANGE_HISTORY"], "NOT_PRESENT")
        self.assertNotEqual(research["CHANGE_HISTORY"], "AVAILABLE")
        self.assertTrue(projection["all_clear"])
        previous = {
            "sources": {
                "RESEARCH": {
                    "change_available_at": "2026-09-01T00:00:00Z",
                    "native_identity": "REC-KEEP",
                }
            }
        }
        out = persistable_watermarks(
            projection["review_snapshot"],
            previous=previous,
            coverage=projection["coverage"],
        )
        self.assertEqual(out["RESEARCH"]["native_identity"], "REC-KEEP")

    def test_present_unopenable_research_store_is_p1_not_absence(self) -> None:
        projection = compose_owner_attention(
            research={
                "sources": [
                    {"source_id": "SRC-EXPERIMENT-SPECS", "status": "AVAILABLE"},
                    {"source_id": "SRC-RESEARCH-STORE", "status": "NOT_PRESENT"},
                ],
                "needs_attention": [],
            },
            research_discovery="INVALID",
        )
        research = projection["coverage"][0]
        self.assertEqual(research["CURRENT_STATE"], "INVALID")
        self.assertEqual(research["CHANGE_HISTORY"], "UNAVAILABLE")
        self.assertEqual(projection["current_attention"][0]["priority"], "P1")
        self.assertEqual(projection["current_attention"][0]["attention_code"], "SOURCE_INVALID")
        self.assertFalse(projection["all_clear"])
        body = _page(
            {"owner_attention": projection, "cockpit": {}, "runtime": {}},
            surface="HOME",
        ).decode("utf-8")
        self.assertNotIn(SURFACE_COPY["HOME"]["do_nothing"], body)
        previous = {
            "sources": {
                "RESEARCH": {
                    "change_available_at": "2026-09-01T00:00:00Z",
                    "native_identity": "REC-KEEP",
                }
            }
        }
        out = persistable_watermarks(
            projection["review_snapshot"],
            previous=previous,
            coverage=projection["coverage"],
        )
        self.assertEqual(out["RESEARCH"]["native_identity"], "REC-KEEP")

    def test_success_state_is_do_nothing_with_visible_coverage(self) -> None:
        projection = compose_owner_attention(
            research={
                "sources": [{"source_id": "SRC-RESEARCH-STORE", "status": "AVAILABLE"}],
                "needs_attention": [],
            },
            trading={"source_status": "PRESENT", "attention": [], "recent_changes": []},
            runtime={"verdict": "RUNTIME_PROVED_BACKUP_UNKNOWN"},
            cursor_status="VALID",
            cursor={"sources": {}},
        )
        self.assertEqual(projection["current_attention"], [])
        self.assertTrue(projection["all_clear"])
        self.assertFalse(projection["healthy_claim"])
        self.assertEqual(projection["coverage"][0]["CHANGE_HISTORY"], "AVAILABLE")
        self.assertEqual(projection["coverage"][2]["CHANGE_HISTORY"], "STATE_ONLY")
        body = _page(
            {"owner_attention": projection, "cockpit": {}, "runtime": {}},
            surface="HOME",
        ).decode("utf-8")
        self.assertIn(SURFACE_COPY["HOME"]["do_nothing"], body)
        self.assertIn(SURFACE_COPY["HOME"]["coverage"], body)

    def test_research_change_feed_is_bounded_and_incomplete(self) -> None:
        records = [
            {
                "record_id": f"REC-{index:02d}",
                "record_kind": "RESEARCH_EVENT",
                "first_reliable_available_at": f"2026-09-07T{index:02d}:00:00Z",
                "effective_at": f"2026-09-01T{index:02d}:00:00Z",
            }
            for index in range(1, 16)
        ]
        projection = compose_owner_attention(
            research={"sources": [{"source_id": "SRC-RESEARCH-STORE", "status": "AVAILABLE"}]},
            research_records=records,
            cursor_status="VALID",
            cursor={
                "sources": {
                    "RESEARCH": {
                        "change_available_at": "2026-09-01T00:00:00Z",
                        "native_identity": "REC-OLD",
                    }
                }
            },
        )
        self.assertLessEqual(len(projection["changes"]), CHANGE_FEED_LIMIT)
        self.assertEqual(projection["review"]["code"], "CHANGE_HISTORY_GAP")
        self.assertFalse(projection["all_clear"])
        self.assertFalse(projection["review_snapshot"]["history_complete"])

    def test_research_conflicts_keep_locator_identity(self) -> None:
        projection = compose_owner_attention(
            research={
                "sources": [{"source_id": "SRC-RESEARCH-STORE", "status": "AVAILABLE"}],
                "needs_attention": [
                    {
                        "locator": {"entity_id": "ENT-A"},
                        "display_state": "CONFLICT",
                        "title": "conflict a",
                        "next_safe_action": "OPEN_RESEARCH",
                    },
                    {
                        "locator": {"entity_id": "ENT-B"},
                        "display_state": "CONFLICT",
                        "title": "conflict b",
                        "next_safe_action": "OPEN_RESEARCH",
                    },
                    {
                        "blocker": "SOURCE_INVALID",
                        "source_id": "SRC-A",
                        "title": "invalid a",
                        "next_safe_action": "OPEN_RESEARCH",
                    },
                    {
                        "blocker": "SOURCE_INVALID",
                        "source_id": "SRC-B",
                        "title": "invalid b",
                        "next_safe_action": "OPEN_RESEARCH",
                    },
                ],
            }
        )
        keys = {item["source_native_identity"] for item in projection["current_attention"]}
        self.assertEqual(keys, {"ENT-A", "ENT-B", "SRC-A", "SRC-B"})
        self.assertTrue(all(item["priority"] == "P1" for item in projection["current_attention"]))

    def test_same_native_keeps_distinct_codes(self) -> None:
        projection = compose_owner_attention(
            trading={
                "source_status": "PRESENT",
                "attention": [
                    _ops_attention("UNRESOLVED_POSITION", "POS-1"),
                    _ops_attention("EXIT_REQUIRED", "POS-1"),
                    {
                        "code": "BOT_DRAINING",
                        "EVIDENCE": "bot.status=DRAINING:BOT-A",
                        "WHY_NOW": "drain a",
                        "IMPACT": "risk",
                        "NEXT_SAFE_ACTION": "WAIT_DRAIN",
                    },
                    {
                        "code": "BOT_DRAINING",
                        "EVIDENCE": "bot.status=DRAINING:BOT-B",
                        "WHY_NOW": "drain b",
                        "IMPACT": "risk",
                        "NEXT_SAFE_ACTION": "WAIT_DRAIN",
                    },
                ],
            }
        )
        codes = {(item["attention_code"], item["source_native_identity"]) for item in projection["current_attention"]}
        self.assertEqual(
            codes,
            {
                ("UNRESOLVED_POSITION", "POS-1"),
                ("EXIT_REQUIRED", "POS-1"),
                ("BOT_DRAINING", "bot.status=DRAINING:BOT-A"),
                ("BOT_DRAINING", "bot.status=DRAINING:BOT-B"),
            },
        )

    def test_ops_window_hole_does_not_advance_watermark(self) -> None:
        events = [
            {
                "event_id": f"EVT-{index:02d}",
                "event_type": "POSITION_TRANSITION",
                "created_at": f"2026-09-07T{index:02d}:00:00Z",
            }
            for index in range(10, 22)
        ]
        cursor = {
            "sources": {
                "OPERATIONS": {
                    "change_available_at": "2026-09-01T00:00:00Z",
                    "native_identity": "EVT-OLD",
                }
            }
        }
        projection = compose_owner_attention(
            trading={"source_status": "PRESENT", "attention": [], "recent_changes": events},
            cursor=cursor,
            cursor_status="VALID",
        )
        self.assertEqual(projection["review"]["code"], "CHANGE_HISTORY_GAP")
        self.assertEqual(projection["coverage"][1]["CHANGE_HISTORY"], "UNAVAILABLE")
        out = persistable_watermarks(
            projection["review_snapshot"],
            previous=cursor,
            coverage=projection["coverage"],
        )
        self.assertEqual(out["OPERATIONS"]["native_identity"], "EVT-OLD")

    def test_empty_live_watermark_keeps_previous(self) -> None:
        previous = {
            "sources": {
                "RESEARCH": {
                    "change_available_at": "2026-09-01T00:00:00Z",
                    "native_identity": "REC-KEEP",
                }
            }
        }
        snapshot = {
            "history_complete": True,
            "sources": {
                "RESEARCH": {
                    "change_available_at": None,
                    "native_identity": None,
                },
                "OPERATIONS": {},
                "SYSTEM": {},
            },
        }
        coverage = [
            {"source_domain": "RESEARCH", "CURRENT_STATE": "AVAILABLE", "CHANGE_HISTORY": "AVAILABLE"},
            {"source_domain": "OPERATIONS", "CURRENT_STATE": "NOT_PRESENT", "CHANGE_HISTORY": "NOT_PRESENT"},
            {"source_domain": "SYSTEM", "CURRENT_STATE": "PARTIAL", "CHANGE_HISTORY": "STATE_ONLY"},
        ]
        out = persistable_watermarks(snapshot, previous=previous, coverage=coverage)
        self.assertEqual(out["RESEARCH"]["native_identity"], "REC-KEEP")

    def test_snapshot_hash_includes_change_identities(self) -> None:
        research = {"sources": [{"source_id": "SRC-RESEARCH-STORE", "status": "AVAILABLE"}]}
        first = compose_owner_attention(
            research=research,
            research_records=[
                {
                    "record_id": "REC-A",
                    "record_kind": "RESEARCH_EVENT",
                    "first_reliable_available_at": "2026-09-07T10:00:00Z",
                },
                {
                    "record_id": "REC-C",
                    "record_kind": "RESEARCH_EVENT",
                    "first_reliable_available_at": "2026-09-07T12:00:00Z",
                },
            ],
            cursor_status="VALID",
            cursor={"sources": {}},
        )
        second = compose_owner_attention(
            research=research,
            research_records=[
                {
                    "record_id": "REC-A",
                    "record_kind": "RESEARCH_EVENT",
                    "first_reliable_available_at": "2026-09-07T10:00:00Z",
                },
                {
                    "record_id": "REC-B",
                    "record_kind": "RESEARCH_EVENT",
                    "first_reliable_available_at": "2026-09-07T11:00:00Z",
                },
                {
                    "record_id": "REC-C",
                    "record_kind": "RESEARCH_EVENT",
                    "first_reliable_available_at": "2026-09-07T12:00:00Z",
                },
            ],
            cursor_status="VALID",
            cursor={"sources": {}},
        )
        self.assertNotEqual(first["review_snapshot_sha256"], second["review_snapshot_sha256"])

    def test_newness_normalizes_timezone_offsets(self) -> None:
        cursor = {
            "sources": {
                "RESEARCH": {
                    "change_available_at": "2026-09-07T08:00:00Z",
                    "native_identity": "REC-OLD",
                }
            }
        }
        projection = compose_owner_attention(
            research={"sources": [{"source_id": "SRC-RESEARCH-STORE", "status": "AVAILABLE"}]},
            research_records=[
                {
                    "record_id": "REC-NEW",
                    "record_kind": "RESEARCH_EVENT",
                    "first_reliable_available_at": "2026-09-07T10:00:00+03:00",
                    "effective_at": "2026-09-06T08:00:00+03:00",
                }
            ],
            cursor=cursor,
            cursor_status="VALID",
        )
        self.assertEqual(len(projection["changes"]), 0)

    def test_semantic_daily_attention_not_delivery_gate(self) -> None:
        projection = load_semantic_projection(ROOT)
        assets, bindings, _queries = load_semantic_catalog_views(ROOT)
        hits = search_semantic_routes(
            projection,
            "What needs my attention today?",
            assets=assets,
            bindings=bindings,
            limit=3,
        )
        self.assertEqual(hits[0]["semantic_route_id"], "SEM-OWNER-DAILY-ATTENTION")
        changed = search_semantic_routes(
            projection,
            "What changed since I reviewed Factory?",
            assets=assets,
            bindings=bindings,
            limit=3,
        )
        self.assertEqual(changed[0]["semantic_route_id"], "SEM-OWNER-DAILY-ATTENTION")
        merge = search_semantic_routes(
            projection, "May this PR merge?", assets=assets, bindings=bindings, limit=3
        )
        self.assertEqual(merge[0]["semantic_route_id"], "SEM-AUTHORITY-BOUNDARIES")
        gate = search_semantic_routes(
            projection,
            "What is OWNER_ATTENTION_GATE_V2?",
            assets=assets,
            bindings=bindings,
            limit=3,
        )
        self.assertEqual(gate[0]["semantic_route_id"], "SEM-AUTHORITY-BOUNDARIES")
        spend = search_semantic_routes(
            projection,
            "May I activate/deploy/spend?",
            assets=assets,
            bindings=bindings,
            limit=3,
        )
        self.assertEqual(spend[0]["semantic_route_id"], "SEM-AUTHORITY-BOUNDARIES")
