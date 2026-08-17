from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.pmf_quote_slice_one_shot import (  # noqa: E402
    AUTHORITY_PHRASE,
    EXPECTED_HOST,
    QuoteShotError,
    QuoteShotTerminalError,
    bind_one_shot_prerequisites,
    build_order_url,
    execute_once,
    perform_http_get_once,
    project_quote,
    validate_policy,
)
import yaml  # noqa: E402


def _load_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "run_pmf_quote_slice_one_shot",
        ROOT / "scripts/run_pmf_quote_slice_one_shot.py",
    )
    if spec is None or spec.loader is None:
        raise AssertionError("runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONFIG = ROOT / "configs/pmf_quote_slice_one_shot_v1.yaml"
MODULE = ROOT / "src/solana_alpha_lab/pmf_quote_slice_one_shot.py"
SCRIPT = ROOT / "scripts/run_pmf_quote_slice_one_shot.py"


def _policy() -> dict[str, object]:
    value = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError("policy")
    return value


def _quote_body(**overrides: object) -> bytes:
    payload = {
        "transaction": None,
        "requestId": "req-1",
        "inAmount": "10000000",
        "outAmount": "12345",
        "router": "metis",
        "mode": "manual",
        **overrides,
    }
    return json.dumps(payload).encode("utf-8")


class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = io.BytesIO(body)
        self._status = status
        self.headers = {"Content-Type": "application/json"}

    def getcode(self) -> int:
        return self._status

    def read(self, n: int = -1) -> bytes:
        return self._body.read(n)

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _FakeOpener:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body = body
        self.status = status
        self.requests: list[object] = []

    def open(self, request: object, timeout: float = 0) -> _FakeResponse:
        self.requests.append(request)
        if self.status >= 400:
            raise urllib.error.HTTPError(
                "https://api.jup.ag/swap/v2/order",
                self.status,
                "error",
                hdrs=None,  # type: ignore[arg-type]
                fp=io.BytesIO(self.body),
            )
        return _FakeResponse(self.body, self.status)


class QuoteSliceOneShotTests(unittest.TestCase):
    def test_url_omits_taker_and_matches_a24_identity(self) -> None:
        url = build_order_url(_policy())
        self.assertIn("inputMint=So11111111111111111111111111111111111111112", url)
        self.assertIn("outputMint=DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK", url)
        self.assertIn("amount=10000000", url)
        self.assertNotIn("taker", url.lower())
        self.assertTrue(url.startswith("https://api.jup.ag/swap/v2/order?"))

    def test_source_does_not_call_execute_or_metis_logger(self) -> None:
        source = MODULE.read_text(encoding="utf-8") + SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("/execute", source)
        self.assertNotIn("/build", source)
        self.assertNotIn("jupiter_quote_logger", source)
        self.assertNotIn("swap/v1/quote", source)

    def test_quote_projection_rejects_transaction_bytes(self) -> None:
        with self.assertRaisesRegex(QuoteShotError, "QUOTE_RETURNED_TRANSACTION"):
            project_quote(_quote_body(transaction="AAAA"))

    def test_execute_once_projects_quote(self) -> None:
        opener = _FakeOpener(_quote_body())
        result = execute_once(_policy(), "test-key", opener=opener)
        self.assertEqual(result["terminal_outcome"], "QUOTE_OBSERVED")
        self.assertEqual(result["quote"]["out_amount"], "12345")
        self.assertFalse(result["quote"]["transaction_present"])
        request = opener.requests[0]
        headers = {str(key).lower(): value for key, value in request.header_items()}
        self.assertEqual(headers.get("x-api-key"), "test-key")
        self.assertNotIn("taker", request.full_url.lower())

    def test_empty_key_omits_header(self) -> None:
        opener = _FakeOpener(_quote_body())
        execute_once(_policy(), "", opener=opener)
        request = opener.requests[0]
        headers = {str(key).lower(): value for key, value in request.header_items()}
        self.assertNotIn("x-api-key", headers)

    def test_http_error_is_terminal(self) -> None:
        opener = _FakeOpener(b'{"error":"no"}', status=401)
        with self.assertRaises(QuoteShotTerminalError) as caught:
            execute_once(_policy(), "test-key", opener=opener)
        self.assertEqual(str(caught.exception), "HTTP_STATUS_ERROR")
        raw = perform_http_get_once(_policy(), "test-key", opener=_FakeOpener(b'{"error":"no"}', status=401))
        self.assertEqual(raw["http_status"], 401)

    def test_prerequisites_bind_offline_slice(self) -> None:
        result = bind_one_shot_prerequisites(ROOT, _policy())
        self.assertEqual(result["terminal"], "PMF_QUOTE_SLICE_BOUND_CALL_NOT_AUTHORIZED")
        validate_policy(_policy(), result)

    def test_run_capture_writes_sanitized_receipt(self) -> None:
        opener = _FakeOpener(_quote_body())
        with tempfile.TemporaryDirectory() as tmp:
            raw_root = Path(tmp) / "raw"
            receipt_path = Path(tmp) / "receipt.json"
            receipt = _load_runner().run_capture(
                authority_phrase=AUTHORITY_PHRASE,
                raw_root=raw_root,
                receipt_path=receipt_path,
                preflight_fn=lambda *_a, **_k: {
                    "schema": "smial.pmf-quote-slice-one-shot.credential-free-preflight",
                    "schema_version": "1.0",
                    "observed_at": "2026-08-17T00:00:00Z",
                    "host": EXPECTED_HOST,
                    "port": 443,
                    "dns_resolved": True,
                    "tcp_443": True,
                    "tls_verified": True,
                    "tls_version": "TLSv1.3",
                    "credential_reads": 0,
                    "provider_requests": 0,
                },
                credential_loader=lambda: "test-key",
                executor=lambda policy, key, opener=None: execute_once(
                    policy, key, opener=opener
                ),
                clock=lambda: datetime(2026, 8, 17, tzinfo=UTC),
                nonce_factory=lambda: "abcd",
                opener=opener,
            )
            self.assertEqual(receipt["terminal_outcome"], "QUOTE_OBSERVED")
            self.assertEqual(receipt["authority"]["execute_calls"], 0)
            self.assertEqual(
                receipt["request"]["output_mint"],
                "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK",
            )
            self.assertEqual(receipt["request"]["taker"], "OMITTED_QUOTE_ONLY")
            self.assertNotIn("test-key", json.dumps(receipt))
            dumped = receipt_path.read_text(encoding="utf-8")
            self.assertNotIn("AAAA", dumped)
            self.assertIn("12345", dumped)

    def test_live_receipt_binds_a24_request_identity(self) -> None:
        from solana_alpha_lab.pmf_quote_slice import (
            EXPECTED_INPUT_MINT,
            EXPECTED_NOTIONAL,
            EXPECTED_OUTPUT_MINT,
        )

        receipt = json.loads(
            (ROOT / "docs/evidence/pmf_quote_slice/a1_pmf_quote_slice_one_shot_runtime_receipt_v1.json").read_text(
                encoding="utf-8"
            )
        )
        request = receipt["request"]
        self.assertEqual(request["input_mint"], EXPECTED_INPUT_MINT)
        self.assertEqual(request["output_mint"], EXPECTED_OUTPUT_MINT)
        self.assertEqual(request["amount"], EXPECTED_NOTIONAL)
        self.assertEqual(request["taker"], "OMITTED_QUOTE_ONLY")
        self.assertEqual(receipt["terminal_outcome"], "QUOTE_OBSERVED")
        self.assertFalse(receipt["quote"]["transaction_present"])
        self.assertFalse(receipt["authority"]["taker_supplied"])
        self.assertEqual(receipt["authority"]["execute_calls"], 0)


if __name__ == "__main__":
    unittest.main()
