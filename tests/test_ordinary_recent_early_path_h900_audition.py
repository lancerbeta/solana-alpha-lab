from __future__ import annotations

import json
import io
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

from solana_alpha_lab.ordinary_recent_early_path_h900_audition import (  # noqa: E402
    AUTHORITY_PHRASE,
    CLOSE_TERMINAL,
    X_FORMULA,
    project_early_path,
    run_early_path_campaign,
    score_audition,
    validate_early_path_policy,
)
from solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition import (  # noqa: E402
    OrganicPressureError,
)
from scripts.run_ordinary_recent_early_path_h900_audition import (  # noqa: E402
    _safe_observation_stem,
    run_capture,
)

CONFIG_PATH = ROOT / "configs/ordinary_recent_early_path_h900_audition_v1.yaml"


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
        self.current = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
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
                    "outAmount": str(10000000 + index),
                    "router": "dflow",
                    "mode": "manual",
                }
            return _Response(json.dumps(body).encode("utf-8"))
        raise AssertionError(f"unexpected URL: {url}")


def _row(index: int, *, mcap: float, organic: float | None = 999.0) -> dict[str, Any]:
    stats: dict[str, float] = {}
    if organic is not None:
        stats = {"buyOrganicVolume": organic, "sellOrganicVolume": 0.0}
    return {
        "id": f"mint-{index:02d}",
        "launchpad": "pump.fun",
        "mcap": mcap,
        "liquidity": 2600.0,
        "stats5m": stats,
        "firstPool": {"createdAt": "2026-08-21T12:00:00Z"},
        "updatedAt": "2026-08-21T12:05:00Z",
    }


class EarlyPathAuditionTests(unittest.TestCase):
    def test_policy_binds_mcap_path_formula_not_organic_or_flow(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(policy, dict)
        validate_early_path_policy(policy, root=ROOT)
        self.assertEqual(policy["decision_snapshot"]["x_formula"], X_FORMULA)
        self.assertNotIn("buyOrganicVolume", str(policy["decision_snapshot"]["x_formula"]))
        self.assertNotIn("buyVolume", str(policy["decision_snapshot"]["x_formula"]))
        self.assertEqual(policy["external_authority"]["owner_phrase"], AUTHORITY_PHRASE)

    def test_policy_rejects_organic_formula_drift(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        policy["decision_snapshot"]["x_formula"] = (
            "(stats5m.buyOrganicVolume - stats5m.sellOrganicVolume) / top-level liquidity"
        )
        with self.assertRaisesRegex(OrganicPressureError, "X_FORMULA_DRIFT"):
            validate_early_path_policy(policy, root=ROOT)

    def test_early_path_uses_both_mcaps_and_does_not_impute_zero(self) -> None:
        observed_at = datetime(2026, 8, 21, 12, 5, tzinfo=UTC)
        recent = _row(0, mcap=1000.0)
        t5 = _row(0, mcap=1500.0)
        result = project_early_path(recent, t5, observed_at)
        self.assertEqual(result["status"], "ELIGIBLE")
        self.assertEqual(result["value"], 0.5)

        missing = project_early_path(recent, _row(0, mcap=float("nan")), observed_at)
        self.assertEqual(missing["status"], "MISSING")
        self.assertIsNone(missing["value"])
        self.assertEqual(missing["reason"], "MCAP_FIELD_MISSING_OR_INVALID")

        absent = dict(_row(0, mcap=1000.0))
        del absent["mcap"]
        missing_key = project_early_path(recent, absent, observed_at)
        self.assertEqual(missing_key["status"], "MISSING")
        self.assertIsNone(missing_key["value"])

        zero_recent = project_early_path(_row(0, mcap=0.0), t5, observed_at)
        self.assertEqual(zero_recent["status"], "MISSING")
        self.assertEqual(zero_recent["reason"], "MCAP_FIELD_MISSING_OR_INVALID")

        zero_t5 = project_early_path(recent, _row(0, mcap=0.0), observed_at)
        self.assertEqual(zero_t5["status"], "ELIGIBLE")
        self.assertEqual(zero_t5["value"], -1.0)

        missing_row = project_early_path(recent, None, observed_at)
        self.assertEqual(missing_row["status"], "MISSING")
        self.assertIsNone(missing_row["value"])
        self.assertEqual(missing_row["reason"], "SEARCH_MINT_NOT_RETURNED")

        mismatched = project_early_path(recent, _row(1, mcap=1500.0), observed_at)
        self.assertEqual(mismatched["status"], "MISSING")
        self.assertEqual(mismatched["reason"], "RECENT_T5_MINT_MISMATCH")

    def test_early_path_ignores_organic_fields_when_mcap_missing(self) -> None:
        observed_at = datetime(2026, 8, 21, 12, 5, tzinfo=UTC)
        recent = _row(0, mcap=1000.0, organic=400.0)
        t5 = _row(0, mcap=1000.0, organic=400.0)
        del t5["mcap"]
        result = project_early_path(recent, t5, observed_at)
        self.assertEqual(result["status"], "MISSING")
        self.assertIsNone(result["value"])

    def test_score_close_terminal_is_early_path_not_organic(self) -> None:
        rows = [
            {
                "mint": f"mint-{index:02d}",
                "x": (index - 9) / 100.0,
                "h900_terminal": "MARKET_EXECUTION_UNAVAILABLE" if index == 17 else "QUOTE_OBSERVED",
                "y": None if index == 17 else (index - 9) / 100.0,
            }
            for index in range(18)
        ]
        result = score_audition(
            rows,
            min_decision_time_eligible=18,
            min_rankable_h900=14,
            tau_floor=0.20,
            leave_one_out_positive_share=0.75,
            close_terminal=CLOSE_TERMINAL,
        )
        self.assertEqual(result["terminal"], CLOSE_TERMINAL)

    def test_campaign_projects_recent_to_t5_mcap_and_skips_quotes_when_mcap_missing(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        recent = [_row(index, mcap=1000.0) for index in range(24)]
        search = [_row(index, mcap=1000.0 + 10.0 * index) for index in range(24)]
        clock = _Clock()
        opener = _PathOpener(recent, search)
        receipt = run_early_path_campaign(
            policy,
            authority_phrase=AUTHORITY_PHRASE,
            reservation={"state": "STARTED", "credential_reads": 0},
            excluded_mints={"prior"},
            credential_loader=lambda: "test-free-key-not-a-secret",
            preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0},
            opener=opener,
            clock=clock.now,
            sleeper=clock.sleep,
        )
        self.assertEqual(receipt["atom_id"], "ORDINARY_RECENT_EARLY_PATH_H900_AUDITION_V1")
        self.assertEqual(receipt["decision_time_eligible"], 24)
        self.assertAlmostEqual(receipt["candidate_observations"][3]["x"], 0.03)
        self.assertEqual(
            receipt["candidate_observations"][0]["x_source"]["field_paths"],
            ["recent.mcap", "t5.mcap", "firstPool.createdAt", "t5.updatedAt"],
        )
        self.assertEqual(receipt["provider_requests"], 50)
        self.assertIn(receipt["terminal_outcome"], {"EARN_FRESH_OOS", CLOSE_TERMINAL})

        missing_search = [dict(row) for row in search]
        for row in missing_search:
            del row["mcap"]
        clock_missing = _Clock()
        opener_missing = _PathOpener(recent, missing_search)
        missing_receipt = run_early_path_campaign(
            policy,
            authority_phrase=AUTHORITY_PHRASE,
            reservation={"state": "STARTED", "credential_reads": 0},
            excluded_mints={"prior"},
            credential_loader=lambda: "test-free-key-not-a-secret",
            preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0},
            opener=opener_missing,
            clock=clock_missing.now,
            sleeper=clock_missing.sleep,
        )
        self.assertEqual(missing_receipt["terminal_outcome"], "INVALID_EVIDENCE_YIELD")
        self.assertEqual(missing_receipt["decision_time_eligible"], 0)
        self.assertEqual(missing_receipt["provider_requests"], 2)
        self.assertIsNone(missing_receipt["candidate_observations"][0]["x"])

    def test_capture_keeps_raw_outside_git_and_does_not_escape_stems(self) -> None:
        self.assertNotIn("/", _safe_observation_stem("../outside:BUY_T0"))
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        recent = [_row(index, mcap=1000.0 + index) for index in range(24)]
        search = [_row(index, mcap=1100.0 + index) for index in range(24)]
        clock = _Clock()
        opener = _PathOpener(recent, search)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            excluded_path = root / "excluded.json"
            excluded_path.write_text(json.dumps(["prior"]), encoding="utf-8")
            receipt_path = root / "runtime.json"
            raw_root = root / "raw"
            receipt = run_capture(
                authority_phrase=AUTHORITY_PHRASE,
                excluded_mints_path=excluded_path,
                policy=policy,
                raw_root=raw_root,
                receipt_path=receipt_path,
                credential_loader=lambda: "test-free-key-not-a-secret",
                preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0},
                opener=opener,
                clock=clock.now,
                sleeper=clock.sleep,
            )
            encoded = receipt_path.read_text(encoding="utf-8")
            self.assertNotIn("test-free-key-not-a-secret", encoded)
            self.assertTrue(any(raw_root.rglob("DISCOVERY_RECENT.body")))
            self.assertEqual(receipt["raw_retention"]["mode"], "A4_OUTSIDE_GIT")


if __name__ == "__main__":
    unittest.main()
