from __future__ import annotations

import hashlib
import io
import json
import math
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.early_valuation_liquidity_divergence_confirmation import (  # noqa: E402
    AUTHORITY_PHRASE,
    CLOSE_TERMINAL,
    EARN_TERMINAL,
    FACTORY_RUNNER,
    FACTORY_RUNNER_SHA256,
    INVALID_TERMINAL,
    X_FORMULA,
    project_divergence,
    run_divergence_campaign,
    score_divergence,
    validate_divergence_policy,
)
from solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition import (  # noqa: E402
    OrganicPressureError,
    run_campaign,
)
from scripts.run_early_valuation_liquidity_divergence_confirmation import (  # noqa: E402
    _terminal_from_error,
    run_capture,
)

CONFIG_PATH = ROOT / "configs/early_valuation_liquidity_divergence_confirmation_v1.yaml"


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
        self.current = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
        self.sleeps: list[float] = []

    def now(self) -> datetime:
        return self.current

    def sleep(self, seconds: float) -> None:
        if seconds < 60:
            return
        self.sleeps.append(seconds)
        self.current += timedelta(seconds=seconds)


class _PathOpener:
    def __init__(
        self,
        recent: list[dict[str, Any]],
        search_r0: list[dict[str, Any]],
        search_r1: list[dict[str, Any]],
    ) -> None:
        self.recent = recent
        self.search_r0 = search_r0
        self.search_r1 = search_r1
        self.search_calls = 0
        self.requests: list[object] = []

    def open(self, request: object, timeout: float = 0) -> _Response:
        self.requests.append(request)
        url = str(getattr(request, "full_url"))
        if "/tokens/v2/recent" in url:
            rows = [{"id": "prior", "launchpad": "pump.fun", "mcap": 1.0}, *self.recent]
            return _Response(json.dumps(rows).encode("utf-8"))
        if "/tokens/v2/search" in url:
            self.search_calls += 1
            rows = self.search_r0 if self.search_calls == 1 else self.search_r1
            return _Response(json.dumps(rows).encode("utf-8"))
        if "/swap/v2/order" in url:
            query = url.split("?", 1)[1]
            values = dict(item.split("=", 1) for item in query.split("&"))
            if values["inputMint"] == "So11111111111111111111111111111111111111112":
                index = int(values["outputMint"].split("-")[-1])
                body = {
                    "transaction": None,
                    "requestId": "buy",
                    "inputMint": values["inputMint"],
                    "outputMint": values["outputMint"],
                    "inAmount": values["amount"],
                    "outAmount": str(1000000 + index),
                    "router": "dflow",
                    "mode": "manual",
                }
            else:
                index = int(values["inputMint"].split("-")[-1])
                body = {
                    "transaction": None,
                    "requestId": "sell",
                    "inputMint": values["inputMint"],
                    "outputMint": values["outputMint"],
                    "inAmount": values["amount"],
                    "outAmount": str(10000000 + index * 200000),
                    "router": "dflow",
                    "mode": "manual",
                }
            return _Response(json.dumps(body).encode("utf-8"))
        raise AssertionError(f"unexpected URL: {url}")


def _row(
    index: int,
    *,
    liquidity: float = 2500.0,
    mcap: float = 10000.0,
    created_at: str = "2026-08-24T11:55:00Z",
    updated_at: str = "2026-08-24T12:00:00Z",
) -> dict[str, Any]:
    return {
        "id": f"mint-{index:02d}",
        "launchpad": "pump.fun",
        "liquidity": liquidity,
        "mcap": mcap,
        "fdv": mcap * 2,
        "firstPool": {"createdAt": created_at},
        "updatedAt": updated_at,
    }


class ValuationLiquidityDivergenceTests(unittest.TestCase):
    def test_policy_and_runner_pin(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(policy, dict)
        validate_divergence_policy(policy, root=ROOT)
        self.assertEqual(policy["decision_snapshot"]["x_formula"], X_FORMULA)
        self.assertEqual(policy["external_authority"]["owner_phrase"], AUTHORITY_PHRASE)
        self.assertEqual(policy["decision_rule"]["tau_b_floor"], "forbidden")
        self.assertFalse(policy["decision_rule"]["top_x_quartile"])
        digest = hashlib.sha256((ROOT / FACTORY_RUNNER).read_bytes()).hexdigest()
        self.assertEqual(digest, FACTORY_RUNNER_SHA256)

    def test_transform_is_temporal_not_level(self) -> None:
        t0 = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
        t1 = datetime(2026, 8, 24, 12, 5, tzinfo=UTC)
        recent = _row(0)
        stable_high = project_divergence(
            recent,
            _row(0, liquidity=5000.0, mcap=10000.0, updated_at="2026-08-24T12:00:00Z"),
            _row(0, liquidity=5000.0, mcap=10000.0, updated_at="2026-08-24T12:05:00Z"),
            t0,
            t1,
        )
        self.assertEqual(stable_high["status"], "ELIGIBLE")
        self.assertAlmostEqual(float(stable_high["value"]), 0.0)

        rising = project_divergence(
            recent,
            _row(0, liquidity=2000.0, mcap=10000.0, updated_at="2026-08-24T12:00:00Z"),
            _row(0, liquidity=2600.0, mcap=10000.0, updated_at="2026-08-24T12:05:00Z"),
            t0,
            t1,
        )
        self.assertEqual(rising["status"], "ELIGIBLE")
        self.assertAlmostEqual(float(rising["value"]), math.log(0.26 / 0.2))
        self.assertGreater(float(rising["value"]), float(stable_high["value"]))

    def test_unknown_and_fdv_and_age_gates(self) -> None:
        t0 = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
        t1 = datetime(2026, 8, 24, 12, 5, tzinfo=UTC)
        recent = _row(0)
        missing = dict(_row(0))
        del missing["mcap"]
        unknown = project_divergence(recent, missing, _row(0), t0, t1)
        self.assertNotEqual(unknown["status"], "ELIGIBLE")
        self.assertIsNone(unknown["value"])

        fdv_only = dict(_row(0))
        del fdv_only["mcap"]
        fdv_only["fdv"] = 50000.0
        rejected = project_divergence(recent, fdv_only, _row(0), t0, t1)
        self.assertTrue(rejected.get("substitute_rejected"))
        self.assertIsNone(rejected["value"])

        too_old_r0 = project_divergence(
            recent,
            _row(0, created_at="2026-08-24T11:40:00Z"),
            _row(0, created_at="2026-08-24T11:40:00Z", updated_at="2026-08-24T12:05:00Z"),
            t0,
            t1,
        )
        self.assertEqual(too_old_r0["status"], "TOO_OLD_FOR_CONFIRMATION")

        too_young = project_divergence(
            recent,
            _row(0, created_at="2026-08-24T11:58:00Z", updated_at="2026-08-24T11:59:00Z"),
            _row(0, created_at="2026-08-24T11:58:00Z", updated_at="2026-08-24T12:05:00Z"),
            t0,
            t1,
        )
        self.assertEqual(too_young["status"], "TOO_YOUNG")

        created_at_mismatch = project_divergence(
            recent,
            _row(0, created_at="2026-08-24T11:55:00Z"),
            _row(0, created_at="2026-08-24T11:54:00Z", updated_at="2026-08-24T12:05:00Z"),
            t0,
            t1,
        )
        self.assertEqual(created_at_mismatch.get("reason"), "CREATED_AT_SNAPSHOT_MISMATCH")
        self.assertNotEqual(created_at_mismatch["status"], "ELIGIBLE")
        self.assertIsNone(created_at_mismatch["value"])

        r1_below_floor = project_divergence(
            recent,
            _row(0, liquidity=2000.0, updated_at="2026-08-24T12:00:00Z"),
            _row(0, liquidity=500.0, updated_at="2026-08-24T12:05:00Z"),
            t0,
            t1,
        )
        self.assertEqual(r1_below_floor.get("reason"), "R1_LIQUIDITY_BELOW_ICP_MIN")
        self.assertNotEqual(r1_below_floor["status"], "ELIGIBLE")
        self.assertIsNone(r1_below_floor["value"])

    def test_sign_only_score_does_not_reopen_quartile(self) -> None:
        rows = [
            {"mint": f"m{index}", "x": float(index), "y": float(index), "h900_terminal": "QUOTE_OBSERVED"}
            for index in range(10)
        ]
        earned = score_divergence(rows)
        self.assertEqual(earned["terminal"], EARN_TERMINAL)
        self.assertIsNone(earned["top_quartile_median_y"])
        self.assertGreater(float(earned["tau_b"]), 0)

        closed = score_divergence(
            [
                {"mint": f"m{index}", "x": float(index), "y": float(-index), "h900_terminal": "QUOTE_OBSERVED"}
                for index in range(10)
            ]
        )
        self.assertEqual(closed["terminal"], CLOSE_TERMINAL)
        self.assertLessEqual(float(closed["tau_b"]), 0)

        invalid = score_divergence(rows[:3])
        self.assertEqual(invalid["terminal"], INVALID_TERMINAL)

    def test_wrong_phrase_never_reads_credential(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        reads = {"count": 0}

        def loader() -> str:
            reads["count"] += 1
            return "secret-key"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            excluded = root / "excluded.json"
            excluded.write_text(json.dumps({"mints": ["prior-mint"]}), encoding="utf-8")
            with self.assertRaisesRegex(OrganicPressureError, "AUTHORITY_PHRASE_INVALID"):
                run_capture(
                    authority_phrase="WRONG",
                    excluded_mints_path=excluded,
                    policy=policy,
                    raw_root=root / "raw",
                    receipt_path=root / "receipt.json",
                    credential_loader=loader,
                )
        self.assertEqual(reads["count"], 0)

    def test_typed_stop_maps_to_invalid_evidence_replan(self) -> None:
        self.assertEqual(
            _terminal_from_error(OrganicPressureError("CALL_CAP_EXCEEDED")),
            INVALID_TERMINAL,
        )
        self.assertEqual(
            _terminal_from_error(OrganicPressureError("API_KEY_IN_URL_LOG_RECEIPT_OR_GIT")),
            INVALID_TERMINAL,
        )
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        reads = {"count": 0}

        def loader() -> str:
            reads["count"] += 1
            return "secret-key"

        def boom_preflight(*_args: object, **_kwargs: object) -> dict[str, object]:
            raise OrganicPressureError("CALL_CAP_EXCEEDED")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            excluded = root / "excluded.json"
            excluded.write_text(json.dumps({"mints": ["prior-mint"]}), encoding="utf-8")
            receipt = run_capture(
                authority_phrase=AUTHORITY_PHRASE,
                excluded_mints_path=excluded,
                policy=policy,
                raw_root=root / "raw",
                receipt_path=root / "receipt.json",
                credential_loader=loader,
                preflight_fn=boom_preflight,
            )
        self.assertEqual(receipt.get("terminal_outcome"), INVALID_TERMINAL)
        self.assertEqual(receipt.get("terminal_error_code"), "CALL_CAP_EXCEEDED")
        self.assertEqual(reads["count"], 0)

    def test_mocked_two_snapshot_campaign_does_not_call_run_campaign(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        recent = [_row(index, created_at="2026-08-24T12:00:00Z") for index in range(24)]
        search_r0 = [
            _row(
                index,
                liquidity=2000.0,
                mcap=10000.0,
                created_at="2026-08-24T12:00:00Z",
                updated_at="2026-08-24T12:05:00Z",
            )
            for index in range(24)
        ]
        search_r1 = [
            _row(
                index,
                liquidity=2000.0 + 40.0 * index,
                mcap=10000.0,
                created_at="2026-08-24T12:00:00Z",
                updated_at="2026-08-24T12:10:00Z",
            )
            for index in range(24)
        ]
        clock = _Clock()
        opener = _PathOpener(recent, search_r0, search_r1)
        calls = {"run_campaign": 0}
        original = run_campaign

        def wrapped(*args: object, **kwargs: object) -> object:
            calls["run_campaign"] += 1
            return original(*args, **kwargs)

        import solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition as organic

        organic.run_campaign = wrapped  # type: ignore[method-assign]
        self.addCleanup(lambda: setattr(organic, "run_campaign", original))
        receipt = run_divergence_campaign(
            policy,
            authority_phrase=AUTHORITY_PHRASE,
            reservation={"state": "STARTED", "credential_reads": 0},
            excluded_mints={"prior"},
            credential_loader=lambda: "test-key",
            preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0, "provider_requests": 0},
            opener=opener,
            clock=clock.now,
            sleeper=clock.sleep,
            monotonic_clock=lambda: 0.0,
        )
        self.assertEqual(opener.search_calls, 2)
        self.assertEqual(calls["run_campaign"], 0)
        self.assertIn(300.0, clock.sleeps)
        observations = receipt.get("candidate_observations") or []
        eligible = [row for row in observations if row.get("x_status") == "ELIGIBLE"]
        self.assertGreaterEqual(len(eligible), 10)
        sample = next(row for row in eligible if row.get("mint") == "mint-10")
        self.assertAlmostEqual(float(sample["x"]), math.log((2000.0 + 400.0) / 2000.0))
        stable = next(row for row in eligible if row.get("mint") == "mint-00")
        self.assertAlmostEqual(float(stable["x"]), 0.0)
        self.assertEqual(receipt.get("terminal_outcome"), EARN_TERMINAL)
        self.assertEqual(receipt.get("score", {}).get("score_kind"), "SIGN_ONLY_KENDALL_TAU_B")


if __name__ == "__main__":
    unittest.main()
