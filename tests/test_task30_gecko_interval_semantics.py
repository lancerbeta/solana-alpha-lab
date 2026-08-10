from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.task30_gecko_interval_semantics import (
    IntervalSemanticsError,
    build_request_plan,
    evaluate_interval_semantics,
)


POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"


def policy() -> dict[str, object]:
    return {
        "task_id": "TASK-30",
        "atom_id": "T30-A10_GECKO_INTERVAL_SEMANTICS_DISCRIMINATOR_V1",
        "frozen_pool_address": POOL,
        "network": "solana",
        "interval_seconds": 900,
        "external_read": {
            "provider": "GECKOTERMINAL_PUBLIC_KEYLESS",
            "public_base_url": "https://api.geckoterminal.com/api/v2",
            "calls_max": 2,
            "credentials": False,
            "retry": False,
            "fallback": False,
            "scheduler": False,
            "requests": [
                {
                    "request_id": "OHLCV_15M",
                    "method": "GET",
                    "path_template": "/networks/solana/pools/{pool}/ohlcv/minute",
                    "query": {
                        "aggregate": "15",
                        "currency": "usd",
                        "token": "base",
                        "limit": "96",
                        "include_empty_intervals": "false",
                        "before_timestamp": "DYNAMIC_CLOSED_BOUNDARY",
                    },
                },
                {
                    "request_id": "POOL_TRADES",
                    "method": "GET",
                    "path_template": "/networks/solana/pools/{pool}/trades",
                    "query": {"token": "base"},
                },
            ],
        },
        "authority": {
            "provider_api_rpc_wss_calls_max": 2,
            "credential_use": False,
            "r2_r3_access": False,
            "scheduler_or_background_processes": False,
            "wallet_signer_transaction_actions": False,
            "cash_spend_usd_cents": 0,
            "task30_trial_or_acceptance": False,
        },
    }


def payload(candles: list[list[float]], trades: list[tuple[str, str]]) -> tuple[dict, dict]:
    return (
        {
            "data": {
                "type": "ohlcv_request_response",
                "attributes": {"ohlcv_list": candles},
            },
            "meta": {"base": {"address": "BASE"}},
        },
        {
            "data": [
                {
                    "type": "trade",
                    "attributes": {
                        "block_timestamp": timestamp,
                        "from_token_address": "QUOTE",
                        "to_token_address": "BASE",
                        "price_to_in_usd": price,
                        "price_from_in_usd": "1",
                    },
                }
                for timestamp, price in trades
            ]
        },
    )


class Task30GeckoIntervalSemanticsTests(unittest.TestCase):
    def test_tracked_policy_is_schema_valid_and_binds_the_exact_two_request_plan(self) -> None:
        config_path = ROOT / "configs" / "task30_gecko_interval_semantics_v1.yaml"
        schema_path = ROOT / "catalog" / "schemas" / "task30_gecko_interval_semantics.schema.json"
        tracked_policy = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        jsonschema.validate(tracked_policy, schema)
        plan = build_request_plan(tracked_policy, before_timestamp=1_800)

        self.assertEqual(len(plan), 2)
        self.assertEqual(tracked_policy["project_sources_disposition"], "NO_CHANGE")

    def test_request_plan_is_exactly_two_keyless_gets_for_the_frozen_pool(self) -> None:
        plan = build_request_plan(policy(), before_timestamp=1_800)

        self.assertEqual(len(plan), 2)
        self.assertEqual([item["method"] for item in plan], ["GET", "GET"])
        self.assertEqual([item["host"] for item in plan], ["api.geckoterminal.com"] * 2)
        self.assertTrue(all(item["pool"] == POOL for item in plan))
        self.assertEqual(plan[0]["query"]["before_timestamp"], "1800")
        self.assertEqual(plan[0]["query"]["aggregate"], "15")
        self.assertEqual(plan[1]["path"], f"/api/v2/networks/solana/pools/{POOL}/trades")

    def test_policy_rejects_a_third_request_or_changed_host_before_io(self) -> None:
        third_request = policy()
        third_request["external_read"]["requests"].append(  # type: ignore[index]
            copy.deepcopy(third_request["external_read"]["requests"][1])  # type: ignore[index]
        )
        with self.assertRaisesRegex(IntervalSemanticsError, "REQUEST_COUNT_INVALID"):
            build_request_plan(third_request, before_timestamp=1_800)

        changed_host = policy()
        changed_host["external_read"]["public_base_url"] = "https://example.invalid/api/v2"  # type: ignore[index]
        with self.assertRaisesRegex(IntervalSemanticsError, "PUBLIC_ENDPOINT_INVALID"):
            build_request_plan(changed_host, before_timestamp=1_800)

    def test_cross_endpoint_prices_select_start_label_only_when_end_is_contradicted(self) -> None:
        ohlcv, trades = payload(
            [
                [900, 10, 12, 10, 11, 5],
                [1800, 20, 22, 20, 21, 5],
                [2700, 30, 32, 30, 31, 5],
            ],
            [("1970-01-01T00:16:40Z", "11"), ("1970-01-01T00:31:40Z", "21")],
        )

        result = evaluate_interval_semantics(policy(), ohlcv, trades)

        self.assertEqual(result["decision"], "START_LABELED")
        self.assertEqual(result["models"]["START_LABELED"]["contradictions"], 0)
        self.assertGreater(result["models"]["END_LABELED"]["contradictions"], 0)
        self.assertFalse(result["claims"]["continuous_panel"])
        self.assertFalse(result["claims"]["pit_admissible"])

    def test_cross_endpoint_prices_select_end_label_only_when_start_is_contradicted(self) -> None:
        ohlcv, trades = payload(
            [
                [900, 1, 3, 1, 2, 5],
                [1800, 10, 12, 10, 11, 5],
                [2700, 20, 22, 20, 21, 5],
            ],
            [("1970-01-01T00:16:40Z", "11"), ("1970-01-01T00:31:40Z", "21")],
        )

        result = evaluate_interval_semantics(policy(), ohlcv, trades)

        self.assertEqual(result["decision"], "END_LABELED")
        self.assertEqual(result["models"]["END_LABELED"]["contradictions"], 0)
        self.assertGreater(result["models"]["START_LABELED"]["contradictions"], 0)

    def test_equally_plausible_models_stay_inconclusive(self) -> None:
        ohlcv, trades = payload(
            [
                [900, 10, 22, 10, 11, 5],
                [1800, 10, 22, 10, 11, 5],
                [2700, 10, 22, 10, 11, 5],
            ],
            [("1970-01-01T00:16:40Z", "11"), ("1970-01-01T00:31:40Z", "21")],
        )

        result = evaluate_interval_semantics(policy(), ohlcv, trades)

        self.assertEqual(result["decision"], "INCONCLUSIVE_NO_UNIQUE_MODEL")
        self.assertIsNone(result["selected_model"])

    def test_malformed_payload_cannot_be_promoted(self) -> None:
        with self.assertRaisesRegex(IntervalSemanticsError, "OHLCV_PAYLOAD_INVALID"):
            evaluate_interval_semantics(policy(), {"data": {}}, {"data": []})


if __name__ == "__main__":
    unittest.main()
