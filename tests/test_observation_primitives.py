from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_primitives import (  # noqa: E402
    ObservationPrimitiveError,
    execute_primitive,
    quote_url,
    request_sha256,
    search_url,
)


class _Opener:
    def __init__(self, result: object) -> None:
        self.urls: list[str] = []
        self.result = result

    def open(self, url: str) -> object:
        self.urls.append(url)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def _clock() -> datetime:
    return datetime(2026, 9, 1, 0, 5, tzinfo=UTC)


class ObservationPrimitiveTests(unittest.TestCase):
    def test_injected_opener_observes_without_network(self) -> None:
        opener = _Opener(
            {
                "http_status": 200,
                "body": {"id": "MintA", "liquidity": "1000"},
            }
        )
        result = execute_primitive(
            primitive_id="PRIM-JUPITER-TOKENS-V2-SEARCH-001",
            primitive_version="1.0",
            method="GET",
            url=search_url(["MintA"]),
            opener=opener,
            clock=_clock,
            expected_entities=["MintA"],
        )
        self.assertEqual(result["status"], "OBSERVED")
        self.assertEqual(len(opener.urls), 1)
        self.assertTrue(opener.urls[0].startswith("https://api.jup.ag/tokens/v2/search"))

    def test_missing_schema_key_is_typed_drift(self) -> None:
        opener = _Opener({"http_status": 200, "body": {"unexpected": True}})
        result = execute_primitive(
            primitive_id="PRIM-JUPITER-TOKENS-V2-SEARCH-001",
            primitive_version="1.0",
            method="GET",
            url=search_url(["MintA"]),
            opener=opener,
            clock=_clock,
            schema_required_keys=["id"],
        )
        self.assertEqual(result["status"], "MISSING_TYPED")
        self.assertEqual(result["missing_reason"], "PROVIDER_SCHEMA_DRIFT")

    def test_timeout_and_http_error_are_typed_missing(self) -> None:
        timeout = execute_primitive(
            primitive_id="PRIM-JUPITER-TOKENS-V2-RECENT-001",
            primitive_version="1.0",
            method="GET",
            url="https://api.jup.ag/tokens/v2/recent",
            opener=_Opener(TimeoutError("slow")),
            clock=_clock,
        )
        self.assertEqual(timeout["missing_reason"], "TIMEOUT")
        http_err = execute_primitive(
            primitive_id="PRIM-JUPITER-TOKENS-V2-RECENT-001",
            primitive_version="1.0",
            method="GET",
            url="https://api.jup.ag/tokens/v2/recent",
            opener=_Opener({"http_status": 500, "body": {}}),
            clock=_clock,
        )
        self.assertEqual(http_err["missing_reason"], "HTTP_ERROR")

    def test_secret_cannot_enter_request_identity_or_payload(self) -> None:
        with self.assertRaisesRegex(ObservationPrimitiveError, "SECRET_IN_REQUEST_IDENTITY"):
            request_sha256(
                method="GET",
                url="https://" + "user" + ":" + "pass" + "@api.jup.ag/tokens/v2/recent",
                body=None,
                primitive_version="1.0",
            )
        with self.assertRaisesRegex(ObservationPrimitiveError, "SECRET_LEAK"):
            execute_primitive(
                primitive_id="PRIM-JUPITER-TOKENS-V2-RECENT-001",
                primitive_version="1.0",
                method="GET",
                url="https://api.jup.ag/tokens/v2/recent",
                opener=_Opener({"http_status": 200, "body": {"token": "super-secret"}}),
                clock=_clock,
                redact_with="super-secret",
            )

    def test_mint_order_is_canonical_in_search_request_hash(self) -> None:
        first = request_sha256(
            method="GET",
            url=search_url(["MintA", "MintB"]),
            body=None,
            primitive_version="1.0",
        )
        second = request_sha256(
            method="GET",
            url=search_url(["MintB", "MintA"]),
            body=None,
            primitive_version="1.0",
        )
        self.assertEqual(first, second)
        third = request_sha256(
            method="GET",
            url=search_url(["MintA"]),
            body=None,
            primitive_version="1.0",
        )
        self.assertNotEqual(first, third)

    def test_endpoint_drift_is_rejected(self) -> None:
        with self.assertRaisesRegex(ObservationPrimitiveError, "ENDPOINT_DRIFT"):
            execute_primitive(
                primitive_id="PRIM-JUPITER-SWAP-V2-QUOTE-BUY-001",
                primitive_version="1.0",
                method="GET",
                url="https://evil.example/swap/v2/order",
                opener=_Opener({"http_status": 200, "body": {}}),
                clock=_clock,
            )
        buy = quote_url(
            input_mint="So11111111111111111111111111111111111111112",
            output_mint="MintA",
            amount="10000000",
        )
        self.assertIn("inputMint=", buy)
        self.assertIn("api.jup.ag/swap/v2/order", buy)

    def test_missing_http_status_is_typed_drift(self) -> None:
        result = execute_primitive(
            primitive_id="PRIM-JUPITER-TOKENS-V2-RECENT-001",
            primitive_version="1.0",
            method="GET",
            url="https://api.jup.ag/tokens/v2/recent",
            opener=_Opener({"body": [{"id": "MintA"}]}),
            clock=_clock,
        )
        self.assertEqual(result["status"], "MISSING_TYPED")
        self.assertEqual(result["missing_reason"], "PROVIDER_SCHEMA_DRIFT")


if __name__ == "__main__":
    unittest.main()
