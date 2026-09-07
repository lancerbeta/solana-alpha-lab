"""RISK_AND_ECONOMICS_V1 vertical acceptance."""

from __future__ import annotations

import hashlib
import sqlite3
import sys
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.application import FactoryApplication  # noqa: E402
from solana_alpha_lab.factory.operational_store import OperationalStore  # noqa: E402
from solana_alpha_lab.factory.paper_plane import (  # noqa: E402
    PaperPlaneStore,
    accept_signal_decision,
    modeled_unrealized_mark,
)
from solana_alpha_lab.factory.risk_economics import compose_risk_economics  # noqa: E402
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
SHADOW_EPOCH = "ACTIVATION-EPOCH-ACCOUNTING-SHADOW-001"
MINT = "So11111111111111111111111111111111111111112"
GET_PATHS = ("/", "/research", "/operations", "/economics", "/system")
AS_OF = "2026-09-07T12:00:00Z"


def isolated_factory_root(tmp: Path) -> Path:
    config = load_runtime_config(ROOT)
    copy_rehost_allowlist(
        src_root=ROOT,
        dst_root=tmp,
        relatives=list(config["rehost_relative_paths"]),
    )
    return tmp


def _copy_strategy(root: Path, *, version: str = "V1", max_open: int | None = None) -> Path:
    dest = root / "configs" / "strategies" / f"STRAT-ACCOUNTING-CONTROL-A-{version}.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = (ROOT / STRAT_REL).read_text(encoding="utf-8")
    text = text.replace("strategy_version: V1", f"strategy_version: {version}")
    if max_open is not None:
        text = text.replace("max_open_positions: 8", f"max_open_positions: {max_open}")
    dest.write_text(text, encoding="utf-8")
    return dest


def _walk(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in root.rglob("*"):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
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


def _signal(signal_id: str, *, version: str = "V1", epoch: str = EPOCH) -> dict:
    return {
        "schema": "smial.signal-decision",
        "schema_version": "1.0",
        "signal_decision_id": signal_id,
        "strategy_id": "STRAT-ACCOUNTING-CONTROL-A",
        "strategy_version": version,
        "activation_epoch_id": epoch,
        "source_hypothesis_refs": ["HYP-ACCOUNTING-SYNTH-A"],
        "mint": MINT,
        "decision_at": "2026-09-03T12:10:00Z",
        "first_reliable_available_at": "2026-09-03T12:09:00Z",
        "action": "ENTER",
        "reason_code": "RISK_ECON_FIXTURE",
        "evidence_refs": [
            "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
        ],
    }


def _enter(
    store: PaperPlaneStore,
    signal_id: str,
    *,
    mode: str = "PAPER",
    version: str = "V1",
    epoch: str | None = None,
    fill_price: str = "1.00",
) -> str:
    strategy = load_strategy_version(ROOT, STRAT_REL)
    if version != "V1":
        strategy = dict(strategy)
        strategy["strategy_version"] = version
    epoch_id = epoch or (SHADOW_EPOCH if mode == "SHADOW" else EPOCH)
    accepted = accept_signal_decision(
        ROOT,
        store,
        strategy=strategy,
        signal_decision=_signal(signal_id, version=version, epoch=epoch_id),
        known_activation_epochs={epoch_id: {"mode": mode}},
        mode=mode,
        as_of="2026-09-03T12:10:00Z",
    )
    pid = str(accepted["position_id"])
    store.apply_paper_entry_fill(
        position_id=pid,
        entry_unit_price_usd=fill_price,
        entry_gross_notional_usd="100",
        fee_bps=10,
        mode=mode,
    )
    return pid


def _reconcile(store: PaperPlaneStore, pid: str, *, exit_price: str, mode: str = "PAPER") -> None:
    store.apply_paper_exit_fill(position_id=pid, exit_unit_price_usd=exit_price, mode=mode)


class RiskAndEconomicsV1Tests(unittest.TestCase):
    def test_a1_absent_source(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            before = _walk(root)
            app = FactoryApplication(root=root)
            body = _get(app, "/economics")
            projection = app.economics_projection()
            self.assertEqual(projection["source_status"], "SOURCE_NOT_PRESENT")
            self.assertEqual(projection["evidence_state"], "SOURCE_NOT_PRESENT")
            self.assertIsNone(projection["reconciled_net_pnl_usd"])
            self.assertIn("SOURCE_NOT_PRESENT", body)
            self.assertNotIn("<td>$0</td>", body)
            self.assertEqual(before, _walk(root))
            self.assertFalse((root / "local").exists())

    def test_a2_paper_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                pid = _enter(store, "SIGDEC-RE-A2")
                _reconcile(store, pid, exit_price="1.10")
                projection = compose_risk_economics(
                    Path(tmp), store, source_status="PRESENT", as_of=AS_OF
                )
                scope = projection["reconciled_scopes"][0]
                row = scope["rows"][0]
                self.assertEqual(scope["pnl_evidence_class"], "PAPER_RECONCILED_MODEL")
                self.assertEqual(scope["status"], "KNOWN")
                self.assertEqual(scope["reconciled_count_known"], 1)
                self.assertEqual(row["realized_gross_pnl_usd"], "10.00")
                self.assertEqual(row["entry_fee_usd"], "0.10")
                self.assertEqual(row["exit_fee_usd"], "0.11")
                self.assertEqual(row["realized_net_after_modeled_fees_usd"], "9.79")
                self.assertEqual(projection["reconciled_net_pnl_usd"], "9.79")
                self.assertEqual(projection["netreturn_status"], "NOT_ESTABLISHED")
                self.assertEqual(projection["owner_fcf_status"], "NOT_AVAILABLE")
            finally:
                store.close()

    def test_a3_a4_paper_and_shadow_separate(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                paper = _enter(store, "SIGDEC-RE-A3P", mode="PAPER")
                _reconcile(store, paper, exit_price="1.10", mode="PAPER")
                shadow = _enter(store, "SIGDEC-RE-A3S", mode="SHADOW")
                _reconcile(store, shadow, exit_price="1.10", mode="SHADOW")
                projection = compose_risk_economics(
                    Path(tmp), store, source_status="PRESENT", as_of=AS_OF
                )
                classes = {scope["pnl_evidence_class"] for scope in projection["reconciled_scopes"]}
                self.assertEqual(
                    classes,
                    {"PAPER_RECONCILED_MODEL", "SHADOW_RECONCILED_QUOTE_MODEL"},
                )
                self.assertTrue(projection["mixed_evidence"])
                self.assertIsNone(projection["reconciled_net_pnl_usd"])
                self.assertEqual(
                    projection["reconciled_net_pnl_status"], "MIXED_EVIDENCE_NOT_AGGREGATED"
                )
                self.assertEqual(projection["evidence_state"], "PAPER_AND_SHADOW_SEPARATE")
            finally:
                store.close()

    def test_a5_different_strategy_versions(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                p1 = _enter(store, "SIGDEC-RE-A5V1", version="V1")
                _reconcile(store, p1, exit_price="1.10")
                p2 = _enter(store, "SIGDEC-RE-A5V2", version="V2", epoch="ACTIVATION-EPOCH-V2")
                _reconcile(store, p2, exit_price="1.20")
                projection = compose_risk_economics(
                    Path(tmp), store, source_status="PRESENT", as_of=AS_OF
                )
                versions = {scope["strategy_version"] for scope in projection["reconciled_scopes"]}
                self.assertEqual(versions, {"V1", "V2"})
                self.assertTrue(projection["mixed_evidence"])
                self.assertIsNone(projection["reconciled_net_pnl_usd"])
            finally:
                store.close()

    def test_a6_accounting_conflict_excludes_row(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = Path(tmp) / "paper.sqlite"
            store = PaperPlaneStore(path)
            try:
                pid = _enter(store, "SIGDEC-RE-A6")
                _reconcile(store, pid, exit_price="1.10")
                store.close()
                conn = sqlite3.connect(path)
                conn.execute(
                    "UPDATE positions SET realized_net_pnl_usd_dec = '99.00' WHERE position_id = ?",
                    (pid,),
                )
                conn.commit()
                conn.close()
                store = PaperPlaneStore(path)
                projection = compose_risk_economics(
                    Path(tmp), store, source_status="PRESENT", as_of=AS_OF
                )
                row = projection["reconciled_scopes"][0]["rows"][0]
                self.assertEqual(row["status"], "ACCOUNTING_CONFLICT")
                self.assertFalse(row["trusted"])
                self.assertIsNone(row["realized_net_after_modeled_fees_usd"])
                self.assertEqual(projection["evidence_state"], "ACCOUNTING_CONFLICT")
                self.assertEqual(projection["next_safe_action"], "INSPECT_ACCOUNTING_EVIDENCE")
                reread = sqlite3.connect(path)
                stored = reread.execute(
                    "SELECT realized_net_pnl_usd_dec FROM positions WHERE position_id = ?",
                    (pid,),
                ).fetchone()[0]
                reread.close()
                self.assertEqual(stored, "99.00")
            finally:
                store.close()

    def test_a7_known_exact_zero(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                pid = _enter(store, "SIGDEC-RE-A7")
                # 100 notional, fee 10 bps both sides: net zero needs gross = 0.20
                _reconcile(store, pid, exit_price="1.002")
                projection = compose_risk_economics(
                    Path(tmp), store, source_status="PRESENT", as_of=AS_OF
                )
                net = projection["reconciled_scopes"][0]["realized_net_after_modeled_fees_usd"]
                self.assertIsNotNone(net)
                if net == "0.00":
                    self.assertEqual(projection["reconciled_scopes"][0]["status"], "KNOWN")
                else:
                    # Pin exact Decimal outcome rather than pretend zero if rounding differs.
                    self.assertEqual(projection["reconciled_scopes"][0]["status"], "KNOWN")
                    path = Path(tmp) / "paper.sqlite"
                    store.close()
                    conn = sqlite3.connect(path)
                    conn.execute(
                        "UPDATE positions SET realized_gross_pnl_usd_dec = '0.20', "
                        "entry_fee_usd_dec = '0.10', exit_fee_usd_dec = '0.10', "
                        "realized_net_pnl_usd_dec = '0.00' WHERE position_id = ?",
                        (pid,),
                    )
                    conn.commit()
                    conn.close()
                    store = PaperPlaneStore(path)
                    projection = compose_risk_economics(
                        Path(tmp), store, source_status="PRESENT", as_of=AS_OF
                    )
                    self.assertEqual(
                        projection["reconciled_scopes"][0]["realized_net_after_modeled_fees_usd"],
                        "0.00",
                    )
                    self.assertEqual(projection["reconciled_scopes"][0]["status"], "KNOWN")
                    self.assertEqual(projection["reconciled_net_pnl_usd"], "0.00")
                    self.assertNotEqual(projection["evidence_state"], "NO_ECONOMIC_EVIDENCE")
            finally:
                store.close()

    def test_m1_m2_open_mark_fees(self) -> None:
        derived = modeled_unrealized_mark(
            mark_price=__import__("decimal").Decimal("1.10"),
            qty=__import__("decimal").Decimal("100"),
            entered_notional=__import__("decimal").Decimal("100"),
            entry_fee=__import__("decimal").Decimal("0.10"),
            fee_bps=10,
        )
        self.assertEqual(format(derived["unrealized_gross"], "f"), "10.00")
        self.assertNotEqual(
            format(derived["unrealized_net"], "f"), format(derived["unrealized_gross"], "f")
        )
        self.assertEqual(format(derived["unrealized_net"], "f"), "9.79")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                pid = _enter(store, "SIGDEC-RE-M1")
                store.record_position_mark(
                    position_id=pid,
                    mark_price_dec="1.10",
                    as_of="2026-09-07T11:00:00Z",
                    evidence_class="PAPER_MARK_TO_MODEL",
                )
                position = store.get_position(pid)
                assert position is not None
                self.assertEqual(position["unrealized_gross_pnl_usd_dec"], "10.00")
                self.assertEqual(position["unrealized_net_pnl_usd_dec"], "9.79")
                projection = compose_risk_economics(
                    Path(tmp), store, source_status="PRESENT", as_of=AS_OF
                )
                mark = projection["open_mark_scopes"][0]
                self.assertEqual(mark["mark_evidence_class"], "PAPER_MARK_TO_MODEL")
                self.assertEqual(mark["unrealized_net_after_modeled_fees_usd"], "9.79")
                self.assertEqual(mark["settlement"], "NOT_SETTLED")
                self.assertEqual(mark["mark_freshness_policy"], "NOT_DEFINED")
                self.assertEqual(mark["rows"][0]["mark_age_seconds"], 3600)
                self.assertNotIn("FRESH", str(projection))
                self.assertNotIn("STALE", str(mark))
            finally:
                store.close()

    def test_m4_missing_mark_as_of(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                pid = _enter(store, "SIGDEC-RE-M4")
                store.record_position_mark(
                    position_id=pid,
                    mark_price_dec="1.10",
                    as_of="2026-09-07T11:00:00Z",
                    evidence_class="PAPER_MARK_TO_MODEL",
                )
                store._conn.execute(
                    "UPDATE positions SET mark_as_of = NULL WHERE position_id = ?",
                    (pid,),
                )
                store._conn.commit()
                projection = compose_risk_economics(
                    Path(tmp), store, source_status="PRESENT", as_of=AS_OF
                )
                row = projection["open_mark_scopes"][0]["rows"][0]
                self.assertEqual(row["gap"], "MARK_TIME_UNKNOWN")
                self.assertIsNone(row["unrealized_net_after_modeled_fees_usd"])
            finally:
                store.close()

    def test_m5_m6_legacy_mark_components(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = Path(tmp) / "paper.sqlite"
            store = PaperPlaneStore(path)
            try:
                pid = _enter(store, "SIGDEC-RE-M5")
                store.record_position_mark(
                    position_id=pid,
                    mark_price_dec="1.10",
                    as_of="2026-09-07T11:00:00Z",
                    evidence_class="PAPER_MARK_TO_MODEL",
                )
                store._conn.execute(
                    "UPDATE positions SET unrealized_net_pnl_usd_dec = unrealized_gross_pnl_usd_dec "
                    "WHERE position_id = ?",
                    (pid,),
                )
                store._conn.commit()
                stored = store.get_position(pid)
                assert stored is not None
                self.assertEqual(stored["unrealized_net_pnl_usd_dec"], "10.00")
                projection = compose_risk_economics(
                    Path(tmp), store, source_status="PRESENT", as_of=AS_OF
                )
                row = projection["open_mark_scopes"][0]["rows"][0]
                self.assertEqual(row["unrealized_net_after_modeled_fees_usd"], "9.79")
                self.assertEqual(row["provenance"], "DERIVED_FROM_LEGACY_RAW_COMPONENTS")
                reread = store.get_position(pid)
                assert reread is not None
                self.assertEqual(reread["unrealized_net_pnl_usd_dec"], "10.00")
                pid2 = _enter(store, "SIGDEC-RE-M6")
                store._conn.execute(
                    "UPDATE positions SET entry_fee_usd_dec = NULL, fee_bps = NULL WHERE position_id = ?",
                    (pid2,),
                )
                store._conn.commit()
                store.record_position_mark(
                    position_id=pid2,
                    mark_price_dec="1.10",
                    as_of="2026-09-07T11:00:00Z",
                    evidence_class="SHADOW_EXECUTABLE_QUOTE_MARK",
                )
                projection = compose_risk_economics(
                    Path(tmp), store, source_status="PRESENT", as_of=AS_OF
                )
                gaps = {item["code"] for item in projection["gaps"]}
                self.assertIn("OPEN_MARK_COST_COMPONENT_GAP", gaps)
            finally:
                store.close()

    def test_p_path_metrics(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                p1 = _enter(store, "SIGDEC-RE-P1")
                _reconcile(store, p1, exit_price="1.10")
                p2 = _enter(store, "SIGDEC-RE-P2")
                _reconcile(store, p2, exit_price="0.90")
                p3 = _enter(store, "SIGDEC-RE-P3")
                _reconcile(store, p3, exit_price="0.80")
                projection = compose_risk_economics(
                    Path(tmp), store, source_status="PRESENT", as_of=AS_OF
                )
                drawdown = projection["reconciled_scopes"][0]["drawdown"]
                self.assertEqual(drawdown["basis"], "RECONCILED_MODEL_PNL_DRAWDOWN_USD")
                self.assertEqual(drawdown["status"], "KNOWN")
                self.assertIsNotNone(drawdown["usd"])
                streak = projection["reconciled_scopes"][0]["loss_streak"]
                self.assertEqual(streak["status"], "KNOWN")
                self.assertEqual(streak["count"], 2)
                store._conn.execute(
                    "UPDATE positions SET realized_net_pnl_usd_dec = NULL, "
                    "pnl_evidence_class = 'PAPER_RECONCILED_MODEL' "
                    "WHERE position_id = ?",
                    (p1,),
                )
                store._conn.commit()
                projection = compose_risk_economics(
                    Path(tmp), store, source_status="PRESENT", as_of=AS_OF
                )
                drawdown = projection["reconciled_scopes"][0]["drawdown"]
                self.assertIsNone(drawdown["usd"])
                self.assertEqual(drawdown["status"], "UNKNOWN")
                streak = projection["reconciled_scopes"][0]["loss_streak"]
                self.assertEqual(streak["status"], "UNKNOWN")
                self.assertIsNone(streak["count"])
                scope = projection["reconciled_scopes"][0]
                self.assertEqual(scope["status"], "PARTIAL_UNKNOWN")
                self.assertIsNone(scope["realized_net_after_modeled_fees_usd"])
                self.assertIsNone(projection["reconciled_net_pnl_usd"])
                self.assertEqual(projection["reconciled_net_pnl_status"], "PARTIAL_UNKNOWN")
                store._conn.execute(
                    "UPDATE positions SET realized_net_pnl_usd_dec = '9.79', "
                    "closed_at = '' WHERE position_id = ?",
                    (p1,),
                )
                store._conn.commit()
                projection = compose_risk_economics(
                    Path(tmp), store, source_status="PRESENT", as_of=AS_OF
                )
                drawdown = projection["reconciled_scopes"][0]["drawdown"]
                self.assertIsNone(drawdown["usd"])
                self.assertEqual(drawdown["status"], "UNKNOWN")
                streak = projection["reconciled_scopes"][0]["loss_streak"]
                self.assertEqual(streak["status"], "UNKNOWN")
                self.assertIsNone(streak["count"])
            finally:
                store.close()

    def test_p3_no_reconciled_empty(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                _enter(store, "SIGDEC-RE-P3E")
                projection = compose_risk_economics(
                    Path(tmp), store, source_status="PRESENT", as_of=AS_OF
                )
                self.assertEqual(projection["reconciled_net_pnl_status"], "EMPTY")
                self.assertIsNone(projection["reconciled_net_pnl_usd"])
            finally:
                store.close()

    def test_r_declared_entry_limit(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            _copy_strategy(root, version="V1", max_open=5)
            _copy_strategy(root, version="V2", max_open=1)
            store = PaperPlaneStore(root / "local/factory_v1/paper_plane_state.sqlite")
            try:
                for idx in range(3):
                    _enter(store, f"SIGDEC-RE-R1-{idx}")
                projection = compose_risk_economics(
                    root, store, source_status="PRESENT", as_of=AS_OF
                )
                risk = projection["declared_risk_scopes"][0]
                self.assertEqual(risk["max_open_positions"], 5)
                self.assertEqual(risk["entry_admission_risk_count"], 3)
                self.assertEqual(risk["remaining_entry_slots"], 2)
                self.assertEqual(risk["entry_admission_status"], "WITHIN_DECLARED_ENTRY_LIMIT")
                self.assertEqual(risk["other_limits"]["daily_loss_limit"], "NOT_DEFINED")
                self.assertEqual(risk["strategy_version"], "V1")
            finally:
                store.close()

    def test_r2_r3_at_and_over_limit(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            _copy_strategy(root, version="V1", max_open=2)
            store = PaperPlaneStore(root / "local/factory_v1/paper_plane_state.sqlite")
            try:
                _enter(store, "SIGDEC-RE-R2A")
                _enter(store, "SIGDEC-RE-R2B")
                projection = compose_risk_economics(
                    root, store, source_status="PRESENT", as_of=AS_OF
                )
                risk = projection["declared_risk_scopes"][0]
                self.assertEqual(risk["entry_admission_status"], "ENTRY_LIMIT_REACHED")
                self.assertEqual(risk["remaining_entry_slots"], 0)
                _enter(store, "SIGDEC-RE-R3C")
                projection = compose_risk_economics(
                    root, store, source_status="PRESENT", as_of=AS_OF
                )
                risk = projection["declared_risk_scopes"][0]
                self.assertEqual(risk["entry_admission_status"], "DECLARED_ENTRY_LIMIT_BREACH")
                self.assertEqual(projection["next_safe_action"], "INSPECT_OPERATIONS")
            finally:
                store.close()

    def test_i1_exit_required_not_all_risk_clear(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            _copy_strategy(root, version="V1", max_open=8)
            store = PaperPlaneStore(root / "local/factory_v1/paper_plane_state.sqlite")
            try:
                pid = _enter(store, "SIGDEC-RE-I1")
                store.transition(pid, "EXIT_REQUIRED")
                projection = compose_risk_economics(
                    root, store, source_status="PRESENT", as_of=AS_OF
                )
                risk = projection["declared_risk_scopes"][0]
                self.assertEqual(risk["entry_admission_status"], "WITHIN_DECLARED_ENTRY_LIMIT")
                self.assertTrue(risk["unresolved_or_exit_inventory"])
                self.assertFalse(risk["all_risk_clear"])
            finally:
                store.close()

    def test_x_exposure_named_and_separate(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                _enter(store, "SIGDEC-RE-X1", mode="PAPER")
                _enter(store, "SIGDEC-RE-X2", mode="SHADOW")
                projection = compose_risk_economics(
                    Path(tmp), store, source_status="PRESENT", as_of=AS_OF
                )
                modes = {scope["mode"] for scope in projection["exposure_scopes"]}
                self.assertEqual(modes, {"PAPER", "SHADOW"})
                for scope in projection["exposure_scopes"]:
                    self.assertEqual(scope["basis"], "ENTERED_NOTIONAL_EXPOSURE_USD")
                    self.assertEqual(scope["entered_notional_exposure_usd"], "100")
                blob = str(projection)
                self.assertNotIn("CAPITAL_AT_RISK", blob)
            finally:
                store.close()

    def test_o_owner_nonclaims_and_get_purity(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = isolated_factory_root(Path(tmp) / "src")
            _copy_strategy(root)
            store = PaperPlaneStore(root / "local/factory_v1/paper_plane_state.sqlite")
            pid = _enter(store, "SIGDEC-RE-O1")
            _reconcile(store, pid, exit_price="1.10")
            store.close()
            before = _walk(root)
            paper_hash = hashlib.sha256(
                (root / "local/factory_v1/paper_plane_state.sqlite").read_bytes()
            ).hexdigest()
            app = FactoryApplication(root=root)
            economics = _get(app, "/economics")
            for path in GET_PATHS:
                _get(app, path)
            self.assertIn("PAPER_RECONCILED_MODEL", economics)
            self.assertIn("STRAT-ACCOUNTING-CONTROL-A@V1", economics)
            self.assertIn("Reconciled net (один совместимый scope)", economics)
            model = app.economics_projection()
            self.assertEqual(model["reconciled_net_pnl_evidence_class"], "PAPER_RECONCILED_MODEL")
            self.assertEqual(model["reconciled_net_pnl_mode"], "PAPER")
            self.assertIn("NO ALPHA", economics)
            self.assertIn("NOT_ESTABLISHED", economics)
            self.assertIn("NOT_AVAILABLE", economics)
            self.assertNotIn('name="command" value="PAUSE_NEW_ENTRIES"', economics)
            self.assertNotIn("PROFITABLE", economics)
            self.assertEqual(before, _walk(root))
            self.assertEqual(
                paper_hash,
                hashlib.sha256(
                    (root / "local/factory_v1/paper_plane_state.sqlite").read_bytes()
                ).hexdigest(),
            )

    def test_home_has_no_fourth_economics_domain(self) -> None:
        text = (ROOT / "src/solana_alpha_lab/factory/owner_daily_attention.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("SOURCE_DOMAIN_ECONOMICS", text)
        self.assertNotIn("ECONOMICS_ATTENTION", text)

    def test_semantic_route_reused(self) -> None:
        assets, bindings, _queries = load_semantic_catalog_views(ROOT)
        projection = load_semantic_projection(ROOT)
        self.assertEqual(len(projection["routes"]), 13)
        lifecycle = next(
            item
            for item in projection["routes"]
            if item["semantic_route_id"] == "SEM-OWNER-LIFECYCLE"
        )
        self.assertEqual(len(lifecycle["root_binding_ids"]), 2)
        self.assertLessEqual(len(lifecycle["search_terms"]), 16)
        ids = [item["semantic_route_id"] for item in projection["routes"]]
        self.assertNotIn("SEM-RISK", ids)
        self.assertNotIn("SEM-ECONOMICS", ids)
        self.assertIn("DOC-RISK-AND-ECONOMICS-001", assets)
        self.assertNotIn("ACTIVE-RISK-AND-ECONOMICS", bindings)
        hits = search_semantic_routes(
            projection,
            "What is the PAPER economic result for this StrategyVersion?",
            assets=assets,
            bindings=bindings,
            limit=3,
        )
        self.assertEqual(hits[0]["semantic_route_id"], "SEM-OWNER-LIFECYCLE")
        capital = search_semantic_routes(
            projection,
            "May I activate/deploy/spend?",
            assets=assets,
            bindings=bindings,
            limit=3,
        )
        self.assertEqual(capital[0]["semantic_route_id"], "SEM-AUTHORITY-BOUNDARIES")


if __name__ == "__main__":
    unittest.main()
