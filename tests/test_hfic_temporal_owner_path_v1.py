"""Vertical owner path for temporal discovery. Published binding, no hand-written holdout."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_temporal_discovery import (  # noqa: E402
    run_registered_fixed_time_proxy,
    temporal_target_label,
)
from tests.test_hfic_cli import bind_draft, populate_real_c1_c2, run_cli  # noqa: E402
from tests.test_hfic_temporal_discovery_v1 import (  # noqa: E402
    _binding,
    _census,
    _explicit_cost,
    _path,
    _spec,
)

ROOT = Path(__file__).resolve().parents[1]
PRICE = "FIELD-USD-PRICE-001"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_partition(directory: Path) -> tuple[Path, Path, list[dict]]:
    census = [_census("cost-mint")]
    observations = _path("cost-mint", [1.0, 1.5, 2.0, 1.6], (10000.0, 9000.0), 1.92)
    census_path = directory / "census.parquet"
    observations_path = directory / "observations.parquet"
    pq.write_table(pa.Table.from_pylist(census), census_path)
    pq.write_table(pa.Table.from_pylist(observations), observations_path)
    return census_path, observations_path, _binding()


def _operation(directory: Path, spec: dict, journal: str, market: str, name: str) -> Path:
    path = directory / f"{name}.operation.json"
    path.write_text(
        json.dumps(
            {
                "owner_request_text": f"protocol owner path {name}",
                "owner_focus": "ORDINARY-TEMPORAL-SYNTH",
                "journal_scope": journal,
                "market_evidence_epoch_sha256": market,
                "spec": spec,
                "question_text": name,
                "owner_cap": {"main": None, "adaptive": None, "preview": None},
                "requested_completion": "LIMITED_RESULT",
            }
        ),
        encoding="utf-8",
    )
    return path


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-B",
            str(ROOT / "scripts" / "hypothesis_forge.py"),
            "--root",
            str(ROOT),
            *args,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


class TemporalOwnerPathTests(unittest.TestCase):
    def test_published_binding_reaches_freeze_and_fixed_time_consumer(self) -> None:
        spec = _spec(cost_profile=None)
        preview = {
            "decision": {"point_id": "Y3600"},
            "schedule": {
                "lateness_seconds": 300,
                "points": ["X300", "Y900", "Y1800", "Y3600"],
            },
            "seed": "owner-path-seed",
        }
        scope = {
            "population": "BASE_X",
            "decision_timestamp": "Y3600",
            "target": temporal_target_label(spec),
            "estimand": "price_relative_proxy",
            "explanatory_condition": "compound",
            "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
            "representation_scope": "TEMPORAL_PRICE_LIQUIDITY",
        }
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = workspace / "rdp"
            populate_real_c1_c2(data_root, workspace)
            preflight = run_cli(
                "preflight",
                "--discovery-contract",
                "--owner-focus",
                "ORDINARY-TEMPORAL-SYNTH",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            receipt = json.loads(preflight.stdout)
            bound = run_cli("discovery-binding", "--format", "json", data_root=data_root)
            self.assertEqual(bound.returncode, 0, bound.stderr)
            published = json.loads(bound.stdout)
            self.assertFalse(published["values_loaded"])
            self.assertTrue(published["holdout_derived_from_discovery_contract"])
            spec_path = workspace / "spec.json"
            scope_path = workspace / "scope.json"
            preview_path = workspace / "preview.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            scope_path.write_text(json.dumps(scope), encoding="utf-8")
            preview_path.write_text(json.dumps(preview), encoding="utf-8")
            journal = str(receipt["search_key_sha256"])
            market = str(receipt["market_evidence_epoch_sha256"])
            published_op = _operation(workspace, spec, journal, market, "published")
            preview_run = run_cli(
                "discovery-preview",
                "--spec",
                str(preview_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertNotEqual(preview_run.returncode, 0)
            self.assertIn("SCHEDULE_CONTEXT_UNBOUND", preview_run.stderr)
            completed = run_cli(
                "discovery-execute",
                "--store",
                str(data_root),
                "--spec",
                str(spec_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--operation",
                str(published_op),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("SCHEDULE_CONTEXT_UNBOUND", completed.stderr)
            empty_root = workspace / "unlined"
            empty_root.mkdir()
            census_path, observations_path, binding = _write_partition(workspace)
            binding[0]["census_sha256"] = _sha256_file(census_path)
            binding[0]["observations_sha256"] = _sha256_file(observations_path)
            binding[0]["census_rel"] = census_path.name
            binding[0]["observations_rel"] = observations_path.name
            binding_path = workspace / "cost-binding.json"
            binding_path.write_text(json.dumps({"cohorts": binding}), encoding="utf-8")
            simple = _spec(
                search_tier="SIMPLE_SCREEN",
                query_id="simple-mark",
                features=[{"name": "mark", "op": "point_value", "field_id": PRICE, "point": "Y3600"}],
                all=[{"feature": "mark", "op": "gte", "value": 0.0}],
                cost_profile=_explicit_cost(),
            )
            compound = _spec(query_id="compound-mark", cost_profile=_explicit_cost())
            simple_path = workspace / "simple.json"
            compound_path = workspace / "compound.json"
            simple_path.write_text(json.dumps(simple), encoding="utf-8")
            compound_path.write_text(json.dumps(compound), encoding="utf-8")
            simple_scope = dict(scope)
            simple_scope["decision_timestamp"] = "Y3600"
            simple_scope["target"] = temporal_target_label(simple)
            compound_scope = dict(scope)
            compound_scope["target"] = temporal_target_label(compound)
            simple_scope_path = workspace / "simple-scope.json"
            compound_scope_path = workspace / "compound-scope.json"
            simple_scope_path.write_text(json.dumps(simple_scope), encoding="utf-8")
            compound_scope_path.write_text(json.dumps(compound_scope), encoding="utf-8")
            simple_run = _cli(
                "--data-root",
                str(empty_root),
                "discovery-execute",
                "--store",
                str(data_root),
                "--binding",
                str(binding_path),
                "--cohort-partition",
                binding[0]["cohort_id"],
                str(census_path),
                str(observations_path),
                "--spec",
                str(simple_path),
                "--candidate-scope",
                str(simple_scope_path),
                "--journal-scope",
                journal,
                "--operation",
                str(_operation(workspace, simple, journal, market, "simple")),
                "--format",
                "json",
            )
            self.assertEqual(simple_run.returncode, 0, simple_run.stderr)
            simple_evidence = json.loads(simple_run.stdout)
            self.assertEqual(simple_evidence["queries"][0]["search_tier"], "SIMPLE_SCREEN")
            compound_run = _cli(
                "--data-root",
                str(empty_root),
                "discovery-execute",
                "--store",
                str(data_root),
                "--binding",
                str(binding_path),
                "--cohort-partition",
                binding[0]["cohort_id"],
                str(census_path),
                str(observations_path),
                "--spec",
                str(compound_path),
                "--candidate-scope",
                str(compound_scope_path),
                "--journal-scope",
                journal,
                "--operation",
                str(_operation(workspace, compound, journal, market, "compound")),
                "--format",
                "json",
            )
            self.assertEqual(compound_run.returncode, 0, compound_run.stderr)
            evidence = json.loads(compound_run.stdout)
            self.assertEqual(evidence["queries"][0]["search_tier"], "COMPOUND_SCREEN")
            self.assertGreaterEqual(evidence["budget"]["simple_main_count"], 1)
            self.assertGreaterEqual(evidence["budget"]["compound_main_count"], 1)
            self.assertTrue(evidence["tier_progress"]["compound_executed"])
            self.assertTrue(evidence["tier_progress"]["simple_executed"])
            self.assertEqual(evidence["result"]["cost"]["status"], "EVALUATED")
            self.assertEqual(
                evidence["result"]["cost"]["scenarios"]["BASE"]["label"],
                "ESTIMATED_NET_PROXY",
            )
            self.assertFalse(evidence["result"]["labeled_net_return"])
            scope = compound_scope
            preflight_after = run_cli(
                "preflight",
                "--discovery-contract",
                "--owner-focus",
                "ORDINARY-TEMPORAL-SYNTH",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight_after.returncode, 0, preflight_after.stderr)
            source_receipt = json.loads(preflight_after.stdout)
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
            draft = bind_draft({**source, "candidates": [card]}, source_receipt)
            draft.pop("runner_up_candidate_ref", None)
            draft.pop("strongest_rejected_alternative", None)
            draft["selected_candidate_ref"] = card["label"]
            draft["grounded_evidence"] = evidence
            draft_path = workspace / "draft.json"
            receipt_path = workspace / "preflight.json"
            draft_path.write_text(json.dumps(draft), encoding="utf-8")
            receipt_path.write_text(json.dumps(source_receipt), encoding="utf-8")
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
                "ORDINARY-TEMPORAL-SYNTH",
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
            packet = frozen["critic_input_packet"]
            handed = packet["grounded_evidence"]
            self.assertEqual(handed["result"]["target_kind"], "PRICE_RELATIVE_PROXY")
            self.assertEqual(handed["result"]["cost"]["scenarios"]["BASE"]["label"], "ESTIMATED_NET_PROXY")
            self.assertEqual(handed["result_refs"], evidence["result_refs"])
            self.assertIn("experiment_recipe", handed["result"])
            critic = {
                "schema": "smial.hypothesis-critic-result",
                "schema_version": "1.1",
                "session_id": frozen["session_id"],
                "critic_input_packet_sha256": frozen["critic_input_packet_sha256"],
                "selected_candidate_id": frozen["selected_candidate_id"],
                "selected_definition_sha256": frozen["selected_definition_sha256"],
                "critic_prompt_version": "HFIC-V1.1",
                "isolated_context_attestation": "NEW_CONTEXT_REQUIRED",
                "critic_terminal": "KILL_PREPARATORY_LOOP",
                "next": "STOP",
                "authority": {
                    "git_mutation": 0,
                    "experiment_execution": 0,
                    "provider_api_rpc_wss_calls": 0,
                },
                "non_claims": ["NO_ALPHA", "FIXTURE_CRITIC"],
            }
            critic_path = workspace / "critic.json"
            critic_path.write_text(json.dumps(critic), encoding="utf-8")
            missing_critic = run_cli(
                "finalize",
                "--session-id",
                str(frozen["session_id"]),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertNotEqual(missing_critic.returncode, 0)
            finalized = run_cli(
                "finalize",
                "--session-id",
                str(frozen["session_id"]),
                "--critic-result",
                str(critic_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(finalized.returncode, 0, finalized.stderr)
            consumed = run_registered_fixed_time_proxy(
                root=ROOT,
                registry_path=ROOT / "configs/experiment_capability_registry_v2.yaml",
                recipe=evidence["result"]["experiment_recipe"],
                data_root=workspace,
            )
            self.assertEqual(consumed["capability_id"], "CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001")
            self.assertEqual(consumed["summary"]["spec_sha256"], evidence["result"]["spec_sha256"])
            self.assertEqual(consumed["summary"]["mean_target"], evidence["result"]["mean_target"])
            self.assertFalse(consumed["labeled_net_return"])
            self.assertEqual(consumed["summary"]["cost"]["scenarios"]["BASE"]["label"], "ESTIMATED_NET_PROXY")
            self.assertNotEqual(consumed["summary"]["target_kind"], "NetReturn")
            cohort = published["cohorts"][0]
            census_path = data_root / cohort["census_rel"]
            original = census_path.read_bytes()
            census_path.write_bytes(original + b"\x00")
            tampered = run_cli(
                "discovery-execute",
                "--store",
                str(data_root),
                "--spec",
                str(spec_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--operation",
                str(published_op),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertNotEqual(tampered.returncode, 0)
            self.assertIn("BINDING_HASH_MISMATCH", tampered.stderr)
            census_path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
