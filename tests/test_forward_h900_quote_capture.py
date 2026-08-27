from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
import sys

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from solana_alpha_lab.factory.capabilities import (  # noqa: E402
    CAP_JUPITER_FREE_KEY_FORWARD_H900_QUOTE_CAPTURE,
    CAPABILITY_ROUTER,
    capture_forward_h900_quote,
    capture_quote_native_free_key,
)
from solana_alpha_lab.factory.forward_h900_quote_capture import (  # noqa: E402
    AUTHORITY_PHRASE,
    CALL_CAP,
    CAPABILITY_ID,
    FACTORY_RUNNER,
    FACTORY_RUNNER_SHA256,
    ForwardCaptureError,
    complete_marker,
    credential_free_capture_preflight,
    freeze_contract,
    planned_calls,
    run_forward_capture,
    validate_policy,
    load_policy,
)
from solana_alpha_lab.factory.forward_mix_offline import (  # noqa: E402
    CLOSE_TERMINAL,
    score_frozen_mix_dataset,
)
from scripts.run_forward_h900_quote_capture import main as capture_cli  # noqa: E402

TEST_FREE_KEY = "test-free-key-not-a-secret"
GIT_SHA = "a" * 40
CREATED_AT = "2026-08-27T11:54:00Z"
SNAPSHOT = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


class _Response:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = io.BytesIO(body)
        self._status = status
        self.headers = {"Content-Type": "application/json"}

    def getcode(self) -> int:
        return self._status

    def read(self, n: int = -1) -> bytes:
        return self._body.read(n)

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _Clock:
    def __init__(self) -> None:
        self.current = SNAPSHOT
        self.sleeps: list[float] = []
        self.mono = 0.0

    def now(self) -> datetime:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += timedelta(seconds=seconds)
        self.mono += seconds

    def monotonic(self) -> float:
        return self.mono


class _Opener:
    def __init__(
        self,
        rows: list[dict[str, Any]],
        *,
        crash_after: int | None = None,
        quote_transaction: bool = False,
        leak_secret: bool = False,
    ) -> None:
        self.rows = rows
        self.crash_after = crash_after
        self.quote_transaction = quote_transaction
        self.leak_secret = leak_secret
        self.urls: list[str] = []

    def open(self, request: object, timeout: float = 0) -> _Response:
        del timeout
        url = str(getattr(request, "full_url"))
        if self.crash_after is not None and len(self.urls) >= self.crash_after:
            raise RuntimeError("injected crash")
        self.urls.append(url)
        if TEST_FREE_KEY in url:
            raise AssertionError("secret in URL")
        if "/tokens/v2/recent" in url:
            payload: object = list(self.rows)
            if self.leak_secret:
                payload = [{"id": "leak", "note": TEST_FREE_KEY}]
            return _Response(json.dumps(payload).encode("utf-8"))
        if "/tokens/v2/search" in url:
            return _Response(json.dumps(self.rows).encode("utf-8"))
        if "/swap/v2/order" in url:
            query = url.split("?", 1)[1]
            values = dict(item.split("=", 1) for item in query.split("&"))
            body = {
                "transaction": "deadbeef" if self.quote_transaction else None,
                "requestId": "q",
                "inputMint": values["inputMint"],
                "outputMint": values["outputMint"],
                "inAmount": values["amount"],
                "outAmount": "11000000"
                if values["inputMint"] == "So11111111111111111111111111111111111111112"
                else "10500000",
                "router": "dflow",
                "mode": "manual",
            }
            return _Response(json.dumps(body).encode("utf-8"))
        raise AssertionError(f"unexpected URL: {url}")


def _stub_preflight(*_args: object, **_kwargs: object) -> dict[str, object]:
    return {"credential_reads": 0, "provider_requests": 0, "dns_resolved": True}


def _row(
    index: int,
    *,
    created_at: str = CREATED_AT,
    stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item = {
        "id": f"mint-{index:02d}",
        "launchpad": "pump.fun",
        "liquidity": 2500.0,
        "mcap": 12000.0,
        "firstPool": {"createdAt": created_at},
        "stats5m": stats if stats is not None else {"buyVolume": 10.0 + index, "sellVolume": 5.0},
    }
    return item


def _freeze(data_root: Path) -> None:
    freeze_contract(repo_root=ROOT, data_root=data_root, git_sha=GIT_SHA)


def _run(
    data_root: Path,
    opener: _Opener,
    clock: _Clock,
    *,
    phrase: str = AUTHORITY_PHRASE,
) -> dict[str, Any]:
    return run_forward_capture(
        repo_root=ROOT,
        data_root=data_root,
        authority_phrase=phrase,
        credential_loader=lambda: TEST_FREE_KEY,
        opener=opener,
        clock=clock.now,
        sleeper=clock.sleep,
        monotonic_clock=clock.monotonic,
        preflight_fn=_stub_preflight,
    )


class ForwardH900QuoteCaptureTests(unittest.TestCase):
    def test_policy_pins_call_cap_pace_retries_and_runner_hash(self) -> None:
        policy = load_policy(ROOT)
        validate_policy(policy, repo_root=ROOT)
        self.assertEqual(planned_calls(29), CALL_CAP)
        self.assertEqual(planned_calls(9), 2)
        self.assertLessEqual(planned_calls(29), 60)
        runner = ROOT / FACTORY_RUNNER
        self.assertEqual(hashlib.sha256(runner.read_bytes()).hexdigest(), FACTORY_RUNNER_SHA256)
        capture_src = (ROOT / "src/solana_alpha_lab/factory/forward_h900_quote_capture.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("classify_r0_mix", capture_src)
        preflight = credential_free_capture_preflight(ROOT, preflight_fn=_stub_preflight)
        self.assertEqual(preflight["planned_calls_max"], 60)
        self.assertEqual(preflight["min_interval_seconds"], 3)
        self.assertEqual(preflight["retries"], 0)
        self.assertIs(preflight["fallback"], False)
        self.assertEqual(preflight["provider_requests"], 0)

    def test_wrong_phrase_makes_zero_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _freeze(data_root)
            opener = _Opener([_row(i) for i in range(10)])
            clock = _Clock()
            with self.assertRaises(ForwardCaptureError) as raised:
                _run(data_root, opener, clock, phrase="not-the-phrase")
            self.assertEqual(str(raised.exception), "AUTHORITY_PHRASE_INVALID")
            self.assertEqual(raised.exception.provider_requests, 0)
            self.assertEqual(opener.urls, [])

    def test_stop_before_quotes_when_eligible_below_ten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _freeze(data_root)
            opener = _Opener([_row(i) for i in range(9)])
            clock = _Clock()
            receipt = _run(data_root, opener, clock)
            self.assertEqual(receipt["terminal_outcome"], "STOP_BEFORE_QUOTES_ELIGIBLE_BELOW_FLOOR")
            self.assertTrue(receipt["window_complete"])
            self.assertEqual(receipt["provider_requests"], 2)
            self.assertEqual(receipt["quotes_attempted"], 0)
            self.assertEqual(receipt["wallet_signer_transaction_actions"], 0)
            self.assertEqual(receipt["execute_calls"], 0)
            self.assertEqual(receipt["build_calls"], 0)
            self.assertFalse(any("/swap/v2/order" in url for url in opener.urls))
            self.assertEqual(sum(1 for url in opener.urls if "/tokens/v2/search" in url), 1)
            pace = [sleep for sleep in clock.sleeps if abs(sleep - 3) < 1e-9]
            self.assertGreaterEqual(len(pace), 1)

    def test_missing_freeze_makes_zero_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            opener = _Opener([_row(i) for i in range(10)])
            with self.assertRaises(ForwardCaptureError) as raised:
                _run(Path(tmp), opener, _Clock())
            self.assertEqual(str(raised.exception), "FROZEN_CONTRACT_MISSING")
            self.assertEqual(opener.urls, [])

    def test_absolute_h900_is_create_at_plus_900_not_buy_plus_900(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _freeze(data_root)
            created = [
                "2026-08-27T11:50:10Z",
                "2026-08-27T11:52:30Z",
                "2026-08-27T11:55:00Z",
            ]
            opener = _Opener([_row(i, created_at=created[i % 3]) for i in range(10)])
            clock = _Clock()
            receipt = _run(data_root, opener, clock)
            self.assertEqual(receipt["terminal_outcome"], "CAPTURE_COMPLETE")
            self.assertLessEqual(receipt["provider_requests"], 60)
            self.assertEqual(receipt["provider_requests"], 22)
            self.assertEqual(receipt["r1_search_calls"], 0)
            self.assertEqual(sum(1 for url in opener.urls if "/tokens/v2/search" in url), 1)
            sol = "So11111111111111111111111111111111111111112"
            swap = [url for url in opener.urls if "/swap/v2/order" in url]
            buy_idx = [index for index, url in enumerate(swap) if f"inputMint={sol}" in url]
            sell_idx = [index for index, url in enumerate(swap) if f"outputMint={sol}" in url]
            self.assertEqual(len(buy_idx), 10)
            self.assertEqual(len(sell_idx), 10)
            self.assertLess(max(buy_idx), min(sell_idx))
            due = sorted({row["h900_due_at"] for row in receipt["rows"]})
            self.assertEqual(
                due,
                [
                    "2026-08-27T12:05:10Z",
                    "2026-08-27T12:07:30Z",
                    "2026-08-27T12:10:00Z",
                ],
            )
            horizon = [sleep for sleep in clock.sleeps if sleep > 60]
            self.assertGreaterEqual(len(horizon), 1)
            self.assertLess(min(horizon), 400)
            self.assertTrue(all(sleep < 500 for sleep in horizon))
            frozen = json.loads((data_root / "forward_h900_quote_capture" / "frozen" / "CURRENT.json").read_text(encoding="utf-8"))
            self.assertEqual(frozen["hypothesis"]["hypothesis_version_id"], "HYP-EARLY-TAKER-VOLUME-MIX-H900-V1")
            self.assertEqual(frozen["primary_x"], "R0_TAKER_VOLUME_MIX")
            self.assertEqual(frozen["stop_rules"]["second_window"], "FORBIDDEN")
            self.assertNotIn(TEST_FREE_KEY, json.dumps(receipt, default=str))
            raw_root = next((data_root / "forward_h900_quote_capture").rglob("*.body"))
            self.assertIn("forward_h900_quote_capture", str(raw_root))

    def test_crash_resume_does_not_repeat_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _freeze(data_root)
            crash = _Opener([_row(i) for i in range(10)], crash_after=2)
            clock = _Clock()
            with self.assertRaises(RuntimeError):
                _run(data_root, crash, clock)
            self.assertEqual(len(crash.urls), 2)
            resume = _Opener([_row(i) for i in range(10)])
            receipt = _run(data_root, resume, clock)
            self.assertEqual(receipt["terminal_outcome"], "CAPTURE_COMPLETE")
            self.assertFalse(any("/tokens/v2/recent" in url for url in resume.urls))
            self.assertFalse(any("/tokens/v2/search" in url for url in resume.urls))
            self.assertTrue(all("/swap/v2/order" in url for url in resume.urls))
            self.assertEqual(receipt["provider_requests"], 22)
            journal = json.loads(
                next((data_root / "forward_h900_quote_capture").rglob("journal.json")).read_text(encoding="utf-8")
            )
            self.assertIn("last_call_at", journal)

    def test_complete_window_is_idempotent_and_forbids_second_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _freeze(data_root)
            opener = _Opener([_row(i) for i in range(10)])
            clock = _Clock()
            first = _run(data_root, opener, clock)
            complete_bytes = complete_marker(data_root).read_bytes()
            deny = _Opener([_row(i) for i in range(10)])
            second = _run(data_root, deny, clock)
            self.assertEqual(second["resume"], "IDEMPOTENT_COMPLETE")
            self.assertEqual(second["second_window"], "FORBIDDEN")
            self.assertEqual(second["provider_requests_new"], 0)
            self.assertEqual(deny.urls, [])
            self.assertEqual(complete_marker(data_root).read_bytes(), complete_bytes)
            self.assertEqual(first["terminal_outcome"], "CAPTURE_COMPLETE")

    def test_secret_in_body_and_quote_transaction_are_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _freeze(data_root)
            leak = _Opener([_row(i) for i in range(10)], leak_secret=True)
            with self.assertRaises(ForwardCaptureError) as leaked:
                _run(data_root, leak, _Clock())
            self.assertEqual(str(leaked.exception), "RAW_BODY_CONTAINS_CREDENTIAL")
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _freeze(data_root)
            quoted = _Opener([_row(i) for i in range(10)], quote_transaction=True)
            with self.assertRaises(ForwardCaptureError) as raised:
                _run(data_root, quoted, _Clock())
            self.assertEqual(str(raised.exception), "QUOTE_RETURNED_TRANSACTION")

    def test_offline_mix_classifier_does_not_touch_provider(self) -> None:
        rows = [
            {
                "mint": f"mint-{index:02d}",
                "h900_terminal": "QUOTE_OBSERVED",
                "y": 0.1 if index % 2 == 0 else -0.1,
                "search_row": _row(index),
            }
            for index in range(10)
        ]
        scored = score_frozen_mix_dataset(rows)
        self.assertEqual(scored["classifier_context"], "OFFLINE_FROZEN_DATASET_ONLY")
        self.assertIn(scored["terminal"], {CLOSE_TERMINAL, "EARN_ONE_CONFIRMATORY_FRESH_OOS"})
        self.assertIs(scored["quartile"], False)
        self.assertEqual(scored["tau_b_floor"], "forbidden")

    def test_score_cli_does_not_mutate_complete_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _freeze(data_root)
            _run(data_root, _Opener([_row(i) for i in range(10)]), _Clock())
            before = complete_marker(data_root).read_bytes()
            exit_code = capture_cli(["--root", str(ROOT), "--data-root", str(data_root), "score"])
            self.assertEqual(exit_code, 0)
            self.assertEqual(complete_marker(data_root).read_bytes(), before)
            self.assertTrue((data_root / "forward_h900_quote_capture" / "SCORE.json").is_file())

    def test_capability_router_is_not_the_quote_native_allowlist(self) -> None:
        self.assertIs(
            CAPABILITY_ROUTER[CAP_JUPITER_FREE_KEY_FORWARD_H900_QUOTE_CAPTURE],
            capture_forward_h900_quote,
        )
        self.assertIsNot(
            CAPABILITY_ROUTER[CAP_JUPITER_FREE_KEY_FORWARD_H900_QUOTE_CAPTURE],
            capture_quote_native_free_key,
        )
        source = (ROOT / "src/solana_alpha_lab/factory/capabilities.py").read_text(encoding="utf-8")
        allowlist = source.split("if atom_id not in {", 1)[1].split("}", 1)[0]
        self.assertNotIn("FORWARD_H900_QUOTE_CAPTURE_V1", allowlist)
        self.assertEqual(CAPABILITY_ID, "CAP-JUPITER-FREE-KEY-FORWARD-H900-QUOTE-CAPTURE-001")


if __name__ == "__main__":
    unittest.main()
