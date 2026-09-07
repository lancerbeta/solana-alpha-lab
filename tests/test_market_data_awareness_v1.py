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
    read_market_evidence,
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


def _get(app: FactoryApplication, path: str, *, timeout: int = 8) -> str:
    server = serve(app, host="127.0.0.1", port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        conn = HTTPConnection(host, port, timeout=timeout)
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
            {"point_id": "Y900", "due_offset_seconds": 900, "allowed_lateness_seconds": 0},
            {"point_id": "Y1800", "due_offset_seconds": 1800, "allowed_lateness_seconds": 0},
            {"point_id": "Y3600", "due_offset_seconds": 3600, "allowed_lateness_seconds": 0},
            {"point_id": "Y7200", "due_offset_seconds": 7200, "allowed_lateness_seconds": 0},
            {"point_id": "Y14400", "due_offset_seconds": 14400, "allowed_lateness_seconds": 0},
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


def _history(
    fields: dict[str, object],
    *,
    point: str = "Y1800",
    hours_from: int = 2,
    hours_to: int = 14,
    n_per_bucket: int = 5,
    schedule_sha: str = SHA_A,
    extra_minutes: int = 0,
) -> list[dict]:
    rows: list[dict] = []
    for hours in range(hours_from, hours_to):
        for index in range(n_per_bucket):
            rows.append(
                _obs(
                    f"hist{point}_{hours}_{index}",
                    point,
                    AS_OF - timedelta(hours=hours, minutes=extra_minutes),
                    fields,
                    schedule_sha=schedule_sha,
                )
            )
    return rows


def _members_from(observations: list[dict]) -> list[dict]:
    members: list[dict] = []
    for row in observations:
        if not row.get("first_reliable_available_at"):
            continue
        members.append(
            {
                "entity_id": row["entity_id"],
                "point_id": row["point_id"],
                "event_time": row.get("event_time"),
                "first_reliable_available_at": row["first_reliable_available_at"],
                "schedule_sha256": row["schedule_sha256"],
                "membership_state": row.get("state") or "OBSERVED",
            }
        )
    return members


def _publish_panel(
    data_root: Path,
    dataset_manifest_id: str,
    *,
    dataset_id: str = "observation-panel-test",
) -> None:
    manifests = data_root / "datasets" / "manifests"
    manifests.mkdir(parents=True, exist_ok=True)
    (manifests / f"{dataset_manifest_id}.json").write_text(
        json.dumps(
            {"dataset_id": dataset_id, "dataset_manifest_id": dataset_manifest_id}
        ),
        encoding="utf-8",
    )
    (manifests / f"{dataset_manifest_id}.published").write_text(
        json.dumps({"dataset_manifest_id": dataset_manifest_id}),
        encoding="utf-8",
    )


def _bundle(definition, observations, *, sha: str = SHA_A, policy: str = "DETERMINISTIC_HASH_BERNOULLI"):
    semantics = schedule_semantics_from_document(_document(policy=policy))
    return {
        "source_status": "PRESENT",
        "source_error": None,
        "observations": observations,
        "members": _members_from(observations),
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
        self.assertEqual(cell["n_in_scope"], 2)
        self.assertEqual(cell["coverage_classes"]["typed_missing"], 1)
        self.assertIn("PIT_CLOCK_MISSING", projection["gaps"])
        self.assertEqual(cell["relative_state"], "UNKNOWN")

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
                "event_time": render_utc(AS_OF - timedelta(minutes=5)),
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
        current_sem = schedule_semantics_from_document(_document())
        unused_sem = schedule_semantics_from_document(_document(policy="ALL_UNDER_CAP"))
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
        rows.extend(_history({"FIELD-LIQUIDITY-USD-001": 100}))
        bundle = {
            "source_status": "PRESENT",
            "observations": rows,
            "members": _members_from(rows),
            "schedules": {"0" * 64: unused_sem, SHA_A: current_sem},
        }
        projection = project_market_context(self.definition, bundle, as_of=AS_OF)
        self.assertEqual(
            _cell(projection, "Y1800", "LIQUIDITY_LEVEL")["relative_state"],
            "HIGH_RELATIVE",
        )

    def test_incompatible_history_does_not_depend_on_sha_order(self) -> None:
        current_sem = schedule_semantics_from_document(_document(policy="ALL_UNDER_CAP"))
        hist_sem = schedule_semantics_from_document(_document())
        rows = [
            _obs(
                "now1",
                "Y1800",
                AS_OF - timedelta(minutes=10),
                {"FIELD-LIQUIDITY-USD-001": 1000},
                schedule_sha=SHA_B,
            ),
        ]
        rows.extend(_history({"FIELD-LIQUIDITY-USD-001": 100}, schedule_sha=SHA_A))
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
        rows.extend(_history({"FIELD-LIQUIDITY-USD-001": 100}))
        bundle = _bundle(self.definition, rows)
        bundle["members_incomplete"] = True
        projection = project_market_context(self.definition, bundle, as_of=AS_OF)
        cell = _cell(projection, "Y1800", "LIQUIDITY_LEVEL")
        self.assertEqual(cell["raw_value"], "1000")
        self.assertEqual(cell["relative_state"], "UNKNOWN")
        self.assertEqual(cell["relative_reason"], "MEMBER_EVIDENCE_INCOMPLETE")
        self.assertEqual(cell["n_in_scope"], 0)

    def test_empty_members_partition_marks_incomplete(self) -> None:
        import pyarrow as pa
        import pyarrow.parquet as pq

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            compact = AS_OF.strftime("%Y%m%d")
            partitions = data_root / "datasets" / "manifests" / "partitions"
            partitions.mkdir(parents=True)
            _publish_panel(data_root, "ds-manifest-empty-members")
            obs_rel = f"datasets/observation-panel/utc-day-{compact}.parquet"
            mem_rel = f"datasets/observation-panel/utc-day-{compact}-members.parquet"
            (data_root / obs_rel).parent.mkdir(parents=True)
            pq.write_table(pa.table({"entity_id": ["mint1"]}), data_root / obs_rel)
            pq.write_table(
                pa.table({"entity_id": pa.array([], type=pa.string())}),
                data_root / mem_rel,
            )
            available = render_utc(AS_OF - timedelta(minutes=10))
            for rel, pid in (
                (obs_rel, f"utc-day-{compact}"),
                (mem_rel, f"utc-day-{compact}-members"),
            ):
                (partitions / f"{pid}.json").write_text(
                    json.dumps(
                        {
                            "dataset_id": "observation-panel-test",
                            "dataset_manifest_id": "ds-manifest-empty-members",
                            "partition_id": pid,
                            "logical_location": rel,
                            "first_reliable_available_at": available,
                        }
                    ),
                    encoding="utf-8",
                )
            bundle = read_market_evidence(
                ROOT,
                as_of=AS_OF,
                definition=self.definition,
                data_root=data_root,
            )
            self.assertTrue(bundle["members_incomplete"])

    def test_historical_obs_day_without_members_marks_incomplete(self) -> None:
        import pyarrow as pa
        import pyarrow.parquet as pq

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            partitions = data_root / "datasets" / "manifests" / "partitions"
            partitions.mkdir(parents=True)
            _publish_panel(data_root, "ds-manifest-hist-members")
            (data_root / "datasets/observation-panel").mkdir(parents=True)
            available = render_utc(AS_OF - timedelta(minutes=10))

            def _write(pid: str) -> None:
                rel = f"datasets/observation-panel/{pid}.parquet"
                pq.write_table(pa.table({"entity_id": ["mint1"]}), data_root / rel)
                (partitions / f"{pid}.json").write_text(
                    json.dumps(
                        {
                            "dataset_id": "observation-panel-test",
                            "dataset_manifest_id": "ds-manifest-hist-members",
                            "partition_id": pid,
                            "logical_location": rel,
                            "first_reliable_available_at": available,
                        }
                    ),
                    encoding="utf-8",
                )

            current = AS_OF.strftime("%Y%m%d")
            hist = (AS_OF - timedelta(days=2)).strftime("%Y%m%d")
            _write(f"utc-day-{current}")
            _write(f"utc-day-{current}-members")
            _write(f"utc-day-{hist}")
            bundle = read_market_evidence(
                ROOT,
                as_of=AS_OF,
                definition=self.definition,
                data_root=data_root,
            )
            self.assertTrue(bundle["members_incomplete"])

    def test_unreadable_observation_parquet_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            partitions = data_root / "datasets" / "manifests" / "partitions"
            partitions.mkdir(parents=True)
            _publish_panel(data_root, "ds-manifest-bad-parquet")
            rel = "datasets/observation-panel/utc-day-20260907.parquet"
            path = data_root / rel
            path.parent.mkdir(parents=True)
            path.write_bytes(b"not-a-parquet")
            compact = AS_OF.strftime("%Y%m%d")
            (partitions / f"utc-day-{compact}.json").write_text(
                json.dumps(
                    {
                        "dataset_id": "observation-panel-test",
                        "dataset_manifest_id": "ds-manifest-bad-parquet",
                        "partition_id": f"utc-day-{compact}",
                        "logical_location": rel,
                        "first_reliable_available_at": render_utc(
                            AS_OF - timedelta(minutes=10)
                        ),
                    }
                ),
                encoding="utf-8",
            )
            bundle = read_market_evidence(
                ROOT,
                as_of=AS_OF,
                definition=self.definition,
                data_root=data_root,
            )
            self.assertEqual(bundle["source_status"], "UNAVAILABLE")
            self.assertEqual(bundle["source_error"], "OBSERVATION_PARTITION_UNREADABLE")
            self.assertEqual(bundle["observations"], [])

    def test_production_partition_json_and_offset_clock_are_admitted(self) -> None:
        import pyarrow as pa
        import pyarrow.parquet as pq

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            manifests = data_root / "datasets" / "manifests"
            partitions = manifests / "partitions"
            partitions.mkdir(parents=True)
            (data_root / "datasets/observation-panel").mkdir(parents=True)
            compact = AS_OF.strftime("%Y%m%d")
            dataset_manifest_id = "ds-manifest-market-001"
            dataset_id = "observation-panel-testdigest"
            available = (AS_OF - timedelta(minutes=10)).isoformat()
            self.assertTrue(available.endswith("+00:00"))
            obs_rel = f"datasets/observation-panel/utc-day-{compact}.parquet"
            mem_rel = f"datasets/observation-panel/utc-day-{compact}-members.parquet"
            pq.write_table(
                pa.table(
                    {
                        "entity_id": ["mint1"],
                        "point_id": ["Y1800"],
                        "first_reliable_available_at": [
                            render_utc(AS_OF - timedelta(minutes=10))
                        ],
                        "schedule_sha256": [SHA_A],
                    }
                ),
                data_root / obs_rel,
            )
            pq.write_table(
                pa.table(
                    {
                        "entity_id": ["mint1"],
                        "membership_state": ["SAMPLED_MEMBER"],
                        "first_reliable_available_at": [
                            render_utc(AS_OF - timedelta(minutes=10))
                        ],
                        "schedule_sha256": [SHA_A],
                    }
                ),
                data_root / mem_rel,
            )
            (manifests / f"{dataset_manifest_id}.json").write_text(
                json.dumps(
                    {
                        "dataset_id": dataset_id,
                        "dataset_manifest_id": dataset_manifest_id,
                    }
                ),
                encoding="utf-8",
            )
            (manifests / f"{dataset_manifest_id}.published").write_text(
                json.dumps({"dataset_manifest_id": dataset_manifest_id}),
                encoding="utf-8",
            )
            for rel, pid in (
                (obs_rel, f"utc-day-{compact}"),
                (mem_rel, f"utc-day-{compact}-members"),
            ):
                (partitions / f"{pid}.json").write_text(
                    json.dumps(
                        {
                            "partition_manifest_id": pid,
                            "dataset_manifest_id": dataset_manifest_id,
                            "partition_id": pid,
                            "logical_location": rel,
                            "first_reliable_available_at": available,
                        }
                    ),
                    encoding="utf-8",
                )
            bundle = read_market_evidence(
                ROOT,
                as_of=AS_OF,
                definition=self.definition,
                data_root=data_root,
            )
            self.assertEqual(bundle["source_status"], "PRESENT")
            self.assertEqual(len(bundle["observations"]), 1)
            self.assertEqual(len(bundle["members"]), 1)
            self.assertFalse(bundle["members_incomplete"])

    def test_schedule_semantics_do_not_stamp_current_tokens(self) -> None:
        semantics = schedule_semantics_from_document(_document())
        self.assertNotIn("tokens_projection_id", semantics)
        self.assertNotIn("field_ids", semantics)
        self.assertNotIn("definition_id", semantics)
        self.assertEqual(
            semantics["source_poll"]["primitive_id"],
            "PRIM-JUPITER-TOKENS-V2-RECENT-001",
        )

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
        self.assertEqual(_quantile(values, Decimal("0.20"), method="ROUND_FLOOR"), Decimal("2"))
        self.assertEqual(_quantile(values, Decimal("0.80"), method="ROUND_FLOOR"), Decimal("8"))

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
        rows.extend(_history({"FIELD-LIQUIDITY-USD-001": 100}))
        projection = project_market_context(
            self.definition, _bundle(self.definition, rows), as_of=AS_OF
        )
        cell = _cell(projection, "Y1800", "LIQUIDITY_LEVEL")
        self.assertEqual(cell["raw_value"], "1000")
        self.assertEqual(cell["relative_state"], "HIGH_RELATIVE")
        self.assertIsNone(cell["relative_reason"])

    def test_thin_historical_buckets_are_not_reference(self) -> None:
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
        rows.extend(_history({"FIELD-LIQUIDITY-USD-001": 100}, n_per_bucket=1))
        projection = project_market_context(
            self.definition, _bundle(self.definition, rows), as_of=AS_OF
        )
        cell = _cell(projection, "Y1800", "LIQUIDITY_LEVEL")
        self.assertEqual(cell["raw_value"], "1000")
        self.assertEqual(cell["relative_state"], "UNKNOWN")
        self.assertEqual(cell["relative_reason"], "REFERENCE_INSUFFICIENT")
        self.assertEqual(cell["reference_bucket_count"], 0)

    def test_history_without_member_evidence_is_not_reference(self) -> None:
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
        current = list(rows)
        rows.extend(_history({"FIELD-LIQUIDITY-USD-001": 100}))
        bundle = _bundle(self.definition, rows)
        bundle["members"] = _members_from(current)
        projection = project_market_context(self.definition, bundle, as_of=AS_OF)
        cell = _cell(projection, "Y1800", "LIQUIDITY_LEVEL")
        self.assertEqual(cell["raw_value"], "1000")
        self.assertEqual(cell["relative_state"], "UNKNOWN")
        self.assertEqual(cell["relative_reason"], "REFERENCE_INSUFFICIENT")

    def test_day_cohort_members_without_anchor_are_not_landmark_eligible(self) -> None:
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
        rows.extend(_history({"FIELD-LIQUIDITY-USD-001": 100}))
        bundle = _bundle(self.definition, rows)
        bundle["members"] = [
            {
                "entity_id": row["entity_id"],
                "first_reliable_available_at": row["first_reliable_available_at"],
                "schedule_sha256": row["schedule_sha256"],
                "membership_state": "SAMPLED_MEMBER",
            }
            for row in rows
        ]
        projection = project_market_context(self.definition, bundle, as_of=AS_OF)
        cell = _cell(projection, "Y1800", "LIQUIDITY_LEVEL")
        self.assertEqual(cell["relative_state"], "UNKNOWN")
        self.assertEqual(cell["relative_reason"], "REFERENCE_INSUFFICIENT")

    def test_discovery_clock_members_enter_y1800_by_anchor(self) -> None:
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
        rows.extend(_history({"FIELD-LIQUIDITY-USD-001": 100}))
        bundle = _bundle(self.definition, rows)
        members = []
        for row in rows:
            available = datetime.fromisoformat(
                str(row["first_reliable_available_at"]).replace("Z", "+00:00")
            )
            members.append(
                {
                    "entity_id": row["entity_id"],
                    "authoritative_anchor": render_utc(available - timedelta(seconds=1800)),
                    "first_reliable_available_at": render_utc(
                        available - timedelta(minutes=90)
                    ),
                    "schedule_sha256": row["schedule_sha256"],
                    "membership_state": "SAMPLED_MEMBER",
                }
            )
        bundle["members"] = members
        projection = project_market_context(self.definition, bundle, as_of=AS_OF)
        cell = _cell(projection, "Y1800", "LIQUIDITY_LEVEL")
        self.assertEqual(cell["relative_state"], "HIGH_RELATIVE")
        self.assertGreaterEqual(cell["n_in_scope"], 5)

    def test_delayed_availability_does_not_enter_current_window(self) -> None:
        rows = []
        for index in range(5):
            row = _obs(
                f"late{index}",
                "Y1800",
                AS_OF - timedelta(minutes=10),
                {"FIELD-LIQUIDITY-USD-001": 1000},
            )
            row["event_time"] = render_utc(AS_OF - timedelta(days=2))
            rows.append(row)
        rows.extend(_history({"FIELD-LIQUIDITY-USD-001": 100}))
        cell = _cell(
            project_market_context(self.definition, _bundle(self.definition, rows), as_of=AS_OF),
            "Y1800",
            "LIQUIDITY_LEVEL",
        )
        self.assertNotEqual(cell["relative_state"], "HIGH_RELATIVE")
        self.assertIsNone(cell["raw_value"])

    def test_breadth_relative_requires_metric_support_n(self) -> None:
        rows = [
            _obs("now1", "Y1800", AS_OF - timedelta(minutes=10), {"FIELD-LIQUIDITY-USD-001": 1000}),
            _obs("now2", "Y1800", AS_OF - timedelta(minutes=9), {"FIELD-LIQUIDITY-USD-001": 1000}),
            _obs("now3", "Y1800", AS_OF - timedelta(minutes=8), {"FIELD-LIQUIDITY-USD-001": 1000}),
            _obs("now4", "Y1800", AS_OF - timedelta(minutes=7), {"FIELD-LIQUIDITY-USD-001": 1000}),
            _obs("now5", "Y1800", AS_OF - timedelta(minutes=6), {"FIELD-LIQUIDITY-USD-001": 1000}),
            _obs("now1", "Y900", AS_OF - timedelta(minutes=40), {"FIELD-LIQUIDITY-USD-001": 100}),
        ]
        rows.extend(_history({"FIELD-LIQUIDITY-USD-001": 100}, point="Y1800"))
        rows.extend(_history({"FIELD-LIQUIDITY-USD-001": 50}, point="Y900"))
        cell = _cell(
            project_market_context(self.definition, _bundle(self.definition, rows), as_of=AS_OF),
            "Y1800",
            "LIQUIDITY_BREADTH",
        )
        self.assertEqual(cell["n_metric_supported"], 1)
        self.assertEqual(cell["relative_state"], "UNKNOWN")
        self.assertEqual(cell["relative_reason"], "COVERAGE_INSUFFICIENT")
        self.assertEqual(cell["raw_value"], "1")

    def test_relative_band_uses_metric_fraction_not_field_observed(self) -> None:
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
            rows.append(
                _obs(
                    f"now{index}",
                    "Y900",
                    AS_OF - timedelta(minutes=40),
                    {"FIELD-LIQUIDITY-USD-001": 100},
                )
            )
        for index in range(21):
            rows.append(
                _obs(
                    f"thin{index}",
                    "Y1800",
                    AS_OF - timedelta(minutes=8),
                    {"FIELD-LIQUIDITY-USD-001": 1000},
                )
            )
        rows.extend(_history({"FIELD-LIQUIDITY-USD-001": 100}, point="Y1800"))
        rows.extend(_history({"FIELD-LIQUIDITY-USD-001": 50}, point="Y900"))
        cell = _cell(
            project_market_context(self.definition, _bundle(self.definition, rows), as_of=AS_OF),
            "Y1800",
            "LIQUIDITY_BREADTH",
        )
        self.assertEqual(cell["n_metric_supported"], 5)
        self.assertGreater(cell["n_observed"], cell["n_metric_supported"])
        self.assertEqual(cell["relative_state"], "UNKNOWN")
        self.assertEqual(cell["relative_reason"], "COVERAGE_INSUFFICIENT")

    def test_mixed_current_schedules_do_not_blend_raw(self) -> None:
        rows = []
        for index in range(5):
            rows.append(
                _obs(
                    f"a{index}",
                    "Y1800",
                    AS_OF - timedelta(minutes=10),
                    {"FIELD-LIQUIDITY-USD-001": 100},
                    schedule_sha=SHA_A,
                )
            )
            rows.append(
                _obs(
                    f"b{index}",
                    "Y1800",
                    AS_OF - timedelta(minutes=10),
                    {"FIELD-LIQUIDITY-USD-001": 10000},
                    schedule_sha=SHA_B,
                )
            )
        bundle = _bundle(self.definition, rows, sha=SHA_A)
        bundle["schedules"][SHA_B] = schedule_semantics_from_document(
            _document(policy="UNIFORM_RANDOM")
        )
        projection = project_market_context(self.definition, bundle, as_of=AS_OF)
        cell = _cell(projection, "Y1800", "LIQUIDITY_LEVEL")
        self.assertIsNone(cell["raw_value"])
        self.assertEqual(cell["relative_state"], "UNKNOWN")
        self.assertIn("CURRENT_SCOPE_MIXED", projection["gaps"])
        self.assertEqual(cell["n_in_scope"], 0)
        self.assertIsNone(projection["scope"]["sampling_policy"])
        from solana_alpha_lab.factory.workbench import _market_section

        html = _market_section({"market": projection})
        self.assertIn("CURRENT_SCOPE_MIXED", html)
        self.assertIn("Смешаны разные текущие scope", html)
        self.assertNotIn("Сырые значения видны", html)

    def test_allowed_lateness_changes_compatibility(self) -> None:
        left = schedule_semantics_from_document(_document())
        other = _document()
        other["y_points"][1]["allowed_lateness_seconds"] = 3600
        right = schedule_semantics_from_document(other)
        self.assertNotEqual(
            context_compatibility_sha256(self.definition, left),
            context_compatibility_sha256(self.definition, right),
        )

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

    def test_get_market_from_partitions_shows_high_relative(self) -> None:
        import pyarrow as pa
        import pyarrow.parquet as pq

        clock = datetime.now(UTC).replace(microsecond=0)
        rows = []
        for index in range(5):
            rows.append(
                _obs(
                    f"now{index}",
                    "Y1800",
                    clock - timedelta(minutes=10),
                    {"FIELD-LIQUIDITY-USD-001": 1000},
                )
            )
        for hours in range(2, 14):
            for index in range(5):
                rows.append(
                    _obs(
                        f"hist{hours}_{index}",
                        "Y1800",
                        clock - timedelta(hours=hours),
                        {"FIELD-LIQUIDITY-USD-001": 100},
                    )
                )
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            factory = isolated_factory_root(data_root / "factory")
            manifests = data_root / "datasets" / "manifests"
            partitions = manifests / "partitions"
            partitions.mkdir(parents=True)
            (data_root / "datasets/observation-panel").mkdir(parents=True)
            compact = clock.strftime("%Y%m%d")
            dataset_manifest_id = "ds-manifest-get-market-001"
            obs_rel = f"datasets/observation-panel/utc-day-{compact}.parquet"
            mem_rel = f"datasets/observation-panel/utc-day-{compact}-members.parquet"
            obs_table = {
                "entity_id": [row["entity_id"] for row in rows],
                "point_id": [row["point_id"] for row in rows],
                "event_time": [row["event_time"] for row in rows],
                "first_reliable_available_at": [
                    row["first_reliable_available_at"] for row in rows
                ],
                "schedule_sha256": [row["schedule_sha256"] for row in rows],
                "field_values": [json.dumps(row["field_values"]) for row in rows],
                "state": [row["state"] for row in rows],
            }
            members = []
            for row in rows:
                available = datetime.fromisoformat(
                    str(row["first_reliable_available_at"]).replace("Z", "+00:00")
                )
                members.append(
                    {
                        "entity_id": row["entity_id"],
                        "authoritative_anchor": render_utc(
                            available - timedelta(seconds=1800)
                        ),
                        "first_reliable_available_at": render_utc(
                            available - timedelta(minutes=90)
                        ),
                        "schedule_sha256": row["schedule_sha256"],
                        "membership_state": "SAMPLED_MEMBER",
                    }
                )
            pq.write_table(pa.table(obs_table), data_root / obs_rel)
            pq.write_table(
                pa.table(
                    {
                        "entity_id": [item["entity_id"] for item in members],
                        "authoritative_anchor": [
                            item["authoritative_anchor"] for item in members
                        ],
                        "first_reliable_available_at": [
                            item["first_reliable_available_at"] for item in members
                        ],
                        "schedule_sha256": [item["schedule_sha256"] for item in members],
                        "membership_state": [
                            item["membership_state"] for item in members
                        ],
                    }
                ),
                data_root / mem_rel,
            )
            (manifests / f"{dataset_manifest_id}.json").write_text(
                json.dumps(
                    {
                        "dataset_id": "observation-panel-getmarket",
                        "dataset_manifest_id": dataset_manifest_id,
                    }
                ),
                encoding="utf-8",
            )
            (manifests / f"{dataset_manifest_id}.published").write_text(
                json.dumps({"dataset_manifest_id": dataset_manifest_id}),
                encoding="utf-8",
            )
            available = (clock - timedelta(minutes=10)).isoformat()
            for rel, pid in (
                (obs_rel, f"utc-day-{compact}"),
                (mem_rel, f"utc-day-{compact}-members"),
            ):
                (partitions / f"{pid}.json").write_text(
                    json.dumps(
                        {
                            "partition_manifest_id": pid,
                            "dataset_manifest_id": dataset_manifest_id,
                            "partition_id": pid,
                            "logical_location": rel,
                            "first_reliable_available_at": available,
                        }
                    ),
                    encoding="utf-8",
                )
            import duckdb

            projections = data_root / "projections"
            projections.mkdir(parents=True)
            connection = duckdb.connect(str(projections / "research_memory.duckdb"))
            try:
                connection.execute(
                    "CREATE TABLE _research_events "
                    "(entity_id VARCHAR, record_kind VARCHAR, payload_json VARCHAR, "
                    "first_reliable_available_at TIMESTAMP)"
                )
                connection.execute(
                    "INSERT INTO _research_events VALUES (?, 'OBSERVATION_SCHEDULE', ?, ?)",
                    [
                        SHA_A,
                        json.dumps({"schedule": _document(), "schedule_sha256": SHA_A}),
                        render_utc(clock),
                    ],
                )
            finally:
                connection.close()
            app = FactoryApplication(root=factory, research_data_root=data_root)
            market = _get(app, "/market", timeout=30)
            self.assertNotIn("SOURCE_NOT_PRESENT", market)
            self.assertIn('data-relative="HIGH_RELATIVE"', market)

    def test_schedule_sha_rollover_still_comparable(self) -> None:
        semantics = schedule_semantics_from_document(_document())
        left = context_compatibility_sha256(self.definition, semantics)
        other_doc = _document()
        other_doc["activation"] = {"starts_at": "2026-09-08T00:00:00Z"}
        other_doc["budgets"] = {"provider_calls_per_utc_day_max": 99}
        right_semantics = schedule_semantics_from_document(other_doc)
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
        rows.extend(_history({"FIELD-LIQUIDITY-USD-001": 100}, schedule_sha=SHA_B))
        bundle = {
            "source_status": "PRESENT",
            "observations": rows,
            "members": _members_from(rows),
            "schedules": {SHA_A: semantics, SHA_B: right_semantics},
        }
        projection = project_market_context(self.definition, bundle, as_of=AS_OF)
        self.assertEqual(
            _cell(projection, "Y1800", "LIQUIDITY_LEVEL")["relative_state"],
            "HIGH_RELATIVE",
        )

    def test_incompatible_sampling_is_reference_scope_mismatch(self) -> None:
        current_sem = schedule_semantics_from_document(_document())
        hist_sem = schedule_semantics_from_document(_document(policy="ALL_UNDER_CAP"))
        self.assertNotEqual(
            context_compatibility_sha256(self.definition, current_sem),
            context_compatibility_sha256(self.definition, hist_sem),
        )
        rows = [
            _obs("now1", "Y1800", AS_OF - timedelta(minutes=10), {"FIELD-LIQUIDITY-USD-001": 1000}),
        ]
        rows.extend(_history({"FIELD-LIQUIDITY-USD-001": 100}, schedule_sha=SHA_B))
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

    def test_incomparable_history_does_not_blend_breadth_previous(self) -> None:
        current_sem = schedule_semantics_from_document(_document())
        hist_sem = schedule_semantics_from_document(_document(policy="ALL_UNDER_CAP"))
        rows = [
            _obs(
                "mint1",
                "Y1800",
                AS_OF - timedelta(minutes=10),
                {"FIELD-LIQUIDITY-USD-001": 1000},
            ),
            _obs(
                "mint1",
                "Y900",
                AS_OF - timedelta(minutes=70),
                {"FIELD-LIQUIDITY-USD-001": 100},
                schedule_sha=SHA_B,
            ),
        ]
        bundle = {
            "source_status": "PRESENT",
            "observations": rows,
            "members": [],
            "schedules": {SHA_A: current_sem, SHA_B: hist_sem},
        }
        cell = _cell(
            project_market_context(self.definition, bundle, as_of=AS_OF),
            "Y1800",
            "LIQUIDITY_BREADTH",
        )
        self.assertIsNone(cell["raw_value"])
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
        rows.extend(_history({"FIELD-LIQUIDITY-USD-001": 100}))
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
        rows.extend(
            _history(
                {
                    "FIELD-LIQUIDITY-USD-001": 100,
                    "FIELD-STATS5M-NUM-TRADERS-001": 8,
                    "FIELD-STATS5M-NUM-BUYS-001": 2,
                    "FIELD-STATS5M-NUM-SELLS-001": 20,
                    "FIELD-USD-PRICE-001": 1,
                }
            )
        )
        rows.extend(
            _history(
                {"FIELD-LIQUIDITY-USD-001": 90, "FIELD-USD-PRICE-001": 1},
                point="Y900",
                extra_minutes=15,
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
        rows.extend(_history({"FIELD-LIQUIDITY-USD-001": 100}))
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

    def test_get_market_shows_observed_relative_state(self) -> None:
        from solana_alpha_lab.factory.market_context import git_data_capability

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
        rows.extend(_history({"FIELD-LIQUIDITY-USD-001": 100}))
        projection = project_market_context(
            self.definition, _bundle(self.definition, rows), as_of=AS_OF
        )
        self.assertEqual(
            _cell(projection, "Y1800", "LIQUIDITY_LEVEL")["relative_state"],
            "HIGH_RELATIVE",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = isolated_factory_root(Path(tmp))
            projection["data_capability"] = git_data_capability(root)
            app = FactoryApplication(root=root)

            def _projection(*, as_of=None):
                return projection

            app.market_projection = _projection  # type: ignore[method-assign]
            market = _get(app, "/market")
            self.assertIn('data-relative="HIGH_RELATIVE"', market)
            self.assertIn("Контекст сейчас", market)
            self.assertIn("Покрытие и пропуски", market)
            self.assertIn(str(_cell(projection, "Y1800", "LIQUIDITY_LEVEL")["n_observed"]), market)

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
            self.assertIn("SOURCE_NOT_PRESENT", market)
            self.assertIn('data-relative="UNKNOWN"', market)
            self.assertNotIn('data-relative="LOW_RELATIVE"', market)
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
