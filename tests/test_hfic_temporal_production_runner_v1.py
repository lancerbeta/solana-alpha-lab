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
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
    schedule_sha256,
    validate_observation_schedule,
)
from solana_alpha_lab.factory.run_passport import experiment_spec_sha256  # noqa: E402
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
    ACTIVATION,
    CAMPAIGN_STARTS,
    CAMPAIGN_STOPS,
    _obs,
    _snapshot_for_week,
)

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_LATENESS = int(
    load_observation_schedule(
        Path(__file__).resolve().parents[1],
        "tests/fixtures/observation_schedule/x300_y900.yaml",
    )["x_point"]["allowed_lateness_seconds"]
)
OFFSETS = {"X300": 300, "Y900": 900, "Y1800": 1800, "Y3600": 3600, "Y7200": 7200}
GIT_SHA = "cd" * 20


def _schedule() -> dict:
    document = load_observation_schedule(
        ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
    )
    document = dict(document)
    document.pop("schedule_sha256", None)
    document["activation"] = {
        **dict(document.get("activation") or {}),
        "starts_at": CAMPAIGN_STARTS.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stops_admitting_at": CAMPAIGN_STOPS.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    document["y_points"] = [
        {
            "point_id": point_id,
            "due_offset_seconds": offset,
            "allowed_lateness_seconds": DOCUMENT_LATENESS,
            "bundle_ids": ["BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-001"],
        }
        for point_id, offset in OFFSETS.items()
        if point_id != "X300"
    ]
    validated = validate_observation_schedule(document, root=ROOT)
    validated["schedule_sha256"] = schedule_sha256(validated)
    return validated


def _moment(anchor, point: str) -> str:
    return (anchor + timedelta(seconds=OFFSETS[point] + DOCUMENT_LATENESS)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


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


def _publish(
    data_root: Path,
    workspace: Path,
    week: int = 0,
    *,
    with_schedule: bool = True,
    snapshot_transport: str | None = None,
) -> None:
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
    schedule = _schedule() if with_schedule else None
    if schedule is not None:
        snapshot["schedule_sha256"] = schedule["schedule_sha256"]
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
    if snapshot_transport in {"new", "legacy"}:
        from solana_alpha_lab.factory.hfic_temporal_discovery import (
            stamp_provider_reported_snapshot_transport,
        )

        snapshot["observations"] = stamp_provider_reported_snapshot_transport(
            snapshot["observations"],
            include_explicit_policy=(snapshot_transport == "new"),
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
    if schedule is not None and week == 0:
        from solana_alpha_lab.factory.observation_panel_publisher import (
            persist_observation_schedule,
        )
        from tests.test_live_cohort_discovery_release_series import PRODUCER

        persist_observation_schedule(
            data_root=data_root,
            schedule=schedule,
            now=as_of,
            producer_git_sha=PRODUCER,
            activation_id=ACTIVATION,
        )


def _freeze_draft(receipt: dict, evidence: dict, *, select: bool, worthy: bool) -> dict:
    source = json.loads(
        (ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text(encoding="utf-8")
    )
    card = dict(source["candidates"][0])
    card.update(
        {
            "population": "BASE_X",
            "decision_timestamp": "Y3600",
            "target": evidence["candidate_scope"]["target"]
            if isinstance(evidence.get("candidate_scope"), dict)
            else card.get("target"),
            "estimand": "price_relative_proxy",
            "explanatory_condition": "simple" if worthy or not select else "compound",
            "representation_scope": "TEMPORAL_PRICE_LIQUIDITY",
        }
    )
    body = dict(evidence)
    body.pop("search_exhausted", None)
    if worthy:
        body["tier_decision"] = "WORTHY_SIMPLE"
    if select:
        draft = bind_draft({**source, "candidates": [card]}, receipt)
        draft.pop("runner_up_candidate_ref", None)
        draft.pop("strongest_rejected_alternative", None)
        draft["selected_candidate_ref"] = card["label"]
    else:
        draft = bind_draft(source, receipt)
        draft.pop("selected_candidate_ref", None)
    draft["grounded_evidence"] = body
    return draft


def _bind_experiment(recipe: dict, data_root: Path) -> dict:
    experiment = offline_v1_1_spec()
    experiment["capability_id"] = "CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001"
    experiment["capabilities"] = ["CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001"]
    experiment["parameters"] = {"temporal_recipe": recipe}
    kept = [
        item for item in experiment["data_bindings"] if item["source_kind"] != "DATASET_MANIFEST"
    ]
    seen: set[str] = set()
    for item in recipe["frozen_input"]:
        manifest_id = str(item.get("dataset_manifest_id") or "")
        if not manifest_id or manifest_id in seen:
            continue
        seen.add(manifest_id)
        manifest = json.loads(
            (data_root / "datasets" / "manifests" / f"{manifest_id}.json").read_text(encoding="utf-8")
        )
        kept.append(
            {
                "binding_id": f"BINDING-TEMPORAL-CORPUS-{len(seen):03d}",
                "source_kind": "DATASET_MANIFEST",
                "stable_id": manifest_id,
                "expected_content_sha256_or_dataset_fingerprint": manifest["dataset_fingerprint"],
            }
        )
    experiment["data_bindings"] = kept
    return experiment


class TemporalVerticalTests(unittest.TestCase):
    def test_published_journal_reaches_document_runner_readback(self) -> None:
        spec = _spec(cost_profile=None, schedule={"lateness_seconds": DOCUMENT_LATENESS})
        simple = _spec(
            search_tier="SIMPLE_SCREEN",
            query_id="vertical-simple",
            features=[_spec()["features"][0]],
            all=[{"feature": "impulse", "op": "gte", "value": 0.0}],
            cost_profile=None,
            schedule={"lateness_seconds": DOCUMENT_LATENESS},
        )
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = workspace / "rdp"
            _publish(data_root, workspace)
            binding = resolve_published_discovery_binding(data_root)
            self.assertTrue(binding["holdout_derived_from_discovery_contract"])
            point_lateness = binding["cohorts"][0]["schedule_point_lateness"]
            self.assertTrue(point_lateness)
            self.assertTrue(all(value == DOCUMENT_LATENESS for value in point_lateness.values()))
            self.assertNotIn("allowed_lateness_seconds", binding["cohorts"][0])
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
                                "lateness_seconds": DOCUMENT_LATENESS,
                                "points": ["X300", "Y900", "Y1800", "Y3600"],
                            },
                            "seed": seed,
                        }
                    ),
                    encoding="utf-8",
                )

            market = str(receipt["market_evidence_epoch_sha256"])
            operation_path = workspace / "ordinary-operation.json"
            operation_path.write_text(
                json.dumps(
                    {
                        "owner_request_text": "protocol vertical temporal",
                        "owner_focus": "ORDINARY-TEMPORAL-VERTICAL",
                        "journal_scope": journal,
                        "market_evidence_epoch_sha256": market,
                        "spec": spec,
                        "question_text": "vertical",
                        "owner_cap": {"main": None, "adaptive": None, "preview": None},
                        "requested_completion": "LIMITED_RESULT",
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
                    "--operation",
                    str(operation_path),
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
                spec_body = json.loads(path.read_text(encoding="utf-8"))
                execute._n = int(getattr(execute, "_n", 0)) + 1
                op = path.with_suffix(".operation.json")
                op.write_text(
                    json.dumps(
                        {
                            "owner_request_text": f"protocol vertical {spec_body.get('query_id')} {execute._n}",
                            "owner_focus": "ORDINARY-TEMPORAL-VERTICAL",
                            "journal_scope": journal,
                            "market_evidence_epoch_sha256": market,
                            "spec": spec_body,
                            "question_text": str(spec_body.get("query_id")),
                            "owner_cap": {"main": None, "adaptive": None, "preview": None},
                            "requested_completion": "LIMITED_RESULT",
                        }
                    ),
                    encoding="utf-8",
                )
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
                    "--operation",
                    str(op),
                    "--format",
                    "json",
                    data_root=data_root,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                return json.loads(completed.stdout)

            simple_evidence = execute(simple_path)
            self.assertEqual(simple_evidence["queries"][0]["search_tier"], "SIMPLE_SCREEN")
            self.assertAlmostEqual(simple_evidence["result"]["mean_target"], 0.2, places=9)
            self.assertEqual(simple_evidence["result"]["observation_index_passes"], 1)
            from solana_alpha_lab.factory.hfic_session import (
                HficSessionError,
                _assert_temporal_search_closed,
            )

            with self.assertRaises(HficSessionError) as pending:
                _assert_temporal_search_closed(
                    {"grounded_evidence": simple_evidence},
                    ResearchStore(data_root),
                )
            self.assertEqual(str(pending.exception), "SEARCH_EXHAUSTED_WITHOUT_COMPOUND")
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
            self.assertEqual(
                frozen_input[0]["schedule_point_lateness"]["Y3600"],
                DOCUMENT_LATENESS,
            )
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
                schedule={"lateness_seconds": DOCUMENT_LATENESS},
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
            mismatch_op = workspace / "mismatch.operation.json"
            mismatch_op.write_text(
                json.dumps(
                    {
                        "owner_request_text": "protocol lateness mismatch",
                        "owner_focus": "ORDINARY-TEMPORAL-VERTICAL",
                        "journal_scope": journal,
                        "market_evidence_epoch_sha256": market,
                        "spec": mismatched,
                        "question_text": "lateness-mismatch",
                        "owner_cap": {"main": None, "adaptive": None, "preview": None},
                        "requested_completion": "LIMITED_RESULT",
                    }
                ),
                encoding="utf-8",
            )
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
                "--operation",
                str(mismatch_op),
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
            same_release = "dd" * 32
            same_census = [dict(row) for row in loaded["census"]]
            same_census.append({**same_census[0], "mint": "MintW0A", "release_id": same_release})
            same_rows = [dict(row) for row in loaded["observations"]]
            for row in list(loaded["observations"]):
                if row.get("mint") != "MintW0A":
                    continue
                copied = dict(row)
                copied["release_id"] = same_release
                same_rows.append(copied)
            same_binding = list(loaded["cohorts"]) + [
                {**loaded["cohorts"][0], "release_id": same_release}
            ]
            identical = execute_discovery_from_rows(
                same_census,
                same_rows,
                spec,
                same_binding,
            )["summary"]
            self.assertGreaterEqual(identical["duplicate_delivery_count"], 1)
            self.assertEqual(identical["integrity_conflict_count"], 0)
            self.assertAlmostEqual(identical["mean_target"], 0.2, places=9)
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
            self.assertEqual(
                handed["result"]["by_cohort"],
                compound_evidence["result"]["by_cohort"],
            )
            self.assertAlmostEqual(handed["result"]["by_cohort"][0]["mean_target"], 0.2, places=9)
            self.assertTrue(handed["tier_progress"]["compound_executed"])
            self.assertGreaterEqual(len(handed["viewed_queries"]), 2)
            progress = assess_tier_progress(list_discovery_looks(store, journal), freeze_worthy=True)
            self.assertTrue(progress["search_exhausted_allowed"])
            with self.assertRaises(GroundedDiscoveryError):
                assert_search_exhaustion_claim(
                    assess_tier_progress([], freeze_worthy=False),
                    claim_search_exhausted=True,
                )
            experiment = _bind_experiment(
                compound_evidence["result"]["experiment_recipe"],
                data_root,
            )
            spec_hash = experiment_spec_sha256(experiment)
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
                    spec_sha256=spec_hash,
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
                saved_summary["by_cohort"][0]["cohort_id"],
                compound_evidence["result"]["by_cohort"][0]["cohort_id"],
            )
            self.assertAlmostEqual(saved_summary["by_cohort"][0]["mean_target"], 0.2, places=9)
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
            self.assertEqual(passport["experiment_spec_sha256"], spec_hash)
            self.assertEqual(passport["as_of"], experiment["as_of"])
            self.assertEqual(passport["availability_cutoff"], experiment["availability_cutoff"])
            self.assertEqual(passport["result_artifact_id"], f"RESULT-ARTIFACT-{run_id.removeprefix('RUN-')}")
            manifest_binding = next(
                item for item in experiment["data_bindings"] if item["source_kind"] == "DATASET_MANIFEST"
            )
            self.assertTrue(manifest_binding["stable_id"].startswith("dataset-"))
            self.assertIn(manifest_binding["stable_id"], passport["dataset_manifest_ids"])
            self.assertIn(
                manifest_binding["expected_content_sha256_or_dataset_fingerprint"],
                passport["dataset_fingerprints"],
            )
            publish_commissioning_dataset(data_root)
            from solana_alpha_lab.factory.commissioning_fixture import (
                COMMISSIONING_DATASET_MANIFEST_ID,
                commissioning_dataset_fingerprint,
            )
            from solana_alpha_lab.factory.hfic_temporal_discovery import (
                _require_manifest_and_cutoff,
                execute_fixed_time_proxy_capability,
            )

            loader_calls = {"n": 0}

            def _loader(*_args, **_kwargs):
                loader_calls["n"] += 1
                raise AssertionError("value loader")

            def run_blocked(spec: dict):
                loader_calls["n"] = 0
                lane = classify_lane(
                    {
                        "experiment_spec": spec,
                        "hypothesis_definition_sha256": HYPOTHESIS_DEFINITION_SHA256,
                    },
                    root=ROOT,
                    data_root=data_root,
                    as_of=AS_OF,
                )
                with patch(
                    "solana_alpha_lab.factory.hfic_grounded_discovery.load_admitted_partition_rows",
                    side_effect=_loader,
                ):
                    runner = DocumentRunner(
                        root=ROOT,
                        store=OperationalStore(data_root / "ops" / "operational_state.sqlite"),
                    )
                    try:
                        outcome = runner.start_document(
                            spec,
                            spec_sha256=experiment_spec_sha256(spec),
                            run_context=RunContext(
                                data_root=data_root,
                                hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                                lane_decision=lane,
                            ),
                        )
                    finally:
                        runner.store.close()
                self.assertEqual(loader_calls["n"], 0)
                self.assertNotEqual(outcome["status"], "COMPLETE")
                return lane, outcome

            commissioned = json.loads(json.dumps(experiment))
            for item in commissioned["data_bindings"]:
                if item["source_kind"] == "DATASET_MANIFEST":
                    item["stable_id"] = COMMISSIONING_DATASET_MANIFEST_ID
                    item["expected_content_sha256_or_dataset_fingerprint"] = (
                        commissioning_dataset_fingerprint(ROOT)
                    )
            commissioned_lane, commissioned_result = run_blocked(commissioned)
            self.assertEqual(commissioned_lane.terminal, "FAST_LANE_READY", commissioned_lane.reason_codes)
            self.assertEqual(commissioned_result["status"], "FAILED_INFRA")
            self.assertIn("MANIFEST_MISMATCH", commissioned_result["reason_codes"])
            absent = json.loads(json.dumps(experiment))
            absent["data_bindings"] = [
                item for item in absent["data_bindings"] if item["source_kind"] != "DATASET_MANIFEST"
            ]
            absent_lane, absent_result = run_blocked(absent)
            self.assertEqual(absent_lane.terminal, "FAST_LANE_READY", absent_lane.reason_codes)
            self.assertIn("MANIFEST_MISMATCH", absent_result["reason_codes"])
            undeclared = json.loads(json.dumps(experiment))
            extra = dict(undeclared["parameters"]["temporal_recipe"]["frozen_input"][0])
            extra["dataset_manifest_id"] = COMMISSIONING_DATASET_MANIFEST_ID
            undeclared["parameters"]["temporal_recipe"]["frozen_input"].append(extra)
            undeclared_lane, undeclared_result = run_blocked(undeclared)
            self.assertEqual(undeclared_lane.terminal, "FAST_LANE_READY", undeclared_lane.reason_codes)
            self.assertIn("MANIFEST_MISMATCH", undeclared_result["reason_codes"])
            duplicate = json.loads(json.dumps(experiment))
            duplicate["data_bindings"].append(
                dict(next(item for item in duplicate["data_bindings"] if item["source_kind"] == "DATASET_MANIFEST"))
            )
            duplicate["data_bindings"][-1]["binding_id"] = "BINDING-TEMPORAL-CORPUS-DUP"
            duplicate_lane, duplicate_result = run_blocked(duplicate)
            self.assertEqual(duplicate_lane.terminal, "FAST_LANE_READY", duplicate_lane.reason_codes)
            self.assertEqual(duplicate_result["status"], "FAILED_INFRA")
            self.assertIn("MANIFEST_MISMATCH", duplicate_result["reason_codes"])
            wrong = json.loads(json.dumps(experiment))
            for item in wrong["data_bindings"]:
                if item["source_kind"] == "DATASET_MANIFEST":
                    item["expected_content_sha256_or_dataset_fingerprint"] = "ab" * 32
            wrong_lane, wrong_result = run_blocked(wrong)
            self.assertNotEqual(wrong_result["status"], "COMPLETE")
            self.assertIn("EVIDENCE_HASH_MISMATCH", wrong_lane.reason_codes)
            shared = json.loads(json.dumps(experiment))
            shared_frozen = shared["parameters"]["temporal_recipe"]["frozen_input"]
            shared_frozen.append(dict(shared_frozen[0]))
            _require_manifest_and_cutoff(shared, shared_frozen, data_root)
            blank = json.loads(json.dumps(experiment))
            for item in blank["data_bindings"]:
                if item["source_kind"] == "DATASET_MANIFEST":
                    item["expected_content_sha256_or_dataset_fingerprint"] = None
            with patch(
                "solana_alpha_lab.factory.hfic_grounded_discovery.load_admitted_partition_rows",
                side_effect=_loader,
            ):
                for bindings in (absent["data_bindings"], wrong["data_bindings"], blank["data_bindings"]):
                    loader_calls["n"] = 0
                    with self.assertRaises(GroundedDiscoveryError) as wrapped:
                        execute_fixed_time_proxy_capability(
                            {
                                "experiment_recipe": compound_evidence["result"]["experiment_recipe"],
                                "data_bindings": bindings,
                                "availability_cutoff": experiment["availability_cutoff"],
                            },
                            root=ROOT,
                            capture_hooks={"data_root": data_root},
                        )
                    self.assertEqual(str(wrapped.exception), "MANIFEST_MISMATCH")
                    self.assertEqual(loader_calls["n"], 0)
            self.assertEqual(
                json.loads(artifact.read_text(encoding="utf-8"))["capability_result"]["summary"]["mean_target"],
                saved_summary["mean_target"],
            )
            early = _bind_experiment(compound_evidence["result"]["experiment_recipe"], data_root)
            early["availability_cutoff"] = "2020-01-01T00:00:00Z"
            early_decision = classify_lane(
                {
                    "experiment_spec": early,
                    "hypothesis_definition_sha256": HYPOTHESIS_DEFINITION_SHA256,
                },
                root=ROOT,
                data_root=data_root,
                as_of=AS_OF,
            )
            early_runner = DocumentRunner(
                root=ROOT,
                store=OperationalStore(data_root / "ops" / "operational_state.sqlite"),
            )
            try:
                early_result = early_runner.start_document(
                    early,
                    spec_sha256=experiment_spec_sha256(early),
                    run_context=RunContext(
                        data_root=data_root,
                        hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                        lane_decision=early_decision,
                    ),
                )
            finally:
                early_runner.store.close()
            self.assertEqual(early_decision.terminal, "BLOCKED_DATA", early_decision.reason_codes)
            self.assertIn("EVIDENCE_UNAVAILABLE_AT_CUTOFF", early_decision.reason_codes)
            self.assertEqual(early_result["status"], "BLOCKED_DATA")
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
            fresh = execute(compound_path)
            self.assertNotEqual(fresh["data_binding_sha256"], compound_evidence["data_binding_sha256"])
            fresh_hashes = {
                item["observations_sha256"]
                for item in fresh["result"]["experiment_recipe"]["frozen_input"]
            }
            self.assertIn(frozen_input[0]["observations_sha256"], fresh_hashes)
            self.assertGreater(len(fresh_hashes), 1)
            new_experiment = _bind_experiment(fresh["result"]["experiment_recipe"], data_root)
            new_spec_hash = experiment_spec_sha256(new_experiment)
            new_decision = classify_lane(
                {
                    "experiment_spec": new_experiment,
                    "hypothesis_definition_sha256": HYPOTHESIS_DEFINITION_SHA256,
                },
                root=ROOT,
                data_root=data_root,
                as_of=AS_OF,
            )
            self.assertEqual(new_decision.terminal, "FAST_LANE_READY", new_decision.reason_codes)
            self.assertNotEqual(new_decision.run_key_sha256, decision.run_key_sha256)
            ops_again = OperationalStore(data_root / "ops" / "operational_state.sqlite")
            try:
                again = DocumentRunner(root=ROOT, store=ops_again).start_document(
                    new_experiment,
                    spec_sha256=new_spec_hash,
                    run_context=RunContext(
                        data_root=data_root,
                        hypothesis_definition_sha256=HYPOTHESIS_DEFINITION_SHA256,
                        lane_decision=new_decision,
                    ),
                )
            finally:
                ops_again.close()
            self.assertEqual(again["status"], "COMPLETE", again)
            self.assertNotEqual(again["run_id_or_null"], run_id)
            self.assertEqual(
                json.loads(artifact.read_text(encoding="utf-8"))["capability_result"]["summary"]["mean_target"],
                saved_summary["mean_target"],
            )


    def test_draft_v12_omits_selected_ref_and_rejects_empty(self) -> None:
        import jsonschema

        schema = json.loads(
            (ROOT / "catalog/schemas/hypothesis_forge_draft_v1_2.schema.json").read_text(encoding="utf-8")
        )
        draft = json.loads(
            (ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("selected_candidate_ref", schema["required"])
        omitted = dict(draft)
        omitted.pop("selected_candidate_ref")
        jsonschema.validate(omitted, schema)
        empty = dict(draft)
        empty["selected_candidate_ref"] = ""
        with self.assertRaises(jsonschema.ValidationError) as caught:
            jsonschema.validate(empty, schema)
        self.assertEqual(caught.exception.validator, "minLength")
        self.assertEqual(list(caught.exception.absolute_path), ["selected_candidate_ref"])
        self.assertEqual(
            list(caught.exception.schema_path),
            ["properties", "selected_candidate_ref", "minLength"],
        )
        null_draft = dict(draft)
        null_draft["selected_candidate_ref"] = None
        with self.assertRaises(jsonschema.ValidationError) as caught_null:
            jsonschema.validate(null_draft, schema)
        self.assertEqual(caught_null.exception.validator, "type")
        self.assertEqual(list(caught_null.exception.absolute_path), ["selected_candidate_ref"])

    def test_hash_match_does_not_accept_a_non_factory_x300_schedule(self) -> None:
        import pyarrow as pa
        import pyarrow.parquet as pq

        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            schedule_projection_for_census,
        )
        from solana_alpha_lab.factory.observation_panel_publisher import (
            persist_observation_schedule,
        )
        from tests.test_live_cohort_discovery_release_series import PRODUCER

        schedule = _schedule()
        schedule.pop("schedule_sha256", None)
        x_point = dict(schedule["x_point"])
        x_point["allowed_lateness_seconds"] = 180
        schedule["x_point"] = x_point
        validated = validate_observation_schedule(schedule, root=ROOT)
        validated["schedule_sha256"] = schedule_sha256(validated)
        with tempfile.TemporaryDirectory() as raw:
            data_root = Path(raw) / "rdp"
            data_root.mkdir()
            census = data_root / "census.parquet"
            pq.write_table(
                pa.Table.from_pylist(
                    [{"source_schedule_sha256": validated["schedule_sha256"]}]
                ),
                census,
            )
            persist_observation_schedule(
                data_root=data_root,
                schedule=validated,
                now=CAMPAIGN_STARTS,
                producer_git_sha=PRODUCER,
                activation_id=ACTIVATION,
            )
            projected = schedule_projection_for_census(data_root, census)
        self.assertTrue(projected["schedule_hash_matches"])
        self.assertEqual(projected["schedule_context_gap"], "CANONICAL_X300_SCHEDULE_INCOMPATIBLE")
        self.assertNotIn("schedule_point_lateness", projected)

    def test_cli_freeze_pending_worthy_simple_and_no_worthy(self) -> None:
        simple = _spec(
            search_tier="SIMPLE_SCREEN",
            query_id="freeze-simple",
            features=[_spec()["features"][0]],
            all=[{"feature": "impulse", "op": "gte", "value": 0.0}],
            cost_profile=None,
            schedule={"lateness_seconds": DOCUMENT_LATENESS},
        )
        compound = _spec(
            cost_profile=None,
            query_id="freeze-compound",
            schedule={"lateness_seconds": DOCUMENT_LATENESS},
        )
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = workspace / "rdp"
            _publish(data_root, workspace)
            simple_path = workspace / "simple.json"
            compound_path = workspace / "compound.json"
            scope_path = workspace / "scope.json"
            simple_path.write_text(json.dumps(simple), encoding="utf-8")
            compound_path.write_text(json.dumps(compound), encoding="utf-8")
            scope_path.write_text(
                json.dumps(
                    {
                        "population": "BASE_X",
                        "decision_timestamp": "Y3600",
                        "target": temporal_target_label(simple),
                        "estimand": "price_relative_proxy",
                        "explanatory_condition": "simple",
                        "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
                        "representation_scope": "TEMPORAL_PRICE_LIQUIDITY",
                    }
                ),
                encoding="utf-8",
            )

            def focus(name: str) -> dict:
                completed = run_cli(
                    "preflight",
                    "--discovery-contract",
                    "--owner-focus",
                    name,
                    "--format",
                    "json",
                    data_root=data_root,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                return json.loads(completed.stdout)

            def execute(path: Path, receipt: dict) -> dict:
                spec_body = json.loads(path.read_text(encoding="utf-8"))
                op = path.with_suffix(".operation.json")
                op.write_text(
                    json.dumps(
                        {
                            "owner_request_text": f"protocol focus {spec_body.get('query_id')}",
                            "owner_focus": str(receipt.get("owner_focus") or "AUTO"),
                            "journal_scope": str(receipt["search_key_sha256"]),
                            "market_evidence_epoch_sha256": str(receipt["market_evidence_epoch_sha256"]),
                            "spec": spec_body,
                            "question_text": str(spec_body.get("query_id")),
                            "owner_cap": {"main": None, "adaptive": None, "preview": None},
                            "requested_completion": "LIMITED_RESULT",
                        }
                    ),
                    encoding="utf-8",
                )
                completed = run_cli(
                    "discovery-execute",
                    "--store",
                    str(data_root),
                    "--spec",
                    str(path),
                    "--candidate-scope",
                    str(scope_path),
                    "--journal-scope",
                    str(receipt["search_key_sha256"]),
                    "--operation",
                    str(op),
                    "--format",
                    "json",
                    data_root=data_root,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                return json.loads(completed.stdout)

            def freeze(name: str, evidence: dict, *, select: bool, worthy: bool) -> object:
                resume = focus(name)
                draft = _freeze_draft(resume, evidence, select=select, worthy=worthy)
                draft_path = workspace / f"{name}-draft.json"
                receipt_path = workspace / f"{name}-receipt.json"
                draft_path.write_text(json.dumps(draft), encoding="utf-8")
                receipt_path.write_text(json.dumps(resume), encoding="utf-8")
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
                again = focus(name)
                again_path = workspace / f"{name}-resume.json"
                again_path.write_text(json.dumps(again), encoding="utf-8")
                return run_cli(
                    "freeze",
                    "--draft",
                    str(draft_path),
                    "--preflight-receipt",
                    str(again_path),
                    "--format",
                    "json",
                    data_root=data_root,
                )

            pending_receipt = focus("ORDINARY-TEMPORAL-PENDING")
            pending_evidence = execute(simple_path, pending_receipt)
            pending_freeze = freeze(
                "ORDINARY-TEMPORAL-PENDING",
                pending_evidence,
                select=False,
                worthy=False,
            )
            self.assertNotEqual(pending_freeze.returncode, 0)
            self.assertIn("SEARCH_EXHAUSTED_WITHOUT_COMPOUND", pending_freeze.stderr)
            self.assertNotIn("NO_WORTHY_HYPOTHESIS", pending_freeze.stdout)
            worthy_receipt = focus("ORDINARY-TEMPORAL-WORTHY")
            worthy_evidence = execute(simple_path, worthy_receipt)
            worthy_freeze = freeze(
                "ORDINARY-TEMPORAL-WORTHY",
                worthy_evidence,
                select=True,
                worthy=True,
            )
            self.assertEqual(worthy_freeze.returncode, 0, worthy_freeze.stderr)
            worthy_body = json.loads(worthy_freeze.stdout)
            self.assertNotEqual(worthy_body.get("critic_terminal"), "NO_WORTHY_HYPOTHESIS")
            closed_receipt = focus("ORDINARY-TEMPORAL-CLOSED")
            execute(simple_path, closed_receipt)
            closed_evidence = execute(compound_path, closed_receipt)
            closed_freeze = freeze(
                "ORDINARY-TEMPORAL-CLOSED",
                closed_evidence,
                select=False,
                worthy=False,
            )
            self.assertEqual(closed_freeze.returncode, 0, closed_freeze.stderr)
            self.assertEqual(json.loads(closed_freeze.stdout).get("critic_terminal"), "NO_WORTHY_HYPOTHESIS")

    def test_three_current_cohorts_without_a_schedule_do_not_invent_lateness(self) -> None:
        """Negative fixtures: three synthetic publications with no schedule document.

        These are not the live market corpus. A missing document is
        CANONICAL_SCHEDULE_UNBOUND, which is not corpus readiness.
        """
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            schedule_projection_for_census,
        )

        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = workspace / "rdp"
            for week in range(3):
                _publish(data_root, workspace, week=week, with_schedule=False)
            binding = resolve_published_discovery_binding(data_root)
            self.assertEqual(len(binding["cohorts"]), 3)
            for cohort in binding["cohorts"]:
                observations = data_root / cohort["observations_rel"]
                before = observations.read_bytes()
                projected = schedule_projection_for_census(
                    data_root, data_root / cohort["census_rel"]
                )
                self.assertEqual(projected["schedule_context_gap"], "CANONICAL_SCHEDULE_UNBOUND")
                self.assertEqual(observations.read_bytes(), before)
                self.assertNotIn("schedule_point_lateness", projected)


if __name__ == "__main__":
    unittest.main()
