from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_panel_publisher import (  # noqa: E402
    rebuild_observation_panel_from_rdp,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    load_observation_schedule,
    render_utc,
)
from solana_alpha_lab.factory.observation_schedule_compiler import (  # noqa: E402
    compile_schedule_document,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.observation_scheduler import (  # noqa: E402
    BUNDLE_TO_PRIMITIVE,
    tick_once,
)
from solana_alpha_lab.factory.pathrisk_calibration import (  # noqa: E402
    BUY_1M,
    BUY_10M,
    NOTIONAL_10M,
    NOTIONAL_1M,
    PathRiskCalibrationError,
    REVERSE_1M,
    REVERSE_10M,
    TERMINAL_BELOW_FLOOR,
    TERMINAL_DEGENERATE,
    TERMINAL_INFORMATIVE,
    TERMINAL_INVALID,
    TERMINAL_PARTIAL,
    build_readout,
    load_policy,
    proposed_capture_packet,
    quote_ratio_minus_one,
    render_fraction,
    select_r0_sample,
)
from solana_alpha_lab.factory.quote_surface_projection import ABSENT  # noqa: E402

GIT_SHA = "c" * 40
SOL = "So11111111111111111111111111111111111111112"
MINTS = (
    "MintA111111111111111111111111111111111111111",
    "MintB111111111111111111111111111111111111111",
    "MintC111111111111111111111111111111111111111",
    "MintD111111111111111111111111111111111111111",
)
ANCHOR = "2026-09-01T00:05:00Z"
T0 = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)
H900 = datetime(2026, 9, 1, 0, 20, tzinfo=UTC)


def _row(mint: str, *, liquidity: str = "2000") -> dict:
    return {
        "id": mint,
        "liquidity": liquidity,
        "firstPool": {"createdAt": ANCHOR, "source": "pump.fun"},
        "first_seen_at": ANCHOR,
    }


def _activate(store: ObservationScheduleStore, schedule: dict) -> str:
    from solana_alpha_lab.factory.observation_schedule import canonical_sha256 as digest
    from solana_alpha_lab.factory.observation_schedule_lifecycle import (
        _authority_policy,
        _minimum_expiry,
        _used_provider_route_ids,
        authorize_schedule,
        expected_authority_phrase,
    )

    data_root = store.path.parent / "rdp"
    data_root.mkdir(parents=True, exist_ok=True)
    store.persist_registered_schedule(
        schedule_sha256=schedule["schedule_sha256"],
        schedule_key=schedule["schedule_key"],
        document=schedule,
        clock=T0,
    )
    expires_at = render_utc(_minimum_expiry(schedule))
    _, routes = _used_provider_route_ids(ROOT, schedule)
    policy = _authority_policy(
        root=ROOT,
        document=schedule,
        schedule_key=schedule["schedule_key"],
        expires_at=expires_at,
    )
    authority = authorize_schedule(
        root=ROOT,
        data_root=data_root,
        store=store,
        schedule_sha256=schedule["schedule_sha256"],
        phrase=expected_authority_phrase(
            schedule_sha256=schedule["schedule_sha256"],
            schedule_key=schedule["schedule_key"],
            activation_starts_at=schedule["activation"]["starts_at"],
            activation_stops_admitting_at=schedule["activation"]["stops_admitting_at"],
            provider_route_ids=routes,
            expires_at=expires_at,
            policy_digest=digest(policy),
        ),
        now=T0,
        producer_git_sha=GIT_SHA,
    )
    store.upsert_activation(
        {
            "schedule_sha256": schedule["schedule_sha256"],
            "activation_id": "ACT-PATHRISK-001",
            "schedule_key": schedule["schedule_key"],
            "state": "ACTIVE",
            "authority_receipt_sha256": authority["receipt_sha256"],
            "starts_at": schedule["activation"]["starts_at"],
            "stops_admitting_at": schedule["activation"]["stops_admitting_at"],
            "payload": {},
        },
        clock=T0,
    )
    return "ACT-PATHRISK-001"


class CalibrationOpener:
    def __init__(self, *, mode: str = "happy", redact: str | None = None) -> None:
        self.urls: list[str] = []
        self.mode = mode
        self.redact = redact
        self.sell_counts: dict[tuple[str, str], int] = {}

    def open(self, url: str) -> dict:
        self.urls.append(url)
        if self.redact and self.redact in url:
            raise AssertionError("SECRET_IN_URL")
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        if "/tokens/v2/search" in url:
            return {
                "http_status": 200,
                "body": [_row(mint) for mint in MINTS],
            }
        amount = (query.get("amount") or [""])[0]
        input_mint = (query.get("inputMint") or [""])[0]
        output_mint = (query.get("outputMint") or [""])[0]
        if self.mode == "typed_failure":
            return {
                "http_status": 400,
                "body": {"error": "FAILED TO GET QUOTES", "errorCode": "NO_ROUTES_FOUND"},
            }
        if input_mint == SOL:
            if amount == NOTIONAL_1M and self.mode == "one_notional_unavailable":
                return {"http_status": 404, "body": {"error": "NO_ROUTE"}}
            token_out = "11100000010" if amount == NOTIONAL_10M else "1110000001"
            body = {
                "inAmount": amount,
                "outAmount": token_out,
                "router": "iris",
                "mode": "ultra",
                "inputMint": input_mint,
                "outputMint": output_mint,
            }
            if self.mode != "missing_surface":
                body.update(
                    {
                        "priceImpactPct": "0.12",
                        "feeBps": "10",
                        "platformFee": None,
                        "routePlan": [
                            {"swapInfo": {"feeAmount": "1"}},
                        ],
                    }
                )
            return {"http_status": 200, "body": body}
        key = (input_mint, amount)
        self.sell_counts[key] = self.sell_counts.get(key, 0) + 1
        visit = self.sell_counts[key]
        if self.mode == "t0_reverse_missing" and visit == 1:
            return {"http_status": 404, "body": {"error": "NO_ROUTE"}}
        if self.mode == "h900_missing" and visit >= 2:
            return {"http_status": 404, "body": {"error": "NO_ROUTE"}}
        if amount == "11100000010":
            t0_out = "9800000"
            h900_out = "9700000" if self.mode != "degenerate_zero" else "9800000"
            if self.mode == "same_h900_diff_t0":
                t0_out = "9800000"
                h900_out = "9700000"
            out = t0_out if visit == 1 else h900_out
        else:
            t0_out = "980000"
            h900_out = "960000" if self.mode != "degenerate_zero" else "980000"
            out = t0_out if visit == 1 else h900_out
        if self.mode == "same_h900_diff_t0" and amount == "1110000001":
            out = "990000" if visit == 1 else "9700000"
        body = {
            "inAmount": amount,
            "outAmount": out,
            "router": "iris",
            "mode": "ultra",
            "inputMint": input_mint,
            "outputMint": output_mint,
            "routePlan": [],
        }
        return {"http_status": 200, "body": body}


def _buy_quote_amount(url: str) -> str | None:
    if "/swap/v2/order" not in url:
        return None
    query = parse_qs(urlsplit(url).query)
    if (query.get("inputMint") or [""])[0] != SOL:
        return None
    return (query.get("amount") or [None])[0]


def _sell_quote_binding(url: str) -> tuple[str, str] | None:
    if "/swap/v2/order" not in url:
        return None
    query = parse_qs(urlsplit(url).query)
    input_mint = (query.get("inputMint") or [""])[0]
    amount = (query.get("amount") or [""])[0]
    if not input_mint or input_mint == SOL or not amount:
        return None
    return input_mint, amount


def _drain(store, schedule, activation_id, start, opener, data_root, discovery, steps: int = 40):
    now = start
    last = None
    for _ in range(steps):
        last = tick_once(
            root=ROOT,
            data_root=data_root,
            store=store,
            schedule=schedule,
            activation_id=activation_id,
            now=now,
            opener=opener,
            producer_git_sha=GIT_SHA,
            discovery_rows=discovery,
            redact_with=opener.redact,
        )
        discovery = []
        pending = [
            row
            for row in store.due_in_states(("PENDING", "DUE", "CLAIMED"))
            if row["schedule_sha256"] == schedule["schedule_sha256"]
            and parse_utc_due(row["due_at"]) <= now
        ]
        if not pending:
            break
        now = now + timedelta(seconds=4)
    return last, now


def parse_utc_due(value: str):
    from solana_alpha_lab.factory.observation_schedule import parse_utc

    return parse_utc(value)


class PathRiskCalibrationTests(unittest.TestCase):
    def test_schedule_expresses_two_notionals_and_t0_reverse(self) -> None:
        document = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/pathrisk_calibration.yaml"
        )
        result = compile_schedule_document(document, root=ROOT)
        self.assertEqual(result.terminal, "SCHEDULE_ACTIVATION_REQUIRED")
        x_bundles = document["x_point"]["bundle_ids"]
        y_bundles = document["y_points"][0]["bundle_ids"]
        self.assertIn("BUNDLE-JUPITER-QUOTE-BUY-001", x_bundles)
        self.assertIn("BUNDLE-JUPITER-QUOTE-BUY-1M-001", x_bundles)
        self.assertIn("BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-001", x_bundles)
        self.assertIn("BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-1M-001", x_bundles)
        self.assertIn("BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-001", y_bundles)
        self.assertIn("BUNDLE-JUPITER-DEPENDENT-REVERSE-SELL-1M-001", y_bundles)
        self.assertEqual(BUNDLE_TO_PRIMITIVE["BUNDLE-JUPITER-QUOTE-BUY-1M-001"], BUY_1M)

    def test_below_floor_makes_zero_quote_calls(self) -> None:
        policy = load_policy(ROOT)
        sample = select_r0_sample(
            [_row(MINTS[0]), _row(MINTS[1]), _row(MINTS[2])],
            policy=policy,
            as_of=T0,
        )
        self.assertEqual(sample["terminal"], TERMINAL_BELOW_FLOOR)
        self.assertEqual(sample["quote_calls"], 0)

    def test_exact_integer_recompute(self) -> None:
        value = quote_ratio_minus_one(9727186, 10_000_000)
        self.assertEqual(render_fraction(value), "-136407/5000000")
        self.assertEqual(value, quote_ratio_minus_one(9727186, 10_000_000))

    def test_path_change_zero_when_t0_equals_h900(self) -> None:
        observations = _synthetic_obs(t0_10m=9800000, h900_10m=9800000, t0_1m=980000, h900_1m=980000)
        readout = build_readout(mints=list(MINTS), observations=observations)
        zeros = {
            cell["QUOTE_PATH_CHANGE"]["value"]
            for cell in readout["cells"]
            if cell["complete"]
        }
        self.assertEqual(zeros, {"0/1"})

    def test_user_scenario_end_to_end_informative(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/pathrisk_calibration.yaml"
        )
        policy = load_policy(ROOT)
        rows = [_row(mint) for mint in MINTS]
        sample = select_r0_sample(rows, policy=policy, as_of=T0)
        self.assertIsNone(sample["terminal"])
        opener = CalibrationOpener()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store_path = Path(tmp) / "ops.sqlite"
            store = ObservationScheduleStore(store_path)
            activation_id = _activate(store, schedule)
            discovery = [_row(mint) for mint in sample["mints"]]
            _drain(store, schedule, activation_id, T0, opener, data_root, discovery)
            t0_calls = list(opener.urls)
            store.close()
            store = ObservationScheduleStore(store_path)
            rebuilt_t0 = rebuild_observation_panel_from_rdp(
                data_root=data_root,
                schedule_sha256=schedule["schedule_sha256"],
            )
            t0_buy_states = {
                row["state"]
                for row in rebuilt_t0["observations"]
                if row["primitive_id"] in {BUY_10M, BUY_1M}
            }
            t0_reverse_states = {
                row["state"]
                for row in rebuilt_t0["observations"]
                if row["primitive_id"] in {REVERSE_10M, REVERSE_1M}
                and row["point_id"] == "X300"
            }
            self.assertIn("OBSERVED", t0_buy_states)
            self.assertIn("OBSERVED", t0_reverse_states)
            members = store.list_candidates(
                schedule_sha256=schedule["schedule_sha256"],
                activation_id=activation_id,
            )
            eligible_states = {
                item["state"]
                for item in members
                if item["entity_id"] in sample["mints"]
            }
            self.assertEqual(eligible_states, {"X_ELIGIBLE"})
            before_h900 = len(opener.urls)
            _drain(store, schedule, activation_id, H900, opener, data_root, [])
            rebuilt = rebuild_observation_panel_from_rdp(
                data_root=data_root,
                schedule_sha256=schedule["schedule_sha256"],
            )
            readout = build_readout(
                mints=sample["mints"],
                observations=rebuilt["observations"],
                provider_calls=len(opener.urls),
            )
            self.assertEqual(readout["terminal"], TERMINAL_INFORMATIVE)
            self.assertGreaterEqual(len(readout["complete_dual_notional_mints"]), 3)
            cell_10 = next(
                cell
                for cell in readout["cells"]
                if cell["complete"] and cell["notional_lamports"] == NOTIONAL_10M
            )
            cell_1 = next(
                cell
                for cell in readout["cells"]
                if cell["complete"] and cell["notional_lamports"] == NOTIONAL_1M
            )
            self.assertEqual(
                cell_10["QUOTE_NET_PROXY"]["value"],
                render_fraction(quote_ratio_minus_one(9700000, 10_000_000)),
            )
            self.assertEqual(
                cell_10["QUOTE_PATH_CHANGE"]["value"],
                render_fraction(quote_ratio_minus_one(9700000, 9_800_000)),
            )
            self.assertNotEqual(
                cell_10["QUOTE_NET_PROXY"]["value"],
                cell_10["QUOTE_PATH_CHANGE"]["value"],
            )
            self.assertEqual(
                cell_1["QUOTE_NET_PROXY"]["value"],
                render_fraction(quote_ratio_minus_one(960000, 1_000_000)),
            )
            self.assertEqual(
                cell_1["QUOTE_PATH_CHANGE"]["value"],
                render_fraction(quote_ratio_minus_one(960000, 980000)),
            )
            sample_cell = next(cell for cell in readout["cells"] if cell["complete"])
            self.assertIn("fee_fields", sample_cell)
            self.assertIn("impact_fields", sample_cell)
            self.assertIn("route_fields", sample_cell)
            self.assertIn("t0_vs_h900_route_impact_delta", sample_cell)
            quote_urls = [url for url in opener.urls if "/swap/v2/order" in url]
            self.assertTrue(quote_urls)
            self.assertTrue(all("taker" not in url.lower() for url in quote_urls))
            self.assertTrue(all("/build" not in url for url in quote_urls))
            self.assertTrue(all("/execute" not in url for url in quote_urls))
            buy_amounts = [_buy_quote_amount(url) for url in quote_urls]
            self.assertEqual(buy_amounts.count(NOTIONAL_10M), 4)
            self.assertEqual(buy_amounts.count(NOTIONAL_1M), 4)
            token_out_10m = "11100000010"
            token_out_1m = "1110000001"
            sells = [item for url in quote_urls if (item := _sell_quote_binding(url))]
            self.assertEqual(len(sells), 16)
            for mint in sample["mints"]:
                amounts = [amount for bound_mint, amount in sells if bound_mint == mint]
                self.assertEqual(amounts.count(token_out_10m), 2)
                self.assertEqual(amounts.count(token_out_1m), 2)
                self.assertNotIn(NOTIONAL_10M, amounts)
                self.assertNotIn(NOTIONAL_1M, amounts)
            buy_10 = {
                item["typed_value_or_null"]
                for row in rebuilt["observations"]
                if row["primitive_id"] == BUY_10M
                for item in row.get("field_values") or []
                if item["field_id"] == "FIELD-QUOTE-BUY-OUT-AMOUNT-001"
                and item["state"] == "OBSERVED"
            }
            buy_1 = {
                item["typed_value_or_null"]
                for row in rebuilt["observations"]
                if row["primitive_id"] == BUY_1M
                for item in row.get("field_values") or []
                if item["field_id"] == "FIELD-QUOTE-BUY-OUT-AMOUNT-001"
                and item["state"] == "OBSERVED"
            }
            self.assertTrue(buy_10)
            self.assertTrue(buy_1)
            self.assertFalse(buy_10 & buy_1)
            fee = next(
                item
                for row in rebuilt["observations"]
                if row["primitive_id"] == BUY_10M
                for item in row.get("field_values") or []
                if item["field_id"] == "FIELD-QUOTE-FEE-BPS-001"
            )
            self.assertEqual(fee["typed_value_or_null"], "10")
            pointer = next(
                item
                for row in rebuilt["observations"]
                if row["primitive_id"] == BUY_10M
                for item in row.get("field_values") or []
                if item["field_id"] == "FIELD-QUOTE-RESPONSE-SHA256-001"
            )
            self.assertEqual(len(pointer["typed_value_or_null"] or ""), 64)
            self.assertGreater(len(opener.urls), before_h900)
            replay, _ = _drain(store, schedule, activation_id, H900, opener, data_root, [])
            self.assertEqual(replay["provider_calls"], 0)
            self.assertTrue(any(path.is_file() for path in data_root.rglob("*")))
            self.assertTrue(t0_calls)
            store.close()

    def test_missing_surface_fields_are_absent_not_zero(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/pathrisk_calibration.yaml"
        )
        opener = CalibrationOpener(mode="missing_surface")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            _drain(store, schedule, activation_id, T0, opener, data_root, [_row(MINTS[0])])
            rebuilt = rebuild_observation_panel_from_rdp(
                data_root=data_root,
                schedule_sha256=schedule["schedule_sha256"],
            )
            fee = next(
                item
                for row in rebuilt["observations"]
                if row["primitive_id"] == BUY_10M
                for item in row.get("field_values") or []
                if item["field_id"] == "FIELD-QUOTE-FEE-BPS-001"
            )
            self.assertIsNone(fee["typed_value_or_null"])
            self.assertEqual(fee["missing_reason"], ABSENT)
            self.assertNotEqual(fee["typed_value_or_null"], "0")
            store.close()

    def test_one_notional_unavailable_and_t0_reverse_missing(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/pathrisk_calibration.yaml"
        )
        opener = CalibrationOpener(mode="one_notional_unavailable")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            _drain(store, schedule, activation_id, T0, opener, data_root, [_row(mint) for mint in MINTS])
            _drain(store, schedule, activation_id, H900, opener, data_root, [])
            rebuilt = rebuild_observation_panel_from_rdp(
                data_root=data_root,
                schedule_sha256=schedule["schedule_sha256"],
            )
            readout = build_readout(mints=list(MINTS), observations=rebuilt["observations"])
            one_m = [cell for cell in readout["cells"] if cell["notional_lamports"] == NOTIONAL_1M]
            self.assertTrue(all(not cell["complete"] for cell in one_m))
            self.assertEqual(readout["terminal"], TERMINAL_PARTIAL)
            store.close()

        opener = CalibrationOpener(mode="t0_reverse_missing")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            _drain(store, schedule, activation_id, T0, opener, data_root, [_row(mint) for mint in MINTS])
            _drain(store, schedule, activation_id, H900, opener, data_root, [])
            rebuilt = rebuild_observation_panel_from_rdp(
                data_root=data_root,
                schedule_sha256=schedule["schedule_sha256"],
            )
            readout = build_readout(mints=list(MINTS), observations=rebuilt["observations"])
            for cell in readout["cells"]:
                self.assertEqual(cell["QUOTE_PATH_CHANGE"]["status"], "UNKNOWN")
                self.assertIsNone(cell["QUOTE_PATH_CHANGE"]["value"])
            store.close()

    def test_h900_missing_and_provider_failure(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/pathrisk_calibration.yaml"
        )
        opener = CalibrationOpener(mode="h900_missing")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            _drain(store, schedule, activation_id, T0, opener, data_root, [_row(mint) for mint in MINTS])
            _drain(store, schedule, activation_id, H900, opener, data_root, [])
            rebuilt = rebuild_observation_panel_from_rdp(
                data_root=data_root,
                schedule_sha256=schedule["schedule_sha256"],
            )
            readout = build_readout(mints=list(MINTS), observations=rebuilt["observations"])
            self.assertEqual(readout["terminal"], TERMINAL_PARTIAL)
            self.assertTrue(
                all(cell["QUOTE_PATH_CHANGE"]["status"] == "UNKNOWN" for cell in readout["cells"])
            )
            store.close()
        opener = CalibrationOpener(mode="typed_failure")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            _drain(store, schedule, activation_id, T0, opener, data_root, [_row(MINTS[0])])
            rebuilt = rebuild_observation_panel_from_rdp(
                data_root=data_root,
                schedule_sha256=schedule["schedule_sha256"],
            )
            buy_states = {
                row["state"]
                for row in rebuilt["observations"]
                if row["primitive_id"] in {BUY_10M, BUY_1M}
            }
            self.assertTrue(buy_states)
            self.assertNotIn("OBSERVED", buy_states)
            store.close()

    def test_same_h900_different_t0_is_informative(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/pathrisk_calibration.yaml"
        )
        opener = CalibrationOpener(mode="same_h900_diff_t0")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            _drain(store, schedule, activation_id, T0, opener, data_root, [_row(mint) for mint in MINTS])
            _drain(store, schedule, activation_id, H900, opener, data_root, [])
            rebuilt = rebuild_observation_panel_from_rdp(
                data_root=data_root,
                schedule_sha256=schedule["schedule_sha256"],
            )
            readout = build_readout(mints=list(MINTS), observations=rebuilt["observations"])
            self.assertEqual(readout["terminal"], TERMINAL_INFORMATIVE)
            h900_outs = {cell["h900_sol_output"] for cell in readout["cells"] if cell["complete"]}
            t0_outs = {cell["t0_reverse_sol_output"] for cell in readout["cells"] if cell["complete"]}
            self.assertEqual(h900_outs, {9700000})
            self.assertGreater(len(t0_outs), 1)
            store.close()

    def test_redaction_and_forbidden_actions(self) -> None:
        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/pathrisk_calibration.yaml"
        )
        marker = "super-secret"
        opener = CalibrationOpener(redact=marker)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            data_root = Path(tmp) / "rdp"
            data_root.mkdir()
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            activation_id = _activate(store, schedule)
            _drain(store, schedule, activation_id, T0, opener, data_root, [_row(MINTS[0])])
            self.assertTrue(all(marker not in url for url in opener.urls))
            self.assertTrue(all("api-key" not in url.lower() for url in opener.urls))
            store.close()

    def test_capture_packet_is_not_live(self) -> None:
        packet = proposed_capture_packet(root=ROOT, main_sha="b" * 40)
        self.assertFalse(packet["live_authorized"])
        self.assertEqual(packet["provider_calls_this_pr"], 0)
        self.assertEqual(packet["sample_floor"], 4)
        self.assertEqual(packet["notionals_lamports"], [NOTIONAL_1M, NOTIONAL_10M])
        self.assertIn("taker", packet["forbidden_actions"])
        self.assertEqual(packet["live_window"]["inject_r0_discovery"], True)
        self.assertEqual(packet["live_window"]["enable_source_poll"], False)
        with self.assertRaisesRegex(PathRiskCalibrationError, "MAIN_SHA_NOT_EXACT_40_HEX"):
            proposed_capture_packet(root=ROOT, main_sha="<EXACT_MAIN_SHA>")
        with self.assertRaisesRegex(PathRiskCalibrationError, "MAIN_SHA_NOT_EXACT_40_HEX"):
            proposed_capture_packet(root=ROOT, main_sha="B" * 40)

    def test_capture_packet_cli_refuses_placeholder_sha(self) -> None:
        import subprocess

        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts" / "early_quote_surface_pathrisk_calibration.py"),
                "capture-packet",
                "--main-sha",
                "<EXACT_MAIN_SHA>",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("MAIN_SHA_NOT_EXACT_40_HEX", completed.stdout + completed.stderr)

    def test_degenerate_classifier(self) -> None:
        observations = _synthetic_obs(
            t0_10m=9800000, h900_10m=9700000, t0_1m=980000, h900_1m=970000
        )
        # Force identical path-change on both notionals: 9700000/9800000-1 vs 970000/980000-1
        # are different; make them the same ratio.
        observations = _synthetic_obs(
            t0_10m=10000000, h900_10m=9000000, t0_1m=1000000, h900_1m=900000
        )
        readout = build_readout(mints=list(MINTS), observations=observations)
        self.assertEqual(readout["terminal"], TERMINAL_DEGENERATE)

    def test_unseasoned_mint_is_not_eligible(self) -> None:
        policy = load_policy(ROOT)
        fresh = _row(MINTS[0])
        fresh["firstPool"] = {"createdAt": "2026-09-01T00:09:59Z", "source": "pump.fun"}
        sample = select_r0_sample(
            [fresh, _row(MINTS[1]), _row(MINTS[2]), _row(MINTS[3])],
            policy=policy,
            as_of=T0,
        )
        self.assertEqual(sample["terminal"], TERMINAL_BELOW_FLOOR)
        self.assertNotIn(MINTS[0], sample["mints"])

    def test_schema_invalid_and_cross_bind_terminals(self) -> None:
        invalid = _synthetic_obs(
            t0_10m=9800000, h900_10m=9700000, t0_1m=980000, h900_1m=960000
        )
        invalid[0]["field_values"][0]["typed_value_or_null"] = "not-an-integer"
        readout = build_readout(mints=list(MINTS), observations=invalid)
        self.assertEqual(readout["terminal"], TERMINAL_INVALID)
        self.assertTrue(readout["schema_invalid"])

        crossed: list[dict] = []
        for mint in MINTS:
            crossed.extend(
                [
                    _obs(mint, "X300", BUY_10M, "FIELD-QUOTE-BUY-OUT-AMOUNT-001", "11100000010"),
                    _obs(mint, "X300", BUY_1M, "FIELD-QUOTE-BUY-OUT-AMOUNT-001", "11100000010"),
                    _obs(mint, "X300", REVERSE_10M, "FIELD-QUOTE-SELL-OUT-AMOUNT-001", "9800000"),
                    _obs(mint, "X300", REVERSE_1M, "FIELD-QUOTE-SELL-OUT-AMOUNT-001", "980000"),
                    _obs(mint, "Y900", REVERSE_10M, "FIELD-QUOTE-SELL-OUT-AMOUNT-001", "9700000"),
                    _obs(mint, "Y900", REVERSE_1M, "FIELD-QUOTE-SELL-OUT-AMOUNT-001", "960000"),
                ]
            )
        crossed_readout = build_readout(mints=list(MINTS), observations=crossed)
        self.assertTrue(crossed_readout["cross_bound"])
        self.assertEqual(crossed_readout["terminal"], TERMINAL_INVALID)

    def test_zero_t0_reverse_is_schema_invalid_not_crash(self) -> None:
        observations = _synthetic_obs(
            t0_10m=0, h900_10m=9700000, t0_1m=0, h900_1m=960000
        )
        readout = build_readout(mints=list(MINTS), observations=observations)
        self.assertEqual(readout["terminal"], TERMINAL_INVALID)

    def test_typed_values_do_not_abort_tick_on_transaction_payload(self) -> None:
        from solana_alpha_lab.factory.observation_primitive_registry import (
            load_observation_primitive_registry,
        )
        from solana_alpha_lab.factory.observation_scheduler import _typed_observation_values

        registry = load_observation_primitive_registry(ROOT)
        values = _typed_observation_values(
            claim={
                "primitive_id": BUY_10M,
                "point_id": "X300",
                "event_time": "2026-09-01T00:10:00Z",
                "first_reliable_available_at": "2026-09-01T00:10:07Z",
                "request_sha256": "a" * 64,
                "call_occurrence_id": "b" * 64,
            },
            state="OBSERVED",
            response_payload={"outAmount": "1", "transaction": "deadbeef"},
            buy_out="1",
            missing_reason=None,
            registry=registry,
        )
        fee = next(item for item in values if item["field_id"] == "FIELD-QUOTE-FEE-BPS-001")
        self.assertIsNone(fee["typed_value_or_null"])
        self.assertEqual(fee["missing_reason"], "INVALID_RESPONSE")


def _synthetic_obs(
    *,
    t0_10m: int,
    h900_10m: int,
    t0_1m: int,
    h900_1m: int,
) -> list[dict]:
    rows = []
    for mint in MINTS:
        rows.extend(
            [
                _obs(mint, "X300", BUY_10M, "FIELD-QUOTE-BUY-OUT-AMOUNT-001", "11100000010"),
                _obs(mint, "X300", BUY_1M, "FIELD-QUOTE-BUY-OUT-AMOUNT-001", "1110000001"),
                _obs(mint, "X300", REVERSE_10M, "FIELD-QUOTE-SELL-OUT-AMOUNT-001", str(t0_10m)),
                _obs(mint, "X300", REVERSE_1M, "FIELD-QUOTE-SELL-OUT-AMOUNT-001", str(t0_1m)),
                _obs(mint, "Y900", REVERSE_10M, "FIELD-QUOTE-SELL-OUT-AMOUNT-001", str(h900_10m)),
                _obs(mint, "Y900", REVERSE_1M, "FIELD-QUOTE-SELL-OUT-AMOUNT-001", str(h900_1m)),
            ]
        )
    return rows


def _obs(mint: str, point: str, primitive: str, field_id: str, value: str) -> dict:
    return {
        "entity_id": mint,
        "point_id": point,
        "primitive_id": primitive,
        "state": "OBSERVED",
        "field_values": [
            {
                "field_id": field_id,
                "typed_value_or_null": value,
                "state": "OBSERVED",
                "missing_reason": None,
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()
