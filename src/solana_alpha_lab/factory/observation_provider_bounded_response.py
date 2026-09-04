"""Bounded Jupiter ObservationSchedule response body and JSON parse.

ADOPT: stdlib chunked ``read(n)`` plus ``MAX+1`` sentinel, matching
``provider_smoke_transport._read_bounded`` and
``perform_credentialed_get(..., max_response_bytes=2_000_000)``.
No new package.

Byte budget (MAX_RESPONSE_BYTES = 2_000_000):

* Official Tokens V2 ``/recent`` is a bounded recent-token feed (default 30
  mints), not an unbounded dump. A multi-GB body is not valid expected
  payload semantics.
* Production search batches at most 100 mints (primitive ``max_batch_size``).
* Quote ``/swap/v2/order`` is a single-order object, much smaller.
* Same-family transport already uses 2 MiB
  (``EXPECTED_MAX_RESPONSE_BYTES``, quote-native ``max_response_bytes``).
* In-repo retained Jupiter JSON envelopes are ~1–125 KiB; 2 MiB is >=16x
  that observed shape and covers 100 rich search rows at ~20 KiB/row.

Content-Length is an early reject only. The actual streamed byte counter is
authoritative. Oversize and invalid JSON never return partial parsed values
and never attach the rejected body to exceptions or results.
"""

from __future__ import annotations

import json
from typing import Any

# Same-family proven cap. See module docstring for the safety margin.
MAX_RESPONSE_BYTES = 2_000_000
READ_SENTINEL_BYTES = 1
_READ_CHUNK_BYTES = 65_536
RESPONSE_BODY_TOO_LARGE = "RESPONSE_BODY_TOO_LARGE"
RESPONSE_JSON_INVALID = "RESPONSE_JSON_INVALID"


class ResponseBodyTooLargeError(Exception):
    """Provider body exceeded the explicit byte budget."""

    def __init__(self) -> None:
        super().__init__(RESPONSE_BODY_TOO_LARGE)


class ResponseJsonInvalidError(Exception):
    """Provider body was not bounded UTF-8 JSON object/array."""

    def __init__(self) -> None:
        super().__init__(RESPONSE_JSON_INVALID)


def _declared_content_length(stream: object) -> int | None:
    length = getattr(stream, "length", None)
    if isinstance(length, int) and length >= 0:
        return length
    headers = getattr(stream, "headers", None)
    if headers is None:
        return None
    getter = getattr(headers, "get", None)
    if not callable(getter):
        return None
    raw = getter("Content-Length")
    if raw is None:
        raw = getter("content-length")
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return value


def read_bounded_http_body(
    stream: object,
    *,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> bytes:
    """Read at most ``max_bytes``; one extra sentinel byte detects oversize."""

    if max_bytes <= 0:
        raise ResponseBodyTooLargeError()
    declared = _declared_content_length(stream)
    if declared is not None and declared > max_bytes:
        raise ResponseBodyTooLargeError()
    read_fn = getattr(stream, "read", None)
    if not callable(read_fn):
        raise ResponseJsonInvalidError()
    chunks: list[bytes] = []
    total = 0
    budget = max_bytes + READ_SENTINEL_BYTES
    while True:
        remaining = budget - total
        if remaining <= 0:
            raise ResponseBodyTooLargeError()
        want = min(_READ_CHUNK_BYTES, remaining)
        piece = read_fn(want)
        if piece is None:
            break
        if isinstance(piece, memoryview):
            piece = piece.tobytes()
        elif isinstance(piece, bytearray):
            piece = bytes(piece)
        if not isinstance(piece, bytes):
            raise ResponseJsonInvalidError()
        if not piece:
            break
        if len(piece) > want:
            piece = piece[:want]
        if total + len(piece) > max_bytes:
            raise ResponseBodyTooLargeError()
        total += len(piece)
        chunks.append(piece)
        if len(piece) < want:
            break
    return b"".join(chunks)


def _json_container_prefix(body: bytes) -> bool:
    index = 0
    length = len(body)
    while index < length and body[index] in b" \t\r\n":
        index += 1
    return index < length and body[index] in b"[{"


def parse_bounded_json(
    body: bytes,
    *,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> Any:
    if len(body) > max_bytes:
        raise ResponseBodyTooLargeError()
    if not _json_container_prefix(body):
        raise ResponseJsonInvalidError()
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise ResponseJsonInvalidError() from None
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, RecursionError, ValueError):
        raise ResponseJsonInvalidError() from None
    if not isinstance(parsed, (dict, list)):
        raise ResponseJsonInvalidError()
    return parsed


__all__ = [
    "MAX_RESPONSE_BYTES",
    "READ_SENTINEL_BYTES",
    "RESPONSE_BODY_TOO_LARGE",
    "RESPONSE_JSON_INVALID",
    "ResponseBodyTooLargeError",
    "ResponseJsonInvalidError",
    "parse_bounded_json",
    "read_bounded_http_body",
]
