from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.quote_native_evidence_timing_recovery import (  # noqa: E402
    TimingRecoveryError,
    recover_timing,
)


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _runtime_for(
    *,
    root: Path,
    h900_written_at: datetime,
    h3600_written_at: datetime,
) -> dict[str, object]:
    h900_due = datetime(2026, 8, 18, 12, 15, tzinfo=UTC)
    h3600_due = datetime(2026, 8, 18, 13, 0, tzinfo=UTC)
    rows = [
        ("RECENT_1:10000000:SELL_H900", h900_due, 900, h900_written_at),
        ("RECENT_1:10000000:SELL_H3600", h3600_due, 3600, h3600_written_at),
    ]
    manifests: list[dict[str, object]] = []
    observations: list[dict[str, object]] = []
    for observation_id, due_at, horizon, written_at in rows:
        filename = observation_id.replace(":", "_") + ".json"
        payload_path = root / "run=fixture" / filename
        payload_path.parent.mkdir(parents=True, exist_ok=True)
        body = f'{{"observation":"{observation_id}"}}'.encode("utf-8")
        payload_path.write_bytes(body)
        timestamp = written_at.timestamp()
        os.utime(payload_path, (timestamp, timestamp))
        manifests.append(
            {
                "observation_id": observation_id,
                "path": payload_path.relative_to(root).as_posix(),
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "retention": "A4_OUTSIDE_GIT",
            }
        )
        observations.append(
            {
                "observation_id": observation_id,
                "kind": f"SELL_H{horizon}",
                "horizon_seconds": horizon,
                "due_at": _utc(due_at),
                "lateness_slack_seconds": 120,
                "consumed_call": True,
                "terminal": "QUOTE_OBSERVED",
            }
        )
    return {
        "atom_id": "QUOTE_NATIVE_EVIDENCE_CHANNEL_QUALIFICATION_V1",
        "raw_retention": {"manifests": manifests},
        "observations": observations,
    }


class TimingRecoveryTests(unittest.TestCase):
    def test_recovers_hash_matched_raw_write_upper_bounds_inside_horizon_slack(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = _runtime_for(
                root=root,
                h900_written_at=datetime(2026, 8, 18, 12, 15, 30, tzinfo=UTC),
                h3600_written_at=datetime(2026, 8, 18, 13, 1, tzinfo=UTC),
            )

            recovered = recover_timing(receipt, raw_root=root)

        self.assertEqual(
            recovered["verdict"],
            "RECOVERED_RAW_WRITE_UPPER_BOUND_WITHIN_SLACK",
        )
        self.assertEqual(recovered["horizon_counts"], {"900": 1, "3600": 1})
        self.assertEqual(recovered["recovered_rows"][0]["within_slack"], True)
        self.assertEqual(
            recovered["timestamp_semantics"],
            "LOCAL_RAW_WRITE_COMPLETE_UPPER_BOUND_NOT_REMOTE_OBSERVED_AT",
        )

    def test_rejects_raw_write_after_declared_lateness_slack(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = _runtime_for(
                root=root,
                h900_written_at=datetime(2026, 8, 18, 12, 17, 1, tzinfo=UTC),
                h3600_written_at=datetime(2026, 8, 18, 13, 1, tzinfo=UTC),
            )

            with self.assertRaisesRegex(TimingRecoveryError, "RAW_WRITE_OUTSIDE_SLACK"):
                recover_timing(receipt, raw_root=root)

    def test_runner_writes_append_only_recovery_receipt_without_raw_or_absolute_paths(self) -> None:
        from scripts.recover_quote_native_evidence_timing import run_recovery

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_root = root / "raw"
            runtime = _runtime_for(
                root=raw_root,
                h900_written_at=datetime(2026, 8, 18, 12, 15, 30, tzinfo=UTC),
                h3600_written_at=datetime(2026, 8, 18, 13, 1, tzinfo=UTC),
            )
            runtime_path = root / "runtime.json"
            output_path = root / "recovery.json"
            runtime_path.write_text(
                json.dumps(runtime, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            result = run_recovery(
                runtime_path=runtime_path,
                raw_root=raw_root,
                output_path=output_path,
                required_horizon_counts={"900": 1, "3600": 1},
            )

            serialized = output_path.read_text(encoding="utf-8")
            self.assertTrue(output_path.is_file())
            self.assertEqual(
                result["verdict"],
                "RECOVERED_RAW_WRITE_UPPER_BOUND_WITHIN_SLACK",
            )
            self.assertEqual(result["side_effects"]["provider_requests"], 0)
            self.assertNotIn(str(root), serialized)
            self.assertNotIn("raw_body", serialized)


if __name__ == "__main__":
    unittest.main()
