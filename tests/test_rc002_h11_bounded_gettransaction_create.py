from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.pump_event_decoder import load_pinned_pump_event_plan  # noqa: E402
from solana_alpha_lab.rc002_h11_bounded_gettransaction_create import (  # noqa: E402
    ATOM_ID,
    ENDPOINT,
    GTA_CREATE_PAYLOAD_LEN,
    PINNED_SIGNATURE,
    REQUEST_ID,
    ROUTE_ID,
    TERMINAL_OUTCOMES,
    bind_get_transaction_request,
    classify_gettransaction_body,
    dns_tcp_preflight,
    perform_http_post_once,
)
from solana_alpha_lab.rc002_h11_truncation_vs_absence import IDL_RELATIVE  # noqa: E402

CONTRACT_PATH = ROOT / "docs/tasks/RC002-H11-BOUNDED-GETTRANSACTION-CREATE-V1.md"
PINNED_DECODER = ROOT / "src/solana_alpha_lab/pump_event_decoder.py"
SAME_195 = ROOT / "tests/fixtures/rc002_h11/gettransaction_create_same_195_v1.json"
NULL_RESULT = ROOT / "tests/fixtures/rc002_h11/gettransaction_create_null_v1.json"


class _FakeResponse:
    def __init__(self, payload: bytes, status: int = 200) -> None:
        self._payload = payload
        self._status = status

    def getcode(self) -> int:
        return self._status

    def read(self, _n: int) -> bytes:
        return self._payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _FakeOpener:
    def __init__(self, payload: bytes | None = None, *, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.opened = 0

    def open(self, _request: object, timeout: float = 0) -> _FakeResponse:
        self.opened += 1
        if self.error is not None:
            raise self.error
        assert self.payload is not None
        return _FakeResponse(self.payload)


class BoundedGetTransactionCreateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pinned = load_pinned_pump_event_plan(ROOT / IDL_RELATIVE)

    def test_contract_names_route_caps_and_signature(self) -> None:
        text = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn("task_id: RC002-H11-BOUNDED-GETTRANSACTION-CREATE-V1", text)
        self.assertIn("network: true", text)
        self.assertIn("credentials: false", text)
        self.assertIn(ROUTE_ID, text)
        self.assertIn(PINNED_SIGNATURE, text)
        self.assertIn("CREATE_GETTX_SAME_195_STILL_TRUNCATED", text)
        self.assertIn("PINNED_PUMP_DECODER_MUTATION", text)
        self.assertIn("HELIUS_OR_GTA_CALL", text)
        self.assertEqual(ATOM_ID, "RC002-H11-BOUNDED-GETTRANSACTION-CREATE-V1")
        self.assertTrue(PINNED_DECODER.is_file())

    def test_request_is_keyless_standard_gettransaction(self) -> None:
        bound = bind_get_transaction_request()
        self.assertEqual(bound["url"], ENDPOINT)
        self.assertNotIn("api-key", str(bound["url"]))
        body = json.loads(bytes(bound["body"]).decode("utf-8"))
        self.assertEqual(body["method"], "getTransaction")
        self.assertEqual(body["id"], REQUEST_ID)
        self.assertEqual(body["params"][0], PINNED_SIGNATURE)
        self.assertEqual(body["params"][1]["encoding"], "json")
        self.assertEqual(body["params"][1]["maxSupportedTransactionVersion"], 0)

    def test_wrong_signature_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            bind_get_transaction_request(signature="11111111111111111111111111111111")

    def test_same_195_fixture_is_still_truncated(self) -> None:
        body = SAME_195.read_bytes()
        result = classify_gettransaction_body(body, pinned=self.pinned)
        self.assertEqual(result["live_payload_len"], GTA_CREATE_PAYLOAD_LEN)
        self.assertEqual(result["terminal"], "CREATE_GETTX_SAME_195_STILL_TRUNCATED")
        scan = result["scan"]
        assert scan is not None
        self.assertEqual(scan["failed_by_event"].get("CreateEvent"), 1)
        self.assertEqual(
            scan["fail_codes_by_event"]["CreateEvent"],
            {"borsh_payload_truncated": 1},
        )

    def test_null_result_is_unavailable(self) -> None:
        result = classify_gettransaction_body(NULL_RESULT.read_bytes(), pinned=self.pinned)
        self.assertEqual(result["terminal"], "CREATE_GETTX_NULL_OR_UNAVAILABLE")
        self.assertIsNone(result["scan"])

    def test_provider_error_is_typed_failure(self) -> None:
        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": REQUEST_ID,
                "error": {"code": -32004, "message": "not available"},
            }
        ).encode("utf-8")
        result = classify_gettransaction_body(body, pinned=self.pinned)
        self.assertEqual(result["terminal"], "PROVIDER_TYPED_FAILURE")
        self.assertEqual(result["provider_error_code"], -32004)

    def test_http_once_uses_injected_opener(self) -> None:
        payload = NULL_RESULT.read_bytes()
        opener = _FakeOpener(payload)
        transport = perform_http_post_once(bind_get_transaction_request(), opener=opener)
        self.assertEqual(opener.opened, 1)
        self.assertEqual(transport["http_status"], 200)
        self.assertEqual(transport["response_bytes"], len(payload))
        self.assertEqual(transport["credential_reads"], 0)

    def test_transport_error_is_unknown_coverage(self) -> None:
        opener = _FakeOpener(error=URLError("timed out"))
        from solana_alpha_lab.rc002_h11_bounded_gettransaction_create import (
            BoundedGetTransactionTerminal,
        )

        with self.assertRaises(BoundedGetTransactionTerminal) as raised:
            perform_http_post_once(bind_get_transaction_request(), opener=opener)
        self.assertEqual(str(raised.exception), "TRANSPORT_OR_COVERAGE_UNKNOWN")

    def test_preflight_does_not_open_tls_or_read_credentials(self) -> None:
        seen: list[tuple[str, int]] = []

        def resolver(host: str, port: int, type: int = 0) -> list[object]:
            seen.append((host, port))
            return [("AF_INET", "SOCK_STREAM", 0, "", ("127.0.0.1", 443))]

        class _Sock:
            def close(self) -> None:
                return None

        def connector(_addr: object, timeout: float = 0) -> _Sock:
            return _Sock()

        result = dns_tcp_preflight(resolver=resolver, connector=connector)
        self.assertEqual(seen, [("api.mainnet-beta.solana.com", 443)])
        self.assertEqual(result["credential_reads"], 0)
        self.assertEqual(result["provider_requests"], 0)
        self.assertTrue(result["tcp_443"])

    def test_acceptance_receipt_is_json_object(self) -> None:
        path = ROOT / (
            "docs/evidence/rc002_h11_bounded_gettransaction_create/"
            "a1_bounded_gettransaction_create_acceptance_v1.json"
        )
        receipt = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["atom_id"], ATOM_ID)
        self.assertEqual(receipt["route_id"], ROUTE_ID)
        self.assertEqual(receipt["signature"], PINNED_SIGNATURE)
        self.assertEqual(receipt["terminal"], "CREATE_GETTX_SAME_195_STILL_TRUNCATED")
        self.assertEqual(receipt["live_payload_len"], 195)
        self.assertEqual(receipt["provider_requests"], 1)
        self.assertEqual(receipt["live_status"], "LIVE_ONE_SHOT")
        self.assertIn("NO_EXCLUSIVE_XB_RPC_CUT_CLAIM", receipt["non_claims"])
        self.assertFalse(receipt["live_PIT_claim"])
        self.assertEqual(receipt["credential_reads"], 0)

    def test_terminal_tuple_matches_contract(self) -> None:
        self.assertEqual(
            TERMINAL_OUTCOMES,
            (
                "CREATE_GETTX_SAME_195_STILL_TRUNCATED",
                "CREATE_GETTX_SAME_195_CONSUMED",
                "CREATE_GETTX_LONGER_BODY_CONSUMED",
                "CREATE_GETTX_LONGER_BODY_STILL_TRUNCATED",
                "CREATE_GETTX_SHORTER_THAN_GTA",
                "CREATE_GETTX_CREATE_BODY_ABSENT",
                "CREATE_GETTX_NULL_OR_UNAVAILABLE",
                "PROVIDER_TYPED_FAILURE",
                "TRANSPORT_OR_COVERAGE_UNKNOWN",
            ),
        )


if __name__ == "__main__":
    unittest.main()
