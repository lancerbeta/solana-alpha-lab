"""OPPORTUNITY_EPISODES three-process vertical proof (D4, D6–D9, D11).

P1 capture host: production ticks through scripts/observation_schedule.py::main,
then capture_freeze_export packets. P2 workstation: CLI consume over a
filesystem transport, a legacy cohort alongside, ordinary Forge lifecycle,
exact repeat and the next run on new evidence. P3 cold: a relocated copy with
network and every original root forbidden; saved readback and registered
numerical replay. Expected values are literals of the authored market.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

PRICE, LIQ, HOLD = "FIELD-USD-PRICE-001", "FIELD-LIQUIDITY-USD-001", "FIELD-HOLDER-COUNT-001"
DAY_A = datetime(2026, 10, 8, tzinfo=UTC)  # Thursday, cycle 2026-10-05
DAY_T = datetime(2026, 10, 11, tzinfo=UTC)  # Sunday, same cycle, tiny cohort
DAY_B = datetime(2026, 10, 12, tzinfo=UTC)  # Monday, next cycle
STOPS = DAY_B + timedelta(hours=3)
END = datetime(2026, 10, 15, 4, 0, 5, tzinfo=UTC)
AS_OF = datetime(2026, 10, 15, 6, 0, tzinfo=UTC)
SKIPPED_TICK = datetime(2026, 10, 8, 4, 35, 5, tzinfo=UTC)  # A2 E14400 slot
FOCUS = "OPPORTUNITY_EPISODES:VERTICAL_SYNTH_FOCUS"


def mints() -> dict[str, list[str]]:
    from tests.test_opportunity_episodes_harness_v1 import synth_mint

    a = [synth_mint(f"VA{i}x") for i in range(12)]
    b = [a[0]] + [synth_mint(f"VB{i}x") for i in range(1, 12)]
    return {"A": a, "B": b, "T": [synth_mint("VTiny")]}


def admission_rounds() -> dict[tuple[str, int], tuple[str, datetime]]:
    rounds: dict[tuple[str, int], tuple[str, datetime]] = {}
    m = mints()
    for i in range(12):
        rounds[("A", i)] = (m["A"][i], DAY_A + timedelta(minutes=15 * i))
        rounds[("B", i)] = (m["B"][i], DAY_B + timedelta(minutes=15 * i))
    rounds[("T", 0)] = (m["T"][0], DAY_T)
    return rounds


def market_row(mint: str, now: datetime, signal: bool, admitted_round: datetime, *, tiny: bool) -> dict[str, Any] | None:
    from tests.test_opportunity_episodes_harness_v1 import token_object

    offset = (now - admitted_round).total_seconds()
    if tiny and offset >= 15 * 60:
        return None  # disappears before its decision point
    if offset < 15 * 60:
        price, holders = 1.00, 60
    elif offset < 2 * 3600:
        price, holders = (1.02, 75) if signal else (0.98, 58)
    else:
        price, holders = (1.122, 80) if signal else (0.931, 55)
    return token_object(mint, price=price, liquidity=12000 if offset >= 15 * 60 else 10000, holders=holders)


def build_market():
    from tests.test_opportunity_episodes_harness_v1 import SyntheticMarket, token_object

    market = SyntheticMarket()
    rounds = admission_rounds()
    by_mint: dict[str, list[tuple[datetime, bool, bool]]] = {}
    for (cohort, index), (mint, start) in rounds.items():
        market.nominations[start] = {
            "toporganicscore": [token_object(mint, price=1.0, liquidity=10000, holders=60)],
            "toptraded": [],
            "toptrending": [],
        }
        by_mint.setdefault(mint, []).append((start, index % 2 == 0 and cohort != "T", cohort == "T"))
    for mint, entries in by_mint.items():
        entries.sort()

        def series(now, entries=entries, mint=mint):
            latest = [item for item in entries if item[0] <= now]
            if not latest:
                return None
            start, signal, tiny = latest[-1]
            return market_row(mint, now, signal, start, tiny=tiny)

        market.series[mint] = series
    return market


def tick_times() -> list[datetime]:
    """Only the instants the proof needs; every other slot terminalizes as an explicit gap.

    A round at grid instant s commits T0 a few seconds later, so point offset o is
    assigned to the next 5-minute grid instant s + o + 300 and dispatched by the
    tick five seconds after it. The sparse tail lets every 72 h obligation expire.
    """

    times: set[datetime] = set()
    for _key, (_mint, start) in admission_rounds().items():
        times.add(start + timedelta(seconds=5))
        for offset in (300, 1800, 14400):
            times.add(start + timedelta(seconds=offset + 300 + 5))
    cursor = DAY_A + timedelta(hours=12, seconds=5)
    while cursor < END:
        times.add(cursor)
        cursor += timedelta(hours=12)
    times.add(END)
    return [item for item in sorted(times) if item != SKIPPED_TICK]


def peak_rss_bytes() -> int | None:
    """OS peak resident set of this process (workstation measurement only)."""

    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = Counters()
            counters.cb = ctypes.sizeof(Counters)
            kernel = ctypes.windll.kernel32
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            kernel.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
            if kernel.K32GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                return int(counters.PeakWorkingSetSize)
            return None
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) * 1024
    except Exception:
        return None
    return None


def tree_bytes(path: Path, *, include=None) -> int:
    total = 0
    if not path.exists():
        return 0
    for item in path.rglob("*"):
        if item.is_file() and (include is None or include(item)):
            total += item.stat().st_size
    return total


# --------------------------------------------------------------------------
# P1: capture host


def phase_p1(work: Path) -> dict[str, Any]:
    from solana_alpha_lab.factory.live_cohort_vanilla_path import capture_freeze_export
    from tests.test_opportunity_episodes_harness_v1 import cli_tick, register_authorize_activate, build_schedule, write_assignment

    data_root = work / "p1" / "rdp"
    data_root.mkdir(parents=True)
    assignment = write_assignment(data_root, [])
    schedule = build_schedule(starts_at=DAY_A, stops_at=STOPS, assignment=assignment)
    register_authorize_activate(data_root, schedule, now=DAY_A)
    market = build_market()
    terminals: dict[str, int] = {}
    completed_before = None
    started = time.perf_counter()
    times = tick_times()
    for at in times:
        result = cli_tick(data_root, market, at)
        terminals[str(result.get("terminal"))] = terminals.get(str(result.get("terminal")), 0) + 1
        if result.get("terminal") == "TICK_REFUSED_NO_LIVE_DEFAULT":
            completed_before = at  # every obligation is terminal; the activation is COMPLETE
            break
        if result.get("_exit_code") != 0:
            raise AssertionError(f"tick failed at {at}: {result}")
    tick_wall = time.perf_counter() - started
    imported: set[str] = set()
    packets = []
    for _index in range(3):
        packet = capture_freeze_export(
            observation_rdp=data_root,
            ops_store=data_root / "observation_schedule_state.sqlite",
            imported_cohort_ids=set(imported),
            as_of=AS_OF,
            collection="OPPORTUNITY_EPISODES",
        )
        path = work / "p1" / f"packet-{packet['cohort_id']}.json"
        path.write_text(json.dumps(packet, default=str), encoding="utf-8")
        packets.append(str(path))
        imported.add(str(packet["cohort_id"]))
    import sqlite3

    ops = data_root / "observation_schedule_state.sqlite"
    connection = sqlite3.connect(ops)
    try:
        states = dict(connection.execute("SELECT state, COUNT(*) FROM due_observations GROUP BY state").fetchall())
        admissions = [json.loads(row[0]) for row in connection.execute("SELECT record_json FROM episode_admissions ORDER BY t0")]
        activation_state = connection.execute("SELECT state FROM schedule_activations").fetchone()[0]
    finally:
        connection.close()
    return {
        "ticks": sum(terminals.values()),
        "completed_before": completed_before,
        "tick_terminals": terminals,
        "tick_wall_seconds": round(tick_wall, 2),
        "tick_wall_mean_seconds": round(tick_wall / max(1, sum(terminals.values())), 3),
        "slot_states": states,
        "admissions": [{key: item[key] for key in ("episode_id", "mint", "t0", "cohort_id", "cycle_start")} for item in admissions],
        "activation_state": activation_state,
        "packets": packets,
        "storage": {
            "ops_sqlite_bytes": ops.stat().st_size,
            "ops_wal_bytes": (ops.with_name(ops.name + "-wal").stat().st_size if ops.with_name(ops.name + "-wal").exists() else 0),
            "raw_plane_bytes": tree_bytes(data_root / "datasets" / "raw_evidence"),
            "publication_parquet_bytes": tree_bytes(data_root / "datasets" / "parquet"),
            "manifest_bytes": tree_bytes(data_root / "datasets" / "manifests"),
            "research_store_bytes": tree_bytes(data_root / "research"),
            "export_bytes": tree_bytes(data_root / "exports"),
            "rdp_total_bytes": tree_bytes(data_root),
        },
        "peak_rss_bytes": peak_rss_bytes(),
    }


# --------------------------------------------------------------------------
# P2: workstation


def _forge_call(*args: str, data_root: Path) -> dict[str, Any]:
    from tests.test_hfic_cli import run_cli

    done = run_cli(*args, "--format", "json", data_root=data_root)
    if done.returncode != 0:
        raise AssertionError(f"{args[0]} failed {done.returncode}: {done.stdout[-1200:]} {done.stderr[-1200:]}")
    return json.loads(done.stdout.strip().splitlines()[-1])


def _discovery(plane: Path, work: Path, *, tag: str, spec, scope, operation) -> dict[str, Any]:
    from tests.test_hfic_ordinary_operation_acceptance_v1 import _forge

    paths = [work / f"{tag}-{name}.json" for name in ("spec", "scope", "op")]
    for path, body in zip(paths, (spec, scope, operation)):
        path.write_text(json.dumps(body), encoding="utf-8")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = _forge().cmd_discovery_execute(
            ROOT,
            store_root=plane,
            census_path=None,
            observations_path=None,
            binding_path=None,
            spec_path=paths[0],
            journal_scope=operation["journal_scope"],
            candidate_scope_path=paths[1],
            explicit_data_root=plane,
            operation_path=paths[2],
        )
    lines = out.getvalue().strip().splitlines()
    payload = json.loads(lines[-1]) if lines else {}
    payload["_exit_code"] = code
    return payload


def vertical_spec(query_id: str) -> dict[str, Any]:
    return {
        "schema": "smial.hfic-temporal-query",
        "schema_version": "1.1",
        "query_id": query_id,
        "population": "OPPORTUNITY_EPISODES",
        "anchor_kind": "NOMINATION_T0",
        "time_contract": {"schedule_contract": "OPPORTUNITY_EPISODE_SCHEDULE_V1", "time_feature_clock": "FIRST_RELIABLE_AVAILABLE_AT"},
        "search_tier": "COMPOUND_SCREEN",
        "budget_allocation": "COMPOUND_FIRST",
        "decision": {"point_id": "E1800"},
        "features": [
            {"name": "holders", "op": "point_value", "field_id": HOLD, "point": "E1800"},
            {"name": "d_holders", "op": "delta", "field_id": HOLD, "start": "E300", "end": "E1800"},
            {"name": "liq", "op": "point_value", "field_id": LIQ, "point": "E1800"},
            {"name": "pret", "op": "return_ratio", "field_id": PRICE, "start": "E300", "end": "E1800"},
            {"name": "elapsed", "op": "elapsed_seconds", "start": "E300", "end": "E1800"},
        ],
        "all": [
            {"feature": "d_holders", "op": "gt", "value": 0},
            {"feature": "pret", "op": "gte", "value": 0},
            {"feature": "liq", "op": "lte", "value": 1000000},
            {"feature": "elapsed", "op": "gt", "value": 0},
        ],
        "target": {"kind": "PRICE_RELATIVE_PROXY", "reference_point": "E1800", "exit_point": "E14400", "field_id": PRICE},
        "entry_model": {"kind": "LAST_AVAILABLE_MARK_WITH_HAIRCUT", "assumed_latency_seconds": 0},
    }


def _import_legacy(plane: Path, scratch: Path) -> dict[str, Any]:
    from solana_alpha_lab.factory.live_cohort_discovery_release import (
        cohort_id_for_admission,
        import_live_cohort,
        seal_live_cohort,
        verify_live_cohort,
        write_observation_rdp_source,
    )
    from tests.test_live_cohort_discovery_release_series import CAMPAIGN_STARTS, CAMPAIGN_STOPS, _snapshot_for_week

    obs = scratch / "legacy-obs"
    release = scratch / "legacy-release"
    write_observation_rdp_source(obs, _snapshot_for_week(0, coverage="GAP_SUSPECTED"))
    cohort = cohort_id_for_admission(CAMPAIGN_STARTS + timedelta(hours=1), starts_at=CAMPAIGN_STARTS, stops_admitting_at=CAMPAIGN_STOPS)
    as_of = CAMPAIGN_STARTS + timedelta(days=10)
    seal_live_cohort(observation_rdp_root=obs, cohort_id=cohort, release_root=release, sealed_at=as_of, as_of=as_of)
    verify_live_cohort(release)
    return import_live_cohort(release_root=release, data_root=plane, import_time=as_of + timedelta(hours=1))


def _consume(packets: list[str], *, source: Path, mirror: Path, plane: Path) -> dict[str, Any]:
    argv = [sys.executable, "-B", str(ROOT / "scripts" / "discovery_evidence_release.py"), "unpack-next-live-cohort",
            "--collection", "OPPORTUNITY_EPISODES", "--max-cohorts", str(len(packets)),
            "--source-rdp", str(source), "--mirror-rdp", str(mirror), "--data-root", str(plane),
            "--as-of", AS_OF.strftime("%Y-%m-%dT%H:%M:%SZ"), "--release-builder-git-sha", "b" * 40]
    for packet in packets:
        argv.extend(["--capture-packet", packet])
    started = time.perf_counter()
    done = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    wall = time.perf_counter() - started
    lines = [line for line in done.stdout.strip().splitlines() if line.startswith("{")]
    payload = json.loads(lines[-1]) if lines else {"stderr": done.stderr[-2000:]}
    payload["_exit_code"] = done.returncode
    payload["_wall_seconds"] = round(wall, 2)
    return payload


def phase_p2(work: Path) -> dict[str, Any]:
    from solana_alpha_lab.factory import hfic_temporal_discovery as temporal
    from solana_alpha_lab.factory.hfic_research_universe_policy import apply_universe_policy, preview_universe_policy
    from solana_alpha_lab.factory.research_store import ResearchStore
    from tests.test_hfic_cli import bind_draft, critic_result_from_packet_only
    from tests.test_hfic_ordinary_operation_acceptance_v1 import _operation

    p1 = json.loads((work / "p1-report.json").read_text(encoding="utf-8"))
    source = work / "p1" / "rdp"
    p2 = work / "p2"
    plane, mirror = p2 / "plane", p2 / "mirror"
    plane.mkdir(parents=True)
    report: dict[str, Any] = {}
    report["legacy_import"] = _import_legacy(plane, p2)
    packets = p1["packets"]
    first = _consume(packets[:1], source=source, mirror=mirror, plane=plane)
    report["consume_first"] = first
    replay_import = _consume(packets[:1], source=source, mirror=mirror, plane=plane)
    report["consume_repeat"] = replay_import
    store = ResearchStore(plane)
    proposal = preview_universe_policy(store, min_holders=50, min_liquidity_usd=5000)["proposal"]
    apply_universe_policy(store, repo_root=ROOT, proposal=proposal, confirm_append_only=True)
    pre = _forge_call("preflight", "--discovery-contract", "--collection", "OPPORTUNITY_EPISODES", "--owner-focus", "VERTICAL_SYNTH_FOCUS", data_root=plane)
    report["preflight_1"] = {k: pre.get(k) for k in ("action", "owner_focus", "market_evidence_epoch_sha256", "search_key_sha256")}
    report["packet_card"] = pre["forge_context_packet"].get("population_card")
    report["packet_has_episode_capabilities"] = "episode_query_capabilities" in pre["forge_context_packet"]
    spec = vertical_spec("VERTICAL-MIXED-1")
    scope = {"population": "OPPORTUNITY_EPISODES", "decision_timestamp": "E1800", "target": temporal.temporal_target_label(spec),
             "estimand": "price_relative_proxy", "explanatory_condition": "holders", "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1"}
    operation = _operation(spec, focus=pre["owner_focus"], journal=pre["search_key_sha256"], market=pre["market_evidence_epoch_sha256"],
                           text="Synthetic vertical mixed episode question", cap={"main": 1, "adaptive": 0, "preview": 1}, completion="SCIENTIFIC_TERMINAL")
    evidence = _discovery(plane, p2, tag="run1", spec=spec, scope=scope, operation=operation)
    report["run1"] = {"exit": evidence["_exit_code"], "values_loaded": evidence.get("values_loaded"), "result": evidence.get("result")}
    repeat = _discovery(plane, p2, tag="run1-repeat", spec=spec, scope=scope, operation=operation)
    report["run1_repeat"] = {"exit": repeat["_exit_code"], "values_loaded": repeat.get("values_loaded"),
                             "scientific_look_delta": repeat.get("scientific_look_delta"), "spec_sha256": repeat.get("spec_sha256")}
    # Lifecycle: draft -> freeze -> isolated Critic (scripted model boundary) -> finalize.
    fresh = _forge_call("preflight", "--discovery-contract", "--owner-focus", pre["owner_focus"], data_root=plane)
    identity = temporal.temporal_holder_claim_identity(evidence["result"])
    template = json.loads((ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text(encoding="utf-8"))
    card = {**template["candidates"][0], **scope, **identity,
            "label": "VERTICAL_SYNTH", "claim_form": "PREDICTIVE", "novelty_class": "REFORMULATION",
            "claim": "Holder growth between E300 and E1800 may discriminate a later E14400 PRICE_RELATIVE_PROXY among admitted OPPORTUNITY_EPISODES; synthetic acceptance only.",
            "mechanism": "Participation growth after nomination may precede price direction; staleness and activity remain confounders, causality UNKNOWN.",
            "mundane_alternative": "Activity and price staleness can produce the same association without predictive holder information.",
            "actor_counterparty": "Admitted episode holders and later buyers; no causal actor identification.",
            "state_transition": "E300 to E1800 holder delta -> fixed E14400 price mark, no execution claim.",
            "proposed_method": "One frozen mixed recipe on the episode corpus, no retuning, PRICE_RELATIVE_PROXY only.",
            "negative_control": "SAME_DECISION_ELIGIBLE baseline; no claim of independence or alpha.",
            "confounders": ["activity", "price staleness"], "required_capability_ids": [temporal.TEMPORAL_CAPABILITY_ID],
            "required_feature_ids": [], "cheapest_falsifier": "One frozen PRICE_RELATIVE_PROXY contrast against SAME_DECISION_ELIGIBLE; no threshold sweep.",
            "disconfirming_prediction": "The holder condition shows no supported price contrast against the decision baseline.",
            "decision_unlocked": "Whether a separately authorized validation is justified; synthetic acceptance grants no science permission.",
            "kill_if": ["PIT lineage fails", "No supported directional contrast"], "prior_work_refs": [],
            "material_difference_from_prior": "New episode population, no prior exact close claimed.", "unresolved_requirements": []}
    draft = bind_draft({**template, "owner_focus": pre["owner_focus"], "candidates": [card]}, fresh)
    draft.pop("runner_up_candidate_ref", None)
    draft.pop("strongest_rejected_alternative", None)
    draft["selected_candidate_ref"] = card["label"]
    draft["grounded_evidence"] = evidence
    draft_path, receipt_path = p2 / "draft.json", p2 / "pre-receipt.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    receipt_path.write_text(json.dumps(fresh), encoding="utf-8")
    _forge_call("persist-draft", "--draft", str(draft_path), "--preflight-receipt", str(receipt_path), "--representation-id", "BASE", data_root=plane)
    resume = _forge_call("preflight", "--discovery-contract", "--owner-focus", pre["owner_focus"], data_root=plane)
    receipt_path.write_text(json.dumps(resume), encoding="utf-8")
    frozen = _forge_call("freeze", "--draft", str(draft_path), "--preflight-receipt", str(receipt_path), data_root=plane)
    packet = frozen["critic_input_packet"]
    report["frozen"] = {"session_id": frozen["session_id"], "grounding": packet["selected_candidate"]["grounding"]["terminal"],
                        "population": packet["selected_candidate"]["population"]}
    from tests.test_hfic_cli import run_cli

    bad = critic_result_from_packet_only(packet, terminal="KILL_STATISTICALLY_UNIDENTIFIABLE")
    bad["critic_input_packet_sha256"] = "0" * 64
    bad_path = p2 / "critic-invalid.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    refused = run_cli("finalize", "--session-id", frozen["session_id"], "--critic-result", str(bad_path), "--format", "json", data_root=plane)
    missing = run_cli("finalize", "--session-id", frozen["session_id"], "--critic-result", str(p2 / "critic-missing.json"), "--format", "json", data_root=plane)
    report["critic_invalid"] = {"exit": refused.returncode, "stderr": refused.stderr.strip()[-200:]}
    report["critic_missing"] = {"exit": missing.returncode, "stderr": missing.stderr.strip()[-200:]}
    critic = critic_result_from_packet_only(packet, terminal="KILL_STATISTICALLY_UNIDENTIFIABLE")
    critic["non_claims"].append("SCRIPTED_CRITIC_MECHANICAL")
    critic_path = p2 / "critic.json"
    critic_path.write_text(json.dumps(critic), encoding="utf-8")
    finished = _forge_call("finalize", "--session-id", frozen["session_id"], "--critic-result", str(critic_path), data_root=plane)
    report["finalize"] = {"session_state": finished.get("session_state"), "terminal": finished.get("final_session_terminal")}
    owner = _forge_call("forge-run", "--owner-focus", pre["owner_focus"], "--persist", data_root=plane)
    report["forge_run_owner"] = (owner.get("ordinary_operation") or {}).get("effective_state")
    (p2 / "run1-evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
    # Next run: two more cohorts (tiny incomplete + next cycle) via the same command.
    report["consume_next"] = _consume(packets[1:], source=source, mirror=mirror, plane=plane)
    pre2 = _forge_call("preflight", "--discovery-contract", "--collection", "OPPORTUNITY_EPISODES", "--owner-focus", "VERTICAL_SYNTH_FOCUS_NEXT", data_root=plane)
    report["preflight_2"] = {k: pre2.get(k) for k in ("action", "market_evidence_epoch_sha256", "search_key_sha256")}
    report["packet_card_2"] = pre2["forge_context_packet"].get("population_card")
    spec2 = vertical_spec("VERTICAL-MIXED-2")
    scope2 = dict(scope, target=temporal.temporal_target_label(spec2))
    operation2 = _operation(spec2, focus=pre2["owner_focus"], journal=pre2["search_key_sha256"], market=pre2["market_evidence_epoch_sha256"],
                            text="Synthetic vertical next run", cap={"main": 1, "adaptive": 0, "preview": 1}, completion="LIMITED_RESULT")
    evidence2 = _discovery(plane, p2, tag="run2", spec=spec2, scope=scope2, operation=operation2)
    report["run2"] = {"exit": evidence2["_exit_code"], "values_loaded": evidence2.get("values_loaded"),
                      "scientific_look_delta": evidence2.get("scientific_look_delta"), "result": evidence2.get("result")}
    (p2 / "run2-evidence.json").write_text(json.dumps(evidence2), encoding="utf-8")
    report["storage"] = {
        "mirror_bytes": tree_bytes(mirror),
        "sealed_release_bytes": tree_bytes(mirror / "sealed_releases"),
        "episode_corpus_bytes": tree_bytes(plane / "datasets" / "opportunity_episodes_corpus"),
        "plane_total_bytes": tree_bytes(plane),
    }
    report["peak_rss_bytes"] = peak_rss_bytes()
    report["focus"] = pre["owner_focus"]
    report["focus_next"] = pre2["owner_focus"]
    return report


# --------------------------------------------------------------------------
# P3: cold relocated process


def phase_p3(work: Path) -> dict[str, Any]:
    original_plane = work / "p2" / "plane"
    cold_parent = Path(tempfile.mkdtemp(prefix="oep-cold-"))
    cold = cold_parent / "relocated" / "plane"
    shutil.copytree(original_plane, cold)
    # Saved evidence is read before the cold boundary is installed.
    p2 = json.loads((work / "p2-report.json").read_text(encoding="utf-8"))
    run1 = json.loads((work / "p2" / "run1-evidence.json").read_text(encoding="utf-8"))
    forbidden = [str((work / "p1").resolve()).lower(), str((work / "p2").resolve()).lower()]
    blocked: list[str] = []

    def hook(event: str, args: tuple) -> None:
        if event in {"socket.connect", "socket.getaddrinfo", "socket.bind"}:
            blocked.append(event)
            raise PermissionError("COLD_NETWORK_FORBIDDEN")
        if event in {"open", "sqlite3.connect", "os.listdir", "os.scandir"} and args:
            target = args[0]
            if isinstance(target, (str, bytes, os.PathLike)):
                text = os.path.abspath(os.fsdecode(target)).lower()
                if any(text.startswith(root) for root in forbidden):
                    blocked.append(event)
                    raise PermissionError("COLD_ORIGINAL_ROOT_FORBIDDEN")

    sys.addaudithook(hook)
    probe = "NOT_BLOCKED"
    try:
        open(work / "p1" / "rdp" / "observation_schedule_state.sqlite", "rb").close()
    except PermissionError:
        probe = "BLOCKED"
    blocked.clear()
    from unittest import mock

    from solana_alpha_lab.factory import hfic_temporal_discovery as temporal
    from solana_alpha_lab.factory.live_cohort_discovery_release import verify_live_cohort
    from solana_alpha_lab.factory.opportunity_episode_release import load_episode_lineage
    from solana_alpha_lab.factory.research_store import ResearchStore
    from tests.test_hfic_ordinary_operation_acceptance_v1 import _forge

    report: dict[str, Any] = {"original_root_probe": probe}
    lineage = load_episode_lineage(cold)
    report["verified_releases"] = [verify_live_cohort(cold / item["release_dir_rel"])["release_id"] for item in lineage["cohorts"]]
    before = ResearchStore(cold).diagnostics().committed_inventory_sha256

    def saved_readback(focus: str) -> dict[str, Any]:
        out = io.StringIO()
        with mock.patch("solana_alpha_lab.factory.hfic_grounded_discovery.load_admitted_partition_rows", side_effect=AssertionError("cold readback loaded values")), \
                mock.patch.object(temporal, "execute_temporal_discovery", side_effect=AssertionError("cold readback evaluated")), \
                contextlib.redirect_stdout(out):
            code = _forge().main(["--root", str(ROOT), "--data-root", str(cold), "forge-run", "--owner-focus", focus, "--format", "json", "--no-write"])
        body = json.loads([line for line in out.getvalue().strip().splitlines() if line.startswith("{")][-1])
        return {"exit": code, "owner_class": body.get("owner_class"), "owner_final": body.get("owner_final"),
                "blocking_reason_codes": body.get("blocking_reason_codes"), "market_evidence_epoch_sha256": body.get("market_evidence_epoch_sha256")}

    # The first focus completed on the previous epoch: new evidence must not
    # carry that completion forward. The next focus reads its saved result.
    report["readback_superseded"] = saved_readback(p2["focus"])
    report["readback"] = saved_readback(p2["focus_next"])
    report["readback"]["store_unchanged"] = ResearchStore(cold).diagnostics().committed_inventory_sha256 == before
    calls = {"evaluator": 0}
    real = temporal.execute_temporal_discovery

    def counting(*args, **kwargs):
        calls["evaluator"] += 1
        return real(*args, **kwargs)

    with mock.patch.object(temporal, "execute_temporal_discovery", side_effect=counting):
        replay = temporal.run_registered_fixed_time_proxy(
            root=ROOT,
            registry_path=ROOT / "configs/experiment_capability_registry_v2.yaml",
            recipe=run1["result"]["experiment_recipe"],
            data_root=cold,
        )
    report["replay"] = {"evaluator_calls": calls["evaluator"], "equal_to_saved": replay["summary"] == run1["result"],
                        "summary": {k: replay["summary"][k] for k in ("matched_n", "observed_target_n", "mean_target", "episode_counts")}}
    report["blocked_events_during_cold"] = sorted(set(blocked))
    report["peak_rss_bytes"] = peak_rss_bytes()
    shutil.rmtree(cold_parent, ignore_errors=True)
    return report


PHASES = {"P1": phase_p1, "P2": phase_p2, "P3": phase_p3}


def run_phase(name: str, work: Path) -> None:
    started = time.perf_counter()
    report = PHASES[name](work)
    report["wall_seconds"] = round(time.perf_counter() - started, 2)
    (work / f"{name.lower()}-report.json").write_text(json.dumps(report, default=str, sort_keys=True), encoding="utf-8")


def spawn(name: str, work: Path) -> dict[str, Any]:
    done = subprocess.run(
        [sys.executable, "-B", str(Path(__file__).resolve()), "--phase", name, "--work", str(work)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if done.returncode != 0:
        raise AssertionError(f"{name} failed: {done.stdout[-3000:]}\n{done.stderr[-5000:]}")
    return json.loads((work / f"{name.lower()}-report.json").read_text(encoding="utf-8"))


class ThreeProcessVerticalTests(unittest.TestCase):
    def test_producer_to_ordinary_forge_to_cold_replay(self) -> None:
        keep = os.environ.get("OEP_VERTICAL_WORK")
        work = Path(keep) if keep else Path(tempfile.mkdtemp(prefix="oep-vertical-"))
        work.mkdir(parents=True, exist_ok=True)
        if not keep:
            self.addCleanup(lambda: shutil.rmtree(work, ignore_errors=True))
        p1 = spawn("P1", work)
        m = mints()
        # D2/D4: 25 admissions over three UTC days, one mint twice across cycles.
        self.assertEqual(len(p1["admissions"]), 25)
        self.assertEqual(p1["activation_state"], "COMPLETE")
        repeated = [item for item in p1["admissions"] if item["mint"] == m["A"][0]]
        self.assertEqual(len(repeated), 2)
        self.assertNotEqual(repeated[0]["episode_id"], repeated[1]["episode_id"])
        self.assertEqual([item["cycle_start"] for item in repeated], ["2026-10-05T00:00:00Z", "2026-10-12T00:00:00Z"])
        self.assertEqual(sorted({item["cohort_id"] for item in p1["admissions"]}), [
            "REL-20261008T000000Z-20261009T000000Z", "REL-20261011T000000Z-20261012T000000Z", "REL-20261012T000000Z-20261013T000000Z"])
        self.assertEqual(sum(p1["slot_states"].values()), 25 * 138)
        self.assertFalse(set(p1["slot_states"]) & {"PENDING", "DUE", "CLAIMED"})
        self.assertIn("DISAPPEARED", p1["slot_states"])
        self.assertIn("CENSORED", p1["slot_states"])
        p2 = spawn("P2", work)
        # D6: genuine consume, exact repeat, legacy alongside.
        self.assertEqual(p2["legacy_import"]["status"], "IMPORTED")
        self.assertEqual(p2["consume_first"]["result"]["terminal"], "EPISODE_BATCH_COMPLETE", p2["consume_first"])
        self.assertEqual(p2["consume_first"]["result"]["cohorts"][0]["import_status"], "IMPORTED")
        self.assertEqual(p2["consume_repeat"]["result"]["cohorts"][0]["import_status"], "PASS_ALREADY_PRESENT_EXACT")
        self.assertEqual(p2["consume_repeat"]["result"]["cohorts"][0]["transferred_files"], 0)
        self.assertEqual(p2["consume_next"]["result"]["imported_n"], 2)
        # D7: generated card and packet.
        card = p2["packet_card"]
        self.assertEqual(card["population"], "OPPORTUNITY_EPISODES")
        self.assertEqual(card["membership"]["admissions_n"], 12)
        self.assertTrue(p2["packet_has_episode_capabilities"])
        self.assertEqual(p2["packet_card_2"]["membership"]["admissions_n"], 25)
        self.assertEqual(p2["packet_card_2"]["membership"]["distinct_mint_n"], 24)
        self.assertEqual(p2["packet_card_2"]["membership"]["repeated_mint_n"], 1)
        # D8: literal oracle of the authored market (signal = even index).
        result = p2["run1"]["result"]
        counts = result["episode_counts"]
        self.assertEqual((counts["n_admitted"], counts["n_decision_eligible"], counts["n_matched"], counts["n_target_available"]), (12, 12, 6, 5))
        self.assertAlmostEqual(result["mean_target"], 0.10, places=9)
        self.assertAlmostEqual(result["baseline"]["mean_target"], (5 * 0.10 + 6 * (0.931 / 0.98 - 1)) / 11, places=9)
        self.assertAlmostEqual(result["matched_feature_means"]["d_holders"], 15.0, places=9)
        self.assertAlmostEqual(result["matched_feature_means"]["elapsed"], 1500.0, places=9)
        self.assertEqual(result["universe_policy"]["n_pass"], 12)
        self.assertEqual(p2["run1_repeat"]["values_loaded"], False)
        self.assertEqual(p2["frozen"]["grounding"], "GROUNDED")
        self.assertNotEqual(p2["critic_invalid"]["exit"], 0)
        self.assertNotEqual(p2["critic_missing"]["exit"], 0)
        self.assertEqual(p2["finalize"]["terminal"], "KILL_STATISTICALLY_UNIDENTIFIABLE")
        self.assertEqual(p2["forge_run_owner"], "COMPLETED")
        # D9: next run on new evidence is a normal new look; exact repeat spent none.
        self.assertNotEqual(p2["preflight_1"]["market_evidence_epoch_sha256"], p2["preflight_2"]["market_evidence_epoch_sha256"])
        self.assertEqual(p2["run2"]["scientific_look_delta"], {"main": 1, "adaptive": 0})
        counts2 = p2["run2"]["result"]["episode_counts"]
        self.assertEqual((counts2["n_admitted"], counts2["n_decision_eligible"], counts2["n_matched"], counts2["n_target_available"]), (25, 24, 12, 11))
        self.assertEqual((counts2["unique_mint_n"], counts2["repeated_mint_n"]), (24, 1))
        p3 = spawn("P3", work)
        self.assertEqual(p3["original_root_probe"], "BLOCKED")
        self.assertEqual(len(p3["verified_releases"]), 3)
        self.assertIn("START_BASE", p3["readback_superseded"]["blocking_reason_codes"])
        self.assertEqual(p3["readback"]["owner_final"], "OPERATION_PAUSED_SEARCH_OPEN")
        self.assertEqual(p3["readback"]["market_evidence_epoch_sha256"], p2["preflight_2"]["market_evidence_epoch_sha256"])
        self.assertTrue(p3["readback"]["store_unchanged"])
        self.assertEqual(p3["replay"]["evaluator_calls"], 1)
        self.assertTrue(p3["replay"]["equal_to_saved"])
        self.assertAlmostEqual(p3["replay"]["summary"]["mean_target"], 0.10, places=9)
        self.assertEqual(p3["blocked_events_during_cold"], [])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=sorted(PHASES))
    parser.add_argument("--work", type=Path)
    parsed, rest = parser.parse_known_args()
    if parsed.phase:
        run_phase(parsed.phase, parsed.work)
    else:
        unittest.main(argv=[sys.argv[0], *rest])
