from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.holder_concentration_top_quartile_veto import (  # noqa: E402
    PASS,
    PHASE_A_FAIL_TERMINAL,
    PHASE_A_SURVIVE_TERMINAL,
    RULE_ID,
    VETO_HIGH_X,
    VETO_UNKNOWN,
    adjudicate_phase_a_windows,
    assign_rule_labels,
    score_phase_a,
    summarize_labeled_rows,
    veto_count,
)


def _row(
    mint: str,
    x: float | None,
    y: float | None,
    *,
    x_status: str = "ELIGIBLE",
    h900_terminal: str | None = "QUOTE_OBSERVED",
) -> dict[str, object]:
    return {
        "mint": mint,
        "x": x,
        "x_status": x_status,
        "h900_terminal": h900_terminal,
        "y": y,
    }


def _window(prefix: str, xs: list[float], ys: list[float]) -> list[dict[str, object]]:
    return [_row(f"{prefix}{index:02d}", x, y) for index, (x, y) in enumerate(zip(xs, ys, strict=True))]


class TopQuartileVetoScorerTests(unittest.TestCase):
    def test_veto_count_is_ceil_quarter(self) -> None:
        self.assertEqual(veto_count(0), 0)
        self.assertEqual(veto_count(1), 1)
        self.assertEqual(veto_count(4), 1)
        self.assertEqual(veto_count(5), 2)
        self.assertEqual(veto_count(22), 6)
        self.assertEqual(veto_count(16), 4)

    def test_missing_x_is_unknown_not_zeroed(self) -> None:
        labeled = assign_rule_labels(
            [
                _row("a", None, 0.1, x_status="MISSING", h900_terminal=None),
                _row("b", 10.0, 0.2),
                _row("c", 40.0, -0.1),
                _row("d", 20.0, 0.0),
                _row("e", 30.0, 0.05),
            ]
        )
        by_mint = {row["mint"]: row for row in labeled}
        self.assertEqual(by_mint["a"]["rule_label"], VETO_UNKNOWN)
        self.assertIsNone(by_mint["a"]["x"])
        self.assertEqual(by_mint["c"]["rule_label"], VETO_HIGH_X)
        self.assertEqual({by_mint[mint]["rule_label"] for mint in ("b", "d", "e")}, {PASS})

    def test_tie_break_is_higher_x_then_mint_lexical(self) -> None:
        labeled = assign_rule_labels(
            [
                _row("m2", 50.0, 0.1),
                _row("m1", 50.0, 0.2),
                _row("m3", 10.0, 0.3),
                _row("m4", 20.0, 0.4),
            ]
        )
        veto = [row["mint"] for row in labeled if row["rule_label"] == VETO_HIGH_X]
        self.assertEqual(veto, ["m1"])

    def test_meu_is_operational_bad_and_not_imputed_into_median(self) -> None:
        labeled = assign_rule_labels(
            [
                _row("v1", 90.0, None, h900_terminal="MARKET_EXECUTION_UNAVAILABLE"),
                _row("v2", 80.0, -0.9),
                _row("p1", 10.0, 0.4),
                _row("p2", 20.0, 0.5),
                _row("p3", 30.0, 0.6),
                _row("p4", 40.0, 0.7),
            ]
        )
        summary = summarize_labeled_rows(labeled)
        self.assertEqual(summary["veto_high_x"]["market_execution_unavailable"], 1)
        self.assertEqual(summary["veto_high_x"]["rankable_count"], 1)
        self.assertEqual(summary["veto_high_x"]["median_y"], -0.9)
        self.assertGreater(summary["pass"]["median_y"], summary["veto_high_x"]["median_y"])
        self.assertGreater(summary["veto_high_x"]["operational_bad_rate"], summary["pass"]["operational_bad_rate"])

    def test_pooled_metrics_reuse_per_window_labels(self) -> None:
        high_window = assign_rule_labels(
            [_row(f"h{i:02d}", 90.0 - i, 0.2 if i >= 4 else -0.5) for i in range(16)]
        )
        low_window = assign_rule_labels(
            [_row(f"l{i:02d}", 20.0 - i, 0.1 if i >= 4 else -0.4) for i in range(16)]
        )
        pooled = summarize_labeled_rows(high_window + low_window)
        self.assertEqual(pooled["pass_count"], 24)
        self.assertEqual(pooled["veto_high_x_count"], 8)
        high_pass = {row["mint"] for row in high_window if row["rule_label"] == PASS}
        self.assertTrue(high_pass)
        pooled_pass = {row["mint"] for row in high_window + low_window if row["rule_label"] == PASS}
        self.assertTrue(high_pass.issubset(pooled_pass))
        five_a = assign_rule_labels([_row(f"a{i}", 50.0 - i, 0.1) for i in range(5)])
        five_b = assign_rule_labels([_row(f"b{i}", 10.0 - i, 0.1) for i in range(5)])
        pooled_uneven = summarize_labeled_rows(five_a + five_b)
        self.assertEqual(pooled_uneven["veto_high_x_count"], 4)
        self.assertNotEqual(pooled_uneven["veto_high_x_count"], veto_count(10))

    def test_phase_a_survives_only_when_all_gates_pass(self) -> None:
        def _surviving_receipt(prefix: str, offset: float) -> dict[str, object]:
            candidates = []
            observations = []
            pass_y = [0.02, 0.03, 0.04, 0.05, 0.06, 0.20, 0.21, 0.22, 0.23, 0.24, 0.25, 0.26]
            for index in range(16):
                mint = f"{prefix}{index:02d}"
                x = 80.0 - index
                y = (-0.4 + offset) if index < 4 else (pass_y[index - 4] + offset)
                candidates.append({"mint": mint, "x": x, "x_status": "ELIGIBLE"})
                observations.append(
                    {
                        "mint": mint,
                        "x": x,
                        "x_status": "ELIGIBLE",
                        "h900_terminal": "QUOTE_OBSERVED",
                        "y": y,
                    }
                )
            candidates.append(
                {"mint": f"{prefix}missing", "x": None, "x_status": "MISSING"}
            )
            return {"candidate_observations": candidates, "observations": observations}

        result = score_phase_a(
            {
                "A": _surviving_receipt("a", 0.0),
                "B": _surviving_receipt("b", 0.05),
            }
        )
        self.assertEqual(result["rule_id"], RULE_ID)
        self.assertEqual(result["terminal"], PHASE_A_SURVIVE_TERMINAL)
        self.assertTrue(result["adjudication"]["survived"])
        self.assertGreaterEqual(result["windows"]["A"]["pass_count"], 12)
        self.assertGreaterEqual(result["windows"]["B"]["pass_count"], 12)
        self.assertGreater(result["pooled"]["pass"]["median_y"], 0)

    def test_phase_a_fails_when_pass_median_not_above_all_rankable(self) -> None:
        labeled = assign_rule_labels(
            [_row(f"n{i:02d}", 40.0 - i, 0.1) for i in range(16)]
        )
        summary = summarize_labeled_rows(labeled)
        adjudication = adjudicate_phase_a_windows(
            {"A": summary, "B": summary},
            pooled=summary,
        )
        self.assertFalse(adjudication["survived"])
        self.assertEqual(adjudication["terminal"], PHASE_A_FAIL_TERMINAL)
        self.assertFalse(adjudication["directional_utility"]["A"])

    def test_phase_a_fails_coverage_below_twelve(self) -> None:
        labeled = assign_rule_labels(
            [_row(f"c{i:02d}", 20.0 - i, 0.2 if i >= 3 else -0.5) for i in range(12)]
        )
        summary = summarize_labeled_rows(labeled)
        self.assertEqual(summary["pass_count"], 9)
        adjudication = adjudicate_phase_a_windows(
            {"A": summary, "B": summary},
            pooled=summary,
        )
        self.assertFalse(adjudication["coverage"]["A"])
        self.assertEqual(adjudication["terminal"], PHASE_A_FAIL_TERMINAL)

    def test_frozen_development_receipts_are_not_actionable_as_top_quartile_veto(self) -> None:
        from solana_alpha_lab.holder_concentration_top_quartile_veto import score_phase_a_from_paths

        result = score_phase_a_from_paths(ROOT)
        self.assertEqual(result["terminal"], PHASE_A_FAIL_TERMINAL)
        self.assertFalse(result["adjudication"]["survived"])
        self.assertEqual(result["mechanism_status"], "HOLDER_CONCENTRATION_MECHANISM_REPLICATED")
        self.assertFalse(result["adjudication"]["economic_plausibility_pooled_median_y_pass_gt_0"])
        self.assertTrue(all(result["adjudication"]["coverage"].values()))
        self.assertFalse(any(result["adjudication"]["directional_utility"].values()))
        self.assertFalse(any(result["adjudication"]["downside_utility"].values()))
        self.assertGreater(result["pooled"]["pass"]["median_y"], result["pooled"]["veto_high_x"]["median_y"])
        self.assertLessEqual(result["pooled"]["pass"]["median_y"], 0)
        self.assertEqual(result["windows"]["EARLY_HOLDER_CONCENTRATION_H900_FALSIFIER_V1"]["pass_count"], 16)
        self.assertEqual(result["windows"]["EARLY_HOLDER_CONCENTRATION_H900_CONFIRMATORY_OOS_V1"]["pass_count"], 16)
        self.assertEqual(result["pooled"]["veto_high_x_count"], 12)
        self.assertEqual(result["pooled"]["pass_count"], 32)
        on_disk = json.loads(
            (ROOT / "docs/evidence/early_holder_concentration_actionability_rule_oos/a1_phase_a_receipt_v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(on_disk["terminal"], result["terminal"])
        self.assertEqual(on_disk["adjudication"], result["adjudication"])
        self.assertEqual(on_disk["pooled"]["veto_high_x_count"], 12)
        self.assertEqual(on_disk["pooled"]["pass_count"], 32)

    def test_ceil_is_not_floor(self) -> None:
        self.assertEqual(veto_count(5), math.ceil(5 / 4))
        self.assertNotEqual(veto_count(5), 5 // 4)


if __name__ == "__main__":
    unittest.main()
