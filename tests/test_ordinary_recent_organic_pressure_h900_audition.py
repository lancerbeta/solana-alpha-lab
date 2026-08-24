from __future__ import annotations

import json
import io
import sys
import tempfile
import unittest
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition import (  # noqa: E402
    AUTHORITY_PHRASE,
    OrganicPressureError,
    build_search_url,
    classify_organic_quote,
    project_organic_pressure,
    run_campaign,
    score_audition,
    score_sign_only_kendall,
    select_frozen_candidates,
    validate_policy,
)
from solana_alpha_lab.pmf_quote_slice_one_shot import QuoteShotError  # noqa: E402
from scripts.run_ordinary_recent_organic_pressure_h900_audition import (  # noqa: E402
    _safe_observation_stem,
    run_capture,
)

CONFIG_PATH = ROOT / "configs/ordinary_recent_organic_pressure_h900_audition_v1.yaml"


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
        self.current = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        self.sleeps: list[float] = []

    def now(self) -> datetime:
        return self.current

    def sleep(self, seconds: float) -> None:
        if seconds < 60:
            return
        self.sleeps.append(seconds)
        self.current += timedelta(seconds=seconds)


class _CampaignOpener:
    def __init__(self, candidates: list[dict[str, Any]]) -> None:
        self.candidates = candidates
        self.requests: list[object] = []

    def open(self, request: object, timeout: float = 0) -> _Response:
        self.requests.append(request)
        url = str(getattr(request, "full_url"))
        if "/tokens/v2/recent" in url:
            rows = [{"id": "prior", "launchpad": "pump.fun"}, *self.candidates]
            return _Response(json.dumps(rows).encode("utf-8"))
        if "/tokens/v2/search" in url:
            return _Response(json.dumps(self.candidates).encode("utf-8"))
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


class _DuplicateSearchOpener(_CampaignOpener):
    def open(self, request: object, timeout: float = 0) -> _Response:
        url = str(getattr(request, "full_url"))
        if "/tokens/v2/search" in url:
            self.requests.append(request)
            rows = [self.candidates[0], self.candidates[0], *self.candidates[2:]]
            return _Response(json.dumps(rows).encode("utf-8"))
        return super().open(request, timeout=timeout)


class OrganicPressureAuditionTests(unittest.TestCase):
    def test_candidate_freeze_excludes_prior_mints_and_keeps_project_predicate(self) -> None:
        rows = [
            {"id": "prior", "launchpad": "pump.fun"},
            {"id": "wrong", "launchpad": "other"},
            {"id": "fresh-a", "launchpad": "pump.fun"},
            {"id": "fresh-a", "launchpad": "pump.fun"},
            {"id": "fresh-b", "launchpad": "pump.fun"},
        ]

        frozen = select_frozen_candidates(
            rows,
            excluded_mints={"prior"},
            target=24,
        )

        self.assertEqual([row["id"] for row in frozen], ["fresh-a", "fresh-b"])

    def test_organic_pressure_keeps_missing_fields_typed(self) -> None:
        observed_at = datetime(2026, 8, 20, 12, 5, tzinfo=UTC)
        row = {
            "id": "mint",
            "launchpad": "pump.fun",
            "liquidity": 1000.0,
            "stats5m": {"buyOrganicVolume": 4.0},
            "firstPool": {"createdAt": "2026-08-20T12:00:00Z"},
            "updatedAt": "2026-08-20T12:05:00Z",
        }

        result = project_organic_pressure(row, snapshot_at=observed_at)

        self.assertEqual(result["status"], "MISSING")
        self.assertIsNone(result["value"])

    def test_organic_pressure_requires_five_minute_seasoning_and_uses_liquidity(self) -> None:
        observed_at = datetime(2026, 8, 20, 12, 5, tzinfo=UTC)
        row = {
            "id": "mint",
            "launchpad": "pump.fun",
            "liquidity": 1000.0,
            "stats5m": {"buyOrganicVolume": 40.0, "sellOrganicVolume": 10.0},
            "firstPool": {"createdAt": "2026-08-20T12:00:00Z"},
            "updatedAt": "2026-08-20T12:05:00Z",
        }

        result = project_organic_pressure(row, snapshot_at=observed_at)

        self.assertEqual(result["status"], "ELIGIBLE")
        self.assertEqual(result["value"], 0.03)

    def test_organic_pressure_rejects_negative_organic_volume(self) -> None:
        observed_at = datetime(2026, 8, 20, 12, 5, tzinfo=UTC)
        row = {
            "id": "mint",
            "launchpad": "pump.fun",
            "liquidity": 1000.0,
            "stats5m": {"buyOrganicVolume": -1.0, "sellOrganicVolume": 10.0},
            "firstPool": {"createdAt": "2026-08-20T12:00:00Z"},
            "updatedAt": "2026-08-20T12:05:00Z",
        }

        result = project_organic_pressure(row, snapshot_at=observed_at)

        self.assertEqual(result["status"], "MISSING")
        self.assertEqual(result["reason"], "ORGANIC_OR_LIQUIDITY_FIELD_MISSING_OR_INVALID")

    def test_organic_pressure_rejects_nonfinite_derived_value(self) -> None:
        observed_at = datetime(2026, 8, 20, 12, 5, tzinfo=UTC)
        row = {
            "id": "mint",
            "launchpad": "pump.fun",
            "liquidity": 1e-308,
            "stats5m": {"buyOrganicVolume": 1e308, "sellOrganicVolume": 0.0},
            "firstPool": {"createdAt": "2026-08-20T12:00:00Z"},
            "updatedAt": "2026-08-20T12:05:00Z",
        }

        result = project_organic_pressure(row, snapshot_at=observed_at)

        self.assertEqual(result["status"], "MISSING")
        self.assertEqual(result["reason"], "ORGANIC_PRESSURE_NONFINITE")

    def test_organic_pressure_marks_future_pool_timestamp_ineligible_without_waiting(self) -> None:
        observed_at = datetime(2026, 8, 20, 12, 5, tzinfo=UTC)
        row = {
            "id": "mint",
            "launchpad": "pump.fun",
            "liquidity": 1000.0,
            "stats5m": {"buyOrganicVolume": 40.0, "sellOrganicVolume": 10.0},
            "firstPool": {"createdAt": "2026-08-20T12:10:00Z"},
            "updatedAt": "2026-08-20T12:10:00Z",
        }

        result = project_organic_pressure(row, snapshot_at=observed_at)

        self.assertEqual(result["status"], "MISSING")
        self.assertEqual(result["reason"], "FIRST_POOL_TIMESTAMP_IN_FUTURE")

    def test_search_url_is_one_query_of_at_most_one_hundred_mints(self) -> None:
        url = build_search_url(["MintA", "MintB"])

        self.assertEqual(url, "https://api.jup.ag/tokens/v2/search?query=MintA%2CMintB")

    def test_policy_rejects_decision_threshold_drift(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        policy["decision_rule"]["tau_b_floor"] = "0.10"

        with self.assertRaisesRegex(OrganicPressureError, "TAU_FLOOR_DRIFT"):
            validate_policy(policy, root=ROOT)

    def test_quote_taxonomy_keeps_market_not_found_out_of_numeric_y(self) -> None:
        body = json.dumps(
            {"transaction": None, "errorCode": "MARKET_NOT_FOUND"}
        ).encode("utf-8")

        result = classify_organic_quote(body, http_status=400)

        self.assertEqual(result["terminal"], "MARKET_EXECUTION_UNAVAILABLE")
        self.assertIsNone(result["y"])

    def test_quote_auth_failure_wins_over_payload_market_error(self) -> None:
        body = json.dumps(
            {"transaction": None, "errorCode": "MARKET_NOT_FOUND"}
        ).encode("utf-8")

        result = classify_organic_quote(body, http_status=401)

        self.assertEqual(result["terminal"], "PROVIDER_MEASUREMENT_FAILURE")
        self.assertIsNone(result["y"])

    def test_observed_quote_requires_expected_atomic_input(self) -> None:
        body = json.dumps(
            {
                "transaction": None,
                "requestId": "request-1",
                "inAmount": "999",
                "outAmount": "1000",
                "router": "dflow",
                "mode": "manual",
            }
        ).encode("utf-8")

        result = classify_organic_quote(body, http_status=200, expected_in_amount="10000000")

        self.assertEqual(result["terminal"], "CLIENT_CONTRACT_FAILURE")
        self.assertIsNone(result["y"])

    def test_observed_quote_requires_expected_mint_direction(self) -> None:
        body = json.dumps(
            {
                "transaction": None,
                "requestId": "request-1",
                "inputMint": "wrong-input",
                "outputMint": "wrong-output",
                "inAmount": "10000000",
                "outAmount": "1000",
                "router": "dflow",
                "mode": "manual",
            }
        ).encode("utf-8")

        result = classify_organic_quote(
            body,
            http_status=200,
            expected_in_amount="10000000",
            expected_input_mint="So11111111111111111111111111111111111111112",
            expected_output_mint="mint-01",
        )

        self.assertEqual(result["terminal"], "CLIENT_CONTRACT_FAILURE")
        self.assertIsNone(result["y"])

    def test_raw_observation_name_cannot_escape_capture_directory(self) -> None:
        self.assertNotIn("/", _safe_observation_stem("../outside:BUY_T0"))
        self.assertNotIn("\\", _safe_observation_stem("..\\outside:BUY_T0"))

    def test_score_stops_on_insufficient_sample_before_any_decision(self) -> None:
        rows = [
            {
                "mint": f"mint-{index:02d}",
                "x": float(index) / 100.0,
                "h900_terminal": "QUOTE_OBSERVED",
                "y": float(index + 1) / 100.0,
            }
            for index in range(16)
        ]

        result = score_audition(
            rows,
            min_decision_time_eligible=18,
            min_rankable_h900=14,
            tau_floor=0.20,
            leave_one_out_positive_share=0.75,
        )

        self.assertEqual(result["terminal"], "INVALID_EVIDENCE_YIELD")
        self.assertEqual(result["decision_time_eligible"], 16)
        self.assertEqual(result["rankable_h900"], 16)

    def test_score_rejects_market_unavailable_token_selected_by_top_x_quartile(self) -> None:
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
        )

        self.assertTrue(result["selected_market_execution_unavailable"])
        self.assertEqual(result["terminal"], "CLOSE_ORGANIC_PRESSURE_CANDIDATE")

    def test_policy_and_campaign_bind_search_t5_and_h900_without_credential_reordering(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(policy, dict)
        validate_policy(policy, root=ROOT)
        candidates = [
            {
                "id": f"mint-{index:02d}",
                "launchpad": "pump.fun",
                "liquidity": 1000.0,
                "stats5m": {
                    "buyOrganicVolume": 100.0 + index,
                    "sellOrganicVolume": 10.0,
                },
                "firstPool": {"createdAt": "2026-08-20T12:00:00Z"},
                "updatedAt": "2026-08-20T12:05:00Z",
            }
            for index in range(24)
        ]
        clock = _Clock()
        opener = _CampaignOpener(candidates)
        events: list[str] = []
        raw_rows: list[str] = []

        def preflight(*_args: object, **_kwargs: object) -> dict[str, object]:
            events.append("preflight")
            return {"credential_reads": 0}

        def credential_loader() -> str:
            events.append("credential")
            return "test-free-key-not-a-secret"

        def raw_sink(observation_id: str, _body: bytes, _observed_at: str) -> None:
            raw_rows.append(observation_id)

        receipt = run_campaign(
            policy,
            authority_phrase=AUTHORITY_PHRASE,
            reservation={"state": "STARTED", "credential_reads": 0},
            excluded_mints={"prior"},
            credential_loader=credential_loader,
            preflight_fn=preflight,
            opener=opener,
            clock=clock.now,
            sleeper=clock.sleep,
            raw_sink=raw_sink,
        )

        self.assertEqual(events, ["preflight", "credential"])
        self.assertEqual(clock.sleeps, [300.0, 900.0])
        self.assertEqual(receipt["provider_requests"], 50)
        self.assertEqual(len(raw_rows), 50)
        self.assertEqual(receipt["decision_time_eligible"], 24)
        self.assertEqual(receipt["rankable_h900"], 24)
        self.assertIn(receipt["terminal_outcome"], {"EARN_FRESH_OOS", "CLOSE_ORGANIC_PRESSURE_CANDIDATE"})
        self.assertEqual(
            {len(row["x_source"]["row_sha256"]) for row in receipt["candidate_observations"]},
            {64},
        )
        for request in opener.requests:
            self.assertNotIn("taker", str(getattr(request, "full_url")).lower())

    def test_campaign_replans_on_duplicate_or_missing_bulk_snapshot_mint(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        candidates = [
            {
                "id": f"mint-{index:02d}",
                "launchpad": "pump.fun",
                "liquidity": 1000.0,
                "stats5m": {"buyOrganicVolume": 100.0, "sellOrganicVolume": 10.0},
                "firstPool": {"createdAt": "2026-08-20T12:00:00Z"},
                "updatedAt": "2026-08-20T12:05:00Z",
            }
            for index in range(24)
        ]
        clock = _Clock()
        opener = _DuplicateSearchOpener(candidates)

        receipt = run_campaign(
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

        self.assertEqual(receipt["terminal_outcome"], "INVALID_EVIDENCE_REPLAN")
        self.assertEqual(receipt["provider_requests"], 2)
        self.assertEqual(len(opener.requests), 2)
        self.assertEqual(receipt["snapshot_error"]["duplicate_mints"], ["mint-00"])
        self.assertIn("mint-01", receipt["snapshot_error"]["missing_mints"])

    def test_capture_writes_reservation_before_key_and_keeps_raw_bodies_outside_receipt(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        candidates = [
            {
                "id": f"mint-{index:02d}",
                "launchpad": "pump.fun",
                "liquidity": 1000.0,
                "stats5m": {
                    "buyOrganicVolume": 100.0 + index,
                    "sellOrganicVolume": 10.0,
                },
                "firstPool": {"createdAt": "2026-08-20T12:00:00Z"},
                "updatedAt": "2026-08-20T12:05:00Z",
            }
            for index in range(24)
        ]
        clock = _Clock()
        opener = _CampaignOpener(candidates)
        events: list[str] = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            excluded_path = root / "excluded.json"
            excluded_path.write_text(json.dumps(["prior"]), encoding="utf-8")
            receipt_path = root / "runtime.json"
            raw_root = root / "raw"

            def preflight(*_args: object, **_kwargs: object) -> dict[str, object]:
                events.append("preflight")
                return {"credential_reads": 0}

            def credential_loader() -> str:
                events.append("credential")
                return "test-free-key-not-a-secret"

            receipt = run_capture(
                authority_phrase=AUTHORITY_PHRASE,
                policy=policy,
                excluded_mints_path=excluded_path,
                raw_root=raw_root,
                receipt_path=receipt_path,
                environ={"JUPITER_API_KEY": "test-free-key-not-a-secret"},
                preflight_fn=preflight,
                credential_loader=credential_loader,
                opener=opener,
                clock=clock.now,
                sleeper=clock.sleep,
            )

            self.assertEqual(events, ["preflight", "credential"])
            self.assertEqual(receipt["credential_reads"], 1)
            self.assertEqual(len(receipt["raw_retention"]["manifests"]), 50)
            self.assertTrue((raw_root / "campaign_reservation.json").is_file())
            self.assertNotIn("test-free-key-not-a-secret", receipt_path.read_text(encoding="utf-8"))

    def test_capture_writes_typed_receipt_when_process_credential_is_missing(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            excluded_path = root / "excluded.json"
            excluded_path.write_text(json.dumps(["prior"]), encoding="utf-8")

            receipt = run_capture(
                authority_phrase=AUTHORITY_PHRASE,
                policy=policy,
                excluded_mints_path=excluded_path,
                raw_root=root / "raw",
                receipt_path=root / "runtime.json",
                environ={},
                preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0},
            )

            self.assertEqual(receipt["credential_reads"], 1)
            self.assertEqual(receipt["provider_requests"], 0)
            self.assertEqual(receipt["terminal_error_code"], "JUPITER_API_KEY_MISSING_OR_EMPTY")
            self.assertTrue((root / "runtime.json").is_file())

    def test_capture_writes_typed_receipt_when_credential_free_preflight_fails(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            excluded_path = root / "excluded.json"
            excluded_path.write_text(json.dumps(["prior"]), encoding="utf-8")

            def failed_preflight(*_args: object, **_kwargs: object) -> dict[str, object]:
                raise QuoteShotError("DNS_PREFLIGHT_FAILED")

            receipt = run_capture(
                authority_phrase=AUTHORITY_PHRASE,
                policy=policy,
                excluded_mints_path=excluded_path,
                raw_root=root / "raw",
                receipt_path=root / "runtime.json",
                environ={"JUPITER_API_KEY": "must-not-be-read"},
                preflight_fn=failed_preflight,
            )

            self.assertEqual(receipt["terminal_outcome"], "INVALID_EVIDENCE_REPLAN")
            self.assertEqual(receipt["terminal_error_code"], "DNS_PREFLIGHT_FAILED")
            self.assertEqual(receipt["credential_reads"], 0)
            self.assertEqual(receipt["provider_requests"], 0)
            self.assertTrue((root / "runtime.json").is_file())

    def test_transaction_response_is_not_retained_in_a4_raw(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        candidates = [
            {
                "id": f"mint-{index:02d}",
                "launchpad": "pump.fun",
                "liquidity": 1000.0,
                "stats5m": {"buyOrganicVolume": 100.0, "sellOrganicVolume": 10.0},
                "firstPool": {"createdAt": "2026-08-20T12:00:00Z"},
                "updatedAt": "2026-08-20T12:05:00Z",
            }
            for index in range(24)
        ]

        class TransactionOpener(_CampaignOpener):
            def open(self, request: object, timeout: float = 0) -> _Response:
                url = str(getattr(request, "full_url"))
                if "/swap/v2/order" in url:
                    self.requests.append(request)
                    body = {
                        "transaction": "forbidden-transaction-bytes",
                        "inputMint": "So11111111111111111111111111111111111111112",
                        "outputMint": "mint-00",
                        "inAmount": "10000000",
                        "outAmount": "1000",
                        "router": "dflow",
                        "mode": "manual",
                    }
                    return _Response(json.dumps(body).encode("utf-8"))
                return super().open(request, timeout=timeout)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            excluded_path = root / "excluded.json"
            excluded_path.write_text(json.dumps(["prior"]), encoding="utf-8")
            raw_root = root / "raw"
            clock = _Clock()

            receipt = run_capture(
                authority_phrase=AUTHORITY_PHRASE,
                policy=policy,
                excluded_mints_path=excluded_path,
                raw_root=raw_root,
                receipt_path=root / "runtime.json",
                environ={"JUPITER_API_KEY": "test-free-key-not-a-secret"},
                preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0},
                opener=TransactionOpener(candidates),
                clock=clock.now,
                sleeper=clock.sleep,
            )

            self.assertEqual(receipt["terminal_error_code"], "QUOTE_RETURNED_TRANSACTION")
            body_files = list(raw_root.rglob("*.body"))
            self.assertEqual([path for path in body_files if "BUY_T0" in path.name], [])
            self.assertTrue(all(b"forbidden-transaction-bytes" not in path.read_bytes() for path in body_files))

    def test_sign_only_kendall_uses_negative_direction_without_quartile_or_loo(self) -> None:
        negative = [
            {
                "mint": f"mint-{index:02d}",
                "x": float(index),
                "h900_terminal": "QUOTE_OBSERVED",
                "y": float(23 - index),
            }
            for index in range(18)
        ]
        earned = score_sign_only_kendall(
            negative,
            min_decision_time_eligible=18,
            min_rankable_h900=14,
            expected_direction="NEGATIVE",
            close_terminal="CLOSE_HOLDER_CONCENTRATION_FAMILY",
            earn_terminal="EARN_ONE_CONFIRMATORY_FRESH_OOS",
            invalid_terminal="INVALID_EVIDENCE_REPLAN",
        )
        self.assertLess(earned["tau_b"], 0)
        self.assertEqual(earned["terminal"], "EARN_ONE_CONFIRMATORY_FRESH_OOS")
        self.assertEqual(earned["score_kind"], "SIGN_ONLY_KENDALL_TAU_B")
        self.assertIsNone(earned["top_quartile_median_y"])
        self.assertIsNone(earned["leave_one_out_positive_share"])

        positive = [
            {
                "mint": f"mint-{index:02d}",
                "x": float(index),
                "h900_terminal": "QUOTE_OBSERVED",
                "y": float(index),
            }
            for index in range(18)
        ]
        closed = score_sign_only_kendall(
            positive,
            min_decision_time_eligible=18,
            min_rankable_h900=14,
            expected_direction="NEGATIVE",
            close_terminal="CLOSE_HOLDER_CONCENTRATION_FAMILY",
            earn_terminal="EARN_ONE_CONFIRMATORY_FRESH_OOS",
            invalid_terminal="INVALID_EVIDENCE_REPLAN",
        )
        self.assertGreaterEqual(closed["tau_b"], 0)
        self.assertEqual(closed["terminal"], "CLOSE_HOLDER_CONCENTRATION_FAMILY")

        short = negative[:16]
        invalid = score_sign_only_kendall(
            short,
            min_decision_time_eligible=18,
            min_rankable_h900=14,
            expected_direction="NEGATIVE",
            close_terminal="CLOSE_HOLDER_CONCENTRATION_FAMILY",
            earn_terminal="EARN_ONE_CONFIRMATORY_FRESH_OOS",
            invalid_terminal="INVALID_EVIDENCE_REPLAN",
        )
        self.assertEqual(invalid["terminal"], "INVALID_EVIDENCE_REPLAN")
        self.assertIsNone(invalid["tau_b"])

        singleton = [
            {"mint": "mint-00", "x": 1.0, "h900_terminal": "QUOTE_OBSERVED", "y": 0.1}
        ]
        degenerate = score_sign_only_kendall(
            singleton,
            min_decision_time_eligible=0,
            min_rankable_h900=0,
            expected_direction="NEGATIVE",
            close_terminal="CLOSE_HOLDER_CONCENTRATION_FAMILY",
            earn_terminal="EARN_ONE_CONFIRMATORY_FRESH_OOS",
            invalid_terminal="INVALID_EVIDENCE_REPLAN",
        )
        self.assertIsNone(degenerate["tau_b"])
        self.assertEqual(degenerate["terminal"], "INVALID_EVIDENCE_REPLAN")

        with self.assertRaisesRegex(OrganicPressureError, "EXPECTED_DIRECTION_UNSUPPORTED"):
            score_sign_only_kendall(
                negative,
                min_decision_time_eligible=18,
                min_rankable_h900=14,
                expected_direction="POSITIVE",
                close_terminal="CLOSE",
                earn_terminal="EARN",
                invalid_terminal="INVALID",
            )

    def test_injected_score_fn_replaces_legacy_scorer_without_changing_default_path(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(policy, dict)
        candidates = [
            {
                "id": f"mint-{index:02d}",
                "launchpad": "pump.fun",
                "liquidity": 1000.0,
                "stats5m": {
                    "buyOrganicVolume": 100.0 + index,
                    "sellOrganicVolume": 10.0,
                },
                "firstPool": {"createdAt": "2026-08-20T12:00:00Z"},
                "updatedAt": "2026-08-20T12:05:00Z",
            }
            for index in range(24)
        ]

        def injected(rows: list[dict[str, object]]) -> dict[str, object]:
            return {
                "terminal": "INJECTED_TERMINAL",
                "decision_time_eligible": 24,
                "rankable_h900": len(rows),
                "tau_b": -0.5,
                "score_kind": "SIGN_ONLY_KENDALL_TAU_B",
            }

        clock = _Clock()
        injected_receipt = run_campaign(
            policy,
            authority_phrase=AUTHORITY_PHRASE,
            reservation={"state": "STARTED", "credential_reads": 0},
            excluded_mints={"prior"},
            credential_loader=lambda: "test-free-key-not-a-secret",
            preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0},
            opener=_CampaignOpener(candidates),
            clock=clock.now,
            sleeper=clock.sleep,
            score_fn=injected,
        )
        self.assertEqual(injected_receipt["terminal_outcome"], "INJECTED_TERMINAL")
        self.assertEqual(injected_receipt["score"]["score_kind"], "SIGN_ONLY_KENDALL_TAU_B")

        default_clock = _Clock()
        default_receipt = run_campaign(
            policy,
            authority_phrase=AUTHORITY_PHRASE,
            reservation={"state": "STARTED", "credential_reads": 0},
            excluded_mints={"prior"},
            credential_loader=lambda: "test-free-key-not-a-secret",
            preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0},
            opener=_CampaignOpener(candidates),
            clock=default_clock.now,
            sleeper=default_clock.sleep,
        )
        self.assertIn(
            default_receipt["terminal_outcome"],
            {"EARN_FRESH_OOS", "CLOSE_ORGANIC_PRESSURE_CANDIDATE"},
        )
        self.assertIn("top_quartile_median_y", default_receipt["score"])
        self.assertNotEqual(default_receipt["terminal_outcome"], "INJECTED_TERMINAL")

    def test_structural_backing_wrapper_keeps_legacy_scorer_default(self) -> None:
        import inspect

        from solana_alpha_lab.early_structural_backing_pit_commissioning import (
            run_structural_backing_campaign,
        )

        source = inspect.getsource(run_structural_backing_campaign)
        self.assertNotIn("score_fn", source)
        self.assertIn("project_x=project_structural_backing", source)

    def test_non_legacy_policy_forbids_tau_quartile_loo_keys(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(policy, dict)
        with self.assertRaisesRegex(OrganicPressureError, "LEGACY_DECISION_KEY_FORBIDDEN:tau_b_floor"):
            validate_policy(policy, root=ROOT, require_legacy_decision_rule=False)


if __name__ == "__main__":
    unittest.main()
