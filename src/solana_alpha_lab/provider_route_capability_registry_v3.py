"""Append-only provider-route registry successor for the A18 read boundary."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from .provider_route_capability_registry import (
    ProviderRouteRegistryError,
)
from .provider_route_capability_registry_v2 import (
    LEGACY_ROUTE_HASHES as V1_ROUTE_HASHES,
    NON_CLAIMS,
    UPDATE_POLICY,
    validate_provider_route_capability_registry_v2,
)


V2_SHA256 = "2fbe49382fcfe5edc438e03378f7eaad173ede4940161fcc5f02d39735d5a7f1"
V2_ROUTE_HASHES = {
    "DEXSCREENER-SOLANA-TOKEN-PAIRS-KEYLESS-001": "c5d7861a4f3074784d1ecfa5614e1617be37dde2fb3e7c28f03ec5d3dd8e0055",
    "HELIUS-SOLANA-GET-SIGNATURES-001": "8852673f88c310d9e9c098a03fdcb2360150a2cfc242cf346637ac5fdd44f46d",
    "HELIUS-SOLANA-LOGS-SUBSCRIBE-001": "97cef2d76835cf484ddd24a378db3a7cb47a91eac6d5d6f179a8090c4c9514cb",
}
ROOT_FIELDS = frozenset(
    {"schema", "schema_version", "registry_id", "as_of", "supersedes", "update_policy", "routes", "non_claims"}
)


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise ProviderRouteRegistryError("REGISTRY_VALUE_INVALID") from exc


def _semantic_sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ProviderRouteRegistryError(code)


EXPECTED_GET_TRANSACTION_ROUTE: dict[str, Any] = {
    "route_id": "SOLANA-STANDARD-GET-TRANSACTION-001",
    "provider": "SOLANA_STANDARD_RPC",
    "endpoint_family": "standard-rpc/getTransaction",
    "network": "solana",
    "access_class": "KEYLESS",
    "operation": "GET_TRANSACTION",
    "protocol": "HTTPS_POST_JSON_RPC",
    "runtime": {
        "client": "PYTHON_STDLIB_URLOPEN",
        "version_source": "CODEX_WORKSPACE_DEPENDENCY",
        "tls_engine": "OPENSSL",
        "observed_result": "HTTP_200_SCHEMA_DRIFT",
    },
    "preflight": {
        "kind": "DNS_TCP",
        "steps": ["DNS", "TCP_443"],
        "consumes_credential": False,
        "consumes_attempt": False,
    },
    "last_success": {
        "observed_at": "2026-07-27T18:47:43.597028Z",
        "http_status": 200,
        "response_bytes": 11460,
        "response_sha256": "fdcb075a854b3471d0d4de0afdae29297e1359a095d5d9b745934f60a907ad6b",
        "evidence_id": "T09-A4-PUMPSWAP-GET-TRANSACTION-001",
    },
    "last_observation": {
        "observed_at": "2026-07-27T18:47:43.597028Z",
        "terminal_class": "HTTP_SUCCESS",
        "layer": "HTTP",
        "http_status": 200,
        "response_bytes": 11460,
        "response_sha256": "fdcb075a854b3471d0d4de0afdae29297e1359a095d5d9b745934f60a907ad6b",
        "error_fingerprint": None,
        "evidence_id": "T09-A4-PUMPSWAP-GET-TRANSACTION-001",
    },
    "known_failures": [
        {
            "fingerprint": "GET_TRANSACTION_RESULT_KEYS_DRIFT",
            "layer": "RPC",
            "interpretation": "Historical HTTP success contained an additive transactionIndex field; preserve raw bytes and classify protocol drift rather than silently widening the parser.",
        }
    ],
    "execution_policy": {
        "retry": False,
        "fallback": False,
        "automatic_selection": False,
        "authority_granted": False,
    },
    "evidence": {
        "last_observation_receipt": "a4://task09_pumpswap_touch_probe_v1/run=t09a4-20260727T184740Z",
        "raw_retention": "A4_OUTSIDE_GIT",
    },
    "non_claims": NON_CLAIMS,
}


def validate_provider_route_capability_registry_v3(
    registry: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    """Validate v2 carry-forward and the observed standard-RPC route addition."""

    _require(isinstance(registry, Mapping), "REGISTRY_ROOT_REQUIRED")
    _require(all(type(key) is str for key in registry), "REGISTRY_ROOT_FIELDS_DRIFT")
    _require(frozenset(registry) == ROOT_FIELDS, "REGISTRY_ROOT_FIELDS_DRIFT")
    for key, expected in {
        "schema": "smial.provider-route-capability-registry",
        "schema_version": "3.0",
        "registry_id": "PROVIDER-ROUTE-CAPABILITY-REGISTRY-003",
        "as_of": "2026-08-13",
    }.items():
        _require(type(registry.get(key)) is str and registry.get(key) == expected, "REGISTRY_IDENTITY_DRIFT")
    expected_supersedes = {
        "registry_id": "PROVIDER-ROUTE-CAPABILITY-REGISTRY-002",
        "path": "configs/provider_route_capability_registry_v2.yaml",
        "sha256": V2_SHA256,
        "preserved_route_semantic_sha256": V2_ROUTE_HASHES,
    }
    _require(_canonical(registry.get("supersedes")) == _canonical(expected_supersedes), "SUPERSEDES_BINDING_DRIFT")
    _require(_canonical(registry.get("update_policy")) == _canonical(UPDATE_POLICY), "UPDATE_POLICY_DRIFT")
    _require(_canonical(registry.get("non_claims")) == _canonical(NON_CLAIMS), "NON_CLAIM_PROMOTION")
    routes = registry.get("routes")
    _require(type(routes) is list and len(routes) == 4, "ROUTE_SET_DRIFT")
    legacy = routes[:3]
    for route, (route_id, expected_hash) in zip(legacy, V2_ROUTE_HASHES.items(), strict=True):
        _require(isinstance(route, Mapping) and route.get("route_id") == route_id, "LEGACY_ROUTE_ORDER_DRIFT")
        _require(_semantic_sha256(route) == expected_hash, "LEGACY_ROUTE_SEMANTICS_DRIFT")
    projected_v2 = {
        "schema": "smial.provider-route-capability-registry",
        "schema_version": "2.0",
        "registry_id": "PROVIDER-ROUTE-CAPABILITY-REGISTRY-002",
        "as_of": "2026-08-13",
        "supersedes": {
            "registry_id": "PROVIDER-ROUTE-CAPABILITY-REGISTRY-001",
            "path": "configs/provider_route_capability_registry_v1.yaml",
            "sha256": "ea44843f7ee7e8116a5599e7e38a8802e416f963ed6e0020448e33db898b7598",
            "preserved_route_semantic_sha256": V1_ROUTE_HASHES,
        },
        "update_policy": registry["update_policy"],
        "routes": legacy,
        "non_claims": registry["non_claims"],
    }
    validate_provider_route_capability_registry_v2(projected_v2)
    _require(_canonical(routes[3]) == _canonical(EXPECTED_GET_TRANSACTION_ROUTE), "GET_TRANSACTION_ROUTE_DRIFT")
    return tuple(routes)


def resolve_provider_route_v3(registry: Mapping[str, Any], route_id: str) -> Mapping[str, Any]:
    """Resolve one route or preserve a fail-closed registry gap."""

    _require(type(route_id) is str and bool(route_id), "ROUTE_ID_REQUIRED")
    for route in validate_provider_route_capability_registry_v3(registry):
        if route["route_id"] == route_id:
            return route
    raise ProviderRouteRegistryError(f"REGISTRY_GAP:{route_id}")
