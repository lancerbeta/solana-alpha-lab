"""Ordinary operation: one explicit owner cap, pause, and continuation.

Numeric signs are fixed by the synthetic prices, not by copying evaluator output.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks  # noqa: E402
from solana_alpha_lab.factory.hfic_ordinary_operation import (  # noqa: E402
    gate_before_values,
    get_operation,
    merge_ordinary_readout,
    owner_allowance,
    project_ordinary_operation,
    record_operation,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402
from tests.test_hfic_temporal_discovery_v1 import (  # noqa: E402
    COHORT,
    LIQ,
    PRICE,
    RELEASE,
    _census,
    _obs,
)

ROOT = Path(__file__).resolve().parents[1]
JOURNAL = "cd" * 32
MARKET = "ab" * 32
FOCUS = "WINDOW_LIQUIDITY_SURVIVAL_15M_TO_4H"


def _simple_spec() -> dict:
    return {
        "schema": "smial.hfic-temporal-query",
        "schema_version": "1.0",
        "query_id": "simple_negative_window",
        "population": "BASE_X",
        "search_tier": "SIMPLE_SCREEN",
        "budget_allocation": "AUTO",
        "decision": {"point_id": "Y3600", "time_policy": "BOUND_SCHEDULE_CUTOFF"},
        "schedule": {"lateness_seconds": 300},
        "features": [
            {
                "name": "retention",
                "op": "ratio",
                "field_id": LIQ,
                "numerator": "Y3600",
                "denominator": "Y1800",
            }
        ],
        "all": [{"feature": "retention", "op": "gte", "value": 0.5}],
        "target": {
            "kind": "PRICE_RELATIVE_PROXY",
            "reference_point": "Y3600",
            "exit_point": "Y7200",
            "field_id": PRICE,
        },
        "entry_model": {"kind": "LAST_AVAILABLE_MARK_WITH_HAIRCUT", "assumed_latency_seconds": 0},
    }


def _compound_spec() -> dict:
    spec = _simple_spec()
    spec["query_id"] = "compound_after_simple"
    spec["search_tier"] = "COMPOUND_SCREEN"
    spec["features"] = [
        *spec["features"],
        {
            "name": "impulse",
            "op": "return_ratio",
            "field_id": PRICE,
            "start": "X300",
            "end": "Y1800",
        },
    ]
    spec["all"] = [
        *spec["all"],
        {"feature": "impulse", "op": "gte", "value": 0.0},
    ]
    return spec


def _rows() -> tuple[list[dict], list[dict]]:
    census = [_census("mint-a")]
    observations = [
        _obs("mint-a", "X300", LIQ, 1000.0),
        _obs("mint-a", "X300", "FIELD-HOLDER-COUNT-001", 50),
        _obs("mint-a", "X300", PRICE, 1.0),
        _obs("mint-a", "Y1800", "FIELD-HOLDER-COUNT-001", 50),
        _obs("mint-a", "Y3600", "FIELD-HOLDER-COUNT-001", 50),
        _obs("mint-a", "Y1800", LIQ, 1000.0),
        _obs("mint-a", "Y1800", PRICE, 1.2),
        _obs("mint-a", "Y3600", LIQ, 900.0),
        _obs("mint-a", "Y3600", PRICE, 2.0),
        _obs("mint-a", "Y7200", PRICE, 1.0),
    ]
    return census, observations


def _write_partition(directory: Path) -> tuple[Path, Path, Path]:
    census, observations = _rows()
    census_path = directory / "census.parquet"
    obs_path = directory / "observations.parquet"
    pq.write_table(pa.Table.from_pylist(census), census_path)
    pq.write_table(pa.Table.from_pylist(observations), obs_path)
    binding = {
        "cohorts": [
            {
                "dataset_id": "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
                "evidence_role": "EXPLORATORY_REUSE",
                "holdout": False,
                "cohort_id": COHORT,
                "release_id": RELEASE,
                "census_sha256": hashlib.sha256(census_path.read_bytes()).hexdigest(),
                "observations_sha256": hashlib.sha256(obs_path.read_bytes()).hexdigest(),
                "schedule_lateness_seconds": 300,
            }
        ]
    }
    path = directory / "binding.json"
    path.write_text(json.dumps(binding), encoding="utf-8")
    return census_path, obs_path, path


def _operation(spec: dict, *, completion: str, cap_main: int, parent: str | None = None) -> dict:
    body = {
        "owner_request_text": f"owner allows {completion} {spec['query_id']} cap {cap_main}",
        "owner_focus": FOCUS,
        "journal_scope": JOURNAL,
        "market_evidence_epoch_sha256": MARKET,
        "spec": spec,
        "question_text": spec["query_id"],
        "owner_cap": {"main": cap_main, "adaptive": 0, "preview": 0},
        "requested_completion": completion,
    }
    if parent:
        body["parent_operation_sha256"] = parent
    return body


def _cli(store: Path, *args: str) -> dict:
    if "discovery-execute" in args or "discovery-preview" in args:
        from tests.test_hfic_cli import _activate_neutral_universe

        _activate_neutral_universe(store)
    completed = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts" / "hypothesis_forge.py"), "--root", str(ROOT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    try:
        payload = json.loads(completed.stdout) if completed.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {"raw": completed.stdout, "err": completed.stderr}
    payload["_exit"] = completed.returncode
    payload["_err"] = completed.stderr
    return payload


def _mains(store: Path) -> list[dict]:
    return [
        item
        for item in list_discovery_looks(ResearchStore(store, create_if_missing=False), JOURNAL)
        if item.get("look_class") == "MAIN" and item.get("new_look") is True
    ]


class OrdinaryOperationTests(unittest.TestCase):
    def test_search_terminal_conflict_refuses_before_values(self) -> None:
        from tests.test_hfic_cli import run_cli
        from tests.test_hfic_temporal_discovery_v1 import _spec as temporal_spec
        from tests.test_hfic_temporal_production_runner_v1 import DOCUMENT_LATENESS, _publish

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            empty = root / "empty"
            ResearchStore(empty)
            spec_path = root / "spec.json"
            scope_path = root / "scope.json"
            op_path = root / "op.json"
            spec = _simple_spec()
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            scope_path.write_text(json.dumps({"estimand": "price_relative_proxy", "explanatory_condition": "retention"}), encoding="utf-8")
            op_path.write_text(
                json.dumps(_operation(spec, completion="SCIENTIFIC_TERMINAL", cap_main=1)),
                encoding="utf-8",
            )
            incomplete = _cli(
                empty,
                "discovery-execute",
                "--store",
                str(empty),
                "--spec",
                str(spec_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                JOURNAL,
                "--operation",
                str(op_path),
                "--format",
                "json",
            )
            self.assertEqual(incomplete.get("reason_code"), "MARKET_EVIDENCE_BASIS_INCOMPLETE", incomplete)
            self.assertFalse(incomplete.get("values_loaded"))
            self.assertEqual(_mains(empty), [])
            workspace = root / "published"
            data_root = workspace / "rdp"
            _publish(data_root, workspace)
            preflight = run_cli(
                "preflight",
                "--discovery-contract",
                "--owner-focus",
                "PUBLISHED_TERMINAL_CONFLICT",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            receipt = json.loads(preflight.stdout)
            simple = temporal_spec(
                "SIMPLE_SCREEN",
                query_id="terminal-conflict-simple",
                features=[{"name": "mark", "op": "point_value", "field_id": PRICE, "point": "Y3600"}],
                all=[{"feature": "mark", "op": "gte", "value": 0.0}],
                cost_profile=None,
                schedule={"lateness_seconds": DOCUMENT_LATENESS},
            )
            spec_path = workspace / "spec.json"
            scope_path = workspace / "scope.json"
            op_path = workspace / "op.json"
            spec_path.write_text(json.dumps(simple), encoding="utf-8")
            scope_path.write_text(json.dumps({"estimand": "price_relative_proxy", "explanatory_condition": "mark"}), encoding="utf-8")
            op_path.write_text(
                json.dumps(
                    {
                        "owner_request_text": "scientific terminal from one simple",
                        "owner_focus": "PUBLISHED_TERMINAL_CONFLICT",
                        "journal_scope": receipt["search_key_sha256"],
                        "market_evidence_epoch_sha256": receipt["market_evidence_epoch_sha256"],
                        "spec": simple,
                        "question_text": "terminal conflict",
                        "owner_cap": {"main": 1, "adaptive": 0, "preview": 0},
                        "requested_completion": "SCIENTIFIC_TERMINAL",
                    }
                ),
                encoding="utf-8",
            )
            refused = run_cli(
                "discovery-execute",
                "--store",
                str(data_root),
                "--spec",
                str(spec_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                str(receipt["search_key_sha256"]),
                "--operation",
                str(op_path),
                "--format",
                "json",
                data_root=data_root,
            )
            payload = json.loads(refused.stdout or "{}")
            self.assertEqual(payload.get("reason_code"), "OPERATION_SEARCH_TERMINAL_CONFLICT", refused.stderr + refused.stdout)
            self.assertFalse(payload.get("values_loaded"))
            self.assertEqual(
                [
                    item
                    for item in list_discovery_looks(
                        ResearchStore(data_root, create_if_missing=False),
                        str(receipt["search_key_sha256"]),
                    )
                    if item.get("new_look") is True
                ],
                [],
            )

    def test_simple_cap_pauses_and_continuation_keeps_the_journal(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = root / "store"
            ResearchStore(store)
            census, observations, binding = _write_partition(root)
            spec = _simple_spec()
            spec_path = root / "spec.json"
            scope_path = root / "scope.json"
            op_path = root / "op.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            scope_path.write_text(
                json.dumps(
                    {
                        "population": "BASE_X",
                        "decision_timestamp": "Y3600",
                        "target": "PRICE_RELATIVE_PROXY:Y3600:Y7200:FIELD-USD-PRICE-001",
                        "estimand": "price_relative_proxy",
                        "explanatory_condition": "retention",
                        "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
                    }
                ),
                encoding="utf-8",
            )
            op_path.write_text(
                json.dumps(_operation(spec, completion="LIMITED_RESULT", cap_main=1)),
                encoding="utf-8",
            )
            first = _cli(
                store,
                "discovery-execute",
                "--store",
                str(store),
                "--census",
                str(census),
                "--observations",
                str(observations),
                "--binding",
                str(binding),
                "--spec",
                str(spec_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                JOURNAL,
                "--operation",
                str(op_path),
                "--format",
                "json",
            )
            self.assertEqual(first.get("reason_code"), "MARKET_EVIDENCE_BASIS_INCOMPLETE", first)
            self.assertFalse(first.get("values_loaded"))
            self.assertFalse(first.get("scientific_negative"))
            self.assertEqual(_mains(store), [])
            return
            self.assertEqual(first.get("ordinary_operation"), "PAUSED_CAP", first)
            self.assertLess(float((first.get("result") or {}).get("mean_target")), 0.0)
            self.assertEqual(len(_mains(store)), 1)
            replay = _cli(
                store,
                "discovery-execute",
                "--store",
                str(store),
                "--census",
                str(census),
                "--observations",
                str(observations),
                "--binding",
                str(binding),
                "--spec",
                str(spec_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                JOURNAL,
                "--operation",
                str(op_path),
                "--format",
                "json",
            )
            self.assertEqual(replay.get("_exit"), 0, replay)
            self.assertTrue(replay.get("replayed_without_evaluator"))
            self.assertEqual(len(_mains(store)), 1)
            readback = _cli(
                store,
                "--data-root",
                str(store),
                "forge-run",
                "--owner-focus",
                FOCUS,
                "--no-write",
                "--format",
                "json",
            )
            seen = project_ordinary_operation(
                ResearchStore(store, create_if_missing=False), owner_focus=FOCUS
            )
            self.assertIsNotNone(seen, readback)
            self.assertEqual(seen["status"], "PAUSED_CAP")
            operation = readback.get("ordinary_operation") or {}
            self.assertEqual(operation.get("status"), "PAUSED_CAP", readback)
            self.assertEqual(operation.get("journal_scope"), JOURNAL)
            self.assertEqual(operation.get("owner_main_remaining"), 0)
            self.assertEqual(operation.get("next_action"), "INPUT_NOT_READY", readback)
            self.assertNotEqual(readback.get("next_action"), "AUTHORIZE_ADDITIONAL_LOOKS", readback)
            self.assertEqual(readback.get("owner_class"), "INPUT_NOT_READY", readback)
            self.assertNotEqual(readback.get("owner_final"), "SEARCH_EXHAUSTED_CURRENT_EVIDENCE")
            frozen = {
                "next_action": "RETURN_EXISTING_RUN",
                "owner_final": "NO_WORTHY_HYPOTHESIS",
                "owner_class": "OWNER_FINAL",
            }
            merged = merge_ordinary_readout(frozen, {"status": "PAUSED_CAP", "next_action": "AUTHORIZE_ADDITIONAL_LOOKS"})
            self.assertEqual(merged["owner_final"], "NO_WORTHY_HYPOTHESIS")
            self.assertEqual(merged["next_action"], "RETURN_EXISTING_RUN")
            self.assertEqual(merged["ordinary_operation"]["status"], "PAUSED_CAP")
            other = _compound_spec()
            other_path = root / "compound.json"
            other_path.write_text(json.dumps(other), encoding="utf-8")
            blocked = _cli(
                store,
                "discovery-execute",
                "--store",
                str(store),
                "--spec",
                str(other_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                JOURNAL,
                "--operation",
                str(op_path),
                "--format",
                "json",
            )
            self.assertEqual(blocked.get("reason_code"), "ORDINARY_OPERATION_SPEC_MISMATCH", blocked)
            self.assertEqual(len(_mains(store)), 1)
            stored = record_operation(
                ResearchStore(store, create_if_missing=False),
                _operation(spec, completion="LIMITED_RESULT", cap_main=1),
            )
            follow = _operation(
                other,
                completion="SCIENTIFIC_TERMINAL",
                cap_main=1,
                parent=stored["operation_sha256"],
            )
            follow_path = root / "follow.json"
            follow_path.write_text(json.dumps(follow), encoding="utf-8")
            second = _cli(
                store,
                "discovery-execute",
                "--store",
                str(store),
                "--census",
                str(census),
                "--observations",
                str(observations),
                "--binding",
                str(binding),
                "--spec",
                str(other_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                JOURNAL,
                "--operation",
                str(follow_path),
                "--format",
                "json",
            )
            self.assertEqual(second.get("_exit"), 0, second)
            self.assertEqual(len(_mains(store)), 2)
            self.assertEqual(second.get("ordinary_operation"), "STOPPED", second)

    def test_gate_replay_does_not_require_a_second_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store_path = root / "store"
            store = ResearchStore(store_path)
            spec = _simple_spec()
            operation = record_operation(
                store, _operation(spec, completion="LIMITED_RESULT", cap_main=1)
            )
            with self.assertRaises(Exception) as raised:
                gate_before_values(
                    store,
                    operation_sha256=operation["operation_sha256"],
                    spec={**spec, "query_id": "renamed-only"},
                    journal_scope=JOURNAL,
                    verified_market=MARKET,
                )
            self.assertEqual(getattr(raised.exception, "code", ""), "ORDINARY_OPERATION_SPEC_MISMATCH")

    def test_zero_owner_cap_refuses_while_protocol_budget_remains(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = root / "store"
            ResearchStore(store)
            spec = _simple_spec()
            operation = record_operation(
                ResearchStore(store),
                _operation(spec, completion="LIMITED_RESULT", cap_main=0),
            )
            with self.assertRaises(Exception) as raised:
                gate_before_values(
                    ResearchStore(store, create_if_missing=False),
                    operation_sha256=operation["operation_sha256"],
                    spec=spec,
                    journal_scope=JOURNAL,
                    verified_market=MARKET,
                )
            self.assertEqual(getattr(raised.exception, "code", ""), "OWNER_CAP_EXHAUSTED")
            self.assertEqual(_mains(store), [])

    def test_preview_cap_zero_refuses_before_values(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = root / "store"
            ResearchStore(store)
            spec = _simple_spec()
            request = _operation(spec, completion="LIMITED_RESULT", cap_main=1)
            request["owner_cap"]["preview"] = 0
            op_path = root / "op.json"
            spec_path = root / "spec.json"
            op_path.write_text(json.dumps(request), encoding="utf-8")
            spec_path.write_text(json.dumps({"decision": {"point_id": "Y3600"}}), encoding="utf-8")
            refused = _cli(
                store,
                "discovery-preview",
                "--spec",
                str(spec_path),
                "--store",
                str(store),
                "--journal-scope",
                JOURNAL,
                "--operation",
                str(op_path),
                "--format",
                "json",
            )
            self.assertEqual(refused.get("reason_code"), "OWNER_CAP_EXHAUSTED", refused)
            self.assertFalse(refused.get("values_loaded"))

    def test_compound_then_real_freeze_is_the_scientific_terminal(self) -> None:
        from tests.test_hfic_cli import bind_draft, seed_minimal_market_basis

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data_root = root / "rdp"
            seed_minimal_market_basis(data_root)
            focus = "V1_ORDINARY_SEARCH_TERMINAL"
            preflight = _cli(
                data_root,
                "--data-root",
                str(data_root),
                "preflight",
                "--owner-focus",
                focus,
                "--format",
                "json",
            )
            self.assertEqual(preflight.get("_exit"), 0, preflight)
            journal = str(preflight["search_key_sha256"])
            market = str(preflight["market_evidence_epoch_sha256"])
            census, observations, binding = _write_partition(root)
            simple = _simple_spec()
            compound = _compound_spec()
            simple_path = root / "simple.json"
            compound_path = root / "compound.json"
            scope_path = root / "scope.json"
            simple_op = root / "simple.op.json"
            compound_op = root / "compound.op.json"
            simple_path.write_text(json.dumps(simple), encoding="utf-8")
            compound_path.write_text(json.dumps(compound), encoding="utf-8")
            scope_path.write_text(
                json.dumps(
                    {
                        "population": "BASE_X",
                        "decision_timestamp": "Y3600",
                        "target": "PRICE_RELATIVE_PROXY:Y3600:Y7200:FIELD-USD-PRICE-001",
                        "estimand": "price_relative_proxy",
                        "explanatory_condition": "retention",
                        "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
                    }
                ),
                encoding="utf-8",
            )
            simple_request = _operation(simple, completion="LIMITED_RESULT", cap_main=1)
            simple_request["owner_focus"] = focus
            simple_request["journal_scope"] = journal
            simple_request["market_evidence_epoch_sha256"] = market
            simple_op.write_text(json.dumps(simple_request), encoding="utf-8")
            first = _cli(
                data_root,
                "discovery-execute",
                "--store",
                str(data_root),
                "--census",
                str(census),
                "--observations",
                str(observations),
                "--binding",
                str(binding),
                "--spec",
                str(simple_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--operation",
                str(simple_op),
                "--format",
                "json",
            )
            self.assertEqual(first.get("_exit"), 0, first)
            self.assertEqual(first.get("ordinary_operation"), "PAUSED_CAP", first)
            parent = record_operation(
                ResearchStore(data_root, create_if_missing=False), simple_request
            )["operation_sha256"]
            follow = _operation(compound, completion="SCIENTIFIC_TERMINAL", cap_main=1, parent=parent)
            follow["owner_focus"] = focus
            follow["journal_scope"] = journal
            follow["market_evidence_epoch_sha256"] = market
            compound_op.write_text(json.dumps(follow), encoding="utf-8")
            second = _cli(
                data_root,
                "discovery-execute",
                "--store",
                str(data_root),
                "--census",
                str(census),
                "--observations",
                str(observations),
                "--binding",
                str(binding),
                "--spec",
                str(compound_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--operation",
                str(compound_op),
                "--format",
                "json",
            )
            self.assertEqual(second.get("_exit"), 0, second)
            self.assertEqual(
                len(list_discovery_looks(ResearchStore(data_root, create_if_missing=False), journal)),
                2,
            )
            fresh = _cli(
                data_root,
                "--data-root",
                str(data_root),
                "preflight",
                "--owner-focus",
                focus,
                "--format",
                "json",
            )
            self.assertEqual(fresh.get("_exit"), 0, fresh)
            source = json.loads(
                (ROOT / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1_2.json").read_text(encoding="utf-8")
            )
            source["grounded_evidence"] = second
            source["owner_focus"] = focus
            receipt = {key: value for key, value in fresh.items() if not str(key).startswith("_")}
            draft = bind_draft(source, receipt)
            draft_path = root / "draft.json"
            receipt_path = root / "preflight.json"
            draft_path.write_text(json.dumps(draft), encoding="utf-8")
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            frozen = _cli(
                data_root,
                "--data-root",
                str(data_root),
                "freeze",
                "--draft",
                str(draft_path),
                "--preflight-receipt",
                str(receipt_path),
                "--format",
                "json",
            )
            self.assertEqual(frozen.get("_exit"), 0, frozen)
            self.assertEqual(frozen.get("critic_terminal"), "NO_WORTHY_HYPOTHESIS", frozen)
            readback = _cli(
                data_root,
                "--data-root",
                str(data_root),
                "forge-run",
                "--owner-focus",
                focus,
                "--no-write",
                "--format",
                "json",
            )
            self.assertEqual(readback.get("_exit"), 0, readback)
            self.assertIn(
                readback.get("owner_final"),
                {"SEARCH_EXHAUSTED_CURRENT_EVIDENCE", "NO_WORTHY_HYPOTHESIS"},
            )
            self.assertEqual(
                len(
                    [
                        item
                        for item in list_discovery_looks(
                            ResearchStore(data_root, create_if_missing=False), journal
                        )
                        if item.get("look_class") == "MAIN" and item.get("new_look") is True
                    ]
                ),
                2,
            )

    def test_cap_zero_still_freezes_a_saved_candidate(self) -> None:
        from tests.test_hfic_cli import bind_draft, seed_minimal_market_basis

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data_root = root / "rdp"
            seed_minimal_market_basis(data_root)
            focus = "V2_CAP_ZERO_CANDIDATE"
            preflight = _cli(
                data_root,
                "--data-root",
                str(data_root),
                "preflight",
                "--owner-focus",
                focus,
                "--format",
                "json",
            )
            self.assertEqual(preflight.get("_exit"), 0, preflight)
            journal = str(preflight["search_key_sha256"])
            market = str(preflight["market_evidence_epoch_sha256"])
            census, observations = _rows()
            for row in observations:
                if row.get("point_id") == "Y7200":
                    row["typed_value"] = 3.0
            census_path = root / "census.parquet"
            obs_path = root / "observations.parquet"
            pq.write_table(pa.Table.from_pylist(census), census_path)
            pq.write_table(pa.Table.from_pylist(observations), obs_path)
            binding = {
                "cohorts": [
                    {
                        "dataset_id": "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
                        "evidence_role": "EXPLORATORY_REUSE",
                        "holdout": False,
                        "cohort_id": COHORT,
                        "release_id": RELEASE,
                        "census_sha256": hashlib.sha256(census_path.read_bytes()).hexdigest(),
                        "observations_sha256": hashlib.sha256(obs_path.read_bytes()).hexdigest(),
                        "schedule_lateness_seconds": 300,
                    }
                ]
            }
            binding_path = root / "binding.json"
            binding_path.write_text(json.dumps(binding), encoding="utf-8")
            spec = _simple_spec()
            spec["query_id"] = "simple_positive_window"
            spec_path = root / "spec.json"
            scope_path = root / "scope.json"
            op_path = root / "op.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            scope_path.write_text(
                json.dumps(
                    {
                        "population": "BASE_X",
                        "decision_timestamp": "Y3600",
                        "target": "PRICE_RELATIVE_PROXY:Y3600:Y7200:FIELD-USD-PRICE-001",
                        "estimand": "price_relative_proxy",
                        "explanatory_condition": "retention",
                        "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
                    }
                ),
                encoding="utf-8",
            )
            request = _operation(spec, completion="LIMITED_RESULT", cap_main=1)
            request["owner_focus"] = focus
            request["journal_scope"] = journal
            request["market_evidence_epoch_sha256"] = market
            op_path.write_text(json.dumps(request), encoding="utf-8")
            evidence = _cli(
                data_root,
                "discovery-execute",
                "--store",
                str(data_root),
                "--census",
                str(census_path),
                "--observations",
                str(obs_path),
                "--binding",
                str(binding_path),
                "--spec",
                str(spec_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--operation",
                str(op_path),
                "--format",
                "json",
            )
            self.assertEqual(evidence.get("_exit"), 0, evidence)
            self.assertGreater(float(evidence["result"]["mean_target"]), 0.0)
            self.assertEqual(evidence.get("ordinary_operation"), "PAUSED_CAP")
            changed = dict(spec)
            changed["query_id"] = "simple_positive_revised"
            changed_path = root / "revised.json"
            changed_path.write_text(json.dumps(changed), encoding="utf-8")
            revised = _cli(
                data_root,
                "discovery-execute",
                "--store",
                str(data_root),
                "--census",
                str(census_path),
                "--observations",
                str(obs_path),
                "--binding",
                str(binding_path),
                "--spec",
                str(changed_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--operation",
                str(op_path),
                "--format",
                "json",
            )
            self.assertEqual(revised.get("reason_code"), "ORDINARY_OPERATION_SPEC_MISMATCH", revised)
            self.assertFalse(revised.get("values_loaded"))
            fresh = _cli(
                data_root,
                "--data-root",
                str(data_root),
                "preflight",
                "--owner-focus",
                focus,
                "--format",
                "json",
            )
            self.assertEqual(fresh.get("_exit"), 0, fresh)
            receipt = {key: value for key, value in fresh.items() if not str(key).startswith("_")}
            source = json.loads(
                (ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text(encoding="utf-8")
            )
            card = dict(source["candidates"][0])
            card.update(
                {
                    "population": "BASE_X",
                    "decision_timestamp": "Y3600",
                    "target": "PRICE_RELATIVE_PROXY:Y3600:Y7200:FIELD-USD-PRICE-001",
                    "estimand": "price_relative_proxy",
                    "explanatory_condition": "retention",
                }
            )
            draft = bind_draft({**source, "candidates": [card]}, receipt)
            draft.pop("runner_up_candidate_ref", None)
            draft.pop("strongest_rejected_alternative", None)
            draft["selected_candidate_ref"] = card["label"]
            draft["grounded_evidence"] = evidence
            draft["owner_focus"] = focus
            draft_path = root / "draft.json"
            receipt_path = root / "preflight.json"
            draft_path.write_text(json.dumps(draft), encoding="utf-8")
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            persisted = _cli(
                data_root,
                "--data-root",
                str(data_root),
                "persist-draft",
                "--draft",
                str(draft_path),
                "--preflight-receipt",
                str(receipt_path),
                "--representation-id",
                "BASE",
                "--format",
                "json",
            )
            self.assertEqual(persisted.get("_exit"), 0, persisted)
            resume = _cli(
                data_root,
                "--data-root",
                str(data_root),
                "preflight",
                "--owner-focus",
                focus,
                "--format",
                "json",
            )
            self.assertEqual(resume.get("_exit"), 0, resume)
            resume_receipt = {key: value for key, value in resume.items() if not str(key).startswith("_")}
            resume_path = root / "resume.json"
            resume_path.write_text(json.dumps(resume_receipt), encoding="utf-8")
            frozen = _cli(
                data_root,
                "--data-root",
                str(data_root),
                "freeze",
                "--draft",
                str(draft_path),
                "--preflight-receipt",
                str(resume_path),
                "--format",
                "json",
            )
            self.assertEqual(frozen.get("_exit"), 0, frozen)
            self.assertTrue(frozen.get("critic_input_packet"), frozen)
            critic = {
                "schema": "smial.hypothesis-critic-result",
                "schema_version": "1.1",
                "session_id": frozen["session_id"],
                "critic_input_packet_sha256": frozen["critic_input_packet_sha256"],
                "selected_candidate_id": frozen["selected_candidate_id"],
                "selected_definition_sha256": frozen["selected_definition_sha256"],
                "critic_prompt_version": "HFIC-V1.1",
                "isolated_context_attestation": "NEW_CONTEXT_REQUIRED",
                "critic_terminal": "KILL_PREPARATORY_LOOP",
                "next": "STOP",
                "authority": {
                    "git_mutation": 0,
                    "experiment_execution": 0,
                    "provider_api_rpc_wss_calls": 0,
                },
                "non_claims": ["NO_ALPHA", "FIXTURE_CRITIC"],
            }
            critic_path = root / "critic.json"
            critic_path.write_text(json.dumps(critic), encoding="utf-8")
            finalized = _cli(
                data_root,
                "--data-root",
                str(data_root),
                "finalize",
                "--session-id",
                str(frozen["session_id"]),
                "--critic-result",
                str(critic_path),
                "--format",
                "json",
            )
            self.assertEqual(finalized.get("_exit"), 0, finalized)
            shown = _cli(
                data_root,
                "--data-root",
                str(data_root),
                "show-session",
                "--session-id",
                str(frozen["session_id"]),
                "--format",
                "json",
            )
            self.assertEqual(shown.get("_exit"), 0, shown)
            self.assertEqual(shown.get("session_id"), frozen["session_id"])
            readback = _cli(
                data_root,
                "--data-root",
                str(data_root),
                "forge-run",
                "--owner-focus",
                focus,
                "--no-write",
                "--format",
                "json",
            )
            self.assertEqual(readback.get("writes", {}).get("research_store"), 0)
            self.assertEqual(
                (readback.get("ordinary_operation") or {}).get("owner_main_remaining"),
                0,
            )
            self.assertEqual(
                len(
                    [
                        item
                        for item in list_discovery_looks(
                            ResearchStore(data_root, create_if_missing=False), journal
                        )
                        if item.get("look_class") == "MAIN" and item.get("new_look") is True
                    ]
                ),
                1,
            )

    def test_later_operation_wins_even_when_its_hash_sorts_first(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = Path(raw) / "store"
            ResearchStore(store)
            first = record_operation(
                ResearchStore(store),
                _operation(_simple_spec(), completion="LIMITED_RESULT", cap_main=1),
            )
            later = None
            for index in range(40):
                spec = _simple_spec()
                spec["query_id"] = f"later_{index}"
                row = record_operation(
                    ResearchStore(store),
                    _operation(spec, completion="LIMITED_RESULT", cap_main=1),
                )
                if row["operation_sha256"] < first["operation_sha256"]:
                    later = row
                    break
            self.assertIsNotNone(later)
            seen = project_ordinary_operation(ResearchStore(store, create_if_missing=False), owner_focus=FOCUS)
            self.assertEqual(seen["operation_sha256"], later["operation_sha256"])
            self.assertEqual(get_operation(ResearchStore(store, create_if_missing=False), first["operation_sha256"])["status"], "OPEN")

    def test_same_reservation_retries_without_a_second_unit(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = Path(raw) / "store"
            ResearchStore(store)
            spec = _simple_spec()
            operation = record_operation(
                ResearchStore(store),
                _operation(spec, completion="LIMITED_RESULT", cap_main=1),
            )
            first = gate_before_values(
                ResearchStore(store, create_if_missing=False),
                operation_sha256=operation["operation_sha256"],
                spec=spec,
                journal_scope=JOURNAL,
                verified_market=MARKET,
            )
            self.assertEqual(first["disposition"], "RESERVED")
            second = gate_before_values(
                ResearchStore(store, create_if_missing=False),
                operation_sha256=operation["operation_sha256"],
                spec=spec,
                journal_scope=JOURNAL,
                verified_market=MARKET,
            )
            self.assertEqual(second["disposition"], "RESUME")
            self.assertFalse(second["writes"])

    def test_one_allowance_covers_two_specs_and_stops_the_third(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = Path(raw) / "store"
            ResearchStore(store)
            request = _operation(_simple_spec(), completion="LIMITED_RESULT", cap_main=2)
            request["owner_request_text"] = "two questions in one scope"
            operation = record_operation(ResearchStore(store), request)
            other = _simple_spec()
            other["query_id"] = "second_question"
            other["all"] = [{"feature": "retention", "op": "gte", "value": 0.8}]
            first = gate_before_values(
                ResearchStore(store, create_if_missing=False),
                operation_sha256=operation["operation_sha256"],
                spec=_simple_spec(),
                journal_scope=JOURNAL,
                verified_market=MARKET,
            )
            second = gate_before_values(
                ResearchStore(store, create_if_missing=False),
                operation_sha256=operation["operation_sha256"],
                spec=other,
                journal_scope=JOURNAL,
                verified_market=MARKET,
            )
            self.assertEqual(first["disposition"], "RESERVED")
            self.assertEqual(second["disposition"], "RESERVED")
            third = _simple_spec()
            third["query_id"] = "third_question"
            third["all"] = [{"feature": "retention", "op": "gte", "value": 0.9}]
            with self.assertRaises(Exception) as raised:
                gate_before_values(
                    ResearchStore(store, create_if_missing=False),
                    operation_sha256=operation["operation_sha256"],
                    spec=third,
                    journal_scope=JOURNAL,
                    verified_market=MARKET,
                )
            self.assertEqual(getattr(raised.exception, "code", ""), "OWNER_CAP_EXHAUSTED")

    def test_foreign_journal_reservations_do_not_spend_this_journal(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = Path(raw) / "store"
            ResearchStore(store)
            other_journal = "ab" * 32
            foreign = _operation(_simple_spec(), completion="LIMITED_RESULT", cap_main=1)
            foreign["journal_scope"] = other_journal
            foreign["owner_request_text"] = "foreign journal one look"
            foreign["owner_focus"] = "FOREIGN-JOURNAL"
            foreign["owner_cap"] = {"main": None, "adaptive": None, "preview": None}
            recorded = record_operation(ResearchStore(store), foreign)
            spec = _simple_spec()
            spec["all"] = [{"feature": "retention", "op": "gte", "value": 0.2}]
            gate_before_values(
                ResearchStore(store, create_if_missing=False),
                operation_sha256=recorded["operation_sha256"],
                spec=spec,
                journal_scope=other_journal,
                verified_market=MARKET,
            )
            home = _operation(_simple_spec(), completion="LIMITED_RESULT", cap_main=1)
            home["owner_cap"] = {"main": None, "adaptive": None, "preview": None}
            home["owner_request_text"] = "home journal untouched"
            recorded_home = record_operation(ResearchStore(store), home)
            self.assertEqual(
                owner_allowance(ResearchStore(store, create_if_missing=False), recorded_home, "main"),
                6,
            )

    def test_published_negative_simple_pauses_on_one_corpus(self) -> None:
        from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_target_label
        from tests.test_hfic_cli import run_cli
        from tests.test_hfic_temporal_discovery_v1 import _spec as temporal_spec
        from tests.test_hfic_temporal_production_runner_v1 import DOCUMENT_LATENESS, _publish

        focus = "PUBLISHED_ORDINARY_PAUSE"
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = workspace / "rdp"
            _publish(data_root, workspace, exit_price="0.60")
            preflight = run_cli(
                "preflight",
                "--discovery-contract",
                "--owner-focus",
                focus,
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            receipt = json.loads(preflight.stdout)
            journal = str(receipt["search_key_sha256"])
            market = str(receipt["market_evidence_epoch_sha256"])
            simple = temporal_spec(
                "SIMPLE_SCREEN",
                query_id="published-negative-simple",
                features=[{"name": "mark", "op": "point_value", "field_id": PRICE, "point": "Y3600"}],
                all=[{"feature": "mark", "op": "gte", "value": 0.0}],
                cost_profile=None,
                schedule={"lateness_seconds": DOCUMENT_LATENESS},
            )
            spec_path = workspace / "spec.json"
            scope_path = workspace / "scope.json"
            op_path = workspace / "op.json"
            spec_path.write_text(json.dumps(simple), encoding="utf-8")
            scope_path.write_text(
                json.dumps(
                    {
                        "population": "BASE_X",
                        "decision_timestamp": "Y3600",
                        "target": temporal_target_label(simple),
                        "estimand": "price_relative_proxy",
                        "explanatory_condition": "mark",
                        "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
                    }
                ),
                encoding="utf-8",
            )
            op_path.write_text(
                json.dumps(
                    {
                        "owner_request_text": "one negative simple on this published corpus",
                        "owner_focus": focus,
                        "journal_scope": journal,
                        "market_evidence_epoch_sha256": market,
                        "spec": simple,
                        "question_text": "published negative simple",
                        "owner_cap": {"main": 1, "adaptive": 0, "preview": 0},
                        "requested_completion": "LIMITED_RESULT",
                    }
                ),
                encoding="utf-8",
            )
            completed = run_cli(
                "discovery-execute",
                "--store",
                str(data_root),
                "--spec",
                str(spec_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--operation",
                str(op_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            evidence = json.loads(completed.stdout)
            self.assertLess(float(evidence["result"]["mean_target"]), 0.0)
            self.assertTrue(evidence["queries"][0]["new_look"])
            self.assertEqual(evidence.get("ordinary_operation"), "PAUSED_CAP")
            readback = run_cli(
                "forge-run",
                "--owner-focus",
                focus,
                "--no-write",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(readback.returncode, 0, readback.stderr + readback.stdout)
            shown = json.loads(readback.stdout)
            self.assertNotEqual(shown.get("owner_class"), "INPUT_NOT_READY")
            self.assertEqual(shown.get("next_action"), "AUTHORIZE_ADDITIONAL_LOOKS")
            self.assertEqual(shown.get("owner_final"), "OPERATION_PAUSED_SEARCH_OPEN")
            operation = shown.get("ordinary_operation") or {}
            self.assertEqual(operation.get("status"), "PAUSED_CAP")
            self.assertEqual(operation.get("journal_scope"), journal)
            self.assertEqual(operation.get("result_refs"), evidence["result_refs"])
            self.assertEqual(
                len(
                    [
                        item
                        for item in list_discovery_looks(
                            ResearchStore(data_root, create_if_missing=False), journal
                        )
                        if item.get("look_class") == "MAIN" and item.get("new_look") is True
                    ]
                ),
                1,
            )
            replay = run_cli(
                "discovery-execute",
                "--store",
                str(data_root),
                "--spec",
                str(spec_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--operation",
                str(op_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(replay.returncode, 0, replay.stderr + replay.stdout)
            replayed = json.loads(replay.stdout)
            self.assertFalse(replayed["queries"][0]["new_look"])
            self.assertEqual(replayed["result_refs"], evidence["result_refs"])
            changed = dict(simple)
            changed["all"] = [{"feature": "mark", "op": "gte", "value": 5.0}]
            changed_path = workspace / "changed.json"
            changed_path.write_text(json.dumps(changed), encoding="utf-8")
            refused = run_cli(
                "discovery-execute",
                "--store",
                str(data_root),
                "--spec",
                str(changed_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--operation",
                str(op_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("ORDINARY_OPERATION_SPEC_MISMATCH", refused.stdout + refused.stderr)
            parent = record_operation(
                ResearchStore(data_root, create_if_missing=False),
                json.loads(op_path.read_text(encoding="utf-8")),
            )["operation_sha256"]
            compound = dict(simple)
            compound["query_id"] = "published-compound"
            compound["search_tier"] = "COMPOUND_SCREEN"
            compound["features"] = [
                simple["features"][0],
                {
                    "name": "retention",
                    "op": "ratio",
                    "field_id": LIQ,
                    "numerator": "Y3600",
                    "denominator": "Y1800",
                },
            ]
            compound["all"] = [
                {"feature": "mark", "op": "gte", "value": 0.0},
                {"feature": "retention", "op": "gte", "value": 0.5},
            ]
            compound_path = workspace / "compound.json"
            compound_op = workspace / "compound.op.json"
            compound_scope = workspace / "compound-scope.json"
            compound_path.write_text(json.dumps(compound), encoding="utf-8")
            compound_scope.write_text(
                json.dumps(
                    {
                        "population": "BASE_X",
                        "decision_timestamp": "Y3600",
                        "target": temporal_target_label(compound),
                        "estimand": "price_relative_proxy",
                        "explanatory_condition": "compound",
                        "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
                    }
                ),
                encoding="utf-8",
            )
            compound_op.write_text(
                json.dumps(
                    {
                        "owner_request_text": "explicit compound on the same open journal",
                        "owner_focus": focus,
                        "journal_scope": journal,
                        "market_evidence_epoch_sha256": market,
                        "spec": compound,
                        "question_text": "published compound",
                        "owner_cap": {"main": 1, "adaptive": 0, "preview": 0},
                        "requested_completion": "LIMITED_RESULT",
                        "parent_operation_sha256": parent,
                    }
                ),
                encoding="utf-8",
            )
            second = run_cli(
                "discovery-execute",
                "--store",
                str(data_root),
                "--spec",
                str(compound_path),
                "--candidate-scope",
                str(compound_scope),
                "--journal-scope",
                journal,
                "--operation",
                str(compound_op),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
            self.assertTrue(json.loads(second.stdout)["queries"][0]["new_look"])
            self.assertEqual(
                len(
                    [
                        item
                        for item in list_discovery_looks(
                            ResearchStore(data_root, create_if_missing=False), journal
                        )
                        if item.get("look_class") == "MAIN" and item.get("new_look") is True
                    ]
                ),
                2,
            )
            from tests.test_hfic_cli import bind_draft

            fresh = run_cli(
                "preflight",
                "--discovery-contract",
                "--owner-focus",
                focus,
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(fresh.returncode, 0, fresh.stderr)
            fresh_receipt = json.loads(fresh.stdout)
            source = json.loads(
                (ROOT / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1_2.json").read_text(encoding="utf-8")
            )
            source["grounded_evidence"] = json.loads(second.stdout)
            source["owner_focus"] = focus
            draft = bind_draft(source, fresh_receipt)
            draft_path = workspace / "draft.json"
            receipt_path = workspace / "receipt.json"
            draft_path.write_text(json.dumps(draft), encoding="utf-8")
            receipt_path.write_text(json.dumps(fresh_receipt), encoding="utf-8")
            frozen = run_cli(
                "freeze",
                "--draft",
                str(draft_path),
                "--preflight-receipt",
                str(receipt_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(frozen.returncode, 0, frozen.stderr + frozen.stdout)
            self.assertEqual(json.loads(frozen.stdout).get("critic_terminal"), "NO_WORTHY_HYPOTHESIS")
            terminal = run_cli(
                "forge-run",
                "--owner-focus",
                focus,
                "--no-write",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(terminal.returncode, 0, terminal.stderr + terminal.stdout)
            finished = json.loads(terminal.stdout)
            self.assertIn(
                finished.get("owner_final"),
                {"SEARCH_EXHAUSTED_CURRENT_EVIDENCE", "NO_WORTHY_HYPOTHESIS"},
            )
            self.assertNotEqual(finished.get("next_action"), "AUTHORIZE_ADDITIONAL_LOOKS")

    def test_published_cap_two_runs_two_questions_without_a_second_grant(self) -> None:
        from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_target_label
        from tests.test_hfic_cli import run_cli
        from tests.test_hfic_temporal_discovery_v1 import _spec as temporal_spec
        from tests.test_hfic_temporal_production_runner_v1 import DOCUMENT_LATENESS, _publish

        focus = "PUBLISHED_TWO_QUESTIONS"
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = workspace / "rdp"
            _publish(data_root, workspace, exit_price="0.60")
            preflight = run_cli(
                "preflight",
                "--discovery-contract",
                "--owner-focus",
                focus,
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            receipt = json.loads(preflight.stdout)
            journal = str(receipt["search_key_sha256"])
            market = str(receipt["market_evidence_epoch_sha256"])
            first_spec = temporal_spec(
                "SIMPLE_SCREEN",
                query_id="published-q1",
                features=[{"name": "mark", "op": "point_value", "field_id": PRICE, "point": "Y3600"}],
                all=[{"feature": "mark", "op": "gte", "value": 0.0}],
                cost_profile=None,
                schedule={"lateness_seconds": DOCUMENT_LATENESS},
            )
            second_spec = dict(first_spec)
            second_spec["query_id"] = "published-q2"
            second_spec["all"] = [{"feature": "mark", "op": "gte", "value": 0.1}]
            third_spec = dict(first_spec)
            third_spec["query_id"] = "published-q3"
            third_spec["all"] = [{"feature": "mark", "op": "gte", "value": 0.2}]
            op_path = workspace / "op.json"
            op_path.write_text(
                json.dumps(
                    {
                        "owner_request_text": "two questions inside one published allowance",
                        "owner_focus": focus,
                        "journal_scope": journal,
                        "market_evidence_epoch_sha256": market,
                        "question_text": "two published questions",
                        "owner_cap": {"main": 2, "adaptive": 0, "preview": 0},
                        "requested_completion": "LIMITED_RESULT",
                    }
                ),
                encoding="utf-8",
            )

            def execute(spec: dict, name: str):
                path = workspace / f"{name}.json"
                path.write_text(json.dumps(spec), encoding="utf-8")
                scope = workspace / f"{name}-scope.json"
                scope.write_text(
                    json.dumps(
                        {
                            "population": "BASE_X",
                            "decision_timestamp": "Y3600",
                            "target": temporal_target_label(spec),
                            "estimand": "price_relative_proxy",
                            "explanatory_condition": name,
                            "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
                        }
                    ),
                    encoding="utf-8",
                )
                return run_cli(
                    "discovery-execute",
                    "--store",
                    str(data_root),
                    "--spec",
                    str(path),
                    "--candidate-scope",
                    str(scope),
                    "--journal-scope",
                    journal,
                    "--operation",
                    str(op_path),
                    "--format",
                    "json",
                    data_root=data_root,
                )

            first = execute(first_spec, "q1")
            second = execute(second_spec, "q2")
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
            self.assertTrue(json.loads(first.stdout)["queries"][0]["new_look"])
            self.assertTrue(json.loads(second.stdout)["queries"][0]["new_look"])
            third = execute(third_spec, "q3")
            self.assertNotEqual(third.returncode, 0)
            self.assertIn("OWNER_CAP_EXHAUSTED", third.stdout + third.stderr)
            self.assertEqual(
                len(
                    [
                        item
                        for item in list_discovery_looks(
                            ResearchStore(data_root, create_if_missing=False), journal
                        )
                        if item.get("look_class") == "MAIN" and item.get("new_look") is True
                    ]
                ),
                2,
            )

    def test_closed_repair_without_operation_artifact_still_reads(self) -> None:
        from tests.test_hfic_legacy_parent_continuation_compat_v1 import (
            LegacyParentContinuationCompatTests,
        )

        legacy = LegacyParentContinuationCompatTests(
            "test_cli_capability_drift_freeze_close_and_readback"
        )
        legacy.test_cli_capability_drift_freeze_close_and_readback()
