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

from solana_alpha_lab.quote_native_quoted_buy_h900_clock import (  # noqa: E402
    A24_MINT,
    AUTHORITY_PHRASE,
    CELLS,
    T21_MINTS,
    WRAPPED_SOL,
    build_order_url,
    build_schedule,
    run_wave,
    validate_policy,
)

CONFIG = ROOT / "configs/quote_native_quoted_buy_h900_clock_v1.yaml"
MODULE = ROOT / "src/solana_alpha_lab/quote_native_quoted_buy_h900_clock.py"
SCRIPT = ROOT / "scripts/run_quote_native_quoted_buy_h900_clock.py"


def _offline_preflight(*_args: object, **_kwargs: object) -> dict[str, object]:
    return {"credential_reads": 0, "provider_requests": 0}


def _run_wave(policy: dict[str, Any], /, **kwargs: Any) -> dict[str, object]:
    kwargs.setdefault("preflight_fn", _offline_preflight)
    return run_wave(policy, **kwargs)


OLD_RECEIPT = (
    ROOT
    / "docs/evidence/quote_native_evidence_fit_panel"
    / "a1_quote_native_evidence_fit_panel_runtime_receipt_v1.json"
)


def _policy() -> dict[str, Any]:
    value = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError("policy")
    return value


def _quote_body(out_amount: str = "12345") -> bytes:
    payload = {
        "transaction": None,
        "requestId": "req-1",
        "inAmount": "10000000",
        "outAmount": out_amount,
        "router": "dflow",
        "mode": "manual",
        "priceImpactPct": "0.01",
        "platformFee": None,
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


class QuotedBuyH900Tests(unittest.TestCase):
    def test_policy_freezes_three_quoted_cells_only(self) -> None:
        policy = _policy()
        validate_policy(policy, root=ROOT)
        cells = [(item["identity_id"], item["mint"], item["notional_atomic"]) for item in policy["cells"]]
        self.assertEqual(tuple(cells), CELLS)
        self.assertEqual(cells[0][1], A24_MINT)
        self.assertEqual(cells[2][1], T21_MINTS[0])
        self.assertNotIn("T21_R2_MINT_B", str(cells))
        self.assertNotIn(("T21_R2_MINT_A", T21_MINTS[0], "1000000"), cells)

    def test_url_and_sources_omit_taker_execute_env(self) -> None:
        url = build_order_url(input_mint=WRAPPED_SOL, output_mint=A24_MINT, amount="10000000")
        self.assertNotIn("taker", url.lower())
        module = MODULE.read_text(encoding="utf-8")
        script = SCRIPT.read_text(encoding="utf-8").lower()
        self.assertNotIn("/execute", module)
        self.assertNotIn("/build", module)
        self.assertNotIn("jupiter_quote_logger", module)
        self.assertNotIn(".env", script)
        self.assertNotIn("jupiter_api_key", script)

    def test_schedule_marks_h3600_h14400_explicit_gap(self) -> None:
        started = datetime(2026, 8, 18, 1, 30, tzinfo=UTC)
        rows = build_schedule(_policy(), panel_started_at=started)
        self.assertEqual(len(rows), 15)
        self.assertEqual(sum(1 for row in rows if row["kind"] == "BUY_T0"), 3)
        self.assertEqual(sum(1 for row in rows if row["kind"] == "SELL_H900"), 3)
        gaps = [row for row in rows if row["kind"] in {"SELL_H3600", "SELL_H14400"}]
        self.assertEqual(len(gaps), 6)
        self.assertTrue(all(row["terminal"] == "EXPLICIT_GAP" for row in gaps))
        h900 = next(row for row in rows if row["kind"] == "SELL_H900")
        self.assertEqual(h900["due_at"], "2026-08-18T01:45:00Z")

    def test_due_wave_rejects_old_panel_receipt(self) -> None:
        old = json.loads(OLD_RECEIPT.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(Exception, "OLD_DUE_AT_REBUILT_OR_OLD_RECEIPT_MUTATED"):
            _run_wave(
                _policy(),
                root=ROOT,
                wave="due",
                now=datetime(2026, 8, 18, 1, 45, tzinfo=UTC),
                prior_receipt=old,
                opener=_ScriptedOpener([]),
            )

    def test_t0_quotes_three_cells_and_keeps_gaps(self) -> None:
        quoted = _quote_body()
        opener = _ScriptedOpener([(quoted, 200)] * 6)
        receipt = _run_wave(
            _policy(),
            root=ROOT,
            wave="t0",
            now=datetime(2026, 8, 18, 1, 30, tzinfo=UTC),
            opener=opener,
        )
        self.assertEqual(receipt["terminal_outcome"], "T0_QUOTED_BUY_CLOCK_ARMED")
        self.assertEqual(receipt["new_provider_requests"], 6)
        self.assertEqual(len(opener.requests), 6)
        gaps = [item for item in receipt["observations"] if item["kind"] in {"SELL_H3600", "SELL_H14400"}]
        self.assertTrue(all(item["terminal"] == "EXPLICIT_GAP" for item in gaps))
        h900 = [item for item in receipt["observations"] if item["kind"] == "SELL_H900"]
        self.assertTrue(all(item["terminal"] == "SCHEDULED" for item in h900))

    def test_due_wave_fires_h900_only_inside_slack(self) -> None:
        quoted = _quote_body()
        t0 = _run_wave(
            _policy(),
            root=ROOT,
            wave="t0",
            now=datetime(2026, 8, 18, 1, 30, tzinfo=UTC),
            opener=_ScriptedOpener([(quoted, 200)] * 6),
        )
        due = _run_wave(
            _policy(),
            root=ROOT,
            wave="due",
            now=datetime(2026, 8, 18, 1, 45, tzinfo=UTC),
            prior_receipt=t0,
            opener=_ScriptedOpener([(quoted, 200)] * 3),
        )
        self.assertEqual(due["terminal_outcome"], "H900_PANEL_OBSERVED")
        self.assertEqual(due["new_provider_requests"], 3)
        self.assertEqual(due["panel_started_at"], t0["panel_started_at"])
        gaps = [item for item in due["observations"] if item["kind"] in {"SELL_H3600", "SELL_H14400"}]
        self.assertTrue(all(item["terminal"] == "EXPLICIT_GAP" and item.get("consumed_call") is False for item in gaps))

    def test_late_h900_is_missed_offset_without_call(self) -> None:
        quoted = _quote_body()
        t0 = _run_wave(
            _policy(),
            root=ROOT,
            wave="t0",
            now=datetime(2026, 8, 18, 1, 30, tzinfo=UTC),
            opener=_ScriptedOpener([(quoted, 200)] * 6),
        )
        late = _run_wave(
            _policy(),
            root=ROOT,
            wave="due",
            now=datetime(2026, 8, 18, 1, 48, tzinfo=UTC),
            prior_receipt=t0,
            opener=_ScriptedOpener([]),
        )
        self.assertEqual(late["terminal_outcome"], "H900_MISSED_OFFSET")
        self.assertEqual(late["new_provider_requests"], 0)
        self.assertTrue(
            all(
                item["terminal"] == "MISSED_OFFSET"
                for item in late["observations"]
                if item["kind"] == "SELL_H900"
            )
        )

    def test_due_before_h900_does_not_fire(self) -> None:
        quoted = _quote_body()
        t0 = _run_wave(
            _policy(),
            root=ROOT,
            wave="t0",
            now=datetime(2026, 8, 18, 1, 30, tzinfo=UTC),
            opener=_ScriptedOpener([(quoted, 200)] * 6),
        )
        early = _run_wave(
            _policy(),
            root=ROOT,
            wave="due",
            now=datetime(2026, 8, 18, 1, 40, tzinfo=UTC),
            prior_receipt=t0,
            opener=_ScriptedOpener([]),
        )
        self.assertEqual(early["new_provider_requests"], 0)
        self.assertTrue(
            all(item["terminal"] == "SCHEDULED" for item in early["observations"] if item["kind"] == "SELL_H900")
        )


if __name__ == "__main__":
    unittest.main()
