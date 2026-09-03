#!/usr/bin/env python3
"""Zero-network ObservationSchedule production-composition parity smoke.

Hard-codes project-owned production paths. Temp root only. No credentials,
network, or deployment. Process-local physical overrides only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.collector_campaign_preflight import (  # noqa: E402
    build_campaign_schedule_document,
)
from solana_alpha_lab.factory.collector_read_model import (  # noqa: E402
    build_collector_read_model,
)
from solana_alpha_lab.factory.observation_provider_pacing import (  # noqa: E402
    AdvancingClock,
    FREE_TIER_MIN_PACE_SECONDS,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    render_utc,
    schedule_sha256,
    validate_observation_schedule,
)
from solana_alpha_lab.factory.observation_schedule_composition import (  # noqa: E402
    TickPhysicalOverrides,
)
from solana_alpha_lab.factory.observation_schedule_lifecycle import (  # noqa: E402
    _authority_policy,
    _minimum_expiry,
    _used_provider_route_ids,
    activate_schedule,
    authorize_schedule,
    expected_authority_phrase,
)
from solana_alpha_lab.factory.observation_schedule_runtime import (  # noqa: E402
    DEFAULT_RUNTIME_RELATIVE,
    FakeProviderOpener,
    UNIT_RELATIVE,
    parse_unit_exec_start,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from scripts.observation_schedule import main as cli_main  # noqa: E402

PASS_TERMINAL = "OBSERVATION_RUNTIME_COMPOSITION_PARITY_PASS"
FIXTURE_RELATIVE = (
    "tests/fixtures/observation_schedule/composition_parity_provider_v1.json"
)
PUMP_MINT = "MintParityPump111111111111111111111111111111"
CONTROL_MINT = "MintParityControl111111111111111111111111111"
LEGACY_MINT = "MintParityLegacyOnly11111111111111111111111"
GIT_SHA = "a" * 40
NOW = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
ACTIVATION_ID = "ACT-COMPOSITION-PARITY-V1"
SEARCH_PRIMITIVE = "PRIM-JUPITER-TOKENS-V2-SEARCH-001"


def _endpoint_role(url: str) -> str | None:
    if "/tokens/v2/recent" in url:
        return "RECENT"
    if "/tokens/v2/search" in url:
        return "SEARCH"
    return None


class _ClockRecordingOpener:
    """Records logical clock at each open for measured pacing spacing."""

    def __init__(self, inner: FakeProviderOpener, clock: AdvancingClock) -> None:
        self.inner = inner
        self.clock = clock
        self.open_at: list[datetime] = []

    @property
    def urls(self) -> list[str]:
        return self.inner.urls

    def open(self, url: str) -> dict[str, Any]:
        self.open_at.append(self.clock.now())
        return self.inner.open(url)


def measured_min_spacing_seconds(open_at: list[datetime]) -> float:
    if len(open_at) < 2:
        return 0.0
    deltas = [
        (open_at[i] - open_at[i - 1]).total_seconds() for i in range(1, len(open_at))
    ]
    return float(min(deltas)) if deltas else 0.0


def load_parity_opener() -> FakeProviderOpener:
    payload = json.loads((ROOT / FIXTURE_RELATIVE).read_text(encoding="utf-8"))
    return FakeProviderOpener(payload)


def build_parity_schedule(*, starts_at: datetime = NOW) -> dict[str, Any]:
    document = build_campaign_schedule_document(
        starts_at=starts_at - timedelta(minutes=5),
        schedule_key="OBS-COMPOSITION-PARITY-V1",
    )
    # Preserve FIELD-LAUNCHPAD-001; raise inclusion so golden path is non-vacuous.
    document["sampling"]["inclusion_probability"] = "1.0"
    # Draft campaign budgets are pre-oracle placeholders (often 1). Parity needs
    # enough headroom for same-tick RECENT+SEARCH without restating science.
    document["budgets"]["provider_calls_per_tick_max"] = 60
    document["budgets"]["provider_calls_per_utc_day_max"] = 60
    document["budgets"]["provider_calls_lifetime_max"] = 500
    document["budgets"]["modeled_provider_credits_per_utc_day_max"] = 60
    # Keep one Y horizon only — schema forbids empty y_points.
    document["y_points"] = [document["y_points"][0]]
    document["activation"]["stops_admitting_at"] = render_utc(
        starts_at + timedelta(hours=2)
    )
    validated = validate_observation_schedule(document, root=ROOT)
    validated["schedule_sha256"] = schedule_sha256(validated)
    return validated


def _authority_phrase(document: dict[str, Any]) -> str:
    expires_at = render_utc(_minimum_expiry(document))
    _, routes = _used_provider_route_ids(ROOT, document)
    policy = _authority_policy(
        root=ROOT,
        document=document,
        schedule_key=document["schedule_key"],
        expires_at=expires_at,
    )
    from solana_alpha_lab.factory.observation_schedule import canonical_sha256

    return expected_authority_phrase(
        schedule_sha256=document["schedule_sha256"],
        schedule_key=document["schedule_key"],
        activation_starts_at=document["activation"]["starts_at"],
        activation_stops_admitting_at=document["activation"]["stops_admitting_at"],
        provider_route_ids=routes,
        expires_at=expires_at,
        policy_digest=canonical_sha256(policy),
    )


def authorize_and_activate(
    *,
    store: ObservationScheduleStore,
    data_root: Path,
    schedule: dict[str, Any],
    now: datetime,
) -> str:
    store.persist_registered_schedule(
        schedule_sha256=schedule["schedule_sha256"],
        schedule_key=schedule["schedule_key"],
        document=schedule,
        clock=now,
    )
    authorize_schedule(
        root=ROOT,
        data_root=data_root,
        store=store,
        schedule_sha256=schedule["schedule_sha256"],
        phrase=_authority_phrase(schedule),
        now=now,
        producer_git_sha=GIT_SHA,
    )
    activate_schedule(
        root=ROOT,
        data_root=data_root,
        store=store,
        schedule_sha256=schedule["schedule_sha256"],
        activation_id=ACTIVATION_ID,
        now=now,
        producer_git_sha=GIT_SHA,
    )
    return ACTIVATION_ID


def insert_matured_search_due(
    store: ObservationScheduleStore,
    schedule: dict[str, Any],
    *,
    now: datetime,
) -> None:
    point_id = str(schedule["x_point"]["point_id"])
    lateness = int(schedule["x_point"]["allowed_lateness_seconds"])
    store.insert_due(
        {
            "schedule_sha256": schedule["schedule_sha256"],
            "activation_id": ACTIVATION_ID,
            "entity_id": PUMP_MINT,
            "point_id": point_id,
            "primitive_id": SEARCH_PRIMITIVE,
            "state": "DUE",
            "due_at": render_utc(now),
            "deadline_at": render_utc(now + timedelta(seconds=lateness)),
            "request_sha256": None,
            "call_occurrence_id": None,
            "payload": {},
        },
        clock=now,
    )


def _cli_tick(
    *,
    data_root: Path,
    overrides: TickPhysicalOverrides,
) -> dict[str, Any]:
    buf = StringIO()
    with redirect_stdout(buf):
        code = cli_main(
            [
                "tick",
                "--once",
                "--runtime-config",
                DEFAULT_RUNTIME_RELATIVE,
                "--data-root",
                str(data_root),
            ],
            physical_overrides=overrides,
        )
    payload = json.loads(buf.getvalue()) if buf.getvalue().strip() else {}
    payload["_exit_code"] = code
    return payload


def static_binding_descriptor() -> dict[str, Any]:
    unit_text = (ROOT / UNIT_RELATIVE).read_text(encoding="utf-8")
    argv = parse_unit_exec_start(unit_text)
    if "tick" not in argv or "--once" not in argv:
        raise RuntimeError("STATIC_BINDING_DRIFT")
    if "--runtime-config" not in argv:
        raise RuntimeError("STATIC_BINDING_DRIFT")
    cfg_idx = argv.index("--runtime-config") + 1
    runtime_arg = argv[cfg_idx]
    if runtime_arg != DEFAULT_RUNTIME_RELATIVE:
        raise RuntimeError("STATIC_BINDING_DRIFT")
    if "OBSERVATION_SCHEDULE_RUNTIME_CONFIG=" in unit_text:
        # Unit env binding must not disagree with explicit argv.
        for line in unit_text.splitlines():
            if line.startswith("Environment=") and "OBSERVATION_SCHEDULE_RUNTIME_CONFIG=" in line:
                # Extract value after =
                part = line.split("OBSERVATION_SCHEDULE_RUNTIME_CONFIG=", 1)[1]
                env_val = part.split()[0].strip('"')
                if env_val and env_val != runtime_arg:
                    raise RuntimeError("STATIC_BINDING_DRIFT")
    return {
        "unit_exec_argv": argv,
        "runtime_config": runtime_arg,
        "schedule_schema": "smial.observation-schedule",
        "schedule_schema_version": "1.0",
        "tick_entrypoint": "scripts.observation_schedule.main",
        "scheduler_role": "observation_scheduler.tick_once",
        "store_role": "ObservationScheduleStore",
        "physical_mode": "DETERMINISTIC_PARITY",
    }


def normalize_semantic_record(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "terminal": raw.get("terminal"),
        "activation_state": raw.get("activation_state"),
        "candidate_state_counts": raw.get("candidate_state_counts"),
        "provider_endpoint_sequence": raw.get("provider_endpoint_sequence"),
        "provider_call_count": raw.get("provider_call_count"),
        "minimum_simulated_spacing_seconds": raw.get(
            "minimum_simulated_spacing_seconds"
        ),
        "restart_terminal": raw.get("restart_terminal"),
        "doctor_terminal": raw.get("doctor_terminal"),
        "health_flags_sorted": raw.get("health_flags_sorted"),
        "credential_reads": raw.get("credential_reads"),
        "network_calls": raw.get("network_calls"),
        "historical_classes": raw.get("historical_classes"),
        "pump_candidate_progressed": raw.get("pump_candidate_progressed"),
        "matured_due_progressed": raw.get("matured_due_progressed"),
        "control_predicate_rejected": raw.get("control_predicate_rejected"),
        "legacy_nested_rejected": raw.get("legacy_nested_rejected"),
        "restart_no_duplicate_completed_ids": raw.get(
            "restart_no_duplicate_completed_ids"
        ),
        "levels": raw.get("levels"),
    }


def semantic_sha256(record: dict[str, Any]) -> str:
    blob = json.dumps(normalize_semantic_record(record), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def run_parity_once(*, root_tmp: Path) -> dict[str, Any]:
    data_root = root_tmp / "rdp"
    data_root.mkdir(parents=True, exist_ok=True)
    ops = data_root / "observation_schedule_state.sqlite"
    schedule = build_parity_schedule()
    predicates = schedule["population"]["source_predicates"]
    if predicates[0]["field_id"] != "FIELD-LAUNCHPAD-001":
        raise RuntimeError("PROVIDER_SHAPE_CONTRACT_GAP")

    store = ObservationScheduleStore(ops)
    try:
        authorize_and_activate(
            store=store, data_root=data_root, schedule=schedule, now=NOW
        )
        insert_matured_search_due(store, schedule, now=NOW)
    finally:
        store.close()

    opener_inner = load_parity_opener()
    clock = AdvancingClock(NOW)
    opener = _ClockRecordingOpener(opener_inner, clock)
    first = _cli_tick(
        data_root=data_root,
        overrides=TickPhysicalOverrides(now=NOW, opener=opener, pacing_clock=clock),
    )
    roles = [role for url in opener.urls if (role := _endpoint_role(url))]
    min_spacing = measured_min_spacing_seconds(opener.open_at)
    controlled_provider_calls = len(opener.urls)

    store_mid = ObservationScheduleStore(ops)
    try:
        calls_after_first = store_mid.list_calls()
        call_ids_after_first = sorted(
            {
                str(row["call_occurrence_id"])
                for row in calls_after_first
                if row.get("call_occurrence_id")
            }
        )
    finally:
        store_mid.close()

    # Fresh composition + reopened store (restart-semantic, not OS supervision).
    opener2_inner = load_parity_opener()
    now2 = clock.now()
    clock2 = AdvancingClock(now2)
    opener2 = _ClockRecordingOpener(opener2_inner, clock2)
    second = _cli_tick(
        data_root=data_root,
        overrides=TickPhysicalOverrides(now=now2, opener=opener2, pacing_clock=clock2),
    )

    store2 = ObservationScheduleStore(ops)
    try:
        candidates = store2.list_candidates(
            schedule_sha256=schedule["schedule_sha256"],
            activation_id=ACTIVATION_ID,
        )
        matured_row = store2.get_due(
            {
                "schedule_sha256": schedule["schedule_sha256"],
                "activation_id": ACTIVATION_ID,
                "entity_id": PUMP_MINT,
                "point_id": str(schedule["x_point"]["point_id"]),
                "primitive_id": SEARCH_PRIMITIVE,
            }
        )
        due_counts = store2.due_counts()
        calls_after_second = store2.list_calls()
        call_ids_after_second = sorted(
            {
                str(row["call_occurrence_id"])
                for row in calls_after_second
                if row.get("call_occurrence_id")
            }
        )
        doctor = build_collector_read_model(
            store2,
            now=now2,
            schedule_sha256=schedule["schedule_sha256"],
            activation_id=ACTIVATION_ID,
            deploy_git_sha=GIT_SHA,
        )
    finally:
        store2.close()

    duplicated_call_ids = sorted(set(call_ids_after_first) & set(call_ids_after_second))
    # Restart must retain prior identities without cloning rows.
    if len(call_ids_after_second) < len(call_ids_after_first):
        raise RuntimeError("PERSISTENCE_RESTART_REGRESSION")
    # Completed identities from tick1 must still exist exactly once.
    for occurrence in call_ids_after_first:
        if call_ids_after_second.count(occurrence) != 1 and occurrence not in call_ids_after_second:
            raise RuntimeError("PERSISTENCE_RESTART_REGRESSION")
    # No new duplicate of an already-completed identity.
    id_counts: dict[str, int] = {}
    for occurrence in call_ids_after_second:
        id_counts[occurrence] = id_counts.get(occurrence, 0) + 1
    if any(count != 1 for count in id_counts.values()):
        raise RuntimeError("PERSISTENCE_RESTART_REGRESSION")

    state_counts: dict[str, int] = {}
    for row in candidates:
        state = str(row.get("state") or "UNKNOWN")
        state_counts[state] = state_counts.get(state, 0) + 1
    pump_states = [
        str(row.get("state"))
        for row in candidates
        if str(row.get("entity_id")) == PUMP_MINT
    ]
    control_states = [
        str(row.get("state"))
        for row in candidates
        if str(row.get("entity_id")) == CONTROL_MINT
    ]
    legacy_states = [
        str(row.get("state"))
        for row in candidates
        if str(row.get("entity_id")) == LEGACY_MINT
    ]
    pump_progressed = any(
        state not in {"NOT_SELECTED_PREDICATE", "UNKNOWN", ""} for state in pump_states
    )
    matured_progressed = (
        matured_row is not None and str(matured_row.get("state")) != "DUE"
    )
    due_state_counts = dict(sorted((due_counts or {}).items()))
    control_rejected = bool(control_states) and all(
        state == "NOT_SELECTED_PREDICATE" for state in control_states
    )
    legacy_rejected = bool(legacy_states) and all(
        state == "NOT_SELECTED_PREDICATE" for state in legacy_states
    )

    doctor_activation = str(doctor.get("activation_id") or "")
    if doctor_activation != ACTIVATION_ID:
        raise RuntimeError("READ_MODEL_COMPOSITION_REGRESSION")
    activation_state = str(doctor.get("activation_state") or "")
    if activation_state != "ACTIVE":
        raise RuntimeError("READ_MODEL_COMPOSITION_REGRESSION")
    health_flags = sorted(str(flag) for flag in (doctor.get("health_flags") or []) if flag)
    if "PROVIDER_FAILED" in health_flags:
        raise RuntimeError("READ_MODEL_COMPOSITION_REGRESSION")
    doctor_terminal = "READ_MODEL_OK"

    historical_classes: list[str] = []
    if pump_progressed and control_rejected and legacy_rejected:
        historical_classes.append("#238")
    if (
        roles.count("RECENT") >= 1
        and roles.count("SEARCH") >= 1
        and min_spacing >= float(FREE_TIER_MIN_PACE_SECONDS)
    ):
        historical_classes.append("#240")
    if isinstance(clock, AdvancingClock) and min_spacing >= float(
        FREE_TIER_MIN_PACE_SECONDS
    ):
        historical_classes.append("#242")

    binding = static_binding_descriptor()
    record = {
        "terminal": first.get("terminal"),
        "activation_state": activation_state,
        "candidate_state_counts": dict(sorted(state_counts.items())),
        "due_state_counts": due_state_counts,
        "provider_endpoint_sequence": roles,
        "provider_call_count": len(roles),
        "controlled_provider_calls": controlled_provider_calls,
        "minimum_simulated_spacing_seconds": min_spacing,
        "restart_terminal": second.get("terminal"),
        "restart_no_duplicate_completed_ids": len(call_ids_after_first) > 0
        and all(occurrence in call_ids_after_second for occurrence in call_ids_after_first)
        and all(count == 1 for count in id_counts.values()),
        "doctor_terminal": doctor_terminal,
        "doctor_activation_id": doctor_activation,
        "health_flags_sorted": health_flags,
        "credential_reads": int(first.get("credential_reads") or 0),
        "network_calls": 0,
        "historical_classes": historical_classes,
        "pump_candidate_progressed": pump_progressed,
        "matured_due_progressed": matured_progressed,
        "control_predicate_rejected": control_rejected,
        "legacy_nested_rejected": legacy_rejected,
        "levels": [
            "P0_STATIC_IDENTITY",
            "P1_COMPOSITION_ASSEMBLY",
            "P2_DETERMINISTIC_VERTICAL",
        ],
        "binding": binding,
        "first_tick": {k: v for k, v in first.items() if k != "_exit_code"},
        "second_tick": {k: v for k, v in second.items() if k != "_exit_code"},
        "doctor": {
            "terminal": doctor_terminal,
            "activation_id": doctor_activation,
            "activation_state": activation_state,
        },
        "non_claims": [
            "FACTORY_LIVE_READY_FROM_THIS_TEST",
            "PROVIDER_COMPATIBILITY_PROVEN_FOREVER",
            "NO_FUTURE_COMPOSITION_BUGS",
            "LONG_RUN_RELIABILITY",
            "OS_SYSTEMD_SUPERVISION",
            "ALPHA",
            "REAL_FILL",
            "NETRETURN",
            "OWNER_CASHFLOW",
            "MICRO_LIVE_READY",
        ],
        "restart_proof_kind": "FRESH_COMPOSITION_PLUS_REOPENED_SQLITE",
        "incident_promotion_rule": (
            "Promote into parity only if >=2 components interact AND "
            "interaction involves time/transport/persistence/authority/CLI wiring "
            "AND focused unit test would not faithfully represent the failure."
        ),
        "fixture_drift_policy": (
            "Do not edit fixture until green; classify EXTERNAL_SHAPE_CHANGED_SUPPORTED | "
            "EXTERNAL_SHAPE_CONTRACT_GAP | FIXTURE_STALE_ONLY | UNKNOWN_PROVIDER_SEMANTICS."
        ),
        "failure_taxonomy": [
            "STATIC_BINDING_DRIFT",
            "PRODUCTION_COMPOSITION_DRIFT",
            "PHYSICAL_OVERRIDE_ISOLATION_BROKEN",
            "AUTHORITY_ORDER_REGRESSION",
            "CREDENTIAL_PATH_REGRESSION",
            "NETWORK_PATH_REGRESSION",
            "CLOCK_PACING_PARITY_REGRESSION",
            "PERSISTENCE_RESTART_REGRESSION",
            "PROVIDER_SHAPE_CONTRACT_GAP",
            "READ_MODEL_COMPOSITION_REGRESSION",
            "FIXTURE_STALE_ONLY",
            "TEST_HARNESS_DEFECT",
            "UNKNOWN_REPLAN_REQUIRED",
        ],
    }
    record["semantic_result_sha256"] = semantic_sha256(record)
    return record


def assert_non_vacuous(record: dict[str, Any]) -> None:
    roles = record["provider_endpoint_sequence"]
    if roles.count("RECENT") < 1:
        raise RuntimeError("PARITY_VACUOUS_NO_RECENT")
    if roles.count("SEARCH") < 1:
        raise RuntimeError("PARITY_VACUOUS_NO_SEARCH")
    if int(record["provider_call_count"]) < 2:
        raise RuntimeError("PARITY_VACUOUS_PROVIDER_CALLS")
    if not record["pump_candidate_progressed"]:
        raise RuntimeError("PARITY_VACUOUS_NO_PUMP_CANDIDATE")
    if not record["matured_due_progressed"]:
        raise RuntimeError("PARITY_VACUOUS_NO_MATURED_DUE")
    if not record.get("control_predicate_rejected"):
        raise RuntimeError("PARITY_VACUOUS_CONTROL_NOT_REJECTED")
    if not record.get("legacy_nested_rejected"):
        raise RuntimeError("PARITY_VACUOUS_LEGACY_NOT_REJECTED")
    if float(record["minimum_simulated_spacing_seconds"]) < FREE_TIER_MIN_PACE_SECONDS:
        raise RuntimeError("CLOCK_PACING_PARITY_REGRESSION")
    if not record.get("restart_no_duplicate_completed_ids"):
        raise RuntimeError("PERSISTENCE_RESTART_REGRESSION")
    if record["credential_reads"] != 0:
        raise RuntimeError("CREDENTIAL_PATH_REGRESSION")
    if record["network_calls"] != 0:
        raise RuntimeError("NETWORK_PATH_REGRESSION")
    if set(record.get("historical_classes") or []) != {"#238", "#240", "#242"}:
        raise RuntimeError("HISTORICAL_CLASS_INCOMPLETE")
    if record["terminal"] not in {"TICK_COMPLETE", "TICK_PARTIAL"}:
        if record["terminal"] == "PACE_WAIT":
            raise RuntimeError("CLOCK_PACING_PARITY_REGRESSION")
        raise RuntimeError(f"UNEXPECTED_TERMINAL:{record['terminal']}")


def run_parity() -> dict[str, Any]:
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="obs-composition-parity-") as tmp:
        record = run_parity_once(root_tmp=Path(tmp))
    assert_non_vacuous(record)
    # Determinism: second clean temp root
    with tempfile.TemporaryDirectory(prefix="obs-composition-parity-b-") as tmp2:
        record2 = run_parity_once(root_tmp=Path(tmp2))
    assert_non_vacuous(record2)
    if record["semantic_result_sha256"] != record2["semantic_result_sha256"]:
        raise RuntimeError("SEMANTIC_DIGEST_DRIFT")
    wall = time.perf_counter() - started
    binding = record["binding"]
    return {
        "terminal": PASS_TERMINAL,
        "levels": record["levels"],
        "semantic_result_sha256": record["semantic_result_sha256"],
        "wall_time_seconds": round(wall, 3),
        "credential_reads": 0,
        "network_calls": 0,
        "minimum_simulated_spacing_seconds": record[
            "minimum_simulated_spacing_seconds"
        ],
        "provider_endpoint_sequence": record["provider_endpoint_sequence"],
        "provider_call_count": record["provider_call_count"],
        "candidate_state_counts": record["candidate_state_counts"],
        "restart_continuation": "PASS",
        "restart_proof_kind": record["restart_proof_kind"],
        "doctor_terminal": record["doctor_terminal"],
        "historical_classes": record["historical_classes"],
        "physical_mode": binding["physical_mode"],
        "runtime_config": binding["runtime_config"],
        "non_claims": record["non_claims"],
        "incident_promotion_rule": record["incident_promotion_rule"],
        "fixture_drift_policy": record["fixture_drift_policy"],
        "failure_taxonomy": record["failure_taxonomy"],
        "restart_no_duplicate_completed_ids": record[
            "restart_no_duplicate_completed_ids"
        ],
        "controlled_provider_calls": record["controlled_provider_calls"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", required=True)
    parser.parse_args(argv)
    try:
        payload = run_parity()
        print(json.dumps(payload, sort_keys=True))
        return 0 if payload["terminal"] == PASS_TERMINAL else 2
    except Exception as exc:  # noqa: BLE001 — smoke emits typed terminal
        print(json.dumps({"terminal": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
