from __future__ import annotations

import copy
import json
import sys
import unittest
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.provider_smoke import (  # noqa: E402
    EXPECTED_ATTEMPT_COUNT,
    EXPECTED_CASE_COUNT,
    EXPECTED_HELIUS_CREDIT_CAP,
    FROZEN_SPEC_SHA256,
    NETWORK_DISABLED_BY_DEFAULT,
    PROVIDER_POLICIES,
    RUNTIME_EVIDENCE_AS_OF,
    NetworkDisabledError,
    ProhibitedPayloadError,
    SmokeContractError,
    SmokeRunGuard,
    StopConditionError,
    build_attempt_raw_event,
    compile_smoke_spec,
    load_frozen_smoke_plan,
    materialize_case,
    validate_response_payload,
)

SPEC_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "pre_git"
    / "task01"
    / "provider_smoke_spec_v1.yaml"
)
FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task07"
    / "provider_smoke_contract_v1.json"
)


class Task07ProviderSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.plan = load_frozen_smoke_plan(SPEC_PATH)
        cls.document = yaml.safe_load(SPEC_PATH.read_bytes())
        cls.times = {
            key: datetime.fromisoformat(value.replace("Z", "+00:00"))
            for key, value in cls.fixture["timestamps"].items()
        }

    def test_frozen_hash_and_inventory_compile_exactly(self) -> None:
        self.assertEqual(self.plan.spec_sha256, FROZEN_SPEC_SHA256)
        self.assertEqual(
            self.fixture["frozen_spec_sha256"],
            FROZEN_SPEC_SHA256,
        )
        self.assertEqual(
            [case.case_id for case in self.plan.cases],
            self.fixture["expected_case_ids"],
        )
        self.assertEqual(
            list(self.plan.attempt_ids),
            self.fixture["expected_attempt_ids"],
        )
        self.assertEqual(len(self.plan.cases), EXPECTED_CASE_COUNT)
        self.assertEqual(len(self.plan.attempt_ids), EXPECTED_ATTEMPT_COUNT)

    def test_runtime_overlay_is_exact_and_account_state_is_explicit(self) -> None:
        self.assertEqual(
            self.fixture["runtime_evidence_as_of"],
            RUNTIME_EVIDENCE_AS_OF,
        )
        for provider, expected in self.fixture["provider_policies"].items():
            with self.subTest(provider=provider):
                policy = PROVIDER_POLICIES[provider]
                self.assertEqual(policy.pacing_group, expected["group"])
                self.assertEqual(
                    policy.minimum_interval_seconds,
                    expected["minimum_interval_seconds"],
                )
                self.assertEqual(
                    policy.account_required,
                    expected["account_required"],
                )
                self.assertEqual(policy.credit_cap, expected["credit_cap"])

    def test_compiler_fails_on_frozen_hash_or_case_inventory_drift(self) -> None:
        changed_path = Path("not-the-frozen-file")
        with self.assertRaises(FileNotFoundError):
            load_frozen_smoke_plan(changed_path)

        changed = copy.deepcopy(self.document)
        changed["cases"].pop()
        with self.assertRaisesRegex(SmokeContractError, "case_count_mismatch"):
            compile_smoke_spec(changed)

        changed = copy.deepcopy(self.document)
        changed["run_order"][0][0], changed["run_order"][0][1] = (
            changed["run_order"][0][1],
            changed["run_order"][0][0],
        )
        with self.assertRaisesRegex(SmokeContractError, "run_order_mismatch"):
            compile_smoke_spec(changed)

    def test_budget_method_and_forbidden_field_drift_fail_closed(self) -> None:
        changed = copy.deepcopy(self.document)
        changed["global_budget"]["cash_cap_usd"] = 1
        with self.assertRaisesRegex(
            SmokeContractError,
            "unexpected_budget_cash_cap_usd",
        ):
            compile_smoke_spec(changed)

        changed = copy.deepcopy(self.document)
        changed["security_boundary"]["allowed_http_methods"].append("POST")
        with self.assertRaisesRegex(
            SmokeContractError,
            "unexpected_allowed_method_set",
        ):
            compile_smoke_spec(changed)

        changed = copy.deepcopy(self.document)
        changed["cases"][0]["params"] = [{"payer": "synthetic"}]
        with self.assertRaisesRegex(
            ProhibitedPayloadError,
            "forbidden_request_field",
        ):
            compile_smoke_spec(changed)

        changed = copy.deepcopy(self.document)
        changed["failure_taxonomy"]["terminal_classes"].remove("NO_ROUTE")
        with self.assertRaisesRegex(
            SmokeContractError,
            "failure_taxonomy_drift",
        ):
            compile_smoke_spec(changed)

        changed = copy.deepcopy(self.document)
        changed["cases"][11]["limits"]["max_open_seconds"] = 11
        with self.assertRaisesRegex(
            SmokeContractError,
            "wss_case_limits_drift",
        ):
            compile_smoke_spec(changed)

    def test_dynamic_producers_and_derived_sell_amount_are_deterministic(
        self,
    ) -> None:
        expected = self.fixture["public_and_dynamic_bindings"]
        self.assertEqual(
            set(self.plan.public_bindings),
            set(expected["frozen"]),
        )
        self.assertEqual(self.plan.output_producers, expected["producers"])

        request = materialize_case(
            self.plan,
            "J08",
            produced_bindings=self.fixture["sample_bindings"],
        )
        self.assertEqual(request["query"]["amount"], 1_000_000)
        self.assertEqual(
            request["query"]["inputMint"],
            self.fixture["sample_bindings"]["RECENT_PUMP_MINT"],
        )

    def test_missing_unknown_and_invalid_dynamic_bindings_fail(self) -> None:
        with self.assertRaisesRegex(
            SmokeContractError,
            "binding_missing:RECENT_PUMP_MINT",
        ):
            materialize_case(self.plan, "J07")

        with self.assertRaisesRegex(
            SmokeContractError,
            "undeclared_produced_binding",
        ):
            materialize_case(
                self.plan,
                "J01",
                produced_bindings={"UNDECLARED": "value"},
            )

        bindings = dict(self.fixture["sample_bindings"])
        bindings["RECENT_PUMP_DECIMALS"] = 19
        with self.assertRaisesRegex(
            SmokeContractError,
            "recent_pump_decimals_out_of_range",
        ):
            materialize_case(
                self.plan,
                "J08",
                produced_bindings=bindings,
            )
        with self.assertRaisesRegex(
            SmokeContractError,
            "undeclared_produced_binding",
        ):
            materialize_case(
                self.plan,
                "J08",
                produced_bindings={
                    "RECENT_PUMP_SELL_AMOUNT_ATOMIC": 1,
                },
            )
        with self.assertRaisesRegex(
            SmokeContractError,
            "recent_pump_mint_invalid",
        ):
            materialize_case(
                self.plan,
                "J07",
                produced_bindings={"RECENT_PUMP_MINT": "not-a-pubkey"},
            )

    def test_network_is_disabled_by_default_and_no_transport_is_embedded(
        self,
    ) -> None:
        self.assertTrue(NETWORK_DISABLED_BY_DEFAULT)
        guard = SmokeRunGuard(self.plan)
        with self.assertRaisesRegex(
            NetworkDisabledError,
            "network_disabled_by_default",
        ):
            guard.authorize_attempt("H01#1", monotonic_seconds=0.0)

        source = (SRC / "solana_alpha_lab" / "provider_smoke.py").read_text(
            encoding="utf-8"
        )
        for forbidden_import in (
            "import httpx",
            "import requests",
            "import urllib",
            "import websockets",
            "ClientSession",
        ):
            self.assertNotIn(forbidden_import, source)

    def test_request_materialization_preserves_read_only_rpc_contract(
        self,
    ) -> None:
        request = materialize_case(self.plan, "H09", produced_bindings={
            "RAPTOR_RECENT_SIGNATURE": self.fixture["sample_bindings"][
                "RAPTOR_RECENT_SIGNATURE"
            ]
        })
        self.assertEqual(request["method"], "POST_JSON_RPC_READ_ONLY")
        self.assertEqual(request["rpc_method"], "getTransaction")
        self.assertEqual(
            request["params"][0],
            self.fixture["sample_bindings"]["RAPTOR_RECENT_SIGNATURE"],
        )
        self.assertNotIn("url", request)
        self.assertNotIn("headers", request)

    def test_quote_null_or_typed_empty_transaction_is_allowed(self) -> None:
        samples = self.fixture["response_samples"]
        for name in ("quote_without_transaction", "typed_quote_error"):
            with self.subTest(name=name):
                redacted = validate_response_payload(
                    self.plan,
                    "J01",
                    samples[name],
                )
                self.assertTrue(redacted.startswith(b"{"))

    def test_transaction_and_payment_payloads_fail_closed(self) -> None:
        samples = self.fixture["response_samples"]
        with self.assertRaisesRegex(
            ProhibitedPayloadError,
            "nonempty_transaction_payload",
        ):
            validate_response_payload(
                self.plan,
                "J01",
                samples["prohibited_transaction"],
            )
        with self.assertRaisesRegex(
            ProhibitedPayloadError,
            "payment_or_x402_payload",
        ):
            validate_response_payload(
                self.plan,
                "R01",
                samples["prohibited_payment"],
            )
        with self.assertRaisesRegex(
            ProhibitedPayloadError,
            "nonempty_transaction_payload",
        ):
            validate_response_payload(
                self.plan,
                "J01",
                {"transaction": ""},
            )

    def test_rpc_transaction_details_are_not_quote_transaction_bytes(
        self,
    ) -> None:
        response = {
            "result": {
                "slot": 123,
                "transaction": {
                    "message": {"accountKeys": []},
                    "signatures": [],
                },
            }
        }
        redacted = validate_response_payload(self.plan, "H09", response)
        self.assertIn(b'"transaction"', redacted)

    def test_malformed_payload_is_retained_unless_safety_is_uninspectable(
        self,
    ) -> None:
        malformed = b'{"result":'
        self.assertEqual(
            validate_response_payload(self.plan, "H01", malformed),
            malformed,
        )
        with self.assertRaisesRegex(
            ProhibitedPayloadError,
            "uninspectable_transaction_payload",
        ):
            validate_response_payload(
                self.plan,
                "J01",
                b'{"transaction":',
            )

    def test_response_size_cap_applies_before_redaction(self) -> None:
        oversized = b"x" * (self.plan.max_response_bytes_per_attempt + 1)
        with self.assertRaisesRegex(
            StopConditionError,
            "response_too_large",
        ):
            validate_response_payload(self.plan, "H01", oversized)

    def test_task06_redaction_and_raw_event_identity_are_reused(self) -> None:
        request = materialize_case(self.plan, "H01")
        synthetic_value = "SYNTHETIC_SENSITIVE_VALUE_12345"
        event = build_attempt_raw_event(
            self.plan,
            case_id="H01",
            materialized_request=request,
            response_body=self.fixture["response_samples"][
                "secret_bearing_success"
            ],
            response_status="SUCCESS",
            error_class=None,
            event_time=self.times["event_time"],
            observed_at=self.times["observed_at"],
            available_to_strategy_at=self.times[
                "available_to_strategy_at"
            ],
            first_reliable_available_at=self.times[
                "first_reliable_available_at"
            ],
            ingested_at=self.times["ingested_at"],
            explicit_secret_values=(synthetic_value,),
        )
        self.assertEqual(event.source, "HELIUS_RPC")
        self.assertEqual(event.redaction_version, "1.0")
        self.assertNotIn(synthetic_value.encode(), event.redacted_body)
        self.assertIn(b"[REDACTED]", event.redacted_body)
        self.assertEqual(event.raw_event_id, f"raw-{event.idempotency_key}")

        changed_request = dict(request)
        changed_request["provider"] = "JUPITER_SWAP"
        with self.assertRaisesRegex(
            SmokeContractError,
            "request_provider_mismatch",
        ):
            build_attempt_raw_event(
                self.plan,
                case_id="H01",
                materialized_request=changed_request,
                response_body={"result": "ok"},
                response_status="SUCCESS",
                error_class=None,
                event_time=self.times["event_time"],
                observed_at=self.times["observed_at"],
                available_to_strategy_at=self.times[
                    "available_to_strategy_at"
                ],
                first_reliable_available_at=self.times[
                    "first_reliable_available_at"
                ],
                ingested_at=self.times["ingested_at"],
            )

    def test_guard_enforces_pacing_and_duplicate_attempts(self) -> None:
        guard_plan = self.guard_plan("H01", "H02")
        guard = SmokeRunGuard(guard_plan, network_authorized=True)
        guard.authorize_attempt("H01#1", monotonic_seconds=10.0)
        with self.assertRaisesRegex(
            StopConditionError,
            "concurrency_one_attempt_still_open",
        ):
            guard.authorize_attempt("H02#1", monotonic_seconds=11.0)
        guard.record_attempt(
            "H01#1",
            response_size_bytes=100,
            terminal_class="SUCCESS",
            credit_cost=1,
        )
        with self.assertRaisesRegex(
            StopConditionError,
            "retry_or_duplicate_attempt_forbidden",
        ):
            guard.authorize_attempt("H01#1", monotonic_seconds=11.0)
        with self.assertRaisesRegex(
            StopConditionError,
            "provider_pacing_interval_not_met",
        ):
            guard.authorize_attempt("H02#1", monotonic_seconds=10.1)
        guard.authorize_attempt("H02#1", monotonic_seconds=10.2)

    def test_guard_enforces_cash_credit_and_response_caps(self) -> None:
        cash_guard = SmokeRunGuard(
            self.guard_plan("J01"),
            network_authorized=True,
        )
        cash_guard.authorize_attempt("J01#1", monotonic_seconds=0.0)
        with self.assertRaisesRegex(
            StopConditionError,
            "cash_spend_forbidden",
        ):
            cash_guard.record_attempt(
                "J01#1",
                response_size_bytes=1,
                terminal_class="SUCCESS",
                cash_cost_usd=0.01,
            )

        credit_guard = SmokeRunGuard(
            self.guard_plan("H01"),
            network_authorized=True,
        )
        credit_guard.authorize_attempt("H01#1", monotonic_seconds=0.0)
        with self.assertRaisesRegex(
            StopConditionError,
            "helius_credit_cap_exceeded",
        ):
            credit_guard.record_attempt(
                "H01#1",
                response_size_bytes=1,
                terminal_class="SUCCESS",
                credit_cost=EXPECTED_HELIUS_CREDIT_CAP + 1,
            )

        byte_guard = SmokeRunGuard(
            self.guard_plan("R01"),
            network_authorized=True,
        )
        byte_guard.authorize_attempt("R01#1", monotonic_seconds=0.0)
        with self.assertRaisesRegex(
            StopConditionError,
            "response_too_large",
        ):
            byte_guard.record_attempt(
                "R01#1",
                response_size_bytes=(
                    self.plan.max_response_bytes_per_attempt + 1
                ),
                terminal_class="SUCCESS",
            )

        terminal_guard = SmokeRunGuard(
            self.guard_plan("H01"),
            network_authorized=True,
        )
        terminal_guard.authorize_attempt("H01#1", monotonic_seconds=0.0)
        with self.assertRaisesRegex(
            SmokeContractError,
            "unknown_terminal_class",
        ):
            terminal_guard.record_attempt(
                "H01#1",
                response_size_bytes=1,
                terminal_class="NOT_A_TERMINAL_CLASS",
            )

    def test_three_consecutive_failures_stop_provider_group(self) -> None:
        guard = SmokeRunGuard(
            self.guard_plan("R01", "R02", "R03", "R04"),
            network_authorized=True,
        )
        for index, attempt_id in enumerate(("R01#1", "R02#1", "R03#1")):
            guard.authorize_attempt(
                attempt_id,
                monotonic_seconds=float(index),
            )
            if index < 2:
                guard.record_attempt(
                    attempt_id,
                    response_size_bytes=10,
                    terminal_class="PROVIDER_5XX",
                )
            else:
                with self.assertRaisesRegex(
                    StopConditionError,
                    "three_consecutive_provider_failures",
                ):
                    guard.record_attempt(
                        attempt_id,
                        response_size_bytes=10,
                        terminal_class="PROVIDER_5XX",
                    )
        with self.assertRaisesRegex(
            StopConditionError,
            "provider_group_stopped",
        ):
            guard.authorize_attempt("R04#1", monotonic_seconds=4.0)

    def test_full_plan_rejects_out_of_order_attempt(self) -> None:
        guard = SmokeRunGuard(self.plan, network_authorized=True)
        with self.assertRaisesRegex(
            StopConditionError,
            "attempt_order_mismatch",
        ):
            guard.authorize_attempt("H02#1", monotonic_seconds=0.0)

    def guard_plan(self, *case_ids: str):
        selected = tuple(
            self.plan.case_by_id[case_id]
            for case_id in case_ids
        )
        attempt_ids = tuple(
            f"{case_id}#{index}"
            for case_id in case_ids
            for index in range(
                1,
                self.plan.case_by_id[case_id].planned_attempts + 1,
            )
        )
        return replace(
            self.plan,
            cases=selected,
            attempt_ids=attempt_ids,
        )


if __name__ == "__main__":
    unittest.main()
