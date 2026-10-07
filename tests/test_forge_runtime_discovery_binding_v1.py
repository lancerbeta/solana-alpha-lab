"""Published discovery corpus resolves an admission binding without a hand-written holdout."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MEASURED_TARGET = "Y1800:FIELD-USD-PRICE-001"
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_control_integrity import (  # noqa: E402
    CURRENT_REPRESENTATION_CONTROL_V1,
)
from solana_alpha_lab.factory.hfic_grounded_discovery import (  # noqa: E402
    ORDINARY_GROUNDED_DISCOVERY_V1,
    GroundedDiscoveryError,
    bind_prior_scope_evidence,
    collapse_exact_partition_duplicates,
    live_state_only_coverage,
    load_admitted_partition_rows,
    prior_scope_relation,
    resolve_published_discovery_binding,
)
from solana_alpha_lab.factory.hfic_prior_memory import (  # noqa: E402
    build_prior_memory_snapshot,
    compact_forge_prior_entry,
)
from solana_alpha_lab.factory.live_cohort_discovery_release import (  # noqa: E402
    classify_cohort_readiness,
    cohort_id_for_admission,
    import_live_cohort,
    load_observation_rdp_source,
    seal_live_cohort,
    verify_live_cohort,
    write_observation_rdp_source,
)
from solana_alpha_lab.factory.research_store import (  # noqa: E402
    RecordKind,
    ResearchEvent,
    ResearchStore,
)
from tests.test_live_cohort_discovery_release_series import (  # noqa: E402
    CAMPAIGN_STARTS,
    CAMPAIGN_STOPS,
    _snapshot_for_week,
)


def _publish_week(root: Path, week: int, data_root: Path) -> None:
    obs = root / f"obs-{week}"
    release = root / f"rel-{week}"
    obs.mkdir()
    release.mkdir()
    snap = _snapshot_for_week(week)
    write_observation_rdp_source(obs, snap)
    admission = CAMPAIGN_STARTS + timedelta(days=7 * week)
    cohort = cohort_id_for_admission(
        admission,
        starts_at=CAMPAIGN_STARTS,
        stops_admitting_at=CAMPAIGN_STOPS,
    )
    as_of = admission + timedelta(days=15)
    ready = classify_cohort_readiness(
        load_observation_rdp_source(obs),
        cohort_id=cohort,
        as_of=as_of,
    )
    if ready["state"] not in {"READY_VALID", "READY_VALID_WITH_COVERAGE_LIMITATION"}:
        raise AssertionError(ready["state"])
    seal_live_cohort(
        observation_rdp_root=obs,
        cohort_id=cohort,
        release_root=release,
        sealed_at=as_of,
        as_of=as_of,
    )
    verify_live_cohort(release)
    import_live_cohort(
        release_root=release,
        data_root=data_root,
        import_time=as_of + timedelta(hours=1),
    )


def _event(kind: RecordKind, record_id: str, payload: dict, *, hyp: str | None = None) -> ResearchEvent:
    import hashlib

    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    now = datetime(2026, 9, 1, tzinfo=UTC)
    return ResearchEvent(
        record_id=record_id,
        record_kind=kind,
        entity_id=hyp or record_id,
        hypothesis_version_id=hyp,
        run_id=None,
        transaction_id="RESEARCH-TXN-BINDING-001",
        effective_at=now,
        first_reliable_available_at=now,
        supersedes_record_id=None,
        payload_json=body,
        payload_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        producer_git_sha="0" * 40,
        created_at=now,
    )


class PublishedDiscoveryBindingTests(unittest.TestCase):
    def test_producer_publication_resolves_without_manual_holdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            _publish_week(root, 0, data)
            _publish_week(root, 1, data)
            binding = resolve_published_discovery_binding(data)
            self.assertEqual(binding["authority_source"], "PUBLISHED_DISCOVERY_LABELS_V1")
            self.assertTrue(binding["holdout_derived_from_discovery_contract"])
            self.assertFalse(binding["protected_holdout_assignment"])
            self.assertGreaterEqual(len(binding["cohorts"]), 2)
            hashes = {
                (item["census_sha256"], item["observations_sha256"])
                for item in binding["cohorts"]
            }
            self.assertEqual(len(hashes), len(binding["cohorts"]))
            loaded = load_admitted_partition_rows(
                data_root=data,
                binding_doc=None,
                partitions=None,
                census_path=None,
                observations_path=None,
            )
            self.assertTrue(loaded["values_loaded"])
            self.assertGreater(len(loaded["census"]), 0)
            from tests.test_hfic_forge_context_and_no_worthy import run_cli

            spec = {
                "query_id": "PUBLISHED_BINDING_Q1",
                "population": "BASE_X",
                "decision_points": ["X300"],
                "decision_fields": ["FIELD-USD-PRICE-001", "FIELD-LIQUIDITY-USD-001"],
                "target_point": "Y1800",
                "target_field": "FIELD-USD-PRICE-001",
                "explanatory": [],
            }
            scope = {
                "question_id": "PUBLISHED_BINDING_Q1",
                "population": "BASE_X",
                "decision_timestamp": "X300",
                "target": "Y1800:FIELD-USD-PRICE-001",
                "estimand": "price_liquidity_prefix",
                "explanatory_condition": "NONE",
                "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
                "representation_scope": "PRICE_LIQUIDITY_PREFIX_THROUGH_Y1800",
            }
            spec_path = root / "spec.json"
            scope_path = root / "scope.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            scope_path.write_text(json.dumps(scope), encoding="utf-8")
            journal = "published-binding-journal"
            from solana_alpha_lab.factory.hfic_research_universe_policy import ensure_profile

            ensure_profile(ResearchStore(data), repo_root=ROOT, min_holders=0, min_liquidity_usd=0)
            first = run_cli(
                "discovery-execute",
                "--store",
                str(data),
                "--spec",
                str(spec_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--format",
                "json",
                data_root=data,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            evidence = json.loads(first.stdout)
            self.assertTrue(evidence["result_refs"])
            self.assertTrue(evidence["queries"][0]["new_look"])
            second = run_cli(
                "discovery-execute",
                "--store",
                str(data),
                "--spec",
                str(spec_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--format",
                "json",
                data_root=data,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            replay = json.loads(second.stdout)
            self.assertFalse(replay["queries"][0]["new_look"])
            self.assertEqual(replay["result_refs"], evidence["result_refs"])

    def test_protected_unknown_and_hash_stop_before_the_loader(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            _publish_week(root, 0, data)
            _publish_week(root, 1, data)
            binding = resolve_published_discovery_binding(data)
            labels_path = (
                data
                / "datasets"
                / "manifests"
                / f"{binding['dataset_manifest_id']}.labels.json"
            )
            labels = json.loads(labels_path.read_text(encoding="utf-8"))

            def _refuse_load(*_args, **_kwargs):
                raise AssertionError("value loader called")

            protected = dict(labels)
            protected["holdout"] = True
            labels_path.write_text(json.dumps(protected), encoding="utf-8")
            with patch(
                "solana_alpha_lab.factory.hfic_grounded_discovery.load_parquet_rows",
                side_effect=_refuse_load,
            ):
                with self.assertRaises(GroundedDiscoveryError) as holdout:
                    load_admitted_partition_rows(
                        data_root=data,
                        binding_doc=None,
                        partitions=None,
                        census_path=None,
                        observations_path=None,
                    )
            self.assertEqual(holdout.exception.code, "HOLDOUT_PROTECTED")

            unknown = dict(labels)
            unknown.pop("evidence_role", None)
            labels_path.write_text(json.dumps(unknown), encoding="utf-8")
            with patch(
                "solana_alpha_lab.factory.hfic_grounded_discovery.load_parquet_rows",
                side_effect=_refuse_load,
            ):
                with self.assertRaises(GroundedDiscoveryError) as role:
                    resolve_published_discovery_binding(data)
            self.assertEqual(role.exception.code, "DISCOVERY_ROLE_UNKNOWN")

            forbidden = dict(labels)
            forbidden["evidence_role"] = "PROSPECTIVE_OOS"
            labels_path.write_text(json.dumps(forbidden), encoding="utf-8")
            with self.assertRaises(GroundedDiscoveryError) as blocked:
                resolve_published_discovery_binding(data)
            self.assertEqual(blocked.exception.code, "DISCOVERY_ROLE_FORBIDDEN")

            labels_path.write_text(json.dumps(labels), encoding="utf-8")
            swapped = json.loads(json.dumps(binding))
            left, right = swapped["cohorts"][0], swapped["cohorts"][-1]
            if left["cohort_id"] != right["cohort_id"]:
                partitions = [
                    (
                        left["cohort_id"],
                        data / right["census_rel"],
                        data / right["observations_rel"],
                    )
                ]
                with patch(
                    "solana_alpha_lab.factory.hfic_grounded_discovery.load_parquet_rows",
                    side_effect=_refuse_load,
                ):
                    with self.assertRaises(GroundedDiscoveryError) as mismatch:
                        load_admitted_partition_rows(
                            data_root=data,
                            binding_doc=swapped,
                            partitions=partitions,
                            census_path=None,
                            observations_path=None,
                        )
                self.assertEqual(mismatch.exception.code, "BINDING_HASH_MISMATCH")

    def test_exact_partition_repeat_does_not_double_and_overlap_stays_visible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            _publish_week(root, 0, data)
            binding = resolve_published_discovery_binding(data)
            cohort = binding["cohorts"][0]
            census = data / cohort["census_rel"]
            obs = data / cohort["observations_rel"]
            once = load_admitted_partition_rows(
                data_root=data,
                binding_doc=binding,
                partitions=[(cohort["cohort_id"], census, obs)],
                census_path=None,
                observations_path=None,
            )
            twice = load_admitted_partition_rows(
                data_root=data,
                binding_doc=binding,
                partitions=[
                    (cohort["cohort_id"], census, obs),
                    (cohort["cohort_id"], census, obs),
                ],
                census_path=None,
                observations_path=None,
            )
            self.assertEqual(twice["duplicate_partitions_eliminated"], 1)
            self.assertEqual(len(twice["census"]), len(once["census"]))
            with self.assertRaises(GroundedDiscoveryError) as conflict:
                collapse_exact_partition_duplicates(
                    [
                        (cohort["cohort_id"], census, obs),
                        (cohort["cohort_id"], census, Path("other.parquet")),
                    ]
                )
            self.assertEqual(conflict.exception.code, "DUPLICATE_COHORT_PARTITION")
            coverage = live_state_only_coverage(data)
            self.assertFalse(coverage["typed_value_selected"])
            self.assertEqual(
                coverage["binding"]["authority_source"],
                "PUBLISHED_DISCOVERY_LABELS_V1",
            )


class PriorScopeTransportTests(unittest.TestCase):
    def _control_prior(self) -> dict:
        return {
            "hypothesis_version_id": "HFIC-CAND-CONTROL-SCOPE",
            "question_id": "HFIC-CAND-CONTROL-SCOPE",
            "population": "BASE_X",
            "decision_timestamp": "X300",
            "target": "Y1800_REPORTED_PRICE_PATH",
            "estimand": "ticket_asymmetry",
            "explanatory_condition": "PRICE_GE_2",
            "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
            "representation_scope": CURRENT_REPRESENTATION_CONTROL_V1,
            "memory_status": "HARD_CLOSE",
            "reason_code": "KILL_PREPARATORY_LOOP",
            "session_id": "HFIC-SESS-CONTROL",
        }

    def test_canonical_memory_survives_empty_caller_list(self) -> None:
        prior = self._control_prior()
        richer = {
            **prior,
            "question_id": "RENAMED_ONLY",
            "evidence_surface_mode": ORDINARY_GROUNDED_DISCOVERY_V1,
            "representation_scope": "PRICE_LIQUIDITY_PREFIX_THROUGH_Y1800",
        }
        bound = bind_prior_scope_evidence(
            {"candidate_scope": richer, "priors": []},
            canonical_priors=[prior],
        )
        self.assertEqual(
            bound["prior_scope_relations"][0]["relation"],
            "SCOPED_CONTROL_DOES_NOT_BLOCK",
        )
        same = {**prior, "question_id": "RENAMED_ONLY"}
        self.assertEqual(prior_scope_relation(same, prior), "EXACT_VALID_CLOSE")
        with self.assertRaises(GroundedDiscoveryError) as exact:
            bind_prior_scope_evidence(
                {"candidate_scope": same, "priors": []},
                canonical_priors=[prior],
            )
        self.assertEqual(exact.exception.code, "EXACT_PRIOR_SCOPE_MATCH")
        missing_surface = {key: value for key, value in prior.items() if key != "evidence_surface_mode"}
        with self.assertRaises(GroundedDiscoveryError) as unresolved_surface:
            bind_prior_scope_evidence(
                {"candidate_scope": same, "priors": []},
                canonical_priors=[missing_surface],
            )
        self.assertEqual(unresolved_surface.exception.code, "UNKNOWN_PRIOR_SCOPE")
        parked = {**prior, "memory_status": "PARK", "reason_code": "OWNER_PRIORITY_PARK"}
        parked_bound = bind_prior_scope_evidence(
            {"candidate_scope": same, "priors": []},
            canonical_priors=[parked],
        )
        self.assertEqual(
            parked_bound["prior_scope_relations"][0]["relation"],
            "NON_BLOCKING_PRIOR",
        )
        incomplete = {
            "hypothesis_version_id": "HFIC-CAND-UNRELATED",
            "memory_status": "HARD_CLOSE",
            "reason_code": "KILL_MECHANISM",
            "population": "BASE_X",
        }
        unresolved = bind_prior_scope_evidence(
            {"candidate_scope": richer, "priors": []},
            canonical_priors=[incomplete],
        )
        self.assertEqual(
            unresolved["prior_scope_relations"][0]["relation"],
            "UNKNOWN_SCOPE_NEEDS_RESOLUTION",
        )

    def test_snapshot_and_forge_projection_keep_recovered_scope(self) -> None:
        prior = self._control_prior()
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            store.append(
                [
                    _event(
                        RecordKind.HYPOTHESIS_VERSION,
                        "HFIC-HYP-CONTROL",
                        prior,
                        hyp=prior["hypothesis_version_id"],
                    ),
                    _event(
                        RecordKind.RESEARCH_CYCLE,
                        "HFIC-CYCLE-CONTROL",
                        {
                            "session_id": prior["session_id"],
                            "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
                            "discovery_candidate_scope": {
                                "population": prior["population"],
                                "decision_timestamp": prior["decision_timestamp"],
                                "target": prior["target"],
                                "estimand": prior["estimand"],
                                "explanatory_condition": prior["explanatory_condition"],
                                "representation_scope": prior["representation_scope"],
                            },
                        },
                    ),
                    _event(
                        RecordKind.DECISION_EVENT,
                        "HFIC-DEC-CONTROL",
                        {
                            "hypothesis_version_id": prior["hypothesis_version_id"],
                            "decision_kind": "REJECT",
                            "reason_code": "KILL_PREPARATORY_LOOP",
                        },
                        hyp=prior["hypothesis_version_id"],
                    ),
                ],
                transaction_id="RESEARCH-TXN-BINDING-001",
            )
            snapshot = build_prior_memory_snapshot(
                store,
                store_inventory_digest="cd" * 32,
            )
            capsule = snapshot["capsules"][0]
            self.assertEqual(capsule["evidence_surface_mode"], CURRENT_REPRESENTATION_CONTROL_V1)
            self.assertEqual(capsule["estimand"], "ticket_asymmetry")
            self.assertEqual(capsule["reason_code"], "KILL_PREPARATORY_LOOP")
            self.assertEqual(capsule["memory_status"], "HARD_CLOSE")
            forge = compact_forge_prior_entry(
                prior["hypothesis_version_id"],
                prior,
                {"decision_kind": "REJECT", "reason_code": "KILL_PREPARATORY_LOOP"},
            )
            self.assertEqual(forge["target"], prior["target"])
            self.assertEqual(
                forge["evidence_surface_mode"],
                CURRENT_REPRESENTATION_CONTROL_V1,
            )
            richer = {
                **prior,
                "evidence_surface_mode": ORDINARY_GROUNDED_DISCOVERY_V1,
                "representation_scope": "PRICE_LIQUIDITY_PREFIX_THROUGH_Y1800",
            }
            bound = bind_prior_scope_evidence(
                {"candidate_scope": richer, "priors": []},
                canonical_priors=snapshot["capsules"],
            )
            self.assertEqual(
                bound["prior_scope_relations"][0]["relation"],
                "SCOPED_CONTROL_DOES_NOT_BLOCK",
            )


class LegacyRankedPriorRecoveryTests(unittest.TestCase):
    def test_preflight_ranked_entry_matches_critic_capsule_without_prefilled_scope(self) -> None:
        from solana_alpha_lab.factory.hfic_grounded_discovery import prior_scope_relation
        from solana_alpha_lab.factory.hfic_reopened_prior_routing import (
            ranked_prior_entries_for_ids,
        )
        from tests.test_hfic_cli import seed_minimal_market_basis
        from tests.test_hfic_forge_context_and_no_worthy import run_cli

        legacy_id = "HFIC-CAND-LEGACY-SCOPE-RECOVERY"
        sibling_id = "HFIC-CAND-LEGACY-SCOPE-SIBLING"
        session_id = "HFIC-SESS-LEGACY-SCOPE"
        focus = "LEGACY_SCOPE_RECOVERY_TOKEN"
        legacy_body = {
            "hypothesis_version_id": legacy_id,
            "session_id": session_id,
            "claim": f"{focus} ticket asymmetry",
            "statement": f"{focus} ticket asymmetry",
            "mechanism": "preparatory loop",
            "actor_counterparty": "crowd",
            "population": "BASE_X",
            "decision_timestamp": "X300",
            "primary_x_family": "ACTIVITY_VOLUME",
            "primary_y": "path",
            "horizon_notional": "Y1800",
            "negative_control": "shuffled",
            "cheapest_falsifier": "kill the loop",
        }
        sibling_body = {
            **legacy_body,
            "hypothesis_version_id": sibling_id,
            "claim": f"{focus} sibling without card",
            "statement": f"{focus} sibling without card",
        }
        self.assertNotIn("target", legacy_body)
        self.assertNotIn("estimand", legacy_body)
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "rdp"
            seed_minimal_market_basis(data)
            store = ResearchStore(data)
            store.append(
                [
                    _event(RecordKind.HYPOTHESIS_VERSION, "HFIC-HYP-LEGACY", legacy_body, hyp=legacy_id),
                    _event(RecordKind.HYPOTHESIS_VERSION, "HFIC-HYP-SIBLING", sibling_body, hyp=sibling_id),
                    _event(
                        RecordKind.RESEARCH_CYCLE,
                        "HFIC-CYCLE-LEGACY",
                        {
                            "session_id": session_id,
                            "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
                            "discovery_candidate_scope": {
                                "target": "POISON_SHARED_TARGET",
                                "estimand": "POISON_SHARED_ESTIMAND",
                            },
                            "grounded_candidates": [
                                {
                                    "candidate_id": legacy_id,
                                    "estimand": "ticket_asymmetry",
                                    "target": "Y1800_REPORTED_PRICE_PATH",
                                    "explanatory_condition": "PRICE_GE_2",
                                    "representation_scope": CURRENT_REPRESENTATION_CONTROL_V1,
                                }
                            ],
                        },
                    ),
                    _event(
                        RecordKind.DECISION_EVENT,
                        "HFIC-DEC-LEGACY",
                        {
                            "hypothesis_version_id": legacy_id,
                            "decision_kind": "REJECT",
                            "reason_code": "KILL_PREPARATORY_LOOP",
                        },
                        hyp=legacy_id,
                    ),
                    _event(
                        RecordKind.DECISION_EVENT,
                        "HFIC-DEC-SIBLING",
                        {
                            "hypothesis_version_id": sibling_id,
                            "decision_kind": "REJECT",
                            "reason_code": "KILL_MECHANISM",
                        },
                        hyp=sibling_id,
                    ),
                ],
                transaction_id="RESEARCH-TXN-BINDING-001",
            )
            preflight = run_cli(
                "preflight",
                "--owner-focus",
                focus,
                "--format",
                "json",
                data_root=data,
            )
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            packet = json.loads(preflight.stdout)["forge_context_packet"]
            ranked = {
                item["hypothesis_version_id"]: item
                for item in packet["ranked_prior_entries"]
            }
            self.assertIn(legacy_id, ranked)
            self.assertIn(sibling_id, ranked)
            prompt_a = ranked[legacy_id]
            self.assertEqual(prompt_a["target"], "Y1800_REPORTED_PRICE_PATH")
            self.assertEqual(prompt_a["estimand"], "ticket_asymmetry")
            self.assertEqual(
                prompt_a["evidence_surface_mode"],
                CURRENT_REPRESENTATION_CONTROL_V1,
            )
            self.assertNotEqual(prompt_a.get("target"), "POISON_SHARED_TARGET")
            sibling_entry = ranked[sibling_id]
            self.assertNotIn("target", sibling_entry)
            self.assertNotIn("estimand", sibling_entry)
            self.assertNotEqual(sibling_entry.get("target"), "Y1800_REPORTED_PRICE_PATH")
            snapshot = build_prior_memory_snapshot(
                ResearchStore(data),
                store_inventory_digest="cd" * 32,
            )
            capsules = {
                item["hypothesis_version_id"]: item for item in snapshot["capsules"]
            }
            for field in (
                "target",
                "estimand",
                "explanatory_condition",
                "representation_scope",
                "evidence_surface_mode",
            ):
                self.assertEqual(capsules[legacy_id].get(field), prompt_a.get(field))
                self.assertEqual(capsules[sibling_id].get(field), sibling_entry.get(field))
            direct = {
                item["hypothesis_version_id"]: item
                for item in ranked_prior_entries_for_ids(
                    [legacy_id, sibling_id],
                    [legacy_body, sibling_body],
                    store=ResearchStore(data),
                )
            }
            self.assertEqual(direct[legacy_id]["target"], prompt_a["target"])
            self.assertNotIn("target", direct[sibling_id])
            self.assertEqual(
                prior_scope_relation(
                    {
                        "population": "BASE_X",
                        "decision_timestamp": "X300",
                        "target": "Y1800_REPORTED_PRICE_PATH",
                        "estimand": "ticket_asymmetry",
                        "explanatory_condition": "PRICE_GE_2",
                        "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
                    },
                    capsules[sibling_id],
                ),
                "UNKNOWN_SCOPE_NEEDS_RESOLUTION",
            )


class PerCandidateScopePersistenceTests(unittest.TestCase):
    def test_runner_up_does_not_inherit_selected_scope(self) -> None:
        from tests.test_hfic_cli import bind_draft, populate_real_c1_c2, run_cli

        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            data_root = workspace / "rdp"
            populate_real_c1_c2(data_root, workspace)
            preflight = run_cli(
                "preflight",
                "--discovery-contract",
                "--owner-focus",
                "PER-CANDIDATE-SCOPE",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            receipt = json.loads(preflight.stdout)
            source = json.loads(
                (ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text(
                    encoding="utf-8"
                )
            )
            base = dict(source["candidates"][0])
            card_a = dict(base)
            card_b = dict(base)
            card_c = dict(base)
            card_a.update(
                {
                    "label": "HFIC-V12-A-SCOPE",
                    "display_ordinal": 1,
                    "population": "BASE_X",
                    "decision_timestamp": "X300",
                    "estimand": "estimand_A",
                    "target": MEASURED_TARGET,
                    "explanatory_condition": "cond_A",
                    "representation_scope": "rep_A",
                }
            )
            card_b.update(
                {
                    "label": "HFIC-V12-B-SCOPE",
                    "display_ordinal": 2,
                    "claim": base["claim"] + " runner B",
                    "population": "BASE_X",
                    "decision_timestamp": "X300",
                    "estimand": "estimand_B",
                    "target": "target_B",
                    "explanatory_condition": "cond_B",
                    "representation_scope": "rep_B",
                }
            )
            card_c.update(
                {
                    "label": "HFIC-V12-C-SCOPE",
                    "display_ordinal": 3,
                    "claim": base["claim"] + " rejected C",
                    "estimand": "estimand_C",
                }
            )
            for key in ("target", "explanatory_condition", "representation_scope"):
                card_c.pop(key, None)
            bound = run_cli(
                "discovery-binding",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(bound.returncode, 0, bound.stderr)
            spec_path = workspace / "spec.json"
            scope_path = workspace / "scope.json"
            spec_path.write_text(
                json.dumps(
                    {
                        "query_id": "PER_CANDIDATE_SCOPE",
                        "population": "BASE_X",
                        "decision_points": ["X300"],
                        "decision_fields": [
                            "FIELD-USD-PRICE-001",
                            "FIELD-LIQUIDITY-USD-001",
                        ],
                        "target_point": "Y1800",
                        "target_field": "FIELD-USD-PRICE-001",
                        "explanatory": [],
                    }
                ),
                encoding="utf-8",
            )
            scope_path.write_text(
                json.dumps(
                    {
                        "question_id": "PER_CANDIDATE_SCOPE",
                        "population": "BASE_X",
                        "decision_timestamp": "X300",
                        "target": "target_A",
                        "estimand": "estimand_A",
                        "explanatory_condition": "cond_A",
                        "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
                        "representation_scope": "rep_A",
                    }
                ),
                encoding="utf-8",
            )
            journal = str(receipt["search_key_sha256"])
            from solana_alpha_lab.factory.hfic_research_universe_policy import ensure_profile

            ensure_profile(ResearchStore(data_root), repo_root=ROOT, min_holders=0, min_liquidity_usd=0)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "scripts/hypothesis_forge.py",
                    "--root",
                    str(ROOT),
                    "--data-root",
                    str(data_root),
                    "discovery-execute",
                    "--store",
                    str(data_root),
                    "--spec",
                    str(spec_path),
                    "--candidate-scope",
                    str(scope_path),
                    "--journal-scope",
                    journal,
                    "--format",
                    "json",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            evidence = json.loads(completed.stdout)
            self.assertEqual(evidence["candidate_scope"]["target"], MEASURED_TARGET)
            preflight_after = run_cli(
                "preflight",
                "--discovery-contract",
                "--owner-focus",
                "PER-CANDIDATE-SCOPE",
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(preflight_after.returncode, 0, preflight_after.stderr)
            receipt = json.loads(preflight_after.stdout)
            self.assertEqual(receipt.get("search_key_sha256"), evidence["journal_scope"])
            draft = bind_draft(
                {**source, "candidates": [card_a, card_b, card_c]},
                receipt,
            )
            draft["selected_candidate_ref"] = card_a["label"]
            draft["runner_up_candidate_ref"] = card_b["label"]
            draft["strongest_rejected_alternative"] = card_c["label"]
            draft["grounded_evidence"] = evidence
            draft_path = workspace / "draft.json"
            receipt_path = workspace / "preflight.json"
            draft_path.write_text(json.dumps(draft), encoding="utf-8")
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            frozen_run = run_cli(
                "freeze",
                "--draft",
                str(draft_path),
                "--preflight-receipt",
                str(receipt_path),
                "--format",
                "json",
                data_root=data_root,
            )
            self.assertEqual(frozen_run.returncode, 0, frozen_run.stderr)
            frozen = json.loads(frozen_run.stdout)
            versions = {}
            for record in ResearchStore(data_root).iter_committed_records():
                kind = getattr(record.record_kind, "value", record.record_kind)
                if kind != "HYPOTHESIS_VERSION":
                    continue
                payload = json.loads(record.payload_json)
                if payload.get("session_id") != frozen["session_id"]:
                    continue
                versions[payload["hypothesis_version_id"]] = payload
            selected = versions[frozen["selected_candidate_id"]]
            runner = versions[frozen["runner_up_candidate_id"]]
            rejected_id = next(
                item
                for item in versions
                if item not in {frozen["selected_candidate_id"], frozen["runner_up_candidate_id"]}
            )
            rejected = versions[rejected_id]
            self.assertEqual(selected["target"], MEASURED_TARGET)
            self.assertEqual(selected["estimand"], "estimand_A")
            self.assertEqual(runner["target"], "target_B")
            self.assertEqual(runner["estimand"], "estimand_B")
            self.assertNotEqual(runner.get("target"), "target_A")
            self.assertEqual(rejected["estimand"], "estimand_C")
            self.assertNotIn("target", rejected)
            runner_packet = frozen["runner_up_critic_input_packet"]
            runner_evidence = runner_packet["grounded_evidence"]
            runner_scope = runner_evidence["candidate_scope"]
            self.assertEqual(runner_scope["target"], "target_B")
            self.assertEqual(runner_scope["estimand"], "estimand_B")
            self.assertNotEqual(runner_scope["target"], "target_A")
            primary_evidence = frozen["critic_input_packet"]["grounded_evidence"]
            self.assertEqual(primary_evidence["candidate_scope"]["target"], MEASURED_TARGET)
            self.assertIn("result", primary_evidence)
            self.assertNotIn("result", runner_evidence)
            self.assertNotIn("result_sha256", runner_evidence)
            self.assertNotIn("result_refs", runner_evidence)
            self.assertNotIn("queries", runner_evidence)
            self.assertNotIn("target_A", json.dumps(runner_evidence))
            self.assertIn("prior_scope_relations", runner_evidence)

    def test_same_scope_runner_up_keeps_its_own_computed_look(self) -> None:
        from solana_alpha_lab.factory.hfic_session import (
            _rebind_runner_up_grounded_evidence,
        )

        scope = {
            "population": "BASE_X",
            "decision_timestamp": "X300",
            "target": "target_same",
            "estimand": "estimand_same",
            "explanatory_condition": "cond_same",
            "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
            "representation_scope": "rep_same",
        }
        packet = {
            "grounded_evidence": {
                "candidate_scope": dict(scope),
                "result": {"pooled": {"mean_target": 1}},
                "result_sha256": "abc",
                "result_refs": ["HFIC-ART-1"],
                "queries": [{"query_id": "Q"}],
                "priors": [],
            },
            "prior_memory": {"capsules": []},
        }
        _rebind_runner_up_grounded_evidence(packet, dict(scope))
        evidence = packet["grounded_evidence"]
        self.assertEqual(evidence["candidate_scope"]["target"], "target_same")
        self.assertEqual(evidence["result_sha256"], "abc")
        self.assertIn("result", evidence)

    def test_sparse_executed_scope_does_not_keep_primary_result(self) -> None:
        from solana_alpha_lab.factory.hfic_session import (
            _rebind_runner_up_grounded_evidence,
        )

        packet = {
            "grounded_evidence": {
                "candidate_scope": {
                    "population": "BASE_X",
                    "decision_timestamp": "X300",
                    "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
                },
                "result": {"pooled": {"mean_target": 1}},
                "result_sha256": "abc",
                "result_refs": ["HFIC-ART-1"],
                "queries": [{"query_id": "Q"}],
                "priors": [],
            },
            "prior_memory": {"capsules": []},
        }
        _rebind_runner_up_grounded_evidence(
            packet,
            {
                "population": "BASE_X",
                "decision_timestamp": "X300",
                "target": "target_B",
                "estimand": "estimand_B",
                "explanatory_condition": "cond_B",
                "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
                "representation_scope": "rep_B",
            },
        )
        evidence = packet["grounded_evidence"]
        self.assertEqual(evidence["candidate_scope"]["target"], "target_B")
        self.assertEqual(evidence["candidate_scope"]["estimand"], "estimand_B")
        self.assertNotIn("result", evidence)
        self.assertNotIn("result_sha256", evidence)

    def test_runner_up_exact_close_still_blocks(self) -> None:
        from solana_alpha_lab.factory.hfic_session import (
            HficSessionError,
            _rebind_runner_up_grounded_evidence,
        )

        scope = {
            "population": "BASE_X",
            "decision_timestamp": "X300",
            "target": "target_same",
            "estimand": "estimand_same",
            "explanatory_condition": "cond_same",
            "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
            "representation_scope": "rep_same",
        }
        packet = {
            "grounded_evidence": {
                "candidate_scope": dict(scope),
                "result": {"pooled": {"mean_target": 1}},
                "result_sha256": "abc",
                "priors": [],
            },
            "prior_memory": {
                "capsules": [
                    {
                        **scope,
                        "memory_status": "HARD_CLOSE",
                        "reason_code": "KILL_TEST",
                        "question_id": "Q-CLOSE",
                        "hypothesis_version_id": "HV-CLOSE",
                    }
                ]
            },
        }
        with self.assertRaises(HficSessionError) as caught:
            _rebind_runner_up_grounded_evidence(packet, dict(scope))
        self.assertEqual(caught.exception.code, "EXACT_PRIOR_SCOPE_MATCH")

    def _freeze_scoped_runner(
        self,
        workspace: Path,
        *,
        runner_matches_look: bool,
        selected_target: str = MEASURED_TARGET,
        scope_target: str = "target_A",
        selected_estimand: str = "estimand_A",
        selected_population: str = "BASE_X",
        selected_decision: str = "X300",
        decision_points: list[str] | None = None,
        scope_estimand: str | None = "estimand_A",
        expect_freeze_error: str | None = None,
    ) -> dict:
        from tests.test_hfic_cli import bind_draft, populate_real_c1_c2, run_cli

        data_root = workspace / "rdp"
        populate_real_c1_c2(data_root, workspace)
        preflight = run_cli(
            "preflight",
            "--discovery-contract",
            "--owner-focus",
            "RUNNER-LOOK-GUARD",
            "--format",
            "json",
            data_root=data_root,
        )
        self.assertEqual(preflight.returncode, 0, preflight.stderr)
        receipt = json.loads(preflight.stdout)
        source = json.loads(
            (ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text(
                encoding="utf-8"
            )
        )
        base = dict(source["candidates"][0])
        card_a = dict(base)
        card_b = dict(base)
        card_c = dict(base)
        card_a.update(
            {
                "label": "HFIC-V12-A-LOOK",
                "display_ordinal": 1,
                "population": selected_population,
                "decision_timestamp": selected_decision,
                "estimand": selected_estimand,
                "target": selected_target,
                "explanatory_condition": "cond_A",
                "representation_scope": "rep_A",
            }
        )
        points = list(decision_points or ["X300"])
        point_offset = {"X300": 300, "Y900": 900, "Y1800": 1800, "Y3600": 3600}
        latest_decision = max(points, key=lambda item: point_offset[item])
        runner_scope = {
            "population": "BASE_X",
            "decision_timestamp": latest_decision,
            "estimand": "estimand_A",
            "target": MEASURED_TARGET,
            "explanatory_condition": "cond_A",
            "representation_scope": "rep_A",
            "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
        }
        card_b.update(
            {
                "label": "HFIC-V12-B-LOOK",
                "display_ordinal": 2,
                "claim": base["claim"] + " runner B",
                "estimand": "estimand_B",
                "target": "target_B",
                "explanatory_condition": "cond_B",
                "representation_scope": "rep_B",
            }
        )
        if runner_matches_look:
            card_b.update(runner_scope)
        card_c.update(
            {
                "label": "HFIC-V12-C-LOOK",
                "display_ordinal": 3,
                "claim": base["claim"] + " rejected C",
                "estimand": "estimand_C",
            }
        )
        for key in ("target", "explanatory_condition", "representation_scope"):
            card_c.pop(key, None)
        bound = run_cli("discovery-binding", "--format", "json", data_root=data_root)
        self.assertEqual(bound.returncode, 0, bound.stderr)
        spec_path = workspace / "spec.json"
        scope_path = workspace / "scope.json"
        spec_path.write_text(
            json.dumps(
                {
                    "query_id": "RUNNER_LOOK_GUARD",
                    "population": "BASE_X",
                    "decision_points": points,
                    "decision_fields": [
                        "FIELD-USD-PRICE-001",
                        "FIELD-LIQUIDITY-USD-001",
                    ],
                    "target_point": "Y1800",
                    "target_field": "FIELD-USD-PRICE-001",
                    "explanatory": [],
                }
            ),
            encoding="utf-8",
        )
        look_scope = {
            "question_id": "RUNNER_LOOK_GUARD",
            "population": "BASE_X",
            "decision_timestamp": latest_decision,
            "target": scope_target,
            "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
        }
        if scope_estimand is not None:
            look_scope["estimand"] = scope_estimand
            look_scope["explanatory_condition"] = "cond_A"
            look_scope["representation_scope"] = "rep_A"
        scope_path.write_text(json.dumps(look_scope), encoding="utf-8")
        journal = str(receipt["search_key_sha256"])
        from solana_alpha_lab.factory.hfic_research_universe_policy import ensure_profile

        ensure_profile(ResearchStore(data_root), repo_root=ROOT, min_holders=0, min_liquidity_usd=0)
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "scripts/hypothesis_forge.py",
                "--root",
                str(ROOT),
                "--data-root",
                str(data_root),
                "discovery-execute",
                "--store",
                str(data_root),
                "--spec",
                str(spec_path),
                "--candidate-scope",
                str(scope_path),
                "--journal-scope",
                journal,
                "--format",
                "json",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        evidence = json.loads(completed.stdout)
        preflight_after = run_cli(
            "preflight",
            "--discovery-contract",
            "--owner-focus",
            "RUNNER-LOOK-GUARD",
            "--format",
            "json",
            data_root=data_root,
        )
        self.assertEqual(preflight_after.returncode, 0, preflight_after.stderr)
        receipt = json.loads(preflight_after.stdout)
        draft = bind_draft(
            {**source, "candidates": [card_a, card_b, card_c]},
            receipt,
        )
        draft["selected_candidate_ref"] = card_a["label"]
        draft["runner_up_candidate_ref"] = card_b["label"]
        draft["strongest_rejected_alternative"] = card_c["label"]
        draft["grounded_evidence"] = evidence
        draft_path = workspace / "draft.json"
        receipt_path = workspace / "preflight.json"
        draft_path.write_text(json.dumps(draft), encoding="utf-8")
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        frozen_run = run_cli(
            "freeze",
            "--draft",
            str(draft_path),
            "--preflight-receipt",
            str(receipt_path),
            "--format",
            "json",
            data_root=data_root,
        )
        self.assertEqual(frozen_run.returncode, 0, frozen_run.stderr) if expect_freeze_error is None else self.assertNotEqual(frozen_run.returncode, 0)
        if expect_freeze_error is not None:
            self.assertIn(expect_freeze_error, frozen_run.stderr)
            return {"data_root": data_root, "frozen": None, "evidence": evidence}
        frozen = json.loads(frozen_run.stdout)
        return {"data_root": data_root, "frozen": frozen, "evidence": evidence}

    def _classify_runner_after_primary_kill(self, session: dict) -> dict:
        from solana_alpha_lab.factory.hfic_session import (
            apply_classification,
            finalize_session,
        )
        from tests.test_fast_lane_classifier import submission
        from tests.test_hfic_cli import critic_result_from_packet_only
        from tests.test_hfic_one_frozen_runner_up_failover_v1 import _with_selected_feats

        data_root = session["data_root"]
        frozen = session["frozen"]
        store = ResearchStore(data_root)
        pending = finalize_session(
            frozen,
            critic_result_from_packet_only(
                frozen["critic_input_packet"], "KILL_MECHANISM"
            ),
            store=store,
            repo_root=ROOT,
            data_root=data_root,
        )
        waiting = finalize_session(
            pending,
            critic_result_from_packet_only(
                pending["critic_input_packet"], "PASS_TO_CLASSIFICATION"
            ),
            store=store,
            repo_root=ROOT,
            data_root=data_root,
        )
        if waiting.get("session_state") != "AWAITING_CLASSIFICATION":
            return waiting
        runner_packet = frozen["runner_up_critic_input_packet"]
        spec = _with_selected_feats(submission(), runner_packet)
        spec["experiment_spec"]["data_bindings"] = [
            {
                "binding_id": "BINDING-DATASET-MISSING-001",
                "source_kind": "DATASET_MANIFEST",
                "stable_id": "DATASET-MANIFEST-MISSING-001",
                "expected_content_sha256_or_dataset_fingerprint": "a" * 64,
            }
        ]
        spec["hypothesis_definition_sha256"] = frozen["runner_up_definition_sha256"]
        return apply_classification(
            waiting,
            spec,
            store=store,
            repo_root=ROOT,
            data_root=data_root,
        )

    def test_unlinked_runner_up_cannot_take_scientific_pass(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            session = self._freeze_scoped_runner(Path(raw), runner_matches_look=False)
            runner_evidence = session["frozen"]["runner_up_critic_input_packet"][
                "grounded_evidence"
            ]
            self.assertNotIn("result", runner_evidence)
            self.assertNotIn("result_refs", runner_evidence)
            self.assertNotIn("result_sha256", runner_evidence)
            done = self._classify_runner_after_primary_kill(session)
            self.assertEqual(done["final_session_terminal"], "KILL_UNBOUND_EVIDENCE")
            self.assertEqual(done.get("runner_up_critic_terminal"), "KILL_UNBOUND_EVIDENCE")
            self.assertNotEqual(done.get("session_state"), "AWAITING_CLASSIFICATION")
            decision = done["decisions"][session["frozen"]["runner_up_candidate_id"]]
            self.assertEqual(decision["reason_code"], "KILL_UNBOUND_EVIDENCE")
            self.assertEqual(decision["decision_kind"], "REJECT")
            self._assert_unbound_kill_does_not_close_memory(session, done)

    def _assert_unbound_kill_does_not_close_memory(self, session: dict, done: dict) -> None:
        from solana_alpha_lab.factory.hfic_memory_policy import (
            iter_search_memory_hypothesis_payloads,
        )
        from solana_alpha_lab.factory.hfic_prior_memory import build_prior_memory_snapshot
        from solana_alpha_lab.factory.hfic_reopened_prior_routing import (
            ranked_prior_entries_for_ids,
        )

        store = ResearchStore(session["data_root"])
        runner_id = session["frozen"]["runner_up_candidate_id"]
        snapshot = build_prior_memory_snapshot(
            store,
            store_inventory_digest=store.diagnostics().committed_inventory_sha256,
        )
        capsule = next(
            item
            for item in snapshot["capsules"]
            if item["hypothesis_version_id"] == runner_id
        )
        self.assertEqual(capsule["reason_code"], "KILL_UNBOUND_EVIDENCE")
        self.assertEqual(capsule["memory_status"], "TECHNICAL_STOP")
        self.assertNotEqual(capsule["memory_status"], "HARD_CLOSE")
        payloads = list(iter_search_memory_hypothesis_payloads(store))
        ranked = ranked_prior_entries_for_ids([runner_id], payloads, store=store)
        self.assertEqual(ranked[0]["memory_status"], "TECHNICAL_STOP")
        self.assertEqual(ranked[0]["reason_code"], "KILL_UNBOUND_EVIDENCE")
        scope = {
            key: capsule[key]
            for key in (
                "population",
                "decision_timestamp",
                "target",
                "estimand",
                "explanatory_condition",
                "evidence_surface_mode",
                "representation_scope",
            )
            if capsule.get(key)
        }
        scope.setdefault("evidence_surface_mode", "ORDINARY_GROUNDED_DISCOVERY_V1")
        bound = bind_prior_scope_evidence(
            {"candidate_scope": scope, "priors": []},
            canonical_priors=snapshot["capsules"],
        )
        relation = next(
            item["relation"]
            for item in bound["prior_scope_relations"]
            if item.get("hypothesis_version_id") == runner_id
        )
        self.assertIn(relation, {"NON_BLOCKING_PRIOR", "UNKNOWN_SCOPE_NEEDS_RESOLUTION"})
        self.assertNotIn(relation, {"EXACT_SCOPE_MATCH", "EXACT_VALID_CLOSE"})
        self.assertEqual(done["final_session_terminal"], "KILL_UNBOUND_EVIDENCE")

    def test_recorded_unbound_kill_is_technical_and_mechanism_still_blocks(self) -> None:
        unbound_id = "HFIC-CAND-RECORDED-UNBOUND"
        mechanism_id = "HFIC-CAND-RECORDED-MECHANISM"
        axes = {
            "population": "BASE_X",
            "decision_timestamp": "X300",
            "target": "target_same",
            "estimand": "estimand_same",
            "explanatory_condition": "cond_same",
            "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1",
            "representation_scope": "rep_same",
        }
        common = {
            "session_id": "HFIC-SESS-RECORDED-KILL",
            "hfic_protocol": "HFIC-V1.2",
            "mechanism": "recorded close",
            "actor_counterparty": "crowd",
            "primary_x_family": "ACTIVITY_VOLUME",
            "primary_y": "path",
            "horizon_notional": "Y1800",
            "negative_control": "shuffled",
            "cheapest_falsifier": "falsifier",
            **axes,
        }
        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            store.append(
                [
                    _event(
                        RecordKind.HYPOTHESIS_VERSION,
                        "HFIC-HYP-UNBOUND",
                        {
                            **common,
                            "hypothesis_version_id": unbound_id,
                            "claim": "recorded unbound kill",
                        },
                        hyp=unbound_id,
                    ),
                    _event(
                        RecordKind.HYPOTHESIS_VERSION,
                        "HFIC-HYP-MECHANISM",
                        {
                            **common,
                            "hypothesis_version_id": mechanism_id,
                            "claim": "recorded mechanism kill",
                        },
                        hyp=mechanism_id,
                    ),
                    _event(
                        RecordKind.DECISION_EVENT,
                        "HFIC-DEC-UNBOUND",
                        {
                            "hypothesis_version_id": unbound_id,
                            "decision_kind": "REJECT",
                            "reason_code": "KILL_UNBOUND_EVIDENCE",
                        },
                        hyp=unbound_id,
                    ),
                    _event(
                        RecordKind.DECISION_EVENT,
                        "HFIC-DEC-MECHANISM",
                        {
                            "hypothesis_version_id": mechanism_id,
                            "decision_kind": "REJECT",
                            "reason_code": "KILL_MECHANISM",
                        },
                        hyp=mechanism_id,
                    ),
                ],
                transaction_id="RESEARCH-TXN-BINDING-001",
            )
            from solana_alpha_lab.factory.hfic_prior_memory import build_prior_memory_snapshot

            snapshot = build_prior_memory_snapshot(
                store,
                store_inventory_digest="ab" * 32,
            )
            by_id = {item["hypothesis_version_id"]: item for item in snapshot["capsules"]}
            self.assertEqual(by_id[unbound_id]["memory_status"], "TECHNICAL_STOP")
            self.assertEqual(by_id[mechanism_id]["memory_status"], "HARD_CLOSE")
            allowed = bind_prior_scope_evidence(
                {"candidate_scope": dict(axes), "priors": []},
                canonical_priors=[by_id[unbound_id]],
            )
            self.assertEqual(
                allowed["prior_scope_relations"][0]["relation"],
                "NON_BLOCKING_PRIOR",
            )
            with self.assertRaises(GroundedDiscoveryError) as caught:
                bind_prior_scope_evidence(
                    {"candidate_scope": dict(axes), "priors": []},
                    canonical_priors=[by_id[mechanism_id]],
                )
            self.assertEqual(caught.exception.code, "EXACT_PRIOR_SCOPE_MATCH")

    def test_retry_does_not_rename_look_and_contradiction_stops_freeze(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            session = self._freeze_scoped_runner(
                workspace,
                runner_matches_look=False,
                selected_target="target_B",
                selected_estimand="estimand_B",
                selected_decision="X900",
                expect_freeze_error="LOOK_SCOPE_CONTRADICTION",
            )
            evidence = session["evidence"]
            self.assertEqual(evidence["candidate_scope"]["target"], MEASURED_TARGET)
            scope_path = workspace / "scope.json"
            scope_path.write_text(
                json.dumps(
                    {
                        **evidence["candidate_scope"],
                        "target": "target_RENAMED",
                        "estimand": "estimand_RENAMED",
                    }
                ),
                encoding="utf-8",
            )
            renamed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "scripts/hypothesis_forge.py",
                    "--root",
                    str(ROOT),
                    "--data-root",
                    str(session["data_root"]),
                    "discovery-execute",
                    "--store",
                    str(session["data_root"]),
                    "--spec",
                    str(workspace / "spec.json"),
                    "--candidate-scope",
                    str(scope_path),
                    "--journal-scope",
                    str(evidence["journal_scope"]),
                    "--format",
                    "json",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
            )
            self.assertEqual(renamed.returncode, 0, renamed.stderr)
            again = json.loads(renamed.stdout)
            self.assertEqual(again["candidate_scope"]["target"], MEASURED_TARGET)
            self.assertEqual(again["candidate_scope"]["estimand"], "estimand_A")
            self.assertNotEqual(again["requested_candidate_scope"]["target"], MEASURED_TARGET)
            self.assertEqual(again["look_scope_relation"], "LOOK_SCOPE_NARROWER")
            self.assertFalse(again["queries"][0]["new_look"])
            hypothesis_ids = [
                json.loads(record.payload_json).get("hypothesis_version_id")
                for record in ResearchStore(session["data_root"]).iter_committed_records()
                if getattr(record.record_kind, "value", record.record_kind) == "HYPOTHESIS_VERSION"
            ]
            self.assertEqual(
                hypothesis_ids,
                ["HYP-QUOTE-NATIVE-FRICTION-H900-V1"],
            )

    def test_narrower_idea_is_saved_without_scientific_pass_or_close(self) -> None:
        from solana_alpha_lab.factory.hfic_prior_memory import build_prior_memory_snapshot
        from solana_alpha_lab.factory.hfic_session import finalize_session
        from tests.test_hfic_cli import critic_result_from_packet_only

        with tempfile.TemporaryDirectory() as raw:
            session = self._freeze_scoped_runner(
                Path(raw),
                runner_matches_look=False,
                scope_estimand=None,
                selected_target="target_A",
                selected_estimand="estimand_narrow",
            )
            frozen = session["frozen"]
            evidence = frozen["critic_input_packet"]["grounded_evidence"]
            self.assertFalse(evidence.get("look_confirms_selected"))
            self.assertEqual(evidence.get("look_scope_relation"), "LOOK_SCOPE_NARROWER")
            self.assertNotIn("result", evidence)
            self.assertNotIn("result_sha256", evidence)
            versions = {}
            for record in ResearchStore(session["data_root"]).iter_committed_records():
                kind = getattr(record.record_kind, "value", record.record_kind)
                if kind != "HYPOTHESIS_VERSION":
                    continue
                payload = json.loads(record.payload_json)
                versions[payload["hypothesis_version_id"]] = payload
            selected = versions[frozen["selected_candidate_id"]]
            self.assertEqual(selected["estimand"], "estimand_narrow")
            self.assertEqual(selected["target"], "target_A")
            store = ResearchStore(session["data_root"])
            done = finalize_session(
                frozen,
                critic_result_from_packet_only(
                    frozen["critic_input_packet"], "KILL_MECHANISM"
                ),
                store=store,
                repo_root=ROOT,
                data_root=session["data_root"],
            )
            self.assertEqual(
                done["decisions"][frozen["selected_candidate_id"]]["reason_code"],
                "KILL_UNBOUND_EVIDENCE",
            )
            self.assertNotEqual(done.get("final_session_terminal"), "KILL_MECHANISM")
            snapshot = build_prior_memory_snapshot(
                store,
                store_inventory_digest=store.diagnostics().committed_inventory_sha256,
            )
            capsule = next(
                item
                for item in snapshot["capsules"]
                if item["hypothesis_version_id"] == frozen["selected_candidate_id"]
            )
            self.assertEqual(capsule["memory_status"], "TECHNICAL_STOP")
            self.assertNotEqual(capsule["memory_status"], "HARD_CLOSE")
            from solana_alpha_lab.factory.hfic_prior_memory import compact_forge_prior_entry

            note = compact_forge_prior_entry(
                frozen["selected_candidate_id"],
                selected,
                {"decision_kind": "REJECT", "reason_code": "KILL_UNBOUND_EVIDENCE"},
            )
            self.assertEqual(
                note["technical_stop_note"],
                "Технический отказ не является отрицательным рыночным результатом.",
            )

    def test_narrower_idea_cannot_take_scientific_pass(self) -> None:
        from solana_alpha_lab.factory.hfic_session import finalize_session
        from tests.test_hfic_cli import critic_result_from_packet_only

        with tempfile.TemporaryDirectory() as raw:
            session = self._freeze_scoped_runner(
                Path(raw),
                runner_matches_look=False,
                scope_estimand=None,
                selected_target="target_A",
                selected_estimand="estimand_narrow",
            )
            frozen = session["frozen"]
            self.assertFalse(
                frozen["critic_input_packet"]["grounded_evidence"].get("look_confirms_selected")
            )
            store = ResearchStore(session["data_root"])
            done = finalize_session(
                frozen,
                critic_result_from_packet_only(
                    frozen["critic_input_packet"], "PASS_TO_CLASSIFICATION"
                ),
                store=store,
                repo_root=ROOT,
                data_root=session["data_root"],
            )
            self.assertNotEqual(done.get("session_state"), "AWAITING_CLASSIFICATION")
            self.assertEqual(
                done["decisions"][frozen["selected_candidate_id"]]["reason_code"],
                "KILL_UNBOUND_EVIDENCE",
            )
            self.assertNotIn(
                done.get("final_session_terminal"),
                {
                    "PASS_FAST_LANE_READY",
                    "PASS_DATA_OPTION_REQUIRED",
                    "PASS_CHANGE_LANE_REQUIRED",
                },
            )

    def test_foreign_decision_moment_does_not_match_the_look(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            session = self._freeze_scoped_runner(
                Path(raw),
                runner_matches_look=False,
                selected_decision="X900",
                expect_freeze_error="LOOK_SCOPE_CONTRADICTION",
            )
            self.assertIsNone(session["frozen"])
            self.assertEqual(session["evidence"]["candidate_scope"]["decision_timestamp"], "X300")

    def test_declared_scope_must_match_the_spec_decision(self) -> None:
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            GroundedDiscoveryError,
            run_recorded_discovery_query,
        )

        spec = {
            "query_id": "SPEC_SCOPE",
            "population": "BASE_X",
            "decision_points": ["X300"],
            "decision_fields": ["FIELD-USD-PRICE-001"],
            "target_point": "Y1800",
            "target_field": "FIELD-USD-PRICE-001",
            "explanatory": [],
        }
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            with self.assertRaises(GroundedDiscoveryError) as caught:
                run_recorded_discovery_query(
                    store,
                    census=[],
                    observations=[],
                    spec=spec,
                    binding=[],
                    journal_scope="journal",
                    candidate_scope={
                        "population": "BASE_X",
                        "decision_timestamp": "X900",
                        "target": "target_A",
                        "estimand": "estimand_A",
                    },
                    git_sha="ab" * 20,
                )
            self.assertEqual(caught.exception.code, "LOOK_SPEC_SCOPE_MISMATCH")
            self.assertEqual(list(store.iter_committed_records()), [])

    def test_foreign_population_does_not_match_the_look(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            session = self._freeze_scoped_runner(
                Path(raw),
                runner_matches_look=False,
                selected_population="OTHER_POP",
                expect_freeze_error="LOOK_SCOPE_CONTRADICTION",
            )
            self.assertIsNone(session["frozen"])
            self.assertEqual(session["evidence"]["candidate_scope"]["population"], "BASE_X")

    def test_declared_population_must_match_the_spec(self) -> None:
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            GroundedDiscoveryError,
            run_recorded_discovery_query,
        )

        spec = {
            "query_id": "SPEC_POPULATION",
            "population": "BASE_X",
            "decision_points": ["X300"],
            "decision_fields": ["FIELD-USD-PRICE-001"],
            "target_point": "Y1800",
            "target_field": "FIELD-USD-PRICE-001",
            "explanatory": [],
        }
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            with self.assertRaises(GroundedDiscoveryError) as caught:
                run_recorded_discovery_query(
                    store,
                    census=[],
                    observations=[],
                    spec=spec,
                    binding=[],
                    journal_scope="journal",
                    candidate_scope={
                        "population": "OTHER_POP",
                        "decision_timestamp": "X300",
                    },
                    git_sha="ab" * 20,
                )
            self.assertEqual(caught.exception.code, "LOOK_SPEC_SCOPE_MISMATCH")
            self.assertEqual(list(store.iter_committed_records()), [])

    def test_spec_fills_omitted_machine_scope(self) -> None:
        from solana_alpha_lab.factory.hfic_grounded_discovery import scope_bound_to_spec

        spec = {
            "query_id": "SPEC_FILL",
            "population": "BASE_X",
            "decision_points": ["X300"],
            "decision_fields": ["FIELD-USD-PRICE-001"],
            "target_point": "Y1800",
            "target_field": "FIELD-USD-PRICE-001",
            "explanatory": [],
        }
        bound = scope_bound_to_spec(spec, {"target": "target_A", "estimand": "estimand_A"})
        self.assertEqual(bound["population"], "BASE_X")
        self.assertEqual(bound["decision_timestamp"], "X300")
        self.assertEqual(bound["target"], MEASURED_TARGET)
        later = {
            **spec,
            "query_id": "SPEC_LATER_DECISION",
            "decision_points": ["X300", "Y900"],
            "target_point": "Y1800",
        }
        filled = scope_bound_to_spec(later, {"target": "Y3600:FIELD-LIQUIDITY-USD-001"})
        self.assertEqual(filled["decision_timestamp"], "Y900")
        self.assertEqual(filled["target"], MEASURED_TARGET)
        self.assertNotIn("Y3600", filled["target"])

    def test_earlier_decision_point_cannot_label_a_later_look(self) -> None:
        from solana_alpha_lab.factory.hfic_grounded_discovery import (
            GroundedDiscoveryError,
            run_recorded_discovery_query,
        )

        spec = {
            "query_id": "PIT_DECISION",
            "population": "BASE_X",
            "decision_points": ["X300", "Y900"],
            "decision_fields": ["FIELD-USD-PRICE-001"],
            "target_point": "Y1800",
            "target_field": "FIELD-USD-PRICE-001",
            "explanatory": [],
        }
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            with self.assertRaises(GroundedDiscoveryError) as caught:
                run_recorded_discovery_query(
                    store,
                    census=[],
                    observations=[],
                    spec=spec,
                    binding=[],
                    journal_scope="journal",
                    candidate_scope={
                        "population": "BASE_X",
                        "decision_timestamp": "X300",
                        "target": MEASURED_TARGET,
                    },
                    git_sha="ab" * 20,
                )
            self.assertEqual(caught.exception.code, "LOOK_SPEC_SCOPE_MISMATCH")
            self.assertEqual(list(store.iter_committed_records()), [])

    def test_free_text_target_cannot_confirm_another_measurement(self) -> None:
        from solana_alpha_lab.factory.hfic_session import finalize_session
        from tests.test_hfic_cli import critic_result_from_packet_only

        lied = "Y3600:FIELD-LIQUIDITY-USD-001"
        with tempfile.TemporaryDirectory() as raw:
            session = self._freeze_scoped_runner(
                Path(raw),
                runner_matches_look=False,
                scope_target=lied,
                selected_target=lied,
            )
            self.assertEqual(session["evidence"]["candidate_scope"]["target"], MEASURED_TARGET)
            self.assertEqual(session["evidence"]["candidate_scope"]["decision_timestamp"], "X300")
            frozen = session["frozen"]
            evidence = frozen["critic_input_packet"]["grounded_evidence"]
            self.assertFalse(evidence.get("look_confirms_selected"))
            self.assertEqual(evidence.get("look_scope_relation"), "LOOK_SCOPE_NARROWER")
            self.assertNotIn("result", evidence)
            done = finalize_session(
                frozen,
                critic_result_from_packet_only(
                    frozen["critic_input_packet"], "PASS_TO_CLASSIFICATION"
                ),
                store=ResearchStore(session["data_root"]),
                repo_root=ROOT,
                data_root=session["data_root"],
            )
            self.assertNotEqual(done.get("session_state"), "AWAITING_CLASSIFICATION")
            self.assertEqual(
                done["decisions"][frozen["selected_candidate_id"]]["reason_code"],
                "KILL_UNBOUND_EVIDENCE",
            )
            self.assertNotIn(
                done.get("final_session_terminal"),
                {
                    "PASS_FAST_LANE_READY",
                    "PASS_DATA_OPTION_REQUIRED",
                    "PASS_CHANGE_LANE_REQUIRED",
                },
            )

    def test_card_only_machine_axis_is_not_confirmation(self) -> None:
        from solana_alpha_lab.factory.hfic_grounded_discovery import relate_look_scope

        relation = relate_look_scope(
            {"population": "BASE_X", "target": "target_A", "estimand": "estimand_A"},
            {
                "population": "BASE_X",
                "decision_timestamp": "X300",
                "target": "target_A",
                "estimand": "estimand_A",
            },
        )
        self.assertEqual(relation, "LOOK_SCOPE_NARROWER")
        omitted = relate_look_scope(
            {
                "population": "BASE_X",
                "decision_timestamp": "X300",
                "target": "target_A",
                "estimand": "estimand_A",
            },
            {"population": "BASE_X", "decision_timestamp": "X300", "target": "target_A"},
        )
        self.assertEqual(omitted, "LOOK_SCOPE_NARROWER")

    def test_revision_locks_target_and_preserves_look_for_wording(self) -> None:
        from solana_alpha_lab.factory.hfic_session import HficSessionError, apply_revision, finalize_session
        from tests.test_hfic_cli import critic_result_from_packet_only

        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            session = self._freeze_scoped_runner(workspace, runner_matches_look=True)
            frozen = session["frozen"]
            self.assertTrue(
                frozen["critic_input_packet"]["grounded_evidence"].get("look_confirms_selected")
            )
            store = ResearchStore(session["data_root"])
            critic = critic_result_from_packet_only(
                frozen["critic_input_packet"], "REVISE_ONCE"
            )
            critic["revision_receipt"] = {"scope": "target", "attempt": 1}
            pending = finalize_session(
                frozen,
                critic,
                store=store,
                repo_root=ROOT,
                data_root=session["data_root"],
            )
            self.assertEqual(pending["session_state"], "REVISION_REQUIRED")
            draft = json.loads((workspace / "draft.json").read_text(encoding="utf-8"))
            for card in draft["candidates"]:
                if card["label"] == "HFIC-V12-A-LOOK":
                    card["target"] = "target_REVISED"
            before = [(row.record_id, row.payload_sha256) for row in store.iter_committed_records()]
            with self.assertRaisesRegex(HficSessionError, "^REVISION_MECHANISM_CHANGED$"):
                apply_revision(pending, draft, store=store, repo_root=ROOT)
            self.assertEqual(before, [(row.record_id, row.payload_sha256) for row in store.iter_committed_records()])
            self.assertEqual(pending["session_state"], "REVISION_REQUIRED")
            # A wording revision retains the scientific question and its saved look.
            wording = json.loads((workspace / "draft.json").read_text(encoding="utf-8"))
            for card in wording["candidates"]:
                if card["label"] == "HFIC-V12-A-LOOK":
                    card["claim"] += " (editorial clarification)"
            revised = apply_revision(pending, wording, store=store, repo_root=ROOT)
            evidence = revised["critic_input_packet"]["grounded_evidence"]
            self.assertTrue(evidence.get("look_confirms_selected"))
            original = frozen["critic_input_packet"]["grounded_evidence"]
            self.assertEqual(evidence["result_refs"], original["result_refs"])
            self.assertEqual(evidence["result_sha256"], original["result_sha256"])

    def test_same_scope_runner_up_keeps_ordinary_classification(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            session = self._freeze_scoped_runner(Path(raw), runner_matches_look=True)
            primary = session["frozen"]["critic_input_packet"]["grounded_evidence"]
            self.assertTrue(primary.get("look_confirms_selected"))
            self.assertEqual(primary["candidate_scope"]["population"], "BASE_X")
            self.assertEqual(primary["candidate_scope"]["decision_timestamp"], "X300")
            self.assertEqual(primary["candidate_scope"]["target"], MEASURED_TARGET)
            self.assertEqual(primary["result_refs"], session["evidence"]["result_refs"])
            runner_evidence = session["frozen"]["runner_up_critic_input_packet"][
                "grounded_evidence"
            ]
            self.assertEqual(
                runner_evidence["result_refs"],
                session["evidence"]["result_refs"],
            )
            self.assertEqual(
                runner_evidence["result_sha256"],
                session["evidence"]["result_sha256"],
            )
            done = self._classify_runner_after_primary_kill(session)
            self.assertEqual(done["final_session_terminal"], "PASS_DATA_OPTION_REQUIRED")
            self.assertEqual(
                done.get("runner_up_critic_terminal"), "PASS_DATA_OPTION_REQUIRED"
            )
            diagnostics = (done.get("session_receipt") or {}).get("diagnostics") or {}
            self.assertNotIn(
                "GROUNDED_RESULT_UNBOUND",
                diagnostics.get("availability_gate_reason_codes") or [],
            )
            decision = done["decisions"][session["frozen"]["runner_up_candidate_id"]]
            self.assertEqual(decision["reason_code"], "PASS_DATA_OPTION_REQUIRED")

    def test_latest_decision_point_confirms_through_critic(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            session = self._freeze_scoped_runner(
                Path(raw),
                runner_matches_look=True,
                decision_points=["X300", "Y900"],
                selected_decision="Y900",
            )
            evidence = session["evidence"]["candidate_scope"]
            self.assertEqual(evidence["decision_timestamp"], "Y900")
            self.assertEqual(evidence["target"], MEASURED_TARGET)
            primary = session["frozen"]["critic_input_packet"]["grounded_evidence"]
            self.assertTrue(primary.get("look_confirms_selected"))
            self.assertEqual(primary["candidate_scope"]["decision_timestamp"], "Y900")
            done = self._classify_runner_after_primary_kill(session)
            self.assertEqual(done["final_session_terminal"], "PASS_DATA_OPTION_REQUIRED")
            decision = done["decisions"][session["frozen"]["runner_up_candidate_id"]]
            self.assertEqual(decision["reason_code"], "PASS_DATA_OPTION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
