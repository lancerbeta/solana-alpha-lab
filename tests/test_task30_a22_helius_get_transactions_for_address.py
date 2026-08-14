from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_helius_get_transactions_for_address import (  # noqa: E402
    A22Error,
    A22TerminalError,
    REQUEST_ID,
    build_json_rpc_payload,
    classify_full_response,
    perform_http_post_once,
    write_raw_artifacts,
)


CONFIG_PATH = ROOT / "configs/task30_a22_helius_get_transactions_for_address_one_shot_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task30_a22_helius_get_transactions_for_address_one_shot.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task30/helius_get_transactions_for_address_v1.json"
CONTRACT_PATH = ROOT / "docs/contracts/task30_a22_helius_get_transactions_for_address_one_shot_contract_v1.md"
TASK_PATH = ROOT / "docs/tasks/TASK-30-a22-helius-get-transactions-for-address-one-shot.md"
SCRIPT_PATH = ROOT / "scripts/run_task30_a22_helius_get_transactions_for_address.py"
RUNTIME_PATH = ROOT / "docs/evidence/task30/a22_helius_get_transactions_for_address_runtime_receipt_v1.json"
ACCEPTANCE_PATH = ROOT / "docs/evidence/task30/a22_helius_get_transactions_for_address_acceptance_v1.json"
REGISTRY_ACCEPTANCE_PATH = ROOT / "docs/evidence/task30/a22_provider_route_capability_registry_acceptance_v1.json"

POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
BASE = "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK"
QUOTE = "So11111111111111111111111111111111111111112"
PROGRAM = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
ENDPOINT = "https://mainnet.helius-rpc.com/"
SINCE = 1_786_492_800
TILL = 1_786_579_200


def _load_yaml(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(path)
    return value


def _transaction(
    index: int,
    *,
    block_time: int | None = None,
    pool: str = POOL,
    err: object = None,
) -> dict[str, object]:
    return {
        "slot": 300_000_000 + index // 2,
        "transactionIndex": index % 2,
        "blockTime": SINCE + index if block_time is None else block_time,
        "transaction": {
            "signatures": [f"signature-{index}"],
            "message": {
                "accountKeys": [pool, PROGRAM, BASE, QUOTE],
                "instructions": [],
                "recentBlockhash": "blockhash",
            },
        },
        "meta": {
            "err": err,
            "fee": 5000,
            "preBalances": [1, 2, 3, 4],
            "postBalances": [1, 2, 3, 4],
            "preTokenBalances": [],
            "postTokenBalances": [],
            "logMessages": [],
        },
    }


def _response(rows: list[dict[str, object]], *, token: str | None = None) -> bytes:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": REQUEST_ID,
            "result": {"data": rows, "paginationToken": token},
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class _Headers(dict[str, str]):
    pass


class _Response:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body = body
        self.status = status
        self.headers = _Headers({"Content-Type": "application/json"})

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def getcode(self) -> int:
        return self.status

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


class _Opener:
    def __init__(self, response: _Response | Exception) -> None:
        self.response = response
        self.calls: list[tuple[object, float]] = []

    def open(self, request: object, timeout: float) -> _Response:
        self.calls.append((request, timeout))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class Task30A22HeliusGetTransactionsForAddressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = _load_yaml(CONFIG_PATH)
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_closed_policy_binds_exact_route_subject_window_and_one_shot(self) -> None:
        jsonschema.Draft202012Validator.check_schema(self.schema)
        jsonschema.validate(self.config, self.schema)
        self.assertEqual(self.config["atom_id"], "T30-A22_HELIUS_GET_TRANSACTIONS_FOR_ADDRESS_ONE_SHOT_V1")
        self.assertEqual(self.config["consumer"], "RC001-H07-H01-LIQUIDITY-RETENTION")
        self.assertEqual(self.config["provider_route"]["route_id"], "HELIUS-SOLANA-GET-TRANSACTIONS-FOR-ADDRESS-001")
        self.assertEqual(self.config["provider_route"]["endpoint"], ENDPOINT)
        self.assertEqual(self.config["reference_subject"]["pool_address"], POOL)
        self.assertEqual(self.config["reference_subject"]["base_mint"], BASE)
        self.assertEqual(self.config["reference_subject"]["quote_mint"], QUOTE)
        self.assertEqual(self.config["reference_subject"]["program_address"], PROGRAM)
        self.assertEqual(self.config["pilot_window"]["block_time_gte"], SINCE)
        self.assertEqual(self.config["pilot_window"]["block_time_lt"], TILL)
        self.assertEqual(self.config["runtime_limits"]["max_provider_requests"], 1)
        self.assertEqual(self.config["runtime_limits"]["max_full_transactions"], 1000)
        self.assertEqual(self.config["runtime_limits"]["max_helius_credits"], 100)
        self.assertFalse(self.config["execution_controls"]["retry"])
        self.assertFalse(self.config["execution_controls"]["fallback"])
        self.assertFalse(self.config["execution_controls"]["redirect"])
        self.assertFalse(self.config["claims"]["pit_admissible"])
        self.assertFalse(self.config["claims"]["task30_acceptance"])

    def test_request_payload_is_exact_and_secret_free(self) -> None:
        payload = build_json_rpc_payload(self.config)
        self.assertEqual(payload["jsonrpc"], "2.0")
        self.assertEqual(payload["id"], REQUEST_ID)
        self.assertEqual(payload["method"], "getTransactionsForAddress")
        self.assertEqual(payload["params"][0], POOL)
        self.assertEqual(
            payload["params"][1],
            {
                "commitment": "finalized",
                "encoding": "json",
                "filters": {
                    "blockTime": {"gte": SINCE, "lt": TILL},
                    "status": "succeeded",
                    "tokenAccounts": "none",
                },
                "limit": 1000,
                "maxSupportedTransactionVersion": 0,
                "sortOrder": "asc",
                "transactionDetails": "full",
            },
        )
        serialized = json.dumps(payload, sort_keys=True)
        self.assertNotIn("api-key", serialized)
        self.assertNotIn("HELIUS_API_KEY", serialized)

    def test_fixture_and_observed_batch_below_cap_are_route_fit_only(self) -> None:
        body = _response([_transaction(0), _transaction(1)])
        projection = classify_full_response(
            self.config,
            body,
            raw_sha256=hashlib.sha256(body).hexdigest(),
            response_bytes=len(body),
            observed_at="2026-08-14T12:00:00Z",
        )
        self.assertEqual(projection["terminal_outcome"], "BATCH_OBSERVED_LT_1000")
        self.assertEqual(projection["transaction_count"], 2)
        self.assertTrue(projection["route_fit_for_raw_batch"])
        self.assertFalse(projection["pit_admissible"])
        self.assertFalse(projection["h07_h01_evidence"])
        self.assertEqual(self.fixture["expected_terminal_outcome"], "BATCH_OBSERVED_LT_1000")

    def test_zero_is_typed_gap_and_cap_or_pagination_stops(self) -> None:
        empty_body = _response([])
        empty = classify_full_response(
            self.config,
            empty_body,
            raw_sha256=hashlib.sha256(empty_body).hexdigest(),
            response_bytes=len(empty_body),
            observed_at="2026-08-14T12:00:00Z",
        )
        self.assertEqual(empty["terminal_outcome"], "ZERO_RESULT_TYPED_GAP")
        self.assertFalse(empty["zero_activity_claim"])
        capped_body = _response([_transaction(index) for index in range(1000)], token="next-page")
        capped = classify_full_response(
            self.config,
            capped_body,
            raw_sha256=hashlib.sha256(capped_body).hexdigest(),
            response_bytes=len(capped_body),
            observed_at="2026-08-14T12:00:00Z",
        )
        self.assertEqual(capped["terminal_outcome"], "TRUNCATED_AT_1000_STOP")
        self.assertFalse(capped["route_fit_for_raw_batch"])
        short_paginated_body = _response([_transaction(0)], token="still-more")
        short_paginated = classify_full_response(
            self.config,
            short_paginated_body,
            raw_sha256=hashlib.sha256(short_paginated_body).hexdigest(),
            response_bytes=len(short_paginated_body),
            observed_at="2026-08-14T12:00:00Z",
        )
        self.assertEqual(short_paginated["terminal_outcome"], "PAGINATION_REQUIRED_STOP")

    def test_provider_error_is_typed_while_window_order_and_identity_drift_fail_closed(self) -> None:
        error_body = json.dumps(
            {"jsonrpc": "2.0", "id": REQUEST_ID, "error": {"code": -32601, "message": "method unavailable"}}
        ).encode()
        typed = classify_full_response(
            self.config,
            error_body,
            raw_sha256=hashlib.sha256(error_body).hexdigest(),
            response_bytes=len(error_body),
            observed_at="2026-08-14T12:00:00Z",
        )
        self.assertEqual(typed["terminal_outcome"], "PROVIDER_TYPED_FAILURE")
        ambiguous_error = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": REQUEST_ID,
                "error": {"code": -32601, "message": "method unavailable"},
                "result": {"data": [], "paginationToken": None},
            }
        ).encode()
        with self.assertRaisesRegex(A22Error, "ERROR_RESPONSE_SHAPE_DRIFT"):
            classify_full_response(
                self.config,
                ambiguous_error,
                raw_sha256=hashlib.sha256(ambiguous_error).hexdigest(),
                response_bytes=len(ambiguous_error),
                observed_at="2026-08-14T12:00:00Z",
            )
        outside = _response([_transaction(0, block_time=TILL)])
        with self.assertRaisesRegex(A22Error, "BLOCK_TIME_OUTSIDE_WINDOW"):
            classify_full_response(self.config, outside, raw_sha256=hashlib.sha256(outside).hexdigest(), response_bytes=len(outside), observed_at="2026-08-14T12:00:00Z")
        unordered = _response([_transaction(1), _transaction(0)])
        with self.assertRaisesRegex(A22Error, "RESULT_ORDER_DRIFT"):
            classify_full_response(self.config, unordered, raw_sha256=hashlib.sha256(unordered).hexdigest(), response_bytes=len(unordered), observed_at="2026-08-14T12:00:00Z")
        wrong_pool = _response([_transaction(0, pool="Other111111111111111111111111111111111111111")])
        with self.assertRaisesRegex(A22Error, "TARGET_POOL_NOT_BOUND"):
            classify_full_response(self.config, wrong_pool, raw_sha256=hashlib.sha256(wrong_pool).hexdigest(), response_bytes=len(wrong_pool), observed_at="2026-08-14T12:00:00Z")
        loaded_drift_document = json.loads(_response([_transaction(0)]))
        loaded_drift_document["result"]["data"][0]["meta"]["loadedAddresses"] = []
        loaded_drift = json.dumps(loaded_drift_document).encode()
        with self.assertRaisesRegex(A22Error, "LOADED_ADDRESSES_INVALID"):
            classify_full_response(
                self.config,
                loaded_drift,
                raw_sha256=hashlib.sha256(loaded_drift).hexdigest(),
                response_bytes=len(loaded_drift),
                observed_at="2026-08-14T12:00:00Z",
            )

    def test_transport_performs_exactly_one_post_and_retains_http_error(self) -> None:
        payload = build_json_rpc_payload(self.config)
        credential_value = "local-test-secret"
        success = _Opener(_Response(_response([])))
        result = perform_http_post_once(self.config, payload, credential_value, opener=success)
        self.assertEqual(len(success.calls), 1)
        request, timeout = success.calls[0]
        self.assertEqual(getattr(request, "method"), "POST")
        self.assertEqual(timeout, 30.0)
        self.assertIn("api" + "-key=" + "local-test-secret", getattr(request, "full_url"))
        safe = json.dumps({key: value for key, value in result.items() if key != "body"}, sort_keys=True)
        self.assertNotIn(credential_value, safe)
        self.assertEqual(result["request_count"], 1)

        http_error = urllib.error.HTTPError(
            ENDPOINT,
            403,
            "Forbidden",
            {"Content-Type": "application/json"},
            io.BytesIO(b'{"error":"forbidden"}'),
        )
        failed = _Opener(http_error)
        retained = perform_http_post_once(self.config, payload, credential_value, opener=failed)
        self.assertEqual(len(failed.calls), 1)
        self.assertEqual(retained["http_status"], 403)
        self.assertEqual(retained["body"], b'{"error":"forbidden"}')

    def test_transport_has_hard_byte_cap_and_no_retry(self) -> None:
        payload = build_json_rpc_payload(self.config)
        oversized = _Opener(_Response(b"x" * 25_000_001))
        with self.assertRaisesRegex(A22TerminalError, "RESPONSE_BYTES_EXCEEDED") as raised:
            perform_http_post_once(self.config, payload, "local-test-secret", opener=oversized)
        self.assertEqual(len(oversized.calls), 1)
        self.assertEqual(raised.exception.evidence["transport"]["request_count"], 1)

    def test_raw_retention_is_create_only_and_secret_free(self) -> None:
        body = _response([_transaction(0)])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = write_raw_artifacts(
                root,
                run_id="20260814T120000Z-test",
                response_body=body,
                request_body_sha256="e" * 64,
                observed_at="2026-08-14T12:00:00Z",
            )
            raw = root / "run=20260814T120000Z-test/raw_response.json"
            self.assertEqual(raw.read_bytes(), body)
            self.assertEqual(manifest["raw_sha256"], hashlib.sha256(body).hexdigest())
            self.assertNotIn("api-key", json.dumps(manifest, sort_keys=True))
            with self.assertRaisesRegex(A22Error, "RUN_ALREADY_EXISTS"):
                write_raw_artifacts(
                    root,
                    run_id="20260814T120000Z-test",
                    response_body=body,
                    request_body_sha256="e" * 64,
                    observed_at="2026-08-14T12:00:00Z",
                )

    def test_contract_and_task_keep_nonclaims_and_exact_owner_authority(self) -> None:
        contract = CONTRACT_PATH.read_text(encoding="utf-8")
        task = TASK_PATH.read_text(encoding="utf-8")
        self.assertIn("OK T30-A22 HELIUS_GET_TRANSACTIONS_FOR_ADDRESS_ONE_SHOT", task)
        self.assertIn("one provider POST", task)
        self.assertIn("No pagination", contract)
        self.assertIn("TASK-30 remains `BLOCKED_DATA`", contract)

    def test_live_receipt_and_acceptance_bind_exact_partial_page_without_promotion(self) -> None:
        runtime = json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))
        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        registry_acceptance = json.loads(REGISTRY_ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(runtime["terminal_outcome"], "PAGINATION_REQUIRED_STOP")
        self.assertEqual(runtime["transport"]["http_status"], 200)
        self.assertEqual(runtime["transport"]["request_count"], 1)
        self.assertEqual(runtime["transaction_count"], 520)
        self.assertTrue(runtime["pagination_token_present"])
        self.assertFalse(runtime["route_fit_for_raw_batch"])
        self.assertEqual(runtime["authority"]["retries"], 0)
        self.assertEqual(runtime["authority"]["fallbacks"], 0)
        self.assertEqual(runtime["authority"]["pagination_requests"], 0)
        self.assertEqual(acceptance["decision"], "ONE_SHOT_INCOMPLETE_PAGINATION_REQUIRED_NO_SECOND_REQUEST")
        self.assertEqual(acceptance["reuse_first"]["decision"], "ADOPT")
        self.assertFalse(acceptance["non_claims"]["account_plan_or_free_quota_verified"])
        self.assertEqual(registry_acceptance["added_route"]["last_success_http_status"], 200)
        self.assertFalse(registry_acceptance["added_route"]["complete_one_shot_batch"])
        for document in (acceptance, registry_acceptance):
            for binding in document["artifact_bindings"].values():
                path = ROOT / binding["path"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), binding["sha256"])

    def test_runner_preflights_before_key_read_and_writes_safe_receipt(self) -> None:
        spec = importlib.util.spec_from_file_location("task30_a22_runner_test", SCRIPT_PATH)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        events: list[str] = []
        preflight = {
            "schema": "smial.task30.helius-get-transactions-for-address.credential-free-preflight",
            "schema_version": "1.0",
            "observed_at": "2026-08-14T11:59:00Z",
            "host": "mainnet.helius-rpc.com",
            "port": 443,
            "dns_resolved": True,
            "tcp_443": True,
            "tls_verified": True,
            "tls_version": "TLSv1.3",
            "credential_reads": 0,
            "provider_requests": 0,
        }
        projection_body = _response([_transaction(0)])
        projection = classify_full_response(
            self.config,
            projection_body,
            raw_sha256=hashlib.sha256(projection_body).hexdigest(),
            response_bytes=len(projection_body),
            observed_at="2026-08-14T12:00:00Z",
        )

        def preflight_fn(*_args: object, **_kwargs: object) -> dict[str, object]:
            events.append("preflight")
            return preflight

        def credential_loader(name: str) -> str:
            events.append("credential")
            self.assertEqual(name, "HELIUS_API_KEY")
            return "local-test-secret"

        def executor(*_args: object, **_kwargs: object) -> dict[str, object]:
            events.append("execute")
            self.assertEqual(_args[1], "local-test-secret")
            return {
                "transport": {
                    "http_status": 200,
                    "content_type": "application/json",
                    "response_bytes": len(projection_body),
                    "request_body_sha256": "f" * 64,
                    "request_count": 1,
                },
                "raw_manifest": {
                    "run_id": "20260814T120000Z-test",
                    "response_bytes": len(projection_body),
                    "raw_sha256": hashlib.sha256(projection_body).hexdigest(),
                    "retention_class": "A4_OUTSIDE_GIT",
                },
                "projection": projection,
            }

        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "receipt.json"
            receipt = module.run_capture(
                authority_phrase="OK T30-A22 HELIUS_GET_TRANSACTIONS_FOR_ADDRESS_ONE_SHOT",
                policy=self.config,
                raw_root=Path(tmp) / "raw",
                receipt_path=receipt_path,
                preflight_fn=preflight_fn,
                credential_loader=credential_loader,
                executor=executor,
                clock=lambda: datetime(2026, 8, 14, 12, 0, tzinfo=UTC),
                nonce_factory=lambda: "test",
            )
            tracked = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(events, ["preflight", "credential", "execute"])
        self.assertEqual(receipt, tracked)
        self.assertEqual(receipt["terminal_outcome"], "BATCH_OBSERVED_LT_1000")
        self.assertEqual(receipt["authority"]["provider_requests"], 1)
        self.assertEqual(receipt["authority"]["credential_reads"], 1)
        self.assertNotIn("local-test-secret", json.dumps(receipt, sort_keys=True))

    def test_runner_refuses_wrong_authority_before_any_external_step(self) -> None:
        spec = importlib.util.spec_from_file_location("task30_a22_runner_refusal_test", SCRIPT_PATH)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        events: list[str] = []

        def forbidden(*_args: object, **_kwargs: object) -> object:
            events.append("called")
            raise AssertionError("external step must not run")

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(A22Error, "AUTHORITY_PHRASE_INVALID"):
                module.run_capture(
                    authority_phrase="wrong",
                    policy=self.config,
                    raw_root=Path(tmp) / "raw",
                    receipt_path=Path(tmp) / "receipt.json",
                    preflight_fn=forbidden,
                    credential_loader=forbidden,
                    executor=forbidden,
                    clock=lambda: datetime(2026, 8, 14, 12, 0, tzinfo=UTC),
                    nonce_factory=lambda: "test",
                )
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
