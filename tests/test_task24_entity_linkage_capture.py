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

from solana_alpha_lab.provider_smoke_transport import TransportResponse  # noqa: E402
from solana_alpha_lab.task24_entity_linkage_capture import (  # noqa: E402
    A3_MANIFEST_SHA256,
    A4_CONFIG_SHA256,
    A4_RECEIPT_SHA256,
    EXTERNAL_AUTHORITY_PHRASE,
    AccessAttestation,
    AccessAttestationError,
    BoundedHistoryTransport,
    DurableHistorySink,
    ExternalAuthorityRequiredError,
    ExternalExecutionGate,
    FrozenPopulation,
    FrozenSubject,
    HeliusCredential,
    HistoryCapturePlan,
    HistoryCaptureRunner,
    Task24HistoryCaptureError,
    default_run_id,
    load_frozen_population,
    parse_history_response,
)


FIXED_NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


def response_for_request(
    request,
    *,
    transactions: list[dict] | None = None,
    max_response_bytes: int | None = None,
):
    body = json.loads(request.body)
    payload = {
        "id": body["id"],
        "jsonrpc": "2.0",
        "result": {
            "data": transactions or [],
            "paginationToken": None,
        },
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return TransportResponse(
        status_code=200,
        body=raw,
        safe_headers=(),
        terminal_class="SUCCESS",
        error_class=None,
        request_started_at=FIXED_NOW,
        request_sent_at=FIXED_NOW,
        response_headers_at=FIXED_NOW,
        response_complete_at=FIXED_NOW,
    )


def transaction(slot: int, signature: str) -> dict:
    return {
        "blockTime": 1_700_000_000 + slot,
        "meta": {"err": None},
        "slot": slot,
        "transaction": {
            "message": {
                "accountKeys": [],
                "header": {"numRequiredSignatures": 0},
                "instructions": [],
            },
            "signatures": [signature],
        },
    }


class Task24EntityLinkageCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.population = load_frozen_population(ROOT)

    def test_content_bindings_and_frozen_population_are_exact(self) -> None:
        import hashlib

        def sha(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest()

        self.assertEqual(
            sha(ROOT / "configs/task24_entity_linkage_evidence_extension_v1.yaml"),
            A4_CONFIG_SHA256,
        )
        self.assertEqual(
            sha(
                ROOT
                / "docs/evidence/task24/a4_bounded_entity_linkage_evidence_extension_decision_v1.json"
            ),
            A4_RECEIPT_SHA256,
        )
        self.assertEqual(
            sha(ROOT / "docs/evidence/task24/a3_entity_evidence_pre_read_manifest_v1.json"),
            A3_MANIFEST_SHA256,
        )
        self.assertEqual(len(self.population.subjects), 21)
        self.assertEqual(len(self.population.wallets), 20)
        self.assertEqual(len({item.subject_id for item in self.population.subjects}), 21)
        self.assertEqual(self.population.mint.node_type, "TOKEN_MINT")
        self.assertTrue(
            all(item.node_type == "WALLET" for item in self.population.wallets)
        )

    def test_safe_population_receipt_contains_no_raw_public_keys(self) -> None:
        payload = json.dumps(self.population.safe_receipt(), sort_keys=True)
        for subject in self.population.subjects:
            self.assertNotIn(subject.raw_public_key, payload)
        self.assertEqual(
            self.population.safe_receipt()["subject_count"], 21
        )

    def test_plan_preserves_a4_caps_and_adds_exact_wire_retention(self) -> None:
        plan = HistoryCapturePlan()
        plan.validate()
        self.assertEqual(plan.provider_calls, 21)
        self.assertEqual(plan.provider_credits, 210)
        self.assertEqual(plan.returned_transactions, 2100)
        self.assertEqual(plan.limit_each, 100)
        self.assertEqual(plan.retries, 0)
        self.assertEqual(plan.cash_spend_usd_cents, 0)
        self.assertEqual(plan.dataset_version, "1.1")
        self.assertTrue(plan.safe_preflight()["exact_wire_response_bytes"])
        self.assertFalse(plan.safe_preflight()["pagination"])

    def test_plan_rejects_cap_drift(self) -> None:
        for field, value, expected in (
            ("provider_calls", 22, "provider_call_cap_drift"),
            ("provider_credits", 211, "provider_credit_cap_drift"),
            ("limit_each", 101, "per_request_limit_drift"),
            ("retries", 1, "retry_cap_drift"),
            ("cash_spend_usd_cents", 1, "cash_cap_drift"),
        ):
            with self.subTest(field=field):
                changed = copy.copy(HistoryCapturePlan())
                object.__setattr__(changed, field, value)
                with self.assertRaisesRegex(Task24HistoryCaptureError, expected):
                    changed.validate()

    def test_exact_authority_and_credit_headroom_are_required(self) -> None:
        with self.assertRaises(ExternalAuthorityRequiredError):
            ExternalExecutionGate("wrong").require()
        ExternalExecutionGate(EXTERNAL_AUTHORITY_PHRASE).require()
        with self.assertRaises(AccessAttestationError):
            AccessAttestation(True, 209).require(HistoryCapturePlan())
        AccessAttestation(True, 210).require(HistoryCapturePlan())

    def test_credential_repr_is_redacted(self) -> None:
        credential = HeliusCredential("unit-" + "h" * 24)
        self.assertEqual(repr(credential), "HeliusCredential(<redacted>)")
        self.assertNotIn(credential.value, repr(credential))

    def test_history_parser_accepts_oldest_first_and_retains_truncation_flag(self) -> None:
        payload = {
            "id": 7,
            "jsonrpc": "2.0",
            "result": {
                "data": [transaction(10, "sig-a"), transaction(11, "sig-b")],
                "paginationToken": "11:1",
            },
        }
        body = json.dumps(payload).encode()
        page = parse_history_response(body, expected_id=7, limit=100)
        self.assertEqual(page.transaction_count, 2)
        self.assertEqual(page.first_slot, 10)
        self.assertEqual(page.last_slot, 11)
        self.assertTrue(page.pagination_token_present)

    def test_history_parser_rejects_order_error_failed_tx_and_over_limit(self) -> None:
        cases = []
        cases.append(
            (
                [transaction(11, "sig-a"), transaction(10, "sig-b")],
                "oldest_first_order_drift",
            )
        )
        failed = transaction(10, "sig-c")
        failed["meta"]["err"] = {"InstructionError": [0, "x"]}
        cases.append(([failed], "transaction_0.not_succeeded"))
        cases.append(
            ([transaction(i, f"sig-{i}") for i in range(3)], "returned_transaction_cap")
        )
        for index, (rows, expected) in enumerate(cases, start=1):
            with self.subTest(expected=expected):
                body = json.dumps(
                    {
                        "id": index,
                        "jsonrpc": "2.0",
                        "result": {"data": rows, "paginationToken": None},
                    }
                ).encode()
                limit = 2 if expected == "returned_transaction_cap" else 100
                with self.assertRaisesRegex(Task24HistoryCaptureError, expected):
                    parse_history_response(body, expected_id=index, limit=limit)

    def test_bound_request_is_exact_and_safe_receipt_hides_key_and_address(self) -> None:
        credential = HeliusCredential("unit-" + "k" * 24)
        transport = BoundedHistoryTransport(
            plan=HistoryCapturePlan(),
            credential=credential,
            gate=ExternalExecutionGate(EXTERNAL_AUTHORITY_PHRASE),
            http_exchange=response_for_request,
        )
        subject = self.population.subjects[0]
        attempt = transport.call(rpc_id=1, subject=subject)
        body = json.loads(attempt.request.body)
        self.assertEqual(body["method"], "getTransactionsForAddress")
        config = body["params"][1]
        self.assertEqual(config["sortOrder"], "asc")
        self.assertEqual(config["limit"], 100)
        self.assertEqual(config["transactionDetails"], "full")
        self.assertNotIn("paginationToken", config)
        safe = json.dumps(attempt.request.safe_receipt(), sort_keys=True)
        self.assertNotIn(credential.value, safe)
        self.assertNotIn(subject.raw_public_key, safe)

    def test_transport_rejects_twenty_second_call(self) -> None:
        credential = HeliusCredential("unit-" + "m" * 24)
        transport = BoundedHistoryTransport(
            plan=HistoryCapturePlan(),
            credential=credential,
            gate=ExternalExecutionGate(EXTERNAL_AUTHORITY_PHRASE),
            http_exchange=response_for_request,
        )
        for rpc_id, subject in enumerate(self.population.subjects, start=1):
            transport.call(rpc_id=rpc_id, subject=subject)
        with self.assertRaisesRegex(Task24HistoryCaptureError, "provider_call_cap"):
            transport.call(rpc_id=22, subject=self.population.subjects[0])

    def test_full_fake_capture_writes_twenty_one_exact_raw_partitions(self) -> None:
        credential = HeliusCredential("unit-" + "n" * 24)
        plan = HistoryCapturePlan()
        gate = ExternalExecutionGate(EXTERNAL_AUTHORITY_PHRASE)
        with tempfile.TemporaryDirectory() as temp:
            raw_root = Path(temp).resolve()
            sink = DurableHistorySink(
                raw_root=raw_root,
                run_id="t24a5-20260802T120000Z",
                plan=plan,
                population=self.population,
                credential=credential,
                now=lambda: FIXED_NOW,
            )
            result = HistoryCaptureRunner(
                plan=plan,
                population=self.population,
                transport=BoundedHistoryTransport(
                    plan=plan,
                    credential=credential,
                    gate=gate,
                    http_exchange=response_for_request,
                ),
                sink=sink,
                access=AccessAttestation(True, 210),
            ).run()
            self.assertEqual(
                result["terminal"], "RAW_HISTORY_CAPTURED_REQUIRES_PROJECTION"
            )
            self.assertEqual(result["provider_calls"], 21)
            self.assertEqual(result["provider_credits_modeled"], 210)
            self.assertEqual(len(result["attempts"]), 21)
            self.assertEqual(len(result["pages"]), 21)
            self.assertEqual(
                len(
                    list(
                        (
                            raw_root
                            / "task24_entity_linkage_history_wire_v1_1"
                            / "run=t24a5-20260802T120000Z"
                        ).glob("*.response.json")
                    )
                ),
                21,
            )
            self.assertEqual(result["stored_exact_wire_bytes"], result["received_bytes"])
            receipt = (
                raw_root
                / "task24_entity_linkage_history_v1_1"
                / "run=t24a5-20260802T120000Z"
                / "receipts/capture.receipt.json"
            )
            self.assertTrue(receipt.is_file())
            safe = receipt.read_text(encoding="utf-8")
            self.assertNotIn(credential.value, safe)
            for subject in self.population.subjects:
                self.assertNotIn(subject.raw_public_key, safe)

    def test_sink_retains_exact_wire_bytes_separately_from_canonical_envelope(self) -> None:
        import hashlib

        def noncanonical_exchange(request, *, max_response_bytes):
            request_document = json.loads(request.body)
            payload = {
                "jsonrpc": "2.0",
                "result": {"paginationToken": None, "data": []},
                "id": request_document["id"],
            }
            body = json.dumps(payload, indent=2).encode("utf-8")
            return TransportResponse(
                status_code=200,
                body=body,
                safe_headers=(),
                terminal_class="SUCCESS",
                error_class=None,
                request_started_at=FIXED_NOW,
                request_sent_at=FIXED_NOW,
                response_headers_at=FIXED_NOW,
                response_complete_at=FIXED_NOW,
            )

        credential = HeliusCredential("unit-" + "w" * 24)
        plan = HistoryCapturePlan()
        transport = BoundedHistoryTransport(
            plan=plan,
            credential=credential,
            gate=ExternalExecutionGate(EXTERNAL_AUTHORITY_PHRASE),
            http_exchange=noncanonical_exchange,
        )
        with tempfile.TemporaryDirectory() as temp:
            raw_root = Path(temp).resolve()
            sink = DurableHistorySink(
                raw_root=raw_root,
                run_id="t24a5-20260802T120003Z",
                plan=plan,
                population=self.population,
                credential=credential,
                now=lambda: FIXED_NOW,
            )
            attempt = transport.call(rpc_id=1, subject=self.population.subjects[0])
            stored = sink.record(
                rpc_id=1,
                subject=self.population.subjects[0],
                attempt=attempt,
            )
            exact_path = raw_root / stored.exact_wire_logical_location
            self.assertEqual(exact_path.read_bytes(), attempt.response.body)
            self.assertEqual(
                stored.exact_wire_response_sha256,
                hashlib.sha256(attempt.response.body).hexdigest(),
            )
            self.assertEqual(stored.exact_wire_response_bytes, len(attempt.response.body))
            self.assertNotEqual(stored.response_sha256, stored.exact_wire_response_sha256)

    def test_payload_failure_is_persisted_once_and_stops_without_retry(self) -> None:
        calls = 0

        def invalid_exchange(request, *, max_response_bytes):
            nonlocal calls
            calls += 1
            response = response_for_request(request)
            return TransportResponse(
                status_code=response.status_code,
                body=b"{invalid",
                safe_headers=(),
                terminal_class="SUCCESS",
                error_class=None,
                request_started_at=FIXED_NOW,
                request_sent_at=FIXED_NOW,
                response_headers_at=FIXED_NOW,
                response_complete_at=FIXED_NOW,
            )

        credential = HeliusCredential("unit-" + "p" * 24)
        plan = HistoryCapturePlan()
        with tempfile.TemporaryDirectory() as temp:
            sink = DurableHistorySink(
                raw_root=Path(temp).resolve(),
                run_id="t24a5-20260802T120001Z",
                plan=plan,
                population=self.population,
                credential=credential,
                now=lambda: FIXED_NOW,
            )
            result = HistoryCaptureRunner(
                plan=plan,
                population=self.population,
                transport=BoundedHistoryTransport(
                    plan=plan,
                    credential=credential,
                    gate=ExternalExecutionGate(EXTERNAL_AUTHORITY_PHRASE),
                    http_exchange=invalid_exchange,
                ),
                sink=sink,
                access=AccessAttestation(True, 210),
            ).run()
            self.assertEqual(result["terminal"], "STOP_PROVIDER_PAYLOAD")
            self.assertEqual(result["provider_calls"], 1)
            self.assertEqual(len(result["attempts"]), 1)
            self.assertEqual(calls, 1)

    def test_population_count_drift_blocks_before_any_call(self) -> None:
        credential = HeliusCredential("unit-" + "q" * 24)
        reduced = FrozenPopulation(
            subjects=self.population.subjects[:-1],
            fingerprint_sha256=self.population.fingerprint_sha256,
        )
        with tempfile.TemporaryDirectory() as temp:
            sink = DurableHistorySink(
                raw_root=Path(temp).resolve(),
                run_id="t24a5-20260802T120002Z",
                plan=HistoryCapturePlan(),
                population=reduced,
                credential=credential,
                now=lambda: FIXED_NOW,
            )
            transport = BoundedHistoryTransport(
                plan=HistoryCapturePlan(),
                credential=credential,
                gate=ExternalExecutionGate(EXTERNAL_AUTHORITY_PHRASE),
                http_exchange=response_for_request,
            )
            with self.assertRaisesRegex(Task24HistoryCaptureError, "population_call_drift"):
                HistoryCaptureRunner(
                    plan=HistoryCapturePlan(),
                    population=reduced,
                    transport=transport,
                    sink=sink,
                    access=AccessAttestation(True, 210),
                ).run()
            self.assertEqual(transport.call_count, 0)

    def test_run_id_is_utc_and_bounded(self) -> None:
        self.assertEqual(default_run_id(FIXED_NOW), "t24a5-20260802T120000Z")
        local = FIXED_NOW.astimezone(UTC) + timedelta(hours=0)
        self.assertEqual(default_run_id(local), "t24a5-20260802T120000Z")


if __name__ == "__main__":
    unittest.main()
