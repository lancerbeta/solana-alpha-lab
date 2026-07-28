from __future__ import annotations

import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.run_task13_pilot_audit import main  # noqa: E402
from solana_alpha_lab.pilot_audit import (  # noqa: E402
    AUDIT_RESULT_SCHEMA,
    PilotAuditContractError,
    audit_population,
)

BASE_TIME = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
POPULATION_PATH = "population.json"


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _raw_table(*, pit_violation: bool = False) -> pa.Table:
    observed = [
        BASE_TIME,
        BASE_TIME + timedelta(seconds=1),
        BASE_TIME + timedelta(seconds=2),
    ]
    reliable = list(observed)
    available = list(observed)
    if pit_violation:
        reliable[1] = observed[1] - timedelta(milliseconds=1)
    return pa.table(
        {
            "raw_event_id": ["raw-a", "raw-b", "raw-c"],
            "idempotency_key": ["idem-a", "idem-b", "idem-c"],
            "source": ["SOURCE_A", "SOURCE_A", "SOURCE_B"],
            "response_status": ["SUCCESS", "SUCCESS", "HTTP_ERROR"],
            "error_class": [None, None, "http_status_not_success:401"],
            "content_sha256": ["a" * 64, "a" * 64, "b" * 64],
            "event_time": observed,
            "observed_at": observed,
            "first_reliable_available_at": reliable,
            "available_to_strategy_at": available,
            "ingested_at": [
                value + timedelta(milliseconds=1) for value in available
            ],
        }
    )


def _write_projection(path: Path, raw_ids: list[str]) -> None:
    connection = duckdb.connect(str(path))
    try:
        connection.execute("CREATE TABLE raw_api_events(raw_event_id VARCHAR)")
        connection.execute("CREATE TABLE quote_attempts(raw_event_id VARCHAR)")
        connection.execute(
            "CREATE TABLE execution_attempts(raw_event_id VARCHAR)"
        )
        connection.executemany(
            "INSERT INTO raw_api_events VALUES (?)",
            [(value,) for value in raw_ids],
        )
        connection.executemany(
            "INSERT INTO quote_attempts VALUES (?)",
            [(value,) for value in raw_ids],
        )
    finally:
        connection.close()


def _build_population(root: Path, *, pit_violation: bool = False) -> str:
    raw_path = root / "data" / "raw" / "synthetic.parquet"
    raw_path.parent.mkdir(parents=True)
    pq.write_table(_raw_table(pit_violation=pit_violation), raw_path)
    projection_path = root / "data" / "raw" / "synthetic.duckdb"
    _write_projection(projection_path, ["raw-a", "raw-b", "raw-c"])
    evidence_path = root / "evidence.json"
    evidence_path.write_bytes(_canonical_json_bytes({"status": "PASS"}))

    raw_bytes = raw_path.stat().st_size
    projection_bytes = projection_path.stat().st_size
    document = {
        "schema": "solana_alpha_lab.pilot_audit_population",
        "schema_version": "1.0",
        "contract_id": "CONTRACT-T13-PILOT-AUDIT-001",
        "population_id": "POPULATION-T13-BOUNDED-HISTORICAL-EVIDENCE-001",
        "population_version": "1.0",
        "task_id": "TASK-13",
        "atom_id": "T13-A2_FROZEN_BOUNDED_AUDIT_CONTRACT_V1",
        "as_of": "2026-07-28",
        "status": "FROZEN_BOUNDED_HISTORICAL_EVIDENCE_CONTRACT",
        "entry_verdict": "START_WITH_PATCH",
        "accepted_claim": (
            "BOUNDED_HISTORICAL_EVIDENCE_AUDIT_CONTRACT_FROZEN"
        ),
        "sustained_pilot_claim": False,
        "provider_purchase_claim": False,
        "population": {
            "class": "BOUNDED_HISTORICAL_EVIDENCE_NOT_SUSTAINED_PILOT",
            "global_pit_cutoff": "2026-07-28T12:00:02Z",
            "primary_slice_id": "SYNTHETIC",
            "primary_consumer": "TASK-14",
            "raw_rows": 3,
            "raw_parquet_files": 1,
            "raw_parquet_bytes": raw_bytes,
            "projection_files": 1,
            "projection_bytes": projection_bytes,
            "data_files": 2,
            "data_bytes": raw_bytes + projection_bytes,
            "unique_raw_event_ids": 3,
            "unique_idempotency_keys": 3,
            "unique_content_sha256": 2,
        },
        "slices": [
            {
                "slice_id": "SYNTHETIC",
                "task_id": "TASK-10",
                "asset_ids": ["DATA-SYNTHETIC-001"],
                "role": "PRIMARY_AUDIT_SLICE",
                "raw_rows": 3,
                "unique_raw_event_ids": 3,
                "unique_idempotency_keys": 3,
                "unique_content_sha256": 2,
                "missing_identity_rows": 0,
                "pit_order_violations": 0,
                "status_counts": [
                    {
                        "source": "SOURCE_A",
                        "response_status": "SUCCESS",
                        "error_class": None,
                        "rows": 2,
                    },
                    {
                        "source": "SOURCE_B",
                        "response_status": "HTTP_ERROR",
                        "error_class": "http_status_not_success:401",
                        "rows": 1,
                    },
                ],
                "projection_rows": {
                    "raw_api_events": 3,
                    "quote_attempts": 3,
                    "execution_attempts": 0,
                },
            }
        ],
        "data_files": [
            {
                "slice_id": "SYNTHETIC",
                "asset_id": "DATA-SYNTHETIC-RAW-001",
                "kind": "RAW_PARQUET",
                "path": "data/raw/synthetic.parquet",
                "sha256": _sha256(raw_path),
                "bytes": raw_bytes,
                "rows": 3,
            },
            {
                "slice_id": "SYNTHETIC",
                "asset_id": "DATA-SYNTHETIC-PROJECTION-001",
                "kind": "DUCKDB_PROJECTION",
                "path": "data/raw/synthetic.duckdb",
                "sha256": _sha256(projection_path),
                "bytes": projection_bytes,
                "rows": 3,
            },
        ],
        "tracked_evidence": [
            {
                "asset_id": "EVIDENCE-SYNTHETIC-001",
                "path": "evidence.json",
                "sha256": _sha256(evidence_path),
            }
        ],
        "caps": {
            "data_files_exact": 2,
            "input_bytes_exact": raw_bytes + projection_bytes,
            "raw_rows_exact": 3,
            "future_local_wall_seconds_max": 120,
            "future_sanitized_output_bytes_max": 1048576,
        },
    }
    population_path = root / POPULATION_PATH
    population_path.write_bytes(_canonical_json_bytes(document))
    return _sha256(population_path)


class Task13PilotAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="task13_audit_")
        self.root = Path(self.temp.name).resolve()
        self.population_sha256 = _build_population(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _run(self) -> dict[str, object]:
        return audit_population(
            repository_root=self.root,
            population_path=POPULATION_PATH,
            expected_population_sha256=self.population_sha256,
        )

    def test_synthetic_population_audits_deterministically(self) -> None:
        first = self._run()
        second = self._run()
        self.assertEqual(first, second)
        self.assertEqual(first["schema"], AUDIT_RESULT_SCHEMA)
        self.assertEqual(first["status"], "PASS_FROZEN_BASELINE_REPRODUCED")
        self.assertEqual(first["totals"]["raw_rows"], 3)
        self.assertEqual(first["totals"]["unique_content_sha256"], 2)
        metrics = first["slice_metrics"][0]
        self.assertEqual(metrics["identity_complete_rows"], 3)
        self.assertEqual(metrics["repeated_content_rows"], 1)
        self.assertEqual(metrics["typed_failure_rows"], 1)
        self.assertEqual(metrics["pit_order_violations"], 0)
        self.assertEqual(metrics["rows_after_global_pit_cutoff"], 0)
        self.assertEqual(metrics["availability_lag"]["mean"], "0")
        projection = first["projection_reconciliation"][0]
        self.assertTrue(projection["raw_event_lineage_exact"])
        self.assertTrue(projection["quote_event_lineage_exact"])
        self.assertFalse(projection["quote_is_fill"])
        self.assertEqual(first["side_effects"]["network_calls"], 0)

    def test_result_is_sanitized_and_contains_no_provider_body(self) -> None:
        encoded = _canonical_json_bytes(self._run()).decode("utf-8")
        self.assertNotIn("redacted_body", encoded)
        self.assertNotIn(str(self.root), encoded)
        self.assertNotIn("provider_body", encoded)
        self.assertLess(len(encoded.encode("utf-8")), 1_048_576)

    def test_raw_byte_tamper_fails_before_analysis(self) -> None:
        path = self.root / "data" / "raw" / "synthetic.parquet"
        data = bytearray(path.read_bytes())
        data[-1] ^= 1
        path.write_bytes(data)
        with self.assertRaisesRegex(
            PilotAuditContractError,
            "input_sha256_mismatch",
        ):
            self._run()

    def test_pit_violation_cannot_hide_behind_matching_file_hash(self) -> None:
        self.temp.cleanup()
        self.temp = tempfile.TemporaryDirectory(prefix="task13_audit_pit_")
        self.root = Path(self.temp.name).resolve()
        self.population_sha256 = _build_population(
            self.root,
            pit_violation=True,
        )
        with self.assertRaisesRegex(
            PilotAuditContractError,
            "slice_pit_order_violations_drift",
        ):
            self._run()

    def test_projection_lineage_mismatch_fails_closed(self) -> None:
        path = self.root / "data" / "raw" / "synthetic.duckdb"
        connection = duckdb.connect(str(path))
        try:
            connection.execute(
                "UPDATE quote_attempts SET raw_event_id = 'wrong' "
                "WHERE raw_event_id = 'raw-c'"
            )
        finally:
            connection.close()
        document_path = self.root / POPULATION_PATH
        document = json.loads(document_path.read_text(encoding="utf-8"))
        projection = document["data_files"][1]
        projection["sha256"] = _sha256(path)
        projection["bytes"] = path.stat().st_size
        document["population"]["projection_bytes"] = path.stat().st_size
        document["population"]["data_bytes"] = (
            document["population"]["raw_parquet_bytes"] + path.stat().st_size
        )
        document["caps"]["input_bytes_exact"] = document["population"][
            "data_bytes"
        ]
        document_path.write_bytes(_canonical_json_bytes(document))
        self.population_sha256 = _sha256(document_path)
        with self.assertRaisesRegex(
            PilotAuditContractError,
            "projection_quote_lineage_mismatch",
        ):
            self._run()

    def test_row_after_global_cutoff_fails_closed(self) -> None:
        document_path = self.root / POPULATION_PATH
        document = json.loads(document_path.read_text(encoding="utf-8"))
        document["population"]["global_pit_cutoff"] = (
            "2026-07-28T12:00:01Z"
        )
        document_path.write_bytes(_canonical_json_bytes(document))
        self.population_sha256 = _sha256(document_path)
        with self.assertRaisesRegex(
            PilotAuditContractError,
            "slice_rows_after_global_pit_cutoff",
        ):
            self._run()

    def test_relative_path_escape_fails_closed(self) -> None:
        document_path = self.root / POPULATION_PATH
        document = json.loads(document_path.read_text(encoding="utf-8"))
        document["data_files"][0]["path"] = "../outside.parquet"
        document_path.write_bytes(_canonical_json_bytes(document))
        self.population_sha256 = _sha256(document_path)
        with self.assertRaisesRegex(
            PilotAuditContractError,
            "input_path_unsafe",
        ):
            self._run()

    def test_cli_is_offline_deterministic_and_sanitized(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = main(
                ["--population", POPULATION_PATH],
                repository_root=self.root,
                expected_population_sha256=self.population_sha256,
            )
        output = stream.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("TASK13_PILOT_AUDIT: PASS", output)
        self.assertIn("EXTERNAL_EFFECTS: ZERO", output)
        self.assertNotIn(str(self.root), output)

    def test_cli_failure_exposes_only_typed_error_code(self) -> None:
        path = self.root / "data" / "raw" / "synthetic.parquet"
        path.write_bytes(b"tampered")
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = main(
                ["--population", POPULATION_PATH],
                repository_root=self.root,
                expected_population_sha256=self.population_sha256,
            )
        output = stream.getvalue()
        self.assertEqual(code, 2)
        self.assertIn("TASK13_PILOT_AUDIT: FAIL", output)
        self.assertIn("ERROR_CODE: input_bytes_mismatch", output)
        self.assertIn("EXTERNAL_EFFECTS: ZERO", output)
        self.assertNotIn(str(self.root), output)


if __name__ == "__main__":
    unittest.main()
