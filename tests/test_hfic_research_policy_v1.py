"""FORGE_RESEARCH_POLICY_RUNTIME_V1: the pure policy owner.

Three append-only artifact kinds, three CAS surfaces: the active policy for
new runs, a per-journal frozen snapshot taken on first touch, and an
append-only chain of explicit per-journal extensions that never reset spend.
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

from solana_alpha_lab.factory import hfic_research_policy as rp  # noqa: E402
from solana_alpha_lab.factory.research_store import ResearchStore  # noqa: E402


def _store(tmp: Path) -> ResearchStore:
    return ResearchStore(tmp)


class LimitsValidationTests(unittest.TestCase):
    def test_default_limits_match_shipped_constants(self) -> None:
        self.assertEqual(
            rp.DEFAULT_LIMITS,
            {
                "auto_cycles_per_market": 1,
                "distinct_focuses_per_market": 3,
                "main_total": 6,
                "adaptive_total": 2,
                "preview_total": 2,
                "simple_before_compound": 3,
                "max_generated": 6,
                "max_diagnostic_slices": 8,
            },
        )

    def test_unknown_field_is_rejected(self) -> None:
        body = dict(rp.DEFAULT_LIMITS)
        body["not_a_real_field"] = 1
        with self.assertRaises(rp.ResearchPolicyError) as raised:
            rp.validate_limits(body)
        self.assertEqual(raised.exception.code, "RESEARCH_POLICY_INVALID")

    def test_missing_field_is_rejected(self) -> None:
        body = dict(rp.DEFAULT_LIMITS)
        del body["main_total"]
        with self.assertRaises(rp.ResearchPolicyError) as raised:
            rp.validate_limits(body)
        self.assertEqual(raised.exception.code, "RESEARCH_POLICY_INVALID")

    def test_negative_value_is_rejected(self) -> None:
        body = dict(rp.DEFAULT_LIMITS)
        body["main_total"] = -1
        with self.assertRaises(rp.ResearchPolicyError) as raised:
            rp.validate_limits(body)
        self.assertEqual(raised.exception.code, "RESEARCH_POLICY_LIMIT_OUT_OF_RANGE")

    def test_bool_is_rejected_even_though_bool_is_an_int_subclass(self) -> None:
        body = dict(rp.DEFAULT_LIMITS)
        body["main_total"] = True
        with self.assertRaises(rp.ResearchPolicyError) as raised:
            rp.validate_limits(body)
        self.assertEqual(raised.exception.code, "RESEARCH_POLICY_LIMIT_OUT_OF_RANGE")

    def test_above_hard_fuse_is_rejected(self) -> None:
        body = dict(rp.DEFAULT_LIMITS)
        body["main_total"] = rp.HARD_FUSES["main_total"] + 1
        with self.assertRaises(rp.ResearchPolicyError) as raised:
            rp.validate_limits(body)
        self.assertEqual(raised.exception.code, "RESEARCH_POLICY_LIMIT_OUT_OF_RANGE")

    def test_at_hard_fuse_is_accepted(self) -> None:
        body = dict(rp.DEFAULT_LIMITS)
        body["main_total"] = rp.HARD_FUSES["main_total"]
        body["simple_before_compound"] = rp.HARD_FUSES["main_total"]
        out = rp.validate_limits(body)
        self.assertEqual(out["main_total"], rp.HARD_FUSES["main_total"])

    def test_max_diagnostic_slices_hard_fuse_equals_shipped_default(self) -> None:
        # This knob may only be lowered in this delivery, never raised.
        self.assertEqual(rp.HARD_FUSES["max_diagnostic_slices"], rp.DEFAULT_LIMITS["max_diagnostic_slices"])

    def test_allocation_cannot_exceed_main_total(self) -> None:
        body = dict(rp.DEFAULT_LIMITS)
        body["main_total"] = 2
        body["simple_before_compound"] = 3
        with self.assertRaises(rp.ResearchPolicyError) as raised:
            rp.validate_limits(body)
        self.assertEqual(raised.exception.code, "RESEARCH_POLICY_ALLOCATION_EXCEEDS_MAIN_TOTAL")


class PresetValidationTests(unittest.TestCase):
    def test_empty_presets_round_trip(self) -> None:
        self.assertEqual(rp.validate_presets(None), {})
        self.assertEqual(rp.validate_presets({}), {})

    def test_preset_name_must_be_snake_case(self) -> None:
        with self.assertRaises(rp.ResearchPolicyError) as raised:
            rp.validate_presets({"Not-Valid": {"main_total": 10}})
        self.assertEqual(raised.exception.code, "RESEARCH_POLICY_PRESET_NAME_INVALID")

    def test_preset_unknown_field_is_rejected(self) -> None:
        with self.assertRaises(rp.ResearchPolicyError) as raised:
            rp.validate_presets({"wide": {"not_a_field": 1}})
        self.assertEqual(raised.exception.code, "RESEARCH_POLICY_INVALID")

    def test_too_many_presets_is_rejected(self) -> None:
        presets = {f"p{i}": {"main_total": 7} for i in range(rp.PRESET_MAX_COUNT + 1)}
        with self.assertRaises(rp.ResearchPolicyError) as raised:
            rp.validate_presets(presets)
        self.assertEqual(raised.exception.code, "RESEARCH_POLICY_PRESETS_INVALID")

    def test_valid_presets_pass_through_cleaned(self) -> None:
        out = rp.validate_presets({"wide": {"main_total": 10, "max_generated": 10}})
        self.assertEqual(out, {"wide": {"main_total": 10, "max_generated": 10}})


class ActivePolicyOwnerTests(unittest.TestCase):
    def test_absent_state_resolves_to_shipped_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            head = rp.effective_policy(store)
            self.assertEqual(head["state"], "ABSENT")
            self.assertEqual(head["limits"], rp.DEFAULT_LIMITS)
            self.assertEqual(head["policy_head_sha256"], rp.GENESIS_HEAD_SHA256)

    def test_preview_is_read_only_and_apply_is_cas_protected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            before = store.diagnostics().committed_inventory_sha256
            preview = rp.preview_policy_change(store, limits_delta={"main_total": 10})
            self.assertEqual(preview["status"], "PROPOSED")
            self.assertEqual(store.diagnostics().committed_inventory_sha256, before)
            applied = rp.apply_policy_change(store, proposal=preview["proposal"], confirm_append_only=True)
            self.assertEqual(applied["status"], "APPENDED")
            # A stale proposal (built against the old head) is refused.
            with self.assertRaises(rp.ResearchPolicyError) as raised:
                rp.apply_policy_change(store, proposal=preview["proposal"], confirm_append_only=True)
            self.assertEqual(raised.exception.code, "RESEARCH_POLICY_PREVIEW_STALE")

    def test_apply_without_confirm_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            preview = rp.preview_policy_change(store, limits_delta={"main_total": 10})
            with self.assertRaises(rp.ResearchPolicyError) as raised:
                rp.apply_policy_change(store, proposal=preview["proposal"], confirm_append_only=False)
            self.assertEqual(raised.exception.code, "RESEARCH_POLICY_CONFIRM_REQUIRED")

    def test_tampered_proposal_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            preview = rp.preview_policy_change(store, limits_delta={"main_total": 10})
            tampered = dict(preview["proposal"])
            tampered["limits"] = dict(tampered["limits"], main_total=999)
            with self.assertRaises(rp.ResearchPolicyError) as raised:
                rp.apply_policy_change(store, proposal=tampered, confirm_append_only=True)
            self.assertEqual(raised.exception.code, "RESEARCH_POLICY_INVALID")

    def test_same_value_apply_is_no_change(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            preview = rp.preview_policy_change(store, limits_delta={"main_total": 6})
            self.assertEqual(preview["status"], "NO_CHANGE")

    def test_preset_driven_change(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            preview0 = rp.preview_policy_change(
                store, presets_delta={"wide": {"main_total": 10, "max_generated": 10}}
            )
            applied0 = rp.apply_policy_change(store, proposal=preview0["proposal"], confirm_append_only=True)
            self.assertEqual(applied0["presets"], {"wide": {"main_total": 10, "max_generated": 10}})
            preview1 = rp.preview_policy_change(store, preset_name="wide")
            self.assertEqual(preview1["after"]["limits"]["main_total"], 10)

    def test_unknown_preset_name_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            with self.assertRaises(rp.ResearchPolicyError) as raised:
                rp.preview_policy_change(store, preset_name="does_not_exist")
            self.assertEqual(raised.exception.code, "RESEARCH_POLICY_PRESET_NOT_FOUND")


class RunSnapshotTests(unittest.TestCase):
    def test_ensure_run_snapshot_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            journal = "a" * 64
            first = rp.ensure_run_snapshot(store, journal)
            second = rp.ensure_run_snapshot(store, journal)
            self.assertEqual(first["policy_artifact_sha256"], second["policy_artifact_sha256"])

    def test_active_policy_change_does_not_move_an_existing_frozen_journal(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            journal = "b" * 64
            rp.ensure_run_snapshot(store, journal)
            preview = rp.preview_policy_change(store, limits_delta={"main_total": 10})
            rp.apply_policy_change(store, proposal=preview["proposal"], confirm_append_only=True)
            self.assertEqual(rp.limits_for_frozen_run(store, journal)["main_total"], 6)

    def test_a_new_journal_freezes_at_the_then_current_active_policy(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            preview = rp.preview_policy_change(store, limits_delta={"main_total": 10})
            rp.apply_policy_change(store, proposal=preview["proposal"], confirm_append_only=True)
            journal = "c" * 64
            rp.ensure_run_snapshot(store, journal)
            self.assertEqual(rp.limits_for_frozen_run(store, journal)["main_total"], 10)

    def test_legacy_journal_never_touched_reads_shipped_defaults_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            preview = rp.preview_policy_change(store, limits_delta={"main_total": 10})
            rp.apply_policy_change(store, proposal=preview["proposal"], confirm_append_only=True)
            legacy_journal = "d" * 64
            before = store.diagnostics().committed_inventory_sha256
            limits = rp.limits_for_frozen_run(store, legacy_journal)
            after = store.diagnostics().committed_inventory_sha256
            self.assertEqual(limits, rp.DEFAULT_LIMITS)
            self.assertIsNone(rp.read_run_snapshot(store, legacy_journal))
            self.assertEqual(before, after)


class RunExtensionTests(unittest.TestCase):
    def test_extension_raises_only_the_named_journal(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            journal_a = "e" * 64
            journal_b = "f" * 64
            rp.ensure_run_snapshot(store, journal_a)
            rp.ensure_run_snapshot(store, journal_b)
            proposal = rp.propose_run_extension(
                store, journal_scope=journal_a, parent_operation_sha256="1" * 64, limits_delta={"main_total": 10}
            )
            applied = rp.apply_run_extension(store, proposal=proposal, confirm_append_only=True)
            self.assertEqual(applied["resulting_limits"]["main_total"], 10)
            self.assertEqual(rp.limits_for_frozen_run(store, journal_a)["main_total"], 10)
            self.assertEqual(rp.limits_for_frozen_run(store, journal_b)["main_total"], 6)

    def test_extension_without_a_snapshot_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            journal = "1" * 64
            with self.assertRaises(rp.ResearchPolicyError) as raised:
                rp.propose_run_extension(
                    store, journal_scope=journal, parent_operation_sha256="2" * 64, limits_delta={"main_total": 10}
                )
            self.assertEqual(raised.exception.code, "RESEARCH_POLICY_RUN_SNAPSHOT_MISSING")

    def test_stale_extension_proposal_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            journal = "3" * 64
            rp.ensure_run_snapshot(store, journal)
            proposal = rp.propose_run_extension(
                store, journal_scope=journal, parent_operation_sha256="4" * 64, limits_delta={"main_total": 8}
            )
            # A second, independently-sequenced extension lands first.
            other = rp.propose_run_extension(
                store, journal_scope=journal, parent_operation_sha256="4" * 64, limits_delta={"adaptive_total": 4}
            )
            rp.apply_run_extension(store, proposal=other, confirm_append_only=True)
            with self.assertRaises(rp.ResearchPolicyError) as raised:
                rp.apply_run_extension(store, proposal=proposal, confirm_append_only=True)
            self.assertEqual(raised.exception.code, "RESEARCH_POLICY_EXTENSION_STALE")

    def test_extensions_chain_and_never_reset_each_other(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            journal = "5" * 64
            rp.ensure_run_snapshot(store, journal)
            first = rp.propose_run_extension(
                store, journal_scope=journal, parent_operation_sha256="6" * 64, limits_delta={"main_total": 8}
            )
            rp.apply_run_extension(store, proposal=first, confirm_append_only=True)
            second = rp.propose_run_extension(
                store, journal_scope=journal, parent_operation_sha256="6" * 64, limits_delta={"adaptive_total": 5}
            )
            rp.apply_run_extension(store, proposal=second, confirm_append_only=True)
            limits = rp.limits_for_frozen_run(store, journal)
            self.assertEqual(limits["main_total"], 8)
            self.assertEqual(limits["adaptive_total"], 5)


class ConcurrencyTests(unittest.TestCase):
    """Two OS-thread-equivalent writers racing the same journal's last slot."""

    def test_two_concurrent_first_touches_converge_on_one_snapshot(self) -> None:
        import threading

        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            journal = "a1" * 32
            results: list[dict] = [None, None]  # type: ignore[list-item]
            barrier = threading.Barrier(2)

            def _touch(index: int) -> None:
                barrier.wait()
                results[index] = rp.ensure_run_snapshot(store, journal)

            threads = [threading.Thread(target=_touch, args=(i,)) for i in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(results[0]["policy_artifact_sha256"], results[1]["policy_artifact_sha256"])
            self.assertEqual(len(rp._iter_artifacts(store, rp.SNAPSHOT_KIND)), 1)

    def test_two_concurrent_extensions_only_one_wins_the_last_sequence_slot(self) -> None:
        import threading

        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            journal = "b2" * 32
            rp.ensure_run_snapshot(store, journal)
            proposal_a = rp.propose_run_extension(
                store, journal_scope=journal, parent_operation_sha256="c" * 64, limits_delta={"main_total": 8}
            )
            proposal_b = rp.propose_run_extension(
                store, journal_scope=journal, parent_operation_sha256="d" * 64, limits_delta={"adaptive_total": 5}
            )
            outcomes: list[object] = [None, None]
            barrier = threading.Barrier(2)

            def _apply(index: int, proposal: dict) -> None:
                barrier.wait()
                try:
                    outcomes[index] = rp.apply_run_extension(store, proposal=proposal, confirm_append_only=True)
                except rp.ResearchPolicyError as exc:
                    outcomes[index] = exc.code

            threads = [
                threading.Thread(target=_apply, args=(0, proposal_a)),
                threading.Thread(target=_apply, args=(1, proposal_b)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            statuses = [item.get("status") if isinstance(item, dict) else item for item in outcomes]
            self.assertEqual(sorted(statuses), sorted(["APPENDED", "RESEARCH_POLICY_EXTENSION_STALE"]))
            self.assertEqual(len(rp.read_run_extensions(store, journal)), 1)


if __name__ == "__main__":
    unittest.main()
