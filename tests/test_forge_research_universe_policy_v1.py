"""Research-universe policy through the public Forge path. No hand-built mask."""

from __future__ import annotations

import hashlib
import json
import shutil
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

from solana_alpha_lab.factory.hfic_research_universe_policy import (
    classify_universe_cells,
    semantic_sha256,
)
from solana_alpha_lab.factory.hfic_temporal_discovery import (
    OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1,
    run_registered_fixed_time_proxy,
)
from tests.test_hfic_cli import run_cli
from tests.test_hfic_ordinary_operation_acceptance_v1 import _operation
from tests.test_hfic_temporal_discovery_v1 import PRICE, _spec

FOCUS = "FORGE_RESEARCH_UNIVERSE_POLICY_V1"


def _publish_cases(workspace: Path) -> Path:
    from tests import test_hfic_temporal_production_runner_v1 as runner
    from tests.test_live_cohort_discovery_release_series import CAMPAIGN_STARTS, _obs, _snapshot_for_week
    from solana_alpha_lab.factory.hfic_temporal_discovery import stamp_provider_reported_snapshot_transport
    from solana_alpha_lab.factory.observation_schedule import schedule_sha256, validate_observation_schedule

    schedule = runner._schedule()
    schedule.pop("schedule_sha256", None)
    schedule = validate_observation_schedule(schedule, root=ROOT)
    schedule["schedule_sha256"] = schedule_sha256(schedule)
    cases = (
        ("h49", 49, 6000, 0),
        ("h50", 50, 6000, 0),
        ("h51", 51, 6000, 0),
        ("liq-low", 51, 4999, 0),
        ("liq-exact", 51, 5000, 0),
        ("liq-missing", 51, None, 0),
        ("zero", 0, 6000, 0),
        ("late", 80, 6000, 120),
    )

    def snapshot(week: int) -> dict:
        body = _snapshot_for_week(week)
        anchor = CAMPAIGN_STARTS + timedelta(days=7 * week)
        admission = anchor.strftime("%Y-%m-%dT%H:%M:%SZ")
        template = body["members"][0]
        body["members"], body["observations"] = [], []
        for name, holders, liquidity, late in cases:
            mint = f"universe-{name}"
            body["members"].append({**template, "mint": mint, "candidate_state": "X_ELIGIBLE"})
            points = [("X300", "FIELD-LIQUIDITY-USD-001", 1000, 0), ("Y900", PRICE, 1, 0), ("Y7200", PRICE, 1.2, 0),
                      ("Y900", "FIELD-HOLDER-COUNT-001", holders, late)]
            if liquidity is not None:
                points.append(("Y900", "FIELD-LIQUIDITY-USD-001", liquidity, 0))
            for point, field, value, delay in points:
                item = _obs(mint, point, admission, missing=False)
                offset = {"X300": 300, "Y900": 900, "Y7200": 7200}[point]
                stamp = (anchor + timedelta(seconds=offset + runner.DOCUMENT_LATENESS + delay)).strftime("%Y-%m-%dT%H:%M:%SZ")
                item.update(field_id=field, typed_value=str(value), state="OBSERVED", missing_reason=None,
                            event_time=stamp, first_reliable_available_at=stamp)
                body["observations"].append(item)
        stamped = stamp_provider_reported_snapshot_transport(body["observations"])
        for item in stamped:
            item["call_occurrence_id"] = hashlib.sha256(f"{item['mint']}:{item['point_id']}:{item['field_id']}".encode()).hexdigest()
        body["observations"] = stamped
        return body

    data_root = workspace / "rdp"
    with mock.patch.object(runner, "_snapshot_for_week", side_effect=snapshot), mock.patch.object(runner, "_schedule", return_value=schedule):
        runner._publish(data_root, workspace, week=0, activate_universe=False)
    return data_root


def _apply(data_root: Path, workspace: Path, holders: str, liquidity: str) -> dict:
    preview = run_cli(
        "universe-policy-preview",
        "--min-holders", holders,
        "--min-liquidity-usd", liquidity,
        "--decision-point", "Y900",
        "--format", "json",
        data_root=data_root,
    )
    if preview.returncode != 0:
        raise AssertionError(preview.stdout + preview.stderr)
    body = json.loads(preview.stdout)
    path = workspace / f"proposal-{holders}-{liquidity}.json"
    path.write_text(json.dumps(body["proposal"]), encoding="utf-8")
    applied = run_cli(
        "universe-policy-apply",
        "--proposal", str(path),
        "--confirm-append-only",
        "--format", "json",
        data_root=data_root,
    )
    if applied.returncode != 0:
        raise AssertionError(applied.stdout + applied.stderr)
    return json.loads(applied.stdout)


class UniversePolicyTests(unittest.TestCase):
    def test_public_owner_path_filters_and_keeps_the_first_binding(self) -> None:
        from solana_alpha_lab.factory.research_store import ResearchStore

        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = _publish_cases(workspace)
            spec = _spec(
                search_tier="SIMPLE_SCREEN",
                query_id="universe-owner-path",
                decision={"point_id": "Y900", "time_policy": "BOUND_SCHEDULE_CUTOFF"},
                schedule={"lateness_seconds": 300, "observation_clock_policy": OBSERVATION_CLOCK_PROVIDER_REPORTED_SNAPSHOT_V1},
                features=[{"name": "mark", "op": "point_value", "field_id": PRICE, "point": "Y900"}],
                all=[{"feature": "mark", "op": "gte", "value": 0}],
                target={"kind": "PRICE_RELATIVE_PROXY", "reference_point": "Y900", "exit_point": "Y7200", "field_id": PRICE},
                cost_profile=None,
            )
            spec["schedule"]["lateness_seconds"] = __import__(
                "tests.test_hfic_temporal_production_runner_v1", fromlist=["DOCUMENT_LATENESS"]
            ).DOCUMENT_LATENESS
            pre = run_cli("preflight", "--discovery-contract", "--owner-focus", FOCUS, "--format", "json", data_root=data_root)
            self.assertEqual(pre.returncode, 0, pre.stdout + pre.stderr)
            receipt = json.loads(pre.stdout)
            self.assertEqual(receipt["universe_policy"]["state"], "ABSENT")
            journal, market = receipt["search_key_sha256"], receipt["market_evidence_epoch_sha256"]
            spec_path = workspace / "spec.json"
            scope_path = workspace / "scope.json"
            op_path = workspace / "operation.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            scope_path.write_text(json.dumps({
                "population": "BASE_X", "decision_timestamp": "Y900",
                "target": "PRICE_RELATIVE_PROXY:Y900:Y7200:FIELD-USD-PRICE-001",
                "estimand": "price_relative_proxy", "explanatory_condition": "mark",
                "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
            }), encoding="utf-8")
            op_path.write_text(json.dumps(_operation(
                spec, focus=FOCUS, journal=journal, market=market,
                text="Synthetic universe policy owner path",
                cap={"main": 1, "adaptive": 0, "preview": 1},
            )), encoding="utf-8")
            blocked_root = workspace / "blocked"
            shutil.copytree(data_root, blocked_root)
            blocked = run_cli(
                "discovery-execute", "--store", str(blocked_root), "--spec", str(spec_path),
                "--candidate-scope", str(scope_path), "--journal-scope", journal,
                "--operation", str(op_path), "--format", "json", data_root=blocked_root,
            )
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("UNIVERSE_POLICY_REQUIRED", blocked.stdout + blocked.stderr)
            preview = run_cli(
                "universe-policy-preview", "--min-holders", "50", "--min-liquidity-usd", "5000",
                "--decision-point", "Y900", "--format", "json", data_root=data_root,
            )
            self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
            proposed = json.loads(preview.stdout)
            counts = proposed["counts"]
            self.assertEqual(counts["n_pass"] + counts["n_fail"] + counts["n_unknown"], counts["n_base"])
            self.assertEqual(counts["n_pass"], 3)
            self.assertGreaterEqual(counts["n_fail"], 3)
            self.assertGreaterEqual(counts["n_unknown"], 2)
            self.assertFalse(proposed["counts_read_future_outcomes"])
            applied = _apply(data_root, workspace, "50", "5000")
            self.assertEqual(applied["status"], "APPENDED")
            from solana_alpha_lab.factory.run_passport import canonical_sha256

            stale = dict(proposed["proposal"])
            stale.pop("proposal_sha256", None)
            stale["base_policy_head_sha256"] = "ab" * 32
            stale["proposal_sha256"] = canonical_sha256(stale)
            stale_path = workspace / "stale.json"
            stale_path.write_text(json.dumps(stale), encoding="utf-8")
            rejected = run_cli(
                "universe-policy-apply", "--proposal", str(stale_path), "--confirm-append-only",
                "--format", "json", data_root=data_root,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("UNIVERSE_POLICY_PREVIEW_STALE", rejected.stdout + rejected.stderr)
            cold = run_cli("universe-policy-status", "--format", "json", data_root=data_root)
            self.assertEqual(cold.returncode, 0, cold.stdout + cold.stderr)
            status = json.loads(cold.stdout)
            self.assertEqual(status["min_holders"], "50")
            self.assertEqual(status["min_liquidity_usd"], "5000")
            self.assertEqual(status["semantic_sha256"], applied["semantic_sha256"])
            open_root = workspace / "open-run"
            shutil.copytree(data_root, open_root)
            executed = run_cli(
                "discovery-execute", "--store", str(data_root), "--spec", str(spec_path),
                "--candidate-scope", str(scope_path), "--journal-scope", journal,
                "--operation", str(op_path), "--format", "json", data_root=data_root,
            )
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            evidence = json.loads(executed.stdout)
            result = evidence["result"]
            self.assertEqual(result["universe_policy"]["n_pass"], 3)
            self.assertEqual(result["universe_policy"]["min_holders"], "50")
            self.assertEqual(result["experiment_recipe"]["universe_policy"]["semantic_sha256"], status["semantic_sha256"])
            self.assertLessEqual(result["matched_n"], result["universe_policy"]["n_pass"])
            replay = run_registered_fixed_time_proxy(
                root=ROOT,
                registry_path=ROOT / "configs/experiment_capability_registry_v2.yaml",
                recipe=result["experiment_recipe"],
                data_root=data_root,
            )
            self.assertEqual(replay["summary"]["universe_policy"]["semantic_sha256"], status["semantic_sha256"])
            self.assertEqual(replay["summary"]["universe_policy"]["n_pass"], 3)
            tampered = json.loads(json.dumps(result["experiment_recipe"]))
            tampered["universe_policy"]["semantic_sha256"] = "cd" * 32
            with self.assertRaises(Exception) as mismatch:
                run_registered_fixed_time_proxy(
                    root=ROOT, registry_path=ROOT / "configs/experiment_capability_registry_v2.yaml",
                    recipe=tampered, data_root=data_root,
                )
            self.assertIn("UNIVERSE_POLICY_BINDING_MISMATCH", str(mismatch.exception))
            self.assertEqual(evidence.get("ordinary_operation"), "PAUSED_CAP", evidence.get("ordinary_operation"))
            blocked_status = json.loads(run_cli("universe-policy-status", "--format", "json", data_root=blocked_root).stdout)
            self.assertFalse(blocked_status["pending_operation"])
            open_op = workspace / "open-op.json"
            open_op.write_text(json.dumps(_operation(
                spec, focus=FOCUS, journal=journal, market=market,
                text="Synthetic open run keeps the profile frozen",
                cap={"main": None, "adaptive": None, "preview": None},
            )), encoding="utf-8")
            opened = run_cli(
                "discovery-execute", "--store", str(open_root), "--spec", str(spec_path),
                "--candidate-scope", str(scope_path), "--journal-scope", journal,
                "--operation", str(open_op), "--format", "json", data_root=open_root,
            )
            self.assertEqual(opened.returncode, 0, opened.stdout + opened.stderr)
            self.assertEqual(json.loads(opened.stdout).get("ordinary_operation"), "OPEN")
            pending_preview = run_cli(
                "universe-policy-preview", "--min-holders", "50", "--min-liquidity-usd", "20000",
                "--decision-point", "Y900", "--format", "json", data_root=open_root,
            )
            self.assertEqual(pending_preview.returncode, 0, pending_preview.stdout + pending_preview.stderr)
            pending_path = workspace / "pending-20k.json"
            pending_path.write_text(json.dumps(json.loads(pending_preview.stdout)["proposal"]), encoding="utf-8")
            refused = run_cli(
                "universe-policy-apply", "--proposal", str(pending_path), "--confirm-append-only",
                "--format", "json", data_root=open_root,
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("UNIVERSE_POLICY_PENDING_OPERATION", refused.stdout + refused.stderr)
            self.assertIn("FINISH_OPEN_FORGE_OPERATION_THEN_PREVIEW", refused.stdout)
            prompt = run_cli("preflight", "--discovery-contract", "--owner-focus", FOCUS, "--format", "json", data_root=data_root)
            self.assertEqual(prompt.returncode, 0, prompt.stdout + prompt.stderr)
            prompt_receipt = json.loads(prompt.stdout)
            readouts = prompt_receipt["forge_context_packet"]["grounded_readouts"]
            self.assertEqual(readouts[-1]["universe_policy"]["semantic_sha256"], status["semantic_sha256"])
            from tests.test_hfic_cli import bind_draft
            from solana_alpha_lab.factory.hfic_session import freeze_draft

            source = json.loads((ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text(encoding="utf-8"))
            card = dict(source["candidates"][0])
            card.update({
                "label": "UNIVERSE-POLICY-Y900",
                "population": "BASE_X",
                "decision_timestamp": "Y900",
                "target": "PRICE_RELATIVE_PROXY:Y900:Y7200:FIELD-USD-PRICE-001",
                "estimand": "price_relative_proxy",
                "explanatory_condition": "mark",
            })
            draft = bind_draft({**source, "owner_focus": FOCUS, "candidates": [card]}, prompt_receipt)
            for key in ("runner_up_candidate_ref", "strongest_rejected_alternative"):
                draft.pop(key, None)
            draft["selected_candidate_ref"] = card["label"]
            draft["grounded_evidence"] = evidence
            frozen = freeze_draft(draft, preflight_receipt=prompt_receipt, store=ResearchStore(data_root), repo_root=ROOT)
            critic = frozen["critic_input_packet"]
            self.assertEqual(
                critic["grounded_evidence"]["universe_policy"]["universe_policy_semantic_sha256"],
                status["semantic_sha256"],
            )
            self.assertEqual(
                critic["grounded_evidence"]["result"]["universe_policy"]["semantic_sha256"],
                status["semantic_sha256"],
            )
            main_after_a = evidence["budget"]["main_count"]
            widened = _apply(data_root, workspace, "50", "20000")
            self.assertEqual(widened["min_liquidity_usd"], "20000")
            stored = run_registered_fixed_time_proxy(
                root=ROOT, registry_path=ROOT / "configs/experiment_capability_registry_v2.yaml",
                recipe=result["experiment_recipe"], data_root=data_root,
            )
            live = json.loads(run_cli("universe-policy-status", "--format", "json", data_root=data_root).stdout)
            self.assertEqual(live["min_liquidity_usd"], "20000")
            self.assertEqual(stored["summary"]["universe_policy"]["min_liquidity_usd"], "5000")
            restored = _apply(data_root, workspace, "50", "5000")
            self.assertEqual(restored["min_liquidity_usd"], "5000")
            self.assertEqual(restored["semantic_sha256"], status["semantic_sha256"])
            returned = run_cli(
                "discovery-execute", "--store", str(data_root), "--spec", str(spec_path),
                "--candidate-scope", str(scope_path), "--journal-scope", journal,
                "--operation", str(op_path), "--format", "json", data_root=data_root,
            )
            self.assertEqual(returned.returncode, 0, returned.stdout + returned.stderr)
            returned_body = json.loads(returned.stdout)
            self.assertFalse(returned_body["queries"][0]["new_look"])
            self.assertEqual(returned_body["scientific_look_delta"]["main"], 0)
            self.assertEqual(returned_body["result_refs"], evidence["result_refs"])
            self.assertEqual(returned_body["result"]["universe_policy"]["min_liquidity_usd"], "5000")
            self.assertEqual(main_after_a, evidence["budget"]["main_count"])

    def test_zero_is_not_missing_and_fail_beats_unknown(self) -> None:
        fail = classify_universe_cells(
            {"status": "OBSERVED", "value": 0},
            {"status": "ABSENT"},
            {"min_holders": "50", "min_liquidity_usd": "5000", "holder_field_id": "FIELD-HOLDER-COUNT-001",
             "liquidity_field_id": "FIELD-LIQUIDITY-USD-001", "rule": "ALL_OF_AT_DECISION_TIME"},
        )
        self.assertEqual(fail["status"], "FAIL")
        self.assertIn("HOLDER_BELOW_MIN", fail["reasons"])
        self.assertIn("LIQUIDITY_UNKNOWN", fail["reasons"])
        exact = classify_universe_cells(
            {"status": "OBSERVED", "value": 50},
            {"status": "OBSERVED", "value": 5000},
            {"min_holders": "50", "min_liquidity_usd": "5000", "holder_field_id": "FIELD-HOLDER-COUNT-001",
             "liquidity_field_id": "FIELD-LIQUIDITY-USD-001", "rule": "ALL_OF_AT_DECISION_TIME"},
        )
        self.assertEqual(exact["status"], "PASS")
        below = classify_universe_cells(
            {"status": "OBSERVED", "value": 49},
            {"status": "OBSERVED", "value": 5000},
            {"min_holders": "50", "min_liquidity_usd": "5000", "holder_field_id": "FIELD-HOLDER-COUNT-001",
             "liquidity_field_id": "FIELD-LIQUIDITY-USD-001", "rule": "ALL_OF_AT_DECISION_TIME"},
        )
        self.assertEqual(below["status"], "FAIL")
