"""FACTORY_STRATEGY_EXECUTION_BOUNDARY_V1 focused acceptance suite."""

from __future__ import annotations

import inspect
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.paper_plane import (  # noqa: E402
    PaperPlaneError,
    PaperPlaneStore,
    accept_exit_decision,
    accept_signal_decision,
    run_commissioning,
    signal_kind_for,
)
from solana_alpha_lab.factory.strategy_runtime import (  # noqa: E402
    load_strategy_version,
    normalize_strategy,
    position_id_for_signal_decision,
    validate_exit_decision,
    validate_signal_decision,
)

FIXTURES = ROOT / "tests" / "fixtures" / "factory_strategy_execution_boundary"
LEGACY_STRAT = "configs/strategies/STRAT-V-EARLY-LIQ-FLOOR-COMMISSIONING-V1.yaml"
EPOCH = "ACTIVATION-EPOCH-BOUNDARY-PAPER-001"
KNOWN_EPOCHS = {EPOCH: {"mode": "PAPER"}}


def _load_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class StrategyExecutionBoundaryTests(unittest.TestCase):
    def test_legacy_v1_0_loads_and_behaves(self) -> None:
        strategy = load_strategy_version(ROOT, LEGACY_STRAT)
        self.assertEqual(strategy["schema_version"], "1.0")
        self.assertTrue(strategy["commissioning_only"])
        self.assertEqual(
            signal_kind_for(strategy, {"X_LIQUIDITY_USD": 2500}),
            "SIMULATED_FILL",
        )
        self.assertEqual(
            signal_kind_for(strategy, {"X_LIQUIDITY_USD": 1000}),
            "NO_SIGNAL",
        )
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "paper.sqlite"
            result = run_commissioning(
                ROOT,
                strategy_relatives=[LEGACY_STRAT],
                store_path=store_path,
                cohort=[
                    {"mint": "So11111111111111111111111111111111111111112", "X_LIQUIDITY_USD": 2500},
                    {"mint": "So22222222222222222222222222222222222222222", "X_LIQUIDITY_USD": 500},
                ],
            )
        self.assertEqual(result["per_strategy"][0]["simulated_fills"], 1)
        self.assertEqual(result["per_strategy"][0]["no_signal_or_unknown"], 1)

    def test_v1_1_schema_accepts_candidates_without_feature_names(self) -> None:
        for name in (
            "strategy_v1_1_candidate_a.yaml",
            "strategy_v1_1_candidate_b.yaml",
        ):
            strategy = load_strategy_version(
                ROOT, f"tests/fixtures/factory_strategy_execution_boundary/{name}"
            )
            self.assertEqual(strategy["schema_version"], "1.1")
            blob = json.dumps(strategy)
            self.assertNotIn("X_LIQUIDITY_USD", blob)
            self.assertNotIn("X_NETFLOW_SHARE", blob)
            self.assertNotIn("signal_rule", blob)
            self.assertNotIn("bin_threshold", blob)
            normalized = normalize_strategy(strategy)
            self.assertEqual(normalized["runtime_path"], "CANDIDATE_V1_1")

    def test_enter_opens_through_canonical_signal(self) -> None:
        strategy = load_strategy_version(
            ROOT,
            "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml",
        )
        decision = _load_json("signal_decision_enter_a.json")
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                result = accept_signal_decision(
                    ROOT,
                    store,
                    strategy=strategy,
                    signal_decision=decision,
                    known_activation_epochs=KNOWN_EPOCHS,
                )
                self.assertTrue(result["opened"])
                position = store.get_position(result["position_id"])
                assert position is not None
                self.assertEqual(position["state"], "OPEN")
                self.assertEqual(position["signal_decision_id"], decision["signal_decision_id"])
                bot = store.get_bot(result["bot_instance_id"])
                assert bot is not None
                self.assertEqual(bot["activation_epoch_id"], EPOCH)
                self.assertEqual(bot["runtime_schema_version"], "1.1")
            finally:
                store.close()

    def test_non_enter_actions_do_not_open(self) -> None:
        strategy = load_strategy_version(
            ROOT,
            "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml",
        )
        for name in (
            "signal_decision_no_enter.json",
            "signal_decision_unknown.json",
            "signal_decision_blocked.json",
        ):
            with tempfile.TemporaryDirectory() as tmp:
                store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
                try:
                    result = accept_signal_decision(
                        ROOT,
                        store,
                        strategy=strategy,
                        signal_decision=_load_json(name),
                        known_activation_epochs=KNOWN_EPOCHS,
                    )
                    self.assertFalse(result["opened"])
                    self.assertEqual(store.positions(), [])
                finally:
                    store.close()

    def test_future_available_enter_forbidden(self) -> None:
        strategy = load_strategy_version(
            ROOT,
            "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml",
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                with self.assertRaisesRegex(
                    PaperPlaneError, "SIGNAL_FUTURE_AVAILABLE_ENTER_FORBIDDEN"
                ):
                    accept_signal_decision(
                        ROOT,
                        store,
                        strategy=strategy,
                        signal_decision=_load_json("signal_decision_future_available.json"),
                        known_activation_epochs=KNOWN_EPOCHS,
                    )
            finally:
                store.close()

    def test_missing_activation_fails_closed(self) -> None:
        strategy = load_strategy_version(
            ROOT,
            "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml",
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                with self.assertRaisesRegex(PaperPlaneError, "ACTIVATION_EPOCH_UNRESOLVED"):
                    accept_signal_decision(
                        ROOT,
                        store,
                        strategy=strategy,
                        signal_decision=_load_json("signal_decision_enter_a.json"),
                        known_activation_epochs={},
                    )
            finally:
                store.close()

    def test_same_mint_distinct_signal_ids(self) -> None:
        strategy = load_strategy_version(
            ROOT,
            "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml",
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                a = accept_signal_decision(
                    ROOT,
                    store,
                    strategy=strategy,
                    signal_decision=_load_json("signal_decision_enter_a.json"),
                    known_activation_epochs=KNOWN_EPOCHS,
                )
                b = accept_signal_decision(
                    ROOT,
                    store,
                    strategy=strategy,
                    signal_decision=_load_json("signal_decision_enter_b_same_mint.json"),
                    known_activation_epochs=KNOWN_EPOCHS,
                )
                self.assertNotEqual(a["position_id"], b["position_id"])
                self.assertEqual(len(store.positions()), 2)
                mints = {p["mint"] for p in store.positions()}
                self.assertEqual(len(mints), 1)
            finally:
                store.close()

    def test_same_signal_idempotent(self) -> None:
        strategy = load_strategy_version(
            ROOT,
            "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml",
        )
        decision = _load_json("signal_decision_enter_a.json")
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                first = accept_signal_decision(
                    ROOT,
                    store,
                    strategy=strategy,
                    signal_decision=decision,
                    known_activation_epochs=KNOWN_EPOCHS,
                )
                second = accept_signal_decision(
                    ROOT,
                    store,
                    strategy=strategy,
                    signal_decision=decision,
                    known_activation_epochs=KNOWN_EPOCHS,
                )
                self.assertTrue(second.get("idempotent"))
                self.assertEqual(first["position_id"], second["position_id"])
                self.assertEqual(len(store.positions()), 1)
            finally:
                store.close()

    def test_exit_decision_advances_without_fill_claim(self) -> None:
        strategy = load_strategy_version(
            ROOT,
            "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml",
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                opened = accept_signal_decision(
                    ROOT,
                    store,
                    strategy=strategy,
                    signal_decision=_load_json("signal_decision_enter_a.json"),
                    known_activation_epochs=KNOWN_EPOCHS,
                )
                exit_decision = _load_json("exit_decision_exit.json")
                self.assertEqual(exit_decision["position_id"], opened["position_id"])
                result = accept_exit_decision(
                    ROOT,
                    store,
                    strategy=strategy,
                    exit_decision=exit_decision,
                    known_activation_epochs=KNOWN_EPOCHS,
                )
                self.assertTrue(result["applied"])
                self.assertFalse(result["fill_claimed"])
                self.assertEqual(result["state"], "EXIT_REQUIRED")
                position = store.get_position(opened["position_id"])
                assert position is not None
                self.assertEqual(position["exit_decision_id"], exit_decision["exit_decision_id"])
            finally:
                store.close()

    def test_sqlite_migration_idempotent_on_legacy_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy.sqlite"
            conn = sqlite3.connect(path)
            conn.execute(
                """
                CREATE TABLE bot_instances (
                    bot_instance_id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    strategy_version TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    stopped_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE positions (
                    position_id TEXT PRIMARY KEY,
                    bot_instance_id TEXT NOT NULL,
                    mint TEXT NOT NULL,
                    state TEXT NOT NULL,
                    signal_kind TEXT,
                    entered_notional_usd REAL,
                    exit_notional_usd REAL,
                    opened_at TEXT,
                    closed_at TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO bot_instances VALUES
                ('BOT-LEGACY','STRAT-LEGACY','STRAT-LEGACY-V1','PAPER','RUNNING','2026-01-01T00:00:00Z',NULL)
                """
            )
            conn.commit()
            conn.close()
            store = PaperPlaneStore(path)
            try:
                bots = store.bots()
                self.assertEqual(bots[0]["bot_instance_id"], "BOT-LEGACY")
                self.assertIsNone(bots[0].get("activation_epoch_id"))
                # Second open must be idempotent.
                store2 = PaperPlaneStore(path)
                try:
                    self.assertEqual(len(store2.bots()), 1)
                finally:
                    store2.close()
            finally:
                store.close()

    def test_v1_1_path_does_not_call_signal_kind_for(self) -> None:
        strategy = load_strategy_version(
            ROOT,
            "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml",
        )
        with self.assertRaisesRegex(PaperPlaneError, "SIGNAL_KIND_FOR_FORBIDDEN_ON_V1_1"):
            signal_kind_for(strategy, {"X_LIQUIDITY_USD": 9999})

    def test_two_structurally_different_producers_same_interface(self) -> None:
        """Two outside-engine producers emit SignalDecision; engine stays agnostic."""

        a = load_strategy_version(
            ROOT,
            "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml",
        )
        b = load_strategy_version(
            ROOT,
            "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_b.yaml",
        )

        def producer_threshold_style(*, strategy_id: str, mint: str) -> dict:
            # Scientific rule lives here — not in paper_plane.
            liquidity = 2500.0
            action = "ENTER" if liquidity >= 2000.0 else "NO_ENTER"
            return {
                "schema": "smial.signal-decision",
                "schema_version": "1.0",
                "signal_decision_id": "SIGDEC-PRODUCER-THRESHOLD-1",
                "strategy_id": strategy_id,
                "strategy_version": "V1",
                "activation_epoch_id": EPOCH,
                "source_hypothesis_refs": ["HYP-BOUNDARY-SYNTH-A"],
                "mint": mint,
                "decision_at": "2026-09-03T12:10:00Z",
                "first_reliable_available_at": "2026-09-03T12:09:00Z",
                "action": action,
                "reason_code": "THRESHOLD_PRODUCER",
                "evidence_refs": [
                    "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                ],
            }

        def producer_pattern_style(*, strategy_id: str, mint: str) -> dict:
            # Different scientific structure — pattern presence, not a threshold.
            tags = {"early_flow_tilt"}
            action = "ENTER" if "early_flow_tilt" in tags else "NO_ENTER"
            return {
                "schema": "smial.signal-decision",
                "schema_version": "1.0",
                "signal_decision_id": "SIGDEC-PRODUCER-PATTERN-1",
                "strategy_id": strategy_id,
                "strategy_version": "V1",
                "activation_epoch_id": EPOCH,
                "source_hypothesis_refs": ["HYP-BOUNDARY-SYNTH-B"],
                "mint": mint,
                "decision_at": "2026-09-03T12:11:00Z",
                "first_reliable_available_at": "2026-09-03T12:10:00Z",
                "action": action,
                "reason_code": "PATTERN_PRODUCER",
                "evidence_refs": [
                    "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
                ],
            }

        mint = "So11111111111111111111111111111111111111112"
        dec_a = producer_threshold_style(strategy_id=a["strategy_id"], mint=mint)
        dec_b = producer_pattern_style(strategy_id=b["strategy_id"], mint=mint)
        validate_signal_decision(ROOT, dec_a)
        validate_signal_decision(ROOT, dec_b)
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                ra = accept_signal_decision(
                    ROOT,
                    store,
                    strategy=a,
                    signal_decision=dec_a,
                    known_activation_epochs=KNOWN_EPOCHS,
                    as_of="2026-09-03T12:10:30Z",
                )
                rb = accept_signal_decision(
                    ROOT,
                    store,
                    strategy=b,
                    signal_decision=dec_b,
                    known_activation_epochs=KNOWN_EPOCHS,
                    as_of="2026-09-03T12:11:30Z",
                )
                self.assertTrue(ra["opened"])
                self.assertTrue(rb["opened"])
                self.assertNotEqual(ra["position_id"], rb["position_id"])
                self.assertNotIn("X_LIQUIDITY_USD", inspect.getsource(accept_signal_decision))
            finally:
                store.close()

    def test_decision_schemas_validate(self) -> None:
        validate_signal_decision(ROOT, _load_json("signal_decision_enter_a.json"))
        validate_exit_decision(ROOT, _load_json("exit_decision_exit.json"))
        self.assertEqual(
            position_id_for_signal_decision("SIGDEC-BOUNDARY-ENTER-A"),
            "POS-SIG-SIGDEC-BOUNDARY-ENTER-A",
        )

    def test_stale_signal_and_max_open_enforced(self) -> None:
        strategy = load_strategy_version(
            ROOT,
            "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml",
        )
        decision = _load_json("signal_decision_enter_a.json")
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                with self.assertRaisesRegex(PaperPlaneError, "SIGNAL_DECISION_STALE"):
                    accept_signal_decision(
                        ROOT,
                        store,
                        strategy=strategy,
                        signal_decision=decision,
                        known_activation_epochs=KNOWN_EPOCHS,
                        as_of="2026-09-03T13:00:00Z",
                    )
            finally:
                store.close()
        tight = dict(strategy)
        tight["risk_policy"] = {"max_open_positions": 1}
        # Re-hash not required for runtime risk check after load; mutate raw.
        strategy = load_strategy_version(
            ROOT,
            "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml",
        )
        strategy = dict(strategy)
        strategy["risk_policy"] = {"max_open_positions": 1}
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                accept_signal_decision(
                    ROOT,
                    store,
                    strategy=strategy,
                    signal_decision=decision,
                    known_activation_epochs=KNOWN_EPOCHS,
                    as_of="2026-09-03T12:10:30Z",
                )
                second = dict(_load_json("signal_decision_enter_b_same_mint.json"))
                with self.assertRaisesRegex(PaperPlaneError, "BLOCK_MAX_OPEN_POSITIONS"):
                    accept_signal_decision(
                        ROOT,
                        store,
                        strategy=strategy,
                        signal_decision=second,
                        known_activation_epochs=KNOWN_EPOCHS,
                        as_of="2026-09-03T12:20:30Z",
                    )
            finally:
                store.close()

    def test_activation_epoch_separates_bots(self) -> None:
        strategy = load_strategy_version(
            ROOT,
            "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml",
        )
        epochs = {
            "ACTIVATION-EPOCH-BOUNDARY-PAPER-001": {},
            "ACTIVATION-EPOCH-BOUNDARY-PAPER-002": {},
        }
        d1 = _load_json("signal_decision_enter_a.json")
        d2 = dict(d1)
        d2["signal_decision_id"] = "SIGDEC-BOUNDARY-ENTER-EPOCH2"
        d2["activation_epoch_id"] = "ACTIVATION-EPOCH-BOUNDARY-PAPER-002"
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                r1 = accept_signal_decision(
                    ROOT,
                    store,
                    strategy=strategy,
                    signal_decision=d1,
                    known_activation_epochs=epochs,
                    as_of="2026-09-03T12:10:30Z",
                )
                r2 = accept_signal_decision(
                    ROOT,
                    store,
                    strategy=strategy,
                    signal_decision=d2,
                    known_activation_epochs=epochs,
                    as_of="2026-09-03T12:10:30Z",
                )
                self.assertNotEqual(r1["bot_instance_id"], r2["bot_instance_id"])
                self.assertEqual(len(store.bots()), 2)
            finally:
                store.close()

    def test_shadow_mode_uses_shadow_executable(self) -> None:
        strategy = load_strategy_version(
            ROOT,
            "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml",
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                result = accept_signal_decision(
                    ROOT,
                    store,
                    strategy=strategy,
                    signal_decision=_load_json("signal_decision_enter_a.json"),
                    known_activation_epochs=KNOWN_EPOCHS,
                    mode="SHADOW",
                    as_of="2026-09-03T12:10:30Z",
                )
                self.assertEqual(result["realized_signal_kind"], "SHADOW_EXECUTABLE")
                pos = store.get_position(result["position_id"])
                assert pos is not None
                self.assertEqual(pos["signal_kind"], "SHADOW_EXECUTABLE")
            finally:
                store.close()

    def test_resume_incomplete_enter_lifecycle(self) -> None:
        strategy = load_strategy_version(
            ROOT,
            "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml",
        )
        decision = _load_json("signal_decision_enter_a.json")
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                bot = store.start_bot(
                    strategy, mode="PAPER", activation_epoch_id=EPOCH
                )
                pid = store.open_position_from_signal(
                    bot_instance_id=bot["bot_instance_id"],
                    signal_decision=decision,
                )
                self.assertEqual(store.get_position(pid)["state"], "WATCHED")
                result = accept_signal_decision(
                    ROOT,
                    store,
                    strategy=strategy,
                    signal_decision=decision,
                    known_activation_epochs=KNOWN_EPOCHS,
                    as_of="2026-09-03T12:10:30Z",
                )
                self.assertTrue(result["opened"])
                self.assertEqual(result["state"], "OPEN")
                self.assertTrue(result["idempotent"])
            finally:
                store.close()

    def test_v1_1_rejects_feature_fields(self) -> None:
        from solana_alpha_lab.factory.strategy_runtime import validate_and_hash_strategy

        strategy = load_strategy_version(
            ROOT,
            "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml",
        )
        bad = dict(strategy)
        bad["signal_rule"] = {
            "feature": "X_LIQUIDITY_USD",
            "bin_op": ">=",
            "bin_threshold": 1,
        }
        with self.assertRaisesRegex(PaperPlaneError, "STRATEGY_V1_1_SCHEMA_INVALID"):
            validate_and_hash_strategy(ROOT, bad)

    def test_exit_rejects_epoch_mismatch(self) -> None:
        strategy = load_strategy_version(
            ROOT,
            "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml",
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                opened = accept_signal_decision(
                    ROOT,
                    store,
                    strategy=strategy,
                    signal_decision=_load_json("signal_decision_enter_a.json"),
                    known_activation_epochs={
                        EPOCH: {},
                        "ACTIVATION-EPOCH-BOUNDARY-PAPER-002": {},
                    },
                    as_of="2026-09-03T12:10:30Z",
                )
                exit_decision = dict(_load_json("exit_decision_exit.json"))
                exit_decision["activation_epoch_id"] = "ACTIVATION-EPOCH-BOUNDARY-PAPER-002"
                with self.assertRaisesRegex(PaperPlaneError, "EXIT_ACTIVATION_EPOCH_MISMATCH"):
                    accept_exit_decision(
                        ROOT,
                        store,
                        strategy=strategy,
                        exit_decision=exit_decision,
                        known_activation_epochs={
                            EPOCH: {},
                            "ACTIVATION-EPOCH-BOUNDARY-PAPER-002": {},
                        },
                    )
                self.assertEqual(store.get_position(opened["position_id"])["state"], "OPEN")
            finally:
                store.close()


    def test_closed_enter_returns_real_state(self) -> None:
        strategy = load_strategy_version(
            ROOT,
            "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml",
        )
        decision = _load_json("signal_decision_enter_a.json")
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                opened = accept_signal_decision(
                    ROOT,
                    store,
                    strategy=strategy,
                    signal_decision=decision,
                    known_activation_epochs=KNOWN_EPOCHS,
                )
                pid = opened["position_id"]
                store.transition(pid, "EXIT_REQUIRED")
                store.transition(pid, "EXITING")
                store.transition(pid, "CLOSED")
                again = accept_signal_decision(
                    ROOT,
                    store,
                    strategy=strategy,
                    signal_decision=decision,
                    known_activation_epochs=KNOWN_EPOCHS,
                )
                self.assertEqual(again["state"], "CLOSED")
                self.assertFalse(again["opened"])
                self.assertTrue(again["idempotent"])
            finally:
                store.close()

    def test_enter_rejects_epoch_mismatch_on_existing_signal(self) -> None:
        strategy = load_strategy_version(
            ROOT,
            "tests/fixtures/factory_strategy_execution_boundary/strategy_v1_1_candidate_a.yaml",
        )
        d1 = _load_json("signal_decision_enter_a.json")
        with tempfile.TemporaryDirectory() as tmp:
            store = PaperPlaneStore(Path(tmp) / "paper.sqlite")
            try:
                accept_signal_decision(
                    ROOT,
                    store,
                    strategy=strategy,
                    signal_decision=d1,
                    known_activation_epochs={
                        EPOCH: {},
                        "ACTIVATION-EPOCH-BOUNDARY-PAPER-002": {},
                    },
                )
                d2 = dict(d1)
                d2["activation_epoch_id"] = "ACTIVATION-EPOCH-BOUNDARY-PAPER-002"
                with self.assertRaisesRegex(PaperPlaneError, "SIGNAL_ACTIVATION_EPOCH_MISMATCH"):
                    accept_signal_decision(
                        ROOT,
                        store,
                        strategy=strategy,
                        signal_decision=d2,
                        known_activation_epochs={
                            EPOCH: {},
                            "ACTIVATION-EPOCH-BOUNDARY-PAPER-002": {},
                        },
                    )
                self.assertEqual(len(store.bots()), 1)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
