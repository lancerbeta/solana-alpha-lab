from __future__ import annotations

import copy
import hashlib
import importlib.util
import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

from pathrisk_live_testkit import (
    ACT_001,
    ACT_002,
    ACT_003,
    ACT_004,
    live_identity_kwargs,
    seed_act001_recent_done,
    seed_act002_below_floor,
    seed_window_journal,
    successor_identity,
    successor_phrase,
)
from solana_alpha_lab.factory.hfic_preflight import evidence_epoch_material
from solana_alpha_lab.factory.hfic_session import evidence_epoch_sha256
from solana_alpha_lab.factory.pathrisk_calibration import (
    TERMINAL_BELOW_FLOOR,
    TERMINAL_INFORMATIVE,
    load_policy,
)
from solana_alpha_lab.factory.pathrisk_live import (
    CALL_CAP,
    CONSUMED_ACT002_LIVE_OWNER_PHRASE,
    CONSUMED_LIVE_OWNER_PHRASE,
    SUCCESSOR_REASON_MARKET_SUPPLY_RETRY,
    ControllableClock,
    FixtureWindowOpener,
    PathRiskLiveError,
    load_journal,
    load_successor_identity_policy,
    require_owner_phrase,
    resolve_live_window_identity,
    run_live_window,
    successor_preflight,
)

GIT_SHA = "c" * 40
MAIN_SHA = "b" * 40
T0 = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)
ANCHOR = "2026-09-01T00:05:00Z"
MINTS = (
    "MintA111111111111111111111111111111111111111",
    "MintB111111111111111111111111111111111111111",
    "MintC111111111111111111111111111111111111111",
    "MintD111111111111111111111111111111111111111",
)
POLICY_PATH = ROOT / "configs" / "early_quote_surface_pathrisk_calibration_v1.yaml"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_hashes(directory: Path) -> dict[str, str]:
    if not directory.is_dir():
        return {}
    hashed: dict[str, str] = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            hashed[path.relative_to(directory).as_posix()] = _sha(path)
    return hashed


def _row(mint: str, *, liquidity: str = "2000") -> dict:
    return {
        "id": mint,
        "liquidity": liquidity,
        "firstPool": {"createdAt": ANCHOR, "source": "pump.fun"},
        "first_seen_at": ANCHOR,
    }


def _fixture(mints=MINTS) -> dict:
    return {
        "recent": [{"id": mint} for mint in mints],
        "search": [_row(mint) for mint in mints],
    }


def _run(
    *,
    data_root: Path,
    opener,
    stop_after: str | None = None,
    activation_id: str = ACT_003,
    predecessor_activation_id: str = ACT_002,
    owner_phrase: str | None = None,
    policy=None,
):
    return run_live_window(
        root=ROOT,
        data_root=data_root,
        opener=opener,
        producer_git_sha=GIT_SHA,
        owner_phrase=owner_phrase
        or successor_phrase(
            activation_id=activation_id,
            predecessor_activation_id=predecessor_activation_id,
            policy=policy,
        ),
        main_sha=MAIN_SHA,
        clock=ControllableClock(T0),
        stop_after=stop_after,
        store_path=data_root / "observation_schedule_state.sqlite",
        policy=policy,
        production=False,
        **live_identity_kwargs(
            activation_id=activation_id,
            predecessor_activation_id=predecessor_activation_id,
        ),
    )


class PathRiskSuccessorWindowIdentityTests(unittest.TestCase):
    def test_t1_act001_immutable(self) -> None:
        opener = FixtureWindowOpener(_fixture())
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            pred = seed_act001_recent_done(data_root)
            seed_act002_below_floor(data_root)
            before = _tree_hashes(pred)
            _run(data_root=data_root, opener=opener, stop_after="after_recent")
            self.assertEqual(_tree_hashes(pred), before)

    def test_t2_act002_immutable(self) -> None:
        opener = FixtureWindowOpener(_fixture())
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            pred = seed_act002_below_floor(data_root)
            before = _tree_hashes(pred)
            _run(data_root=data_root, opener=opener, stop_after="after_recent")
            self.assertEqual(_tree_hashes(pred), before)

    def test_t3_t4_successor_preflight_proposes_act003(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            seed_act001_recent_done(data_root)
            seed_act002_below_floor(data_root)
            payload = successor_preflight(data_root=data_root, policy=load_policy(ROOT))
        self.assertTrue(payload["eligible_for_successor"])
        self.assertEqual(payload["predecessor_activation_id"], ACT_002)
        self.assertEqual(payload["predecessor_terminal"], TERMINAL_BELOW_FLOOR)
        self.assertEqual(payload["proposed_activation_id"], ACT_003)
        self.assertEqual(payload["successor_reason"], SUCCESSOR_REASON_MARKET_SUPPLY_RETRY)
        self.assertEqual(payload["exact_future_owner_phrase"], successor_phrase())
        self.assertFalse(payload["credential_reads"])
        self.assertEqual(payload["provider_calls"], 0)
        self.assertFalse(payload["git_mutated"])

    def test_t5_t6_t7_act003_runtime_journal_binding_distinct(self) -> None:
        opener = FixtureWindowOpener(_fixture())
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            pred = seed_act002_below_floor(data_root)
            _run(data_root=data_root, opener=opener, stop_after="after_recent")
            successor = data_root / "pathrisk_live" / ACT_003
            self.assertTrue(successor.is_dir())
            self.assertNotEqual(successor, pred)
            journal = load_journal(data_root, ACT_003)
            self.assertEqual(journal["activation_id"], ACT_003)
            self.assertEqual(journal["predecessor_activation_id"], ACT_002)
            self.assertNotEqual(journal, json.loads((pred / "journal.json").read_text(encoding="utf-8")))
            binding = json.loads((successor / "runtime_binding.json").read_text(encoding="utf-8"))
            pred_binding = json.loads((pred / "runtime_binding.json").read_text(encoding="utf-8"))
            self.assertEqual(binding["activation_id"], ACT_003)
            self.assertNotEqual(binding["activation_id"], pred_binding["activation_id"])
            self.assertTrue((successor / "runtime_schedule.yaml").is_file())
            self.assertNotEqual(
                (successor / "runtime_schedule.yaml").read_bytes(),
                (pred / "runtime_schedule.yaml").read_bytes(),
            )

    def test_t8_act003_cannot_load_act002_state(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            seed_act002_below_floor(data_root)
            foreign = json.loads(
                (data_root / "pathrisk_live" / ACT_002 / "journal.json").read_text(encoding="utf-8")
            )
            seed_window_journal(
                data_root,
                activation_id=ACT_003,
                stage="RECENT_DONE",
                predecessor_activation_id=ACT_001,
                replacement_reason="PRE_EVIDENCE_OPERATIONAL_FAILURE",
                extra={"recent_sha256": foreign.get("stage")},
            )
            with self.assertRaisesRegex(PathRiskLiveError, "INCOMPATIBLE_ACTIVATION_BINDING"):
                _run(
                    data_root=data_root,
                    opener=FixtureWindowOpener(_fixture()),
                    stop_after="after_recent",
                )

    def test_t9_predecessor_must_exist(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            with self.assertRaisesRegex(PathRiskLiveError, "PREDECESSOR_JOURNAL_MISSING"):
                _run(
                    data_root=Path(tmp) / "rdp",
                    opener=FixtureWindowOpener(_fixture()),
                    stop_after="after_recent",
                )

    def test_t10_predecessor_identity_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            seed_window_journal(
                data_root,
                activation_id=ACT_002,
                stage="BELOW_FLOOR",
                terminal=TERMINAL_BELOW_FLOOR,
                predecessor_activation_id=ACT_001,
                replacement_reason="PRE_EVIDENCE_OPERATIONAL_FAILURE",
                extra={"activation_id": ACT_001},
            )
            with self.assertRaisesRegex(PathRiskLiveError, "PREDECESSOR_IDENTITY_MISMATCH"):
                _run(
                    data_root=data_root,
                    opener=FixtureWindowOpener(_fixture()),
                    stop_after="after_recent",
                )

    def test_t11_predecessor_must_be_below_floor(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            seed_window_journal(
                data_root,
                activation_id=ACT_002,
                stage="SAMPLED",
                predecessor_activation_id=ACT_001,
                replacement_reason="PRE_EVIDENCE_OPERATIONAL_FAILURE",
            )
            with self.assertRaisesRegex(PathRiskLiveError, "PREDECESSOR_NOT_BELOW_FLOOR"):
                _run(
                    data_root=data_root,
                    opener=FixtureWindowOpener(_fixture()),
                    stop_after="after_recent",
                )

    def test_t12_predecessor_recent_done_fails(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            seed_window_journal(
                data_root,
                activation_id=ACT_002,
                stage="RECENT_DONE",
                predecessor_activation_id=ACT_001,
                replacement_reason="PRE_EVIDENCE_OPERATIONAL_FAILURE",
            )
            with self.assertRaisesRegex(PathRiskLiveError, "PREDECESSOR_NOT_BELOW_FLOOR"):
                _run(
                    data_root=data_root,
                    opener=FixtureWindowOpener(_fixture()),
                    stop_after="after_recent",
                )

    def test_t13_informative_complete_predecessor_does_not_grant_ordinary_successor(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            seed_window_journal(
                data_root,
                activation_id=ACT_002,
                stage="COMPLETE",
                terminal=TERMINAL_INFORMATIVE,
                predecessor_activation_id=ACT_001,
                replacement_reason="PRE_EVIDENCE_OPERATIONAL_FAILURE",
            )
            with self.assertRaisesRegex(
                PathRiskLiveError,
                "PREDECESSOR_INFORMATIVE_OR_COMPLETE_FORBIDS_ORDINARY_SUCCESSOR",
            ):
                _run(
                    data_root=data_root,
                    opener=FixtureWindowOpener(_fixture()),
                    stop_after="after_recent",
                )
            payload = successor_preflight(data_root=data_root, policy=load_policy(ROOT))
            self.assertFalse(payload["eligible_for_successor"])
            self.assertIsNone(payload["exact_future_owner_phrase"])

    def test_t14_t15_sequence_plus_one_and_branching_forbidden(self) -> None:
        policy = load_policy(ROOT)
        with self.assertRaisesRegex(PathRiskLiveError, "SUCCESSOR_SEQUENCE_MUST_BE_PLUS_ONE"):
            resolve_live_window_identity(policy, ACT_004, ACT_002)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            seed_act002_below_floor(data_root)
            with self.assertRaisesRegex(PathRiskLiveError, "SUCCESSOR_SEQUENCE_MUST_BE_PLUS_ONE"):
                _run(
                    data_root=data_root,
                    opener=FixtureWindowOpener(_fixture()),
                    activation_id=ACT_004,
                    predecessor_activation_id=ACT_002,
                    stop_after="after_recent",
                )

    def test_t16_same_act003_incomplete_may_resume(self) -> None:
        opener = FixtureWindowOpener(_fixture())
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            seed_act002_below_floor(data_root)
            first = _run(data_root=data_root, opener=opener, stop_after="after_recent")
            second = _run(data_root=data_root, opener=opener)
            self.assertEqual(first["terminal"], "STOPPED_AFTER_RECENT")
            self.assertEqual(second["terminal"], TERMINAL_INFORMATIVE)
            self.assertEqual(load_journal(data_root, ACT_003)["activation_id"], ACT_003)

    def test_t17_same_act003_below_floor_cannot_rerun(self) -> None:
        opener = FixtureWindowOpener(_fixture(MINTS[:3]))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            seed_act002_below_floor(data_root)
            first = _run(data_root=data_root, opener=opener)
            self.assertEqual(first["terminal"], TERMINAL_BELOW_FLOOR)
            with self.assertRaisesRegex(PathRiskLiveError, "PRIOR_PATHRISK_WINDOW_BELOW_FLOOR"):
                _run(data_root=data_root, opener=opener)

    def test_t18_same_act003_complete_cannot_rerun(self) -> None:
        opener = FixtureWindowOpener(_fixture())
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            seed_act002_below_floor(data_root)
            first = _run(data_root=data_root, opener=opener)
            self.assertEqual(first["terminal"], TERMINAL_INFORMATIVE)
            with self.assertRaisesRegex(PathRiskLiveError, "PRIOR_PATHRISK_WINDOW_COMPLETED"):
                _run(data_root=data_root, opener=opener)

    def test_t19_t20_phrase_accepted_only_for_matching_identity(self) -> None:
        policy = load_policy(ROOT)
        phrase_003 = successor_phrase()
        require_owner_phrase(policy, phrase_003, successor_identity())
        identity_004 = successor_identity(activation_id=ACT_004, predecessor_activation_id=ACT_003)
        with self.assertRaisesRegex(PathRiskLiveError, "OWNER_PHRASE_MISMATCH"):
            require_owner_phrase(policy, phrase_003, identity_004)

    def test_t21_act002_phrase_rejected_for_act003(self) -> None:
        policy = load_policy(ROOT)
        with self.assertRaisesRegex(PathRiskLiveError, "OWNER_PHRASE_CONSUMED"):
            require_owner_phrase(policy, CONSUMED_ACT002_LIVE_OWNER_PHRASE, successor_identity())

    def test_t22_consumed_act001_phrase_rejected(self) -> None:
        policy = load_policy(ROOT)
        with self.assertRaisesRegex(PathRiskLiveError, "OWNER_PHRASE_CONSUMED"):
            require_owner_phrase(policy, CONSUMED_LIVE_OWNER_PHRASE, successor_identity())

    def test_t23_wrong_predecessor_in_phrase_rejected(self) -> None:
        policy = load_policy(ROOT)
        identity = successor_identity()
        mutated = successor_phrase().replace(ACT_002, ACT_001)
        with self.assertRaisesRegex(PathRiskLiveError, "OWNER_PHRASE_MISMATCH"):
            require_owner_phrase(policy, mutated, identity)

    def test_t24_wrong_reason_in_phrase_rejected(self) -> None:
        policy = load_policy(ROOT)
        mutated = successor_phrase().replace(
            SUCCESSOR_REASON_MARKET_SUPPLY_RETRY,
            "PRE_EVIDENCE_OPERATIONAL_FAILURE",
        )
        with self.assertRaisesRegex(PathRiskLiveError, "OWNER_PHRASE_MISMATCH"):
            require_owner_phrase(policy, mutated, successor_identity())

    def test_t25_t26_t27_t28_science_authority_retained(self) -> None:
        policy = load_policy(ROOT)
        phrase = successor_phrase()
        self.assertIn("call cap 26", phrase)
        self.assertIn("10000000", phrase)
        self.assertIn("1000000", phrase)
        self.assertIn("ICP-EARLY-PUMPFUN-V1", phrase)
        self.assertIn("no retry / fallback", phrase)
        self.assertIn("JUPITER_API_KEY", phrase)
        self.assertIn("quote-only /swap/v2/order", phrase)
        self.assertEqual(int(policy["runtime_limits"]["max_calls"]), CALL_CAP)
        self.assertIs(policy["runtime_limits"]["retry"], False)
        self.assertIs(policy["runtime_limits"]["fallback"], False)
        self.assertEqual(policy["sample"]["floor"], 4)
        self.assertEqual(policy["informative_complete_dual_notional_floor"], 3)
        self.assertNotIn("activation_id", policy["live_window"]["identity"])
        self.assertEqual(
            policy["external_authority"]["owner_phrase_source"],
            "SUCCESSOR_DETERMINISTIC_RENDERER",
        )
        self.assertIsNone(load_policy(ROOT).get("external_authority", {}).get("future_owner_phrase"))

    def test_t29_t30_transport_and_http_class_modules_remain(self) -> None:
        self.assertTrue((ROOT / "tests" / "test_jupiter_readonly_transport_parity.py").is_file())
        self.assertTrue((ROOT / "tests" / "test_pathrisk_recent_http_class.py").is_file())

    def test_t31_t32_no_rdp_publication_or_git_epoch_mutation(self) -> None:
        opener = FixtureWindowOpener(_fixture())
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            unused = Path(tmp) / "epoch-baseline"
            unused.mkdir()
            before = evidence_epoch_sha256(evidence_epoch_material(ROOT, unused))
            data_root = Path(tmp) / "rdp"
            seed_act002_below_floor(data_root)
            result = _run(data_root=data_root, opener=opener, stop_after="after_recent")
            after = evidence_epoch_sha256(evidence_epoch_material(ROOT, unused))
            published = list((data_root / "datasets" / "manifests").glob("dataset-*.published"))
        self.assertEqual(published, [])
        self.assertFalse(result.get("rdp_manifest_last", False))
        self.assertEqual(after, before)
        self.assertFalse(result["git_mutated"])

    def test_t33_t34_zero_provider_and_credential_reads(self) -> None:
        class CountingEnv(dict):
            def get(self, key, default=None):  # type: ignore[override]
                self.reads = getattr(self, "reads", 0) + 1
                return super().get(key, default)

        env = CountingEnv()
        env["JUPITER_API_KEY"] = "fixture-not-a-real-key"
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            seed_act002_below_floor(data_root)
            result = run_live_window(
                root=ROOT,
                data_root=data_root,
                opener=FixtureWindowOpener(_fixture()),
                producer_git_sha=GIT_SHA,
                owner_phrase=successor_phrase(),
                main_sha=MAIN_SHA,
                clock=ControllableClock(T0),
                stop_after="after_recent",
                store_path=data_root / "observation_schedule_state.sqlite",
                production=False,
                environ=env,
                **live_identity_kwargs(),
            )
        self.assertEqual(result["quote_calls"], 0)
        self.assertEqual(getattr(env, "reads", 0), 0)

    def test_t35_secret_leak_tests_pass(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "secret_scan_successor", ROOT / "scripts" / "secret_scan.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.run_self_test(), [])
        for relative in (
            "src/solana_alpha_lab/factory/pathrisk_live.py",
            "configs/early_quote_surface_pathrisk_calibration_v1.yaml",
            "tests/test_pathrisk_successor_window_identity.py",
        ):
            findings = module.findings_for_text((ROOT / relative).read_text(encoding="utf-8"))
            self.assertEqual(findings, [], findings)

    def test_product_proof_act003_then_act004_without_git_change(self) -> None:
        policy_before = _sha(POLICY_PATH)
        opener = FixtureWindowOpener(_fixture(MINTS[:3]))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            seed_act002_below_floor(data_root)
            first = successor_preflight(data_root=data_root, policy=load_policy(ROOT))
            self.assertEqual(first["proposed_activation_id"], ACT_003)
            below = _run(
                data_root=data_root,
                opener=opener,
                owner_phrase=first["exact_future_owner_phrase"],
            )
            self.assertEqual(below["terminal"], TERMINAL_BELOW_FLOOR)
            self.assertEqual(_sha(POLICY_PATH), policy_before)
            second = successor_preflight(data_root=data_root, policy=load_policy(ROOT))
            self.assertTrue(second["eligible_for_successor"])
            self.assertEqual(second["predecessor_activation_id"], ACT_003)
            self.assertEqual(second["proposed_activation_id"], ACT_004)
            self.assertEqual(second["successor_reason"], SUCCESSOR_REASON_MARKET_SUPPLY_RETRY)
            self.assertIn(ACT_004, second["exact_future_owner_phrase"])
            self.assertIn(ACT_003, second["exact_future_owner_phrase"])
            self.assertNotEqual(first["exact_future_owner_phrase"], second["exact_future_owner_phrase"])
            fourth = _run(
                data_root=data_root,
                opener=FixtureWindowOpener(_fixture(MINTS[:3])),
                activation_id=ACT_004,
                predecessor_activation_id=ACT_003,
                owner_phrase=second["exact_future_owner_phrase"],
            )
            self.assertEqual(fourth["terminal"], TERMINAL_BELOW_FLOOR)
            self.assertEqual(load_journal(data_root, ACT_004)["activation_id"], ACT_004)
            self.assertEqual(load_journal(data_root, ACT_003)["stage"], "BELOW_FLOOR")
        self.assertEqual(_sha(POLICY_PATH), policy_before)
        self.assertNotIn("activation_id: ACT-PATHRISK-LIVE-003", POLICY_PATH.read_text(encoding="utf-8"))
        self.assertNotIn("activation_id: ACT-PATHRISK-LIVE-004", POLICY_PATH.read_text(encoding="utf-8"))

    def test_predecessor_below_floor_stage_maps_when_terminal_omitted(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            seed_window_journal(
                data_root,
                activation_id=ACT_002,
                stage="BELOW_FLOOR",
                predecessor_activation_id=ACT_001,
                replacement_reason="PRE_EVIDENCE_OPERATIONAL_FAILURE",
            )
            result = _run(
                data_root=data_root,
                opener=FixtureWindowOpener(_fixture()),
                stop_after="after_recent",
            )
            self.assertEqual(result["terminal"], "STOPPED_AFTER_RECENT")

    def test_git_policy_is_stable_successor_rules(self) -> None:
        rules = load_successor_identity_policy(load_policy(ROOT))
        self.assertEqual(rules["namespace"], "ACT-PATHRISK-LIVE")
        self.assertEqual(rules["successor_reason"], SUCCESSOR_REASON_MARKET_SUPPLY_RETRY)
        self.assertEqual(rules["sequence_step"], 1)
        mutated = copy.deepcopy(load_policy(ROOT))
        mutated["live_window"]["identity"]["activation_id"] = ACT_003
        with self.assertRaisesRegex(PathRiskLiveError, "GIT_PER_WINDOW_IDENTITY_FORBIDDEN"):
            load_successor_identity_policy(mutated)

    def test_run_live_window_requires_runtime_identity(self) -> None:
        self.assertIn("activation_id", inspect.signature(run_live_window).parameters)
        self.assertIn("predecessor_activation_id", inspect.signature(run_live_window).parameters)

    def test_uuid_identity_rejected(self) -> None:
        with self.assertRaisesRegex(PathRiskLiveError, "LIVE_IDENTITY_NAMESPACE_MISMATCH"):
            resolve_live_window_identity(load_policy(ROOT), "SCIENCE-CAMPAIGN-UUID", ACT_002)

    def test_cli_successor_preflight_zero_network(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            seed_act002_below_floor(data_root)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts" / "early_quote_surface_pathrisk_calibration.py"),
                    "successor-preflight",
                    "--data-root",
                    str(data_root),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["proposed_activation_id"], ACT_003)
        self.assertTrue(payload["eligible_for_successor"])


if __name__ == "__main__":
    unittest.main()
