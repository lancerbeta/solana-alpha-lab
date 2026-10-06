"""Pure semantics of the list selector and scope (D03/D04/D05).

Expected sets are literals from the PRD fixture, not produced by the selector.
"""

from __future__ import annotations

import itertools
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from solana_alpha_lab.factory import hfic_research_scope as rs  # noqa: E402

LISTS = {"A": "L:A", "B": "L:B", "C": "L:C"}
# episode -> member lists (PRD section 17.1)
MEMBERS = {"e1": "A", "e2": "B", "e3": "C", "e4": "AB", "e5": "AC", "e6": "BC", "e7": "ABC"}


def _resolver(ref):
    return rs.resolve_alias(ref, {"A": "L:A", "B": "L:B", "C": "L:C", "D": "L:D", "E": "L:E"}, {f"L:{x}" for x in "ABCDE"})


def _states(letters: str, known: str = "ABC") -> dict[str, str]:
    return {f"L:{x}": (rs.TRUE if x in letters else rs.FALSE) for x in known}


def _select(spec, known="ABC"):
    selector = rs.canonical_selector(spec, _resolver)
    return {e for e, letters in MEMBERS.items() if rs.evaluate_selector(selector, _states(letters, known)) == rs.TRUE}


def _clause(**kw):
    return {"clauses": [kw]}


class SelectorTests(unittest.TestCase):
    def test_literal_sets(self) -> None:
        self.assertEqual(_select({"clauses": [{}]}), set(MEMBERS))
        self.assertEqual(_select(_clause(all_of=["A"])), {"e1", "e4", "e5", "e7"})
        self.assertEqual(_select(_clause(all_of=["B"])), {"e2", "e4", "e6", "e7"})
        self.assertEqual(_select(_clause(all_of=["C"])), {"e3", "e5", "e6", "e7"})
        self.assertEqual(_select(_clause(all_of=["A", "C"])), {"e5", "e7"})
        self.assertEqual(_select(_clause(all_of=["A", "C"], none_of=["B"])), {"e5"})
        self.assertEqual(_select(_clause(count={"of": ["A", "B", "C"], "min": 2, "max": 3})), {"e4", "e5", "e6", "e7"})
        self.assertEqual(_select(_clause(count={"of": ["A", "B", "C"], "min": 2, "max": 2})), {"e4", "e5", "e6"})
        self.assertEqual(_select(_clause(all_of=["A", "B", "C"])), {"e7"})
        self.assertEqual(
            _select({"clauses": [{"all_of": ["A", "B"]}, {"all_of": ["C"], "none_of": ["A"]}]}),
            {"e4", "e7", "e3", "e6"},
        )

    def test_hash_invariance_and_alias_dedup(self) -> None:
        a = rs.canonical_selector(_clause(all_of=["C", "A"]), _resolver)
        b = rs.canonical_selector(_clause(all_of=["L:A", "A", "C"]), _resolver)
        self.assertEqual(rs.selector_sha256(a), rs.selector_sha256(b))
        # two aliases of one list are not "2 of 2"
        with self.assertRaises(rs.ResearchScopeError) as caught:
            rs.canonical_selector(_clause(count={"of": ["A", "L:A"], "min": 2}), _resolver)
        self.assertEqual(caught.exception.code, "SELECTOR_COUNT_BOUNDS_INVALID")

    def test_strict_errors(self) -> None:
        for spec, code in (
            ({"clauses": []}, "SELECTOR_CLAUSES_INVALID"),
            ({"clauses": [{"all_of": ["A"], "none_of": ["A"]}]}, "SELECTOR_CONTRADICTION"),
            ({"clauses": [{"bogus": 1}]}, "SELECTOR_CLAUSE_INVALID"),
            ({"clauses": [{}], "extra": 1}, "SELECTOR_UNKNOWN_FIELD"),
            ({"clauses": [{"count": {"of": ["A"], "min": True}}]}, "SELECTOR_COUNT_INVALID"),
            ({"clauses": [{"all_of": ["Z"]}]}, "LIST_REF_UNKNOWN"),
            ({"clauses": [{}] * 9}, "SELECTOR_CLAUSES_INVALID"),
        ):
            with self.subTest(code=code), self.assertRaises(rs.ResearchScopeError) as caught:
                rs.canonical_selector(spec, _resolver)
            self.assertEqual(caught.exception.code, code)

    def test_coverage_is_part_of_semantics(self) -> None:
        # count 0..2 of {A,B} is a tautology, but D/E are still required observed.
        selector = rs.canonical_selector(_clause(count={"of": ["D", "E"], "min": 0, "max": 2}), _resolver)
        self.assertEqual(selector["required_observed_lists"], ["L:D", "L:E"])
        self.assertEqual(rs.evaluate_selector(selector, {}), rs.UNKNOWN)
        self.assertEqual(rs.evaluate_selector(selector, {"L:D": rs.TRUE, "L:E": rs.FALSE}), rs.TRUE)
        # UNKNOWN is never FALSE: excluding via not-B cannot rely on an unobserved B.
        not_b = rs.canonical_selector(_clause(none_of=["B"]), _resolver)
        self.assertEqual(rs.evaluate_selector(not_b, {"L:B": rs.UNKNOWN}), rs.UNKNOWN)
        self.assertEqual(rs.evaluate_selector(not_b, {"L:B": rs.INVALID}), rs.INVALID)

    def test_five_lists_truth_table_without_enumerating_in_production(self) -> None:
        selector = rs.canonical_selector(_clause(count={"of": list("ABCDE"), "min": 2, "max": 3}, all_of=["A"]), _resolver)
        total = 0
        for bits in itertools.product((False, True), repeat=5):
            states = {f"L:{x}": (rs.TRUE if bit else rs.FALSE) for x, bit in zip("ABCDE", bits)}
            expected = bits[0] and 2 <= sum(bits) <= 3
            total += 1
            self.assertEqual(rs.evaluate_selector(selector, states) == rs.TRUE, expected)
        self.assertEqual(total, 32)

    def test_aliases_ambiguity_refused(self) -> None:
        defs = {"L:A": {"aliases": ["x"]}, "L:B": {"aliases": ["x"]}}
        with self.assertRaises(rs.ResearchScopeError) as caught:
            rs.alias_table(defs)
        self.assertEqual(caught.exception.code, "LIST_ALIAS_AMBIGUOUS")


def _snapshot(members, *, available="2026-10-01T00:00:00Z", start="2026-10-01T00:00:00Z", end="2026-12-01T00:00:00Z", list_id="OWNER:D"):
    return {
        "schema": rs.SNAPSHOT_SCHEMA,
        "schema_version": rs.SNAPSHOT_VERSION,
        "definition": {"list_id": list_id, "definition_version": "1", "provider_or_owner": "OWNER", "kind": "MANUAL_SET", "semantics": {"note": "synthetic"}},
        "member_identity_kind": "MINT",
        "members": members,
        "effective_from": start,
        "effective_until": end,
        "available_at": available,
        "basis": "MANUAL_REGISTERED",
        "completeness": {"kind": "COMPLETE_FOR_INTERVAL"},
    }


class LocalSnapshotTests(unittest.TestCase):
    def _register(self, root: Path, document, at: datetime):
        import json

        path = root / "snap.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return rs.register_local_snapshot(root, path, registered_at=at)

    def test_registration_exact_repeat_conflict_and_no_backdating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registered = datetime(2026, 10, 10, tzinfo=UTC)
            first = self._register(root, _snapshot(["m1", "m2"]), registered)
            self.assertEqual(first["status"], "REGISTERED")
            # declared availability on 10-01 is not accepted: registered 10-10
            self.assertEqual(first["reliable_available_at"], "2026-10-10T00:00:00Z")
            again = self._register(root, _snapshot(["m2", "m1"]), datetime(2026, 11, 1, tzinfo=UTC))
            self.assertEqual(again["status"], "PASS_ALREADY_PRESENT_EXACT")
            with self.assertRaises(rs.ResearchScopeError) as caught:
                self._register(root, _snapshot(["m1"]), registered)
            self.assertEqual(caught.exception.code, "SNAPSHOT_INTERVAL_CONFLICT")
            with self.assertRaises(rs.ResearchScopeError) as caught:
                self._register(root, _snapshot(["m1"], list_id="JUPITER:x:5m", start="2027-01-01T00:00:00Z", end="2027-02-01T00:00:00Z"), registered)
            self.assertEqual(caught.exception.code, "SNAPSHOT_LIST_ID_RESERVED")

    def test_membership_at_t0_unknown_before_availability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._register(root, _snapshot(["m1"]), datetime(2026, 10, 10, tzinfo=UTC))
            evidence = rs.MembershipEvidence()
            evidence.t0 = {"old": datetime(2026, 10, 5, tzinfo=UTC), "new_in": datetime(2026, 10, 12, tzinfo=UTC), "new_out": datetime(2026, 10, 12, tzinfo=UTC)}
            evidence.mints = {"old": "m1", "new_in": "m1", "new_out": "m9"}
            rs.add_local_snapshots(evidence, root)
            self.assertEqual(evidence.state("old", "OWNER:D"), rs.UNKNOWN)
            self.assertEqual(evidence.state("new_in", "OWNER:D"), rs.TRUE)
            self.assertEqual(evidence.state("new_out", "OWNER:D"), rs.FALSE)


if __name__ == "__main__":
    unittest.main()
