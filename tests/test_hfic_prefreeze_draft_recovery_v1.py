"""Pre-freeze generated-draft recovery across a capability-only repair.

The disposable store is synthetic. These tests do not read or write the
owner ResearchStore, do not run Prompt A, and do not open a second trial.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.hfic_evidence_identity import (
    compute_capability_epoch_for_repo,
)
from solana_alpha_lab.factory.hfic_session import (
    HficSessionError,
    find_generated_draft,
    freeze_draft,
    list_hfic_sessions,
    list_scientific_slot_admissions,
    persist_generated_draft,
    prefreeze_generated_draft_recovery,
)
from solana_alpha_lab.factory.research_store import ResearchStore
from tests.test_forge_evidence_identity_and_owner_gold_v1 import (
    _append_c3,
    _control_stamped_preflight,
    _enumerate_c3,
    _enumerate_production_fixture,
    _fresh_v12_draft,
    _run_production_preflight,
    _write_lineage,
)

CAPABILITY_B = "ab" * 32


def _capability_b(_repo: Path) -> tuple[str, dict[str, str]]:
    return CAPABILITY_B, {"basis_version": "TEST_CAPABILITY_B"}


def _artifact_rows(
    store: ResearchStore,
    kind: str,
    *,
    lifecycle: str | None = None,
) -> list[dict[str, object]]:
    rows = []
    for record in store.iter_committed_records():
        record_kind = getattr(record.record_kind, "value", record.record_kind)
        if record_kind != "RESEARCH_ARTIFACT":
            continue
        payload = json.loads(record.payload_json)
        if payload.get("artifact_kind") != kind:
            continue
        if lifecycle is not None and payload.get("draft_lifecycle") != lifecycle:
            continue
        rows.append(
            {
                "record_id": record.record_id,
                "payload_sha256": record.payload_sha256,
                "body_sha256": payload.get("payload_sha256"),
            }
        )
    return rows


def _prose_draft(preflight: dict[str, object], text: str) -> dict[str, object]:
    draft = _fresh_v12_draft(preflight)
    draft["candidates"][0]["material_difference_from_prior"] = text
    return draft


class PrefreezeDraftRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        real_capability, _basis = compute_capability_epoch_for_repo(ROOT)
        self.assertNotEqual(real_capability, CAPABILITY_B)
        self.capability_a = real_capability

    def _occupied(self, data_root: Path) -> tuple[ResearchStore, dict[str, object], str]:
        _write_lineage(data_root)
        store = ResearchStore(data_root)
        preflight = _control_stamped_preflight(data_root, store)
        self.assertEqual(preflight.get("action"), "START_NEW_SESSION")
        draft = _prose_draft(preflight, "Weak: prose label stays valid")
        with patch(
            "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
            side_effect=_enumerate_production_fixture,
        ):
            saved = persist_generated_draft(
                store,
                draft,
                preflight_receipt=preflight,
                repo_root=ROOT,
                representation_id="BASE",
            )
        self.assertEqual(saved.get("capability_epoch_sha256"), self.capability_a)
        self.assertEqual(list_hfic_sessions(store), [])
        self.assertEqual(len(list_scientific_slot_admissions(store)), 1)
        return store, draft, str(saved["payload_sha256"])

    def test_bad_draft_fails_before_slot_reservation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _write_lineage(data_root)
            store = ResearchStore(data_root)
            preflight = _control_stamped_preflight(data_root, store)
            before = store.diagnostics().committed_inventory_sha256
            draft = _prose_draft(preflight, "file:///tmp/x")
            with self.assertRaises(HficSessionError) as raised:
                persist_generated_draft(
                    store,
                    draft,
                    preflight_receipt=preflight,
                    repo_root=ROOT,
                    representation_id="BASE",
                )
            self.assertEqual(str(raised.exception), "PHYSICAL_PATH_FORBIDDEN")
            self.assertEqual(
                store.diagnostics().committed_inventory_sha256,
                before,
            )
            self.assertEqual(list_scientific_slot_admissions(store), [])
            self.assertEqual(_artifact_rows(store, "FORGE_DRAFT"), [])
            self.assertEqual(list_hfic_sessions(store), [])

    def test_capability_repair_freezes_the_exact_saved_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            store, draft, draft_sha = self._occupied(data_root)
            slot = str(
                list_scientific_slot_admissions(store)[0]["scientific_slot_sha256"]
            )
            market = str(
                list_scientific_slot_admissions(store)[0][
                    "market_evidence_epoch_sha256"
                ]
            )
            admission_before = _artifact_rows(store, "SCIENTIFIC_SLOT_ADMISSION")
            draft_before = _artifact_rows(
                store, "FORGE_DRAFT", lifecycle="GENERATED_BEFORE_FREEZE"
            )
            self.assertEqual(len(admission_before), 1)
            self.assertEqual(len(draft_before), 1)

            with patch(
                "solana_alpha_lab.factory.hfic_evidence_identity.compute_capability_epoch_for_repo",
                side_effect=_capability_b,
            ), patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
            ):
                resumed = _control_stamped_preflight(data_root, store)
                self.assertEqual(resumed.get("action"), "RESUME_EXISTING_SESSION")
                self.assertEqual(resumed.get("generated_draft_sha256"), draft_sha)
                self.assertIs(resumed.get("prefreeze_capability_repair"), True)
                self.assertEqual(
                    resumed.get("generated_draft_capability_epoch_sha256"),
                    self.capability_a,
                )
                self.assertEqual(resumed.get("capability_epoch_sha256"), CAPABILITY_B)
                self.assertNotEqual(
                    resumed.get("generated_draft_capability_epoch_sha256"),
                    resumed.get("capability_epoch_sha256"),
                )
                self.assertEqual(
                    len(_artifact_rows(store, "SCIENTIFIC_SLOT_ADMISSION")),
                    1,
                )
                self.assertEqual(list_hfic_sessions(store), [])
                from solana_alpha_lab.factory.hfic_representation_ladder import (
                    evaluate_forge_run,
                )

                forge_run = evaluate_forge_run(
                    ROOT,
                    data_root,
                    owner_focus="AUTO",
                    persist=False,
                )
                self.assertEqual(forge_run.get("next_action"), "RESUME_BASE")
                self.assertIsNone(forge_run.get("owner_final"))
                self.assertNotIn(
                    "SCIENTIFIC_SLOT_OCCUPIED_READBACK_MISSING",
                    list(forge_run.get("blocking_reason_codes") or []),
                )

                mutated = json.loads(json.dumps(draft))
                mutated["candidates"][0]["claim"] += " mutated bytes"
                with self.assertRaises(HficSessionError):
                    freeze_draft(
                        mutated,
                        preflight_receipt=resumed,
                        store=store,
                        repo_root=ROOT,
                        verify_current_market_identity=True,
                    )
                self.assertEqual(list_hfic_sessions(store), [])

                frozen = freeze_draft(
                    draft,
                    preflight_receipt=resumed,
                    store=store,
                    repo_root=ROOT,
                    verify_current_market_identity=True,
                )

            self.assertEqual(frozen.get("scientific_slot_sha256"), slot)
            self.assertEqual(frozen.get("market_evidence_epoch_sha256"), market)
            self.assertIs(frozen.get("prefreeze_capability_repair"), True)
            self.assertEqual(
                frozen.get("generated_draft_capability_epoch_sha256"),
                self.capability_a,
            )
            self.assertEqual(
                frozen.get("recovery_capability_epoch_sha256"),
                CAPABILITY_B,
            )
            self.assertNotEqual(
                frozen.get("generated_draft_capability_epoch_sha256"),
                frozen.get("recovery_capability_epoch_sha256"),
            )
            self.assertIn("critic_input_packet", frozen)
            self.assertTrue(frozen.get("critic_input_packet_sha256"))
            sessions = list_hfic_sessions(store)
            self.assertEqual(len(sessions), 1)
            self.assertEqual(len(list_scientific_slot_admissions(store)), 1)
            self.assertEqual(
                _artifact_rows(store, "SCIENTIFIC_SLOT_ADMISSION"),
                admission_before,
            )
            self.assertEqual(
                _artifact_rows(
                    store, "FORGE_DRAFT", lifecycle="GENERATED_BEFORE_FREEZE"
                ),
                draft_before,
            )
            saved = find_generated_draft(
                store,
                market_evidence_epoch_sha256=market,
                owner_focus="AUTO",
                representation_id="BASE",
                representation_semantic_version="HFIC-V1.2",
                scientific_slot_sha256=slot,
            )
            self.assertIsNotNone(saved)
            assert saved is not None
            self.assertEqual(saved.get("payload_sha256"), draft_sha)

    def test_market_change_does_not_reuse_the_old_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            store, _draft, draft_sha = self._occupied(data_root)
            _append_c3(data_root)
            moved = _run_production_preflight(
                data_root,
                evidence_surface_mode="CURRENT_REPRESENTATION_CONTROL_V1",
                enumerator=_enumerate_c3,
            )
            self.assertNotEqual(moved.get("generated_draft_sha256"), draft_sha)
            self.assertNotEqual(moved.get("action"), "RESUME_EXISTING_SESSION")
            self.assertEqual(len(list_scientific_slot_admissions(store)), 1)
            self.assertEqual(list_hfic_sessions(store), [])

    def test_other_identity_axes_deny_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            store, _draft, _sha = self._occupied(data_root)
            admission = list_scientific_slot_admissions(store)[0]
            saved = find_generated_draft(
                store,
                market_evidence_epoch_sha256=str(
                    admission["market_evidence_epoch_sha256"]
                ),
                owner_focus="AUTO",
                representation_id="BASE",
                representation_semantic_version="HFIC-V1.2",
                scientific_slot_sha256=str(admission["scientific_slot_sha256"]),
            )
            assert saved is not None
            common = {
                "sessions": [],
                "reservations": list_scientific_slot_admissions(store),
                "market_evidence_epoch_sha256": admission[
                    "market_evidence_epoch_sha256"
                ],
                "scientific_slot_sha256": admission["scientific_slot_sha256"],
                "representation_id": "BASE",
                "representation_semantic_version": "HFIC-V1.2",
                "owner_focus": "AUTO",
                "capability_epoch_sha256": CAPABILITY_B,
                "memory_eligibility_sha256": admission["memory_eligibility_sha256"],
                "evidence_surface_mode": admission["evidence_surface_mode"],
            }
            self.assertTrue(prefreeze_generated_draft_recovery(saved, **common))
            denied = {
                "owner_focus": "OTHER-FOCUS",
                "memory_eligibility_sha256": "cd" * 32,
                "evidence_surface_mode": None,
                "representation_id": "NORMALIZED_TRAJECTORY_V1",
                "market_evidence_epoch_sha256": "ef" * 32,
            }
            for key, value in denied.items():
                with self.subTest(axis=key):
                    kwargs = dict(common)
                    kwargs[key] = value
                    self.assertFalse(
                        prefreeze_generated_draft_recovery(saved, **kwargs)
                    )

    def test_frozen_session_does_not_gain_the_prefreeze_exception(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            store, draft, _sha = self._occupied(data_root)
            preflight = _control_stamped_preflight(data_root, store)
            self.assertEqual(preflight.get("action"), "RESUME_EXISTING_SESSION")
            self.assertNotIn("prefreeze_capability_repair", preflight)
            admission_before = _artifact_rows(store, "SCIENTIFIC_SLOT_ADMISSION")
            with patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                side_effect=_enumerate_production_fixture,
            ):
                freeze_draft(
                    draft,
                    preflight_receipt=preflight,
                    store=store,
                    repo_root=ROOT,
                    verify_current_market_identity=True,
                )
            self.assertEqual(len(list_hfic_sessions(store)), 1)
            with patch(
                "solana_alpha_lab.factory.hfic_evidence_identity.compute_capability_epoch_for_repo",
                side_effect=_capability_b,
            ):
                blocked = _control_stamped_preflight(data_root, store)
            self.assertEqual(blocked.get("action"), "STOP")
            self.assertEqual(
                blocked.get("terminal"),
                "SCIENTIFIC_SLOT_OCCUPIED_DIFFERENT_EXECUTION_BINDING",
            )
            self.assertNotIn("prefreeze_capability_repair", blocked)
            self.assertEqual(len(list_hfic_sessions(store)), 1)
            self.assertEqual(
                _artifact_rows(store, "SCIENTIFIC_SLOT_ADMISSION"),
                admission_before,
            )


if __name__ == "__main__":
    unittest.main()
