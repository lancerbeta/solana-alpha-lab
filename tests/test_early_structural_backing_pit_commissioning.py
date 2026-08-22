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

from solana_alpha_lab.early_structural_backing_pit_commissioning import (  # noqa: E402
    AUTHORITY_PHRASE,
    CLOSE_TERMINAL,
    EARN_SHADOW,
    FACTORY_RUNNER,
    FACTORY_RUNNER_SHA256,
    X_FORMULA,
    decide_family,
    project_structural_backing,
    run_structural_backing_campaign,
    validate_structural_backing_policy,
)
from solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition import (  # noqa: E402
    OrganicPressureError,
)
from scripts.run_early_structural_backing_pit_commissioning import (  # noqa: E402
    run_capture,
)

CONFIG_PATH = ROOT / "configs/early_structural_backing_pit_commissioning_v1.yaml"


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
        self.current = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
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
    liquidity: float = 2500.0,
    mcap: float = 10000.0,
    created_at: str = "2026-08-22T11:55:00Z",
    updated_at: str = "2026-08-22T12:05:00Z",
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


class StructuralBackingPitTests(unittest.TestCase):
    def test_policy_and_runner_pin(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(policy, dict)
        validate_structural_backing_policy(policy, root=ROOT)
        self.assertEqual(policy["decision_snapshot"]["x_formula"], X_FORMULA)
        self.assertEqual(policy["external_authority"]["owner_phrase"], AUTHORITY_PHRASE)
        digest = hashlib.sha256((ROOT / FACTORY_RUNNER).read_bytes()).hexdigest()
        self.assertEqual(digest, FACTORY_RUNNER_SHA256)
        self.assertEqual(policy["factory_runner_sha256"], FACTORY_RUNNER_SHA256)

    def test_bind_liquidity_over_mcap_rejects_fdv_and_unknown(self) -> None:
        observed_at = datetime(2026, 8, 22, 12, 5, tzinfo=UTC)
        recent = _row(0)
        t5 = _row(0, liquidity=2000.0, mcap=10000.0)
        ok = project_structural_backing(recent, t5, observed_at)
        self.assertEqual(ok["status"], "ELIGIBLE")
        self.assertEqual(ok["value"], 0.2)

        missing = dict(t5)
        del missing["mcap"]
        unknown = project_structural_backing(recent, missing, observed_at)
        self.assertEqual(unknown["status"], "MISSING")
        self.assertIsNone(unknown["value"])

        zero = project_structural_backing(recent, _row(0, mcap=0.0), observed_at)
        self.assertEqual(zero["status"], "MISSING")
        self.assertIsNone(zero["value"])

        fdv_only = dict(t5)
        del fdv_only["mcap"]
        fdv_only["fdv"] = 50000.0
        rejected = project_structural_backing(recent, fdv_only, observed_at)
        self.assertEqual(rejected["status"], "MISSING")
        self.assertTrue(rejected.get("substitute_rejected"))
        self.assertIsNone(rejected["value"])

    def test_icp_age_and_liquidity_gates(self) -> None:
        observed_at = datetime(2026, 8, 22, 12, 5, tzinfo=UTC)
        recent = _row(0)
        too_young = project_structural_backing(
            recent,
            _row(0, created_at="2026-08-22T12:03:00Z", updated_at="2026-08-22T12:04:00Z"),
            observed_at,
        )
        self.assertEqual(too_young["status"], "TOO_YOUNG")

        too_old = project_structural_backing(
            recent,
            _row(0, created_at="2026-08-22T11:40:00Z", updated_at="2026-08-22T12:05:00Z"),
            observed_at,
        )
        self.assertEqual(too_old["status"], "TOO_OLD")

        low_liq = project_structural_backing(recent, _row(0, liquidity=500.0), observed_at)
        self.assertEqual(low_liq["status"], "MISSING")
        self.assertEqual(low_liq["reason"], "LIQUIDITY_BELOW_ICP_MIN")

    def test_decide_family_window_rules(self) -> None:
        close_a = decide_family({"terminal": CLOSE_TERMINAL, "score": {"terminal": CLOSE_TERMINAL, "tau_b": -0.1}})
        self.assertEqual(close_a["family_decision"], CLOSE_TERMINAL)
        self.assertFalse(close_a["window_b_required"])

        need_b = decide_family({"terminal": "EARN_FRESH_OOS", "score": {"terminal": "EARN_FRESH_OOS", "tau_b": 0.3}})
        self.assertEqual(need_b["family_decision"], "RUN_WINDOW_B")
        self.assertTrue(need_b["window_b_required"])

        earn = decide_family(
            {"terminal": "EARN_FRESH_OOS", "score": {"terminal": "EARN_FRESH_OOS", "tau_b": 0.3}},
            {"terminal": "EARN_FRESH_OOS", "score": {"terminal": "EARN_FRESH_OOS", "tau_b": 0.25}},
        )
        self.assertEqual(earn["family_decision"], EARN_SHADOW)

        flip = decide_family(
            {"terminal": "EARN_FRESH_OOS", "score": {"terminal": "EARN_FRESH_OOS", "tau_b": 0.3}},
            {"terminal": CLOSE_TERMINAL, "score": {"terminal": CLOSE_TERMINAL, "tau_b": -0.2}},
        )
        self.assertEqual(flip["family_decision"], CLOSE_TERMINAL)

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
                    window="A",
                    policy=policy,
                    raw_root=root / "raw",
                    receipt_path=root / "receipt.json",
                    credential_loader=loader,
                )
        self.assertEqual(reads["count"], 0)

    def test_mocked_campaign_projects_x_and_skips_non_eligible(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        recent = [_row(index, mcap=10000.0 + 100.0 * index) for index in range(24)]
        search = []
        for index in range(24):
            row = _row(index, liquidity=2500.0 + 10.0 * index, mcap=10000.0 + 100.0 * index)
            if index == 0:
                del row["mcap"]
                row["fdv"] = 99999.0
            search.append(row)
        clock = _Clock()
        opener = _PathOpener(recent, search)
        receipt = run_structural_backing_campaign(
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
        observations = receipt.get("candidate_observations") or receipt.get("observations") or []
        self.assertTrue(observations)
        missing = [row for row in observations if row.get("mint") == "mint-00"]
        if missing:
            self.assertNotEqual(missing[0].get("x_status"), "ELIGIBLE")
            self.assertIsNone(missing[0].get("x"))


if __name__ == "__main__":
    unittest.main()
