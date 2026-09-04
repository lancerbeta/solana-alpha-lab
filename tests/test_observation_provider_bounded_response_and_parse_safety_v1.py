"""OBSERVATION_PROVIDER_BOUNDED_RESPONSE_AND_PARSE_SAFETY_V1 proofs."""

from __future__ import annotations

import inspect
import json
import sys
import tempfile
import time
import tracemalloc
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.observation_primitives import (  # noqa: E402
    HTTP_CLASS_401,
    HTTP_CLASS_403,
    HTTP_CLASS_429,
    HTTP_CLASS_5XX,
    HTTP_CLASS_OK,
    HTTP_CLASS_TIMEOUT,
    HTTP_CLASS_TRANSPORT,
    execute_primitive,
)
from solana_alpha_lab.factory.observation_provider_bounded_response import (  # noqa: E402
    MAX_RESPONSE_BYTES,
    RESPONSE_BODY_TOO_LARGE,
    RESPONSE_JSON_INVALID,
    ResponseBodyTooLargeError,
    parse_bounded_json,
    read_bounded_http_body,
)
from solana_alpha_lab.factory.observation_provider_pacing import WallClock  # noqa: E402
from solana_alpha_lab.factory.observation_provider_wall_deadline import (  # noqa: E402
    ProviderWallDeadlineError,
    run_with_provider_wall_deadline,
)
from solana_alpha_lab.factory.observation_schedule import (  # noqa: E402
    canonical_sha256,
    load_observation_schedule,
    render_utc,
    schedule_sha256,
)
from solana_alpha_lab.factory.observation_schedule_runtime import (  # noqa: E402
    JupiterReadonlyOpener,
)
from solana_alpha_lab.factory.observation_schedule_store import (  # noqa: E402
    LEASE_SECONDS,
    ObservationScheduleStore,
)
from solana_alpha_lab.factory.observation_scheduler import tick_once  # noqa: E402

GIT_SHA = "d" * 40
NOW = datetime(2026, 9, 1, 0, 10, tzinfo=UTC)
RECENT = "https://api.jup.ag/tokens/v2/recent"
FIXTURE_KEY = "TEST_KEY_NOT_A_SECRET"
NORMAL_RECENT = b'[{"id":"MintA","liquidity":"2000"}]'
ADVERSARIAL_AVAILABLE = 32 * 1024 * 1024
SECRET_MARKER = "JUPITER_FAKE_KEY_DO_NOT_LEAK"


class _HttpLike:
    def __init__(
        self,
        payload: bytes,
        *,
        content_length: str | None = None,
        status: int = 200,
        ignore_limit: bool = False,
    ) -> None:
        self._payload = payload
        self._offset = 0
        self.status = status
        self.headers: dict[str, str] = {}
        if content_length is not None:
            self.headers["Content-Length"] = content_length
        self.bytes_returned = 0
        self.read_calls = 0
        self.ignore_limit = ignore_limit

    def read(self, n: int = -1) -> bytes:
        self.read_calls += 1
        remaining = self._payload[self._offset :]
        if self.ignore_limit or n is None or n < 0:
            take = remaining
        else:
            take = remaining[:n]
        self._offset += len(take)
        self.bytes_returned += len(take)
        return take

    def __enter__(self) -> _HttpLike:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class _ChunkedUnknownLength:
    """Chunked/unknown-length stream that honors read(n)."""

    def __init__(self, total_available: int, chunk: bytes = b"x") -> None:
        self._left = total_available
        self._chunk = chunk
        self.status = 200
        self.headers: dict[str, str] = {}
        self.bytes_returned = 0
        self.read_calls = 0

    def read(self, n: int = -1) -> bytes:
        self.read_calls += 1
        if n is None or n < 0:
            take_n = self._left
        else:
            take_n = min(self._left, n)
        take_n = max(0, take_n)
        self._left -= take_n
        self.bytes_returned += take_n
        # Repeat a one-byte pattern; not parsed on oversize.
        return (self._chunk * take_n)[:take_n]

    def __enter__(self) -> _ChunkedUnknownLength:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _clock() -> datetime:
    return NOW


def _hook_open(opener: JupiterReadonlyOpener, stream: object):
    return patch.object(opener._http, "open", return_value=stream)


def _hook_error(opener: JupiterReadonlyOpener, error: BaseException):
    return patch.object(opener._http, "open", side_effect=error)


def _primitive(opener: object) -> dict:
    return execute_primitive(
        primitive_id="PRIM-JUPITER-TOKENS-V2-RECENT-001",
        primitive_version="1.0",
        method="GET",
        url=RECENT,
        opener=opener,
        clock=_clock,
    )


def _near_ceiling_json() -> bytes:
    target = MAX_RESPONSE_BYTES - 16
    n_items = max(1, (target - 1) // 2)
    return ("[" + ",".join(["0"] * n_items) + "]").encode("ascii")


def _live_schedule_around(clock_now: datetime) -> dict:
    schedule = load_observation_schedule(
        ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
    )
    schedule = dict(schedule)
    activation = dict(schedule["activation"])
    activation["starts_at"] = render_utc(clock_now - timedelta(hours=1))
    activation["stops_admitting_at"] = render_utc(clock_now + timedelta(days=2))
    schedule["activation"] = activation
    schedule.pop("schedule_sha256", None)
    schedule["schedule_sha256"] = schedule_sha256(schedule)
    return schedule


def _activate(
    store: ObservationScheduleStore,
    schedule: dict,
    *,
    clock: datetime = NOW,
) -> str:
    from solana_alpha_lab.factory.observation_schedule_lifecycle import (
        _authority_policy,
        _minimum_expiry,
        _used_provider_route_ids,
        authorize_schedule,
        expected_authority_phrase,
    )

    activation_id = "ACT-BOUND-001"
    data_root = store.path.parent / "rdp"
    data_root.mkdir(parents=True, exist_ok=True)
    store.persist_registered_schedule(
        schedule_sha256=schedule["schedule_sha256"],
        schedule_key=schedule["schedule_key"],
        document=schedule,
        clock=clock,
    )
    min_expiry = _minimum_expiry(schedule)
    expires_at = render_utc(max(min_expiry, clock + timedelta(days=30)))
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
            policy_digest=canonical_sha256(policy),
        ),
        now=clock,
        producer_git_sha=GIT_SHA,
        expires_at=expires_at,
    )
    store.upsert_activation(
        {
            "schedule_sha256": schedule["schedule_sha256"],
            "activation_id": activation_id,
            "schedule_key": schedule["schedule_key"],
            "state": "ACTIVE",
            "authority_receipt_sha256": authority["receipt_sha256"],
            "starts_at": schedule["activation"]["starts_at"],
            "stops_admitting_at": schedule["activation"]["stops_admitting_at"],
            "payload": {},
        },
        clock=clock,
    )
    return activation_id


class CurrentFailureClassTests(unittest.TestCase):
    def test_unbounded_read_grows_materially_and_thread_wall_is_not_hard(self) -> None:
        stream = _ChunkedUnknownLength(16 * 1024 * 1024)
        tracemalloc.start()
        dumped = stream.read()
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertEqual(len(dumped), 16 * 1024 * 1024)
        self.assertGreaterEqual(peak, 16 * 1024 * 1024)

        body = ("[" + ",".join(["1"] * 2_000_000) + "]").encode("ascii")
        wall = 0.05
        started = time.perf_counter()
        fired = False
        try:
            run_with_provider_wall_deadline(
                lambda: json.loads(body.decode("utf-8")),
                wall_seconds=wall,
                heartbeat_every_seconds=0.02,
            )
        except ProviderWallDeadlineError:
            fired = True
        elapsed = time.perf_counter() - started
        self.assertFalse(fired)
        self.assertGreater(elapsed, wall)

    def test_production_opener_no_longer_calls_unbounded_read(self) -> None:
        source = inspect.getsource(JupiterReadonlyOpener.open)
        self.assertNotRegex(source, r"response\.read\(\s*\)")
        self.assertIn("read_bounded_http_body", source)
        self.assertIn("parse_bounded_json", source)


class BoundedTransportTests(unittest.TestCase):
    def test_normal_recent_unchanged(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        with patch.object(
            opener._http, "open", side_effect=lambda *a, **k: _HttpLike(NORMAL_RECENT)
        ):
            opened = opener.open(RECENT)
            primitive = _primitive(opener)
        self.assertEqual(opened["http_status"], 200)
        self.assertEqual(opened["body"], [{"id": "MintA", "liquidity": "2000"}])
        self.assertEqual(primitive["status"], "OBSERVED")
        self.assertEqual(primitive["http_class"], HTTP_CLASS_OK)
        self.assertEqual(primitive["http_status"], 200)

    def test_http_error_classes_unchanged(self) -> None:
        cases = (
            (401, HTTP_CLASS_401),
            (403, HTTP_CLASS_403),
            (429, HTTP_CLASS_429),
            (503, HTTP_CLASS_5XX),
        )
        for status, http_class in cases:
            opener = JupiterReadonlyOpener(FIXTURE_KEY)
            err = HTTPError(RECENT, status, "denied", hdrs={}, fp=None)
            with _hook_error(opener, err):
                opened = opener.open(RECENT)
                primitive = _primitive(opener)
            self.assertEqual(opened["http_status"], status)
            self.assertIsNone(opened["body"])
            self.assertEqual(primitive["http_status"], status)
            self.assertEqual(primitive["http_class"], http_class)

    def test_socket_timeout_unchanged(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        with _hook_error(opener, URLError(TimeoutError("timed out"))):
            primitive = _primitive(opener)
        self.assertEqual(primitive["http_class"], HTTP_CLASS_TIMEOUT)
        self.assertEqual(primitive["missing_reason"], "TIMEOUT")
        self.assertIsNone(primitive["http_status"])

    def test_oversized_content_length_rejected_without_read(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        stream = _HttpLike(
            b'[{"id":"MintA"}]',
            content_length=str(MAX_RESPONSE_BYTES + 1),
        )
        with _hook_open(opener, stream):
            with self.assertRaises(ResponseBodyTooLargeError) as ctx:
                opener.open(RECENT)
            primitive = _primitive(opener)
        self.assertEqual(str(ctx.exception), RESPONSE_BODY_TOO_LARGE)
        self.assertEqual(stream.read_calls, 0)
        self.assertEqual(stream.bytes_returned, 0)
        self.assertEqual(primitive["status"], "MISSING_TYPED")
        self.assertEqual(primitive["missing_reason"], RESPONSE_BODY_TOO_LARGE)
        self.assertEqual(primitive["http_class"], HTTP_CLASS_TRANSPORT)
        self.assertIsNone(primitive.get("body"))
        self.assertNotIn("xxxx", str(ctx.exception))

    def test_oversized_chunked_unknown_length_rejected_by_byte_counter(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        stream = _ChunkedUnknownLength(ADVERSARIAL_AVAILABLE)
        tracemalloc.start()
        with _hook_open(opener, stream):
            with self.assertRaises(ResponseBodyTooLargeError):
                opener.open(RECENT)
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertLessEqual(stream.bytes_returned, MAX_RESPONSE_BYTES + 65536)
        self.assertLess(stream.bytes_returned, ADVERSARIAL_AVAILABLE)
        self.assertLess(peak, 8 * 1024 * 1024)
        stream2 = _ChunkedUnknownLength(ADVERSARIAL_AVAILABLE)
        with _hook_open(opener, stream2):
            primitive = _primitive(opener)
        self.assertEqual(primitive["missing_reason"], RESPONSE_BODY_TOO_LARGE)
        self.assertIsNone(primitive.get("body"))

    def test_malformed_bounded_json_typed(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        stream = _HttpLike(b"{not-json")
        with _hook_open(opener, stream):
            primitive = _primitive(opener)
        self.assertEqual(primitive["status"], "MISSING_TYPED")
        self.assertEqual(primitive["missing_reason"], RESPONSE_JSON_INVALID)
        self.assertEqual(primitive["http_class"], HTTP_CLASS_TRANSPORT)
        self.assertIsNone(primitive.get("body"))

    def test_huge_int_inside_container_is_typed_invalid_quickly(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        payload = b'{"n":' + (b"1" * 500) + b"}"
        stream = _HttpLike(payload)
        started = time.perf_counter()
        with _hook_open(opener, stream):
            primitive = _primitive(opener)
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 1.0)
        self.assertEqual(primitive["missing_reason"], RESPONSE_JSON_INVALID)

    def test_ordinary_json_numbers_still_parse(self) -> None:
        parsed = parse_bounded_json(b'{"usdPrice":1.25,"holderCount":12}')
        self.assertEqual(parsed["usdPrice"], 1.25)
        self.assertEqual(parsed["holderCount"], 12)

    def test_non_container_json_rejected_without_huge_int_parse(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        stream = _HttpLike(b"1" * 200_000)
        started = time.perf_counter()
        with _hook_open(opener, stream):
            primitive = _primitive(opener)
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 1.0)
        self.assertEqual(primitive["missing_reason"], RESPONSE_JSON_INVALID)

    def test_worst_case_allowed_json_parse_has_lease_headroom(self) -> None:
        body = _near_ceiling_json()
        self.assertLessEqual(len(body), MAX_RESPONSE_BYTES)
        self.assertGreater(len(body), MAX_RESPONSE_BYTES * 0.9)
        started = time.perf_counter()
        parsed = parse_bounded_json(body)
        elapsed = time.perf_counter() - started
        self.assertIsInstance(parsed, list)
        # Wall 60s / lease 120s: require >100x headroom vs lease.
        self.assertLess(elapsed, 1.2)
        self.assertLess(elapsed * 100, LEASE_SECONDS)

        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        stream = _HttpLike(body)
        started = time.perf_counter()
        with _hook_open(opener, stream):
            opened = opener.open(RECENT)
        elapsed_open = time.perf_counter() - started
        self.assertEqual(opened["http_status"], 200)
        self.assertIsInstance(opened["body"], list)
        self.assertLess(elapsed_open, 1.2)

    def test_no_secret_in_oversize_or_invalid_surfaces(self) -> None:
        opener = JupiterReadonlyOpener(SECRET_MARKER)
        oversize = _HttpLike(
            b"[]",
            content_length=str(MAX_RESPONSE_BYTES + 8),
        )
        with _hook_open(opener, oversize):
            with self.assertRaises(ResponseBodyTooLargeError) as ctx:
                opener.open(RECENT)
            primitive = _primitive(opener)
        blob = json.dumps({"exc": str(ctx.exception), "primitive": primitive}, default=str)
        self.assertNotIn(SECRET_MARKER, blob)
        self.assertNotIn(SECRET_MARKER, str(ctx.exception))
        malformed = _HttpLike(b"{bad")
        opener2 = JupiterReadonlyOpener(SECRET_MARKER)
        with _hook_open(opener2, malformed):
            primitive2 = _primitive(opener2)
        self.assertNotIn(SECRET_MARKER, json.dumps(primitive2, default=str))


class BoundedLedgerAndLeaseTests(unittest.TestCase):
    def test_handled_oversize_exits_started_and_does_not_lease_fence(self) -> None:
        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        stream = _ChunkedUnknownLength(ADVERSARIAL_AVAILABLE)
        with _hook_open(opener, stream):
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
                store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
                try:
                    data_root = Path(tmp) / "rdp"
                    data_root.mkdir()
                    clock = WallClock()
                    act_now = clock.now()
                    schedule = _live_schedule_around(act_now)
                    activation_id = _activate(store, schedule, clock=act_now)
                    result = tick_once(
                        root=ROOT,
                        data_root=data_root,
                        store=store,
                        schedule=schedule,
                        activation_id=activation_id,
                        now=clock.now(),
                        clock=clock,
                        opener=opener,
                        producer_git_sha=GIT_SHA,
                        provider_call_wall_seconds=60,
                    )
                    self.assertNotEqual(result.get("terminal"), "LEASE_FENCED")
                    rows = store._conn.execute(
                        "SELECT state, payload_json FROM call_ledger WHERE primitive_id=?",
                        ("PRIM-JUPITER-TOKENS-V2-RECENT-001",),
                    ).fetchall()
                    self.assertTrue(rows)
                    self.assertTrue(all(str(row[0]) != "STARTED" for row in rows))
                    payloads = [json.loads(str(row[1] or "{}")) for row in rows]
                    self.assertTrue(
                        any(
                            payload.get("missing_reason") == RESPONSE_BODY_TOO_LARGE
                            for payload in payloads
                        ),
                        msg=payloads,
                    )
                    dumped = json.dumps(payloads)
                    self.assertLess(len(dumped), 50_000)
                    self.assertNotIn("x" * 1000, dumped)
                finally:
                    store.close()

    def test_restart_after_started_remains_in_flight_indeterminate(self) -> None:
        from solana_alpha_lab.factory.observation_primitives import (
            RECENT_URL,
            call_occurrence_id,
            request_sha256,
        )
        from solana_alpha_lab.factory.observation_scheduler import poll_slot_id

        schedule = load_observation_schedule(
            ROOT, "tests/fixtures/observation_schedule/x300_y900.yaml"
        )
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = ObservationScheduleStore(Path(tmp) / "ops.sqlite")
            try:
                data_root = Path(tmp) / "rdp"
                data_root.mkdir()
                activation_id = _activate(store, schedule)
                tick_now = NOW + timedelta(minutes=15)
                digest = schedule["schedule_sha256"]
                request_digest = request_sha256(
                    method="GET", url=RECENT_URL, body=None, primitive_version="1.0"
                )
                slot = poll_slot_id(
                    primitive_id=str(schedule["source_poll"]["primitive_id"]),
                    query_profile_id=str(schedule["source_poll"]["query_profile_id"]),
                    period_seconds=int(schedule["source_poll"]["period_seconds"]),
                    now=tick_now,
                    schedule_sha256=digest,
                    activation_id=activation_id,
                )
                occurrence = call_occurrence_id(
                    schedule_sha256=digest,
                    activation_id=activation_id,
                    primitive_id="PRIM-JUPITER-TOKENS-V2-RECENT-001",
                    point_id="DISCOVERY",
                    due_at=slot,
                    claim_identity_set=(),
                    request_digest=request_digest,
                )
                token = store.acquire_lease("crash-sim", clock=tick_now)
                self.assertIsNotNone(token)
                store.start_call(
                    request_sha256=request_digest,
                    call_occurrence_id=occurrence,
                    attempt_id="ATT-CRASH",
                    primitive_id="PRIM-JUPITER-TOKENS-V2-RECENT-001",
                    payload={"url": RECENT_URL, "poll_slot_id": slot},
                    clock=tick_now,
                )
                store.release_lease(str(token))
                self.assertEqual(store.call_state(occurrence), "STARTED")
                opener = JupiterReadonlyOpener(FIXTURE_KEY)
                stream = _HttpLike(NORMAL_RECENT)
                with _hook_open(opener, stream):
                    tick_once(
                        root=ROOT,
                        data_root=data_root,
                        store=store,
                        schedule=schedule,
                        activation_id=activation_id,
                        now=tick_now,
                        opener=opener,
                        producer_git_sha=GIT_SHA,
                        provider_call_wall_seconds=30,
                    )
                self.assertEqual(store.call_state(occurrence), "STARTED")
                self.assertEqual(stream.read_calls, 0)
            finally:
                store.close()


class BoundedHelperTests(unittest.TestCase):
    def test_content_length_untrusted_still_counts_bytes(self) -> None:
        payload = b"[" + (b"1," * (MAX_RESPONSE_BYTES // 2)) + b"1]"
        stream = _HttpLike(payload, content_length="12")
        with self.assertRaises(ResponseBodyTooLargeError):
            read_bounded_http_body(stream)
        self.assertGreater(stream.bytes_returned, 12)

    def test_budget_documented_not_magic_only(self) -> None:
        self.assertEqual(MAX_RESPONSE_BYTES, 2_000_000)
        doc = Path(
            ROOT,
            "src/solana_alpha_lab/factory/observation_provider_bounded_response.py",
        ).read_text(encoding="utf-8")
        self.assertIn("default 30", doc)
        self.assertIn("16x", doc)
        self.assertIn("2_000_000", doc)

    def test_zero_arg_read_small_body_accepted(self) -> None:
        class _ZeroArg:
            status = 200
            headers: dict[str, str] = {}

            def read(self) -> bytes:
                return b'{"outAmount":"1"}'

            def __enter__(self) -> _ZeroArg:
                return self

            def __exit__(self, *args: object) -> None:
                return None

        opener = JupiterReadonlyOpener(FIXTURE_KEY)
        with _hook_open(opener, _ZeroArg()):
            opened = opener.open(RECENT)
        self.assertEqual(opened["body"], {"outAmount": "1"})

    def test_lying_sized_read_over_want_is_too_large(self) -> None:
        stream = _HttpLike(b"[" + (b"1," * 1000) + b"1]", ignore_limit=True)
        with self.assertRaises(ResponseBodyTooLargeError):
            read_bounded_http_body(stream, max_bytes=64)


    def test_wall_module_does_not_claim_gil_hard_kill(self) -> None:
        text = Path(
            ROOT,
            "src/solana_alpha_lab/factory/observation_provider_wall_deadline.py",
        ).read_text(encoding="utf-8")
        self.assertIn("not a GIL-preempting hard kill", text)
        self.assertIn("Bounded response + bounded parse", text)
        self.assertNotIn("Hard end-to-end provider-call wall deadline exceeded", text)
        self.assertNotIn("with the hard provider-call wall deadline", text)


if __name__ == "__main__":
    unittest.main()
