"""OWNER_OPERATIONS_COCKPIT_V1 focused acceptance suite."""

from __future__ import annotations

import inspect
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

from solana_alpha_lab.factory.application import FactoryApplication  # noqa: E402
from solana_alpha_lab.factory.operational_store import OperationalStore  # noqa: E402
from solana_alpha_lab.factory.paper_plane import PaperPlaneStore, accept_signal_decision  # noqa: E402
from solana_alpha_lab.factory.paper_shadow_operations import open_position_set_sha256  # noqa: E402
from solana_alpha_lab.factory.runtime import copy_rehost_allowlist, load_runtime_config  # noqa: E402
from solana_alpha_lab.factory.strategy_runtime import load_strategy_version  # noqa: E402
from solana_alpha_lab.factory import workbench as workbench_mod  # noqa: E402
from solana_alpha_lab.factory.workbench import serve  # noqa: E402

ACCEPTANCE_RELATIVE = (
    "docs/evidence/factory_v1_commissioning/a2_factory_v1_commissioning_acceptance_v1.json"
)
PAPER_STORE_RELATIVE = "local/factory_v1/paper_plane_state.sqlite"

STRAT_REL = "tests/fixtures/paper_shadow_accounting_control/strategy_v1_1_accounting.yaml"
EPOCH = "ACTIVATION-EPOCH-ACCOUNTING-PAPER-001"
KNOWN_EPOCHS = {EPOCH: {"mode": "PAPER"}}
MINT = "So11111111111111111111111111111111111111112"


def isolated_factory_root(tmp: Path) -> Path:
    config = load_runtime_config(ROOT)
    copy_rehost_allowlist(
        src_root=ROOT,
        dst_root=tmp,
        relatives=list(config["rehost_relative_paths"]),
    )
    return tmp


def _signal(signal_id: str, *, decision_at: str) -> dict:
    return {
        "schema": "smial.signal-decision",
        "schema_version": "1.0",
        "signal_decision_id": signal_id,
        "strategy_id": "STRAT-ACCOUNTING-CONTROL-A",
        "strategy_version": "V1",
        "activation_epoch_id": EPOCH,
        "source_hypothesis_refs": ["HYP-ACCOUNTING-SYNTH-A"],
        "mint": MINT,
        "decision_at": decision_at,
        "first_reliable_available_at": "2026-09-03T12:09:00Z",
        "action": "ENTER",
        "reason_code": "COCKPIT_FIXTURE_ENTER",
        "evidence_refs": [
            "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
        ],
    }


def _seed_ops(store: PaperPlaneStore) -> dict[str, str]:
    strategy = load_strategy_version(ROOT, STRAT_REL)
    ids = {}
    for idx, (sig, entry, exit_price, decision_at) in enumerate(
        (
            ("SIGDEC-COCKPIT-P1", "1.00", "1.10", "2026-09-03T12:10:00Z"),
            ("SIGDEC-COCKPIT-P2", "1.00", "0.90", "2026-09-03T12:11:00Z"),
            ("SIGDEC-COCKPIT-P3", "1.00", "0.80", "2026-09-03T12:12:00Z"),
        ),
        start=1,
    ):
        accepted = accept_signal_decision(
            ROOT,
            store,
            strategy=strategy,
            signal_decision=_signal(sig, decision_at=decision_at),
            known_activation_epochs=KNOWN_EPOCHS,
            mode="PAPER",
            as_of=decision_at,
        )
        pid = str(accepted["position_id"])
        store.apply_paper_entry_fill(
            position_id=pid,
            entry_unit_price_usd=entry,
            entry_gross_notional_usd="100",
            fee_bps=10,
            mode="PAPER",
        )
        store.apply_paper_exit_fill(position_id=pid, exit_unit_price_usd=exit_price, mode="PAPER")
        ids[f"p{idx}"] = pid
    accepted = accept_signal_decision(
        ROOT,
        store,
        strategy=strategy,
        signal_decision=_signal("SIGDEC-COCKPIT-P4", decision_at="2026-09-03T12:13:00Z"),
        known_activation_epochs=KNOWN_EPOCHS,
        mode="PAPER",
        as_of="2026-09-03T12:13:00Z",
    )
    p4 = str(accepted["position_id"])
    store.apply_paper_entry_fill(
        position_id=p4,
        entry_unit_price_usd="1.00",
        entry_gross_notional_usd="100",
        fee_bps=10,
        mode="PAPER",
    )
    store.record_position_mark(
        position_id=p4,
        mark_price_dec=None,
        as_of="2026-09-03T12:14:00Z",
        evidence_class="UNKNOWN",
    )
    accepted = accept_signal_decision(
        ROOT,
        store,
        strategy=strategy,
        signal_decision=_signal("SIGDEC-COCKPIT-P5", decision_at="2026-09-03T12:15:00Z"),
        known_activation_epochs=KNOWN_EPOCHS,
        mode="PAPER",
        as_of="2026-09-03T12:15:00Z",
    )
    p5 = str(accepted["position_id"])
    store.apply_paper_entry_fill(
        position_id=p5,
        entry_unit_price_usd="1.00",
        entry_gross_notional_usd="100",
        fee_bps=10,
        mode="PAPER",
    )
    store.apply_paper_exit_fill(
        position_id=p5, exit_unit_price_usd=None, mode="PAPER", unresolved=True
    )
    ids["p4"] = p4
    ids["p5"] = p5
    return ids


def _get(app: FactoryApplication, path: str) -> str:
    server = serve(app, host="127.0.0.1", port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        conn = HTTPConnection(host, port, timeout=3)
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
        conn = HTTPConnection(host, port, timeout=3)
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


class OwnerOperationsCockpitTests(unittest.TestCase):
    def test_operations_economics_and_commands(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            ops = OperationalStore((root / "ops.sqlite").resolve())
            paper = PaperPlaneStore((root / "local/factory_v1/paper_plane_state.sqlite").resolve())
            ids = _seed_ops(paper)
            app = FactoryApplication(root=root, store=ops, paper_plane_store=paper)
            try:
                home = _get(app, "/")
                operations = _get(app, "/operations")
                economics = _get(app, "/economics")
                self.assertIn('href="/operations"', home)
                self.assertIn(">Операции<", home)
                self.assertIn('href="/economics"', home)
                self.assertIn(">Экономика<", home)
                self.assertNotIn(">MARKET<", home)
                self.assertIn(ids["p4"], operations)
                self.assertIn("UNKNOWN", operations)
                self.assertIn(ids["p5"], operations)
                self.assertIn("UNRESOLVED", operations)
                self.assertIn("PAPER_RECONCILED_MODEL", operations)
                self.assertIn("LOSS_STREAK", operations)
                self.assertIn("NO_REALIZED_LIVE_PNL", economics)
                self.assertIn("NO_OWNER_FCF", economics)
                self.assertIn("NO_LIVE_CAPITAL", economics)
                self.assertIn("NO_NETRETURN_CLAIM", economics)
                self.assertIn("Отсутствующие live-метрики не показываются как $0.", economics)
                self.assertIn("30.37", economics)
                self.assertIn("REQUEST_CLOSE_ALL", operations)
                self.assertIn(
                    "Подтверждаю REQUEST_CLOSE_ALL против показанного снимка открытых позиций",
                    operations,
                )

                bot_id = paper.bots()[0]["bot_instance_id"]
                pause = _post(
                    app,
                    "/operations",
                    {
                        "command": "PAUSE_NEW_ENTRIES",
                        "bot_instance_id": bot_id,
                        "idempotency_key": "WB-PAUSE-1",
                    },
                )
                self.assertIn("ENTRIES_PAUSED", pause)
                self.assertTrue(bool(int(paper.get_bot(bot_id)["entries_paused"])))
                self.assertIn("REQUEST_CLOSE_POSITION", pause)

                close_one = _post(
                    app,
                    "/operations",
                    {
                        "command": "REQUEST_CLOSE_POSITION",
                        "position_id": ids["p4"],
                        "idempotency_key": "WB-CLOSE-1",
                    },
                )
                self.assertIn("EXIT_REQUIRED", close_one)
                self.assertEqual(paper.get_position(ids["p4"])["state"], "EXIT_REQUIRED")

                no_confirm = _post(
                    app,
                    "/operations",
                    {
                        "command": "REQUEST_CLOSE_ALL",
                        "bot_instance_id": bot_id,
                        "expected_open_position_set_sha256": "0" * 64,
                        "idempotency_key": "WB-CLOSE-ALL-N",
                    },
                )
                self.assertIn("CLOSE_ALL_CONFIRMATION_REQUIRED", no_confirm)

                ops_proj = app.operations_projection()
                stale = _post(
                    app,
                    "/operations",
                    {
                        "command": "REQUEST_CLOSE_ALL",
                        "bot_instance_id": bot_id,
                        "expected_open_position_set_sha256": "0" * 64,
                        "confirm_close_all": "1",
                        "idempotency_key": "WB-CLOSE-ALL-STALE",
                    },
                )
                self.assertIn("STALE_OPERATOR_SNAPSHOT", stale)

                snap = ops_proj["open_position_set_sha256"]
                self.assertEqual(snap, open_position_set_sha256(ops_proj["open_position_ids"]))
                ok = _post(
                    app,
                    "/operations",
                    {
                        "command": "REQUEST_CLOSE_ALL",
                        "bot_instance_id": bot_id,
                        "expected_open_position_set_sha256": snap,
                        "confirm_close_all": "1",
                        "idempotency_key": "WB-CLOSE-ALL-OK",
                    },
                )
                self.assertNotIn("STALE_OPERATOR_SNAPSHOT", ok)
                dup = app.apply_paper_operator_command(
                    {
                        "command_type": "REQUEST_CLOSE_ALL",
                        "bot_instance_id": bot_id,
                        "expected_open_position_set_sha256": snap,
                        "idempotency_key": "WB-CLOSE-ALL-OK",
                    }
                )
                self.assertTrue(dup.get("idempotent"))

                resume = _post(
                    app,
                    "/operations",
                    {
                        "command": "RESUME_NEW_ENTRIES",
                        "bot_instance_id": bot_id,
                        "idempotency_key": "WB-RESUME-1",
                    },
                )
                self.assertNotIn("ENTRIES_PAUSED", resume)
                self.assertEqual(int(paper.get_bot(bot_id)["entries_paused"]), 0)

                stop = _post(
                    app,
                    "/operations",
                    {
                        "command": "STOP_BOT",
                        "bot_instance_id": bot_id,
                        "idempotency_key": "WB-STOP-1",
                    },
                )
                self.assertIn("DRAINING", stop)

                missing_bot = _post(
                    app,
                    "/operations",
                    {
                        "command": "PAUSE_NEW_ENTRIES",
                        "idempotency_key": "WB-PAUSE-NOBOT",
                    },
                )
                self.assertIn("BOT_INSTANCE_ID_REQUIRED", missing_bot)

                source = inspect.getsource(workbench_mod)
                self.assertNotIn("sqlite3", source)
                self.assertNotIn("PaperPlaneStore", source)
            finally:
                paper.close()
                ops.close()

    def test_legacy_surfaces_still_work(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            store = OperationalStore((root / "ops.sqlite").resolve())
            app = FactoryApplication(root=root, store=store)
            paper_path = root / PAPER_STORE_RELATIVE
            try:
                self.assertIn('href="/research"', _get(app, "/research"))
                self.assertIn(">Исследования<", _get(app, "/research"))
                self.assertIn("Runtime", _get(app, "/system"))
                self.assertFalse(paper_path.is_file())
            finally:
                store.close()

    def test_position_questions_without_git_archaeology(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            (root / ACCEPTANCE_RELATIVE).unlink()
            ops = OperationalStore((root / "ops.sqlite").resolve())
            paper = PaperPlaneStore((root / PAPER_STORE_RELATIVE).resolve())
            ids = _seed_ops(paper)
            app = FactoryApplication(root=root, store=ops, paper_plane_store=paper)
            try:
                self.assertTrue(app.read_model()["git_archaeology_required"])
                operations = _get(app, "/operations")
                economics = _get(app, "/economics")
                self.assertIn(ids["p4"], operations)
                self.assertIn(ids["p5"], operations)
                self.assertIn("UNKNOWN", operations)
                self.assertIn("NO_REALIZED_LIVE_PNL", economics)
                ops_model = app.read_model(surface="OPERATIONS")
                self.assertEqual(ops_model["cockpit"]["terminal"], "OWNER_OPERATIONS_COCKPIT_PASS")
            finally:
                paper.close()
                ops.close()


if __name__ == "__main__":
    unittest.main()
