from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/task27_stage_b_exact_owner_packet_v1.yaml"
STAGE_A_RECEIPT_PATH = ROOT / "docs/evidence/task27/a1_stage_a_public_pair_identity_runtime_receipt_v1.json"
RUNTIME_RECEIPT_PATH = ROOT / "docs/evidence/task27/a1s2_stage_b_pool_history_runtime_receipt_v1.json"

TOKEN_REQUEST_ID = "T27-A1S2-STAGE-B-TOKEN-001"
POOL_REQUEST_ID = "T27-A1S2-STAGE-B-POOL-OHLCV-001"
TOKEN_RAW_SHA256 = "911139a37c84ea1c0fbeb249f268530fe20ca545a280158c58a5b66e6f9ae6cc"
POOL_RAW_SHA256 = "721fad404e9b0ef368f99de170fb096c14e58591ecc7556e25d2146340d6b981"
PROJECTION_SHA256 = "9caa0b4e4727ab79d3169f365fe4753459f6b8f4482f44d567e6e6579a602f9c"
RAW_MANIFEST_SHA256 = "9f0503175d84bbb4ece777b962b1bbdb61a951f10268203d4c43d26f65d1851f"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class StageBPoolHistoryRuntimeReceiptTests(unittest.TestCase):
    def test_runtime_receipt_binds_the_exact_authorized_route_without_task_acceptance(self) -> None:
        self.assertTrue(
            RUNTIME_RECEIPT_PATH.is_file(),
            "the Stage B runtime receipt must exist after the bounded provider run",
        )
        receipt = load_json(RUNTIME_RECEIPT_PATH)
        policy = load_yaml(CONFIG_PATH)

        self.assertEqual(receipt["schema"], "smial.task27.stage-b-pool-history.runtime-receipt")
        self.assertEqual(receipt["task_id"], "TASK-27")
        self.assertEqual(receipt["atom_id"], "T27-A1S2_STAGE_B_SOLANA_TRACKER_POOL_HISTORY_PILOT_V1")
        self.assertEqual(
            receipt["artifact_bindings"]["stage_b_config"],
            {
                "path": CONFIG_PATH.relative_to(ROOT).as_posix(),
                "sha256": sha256(CONFIG_PATH),
            },
        )
        self.assertEqual(
            receipt["artifact_bindings"]["stage_a_receipt"],
            {
                "path": STAGE_A_RECEIPT_PATH.relative_to(ROOT).as_posix(),
                "sha256": sha256(STAGE_A_RECEIPT_PATH),
            },
        )

        requests = receipt["requests"]
        self.assertIn(len(requests), (1, 2))
        self.assertLessEqual(len(requests), policy["request_cap"])
        self.assertEqual(requests[0]["request_id"], TOKEN_REQUEST_ID)
        self.assertEqual(requests[0]["method"], "GET")
        self.assertEqual(requests[0]["url"], policy["exact_urls"][0])
        self.assertEqual(requests[0]["query"], {})
        for request in requests:
            with self.subTest(request_id=request["request_id"]):
                self.assertEqual(request["method"], "GET")
                self.assertEqual(request["retries"], 0)
                self.assertFalse(request["redirect_followed"])
                self.assertIn(request["http_status"], range(100, 600))
                self.assertRegex(request["raw_sha256"], r"^[0-9a-f]{64}$")

        if len(requests) == 2:
            self.assertEqual(requests[1]["request_id"], POOL_REQUEST_ID)
            self.assertEqual(requests[1]["url"], policy["exact_urls"][1])
            self.assertEqual(requests[1]["query"], policy["chart_query"])
            self.assertEqual(receipt["decision"]["second_request_condition"], "TOKEN_IDENTITY_PASS")
        else:
            self.assertEqual(receipt["decision"]["second_request_condition"], "NOT_ATTEMPTED_AFTER_STOP")
            self.assertEqual(receipt["decision"]["terminal_disposition"], "STOPPED_NO_RETRY")

        raw_evidence = receipt["raw_evidence"]
        self.assertTrue(raw_evidence["outside_git"])
        self.assertTrue(raw_evidence["raw_manifest_relative_path"].startswith("local/task27_public_history_route/run="))
        self.assertEqual(raw_evidence["raw_manifest_sha256"], RAW_MANIFEST_SHA256)
        self.assertEqual(raw_evidence["panel_projection_sha256"], PROJECTION_SHA256)
        self.assertEqual([request["raw_sha256"] for request in requests], [TOKEN_RAW_SHA256, POOL_RAW_SHA256])

        self.assertEqual(
            receipt["identity_validation"],
            {
                "pool_address": "PASS",
                "base_mint": "PASS",
                "quote_mint": "PASS",
                "stage_a_dex_label": "pumpswap",
                "provider_market_label": "pumpfun-amm",
                "market_label_reconciliation": "UNRESOLVED_NOT_USED_AS_POOL_IDENTITY",
            },
        )
        self.assertEqual(
            receipt["panel_observation"],
            {
                "expected_natural_bars": 96,
                "observed_bars": 33,
                "unique_timestamps": 33,
                "first_timestamp": 1786100400,
                "last_timestamp": 1786185900,
                "strict_ascending": True,
                "aligned_to_frozen_grid": True,
                "missing_natural_bars": 63,
                "invalid_ohlcv_rows": 0,
                "missing_timestamps_sha256": "a9625839ce1b9169ef7a7ed6e21907158866ae21d09a0d982c522d8ff38aee96",
            },
        )
        self.assertEqual(receipt["decision"]["terminal_disposition"], "INCOMPLETE_PANEL_NOT_FEASIBLE")

        authority = receipt["authority"]
        self.assertEqual(authority["provider_api_rpc_wss_calls"], len(requests))
        self.assertTrue(authority["credential_use"])
        self.assertEqual(authority["r2_value_reads"], 0)
        self.assertEqual(authority["r3_value_or_path_reads"], 0)
        self.assertEqual(authority["wallet_signer_transaction_actions"], 0)
        self.assertEqual(authority["cash_spend_usd_cents"], 0)
        self.assertFalse(authority["task27_acceptance"])

        claims = receipt["claims"]
        self.assertFalse(claims["pit_admissible"])
        self.assertFalse(claims["alpha"])
        self.assertFalse(claims["execution"])
        self.assertFalse(claims["pnl"])
        self.assertFalse(claims["netreturn"])
        self.assertFalse(claims["cashflow"])
        self.assertEqual(claims["history_grade"], "ONE_INCOMPLETE_PANEL_OBSERVED_NOT_PIT_ADMISSIBLE")

        serialized = json.dumps(receipt, sort_keys=True).lower()
        for forbidden_marker in ("api-key", "api_key", "authorization", "private_key", "seed"):
            with self.subTest(forbidden_marker=forbidden_marker):
                self.assertNotIn(forbidden_marker, serialized)


if __name__ == "__main__":
    unittest.main()
