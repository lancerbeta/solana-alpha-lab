"""TRADING_OPERATIONS_WORKBENCH_V2 vertical acceptance."""

from __future__ import annotations

import hashlib
import sqlite3
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
from solana_alpha_lab.factory.paper_plane import (  # noqa: E402
    PaperPlaneError,
    PaperPlaneStore,
    accept_signal_decision,
)
from solana_alpha_lab.factory.paper_shadow_operations import open_position_set_sha256  # noqa: E402
from solana_alpha_lab.factory.runtime import copy_rehost_allowlist, load_runtime_config  # noqa: E402
from solana_alpha_lab.factory.strategy_runtime import load_strategy_version  # noqa: E402
from solana_alpha_lab.factory.workbench import serve  # noqa: E402
from solana_alpha_lab.factory_semantic_operability import (  # noqa: E402
    load_semantic_catalog_views,
    load_semantic_projection,
    search_semantic_routes,
)

STRAT_REL = "tests/fixtures/paper_shadow_accounting_control/strategy_v1_1_accounting.yaml"
EPOCH = "ACTIVATION-EPOCH-ACCOUNTING-PAPER-001"
KNOWN_EPOCHS = {EPOCH: {"mode": "PAPER"}}
MINT = "So11111111111111111111111111111111111111112"
GAP_STRAT = "configs/strategies/STRAT-V-EARLY-LIQ-FLOOR-COMMISSIONING-V1.yaml"
GET_PATHS = ("/", "/research", "/operations", "/economics", "/system")


def isolated_factory_root(tmp: Path) -> Path:
    config = load_runtime_config(ROOT)
    copy_rehost_allowlist(
        src_root=ROOT,
        dst_root=tmp,
        relatives=list(config["rehost_relative_paths"]),
    )
    return tmp


def _copy_git_strategy(root: Path, relative: str) -> None:
    dest = root / "configs" / "strategies" / Path(relative).name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes((ROOT / relative).read_bytes())


def _signal(signal_id: str, *, decision_at: str, action: str = "ENTER", mint: str = MINT) -> dict:
    return {
        "schema": "smial.signal-decision",
        "schema_version": "1.0",
        "signal_decision_id": signal_id,
        "strategy_id": "STRAT-ACCOUNTING-CONTROL-A",
        "strategy_version": "V1",
        "activation_epoch_id": EPOCH,
        "source_hypothesis_refs": ["HYP-ACCOUNTING-SYNTH-A"],
        "mint": mint,
        "decision_at": decision_at,
        "first_reliable_available_at": "2026-09-03T12:09:00Z",
        "action": action,
        "reason_code": "OPS_V2_FIXTURE",
        "evidence_refs": [
            "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
        ],
    }


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


def _enter(
    store: PaperPlaneStore,
    signal_id: str,
    *,
    decision_at: str,
    strategy: dict | None = None,
    fill: bool = True,
    mint: str = MINT,
) -> str:
    loaded = strategy or load_strategy_version(ROOT, STRAT_REL)
    accepted = accept_signal_decision(
        ROOT,
        store,
        strategy=loaded,
        signal_decision=_signal(signal_id, decision_at=decision_at, mint=mint),
        known_activation_epochs=KNOWN_EPOCHS,
        mode="PAPER",
        as_of=decision_at,
    )
    pid = str(accepted["position_id"])
    if fill:
        store.apply_paper_entry_fill(
            position_id=pid,
            entry_unit_price_usd="1.00",
            entry_gross_notional_usd="100",
            fee_bps=10,
            mode="PAPER",
        )
    return pid


class TradingOperationsWorkbenchV2Tests(unittest.TestCase):
    def test_a_get_does_not_bootstrap_runtime(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            before = _walk_relatives(root)
            self.assertFalse((root / "local").exists())
            app = FactoryApplication(root=root)
            for path in GET_PATHS:
                body = _get(app, path)
                if path == "/operations":
                    self.assertIn("NOT_PRESENT", body)
                    self.assertIn("SOURCE_NOT_PRESENT", body)
                    self.assertNotIn('name="command" value="PAUSE_NEW_ENTRIES"', body)
                    self.assertNotIn("START PAPER", body)
                    self.assertNotIn("ACTIVATE STRATEGY", body)
            after = _walk_relatives(root)
            self.assertEqual(before, after)
            self.assertFalse((root / "local").exists())
            self.assertIsNone(app.existing_paper_plane())
            with self.assertRaises(ApplicationError) as raised:
                app.apply_paper_operator_command(
                    {
                        "command_type": "PAUSE_NEW_ENTRIES",
                        "bot_instance_id": "BOT-ABSENT",
                        "idempotency_key": "WB-ABSENT-1",
                    }
                )
            self.assertEqual(raised.exception.code, "SOURCE_NOT_PRESENT")
            self.assertEqual(before, _walk_relatives(root))

    def test_a_existing_store_get_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            paper_path = (root / "local/factory_v1/paper_plane_state.sqlite").resolve()
            paper = PaperPlaneStore(paper_path)
            _enter(paper, "SIGDEC-OPS-V2-A2", decision_at="2026-09-03T12:10:00Z")
            paper.close()
            before = _walk_relatives(root)
            app = FactoryApplication(root=root)
            for path in GET_PATHS:
                _get(app, path)
            self.assertEqual(before, _walk_relatives(root))
            self.assertEqual(app._paper_plane_source_status, "PRESENT")

    def test_b_c_strategy_bot_lineage_and_activation_gap(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            _copy_git_strategy(root, STRAT_REL)
            _copy_git_strategy(root, GAP_STRAT)
            paper = PaperPlaneStore((root / "local/factory_v1/paper_plane_state.sqlite").resolve())
            pid = _enter(paper, "SIGDEC-OPS-V2-B", decision_at="2026-09-03T12:10:00Z")
            app = FactoryApplication(root=root, paper_plane_store=paper)
            try:
                model = app.read_model(surface="OPERATIONS")
                trading = model["trading_operations"]
                self.assertEqual(trading["source_status"], "PRESENT")
                by_strategy = {row["strategy_id"]: row for row in trading["contexts"]}
                linked = by_strategy["STRAT-ACCOUNTING-CONTROL-A"]
                self.assertEqual(linked["relation"], "EXPLICIT")
                self.assertEqual(linked["bot_status"], "RUNNING")
                self.assertEqual(linked["activation_epoch_id"], EPOCH)
                self.assertEqual(linked["bot_instance_id"], paper.bots()[0]["bot_instance_id"])
                gap = next(
                    row
                    for row in trading["contexts"]
                    if row["strategy_id"] == "STRAT-V-EARLY-LIQ-FLOOR"
                )
                self.assertEqual(gap["bot_status"], "NOT_ACTIVATED")
                self.assertEqual(gap["relation"], "ACTIVATION_GAP")
                self.assertIsNone(gap["bot_instance_id"])
                codes = {item["code"] for item in trading["attention"]}
                self.assertIn("ACTIVATION_GAP", codes)
                body = _get(app, "/operations")
                self.assertIn(pid, body)
                self.assertIn("ACTIVATION_GAP", body)
                self.assertIn("ACTIVATION_PATH_GAP", body)
                self.assertNotIn('name="command" value="START_PAPER"', body)
                copied = root / "configs" / "strategies" / Path(STRAT_REL).name
                copied.write_text(
                    copied.read_text(encoding="utf-8").replace(
                        "strategy_version: V1",
                        "strategy_version: V9",
                        1,
                    ),
                    encoding="utf-8",
                )
                mismatched = app.read_model(surface="OPERATIONS")["trading_operations"]
                git_row = next(
                    row
                    for row in mismatched["contexts"]
                    if row["strategy_id"] == "STRAT-ACCOUNTING-CONTROL-A"
                    and row["relation"] == "ACTIVATION_GAP"
                )
                self.assertEqual(git_row["strategy_version"], "V9")
                runtime_row = next(
                    row
                    for row in mismatched["contexts"]
                    if row["relation"] == "RUNTIME_ONLY"
                )
                self.assertEqual(runtime_row["current_blocker"], "STRATEGY_VERSION_GAP")
                self.assertIn(
                    "STRATEGY_VERSION_GAP",
                    {item["code"] for item in mismatched["attention"]},
                )
            finally:
                paper.close()

    def test_d_e_signal_risk_trace_and_non_enter(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            paper = PaperPlaneStore((root / "local/factory_v1/paper_plane_state.sqlite").resolve())
            strategy = load_strategy_version(ROOT, STRAT_REL)
            pid = _enter(paper, "SIGDEC-OPS-V2-D", decision_at="2026-09-03T12:10:00Z")
            blocked = dict(strategy)
            blocked["risk_policy"] = dict(strategy["risk_policy"])
            blocked["risk_policy"]["max_open_positions"] = 0
            with self.assertRaises(PaperPlaneError):
                accept_signal_decision(
                    ROOT,
                    paper,
                    strategy=blocked,
                    signal_decision=_signal(
                        "SIGDEC-OPS-V2-E-RISK", decision_at="2026-09-03T12:11:00Z"
                    ),
                    known_activation_epochs=KNOWN_EPOCHS,
                    mode="PAPER",
                    as_of="2026-09-03T12:11:00Z",
                )
            accept_signal_decision(
                ROOT,
                paper,
                strategy=strategy,
                signal_decision=_signal(
                    "SIGDEC-OPS-V2-E-HOLD",
                    decision_at="2026-09-03T12:12:00Z",
                    action="NO_ENTER",
                ),
                known_activation_epochs=KNOWN_EPOCHS,
                mode="PAPER",
                as_of="2026-09-03T12:12:00Z",
            )
            app = FactoryApplication(root=root, paper_plane_store=paper)
            try:
                traces = app.read_model()["trading_operations"]["traces"]
                by_signal = {
                    row.get("signal_decision_id"): row
                    for row in traces
                    if row.get("signal_decision_id")
                }
                happy = by_signal["SIGDEC-OPS-V2-D"]
                self.assertEqual(happy["stages"]["SIGNAL_DECISION"], "PROVEN")
                self.assertEqual(happy["stages"]["PRE_TRADE_RISK"], "PROVEN")
                self.assertEqual(happy["stages"]["EXECUTION_INTENT"], "PROVEN")
                self.assertEqual(happy["stages"]["EXECUTION_OBSERVATION"], "PROVEN")
                self.assertEqual(happy["stages"]["POSITION"], "PROVEN")
                self.assertEqual(happy["position_id"], pid)
                risk = by_signal["SIGDEC-OPS-V2-E-RISK"]
                self.assertEqual(risk["stages"]["PRE_TRADE_RISK"], "PROVEN")
                self.assertEqual(risk["blocker"], "RISK_BLOCK")
                self.assertIsNone(risk.get("position_id") or None)
                self.assertFalse(
                    any(
                        row.get("signal_decision_id") == "SIGDEC-OPS-V2-E-RISK"
                        for row in paper.positions()
                    )
                )
                held = by_signal["SIGDEC-OPS-V2-E-HOLD"]
                self.assertEqual(held["stages"]["SIGNAL_DECISION"], "PROVEN")
                self.assertEqual(held["stages"]["POSITION"], "GAP")
                self.assertTrue(
                    all(row.get("signal_decision_id") != "SIGDEC-OPS-V2-E-HOLD" for row in paper.positions())
                )
            finally:
                paper.close()

    def test_f_g_unknown_mark_and_exit_reconcile(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            paper = PaperPlaneStore((root / "local/factory_v1/paper_plane_state.sqlite").resolve())
            unknown_id = _enter(paper, "SIGDEC-OPS-V2-F", decision_at="2026-09-03T12:10:00Z")
            paper.record_position_mark(
                position_id=unknown_id,
                mark_price_dec=None,
                as_of="2026-09-03T12:14:00Z",
                evidence_class="UNKNOWN",
            )
            exit_id = _enter(paper, "SIGDEC-OPS-V2-G", decision_at="2026-09-03T12:11:00Z")
            paper.transition(exit_id, "EXIT_REQUIRED")
            paper.apply_paper_exit_fill(
                position_id=exit_id, exit_unit_price_usd="1.10", mode="PAPER"
            )
            app = FactoryApplication(root=root, paper_plane_store=paper)
            try:
                ops = app.read_model()["operations"]
                by_id = {row["position_id"]: row for row in ops["position_rows"]}
                unknown = by_id[unknown_id]
                self.assertEqual(unknown["state"], "OPEN")
                self.assertEqual(unknown["pnl_status"], "UNKNOWN")
                self.assertIsNone(unknown["net_pnl_usd"])
                self.assertGreater(ops["pnl_unknown_count"], 0)
                codes = {
                    item["code"]
                    for item in app.read_model()["trading_operations"]["attention"]
                }
                self.assertIn("PNL_UNKNOWN_OR_STALE", codes)
                reconciled = by_id[exit_id]
                self.assertEqual(reconciled["state"], "RECONCILED")
                body = _get(app, "/operations")
                self.assertIn("UNKNOWN", body)
                self.assertNotIn("$0", body.split(unknown_id, 1)[1][:400])
                traces = app.read_model()["trading_operations"]["traces"]
                g_trace = next(row for row in traces if row.get("signal_decision_id") == "SIGDEC-OPS-V2-G")
                self.assertEqual(g_trace["stages"]["EXIT"], "PROVEN")
                self.assertEqual(g_trace["stages"]["RECONCILIATION"], "PROVEN")
            finally:
                paper.close()

    def test_h_i_command_readback_and_stale_close_all(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            paper = PaperPlaneStore((root / "local/factory_v1/paper_plane_state.sqlite").resolve())
            pid = _enter(paper, "SIGDEC-OPS-V2-H", decision_at="2026-09-03T12:10:00Z")
            bot_id = paper.bots()[0]["bot_instance_id"]
            app = FactoryApplication(root=root, paper_plane_store=paper)
            try:
                pause = _post(
                    app,
                    "/operations",
                    {
                        "command": "PAUSE_NEW_ENTRIES",
                        "bot_instance_id": bot_id,
                        "idempotency_key": "WB-OPS-V2-PAUSE",
                    },
                )
                self.assertIn("ENTRIES_PAUSED", pause)
                self.assertTrue(bool(int(paper.get_bot(bot_id)["entries_paused"])))
                self.assertIn("PAUSE_NEW_ENTRIES", pause)
                live_hash = open_position_set_sha256(
                    [row["position_id"] for row in paper.positions() if row["state"] in {"OPEN", "PARTIAL"}]
                )
                stale = app.apply_paper_operator_command(
                    {
                        "command_type": "REQUEST_CLOSE_ALL",
                        "bot_instance_id": bot_id,
                        "expected_open_position_set_sha256": "0" * 64,
                        "idempotency_key": "WB-OPS-V2-STALE",
                    }
                )
                self.assertEqual(stale["status"], "STALE_OPERATOR_SNAPSHOT")
                self.assertEqual(stale.get("side_effects"), 0)
                self.assertEqual(paper.get_position(pid)["state"], "OPEN")
                applied = app.apply_paper_operator_command(
                    {
                        "command_type": "REQUEST_CLOSE_ALL",
                        "bot_instance_id": bot_id,
                        "expected_open_position_set_sha256": live_hash,
                        "idempotency_key": "WB-OPS-V2-CLOSE-ALL",
                    }
                )
                self.assertEqual(applied["status"], "APPLIED")
                self.assertEqual(paper.get_position(pid)["state"], "EXIT_REQUIRED")
                traces = app.read_model()["trading_operations"]["traces"]
                h_trace = next(
                    row for row in traces if row.get("signal_decision_id") == "SIGDEC-OPS-V2-H"
                )
                self.assertEqual(h_trace["stages"]["POSITION"], "PROVEN")
                self.assertEqual(h_trace["stages"]["EXIT"], "GAP")
            finally:
                paper.close()

    def test_h_get_then_command_sees_fresh_runtime(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            path = (root / "local/factory_v1/paper_plane_state.sqlite").resolve()
            paper = PaperPlaneStore(path)
            _enter(paper, "SIGDEC-OPS-V2-H2", decision_at="2026-09-03T12:10:00Z")
            bot_id = paper.bots()[0]["bot_instance_id"]
            paper.close()
            app = FactoryApplication(root=root)
            before = _get(app, "/operations")
            self.assertNotIn("ENTRIES_PAUSED", before)
            after = _post(
                app,
                "/operations",
                {
                    "command": "PAUSE_NEW_ENTRIES",
                    "bot_instance_id": bot_id,
                    "idempotency_key": "WB-OPS-V2-H2-PAUSE",
                },
            )
            self.assertIn("PAUSE_NEW_ENTRIES", after)
            self.assertIn("ENTRIES_PAUSED", after)
            self.assertIn(f"open_set.{bot_id}", after)
            reread = _get(app, "/operations")
            self.assertIn("ENTRIES_PAUSED", reread)

    def test_incompatible_schema_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            path = (root / "local/factory_v1/paper_plane_state.sqlite").resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE dummy (id INTEGER)")
            conn.commit()
            conn.close()
            app = FactoryApplication(root=root)
            trading = app.read_model(surface="OPERATIONS")["trading_operations"]
            self.assertEqual(trading["source_status"], "UNAVAILABLE")
            self.assertIn(
                "RUNTIME_SOURCE_UNAVAILABLE",
                {item["code"] for item in trading["attention"]},
            )
            body = _get(app, "/operations")
            self.assertIn("RUNTIME_SOURCE_UNAVAILABLE", body)
            self.assertNotIn('name="command" value="PAUSE_NEW_ENTRIES"', body)

    def test_j_same_mint_does_not_merge_contexts(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            paper = PaperPlaneStore((root / "local/factory_v1/paper_plane_state.sqlite").resolve())
            first = _enter(paper, "SIGDEC-OPS-V2-J1", decision_at="2026-09-03T12:10:00Z")
            second = _enter(paper, "SIGDEC-OPS-V2-J2", decision_at="2026-09-03T12:11:00Z")
            app = FactoryApplication(root=root, paper_plane_store=paper)
            try:
                traces = app.read_model()["trading_operations"]["traces"]
                keyed = {
                    row["signal_decision_id"]: row
                    for row in traces
                    if row.get("signal_decision_id") in {"SIGDEC-OPS-V2-J1", "SIGDEC-OPS-V2-J2"}
                }
                self.assertEqual(keyed["SIGDEC-OPS-V2-J1"]["mint"], MINT)
                self.assertEqual(keyed["SIGDEC-OPS-V2-J2"]["mint"], MINT)
                self.assertEqual(keyed["SIGDEC-OPS-V2-J1"]["position_id"], first)
                self.assertEqual(keyed["SIGDEC-OPS-V2-J2"]["position_id"], second)
                self.assertNotEqual(first, second)
            finally:
                paper.close()

    def test_k_git_runtime_separation(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            _copy_git_strategy(root, STRAT_REL)
            yaml_path = root / "configs" / "strategies" / Path(STRAT_REL).name
            before_yaml = yaml_path.read_bytes()
            paper = PaperPlaneStore((root / "local/factory_v1/paper_plane_state.sqlite").resolve())
            _enter(paper, "SIGDEC-OPS-V2-K", decision_at="2026-09-03T12:10:00Z")
            bot_id = paper.bots()[0]["bot_instance_id"]
            app = FactoryApplication(root=root, paper_plane_store=paper)
            try:
                before_bot = dict(paper.get_bot(bot_id))
                app.apply_paper_operator_command(
                    {
                        "command_type": "PAUSE_NEW_ENTRIES",
                        "bot_instance_id": bot_id,
                        "idempotency_key": "WB-OPS-V2-K",
                    }
                )
                self.assertTrue(bool(int(paper.get_bot(bot_id)["entries_paused"])))
                self.assertEqual(yaml_path.read_bytes(), before_yaml)
                yaml_path.write_text(
                    yaml_path.read_text(encoding="utf-8").replace(
                        "title: Accounting control PAPER fixture",
                        "title: Accounting control PAPER fixture (edited)",
                    ),
                    encoding="utf-8",
                )
                refreshed = app.read_model()["trading_operations"]
                linked = next(
                    row
                    for row in refreshed["contexts"]
                    if row.get("bot_instance_id") == bot_id
                )
                self.assertEqual(linked["bot_status"], before_bot["status"] or "RUNNING")
                self.assertEqual(paper.get_bot(bot_id)["bot_instance_id"], bot_id)
            finally:
                paper.close()

    def test_legacy_event_without_join_is_gap(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            paper = PaperPlaneStore((root / "local/factory_v1/paper_plane_state.sqlite").resolve())
            paper.append_execution_event(
                event_type="PAPER_SIMULATION_OBSERVED",
                bot_instance_id=None,
                position_id=None,
                payload={"mint": MINT, "note": "legacy"},
            )
            app = FactoryApplication(root=root, paper_plane_store=paper)
            try:
                traces = app.read_model()["trading_operations"]["traces"]
                self.assertTrue(any(row.get("join") == "LEGACY_TRACE_GAP" for row in traces))
            finally:
                paper.close()

    def test_semantic_questions(self) -> None:
        projection = load_semantic_projection(ROOT)
        assets, bindings, _queries = load_semantic_catalog_views(ROOT)
        expected = {
            "What bot is executing this StrategyVersion?": "SEM-OWNER-LIFECYCLE",
            "What happened after this SignalDecision?": "SEM-OWNER-LIFECYCLE",
            "Which positions are unresolved?": "SEM-OWNER-LIFECYCLE",
            "How do I pause PAPER entries safely?": "SEM-OWNER-LIFECYCLE",
            "May I activate/deploy/spend?": "SEM-AUTHORITY-BOUNDARIES",
        }
        for query, route in expected.items():
            hits = search_semantic_routes(
                projection, query, assets=assets, bindings=bindings, limit=5
            )
            self.assertTrue(hits, query)
            self.assertEqual(hits[0]["semantic_route_id"], route, query)
            self.assertIs(hits[0]["authority_granted"], False)


if __name__ == "__main__":
    unittest.main()
