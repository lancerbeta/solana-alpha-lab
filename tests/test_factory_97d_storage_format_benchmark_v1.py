"""Lossless Parquet/raw representation benchmarks on a schema-faithful corpus.

Does not commit live Factory bytes. Semantic equality includes typed values,
event_time, first_reliable_available_at, missingness/state, and call identity.
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    canonical_json_bytes,
    canonical_sha256,
)


def _semantic_fingerprint(table: pa.Table) -> str:
    payload = [{"name": name, "values": table.column(name).to_pylist()} for name in table.column_names]
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _observation_rows(count: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(count):
        event_time = f"2026-09-04T12:{index % 60:02d}:00Z"
        available = f"2026-09-04T12:{index % 60:02d}:01Z"
        observed = index % 7 != 0
        request_sha = hashlib.sha256(f"req-{index}".encode("utf-8")).hexdigest()
        call_id = f"CALL-{index:06d}"
        rows.append(
            {
                "point_id": f"POINT-{index:06d}",
                "entity_id": f"mint{index % 17}",
                "primitive_id": "PRIM-QUOTE-BUY-001",
                "event_time": event_time,
                "first_reliable_available_at": available,
                "request_sha256": request_sha,
                "call_occurrence_id": call_id,
                "state": "OBSERVED" if observed else "MISSING_TYPED",
                "field_values": [
                    {
                        "field_id": "FIELD-QUOTE-BUY-OUT-AMOUNT-001",
                        "value_kind": "integer_string",
                        "typed_value_or_null": str(1000 + index) if observed else None,
                        "state": "OBSERVED" if observed else "MISSING_TYPED",
                        "missing_reason": None if observed else "FIELD_ABSENT",
                        "primitive_id": "PRIM-QUOTE-BUY-001",
                        "point_id": f"POINT-{index:06d}",
                        "event_time": event_time,
                        "first_reliable_available_at": available,
                        "request_sha256": request_sha,
                        "call_occurrence_id": call_id,
                    }
                ],
            }
        )
    return rows


class Factory97dFormatBenchmarkTests(unittest.TestCase):
    def test_parquet_codecs_preserve_scientific_semantics_and_zstd_shrinks(self) -> None:
        table = pa.Table.from_pylist(_observation_rows(240))
        original_fp = _semantic_fingerprint(table)
        codecs: list[tuple[str, dict[str, object]]] = [
            ("current_unspecified", {}),
            ("uncompressed", {"compression": "none"}),
            ("zstd_1", {"compression": "zstd", "compression_level": 1}),
            ("zstd_3", {"compression": "zstd", "compression_level": 3}),
            ("zstd_7", {"compression": "zstd", "compression_level": 7}),
            ("snappy", {"compression": "snappy"}),
        ]
        sizes: dict[str, int] = {}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for label, kwargs in codecs:
                path = root / f"{label}.parquet"
                pq.write_table(table, path, **kwargs)
                roundtrip = pq.read_table(path)
                self.assertEqual(_semantic_fingerprint(roundtrip), original_fp, label)
                sizes[label] = path.stat().st_size
        self.assertLess(sizes["zstd_3"], sizes["uncompressed"])
        self.assertLess(sizes["zstd_7"], sizes["uncompressed"])

    def test_batch_concat_preserves_first_reliable_available_at(self) -> None:
        first = pa.Table.from_pylist(_observation_rows(40))
        second = pa.Table.from_pylist(_observation_rows(40)[20:])
        merged = pa.concat_tables([first, second], promote_options="default")
        clocks = merged.column("first_reliable_available_at").to_pylist()
        self.assertEqual(clocks[:40], first.column("first_reliable_available_at").to_pylist())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "batch.parquet"
            pq.write_table(merged, path, compression="zstd", compression_level=3)
            roundtrip = pq.read_table(path)
            self.assertEqual(
                roundtrip.column("first_reliable_available_at").to_pylist(),
                clocks,
            )

    def test_canonical_raw_parquet_roundtrip_and_sha_dedup(self) -> None:
        bodies = [
            {"rows": [{"id": "a", "price": "1"}]},
            {"rows": [{"id": "b", "price": "2"}]},
            {"rows": [{"id": "a", "price": "1"}]},
        ]
        records = []
        unique: dict[str, bytes] = {}
        for index, body in enumerate(bodies):
            canonical = canonical_json_bytes(body)
            digest = canonical_sha256(body)
            unique[digest] = canonical
            records.append(
                {
                    "call_occurrence_id": f"CALL-{index}",
                    "request_sha256": hashlib.sha256(f"req-{index}".encode()).hexdigest(),
                    "response_sha256": digest,
                    "first_reliable_available_at": f"2026-09-04T12:00:0{index}Z",
                    "canonical_json_bytes": canonical,
                }
            )
        table = pa.table(
            {
                "call_occurrence_id": [row["call_occurrence_id"] for row in records],
                "request_sha256": [row["request_sha256"] for row in records],
                "response_sha256": [row["response_sha256"] for row in records],
                "first_reliable_available_at": [
                    row["first_reliable_available_at"] for row in records
                ],
                "canonical_json_bytes": [row["canonical_json_bytes"] for row in records],
            }
        )
        uniq = pa.table(
            {
                "response_sha256": list(unique.keys()),
                "canonical_json_bytes": list(unique.values()),
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inline = root / "inline.parquet"
            bodies_path = root / "unique-bodies.parquet"
            pq.write_table(table, inline, compression="zstd", compression_level=3)
            pq.write_table(uniq, bodies_path, compression="zstd", compression_level=3)
            extracted = pq.read_table(inline).column("canonical_json_bytes").to_pylist()
            self.assertEqual(extracted, [row["canonical_json_bytes"] for row in records])
            uniq_rt = pq.read_table(bodies_path)
            mapping = dict(
                zip(
                    uniq_rt.column("response_sha256").to_pylist(),
                    uniq_rt.column("canonical_json_bytes").to_pylist(),
                )
            )
            rebuilt = [mapping[row["response_sha256"]] for row in records]
            self.assertEqual(rebuilt, [row["canonical_json_bytes"] for row in records])
            self.assertEqual(len(unique), 2)
            self.assertEqual(
                hashlib.sha256(rebuilt[0]).hexdigest(),
                records[0]["response_sha256"],
            )
            self.assertEqual(
                records[0]["response_sha256"],
                records[2]["response_sha256"],
            )
