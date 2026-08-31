from __future__ import annotations

import copy
import hashlib
import importlib.util
import inspect
import json
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
    ACT_002,
    ACT_003,
    ensure_act002_below_floor,
    live_identity_kwargs,
    successor_identity,
    successor_phrase,
)
from solana_alpha_lab.factory.hfic_preflight import evidence_epoch_material
from solana_alpha_lab.factory.hfic_session import evidence_epoch_sha256
from solana_alpha_lab.factory.observation_schedule_runtime import (
    JupiterReadonlyOpener,
    PROVEN_READONLY_USER_AGENT,
)
from solana_alpha_lab.factory.pathrisk_calibration import (
    TERMINAL_INFORMATIVE,
    load_policy,
)
from solana_alpha_lab.factory.pathrisk_live import (
    CALL_CAP,
    CONSUMED_LIVE_OWNER_PHRASE,
    ControllableClock,
    FixtureWindowOpener,
    PathRiskLiveError,
    load_journal,
    require_owner_phrase,
    resolve_live_window_identity,
    run_live_window,
    run_transport_probe_recent,
)

GIT_SHA = "c" * 40
MAIN_SHA = "b" * 40
T0 = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)
ANCHOR = "2026-09-01T00:05:00Z"
PREDECESSOR_ID = "ACT-PATHRISK-LIVE-001"
REPLACEMENT_ID = "ACT-PATHRISK-LIVE-003"
MINTS = (
    "MintA111111111111111111111111111111111111111",
    "MintB111111111111111111111111111111111111111",
    "MintC111111111111111111111111111111111111111",
    "MintD111111111111111111111111111111111111111",
)
PROD_DATA = ROOT / "local" / "factory_v1" / "data_plane"
PRED_PROD = PROD_DATA / "pathrisk_live" / PREDECESSOR_ID


def _identity():
    return successor_identity()


def _phrase() -> str:
    return successor_phrase()


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


def _run(*, data_root: Path, opener, stop_after: str | None = None, policy=None):
    ensure_act002_below_floor(data_root)
    return run_live_window(
        root=ROOT,
        data_root=data_root,
        opener=opener,
        producer_git_sha=GIT_SHA,
        owner_phrase=_phrase(),
        main_sha=MAIN_SHA,
        clock=ControllableClock(T0),
        stop_after=stop_after,
        store_path=data_root / "observation_schedule_state.sqlite",
        policy=policy,
        production=False,
        **live_identity_kwargs(),
    )


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


def _seed_predecessor(data_root: Path) -> dict[str, str]:
    pred = data_root / "pathrisk_live" / PREDECESSOR_ID
    pred.mkdir(parents=True, exist_ok=True)
    (pred / "journal.json").write_text(
        json.dumps(
            {
                "stage": "RECENT_DONE",
                "recent_sha256": None,
                "recent_reused": False,
                "schedule_sha256": "dead-predecessor-schedule",
                "predecessor_canary": "ACT-001-ONLY",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (pred / "runtime_binding.json").write_text(
        json.dumps(
            {
                "activation_id": PREDECESSOR_ID,
                "schedule_sha256": "dead-predecessor-schedule",
                "starts_at": "2026-08-31T09:19:56.092385Z",
                "stops_admitting_at": "2026-08-31T09:22:56.092385Z",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (pred / "runtime_schedule.yaml").write_text(
        "schedule_key: OBS-EARLY-QUOTE-SURFACE-PATHRISK-LIVE-001\n",
        encoding="utf-8",
    )
    return _tree_hashes(pred)


class PathRiskFreshActivationIdentityTests(unittest.TestCase):
    def test_t6_t7_policy_is_stable_successor_and_runtime_binds_act003(self) -> None:
        identity = _identity()
        self.assertEqual(identity.activation_id, REPLACEMENT_ID)
        self.assertEqual(identity.predecessor_activation_id, ACT_002)
        self.assertEqual(identity.replacement_reason, "MARKET_SUPPLY_RETRY_AFTER_BELOW_FLOOR")
        self.assertNotEqual(identity.activation_id, identity.predecessor_activation_id)
        self.assertNotIn("activation_id", load_policy(ROOT)["live_window"]["identity"])

    def test_t12_predecessor_cannot_be_current(self) -> None:
        with self.assertRaisesRegex(
            PathRiskLiveError, "PREDECESSOR_CANNOT_BE_CURRENT_ACTIVATION"
        ):
            resolve_live_window_identity(load_policy(ROOT), PREDECESSOR_ID, PREDECESSOR_ID)
        self.assertIn("activation_id", inspect.signature(run_live_window).parameters)

    def test_t13_old_calibration_phrase_rejected(self) -> None:
        policy = load_policy(ROOT)
        identity = successor_identity()
        with self.assertRaisesRegex(PathRiskLiveError, "OWNER_PHRASE_CONSUMED"):
            require_owner_phrase(policy, CONSUMED_LIVE_OWNER_PHRASE, identity)
        with self.assertRaisesRegex(PathRiskLiveError, "OWNER_PHRASE_MISMATCH"):
            require_owner_phrase(policy, "not-the-replacement-phrase", identity)

    def test_t14_new_phrase_accepted_only_for_act_003_contract(self) -> None:
        policy = load_policy(ROOT)
        require_owner_phrase(policy, _phrase(), successor_identity())
        self.assertIn(REPLACEMENT_ID, _phrase())
        self.assertIn(ACT_002, _phrase())
        self.assertIn("MARKET_SUPPLY_RETRY_AFTER_BELOW_FLOOR", _phrase())
        other = successor_identity(activation_id="ACT-PATHRISK-LIVE-004", predecessor_activation_id=REPLACEMENT_ID)
        with self.assertRaisesRegex(PathRiskLiveError, "OWNER_PHRASE_MISMATCH"):
            require_owner_phrase(policy, _phrase(), other)

    def test_t1_t2_t3_t4_t5_isolation_from_predecessor(self) -> None:
        opener = FixtureWindowOpener(_fixture())
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            pred_hashes = _seed_predecessor(data_root)
            result = _run(data_root=data_root, opener=opener, stop_after="after_recent")
            pred = data_root / "pathrisk_live" / PREDECESSOR_ID
            repl = data_root / "pathrisk_live" / REPLACEMENT_ID
            self.assertEqual(_tree_hashes(pred), pred_hashes)
            self.assertTrue(repl.is_dir())
            self.assertNotEqual(pred, repl)
            self.assertTrue((repl / "journal.json").is_file())
            self.assertTrue((repl / "runtime_schedule.yaml").is_file())
            self.assertTrue((repl / "runtime_binding.json").is_file())
            journal = json.loads((repl / "journal.json").read_text(encoding="utf-8"))
            binding = json.loads((repl / "runtime_binding.json").read_text(encoding="utf-8"))
            self.assertEqual(journal["activation_id"], REPLACEMENT_ID)
            self.assertEqual(journal["predecessor_activation_id"], ACT_002)
            self.assertIs(journal["resume_of_predecessor"], False)
            self.assertEqual(journal["stage"], "RECENT_DONE")
            pred_journal = json.loads((pred / "journal.json").read_text(encoding="utf-8"))
            self.assertEqual(pred_journal["stage"], "RECENT_DONE")
            self.assertEqual(pred_journal["predecessor_canary"], "ACT-001-ONLY")
            self.assertNotIn("activation_id", pred_journal)
            self.assertNotEqual(journal.get("predecessor_canary"), "ACT-001-ONLY")
            self.assertNotIn("predecessor_canary", journal)
            self.assertEqual(load_journal(data_root, PREDECESSOR_ID)["predecessor_canary"], "ACT-001-ONLY")
            self.assertNotIn("predecessor_canary", load_journal(data_root, REPLACEMENT_ID))
            self.assertEqual(binding["activation_id"], REPLACEMENT_ID)
            self.assertEqual(binding["predecessor_activation_id"], ACT_002)
            self.assertNotEqual(
                binding["schedule_sha256"], pred_journal["schedule_sha256"]
            )
            loaded = load_journal(data_root, REPLACEMENT_ID)
            self.assertEqual(loaded["activation_id"], REPLACEMENT_ID)
            self.assertEqual(result["terminal"], "STOPPED_AFTER_RECENT")

    def test_t8_incompatible_existing_binding_hard_fails(self) -> None:
        opener = FixtureWindowOpener(_fixture())
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            _run(data_root=data_root, opener=opener, stop_after="after_recent")
            binding_path = (
                data_root / "pathrisk_live" / REPLACEMENT_ID / "runtime_binding.json"
            )
            payload = json.loads(binding_path.read_text(encoding="utf-8"))
            payload["predecessor_activation_id"] = "ACT-PATHRISK-LIVE-000"
            binding_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                PathRiskLiveError, "INCOMPATIBLE_ACTIVATION_BINDING"
            ):
                _run(
                    data_root=data_root,
                    opener=FixtureWindowOpener(_fixture()),
                    stop_after="after_recent",
                )

    def test_t9_complete_cannot_run_again(self) -> None:
        opener = FixtureWindowOpener(_fixture())
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            done = _run(data_root=data_root, opener=opener)
            self.assertEqual(done["terminal"], TERMINAL_INFORMATIVE)
            self.assertEqual(done["activation_id"], REPLACEMENT_ID)
            with self.assertRaisesRegex(
                PathRiskLiveError, "PRIOR_PATHRISK_WINDOW_COMPLETED"
            ):
                _run(
                    data_root=data_root,
                    opener=FixtureWindowOpener(_fixture()),
                )

    def test_t10_t11_crash_resume_same_identity_no_duplicate_recent(self) -> None:
        opener = FixtureWindowOpener(_fixture())
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            paused = _run(data_root=data_root, opener=opener, stop_after="after_recent")
            journal_path = (
                data_root / "pathrisk_live" / REPLACEMENT_ID / "journal.json"
            )
            first = json.loads(journal_path.read_text(encoding="utf-8"))
            self.assertEqual(paused["terminal"], "STOPPED_AFTER_RECENT")
            self.assertEqual(first["activation_id"], REPLACEMENT_ID)
            resumed = _run(data_root=data_root, opener=opener)
            second = json.loads(journal_path.read_text(encoding="utf-8"))
            self.assertEqual(second["activation_id"], REPLACEMENT_ID)
            self.assertEqual(second["stage"], "COMPLETE")
            recent = [url for url in opener.urls if "/tokens/v2/recent" in url]
            search = [url for url in opener.urls if "/tokens/v2/search" in url]
            self.assertEqual(len(recent), 1)
            self.assertEqual(len(search), 1)
            self.assertEqual(resumed["terminal"], TERMINAL_INFORMATIVE)
            self.assertFalse((data_root / "pathrisk_live" / PREDECESSOR_ID).exists())

    def test_predecessor_rdp_labels_are_not_overwritten(self) -> None:
        import pyarrow as pa
        import pyarrow.parquet as pq

        opener = FixtureWindowOpener(_fixture())
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            manifests = data_root / "datasets" / "manifests"
            parquet_rel = "datasets/partitions/PARTITION-PRED-PATHRISK-001.parquet"
            parquet_path = data_root / parquet_rel
            parquet_path.parent.mkdir(parents=True, exist_ok=True)
            table = pa.table(
                {
                    "schedule_sha256": pa.array(["dead-predecessor-schedule"], type=pa.string()),
                    "activation_id": pa.array([PREDECESSOR_ID], type=pa.string()),
                    "entity_id": pa.array(["MintPred"], type=pa.string()),
                    "point_id": pa.array(["X300"], type=pa.string()),
                    "primitive_id": pa.array(["PRIM-JUPITER-QUOTE-001"], type=pa.string()),
                }
            )
            pq.write_table(table, parquet_path)
            manifests.mkdir(parents=True, exist_ok=True)
            manifest_id = "DATASET-MANIFEST-PRED-PATHRISK-001"
            (manifests / f"{manifest_id}.json").write_text(
                json.dumps(
                    {
                        "dataset_id": "observation-panel-pred-001",
                        "dataset_manifest_id": manifest_id,
                        "created_at": "2026-08-31T09:27:00Z",
                        "partitions": [
                            {
                                "partition_id": "PARTITION-PRED-PATHRISK-001",
                                "logical_location": parquet_rel.replace("\\", "/"),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (manifests / f"dataset-{manifest_id}.published").write_text(
                json.dumps({"dataset_manifest_id": manifest_id}),
                encoding="utf-8",
            )
            labels_path = manifests / f"{manifest_id}.labels.json"
            pred_labels = {
                "activation_id": PREDECESSOR_ID,
                "pathrisk_terminal": "HISTORICAL_DEAD",
                "predecessor_canary": "ACT-001-LABELS",
            }
            labels_path.write_text(
                json.dumps(pred_labels, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            before = _sha(labels_path)
            done = _run(data_root=data_root, opener=opener)
            self.assertEqual(done["terminal"], TERMINAL_INFORMATIVE)
            self.assertEqual(_sha(labels_path), before)
            after = json.loads(labels_path.read_text(encoding="utf-8"))
            self.assertEqual(after["activation_id"], PREDECESSOR_ID)
            self.assertEqual(after["predecessor_canary"], "ACT-001-LABELS")
            written = list(manifests.glob("*.labels.json"))
            replacement_labels = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in written
                if path.name != f"{manifest_id}.labels.json"
            ]
            self.assertTrue(replacement_labels)
            self.assertTrue(
                all(item.get("activation_id") == REPLACEMENT_ID for item in replacement_labels)
            )

    def test_t15_t16_t17_science_and_caps_unchanged(self) -> None:
        policy = load_policy(ROOT)
        self.assertEqual(policy["runtime_limits"]["max_calls"], CALL_CAP)
        self.assertEqual(CALL_CAP, 26)
        self.assertIs(policy["runtime_limits"]["retry"], False)
        self.assertIs(policy["runtime_limits"]["fallback"], False)
        self.assertEqual(policy["sample"]["floor"], 4)
        self.assertEqual(policy["sample"]["ordering"], "DETERMINISTIC_MINT_ASC")
        self.assertEqual(policy["notionals_lamports"], ["1000000", "10000000"])
        self.assertEqual(policy["horizons"]["t0_offset_seconds"], 300)
        self.assertEqual(policy["horizons"]["h900_offset_seconds"], 900)
        self.assertEqual(policy["population"]["icp_id"], "ICP-EARLY-PUMPFUN-V1")
        self.assertEqual(policy["population"]["seasoning_seconds"], 300)
        self.assertEqual(policy["informative_complete_dual_notional_floor"], 3)
        self.assertFalse(policy["external_authority"]["capture_authorized"])
        live_src = (ROOT / "src/solana_alpha_lab/factory/pathrisk_live.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("ACTIVATION_ID = ", live_src)
        factory = ROOT / "src/solana_alpha_lab/factory/document_runner.py"
        forge = ROOT / "src/solana_alpha_lab/factory/hfic_session.py"
        self.assertTrue(factory.is_file())
        self.assertTrue(forge.is_file())

    def test_t18_t19_production_rdp_and_epoch_untouched(self) -> None:
        pred_hashes = _tree_hashes(PRED_PROD) if PRED_PROD.is_dir() else None
        epoch_before = None
        if PROD_DATA.is_dir():
            epoch_before = evidence_epoch_sha256(
                evidence_epoch_material(ROOT, PROD_DATA)
            )
        opener = FixtureWindowOpener(_fixture())
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            _run(data_root=Path(tmp) / "rdp", opener=opener, stop_after="after_recent")
        if pred_hashes is not None:
            self.assertEqual(_tree_hashes(PRED_PROD), pred_hashes)
        if epoch_before is not None:
            epoch_after = evidence_epoch_sha256(
                evidence_epoch_material(ROOT, PROD_DATA)
            )
            self.assertEqual(epoch_after, epoch_before)

    def test_t20_t21_zero_provider_and_credential_reads(self) -> None:
        class CountingEnv(dict):
            def __init__(self) -> None:
                super().__init__()
                self.reads = 0

            def get(self, key, default=None):  # type: ignore[override]
                self.reads += 1
                return super().get(key, default)

        env = CountingEnv()
        env["JUPITER_API_KEY"] = "fixture-not-a-real-key"
        opener = FixtureWindowOpener(_fixture())
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            ensure_act002_below_floor(data_root)
            result = run_live_window(
                root=ROOT,
                data_root=data_root,
                opener=opener,
                producer_git_sha=GIT_SHA,
                owner_phrase=_phrase(),
                main_sha=MAIN_SHA,
                clock=ControllableClock(T0),
                stop_after="after_recent",
                store_path=Path(tmp) / "rdp" / "observation_schedule_state.sqlite",
                production=False,
                environ=env,
                **live_identity_kwargs(),
            )
        self.assertEqual(result["quote_calls"], 0)
        self.assertEqual(env.reads, 0)
        self.assertFalse(load_policy(ROOT)["external_authority"]["capture_authorized"])

    def test_t22_secret_leak_tests_pass(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "secret_scan_identity", ROOT / "scripts" / "secret_scan.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.run_self_test(), [])
        for relative in (
            "src/solana_alpha_lab/factory/pathrisk_live.py",
            "configs/early_quote_surface_pathrisk_calibration_v1.yaml",
            "tests/test_pathrisk_fresh_activation_identity.py",
        ):
            self.assertEqual(
                module.findings_for_text((ROOT / relative).read_text(encoding="utf-8")),
                [],
            )

    def test_t23_transport_probe_independent_null_activation(self) -> None:
        opener = FixtureWindowOpener(_fixture())
        payload = run_transport_probe_recent(opener=opener, clock=ControllableClock(T0))
        self.assertIsNone(payload["activation_id"])
        self.assertIs(payload["scientific_window_started"], False)
        self.assertEqual(payload["provider_calls"], 1)
        self.assertEqual(payload["rdp_mutation"], 0)

    def test_t24_opener_parity_profile_still_bound(self) -> None:
        self.assertIn("solana-alpha-lab/quote-native-evidence-qualification-v1", PROVEN_READONLY_USER_AGENT)
        source = inspect.getsource(JupiterReadonlyOpener)
        self.assertIn("PROVEN_READONLY_USER_AGENT", source)
        self.assertNotIn(PREDECESSOR_ID, source)
        self.assertNotIn(REPLACEMENT_ID, source)

    def test_copied_predecessor_journal_is_not_resumed_as_replacement(self) -> None:
        opener = FixtureWindowOpener(_fixture())
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            _seed_predecessor(data_root)
            dest = data_root / "pathrisk_live" / REPLACEMENT_ID
            dest.mkdir(parents=True)
            pred_journal = (
                data_root / "pathrisk_live" / PREDECESSOR_ID / "journal.json"
            ).read_text(encoding="utf-8")
            (dest / "journal.json").write_text(pred_journal, encoding="utf-8")
            with self.assertRaisesRegex(
                PathRiskLiveError, "INCOMPATIBLE_ACTIVATION_BINDING"
            ):
                _run(data_root=data_root, opener=opener, stop_after="after_recent")


if __name__ == "__main__":
    unittest.main()
