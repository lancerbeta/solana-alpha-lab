"""Ordinary operation lifecycle through the public Forge path.

A run that reached a persisted owner-final no longer holds the research-universe
gate; an unfinished run can be stopped by the owner without a verdict, quota
return or store edit. No status is hand-written: completion comes from the
production forge-run receipt and a stop from the public stop command.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_grounded_discovery import list_discovery_looks  # noqa: E402
from solana_alpha_lab.factory.hfic_ordinary_operation import (  # noqa: E402
    OrdinaryOperationError,
    gate_before_values,
    get_operation,
    list_operations,
    note_look_landed,
    operation_lifecycle,
    owner_allowance,
    record_operation,
)
from solana_alpha_lab.factory.hfic_temporal_discovery import (  # noqa: E402
    OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402
from tests.test_hfic_cli import bind_draft, run_cli  # noqa: E402
from tests.test_hfic_ordinary_operation_acceptance_v1 import _operation  # noqa: E402
from tests.test_hfic_temporal_discovery_v1 import LIQ, PRICE, _spec  # noqa: E402

HOLDER = "FIELD-HOLDER-COUNT-001"

# name, holders, liquidity at Y900. Liquidity above 20k keeps a 50/20k cycle populated.
CASES = (
    ("h49", 49, 30000),
    ("h50", 50, 6000),
    ("h51", 51, 30000),
    ("h80", 80, 25000),
    ("liq-low", 60, 4999),
    ("liq-missing", 60, None),
)


def _publish(workspace: Path) -> Path:
    from tests import test_hfic_temporal_production_runner_v1 as runner
    from tests.test_live_cohort_discovery_release_series import CAMPAIGN_STARTS, _obs, _snapshot_for_week
    from solana_alpha_lab.factory.hfic_temporal_discovery import stamp_provider_reported_snapshot_transport
    from solana_alpha_lab.factory.observation_schedule import schedule_sha256, validate_observation_schedule

    schedule = runner._schedule()
    schedule.pop("schedule_sha256", None)
    schedule = validate_observation_schedule(schedule, root=ROOT)
    schedule["schedule_sha256"] = schedule_sha256(schedule)

    def snapshot(week: int) -> dict:
        body = _snapshot_for_week(week)
        anchor = CAMPAIGN_STARTS + timedelta(days=7 * week)
        admission = anchor.strftime("%Y-%m-%dT%H:%M:%SZ")
        template = body["members"][0]
        body["members"], body["observations"] = [], []
        for index, (name, holders, liquidity) in enumerate(CASES):
            mint = f"lifecycle-{name}"
            body["members"].append({**template, "mint": mint, "candidate_state": "X_ELIGIBLE"})
            exit_price = 1.0 + 0.1 * index
            points = [
                ("X300", LIQ, 1000),
                ("Y900", PRICE, 1),
                ("Y7200", PRICE, exit_price),
                ("Y900", HOLDER, holders),
            ]
            if liquidity is not None:
                points.append(("Y900", LIQ, liquidity))
            for point, field, value in points:
                item = _obs(mint, point, admission, missing=False)
                offset = {"X300": 300, "Y900": 900, "Y7200": 7200}[point]
                stamp = (anchor + timedelta(seconds=offset + runner.DOCUMENT_LATENESS)).strftime("%Y-%m-%dT%H:%M:%SZ")
                item.update(field_id=field, typed_value=str(value), state="OBSERVED", missing_reason=None,
                            event_time=stamp, first_reliable_available_at=stamp)
                body["observations"].append(item)
        stamped = stamp_provider_reported_snapshot_transport(body["observations"])
        for item in stamped:
            item["call_occurrence_id"] = hashlib.sha256(
                f"{item['mint']}:{item['point_id']}:{item['field_id']}".encode()
            ).hexdigest()
        body["observations"] = stamped
        return body

    data_root = workspace / "rdp"
    with mock.patch.object(runner, "_snapshot_for_week", side_effect=snapshot), mock.patch.object(
        runner, "_schedule", return_value=schedule
    ):
        runner._publish(data_root, workspace, week=0, activate_universe=False)
    return data_root


def _json(completed) -> dict:
    try:
        body = json.loads(completed.stdout) if completed.stdout.strip() else {}
    except json.JSONDecodeError:
        body = {"raw": completed.stdout}
    body["_exit"] = completed.returncode
    body["_err"] = completed.stderr[-4000:]
    return body


def _cli(data_root: Path, *args: str) -> dict:
    return _json(run_cli(*args, "--format", "json", data_root=data_root))


def _clean(body: dict) -> dict:
    return {key: value for key, value in body.items() if not str(key).startswith("_")}


def _apply_profile(test: unittest.TestCase, data_root: Path, workspace: Path, holders: str, liquidity: str) -> dict:
    preview = _cli(data_root, "universe-policy-preview", "--min-holders", holders, "--min-liquidity-usd", liquidity)
    test.assertEqual(preview["_exit"], 0, preview)
    path = workspace / f"universe-{holders}-{liquidity}.json"
    path.write_text(json.dumps(preview["proposal"]), encoding="utf-8")
    applied = _cli(data_root, "universe-policy-apply", "--proposal", str(path), "--confirm-append-only")
    test.assertEqual(applied["_exit"], 0, applied)
    return applied


def _specs(query: str) -> tuple[dict, dict]:
    from tests.test_hfic_temporal_production_runner_v1 import DOCUMENT_LATENESS

    base = {
        "decision": {"point_id": "Y900", "time_policy": "BOUND_SCHEDULE_CUTOFF"},
        "schedule": {
            "lateness_seconds": DOCUMENT_LATENESS,
            "observation_clock_policy": OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
        },
        "target": {"kind": "PRICE_RELATIVE_PROXY", "reference_point": "Y900", "exit_point": "Y7200", "field_id": PRICE},
        "cost_profile": None,
    }
    simple = _spec(
        search_tier="SIMPLE_SCREEN",
        query_id=f"{query}-simple",
        features=[{"name": "mark", "op": "point_value", "field_id": PRICE, "point": "Y900"}],
        all=[{"feature": "mark", "op": "gte", "value": 0}],
        **base,
    )
    compound = _spec(
        search_tier="COMPOUND_SCREEN",
        query_id=f"{query}-compound",
        features=[
            {"name": "mark", "op": "point_value", "field_id": PRICE, "point": "Y900"},
            {"name": "holders", "op": "point_value", "field_id": HOLDER, "point": "Y900"},
        ],
        all=[{"feature": "mark", "op": "gte", "value": 0}, {"feature": "holders", "op": "gte", "value": 60}],
        **base,
    )
    return simple, compound


SCOPE = {
    "population": "BASE_X",
    "decision_timestamp": "Y900",
    "target": "PRICE_RELATIVE_PROXY:Y900:Y7200:FIELD-USD-PRICE-001",
    "estimand": "price_relative_proxy",
    "explanatory_condition": "mark",
    "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
}


def _execute(data_root: Path, workspace: Path, spec: dict, operation: dict, tag: str) -> dict:
    spec_path = workspace / f"{tag}.spec.json"
    scope_path = workspace / f"{tag}.scope.json"
    op_path = workspace / f"{tag}.op.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    scope_path.write_text(json.dumps(SCOPE), encoding="utf-8")
    op_path.write_text(json.dumps(operation), encoding="utf-8")
    return _cli(
        data_root,
        "discovery-execute",
        "--store", str(data_root),
        "--spec", str(spec_path),
        "--candidate-scope", str(scope_path),
        "--journal-scope", str(operation["journal_scope"]),
        "--operation", str(op_path),
    )


def _status(data_root: Path) -> dict:
    return _cli(data_root, "universe-policy-status")


def _ops(data_root: Path) -> int:
    return len(list_operations(ResearchStore(data_root, create_if_missing=False)))


def _cycle(test: unittest.TestCase, data_root: Path, workspace: Path, focus: str) -> dict:
    """One SCIENTIFIC_TERMINAL run to a persisted owner-final, on the public path only."""

    pre = _cli(data_root, "preflight", "--discovery-contract", "--owner-focus", focus)
    test.assertEqual(pre["_exit"], 0, pre)
    journal, market = pre["search_key_sha256"], pre["market_evidence_epoch_sha256"]
    simple, compound = _specs(focus.lower())
    operation = _operation(
        simple, focus=focus, journal=journal, market=market,
        text=f"Owner run {focus} to its scientific terminal",
        cap={"main": None, "adaptive": None, "preview": None},
        completion="SCIENTIFIC_TERMINAL",
    )
    operation.pop("spec")
    first = _execute(data_root, workspace, simple, operation, f"{focus}-simple")
    test.assertEqual(first["_exit"], 0, first)
    test.assertEqual(first.get("ordinary_operation"), "OPEN", first)
    second = _execute(data_root, workspace, compound, operation, f"{focus}-compound")
    test.assertEqual(second["_exit"], 0, second)
    digest = str(second["operation_sha256"])
    status = _status(data_root)
    test.assertTrue(status["pending_operation"], status)
    blocking = {item["operation_sha256"]: item for item in status["blocking_operations"]}
    test.assertIn(digest, blocking)
    test.assertEqual(blocking[digest]["effective_state"], "OPEN")
    test.assertEqual(blocking[digest]["next_action"], "FINISH_RUN_THEN_PERSIST_OWNER_FINAL_OR_STOP_OPERATION")
    fresh = _cli(data_root, "preflight", "--discovery-contract", "--owner-focus", focus)
    test.assertEqual(fresh["_exit"], 0, fresh)
    source = json.loads((ROOT / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1_2.json").read_text(encoding="utf-8"))
    # Each cycle authors its own cards; identical fixture cards would share hypothesis identities.
    renamed = {}
    for card in source["candidates"]:
        renamed[card["label"]] = f"{card['label']}-{focus}"
        card["label"] = renamed[card["label"]]
        card["claim"] = f"{card['claim']} ({focus})"
    for key in ("runner_up_candidate_ref", "strongest_rejected_alternative"):
        if source.get(key) in renamed:
            source[key] = renamed[source[key]]
    source["grounded_evidence"] = _clean(second)
    source["owner_focus"] = focus
    receipt = _clean(fresh)
    draft = bind_draft(source, receipt)
    draft_path = workspace / f"{focus}.draft.json"
    receipt_path = workspace / f"{focus}.preflight.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    frozen = _cli(data_root, "freeze", "--draft", str(draft_path), "--preflight-receipt", str(receipt_path))
    test.assertEqual(frozen["_exit"], 0, frozen)
    unpersisted = _cli(data_root, "forge-run", "--owner-focus", focus, "--no-write")
    test.assertEqual(unpersisted["_exit"], 0, unpersisted)
    test.assertEqual(unpersisted["owner_class"], "OWNER_FINAL", unpersisted)
    op_view = unpersisted["ordinary_operation"]
    test.assertEqual(op_view["effective_state"], "OPEN", op_view)
    test.assertEqual(op_view["next_action"], "PERSIST_OWNER_FINAL", op_view)
    test.assertTrue(_status(data_root)["pending_operation"])
    persisted = _cli(data_root, "forge-run", "--owner-focus", focus, "--persist")
    test.assertEqual(persisted["_exit"], 0, persisted)
    cold = _cli(data_root, "forge-run", "--owner-focus", focus, "--no-write")
    test.assertEqual(cold["ordinary_operation"]["effective_state"], "COMPLETED", cold["ordinary_operation"])
    test.assertEqual(cold["ordinary_operation"]["next_action"], "READ_SAVED_RESULT")
    basis = cold["ordinary_operation"]["lifecycle_basis"]
    test.assertEqual(basis["kind"], "RUN_OWNER_FINAL_RECEIPT")
    test.assertEqual(basis["owner_final"], persisted["owner_final"])
    test.assertEqual(get_operation(ResearchStore(data_root, create_if_missing=False), digest)["status"], "OPEN")
    return {
        "operation_sha256": digest,
        "journal": journal,
        "market": market,
        "result_refs": [first["result_refs"], second["result_refs"]],
        "owner_final": persisted["owner_final"],
    }


def _load_cli_module():
    spec = importlib.util.spec_from_file_location("hypothesis_forge_cli_lifecycle", ROOT / "scripts/hypothesis_forge.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    spec.loader.exec_module(module)
    return module


class OrdinaryOperationLifecycleTests(unittest.TestCase):
    def test_r1_r3_two_full_cycles_release_the_profile_without_repair(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = _publish(workspace)
            self.assertEqual(_apply_profile(self, data_root, workspace, "50", "5000")["status"], "APPENDED")
            first = _cycle(self, data_root, workspace, "LIFECYCLE_CYCLE_ONE")
            status = _status(data_root)
            self.assertFalse(status["pending_operation"], status)
            self.assertEqual(status["blocking_operations"], [])
            store = ResearchStore(data_root, create_if_missing=False)
            looks_before = list_discovery_looks(store, first["journal"])
            self.assertEqual(_apply_profile(self, data_root, workspace, "50", "20000")["min_liquidity_usd"], "20000")
            second = _cycle(self, data_root, workspace, "LIFECYCLE_CYCLE_TWO")
            self.assertNotEqual(second["operation_sha256"], first["operation_sha256"])
            self.assertFalse(_status(data_root)["pending_operation"])
            store = ResearchStore(data_root, create_if_missing=False)
            looks_after = list_discovery_looks(store, first["journal"])
            self.assertEqual(
                [item.get("record_id") for item in looks_after],
                [item.get("record_id") for item in looks_before],
            )
            again = _cli(data_root, "forge-run", "--owner-focus", "LIFECYCLE_CYCLE_ONE", "--no-write")
            self.assertEqual(again["ordinary_operation"]["effective_state"], "COMPLETED")
            self.assertEqual(again["owner_final"], first["owner_final"])
            repeat = _cli(data_root, "forge-run", "--owner-focus", "LIFECYCLE_CYCLE_ONE", "--persist")
            self.assertEqual(repeat["_exit"], 0, repeat)
            self.assertEqual(repeat["writes"]["research_store"], 0, repeat["writes"])
            stop = _cli(
                data_root, "operation-stop-preview",
                "--operation-sha256", first["operation_sha256"],
                "--owner-request-text", "cancel a finished run",
            )
            self.assertEqual(stop["_exit"], 2, stop)
            self.assertEqual(stop["reason_code"], "OPERATION_ALREADY_COMPLETED")
            self.assertEqual(stop["next_action"], "READ_SAVED_RESULT")

    def test_r2_r4_r5_owner_stop_without_profile_keeps_history_and_quota(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = _publish(workspace)
            pre = _cli(data_root, "preflight", "--discovery-contract", "--owner-focus", "LIFECYCLE_STOP")
            journal, market = pre["search_key_sha256"], pre["market_evidence_epoch_sha256"]
            simple, _compound = _specs("lifecycle-stop")
            request = _operation(
                simple, focus="LIFECYCLE_STOP", journal=journal, market=market,
                text="Pre-policy owner search left unfinished",
                cap={"main": None, "adaptive": None, "preview": None},
                completion="SCIENTIFIC_TERMINAL",
            )
            request.pop("spec")
            store = ResearchStore(data_root, create_if_missing=False)
            # A pre-policy operation recorded by the production owner, as the live store holds.
            digest = record_operation(store, request)["operation_sha256"]
            reserved = gate_before_values(
                store, operation_sha256=digest, spec=simple, journal_scope=journal,
                verified_market=market, repo_root=ROOT, data_root=data_root,
            )
            self.assertEqual(reserved["disposition"], "RESERVED")
            main_before = owner_allowance(store, get_operation(store, digest), "main")
            status = _status(data_root)
            self.assertTrue(status["pending_operation"])
            self.assertEqual(status["state"], "ABSENT")
            [blocking] = status["blocking_operations"]
            self.assertEqual(blocking["operation_sha256"], digest)
            self.assertEqual(blocking["unresolved_reservations"], 1)
            refused_apply = _cli(data_root, "universe-policy-preview", "--min-holders", "50", "--min-liquidity-usd", "5000")
            self.assertEqual(refused_apply["next_action"], "FINISH_OPEN_FORGE_OPERATION_THEN_PREVIEW")
            unknown = _cli(data_root, "operation-stop-preview", "--operation-sha256", "ef" * 32,
                           "--owner-request-text", "stop a foreign id")
            self.assertEqual(unknown["reason_code"], "ORDINARY_OPERATION_NOT_FOUND", unknown)
            textless = _cli(data_root, "operation-stop-preview", "--operation-sha256", digest,
                            "--owner-request-text", "  ")
            self.assertEqual(textless["reason_code"], "OPERATION_STOP_REQUEST_REQUIRED", textless)
            preview = _cli(data_root, "operation-stop-preview", "--operation-sha256", digest,
                           "--owner-request-text", "Owner cancels the unfinished pre-policy search")
            self.assertEqual(preview["_exit"], 0, preview)
            self.assertEqual(preview["status"], "PROPOSED")
            self.assertIsNone(preview["effect"]["scientific_verdict"])
            self.assertFalse(preview["effect"]["quota_returned"])
            self.assertEqual(preview["writes"], {"research_store": 0})
            proposal_path = workspace / "stop.json"
            proposal_path.write_text(json.dumps(preview["proposal"]), encoding="utf-8")
            inventory = store.diagnostics().committed_inventory_sha256
            unconfirmed = _cli(data_root, "operation-stop", "--proposal", str(proposal_path))
            self.assertEqual(unconfirmed["reason_code"], "OPERATION_STOP_CONFIRM_REQUIRED", unconfirmed)
            forged = dict(preview["proposal"])
            forged["operation_sha256"] = "ef" * 32
            forged_path = workspace / "forged.json"
            forged_path.write_text(json.dumps(forged), encoding="utf-8")
            tampered = _cli(data_root, "operation-stop", "--proposal", str(forged_path), "--confirm-append-only")
            self.assertEqual(tampered["reason_code"], "OPERATION_STOP_PROPOSAL_INVALID", tampered)
            self.assertEqual(ResearchStore(data_root, create_if_missing=False).diagnostics().committed_inventory_sha256, inventory)
            other = _cli(data_root, "operation-stop-preview", "--operation-sha256", digest,
                         "--owner-request-text", "A second, different owner wording")
            other_path = workspace / "other.json"
            other_path.write_text(json.dumps(other["proposal"]), encoding="utf-8")
            stopped = _cli(data_root, "operation-stop", "--proposal", str(proposal_path), "--confirm-append-only")
            self.assertEqual(stopped["_exit"], 0, stopped)
            self.assertEqual(stopped["status"], "APPENDED")
            self.assertEqual(stopped["writes"], {"research_store": 1})
            store = ResearchStore(data_root, create_if_missing=False)
            stopped_row = get_operation(store, digest)
            self.assertEqual(stopped_row["status"], "STOPPED")
            self.assertEqual(stopped_row["lifecycle_event"]["unresolved_reservation_spec_sha256"], [reserved["spec_sha256"]])
            self.assertIsNone(stopped_row["lifecycle_event"]["scientific_verdict"])
            repeat = _cli(data_root, "operation-stop", "--proposal", str(proposal_path), "--confirm-append-only")
            self.assertEqual(repeat["status"], "NO_CHANGE", repeat)
            self.assertEqual(repeat["writes"], {"research_store": 0})
            stale = _cli(data_root, "operation-stop", "--proposal", str(other_path), "--confirm-append-only")
            self.assertEqual(stale["status"], "NO_CHANGE", stale)
            self.assertFalse(stale["same_proposal"])
            self.assertEqual(_ops(data_root), 2)
            # Quota is not returned: the unresolved reservation stays spent.
            self.assertEqual(owner_allowance(store, get_operation(store, digest), "main"), main_before)
            # A late landing cannot reopen the operation.
            self.assertEqual(note_look_landed(store, digest)["status"], "STOPPED")
            with self.assertRaises(OrdinaryOperationError) as resumed:
                gate_before_values(
                    store, operation_sha256=digest, spec=simple, journal_scope=journal,
                    verified_market=market, repo_root=ROOT, data_root=data_root,
                )
            self.assertEqual(resumed.exception.code, "ORDINARY_OPERATION_STOPPED")
            self.assertEqual(_ops(data_root), 2)
            readback = _cli(data_root, "forge-run", "--owner-focus", "LIFECYCLE_STOP", "--no-write")
            self.assertEqual(readback["ordinary_operation"]["effective_state"], "STOPPED")
            self.assertEqual(readback["ordinary_operation"]["next_action"], "READ_SAVED_RESULT")
            self.assertNotIn(readback.get("owner_final"), {"NO_WORTHY_HYPOTHESIS", "SEARCH_EXHAUSTED_CURRENT_EVIDENCE"})
            self.assertFalse(_status(data_root)["pending_operation"])
            _apply_profile(self, data_root, workspace, "50", "5000")
            denied = _execute(data_root, workspace, simple, request, "after-stop")
            self.assertEqual(denied["reason_code"], "ORDINARY_OPERATION_STOPPED", denied)
            self.assertFalse(denied["values_loaded"])
            self.assertEqual(list_discovery_looks(ResearchStore(data_root, create_if_missing=False), journal), [])

    def test_r4_open_run_blocks_apply_and_limited_result_pauses(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = _publish(workspace)
            _apply_profile(self, data_root, workspace, "50", "5000")
            pre = _cli(data_root, "preflight", "--discovery-contract", "--owner-focus", "LIFECYCLE_LIMITED")
            journal, market = pre["search_key_sha256"], pre["market_evidence_epoch_sha256"]
            simple, _compound = _specs("lifecycle-limited")
            limited = _operation(
                simple, focus="LIFECYCLE_LIMITED", journal=journal, market=market,
                text="One limited look", cap={"main": 1, "adaptive": 0, "preview": 0},
            )
            landed = _execute(data_root, workspace, simple, limited, "limited")
            self.assertEqual(landed.get("ordinary_operation"), "PAUSED_CAP", landed)
            store = ResearchStore(data_root, create_if_missing=False)
            paused = get_operation(store, landed["operation_sha256"])
            self.assertEqual(operation_lifecycle(store, paused)["effective_state"], "PAUSED_CAP")
            self.assertFalse(_status(data_root)["pending_operation"])
            open_request = _operation(
                simple, focus="LIFECYCLE_LIMITED", journal=journal, market=market,
                text="An open search still running", cap={"main": None, "adaptive": None, "preview": None},
                completion="SCIENTIFIC_TERMINAL",
            )
            open_request.pop("spec")
            record_operation(store, open_request)
            preview = _cli(data_root, "universe-policy-preview", "--min-holders", "50", "--min-liquidity-usd", "20000")
            path = workspace / "pending.json"
            path.write_text(json.dumps(preview["proposal"]), encoding="utf-8")
            refused = _cli(data_root, "universe-policy-apply", "--proposal", str(path), "--confirm-append-only")
            self.assertEqual(refused["reason_code"], "UNIVERSE_POLICY_PENDING_OPERATION", refused)
            self.assertEqual(len(refused["blocking_operations"]), 1)

    def test_r6_predictable_preview_refusal_never_calls_the_loader(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = _publish(workspace)
            pre = _cli(data_root, "preflight", "--discovery-contract", "--owner-focus", "LIFECYCLE_PREVIEW_CAP")
            simple, _compound = _specs("lifecycle-preview")
            request = _operation(
                simple, focus="LIFECYCLE_PREVIEW_CAP", journal=pre["search_key_sha256"],
                market=pre["market_evidence_epoch_sha256"], text="Owner gave this search no preview",
                cap={"main": None, "adaptive": None, "preview": 0}, completion="SCIENTIFIC_TERMINAL",
            )
            request.pop("spec")
            record_operation(ResearchStore(data_root, create_if_missing=False), request)
            cli = _load_cli_module()

            def _run(**patches) -> dict:
                out = io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                    with contextlib.ExitStack() as stack:
                        for target, value in patches.items():
                            stack.enter_context(mock.patch(target, value))
                        cli.cmd_universe_policy_preview(
                            ROOT, explicit_data_root=data_root, min_holders="50",
                            min_liquidity_usd="5000", decision_point="Y900",
                        )
                return json.loads(out.getvalue())

            loader = mock.Mock(side_effect=AssertionError("value loader called"))
            refused = _run(**{"solana_alpha_lab.factory.hfic_grounded_discovery.load_admitted_partition_rows": loader})
            self.assertEqual(refused["reason_code"], "OWNER_CAP_EXHAUSTED", refused)
            self.assertFalse(refused["values_loaded"])
            self.assertEqual(loader.call_count, 0)
            self.assertEqual(len(refused["blocking_operations"]), 1)
            from solana_alpha_lab.factory.hfic_research_universe_policy import UniversePolicyError

            with mock.patch(
                "solana_alpha_lab.factory.hfic_research_universe_policy._deny_exhausted_preview",
                lambda _store: None,
            ):
                late = _run(**{
                    "solana_alpha_lab.factory.hfic_temporal_discovery.universe_population_counts":
                    mock.Mock(side_effect=UniversePolicyError("UNIVERSE_POLICY_INVALID")),
                })
            self.assertEqual(late["reason_code"], "UNIVERSE_POLICY_INVALID", late)
            self.assertTrue(late["values_loaded"])
            history = _cli(data_root, "forge-run", "--owner-focus", "LIFECYCLE_PREVIEW_CAP", "--no-write")
            self.assertIn("ordinary_operation", history)


class OperationCompletionBindingTests(unittest.TestCase):
    """R7: only the bound run's owner-final receipt completes an operation."""

    MARKET = "ab" * 32
    JOURNAL = "cd" * 32
    FOCUS = "LIFECYCLE_BINDING"

    def _receipt(self, store: ResearchStore, **overrides) -> None:
        from solana_alpha_lab.factory.hfic_evidence_identity import scientific_slot_sha256
        from solana_alpha_lab.factory.hfic_representation_ladder import _persist_run_receipt
        from solana_alpha_lab.factory.run_passport import canonical_sha256

        slot = scientific_slot_sha256(
            market_evidence_epoch_sha256=self.MARKET, representation_id="BASE",
            representation_semantic_version="HFIC-V1.2", owner_focus=self.FOCUS,
        )
        body = {
            "schema": "smial.forge-run-receipt",
            "owner_focus": self.FOCUS,
            "owner_class": "OWNER_FINAL",
            "owner_final": "SEARCH_EXHAUSTED_CURRENT_EVIDENCE",
            "market_evidence_epoch_sha256": self.MARKET,
            "scientific_slot_sha256": slot,
            "stages": [{"representation_id": "BASE", "session_id": "HFIC-SESS-UNKNOWN", "scientific_slot_sha256": slot}],
            "run_id": "FORGE-RUN-SYNTHETIC",
        }
        body.update(overrides)
        body["receipt_sha256"] = canonical_sha256(body)
        _persist_run_receipt(store, body, repo_root=ROOT)

    def _operation(self, store: ResearchStore) -> dict:
        return record_operation(store, {
            "owner_request_text": "binding witness",
            "owner_focus": self.FOCUS,
            "journal_scope": self.JOURNAL,
            "market_evidence_epoch_sha256": self.MARKET,
            "requested_completion": "SCIENTIFIC_TERMINAL",
            "owner_cap": {"main": None, "adaptive": None, "preview": None},
        })

    def test_foreign_non_final_early_or_unbound_receipts_do_not_complete(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw) / "rdp")
            self._receipt(store, run_id="EARLY")
            operation = self._operation(store)
            self._receipt(store, run_id="FOREIGN-MARKET", market_evidence_epoch_sha256="ef" * 32)
            self._receipt(store, run_id="FOREIGN-SLOT", scientific_slot_sha256="12" * 32)
            self._receipt(store, run_id="FOREIGN-FOCUS", owner_focus="OTHER_FOCUS")
            self._receipt(store, run_id="UNBOUND-SESSION")
            self._receipt(store, run_id="IN-PROGRESS", owner_class="FORGE_RUN_IN_PROGRESS", owner_final=None)
            lifecycle = operation_lifecycle(store, get_operation(store, operation["operation_sha256"]))
            self.assertEqual(lifecycle["effective_state"], "OPEN", lifecycle)
            self.assertEqual(get_operation(store, operation["operation_sha256"])["status"], "OPEN")


if __name__ == "__main__":
    unittest.main()
