"""Frozen physical historical layouts; synthetic/scratch evidence only."""
from __future__ import annotations

import json
import copy
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.factory import live_corpus_logical_rows as logical
from solana_alpha_lab.factory import live_corpus_manifest_publish as publish
from solana_alpha_lab.factory import live_cohort_discovery_release as releases
from solana_alpha_lab.factory.hfic_evidence_identity import compute_market_epoch_for_data_root
from solana_alpha_lab.factory.hfic_preflight import enumerate_rdp_datasets, epoch_search_budget_usage
from solana_alpha_lab.factory.cohort_import_readback import build_cohort_import_readback
from solana_alpha_lab.factory.forge_input_receipt import build_forge_input_receipt
from solana_alpha_lab.factory.hfic_grounded_discovery import load_admitted_partition_rows
from solana_alpha_lab.factory.hfic_temporal_discovery import execute_temporal_discovery
from tests import test_live_corpus_manifest_contract_repair_v1 as fixture
from tests.test_live_cohort_discovery_release_series import _snapshot_for_week
from tests import test_hfic_market_evidence_epoch_decision_basis_v2 as market_fixture
from tests.test_hfic_temporal_discovery_v1 import _spec
from tests.test_hfic_temporal_production_runner_v1 import _schedule
from solana_alpha_lab.factory.observation_panel_publisher import persist_observation_schedule
from tests.test_live_cohort_discovery_release_series import PRODUCER, ACTIVATION

# An independent frozen fixture: never derive this from the moving writer schema.
OBS21_NAMES = (
    "release_id", "cohort_id", "mint", "point_id", "primitive_id", "field_id",
    "value_kind", "typed_value", "state", "missing_reason", "event_time",
    "request_started_at", "response_received_at", "first_reliable_available_at",
    "request_sha256", "response_sha256", "call_occurrence_id", "http_status",
    "http_class", "evidence_role", "confirmatory_reuse_forbidden",
)
OBS21 = pa.schema([
    pa.field(name, pa.int64() if name == "http_status" else
             pa.bool_() if name == "confirmatory_reuse_forbidden" else pa.string())
    for name in OBS21_NAMES
])
LEGACY_EXPECTED = "f593eaf7250991bf6d72ece7c9d01360a3e9b2f37c0456cb87a18435992a1a56"
CURRENT_NULL_EXPECTED = "266827eab99834c80d31f7581948de2f6f74572cd079c85006ca3b1932ff70fc"
HISTORICAL_COHORT_HASHES = (
    "26025cd5abc416de910358f89b54502328f56e1689bfbccda848a32bb935d548",
    "14130708af8fc36fd8e35995abd7de5b186bb6c95d667c83f645196e065b0b8d",
    "68078915ef6c5080fbffa3e424146497e4b0038eb0965fb283d407f9524e3789",
)


def legacy_descriptor():
    # Original frozen descriptor, independently serialized by this fixture.
    census_names = (
        "release_id", "cohort_id", "source_schedule_sha256", "activation_id",
        "producer_git_sha", "mint", "discovery_first_reliable_available_at",
        "authoritative_anchor", "candidate_state", "membership_state",
        "denominator_state", "sampling_policy", "sampling_seed",
        "inclusion_probability", "selected_or_excluded", "exclusion_reason",
        "discovery_coverage_class", "source_request_sha256", "source_response_sha256",
        "evidence_role",
    )
    return {
        "census": [{"name": n, "type": "string", "nullable": True} for n in census_names],
        "observations": [{"name": f.name, "type": str(f.type), "nullable": True} for f in OBS21],
        "logical_row_profile": "smial-live-corpus-logical-rows-v1",
        "profile": "smial-live-corpus-schema-v1",
        "schema_id": "SCHEMA-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
    }


def inventory(root):
    return {p.relative_to(root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in sorted(root.rglob("*")) if p.is_file()}


def seal_week_with_schedule(base, week, *, current_clocks=False):
    source = _snapshot_for_week(week)
    schedule = _schedule()
    source["schedule_sha256"] = schedule["schedule_sha256"]
    for member in source["members"]:
        if member["denominator_state"] == "observed":
            member["candidate_state"] = "X_ELIGIBLE"
    for row in list(source["observations"]):
        if row["point_id"] == "X300":
            source["observations"].append({**row, "field_id": "FIELD-LIQUIDITY-USD-001",
                                          "typed_value": "10000"})
    offsets = {"X300": 300, "Y900": 900, "Y1800": 1800, "Y3600": 3600, "Y7200": 7200}
    anchor = source["observations"][0]["event_time"]
    for row in source["observations"]:
        at = (datetime.fromisoformat(anchor.replace("Z", "+00:00")) + timedelta(
            seconds=offsets[row["point_id"]] + schedule["x_point"]["allowed_lateness_seconds"])
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        for key in ("event_time", "request_started_at", "response_received_at", "first_reliable_available_at"):
            row[key] = at
        if row["point_id"] == "Y7200":
            row.update(typed_value="1.50", state="OBSERVED", missing_reason=None)
    late = {**source["observations"][0], "typed_value": "999"}
    late_at = (datetime.fromisoformat(late["event_time"].replace("Z", "+00:00"))
               + timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for key in ("event_time", "request_started_at", "response_received_at", "first_reliable_available_at"):
        late[key] = late_at
    source["observations"].append(late)
    if current_clocks:
        for row in source["observations"][:3]:
            row.update(observation_clock_policy="EVENT_TIME_V1",
                       source_price_event_time=row["event_time"], member_anchor=anchor)
    with patch.object(fixture, "_snapshot_for_week", return_value=source):
        return fixture._seal_week(base, week)


def cold_read(data):
    rows, warnings = enumerate_rdp_datasets(data)
    assert not warnings, warnings
    chosen = releases.select_current_datasets_for_forge(rows)
    receipt = build_forge_input_receipt(data, repo_root=ROOT)
    loaded = load_admitted_partition_rows(data_root=data, binding_doc=None,
        partitions=None, census_path=None, observations_path=None)
    spec = _spec("SIMPLE_SCREEN", features=[{"name": "early", "op": "return_ratio",
        "field_id": "FIELD-USD-PRICE-001", "start": "X300", "end": "Y900"}],
        all=[{"feature": "early", "op": "gte", "value": 0.0}],
        decision={"point_id": "Y900", "time_policy": "BOUND_SCHEDULE_CUTOFF"},
        target={"kind": "PRICE_RELATIVE_PROXY", "reference_point": "Y900",
                "exit_point": "Y7200", "field_id": "FIELD-USD-PRICE-001"})
    computed = execute_temporal_discovery(
        loaded["census"], loaded["observations"], spec, loaded["cohorts"])
    return {"selected": [r["dataset_manifest_id"] for r in chosen],
            "receipt_mid": receipt["active_evidence_set"]["current_dataset_manifest_id"],
            "observations": loaded["observations"], "summary": computed["summary"]}


def frozen_rows():
    rows = []
    for missing in (False, True):
        row = dict.fromkeys(OBS21_NAMES)
        row.update(
            release_id="a" * 64,
            cohort_id="REL-20260105T120000Z-20260112T120000Z", mint="ScratchMint",
            point_id="Y900" if missing else "X300",
            primitive_id="PRIM-JUPITER-TOKENS-V2-SEARCH-001",
            field_id="FIELD-USD-PRICE-001", value_kind="DECIMAL",
            typed_value=None if missing else "1.23",
            state="MISSING" if missing else "OBSERVED",
            missing_reason="PROVIDER_TIMEOUT" if missing else None,
            event_time=None if missing else "2026-01-05T12:05:00Z",
            request_started_at="2026-01-05T12:05:00Z",
            response_received_at="2026-01-05T12:05:01Z",
            first_reliable_available_at="2026-01-05T12:05:02Z",
            request_sha256="c" * 64, response_sha256="d" * 64,
            call_occurrence_id="e" * 64, http_status=504 if missing else 200,
            http_class="TIMEOUT" if missing else "OK",
            evidence_role="EXPLORATORY_REUSE", confirmatory_reuse_forbidden=True,
        )
        rows.append(row)
    return rows


class FrozenProjectionTests(unittest.TestCase):
    def test_physical_obs21_reproduces_independently_pinned_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "historical.parquet"
            pq.write_table(pa.Table.from_pylist(frozen_rows(), schema=OBS21), path)
            before = (path.read_bytes(), path.stat().st_mtime_ns)
            self.assertTrue(pq.ParquetFile(path).schema_arrow.equals(OBS21))
            claims = logical.measure_live_corpus_parquet(
                path, kind="OBS", partition_id="FROZEN-OBS", logical_location=path.name)
            self.assertEqual(claims.content_sha256, LEGACY_EXPECTED)
            self.assertEqual(claims.row_count, 2)
            self.assertIsNone(claims.min_event_time)
            self.assertEqual(claims.min_available_to_strategy_at.isoformat(),
                             "2026-01-05T12:05:02+00:00")
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_explicit_current_null_columns_remain_in_content_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "current.parquet"
            rows = [{**r, "observation_clock_policy": None,
                     "source_price_event_time": None, "member_anchor": None}
                    for r in frozen_rows()]
            pq.write_table(pa.Table.from_pylist(rows, schema=logical.OBS_RELEASE_SCHEMA), path)
            claims = logical.measure_live_corpus_parquet(
                path, kind="OBS", partition_id="CURRENT-OBS", logical_location=path.name)
            self.assertEqual(claims.content_sha256, CURRENT_NULL_EXPECTED)
            self.assertNotEqual(claims.content_sha256, LEGACY_EXPECTED)


class MixedCorpusVerticalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.data = self.base / "rdp"
        self.data.mkdir()
        descriptor = legacy_descriptor()
        digest = hashlib.sha256(json.dumps(descriptor, sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(digest, "58d35d5a6c1248eea85d1a413ba82c3b987a52a13ca0b8f1d8ac458c44aaeb15")
        # Reproduce the historical writer/descriptor for fixture construction only;
        # no production claims are stubbed and files really have 21 columns.
        with patch.object(releases, "OBS_RELEASE_SCHEMA", OBS21), \
             patch.object(logical, "OBS_RELEASE_SCHEMA", OBS21), \
             patch.object(logical, "live_corpus_schema_projection", return_value=descriptor):
            for week in range(3):
                release, _, _ = seal_week_with_schedule(self.base, week)
                releases.verify_live_cohort(release)
                releases.import_live_cohort(release_root=release, data_root=self.data,
                    import_time=datetime(2026, 2, 10 + week, tzinfo=UTC))
        persist_observation_schedule(data_root=self.data, schedule=_schedule(),
            now=datetime(2026, 2, 13, tzinfo=UTC), producer_git_sha=PRODUCER,
            activation_id=ACTIVATION)
        self.old_lineage = releases.load_live_corpus_lineage(self.data)
        self.old_mid = self.old_lineage["current_dataset_manifest_id"]
        old = publish.inspect_canonical_root(self.data, self.old_mid,
            expected_schema_sha256=digest)
        self.assertTrue(old["complete"], old["reason"])
        self.old_claims = {p.partition_id: publish.claims_from_partition(p) for p in old["partitions"]}
        observed = [p.content_sha256 for p in old["partitions"] if p.partition_id.endswith("-OBS")]
        self.assertEqual(tuple(observed), HISTORICAL_COHORT_HASHES)
        self.before = inventory(self.data)
        self.release_before = {n: inventory(self.base / f"rel_{n}") for n in range(3)}
        self.epoch, self.basis = compute_market_epoch_for_data_root(ROOT, self.data)

    def repair(self):
        return releases.repair_live_corpus_manifests(data_root=self.data,
            published_at=datetime(2026, 3, 1, tzinfo=UTC))

    def append(self, week):
        release, _, _ = seal_week_with_schedule(self.base, week, current_clocks=True)
        releases.verify_live_cohort(release)
        with patch.object(publish, "measure_live_corpus_parquet",
                          wraps=logical.measure_live_corpus_parquet) as measured:
            result = releases.import_live_cohort(release_root=release, data_root=self.data,
                import_time=datetime(2026, 2, 10 + week, tzinfo=UTC))
        self.assertEqual(measured.call_count, 2)
        self.assertTrue(all(result["cohort_id"] in call.kwargs["logical_location"]
                            for call in measured.call_args_list))
        self.assertEqual(result["logical_rows_measured_partitions"], 2)
        return result

    def test_connected_v3_repair_mixed_v4_cold_idempotent_v5_append(self):
        history = [market_fixture.ScientificMarketV2Tests.session(self.epoch, self.basis)]
        frozen_history = copy.deepcopy(history)
        usage = epoch_search_budget_usage(history, evidence_epoch=self.epoch,
                                         market_evidence_basis=self.basis)
        repaired = self.repair()
        self.assertEqual(repaired["status"], "REPAIRED")
        self.assertEqual(repaired["corpus_version"], 3)
        root = publish.inspect_canonical_root(self.data, repaired["dataset_manifest_id"])
        self.assertTrue(root["complete"])
        self.assertEqual({p.partition_id: publish.claims_from_partition(p) for p in root["partitions"]},
                         self.old_claims)
        epoch, basis = compute_market_epoch_for_data_root(ROOT, self.data)
        self.assertEqual(epoch, self.epoch)
        self.assertEqual(epoch_search_budget_usage(history, evidence_epoch=epoch,
                         market_evidence_basis=basis), usage)
        historical_rows = [r for c in self.old_lineage["cohorts"]
            for r in pq.ParquetFile(self.data / c["obs_rel"]).read().to_pylist()]
        v4 = self.append(3)
        self.assertEqual(v4["corpus_version"], 4)
        self.assertNotEqual(compute_market_epoch_for_data_root(ROOT, self.data)[0], epoch)
        readback = build_cohort_import_readback(self.data)
        self.assertEqual(readback["duplicate_cohort_count"], 0)
        self.assertEqual(len(readback["visible_cohorts"]), 4)
        self.assertTrue(all(r["lineage_count"] == 1 for r in readback["visible_cohorts"]))
        command = [sys.executable, "-X", "utf8", "-B", "-c",
            "import json; from pathlib import Path; "
            "from tests.test_live_corpus_stored_projection_compatibility_v1 import cold_read; "
            "import sys; print(json.dumps(cold_read(Path(sys.argv[1]))))", str(self.data)]
        child = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(child.returncode, 0, child.stderr)
        cold = json.loads(child.stdout)
        self.assertEqual(cold["selected"], [v4["dataset_manifest_id"]])
        self.assertEqual(cold["receipt_mid"], v4["dataset_manifest_id"])
        historical_ids = {c["cohort_id"] for c in self.old_lineage["cohorts"]}
        old_rows = [r for r in cold["observations"] if r["cohort_id"] in historical_ids]
        self.assertEqual(old_rows, historical_rows)
        self.assertTrue(all("observation_clock_policy" not in r for r in old_rows))
        new_rows = [r for r in cold["observations"] if r["cohort_id"] == v4["cohort_id"]]
        self.assertTrue(any(r["observation_clock_policy"] is None for r in new_rows))
        self.assertTrue(any(r["observation_clock_policy"] == "EVENT_TIME_V1"
                            and r["source_price_event_time"] and r["member_anchor"] for r in new_rows))
        self.assertEqual([r["matched_n"] for r in cold["summary"]["by_cohort"]], [2] * 4)
        self.assertEqual([r["observed_target_n"] for r in cold["summary"]["by_cohort"]], [1] * 4)
        self.assertEqual([r["missing_target_n"] for r in cold["summary"]["by_cohort"]], [1] * 4)
        mixed_before = inventory(self.data)
        self.assertEqual(self.repair()["status"], "IDEMPOTENT_REPAIR")
        self.assertEqual(inventory(self.data), mixed_before)
        v5 = self.append(4)
        self.assertEqual(v5["corpus_version"], 5)
        self.assertTrue(publish.inspect_canonical_root(self.data, v5["dataset_manifest_id"])["complete"])
        final = build_cohort_import_readback(self.data)
        self.assertEqual(len(final["visible_cohorts"]), 5)
        self.assertEqual(final["duplicate_cohort_count"], 0)
        self.assertTrue(all(r["lineage_count"] == 1 for r in final["visible_cohorts"]))
        for path, state in self.before.items():
            if path.endswith(".parquet"):
                self.assertEqual(inventory(self.data)[path], state)
        for n, state in self.release_before.items():
            self.assertEqual(inventory(self.base / f"rel_{n}"), state)
        self.assertEqual(history, frozen_history)

    def test_altered_bytes_stop_repair_before_current_state_changes(self):
        path = self.data / self.old_lineage["cohorts"][0]["obs_rel"]
        content = path.read_bytes()
        path.write_bytes(content[:-1] + bytes([content[-1] ^ 1]))
        before = inventory(self.data)
        with self.assertRaisesRegex(Exception, "CORPUS_PARQUET_SHA_MISMATCH"):
            self.repair()
        self.assertEqual(inventory(self.data), before)

    def test_stored_content_and_pit_bindings_are_not_replaced_by_current_reader(self):
        part = next(c for c in self.old_claims.values() if c.kind == "OBS")
        before = inventory(self.data)
        for wrong in (replace(part, content_sha256="0" * 64),
                      replace(part, min_available_to_strategy_at=None)):
            with self.subTest(wrong=wrong), self.assertRaisesRegex(
                    logical.LiveCorpusLogicalRowError, "LIVE_CORPUS_LOGICAL_CONTENT_NOT_RECONSTRUCTIBLE"):
                logical.measure_live_corpus_parquet(self.data / part.logical_location,
                    kind=part.kind, partition_id=part.partition_id,
                    logical_location=part.logical_location, stored_claims=wrong)
        self.assertEqual(inventory(self.data), before)

    def test_unknown_names_types_and_nullability_stop_without_writes(self):
        cases = [pa.schema([pa.field("unknown" if f.name == "mint" else f.name, f.type)
                            for f in OBS21]),
                 pa.schema([pa.field(f.name, pa.int32() if f.name == "http_status" else f.type)
                            for f in OBS21]),
                 pa.schema([pa.field(f.name, f.type, nullable=f.name != "mint") for f in OBS21])]
        before = inventory(self.data)
        for i, schema in enumerate(cases):
            with self.subTest(i=i):
                path = self.base / f"unsupported_{i}.parquet"
                pq.write_table(pa.Table.from_pylist(frozen_rows(), schema=schema), path)
                state = inventory(self.base)
                with self.assertRaisesRegex(logical.LiveCorpusLogicalRowError,
                                           "LIVE_CORPUS_PARTITION_SCHEMA_UNSUPPORTED"):
                    logical.measure_live_corpus_parquet(path, kind="OBS",
                        partition_id="UNSUPPORTED", logical_location=path.name)
                self.assertEqual(inventory(self.base), state)
        self.assertEqual(inventory(self.data), before)


if __name__ == "__main__":
    unittest.main()
