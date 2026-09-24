"""A5 owner gold: market/capability identity, reuse/resume/budget, sequential G1–G12.

Synthetic sources and generator/Critic replies only. Production import/preflight/
packet/ladder/freeze/classifier/finalize/discovery/persistence/readout bindings.
Does not execute Prompt A/B/C, real Independent Critic, or scientific market Forge.
"""

from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.data_root import resolve_data_root  # noqa: E402
from solana_alpha_lab.factory.forge_input_receipt import (  # noqa: E402
    OWNER_CLASS_OBSERVABILITY_BLOCKED,
    build_forge_input_receipt,
)
from solana_alpha_lab.factory.hfic_evidence_identity import (  # noqa: E402
    DISPOSITION_HISTORICAL_ONLY,
    DISPOSITION_UNRESOLVED,
    classify_legacy_session_disposition,
    compute_capability_epoch_for_repo,
    compute_market_epoch_for_data_root,
    compute_split_identity,
    build_market_evidence_basis,
    execution_binding_sha256,
    forge_run_identity_sha256,
    market_evidence_epoch_sha256,
    resolve_scientific_admission,
    session_scientific_slot_sha256,
    scientific_slot_sha256,
)
from solana_alpha_lab.factory.hfic_identity import assign_portfolio_ids  # noqa: E402
from solana_alpha_lab.factory.hfic_representation_ladder import (  # noqa: E402
    ACTION_OBSERVABILITY_BLOCKED,
    ACTION_OWNER_CANDIDATE,
    ACTION_RESUME_BASE,
    ACTION_RESUME_V1,
    ACTION_RETURN_EXISTING,
    ACTION_SEARCH_EXHAUSTED,
    ACTION_START_BASE,
    ACTION_START_V1,
    EXEC_PROVENANCE_CONFLICT,
    EXEC_REUSED,
    LadderError,
    consume_start_v1_envelope,
    evaluate_forge_run,
    prepare_ladder_freeze_preflight,
)
from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    build_offline_commission_packet,
    epoch_search_budget_usage,
    enumerate_rdp_datasets as _enumerate_repository_datasets,
    run_preflight,
)
from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    HficSessionError,
    apply_classification,
    canonical_preflight_receipt_sha256,
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
from solana_alpha_lab.factory.live_cohort_discovery_release import (  # noqa: E402
    import_live_cohort,
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
    _later_registry,
    _representation_fixture_rel_c2,
    _submission_for_frozen,
    _v1_freeze_preflight_from_envelope,
)
from tests.test_hfic_session import (  # noqa: E402
    critic_result_from_packet_only,
)


def _fresh_v12_draft(preflight: dict | None = None) -> dict:
    """Generator reply for a fresh HFIC-V1.2 START_NEW_SESSION.

    Labels are prefixed so a second current-prompt session does not collide
    with the no-worthy V1.2 control cards in the same store. Historical
    packet 1.1 stays on ``valid_draft()``.
    """

    draft = json.loads(
        (ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text(
            encoding="utf-8"
        )
    )
    renamed: dict[str, str] = {}
    for card in draft.get("candidates") or []:
        if not isinstance(card, dict):
            continue
        claim = str(card.get("claim") or "")
        card["claim"] = f"Selected-session variant. {claim}".strip()
        old = str(card.get("label") or "")
        new = f"SEL-{old}" if old else old
        card["label"] = new
        renamed[old] = new
    for key in (
        "selected_candidate_ref",
        "runner_up_candidate_ref",
        "strongest_rejected_alternative",
    ):
        current = draft.get(key)
        if isinstance(current, str) and current in renamed:
            draft[key] = renamed[current]
    if preflight is None:
        return draft
    from tests.test_hfic_cli import bind_draft

    return bind_draft(draft, preflight)
from tests.test_normalized_trajectory_v1_execution_closure_v1 import (  # noqa: E402
    _no_worthy_forge_receipt,
)
from tests.test_live_corpus_manifest_contract_repair_v1 import (  # noqa: E402
    _seal_week,
)


def _enumerate_c3(_data_root: Path):
    live = _enumerate_production_fixture(_data_root)[0]
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


def _commission_fixture(repo_root: Path, data_root: Path) -> None:
    script_path = repo_root / "scripts/hypothesis_fast_lane.py"
    spec = importlib.util.spec_from_file_location(
        "a5_owner_gold_fast_lane_fixture", script_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("FAST_LANE_NOT_COMMISSIONABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    packet_path = data_root / "offline_commission.json"
    packet_path.write_text(
        json.dumps(build_offline_commission_packet(repo_root)), encoding="utf-8"
    )
    module.execute_commission_offline(repo_root, data_root, packet_path)


def _with_control_projection_rows(datasets: list[dict[str, object]]):
    from solana_alpha_lab.factory.scientific_eligibility_projection import (
        X_FIELD_ID,
        X_POINT_ID,
    )

    enriched = []
    anchor = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
    anchor_text = anchor.isoformat().replace("+00:00", "Z")
    census_rows = []
    observation_rows = []
    for index in range(10):
        mint = f"A5-C1-C2-{index:02d}"
        census_rows.append(
            {
                "mint": mint,
                "candidate_state": "X_ELIGIBLE",
                "denominator_state": "observed",
                "authoritative_anchor": anchor_text,
            }
        )
        observation_rows.append(
            {
                "mint": mint,
                "point_id": X_POINT_ID,
                "field_id": X_FIELD_ID,
                "state": "OBSERVED",
                "first_reliable_available_at": (
                    anchor + timedelta(seconds=300)
                ).isoformat().replace("+00:00", "Z"),
            }
        )
    for item in datasets:
        row = dict(item)
        row.setdefault("evidence_role", "UNSPECIFIED")
        row.setdefault("feature_families", [])
        row.setdefault("feature_hint", None)
        row.setdefault("feature_usable", True)
        row.setdefault("yield_missing", 0)
        row.setdefault("dataset_terminal", None)
        # The A4 CONTROL readiness resolver needs actual X300 eligibility
        # rows, not a hand-entered yield count. Keep the fixture deterministic
        # and tiny; production projection computes the ten-member result.
        row.setdefault("census_rows", census_rows)
        row.setdefault("observation_rows", observation_rows)
        enriched.append(row)
    return enriched


def _enumerate_production_fixture(root: Path):
    live, warnings = _enumerate_live(root)
    return _with_control_projection_rows(live), warnings


def _enumerate_imported_control_fixture(root: Path):
    datasets, warnings = _enumerate_repository_datasets(root)
    return _with_control_projection_rows(list(datasets)), warnings


def _run_production_preflight(
    data_root: Path,
    *,
    repo_root: Path = ROOT,
    evidence_surface_mode: str | None = None,
    enumerator=_enumerate_production_fixture,
    model_provenance_sha256: str | None = None,
) -> dict[str, object]:
    """Run production preflight over synthetic C1/C2 evidence."""

    from solana_alpha_lab.factory.document_runner import repository_git_snapshot
    from tests.test_hfic_preflight import _CLOCK

    _commission_fixture(repo_root, data_root)
    snapshot = repository_git_snapshot(repo_root)
    with patch(
        "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
        side_effect=enumerator,
    ):
        return run_preflight(
            repo_root,
            data_root,
            owner_focus="AUTO",
            auto_commission=False,
            git_snapshot={
                "head_sha": snapshot.head_sha,
                "composite_sha256": snapshot.composite_sha256,
            },
            clock=_CLOCK,
            evidence_surface_mode=evidence_surface_mode,
            model_provenance_sha256=model_provenance_sha256,
        )


def _ordinary_stamped_preflight(
    data_root: Path,
    _store: ResearchStore,
    *,
    repo_root: Path = ROOT,
    model_provenance_sha256: str | None = None,
) -> dict[str, object]:
    """Ordinary non-CONTROL production entry over synthetic C1/C2 evidence."""

    return _run_production_preflight(
        data_root,
        repo_root=repo_root,
        model_provenance_sha256=model_provenance_sha256,
    )


def _control_stamped_preflight(
    data_root: Path, store: ResearchStore, *, repo_root: Path = ROOT
) -> dict[str, object]:
    """A4 CONTROL surface created through the production preflight API."""

    from solana_alpha_lab.factory.hfic_control_integrity import (
        CURRENT_REPRESENTATION_CONTROL_V1,
    )

    return _run_production_preflight(
        data_root,
        repo_root=repo_root,
        evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1,
    )


def _actual_production_preflight(
    data_root: Path,
    *,
    repo_root: Path = ROOT,
) -> dict[str, object]:
    """Use imported manifests plus production preflight/projection bindings."""

    from solana_alpha_lab.factory.hfic_control_integrity import (
        CURRENT_REPRESENTATION_CONTROL_V1,
    )

    receipt = _run_production_preflight(
        data_root,
        repo_root=repo_root,
        evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1,
        enumerator=_enumerate_imported_control_fixture,
    )
    if receipt.get("action") == "STOP":
        raise AssertionError(
            "Imported C1/C2 production preflight stopped: "
            f"{receipt.get('terminal')} / {receipt.get('next')}"
        )
    return receipt


def _no_worthy_base(
    data_root: Path,
    store: ResearchStore,
    *,
    production_preflight: bool = False,
    repo_root: Path = ROOT,
) -> dict[str, object]:
    draft_path = (
        ROOT / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1_2.json"
        if production_preflight
        else NO_WORTHY_DRAFT
    )
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    # The A4 candidate-path acceptance uses production run_preflight; the
    # legacy CONTROL helper remains only for focused control-seam tests.
    if production_preflight:
        # A4 ladder acceptance needs the existing CONTROL input surface, but
        # the receipt and its identity must come from production run_preflight.
        preflight = _control_stamped_preflight(data_root, store, repo_root=repo_root)
        if preflight.get("action") == "STOP":
            raise AssertionError(
                "A4 production run_preflight stopped: "
                f"{preflight.get('terminal')} / {preflight.get('next')}"
            )
        from tests.test_hfic_cli import bind_draft

        draft = bind_draft(draft, preflight)
    else:
        with patch(
            "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
            side_effect=_enumerate_production_fixture,
        ):
            preflight = _control_preflight(data_root, store, repo_root=repo_root)
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


def _ordinary_pass_base(
    data_root: Path,
    store: ResearchStore,
    *,
    preflight: dict[str, object] | None = None,
    model_provenance_sha256: str | None = None,
) -> dict[str, object]:
    """Ordinary BASE final PASS via freeze→Critic→classify (no CONTROL surface)."""

    if preflight is None:
        with patch(
            "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
            side_effect=_enumerate_production_fixture,
        ):
            preflight = _ordinary_stamped_preflight(
                data_root,
                store,
                model_provenance_sha256=model_provenance_sha256,
            )
    from tests.test_hfic_cli import bind_draft

    draft = json.loads(
        (ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text(
            encoding="utf-8"
        )
    )
    draft = bind_draft(draft, preflight)
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
    spec = _submission_for_frozen(frozen)
    selected = frozen["critic_input_packet"]["selected_candidate"]
    spec["experiment_spec"]["required_feature_ids"] = list(
        selected.get("required_feature_ids") or []
    )
    apply_classification(
        frozen, spec, store=store, repo_root=ROOT, data_root=data_root
    )
    store.rebuild_projection()
    return frozen


class IdentityUnitTests(unittest.TestCase):
    def test_capability_epoch_covers_runtime_truth_owners(self) -> None:
        _digest, basis = compute_capability_epoch_for_repo(ROOT)
        paths = {str(item["path"]) for item in basis["protocol_files"]}
        self.assertTrue(
            {
                "src/solana_alpha_lab/factory/hfic_evidence_identity.py",
                "src/solana_alpha_lab/factory/hfic_preflight.py",
                "src/solana_alpha_lab/factory/hfic_session.py",
                "src/solana_alpha_lab/factory/hfic_representation_ladder.py",
                "src/solana_alpha_lab/factory/forge_input_receipt.py",
                "src/solana_alpha_lab/factory/hfic_reopened_prior_routing.py",
            }.issubset(paths)
        )

    def test_existing_ladder_readback_validates_current_market_before_lookup(self) -> None:
        from solana_alpha_lab.factory.hfic_session import _bind_store_freeze_preflight

        events: list[str] = []
        existing = {"session_id": "HFIC-SESS-EXISTING-V1"}
        preflight = {
            "forge_context_packet": {
                "ladder_representation_id": "NORMALIZED_TRAJECTORY_V1",
                "control_session_id": "HFIC-SESS-BASE",
            }
        }
        fake_store = type("FakeStore", (), {"_root": ROOT})()
        with patch(
            "solana_alpha_lab.factory.hfic_session._validate_split_identity_binding",
            side_effect=lambda *args, **kwargs: events.append("validate"),
        ), patch(
            "solana_alpha_lab.factory.hfic_session._lookup_existing_freeze_session",
            side_effect=lambda *args, **kwargs: events.append("lookup") or existing,
        ):
            result = _bind_store_freeze_preflight(
                {"owner_focus": "AUTO"},
                preflight,
                store=fake_store,
                repo_root=ROOT,
                memory_as_of="2026-09-01T00:00:00Z",
                verify_current_market_identity=True,
            )
        self.assertEqual(events, ["validate", "lookup"])
        self.assertIs(result[1], existing)

    def test_a3_pit_availability_validation_digest_is_market_identity(self) -> None:
        common = {
            "dataset_manifest_id": "MID-CURRENT",
            "dataset_fingerprint": "aa" * 32,
            "dataset_id": "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
        }
        basis_a = build_market_evidence_basis(
            datasets=[
                {
                    **common,
                    "a3_pit_availability_validation_sha256": "11" * 32,
                }
            ],
            visible_cohort_ids=["REL-C1"],
            current_dataset_manifest_id="MID-CURRENT",
            corpus_version=1,
            lineage_bindings=[
                {
                    "cohort_id": "REL-C1",
                    "release_id": "rel-c1",
                    "source_sha256": "bb" * 32,
                }
            ],
        )
        basis_b = build_market_evidence_basis(
            datasets=[
                {
                    **common,
                    "a3_pit_availability_validation_sha256": "22" * 32,
                }
            ],
            visible_cohort_ids=["REL-C1"],
            current_dataset_manifest_id="MID-CURRENT",
            corpus_version=1,
            lineage_bindings=[
                {
                    "cohort_id": "REL-C1",
                    "release_id": "rel-c1",
                    "source_sha256": "bb" * 32,
                }
            ],
        )
        self.assertEqual(
            basis_a["datasets"][0]["a3_pit_availability_validation_sha256"],
            "11" * 32,
        )
        self.assertNotEqual(
            market_evidence_epoch_sha256(basis_a),
            market_evidence_epoch_sha256(basis_b),
        )
        incomplete = build_market_evidence_basis(
            datasets=[common, {**common, "dataset_manifest_id": "MID-OTHER", "a3_pit_availability_validation_sha256": "33" * 32}],
            visible_cohort_ids=["REL-C1"],
            current_dataset_manifest_id="MID-CURRENT",
            corpus_version=1,
            lineage_bindings=[
                {
                    "cohort_id": "REL-C1",
                    "release_id": "rel-c1",
                    "source_sha256": "bb" * 32,
                }
            ],
        )
        with self.assertRaisesRegex(ValueError, "MARKET_EVIDENCE_BASIS_INCOMPLETE"):
            market_evidence_epoch_sha256(incomplete)
        for invalid_corpus_version in ({"unknown": True}, [], True, "1"):
            with self.subTest(invalid_corpus_version=invalid_corpus_version):
                invalid = {**basis_a, "corpus_version": invalid_corpus_version}
                with self.assertRaisesRegex(
                    ValueError, "MARKET_EVIDENCE_BASIS_INCOMPLETE"
                ):
                    market_evidence_epoch_sha256(invalid)

    def test_a3_label_projection_is_market_identity(self) -> None:
        common = {
            "dataset_manifest_id": "MID-CURRENT",
            "dataset_fingerprint": "aa" * 32,
            "dataset_id": "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
            "a3_pit_availability_validation_sha256": "11" * 32,
            "labels": {
                "logical_dataset_id": "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
                "corpus_version": 2,
                "is_current_corpus_version": True,
                "yield_eligible": 10,
            },
            "yield_eligible": 10,
            "feature_usable": True,
            "dataset_terminal": "SAMPLE_VALID",
        }
        basis_a = build_market_evidence_basis(
            datasets=[common],
            visible_cohort_ids=["REL-C1"],
            current_dataset_manifest_id="MID-CURRENT",
            corpus_version=2,
            lineage_bindings=[
                {
                    "cohort_id": "REL-C1",
                    "release_id": "rel-c1",
                    "source_sha256": "bb" * 32,
                }
            ],
        )
        changed = {
            **common,
            "labels": {**common["labels"], "is_current_corpus_version": False},
        }
        basis_b = build_market_evidence_basis(
            datasets=[changed],
            visible_cohort_ids=["REL-C1"],
            current_dataset_manifest_id="MID-CURRENT",
            corpus_version=2,
            lineage_bindings=[
                {
                    "cohort_id": "REL-C1",
                    "release_id": "rel-c1",
                    "source_sha256": "bb" * 32,
                }
            ],
        )
        self.assertNotEqual(
            basis_a["datasets"][0]["a3_dataset_label_projection_sha256"],
            basis_b["datasets"][0]["a3_dataset_label_projection_sha256"],
        )
        self.assertNotEqual(
            market_evidence_epoch_sha256(basis_a),
            market_evidence_epoch_sha256(basis_b),
        )

    def test_market_epoch_stable_under_docs_only_capability_change_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
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

    def test_completed_slot_requires_known_current_model_for_reuse(self) -> None:
        market = "aa" * 32
        capability = "bb" * 32
        payload = "cc" * 32
        memory = "dd" * 32
        model = "ee" * 32
        slot = scientific_slot_sha256(
            market_evidence_epoch_sha256=market,
            representation_id="BASE",
            representation_semantic_version="HFIC-V1.2",
            owner_focus="AUTO",
        )
        row = {
            "session_id": "HFIC-SESS-KNOWN-MODEL",
            "session_state": "SYNTHESIS_COMPLETE",
            "market_evidence_epoch_sha256": market,
            "scientific_slot_sha256": slot,
            "ladder_representation_id": "BASE",
            "representation_semantic_version": "HFIC-V1.2",
            "owner_focus": "AUTO",
            "capability_epoch_sha256": capability,
            "representation_payload_sha256": payload,
            "memory_eligibility_sha256": memory,
            "model_provenance_sha256": model,
            "execution_binding_sha256": execution_binding_sha256(
                scientific_slot_sha256=slot,
                capability_epoch_sha256=capability,
                representation_payload_sha256=payload,
                memory_eligibility_sha256=memory,
                model_provenance_sha256=model,
            ),
        }
        unknown = resolve_scientific_admission(
            [row],
            market_evidence_epoch=market,
            representation_id="BASE",
            representation_semantic_version="HFIC-V1.2",
            owner_focus="AUTO",
            execution_context={"capability_epoch_sha256": capability},
        )
        self.assertEqual(unknown["action"], "STOP")
        self.assertEqual(
            unknown["reason_code"],
            "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING",
        )
        exact = resolve_scientific_admission(
            [row],
            market_evidence_epoch=market,
            representation_id="BASE",
            representation_semantic_version="HFIC-V1.2",
            owner_focus="AUTO",
            execution_context={
                "capability_epoch_sha256": capability,
                "model_provenance_sha256": model,
            },
        )
        self.assertEqual(exact["action"], "RETURN_EXISTING_SESSION")

    def test_corrupt_slot_reservation_remains_unresolved_occupancy(self) -> None:
        from solana_alpha_lab.factory.research_store import (
            RecordKind,
            ResearchEvent,
        )

        def malformed_event(market: str) -> tuple[str, ResearchEvent]:
            slot = scientific_slot_sha256(
                market_evidence_epoch_sha256=market,
                representation_id="BASE",
                representation_semantic_version="HFIC-V1.2",
                owner_focus="AUTO",
            )
            body = {
                "schema": "smial.scientific-slot-admission",
                "schema_version": "1.0",
                "scientific_slot_sha256": slot,
                "session_id": "HFIC-SESS-CORRUPT-RESERVATION",
                "market_evidence_epoch_sha256": market,
                "ladder_representation_id": "BASE",
                "representation_semantic_version": "HFIC-V1.2",
                "owner_focus": "AUTO",
                "admission_state": "RESERVED",
            }
            raw = json.dumps(body, sort_keys=True, separators=(",", ":"))
            wrapper = {
                "research_artifact_id": f"HFIC-ART-SLOT-ADMISSION-{slot.upper()}",
                "session_id": body["session_id"],
                "artifact_kind": "SCIENTIFIC_SLOT_ADMISSION",
                "payload_canonical": raw,
                # Outer committed record valid; only the artifact self-hash is
                # corrupted, matching the production reader failure mode.
                "payload_sha256": "00" * 32,
            }
            payload_json = json.dumps(wrapper, sort_keys=True, separators=(",", ":"))
            now = datetime(2026, 9, 1, tzinfo=UTC)
            return slot, ResearchEvent(
                record_id=f"HFIC-ART-SLOT-ADMISSION-{slot.upper()}",
                record_kind=RecordKind.RESEARCH_ARTIFACT,
                entity_id=f"HFIC-ART-SLOT-ADMISSION-{slot.upper()}",
                hypothesis_version_id=None,
                run_id=None,
                transaction_id=f"RESEARCH-TXN-CORRUPT-SLOT-{slot.upper()}",
                effective_at=now,
                first_reliable_available_at=now,
                supersedes_record_id=None,
                payload_json=payload_json,
                payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
                schema_version="1.0",
                producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
                producer_git_sha="a" * 40,
                created_at=now,
            )

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            from tests.test_hfic_preflight import _CLOCK, _commission, _git_snapshot

            _commission(data_root)
            store = ResearchStore(data_root)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
            ):
                initial = run_preflight(
                    ROOT,
                    data_root,
                    owner_focus="AUTO",
                    auto_commission=False,
                    git_snapshot=_git_snapshot(),
                    clock=_CLOCK,
                    persist=False,
                )
            market = str(initial["market_evidence_epoch_sha256"])
            _slot, event = malformed_event(market)
            store.append([event], transaction_id=event.transaction_id)
            reservations = list_scientific_slot_admissions(store)
            self.assertEqual(len(reservations), 1)
            self.assertEqual(
                reservations[0].get("identity_binding_status"), "CONFLICT"
            )
            decision = resolve_scientific_admission(
                [],
                market_evidence_epoch=market,
                representation_id="BASE",
                representation_semantic_version="HFIC-V1.2",
                owner_focus="AUTO",
                reservations=reservations,
            )
            before = store.diagnostics().committed_inventory_sha256
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
            ):
                blocked = run_preflight(
                    ROOT,
                    data_root,
                    owner_focus="AUTO",
                    auto_commission=False,
                    git_snapshot=_git_snapshot(),
                    clock=_CLOCK,
                    persist=True,
                )
            after = ResearchStore(data_root).diagnostics().committed_inventory_sha256
        self.assertEqual(blocked["action"], "STOP")
        self.assertEqual(blocked["terminal"], "SCIENTIFIC_IDENTITY_CONFLICT")
        self.assertEqual(
            blocked["writes"],
            {"research_store": 0, "forge_context": 0, "session": 0},
        )
        self.assertEqual(after, before)
        self.assertEqual(decision["action"], "STOP")
        self.assertEqual(decision["reason_code"], "SCIENTIFIC_IDENTITY_CONFLICT")

    def test_identity_conflict_in_different_market_does_not_globally_block(self) -> None:
        current_market = "aa" * 32
        historical_market = "bb" * 32
        row = {
            "session_id": "HFIC-SESS-HISTORICAL-CONFLICT",
            "market_evidence_epoch_sha256": historical_market,
            "scientific_slot_sha256": "bad",
            "identity_binding_status": "CONFLICT",
            "identity_conflict_fields": ["scientific_slot_sha256"],
            "owner_focus": "ALT",
        }
        decision = resolve_scientific_admission(
            [row],
            market_evidence_epoch=current_market,
            representation_id="BASE",
            representation_semantic_version="HFIC-V1.2",
            owner_focus="AUTO",
        )
        self.assertEqual(decision["action"], "START_NEW_SESSION")

    def test_corrupt_reservation_slot_identity_remains_unscoped_occupancy(self) -> None:
        """A valid-looking market in a mismatched body cannot free any budget."""

        from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            record_slot = "aa" * 32
            body_slot = "bb" * 32
            body = {
                "schema": "smial.scientific-slot-admission",
                "schema_version": "1.0",
                "scientific_slot_sha256": body_slot,
                "session_id": "HFIC-SESS-CORRUPT-RESERVATION",
                "market_evidence_epoch_sha256": "cc" * 32,
                "admission_state": "RESERVED",
            }
            canonical = json.dumps(
                body, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            record_id = f"HFIC-ART-SLOT-ADMISSION-{record_slot.upper()}"
            wrapper = {
                "research_artifact_id": record_id,
                "session_id": body["session_id"],
                "artifact_kind": "SCIENTIFIC_SLOT_ADMISSION",
                "payload_canonical": canonical,
                "payload_sha256": digest,
            }
            payload_json = json.dumps(
                wrapper, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            timestamp = datetime(2026, 9, 22, tzinfo=UTC)
            event = ResearchEvent(
                record_id=record_id,
                record_kind=RecordKind.RESEARCH_ARTIFACT,
                entity_id=record_id,
                hypothesis_version_id=None,
                run_id=None,
                transaction_id="RESEARCH-TXN-CORRUPT-RESERVATION",
                effective_at=timestamp,
                first_reliable_available_at=timestamp,
                supersedes_record_id=None,
                payload_json=payload_json,
                payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
                schema_version="1.0",
                producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
                producer_git_sha="0" * 40,
                created_at=timestamp,
            )
            store.append(
                [event], transaction_id="RESEARCH-TXN-CORRUPT-RESERVATION"
            )

            decision = resolve_scientific_admission(
                [],
                reservations=list_scientific_slot_admissions(store),
                market_evidence_epoch="dd" * 32,
                representation_id="BASE",
                representation_semantic_version="HFIC-V1.2",
                owner_focus="AUTO",
            )

        self.assertEqual(decision["action"], "STOP")
        self.assertEqual(decision["occupancy"], "UNRESOLVED_BINDING")

    def test_history_market_conflict_blocks_known_market_without_global_veto(self) -> None:
        from solana_alpha_lab.factory.research_store import RecordKind, ResearchEvent
        from solana_alpha_lab.factory.hfic_session import focus_key_sha256

        with tempfile.TemporaryDirectory() as tmp:
            store = ResearchStore(Path(tmp))
            market_a, market_b, market_c = "aa" * 32, "bb" * 32, "cc" * 32
            focus = focus_key_sha256("AUTO")
            timestamp = datetime(2026, 9, 22, tzinfo=UTC)
            events = []
            for sequence, market in ((1, market_a), (2, market_b)):
                slot = scientific_slot_sha256(
                    market_evidence_epoch_sha256=market,
                    representation_id="BASE",
                    representation_semantic_version="HFIC-V1.2",
                    owner_focus="AUTO",
                )
                body = {
                    "hfic_protocol": "HFIC-V1.2",
                    "session_id": "HFIC-SESS-MARKET-HISTORY-CONFLICT",
                    "phase": "FROZEN_AWAITING_CRITIC",
                    "evidence_epoch_sha256": market,
                    "market_evidence_epoch_sha256": market,
                    "capability_epoch_sha256": "dd" * 32,
                    "focus_key_sha256": focus,
                    "search_key_sha256": f"{sequence:064x}",
                    "memory_eligibility_sha256": "ee" * 32,
                    "prompt_version": "HFIC-V1.2",
                    "owner_focus": "AUTO",
                    "hfic_cycle_seq": sequence,
                    "ladder_representation_id": "BASE",
                    "representation_semantic_version": "HFIC-V1.2",
                    "scientific_slot_sha256": slot,
                }
                record_id = f"HFIC-CYCLE-MARKET-CONFLICT-{sequence}"
                payload_json = json.dumps(
                    body, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                events.append(
                    ResearchEvent(
                        record_id=record_id,
                        record_kind=RecordKind.RESEARCH_CYCLE,
                        entity_id=body["session_id"],
                        hypothesis_version_id=None,
                        run_id=None,
                        transaction_id="RESEARCH-TXN-MARKET-HISTORY-CONFLICT",
                        effective_at=timestamp,
                        first_reliable_available_at=timestamp,
                        supersedes_record_id=None,
                        payload_json=payload_json,
                        payload_sha256=hashlib.sha256(
                            payload_json.encode("utf-8")
                        ).hexdigest(),
                        schema_version="1.0",
                        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
                        producer_git_sha="0" * 40,
                        created_at=timestamp,
                    )
                )
            store.append(events, transaction_id="RESEARCH-TXN-MARKET-HISTORY-CONFLICT")
            rows = list_hfic_sessions(store)
            blocked = resolve_scientific_admission(
                rows,
                market_evidence_epoch=market_a,
                representation_id="BASE",
                representation_semantic_version="HFIC-V1.2",
                owner_focus="AUTO",
            )
            unrelated = resolve_scientific_admission(
                rows,
                market_evidence_epoch=market_c,
                representation_id="BASE",
                representation_semantic_version="HFIC-V1.2",
                owner_focus="AUTO",
            )

        self.assertEqual(blocked["action"], "STOP")
        self.assertEqual(blocked["reason_code"], "SCIENTIFIC_IDENTITY_CONFLICT")
        self.assertEqual(unrelated["action"], "START_NEW_SESSION")

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

    def test_malformed_focus_key_is_not_occupancy_evidence(self) -> None:
        market = "aa" * 32
        row = {
            "session_id": "HFIC-SESS-TAMPERED-FOCUS",
            "market_evidence_epoch_sha256": market,
            "ladder_representation_id": "BASE",
            "representation_semantic_version": "HFIC-V1.2",
            "owner_focus": "AUTO",
            "focus_key_sha256": "bad",
            "scientific_slot_sha256": scientific_slot_sha256(
                market_evidence_epoch_sha256=market,
                representation_id="BASE",
                representation_semantic_version="HFIC-V1.2",
                owner_focus="AUTO",
            ),
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

    def test_market_stamped_legacy_row_without_slot_stays_occupied(self) -> None:
        market = "aa" * 32
        row = {
            "session_id": "HFIC-SESS-LEGACY-MARKET",
            "market_evidence_epoch_sha256": market,
            "evidence_epoch_sha256": "bb" * 32,
            "owner_focus": "AUTO",
        }
        decision = resolve_scientific_admission(
            [row],
            market_evidence_epoch=market,
            representation_id="BASE",
            representation_semantic_version="HFIC-V1.2",
            owner_focus="AUTO",
        )
        self.assertEqual(decision["action"], "STOP")
        self.assertEqual(
            decision["reason_code"],
            "SCIENTIFIC_SLOT_OCCUPIED_READBACK_MISSING",
        )
        self.assertEqual(decision["occupancy"], "OCCUPIED_UNRESOLVED")

    def test_malformed_market_stamp_without_slot_cannot_free_market_budget(self) -> None:
        market = "aa" * 32
        malformed = "g" + "a" * 63
        row = {
            "session_id": "HFIC-SESS-MALFORMED-MARKET",
            "market_evidence_epoch_sha256": malformed,
            "evidence_epoch_sha256": "bb" * 32,
            "owner_focus": "AUTO",
            "forge_context_packet": {
                "bound_visible_cohort_ids": ["REL-C1", "REL-C2"]
            },
        }
        disposition = classify_legacy_session_disposition(
            row,
            current_market_epoch=market,
            current_visible_cohort_ids=["REL-C1", "REL-C2"],
        )
        self.assertEqual(disposition["disposition"], DISPOSITION_UNRESOLVED)
        self.assertIn("MALFORMED_MARKET_EPOCH_BINDING", disposition["reasons"])
        decision = resolve_scientific_admission(
            [row],
            market_evidence_epoch=market,
            representation_id="BASE",
            representation_semantic_version="HFIC-V1.2",
            owner_focus="AUTO",
            current_visible_cohort_ids=["REL-C1", "REL-C2"],
        )
        self.assertEqual(decision["action"], "STOP")
        self.assertEqual(decision["reason_code"], "SCIENTIFIC_IDENTITY_CONFLICT")
        self.assertEqual(decision["occupancy"], "UNRESOLVED_BINDING")

    def test_unregistered_representation_version_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "REPRESENTATION_VERSION_UNREGISTERED"
        ):
            resolve_scientific_admission(
                [],
                market_evidence_epoch="aa" * 32,
                representation_id="BASE",
                representation_semantic_version="UNREGISTERED-V9",
                owner_focus="AUTO",
            )

    def test_admission_loads_registry_from_exact_repo_root(self) -> None:
        registry = {
            "representations": [
                {"id": "BASE", "status": "ACTIVE", "version": "HFIC-V1.2"}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp, patch(
            "solana_alpha_lab.factory.hfic_representation_ladder.load_ladder_registry",
            return_value=registry,
        ) as loader:
            decision = resolve_scientific_admission(
                [],
                market_evidence_epoch="aa" * 32,
                representation_id="BASE",
                representation_semantic_version="HFIC-V1.2",
                owner_focus="AUTO",
                repo_root=Path(tmp),
            )
        self.assertEqual(decision["action"], "START_NEW_SESSION")
        loader.assert_called_once_with(
            Path(tmp) / "configs" / "hfic_representation_ladder_v1.yaml"
        )

    def test_model_context_drift_blocks_reuse_without_resetting_market_budget(self) -> None:
        market = "aa" * 32
        slot = scientific_slot_sha256(
            market_evidence_epoch_sha256=market,
            representation_id="BASE",
            representation_semantic_version="HFIC-V1.2",
            owner_focus="AUTO",
        )
        row = {
            "session_id": "HFIC-SESS-MODEL",
            "market_evidence_epoch_sha256": market,
            "ladder_representation_id": "BASE",
            "representation_semantic_version": "HFIC-V1.2",
            "owner_focus": "AUTO",
            "scientific_slot_sha256": slot,
            "session_state": "SYNTHESIS_COMPLETE",
            "capability_epoch_sha256": "bb" * 32,
            "model_provenance_sha256": "11" * 32,
        }
        decision = resolve_scientific_admission(
            [row],
            market_evidence_epoch=market,
            representation_id="BASE",
            representation_semantic_version="HFIC-V1.2",
            owner_focus="AUTO",
            execution_context={
                "capability_epoch_sha256": "bb" * 32,
                "model_provenance_sha256": "22" * 32,
            },
        )
        self.assertEqual(decision["action"], "STOP")
        self.assertEqual(
            decision["reason_code"],
            "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING",
        )

    def test_malformed_persisted_provenance_does_not_reuse_without_context(self) -> None:
        market = "aa" * 32
        slot = scientific_slot_sha256(
            market_evidence_epoch_sha256=market,
            representation_id="BASE",
            representation_semantic_version="HFIC-V1.2",
            owner_focus="AUTO",
        )
        row = {
            "session_id": "HFIC-SESS-MALFORMED-MODEL",
            "market_evidence_epoch_sha256": market,
            "ladder_representation_id": "BASE",
            "representation_semantic_version": "HFIC-V1.2",
            "owner_focus": "AUTO",
            "scientific_slot_sha256": slot,
            "session_state": "SYNTHESIS_COMPLETE",
            "model_provenance_sha256": "not-a-sha256",
        }
        decision = resolve_scientific_admission(
            [row],
            market_evidence_epoch=market,
            representation_id="BASE",
            representation_semantic_version="HFIC-V1.2",
            owner_focus="AUTO",
        )
        self.assertEqual(decision["action"], "STOP")
        self.assertEqual(
            decision["reason_code"],
            "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING",
        )

    def test_malformed_nested_identity_fails_closed(self) -> None:
        from solana_alpha_lab.factory.hfic_session import _execution_identity_fields

        source = {
            "market_evidence_epoch_sha256": "aa" * 32,
            "capability_epoch_sha256": "bb" * 32,
            "memory_eligibility_sha256": "cc" * 32,
            "model_provenance_sha256": "dd" * 32,
            "representation_payload_sha256": "ee" * 32,
            "ladder_representation_id": "BASE",
            "representation_semantic_version": "HFIC-V1.2",
            "owner_focus": "AUTO",
            "forge_context_packet": {"model_provenance_sha256": "not-a-sha256"},
        }
        with self.assertRaisesRegex(HficSessionError, "SCIENTIFIC_IDENTITY_CONFLICT"):
            _execution_identity_fields(source)

    def test_conflicting_representation_or_focus_sources_fail_closed(self) -> None:
        from solana_alpha_lab.factory.hfic_session import _execution_identity_fields

        with self.assertRaisesRegex(HficSessionError, "SCIENTIFIC_IDENTITY_CONFLICT"):
            _execution_identity_fields(
                {
                    "ladder_representation_id": "NORMALIZED_TRAJECTORY_V1",
                    "owner_focus": "AUTO",
                },
                {
                    "ladder_representation_id": "SYNTHETIC_LATER_V2",
                    "owner_focus": "ALT",
                },
            )

    def test_tampered_pending_execution_binding_blocks_resume(self) -> None:
        market = "aa" * 32
        slot = scientific_slot_sha256(
            market_evidence_epoch_sha256=market,
            representation_id="BASE",
            representation_semantic_version="HFIC-V1.2",
            owner_focus="AUTO",
        )
        row = {
            "session_id": "HFIC-SESS-PENDING-TAMPER",
            "market_evidence_epoch_sha256": market,
            "ladder_representation_id": "BASE",
            "representation_semantic_version": "HFIC-V1.2",
            "owner_focus": "AUTO",
            "scientific_slot_sha256": slot,
            "session_state": "FROZEN_AWAITING_CRITIC",
            "capability_epoch_sha256": "bb" * 32,
            "representation_payload_sha256": "cc" * 32,
            "memory_eligibility_sha256": "dd" * 32,
            "model_provenance_sha256": "ee" * 32,
            "execution_binding_sha256": "00" * 32,
        }
        decision = resolve_scientific_admission(
            [row],
            market_evidence_epoch=market,
            representation_id="BASE",
            representation_semantic_version="HFIC-V1.2",
            owner_focus="AUTO",
            memory_eligibility_sha256="dd" * 32,
            execution_context={"capability_epoch_sha256": "bb" * 32},
        )
        self.assertEqual(decision["action"], "STOP")
        self.assertEqual(
            decision["reason_code"],
            "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING",
        )

    def test_malformed_execution_context_fails_closed(self) -> None:
        decision = resolve_scientific_admission(
            [],
            market_evidence_epoch="aa" * 32,
            representation_id="BASE",
            representation_semantic_version="HFIC-V1.2",
            owner_focus="AUTO",
            execution_context={"model_provenance_sha256": "not-a-sha256"},
        )
        self.assertEqual(decision["action"], "STOP")
        self.assertEqual(decision["reason_code"], "SCIENTIFIC_IDENTITY_CONFLICT")

    def test_execution_binding_is_positive_and_tamper_checked(self) -> None:
        from solana_alpha_lab.factory.hfic_session import _execution_identity_fields

        source = {
            "market_evidence_epoch_sha256": "aa" * 32,
            "capability_epoch_sha256": "bb" * 32,
            "memory_eligibility_sha256": "cc" * 32,
            "model_provenance_sha256": "dd" * 32,
            "representation_payload_sha256": "ee" * 32,
            "ladder_representation_id": "BASE",
            "representation_semantic_version": "HFIC-V1.2",
            "owner_focus": "AUTO",
        }
        fields = _execution_identity_fields(source)
        self.assertRegex(str(fields.get("scientific_slot_sha256")), r"^[0-9a-f]{64}$")
        self.assertRegex(
            str(fields.get("execution_binding_sha256")), r"^[0-9a-f]{64}$"
        )
        expected = execution_binding_sha256(
            scientific_slot_sha256=str(fields["scientific_slot_sha256"]),
            capability_epoch_sha256=source["capability_epoch_sha256"],
            control_session_id=None,
            representation_payload_sha256=source["representation_payload_sha256"],
            memory_eligibility_sha256=source["memory_eligibility_sha256"],
            model_provenance_sha256=source["model_provenance_sha256"],
        )
        self.assertEqual(fields["execution_binding_sha256"], expected)
        with self.assertRaisesRegex(
            ValueError, "EXECUTION_BINDING_PROVENANCE_INCOMPLETE"
        ):
            execution_binding_sha256(
                scientific_slot_sha256=str(fields["scientific_slot_sha256"]),
                capability_epoch_sha256=source["capability_epoch_sha256"],
                representation_payload_sha256=None,
                memory_eligibility_sha256=source["memory_eligibility_sha256"],
                model_provenance_sha256=source["model_provenance_sha256"],
            )
        for key in (
            "capability_epoch_sha256",
            "memory_eligibility_sha256",
            "model_provenance_sha256",
            "representation_payload_sha256",
        ):
            changed = {**source, key: "ff" * 32}
            self.assertNotEqual(
                _execution_identity_fields(changed)["execution_binding_sha256"],
                fields["execution_binding_sha256"],
            )
        with self.assertRaisesRegex(ValueError, "SCIENTIFIC_IDENTITY_CONFLICT"):
            _execution_identity_fields(
                {**source, "execution_binding_sha256": "00" * 32}
            )

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
                side_effect=_enumerate_production_fixture,
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

    def test_g6_v1_generated_draft_persists_from_representation_receipt(self) -> None:
        """A V1 start exposes a hash-bound receipt consumable by persist-draft."""

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = _no_worthy_base(data_root, store, production_preflight=True)
            v1_preflight, _envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(base["session_id"]),
                model_provenance_sha256="11" * 32,
            )

            self.assertEqual(v1_preflight.get("action"), "START_NEW_SESSION")
            receipt_id = str(v1_preflight.get("receipt_id") or "")
            self.assertTrue(receipt_id.startswith("HFIC-PREFLIGHT-"))
            self.assertEqual(
                v1_preflight.get("preflight_receipt_sha256"),
                canonical_preflight_receipt_sha256(v1_preflight),
            )
            self.assertEqual(
                v1_preflight["forge_context_packet"].get("search_key_sha256"),
                v1_preflight["search_key_sha256"],
            )
            draft = json.loads(
                (ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json")
                .read_text(encoding="utf-8")
            )
            from tests.test_hfic_cli import bind_draft

            draft = bind_draft(draft, v1_preflight)
            draft["preflight_receipt_id"] = receipt_id
            draft["preflight_receipt_sha256"] = v1_preflight[
                "preflight_receipt_sha256"
            ]
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
            ):
                saved = persist_generated_draft(
                    store,
                    draft,
                    preflight_receipt=v1_preflight,
                    repo_root=ROOT,
                    representation_id="NORMALIZED_TRAJECTORY_V1",
                    model_provenance_sha256="11" * 32,
                )
            admissions = list_scientific_slot_admissions(store)
            expected_slot = scientific_slot_sha256(
                market_evidence_epoch_sha256=str(
                    v1_preflight["market_evidence_epoch_sha256"]
                ),
                representation_id="NORMALIZED_TRAJECTORY_V1",
                representation_semantic_version=str(
                    v1_preflight["representation_semantic_version"]
                ),
                owner_focus=str(v1_preflight["owner_focus"]),
            )

        self.assertEqual(saved["draft_lifecycle"], "GENERATED_BEFORE_FREEZE")
        self.assertEqual(saved["model_provenance_sha256"], "11" * 32)
        self.assertIn(
            expected_slot,
            {str(row.get("scientific_slot_sha256")) for row in admissions},
        )

    def test_g6_invalid_generated_draft_cannot_reserve_scientific_slot(self) -> None:
        """Schema-invalid model output leaves both draft and slot budget untouched."""

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = _no_worthy_base(data_root, store, production_preflight=True)
            v1_preflight, _envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(base["session_id"]),
            )
            draft = json.loads(
                (ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json")
                .read_text(encoding="utf-8")
            )
            from tests.test_hfic_cli import bind_draft

            draft = bind_draft(draft, v1_preflight)
            draft["preflight_receipt_id"] = v1_preflight["receipt_id"]
            draft["preflight_receipt_sha256"] = v1_preflight[
                "preflight_receipt_sha256"
            ]
            draft.pop("candidates")
            inventory_before = store.diagnostics().committed_inventory_sha256
            admissions_before = list_scientific_slot_admissions(store)

            with self.assertRaisesRegex(HficSessionError, "HFIC_PROTOCOL_INVALID"):
                persist_generated_draft(
                    store,
                    draft,
                    preflight_receipt=v1_preflight,
                    repo_root=ROOT,
                    representation_id="NORMALIZED_TRAJECTORY_V1",
                )

            self.assertEqual(
                store.diagnostics().committed_inventory_sha256, inventory_before
            )
            self.assertEqual(
                list_scientific_slot_admissions(store), admissions_before
            )

    def test_g6_orphan_reservation_rejects_same_session_execution_drift(self) -> None:
        """A crash reservation cannot be completed under a different model bind."""

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            original = _ordinary_stamped_preflight(
                data_root, store, model_provenance_sha256="11" * 32
            )
            session_id = "HFIC-SESS-" + str(original["search_key_sha256"])[
                :16
            ].upper()
            binding = {**original, "session_id": session_id}
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
            ):
                persist_scientific_slot_admission(
                    store, binding, repo_root=ROOT
                )

            drifted = dict(original)
            drifted["model_provenance_sha256"] = "22" * 32
            drifted["preflight_receipt_sha256"] = canonical_preflight_receipt_sha256(
                drifted
            )
            draft = json.loads(
                (ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json")
                .read_text(encoding="utf-8")
            )
            from tests.test_hfic_cli import bind_draft

            draft = bind_draft(draft, drifted)
            inventory_before = store.diagnostics().committed_inventory_sha256
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
            ), self.assertRaisesRegex(
                HficSessionError,
                "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING",
            ):
                persist_generated_draft(
                    store,
                    draft,
                    preflight_receipt=drifted,
                    repo_root=ROOT,
                    model_provenance_sha256="22" * 32,
                )

            self.assertEqual(
                store.diagnostics().committed_inventory_sha256, inventory_before
            )

    def test_g8_v1_persist_rejects_c1c2_receipt_after_production_c3_import(self) -> None:
        """A saved V1 draft cannot reserve stale C1+C2 after real C3 import."""

        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            data_root = base_dir / "rdp"
            data_root.mkdir()
            release_c1, _, _ = _seal_week(base_dir, 0)
            release_c2, _, _ = _seal_week(base_dir, 1)
            release_c3, _, _ = _seal_week(base_dir, 2)
            import_live_cohort(
                release_root=release_c1,
                data_root=data_root,
                import_time=datetime(2026, 1, 20, tzinfo=UTC),
            )
            import_live_cohort(
                release_root=release_c2,
                data_root=data_root,
                import_time=datetime(2026, 1, 27, tzinfo=UTC),
            )
            store = ResearchStore(data_root)
            control_preflight = _actual_production_preflight(data_root)
            control_draft = json.loads(
                (
                    ROOT
                    / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1_2.json"
                ).read_text(encoding="utf-8")
            )
            from tests.test_hfic_cli import bind_draft

            control_draft = bind_draft(control_draft, control_preflight)
            control = freeze_draft(
                control_draft,
                preflight_receipt=control_preflight,
                store=store,
                repo_root=ROOT,
            )
            persist_no_worthy_session(
                store,
                control,
                repo_root=ROOT,
                identities=assign_portfolio_ids(control_draft["candidates"]),
                draft=control_draft,
                preflight_receipt=control_preflight,
            )
            store.rebuild_projection()
            v1_preflight, _envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(control["session_id"]),
                model_provenance_sha256="11" * 32,
            )
            v1_draft = json.loads(
                (ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json")
                .read_text(encoding="utf-8")
            )
            v1_draft = bind_draft(v1_draft, v1_preflight)
            v1_draft["preflight_receipt_id"] = v1_preflight["receipt_id"]
            v1_draft["preflight_receipt_sha256"] = v1_preflight[
                "preflight_receipt_sha256"
            ]
            imported = import_live_cohort(
                release_root=release_c3,
                data_root=data_root,
                import_time=datetime(2026, 2, 3, tzinfo=UTC),
            )
            self.assertEqual(imported["status"], "IMPORTED")
            inventory_before = store.diagnostics().committed_inventory_sha256

            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_imported_control_fixture,
            ), self.assertRaisesRegex(HficSessionError, "MARKET_IDENTITY_DRIFT"):
                persist_generated_draft(
                    store,
                    v1_draft,
                    preflight_receipt=v1_preflight,
                    repo_root=ROOT,
                    representation_id="NORMALIZED_TRAJECTORY_V1",
                    model_provenance_sha256="11" * 32,
                )

            self.assertEqual(
                store.diagnostics().committed_inventory_sha256, inventory_before
            )

    def test_ordinary_stamped_preflight_uses_normal_run_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            preflight = _ordinary_stamped_preflight(data_root, store)

        self.assertIn("action", preflight)
        self.assertNotEqual(preflight["action"], "STOP")
        self.assertEqual(preflight.get("owner_focus"), "AUTO")
        self.assertIsInstance(preflight.get("market_evidence_epoch_sha256"), str)
        self.assertIsInstance(preflight.get("capability_epoch_sha256"), str)
        self.assertNotIn("evidence_surface_mode", preflight)
        packet = preflight.get("forge_context_packet")
        self.assertIsInstance(packet, dict)
        self.assertNotIn("evidence_surface_mode", packet)

    def test_g1_g2_import_and_normal_entry_stamps_market(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
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
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = _no_worthy_base(data_root, store, production_preflight=True)
            self.assertEqual(
                base.get("evidence_surface_mode"),
                "CURRENT_REPRESENTATION_CONTROL_V1",
            )
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
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
            draft = _fresh_v12_draft(v1_pre)
            frozen = freeze_draft(draft, preflight_receipt=v1_pre, repo_root=ROOT)
            self.assertEqual(frozen.get("market_evidence_epoch_sha256"), market)
            scientific_slot = str(frozen.get("scientific_slot_sha256") or "")
            capability_epoch = str(frozen.get("capability_epoch_sha256") or "")
            self.assertRegex(scientific_slot, r"^[0-9a-f]{64}$")
            self.assertRegex(capability_epoch, r"^[0-9a-f]{64}$")
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
            self.assertEqual(listed_freeze.get("scientific_slot_sha256"), scientific_slot)
            self.assertEqual(listed_freeze.get("capability_epoch_sha256"), capability_epoch)
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
            market_slots_freeze = {
                row["scientific_slot_sha256"]
                for row in usage_freeze["representation_slots"]
            }
            self.assertIn(scientific_slot, market_slots_freeze)
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
            self.assertEqual(listed_mid.get("scientific_slot_sha256"), scientific_slot)
            self.assertEqual(listed_mid.get("capability_epoch_sha256"), capability_epoch)
            usage_mid = epoch_search_budget_usage(
                list_hfic_sessions(store), evidence_epoch=market
            )
            self.assertEqual(
                {
                    row["scientific_slot_sha256"]
                    for row in usage_mid["representation_slots"]
                },
                market_slots_freeze,
            )
            self.assertGreaterEqual(
                usage_mid["auto_sessions_used"] + usage_mid["distinct_focus_used"], 1
            )
            spec = _submission_for_frozen(frozen)
            from solana_alpha_lab.factory.document_runner import repository_git_snapshot

            self.assertEqual(
                frozen.get("git_composite_sha256"),
                repository_git_snapshot(ROOT).composite_sha256,
                "Git composite drifted before classification",
            )
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
            self.assertEqual(listed_done.get("scientific_slot_sha256"), scientific_slot)
            self.assertEqual(listed_done.get("capability_epoch_sha256"), capability_epoch)
            bundle = load_session_bundle(store_reloaded, frozen["session_id"])
            assert bundle is not None
            self.assertEqual(bundle.get("market_evidence_epoch_sha256"), market)
            self.assertEqual(
                bundle.get("scientific_slot_sha256"), scientific_slot
            )
            self.assertEqual(bundle.get("capability_epoch_sha256"), capability_epoch)
            self.assertEqual(
                bundle.get("execution_binding_sha256"),
                listed_done.get("execution_binding_sha256"),
            )
            usage_done = epoch_search_budget_usage(
                list_hfic_sessions(store_reloaded), evidence_epoch=market
            )
            self.assertEqual(
                {
                    row["scientific_slot_sha256"]
                    for row in usage_done["representation_slots"]
                },
                market_slots_freeze,
            )
            self.assertGreaterEqual(
                usage_done["auto_sessions_used"] + usage_done["distinct_focus_used"], 1
            )
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
            ):
                finished = evaluate_forge_run(ROOT, data_root, persist=True)
                retry = evaluate_forge_run(ROOT, data_root, persist=False)
            self.assertEqual(finished["next_action"], ACTION_OWNER_CANDIDATE)
            self.assertEqual(finished["owner_final"], ACTION_OWNER_CANDIDATE)
            self.assertNotIn(
                "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING",
                finished.get("blocking_reason_codes") or [],
            )
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
            restarted = next(
                item for item in sessions_after if item.get("session_id") == frozen["session_id"]
            )
            self.assertEqual(restarted.get("scientific_slot_sha256"), scientific_slot)
            self.assertEqual(restarted.get("capability_epoch_sha256"), capability_epoch)
            restarted_usage = epoch_search_budget_usage(
                sessions_after, evidence_epoch=market
            )
            self.assertEqual(
                {
                    row["scientific_slot_sha256"]
                    for row in restarted_usage["representation_slots"]
                },
                market_slots_freeze,
            )
            self.assertTrue(
                any(item.get("session_id") == base["session_id"] for item in sessions_after)
            )

    def test_g11_completed_replay_checks_known_model_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            model = "11" * 32
            _ordinary_pass_base(
                data_root, store, model_provenance_sha256=model
            )
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
            ):
                finished = evaluate_forge_run(
                    ROOT,
                    data_root,
                    persist=True,
                    execution_context={"model_provenance_sha256": model},
                )
                replay = evaluate_forge_run(
                    ROOT,
                    data_root,
                    persist=False,
                    execution_context={"model_provenance_sha256": model},
                )
                unknown = evaluate_forge_run(ROOT, data_root, persist=False)
                drifted = evaluate_forge_run(
                    ROOT,
                    data_root,
                    persist=False,
                    execution_context={"model_provenance_sha256": "22" * 32},
                )
        self.assertEqual(finished["next_action"], ACTION_OWNER_CANDIDATE)
        self.assertEqual(replay["next_action"], ACTION_RETURN_EXISTING)
        self.assertEqual(unknown["next_action"], ACTION_OBSERVABILITY_BLOCKED)
        self.assertIn(
            "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING",
            unknown["blocking_reason_codes"],
        )
        self.assertEqual(drifted["next_action"], ACTION_OBSERVABILITY_BLOCKED)
        self.assertIn(
            "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING",
            drifted["blocking_reason_codes"],
        )
        self.assertEqual(drifted["writes"]["research_store"], 0)

    def test_g11_completed_replay_checks_persisted_binding_before_readback(self) -> None:
        """A tampered completed artifact cannot bypass the production replay gate."""

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
            ):
                base = _no_worthy_base(data_root, store, production_preflight=True)
                started = evaluate_forge_run(ROOT, data_root, persist=True)
            self.assertEqual(started["next_action"], ACTION_START_V1)
            v1_pre, _envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(base["session_id"]),
                model_provenance_sha256="11" * 32,
            )
            self.assertEqual(v1_pre.get("model_provenance_sha256"), "11" * 32)
            draft = _fresh_v12_draft(v1_pre)
            frozen = freeze_draft(
                draft, preflight_receipt=v1_pre, repo_root=ROOT
            )
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
            spec = _submission_for_frozen(frozen)
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
                side_effect=_enumerate_production_fixture,
            ):
                finished = evaluate_forge_run(
                    ROOT,
                    data_root,
                    persist=True,
                    execution_context={"model_provenance_sha256": "11" * 32},
                )

            self.assertEqual(finished["next_action"], ACTION_OWNER_CANDIDATE)
            self.assertRegex(
                str(finished.get("execution_binding_sha256")), r"^[0-9a-f]{64}$"
            )

            from solana_alpha_lab.factory import hfic_representation_ladder as ladder

            real_lookup = ladder._lookup_run_artifact

            def tampered_lookup(
                current_store: ResearchStore, identity: str
            ) -> dict[str, object] | None:
                body = real_lookup(current_store, identity)
                if body is None:
                    return None
                tampered = dict(body)
                tampered["execution_binding_sha256"] = "00" * 32
                return tampered

            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
            ), patch(
                "solana_alpha_lab.factory.hfic_representation_ladder._lookup_run_artifact",
                side_effect=tampered_lookup,
            ):
                replay = evaluate_forge_run(
                    ROOT,
                    data_root,
                    persist=False,
                    execution_context={"model_provenance_sha256": "11" * 32},
                )

        self.assertEqual(replay["next_action"], ACTION_OBSERVABILITY_BLOCKED)
        self.assertEqual(replay["owner_final"], ACTION_OBSERVABILITY_BLOCKED)
        self.assertEqual(replay["owner_class"], OWNER_CLASS_OBSERVABILITY_BLOCKED)
        self.assertEqual(
            replay["execution_provenance_status"], EXEC_PROVENANCE_CONFLICT
        )
        self.assertIn("SCIENTIFIC_IDENTITY_CONFLICT", replay["blocking_reason_codes"])
        self.assertEqual(
            replay["writes"], {"research_store": 0, "forge_run": 0, "session": 0}
        )
        self.assertNotIn("status: DONE", replay["owner_readout"])

    def test_g11_pending_resume_checks_known_model_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            from solana_alpha_lab.factory.hfic_control_integrity import (
                CURRENT_REPRESENTATION_CONTROL_V1,
            )
            from tests.test_hfic_preflight import _CLOCK, _git_snapshot

            preflight = _control_stamped_preflight(data_root, store)
            from tests.test_hfic_cli import bind_draft

            draft = json.loads(
                (
                    ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json"
                ).read_text(encoding="utf-8")
            )
            draft = bind_draft(draft, preflight)
            inventory_before_invalid_receipt = (
                store.diagnostics().committed_inventory_sha256
            )
            tampered_preflight = dict(preflight)
            tampered_preflight["owner_focus"] = "CHANGED_AFTER_RECEIPT"
            with self.assertRaisesRegex(
                HficSessionError, "PREFLIGHT_RECEIPT_HASH_MISMATCH"
            ):
                persist_generated_draft(
                    store,
                    draft,
                    preflight_receipt=tampered_preflight,
                    repo_root=ROOT,
                    model_provenance_sha256="11" * 32,
                )
            self.assertEqual(
                store.diagnostics().committed_inventory_sha256,
                inventory_before_invalid_receipt,
            )
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
            ):
                generated = persist_generated_draft(
                    store,
                    draft,
                    preflight_receipt=preflight,
                    repo_root=ROOT,
                    model_provenance_sha256="11" * 32,
                )
            store.rebuild_projection()
            self.assertEqual(generated.get("draft_lifecycle"), "GENERATED_BEFORE_FREEZE")
            self.assertEqual(len(list_scientific_slot_admissions(store)), 1)
            reloaded = ResearchStore(data_root, create_if_missing=False)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
            ):
                resumed_preflight = run_preflight(
                    ROOT,
                    data_root,
                    owner_focus="AUTO",
                    auto_commission=False,
                    git_snapshot=_git_snapshot(),
                    clock=_CLOCK,
                    evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1,
                    persist=False,
                )
            self.assertEqual(resumed_preflight["action"], "RESUME_EXISTING_SESSION")
            self.assertEqual(
                resumed_preflight.get("generated_draft_sha256"),
                generated.get("payload_sha256"),
            )
            self.assertEqual(
                resumed_preflight.get("model_provenance_sha256"), "11" * 32
            )
            saved_draft = json.loads(str(generated["payload_canonical"]))
            frozen = freeze_draft(
                saved_draft,
                preflight_receipt=resumed_preflight,
                store=reloaded,
                repo_root=ROOT,
            )
            persist_frozen_session(
                reloaded,
                frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(saved_draft["candidates"]),
                draft=saved_draft,
            )
            reloaded.rebuild_projection()
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
            ):
                resumed = evaluate_forge_run(
                    ROOT,
                    data_root,
                    persist=False,
                    execution_context={"model_provenance_sha256": "11" * 32},
                )
                drifted = evaluate_forge_run(
                    ROOT,
                    data_root,
                    persist=False,
                    execution_context={"model_provenance_sha256": "22" * 32},
                )
        self.assertEqual(
            resumed["next_action"],
            ACTION_RESUME_BASE,
            json.dumps(
                {
                    "blocking_reason_codes": resumed.get("blocking_reason_codes"),
                    "scientific_identity_status": resumed.get(
                        "scientific_identity_status"
                    ),
                    "stages": resumed.get("stages"),
                },
                sort_keys=True,
            ),
        )
        self.assertEqual(drifted["next_action"], ACTION_OBSERVABILITY_BLOCKED)
        self.assertIn(
            "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING",
            drifted["blocking_reason_codes"],
        )
        self.assertEqual(drifted["writes"]["session"], 0)

    def test_g11_v1_freeze_rejects_changed_execution_binding_without_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = _no_worthy_base(data_root, store, production_preflight=True)
            v1_pre, _envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(base["session_id"]),
                model_provenance_sha256="11" * 32,
            )
            draft = _fresh_v12_draft(v1_pre)
            frozen = freeze_draft(
                draft,
                preflight_receipt=v1_pre,
                store=store,
                repo_root=ROOT,
            )
            persist_frozen_session(
                store,
                frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(draft["candidates"]),
                draft=draft,
            )
            store.rebuild_projection()
            before = store.diagnostics().committed_inventory_sha256
            changed, _changed_envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(base["session_id"]),
                model_provenance_sha256="22" * 32,
            )
            with self.assertRaisesRegex(
                HficSessionError,
                "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING",
            ):
                freeze_draft(
                    draft,
                    preflight_receipt=changed,
                    store=store,
                    repo_root=ROOT,
                )
            self.assertEqual(
                store.diagnostics().committed_inventory_sha256,
                before,
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

            store = ResearchStore(data_root)
            model_provenance = "11" * 32
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
                draft = _fresh_v12_draft(preflight)
                generated = persist_generated_draft(
                    store,
                    draft,
                    preflight_receipt=preflight,
                    repo_root=ROOT,
                    model_provenance_sha256=model_provenance,
                )
            draft_sha = str(generated["payload_sha256"])
            self.assertEqual(generated["model_provenance_sha256"], model_provenance)
            self.assertEqual(
                generated["capability_epoch_sha256"],
                preflight["capability_epoch_sha256"],
            )
            generated_records = list(store.iter_committed_records())
            reservation_record = next(
                row
                for row in generated_records
                if row.record_id.startswith("HFIC-ART-SLOT-ADMISSION-")
            )
            draft_record = next(
                row
                for row in generated_records
                if json.loads(row.payload_json).get("artifact_kind")
                == "FORGE_DRAFT"
            )
            self.assertEqual(
                reservation_record.transaction_id, draft_record.transaction_id
            )
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
                resumed_preflight.get("model_provenance_sha256"), model_provenance
            )
            self.assertEqual(
                resumed_preflight["writes"],
                {"research_store": 0, "forge_context": 0, "session": 0},
            )

            from solana_alpha_lab.factory.hfic_preflight import decide_preflight_action

            drifted_action = decide_preflight_action(
                [],
                search_key=str(preflight["search_key_sha256"]),
                evidence_epoch=str(preflight["market_evidence_epoch_sha256"]),
                focus_key=str(preflight["focus_key_sha256"]),
                owner_focus="AUTO",
                memory_eligibility_sha256=str(
                    preflight["memory_eligibility_sha256"]
                ),
                representation_id="BASE",
                representation_semantic_version="HFIC-V1.2",
                reservations=admissions,
                generated_draft=generated,
                current_visible_cohort_ids=list(
                    preflight.get("visible_cohort_ids") or []
                ),
                execution_context={"capability_epoch_sha256": "ff" * 32},
                repo_root=ROOT,
            )
            self.assertEqual(
                drifted_action,
                ("STOP", "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING"),
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
            changed["candidates"] = [dict(card) for card in draft["candidates"]]
            changed["candidates"][0]["claim"] = (
                "Different generator bytes for the same preflight focus."
            )
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production,
            ):
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
                side_effect=_enumerate_production_fixture,
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
            base = _no_worthy_base(data_root, store, production_preflight=True)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
            ):
                evaluate_forge_run(ROOT, data_root, persist=False)
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
                side_effect=_enumerate_production_fixture,
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
            _no_worthy_base(data_root, store, production_preflight=True)
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
                side_effect=_enumerate_production_fixture,
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
                side_effect=_enumerate_production_fixture,
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
            # Capability drift keeps the market/run identity but invalidates
            # current reuse.  The occupied slot must stop before a new trial.
            self.assertEqual(again["next_action"], "OBSERVABILITY_BLOCKED")
            self.assertIn(
                "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING",
                again["blocking_reason_codes"],
            )
            self.assertEqual(again["writes"]["research_store"], 0)

    def test_g6_interruption_resume_keeps_draft_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = _no_worthy_base(data_root, store, production_preflight=True)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
            ):
                started = evaluate_forge_run(ROOT, data_root, persist=True)
            v1_pre, _envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(base["session_id"]),
            )
            draft = _fresh_v12_draft(v1_pre)
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
                side_effect=_enumerate_production_fixture,
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
                side_effect=_enumerate_production_fixture,
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
            base = _no_worthy_base(data_root, store, production_preflight=True)
            draft = _distinct_no_worthy_draft(label="V1")
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
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
                side_effect=_enumerate_production_fixture,
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
                    side_effect=_enumerate_production_fixture,
                ):
                    finished = evaluate_forge_run(
                        ROOT, data_root, persist=False, registry=registry
                    )
            self.assertEqual(finished["next_action"], "OBSERVABILITY_BLOCKED")
            self.assertIn(
                "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING",
                finished["blocking_reason_codes"],
            )
            self.assertEqual(
                finished["market_evidence_epoch_sha256"],
                started["market_evidence_epoch_sha256"],
            )
            self.assertEqual(finished["writes"]["research_store"], 0)

    def test_g1_g5_two_worktrees_share_market_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            principal = Path(tmp) / "principal"
            linked = Path(tmp) / "linked"
            # Keep Git metadata inside the disposable test directory.  The
            # real checkout may be sandboxed against worktree-admin writes.
            _git(ROOT, "clone", "--no-local", str(ROOT), str(principal))
            # A detached source clone has HEAD but no refs/heads entry.
            # for-each-ref then looks empty and the write fence fails closed.
            _git(principal, "checkout", "-B", "a5-ci-snapshot")
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
                    side_effect=_enumerate_production_fixture,
                ):
                    from_a = build_forge_input_receipt(data_root, repo_root=principal)
                    from_b = build_forge_input_receipt(data_root, repo_root=linked)
                self.assertEqual(
                    from_a["market_evidence_epoch_sha256"],
                    from_b["market_evidence_epoch_sha256"],
                )
                base = _no_worthy_base(
                    data_root, store, production_preflight=True, repo_root=principal
                )
                with patch(
                    "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                    side_effect=_enumerate_production_fixture,
                ):
                    started = evaluate_forge_run(principal, data_root, persist=True)
                self.assertEqual(started["next_action"], ACTION_START_V1)
                # Linked worktree / fresh store handle: completed BASE still
                # answers without minting a second CONTROL on same market.
                store_b = ResearchStore(data_root)
                with patch(
                    "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                    side_effect=_enumerate_production_fixture,
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
            frozen = _no_worthy_base(data_root, store, production_preflight=True)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
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

    def test_g8_production_import_c3_changes_current_market_after_completed_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_root = base / "rdp"
            data_root.mkdir()
            release_c1, _, _ = _seal_week(base, 0)
            release_c2, _, _ = _seal_week(base, 1)
            release_c3, _, _ = _seal_week(base, 2)
            import_live_cohort(
                release_root=release_c1,
                data_root=data_root,
                import_time=datetime(2026, 1, 20, tzinfo=UTC),
            )
            import_live_cohort(
                release_root=release_c2,
                data_root=data_root,
                import_time=datetime(2026, 1, 27, tzinfo=UTC),
            )
            store = ResearchStore(data_root)
            preflight = _run_production_preflight(
                data_root,
                enumerator=_enumerate_imported_control_fixture,
                model_provenance_sha256="11" * 32,
            )
            self.assertEqual(preflight["action"], "START_NEW_SESSION")
            frozen = _ordinary_pass_base(data_root, store, preflight=preflight)
            store.rebuild_projection()
            old_bundle = load_session_bundle(store, str(frozen["session_id"]))
            assert old_bundle is not None
            self.assertEqual(old_bundle.get("session_state"), "SYNTHESIS_COMPLETE")
            self.assertEqual(
                (old_bundle.get("critic_result") or {}).get("critic_terminal"),
                "PASS_FAST_LANE_READY",
            )
            old_market = str(preflight["market_evidence_epoch_sha256"])

            imported = import_live_cohort(
                release_root=release_c3,
                data_root=data_root,
                import_time=datetime(2026, 2, 3, tzinfo=UTC),
            )
            self.assertEqual(imported["status"], "IMPORTED")
            from tests.test_hfic_cli import run_cli

            after_process = run_cli(
                "forge-run", "--no-write", "--format", "json", data_root=data_root
            )
            self.assertEqual(after_process.returncode, 0, after_process.stderr)
            after = json.loads(after_process.stdout)
            self.assertNotEqual(
                after["market_evidence_epoch_sha256"], old_market
            )
            self.assertNotEqual(after["stages"][0]["execution_status"], EXEC_REUSED)
            self.assertEqual(after["next_action"], ACTION_START_BASE)
            self.assertNotIn("RETURN_EXISTING_RUN", after["owner_readout"])
            self.assertIn("START_BASE", after["owner_readout"])
            self.assertEqual(len(list_hfic_sessions(ResearchStore(data_root))), 1)

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
                side_effect=_enumerate_production_fixture,
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
                side_effect=_enumerate_production_fixture,
            ):
                before = build_forge_input_receipt(data_root, repo_root=ROOT)
            _no_worthy_base(data_root, store, production_preflight=True)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
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
            base = _no_worthy_base(data_root, store, production_preflight=True)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
            ):
                before = evaluate_forge_run(ROOT, data_root, persist=True)
            exported = export_snapshot(data_root, snap)
            restore_snapshot(exported.snapshot_root, restore_root)
            # Snapshot owns ResearchStore bytes. Gold reconstitutes the same
            # fixture lineage used at export (not a second scientific look).
            _write_lineage(restore_root)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
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
