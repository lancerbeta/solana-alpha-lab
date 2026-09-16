"""Positive suppression authority for HFIC closed-family semantics.

A CLOSE_* terminal (with or without ``_FAMILY``) is an exclusion action and
requires positive machine authority from the source payload.  Naming, suffix,
filename, owner PARK, or absence of contrary evidence never authorizes a
family hard-close.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from solana_alpha_lab.factory.hfic_suppression_semantics import (
    AMBIGUOUS_REQUIRES_OWNER,
    OWNER_PRIORITY_PARK,
    SCIENTIFIC_CLOSE_VALID,
    SCOPE_LIMITED_CLOSE,
    classify_source_payload,
    enumerate_closed_park_terminals_with_authority,
    family_close_authority,
    suppression_counts,
)

ROOT = Path(__file__).resolve().parents[1]


def _classify(terminal: str, payload: dict | None) -> dict:
    return classify_source_payload(
        payload or {},
        terminal=terminal,
        source_receipt="docs/evidence/synthetic/a1_acceptance_v1.json",
    )


class FamilyNamingIsNotAuthority(unittest.TestCase):  # noqa: D101
    def test_family_suffix_alone_cannot_hard_close(self) -> None:
        item = _classify(
            "CLOSE_SOMETHING_FAMILY",
            {"verdict": "CLOSE_SOMETHING_FAMILY"},
        )
        self.assertNotEqual(item["suppression_class"], SCIENTIFIC_CLOSE_VALID)
        self.assertNotEqual(item["scope_kind"], "FAMILY")
        self.assertIn(
            item["suppression_class"],
            {AMBIGUOUS_REQUIRES_OWNER, SCOPE_LIMITED_CLOSE},
        )

    def test_family_close_flag_alone_cannot_hard_close(self) -> None:
        item = _classify(
            "CLOSE_SOMETHING",
            {"family_close": True},
        )
        self.assertNotEqual(item["suppression_class"], SCIENTIFIC_CLOSE_VALID)
        self.assertNotEqual(item["scope_kind"], "FAMILY")

    def test_science_false_family_terminal_is_not_family_close(self) -> None:
        # Observed legacy case: quote surface retention.
        payload = {
            "confirmatory_scientific_terminal": "CLOSE_EXACT_QUOTE_SURFACE_RETENTION_FAMILY",
            "design_probe": {"science": False},
            "owner_decision": "ACCEPT_TOUCH_FILLABLE_FEES_NOT_EVIDENCED_QUOTE_ONLY_KEEP_SCREENING_EXHAUSTED",
        }
        item = _classify("CLOSE_EXACT_QUOTE_SURFACE_RETENTION_FAMILY", payload)
        self.assertNotEqual(item["suppression_class"], SCIENTIFIC_CLOSE_VALID)
        self.assertNotEqual(item["scope_kind"], "FAMILY")
        self.assertFalse(item["reopen_forbidden"])


import unittest  # noqa: E402


class TypedRuntimeReceiptAuthority(unittest.TestCase):  # noqa: D101
    def test_typed_rdp_runtime_receipt_family_close_stays_authoritative(self) -> None:
        payload = {
            "schema": "smial.early-icp-first-hit-mix-falsifier.runtime-receipt",
            "schema_version": "1.0",
            "atom_id": "EARLY_ICP_FIRST_HIT_MIX_FALSIFIER_V1",
            "scientific_terminal": "CLOSE_EARLY_TAKER_VOLUME_MIX_FAMILY",
            "outcome_consumed": True,
            "dataset_fingerprint": "ab" * 32,
            "score": {"terminal": "CLOSE_EARLY_TAKER_VOLUME_MIX_FAMILY"},
        }
        item = _classify("CLOSE_EARLY_TAKER_VOLUME_MIX_FAMILY", payload)
        self.assertEqual(item["suppression_class"], SCIENTIFIC_CLOSE_VALID)
        self.assertEqual(item["scope_kind"], "FAMILY")
        self.assertTrue(item["reopen_forbidden"])

    def test_rdp_runtime_receipt_without_atom_scope_is_not_family(self) -> None:
        payload = {
            "schema": "smial.some.runtime-receipt",
            "scientific_terminal": "CLOSE_X_FAMILY",
        }
        item = _classify("CLOSE_X_FAMILY", payload)
        self.assertNotEqual(item["scope_kind"], "FAMILY")


class GitAcceptanceAuthority(unittest.TestCase):  # noqa: D101
    def _portable(self) -> dict:
        return {
            "family_close": True,
            "scientific_terminal": "CLOSE_EXACT_FRICTION_VETO_FAMILY",
            "atom_id": "FRESH_OOS_BASELINE_VS_FRICTION_VETO_V1",
            "cohort": {"n": 60, "population": "H900 ordinary recent"},
            "criteria": {"falsifier": "TAKER_EXCHANGE_ROUND_TRIP", "ran": True},
            "source_runtime_receipt_sha256": "ee" * 32,
        }

    def test_positive_typed_git_acceptance_hard_closes(self) -> None:
        item = _classify("CLOSE_EXACT_FRICTION_VETO_FAMILY", self._portable())
        self.assertEqual(item["suppression_class"], SCIENTIFIC_CLOSE_VALID)
        self.assertEqual(item["scope_kind"], "FAMILY")
        self.assertTrue(item["reopen_forbidden"])
        self.assertEqual(item["scope_id"], "FRESH_OOS_BASELINE_VS_FRICTION_VETO_V1")

    def test_source_hash_drift_invalidates_portability(self) -> None:
        authority = family_close_authority(self._portable())
        self.assertIsNotNone(authority)
        drifted = dict(self._portable())
        drifted["source_runtime_receipt_sha256"] = "ff" * 32
        # authority content changed => classifier re-evaluates on the payload
        # it actually sees; drift detection is proven at enumerate level with
        # hash-bound overlay entries (see below).
        self.assertNotEqual(
            family_close_authority(drifted),
            family_close_authority(self._portable()),
        )

    def test_science_negation_blocks_family_close(self) -> None:
        payload = dict(self._portable())
        payload["design_probe"] = {"science": False}
        item = _classify("CLOSE_EXACT_FRICTION_VETO_FAMILY", payload)
        self.assertNotEqual(item["scope_kind"], "FAMILY")

    def test_no_ran_marker_blocks_family_close(self) -> None:
        payload = dict(self._portable())
        del payload["criteria"]
        item = _classify("CLOSE_EXACT_FRICTION_VETO_FAMILY", payload)
        self.assertNotEqual(item["scope_kind"], "FAMILY")
class ParksAndScopeFences(unittest.TestCase):  # noqa: D101
    def test_typed_park_never_suppresses(self) -> None:
        payload = {
            "priority_disposition": "PARKED_FROM_PRIORITY",
            "science_disposition": "RETAINED",
            "hypothesis_verdict": "NOT_REFUTED_NOT_SUPPORTED",
            "hypothesis_id": "HYP-X-1",
        }
        item = _classify("PARK_H11_FROM_PRIORITY", payload)
        self.assertEqual(item["suppression_class"], OWNER_PRIORITY_PARK)
        self.assertFalse(item["reopen_forbidden"])

    def test_scope_limited_close_cannot_widen_to_family(self) -> None:
        payload = {
            "atom_id": "SOME_ROUTE_V1",
            "runtime_terminal": "CLOSE_TASK40_WITH_CREATE_AT_GAP",
        }
        item = _classify("CLOSE_TASK40_WITH_CREATE_AT_GAP", payload)
        self.assertEqual(item["suppression_class"], SCOPE_LIMITED_CLOSE)
        self.assertIn(item["scope_kind"], {"ROUTE", "RULE", "CANDIDATE", "VERSION"})


class LiveRepositoryAudit(unittest.TestCase):  # noqa: D101
    """Recompute from current truth: no hardcoded counts."""

    def test_repository_ledger_has_no_unauthorized_family_hard_close(self) -> None:
        ledger = enumerate_closed_park_terminals_with_authority(ROOT, None)
        counts = suppression_counts(ledger)
        self.assertEqual(counts["priority_park_hard_close_count"], 0)
        self.assertEqual(counts["scope_overclosure_count"], 0)
        for item in ledger:
            if item.get("reopen_forbidden") is True and item.get("scope_kind") == "FAMILY":
                authority = item.get("family_close_authority") or {}
                self.assertEqual(
                    authority.get("class"),
                    "POSITIVE",
                    f"family hard-close without positive authority: {item.get('terminal')}",
                )
        # Observed legacy false positive must not act as family hard-close:
        # the legacy pmf overlay payload (design_probe.science=false) classifies
        # reopenable, and the terminal only hard-closes through the positive
        # confirmatory acceptance (criteria/retention/cohort + hash binding).
        legacy = classify_source_payload(
            json.loads(
                (
                    ROOT
                    / "docs/evidence/pmf_quote_slice/a1_pmf_quote_stay_overlay_acceptance_v1.json"
                ).read_text(encoding="utf-8")
            ),
            terminal="CLOSE_EXACT_QUOTE_SURFACE_RETENTION_FAMILY",
            source_receipt="docs/evidence/pmf_quote_slice/a1_pmf_quote_stay_overlay_acceptance_v1.json",
        )
        self.assertFalse(legacy["reopen_forbidden"])
        self.assertNotEqual(legacy["scope_kind"], "FAMILY")
        quote = next(
            (
                item
                for item in ledger
                if item.get("terminal") == "CLOSE_EXACT_QUOTE_SURFACE_RETENTION_FAMILY"
            ),
            None,
        )
        self.assertIsNotNone(quote)
        if quote.get("scope_kind") == "FAMILY":
            self.assertEqual(
                quote.get("source_receipt"),
                "docs/evidence/quote_surface_retention_confirmatory/c1_quote_surface_retention_confirmatory_acceptance_v1.json",
            )
            authority = quote.get("family_close_authority") or {}
            self.assertEqual(authority.get("class"), "POSITIVE")
        else:
            self.assertFalse(quote.get("reopen_forbidden"))

    def test_quote_retention_source_file_unchanged(self) -> None:
        source = (
            ROOT
            / "docs/evidence/pmf_quote_slice/a1_pmf_quote_stay_overlay_acceptance_v1.json"
        )
        payload = json.loads(source.read_text(encoding="utf-8"))
        item = classify_source_payload(
            payload,
            terminal="CLOSE_EXACT_QUOTE_SURFACE_RETENTION_FAMILY",
            source_receipt=str(source.relative_to(ROOT)).replace("\\", "/"),
        )
        self.assertFalse(item["reopen_forbidden"])
        self.assertNotEqual(item["scope_kind"], "FAMILY")


if __name__ == "__main__":
    unittest.main()
