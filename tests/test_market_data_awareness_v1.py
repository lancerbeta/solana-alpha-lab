"""MARKET_DATA_AWARENESS_V1 vertical acceptance for OBSERVE / COMPARE / INTERPRET."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.application import FactoryApplication  # noqa: E402
from solana_alpha_lab.factory.market_context import (  # noqa: E402
    compose_market_context,
    context_compatibility_sha256,
    load_market_context_definition,
    project_market_context,
)
from solana_alpha_lab.factory.market_evidence import (  # noqa: E402
    schedule_semantics_from_document,
)
from solana_alpha_lab.factory.observation_schedule import render_utc  # noqa: E402
from solana_alpha_lab.factory.runtime import copy_rehost_allowlist, load_runtime_config  # noqa: E402
from solana_alpha_lab.factory.workbench import serve  # noqa: E402
from solana_alpha_lab.factory_semantic_operability import (  # noqa: E402
    load_semantic_catalog_views,
    load_semantic_projection,
    search_semantic_routes,
)

AS_OF = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
SHA_A = "a" * 64
SHA_B = "b" * 64


def isolated_factory_root(tmp: Path) -> Path:
    config = load_runtime_config(ROOT)
    copy_rehost_allowlist(
        src_root=ROOT,
        dst_root=tmp,
        relatives=list(config["rehost_relative_paths"]),
    )
    return tmp


def _walk(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in root.rglob("*"):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _get(app: FactoryApplication, path: str) -> str:
    server = serve(app, host="127.0.0.1", port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        conn = HTTPConnection(host, port, timeout=8)
        conn.request("GET", path)
        response = conn.getresponse()
        body = response.read().decode("utf-8")
        conn.close()
        return body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _document(*, policy: str = "DETERMINISTIC_HASH_BERNOULLI") -> dict:
    return {
        "population": {
            "entity_type": "TOKEN_MINT",
            "entity_key_field_id": "FIELD-TOKEN-MINT-001",
            "anchor_field_id": "FIELD-FIRST-POOL-CREATED-AT-001",
            "source_predicates": [
                {"field_id": "FIELD-FIRST-POOL-SOURCE-001", "operator": "EQ", "value_text": "pump.fun"}
            ],
            "x_eligibility_predicates": [
                {"field_id": "FIELD-LIQUIDITY-USD-001", "operator": "GTE", "value_decimal": "1000"}
            ],
        },
        "sampling": {
            "policy": policy,
            "inclusion_probability": "1.0",
            "max_candidates_per_utc_day": 2000,
            "max_members_per_utc_day": 20,
            "overflow_state": "NOT_SELECTED_CAPACITY",
            "seed": "EARLY-PUMPFUN-OPTION-VALUE-V1",
        },
        "source_poll": {
            "primitive_id": "PRIM-JUPITER-TOKENS-V2-RECENT-001",
            "query_profile_id": "QUERY-JUPITER-PUMPFUN-RECENT-001",
            "period_seconds": 60,
        },
        "x_point": {"point_id": "X300", "due_offset_seconds": 300},
        "y_points": [
            {"point_id": "Y900", "due_offset_seconds": 900},
            {"point_id": "Y1800", "due_offset_seconds": 1800},
            {"point_id": "Y3600", "due_offset_seconds": 3600},
            {"point_id": "Y7200", "due_offset_seconds": 7200},
            {"point_id": "Y14400", "due_offset_seconds": 14400},
        ],
        "activation": {"starts_at": "2026-09-01T00:00:00Z"},
        "budgets": {"provider_calls_per_utc_day_max": 3200},
    }


def _obs(
    entity: str,
    point: str,
    available: datetime,
    fields: dict[str, object],
    *,
    schedule_sha: str = SHA_A,
    state: str = "OBSERVED",
    omit_pit: bool = False,
) -> dict:
    values = []
    for field_id, value in fields.items():
        observed = state == "OBSERVED" and value is not None
        values.append(
            {
                "field_id": field_id,
                "typed_value_or_null": value if observed else None,
                "state": state if observed or value is None else state,
            }
        )
    return {
        "entity_id": entity,
        "point_id": point,
        "first_reliable_available_at": "" if omit_pit else render_utc(available),
        "event_time": render_utc(available - timedelta(minutes=1)),
        "schedule_sha256": schedule_sha,
        "activation_id": "ACT-MARKET-001",
        "state": state,
        "field_values": values,
    }


def _bundle(definition, observations, *, sha: str = SHA_A, policy: str = "DETERMINISTIC_HASH_BERNOULLI"):
    semantics = schedule_semantics_from_document(_document(policy=policy), definition=definition)
    return {
        "source_status": "PRESENT",
        "source_error": None,
        "observations": observations,
        "members": [],
        "schedules": {sha: semantics},
        "partitions_read": 1,
        "provider_calls": 0,
        "writes": 0,
    }


def _cell(projection: dict, point_id: str, axis_id: str) -> dict:
    for landmark in projection["lifecycle_slices"]:
        if landmark["point_id"] != point_id:
            continue
        for cell in landmark["axes"]:
            if cell["axis_id"] == axis_id:
                return cell
    raise AssertionError(f"missing {point_id}/{axis_id}")


class MarketDataAwarenessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.definition = load_market_context_definition(ROOT)

    def test_no_evidence_does_not_invent_low(self) -> None:
        projection = project_market_context(
            self.definition,
            {
                "source_status": "NOT_PRESENT",
                "source_error": "RESEARCH_STORE_NOT_PRESENT",
                "observations": [],
                "members": [],
                "schedules": {},
            },
            as_of=AS_OF,
        )
        self.assertEqual(projection["source_status"], "NOT_PRESENT")
        cell = _cell(projection, "Y1800", "LIQUIDITY_LEVEL")
        self.assertIsNone(cell["raw_value"])
        self.assertEqual(cell["relative_state"], "UNKNOWN")
        self.assertEqual(cell["relative_reason"], "SOURCE_NOT_PRESENT")
        self.assertNotEqual(cell["relative_state"], "LOW_RELATIVE")
        self.assertFalse(projection["interpretation"]["composite_regime"])
        self.assertTrue(
            {
                cell["relative_state"]
                for landmark in projection["lifecycle_slices"]
                for cell in landmark["axes"]
            }.isdisjoint({"BULL", "BEAR", "RISK_ON", "RISK_OFF", "GOOD_REGIME", "BAD_REGIME"})
        )

    def test_future_pit_observation_excluded(self) -> None:
        future = _obs(
            "mint1",
            "Y1800",
            AS_OF + timedelta(minutes=5),
            {"FIELD-LIQUIDITY-USD-001": 9000},
        )
        current = _obs(
            "mint2",
            "Y1800",
            AS_OF - timedelta(minutes=10),
            {"FIELD-LIQUIDITY-USD-001": 40},
        )
        projection = project_market_context(
            self.definition,
            _bundle(self.definition, [future, current]),
            as_of=AS_OF,
        )
        cell = _cell(projection, "Y1800", "LIQUIDITY_LEVEL")
        self.assertEqual(cell["raw_value"], "40")
        self.assertEqual(cell["n_observed"], 1)

    def test_missing_pit_clock_is_typed_missing_not_numeric(self) -> None:
        missing = _obs(
            "mint_missing",
            "Y1800",
            AS_OF - timedelta(minutes=10),
            {"FIELD-LIQUIDITY-USD-001": 9000},
            omit_pit=True,
        )
        current = _obs(
            "mint2",
            "Y1800",
            AS_OF - timedelta(minutes=10),
            {"FIELD-LIQUIDITY-USD-001": 40},
        )
        projection = project_market_context(
            self.definition,
            _bundle(self.definition, [missing, current]),
            as_of=AS_OF,
        )
        cell = _cell(projection, "Y1800", "LIQUIDITY_LEVEL")
        self.assertEqual(cell["raw_value"], "40")
        self.assertEqual(cell["n_observed"], 1)
        self.assertEqual(cell["n_in_scope"], 1)
        self.assertEqual(cell["coverage_classes"]["typed_missing"], 0)
        self.assertIn("PIT_CLOCK_MISSING", projection["gaps"])

    def test_stale_members_do_not_enter_current_denominator(self) -> None:
        rows = [
            _obs("mint1", "Y1800", AS_OF - timedelta(minutes=10), {"FIELD-LIQUIDITY-USD-001": 40}),
        ]
        bundle = _bundle(self.definition, rows)
        bundle["members"] = [
            {
                "entity_id": "old",
                "point_id": "Y1800",
                "_partition_day": "2026-08-31",
                "first_reliable_available_at": render_utc(AS_OF - timedelta(days=7)),
            },
            {
                "entity_id": "today",
                "point_id": "Y1800",
                "_partition_day": "2026-09-07",
                "first_reliable_available_at": render_utc(AS_OF - timedelta(minutes=5)),
            },
            {
                "entity_id": "wrong_landmark",
                "point_id": "Y900",
                "first_reliable_available_at": render_utc(AS_OF - timedelta(minutes=5)),
            },
        ]
        projection = project_market_context(self.definition, bundle, as_of=AS_OF)
        cell = _cell(projection, "Y1800", "LIQUIDITY_LEVEL")
        self.assertEqual(cell["n_in_scope"], 2)
        self.assertEqual(cell["coverage_classes"]["unknown"], 1)
        self.assertEqual(cell["n_observed"], 1)

    def test_unused_incompatible_schedule_does_not_break_current(self) -> None:
        current_sem = schedule_semantics_from_document(_document(), definition=self.definition)
        unused_sem = schedule_semantics_from_document(
            _document(policy="ALL_UNDER_CAP"), definition=self.definition
        )
        rows = []
        for index in range(5):
            rows.append(
                _obs(
                    f"now{index}",
                    "Y1800",
                    AS_OF - timedelta(minutes=10),
                    {"FIELD-LIQUIDITY-USD-001": 1000},
                )
            )
        for hours in range(2, 14):
            rows.append(
                _obs(
                    f"hist{hours}",
                    "Y1800",
                    AS_OF - timedelta(hours=hours),
                    {"FIELD-LIQUIDITY-USD-001": 100},
                )
            )
        bundle = {
            "source_status": "PRESENT",
            "observations": rows,
            "members": [],
            "schedules": {"0" * 64: unused_sem, SHA_A: current_sem},
        }
        projection = project_market_context(self.definition, bundle, as_of=AS_OF)
        self.assertEqual(
            _cell(projection, "Y1800", "LIQUIDITY_LEVEL")["relative_state"],
            "HIGH_RELATIVE",
        )

    def test_incompatible_history_does_not_depend_on_sha_order(self) -> None:
        current_sem = schedule_semantics_from_document(
            _document(policy="ALL_UNDER_CAP"), definition=self.definition
        )
        hist_sem = schedule_semantics_from_document(_document(), definition=self.definition)
        rows = [
            _obs(
                "now1",
                "Y1800",
                AS_OF - timedelta(minutes=10),
                {"FIELD-LIQUIDITY-USD-001": 1000},
                schedule_sha=SHA_B,
            ),
        ]
        for hours in range(2, 14):
            rows.append(
                _obs(
                    f"hist{hours}",
                    "Y1800",
                    AS_OF - timedelta(hours=hours),
                    {"FIELD-LIQUIDITY-USD-001": 100},
                    schedule_sha=SHA_A,
                )
            )
        bundle = {
            "source_status": "PRESENT",
            "observations": rows,
            "members": [],
            "schedules": {SHA_A: hist_sem, SHA_B: current_sem},
        }
        projection = project_market_context(self.definition, bundle, as_of=AS_OF)
        cell = _cell(projection, "Y1800", "LIQUIDITY_LEVEL")
        self.assertEqual(cell["relative_state"], "UNKNOWN")
        self.assertEqual(cell["relative_reason"], "REFERENCE_SCOPE_MISMATCH")
        self.assertEqual(projection["reference_status"], "REFERENCE_SCOPE_MISMATCH")

    def test_members_incomplete_suppresses_relative_band(self) -> None:
        rows = []
        for index in range(5):
            rows.append(
                _obs(
                    f"now{index}",
                    "Y1800",
                    AS_OF - timedelta(minutes=10),
                    {"FIELD-LIQUIDITY-USD-001": 1000},
                )
            )
        for hours in range(2, 14):
            rows.append(
                _obs(
                    f"hist{hours}",
                    "Y1800",
                    AS_OF - timedelta(hours=hours),
                    {"FIELD-LIQUIDITY-USD-001": 100},
                )
            )
        bundle = _bundle(self.definition, rows)
        bundle["members_incomplete"] = True
        projection = project_market_context(self.definition, bundle, as_of=AS_OF)
        cell = _cell(projection, "Y1800", "LIQUIDITY_LEVEL")
        self.assertEqual(cell["raw_value"], "1000")
        self.assertEqual(cell["relative_state"], "UNKNOWN")
        self.assertEqual(cell["relative_reason"], "MEMBER_EVIDENCE_INCOMPLETE")

    def test_unrelated_partition_is_not_observation_panel(self) -> None:
        from solana_alpha_lab.factory.market_evidence import (
            _is_observation_panel_partition,
            _partition_day,
        )

        self.assertFalse(
            _is_observation_panel_partition({"dataset_id": "other-dataset", "partition_id": "utc-day-2026-09-07"})
        )
        self.assertTrue(
            _is_observation_panel_partition(
                {"dataset_id": "observation-panel-abc", "partition_id": "utc-day-2026-09-07"}
            )
        )
        self.assertFalse(_is_observation_panel_partition({"partition_id": "utc-day-2026-09-07"}))
        self.assertEqual(_partition_day("utc-day-20260907"), "2026-09-07")
        self.assertEqual(_partition_day("utc-day-20260907-members"), "2026-09-07")
        self.assertEqual(_partition_day("utc-day-2026-09-07"), "2026-09-07")
        self.assertEqual(_partition_day("utc-day-2026-09-07-members"), "2026-09-07")

    def test_floor_quantile_is_not_interpolated(self) -> None:
        from decimal import Decimal

        from solana_alpha_lab.factory.market_context import _quantile

        values = [Decimal(str(item)) for item in range(1, 11)]
        self.assertEqual(_quantile(values, Decimal("0.20")), Decimal("2"))
        self.assertEqual(_quantile(values, Decimal("0.80")), Decimal("8"))

    def test_lifecycle_landmarks_not_pooled(self) -> None:
        rows = [
            _obs("mint1", "Y900", AS_OF - timedelta(minutes=10), {"FIELD-LIQUIDITY-USD-001": 10}),
            _obs("mint1", "Y1800", AS_OF - timedelta(minutes=10), {"FIELD-LIQUIDITY-USD-001": 5000}),
        ]
        projection = project_market_context(
            self.definition, _bundle(self.definition, rows), as_of=AS_OF
        )
        self.assertEqual(_cell(projection, "Y900", "LIQUIDITY_LEVEL")["raw_value"], "10")
        self.assertEqual(_cell(projection, "Y1800", "LIQUIDITY_LEVEL")["raw_value"], "5000")

    def test_missing_and_disappeared_stay_in_denominator(self) -> None:
        rows = [
            _obs("mint1", "Y1800", AS_OF - timedelta(minutes=10), {"FIELD-LIQUIDITY-USD-001": 50}),
            _obs(
                "mint2",
                "Y1800",
                AS_OF - timedelta(minutes=10),
                {"FIELD-LIQUIDITY-USD-001": None},
                state="MISSING_TYPED",
            ),
            _obs(
                "mint3",
                "Y1800",
                AS_OF - timedelta(minutes=10),
                {"FIELD-LIQUIDITY-USD-001": None},
                state="DISAPPEARED",
            ),
        ]
        projection = project_market_context(
            self.definition, _bundle(self.definition, rows), as_of=AS_OF
        )
        cell = _cell(projection, "Y1800", "LIQUIDITY_LEVEL")
        self.assertEqual(cell["n_in_scope"], 3)
        self.assertEqual(cell["n_observed"], 1)
        self.assertEqual(cell["coverage_classes"]["typed_missing"], 1)
        self.assertEqual(cell["coverage_classes"]["disappeared"], 1)

    def test_compatible_history_relative_band(self) -> None:
        rows = []
        for index in range(5):
            rows.append(
                _obs(
                    f"now{index}",
                    "Y1800",
                    AS_OF - timedelta(minutes=10),
                    {"FIELD-LIQUIDITY-USD-001": 1000},
                )
            )
        for hours in range(2, 14):
            rows.append(
                _obs(
                    f"hist{hours}",
                    "Y1800",
                    AS_OF - timedelta(hours=hours),
                    {"FIELD-LIQUIDITY-USD-001": 100},
                )
            )
        projection = project_market_context(
            self.definition, _bundle(self.definition, rows), as_of=AS_OF
        )
        cell = _cell(projection, "Y1800", "LIQUIDITY_LEVEL")
        self.assertEqual(cell["raw_value"], "1000")
        self.assertEqual(cell["relative_state"], "HIGH_RELATIVE")
        self.assertIsNone(cell["relative_reason"])

    def test_insufficient_history_keeps_raw_unknown_relative(self) -> None:
        rows = [
            _obs("now1", "Y1800", AS_OF - timedelta(minutes=10), {"FIELD-LIQUIDITY-USD-001": 80}),
            _obs("now2", "Y1800", AS_OF - timedelta(minutes=9), {"FIELD-LIQUIDITY-USD-001": 90}),
            _obs("now3", "Y1800", AS_OF - timedelta(minutes=8), {"FIELD-LIQUIDITY-USD-001": 100}),
            _obs("now4", "Y1800", AS_OF - timedelta(minutes=7), {"FIELD-LIQUIDITY-USD-001": 110}),
            _obs("now5", "Y1800", AS_OF - timedelta(minutes=6), {"FIELD-LIQUIDITY-USD-001": 120}),
        ]
        projection = project_market_context(
            self.definition, _bundle(self.definition, rows), as_of=AS_OF
        )
        cell = _cell(projection, "Y1800", "LIQUIDITY_LEVEL")
        self.assertEqual(cell["raw_value"], "100")
        self.assertEqual(cell["relative_state"], "UNKNOWN")
        self.assertEqual(cell["relative_reason"], "REFERENCE_INSUFFICIENT")

    def test_schedule_sha_rollover_still_comparable(self) -> None:
        semantics = schedule_semantics_from_document(_document(), definition=self.definition)
        left = context_compatibility_sha256(self.definition, semantics)
        other_doc = _document()
        other_doc["activation"] = {"starts_at": "2026-09-08T00:00:00Z"}
        other_doc["budgets"] = {"provider_calls_per_utc_day_max": 99}
        right_semantics = schedule_semantics_from_document(other_doc, definition=self.definition)
        right = context_compatibility_sha256(self.definition, right_semantics)
        self.assertEqual(left, right)
        self.assertNotEqual(SHA_A, SHA_B)
        rows = []
        for index in range(5):
            rows.append(
                _obs(
                    f"now{index}",
                    "Y1800",
                    AS_OF - timedelta(minutes=10),
                    {"FIELD-LIQUIDITY-USD-001": 1000},
                    schedule_sha=SHA_A,
                )
            )
        for hours in range(2, 14):
            rows.append(
                _obs(
                    f"hist{hours}",
                    "Y1800",
                    AS_OF - timedelta(hours=hours),
                    {"FIELD-LIQUIDITY-USD-001": 100},
                    schedule_sha=SHA_B,
                )
            )
        bundle = {
            "source_status": "PRESENT",
            "observations": rows,
            "members": [],
            "schedules": {SHA_A: semantics, SHA_B: right_semantics},
        }
        projection = project_market_context(self.definition, bundle, as_of=AS_OF)
        self.assertEqual(
            _cell(projection, "Y1800", "LIQUIDITY_LEVEL")["relative_state"],
            "HIGH_RELATIVE",
        )

    def test_incompatible_sampling_is_reference_scope_mismatch(self) -> None:
        current_sem = schedule_semantics_from_document(_document(), definition=self.definition)
        hist_sem = schedule_semantics_from_document(
            _document(policy="ALL_UNDER_CAP"), definition=self.definition
        )
        self.assertNotEqual(
            context_compatibility_sha256(self.definition, current_sem),
            context_compatibility_sha256(self.definition, hist_sem),
        )
        rows = [
            _obs("now1", "Y1800", AS_OF - timedelta(minutes=10), {"FIELD-LIQUIDITY-USD-001": 1000}),
        ]
        for hours in range(2, 14):
            rows.append(
                _obs(
                    f"hist{hours}",
                    "Y1800",
                    AS_OF - timedelta(hours=hours),
                    {"FIELD-LIQUIDITY-USD-001": 100},
                    schedule_sha=SHA_B,
                )
            )
        bundle = {
            "source_status": "PRESENT",
            "observations": rows,
            "members": [],
            "schedules": {SHA_A: current_sem, SHA_B: hist_sem},
        }
        projection = project_market_context(self.definition, bundle, as_of=AS_OF)
        cell = _cell(projection, "Y1800", "LIQUIDITY_LEVEL")
        self.assertEqual(cell["relative_state"], "UNKNOWN")
        self.assertEqual(cell["relative_reason"], "REFERENCE_SCOPE_MISMATCH")

    def test_current_window_excluded_from_reference(self) -> None:
        rows = []
        for index in range(5):
            rows.append(
                _obs(
                    f"now{index}",
                    "Y1800",
                    AS_OF - timedelta(minutes=10),
                    {"FIELD-LIQUIDITY-USD-001": 1000},
                )
            )
        projection = project_market_context(
            self.definition, _bundle(self.definition, rows), as_of=AS_OF
        )
        cell = _cell(projection, "Y1800", "LIQUIDITY_LEVEL")
        self.assertEqual(cell["reference_bucket_count"], 0)
        self.assertEqual(cell["relative_reason"], "REFERENCE_INSUFFICIENT")

    def test_thin_coverage_suppresses_band(self) -> None:
        rows = [
            _obs("now1", "Y1800", AS_OF - timedelta(minutes=10), {"FIELD-LIQUIDITY-USD-001": 1000}),
        ]
        for hours in range(2, 14):
            rows.append(
                _obs(
                    f"hist{hours}",
                    "Y1800",
                    AS_OF - timedelta(hours=hours),
                    {"FIELD-LIQUIDITY-USD-001": 100},
                )
            )
        projection = project_market_context(
            self.definition, _bundle(self.definition, rows), as_of=AS_OF
        )
        cell = _cell(projection, "Y1800", "LIQUIDITY_LEVEL")
        self.assertEqual(cell["raw_value"], "1000")
        self.assertEqual(cell["relative_state"], "UNKNOWN")
        self.assertEqual(cell["relative_reason"], "COVERAGE_INSUFFICIENT")

    def test_no_composite_regime_or_market_wide_claim(self) -> None:
        rows = []
        for index in range(5):
            rows.append(
                _obs(
                    f"now{index}",
                    "Y1800",
                    AS_OF - timedelta(minutes=10),
                    {
                        "FIELD-LIQUIDITY-USD-001": 1000,
                        "FIELD-STATS5M-NUM-TRADERS-001": 80,
                        "FIELD-STATS5M-NUM-BUYS-001": 20,
                        "FIELD-STATS5M-NUM-SELLS-001": 2,
                        "FIELD-USD-PRICE-001": 2,
                    },
                )
            )
            rows.append(
                _obs(
                    f"now{index}",
                    "Y900",
                    AS_OF - timedelta(minutes=20),
                    {"FIELD-LIQUIDITY-USD-001": 100, "FIELD-USD-PRICE-001": 1},
                )
            )
        for hours in range(2, 14):
            rows.append(
                _obs(
                    f"hist{hours}",
                    "Y1800",
                    AS_OF - timedelta(hours=hours),
                    {
                        "FIELD-LIQUIDITY-USD-001": 100,
                        "FIELD-STATS5M-NUM-TRADERS-001": 8,
                        "FIELD-STATS5M-NUM-BUYS-001": 2,
                        "FIELD-STATS5M-NUM-SELLS-001": 20,
                        "FIELD-USD-PRICE-001": 1,
                    },
                )
            )
            rows.append(
                _obs(
                    f"hist{hours}",
                    "Y900",
                    AS_OF - timedelta(hours=hours, minutes=15),
                    {"FIELD-LIQUIDITY-USD-001": 90, "FIELD-USD-PRICE-001": 1},
                )
            )
        projection = project_market_context(
            self.definition, _bundle(self.definition, rows), as_of=AS_OF
        )
        self.assertFalse(projection["interpretation"]["composite_regime"])
        self.assertNotEqual(projection["interpretation"]["kind"], "BULL")
        states = {
            cell["relative_state"]
            for landmark in projection["lifecycle_slices"]
            for cell in landmark["axes"]
        }
        self.assertTrue(
            states.isdisjoint({"BULL", "BEAR", "RISK_ON", "RISK_OFF", "GOOD_REGIME", "BAD_REGIME"})
        )
        self.assertFalse(projection["scope"]["market_wide_claim"])
        self.assertEqual(projection["interpretation"]["tested_context_binding"], "NOT_AVAILABLE")
        self.assertFalse(projection["authority"]["pause_bot"])
        states = {
            cell["axis_id"]: cell["relative_state"]
            for cell in next(
                item for item in projection["lifecycle_slices"] if item["point_id"] == "Y1800"
            )["axes"]
        }
        self.assertGreaterEqual(len(set(states.values())), 1)

    def test_buy_sell_no_activity_not_numeric(self) -> None:
        row = _obs(
            "mint1",
            "Y1800",
            AS_OF - timedelta(minutes=10),
            {"FIELD-STATS5M-NUM-BUYS-001": 0, "FIELD-STATS5M-NUM-SELLS-001": 0},
        )
        projection = project_market_context(
            self.definition, _bundle(self.definition, [row]), as_of=AS_OF
        )
        cell = _cell(projection, "Y1800", "BUY_SELL_ACTIVITY_BALANCE")
        self.assertIsNone(cell["raw_value"])
        self.assertIn("NO_ACTIVITY", cell["detail_states"])

    def test_determinism(self) -> None:
        rows = [
            _obs("now1", "Y1800", AS_OF - timedelta(minutes=10), {"FIELD-LIQUIDITY-USD-001": 40}),
        ]
        bundle = _bundle(self.definition, rows)
        first = project_market_context(self.definition, bundle, as_of=AS_OF)
        second = project_market_context(self.definition, bundle, as_of=AS_OF)
        self.assertEqual(first["context_snapshot_sha256"], second["context_snapshot_sha256"])

    def test_market_section_renders_observed_relative_state(self) -> None:
        from solana_alpha_lab.factory.workbench import _market_section

        rows = []
        for index in range(5):
            rows.append(
                _obs(
                    f"now{index}",
                    "Y1800",
                    AS_OF - timedelta(minutes=10),
                    {"FIELD-LIQUIDITY-USD-001": 1000},
                )
            )
        for hours in range(2, 14):
            rows.append(
                _obs(
                    f"hist{hours}",
                    "Y1800",
                    AS_OF - timedelta(hours=hours),
                    {"FIELD-LIQUIDITY-USD-001": 100},
                )
            )
        projection = project_market_context(
            self.definition, _bundle(self.definition, rows), as_of=AS_OF
        )
        html = _market_section({"market": projection})
        self.assertIn("HIGH_RELATIVE", html)
        self.assertIn("Контекст сейчас", html)
        self.assertIn("Покрытие и пропуски", html)
        self.assertIn("Scope, источник и as-of", html)
        self.assertIn("Что это означает как context", html)
        self.assertIn("Что это не означает", html)
        self.assertIn("Ликвидность", html)

    def test_get_market_zero_writes_and_visible_nav(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_factory_root(Path(tmp))
            before = _walk(root)
            app = FactoryApplication(root=root)
            home = _get(app, "/")
            market = _get(app, "/market")
            after = _walk(root)
            self.assertEqual(before, after)
            self.assertIn('href="/market"', home)
            self.assertIn("Рынок", market)
            self.assertIn("Матрица возраста", market)
            self.assertIn("HIGH_RELATIVE значит только", market)
            self.assertIn("NO_MARKET_WIDE_CLAIM", market)
            self.assertIn("GIT_CAPABILITY", market)
            self.assertIn("/system", market)
            self.assertNotIn(">BULL<", market)
            self.assertIn("NO_BULL_BEAR_OR_COMPOSITE_REGIME", market)
            home_model = app.read_model(surface="HOME")
            self.assertNotIn("market", home_model)
            market_model = app.read_model(surface="MARKET")
            self.assertEqual(market_model["market"]["purity"]["provider_calls"], 0)
            self.assertEqual(market_model["market"]["authority"]["pause_bot"], False)

    def test_post_market_has_no_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_factory_root(Path(tmp))
            app = FactoryApplication(root=root)
            server = serve(app, host="127.0.0.1", port=0)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address[:2]
                conn = HTTPConnection(host, port, timeout=8)
                conn.request(
                    "POST",
                    "/market",
                    body="command=PAUSE_NEW_ENTRIES",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response = conn.getresponse()
                body = response.read().decode("utf-8")
                conn.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            self.assertIn("MARKET_HAS_NO_COMMANDS", body)

    def test_semantic_context_and_feature_queries(self) -> None:
        projection = load_semantic_projection(ROOT)
        assets, bindings, _queries = load_semantic_catalog_views(ROOT)
        kwargs = {"assets": assets, "bindings": bindings, "limit": 5}
        context_hits = search_semantic_routes(
            projection, "какой market context сейчас наблюдается", **kwargs
        )
        feature_hits = search_semantic_routes(
            projection, "what feature/data exists at decision time", **kwargs
        )
        collector = search_semantic_routes(
            projection, "работает ли collector", **kwargs
        )
        pause = search_semantic_routes(
            projection, "поставь бота на паузу", **kwargs
        )
        strategy = search_semantic_routes(
            projection, "эта стратегия работает в таком режиме?", **kwargs
        )
        provider = search_semantic_routes(
            projection, "Does a provider route already exist?", **kwargs
        )
        mixed_provider = search_semantic_routes(
            projection, "подключи новый market provider", **kwargs
        )
        assert isinstance(context_hits, list)
        assert isinstance(feature_hits, list)
        assert isinstance(collector, list)
        assert isinstance(pause, list)
        assert isinstance(strategy, list)
        assert isinstance(provider, list)
        assert isinstance(mixed_provider, list)
        self.assertEqual(context_hits[0]["semantic_route_id"], "SEM-MARKET-DATA-FEATURES")
        self.assertEqual(feature_hits[0]["semantic_route_id"], "SEM-MARKET-DATA-FEATURES")
        self.assertTrue(collector)
        self.assertNotEqual(collector[0]["semantic_route_id"], "SEM-MARKET-DATA-FEATURES")
        if pause:
            self.assertNotEqual(pause[0]["semantic_route_id"], "SEM-MARKET-DATA-FEATURES")
            self.assertFalse(pause[0]["authority_granted"])
        if strategy:
            self.assertNotEqual(strategy[0]["semantic_route_id"], "SEM-MARKET-DATA-FEATURES")
        self.assertTrue(provider)
        self.assertEqual(provider[0]["semantic_route_id"], "SEM-PROVIDER-ROUTES")
        self.assertFalse(provider[0]["authority_granted"])
        if mixed_provider:
            self.assertFalse(mixed_provider[0]["authority_granted"])
        route = next(
            item
            for item in projection["routes"]
            if item["semantic_route_id"] == "SEM-MARKET-DATA-FEATURES"
        )
        self.assertIn("ACTIVE-FACTORY-MARKET-FEATURE-SURFACE", route["root_binding_ids"])
        self.assertIn("ACTIVE-MARKET-DATA-AWARENESS", route["root_binding_ids"])

    def test_compose_without_rdp_is_source_not_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_factory_root(Path(tmp))
            projection = compose_market_context(root, as_of=AS_OF)
            self.assertEqual(projection["source_status"], "NOT_PRESENT")
            self.assertEqual(projection["data_capability"]["status"], "GIT_CAPABILITY")
            self.assertTrue(projection["data_capability"]["not_live_market_values"])


if __name__ == "__main__":
    unittest.main()
