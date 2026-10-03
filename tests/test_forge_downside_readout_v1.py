"""Fixed downside arithmetic and admitted-sample regressions."""

from __future__ import annotations

import math
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from solana_alpha_lab.factory.hfic_grounded_discovery import (
    GroundedDiscoveryError,
    execute_discovery_from_rows,
)
from solana_alpha_lab.factory.hfic_temporal_discovery import downside_descriptive
from solana_alpha_lab.factory import hfic_temporal_discovery as temporal
from solana_alpha_lab.factory import hfic_grounded_discovery as grounded
from tests.test_hfic_temporal_discovery_v1 import (
    LIQ,
    PRICE,
    _binding,
    _census,
    _obs,
    _spec,
)


class DownsideNumerics(unittest.TestCase):
    def test_detached_and_runner_up_scopes_drop_compact_numbers(self) -> None:
        from solana_alpha_lab.factory.hfic_session import (
            _bind_selected_look, _rebind_runner_up_grounded_evidence,
        )
        evidence = {"result": {"some": "computed"}, "result_sha256": "00" * 32,
                    "result_refs": ["saved-look"], "descriptive_readout": {"matched": {"median_target": -0.5}}}
        detached = _bind_selected_look(evidence, {}, store=None)
        self.assertFalse(detached["look_confirms_selected"])
        self.assertNotIn("result", detached)
        self.assertNotIn("descriptive_readout", detached)
        packet = {"grounded_evidence": evidence}
        _rebind_runner_up_grounded_evidence(packet, {})
        self.assertNotIn("result", packet["grounded_evidence"])
        self.assertNotIn("descriptive_readout", packet["grounded_evidence"])

    def test_g3_same_median_different_event_frequency(self) -> None:
        spec = _spec(
            tier="SIMPLE_SCREEN",
            features=[{"name": "mark", "op": "point_value", "field_id": LIQ, "point": "Y3600"}],
            all=[{"feature": "mark", "op": "gte", "value": 0.5}],
            cost_profile=None,
        )
        census, observations = [], []
        for i in range(40):
            mint = f"g3-{i:02}"
            census.append(_census(mint))
            target = -0.5 if i in (0, 1, 2, 10) else 0.0
            observations.extend(
                [
                    _obs(mint, "X300", LIQ, 1000),
                    _obs(mint, "X300", PRICE, 1),
                    _obs(mint, "Y3600", LIQ, 1 if i < 10 else 0),
                    _obs(mint, "Y3600", PRICE, 1),
                    _obs(mint, "Y7200", PRICE, 1 + target),
                ]
            )
        result = execute_discovery_from_rows(census, observations, spec, _binding())["summary"]
        matched = result["downside"]
        baseline = result["baseline"]["downside"]
        self.assertEqual((result["matched_n"], result["observed_target_n"]), (10, 10))
        self.assertEqual((result["mean_target"], result["median_target"]), (-0.15, 0.0))
        self.assertEqual(result["baseline"]["mean_target"], -0.05)
        self.assertEqual((matched["le_minus_20_rate"], baseline["le_minus_20_rate"]), (0.3, 0.1))
        self.assertEqual((matched["le_minus_50_rate"], baseline["le_minus_50_rate"]), (0.3, 0.1))
        self.assertEqual((matched["negative_mass"], baseline["negative_mass"]), (1.5, 2.0))
        self.assertAlmostEqual(matched["worst_negative_share"], 1 / 3)
        self.assertEqual(baseline["worst_negative_share"], 0.25)
        self.assertEqual((matched["es10_return"], baseline["es10_return"]), (-0.5, -0.5))
        self.assertEqual(result["pooled"]["downside"], matched)
        self.assertEqual(result["by_cohort"][0]["downside"], matched)
        self.assertEqual(result["ablations"][0]["downside"]["observed_n"], 40)

    def test_fractional_tail_empty_positive_and_exact_boundaries(self) -> None:
        tail = downside_descriptive([-1.0, -0.5] + [0.0] * 13, missing_n=2)
        self.assertAlmostEqual(tail["es10_return"], -5 / 6)
        self.assertEqual(tail["es10_tail_mass_n"], 1.5)
        for field, expected in (("p05", -0.65), ("p10", -0.3), ("p25", 0.0)):
            self.assertAlmostEqual(tail[field], expected)
        empty = downside_descriptive([], missing_n=7)
        self.assertEqual((empty["status"], empty["observed_n"], empty["missing_n"]), ("NO_OBSERVED_TARGET", 0, 7))
        self.assertIsNone(empty["le_minus_20_rate"])
        self.assertIsNone(empty["es10_return"])
        self.assertIsNone(empty["worst_negative_share"])
        self.assertIsNone(empty["negative_mass"])
        zero = downside_descriptive([0, 0], missing_n=0)
        self.assertEqual((zero["negative_mass"], zero["le_minus_20_rate"]), (0, 0))
        self.assertIsNone(zero["worst_negative_share"])
        positive = downside_descriptive([0.1], missing_n=0)
        self.assertAlmostEqual(positive["p05"], 0.1)
        self.assertAlmostEqual(positive["es10_return"], 0.1)
        boundary = downside_descriptive([-0.5, -0.2, -0.2 + 1e-12], missing_n=0)
        self.assertEqual((boundary["le_minus_20_n"], boundary["le_minus_50_n"]), (2, 1))
        with self.assertRaises(GroundedDiscoveryError) as stop:
            downside_descriptive([math.inf], missing_n=0)
        self.assertEqual(stop.exception.code, "TEMPORAL_TARGET_NONFINITE")

    def test_pre_outcome_ablation_and_calendar_missing_support(self) -> None:
        spec = _spec(tier="SIMPLE_SCREEN", features=[{"name": "mark", "op": "point_value", "field_id": LIQ, "point": "Y3600"}], all=[{"feature": "mark", "op": "gte", "value": 0.5}], cost_profile=None)
        census, rows = [], []
        for i in range(4):
            mint = f"missing-{i}"
            census.append(_census(mint))
            rows.extend([_obs(mint, "X300", LIQ, 1000), _obs(mint, "X300", PRICE, 1), _obs(mint, "Y3600", LIQ, 1 if i < 2 else 0), _obs(mint, "Y3600", PRICE, 1)])
            if i in (0, 3):
                rows.append(_obs(mint, "Y7200", PRICE, 0.5))
        result = execute_discovery_from_rows(census, rows, spec, _binding())["summary"]
        self.assertEqual((result["downside"]["observed_n"], result["downside"]["missing_n"]), (1, 1))
        for row in (result["baseline"], result["ablations"][0]):
            self.assertEqual((row["downside"]["observed_n"], row["downside"]["missing_n"]), (2, 2))
        self.assertEqual(result["by_calendar_block"][0]["downside"]["missing_n"], 1)
        self.assertEqual(temporal.temporal_result_coherence(result)["status"], "COHERENT")
        damaged = copy.deepcopy(result)
        damaged["baseline"]["downside"]["le_minus_50_rate"] = 0.0
        self.assertEqual(temporal.temporal_result_coherence(damaged)["status"], "INCOHERENT")
        missing_block = copy.deepcopy(result)
        del missing_block["downside"]
        self.assertEqual(temporal.temporal_result_coherence(missing_block)["status"], "INCOHERENT")
        for field in ("p05", "le_minus_50_rate", "negative_mass", "worst_negative_share"):
            bad_type = copy.deepcopy(result)
            bad_type["downside"][field] = str(bad_type["downside"][field])
            self.assertEqual(temporal.temporal_result_coherence(bad_type)["status"], "INCOHERENT")

    def test_compact_packet_keeps_comparison_and_labels_truncation(self) -> None:
        # Existing canonical-order view lists, representative 4 cohorts/28 days.
        from solana_alpha_lab.factory.hfic_grounded_discovery import descriptive_return_readout
        from solana_alpha_lab.factory.hfic_preflight import FORGE_OPERATIONAL_PACKET_MAX_BYTES
        from tests.test_hfic_temporal_result_coherence_v1 import DISJOINT_BINDING, _disjoint, _query
        census, rows = _disjoint()
        result = execute_discovery_from_rows(census, rows, _query(), DISJOINT_BINDING)["summary"]
        result["by_calendar_block"] = [{**result["by_calendar_block"][0], "view": f"DAY_{i:02}"} for i in range(28)]
        compact = descriptive_return_readout(result)
        self.assertEqual(compact["matched"]["downside"], result["downside"])
        self.assertEqual(compact["baseline"]["downside"], result["baseline"]["downside"])
        self.assertEqual(compact["details"]["by_cohort"][0]["view"], result["by_cohort"][0]["cohort_id"])
        self.assertEqual(compact["detail_truncation"]["by_calendar_block"], {"total": 28, "included": 4, "truncated": True})
        self.assertEqual([row["view"] for row in compact["details"]["by_calendar_block"]], [f"DAY_{i:02}" for i in range(4)])
        self.assertLess(len(json.dumps(compact).encode()), FORGE_OPERATIONAL_PACKET_MAX_BYTES)
        self.assertEqual(FORGE_OPERATIONAL_PACKET_MAX_BYTES, 65536)

    def test_calendar_missing_only_uses_same_keys_and_explicit_truncation(self) -> None:
        from datetime import timedelta
        from solana_alpha_lab.factory.hfic_grounded_discovery import descriptive_return_readout
        from tests.test_hfic_temporal_result_coherence_v1 import _member_rows, _rows, _query
        from tests.test_hfic_temporal_discovery_v1 import ANCHOR, COHORT, RELEASE, _bind

        census, observations = _rows([
            _member_rows(f"calendar-{day}", COHORT, RELEASE, mark=1.2,
                         exit_price=0.5 if day in (0, 5) else None,
                         anchor=ANCHOR + timedelta(days=day))
            for day in range(6)
        ])
        with v4_writer():
            old = grounded.execute_discovery_from_rows(census, observations, _query(), [_bind(COHORT, RELEASE)])["summary"]
        new = grounded.execute_discovery_from_rows(census, observations, _query(), [_bind(COHORT, RELEASE)])["summary"]
        old_rows = {row["view"]: row for row in old["by_calendar_block"]}
        new_rows = {row["view"]: row for row in new["by_calendar_block"]}
        self.assertEqual((new["matched_n"], new["observed_target_n"], new["missing_target_n"]), (6, 2, 4))
        self.assertEqual(len(old_rows), 2)
        self.assertEqual(len(new_rows), 6)
        for key, old_row in old_rows.items():
            self.assertEqual((new_rows[key]["observed_n"], new_rows[key]["mean_target"]),
                             (old_row["observed_n"], old_row["mean_target"]))
        for key in new_rows.keys() - old_rows.keys():
            self.assertEqual(new_rows[key]["observed_n"], 0)
            self.assertIsNone(new_rows[key]["mean_target"])
            self.assertEqual(new_rows[key]["downside"]["missing_n"], 1)
        temporal.assert_downside_revision_preserves_v4(old, new)
        compact = descriptive_return_readout(new)
        self.assertEqual(compact["detail_truncation"]["by_calendar_block"],
                         {"total": 6, "included": 4, "truncated": True})
        self.assertEqual(compact["matched"]["downside"]["observed_n"], 2)
        self.assertEqual(compact["matched"]["downside"]["missing_n"], 4)
        self.assertEqual(sum(row["downside"]["observed_n"] for row in compact["details"]["by_calendar_block"]), 1)


@contextlib.contextmanager
def v4_writer():
    """Emulate the predecessor producer, never fabricate store bindings."""
    real = grounded.execute_discovery_from_rows

    def calculate(*args, **kwargs):
        computed = real(*args, **kwargs)
        result = computed["summary"]
        result.pop("downside", None)
        result.pop("downside_readout_exposure", None)
        result["viewed_variants"].remove(temporal.DOWNSIDE_PROFILE)
        result["pooled"].pop("downside", None)
        for row in [result["baseline"], *result["ablations"], *result["by_cohort"], *result["by_calendar_block"]]:
            row.pop("downside", None)
            row.pop("median_target", None)
        result["by_calendar_block"] = [row for row in result["by_calendar_block"] if row["observed_n"]]
        return computed

    with mock.patch.object(temporal, "TEMPORAL_CALCULATION_VERSION", temporal.TEMPORAL_CALCULATION_VERSION_V4), mock.patch.object(grounded, "execute_discovery_from_rows", calculate):
        yield


class ClosedRevisionVertical(unittest.TestCase):
    def test_ordinary_crash_replay_completes_landing_once(self) -> None:
        from solana_alpha_lab.factory import hfic_ordinary_operation as ordinary
        from solana_alpha_lab.factory.research_store import ResearchStore
        from tests.test_hfic_cli import run_cli
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _forge, _operation, _publish_focus, _simple
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root, receipt = _publish_focus(workspace, "ORDINARY_CRASH_REPLAY")
            spec = _simple("ordinary-crash-replay")
            scope = {"population": "BASE_X", "decision_timestamp": "Y3600", "target": temporal.temporal_target_label(spec), "estimand": "price_relative_proxy", "explanatory_condition": "mark", "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1"}
            spec_path, scope_path, op_path = [workspace / f"{name}.json" for name in ("spec", "scope", "op")]
            for path, body in [(spec_path, spec), (scope_path, scope), (op_path, _operation(spec, focus="ORDINARY_CRASH_REPLAY", journal=receipt["search_key_sha256"], market=receipt["market_evidence_epoch_sha256"], text="one limited MAIN", cap={"main": 1, "adaptive": 0, "preview": 0}))]:
                path.write_text(json.dumps(body), encoding="utf-8")
            with mock.patch.object(ordinary, "note_look_landed", side_effect=RuntimeError("after-result-before-landing")), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError):
                    _forge().cmd_discovery_execute(root, store_root=data_root, census_path=None, observations_path=None, binding_path=None, spec_path=spec_path, journal_scope=receipt["search_key_sha256"], candidate_scope_path=scope_path, explicit_data_root=data_root, operation_path=op_path)
            store = ResearchStore(data_root, create_if_missing=False)
            operations = ordinary.list_operations(store)
            op_sha = operations[-1]["operation_sha256"]
            self.assertEqual(ordinary.get_operation(store, op_sha)["status"], "OPEN")
            looks = grounded.list_discovery_looks(store, receipt["search_key_sha256"])
            self.assertEqual(len(looks), 1)
            before = {r.record_id: r.model_dump_json() for r in store.iter_committed_records()}
            args = ("discovery-execute", "--store", str(data_root), "--spec", str(spec_path), "--candidate-scope", str(scope_path), "--journal-scope", receipt["search_key_sha256"], "--operation-sha256", op_sha, "--format", "json")
            cold = run_cli(*args, data_root=data_root)
            self.assertEqual(cold.returncode, 0, cold.stderr + cold.stdout)
            readout = json.loads(cold.stdout)
            self.assertFalse(readout["values_loaded"])
            self.assertTrue(readout["writes"])
            self.assertEqual(readout["ordinary_operation"], "PAUSED_CAP")
            self.assertEqual(readout["ordinary_operation_readout"]["next_action"], "AUTHORIZE_ADDITIONAL_LOOKS")
            self.assertEqual(readout["record_delta"], {"discovery_look_records": 0, "ordinary_operation_records": 1})
            self.assertEqual(readout["scientific_look_delta"], {"main": 0, "adaptive": 0})
            after = {r.record_id: r.model_dump_json() for r in store.iter_committed_records()}
            self.assertEqual(len(after), len(before) + 1)
            self.assertTrue(all(after[key] == value for key, value in before.items()))
            self.assertEqual(grounded.list_discovery_looks(store, receipt["search_key_sha256"]), looks)
            inventory = store.diagnostics().committed_inventory_sha256
            repeated = run_cli(*args, data_root=data_root)
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            self.assertFalse(json.loads(repeated.stdout)["writes"])
            self.assertEqual(store.diagnostics().committed_inventory_sha256, inventory)
            with mock.patch.object(ordinary, "get_operation", return_value={"status": "STOPPED"}), mock.patch.object(ordinary, "_append", side_effect=AssertionError("terminal rewrite")):
                self.assertEqual(ordinary.note_look_landed(store, op_sha), {"status": "STOPPED"})

    def test_closed_v4_public_revision_cold_replay_and_unchanged_history(self) -> None:
        from solana_alpha_lab.factory.hfic_session import freeze_draft, list_hfic_sessions
        from solana_alpha_lab.factory.hfic_preflight import epoch_search_budget_usage
        from solana_alpha_lab.factory.research_store import ResearchStore
        from tests.test_hfic_cli import bind_draft, run_cli
        from tests.test_hfic_ordinary_operation_acceptance_v1 import _forge, _operation, _publish_focus, _simple

        root = Path(__file__).resolve().parents[1]
        focus = "DOWNSIDE_CLOSED_V4"
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root, receipt = _publish_focus(workspace, focus, exit_price="0.60")
            journal, market = receipt["search_key_sha256"], receipt["market_evidence_epoch_sha256"]
            spec = _simple("closed-v4-compound")
            spec["search_tier"] = "COMPOUND_SCREEN"
            spec["features"].append({"name": "retention", "op": "ratio", "field_id": LIQ, "numerator": "Y3600", "denominator": "Y1800"})
            spec["all"].append({"feature": "retention", "op": "gte", "value": 0.5})
            scope = {"population": "BASE_X", "decision_timestamp": "Y3600", "target": temporal.temporal_target_label(spec), "estimand": "price_relative_proxy", "explanatory_condition": "compound", "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1"}
            spec_path, scope_path, op_path = (workspace / name for name in ("spec.json", "scope.json", "op.json"))
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            scope_path.write_text(json.dumps(scope), encoding="utf-8")
            op_path.write_text(json.dumps(_operation(spec, focus=focus, journal=journal, market=market, text="one compound", cap={"main": 1, "adaptive": 0, "preview": 0})), encoding="utf-8")
            forge = _forge()

            def execute(correction=None):
                output = io.StringIO()
                errors = io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                    code = forge.cmd_discovery_execute(root, store_root=data_root, census_path=None, observations_path=None, binding_path=None, spec_path=spec_path, journal_scope=journal, candidate_scope_path=scope_path, explicit_data_root=data_root, operation_path=op_path if correction is None else None, operation_sha256=op_sha if correction else None, correct_result_ref=correction[0] if correction else None, correct_result_sha256=correction[1] if correction else None)
                return code, (json.loads(output.getvalue().splitlines()[-1]) if output.getvalue().strip()
                              else {"reason_code": errors.getvalue().strip()})

            with v4_writer():
                code, source = execute()
            self.assertEqual(code, 0, source)
            self.assertEqual(source["calculation_version"], temporal.TEMPORAL_CALCULATION_VERSION_V4)
            op_sha = source["operation_sha256"]
            correction = (source["result_refs"][0], source["result_sha256"])
            fresh = run_cli("preflight", "--discovery-contract", "--owner-focus", focus, "--format", "json", data_root=data_root)
            self.assertEqual(fresh.returncode, 0, fresh.stderr + fresh.stdout)
            receipt = json.loads(fresh.stdout)
            draft = json.loads((root / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1_2.json").read_text(encoding="utf-8"))
            draft["candidates"] = []
            for field in ("selected_candidate_ref", "runner_up_candidate_ref", "strongest_rejected_alternative"):
                draft.pop(field, None)
            draft["owner_focus"] = focus
            draft = bind_draft(draft, receipt)
            draft["grounded_evidence"] = source
            frozen = freeze_draft(draft, preflight_receipt=receipt, store=ResearchStore(data_root), repo_root=root)
            self.assertEqual(frozen["critic_terminal"], "NO_WORTHY_HYPOTHESIS")
            store = ResearchStore(data_root, create_if_missing=False)
            before = {r.record_id: r.model_dump_json() for r in store.iter_committed_records()}
            sessions = list_hfic_sessions(store)
            budget = epoch_search_budget_usage(sessions, evidence_epoch=market)
            inventory = store.diagnostics().committed_inventory_sha256
            with mock.patch.object(temporal, "execute_temporal_discovery", side_effect=AssertionError("legacy replay evaluated")):
                code, replay = execute()
            self.assertEqual(code, 0, replay)
            self.assertEqual(replay["descriptive_readout"]["status"], "LEGACY_READOUT_UNAVAILABLE")
            self.assertEqual(store.diagnostics().committed_inventory_sha256, inventory)
            # Public CLI refusals happen before any intent/reservation/lifecycle write.
            code, refused = execute((correction[0], "0" * 64))
            self.assertEqual((code, refused["reason_code"]), (2, "CALCULATION_REVISION_SOURCE_HASH_MISMATCH"))
            self.assertEqual(store.diagnostics().committed_inventory_sha256, inventory)
            wrong = copy.deepcopy(spec)
            wrong["all"][0]["value"] += 0.01
            spec_path.write_text(json.dumps(wrong), encoding="utf-8")
            code, refused = execute(correction)
            self.assertEqual((code, refused["reason_code"]), (2, "ORDINARY_OPERATION_SPEC_MISMATCH"))
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            self.assertEqual(store.diagnostics().committed_inventory_sha256, inventory)
            real_load = grounded.load_admitted_partition_rows

            def clock_drift(*args, **kwargs):
                loaded = real_load(*args, **kwargs)
                loaded["census"] = copy.deepcopy(loaded["census"])
                loaded["census"][0]["authoritative_anchor"] = "2026-09-03T00:00:01Z"
                return loaded

            with mock.patch.object(grounded, "load_admitted_partition_rows", side_effect=clock_drift):
                code, refused = execute(correction)
            self.assertEqual((code, refused["reason_code"]), (2, "CALCULATION_REVISION_INPUT_MISMATCH"))
            self.assertEqual(store.diagnostics().committed_inventory_sha256, inventory)
            real_calculate = grounded.execute_discovery_from_rows

            def old_numbers_drift(*args, **kwargs):
                computed = real_calculate(*args, **kwargs)
                result = computed["summary"]
                for row in [result, result["pooled"], *result["by_cohort"], *result["by_calendar_block"]]:
                    if row.get("mean_target") is not None:
                        row["mean_target"] += 0.01
                return computed

            with mock.patch.object(grounded, "execute_discovery_from_rows", side_effect=old_numbers_drift):
                code, refused = execute(correction)
            self.assertEqual((code, refused["reason_code"]), (2, "CALCULATION_REVISION_OLD_NUMERIC_CHANGED"))
            self.assertEqual(store.diagnostics().committed_inventory_sha256, inventory)
            request = json.loads(op_path.read_text(encoding="utf-8"))
            request["owner_request_text"] = "new operation forbidden for correction"
            op_path.write_text(json.dumps(request), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = forge.cmd_discovery_execute(root, store_root=data_root, census_path=None, observations_path=None, binding_path=None, spec_path=spec_path, journal_scope=journal, candidate_scope_path=scope_path, explicit_data_root=data_root, operation_path=op_path, correct_result_ref=correction[0], correct_result_sha256=correction[1])
            self.assertEqual((code, json.loads(output.getvalue())["reason_code"]), (2, "CALCULATION_REVISION_EXISTING_OPERATION_REQUIRED"))
            self.assertEqual(store.diagnostics().committed_inventory_sha256, inventory)
            with mock.patch.object(grounded, "_append_discovery_look", side_effect=RuntimeError("before-commit")):
                with self.assertRaises(RuntimeError):
                    execute(correction)
            self.assertEqual(store.diagnostics().committed_inventory_sha256, inventory)
            real_append = grounded._append_discovery_look

            def reply_lost(*args, **kwargs):
                real_append(*args, **kwargs)
                raise RuntimeError("after-commit-reply-lost")

            with mock.patch.object(grounded, "_append_discovery_look", side_effect=reply_lost):
                with self.assertRaises(RuntimeError):
                    execute(correction)
            with mock.patch.object(temporal, "execute_temporal_discovery", side_effect=AssertionError("committed recovery evaluated")):
                code, revised = execute(correction)
            self.assertEqual(code, 0, revised)
            self.assertEqual(revised["revision_of"]["reason"]["code"], "DOWNSIDE_READOUT_ADDED")
            self.assertFalse(revised["queries"][0]["new_look"])
            self.assertEqual(revised["assessment_advisory"], "REVIEW_REQUIRED_FOR_ASSESSMENT_BOUND_TO_SOURCE")
            self.assertEqual(revised["data_binding_sha256"], source["data_binding_sha256"])
            self.assertEqual(revised["queries"][0]["spec_sha256"], source["queries"][0]["spec_sha256"])
            after = {r.record_id: r.model_dump_json() for r in store.iter_committed_records()}
            self.assertEqual(len(after) - len(before), 1)
            self.assertTrue(all(after[key] == value for key, value in before.items()))
            self.assertEqual(list_hfic_sessions(store), sessions)
            self.assertEqual(epoch_search_budget_usage(list_hfic_sessions(store), evidence_epoch=market), budget)
            after_inventory = store.diagnostics().committed_inventory_sha256
            with mock.patch.object(temporal, "execute_temporal_discovery", side_effect=AssertionError("retry evaluated")):
                code, retry = execute(correction)
            self.assertEqual(code, 0, retry)
            self.assertTrue(retry["correction_already_applied"])
            self.assertFalse(retry["writes"])
            self.assertEqual(store.diagnostics().committed_inventory_sha256, after_inventory)
            cold = run_cli("discovery-execute", "--store", str(data_root), "--spec", str(spec_path), "--candidate-scope", str(scope_path), "--journal-scope", journal, "--operation-sha256", op_sha, "--correct-result-ref", correction[0], "--correct-result-sha256", correction[1], "--format", "json", data_root=data_root)
            self.assertEqual(cold.returncode, 0, cold.stderr + cold.stdout)
            self.assertEqual(json.loads(cold.stdout)["result_refs"], revised["result_refs"])
            self.assertEqual(store.diagnostics().committed_inventory_sha256, after_inventory)


if __name__ == "__main__":
    unittest.main()
