"""Controlled market ingress only. No science carriers or result fixtures."""
from __future__ import annotations

import copy
import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from solana_alpha_lab.factory.list_a_confirmation_inputs import write_native_confirmation_sample, register_source_authority
from solana_alpha_lab.factory.list_a_confirmation_method import digest
from solana_alpha_lab.factory.opportunity_episodes import (
    build_frame, frame_receipt, inventory_from_documents, cycle_start, episode_id_for, resolve_point,
    validate_episode_schedule, admission_record,
)

NOW = datetime(2027, 1, 4, tzinfo=UTC)


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def ingress(root: Path, store, case: str = "POSITIVE", *, missing_a: int = 0, source_id="SYNTH-LIST-A-V1", origin_label=None,
            t0_shift_seconds: int = 0, data_cutoff: str | None = None, interval_end_exclusive: str | None = None):
    schedule = yaml.safe_load((root / "configs/opportunity_episodes_jupiter_core_v1.yaml").read_text(encoding="utf-8"))
    schedule = copy.deepcopy(schedule)
    schedule["activation"] = {"starts_at": "2026-11-02T00:00:00Z", "stops_admitting_at": "2027-01-04T00:00:00Z"}
    assignment = {"schema": "smial.protected-identity-assignment", "schema_version": "1.0",
                  "assignment_id": "SYNTHETIC-NATIVE-CAPTURE", "interpretation_version": "1",
                  "completeness": {"complete": True}, "entries": []}
    inventory = inventory_from_documents([assignment])
    schedule["protection"]["assignment_sources"] = [{"assignment_id": assignment["assignment_id"], "sha256": digest(assignment)}]
    schedule = validate_episode_schedule(schedule, root=root)
    sb = {**schedule["observation_schedule"], "witness_max_age_seconds": schedule["nomination"]["witness_max_age_seconds"]}
    census, observations, frames, oracle, admissions = [], [], {}, [], []
    missing_left = missing_a
    for day in range(32):
        for slot in range(8):
            t0 = datetime(2026, 11, 2, 0, 15, tzinfo=UTC) + timedelta(days=day * 2, minutes=slot * 15, seconds=t0_shift_seconds)
            group = "A" if slot < 4 else "C"
            label = f"D{day:02d}S{slot}"
            if day == 4 and slot == 0:
                label = "D00S0"  # lawful repeated mint after eight days, new cycle/episode
            origin = hashlib.sha256((origin_label or source_id).encode()).hexdigest()[:8]
            mint = ("Synth" + origin + label + "1" * 44)[:44]
            native_id = episode_id_for(lineage_id=source_id, cycle=cycle_start(t0), mint=mint)
            token = {"id": mint, "name": "Synthetic", "symbol": "SYN", "decimals": 6,
                "tags": ["community"], "firstPool": {"createdAt": "2026-11-01T00:00:00Z"},
                "usdPrice": 8, "liquidity": 12000, "holderCount": 60}
            results = []
            for category in schedule["nomination"]["sources"]:
                membership = (("toporganicscore_5m",), ("toporganicscore_5m", "toptraded_5m"),
                    ("toporganicscore_5m", "toptrending_5m"), ("toporganicscore_5m", "toptraded_5m", "toptrending_5m"),
                    ("toptraded_5m",), ("toptrending_5m",), ("toptraded_5m", "toptrending_5m"), ("toptraded_5m",))
                present = category["source_id"] in membership[slot]
                results.append({"source_id": category["source_id"], "status": "OBSERVED", "body": [token] if present else [],
                    "response_received_at": stamp(t0), "first_reliable_available_at": stamp(t0),
                    "call_occurrence_id": digest([origin_label or source_id, day, slot, category]),
                    "request_sha256": digest([category, stamp(t0)]), "request_started_at": stamp(t0 - timedelta(seconds=1)),
                    "response_sha256": digest([token] if present else [])})
            frame = build_frame(document=schedule, activation_id="ACT-SYNTH-LIST-A", round_started_at=t0,
                                source_results=results, inventory=inventory)
            receipt = frame_receipt(frame)
            frames[receipt["round_id"]] = receipt
            candidate = next(c for c in frame["candidates"] if c["mint"] == mint)
            admission = admission_record(document=schedule, activation_id="ACT-SYNTH-LIST-A", lineage_id=source_id,
                cycle=cycle_start(t0), mint=mint, t0=t0, ticket_priority_value=digest([source_id,native_id]),
                candidate=candidate, frame_sha256=receipt["frame_sha256"], protection_fingerprint=inventory.fingerprint(),
                round_id_value=receipt["round_id"])
            admissions.append(admission)
            row = {"episode_id": native_id, "mint": mint, "t0": stamp(t0), "cohort_id": admission["cohort_id"],
                   "evidence_role": "UNTOUCHED_FORWARD_HOLDOUT", "confirmatory_reuse_forbidden": False,
                   "release_id": "RELEASE-" + source_id, "round_id": receipt["round_id"], "frame_sha256": receipt["frame_sha256"],
                   "admission_request_started_at": stamp(t0 - timedelta(seconds=1)),
                   "admission_response_received_at": stamp(t0), "admission_first_reliable_available_at": stamp(t0)}
            census.append(row)
            missing = group == "A" and missing_left > 0
            if missing:
                missing_left -= 1
            oracle.append({"episode_id": native_id, "mint": mint, "group": group, "missing": missing,
                           "decision_nominal_due": (t0 + timedelta(seconds=1800)).isoformat()})
            for point in ("E1800", "E14400"):
                window = resolve_point(sb, t0, point)
                request = window.request_not_before
                price = "9" if point == "E14400" and group == "A" and case != "NULL" else "8"
                state = "MISSING_TYPED" if (point == "E14400" and (missing or case == "MISSING_ALL_TARGETS")) or (
                    point == "E1800" and group == "A" and case == "EMPTY_DECISION_A") else "OBSERVED"
                observations.append({"episode_id": native_id, "mint": mint, "cohort_id": row["cohort_id"], "release_id": row["release_id"],
                    "evidence_role": "UNTOUCHED_FORWARD_HOLDOUT", "confirmatory_reuse_forbidden": False,
                    "point_id": point, "field_id": "FIELD-USD-PRICE-001", "state": state,
                    "typed_value": price if state == "OBSERVED" else None,
                    "observation_clock_policy": "PROVIDER_REPORTED_SNAPSHOT_V1", "source_price_event_time": "UNKNOWN",
                    "primitive_id": "PRIM-JUPITER-TOKENS-V2-SEARCH-001", "call_occurrence_id": digest([source_id, native_id, point]),
                    "request_sha256": digest([mint, point]), "request_started_at": stamp(request),
                    "response_received_at": stamp(request + timedelta(seconds=1)),
                    "first_reliable_available_at": stamp(request + timedelta(seconds=2))})
    exposure = {"source_ids": [source_id], "ancestors": [], "inventory_complete": True,
        "confirmatory_reuse_forbidden": False, "empirical_development": False,
        "preregistered_at": "2026-10-14T00:00:00Z", "prior_exposure_end": "2026-10-14T00:00:00Z",
        "development_decision_max": None, "development_target_available_max": None}
    sample = write_native_confirmation_sample(root=root, store=store, source_id=source_id, lineage_id=source_id,
        namespace=source_id, census=census, observations=observations, schedule=schedule, frames=frames,
        admission_documents=admissions, protection_documents=[assignment],
        interval_start="2026-11-02T00:00:00Z", interval_end_exclusive=interval_end_exclusive or "2027-01-04T00:00:00Z",
        information_start="2026-11-02T00:00:00Z", data_cutoff=data_cutoff or NOW.isoformat(), exposure=exposure, domain="SYNTHETIC")
    proposal = register_source_authority(sample, root=root, store=store)
    register_source_authority(sample, root=root, store=store, owner_phrase=proposal["owner_phrase"])
    return sample, oracle
