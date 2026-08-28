"""Zero-network-injectable wrappers for registered Jupiter observation primitives."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any
from urllib.parse import urlencode, urlsplit

from solana_alpha_lab.factory.observation_schedule import canonical_sha256, parse_utc, render_utc

API_HOST = "api.jup.ag"
SOL_MINT = "So11111111111111111111111111111111111111112"
BUY_AMOUNT = "10000000"
SLIPPAGE_BPS = "100"
ALLOWED_PATHS = frozenset(
    {
        "/tokens/v2/recent",
        "/tokens/v2/search",
        "/swap/v2/order",
    }
)
RECENT_URL = "https://api.jup.ag/tokens/v2/recent"


class ObservationPrimitiveError(ValueError):
    """Typed primitive execution failure."""


def request_sha256(*, method: str, url: str, body: Mapping[str, Any] | None, primitive_version: str) -> str:
    parsed = urlsplit(url)
    if parsed.username or parsed.password or "api-key" in url.casefold():
        raise ObservationPrimitiveError("SECRET_IN_REQUEST_IDENTITY")
    return canonical_sha256(
        {
            "method": method,
            "url": url,
            "body": body,
            "primitive_version": primitive_version,
        }
    )


def redact(value: object, redact_with: str | None) -> object:
    if redact_with and isinstance(value, str) and redact_with and redact_with in value:
        raise ObservationPrimitiveError("SECRET_LEAK")
    if isinstance(value, Mapping):
        return {str(key): redact(item, redact_with) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, redact_with) for item in value]
    return value


def _validate_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != API_HOST or parsed.port is not None:
        raise ObservationPrimitiveError("ENDPOINT_DRIFT")
    if parsed.path not in ALLOWED_PATHS:
        raise ObservationPrimitiveError("ENDPOINT_PATH_DRIFT")
    if parsed.username or parsed.password or parsed.fragment:
        raise ObservationPrimitiveError("ENDPOINT_USERINFO_FORBIDDEN")


def search_url(mints: Sequence[str]) -> str:
    ordered = list(mints)
    query = ",".join(ordered)
    return f"https://api.jup.ag/tokens/v2/search?{urlencode({'query': query})}"


def quote_url(*, input_mint: str, output_mint: str, amount: str) -> str:
    return (
        "https://api.jup.ag/swap/v2/order?"
        + urlencode(
            {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": amount,
                "slippageBps": SLIPPAGE_BPS,
            }
        )
    )


def execute_primitive(
    *,
    primitive_id: str,
    primitive_version: str,
    method: str,
    url: str,
    opener: object,
    clock: Callable[[], datetime],
    redact_with: str | None = None,
    expected_entities: Sequence[str] | None = None,
    schema_required_keys: Sequence[str] | None = None,
) -> dict[str, Any]:
    _validate_url(url)
    digest = request_sha256(
        method=method,
        url=url,
        body=None,
        primitive_version=primitive_version,
    )
    observed_at = render_utc(clock())
    try:
        result = opener.open(url)  # type: ignore[union-attr]
    except TimeoutError:
        return {
            "status": "MISSING_TYPED",
            "missing_reason": "TIMEOUT",
            "request_sha256": digest,
            "observed_at": observed_at,
            "response_sha256": None,
            "entities": {},
        }
    except OSError:
        return {
            "status": "MISSING_TYPED",
            "missing_reason": "HTTP_ERROR",
            "request_sha256": digest,
            "observed_at": observed_at,
            "response_sha256": None,
            "entities": {},
        }
    if not isinstance(result, Mapping):
        raise ObservationPrimitiveError("INVALID_RESPONSE")
    if result.get("url_has_api_key") is True:
        raise ObservationPrimitiveError("SECRET_LEAK")
    raw_status = result.get("http_status")
    if raw_status is None:
        raw_status = result.get("status")
    if raw_status is None:
        return {
            "status": "MISSING_TYPED",
            "missing_reason": "PROVIDER_SCHEMA_DRIFT",
            "request_sha256": digest,
            "observed_at": observed_at,
            "response_sha256": None,
            "entities": {},
        }
    status = int(raw_status)
    body = result.get("body")
    if redact_with:
        payload_text = json.dumps(result, default=str)
        if redact_with in payload_text:
            raise ObservationPrimitiveError("SECRET_LEAK")
    if status in {404}:
        return {
            "status": "MISSING_TYPED",
            "missing_reason": "NO_ROUTE",
            "request_sha256": digest,
            "observed_at": observed_at,
            "response_sha256": None,
            "entities": {},
        }
    if status >= 400:
        return {
            "status": "MISSING_TYPED",
            "missing_reason": "HTTP_ERROR",
            "request_sha256": digest,
            "observed_at": observed_at,
            "response_sha256": None,
            "entities": {},
        }
    if schema_required_keys:
        if not isinstance(body, Mapping) and not isinstance(body, list):
            return {
                "status": "MISSING_TYPED",
                "missing_reason": "PROVIDER_SCHEMA_DRIFT",
                "request_sha256": digest,
                "observed_at": observed_at,
                "response_sha256": None,
                "entities": {},
            }
        sample = body if isinstance(body, Mapping) else (body[0] if body else {})
        if isinstance(sample, Mapping) and any(key not in sample for key in schema_required_keys):
            return {
                "status": "MISSING_TYPED",
                "missing_reason": "PROVIDER_SCHEMA_DRIFT",
                "request_sha256": digest,
                "observed_at": observed_at,
                "response_sha256": None,
                "entities": {},
            }
    response_hash = canonical_sha256(body)
    entities: dict[str, Any] = {}
    if expected_entities:
        if isinstance(body, list):
            indexed: dict[str, Any] = {}
            for row in body:
                if isinstance(row, Mapping):
                    mint = str(row.get("id") or row.get("mint") or "")
                    if mint:
                        indexed[mint] = row
            for entity_id in expected_entities:
                row = indexed.get(entity_id)
                if row is None:
                    entities[entity_id] = {
                        "status": "MISSING_TYPED",
                        "missing_reason": "ENTITY_ABSENT_FROM_RESPONSE",
                    }
                else:
                    entities[entity_id] = {"status": "OBSERVED", "row": row}
        elif isinstance(body, Mapping):
            mint = str(body.get("id") or body.get("mint") or "")
            for entity_id in expected_entities:
                if mint and mint != entity_id:
                    entities[entity_id] = {
                        "status": "MISSING_TYPED",
                        "missing_reason": "ENTITY_ABSENT_FROM_RESPONSE",
                    }
                else:
                    entities[entity_id] = {"status": "OBSERVED", "row": body}
    return {
        "status": "OBSERVED",
        "missing_reason": None,
        "request_sha256": digest,
        "observed_at": observed_at,
        "response_sha256": response_hash,
        "body": body,
        "entities": entities,
        "primitive_id": primitive_id,
    }


def parse_first_seen(row: Mapping[str, Any]) -> datetime | None:
    raw = row.get("first_seen_at")
    if isinstance(raw, str):
        try:
            return parse_utc(raw if raw.endswith("Z") else raw + "Z")
        except Exception:
            return None
    return None


def parse_anchor(row: Mapping[str, Any]) -> datetime | None:
    first_pool = row.get("firstPool")
    if isinstance(first_pool, Mapping):
        created = first_pool.get("createdAt")
        if isinstance(created, str):
            try:
                return parse_utc(created if created.endswith("Z") else created + "Z")
            except Exception:
                return None
    created = row.get("createdAt") or row.get("firstPoolCreatedAt")
    if isinstance(created, str):
        try:
            return parse_utc(created if created.endswith("Z") else created + "Z")
        except Exception:
            return None
    return None


__all__ = [
    "BUY_AMOUNT",
    "ObservationPrimitiveError",
    "RECENT_URL",
    "SOL_MINT",
    "execute_primitive",
    "parse_anchor",
    "parse_first_seen",
    "quote_url",
    "redact",
    "request_sha256",
    "search_url",
]
