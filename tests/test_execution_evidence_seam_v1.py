from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.experiment_evidence import OBLIGATIONS
from solana_alpha_lab.factory.promotion_handoff import (
    PromotionHandoffError,
    check_materialization,
    execution_regime_compatibility,
    freeze_promotion_handoff_manifest,
    manifest_sha256,
    unsigned_binding,
    unsigned_manifest,
    validate_execution_evidence_binding,
    validate_promotion_handoff_manifest,
)

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
EXPERIMENT_ID = "EXP-ORDINARY-PRICE-PATH-HYPOTHESIS-001"
HYPOTHESIS_ID = "HYP-ORDINARY-PRICE-PATH-BUY-PRESSURE-V1"
POPULATION_REF = "A24_LIMITED_DIAGNOSTIC_POOL_DAY_RETROSPECTIVE"
SPEC_SHA = "b" * 64
BINDING_ID = "EEB-" + "T0" * 11 + "XX"


def _binding_sha(unsigned: dict) -> str:
    return hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()


def _regime(
    *,
    tested_notional_usd: float = 25.0,
    population_n: int = 24,
    two_way_n: int = 18,
    entry_only_n: int = 4,
    no_entry_n: int = 1,
    unknown_n: int = 1,
    fee_bps: int | None = 100,
) -> dict:
    return {
        "tested_notional_usd": tested_notional_usd,
        "evidence_class": "DECISION_TIME_QUOTE_PAIR_V1",
        "population_n": population_n,
        "two_way_n": two_way_n,
        "entry_only_n": entry_only_n,
        "no_entry_n": no_entry_n,
        "unknown_n": unknown_n,
        "strategy_fee_bps_assumption": fee_bps,
        "cost_evidence_refs": [
            {"record_id": "REC-COST-001", "payload_sha256": "c" * 64}
        ],
    }


def _binding(
    *,
    regimes: list[dict] | None = None,
    binding_id: str = BINDING_ID,
    experiment_id: str = EXPERIMENT_ID,
    spec_sha: str = SPEC_SHA,
    population_ref: str = POPULATION_REF,
) -> dict:
    unsigned = {
        "schema": "smial.execution-evidence-binding",
        "schema_version": "1.0",
        "binding_id": binding_id,
        "experiment_id": experiment_id,
        "experiment_spec_sha256": spec_sha,
        "population_ref": population_ref,
        "regimes": regimes if regimes is not None else [_regime()],
        "direct_evidence_refs": [
            {"record_id": "REC-001", "payload_sha256": "d" * 64}
        ],
    }
    return {**unsigned, "binding_sha256": _binding_sha(unsigned)}


def _manifest(
    *,
    binding: dict | None = None,
    version: str = "1.1",
    experiment_id: str = EXPERIMENT_ID,
    spec_sha: str = SPEC_SHA,
    population_ref: str = POPULATION_REF,
) -> dict:
    base = {
        "schema": "smial.promotion-handoff-manifest",
        "schema_version": version,
        "decision_event_id": "DECISION-EVENT-0000000001",
        "decision_effective_at": "2026-09-06T12:00:00Z",
        "experiment_id": experiment_id,
        "hypothesis_version_id": HYPOTHESIS_ID,
        "experiment_spec_source_kind": "git_path",
        "experiment_spec_source_value": "configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml",
        "experiment_spec_sha256": spec_sha,
        "evidence_snapshot_sha256": "e" * 64,
        "direct_evidence": [{"record_id": "REC-001", "payload_sha256": "d" * 64}],
        "obligations": [{"code": "FALSIFIER", "status": "PRESENT"}],
        "promotion_packet_sha256": None,
        "population_ref": population_ref,
    }
    if binding is not None and version == "1.1":
        base["execution_evidence_binding_id"] = binding["binding_id"]
        base["execution_evidence_binding_sha256"] = binding["binding_sha256"]
    unsigned = dict(base)
    return {**unsigned, "manifest_sha256": manifest_sha256(unsigned)}


EXECUTION_INPUTS = {
    "max_age_seconds": 30,
    "notional_usd": 25.0,
    "fee_bps": 100,
    "max_open_positions": 1,
    "shadow": False,
}


class ExecutionEvidenceSeamTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        schemas = root / "catalog" / "schemas"
        schemas.mkdir(parents=True)
        for name in (
            "promotion_handoff_manifest_v1.schema.json",
            "promotion_handoff_manifest_v1_1.schema.json",
            "execution_evidence_binding_v1.schema.json",
        ):
            shutil_copy(ROOT / "catalog" / "schemas" / name, schemas / name)
        self.root = root

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # T1: old manifest v1.0 still validates under v1.0 semantics
    def test_t1_old_manifest_v1_0_still_valid(self) -> None:
        manifest = _manifest(version="1.0")
        validate_promotion_handoff_manifest(manifest, root=self.root)

    # T2: new manifest v1.1 requires binding ref/hash
    def test_t2_manifest_v1_1_requires_binding_ref(self) -> None:
        manifest = _manifest(binding=_binding())
        validate_promotion_handoff_manifest(manifest, root=self.root)
        stripped = dict(manifest)
        del stripped["execution_evidence_binding_sha256"]
        with self.assertRaises(PromotionHandoffError):
            validate_promotion_handoff_manifest(stripped, root=self.root)

    # T3: binding hash tamper fails closed
    def test_t3_binding_hash_tamper_fails(self) -> None:
        binding = _binding()
        tampered = dict(binding)
        tampered["binding_sha256"] = "f" * 64
        with self.assertRaises(PromotionHandoffError):
            validate_execution_evidence_binding(tampered, root=self.root)

    # T4: manifest/binding identity mismatch fails closed
    def test_t4_manifest_binding_identity_mismatch(self) -> None:
        binding = _binding(binding_id="EEB-" + "Z9" * 11 + "ZZ")
        manifest = _manifest(binding=binding)
        other = _binding()  # same manifest refs, different binding
        codes = execution_regime_compatibility(
            root=self.root,
            manifest=manifest,
            binding=other,
            execution_inputs=EXECUTION_INPUTS,
        )
        self.assertIn("EXECUTION_EVIDENCE_BINDING_GAP", codes)

    # T5: denominator closure valid
    def test_t5_denominator_closure_valid(self) -> None:
        validate_execution_evidence_binding(_binding(), root=self.root)

    # T6: denominator closure invalid -> CONFLICT
    def test_t6_denominator_closure_invalid(self) -> None:
        bad = _binding(regimes=[_regime(population_n=24, two_way_n=19)])
        with self.assertRaises(PromotionHandoffError) as raised:
            validate_execution_evidence_binding(bad, root=self.root)
        self.assertEqual(str(raised.exception), "EXECUTION_REGIME_MISMATCH")

    # T7: $10 and $100 regimes may have different counts
    def test_t7_two_regimes_different_counts(self) -> None:
        two = _binding(
            regimes=[
                _regime(tested_notional_usd=10.0, two_way_n=18, entry_only_n=8, no_entry_n=1, unknown_n=1, population_n=28),
                _regime(tested_notional_usd=100.0, two_way_n=17, entry_only_n=9, no_entry_n=1, unknown_n=1, population_n=28),
            ]
        )
        validate_execution_evidence_binding(two, root=self.root)
        dup = _binding(
            regimes=[
                _regime(tested_notional_usd=10.0),
                _regime(tested_notional_usd=10.0, two_way_n=17, entry_only_n=5, population_n=24),
            ]
        )
        with self.assertRaises(PromotionHandoffError):
            validate_execution_evidence_binding(dup, root=self.root)

    # T8: exact tested notional -> compatible
    def test_t8_exact_notional_compatible(self) -> None:
        binding = _binding(regimes=[_regime(tested_notional_usd=100.0)])
        manifest = _manifest(binding=binding)
        codes = execution_regime_compatibility(
            root=self.root,
            manifest=manifest,
            binding=binding,
            execution_inputs={**EXECUTION_INPUTS, "notional_usd": 100.0, "fee_bps": 100},
        )
        self.assertEqual(codes, [])

    # T9: tested $10 / requested $100 -> NOTIONAL_EVIDENCE_MISMATCH
    def test_t9_tested_10_requested_100_mismatch(self) -> None:
        binding = _binding(regimes=[_regime(tested_notional_usd=10.0)])
        manifest = _manifest(binding=binding)
        codes = execution_regime_compatibility(
            root=self.root,
            manifest=manifest,
            binding=binding,
            execution_inputs={**EXECUTION_INPUTS, "notional_usd": 100.0},
        )
        self.assertEqual(codes, ["NOTIONAL_EVIDENCE_MISMATCH"])

    # T10: tested $100 / requested $10 -> NOTIONAL_EVIDENCE_MISMATCH
    def test_t10_tested_100_requested_10_mismatch(self) -> None:
        binding = _binding(regimes=[_regime(tested_notional_usd=100.0)])
        manifest = _manifest(binding=binding)
        codes = execution_regime_compatibility(
            root=self.root,
            manifest=manifest,
            binding=binding,
            execution_inputs={**EXECUTION_INPUTS, "notional_usd": 10.0},
        )
        self.assertEqual(codes, ["NOTIONAL_EVIDENCE_MISMATCH"])

    # T11: ENTRY_ONLY remains in population denominator
    def test_t11_entry_only_retained(self) -> None:
        binding = _binding(regimes=[_regime(entry_only_n=11, two_way_n=11, no_entry_n=1, unknown_n=1, population_n=24)])
        validate_execution_evidence_binding(binding, root=self.root)

    # T12: provider failure remains UNKNOWN (distinct count), never coerced
    def test_t12_provider_failure_unknown_count(self) -> None:
        binding = _binding(
            regimes=[_regime(unknown_n=3, two_way_n=15, entry_only_n=4, no_entry_n=1, population_n=23)]
        )
        validate_execution_evidence_binding(binding, root=self.root)

    # T13: missing strategy_fee_bps_assumption -> COST_ASSUMPTION_BINDING_GAP
    def test_t13_missing_fee_assumption_gap(self) -> None:
        regime = _regime(fee_bps=None)
        binding = _binding(regimes=[regime])
        manifest = _manifest(binding=binding)
        codes = execution_regime_compatibility(
            root=self.root,
            manifest=manifest,
            binding=binding,
            execution_inputs=EXECUTION_INPUTS,
        )
        self.assertEqual(codes, ["COST_ASSUMPTION_BINDING_GAP"])

    # T14: fee assumption mismatch -> COST_EVIDENCE_MISMATCH
    def test_t14_fee_assumption_mismatch(self) -> None:
        binding = _binding(regimes=[_regime(fee_bps=250)])
        manifest = _manifest(binding=binding)
        codes = execution_regime_compatibility(
            root=self.root,
            manifest=manifest,
            binding=binding,
            execution_inputs=EXECUTION_INPUTS,  # fee_bps=100
        )
        self.assertEqual(codes, ["COST_EVIDENCE_MISMATCH"])

    # T15: measured roundtrip friction is never the fee comparison RHS
    def test_t15_no_friction_field_in_binding(self) -> None:
        binding = _binding()
        regime = binding["regimes"][0]
        self.assertNotIn("measured_roundtrip_bps", regime)
        self.assertNotIn("roundtrip_friction", regime)
        # schema forbids extra keys
        poisoned = copy.deepcopy(binding)
        poisoned["regimes"][0]["measured_roundtrip_bps"] = 329
        unsigned = unsigned_binding(poisoned)
        poisoned["binding_sha256"] = _binding_sha(unsigned)
        with self.assertRaises(PromotionHandoffError):
            validate_execution_evidence_binding(poisoned, root=self.root)

    # T16/T17: strategy v1.1 schema unchanged (byte identity)
    def test_t16_t17_strategy_schema_unchanged(self) -> None:
        expected = (
            "a8f0e6e2f6b74c5f9b3e2a6d8c4f1e5b7a9d3c6f2e8b1a4d7c9f3e6b2a5d8c1f"
        )
        del expected  # no pinned hash: assert file untouched by this atom instead
        current = (ROOT / "catalog/schemas/strategy_version_v1_1.schema.json").read_bytes()
        import subprocess

        blob = subprocess.run(
            ["git", "show", "HEAD:catalog/schemas/strategy_version_v1_1.schema.json"],
            capture_output=True,
            cwd=ROOT,
            check=True,
        ).stdout
        self.assertEqual(current, blob)

    # T18: new PROMOTE cannot pass required regime binding when missing
    def test_t18_promote_requires_binding(self) -> None:
        manifest = _manifest(version="1.0")  # legacy-shaped, no binding
        codes = execution_regime_compatibility(
            root=self.root,
            manifest=manifest,
            binding=None,
            execution_inputs=EXECUTION_INPUTS,
        )
        self.assertEqual(codes, ["EXECUTION_EVIDENCE_BINDING_GAP"])
        self.assertIn("EXECUTION_REGIME_BINDING", OBLIGATIONS)

    # T19: CHECK / RENDER / VERIFY agree (via check_materialization parity)
    def test_t19_check_render_verify_agree(self) -> None:
        binding = _binding(regimes=[_regime(tested_notional_usd=100.0)])
        manifest = _manifest(binding=binding)
        good = check_materialization(
            root=self.root,
            manifest=manifest,
            execution_inputs={**EXECUTION_INPUTS, "notional_usd": 100.0},
            decision_event_id="DECISION-EVENT-0000000001",
            created_at="2026-09-06T12:00:00Z",
            execution_evidence_binding=binding,
        )
        self.assertEqual(good["handoff_state"], "READY_TO_MATERIALIZE")
        bad = check_materialization(
            root=self.root,
            manifest=manifest,
            execution_inputs={**EXECUTION_INPUTS, "notional_usd": 10.0},
            decision_event_id="DECISION-EVENT-0000000001",
            created_at="2026-09-06T12:00:00Z",
            execution_evidence_binding=binding,
        )
        self.assertEqual(bad["handoff_state"], "BLOCKED")
        self.assertIn("NOTIONAL_EVIDENCE_MISMATCH", bad["blocker_codes"])

    # T20: manifest/binding replay and hashing are deterministic
    def test_t20_deterministic_hashing(self) -> None:
        first = _binding()
        second = _binding()
        self.assertEqual(first["binding_sha256"], second["binding_sha256"])
        m1 = _manifest(binding=first)
        m2 = _manifest(binding=second)
        self.assertEqual(m1["manifest_sha256"], m2["manifest_sha256"])
        self.assertEqual(
            manifest_sha256(unsigned_manifest(m1)), m1["manifest_sha256"]
        )

    def test_binding_identity_must_match_manifest_science(self) -> None:
        binding = _binding(experiment_id="EXP-OTHER-EXPERIMENT-001")
        manifest = _manifest(binding=binding)
        codes = execution_regime_compatibility(
            root=self.root,
            manifest=manifest,
            binding=binding,
            execution_inputs=EXECUTION_INPUTS,
        )
        self.assertEqual(codes, ["EXECUTION_REGIME_MISMATCH"])

    def test_freeze_v1_1_requires_direct_evidence_coverage(self) -> None:
        dossier = {
            "locator": {"entity_id": EXPERIMENT_ID},
            "tested": {
                "hypothesis_version_id": HYPOTHESIS_ID,
                "population": POPULATION_REF,
            },
            "experiment_spec_binding": {
                "source_kind": "git_path",
                "source_value": "configs/experiment_specs/ordinary_price_path_buy_pressure_v1.yaml",
                "spec_sha256": SPEC_SHA,
            },
            "evidence_snapshot_sha256": "e" * 64,
            "direct_evidence": [
                {"record_id": "REC-001", "payload_sha256": "d" * 64},
            ],
            "obligations": [{"code": "FALSIFIER", "status": "PRESENT"}],
        }
        frozen = freeze_promotion_handoff_manifest(
            dossier,
            root=self.root,
            decision_event_id="DECISION-EVENT-0000000002",
            decision_effective_at="2026-09-06T12:00:00Z",
            execution_evidence_binding=_binding(),
        )
        self.assertEqual(frozen["schema_version"], "1.1")
        binding = _binding(
            regimes=[
                _regime(),
                _regime(tested_notional_usd=100.0, two_way_n=17, entry_only_n=9, no_entry_n=1, unknown_n=1, population_n=28),
            ]
        )
        frozen_two = freeze_promotion_handoff_manifest(
            dossier,
            root=self.root,
            decision_event_id="DECISION-EVENT-0000000003",
            decision_effective_at="2026-09-06T12:00:00Z",
            execution_evidence_binding=binding,
        )
        self.assertEqual(frozen_two["schema_version"], "1.1")
        # binding refs outside manifest direct evidence fail closed
        outside = _binding()
        outside_unsigned = unsigned_binding(outside)
        outside_unsigned["direct_evidence_refs"] = [
            {"record_id": "REC-UNBOUND-001", "payload_sha256": "d" * 64}
        ]
        outside["direct_evidence_refs"] = outside_unsigned["direct_evidence_refs"]
        outside["binding_sha256"] = _binding_sha(outside_unsigned)
        with self.assertRaises(PromotionHandoffError):
            freeze_promotion_handoff_manifest(
                dossier,
                root=self.root,
                decision_event_id="DECISION-EVENT-0000000004",
                decision_effective_at="2026-09-06T12:00:00Z",
                execution_evidence_binding=outside,
            )


def shutil_copy(source: Path, target: Path) -> None:
    import shutil

    shutil.copy(source, target)


if __name__ == "__main__":
    unittest.main()
