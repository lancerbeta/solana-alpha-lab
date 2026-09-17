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
    FROZEN_SPEC_SHA256 as STAGE1_FROZEN_SPEC_SHA256,
    INCONCLUSIVE as STAGE1_INCONCLUSIVE,
    SHIFT_DETECTED,
    SHIFT_NOT_DETECTED,
    load_diagnostic_spec,
    run_censoring_ignorability_diagnostic,
)
from solana_alpha_lab.factory.hfic_preflight import assert_capability_registry_v2_superset
from solana_alpha_lab.factory.hfic_selection_robustness_gate import (
    BLOCK_FORGE_EVIDENCE_GAP,
    BLOCK_FORGE_SELECTION_RISK,
    CAP_HFIC_SELECTION_ROBUSTNESS_GATE,
    FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
    FROZEN_SPEC_SHA256,
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
from tests.test_hfic_censoring_ignorability_diagnostic_v1 import (
    CENSUS_RELEASE_SCHEMA,
    HOLDERS,
    LAUNCHPAD,
    LIQUIDITY,
    MCAP,
    OBS_RELEASE_SCHEMA,
    PRICE,
    _balanced_fixture,
    _block_a_obs,
    _member,
    _write_parquet,
    _x300,
)

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
        self.assertEqual(
            apply_selection_gate_to_preflight("START_NEW_SESSION", block)["action"],
            "STOP",
        )
        self.assertEqual(
            apply_selection_gate_to_preflight("START_NEW_SESSION", block)["terminal"],
            BLOCK_FORGE_SELECTION_RISK,
        )
        self.assertEqual(
            apply_selection_gate_to_preflight("START_NEW_SESSION", gap)["terminal"],
            BLOCK_FORGE_EVIDENCE_GAP,
        )
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
            loaded = load_applicable_gate_receipt(Path(tmp))
            self.assertIsNone(loaded)
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
            loaded = load_applicable_gate_receipt(Path(tmp))
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["receipt_sha256"], receipt["receipt_sha256"])
            self.assertEqual(
                loaded["router_decision"], FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT
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


if __name__ == "__main__":
    unittest.main()
