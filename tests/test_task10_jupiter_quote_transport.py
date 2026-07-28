from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.jupiter_quote_logger import (  # noqa: E402
    PROVIDER,
    PROVIDER_VERSION,
    QuoteRequest,
)
from solana_alpha_lab.contracts.schema_v1 import Side  # noqa: E402
from solana_alpha_lab.jupiter_quote_transport import (  # noqa: E402
    EXTERNAL_AUTHORITY_PHRASE,
    MAX_DURABLE_BYTES,
    MAX_HTTP_REQUESTS,
    MAX_RECEIVED_BYTES,
    BoundedQuoteTransport,
    DurableQuotePilotSink,
    ExternalAuthorityRequiredError,
    ExternalExecutionGate,
    InMemoryQuoteSink,
    QuotePilotRunner,
    QuoteTransportContractError,
    load_pilot_plan,
)

PLAN_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task10"
    / "jupiter_quote_pilot_plan_v2.json"
)
HISTORICAL_PLAN_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task10"
    / "jupiter_quote_pilot_plan_v1.json"
)
SCHEMA_PATH = (ROOT / "schemas" / "schema_v1.sql").resolve()


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


class StepNow:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 28, 1, 30, tzinfo=UTC)

    def __call__(self) -> datetime:
        observed = self.value
        self.value += timedelta(milliseconds=10)
        return observed


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.status = status
        self.body = body
        self.headers = {"Content-Length": str(len(body))}

    def read(self, amount: int) -> bytes:
        return self.body[:amount]

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _quote_body(request: QuoteRequest) -> bytes:
    output = max(1, request.input_requested_atomic // 2)
    payload = {
        "inputMint": request.input_mint,
        "inAmount": str(request.input_requested_atomic),
        "outputMint": request.output_mint,
        "outAmount": str(output),
        "otherAmountThreshold": str(max(0, output - 1)),
        "swapMode": "ExactIn",
        "slippageBps": request.slippage_bps,
        "platformFee": None,
        "priceImpactPct": "0.001",
        "routePlan": [
            {
                "swapInfo": {
                    "ammKey": "synthetic-amm-key",
                    "label": "Synthetic AMM",
                    "inputMint": request.input_mint,
                    "outputMint": request.output_mint,
                    "inAmount": str(request.input_requested_atomic),
                    "outAmount": str(output),
                    "feeAmount": "0",
                    "feeMint": request.input_mint,
                },
                "percent": 100,
                "bps": 10000,
            }
        ],
        "contextSlot": 123,
        "timeTaken": 0.01,
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


class QuoteAwareOpener:
    def __init__(self) -> None:
        self.requests: list[object] = []

    def open(self, request: object, *, timeout: int) -> FakeResponse:
        self.requests.append(request)
        parsed = urllib.parse.urlsplit(request.full_url)
        query = urllib.parse.parse_qs(parsed.query)
        side = (
            Side.BUY
            if query["inputMint"][0]
            == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
            else Side.SELL
        )
        quote_request = QuoteRequest(
            side=side,
            input_mint=query["inputMint"][0],
            output_mint=query["outputMint"][0],
            input_requested_atomic=int(query["amount"][0]),
            input_decimals=6,
            output_decimals=6,
            slippage_bps=int(query["slippageBps"][0]),
            attempt_ordinal=len(self.requests),
            business_key=f"synthetic-{len(self.requests)}",
        )
        self.last_timeout = timeout
        return FakeResponse(_quote_body(quote_request))


class NoRouteTransport:
    def __init__(self, now: StepNow) -> None:
        self._now = now
        self._attempts = 0
        self._received_bytes = 0

    @property
    def attempts(self) -> int:
        return self._attempts

    @property
    def received_bytes(self) -> int:
        return self._received_bytes

    def execute(self, request: QuoteRequest):
        from solana_alpha_lab.jupiter_quote_logger import TransportObservation
        from solana_alpha_lab.jupiter_quote_transport import HttpCapture

        self._attempts += 1
        requested = self._now()
        response = self._now()
        body = (
            b'{"error":"Could not find any route",'
            b'"errorCode":"COULD_NOT_FIND_ANY_ROUTE"}'
        )
        self._received_bytes += len(body)
        return HttpCapture(
            observation=TransportObservation(
                requested_at=requested,
                response_at=response,
                first_reliable_available_at=response,
                available_to_strategy_at=response,
                ingested_at=response,
                http_status_code=400,
                response_body=body,
            ),
            received_bytes=len(body),
            transport_stop_reason=None,
        )


class Task10JupiterQuoteTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = load_pilot_plan(PLAN_PATH)

    def test_plan_freezes_task09_lineage_before_route_observation(self) -> None:
        self.assertEqual(
            self.plan.atom_id,
            "T10-A6_BOUNDED_EXTERNAL_QUOTE_PILOT_V2",
        )
        self.assertEqual(self.plan.run_id, "t10a6-20260728T015829Z")
        self.assertEqual(
            self.plan.logical_root,
            "task10_jupiter_quote_pilot_v2/"
            "run=t10a6-20260728T015829Z",
        )
        self.assertEqual(
            self.plan.selected_mint,
            "4vXNhA6ncbx8usZ14CfxkYeQKdaQYgrLfJXNyWcVpump",
        )
        self.assertEqual(self.plan.selected_mint_decimals, 6)
        self.assertEqual(
            self.plan.source_partition_sha256,
            "577e614c0b2f41b7a1e3ae92b6cfd965e87e4d4bca76070925873df1ef5b4466",
        )
        self.assertEqual(
            self.plan.source_raw_event_id,
            "raw-86dee058f272ebb62e54a1a7a3ee2ce840fe1c109e3b463b46d65914c71dc702",
        )
        self.assertEqual(self.plan.source_slot, 435592031)
        self.assertEqual(self.plan.caps.http_requests_total_max, 8)
        self.assertEqual(self.plan.caps.retries, 0)
        self.assertEqual(
            self.plan.caps.received_response_bytes_max,
            MAX_RECEIVED_BYTES,
        )
        self.assertEqual(
            self.plan.caps.durable_raw_bytes_max,
            MAX_DURABLE_BYTES,
        )

    def test_historical_stopped_plan_cannot_be_resumed(self) -> None:
        with self.assertRaisesRegex(
            QuoteTransportContractError,
            "pilot_plan_hash_mismatch",
        ):
            load_pilot_plan(HISTORICAL_PLAN_PATH)

    def test_wrong_authority_blocks_before_opener_use(self) -> None:
        with self.assertRaisesRegex(
            ExternalAuthorityRequiredError,
            "external_authority_phrase_mismatch",
        ):
            ExternalExecutionGate(authority_phrase="wrong")

    def test_transport_is_exact_host_path_keyless_and_zero_retry(self) -> None:
        opener = QuoteAwareOpener()
        clock = FakeClock()
        now = StepNow()
        transport = BoundedQuoteTransport(
            gate=ExternalExecutionGate(
                authority_phrase=EXTERNAL_AUTHORITY_PHRASE
            ),
            opener=opener,
            clock=clock.monotonic,
            sleeper=clock.sleep,
            now=now,
        )
        request = QuoteRequest(
            side=Side.BUY,
            input_mint=self.plan.quote_mint,
            output_mint=self.plan.selected_mint,
            input_requested_atomic=10_000_000,
            input_decimals=6,
            output_decimals=6,
            slippage_bps=100,
            attempt_ordinal=1,
            business_key="task10-panel-usd-10",
        )
        capture = transport.execute(request)
        self.assertEqual(capture.observation.http_status_code, 200)
        self.assertEqual(transport.attempts, 1)
        self.assertEqual(transport.received_bytes, capture.received_bytes)
        outgoing = opener.requests[0]
        parsed = urllib.parse.urlsplit(outgoing.full_url)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.hostname, "api.jup.ag")
        self.assertEqual(parsed.path, "/swap/v1/quote")
        self.assertNotIn("Authorization", outgoing.headers)
        self.assertNotIn("X-api-key", outgoing.headers)
        self.assertEqual(opener.last_timeout, 20)

    def test_runner_executes_four_buy_and_four_exact_reverse_sell(self) -> None:
        opener = QuoteAwareOpener()
        clock = FakeClock()
        now = StepNow()
        transport = BoundedQuoteTransport(
            gate=ExternalExecutionGate(
                authority_phrase=EXTERNAL_AUTHORITY_PHRASE
            ),
            opener=opener,
            clock=clock.monotonic,
            sleeper=clock.sleep,
            now=now,
        )
        sink = InMemoryQuoteSink(run_id=self.plan.run_id)
        summary = QuotePilotRunner(
            plan=self.plan,
            transport=transport,
            sink=sink,
            clock=clock.monotonic,
        ).run()
        self.assertEqual(summary.status, "COMPLETE")
        self.assertEqual(summary.provider_calls, MAX_HTTP_REQUESTS)
        self.assertEqual(summary.buy_attempts, 4)
        self.assertEqual(summary.sell_attempts, 4)
        self.assertEqual(summary.sell_not_attempted, 0)
        self.assertEqual(summary.stored_events, 8)
        self.assertEqual(
            summary.terminal_counts,
            {"QUOTE_AVAILABLE": 8},
        )
        for panel in range(4):
            buy = sink.projections[panel * 2].quote_attempt
            sell = sink.projections[panel * 2 + 1].quote_attempt
            self.assertEqual(
                sell.input_requested_atomic,
                buy.output_quoted_atomic,
            )
            self.assertEqual(sell.input_mint, buy.output_mint)
            self.assertEqual(sell.output_mint, buy.input_mint)
        self.assertEqual(len(clock.sleeps), 7)
        self.assertTrue(all(value == 2.2 for value in clock.sleeps))

    def test_no_route_buys_never_create_sell_requests(self) -> None:
        now = StepNow()
        transport = NoRouteTransport(now)
        sink = InMemoryQuoteSink(run_id=self.plan.run_id)
        summary = QuotePilotRunner(
            plan=self.plan,
            transport=transport,
            sink=sink,
            clock=lambda: 0.0,
        ).run()
        self.assertEqual(summary.status, "COMPLETE")
        self.assertEqual(summary.provider_calls, 4)
        self.assertEqual(summary.buy_attempts, 4)
        self.assertEqual(summary.sell_attempts, 0)
        self.assertEqual(summary.sell_not_attempted, 4)
        self.assertEqual(summary.terminal_counts, {"NO_ROUTE": 4})

    def test_authentication_response_stops_after_first_attempt(self) -> None:
        body = b"authentication required"

        class AuthOpener:
            calls = 0

            def open(self, request: object, *, timeout: int) -> object:
                self.calls += 1
                raise urllib.error.HTTPError(
                    request.full_url,
                    401,
                    "Unauthorized",
                    {"Content-Length": str(len(body))},
                    io.BytesIO(body),
                )

        opener = AuthOpener()
        clock = FakeClock()
        transport = BoundedQuoteTransport(
            gate=ExternalExecutionGate(
                authority_phrase=EXTERNAL_AUTHORITY_PHRASE
            ),
            opener=opener,
            clock=clock.monotonic,
            sleeper=clock.sleep,
            now=StepNow(),
        )
        sink = InMemoryQuoteSink(run_id=self.plan.run_id)
        summary = QuotePilotRunner(
            plan=self.plan,
            transport=transport,
            sink=sink,
            clock=clock.monotonic,
        ).run()
        self.assertEqual(summary.status, "STOPPED")
        self.assertEqual(
            summary.stop_reason,
            "AUTHENTICATION_OR_ACCOUNT_REQUIRED",
        )
        self.assertEqual(summary.provider_calls, 1)
        self.assertEqual(opener.calls, 1)
        self.assertEqual(
            summary.terminal_counts,
            {"PROVIDER_ERROR": 1},
        )

    def test_durable_sink_writes_raw_and_quote_relation_under_cap(self) -> None:
        opener = QuoteAwareOpener()
        clock = FakeClock()
        transport = BoundedQuoteTransport(
            gate=ExternalExecutionGate(
                authority_phrase=EXTERNAL_AUTHORITY_PHRASE
            ),
            opener=opener,
            clock=clock.monotonic,
            sleeper=clock.sleep,
            now=StepNow(),
        )
        with tempfile.TemporaryDirectory() as directory:
            raw_root = Path(directory).resolve()
            sink = DurableQuotePilotSink(
                raw_root=raw_root,
                schema_path=SCHEMA_PATH,
                plan=self.plan,
            )
            summary = QuotePilotRunner(
                plan=self.plan,
                transport=transport,
                sink=sink,
                clock=clock.monotonic,
            ).run()
            run_root = (
                raw_root
                / "task10_jupiter_quote_pilot_v2"
                / f"run={self.plan.run_id}"
            )
            database = run_root / self.plan.projection_database
            connection = duckdb.connect(str(database), read_only=True)
            try:
                quote_count = connection.execute(
                    "SELECT COUNT(*) FROM quote_attempts"
                ).fetchone()[0]
                execution_count = connection.execute(
                    "SELECT COUNT(*) FROM execution_attempts"
                ).fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(summary.status, "COMPLETE")
            self.assertEqual(summary.stored_events, 8)
            self.assertEqual(quote_count, 8)
            self.assertEqual(execution_count, 0)
            self.assertLessEqual(summary.stored_bytes, MAX_DURABLE_BYTES)
            self.assertTrue(
                (run_root / self.plan.raw_partition).is_file()
            )
            self.assertTrue(
                (run_root / self.plan.manifest_location).is_file()
            )
            self.assertTrue(
                (run_root / self.plan.receipt_location).is_file()
            )

    def test_plan_provider_identity_is_compatibility_only(self) -> None:
        self.assertEqual(PROVIDER, "JUPITER_METIS")
        self.assertEqual(PROVIDER_VERSION, "legacy_metis_v1_quote")
        self.assertEqual(self.plan.base_url, "https://api.jup.ag")
        self.assertEqual(self.plan.path, "/swap/v1/quote")
        self.assertEqual(self.plan.caps.provider_credits, 0)
        self.assertEqual(self.plan.caps.cash_spend_usd_cents, 0)
        self.assertEqual(
            self.plan.caps.wallet_signer_transaction_actions,
            0,
        )


if __name__ == "__main__":
    unittest.main()
