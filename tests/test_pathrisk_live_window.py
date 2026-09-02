from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

from pathrisk_live_testkit import (
    ACT_003,
    ensure_act002_below_floor,
    live_identity_kwargs,
    successor_phrase,
)
from solana_alpha_lab.contracts.schema_v1 import DatasetManifest, PartitionManifest
from solana_alpha_lab.factory.pathrisk_calibration import (
    NOTIONAL_10M,
    NOTIONAL_1M,
    TERMINAL_BELOW_FLOOR,
    TERMINAL_DEGENERATE,
    TERMINAL_INFORMATIVE,
    TERMINAL_INVALID,
    TERMINAL_PARTIAL,
    load_policy,
    select_r0_sample,
)
from solana_alpha_lab.factory.pathrisk_live import (
    CALL_CAP,
    FORBIDDEN_SEARCH_BUNDLE,
    ControllableClock,
    FixtureWindowOpener,
    HardCapOpener,
    compile_live_schedule,
    count_url_kinds,
    resolve_consumed_exclusions,
    run_live_window,
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
CONSUMED_PUMP = "7DtkuLZfHmF51sifFtd2AjdZe9R77JDAUtHZgUJtpump"


def _row(mint: str, *, liquidity: str = "2000") -> dict:
    return {
        "id": mint,
        "liquidity": liquidity,
        "firstPool": {"createdAt": ANCHOR, "source": "pump.fun"},
        "first_seen_at": ANCHOR,
    }


def _phrase() -> str:
    return successor_phrase()


def _fixture(mints: tuple[str, ...] | list[str], *, order: Sequence[str] | None = None) -> dict:
    ordered = list(order or mints)
    return {
        "recent": [{"id": mint} for mint in ordered],
        "search": [_row(mint) for mint in ordered],
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


def _write_consumed_rdp(data_root: Path, extra_mint: str) -> None:
    from datetime import UTC, datetime

    now = datetime(2026, 8, 30, tzinfo=UTC)
    manifest_id = "DATASET-MANIFEST-PATHRISK-EXCLUSION-TEST-001"
    parquet_rel = f"datasets/parquet/{manifest_id}/mints.parquet"
    parquet_path = data_root / parquet_rel
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table({"mint": pa.array([extra_mint], type=pa.string())})
    pq.write_table(table, parquet_path)
    file_sha = hashlib.sha256(parquet_path.read_bytes()).hexdigest()
    fingerprint = "a" * 64
    dataset = DatasetManifest(
        dataset_manifest_id=manifest_id,
        dataset_id="DATASET-PATHRISK-EXCLUSION-TEST-001",
        dataset_version="1.0",
        schema_id="SCHEMA-PATHRISK-EXCLUSION-TEST-001",
        schema_sha256="b" * 64,
        dataset_fingerprint=fingerprint,
        generation_task_id="PATHRISK_LIVE_WINDOW_EXECUTION_GLUE_V1",
        generation_run_id="run-exclusion-test",
        validation_receipt_sha256="c" * 64,
        first_reliable_available_at=now,
        created_at=now,
        content_sha256="d" * 64,
    )
    partition = PartitionManifest(
        partition_manifest_id="PARTITION-PATHRISK-EXCLUSION-TEST-001",
        dataset_manifest_id=manifest_id,
        partition_id="mints",
        logical_location=parquet_rel.replace("\\", "/"),
        file_sha256=file_sha,
        content_sha256=file_sha,
        row_count=1,
        min_event_time=now,
        max_event_time=now,
        min_available_to_strategy_at=now,
        max_available_to_strategy_at=now,
        first_reliable_available_at=now,
        created_at=now,
    )
    manifests = data_root / "datasets" / "manifests"
    partitions = manifests / "partitions"
    manifests.mkdir(parents=True, exist_ok=True)
    partitions.mkdir(parents=True, exist_ok=True)
    (manifests / f"{manifest_id}.json").write_text(
        dataset.model_dump_json(), encoding="utf-8"
    )
    (partitions / f"{partition.partition_manifest_id}.json").write_text(
        partition.model_dump_json(), encoding="utf-8"
    )
    (manifests / f"{manifest_id}.decision.json").write_text(
        json.dumps({"outcome_consumed": True, "schema": "smial.runtime-receipt.v1"}),
        encoding="utf-8",
    )


class PathRiskLiveWindowTests(unittest.TestCase):
    def test_live_schedule_has_no_search_bundle_and_poll_disabled(self) -> None:
        schedule = compile_live_schedule(ROOT)
        self.assertIs(schedule["source_poll"]["enabled"], False)
        self.assertNotIn(FORBIDDEN_SEARCH_BUNDLE, schedule["x_point"]["bundle_ids"])
        self.assertNotIn(
            FORBIDDEN_SEARCH_BUNDLE,
            [bundle for point in schedule["y_points"] for bundle in point["bundle_ids"]],
        )
        self.assertEqual(int(schedule["budgets"]["provider_calls_lifetime_max"]), 26)
        self.assertIs(schedule["budgets"]["retry"], False)
        self.assertIs(schedule["budgets"]["fallback"], False)

    def test_t1_t2_t3_t8_t12_t14_t15_t17_t18_t20_happy_e2e(self) -> None:
        opener = FixtureWindowOpener(_fixture(MINTS, order=reversed(MINTS)))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            result = _run(data_root=data_root, opener=opener)
            kinds = count_url_kinds(result["urls"])
            self.assertEqual(kinds["recent"], 1)
            self.assertEqual(kinds["search"], 1)
            self.assertLessEqual(kinds["quotes"], 24)
            self.assertLessEqual(kinds["total"], 26)
            self.assertEqual(result["provider_calls"], kinds["total"])
            self.assertEqual(result["selected_mints"], list(MINTS))
            self.assertEqual(result["terminal"], TERMINAL_INFORMATIVE)
            self.assertTrue(result["build_readout_live_wired"])
            self.assertTrue(result["rdp_manifest_last"])
            self.assertTrue(result["evidence_epoch_changed"])
            self.assertIs(result["retry"], False)
            self.assertIs(result["fallback"], False)
            self.assertFalse(result["git_mutated"])
            self.assertTrue(all("api-key" not in url.lower() for url in result["urls"]))
            self.assertNotIn("feature_hint", result["readout"])
            labels = list((data_root / "datasets" / "manifests").glob("*.labels.json"))
            self.assertTrue(labels)
            payload = json.loads(labels[0].read_text(encoding="utf-8"))
            self.assertNotIn("feature_hint", payload)
            self.assertIs(payload["alpha_claim"], False)
            self.assertFalse(load_policy(ROOT)["external_authority"]["capture_authorized"])
            self.assertIn("NO_ALPHA", result["non_claims"])
            self.assertIn("PATHRISK_PROXY_NOT_PROFITABILITY", result["non_claims"])
            self.assertTrue(result["all_published_panels_labeled"])
            self.assertTrue((data_root / "pathrisk_live" / ACT_003 / "readout.json").is_file())
            self.assertGreaterEqual(
                len(result["readout"]["complete_dual_notional_mints"]), 3
            )
            quote_urls = [url for url in result["urls"] if "/swap/v2/order" in url]
            buys = [url for url in quote_urls if "inputMint=So11111111111111111111111111111111111111112" in url]
            sells = [url for url in quote_urls if "inputMint=So11111111111111111111111111111111111111112" not in url]
            self.assertEqual(len(buys), 8)
            self.assertEqual(len(sells), 16)
            self.assertTrue(all("11100000010" in url or "1110000001" in url for url in sells))

    def test_t4_exclusion_hash_changes_with_canonical_consumed_evidence(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            first = resolve_consumed_exclusions(
                repo_root=ROOT,
                data_root=data_root,
                policy=load_policy(ROOT),
                resolved_at=T0,
            )
            extra_mint = "ZzzzPathriskExclusionMint1111111111111111pump"
            extra = Path(tmp) / "extra_receipt.json"
            extra.write_text(
                json.dumps({"mint": extra_mint}),
                encoding="utf-8",
            )
            policy = dict(load_policy(ROOT))
            policy["consumed_mint_receipts"] = list(policy["consumed_mint_receipts"]) + [
                extra.relative_to(ROOT).as_posix()
                if extra.is_relative_to(ROOT)
                else str(extra)
            ]
            # Extra receipt lives outside the repo; resolver requires repo-relative paths.
            # Use RDP consumed evidence instead.
            _write_consumed_rdp(data_root, extra_mint)
            second = resolve_consumed_exclusions(
                repo_root=ROOT,
                data_root=data_root,
                policy=load_policy(ROOT),
                resolved_at=T0,
            )
            self.assertNotEqual(first["excluded_mints_sha256"], second["excluded_mints_sha256"])
            self.assertEqual(first["excluded_mints_sha256"], first["excluded_mints_sha256"])
            self.assertIn(extra_mint, second["mints"])
            self.assertGreater(second["excluded_mint_count"], first["excluded_mint_count"])
            self.assertEqual(len(first["excluded_mints_sha256"]), 64)

    def test_t5_consumed_mint_never_enters_selected_four(self) -> None:
        mints = (*MINTS, CONSUMED_PUMP)
        opener = FixtureWindowOpener(
            {
                "recent": [{"id": mint} for mint in (CONSUMED_PUMP, *reversed(MINTS))],
                "search": [_row(mint) for mint in mints],
            }
        )
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            result = _run(data_root=Path(tmp) / "rdp", opener=opener)
            self.assertNotIn(CONSUMED_PUMP, result["selected_mints"])
            self.assertEqual(result["selected_mints"], list(MINTS))

    def test_t6_order_is_mint_asc_not_discovery_order(self) -> None:
        policy = load_policy(ROOT)
        shuffled = [_row(mint) for mint in reversed(MINTS)]
        sample = select_r0_sample(shuffled, policy=policy, as_of=T0)
        self.assertEqual(sample["mints"], list(MINTS))

    def test_t7_below_floor_quote_calls_zero_e2e(self) -> None:
        three_plus_consumed = (*MINTS[:3], CONSUMED_PUMP)
        opener = FixtureWindowOpener(
            {
                "recent": [{"id": mint} for mint in three_plus_consumed],
                "search": [_row(mint) for mint in three_plus_consumed],
            }
        )
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            result = _run(data_root=data_root, opener=opener)
            self.assertEqual(result["terminal"], TERMINAL_BELOW_FLOOR)
            self.assertEqual(result["quote_calls"], 0)
            kinds = count_url_kinds(result["urls"])
            self.assertEqual(kinds["quotes"], 0)
            self.assertEqual(kinds["recent"], 1)
            self.assertEqual(kinds["search"], 1)
            self.assertGreater(result["provider_calls"], 0)
            self.assertFalse(result.get("evidence_epoch_changed"))
            self.assertFalse(list((data_root / "datasets" / "manifests").glob("*.labels.json")))

    def test_t9_t10_reverse_and_h900_bind_buy_out_amount(self) -> None:
        opener = FixtureWindowOpener(_fixture(MINTS))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            result = _run(data_root=Path(tmp) / "rdp", opener=opener)
            sells = [
                url
                for url in result["urls"]
                if "/swap/v2/order" in url
                and "inputMint=So11111111111111111111111111111111111111112" not in url
            ]
            self.assertTrue(sells)
            self.assertTrue(all("amount=11100000010" in url or "amount=1110000001" in url for url in sells))
            buys = [
                url
                for url in result["urls"]
                if "/swap/v2/order" in url
                and "inputMint=So11111111111111111111111111111111111111112" in url
            ]
            self.assertEqual(len(buys), 8)
            self.assertFalse(
                any("amount=11100000010" in url or "amount=1110000001" in url for url in buys)
            )

    def test_t11_hard_cap_includes_discovery(self) -> None:
        inner = FixtureWindowOpener(_fixture(MINTS))
        opener = HardCapOpener(inner, cap=2)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            with self.assertRaisesRegex(Exception, "CALL_CAP_26_EXCEEDED"):
                _run(data_root=Path(tmp) / "rdp", opener=opener)

    def test_t13_crash_resume_does_not_duplicate_recent_search_or_quotes(self) -> None:
        opener = FixtureWindowOpener(_fixture(MINTS))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            paused = _run(data_root=data_root, opener=opener, stop_after="after_recent")
            self.assertEqual(count_url_kinds(paused["urls"])["recent"], 1)
            self.assertEqual(count_url_kinds(paused["urls"])["search"], 0)
            after_search = _run(
                data_root=data_root, opener=opener, stop_after="after_search"
            )
            self.assertEqual(count_url_kinds(opener.urls)["recent"], 1)
            self.assertEqual(count_url_kinds(after_search["urls"])["search"], 1)
            mid_t0 = _run(data_root=data_root, opener=opener, stop_after="during_t0")
            self.assertEqual(mid_t0["terminal"], "STOPPED_DURING_T0")
            self.assertGreater(mid_t0["quote_calls"], 0)
            after_t0 = _run(data_root=data_root, opener=opener, stop_after="after_t0")
            self.assertEqual(count_url_kinds(opener.urls)["recent"], 1)
            self.assertEqual(count_url_kinds(opener.urls)["search"], 1)
            cumulative_quotes = len(
                [url for url in opener.urls if "/swap/v2/order" in url]
            )
            self.assertGreaterEqual(cumulative_quotes, mid_t0["quote_calls"])
            partial = _run(
                data_root=data_root, opener=opener, stop_after="during_h900"
            )
            done = _run(data_root=data_root, opener=opener)
            kinds = count_url_kinds(opener.urls)
            self.assertEqual(kinds["recent"], 1)
            self.assertEqual(kinds["search"], 1)
            self.assertLessEqual(kinds["quotes"], 24)
            self.assertLessEqual(kinds["total"], 26)
            self.assertLessEqual(done["provider_calls"], 26)
            self.assertEqual(done["terminal"], TERMINAL_INFORMATIVE)
            self.assertIsNotNone(partial["terminal"])

    def test_t16_live_typed_terminals_are_not_alpha(self) -> None:
        degenerate = dict(_fixture(MINTS))
        degenerate["mode"] = "degenerate"
        missing = dict(_fixture(MINTS))
        missing["mode"] = "h900_missing"
        invalid = dict(_fixture(MINTS))
        invalid["mode"] = "invalid_schema"
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root_tmp = Path(tmp)
            deg = _run(
                data_root=root_tmp / "deg",
                opener=FixtureWindowOpener(degenerate),
            )
            self.assertEqual(deg["terminal"], TERMINAL_DEGENERATE)
            self.assertIn("NO_ALPHA", deg["non_claims"])
            self.assertNotEqual(deg["terminal"], TERMINAL_INFORMATIVE)
            part = _run(
                data_root=root_tmp / "part",
                opener=FixtureWindowOpener(missing),
            )
            self.assertEqual(part["terminal"], TERMINAL_PARTIAL)
            self.assertNotEqual(part["terminal"], TERMINAL_INFORMATIVE)
            inv = _run(
                data_root=root_tmp / "inv",
                opener=FixtureWindowOpener(invalid),
            )
            self.assertEqual(inv["terminal"], TERMINAL_INVALID)
            self.assertNotEqual(inv["terminal"], TERMINAL_INFORMATIVE)

    def test_live_run_cli_uses_fixture_only(self) -> None:
        import subprocess

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            fixture_path = Path(tmp) / "fixture.json"
            fixture_path.write_text(json.dumps(_fixture(MINTS[:3])), encoding="utf-8")
            data_root = Path(tmp) / "rdp"
            ensure_act002_below_floor(data_root)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts" / "early_quote_surface_pathrisk_calibration.py"),
                    "live-run",
                    "--main-sha",
                    MAIN_SHA,
                    "--owner-phrase",
                    _phrase(),
                    "--data-root",
                    str(data_root),
                    "--producer-git-sha",
                    GIT_SHA,
                    "--activation-id",
                    ACT_003,
                    "--predecessor-activation-id",
                    "ACT-PATHRISK-LIVE-002",
                    "--fake-provider-fixture",
                    str(fixture_path),
                    "--now",
                    "2026-09-01T00:10:00Z",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["terminal"], TERMINAL_BELOW_FLOOR)
            self.assertEqual(payload["quote_calls"], 0)


if __name__ == "__main__":
    unittest.main()
