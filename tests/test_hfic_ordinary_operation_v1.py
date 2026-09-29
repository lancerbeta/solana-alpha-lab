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
        _obs("mint-a", "X300", PRICE, 1.0),
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
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = root / "store"
            ResearchStore(store)
            spec = _simple_spec()
            request = _operation(spec, completion="SCIENTIFIC_TERMINAL", cap_main=1)
            op_path = root / "op.json"
            spec_path = root / "spec.json"
            scope_path = root / "scope.json"
            op_path.write_text(json.dumps(request), encoding="utf-8")
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            scope_path.write_text("{}", encoding="utf-8")
            refused = _cli(
                store,
                "discovery-execute",
                "--store",
                str(store),
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
            self.assertEqual(refused.get("reason_code"), "OPERATION_SEARCH_TERMINAL_CONFLICT", refused)
            self.assertFalse(refused.get("values_loaded"))
            self.assertEqual(_mains(store), [])

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
            self.assertEqual(first.get("_exit"), 0, first)
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
            self.assertEqual(readback.get("next_action"), "AUTHORIZE_ADDITIONAL_LOOKS", readback)
            self.assertNotEqual(readback.get("owner_final"), "SEARCH_EXHAUSTED_CURRENT_EVIDENCE")
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
                )
            self.assertEqual(getattr(raised.exception, "code", ""), "ORDINARY_OPERATION_SPEC_MISMATCH")
