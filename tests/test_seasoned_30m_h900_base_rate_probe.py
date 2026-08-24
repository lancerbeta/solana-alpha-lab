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
    validate_holder_concentration_policy,
)
from solana_alpha_lab.early_structural_backing_pit_commissioning import (  # noqa: E402
    validate_structural_backing_policy,
)
from solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition import (  # noqa: E402
    OrganicPressureError,
    SEASONING_SECONDS,
    validate_policy,
)
from solana_alpha_lab.seasoned_30m_h900_base_rate_probe import (  # noqa: E402
    AGE_MAX_EXCLUSIVE_SECONDS,
    AGE_MIN_SECONDS,
    AUTHORITY_PHRASE,
    ELIGIBILITY_MARKER_ROLE,
    FACTORY_RUNNER,
    FACTORY_RUNNER_SHA256,
    INCONCLUSIVE_TERMINAL,
    INVALID_TERMINAL,
    MARKET_EXECUTION_UNAVAILABLE,
    NO_POSITIVE_MASS_TERMINAL,
    POPULATION_ID,
    QUOTE_OBSERVED,
    SEASONING_SECONDS as PROBE_SEASONING_SECONDS,
    SHOWS_POSITIVE_MASS_TERMINAL,
    X_FORMULA,
    classify_campaign_failure,
    project_seasoned_decision_eligibility,
    run_seasoned_base_rate_campaign,
    score_seasoned_base_rate,
    validate_seasoned_base_rate_policy,
)
from scripts.run_seasoned_30m_h900_base_rate_probe import run_capture  # noqa: E402


CONFIG_PATH = ROOT / "configs/seasoned_30m_h900_base_rate_probe_v1.yaml"
MODULE_PATH = ROOT / "src/solana_alpha_lab/seasoned_30m_h900_base_rate_probe.py"
ORDINARY_CONFIG = ROOT / "configs/ordinary_recent_organic_pressure_h900_audition_v1.yaml"
HOLDER_CONFIG = ROOT / "configs/early_holder_concentration_h900_falsifier_v1.yaml"
STRUCTURAL_CONFIG = ROOT / "configs/early_structural_backing_pit_commissioning_v1.yaml"


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
    def __init__(self, recent: list[dict[str, Any]], search: list[dict[str, Any]], sell_out: str = "9727186") -> None:
        self.recent = recent
        self.search = search
        self.sell_out = sell_out
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
                    "outAmount": str(1_000_000 + index),
                    "router": "dflow",
                    "mode": "manual",
                }
            else:
                body = {
                    "transaction": None,
                    "requestId": "sell",
                    "inputMint": values["inputMint"],
                    "outputMint": values["outputMint"],
                    "inAmount": values["amount"],
                    "outAmount": self.sell_out,
                    "router": "dflow",
                    "mode": "manual",
                }
            return _Response(json.dumps(body).encode("utf-8"))
        raise AssertionError(f"unexpected URL: {url}")


def _row(
    index: int,
    *,
    liquidity: float = 2500.0,
    created_at: str = "2026-08-24T12:00:00Z",
    updated_at: str = "2026-08-24T12:00:00Z",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": f"mint-{index:02d}",
        "launchpad": "pump.fun",
        "liquidity": liquidity,
        "firstPool": {"createdAt": created_at},
        "updatedAt": updated_at,
        "audit": {"topHoldersPercentage": 80.0},
        "stats5m": {"buyOrganicVolume": 9.0, "sellOrganicVolume": 1.0},
    }
    if extra:
        row.update(extra)
    return row


def _score_row(*, y: float | None, terminal: str = QUOTE_OBSERVED, status: str = "ELIGIBLE") -> dict[str, object]:
    payload: dict[str, object] = {
        "x_status": status,
        "x": 1.0,
        "h900_terminal": terminal,
        "y": y,
    }
    if y is not None:
        payload["h900"] = {"output_amount": str(int(round((y + 1.0) * 10_000_000)))}
    return payload


class Seasoned30mBaseRateProbeTests(unittest.TestCase):
    def test_existing_consumers_keep_300s_seasoning(self) -> None:
        ordinary = yaml.safe_load(ORDINARY_CONFIG.read_text(encoding="utf-8"))
        holder = yaml.safe_load(HOLDER_CONFIG.read_text(encoding="utf-8"))
        structural = yaml.safe_load(STRUCTURAL_CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(ordinary["population"]["seasoning_seconds"], SEASONING_SECONDS)
        self.assertEqual(holder["population"]["seasoning_seconds"], SEASONING_SECONDS)
        self.assertEqual(structural["population"]["seasoning_seconds"], SEASONING_SECONDS)
        validate_policy(ordinary, root=ROOT)
        validate_holder_concentration_policy(holder, root=ROOT)
        validate_structural_backing_policy(structural, root=ROOT)
        self.assertEqual(PROBE_SEASONING_SECONDS, 1800)
        self.assertNotEqual(PROBE_SEASONING_SECONDS, SEASONING_SECONDS)

    def test_policy_pins_task_local_population_and_factory_runner(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(policy, dict)
        validate_seasoned_base_rate_policy(policy, root=ROOT)
        self.assertEqual(policy["population"]["population_id"], POPULATION_ID)
        self.assertNotEqual(policy["population"].get("icp_id"), "ICP-EARLY-PUMPFUN-V1")
        self.assertEqual(policy["population"]["seasoning_seconds"], 1800)
        self.assertEqual(policy["population"]["age_band_seconds"]["min"], AGE_MIN_SECONDS)
        self.assertEqual(policy["population"]["age_band_seconds"]["max_exclusive"], AGE_MAX_EXCLUSIVE_SECONDS)
        self.assertEqual(policy["decision_snapshot"]["x_formula"], X_FORMULA)
        self.assertEqual(policy["decision_snapshot"]["hypothesis_x"], "forbidden")
        self.assertEqual(policy["external_authority"]["owner_phrase"], AUTHORITY_PHRASE)
        digest = hashlib.sha256((ROOT / FACTORY_RUNNER).read_bytes()).hexdigest()
        self.assertEqual(digest, FACTORY_RUNNER_SHA256)
        self.assertEqual(digest, policy["factory_runner_sha256"])

    def test_wrapper_does_not_duplicate_campaign_runtime(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("perform_credentialed_get", source)
        self.assertNotIn("build_search_url", source)
        self.assertNotIn("ORDER_ENDPOINT", source)
        self.assertNotIn("RECENT_ENDPOINT", source)
        self.assertNotIn("time.sleep", source)
        self.assertEqual(source.count("run_campaign("), 1)
        self.assertIn("expected_seasoning_seconds=SEASONING_SECONDS", source)
        self.assertIn("project_x=project_seasoned_decision_eligibility", source)
        self.assertIn("score_fn=score_seasoned_base_rate", source)

    def test_projector_uses_only_neutral_eligibility_fields(self) -> None:
        observed_at = datetime(2026, 8, 24, 12, 30, tzinfo=UTC)
        recent = _row(0, created_at="2026-08-24T12:00:00Z", updated_at="2026-08-24T12:30:00Z")
        ok = project_seasoned_decision_eligibility(recent, recent, observed_at)
        self.assertEqual(ok["status"], "ELIGIBLE")
        self.assertEqual(ok["value"], 1.0)
        self.assertEqual(ok["eligibility_marker_role"], "NOT_A_SCIENTIFIC_X")
        self.assertEqual(ok["age_seconds"], 1800.0)
        self.assertNotIn("audit.topHoldersPercentage", ok["inputs"])
        self.assertNotIn("stats5m.buyOrganicVolume", ok["inputs"])

        too_young = project_seasoned_decision_eligibility(
            recent,
            _row(0, created_at="2026-08-24T12:00:01Z", updated_at="2026-08-24T12:30:00Z"),
            observed_at,
        )
        self.assertEqual(too_young["status"], "TOO_YOUNG")

        too_old = project_seasoned_decision_eligibility(
            recent,
            _row(0, created_at="2026-08-24T11:30:00Z", updated_at="2026-08-24T12:30:00Z"),
            observed_at,
        )
        self.assertEqual(too_old["status"], "TOO_OLD")

        low = project_seasoned_decision_eligibility(
            recent,
            _row(0, liquidity=999.0, updated_at="2026-08-24T12:30:00Z"),
            observed_at,
        )
        self.assertEqual(low["status"], "MISSING")
        self.assertEqual(low["reason"], "LIQUIDITY_BELOW_MIN")

        missing = project_seasoned_decision_eligibility(recent, None, observed_at)
        self.assertEqual(missing["reason"], "SEARCH_MINT_NOT_RETURNED")

        mismatch = dict(recent)
        mismatch["id"] = "other"
        bad_id = project_seasoned_decision_eligibility(recent, mismatch, observed_at)
        self.assertEqual(bad_id["reason"], "RECENT_T5_MINT_MISMATCH")

    def test_scorer_emits_typed_terminals_and_ignores_constant_marker(self) -> None:
        none_positive = [_score_row(y=-0.0272814) for _ in range(18)]
        none_score = score_seasoned_base_rate(none_positive)
        self.assertEqual(none_score["terminal"], NO_POSITIVE_MASS_TERMINAL)
        self.assertEqual(none_score["positive_executable_count"], 0)
        self.assertEqual(none_score["decision_time_eligible"], 18)
        self.assertGreaterEqual(none_score["near_friction_floor_count"], 1)

        three_pos = [_score_row(y=-0.02) for _ in range(15)] + [
            _score_row(y=0.01),
            _score_row(y=0.02),
            _score_row(y=0.03),
        ]
        show = score_seasoned_base_rate(three_pos)
        self.assertEqual(show["terminal"], SHOWS_POSITIVE_MASS_TERMINAL)

        median_pos = [_score_row(y=0.01) for _ in range(10)] + [_score_row(y=-0.01) for _ in range(8)]
        median_score = score_seasoned_base_rate(median_pos)
        self.assertEqual(median_score["terminal"], SHOWS_POSITIVE_MASS_TERMINAL)
        self.assertGreater(median_score["median_y"], 0)

        inconclusive = [_score_row(y=-0.02) for _ in range(16)] + [_score_row(y=0.01), _score_row(y=0.02)]
        inc = score_seasoned_base_rate(inconclusive)
        self.assertEqual(inc["terminal"], INCONCLUSIVE_TERMINAL)
        self.assertEqual(inc["positive_executable_count"], 2)
        self.assertLessEqual(inc["median_y"], 0)

        meu = [_score_row(y=None, terminal="MARKET_EXECUTION_UNAVAILABLE") for _ in range(10)] + [
            _score_row(y=-0.01) for _ in range(8)
        ]
        invalid = score_seasoned_base_rate(meu)
        self.assertEqual(invalid["terminal"], INVALID_TERMINAL)
        self.assertEqual(invalid["invalid_class"], "DATA")
        self.assertLess(invalid["rankable_h900"], 14)

    def test_mocked_campaign_waits_1800s_and_returns_no_positive_mass(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        rows = [_row(index) for index in range(24)]
        clock = _Clock()
        receipt = run_seasoned_base_rate_campaign(
            policy,
            authority_phrase=AUTHORITY_PHRASE,
            reservation={"state": "STARTED", "credential_reads": 0},
            excluded_mints={"prior"},
            credential_loader=lambda: "test-key",
            preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0, "provider_requests": 0},
            opener=_PathOpener(rows, rows),
            clock=clock.now,
            sleeper=clock.sleep,
            monotonic_clock=lambda: 0.0,
        )
        self.assertEqual(clock.sleeps[0], 1800.0)
        self.assertEqual(clock.sleeps[1], 900.0)
        self.assertEqual(receipt["provider_requests"], 50)
        self.assertEqual(receipt["decision_time_eligible"], 24)
        self.assertEqual(receipt["terminal_outcome"], NO_POSITIVE_MASS_TERMINAL)
        self.assertEqual(receipt["population_id"], POPULATION_ID)
        self.assertEqual(receipt["score"]["positive_executable_count"], 0)
        self.assertTrue(all(row.get("x") == 1.0 for row in receipt["candidate_observations"]))

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

    def test_provider_discovery_failure_classifies_as_provider(self) -> None:
        receipt = {
            "terminal_outcome": INVALID_TERMINAL,
            "discovery_observations": [
                {
                    "terminal": "PROVIDER_MEASUREMENT_FAILURE",
                    "terminal_error": "HTTP_429",
                }
            ],
        }
        self.assertEqual(classify_campaign_failure(receipt), "PROVIDER")

    def test_quote_provider_failures_override_floor_data_class(self) -> None:
        rows = [_score_row(y=None, terminal="PROVIDER_MEASUREMENT_FAILURE") for _ in range(18)]
        score = score_seasoned_base_rate(rows)
        self.assertEqual(score["terminal"], INVALID_TERMINAL)
        self.assertEqual(score["invalid_class"], "DATA")
        classified = classify_campaign_failure(
            {
                "terminal_outcome": INVALID_TERMINAL,
                "score": score,
                "candidate_observations": [
                    {"buy_terminal": "QUOTE_OBSERVED", "h900_terminal": "PROVIDER_MEASUREMENT_FAILURE"}
                    for _ in range(18)
                ],
            }
        )
        self.assertEqual(classified, "PROVIDER")

    def test_missing_key_before_reservation_does_not_consume_window(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            excluded = root / "excluded.json"
            excluded.write_text(json.dumps({"mints": ["prior-mint"]}), encoding="utf-8")
            raw_root = root / "raw"
            with self.assertRaisesRegex(OrganicPressureError, "JUPITER_API_KEY_MISSING_OR_EMPTY"):
                run_capture(
                    authority_phrase=AUTHORITY_PHRASE,
                    excluded_mints_path=excluded,
                    policy=policy,
                    raw_root=raw_root,
                    receipt_path=root / "receipt.json",
                    environ={},
                )
            self.assertFalse((raw_root / "campaign_reservation.json").exists())

    def test_help_warns_about_wait_and_powershell_quoting(self) -> None:
        source = (ROOT / "scripts/run_seasoned_30m_h900_base_rate_probe.py").read_text(encoding="utf-8")
        self.assertIn("single-quoted string", source)
        self.assertIn("~1800s then ~900s", source)
        self.assertIn("CREATE_ONLY_EXISTS", source)


if __name__ == "__main__":
    unittest.main()
