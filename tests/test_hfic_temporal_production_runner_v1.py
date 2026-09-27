"""One published corpus through binder, journal, freeze, and DocumentRunner."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.document_runner import (  # noqa: E402
    DocumentRunner,
    RunContext,
)
from solana_alpha_lab.factory.hfic_grounded_discovery import (  # noqa: E402
    LIQUIDITY,
    PRICE,
    GroundedDiscoveryError,
    execute_discovery_from_rows,
    list_discovery_looks,
    load_admitted_partition_rows,
    resolve_published_discovery_binding,
    run_recorded_discovery_query,
)
from solana_alpha_lab.factory.hfic_temporal_discovery import (  # noqa: E402
    assert_search_exhaustion_claim,
    assess_tier_progress,
    temporal_target_label,
)
from solana_alpha_lab.factory.lane_classifier import classify_lane  # noqa: E402
from solana_alpha_lab.factory.live_cohort_discovery_release import (  # noqa: E402
    cohort_id_for_admission,
    import_live_cohort,
    seal_live_cohort,
    write_observation_rdp_source,
)
from solana_alpha_lab.factory.operational_store import OperationalStore  # noqa: E402
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402
from tests.test_fast_lane_classifier import AS_OF, HYPOTHESIS_DEFINITION_SHA256  # noqa: E402
from tests.test_fast_lane_runner import offline_v1_1_spec, publish_commissioning_dataset  # noqa: E402
from tests.test_hfic_cli import bind_draft, run_cli  # noqa: E402
from tests.test_hfic_temporal_discovery_v1 import _spec  # noqa: E402
from tests.test_live_cohort_discovery_release_series import (  # noqa: E402
    CAMPAIGN_STARTS,
    CAMPAIGN_STOPS,
    _obs,
    _snapshot_for_week,
)

ROOT = Path(__file__).resolve().parents[1]
LATENESS = 300
OFFSETS = {"X300": 300, "Y900": 900, "Y1800": 1800, "Y3600": 3600, "Y7200": 7200}
GIT_SHA = "cd" * 20


def _moment(anchor, point: str) -> str:
    return (anchor + timedelta(seconds=OFFSETS[point] + LATENESS)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _timed(mint: str, point: str, field: str, value: str, anchor) -> dict:
    row = _obs(mint, point, anchor.strftime("%Y-%m-%dT%H:%M:%SZ"))
    stamp = _moment(anchor, point)
    row["field_id"] = field
    row["typed_value"] = value
    row["state"] = "OBSERVED"
    row["missing_reason"] = None
    row["event_time"] = stamp
    row["first_reliable_available_at"] = stamp
    row["request_started_at"] = stamp
    row["response_received_at"] = stamp
    return row


def _publish(data_root: Path, workspace: Path, week: int = 0) -> None:
    data_root.mkdir(parents=True, exist_ok=True)
    admission = CAMPAIGN_STARTS + timedelta(days=7 * week)
    as_of = admission + timedelta(days=10)
    cohort_id = cohort_id_for_admission(
        admission,
        starts_at=CAMPAIGN_STARTS,
        stops_admitting_at=CAMPAIGN_STOPS,
    )
    assert cohort_id is not None
    snapshot = _snapshot_for_week(week)
    snapshot["allowed_lateness_seconds"] = LATENESS
    if week == 0:
        prices = {"X300": "1.0", "Y900": "1.2", "Y1800": "1.5", "Y3600": "1.2"}
        for member in snapshot["members"]:
            if member["mint"] == "MintW0A":
                member["candidate_state"] = "X_ELIGIBLE"
        for obs in snapshot["observations"]:
            if obs["mint"] == "MintW0A" and obs["point_id"] in prices:
                stamp = _moment(admission, obs["point_id"])
                obs["typed_value"] = prices[obs["point_id"]]
                obs["event_time"] = stamp
                obs["first_reliable_available_at"] = stamp
            if obs["mint"] == "MintW0A" and obs["point_id"] == "Y7200":
                stamp = _moment(admission, "Y7200")
                obs["typed_value"] = "1.44"
                obs["state"] = "OBSERVED"
                obs["missing_reason"] = None
                obs["event_time"] = stamp
                obs["first_reliable_available_at"] = stamp
        snapshot["observations"].extend(
            [
                _timed("MintW0A", "X300", LIQUIDITY, "10000", admission),
                _timed("MintW0A", "Y1800", LIQUIDITY, "10000", admission),
                _timed("MintW0A", "Y3600", LIQUIDITY, "9000", admission),
            ]
        )
    observation_root = workspace / f"observation-rdp-{week}"
    release_root = workspace / f"release-{week}"
    write_observation_rdp_source(observation_root, snapshot, cohort_id=cohort_id)
    seal_live_cohort(
        observation_rdp_root=observation_root,
        cohort_id=cohort_id,
        release_root=release_root,
        sealed_at=as_of,
        as_of=as_of,
    )
    imported = import_live_cohort(
        release_root=release_root,
        data_root=data_root,
        import_time=as_of + timedelta(hours=1),
    )
    assert imported["status"] == "IMPORTED"


class TemporalVerticalTests(unittest.TestCase):
    def test_published_journal_reaches_document_runner_readback(self) -> None:
        spec = _spec(cost_profile=None)
        simple = _spec(
            search_tier="SIMPLE_SCREEN",
            query_id="vertical-simple",
            features=[_spec()["features"][0]],
            all=[{"feature": "impulse", "op": "gte", "value": 0.0}],
            cost_profile=None,
        )
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = workspace / "rdp"
            _publish(data_root, workspace)
            publish_commissioning_dataset(data_root)
            binding = resolve_published_discovery_binding(data_root)
            self.assertTrue(binding["holdout_derived_from_discovery_contract"])
            self.assertEqual(binding["cohorts"][0]["schedule_lateness_seconds"], LATENESS)
            preflight = run_cli(
                "preflight",
                "--discovery-contract",
                "--owner-focus",
                "ORDINARY-TEMPORAL-VERTICAL",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            receipt = json.loads(preflight.stdout)
            journal = str(receipt["search_key_sha256"])
            preview_path = workspace / "preview.json"
            second_preview = workspace / "preview-2.json"
            third_preview = workspace / "preview-3.json"
            for path, seed in (
                (preview_path, "vertical-seed"),
                (second_preview, "vertical-seed-2"),
                (third_preview, "vertical-seed-3"),
            ):
                path.write_text(
                    json.dumps(
                        {
                            "decision": {"point_id": "Y3600"},
                            "schedule": {
                                "lateness_seconds": LATENESS,
                                "points": ["X300", "Y900", "Y1800", "Y3600"],
                            },
                            "seed": seed,
                        }
                    ),
                    encoding="utf-8",
                )

            def preview(path: Path) -> object:
                return run_cli(
                    "discovery-preview",
                    "--spec",
                    str(path),
                    "--store",
                    str(data_root),
                    "--journal-scope",
                    journal,
                    "--prior-preview-hash",
                    "",
                    "--format",
                    "json",
                    data_root=data_root,
                )

            first_preview = preview(preview_path)
            self.assertEqual(first_preview.returncode, 0, first_preview.stderr)
            self.assertFalse(json.loads(first_preview.stdout)["target_included"])
            second = preview(second_preview)
            self.assertEqual(second.returncode, 0, second.stderr)
            third = preview(third_preview)
            self.assertNotEqual(third.returncode, 0)
            self.assertIn("PREVIEW_ENVELOPE_EXHAUSTED", third.stderr)
            scope = {
                "population": "BASE_X",
                "decision_timestamp": "Y3600",
                "target": temporal_target_label(simple),
                "estimand": "price_relative_proxy",
                "explanatory_condition": "simple",
                "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
                "representation_scope": "TEMPORAL_PRICE_LIQUIDITY",
            }
            simple_path = workspace / "simple.json"
            compound_path = workspace / "compound.json"
            scope_path = workspace / "scope.json"
            simple_path.write_text(json.dumps(simple), encoding="utf-8")
            scope["target"] = temporal_target_label(spec)
            scope["explanatory_condition"] = "compound"
            compound_path.write_text(json.dumps(spec), encoding="utf-8")
            scope_path.write_text(json.dumps(scope), encoding="utf-8")

            def execute(path: Path) -> dict:
                completed = run_cli(
                    "discovery-execute",
                    "--store",
                    str(data_root),
                    "--spec",
                    str(path),
                    "--candidate-scope",
                    str(scope_path),
                    "--journal-scope",
                    journal,
                    "--format",
                    "json",
                    data_root=data_root,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                return json.loads(completed.stdout)

            simple_evidence = execute(simple_path)
            self.assertEqual(simple_evidence["queries"][0]["search_tier"], "SIMPLE_SCREEN")
            self.assertAlmostEqual(simple_evidence["result"]["mean_target"], 0.2, places=9)
            compound_evidence = execute(compound_path)
            self.assertEqual(compound_evidence["queries"][0]["search_tier"], "COMPOUND_SCREEN")
            self.assertTrue(compound_evidence["tier_progress"]["compound_executed"])
            self.assertTrue(compound_evidence["tier_progress"]["simple_executed"])
            self.assertAlmostEqual(compound_evidence["result"]["mean_target"], 0.2, places=9)
            frozen_input = compound_evidence["result"]["experiment_recipe"]["frozen_input"]
            self.assertEqual(
                frozen_input[0]["observations_sha256"],
                binding["cohorts"][0]["observations_sha256"],
            )
            self.assertEqual(frozen_input[0]["schedule_lateness_seconds"], LATENESS)
            store = ResearchStore(data_root)
            intents = []
            for record in store.iter_committed_records():
                kind = getattr(record.record_kind, "value", record.record_kind)
                if kind != "RESEARCH_ARTIFACT":
                    continue
                wrapper = json.loads(record.payload_json)
                raw_body = wrapper.get("payload_canonical") if isinstance(wrapper, dict) else None
                if not isinstance(raw_body, str):
                    continue
                body = json.loads(raw_body)
                if body.get("artifact_kind") == "DISCOVERY_QUERY_INTENT":
                    intents.append(body["spec_sha256"])
            self.assertIn(compound_evidence["result"]["spec_sha256"], intents)
            loaded = load_admitted_partition_rows(
                data_root=data_root,
                binding_doc=None,
                partitions=None,
                census_path=None,
                observations_path=None,
            )
            with patch(
                "solana_alpha_lab.factory.hfic_grounded_discovery.execute_discovery_from_rows",
                side_effect=AssertionError("evaluator must not rerun a completed look"),
            ):
                replay = run_recorded_discovery_query(
                    store,
                    census=loaded["census"],
                    observations=loaded["observations"],
                    spec=spec,
                    binding=loaded["cohorts"],
                    journal_scope=journal,
                    candidate_scope=scope,
                    git_sha=GIT_SHA,
                )
            self.assertFalse(replay["queries"][0]["new_look"])
            self.assertEqual(replay["result_sha256"], compound_evidence["result_sha256"])
            looks_before_interrupt = len(list_discovery_looks(store, journal))
            interrupt_spec = _spec(
                search_tier="SIMPLE_SCREEN",
                query_id="vertical-interrupt",
                features=[{"name": "mark", "op": "point_value", "field_id": PRICE, "point": "Y3600"}],
                all=[{"feature": "mark", "op": "gte", "value": 0.0}],
                cost_profile=None,
            )
            with patch(
                "solana_alpha_lab.factory.hfic_grounded_discovery.execute_discovery_from_rows",
                side_effect=RuntimeError("interrupt-after-intent"),
            ):
                with self.assertRaises(RuntimeError):
                    run_recorded_discovery_query(
                        store,
                        census=loaded["census"],
                        observations=loaded["observations"],
                        spec=interrupt_spec,
                        binding=loaded["cohorts"],
                        journal_scope=journal,
                        candidate_scope=scope,
                        git_sha=GIT_SHA,
                    )
            self.assertEqual(len(list_discovery_looks(store, journal)), looks_before_interrupt)
            resumed = run_recorded_discovery_query(
                store,
                census=loaded["census"],
                observations=loaded["observations"],
                spec=interrupt_spec,
                binding=loaded["cohorts"],
                journal_scope=journal,
                candidate_scope=scope,
                git_sha=GIT_SHA,
            )
            self.assertTrue(resumed["queries"][0]["new_look"])
            self.assertEqual(resumed["result"]["query_id"], "vertical-interrupt")
            self.assertEqual(len(list_discovery_looks(store, journal)), looks_before_interrupt + 1)
            mismatched = dict(spec)
            mismatched["query_id"] = "lateness-mismatch"
            mismatched["schedule"] = {"lateness_seconds": 0}
            mismatch_path = workspace / "mismatch.json"
            mismatch_path.write_text(json.dumps(mismatched), encoding="utf-8")
            looks_before_mismatch = len(list_discovery_looks(store, journal))
            mismatch_run = run_cli(
                "discovery-execute",
                "--store",
                str(data_root),
                "--spec",
                str(mismatch_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertNotEqual(mismatch_run.returncode, 0)
            self.assertIn("SCHEDULE_LATENESS_MISMATCH", mismatch_run.stderr)
            self.assertEqual(len(list_discovery_looks(store, journal)), looks_before_mismatch)
            blanked = [dict(row) for row in loaded["observations"]]
            for row in blanked:
                if row.get("mint") == "MintW0A" and row.get("point_id") == "Y7200":
                    row["event_time"] = None
                    row["observed_at"] = None
            missing_event = execute_discovery_from_rows(
                loaded["census"],
                blanked,
                spec,
                loaded["cohorts"],
            )["summary"]
            self.assertEqual(missing_event["observed_target_n"], 0)
            self.assertIsNone(missing_event["mean_target"])
            conflicted = [dict(row) for row in loaded["observations"]]
            for row in list(conflicted):
                if row.get("mint") == "MintW0A" and row.get("point_id") == "Y7200":
                    twin = dict(row)
                    twin["event_time"] = "2026-01-05T13:00:00Z"
                    conflicted.append(twin)
            event_conflict = execute_discovery_from_rows(
                loaded["census"],
                conflicted,
                spec,
                loaded["cohorts"],
            )["summary"]
            self.assertEqual(event_conflict["observed_target_n"], 0)
            other_release = "ee" * 32
            twin_census = [dict(row) for row in loaded["census"]]
            twin_census.append({**twin_census[0], "mint": "MintW0A", "release_id": other_release})
            twin_rows = [dict(row) for row in loaded["observations"]]
            for row in list(loaded["observations"]):
                if row.get("mint") != "MintW0A":
                    continue
                copied = dict(row)
                copied["release_id"] = other_release
                if copied.get("point_id") == "Y7200":
                    copied["typed_value"] = "9"
                twin_rows.append(copied)
            twin_binding = list(loaded["cohorts"]) + [
                {**loaded["cohorts"][0], "release_id": other_release}
            ]
            conflict = execute_discovery_from_rows(twin_census, twin_rows, spec, twin_binding)["summary"]
            reordered = execute_discovery_from_rows(
                list(reversed(twin_census)),
                list(reversed(twin_rows)),
                spec,
                twin_binding,
            )["summary"]
            self.assertGreaterEqual(conflict["integrity_conflict_count"], 1)
            self.assertIsNone(conflict["mean_target"])
            self.assertEqual(reordered["integrity_conflict_count"], conflict["integrity_conflict_count"])
            self.assertEqual(reordered["mean_target"], conflict["mean_target"])
            self.assertEqual(reordered["unique_decision_n"], conflict["unique_decision_n"])
            source = json.loads(
                (ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text(encoding="utf-8")
            )
            card = dict(source["candidates"][0])
            card.update(
                {
                    "population": "BASE_X",
                    "decision_timestamp": "Y3600",
                    "target": scope["target"],
                    "estimand": scope["estimand"],
                    "explanatory_condition": scope["explanatory_condition"],
                    "representation_scope": scope["representation_scope"],
                }
            )
            evidence = dict(compound_evidence)
            evidence["search_exhausted"] = True
            evidence["tier_decision"] = "WORTHY_SIMPLE"
            draft = bind_draft({**source, "candidates": [card]}, receipt)
            draft.pop("runner_up_candidate_ref", None)
            draft.pop("strongest_rejected_alternative", None)
            draft["selected_candidate_ref"] = card["label"]
            draft["grounded_evidence"] = evidence
            draft_path = workspace / "draft.json"
            receipt_path = workspace / "preflight.json"
            draft_path.write_text(json.dumps(draft), encoding="utf-8")
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            persisted = run_cli(
                "persist-draft",
                "--draft",
                str(draft_path),
                "--preflight-receipt",
                str(receipt_path),
                "--representation-id",
                "BASE",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(persisted.returncode, 0, persisted.stderr)
            resume_run = run_cli(
                "preflight",
                "--discovery-contract",
                "--owner-focus",
                "ORDINARY-TEMPORAL-VERTICAL",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(resume_run.returncode, 0, resume_run.stderr)
            resume_receipt = json.loads(resume_run.stdout)
            self.assertEqual(resume_receipt.get("action"), "RESUME_EXISTING_SESSION")
            resume_path = workspace / "resume.json"
            resume_path.write_text(json.dumps(resume_receipt), encoding="utf-8")
            frozen_run = run_cli(
                "freeze",
                "--draft",
                str(draft_path),
                "--preflight-receipt",
                str(resume_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(frozen_run.returncode, 0, frozen_run.stderr)
            frozen = json.loads(frozen_run.stdout)
            handed = frozen["critic_input_packet"]["grounded_evidence"]
            self.assertEqual(handed["result_refs"], compound_evidence["result_refs"])
            self.assertEqual(handed["result"]["spec_sha256"], compound_evidence["result"]["spec_sha256"])
            self.assertTrue(handed["tier_progress"]["compound_executed"])
            progress = assess_tier_progress(list_discovery_looks(store, journal), freeze_worthy=True)
            self.assertTrue(progress["search_exhausted_allowed"])
            with self.assertRaises(GroundedDiscoveryError):
                assert_search_exhaustion_claim(
                    assess_tier_progress([], freeze_worthy=False),
                    claim_search_exhausted=True,
                )
            experiment = offline_v1_1_spec()
            experiment["capability_id"] = "CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001"
            experiment["capabilities"] = ["CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001"]
            experiment["parameters"] = {
                "temporal_recipe": compound_evidence["result"]["experiment_recipe"]
            }
            decision = classify_lane(
                {
                    "experiment_spec": experiment,
                    "hypothesis_definition_sha256": HYPOTHESIS_DEFINITION_SHA256,
                },
                root=ROOT,
                data_root=data_root,
                as_of=AS_OF,
            )
            self.assertEqual(decision.terminal, "FAST_LANE_READY", decision.reason_codes)
            ops = OperationalStore(data_root / "ops" / "operational_state.sqlite")
            try:
                result = DocumentRunner(root=ROOT, store=ops).start_document(
                    experiment,
                    spec_sha256="cd" * 32,
                    run_context=RunContext(
                        data_root=data_root,
                        hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                        lane_decision=decision,
                    ),
                )
            finally:
                ops.close()
            self.assertEqual(result["status"], "COMPLETE", result)
            self.assertEqual(result["provider_calls_actual"], 0)
            run_id = str(result["run_id_or_null"])
            artifact = (
                data_root
                / "research"
                / "artifacts"
                / "results"
                / f"RESULT-ARTIFACT-{run_id.removeprefix('RUN-')}.json"
            )
            saved = json.loads(artifact.read_text(encoding="utf-8"))
            saved_summary = saved["capability_result"]["summary"]
            self.assertEqual(saved_summary["spec_sha256"], compound_evidence["result"]["spec_sha256"])
            self.assertAlmostEqual(saved_summary["mean_target"], 0.2, places=9)
            self.assertEqual(
                saved_summary["experiment_recipe"]["frozen_input"][0]["observations_sha256"],
                frozen_input[0]["observations_sha256"],
            )
            passport = None
            for record in ResearchStore(data_root).iter_committed_records():
                kind = getattr(record.record_kind, "value", record.record_kind)
                if kind != "RUN_COMPLETED":
                    continue
                body = json.loads(record.payload_json)
                if body.get("run_id") == run_id:
                    passport = body
            self.assertIsNotNone(passport)
            assert passport is not None
            self.assertEqual(passport["run_key_sha256"], decision.run_key_sha256)
            self.assertEqual(passport["experiment_spec_sha256"], "cd" * 32)
            self.assertEqual(passport["as_of"], experiment["as_of"])
            self.assertEqual(passport["availability_cutoff"], experiment["availability_cutoff"])
            self.assertEqual(passport["result_artifact_id"], f"RESULT-ARTIFACT-{run_id.removeprefix('RUN-')}")
            cohort = binding["cohorts"][0]
            obs_path = data_root / cohort["observations_rel"]
            original = obs_path.read_bytes()
            obs_path.write_bytes(original + b"\x00")
            mismatch = DocumentRunner(
                root=ROOT,
                store=OperationalStore(data_root / "ops" / "operational_state.sqlite"),
            )
            try:
                blocked = mismatch.start_document(
                    experiment,
                    spec_sha256="ce" * 32,
                    run_context=RunContext(
                        data_root=data_root,
                        hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                        lane_decision=decision,
                    ),
                )
            finally:
                mismatch.store.close()
            self.assertEqual(blocked["status"], "FAILED_INFRA")
            self.assertIn("FROZEN_INPUT_MISMATCH", blocked["reason_codes"])
            reread = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertAlmostEqual(
                reread["capability_result"]["summary"]["mean_target"],
                0.2,
                places=9,
            )
            obs_path.write_bytes(original)
            _publish(data_root, workspace, week=1)
            rebound = resolve_published_discovery_binding(data_root)
            self.assertEqual(len(rebound["cohorts"]), 2)
            self.assertNotEqual(
                rebound["cohorts"][1]["observations_sha256"],
                frozen_input[0]["observations_sha256"],
            )
            ops_again = OperationalStore(data_root / "ops" / "operational_state.sqlite")
            try:
                again = DocumentRunner(root=ROOT, store=ops_again).start_document(
                    experiment,
                    spec_sha256="cd" * 32,
                    run_context=RunContext(
                        data_root=data_root,
                        hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                        lane_decision=decision,
                    ),
                )
            finally:
                ops_again.close()
            self.assertEqual(again["status"], "COMPLETE", again)
            fresh = execute(compound_path)
            self.assertNotEqual(fresh["data_binding_sha256"], compound_evidence["data_binding_sha256"])
            self.assertEqual(
                json.loads(artifact.read_text(encoding="utf-8"))["capability_result"]["summary"]["mean_target"],
                saved_summary["mean_target"],
            )


if __name__ == "__main__":
    unittest.main()
