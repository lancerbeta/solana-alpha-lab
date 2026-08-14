from __future__ import annotations

import copy
import importlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from datetime import datetime

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
CONFIG_PATH = ROOT / "configs/task30_bitquery_named_partial_pit_route_capture_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task30_bitquery_named_partial_pit_route_capture.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task30/bitquery_named_partial_pit_route_capture_v1.json"
CONTRACT_PATH = ROOT / "docs/contracts/task30_bitquery_named_partial_pit_route_capture_contract_v1.md"
SCRIPT_PATH = ROOT / "scripts/run_task30_bitquery_named_partial_pit_route_capture.py"
MODULE_NAME = "solana_alpha_lab.task30_bitquery_named_partial_pit_route_capture"

POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
BASE = "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK"
QUOTE = "So11111111111111111111111111111111111111112"
PROGRAM = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
ENDPOINT = "https://streaming.bitquery.io/graphql"
SINCE = "2026-08-12T00:00:00Z"
TILL = "2026-08-13T00:00:00Z"


class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body = body
        self.status = status
        self.headers = {"Content-Type": "application/json"}
        self.read_limits: list[int] = []

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        self.read_limits.append(limit)
        return self.body[:limit]

    def getcode(self) -> int:
        return self.status


class _FakeOpener:
    def __init__(self, response: _FakeResponse | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[tuple[object, float]] = []

    def open(self, request: object, *, timeout: float) -> _FakeResponse:
        self.calls.append((request, timeout))
        if self.error is not None:
            raise self.error
        if self.response is None:
            raise AssertionError("fake response required")
        return self.response


class _FakeSocket:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeTlsSocket(_FakeSocket):
    def __enter__(self) -> "_FakeTlsSocket":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def version(self) -> str:
        return "TLSv1.3"


class _FakeSslContext:
    def __init__(self, tls_socket: _FakeTlsSocket) -> None:
        self.tls_socket = tls_socket
        self.calls: list[tuple[object, str]] = []

    def wrap_socket(self, raw_socket: object, *, server_hostname: str) -> _FakeTlsSocket:
        self.calls.append((raw_socket, server_hostname))
        return self.tls_socket


class Task30BitqueryNamedPartialPitRouteCaptureTests(unittest.TestCase):
    def _module(self):
        try:
            return importlib.import_module(MODULE_NAME)
        except ModuleNotFoundError as exc:
            self.fail(f"production module missing: {exc}")

    def _script_module(self):
        spec = importlib.util.spec_from_file_location("task30_bitquery_capture_script_test", SCRIPT_PATH)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _artifacts(self) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        for path in (CONFIG_PATH, SCHEMA_PATH, FIXTURE_PATH, CONTRACT_PATH):
            self.assertTrue(path.is_file(), f"missing artifact: {path.relative_to(ROOT)}")
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(config, dict)
        self.assertIsInstance(schema, dict)
        self.assertIsInstance(fixture, dict)
        return config, schema, fixture

    def test_policy_binds_one_bitquery_request_and_closed_identity(self) -> None:
        config, schema, _fixture = self._artifacts()
        jsonschema.validate(config, schema)
        self.assertEqual(config["provider_route"]["route_id"], "BITQUERY-SOLANA-PUMPSWAP-OHLCV-001")
        self.assertEqual(config["provider_route"]["endpoint"], ENDPOINT)
        self.assertEqual(config["provider_route"]["dataset"], "archive")
        self.assertEqual(config["reference_subject"]["pool_address"], POOL)
        self.assertEqual(config["reference_subject"]["base_mint"], BASE)
        self.assertEqual(config["reference_subject"]["quote_mint"], QUOTE)
        self.assertEqual(config["reference_subject"]["program_address"], PROGRAM)
        self.assertEqual(config["pilot_window"]["since_inclusive"], SINCE)
        self.assertEqual(config["pilot_window"]["till_exclusive"], TILL)
        self.assertEqual(config["pilot_window"]["expected_slots"], 96)
        self.assertEqual(config["route_feasibility"]["notional_usd"], [10, 25, 50, 100])
        self.assertEqual(config["route_feasibility"]["state"], "NOT_ESTABLISHED_FROM_HISTORICAL_OHLCV")
        self.assertEqual(config["runtime_limits"]["max_provider_requests"], 1)
        self.assertEqual(config["runtime_limits"]["max_response_bytes"], 2_000_000)
        self.assertEqual(config["runtime_limits"]["max_bitquery_points"], 100)
        self.assertFalse(config["execution_controls"]["retry"])
        self.assertFalse(config["execution_controls"]["fallback"])
        self.assertEqual(config["authority"]["cash_spend_usd_cents"], 0)
        self.assertFalse(config["claims"]["fillability"])
        self.assertFalse(config["claims"]["execution"])
        self.assertFalse(config["claims"]["task30_acceptance"])

    def test_cli_exposes_separate_preflight_and_capture_without_token_argument(self) -> None:
        self.assertTrue(SCRIPT_PATH.is_file(), f"missing artifact: {SCRIPT_PATH.relative_to(ROOT)}")
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--help"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        help_text = completed.stdout + completed.stderr
        self.assertIn("{preflight,capture}", help_text)
        self.assertNotIn("--token", help_text)

    def test_graphql_payload_uses_exact_archive_pool_and_closed_window_filters(self) -> None:
        module = self._module()
        config, _schema, _fixture = self._artifacts()
        payload = module.build_graphql_payload(config)
        query = payload["query"]
        variables = payload["variables"]
        self.assertIn("Solana(dataset: archive)", query)
        self.assertIn("bars: DEXTradeByTokens", query)
        self.assertIn("Time(interval: {count: 15, in: minutes})", query)
        self.assertIn("PriceInUSD(minimum: Block_Slot)", query)
        self.assertIn("PriceInUSD(maximum: Trade_PriceInUSD)", query)
        self.assertIn("sum(of: Trade_Side_AmountInUSD)", query)
        self.assertEqual(
            variables,
            {
                "since": SINCE,
                "till": TILL,
                "pool": POOL,
                "base": BASE,
                "quote": QUOTE,
                "program": PROGRAM,
            },
        )
        self.assertNotIn("ory_", json.dumps(payload, sort_keys=True))

    def test_two_observations_project_to_two_rows_and_94_typed_gaps(self) -> None:
        module = self._module()
        config, _schema, fixture = self._artifacts()
        projection = module.project_slots(
            config,
            fixture["response"],
            raw_sha256="a" * 64,
            response_bytes=1234,
            observed_at="2026-08-14T12:00:00Z",
        )
        self.assertEqual(projection["counts"], {"slots": 96, "observed": 2, "typed_gaps": 94})
        self.assertEqual(projection["terminal_outcome"], "PARTIAL_TYPED_GAP_PANEL")
        self.assertEqual(projection["slots"][0]["slot_start"], SINCE)
        self.assertEqual(projection["slots"][0]["state"], "OBSERVATION")
        self.assertEqual(projection["slots"][0]["open_usd"], "1.0")
        self.assertEqual(projection["slots"][1]["slot_start"], "2026-08-12T00:15:00Z")
        self.assertEqual(projection["slots"][1]["state"], "MISSING_UNKNOWN")
        self.assertEqual(projection["slots"][1]["gap_type"], "NO_OBSERVATION_RETURNED")
        for prohibited in ("open_usd", "high_usd", "low_usd", "close_usd", "volume_usd", "trade_count"):
            self.assertNotIn(prohibited, projection["slots"][1])
        self.assertEqual(projection["slots"][2]["slot_start"], "2026-08-12T00:30:00Z")
        self.assertEqual(projection["slots"][2]["state"], "OBSERVATION")
        self.assertEqual(projection["slots"][-1]["slot_end"], TILL)

    def test_graphql_errors_and_identity_or_grid_drift_fail_closed(self) -> None:
        module = self._module()
        config, _schema, fixture = self._artifacts()
        cases: list[tuple[str, dict[str, object], str]] = []
        cases.append(("graphql", {"errors": [{"message": "synthetic"}]}, "GRAPHQL_ERRORS_RETURNED"))
        for case_id, path, value, expected in (
            ("pool", ("Trade", "Market", "MarketAddress"), "wrong-pool", "POOL_IDENTITY_DRIFT"),
            ("base", ("Trade", "Currency", "MintAddress"), "wrong-base", "BASE_MINT_IDENTITY_DRIFT"),
            ("quote", ("Trade", "Side", "Currency", "MintAddress"), "wrong-quote", "QUOTE_MINT_IDENTITY_DRIFT"),
            ("program", ("Trade", "Dex", "ProgramAddress"), "wrong-program", "PROGRAM_IDENTITY_DRIFT"),
            ("off_grid", ("Block", "Timefield"), "2026-08-12T00:01:00Z", "SLOT_OFF_GRID"),
        ):
            response = copy.deepcopy(fixture["response"])
            node = response["data"]["Solana"]["bars"][0]
            for key in path[:-1]:
                node = node[key]
            node[path[-1]] = value
            cases.append((case_id, response, expected))
        duplicate = copy.deepcopy(fixture["response"])
        duplicate["data"]["Solana"]["bars"].append(copy.deepcopy(duplicate["data"]["Solana"]["bars"][0]))
        cases.append(("duplicate", duplicate, "DUPLICATE_SLOT"))

        for case_id, response, expected in cases:
            with self.subTest(case_id=case_id):
                with self.assertRaisesRegex(module.CaptureContractError, f"^{expected}$"):
                    module.project_slots(
                        config,
                        response,
                        raw_sha256="b" * 64,
                        response_bytes=100,
                        observed_at="2026-08-14T12:00:00Z",
                    )

    def test_http_transport_uses_one_post_and_returns_no_secret_metadata(self) -> None:
        module = self._module()
        config, _schema, fixture = self._artifacts()
        body = json.dumps(fixture["response"], separators=(",", ":")).encode("utf-8")
        response = _FakeResponse(body)
        opener = _FakeOpener(response=response)
        token = "ory_at_synthetic_unit_test_value_1234567890"
        result = module.perform_http_post_once(
            config,
            module.build_graphql_payload(config),
            token,
            opener=opener,
        )
        self.assertEqual(len(opener.calls), 1)
        request, timeout = opener.calls[0]
        self.assertEqual(request.full_url, ENDPOINT)
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.get_header("Authorization"), f"Bearer {token}")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(timeout, 30.0)
        self.assertEqual(response.read_limits, [2_000_001])
        self.assertEqual(result["response_bytes"], len(body))
        self.assertEqual(result["request_count"], 1)
        self.assertEqual(result["body"], body)
        sanitized = json.dumps({key: value for key, value in result.items() if key != "body"}, sort_keys=True)
        self.assertNotIn(token, sanitized)
        self.assertNotIn("Authorization", sanitized)

    def test_http_failure_or_byte_cap_does_not_retry(self) -> None:
        module = self._module()
        config, _schema, fixture = self._artifacts()
        payload = module.build_graphql_payload(config)
        failing = _FakeOpener(error=OSError("synthetic transport failure"))
        with self.assertRaisesRegex(module.CaptureTerminalError, "^TRANSPORT_ERROR$") as caught:
            module.perform_http_post_once(config, payload, "ory_at_synthetic_1234567890", opener=failing)
        self.assertEqual(len(failing.calls), 1)
        self.assertEqual(caught.exception.evidence["transport"]["request_count"], 1)
        self.assertIsNone(caught.exception.evidence["raw_manifest"])

        oversized_body = b"x" * 2_000_001
        oversized_response = _FakeResponse(oversized_body)
        oversized = _FakeOpener(response=oversized_response)
        with self.assertRaisesRegex(module.CaptureContractError, "^RESPONSE_BYTES_EXCEEDED$"):
            module.perform_http_post_once(config, payload, "ory_at_synthetic_1234567890", opener=oversized)
        self.assertEqual(len(oversized.calls), 1)

    def test_http_error_is_not_collapsed_into_transport_error(self) -> None:
        module = self._module()
        config, _schema, _fixture = self._artifacts()
        error_body = b'{"errors":[{"message":"synthetic unauthorized"}]}'
        http_error = urllib.error.HTTPError(
            ENDPOINT,
            401,
            "Unauthorized",
            {"Content-Type": "application/json"},
            io.BytesIO(error_body),
        )
        opener = _FakeOpener(error=http_error)
        result = module.perform_http_post_once(
            config,
            module.build_graphql_payload(config),
            "ory_at_synthetic_http_error_1234567890",
            opener=opener,
        )
        self.assertEqual(len(opener.calls), 1)
        self.assertEqual(result["http_status"], 401)
        self.assertEqual(result["body"], error_body)
        self.assertEqual(result["request_count"], 1)

    def test_http_terminal_error_retains_raw_and_sanitized_evidence(self) -> None:
        module = self._module()
        config, _schema, _fixture = self._artifacts()
        error_body = b'{"errors":[{"message":"synthetic unauthorized"}]}'
        http_error = urllib.error.HTTPError(
            ENDPOINT,
            401,
            "Unauthorized",
            {"Content-Type": "application/json"},
            io.BytesIO(error_body),
        )
        opener = _FakeOpener(error=http_error)
        token = "ory_at_synthetic_terminal_error_never_persist_1234567890"
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(module.CaptureTerminalError, "^HTTP_STATUS_ERROR$") as caught:
                module.execute_once(
                    config,
                    token,
                    Path(tmp),
                    run_id="t30-bitquery-http-terminal-test",
                    observed_at="2026-08-14T12:00:00Z",
                    opener=opener,
                )
            evidence = caught.exception.evidence
            self.assertEqual(evidence["transport"]["http_status"], 401)
            self.assertEqual(evidence["transport"]["request_count"], 1)
            self.assertEqual(evidence["raw_manifest"]["response_bytes"], len(error_body))
            self.assertEqual(
                (Path(tmp) / "run=t30-bitquery-http-terminal-test/raw_response.json").read_bytes(),
                error_body,
            )
            self.assertNotIn(token, json.dumps(evidence, sort_keys=True))

    def test_raw_writer_hashes_exact_bytes_and_never_persists_token(self) -> None:
        module = self._module()
        body = b'{"data":{"Solana":{"bars":[]}}}'
        token = "ory_at_synthetic_never_persist_1234567890"
        with tempfile.TemporaryDirectory() as tmp:
            manifest = module.write_raw_artifacts(
                Path(tmp),
                run_id="t30-bitquery-test-run",
                response_body=body,
                request_body_sha256="c" * 64,
                observed_at="2026-08-14T12:00:00Z",
            )
            run_root = Path(tmp) / "run=t30-bitquery-test-run"
            self.assertEqual((run_root / "raw_response.json").read_bytes(), body)
            stored_manifest = json.loads((run_root / "raw_manifest_v1.json").read_text(encoding="utf-8"))
            self.assertEqual(stored_manifest, manifest)
            self.assertEqual(manifest["response_bytes"], len(body))
            self.assertEqual(manifest["raw_sha256"], "5e9d0aabb2f82a2305d8d17c86d882837579a0a914d6a128bd87c37cf23d46c6")
            self.assertNotIn(token, json.dumps(manifest, sort_keys=True))

    def test_credential_free_preflight_binds_dns_tcp_and_verified_tls(self) -> None:
        module = self._module()
        config, _schema, _fixture = self._artifacts()
        raw_socket = _FakeSocket()
        tls_socket = _FakeTlsSocket()
        ssl_context = _FakeSslContext(tls_socket)
        resolver_calls: list[tuple[str, int, int]] = []
        connector_calls: list[tuple[tuple[str, int], float]] = []

        def resolver(host: str, port: int, *, type: int):
            resolver_calls.append((host, port, type))
            return [(2, type, 6, "", ("203.0.113.10", port))]

        def connector(address: tuple[str, int], *, timeout: float):
            connector_calls.append((address, timeout))
            return raw_socket

        receipt = module.credential_free_preflight(
            config,
            observed_at="2026-08-14T12:00:00Z",
            resolver=resolver,
            connector=connector,
            context_factory=lambda: ssl_context,
        )
        self.assertEqual(receipt["host"], "streaming.bitquery.io")
        self.assertEqual(receipt["port"], 443)
        self.assertTrue(receipt["dns_resolved"])
        self.assertTrue(receipt["tcp_443"])
        self.assertTrue(receipt["tls_verified"])
        self.assertEqual(receipt["tls_version"], "TLSv1.3")
        self.assertEqual(len(resolver_calls), 1)
        self.assertEqual(connector_calls, [(('streaming.bitquery.io', 443), 5.0)])
        self.assertEqual(ssl_context.calls, [(raw_socket, "streaming.bitquery.io")])
        self.assertTrue(tls_socket.closed)

    def test_execute_once_retains_raw_and_projects_without_retry(self) -> None:
        module = self._module()
        config, _schema, fixture = self._artifacts()
        body = json.dumps(fixture["response"], separators=(",", ":")).encode("utf-8")
        opener = _FakeOpener(response=_FakeResponse(body))
        token = "ory_at_synthetic_execute_once_never_persist_1234567890"
        with tempfile.TemporaryDirectory() as tmp:
            result = module.execute_once(
                config,
                token,
                Path(tmp),
                run_id="t30-bitquery-execute-once-test",
                observed_at="2026-08-14T12:00:00Z",
                opener=opener,
            )
            self.assertEqual(len(opener.calls), 1)
            self.assertEqual(result["transport"]["request_count"], 1)
            self.assertEqual(result["projection"]["counts"], {"slots": 96, "observed": 2, "typed_gaps": 94})
            self.assertEqual(result["raw_manifest"]["raw_sha256"], result["projection"]["raw_sha256"])
            retained = b"\n".join(path.read_bytes() for path in Path(tmp).rglob("*.*"))
            self.assertNotIn(token.encode("utf-8"), retained)

    def test_failed_preflight_blocks_credential_read_and_provider_request(self) -> None:
        module = self._module()
        config, _schema, fixture = self._artifacts()
        body = json.dumps(fixture["response"], separators=(",", ":")).encode("utf-8")
        opener = _FakeOpener(response=_FakeResponse(body))
        credential_reads: list[str] = []

        def credential_loader(name: str) -> str:
            credential_reads.append(name)
            return "ory_at_synthetic_should_not_be_read_1234567890"

        failed_preflight = {
            "schema": "smial.task30.bitquery-credential-free-preflight",
            "schema_version": "1.0",
            "observed_at": "2026-08-14T11:59:00Z",
            "host": "streaming.bitquery.io",
            "port": 443,
            "dns_resolved": True,
            "tcp_443": True,
            "tls_verified": False,
            "tls_version": "",
            "credential_reads": 0,
            "provider_requests": 0,
        }
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(module.CaptureContractError, "^PREFLIGHT_NOT_PASS$"):
                module.execute_after_preflight(
                    config,
                    failed_preflight,
                    credential_loader,
                    Path(tmp),
                    run_id="t30-bitquery-invalid-preflight",
                    observed_at="2026-08-14T12:00:00Z",
                    opener=opener,
                )
        self.assertEqual(credential_reads, [])
        self.assertEqual(opener.calls, [])

    def test_passed_preflight_allows_one_credential_read_and_one_request(self) -> None:
        module = self._module()
        config, _schema, fixture = self._artifacts()
        body = json.dumps(fixture["response"], separators=(",", ":")).encode("utf-8")
        opener = _FakeOpener(response=_FakeResponse(body))
        token = "ory_at_synthetic_preflight_gate_never_persist_1234567890"
        credential_reads: list[str] = []

        def credential_loader(name: str) -> str:
            credential_reads.append(name)
            return token

        passed_preflight = {
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
        with tempfile.TemporaryDirectory() as tmp:
            result = module.execute_after_preflight(
                config,
                passed_preflight,
                credential_loader,
                Path(tmp),
                run_id="t30-bitquery-valid-preflight",
                observed_at="2026-08-14T12:00:00Z",
                opener=opener,
            )
            retained = b"\n".join(path.read_bytes() for path in Path(tmp).rglob("*.*"))
            self.assertNotIn(token.encode("utf-8"), retained)
        self.assertEqual(credential_reads, ["BITQUERY_ACCESS_TOKEN"])
        self.assertEqual(len(opener.calls), 1)
        self.assertEqual(result["authority"]["credential_reads"], 1)
        self.assertEqual(result["authority"]["provider_requests"], 1)
        self.assertEqual(result["preflight"], passed_preflight)

    def test_unknown_stop_receipt_preserves_unknown_counts_and_nonclaims(self) -> None:
        module = self._module()
        config, _schema, _fixture = self._artifacts()
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
        terminal_error = module.CaptureTerminalError(
            "TRANSPORT_ERROR",
            evidence={
                "transport": {
                    "http_status": None,
                    "response_bytes": None,
                    "request_count": 1,
                    "request_body_sha256": "d" * 64,
                },
                "raw_manifest": None,
            },
        )
        receipt = module.build_unknown_stop_receipt(
            config,
            preflight,
            observed_at="2026-08-14T12:00:00Z",
            terminal_error=terminal_error,
        )
        self.assertEqual(receipt["terminal_outcome"], "ROUTE_UNKNOWN_STOP")
        self.assertEqual(
            receipt["panel_counts"],
            {"slots_expected": 96, "slots_observed": None, "typed_gaps": None},
        )
        self.assertFalse(receipt["raw_retention"]["raw_retained"])
        self.assertEqual(receipt["raw_retention"]["loss_reason"], "NO_RESPONSE_BYTES_AVAILABLE")
        self.assertEqual(receipt["authority"]["provider_requests"], 1)
        self.assertFalse(receipt["non_claims"]["missing_is_zero_or_flat"])
        self.assertNotIn("ory_", json.dumps(receipt, sort_keys=True))

    def test_cli_writes_terminal_receipt_when_consumed_request_stops(self) -> None:
        module = self._module()
        script = self._script_module()
        config, _schema, _fixture = self._artifacts()
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
        terminal_error = module.CaptureTerminalError(
            "TRANSPORT_ERROR",
            evidence={
                "transport": {
                    "http_status": None,
                    "content_type": None,
                    "response_bytes": None,
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
            script._load_policy = lambda: config
            script._read_preflight = lambda: preflight
            script._now_utc = lambda: datetime.fromisoformat("2026-08-14T12:00:00+00:00")
            script.execute_after_preflight = stop_execution
            result = script.run_capture()
            receipt = json.loads(script.RUNTIME_RECEIPT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(result["terminal_outcome"], "ROUTE_UNKNOWN_STOP")
        self.assertEqual(result["request_count"], 1)
        self.assertEqual(receipt["terminal_error"], "TRANSPORT_ERROR")
        self.assertEqual(receipt["panel_state"], "NOT_ESTABLISHED")


if __name__ == "__main__":
    unittest.main()
