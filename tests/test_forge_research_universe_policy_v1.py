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


def _change_published_observation(data_root: Path) -> None:
    """Rewrite one sealed observation and the publication hashes that name it."""

    import pyarrow as pa
    import pyarrow.parquet as pq

    from solana_alpha_lab.factory.live_cohort_discovery_release import (
        load_live_corpus_lineage,
        write_live_corpus_lineage,
    )
    from solana_alpha_lab.factory.live_cohort_source_bundle import sha256_file_streaming
    from solana_alpha_lab.factory.live_corpus_manifest_publish import (
        COMMIT_POINT_KIND,
        _build_dataset,
        _build_receipt,
        _commit_canonical_root,
        _load_dataset_manifest,
        _load_partitions_for_dataset,
    )
    from solana_alpha_lab.storage.manifests import (
        build_partition_manifest,
        compute_dataset_fingerprint,
    )

    lineage = load_live_corpus_lineage(data_root)
    cohorts = [item for item in lineage.get("cohorts") or [] if isinstance(item, dict)]
    if not cohorts:
        raise AssertionError("published cohort missing")
    cohort = cohorts[-1]
    path = data_root / str(cohort["obs_rel"])
    table = pq.read_table(path)
    values = table.column("typed_value").to_pylist()
    if not values:
        raise AssertionError("published observations empty")
    values[0] = "9" if values[0] != "9" else "8"
    column = table.schema.get_field_index("typed_value")
    table = table.set_column(column, "typed_value", pa.array(values, type=pa.string()))
    pq.write_table(table, path)
    file_sha = sha256_file_streaming(path)
    cohort["observations_sha256"] = file_sha
    write_live_corpus_lineage(data_root, lineage)
    manifest_id = str(cohort["dataset_manifest_id"])
    dataset = _load_dataset_manifest(data_root, manifest_id)
    partitions = _load_partitions_for_dataset(data_root, manifest_id)
    replaced = False
    rebuilt: list = []
    for part in partitions:
        if part.logical_location != cohort["obs_rel"]:
            rebuilt.append(part)
            continue
        replaced = True
        old_path = data_root / "datasets" / "manifests" / "partitions" / f"{part.partition_manifest_id}.json"
        rebuilt.append(build_partition_manifest(
            dataset_id=dataset.dataset_id,
            dataset_version=dataset.dataset_version,
            partition_id=part.partition_id,
            logical_location=part.logical_location,
            file_sha256=file_sha,
            content_sha256=part.content_sha256,
            row_count=part.row_count,
            min_event_time=part.min_event_time,
            max_event_time=part.max_event_time,
            min_available_to_strategy_at=part.min_available_to_strategy_at,
            max_available_to_strategy_at=part.max_available_to_strategy_at,
            first_reliable_available_at=part.first_reliable_available_at,
            created_at=part.created_at,
        ))
        if old_path.is_file():
            old_path.unlink()
        size_path = data_root / "datasets" / "manifests" / "partitions" / f"{part.partition_id}.bytes"
        if size_path.is_file():
            size_path.unlink()
    if not replaced:
        raise AssertionError("observation partition missing")
    receipt_path = data_root / "datasets" / "manifests" / f"{manifest_id}.validation.json"
    previous = json.loads(receipt_path.read_text(encoding="utf-8"))
    fingerprint = compute_dataset_fingerprint(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.dataset_version,
        schema_id=dataset.schema_id,
        schema_sha256=dataset.schema_sha256,
        partitions=rebuilt,
    )
    _receipt, receipt_bytes, receipt_sha = _build_receipt(
        dataset_version=dataset.dataset_version,
        schema_sha256=dataset.schema_sha256,
        composition=previous["corpus_composition"],
        partitions=rebuilt,
        dataset_fingerprint=fingerprint,
        generation_reason=str(previous.get("generation_reason") or "OBSERVATION_REVISION"),
        published_at=dataset.created_at,
        superseded_dataset_manifest_id=previous.get("superseded_dataset_manifest_id"),
    )
    revised = _build_dataset(
        dataset_version=dataset.dataset_version,
        schema_sha256=dataset.schema_sha256,
        partitions=rebuilt,
        validation_receipt_sha256=receipt_sha,
        published_at=dataset.created_at,
        generation_task_id=dataset.generation_task_id,
        generation_run_id=dataset.generation_run_id,
    )
    manifests = data_root / "datasets" / "manifests"
    for name in (f"{manifest_id}.validation.json", f"{manifest_id}.json", f"{manifest_id}.published"):
        target = manifests / name
        if target.is_file():
            target.unlink()
    labels = json.loads((manifests / f"{manifest_id}.labels.json").read_text(encoding="utf-8"))
    latest = previous["corpus_composition"][-1]
    _commit_canonical_root(
        data_root=data_root,
        dataset=revised,
        partitions=rebuilt,
        receipt_bytes=receipt_bytes,
        published={
            "commit_point": COMMIT_POINT_KIND,
            "cohort_id": latest.get("cohort_id"),
            "corpus_version": labels.get("corpus_version"),
            "cumulative_cohort_count": len(previous["corpus_composition"]),
            "dataset_fingerprint": revised.dataset_fingerprint,
            "dataset_manifest_id": revised.dataset_manifest_id,
            "metadata_clock_at": previous.get("published_at"),
            "published_at": previous.get("published_at"),
            "release_id": latest.get("release_id"),
        },
    )


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
            twenty_root = workspace / "twenty"
            shutil.copytree(data_root, twenty_root)
            self.assertEqual(_apply(twenty_root, workspace, "50", "20000")["min_liquidity_usd"], "20000")
            twenty_op = workspace / "twenty-op.json"
            twenty_op.write_text(json.dumps(_operation(
                spec, focus=FOCUS, journal=journal, market=market,
                text="Synthetic 20k admission on the same code path",
                cap={"main": 1, "adaptive": 0, "preview": 1},
            )), encoding="utf-8")
            twenty = run_cli(
                "discovery-execute", "--store", str(twenty_root), "--spec", str(spec_path),
                "--candidate-scope", str(scope_path), "--journal-scope", journal,
                "--operation", str(twenty_op), "--format", "json", data_root=twenty_root,
            )
            self.assertEqual(twenty.returncode, 0, twenty.stdout + twenty.stderr)
            twenty_result = json.loads(twenty.stdout)["result"]["universe_policy"]
            self.assertEqual(twenty_result["min_liquidity_usd"], "20000")
            self.assertLess(twenty_result["n_pass"], 3)
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
            self.assertEqual(
                json.loads(pending_preview.stdout)["next_action"],
                "FINISH_OPEN_FORGE_OPERATION_THEN_PREVIEW",
            )
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
            adapt_op = workspace / "adapt-op.json"
            adapt_body = _operation(
                spec, focus=FOCUS, journal=journal, market=market,
                text="Same question after the live profile moves to 20k",
                cap={"main": 0, "adaptive": 1, "preview": 0},
            )
            adapt_body["parent_operation_sha256"] = evidence["operation_sha256"]
            adapt_op.write_text(json.dumps(adapt_body), encoding="utf-8")
            adapted = run_cli(
                "discovery-execute", "--store", str(data_root), "--spec", str(spec_path),
                "--candidate-scope", str(scope_path), "--journal-scope", journal,
                "--operation", str(adapt_op), "--format", "json", data_root=data_root,
            )
            self.assertEqual(adapted.returncode, 0, adapted.stdout + adapted.stderr)
            adapted_body = json.loads(adapted.stdout)
            self.assertEqual(adapted_body["queries"][0]["look_class"], "ADAPTIVE")
            self.assertTrue(adapted_body["queries"][0]["new_look"])
            self.assertEqual(adapted_body["scientific_look_delta"]["main"], 0)
            self.assertEqual(adapted_body["result"]["universe_policy"]["min_liquidity_usd"], "20000")
            self.assertEqual(adapted_body["result"]["universe_policy"]["n_pass"], 0)
            self.assertLessEqual(
                adapted_body["result"]["matched_n"],
                adapted_body["result"]["universe_policy"]["n_pass"],
            )
            self.assertNotEqual(adapted_body["result_refs"], evidence["result_refs"])
            grown_root = workspace / "grown"
            shutil.copytree(data_root, grown_root)
            _change_published_observation(grown_root)
            grown_op = workspace / "grown-op.json"
            grown_op.write_text(json.dumps(_operation(
                spec, focus=FOCUS, journal=journal, market=market,
                text="Same question after a published observation changes",
                cap={"main": 1, "adaptive": 0, "preview": 0},
            )), encoding="utf-8")
            grown = run_cli(
                "discovery-execute", "--store", str(grown_root), "--spec", str(spec_path),
                "--candidate-scope", str(scope_path), "--journal-scope", journal,
                "--operation", str(grown_op), "--format", "json", data_root=grown_root,
            )
            self.assertNotEqual(grown.returncode, 0)
            grown_body = json.loads(grown.stdout)
            self.assertEqual(grown_body["reason_code"], "LIVE_CORPUS_LOGICAL_CONTENT_NOT_RECONSTRUCTIBLE")
            self.assertNotEqual(grown_body.get("scientific_look_delta", {}).get("main"), 1)
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

    def test_threshold_change_is_adaptation_not_a_second_main(self) -> None:
        from solana_alpha_lab.factory.hfic_grounded_discovery import run_recorded_discovery_query
        from solana_alpha_lab.factory.hfic_ordinary_operation import record_operation
        from solana_alpha_lab.factory.hfic_research_universe_policy import ensure_profile
        from solana_alpha_lab.factory.research_store import ResearchStore
        from tests.test_hfic_temporal_discovery_v1 import GIT_SHA, _binding, _census, _obs, _path, _scope, _spec

        spec = _spec(search_tier="SIMPLE_SCREEN", query_id="universe-adaptation")
        rows = _path("a", [1.0, 1.5, 2.0, 1.6], (10000.0, 9000.0), 1.92) + [
            _obs("a", "Y3600", "FIELD-HOLDER-COUNT-001", 50)
        ]
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            ensure_profile(store, repo_root=ROOT, min_holders=0, min_liquidity_usd=0)
            operation = record_operation(store, {
                "owner_request_text": "synthetic policy adaptation",
                "owner_focus": "UNIVERSE_ADAPTATION",
                "journal_scope": "ab" * 32,
                "market_evidence_epoch_sha256": "cd" * 32,
                "spec": spec,
                "owner_cap": {"main": 1, "adaptive": None, "preview": None},
                "requested_completion": "LIMITED_RESULT",
            })
            first = run_recorded_discovery_query(
                store, census=[_census("a")], observations=rows, spec=spec, binding=_binding(),
                journal_scope="ab" * 32, candidate_scope=_scope(spec), git_sha=GIT_SHA,
                operation_sha256=operation["operation_sha256"], verified_market="cd" * 32,
            )
            self.assertEqual(first["queries"][0]["look_class"], "MAIN")
            from solana_alpha_lab.factory.hfic_ordinary_operation import note_look_landed

            self.assertEqual(note_look_landed(store, operation["operation_sha256"])["status"], "PAUSED_CAP")
            ensure_profile(store, repo_root=ROOT, min_holders=50, min_liquidity_usd=20000)
            follow = record_operation(store, {
                "owner_request_text": "synthetic policy adaptation follow-up",
                "owner_focus": "UNIVERSE_ADAPTATION_FOLLOW",
                "journal_scope": "ab" * 32,
                "market_evidence_epoch_sha256": "cd" * 32,
                "spec": spec,
                "owner_cap": {"main": 0, "adaptive": 1, "preview": 0},
                "requested_completion": "LIMITED_RESULT",
            })
            second = run_recorded_discovery_query(
                store, census=[_census("a")], observations=rows, spec=spec, binding=_binding(),
                journal_scope="ab" * 32, candidate_scope=_scope(spec), git_sha=GIT_SHA,
                operation_sha256=follow["operation_sha256"], verified_market="cd" * 32,
            )
            self.assertTrue(second["queries"][0]["new_look"])
            self.assertEqual(second["queries"][0]["look_class"], "ADAPTIVE")
            self.assertEqual(second["budget"]["main_count"], first["budget"]["main_count"])
            grown = [dict(item) for item in rows]
            grown[0] = dict(grown[0])
            grown[0]["typed_value"] = "9"
            fresh = record_operation(store, {
                "owner_request_text": "synthetic observation change after the threshold move",
                "owner_focus": "UNIVERSE_ADAPTATION_GROWN",
                "journal_scope": "ab" * 32,
                "market_evidence_epoch_sha256": "cd" * 32,
                "spec": spec,
                "owner_cap": {"main": 1, "adaptive": 0, "preview": 0},
                "requested_completion": "LIMITED_RESULT",
            })
            third = run_recorded_discovery_query(
                store, census=[_census("a")], observations=grown, spec=spec, binding=_binding(),
                journal_scope="ab" * 32, candidate_scope=_scope(spec), git_sha=GIT_SHA,
                operation_sha256=fresh["operation_sha256"], verified_market="cd" * 32,
            )
            self.assertEqual(third["queries"][0]["look_class"], "MAIN")
            self.assertEqual(third["budget"]["main_count"], first["budget"]["main_count"] + 1)

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
