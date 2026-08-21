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

from solana_alpha_lab.quote_native_evidence_fit_panel import (  # noqa: E402
    A24_MINT,
    AUTHORITY_PHRASE,
    T21_MINTS,
    WRAPPED_SOL,
    build_order_url,
    build_schedule,
    project_quote,
    run_wave,
    validate_policy,
)

CONFIG = ROOT / "configs/quote_native_evidence_fit_panel_v1.yaml"
MODULE = ROOT / "src/solana_alpha_lab/quote_native_evidence_fit_panel.py"
SCRIPT = ROOT / "scripts/run_quote_native_evidence_fit_panel.py"


def _policy() -> dict[str, Any]:
    value = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError("policy")
    return value


def _quote_body(**overrides: object) -> bytes:
    payload = {
        "transaction": None,
        "requestId": "req-1",
        "inputMint": WRAPPED_SOL,
        "outputMint": A24_MINT,
        "inAmount": "10000000",
        "outAmount": "12345",
        "router": "dflow",
        "mode": "manual",
        "priceImpactPct": "0.01",
        "platformFee": None,
        "routePlan": [
            {
                "swapInfo": {
                    "feeAmount": "3",
                    "feeMint": WRAPPED_SOL,
                }
            }
        ],
        **overrides,
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


class QuoteNativePanelTests(unittest.TestCase):
    def test_policy_freezes_git_identities_and_two_notionals(self) -> None:
        policy = _policy()
        validate_policy(policy, root=ROOT)
        mints = [item["mint"] for item in policy["identities"]]
        self.assertEqual(mints[0], A24_MINT)
        self.assertEqual(tuple(mints[1:]), T21_MINTS)
        self.assertEqual(policy["notionals_atomic"], ["10000000", "1000000"])
        self.assertTrue(all(item["source_kind"] == "GIT_FROZEN" for item in policy["identities"]))

    def test_url_omits_taker_and_execute(self) -> None:
        url = build_order_url(input_mint=WRAPPED_SOL, output_mint=A24_MINT, amount="10000000")
        self.assertTrue(url.startswith("https://api.jup.ag/swap/v2/order?"))
        self.assertNotIn("taker", url.lower())
        source = MODULE.read_text(encoding="utf-8")
        self.assertNotIn("/execute", source)
        self.assertNotIn("/build", source)
        self.assertNotIn("jupiter_quote_logger", source)

    def test_runner_source_does_not_read_credentials(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8").lower()
        self.assertNotIn(".env", source)
        self.assertNotIn("jupiter_api_key", source)
        self.assertNotIn("x-api-key", source)

    def test_schedule_is_forty_rows_with_horizons(self) -> None:
        rows = build_schedule(_policy(), panel_started_at=datetime(2026, 8, 18, 0, 0, tzinfo=UTC))
        self.assertEqual(len(rows), 40)
        self.assertEqual(sum(1 for row in rows if row["kind"] == "BUY_T0"), 8)
        self.assertEqual(sum(1 for row in rows if row["kind"] == "REVERSE_T0"), 8)
        self.assertEqual(sum(1 for row in rows if str(row["kind"]).startswith("SELL_H")), 24)

    def test_fee_fields_are_typed_not_zero_filled(self) -> None:
        quote = project_quote(_quote_body())
        self.assertEqual(quote["surface"], "QUOTE_OBSERVED")
        self.assertEqual(quote["platform_fee"]["status"], "NULL")
        self.assertEqual(quote["price_impact_pct"]["status"], "OBSERVED")
        self.assertTrue(quote["route_plan"]["fee_amounts_present"])
        missing = project_quote(_quote_body())
        payload = json.loads(_quote_body())
        del payload["priceImpactPct"]
        del payload["platformFee"]
        del payload["routePlan"]
        absent = project_quote(json.dumps(payload).encode("utf-8"))
        self.assertEqual(absent["price_impact_pct"]["status"], "ABSENT")
        self.assertEqual(absent["platform_fee"]["status"], "ABSENT")
        self.assertIsNone(absent["price_impact_pct"]["value"])

    def test_quote_error_taxonomy_is_explicit_not_route_substring_based(self) -> None:
        market = project_quote(
            _quote_body(
                inAmount=None,
                outAmount=None,
                router=None,
                mode=None,
                errorCode="TOKEN_NOT_TRADABLE",
            )
        )
        notional = project_quote(
            _quote_body(
                inAmount=None,
                outAmount=None,
                router=None,
                mode=None,
                errorCode="ROUTE_PLAN_DOES_NOT_CONSUME_ALL_THE_AMOUNT",
            )
        )
        unknown = project_quote(
            _quote_body(
                inAmount=None,
                outAmount=None,
                router=None,
                mode=None,
                errorCode="PROVIDER_NEW_TYPED_FAILURE",
            )
        )

        self.assertEqual(market["terminal_class"], "MARKET_EXECUTION_UNAVAILABLE")
        self.assertEqual(market["surface"], "PROVIDER_TYPED_FAILURE")
        self.assertEqual(notional["terminal_class"], "NOTIONAL_EXECUTION_UNAVAILABLE")
        self.assertEqual(unknown["terminal_class"], "UNKNOWN_TYPED_FAILURE")

        failed_quotes = project_quote(
            json.dumps(
                {
                    "requestId": "01a0216b-8b58-726c-b959-56d483df6662",
                    "error": "Failed to get quotes",
                }
            ).encode("utf-8")
        )
        self.assertEqual(failed_quotes["terminal_class"], "MARKET_EXECUTION_UNAVAILABLE")
        self.assertEqual(failed_quotes["error_code"], "Failed to get quotes")
        self.assertEqual(failed_quotes["surface"], "PROVIDER_TYPED_FAILURE")

    def test_transaction_bytes_fail_closed(self) -> None:
        with self.assertRaisesRegex(Exception, "QUOTE_RETURNED_TRANSACTION"):
            project_quote(_quote_body(transaction="AAAA"))

    def test_missing_buy_skips_reverse_without_extra_call(self) -> None:
        no_route = json.dumps({"transaction": None, "errorCode": "COULD_NOT_FIND_ANY_ROUTE"}).encode("utf-8")
        quoted = _quote_body(outAmount="999")
        opener = _ScriptedOpener(
            [
                (quoted, 200),
                (quoted, 200),
                (quoted, 200),
                (quoted, 200),
                (no_route, 400),
                (quoted, 200),
                (quoted, 200),
                (quoted, 200),
                (quoted, 200),
                (quoted, 200),
                (quoted, 200),
                (quoted, 200),
                (quoted, 200),
                (quoted, 200),
                (quoted, 200),
            ]
        )

        def _preflight(policy: object, *, observed_at: str) -> dict[str, object]:
            return {"credential_reads": 0, "observed_at": observed_at}

        receipt = run_wave(
            _policy(),
            root=ROOT,
            wave="t0",
            now=datetime(2026, 8, 18, 1, 0, tzinfo=UTC),
            opener=opener,
            preflight_fn=_preflight,
        )
        reverse_after_no_route = next(
            item
            for item in receipt["observations"]
            if item["identity_id"] == "T21_R2_MINT_A"
            and item["kind"] == "REVERSE_T0"
            and item["observation_id"].endswith("10000000:REVERSE_T0")
        )
        self.assertEqual(reverse_after_no_route["terminal"], "SKIPPED_NO_ENTRY")
        self.assertFalse(reverse_after_no_route["consumed_call"])
        self.assertGreaterEqual(len(receipt["comparable_identities"]), 2)
        self.assertEqual(receipt["terminal_outcome"], "T0_PANEL_OBSERVED")
        self.assertEqual(receipt["retries"], 0)
        for request in opener.requests:
            self.assertNotIn("taker", request.full_url.lower())
            headers = {str(key).lower(): value for key, value in request.header_items()}
            self.assertNotIn("x-api-key", headers)

    def test_second_identity_incomparable_shape_stops_panel(self) -> None:
        quoted = _quote_body()
        bad = json.dumps({"transaction": None, "hello": "world"}).encode("utf-8")
        opener = _ScriptedOpener(
            [
                (quoted, 200),
                (quoted, 200),
                (quoted, 200),
                (quoted, 200),
                (bad, 200),
            ]
        )

        def _preflight(policy: object, *, observed_at: str) -> dict[str, object]:
            return {"credential_reads": 0, "observed_at": observed_at}

        receipt = run_wave(
            _policy(),
            root=ROOT,
            wave="t0",
            now=datetime(2026, 8, 18, 1, 0, tzinfo=UTC),
            opener=opener,
            preflight_fn=_preflight,
        )
        self.assertEqual(receipt["terminal_outcome"], "SECOND_IDENTITY_PROTOCOL_FAIL")

    def test_429_after_second_identity_quote_is_not_protocol_fail(self) -> None:
        quoted = _quote_body()
        opener = _ScriptedOpener(
            [
                (quoted, 200),
                (quoted, 200),
                (quoted, 200),
                (quoted, 200),
                (quoted, 200),
                (b'{"error":"rate limited"}', 429),
            ]
        )

        def _preflight(policy: object, *, observed_at: str) -> dict[str, object]:
            return {"credential_reads": 0, "observed_at": observed_at}

        receipt = run_wave(
            _policy(),
            root=ROOT,
            wave="t0",
            now=datetime(2026, 8, 18, 1, 0, tzinfo=UTC),
            opener=opener,
            preflight_fn=_preflight,
        )
        self.assertEqual(receipt["terminal_outcome"], "T0_PANEL_OBSERVED")
        self.assertIn("T21_R2_MINT_A", receipt["quoted_identities"])
        limited = next(
            item
            for item in receipt["observations"]
            if item["observation_id"] == "T21_R2_MINT_A:10000000:REVERSE_T0"
        )
        self.assertEqual(limited["terminal"], "RATE_LIMITED")
        horizon = next(
            item
            for item in receipt["observations"]
            if item["observation_id"] == "T21_R2_MINT_A:10000000:SELL_H900"
        )
        self.assertEqual(horizon["terminal"], "SCHEDULED")
        leftover_buy = next(
            item
            for item in receipt["observations"]
            if item["observation_id"] == "T21_R2_MINT_B:10000000:BUY_T0"
        )
        self.assertEqual(leftover_buy["terminal"], "NOT_REACHED")
        self.assertEqual(receipt["provider_requests"], 6)
        self.assertIn("RATE_LIMIT_STOPPED_REMAINING_CELLS", receipt["limitations"])
        self.assertEqual(
            receipt["identity_bindings"]["v7_access_class"],
            "KEYLESS",
        )
        self.assertNotIn("pmf_quote_slice_v1_sha256", receipt["identity_bindings"])
        a24_buy = next(
            item
            for item in receipt["observations"]
            if item["observation_id"] == "A24_POST_MIGRATION:10000000:BUY_T0"
        )
        t21_buy = next(
            item
            for item in receipt["observations"]
            if item["observation_id"] == "T21_R2_MINT_A:10000000:BUY_T0"
        )
        self.assertEqual(a24_buy["post_migration_status"], "GIT_NAMED_POST_MIGRATION")
        self.assertEqual(
            t21_buy["post_migration_status"],
            "GIT_NAMED_INDEPENDENT_NOT_PROVEN_POST_MIGRATION",
        )

    def test_transport_unknown_on_second_identity_is_not_t0_observed(self) -> None:
        quoted = _quote_body()

        class _TransportOpener(_ScriptedOpener):
            def open(self, request: object, timeout: float = 0) -> _FakeResponse:
                if len(self.requests) >= 4:
                    self.requests.append(request)
                    raise urllib.error.URLError("dns")
                return super().open(request, timeout=timeout)

        opener = _TransportOpener([(quoted, 200), (quoted, 200), (quoted, 200), (quoted, 200)])

        def _preflight(policy: object, *, observed_at: str) -> dict[str, object]:
            return {"credential_reads": 0, "observed_at": observed_at}

        receipt = run_wave(
            _policy(),
            root=ROOT,
            wave="t0",
            now=datetime(2026, 8, 18, 1, 0, tzinfo=UTC),
            opener=opener,
            preflight_fn=_preflight,
        )
        self.assertEqual(receipt["terminal_outcome"], "PANEL_TRANSPORT_UNKNOWN")
        self.assertNotIn("T21_R2_MINT_A", receipt["comparable_identities"])

    def test_due_wave_keeps_frozen_schedule_and_skips_consumed(self) -> None:
        quoted = _quote_body()
        opener = _ScriptedOpener(
            [
                (quoted, 200),
                (quoted, 200),
                (quoted, 200),
                (quoted, 200),
                (quoted, 200),
                (b'{"error":"rate limited"}', 429),
            ]
        )

        def _preflight(policy: object, *, observed_at: str) -> dict[str, object]:
            return {"credential_reads": 0, "observed_at": observed_at}

        prior = run_wave(
            _policy(),
            root=ROOT,
            wave="t0",
            now=datetime(2026, 8, 18, 1, 0, tzinfo=UTC),
            opener=opener,
            preflight_fn=_preflight,
        )
        prior.pop("raw_bodies", None)
        frozen_due = next(
            item["due_at"]
            for item in prior["observations"]
            if item["observation_id"] == "A24_POST_MIGRATION:10000000:SELL_H900"
        )
        idle_opener = _ScriptedOpener([])
        continued = run_wave(
            _policy(),
            root=ROOT,
            wave="due",
            now=datetime(2026, 8, 18, 1, 1, tzinfo=UTC),
            opener=idle_opener,
            preflight_fn=_preflight,
            prior_receipt=prior,
        )
        self.assertEqual(len(idle_opener.requests), 0)
        leftover = next(
            item
            for item in continued["observations"]
            if item["observation_id"] == "T21_R2_MINT_A:1000000:BUY_T0"
        )
        self.assertEqual(leftover["terminal"], "NOT_REACHED")
        horizon = next(
            item
            for item in continued["observations"]
            if item["observation_id"] == "A24_POST_MIGRATION:10000000:SELL_H900"
        )
        self.assertEqual(horizon["due_at"], frozen_due)
        self.assertEqual(horizon["terminal"], "SCHEDULED")
        consumed = next(
            item
            for item in continued["observations"]
            if item["observation_id"] == "A24_POST_MIGRATION:10000000:BUY_T0"
        )
        self.assertEqual(consumed["terminal"], "QUOTE_OBSERVED")
        self.assertEqual(continued["panel_started_at"], prior["started_at"])
        due_opener = _ScriptedOpener(
            [
                (quoted, 200),
                (b'{"error":"rate limited"}', 429),
            ]
        )
        horizon_wave = run_wave(
            _policy(),
            root=ROOT,
            wave="due",
            now=datetime(2026, 8, 18, 1, 16, tzinfo=UTC),
            opener=due_opener,
            preflight_fn=_preflight,
            prior_receipt=prior,
        )
        self.assertEqual(len(due_opener.requests), 2)
        first_url = due_opener.requests[0].full_url
        self.assertIn(A24_MINT, first_url)
        self.assertNotIn("2Ezm4w3gFdymRAyhx9KEsbJV9NA79Y7UoiNWeXNFpump", first_url)
        first_horizon = next(
            item
            for item in horizon_wave["observations"]
            if item["observation_id"] == "A24_POST_MIGRATION:10000000:SELL_H900"
        )
        self.assertEqual(first_horizon["terminal"], "QUOTE_OBSERVED")
        second_horizon = next(
            item
            for item in horizon_wave["observations"]
            if item["observation_id"] == "A24_POST_MIGRATION:1000000:SELL_H900"
        )
        self.assertEqual(second_horizon["terminal"], "RATE_LIMITED")
        leftover_horizon = next(
            item
            for item in horizon_wave["observations"]
            if item["observation_id"] == "T21_R2_MINT_B:10000000:SELL_H900"
        )
        self.assertEqual(leftover_horizon["terminal"], "SCHEDULED")
        quoted_unreached_horizon = next(
            item
            for item in horizon_wave["observations"]
            if item["observation_id"] == "T21_R2_MINT_A:10000000:SELL_H900"
        )
        self.assertEqual(quoted_unreached_horizon["terminal"], "SCHEDULED")
        later_horizon = next(
            item
            for item in horizon_wave["observations"]
            if item["observation_id"] == "A24_POST_MIGRATION:10000000:SELL_H3600"
        )
        self.assertEqual(later_horizon["terminal"], "SCHEDULED")
        leftover_buy = next(
            item
            for item in horizon_wave["observations"]
            if item["observation_id"] == "T21_R2_MINT_B:10000000:BUY_T0"
        )
        self.assertEqual(leftover_buy["terminal"], "NOT_REACHED")
        with self.assertRaisesRegex(Exception, "PRIOR_RECEIPT_REQUIRED"):
            run_wave(
                _policy(),
                root=ROOT,
                wave="due",
                now=datetime(2026, 8, 18, 1, 16, tzinfo=UTC),
                opener=due_opener,
                preflight_fn=_preflight,
            )

    def test_rate_limited_buy_skips_reverse_and_horizons(self) -> None:
        opener = _ScriptedOpener([(b'{"error":"rate limited"}', 429)])

        def _preflight(policy: object, *, observed_at: str) -> dict[str, object]:
            return {"credential_reads": 0, "observed_at": observed_at}

        receipt = run_wave(
            _policy(),
            root=ROOT,
            wave="t0",
            now=datetime(2026, 8, 18, 1, 0, tzinfo=UTC),
            opener=opener,
            preflight_fn=_preflight,
        )
        self.assertEqual(len(opener.requests), 1)
        reverse = next(
            item
            for item in receipt["observations"]
            if item["observation_id"] == "A24_POST_MIGRATION:10000000:REVERSE_T0"
        )
        horizon = next(
            item
            for item in receipt["observations"]
            if item["observation_id"] == "A24_POST_MIGRATION:10000000:SELL_H900"
        )
        self.assertEqual(reverse["terminal"], "SKIPPED_NO_ENTRY")
        self.assertEqual(horizon["terminal"], "SKIPPED_NO_ENTRY")
        self.assertEqual(receipt["terminal_outcome"], "PANEL_RATE_LIMITED")

    def test_failed_buy_skips_horizon_sells_without_extra_calls(self) -> None:
        no_route = _quote_body(
            inAmount=None,
            outAmount=None,
            router=None,
            mode=None,
            errorCode="NO_ROUTES_FOUND",
        )
        opener = _ScriptedOpener([(no_route, 200), (b'{"error":"unauthorized"}', 401)])

        def _preflight(policy: object, *, observed_at: str) -> dict[str, object]:
            return {"credential_reads": 0, "observed_at": observed_at}

        receipt = run_wave(
            _policy(),
            root=ROOT,
            wave="t0",
            now=datetime(2026, 8, 18, 1, 0, tzinfo=UTC),
            opener=opener,
            preflight_fn=_preflight,
        )
        self.assertEqual(len(opener.requests), 2)
        horizon = next(
            item
            for item in receipt["observations"]
            if item["observation_id"] == "A24_POST_MIGRATION:10000000:SELL_H900"
        )
        reverse = next(
            item
            for item in receipt["observations"]
            if item["observation_id"] == "A24_POST_MIGRATION:10000000:REVERSE_T0"
        )
        self.assertEqual(reverse["terminal"], "SKIPPED_NO_ENTRY")
        self.assertEqual(horizon["terminal"], "SKIPPED_NO_ENTRY")

    def test_401_is_credential_stop_without_retry(self) -> None:
        opener = _ScriptedOpener([(b'{"error":"unauthorized"}', 401)])

        def _preflight(policy: object, *, observed_at: str) -> dict[str, object]:
            return {"credential_reads": 0, "observed_at": observed_at}

        receipt = run_wave(
            _policy(),
            root=ROOT,
            wave="t0",
            now=datetime(2026, 8, 18, 1, 0, tzinfo=UTC),
            opener=opener,
            preflight_fn=_preflight,
        )
        self.assertEqual(receipt["terminal_outcome"], "CREDENTIAL_REQUIRED_NOT_AUTHORIZED")
        self.assertEqual(receipt["provider_requests"], 1)
        self.assertEqual(receipt["credential_reads"], 0)

    def test_owner_phrase_matches_authority(self) -> None:
        self.assertIn("call cap 40", AUTHORITY_PHRASE)
        self.assertIn("JUPITER-SOLANA-SWAP-V2-ORDER-001", AUTHORITY_PHRASE)
        self.assertEqual(_policy()["external_authority"]["owner_phrase"], AUTHORITY_PHRASE)

    def test_catalog_registers_panel_assets(self) -> None:
        core = (ROOT / "catalog/assets/core.yaml").read_text(encoding="utf-8")
        for asset_id in (
            "EVIDENCE-QUOTE-NATIVE-EVIDENCE-FIT-PANEL-001",
            "EVIDENCE-QUOTE-NATIVE-EVIDENCE-FIT-PANEL-ACCEPTANCE-001",
            "REPORT-QUOTE-NATIVE-EVIDENCE-FIT-PANEL-001",
            "CTRL-QUOTE-NATIVE-EVIDENCE-FIT-PANEL-001",
            "CONFIG-QUOTE-NATIVE-EVIDENCE-FIT-PANEL-001",
            "MODULE-QUOTE-NATIVE-EVIDENCE-FIT-PANEL-001",
            "SCRIPT-QUOTE-NATIVE-EVIDENCE-FIT-PANEL-001",
            "TEST-QUOTE-NATIVE-EVIDENCE-FIT-PANEL-001",
        ):
            self.assertIn(f"asset_id: {asset_id}", core)


if __name__ == "__main__":
    unittest.main()
