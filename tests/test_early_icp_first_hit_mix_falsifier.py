from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
import sys

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402
from solana_alpha_lab.factory.capabilities import (  # noqa: E402
    CAP_JUPITER_FREE_KEY_EARLY_ICP_FIRST_HIT_MIX_FALSIFIER,
    CAPABILITY_ROUTER,
    capture_early_icp_first_hit_mix_falsifier,
    capture_forward_h900_quote,
)
from solana_alpha_lab.factory.early_icp_first_hit_mix_falsifier import (  # noqa: E402
    AUTHORITY_PHRASE,
    CALL_CAP,
    CAPABILITY_ID,
    DATASET_MANIFEST_ID,
    DENSITY_CHECK_PERIOD_SECONDS,
    FACTORY_RUNNER,
    FACTORY_RUNNER_SHA256,
    IN_FLIGHT_TERMINAL,
    LABELS_RELATIVE,
    MANIFEST_RELATIVE,
    MAX_DENSITY_CHECKS,
    NOT_QUOTED,
    POLICY_RELATIVE,
    PUBLISHED_RELATIVE,
    QUOTE_CALL_RESERVE,
    SLEEP_TERMINAL,
    FirstHitError,
    credential_free_first_hit_preflight,
    load_policy,
    quote_capacity,
    run_first_hit_mix_falsifier,
    validate_policy,
    v2_complete_path,
)
from solana_alpha_lab.factory.forward_h900_quote_capture import (  # noqa: E402
    complete_marker,
)
from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    enumerate_rdp_datasets,
    evidence_epoch_material,
)
from solana_alpha_lab.factory.hfic_session import evidence_epoch_sha256  # noqa: E402
from scripts.run_early_icp_first_hit_mix_falsifier import (  # noqa: E402
    main as falsifier_cli,
)

TEST_FREE_KEY = "test-free-key-not-a-secret"
SCORER_SHA256 = "7ad086f0530f7e5ac7185a8978bf12c91a0a0478405d68bca5271da04b720942"
SNAPSHOT = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
V2_COMPLETE_BYTES = b'{"terminal_outcome":"STOP_BEFORE_QUOTES_ELIGIBLE_BELOW_FLOOR","window_complete":true}\n'
WRAPPED_SOL = "So11111111111111111111111111111111111111112"


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
        clock: _Clock,
        *,
        n_eligible: int = 10,
        miss_checks: int = 0,
        crash_after: int | None = None,
        y_mode: str = "earn",
        sell_mode: str = "quote",
        transport_error: bool = False,
    ) -> None:
        self.clock = clock
        self.n_eligible = n_eligible
        self.miss_remaining = miss_checks
        self.crash_after = crash_after
        self.y_mode = y_mode
        self.sell_mode = sell_mode
        self.transport_error = transport_error
        self.urls: list[str] = []

    def _eligible_rows(self) -> list[dict[str, Any]]:
        created = (self.clock.now() - timedelta(seconds=360)).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows: list[dict[str, Any]] = []
        for index in range(self.n_eligible):
            rows.append(
                {
                    "id": f"mint-{index:02d}",
                    "launchpad": "pump.fun",
                    "liquidity": 2500.0,
                    "mcap": 12000.0,
                    "firstPool": {"createdAt": created},
                    "stats5m": {"buyVolume": 10.0 + index, "sellVolume": 5.0},
                }
            )
        return rows

    def _miss_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "id": f"miss-{index:02d}",
                "launchpad": "pump.fun",
                "liquidity": 1.0,
                "mcap": 12000.0,
                "firstPool": {"createdAt": self.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ")},
                "stats5m": {"buyVolume": 10.0, "sellVolume": 5.0},
            }
            for index in range(10)
        ]

    def open(self, request: object, timeout: float = 0) -> _Response:
        del timeout
        url = str(getattr(request, "full_url"))
        if self.crash_after is not None and len(self.urls) >= self.crash_after:
            raise RuntimeError("injected crash")
        if self.transport_error:
            raise urllib.error.URLError("injected transport")
        self.urls.append(url)
        if TEST_FREE_KEY in url:
            raise AssertionError("secret in URL")
        if "/tokens/v2/recent" in url or "/tokens/v2/search" in url:
            if self.miss_remaining > 0:
                payload = self._miss_rows()
                if "/tokens/v2/search" in url:
                    self.miss_remaining -= 1
                return _Response(json.dumps(payload).encode("utf-8"))
            return _Response(json.dumps(self._eligible_rows()).encode("utf-8"))
        if "/swap/v2/order" in url:
            query = parse_qs(urlparse(url).query)
            values = {key: items[0] for key, items in query.items()}
            if values.get("inputMint") != WRAPPED_SOL and self.sell_mode == "meu":
                return _Response(
                    json.dumps({"error": "Failed to get quotes", "transaction": None}).encode("utf-8")
                )
            mint = values.get("outputMint") if values.get("inputMint") == WRAPPED_SOL else values.get("inputMint")
            index = int(str(mint).split("-")[1])
            if self.y_mode == "earn":
                sell_out = str(10_000_000 + index * 100_000)
            elif self.y_mode == "close":
                sell_out = str(20_000_000 - index * 100_000)
            else:
                sell_out = "10500000"
            body = {
                "transaction": None,
                "requestId": "q",
                "inputMint": values["inputMint"],
                "outputMint": values["outputMint"],
                "inAmount": values["amount"],
                "outAmount": "11000000" if values["inputMint"] == WRAPPED_SOL else sell_out,
                "router": "dflow",
                "mode": "manual",
            }
            return _Response(json.dumps(body).encode("utf-8"))
        raise AssertionError(f"unexpected URL: {url}")


def _stub_preflight(*_args: object, **_kwargs: object) -> dict[str, object]:
    return {"credential_reads": 0, "provider_requests": 0, "dns_resolved": True}


def _seed_v2(data_root: Path) -> bytes:
    path = complete_marker(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(V2_COMPLETE_BYTES)
    return V2_COMPLETE_BYTES


def _epoch(data_root: Path) -> str:
    return evidence_epoch_sha256(evidence_epoch_material(ROOT, data_root))


def _run(
    data_root: Path,
    staging_root: Path,
    opener: _Opener,
    clock: _Clock,
    *,
    phrase: str = AUTHORITY_PHRASE,
    publication_hook: Any = None,
    search_commit_hook: Any = None,
) -> dict[str, Any]:
    return run_first_hit_mix_falsifier(
        repo_root=ROOT,
        data_root=data_root,
        staging_root=staging_root,
        authority_phrase=phrase,
        credential_loader=lambda: TEST_FREE_KEY,
        opener=opener,
        clock=clock.now,
        sleeper=clock.sleep,
        monotonic_clock=clock.monotonic,
        preflight_fn=_stub_preflight,
        publication_hook=publication_hook,
        search_commit_hook=search_commit_hook,
    )


class EarlyIcpFirstHitMixFalsifierTests(unittest.TestCase):
    def test_policy_pins_cadence_reserve_runner_and_unchanged_scorer(self) -> None:
        policy = load_policy(ROOT)
        validate_policy(policy, repo_root=ROOT)
        loaded = yaml.safe_load((ROOT / POLICY_RELATIVE).read_text(encoding="utf-8"))
        self.assertEqual(loaded["external_authority"]["owner_phrase"], AUTHORITY_PHRASE)
        self.assertEqual(quote_capacity(0), 29)
        self.assertEqual(quote_capacity(40), 10)
        self.assertEqual(MAX_DENSITY_CHECKS * 2 + QUOTE_CALL_RESERVE, CALL_CAP)
        self.assertEqual(DENSITY_CHECK_PERIOD_SECONDS, 60)
        self.assertEqual(
            hashlib.sha256((ROOT / FACTORY_RUNNER).read_bytes()).hexdigest(),
            FACTORY_RUNNER_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "src/solana_alpha_lab/factory/forward_mix_offline.py").read_bytes()
            ).hexdigest(),
            SCORER_SHA256,
        )
        preflight = credential_free_first_hit_preflight(ROOT, preflight_fn=_stub_preflight)
        self.assertEqual(preflight["call_cap"], 60)
        self.assertEqual(preflight["max_density_checks"], 20)
        self.assertEqual(preflight["quote_call_reserve"], 20)
        self.assertEqual(preflight["retries"], 0)
        self.assertIs(preflight["fallback"], False)
        self.assertEqual(preflight["provider_requests"], 0)

    def test_wrong_phrase_makes_zero_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            clock = _Clock()
            opener = _Opener(clock)
            with self.assertRaises(FirstHitError) as raised:
                _run(data_root, staging, opener, clock, phrase="not-the-phrase")
            self.assertEqual(str(raised.exception), "AUTHORITY_PHRASE_INVALID")
            self.assertEqual(raised.exception.provider_requests, 0)
            self.assertEqual(opener.urls, [])

    def test_staging_inside_rdp_is_rejected_with_zero_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            _seed_v2(data_root)
            clock = _Clock()
            opener = _Opener(clock)
            with self.assertRaises(FirstHitError) as raised:
                _run(data_root, data_root / "staging", opener, clock)
            self.assertEqual(str(raised.exception), "STAGING_INSIDE_RDP")
            self.assertEqual(opener.urls, [])

    def test_sleep_after_twenty_misses_is_forty_calls_and_does_not_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            before_epoch = _epoch(data_root)
            clock = _Clock()
            opener = _Opener(clock, miss_checks=20)
            receipt = _run(data_root, staging, opener, clock)
            self.assertEqual(receipt["terminal_outcome"], SLEEP_TERMINAL)
            self.assertIsNone(receipt["scientific_terminal"])
            self.assertEqual(receipt["provider_requests"], 40)
            self.assertEqual(receipt["quotes_attempted"], 0)
            self.assertFalse(receipt["dataset_published"])
            self.assertFalse((data_root / PUBLISHED_RELATIVE).exists())
            self.assertFalse((data_root / "journal.json").exists())
            self.assertTrue((staging / "journal.json").is_file())
            self.assertEqual(v2_complete_path(data_root).read_bytes(), V2_COMPLETE_BYTES)
            self.assertEqual(_epoch(data_root), before_epoch)
            self.assertEqual(sum("/tokens/v2/recent" in url for url in opener.urls), 20)
            self.assertEqual(sum("/tokens/v2/search" in url for url in opener.urls), 20)
            self.assertEqual(sum("/swap/v2/order" in url for url in opener.urls), 0)
            period_sleeps = [item for item in clock.sleeps if item >= 50]
            self.assertEqual(len(period_sleeps), 20)

    def test_early_hit_earn_publishes_one_bundle_and_one_search_after_r0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            before_epoch = _epoch(data_root)
            clock = _Clock()
            opener = _Opener(clock, n_eligible=10, y_mode="earn")
            receipt = _run(data_root, staging, opener, clock)
            self.assertEqual(receipt["terminal_outcome"], "EARN_ONE_CONFIRMATORY_FRESH_OOS")
            self.assertEqual(receipt["quoted_count"], 10)
            self.assertEqual(receipt["unquoted_count"], 0)
            self.assertEqual(receipt["provider_requests"], 22)
            self.assertTrue((data_root / PUBLISHED_RELATIVE).is_file())
            self.assertNotEqual(_epoch(data_root), before_epoch)
            self.assertEqual(sum("/tokens/v2/search" in url for url in opener.urls), 1)
            self.assertEqual(v2_complete_path(data_root).read_bytes(), V2_COMPLETE_BYTES)
            entries, _warnings = enumerate_rdp_datasets(data_root)
            self.assertTrue(any(item["dataset_manifest_id"] == DATASET_MANIFEST_ID for item in entries))
            second = _run(data_root, staging, opener, clock)
            self.assertEqual(second.get("resume"), "IDEMPOTENT_PUBLISHED")
            self.assertEqual(len(opener.urls), 22)

    def test_close_when_tau_b_is_non_positive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            clock = _Clock()
            opener = _Opener(clock, n_eligible=10, y_mode="close")
            receipt = _run(data_root, staging, opener, clock)
            self.assertEqual(receipt["terminal_outcome"], "CLOSE_EARLY_TAKER_VOLUME_MIX_FAMILY")
            self.assertLessEqual(float(receipt["score"]["tau_b"]), 0)

    def test_invalid_when_rankable_h900_below_floor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            clock = _Clock()
            opener = _Opener(clock, n_eligible=10, sell_mode="meu")
            receipt = _run(data_root, staging, opener, clock)
            self.assertEqual(receipt["terminal_outcome"], "INVALID_EVIDENCE_REPLAN")
            self.assertEqual(receipt["score"]["rankable_h900"], 0)
            self.assertGreaterEqual(int(receipt["score"]["mix_eligible"]), 10)

    def test_last_budget_hit_quotes_ten_pairs_and_keeps_unquoted_y_null(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            clock = _Clock()
            opener = _Opener(clock, n_eligible=15, miss_checks=19, y_mode="earn")
            receipt = _run(data_root, staging, opener, clock)
            self.assertEqual(receipt["provider_requests"], 60)
            self.assertEqual(receipt["quoted_count"], 10)
            self.assertEqual(receipt["unquoted_count"], 5)
            self.assertEqual(receipt["eligible_count"], 15)
            self.assertEqual(receipt["terminal_outcome"], "EARN_ONE_CONFIRMATORY_FRESH_OOS")
            import pyarrow.parquet as pq

            table = pq.read_table(data_root / f"datasets/partitions/PARTITION-EARLY-ICP-FIRST-HIT-MIX-FALSIFIER-001.parquet")
            rows = table.to_pydict()
            unquoted = [
                index
                for index, quoted in enumerate(rows["quoted"])
                if not quoted
            ]
            self.assertEqual(len(unquoted), 5)
            for index in unquoted:
                self.assertIsNone(rows["y"][index])
                self.assertEqual(rows["h900_terminal"][index], NOT_QUOTED)
            self.assertEqual(sum("/tokens/v2/search" in url for url in opener.urls), 20)
            self.assertEqual(sum("/swap/v2/order" in url for url in opener.urls), 20)

    def test_y_blind_prefix_keeps_full_eligible_universe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            clock = _Clock()
            opener = _Opener(clock, n_eligible=30, y_mode="earn")
            receipt = _run(data_root, staging, opener, clock)
            self.assertEqual(receipt["quoted_count"], 29)
            self.assertEqual(receipt["unquoted_count"], 1)
            self.assertEqual(receipt["eligible_count"], 30)
            self.assertEqual(receipt["provider_requests"], 60)

    def test_in_flight_call_is_fail_closed_and_not_retried(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            before_epoch = _epoch(data_root)
            clock = _Clock()
            opener = _Opener(clock, n_eligible=10, crash_after=1)
            with self.assertRaises(RuntimeError):
                _run(data_root, staging, opener, clock)
            opener.crash_after = None
            with self.assertRaises(FirstHitError) as raised:
                _run(data_root, staging, opener, clock)
            self.assertEqual(str(raised.exception), IN_FLIGHT_TERMINAL)
            self.assertEqual(len(opener.urls), 1)
            self.assertFalse((data_root / PUBLISHED_RELATIVE).exists())
            self.assertEqual(_epoch(data_root), before_epoch)
            self.assertEqual(v2_complete_path(data_root).read_bytes(), V2_COMPLETE_BYTES)

    def test_crash_before_commit_marker_leaves_epoch_unchanged_then_resume_publishes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            before_epoch = _epoch(data_root)

            class _Hook:
                def __init__(self) -> None:
                    self.calls = 0

                def __call__(self) -> None:
                    self.calls += 1
                    if self.calls == 1:
                        raise RuntimeError("crash before marker")

            hook = _Hook()
            clock = _Clock()
            opener = _Opener(clock, n_eligible=10, y_mode="earn")
            with self.assertRaises(RuntimeError):
                _run(data_root, staging, opener, clock, publication_hook=hook)
            self.assertTrue((data_root / MANIFEST_RELATIVE).is_file())
            self.assertTrue((data_root / LABELS_RELATIVE).is_file())
            self.assertFalse((data_root / PUBLISHED_RELATIVE).exists())
            entries, warnings = enumerate_rdp_datasets(data_root)
            self.assertFalse(any(item["dataset_manifest_id"] == DATASET_MANIFEST_ID for item in entries))
            self.assertTrue(
                any(item.get("code") == "DATASET_PUBLICATION_INCOMPLETE" for item in warnings)
            )
            self.assertEqual(_epoch(data_root), before_epoch)
            http_after_crash = len(opener.urls)
            receipt = _run(data_root, staging, opener, clock, publication_hook=hook)
            self.assertEqual(receipt["terminal_outcome"], "EARN_ONE_CONFIRMATORY_FRESH_OOS")
            self.assertTrue((data_root / PUBLISHED_RELATIVE).is_file())
            self.assertNotEqual(_epoch(data_root), before_epoch)
            self.assertEqual(len(opener.urls), http_after_crash)

    def test_transport_error_is_in_flight_and_not_retried(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            clock = _Clock()
            opener = _Opener(clock, n_eligible=10, transport_error=True)
            with self.assertRaises(FirstHitError) as raised:
                _run(data_root, staging, opener, clock)
            self.assertEqual(str(raised.exception), IN_FLIGHT_TERMINAL)
            opener.transport_error = False
            with self.assertRaises(FirstHitError) as second:
                _run(data_root, staging, opener, clock)
            self.assertEqual(str(second.exception), IN_FLIGHT_TERMINAL)
            self.assertEqual(opener.urls, [])
            journal = json.loads((staging / "journal.json").read_text(encoding="utf-8"))
            recent = journal["observations"]["CHECK:00:RECENT"]
            self.assertEqual(recent["state"], "STARTED")
            self.assertNotEqual(recent.get("state"), "COMPLETED")

    def test_resume_after_completed_search_does_not_issue_second_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            clock = _Clock()
            opener = _Opener(clock, n_eligible=10, y_mode="earn")

            class _Hook:
                def __init__(self) -> None:
                    self.calls = 0

                def __call__(self) -> None:
                    self.calls += 1
                    if self.calls == 1:
                        raise RuntimeError("crash after hash-bound search")

            hook = _Hook()
            with self.assertRaises(RuntimeError):
                _run(data_root, staging, opener, clock, search_commit_hook=hook)
            self.assertEqual(sum("/tokens/v2/search" in url for url in opener.urls), 1)
            journal = json.loads((staging / "journal.json").read_text(encoding="utf-8"))
            self.assertIsNone(journal.get("hit_check_index"))
            self.assertEqual(journal["observations"]["CHECK:00:SEARCH"]["state"], "COMPLETED")
            receipt = _run(data_root, staging, opener, clock, search_commit_hook=hook)
            self.assertEqual(receipt["terminal_outcome"], "EARN_ONE_CONFIRMATORY_FRESH_OOS")
            self.assertEqual(sum("/tokens/v2/search" in url for url in opener.urls), 1)

    def test_delayed_resume_keeps_completed_sell_not_late_before_quote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)

            class _Hook:
                def __init__(self) -> None:
                    self.calls = 0

                def __call__(self) -> None:
                    self.calls += 1
                    if self.calls == 1:
                        raise RuntimeError("crash before marker")

            hook = _Hook()
            clock = _Clock()
            opener = _Opener(clock, n_eligible=10, y_mode="earn")
            with self.assertRaises(RuntimeError):
                _run(data_root, staging, opener, clock, publication_hook=hook)
            http_after_crash = len(opener.urls)
            clock.current += timedelta(seconds=10_000)
            receipt = _run(data_root, staging, opener, clock, publication_hook=hook)
            self.assertEqual(receipt["terminal_outcome"], "EARN_ONE_CONFIRMATORY_FRESH_OOS")
            self.assertEqual(len(opener.urls), http_after_crash)
            self.assertEqual(receipt["score"]["rankable_h900"], 10)

    def test_cli_help_states_operator_terminals_and_in_flight(self) -> None:
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            with self.assertRaises(SystemExit):
                falsifier_cli(["--help"])
        help_text = buf.getvalue()
        self.assertIn("IN_FLIGHT_CALL_INDETERMINATE", help_text)
        self.assertIn("SLEEP_ELIGIBLE_BELOW_10", help_text)
        self.assertIn("staging-root must be outside data-root", help_text)

    def test_cli_run_without_staging_is_zero_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            missing = falsifier_cli(
                [
                    "--root",
                    str(ROOT),
                    "--data-root",
                    str(data_root),
                    "run",
                    "--owner-phrase",
                    AUTHORITY_PHRASE,
                ]
            )
            self.assertEqual(missing, 2)

    def test_capability_router_is_not_forward_h900_or_quote_native_allowlist(self) -> None:
        self.assertIs(
            CAPABILITY_ROUTER[CAP_JUPITER_FREE_KEY_EARLY_ICP_FIRST_HIT_MIX_FALSIFIER],
            capture_early_icp_first_hit_mix_falsifier,
        )
        self.assertIsNot(
            CAPABILITY_ROUTER[CAP_JUPITER_FREE_KEY_EARLY_ICP_FIRST_HIT_MIX_FALSIFIER],
            capture_forward_h900_quote,
        )
        source = (ROOT / "src/solana_alpha_lab/factory/capabilities.py").read_text(encoding="utf-8")
        allowlist = source.split("if atom_id not in {", 1)[1].split("}", 1)[0]
        self.assertNotIn("EARLY_ICP_FIRST_HIT_MIX_FALSIFIER_V1", allowlist)
        self.assertEqual(CAPABILITY_ID, "CAP-JUPITER-FREE-KEY-EARLY-ICP-FIRST-HIT-MIX-FALSIFIER-001")


if __name__ == "__main__":
    unittest.main()
