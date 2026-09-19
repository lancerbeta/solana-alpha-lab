#!/usr/bin/env python3
"""Deterministic production-shape plan bench for C3/C20/C50/C100.

Compares ResearchStore payload work and selected member/observation counts
across synthetic history depths with comparable per-cohort publication
density. Does not create giant real datasets and does not run the unbounded
C2 algorithm.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.bounded_cohort_materialization import (  # noqa: E402
    BOUNDED_WORK_CLASS,
)
from solana_alpha_lab.factory.live_cohort_discovery_release import (  # noqa: E402
    build_live_observation_source_from_rdp,
)
from solana_alpha_lab.factory.live_cohort_to_forge import synthetic_closed_receipt  # noqa: E402
from solana_alpha_lab.factory.members_snapshot_delta import write_snapshot_unit  # noqa: E402
from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    persist_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
    schedule_sha256,
    validate_observation_schedule,
)
from solana_alpha_lab.factory.research_store import (  # noqa: E402
    RecordKind,
    ResearchEvent,
    ResearchStore,
)
from solana_alpha_lab.storage.manifests import compute_dataset_manifest_id  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

ACTIVATION_ID = "ACT-BOUNDED-BENCH-V1"
WINDOW_START = datetime(2026, 9, 9, 11, 19, tzinfo=UTC)
PRODUCER = "a" * 40
COHORT_ID = "REL-20260909T111900Z-20260916T111900Z"
AS_OF = datetime(2026, 9, 17, 11, 19, tzinfo=UTC)


def _schedule() -> dict[str, Any]:
    schedule = load_observation_schedule(
        ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
    )
    schedule = dict(schedule)
    schedule.pop("schedule_sha256", None)
    schedule["activation"] = {
        **dict(schedule.get("activation") or {}),
        "starts_at": "2026-09-02T11:19:00Z",
        "stops_admitting_at": "2026-09-23T11:19:00Z",
        "cadence_alignment": "UTC_EPOCH",
    }
    validated = validate_observation_schedule(schedule, root=ROOT)
    digest = schedule_sha256(validated)
    validated["schedule_sha256"] = digest
    return validated


def _member(entity_id: str, *, admit: datetime, digest: str) -> dict[str, str]:
    stamp = admit.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "schedule_sha256": digest,
        "activation_id": ACTIVATION_ID,
        "entity_id": entity_id,
        "mint": entity_id,
        "discovery_first_reliable_available_at": stamp,
        "first_reliable_available_at": stamp,
        "discovery_available_at": stamp,
        "authoritative_anchor": stamp,
        "membership_state": "OBSERVED",
        "candidate_state": "ADMITTED",
        "inclusion_probability": "0.0425",
        "sampling_seed": "BOUNDED-BENCH",
    }


def _append_event(
    data_root: Path,
    *,
    record_id: str,
    kind: RecordKind,
    digest: str,
    payload: dict[str, Any],
    now: datetime,
    txn: str,
) -> None:
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    event = ResearchEvent(
        record_id=record_id,
        record_kind=kind,
        entity_id=digest,
        hypothesis_version_id=None,
        run_id=ACTIVATION_ID,
        transaction_id=txn,
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OBSERVATION-SCHEDULE-COMPILE-BIND-001",
        producer_git_sha=PRODUCER,
        created_at=now,
    )
    ResearchStore(data_root).append([event], transaction_id=txn)


def _publish_current_observation(root: Path, *, digest: str) -> None:
    stamp = (WINDOW_START + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    obs_rel = "datasets/parquet/cur-obs/observations.parquet"
    obs_path = root / obs_rel
    obs_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "schedule_sha256": digest,
                    "activation_id": ACTIVATION_ID,
                    "entity_id": "mint1",
                    "point_id": "X300",
                    "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001",
                    "event_time": stamp,
                    "first_reliable_available_at": stamp,
                    "request_sha256": "c" * 64,
                    "response_sha256": "d" * 64,
                    "call_occurrence_id": "e" * 64,
                    "http_status": 200,
                    "http_class": "HTTP_OK",
                    "field_values": [
                        {
                            "field_id": "FIELD-LIQUIDITY-USD-001",
                            "value_kind": "DECIMAL",
                            "typed_value": "1.25",
                            "state": "OBSERVED",
                        }
                    ],
                }
            ]
        ),
        obs_path,
        compression="zstd",
    )
    dataset_id = "observation-panel-cur"
    dataset_version = "20260910-1-cur"
    dataset_manifest_id = compute_dataset_manifest_id(dataset_id, dataset_version)
    manifests = root / "datasets" / "manifests"
    manifests.mkdir(parents=True, exist_ok=True)
    manifest = {
        "dataset_manifest_id": dataset_manifest_id,
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "created_at": stamp,
        "first_reliable_available_at": stamp,
        "partitions": [
            {
                "partition_manifest_id": "partition-cur-obs",
                "dataset_manifest_id": dataset_manifest_id,
                "partition_id": "utc-day-20260910",
                "logical_location": obs_rel,
            }
        ],
    }
    (manifests / f"{dataset_manifest_id}.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )
    _append_event(
        root,
        record_id="OBS-CUR",
        kind=RecordKind.OBSERVATION_BATCH,
        digest=digest,
        payload={
            "schedule_sha256": digest,
            "dataset_manifest_id": dataset_manifest_id,
            "row_count": 1,
        },
        now=WINDOW_START + timedelta(hours=2),
        txn="RESEARCH-TXN-OBS-CURBENCH01",
    )


def plan_shape(history: int) -> dict[str, Any]:
    schedule = _schedule()
    digest = str(schedule["schedule_sha256"])
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "rdp"
        root.mkdir()
        persist_observation_schedule(
            data_root=root,
            schedule=schedule,
            now=datetime(2026, 9, 2, 11, 19, tzinfo=UTC),
            producer_git_sha=PRODUCER,
            activation_id=ACTIVATION_ID,
        )
        predecessor = write_snapshot_unit(
            root,
            utc_day="20260908",
            dataset_manifest_id="pred",
            rows=[_member("pred", admit=WINDOW_START + timedelta(hours=1), digest=digest)],
        )
        predecessor_rel = str(predecessor["publications"][0]["rel"])
        for index in range(history):
            when = WINDOW_START - timedelta(days=history - index, hours=1)
            is_predecessor = index == history - 1
            _append_event(
                root,
                record_id=f"HIST-{index:04d}",
                kind=RecordKind.OBSERVATION_MEMBER_BATCH,
                digest=digest,
                payload={
                    "schedule_sha256": digest,
                    "dataset_manifest_id": "pred" if is_predecessor else f"hist-{index}",
                    "member_location": predecessor_rel
                    if is_predecessor
                    else f"datasets/parquet/hist-{index}/members.parquet",
                    "row_count": 1,
                },
                now=when,
                txn=f"RESEARCH-TXN-MEM-H{index:04d}XXXX",
            )
            _append_event(
                root,
                record_id=f"HIST-OBS-{index:04d}",
                kind=RecordKind.OBSERVATION_BATCH,
                digest=digest,
                payload={
                    "schedule_sha256": digest,
                    "dataset_manifest_id": f"hist-obs-{index}",
                    "row_count": 1,
                },
                now=when,
                txn=f"RESEARCH-TXN-OBS-H{index:04d}XXXX",
            )
        unit = write_snapshot_unit(
            root,
            utc_day="20260910",
            dataset_manifest_id="cur",
            rows=[_member("mint1", admit=WINDOW_START + timedelta(hours=2), digest=digest)],
        )
        _append_event(
            root,
            record_id="MEM-CUR",
            kind=RecordKind.OBSERVATION_MEMBER_BATCH,
            digest=digest,
            payload={
                "schedule_sha256": digest,
                "dataset_manifest_id": "cur",
                "member_location": str(unit["publications"][0]["rel"]),
                "row_count": 1,
            },
            now=WINDOW_START + timedelta(hours=2),
            txn="RESEARCH-TXN-MEM-CURBENCH01",
        )
        _publish_current_observation(root, digest=digest)
        receipt = synthetic_closed_receipt(
            schedule_sha256=digest,
            activation_id=ACTIVATION_ID,
            cohort_id=COHORT_ID,
            as_of=AS_OF,
            members_total=1,
        )
        started = time.perf_counter()
        plan = build_live_observation_source_from_rdp(
            observation_rdp_root=root,
            schedule_sha256=digest,
            activation_id=ACTIVATION_ID,
            cohort_id=COHORT_ID,
            as_of=AS_OF,
            closure_receipt=receipt,
            plan_only=True,
        )
        elapsed_s = time.perf_counter() - started
        if str(plan.get("work_class") or "") != BOUNDED_WORK_CLASS:
            raise SystemExit(f"UNBOUNDED_SHAPE history={history}")
        return {
            "history_depth": history,
            "elapsed_s": round(elapsed_s, 3),
            "work_class": plan["work_class"],
            "research_manifest_headers_scanned": int(
                plan["research_manifest_headers_scanned"]
            ),
            "research_event_partitions_opened": int(
                plan["research_event_partitions_planned"]
            ),
            "research_event_records_decoded": int(plan["research_event_records_decoded"]),
            "research_event_payload_bytes_read": int(
                plan["research_event_payload_bytes_read"]
            ),
            "member_batches_selected": int(plan["member_batches_selected"]),
            "predicted_delta_applications": int(plan["predicted_delta_applications"]),
            "predicted_member_input_bytes": int(plan["predicted_member_input_bytes"]),
            "predicted_observation_input_bytes": int(
                plan["predicted_observation_input_bytes"]
            ),
            "observation_batches_selected": int(plan["observation_batches_selected"]),
            "legacy_member_locations": int(plan["legacy_member_locations"]),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    rows = {label: plan_shape(n) for label, n in (("C3", 3), ("C20", 20), ("C50", 50), ("C100", 100))}
    c3 = rows["C3"]
    c100 = rows["C100"]
    payload_ratio = c100["research_event_payload_bytes_read"] / max(
        c3["research_event_payload_bytes_read"], 1
    )
    member_ratio = c100["member_batches_selected"] / max(c3["member_batches_selected"], 1)
    member_bytes_ratio = c100["predicted_member_input_bytes"] / max(
        c3["predicted_member_input_bytes"], 1
    )
    observation_ratio = c100["predicted_observation_input_bytes"] / max(
        c3["predicted_observation_input_bytes"], 1
    )
    bounded = (
        payload_ratio <= 1.5
        and member_ratio <= 1.5
        and member_bytes_ratio <= 1.5
        and observation_ratio <= 1.5
    )
    verdict = "C100_PAYLOAD_WORK_BOUNDED" if bounded else "C100_SCALING_FAIL"
    document = {
        "verdict": verdict,
        "payload_ratio": payload_ratio,
        "member_ratio": member_ratio,
        "member_bytes_ratio": member_bytes_ratio,
        "observation_ratio": observation_ratio,
        "rows": rows,
    }
    text = json.dumps(document, indent=2, sort_keys=True)
    print(text)
    if args.out is not None:
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0 if verdict == "C100_PAYLOAD_WORK_BOUNDED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
