from __future__ import annotations

import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

from pathrisk_live_testkit import (
    ACT_002,
    ACT_003,
    ensure_act002_below_floor,
    live_identity_kwargs,
    successor_identity,
    successor_phrase,
)
from solana_alpha_lab.factory.observation_schedule_runtime import JupiterReadonlyOpener
from solana_alpha_lab.factory.pathrisk_live import (
    CREDENTIAL_ENV_NAME,
    ControllableClock,
    FixtureWindowOpener,
    PathRiskLiveError,
    SOL_MINT,
    SystemClock,
    TERMINAL_CREDENTIAL_MISSING,
    count_url_kinds,
    materialize_runtime_schedule,
    run_live_window as _run_live_window,
)
from solana_alpha_lab.factory.pathrisk_calibration import (
    TERMINAL_BELOW_FLOOR,
    TERMINAL_INFORMATIVE,
    TERMINAL_PARTIAL,
    load_policy,
)
from solana_alpha_lab.factory.observation_schedule import render_utc

GIT_SHA = "c" * 40
MAIN_SHA = "b" * 40
NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
MINTS = (
    "MintA111111111111111111111111111111111111111",
    "MintB111111111111111111111111111111111111111",
    "MintC111111111111111111111111111111111111111",
    "MintD111111111111111111111111111111111111111",
)


def _phrase() -> str:
    return successor_phrase()


def run_live_window(**kwargs):
    kwargs.setdefault("activation_id", ACT_003)
    kwargs.setdefault("predecessor_activation_id", ACT_002)
    if kwargs.get("owner_phrase") != "wrong":
        ensure_act002_below_floor(Path(kwargs["data_root"]))
    return _run_live_window(**kwargs)


def _row(mint: str, *, created: datetime, liquidity: str = "2000") -> dict:
    stamp = render_utc(created)
    return {
        "id": mint,
        "liquidity": liquidity,
        "firstPool": {"createdAt": stamp, "source": "pump.fun"},
        "first_seen_at": stamp,
    }


def _offsets() -> tuple[datetime, ...]:
    return tuple(NOW - timedelta(seconds=300 + (index * 20)) for index in range(4))


def _fixture(mints=MINTS, created_at: datetime | None = None) -> dict:
    anchors = _offsets() if created_at is None else (created_at,) * len(mints)
    return {
        "recent": [{"id": mint} for mint in mints],
        "search": [_row(mint, created=anchor) for mint, anchor in zip(mints, anchors, strict=False)],
    }


class CountingEnv(dict):
    def __init__(self) -> None:
        super().__init__()
        self.reads = 0

    def get(self, key, default=None):  # type: ignore[override]
        self.reads += 1
        return super().get(key, default)


class ClockRecordingOpener(FixtureWindowOpener):
    def __init__(self, fixture: dict, clock: ControllableClock) -> None:
        super().__init__(fixture)
        self.clock = clock
        self.h900_at: list[tuple[str, datetime]] = []

    def open(self, url: str) -> dict:
        result = super().open(url)
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        input_mint = (query.get("inputMint") or [""])[0]
        amount = (query.get("amount") or [""])[0]
        if parsed.path == "/swap/v2/order" and input_mint and input_mint != SOL_MINT:
            key = (input_mint, amount)
            if self.sell_counts.get(key, 0) >= 2:
                self.h900_at.append((input_mint, self.clock()))
        return result


class PathRiskWallclockLiveTests(unittest.TestCase):
    def test_t1_production_cli_exists_without_mandatory_fixture(self) -> None:
        script = (ROOT / "scripts" / "early_quote_surface_pathrisk_calibration.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("--real-provider", script)
        self.assertIn("required=True", script)
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts" / "early_quote_surface_pathrisk_calibration.py"),
                "live-preflight",
                "--main-sha",
                MAIN_SHA,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["credential_env_name"], "JUPITER_API_KEY")
        self.assertIs(payload["fake_fixture_required"], False)
        self.assertIs(payload["dotenv_read"], False)

    def test_t2_production_mode_rejects_fake_fixture(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts" / "early_quote_surface_pathrisk_calibration.py"),
                "live-run",
                "--main-sha",
                MAIN_SHA,
                "--owner-phrase",
                _phrase(),
                "--data-root",
                str(ROOT / "local" / "tmp_unused_rdp"),
                    "--producer-git-sha",
                GIT_SHA,
                "--activation-id",
                ACT_003,
                "--predecessor-activation-id",
                ACT_002,
                "--real-provider",
                "--fake-provider-fixture",
                "tests/fixtures/observation_schedule/pathrisk_live_window.yaml",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)

    def test_t2b_production_rejects_now_override(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts" / "early_quote_surface_pathrisk_calibration.py"),
                "live-run",
                "--main-sha",
                MAIN_SHA,
                "--owner-phrase",
                _phrase(),
                "--data-root",
                str(ROOT / "local" / "tmp_unused_rdp"),
                    "--producer-git-sha",
                GIT_SHA,
                "--activation-id",
                ACT_003,
                "--predecessor-activation-id",
                ACT_002,
                "--real-provider",
                "--now",
                "2026-08-31T12:00:00Z",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("NOW_OVERRIDE_FORBIDDEN_IN_PRODUCTION", completed.stderr + completed.stdout)

    def test_t2c_production_rejects_stop_after(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts" / "early_quote_surface_pathrisk_calibration.py"),
                "live-run",
                "--main-sha",
                MAIN_SHA,
                "--owner-phrase",
                _phrase(),
                "--data-root",
                str(ROOT / "local" / "tmp_unused_rdp"),
                    "--producer-git-sha",
                GIT_SHA,
                "--activation-id",
                ACT_003,
                "--predecessor-activation-id",
                ACT_002,
                "--real-provider",
                "--stop-after",
                "after_t0",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("STOP_AFTER_FORBIDDEN_IN_PRODUCTION", completed.stderr + completed.stdout)

    def test_t3_fixture_mode_never_constructs_real_opener(self) -> None:
        script = (ROOT / "scripts" / "early_quote_surface_pathrisk_calibration.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("FixtureWindowOpener", script)
        self.assertIn("if args.real_provider", script)
        self.assertNotIn("JupiterReadonlyOpener(fixture", script)

    def test_t4_phrase_mismatch_reads_no_credential(self) -> None:
        env = CountingEnv()
        env["JUPITER_API_KEY"] = "not-a-real-key"
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            with self.assertRaisesRegex(PathRiskLiveError, "OWNER_PHRASE_MISMATCH"):
                run_live_window(
                    root=ROOT,
                    data_root=Path(tmp) / "rdp",
                    opener=None,
                    producer_git_sha=GIT_SHA,
                    owner_phrase="wrong",
                    main_sha=MAIN_SHA,
                    production=True,
                    clock=ControllableClock(NOW),
                    environ=env,
                )
        self.assertEqual(env.reads, 0)

    def test_t5_missing_credential_after_authority(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            result = run_live_window(
                root=ROOT,
                data_root=Path(tmp) / "rdp",
                opener=None,
                producer_git_sha=GIT_SHA,
                owner_phrase=_phrase(),
                main_sha=MAIN_SHA,
                production=True,
                clock=ControllableClock(NOW),
                environ={},
            )
        self.assertEqual(result["terminal"], TERMINAL_CREDENTIAL_MISSING)
        self.assertEqual(result["provider_calls"], 0)
        self.assertEqual(result["quote_calls"], 0)

    def test_t6_real_opener_header_only(self) -> None:
        captured: dict[str, object] = {}

        class _Response:
            status = 200

            def read(self) -> bytes:
                return b'{"outAmount":"1"}'

            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> None:
                return None

        def _open(request, timeout=20.0):  # noqa: ARG001
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            headers = {
                key.lower(): value for key, value in request.header_items()
            }
            captured["header"] = headers.get("x-api-key")
            return _Response()

        opener = JupiterReadonlyOpener("TEST_KEY_NOT_A_SECRET")
        with patch.object(opener._http, "open", side_effect=_open):
            opener.open("https://api.jup.ag/swap/v2/order?inputMint=x")
        self.assertEqual(captured["method"], "GET")
        self.assertNotIn("TEST_KEY_NOT_A_SECRET", str(captured["url"]))
        self.assertNotIn("api-key=", str(captured["url"]).lower())
        self.assertEqual(captured["header"], "TEST_KEY_NOT_A_SECRET")

    def test_t7_no_dotenv_path(self) -> None:
        live = (ROOT / "src" / "solana_alpha_lab" / "factory" / "pathrisk_live.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("load_dotenv", live)
        self.assertNotIn("from dotenv", live)
        self.assertNotIn('Path(".env")', live)
        self.assertNotIn("Path('.env')", live)
        cli = (ROOT / "scripts" / "early_quote_surface_pathrisk_calibration.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("load_dotenv", cli)
        self.assertNotIn("from dotenv", cli)
        self.assertNotIn('Path(".env")', cli)
        self.assertIn("dotenv_read", cli)

    def test_t8_system_clock_cannot_advance(self) -> None:
        self.assertFalse(hasattr(SystemClock(), "advance"))

    def test_t9_t10_t11_t20_h900_per_mint_after_due(self) -> None:
        created = _offsets()
        fixture = {
            "recent": [{"id": mint} for mint in MINTS],
            "search": [_row(mint, created=stamp) for mint, stamp in zip(MINTS, created, strict=True)],
        }
        clock = ControllableClock(NOW)
        opener = ClockRecordingOpener(fixture, clock)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            result = run_live_window(
                root=ROOT,
                data_root=Path(tmp) / "rdp",
                opener=opener,
                producer_git_sha=GIT_SHA,
                owner_phrase=_phrase(),
                main_sha=MAIN_SHA,
                clock=clock,
                production=False,
            )
            dues = {mint: stamp + timedelta(seconds=900) for mint, stamp in zip(MINTS, created, strict=True)}
            self.assertEqual(len(set(dues.values())), 4)
            self.assertTrue(opener.h900_at)
            observed_mints = {mint for mint, _ in opener.h900_at}
            self.assertEqual(observed_mints, set(MINTS))
            for mint, observed in opener.h900_at:
                due = dues[mint]
                self.assertGreaterEqual(observed, due)
                self.assertLessEqual(observed, due + timedelta(seconds=120))
            yaml_text = (
                Path(tmp)
                / "rdp"
                / "pathrisk_live"
                / ACT_003
                / "runtime_schedule.yaml"
            ).read_text(encoding="utf-8")
            self.assertNotIn("2026-09-01T00:00:00Z", yaml_text)
            self.assertIn("2026-08-31T12:00:00Z", yaml_text)
            self.assertIn("enabled: false", yaml_text)
            self.assertEqual(result["recent_calls"], 1)
            self.assertEqual(result["search_calls"], 1)
            self.assertTrue(result["build_readout_live_wired"])
            self.assertIn("NO_ALPHA", result["non_claims"])
            self.assertIs(result["git_mutated"], False)
            self.assertEqual(result["terminal"], TERMINAL_INFORMATIVE)

    def test_t10_late_h900_is_typed_missing_not_backdated(self) -> None:
        created = _offsets()
        fixture = {
            "recent": [{"id": mint} for mint in MINTS],
            "search": [_row(mint, created=stamp) for mint, stamp in zip(MINTS, created, strict=True)],
        }
        opener = FixtureWindowOpener(fixture)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            after_t0 = run_live_window(
                root=ROOT,
                data_root=data_root,
                opener=opener,
                producer_git_sha=GIT_SHA,
                owner_phrase=_phrase(),
                main_sha=MAIN_SHA,
                clock=ControllableClock(NOW),
                stop_after="after_t0",
                production=False,
            )
            quotes_before = after_t0["quote_calls"]
            late = run_live_window(
                root=ROOT,
                data_root=data_root,
                opener=opener,
                producer_git_sha=GIT_SHA,
                owner_phrase=_phrase(),
                main_sha=MAIN_SHA,
                clock=ControllableClock(NOW + timedelta(seconds=800)),
                production=False,
            )
            quote_urls = [url for url in opener.urls if "/swap/v2/order" in url]
            self.assertEqual(len(quote_urls), quotes_before)
            self.assertEqual(late["terminal"], TERMINAL_PARTIAL)

    def test_t12_t13_t14_crash_resume_wait(self) -> None:
        created = _offsets()
        fixture = {
            "recent": [{"id": mint} for mint in MINTS],
            "search": [_row(mint, created=stamp) for mint, stamp in zip(MINTS, created, strict=True)],
        }
        opener = FixtureWindowOpener(fixture)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            after_t0 = run_live_window(
                root=ROOT,
                data_root=data_root,
                opener=opener,
                producer_git_sha=GIT_SHA,
                owner_phrase=_phrase(),
                main_sha=MAIN_SHA,
                clock=ControllableClock(NOW),
                stop_after="after_t0",
                production=False,
            )
            before = len(opener.urls)
            resumed = run_live_window(
                root=ROOT,
                data_root=data_root,
                opener=opener,
                producer_git_sha=GIT_SHA,
                owner_phrase=_phrase(),
                main_sha=MAIN_SHA,
                clock=ControllableClock(NOW),
                production=False,
            )
            self.assertEqual(count_recent_search(opener.urls)["recent"], 1)
            self.assertEqual(count_recent_search(opener.urls)["search"], 1)
            kinds = count_url_kinds(opener.urls)
            self.assertGreater(kinds["quotes"], after_t0["quote_calls"])
            self.assertLessEqual(kinds["total"], 26)
            self.assertLessEqual(len(opener.urls), 26)
            self.assertGreaterEqual(len(opener.urls), before)

    def test_t15_t16_runtime_schedule_uses_supplied_clock(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            first = materialize_runtime_schedule(ROOT, data_root, NOW, successor_identity())
            second = materialize_runtime_schedule(
                ROOT, data_root, NOW + timedelta(hours=1), successor_identity()
            )
            self.assertEqual(first["schedule_sha256"], second["schedule_sha256"])
            self.assertEqual(first["activation"]["starts_at"], "2026-08-31T12:00:00Z")
            self.assertNotEqual(first["activation"]["starts_at"], "2026-09-01T00:00:00Z")

    def test_t18_ineligible_mint_never_quoted(self) -> None:
        late = NOW - timedelta(seconds=800)
        fresh = NOW - timedelta(seconds=300)
        mints = (*MINTS[:3], "MintLate11111111111111111111111111111111111")
        created = (fresh, fresh - timedelta(seconds=20), fresh - timedelta(seconds=40), late)
        fixture = {
            "recent": [{"id": mint} for mint in mints],
            "search": [_row(mint, created=stamp) for mint, stamp in zip(mints, created, strict=True)],
        }
        opener = FixtureWindowOpener(fixture)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            result = run_live_window(
                root=ROOT,
                data_root=Path(tmp) / "rdp",
                opener=opener,
                producer_git_sha=GIT_SHA,
                owner_phrase=_phrase(),
                main_sha=MAIN_SHA,
                clock=ControllableClock(NOW),
                production=False,
            )
            self.assertNotIn("MintLate11111111111111111111111111111111111", result["selected_mints"])
            self.assertFalse(any("MintLate" in url for url in result["urls"] if "/swap/v2/order" in url))

    def test_t19_below_floor_reports_discovery_calls(self) -> None:
        fresh = NOW - timedelta(seconds=300)
        fixture = {
            "recent": [{"id": mint} for mint in MINTS[:3]],
            "search": [_row(mint, created=fresh) for mint in MINTS[:3]],
        }
        opener = FixtureWindowOpener(fixture)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            result = run_live_window(
                root=ROOT,
                data_root=Path(tmp) / "rdp",
                opener=opener,
                producer_git_sha=GIT_SHA,
                owner_phrase=_phrase(),
                main_sha=MAIN_SHA,
                clock=ControllableClock(NOW),
                production=False,
            )
            self.assertEqual(result["terminal"], TERMINAL_BELOW_FLOOR)
            self.assertEqual(result["quote_calls"], 0)
            self.assertEqual(result["provider_calls"], 2)
            self.assertEqual(result["discovery_calls"], 2)

    def test_t21_production_path_does_not_construct_frozen_clock(self) -> None:
        import solana_alpha_lab.factory.pathrisk_live as module

        source = inspect.getsource(module.run_live_window)
        self.assertNotIn("FrozenClock(", source)

    def test_t22_t23_t24_source_safety(self) -> None:
        self.assertEqual(CREDENTIAL_ENV_NAME, "JUPITER_API_KEY")
        self.assertNotEqual(CREDENTIAL_ENV_NAME, "JUPITER_FREE_API_KEY")
        live = inspect.getsource(run_live_window)
        self.assertNotIn("capture_authorized: true", live)


def count_recent_search(urls: list[str]) -> dict[str, int]:
    return {
        "recent": sum(1 for url in urls if "/tokens/v2/recent" in url),
        "search": sum(1 for url in urls if "/tokens/v2/search" in url),
    }


if __name__ == "__main__":
    unittest.main()
