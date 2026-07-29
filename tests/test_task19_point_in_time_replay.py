from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.jupiter_quote_logger import USDC_MINT
from solana_alpha_lab.task17a_execution_capacity_panel import SELECTED_MINT
from solana_alpha_lab.task19_point_in_time_replay import (
    Task19ReplayError,
    audit_point_in_time_replay,
    build_lineage_projection,
    canonical_json_bytes,
    load_frozen_contract,
    replay_rows,
    run_adversarial_suite,
)

CONTRACT_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task19"
    / "point_in_time_replay_contract_v1.json"
)
EVIDENCE_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task19"
    / "point_in_time_replay_v1.json"
)
SUMMARY_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task19"
    / "point_in_time_replay_summary_v1.md"
)
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
TASK18_PATH = ROOT / next(
    row["path"]
    for row in CONTRACT["tracked_inputs"]
    if row["asset_id"] == "FIXTURE-T18-NARROW-DATA-QUALITY-001"
)
TASK18_CONTRACT = json.loads(TASK18_PATH.read_text(encoding="utf-8"))
RAW_EVIDENCE_AVAILABLE = all(
    (ROOT / row["path"]).is_file()
    for row in TASK18_CONTRACT["raw_inventory"]["files"]
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _times() -> tuple[str, ...]:
    return (
        "2026-07-29T13:00:00.000001Z",
        "2026-07-29T13:00:00.000002Z",
        "2026-07-29T13:00:00.000003Z",
        "2026-07-29T13:00:00.000004Z",
        "2026-07-29T13:00:00.000005Z",
    )


def synthetic_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    windows = [
        *CONTRACT["membership"]["accepted_window_order"],
        CONTRACT["membership"]["excluded_window_id"],
    ]
    cost_bps = (100, 200, 300, 400)
    notionals = CONTRACT["pairing"]["notionals_usd"]
    for window_index, window_id in enumerate(windows, start=1):
        for pair_index, (notional, cost) in enumerate(
            zip(notionals, cost_bps),
            start=1,
        ):
            notional_atomic = notional * 1_000_000
            buy_output = notional_atomic * 10_000 + window_index
            sell_output = notional_atomic * (10_000 - cost) // 10_000
            for side_index, side in enumerate(("BUY", "SELL")):
                ordinal = (pair_index - 1) * 2 + side_index + 1
                suffix = f"{window_index}-{ordinal}"
                request_hash = hashlib.sha256(
                    f"request-{suffix}".encode()
                ).hexdigest()
                content_hash = hashlib.sha256(
                    f"content-{suffix}".encode()
                ).hexdigest()
                quote_id = f"quote-{suffix}"
                raw_id = f"raw-{suffix}"
                idempotency_key = f"idem-{suffix}"
                requested, response, first, available, ingested = _times()
                quote = {
                    "quote_attempt_id": quote_id,
                    "raw_event_id": raw_id,
                    "request_hash": request_hash,
                    "idempotency_key": idempotency_key,
                    "response_content_sha256": content_hash,
                    "revision_number": 1,
                    "revision_of": None,
                    "side": side,
                    "input_mint": USDC_MINT if side == "BUY" else SELECTED_MINT,
                    "output_mint": (
                        SELECTED_MINT if side == "BUY" else USDC_MINT
                    ),
                    "input_requested_atomic": (
                        notional_atomic if side == "BUY" else buy_output
                    ),
                    "output_quoted_atomic": (
                        buy_output if side == "BUY" else sell_output
                    ),
                    "requested_at": requested,
                    "response_at": response,
                    "first_reliable_available_at": first,
                    "available_to_strategy_at": available,
                    "ingested_at": ingested,
                }
                raw = {
                    "raw_event_id": raw_id,
                    "request_hash": request_hash,
                    "idempotency_key": f"raw-idem-{suffix}",
                    "content_sha256": content_hash,
                    "revision_number": 1,
                    "revision_of": None,
                    "requested_at": requested,
                    "response_at": response,
                    "first_reliable_available_at": first,
                    "available_to_strategy_at": available,
                    "ingested_at": ingested,
                }
                rows.append(
                    {
                        "hypothesis_version_id": CONTRACT["estimand"][
                            "hypothesis_version_id"
                        ],
                        "watchlist_id": CONTRACT["estimand"]["watchlist_id"],
                        "watchlist_version": CONTRACT["estimand"][
                            "watchlist_version"
                        ],
                        "window_id": window_id,
                        "member_id": CONTRACT["estimand"]["member_ids"][0],
                        "call_ordinal": ordinal,
                        "request_hash": request_hash,
                        "idempotency_key": idempotency_key,
                        "raw_content_sha256": content_hash,
                        "requested_at": requested,
                        "response_at": response,
                        "first_reliable_available_at": first,
                        "available_to_strategy_at": available,
                        "ingested_at": ingested,
                        "quote_attempt": quote,
                        "raw_event": raw,
                    }
                )
    return rows


class Task19PointInTimeReplayTests(unittest.TestCase):
    def test_frozen_contract_is_exact_and_uses_literal_cutoffs(self) -> None:
        contract = load_frozen_contract(CONTRACT_PATH)
        self.assertEqual(
            contract["time_contract"]["cutoff_source"],
            "FROZEN_LITERAL_NOT_RUNTIME_MAXIMUM",
        )
        self.assertFalse(
            contract["time_contract"]["runtime_cutoff_extension_allowed"]
        )

    def test_synthetic_replay_is_shuffle_deterministic(self) -> None:
        rows = synthetic_rows()
        first = replay_rows(rows, CONTRACT, enforce_expected=False)
        second = replay_rows(
            list(reversed(rows)),
            CONTRACT,
            enforce_expected=False,
        )
        self.assertEqual(
            hashlib.sha256(canonical_json_bytes(first)).hexdigest(),
            hashlib.sha256(canonical_json_bytes(second)).hexdigest(),
        )
        self.assertEqual(first["accepted_rows"], 24)
        self.assertEqual(first["excluded_retained_rows"], 8)
        self.assertEqual(first["complete_quote_pairs"], 12)

    def test_lineage_projection_binds_every_attempt_and_exclusion(self) -> None:
        lineage = build_lineage_projection(synthetic_rows(), CONTRACT)
        attempts = lineage["attempts"]
        self.assertEqual(len(attempts), 32)
        accepted = [
            row for row in attempts if row["classification"] == "ACCEPTED"
        ]
        excluded = [
            row
            for row in attempts
            if row["classification"] == "EXCLUDED_RETAINED"
        ]
        self.assertEqual((len(accepted), len(excluded)), (24, 8))
        self.assertTrue(all(row["eligible_at_decision"] for row in accepted))
        self.assertTrue(
            all(not row["eligible_at_decision"] for row in excluded)
        )
        self.assertTrue(
            all(
                len(row["raw_content_sha256"]) == 64
                and row["quote_attempt_id"]
                and row["raw_event_id"]
                for row in attempts
            )
        )

    def test_all_ten_adversarial_vectors_pass_without_raw_workspace(
        self,
    ) -> None:
        probe = b"frozen-physical-probe"
        checks = run_adversarial_suite(
            synthetic_rows(),
            CONTRACT,
            physical_probe=(
                probe,
                len(probe),
                hashlib.sha256(probe).hexdigest(),
            ),
        )
        self.assertEqual(len(checks), 10)
        self.assertEqual(
            {row["vector_id"] for row in checks},
            {
                row["vector_id"]
                for row in CONTRACT["adversarial_vectors"]
            },
        )
        self.assertTrue(all(row["status"] == "PASS" for row in checks))

    def test_duplicate_missing_time_and_incomplete_pair_fail_closed(
        self,
    ) -> None:
        mutations = []
        duplicate = synthetic_rows()
        duplicate.append(copy.deepcopy(duplicate[0]))
        mutations.append(duplicate)
        missing = synthetic_rows()
        missing[0].pop("first_reliable_available_at")
        mutations.append(missing)
        incomplete = synthetic_rows()
        incomplete.pop(1)
        mutations.append(incomplete)
        for rows in mutations:
            with self.subTest(rows=len(rows)):
                with self.assertRaises(Task19ReplayError) as raised:
                    replay_rows(rows, CONTRACT, enforce_expected=False)
                self.assertEqual(
                    raised.exception.verdict,
                    "EVIDENCE_UNAVAILABLE",
                )

    def test_missing_workspace_fails_closed_before_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            receipt = audit_point_in_time_replay(
                repository_root=Path(directory),
                contract_path=CONTRACT_PATH,
            )
        self.assertEqual(receipt["verdict"], "EVIDENCE_UNAVAILABLE")
        self.assertFalse(receipt["claims"]["point_in_time_replay_safe"])
        self.assertGreater(len(receipt["failures"]), 0)
        self.assertNotIn("replay_output", receipt)

    @unittest.skipUnless(
        RAW_EVIDENCE_AVAILABLE,
        "ignored TASK-17A raw evidence is unavailable in clean clone",
    )
    def test_actual_raw_replay_is_safe_and_matches_tracked_receipt(self) -> None:
        receipt = audit_point_in_time_replay(
            repository_root=ROOT,
            contract_path=CONTRACT_PATH,
        )
        self.assertEqual(receipt["verdict"], "REPLAY_SAFE")
        self.assertEqual(receipt["failures"], [])
        self.assertEqual(receipt["limitations"], [])
        self.assertEqual(
            receipt["replay_output"],
            CONTRACT["expected_output"],
        )
        lineage = receipt["lineage_projection"]
        self.assertEqual(len(lineage["attempts"]), 32)
        self.assertEqual(
            receipt["lineage_projection_sha256"],
            hashlib.sha256(canonical_json_bytes(lineage)).hexdigest(),
        )
        self.assertEqual(
            lineage["hypothesis_version_id"],
            CONTRACT["estimand"]["hypothesis_version_id"],
        )
        self.assertEqual(
            sum(
                row["status"] == "PASS"
                for row in receipt["adversarial_checks"]
            ),
            10,
        )
        tracked = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(receipt, tracked)
        self.assertIn(sha256(EVIDENCE_PATH), SUMMARY_PATH.read_text("utf-8"))

    @unittest.skipUnless(
        RAW_EVIDENCE_AVAILABLE,
        "ignored TASK-17A raw evidence is unavailable in clean clone",
    )
    def test_replay_does_not_mutate_frozen_raw(self) -> None:
        before = {
            row["path"]: sha256(ROOT / row["path"])
            for row in TASK18_CONTRACT["raw_inventory"]["files"]
        }
        audit_point_in_time_replay(
            repository_root=ROOT,
            contract_path=CONTRACT_PATH,
        )
        after = {
            row["path"]: sha256(ROOT / row["path"])
            for row in TASK18_CONTRACT["raw_inventory"]["files"]
        }
        self.assertEqual(before, after)

    @unittest.skipUnless(
        RAW_EVIDENCE_AVAILABLE,
        "ignored TASK-17A raw evidence is unavailable in clean clone",
    )
    def test_authority_receipt_stays_zero_side_effect(self) -> None:
        receipt = audit_point_in_time_replay(
            repository_root=ROOT,
            contract_path=CONTRACT_PATH,
        )
        self.assertTrue(all(value == 0 for value in receipt["authority"].values()))
        self.assertEqual(
            receipt["next_gate"],
            {
                "atom_id": "T19-A4_CATALOG_REPOSITORY_FINALIZATION_V1",
                "status": "NOT_AUTHORIZED_BY_T19_A3",
            },
        )


if __name__ == "__main__":
    unittest.main()
