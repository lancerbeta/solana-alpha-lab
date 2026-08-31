from __future__ import annotations

import inspect
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_primitives import (
    HTTP_CLASS_401,
    HTTP_CLASS_403,
    HTTP_CLASS_429,
    HTTP_CLASS_5XX,
    HTTP_CLASS_OK,
    HTTP_CLASS_TIMEOUT,
    HTTP_CLASS_TRANSPORT,
    execute_primitive,
)
from solana_alpha_lab.factory.observation_schedule_runtime import (
    JupiterReadonlyOpener,
    PROVEN_READONLY_USER_AGENT,
    _NoRedirectHandler,
)
from solana_alpha_lab.factory.pathrisk_calibration import load_policy
from solana_alpha_lab.factory.pathrisk_live import run_transport_probe_recent
from solana_alpha_lab.quote_native_evidence_channel_qualification import (
    USER_AGENT,
    perform_credentialed_get,
)

FIXTURE_KEY = "TEST_KEY_NOT_A_SECRET"
RECENT = "https://api.jup.ag/tokens/v2/recent"
RUNTIME = (
    ROOT
    / "src"
    / "solana_alpha_lab"
    / "factory"
    / "observation_schedule_runtime.py"
)


def _clock():
    from datetime import UTC, datetime

    return datetime(2026, 9, 1, 0, 10, tzinfo=UTC)


def _headers(request: urllib.request.Request) -> dict[str, str]:
    return {key.lower(): value for key, value in request.header_items()}


def _ok_response(body: bytes = b'[{"id":"MintA"}]') -> MagicMock:
    response = MagicMock()
    response.status = 200
    response.read.return_value = body
    response.__enter__.return_value = response
    response.__exit__.return_value = None
    return response


def _capture_open(opener: JupiterReadonlyOpener, *, response: object | None = None, error: BaseException | None = None):
    captured: dict[str, object] = {"calls": 0, "request": None}

    def _open(request, data=None, timeout=None):  # noqa: ARG001
        captured["calls"] = int(captured["calls"]) + 1
        captured["request"] = request
        captured["timeout"] = timeout
        if error is not None:
            raise error
        return response if response is not None else _ok_response()

    return patch.object(opener._http, "open", side_effect=_open), captured


def _primitive(opener: object) -> dict:
    return execute_primitive(
        primitive_id="PRIM-JUPITER-TOKENS-V2-RECENT-001",
        primitive_version="1.0",
        method="GET",
        url=RECENT,
        opener=opener,
        clock=_clock,
    )


class JupiterReadonlyTransportParityTests(unittest.TestCase):
    def test_t1_explicit_proven_user_agent(self) -> None:
        self.assertEqual(PROVEN_READONLY_USER_AGENT, USER_AGENT)
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        hooked, captured = _capture_open(opener)
        with hooked:
            opener.open(RECENT)
        headers = _headers(captured["request"])  # type: ignore[arg-type]
        self.assertEqual(headers["user-agent"], USER_AGENT)
        request = captured["request"]
        assert isinstance(request, urllib.request.Request)
        self.assertEqual(request.get_method(), "GET")

    def test_t1_captured_request_matches_perform_credentialed_get(self) -> None:
        legacy: dict[str, object] = {}

        class _LegacyDirector:
            def open(self, request, data=None, timeout=None):  # noqa: ARG001
                legacy["request"] = request
                return _ok_response()

        perform_credentialed_get(
            RECENT,
            api_key=FIXTURE_KEY,
            limits={"timeout_seconds": 20.0, "max_response_bytes": 2_000_000},
            opener=_LegacyDirector(),
        )
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        hooked, captured = _capture_open(opener)
        with hooked:
            opener.open(RECENT)
        proven = captured["request"]
        sent = legacy["request"]
        assert isinstance(proven, urllib.request.Request)
        assert isinstance(sent, urllib.request.Request)
        self.assertEqual(proven.get_method(), sent.get_method())
        self.assertEqual(_headers(proven), _headers(sent))

    def test_t2_accept_remains_application_json(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        hooked, captured = _capture_open(opener)
        with hooked:
            opener.open(RECENT)
        headers = _headers(captured["request"])  # type: ignore[arg-type]
        self.assertEqual(headers["accept"], "application/json")

    def test_t3_x_api_key_header_only(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        hooked, captured = _capture_open(opener)
        with hooked:
            opener.open(RECENT)
        request = captured["request"]
        assert isinstance(request, urllib.request.Request)
        headers = _headers(request)
        self.assertEqual(headers["x-api-key"], FIXTURE_KEY)
        self.assertNotIn(FIXTURE_KEY, request.full_url)
        self.assertNotIn("api-key=", request.full_url.lower())

    def test_t4_credential_absent_from_url_log_result(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        hooked, captured = _capture_open(opener)
        with hooked:
            result = opener.open(RECENT)
        dumped = json.dumps(result, sort_keys=True)
        self.assertNotIn(FIXTURE_KEY, dumped)
        self.assertFalse(result["url_has_api_key"])
        request = captured["request"]
        assert isinstance(request, urllib.request.Request)
        self.assertNotIn(FIXTURE_KEY, request.full_url)

    def test_t5_explicit_no_redirect_opener(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        redirect = [
            handler
            for handler in opener._http.handlers
            if isinstance(handler, urllib.request.HTTPRedirectHandler)
        ]
        self.assertEqual(len(redirect), 1)
        self.assertIs(type(redirect[0]), _NoRedirectHandler)
        self.assertIsNone(
            redirect[0].redirect_request(
                None,
                None,
                302,
                "found",
                {},
                "https://example.invalid",
            )
        )
        self.assertNotIn("urlopen", inspect.getsource(JupiterReadonlyOpener))
        self.assertNotIn("urlopen", inspect.getsource(JupiterReadonlyOpener.open))

    def test_t6_200_json_decoded(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        hooked, _captured = _capture_open(
            opener, response=_ok_response(b'[{"id":"MintA"},{"id":"MintB"}]')
        )
        with hooked:
            result = opener.open(RECENT)
            primitive = _primitive(opener)
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["body"], [{"id": "MintA"}, {"id": "MintB"}])
        self.assertEqual(primitive["http_class"], HTTP_CLASS_OK)
        self.assertEqual(primitive["http_status"], 200)

    def test_t7_401_class_status_preserved(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        hooked, _captured = _capture_open(
            opener, error=HTTPError(RECENT, 401, "unauthorized", hdrs={}, fp=None)
        )
        with hooked:
            opened = opener.open(RECENT)
            result = _primitive(opener)
        self.assertEqual(opened["http_status"], 401)
        self.assertIsNone(opened["body"])
        self.assertEqual(result["http_status"], 401)
        self.assertEqual(result["http_class"], HTTP_CLASS_401)

    def test_t8_403_class_status_preserved(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        hooked, _captured = _capture_open(
            opener, error=HTTPError(RECENT, 403, "forbidden", hdrs={}, fp=None)
        )
        with hooked:
            opened = opener.open(RECENT)
            result = _primitive(opener)
        self.assertEqual(opened["http_status"], 403)
        self.assertIsNone(opened["body"])
        self.assertEqual(result["http_status"], 403)
        self.assertEqual(result["http_class"], HTTP_CLASS_403)

    def test_t9_429_class_status_preserved(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        hooked, _captured = _capture_open(
            opener, error=HTTPError(RECENT, 429, "limited", hdrs={}, fp=None)
        )
        with hooked:
            result = _primitive(opener)
        self.assertEqual(result["http_status"], 429)
        self.assertEqual(result["http_class"], HTTP_CLASS_429)

    def test_t10_5xx_preserved(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        hooked, _captured = _capture_open(
            opener, error=HTTPError(RECENT, 503, "unavailable", hdrs={}, fp=None)
        )
        with hooked:
            result = _primitive(opener)
        self.assertEqual(result["http_status"], 503)
        self.assertEqual(result["http_class"], HTTP_CLASS_5XX)

    def test_t11_timeout_remains_timeout(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        hooked, _captured = _capture_open(
            opener, error=URLError(TimeoutError("timed out"))
        )
        with hooked:
            result = _primitive(opener)
        self.assertEqual(result["http_class"], HTTP_CLASS_TIMEOUT)
        self.assertIsNone(result["http_status"])

    def test_t12_transport_failure_remains_transport_error(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        hooked, _captured = _capture_open(opener, error=URLError("dns"))
        with hooked:
            result = _primitive(opener)
        self.assertEqual(result["http_class"], HTTP_CLASS_TRANSPORT)
        self.assertIsNone(result["http_status"])

    def test_t13_no_retry(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        hooked, captured = _capture_open(
            opener, error=HTTPError(RECENT, 403, "forbidden", hdrs={}, fp=None)
        )
        with hooked:
            opener.open(RECENT)
        self.assertEqual(captured["calls"], 1)
        source = inspect.getsource(JupiterReadonlyOpener.open)
        self.assertNotIn("retry", source.casefold())
        self.assertNotIn("for _ in", source)

    def test_t14_no_fallback(self) -> None:
        source = inspect.getsource(JupiterReadonlyOpener.open)
        self.assertNotIn("fallback", source.casefold())
        policy = load_policy(ROOT)
        self.assertFalse(policy["runtime_limits"]["fallback"])

    def test_t15_transport_probe_recent_max_one_call(self) -> None:
        class _Once:
            def __init__(self) -> None:
                self.opens = 0

            def open(self, url: str) -> dict:
                self.opens += 1
                return {"http_status": 200, "body": []}

        opener = _Once()
        payload = run_transport_probe_recent(opener=opener)
        self.assertEqual(payload["provider_calls"], 1)
        self.assertEqual(opener.opens, 1)
        self.assertFalse(payload["retry"])
        self.assertFalse(payload["fallback"])
        self.assertFalse(payload["scientific_window_started"])

    def test_t16_pathrisk_science_semantics_unchanged(self) -> None:
        policy = load_policy(ROOT)
        self.assertEqual(policy["sample"]["floor"], 4)
        self.assertEqual(policy["notionals_lamports"], ["1000000", "10000000"])
        self.assertEqual(policy["horizons"]["h900_offset_seconds"], 900)
        self.assertEqual(policy["population"]["liquidity_usd_min"], "1000")
        self.assertEqual(policy["runtime_limits"]["max_calls"], 26)
        self.assertFalse(policy["runtime_limits"]["retry"])
        self.assertFalse(policy["runtime_limits"]["fallback"])
        self.assertEqual(policy["external_authority"]["credential_name"], "JUPITER_API_KEY")
        self.assertFalse(policy["external_authority"]["capture_authorized"])
        self.assertNotIn("ACT-PATHRISK-LIVE-001", inspect.getsource(JupiterReadonlyOpener))

    def test_t17_old_activation_untouched(self) -> None:
        text = RUNTIME.read_text(encoding="utf-8")
        self.assertNotIn("ACT-PATHRISK-LIVE-001", text)
        self.assertNotIn("evidence_epoch", inspect.getsource(JupiterReadonlyOpener))

    def test_t18_provider_calls_this_pr_zero(self) -> None:
        self.assertNotIn("urlopen", inspect.getsource(JupiterReadonlyOpener))
        self.assertNotIn("urlopen", RUNTIME.read_text(encoding="utf-8"))

    def test_t19_real_credential_reads_this_pr_zero(self) -> None:
        source = inspect.getsource(JupiterReadonlyOpener)
        self.assertNotIn("os.environ", source)
        self.assertNotIn("load_process_credential", source)
        self.assertNotIn("getenv", source)

    def test_t20_secret_leak_tests_pass(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        hooked, captured = _capture_open(opener)
        with hooked:
            result = opener.open(RECENT)
        request = captured["request"]
        assert isinstance(request, urllib.request.Request)
        blob = json.dumps({"result": result, "url": request.full_url}, sort_keys=True)
        self.assertNotIn(FIXTURE_KEY, blob)
        self.assertNotIn(FIXTURE_KEY, json.dumps(result))


if __name__ == "__main__":
    unittest.main()
