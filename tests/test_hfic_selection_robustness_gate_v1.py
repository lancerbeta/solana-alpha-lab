"""Synthetic proofs for the HFIC selection-robustness gate."""

from __future__ import annotations

import json
import os
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

from solana_alpha_lab.factory.capabilities import (
    CAPABILITY_ROUTER,
    CapabilityError,
    execute_capability,
)
from solana_alpha_lab.factory.hfic_censoring_ignorability_diagnostic import (
    CANONICAL_INPUT_MODE,
    FROZEN_SPEC_SHA256 as STAGE1_FROZEN_SPEC_SHA256,
    INCONCLUSIVE as STAGE1_INCONCLUSIVE,
    SCOPE_CANONICAL,
    SHIFT_DETECTED,
    SHIFT_NOT_DETECTED,
    bind_canonical_censoring_inputs,
    load_diagnostic_spec,
    run_censoring_ignorability_diagnostic,
)
from solana_alpha_lab.factory.early_market_panel_importer import (
    MIN_USABLE_YIELD_ELIGIBLE,
)
from solana_alpha_lab.factory.hfic_control_integrity import (
    CURRENT_REPRESENTATION_CONTROL_V1,
)
from solana_alpha_lab.factory.hfic_preflight import (
    assert_capability_registry_v2_superset,
    run_preflight,
)
from solana_alpha_lab.factory.hfic_selection_robustness_gate import (
    BLOCK_FORGE_EVIDENCE_GAP,
    BLOCK_FORGE_SELECTION_RISK,
    CAP_HFIC_SELECTION_ROBUSTNESS_GATE,
    FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
    FROZEN_SPEC_SHA256,
    GATE_ARTIFACT_RELATIVE,
    RECEIPT_SCHEMA,
    SELECTION_GATE_RECEIPT_INPUT_IDENTITY_MISMATCH,
    STAGE2_DETECTED,
    STAGE2_INCONCLUSIVE,
    STAGE2_NOT_DETECTED,
    STAGE2_SKIPPED,
    _fit_preprocessor,
    _load_block_a_typed,
    _transform_members,
    apply_selection_gate_to_preflight,
    load_applicable_gate_receipt,
    load_gate_spec,
    persist_gate_receipt,
    roc_auc,
    route_selection_gate,
    run_selection_robustness_gate,
    stratified_kfold,
)
from solana_alpha_lab.factory.live_cohort_discovery_release import CORPUS_DATASET_ID
from solana_alpha_lab.factory.run_passport import canonical_sha256
from tests.test_hfic_censoring_ignorability_diagnostic_v1 import (
    CENSUS_RELEASE_SCHEMA,
    FROZEN_COHORT,
    FROZEN_DATASET,
    FROZEN_RELEASE,
    HOLDERS,
    LAUNCHPAD,
    LIQUIDITY,
    MCAP,
    OBS_RELEASE_SCHEMA,
    PRICE,
    _balanced_fixture,
    _block_a_obs,
    _install_canonical_corpus,
    _member,
    _pins_from_installed,
    _write_parquet,
    _x300,
)
from tests.test_hfic_preflight import _CLOCK, _commission, _git_snapshot

CLI = ROOT / "scripts" / "hypothesis_forge.py"
STAGE1_SPEC = ROOT / "configs" / "hfic_censoring_ignorability_diagnostic_v1.yaml"
GATE_SPEC = ROOT / "configs" / "hfic_selection_robustness_gate_v1.yaml"
BLOCK_A = (
    "FIELD-LIQUIDITY-USD-001",
    "FIELD-MARKET-CAP-USD-001",
    "FIELD-USD-PRICE-001",
    "FIELD-HOLDER-COUNT-001",
    "FIELD-LAUNCHPAD-001",
)
LEAK_FIELDS = (
    "FIELD-STATS5M-TAKER-VOLUME-001",
    "FIELD-R0-TAKER-VOLUME-MIX-001",
    "FIELD-QUOTE-ASK-001",
    "FIELD-TOKEN-MINT-001",
    "FIELD-FIRST-SEEN-AT-001",
    "FIELD-FIRST-POOL-CREATED-AT-001",
)


def _mv_fixture(
    directory: Path,
    *,
    observed_n: int,
    censored_n: int,
    shift: float,
    include_y: bool = False,
    include_leaks: bool = False,
) -> tuple[Path, Path]:
    census: list[dict[str, object]] = []
    observations: list[dict[str, object]] = []
    for index in range(observed_n):
        mint = f"obs{index:03d}"
        census.append(_member(mint, candidate="X_ELIGIBLE", denom="observed", anchor="ANCHOR"))
        observations.extend(
            _block_a_obs(
                mint,
                liquidity=100.0 + (index % 17) * 6.0 + shift,
                mcap=200.0 + ((index * 3) % 13) * 6.0 - shift,
                price=0.01 + ((index * 5) % 9) * 0.002,
                holders=50.0 + ((index * 7) % 11) * 6.0 - shift,
                launchpad="pump" if index % 3 else "letsbonk",
            )
        )
        if include_y:
            observations.append(_x300(mint, LIQUIDITY, 10**12, point_id="Y900"))
        if include_leaks:
            observations.append(
                _x300(mint, "FIELD-STATS5M-TAKER-VOLUME-001", 999.0)
            )
            observations.append(
                _x300(mint, "FIELD-R0-TAKER-VOLUME-MIX-001", 0.8)
            )
    for index in range(censored_n):
        mint = f"cen{index:03d}"
        census.append(
            _member(mint, candidate="X_ELIGIBLE", denom="censored_late", anchor="ANCHOR")
        )
        observations.extend(
            _block_a_obs(
                mint,
                liquidity=100.0 + (index % 17) * 6.0,
                mcap=200.0 + ((index * 3) % 13) * 6.0,
                price=0.01 + ((index * 5) % 9) * 0.002,
                holders=50.0 + ((index * 7) % 11) * 6.0,
                launchpad="pump" if index % 3 else "letsbonk",
            )
        )
        if include_y:
            observations.append(_x300(mint, LIQUIDITY, 10**12, point_id="Y86400"))
        if include_leaks:
            observations.append(
                _x300(mint, "FIELD-STATS5M-TAKER-VOLUME-001", 1.0)
            )
    for index in range(5):
        census.append(_member(f"adm{index:03d}", candidate="ADMITTED", denom="censored_late"))
    for index in range(4):
        census.append(
            _member(f"inel{index:03d}", candidate="X_POPULATION_INELIGIBLE", denom="excluded")
        )
    census_path = directory / "census.parquet"
    observations_path = directory / "observations.parquet"
    _write_parquet(census_path, census, CENSUS_RELEASE_SCHEMA)
    _write_parquet(observations_path, observations, OBS_RELEASE_SCHEMA)
    return census_path, observations_path


def _tiny_fixture(directory: Path, observed_n: int = 4, censored_n: int = 4) -> tuple[Path, Path]:
    return _mv_fixture(directory, observed_n=observed_n, censored_n=censored_n, shift=0.0)


def _hashed_gate_receipt(decision: str, **fields: object) -> dict[str, object]:
    body: dict[str, object] = {"schema": RECEIPT_SCHEMA, "router_decision": decision}
    body.update(fields)
    receipt = dict(body)
    receipt["receipt_sha256"] = canonical_sha256(body)
    return receipt


def _identity_fields(installed: dict[str, str], **overrides: str) -> dict[str, str]:
    fields = {
        "corpus_id": FROZEN_DATASET,
        "cohort_id": FROZEN_COHORT,
        "release_id": FROZEN_RELEASE,
        "census_sha256": installed["census_sha256"],
        "observations_sha256": installed["observations_sha256"],
        "dataset_manifest_id": installed["dataset_manifest_id"],
        "spec_file_sha256": FROZEN_SPEC_SHA256,
    }
    fields.update(overrides)
    return fields


def _bind_installed(installed: dict[str, str]):
    pins = _pins_from_installed(installed)
    real = bind_canonical_censoring_inputs

    def _bind(data_root: Path, _corpus: object):
        return real(data_root, pins)

    return patch(
        "solana_alpha_lab.factory.hfic_selection_robustness_gate.bind_canonical_censoring_inputs",
        side_effect=_bind,
    )


def _load_gate(data_root: Path) -> dict[str, object] | None:
    return load_applicable_gate_receipt(data_root, root=ROOT)


def _control_corpus(yield_eligible: int) -> dict[str, object]:
    return {
        "dataset_id": CORPUS_DATASET_ID,
        "dataset_manifest_id": "dataset-" + "a" * 64,
        "dataset_fingerprint": "bb" * 32,
        "evidence_role": "UNSPECIFIED",
        "yield_eligible": yield_eligible,
        "base_x_population_n": yield_eligible,
        "yield_missing": 0,
        "feature_usable": yield_eligible >= MIN_USABLE_YIELD_ELIGIBLE,
        "labels": {
            "yield_eligible": yield_eligible,
            "base_x_population_n": yield_eligible,
            "logical_dataset_id": CORPUS_DATASET_ID,
        },
    }


class SelectionRobustnessGateTests(unittest.TestCase):
    def test_stage1_frozen_spec_bytes_and_block_a_match(self) -> None:
        self.assertEqual(
            STAGE1_FROZEN_SPEC_SHA256,
            "47668ad5a7316b4bdb1a78be0bbc9bd1caed24ba597f10c6cf966dfaa05d556c",
        )
        self.assertEqual(STAGE1_SPEC.read_bytes().hex()[:8], "73636865")
        gate = load_gate_spec(ROOT)
        stage1 = load_diagnostic_spec(ROOT)
        self.assertEqual(
            [item["field_id"] for item in gate["block_a_omnibus"]],
            [item["field_id"] for item in stage1["block_a_omnibus"]],
        )
        self.assertEqual(tuple(item["field_id"] for item in gate["block_a_omnibus"]), BLOCK_A)
        self.assertEqual(float(gate["oof_auc_threshold"]), 0.57)
        self.assertEqual(float(gate["permutation_p_threshold"]), 0.05)
        self.assertEqual(float(gate["l2_lambda"]), 1.0)
        self.assertEqual(int(gate["permutation_count"]), 999)
        self.assertEqual(int(gate["cv_folds"]), 5)
        self.assertEqual(str(gate["cv_seed"]), "A17C9E02")
        import hashlib

        self.assertEqual(hashlib.sha256(GATE_SPEC.read_bytes()).hexdigest(), FROZEN_SPEC_SHA256)

    def test_router_mapping(self) -> None:
        self.assertEqual(
            route_selection_gate(SHIFT_DETECTED)["router_decision"],
            BLOCK_FORGE_SELECTION_RISK,
        )
        self.assertEqual(
            route_selection_gate(STAGE1_INCONCLUSIVE)["router_decision"],
            BLOCK_FORGE_EVIDENCE_GAP,
        )
        self.assertEqual(
            route_selection_gate("NOT_A_TERMINAL")["router_decision"],
            BLOCK_FORGE_EVIDENCE_GAP,
        )
        self.assertEqual(route_selection_gate(SHIFT_DETECTED)["stage2_status"], STAGE2_SKIPPED)
        self.assertEqual(
            route_selection_gate(
                SHIFT_NOT_DETECTED,
                stage2_terminal=STAGE2_DETECTED,
                stage2_status="RAN",
            )["router_decision"],
            BLOCK_FORGE_SELECTION_RISK,
        )
        self.assertEqual(
            route_selection_gate(
                SHIFT_NOT_DETECTED,
                stage2_terminal=STAGE2_INCONCLUSIVE,
                stage2_status="RAN",
            )["router_decision"],
            BLOCK_FORGE_EVIDENCE_GAP,
        )
        self.assertEqual(
            route_selection_gate(
                SHIFT_NOT_DETECTED,
                stage2_terminal=STAGE2_NOT_DETECTED,
                stage2_status="RAN",
            )["router_decision"],
            FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
        )

    def test_stage1_detected_skips_stage2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=True)
            with patch(
                "solana_alpha_lab.factory.hfic_selection_robustness_gate._run_stage2"
            ) as stage2:
                receipt = run_selection_robustness_gate(
                    root=ROOT,
                    census_path=census,
                    observations_path=observations,
                    persist=False,
                )
            stage2.assert_not_called()
            self.assertEqual(receipt["stage1_terminal"], SHIFT_DETECTED)
            self.assertEqual(receipt["stage2_status"], STAGE2_SKIPPED)
            self.assertIsNone(receipt["oof_roc_auc"])
            self.assertEqual(receipt["router_decision"], BLOCK_FORGE_SELECTION_RISK)
            self.assertEqual(receipt["provider_requests"], 0)
            self.assertEqual(receipt["credential_reads"], 0)

    def test_stage1_inconclusive_skips_stage2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(
                Path(tmp), shift_liquidity=False, holder_coverage=False
            )
            with patch(
                "solana_alpha_lab.factory.hfic_selection_robustness_gate._run_stage2"
            ) as stage2:
                receipt = run_selection_robustness_gate(
                    root=ROOT,
                    census_path=census,
                    observations_path=observations,
                    persist=False,
                )
            stage2.assert_not_called()
            self.assertEqual(receipt["stage1_terminal"], STAGE1_INCONCLUSIVE)
            self.assertEqual(receipt["stage2_status"], STAGE2_SKIPPED)
            self.assertEqual(receipt["router_decision"], BLOCK_FORGE_EVIDENCE_GAP)

    def test_stage1_not_detected_enters_stage2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            with patch(
                "solana_alpha_lab.factory.hfic_selection_robustness_gate._run_stage2",
                return_value={
                    "terminal": STAGE2_NOT_DETECTED,
                    "inconclusive_reasons": [],
                    "oof_roc_auc": 0.51,
                    "permutation_hits": 400,
                    "permutation_p": 0.401,
                    "oof_prediction_sha256": "a" * 64,
                },
            ) as stage2:
                receipt = run_selection_robustness_gate(
                    root=ROOT,
                    census_path=census,
                    observations_path=observations,
                    persist=False,
                )
            stage2.assert_called_once()
            self.assertEqual(receipt["stage1_terminal"], SHIFT_NOT_DETECTED)
            self.assertEqual(receipt["stage2_status"], "RAN")
            self.assertEqual(receipt["stage2_terminal"], STAGE2_NOT_DETECTED)
            self.assertEqual(
                receipt["router_decision"], FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT
            )

    def test_feature_universe_and_leakage_denied(self) -> None:
        gate = load_gate_spec(ROOT)
        field_ids = [str(item["field_id"]) for item in gate["block_a_omnibus"]]
        self.assertEqual(field_ids, list(BLOCK_A))
        excluded = set(gate["excluded_fields"])
        for leaked in LEAK_FIELDS:
            self.assertNotIn(leaked, field_ids)
            self.assertTrue(
                leaked in excluded
                or leaked.startswith("FIELD-STATS5M-")
                or leaked.startswith("FIELD-R0-")
                or leaked.startswith("FIELD-QUOTE-")
            )
        self.assertIn("FIELD-STATS5M-TAKER-VOLUME-001", set(gate["excluded_fields"]))
        self.assertIn("FIELD-TOKEN-MINT-001", set(gate["excluded_fields"]))
        seen: list[tuple[str, ...]] = []
        real = _load_block_a_typed

        def _wrapped(path, *, allowed_point_id, y_prefix, field_ids):
            seen.append(tuple(field_ids))
            for field_id in field_ids:
                self.assertNotIn(field_id, LEAK_FIELDS)
                self.assertFalse(field_id.startswith("Y"))
                self.assertFalse(field_id.startswith("FIELD-STATS5M-"))
                self.assertFalse(field_id.startswith("FIELD-QUOTE-"))
            return real(
                path,
                allowed_point_id=allowed_point_id,
                y_prefix=y_prefix,
                field_ids=field_ids,
            )

        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _mv_fixture(
                Path(tmp),
                observed_n=24,
                censored_n=24,
                shift=0.0,
                include_y=True,
                include_leaks=True,
            )
            with patch(
                "solana_alpha_lab.factory.hfic_selection_robustness_gate._load_block_a_typed",
                side_effect=_wrapped,
            ):
                with patch(
                    "solana_alpha_lab.factory.hfic_selection_robustness_gate._run_stage2",
                    return_value={
                        "terminal": STAGE2_NOT_DETECTED,
                        "inconclusive_reasons": [],
                        "oof_roc_auc": 0.5,
                        "permutation_hits": 500,
                        "permutation_p": 0.5,
                        "oof_prediction_sha256": "b" * 64,
                    },
                ):
                    receipt = run_selection_robustness_gate(
                        root=ROOT,
                        census_path=census,
                        observations_path=observations,
                        persist=False,
                    )
        self.assertTrue(seen)
        self.assertEqual(receipt["y_point_rows_present_unread"] > 0, True)
        self.assertEqual(set(seen[-1]), set(BLOCK_A))

    def test_fold_local_preprocessing_and_unseen_other(self) -> None:
        spec = load_gate_spec(ROOT)
        train = []
        for index in range(20):
            train.append(
                {
                    "group": "observed" if index < 10 else "censored_late",
                    "features": {
                        "log1p_liquidity_usd": 2.0 if index < 10 else 2.2,
                        "log1p_market_cap_usd": 3.0,
                        "log1p_usd_price": 0.1,
                        "log1p_holder_count": 4.0,
                        "launchpad": "pump" if index != 19 else "rarepad",
                    },
                    "observed_flags": {
                        "log1p_liquidity_usd": True,
                        "log1p_market_cap_usd": True,
                        "log1p_usd_price": True,
                        "log1p_holder_count": True,
                        "launchpad": True,
                    },
                }
            )
        test = [
            {
                "group": "observed",
                "features": {},
                "observed_flags": {
                    "log1p_liquidity_usd": False,
                    "log1p_market_cap_usd": True,
                    "log1p_usd_price": True,
                    "log1p_holder_count": True,
                    "launchpad": True,
                },
            }
        ]
        test[0]["features"] = {
            "log1p_market_cap_usd": 3.0,
            "log1p_usd_price": 0.1,
            "log1p_holder_count": 4.0,
            "launchpad": "unseen_pad",
        }
        preprocessor = _fit_preprocessor(train, spec)
        self.assertIsNotNone(preprocessor)
        assert preprocessor is not None
        train_median = preprocessor["continuous"]["log1p_liquidity_usd"]["median"]
        leaked = _fit_preprocessor(train + test, spec)
        assert leaked is not None
        rows = _transform_members(test, spec, preprocessor)
        self.assertEqual(rows[0][1], 1.0)
        imputed = rows[0][2]
        mean = preprocessor["continuous"]["log1p_liquidity_usd"]["mean"]
        std = preprocessor["continuous"]["log1p_liquidity_usd"]["std"]
        self.assertAlmostEqual(imputed, (train_median - mean) / std)
        dummy_levels = preprocessor["dummy_levels"]["launchpad"]
        for level in dummy_levels:
            self.assertNotEqual(level, "unseen_pad")

    def test_stratified_folds_deterministic(self) -> None:
        import random

        labels = [1] * 12 + [0] * 12
        left = stratified_kfold(labels, folds=5, rng=random.Random(0xA17C9E02))
        right = stratified_kfold(labels, folds=5, rng=random.Random(0xA17C9E02))
        self.assertEqual(left, right)
        self.assertIsNotNone(left)
        assert left is not None
        self.assertEqual(len(left), 5)
        for fold in left:
            present = {labels[index] for index in fold}
            self.assertEqual(present, {0, 1})

    def test_auc_and_thresholds_are_exact_floors(self) -> None:
        self.assertAlmostEqual(roc_auc([1, 1, 0, 0], [0.9, 0.8, 0.2, 0.1]) or 0.0, 1.0)
        spec = load_gate_spec(ROOT)
        self.assertEqual(spec["oof_auc_threshold"], 0.57)
        self.assertEqual(spec["permutation_p_threshold"], 0.05)
        self.assertEqual(spec["l2_lambda"], 1.0)

    def test_synthetic_clear_multivariate_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _mv_fixture(
                Path(tmp), observed_n=48, censored_n=48, shift=9.0
            )
            stage1 = run_censoring_ignorability_diagnostic(
                root=ROOT,
                census_path=census,
                observations_path=observations,
            )
            self.assertEqual(stage1["scientific_terminal"], SHIFT_NOT_DETECTED)
            receipt = run_selection_robustness_gate(
                root=ROOT,
                census_path=census,
                observations_path=observations,
                persist=False,
            )
        self.assertEqual(receipt["stage2_terminal"], STAGE2_DETECTED)
        self.assertGreaterEqual(float(receipt["oof_roc_auc"]), 0.57)
        self.assertLessEqual(float(receipt["permutation_p"]), 0.05)
        self.assertEqual(receipt["router_decision"], BLOCK_FORGE_SELECTION_RISK)
        self.assertIn("NO_MNAR", receipt["non_claims"])
        self.assertIn("NO_MAR", receipt["non_claims"])

    def test_synthetic_no_separation_not_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _mv_fixture(
                Path(tmp), observed_n=36, censored_n=36, shift=0.0
            )
            receipt = run_selection_robustness_gate(
                root=ROOT,
                census_path=census,
                observations_path=observations,
                persist=False,
            )
        self.assertEqual(receipt["stage1_terminal"], SHIFT_NOT_DETECTED)
        self.assertEqual(receipt["stage2_terminal"], STAGE2_NOT_DETECTED)
        self.assertEqual(
            receipt["router_decision"], FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT
        )
        self.assertLess(float(receipt["oof_roc_auc"]), 0.57)

    def test_integrity_break_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _tiny_fixture(Path(tmp))
            receipt = run_selection_robustness_gate(
                root=ROOT,
                census_path=census,
                observations_path=observations,
                persist=False,
            )
        self.assertEqual(receipt["stage1_terminal"], SHIFT_NOT_DETECTED)
        self.assertEqual(receipt["stage2_terminal"], STAGE2_INCONCLUSIVE)
        self.assertEqual(receipt["router_decision"], BLOCK_FORGE_EVIDENCE_GAP)
        self.assertIn("STRATIFIED_FOLDS_INFEASIBLE", receipt["inconclusive_reasons"])

    def test_seed_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _mv_fixture(
                Path(tmp), observed_n=24, censored_n=24, shift=0.0
            )
            first = run_selection_robustness_gate(
                root=ROOT,
                census_path=census,
                observations_path=observations,
                persist=False,
            )
            second = run_selection_robustness_gate(
                root=ROOT,
                census_path=census,
                observations_path=observations,
                persist=False,
            )
        self.assertEqual(first["oof_roc_auc"], second["oof_roc_auc"])
        self.assertEqual(first["permutation_p"], second["permutation_p"])
        self.assertEqual(first["permutation_hits"], second["permutation_hits"])
        self.assertEqual(first["oof_prediction_sha256"], second["oof_prediction_sha256"])

    def test_forge_preflight_consumption_and_resume_preserved(self) -> None:
        block = {
            "router_decision": BLOCK_FORGE_SELECTION_RISK,
            "receipt_sha256": "c" * 64,
        }
        gap = {
            "router_decision": BLOCK_FORGE_EVIDENCE_GAP,
            "receipt_sha256": "d" * 64,
        }
        caveat = {
            "router_decision": FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
            "receipt_sha256": "e" * 64,
        }
        self.assertEqual(
            apply_selection_gate_to_preflight("START_NEW_SESSION", None)["action"],
            "START_NEW_SESSION",
        )
        blocked = apply_selection_gate_to_preflight("START_NEW_SESSION", block)
        self.assertEqual(blocked["action"], "START_NEW_SESSION")
        self.assertTrue(blocked.get("caveat"))
        self.assertEqual(blocked["router_decision"], BLOCK_FORGE_SELECTION_RISK)
        self.assertIsNone(blocked.get("terminal"))
        gap_view = apply_selection_gate_to_preflight("START_NEW_SESSION", gap)
        self.assertEqual(gap_view["action"], "START_NEW_SESSION")
        self.assertTrue(gap_view.get("caveat"))
        self.assertEqual(gap_view["router_decision"], BLOCK_FORGE_EVIDENCE_GAP)
        self.assertIsNone(gap_view.get("terminal"))
        eligible = apply_selection_gate_to_preflight("START_NEW_SESSION", caveat)
        self.assertEqual(eligible["action"], "START_NEW_SESSION")
        self.assertTrue(eligible.get("caveat"))
        self.assertEqual(
            apply_selection_gate_to_preflight("RETURN_EXISTING_SESSION", block)["action"],
            "RETURN_EXISTING_SESSION",
        )
        self.assertEqual(
            apply_selection_gate_to_preflight("RESUME_CRITIC", gap)["action"],
            "RESUME_CRITIC",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = persist_gate_receipt(
                Path(tmp),
                {
                    "schema": "smial.hfic-selection-robustness-gate-receipt",
                    "router_decision": FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
                },
            )
            self.assertTrue(path.is_file())
            loaded = _load_gate(Path(tmp))
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertTrue(loaded.get("integrity_invalid"))
            self.assertEqual(loaded["router_decision"], BLOCK_FORGE_EVIDENCE_GAP)
            self.assertEqual(
                apply_selection_gate_to_preflight("START_NEW_SESSION", loaded)["action"],
                "STOP",
            )
        self.assertIsNone(_load_gate(Path(tempfile.gettempdir()) / "missing-gate-root"))
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / GATE_ARTIFACT_RELATIVE
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_bytes(b"\xff\xfe\x00not-utf8")
            loaded = _load_gate(Path(tmp))
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertTrue(loaded.get("integrity_invalid"))
            self.assertEqual(loaded["router_decision"], BLOCK_FORGE_EVIDENCE_GAP)
        with tempfile.TemporaryDirectory() as tmp:
            occupied = Path(tmp) / GATE_ARTIFACT_RELATIVE
            occupied.parent.mkdir(parents=True, exist_ok=True)
            occupied.mkdir()
            loaded = _load_gate(Path(tmp))
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertTrue(loaded.get("integrity_invalid"))
            self.assertEqual(loaded["router_decision"], BLOCK_FORGE_EVIDENCE_GAP)
            self.assertEqual(
                apply_selection_gate_to_preflight("START_NEW_SESSION", loaded)["action"],
                "STOP",
            )
        preflight_src = (
            ROOT / "src/solana_alpha_lab/factory/hfic_preflight.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "if control_mode != CURRENT_REPRESENTATION_CONTROL_V1:",
            preflight_src,
        )
        self.assertIn("DO_NOT_START_FORGE_UNTIL_SELECTION_GATE_ALLOWS", preflight_src)
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            with patch(
                "solana_alpha_lab.factory.hfic_selection_robustness_gate._run_stage2",
                return_value={
                    "terminal": STAGE2_NOT_DETECTED,
                    "inconclusive_reasons": [],
                    "oof_roc_auc": 0.51,
                    "permutation_hits": 400,
                    "permutation_p": 0.401,
                    "oof_prediction_sha256": "a" * 64,
                },
            ):
                receipt = run_selection_robustness_gate(
                    root=ROOT,
                    census_path=census,
                    observations_path=observations,
                    persist=False,
                )
            persist_gate_receipt(Path(tmp), receipt)
            loaded = _load_gate(Path(tmp))
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertTrue(loaded.get("integrity_invalid"))
            self.assertEqual(loaded["router_decision"], BLOCK_FORGE_EVIDENCE_GAP)
            self.assertEqual(
                loaded.get("integrity_reason"),
                SELECTION_GATE_RECEIPT_INPUT_IDENTITY_MISMATCH,
            )
            self.assertIsNone(receipt.get("dataset_manifest_id"))

    def test_dangling_symlink_latest_json_is_evidence_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dangling = Path(tmp) / GATE_ARTIFACT_RELATIVE
            dangling.parent.mkdir(parents=True, exist_ok=True)
            missing = Path(tmp) / "missing-target.json"
            try:
                os.symlink(missing, dangling)
            except (OSError, NotImplementedError):
                self.skipTest("symlink unavailable")
            loaded = _load_gate(Path(tmp))
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertTrue(loaded.get("integrity_invalid"))
            self.assertEqual(loaded["router_decision"], BLOCK_FORGE_EVIDENCE_GAP)

    def test_run_preflight_consumes_gate_without_rewriting_budget_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            _commission(data_root)
            missing = run_preflight(
                ROOT,
                data_root,
                owner_focus="AUTO",
                auto_commission=False,
                git_snapshot=_git_snapshot(),
                clock=_CLOCK,
            )
            self.assertEqual(missing["action"], "STOP")
            self.assertEqual(missing["terminal"], "MARKET_EVIDENCE_BASIS_INCOMPLETE")
            self.assertIsNone(missing.get("router_decision"))
            self.assertEqual(missing.get("next"), "RESTORE_CURRENT_EVIDENCE")
            self.assertNotEqual(
                missing.get("next"),
                "DO_NOT_START_FORGE_UNTIL_SELECTION_GATE_ALLOWS",
            )
            self.assertNotEqual(
                (missing.get("selection_gate") or {}).get("applicable"),
                True,
            )

            artifact = data_root / GATE_ARTIFACT_RELATIVE
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.mkdir()
            directory = run_preflight(
                ROOT,
                data_root,
                owner_focus="AUTO",
                auto_commission=False,
                git_snapshot=_git_snapshot(),
                clock=_CLOCK,
            )
            self.assertEqual(directory["action"], "STOP")
            self.assertEqual(directory["terminal"], "MARKET_EVIDENCE_BASIS_INCOMPLETE")
            self.assertIsNone(directory.get("router_decision"))
            self.assertEqual(
                directory["next"],
                "RESTORE_CURRENT_EVIDENCE",
            )
            artifact.rmdir()

            persist_gate_receipt(
                data_root, _hashed_gate_receipt(BLOCK_FORGE_SELECTION_RISK)
            )
            stale_block = run_preflight(
                ROOT,
                data_root,
                owner_focus="AUTO",
                auto_commission=False,
                git_snapshot=_git_snapshot(),
                clock=_CLOCK,
            )
            self.assertEqual(stale_block["action"], "STOP")
            self.assertEqual(stale_block["terminal"], "MARKET_EVIDENCE_BASIS_INCOMPLETE")
            self.assertIsNone(stale_block.get("router_decision"))
            self.assertEqual(
                stale_block["next"],
                "RESTORE_CURRENT_EVIDENCE",
            )
            artifact.unlink()

            persist_gate_receipt(
                data_root,
                _hashed_gate_receipt(FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT),
            )
            stale_allow = run_preflight(
                ROOT,
                data_root,
                owner_focus="AUTO",
                auto_commission=False,
                git_snapshot=_git_snapshot(),
                clock=_CLOCK,
            )
            self.assertEqual(stale_allow["action"], "STOP")
            self.assertEqual(stale_allow["terminal"], "MARKET_EVIDENCE_BASIS_INCOMPLETE")
            self.assertNotEqual(
                stale_allow.get("router_decision"),
                FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
            )
            artifact.unlink()

            installed = _install_canonical_corpus(data_root)
            matching_block = _hashed_gate_receipt(
                BLOCK_FORGE_SELECTION_RISK,
                **_identity_fields(installed),
            )
            persist_gate_receipt(data_root, matching_block)
            with _bind_installed(installed):
                blocked = run_preflight(
                    ROOT,
                    data_root,
                    owner_focus="AUTO",
                    auto_commission=False,
                    git_snapshot=_git_snapshot(),
                    clock=_CLOCK,
                )
            self.assertEqual(blocked["action"], "START_NEW_SESSION")
            self.assertEqual(blocked["router_decision"], BLOCK_FORGE_SELECTION_RISK)
            self.assertTrue((blocked.get("forge_context_packet") or {}).get(
                "selection_robustness_caveat"
            ))
            self.assertEqual(
                blocked.get("owner_next"),
                "CONTINUE_WITH_SCOPED_SELECTION_CAVEAT",
            )
            self.assertEqual(
                (blocked.get("selection_gate") or {}).get("owner_next"),
                "CONTINUE_WITH_SCOPED_SELECTION_CAVEAT",
            )
            self.assertNotEqual(
                blocked.get("next"),
                "DO_NOT_START_FORGE_UNTIL_SELECTION_GATE_ALLOWS",
            )
            artifact.unlink()

            persist_gate_receipt(
                data_root,
                _hashed_gate_receipt(
                    FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
                    **_identity_fields(installed),
                ),
            )
            with _bind_installed(installed):
                caveat = run_preflight(
                    ROOT,
                    data_root,
                    owner_focus="AUTO",
                    auto_commission=False,
                    git_snapshot=_git_snapshot(),
                    clock=_CLOCK,
                )
            self.assertEqual(caveat["action"], "START_NEW_SESSION")
            self.assertEqual(
                caveat["router_decision"],
                FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
            )
            artifact.unlink()

            with patch(
                "solana_alpha_lab.factory.hfic_preflight.decide_preflight_action",
                return_value=("STOP", "SEARCH_BUDGET_EXHAUSTED"),
            ):
                budget = run_preflight(
                    ROOT,
                    data_root,
                    owner_focus="AUTO",
                    auto_commission=False,
                    git_snapshot=_git_snapshot(),
                    clock=_CLOCK,
                )
            self.assertEqual(budget["action"], "STOP")
            self.assertEqual(budget["terminal"], "SEARCH_BUDGET_EXHAUSTED")
            self.assertIsNone(budget.get("router_decision"))
            self.assertNotEqual(
                budget.get("next"),
                "DO_NOT_START_FORGE_UNTIL_SELECTION_GATE_ALLOWS",
            )
            self.assertNotEqual(
                (budget.get("selection_gate") or {}).get("applicable"),
                True,
            )

            persist_gate_receipt(
                data_root,
                _hashed_gate_receipt(
                    BLOCK_FORGE_SELECTION_RISK,
                    **_identity_fields(installed),
                ),
            )
            with _bind_installed(installed), patch(
                "solana_alpha_lab.factory.hfic_preflight.enumerate_rdp_datasets",
                return_value=([_control_corpus(MIN_USABLE_YIELD_ELIGIBLE)], []),
            ):
                control = run_preflight(
                    ROOT,
                    data_root,
                    owner_focus="AUTO",
                    auto_commission=False,
                    git_snapshot=_git_snapshot(),
                    clock=_CLOCK,
                    evidence_surface_mode=CURRENT_REPRESENTATION_CONTROL_V1,
                )
            self.assertEqual(control["action"], "STOP")
            self.assertEqual(control["terminal"], "MARKET_EVIDENCE_BASIS_INCOMPLETE")
            self.assertEqual(control["next"], "RESTORE_CURRENT_EVIDENCE")
            self.assertIsNone(control.get("router_decision"))
            self.assertEqual(
                (control.get("forge_input_receipt") or {}).get("owner_class"),
                "OBSERVABILITY_BLOCKED",
            )

    def test_prior_hfic_sessions_remain_in_scientific_context(self) -> None:
        spec = load_gate_spec(ROOT)
        self.assertEqual(
            spec["canonical_corpus"]["scientific_context_session"],
            "HFIC-SESS-560C4E1A72B4F9E6",
        )
        gate_source = (
            ROOT / "src/solana_alpha_lab/factory/hfic_selection_robustness_gate.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("quarantine", gate_source.lower())
        self.assertNotIn("HFIC-SESS-60FB3DA7C8EB33FC", gate_source)
        budget_guard = ROOT / "docs/evidence/hfic_search_budget_epoch_guard/a1_active_rdp_preview_v1.json"
        self.assertIn("HFIC-SESS-60FB3DA7C8EB33FC", budget_guard.read_text(encoding="utf-8"))

    def test_capability_router_budget_and_cli(self) -> None:
        self.assertIn(CAP_HFIC_SELECTION_ROBUSTNESS_GATE, CAPABILITY_ROUTER)
        proof = assert_capability_registry_v2_superset(ROOT)
        self.assertIn(CAP_HFIC_SELECTION_ROBUSTNESS_GATE, proof["intentional_v2_additions"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(CapabilityError) as raised:
                execute_capability(
                    {
                        "capabilities": [CAP_HFIC_SELECTION_ROBUSTNESS_GATE],
                        "evidence_budget": {"provider_api_rpc_wss_calls": 1},
                        "parameters": {},
                    },
                    root=root,
                )
            self.assertEqual(str(raised.exception), "PROVIDER_BUDGET_NOT_ZERO")
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=True)
            env = dict(os.environ)
            env["SMIAL_DATA_ROOT"] = str(Path(tmp) / "unused")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(CLI),
                    "--root",
                    str(ROOT),
                    "selection-robustness-gate",
                    "--census",
                    str(census),
                    "--observations",
                    str(observations),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertIn(payload["router_decision"], {
                FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
                BLOCK_FORGE_SELECTION_RISK,
                BLOCK_FORGE_EVIDENCE_GAP,
            })
            self.assertNotIn("C:\\\\", completed.stdout.replace("/", "\\\\"))

    def test_stage1_behavior_on_balanced_fixture_still_not_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            receipt = run_censoring_ignorability_diagnostic(
                root=ROOT,
                census_path=census,
                observations_path=observations,
            )
        self.assertEqual(receipt["scientific_terminal"], SHIFT_NOT_DETECTED)
        self.assertEqual(receipt["provider_requests"], 0)


class SelectionGateReceiptIdentityTests(unittest.TestCase):
    def test_matching_canonical_receipt_is_applicable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            installed = _install_canonical_corpus(data_root)
            receipt = _hashed_gate_receipt(
                FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
                git_head="deadbeef" * 5,
                **_identity_fields(installed),
            )
            persist_gate_receipt(data_root, receipt)
            with _bind_installed(installed):
                loaded = _load_gate(data_root)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertFalse(loaded.get("integrity_invalid"))
            self.assertEqual(loaded["receipt_sha256"], receipt["receipt_sha256"])
            self.assertEqual(
                loaded["router_decision"], FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT
            )
            self.assertEqual(
                loaded["dataset_manifest_id"], installed["dataset_manifest_id"]
            )

    def test_current_corpus_head_change_does_not_invalidate_historical_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            installed = _install_canonical_corpus(data_root)
            stale = "dataset-" + "b" * 64
            self.assertNotEqual(stale, installed["dataset_manifest_id"])
            persist_gate_receipt(
                data_root,
                _hashed_gate_receipt(
                    FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
                    **_identity_fields(installed, dataset_manifest_id=stale),
                ),
            )
            with _bind_installed(installed):
                loaded = _load_gate(data_root)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertFalse(loaded.get("integrity_invalid"))
            self.assertEqual(
                loaded["router_decision"], FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT
            )
            self.assertEqual(loaded["dataset_manifest_id"], stale)

    def test_mismatched_cohort_or_release_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            installed = _install_canonical_corpus(data_root)
            persist_gate_receipt(
                data_root,
                _hashed_gate_receipt(
                    BLOCK_FORGE_SELECTION_RISK,
                    **_identity_fields(installed, cohort_id="REL-OTHER"),
                ),
            )
            with _bind_installed(installed):
                cohort = _load_gate(data_root)
            assert cohort is not None
            self.assertEqual(
                cohort.get("integrity_reason"),
                SELECTION_GATE_RECEIPT_INPUT_IDENTITY_MISMATCH,
            )
            persist_gate_receipt(
                data_root,
                _hashed_gate_receipt(
                    BLOCK_FORGE_SELECTION_RISK,
                    **_identity_fields(installed, release_id="ff" * 32),
                ),
            )
            with _bind_installed(installed):
                release = _load_gate(data_root)
            assert release is not None
            self.assertEqual(
                release.get("integrity_reason"),
                SELECTION_GATE_RECEIPT_INPUT_IDENTITY_MISMATCH,
            )

    def test_mismatched_census_or_observations_sha_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            installed = _install_canonical_corpus(data_root)
            persist_gate_receipt(
                data_root,
                _hashed_gate_receipt(
                    FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
                    **_identity_fields(installed, census_sha256="aa" * 32),
                ),
            )
            with _bind_installed(installed):
                census = _load_gate(data_root)
            assert census is not None
            self.assertEqual(
                census.get("integrity_reason"),
                SELECTION_GATE_RECEIPT_INPUT_IDENTITY_MISMATCH,
            )
            persist_gate_receipt(
                data_root,
                _hashed_gate_receipt(
                    FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
                    **_identity_fields(installed, observations_sha256="bb" * 32),
                ),
            )
            with _bind_installed(installed):
                observations = _load_gate(data_root)
            assert observations is not None
            self.assertEqual(
                observations.get("integrity_reason"),
                SELECTION_GATE_RECEIPT_INPUT_IDENTITY_MISMATCH,
            )

    def test_missing_canonical_identity_fields_are_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            installed = _install_canonical_corpus(data_root)
            persist_gate_receipt(
                data_root, _hashed_gate_receipt(FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT)
            )
            with _bind_installed(installed):
                loaded = _load_gate(data_root)
            assert loaded is not None
            self.assertTrue(loaded.get("integrity_invalid"))
            self.assertEqual(loaded["router_decision"], BLOCK_FORGE_EVIDENCE_GAP)
            self.assertEqual(
                loaded.get("integrity_reason"),
                SELECTION_GATE_RECEIPT_INPUT_IDENTITY_MISMATCH,
            )

    def test_old_valid_hash_cannot_allow_after_corpus_identity_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            installed = _install_canonical_corpus(data_root)
            persist_gate_receipt(
                data_root,
                _hashed_gate_receipt(
                    FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
                    **_identity_fields(
                        installed,
                        dataset_manifest_id="dataset-" + "c" * 64,
                    ),
                ),
            )
            with _bind_installed(installed):
                loaded = _load_gate(data_root)
                view = apply_selection_gate_to_preflight("START_NEW_SESSION", loaded)
            self.assertEqual(view["action"], "START_NEW_SESSION")
            self.assertTrue(view.get("caveat"))
            self.assertEqual(
                view.get("router_decision"), FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT
            )
            self.assertFalse(loaded.get("integrity_invalid") if loaded else True)
            self.assertTrue((data_root / GATE_ARTIFACT_RELATIVE).is_file())

    def test_old_valid_hash_block_is_not_current_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            installed = _install_canonical_corpus(data_root)
            persist_gate_receipt(
                data_root,
                _hashed_gate_receipt(
                    BLOCK_FORGE_SELECTION_RISK,
                    **_identity_fields(installed, release_id="00" * 32),
                ),
            )
            with _bind_installed(installed):
                loaded = _load_gate(data_root)
                view = apply_selection_gate_to_preflight("START_NEW_SESSION", loaded)
            self.assertEqual(view["terminal"], BLOCK_FORGE_EVIDENCE_GAP)
            self.assertNotEqual(view.get("terminal"), BLOCK_FORGE_SELECTION_RISK)

    def test_matching_receipt_keeps_block_and_caveat_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            installed = _install_canonical_corpus(data_root)
            persist_gate_receipt(
                data_root,
                _hashed_gate_receipt(
                    BLOCK_FORGE_SELECTION_RISK,
                    **_identity_fields(installed),
                ),
            )
            with _bind_installed(installed):
                blocked = apply_selection_gate_to_preflight(
                    "START_NEW_SESSION", _load_gate(data_root)
                )
            self.assertEqual(blocked["action"], "START_NEW_SESSION")
            self.assertTrue(blocked.get("caveat"))
            self.assertEqual(blocked["router_decision"], BLOCK_FORGE_SELECTION_RISK)
            persist_gate_receipt(
                data_root,
                _hashed_gate_receipt(
                    FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
                    **_identity_fields(installed),
                ),
            )
            with _bind_installed(installed):
                caveat = apply_selection_gate_to_preflight(
                    "START_NEW_SESSION", _load_gate(data_root)
                )
            self.assertEqual(caveat["action"], "START_NEW_SESSION")
            self.assertTrue(caveat.get("caveat"))
            persist_gate_receipt(
                data_root,
                _hashed_gate_receipt(
                    BLOCK_FORGE_EVIDENCE_GAP,
                    **_identity_fields(installed),
                ),
            )
            with _bind_installed(installed):
                gap = apply_selection_gate_to_preflight(
                    "START_NEW_SESSION", _load_gate(data_root)
                )
            self.assertEqual(gap["action"], "START_NEW_SESSION")
            self.assertTrue(gap.get("caveat"))
            self.assertEqual(gap["router_decision"], BLOCK_FORGE_EVIDENCE_GAP)

    def test_skip_stage2_canonical_receipt_binds_dataset_manifest_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            installed = _install_canonical_corpus(data_root)
            fake_stage1 = {
                "scientific_terminal": SHIFT_DETECTED,
                "receipt_sha256": "ab" * 32,
                "input_mode": CANONICAL_INPUT_MODE,
                "terminal_population_scope": SCOPE_CANONICAL,
                "y_point_rows_present_unread": 0,
                "counts": {},
                "census_sha256": installed["census_sha256"],
                "observations_sha256": installed["observations_sha256"],
                "dataset_manifest_id": installed["dataset_manifest_id"],
            }
            with _bind_installed(installed), patch(
                "solana_alpha_lab.factory.hfic_selection_robustness_gate.run_censoring_ignorability_diagnostic",
                return_value=fake_stage1,
            ):
                receipt = run_selection_robustness_gate(
                    root=ROOT,
                    data_root=data_root,
                    persist=True,
                )
            self.assertEqual(receipt["stage2_status"], STAGE2_SKIPPED)
            self.assertEqual(receipt["router_decision"], BLOCK_FORGE_SELECTION_RISK)
            self.assertEqual(
                receipt["dataset_manifest_id"], installed["dataset_manifest_id"]
            )
            self.assertEqual(receipt["corpus_id"], FROZEN_DATASET)
            self.assertEqual(receipt["spec_file_sha256"], FROZEN_SPEC_SHA256)
            with _bind_installed(installed):
                loaded = _load_gate(data_root)
            assert loaded is not None
            self.assertEqual(loaded["receipt_sha256"], receipt["receipt_sha256"])
            self.assertEqual(loaded["router_decision"], BLOCK_FORGE_SELECTION_RISK)


if __name__ == "__main__":
    unittest.main()
