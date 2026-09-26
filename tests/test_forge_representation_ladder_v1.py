"""A4 representation ladder: deterministic transitions, run receipt, no-write compatibility.

Does not execute Prompt A/B/C, Independent Critic, or the scientific V1 probe.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.data_root import (  # noqa: E402
    instance_fingerprint,
    resolve_data_root,
    resolve_existing_data_root,
)
from solana_alpha_lab.factory.document_runner import repository_git_snapshot  # noqa: E402
from solana_alpha_lab.factory.hfic_identity import assign_portfolio_ids  # noqa: E402
from solana_alpha_lab.factory.hfic_evidence_identity import (  # noqa: E402
    compute_split_identity,
)
from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    RUNNER_UP_AWAITING_CRITIC,
    HficSessionError,
    apply_classification,
    canonical_preflight_receipt_sha256,
    focus_key_sha256,
    find_session_by_epoch_focus,
    freeze_draft,
    list_hfic_sessions,
    persist_frozen_session,
    persist_no_worthy_session,
    finalize_session,
    load_session_bundle,
)
from solana_alpha_lab.factory.hfic_representation_probe import (  # noqa: E402
    CONTROL_CONTEXT_KIND_FORGE,
    control_baseline_from_receipt,
    control_memory_baseline_sha256,
)
from solana_alpha_lab.factory.normalized_trajectory_v1 import (  # noqa: E402
    DEFAULT_SCHEDULE,
    LifecycleCorpusBinding,
    LifecycleSchedule,
    TypedLifecycleObservation,
    project_normalized_trajectory,
)
from solana_alpha_lab.factory.forge_input_receipt import (  # noqa: E402
    OWNER_CLASS_INPUT_NOT_READY,
    OWNER_CLASS_OBSERVABILITY_BLOCKED,
)
from solana_alpha_lab.factory.hfic_control_integrity import (  # noqa: E402
    CASE_A_TERMINALS,
    CURRENT_REPRESENTATION_CONTROL_V1,
)
from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    is_fast_lane_commissioned,
    persist_forge_context_packet,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402
from solana_alpha_lab.factory.run_passport import canonical_sha256  # noqa: E402
from solana_alpha_lab.factory.hfic_evidence_identity import (  # noqa: E402
    execution_binding_sha256,
)
from solana_alpha_lab.factory.hfic_representation_ladder import (  # noqa: E402
    ACTION_CONTROL_REQUIRED,
    ACTION_FINISH_RUNNER_UP,
    ACTION_KEEP_PAUSE,
    ACTION_NON_SCIENTIFIC_STOP,
    ACTION_OBSERVABILITY_BLOCKED,
    ACTION_OWNER_CANDIDATE,
    ACTION_RESUME_BASE,
    ACTION_RESUME_V1,
    ACTION_RETURN_EXISTING,
    ACTION_SEARCH_EXHAUSTED,
    ACTION_START_BASE,
    ACTION_START_V1,
    EXEC_BLOCKED,
    EXEC_EXECUTED,
    EXEC_NOT_RUN,
    EXEC_PROVENANCE_CONFLICT,
    EXEC_PROVENANCE_HISTORICAL_UNKNOWN,
    EXEC_PROVENANCE_VERIFIED,
    EXEC_REUSED,
    EXISTING_V1_CONTROL_SESSION_ID,
    HANDLER_SYNTHETIC_LATER_V2,
    LadderError,
    PASS_TERMINALS,
    consume_start_v1_envelope,
    control_preflight_from_bundle,
    evaluate_forge_run,
    _execution_provenance_status,
    format_forge_run_owner_readout,
    load_ladder_registry,
    prepare_ladder_freeze_preflight,
    attach_ladder_freeze_preflight,
    resolve_next_action,
    _packet_for_bundle,
)

from tests.test_forge_input_truth_and_visibility_v1 import (  # noqa: E402
    _enumerate_live,
    _write_lineage,
)
from tests.test_hfic_representation_probe import (  # noqa: E402
    _cohort_readiness_receipt,
    _control_receipt,
    _representation_fixture,
    build_challenger_packet,
    existing_hfic_lifecycle_fixture_input,
    existing_hfic_packet,
)
from tests.test_normalized_trajectory_v1_execution_closure_v1 import (  # noqa: E402
    _no_worthy_forge_receipt,
)
from tests.test_hfic_session import (  # noqa: E402
    critic_result_from_packet_only,
    finalize_kill_complete,
    valid_draft,
)


def _submission_for_frozen(frozen: Mapping[str, object]) -> dict[str, object]:
    """Classifier packet grounded to the frozen candidate's required features."""

    from tests.test_fast_lane_classifier import submission

    packet = submission()
    spec = dict(packet["experiment_spec"])
    critic = frozen.get("critic_input_packet")
    selected = critic.get("selected_candidate") if isinstance(critic, Mapping) else None
    feats = list(selected.get("required_feature_ids") or []) if isinstance(selected, Mapping) else []
    if feats:
        spec["required_feature_ids"] = feats
    bound = dict(packet)
    bound["experiment_spec"] = spec
    bound["hypothesis_definition_sha256"] = frozen["selected_definition_sha256"]
    return bound


def _current_v12_draft(preflight: Mapping[str, object] | None = None) -> dict[str, object]:
    """Fresh HFIC-V1.2 generator reply. V1.1 ``valid_draft()`` stays historical."""

    draft = json.loads(
        (ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text(
            encoding="utf-8"
        )
    )
    if preflight is None:
        return draft
    from tests.test_hfic_cli import bind_draft

    return bind_draft(draft, preflight)

NO_WORTHY_DRAFT = ROOT / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1.json"


def _load_hypothesis_forge_cli():
    spec = importlib.util.spec_from_file_location(
        "hypothesis_forge_cli_a4", ROOT / "scripts" / "hypothesis_forge.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _control_preflight(
    data_root: Path,
    store: ResearchStore,
    *,
    repo_root: Path = ROOT,
) -> dict[str, object]:
    """CONTROL preflight through the production packet/identity writer.

    These tests exercise lifecycle boundaries, so they must carry the same
    market/capability split and cohort binding as the real entry path. Legacy
    combined-only receipts belong in explicit historical-disposition tests.
    """

    return _production_control_preflight(data_root, store, repo_root=repo_root)


def _production_control_preflight(
    data_root: Path,
    store: ResearchStore,
    *,
    evidence_surface_mode: str | None = CURRENT_REPRESENTATION_CONTROL_V1,
    repo_root: Path = ROOT,
) -> dict[str, object]:
    """Normal CONTROL packet via production writer (G1 acceptance path)."""

    from solana_alpha_lab.factory.hfic_preflight import build_forge_context_packet
    from solana_alpha_lab.factory.hfic_memory_policy import effective_policy
    from solana_alpha_lab.factory.hfic_session import (
        PROMPT_VERSION,
        focus_key_sha256,
        search_key_sha256,
    )

    def _enumerate_production(_root: Path, **_kwargs: object):
        # Fixture enumerate returns thin rows; stamp the same evidence_role /
        # feature fields real enumerate_rdp_datasets emits so the production
        # packet writer is exercised without replacing it.
        live, warnings = _enumerate_live(_root)
        enriched: list[dict[str, object]] = []
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

    git = repository_git_snapshot(repo_root)
    from solana_alpha_lab.factory.hfic_evidence_identity import compute_split_identity

    with patch(
        "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
        side_effect=_enumerate_production,
    ):
        from solana_alpha_lab.factory.forge_input_receipt import (
            build_forge_input_receipt,
        )
        split = compute_split_identity(repo_root, data_root)
        policy = effective_policy(store)
        market_epoch = str(split["market_evidence_epoch_sha256"])
        owner_focus = "AUTO"
        memory_eligibility = str(policy["memory_eligibility_sha256"])
        focus_key = focus_key_sha256(owner_focus)
        search_key = search_key_sha256(
            market_epoch,
            owner_focus,
            PROMPT_VERSION,
            memory_eligibility,
            evidence_surface_mode,
        )
        packet, digest = build_forge_context_packet(
            repo_root,
            data_root,
            owner_focus=owner_focus,
            evidence_epoch=market_epoch,
            search_key=search_key,
            commissioning_status="FAST_LANE_COMMISSIONED",
            research_memory_as_of="2026-09-16T12:00:00Z",
            store=store,
            persist=True,
            evidence_surface_mode=evidence_surface_mode,
        )
        forge_input = build_forge_input_receipt(
            data_root,
            repo_root=repo_root,
            evidence_surface_mode=evidence_surface_mode,
            owner_focus=owner_focus,
        )
    result: dict[str, object] = {
        "receipt_id": "HFIC-PREFLIGHT-PRODUCTION-001",
        "evidence_epoch_sha256": market_epoch,
        "focus_key_sha256": focus_key,
        "search_key_sha256": search_key,
        "owner_focus": owner_focus,
        "live_git_head": git.head_sha.lower(),
        "git_composite_sha256": git.composite_sha256,
        "session_started_at": "2026-08-27T12:00:00Z",
        "memory_eligibility_sha256": memory_eligibility,
        "forge_context_packet_sha256": digest,
        "forge_context_packet": packet,
        "forge_input_receipt": forge_input,
        # Same production split axes as run_preflight / forge-input admission.
        "market_evidence_epoch_sha256": split["market_evidence_epoch_sha256"],
        "capability_epoch_sha256": split["capability_epoch_sha256"],
        "legacy_combined_evidence_epoch_sha256": split[
            "legacy_combined_evidence_epoch_sha256"
        ],
    }
    if evidence_surface_mode is not None:
        result["evidence_surface_mode"] = evidence_surface_mode
    return result


def _ordinary_stamped_preflight(
    data_root: Path, store: ResearchStore, *, repo_root: Path = ROOT
) -> dict[str, object]:
    """Production split identity with the ordinary (non-CONTROL) surface."""

    return _production_control_preflight(
        data_root, store, evidence_surface_mode=None, repo_root=repo_root
    )


def _rel_c2_corpus_binding() -> LifecycleCorpusBinding:
    """Release-local V1 binding: same schedule geometry, cohort REL-C2 only."""

    base = DEFAULT_SCHEDULE.corpus_binding
    assert base is not None
    values = base.as_dict()
    return LifecycleCorpusBinding(
        release_id=values["release_id"],
        cohort_id="REL-C2",
        schedule_sha256=values["schedule_sha256"],
        activation_id=values["activation_id"],
        producer_git_sha=values["producer_git_sha"],
        source_sha256=values["source_sha256"],
        census_sha256=values["census_sha256"],
        observations_sha256=values["observations_sha256"],
    )


def _representation_fixture_rel_c2():
    binding = _rel_c2_corpus_binding()
    schedule = LifecycleSchedule(
        schedule_sha256=binding.schedule_sha256,
        activation_id=binding.activation_id,
        corpus_binding=binding,
    )
    anchor = datetime(2026, 1, 1, tzinfo=UTC)
    rows: list[TypedLifecycleObservation] = []
    for index in range(10):
        member = f"synthetic-{index}"
        for field, values in (
            ("FIELD-USD-PRICE-001", (1.0, 2.0, 3.0)),
            ("FIELD-LIQUIDITY-USD-001", (1000.0, 1000.0, 1000.0)),
            ("FIELD-STATS5M-NUM-TRADERS-001", (1.0, 1.0, 1.0)),
        ):
            for due, value in zip(schedule.prefix_due_offsets, values, strict=True):
                rows.append(
                    TypedLifecycleObservation(
                        member_id=member,
                        member_anchor_at=anchor,
                        due_offset_seconds=due,
                        field_id=field,
                        value=value,
                        first_reliable_available_at=anchor + timedelta(seconds=due),
                        schedule_sha256=schedule.schedule_sha256,
                        activation_id=schedule.activation_id,
                    )
                )
    return project_normalized_trajectory(rows, schedule=schedule)


def _cohort_readiness_receipt_rel_c2(**kwargs: object) -> dict[str, object]:
    from solana_alpha_lab.factory.hfic_representation_probe import (
        cohort_readiness_receipt_from_release_manifest,
    )

    receipt = _cohort_readiness_receipt(**kwargs)
    manifest = dict(receipt["release_manifest"])
    binding = _rel_c2_corpus_binding().as_dict()
    for key, value in binding.items():
        manifest[key] = value
    return cohort_readiness_receipt_from_release_manifest(manifest)


def _forge_control_receipt_from_preflight(
    preflight: Mapping[str, object],
    *,
    session_id: str,
    terminal: str = "NO_WORTHY_HYPOTHESIS",
) -> dict[str, object]:
    """Probe-compatible CONTROL receipt bound to the exact freeze preflight packet."""

    packet = dict(preflight.get("forge_context_packet") or {})
    digest = preflight.get("forge_context_packet_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        digest = canonical_sha256(packet)
    session_receipt: dict[str, object] = {
        "session_id": session_id,
        "session_state": "SYNTHESIS_COMPLETE",
        "evidence_epoch_sha256": preflight.get("evidence_epoch_sha256"),
        "focus_key_sha256": preflight.get("focus_key_sha256"),
        "search_key_sha256": preflight.get("search_key_sha256"),
        "prompt_version": "HFIC-V1.2",
        "critic_input_packet_sha256": None,
        "forge_context_packet_sha256": digest,
        "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
        "final_session_terminal": terminal,
        "critic_terminal": terminal,
        "effective_control_terminal": terminal,
    }
    receipt: dict[str, object] = {
        "session_id": session_id,
        "critic_input_packet": None,
        "critic_input_packet_sha256": None,
        "forge_context_packet": packet,
        "forge_context_packet_sha256": digest,
        "evidence_epoch_sha256": preflight.get("evidence_epoch_sha256"),
        "focus_key_sha256": preflight.get("focus_key_sha256"),
        "search_key_sha256": preflight.get("search_key_sha256"),
        "prompt_version": "HFIC-V1.2",
        "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
        "final_session_terminal": terminal,
        "critic_terminal": terminal,
        "effective_control_terminal": terminal,
        "session_receipt": session_receipt,
    }
    receipt["memory_baseline_sha256"] = control_memory_baseline_sha256(receipt)
    return receipt


def _v1_freeze_preflight_from_envelope(
    data_root: Path,
    store: ResearchStore,
    *,
    control_session_id: str,
    control_preflight: Mapping[str, object] | None = None,
    repo_root: Path = ROOT,
    model_provenance_sha256: str | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    """Envelope → representation-aware freeze preflight (production binding path).

    Builds the challenger from the same CONTROL packet used for freeze. Does not
    patch parent or used scope after build.
    """

    if control_preflight is None:
        bundle = load_session_bundle(store, control_session_id)
        if bundle is not None:
            packet_loaded = _packet_for_bundle(data_root, bundle, store)
            control = control_preflight_from_bundle(bundle, packet_loaded)
        else:
            # Disposable orphan-parent probes may name a non-persisted CONTROL id.
            control = _control_preflight(data_root, store, repo_root=repo_root)
    else:
        control = dict(control_preflight)
    control_receipt = _forge_control_receipt_from_preflight(
        control, session_id=control_session_id
    )
    representation = _representation_fixture_rel_c2()
    readiness = _cohort_readiness_receipt_rel_c2()
    envelope = consume_start_v1_envelope(
        {"next_action": ACTION_START_V1, "owner_final": None},
        control_receipt=control_receipt,
        representation=representation,
        cohort_readiness_receipt=readiness,
        base_x_population_n=10,
    )
    challenger = envelope["challenger"]
    assert isinstance(challenger, Mapping)
    parent = str(envelope.get("control_session_id") or challenger.get("control_session_id"))
    assert parent == control_session_id
    v1_pre = prepare_ladder_freeze_preflight(
        control,
        representation_id="NORMALIZED_TRAJECTORY_V1",
        control_session_id=parent,
        challenger=challenger,
        control_receipt=control_receipt,
        model_provenance_sha256=model_provenance_sha256,
    )
    packet = v1_pre["forge_context_packet"]
    assert isinstance(packet, dict)
    # Production embed owns release-local scope; do not assign after build.
    assert packet.get("bound_visible_cohort_ids") == ["REL-C2"]
    digest = persist_forge_context_packet(
        data_root, packet, store=store, repo_root=repo_root
    )
    v1_pre["forge_context_packet_sha256"] = digest
    v1_pre["preflight_receipt_sha256"] = canonical_preflight_receipt_sha256(v1_pre)
    return v1_pre, envelope


def _git(cwd: Path, *args: str) -> None:
    subprocess.check_call(["git", *args], cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "a4@test")
    _git(path, "config", "user.name", "a4")
    (path / "README.md").write_text("a4\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "init")


def _base(**kwargs: object) -> dict[str, object]:
    row: dict[str, object] = {
        "representation_id": "BASE",
        "execution_status": EXEC_REUSED,
        "effective_terminal": "NO_WORTHY_HYPOTHESIS",
        "input_scope": CURRENT_REPRESENTATION_CONTROL_V1,
        "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
        "session_state": "SYNTHESIS_COMPLETE",
        "used_cohort_ids": ["REL-C1", "REL-C2"],
    }
    row.update(kwargs)
    return row


def _v1(**kwargs: object) -> dict[str, object]:
    row: dict[str, object] = {
        "representation_id": "NORMALIZED_TRAJECTORY_V1",
        "execution_status": EXEC_NOT_RUN,
        "effective_terminal": None,
        "input_scope": "REPRESENTATION_RELEASE_LOCAL",
        "used_cohort_ids": ["REL-C2"],
    }
    row.update(kwargs)
    return row


def _provenance_status(**overrides: str | None) -> str:
    slot = "aa" * 32
    parent = "HFIC-SESS-BASE"
    fields = {
        "capability_epoch_sha256": "11" * 32,
        "representation_payload_sha256": "33" * 32,
        "memory_eligibility_sha256": "44" * 32,
        "model_provenance_sha256": "55" * 32,
    }
    binding = execution_binding_sha256(
        scientific_slot_sha256=slot,
        control_session_id=parent,
        **fields,
    )
    packet = {"control_session_id": parent, **fields}
    receipt = {"control_session_id": parent, **fields}
    bundle = {
        "control_session_id": parent,
        "execution_binding_sha256": binding,
        **fields,
    }
    if "control_session_id" in overrides:
        packet["control_session_id"] = overrides.pop("control_session_id")
    for key, value in overrides.items():
        if value is None:
            packet.pop(key, None)
            receipt.pop(key, None)
            bundle.pop(key, None)
        else:
            packet[key] = value
    return _execution_provenance_status(
        bundle,
        receipt=receipt,
        packet=packet,
        scientific_slot_sha256=slot,
        stored_binding=binding,
        execution_status=EXEC_EXECUTED,
    )


class ResolveNextActionTests(unittest.TestCase):
    def test_positive_base_candidate_skips_v1(self) -> None:
        decision = resolve_next_action(
            [
                _base(
                    effective_terminal="PASS_FAST_LANE_READY",
                    selected_candidate_id="HFIC-CAND-SYNTH-ALPHA",
                )
            ]
        )
        self.assertEqual(decision["next_action"], ACTION_OWNER_CANDIDATE)
        self.assertEqual(decision["owner_final"], ACTION_OWNER_CANDIDATE)

    def test_base_empty_auto_starts_v1_on_control(self) -> None:
        decision = resolve_next_action([_base()])
        self.assertEqual(decision["next_action"], ACTION_START_V1)
        self.assertIsNone(decision["owner_final"])

    def test_ordinary_no_worthy_requires_control_surface_start_base(self) -> None:
        decision = resolve_next_action(
            [_base(evidence_surface_mode=None, input_scope="ORDINARY_BASE")]
        )
        self.assertEqual(decision["next_action"], ACTION_START_BASE)
        self.assertIsNone(decision["owner_final"])
        self.assertEqual(decision["reason_code"], "CONTROL_SURFACE_REQUIRED")
        self.assertEqual(
            decision.get("base_evidence_surface_mode"),
            CURRENT_REPRESENTATION_CONTROL_V1,
        )

    def test_v1_scientific_negative_is_scoped_exhaustion(self) -> None:
        decision = resolve_next_action(
            [
                _base(),
                _v1(
                    execution_status=EXEC_EXECUTED,
                    effective_terminal="NO_WORTHY_HYPOTHESIS",
                    stage_ref_sha256="aa" * 32,
                ),
            ]
        )
        self.assertEqual(decision["next_action"], ACTION_SEARCH_EXHAUSTED)
        self.assertEqual(decision["owner_final"], ACTION_SEARCH_EXHAUSTED)

    def test_v1_visibility_is_observability_not_scientific_negative(self) -> None:
        decision = resolve_next_action(
            [
                _base(),
                _v1(
                    execution_status=EXEC_BLOCKED,
                    reason_code="FORGE_VISION_INTEGRITY_BLOCKED",
                ),
            ]
        )
        self.assertEqual(decision["next_action"], ACTION_OBSERVABILITY_BLOCKED)
        self.assertNotEqual(decision["owner_final"], ACTION_SEARCH_EXHAUSTED)

    def test_runner_up_pending_blocks_early_v1(self) -> None:
        decision = resolve_next_action(
            [
                _base(
                    effective_terminal="KILL_MECHANISM",
                    session_state=RUNNER_UP_AWAITING_CRITIC,
                    execution_status=EXEC_EXECUTED,
                )
            ]
        )
        self.assertEqual(decision["next_action"], ACTION_FINISH_RUNNER_UP)
        self.assertNotEqual(decision["next_action"], ACTION_START_V1)

    def test_runner_up_pause_keeps_pause(self) -> None:
        decision = resolve_next_action(
            [_base(effective_terminal="RUNNER_UP_REVISION_REQUIRED")]
        )
        self.assertEqual(decision["next_action"], ACTION_KEEP_PAUSE)
        self.assertIsNone(decision["owner_final"])

    def test_frozen_awaiting_critic_resumes_base(self) -> None:
        decision = resolve_next_action(
            [
                _base(
                    effective_terminal=None,
                    session_state="FROZEN_AWAITING_CRITIC",
                    execution_status=EXEC_EXECUTED,
                    draft_sha256="ab" * 32,
                )
            ]
        )
        self.assertEqual(decision["next_action"], ACTION_RESUME_BASE)
        self.assertEqual(decision["draft_sha256"], "ab" * 32)

    def test_critic_result_ready_resumes_base_not_keep_pause(self) -> None:
        for state in (
            "CRITIC_RESULT_READY",
            "REVISION_REQUIRED",
            "AWAITING_CLASSIFICATION",
        ):
            with self.subTest(state=state):
                decision = resolve_next_action(
                    [
                        _base(
                            effective_terminal=None,
                            session_state=state,
                            execution_status=EXEC_EXECUTED,
                        )
                    ]
                )
                self.assertEqual(decision["next_action"], ACTION_RESUME_BASE)
                self.assertIsNone(decision["owner_final"])
                self.assertNotEqual(decision["next_action"], ACTION_KEEP_PAUSE)

    def test_base_missing_terminal_is_observability(self) -> None:
        decision = resolve_next_action(
            [
                _base(
                    effective_terminal=None,
                    session_state="SYNTHESIS_COMPLETE",
                    execution_status=EXEC_EXECUTED,
                )
            ]
        )
        self.assertEqual(decision["next_action"], ACTION_OBSERVABILITY_BLOCKED)
        self.assertEqual(decision["reason_code"], "BASE_TERMINAL_MISSING")
        self.assertNotEqual(decision["next_action"], ACTION_SEARCH_EXHAUSTED)

    def test_keep_pause_readout_is_not_done(self) -> None:
        text = format_forge_run_owner_readout(
            {
                "run_id": "FORGE-RUN-TEST",
                "owner_class": "FORGE_RUN_IN_PROGRESS",
                "next_action": ACTION_KEEP_PAUSE,
                "owner_final": None,
                "stages": [],
                "writes": {"research_store": 0, "forge_run": 0, "session": 0},
                "blocking_reason_codes": [],
            }
        )
        self.assertIn("status: NEXT", text)
        self.assertNotIn("status: DONE", text)

    def test_control_surface_required_readout_is_next_not_evening_done(self) -> None:
        text = format_forge_run_owner_readout(
            {
                "run_id": "FORGE-RUN-TEST",
                "owner_class": "FORGE_RUN_IN_PROGRESS",
                "next_action": ACTION_START_BASE,
                "owner_final": None,
                "stages": [],
                "writes": {"research_store": 0, "forge_run": 0, "session": 0},
                "blocking_reason_codes": ["CONTROL_SURFACE_REQUIRED"],
            }
        )
        self.assertIn("status: NEXT", text)
        self.assertIn("CONTROL-compatible BASE", text)
        self.assertIn("/hypothesis-forge CURRENT_REPRESENTATION_CONTROL", text)
        self.assertNotIn("status: DONE", text)
        self.assertNotIn("STOP_BEFORE_SYNTHESIS", text)

    def test_no_write_control_required_readout_is_not_slash_authority(self) -> None:
        text = format_forge_run_owner_readout(
            {
                "run_id": "FORGE-RUN-TEST",
                "owner_class": "FORGE_RUN_IN_PROGRESS",
                "next_action": ACTION_START_BASE,
                "owner_final": None,
                "stages": [],
                "writes": {"research_store": 0, "forge_run": 0, "session": 0},
                "blocking_reason_codes": ["CONTROL_SURFACE_REQUIRED"],
                "no_write": True,
            }
        )
        self.assertIn("START_BASE", text)
        self.assertIn("CONTROL_SURFACE_REQUIRED", text)
        self.assertIn("next: STOP_BEFORE_SYNTHESIS", text)
        self.assertNotIn("/hypothesis-forge", text)
        self.assertNotIn("CONTROL_ENTRY", text)

    def test_authorized_control_required_readout_keeps_slash_action(self) -> None:
        text = format_forge_run_owner_readout(
            {
                "run_id": "FORGE-RUN-TEST",
                "owner_class": "FORGE_RUN_IN_PROGRESS",
                "next_action": ACTION_START_BASE,
                "owner_final": None,
                "stages": [],
                "writes": {"research_store": 0, "forge_run": 0, "session": 0},
                "blocking_reason_codes": ["CONTROL_SURFACE_REQUIRED"],
                "no_write": False,
            }
        )
        self.assertIn("CONTROL-compatible BASE", text)
        self.assertIn("next: CONTROL_ENTRY", text)
        self.assertIn("/hypothesis-forge CURRENT_REPRESENTATION_CONTROL", text)
        self.assertNotIn("STOP_BEFORE_SYNTHESIS", text)

    def test_known_hash_mismatch_is_execution_binding_conflict(self) -> None:
        fields = (
            "capability_epoch_sha256",
            "representation_payload_sha256",
            "memory_eligibility_sha256",
            "model_provenance_sha256",
        )
        for key in fields:
            with self.subTest(key=key):
                status = _provenance_status(**{key: "22" * 32})
                self.assertEqual(status, EXEC_PROVENANCE_CONFLICT)

    def test_differing_control_session_id_is_conflict(self) -> None:
        self.assertEqual(
            _provenance_status(control_session_id="HFIC-SESS-OTHER"),
            EXEC_PROVENANCE_CONFLICT,
        )

    def test_missing_historical_hash_is_not_a_false_conflict(self) -> None:
        self.assertEqual(
            _provenance_status(model_provenance_sha256=None),
            EXEC_PROVENANCE_HISTORICAL_UNKNOWN,
        )

    def test_matching_known_provenance_stays_verified(self) -> None:
        self.assertEqual(_provenance_status(), EXEC_PROVENANCE_VERIFIED)

    def test_occupied_slot_readback_block_has_owner_recovery_next(self) -> None:
        text = format_forge_run_owner_readout(
            {
                "run_id": "FORGE-RUN-TEST",
                "session_id": "HFIC-SESS-OCCUPIED-READBACK",
                "owner_class": ACTION_OBSERVABILITY_BLOCKED,
                "next_action": ACTION_OBSERVABILITY_BLOCKED,
                "owner_final": ACTION_OBSERVABILITY_BLOCKED,
                "stages": [],
                "writes": {"research_store": 0, "forge_run": 0, "session": 0},
                "blocking_reason_codes": ["SCIENTIFIC_SLOT_OCCUPIED_READBACK_MISSING"],
            }
        )
        self.assertIn("occupied slot has no readable lifecycle row", text)
        self.assertIn("RECOVER_EXISTING_READBACK", text)
        self.assertIn(
            "show-session --session-id HFIC-SESS-OCCUPIED-READBACK --format json",
            text,
        )
        self.assertIn("do not rewrite receipts, regenerate, or reset budget", text)
        self.assertIn("Блокировка не является научным отрицательным результатом", text)
        self.assertIn(
            "uv run --locked --managed-python python -B scripts/hypothesis_forge.py show-session",
            text,
        )

    def test_execution_binding_conflict_has_exact_readback_recovery(self) -> None:
        text = format_forge_run_owner_readout(
            {
                "run_id": "FORGE-RUN-TEST",
                "session_id": "HFIC-SESS-IDENTITY-CONFLICT",
                "owner_class": ACTION_OBSERVABILITY_BLOCKED,
                "next_action": ACTION_OBSERVABILITY_BLOCKED,
                "owner_final": ACTION_OBSERVABILITY_BLOCKED,
                "stages": [],
                "writes": {"research_store": 0, "forge_run": 0, "session": 0},
                "blocking_reason_codes": [
                    "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING"
                ],
            }
        )
        self.assertIn("VERIFY_EXECUTION_COMPATIBILITY", text)
        self.assertIn(
            "show-session --session-id HFIC-SESS-IDENTITY-CONFLICT --format json",
            text,
        )
        self.assertIn("historical result remains occupied", text)
        self.assertIn("do not replay, regenerate, or reset budget", text)
        self.assertNotIn("start a new explicitly authorized /hypothesis-forge slash", text)

    def test_budget_exhaustion_is_final_stop_and_reports_all_read_only_counters(self) -> None:
        text = format_forge_run_owner_readout(
            {
                "run_id": "FORGE-RUN-TEST",
                "owner_class": ACTION_OBSERVABILITY_BLOCKED,
                "next_action": ACTION_OBSERVABILITY_BLOCKED,
                "owner_final": ACTION_OBSERVABILITY_BLOCKED,
                "stages": [],
                "writes": {"research_store": 0, "forge_run": 0, "session": 0},
                "blocking_reason_codes": ["SEARCH_BUDGET_EXHAUSTED"],
            }
        )
        self.assertIn("status: STOP", text)
        self.assertIn("Лимит поиска", text)
        self.assertIn("повторять", text)
        self.assertIn("writes: store=0 forge_run=0 session=0 forge_context=0", text)
        self.assertNotIn("восстановите указанное readback/evidence", text)

    def test_resume_readout_exposes_exact_draft_recovery_command(self) -> None:
        draft_sha = "ab" * 32
        text = format_forge_run_owner_readout(
            {
                "run_id": "FORGE-RUN-TEST",
                "owner_class": "FORGE_RUN_IN_PROGRESS",
                "next_action": ACTION_RESUME_V1,
                "owner_final": None,
                "owner_focus": "ALT focus",
                "stages": [
                    {"representation_id": "BASE", "draft_sha256": "cd" * 32},
                    {
                        "representation_id": "NORMALIZED_TRAJECTORY_V1",
                        "draft_sha256": draft_sha,
                    },
                ],
                "writes": {"research_store": 0, "forge_run": 0, "session": 0},
                "blocking_reason_codes": ["PASS_TO_CLASSIFICATION"],
            }
        )
        self.assertIn("RESUME_EXISTING_SESSION", text)
        self.assertIn("--saved-draft-sha256 " + draft_sha, text)
        self.assertIn(
            "uv run --locked --managed-python python -B scripts/hypothesis_forge.py forge-run --no-write",
            text,
        )
        self.assertIn("--owner-focus 'ALT focus'", text)
        self.assertIn("continue classification/finalize in the same session", text)
        self.assertNotIn("persist/freeze that exact draft", text)
        self.assertIn("forge_context=0", text)

    def test_historical_execution_readback_is_not_readiness(self) -> None:
        text = format_forge_run_owner_readout(
            {
                "run_id": "FORGE-RUN-TEST",
                "owner_class": "FORGE_RUN_IN_PROGRESS",
                "next_action": ACTION_RETURN_EXISTING,
                "owner_final": None,
                "execution_provenance_status": EXEC_PROVENANCE_HISTORICAL_UNKNOWN,
                "stages": [],
                "writes": {"research_store": 0, "forge_run": 0, "session": 0},
                "blocking_reason_codes": [],
            }
        )
        self.assertIn("historical readback is UNKNOWN", text)
        self.assertIn("not a readiness receipt", text)

    def test_missing_current_market_identity_is_not_currently_applicable(self) -> None:
        from solana_alpha_lab.factory.hfic_representation_ladder import (
            _session_applicable_to_current_market,
        )

        self.assertFalse(
            _session_applicable_to_current_market(
                {"market_evidence_epoch_sha256": "aa" * 32},
                current_market_epoch=None,
                visible=[],
            )
        )

    def test_current_reuse_requires_full_visible_cohort_scope(self) -> None:
        from solana_alpha_lab.factory.hfic_evidence_identity import (
            scientific_slot_sha256,
        )
        from solana_alpha_lab.factory.hfic_representation_ladder import (
            _session_applicable_to_current_market,
        )

        market = "aa" * 32
        slot = scientific_slot_sha256(
            market_evidence_epoch_sha256=market,
            representation_id="BASE",
            representation_semantic_version="HFIC-V1.2",
            owner_focus="AUTO",
        )
        partial = {
            "market_evidence_epoch_sha256": market,
            "scientific_slot_sha256": slot,
            "representation_semantic_version": "HFIC-V1.2",
            "owner_focus": "AUTO",
            "bound_visible_cohort_ids": ["REL-C1"],
        }
        self.assertFalse(
            _session_applicable_to_current_market(
                partial,
                current_market_epoch=market,
                visible=["REL-C1", "REL-C2"],
            )
        )
        complete = {**partial, "bound_visible_cohort_ids": ["REL-C1", "REL-C2"]}
        self.assertTrue(
            _session_applicable_to_current_market(
                complete,
                current_market_epoch=market,
                visible=["REL-C1", "REL-C2"],
            )
        )

    def test_stage_unknown_readback_is_not_false_done(self) -> None:
        text = format_forge_run_owner_readout(
            {
                "run_id": "FORGE-RUN-TEST",
                "next_action": ACTION_RETURN_EXISTING,
                "owner_final": ACTION_OWNER_CANDIDATE,
                "execution_provenance_status": "NOT_APPLICABLE",
                "stages": [
                    {
                        "representation_id": "BASE",
                        "execution_status": EXEC_REUSED,
                        "execution_provenance_status": EXEC_PROVENANCE_HISTORICAL_UNKNOWN,
                        "effective_terminal": "PASS",
                        "input_scope": "ORDINARY_BASE",
                    }
                ],
                "writes": {"research_store": 0, "forge_run": 0, "session": 0},
                "blocking_reason_codes": [],
            }
        )
        self.assertIn("execution provenance UNKNOWN — not a readiness receipt", text)
        self.assertIn("historical readback is UNKNOWN", text)
        self.assertIn("execution_scope: NOT_SCIENTIFIC_EXECUTION", text)

    def test_execution_binding_conflict_is_blocked_not_done(self) -> None:
        text = format_forge_run_owner_readout(
            {
                "run_id": "FORGE-RUN-TEST",
                "next_action": ACTION_RETURN_EXISTING,
                "owner_final": ACTION_OWNER_CANDIDATE,
                "execution_provenance_status": "NOT_APPLICABLE",
                "stages": [
                    {
                        "representation_id": "BASE",
                        "execution_status": EXEC_REUSED,
                        "execution_provenance_status": EXEC_PROVENANCE_CONFLICT,
                        "effective_terminal": "PASS",
                        "input_scope": "ORDINARY_BASE",
                    }
                ],
                "writes": {"research_store": 0, "forge_run": 0, "session": 0},
                "blocking_reason_codes": [],
            }
        )
        self.assertIn("status: BLOCKED", text)
        self.assertIn("execution binding conflict", text)
        self.assertIn("not a readiness receipt", text)
        self.assertNotIn("status: DONE", text)
        self.assertNotIn("status: READBACK", text)

    def test_pass_to_classification_resumes_until_classify(self) -> None:
        decision = resolve_next_action(
            [
                _base(),
                _v1(
                    execution_status=EXEC_EXECUTED,
                    effective_terminal="PASS_TO_CLASSIFICATION",
                    session_state="AWAITING_CLASSIFICATION",
                    stage_ref_sha256="aa" * 32,
                ),
            ]
        )
        self.assertEqual(decision["next_action"], ACTION_RESUME_V1)
        self.assertIsNone(decision["owner_final"])
        self.assertIn(
            decision["reason_code"],
            {"AWAITING_CLASSIFICATION", "PASS_TO_CLASSIFICATION"},
        )

    def test_kill_with_selected_candidate_is_not_owner_candidate(self) -> None:
        decision = resolve_next_action(
            [
                _base(
                    effective_terminal="KILL_MECHANISM",
                    selected_candidate_id="HFIC-CAND-KILLED",
                    session_state="SYNTHESIS_COMPLETE",
                )
            ]
        )
        self.assertEqual(decision["next_action"], ACTION_SEARCH_EXHAUSTED)
        self.assertNotEqual(decision["next_action"], ACTION_OWNER_CANDIDATE)

    def test_v1_executed_without_terminal_is_observability(self) -> None:
        decision = resolve_next_action(
            [
                _base(),
                _v1(execution_status=EXEC_EXECUTED, effective_terminal=None),
            ]
        )
        self.assertEqual(decision["next_action"], ACTION_OBSERVABILITY_BLOCKED)
        self.assertNotEqual(decision["next_action"], ACTION_SEARCH_EXHAUSTED)

    def test_v1_unmatched_terminal_is_observability(self) -> None:
        decision = resolve_next_action(
            [
                _base(),
                _v1(
                    execution_status=EXEC_EXECUTED,
                    effective_terminal="NOT_A_KNOWN_TERMINAL",
                    stage_ref_sha256="aa" * 32,
                ),
            ]
        )
        self.assertEqual(decision["next_action"], ACTION_OBSERVABILITY_BLOCKED)
        self.assertEqual(decision["reason_code"], "V1_TERMINAL_UNMATCHED")

    def test_v1_exhaustion_without_stage_ref_is_observability(self) -> None:
        decision = resolve_next_action(
            [
                _base(),
                _v1(
                    execution_status=EXEC_EXECUTED,
                    effective_terminal="NO_WORTHY_HYPOTHESIS",
                ),
            ]
        )
        self.assertEqual(decision["next_action"], ACTION_OBSERVABILITY_BLOCKED)
        self.assertEqual(decision["reason_code"], "V1_STAGE_REF_MISSING")

    def test_case_c_is_non_scientific_stop(self) -> None:
        decision = resolve_next_action(
            [_base(effective_terminal="KILL_DATA_INFEASIBLE")]
        )
        self.assertEqual(decision["next_action"], ACTION_NON_SCIENTIFIC_STOP)

    def test_crash_after_generation_reuses_draft(self) -> None:
        decision = resolve_next_action(
            [_base()],
            saved_draft_sha256="ab" * 32,
        )
        self.assertEqual(decision["next_action"], ACTION_RESUME_V1)
        self.assertEqual(decision["draft_sha256"], "ab" * 32)

    def test_retry_completed_run_is_readback(self) -> None:
        decision = resolve_next_action([_base()], existing_completed=True)
        self.assertEqual(decision["next_action"], ACTION_RETURN_EXISTING)

    def test_input_block_precedes_completed_readback(self) -> None:
        decision = resolve_next_action(
            [_base()],
            existing_completed=True,
            input_owner_class=OWNER_CLASS_OBSERVABILITY_BLOCKED,
        )
        self.assertEqual(decision["next_action"], ACTION_OBSERVABILITY_BLOCKED)
        self.assertEqual(decision["owner_final"], ACTION_OBSERVABILITY_BLOCKED)

    def test_future_leak_stays_observability(self) -> None:
        decision = resolve_next_action(
            [
                _base(),
                _v1(execution_status=EXEC_BLOCKED, reason_code="FUTURE_POINT_LEAKAGE"),
            ]
        )
        self.assertEqual(decision["next_action"], ACTION_OBSERVABILITY_BLOCKED)
        self.assertEqual(decision["owner_final"], ACTION_OBSERVABILITY_BLOCKED)

    def test_eligible_synthetic_not_closed_for_missing_alpha(self) -> None:
        decision = resolve_next_action(
            [
                _base(
                    effective_terminal="PASS_CHANGE_LANE_REQUIRED",
                    selected_candidate_id="HFIC-CAND-FIELD-LOOKALIKE",
                )
            ]
        )
        self.assertEqual(decision["next_action"], ACTION_OWNER_CANDIDATE)

    def test_ordinary_no_worthy_not_run_preserves_control_surface_reason(self) -> None:
        decision = resolve_next_action(
            [
                {
                    "representation_id": "BASE",
                    "execution_status": EXEC_NOT_RUN,
                    "effective_terminal": None,
                    "input_scope": "ORDINARY_BASE",
                    "reason_code": "CONTROL_SURFACE_REQUIRED",
                }
            ]
        )
        self.assertEqual(decision["next_action"], ACTION_START_BASE)
        self.assertIsNone(decision["owner_final"])
        self.assertEqual(decision["reason_code"], "CONTROL_SURFACE_REQUIRED")
        self.assertEqual(
            decision.get("base_evidence_surface_mode"),
            CURRENT_REPRESENTATION_CONTROL_V1,
        )

    def test_start_base_when_missing(self) -> None:
        decision = resolve_next_action(
            [
                {
                    "representation_id": "BASE",
                    "execution_status": EXEC_NOT_RUN,
                    "effective_terminal": None,
                    "input_scope": "ORDINARY_BASE",
                }
            ]
        )
        self.assertEqual(decision["next_action"], ACTION_START_BASE)

    def test_input_classes(self) -> None:
        missing = resolve_next_action([], input_owner_class=OWNER_CLASS_INPUT_NOT_READY)
        blocked = resolve_next_action(
            [], input_owner_class=OWNER_CLASS_OBSERVABILITY_BLOCKED
        )
        self.assertEqual(missing["next_action"], "INPUT_NOT_READY")
        self.assertEqual(blocked["next_action"], ACTION_OBSERVABILITY_BLOCKED)

    def test_unknown_active_handler_fail_closes(self) -> None:
        registry = load_ladder_registry()
        extra = list(registry["representations"])
        extra.append(
            {
                "id": "UNKNOWN_LENS",
                "version": "1.0",
                "order": 9,
                "status": "ACTIVE",
                "reuse_class": "CHALLENGER",
                "handler": "NOT_A_HANDLER",
                "trigger_terminals": ["NO_WORTHY_HYPOTHESIS"],
            }
        )
        with self.assertRaises(LadderError) as raised:
            resolve_next_action(
                [
                    _base(),
                    _v1(
                        execution_status=EXEC_EXECUTED,
                        effective_terminal="NO_WORTHY_HYPOTHESIS",
                    ),
                ],
                registry={**registry, "representations": extra},
            )
        self.assertEqual(str(raised.exception), "UNKNOWN_ACTIVE_REPRESENTATION")

    def test_later_registered_known_handler_without_engine_rewrite(self) -> None:
        registry = load_ladder_registry()
        extra = list(registry["representations"])
        extra.append(
            {
                "id": "SYNTHETIC_LATER_V2",
                "version": "1.0",
                "order": 3,
                "status": "ACTIVE",
                "reuse_class": "CHALLENGER",
                "handler": HANDLER_SYNTHETIC_LATER_V2,
                "trigger_terminals": ["NO_WORTHY_HYPOTHESIS"],
            }
        )
        decision = resolve_next_action(
            [
                _base(),
                _v1(
                    execution_status=EXEC_EXECUTED,
                    effective_terminal="NO_WORTHY_HYPOTHESIS",
                    stage_ref_sha256="aa" * 32,
                ),
            ],
            registry={**registry, "representations": extra},
        )
        self.assertEqual(decision["next_action"], "START_SYNTHETIC_LATER_V2")

    def test_completed_later_representation_is_not_restarted(self) -> None:
        registry = load_ladder_registry()
        extra = list(registry["representations"])
        extra.append(
            {
                "id": "SYNTHETIC_LATER_V2",
                "version": "1.0",
                "order": 3,
                "status": "ACTIVE",
                "reuse_class": "CHALLENGER",
                "handler": HANDLER_SYNTHETIC_LATER_V2,
                "trigger_terminals": ["NO_WORTHY_HYPOTHESIS"],
            }
        )
        registry = {**registry, "representations": extra}
        passed = resolve_next_action(
            [
                _base(),
                _v1(
                    execution_status=EXEC_EXECUTED,
                    effective_terminal="NO_WORTHY_HYPOTHESIS",
                    stage_ref_sha256="aa" * 32,
                ),
                {
                    "representation_id": "SYNTHETIC_LATER_V2",
                    "execution_status": EXEC_EXECUTED,
                    "effective_terminal": "PASS_FAST_LANE_READY",
                    "input_scope": "REPRESENTATION_RELEASE_LOCAL",
                    "stage_ref_sha256": "bb" * 32,
                    "session_state": "SYNTHESIS_COMPLETE",
                },
            ],
            registry=registry,
        )
        self.assertEqual(passed["next_action"], ACTION_OWNER_CANDIDATE)
        self.assertNotEqual(passed["next_action"], "START_SYNTHETIC_LATER_V2")
        exhausted = resolve_next_action(
            [
                _base(),
                _v1(
                    execution_status=EXEC_EXECUTED,
                    effective_terminal="NO_WORTHY_HYPOTHESIS",
                    stage_ref_sha256="aa" * 32,
                ),
                {
                    "representation_id": "SYNTHETIC_LATER_V2",
                    "execution_status": EXEC_EXECUTED,
                    "effective_terminal": "NO_WORTHY_HYPOTHESIS",
                    "input_scope": "REPRESENTATION_RELEASE_LOCAL",
                    "stage_ref_sha256": "bb" * 32,
                    "session_state": "SYNTHESIS_COMPLETE",
                },
            ],
            registry=registry,
        )
        self.assertEqual(exhausted["next_action"], ACTION_SEARCH_EXHAUSTED)
        self.assertNotEqual(exhausted["next_action"], "START_SYNTHETIC_LATER_V2")


class ScopeAndPersistenceTests(unittest.TestCase):
    def test_used_cohorts_are_not_all_visible_cohorts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            ResearchStore(data_root)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                receipt = evaluate_forge_run(
                    ROOT,
                    data_root,
                    persist=False,
                    stages=[_base(), _v1(execution_status=EXEC_EXECUTED, effective_terminal="NO_WORTHY_HYPOTHESIS", stage_ref_sha256="aa" * 32)],
                )
        self.assertIn("REL-C1", receipt["stages"][0]["used_cohort_ids"])
        self.assertEqual(receipt["stages"][1]["used_cohort_ids"], ["REL-C2"])
        self.assertNotEqual(
            receipt["visible_cohort_ids"], receipt["stages"][1]["used_cohort_ids"]
        )
        self.assertIn("used_cohorts:", receipt["owner_readout"])
        self.assertEqual(receipt["next_action"], ACTION_SEARCH_EXHAUSTED)
        self.assertEqual(receipt["writes"]["research_store"], 0)

    def test_persist_then_retry_is_readback_same_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            ResearchStore(data_root)
            stages = [
                _base(),
                _v1(
                    execution_status=EXEC_EXECUTED,
                    effective_terminal="NO_WORTHY_HYPOTHESIS",
                    stage_ref_sha256="aa" * 32,
                ),
            ]
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                first = evaluate_forge_run(
                    ROOT, data_root, persist=True, stages=stages, existing_completed=False
                )
            self.assertEqual(first["writes"]["forge_run"], 1)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                second = evaluate_forge_run(
                    ROOT, data_root, persist=False, stages=stages, existing_completed=False
                )
            self.assertEqual(second["run_identity_sha256"], first["run_identity_sha256"])
            self.assertEqual(second["next_action"], ACTION_RETURN_EXISTING)
            self.assertEqual(second["owner_final"], ACTION_SEARCH_EXHAUSTED)
            self.assertEqual(second["persisted_receipt_sha256"], first["receipt_sha256"])
            body = {
                key: value
                for key, value in second.items()
                if key not in {"owner_readout", "receipt_sha256"}
            }
            self.assertEqual(second["receipt_sha256"], canonical_sha256(body))
            self.assertIn("owner_class:", second["owner_readout"])
            self.assertIn("status:", second["owner_readout"])
            self.assertIn("READBACK", second["owner_readout"])
            self.assertIn("persisted:", second["owner_readout"])

    def test_persist_incomplete_base_resumes_not_exhausts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            ResearchStore(data_root)
            stages = [
                _base(
                    effective_terminal=None,
                    session_state="FROZEN_AWAITING_CRITIC",
                    execution_status=EXEC_EXECUTED,
                    draft_sha256="ab" * 32,
                )
            ]
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                first = evaluate_forge_run(
                    ROOT, data_root, persist=True, stages=stages, existing_completed=False
                )
            self.assertEqual(first["next_action"], ACTION_RESUME_BASE)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                replay = evaluate_forge_run(
                    ROOT,
                    data_root,
                    persist=False,
                    stages=first["stages"],
                    existing_completed=False,
                )
        self.assertEqual(replay["next_action"], ACTION_RESUME_BASE)
        self.assertNotEqual(replay["next_action"], ACTION_SEARCH_EXHAUSTED)

    def test_same_slot_does_not_mint_second_payload(self) -> None:
        decision_a = resolve_next_action([_base()], saved_draft_sha256="cd" * 32)
        decision_b = resolve_next_action([_base()], saved_draft_sha256="cd" * 32)
        self.assertEqual(decision_a["draft_sha256"], decision_b["draft_sha256"])
        self.assertEqual(decision_a["next_action"], ACTION_RESUME_V1)


class RealNoWriteVerticalTests(unittest.TestCase):
    def test_canonical_control_auto_advance_does_not_write(self) -> None:
        resolved = resolve_existing_data_root(ROOT)
        if resolved.status != "PRESENT" or resolved.root is None:
            self.skipTest("canonical data plane not present in this checkout")
        data_root = resolved.root
        if not is_fast_lane_commissioned(data_root):
            self.skipTest("canonical plane is not Fast Lane commissioned")

        def fingerprint() -> str:
            parts: list[str] = []
            research = data_root / "research"
            if research.is_dir():
                for path in sorted(
                    p for p in research.rglob("*") if p.is_file() and not p.is_symlink()
                ):
                    rel = path.relative_to(data_root).as_posix()
                    stat = path.stat()
                    parts.append(f"{rel}:{stat.st_size}:{stat.st_mtime_ns}")
            return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()

        before = fingerprint()
        fp = instance_fingerprint(data_root)
        receipt = evaluate_forge_run(
            ROOT,
            data_root,
            persist=False,
            preferred_control_session_id=EXISTING_V1_CONTROL_SESSION_ID,
        )
        self.assertEqual(before, fingerprint())
        self.assertEqual(receipt["writes"]["research_store"], 0)
        self.assertEqual(receipt["writes"]["session"], 0)
        self.assertEqual(fp, instance_fingerprint(data_root))
        self.assertIsNone(receipt["control_session_id"])
        self.assertEqual(receipt["next_action"], ACTION_START_BASE)
        self.assertIsNone(receipt["owner_final"])
        self.assertIn("CONTROL_SURFACE_REQUIRED", receipt["blocking_reason_codes"])
        self.assertEqual(receipt["stages"][0]["reason_code"], "CONTROL_SURFACE_REQUIRED")
        self.assertIsInstance(receipt["market_evidence_epoch_sha256"], str)
        self.assertEqual(len(receipt["market_evidence_epoch_sha256"]), 64)


class RegistryLoadTests(unittest.TestCase):
    def test_default_registry_known_handlers(self) -> None:
        registry = load_ladder_registry()
        ids = [row["id"] for row in registry["representations"]]
        self.assertEqual(ids, ["BASE", "NORMALIZED_TRAJECTORY_V1"])


class SkillContractTests(unittest.TestCase):
    def test_slash_docs_are_bounded_run(self) -> None:
        skill = (ROOT / ".agents/skills/hypothesis-forge/SKILL.md").read_text(
            encoding="utf-8"
        )
        command = (ROOT / ".cursor/commands/hypothesis-forge.md").read_text(
            encoding="utf-8"
        )
        operator = (
            ROOT / "docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md"
        ).read_text(encoding="utf-8")
        yaml_text = (
            ROOT / "configs/hypothesis_forge_independent_critic_v1.yaml"
        ).read_text(encoding="utf-8")
        for text in (skill, command, operator, yaml_text):
            self.assertIn("ONE_SLASH_ONE_BOUNDED_RUN", text)
            self.assertNotIn("ONE_SLASH_ONE_SESSION", text)
            self.assertIn("forge-run", text)
        for text in (skill, command, operator):
            self.assertIn("owner_readout", text)
        self.assertIn("Branch on `forge-run` `next_action`", skill)
        self.assertIn("**not** stop the bounded run when `forge-run` next is `START_V1`", skill)
        self.assertIn("run_layer_auto_advance", yaml_text)
        self.assertIn("START_V1", yaml_text)
        self.assertIn("consume_start_v1_envelope", skill)
        self.assertIn("FORGE_CONTEXT_PACKET", skill)
        self.assertIn("no fake critic", skill)
        self.assertIn("challenger", skill.lower())
        self.assertIn("CONTROL_SURFACE_REQUIRED", skill)
        self.assertIn("PASS_TO_CLASSIFICATION", skill)
        self.assertIn("prepare_ladder_freeze_preflight", skill)
        self.assertIn("re-run `forge-run`", skill.lower())
        self.assertIn("`KEEP_PAUSE` is a typed pause (`status: NEXT`", skill)
        self.assertIn("`owner_final` null", skill)
        self.assertIn("do **not** report", skill)
        self.assertIn("evening DONE / success", skill)
        self.assertIn("must not lock the run as", skill)
        self.assertNotIn("dormant wiring", skill)
        self.assertIn("CONTROL_SURFACE_REQUIRED", command)
        self.assertIn("CONTROL_SURFACE_REQUIRED", operator)
        self.assertIn("`KEEP_PAUSE` is a typed pause (`status: NEXT`)", command)
        self.assertIn("`KEEP_PAUSE` is a typed pause (`status: NEXT`)", operator)
        self.assertNotIn("evening complete, not a NEXT", command)
        self.assertIn("FORGE_CONTEXT_PACKET", command)
        self.assertIn("FORGE_CONTEXT_PACKET", operator)
        self.assertNotIn("Then branch on preflight action (step 2)", skill.split("forge-run")[0])


class DisposableFreezeFinalizeE2ETests(unittest.TestCase):
    def test_kill_base_finalize_does_not_start_v1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            frozen = freeze_draft(
                valid_draft(),
                preflight_receipt=_control_preflight(data_root, store),
                repo_root=ROOT,
            )
            packet = frozen["critic_input_packet"]
            assert isinstance(packet, dict)
            done = finalize_kill_complete(
                frozen,
                critic_result_from_packet_only(packet, "KILL_MECHANISM"),
                store,
                repo_root=ROOT,
            )
            self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                receipt = evaluate_forge_run(
                    ROOT,
                    data_root,
                    persist=False,
                    preferred_control_session_id=str(frozen["session_id"]),
                )
        self.assertNotEqual(receipt["next_action"], ACTION_START_V1)
        self.assertEqual(receipt["next_action"], ACTION_SEARCH_EXHAUSTED)
        self.assertNotEqual(receipt["next_action"], ACTION_OWNER_CANDIDATE)
        self.assertEqual(receipt["control_session_id"], frozen["session_id"])
        v1 = next(
            (
                row
                for row in receipt["stages"]
                if row["representation_id"] == "NORMALIZED_TRAJECTORY_V1"
            ),
            None,
        )
        if v1 is not None:
            self.assertEqual(v1["execution_status"], EXEC_NOT_RUN)
        self.assertIn("next_action:", receipt["owner_readout"])

    def test_selected_base_freeze_resumes_without_starting_v1(self) -> None:
        draft = valid_draft()
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            frozen = freeze_draft(
                draft,
                preflight_receipt=_control_preflight(data_root, store),
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
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                receipt = evaluate_forge_run(
                    ROOT,
                    data_root,
                    persist=False,
                    preferred_control_session_id=str(frozen["session_id"]),
                )
        self.assertEqual(receipt["next_action"], ACTION_RESUME_BASE)
        self.assertNotEqual(receipt["next_action"], ACTION_START_V1)
        self.assertNotEqual(receipt["next_action"], ACTION_OWNER_CANDIDATE)
        self.assertEqual(receipt["control_session_id"], frozen["session_id"])
        self.assertIsNone(receipt["owner_final"])

    def test_no_worthy_control_freeze_auto_starts_v1(self) -> None:
        draft = json.loads(NO_WORTHY_DRAFT.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            preflight = _control_preflight(data_root, store)
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
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                receipt = evaluate_forge_run(
                    ROOT,
                    data_root,
                    persist=False,
                    preferred_control_session_id=str(frozen["session_id"]),
                )
        self.assertEqual(receipt["next_action"], ACTION_START_V1)
        self.assertIsNone(receipt["owner_final"])
        self.assertEqual(receipt["control_session_id"], frozen["session_id"])
        self.assertEqual(receipt["writes"]["session"], 0)
        self.assertEqual(receipt["writes"]["forge_run"], 0)
        envelope = consume_start_v1_envelope(
            {
                "next_action": receipt["next_action"],
                "owner_final": receipt["owner_final"],
            },
            control_receipt=_no_worthy_forge_receipt(),
            representation=_representation_fixture(),
            cohort_readiness_receipt=_cohort_readiness_receipt(),
            base_x_population_n=10,
        )
        self.assertEqual(envelope["control_context_kind"], CONTROL_CONTEXT_KIND_FORGE)
        self.assertIsNone(envelope["critic_input_packet"])
        self.assertFalse(envelope["probe_executed"])

    def test_start_v1_routing_consumes_challenger_envelope(self) -> None:
        control = _no_worthy_forge_receipt()
        representation = _representation_fixture()
        readiness = _cohort_readiness_receipt()
        envelope = consume_start_v1_envelope(
            {"next_action": ACTION_START_V1, "owner_final": None},
            control_receipt=control,
            representation=representation,
            cohort_readiness_receipt=readiness,
            base_x_population_n=10,
        )
        self.assertFalse(envelope["probe_executed"])
        self.assertFalse(envelope["fake_critic_packet"])
        self.assertEqual(
            envelope.get("ladder_representation_id"),
            "NORMALIZED_TRAJECTORY_V1",
        )
        self.assertNotIn("ladder_representation_id", envelope["challenger"])
        self.assertEqual(envelope["control_context_kind"], CONTROL_CONTEXT_KIND_FORGE)
        self.assertIsNone(envelope["critic_input_packet"])
        self.assertIsNone(envelope["lifecycle"])
        challenger = envelope["challenger"]
        assert isinstance(challenger, dict)
        self.assertEqual(challenger["control_context"], control["forge_context_packet"])
        self.assertIn("normalized_trajectory_v1", challenger)
        self.assertNotIn("selected_candidate", json.dumps(challenger))
        self.assertNotEqual(
            envelope["representation_search_key_sha256"],
            control["search_key_sha256"],
        )
        with self.assertRaises(LadderError):
            consume_start_v1_envelope(
                {"next_action": ACTION_RESUME_V1, "owner_final": None},
                control_receipt=control,
                representation=representation,
                cohort_readiness_receipt=readiness,
                base_x_population_n=10,
            )
        with self.assertRaises(LadderError):
            consume_start_v1_envelope(
                {"next_action": ACTION_SEARCH_EXHAUSTED, "owner_final": None},
                control_receipt=control,
                representation=representation,
                cohort_readiness_receipt=readiness,
                base_x_population_n=10,
            )

    def test_b1_selected_control_envelope_keeps_marker_outside_challenger(self) -> None:
        """Selected CONTROL must not inject ladder_representation_id into frozen challenger."""

        envelope = consume_start_v1_envelope(
            {"next_action": ACTION_START_V1, "owner_final": None},
            control_receipt=_control_receipt(),
            representation=_representation_fixture(),
            cohort_readiness_receipt=_cohort_readiness_receipt(),
            base_x_population_n=10,
        )
        self.assertEqual(envelope.get("ladder_representation_id"), "NORMALIZED_TRAJECTORY_V1")
        challenger = envelope["challenger"]
        assert isinstance(challenger, dict)
        self.assertNotIn("ladder_representation_id", challenger)
        # Downstream scientific validator accepts the exact challenger bytes.
        existing_hfic_lifecycle_fixture_input(
            challenger,
            control_receipt=_control_receipt(),
            cohort_readiness_receipt=_cohort_readiness_receipt(),
            base_x_population_n=10,
        )

    def test_b2_payload_and_parent_tamper_rejected_before_freeze(self) -> None:
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
        # Payload bytes changed, hashes left intact → scientific reject.
        tampered = dict(challenger)
        payload = dict(tampered["normalized_trajectory_v1"])
        payload["eligible_member_count"] = int(payload.get("eligible_member_count") or 0) + 1
        tampered["normalized_trajectory_v1"] = payload
        with self.assertRaises(LadderError) as payload_exc:
            prepare_ladder_freeze_preflight(
                preflight,
                representation_id="NORMALIZED_TRAJECTORY_V1",
                control_session_id=parent,
                challenger=tampered,
                control_receipt=control,
            )
        self.assertIn("LADDER_FREEZE_CHALLENGER_INVALID", str(payload_exc.exception))
        # Parent string rewritten without matching CONTROL receipt → reject.
        foreign = dict(challenger)
        foreign["control_session_id"] = "HFIC-SESS-FOREIGN-PARENT"
        with self.assertRaises(LadderError) as parent_exc:
            prepare_ladder_freeze_preflight(
                preflight,
                representation_id="NORMALIZED_TRAJECTORY_V1",
                control_session_id="HFIC-SESS-FOREIGN-PARENT",
                challenger=foreign,
                control_receipt=control,
            )
        msg = str(parent_exc.exception)
        self.assertTrue(
            "PARENT_MISMATCH" in msg
            or "CONTROL_UNBOUND" in msg
            or "LADDER_FREEZE_CHALLENGER_INVALID" in msg,
            msg,
        )

    def test_v1_challenger_envelope_reaches_existing_hfic_lifecycle(self) -> None:
        control = _control_receipt()
        representation = _representation_fixture()
        readiness = _cohort_readiness_receipt()
        challenger = build_challenger_packet(
            control_baseline_from_receipt(control),
            representation,
            cohort_readiness_receipt=readiness,
        )
        lifecycle = existing_hfic_lifecycle_fixture_input(
            challenger,
            control_receipt=control,
            cohort_readiness_receipt=readiness,
        )
        baseline_packet = existing_hfic_packet(
            challenger, cohort_readiness_receipt=readiness
        )
        self.assertEqual(lifecycle["critic_input_packet"], baseline_packet)
        self.assertIn("representation", lifecycle)
        self.assertEqual(lifecycle["representation"], challenger["normalized_trajectory_v1"])
        self.assertNotEqual(
            challenger["representation_search_key_sha256"],
            control["search_key_sha256"],
        )
        self.assertTrue(challenger["ordinary_search_budget_unchanged"])

    def test_two_worktrees_share_root_and_c3_is_visible_without_ladder_edits(self) -> None:
        ladder_before = (ROOT / "configs/hfic_representation_ladder_v1.yaml").read_bytes()
        historical_c1 = (
            ROOT / "docs/evidence/forge_input_truth_and_visibility/a1_c1_c2_forge_input_v1.json"
        ).read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            principal = Path(tmp) / "principal"
            linked = Path(tmp) / "linked"
            _init_repo(principal)
            _git(principal, "worktree", "add", str(linked), "-b", "linked-a4")
            try:
                from_principal = resolve_data_root(principal, env={})
                from_linked = resolve_data_root(linked, env={})
                self.assertEqual(from_principal, from_linked)
                data_root = from_principal
                data_root.mkdir(parents=True, exist_ok=True)
                _write_lineage(data_root)
                ResearchStore(data_root)
                with patch(
                    "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                    side_effect=_enumerate_live,
                ):
                    first = evaluate_forge_run(
                        ROOT,
                        data_root,
                        persist=False,
                        stages=[_base(), _v1()],
                    )
                lineage_path = (
                    data_root / "datasets" / "live_lifecycle_corpus" / "lineage.json"
                )
                payload = json.loads(lineage_path.read_text(encoding="utf-8"))
                payload["cohorts"].append(
                    {
                        "cohort_id": "REL-C3",
                        "release_id": "rel-c3",
                        "source_sha256": "cc" * 32,
                    }
                )
                lineage_path.write_text(
                    json.dumps(payload, indent=2), encoding="utf-8"
                )

                def _enumerate_c3(_data_root: Path, **_kwargs: object):
                    live = _enumerate_live(_data_root)[0]
                    extra = dict(live[0])
                    extra["dataset_manifest_id"] = "MID-C3"
                    extra["labels"] = {
                        **dict(extra.get("labels") or {}),
                        "cohort_id": "REL-C3",
                    }
                    return [*live, extra], []

                with patch(
                    "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                    side_effect=_enumerate_c3,
                ):
                    second = evaluate_forge_run(
                        ROOT,
                        data_root,
                        persist=False,
                        stages=[_base(), _v1()],
                    )
            finally:
                _git(principal, "worktree", "remove", "--force", str(linked))
        self.assertEqual(ladder_before, (ROOT / "configs/hfic_representation_ladder_v1.yaml").read_bytes())
        self.assertEqual(
            historical_c1,
            (
                ROOT / "docs/evidence/forge_input_truth_and_visibility/a1_c1_c2_forge_input_v1.json"
            ).read_bytes(),
        )
        self.assertIn("REL-C1", first["visible_cohort_ids"])
        self.assertNotEqual(first["input_receipt_sha256"], second["input_receipt_sha256"])
        self.assertEqual(first["next_action"], ACTION_START_V1)
        self.assertEqual(second["next_action"], ACTION_START_V1)


def _v1_preflight(
    data_root: Path,
    store: ResearchStore,
    *,
    control_session_id: str,
    cohorts: list[str] | None = None,
    repo_root: Path = ROOT,
) -> dict[str, object]:
    """V1 freeze preflight via envelope challenger (not marker-only CONTROL copy)."""

    v1_pre, _envelope = _v1_freeze_preflight_from_envelope(
        data_root,
        store,
        control_session_id=control_session_id,
        repo_root=repo_root,
    )
    if cohorts is not None:
        packet = v1_pre["forge_context_packet"]
        assert isinstance(packet, dict)
        packet["bound_visible_cohort_ids"] = list(cohorts)
        packet.pop("visible_cohort_ids", None)
        digest = persist_forge_context_packet(
            data_root, packet, store=store, repo_root=repo_root
        )
        v1_pre["forge_context_packet_sha256"] = digest
    return v1_pre


def _v2_preflight(
    data_root: Path,
    store: ResearchStore,
    *,
    control_session_id: str,
) -> dict[str, object]:
    with patch(
        "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
        side_effect=_enumerate_live,
    ):
        split = compute_split_identity(ROOT, data_root)
    market_epoch = str(split["market_evidence_epoch_sha256"])
    capability_epoch = str(split["capability_epoch_sha256"])
    git = repository_git_snapshot(ROOT)
    packet = {
        "schema": "smial.forge-context-packet",
        "owner_focus": "AUTO",
        "evidence_epoch_sha256": market_epoch,
        "market_evidence_epoch_sha256": market_epoch,
        "capability_epoch_sha256": capability_epoch,
        "capability_ids": ["CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"],
        "vision_integrity": {"status": "PASS"},
        "ladder_representation_id": "SYNTHETIC_LATER_V2",
        "representation_semantic_version": "1.0",
        "visible_cohort_ids": ["REL-C2"],
        "bound_visible_cohort_ids": ["REL-C2"],
        "control_session_id": control_session_id,
    }
    digest = persist_forge_context_packet(
        data_root, packet, store=store, repo_root=ROOT
    )
    return {
        "receipt_id": "HFIC-PREFLIGHT-V2-FIXTURE-001",
        "evidence_epoch_sha256": market_epoch,
        "market_evidence_epoch_sha256": market_epoch,
        "capability_epoch_sha256": capability_epoch,
        "focus_key_sha256": focus_key_sha256("AUTO"),
        "search_key_sha256": "ee" * 32,
        "owner_focus": "AUTO",
        "live_git_head": git.head_sha.lower(),
        "git_composite_sha256": git.composite_sha256,
        "session_started_at": "2026-08-27T12:00:00Z",
        "forge_context_packet_sha256": digest,
        "forge_context_packet": packet,
    }


def _distinct_no_worthy_draft(*, label: str) -> dict[str, object]:
    """Current-prompt no-worthy reply. Historical 1.1 lives in NO_WORTHY_DRAFT."""

    draft = json.loads(
        (ROOT / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1_2.json").read_text(
            encoding="utf-8"
        )
    )
    for card in draft.get("candidates") or []:
        if isinstance(card, dict):
            claim = str(card.get("claim") or "")
            card["claim"] = f"{label} {claim}".strip()
    return draft


def _later_registry() -> dict[str, object]:
    registry = load_ladder_registry()
    extra = list(registry["representations"])
    extra.append(
        {
            "id": "SYNTHETIC_LATER_V2",
            "version": "1.0",
            "order": 3,
            "status": "ACTIVE",
            "reuse_class": "CHALLENGER",
            "handler": HANDLER_SYNTHETIC_LATER_V2,
            "trigger_terminals": ["NO_WORTHY_HYPOTHESIS"],
        }
    )
    return {**registry, "representations": extra}


class ProductionPathAcceptanceTests(unittest.TestCase):
    def _no_worthy_base(
        self,
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

    def test_g1_ordinary_no_worthy_surfaces_control_surface_required(self) -> None:
        """Ordinary completed BASE must not bare-START without CONTROL_SURFACE_REQUIRED."""

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            draft = json.loads(NO_WORTHY_DRAFT.read_text(encoding="utf-8"))
            git = repository_git_snapshot(ROOT)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                split = compute_split_identity(ROOT, data_root)
            market_epoch = str(split["market_evidence_epoch_sha256"])
            capability_epoch = str(split["capability_epoch_sha256"])
            packet = {
                "schema": "smial.forge-context-packet",
                "owner_focus": "AUTO",
                "evidence_epoch_sha256": market_epoch,
                "market_evidence_epoch_sha256": market_epoch,
                "capability_epoch_sha256": capability_epoch,
                "capability_ids": ["CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"],
                "vision_integrity": {"status": "PASS"},
                "ladder_representation_id": "BASE",
            }
            digest = persist_forge_context_packet(
                data_root, packet, store=store, repo_root=ROOT
            )
            ordinary = {
                "receipt_id": "HFIC-PREFLIGHT-ORDINARY-001",
                "evidence_epoch_sha256": market_epoch,
                "market_evidence_epoch_sha256": market_epoch,
                "capability_epoch_sha256": capability_epoch,
                "focus_key_sha256": focus_key_sha256("AUTO"),
                "search_key_sha256": "cc" * 32,
                "owner_focus": "AUTO",
                "live_git_head": git.head_sha.lower(),
                "git_composite_sha256": git.composite_sha256,
                "session_started_at": "2026-08-27T12:00:00Z",
                "forge_context_packet_sha256": digest,
                "forge_context_packet": packet,
            }
            frozen = freeze_draft(draft, preflight_receipt=ordinary, repo_root=ROOT)
            persist_no_worthy_session(
                store,
                frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(draft["candidates"]),
                draft=draft,
                preflight_receipt=ordinary,
            )
            store.rebuild_projection()
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                started = evaluate_forge_run(ROOT, data_root, persist=False)
        self.assertEqual(started["next_action"], ACTION_START_BASE)
        self.assertIsNone(started["owner_final"])
        self.assertIn("CONTROL_SURFACE_REQUIRED", started["blocking_reason_codes"])
        self.assertIn("CONTROL-compatible BASE", started["owner_readout"])
        self.assertNotIn("status: DONE", started["owner_readout"])

    def test_g1_production_packet_writer_stamps_bound_cohorts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            preflight = _production_control_preflight(data_root, store)
            packet = preflight["forge_context_packet"]
            assert isinstance(packet, dict)
            self.assertEqual(
                packet.get("evidence_surface_mode"),
                CURRENT_REPRESENTATION_CONTROL_V1,
            )
            self.assertEqual(packet.get("bound_visible_cohort_ids"), ["REL-C1", "REL-C2"])
            self.assertNotIn("visible_cohort_ids", packet)
            base = self._no_worthy_base(data_root, store, production_packet=True)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                started = evaluate_forge_run(ROOT, data_root, persist=False)
        self.assertEqual(started["control_session_id"], base["session_id"])
        self.assertEqual(started["next_action"], ACTION_START_V1)
        self.assertEqual(started["stages"][0]["used_cohort_ids"], ["REL-C1", "REL-C2"])

    def test_f1_historical_control_does_not_inherit_later_visible_cohorts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            frozen = self._no_worthy_base(data_root, store)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                matched = evaluate_forge_run(ROOT, data_root, persist=False)
            self.assertEqual(matched["control_session_id"], frozen["session_id"])
            self.assertEqual(matched["next_action"], ACTION_START_V1)
            self.assertEqual(matched["stages"][0]["used_cohort_ids"], ["REL-C1", "REL-C2"])
            self.assertEqual(matched["stages"][0]["execution_status"], EXEC_REUSED)
            lineage_path = data_root / "datasets" / "live_lifecycle_corpus" / "lineage.json"
            payload = json.loads(lineage_path.read_text(encoding="utf-8"))
            payload["cohorts"].append(
                {"cohort_id": "REL-C3", "release_id": "rel-c3", "source_sha256": "cc" * 32}
            )
            lineage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            def _enumerate_c3(_data_root: Path, **_kwargs: object):
                live = _enumerate_live(_data_root)[0]
                extra = dict(live[0])
                extra["dataset_manifest_id"] = "MID-C3"
                extra["labels"] = {
                    **dict(extra.get("labels") or {}),
                    "cohort_id": "REL-C3",
                }
                return [*live, extra], []

            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_c3,
            ):
                drifted = evaluate_forge_run(ROOT, data_root, persist=False)
                alt_focus = evaluate_forge_run(
                    ROOT, data_root, persist=False, owner_focus="ALT"
                )
        self.assertNotIn("REL-C3", drifted["stages"][0]["used_cohort_ids"])
        self.assertNotEqual(drifted["stages"][0]["execution_status"], EXEC_REUSED)
        self.assertNotEqual(drifted["next_action"], ACTION_SEARCH_EXHAUSTED)
        self.assertIsNone(alt_focus["control_session_id"])
        self.assertEqual(alt_focus["next_action"], ACTION_START_BASE)

    def test_f2_v1_candidate_from_real_artifacts_then_readback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = self._no_worthy_base(data_root, store, production_packet=True)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                started = evaluate_forge_run(ROOT, data_root, persist=True)
            self.assertEqual(started["next_action"], ACTION_START_V1)
            self.assertEqual(started["writes"]["forge_run"], 1)
            v1_pre, envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(base["session_id"]),
            )
            self.assertFalse(envelope["fake_critic_packet"])
            self.assertIn("normalized_trajectory_v1", v1_pre["forge_context_packet"])
            self.assertEqual(
                v1_pre["forge_context_packet"].get("representation_payload_sha256"),
                envelope["challenger"].get("representation_payload_sha256"),
            )
            draft = _current_v12_draft(v1_pre)
            frozen = freeze_draft(draft, preflight_receipt=v1_pre, repo_root=ROOT)
            persist_frozen_session(
                store,
                frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(draft["candidates"]),
                draft=draft,
            )
            store.rebuild_projection()
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                mid = evaluate_forge_run(ROOT, data_root, persist=True)
            self.assertEqual(mid["next_action"], ACTION_RESUME_V1)
            self.assertEqual(mid["run_identity_sha256"], started["run_identity_sha256"])
            packet = frozen["critic_input_packet"]
            assert isinstance(packet, dict)
            awaiting = finalize_session(
                frozen,
                critic_result_from_packet_only(packet, "PASS_TO_CLASSIFICATION"),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(awaiting["session_state"], "AWAITING_CLASSIFICATION")
            store.rebuild_projection()
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                pending = evaluate_forge_run(ROOT, data_root, persist=True)
            self.assertEqual(pending["next_action"], ACTION_RESUME_V1)
            self.assertIsNone(pending["owner_final"])
            self.assertIn("classify then finalize", pending["owner_readout"])
            spec = _submission_for_frozen(frozen)
            done = apply_classification(
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
        v1 = next(
            row
            for row in finished["stages"]
            if row["representation_id"] == "NORMALIZED_TRAJECTORY_V1"
        )
        self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
        self.assertNotEqual(done.get("critic_terminal"), "PASS_TO_CLASSIFICATION")
        self.assertEqual(finished["next_action"], ACTION_OWNER_CANDIDATE)
        self.assertEqual(v1["session_id"], frozen["session_id"])
        self.assertIsInstance(v1["stage_ref_sha256"], str)
        self.assertEqual(len(str(v1["stage_ref_sha256"])), 64)
        self.assertEqual(v1["used_cohort_ids"], ["REL-C2"])
        self.assertNotEqual(v1["used_cohort_ids"], finished["visible_cohort_ids"])
        self.assertIn("candidate:", finished["owner_readout"])
        self.assertEqual(retry["next_action"], ACTION_RETURN_EXISTING)
        self.assertEqual(retry["run_identity_sha256"], started["run_identity_sha256"])

    def test_f2_v1_negative_exhaustion_then_retry_readback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = self._no_worthy_base(data_root, store, production_packet=True)
            draft = _distinct_no_worthy_draft(label="V1")
            v1_pre, envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(base["session_id"]),
            )
            self.assertIn("normalized_trajectory_v1", v1_pre["forge_context_packet"])
            self.assertEqual(
                v1_pre["forge_context_packet"].get("representation_payload_sha256"),
                envelope["challenger"].get("representation_payload_sha256"),
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
        v1 = next(
            row
            for row in finished["stages"]
            if row["representation_id"] == "NORMALIZED_TRAJECTORY_V1"
        )
        self.assertEqual(finished["next_action"], ACTION_SEARCH_EXHAUSTED)
        self.assertEqual(v1["effective_terminal"], "NO_WORTHY_HYPOTHESIS")
        self.assertEqual(v1["session_id"], frozen["session_id"])
        self.assertIsInstance(v1["stage_ref_sha256"], str)
        self.assertIn("NOT_RUN_NO_SELECTED_CANDIDATE", finished["owner_readout"])
        self.assertEqual(retry["next_action"], ACTION_RETURN_EXISTING)

    def test_f3_completed_v2_is_not_restarted_on_normal_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = self._no_worthy_base(data_root, store)
            v1_draft = _distinct_no_worthy_draft(label="V1")
            v1_pre = _v1_preflight(data_root, store, control_session_id=str(base["session_id"]))
            v1_frozen = freeze_draft(v1_draft, preflight_receipt=v1_pre, repo_root=ROOT)
            persist_no_worthy_session(
                store,
                v1_frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(v1_draft["candidates"]),
                draft=v1_draft,
                preflight_receipt=v1_pre,
            )
            v2_draft = valid_draft()
            v2_pre = _v2_preflight(data_root, store, control_session_id=str(base["session_id"]))
            v2_frozen = freeze_draft(v2_draft, preflight_receipt=v2_pre, repo_root=ROOT)
            persist_frozen_session(
                store,
                v2_frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(v2_draft["candidates"]),
                draft=v2_draft,
                representation_registry=_later_registry(),
            )
            packet = v2_frozen["critic_input_packet"]
            assert isinstance(packet, dict)
            awaiting = finalize_session(
                v2_frozen,
                critic_result_from_packet_only(packet, "PASS_TO_CLASSIFICATION"),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(awaiting["session_state"], "AWAITING_CLASSIFICATION")
            spec = _submission_for_frozen(v2_frozen)
            apply_classification(
                v2_frozen,
                spec,
                store=store,
                repo_root=ROOT,
                data_root=data_root,
            )
            store.rebuild_projection()
            registry = _later_registry()
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                finished = evaluate_forge_run(
                    ROOT, data_root, persist=True, registry=registry
                )
                retry = evaluate_forge_run(
                    ROOT, data_root, persist=False, registry=registry
                )
        self.assertEqual(finished["next_action"], ACTION_OWNER_CANDIDATE)
        self.assertNotEqual(finished["next_action"], "START_SYNTHETIC_LATER_V2")
        self.assertEqual(retry["next_action"], ACTION_RETURN_EXISTING)

    def test_f2_epoch_focus_lookup_keeps_base_and_v1_slots_apart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = self._no_worthy_base(data_root, store)
            control = _control_preflight(data_root, store)
            found_base = find_session_by_epoch_focus(
                store,
                str(control["evidence_epoch_sha256"]),
                str(control["focus_key_sha256"]),
                evidence_surface_mode=str(control["evidence_surface_mode"]),
                ladder_representation_id="BASE",
                control_session_id=None,
            )
            self.assertIsNotNone(found_base)
            assert found_base is not None
            self.assertEqual(found_base["session_id"], base["session_id"])
            v1_pre, _envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(base["session_id"]),
                control_preflight=control,
            )
            draft = _current_v12_draft(v1_pre)
            frozen = freeze_draft(draft, preflight_receipt=v1_pre, repo_root=ROOT)
            persist_frozen_session(
                store,
                frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(draft["candidates"]),
                draft=draft,
            )
            store.rebuild_projection()
            found_v1 = find_session_by_epoch_focus(
                store,
                str(v1_pre["evidence_epoch_sha256"]),
                str(v1_pre["focus_key_sha256"]),
                ladder_representation_id="NORMALIZED_TRAJECTORY_V1",
                control_session_id=str(base["session_id"]),
            )
            found_base_again = find_session_by_epoch_focus(
                store,
                str(control["evidence_epoch_sha256"]),
                str(control["focus_key_sha256"]),
                evidence_surface_mode=str(control["evidence_surface_mode"]),
                ladder_representation_id="BASE",
                control_session_id=None,
            )
        self.assertIsNotNone(found_v1)
        assert found_v1 is not None
        self.assertEqual(found_v1["session_id"], frozen["session_id"])
        self.assertNotEqual(found_v1["session_id"], base["session_id"])
        self.assertIsNotNone(found_base_again)
        assert found_base_again is not None
        self.assertEqual(found_base_again["session_id"], base["session_id"])

    def test_f2_cli_preflight_store_freeze_is_distinct_from_control(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = self._no_worthy_base(data_root, store, production_packet=True)
            cli = _load_hypothesis_forge_cli()
            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = cli.cmd_forge_run(
                        ROOT,
                        explicit_data_root=data_root,
                        owner_focus="AUTO",
                        persist=True,
                    )
            self.assertEqual(code, 0)
            started = json.loads(stdout.getvalue())
            self.assertEqual(started["next_action"], ACTION_START_V1)
            # Without envelope challenger, freeze stays pending (not marker-only).
            self.assertNotIn("ladder_freeze_preflight", started)
            self.assertEqual(
                started.get("ladder_freeze_pending_reason"),
                "LADDER_FREEZE_CHALLENGER_REQUIRED",
            )
            v1_pre, envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(base["session_id"]),
            )
            packet = v1_pre["forge_context_packet"]
            self.assertEqual((packet.get("vision_integrity") or {}).get("status"), "PASS")
            self.assertIn("normalized_trajectory_v1", packet)
            self.assertEqual(
                packet.get("representation_payload_sha256"),
                envelope["challenger"].get("representation_payload_sha256"),
            )
            self.assertEqual(packet.get("ladder_representation_id"), "NORMALIZED_TRAJECTORY_V1")
            self.assertIsNone(base.get("critic_input_packet"))
            draft = _current_v12_draft(v1_pre)
            frozen = freeze_draft(
                draft,
                preflight_receipt=v1_pre,
                store=store,
                repo_root=ROOT,
            )
            self.assertNotEqual(frozen["session_id"], base["session_id"])
            self.assertEqual(frozen["ladder_representation_id"], "NORMALIZED_TRAJECTORY_V1")
            self.assertEqual(frozen["control_session_id"], base["session_id"])
            self.assertNotEqual(frozen.get("action"), "START_NEW_SESSION")
            packet_out = frozen["critic_input_packet"]
            assert isinstance(packet_out, dict)
            self.assertIsNotNone(packet_out.get("selected_candidate"))
            self.assertEqual(
                packet_out.get("ladder_representation_id"),
                "NORMALIZED_TRAJECTORY_V1",
            )
            self.assertIn("normalized_trajectory_v1", packet_out)
            self.assertEqual(
                packet_out.get("representation_payload_sha256"),
                envelope["challenger"].get("representation_payload_sha256"),
            )
            self.assertEqual(
                frozen["forge_context_packet"].get("ladder_representation_id"),
                "NORMALIZED_TRAJECTORY_V1",
            )
            awaiting = finalize_session(
                frozen,
                critic_result_from_packet_only(packet_out, "PASS_TO_CLASSIFICATION"),
                store=store,
                repo_root=ROOT,
            )
            self.assertEqual(awaiting["session_state"], "AWAITING_CLASSIFICATION")
            store.rebuild_projection()
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                pending = evaluate_forge_run(ROOT, data_root, persist=True)
            self.assertEqual(pending["next_action"], ACTION_RESUME_V1)
            self.assertIsNone(pending["owner_final"])
            spec = _submission_for_frozen(frozen)
            done = apply_classification(
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
            found_v1 = find_session_by_epoch_focus(
                store,
                str(v1_pre["evidence_epoch_sha256"]),
                str(v1_pre["focus_key_sha256"]),
                ladder_representation_id="NORMALIZED_TRAJECTORY_V1",
                control_session_id=str(base["session_id"]),
            )
        self.assertIsNotNone(found_v1)
        assert found_v1 is not None
        self.assertEqual(found_v1["session_id"], frozen["session_id"])
        self.assertEqual(done["session_id"], frozen["session_id"])
        self.assertEqual(finished["next_action"], ACTION_OWNER_CANDIDATE)
        v1 = next(
            row
            for row in finished["stages"]
            if row["representation_id"] == "NORMALIZED_TRAJECTORY_V1"
        )
        self.assertEqual(v1["session_id"], frozen["session_id"])
        self.assertEqual(v1["used_cohort_ids"], ["REL-C2"])
        self.assertEqual(retry["next_action"], ACTION_RETURN_EXISTING)
        self.assertEqual(retry["run_identity_sha256"], started["run_identity_sha256"])

    def test_f2_cli_missing_control_packet_is_observability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            self._no_worthy_base(data_root, store)
            payload = attach_ladder_freeze_preflight(
                {
                    "next_action": ACTION_START_V1,
                    "control_session_id": "HFIC-SESS-MISSINGPACKET01",
                    "owner_class": "FORGE_RUN_IN_PROGRESS",
                },
                data_root=data_root,
                store=store,
            )
        self.assertEqual(payload["next_action"], ACTION_OBSERVABILITY_BLOCKED)
        self.assertEqual(payload["owner_final"], ACTION_OBSERVABILITY_BLOCKED)
        self.assertEqual(payload["owner_class"], ACTION_OBSERVABILITY_BLOCKED)
        self.assertNotIn("ladder_freeze_preflight", payload)
        self.assertIn("FORGE_CONTEXT_ARTIFACT_MISSING", payload["blocking_reason_codes"])
        self.assertIn("status: BLOCKED", payload["owner_readout"])
        self.assertNotIn("continue V1 envelope", payload["owner_readout"])

    def test_f2_orphan_v1_without_parent_is_not_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            self._no_worthy_base(data_root, store)
            orphan_pre = _v1_preflight(
                data_root, store, control_session_id="HFIC-SESS-OTHERCONTROL01"
            )
            packet = dict(orphan_pre["forge_context_packet"])
            packet.pop("control_session_id", None)
            orphan_pre["forge_context_packet"] = packet
            orphan_pre.pop("control_session_id", None)
            digest = persist_forge_context_packet(
                data_root, packet, store=store, repo_root=ROOT
            )
            orphan_pre["forge_context_packet_sha256"] = digest
            draft = _current_v12_draft(orphan_pre)
            frozen = freeze_draft(draft, preflight_receipt=orphan_pre, repo_root=ROOT)
            persist_frozen_session(
                store,
                frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(draft["candidates"]),
                draft=draft,
            )
            store.rebuild_projection()
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                started = evaluate_forge_run(ROOT, data_root, persist=False)
        v1 = next(
            row
            for row in started["stages"]
            if row["representation_id"] == "NORMALIZED_TRAJECTORY_V1"
        )
        self.assertEqual(started["next_action"], ACTION_OBSERVABILITY_BLOCKED)
        self.assertIn(
            "SCIENTIFIC_SLOT_OCCUPIED_READBACK_MISSING",
            started["blocking_reason_codes"],
        )
        self.assertIsNone(v1["session_id"])
        self.assertEqual(v1["execution_status"], EXEC_NOT_RUN)
        self.assertIsInstance(started.get("session_id"), str)
        self.assertIn(
            "show-session --session-id " + str(started["session_id"]),
            started["owner_readout"],
        )

    def test_g4_marker_only_v1_freeze_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = self._no_worthy_base(data_root, store)
            control = _control_preflight(data_root, store)
            with self.assertRaises(LadderError) as raised:
                prepare_ladder_freeze_preflight(
                    control,
                    representation_id="NORMALIZED_TRAJECTORY_V1",
                    control_session_id=str(base["session_id"]),
                    challenger=None,
                )
        self.assertEqual(str(raised.exception), "LADDER_FREEZE_CHALLENGER_REQUIRED")
        with self.assertRaises(LadderError) as receipt_exc:
            prepare_ladder_freeze_preflight(
                control,
                representation_id="NORMALIZED_TRAJECTORY_V1",
                control_session_id=str(base["session_id"]),
                challenger={"control_session_id": str(base["session_id"])},
            )
        self.assertEqual(
            str(receipt_exc.exception), "LADDER_FREEZE_CONTROL_RECEIPT_REQUIRED"
        )

    def test_g4_freeze_without_ladder_challenger_packet_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = self._no_worthy_base(data_root, store, production_packet=True)
            v1_pre, _envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(base["session_id"]),
            )
            weak = dict(v1_pre)
            weak.pop("ladder_challenger_packet", None)
            draft = valid_draft()
            with self.assertRaises(HficSessionError) as raised:
                freeze_draft(
                    draft, preflight_receipt=weak, store=store, repo_root=ROOT
                )
        self.assertEqual(str(raised.exception), "LADDER_CHALLENGER_PACKET_REQUIRED")

    def test_g4_attach_tampered_challenger_is_observability_not_soft_pend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = self._no_worthy_base(data_root, store, production_packet=True)
            v1_pre, envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(base["session_id"]),
            )
            challenger = dict(envelope["challenger"])
            payload = dict(challenger["normalized_trajectory_v1"])
            payload["eligible_member_count"] = int(payload.get("eligible_member_count") or 0) + 1
            challenger["normalized_trajectory_v1"] = payload
            blocked = attach_ladder_freeze_preflight(
                {
                    "next_action": ACTION_START_V1,
                    "control_session_id": str(base["session_id"]),
                    "owner_class": "FORGE_RUN_IN_PROGRESS",
                    "challenger": challenger,
                },
                data_root=data_root,
                store=store,
            )
            self.assertEqual(blocked["next_action"], ACTION_OBSERVABILITY_BLOCKED)
            self.assertEqual(blocked["owner_final"], ACTION_OBSERVABILITY_BLOCKED)
            self.assertTrue(
                any(
                    str(code).startswith("LADDER_FREEZE_CHALLENGER_INVALID:")
                    for code in (blocked.get("blocking_reason_codes") or [])
                )
            )
            self.assertIn("freeze_block:", blocked["owner_readout"])
            self.assertNotIn("freeze_pending:", blocked["owner_readout"])
            self.assertNotIn("continue V1 envelope", blocked["owner_readout"])
            # Missing envelope still soft-pends START_V1.
            pending = attach_ladder_freeze_preflight(
                {
                    "next_action": ACTION_START_V1,
                    "control_session_id": str(base["session_id"]),
                    "owner_class": "FORGE_RUN_IN_PROGRESS",
                },
                data_root=data_root,
                store=store,
            )
            self.assertEqual(pending["next_action"], ACTION_START_V1)
            self.assertEqual(
                pending.get("ladder_freeze_pending_reason"),
                "LADDER_FREEZE_CHALLENGER_REQUIRED",
            )
            self.assertIn("freeze_pending:", pending["owner_readout"])
            self.assertNotIn("freeze_block:", pending["owner_readout"])

    def test_g4_classify_after_store_reload_keeps_ladder_slot(self) -> None:
        """PASS_TO_CLASSIFICATION intermediate must stamp slot before classify reload."""

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = self._no_worthy_base(data_root, store, production_packet=True)
            v1_pre, _envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(base["session_id"]),
            )
            draft = _current_v12_draft(v1_pre)
            frozen = freeze_draft(draft, preflight_receipt=v1_pre, repo_root=ROOT)
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
            store.rebuild_projection()
            awaiting = load_session_bundle(store, str(frozen["session_id"]))
            assert awaiting is not None
            self.assertEqual(awaiting["session_state"], "AWAITING_CLASSIFICATION")
            self.assertEqual(
                awaiting.get("ladder_representation_id"),
                "NORMALIZED_TRAJECTORY_V1",
            )
            self.assertEqual(awaiting.get("control_session_id"), base["session_id"])
            # Classify from store-reloaded bundle only (no in-memory freeze object).
            spec = _submission_for_frozen(awaiting)
            done = apply_classification(
                awaiting,
                spec,
                store=store,
                repo_root=ROOT,
                data_root=data_root,
            )
            store.rebuild_projection()
            complete = load_session_bundle(store, str(frozen["session_id"]))
            assert complete is not None
        self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
        self.assertEqual(
            complete.get("ladder_representation_id"),
            "NORMALIZED_TRAJECTORY_V1",
        )
        self.assertEqual(complete.get("control_session_id"), base["session_id"])
        self.assertIsInstance(complete.get("forge_context_packet_sha256"), str)

    def test_f3_foreign_parent_v2_is_not_consumed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = self._no_worthy_base(data_root, store)
            v1_draft = _distinct_no_worthy_draft(label="V1")
            v1_pre = _v1_preflight(data_root, store, control_session_id=str(base["session_id"]))
            v1_frozen = freeze_draft(v1_draft, preflight_receipt=v1_pre, repo_root=ROOT)
            persist_no_worthy_session(
                store,
                v1_frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(v1_draft["candidates"]),
                draft=v1_draft,
                preflight_receipt=v1_pre,
            )
            v2_draft = valid_draft()
            v2_pre = _v2_preflight(data_root, store, control_session_id="HFIC-SESS-FOREIGNCONTROL1")
            v2_frozen = freeze_draft(v2_draft, preflight_receipt=v2_pre, repo_root=ROOT)
            persist_frozen_session(
                store,
                v2_frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(v2_draft["candidates"]),
                draft=v2_draft,
                representation_registry=_later_registry(),
            )
            packet = v2_frozen["critic_input_packet"]
            assert isinstance(packet, dict)
            finalize_session(
                v2_frozen,
                critic_result_from_packet_only(packet, "PASS_TO_CLASSIFICATION"),
                store=store,
                repo_root=ROOT,
            )
            store.rebuild_projection()
            registry = _later_registry()
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                finished = evaluate_forge_run(
                    ROOT, data_root, persist=False, registry=registry
                )
        self.assertEqual(finished["next_action"], "START_SYNTHETIC_LATER_V2")
        self.assertNotEqual(finished["next_action"], ACTION_OWNER_CANDIDATE)

    def test_n1_fresh_normal_entry_preselects_control_surface(self) -> None:
        """Empty store: forge-run chooses CONTROL-compatible START_BASE before generation."""

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                started = evaluate_forge_run(ROOT, data_root, persist=False)
        self.assertEqual(started["next_action"], ACTION_START_BASE)
        self.assertIsNone(started["owner_final"])
        self.assertIn("CONTROL_SURFACE_REQUIRED", started["blocking_reason_codes"])
        self.assertIn("CONTROL-compatible BASE", started["owner_readout"])
        base = started["stages"][0]
        self.assertEqual(base["execution_status"], EXEC_NOT_RUN)
        self.assertIsNone(base["session_id"])
        self.assertEqual(base["reason_code"], "CONTROL_SURFACE_REQUIRED")

    def test_n1_ordinary_final_pass_is_honest_candidate_readback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            ordinary = _ordinary_stamped_preflight(data_root, store)
            draft = valid_draft()
            frozen = freeze_draft(draft, preflight_receipt=ordinary, repo_root=ROOT)
            persist_frozen_session(
                store,
                frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(draft["candidates"]),
                draft=draft,
            )
            critic_packet = frozen["critic_input_packet"]
            assert isinstance(critic_packet, dict)
            finalize_session(
                frozen,
                critic_result_from_packet_only(critic_packet, "PASS_TO_CLASSIFICATION"),
                store=store,
                repo_root=ROOT,
            )
            store.rebuild_projection()
            spec = _submission_for_frozen(frozen)
            done = apply_classification(
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
                readback = evaluate_forge_run(ROOT, data_root, persist=False)
        self.assertEqual(done["session_state"], "SYNTHESIS_COMPLETE")
        self.assertIn(done["critic_terminal"], PASS_TERMINALS | CASE_A_TERMINALS)
        self.assertEqual(readback["next_action"], ACTION_OWNER_CANDIDATE)
        self.assertEqual(readback["owner_final"], ACTION_OWNER_CANDIDATE)
        self.assertNotIn("CONTROL_SURFACE_REQUIRED", readback["blocking_reason_codes"])
        base = readback["stages"][0]
        self.assertEqual(base["session_id"], frozen["session_id"])
        self.assertEqual(base["effective_terminal"], done["critic_terminal"])
        self.assertEqual(base["input_scope"], "ORDINARY_BASE")

    def test_n1_ordinary_pending_classify_resumes_same_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            ordinary = _ordinary_stamped_preflight(data_root, store)
            draft = valid_draft()
            frozen = freeze_draft(draft, preflight_receipt=ordinary, repo_root=ROOT)
            persist_frozen_session(
                store,
                frozen,
                repo_root=ROOT,
                identities=assign_portfolio_ids(draft["candidates"]),
                draft=draft,
            )
            critic_packet = frozen["critic_input_packet"]
            assert isinstance(critic_packet, dict)
            awaiting = finalize_session(
                frozen,
                critic_result_from_packet_only(critic_packet, "PASS_TO_CLASSIFICATION"),
                store=store,
                repo_root=ROOT,
            )
            store.rebuild_projection()
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                pending = evaluate_forge_run(ROOT, data_root, persist=False)
        self.assertEqual(awaiting["session_state"], "AWAITING_CLASSIFICATION")
        self.assertEqual(pending["next_action"], ACTION_RESUME_BASE)
        self.assertIsNone(pending["owner_final"])
        self.assertNotIn("CONTROL_SURFACE_REQUIRED", pending["blocking_reason_codes"])
        base = pending["stages"][0]
        self.assertEqual(base["session_id"], frozen["session_id"])
        self.assertEqual(base["session_state"], "AWAITING_CLASSIFICATION")
        self.assertEqual(base["input_scope"], "ORDINARY_BASE")

    def test_i1_outer_search_key_drift_rejects_before_child_persist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = self._no_worthy_base(data_root, store, production_packet=True)
            v1_pre, _envelope = _v1_freeze_preflight_from_envelope(
                data_root,
                store,
                control_session_id=str(base["session_id"]),
            )
            before = {
                str(item.get("session_id") or "") for item in list_hfic_sessions(store)
            }
            weak = dict(v1_pre)
            weak["search_key_sha256"] = "ff" * 32
            self.assertNotEqual(
                weak["search_key_sha256"],
                v1_pre["forge_context_packet"]["representation_search_key_sha256"],
            )
            with self.assertRaises(HficSessionError) as raised:
                freeze_draft(
                    valid_draft(),
                    preflight_receipt=weak,
                    store=store,
                    repo_root=ROOT,
                )
            store.rebuild_projection()
            after = {
                str(item.get("session_id") or "") for item in list_hfic_sessions(store)
            }
        self.assertEqual(str(raised.exception), "LADDER_SEARCH_KEY_DRIFT")
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
