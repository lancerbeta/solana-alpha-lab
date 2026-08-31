from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import os

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

from pathrisk_live_testkit import (
    ensure_act002_below_floor,
    live_identity_kwargs,
    successor_phrase,
)
from solana_alpha_lab.factory.observation_primitives import (
    HTTP_CLASS_401,
    HTTP_CLASS_403,
    HTTP_CLASS_429,
    HTTP_CLASS_5XX,
    HTTP_CLASS_NO_RESPONSE,
    HTTP_CLASS_OK,
    HTTP_CLASS_OTHER_4XX,
    HTTP_CLASS_TIMEOUT,
    HTTP_CLASS_TRANSPORT,
    classify_http_transport,
    execute_primitive,
)
from solana_alpha_lab.factory.observation_schedule_runtime import JupiterReadonlyOpener
from solana_alpha_lab.factory.pathrisk_calibration import (
    TERMINAL_INFORMATIVE,
    load_policy,
)
from solana_alpha_lab.factory.pathrisk_live import (
    ControllableClock,
    FixtureWindowOpener,
    PathRiskLiveError,
    UNKNOWN_NOT_RECORDED_AT_TIME,
    _http_fields,
    r0_recent_operational_terminal,
    run_live_window,
    run_transport_probe_recent,
    transport_probe_owner_phrase,
)

GIT_SHA = "c" * 40
MAIN_SHA = "b" * 40
NOW = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)
RECENT = "https://api.jup.ag/tokens/v2/recent"
MINTS = (
    "MintA111111111111111111111111111111111111111",
    "MintB111111111111111111111111111111111111111",
    "MintC111111111111111111111111111111111111111",
    "MintD111111111111111111111111111111111111111",
)


def _clock() -> datetime:
    return NOW


def _phrase() -> str:
    return successor_phrase()


def _probe_phrase() -> str:
    return transport_probe_owner_phrase(load_policy(ROOT))


def _row(mint: str) -> dict:
    return {
        "id": mint,
        "liquidity": "2000",
        "firstPool": {"createdAt": "2026-09-01T00:05:00Z", "source": "pump.fun"},
        "first_seen_at": "2026-09-01T00:05:00Z",
    }


def _happy_fixture() -> dict:
    return {
        "recent": [{"id": mint} for mint in MINTS],
        "search": [_row(mint) for mint in MINTS],
    }


class _StatusOpener:
    def __init__(self, result: object) -> None:
        self.urls: list[str] = []
        self.result = result
        self.opens = 0

    def open(self, url: str) -> object:
        self.urls.append(url)
        self.opens += 1
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def _primitive(opener: object) -> dict:
    return execute_primitive(
        primitive_id="PRIM-JUPITER-TOKENS-V2-RECENT-001",
        primitive_version="1.0",
        method="GET",
        url=RECENT,
        opener=opener,
        clock=_clock,
    )


def _run_window(*, data_root: Path, opener: object) -> dict:
    ensure_act002_below_floor(data_root)
    return run_live_window(
        root=ROOT,
        data_root=data_root,
        opener=opener,
        producer_git_sha=GIT_SHA,
        owner_phrase=_phrase(),
        main_sha=MAIN_SHA,
        clock=ControllableClock(NOW),
        store_path=data_root / "observation_schedule_state.sqlite",
        production=False,
        **live_identity_kwargs(),
    )


class PathRiskRecentHttpClassTests(unittest.TestCase):
    def test_t1_http_200_is_ok(self) -> None:
        result = _primitive(
            _StatusOpener({"http_status": 200, "body": [{"id": "MintA"}]})
        )
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["http_class"], HTTP_CLASS_OK)
        self.assertEqual(classify_http_transport(http_status=200), (200, HTTP_CLASS_OK))

    def test_t2_http_401_persists_exact_status(self) -> None:
        result = _primitive(_StatusOpener({"http_status": 401, "body": None}))
        self.assertEqual(result["status"], "MISSING_TYPED")
        self.assertEqual(result["missing_reason"], "HTTP_ERROR")
        self.assertEqual(result["http_status"], 401)
        self.assertEqual(result["http_class"], HTTP_CLASS_401)

    def test_t3_http_403_persists_class(self) -> None:
        result = _primitive(_StatusOpener({"http_status": 403, "body": None}))
        self.assertEqual(result["http_status"], 403)
        self.assertEqual(result["http_class"], HTTP_CLASS_403)

    def test_t4_http_429_persists_class(self) -> None:
        result = _primitive(_StatusOpener({"http_status": 429, "body": None}))
        self.assertEqual(result["http_status"], 429)
        self.assertEqual(result["http_class"], HTTP_CLASS_429)

    def test_t5_http_500_is_5xx(self) -> None:
        result = _primitive(_StatusOpener({"http_status": 500, "body": None}))
        self.assertEqual(result["http_status"], 500)
        self.assertEqual(result["http_class"], HTTP_CLASS_5XX)

    def test_t6_other_4xx(self) -> None:
        result = _primitive(_StatusOpener({"http_status": 418, "body": None}))
        self.assertEqual(result["http_status"], 418)
        self.assertEqual(result["http_class"], HTTP_CLASS_OTHER_4XX)

    def test_t7_timeout_has_null_status(self) -> None:
        result = _primitive(_StatusOpener(TimeoutError("slow")))
        self.assertIsNone(result["http_status"])
        self.assertEqual(result["http_class"], HTTP_CLASS_TIMEOUT)
        self.assertEqual(result["missing_reason"], "TIMEOUT")

    def test_t8_oserror_is_transport_error(self) -> None:
        result = _primitive(_StatusOpener(OSError("down")))
        self.assertIsNone(result["http_status"])
        self.assertEqual(result["http_class"], HTTP_CLASS_TRANSPORT)

    def test_t9_completed_reuse_does_not_reopen(self) -> None:
        opener = _StatusOpener({"http_status": 401, "body": None})
        with tempfile.TemporaryDirectory() as raw:
            data_root = Path(raw)
            first = _run_window(data_root=data_root, opener=opener)
            self.assertEqual(first["terminal"], "R0_RECENT_HTTP_401_UNAUTHORIZED")
            self.assertEqual(opener.opens, 1)
            second = _run_window(data_root=data_root, opener=opener)
        self.assertEqual(second["terminal"], "R0_RECENT_HTTP_401_UNAUTHORIZED")
        self.assertEqual(second["http_status"], 401)
        self.assertEqual(second["http_class"], HTTP_CLASS_401)
        self.assertEqual(opener.opens, 1)

    def test_t10_r0_401_is_not_generic_binding(self) -> None:
        opener = _StatusOpener({"http_status": 401, "body": None})
        with tempfile.TemporaryDirectory() as raw:
            result = _run_window(data_root=Path(raw), opener=opener)
        self.assertEqual(result["terminal"], "R0_RECENT_HTTP_401_UNAUTHORIZED")
        self.assertNotEqual(result["terminal"], "R0_SINGLE_SNAPSHOT_BINDING_NOT_PROVEN")

    def test_t11_http_200_empty_rows_stay_binding(self) -> None:
        opener = _StatusOpener({"http_status": 200, "body": []})
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaisesRegex(
                PathRiskLiveError, "R0_SINGLE_SNAPSHOT_BINDING_NOT_PROVEN"
            ):
                _run_window(data_root=Path(raw), opener=opener)

    def test_t12_probe_one_fake_open(self) -> None:
        opener = _StatusOpener({"http_status": 200, "body": [{"id": "MintA"}]})
        payload = run_transport_probe_recent(opener=opener, clock=_clock)
        self.assertEqual(opener.opens, 1)
        self.assertEqual(payload["provider_calls"], 1)
        self.assertEqual(payload["http_class"], HTTP_CLASS_OK)

    def test_t13_probe_cannot_call_search_or_order(self) -> None:
        opener = _StatusOpener({"http_status": 200, "body": []})
        run_transport_probe_recent(opener=opener, clock=_clock)
        self.assertEqual(opener.urls, [RECENT])
        joined = " ".join(opener.urls)
        self.assertNotIn("/tokens/v2/search", joined)
        self.assertNotIn("/swap/v2/order", joined)

    def test_t14_probe_creates_no_activation(self) -> None:
        opener = _StatusOpener({"http_status": 200, "body": []})
        with tempfile.TemporaryDirectory() as raw:
            data_root = Path(raw)
            payload = run_transport_probe_recent(opener=opener, clock=_clock)
            self.assertFalse((data_root / "pathrisk_live").exists())
        self.assertIsNone(payload["activation_id"])
        self.assertFalse(payload["scientific_window_started"])

    def test_t15_probe_does_not_mutate_rdp(self) -> None:
        marker = {"before": True}
        with tempfile.TemporaryDirectory() as raw:
            data_root = Path(raw)
            target = data_root / "datasets" / "manifests" / "keep.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(marker), encoding="utf-8")
            before = target.read_bytes()
            run_transport_probe_recent(
                opener=_StatusOpener({"http_status": 200, "body": []}),
                clock=_clock,
            )
            self.assertEqual(target.read_bytes(), before)
        self.assertEqual(
            run_transport_probe_recent(
                opener=_StatusOpener({"http_status": 200, "body": []}),
                clock=_clock,
            )["rdp_mutation"],
            0,
        )

    def test_t16_credential_absent_from_probe_output(self) -> None:
        env = os.environ.copy()
        env["JUPITER_API_KEY"] = "not-a-real-key"
        fixture = {"recent": [{"id": "MintA"}]}
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "fixture.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts" / "early_quote_surface_pathrisk_calibration.py"),
                    "transport-probe-recent",
                    "--owner-phrase",
                    _probe_phrase(),
                    "--fake-provider-fixture",
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
        blob = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 0, blob)
        self.assertNotIn("not-a-real-key", blob)
        payload = json.loads(completed.stdout)
        self.assertNotIn("not-a-real-key", json.dumps(payload))

    def test_t17_probe_has_no_retry(self) -> None:
        opener = _StatusOpener({"http_status": 500, "body": None})
        payload = run_transport_probe_recent(opener=opener, clock=_clock)
        self.assertEqual(opener.opens, 1)
        self.assertFalse(payload["retry"])
        self.assertFalse(payload["fallback"])
        self.assertEqual(payload["http_class"], HTTP_CLASS_5XX)

    def test_t18_science_terminal_unchanged_on_happy_path(self) -> None:
        opener = FixtureWindowOpener(_happy_fixture())
        with tempfile.TemporaryDirectory() as raw:
            result = _run_window(data_root=Path(raw), opener=opener)
        self.assertEqual(result["terminal"], TERMINAL_INFORMATIVE)

    def test_probe_print_phrase_is_not_calibration_phrase(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts" / "early_quote_surface_pathrisk_calibration.py"),
                "transport-probe-recent",
                "--print-phrase",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), _probe_phrase())
        self.assertNotEqual(completed.stdout.strip(), _phrase())

    def test_probe_rejects_calibration_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "fixture.json"
            path.write_text(json.dumps({"recent": []}), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts" / "early_quote_surface_pathrisk_calibration.py"),
                    "transport-probe-recent",
                    "--owner-phrase",
                    _phrase(),
                    "--fake-provider-fixture",
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("OWNER_PHRASE_MISMATCH", completed.stderr + completed.stdout)

    def test_opener_httperror_keeps_status_without_body(self) -> None:
        error = HTTPError(RECENT, 401, "unauthorized", hdrs={}, fp=None)
        opener = JupiterReadonlyOpener("TEST_KEY_NOT_A_SECRET")
        with patch.object(opener._http, "open", side_effect=error):
            result = opener.open(RECENT)
        self.assertEqual(result["http_status"], 401)
        self.assertIsNone(result["body"])

    def test_opener_urlerror_is_oserror(self) -> None:
        opener = JupiterReadonlyOpener("TEST_KEY_NOT_A_SECRET")
        with patch.object(opener._http, "open", side_effect=URLError("dns")):
            with self.assertRaises(OSError):
                opener.open(RECENT)

    def test_historical_payload_stays_unknown(self) -> None:
        payload = {
            "status": "MISSING_TYPED",
            "missing_reason": "HTTP_ERROR",
            "body": None,
            "rows": [],
        }
        fields = _http_fields(payload)
        self.assertEqual(fields["http_class"], UNKNOWN_NOT_RECORDED_AT_TIME)
        self.assertIsNone(r0_recent_operational_terminal(payload))

    def test_urlerror_timeout_is_timeout_class(self) -> None:
        opener = JupiterReadonlyOpener("TEST_KEY_NOT_A_SECRET")
        with patch.object(
            opener._http,
            "open",
            side_effect=URLError(TimeoutError("timed out")),
        ):
            result = _primitive(opener)
        self.assertEqual(result["http_class"], HTTP_CLASS_TIMEOUT)
        self.assertIsNone(result["http_status"])

    def test_r0_429_is_operational_terminal(self) -> None:
        opener = _StatusOpener({"http_status": 429, "body": None})
        with tempfile.TemporaryDirectory() as raw:
            result = _run_window(data_root=Path(raw), opener=opener)
        self.assertEqual(result["terminal"], "R0_RECENT_HTTP_429_RATE_LIMITED")

    def test_no_http_response_class(self) -> None:
        result = _primitive(_StatusOpener({"body": [{"id": "MintA"}]}))
        self.assertEqual(result["http_class"], HTTP_CLASS_NO_RESPONSE)


if __name__ == "__main__":
    unittest.main()
