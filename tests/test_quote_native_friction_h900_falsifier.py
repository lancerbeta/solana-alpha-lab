from __future__ import annotations

import io
import json
import urllib.error
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
import sys

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.quote_native_friction_h900_falsifier import (  # noqa: E402
    A24_MINT,
    AUTHORITY_PHRASE,
    CELLS,
    T21_MINTS,
    WRAPPED_SOL,
    build_order_url,
    build_schedule,
    run_wave,
    score_mechanism,
    validate_policy,
)

CONFIG = ROOT / "configs/quote_native_friction_h900_falsifier_v1.yaml"
MODULE = ROOT / "src/solana_alpha_lab/quote_native_friction_h900_falsifier.py"
SCRIPT = ROOT / "scripts/run_quote_native_friction_h900_falsifier.py"
CONSUMED_RECEIPT = (
    ROOT
    / "docs/evidence/quote_native_quoted_buy_h900_clock"
    / "a1_quote_native_quoted_buy_h900_clock_runtime_receipt_v1.json"
)


def _policy() -> dict[str, Any]:
    value = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError("policy")
    return value


def _quote_body(out_amount: str = "9940000") -> bytes:
    payload = {
        "transaction": None,
        "requestId": "req-1",
        "inAmount": "10000000",
        "outAmount": out_amount,
        "router": "dflow",
        "mode": "manual",
        "priceImpactPct": "0.01",
        "platformFee": None,
        "feeBps": "1",
        "routePlan": [{"swapInfo": {"feeAmount": "3", "feeMint": WRAPPED_SOL}}],
    }
    return json.dumps(payload).encode("utf-8")


class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = io.BytesIO(body)
        self._status = status
        self.headers = {"Content-Type": "application/json"}

    def getcode(self) -> int:
        return self._status

    def read(self, n: int = -1) -> bytes:
        return self._body.read(n)

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _ScriptedOpener:
    def __init__(self, bodies: list[tuple[bytes, int]]) -> None:
        self.bodies = list(bodies)
        self.requests: list[object] = []

    def open(self, request: object, timeout: float = 0) -> _FakeResponse:
        self.requests.append(request)
        if not self.bodies:
            raise AssertionError("unexpected extra request")
        body, status = self.bodies.pop(0)
        if status >= 400:
            raise urllib.error.HTTPError(
                "https://api.jup.ag/swap/v2/order",
                status,
                "error",
                hdrs=None,  # type: ignore[arg-type]
                fp=io.BytesIO(body),
            )
        return _FakeResponse(body, status)


class FrictionH900Tests(unittest.TestCase):
    def test_policy_freezes_four_unused_t21_cells(self) -> None:
        policy = _policy()
        validate_policy(policy, root=ROOT)
        cells = [(item["identity_id"], item["mint"], item["notional_atomic"]) for item in policy["cells"]]
        self.assertEqual(tuple(cells), CELLS)
        self.assertNotIn(A24_MINT, str(cells))
        self.assertNotIn(T21_MINTS[0], str(cells))
        self.assertNotIn("A24_POST_MIGRATION", str(cells))
        self.assertNotIn("T21_R2_MINT_A", str(cells))

    def test_url_and_sources_omit_taker_execute_env_and_dexscreener(self) -> None:
        url = build_order_url(input_mint=WRAPPED_SOL, output_mint=CELLS[0][1], amount="10000000")
        self.assertNotIn("taker", url.lower())
        module = MODULE.read_text(encoding="utf-8").lower()
        script = SCRIPT.read_text(encoding="utf-8").lower()
        self.assertNotIn("/execute", module)
        self.assertNotIn("/build", module)
        self.assertNotIn("jupiter_quote_logger", module)
        self.assertNotIn("api.dexscreener.com", module)
        self.assertNotIn(".env", script)
        self.assertNotIn("jupiter_api_key", script)
        self.assertIn(AUTHORITY_PHRASE[:40].lower(), module)

    def test_schedule_marks_gaps_and_forbids_consumed_clock(self) -> None:
        started = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)
        rows = build_schedule(_policy(), panel_started_at=started)
        self.assertEqual(len(rows), 20)
        self.assertEqual(sum(1 for row in rows if row["kind"] == "BUY_T0"), 4)
        self.assertEqual(sum(1 for row in rows if row["kind"] == "SELL_H900"), 4)
        gaps = [row for row in rows if row["kind"] in {"SELL_H3600", "SELL_H14400"}]
        self.assertEqual(len(gaps), 8)
        self.assertTrue(all(row["terminal"] == "EXPLICIT_GAP" for row in gaps))
        h900 = next(row for row in rows if row["kind"] == "SELL_H900")
        self.assertEqual(h900["due_at"], "2026-08-18T10:15:00Z")

    def test_due_wave_rejects_consumed_h900_receipt(self) -> None:
        old = json.loads(CONSUMED_RECEIPT.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(Exception, "CONSUMED_H900_OUTCOME_REUSED|OLD_DUE_AT_REBUILT"):
            run_wave(
                _policy(),
                root=ROOT,
                wave="due",
                now=datetime(2026, 8, 18, 10, 15, tzinfo=UTC),
                prior_receipt=old,
                opener=_ScriptedOpener([]),
            )

    def test_t0_quotes_four_cells_and_keeps_gaps(self) -> None:
        quoted = _quote_body()
        opener = _ScriptedOpener([(quoted, 200)] * 8)
        receipt = run_wave(
            _policy(),
            root=ROOT,
            wave="t0",
            now=datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
            opener=opener,
        )
        self.assertEqual(receipt["terminal_outcome"], "T0_FRICTION_CLOCK_ARMED")
        self.assertEqual(receipt["new_provider_requests"], 8)
        self.assertEqual(len(opener.requests), 8)
        gaps = [item for item in receipt["observations"] if item["kind"] in {"SELL_H3600", "SELL_H14400"}]
        self.assertTrue(all(item["terminal"] == "EXPLICIT_GAP" for item in gaps))

    def test_due_wave_scores_predeclared_direction(self) -> None:
        t0_bodies = [
            (_quote_body("11000000"), 200),
            (_quote_body("10900000"), 200),
            (_quote_body("11000000"), 200),
            (_quote_body("10800000"), 200),
            (_quote_body("11000000"), 200),
            (_quote_body("10700000"), 200),
            (_quote_body("11000000"), 200),
            (_quote_body("10600000"), 200),
        ]
        t0 = run_wave(
            _policy(),
            root=ROOT,
            wave="t0",
            now=datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
            opener=_ScriptedOpener(t0_bodies),
        )
        due = run_wave(
            _policy(),
            root=ROOT,
            wave="due",
            now=datetime(2026, 8, 18, 10, 15, tzinfo=UTC),
            prior_receipt=t0,
            opener=_ScriptedOpener(
                [
                    (_quote_body("10800000"), 200),
                    (_quote_body("10700000"), 200),
                    (_quote_body("10600000"), 200),
                    (_quote_body("10500000"), 200),
                ]
            ),
        )
        self.assertEqual(due["terminal_outcome"], "DIRECTIONAL_HINT_NOT_CONFIRMATION")
        self.assertEqual(due["mechanism"]["complete_xy_count"], 4)
        self.assertEqual(due["mechanism"]["time_separated_complete_xy_count"], 4)
        self.assertEqual(due["mechanism"]["y_equals_x_count"], 0)
        self.assertGreater(due["mechanism"]["concordant_pairs"], due["mechanism"]["discordant_pairs"])
        self.assertIs(due["mechanism"]["family_close"], False)

    def test_missing_x_is_not_zero_and_route_domination_is_sample_invalid(self) -> None:
        scored = score_mechanism(
            [
                {
                    "identity_id": "T21_R2_MINT_B",
                    "kind": "BUY_T0",
                    "terminal": "QUOTE_OBSERVED",
                    "amount": "10000000",
                    "quote": {"out_amount": "11000000"},
                },
                {
                    "identity_id": "T21_R2_MINT_B",
                    "kind": "REVERSE_T0",
                    "terminal": "RATE_LIMITED",
                    "quote": None,
                },
                {
                    "identity_id": "T21_R2_MINT_B",
                    "kind": "SELL_H900",
                    "terminal": "NO_ROUTE",
                    "quote": None,
                },
            ]
        )
        self.assertEqual(scored["cells"][0]["x_status"], "MISSING")
        self.assertEqual(scored["cells"][0]["y_status"], "MISSING")
        self.assertEqual(scored["verdict"], "SAMPLE_INVALID_ROUTE_DOMINATED")
        self.assertIs(scored["family_close"], False)

    def test_y_equals_x_is_sample_invalid_not_directional_hint(self) -> None:
        scored = score_mechanism(
            [
                {
                    "identity_id": "T21_R2_MINT_B",
                    "kind": "BUY_T0",
                    "terminal": "QUOTE_OBSERVED",
                    "amount": "10000000",
                    "quote": {"out_amount": "315000000000"},
                },
                {
                    "identity_id": "T21_R2_MINT_B",
                    "kind": "REVERSE_T0",
                    "terminal": "QUOTE_OBSERVED",
                    "quote": {"out_amount": "9755375"},
                },
                {
                    "identity_id": "T21_R2_MINT_B",
                    "kind": "SELL_H900",
                    "terminal": "QUOTE_OBSERVED",
                    "quote": {"out_amount": "9755375"},
                },
                {
                    "identity_id": "T21_R2_MINT_C",
                    "kind": "BUY_T0",
                    "terminal": "QUOTE_OBSERVED",
                    "amount": "10000000",
                    "quote": {"out_amount": "351000000000"},
                },
                {
                    "identity_id": "T21_R2_MINT_C",
                    "kind": "REVERSE_T0",
                    "terminal": "QUOTE_OBSERVED",
                    "quote": {"out_amount": "9727199"},
                },
                {
                    "identity_id": "T21_R2_MINT_C",
                    "kind": "SELL_H900",
                    "terminal": "QUOTE_OBSERVED",
                    "quote": {"out_amount": "9727199"},
                },
            ]
        )
        self.assertEqual(scored["complete_xy_count"], 2)
        self.assertEqual(scored["time_separated_complete_xy_count"], 0)
        self.assertEqual(scored["y_equals_x_count"], 2)
        self.assertIs(scored["concordance_rate"], None)
        self.assertEqual(scored["verdict"], "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY")
        self.assertIs(scored["family_close"], False)
        self.assertIn("NO_TIME_SEPARATED_MECHANISM_ON_Y_EQUALS_X", scored["non_claims"])
        self.assertIn("NO_MOVE_2_EARNED", scored["non_claims"])

    def test_late_h900_is_missed_offset_without_call(self) -> None:
        quoted = _quote_body()
        t0 = run_wave(
            _policy(),
            root=ROOT,
            wave="t0",
            now=datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
            opener=_ScriptedOpener([(quoted, 200)] * 8),
        )
        late = run_wave(
            _policy(),
            root=ROOT,
            wave="due",
            now=datetime(2026, 8, 18, 10, 18, tzinfo=UTC),
            prior_receipt=t0,
            opener=_ScriptedOpener([]),
        )
        self.assertEqual(late["terminal_outcome"], "H900_MISSED_OFFSET")
        self.assertEqual(late["new_provider_requests"], 0)


if __name__ == "__main__":
    unittest.main()
