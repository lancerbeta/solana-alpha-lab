"""Append-only successor resolver for provider-route capabilities."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from .provider_route_capability_registry import (
    ProviderRouteRegistryError,
    validate_provider_route_capability_registry,
)


V1_SHA256 = "ea44843f7ee7e8116a5599e7e38a8802e416f963ed6e0020448e33db898b7598"
LEGACY_ROUTE_HASHES = {
    "DEXSCREENER-SOLANA-TOKEN-PAIRS-KEYLESS-001": "c5d7861a4f3074784d1ecfa5614e1617be37dde2fb3e7c28f03ec5d3dd8e0055",
    "HELIUS-SOLANA-GET-SIGNATURES-001": "8852673f88c310d9e9c098a03fdcb2360150a2cfc242cf346637ac5fdd44f46d",
}
NON_CLAIMS = {
    "provider_reliability": False,
    "data_completeness": False,
    "market_activity": False,
    "task30_trial": False,
    "alpha": False,
    "numeric_netreturn": False,
}
UPDATE_POLICY = {
    "observed_receipt_required": True,
    "preserve_receipt_history": True,
    "separate_last_success": True,
    "registry_gap_is_unavailability": False,
    "automatic_routing": False,
    "authority_granted": False,
}
EXPECTED_WSS_ROUTE = {
    "route_id": "HELIUS-SOLANA-LOGS-SUBSCRIBE-001",
    "provider": "HELIUS",
    "endpoint_family": "standard-wss/logsSubscribe",
    "network": "solana",
    "access_class": "LOCAL_ENV_CREDENTIAL",
    "operation": "LOGS_SUBSCRIBE_MENTIONS",
    "protocol": "WSS_JSON_RPC",
    "runtime": {
        "client": "PYTHON_WEBSOCKETS",
        "version_source": "CODEX_WORKSPACE_DEPENDENCY",
        "tls_engine": "OPENSSL",
        "observed_result": "SUBSCRIPTION_ACCEPTED",
    },
    "preflight": {
        "kind": "DNS_TCP",
        "steps": ["DNS", "TCP_443"],
        "consumes_credential": False,
        "consumes_attempt": False,
    },
    "last_success": {
        "observed_at": "2026-08-12T09:27:53.436278Z",
        "transport_status": "SUBSCRIPTION_ACCEPTED",
        "response_bytes": 71,
        "response_sha256": "3403dc7c4f2b3728b19e08f41522c4471fe2ebd0f007e931d07b13cd84529172",
        "evidence_id": "T30-A15P-STANDARD-POOL-LOGS-RUNTIME-001",
    },
    "last_observation": {
        "observed_at": "2026-08-12T09:37:53.059095Z",
        "terminal_class": "BOUND_REACHED",
        "layer": "DATA",
        "transport_status": "ELAPSED_CAP",
        "response_bytes": 71,
        "response_sha256": "3403dc7c4f2b3728b19e08f41522c4471fe2ebd0f007e931d07b13cd84529172",
        "error_fingerprint": None,
        "evidence_id": "T30-A15P-STANDARD-POOL-LOGS-RUNTIME-001",
    },
    "known_failures": [],
    "execution_policy": {
        "retry": False,
        "fallback": False,
        "automatic_selection": False,
        "authority_granted": False,
    },
    "evidence": {
        "last_observation_receipt": "a4://task30_standard_pool_logs/run=20260812T092752Z-f96d593f",
        "raw_retention": "A4_OUTSIDE_GIT",
    },
    "non_claims": NON_CLAIMS,
}
ROOT_FIELDS = frozenset(
    {"schema", "schema_version", "registry_id", "as_of", "supersedes", "update_policy", "routes", "non_claims"}
)


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    except (TypeError, ValueError) as exc:
        raise ProviderRouteRegistryError("REGISTRY_VALUE_INVALID") from exc


def _semantic_sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ProviderRouteRegistryError(code)


def validate_provider_route_capability_registry_v2(
    registry: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    """Validate the immutable v1 carry-forward and the observed WSS addition."""

    _require(isinstance(registry, Mapping), "REGISTRY_ROOT_REQUIRED")
    _require(all(type(key) is str for key in registry), "REGISTRY_ROOT_FIELDS_DRIFT")
    _require(frozenset(registry) == ROOT_FIELDS, "REGISTRY_ROOT_FIELDS_DRIFT")
    for key, expected in {
        "schema": "smial.provider-route-capability-registry",
        "schema_version": "2.0",
        "registry_id": "PROVIDER-ROUTE-CAPABILITY-REGISTRY-002",
        "as_of": "2026-08-13",
    }.items():
        _require(type(registry.get(key)) is str and registry.get(key) == expected, "REGISTRY_IDENTITY_DRIFT")
    supersedes = registry.get("supersedes")
    expected_supersedes = {
        "registry_id": "PROVIDER-ROUTE-CAPABILITY-REGISTRY-001",
        "path": "configs/provider_route_capability_registry_v1.yaml",
        "sha256": V1_SHA256,
        "preserved_route_semantic_sha256": LEGACY_ROUTE_HASHES,
    }
    _require(_canonical(supersedes) == _canonical(expected_supersedes), "SUPERSEDES_BINDING_DRIFT")
    _require(_canonical(registry.get("update_policy")) == _canonical(UPDATE_POLICY), "UPDATE_POLICY_DRIFT")
    _require(_canonical(registry.get("non_claims")) == _canonical(NON_CLAIMS), "NON_CLAIM_PROMOTION")
    routes = registry.get("routes")
    _require(type(routes) is list and len(routes) == 3, "ROUTE_SET_DRIFT")
    legacy = routes[:2]
    for route, (route_id, expected_hash) in zip(legacy, LEGACY_ROUTE_HASHES.items(), strict=True):
        _require(isinstance(route, Mapping) and route.get("route_id") == route_id, "LEGACY_ROUTE_ORDER_DRIFT")
        _require(_semantic_sha256(route) == expected_hash, "LEGACY_ROUTE_SEMANTICS_DRIFT")
    projected_v1 = {
        "schema": "smial.provider-route-capability-registry",
        "schema_version": "1.0",
        "registry_id": "PROVIDER-ROUTE-CAPABILITY-REGISTRY-001",
        "as_of": "2026-08-13",
        "update_policy": registry["update_policy"],
        "routes": legacy,
        "non_claims": registry["non_claims"],
    }
    validate_provider_route_capability_registry(projected_v1)
    _require(_canonical(routes[2]) == _canonical(EXPECTED_WSS_ROUTE), "WSS_ROUTE_DRIFT")
    return tuple(routes)


def resolve_provider_route_v2(
    registry: Mapping[str, Any], route_id: str
) -> Mapping[str, Any]:
    """Resolve one stable route from the append-only successor snapshot."""

    _require(type(route_id) is str and bool(route_id), "ROUTE_ID_REQUIRED")
    for route in validate_provider_route_capability_registry_v2(registry):
        if route["route_id"] == route_id:
            return route
    raise ProviderRouteRegistryError(f"REGISTRY_GAP:{route_id}")
