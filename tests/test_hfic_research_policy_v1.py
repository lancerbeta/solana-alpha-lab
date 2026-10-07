"""FORGE_RESEARCH_POLICY_RUNTIME_V1: the pure policy owner.

Three append-only artifact kinds, three CAS surfaces: the active policy for
new scopes, a frozen snapshot per accounting scope (a journal, or a market
epoch for the shared AUTO/focus pool), and an append-only chain of explicit
extensions that never reset spend.
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

J1 = "a1" * 32
J2 = "b2" * 32
E1 = "e1" * 32
E2 = "e2" * 32


def _store(tmp: Path) -> ResearchStore:
    return ResearchStore(tmp)


def _preset(preset_id: str = "organic_and_trending") -> dict:
    return {
        "preset_id": preset_id,
        "population": "OPPORTUNITY_EPISODES",
        "representation_id": "BASE",
        "hypothesis_kind": "LIST_CONTRAST",
        "research_scope": {"universe_selector": {"clauses": [{}]}},
        "list_condition": {"clauses": [{"all_of": ["JUPITER:toporganicscore:5m", "JUPITER:toptrending:5m"]}]},
        "diagnostic_slices": [],
    }


def _apply(store: ResearchStore, **kwargs) -> dict:
    preview = rp.preview_policy_change(store, **kwargs)
    return rp.apply_policy_change(store, proposal=preview["proposal"], confirm_append_only=True)


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

    def test_defaults_equal_the_legacy_constants_still_used_by_bare_callers(self) -> None:
        from solana_alpha_lab.factory.hfic_grounded_discovery import MAX_ADAPTIVE_REFINEMENTS, MAX_MAIN_QUERY_SPECS
        from solana_alpha_lab.factory.hfic_preflight import AUTO_SESSIONS_PER_EPOCH, MAX_DISTINCT_FOCUSES_PER_EPOCH
        from solana_alpha_lab.factory.hfic_session import MAX_CANDIDATES
        from solana_alpha_lab.factory.hfic_temporal_discovery import (
            MAX_DIAGNOSTIC_SLICES,
            MAX_PREVIEW_SPECS,
            SIMPLE_MAIN_RESERVE,
        )

        legacy = {
            "auto_cycles_per_market": AUTO_SESSIONS_PER_EPOCH,
            "distinct_focuses_per_market": MAX_DISTINCT_FOCUSES_PER_EPOCH,
            "main_total": MAX_MAIN_QUERY_SPECS,
            "adaptive_total": MAX_ADAPTIVE_REFINEMENTS,
            "preview_total": MAX_PREVIEW_SPECS,
            "simple_before_compound": SIMPLE_MAIN_RESERVE,
            "max_generated": MAX_CANDIDATES,
            "max_diagnostic_slices": MAX_DIAGNOSTIC_SLICES,
        }
        self.assertEqual(rp.DEFAULT_LIMITS, legacy)

    def test_unknown_and_missing_fields_are_rejected(self) -> None:
        body = dict(rp.DEFAULT_LIMITS)
        body["not_a_real_field"] = 1
        with self.assertRaises(rp.ResearchPolicyError) as raised:
            rp.validate_limits(body)
        self.assertEqual(raised.exception.code, "RESEARCH_POLICY_INVALID")
        body = dict(rp.DEFAULT_LIMITS)
        del body["main_total"]
        with self.assertRaises(rp.ResearchPolicyError):
            rp.validate_limits(body)

    def test_negative_bool_and_non_integer_values_name_the_field_and_the_fuse(self) -> None:
        for bad in (-1, True, 1.5, "6"):
            body = dict(rp.DEFAULT_LIMITS)
            body["main_total"] = bad
            with self.assertRaises(rp.ResearchPolicyError) as raised:
                rp.validate_limits(body)
            self.assertEqual(raised.exception.code, "RESEARCH_POLICY_LIMIT_OUT_OF_RANGE")
            self.assertEqual(raised.exception.detail["field"], "main_total")
            self.assertEqual(raised.exception.detail["hard_fuse"], 32)

    def test_ranges_match_the_contract(self) -> None:
        self.assertEqual(rp.FIELD_RANGES["max_generated"], (1, 16))
        self.assertEqual(rp.FIELD_RANGES["auto_cycles_per_market"], (0, 8))
        self.assertEqual(rp.FIELD_RANGES["distinct_focuses_per_market"], (0, 32))
        self.assertEqual(rp.FIELD_RANGES["max_diagnostic_slices"], (0, 8))
        body = dict(rp.DEFAULT_LIMITS)
        body["max_generated"] = 0
        with self.assertRaises(rp.ResearchPolicyError):
            rp.validate_limits(body)
        body["max_generated"] = 17
        with self.assertRaises(rp.ResearchPolicyError):
            rp.validate_limits(body)

    def test_zero_forbids_and_is_accepted_for_counters(self) -> None:
        body = dict(rp.DEFAULT_LIMITS)
        body.update(main_total=0, simple_before_compound=0, adaptive_total=0, preview_total=0, auto_cycles_per_market=0)
        self.assertEqual(rp.validate_limits(body)["main_total"], 0)

    def test_allocation_cannot_exceed_main_total(self) -> None:
        body = dict(rp.DEFAULT_LIMITS)
        body["main_total"] = 2
        with self.assertRaises(rp.ResearchPolicyError) as raised:
            rp.validate_limits(body)
        self.assertEqual(raised.exception.code, "RESEARCH_POLICY_ALLOCATION_EXCEEDS_MAIN_TOTAL")

    def test_pool_fields_and_journal_fields_partition_the_limits(self) -> None:
        self.assertEqual(set(rp.EPOCH_FIELDS) | set(rp.JOURNAL_FIELDS), set(rp.LIMIT_FIELDS))
        self.assertFalse(set(rp.EPOCH_FIELDS) & set(rp.JOURNAL_FIELDS))

    def test_scope_keys(self) -> None:
        self.assertEqual(rp.scope_kind(J1), rp.SCOPE_JOURNAL)
        self.assertEqual(rp.scope_kind(rp.epoch_scope_key(E1)), rp.SCOPE_EPOCH)
        for bad in ("", "x" * 64, "EPOCH:abc", None):
            with self.assertRaises(rp.ResearchPolicyError):
                rp.scope_kind(bad)  # type: ignore[arg-type]


class PresetTests(unittest.TestCase):
    def test_empty_presets_round_trip(self) -> None:
        self.assertEqual(rp.validate_presets(None), {})
        self.assertEqual(rp.validate_presets({}), {})

    def test_a_valid_selector_preset_is_kept_expanded(self) -> None:
        out = rp.validate_presets({"organic_and_trending": _preset()})
        self.assertEqual(out["organic_and_trending"]["hypothesis_kind"], "LIST_CONTRAST")

    def test_unknown_missing_and_mismatched_fields_are_refused(self) -> None:
        bad = _preset()
        bad["not_a_field"] = 1
        with self.assertRaises(rp.ResearchPolicyError) as raised:
            rp.validate_preset("organic_and_trending", bad)
        self.assertEqual(raised.exception.code, "RESEARCH_POLICY_PRESET_INVALID")
        bad = _preset()
        del bad["research_scope"]
        with self.assertRaises(rp.ResearchPolicyError):
            rp.validate_preset("organic_and_trending", bad)
        with self.assertRaises(rp.ResearchPolicyError):
            rp.validate_preset("other_id", _preset())
        bad = _preset()
        bad["hypothesis_kind"] = "MAGIC"
        with self.assertRaises(rp.ResearchPolicyError):
            rp.validate_preset("organic_and_trending", bad)

    def test_nesting_is_forbidden(self) -> None:
        bad = _preset()
        bad["research_scope"] = {"universe_selector": {"preset_ref": "other"}}
        with self.assertRaises(rp.ResearchPolicyError) as raised:
            rp.validate_preset("organic_and_trending", bad)
        self.assertEqual(raised.exception.code, "RESEARCH_POLICY_PRESET_NESTING_FORBIDDEN")

    def test_name_count_and_size_bounds(self) -> None:
        with self.assertRaises(rp.ResearchPolicyError) as raised:
            rp.validate_presets({"Not-Valid": _preset("Not-Valid")})
        self.assertEqual(raised.exception.code, "RESEARCH_POLICY_PRESET_NAME_INVALID")
        many = {f"p{i}": _preset(f"p{i}") for i in range(rp.PRESET_MAX_COUNT + 1)}
        with self.assertRaises(rp.ResearchPolicyError) as raised:
            rp.validate_presets(many)
        self.assertEqual(raised.exception.code, "RESEARCH_POLICY_PRESETS_INVALID")
        huge = _preset()
        huge["list_condition"] = {"clauses": [{"all_of": ["L" * 200 for _ in range(40)]}]}
        with self.assertRaises(rp.ResearchPolicyError) as raised:
            rp.validate_preset("organic_and_trending", huge)
        self.assertEqual(raised.exception.code, "RESEARCH_POLICY_PRESET_TOO_LARGE")

    def test_expand_applies_to_explicit_fields_and_a_conflict_is_refused_not_merged(self) -> None:
        presets = rp.validate_presets({"organic_and_trending": _preset()})
        expanded = rp.expand_preset(presets, "organic_and_trending", {"target": "Y3600"})
        self.assertEqual(expanded["target"], "Y3600")
        self.assertEqual(expanded["hypothesis_kind"], "LIST_CONTRAST")
        self.assertNotIn("preset_id", expanded)
        same = rp.expand_preset(presets, "organic_and_trending", {"hypothesis_kind": "LIST_CONTRAST"})
        self.assertEqual(same["hypothesis_kind"], "LIST_CONTRAST")
        with self.assertRaises(rp.ResearchPolicyError) as raised:
            rp.expand_preset(presets, "organic_and_trending", {"hypothesis_kind": "NUMERIC_IN_SCOPE"})
        self.assertEqual(raised.exception.code, "RESEARCH_POLICY_PRESET_CONFLICT")
        with self.assertRaises(rp.ResearchPolicyError) as raised:
            rp.expand_preset(presets, "nope")
        self.assertEqual(raised.exception.code, "RESEARCH_POLICY_PRESET_NOT_FOUND")


class ActivePolicyOwnerTests(unittest.TestCase):
    def test_absent_state_resolves_to_shipped_defaults_with_an_explicit_source(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            head = rp.effective_policy(_store(Path(raw)))
            self.assertEqual((head["state"], head["source"]), ("ABSENT", rp.SOURCE_DEFAULTS))
            self.assertEqual(head["limits"], rp.DEFAULT_LIMITS)
            self.assertEqual(head["policy_head_sha256"], rp.GENESIS_HEAD_SHA256)

    def test_preview_reads_no_values_writes_nothing_and_states_its_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            before = store.diagnostics().committed_inventory_sha256
            preview = rp.preview_policy_change(store, limits_delta={"main_total": 10, "max_generated": 10})
            self.assertEqual(preview["status"], "PROPOSED")
            self.assertEqual(preview["changed_limits"]["main_total"], {"from": 6, "to": 10})
            self.assertEqual(preview["applies_to"], "NEW_SCOPES_ONLY")
            self.assertEqual(preview["market_values_read"], 0)
            self.assertEqual(preview["writes"], {"research_store": 0})
            self.assertEqual(store.diagnostics().committed_inventory_sha256, before)

    def test_cas_is_the_policy_head_not_the_whole_store(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            preview = rp.preview_policy_change(store, limits_delta={"main_total": 10})
            # Unrelated research data lands after the preview: the owner is not asked to re-confirm.
            rp.ensure_scope_snapshot(store, J1)
            applied = rp.apply_policy_change(store, proposal=preview["proposal"], confirm_append_only=True)
            self.assertEqual(applied["status"], "APPENDED")

    def test_repeating_the_same_applied_proposal_is_the_exact_existing_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            preview = rp.preview_policy_change(store, limits_delta={"main_total": 10})
            first = rp.apply_policy_change(store, proposal=preview["proposal"], confirm_append_only=True)
            before = store.diagnostics().committed_inventory_sha256
            again = rp.apply_policy_change(store, proposal=preview["proposal"], confirm_append_only=True)
            self.assertEqual(again["status"], rp.ALREADY_APPLIED)
            self.assertEqual(again["policy_head_sha256"], first["policy_head_sha256"])
            self.assertEqual(store.diagnostics().committed_inventory_sha256, before)

    def test_a_proposal_built_against_an_older_head_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            stale = rp.preview_policy_change(store, limits_delta={"main_total": 10})
            _apply(store, limits_delta={"adaptive_total": 4})
            with self.assertRaises(rp.ResearchPolicyError) as raised:
                rp.apply_policy_change(store, proposal=stale["proposal"], confirm_append_only=True)
            self.assertEqual(raised.exception.code, "RESEARCH_POLICY_PREVIEW_STALE")

    def test_apply_needs_confirm_and_refuses_a_tampered_proposal_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            preview = rp.preview_policy_change(store, limits_delta={"main_total": 10})
            with self.assertRaises(rp.ResearchPolicyError) as raised:
                rp.apply_policy_change(store, proposal=preview["proposal"], confirm_append_only=False)
            self.assertEqual(raised.exception.code, "RESEARCH_POLICY_CONFIRM_REQUIRED")
            tampered = dict(preview["proposal"])
            tampered["limits"] = dict(tampered["limits"], main_total=32)
            before = store.diagnostics().committed_inventory_sha256
            with self.assertRaises(rp.ResearchPolicyError) as raised:
                rp.apply_policy_change(store, proposal=tampered, confirm_append_only=True)
            self.assertEqual(raised.exception.code, "RESEARCH_POLICY_INVALID")
            self.assertEqual(store.diagnostics().committed_inventory_sha256, before)

    def test_same_content_is_no_change_and_rollback_is_a_new_revision(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            self.assertEqual(rp.preview_policy_change(store, limits_delta={"main_total": 6})["status"], "NO_CHANGE")
            _apply(store, limits_delta={"main_total": 10})
            back = _apply(store, limits_delta={"main_total": 6})
            self.assertEqual(back["status"], "APPENDED")
            self.assertEqual(back["policy_sequence"], 2)
            self.assertEqual(rp.effective_policy(store)["limits"], rp.DEFAULT_LIMITS)

    def test_an_empty_change_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaises(rp.ResearchPolicyError) as raised:
                rp.preview_policy_change(_store(Path(raw)))
            self.assertEqual(raised.exception.code, "RESEARCH_POLICY_CHANGE_EMPTY")

    def test_presets_are_added_changed_and_removed_through_the_same_chain(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            added = _apply(store, presets_delta={"organic_and_trending": _preset()})
            self.assertEqual(added["preset_ids"], ["organic_and_trending"])
            self.assertEqual(rp.effective_policy(store)["limits"], rp.DEFAULT_LIMITS)
            removed = _apply(store, presets_remove=["organic_and_trending"])
            self.assertEqual(removed["preset_ids"], [])
            with self.assertRaises(rp.ResearchPolicyError) as raised:
                rp.preview_policy_change(store, presets_remove=["organic_and_trending"])
            self.assertEqual(raised.exception.code, "RESEARCH_POLICY_PRESET_NOT_FOUND")

    def test_a_forked_or_unchained_record_is_corruption_not_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            _apply(store, limits_delta={"main_total": 10})
            artifact = rp._iter_artifacts(store, rp.ARTIFACT_KIND)[0]
            tampered = dict(artifact)
            tampered["limits"] = dict(artifact["limits"], main_total=11)
            with self.assertRaises(rp.ResearchPolicyError) as raised:
                rp._verified(tampered)
            self.assertEqual(raised.exception.code, "RESEARCH_POLICY_CHAIN_CORRUPT")


class ScopeSnapshotTests(unittest.TestCase):
    def test_ensure_is_idempotent_and_returns_one_shape(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            first = rp.ensure_scope_snapshot(store, J1)
            second = rp.ensure_scope_snapshot(store, J1)
            self.assertEqual(first, second)
            self.assertEqual(first["freeze_basis"], rp.BASIS_ACTIVE_POLICY)

    def test_an_active_policy_change_never_moves_a_frozen_scope(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            rp.ensure_scope_snapshot(store, J1)
            rp.ensure_scope_snapshot(store, rp.epoch_scope_key(E1))
            _apply(store, limits_delta={"main_total": 10, "auto_cycles_per_market": 2})
            self.assertEqual(rp.limits_for_frozen_run(store, J1)["main_total"], 6)
            self.assertEqual(rp.epoch_limits(store, E1)["auto_cycles_per_market"], 1)

    def test_a_new_scope_freezes_at_the_then_active_policy(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            _apply(store, limits_delta={"main_total": 10, "auto_cycles_per_market": 2})
            rp.ensure_scope_snapshot(store, J2)
            rp.ensure_scope_snapshot(store, rp.epoch_scope_key(E2))
            self.assertEqual(rp.limits_for_frozen_run(store, J2)["main_total"], 10)
            self.assertEqual(rp.epoch_limits(store, E2)["auto_cycles_per_market"], 2)

    def test_a_scope_with_history_freezes_at_the_shipped_defaults_not_todays_raise(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            _apply(store, limits_delta={"main_total": 10})
            legacy = rp.ensure_scope_snapshot(store, J1, has_history=True)
            self.assertEqual(legacy["limits"]["main_total"], 6)
            self.assertEqual((legacy["source"], legacy["freeze_basis"]), (rp.SOURCE_LEGACY, rp.BASIS_LEGACY_DEFAULTS))

    def test_a_scope_never_touched_reads_defaults_writes_nothing_and_reports_the_first_touch_value(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            _apply(store, limits_delta={"main_total": 10})
            before = store.diagnostics().committed_inventory_sha256
            self.assertEqual(rp.limits_for_frozen_run(store, J1), rp.DEFAULT_LIMITS)
            self.assertIsNone(rp.read_scope_snapshot(store, J1))
            fresh = rp.resolve_scope_limits(store, J1)
            self.assertEqual((fresh["frozen"], fresh["would_freeze_basis"]), (False, rp.BASIS_ACTIVE_POLICY))
            self.assertEqual(fresh["limits"]["main_total"], 10)
            with_history = rp.resolve_scope_limits(store, J1, has_history=True)
            self.assertEqual(with_history["limits"]["main_total"], 6)
            self.assertEqual(store.diagnostics().committed_inventory_sha256, before)

    def test_limits_or_defaults_only_defaults_a_non_key_or_missing_store(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            self.assertEqual(rp.limits_or_defaults(None, J1), rp.DEFAULT_LIMITS)
            self.assertEqual(rp.limits_or_defaults(store, "journal-1"), rp.DEFAULT_LIMITS)
            self.assertEqual(rp.limits_or_defaults(store, J1), rp.DEFAULT_LIMITS)

    def test_readout_separates_new_scope_policy_from_the_frozen_scope_and_flags_the_difference(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            rp.ensure_scope_snapshot(store, J1)
            _apply(store, limits_delta={"main_total": 10})
            readout = rp.policy_readout(store, scope_keys=[J1])
            self.assertEqual(readout["active_policy_for_new_runs"]["limits"]["main_total"], 10)
            frozen = readout["frozen_policy"][J1]
            self.assertEqual(frozen["limits"]["main_total"], 6)
            self.assertTrue(frozen["differs"])


class ScopeExtensionTests(unittest.TestCase):
    def test_extension_raises_only_the_named_scope_and_states_what_it_does_not_change(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            rp.ensure_scope_snapshot(store, J1)
            rp.ensure_scope_snapshot(store, J2)
            proposal = rp.propose_run_extension(
                store, scope_key=J1, parent_operation_sha256="1" * 64, limits_delta={"main_total": 10}
            )
            self.assertEqual(proposal["before_limits"]["main_total"], 6)
            applied = rp.apply_run_extension(store, proposal=proposal, confirm_append_only=True)
            self.assertEqual(applied["resulting_limits"]["main_total"], 10)
            self.assertIn("unchanged", applied)
            self.assertEqual(rp.limits_for_frozen_run(store, J1)["main_total"], 10)
            self.assertEqual(rp.limits_for_frozen_run(store, J2)["main_total"], 6)

    def test_total_is_the_ceiling_of_the_chain_not_an_extra_allowance(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            rp.ensure_scope_snapshot(store, J1)
            for total in (10, 10):
                proposal = rp.propose_run_extension(
                    store, scope_key=J1, parent_operation_sha256="1" * 64, limits_delta={"main_total": total}
                )
                rp.apply_run_extension(store, proposal=proposal, confirm_append_only=True)
            self.assertEqual(rp.limits_for_frozen_run(store, J1)["main_total"], 10)

    def test_a_lower_total_is_allowed_and_leaves_a_visible_ceiling_below_occupancy(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            rp.ensure_scope_snapshot(store, J1)
            proposal = rp.propose_run_extension(
                store, scope_key=J1, parent_operation_sha256="1" * 64, limits_delta={"main_total": 3, "simple_before_compound": 3}
            )
            rp.apply_run_extension(store, proposal=proposal, confirm_append_only=True)
            self.assertEqual(rp.limits_for_frozen_run(store, J1)["main_total"], 3)

    def test_scope_kind_restricts_the_fields(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            rp.ensure_scope_snapshot(store, J1)
            with self.assertRaises(rp.ResearchPolicyError) as raised:
                rp.propose_run_extension(
                    store, scope_key=J1, parent_operation_sha256="1" * 64, limits_delta={"auto_cycles_per_market": 2}
                )
            self.assertEqual(raised.exception.code, "RESEARCH_POLICY_FIELD_NOT_IN_SCOPE")

    def test_extension_without_a_snapshot_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaises(rp.ResearchPolicyError) as raised:
                rp.propose_run_extension(
                    _store(Path(raw)), scope_key=J1, parent_operation_sha256="2" * 64, limits_delta={"main_total": 10}
                )
            self.assertEqual(raised.exception.code, "RESEARCH_POLICY_RUN_SNAPSHOT_MISSING")

    def test_a_stale_extension_is_refused_and_a_repeat_of_an_applied_one_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            rp.ensure_scope_snapshot(store, J1)
            slow = rp.propose_run_extension(
                store, scope_key=J1, parent_operation_sha256="4" * 64, limits_delta={"main_total": 8}
            )
            fast = rp.propose_run_extension(
                store, scope_key=J1, parent_operation_sha256="4" * 64, limits_delta={"adaptive_total": 4}
            )
            rp.apply_run_extension(store, proposal=fast, confirm_append_only=True)
            with self.assertRaises(rp.ResearchPolicyError) as raised:
                rp.apply_run_extension(store, proposal=slow, confirm_append_only=True)
            self.assertEqual(raised.exception.code, "RESEARCH_POLICY_EXTENSION_STALE")
            before = store.diagnostics().committed_inventory_sha256
            again = rp.apply_run_extension(store, proposal=fast, confirm_append_only=True)
            self.assertEqual(again["status"], rp.ALREADY_APPLIED)
            self.assertEqual(store.diagnostics().committed_inventory_sha256, before)

    def test_extensions_chain_and_never_reset_each_other(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            rp.ensure_scope_snapshot(store, J1)
            for delta in ({"main_total": 8}, {"adaptive_total": 5}):
                proposal = rp.propose_run_extension(
                    store, scope_key=J1, parent_operation_sha256="6" * 64, limits_delta=delta
                )
                rp.apply_run_extension(store, proposal=proposal, confirm_append_only=True)
            limits = rp.limits_for_frozen_run(store, J1)
            self.assertEqual((limits["main_total"], limits["adaptive_total"]), (8, 5))

    def test_malformed_sequence_is_a_typed_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            rp.ensure_scope_snapshot(store, J1)
            proposal = rp.propose_run_extension(
                store, scope_key=J1, parent_operation_sha256="6" * 64, limits_delta={"main_total": 8}
            )
            broken = dict(proposal)
            broken.pop("proposal_sha256")
            broken["base_extension_sequence"] = "zero"
            from solana_alpha_lab.factory.run_passport import canonical_sha256

            broken["proposal_sha256"] = canonical_sha256(broken)
            with self.assertRaises(rp.ResearchPolicyError) as raised:
                rp.apply_run_extension(store, proposal=broken, confirm_append_only=True)
            self.assertEqual(raised.exception.code, "RESEARCH_POLICY_EXTENSION_STALE")


class ConcurrencyTests(unittest.TestCase):
    """Two writers racing the same scope's last slot."""

    def test_two_concurrent_first_touches_converge_on_one_snapshot(self) -> None:
        import threading

        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            results: list = [None, None]
            barrier = threading.Barrier(2)

            def _touch(index: int) -> None:
                barrier.wait()
                results[index] = rp.ensure_scope_snapshot(store, J1)

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
            rp.ensure_scope_snapshot(store, J1)
            proposals = [
                rp.propose_run_extension(store, scope_key=J1, parent_operation_sha256="c" * 64, limits_delta={"main_total": 8}),
                rp.propose_run_extension(store, scope_key=J1, parent_operation_sha256="d" * 64, limits_delta={"adaptive_total": 5}),
            ]
            outcomes: list = [None, None]
            barrier = threading.Barrier(2)

            def _apply_one(index: int) -> None:
                barrier.wait()
                try:
                    outcomes[index] = rp.apply_run_extension(store, proposal=proposals[index], confirm_append_only=True)
                except rp.ResearchPolicyError as exc:
                    outcomes[index] = exc.code

            threads = [threading.Thread(target=_apply_one, args=(i,)) for i in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            statuses = [item.get("status") if isinstance(item, dict) else item for item in outcomes]
            self.assertEqual(sorted(statuses), sorted(["APPENDED", "RESEARCH_POLICY_EXTENSION_STALE"]))
            self.assertEqual(len(rp.read_scope_extensions(store, J1)), 1)

    def test_two_concurrent_policy_applies_only_one_wins_the_head(self) -> None:
        import threading

        with tempfile.TemporaryDirectory() as raw:
            store = _store(Path(raw))
            proposals = [
                rp.preview_policy_change(store, limits_delta={"main_total": 8})["proposal"],
                rp.preview_policy_change(store, limits_delta={"adaptive_total": 5})["proposal"],
            ]
            outcomes: list = [None, None]
            barrier = threading.Barrier(2)

            def _apply_one(index: int) -> None:
                barrier.wait()
                try:
                    outcomes[index] = rp.apply_policy_change(store, proposal=proposals[index], confirm_append_only=True)
                except rp.ResearchPolicyError as exc:
                    outcomes[index] = exc.code

            threads = [threading.Thread(target=_apply_one, args=(i,)) for i in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            statuses = [item.get("status") if isinstance(item, dict) else item for item in outcomes]
            self.assertEqual(sorted(statuses), sorted(["APPENDED", "RESEARCH_POLICY_PREVIEW_STALE"]))
            self.assertEqual(len(rp.load_policy_records(store)), 1)


class MovedRootColdReadTests(unittest.TestCase):
    """A moved root and a brand-new handle still see durable state, without any network."""

    def test_active_policy_snapshot_and_extension_survive_a_moved_root(self) -> None:
        import shutil

        with tempfile.TemporaryDirectory() as raw:
            original = Path(raw) / "original"
            store = _store(original)
            rp.ensure_scope_snapshot(store, J1)
            _apply(store, limits_delta={"main_total": 9})
            proposal = rp.propose_run_extension(
                store, scope_key=J1, parent_operation_sha256="8" * 64, limits_delta={"main_total": 9}
            )
            rp.apply_run_extension(store, proposal=proposal, confirm_append_only=True)
            moved = Path(raw) / "moved"
            shutil.move(str(original), str(moved))
            del store
            fresh = _store(moved)
            self.assertEqual(rp.effective_policy(fresh)["limits"]["main_total"], 9)
            self.assertEqual(rp.limits_for_frozen_run(fresh, J1)["main_total"], 9)
            self.assertEqual(len(rp.read_scope_extensions(fresh, J1)), 1)


if __name__ == "__main__":
    unittest.main()
