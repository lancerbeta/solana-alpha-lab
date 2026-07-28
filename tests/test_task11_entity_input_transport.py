from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.contracts.schema_v1 import (  # noqa: E402
    RawResponseStatus,
)
from solana_alpha_lab.entity_input_transport import (  # noqa: E402
    EXPECTED_MANAGED_FILES,
    EXPECTED_METHODS,
    EXTERNAL_AUTHORITY_PHRASE,
    PLAN_FIXTURE_SHA256,
    AccessAttestation,
    AccessAttestationError,
    BoundedEntityTransport,
    DurableEntityProbeSink,
    EntityProbeRunner,
    EntityTransportContractError,
    ExternalAuthorityRequiredError,
    ExternalExecutionGate,
    HeliusCredential,
    LargestAccountsObservation,
    OwnersObservation,
    TokenSupplyObservation,
    default_run_id,
    load_entity_pilot_plan,
    parse_largest_accounts,
    parse_owner_accounts,
    parse_token_supply,
)
from solana_alpha_lab.provider_smoke_transport import (  # noqa: E402
    BoundRequest,
    TransportResponse,
)

PLAN_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task11"
    / "entity_input_pilot_plan_v1.json"
)
MINT = "4vXNhA6ncbx8usZ14CfxkYeQKdaQYgrLfJXNyWcVpump"
BASE_TIME = datetime(2026, 7, 28, 14, 0, tzinfo=UTC)


def _response(
    body: object,
    *,
    status_code: int | None = 200,
    terminal_class: str = "SUCCESS",
    error_class: str | None = None,
    offset: int = 0,
) -> TransportResponse:
    started = BASE_TIME + timedelta(seconds=offset)
    return TransportResponse(
        status_code=status_code,
        body=json.dumps(
            body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8"),
        safe_headers=(("content-type", "application/json"),),
        terminal_class=terminal_class,
        error_class=error_class,
        request_started_at=started,
        request_sent_at=started,
        response_headers_at=started + timedelta(milliseconds=10),
        response_complete_at=started + timedelta(milliseconds=20),
    )


def _supply_body(*, extra_value: bool = False) -> dict[str, object]:
    value: dict[str, object] = {
        "amount": "1000000",
        "decimals": 6,
        "uiAmount": 1.0,
        "uiAmountString": "1",
    }
    if extra_value:
        value["unexpected"] = "drift"
    return {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {
            "context": {"apiVersion": "2.3.0", "slot": 100},
            "value": value,
        },
    }


def _largest_rows() -> list[dict[str, object]]:
    return [
        {
            "address": "synthetic-token-account-a",
            "amount": "400000",
            "decimals": 6,
            "uiAmount": 0.4,
            "uiAmountString": "0.4",
        },
        {
            "address": "synthetic-token-account-b",
            "amount": "200000",
            "decimals": 6,
            "uiAmount": 0.2,
            "uiAmountString": "0.2",
        },
        {
            "address": "synthetic-token-account-c",
            "amount": "100000",
            "decimals": 6,
            "uiAmount": 0.1,
            "uiAmountString": "0.1",
        },
    ]


def _largest_body() -> dict[str, object]:
    return {
        "id": 2,
        "jsonrpc": "2.0",
        "result": {
            "context": {"apiVersion": "2.3.0", "slot": 101},
            "value": _largest_rows(),
        },
    }


def _owner_account(
    *,
    owner: str,
    amount: str,
) -> dict[str, object]:
    return {
        "data": {
            "parsed": {
                "info": {
                    "isNative": False,
                    "mint": MINT,
                    "owner": owner,
                    "state": "initialized",
                    "tokenAmount": {
                        "amount": amount,
                        "decimals": 6,
                        "uiAmount": int(amount) / 1_000_000,
                        "uiAmountString": str(int(amount) / 1_000_000),
                    },
                },
                "type": "account",
            },
            "program": "spl-token",
            "space": 165,
        },
        "executable": False,
        "lamports": 2039280,
        "owner": "TokenProgramSynthetic1111111111111111111111",
        "rentEpoch": 18446744073709551615,
        "space": 165,
    }


def _owners_body(*, incomplete: bool = False) -> dict[str, object]:
    values = [
        _owner_account(owner="synthetic-owner-a", amount="400000"),
        _owner_account(owner="synthetic-owner-b", amount="200000"),
        _owner_account(owner="synthetic-owner-c", amount="100000"),
    ]
    if incomplete:
        values.pop()
    return {
        "id": 3,
        "jsonrpc": "2.0",
        "result": {
            "context": {"apiVersion": "2.3.0", "slot": 102},
            "value": values,
        },
    }


class FakeExchange:
    def __init__(self, responses: list[TransportResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[BoundRequest] = []

    def __call__(
        self,
        request: BoundRequest,
        *,
        max_response_bytes: int,
    ) -> TransportResponse:
        self.requests.append(request)
        if not self.responses:
            raise RuntimeError("unexpected_extra_call")
        response = self.responses.pop(0)
        if len(response.body) > max_response_bytes:
            raise RuntimeError("response_too_large")
        return response


class Task11EntityInputTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = load_entity_pilot_plan(PLAN_PATH)
        cls.document = json.loads(PLAN_PATH.read_text(encoding="utf-8"))

    def test_frozen_plan_hash_inventory_and_caps_are_exact(self) -> None:
        self.assertEqual(
            PLAN_FIXTURE_SHA256,
            "ff0524ab2a77b517f8796ff54a753842"
            "306b83de9be6e8d4c391776afba0cf1d",
        )
        self.assertEqual(self.plan.methods, EXPECTED_METHODS)
        self.assertEqual(
            tuple(self.document["managed_tracked_files"]),
            EXPECTED_MANAGED_FILES,
        )
        self.assertEqual(self.plan.provider_calls, 3)
        self.assertEqual(self.plan.retries, 0)
        self.assertEqual(self.plan.modeled_credits_total, 30)
        self.assertEqual(self.plan.cash_spend_usd_cents, 0)
        self.assertEqual(self.plan.selected_mint, MINT)

    def test_plan_loader_rejects_any_byte_drift(self) -> None:
        changed = copy.deepcopy(self.document)
        changed["caps"]["provider_calls"] = 4
        with tempfile.TemporaryDirectory(prefix="task11_plan_drift_") as tmp:
            path = Path(tmp) / "changed.json"
            path.write_text(
                json.dumps(changed),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                EntityTransportContractError,
                "pilot_plan_sha256_drift",
            ):
                load_entity_pilot_plan(path)

    def test_gate_access_and_credential_repr_fail_closed(self) -> None:
        gate = ExternalExecutionGate(EXTERNAL_AUTHORITY_PHRASE)
        gate.require()
        with self.assertRaises(ExternalAuthorityRequiredError):
            ExternalExecutionGate("wrong").require()

        AccessAttestation(True, 30).require(self.plan)
        with self.assertRaises(AccessAttestationError):
            AccessAttestation(True, 29).require(self.plan)

        credential = HeliusCredential("fixture-helius-key")
        self.assertEqual(repr(credential), "HeliusCredential(<redacted>)")
        self.assertNotIn("fixture-helius-key", repr(credential))

    def test_three_rpc_payload_parsers_preserve_slots_and_owners(self) -> None:
        supply = parse_token_supply(
            _response(_supply_body()).body,
            expected_id=1,
            expected_decimals=6,
        )
        self.assertEqual(
            supply,
            TokenSupplyObservation(
                amount_atomic=1_000_000,
                decimals=6,
                context_slot=100,
            ),
        )
        largest = parse_largest_accounts(
            _response(_largest_body()).body,
            expected_id=2,
            expected_decimals=6,
        )
        self.assertIsInstance(largest, LargestAccountsObservation)
        self.assertEqual(largest.context_slot, 101)
        self.assertEqual(len(largest.accounts), 3)
        owners = parse_owner_accounts(
            _response(_owners_body()).body,
            expected_id=3,
            expected_mint=MINT,
            expected_accounts=largest.accounts,
        )
        self.assertIsInstance(owners, OwnersObservation)
        self.assertEqual(owners.context_slot, 102)
        self.assertEqual(
            tuple(item.owner for item in owners.owners),
            (
                "synthetic-owner-a",
                "synthetic-owner-b",
                "synthetic-owner-c",
            ),
        )

    def test_schema_drift_and_incomplete_owner_response_are_distinct(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            EntityTransportContractError,
            "token_supply_value_unknown_keys",
        ):
            parse_token_supply(
                _response(_supply_body(extra_value=True)).body,
                expected_id=1,
                expected_decimals=6,
            )
        largest = parse_largest_accounts(
            _response(_largest_body()).body,
            expected_id=2,
            expected_decimals=6,
        )
        with self.assertRaisesRegex(
            EntityTransportContractError,
            "incomplete_owner_response",
        ):
            parse_owner_accounts(
                _response(_owners_body(incomplete=True)).body,
                expected_id=3,
                expected_mint=MINT,
                expected_accounts=largest.accounts,
            )

    def _run(
        self,
        responses: list[TransportResponse],
        raw_root: Path,
    ) -> tuple[dict[str, object], FakeExchange, DurableEntityProbeSink]:
        credential = HeliusCredential("fixture-helius-key")
        gate = ExternalExecutionGate(EXTERNAL_AUTHORITY_PHRASE)
        exchange = FakeExchange(responses)
        transport = BoundedEntityTransport(
            plan=self.plan,
            credential=credential,
            gate=gate,
            http_exchange=exchange,
            clock=lambda: 0.0,
        )
        sink = DurableEntityProbeSink(
            raw_root=raw_root,
            run_id="t11a3-20260728T140000Z",
            plan=self.plan,
            credential=credential,
            now=lambda: BASE_TIME + timedelta(seconds=10),
        )
        result = EntityProbeRunner(
            plan=self.plan,
            transport=transport,
            sink=sink,
            access=AccessAttestation(True, 30),
        ).run()
        return result, exchange, sink

    def test_successful_runner_writes_three_raw_partitions_and_receipt(
        self,
    ) -> None:
        responses = [
            _response(_supply_body(), offset=1),
            _response(_largest_body(), offset=2),
            _response(_owners_body(), offset=3),
        ]
        with tempfile.TemporaryDirectory(prefix="task11_probe_success_") as tmp:
            root = Path(tmp)
            result, exchange, sink = self._run(responses, root)
            files = sorted(
                path.relative_to(root).as_posix()
                for path in root.rglob("*")
                if path.is_file()
            )
            all_bytes = b"".join(
                path.read_bytes() for path in root.rglob("*") if path.is_file()
            )

        self.assertEqual(
            result["terminal"],
            "RAW_TOP20_FEASIBILITY_CAPTURED",
        )
        self.assertEqual(result["completed_calls"], 3)
        self.assertEqual(result["modeled_credits"], 30)
        self.assertEqual(result["raw_top_accounts_amount_atomic"], 700_000)
        self.assertEqual(result["raw_top_accounts_supply_share"], "0.7")
        self.assertIsNone(result["adjusted_concentration"])
        self.assertEqual(result["supply_atomic"], 1_000_000)
        self.assertEqual(result["supply_context_slot"], 100)
        self.assertEqual(result["largest_accounts_context_slot"], 101)
        self.assertEqual(result["owners_context_slot"], 102)
        self.assertEqual(result["context_slot_spread"], 2)
        self.assertEqual(result["top_account_count"], 3)
        self.assertEqual(result["owner_resolution_count"], 3)
        self.assertEqual(len(result["attempts"]), 3)
        self.assertEqual(len(sink.receipts), 3)
        self.assertEqual(
            [request.case_id for request in exchange.requests],
            list(EXPECTED_METHODS),
        )
        self.assertEqual(sum(path.endswith(".parquet") for path in files), 3)
        self.assertEqual(
            sum(path.endswith("probe.receipt.json") for path in files),
            1,
        )
        self.assertNotIn(b"fixture-helius-key", all_bytes)
        for request in exchange.requests:
            self.assertNotIn(
                "fixture-helius-key",
                json.dumps(request.safe_receipt()),
            )
            self.assertNotIn("fixture-helius-key", repr(request))

    def test_http_failure_stops_after_second_call_and_preserves_prefix(
        self,
    ) -> None:
        responses = [
            _response(_supply_body(), offset=1),
            _response(
                {"error": "unavailable"},
                status_code=503,
                terminal_class="PROVIDER_5XX",
                error_class="http_503",
                offset=2,
            ),
        ]
        with tempfile.TemporaryDirectory(prefix="task11_probe_failure_") as tmp:
            result, exchange, sink = self._run(responses, Path(tmp))

        self.assertEqual(result["terminal"], "STOPPED_PROVIDER_TRANSPORT")
        self.assertEqual(result["error_code"], "http_503")
        self.assertEqual(result["completed_calls"], 2)
        self.assertEqual(len(exchange.requests), 2)
        self.assertEqual(len(sink.receipts), 2)
        self.assertEqual(
            sink.receipts[1].response_status,
            str(RawResponseStatus.HTTP_ERROR),
        )

    def test_schema_drift_is_preserved_as_invalid_response(self) -> None:
        responses = [_response(_supply_body(extra_value=True), offset=1)]
        with tempfile.TemporaryDirectory(prefix="task11_probe_drift_") as tmp:
            result, exchange, sink = self._run(responses, Path(tmp))

        self.assertEqual(result["terminal"], "STOPPED_SCHEMA_DRIFT")
        self.assertEqual(
            result["error_code"],
            "token_supply_value_unknown_keys",
        )
        self.assertEqual(len(exchange.requests), 1)
        self.assertEqual(len(sink.receipts), 1)
        self.assertEqual(
            sink.receipts[0].response_status,
            str(RawResponseStatus.INVALID_RESPONSE),
        )

    def test_run_id_is_utc_and_second_bounded(self) -> None:
        self.assertEqual(
            default_run_id(BASE_TIME),
            "t11a3-20260728T140000Z",
        )
        with self.assertRaisesRegex(
            EntityTransportContractError,
            "run_time_must_be_aware",
        ):
            default_run_id(datetime(2026, 7, 28, 14, 0))


if __name__ == "__main__":
    unittest.main()
