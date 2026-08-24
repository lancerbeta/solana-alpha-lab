from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.early_holder_concentration_h900_falsifier import (  # noqa: E402
    AUTHORITY_PHRASE,
    CONFIRMATORY_ATOM_ID,
    CONFIRMATORY_AUTHORITY_PHRASE,
    CONFIRMATORY_CLOSE_TERMINAL,
    CONFIRMATORY_EARN_TERMINAL,
    FACTORY_RUNNER,
    FACTORY_RUNNER_SHA256,
    INVALID_TERMINAL,
    JUPITER_TOP_HOLDERS_POOL_EXCLUSION,
    X_FORMULA,
    holder_identity,
    run_holder_concentration_campaign,
    validate_holder_concentration_policy,
)
from solana_alpha_lab.ordinary_recent_organic_pressure_h900_audition import (  # noqa: E402
    OrganicPressureError,
)
from scripts.run_early_holder_concentration_h900_falsifier import (  # noqa: E402
    owner_exit_blocked,
    run_capture,
)
from tests.test_early_holder_concentration_h900_falsifier import (  # noqa: E402
    _Clock,
    _PathOpener,
    _row,
)

CONFIG_PATH = ROOT / "configs/early_holder_concentration_h900_confirmatory_oos_v1.yaml"
FALSIFIER_CONFIG_PATH = ROOT / "configs/early_holder_concentration_h900_falsifier_v1.yaml"
CAMPAIGN_PATH = "src/solana_alpha_lab/ordinary_recent_organic_pressure_h900_audition.py"
RUNNER_PATH = "src/solana_alpha_lab/factory/runner.py"


class HolderConcentrationConfirmatoryTests(unittest.TestCase):
    def test_confirmatory_policy_identity_and_frozen_science(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(policy, dict)
        validate_holder_concentration_policy(policy, root=ROOT)
        identity = holder_identity(policy)
        self.assertEqual(policy["atom_id"], CONFIRMATORY_ATOM_ID)
        self.assertEqual(identity["atom_id"], CONFIRMATORY_ATOM_ID)
        self.assertEqual(policy["external_authority"]["owner_phrase"], CONFIRMATORY_AUTHORITY_PHRASE)
        self.assertEqual(identity["phrase"], CONFIRMATORY_AUTHORITY_PHRASE)
        self.assertEqual(identity["close"], CONFIRMATORY_CLOSE_TERMINAL)
        self.assertEqual(identity["earn"], CONFIRMATORY_EARN_TERMINAL)
        self.assertEqual(
            identity["receipt_id"],
            "EVIDENCE-EARLY-HOLDER-CONCENTRATION-H900-CONFIRMATORY-RUNTIME-001",
        )
        self.assertEqual(identity["raw_root"], "local/early_holder_concentration_h900_confirmatory_oos")
        self.assertEqual(
            identity["evidence_dir"],
            "docs/evidence/early_holder_concentration_h900_confirmatory_oos",
        )
        self.assertEqual(policy["decision_snapshot"]["x_formula"], X_FORMULA)
        self.assertEqual(policy["decision_rule"]["min_decision_time_eligible"], 18)
        self.assertEqual(policy["decision_rule"]["min_rankable_h900"], 14)
        self.assertEqual(policy["decision_rule"]["expected_direction"], "NEGATIVE")
        self.assertEqual(policy["population"]["icp_id"], "ICP-EARLY-PUMPFUN-V1")
        self.assertEqual(policy["limitations"]["jupiter_top_holders_pool_exclusion"], JUPITER_TOP_HOLDERS_POOL_EXCLUSION)
        self.assertNotIn("tau_b_floor", policy["decision_rule"])
        falsifier = yaml.safe_load(FALSIFIER_CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(falsifier, dict)
        for key in (
            "population",
            "decision_snapshot",
            "quote",
            "execution_controls",
            "runtime_limits",
        ):
            self.assertEqual(policy[key], falsifier[key], key)
        self.assertEqual(
            policy["decision_rule"]["min_decision_time_eligible"],
            falsifier["decision_rule"]["min_decision_time_eligible"],
        )
        self.assertEqual(
            policy["decision_rule"]["min_rankable_h900"],
            falsifier["decision_rule"]["min_rankable_h900"],
        )
        digest = hashlib.sha256((ROOT / FACTORY_RUNNER).read_bytes()).hexdigest()
        self.assertEqual(digest, FACTORY_RUNNER_SHA256)
        self.assertEqual(policy["factory_runner_sha256"], FACTORY_RUNNER_SHA256)

    def test_unknown_atom_id_is_rejected(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(policy, dict)
        policy["atom_id"] = "EARLY_HOLDER_CONCENTRATION_H900_THIRD_SAMPLE_V1"
        with self.assertRaisesRegex(OrganicPressureError, "ATOM_ID_NOT_IN_HOLDER_IDENTITY_ALLOWLIST"):
            validate_holder_concentration_policy(policy, root=ROOT)

    def test_campaign_and_factory_runner_match_origin_main(self) -> None:
        for relative in (CAMPAIGN_PATH, RUNNER_PATH):
            result = subprocess.run(
                ["git", "diff", "--exit-code", "origin/main", "--", relative],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"{relative} drifted from origin/main:\n{result.stdout}{result.stderr}",
            )

    def test_mocked_negative_replicates_and_positive_closes_family(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        earn_recent = [_row(index, top_holders=60.0 - index) for index in range(24)]
        earn_search = [_row(index, top_holders=60.0 - index) for index in range(24)]
        clock = _Clock()
        earn_receipt = run_holder_concentration_campaign(
            policy,
            authority_phrase=CONFIRMATORY_AUTHORITY_PHRASE,
            reservation={"state": "STARTED", "credential_reads": 0},
            excluded_mints={"prior"},
            credential_loader=lambda: "test-key",
            preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0, "provider_requests": 0},
            opener=_PathOpener(earn_recent, earn_search),
            clock=clock.now,
            sleeper=clock.sleep,
            monotonic_clock=lambda: 0.0,
        )
        self.assertLess(earn_receipt["score"]["tau_b"], 0)
        self.assertEqual(earn_receipt["terminal_outcome"], CONFIRMATORY_EARN_TERMINAL)
        self.assertNotEqual(earn_receipt["terminal_outcome"], "EARN_ONE_CONFIRMATORY_FRESH_OOS")
        for claim in ("NO_ALPHA", "NO_NETRETURN", "NO_STRATEGY_OR_SHADOW"):
            self.assertIn(claim, earn_receipt["non_claims"])
        self.assertEqual(
            earn_receipt["limitations"]["jupiter_top_holders_pool_exclusion"],
            JUPITER_TOP_HOLDERS_POOL_EXCLUSION,
        )

        close_recent = [_row(index, top_holders=float(index)) for index in range(24)]
        close_search = [_row(index, top_holders=float(index)) for index in range(24)]
        close_clock = _Clock()
        close_receipt = run_holder_concentration_campaign(
            policy,
            authority_phrase=CONFIRMATORY_AUTHORITY_PHRASE,
            reservation={"state": "STARTED", "credential_reads": 0},
            excluded_mints={"prior"},
            credential_loader=lambda: "test-key",
            preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0, "provider_requests": 0},
            opener=_PathOpener(close_recent, close_search),
            clock=close_clock.now,
            sleeper=close_clock.sleep,
            monotonic_clock=lambda: 0.0,
        )
        self.assertGreaterEqual(close_receipt["score"]["tau_b"], 0)
        self.assertEqual(close_receipt["terminal_outcome"], CONFIRMATORY_CLOSE_TERMINAL)
        self.assertNotEqual(close_receipt["terminal_outcome"], "CLOSE_HOLDER_CONCENTRATION_FAMILY")

    def test_wrong_confirmatory_phrase_never_reads_credential(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        reads = {"count": 0}

        def loader() -> str:
            reads["count"] += 1
            return "secret-key"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            excluded = root / "excluded.json"
            excluded.write_text(json.dumps({"mints": ["prior-mint"]}), encoding="utf-8")
            with self.assertRaisesRegex(OrganicPressureError, "AUTHORITY_PHRASE_INVALID"):
                run_capture(
                    authority_phrase="WRONG",
                    excluded_mints_path=excluded,
                    policy=policy,
                    config_path=CONFIG_PATH,
                    raw_root=root / "raw",
                    receipt_path=root / "receipt.json",
                    credential_loader=loader,
                )
        self.assertEqual(reads["count"], 0)

    def test_falsifier_phrase_with_confirmatory_config_is_mismatch_not_invalid(self) -> None:
        policy = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        reads = {"count": 0}

        def loader() -> str:
            reads["count"] += 1
            return "secret-key"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            excluded = root / "excluded.json"
            excluded.write_text(json.dumps({"mints": ["prior-mint"]}), encoding="utf-8")
            with self.assertRaisesRegex(OrganicPressureError, "AUTHORITY_PHRASE_CONFIG_MISMATCH"):
                run_capture(
                    authority_phrase=AUTHORITY_PHRASE,
                    excluded_mints_path=excluded,
                    policy=policy,
                    config_path=CONFIG_PATH,
                    raw_root=root / "raw",
                    receipt_path=root / "receipt.json",
                    credential_loader=loader,
                )
        self.assertEqual(reads["count"], 0)

    def test_cli_treats_confirmatory_terminals_as_success(self) -> None:
        self.assertFalse(owner_exit_blocked(CONFIRMATORY_CLOSE_TERMINAL))
        self.assertFalse(owner_exit_blocked(CONFIRMATORY_EARN_TERMINAL))
        self.assertFalse(owner_exit_blocked("EARN_ONE_CONFIRMATORY_FRESH_OOS"))
        self.assertFalse(owner_exit_blocked("CLOSE_HOLDER_CONCENTRATION_FAMILY"))
        self.assertTrue(owner_exit_blocked(INVALID_TERMINAL))
        self.assertTrue(owner_exit_blocked("INVALID_EVIDENCE_YIELD"))
        from scripts.run_early_holder_concentration_h900_falsifier import SUCCESS_TERMINALS

        self.assertIn(CONFIRMATORY_CLOSE_TERMINAL, SUCCESS_TERMINALS)
        self.assertIn(CONFIRMATORY_EARN_TERMINAL, SUCCESS_TERMINALS)
        from scripts.run_early_holder_concentration_h900_falsifier import _owner_next_for_error

        self.assertEqual(
            _owner_next_for_error("AUTHORITY_PHRASE_CONFIG_MISMATCH"),
            "PASS_MATCHING_CONFIG_YAML_VIA_--config_FOR_THIS_PHRASE",
        )


if __name__ == "__main__":
    unittest.main()
