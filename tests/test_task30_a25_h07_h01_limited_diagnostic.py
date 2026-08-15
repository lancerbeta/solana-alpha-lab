from __future__ import annotations

import copy
import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_h07_h01_limited_diagnostic import (  # noqa: E402
    ATOM_ID,
    TERMINAL_OUTCOMES,
    A25IntegrityError,
    assess_metric_computability,
    evaluate_lane_supply,
    execute_diagnostic,
    issue_verdict,
    load_policy,
    missingness_statistics,
    precision_and_power,
    read_frozen_estimand,
    resolve_frozen_parameters,
    verify_lane_coverage,
)
from solana_alpha_lab.task30_raw_to_pit_admissibility import (  # noqa: E402
    load_policy as load_upstream_policy,
)

CONFIG_PATH = ROOT / "configs/task30_a25_h07_h01_limited_diagnostic_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/task30_a25_h07_h01_limited_diagnostic.schema.json"
FIXTURE_PATH = ROOT / "tests/fixtures/task30/h07_h01_limited_diagnostic_v1.json"
UPSTREAM_CONFIG_PATH = (
    ROOT / "configs/task30_a24_raw_to_pit_admissibility_owner_panel_v1.yaml"
)
ACCEPTANCE_PATH = (
    ROOT / "docs/evidence/task30/a25_h07_h01_limited_diagnostic_acceptance_v1.json"
)
A22_RAW = ROOT / (
    "local/task30_a22_helius_get_transactions_for_address/"
    "run=20260814T184209Z-7572a5c2/raw_response.json"
)
A23_RAW = ROOT / (
    "local/task30_a23_helius_bounded_pagination/"
    "run=20260814T220124Z-e494b5aa/page=001/raw_response.json"
)
MEASURED = datetime(2026, 8, 15, 8, 0, tzinfo=UTC)


def _slot(index: int, state: str) -> dict[str, object]:
    observed = state == "OBSERVED_TARGET_TRADES"
    carry = state == "STATE_PERSISTENCE_PROVEN"
    return {
        "slot_index": index,
        "start_at": "2026-08-12T00:00:00Z",
        "end_at": "2026-08-12T00:15:00Z",
        "state": state,
        "target_trade_count": 1 if observed else 0,
        "buy_count": 1 if observed else 0,
        "sell_count": 0,
        "volume_base_atomic": 1000 if observed else 0,
        "volume_quote_atomic": 1000 if observed else 0,
        "ohlc": {
            "open": "1" if observed else None,
            "high": "1" if observed else None,
            "low": "1" if observed else None,
            "close": "1" if observed else None,
        },
        "reserves": {
            "raw_base_reserve_atomic": 10 if observed or carry else None,
            "raw_quote_reserve_atomic": 20 if observed or carry else None,
            "virtual_quote_reserves": 30 if observed or carry else None,
            "carry_forward": carry,
        },
        "log_truncated_transactions": 0,
        "source_hashes": {"a22_raw_sha256": "a" * 64, "a23_terminal_sha256": "b" * 64},
        "measured_as_of": "2026-08-15T08:00:00Z",
    }


def _synthetic_panel(*, observed: int = 35, proven_empty: int = 1) -> list[dict[str, object]]:
    panel = [_slot(index, "PROVEN_NO_TARGET_TRADE") for index in range(proven_empty)]
    panel.extend(
        _slot(index, "OBSERVED_TARGET_TRADES")
        for index in range(proven_empty, proven_empty + observed)
    )
    panel.extend(
        _slot(index, "STATE_PERSISTENCE_PROVEN")
        for index in range(proven_empty + observed, 96)
    )
    return panel


class Task30A25LimitedDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load_policy(CONFIG_PATH)
        cls.upstream_policy = load_upstream_policy(UPSTREAM_CONFIG_PATH)
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.frozen = read_frozen_estimand(ROOT, cls.policy)

    def _result(self, panel: list[dict[str, object]] | None = None) -> dict[str, object]:
        return {
            "panel_96_slots": panel if panel is not None else _synthetic_panel(),
            "pit": {
                "event_at_basis": "on_chain_buy_sell_event_timestamp",
                "observed_at": "2026-08-14T18:42:09Z",
                "first_reliable_available_at": "2026-08-14T22:01:24Z",
                "available_to_strategy_at": "2026-08-15T08:00:00Z",
                "ingested_at": "2026-08-14T18:42:09Z",
                "measured_as_of": "2026-08-13T00:00:00Z",
                "chain_block_time_used_as_availability": False,
                "retrospective_market_history_usable": True,
                "prospective_pit_route_usable": False,
                "unknown_earlier_availability": True,
            },
            "upstream_policy": self.upstream_policy,
        }

    def test_policy_matches_closed_schema(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(
            yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        )
        self.assertEqual(self.policy["atom_id"], ATOM_ID)
        self.assertEqual(tuple(self.policy["terminal_outcomes"]), TERMINAL_OUTCOMES)

    def test_frozen_estimand_is_read_not_restated(self) -> None:
        self.assertEqual(
            self.frozen["definition_sha256"],
            self.fixture["frozen_estimand"]["definition_sha256"],
        )
        self.assertEqual(
            self.frozen["target_metrics"],
            self.fixture["frozen_estimand"]["target_metrics"],
        )
        self.assertEqual(
            self.frozen["definition_inputs"],
            self.fixture["frozen_estimand"]["definition_inputs"],
        )
        self.assertEqual(self.frozen["expected_admissibility_state"], "BLOCKED_DATA")
        self.assertEqual(
            sorted(self.frozen["definition_input_bindings"]["multi-notional route persistence"].items()),
            [
                ("entry_gate_requirement", "multi_notional_route_persistence"),
                ("lane", "ROUTE_FEASIBILITY"),
                ("state", "MISSING_UNKNOWN"),
            ],
        )

    def test_both_frozen_owners_must_agree_on_the_definition_hash(self) -> None:
        policy = copy.deepcopy(dict(self.policy))
        policy["frozen_definition"]["definition_sha256"] = "0" * 64
        with self.assertRaises(A25IntegrityError):
            read_frozen_estimand(ROOT, policy)

    def test_lane_coverage_must_be_exactly_the_frozen_field_set(self) -> None:
        verify_lane_coverage(self.policy, self.frozen)
        policy = copy.deepcopy(dict(self.policy))
        policy["lane_field_supply"]["ROUTE_FEASIBILITY"].pop("price_impact")
        with self.assertRaises(A25IntegrityError):
            verify_lane_coverage(policy, self.frozen)

    def test_declared_absent_route_field_appearing_in_the_panel_fails_closed(self) -> None:
        panel = _synthetic_panel()
        panel[0]["price_impact"] = "0"
        with self.assertRaises(A25IntegrityError):
            evaluate_lane_supply(self.policy, self._result(panel))

    def test_route_lane_is_unsupplied_and_pit_lane_carries_typed_gaps(self) -> None:
        supply = evaluate_lane_supply(self.policy, self._result())
        self.assertTrue(
            all(
                entry["supply"] == "NOT_SUPPLIED"
                for entry in supply["ROUTE_FEASIBILITY"].values()
            )
        )
        self.assertEqual(supply["PIT_MARKET"]["ohlcv"]["supply"], "PARTIAL_TYPED_GAP")
        self.assertEqual(supply["PIT_MARKET"]["ohlcv"]["non_null_observations"], 35)
        self.assertEqual(
            supply["PIT_MARKET"]["liquidity_state"]["supply"], "PARTIAL_TYPED_GAP"
        )
        self.assertEqual(
            supply["PIT_MARKET"]["liquidity_state"]["eligible_rows"], 36
        )
        self.assertEqual(supply["PIT_MARKET"]["typed_gap_or_failure"]["supply"], "SUPPLIED")

    def test_route_metrics_are_not_computable_on_a_trade_only_panel(self) -> None:
        supply = evaluate_lane_supply(self.policy, self._result())
        metrics = assess_metric_computability(self.policy, self.frozen, supply)
        self.assertEqual(metrics["PIT_ROUTE_SURVIVAL"]["computability"], "NOT_COMPUTABLE")
        self.assertEqual(metrics["QUOTE_AVAILABILITY"]["computability"], "NOT_COMPUTABLE")
        self.assertEqual(
            metrics["MISSINGNESS_RATE"]["computability"], "COMPUTABLE_WITH_TYPED_GAPS"
        )

    def test_state_persistence_slots_are_never_counted_as_observed_trades(self) -> None:
        statistics = missingness_statistics(self.policy, self._result())
        self.assertEqual(statistics["slots_consumed_as_observed"], 35)
        self.assertEqual(statistics["slots_consumed_as_typed_gap"], 61)
        self.assertEqual(statistics["consumed_slot_states"]["STATE_PERSISTENCE_PROVEN"], 60)
        self.assertEqual(statistics["ohlc_missingness_rate"], "0.635417")
        self.assertEqual(statistics["fresh_liquidity_observation_slots"], 35)
        self.assertEqual(statistics["carried_forward_liquidity_slots"], 60)
        self.assertFalse(statistics["carry_forward_is_an_observation"])

    def test_unknown_coverage_fails_closed(self) -> None:
        panel = _synthetic_panel()
        panel[95]["state"] = "UNKNOWN_COVERAGE"
        with self.assertRaises(A25IntegrityError):
            missingness_statistics(self.policy, self._result(panel))

    def test_single_cluster_has_no_valid_standard_error(self) -> None:
        statistics = missingness_statistics(self.policy, self._result())
        power = precision_and_power(self.policy, statistics)
        self.assertEqual(power["independent_clusters"], 1)
        self.assertEqual(power["effective_sample_size_for_the_estimand"], 1)
        self.assertEqual(power["between_cluster_degrees_of_freedom"], 0)
        self.assertIsNone(power["standard_error"])
        self.assertIsNone(power["confidence_interval"])
        self.assertEqual(
            power["naive_binomial_se_validity"],
            "INVALID_SLOTS_ARE_NOT_INDEPENDENT_REPLICATES",
        )

    def test_claiming_independent_slots_fails_closed(self) -> None:
        policy = copy.deepcopy(dict(self.policy))
        policy["cluster_design"]["slots_are_independent_replicates"] = True
        statistics = missingness_statistics(self.policy, self._result())
        with self.assertRaises(A25IntegrityError):
            precision_and_power(policy, statistics)

    def test_unresolved_frozen_parameter_is_reported_not_guessed(self) -> None:
        parameters = resolve_frozen_parameters(self.policy, self.frozen, self._result())
        self.assertFalse(parameters["NOTIONAL_BUCKET_SET_V1"]["resolved"])
        self.assertIsNone(parameters["NOTIONAL_BUCKET_SET_V1"]["resolved_bucket_count"])
        self.assertTrue(parameters["OBSERVATION_WINDOW_15M"]["resolved"])
        self.assertEqual(parameters["OBSERVATION_WINDOW_15M"]["resolved_as_seconds"], 900)

    def test_verdict_rule_reaches_every_non_stop_outcome(self) -> None:
        specification = {"minimum_clusters_for_two_group_cluster_level_test": 4}
        base = {
            "policy": self.policy,
            "frozen": self.frozen,
            "supply": {"ROUTE_FEASIBILITY": {"notional": {"supply": "NOT_SUPPLIED"}}},
            "parameters": {"OBSERVATION_WINDOW_15M": {"resolved": True}},
            "power": {"independent_clusters": 8},
            "specification": specification,
        }
        gap = issue_verdict(
            **base, metrics={"QUOTE_AVAILABILITY": {"computability": "NOT_COMPUTABLE"}}
        )
        self.assertEqual(
            gap["terminal_decision"],
            "ESTIMAND_NOT_COMPUTABLE_TARGETED_CAPABILITY_GAP_PROVEN",
        )
        computable = {"QUOTE_AVAILABILITY": {"computability": "COMPUTABLE"}}
        underpowered = issue_verdict(
            **{**base, "power": {"independent_clusters": 1}}, metrics=computable
        )
        self.assertEqual(
            underpowered["terminal_decision"],
            "ESTIMAND_MEASURABLE_UNDERPOWERED_WITH_EXACT_DATA_SPEC",
        )
        ambiguous = issue_verdict(
            **{**base, "parameters": {"NOTIONAL_BUCKET_SET_V1": {"resolved": False}}},
            metrics=computable,
        )
        self.assertEqual(
            ambiguous["terminal_decision"],
            "ESTIMAND_MEASURABLE_UNDERPOWERED_WITH_EXACT_DATA_SPEC",
        )
        decisive = issue_verdict(**base, metrics=computable)
        self.assertEqual(
            decisive["terminal_decision"],
            "ESTIMAND_MEASURABLE_AND_DECISIVE_ON_FROZEN_PANEL",
        )
        for outcome in (gap, underpowered, ambiguous, decisive):
            self.assertEqual(outcome["task_state"], "BLOCKED_DATA")
            self.assertFalse(outcome["rc001_promoted"])

    def test_input_hash_drift_is_stop_integrity_conflict(self) -> None:
        result = execute_diagnostic(
            repo_root=ROOT,
            policy=self.policy,
            a22_payload=b'{"jsonrpc":"2.0","id":"x","result":{"data":[],"paginationToken":"x"}}',
            a23_payload=b'{"jsonrpc":"2.0","id":"y","result":{"data":[],"paginationToken":null}}',
            measured_as_of=MEASURED,
        )
        self.assertEqual(result["terminal_decision"], "STOP_INTEGRITY_CONFLICT")
        self.assertIn("A22_HASH_DRIFT", result["verdict"]["integrity_error"])
        self.assertEqual(result["verdict"]["task_state"], "BLOCKED_DATA")

    def test_tracked_acceptance_declares_no_source_change(self) -> None:
        receipt = json.loads(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(receipt["project_sources_disposition"], {"kind": "NO_CHANGE"})
        self.assertEqual(receipt["task_state"], "BLOCKED_DATA")
        self.assertIn("NO_EFFECT_ESTIMATE", receipt["non_claims"])
        self.assertIn("NO_RC001_PROMOTION", receipt["non_claims"])

    # DELIVERY_PREFLIGHT_NONCRITICAL_SKIP: docs/evidence/task30/a25_h07_h01_limited_diagnostic_runtime_receipt_v1.json
    @unittest.skipUnless(
        A22_RAW.is_file() and A23_RAW.is_file(), "retained raw is local-only"
    )
    def test_live_retained_batch_reproduces_the_measurability_verdict(self) -> None:
        expected = self.fixture["expected_if_live_bytes_present"]
        result = execute_diagnostic(
            repo_root=ROOT,
            policy=self.policy,
            a22_payload=A22_RAW.read_bytes(),
            a23_payload=A23_RAW.read_bytes(),
            measured_as_of=MEASURED,
        )
        self.assertEqual(result["terminal_decision"], expected["terminal_decision"])
        self.assertEqual(
            result["verdict"]["not_computable_metrics"], expected["not_computable_metrics"]
        )
        self.assertEqual(
            result["verdict"]["missing_capability_lanes"],
            expected["missing_capability_lanes"],
        )
        self.assertEqual(
            result["statistics"]["slots_consumed_as_observed"],
            expected["slots_consumed_as_observed"],
        )
        self.assertEqual(
            result["statistics"]["slots_consumed_as_typed_gap"],
            expected["slots_consumed_as_typed_gap"],
        )
        self.assertEqual(
            result["statistics"]["ohlc_missingness_rate"], expected["ohlc_missingness_rate"]
        )
        self.assertEqual(
            result["precision_and_power"]["standard_error_status"],
            expected["standard_error_status"],
        )
        self.assertIsNone(result["precision_and_power"]["standard_error"])
        self.assertEqual(
            result["required_data_specification"]["unresolved_frozen_parameters"],
            expected["unresolved_frozen_parameters"],
        )
        self.assertFalse(
            result["required_data_specification"]["decisive_scale_derivable_from_this_panel"]
        )
        self.assertEqual(result["side_effects"]["provider_requests"], 0)
        self.assertFalse(result["pit"]["prospective_pit_route_usable"])
        self.assertFalse(result["pit"]["chain_block_time_used_as_availability"])

    # DELIVERY_PREFLIGHT_NONCRITICAL_SKIP: docs/evidence/task30/a25_h07_h01_limited_diagnostic_runtime_receipt_v1.json
    @unittest.skipUnless(
        A22_RAW.is_file() and A23_RAW.is_file(), "retained raw is local-only"
    )
    def test_live_diagnostic_is_idempotent_over_frozen_inputs(self) -> None:
        payloads = (A22_RAW.read_bytes(), A23_RAW.read_bytes())
        first = execute_diagnostic(
            repo_root=ROOT,
            policy=self.policy,
            a22_payload=payloads[0],
            a23_payload=payloads[1],
            measured_as_of=MEASURED,
        )
        second = execute_diagnostic(
            repo_root=ROOT,
            policy=self.policy,
            a22_payload=payloads[0],
            a23_payload=payloads[1],
            measured_as_of=MEASURED,
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
