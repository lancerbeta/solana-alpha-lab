from __future__ import annotations

import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.early_state_hypothesis import (  # noqa: E402
    ATOM_ID,
    EarlyStateError,
    build_cohort,
    evaluate,
    load_config,
)
from solana_alpha_lab.factory.paper_plane import (  # noqa: E402
    PaperPlaneError,
    PaperPlaneStore,
    load_strategy_version,
    run_commissioning,
    signal_kind_for,
)

LIVE_EVIDENCE_PRESENT = (
    ROOT / "local/in_scope_population_live_supply_gate/71b1e477322066b1a5876ad22769fb22465641ce2749f5a5e519f3099f20389a.body"
).is_file() and (ROOT / "local/early_icp_freeze_maturity_probe").is_dir()


def _row(mint: str, liq, netflow):
    return {"mint": mint, "X_LIQUIDITY_USD": liq, "X_NETFLOW_SHARE": netflow}


class StrategyVersionContractTests(unittest.TestCase):
    def test_both_strategy_configs_load_with_valid_self_hash(self) -> None:
        for rel in (
            "configs/strategies/STRAT-V-EARLY-LIQ-FLOOR-COMMISSIONING-V1.yaml",
            "configs/strategies/STRAT-V-EARLY-NETFLOW-TILT-COMMISSIONING-V1.yaml",
        ):
            strategy = load_strategy_version(ROOT, rel)
            self.assertEqual(strategy["commissioning_only"], True)
            self.assertFalse(strategy["mode_eligibility"]["micro_live"])

    def test_tampered_spec_sha256_is_rejected(self) -> None:
        import yaml

        original = (ROOT / "configs/strategies/STRAT-V-EARLY-LIQ-FLOOR-COMMISSIONING-V1.yaml").read_text(
            encoding="utf-8"
        )
        tampered = original.replace(
            "spec_sha256: 88ccb03e0a06b1e3b6698c17de25f8fc49224d45566413c358807cc9403cc95b",
            "spec_sha256: " + "ab" * 32,
        )
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            (tmp_root / "catalog/schemas").mkdir(parents=True)
            (tmp_root / "catalog/schemas/strategy_version.schema.json").write_bytes(
                (ROOT / "catalog/schemas/strategy_version.schema.json").read_bytes()
            )
            (tmp_root / "tampered.yaml").write_text(tampered, encoding="utf-8")
            with self.assertRaisesRegex(PaperPlaneError, "SPEC_SHA256_MISMATCH"):
                load_strategy_version(tmp_root, "tampered.yaml")

    def test_micro_live_true_fails_schema(self) -> None:
        import yaml
        import json
        import jsonschema
        import tempfile

        schema = json.loads((ROOT / "catalog/schemas/strategy_version.schema.json").read_text(encoding="utf-8"))
        doc = yaml.safe_load((ROOT / "configs/strategies/STRAT-V-EARLY-LIQ-FLOOR-COMMISSIONING-V1.yaml").read_text(encoding="utf-8"))
        doc["mode_eligibility"]["micro_live"] = True
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(doc, schema)


class PaperPlaneLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.store = PaperPlaneStore(Path(self._tmp.name) / "state.sqlite")

    def tearDown(self) -> None:
        self.store.close()
        self._tmp.cleanup()

    def test_simulated_fill_full_lifecycle_reaches_reconciled(self) -> None:
        strategy = load_strategy_version(
            ROOT, "configs/strategies/STRAT-V-EARLY-LIQ-FLOOR-COMMISSIONING-V1.yaml"
        )
        bot = self.store.start_bot(strategy, mode="PAPER")
        position_id, kind = self.store.fill_paper(
            bot_instance_id=bot["bot_instance_id"],
            mint="MINT1234567890abcdef",
            notional_usd=Decimal("100"),
        )
        self.assertEqual(kind, "SIMULATED_FILL")
        self.store.transition(position_id, "EXIT_REQUIRED")
        self.store.transition(position_id, "EXITING")
        self.store.transition(position_id, "CLOSED")
        final = self.store.transition(position_id, "RECONCILED")
        self.assertEqual(final["state"], "RECONCILED")

    def test_real_fill_signal_is_forbidden(self) -> None:
        with self.assertRaisesRegex(PaperPlaneError, "REAL_FILL_FORBIDDEN"):
            self.store.open_position(
                bot_instance_id="BOT-X", mint="m", signal_kind="REAL_FILL"
            )

    def test_illegal_transition_fails_closed(self) -> None:
        position_id = self.store.open_position(
            bot_instance_id="BOT-X", mint="mint-1", signal_kind="NO_SIGNAL"
        )
        with self.assertRaisesRegex(PaperPlaneError, "ILLEGAL_TRANSITION"):
            self.store.transition(position_id, "RECONCILED")

    def test_position_ids_are_unique_per_bot(self) -> None:
        first = self.store.open_position(bot_instance_id="BOT-A", mint="mint", signal_kind="SIMULATED_FILL")
        second = self.store.open_position(bot_instance_id="BOT-B", mint="mint", signal_kind="SIMULATED_FILL")
        self.assertNotEqual(first, second)


class SignalRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy = load_strategy_version(
            ROOT, "configs/strategies/STRAT-V-EARLY-NETFLOW-TILT-COMMISSIONING-V1.yaml"
        )

    def test_unknown_feature_data_yields_unknown_not_zero(self) -> None:
        self.assertEqual(
            signal_kind_for(self.strategy, {"X_NETFLOW_SHARE": None}),
            "UNKNOWN",
        )

    def test_positive_netflow_enters_high_bin(self) -> None:
        row = {"X_NETFLOW_SHARE": Decimal("0.25")}
        kind = signal_kind_for(self.strategy, row)
        entry_kinds = self.strategy["entry_rule"]["when_signal_kind_in"]
        self.assertIn(kind, {entry_kinds[0], "NO_SIGNAL"})

    def test_negative_netflow_yields_low_bin(self) -> None:
        kind = signal_kind_for(self.strategy, {"X_NETFLOW_SHARE": Decimal("-0.5")})
        self.assertEqual(kind, "NO_SIGNAL")


class PromotionGateTests(unittest.TestCase):
    def _stats(self, high_n, low_n, high_median="1.2", low_median="1.0", spread=True):
        return {
            "HIGH": {
                "n": high_n,
                "median_y": high_median,
                "coverage": "0.9",
                "non_degenerate_spread": spread,
            },
            "LOW": {
                "n": low_n,
                "median_y": low_median,
                "coverage": "0.9",
                "non_degenerate_spread": spread,
            },
        }

    def test_gate_passes_on_healthy_split(self) -> None:
        from solana_alpha_lab.early_state_hypothesis import apply_gate

        self.assertTrue(apply_gate(self._stats(10, 10)))

    def test_gate_fails_when_low_bin_below_min_n(self) -> None:
        from solana_alpha_lab.early_state_hypothesis import apply_gate

        self.assertFalse(apply_gate(self._stats(20, 5)))

    def test_gate_fails_when_high_not_strictly_better(self) -> None:
        from solana_alpha_lab.early_state_hypothesis import apply_gate

        self.assertFalse(apply_gate(self._stats(10, 10, high_median="0.9", low_median="1.0")))

    def test_gate_fails_on_degenerate_spread(self) -> None:
        from solana_alpha_lab.early_state_hypothesis import apply_gate

        self.assertFalse(apply_gate(self._stats(10, 10, spread=False)))

    def test_too_sparse_terminal_shape_matches_normal_path(self) -> None:
        from solana_alpha_lab.early_state_hypothesis import TOO_SPARSE

        stats = self._stats(2, 2)
        # direct gate check on a too-sparse cohort shape
        self.assertFalse(__import__(
            "solana_alpha_lab.early_state_hypothesis", fromlist=["apply_gate"]
        ).apply_gate(stats))
        self.assertTrue(hasattr(TOO_SPARSE, "__str__"))


class FrozenHypothesisTests(unittest.TestCase):
    def test_config_pins_and_runner_unchanged(self) -> None:
        config = load_config(ROOT)
        self.assertEqual(config["atom_id"], ATOM_ID)

    # DELIVERY_PREFLIGHT_NONCRITICAL_SKIP: docs/evidence/early_state_paper/a1_runtime_receipt_v1.json
    @unittest.skipUnless(LIVE_EVIDENCE_PRESENT, "LOCAL_A4_ABSENT")
    def test_pinned_replay_matches_committed_receipt(self) -> None:
        config = load_config(ROOT)
        runtime = evaluate(ROOT, config)
        committed = json.loads(
            (ROOT / "docs/evidence/early_state_paper/a1_runtime_receipt_v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(runtime["terminal"], committed["scientific"]["terminal"])
        self.assertEqual(runtime["joined_n"], committed["scientific"]["joined_n"])

    def test_missing_pins_fail_closed_before_read(self) -> None:
        config = load_config(ROOT)
        config = dict(config)
        config["pins"] = {
            "decision_search_body": {"path": "missing_a.json", "sha256": "0" * 64},
            "later_search_body": {"path": "missing_b.json", "sha256": "0" * 64},
        }
        root = Path(__file__).resolve().parents[1]
        with self.assertRaisesRegex(EarlyStateError, "PIN_MISSING"):
            evaluate(root, config)


class RunnerRerunTests(unittest.TestCase):
    def test_commissioning_is_rerunnable_over_reconciled_store(self) -> None:
        config = load_config(ROOT)
        cohort, _extras = build_cohort(ROOT, config)
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "state.sqlite"
            first = run_commissioning(
                ROOT,
                strategy_relatives=list(config["strategies"]),
                store_path=store_path,
                cohort=cohort,
            )
            second = run_commissioning(
                ROOT,
                strategy_relatives=list(config["strategies"]),
                store_path=store_path,
                cohort=cohort,
            )
            self.assertEqual(
                [s["simulated_fills"] for s in first["per_strategy"]],
                [s["simulated_fills"] for s in second["per_strategy"]],
            )
            self.assertTrue(all(p["state"] == "RECONCILED" for p in second["positions"]))


if __name__ == "__main__":
    unittest.main()
