from __future__ import annotations

import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.quote_native_evidence_channel_qualification import (  # noqa: E402
    AUTHORITY_PHRASE,
    QualificationError,
    load_process_credential,
    perform_credentialed_get,
    run_campaign,
    validate_policy,
)


ORDER_URL = (
    "https://api.jup.ag/swap/v2/order?"
    "inputMint=So11111111111111111111111111111111111111112&"
    "outputMint=ExampleMint111111111111111111111111111111111&"
    "amount=10000000&slippageBps=100"
)
SEARCH_URL = (
    "https://api.jup.ag/tokens/v2/search?query="
    "MintA111111111111111111111111111111111111111%2CMintB222222222222222222222222222222222222222"
)
LIMITS = {"timeout_seconds": 20.0, "max_response_bytes": 500_000}
CONFIG_PATH = ROOT / "configs/quote_native_evidence_channel_qualification_v1.yaml"
RUNTIME_RECEIPT_PATH = (
    ROOT
    / "docs/evidence/quote_native_evidence_channel_qualification"
    / "a1_quote_native_evidence_channel_qualification_runtime_receipt_v1.json"
)
TIMING_RECOVERY_PATH = (
    ROOT
    / "docs/evidence/quote_native_evidence_channel_qualification"
    / "a1_quote_native_evidence_channel_qualification_timing_recovery_v1.json"
)
ACCEPTANCE_PATH = (
    ROOT
    / "docs/evidence/quote_native_evidence_channel_qualification"
    / "a1_quote_native_evidence_channel_qualification_acceptance_v1.json"
)


class _Response:
    def __init__(
        self,
        body: bytes,
        *,
        status: int,
        headers: dict[str, str],
    ) -> None:
        self._body = io.BytesIO(body)
        self._status = status
        self.headers = headers

    def getcode(self) -> int:
        return self._status

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _Opener:
    def __init__(self, response: _Response | urllib.error.HTTPError) -> None:
        self.response = response
        self.requests: list[object] = []

    def open(self, request: object, timeout: float = 0) -> _Response:
        self.requests.append(request)
        if isinstance(self.response, urllib.error.HTTPError):
            raise self.response
        return self.response


class _SequenceOpener:
    def __init__(self, responses: list[_Response | urllib.error.HTTPError]) -> None:
        self.responses = list(responses)
        self.requests: list[object] = []

    def open(self, request: object, timeout: float = 0) -> _Response:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("unexpected provider request")
        response = self.responses.pop(0)
        if isinstance(response, urllib.error.HTTPError):
            raise response
        return response


class _SlowSequenceOpener(_SequenceOpener):
    def __init__(
        self,
        responses: list[_Response | urllib.error.HTTPError],
        *,
        clock: _Clock,
        slow_call_number: int,
        elapsed_seconds: int,
    ) -> None:
        super().__init__(responses)
        self._clock = clock
        self._slow_call_number = slow_call_number
        self._elapsed_seconds = elapsed_seconds

    def open(self, request: object, timeout: float = 0) -> _Response:
        response = super().open(request, timeout=timeout)
        if len(self.requests) == self._slow_call_number:
            self._clock.current += timedelta(seconds=self._elapsed_seconds)
        return response


class _TransportFailureOpener:
    def __init__(self) -> None:
        self.requests: list[object] = []

    def open(self, request: object, timeout: float = 0) -> _Response:
        self.requests.append(request)
        raise urllib.error.URLError("network unavailable")


class _Clock:
    def __init__(self, start: datetime) -> None:
        self.started = start
        self.current = start
        self.sleeps: list[float] = []

    def __call__(self) -> datetime:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += timedelta(seconds=seconds)

    def monotonic(self) -> float:
        return (self.current - self.started).total_seconds()


def _token_rows(prefix: str) -> bytes:
    payload = [
        {
            "id": f"{prefix}{index:02d}111111111111111111111111111111111",
            "liquidity": 2_000,
            "firstPool": {"createdAt": f"2026-08-18T00:{index:02d}:00Z"},
        }
        for index in range(1, 7)
    ]
    return json.dumps(payload).encode("utf-8")


def _quote_body(amount: str, *, out_amount: str = "1000000") -> bytes:
    return json.dumps(
        {
            "transaction": None,
            "requestId": "request-1",
            "inAmount": amount,
            "outAmount": out_amount,
            "router": "metis",
            "mode": "manual",
            "priceImpactPct": "0.01",
            "platformFee": None,
            "feeBps": "1",
            "routePlan": [],
        }
    ).encode("utf-8")


def _transaction_bearing_body() -> bytes:
    return json.dumps(
        {
            "transaction": "must-not-be-retained",
            "requestId": "request-with-transaction",
        }
    ).encode("utf-8")


def _policy() -> dict[str, Any]:
    return {
        "atom_id": "QUOTE_NATIVE_EVIDENCE_CHANNEL_QUALIFICATION_V1",
        "external_authority": {
            "owner_phrase": AUTHORITY_PHRASE,
            "credential_name": "JUPITER_API_KEY",
            "credential_reads": 1,
            "dotenv_reads": False,
            "execute": False,
            "build": False,
            "taker": "OMITTED_QUOTE_ONLY",
            "cash_cap_usd_cents": 0,
            "call_cap": 60,
        },
        "quote_route": {
            "route_id": "JUPITER-SOLANA-SWAP-V2-ORDER-FREE-API-KEY-001",
            "endpoint": "https://api.jup.ag/swap/v2/order",
            "host": "api.jup.ag",
            "method": "GET",
        },
        "discovery_routes": {
            "recent": {
                "route_id": "JUPITER-SOLANA-TOKENS-V2-RECENT-FREE-API-KEY-001",
                "endpoint": "https://api.jup.ag/tokens/v2/recent",
            },
            "traded": {
                "route_id": "JUPITER-SOLANA-TOKENS-V2-TOPTRADED-FREE-API-KEY-001",
                "endpoint": "https://api.jup.ag/tokens/v2/toptraded/1h",
            },
        },
        "wrapped_sol_mint": "So11111111111111111111111111111111111111112",
        "slippage_bps": "100",
        "notional_atomic": "10000000",
        "recent_cell_count": 6,
        "traded_cell_count": 6,
        "liquidity_floor_usd": 1000,
        "min_interval_seconds": 3,
        "observable_horizon_seconds": [900, 3600],
        "gap_horizon_seconds": [14400],
        "lateness_slack_seconds": 120,
        "control_kill": {
            "min_complete_cells": 6,
            "min_time_separated_share": "0.5",
        },
        "success": {
            "min_complete_xy": 10,
            "min_time_separated": 6,
        },
        "runtime_limits": LIMITS,
        "execution_controls": {
            "retries": 0,
            "fallback": False,
            "persist_transaction_bytes": False,
            "provider_requests_max": 60,
            "background_scheduler": False,
            "second_provider": False,
            "paid_plan": False,
        },
    }


class CredentialTransportTests(unittest.TestCase):
    def test_process_credential_rejects_missing_or_blank_value(self) -> None:
        with self.assertRaisesRegex(
            QualificationError,
            "JUPITER_API_KEY_MISSING_OR_EMPTY",
        ):
            load_process_credential({})

        with self.assertRaisesRegex(
            QualificationError,
            "JUPITER_API_KEY_MISSING_OR_EMPTY",
        ):
            load_process_credential({"JUPITER_API_KEY": "   "})

    def test_credential_is_sent_only_in_request_header_and_safe_headers_are_allowlisted(self) -> None:
        key = "test-free-key-not-a-secret"
        opener = _Opener(
            _Response(
                b'{"requestId":"request-1"}',
                status=200,
                headers={
                    "Content-Type": "application/json",
                    "x-api-gateway-request-id": "gateway-request-1",
                    "retry-after": "3",
                    "set-cookie": "must-not-be-retained",
                },
            )
        )

        result = perform_credentialed_get(
            ORDER_URL,
            api_key=key,
            limits=LIMITS,
            opener=opener,
        )

        self.assertEqual(result["http_status"], 200)
        self.assertEqual(
            result["safe_response_headers"],
            {
                "retry-after": "3",
                "x-api-gateway-request-id": "gateway-request-1",
            },
        )
        self.assertNotIn("content_type", result)
        self.assertFalse(result["url_has_api_key"])
        request = opener.requests[0]
        self.assertNotIn(key, str(getattr(request, "full_url")))
        headers = {
            str(name).casefold(): str(value)
            for name, value in getattr(request, "header_items")()
        }
        self.assertEqual(headers["x-api-key"], key)
        receipt_view = {name: value for name, value in result.items() if name != "body"}
        self.assertNotIn(key, json.dumps(receipt_view, sort_keys=True))

    def test_transport_view_preserves_url_has_api_key_detector(self) -> None:
        from solana_alpha_lab.quote_native_evidence_channel_qualification import (
            _transport_view,
        )

        view = _transport_view(
            {
                "http_status": 200,
                "url_has_api_key": True,
                "safe_response_headers": {},
            }
        )
        self.assertTrue(view["url_has_api_key"])

    def test_rate_limited_response_retains_only_safe_headers_without_raising_or_retrying(self) -> None:
        key = "test-free-key-not-a-secret"
        error = urllib.error.HTTPError(
            ORDER_URL,
            429,
            "rate limited",
            hdrs={
                "Content-Type": "application/json",
                "x-api-gateway-request-id": "gateway-request-429",
                "retry-after": "3",
                "set-cookie": "must-not-be-retained",
            },
            fp=io.BytesIO(b'{"error":"rate limited"}'),
        )
        opener = _Opener(error)

        result = perform_credentialed_get(
            ORDER_URL,
            api_key=key,
            limits=LIMITS,
            opener=opener,
        )

        self.assertEqual(result["http_status"], 429)
        self.assertEqual(result["response_bytes"], len(b'{"error":"rate limited"}'))
        self.assertEqual(
            result["safe_response_headers"],
            {
                "retry-after": "3",
                "x-api-gateway-request-id": "gateway-request-429",
            },
        )
        receipt_view = {name: value for name, value in result.items() if name != "body"}
        self.assertNotIn(key, json.dumps(receipt_view, sort_keys=True))
        self.assertEqual(len(opener.requests), 1)

    def test_endpoint_specific_query_allowlist_rejects_credential_like_or_unknown_parameters(self) -> None:
        key = "test-free-key-not-a-secret"
        credential_query_name = "api" + "Key"
        for unsafe_url in (
            f"{ORDER_URL}&{credential_query_name}=abcdefghijkl",
            f"{ORDER_URL}&unknown=1",
            "https://api.jup.ag/tokens/v2/recent?limit=10",
        ):
            with self.subTest(url=unsafe_url):
                with self.assertRaisesRegex(QualificationError, "QUERY_ALLOWLIST_DRIFT"):
                    perform_credentialed_get(
                        unsafe_url,
                        api_key=key,
                        limits=LIMITS,
                        opener=_Opener(
                            _Response(b"{}", status=200, headers={})
                        ),
                    )

        with self.assertRaisesRegex(QualificationError, "ENDPOINT_USERINFO_FORBIDDEN"):
            perform_credentialed_get(
                f"https://{key}@api.jup.ag/tokens/v2/recent",
                api_key=key,
                limits=LIMITS,
                opener=_Opener(_Response(b"{}", status=200, headers={})),
            )

    def test_tokens_search_query_is_allowlisted_for_frozen_mint_batches(self) -> None:
        key = "test-free-key-not-a-secret"
        opener = _Opener(_Response(b"[]", status=200, headers={}))
        result = perform_credentialed_get(
            SEARCH_URL,
            api_key=key,
            limits=LIMITS,
            opener=opener,
        )

        self.assertEqual(result["http_status"], 200)
        self.assertEqual(len(opener.requests), 1)
        self.assertNotIn("x-api-key", opener.requests[0].full_url.lower())


class CampaignBoundaryTests(unittest.TestCase):
    def test_committed_policy_binds_all_three_v9_routes_and_preserves_measurement_thresholds(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(policy, dict)
        validate_policy(policy, root=ROOT)

        self.assertEqual(policy["recent_cell_count"], 6)
        self.assertEqual(policy["traded_cell_count"], 6)
        self.assertEqual(
            policy["success"],
            {"min_complete_xy": 10, "min_time_separated": 6},
        )
        self.assertEqual(
            policy["control_kill"],
            {"min_complete_cells": 6, "min_time_separated_share": "0.5"},
        )
        self.assertEqual(policy["external_authority"]["credential_name"], "JUPITER_API_KEY")
        self.assertFalse(policy["external_authority"]["dotenv_reads"])

    def test_policy_rejects_owner_phrase_drift(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(policy, dict)
        tampered = copy.deepcopy(policy)
        tampered["external_authority"]["owner_phrase"] = "different phrase"

        with self.assertRaisesRegex(QualificationError, "AUTHORITY_PHRASE_DRIFT"):
            validate_policy(tampered, root=ROOT)

    def test_policy_rejects_paid_plan_or_transaction_retention_drift(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(policy, dict)
        paid = copy.deepcopy(policy)
        paid["execution_controls"]["paid_plan"] = True
        persisted = copy.deepcopy(policy)
        persisted["execution_controls"]["persist_transaction_bytes"] = True

        with self.assertRaisesRegex(QualificationError, "PAID_PLAN_NOT_FORBIDDEN"):
            validate_policy(paid, root=ROOT)
        with self.assertRaisesRegex(QualificationError, "TX_PERSIST_NOT_FORBIDDEN"):
            validate_policy(persisted, root=ROOT)

    def test_preflight_precedes_single_key_read_and_429_closes_campaign_without_retry(self) -> None:
        key = "test-free-key-not-a-secret"
        events: list[str] = []
        clock = _Clock(datetime(2026, 8, 18, 12, 0, tzinfo=UTC))
        rate_limited = urllib.error.HTTPError(
            ORDER_URL,
            429,
            "rate limited",
            hdrs={"Content-Type": "application/json", "retry-after": "3"},
            fp=io.BytesIO(b'{"error":"rate limited"}'),
        )
        opener = _SequenceOpener(
            [
                _Response(_token_rows("Recent"), status=200, headers={}),
                _Response(_token_rows("Traded"), status=200, headers={}),
                _Response(_quote_body("10000000"), status=200, headers={}),
                _Response(_quote_body("1000000"), status=200, headers={}),
                rate_limited,
            ]
        )

        def preflight(*_args: object, **_kwargs: object) -> dict[str, object]:
            events.append("preflight")
            return {"credential_reads": 0, "dns_resolved": True}

        def credential_loader() -> str:
            events.append("credential")
            return key

        receipt = run_campaign(
            _policy(),
            credential_loader=credential_loader,
            preflight_fn=preflight,
            opener=opener,
            clock=clock,
            sleeper=clock.sleep,
            monotonic_clock=clock.monotonic,
        )

        self.assertEqual(events, ["preflight", "credential"])
        self.assertEqual(receipt["credential_reads"], 1)
        self.assertEqual(
            receipt["terminal_outcome"],
            "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE",
        )
        self.assertEqual(receipt["provider_requests"], 5)
        self.assertEqual(receipt["retries"], 0)
        self.assertEqual(receipt["fallbacks"], 0)
        self.assertGreaterEqual(len(clock.sleeps), 1)
        self.assertTrue(all(delay >= 3 for delay in clock.sleeps))
        self.assertNotIn(key, json.dumps(receipt, sort_keys=True))
        self.assertTrue(
            all(
                isinstance(row.get("observed_at"), str)
                for row in receipt["discovery_observations"]
            )
        )
        self.assertTrue(
            all(
                isinstance(row.get("observed_at"), str)
                for row in receipt["observations"]
                if row.get("consumed_call")
            )
        )
        t0_rows = [
            row
            for row in receipt["observations"]
            if row["wave"] == "t0" and row["identity_id"] != "RECENT_1"
        ]
        self.assertTrue(any(row["terminal"] == "NOT_REACHED" for row in t0_rows))
        cancelled_horizons = [
            row
            for row in receipt["observations"]
            if row["wave"] == "horizon"
        ]
        self.assertTrue(
            all(
                row["terminal"] == "CANCELLED_AFTER_TERMINAL"
                for row in cancelled_horizons
            )
        )

    def test_complete_foreground_baseline_records_numeric_scorer_pass_not_acceptance(self) -> None:
        key = "test-free-key-not-a-secret"
        clock = _Clock(datetime(2026, 8, 18, 12, 0, tzinfo=UTC))
        order_responses: list[_Response] = []
        for _ in range(12):
            order_responses.append(
                _Response(_quote_body("10000000", out_amount="1000000"), status=200, headers={})
            )
            order_responses.append(
                _Response(_quote_body("1000000", out_amount="990000"), status=200, headers={})
            )
        order_responses.extend(
            _Response(_quote_body("1000000", out_amount="980000"), status=200, headers={})
            for _ in range(12)
        )
        order_responses.extend(
            _Response(_quote_body("1000000", out_amount="970000"), status=200, headers={})
            for _ in range(12)
        )
        opener = _SequenceOpener(
            [
                _Response(_token_rows("Recent"), status=200, headers={}),
                _Response(_token_rows("Traded"), status=200, headers={}),
                *order_responses,
            ]
        )

        receipt = run_campaign(
            _policy(),
            credential_loader=lambda: key,
            preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0},
            opener=opener,
            clock=clock,
            sleeper=clock.sleep,
            monotonic_clock=clock.monotonic,
        )

        self.assertEqual(receipt["terminal_outcome"], "QUOTE_NATIVE_EVIDENCE_FIT_PASS")
        self.assertEqual(receipt["provider_requests"], 50)
        self.assertEqual(receipt["credential_reads"], 1)
        self.assertEqual(receipt["campaign"]["complete_xy_count"], 12)
        self.assertEqual(receipt["campaign"]["time_separated_complete_xy_count"], 12)
        self.assertEqual(receipt["campaign"]["traded_complete_xy_count"], 6)
        self.assertEqual(receipt["campaign"]["traded_time_separated_count"], 6)
        self.assertFalse(receipt["campaign"]["family_close"])
        self.assertNotIn(key, json.dumps(receipt, sort_keys=True))
        transports = [
            row["transport"]
            for row in [*receipt["discovery_observations"], *receipt["observations"]]
            if isinstance(row.get("transport"), dict)
        ]
        self.assertTrue(transports)
        self.assertTrue(all(row["url_has_api_key"] is False for row in transports))
        self.assertNotEqual(
            receipt["terminal_outcome"],
            "EVIDENCE_FIT_ACCEPTED",
        )

    def test_transaction_bearing_order_body_is_never_sent_to_raw_sink(self) -> None:
        clock = _Clock(datetime(2026, 8, 18, 12, 0, tzinfo=UTC))
        raw_ids: list[str] = []
        opener = _SequenceOpener(
            [
                _Response(_token_rows("Recent"), status=200, headers={}),
                _Response(_token_rows("Traded"), status=200, headers={}),
                *[
                    _Response(_transaction_bearing_body(), status=200, headers={})
                    for _ in range(12)
                ],
            ]
        )

        run_campaign(
            _policy(),
            credential_loader=lambda: "test-free-key-not-a-secret",
            preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0},
            opener=opener,
            clock=clock,
            sleeper=clock.sleep,
            monotonic_clock=clock.monotonic,
            raw_sink=lambda observation_id, _body, _observed_at: raw_ids.append(observation_id),
        )

        self.assertEqual(raw_ids, ["DISCOVERY:RECENT", "DISCOVERY:TRADED"])

    def test_nested_transaction_in_discovery_list_is_not_sent_to_raw_sink(self) -> None:
        clock = _Clock(datetime(2026, 8, 18, 12, 0, tzinfo=UTC))
        raw_ids: list[str] = []
        nested = json.dumps(
            [
                {
                    "id": "Recent011111111111111111111111111111111",
                    "liquidity": 2_000,
                    "firstPool": {"createdAt": "2026-08-18T00:01:00Z"},
                    "transaction": "nested",
                }
            ]
        ).encode("utf-8")
        opener = _SequenceOpener(
            [
                _Response(nested, status=200, headers={}),
                _Response(_token_rows("Traded"), status=200, headers={}),
            ]
        )

        run_campaign(
            _policy(),
            credential_loader=lambda: "test-free-key-not-a-secret",
            preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0},
            opener=opener,
            clock=clock,
            sleeper=clock.sleep,
            monotonic_clock=clock.monotonic,
            raw_sink=lambda observation_id, _body, _observed_at: raw_ids.append(observation_id),
        )

        self.assertEqual(raw_ids, ["DISCOVERY:TRADED"])

    def test_late_horizon_cells_are_marked_missed_without_extra_provider_calls(self) -> None:
        clock = _Clock(datetime(2026, 8, 18, 12, 0, tzinfo=UTC))
        order_responses: list[_Response] = []
        for _ in range(12):
            order_responses.append(
                _Response(_quote_body("10000000", out_amount="1000000"), status=200, headers={})
            )
            order_responses.append(
                _Response(_quote_body("1000000", out_amount="990000"), status=200, headers={})
            )
        order_responses.append(
            _Response(_quote_body("1000000", out_amount="980000"), status=200, headers={})
        )
        opener = _SlowSequenceOpener(
            [
                _Response(_token_rows("Recent"), status=200, headers={}),
                _Response(_token_rows("Traded"), status=200, headers={}),
                *order_responses,
            ],
            clock=clock,
            slow_call_number=27,
            elapsed_seconds=121,
        )

        receipt = run_campaign(
            _policy(),
            credential_loader=lambda: "test-free-key-not-a-secret",
            preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0},
            opener=opener,
            clock=clock,
            sleeper=clock.sleep,
            monotonic_clock=clock.monotonic,
        )

        self.assertEqual(receipt["provider_requests"], 27)
        self.assertEqual(
            receipt["terminal_outcome"],
            "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE",
        )
        missed = [
            row
            for row in receipt["observations"]
            if row["horizon_seconds"] == 900
        ]
        self.assertTrue(all(row["terminal"] == "MISSED_OFFSET" for row in missed))
        self.assertEqual(len(missed), 12)

    def test_production_default_sleeper_is_not_a_noop(self) -> None:
        from unittest.mock import patch

        opener = _SequenceOpener(
            [
                _Response(_token_rows("Recent"), status=200, headers={}),
                _Response(_token_rows("Traded"), status=200, headers={}),
                _Response(_quote_body("10000000"), status=200, headers={}),
                _Response(_quote_body("1000000"), status=200, headers={}),
                urllib.error.HTTPError(
                    ORDER_URL,
                    429,
                    "rate limited",
                    hdrs={"Content-Type": "application/json"},
                    fp=io.BytesIO(b'{"error":"rate limited"}'),
                ),
            ]
        )
        with patch(
            "solana_alpha_lab.quote_native_evidence_channel_qualification.time.sleep"
        ) as sleeper:
            run_campaign(
                _policy(),
                credential_loader=lambda: "test-free-key-not-a-secret",
                preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0},
                opener=opener,
                clock=lambda: datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
            )

        self.assertGreaterEqual(sleeper.call_count, 1)

    def test_post_credential_transport_failure_returns_typed_terminal_receipt(self) -> None:
        clock = _Clock(datetime(2026, 8, 18, 12, 0, tzinfo=UTC))
        opener = _TransportFailureOpener()

        receipt = run_campaign(
            _policy(),
            credential_loader=lambda: "test-free-key-not-a-secret",
            preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0},
            opener=opener,
            clock=clock,
            sleeper=clock.sleep,
            monotonic_clock=clock.monotonic,
        )

        self.assertEqual(
            receipt["terminal_outcome"],
            "TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED",
        )
        self.assertEqual(receipt["credential_reads"], 1)
        self.assertEqual(receipt["provider_requests"], 1)
        self.assertEqual(len(opener.requests), 1)


class RunnerTests(unittest.TestCase):
    def test_existing_campaign_reservation_stops_before_preflight_or_credential_read(self) -> None:
        from scripts.run_quote_native_evidence_channel_qualification import run_capture

        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(policy, dict)
        authority_phrase = policy["external_authority"]["owner_phrase"]
        environment_name = policy["external_authority"]["credential_name"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_root = root / "raw"
            raw_root.mkdir()
            (raw_root / "campaign_reservation.json").write_text(
                '{"state":"STARTED"}\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                QualificationError,
                "CAMPAIGN_RESERVATION_EXISTS",
            ):
                run_capture(
                    authority_phrase=authority_phrase,
                    policy=policy,
                    raw_root=raw_root,
                    receipt_path=root / "runtime.json",
                    environ={environment_name: "test-free-key-not-a-secret"},
                    preflight_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                        AssertionError("preflight should not run")
                    ),
                    opener=_SequenceOpener([]),
                    clock=_Clock(datetime(2026, 8, 18, 12, 0, tzinfo=UTC)),
                    sleeper=lambda _seconds: None,
                )

    def test_preflight_failure_writes_typed_zero_credential_terminal_receipt(self) -> None:
        from scripts.run_quote_native_evidence_channel_qualification import run_capture

        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(policy, dict)
        authority_phrase = policy["external_authority"]["owner_phrase"]
        environment_name = policy["external_authority"]["credential_name"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = run_capture(
                authority_phrase=authority_phrase,
                policy=policy,
                raw_root=root / "raw",
                receipt_path=root / "runtime.json",
                environ={environment_name: "test-free-key-not-a-secret"},
                preflight_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    QualificationError("DNS_PREFLIGHT_FAILED")
                ),
                opener=_SequenceOpener([]),
                clock=_Clock(datetime(2026, 8, 18, 12, 0, tzinfo=UTC)),
                sleeper=lambda _seconds: None,
            )

            self.assertEqual(
                receipt["terminal_outcome"],
                "TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED",
            )
            self.assertEqual(receipt["credential_reads"], 0)
            self.assertEqual(receipt["provider_requests"], 0)
            self.assertTrue((root / "runtime.json").is_file())

    def test_empty_injected_environment_never_falls_back_to_process_environment(self) -> None:
        from scripts.run_quote_native_evidence_channel_qualification import run_capture

        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(policy, dict)
        authority_phrase = policy["external_authority"]["owner_phrase"]
        environment_name = policy["external_authority"]["credential_name"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict(
                "scripts.run_quote_native_evidence_channel_qualification.os.environ",
                {environment_name: "x"},
                clear=True,
            ):
                receipt = run_capture(
                    authority_phrase=authority_phrase,
                    policy=policy,
                    raw_root=root / "raw",
                    receipt_path=root / "runtime.json",
                    environ={},
                    preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0},
                    opener=_SequenceOpener([]),
                    clock=_Clock(datetime(2026, 8, 18, 12, 0, tzinfo=UTC)),
                    sleeper=lambda _seconds: None,
                )

            self.assertEqual(
                receipt["terminal_outcome"],
                "TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED",
            )
            self.assertEqual(receipt["credential_reads"], 1)
            self.assertEqual(receipt["provider_requests"], 0)

    def test_runner_creates_local_raw_and_secret_free_receipt(self) -> None:
        from scripts.run_quote_native_evidence_channel_qualification import run_capture

        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(policy, dict)
        authority_phrase = policy["external_authority"]["owner_phrase"]
        environment_name = policy["external_authority"]["credential_name"]
        key = "test-free-key-not-a-secret"
        clock = _Clock(datetime(2026, 8, 18, 12, 0, tzinfo=UTC))
        rate_limited = urllib.error.HTTPError(
            ORDER_URL,
            429,
            "rate limited",
            hdrs={"Content-Type": "application/json", "retry-after": "3"},
            fp=io.BytesIO(b'{"error":"rate limited"}'),
        )
        opener = _SequenceOpener(
            [
                _Response(_token_rows("Recent"), status=200, headers={}),
                _Response(_token_rows("Traded"), status=200, headers={}),
                _Response(_quote_body("10000000"), status=200, headers={}),
                _Response(_quote_body("1000000"), status=200, headers={}),
                rate_limited,
            ]
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt_path = root / "runtime.json"
            raw_root = root / "raw"
            receipt = run_capture(
                authority_phrase=authority_phrase,
                policy=policy,
                raw_root=raw_root,
                receipt_path=receipt_path,
                environ={environment_name: key},
                preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0},
                opener=opener,
                clock=clock,
                sleeper=clock.sleep,
            )

            self.assertTrue(receipt_path.is_file())
            self.assertEqual(
                receipt["terminal_outcome"],
                "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE",
            )
            self.assertEqual(receipt["credential_reads"], 1)
            self.assertNotIn(key, receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(len(list(raw_root.rglob("*.json"))), 6)
            self.assertTrue((raw_root / "campaign_reservation.json").is_file())
            self.assertEqual(
                receipt["attempt_reservation"]["path"],
                "campaign_reservation.json",
            )
            self.assertTrue(
                all(
                    isinstance(manifest["raw_write_complete_at"], str)
                    and manifest["raw_write_complete_at"].endswith("Z")
                    and isinstance(manifest["observed_at"], str)
                    for manifest in receipt["raw_retention"]["manifests"]
                )
            )

    def test_api_key_in_order_url_keeps_typed_terminal_and_counted_requests(self) -> None:
        from scripts.run_quote_native_evidence_channel_qualification import run_capture

        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(policy, dict)
        authority_phrase = policy["external_authority"]["owner_phrase"]
        environment_name = policy["external_authority"]["credential_name"]
        wrapped_sol = str(policy["wrapped_sol_mint"])
        clock = _Clock(datetime(2026, 8, 18, 12, 0, tzinfo=UTC))
        opener = _SequenceOpener(
            [
                _Response(_token_rows("Recent"), status=200, headers={}),
                _Response(_token_rows("Traded"), status=200, headers={}),
                _Response(_quote_body("10000000"), status=200, headers={}),
            ]
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt_path = root / "runtime.json"
            receipt = run_capture(
                authority_phrase=authority_phrase,
                policy=policy,
                raw_root=root / "raw",
                receipt_path=receipt_path,
                environ={environment_name: wrapped_sol},
                preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0},
                opener=opener,
                clock=clock,
                sleeper=clock.sleep,
            )

            self.assertEqual(
                receipt["terminal_outcome"],
                "API_KEY_IN_URL_LOG_RECEIPT_OR_GIT",
            )
            self.assertEqual(
                receipt["terminal_error_code"],
                "API_KEY_IN_URL_LOG_RECEIPT_OR_GIT",
            )
            self.assertEqual(
                receipt["campaign"]["campaign_verdict"],
                "API_KEY_IN_URL_LOG_RECEIPT_OR_GIT",
            )
            self.assertGreaterEqual(receipt["provider_requests"], 3)
            self.assertEqual(receipt["credential_reads"], 1)
            self.assertNotEqual(
                receipt["terminal_outcome"],
                "TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED",
            )
            self.assertNotIn(wrapped_sol, receipt_path.read_text(encoding="utf-8"))


class AcceptanceEvidenceTests(unittest.TestCase):
    def test_acceptance_is_hash_bound_to_runtime_and_timing_recovery(self) -> None:
        runtime = json.loads(RUNTIME_RECEIPT_PATH.read_text(encoding="utf-8"))
        timing = json.loads(TIMING_RECOVERY_PATH.read_text(encoding="utf-8"))
        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(runtime["terminal_outcome"], "QUOTE_NATIVE_EVIDENCE_FIT_PASS")
        self.assertEqual(
            acceptance["terminal"],
            "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE",
        )
        self.assertEqual(acceptance["capture_contract"], "INVALID_CAPTURE_CONTRACT")
        self.assertEqual(acceptance["numeric_floors"], "PASSED")
        self.assertEqual(acceptance["evidence_fit"], "NOT_ACCEPTED")
        self.assertFalse(acceptance["criteria"]["acceptance_allowed"])
        self.assertEqual(
            acceptance["source_runtime_receipt_sha256"],
            hashlib.sha256(RUNTIME_RECEIPT_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            acceptance["timing_recovery_receipt_sha256"],
            hashlib.sha256(TIMING_RECOVERY_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            acceptance["timing_evidence"]["horizon_counts"],
            timing["horizon_counts"],
        )
        self.assertEqual(
            acceptance["criteria"]["observed_complete_xy"],
            runtime["campaign"]["complete_xy_count"],
        )
        self.assertEqual(
            acceptance["criteria"]["observed_time_separated"],
            runtime["campaign"]["time_separated_complete_xy_count"],
        )
        self.assertEqual(
            sum(acceptance["provider_observations"]["all_http_status_counts"].values()),
            acceptance["provider_observations"]["provider_requests"],
        )
        self.assertEqual(
            sum(acceptance["provider_observations"]["token_http_status_counts"].values()),
            2,
        )
        self.assertEqual(
            sum(acceptance["provider_observations"]["swap_http_status_counts"].values()),
            48,
        )
        self.assertTrue(acceptance["criteria"]["success_passed"])
        self.assertFalse(acceptance["criteria"]["control_kill_triggered"])
        self.assertEqual(
            acceptance["runtime_scorer_semantics"],
            "NUMERIC_FLOORS_ONLY_NOT_EVIDENCE_FIT_ACCEPTANCE",
        )
        self.assertEqual(
            acceptance["next_boundary"],
            "OWNER_DECISION_NEW_RECAPTURE_CONTRACT_OR_LEAVE_QUOTE_NATIVE_PAUSED",
        )
        self.assertIn("NO_MECHANISM_AUDITION_NOMINATED", acceptance["non_claims"])
        self.assertFalse(acceptance["timing_evidence"]["portal_row_identity"])
        self.assertIn("NO_ALPHA", acceptance["non_claims"])

    def test_task_contract_does_not_treat_runtime_scorer_token_as_audition_trigger(self) -> None:
        text = (
            ROOT / "docs/tasks/QUOTE_NATIVE_EVIDENCE_CHANNEL_QUALIFICATION_V1.md"
        ).read_text(encoding="utf-8")
        self.assertIn("numeric-only and does not nominate", text)
        self.assertNotIn(
            "only `QUOTE_NATIVE_EVIDENCE_FIT_PASS` may nominate",
            text,
        )

    def test_canonical_runtime_receipt_has_no_unallowlisted_response_header_fields(self) -> None:
        runtime = json.loads(RUNTIME_RECEIPT_PATH.read_text(encoding="utf-8"))

        def walk(value: object) -> None:
            if isinstance(value, dict):
                self.assertNotIn("content_type", value)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(runtime)


if __name__ == "__main__":
    unittest.main()
