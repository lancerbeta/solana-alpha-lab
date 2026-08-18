from __future__ import annotations

import io
import json
import urllib.error
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
import sys

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.quote_native_evidence_fit_panel import (  # noqa: E402
    A24_MINT,
    T21_MINTS,
    WRAPPED_SOL,
)
from solana_alpha_lab.quote_native_friction_h900_falsifier import R3_MINTS  # noqa: E402
from solana_alpha_lab.quote_native_live_variation_campaign import (  # noqa: E402
    AUTHORITY_PHRASE,
    FORBIDDEN_MINTS,
    NOTIONAL,
    RECENT_ENDPOINT,
    TRADED_ENDPOINT,
    build_schedule,
    run_wave,
    score_campaign,
    select_cohort,
    validate_policy,
)

CONFIG = ROOT / "configs/quote_native_live_variation_campaign_v1.yaml"


def _policy() -> dict[str, Any]:
    value = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError("policy")
    return value


def _mint(mint_id: str, *, liquidity: float = 5000, created: str, usd_price: float = 1.0) -> dict[str, object]:
    return {
        "id": mint_id,
        "liquidity": liquidity,
        "usdPrice": usd_price,
        "firstPool": {"createdAt": created},
    }


def _quote_body(out_amount: str) -> bytes:
    payload = {
        "transaction": None,
        "requestId": "req-1",
        "inAmount": NOTIONAL,
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
    def __init__(self, responses: list[tuple[str, bytes, int]]) -> None:
        self.responses = list(responses)
        self.requests: list[object] = []

    def open(self, request: object, timeout: float = 0) -> _FakeResponse:
        self.requests.append(request)
        headers = {str(key).lower() for key in getattr(request, "headers", {})}
        if "x-api-key" in headers:
            raise AssertionError("api-key header")
        url = str(getattr(request, "full_url", ""))
        if "taker" in url.lower():
            raise AssertionError("taker")
        if not self.responses:
            raise AssertionError(f"extra request {url}")
        needle, body, status = self.responses.pop(0)
        if needle not in url:
            raise AssertionError(f"{needle} not in {url}")
        if status >= 400:
            raise urllib.error.HTTPError(url, status, "error", hdrs=None, fp=io.BytesIO(body))  # type: ignore[arg-type]
        return _FakeResponse(body, status)


class _Clock:
    def __init__(self, start: datetime) -> None:
        self.current = start
        self.sleeps: list[float] = []

    def __call__(self) -> datetime:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current = self.current + timedelta(seconds=seconds)


def _preflight(*_args: object, **_kwargs: object) -> dict[str, object]:
    return {"credential_reads": 0, "dns_resolved": True}


class CampaignPolicyTests(unittest.TestCase):
    def test_policy_and_forbidden_literals(self) -> None:
        validate_policy(_policy(), root=ROOT)
        self.assertEqual(
            FORBIDDEN_MINTS,
            (
                A24_MINT,
                T21_MINTS[0],
                T21_MINTS[1],
                T21_MINTS[2],
                R3_MINTS[0],
                R3_MINTS[1],
            ),
        )
        self.assertIn(AUTHORITY_PHRASE, CONFIG.read_text(encoding="utf-8"))


class CohortSelectionTests(unittest.TestCase):
    def test_ranks_recent_by_pool_time_not_price(self) -> None:
        older = _mint("OldMint111111111111111111111111111111111111", created="2026-08-01T00:00:00Z", usd_price=0.0001)
        newer = _mint("NewMint111111111111111111111111111111111111", created="2026-08-18T10:00:00Z", usd_price=999)
        cheap_low_liq = _mint("ThinMint1111111111111111111111111111111111", created="2026-08-18T11:00:00Z", liquidity=10)
        forbidden = _mint(A24_MINT, created="2026-08-18T12:00:00Z")
        recent = [older, cheap_low_liq, forbidden, newer]
        recent.extend(
            _mint(f"Rec{index:02d}111111111111111111111111111111111111", created=f"2026-08-18T0{index}:00:00Z")
            for index in range(1, 6)
        )
        traded = [
            _mint(f"Trd{index:02d}111111111111111111111111111111111111", created="2026-08-18T00:00:00Z")
            for index in range(1, 7)
        ]
        selected = select_cohort(recent, traded)
        self.assertTrue(selected["sufficient"])
        cells = selected["cells"]
        assert isinstance(cells, list)
        self.assertEqual(cells[0]["mint"], "NewMint111111111111111111111111111111111111")
        mints = {str(cell["mint"]) for cell in cells if isinstance(cell, dict)}
        self.assertNotIn(A24_MINT, mints)
        self.assertNotIn("ThinMint1111111111111111111111111111111111", mints)


class ScoringTests(unittest.TestCase):
    def _xy(
        self,
        identity_id: str,
        *,
        reverse_out: str,
        sell_out: str,
    ) -> list[dict[str, object]]:
        return [
            {
                "identity_id": identity_id,
                "kind": "BUY_T0",
                "terminal": "QUOTE_OBSERVED",
                "amount": NOTIONAL,
                "quote": {"out_amount": "10000000"},
            },
            {
                "identity_id": identity_id,
                "kind": "REVERSE_T0",
                "terminal": "QUOTE_OBSERVED",
                "quote": {"out_amount": reverse_out},
            },
            {
                "identity_id": identity_id,
                "kind": "SELL_H900",
                "terminal": "QUOTE_OBSERVED",
                "quote": {"out_amount": sell_out},
            },
        ]

    def test_y_equals_x_is_not_directional_hint(self) -> None:
        rows: list[dict[str, object]] = []
        for index in range(1, 7):
            rows.extend(self._xy(f"RECENT_{index}", reverse_out="9700000", sell_out="9700000"))
            rows.extend(self._xy(f"TRADED_{index}", reverse_out="9800000", sell_out="9800000"))
        scored = score_campaign(rows)
        self.assertEqual(scored["campaign_verdict"], "VARIATION_ABSENT_ON_TRADED_CONTROL")
        self.assertEqual(scored["verdict"], "VARIATION_ABSENT_ON_TRADED_CONTROL")
        self.assertNotEqual(scored["verdict"], "DIRECTIONAL_HINT_NOT_CONFIRMATION")
        self.assertGreaterEqual(scored["traded_complete_xy_count"], 6)

    def test_partial_time_separated_is_sample_invalid_not_hint(self) -> None:
        rows: list[dict[str, object]] = []
        rows.extend(self._xy("RECENT_1", reverse_out="9700000", sell_out="9600000"))
        rows.extend(self._xy("RECENT_2", reverse_out="9800000", sell_out="9500000"))
        scored = score_campaign(rows)
        self.assertEqual(scored["campaign_verdict"], "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY")
        self.assertEqual(scored["verdict"], "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY")
        self.assertEqual(scored["complete_xy_count"], 2)
        self.assertEqual(scored["time_separated_complete_xy_count"], 2)
        self.assertEqual(scored["traded_complete_xy_count"], 0)
        for forbidden in (
            "expected_direction",
            "concordance_rate",
            "concordant_pairs",
            "discordant_pairs",
            "tied_pairs",
        ):
            self.assertNotIn(forbidden, scored)

    def test_variation_present_when_control_moves(self) -> None:
        rows: list[dict[str, object]] = []
        for index in range(1, 7):
            rows.extend(self._xy(f"RECENT_{index}", reverse_out="9700000", sell_out=str(9600000 - index * 1000)))
            rows.extend(self._xy(f"TRADED_{index}", reverse_out="9800000", sell_out=str(9700000 - index * 2000)))
        scored = score_campaign(rows)
        self.assertEqual(scored["campaign_verdict"], "VARIATION_PRESENT_NOT_MECHANISM")
        self.assertEqual(scored["verdict"], "VARIATION_PRESENT_NOT_MECHANISM")
        self.assertGreaterEqual(scored["time_separated_complete_xy_count"], 6)


class DiscoveryWaveTests(unittest.TestCase):
    def test_recent_401_stops_before_traded_and_quotes(self) -> None:
        opener = _ScriptedOpener([("/tokens/v2/recent", b'{"error":"auth"}', 401)])
        receipt = run_wave(
            _policy(),
            root=ROOT,
            wave="discovery",
            now=datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
            opener=opener,
            preflight_fn=_preflight,
        )
        self.assertEqual(receipt["terminal_outcome"], "DISCOVERY_CREDENTIAL_REQUIRED_NOT_AUTHORIZED")
        self.assertEqual(receipt["provider_requests"], 1)
        self.assertEqual(receipt["frozen_cells"], [])
        self.assertEqual(receipt["observations"], [])
        self.assertEqual(len(opener.requests), 1)

    def test_discovery_freezes_twelve_live_cells(self) -> None:
        recent = [
            _mint(f"Rec{index:02d}111111111111111111111111111111111111", created=f"2026-08-18T{index:02d}:00:00Z")
            for index in range(10, 16)
        ]
        traded = [
            _mint(f"Trd{index:02d}111111111111111111111111111111111111", created="2026-08-18T00:00:00Z")
            for index in range(1, 7)
        ]
        opener = _ScriptedOpener(
            [
                ("/tokens/v2/recent", json.dumps(recent).encode("utf-8"), 200),
                ("/tokens/v2/toptraded/1h", json.dumps(traded).encode("utf-8"), 200),
            ]
        )
        clock = _Clock(datetime(2026, 8, 18, 10, 0, tzinfo=UTC))
        receipt = run_wave(
            _policy(),
            root=ROOT,
            wave="discovery",
            now=clock.current,
            opener=opener,
            preflight_fn=_preflight,
            clock=clock,
            sleeper=clock.sleep,
        )
        self.assertEqual(receipt["terminal_outcome"], "DISCOVERY_COHORT_FROZEN")
        self.assertEqual(len(receipt["frozen_cells"]), 12)
        self.assertGreaterEqual(len(clock.sleeps), 1)
        mints = {str(cell["mint"]) for cell in receipt["frozen_cells"]}
        self.assertTrue(mints.isdisjoint(FORBIDDEN_MINTS))


class QuoteWaveTests(unittest.TestCase):
    def _frozen_receipt(self) -> dict[str, object]:
        cells = []
        for index in range(1, 7):
            cells.append(
                {
                    "identity_id": f"RECENT_{index}",
                    "mint": f"Rec{index:02d}111111111111111111111111111111111111",
                    "stratum": "RECENT",
                    "notional_atomic": NOTIONAL,
                    "liquidity": 5000,
                    "first_pool_created_at": "2026-08-18T10:00:00Z",
                    "source_kind": "LIVE_TOKENS_V2_RECENT",
                }
            )
            cells.append(
                {
                    "identity_id": f"TRADED_{index}",
                    "mint": f"Trd{index:02d}111111111111111111111111111111111111",
                    "stratum": "TRADED",
                    "notional_atomic": NOTIONAL,
                    "liquidity": 8000,
                    "first_pool_created_at": "2026-08-18T09:00:00Z",
                    "source_kind": "LIVE_TOKENS_V2_TOPTRADED",
                }
            )
        return {
            "atom_id": "QUOTE_NATIVE_LIVE_VARIATION_CAMPAIGN_V1",
            "terminal_outcome": "DISCOVERY_COHORT_FROZEN",
            "provider_requests": 2,
            "last_provider_call_at": "2026-08-18T10:00:04Z",
            "frozen_cells": cells,
            "discovery_observations": [],
            "observations": [],
        }

    def test_t0_quotes_and_keeps_horizons(self) -> None:
        responses = []
        for _index in range(24):
            responses.append(("/swap/v2/order", _quote_body("9750000"), 200))
        opener = _ScriptedOpener(responses)
        clock = _Clock(datetime(2026, 8, 18, 10, 1, tzinfo=UTC))
        receipt = run_wave(
            _policy(),
            root=ROOT,
            wave="t0",
            now=clock.current,
            opener=opener,
            prior_receipt=self._frozen_receipt(),
            preflight_fn=_preflight,
            clock=clock,
            sleeper=clock.sleep,
        )
        self.assertEqual(receipt["terminal_outcome"], "T0_VARIATION_CLOCK_ARMED")
        self.assertEqual(len(receipt["observations"]), 60)
        self.assertEqual(
            sum(1 for row in receipt["observations"] if row.get("kind") == "SELL_H14400" and row.get("terminal") == "EXPLICIT_GAP"),
            12,
        )
        self.assertEqual(
            sum(1 for row in receipt["observations"] if row.get("kind") == "SELL_H900" and row.get("terminal") == "SCHEDULED"),
            12,
        )
        rebuilt = build_schedule(self._frozen_receipt()["frozen_cells"], panel_started_at=datetime(2026, 8, 18, 10, 1, tzinfo=UTC))
        self.assertEqual(len(rebuilt), 60)

    def test_due_wave_does_not_rebuild_start(self) -> None:
        prior = self._frozen_receipt()
        opener = _ScriptedOpener([("/swap/v2/order", _quote_body("9750000"), 200) for _ in range(24)])
        clock = _Clock(datetime(2026, 8, 18, 10, 1, tzinfo=UTC))
        t0 = run_wave(
            _policy(),
            root=ROOT,
            wave="t0",
            now=clock.current,
            opener=opener,
            prior_receipt=prior,
            preflight_fn=_preflight,
            clock=clock,
            sleeper=clock.sleep,
        )
        started = t0["panel_started_at"]
        h900_opener = _ScriptedOpener([("/swap/v2/order", _quote_body("9600000"), 200) for _ in range(12)])
        h900_clock = _Clock(datetime(2026, 8, 18, 10, 16, tzinfo=UTC))
        h900 = run_wave(
            _policy(),
            root=ROOT,
            wave="due",
            now=h900_clock.current,
            opener=h900_opener,
            prior_receipt=t0,
            preflight_fn=_preflight,
            clock=h900_clock,
            sleeper=h900_clock.sleep,
        )
        self.assertEqual(h900["panel_started_at"], started)
        h3600_opener = _ScriptedOpener([("/swap/v2/order", _quote_body("9500000"), 200) for _ in range(12)])
        h3600_clock = _Clock(datetime(2026, 8, 18, 11, 1, tzinfo=UTC))
        due = run_wave(
            _policy(),
            root=ROOT,
            wave="due",
            now=h3600_clock.current,
            opener=h3600_opener,
            prior_receipt=h900,
            preflight_fn=_preflight,
            clock=h3600_clock,
            sleeper=h3600_clock.sleep,
        )
        self.assertEqual(due["panel_started_at"], started)
        self.assertEqual(due["campaign"]["campaign_verdict"], "VARIATION_PRESENT_NOT_MECHANISM")
        self.assertEqual(due["terminal_outcome"], "VARIATION_PRESENT_NOT_MECHANISM")


if __name__ == "__main__":
    unittest.main()
