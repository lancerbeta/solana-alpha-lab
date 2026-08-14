from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/task30_a21_patched_bitquery_one_shot_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task30_a21_patched_bitquery_one_shot.schema.json"
CONTRACT_PATH = ROOT / "docs/contracts/task30_a21_patched_bitquery_one_shot_contract_v1.md"
TASK_PATH = ROOT / "docs/tasks/TASK-30-a21-patched-bitquery-one-shot.md"
SCRIPT_PATH = ROOT / "scripts/run_task30_a21_patched_bitquery_one_shot.py"
A20_RUNTIME = ROOT / "docs/evidence/task30/a20p_bitquery_named_partial_pit_route_capture_runtime_receipt_v1.json"
A20_ACCEPTANCE = ROOT / "docs/evidence/task30/a20_bitquery_named_partial_pit_route_capture_acceptance_v1.json"
A20_SCRIPT = ROOT / "scripts/run_task30_bitquery_named_partial_pit_route_capture.py"

POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
BASE = "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK"
QUOTE = "So11111111111111111111111111111111111111112"
PROGRAM = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
ENDPOINT = "https://streaming.bitquery.io/graphql"
SINCE = "2026-08-12T00:00:00Z"
TILL = "2026-08-13T00:00:00Z"
PATCHED_HEAD = "3b532d6ad4a875837bee061ff2e7832e86344fdb"


class Task30A21PatchedBitqueryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.contract = CONTRACT_PATH.read_text(encoding="utf-8")
        cls.task = TASK_PATH.read_text(encoding="utf-8")
        cls.a20_runtime = json.loads(A20_RUNTIME.read_text(encoding="utf-8"))

    def _script_module(self):
        spec = importlib.util.spec_from_file_location("task30_a21_capture_script_test", SCRIPT_PATH)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def test_closed_policy_binds_same_route_and_authorizes_one_shot(self) -> None:
        jsonschema.validate(self.config, self.schema)
        self.assertEqual(self.config["atom_id"], "T30-A21_PATCHED_BITQUERY_ONE_SHOT_V1")
        self.assertEqual(self.config["spec_route"], "NONE")
        self.assertEqual(self.config["consumer"], "RC001-H07-H01-LIQUIDITY-RETENTION")
        route = self.config["provider_route"]
        self.assertEqual(route["route_id"], "BITQUERY-SOLANA-PUMPSWAP-OHLCV-001")
        self.assertEqual(route["endpoint"], ENDPOINT)
        subject = self.config["reference_subject"]
        self.assertEqual(subject["pool_address"], POOL)
        self.assertEqual(subject["base_mint"], BASE)
        self.assertEqual(subject["quote_mint"], QUOTE)
        self.assertEqual(subject["program_address"], PROGRAM)
        window = self.config["pilot_window"]
        self.assertEqual(window["since_inclusive"], SINCE)
        self.assertEqual(window["till_exclusive"], TILL)
        self.assertEqual(window["expected_slots"], 96)
        self.assertEqual(self.config["runtime_limits"]["max_provider_requests"], 1)
        self.assertFalse(self.config["execution_controls"]["retry"])
        self.assertFalse(self.config["execution_controls"]["fallback"])
        self.assertTrue(self.config["external_authority"]["capture_authorized"])
        self.assertEqual(self.config["external_authority"]["provider_api_graphql_calls_authorized"], 1)
        self.assertEqual(self.config["authority"]["provider_api_rpc_wss_calls"], 1)
        self.assertFalse(self.config["claims"]["pit_admissible"])
        self.assertFalse(self.config["claims"]["task30_acceptance"])

    def test_reopen_binds_a20_unknown_stop_and_patched_main(self) -> None:
        basis = self.config["reopen_basis"]
        self.assertEqual(basis["patched_client_head"], PATCHED_HEAD)
        self.assertEqual(
            basis["decision"],
            "PATCHED_CLIENT_SAME_ROUTE_ONE_SHOT_OWNER_GATE",
        )
        self.assertEqual(self.a20_runtime["terminal_outcome"], "ROUTE_UNKNOWN_STOP")
        self.assertIsNone(self.a20_runtime["transport"]["http_status"])
        self.assertTrue(A20_ACCEPTANCE.is_file())
        self.assertIn("HTTPError", self.contract)
        self.assertIn(PATCHED_HEAD, self.task)

    def test_a20_receipts_and_script_paths_stay_immutable(self) -> None:
        retention = self.config["retention"]
        self.assertTrue(retention["a20_receipts_immutable"])
        self.assertEqual(
            retention["tracked_projection"],
            "docs/evidence/task30/a21p_patched_bitquery_one_shot_runtime_receipt_v1.json",
        )
        self.assertEqual(retention["raw_root"], "local/task30_a21_bitquery_one_shot")
        self.assertNotEqual(
            retention["tracked_projection"],
            "docs/evidence/task30/a20p_bitquery_named_partial_pit_route_capture_runtime_receipt_v1.json",
        )
        script = A20_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("a20p_bitquery_named_partial_pit_route_capture_runtime_receipt_v1.json", script)
        self.assertNotIn("a21p_patched_bitquery_one_shot_runtime_receipt_v1.json", script)
        self.assertTrue(self.config["evidence_retention"]["http_error_status_required"])

    def test_cli_refuses_unauthorized_policy_and_a20_paths(self) -> None:
        script = self._script_module()
        unauthorized = json.loads(json.dumps(self.config))
        unauthorized["external_authority"]["capture_authorized"] = False
        with tempfile.TemporaryDirectory() as tmp:
            script.RUNTIME_RECEIPT_PATH = Path(tmp) / "a21.json"
            script.RAW_ROOT = Path(tmp) / "raw"
            script.PREFLIGHT_PATH = Path(tmp) / "preflight.json"
            script._load_policy = lambda: unauthorized
            with self.assertRaisesRegex(script.CaptureContractError, "CAPTURE_NOT_AUTHORIZED"):
                script.run_capture()
        self.assertTrue(str(script.RUNTIME_RECEIPT_PATH).replace("\\", "/").endswith(
            "docs/evidence/task30/a21p_patched_bitquery_one_shot_runtime_receipt_v1.json"
        ) or script.RUNTIME_RECEIPT_PATH.name == "a21.json")
        self.assertNotIn("a20p_bitquery", str(script.RUNTIME_RECEIPT_PATH))

    def test_cli_writes_a21_terminal_receipt_without_touching_a20(self) -> None:
        from solana_alpha_lab.task30_bitquery_named_partial_pit_route_capture import CaptureTerminalError

        script = self._script_module()
        a20_before = A20_RUNTIME.read_text(encoding="utf-8")
        preflight = {
            "schema": "smial.task30.bitquery-credential-free-preflight",
            "schema_version": "1.0",
            "observed_at": "2026-08-14T11:59:00Z",
            "host": "streaming.bitquery.io",
            "port": 443,
            "dns_resolved": True,
            "tcp_443": True,
            "tls_verified": True,
            "tls_version": "TLSv1.3",
            "credential_reads": 0,
            "provider_requests": 0,
        }
        terminal_error = CaptureTerminalError(
            "HTTP_STATUS_ERROR",
            evidence={
                "transport": {
                    "http_status": 401,
                    "content_type": "application/json",
                    "response_bytes": 12,
                    "request_body_sha256": "e" * 64,
                    "request_count": 1,
                },
                "raw_manifest": None,
            },
        )

        def stop_execution(*_args: object, **_kwargs: object):
            raise terminal_error

        with tempfile.TemporaryDirectory() as tmp:
            script.RUNTIME_RECEIPT_PATH = Path(tmp) / "runtime.json"
            script.RAW_ROOT = Path(tmp) / "raw"
            script.PREFLIGHT_PATH = Path(tmp) / "preflight.json"
            script._load_policy = lambda: self.config
            script._read_preflight = lambda: preflight
            script._now_utc = lambda: datetime.fromisoformat("2026-08-14T12:00:00+00:00")
            script.execute_after_preflight = stop_execution
            result = script.run_capture()
            receipt = json.loads(script.RUNTIME_RECEIPT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(result["terminal_outcome"], "ROUTE_UNKNOWN_STOP")
        self.assertEqual(receipt["receipt_id"], "EVIDENCE-T30-A21P-PATCHED-BITQUERY-ONE-SHOT-001")
        self.assertEqual(receipt["atom_id"], "T30-A21_PATCHED_BITQUERY_ONE_SHOT_V1")
        self.assertEqual(receipt["transport"]["http_status"], 401)
        self.assertEqual(A20_RUNTIME.read_text(encoding="utf-8"), a20_before)

    def test_a21_runtime_retains_http_403_and_leaves_a20_unknown(self) -> None:
        a21_runtime = ROOT / "docs/evidence/task30/a21p_patched_bitquery_one_shot_runtime_receipt_v1.json"
        receipt = json.loads(a21_runtime.read_text(encoding="utf-8"))
        self.assertEqual(receipt["receipt_id"], "EVIDENCE-T30-A21P-PATCHED-BITQUERY-ONE-SHOT-001")
        self.assertEqual(receipt["atom_id"], "T30-A21_PATCHED_BITQUERY_ONE_SHOT_V1")
        self.assertEqual(receipt["terminal_outcome"], "ROUTE_UNKNOWN_STOP")
        self.assertEqual(receipt["terminal_error"], "HTTP_STATUS_ERROR")
        self.assertEqual(receipt["transport"]["http_status"], 403)
        self.assertEqual(receipt["transport"]["request_count"], 1)
        self.assertTrue(receipt["raw_retention"]["raw_retained"])
        self.assertEqual(receipt["authority"]["retries"], 0)
        self.assertEqual(receipt["authority"]["fallbacks"], 0)
        self.assertIsNone(self.a20_runtime["transport"]["http_status"])
        self.assertEqual(self.a20_runtime["terminal_error"], "TRANSPORT_ERROR")


if __name__ == "__main__":
    unittest.main()
