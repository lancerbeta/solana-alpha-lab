from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.delivery_tracked_hash import sha256_tracked_path
from solana_alpha_lab.factory.capabilities import capture_quote_native_free_key
from solana_alpha_lab.factory.experiment_spec import load_experiment_spec
from solana_alpha_lab.factory.quote_surface_retention import (
    apply_quote_surface_retention_to_receipt,
    load_quote_surface_retention_rule,
    score_retention_observations,
)
from solana_alpha_lab.factory.quote_surface_retention_clock import (
    CLOCK_INVALID,
    CLOCK_UNKNOWN,
    CLOCK_VALID,
    QuoteSurfaceRetentionClockError,
    clock_metadata_from_observation,
    evaluate_observation_clock,
    evaluate_retention_cell_clock,
    qualify_clock_from_consumed_receipt,
)

CONSUMED_RECEIPT = (
    ROOT
    / "docs/evidence/quote_surface_retention_falsifier"
    / "a1_quote_surface_retention_falsifier_runtime_receipt_v1.json"
)
ACCEPTANCE = (
    ROOT
    / "docs/evidence/quote_surface_retention_falsifier"
    / "a1_quote_surface_retention_falsifier_acceptance_v1.json"
)
QUALIFICATION = (
    ROOT
    / "docs/evidence/quote_surface_retention_clock_qualify"
    / "q1_engineering_qualification_v1.json"
)

H900_DUE = "2026-08-19T12:15:00Z"
H3600_DUE = "2026-08-19T13:00:00Z"


def _clock_counts(cells: list[dict[str, object]]) -> dict[str, int]:
    recent_valid = 0
    traded_valid = 0
    invalid_n = 0
    unknown_n = 0
    for cell in cells:
        status = str(cell.get("clock_status") or "")
        stratum = str(cell.get("stratum") or "")
        if status == CLOCK_VALID and stratum == "RECENT":
            recent_valid += 1
        elif status == CLOCK_VALID and stratum == "TRADED":
            traded_valid += 1
        elif status == CLOCK_INVALID:
            invalid_n += 1
        else:
            unknown_n += 1
    return {
        "recent_clock_valid_n": recent_valid,
        "traded_clock_valid_n": traded_valid,
        "clock_invalid_n": invalid_n,
        "clock_unknown_n": unknown_n,
    }


def _meta(
    *,
    kind: str,
    terminal: str = "QUOTE_OBSERVED",
    due_at: str | None = None,
    observed_at: str | None = None,
    slack: int = 120,
) -> dict[str, object]:
    row: dict[str, object] = {
        "identity_id": "CELL_0",
        "kind": kind,
        "terminal": terminal,
        "lateness_slack_seconds": slack,
        "horizon_seconds": 900 if kind == "REVERSE_H900" else 3600,
    }
    if due_at is not None:
        row["due_at"] = due_at
    if observed_at is not None:
        row["observed_at"] = observed_at
    return row


class QuoteSurfaceRetentionClockTests(unittest.TestCase):
    def test_same_value_different_valid_clock_is_valid(self) -> None:
        status = evaluate_observation_clock(
            _meta(kind="REVERSE_H900", due_at=H900_DUE, observed_at=H900_DUE),
            _meta(kind="SELL_H3600", due_at=H3600_DUE, observed_at=H3600_DUE),
        )
        self.assertEqual(status, CLOCK_VALID)

    def test_different_value_same_clock_is_invalid(self) -> None:
        status = evaluate_observation_clock(
            _meta(kind="REVERSE_H900", due_at=H900_DUE, observed_at=H900_DUE),
            _meta(kind="SELL_H3600", due_at=H900_DUE, observed_at=H900_DUE),
        )
        self.assertEqual(status, CLOCK_INVALID)

    def test_same_due_different_observed_at_is_invalid(self) -> None:
        later = (
            datetime.fromisoformat(H900_DUE.replace("Z", "+00:00")) + timedelta(seconds=3)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        status = evaluate_observation_clock(
            _meta(kind="REVERSE_H900", due_at=H900_DUE, observed_at=H900_DUE),
            _meta(kind="SELL_H3600", due_at=H900_DUE, observed_at=later),
        )
        self.assertEqual(status, CLOCK_INVALID)

    def test_buy_h900_outside_window_makes_cell_invalid(self) -> None:
        late_buy = (
            datetime.fromisoformat(H900_DUE.replace("Z", "+00:00")) + timedelta(seconds=121)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        status = evaluate_retention_cell_clock(
            _meta(kind="BUY_H900", due_at=H900_DUE, observed_at=late_buy),
            _meta(kind="REVERSE_H900", due_at=H900_DUE, observed_at=H900_DUE),
            _meta(kind="SELL_H3600", due_at=H3600_DUE, observed_at=H3600_DUE),
        )
        self.assertEqual(status, CLOCK_INVALID)

    def test_h3600_before_h900_is_invalid(self) -> None:
        status = evaluate_observation_clock(
            _meta(kind="REVERSE_H900", due_at=H3600_DUE, observed_at=H3600_DUE),
            _meta(kind="SELL_H3600", due_at=H900_DUE, observed_at=H900_DUE),
        )
        self.assertEqual(status, CLOCK_INVALID)

    def test_outside_observation_window_is_invalid(self) -> None:
        late = (
            datetime.fromisoformat(H3600_DUE.replace("Z", "+00:00")) + timedelta(seconds=121)
        ).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        status = evaluate_observation_clock(
            _meta(kind="REVERSE_H900", due_at=H900_DUE, observed_at=H900_DUE),
            _meta(kind="SELL_H3600", due_at=H3600_DUE, observed_at=late),
        )
        self.assertEqual(status, CLOCK_INVALID)

    def test_missing_timestamp_is_unknown(self) -> None:
        status = evaluate_observation_clock(
            _meta(kind="REVERSE_H900", due_at=H900_DUE, observed_at=H900_DUE),
            _meta(kind="SELL_H3600", due_at=H3600_DUE, observed_at=None),
        )
        self.assertEqual(status, CLOCK_UNKNOWN)

    def test_provider_400_is_unknown(self) -> None:
        status = evaluate_observation_clock(
            _meta(
                kind="REVERSE_H900",
                terminal="PROVIDER_TYPED_FAILURE",
                due_at=H900_DUE,
                observed_at=H900_DUE,
            ),
            _meta(kind="SELL_H3600", due_at=H3600_DUE, observed_at=H3600_DUE),
        )
        self.assertEqual(status, CLOCK_UNKNOWN)

    def test_clock_evaluator_rejects_quote_and_y_fields(self) -> None:
        leaked = _meta(kind="REVERSE_H900", due_at=H900_DUE, observed_at=H900_DUE)
        leaked["quote"] = {"out_amount": "9727186"}
        with self.assertRaisesRegex(QuoteSurfaceRetentionClockError, "CLOCK_METADATA_LEAK"):
            evaluate_observation_clock(
                leaked,
                _meta(kind="SELL_H3600", due_at=H3600_DUE, observed_at=H3600_DUE),
            )

    def test_equal_out_amount_scored_cell_is_clock_valid(self) -> None:
        h900_obs = "2026-08-19T21:42:14Z"
        h3600_obs = "2026-08-19T22:27:13Z"
        observations = [
            {
                "identity_id": "RECENT_1",
                "kind": "BUY_T0",
                "terminal": "QUOTE_OBSERVED",
                "amount": "10000000",
                "quote": {"out_amount": "10000000"},
                "observed_at": "2026-08-19T21:27:13Z",
                "due_at": "2026-08-19T21:27:10Z",
                "lateness_slack_seconds": 120,
            },
            {
                "identity_id": "RECENT_1",
                "kind": "REVERSE_T0",
                "terminal": "QUOTE_OBSERVED",
                "amount": "10000000",
                "quote": {"out_amount": "9727186"},
                "observed_at": "2026-08-19T21:27:16Z",
                "due_at": "2026-08-19T21:27:10Z",
                "lateness_slack_seconds": 120,
            },
            {
                "identity_id": "RECENT_1",
                "kind": "BUY_H900",
                "terminal": "QUOTE_OBSERVED",
                "amount": "10000000",
                "quote": {"out_amount": "10000000"},
                "observed_at": h900_obs,
                "due_at": "2026-08-19T21:42:10Z",
                "lateness_slack_seconds": 120,
            },
            {
                "identity_id": "RECENT_1",
                "kind": "REVERSE_H900",
                "terminal": "QUOTE_OBSERVED",
                "amount": "10000000",
                "quote": {"out_amount": "9727186"},
                "observed_at": h900_obs,
                "due_at": "2026-08-19T21:42:10Z",
                "lateness_slack_seconds": 120,
            },
            {
                "identity_id": "RECENT_1",
                "kind": "SELL_H3600",
                "terminal": "QUOTE_OBSERVED",
                "amount": "10000000",
                "quote": {"out_amount": "9727186"},
                "observed_at": h3600_obs,
                "due_at": "2026-08-19T22:27:10Z",
                "lateness_slack_seconds": 120,
            },
        ]
        scored = score_retention_observations(
            observations,
            frozen_cells=[{"identity_id": "RECENT_1", "stratum": "RECENT"}],
        )
        cell = scored["cells"][0]
        self.assertEqual(cell["clock_status"], CLOCK_VALID)
        self.assertTrue(cell["time_separated"])
        self.assertEqual(cell["forward_quoted_return_h900_h3600"], "-0.0272814")

    def test_different_out_amount_same_clock_is_not_time_separated(self) -> None:
        same_clock = H900_DUE
        observations = [
            {
                "identity_id": "CELL_0",
                "kind": "BUY_T0",
                "terminal": "QUOTE_OBSERVED",
                "amount": "10000000",
                "quote": {"out_amount": "10000000"},
                "observed_at": same_clock,
                "due_at": H900_DUE,
                "lateness_slack_seconds": 120,
            },
            {
                "identity_id": "CELL_0",
                "kind": "REVERSE_T0",
                "terminal": "QUOTE_OBSERVED",
                "amount": "10000000",
                "quote": {"out_amount": "9000000"},
                "observed_at": same_clock,
                "due_at": H900_DUE,
                "lateness_slack_seconds": 120,
            },
            {
                "identity_id": "CELL_0",
                "kind": "BUY_H900",
                "terminal": "QUOTE_OBSERVED",
                "amount": "10000000",
                "quote": {"out_amount": "10000000"},
                "observed_at": same_clock,
                "due_at": H900_DUE,
                "lateness_slack_seconds": 120,
            },
            {
                "identity_id": "CELL_0",
                "kind": "REVERSE_H900",
                "terminal": "QUOTE_OBSERVED",
                "amount": "10000000",
                "quote": {"out_amount": "9000000"},
                "observed_at": same_clock,
                "due_at": H900_DUE,
                "lateness_slack_seconds": 120,
            },
            {
                "identity_id": "CELL_0",
                "kind": "SELL_H3600",
                "terminal": "QUOTE_OBSERVED",
                "amount": "10000000",
                "quote": {"out_amount": "8000000"},
                "observed_at": same_clock,
                "due_at": H900_DUE,
                "lateness_slack_seconds": 120,
            },
        ]
        scored = score_retention_observations(
            observations,
            frozen_cells=[{"identity_id": "CELL_0", "stratum": "RECENT"}],
        )
        cell = scored["cells"][0]
        self.assertEqual(cell["clock_status"], CLOCK_INVALID)
        self.assertFalse(cell["time_separated"])
        self.assertIsNotNone(cell["forward_quoted_return_h900_h3600"])
        self.assertNotEqual(cell["forward_quoted_return_h900_h3600"], "0")

    def test_h3600_no_route_with_valid_clocks_is_path_risk(self) -> None:
        observations = [
            {
                "identity_id": "CELL_0",
                "kind": "BUY_T0",
                "terminal": "QUOTE_OBSERVED",
                "amount": "10000000",
                "quote": {"out_amount": "10000000"},
                "observed_at": "2026-08-19T12:00:00Z",
                "due_at": "2026-08-19T12:00:00Z",
                "lateness_slack_seconds": 120,
            },
            {
                "identity_id": "CELL_0",
                "kind": "REVERSE_T0",
                "terminal": "QUOTE_OBSERVED",
                "amount": "10000000",
                "quote": {"out_amount": "9000000"},
                "observed_at": "2026-08-19T12:00:03Z",
                "due_at": "2026-08-19T12:00:00Z",
                "lateness_slack_seconds": 120,
            },
            {
                "identity_id": "CELL_0",
                "kind": "BUY_H900",
                "terminal": "QUOTE_OBSERVED",
                "amount": "10000000",
                "quote": {"out_amount": "10000000"},
                "observed_at": H900_DUE,
                "due_at": H900_DUE,
                "lateness_slack_seconds": 120,
            },
            {
                "identity_id": "CELL_0",
                "kind": "REVERSE_H900",
                "terminal": "QUOTE_OBSERVED",
                "amount": "10000000",
                "quote": {"out_amount": "9000000"},
                "observed_at": H900_DUE,
                "due_at": H900_DUE,
                "lateness_slack_seconds": 120,
            },
            {
                "identity_id": "CELL_0",
                "kind": "SELL_H3600",
                "terminal": "NO_ROUTE",
                "amount": "10000000",
                "quote": None,
                "observed_at": H3600_DUE,
                "due_at": H3600_DUE,
                "lateness_slack_seconds": 120,
            },
        ]
        scored = score_retention_observations(
            observations,
            frozen_cells=[{"identity_id": "CELL_0", "stratum": "RECENT"}],
        )
        cell = scored["cells"][0]
        self.assertEqual(cell["clock_status"], CLOCK_VALID)
        self.assertTrue(cell["time_separated"])
        self.assertEqual(cell["y_status"], "PATH_RISK")
        self.assertIsNone(cell["forward_quoted_return_h900_h3600"])

    def test_consumed_156_replay_is_qualification_only(self) -> None:
        receipt = json.loads(CONSUMED_RECEIPT.read_text(encoding="utf-8"))
        acceptance = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
        packet = qualify_clock_from_consumed_receipt(receipt)
        scored = score_retention_observations(
            receipt["observations"],
            frozen_cells=list(receipt.get("frozen_cells") or []),
        )
        projector_counts = _clock_counts(scored["cells"])
        self.assertEqual(packet["evidence_class"], "ENGINEERING_QUALIFICATION_ONLY")
        self.assertIs(packet["scientific_reclassification"], False)
        self.assertIs(packet["confirmation_eligible"], False)
        self.assertEqual(packet["provider_api_rpc_wss_calls"], 0)
        self.assertNotIn("terminal", packet)
        self.assertNotIn("median_y_kept", packet)
        self.assertNotIn("p90_y_kept", packet)
        self.assertEqual(packet["recent_clock_valid_n"], 5)
        self.assertEqual(packet["traded_clock_valid_n"], 6)
        self.assertEqual(packet["clock_unknown_n"], 1)
        self.assertEqual(packet["clock_invalid_n"], 0)
        self.assertEqual(projector_counts, {
            "recent_clock_valid_n": 5,
            "traded_clock_valid_n": 6,
            "clock_invalid_n": 0,
            "clock_unknown_n": 1,
        })
        for cell in scored["cells"]:
            self.assertEqual(cell["time_separated"], cell["clock_status"] == CLOCK_VALID)
        self.assertEqual(acceptance["owner_decision"], "SAMPLE_INVALID_REPLAN_REQUIRED")
        self.assertEqual(acceptance["criteria"]["recent_valid_n"], 0)
        self.assertEqual(acceptance["criteria"]["traded_valid_n"], 6)
        before = CONSUMED_RECEIPT.read_bytes()
        naive = apply_quote_surface_retention_to_receipt(
            receipt,
            rule=load_quote_surface_retention_rule(ROOT, "configs/quote_surface_retention_rule_v1.yaml"),
        )
        self.assertEqual(CONSUMED_RECEIPT.read_bytes(), before)
        self.assertEqual(naive["terminal"], "CLOSE_EXACT_QUOTE_SURFACE_RETENTION_FAMILY")
        self.assertEqual(naive["retention"]["recent_valid_n"], 5)
        self.assertEqual(naive["retention"]["traded_valid_n"], 6)
        recorded = json.loads(QUALIFICATION.read_text(encoding="utf-8"))
        self.assertEqual(recorded["evidence_class"], "ENGINEERING_QUALIFICATION_ONLY")
        self.assertNotIn("terminal", recorded)
        self.assertNotIn("median_y_kept", recorded)
        self.assertNotIn("p90_y_kept", recorded)
        self.assertNotIn("pr_156_scientific_terminal_unchanged", recorded)
        self.assertNotEqual(recorded.get("next_boundary"), naive["terminal"])
        self.assertEqual(recorded["clock_counts"]["recent_clock_valid_n"], packet["recent_clock_valid_n"])
        self.assertEqual(recorded["clock_counts"]["traded_clock_valid_n"], packet["traded_clock_valid_n"])
        self.assertEqual(recorded["clock_counts"]["clock_unknown_n"], packet["clock_unknown_n"])
        self.assertEqual(len(recorded["consumed_mints"]), 12)
        self.assertEqual(
            recorded["consumed_runtime_sha256"],
            sha256_tracked_path(
                ROOT,
                "docs/evidence/quote_surface_retention_falsifier/"
                "a1_quote_surface_retention_falsifier_runtime_receipt_v1.json",
            ),
        )

    def test_factory_overlay_does_not_rescore_consumed_156_terminal(self) -> None:
        spec = load_experiment_spec(
            ROOT,
            "configs/experiment_specs/quote_surface_retention_falsifier_v1.yaml",
        )
        result = capture_quote_native_free_key(spec, root=ROOT)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["terminal"], "SAMPLE_INVALID_REPLAN_REQUIRED")

    def test_clock_metadata_strip_allows_raw_rows_into_factory(self) -> None:
        raw = {
            "identity_id": "RECENT_1",
            "kind": "REVERSE_H900",
            "terminal": "QUOTE_OBSERVED",
            "due_at": H900_DUE,
            "observed_at": H900_DUE,
            "lateness_slack_seconds": 120,
            "horizon_seconds": 900,
            "quote": {"out_amount": "9727186"},
            "amount": "10000000",
        }
        stripped = clock_metadata_from_observation(raw)
        self.assertNotIn("quote", stripped)
        self.assertEqual(
            evaluate_observation_clock(
                stripped,
                _meta(kind="SELL_H3600", due_at=H3600_DUE, observed_at=H3600_DUE),
            ),
            CLOCK_VALID,
        )

    def test_tracked_hash_uses_git_blob_not_crlf_working_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "clock@example.test"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "clock"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "core.autocrlf", "false"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            relative = "docs/note.json"
            path = repo / relative
            path.parent.mkdir(parents=True)
            lf = b'{"ok":true}\n'
            path.write_bytes(lf)
            subprocess.run(["git", "add", relative], cwd=repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "note"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            path.write_bytes(b'{"ok":true}\r\n')
            tracked = sha256_tracked_path(repo, relative)
            blob = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=repo)
            self.assertEqual(tracked, hashlib.sha256(blob).hexdigest())
            self.assertNotEqual(tracked, hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
