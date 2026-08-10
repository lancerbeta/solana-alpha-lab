from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from run_task30_gecko_interval_semantics import (
    BoundedGeckoTransport,
    RunnerError,
    dry_run,
)
from solana_alpha_lab.task30_gecko_interval_semantics import build_request_plan
from test_task30_gecko_interval_semantics import policy


class FakeResponse:
    status = 200
    headers = {"content-type": "application/json"}

    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, _: int) -> bytes:
        return self.body


class FakeOpener:
    def __init__(self) -> None:
        self.requests: list[object] = []

    def open(self, request: object, *, timeout: int) -> FakeResponse:
        self.requests.append(request)
        self.timeout = timeout
        return FakeResponse(b'{"data": []}')


class Task30GeckoIntervalSemanticsRunnerTests(unittest.TestCase):
    def test_dry_run_has_exact_plan_and_zero_network_calls(self) -> None:
        result = dry_run(policy(), now_epoch=1_999)

        self.assertEqual(result["network_calls"], 0)
        self.assertEqual(result["before_timestamp"], 1_800)
        self.assertEqual(len(result["plan"]), 2)

    def test_transport_executes_each_of_the_two_planned_gets_once(self) -> None:
        plan = build_request_plan(policy(), before_timestamp=1_800)
        opener = FakeOpener()
        transport = BoundedGeckoTransport(opener=opener)

        captures = transport.execute(plan)

        self.assertEqual(transport.attempts, 2)
        self.assertEqual(len(opener.requests), 2)
        self.assertEqual([capture["http_status"] for capture in captures], [200, 200])

    def test_transport_rejects_more_than_two_requests_before_network_io(self) -> None:
        plan = build_request_plan(policy(), before_timestamp=1_800)
        opener = FakeOpener()
        transport = BoundedGeckoTransport(opener=opener)

        with self.assertRaisesRegex(RunnerError, "REQUEST_PLAN_CAP_INVALID"):
            transport.execute(plan + [plan[0]])

        self.assertEqual(opener.requests, [])


if __name__ == "__main__":
    unittest.main()
