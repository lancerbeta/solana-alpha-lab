"""Published discovery corpus resolves an admission binding without a hand-written holdout."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
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


if __name__ == "__main__":
    unittest.main()
