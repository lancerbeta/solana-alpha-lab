"""A4 representation ladder: deterministic transitions, run receipt, no-write compatibility.

Does not execute Prompt A/B/C, Independent Critic, or the scientific V1 probe.
"""

from __future__ import annotations

import hashlib
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

from solana_alpha_lab.factory.data_root import (  # noqa: E402
    instance_fingerprint,
    resolve_data_root,
    resolve_existing_data_root,
)
from solana_alpha_lab.factory.document_runner import repository_git_snapshot  # noqa: E402
from solana_alpha_lab.factory.hfic_identity import assign_portfolio_ids  # noqa: E402
from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    RUNNER_UP_AWAITING_CRITIC,
    find_session_by_epoch_focus,
    freeze_draft,
    persist_frozen_session,
    persist_no_worthy_session,
    finalize_session,
    load_session_bundle,
)
from solana_alpha_lab.factory.hfic_representation_probe import (  # noqa: E402
    CONTROL_CONTEXT_KIND_FORGE,
    control_baseline_from_receipt,
)
from solana_alpha_lab.factory.forge_input_receipt import (  # noqa: E402
    OWNER_CLASS_INPUT_NOT_READY,
    OWNER_CLASS_OBSERVABILITY_BLOCKED,
)
from solana_alpha_lab.factory.hfic_control_integrity import (  # noqa: E402
    CURRENT_REPRESENTATION_CONTROL_V1,
)
from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    is_fast_lane_commissioned,
    persist_forge_context_packet,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402
from solana_alpha_lab.factory.run_passport import canonical_sha256  # noqa: E402
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
    EXEC_REUSED,
    EXISTING_V1_CONTROL_SESSION_ID,
    HANDLER_SYNTHETIC_LATER_V2,
    LadderError,
    consume_start_v1_envelope,
    control_preflight_from_bundle,
    evaluate_forge_run,
    format_forge_run_owner_readout,
    load_ladder_registry,
    prepare_ladder_freeze_preflight,
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

NO_WORTHY_DRAFT = ROOT / "tests/fixtures/hypothesis_forge/draft_no_worthy_v1.json"


def _control_preflight(data_root: Path, store: ResearchStore) -> dict[str, object]:
    git = repository_git_snapshot(ROOT)
    packet = {
        "schema": "smial.forge-context-packet",
        "owner_focus": "AUTO",
        "evidence_epoch_sha256": "aa" * 32,
        "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
        "capability_ids": ["CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"],
        "vision_integrity": {"status": "PASS"},
        "ladder_representation_id": "BASE",
        "visible_cohort_ids": ["REL-C1", "REL-C2"],
        "bound_visible_cohort_ids": ["REL-C1", "REL-C2"],
    }
    digest = persist_forge_context_packet(
        data_root,
        packet,
        store=store,
        repo_root=ROOT,
    )
    return {
        "receipt_id": "HFIC-PREFLIGHT-FIXTURE-001",
        "evidence_epoch_sha256": "aa" * 32,
        "focus_key_sha256": "bb" * 32,
        "search_key_sha256": "cc" * 32,
        "owner_focus": "AUTO",
        "live_git_head": git.head_sha.lower(),
        "git_composite_sha256": git.composite_sha256,
        "session_started_at": "2026-08-27T12:00:00Z",
        "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
        "forge_context_packet_sha256": digest,
        "forge_context_packet": packet,
    }


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

    def test_ordinary_no_worthy_is_control_required(self) -> None:
        decision = resolve_next_action(
            [_base(evidence_surface_mode=None, input_scope="ORDINARY_BASE")]
        )
        self.assertEqual(decision["next_action"], ACTION_CONTROL_REQUIRED)

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
                "owner_class": "OWNER_FINAL",
                "next_action": ACTION_KEEP_PAUSE,
                "owner_final": ACTION_KEEP_PAUSE,
                "stages": [],
                "writes": {"research_store": 0, "forge_run": 0, "session": 0},
                "blocking_reason_codes": [],
            }
        )
        self.assertIn("status: NEXT", text)
        self.assertNotIn("status: DONE", text)

    def test_control_required_readout_is_ordinary_evening_done(self) -> None:
        text = format_forge_run_owner_readout(
            {
                "run_id": "FORGE-RUN-TEST",
                "owner_class": "OWNER_FINAL",
                "next_action": ACTION_CONTROL_REQUIRED,
                "owner_final": ACTION_CONTROL_REQUIRED,
                "stages": [],
                "writes": {"research_store": 0, "forge_run": 0, "session": 0},
                "blocking_reason_codes": [],
            }
        )
        self.assertIn("status: DONE", text)
        self.assertIn("CONTROL_REQUIRED", text)
        self.assertNotIn("status: NEXT", text)

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
            first = evaluate_forge_run(
                ROOT, data_root, persist=True, stages=stages, existing_completed=False
            )
            self.assertEqual(first["writes"]["forge_run"], 1)
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
            first = evaluate_forge_run(
                ROOT, data_root, persist=True, stages=stages, existing_completed=False
            )
            self.assertEqual(first["next_action"], ACTION_RESUME_BASE)
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
        self.assertEqual(receipt["control_session_id"], EXISTING_V1_CONTROL_SESSION_ID)
        self.assertEqual(receipt["next_action"], ACTION_START_V1)
        self.assertIsNone(receipt["owner_final"])
        self.assertNotEqual(receipt["next_action"], ACTION_SEARCH_EXHAUSTED)
        self.assertEqual(
            receipt["legacy_epoch_sha256"],
            "456411903174e403092f115cddf62fd38c9ae1bb943ebba0048c5b6bd070854e",
        )


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
        self.assertIn("re-run `forge-run`", skill.lower())
        self.assertNotIn("dormant wiring", skill)
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
            envelope["challenger"].get("ladder_representation_id"),
            "NORMALIZED_TRAJECTORY_V1",
        )
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

                def _enumerate_c3(_data_root: Path):
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
) -> dict[str, object]:
    git = repository_git_snapshot(ROOT)
    packet = {
        "schema": "smial.forge-context-packet",
        "owner_focus": "AUTO",
        "evidence_epoch_sha256": "aa" * 32,
        "capability_ids": ["CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"],
        "vision_integrity": {"status": "PASS"},
        "ladder_representation_id": "NORMALIZED_TRAJECTORY_V1",
        "visible_cohort_ids": list(cohorts or ["REL-C2"]),
        "bound_visible_cohort_ids": list(cohorts or ["REL-C2"]),
        "control_session_id": control_session_id,
    }
    digest = persist_forge_context_packet(
        data_root, packet, store=store, repo_root=ROOT
    )
    return {
        "receipt_id": "HFIC-PREFLIGHT-V1-FIXTURE-001",
        "evidence_epoch_sha256": "aa" * 32,
        "focus_key_sha256": "bb" * 32,
        "search_key_sha256": "dd" * 32,
        "owner_focus": "AUTO",
        "live_git_head": git.head_sha.lower(),
        "git_composite_sha256": git.composite_sha256,
        "session_started_at": "2026-08-27T12:00:00Z",
        "forge_context_packet_sha256": digest,
        "forge_context_packet": packet,
    }


def _v2_preflight(
    data_root: Path,
    store: ResearchStore,
    *,
    control_session_id: str,
) -> dict[str, object]:
    git = repository_git_snapshot(ROOT)
    packet = {
        "schema": "smial.forge-context-packet",
        "owner_focus": "AUTO",
        "evidence_epoch_sha256": "aa" * 32,
        "capability_ids": ["CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"],
        "vision_integrity": {"status": "PASS"},
        "ladder_representation_id": "SYNTHETIC_LATER_V2",
        "visible_cohort_ids": ["REL-C2"],
        "bound_visible_cohort_ids": ["REL-C2"],
        "control_session_id": control_session_id,
    }
    digest = persist_forge_context_packet(
        data_root, packet, store=store, repo_root=ROOT
    )
    return {
        "receipt_id": "HFIC-PREFLIGHT-V2-FIXTURE-001",
        "evidence_epoch_sha256": "aa" * 32,
        "focus_key_sha256": "bb" * 32,
        "search_key_sha256": "ee" * 32,
        "owner_focus": "AUTO",
        "live_git_head": git.head_sha.lower(),
        "git_composite_sha256": git.composite_sha256,
        "session_started_at": "2026-08-27T12:00:00Z",
        "forge_context_packet_sha256": digest,
        "forge_context_packet": packet,
    }


def _distinct_no_worthy_draft(*, label: str) -> dict[str, object]:
    draft = json.loads(NO_WORTHY_DRAFT.read_text(encoding="utf-8"))
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
    def _no_worthy_base(self, data_root: Path, store: ResearchStore) -> dict[str, object]:
        draft = json.loads(NO_WORTHY_DRAFT.read_text(encoding="utf-8"))
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
        return frozen

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

            def _enumerate_c3(_data_root: Path):
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
            base = self._no_worthy_base(data_root, store)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                started = evaluate_forge_run(ROOT, data_root, persist=True)
            self.assertEqual(started["next_action"], ACTION_START_V1)
            self.assertEqual(started["writes"]["forge_run"], 1)
            envelope = consume_start_v1_envelope(
                {"next_action": started["next_action"], "owner_final": started["owner_final"]},
                control_receipt=_no_worthy_forge_receipt(),
                representation=_representation_fixture(),
                cohort_readiness_receipt=_cohort_readiness_receipt(),
                base_x_population_n=10,
            )
            self.assertFalse(envelope["fake_critic_packet"])
            self.assertEqual(
                envelope["challenger"].get("ladder_representation_id"),
                "NORMALIZED_TRAJECTORY_V1",
            )
            draft = valid_draft()
            v1_pre = prepare_ladder_freeze_preflight(
                _control_preflight(data_root, store),
                representation_id="NORMALIZED_TRAJECTORY_V1",
                control_session_id=str(base["session_id"]),
            )
            v1_pre["forge_context_packet"]["visible_cohort_ids"] = ["REL-C2"]
            v1_pre["forge_context_packet"]["bound_visible_cohort_ids"] = ["REL-C2"]
            digest = persist_forge_context_packet(
                data_root,
                v1_pre["forge_context_packet"],
                store=store,
                repo_root=ROOT,
            )
            v1_pre["forge_context_packet_sha256"] = digest
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
            self.assertEqual(mid["writes"]["forge_run"], 1)
            packet = frozen["critic_input_packet"]
            assert isinstance(packet, dict)
            done = finalize_session(
                frozen,
                critic_result_from_packet_only(packet, "PASS_TO_CLASSIFICATION"),
                store=store,
                repo_root=ROOT,
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
        self.assertEqual(finished["next_action"], ACTION_OWNER_CANDIDATE)
        self.assertEqual(finished["writes"]["forge_run"], 1)
        self.assertEqual(v1["session_id"], frozen["session_id"])
        self.assertIsInstance(v1["stage_ref_sha256"], str)
        self.assertEqual(len(str(v1["stage_ref_sha256"])), 64)
        self.assertEqual(v1["used_cohort_ids"], ["REL-C2"])
        self.assertNotEqual(v1["used_cohort_ids"], finished["visible_cohort_ids"])
        self.assertIn("candidate:", finished["owner_readout"])
        self.assertEqual(retry["next_action"], ACTION_RETURN_EXISTING)
        self.assertEqual(retry["run_identity_sha256"], started["run_identity_sha256"])
        self.assertEqual(done["session_id"], frozen["session_id"])

    def test_f2_v1_negative_exhaustion_then_retry_readback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            base = self._no_worthy_base(data_root, store)
            draft = _distinct_no_worthy_draft(label="V1")
            v1_pre = prepare_ladder_freeze_preflight(
                _control_preflight(data_root, store),
                representation_id="NORMALIZED_TRAJECTORY_V1",
                control_session_id=str(base["session_id"]),
            )
            digest = persist_forge_context_packet(
                data_root,
                v1_pre["forge_context_packet"],
                store=store,
                repo_root=ROOT,
            )
            v1_pre["forge_context_packet_sha256"] = digest
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
            v1_pre = prepare_ladder_freeze_preflight(
                control,
                representation_id="NORMALIZED_TRAJECTORY_V1",
                control_session_id=str(base["session_id"]),
            )
            digest = persist_forge_context_packet(
                data_root,
                v1_pre["forge_context_packet"],
                store=store,
                repo_root=ROOT,
            )
            v1_pre["forge_context_packet_sha256"] = digest
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
            base = self._no_worthy_base(data_root, store)
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_live,
            ):
                started = evaluate_forge_run(ROOT, data_root, persist=True)
            self.assertEqual(started["next_action"], ACTION_START_V1)
            bundle = load_session_bundle(store, str(base["session_id"]))
            assert bundle is not None
            packet = _packet_for_bundle(data_root, bundle, store)
            self.assertIsInstance(packet, dict)
            assert isinstance(packet, dict)
            self.assertEqual((packet.get("vision_integrity") or {}).get("status"), "PASS")
            v1_pre = prepare_ladder_freeze_preflight(
                control_preflight_from_bundle(bundle, packet),
                representation_id="NORMALIZED_TRAJECTORY_V1",
                control_session_id=str(base["session_id"]),
            )
            v1_pre["forge_context_packet"]["visible_cohort_ids"] = ["REL-C2"]
            v1_pre["forge_context_packet"]["bound_visible_cohort_ids"] = ["REL-C2"]
            draft = valid_draft()
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
            done = finalize_session(
                frozen,
                critic_result_from_packet_only(packet_out, "PASS_TO_CLASSIFICATION"),
                store=store,
                repo_root=ROOT,
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

    def test_f2_orphan_v1_without_parent_is_not_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            self._no_worthy_base(data_root, store)
            orphan_pre = _v1_preflight(data_root, store, control_session_id="HFIC-SESS-OTHERCONTROL01")
            packet = dict(orphan_pre["forge_context_packet"])
            packet.pop("control_session_id", None)
            orphan_pre["forge_context_packet"] = packet
            digest = persist_forge_context_packet(
                data_root, packet, store=store, repo_root=ROOT
            )
            orphan_pre["forge_context_packet_sha256"] = digest
            draft = valid_draft()
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
        self.assertEqual(started["next_action"], ACTION_START_V1)
        self.assertIsNone(v1["session_id"])
        self.assertEqual(v1["execution_status"], EXEC_NOT_RUN)

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


if __name__ == "__main__":
    unittest.main()
