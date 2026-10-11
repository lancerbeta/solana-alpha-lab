"""Wire-shaped boundary proofs; no provider, key, signer or transaction use."""
import json
import unittest
from decimal import Decimal
from urllib.parse import urlencode

from solana_alpha_lab.factory.trading_adapters import JupiterQuoteAdapter, PaperModelAdapter, ENDPOINT, checked_observation, raw_amount
from solana_alpha_lab.factory.hfic_research_scope import sha256_of

FUNDING = "So11111111111111111111111111111111111111112"
ASSET = "SynthContinuity11111111111111111111111111111"
AT = "2026-10-05T12:40:00Z"


def frozen_request(**overrides):
    request = {"inputMint": FUNDING, "outputMint": ASSET, "amount": "300000000",
        "input_decimals": 9, "output_decimals": 6, "funding_price_usd": "100",
        "admitted_notional_usd": "30", "activation_epoch_id": "ACTIVATION-EPOCH-ADAPTER",
        "strategy_sha256": "a" * 64, **overrides}
    return {**request, "request_sha256": sha256_of(request)}


def wire(request, **overrides):
    return {"transaction": None, "inputMint": request["inputMint"], "outputMint": request["outputMint"],
        "inAmount": request["amount"], "outAmount": "10000000000000", "router": "metis", "mode": "ultra",
        "feeBps": 20, "feeMint": request["outputMint"], "requestId": "synthetic-original-request", **overrides}


class AdapterTests(unittest.TestCase):
    def adapter(self, payload=None, *, status=200, url=None):
        def transport(request, **bounds):
            self.assertNotIn("taker", request)
            self.assertNotIn("payer", request)
            self.assertIsNone(bounds["api_key"])
            return {"status": status, "body": json.dumps(payload or wire(request)).encode(),
                "url": url or ENDPOINT + "?" + urlencode(request)}
        return JupiterQuoteAdapter(timeout_seconds=1, max_response_bytes=8192, transport=transport)

    def test_C04_C14_fee_in_quote_raw_units_literal_oracle(self):
        request = frozen_request()
        result, provenance = self.adapter().dispatch({"attempt_id": "ATTEMPT-ONE", "side": "ENTRY"}, request, as_of=AT)
        self.assertEqual(Decimal(result["quantity_filled"]), Decimal("10000000"))
        self.assertEqual(Decimal(result["filled_notional_usd"]), Decimal("30"))
        self.assertEqual(Decimal(result["unit_price_usd"]), Decimal("0.000003"))
        self.assertEqual(result["fee_semantics"], "INCLUDED_IN_UNIT_PRICE")
        self.assertFalse(provenance["fill_claimed"])
        exit_request = frozen_request(inputMint=ASSET, outputMint=FUNDING, amount="4000000000000",
            input_decimals=6, output_decimals=9, remaining_quantity="10000000")
        result, _ = self.adapter(wire(exit_request, outAmount="132000000")).dispatch(
            {"attempt_id": "ATTEMPT-EXIT", "side": "EXIT"}, exit_request, as_of=AT)
        self.assertEqual(result["outcome"], "PARTIAL")
        self.assertEqual(Decimal(result["quantity_sold"]), Decimal("4000000"))
        self.assertEqual(Decimal(result["remaining_quantity"]), Decimal("6000000"))
        self.assertEqual(Decimal(result["unit_price_usd"]), Decimal(".0000033"))

    def test_C14_C23_negative_wire_shapes_before_persistence(self):
        request = frozen_request()
        for overrides in ({"transaction": "CANARY-TRANSACTION-BYTES"}, {"inputMint": ASSET},
            {"inAmount": "300000001"}, {"outAmount": "0"}, {"feeMint": "wrong"}, {"router": "unknown"},
            {"requestId": None}, {"feeBps": True}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.adapter(wire(request, **overrides)).dispatch({"attempt_id": "A", "side": "ENTRY"}, request, as_of=AT)
        with self.assertRaisesRegex(ValueError, "QUOTE_REDIRECT_OR_HOST_REJECTED"):
            self.adapter(url="https://redirect.invalid/order").dispatch({"attempt_id": "A", "side": "ENTRY"}, request, as_of=AT)
        calls = []
        # No grant means no credential callback and no transport invocation.
        adapter = JupiterQuoteAdapter(timeout_seconds=1, max_response_bytes=8192, credential_supplier=lambda: calls.append(True))
        with self.assertRaisesRegex(ValueError, "QUOTE_EXTERNAL_AUTHORITY_REQUIRED"):
            adapter.dispatch({"attempt_id": "A", "side": "ENTRY"}, request, as_of=AT)
        self.assertEqual(calls, [])
        self.assertEqual(adapter.calls, 0)

    def test_C12_timeout_unknown_rejection_definitive_not_flat(self):
        request = frozen_request()
        unknown, _ = self.adapter(status=504).dispatch({"attempt_id": "A", "side": "EXIT"}, request, as_of=AT)
        refused, _ = self.adapter(status=400).dispatch({"attempt_id": "A", "side": "EXIT"}, request, as_of=AT)
        self.assertEqual(unknown["outcome"], "UNKNOWN_REQUIRES_RECONCILIATION")
        self.assertNotIn("quantity_sold", unknown)
        self.assertEqual(refused["outcome"], "REJECTED_BEFORE_SEND")

    def test_C03_C14_input_clock_and_denominator_guards(self):
        row = {"mint": FUNDING, "decimals": 9, "unit_price_usd": "100", "observed_at": AT, "available_at": AT}
        self.assertEqual(checked_observation(row, mint=FUNDING, as_of=AT, max_age_seconds=60)["unit_price_usd"], "100")
        for changes in ({"available_at": "2026-10-05T12:40:01Z"}, {"unit_price_usd": "NaN"}, {"mint": ASSET}, {"decimals": True}):
            with self.assertRaises(ValueError):
                checked_observation({**row, **changes}, mint=FUNDING, as_of=AT, max_age_seconds=60)
        self.assertEqual(raw_amount(".1234567899", 9), "123456789")
        with self.assertRaises(ValueError):
            PaperModelAdapter({"version": "TIMELY_OBSERVATION_MODEL_V1", "missing_input": "UNKNOWN", "latency_seconds": float("nan")})


if __name__ == "__main__":
    unittest.main()
