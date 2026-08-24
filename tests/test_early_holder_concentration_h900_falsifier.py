from __future__ import annotations

import hashlib
import io
import json
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

from solana_alpha_lab.early_holder_concentration_h900_falsifier import (  # noqa: E402
    AUTHORITY_PHRASE,
    CLOSE_TERMINAL,
    EARN_TERMINAL,
    FACTORY_RUNNER,
    FACTORY_RUNNER_SHA256,
    INVALID_TERMINAL,
    X_FORMULA,
    project_holder_concentration,
    run_holder_concentration_campaign,
    validate_holder_concentration_policy,
)
from solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition import (  # noqa: E402
    OrganicPressureError,
)
from scripts.run_early_holder_concentration_h900_falsifier import (  # noqa: E402
    run_capture,
)

CONFIG_PATH = ROOT / "configs/early_holder_concentration_h900_falsifier_v1.yaml"
MODULE_PATH = ROOT / "src/solana_alpha_lab/early_holder_concentration_h900_falsifier.py"


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
    def __init__(self, recent: list[dict[str, Any]], search: list[dict[str, Any]]) -> None:
        self.recent = recent
        self.search = search
        self.requests: list[object] = []

    def open(self, request: object, timeout: float = 0) -> _Response:
        self.requests.append(request)
        url = str(getattr(request, "full_url"))
        if "/tokens/v2/recent" in url:
            rows = [{"id": "prior", "launchpad": "pump.fun", "mcap": 1.0}, *self.recent]
            return _Response(json.dumps(rows).encode("utf-8"))
        if "/tokens/v2/search" in url:
            return _Response(json.dumps(self.search).encode("utf-8"))
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
                    "outAmount": str(10000000 + index * 100000),
                    "router": "dflow",
                    "mode": "manual",
                }
            return _Response(json.dumps(body).encode("utf-8"))
        raise AssertionError(f"unexpected URL: {url}")


def _row(
    index: int,
    *,
    top_holders: float | None = None,
    liquidity: float = 2500.0,
    created_at: str = "2026-08-24T11:55:00Z",
    updated_at: str = "2026-08-24T12:05:00Z",
    include_audit: bool = True,
) -> dict[str, Any]:
    if top_holders is None:
        top_holders = float(index)
    row: dict[str, Any] = {
        "id": f"mint-{index:02d}",
        "launchpad": "pump.fun",
        "liquidity": liquidity,
        "firstPool": {"createdAt": created_at},
        "updatedAt": updated_at,
    }
    if include_audit:
        row["audit"] = {"topHoldersPercentage": top_holders}
    return row


class HolderConcentrationFalsifierTests(unittest.TestCase):
    def test_policy_phrase_and_runner_pin(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(policy, dict)
        validate_holder_concentration_policy(policy, root=ROOT)
        self.assertEqual(policy["decision_snapshot"]["x_formula"], X_FORMULA)
        self.assertEqual(policy["external_authority"]["owner_phrase"], AUTHORITY_PHRASE)
        self.assertNotIn("tau_b_floor", policy["decision_rule"])
        digest = hashlib.sha256((ROOT / FACTORY_RUNNER).read_bytes()).hexdigest()
        self.assertEqual(digest, FACTORY_RUNNER_SHA256)

    def test_wrapper_does_not_duplicate_campaign_runtime(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("perform_credentialed_get", source)
        self.assertNotIn("build_search_url", source)
        self.assertNotIn("ORDER_ENDPOINT", source)
        self.assertNotIn("RECENT_ENDPOINT", source)
        self.assertNotIn("time.sleep", source)
        self.assertEqual(source.count("run_campaign("), 1)
        self.assertIn("score_fn=score_holder_campaign", source)

    def test_x_absent_is_missing_never_zero(self) -> None:
        observed_at = datetime(2026, 8, 24, 12, 5, tzinfo=UTC)
        recent = _row(0, top_holders=12.5)
        absent = dict(recent)
        del absent["audit"]
        missing = project_holder_concentration(recent, absent, observed_at)
        self.assertEqual(missing["status"], "MISSING")
        self.assertIsNone(missing["value"])
        self.assertEqual(missing["reason"], "TOP_HOLDERS_PERCENTAGE_ABSENT")

        none_audit = dict(recent)
        none_audit["audit"] = {"topHoldersPercentage": None}
        none_missing = project_holder_concentration(recent, none_audit, observed_at)
        self.assertEqual(none_missing["status"], "MISSING")
        self.assertIsNone(none_missing["value"])

        zero = project_holder_concentration(recent, _row(0, top_holders=0.0), observed_at)
        self.assertEqual(zero["status"], "ELIGIBLE")
        self.assertEqual(zero["value"], 0.0)

    def test_x_range_predicate_age_and_liquidity(self) -> None:
        observed_at = datetime(2026, 8, 24, 12, 5, tzinfo=UTC)
        recent = _row(0, top_holders=62.5)
        ok = project_holder_concentration(recent, _row(0, top_holders=62.5), observed_at)
        self.assertEqual(ok["status"], "ELIGIBLE")
        self.assertEqual(ok["value"], 62.5)

        high = project_holder_concentration(recent, _row(0, top_holders=100.1), observed_at)
        self.assertEqual(high["status"], "MISSING")
        self.assertEqual(high["reason"], "TOP_HOLDERS_PERCENTAGE_OUT_OF_RANGE")

        boolean = dict(_row(0, top_holders=1.0))
        boolean["audit"] = {"topHoldersPercentage": True}
        invalid = project_holder_concentration(recent, boolean, observed_at)
        self.assertEqual(invalid["status"], "MISSING")
        self.assertEqual(invalid["reason"], "TOP_HOLDERS_PERCENTAGE_INVALID")

        too_young = project_holder_concentration(
            recent,
            _row(0, created_at="2026-08-24T12:03:00Z", updated_at="2026-08-24T12:04:00Z"),
            observed_at,
        )
        self.assertEqual(too_young["status"], "TOO_YOUNG")

        too_old = project_holder_concentration(
            recent,
            _row(0, created_at="2026-08-24T11:40:00Z", updated_at="2026-08-24T12:05:00Z"),
            observed_at,
        )
        self.assertEqual(too_old["status"], "TOO_OLD")

        future_pool = project_holder_concentration(
            recent,
            _row(0, created_at="2026-08-24T12:10:00Z", updated_at="2026-08-24T12:10:00Z"),
            observed_at,
        )
        self.assertEqual(future_pool["status"], "MISSING")
        self.assertEqual(future_pool["reason"], "FIRST_POOL_TIMESTAMP_IN_FUTURE")

        future_updated = project_holder_concentration(
            recent,
            _row(0, created_at="2026-08-24T11:55:00Z", updated_at="2026-08-24T12:06:00Z"),
            observed_at,
        )
        self.assertEqual(future_updated["status"], "MISSING")
        self.assertEqual(future_updated["reason"], "UPDATED_TIMESTAMP_IN_FUTURE")

        low_liq = project_holder_concentration(recent, _row(0, liquidity=500.0), observed_at)
        self.assertEqual(low_liq["status"], "MISSING")
        self.assertEqual(low_liq["reason"], "LIQUIDITY_BELOW_ICP_MIN")

    def test_legacy_decision_keys_are_rejected(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(policy, dict)
        policy["decision_rule"]["tau_b_floor"] = "0.20"
        with self.assertRaisesRegex(OrganicPressureError, "LEGACY_DECISION_KEY_FORBIDDEN:tau_b_floor"):
            validate_holder_concentration_policy(policy, root=ROOT)

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

    def test_mocked_negative_association_earns_and_positive_closes(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        earn_recent = [_row(index, top_holders=60.0 - index) for index in range(24)]
        earn_search = [_row(index, top_holders=60.0 - index) for index in range(24)]
        clock = _Clock()
        earn_receipt = run_holder_concentration_campaign(
            policy,
            authority_phrase=AUTHORITY_PHRASE,
            reservation={"state": "STARTED", "credential_reads": 0},
            excluded_mints={"prior"},
            credential_loader=lambda: "test-key",
            preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0, "provider_requests": 0},
            opener=_PathOpener(earn_recent, earn_search),
            clock=clock.now,
            sleeper=clock.sleep,
            monotonic_clock=lambda: 0.0,
        )
        self.assertEqual(earn_receipt["provider_requests"], 50)
        self.assertEqual(earn_receipt["decision_time_eligible"], 24)
        self.assertLess(earn_receipt["score"]["tau_b"], 0)
        self.assertEqual(earn_receipt["terminal_outcome"], EARN_TERMINAL)

        close_recent = [_row(index, top_holders=float(index)) for index in range(24)]
        close_search = [_row(index, top_holders=float(index)) for index in range(24)]
        close_clock = _Clock()
        close_receipt = run_holder_concentration_campaign(
            policy,
            authority_phrase=AUTHORITY_PHRASE,
            reservation={"state": "STARTED", "credential_reads": 0},
            excluded_mints={"prior"},
            credential_loader=lambda: "test-key",
            preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0, "provider_requests": 0},
            opener=_PathOpener(close_recent, close_search),
            clock=close_clock.now,
            sleeper=close_clock.sleep,
            monotonic_clock=lambda: 0.0,
        )
        self.assertGreaterEqual(close_receipt["score"]["tau_b"], 0)
        self.assertEqual(close_receipt["terminal_outcome"], CLOSE_TERMINAL)

    def test_early_yield_uses_invalid_evidence_replan(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        recent = [_row(index, include_audit=False) for index in range(24)]
        search = [_row(index, include_audit=False) for index in range(24)]
        clock = _Clock()
        receipt = run_holder_concentration_campaign(
            policy,
            authority_phrase=AUTHORITY_PHRASE,
            reservation={"state": "STARTED", "credential_reads": 0},
            excluded_mints={"prior"},
            credential_loader=lambda: "test-key",
            preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0, "provider_requests": 0},
            opener=_PathOpener(recent, search),
            clock=clock.now,
            sleeper=clock.sleep,
            monotonic_clock=lambda: 0.0,
        )
        self.assertEqual(receipt["terminal_outcome"], INVALID_TERMINAL)
        self.assertEqual(receipt["decision_time_eligible"], 0)
        self.assertLess(receipt["provider_requests"], 10)

    def test_short_frozen_cohort_is_invalid_evidence_replan_not_yield(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        recent = [_row(index) for index in range(10)]
        search = [_row(index) for index in range(10)]
        clock = _Clock()
        receipt = run_holder_concentration_campaign(
            policy,
            authority_phrase=AUTHORITY_PHRASE,
            reservation={"state": "STARTED", "credential_reads": 0},
            excluded_mints={"prior"},
            credential_loader=lambda: "test-key",
            preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0, "provider_requests": 0},
            opener=_PathOpener(recent, search),
            clock=clock.now,
            sleeper=clock.sleep,
            monotonic_clock=lambda: 0.0,
        )
        self.assertEqual(receipt["terminal_outcome"], INVALID_TERMINAL)
        self.assertNotEqual(receipt["terminal_outcome"], "INVALID_EVIDENCE_YIELD")

    def test_cli_blocks_non_close_non_earn_terminals(self) -> None:
        from scripts.run_early_holder_concentration_h900_falsifier import owner_exit_blocked

        self.assertFalse(owner_exit_blocked(CLOSE_TERMINAL))
        self.assertFalse(owner_exit_blocked(EARN_TERMINAL))
        self.assertTrue(owner_exit_blocked(INVALID_TERMINAL))
        self.assertTrue(owner_exit_blocked("INVALID_EVIDENCE_YIELD"))


if __name__ == "__main__":
    unittest.main()
