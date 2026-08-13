"""One-shot retained runtime for the TASK-30 A17 discriminator."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .lifecycle_discovery_transport import BoundProbeRequest, HttpCapture, WssCapture
from .task30_active_pool_route_yield import (
    OWNER_RUNTIME_PHRASE,
    POPCAT_MINT,
    ActivePoolRouteYieldError,
    acknowledged_zero_window,
    bind_pool_activity_request,
    bind_pool_logs_subscribe,
    classify_route_window,
    evaluate_active_pool_route_yield_policy,
    select_active_pool,
)


LOGICAL_ROOT = "local/task30_active_pool_route_yield"
DISCOVERY_URL = f"https://api.dexscreener.com/token-pairs/v1/solana/{POPCAT_MINT}"
_NONCE = re.compile(r"^[0-9a-f]{8}$")


class ActivePoolRouteYieldRuntimeError(RuntimeError):
    """A future A17 runtime crossed its exact owner, path or call boundary."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ActivePoolRouteYieldRuntimeError(code)


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    except (TypeError, ValueError) as exc:
        raise ActivePoolRouteYieldRuntimeError("JSON_VALUE_INVALID") from exc


def _utc(value: datetime) -> str:
    _require(value.tzinfo is not None, "AWARE_CLOCK_REQUIRED")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _publish(path: Path, body: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(body)
    except (FileExistsError, OSError) as exc:
        raise ActivePoolRouteYieldRuntimeError("IMMUTABLE_WRITE_FAILED") from exc


def _safe_root(repository_root: Path, raw_root: Path) -> None:
    _require(repository_root.is_absolute() and raw_root.is_absolute(), "ABSOLUTE_ROOT_REQUIRED")
    _require(
        raw_root.resolve(strict=False)
        == (repository_root / LOGICAL_ROOT).resolve(strict=False),
        "RAW_ROOT_DRIFT",
    )
    current = repository_root
    for part in Path(LOGICAL_ROOT).parts:
        current /= part
        if current.exists():
            _require(not current.is_symlink(), "RAW_ROOT_SYMLINK_FORBIDDEN")


@dataclass(frozen=True, slots=True, repr=False)
class KeylessGetRequest:
    """One immutable public request without query, credential or body."""

    request_id: str = "task30-a17-active-pool-discovery"
    provider: str = "DEXSCREENER"
    transport: str = "HTTP"
    method: str = "GET"
    url: str = field(default=DISCOVERY_URL, repr=False)
    headers: tuple[tuple[str, str], ...] = field(
        default=(("accept", "application/json"), ("user-agent", "smial-task30-a17/1.0")),
        repr=False,
    )
    body: bytes = field(default=b"", repr=False)

    def __post_init__(self) -> None:
        _require(self.url == DISCOVERY_URL, "DISCOVERY_URL_DRIFT")
        _require(self.method == "GET" and self.body == b"", "DISCOVERY_REQUEST_DRIFT")

    def __repr__(self) -> str:
        return "KeylessGetRequest(provider='DEXSCREENER', method='GET', url=<redacted>)"


def _discovery_request() -> KeylessGetRequest:
    return KeylessGetRequest()


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _parse_discovery(capture: HttpCapture) -> tuple[bool, object]:
    if capture.terminal_class != "SUCCESS" or capture.status_code != 200:
        return False, None
    try:
        document = json.loads(capture.body, object_pairs_hook=_unique_json_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return False, None
    if type(document) is not list:
        return False, None
    required = frozenset(
        {"chainId", "dexId", "pairAddress", "baseToken", "quoteToken", "txns", "liquidity"}
    )
    for row in document:
        if not isinstance(row, Mapping) or not required.issubset(row):
            return False, None
        base, quote, txns, liquidity = (
            row.get("baseToken"),
            row.get("quoteToken"),
            row.get("txns"),
            row.get("liquidity"),
        )
        if not all(isinstance(value, Mapping) for value in (base, quote, txns, liquidity)):
            return False, None
        m5 = txns.get("m5")
        if (
            not isinstance(m5, Mapping)
            or type(m5.get("buys")) is not int
            or type(m5.get("sells")) is not int
            or type(row.get("chainId")) is not str
            or type(row.get("dexId")) is not str
            or type(row.get("pairAddress")) is not str
            or type(base.get("address")) is not str
            or type(quote.get("address")) is not str
        ):
            return False, None
        liquidity_usd = liquidity.get("usd")
        if liquidity_usd is not None and type(liquidity_usd) not in {int, float}:
            return False, None
    return True, document


def _sanitize_selection(selection: Mapping[str, object] | None) -> dict[str, object] | None:
    return None if selection is None else dict(selection)


def _terminal_shape(
    state: str,
    *,
    error_stage: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "terminal_state": state,
        "unknown": state == "TRANSPORT_OR_COVERAGE_UNKNOWN",
        "rpc_requests": 0,
        "interior_signature_count": 0,
        "window_bracketed": False,
        "route_yield": state == "ROUTE_YIELD_OBSERVED_TECHNICAL_ONLY",
        "price": False,
        "volume": False,
        "zero_volume": False,
        "empty_interval": False,
        "interval_complete": False,
        "pit_admissible": False,
        "task30_trial": False,
        "task30_acceptance": False,
        "numeric_netreturn": False,
        "replan": {
            "required": state != "ROUTE_YIELD_OBSERVED_TECHNICAL_ONLY",
            "terminal_atom": True,
            "automatic_suffix_atom": False,
            "allowed_next_decisions": ["PIVOT", "ACCEPT_UNKNOWN", "DEFER", "CLOSE"],
        },
    }
    if error_stage is not None:
        result["error_stage"] = error_stage
    return result


def _terminal_receipt(
    base: Mapping[str, object],
    state: str,
    *,
    provider_calls: int,
    helius_calls: int,
    terminal_at: str,
    error_stage: str | None = None,
) -> dict[str, object]:
    return {
        **base,
        **_terminal_shape(state, error_stage=error_stage),
        "provider_calls": provider_calls,
        "helius_calls": helius_calls,
        "terminal_at": terminal_at,
    }


def execute_active_pool_route_yield(
    config: Mapping[str, Any],
    registry: Mapping[str, Any],
    *,
    authority_phrase: str,
    repository_root: Path,
    raw_root: Path,
    discovery_exchange: Callable[..., HttpCapture],
    route_preflight: Callable[[], Mapping[str, object]],
    credential_loader: Callable[[str], str],
    wss_exchange: Callable[..., WssCapture],
    rpc_exchange: Callable[..., HttpCapture],
    clock: Callable[[], datetime],
    nonce_factory: Callable[[], str],
) -> dict[str, object]:
    """Execute the exact future sequence; tests inject every transport."""

    evaluate_active_pool_route_yield_policy(config, registry)
    _require(authority_phrase == OWNER_RUNTIME_PHRASE, "OWNER_AUTHORITY_MISMATCH")
    _safe_root(repository_root, raw_root)
    _require(not raw_root.exists() or not any(raw_root.glob("run=*")), "PRIOR_ATTEMPT_REQUIRES_NEW_GATE")
    started_at = clock()
    nonce = nonce_factory()
    _require(type(nonce) is str and _NONCE.fullmatch(nonce) is not None, "NONCE_INVALID")
    run_id = f"{started_at.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}-{nonce}"
    run_root = raw_root / f"run={run_id}"
    try:
        run_root.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise ActivePoolRouteYieldRuntimeError("ATTEMPT_ROOT_CREATE_FAILED") from exc

    intent = {
        "schema": "smial.task30.active-pool-route-yield-runtime-intent",
        "schema_version": "1.0",
        "run_id": run_id,
        "started_at": _utc(started_at),
        "authority_sha256": hashlib.sha256(authority_phrase.encode()).hexdigest(),
        "planned_calls": {"dexscreener_get": 1, "helius_wss": 1, "helius_rpc_conditional": 1},
        "retry": False,
        "reconnect": False,
        "fallback": False,
    }
    intent_body = _canonical(intent)
    _publish(run_root / "intent.json", intent_body)

    raw_objects: list[dict[str, object]] = [
        {"path": "intent.json", "bytes": len(intent_body), "sha256": hashlib.sha256(intent_body).hexdigest(), "observed_at": intent["started_at"]},
    ]
    base: dict[str, object] = {
        "run_id": run_id,
        "logical_run_root": f"{LOGICAL_ROOT}/run={run_id}",
        "selected_target": None,
        "raw_retention": "A4_EXACT_RETAINED",
        "retry": False,
        "reconnect": False,
        "fallback": False,
    }
    try:
        discovery = discovery_exchange(_discovery_request(), max_response_bytes=1_000_000)
    except Exception:
        receipt = _terminal_receipt(
            base,
            "TRANSPORT_OR_COVERAGE_UNKNOWN",
            provider_calls=1,
            helius_calls=0,
            terminal_at=_utc(clock()),
            error_stage="DISCOVERY_ADAPTER_FAILURE",
        )
        return _finalize(run_root, raw_objects, receipt)
    if type(discovery) is not HttpCapture:
        receipt = _terminal_receipt(
            base,
            "TRANSPORT_OR_COVERAGE_UNKNOWN",
            provider_calls=1,
            helius_calls=0,
            terminal_at=_utc(clock()),
            error_stage="DISCOVERY_CAPTURE_INVALID",
        )
        return _finalize(run_root, raw_objects, receipt)
    if len(discovery.body) > 1_000_000:
        receipt = _terminal_receipt(base, "TRANSPORT_OR_COVERAGE_UNKNOWN", provider_calls=1, helius_calls=0, terminal_at=_utc(clock()), error_stage="DISCOVERY_BYTE_CAP_EXCEEDED")
        return _finalize(run_root, raw_objects, receipt)
    discovery_at = clock()
    _publish(run_root / "dexscreener_response.json", discovery.body)
    discovery_valid, discovery_document = _parse_discovery(discovery)
    selection = select_active_pool(discovery_document) if discovery_valid else None
    raw_objects.append(
        {"path": "dexscreener_response.json", "bytes": len(discovery.body), "sha256": hashlib.sha256(discovery.body).hexdigest(), "observed_at": _utc(discovery_at)}
    )
    base = {
        **base,
        "selected_target": _sanitize_selection(selection),
    }
    if not discovery_valid:
        receipt = _terminal_receipt(base, "TRANSPORT_OR_COVERAGE_UNKNOWN", provider_calls=1, helius_calls=0, terminal_at=_utc(clock()))
        return _finalize(run_root, raw_objects, receipt)
    if selection is None:
        receipt = _terminal_receipt(base, "NO_ACTIVE_TARGET_STOP", provider_calls=1, helius_calls=0, terminal_at=_utc(clock()))
        return _finalize(run_root, raw_objects, receipt)

    try:
        preflight = route_preflight()
    except Exception:
        receipt = _terminal_receipt(base, "TRANSPORT_OR_COVERAGE_UNKNOWN", provider_calls=1, helius_calls=0, terminal_at=_utc(clock()), error_stage="HELIUS_PREFLIGHT_FAILURE")
        return _finalize(run_root, raw_objects, receipt)
    if not (
        isinstance(preflight, Mapping)
        and frozenset(preflight) == frozenset({"dns_resolved", "tcp_443"})
        and preflight.get("dns_resolved") is True
        and preflight.get("tcp_443") is True
    ):
        receipt = _terminal_receipt(base, "TRANSPORT_OR_COVERAGE_UNKNOWN", provider_calls=1, helius_calls=0, terminal_at=_utc(clock()), error_stage="HELIUS_PREFLIGHT_FAILED_CLOSED")
        return _finalize(run_root, raw_objects, receipt)

    pool = str(selection["pool_address"])
    try:
        key = credential_loader("HELIUS_API_KEY")
        stream_request = bind_pool_logs_subscribe(pool, key)
    except Exception:
        receipt = _terminal_receipt(base, "TRANSPORT_OR_COVERAGE_UNKNOWN", provider_calls=1, helius_calls=0, terminal_at=_utc(clock()), error_stage="CREDENTIAL_UNAVAILABLE_OR_INVALID")
        return _finalize(run_root, raw_objects, receipt)
    limits = config["runtime_limits"]
    _require(isinstance(limits, Mapping), "RUNTIME_LIMITS_REQUIRED")
    try:
        wss_capture = wss_exchange(
            stream_request,
            max_open_seconds=limits["max_wss_seconds"],
            max_stream_bytes=limits["max_stream_bytes"],
            max_notifications=limits["max_notifications"],
        )
    except Exception:
        receipt = _terminal_receipt(base, "TRANSPORT_OR_COVERAGE_UNKNOWN", provider_calls=2, helius_calls=1, terminal_at=_utc(clock()), error_stage="WSS_ADAPTER_FAILURE")
        return _finalize(run_root, raw_objects, receipt)
    if type(wss_capture) is not WssCapture:
        receipt = _terminal_receipt(base, "TRANSPORT_OR_COVERAGE_UNKNOWN", provider_calls=2, helius_calls=1, terminal_at=_utc(clock()), error_stage="WSS_CAPTURE_INVALID")
        return _finalize(run_root, raw_objects, receipt)
    stream_bytes = len(wss_capture.acknowledgement) + sum(
        len(body) for body in wss_capture.notifications
    )
    if (
        len(wss_capture.notifications) > int(limits["max_notifications"])
        or len(wss_capture.notification_observed_at) != len(wss_capture.notifications)
        or stream_bytes > int(limits["max_stream_bytes"])
        or len(wss_capture.acknowledgement) > int(limits["max_frame_bytes"])
        or any(len(body) > int(limits["max_frame_bytes"]) for body in wss_capture.notifications)
    ):
        receipt = _terminal_receipt(base, "TRANSPORT_OR_COVERAGE_UNKNOWN", provider_calls=2, helius_calls=1, terminal_at=_utc(clock()), error_stage="WSS_CAPTURE_BOUNDARY_INVALID")
        return _finalize(run_root, raw_objects, receipt)
    terminal_at = clock()
    if wss_capture.acknowledgement:
        _publish(run_root / "wss_acknowledgement.json", wss_capture.acknowledgement)
        raw_objects.append({"path": "wss_acknowledgement.json", "bytes": len(wss_capture.acknowledgement), "sha256": hashlib.sha256(wss_capture.acknowledgement).hexdigest(), "observed_at": _utc(wss_capture.acknowledgement_observed_at or terminal_at)})
    for index, body in enumerate(wss_capture.notifications):
        name = f"wss_notification_{index + 1:03d}.json"
        _publish(run_root / name, body)
        raw_objects.append({"path": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "observed_at": _utc(wss_capture.notification_observed_at[index])})

    rpc_capture: HttpCapture | None = None
    if acknowledged_zero_window(wss_capture):
        try:
            rpc_capture = rpc_exchange(
                bind_pool_activity_request(pool, key),
                max_response_bytes=limits["max_rpc_response_bytes"],
            )
        except Exception:
            receipt = _terminal_receipt(base, "TRANSPORT_OR_COVERAGE_UNKNOWN", provider_calls=3, helius_calls=2, terminal_at=_utc(clock()), error_stage="RPC_ADAPTER_FAILURE")
            return _finalize(run_root, raw_objects, receipt)
        if type(rpc_capture) is not HttpCapture:
            receipt = _terminal_receipt(base, "TRANSPORT_OR_COVERAGE_UNKNOWN", provider_calls=3, helius_calls=2, terminal_at=_utc(clock()), error_stage="RPC_CAPTURE_INVALID")
            return _finalize(run_root, raw_objects, receipt)
        if len(rpc_capture.body) > int(limits["max_rpc_response_bytes"]):
            receipt = _terminal_receipt(base, "TRANSPORT_OR_COVERAGE_UNKNOWN", provider_calls=3, helius_calls=2, terminal_at=_utc(clock()), error_stage="RPC_BYTE_CAP_EXCEEDED")
            return _finalize(run_root, raw_objects, receipt)
        _publish(run_root / "rpc_response.json", rpc_capture.body)
        raw_objects.append({"path": "rpc_response.json", "bytes": len(rpc_capture.body), "sha256": hashlib.sha256(rpc_capture.body).hexdigest(), "observed_at": _utc(clock())})

    try:
        classification = classify_route_window(
            config,
            registry,
            selection,
            wss_capture=wss_capture,
            rpc_capture=rpc_capture,
            terminal_observed_at=terminal_at,
        )
    except (ActivePoolRouteYieldError, KeyError, TypeError):
        receipt = _terminal_receipt(base, "TRANSPORT_OR_COVERAGE_UNKNOWN", provider_calls=2 + int(rpc_capture is not None), helius_calls=1 + int(rpc_capture is not None), terminal_at=_utc(clock()), error_stage="CLASSIFICATION_FAILURE")
        return _finalize(run_root, raw_objects, receipt)
    receipt = {
        **base,
        **classification,
        "provider_calls": 2 + int(rpc_capture is not None),
        "helius_calls": 1 + int(rpc_capture is not None),
        "terminal_at": _utc(clock()),
    }
    return _finalize(run_root, raw_objects, receipt)


def _finalize(
    run_root: Path,
    raw_objects: list[dict[str, object]],
    receipt: dict[str, object],
) -> dict[str, object]:
    manifest = {
        "schema": "smial.task30.active-pool-route-yield-raw-manifest",
        "schema_version": "1.0",
        "run_id": receipt["run_id"],
        "retention_class": "A4",
        "raw_objects": raw_objects,
    }
    manifest_body = _canonical(manifest)
    _publish(run_root / "raw_manifest.json", manifest_body)
    receipt["raw_manifest_sha256"] = hashlib.sha256(manifest_body).hexdigest()
    _publish(run_root / "terminal_receipt.json", _canonical(receipt))
    return receipt
