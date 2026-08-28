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
    DECISION_RELATIVE,
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
    IDENTITY_MISMATCH,
    JOURNAL_SCHEMA,
    JOURNAL_SCHEMA_VERSION,
    PARTITION_RELATIVE,
    REQUEST_SHA256_MISMATCH,
    SEARCH_POOL_CAP,
    SLEEP_TERMINAL,
    FirstHitError,
    credential_free_first_hit_preflight,
    expire_matured_pool,
    ingest_recent_into_pool,
    load_policy,
    published_marker_path,
    quote_capacity,
    run_first_hit_mix_falsifier,
    select_search_mints,
    select_valid_mix_eligible,
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


def _as_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


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
        recent_age_seconds: int = 360,
        extra_invalid: int = 0,
        rotate_recent: bool = False,
        expire_first_search: bool = False,
        recent_count: int | None = None,
        fail_recent_after: int | None = None,
    ) -> None:
        self.clock = clock
        self.n_eligible = n_eligible
        self.miss_remaining = miss_checks
        self.crash_after = crash_after
        self.y_mode = y_mode
        self.sell_mode = sell_mode
        self.transport_error = transport_error
        self.recent_age_seconds = recent_age_seconds
        self.extra_invalid = extra_invalid
        self.rotate_recent = rotate_recent
        self.expire_first_search = expire_first_search
        self.recent_count = recent_count
        self.fail_recent_after = fail_recent_after
        self.urls: list[str] = []
        self.birth: dict[str, str] = {}
        self.liquidity: dict[str, float] = {}
        self.stats: dict[str, dict[str, float]] = {}
        self.recent_waves = 0
        self.search_calls = 0
        self.wave = 0

    def _record(self, mint: str, created: str, *, liq: float, stats: dict[str, float]) -> None:
        self.birth.setdefault(mint, created)
        self.liquidity.setdefault(mint, liq)
        self.stats.setdefault(mint, stats)

    def _row(self, mint: str, *, created_override: str | None = None) -> dict[str, Any]:
        created = created_override or self.birth[mint]
        return {
            "id": mint,
            "launchpad": "pump.fun",
            "liquidity": self.liquidity.get(mint, 2500.0),
            "mcap": 12000.0,
            "firstPool": {"createdAt": created},
            "stats5m": dict(self.stats.get(mint, {"buyVolume": 10.0, "sellVolume": 5.0})),
        }

    def _recent_payload(self) -> list[dict[str, Any]]:
        now = self.clock.now()
        if self.miss_remaining > 0:
            created = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            rows: list[dict[str, Any]] = []
            for index in range(10):
                mint = f"miss-{self.wave:02d}-{index:02d}"
                self._record(mint, created, liq=1.0, stats={"buyVolume": 10.0, "sellVolume": 5.0})
                rows.append(self._row(mint))
            self.wave += 1
            return rows
        if self.rotate_recent:
            created = (now - timedelta(seconds=self.recent_age_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
            rows = []
            for index in range(10):
                mint = f"gen-{self.recent_waves:02d}-{index:02d}"
                self._record(
                    mint,
                    created,
                    liq=2500.0,
                    stats={"buyVolume": 10.0 + index, "sellVolume": 5.0},
                )
                rows.append(self._row(mint))
            self.recent_waves += 1
            return rows
        count = self.recent_count if self.recent_count is not None else self.n_eligible
        width = 3 if count >= 100 else 2
        created = (now - timedelta(seconds=self.recent_age_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = []
        for index in range(count):
            mint = f"mint-{index:0{width}d}"
            self._record(
                mint,
                created,
                liq=2500.0,
                stats={"buyVolume": 10.0 + index, "sellVolume": 5.0},
            )
            rows.append(self._row(mint))
        for index in range(self.extra_invalid):
            mint = f"bad-{self.wave:02d}-{index:02d}"
            self._record(
                mint,
                created,
                liq=2500.0,
                stats={"buyVolume": 0.0, "sellVolume": 0.0},
            )
            rows.append(self._row(mint))
        self.wave += 1
        return rows

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
        if "/tokens/v2/recent" in url:
            if self.fail_recent_after is not None and sum(
                "/tokens/v2/recent" in item for item in self.urls
            ) > self.fail_recent_after:
                return _Response(b'{"error":"recent-unavailable"}')
            return _Response(json.dumps(self._recent_payload()).encode("utf-8"))
        if "/tokens/v2/search" in url:
            query = parse_qs(urlparse(url).query).get("query", [""])[0]
            mints = [item for item in query.split(",") if item]
            created_override = None
            if self.expire_first_search and self.search_calls == 0:
                created_override = (self.clock.now() - timedelta(seconds=700)).strftime("%Y-%m-%dT%H:%M:%SZ")
            rows = []
            for mint in mints:
                if mint not in self.birth:
                    created = (self.clock.now() - timedelta(seconds=self.recent_age_seconds)).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    )
                    self._record(
                        mint,
                        created,
                        liq=2500.0,
                        stats={"buyVolume": 10.0, "sellVolume": 5.0},
                    )
                mint_override = created_override
                if mint.startswith("miss-"):
                    mint_override = (self.clock.now() - timedelta(seconds=700)).strftime("%Y-%m-%dT%H:%M:%SZ")
                rows.append(self._row(mint, created_override=mint_override))
            if self.miss_remaining > 0:
                self.miss_remaining -= 1
            self.search_calls += 1
            return _Response(json.dumps(rows).encode("utf-8"))
        if "/swap/v2/order" in url:
            query = parse_qs(urlparse(url).query)
            values = {key: items[0] for key, items in query.items()}
            if values.get("inputMint") != WRAPPED_SOL and self.sell_mode == "meu":
                return _Response(
                    json.dumps({"error": "Failed to get quotes", "transaction": None}).encode("utf-8")
                )
            mint = values.get("outputMint") if values.get("inputMint") == WRAPPED_SOL else values.get("inputMint")
            try:
                index = int(str(mint).rsplit("-", 1)[-1])
            except (TypeError, ValueError):
                index = 0
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
                "outAmount": "11000000" if values.get("inputMint") == WRAPPED_SOL else sell_out,
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
        self.assertEqual(loaded["retained_cohort"]["journal_schema"], JOURNAL_SCHEMA)
        self.assertEqual(loaded["retained_cohort"]["journal_schema_version"], JOURNAL_SCHEMA_VERSION)
        self.assertEqual(preflight["journal_schema"], JOURNAL_SCHEMA)
        self.assertEqual(preflight["journal_schema_version"], JOURNAL_SCHEMA_VERSION)
        self.assertEqual(preflight["quote_call_reserve"], 20)
        self.assertEqual(preflight["retries"], 0)
        self.assertIs(preflight["fallback"], False)
        self.assertEqual(preflight["provider_requests"], 0)
        self.assertEqual(preflight["search_from"], "retained_pool")
        self.assertEqual(preflight["r0_floor"], "valid_mix_eligible")
        self.assertEqual(SEARCH_POOL_CAP, 100)

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
            journal_after_crash = json.loads((staging / "journal.json").read_text(encoding="utf-8"))
            self.assertIsNotNone(journal_after_crash.get("decision_at"))
            self.assertIsNotNone(journal_after_crash.get("r0_event_at"))
            receipt = _run(data_root, staging, opener, clock, publication_hook=hook)
            self.assertEqual(receipt["terminal_outcome"], "EARN_ONE_CONFIRMATORY_FRESH_OOS")
            self.assertEqual(receipt["decision_at"], journal_after_crash["decision_at"])
            self.assertEqual(receipt["r0_event_at"], journal_after_crash["r0_event_at"])
            self.assertTrue((data_root / PUBLISHED_RELATIVE).is_file())
            self.assertNotEqual(_epoch(data_root), before_epoch)
            self.assertEqual(len(opener.urls), http_after_crash)

    def test_microsecond_clock_crash_before_marker_resume_is_byte_identical(self) -> None:
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
            clock.current = datetime(2026, 8, 28, 12, 0, 0, 123456, tzinfo=UTC)
            opener = _Opener(clock, n_eligible=10, y_mode="earn")
            with self.assertRaises(RuntimeError):
                _run(data_root, staging, opener, clock, publication_hook=hook)
            manifest_after_crash = (data_root / MANIFEST_RELATIVE).read_bytes()
            partition_after_crash = (data_root / PARTITION_RELATIVE).read_bytes()
            decision_after_crash = (data_root / DECISION_RELATIVE).read_bytes()
            journal_after_crash = json.loads((staging / "journal.json").read_text(encoding="utf-8"))
            self.assertRegex(journal_after_crash["decision_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
            http_after_crash = len(opener.urls)
            receipt = _run(data_root, staging, opener, clock, publication_hook=hook)
            self.assertEqual(receipt["terminal_outcome"], "EARN_ONE_CONFIRMATORY_FRESH_OOS")
            self.assertEqual((data_root / MANIFEST_RELATIVE).read_bytes(), manifest_after_crash)
            self.assertEqual((data_root / PARTITION_RELATIVE).read_bytes(), partition_after_crash)
            self.assertEqual((data_root / DECISION_RELATIVE).read_bytes(), decision_after_crash)
            self.assertEqual(len(opener.urls), http_after_crash)
            self.assertEqual(receipt["decision_at"], journal_after_crash["decision_at"])
            partition = json.loads(partition_after_crash.decode("utf-8"))
            self.assertEqual(_as_dt(partition["created_at"]), _as_dt(journal_after_crash["decision_at"]))

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

    def test_late_clock_does_not_mask_in_flight_sell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            clock = _Clock()
            # 1 recent + 1 search + 10 buys = 12 completed HTTP; next opener call is first SELL.
            opener = _Opener(clock, n_eligible=10, y_mode="earn", crash_after=12)
            with self.assertRaises(RuntimeError):
                _run(data_root, staging, opener, clock)
            journal = json.loads((staging / "journal.json").read_text(encoding="utf-8"))
            started_sells = [
                key
                for key, value in journal["observations"].items()
                if key.endswith(":SELL_H900") and value.get("state") == "STARTED"
            ]
            self.assertTrue(started_sells)
            clock.current += timedelta(seconds=10_000)
            opener.crash_after = None
            with self.assertRaises(FirstHitError) as raised:
                _run(data_root, staging, opener, clock)
            self.assertEqual(str(raised.exception), IN_FLIGHT_TERMINAL)
            self.assertFalse(published_marker_path(data_root).exists())

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
        self.assertIn("STAGING_ATTEMPT_IDENTITY_MISMATCH", help_text)
        self.assertIn("staging-root must be outside data-root", help_text)
        self.assertIn("valid_mix_eligible", help_text)

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

    def test_young_mints_are_retained_and_mature_to_r0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            clock = _Clock()
            opener = _Opener(clock, n_eligible=10, recent_age_seconds=60, y_mode="earn")
            receipt = _run(data_root, staging, opener, clock)
            self.assertEqual(receipt["terminal_outcome"], "EARN_ONE_CONFIRMATORY_FRESH_OOS")
            search_urls = [url for url in opener.urls if "/tokens/v2/search" in url]
            self.assertGreaterEqual(len(search_urls), 2)
            self.assertEqual(sum("/tokens/v2/search" in url for url in opener.urls), len(search_urls))
            journal = json.loads((staging / "journal.json").read_text(encoding="utf-8"))
            self.assertIn("mint-00", journal["retained_pool"])
            self.assertEqual(journal["retained_pool"]["mint-00"]["first_seen_at"], journal["observations"]["CHECK:00:RECENT"]["observed_at"])
            self.assertGreaterEqual(int(journal["hit_check_index"]), 1)
            self.assertEqual(v2_complete_path(data_root).read_bytes(), V2_COMPLETE_BYTES)

    def test_failed_recent_still_searches_retained_pool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            clock = _Clock()
            opener = _Opener(
                clock,
                n_eligible=10,
                recent_age_seconds=60,
                fail_recent_after=1,
                y_mode="earn",
            )
            receipt = _run(data_root, staging, opener, clock)
            self.assertEqual(receipt["terminal_outcome"], "EARN_ONE_CONFIRMATORY_FRESH_OOS")
            search_urls = [url for url in opener.urls if "/tokens/v2/search" in url]
            self.assertGreaterEqual(len(search_urls), 2)
            second = parse_qs(urlparse(search_urls[1]).query)["query"][0].split(",")
            self.assertIn("mint-00", second)
            self.assertGreaterEqual(sum("/tokens/v2/recent" in url for url in opener.urls), 2)

    def test_r0_resume_does_not_reenter_density_or_recompute_search_universe(self) -> None:
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
                        raise RuntimeError("crash after frozen search bytes")

            hook = _Hook()
            with self.assertRaises(RuntimeError):
                _run(data_root, staging, opener, clock, search_commit_hook=hook)
            journal_path = staging / "journal.json"
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            search_obs = journal["observations"]["CHECK:00:SEARCH"]
            self.assertEqual(search_obs["state"], "COMPLETED")
            self.assertIn("mint-00", search_obs["search_mints"])
            journal["hit_check_index"] = 0
            journal["r0_search_mints"] = list(search_obs["search_mints"])
            for entry in journal["retained_pool"].values():
                entry["active"] = False
            journal_path.write_bytes(
                json.dumps(journal, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
            )
            http_after_crash = len(opener.urls)
            receipt = _run(data_root, staging, opener, clock)
            self.assertEqual(receipt["terminal_outcome"], "EARN_ONE_CONFIRMATORY_FRESH_OOS")
            self.assertEqual(sum("/tokens/v2/search" in url for url in opener.urls), 1)
            self.assertGreater(len(opener.urls), http_after_crash)

    def test_current_recent_does_not_define_search_universe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            clock = _Clock()
            opener = _Opener(
                clock,
                n_eligible=10,
                recent_age_seconds=60,
                rotate_recent=True,
                y_mode="earn",
            )
            receipt = _run(data_root, staging, opener, clock)
            self.assertEqual(receipt["terminal_outcome"], "EARN_ONE_CONFIRMATORY_FRESH_OOS")
            search_urls = [url for url in opener.urls if "/tokens/v2/search" in url]
            self.assertGreaterEqual(len(search_urls), 2)
            first = parse_qs(urlparse(search_urls[0]).query)["query"][0].split(",")
            second = parse_qs(urlparse(search_urls[1]).query)["query"][0].split(",")
            self.assertIn("gen-00-00", first)
            self.assertNotIn("gen-01-00", first)
            self.assertIn("gen-00-00", second)
            self.assertIn("gen-01-00", second)

    def test_pool_over_100_has_stable_y_blind_order(self) -> None:
        snapshot = SNAPSHOT
        pool: dict[str, Any] = {}
        rows = [
            {"id": f"mint-{index:03d}", "launchpad": "pump.fun"}
            for index in range(120)
        ]
        ingest_recent_into_pool(pool, rows, observed_at="2026-08-28T12:00:00Z", excluded_mints=set())
        selected = select_search_mints(pool, snapshot_at=snapshot)
        self.assertEqual(len(selected), 100)
        self.assertEqual(selected, [f"mint-{index:03d}" for index in range(100)])
        selected_again = select_search_mints(pool, snapshot_at=snapshot)
        self.assertEqual(selected, selected_again)
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            clock = _Clock()
            opener = _Opener(clock, n_eligible=10, recent_count=120, recent_age_seconds=10, crash_after=2)
            with self.assertRaises(RuntimeError):
                _run(data_root, staging, opener, clock)
            search_urls = [url for url in opener.urls if "/tokens/v2/search" in url]
            self.assertEqual(len(search_urls), 1)
            queried = parse_qs(urlparse(search_urls[0]).query)["query"][0].split(",")
            self.assertEqual(len(queried), 100)
            self.assertEqual(queried, [f"mint-{index:03d}" for index in range(100)])

    def test_age_at_least_600_is_removed_from_active_pool(self) -> None:
        snapshot = SNAPSHOT
        pool = {
            "old-01": {
                "mint": "old-01",
                "first_seen_at": "2026-08-28T11:00:00Z",
                "consumed": False,
                "created_at": (SNAPSHOT - timedelta(seconds=700)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "active": True,
            },
            "live-01": {
                "mint": "live-01",
                "first_seen_at": "2026-08-28T12:00:00Z",
                "consumed": False,
                "created_at": (SNAPSHOT - timedelta(seconds=360)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "active": True,
            },
        }
        expire_matured_pool(pool, snapshot_at=snapshot)
        self.assertIs(pool["old-01"]["active"], False)
        self.assertIs(pool["live-01"]["active"], True)
        self.assertEqual(select_search_mints(pool, snapshot_at=snapshot), ["live-01"])
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            clock = _Clock()
            opener = _Opener(
                clock,
                n_eligible=10,
                recent_age_seconds=360,
                rotate_recent=True,
                expire_first_search=True,
                y_mode="earn",
            )
            receipt = _run(data_root, staging, opener, clock)
            self.assertEqual(receipt["terminal_outcome"], "EARN_ONE_CONFIRMATORY_FRESH_OOS")
            search_urls = [url for url in opener.urls if "/tokens/v2/search" in url]
            self.assertGreaterEqual(len(search_urls), 2)
            second = parse_qs(urlparse(search_urls[1]).query)["query"][0].split(",")
            self.assertNotIn("gen-00-00", second)
            self.assertIn("gen-01-00", second)
            journal = json.loads((staging / "journal.json").read_text(encoding="utf-8"))
            self.assertIs(journal["retained_pool"]["gen-00-00"]["active"], False)

    def test_stats5m_mapping_with_invalid_mix_is_not_quote_floor(self) -> None:
        structural = [
            {
                "id": f"bad-{index:02d}",
                "stats5m": {"buyVolume": 0.0, "sellVolume": 0.0},
            }
            for index in range(10)
        ]
        self.assertEqual(select_valid_mix_eligible(structural), [])
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            before_epoch = _epoch(data_root)
            clock = _Clock()
            opener = _Opener(clock, n_eligible=0, extra_invalid=10, recent_age_seconds=360)
            receipt = _run(data_root, staging, opener, clock)
            self.assertEqual(receipt["terminal_outcome"], SLEEP_TERMINAL)
            self.assertEqual(receipt["provider_requests"], 40)
            self.assertFalse(receipt["dataset_published"])
            self.assertEqual(_epoch(data_root), before_epoch)
            self.assertEqual(sum("/swap/v2/order" in url for url in opener.urls), 0)

    def test_valid_mix_hit_is_sole_r0_and_keeps_invalid_x_typed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            clock = _Clock()
            opener = _Opener(clock, n_eligible=10, extra_invalid=10, y_mode="earn")
            receipt = _run(data_root, staging, opener, clock)
            self.assertEqual(receipt["quoted_count"], 10)
            self.assertEqual(receipt["eligible_count"], 10)
            self.assertEqual(receipt["structural_eligible_count"], 20)
            self.assertEqual(receipt["invalid_x_count"], 10)
            self.assertEqual(sum("/tokens/v2/search" in url for url in opener.urls), 1)
            import pyarrow.parquet as pq

            table = pq.read_table(
                data_root / "datasets/partitions/PARTITION-EARLY-ICP-FIRST-HIT-MIX-FALSIFIER-001.parquet"
            )
            rows = table.to_pydict()
            self.assertEqual(len(rows["mint"]), 20)
            invalid = [
                index
                for index, mint in enumerate(rows["mint"])
                if str(mint).startswith("bad-")
            ]
            self.assertEqual(len(invalid), 10)
            for index in invalid:
                self.assertFalse(rows["quoted"][index])
                self.assertIsNone(rows["y"][index])
                self.assertEqual(rows["missingness_code"][index], "ZERO_DENOMINATOR")

    def test_crash_resume_before_and_after_maturity_search(self) -> None:
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
                        raise RuntimeError("crash after first retained search")

            hook = _Hook()
            clock = _Clock()
            opener = _Opener(clock, n_eligible=10, recent_age_seconds=60, y_mode="earn")
            with self.assertRaises(RuntimeError):
                _run(data_root, staging, opener, clock, search_commit_hook=hook)
            self.assertEqual(sum("/tokens/v2/search" in url for url in opener.urls), 1)
            journal = json.loads((staging / "journal.json").read_text(encoding="utf-8"))
            self.assertIn("retained_pool", journal)
            self.assertIn("mint-00", journal["retained_pool"])
            self.assertIsNone(journal.get("hit_check_index"))
            receipt = _run(data_root, staging, opener, clock, search_commit_hook=hook)
            self.assertEqual(receipt["terminal_outcome"], "EARN_ONE_CONFIRMATORY_FRESH_OOS")
            self.assertGreater(sum("/tokens/v2/search" in url for url in opener.urls), 1)
            self.assertEqual(journal["observations"]["CHECK:00:SEARCH"]["state"], "COMPLETED")
            self.assertIsNotNone(json.loads((staging / "journal.json").read_text(encoding="utf-8")).get("hit_check_index"))

    def test_prior_sleep_artifacts_and_v2_complete_are_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            prior_sleep = Path(tmp) / "prior_sleep"
            data_root.mkdir()
            prior_sleep.mkdir()
            frozen = b'{"terminal_outcome":"SLEEP_ELIGIBLE_BELOW_10","dataset_published":false}\n'
            marker = prior_sleep / "journal.json"
            marker.write_bytes(frozen)
            _seed_v2(data_root)
            clock = _Clock()
            opener = _Opener(clock, n_eligible=10, y_mode="earn")
            receipt = _run(data_root, staging, opener, clock)
            self.assertEqual(receipt["terminal_outcome"], "EARN_ONE_CONFIRMATORY_FRESH_OOS")
            self.assertEqual(marker.read_bytes(), frozen)
            self.assertEqual(v2_complete_path(data_root).read_bytes(), V2_COMPLETE_BYTES)

    def test_published_provenance_uses_decision_at_not_r0_search_at(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            _seed_v2(data_root)
            clock = _Clock()
            opener = _Opener(clock, n_eligible=10, y_mode="earn")
            receipt = _run(data_root, staging, opener, clock)
            self.assertEqual(receipt["terminal_outcome"], "EARN_ONE_CONFIRMATORY_FRESH_OOS")
            journal = json.loads((staging / "journal.json").read_text(encoding="utf-8"))
            decision = json.loads((data_root / DECISION_RELATIVE).read_text(encoding="utf-8"))
            partition = json.loads((data_root / PARTITION_RELATIVE).read_text(encoding="utf-8"))
            dataset = json.loads((data_root / MANIFEST_RELATIVE).read_text(encoding="utf-8"))
            r0_event_at = _as_dt(journal["r0_event_at"])
            decision_at = _as_dt(journal["decision_at"])
            self.assertEqual(decision["r0_event_at"], journal["r0_event_at"])
            self.assertEqual(decision["decision_at"], journal["decision_at"])
            self.assertGreater(decision_at, r0_event_at)
            self.assertEqual(_as_dt(partition["min_event_time"]), r0_event_at)
            self.assertEqual(_as_dt(partition["max_event_time"]), decision_at)
            self.assertEqual(_as_dt(partition["min_available_to_strategy_at"]), decision_at)
            self.assertEqual(_as_dt(partition["max_available_to_strategy_at"]), decision_at)
            self.assertEqual(_as_dt(partition["created_at"]), decision_at)
            self.assertEqual(_as_dt(partition["first_reliable_available_at"]), decision_at)
            self.assertEqual(_as_dt(dataset["created_at"]), decision_at)
            self.assertEqual(_as_dt(dataset["first_reliable_available_at"]), decision_at)
            self.assertGreater(_as_dt(dataset["first_reliable_available_at"]), r0_event_at)
            h900_times = [
                _as_dt(str(item["observed_at"]))
                for obs_id, item in journal["observations"].items()
                if str(obs_id).endswith(":SELL_H900") or str(obs_id).endswith(":BUY_R0")
                if isinstance(item, dict) and item.get("state") == "COMPLETED" and item.get("observed_at")
            ]
            self.assertTrue(h900_times)
            self.assertGreaterEqual(_as_dt(dataset["first_reliable_available_at"]), max(h900_times))
            search_obs = journal["observations"]["CHECK:00:SEARCH"]
            self.assertNotEqual(str(dataset["first_reliable_available_at"])[:19], str(search_obs["observed_at"])[:19])

    def test_legacy_pre_corrective_journal_is_rejected_with_zero_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "rdp"
            staging = Path(tmp) / "staging"
            data_root.mkdir()
            staging.mkdir()
            _seed_v2(data_root)
            journal_path = staging / "journal.json"
            leftover = staging / "raw" / "CHECK_00_RECENT.body"
            leftover.parent.mkdir()
            leftover.write_bytes(b'{"legacy":true}')
            frozen = json.dumps(
                {
                    "observations": {
                        "CHECK:00:RECENT": {
                            "state": "COMPLETED",
                            "url": "https://example.invalid/tokens/v2/recent",
                            "body_sha256": "0" * 64,
                            "observed_at": "2026-08-28T12:00:00Z",
                        }
                    },
                    "last_call_at": "2026-08-28T12:00:00Z",
                    "retained_pool": {
                        "mint-00": {
                            "mint": "mint-00",
                            "first_seen_at": "2026-08-28T12:00:00Z",
                            "consumed": False,
                            "active": True,
                        }
                    },
                },
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            journal_path.write_bytes(frozen)
            clock = _Clock()
            opener = _Opener(clock, n_eligible=10, y_mode="earn")
            credential_reads: list[int] = []

            def loader() -> str:
                credential_reads.append(1)
                return TEST_FREE_KEY

            with self.assertRaises(FirstHitError) as raised:
                run_first_hit_mix_falsifier(
                    repo_root=ROOT,
                    data_root=data_root,
                    staging_root=staging,
                    authority_phrase=AUTHORITY_PHRASE,
                    credential_loader=loader,
                    opener=opener,
                    clock=clock.now,
                    sleeper=clock.sleep,
                    monotonic_clock=clock.monotonic,
                    preflight_fn=_stub_preflight,
                )
            self.assertEqual(str(raised.exception), IDENTITY_MISMATCH)
            self.assertEqual(raised.exception.provider_requests, 0)
            self.assertEqual(opener.urls, [])
            self.assertEqual(credential_reads, [])
            self.assertEqual(journal_path.read_bytes(), frozen)
            self.assertEqual(leftover.read_bytes(), b'{"legacy":true}')

    def test_cached_search_with_different_mint_query_is_rejected(self) -> None:
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
                        raise RuntimeError("crash after frozen search bytes")

            hook = _Hook()
            with self.assertRaises(RuntimeError):
                _run(data_root, staging, opener, clock, search_commit_hook=hook)
            journal_path = staging / "journal.json"
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            search_obs = journal["observations"]["CHECK:00:SEARCH"]
            self.assertEqual(search_obs["state"], "COMPLETED")
            self.assertIn("request_sha256", search_obs)
            journal["hit_check_index"] = 0
            journal["r0_search_mints"] = ["other-mint"]
            rewritten = json.dumps(journal, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
            journal_path.write_bytes(rewritten)
            http_after_crash = len(opener.urls)
            with self.assertRaises(FirstHitError) as raised:
                _run(data_root, staging, opener, clock)
            self.assertEqual(str(raised.exception), REQUEST_SHA256_MISMATCH)
            self.assertEqual(len(opener.urls), http_after_crash)
            self.assertEqual(journal_path.read_bytes(), rewritten)

    def test_current_version_exact_request_crash_resume_is_idempotent(self) -> None:
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
                        raise RuntimeError("crash after first retained search")

            hook = _Hook()
            with self.assertRaises(RuntimeError):
                _run(data_root, staging, opener, clock, search_commit_hook=hook)
            journal = json.loads((staging / "journal.json").read_text(encoding="utf-8"))
            search_hash = journal["observations"]["CHECK:00:SEARCH"]["request_sha256"]
            self.assertEqual(len(search_hash), 64)
            receipt = _run(data_root, staging, opener, clock, search_commit_hook=hook)
            self.assertEqual(receipt["terminal_outcome"], "EARN_ONE_CONFIRMATORY_FRESH_OOS")
            resumed = json.loads((staging / "journal.json").read_text(encoding="utf-8"))
            self.assertEqual(resumed["observations"]["CHECK:00:SEARCH"]["request_sha256"], search_hash)
            self.assertEqual(sum("/tokens/v2/search" in url for url in opener.urls), 1)
            self.assertEqual(resumed["schema"], JOURNAL_SCHEMA)
            self.assertEqual(resumed["schema_version"], JOURNAL_SCHEMA_VERSION)
            self.assertEqual(resumed["r0_event_at"], receipt["r0_event_at"])
            self.assertEqual(resumed["decision_at"], receipt["decision_at"])


if __name__ == "__main__":
    unittest.main()
