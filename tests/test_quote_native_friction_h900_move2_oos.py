from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.quote_native_admissible_friction_audition import (  # noqa: E402
    attempt_reservation_document,
    capture_envelope,
)
from solana_alpha_lab.quote_native_friction_h900_move2_oos import (  # noqa: E402
    A1_RUNTIME_SHA256,
    AUTHORITY_PHRASE,
    COHORT_SNAPSHOT_NAME,
    Move2Error,
    attach_lineage_to_git_receipt,
    classify_move2_terminal,
    family_closed,
    filter_discovery_payload,
    load_cohort_snapshot,
    load_exclusion_set,
    receipt_from_incomplete_local_run,
    select_cohort_excluding_a1,
    validate_policy,
    write_cohort_snapshot,
)


A1_RUNTIME_PATH = (
    ROOT
    / "docs/evidence/quote_native_admissible_friction_audition"
    / "a1_quote_native_admissible_friction_audition_runtime_receipt_v1.json"
)
RUNTIME_PATH = (
    ROOT
    / "docs/evidence/quote_native_friction_h900_move2_oos"
    / "a1_quote_native_friction_h900_move2_oos_runtime_receipt_v1.json"
)
ACCEPTANCE_PATH = (
    ROOT
    / "docs/evidence/quote_native_friction_h900_move2_oos"
    / "a1_quote_native_friction_h900_move2_oos_acceptance_v1.json"
)
CONFIG_PATH = ROOT / "configs/quote_native_friction_h900_move2_oos_v1.yaml"
RUNTIME_SHA256 = "a860888cd6c528c03cffb27146d07da6ed60770d0f1e13d47651b0d63f51b926"
ACCEPTANCE_SHA256 = "466e4fcc0738da51088f12155e3319f2064488edce95a11fe3fd459694470e31"


class _Response:
    def __init__(self, body: bytes, *, status: int, headers: dict[str, str]) -> None:
        self._body = io.BytesIO(body)
        self._status = status
        self.headers = headers

    def getcode(self) -> int:
        return self._status

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _SequenceOpener:
    def __init__(self, responses: list[_Response]) -> None:
        self.responses = list(responses)
        self.requests: list[object] = []

    def open(self, request: object, timeout: float = 0) -> _Response:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("unexpected provider request")
        return self.responses.pop(0)


class _Clock:
    def __init__(self, start: datetime) -> None:
        self.started = start
        self.current = start
        self.sleeps: list[float] = []

    def __call__(self) -> datetime:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += timedelta(seconds=seconds)


def _policy() -> dict[str, Any]:
    loaded = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _excluded_mints() -> list[str]:
    exclusion = load_exclusion_set(ROOT, _policy())
    return list(exclusion["excluded_mints"])


def _token_rows(prefix: str, *, extra: list[str] | None = None) -> bytes:
    payload = []
    for mint in extra or []:
        payload.append(
            {
                "id": mint,
                "liquidity": 2_000,
                "firstPool": {"createdAt": "2026-08-18T00:00:00Z"},
            }
        )
    payload.extend(
        {
            "id": f"{prefix}{index:02d}111111111111111111111111111111111",
            "liquidity": 2_000,
            "firstPool": {"createdAt": f"2026-08-18T00:{index:02d}:00Z"},
        }
        for index in range(1, 7)
    )
    return json.dumps(payload).encode("utf-8")


def _quote_body(amount: str, *, out_amount: str) -> bytes:
    return json.dumps(
        {
            "transaction": None,
            "requestId": "request-1",
            "inAmount": amount,
            "outAmount": out_amount,
            "router": "metis",
            "mode": "manual",
            "priceImpactPct": "0.01",
            "platformFee": None,
            "feeBps": "1",
            "routePlan": [],
        }
    ).encode("utf-8")


def _quote_sequence(
    *,
    reverse_out: list[str],
    sell_out: list[str],
    h3600_out: list[str],
    recent_extra: list[str] | None = None,
    traded_extra: list[str] | None = None,
) -> list[_Response]:
    buy_out = "10000000"
    responses = [
        _Response(_token_rows("Recent", extra=recent_extra), status=200, headers={}),
        _Response(_token_rows("Traded", extra=traded_extra), status=200, headers={}),
    ]
    for index in range(12):
        responses.append(_Response(_quote_body("10000000", out_amount=buy_out), status=200, headers={}))
        responses.append(
            _Response(_quote_body(buy_out, out_amount=reverse_out[index]), status=200, headers={})
        )
    for index in range(12):
        responses.append(_Response(_quote_body(buy_out, out_amount=sell_out[index]), status=200, headers={}))
    for index in range(12):
        responses.append(_Response(_quote_body(buy_out, out_amount=h3600_out[index]), status=200, headers={}))
    return responses


def _run_capture(responses: list[_Response], *, directory: Path) -> dict[str, Any]:
    from scripts.run_quote_native_friction_h900_move2_oos import run_capture

    clock = _Clock(datetime(2026, 8, 19, 12, 0, tzinfo=UTC))
    return run_capture(
        authority_phrase=AUTHORITY_PHRASE,
        policy=_policy(),
        raw_root=directory / "raw",
        receipt_path=directory / "runtime.json",
        environ={"JUPITER_API_KEY": "test-key-not-a-secret"},
        preflight_fn=lambda *_args, **_kwargs: {"credential_reads": 0},
        opener=_SequenceOpener(responses),
        clock=clock,
        sleeper=clock.sleep,
    )


class ExclusionSetTests(unittest.TestCase):
    def test_exclusion_set_is_hash_bound_to_a1_runtime(self) -> None:
        self.assertEqual(hashlib.sha256(A1_RUNTIME_PATH.read_bytes()).hexdigest(), A1_RUNTIME_SHA256)
        exclusion = load_exclusion_set(ROOT, _policy())
        self.assertEqual(exclusion["excluded_mint_count"], 12)
        self.assertEqual(len(exclusion["excluded_mints"]), 12)
        self.assertEqual(len(set(exclusion["excluded_mints"])), 12)

    def test_filter_drops_a1_mints_and_keeps_others(self) -> None:
        excluded = set(_excluded_mints())
        mint = next(iter(excluded))
        rows = [{"id": mint, "liquidity": 2000}, {"id": "KeepMint111111111111111111111111111111", "liquidity": 2000}]
        filtered = filter_discovery_payload(rows, excluded)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["id"], "KeepMint111111111111111111111111111111")

    def test_policy_forbids_a1_fitted_rate_floor(self) -> None:
        policy = _policy()
        validate_policy(policy, root=ROOT)
        self.assertEqual(policy["concordance_rule"], "ORDINAL_SIGN_TEST_NO_RATE_FLOOR")
        self.assertNotIn("concordance_min_rate", policy)
        self.assertNotIn("concordance_rate_floor", policy)
        self.assertEqual(policy["external_authority"]["owner_phrase"], AUTHORITY_PHRASE)


class TerminalClassificationTests(unittest.TestCase):
    def test_invalid_capture_pauses_and_does_not_close_family(self) -> None:
        terminal = classify_move2_terminal(
            capture={"accepted": False, "blockers": ["CAPTURE_TIME_NOT_HASH_BOUND_AT_WRITE"]},
            campaign={"campaign_verdict": "VARIATION_PRESENT_NOT_MECHANISM"},
            mechanism={"verdict": "DIRECTIONAL_HINT_NOT_CONFIRMATION"},
            wrapped_terminal="PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE",
            discovery_rows=[{"terminal": "TOKEN_LIST_OBSERVED"}, {"terminal": "TOKEN_LIST_OBSERVED"}],
            frozen_cells=[{}] * 12,
        )
        self.assertEqual(terminal, "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE")
        self.assertFalse(family_closed(terminal))

    def test_sample_invalid_does_not_close_family(self) -> None:
        terminal = classify_move2_terminal(
            capture={"accepted": True},
            campaign={"campaign_verdict": "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY"},
            mechanism={"verdict": "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY"},
            wrapped_terminal="PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE",
            discovery_rows=[{"terminal": "TOKEN_LIST_OBSERVED"}, {"terminal": "TOKEN_LIST_OBSERVED"}],
            frozen_cells=[],
        )
        self.assertEqual(terminal, "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY")
        self.assertFalse(family_closed(terminal))

    def test_failed_sign_closes_exact_mechanism(self) -> None:
        terminal = classify_move2_terminal(
            capture={"accepted": True},
            campaign={"campaign_verdict": "VARIATION_PRESENT_NOT_MECHANISM"},
            mechanism={"verdict": "MECHANISM_NOT_SUPPORTED_ON_THIS_SAMPLE"},
            wrapped_terminal="CLOSE_EXACT_QUOTE_FRICTION_MECHANISM",
            discovery_rows=[{"terminal": "TOKEN_LIST_OBSERVED"}, {"terminal": "TOKEN_LIST_OBSERVED"}],
            frozen_cells=[{}] * 12,
        )
        self.assertEqual(terminal, "CLOSE_EXACT_QUOTE_FRICTION_MECHANISM")
        self.assertTrue(family_closed(terminal))

    def test_replicated_sign_is_not_alpha_and_not_move_3(self) -> None:
        terminal = classify_move2_terminal(
            capture={"accepted": True},
            campaign={"campaign_verdict": "VARIATION_PRESENT_NOT_MECHANISM"},
            mechanism={"verdict": "DIRECTIONAL_HINT_NOT_CONFIRMATION"},
            wrapped_terminal="DIRECTIONAL_HINT_NOT_CONFIRMATION",
            discovery_rows=[{"terminal": "TOKEN_LIST_OBSERVED"}, {"terminal": "TOKEN_LIST_OBSERVED"}],
            frozen_cells=[{}] * 12,
        )
        self.assertEqual(terminal, "REPLICATED_SIGN_NOT_ALPHA")
        self.assertFalse(family_closed(terminal))
        self.assertNotEqual(terminal, "ALPHA")
        self.assertFalse(terminal.startswith("MOVE_3"))


class CampaignCaptureTests(unittest.TestCase):
    def test_excludes_a1_mints_and_replicates_sign(self) -> None:
        excluded = _excluded_mints()
        reverse = [str(9_900_000 - index * 10_000) for index in range(12)]
        sell = [str(9_800_000 - index * 10_000) for index in range(12)]
        h3600 = [str(9_700_000 - index * 5_000) for index in range(12)]
        with tempfile.TemporaryDirectory() as directory:
            receipt = _run_capture(
                _quote_sequence(
                    reverse_out=reverse,
                    sell_out=sell,
                    h3600_out=h3600,
                    recent_extra=excluded[:6],
                    traded_extra=excluded[6:],
                ),
                directory=Path(directory),
            )
            frozen_mints = {cell["mint"] for cell in receipt["frozen_cells"]}
            self.assertTrue(frozen_mints.isdisjoint(set(excluded)))
            self.assertEqual(len(receipt["frozen_cells"]), 12)
            self.assertTrue(receipt["capture"]["accepted"])
            self.assertEqual(receipt["attempt_reservation"]["credential_reads"], 0)
            self.assertEqual(receipt["credential_reads"], 1)
            self.assertEqual(receipt["terminal_outcome"], "REPLICATED_SIGN_NOT_ALPHA")
            self.assertFalse(receipt["family_close"])
            self.assertFalse(receipt["move_3_executed"])
            self.assertEqual(receipt["concordance_rule"], "ORDINAL_SIGN_TEST_NO_RATE_FLOOR")
            self.assertEqual(receipt["exclusion"]["sha256"], A1_RUNTIME_SHA256)
            self.assertFalse(receipt["cohort_snapshot"]["reselected"])
            self.assertNotIn("test-key-not-a-secret", json.dumps(receipt))
            consumed = [
                row
                for row in receipt["discovery_observations"] + receipt["observations"]
                if row.get("consumed_call") is True
            ]
            for row in consumed:
                expected = capture_envelope(
                    observation_id=str(row["observation_id"]),
                    observed_at=str(row["observed_at"]),
                    body_sha256=str(row["transport"]["response_sha256"]),
                )
                self.assertEqual(row["capture_envelope_sha256"], expected["envelope_sha256"])

    def test_failed_sign_closes_family(self) -> None:
        reverse = [str(9_900_000 - index * 10_000) for index in range(12)]
        sell = [str(9_000_000 + index * 10_000) for index in range(12)]
        h3600 = [str(8_900_000 + index * 5_000) for index in range(12)]
        with tempfile.TemporaryDirectory() as directory:
            receipt = _run_capture(
                _quote_sequence(reverse_out=reverse, sell_out=sell, h3600_out=h3600),
                directory=Path(directory),
            )
            self.assertTrue(receipt["capture"]["accepted"])
            self.assertEqual(receipt["terminal_outcome"], "CLOSE_EXACT_QUOTE_FRICTION_MECHANISM")
            self.assertTrue(receipt["family_close"])
            self.assertGreater(receipt["mechanism"]["discordant_pairs"], receipt["mechanism"]["concordant_pairs"])

    def test_exclusion_emptied_cohort_is_sample_invalid_not_close(self) -> None:
        excluded = _excluded_mints()
        recent = json.dumps(
            [
                {"id": mint, "liquidity": 2000, "firstPool": {"createdAt": "2026-08-18T00:00:00Z"}}
                for mint in excluded[:6]
            ]
        ).encode("utf-8")
        traded = json.dumps(
            [
                {"id": mint, "liquidity": 2000, "firstPool": {"createdAt": "2026-08-18T00:00:00Z"}}
                for mint in excluded[6:]
            ]
        ).encode("utf-8")
        responses = [
            _Response(recent, status=200, headers={}),
            _Response(traded, status=200, headers={}),
        ]
        with tempfile.TemporaryDirectory() as directory:
            receipt = _run_capture(responses, directory=Path(directory))
            self.assertEqual(receipt["terminal_outcome"], "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY")
            self.assertFalse(receipt["family_close"])
            self.assertTrue(receipt["capture"]["accepted"])


class GitReceiptTests(unittest.TestCase):
    def test_runtime_is_hash_bound_and_excludes_a1_mints(self) -> None:
        payload = RUNTIME_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), RUNTIME_SHA256)
        receipt = json.loads(payload.decode("utf-8"))
        excluded = set(_excluded_mints())
        frozen = {str(cell["mint"]) for cell in receipt["frozen_cells"]}
        self.assertEqual(len(receipt["frozen_cells"]), 12)
        self.assertTrue(frozen.isdisjoint(excluded))
        self.assertEqual(receipt["exclusion"]["sha256"], A1_RUNTIME_SHA256)
        self.assertTrue(receipt["capture"]["accepted"])
        self.assertEqual(receipt["terminal_outcome"], "REPLICATED_SIGN_NOT_ALPHA")
        self.assertFalse(receipt["family_close"])
        self.assertFalse(receipt["move_3_executed"])
        self.assertTrue(receipt["h900_observed"])
        self.assertFalse(receipt["h3600_observed"])
        self.assertTrue(receipt["foreground_run_incomplete"])
        self.assertEqual(receipt["provider_requests"], 34)
        self.assertEqual(receipt["capture"]["consumed_count"], 34)
        self.assertTrue(receipt["mechanism"]["scored"])
        self.assertEqual(receipt["mechanism"]["concordant_pairs"], 21)
        self.assertEqual(receipt["mechanism"]["discordant_pairs"], 15)
        self.assertGreater(
            receipt["mechanism"]["concordant_pairs"],
            receipt["mechanism"]["discordant_pairs"],
        )
        self.assertEqual(receipt["concordance_rule"], "ORDINAL_SIGN_TEST_NO_RATE_FLOOR")
        self.assertNotIn("concordance_min_rate", receipt)
        self.assertFalse(receipt["cohort_snapshot"]["reselected"])
        self.assertEqual(len(str(receipt["cohort_snapshot"].get("snapshot_sha256") or "")), 64)
        cells_by_identity = {str(cell["identity_id"]): cell for cell in receipt["frozen_cells"]}
        for row in receipt["observations"]:
            cell = cells_by_identity[str(row["identity_id"])]
            self.assertEqual(row["mint"], cell["mint"])
            self.assertEqual(row["stratum"], cell["stratum"])
        serialized = json.dumps(receipt)
        self.assertNotIn("JUPITER_API_KEY", serialized)
        self.assertNotIn("test-key-not-a-secret", serialized)
        self.assertNotIn("C:\\\\Users", serialized)

    def test_acceptance_binds_runtime_and_does_not_close_family(self) -> None:
        payload = ACCEPTANCE_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), ACCEPTANCE_SHA256)
        acceptance = json.loads(payload.decode("utf-8"))
        self.assertEqual(acceptance["source_runtime_receipt_sha256"], RUNTIME_SHA256)
        self.assertEqual(acceptance["a1_runtime_receipt_sha256"], A1_RUNTIME_SHA256)
        self.assertEqual(acceptance["terminal"], "REPLICATED_SIGN_NOT_ALPHA")
        self.assertFalse(acceptance["family_close"])
        self.assertFalse(acceptance["move_3_executed"])
        self.assertTrue(acceptance["criteria"]["mechanism_scored"])
        self.assertEqual(acceptance["criteria"]["concordant_pairs"], 21)
        self.assertEqual(acceptance["criteria"]["discordant_pairs"], 15)
        self.assertTrue(acceptance["provider_observations"]["h900_observed"])
        self.assertEqual(acceptance["provider_observations"]["provider_requests"], 34)
        self.assertIn("NO_RECAPTURE_ONLY_SUFFIX", acceptance["non_claims"])
        self.assertIn("NO_THRESHOLD_FIT", acceptance["non_claims"])
        self.assertIn("NO_A1_MINT_REUSE", acceptance["non_claims"])
        self.assertIn("NO_MOVE_3", acceptance["non_claims"])
        self.assertIn("NO_ALPHA", acceptance["non_claims"])


class IncompleteRecoveryTests(unittest.TestCase):
    def _write_rows(self, run_dir: Path, rows: list[tuple[str, str, str, bytes]]) -> None:
        for name, observation_id, observed_at, body in rows:
            envelope = capture_envelope(
                observation_id=observation_id,
                observed_at=observed_at,
                body_sha256=hashlib.sha256(body).hexdigest(),
            )
            (run_dir / f"{name}.envelope.json").write_text(
                json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (run_dir / f"{name}.body").write_bytes(body)

    def _write_snapshot(self, run_dir: Path, excluded: list[str]) -> None:
        recent = json.loads((run_dir / "DISCOVERY_RECENT.body").read_text(encoding="utf-8"))
        traded = json.loads((run_dir / "DISCOVERY_TRADED.body").read_text(encoding="utf-8"))
        cohort = select_cohort_excluding_a1(recent, traded, excluded_mints=set(excluded))
        cells = cohort["cells"]
        assert isinstance(cells, list)
        write_cohort_snapshot(
            run_dir / COHORT_SNAPSHOT_NAME,
            cells=cells,
            discovery_recent_body_sha256=hashlib.sha256((run_dir / "DISCOVERY_RECENT.body").read_bytes()).hexdigest(),
            discovery_traded_body_sha256=hashlib.sha256((run_dir / "DISCOVERY_TRADED.body").read_bytes()).hexdigest(),
        )

    def test_incomplete_local_envelopes_recover_transport_unknown_without_new_gets(self) -> None:
        policy = _policy()
        excluded = _excluded_mints()
        reservation = attempt_reservation_document(
            started_at="2026-08-19T12:00:00Z",
            policy_sha256="b" * 64,
        )
        recent_body = _token_rows("Recent", extra=excluded[:6])
        traded_body = _token_rows("Traded", extra=excluded[6:])
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            self._write_rows(
                run_dir,
                [
                    ("DISCOVERY_RECENT", "DISCOVERY:RECENT", "2026-08-19T12:00:03Z", recent_body),
                    ("DISCOVERY_TRADED", "DISCOVERY:TRADED", "2026-08-19T12:00:06Z", traded_body),
                    (
                        "RECENT_1_10000000_BUY_T0",
                        "RECENT_1:10000000:BUY_T0",
                        "2026-08-19T12:00:09Z",
                        _quote_body("10000000", out_amount="10000000"),
                    ),
                ],
            )
            self._write_snapshot(run_dir, excluded)
            receipt = receipt_from_incomplete_local_run(
                policy,
                root=ROOT,
                reservation=reservation,
                run_dir=run_dir,
                credential_reads=1,
            )
            frozen = {str(cell["mint"]) for cell in receipt["frozen_cells"]}
            self.assertEqual(receipt["terminal_outcome"], "TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED")
            self.assertTrue(receipt["capture"]["accepted"])
            self.assertFalse(receipt["family_close"])
            self.assertFalse(receipt["move_3_executed"])
            self.assertTrue(receipt["foreground_run_incomplete"])
            self.assertFalse(receipt["cohort_snapshot"]["reselected"])
            self.assertEqual(len(receipt["frozen_cells"]), 12)
            self.assertTrue(frozen.isdisjoint(set(excluded)))
            self.assertEqual(receipt["exclusion"]["sha256"], A1_RUNTIME_SHA256)
            self.assertEqual(receipt["provider_requests"], 3)
            self.assertEqual(receipt["credential_reads"], 1)
            quote_row = receipt["observations"][0]
            self.assertIn(quote_row["mint"], frozen)
            self.assertEqual(quote_row["identity_id"], "RECENT_1")
            self.assertEqual(quote_row["quote"]["out_amount"], "10000000")

    def test_same_run_h900_envelopes_score_instead_of_transport_unknown(self) -> None:
        policy = _policy()
        excluded = _excluded_mints()
        reservation = attempt_reservation_document(
            started_at="2026-08-19T12:00:00Z",
            policy_sha256="b" * 64,
        )
        recent_body = _token_rows("Recent", extra=excluded[:6])
        traded_body = _token_rows("Traded", extra=excluded[6:])
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            self._write_rows(
                run_dir,
                [
                    ("DISCOVERY_RECENT", "DISCOVERY:RECENT", "2026-08-19T12:00:03Z", recent_body),
                    ("DISCOVERY_TRADED", "DISCOVERY:TRADED", "2026-08-19T12:00:06Z", traded_body),
                    (
                        "RECENT_1_10000000_BUY_T0",
                        "RECENT_1:10000000:BUY_T0",
                        "2026-08-19T12:00:09Z",
                        _quote_body("10000000", out_amount="10000000"),
                    ),
                    (
                        "RECENT_1_10000000_REVERSE_T0",
                        "RECENT_1:10000000:REVERSE_T0",
                        "2026-08-19T12:00:12Z",
                        _quote_body("10000000", out_amount="9900000"),
                    ),
                    (
                        "RECENT_1_10000000_SELL_H900",
                        "RECENT_1:10000000:SELL_H900",
                        "2026-08-19T12:15:12Z",
                        _quote_body("10000000", out_amount="9800000"),
                    ),
                ],
            )
            self._write_snapshot(run_dir, excluded)
            receipt = receipt_from_incomplete_local_run(
                policy,
                root=ROOT,
                reservation=reservation,
                run_dir=run_dir,
                credential_reads=1,
            )
            self.assertNotEqual(receipt["terminal_outcome"], "TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED")
            self.assertTrue(receipt["capture"]["accepted"])
            self.assertTrue(receipt["h900_observed"])
            self.assertTrue(receipt["mechanism"]["scored"])
            self.assertEqual(receipt["mechanism"]["searchable_y_kind"], "SELL_H900")
            self.assertFalse(receipt["cohort_snapshot"]["reselected"])
            self.assertEqual(receipt["provider_requests"], 5)
            self.assertFalse(receipt["family_close"])
            self.assertFalse(receipt["move_3_executed"])
            kinds = {str(row["kind"]) for row in receipt["observations"]}
            self.assertIn("SELL_H900", kinds)

    def test_attach_lineage_requires_matching_snapshot(self) -> None:
        policy = _policy()
        excluded = _excluded_mints()
        reservation = attempt_reservation_document(
            started_at="2026-08-19T12:00:00Z",
            policy_sha256="b" * 64,
        )
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            self._write_rows(
                run_dir,
                [
                    ("DISCOVERY_RECENT", "DISCOVERY:RECENT", "2026-08-19T12:00:03Z", _token_rows("Recent")),
                    ("DISCOVERY_TRADED", "DISCOVERY:TRADED", "2026-08-19T12:00:06Z", _token_rows("Traded")),
                    (
                        "RECENT_1_10000000_BUY_T0",
                        "RECENT_1:10000000:BUY_T0",
                        "2026-08-19T12:00:09Z",
                        _quote_body("10000000", out_amount="10000000"),
                    ),
                ],
            )
            self._write_snapshot(run_dir, excluded)
            receipt = receipt_from_incomplete_local_run(
                policy,
                root=ROOT,
                reservation=reservation,
                run_dir=run_dir,
                credential_reads=1,
            )
            snapshot = load_cohort_snapshot(run_dir / COHORT_SNAPSHOT_NAME)
            attached = attach_lineage_to_git_receipt(receipt, snapshot=snapshot)
            self.assertFalse(attached["cohort_snapshot"]["reselected"])
            self.assertEqual(
                attached["cohort_snapshot"]["snapshot_sha256"],
                snapshot["snapshot_sha256"],
            )
            broken = dict(snapshot)
            broken["discovery_recent_body_sha256"] = "0" * 64
            with self.assertRaises(Move2Error) as raised:
                attach_lineage_to_git_receipt(receipt, snapshot=broken)
            self.assertEqual(str(raised.exception), "SNAPSHOT_RECENT_SHA_MISMATCH")

    def test_recovery_rejects_body_bytes_that_do_not_match_envelope(self) -> None:
        policy = _policy()
        excluded = _excluded_mints()
        reservation = attempt_reservation_document(
            started_at="2026-08-19T12:00:00Z",
            policy_sha256="b" * 64,
        )
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            self._write_rows(
                run_dir,
                [
                    ("DISCOVERY_RECENT", "DISCOVERY:RECENT", "2026-08-19T12:00:03Z", _token_rows("Recent")),
                    ("DISCOVERY_TRADED", "DISCOVERY:TRADED", "2026-08-19T12:00:06Z", _token_rows("Traded")),
                ],
            )
            self._write_snapshot(run_dir, excluded)
            (run_dir / "DISCOVERY_RECENT.body").write_bytes(_token_rows("Tamper"))
            with self.assertRaises(Move2Error) as raised:
                receipt_from_incomplete_local_run(
                    policy,
                    root=ROOT,
                    reservation=reservation,
                    run_dir=run_dir,
                    credential_reads=1,
                )
            self.assertEqual(str(raised.exception), "RECOVERY_BODY_SHA_MISMATCH")

    def test_recovery_does_not_reselect_cohort_without_snapshot(self) -> None:
        policy = _policy()
        reservation = attempt_reservation_document(
            started_at="2026-08-19T12:00:00Z",
            policy_sha256="b" * 64,
        )
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            self._write_rows(
                run_dir,
                [
                    ("DISCOVERY_RECENT", "DISCOVERY:RECENT", "2026-08-19T12:00:03Z", _token_rows("Recent")),
                    ("DISCOVERY_TRADED", "DISCOVERY:TRADED", "2026-08-19T12:00:06Z", _token_rows("Traded")),
                ],
            )
            with self.assertRaises(Move2Error) as raised:
                receipt_from_incomplete_local_run(
                    policy,
                    root=ROOT,
                    reservation=reservation,
                    run_dir=run_dir,
                    credential_reads=1,
                )
            self.assertEqual(str(raised.exception), "COHORT_SNAPSHOT_MISSING")


class ReservationTests(unittest.TestCase):
    def test_reservation_hash_is_bound_before_credential_read(self) -> None:
        reservation = attempt_reservation_document(
            started_at="2026-08-19T12:00:00Z",
            policy_sha256="b" * 64,
        )
        self.assertEqual(reservation["credential_reads"], 0)


if __name__ == "__main__":
    unittest.main()
