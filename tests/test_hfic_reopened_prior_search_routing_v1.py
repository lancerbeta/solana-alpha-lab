from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_control_integrity import (  # noqa: E402
    CURRENT_REPRESENTATION_CONTROL_V1,
    control_packet_has_raw_sequences,
)
from solana_alpha_lab.factory.hfic_memory_policy import (  # noqa: E402
    REASON_PRE_CAPABILITY_BASELINE,
    apply_memory_policy,
    hypothesis_search_eligible,
    iter_search_memory_hypothesis_payloads,
    preview_memory_policy,
)
from solana_alpha_lab.factory.hfic_preflight import (  # noqa: E402
    HficPreflightError,
    MAX_PACKET_BYTES,
    build_forge_context_packet,
    decide_preflight_action,
    evidence_epoch_material,
    rank_prior_candidate_ids,
)
from solana_alpha_lab.factory.hfic_prior_memory import (  # noqa: E402
    build_prior_memory_snapshot,
)
from solana_alpha_lab.factory.hfic_reopened_prior_routing import (  # noqa: E402
    BODY_INCOMPLETE,
    BODY_UNRESOLVABLE,
    DEFECTIVE_CONTROL_SESSION_ID,
    IDENTITY_CONFLICT,
    NO_CHANGE,
    READY_TERMINAL,
    ReopenedPriorRoutingError,
    commission_reopened_priors,
    freeze_reopened_prior_compat_smoke,
    overlay_search_payloads,
    ranked_prior_entries_for_ids,
    reopened_inventory,
    resolve_all_reopened_priors,
    resolve_reopened_prior,
)
from solana_alpha_lab.factory.hfic_session import (  # noqa: E402
    PROMPT_VERSION,
    evidence_epoch_sha256,
    focus_key_sha256,
    search_key_sha256,
)
from solana_alpha_lab.factory.hfic_suppression_semantics import (  # noqa: E402
    OWNER_PRIORITY_PARK,
    SCIENTIFIC_CLOSE_VALID,
    SCOPE_LIMITED_CLOSE,
    candidate_matches_hard_close,
    classify_source_payload,
    family_hard_close_terminals,
)
from solana_alpha_lab.factory.research_store import (  # noqa: E402
    RecordKind,
    ResearchEvent,
    ResearchStore,
)
from tests.test_hfic_cli import run_cli  # noqa: E402
from tests.test_hfic_operational_memory_quarantine_v1 import (  # noqa: E402
    _session_records,
)

CREATED = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
CLOCK = lambda: CREATED  # noqa: E731
H11 = "HYP-RC002-H11-LIFECYCLE-CLOCK-V1"
H13 = "RC001-H13-COMPOSITE-VETO"


def _event(
    *,
    record_id: str,
    kind: RecordKind,
    entity_id: str,
    payload: dict[str, object],
    transaction_id: str,
    hypothesis_version_id: str | None = None,
) -> ResearchEvent:
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return ResearchEvent(
        record_id=record_id,
        record_kind=kind,
        entity_id=entity_id,
        hypothesis_version_id=hypothesis_version_id,
        run_id=None,
        transaction_id=transaction_id,
        effective_at=CREATED,
        first_reliable_available_at=CREATED,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id="CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001",
        producer_git_sha="0" * 40,
        created_at=CREATED,
    )


def _hyp(
    hyp_id: str,
    claim: str,
    *,
    hfic: bool = False,
    session_id: str | None = None,
) -> ResearchEvent:
    payload: dict[str, object] = {
        "hypothesis_version_id": hyp_id,
        "claim": claim,
        "statement": claim,
        "mechanism": claim,
        "primary_x_family": claim,
    }
    if hfic:
        payload["hfic_protocol"] = "HFIC-V1.2"
        payload["session_id"] = session_id or DEFECTIVE_CONTROL_SESSION_ID
    return _event(
        record_id=f"REC-{hyp_id}",
        kind=RecordKind.HYPOTHESIS_VERSION,
        entity_id=hyp_id,
        payload=payload,
        transaction_id="RESEARCH-TXN-REOPEN-TEST",
        hypothesis_version_id=hyp_id,
    )


class ReopenedInventoryTests(unittest.TestCase):
    def test_h11_h13_reopenable_and_generic_inventory(self) -> None:
        items = reopened_inventory(ROOT)
        ids = {
            resolve_reopened_prior(ROOT, item)["hypothesis_version_id"] for item in items
        }
        self.assertEqual(ids, {H11, H13})
        for item in items:
            self.assertTrue(item["visible_as_prior_work"])
            self.assertFalse(item["reopen_forbidden"])
            self.assertEqual(item["suppression_class"], OWNER_PRIORITY_PARK)
        source = Path(__file__).read_text(encoding="utf-8")
        routing = (
            ROOT / "src/solana_alpha_lab/factory/hfic_reopened_prior_routing.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("HYP-RC002-H11-LIFECYCLE-CLOCK-V1", routing.split("def reopened_inventory")[1].split("def resolve_reopened_prior")[0])

    def test_scientific_family_close_stays_hard_closed(self) -> None:
        item = classify_source_payload(
            {
                "scientific_terminal": "CLOSE_TAKER_VOLUME_MIX_FAMILY",
                "family_close": True,
                "atom_id": "SYNTHETIC_TAKER_MIX_FALSIFIER_V1",
                "criteria": {"ran": True},
                "cohort": {"n": 60},
                "source_runtime_receipt_sha256": "ab" * 32,
            },
            terminal="CLOSE_TAKER_VOLUME_MIX_FAMILY",
            source_receipt="docs/evidence/synthetic/a1_family_close.json",
        )
        self.assertTrue(item["reopen_forbidden"])
        self.assertEqual(item["suppression_class"], SCIENTIFIC_CLOSE_VALID)
        self.assertNotEqual(family_hard_close_terminals([item]), [])
        inventory_terminals = {row["terminal"] for row in reopened_inventory(ROOT)}
        self.assertNotIn(item["terminal"], inventory_terminals)
        card = {
            "primary_x_family": "TAKER_VOLUME_MIX",
            "claim": "taker volume mix remains closed",
            "mechanism": "family close",
        }
        self.assertIsNotNone(candidate_matches_hard_close(card, [item]))

    def test_scope_limited_close_remains_scoped(self) -> None:
        item = classify_source_payload(
            {"rule_id": "HOLDER_CONCENTRATION_TOP_QUARTILE_VETO_V1"},
            terminal="CLOSE_RULE_HOLDER_CONCENTRATION",
            source_receipt="docs/evidence/synthetic/a1_rule_close.json",
        )
        self.assertTrue(item["reopen_forbidden"])
        self.assertEqual(item["suppression_class"], SCOPE_LIMITED_CLOSE)
        self.assertNotIn(
            item["terminal"],
            {row["terminal"] for row in reopened_inventory(ROOT)},
        )


class CanonicalProjectionTests(unittest.TestCase):
    def test_source_hashes_and_unknown_fields(self) -> None:
        resolved = {item["hypothesis_version_id"]: item for item in resolve_all_reopened_priors(ROOT)}
        for hyp_id in (H11, H13):
            item = resolved[hyp_id]
            hashes = item["provenance"]["source_content_sha256"]
            self.assertTrue(hashes)
            for rel, digest in hashes.items():
                self.assertEqual(
                    digest,
                    hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(),
                )
            payload = item["payload"]
            self.assertIsNone(payload.get("claim"))
            self.assertIsNone(payload.get("mechanism"))
            self.assertIsNone(payload.get("cheapest_falsifier"))
            self.assertIsNone(payload.get("primary_x_family"))
            legacy = payload["legacy_definition"]
            self.assertTrue(legacy)
            if hyp_id == H11:
                self.assertTrue(str(legacy.get("primary_question") or "").strip())
                self.assertNotEqual(payload.get("claim"), legacy.get("primary_question"))
            if hyp_id == H13:
                self.assertTrue(str(legacy.get("falsifier") or "").strip())
                self.assertEqual(
                    (legacy.get("historical_expected_admissibility") or {}).get("state"),
                    "BLOCKED_DATA",
                )
            self.assertFalse(str(item["record_id"]).startswith("HFIC-"))
            self.assertNotIn("hfic_protocol", payload)

    def test_missing_canonical_body_fails_typed(self) -> None:
        item = {
            "visible_as_prior_work": True,
            "reopen_forbidden": False,
            "source_receipt": "docs/evidence/missing/no-such.json",
            "terminal": "PARK_UNKNOWN",
        }
        with self.assertRaises(ReopenedPriorRoutingError) as raised:
            resolve_reopened_prior(ROOT, item)
        self.assertEqual(raised.exception.code, BODY_UNRESOLVABLE)


class CommissionAndMemoryTests(unittest.TestCase):
    def test_idempotent_conflict_and_non_hfic_visibility(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            first = commission_reopened_priors(
                store, ROOT, git_sha="0" * 40, clock=CLOCK, confirm_append_only=True
            )
            self.assertEqual(first["status"], "APPENDED")
            self.assertEqual(first["appended"], 2)
            second = commission_reopened_priors(
                store, ROOT, git_sha="0" * 40, clock=CLOCK, confirm_append_only=True
            )
            self.assertEqual(second["status"], NO_CHANGE)
            ids = {
                str(item.get("hypothesis_version_id") or "")
                for item in iter_search_memory_hypothesis_payloads(store)
            }
            self.assertEqual({H11, H13}, ids & {H11, H13})
            for payload in iter_search_memory_hypothesis_payloads(store):
                self.assertTrue(
                    hypothesis_search_eligible(payload, [DEFECTIVE_CONTROL_SESSION_ID])
                )

        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            store.append(
                [
                    _event(
                        record_id="HV-CONFLICT-H11",
                        kind=RecordKind.HYPOTHESIS_VERSION,
                        entity_id=H11,
                        payload={
                            "hypothesis_version_id": H11,
                            "claim": "DIFFERENT CLAIM MUST CONFLICT",
                            "provenance": {
                                "source_content_sha256": {"x": "00" * 32},
                                "frozen_definition_sha256": "11" * 32,
                            },
                        },
                        transaction_id="RESEARCH-TXN-CONFLICT-H11",
                        hypothesis_version_id=H11,
                    )
                ],
                transaction_id="RESEARCH-TXN-CONFLICT-H11",
            )
            with self.assertRaises(ReopenedPriorRoutingError) as raised:
                commission_reopened_priors(
                    store, ROOT, git_sha="0" * 40, clock=CLOCK, confirm_append_only=True
                )
            self.assertEqual(raised.exception.code, IDENTITY_CONFLICT)

    def test_quarantine_hides_hfic_not_commissioned_priors(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            session_id = DEFECTIVE_CONTROL_SESSION_ID
            cycle = _session_records(session_id, ["HFIC-CAND-DEFECT-001"])
            store.append(cycle, transaction_id=cycle[0].transaction_id)
            store.append(
                [
                    _hyp("HYP-EARLY-TAKER-VOLUME-MIX-H900-V1", "taker volume mix"),
                ],
                transaction_id="RESEARCH-TXN-REOPEN-TEST",
            )
            commission_reopened_priors(
                store, ROOT, git_sha="0" * 40, clock=CLOCK, confirm_append_only=True
            )
            before = {
                str(item.get("hypothesis_version_id"))
                for item in iter_search_memory_hypothesis_payloads(store)
            }
            self.assertIn("HFIC-CAND-DEFECT-001", before)
            self.assertIn(H11, before)
            original = next(
                record.payload_json
                for record in store.iter_committed_records()
                if record.record_id == "HFIC-HYP-HFIC-CAND-DEFECT-001"
            )
            proposal = preview_memory_policy(
                store,
                repo_root=ROOT,
                quarantine_session_ids=[session_id],
                reason_code=REASON_PRE_CAPABILITY_BASELINE,
            )
            apply_memory_policy(
                store,
                repo_root=ROOT,
                proposal=proposal["proposal"],
                confirm_append_only=True,
            )
            after = {
                str(item.get("hypothesis_version_id"))
                for item in iter_search_memory_hypothesis_payloads(store)
            }
            self.assertNotIn("HFIC-CAND-DEFECT-001", after)
            self.assertIn(H11, after)
            self.assertIn(H13, after)
            unchanged = next(
                record.payload_json
                for record in store.iter_committed_records()
                if record.record_id == "HFIC-HYP-HFIC-CAND-DEFECT-001"
            )
            self.assertEqual(original, unchanged)

    def test_epoch_and_eligibility_and_start_new_session(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_root = Path(raw)
            store = ResearchStore(data_root)
            store.append(
                _session_records(
                    DEFECTIVE_CONTROL_SESSION_ID, ["HFIC-CAND-DEFECT-001"]
                ),
                transaction_id=f"RESEARCH-TXN-{DEFECTIVE_CONTROL_SESSION_ID}",
            )
            old_epoch = evidence_epoch_sha256(evidence_epoch_material(ROOT, data_root))
            commission_reopened_priors(
                store, ROOT, git_sha="0" * 40, clock=CLOCK, confirm_append_only=True
            )
            new_epoch = evidence_epoch_sha256(evidence_epoch_material(ROOT, data_root))
            self.assertNotEqual(old_epoch, new_epoch)
            policy = preview_memory_policy(
                store,
                repo_root=ROOT,
                quarantine_session_ids=[DEFECTIVE_CONTROL_SESSION_ID],
                reason_code=REASON_PRE_CAPABILITY_BASELINE,
            )
            self.assertNotEqual(
                policy["memory_eligibility_sha256_before"],
                policy["memory_eligibility_sha256_after"],
            )
            apply_memory_policy(
                store,
                repo_root=ROOT,
                proposal=policy["proposal"],
                confirm_append_only=True,
            )
            action, _sid = decide_preflight_action(
                [
                    {
                        "session_id": DEFECTIVE_CONTROL_SESSION_ID,
                        "session_state": "SYNTHESIS_COMPLETE",
                        "evidence_epoch_sha256": old_epoch,
                        "focus_key_sha256": focus_key_sha256("AUTO"),
                        "search_key_sha256": search_key_sha256(
                            old_epoch,
                            "AUTO",
                            PROMPT_VERSION,
                            policy["memory_eligibility_sha256_before"],
                            CURRENT_REPRESENTATION_CONTROL_V1,
                        ),
                        "owner_focus": "AUTO",
                        "memory_eligibility_sha256": policy[
                            "memory_eligibility_sha256_before"
                        ],
                        "evidence_surface_mode": CURRENT_REPRESENTATION_CONTROL_V1,
                    }
                ],
                search_key=search_key_sha256(
                    new_epoch,
                    "AUTO",
                    PROMPT_VERSION,
                    policy["memory_eligibility_sha256_after"],
                    CURRENT_REPRESENTATION_CONTROL_V1,
                ),
                evidence_epoch=new_epoch,
                focus_key=focus_key_sha256("AUTO"),
                owner_focus="AUTO",
                memory_eligibility_sha256=policy["memory_eligibility_sha256_after"],
                evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1,
            )
            self.assertEqual(action, "START_NEW_SESSION")


class PromptABodyTests(unittest.TestCase):
    def test_ranked_ids_have_bodies_and_mismatch_fails(self) -> None:
        payloads = resolve_all_reopened_priors(ROOT)
        bodies = [item["payload"] for item in payloads]
        ranked = [H11, H13]
        entries = ranked_prior_entries_for_ids(ranked, bodies)
        self.assertEqual({item["hypothesis_version_id"] for item in entries}, set(ranked))
        for entry in entries:
            self.assertTrue(
                str(entry.get("claim") or "").strip()
                or (entry.get("legacy_definition") or {})
            )
            self.assertNotEqual(
                entry.get("claim"),
                (entry.get("legacy_definition") or {}).get("primary_question")
                or (entry.get("legacy_definition") or {}).get("falsifier"),
            )
        with self.assertRaises(ReopenedPriorRoutingError) as raised:
            ranked_prior_entries_for_ids(["MISSING-ID"], bodies)
        self.assertEqual(raised.exception.code, BODY_INCOMPLETE)
        with self.assertRaises(ReopenedPriorRoutingError) as empty:
            ranked_prior_entries_for_ids(
                ["EMPTY-ID"],
                [{"hypothesis_version_id": "EMPTY-ID"}],
            )
        self.assertEqual(empty.exception.code, BODY_INCOMPLETE)

    def test_packet_one_to_one_within_16kib_and_no_silent_drop(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_root = Path(raw)
            store = ResearchStore(data_root)
            store.append(
                [
                    _hyp("HYP-EARLY-TAKER-VOLUME-MIX-H900-V1", "taker volume mix"),
                    _hyp("HYP-QUOTE-NATIVE-FRICTION-H900-V1", "quote native friction"),
                    _hyp(
                        "HFIC-CAND-DEFECT-001",
                        "defective control",
                        hfic=True,
                    ),
                ],
                transaction_id="RESEARCH-TXN-REOPEN-TEST",
            )
            extras = [item["payload"] for item in resolve_all_reopened_priors(ROOT)]
            planned = overlay_search_payloads(
                store, extras, [DEFECTIVE_CONTROL_SESSION_ID]
            )
            packet, _digest = build_forge_context_packet(
                ROOT,
                data_root,
                owner_focus="AUTO",
                evidence_epoch="aa" * 32,
                search_key="bb" * 32,
                commissioning_status="FAST_LANE_COMMISSIONED",
                research_memory_as_of="2026-09-15T00:00:00Z",
                store=store,
                persist=False,
                search_payloads=planned,
                evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1,
            )
            ranked = packet["ranked_prior_candidate_ids"]
            entries = packet["ranked_prior_entries"]
            self.assertEqual(
                {item["hypothesis_version_id"] for item in entries},
                set(ranked),
            )
            self.assertIn(H11, ranked)
            self.assertIn(H13, ranked)
            encoded = json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()
            self.assertLessEqual(len(encoded), MAX_PACKET_BYTES)
            self.assertEqual(packet["evidence_surface_mode"], CURRENT_REPRESENTATION_CONTROL_V1)
            self.assertFalse(control_packet_has_raw_sequences(packet))
            self.assertNotIn("trajectory", packet)
            self.assertNotIn("normalized_trajectory_v1", packet)

            with patch(
                "solana_alpha_lab.factory.hfic_preflight.MAX_PACKET_BYTES",
                64,
            ):
                with self.assertRaises(HficPreflightError) as raised:
                    build_forge_context_packet(
                        ROOT,
                        data_root,
                        owner_focus="AUTO",
                        evidence_epoch="aa" * 32,
                        search_key="bb" * 32,
                        commissioning_status="FAST_LANE_COMMISSIONED",
                        research_memory_as_of="2026-09-15T00:00:00Z",
                        store=store,
                        persist=False,
                        search_payloads=planned,
                    )
                self.assertEqual(
                    str(raised.exception),
                    "FORGE_CONTEXT_PACKET_CAPACITY_EXCEEDED",
                )

    def test_ordinary_ranker_unchanged_except_bodies(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            store.append(
                [
                    _hyp("HYP-AAA-UNRELATED-001", "holder concentration"),
                    _hyp("HYP-MMM-TAKER-VOLUME-001", "taker volume mix"),
                ],
                transaction_id="RESEARCH-TXN-REOPEN-TEST",
            )
            ranked, dropped = rank_prior_candidate_ids(
                store,
                owner_focus="AUTO",
                feature_hints=["FEAT-TAKER-VOLUME-MIX"],
            )
            self.assertEqual(ranked[0], "HYP-MMM-TAKER-VOLUME-001")
            self.assertEqual(dropped, 0)

    def test_commissioned_capsules_validate_critic_schema(self) -> None:
        from jsonschema import Draft202012Validator

        schema = json.loads(
            (
                ROOT / "catalog/schemas/hypothesis_critic_input_v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        capsule_schema = schema["properties"]["prior_memory"]["properties"]["capsules"][
            "items"
        ]
        validator = Draft202012Validator(capsule_schema)
        with tempfile.TemporaryDirectory() as raw:
            store = ResearchStore(Path(raw))
            commission_reopened_priors(
                store, ROOT, git_sha="0" * 40, clock=CLOCK, confirm_append_only=True
            )
            snapshot = build_prior_memory_snapshot(
                store,
                store_inventory_digest=store.diagnostics().committed_inventory_sha256,
                repo_root=ROOT,
            )
            self.assertGreaterEqual(snapshot["emitted_count"], 2)
            for capsule in snapshot["capsules"]:
                validator.validate(capsule)
                if capsule["hypothesis_version_id"] in {H11, H13}:
                    self.assertTrue(capsule.get("legacy_definition"))
                    self.assertTrue(str(capsule.get("park_status") or "").strip())
                    self.assertIsNone(capsule.get("claim"))


class FreezeCompatAndCliTests(unittest.TestCase):
    def test_freeze_compat_typed_unresolved_no_fabricated_ids(self) -> None:
        smoke = freeze_reopened_prior_compat_smoke(ROOT)
        self.assertEqual(smoke["status"], "PASS")
        self.assertEqual(smoke["grounding_terminal"], "GROUNDED_WITH_GAPS")
        self.assertTrue(smoke["unresolved_requirements"])
        self.assertEqual(smoke["critic_packet_version"], "1.4")
        self.assertTrue(all(item.startswith("FEAT-") for item in smoke["feature_ids"]))

    def test_cli_commission_requires_confirm(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            completed = run_cli(
                "commission-reopened-priors",
                "--format",
                "json",
                data_root=Path(raw),
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("CONFIRM_APPEND_ONLY_REQUIRED", completed.stderr + completed.stdout)

    def test_ready_terminal_constant(self) -> None:
        self.assertEqual(
            READY_TERMINAL,
            "CONTROL_RECONSIDERATION_READY_AFTER_COMMISSION",
        )


if __name__ == "__main__":
    unittest.main()
