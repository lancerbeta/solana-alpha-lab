from __future__ import annotations

import importlib
import hashlib
import inspect
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_helius_bounded_pagination import (  # noqa: E402
    A23Error,
    A23TerminalError,
    build_continuation_payload,
    cursor_sha256,
    execute_bounded_pagination,
    validate_full_page,
)


POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
A22_REQUEST_ID = "task30-a22-helius-get-transactions-for-address"
SINCE = 1_786_492_800
TILL = 1_786_579_200
CONFIG_PATH = ROOT / "configs/task30_a23_helius_bounded_pagination_complete_batch_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task30_a23_helius_bounded_pagination_complete_batch.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task30/helius_bounded_pagination_v1.json"
CONTRACT_PATH = ROOT / "docs/contracts/task30_a23_helius_bounded_pagination_complete_batch_contract_v1.md"
SCRIPT_PATH = ROOT / "scripts/run_task30_a23_helius_bounded_pagination.py"
RUNTIME_PATH = ROOT / "docs/evidence/task30/a23_helius_bounded_pagination_runtime_receipt_v1.json"
ACCEPTANCE_PATH = ROOT / "docs/evidence/task30/a23_helius_bounded_pagination_acceptance_v1.json"
RAW_ROOT = ROOT / "local/task30_a23_helius_bounded_pagination"


def _row(slot: int, index: int, signature: str, *, block_time: int) -> dict[str, object]:
    return {
        "slot": slot,
        "transactionIndex": index,
        "blockTime": block_time,
        "transaction": {
            "signatures": [signature],
            "message": {
                "accountKeys": [POOL],
                "instructions": [],
                "recentBlockhash": "blockhash",
            },
        },
        "meta": {
            "err": None,
            "fee": 5000,
            "preBalances": [1],
            "postBalances": [1],
            "preTokenBalances": [],
            "postTokenBalances": [],
            "innerInstructions": [],
            "logMessages": [],
            "loadedAddresses": {"writable": [], "readonly": []},
        },
    }


def _response(request_id: str, rows: list[dict[str, object]], token: str | None) -> bytes:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"data": rows, "paginationToken": token},
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _policy(first_page: bytes, *, count: int, cursor_hash: str) -> dict[str, object]:
    return {
        "atom_id": "T30-A23_HELIUS_BOUNDED_PAGINATION_COMPLETE_BATCH_V1",
        "provider_route": {
            "route_id": "HELIUS-SOLANA-GET-TRANSACTIONS-FOR-ADDRESS-001",
            "endpoint": "https://mainnet.helius-rpc.com/",
            "method": "getTransactionsForAddress",
        },
        "reference_subject": {"pool_address": POOL},
        "request": {
            "transaction_details": "full",
            "sort_order": "asc",
            "limit": 1000,
            "commitment": "finalized",
            "encoding": "json",
            "max_supported_transaction_version": 0,
            "status": "succeeded",
            "token_accounts": "none",
        },
        "pilot_window": {
            "since_inclusive": "2026-08-12T00:00:00Z",
            "till_exclusive": "2026-08-13T00:00:00Z",
            "block_time_gte": SINCE,
            "block_time_lt": TILL,
        },
        "first_page_binding": {
            "request_id": A22_REQUEST_ID,
            "raw_sha256": hashlib.sha256(first_page).hexdigest(),
            "transaction_count": count,
            "cursor_sha256": cursor_hash,
        },
        "runtime_limits": {
            "max_credential_free_preflights": 1,
            "max_continuation_requests": 2,
            "max_response_bytes_per_page": 25_000_000,
            "max_new_response_bytes_total": 50_000_000,
            "timeout_seconds": 30,
            "max_full_transactions_per_page": 1000,
            "max_helius_credits_per_page": 100,
            "max_helius_credits_total": 200,
        },
        "execution_controls": {
            "retry": False,
            "fallback": False,
            "redirect": False,
            "pagination": True,
            "scheduler": False,
            "background_process": False,
        },
    }


def _load_runner() -> object:
    spec = importlib.util.spec_from_file_location("task30_a23_runner", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("runner import spec unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Task30A23HeliusBoundedPaginationApiTests(unittest.TestCase):
    def test_public_api_exists_for_bounded_continuation(self) -> None:
        """Catches an A23 implementation that omits the bounded-pagination seam."""

        try:
            module = importlib.import_module(
                "solana_alpha_lab.task30_helius_bounded_pagination"
            )
        except ModuleNotFoundError:
            module = None

        self.assertIsNotNone(module)
        for name in (
            "A23Error",
            "A23TerminalError",
            "build_continuation_payload",
            "cursor_sha256",
            "validate_full_page",
            "execute_bounded_pagination",
        ):
            self.assertTrue(callable(getattr(module, name, None)), name)


class Task30A23HeliusBoundedPaginationBehaviorTests(unittest.TestCase):
    def test_acceptance_binds_complete_batch_without_task30_promotion(self) -> None:
        """Catches an acceptance that overclaims or points at stale artifacts."""

        self.assertTrue(ACCEPTANCE_PATH.is_file(), ACCEPTANCE_PATH)
        acceptance = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(acceptance["decision"], "COMPLETE_RAW_BATCH_CANDIDATE")
        self.assertEqual(acceptance["task_state"], "BLOCKED_DATA")
        self.assertEqual(acceptance["route_observation"]["provider_requests"], 1)
        self.assertEqual(acceptance["route_observation"]["total_transaction_count"], 520)
        self.assertFalse(acceptance["non_claims"]["pit_admissible"])
        self.assertFalse(acceptance["non_claims"]["task30_acceptance"])
        for binding in acceptance["artifact_bindings"].values():
            path = ROOT / binding["path"]
            self.assertTrue(path.is_file(), path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), binding["sha256"])

    def test_live_receipt_binds_the_exact_create_only_raw_run(self) -> None:
        """Catches a page hash that cannot be resolved to its retained run."""

        receipt = json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))
        self.assertIn("run_id", receipt)
        raw_path = (
            RAW_ROOT
            / f"run={receipt['run_id']}"
            / "page=001"
            / "raw_response.json"
        )
        self.assertTrue(raw_path.is_file(), raw_path)
        raw = raw_path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), receipt["raw_manifests"][0]["raw_sha256"])
        self.assertEqual(len(raw), receipt["raw_manifests"][0]["response_bytes"])
        self.assertEqual(receipt["terminal_outcome"], "COMPLETE_RAW_BATCH_CANDIDATE")
        self.assertEqual(receipt["provider_requests"], 1)
        self.assertEqual(receipt["total_transaction_count"], 520)
        self.assertEqual(receipt["page_summaries"][1]["transaction_count"], 0)
        self.assertFalse(receipt["page_summaries"][1]["cursor_present"])

    def test_runner_preflights_before_one_credential_read_and_execution(self) -> None:
        """Catches credential access before preflight or more than one local read."""

        self.assertTrue(SCRIPT_PATH.is_file(), SCRIPT_PATH)
        runner = _load_runner()
        self.assertIn("first_page_verifier", inspect.signature(runner.run_capture).parameters)
        first = _response(A22_REQUEST_ID, [_row(10, 0, "sig-0", block_time=SINCE)], "300000000:1")
        policy = _policy(first, count=1, cursor_hash=cursor_sha256("300000000:1"))
        policy["external_authority"] = {
            "capture_authorized": True,
            "owner_phrase": "OK T30-A23 HELIUS_BOUNDED_PAGINATION_COMPLETE_BATCH",
        }
        policy["provider_route"]["route_id"] = "HELIUS-SOLANA-GET-TRANSACTIONS-FOR-ADDRESS-001"  # type: ignore[index]
        policy["claims"] = {"pit_admissible": False, "h07_h01_evidence": False, "task30_acceptance": False}
        events: list[str] = []

        def preflight_fn(_policy: object, *, observed_at: str) -> dict[str, object]:
            events.append("preflight")
            return {
                "schema": "smial.task30.helius-get-transactions-for-address.credential-free-preflight",
                "schema_version": "1.0",
                "observed_at": observed_at,
                "host": "mainnet.helius-rpc.com",
                "port": 443,
                "dns_resolved": True,
                "tcp_443": True,
                "tls_verified": True,
                "tls_version": "TLSv1.3",
                "credential_reads": 0,
                "provider_requests": 0,
            }

        def credential_loader(name: str) -> str:
            events.append("credential")
            self.assertEqual(name, "HELIUS_API_KEY")
            return "local-test-key"

        def first_page_verifier(_policy: object, path: Path) -> object:
            events.append("verify-first-page")
            self.assertTrue(path.is_file())
            return object()

        def executor(*_args: object, **_kwargs: object) -> dict[str, object]:
            events.append("execute")
            return {
                "terminal_outcome": "COMPLETE_RAW_BATCH_CANDIDATE",
                "provider_requests": 1,
                "a22_first_page_reused": True,
                "a22_first_page_refetched": False,
                "total_transaction_count": 2,
                "new_response_bytes": 100,
                "credits_upper_bound": 10,
                "page_summaries": [],
                "raw_manifests": [],
                "complete_raw_batch_candidate": True,
                "pit_admissible": False,
                "h07_h01_evidence": False,
                "task30_acceptance": False,
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_path = root / "a22.json"
            first_path.write_bytes(first)
            receipt_path = root / "receipt.json"
            receipt = runner.run_capture(
                authority_phrase="OK T30-A23 HELIUS_BOUNDED_PAGINATION_COMPLETE_BATCH",
                policy=policy,
                a22_raw_path=first_path,
                raw_root=root / "a23",
                receipt_path=receipt_path,
                preflight_fn=preflight_fn,
                first_page_verifier=first_page_verifier,
                credential_loader=credential_loader,
                executor=executor,
                clock=lambda: datetime(2026, 8, 15, tzinfo=UTC),
                nonce_factory=lambda: "abcd1234",
            )

        self.assertEqual(
            events,
            ["preflight", "verify-first-page", "credential", "execute"],
        )
        self.assertEqual(receipt["authority"]["credential_reads"], 1)
        self.assertEqual(receipt["authority"]["provider_requests"], 1)
        self.assertNotIn("local-test-key", repr(receipt))

    def test_closed_policy_validates_and_builds_exact_first_continuation(self) -> None:
        """Catches schema or policy drift that changes the authorized request."""

        for path in (CONFIG_PATH, SCHEMA_PATH, FIXTURE_PATH, CONTRACT_PATH):
            self.assertTrue(path.is_file(), path)
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        jsonschema.Draft202012Validator(schema).validate(policy)
        payload = build_continuation_payload(
            policy,
            fixture["synthetic_cursor"],
            page_number=1,
        )

        self.assertEqual(policy["external_authority"]["provider_api_rpc_calls_authorized"], 2)
        self.assertEqual(policy["runtime_limits"]["max_helius_credits_total"], 200)
        self.assertEqual(policy["runtime_limits"]["max_new_response_bytes_total"], 50_000_000)
        self.assertEqual(payload["params"][1]["paginationToken"], fixture["synthetic_cursor"])
        self.assertFalse(policy["claims"]["pit_admissible"])
        self.assertFalse(policy["claims"]["task30_acceptance"])

    def test_cursor_hash_accepts_only_official_opaque_shape(self) -> None:
        """Catches cursor logging/acceptance that loses slot:position binding."""

        self.assertEqual(
            cursor_sha256("300000000:1"),
            "92ed770be2cc8e68cb69591fc4f7fa05cc9257d416502cecc36ef6ee9c0f0773",
        )
        for malformed in ("", "secret", "1:", ":1", "1:2:3", None):
            with self.subTest(malformed=malformed):
                with self.assertRaisesRegex(A23Error, "PAGINATION_CURSOR_MALFORMED"):
                    cursor_sha256(malformed)  # type: ignore[arg-type]

    def test_continuation_payload_changes_only_id_and_cursor(self) -> None:
        """Catches a continuation that drifts any frozen A22 request field."""

        first = _response(A22_REQUEST_ID, [_row(10, 0, "sig-0", block_time=SINCE)], "300000000:1")
        policy = _policy(first, count=1, cursor_hash=cursor_sha256("300000000:1"))

        payload = build_continuation_payload(policy, "300000000:1", page_number=1)

        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["id"], "task30-a23-helius-page-1")
        self.assertEqual(payload["method"], "getTransactionsForAddress")
        self.assertEqual(payload["params"][0], POOL)  # type: ignore[index]
        self.assertEqual(
            payload["params"][1],  # type: ignore[index]
            {
                "transactionDetails": "full",
                "sortOrder": "asc",
                "limit": 1000,
                "commitment": "finalized",
                "encoding": "json",
                "maxSupportedTransactionVersion": 0,
                "filters": {
                    "blockTime": {"gte": SINCE, "lt": TILL},
                    "status": "succeeded",
                    "tokenAccounts": "none",
                },
                "paginationToken": "300000000:1",
            },
        )

    def test_page_validation_returns_safe_cursor_hash_and_strict_keys(self) -> None:
        """Catches malformed full rows, weak ordering, and raw cursor projection."""

        first = _response(A22_REQUEST_ID, [_row(10, 0, "sig-0", block_time=SINCE)], "300000000:1")
        policy = _policy(first, count=1, cursor_hash=cursor_sha256("300000000:1"))
        body = _response(
            "task30-a23-helius-page-1",
            [
                _row(11, 0, "sig-1", block_time=SINCE + 1),
                _row(11, 1, "sig-2", block_time=SINCE + 1),
            ],
            "300000001:0",
        )

        page = validate_full_page(policy, body, expected_request_id="task30-a23-helius-page-1")

        self.assertIsNotNone(page)
        self.assertEqual(page.transaction_count, 2)
        self.assertEqual(page.transaction_keys, ((11, 0), (11, 1)))
        self.assertEqual(page.primary_signatures, ("sig-1", "sig-2"))
        self.assertEqual(
            page.cursor_sha256,
            "79e5a297173f3bc6bbb51985256cc31593c7c19ad71b5a2a7d9d8089cb63b912",
        )
        self.assertNotIn("300000001:0", repr(page))
        self.assertEqual(page.credits_upper_bound, 10)

    def test_one_continuation_completes_and_does_not_refetch_page_zero(self) -> None:
        """Catches a loop that refetches A22 or spends a second request after null."""

        first = _response(A22_REQUEST_ID, [_row(10, 0, "sig-0", block_time=SINCE)], "300000000:1")
        policy = _policy(first, count=1, cursor_hash=cursor_sha256("300000000:1"))
        second = _response(
            "task30-a23-helius-page-1",
            [_row(11, 0, "sig-1", block_time=SINCE + 1)],
            None,
        )
        calls: list[dict[str, object]] = []

        def post_once(_policy: object, payload: dict[str, object], _key: str) -> dict[str, object]:
            calls.append(payload)
            return {
                "body": second,
                "http_status": 200,
                "content_type": "application/json",
                "response_bytes": len(second),
                "request_body_sha256": "a" * 64,
                "request_count": 1,
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_path = root / "a22.json"
            first_path.write_bytes(first)
            result = execute_bounded_pagination(
                policy,
                "local-test-key",
                first_path,
                root / "a23",
                run_id="test-run",
                observed_at="2026-08-15T00:00:00Z",
                post_fn=post_once,
            )

        self.assertIsInstance(result, dict)
        self.assertEqual(result["terminal_outcome"], "COMPLETE_RAW_BATCH_CANDIDATE")
        self.assertEqual(result["provider_requests"], 1)
        self.assertEqual(result["total_transaction_count"], 2)
        self.assertEqual(result["new_response_bytes"], len(second))
        self.assertEqual(result["credits_upper_bound"], 10)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["params"][1]["paginationToken"], "300000000:1")  # type: ignore[index]

    def test_two_non_null_pages_stop_incomplete_without_third_request(self) -> None:
        """Catches request-cap overrun and cursor-cycle acceptance."""

        first = _response(A22_REQUEST_ID, [_row(10, 0, "sig-0", block_time=SINCE)], "300000000:1")
        policy = _policy(first, count=1, cursor_hash=cursor_sha256("300000000:1"))
        pages = [
            _response("task30-a23-helius-page-1", [_row(11, 0, "sig-1", block_time=SINCE + 1)], "300000001:0"),
            _response("task30-a23-helius-page-2", [_row(12, 0, "sig-2", block_time=SINCE + 2)], "300000002:0"),
        ]
        calls = 0

        def post_once(_policy: object, _payload: dict[str, object], _key: str) -> dict[str, object]:
            nonlocal calls
            body = pages[calls]
            calls += 1
            return {
                "body": body,
                "http_status": 200,
                "content_type": "application/json",
                "response_bytes": len(body),
                "request_body_sha256": "b" * 64,
                "request_count": 1,
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_path = root / "a22.json"
            first_path.write_bytes(first)
            result = execute_bounded_pagination(
                policy,
                "local-test-key",
                first_path,
                root / "a23",
                run_id="test-run",
                observed_at="2026-08-15T00:00:00Z",
                post_fn=post_once,
            )

        self.assertIsInstance(result, dict)
        self.assertEqual(result["terminal_outcome"], "BOUNDED_PAGINATION_INCOMPLETE_STOP")
        self.assertEqual(result["provider_requests"], 2)
        self.assertEqual(calls, 2)
        self.assertLessEqual(result["credits_upper_bound"], 200)

    def test_global_duplicate_signature_is_terminal_and_secret_safe(self) -> None:
        """Catches page-local validation that misses a duplicate across pages."""

        first = _response(A22_REQUEST_ID, [_row(10, 0, "sig-0", block_time=SINCE)], "300000000:1")
        policy = _policy(first, count=1, cursor_hash=cursor_sha256("300000000:1"))
        duplicate = _response(
            "task30-a23-helius-page-1",
            [_row(11, 0, "sig-0", block_time=SINCE + 1)],
            None,
        )

        def post_once(_policy: object, _payload: dict[str, object], _key: str) -> dict[str, object]:
            return {
                "body": duplicate,
                "http_status": 200,
                "content_type": "application/json",
                "response_bytes": len(duplicate),
                "request_body_sha256": "c" * 64,
                "request_count": 1,
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_path = root / "a22.json"
            first_path.write_bytes(first)
            with self.assertRaisesRegex(A23TerminalError, "DUPLICATE_SIGNATURE") as raised:
                execute_bounded_pagination(
                    policy,
                    "local-test-key",
                    first_path,
                    root / "a23",
                    run_id="test-run",
                    observed_at="2026-08-15T00:00:00Z",
                    post_fn=post_once,
                )

        self.assertNotIn("local-test-key", repr(raised.exception.evidence))
        self.assertNotIn("300000000:1", repr(raised.exception.evidence))

    def test_consumed_request_with_transport_metadata_drift_is_terminal(self) -> None:
        """Catches a consumed POST that escapes without a tracked terminal receipt."""

        first = _response(A22_REQUEST_ID, [_row(10, 0, "sig-0", block_time=SINCE)], "300000000:1")
        policy = _policy(first, count=1, cursor_hash=cursor_sha256("300000000:1"))
        second = _response("task30-a23-helius-page-1", [], None)

        def post_once(_policy: object, _payload: dict[str, object], _key: str) -> dict[str, object]:
            return {
                "body": second,
                "http_status": 200,
                "content_type": "application/json",
                "response_bytes": len(second) + 1,
                "request_body_sha256": "d" * 64,
                "request_count": 1,
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_path = root / "a22.json"
            first_path.write_bytes(first)
            try:
                execute_bounded_pagination(
                    policy,
                    "local-test-key",
                    first_path,
                    root / "a23",
                    run_id="test-run",
                    observed_at="2026-08-15T00:00:00Z",
                    post_fn=post_once,
                )
            except A23TerminalError as exc:
                self.assertEqual(str(exc), "RESPONSE_BYTES_MISMATCH")
                self.assertEqual(exc.evidence["provider_requests"], 1)
                self.assertNotIn("local-test-key", repr(exc.evidence))
            except A23Error as exc:
                self.fail(f"consumed request escaped as non-terminal: {exc}")
            else:
                self.fail("malformed transport metadata was accepted")

    def test_raw_retention_failure_reports_received_bytes_exactly_once(self) -> None:
        """Catches double-counted bytes when retention fails after a consumed POST."""

        first = _response(A22_REQUEST_ID, [_row(10, 0, "sig-0", block_time=SINCE)], "300000000:1")
        policy = _policy(first, count=1, cursor_hash=cursor_sha256("300000000:1"))
        second = _response("task30-a23-helius-page-1", [], None)

        def post_once(_policy: object, _payload: dict[str, object], _key: str) -> dict[str, object]:
            return {
                "body": second,
                "http_status": 200,
                "content_type": "application/json",
                "response_bytes": len(second),
                "request_body_sha256": "e" * 64,
                "request_count": 1,
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_path = root / "a22.json"
            first_path.write_bytes(first)
            with mock.patch(
                "solana_alpha_lab.task30_helius_bounded_pagination._write_page",
                side_effect=OSError("synthetic retention failure"),
            ):
                with self.assertRaisesRegex(A23TerminalError, "RAW_RETENTION_ERROR") as raised:
                    execute_bounded_pagination(
                        policy,
                        "local-test-key",
                        first_path,
                        root / "a23",
                        run_id="test-run",
                        observed_at="2026-08-15T00:00:00Z",
                        post_fn=post_once,
                    )

        self.assertEqual(raised.exception.evidence["provider_requests"], 1)
        self.assertEqual(raised.exception.evidence["new_response_bytes"], len(second))
        self.assertNotIn("local-test-key", repr(raised.exception.evidence))


if __name__ == "__main__":
    unittest.main()
