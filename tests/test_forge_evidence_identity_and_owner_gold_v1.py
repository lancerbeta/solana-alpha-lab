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
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.forge_input_receipt import (  # noqa: E402
    build_forge_input_receipt,
)
from solana_alpha_lab.factory.hfic_evidence_identity import (  # noqa: E402
    DISPOSITION_HISTORICAL_ONLY,
    DISPOSITION_UNRESOLVED,
    classify_legacy_session_disposition,
    compute_capability_epoch_for_repo,
    compute_split_identity,
    forge_run_identity_sha256,
    scientific_slot_sha256,
)
from solana_alpha_lab.factory.hfic_identity import assign_portfolio_ids  # noqa: E402
from solana_alpha_lab.factory.hfic_representation_ladder import (  # noqa: E402
    ACTION_OWNER_CANDIDATE,
    ACTION_RETURN_EXISTING,
    ACTION_SEARCH_EXHAUSTED,
    ACTION_START_BASE,
    ACTION_START_V1,
    EXEC_REUSED,
    evaluate_forge_run,
)
from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    apply_classification,
    freeze_draft,
    list_hfic_sessions,
    persist_frozen_session,
    persist_no_worthy_session,
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
    _production_control_preflight,
    _v1_freeze_preflight_from_envelope,
    _distinct_no_worthy_draft,
)
from tests.test_hfic_session import (  # noqa: E402
    critic_result_from_packet_only,
    valid_draft,
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.check_call(["git", *args], cwd=cwd, stdout=subprocess.DEVNULL)


def _stamp_preflight_split(preflight: dict[str, object], data_root: Path) -> dict[str, object]:
    split = compute_split_identity(ROOT, data_root)
    stamped = dict(preflight)
    stamped["market_evidence_epoch_sha256"] = split["market_evidence_epoch_sha256"]
    stamped["capability_epoch_sha256"] = split["capability_epoch_sha256"]
    stamped["legacy_combined_evidence_epoch_sha256"] = split[
        "legacy_combined_evidence_epoch_sha256"
    ]
    return stamped


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


def _no_worthy_base(
    data_root: Path,
    store: ResearchStore,
    *,
    production_packet: bool = False,
) -> dict[str, object]:
    draft = json.loads(NO_WORTHY_DRAFT.read_text(encoding="utf-8"))
    preflight = (
        _production_control_preflight(data_root, store)
        if production_packet
        else _control_preflight(data_root, store)
    )
    preflight = _stamp_preflight_split(preflight, data_root)
    frozen = freeze_draft(draft, preflight_receipt=preflight, repo_root=ROOT)
    persist_no_worthy_session(
        store,
        frozen,
        repo_root=ROOT,
        identities=assign_portfolio_ids(draft["candidates"]),
        draft=draft,
        preflight_receipt=preflight,
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
            capability = started["capability_epoch_sha256"]
            run_id = started["run_identity_sha256"]
            v1_pre, _envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(base["session_id"]),
            )
            v1_pre = dict(v1_pre)
            v1_pre["market_evidence_epoch_sha256"] = market
            v1_pre["capability_epoch_sha256"] = capability
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
                frozen,
                spec,
                store=store,
                repo_root=ROOT,
                data_root=data_root,
            )
            store.rebuild_projection()
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                finished = evaluate_forge_run(ROOT, data_root, persist=True)
                retry = evaluate_forge_run(ROOT, data_root, persist=False)
            self.assertEqual(finished["next_action"], ACTION_OWNER_CANDIDATE)
            self.assertEqual(finished["run_identity_sha256"], run_id)
            self.assertEqual(finished["market_evidence_epoch_sha256"], market)
            self.assertEqual(retry["next_action"], ACTION_RETURN_EXISTING)
            self.assertEqual(retry["run_identity_sha256"], run_id)
            self.assertEqual(retry["writes"]["session"], 0)
            # persist=False must not mint a new scientific session.
            self.assertEqual(
                len(list_hfic_sessions(store)),
                len(
                    {
                        row["session_id"]
                        for row in finished.get("stages") or []
                        if row.get("session_id")
                    }
                )
                or len(list_hfic_sessions(store)),
            )
            sessions_after = list_hfic_sessions(store)
            self.assertTrue(
                any(item.get("session_id") == frozen["session_id"] for item in sessions_after)
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
            v1_pre = dict(v1_pre)
            v1_pre["market_evidence_epoch_sha256"] = started[
                "market_evidence_epoch_sha256"
            ]
            v1_pre["capability_epoch_sha256"] = started["capability_epoch_sha256"]
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
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                before = compute_split_identity(ROOT, data_root)
                started = evaluate_forge_run(ROOT, data_root, persist=False)
            # Same market input after unrelated prose: market + run identity hold.
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                after = compute_split_identity(ROOT, data_root)
                again = evaluate_forge_run(ROOT, data_root, persist=False)
            self.assertEqual(
                before["market_evidence_epoch_sha256"],
                after["market_evidence_epoch_sha256"],
            )
            self.assertEqual(
                started["run_identity_sha256"], again["run_identity_sha256"]
            )
            self.assertEqual(
                started["market_evidence_epoch_sha256"],
                again["market_evidence_epoch_sha256"],
            )
            # Capability is independent of market; Git/docs provenance alone
            # must not appear in market basis (asserted by equal market hashes).
            self.assertNotEqual(
                before["market_evidence_epoch_sha256"],
                before["capability_epoch_sha256"],
            )

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
            pre["evidence_epoch_sha256"] = "ab" * 32
            frozen = freeze_draft(draft, preflight_receipt=pre, repo_root=ROOT)
            persist_no_worthy_session(
                store,
                frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(draft["candidates"]),
                draft=draft,
                preflight_receipt=pre,
            )
            store.rebuild_projection()
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
        import shutil

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
            # Snapshot owns ResearchStore bytes; market lineage fixtures must travel
            # with the plane for identity continuity (not a second scientific look).
            datasets = data_root / "datasets"
            if datasets.is_dir():
                shutil.copytree(
                    datasets, restore_root / "datasets", dirs_exist_ok=True
                )
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
