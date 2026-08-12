from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_pool_activity_discriminator import (
    PoolActivityDiscriminatorError,
    build_pool_activity_request,
    classify_pool_activity_response,
    evaluate_pool_activity_policy,
)


CONFIG = ROOT / "configs/task30_pool_activity_discriminator_v1.yaml"
SCHEMA = ROOT / "catalog/schemas/task30_pool_activity_discriminator.schema.json"
FIXTURE = ROOT / "tests/fixtures/task30/pool_activity_discriminator_v1.json"
CONTRACT = ROOT / "docs/contracts/task30_pool_activity_discriminator_contract_v1.md"
MODULE = ROOT / "src/solana_alpha_lab/task30_pool_activity_discriminator.py"
TEST = Path(__file__)
DESIGN = ROOT / "docs/superpowers/specs/2026-08-12-task30-pool-activity-discriminator-design.md"
PLAN = ROOT / "docs/superpowers/plans/2026-08-12-task30-pool-activity-discriminator.md"
ACCEPTANCE = ROOT / "docs/evidence/task30/a16_pool_activity_discriminator_acceptance_v1.json"
FACTORY_FIT = ROOT / "docs/evidence/task30/a16_pool_activity_discriminator_factory_fit_v1.json"
CATALOG = ROOT / "catalog/assets/core.yaml"
POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
REQUEST_ID = "task30-a16-pool-activity-discriminator"
ARTIFACTS = {
    "contract": CONTRACT,
    "config": CONFIG,
    "schema": SCHEMA,
    "fixture": FIXTURE,
    "module": MODULE,
    "test": TEST,
    "design": DESIGN,
    "plan": PLAN,
}
CATALOG_IDS = {
    "CONTRACT-T30-POOL-ACTIVITY-DISCRIMINATOR-001": CONTRACT,
    "CONFIG-T30-POOL-ACTIVITY-DISCRIMINATOR-001": CONFIG,
    "SCHEMA-T30-POOL-ACTIVITY-DISCRIMINATOR-001": SCHEMA,
    "FIXTURE-T30-POOL-ACTIVITY-DISCRIMINATOR-001": FIXTURE,
    "MODULE-T30-POOL-ACTIVITY-DISCRIMINATOR-001": MODULE,
    "TEST-T30-POOL-ACTIVITY-DISCRIMINATOR-001": TEST,
    "EVIDENCE-T30-A16-POOL-ACTIVITY-DISCRIMINATOR-001": ACCEPTANCE,
    "EVIDENCE-T30-A16-POOL-ACTIVITY-DISCRIMINATOR-FACTORY-FIT-001": FACTORY_FIT,
}


def policy() -> dict[str, object]:
    loaded = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def response(records: list[dict[str, object]]) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": REQUEST_ID, "result": records}


def synthetic_record(index: int, block_time: int) -> dict[str, object]:
    return {
        "signature": f"sig-{index:04d}",
        "slot": 10000 - index,
        "err": None,
        "memo": None,
        "blockTime": block_time,
        "confirmationStatus": "confirmed",
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Task30PoolActivityDiscriminatorTests(unittest.TestCase):
    def records(self) -> dict[str, dict[str, object]]:
        records = fixture()["records"]
        assert isinstance(records, dict)
        return copy.deepcopy(records)

    def classify(self, records: list[dict[str, object]]) -> dict[str, object]:
        return classify_pool_activity_response(policy(), response(records))

    def test_policy_is_closed_exact_and_zero_authority(self) -> None:
        document = policy()
        Draft202012Validator(
            json.loads(SCHEMA.read_text(encoding="utf-8"))
        ).validate(document)
        summary = evaluate_pool_activity_policy(document)
        self.assertEqual(summary["pool_address"], POOL)
        self.assertEqual(summary["max_requests"], 1)
        self.assertEqual(summary["transaction_followups"], 0)
        self.assertTrue(all(value in (0, False) for value in document["authority"].values()))

    def test_request_is_exact_pool_targeted_and_contains_no_secret_or_url(self) -> None:
        body = build_pool_activity_request(policy())
        self.assertEqual(
            body,
            {
                "jsonrpc": "2.0",
                "id": REQUEST_ID,
                "method": "getSignaturesForAddress",
                "params": [POOL, {"commitment": "confirmed", "limit": 1000}],
            },
        )
        rendered = json.dumps(body, sort_keys=True).casefold()
        self.assertNotIn("api_key", rendered)
        self.assertNotIn("://", rendered)

    def test_policy_rejects_widening_extra_fields_and_type_confusion(self) -> None:
        mutations = (
            (("runtime_limits", "max_requests"), True),
            (("runtime_limits", "estimated_credit_cap"), 1.0),
            (("runtime_limits", "transaction_followups"), 1),
            (("execution_controls", "retry"), True),
            (("authority", "provider_api_rpc_wss_calls"), 1),
            (("request", "limit"), 999),
        )
        for pointer, value in mutations:
            candidate = copy.deepcopy(policy())
            candidate[pointer[0]][pointer[1]] = value
            with self.subTest(pointer=pointer):
                with self.assertRaises(PoolActivityDiscriminatorError):
                    evaluate_pool_activity_policy(candidate)
        extra = copy.deepcopy(policy())
        extra["notes"] = "widen"
        with self.assertRaises(PoolActivityDiscriminatorError):
            evaluate_pool_activity_policy(extra)

    def test_interior_signature_is_positive_and_wins_over_valid_null_or_boundary(self) -> None:
        records = self.records()
        result = self.classify(
            [records["after_terminal"], records["inside"], records["start_boundary"], records["null_time"]]
        )
        self.assertEqual(result["terminal_state"], "POOL_ADDRESS_ACTIVITY_OBSERVED_ROUTE_REVIEW_REQUIRED")
        self.assertEqual(result["interior_signature_count"], 1)
        self.assertIs(result["pool_address_activity_observed"], True)

    def test_only_a_page_reaching_before_ack_supports_no_direct_activity(self) -> None:
        records = self.records()
        short_bracketed = self.classify([records["after_terminal"], records["before_start"]])
        bracketed_records = [
            synthetic_record(index, 1786527600 - index)
            for index in range(10)
        ] + [
            synthetic_record(index + 10, 1786526800 - index)
            for index in range(990)
        ]
        bracketed = self.classify(bracketed_records)
        for result in (short_bracketed, bracketed):
            self.assertEqual(result["terminal_state"], "NO_DIRECT_POOL_ACTIVITY_SUPPORTED")
            self.assertIs(result["pool_inactive"], False)
            self.assertIs(result["zero_volume"], False)

    def test_boundary_null_short_unbracketed_and_truncated_pages_remain_typed_unknown(self) -> None:
        records = self.records()
        start_bracket = self.classify([records["after_terminal"], records["start_boundary"]])
        ack_boundary = copy.deepcopy(records["start_boundary"])
        ack_boundary["signature"] = "sig-ack-boundary"
        ack_boundary["blockTime"] = 1786526873
        terminal_boundary = copy.deepcopy(records["start_boundary"])
        terminal_boundary["signature"] = "sig-terminal-boundary"
        terminal_boundary["blockTime"] = 1786527473
        null_time = self.classify([records["after_terminal"], records["before_start"], records["null_time"]])
        short_unbracketed = self.classify([records["after_terminal"]])
        empty = self.classify([])
        truncated = self.classify(
            [synthetic_record(index, 1786529000 - index) for index in range(1000)]
        )
        self.assertEqual(start_bracket["terminal_state"], "NO_DIRECT_POOL_ACTIVITY_SUPPORTED")
        self.assertEqual(self.classify([records["after_terminal"], ack_boundary])["terminal_state"], "BOUNDARY_TIME_AMBIGUOUS_UNKNOWN")
        self.assertEqual(self.classify([records["after_terminal"], terminal_boundary])["terminal_state"], "BOUNDARY_TIME_AMBIGUOUS_UNKNOWN")
        self.assertEqual(null_time["terminal_state"], "NULL_BLOCK_TIME_UNKNOWN")
        self.assertEqual(short_unbracketed["terminal_state"], "HISTORY_COVERAGE_UNKNOWN")
        self.assertEqual(empty["terminal_state"], "HISTORY_COVERAGE_UNKNOWN")
        self.assertEqual(truncated["terminal_state"], "PAGE_TRUNCATED_UNKNOWN")
        self.assertTrue(all(item["unknown"] for item in (null_time, short_unbracketed, empty, truncated)))

    def test_rpc_error_malformed_schema_ordering_and_duplicate_fail_closed(self) -> None:
        records = self.records()
        cases = (
            ({"jsonrpc": "2.0", "id": REQUEST_ID, "error": {"code": -1, "message": "synthetic"}}, "MALFORMED_OR_RPC_ERROR_UNKNOWN"),
            ({"jsonrpc": "2.0", "id": "wrong", "result": []}, "MALFORMED_OR_RPC_ERROR_UNKNOWN"),
            (response([{**records["before_start"], "extra": 1}]), "ORDERING_OR_SCHEMA_DRIFT_UNKNOWN"),
            (response([records["before_start"], records["after_terminal"]]), "ORDERING_OR_SCHEMA_DRIFT_UNKNOWN"),
            (response([records["after_terminal"], records["after_terminal"]]), "ORDERING_OR_SCHEMA_DRIFT_UNKNOWN"),
            (response([{**records["inside"], "err": True}]), "ORDERING_OR_SCHEMA_DRIFT_UNKNOWN"),
            (response([{**records["inside"], "err": "not-a-transaction-error"}]), "ORDERING_OR_SCHEMA_DRIFT_UNKNOWN"),
            (response([{**records["inside"], "err": {"NotATransactionError": True}}]), "ORDERING_OR_SCHEMA_DRIFT_UNKNOWN"),
            (response([{**records["inside"], "err": {"InstructionError": [256, "BorshIoError"]}}]), "ORDERING_OR_SCHEMA_DRIFT_UNKNOWN"),
            (response([{**records["inside"], "err": {"DuplicateInstruction": 256}}]), "ORDERING_OR_SCHEMA_DRIFT_UNKNOWN"),
            (response([{**records["inside"], "err": {"InsufficientFundsForRent": {"account_index": 256}}}]), "ORDERING_OR_SCHEMA_DRIFT_UNKNOWN"),
        )
        for payload, expected in cases:
            with self.subTest(expected=expected):
                result = classify_pool_activity_response(policy(), payload)
                self.assertEqual(result["terminal_state"], expected)
                self.assertIs(result["unknown"], True)

    def test_slot_order_ties_and_transaction_error_union_are_explicit(self) -> None:
        records = self.records()
        first = copy.deepcopy(records["inside"])
        tied = copy.deepcopy(records["inside"])
        tied["signature"] = "sig-tied"
        tied["err"] = {"InstructionError": [0, {"Custom": 6001}]}
        accepted = self.classify([first, tied])
        self.assertEqual(
            accepted["terminal_state"],
            "POOL_ADDRESS_ACTIVITY_OBSERVED_ROUTE_REVIEW_REQUIRED",
        )
        inverted = copy.deepcopy(records["inside"])
        inverted["slot"] = records["after_terminal"]["slot"] + 1
        rejected = self.classify([records["after_terminal"], inverted])
        self.assertEqual(rejected["terminal_state"], "ORDERING_OR_SCHEMA_DRIFT_UNKNOWN")
        inconsistent_tie = copy.deepcopy(tied)
        inconsistent_tie["blockTime"] = tied["blockTime"] + 1
        rejected_tie = self.classify([first, inconsistent_tie])
        self.assertEqual(rejected_tie["terminal_state"], "ORDERING_OR_SCHEMA_DRIFT_UNKNOWN")
        for valid_error in (
            "ProgramCacheHitMaxLimit",
            {"InstructionError": [255, "BorshIoError"]},
        ):
            candidate = copy.deepcopy(first)
            candidate["err"] = valid_error
            with self.subTest(valid_error=valid_error):
                self.assertEqual(
                    self.classify([candidate])["terminal_state"],
                    "POOL_ADDRESS_ACTIVITY_OBSERVED_ROUTE_REVIEW_REQUIRED",
                )

    def test_every_result_preserves_market_and_task_nonclaims(self) -> None:
        results = (
            self.classify([]),
            self.classify([self.records()["inside"]]),
            classify_pool_activity_response(policy(), {"bad": "envelope"}),
        )
        for result in results:
            for key in (
                "pumpswap_trade",
                "price",
                "volume",
                "empty_interval",
                "interval_complete",
                "pit_admissible",
                "task30_trial",
                "task30_acceptance",
                "numeric_netreturn",
            ):
                self.assertIs(result[key], False)

    def test_acceptance_is_hash_bound_catalogued_and_does_not_promote_task30(self) -> None:
        acceptance = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
        self.assertEqual(
            acceptance["decision"],
            "OFFLINE_DISCRIMINATOR_READY_FOR_OWNER_GATE",
        )
        self.assertEqual(acceptance["validation_status"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(acceptance["state_change"], "NONE")
        self.assertEqual(acceptance["project_sources_disposition"]["kind"], "NO_CHANGE")
        self.assertEqual(set(acceptance["artifact_bindings"]), set(ARTIFACTS))
        for artifact_id, path in ARTIFACTS.items():
            binding = acceptance["artifact_bindings"][artifact_id]
            self.assertEqual(binding["path"], path.relative_to(ROOT).as_posix())
            self.assertEqual(binding["sha256"], sha256(path))
        self.assertTrue(all(value in (0, False) for value in acceptance["authority"].values()))
        self.assertTrue(all(value is False for value in acceptance["non_claims"].values()))

        factory_fit = json.loads(FACTORY_FIT.read_text(encoding="utf-8"))
        self.assertEqual(factory_fit["review_scope"], "FULL_REVIEW")
        self.assertEqual(factory_fit["verdict"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(factory_fit["state_change"], "NONE")

        catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
        records = {record["asset_id"]: record for record in catalog["records"]}
        for asset_id, path in CATALOG_IDS.items():
            self.assertEqual(
                records[asset_id]["location"]["repository_path"],
                path.relative_to(ROOT).as_posix(),
            )


if __name__ == "__main__":
    unittest.main()
