from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.contracts.schema_v1 import (  # noqa: E402
    QuoteAttempt,
    QuoteStatus,
    Side,
)
from solana_alpha_lab.jupiter_quote_logger import (  # noqa: E402
    BUY_PANELS,
    MAX_RESPONSE_BYTES,
    NETWORK_ENABLED,
    USDC_MINT,
    DependentSellDecision,
    QuoteRequest,
    TransportObservation,
    build_buy_panel_requests,
    decide_dependent_sell,
    load_synthetic_fixture,
    observation_from_mapping,
    project_fixture_case,
    project_quote_observation,
    request_from_mapping,
    safe_preflight_summary,
)
from solana_alpha_lab.storage.raw_envelope import (  # noqa: E402
    verify_raw_api_event,
)

FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task10"
    / "jupiter_quote_logger_cases_v1.json"
)
MODULE_PATH = ROOT / "src" / "solana_alpha_lab" / "jupiter_quote_logger.py"
SCRIPT_PATH = ROOT / "scripts" / "run_task10_jupiter_quote_logger.py"
EXPECTED_FIXTURE_SHA256 = (
    "744d79202805746271547123a6aff23cb299eb2b0b52e3639f4bf5a2554a2382"
)
EXPECTED_TERMINAL_STATES = {
    "QUOTE_AVAILABLE",
    "NO_ROUTE",
    "PROVIDER_ERROR",
    "INVALID_RESPONSE",
    "TIMEOUT",
}


class Task10JupiterQuoteLoggerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_bytes = FIXTURE_PATH.read_bytes()
        cls.document = load_synthetic_fixture(FIXTURE_PATH)
        cls.cases = {
            case["case_id"]: case for case in cls.document["cases"]
        }

    def test_fixture_identity_and_offline_authority_are_exact(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.fixture_bytes).hexdigest(),
            EXPECTED_FIXTURE_SHA256,
        )
        self.assertEqual(self.document["task_id"], "TASK-10")
        self.assertEqual(
            self.document["atom_id"],
            "T10-A3_LOCAL_QUOTE_LOGGER_IMPLEMENTATION",
        )
        self.assertTrue(self.document["synthetic_only"])
        authority = self.document["authority"]
        self.assertFalse(authority["network"])
        self.assertEqual(authority["provider_api_rpc_wss_calls"], 0)
        self.assertEqual(authority["raw_data_writes"], 0)
        self.assertEqual(authority["dependency_changes"], 0)
        self.assertFalse(authority["credential_use"])
        self.assertEqual(authority["cash_spend_usd_cents"], 0)
        self.assertEqual(authority["wallet_signer_transaction_actions"], 0)
        for field in ("commit", "push", "pull_request", "merge", "ui_changes"):
            with self.subTest(field=field):
                self.assertFalse(authority[field])

    def test_exact_buy_panels_use_integer_atomics(self) -> None:
        requests = build_buy_panel_requests(
            selected_output_mint="task09-followup-mint-synthetic",
            output_decimals=6,
        )
        self.assertEqual(
            tuple(
                (
                    int(request.business_key.rsplit("-", 1)[1]),
                    request.input_requested_atomic,
                )
                for request in requests
            ),
            BUY_PANELS,
        )
        self.assertEqual(
            {request.input_mint for request in requests},
            {USDC_MINT},
        )
        self.assertTrue(all(request.side == Side.BUY for request in requests))
        self.assertEqual(
            [request.attempt_ordinal for request in requests],
            [1, 2, 3, 4],
        )

    def test_all_five_terminal_states_project_to_existing_model(self) -> None:
        projections = [
            project_fixture_case(case) for case in self.document["cases"]
        ]
        self.assertEqual(
            {projection.quote_attempt.status for projection in projections},
            EXPECTED_TERMINAL_STATES,
        )
        for case, projection in zip(
            self.document["cases"],
            projections,
            strict=True,
        ):
            row = projection.quote_attempt
            self.assertIsInstance(row, QuoteAttempt)
            self.assertEqual(row.status, case["expected_status"])
            self.assertEqual(row.error_class, case["expected_error_class"])
            self.assertEqual(
                projection.stop_reason,
                case["expected_stop_reason"],
            )
            self.assertEqual(row.raw_event_id, projection.raw_event.raw_event_id)
            self.assertEqual(
                row.response_content_sha256,
                projection.raw_event.content_sha256,
            )
            verify_raw_api_event(projection.raw_event)

    def test_available_quote_preserves_exact_output_and_route_identity(
        self,
    ) -> None:
        case = self.cases["QUOTE_AVAILABLE_BUY"]
        projection = project_fixture_case(case)
        row = projection.quote_attempt
        self.assertEqual(row.output_quoted_atomic, 2_500_000)
        self.assertEqual(row.route_count, 1)
        route_plan = case["observation"]["response_body"]["routePlan"]
        expected_route_id = hashlib.sha256(
            json.dumps(
                route_plan,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(row.route_id, expected_route_id)
        self.assertEqual(row.context_slot, 100)
        self.assertEqual(row.provider_latency_ms, 100)
        self.assertEqual(row.quote_age_ms, 20)

    def test_normalized_fees_stay_null_and_output_is_not_reduced(self) -> None:
        row = project_fixture_case(
            self.cases["QUOTE_AVAILABLE_BUY"]
        ).quote_attempt
        self.assertEqual(row.output_quoted_atomic, 2_500_000)
        self.assertIsNone(row.provider_fee_atomic)
        self.assertIsNone(row.platform_fee_atomic)
        self.assertIsNone(row.fee_mint)
        self.assertIsNone(row.included_in_output_amount)
        self.assertEqual(
            row.quality_flags,
            "PROVIDER_ROUTE_FEE_DETAIL_RAW_ONLY",
        )

    def test_explicit_no_route_is_not_generic_http_failure(self) -> None:
        row = project_fixture_case(
            self.cases["NO_ROUTE_SELL"]
        ).quote_attempt
        self.assertEqual(row.status, QuoteStatus.NO_ROUTE)
        self.assertEqual(row.route_count, 0)
        self.assertIsNone(row.output_quoted_atomic)
        self.assertIsNone(row.error_class)

    def test_provider_failure_is_not_no_route(self) -> None:
        row = project_fixture_case(
            self.cases["PROVIDER_RATE_LIMIT"]
        ).quote_attempt
        self.assertEqual(row.status, QuoteStatus.PROVIDER_ERROR)
        self.assertEqual(row.error_class, "RATE_LIMITED")
        self.assertIsNone(row.route_count)
        with self.assertRaisesRegex(
            ValidationError,
            "no_route_state_incoherent",
        ):
            payload = row.model_dump()
            payload["side"] = Side.BUY
            payload["status"] = QuoteStatus.NO_ROUTE
            payload["route_count"] = 0
            QuoteAttempt.model_validate(
                payload
            )

    def test_timeout_has_no_response_and_never_becomes_no_route(self) -> None:
        projection = project_fixture_case(
            self.cases["TIMEOUT_NO_RESPONSE"]
        )
        row = projection.quote_attempt
        self.assertEqual(row.status, QuoteStatus.TIMEOUT)
        self.assertIsNone(row.response_at)
        self.assertIsNone(row.provider_latency_ms)
        self.assertIsNone(row.quote_age_ms)
        self.assertIsNone(row.route_count)
        self.assertIn(
            b'"response_body_present":false',
            projection.raw_event.redacted_body,
        )

    def test_transaction_payload_is_fail_closed_and_not_retained(self) -> None:
        projection = project_fixture_case(
            self.cases["INVALID_TRANSACTION_PAYLOAD"]
        )
        row = projection.quote_attempt
        self.assertEqual(row.status, QuoteStatus.INVALID_RESPONSE)
        self.assertEqual(
            row.error_class,
            "TRANSACTION_PAYLOAD_FORBIDDEN",
        )
        self.assertEqual(
            projection.stop_reason,
            "V2_TRANSACTION_OR_INSTRUCTION_SURFACE_REQUIRED",
        )
        self.assertNotIn(
            b"synthetic-forbidden-payload",
            projection.raw_event.redacted_body,
        )

    def test_stale_quote_is_invalid_not_available(self) -> None:
        case = self.cases["QUOTE_AVAILABLE_BUY"]
        request = request_from_mapping(case["request"])
        observation = replace(
            observation_from_mapping(case["observation"]),
            stale=True,
        )
        projection = project_quote_observation(request, observation)
        self.assertEqual(
            projection.quote_attempt.status,
            QuoteStatus.INVALID_RESPONSE,
        )
        self.assertEqual(
            projection.quote_attempt.error_class,
            "STALE_RESPONSE",
        )

    def test_unexpected_top_level_key_stops_as_schema_drift(self) -> None:
        case = copy.deepcopy(self.cases["QUOTE_AVAILABLE_BUY"])
        case["observation"]["response_body"]["newProviderField"] = True
        projection = project_fixture_case(case)
        self.assertEqual(
            projection.quote_attempt.status,
            QuoteStatus.INVALID_RESPONSE,
        )
        self.assertEqual(
            projection.quote_attempt.error_class,
            "SCHEMA_MISMATCH",
        )
        self.assertEqual(
            projection.stop_reason,
            "UNCLASSIFIABLE_SCHEMA_DRIFT",
        )

    def test_observed_typed_additive_schema_replays_offline(self) -> None:
        case = copy.deepcopy(self.cases["QUOTE_AVAILABLE_BUY"])
        body = case["observation"]["response_body"]
        body.update(
            {
                "instructionVersion": None,
                "loadedLongtailToken": False,
                "longtailMarketQuoteReport": None,
                "mostReliableAmmsQuoteReport": {
                    "info": {
                        "synthetic-amm-key": "Synthetic AMM",
                    }
                },
                "otherRoutePlans": None,
                "swapUsdValue": "9.99",
                "useIncurredSlippageForQuoting": None,
                "useRewards": None,
            }
        )
        swap_info = body["routePlan"][0]["swapInfo"]
        del swap_info["feeAmount"]
        del swap_info["feeMint"]
        swap_info["updateContextSlot"] = "100"
        body["routePlan"][0]["bps"] = None

        projection = project_fixture_case(case)

        self.assertEqual(
            projection.quote_attempt.status,
            QuoteStatus.QUOTE_AVAILABLE,
        )
        self.assertEqual(
            projection.quote_attempt.quality_flags,
            "PROVIDER_ROUTE_FEE_FIELDS_ABSENT_RAW_ONLY",
        )
        self.assertIsNone(projection.quote_attempt.provider_fee_atomic)
        self.assertIsNone(projection.quote_attempt.platform_fee_atomic)
        self.assertIsNone(projection.quote_attempt.fee_mint)
        self.assertIsNone(
            projection.quote_attempt.included_in_output_amount
        )
        self.assertIsNone(projection.stop_reason)

    def test_typed_extension_shape_change_stays_fail_closed(self) -> None:
        case = copy.deepcopy(self.cases["QUOTE_AVAILABLE_BUY"])
        case["observation"]["response_body"]["instructionVersion"] = "V0"
        projection = project_fixture_case(case)
        self.assertEqual(
            projection.quote_attempt.status,
            QuoteStatus.INVALID_RESPONSE,
        )
        self.assertEqual(
            projection.stop_reason,
            "UNCLASSIFIABLE_SCHEMA_DRIFT",
        )

    def test_unexpected_swap_info_key_stays_fail_closed(self) -> None:
        case = copy.deepcopy(self.cases["QUOTE_AVAILABLE_BUY"])
        swap_info = case["observation"]["response_body"]["routePlan"][0][
            "swapInfo"
        ]
        swap_info["newProviderField"] = "unexpected"
        projection = project_fixture_case(case)
        self.assertEqual(
            projection.quote_attempt.status,
            QuoteStatus.INVALID_RESPONSE,
        )
        self.assertEqual(
            projection.stop_reason,
            "UNCLASSIFIABLE_SCHEMA_DRIFT",
        )

    def test_mismatched_atomic_input_is_invalid(self) -> None:
        case = copy.deepcopy(self.cases["QUOTE_AVAILABLE_BUY"])
        case["observation"]["response_body"]["inAmount"] = "9999999"
        projection = project_fixture_case(case)
        self.assertEqual(
            projection.quote_attempt.status,
            QuoteStatus.INVALID_RESPONSE,
        )
        self.assertEqual(
            projection.quote_attempt.error_class,
            "SCHEMA_MISMATCH",
        )

    def test_multi_step_route_is_not_rejected_by_false_weight_sum(self) -> None:
        case = copy.deepcopy(self.cases["QUOTE_AVAILABLE_BUY"])
        second = copy.deepcopy(
            case["observation"]["response_body"]["routePlan"][0]
        )
        second["swapInfo"]["ammKey"] = "synthetic-second-amm"
        case["observation"]["response_body"]["routePlan"].append(second)
        projection = project_fixture_case(case)
        self.assertEqual(
            projection.quote_attempt.status,
            QuoteStatus.QUOTE_AVAILABLE,
        )
        self.assertEqual(projection.quote_attempt.route_count, 2)

    def test_non_finite_json_number_is_invalid(self) -> None:
        case = copy.deepcopy(self.cases["QUOTE_AVAILABLE_BUY"])
        case["observation"]["response_body"]["timeTaken"] = float("nan")
        projection = project_fixture_case(case)
        self.assertEqual(
            projection.quote_attempt.status,
            QuoteStatus.INVALID_RESPONSE,
        )
        self.assertEqual(
            projection.quote_attempt.error_class,
            "SCHEMA_MISMATCH",
        )

    def test_response_byte_cap_is_fail_closed_without_body_retention(
        self,
    ) -> None:
        case = self.cases["QUOTE_AVAILABLE_BUY"]
        request = request_from_mapping(case["request"])
        observation = replace(
            observation_from_mapping(case["observation"]),
            response_body=b"x" * (MAX_RESPONSE_BYTES + 1),
        )
        projection = project_quote_observation(request, observation)
        self.assertEqual(
            projection.quote_attempt.status,
            QuoteStatus.INVALID_RESPONSE,
        )
        self.assertEqual(
            projection.stop_reason,
            "RESPONSE_BYTE_CAP_EXHAUSTED",
        )
        self.assertNotIn(
            b"x" * 128,
            projection.raw_event.redacted_body,
        )

    def test_reverse_sell_uses_exact_buy_output_atomic(self) -> None:
        buy = project_fixture_case(self.cases["QUOTE_AVAILABLE_BUY"])
        decision = decide_dependent_sell(buy, attempt_ordinal=5)
        self.assertIsInstance(decision, DependentSellDecision)
        self.assertEqual(
            decision.disposition,
            "ATTEMPT_EXACT_BUY_OUTPUT_ATOMIC",
        )
        assert decision.request is not None
        self.assertEqual(
            decision.request.input_requested_atomic,
            buy.quote_attempt.output_quoted_atomic,
        )
        self.assertEqual(decision.request.side, Side.SELL)
        self.assertEqual(
            decision.request.business_key,
            buy.quote_attempt.business_key,
        )

    def test_unavailable_buy_does_not_create_sell_attempt(self) -> None:
        unavailable = project_fixture_case(
            self.cases["PROVIDER_RATE_LIMIT"]
        )
        decision = decide_dependent_sell(unavailable, attempt_ordinal=6)
        self.assertIsNone(decision.request)
        self.assertEqual(
            decision.disposition,
            "NOT_ATTEMPTED_BUY_PREREQUISITE_FAILED",
        )

    def test_projection_is_deterministic_for_identical_input(self) -> None:
        first = project_fixture_case(self.cases["QUOTE_AVAILABLE_BUY"])
        second = project_fixture_case(self.cases["QUOTE_AVAILABLE_BUY"])
        self.assertEqual(first.quote_attempt, second.quote_attempt)
        self.assertEqual(first.raw_event, second.raw_event)

    def test_timestamp_order_is_enforced_before_projection(self) -> None:
        case = self.cases["QUOTE_AVAILABLE_BUY"]
        value = copy.deepcopy(case["observation"])
        value["available_to_strategy_at"] = "2026-07-27T23:59:59Z"
        with self.assertRaisesRegex(
            ValueError,
            "first_reliable_after_strategy_availability",
        ):
            observation_from_mapping(value)

    def test_request_validation_rejects_float_atomic_amount(self) -> None:
        case = self.cases["QUOTE_AVAILABLE_BUY"]
        value = copy.deepcopy(case["request"])
        value["input_requested_atomic"] = 10_000_000.0
        with self.assertRaisesRegex(
            ValueError,
            "input_requested_atomic_must_be_positive_integer",
        ):
            request_from_mapping(value)

    def test_preflight_summary_is_zero_side_effect(self) -> None:
        summary = safe_preflight_summary(self.document)
        self.assertFalse(NETWORK_ENABLED)
        self.assertFalse(summary["network_enabled"])
        self.assertEqual(summary["provider_api_rpc_wss_calls"], 0)
        self.assertEqual(summary["raw_data_writes"], 0)
        self.assertEqual(summary["cash_spend_usd_cents"], 0)
        self.assertEqual(summary["wallet_signer_transaction_actions"], 0)
        self.assertEqual(summary["case_count"], 5)

    def test_launcher_default_and_case_replay_are_read_only(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "task10_quote_logger_launcher",
            SCRIPT_PATH,
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        before = sorted(
            path.relative_to(ROOT).as_posix()
            for path in ROOT.rglob("*")
            if path.is_file()
        )
        output = io.StringIO()
        with redirect_stdout(output):
            default_code = module.main([])
            replay_code = module.main(["--case", "QUOTE_AVAILABLE_BUY"])
        after = sorted(
            path.relative_to(ROOT).as_posix()
            for path in ROOT.rglob("*")
            if path.is_file()
        )
        self.assertEqual(default_code, 0)
        self.assertEqual(replay_code, 0)
        self.assertEqual(before, after)
        rendered = output.getvalue()
        self.assertIn("TASK10_QUOTE_LOGGER_PREFLIGHT: PASS", rendered)
        self.assertIn("TASK10_QUOTE_LOGGER_REPLAY: PASS", rendered)
        self.assertIn('"network_enabled":false', rendered)
        self.assertIn('"raw_data_written":false', rendered)

    def test_launcher_execute_is_a_hard_tripwire(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "task10_quote_logger_execute_tripwire",
            SCRIPT_PATH,
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        output = io.StringIO()
        with redirect_stdout(output):
            code = module.main(
                ["--execute"],
                input_fn=lambda _: "wrong-authority",
            )
        self.assertEqual(code, 2)
        self.assertIn(
            "TASK10_EXTERNAL: BLOCKED_AUTHORITY_PHRASE",
            output.getvalue(),
        )

    def test_runtime_contains_no_network_or_transaction_implementation(
        self,
    ) -> None:
        combined = (
            MODULE_PATH.read_text(encoding="utf-8")
            + SCRIPT_PATH.read_text(encoding="utf-8")
        )
        prohibited_imports = (
            "import requests",
            "import httpx",
            "import urllib",
            "import socket",
            "import aiohttp",
            "import websockets",
        )
        for marker in prohibited_imports:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, combined)
        prohibited_actions = (
            "send_transaction",
            "sign_transaction",
            "simulate_transaction",
            "swapTransaction",
            "wallet_connect",
        )
        for marker in prohibited_actions:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, combined)

    def test_fixture_loader_rejects_duplicate_case_ids(self) -> None:
        document = copy.deepcopy(self.document)
        document["cases"].append(copy.deepcopy(document["cases"][0]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text(
                json.dumps(document),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "fixture_case_id_duplicate",
            ):
                load_synthetic_fixture(path)

    def test_transport_observation_rejects_timeout_with_body(self) -> None:
        instant = datetime(2026, 7, 28, tzinfo=timezone.utc)
        with self.assertRaisesRegex(
            ValueError,
            "timeout_cannot_have_response",
        ):
            TransportObservation(
                requested_at=instant,
                response_at=None,
                first_reliable_available_at=instant + timedelta(seconds=10),
                available_to_strategy_at=instant + timedelta(seconds=10),
                ingested_at=instant + timedelta(seconds=10),
                http_status_code=None,
                response_body={},
                timed_out=True,
            )

    def test_quote_request_identities_bind_ordinal_and_exact_amount(
        self,
    ) -> None:
        request = request_from_mapping(
            self.cases["QUOTE_AVAILABLE_BUY"]["request"]
        )
        changed_ordinal = replace(request, attempt_ordinal=2)
        changed_amount = replace(
            request,
            input_requested_atomic=request.input_requested_atomic + 1,
        )
        self.assertNotEqual(
            request.idempotency_key,
            changed_ordinal.idempotency_key,
        )
        self.assertNotEqual(
            request.idempotency_key,
            changed_amount.idempotency_key,
        )
        self.assertNotEqual(request.request_hash, changed_amount.request_hash)


if __name__ == "__main__":
    unittest.main()
