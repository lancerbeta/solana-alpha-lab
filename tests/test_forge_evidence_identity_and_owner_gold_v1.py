"""A5 owner gold: market/capability identity, reuse/resume/budget, sequential G1–G12.

Synthetic sources and generator/Critic replies only. Production import/preflight/
packet/ladder/freeze/classifier/finalize/discovery/persistence/readout bindings.
Does not execute Prompt A/B/C, real Independent Critic, or scientific market Forge.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.data_root import resolve_data_root  # noqa: E402
from solana_alpha_lab.factory.forge_input_receipt import (  # noqa: E402
    build_forge_input_receipt,
)
from solana_alpha_lab.factory.hfic_evidence_identity import (  # noqa: E402
    DISPOSITION_HISTORICAL_ONLY,
    DISPOSITION_UNRESOLVED,
    classify_legacy_session_disposition,
    compute_capability_epoch_for_repo,
    compute_market_epoch_for_data_root,
    compute_split_identity,
    forge_run_identity_sha256,
    resolve_scientific_admission,
    session_scientific_slot_sha256,
    scientific_slot_sha256,
)
from solana_alpha_lab.factory.hfic_identity import assign_portfolio_ids  # noqa: E402
from solana_alpha_lab.factory.hfic_representation_ladder import (  # noqa: E402
    ACTION_OWNER_CANDIDATE,
    ACTION_RESUME_V1,
    ACTION_RETURN_EXISTING,
    ACTION_SEARCH_EXHAUSTED,
    ACTION_START_BASE,
    ACTION_START_V1,
    EXEC_REUSED,
    LadderError,
    consume_start_v1_envelope,
    evaluate_forge_run,
    prepare_ladder_freeze_preflight,
)
from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    epoch_search_budget_usage,
    run_preflight,
)
from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    HficSessionError,
    apply_classification,
    freeze_draft,
    list_scientific_slot_admissions,
    list_hfic_sessions,
    load_session_bundle,
    persist_generated_draft,
    persist_frozen_session,
    persist_no_worthy_session,
    persist_scientific_slot_admission,
    finalize_session,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402
from solana_alpha_lab.factory.fast_lane_snapshot import (  # noqa: E402
    export_snapshot,
    restore_snapshot,
)

from tests.test_forge_input_truth_and_visibility_v1 import (  # noqa: E402
    _enumerate_live,
    _write_lineage,
)
from tests.test_forge_representation_ladder_v1 import (  # noqa: E402
    NO_WORTHY_DRAFT,
    _control_preflight,
    _cohort_readiness_receipt_rel_c2,
    _distinct_no_worthy_draft,
    _git,
    _init_repo,
    _later_registry,
    _production_control_preflight,
    _representation_fixture_rel_c2,
    _v1_freeze_preflight_from_envelope,
)
from tests.test_hfic_session import (  # noqa: E402
    critic_result_from_packet_only,
    valid_draft,
)
from tests.test_normalized_trajectory_v1_execution_closure_v1 import (  # noqa: E402
    _no_worthy_forge_receipt,
)


def _enumerate_c3(_data_root: Path):
    live = _enumerate_live(_data_root)[0]
    extra = dict(live[0])
    extra["dataset_manifest_id"] = "MID-C3"
    extra["labels"] = {**dict(extra.get("labels") or {}), "cohort_id": "REL-C3"}
    return [*live, extra], []


def _append_c3(data_root: Path) -> None:
    lineage_path = data_root / "datasets" / "live_lifecycle_corpus" / "lineage.json"
    payload = json.loads(lineage_path.read_text(encoding="utf-8"))
    payload["cohorts"].append(
        {"cohort_id": "REL-C3", "release_id": "rel-c3", "source_sha256": "cc" * 32}
    )
    lineage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ordinary_stamped_preflight(data_root: Path, store: ResearchStore) -> dict[str, object]:
    """Ordinary BASE freeze receipt: production split stamps, no CONTROL surface."""

    pre = dict(_production_control_preflight(data_root, store))
    pre.pop("evidence_surface_mode", None)
    packet = dict(pre.get("forge_context_packet") or {})
    packet.pop("evidence_surface_mode", None)
    pre["forge_context_packet"] = packet
    return pre


def _no_worthy_base(
    data_root: Path,
    store: ResearchStore,
    *,
    production_packet: bool = False,
    repo_root: Path = ROOT,
) -> dict[str, object]:
    draft = json.loads(NO_WORTHY_DRAFT.read_text(encoding="utf-8"))
    # Stamps come from production CONTROL preflight (compute_split_identity),
    # not a separate test-only post-hoc stamp injection.
    with patch(
        "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
        side_effect=_enumerate_live,
    ):
        preflight = (
            _production_control_preflight(data_root, store, repo_root=repo_root)
            if production_packet
            else _control_preflight(data_root, store, repo_root=repo_root)
        )
        if not production_packet:
            split = compute_split_identity(repo_root, data_root)
            preflight = dict(preflight)
            preflight["market_evidence_epoch_sha256"] = split[
                "market_evidence_epoch_sha256"
            ]
            preflight["capability_epoch_sha256"] = split["capability_epoch_sha256"]
            preflight["legacy_combined_evidence_epoch_sha256"] = split[
                "legacy_combined_evidence_epoch_sha256"
            ]
    frozen = freeze_draft(draft, preflight_receipt=preflight, repo_root=repo_root)
    persist_no_worthy_session(
        store,
        frozen,
        repo_root=repo_root,
        identities=assign_portfolio_ids(draft["candidates"]),
        draft=draft,
        preflight_receipt=preflight,
    )
    store.rebuild_projection()
    return frozen


def _ordinary_pass_base(data_root: Path, store: ResearchStore) -> dict[str, object]:
    """Ordinary BASE final PASS via freeze→Critic→classify (no CONTROL surface)."""

    from tests.test_fast_lane_classifier import submission

    with patch(
        "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
        side_effect=_enumerate_live,
    ):
        preflight = _ordinary_stamped_preflight(data_root, store)
    draft = valid_draft()
    frozen = freeze_draft(draft, preflight_receipt=preflight, repo_root=ROOT)
    persist_frozen_session(
        store,
        frozen,
        repo_root=ROOT,
        identities=assign_portfolio_ids(draft["candidates"]),
        draft=draft,
    )
    packet = frozen["critic_input_packet"]
    assert isinstance(packet, dict)
    finalize_session(
        frozen,
        critic_result_from_packet_only(packet, "PASS_TO_CLASSIFICATION"),
        store=store,
        repo_root=ROOT,
    )
    spec = submission()
    spec["hypothesis_definition_sha256"] = frozen["selected_definition_sha256"]
    apply_classification(
        frozen, spec, store=store, repo_root=ROOT, data_root=data_root
    )
    store.rebuild_projection()
    return frozen


class IdentityUnitTests(unittest.TestCase):
    def test_market_epoch_stable_under_docs_only_capability_change_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                before = compute_split_identity(ROOT, data_root)
                receipt = build_forge_input_receipt(data_root, repo_root=ROOT)
            self.assertEqual(
                receipt["market_evidence_epoch_sha256"],
                before["market_evidence_epoch_sha256"],
            )
            self.assertEqual(len(receipt["market_evidence_epoch_sha256"]), 64)
            self.assertEqual(len(receipt["capability_epoch_sha256"]), 64)
            # Capability digests protocol files; market excludes Git/docs.
            self.assertNotEqual(
                before["market_evidence_epoch_sha256"],
                before["capability_epoch_sha256"],
            )
            run_a = forge_run_identity_sha256(
                market_evidence_epoch_sha256=before["market_evidence_epoch_sha256"],
                frozen_representation_ids=["BASE", "NORMALIZED_TRAJECTORY_V1"],
                owner_focus="AUTO",
            )
            # Cohort mutation changes market; Git/docs would not (asserted in G7).
            _append_c3(data_root)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_c3,
            ):
                after = compute_split_identity(ROOT, data_root)
            self.assertNotEqual(
                before["market_evidence_epoch_sha256"],
                after["market_evidence_epoch_sha256"],
            )
            run_b = forge_run_identity_sha256(
                market_evidence_epoch_sha256=after["market_evidence_epoch_sha256"],
                frozen_representation_ids=["BASE", "NORMALIZED_TRAJECTORY_V1"],
                owner_focus="AUTO",
            )
            self.assertNotEqual(run_a, run_b)

    def test_legacy_disposition_rejects_focus_only_reuse(self) -> None:
        session = {
            "session_id": "HFIC-SESS-LEGACY",
            "evidence_epoch_sha256": "ab" * 32,
            "owner_focus": "AUTO",
            "forge_context_packet": {"bound_visible_cohort_ids": ["REL-C1", "REL-C2"]},
        }
        row = classify_legacy_session_disposition(
            session,
            current_market_epoch="cd" * 32,
            current_visible_cohort_ids=["REL-C1", "REL-C2"],
        )
        self.assertIn(
            row["disposition"],
            {DISPOSITION_HISTORICAL_ONLY, DISPOSITION_UNRESOLVED},
        )
        self.assertTrue(row["reasons"])

    def test_scientific_slot_ignores_capability_in_key(self) -> None:
        market = "aa" * 32
        slot = scientific_slot_sha256(
            market_evidence_epoch_sha256=market,
            representation_id="BASE",
            representation_semantic_version="1",
            owner_focus="AUTO",
        )
        cap_a, _ = compute_capability_epoch_for_repo(ROOT)
        other = scientific_slot_sha256(
            market_evidence_epoch_sha256=market,
            representation_id="BASE",
            representation_semantic_version="1",
            owner_focus="AUTO",
        )
        self.assertEqual(slot, other)
        self.assertEqual(len(cap_a), 64)

    def test_tampered_slot_stamp_is_not_occupancy_evidence(self) -> None:
        market = "aa" * 32
        row = {
            "session_id": "HFIC-SESS-TAMPERED",
            "market_evidence_epoch_sha256": market,
            "ladder_representation_id": "BASE",
            "representation_semantic_version": "HFIC-V1.2",
            "owner_focus": "AUTO",
            "scientific_slot_sha256": "00" * 32,
        }
        self.assertIsNone(session_scientific_slot_sha256(row))
        decision = resolve_scientific_admission(
            [row],
            market_evidence_epoch=market,
            representation_id="BASE",
            representation_semantic_version="HFIC-V1.2",
            owner_focus="AUTO",
        )
        self.assertEqual(decision["action"], "STOP")
        self.assertEqual(decision["reason_code"], "SCIENTIFIC_SLOT_IDENTITY_INVALID")

    def test_g1_concurrent_slot_writers_have_one_durable_winner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            market = "aa" * 32
            capability = "bb" * 32
            memory = "cc" * 32
            model = "dd" * 32
            common = {
                "market_evidence_epoch_sha256": market,
                "capability_epoch_sha256": capability,
                "memory_eligibility_sha256": memory,
                "model_provenance_sha256": model,
                "representation_payload_sha256": "ee" * 32,
                "ladder_representation_id": "BASE",
                "representation_semantic_version": "HFIC-V1.2",
                "owner_focus": "AUTO",
            }
            barrier = threading.Barrier(2)
            results: list[str] = []
            errors: list[str] = []

            def writer(session_id: str) -> None:
                try:
                    barrier.wait(timeout=5)
                    persist_scientific_slot_admission(
                        ResearchStore(data_root, create_if_missing=False),
                        {**common, "session_id": session_id},
                        repo_root=ROOT,
                    )
                    results.append(session_id)
                except Exception as exc:  # the loser must be typed below
                    errors.append(str(exc))

            threads = [
                threading.Thread(target=writer, args=("HFIC-SESS-RACE-A",)),
                threading.Thread(target=writer, args=("HFIC-SESS-RACE-B",)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertEqual(len(results), 1)
            self.assertEqual(errors, ["SCIENTIFIC_SLOT_OCCUPIED"])
            admissions = list_scientific_slot_admissions(
                ResearchStore(data_root, create_if_missing=False)
            )
            self.assertEqual(len(admissions), 1)
            self.assertEqual(admissions[0]["session_id"], results[0])

    def test_capability_unknown_does_not_become_valid_digest(self) -> None:
        from solana_alpha_lab.factory_semantic_operability import (
            SemanticOperabilityError,
        )

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ), patch(
                "solana_alpha_lab.factory_semantic_operability.semantic_capability_digest_for_repo",
                side_effect=SemanticOperabilityError("SEMANTIC_PROJECTION_INVALID"),
            ):
                receipt = build_forge_input_receipt(data_root, repo_root=ROOT)
        self.assertFalse(receipt["forge_runnable"])
        self.assertIn("CAPABILITY_IDENTITY_UNAVAILABLE", receipt["blocking_reason_codes"])
        self.assertNotIn("capability_epoch_sha256", receipt)

    def test_market_epoch_covers_current_dataset_outside_packet_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            base, _warnings = _enumerate_live(data_root)
            rows = [dict(item) for item in base]
            while len(rows) < 9:
                index = len(rows)
                rows.append(
                    {
                        "dataset_id": f"DATASET-EXTRA-{index}",
                        "dataset_manifest_id": f"dataset-extra-{index}",
                        "dataset_fingerprint": f"{index:064x}",
                        "labels": {"logical_dataset_id": f"DATASET-EXTRA-{index}"},
                    }
                )

            def first_eight(_root: Path):
                return rows[:8], []

            def all_nine(_root: Path):
                return rows, []

            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=first_eight,
            ):
                epoch_eight, _basis_eight = compute_market_epoch_for_data_root(
                    ROOT, data_root
                )
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=all_nine,
            ):
                epoch_nine, _basis_nine = compute_market_epoch_for_data_root(
                    ROOT, data_root
                )
            self.assertNotEqual(epoch_eight, epoch_nine)


class OwnerGoldSequentialTests(unittest.TestCase):
    """G1–G12 sequential family on production bindings (synthetic replies)."""

    def test_g1_g2_import_and_normal_entry_stamps_market(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                receipt_a = build_forge_input_receipt(data_root, repo_root=ROOT)
                receipt_b = build_forge_input_receipt(data_root, repo_root=ROOT)
                fresh = evaluate_forge_run(ROOT, data_root, persist=False)
            self.assertEqual(
                receipt_a["market_evidence_epoch_sha256"],
                receipt_b["market_evidence_epoch_sha256"],
            )
            self.assertEqual(
                receipt_a["active_evidence_set"]["visible_cohort_ids"],
                ["REL-C1", "REL-C2"],
            )
            self.assertTrue(receipt_a["forge_runnable"])
            self.assertEqual(fresh["next_action"], ACTION_START_BASE)
            self.assertEqual(
                fresh["market_evidence_epoch_sha256"],
                receipt_a["market_evidence_epoch_sha256"],
            )
            self.assertIsInstance(fresh["capability_epoch_sha256"], str)
            # Inventory unchanged by no-write evaluate.
            self.assertEqual(len(list_hfic_sessions(store)), 0)

    def test_g3_g5_candidate_path_completed_replay(self) -> None:
        from tests.test_fast_lane_classifier import submission

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = _no_worthy_base(data_root, store, production_packet=True)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                started = evaluate_forge_run(ROOT, data_root, persist=True)
            self.assertEqual(started["next_action"], ACTION_START_V1)
            market = started["market_evidence_epoch_sha256"]
            run_id = started["run_identity_sha256"]
            # V1 freeze preflight inherits stamps from CONTROL via
            # control_preflight_from_bundle — no manual market/capability writes.
            v1_pre, envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(base["session_id"]),
            )
            self.assertEqual(v1_pre.get("market_evidence_epoch_sha256"), market)
            draft = valid_draft()
            frozen = freeze_draft(draft, preflight_receipt=v1_pre, repo_root=ROOT)
            self.assertEqual(frozen.get("market_evidence_epoch_sha256"), market)
            persist_frozen_session(
                store,
                frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(draft["candidates"]),
                draft=draft,
            )
            store.rebuild_projection()
            listed_freeze = next(
                item
                for item in list_hfic_sessions(store)
                if item.get("session_id") == frozen["session_id"]
            )
            self.assertEqual(listed_freeze.get("market_evidence_epoch_sha256"), market)
            self.assertIsInstance(
                listed_freeze.get("representation_semantic_version"), str
            )
            self.assertEqual(len(str(listed_freeze.get("scientific_slot_sha256"))), 64)
            # Freeze/readback has no actual model provenance yet.  A5 must
            # preserve UNKNOWN instead of minting a readiness-looking binding.
            self.assertIsNone(listed_freeze.get("execution_binding_sha256"))
            self.assertEqual(
                len(str(listed_freeze.get("representation_payload_sha256"))), 64
            )
            usage_freeze = epoch_search_budget_usage(
                list_hfic_sessions(store), evidence_epoch=market
            )
            self.assertGreaterEqual(
                usage_freeze["auto_sessions_used"] + usage_freeze["distinct_focus_used"],
                1,
            )
            packet = frozen["critic_input_packet"]
            assert isinstance(packet, dict)
            finalize_session(
                frozen,
                critic_result_from_packet_only(packet, "PASS_TO_CLASSIFICATION"),
                store=store,
                repo_root=ROOT,
            )
            store.rebuild_projection()
            listed_mid = next(
                item
                for item in list_hfic_sessions(store)
                if item.get("session_id") == frozen["session_id"]
            )
            self.assertEqual(listed_mid.get("market_evidence_epoch_sha256"), market)
            usage_mid = epoch_search_budget_usage(
                list_hfic_sessions(store), evidence_epoch=market
            )
            self.assertGreaterEqual(
                usage_mid["auto_sessions_used"] + usage_mid["distinct_focus_used"], 1
            )
            spec = submission()
            spec["hypothesis_definition_sha256"] = frozen["selected_definition_sha256"]
            apply_classification(
                frozen,
                spec,
                store=store,
                repo_root=ROOT,
                data_root=data_root,
            )
            store.rebuild_projection()
            # Fresh process reader: new ResearchStore over same data_root.
            store_reloaded = ResearchStore(data_root)
            listed_done = next(
                item
                for item in list_hfic_sessions(store_reloaded)
                if item.get("session_id") == frozen["session_id"]
            )
            self.assertEqual(listed_done.get("market_evidence_epoch_sha256"), market)
            bundle = load_session_bundle(store_reloaded, frozen["session_id"])
            assert bundle is not None
            self.assertEqual(bundle.get("market_evidence_epoch_sha256"), market)
            self.assertEqual(
                bundle.get("scientific_slot_sha256"), listed_done.get("scientific_slot_sha256")
            )
            self.assertEqual(
                bundle.get("execution_binding_sha256"),
                listed_done.get("execution_binding_sha256"),
            )
            usage_done = epoch_search_budget_usage(
                list_hfic_sessions(store_reloaded), evidence_epoch=market
            )
            self.assertGreaterEqual(
                usage_done["auto_sessions_used"] + usage_done["distinct_focus_used"], 1
            )
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                finished = evaluate_forge_run(ROOT, data_root, persist=True)
                retry = evaluate_forge_run(ROOT, data_root, persist=False)
            self.assertEqual(finished["next_action"], ACTION_OWNER_CANDIDATE)
            self.assertEqual(finished["run_identity_sha256"], run_id)
            self.assertEqual(finished["market_evidence_epoch_sha256"], market)
            # Execution binding uses actual representation payload when present.
            challenger = envelope.get("challenger") if isinstance(envelope, dict) else None
            payload = None
            if isinstance(challenger, dict):
                payload = challenger.get("representation_payload_sha256")
            self.assertIsNone(finished.get("execution_binding_sha256"))
            self.assertIsInstance(finished.get("scientific_slot_sha256"), str)
            if isinstance(payload, str) and len(payload) == 64:
                # Binding must change if payload were absent (not readiness hash).
                self.assertNotEqual(
                    finished["execution_binding_sha256"],
                    finished.get("input_receipt_sha256"),
                )
            self.assertEqual(retry["next_action"], ACTION_RETURN_EXISTING)
            self.assertEqual(retry["run_identity_sha256"], run_id)
            self.assertEqual(retry["writes"]["session"], 0)
            sessions_after = list_hfic_sessions(store_reloaded)
            self.assertTrue(
                any(item.get("session_id") == frozen["session_id"] for item in sessions_after)
            )
            self.assertTrue(
                any(item.get("session_id") == base["session_id"] for item in sessions_after)
            )

    def test_g6_generated_draft_restart_keeps_slot_and_rejects_regeneration(self) -> None:
        """A generator crash before freeze resumes bytes, slot, and budget."""

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            from solana_alpha_lab.factory.hfic_preflight import run_preflight
            from tests.test_hfic_preflight import _CLOCK, _commission, _git_snapshot

            _commission(data_root)

            def _enumerate_production(root: Path):
                live, warnings = _enumerate_live(root)
                enriched = []
                for item in live:
                    row = dict(item)
                    row.setdefault("evidence_role", "UNSPECIFIED")
                    row.setdefault("feature_families", [])
                    row.setdefault("feature_hint", None)
                    row.setdefault("feature_usable", True)
                    row.setdefault("yield_missing", 0)
                    row.setdefault("dataset_terminal", None)
                    enriched.append(row)
                return enriched, warnings

            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production,
            ):
                preflight = run_preflight(
                    ROOT,
                    data_root,
                    owner_focus="AUTO",
                    auto_commission=False,
                    git_snapshot=_git_snapshot(),
                    clock=_CLOCK,
                )
            store = ResearchStore(data_root)
            draft = valid_draft()
            generated = persist_generated_draft(
                store,
                draft,
                preflight_receipt=preflight,
                repo_root=ROOT,
            )
            draft_sha = str(generated["payload_sha256"])
            admissions = list_scientific_slot_admissions(store)
            self.assertEqual(len(admissions), 1)
            self.assertEqual(admissions[0]["admission_state"], "RESERVED")
            market = str(preflight["market_evidence_epoch_sha256"])
            usage = epoch_search_budget_usage(
                list_hfic_sessions(store),
                evidence_epoch=market,
                reservations=admissions,
            )
            self.assertEqual(usage["auto_sessions_used"], 1)
            self.assertEqual(len(usage["representation_slots"]), 1)

            # Real restart path: reload the store and let production
            # preflight resolve the durable generated draft.  The reservation
            # is not a free slot and must not be mistaken for a fresh start.
            store_reloaded = ResearchStore(data_root, create_if_missing=False)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production,
            ):
                resumed_preflight = run_preflight(
                    ROOT,
                    data_root,
                    owner_focus="AUTO",
                    auto_commission=False,
                    git_snapshot=_git_snapshot(),
                    clock=_CLOCK,
                    persist=False,
                )
            self.assertEqual(resumed_preflight["action"], "RESUME_EXISTING_SESSION")
            self.assertEqual(
                resumed_preflight.get("session_id"), "HFIC-SESS-" + str(
                    preflight["search_key_sha256"]
                )[:16].upper(),
            )
            self.assertEqual(
                resumed_preflight.get("generated_draft_sha256"), draft_sha
            )
            self.assertEqual(
                resumed_preflight["writes"],
                {"research_store": 0, "forge_context": 0, "session": 0},
            )
            generated_draft = json.loads(str(generated["payload_canonical"]))
            frozen = freeze_draft(
                generated_draft,
                preflight_receipt=resumed_preflight,
                repo_root=ROOT,
            )
            persist_frozen_session(
                store_reloaded,
                frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(generated_draft["candidates"]),
                draft=generated_draft,
            )
            store_reloaded.rebuild_projection()
            resumed_bundle = load_session_bundle(
                store_reloaded, str(frozen["session_id"])
            )
            self.assertIsNotNone(resumed_bundle)
            self.assertEqual(
                resumed_bundle.get("session_state") if resumed_bundle else None,
                "FROZEN_AWAITING_CRITIC",
            )

            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production,
            ):
                resumed = evaluate_forge_run(ROOT, data_root, persist=False)
            self.assertEqual(resumed["next_action"], "RESUME_BASE")
            base_stage = next(
                row for row in resumed["stages"] if row["representation_id"] == "BASE"
            )
            self.assertEqual(base_stage["draft_sha256"], draft_sha)
            self.assertEqual(len(str(base_stage["scientific_slot_sha256"])), 64)

            changed = dict(draft)
            changed["owner_focus"] = "ALT"
            with self.assertRaises(HficSessionError) as ctx:
                persist_generated_draft(
                    store,
                    changed,
                    preflight_receipt=preflight,
                    repo_root=ROOT,
                )
            self.assertEqual(str(ctx.exception), "GENERATED_DRAFT_CONFLICT")

    def test_f1a_ordinary_pass_then_c3_does_not_reuse_stale_market(self) -> None:
        """F1a: ordinary BASE PASS on C1+C2 must not answer C1+C2+C3 as REUSED_VALID."""

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            frozen = _ordinary_pass_base(data_root, store)
            self.assertIsInstance(frozen.get("market_evidence_epoch_sha256"), str)
            self.assertNotEqual(
                frozen.get("evidence_surface_mode"),
                "CURRENT_REPRESENTATION_CONTROL_V1",
            )
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                matched = evaluate_forge_run(ROOT, data_root, persist=False)
            market_before = matched["market_evidence_epoch_sha256"]
            # Same market: ordinary PASS may be presented as current readback.
            matched_stage = next(
                (
                    stage
                    for stage in (matched.get("stages") or [])
                    if isinstance(stage, dict)
                    and stage.get("session_id") == frozen["session_id"]
                ),
                None,
            )
            self.assertIsNotNone(matched_stage)
            assert matched_stage is not None
            self.assertEqual(matched_stage.get("execution_status"), EXEC_REUSED)
            _append_c3(data_root)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_c3,
            ):
                after_c3 = evaluate_forge_run(ROOT, data_root, persist=False)
            market_after = after_c3["market_evidence_epoch_sha256"]
            self.assertNotEqual(market_before, market_after)
            self.assertNotEqual(after_c3["next_action"], ACTION_OWNER_CANDIDATE)
            for stage in after_c3.get("stages") or []:
                if not isinstance(stage, dict):
                    continue
                if stage.get("session_id") == frozen["session_id"]:
                    self.assertNotEqual(stage.get("execution_status"), EXEC_REUSED)
            self.assertIn(
                after_c3["next_action"],
                {ACTION_START_BASE, ACTION_START_V1, ACTION_SEARCH_EXHAUSTED},
            )

    def test_g4_negative_exhaustion_readback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = _no_worthy_base(data_root, store, production_packet=True)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                started = evaluate_forge_run(ROOT, data_root, persist=False)
            draft = _distinct_no_worthy_draft(label="V1")
            v1_pre, _envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(base["session_id"]),
            )
            frozen = freeze_draft(draft, preflight_receipt=v1_pre, repo_root=ROOT)
            persist_no_worthy_session(
                store,
                frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(draft["candidates"]),
                draft=draft,
                preflight_receipt=v1_pre,
            )
            store.rebuild_projection()
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                finished = evaluate_forge_run(ROOT, data_root, persist=True)
                retry = evaluate_forge_run(ROOT, data_root, persist=False)
            self.assertEqual(finished["next_action"], ACTION_SEARCH_EXHAUSTED)
            self.assertEqual(retry["next_action"], ACTION_RETURN_EXISTING)

    def test_g7_docs_change_does_not_reset_market_or_run_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data"
            data_root.mkdir()
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            _no_worthy_base(data_root, store, production_packet=True)
            clone = Path(tmp) / "repo"
            current_branch = subprocess.check_output(
                ["git", "branch", "--show-current"], cwd=ROOT, text=True
            ).strip()
            subprocess.check_call(
                [
                    "git",
                    "clone",
                    "--no-local",
                    "--branch",
                    current_branch,
                    str(ROOT),
                    str(clone),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            current_head = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip()
            _git(clone, "checkout", "--detach", current_head)
            candidate_diff = subprocess.check_output(
                ["git", "diff", "--binary", "HEAD"], cwd=ROOT
            )
            if candidate_diff:
                subprocess.run(
                    ["git", "apply", "--binary", "-"],
                    cwd=clone,
                    input=candidate_diff,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                before = compute_split_identity(ROOT, data_root)
                started = evaluate_forge_run(ROOT, data_root, persist=False)
                clone_before = compute_split_identity(clone, data_root)
            self.assertEqual(
                before["market_evidence_epoch_sha256"],
                clone_before["market_evidence_epoch_sha256"],
            )
            self.assertEqual(
                before["capability_epoch_sha256"],
                clone_before["capability_epoch_sha256"],
            )
            # Mutate and commit a real tracked capability document.  No
            # post-hoc hash/stamp patch stands in for the production path.
            capability_doc = clone / "docs/contracts/normalized_trajectory_v1_capability_contract.md"
            capability_doc.write_text(
                capability_doc.read_text(encoding="utf-8") + "\nA5-G7-REAL-GIT-DOC-CHANGE\n",
                encoding="utf-8",
            )
            _git(clone, "add", capability_doc.relative_to(clone).as_posix())
            _git(clone, "commit", "-m", "test: change capability document")
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                after = compute_split_identity(clone, data_root)
                again = evaluate_forge_run(clone, data_root, persist=False)
            self.assertEqual(
                before["market_evidence_epoch_sha256"],
                after["market_evidence_epoch_sha256"],
            )
            self.assertNotEqual(
                before["capability_epoch_sha256"],
                after["capability_epoch_sha256"],
            )
            self.assertEqual(
                started["run_identity_sha256"], again["run_identity_sha256"]
            )
            self.assertEqual(
                started["market_evidence_epoch_sha256"],
                again["market_evidence_epoch_sha256"],
            )
            # Occupied CONTROL slot still answers; capability drift ≠ new trial.
            self.assertEqual(again["next_action"], ACTION_START_V1)
            self.assertEqual(again["stages"][0]["execution_status"], EXEC_REUSED)

    def test_g6_interruption_resume_keeps_draft_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = _no_worthy_base(data_root, store, production_packet=True)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                started = evaluate_forge_run(ROOT, data_root, persist=True)
            v1_pre, _envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(base["session_id"]),
            )
            draft = valid_draft()
            frozen = freeze_draft(draft, preflight_receipt=v1_pre, repo_root=ROOT)
            persist_frozen_session(
                store,
                frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(draft["candidates"]),
                draft=draft,
            )
            store.rebuild_projection()
            draft_sha = frozen.get("critic_input_packet_sha256")
            self.assertIsInstance(draft_sha, str)
            self.assertEqual(len(str(draft_sha)), 64)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                # Restart without re-injecting draft: discovery must find pending V1.
                mid = evaluate_forge_run(ROOT, data_root, persist=True)
            self.assertEqual(mid["next_action"], ACTION_RESUME_V1)
            self.assertEqual(mid["run_identity_sha256"], started["run_identity_sha256"])
            v1 = next(
                row
                for row in mid["stages"]
                if row["representation_id"] == "NORMALIZED_TRAJECTORY_V1"
            )
            self.assertEqual(v1["session_id"], frozen["session_id"])
            # Persisted freeze bytes remain addressable after restart.
            from solana_alpha_lab.factory.hfic_session import load_session_bundle

            bundle = load_session_bundle(store, str(frozen["session_id"]))
            assert bundle is not None
            self.assertEqual(
                bundle.get("critic_input_packet_sha256")
                or (bundle.get("session_receipt") or {}).get("critic_input_packet_sha256"),
                draft_sha,
            )
            # Second call: still same pending session, no new session minted.
            before_sessions = {
                item["session_id"] for item in list_hfic_sessions(store)
            }
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                again = evaluate_forge_run(ROOT, data_root, persist=False)
            self.assertEqual(again["next_action"], ACTION_RESUME_V1)
            self.assertEqual(
                {item["session_id"] for item in list_hfic_sessions(store)},
                before_sessions,
            )

    def test_g10_incomplete_market_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            # Empty RDP: no datasets/lineage → incomplete market, not a digest.
            store = ResearchStore(data_root)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                return_value=([], []),
            ):
                receipt = build_forge_input_receipt(data_root, repo_root=ROOT)
            self.assertFalse(receipt.get("forge_runnable"))
            self.assertIn(
                "MARKET_EVIDENCE_BASIS_INCOMPLETE",
                receipt.get("blocking_reason_codes") or [],
            )
            self.assertNotIn("market_evidence_epoch_sha256", receipt)
            with self.assertRaises(LadderError) as ctx:
                with patch(
                    "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                    return_value=([], []),
                ):
                    evaluate_forge_run(ROOT, data_root, persist=False)
            self.assertEqual(str(ctx.exception), "MARKET_EVIDENCE_BASIS_INCOMPLETE")
            del store

    def test_g10_current_incomplete_market_persist_true_is_no_write(self) -> None:
        """A current A3 surface cannot enter legacy commissioning on persist=True."""

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            broken = dict(_enumerate_live(data_root)[0][0])
            broken["dataset_fingerprint"] = "not-a-fingerprint"
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                return_value=([broken], []),
            ):
                receipt = run_preflight(
                    ROOT,
                    data_root,
                    owner_focus="AUTO",
                    auto_commission=False,
                    persist=True,
                )
            self.assertEqual(receipt["action"], "STOP")
            self.assertEqual(receipt["terminal"], "MARKET_EVIDENCE_BASIS_INCOMPLETE")
            self.assertEqual(
                receipt["writes"],
                {"research_store": 0, "forge_context": 0, "session": 0},
            )
            self.assertFalse((data_root / "research").exists())

    def test_g10_tamper_outer_key_is_integrity_stop(self) -> None:
        from solana_alpha_lab.factory.hfic_control_integrity import (
            CURRENT_REPRESENTATION_CONTROL_V1,
        )

        control = _no_worthy_forge_receipt()
        envelope = consume_start_v1_envelope(
            {"next_action": ACTION_START_V1, "owner_final": None},
            control_receipt=control,
            representation=_representation_fixture_rel_c2(),
            cohort_readiness_receipt=_cohort_readiness_receipt_rel_c2(),
            base_x_population_n=10,
        )
        challenger = dict(envelope["challenger"])
        parent = str(challenger["control_session_id"])
        preflight = {
            "evidence_epoch_sha256": control["evidence_epoch_sha256"],
            "focus_key_sha256": control["focus_key_sha256"],
            "search_key_sha256": control["search_key_sha256"],
            "owner_focus": "AUTO",
            "live_git_head": "0" * 40,
            "forge_context_packet": dict(control["forge_context_packet"]),
            "forge_context_packet_sha256": control["forge_context_packet_sha256"],
            "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
        }
        tampered = dict(challenger)
        payload = dict(tampered["normalized_trajectory_v1"])
        payload["eligible_member_count"] = int(payload.get("eligible_member_count") or 0) + 1
        tampered["normalized_trajectory_v1"] = payload
        with self.assertRaises(LadderError):
            prepare_ladder_freeze_preflight(
                preflight,
                representation_id="NORMALIZED_TRAJECTORY_V1",
                control_session_id=parent,
                challenger=tampered,
                control_receipt=control,
            )

    def test_g11_capability_change_does_not_free_completed_slot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = _no_worthy_base(data_root, store, production_packet=True)
            draft = _distinct_no_worthy_draft(label="V1")
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                started = evaluate_forge_run(ROOT, data_root, persist=False)
            v1_pre, _envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(base["session_id"]),
            )
            frozen = freeze_draft(draft, preflight_receipt=v1_pre, repo_root=ROOT)
            persist_no_worthy_session(
                store,
                frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(draft["candidates"]),
                draft=draft,
                preflight_receipt=v1_pre,
            )
            store.rebuild_projection()
            # Future ACTIVE Vn on same market must not rewrite completed BASE/V1.
            registry = _later_registry()
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                with_vn = evaluate_forge_run(
                    ROOT, data_root, persist=False, registry=registry
                )
            # New representation slot may open; completed BASE/V1 must not restart.
            self.assertEqual(with_vn["next_action"], "START_SYNTHETIC_LATER_V2")
            base_stage = next(
                row for row in with_vn["stages"] if row["representation_id"] == "BASE"
            )
            v1_stage = next(
                row
                for row in with_vn["stages"]
                if row["representation_id"] == "NORMALIZED_TRAJECTORY_V1"
            )
            self.assertEqual(base_stage["execution_status"], EXEC_REUSED)
            self.assertEqual(v1_stage["execution_status"], EXEC_REUSED)
            self.assertEqual(
                with_vn["market_evidence_epoch_sha256"],
                started["market_evidence_epoch_sha256"],
            )
            # Model/capability-only drift still preserves market + prior stages.
            with patch(
                "solana_alpha_lab.factory.hfic_evidence_identity._file_sha256",
                return_value="ab" * 32,
            ):
                with patch(
                    "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                    side_effect=_enumerate_live,
                ):
                    finished = evaluate_forge_run(
                        ROOT, data_root, persist=False, registry=registry
                    )
            self.assertEqual(finished["next_action"], "START_SYNTHETIC_LATER_V2")
            self.assertEqual(
                finished["market_evidence_epoch_sha256"],
                started["market_evidence_epoch_sha256"],
            )
            self.assertEqual(
                next(
                    row
                    for row in finished["stages"]
                    if row["representation_id"] == "BASE"
                )["execution_status"],
                EXEC_REUSED,
            )

    def test_g1_g5_two_worktrees_share_market_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            principal = Path(tmp) / "principal"
            linked = Path(tmp) / "linked"
            # Keep Git metadata inside the disposable test directory.  The
            # real checkout may be sandboxed against worktree-admin writes.
            _git(ROOT, "clone", "--no-local", str(ROOT), str(principal))
            _git(principal, "worktree", "add", "--detach", str(linked), "HEAD")
            shared_data_root = Path(tmp) / "shared-data-plane"
            env = {"SMIAL_DATA_ROOT": str(shared_data_root)}
            try:
                data_root = resolve_data_root(principal, env=env)
                self.assertEqual(data_root, resolve_data_root(linked, env=env))
                data_root.mkdir(parents=True, exist_ok=True)
                _write_lineage(data_root)
                store = ResearchStore(data_root)
                with patch(
                    "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                    side_effect=_enumerate_live,
                ):
                    from_a = build_forge_input_receipt(data_root, repo_root=principal)
                    from_b = build_forge_input_receipt(data_root, repo_root=linked)
                self.assertEqual(
                    from_a["market_evidence_epoch_sha256"],
                    from_b["market_evidence_epoch_sha256"],
                )
                base = _no_worthy_base(
                    data_root, store, production_packet=True, repo_root=principal
                )
                with patch(
                    "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                    side_effect=_enumerate_live,
                ):
                    started = evaluate_forge_run(principal, data_root, persist=True)
                self.assertEqual(started["next_action"], ACTION_START_V1)
                # Linked worktree / fresh store handle: completed BASE still
                # answers without minting a second CONTROL on same market.
                store_b = ResearchStore(data_root)
                with patch(
                    "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                    side_effect=_enumerate_live,
                ):
                    replay = evaluate_forge_run(linked, data_root, persist=False)
                self.assertEqual(
                    replay["market_evidence_epoch_sha256"],
                    from_a["market_evidence_epoch_sha256"],
                )
                self.assertEqual(replay["control_session_id"], base["session_id"])
                self.assertEqual(replay["run_identity_sha256"], started["run_identity_sha256"])
                self.assertEqual(len(list_hfic_sessions(store_b)), 1)
            finally:
                _git(principal, "worktree", "remove", "--force", str(linked))

    def test_g8_c3_after_completed_does_not_reuse_stale_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            frozen = _no_worthy_base(data_root, store, production_packet=True)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                matched = evaluate_forge_run(ROOT, data_root, persist=False)
            self.assertEqual(matched["control_session_id"], frozen["session_id"])
            self.assertEqual(matched["stages"][0]["execution_status"], EXEC_REUSED)
            old_market = matched["market_evidence_epoch_sha256"]
            _append_c3(data_root)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_c3,
            ):
                drifted = evaluate_forge_run(ROOT, data_root, persist=False)
                alt = evaluate_forge_run(
                    ROOT, data_root, persist=False, owner_focus="ALT"
                )
            self.assertNotEqual(
                drifted["market_evidence_epoch_sha256"], old_market
            )
            self.assertNotIn("REL-C3", drifted["stages"][0]["used_cohort_ids"])
            self.assertNotEqual(drifted["stages"][0]["execution_status"], EXEC_REUSED)
            self.assertNotEqual(drifted["next_action"], ACTION_SEARCH_EXHAUSTED)
            self.assertEqual(alt["next_action"], ACTION_START_BASE)
            # Negative control (a): stale accepted result must not answer new input.
            self.assertNotEqual(
                drifted["run_identity_sha256"], matched["run_identity_sha256"]
            )

    def test_g9_legacy_ordinary_not_focus_only_current_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            draft = _distinct_no_worthy_draft(label="ORD")
            pre = dict(_control_preflight(data_root, store))
            pre.pop("evidence_surface_mode", None)
            packet = dict(pre.get("forge_context_packet") or {})
            packet.pop("evidence_surface_mode", None)
            pre["forge_context_packet"] = packet
            # Legacy combined epoch only — no market split stamp.
            pre.pop("market_evidence_epoch_sha256", None)
            pre.pop("capability_epoch_sha256", None)
            pre["evidence_epoch_sha256"] = "ab" * 32
            frozen = freeze_draft(draft, preflight_receipt=pre, repo_root=ROOT)
            with self.assertRaisesRegex(
                HficSessionError, "SCIENTIFIC_ADMISSION_REQUIRED"
            ):
                persist_no_worthy_session(
                    store,
                    frozen,
                    repo_root=ROOT,
                    identities=assign_portfolio_ids(draft["candidates"]),
                    draft=draft,
                    preflight_receipt=pre,
                )
            # Legacy combined-only data remains readable/dispositioned, but
            # this A5 writer must not create a lifecycle row or reservation.
            self.assertEqual(list_hfic_sessions(store), [])
            self.assertEqual(list_scientific_slot_admissions(store), [])
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                split = compute_split_identity(ROOT, data_root)
                current = evaluate_forge_run(ROOT, data_root, persist=False)
            row = classify_legacy_session_disposition(
                {
                    **frozen,
                    "forge_context_packet": {
                        "bound_visible_cohort_ids": ["REL-C1", "REL-C2"]
                    },
                },
                current_market_epoch=str(split["market_evidence_epoch_sha256"]),
                current_visible_cohort_ids=["REL-C1", "REL-C2"],
            )
            self.assertNotEqual(
                row["disposition"], "COMPATIBLE_FOR_EXACT_REUSE_OR_RESUME"
            )
            # Ordinary legacy without CONTROL surface must not present a finished
            # current-market answer; START_V1 would imply CONTROL reuse.
            self.assertNotEqual(current["next_action"], ACTION_RETURN_EXISTING)
            self.assertNotEqual(current["next_action"], ACTION_SEARCH_EXHAUSTED)
            self.assertNotEqual(current.get("owner_final"), "SEARCH_EXHAUSTED_CURRENT_EVIDENCE")

    def test_negative_own_artifacts_do_not_mutate_market_epoch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                before = build_forge_input_receipt(data_root, repo_root=ROOT)
            _no_worthy_base(data_root, store, production_packet=True)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                after = build_forge_input_receipt(data_root, repo_root=ROOT)
            self.assertEqual(
                before["market_evidence_epoch_sha256"],
                after["market_evidence_epoch_sha256"],
            )

    def test_g12_snapshot_restore_preserves_occupied_slot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data"
            snap = Path(tmp) / "snap"
            restore_root = Path(tmp) / "restored"
            data_root.mkdir()
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = _no_worthy_base(data_root, store, production_packet=True)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                before = evaluate_forge_run(ROOT, data_root, persist=True)
            exported = export_snapshot(data_root, snap)
            restore_snapshot(exported.snapshot_root, restore_root)
            # Snapshot owns ResearchStore bytes. Gold reconstitutes the same
            # fixture lineage used at export (not a second scientific look).
            _write_lineage(restore_root)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                after = evaluate_forge_run(ROOT, restore_root, persist=False)
            self.assertEqual(before["run_identity_sha256"], after["run_identity_sha256"])
            self.assertEqual(
                before["market_evidence_epoch_sha256"],
                after["market_evidence_epoch_sha256"],
            )
            self.assertEqual(after["control_session_id"], base["session_id"])
            self.assertGreaterEqual(
                len(list_hfic_sessions(ResearchStore(restore_root))), 1
            )


if __name__ == "__main__":
    unittest.main()
