from __future__ import annotations

import hashlib
import json
import statistics
import sys
import tempfile
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.prior_work import (  # noqa: E402
    PriorWorkError,
    legacy_outcome_semantics,
    merge_plane_results,
    query_data_plane_prior_work,
    query_hypotheses,
)
from solana_alpha_lab.factory.research_store import (  # noqa: E402
    ResearchEvent,
    ResearchStore,
    ResearchStoreError,
)


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
HYPOTHESIS_ID = "HYP-VERSION-PROJECTION-V1"


def canonical_payload(payload: object) -> tuple[str, str]:
    text = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def event(
    record_id: str,
    record_kind: str,
    payload: dict[str, object],
    *,
    transaction_id: str = "RESEARCH-TXN-PROJECTION-001",
    entity_id: str | None = None,
    hypothesis_version_id: str | None = HYPOTHESIS_ID,
    run_id: str | None = None,
    effective_at: datetime = NOW,
    available_at: datetime = NOW,
    supersedes_record_id: str | None = None,
) -> ResearchEvent:
    payload_json, payload_sha256 = canonical_payload(payload)
    return ResearchEvent(
        record_id=record_id,
        record_kind=record_kind,
        entity_id=entity_id or record_id,
        hypothesis_version_id=hypothesis_version_id,
        run_id=run_id,
        transaction_id=transaction_id,
        effective_at=effective_at,
        first_reliable_available_at=available_at,
        supersedes_record_id=supersedes_record_id,
        payload_json=payload_json,
        payload_sha256=payload_sha256,
        schema_version="1.0",
        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        producer_git_sha="a" * 40,
        created_at=effective_at,
    )


def completed_payload(
    run_id: str,
    run_key_sha256: str,
    *,
    outcome: str = "POSITIVE",
    terminal: str = "RETAINED",
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "run_key_sha256": run_key_sha256,
        "trial_id": f"TRIAL-{run_id}",
        "hypothesis_version_id": HYPOTHESIS_ID,
        "hypothesis_definition_sha256": "1" * 64,
        "experiment_spec_sha256": "2" * 64,
        "runner_capability_id": "CAP-RUNNER-001",
        "runner_git_sha": "b" * 40,
        "capability_closure_sha256": "3" * 64,
        "uv_lock_sha256": "4" * 64,
        "dataset_manifest_ids": ["DATASET-MANIFEST-001"],
        "dataset_fingerprints": ["5" * 64],
        "query_recipe_ids": ["QUERY-RECIPE-001"],
        "query_recipe_sha256s": ["6" * 64],
        "config_sha256": "7" * 64,
        "as_of": "2026-08-25T11:00:00Z",
        "availability_cutoff": "2026-08-25T11:00:00Z",
        "holdout_consumption_ids": [],
        "random_seed_or_null": 17,
        "started_at": "2026-08-25T11:30:00Z",
        "completed_at": "2026-08-25T12:00:00Z",
        "first_reliable_available_at": "2026-08-25T12:00:00Z",
        "provider_calls_planned": 0,
        "provider_calls_actual": 0,
        "cash_spend_usd_cents": 0,
        "execution_status": "COMPLETE",
        "trial_outcome": outcome,
        "scientific_terminal": terminal,
        "result_digest_sha256": "8" * 64,
        "artifact_manifest_sha256": "9" * 64,
        "limitations": [],
        "non_claims": [],
        "origin_kind": "DATA_ANALYSIS",
        "capability_ids": ["CAP-RUNNER-001"],
        "what_changed": "fixed-seed acceptance fixture",
    }


def seeded_store(root: Path) -> ResearchStore:
    run_id = "RUN-PROJECTION-001"
    records = [
        event(
            "HYPOTHESIS-PROJECTION-001",
            "HYPOTHESIS_VERSION",
            {
                "hypothesis_version_id": HYPOTHESIS_ID,
                "family_id": "HYP-FAMILY-PROJECTION",
                "version_ordinal": 1,
                "origin_id": "HYP-ORIGIN-PROJECTION",
                "origin_kind": "DATA_ANALYSIS",
                "research_cycle_id": "RESEARCH-CYCLE-PROJECTION",
                "definition_sha256": "1" * 64,
                "statement": "Liquidity imbalance predicts reversal",
                "mechanism": "liquidity imbalance mean reversion",
                "falsifier": "no reversal after executable costs",
                "expected_regime_terms": ["thin liquidity", "volatile"],
                "what_changed": "initial version",
            },
            entity_id=HYPOTHESIS_ID,
        ),
        event(
            "ORIGIN-PROJECTION-001",
            "HYPOTHESIS_ORIGIN",
            {
                "origin_id": "HYP-ORIGIN-PROJECTION",
                "origin_kind": "DATA_ANALYSIS",
            },
        ),
        event(
            "RUN-COMPLETED-PROJECTION-001",
            "RUN_COMPLETED",
            completed_payload(run_id, "a" * 64),
            entity_id=run_id,
            run_id=run_id,
        ),
        event(
            "METRIC-PROJECTION-001",
            "EXPERIMENT_METRIC",
            {
                "metric_id": "METRIC-PROJECTION-001",
                "metric_name": "net_return",
                "scalar_value": None,
                "unit": "ratio",
            },
            run_id=run_id,
        ),
        event(
            "EVIDENCE-PROJECTION-001",
            "EVIDENCE_BINDING",
            {
                "evidence_binding_id": "EVIDENCE-PROJECTION-001",
                "binding_kind": "DATASET",
                "content_sha256": "b" * 64,
                "logical_uri": "smial-data://datasets/projection",
            },
            run_id=run_id,
        ),
        event(
            "PROMOTION-PROJECTION-001",
            "PROMOTION_CANDIDATE",
            {
                "promotion_candidate_id": "PROMOTION-PROJECTION-001",
                "nomination_state": "NOMINATED",
                "owner_state": "PENDING",
            },
            run_id=run_id,
        ),
        event(
            "CAPABILITY-GAP-PROJECTION-001",
            "CAPABILITY_GAP",
            {
                "capability_gap_id": "CAPABILITY-GAP-PROJECTION-001",
                "capability_id": "CAP-MISSING-001",
                "reason_code": "CAPABILITY_NOT_REGISTERED",
            },
        ),
        event(
            "DECISION-FUTURE-REJECT-001",
            "DECISION_EVENT",
            {
                "decision_event_id": "DECISION-FUTURE-REJECT-001",
                "decision_kind": "REJECT",
            },
            effective_at=NOW + timedelta(hours=1),
            available_at=NOW + timedelta(days=1),
        ),
    ]
    store = ResearchStore(root)
    store.append(records, transaction_id="RESEARCH-TXN-PROJECTION-001")
    return store


class ResearchProjectionTests(unittest.TestCase):
    def test_rebuild_exposes_all_views_and_preserves_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = seeded_store(root)
            receipt = store.rebuild_projection()

            self.assertEqual(receipt.status, "READY")
            self.assertRegex(receipt.projection_digest_sha256, r"^[0-9a-f]{64}$")
            self.assertEqual(
                receipt.logical_uri,
                "smial-data://projections/research_memory.duckdb",
            )
            projection = root / "projections" / "research_memory.duckdb"
            self.assertNotIn(str(root).encode("utf-8"), projection.read_bytes())
            connection = duckdb.connect(str(projection), read_only=True)
            try:
                views = {
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT table_name
                        FROM information_schema.views
                        WHERE table_schema = 'main'
                        """
                    ).fetchall()
                }
                self.assertTrue(
                    {
                        "hypotheses",
                        "hypothesis_events",
                        "experiment_runs",
                        "experiment_metrics",
                        "evidence_bindings",
                        "promotion_candidates",
                        "prior_work",
                        "capability_gaps",
                    }
                    <= views
                )
                metric = connection.execute(
                    "SELECT scalar_value FROM experiment_metrics"
                ).fetchone()
                self.assertIsNone(metric[0])
                promotion = connection.execute(
                    """
                    SELECT nomination_state, owner_state
                    FROM promotion_candidates
                    """
                ).fetchone()
                self.assertEqual(promotion, ("NOMINATED", "PENDING"))
                self.assertNotIn("PROMOTED", promotion)
                invalid_or_negative = connection.execute(
                    """
                    SELECT trial_outcome, scientific_terminal
                    FROM experiment_runs
                    """
                ).fetchone()
                self.assertEqual(invalid_or_negative, ("POSITIVE", "RETAINED"))
            finally:
                connection.close()

    def test_future_event_does_not_change_past_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = seeded_store(root)
            store.rebuild_projection()
            projection = root / "projections" / "research_memory.duckdb"

            past = query_hypotheses(projection, "2026-08-25T12:30:00Z")
            future = query_hypotheses(projection, "2026-08-27T00:00:00Z")

            self.assertEqual(past[0]["derived_state"], "RETAINED")
            self.assertEqual(future[0]["derived_state"], "REJECTED")

    def test_data_plane_search_supports_all_required_predicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = seeded_store(root)
            store.rebuild_projection()
            projection = root / "projections" / "research_memory.duckdb"
            predicates = (
                ("hypothesis_version_ids", HYPOTHESIS_ID),
                ("hypothesis_definition_sha256s", "1" * 64),
                ("mechanism_terms", "imbalance"),
                ("falsifier_terms", "costs"),
                ("regime_terms", "volatile"),
                ("origin_kinds", "DATA_ANALYSIS"),
                ("dataset_manifest_ids", "DATASET-MANIFEST-001"),
                ("dataset_fingerprints", "5" * 64),
                ("capability_ids", "CAP-RUNNER-001"),
                ("query_recipe_ids", "QUERY-RECIPE-001"),
                ("trial_outcomes", "POSITIVE"),
                ("scientific_terminals", "RETAINED"),
                ("decision_kinds", "REJECT"),
                ("what_changed_terms", "initial"),
            )
            for name, value in predicates:
                with self.subTest(predicate=name):
                    result = query_data_plane_prior_work(
                        projection,
                        {
                            "query_id": "PRIOR-WORK-QUERY-PREDICATE-001",
                            "as_of": "2026-08-27T00:00:00Z",
                            "max_results": 1,
                            "predicates": {name: [value]},
                        },
                    )
                    self.assertEqual(result["result_count"], 1)
                    self.assertEqual(
                        result["results"][0]["hypothesis_version_id"],
                        HYPOTHESIS_ID,
                    )
            for invalid_limit in (0, 51):
                with self.subTest(max_results=invalid_limit):
                    with self.assertRaises(ValueError):
                        query_data_plane_prior_work(
                            projection,
                            {
                                "query_id": "PRIOR-WORK-QUERY-BOUNDS-001",
                                "as_of": "2026-08-27T00:00:00Z",
                                "max_results": invalid_limit,
                                "predicates": {
                                    "hypothesis_version_ids": [HYPOTHESIS_ID]
                                },
                            },
                        )

    def test_search_uses_stable_id_tie_break_and_result_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ResearchStore(root)
            hypotheses = []
            for suffix in ("B", "A"):
                version_id = f"HYP-VERSION-TIE-{suffix}-V1"
                hypotheses.append(
                    event(
                        f"HYPOTHESIS-TIE-{suffix}-001",
                        "HYPOTHESIS_VERSION",
                        {
                            "hypothesis_version_id": version_id,
                            "family_id": f"HYP-FAMILY-TIE-{suffix}",
                            "definition_sha256": (
                                hashlib.sha256(suffix.encode("ascii")).hexdigest()
                            ),
                            "statement": "liquidity tie",
                            "mechanism": "liquidity reversal",
                            "falsifier": "none",
                            "expected_regime_terms": [],
                        },
                        entity_id=version_id,
                        hypothesis_version_id=version_id,
                    )
                )
            store.append(
                hypotheses,
                transaction_id="RESEARCH-TXN-PROJECTION-001",
            )
            store.rebuild_projection()
            result = query_data_plane_prior_work(
                root / "projections" / "research_memory.duckdb",
                {
                    "query_id": "PRIOR-WORK-QUERY-TIE-001",
                    "as_of": "2026-08-25T13:00:00Z",
                    "max_results": 1,
                    "predicates": {"mechanism_terms": ["liquidity"]},
                },
            )
            self.assertEqual(result["result_count"], 1)
            self.assertEqual(
                result["results"][0]["hypothesis_version_id"],
                "HYP-VERSION-TIE-A-V1",
            )

    def test_invalid_run_is_not_negative_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ResearchStore(root)
            run_id = "RUN-INVALID-001"
            store.append(
                [
                    event(
                        "HYPOTHESIS-PROJECTION-001",
                        "HYPOTHESIS_VERSION",
                        {
                            "hypothesis_version_id": HYPOTHESIS_ID,
                            "family_id": "HYP-FAMILY-PROJECTION",
                            "definition_sha256": "1" * 64,
                            "statement": "invalid evidence stays invalid",
                            "mechanism": "liquidity",
                            "falsifier": "cost",
                            "expected_regime_terms": [],
                        },
                        entity_id=HYPOTHESIS_ID,
                    ),
                    event(
                        "RUN-INVALID-PROJECTION-001",
                        "RUN_INVALID",
                        completed_payload(
                            run_id,
                            "c" * 64,
                            outcome="INVALID",
                            terminal="INVALID",
                        ),
                        entity_id=run_id,
                        run_id=run_id,
                    ),
                ],
                transaction_id="RESEARCH-TXN-PROJECTION-001",
            )
            store.rebuild_projection()
            connection = duckdb.connect(
                str(root / "projections" / "research_memory.duckdb"),
                read_only=True,
            )
            try:
                row = connection.execute(
                    """
                    SELECT trial_outcome, scientific_terminal
                    FROM experiment_runs
                    """
                ).fetchone()
            finally:
                connection.close()
            self.assertEqual(row, ("INVALID", "INVALID"))
            self.assertNotIn("NEGATIVE", row)

    def test_rebuild_is_deterministic_and_failed_rebuild_keeps_projection(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = seeded_store(root)
            first = store.rebuild_projection()
            projection = root / "projections" / "research_memory.duckdb"
            original_bytes = projection.read_bytes()
            second = store.rebuild_projection()
            self.assertEqual(
                first.projection_digest_sha256,
                second.projection_digest_sha256,
            )

            manifest = next(
                (root / "research" / "manifests" / "partitions").glob("*.json")
            )
            manifest.write_text("{}", encoding="utf-8")
            with self.assertRaises(ResearchStoreError):
                store.rebuild_projection()
            self.assertEqual(projection.read_bytes(), original_bytes)

    def test_duplicate_stable_id_with_mismatched_hash_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ResearchStore(root)
            first = event(
                "HYPOTHESIS-DUPLICATE-001",
                "HYPOTHESIS_VERSION",
                {
                    "hypothesis_version_id": HYPOTHESIS_ID,
                    "definition_sha256": "1" * 64,
                },
                entity_id=HYPOTHESIS_ID,
            )
            second = event(
                "HYPOTHESIS-DUPLICATE-002",
                "HYPOTHESIS_VERSION",
                {
                    "hypothesis_version_id": HYPOTHESIS_ID,
                    "definition_sha256": "2" * 64,
                },
                entity_id=HYPOTHESIS_ID,
            )
            store.append(
                [first, second],
                transaction_id="RESEARCH-TXN-PROJECTION-001",
            )
            with self.assertRaisesRegex(
                ResearchStoreError,
                "DUPLICATE_STABLE_ID_CONFLICT",
            ):
                store.rebuild_projection()

    def test_generated_ten_thousand_event_performance_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ResearchStore(root)
            records = [
                event(
                    "HYPOTHESIS-PERFORMANCE-001",
                    "HYPOTHESIS_VERSION",
                    {
                        "hypothesis_version_id": HYPOTHESIS_ID,
                        "family_id": "HYP-FAMILY-PERFORMANCE",
                        "definition_sha256": "1" * 64,
                        "statement": "fixed seed performance hypothesis",
                        "mechanism": "liquidity reversal",
                        "falsifier": "no executable reversal",
                        "expected_regime_terms": ["volatile"],
                        "origin_kind": "DATA_ANALYSIS",
                    },
                    entity_id=HYPOTHESIS_ID,
                    transaction_id="RESEARCH-TXN-PERFORMANCE-001",
                )
            ]
            for index in range(9_999):
                run_id = f"RUN-PERFORMANCE-{index:05d}"
                run_key = hashlib.sha256(
                    f"fixed-seed-17:{index}".encode("ascii")
                ).hexdigest()
                records.append(
                    event(
                        f"RUN-COMPLETED-PERFORMANCE-{index:05d}",
                        "RUN_COMPLETED",
                        completed_payload(run_id, run_key),
                        transaction_id="RESEARCH-TXN-PERFORMANCE-001",
                        entity_id=run_id,
                        run_id=run_id,
                    )
                )
            store.append(
                records,
                transaction_id="RESEARCH-TXN-PERFORMANCE-001",
            )

            started = time.perf_counter()
            store.rebuild_projection()
            rebuild_seconds = time.perf_counter() - started
            self.assertLessEqual(rebuild_seconds, 60.0)

            projection = root / "projections" / "research_memory.duckdb"
            query_spec = {
                "query_id": "PRIOR-WORK-QUERY-PERFORMANCE-001",
                "as_of": "2026-08-25T13:00:00Z",
                "max_results": 20,
                "predicates": {
                    "hypothesis_version_ids": [HYPOTHESIS_ID],
                },
            }
            timings: list[float] = []
            for _ in range(7):
                started = time.perf_counter()
                result = query_data_plane_prior_work(projection, query_spec)
                timings.append(time.perf_counter() - started)
                self.assertEqual(result["result_count"], 1)
            p95 = statistics.quantiles(timings, n=20)[18]
            self.assertLessEqual(p95, 2.0)

            final_key = hashlib.sha256(b"fixed-seed-17:9998").hexdigest()
            started = time.perf_counter()
            passport = store.find_completed_run(final_key)
            lookup_seconds = time.perf_counter() - started
            self.assertIsNotNone(passport)
            self.assertLessEqual(lookup_seconds, 0.250)

    def test_cross_plane_hash_conflict_fails_closed(self) -> None:
        legacy = {
            "results": [
                {
                    "hypothesis_version_id": "HYP-VERSION-LIQUIDITY-REVERSAL-V1",
                    "definition_sha256": "a" * 64,
                    "score": 5,
                }
            ]
        }
        data_plane = {
            "results": [
                {
                    "hypothesis_version_id": "HYP-VERSION-LIQUIDITY-REVERSAL-V1",
                    "definition_sha256": "b" * 64,
                    "score": 5,
                }
            ]
        }
        with self.assertRaisesRegex(PriorWorkError, "CROSS_PLANE_ID_CONFLICT"):
            merge_plane_results(legacy, data_plane, max_results=20)

    def test_legacy_pass_and_fail_outcomes_remain_unresolved(self) -> None:
        for label in ("PASS", "FAIL"):
            with self.subTest(label=label):
                semantics = legacy_outcome_semantics(label)
                self.assertEqual(semantics["legacy_outcome"], label)
                self.assertIsNone(semantics["trial_outcome"])
                self.assertEqual(semantics["diagnostic"], "LEGACY_OUTCOME_UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
