"""Packet-1.4 classification must persist one typed terminal.

SYNTHETIC_AUDIT_FIXTURE only. T-A and T-B reproduce the base defects:
observation-route false PASS, and an exception that strands AWAITING_CLASSIFICATION.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    persist_forge_context_packet,
)
from unittest import mock

from solana_alpha_lab.factory.hfic_control_integrity import (  # noqa: E402
    DENY_HFIC_AVAILABILITY_GATE,
    DIRECT_CLASSIFIER_HFIC_TERMINAL,
    classifier_route_requires_availability_gate,
)
from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    HficSessionError,
    _classifier_to_hfic_terminal,
    apply_classification,
    finalize_session,
    freeze_draft,
    load_session_bundle,
    run_live_classifier,
    validate_live_classifier_receipt,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
)
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402
from tests.test_fast_lane_classifier import experiment_spec  # noqa: E402
from tests.test_hfic_packet14_availability_fast_lane_guard_v1 import (  # noqa: E402
    _draft,
    _freeze,
    _grounded_preflight,
    _mutate_selected,
    _selected,
)
from tests.test_hfic_session import _critic_result, critic_result_from_packet_only  # noqa: E402
from tests.test_observation_fast_lane_routing_closure import (  # noqa: E402
    AS_OF_NOON,
    persist_covering_snapshot,
    v1_2_spec,
)
from solana_alpha_lab.factory.observation_fast_lane_terminals import (  # noqa: E402
    OBSERVATION_CHANGE_LANE_TERMINALS,
    OBSERVATION_DENY_TERMINALS,
    OBSERVATION_FAST_LANE_TERMINALS,
)

FORWARD_LABEL = "HFIC-V12-C3-FORWARD-QUOTE"
RUNNER_LABEL = "HFIC-V12-C2-HISTORICAL-RETURN"
FORWARD_FEAT = "FEAT-QUOTE-AVAILABILITY"


def _freeze_bound(data_root: Path, selected_label: str = FORWARD_LABEL, runner_label: str = RUNNER_LABEL) -> dict:
    packet = {
        "capability_ids": ["CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"],
        "marker": "SYNTHETIC_AUDIT_FIXTURE",
        "vision_integrity": {"status": "PASS"},
    }
    digest = persist_forge_context_packet(data_root, packet, repo_root=ROOT)
    receipt = _grounded_preflight()
    receipt["forge_context_packet_sha256"] = digest
    receipt["forge_context_packet"] = packet
    draft = _draft()
    for card in draft["candidates"]:
        if card["label"] == FORWARD_LABEL:
            card["required_feature_ids"] = [FORWARD_FEAT]
            card["unresolved_requirements"] = []
    draft["selected_candidate_ref"] = selected_label
    draft["runner_up_candidate_ref"] = runner_label
    return freeze_draft(draft, preflight_receipt=receipt, repo_root=ROOT)


def _awaiting_store(data_root: Path, frozen: dict) -> ResearchStore:
    store = ResearchStore(data_root)
    finalize_session(
        frozen,
        _critic_result(frozen, "PASS_TO_CLASSIFICATION"),
        store=store,
        repo_root=ROOT,
        data_root=data_root,
    )
    return store


def _observation_packet(frozen: dict) -> dict:
    selected = _selected(frozen)
    spec = v1_2_spec(
        mode="REUSE_OR_SCHEDULE",
        role="EXPLORATORY_REUSE",
        as_of="2026-09-01T12:00:00Z",
        availability_cutoff="2026-09-01T12:00:00Z",
    )
    spec["required_feature_ids"] = list(selected["required_feature_ids"])
    return {
        "experiment_spec": spec,
        "hypothesis_definition_sha256": frozen["selected_definition_sha256"],
        "classifier_evaluated_at": AS_OF_NOON.isoformat().replace("+00:00", "Z"),
    }


def _fast_lane_packet(frozen: dict) -> dict:
    selected = _selected(frozen)
    spec = experiment_spec()
    spec["required_feature_ids"] = list(selected["required_feature_ids"])
    return {
        "experiment_spec": spec,
        "hypothesis_definition_sha256": frozen["selected_definition_sha256"],
    }


def _panel_root(tmp: str) -> Path:
    data_root = Path(tmp)
    covering = load_observation_schedule(
        ROOT, "tests/fixtures/observation_schedule/common_panel.yaml"
    )
    persist_covering_snapshot(data_root, covering)
    return data_root


def _readback(data_root: Path) -> dict[str, object]:
    from solana_alpha_lab.factory.hfic_preflight import run_preflight
    from solana_alpha_lab.factory.hfic_representation_ladder import evaluate_forge_run

    preflight_error = None
    forge_error = None
    preflight: dict = {}
    forge: dict = {}
    try:
        preflight = run_preflight(
            ROOT,
            data_root,
            owner_focus="AUTO",
            auto_commission=False,
            persist=False,
        )
    except Exception as exc:  # noqa: BLE001 — RED diagnostic only
        preflight_error = f"{type(exc).__name__}:{exc}"
    try:
        forge = evaluate_forge_run(
            ROOT,
            data_root,
            owner_focus="AUTO",
            persist=False,
        )
    except Exception as exc:  # noqa: BLE001 — RED diagnostic only
        forge_error = f"{type(exc).__name__}:{exc}"
    return {
        "preflight_action": preflight.get("action"),
        "preflight_next": preflight.get("next"),
        "preflight_terminal": preflight.get("terminal"),
        "preflight_error": preflight_error,
        "forge_next": forge.get("next_action"),
        "forge_reason": forge.get("reason_code"),
        "forge_error": forge_error,
    }


def _requires_classify(readback: dict[str, object]) -> bool:
    if readback.get("preflight_action") == "RESUME_CLASSIFY":
        return True
    if readback.get("forge_next") in {"RESUME_BASE", "RESUME_CLASSIFY"} and (
        readback.get("forge_reason") == "AWAITING_CLASSIFICATION"
        or readback.get("preflight_action") == "RESUME_CLASSIFY"
    ):
        return True
    text = " ".join(str(item) for item in readback.values())
    return "RESUME_CLASSIFY" in text or "AWAITING_CLASSIFICATION" in text


class ClassificationOutcomeIntegrityTests(unittest.TestCase):
    def test_t_a_observation_route_non_pit_is_persisted_kill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = _panel_root(tmp)
            frozen = _freeze_bound(data_root)
            selected = _selected(frozen)
            self.assertEqual(selected["required_feature_ids"], [FORWARD_FEAT])
            self.assertEqual(
                selected["grounding"]["feature_bindings"][0]["availability_class"],
                "FORWARD_ONLY",
            )
            store = _awaiting_store(data_root, frozen)
            done = apply_classification(
                frozen,
                _observation_packet(frozen),
                store=store,
                repo_root=ROOT,
                data_root=data_root,
            )
            if (
                done.get("session_state") == "SYNTHESIS_COMPLETE"
                and done.get("critic_terminal") == "PASS_FAST_LANE_READY"
            ):
                self.fail(
                    "RED T-A false PASS "
                    f"state={done.get('session_state')} "
                    f"terminal={done.get('critic_terminal')} "
                    f"lane={done.get('lane_classifier_terminal')}"
                )
            self.assertEqual(done.get("session_state"), "RUNNER_UP_AWAITING_CRITIC")
            self.assertEqual(done.get("critic_terminal"), "KILL_UNBOUND_EVIDENCE")
            receipt = done.get("classifier_receipt") or {}
            self.assertEqual(
                receipt.get("lane_classifier_terminal"),
                "DENY_HFIC_AVAILABILITY_GATE",
            )
            self.assertEqual(receipt.get("classifier_route_terminal"), "PANEL_REUSE_READY")
            self.assertIn(
                "REQUIRED_BINDING_NOT_PIT_READY:FEAT-QUOTE-AVAILABILITY",
                receipt.get("reason_codes") or [],
            )

    def test_t_b_fast_lane_gate_failure_is_persisted_not_stranded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            frozen = _freeze_bound(data_root)
            store = _awaiting_store(data_root, frozen)
            try:
                done = apply_classification(
                    frozen,
                    _fast_lane_packet(frozen),
                    store=store,
                    repo_root=ROOT,
                    data_root=data_root,
                )
            except HficSessionError as exc:
                from solana_alpha_lab.factory.hfic_preflight import (
                    decide_preflight_action,
                    list_hfic_sessions,
                )

                sessions = list_hfic_sessions(store)
                row = sessions[0] if sessions else {}
                router = decide_preflight_action(
                    sessions,
                    search_key=str(row.get("search_key_sha256") or ""),
                    evidence_epoch=str(row.get("evidence_epoch_sha256") or ""),
                    focus_key=str(row.get("focus_key_sha256") or ""),
                    owner_focus=str(row.get("owner_focus") or "AUTO"),
                    memory_eligibility_sha256=row.get("memory_eligibility_sha256"),
                )
                bundle = load_session_bundle(store, str(frozen["session_id"]))
                state = None if bundle is None else bundle.get("session_state")
                readback = _readback(data_root)
                readback["session_router"] = router[0]
                self.fail(
                    "RED T-B stranded "
                    f"raised={exc} state={state} "
                    f"requires_classify={_requires_classify(readback)} "
                    f"readback={readback}"
                )
            self.assertNotEqual(done.get("session_state"), "AWAITING_CLASSIFICATION")
            self.assertEqual(done.get("critic_terminal"), "KILL_UNBOUND_EVIDENCE")
            bundle = load_session_bundle(store, str(frozen["session_id"]))
            self.assertIsNotNone(bundle)
            assert bundle is not None
            self.assertNotEqual(bundle.get("session_state"), "AWAITING_CLASSIFICATION")
            readback = _readback(data_root)
            self.assertFalse(_requires_classify(readback), readback)

    def test_t_c_terminal_by_feature_class_matrix(self) -> None:
        terminals = set(DIRECT_CLASSIFIER_HFIC_TERMINAL) | set(
            OBSERVATION_FAST_LANE_TERMINALS
        ) | set(OBSERVATION_CHANGE_LANE_TERMINALS) | set(OBSERVATION_DENY_TERMINALS)
        self.assertIn("DENY_INTEGRITY_MISMATCH", terminals)
        self.assertEqual(
            _classifier_to_hfic_terminal(
                {"lane_classifier_terminal": "DENY_INTEGRITY_MISMATCH"}
            ),
            "KILL_UNBOUND_EVIDENCE",
        )
        cases = {
            "pit": _freeze("HFIC-V12-C1-PIT-LIQUIDITY-RATIO", FORWARD_LABEL),
            "forward": _freeze(FORWARD_LABEL, RUNNER_LABEL),
            "historical": _freeze(RUNNER_LABEL, FORWARD_LABEL),
            "missing": _freeze(
                "HFIC-V12-C1-PIT-LIQUIDITY-RATIO",
                FORWARD_LABEL,
                required_feature_ids=["FEAT-AGE-SINCE-CREATION"],
            ),
            "unresolved": _mutate_selected(
                _freeze("HFIC-V12-C1-PIT-LIQUIDITY-RATIO", FORWARD_LABEL),
                lambda selected: selected.__setitem__(
                    "unresolved_requirements", ["SYNTHETIC_AUDIT_FIXTURE"]
                ),
            ),
            "no_required": _mutate_selected(
                _freeze("HFIC-V12-C1-PIT-LIQUIDITY-RATIO", FORWARD_LABEL),
                lambda selected: selected.__setitem__("required_feature_ids", []),
            ),
        }
        denying = {"forward", "historical", "missing", "unresolved"}
        for kind, frozen in cases.items():
            selected = _selected(frozen)
            spec = experiment_spec()
            if selected["required_feature_ids"]:
                spec["required_feature_ids"] = list(selected["required_feature_ids"])
            for terminal in sorted(terminals):
                raw_hfic = _classifier_to_hfic_terminal(
                    {"lane_classifier_terminal": terminal}
                )
                expected = (
                    "KILL_UNBOUND_EVIDENCE"
                    if raw_hfic == "PASS_FAST_LANE_READY" and kind in denying
                    else raw_hfic
                )
                receipt = mock_classify(frozen, spec, terminal)
                with self.subTest(kind=kind, terminal=terminal):
                    self.assertEqual(_classifier_to_hfic_terminal(receipt), expected)

    def test_t_d_every_pass_route_is_gated(self) -> None:
        frozen = _freeze(FORWARD_LABEL, RUNNER_LABEL)
        spec = experiment_spec()
        spec["required_feature_ids"] = list(_selected(frozen)["required_feature_ids"])
        terminals = set(DIRECT_CLASSIFIER_HFIC_TERMINAL) | set(
            OBSERVATION_FAST_LANE_TERMINALS
        ) | set(OBSERVATION_CHANGE_LANE_TERMINALS) | set(OBSERVATION_DENY_TERMINALS)
        for terminal in sorted(terminals):
            mapped = _classifier_to_hfic_terminal({"lane_classifier_terminal": terminal})
            self.assertEqual(
                classifier_route_requires_availability_gate(terminal),
                mapped == "PASS_FAST_LANE_READY",
            )
            if mapped != "PASS_FAST_LANE_READY":
                continue
            receipt = mock_classify(frozen, spec, terminal)
            self.assertEqual(
                receipt["lane_classifier_terminal"], DENY_HFIC_AVAILABILITY_GATE
            )

    def test_t_e_critic_claimed_pass_is_downgraded_not_mismatched(self) -> None:
        from solana_alpha_lab.factory.hfic_session import show_session

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            frozen = _freeze_bound(data_root)
            store = _awaiting_store(data_root, frozen)
            honest = run_live_classifier(
                _fast_lane_packet(frozen),
                frozen,
                repo_root=ROOT,
                data_root=data_root,
            )
            claimed = _critic_result(frozen, "PASS_FAST_LANE_READY")
            claimed["classifier_receipt"] = honest
            claimed["experiment_spec_packet"] = _fast_lane_packet(frozen)
            done = finalize_session(
                frozen,
                claimed,
                store=store,
                repo_root=ROOT,
                data_root=data_root,
            )
            self.assertEqual(done.get("critic_terminal"), "KILL_UNBOUND_EVIDENCE")
            self.assertEqual(done.get("critic_claimed_terminal"), "PASS_FAST_LANE_READY")
            shown = show_session(store, frozen["session_id"], repo_root=ROOT)
            self.assertEqual(shown.get("classifier_route_terminal"), "FAST_LANE_READY")
            self.assertIn("persisted_KILL_not_error", shown["owner_readout"])
            self.assertIn("PASS_FAST_LANE_READY", shown["owner_readout"])
            self.assertNotIn(str(data_root), shown["owner_readout"])
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            pit = _freeze_bound(
                data_root,
                "HFIC-V12-C1-PIT-LIQUIDITY-RATIO",
                FORWARD_LABEL,
            )
            honest_pass = run_live_classifier(
                _fast_lane_packet(pit),
                pit,
                repo_root=ROOT,
                data_root=data_root,
            )
            other = _critic_result(pit, "PASS_DATA_OPTION_REQUIRED")
            other["classifier_receipt"] = honest_pass
            other["experiment_spec_packet"] = _fast_lane_packet(pit)
            store = _awaiting_store(data_root, pit)
            with self.assertRaises(HficSessionError) as raised:
                finalize_session(
                    pit,
                    other,
                    store=store,
                    repo_root=ROOT,
                    data_root=data_root,
                )
            self.assertEqual(str(raised.exception), "CLASSIFIER_TERMINAL_MISMATCH")

    def test_t_f_runner_up_kill_is_final_without_c3(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            frozen = _freeze_bound(data_root)
            store = _awaiting_store(data_root, frozen)
            parked = apply_classification(
                frozen,
                _fast_lane_packet(frozen),
                store=store,
                repo_root=ROOT,
                data_root=data_root,
            )
            self.assertEqual(parked.get("session_state"), "RUNNER_UP_AWAITING_CRITIC")
            waiting = finalize_session(
                parked,
                critic_result_from_packet_only(
                    parked["runner_up_critic_input_packet"],
                    "PASS_TO_CLASSIFICATION",
                ),
                store=store,
                repo_root=ROOT,
                data_root=data_root,
            )
            self.assertEqual(waiting.get("session_state"), "AWAITING_CLASSIFICATION")
            runner_packet = _fast_lane_packet(frozen)
            runner_ids = parked["runner_up_critic_input_packet"]["selected_candidate"][
                "required_feature_ids"
            ]
            runner_packet["experiment_spec"]["required_feature_ids"] = list(runner_ids)
            runner_packet["hypothesis_definition_sha256"] = frozen[
                "runner_up_definition_sha256"
            ]
            done = apply_classification(
                waiting,
                runner_packet,
                store=store,
                repo_root=ROOT,
                data_root=data_root,
            )
            self.assertEqual(done.get("session_state"), "SYNTHESIS_COMPLETE")
            self.assertEqual(done.get("final_session_terminal"), "KILL_UNBOUND_EVIDENCE")
            self.assertEqual(done.get("critic_screen_count"), 2)

    def test_t_g_pit_ready_passes_on_both_routes(self) -> None:
        context = {
            "capability_ids": ["CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"],
            "marker": "SYNTHETIC_AUDIT_FIXTURE",
            "vision_integrity": {"status": "PASS"},
        }

        def bound(data_root: Path) -> dict:
            digest = persist_forge_context_packet(data_root, context, repo_root=ROOT)
            receipt = _grounded_preflight()
            receipt["forge_context_packet_sha256"] = digest
            receipt["forge_context_packet"] = context
            draft = _draft()
            draft["selected_candidate_ref"] = "HFIC-V12-C1-PIT-LIQUIDITY-RATIO"
            draft["runner_up_candidate_ref"] = FORWARD_LABEL
            return freeze_draft(draft, preflight_receipt=receipt, repo_root=ROOT)

        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            frozen = bound(data_root)
            store = _awaiting_store(data_root, frozen)
            fast = apply_classification(
                frozen,
                _fast_lane_packet(frozen),
                store=store,
                repo_root=ROOT,
                data_root=data_root,
            )
            self.assertEqual(fast.get("critic_terminal"), "PASS_FAST_LANE_READY")
            self.assertEqual(fast.get("session_state"), "SYNTHESIS_COMPLETE")
        with tempfile.TemporaryDirectory() as tmp:
            data_root = _panel_root(tmp)
            frozen = bound(data_root)
            store = _awaiting_store(data_root, frozen)
            observed = apply_classification(
                frozen,
                _observation_packet(frozen),
                store=store,
                repo_root=ROOT,
                data_root=data_root,
            )
            self.assertEqual(observed.get("critic_terminal"), "PASS_FAST_LANE_READY")
            self.assertEqual(observed.get("lane_classifier_terminal"), "PANEL_REUSE_READY")

    def test_t_h_denial_receipt_is_deterministic_and_rejects_forgery(self) -> None:
        frozen = _freeze(FORWARD_LABEL, RUNNER_LABEL)
        packet = _fast_lane_packet(frozen)
        first = run_live_classifier(packet, frozen, repo_root=ROOT, data_root=ROOT)
        second = run_live_classifier(packet, frozen, repo_root=ROOT, data_root=ROOT)
        self.assertEqual(first, second)
        forged = dict(first)
        forged["classifier_route_terminal"] = "TAMPERED"
        with self.assertRaises(HficSessionError) as raised:
            validate_live_classifier_receipt(
                {
                    "experiment_spec": packet["experiment_spec"],
                    "hypothesis_definition_sha256": packet["hypothesis_definition_sha256"],
                    "classifier_receipt": forged,
                },
                frozen,
                repo_root=ROOT,
                data_root=ROOT,
            )
        self.assertEqual(str(raised.exception), "CLASSIFIER_RECEIPT_INVALID")


def mock_classify(frozen: dict, spec: dict, terminal: str) -> dict:
    decision = mock.Mock(
        terminal=terminal,
        lane=mock.Mock(value="FAST_LANE"),
        reason_codes=["SYNTHETIC_AUDIT_FIXTURE"],
        next_action="PAUSE",
    )
    with mock.patch(
        "solana_alpha_lab.factory.lane_classifier.classify_lane",
        return_value=decision,
    ):
        return run_live_classifier(
            {
                "experiment_spec": spec,
                "hypothesis_definition_sha256": frozen["selected_definition_sha256"],
            },
            frozen,
            repo_root=ROOT,
            data_root=ROOT,
        )
