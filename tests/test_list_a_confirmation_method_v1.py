"""Literal independent arithmetic witnesses, including one fixed nonzero draw."""
import hashlib
import random
import unittest
from datetime import datetime
from fractions import Fraction
from types import SimpleNamespace
from unittest.mock import patch

from solana_alpha_lab.factory.list_a_confirmation_method import (
    CORE_SHA, draw_weights, nearest_rank_interval, seed_for, weighted_contrast, calculate_list_a,
)


class FixedDraw:
    def __init__(self):
        self.draws = iter([0, 0, 1, 0, 1, 1])
        self.calls = []

    def randrange(self, width):
        self.calls.append(width)
        return next(self.draws)


class MethodTests(unittest.TestCase):
    def test_native_numeric_unavailable_preserves_observed_counts_without_zero_fill(self):
        rows = [{"episode_id": f"{g}{i:02d}", "group": g, "mint": f"{g}m{i}", "r": 0.125 if g == "A" else 0.0,
                 "blocks": {str(h): i for h in (86400, 172800)}} for g in ("A", "C") for i in range(32)]
        rows[0].update(r=None, numeric_refusal="TEMPORAL_TARGET_UNREPRESENTABLE")
        with patch("solana_alpha_lab.factory.list_a_confirmation_method.draw_weights", side_effect=AssertionError("NO_NUMERIC_REROLL")):
            result = calculate_list_a(rows, {"A": 32, "C": 32})
        self.assertEqual(result["terminal"], "INSUFFICIENT")
        self.assertEqual(result["coverage"], {"A": 1.0, "C": 1.0})
        self.assertEqual((result["support"]["A"]["observed"], result["support"]["C"]["observed"]), (32, 32))
        self.assertIsNone(result["contrast"])
        self.assertIsNone(result["means"])
        self.assertEqual(result["partitions"], {})
        self.assertIn("TEMPORAL_TARGET_UNREPRESENTABLE", result["reason_codes"])
        rows[0].pop("numeric_refusal")
        with self.assertRaisesRegex(ValueError, "INVALID_OBSERVED_ROW"):
            calculate_list_a(rows, {"A": 32, "C": 32})

    def test_independent_fraction_draw_and_weighting(self):
        # Independent labels and multiplicities. The production draw owner must
        # choose M draws before T, and use the same crossed weights in A and C.
        cells = [("A", "m1", 1, Fraction(1, 4)), ("A", "m2", 2, Fraction(0)),
                 ("A", "m3", 3, Fraction(0)), ("C", "m1", 2, Fraction(-1, 8)),
                 ("C", "m2", 1, Fraction(1, 8))]
        rows = [{"group": g, "mint": m, "r": float(r), "blocks": {"86400": t}} for g, m, t, r in cells]
        mm, tt = {"m1": 2, "m2": 1, "m3": 0}, {1: 1, 2: 2, 3: 0}
        weights = [mm[m] * tt[t] for _, m, t, _ in cells]
        means = [sum(w * r for (g, _, _, r), w in zip(cells, weights) if g == group) /
                 sum(w for (g, _, _, _), w in zip(cells, weights) if g == group) for group in ("A", "C")]
        self.assertEqual(means, [Fraction(1, 8), Fraction(-3, 40)])
        self.assertEqual(means[0] - means[1], Fraction(1, 5))
        rng = FixedDraw()
        actual = draw_weights(rows, ["m1", "m2", "m3"], [1, 2, 3], 86400, rng)
        self.assertEqual(actual, [2, 2, 0, 4, 1])
        self.assertEqual(rng.calls, [3] * 6)
        self.assertEqual(weighted_contrast(rows, actual), (0.125, -0.075, 0.2))

    def test_seeds_and_nearest_rank(self):
        for h, expected in ((86400, 2055296707731192101), (172800, 3449030900544075880)):
            independent = int(hashlib.sha256((CORE_SHA + ":" + str(h)).encode()).hexdigest()[:16], 16)
            self.assertEqual(independent, expected)
            self.assertEqual(seed_for(h), expected)
        self.assertEqual(nearest_rank_interval(list(range(4096))), [102, 3993])

    def test_rng_draw_order_literal_non_degenerate(self):
        rng = random.Random(2055296707731192101)
        # Independent standard library sequence, consumed M then T.
        expected_m = [rng.randrange(4) for _ in range(4)]
        expected_t = [rng.randrange(3) for _ in range(3)]
        rows = [{"mint": "m" + str(i), "blocks": {"86400": i % 3}} for i in range(4)]
        expected = [expected_m.count(i) * expected_t.count(i % 3) for i in range(4)]
        self.assertEqual(draw_weights(rows, ["m0", "m1", "m2", "m3"], [0, 1, 2], 86400,
                                      random.Random(2055296707731192101)), expected)

    def test_integer_coverage_boundary_and_empty_group(self):
        rows = [{"episode_id": f"{g}{i:03}", "mint": f"{g}{i}", "group": g, "r": 0.125 if g == "A" else 0.0,
                 "blocks": {"86400": i // 4, "172800": i // 4}} for g, count in (("A", 122), ("C", 128)) for i in range(count)]
        accepted = calculate_list_a(rows, {"A": 128, "C": 128})
        self.assertEqual(accepted["terminal"], "ASSOCIATION_SUPPORTED_CONDITIONAL")
        self.assertEqual(accepted["coverage"]["A"], float(Fraction(61, 64)))
        rejected = calculate_list_a([r for r in rows if r["group"] == "C" or int(r["episode_id"][1:]) < 120], {"A":128,"C":128})
        self.assertEqual(rejected["coverage"]["A"], float(Fraction(15, 16)))
        self.assertIn("TARGET_COVERAGE_BELOW_95_PERCENT", rejected["reason_codes"])
        empty = calculate_list_a([r for r in rows if r["group"] == "C"], {"A":0,"C":128})
        self.assertEqual(empty["terminal"], "INSUFFICIENT")
        self.assertIsNone(empty["coverage"]["A"])

    def test_off_grid_acquisition_independent_clock_oracle(self):
        from solana_alpha_lab.factory.hfic_temporal_discovery import confirmation_price_cell
        def time(s): return datetime.fromisoformat("2026-11-02T" + s + "+00:00")
        window = SimpleNamespace(nominal_due=time("00:45:01"), request_not_before=time("00:50:00"),
                                 availability_deadline=time("00:55:00"))
        row = {"state":"OBSERVED","typed_value":"8", "observation_clock_policy":"PROVIDER_REPORTED_SNAPSHOT_V1",
            "source_price_event_time":"UNKNOWN", "primitive_id":"PRIM-JUPITER-TOKENS-V2-SEARCH-001",
            "call_occurrence_id":"0"*64,"request_sha256":"1"*64,"request_started_at":"2026-11-02T00:45:01Z",
            "response_received_at":"2026-11-02T00:45:02Z","first_reliable_available_at":"2026-11-02T00:45:03Z"}
        cell = confirmation_price_cell([row], cohort="C",release="R",episode_id="E",point="E1800",window=window)
        self.assertNotEqual(cell["status"], "OBSERVED")
        row.update(request_started_at="2026-11-02T00:50:00Z",response_received_at="2026-11-02T00:50:01Z",first_reliable_available_at="2026-11-02T00:50:02Z")
        self.assertEqual(confirmation_price_cell([row], cohort="C",release="R",episode_id="E",point="E1800",window=window)["status"],"OBSERVED")
