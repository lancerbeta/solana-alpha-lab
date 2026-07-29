from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.contracts.schema_v1 import Side  # noqa: E402
from solana_alpha_lab.jupiter_quote_logger import QuoteRequest  # noqa: E402
from solana_alpha_lab.jupiter_quote_transport import (  # noqa: E402
    EXTERNAL_AUTHORITY_PHRASE as TASK10_AUTHORITY,
    BoundedQuoteTransport,
    ExternalExecutionGate,
)
from solana_alpha_lab.task17a_execution_capacity_panel import (  # noqa: E402
    EXTERNAL_AUTHORITY_PHRASE,
    LOGICAL_ROOT,
    Task17AExecutionGate,
    Task17APanelError,
    load_frozen_contract,
    run_panel,
)

CONTRACT_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task17a"
    / "bounded_execution_capacity_quote_panel_contract_v1.json"
)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class StepNow:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        result = self.value
        self.value += timedelta(milliseconds=10)
        return result


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.status = 200
        self.body = body
        self.headers = {"Content-Length": str(len(body))}

    def read(self, amount: int) -> bytes:
        return self.body[:amount]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class QuoteOpener:
    def open(self, request: object, *, timeout: int) -> FakeResponse:
        query = urllib.parse.parse_qs(
            urllib.parse.urlsplit(request.full_url).query
        )
        output = max(1, int(query["amount"][0]) // 2)
        body = {
            "inputMint": query["inputMint"][0],
            "inAmount": query["amount"][0],
            "outputMint": query["outputMint"][0],
            "outAmount": str(output),
            "otherAmountThreshold": str(max(0, output - 1)),
            "swapMode": "ExactIn",
            "slippageBps": int(query["slippageBps"][0]),
            "platformFee": None,
            "priceImpactPct": "0.001",
            "routePlan": [
                {
                    "swapInfo": {
                        "ammKey": "synthetic",
                        "label": "Synthetic",
                        "inputMint": query["inputMint"][0],
                        "outputMint": query["outputMint"][0],
                        "inAmount": query["amount"][0],
                        "outAmount": str(output),
                        "feeAmount": "0",
                        "feeMint": query["inputMint"][0],
                    },
                    "percent": 100,
                    "bps": 10000,
                }
            ],
            "contextSlot": 1,
            "timeTaken": 0.01,
        }
        return FakeResponse(json.dumps(body).encode("utf-8"))


class AuthOpener:
    def open(self, request: object, *, timeout: int) -> object:
        body = b"authentication required"
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            {"Content-Length": str(len(body))},
            io.BytesIO(body),
        )


class Task17AExecutionCapacityPanelTests(unittest.TestCase):
    def test_contract_and_wrong_runtime_gate_fail_closed(self) -> None:
        contract = load_frozen_contract(CONTRACT_PATH)
        self.assertEqual(contract["caps"]["provider_calls_current_max"], 24)
        with self.assertRaisesRegex(
            Task17APanelError, "external_authority_phrase_mismatch"
        ):
            Task17AExecutionGate(authority_phrase="wrong")

    def test_three_windows_use_exact_24_calls_and_persist_hashes(self) -> None:
        clock = FakeClock()
        now = StepNow()

        def factory() -> BoundedQuoteTransport:
            return BoundedQuoteTransport(
                gate=ExternalExecutionGate(
                    authority_phrase=TASK10_AUTHORITY
                ),
                opener=QuoteOpener(),
                clock=clock.monotonic,
                sleeper=clock.sleep,
                now=now,
            )

        with tempfile.TemporaryDirectory() as directory:
            raw_root = Path(directory).resolve()
            summary = run_panel(
                gate=Task17AExecutionGate(
                    authority_phrase=EXTERNAL_AUTHORITY_PHRASE
                ),
                raw_root=raw_root,
                contract_path=CONTRACT_PATH,
                transport_factory=factory,
                clock=clock.monotonic,
                sleeper=clock.sleep,
                now=now,
                emit=lambda _line: None,
            )
            self.assertEqual(summary["status"], "COMPLETE")
            self.assertEqual(summary["provider_calls"], 24)
            self.assertEqual(summary["completed_windows"], 3)
            panel_root = raw_root / LOGICAL_ROOT
            for index in range(1, 4):
                window = panel_root / f"window=T17A-WINDOW-0{index}"
                self.assertTrue((window / "raw_events.jsonl").is_file())
                self.assertTrue((window / "manifest.json").is_file())
                self.assertTrue((window / "receipt.json").is_file())

    def test_auth_requirement_stops_after_one_call_and_one_window(self) -> None:
        clock = FakeClock()
        now = StepNow()

        def factory() -> BoundedQuoteTransport:
            return BoundedQuoteTransport(
                gate=ExternalExecutionGate(
                    authority_phrase=TASK10_AUTHORITY
                ),
                opener=AuthOpener(),
                clock=clock.monotonic,
                sleeper=clock.sleep,
                now=now,
            )

        with tempfile.TemporaryDirectory() as directory:
            summary = run_panel(
                gate=Task17AExecutionGate(
                    authority_phrase=EXTERNAL_AUTHORITY_PHRASE
                ),
                raw_root=Path(directory).resolve(),
                contract_path=CONTRACT_PATH,
                transport_factory=factory,
                clock=clock.monotonic,
                sleeper=clock.sleep,
                now=now,
                emit=lambda _line: None,
            )
            self.assertEqual(summary["status"], "STOPPED")
            self.assertEqual(summary["provider_calls"], 1)
            self.assertEqual(summary["completed_windows"], 1)
            self.assertEqual(
                summary["stop_reason"],
                "AUTHENTICATION_OR_ACCOUNT_REQUIRED",
            )


if __name__ == "__main__":
    unittest.main()
