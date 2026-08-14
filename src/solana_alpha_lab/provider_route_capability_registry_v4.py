"""Append-only provider-route registry successor for TASK-30 A20."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from .provider_route_capability_registry import ProviderRouteRegistryError
from .provider_route_capability_registry_v2 import NON_CLAIMS, UPDATE_POLICY
from .provider_route_capability_registry_v3 import (
    V2_ROUTE_HASHES,
    V2_SHA256,
    validate_provider_route_capability_registry_v3,
)


V3_SHA256 = "dfab094593c061fc2dcbe344b2e7977942927f833c2d2a83e50aa5a3e27cd95e"
V3_ROUTE_HASHES = {
    "DEXSCREENER-SOLANA-TOKEN-PAIRS-KEYLESS-001": "c5d7861a4f3074784d1ecfa5614e1617be37dde2fb3e7c28f03ec5d3dd8e0055",
    "HELIUS-SOLANA-GET-SIGNATURES-001": "8852673f88c310d9e9c098a03fdcb2360150a2cfc242cf346637ac5fdd44f46d",
    "HELIUS-SOLANA-LOGS-SUBSCRIBE-001": "97cef2d76835cf484ddd24a378db3a7cb47a91eac6d5d6f179a8090c4c9514cb",
    "SOLANA-STANDARD-GET-TRANSACTION-001": "b00b7c58edebd331e6908ff19b1a4b066678b9b371362d55157c599633db4ae7",
}
RUNTIME_RECEIPT_SHA256 = "fd7a52e6952e12fc48b9a88ed13b6dcfb28dbc9324cb767642fb28806897a185"
ROOT_FIELDS = frozenset(
    {"schema", "schema_version", "registry_id", "as_of", "supersedes", "update_policy", "routes", "non_claims"}
)


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProviderRouteRegistryError("REGISTRY_VALUE_INVALID") from exc


def _semantic_sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ProviderRouteRegistryError(code)


EXPECTED_BITQUERY_ROUTE: dict[str, Any] = {
    "route_id": "BITQUERY-SOLANA-PUMPSWAP-OHLCV-001",
    "provider": "BITQUERY",
    "endpoint_family": "streaming.bitquery.io/graphql",
    "network": "solana",
    "access_class": "LOCAL_ENV_CREDENTIAL",
    "operation": "PUMPSWAP_ARCHIVE_15M_OHLCV",
    "protocol": "HTTPS_POST_GRAPHQL_V2",
    "runtime": {
        "client": "PYTHON_STDLIB_URLLIB",
        "version_source": "CODEX_WORKSPACE_DEPENDENCY",
        "tls_engine": "OPENSSL",
        "observed_result": "ROUTE_UNKNOWN_STOP",
    },
    "preflight": {
        "kind": "DNS_TCP_TLS",
        "steps": ["DNS", "TCP_443", "TLS_HANDSHAKE"],
        "consumes_credential": False,
        "consumes_attempt": False,
    },
    "last_success": None,
    "last_observation": {
        "observed_at": "2026-08-14T12:26:53Z",
        "observed_at_semantics": "RECEIPT_RECORDED_AT",
        "attempt_time_precision": "BOUNDED_NOT_EXACT_PREPATCH",
        "terminal_class": "ROUTE_UNKNOWN_STOP",
        "layer": "TRANSPORT",
        "http_status": None,
        "response_bytes": None,
        "response_sha256": None,
        "error_fingerprint": "PREPATCH_HTTPERROR_OR_TRANSPORT_COLLAPSE",
        "evidence_id": "EVIDENCE-T30-A20P-BITQUERY-PIT-CAPTURE-001",
    },
    "known_failures": [
        {
            "fingerprint": "PREPATCH_HTTPERROR_OR_TRANSPORT_COLLAPSE",
            "layer": "LOCAL_CLIENT",
            "interpretation": "The one authorized request stopped after a passed TLS preflight; the pre-patch client collapsed HTTPError and transport failure, so provider cause and response bytes remain unknown and no retry is allowed.",
        }
    ],
    "execution_policy": {
        "retry": False,
        "fallback": False,
        "automatic_selection": False,
        "authority_granted": False,
    },
    "evidence": {
        "last_observation_receipt": "docs/evidence/task30/a20p_bitquery_named_partial_pit_route_capture_runtime_receipt_v1.json",
        "last_observation_receipt_sha256": RUNTIME_RECEIPT_SHA256,
        "raw_retention": "NO_RESPONSE_BYTES_AVAILABLE",
    },
    "non_claims": NON_CLAIMS,
}


def validate_provider_route_capability_registry_v4(
    registry: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    """Validate exact v3 carry-forward plus the observed Bitquery stop."""

    _require(isinstance(registry, Mapping), "REGISTRY_ROOT_REQUIRED")
    _require(all(type(key) is str for key in registry), "REGISTRY_ROOT_FIELDS_DRIFT")
    _require(frozenset(registry) == ROOT_FIELDS, "REGISTRY_ROOT_FIELDS_DRIFT")
    for key, expected in {
        "schema": "smial.provider-route-capability-registry",
        "schema_version": "4.0",
        "registry_id": "PROVIDER-ROUTE-CAPABILITY-REGISTRY-004",
        "as_of": "2026-08-14",
    }.items():
        _require(type(registry.get(key)) is str and registry.get(key) == expected, "REGISTRY_IDENTITY_DRIFT")
    expected_supersedes = {
        "registry_id": "PROVIDER-ROUTE-CAPABILITY-REGISTRY-003",
        "path": "configs/provider_route_capability_registry_v3.yaml",
        "sha256": V3_SHA256,
        "preserved_route_semantic_sha256": V3_ROUTE_HASHES,
    }
    _require(_canonical(registry.get("supersedes")) == _canonical(expected_supersedes), "SUPERSEDES_BINDING_DRIFT")
    _require(_canonical(registry.get("update_policy")) == _canonical(UPDATE_POLICY), "UPDATE_POLICY_DRIFT")
    _require(_canonical(registry.get("non_claims")) == _canonical(NON_CLAIMS), "NON_CLAIM_PROMOTION")
    routes = registry.get("routes")
    _require(type(routes) is list and len(routes) == 5, "ROUTE_SET_DRIFT")
    legacy = routes[:4]
    for route, (route_id, expected_hash) in zip(legacy, V3_ROUTE_HASHES.items(), strict=True):
        _require(isinstance(route, Mapping) and route.get("route_id") == route_id, "LEGACY_ROUTE_ORDER_DRIFT")
        _require(_semantic_sha256(route) == expected_hash, "LEGACY_ROUTE_SEMANTICS_DRIFT")
    projected_v3 = {
        "schema": "smial.provider-route-capability-registry",
        "schema_version": "3.0",
        "registry_id": "PROVIDER-ROUTE-CAPABILITY-REGISTRY-003",
        "as_of": "2026-08-13",
        "supersedes": {
            "registry_id": "PROVIDER-ROUTE-CAPABILITY-REGISTRY-002",
            "path": "configs/provider_route_capability_registry_v2.yaml",
            "sha256": V2_SHA256,
            "preserved_route_semantic_sha256": V2_ROUTE_HASHES,
        },
        "update_policy": registry["update_policy"],
        "routes": legacy,
        "non_claims": registry["non_claims"],
    }
    validate_provider_route_capability_registry_v3(projected_v3)
    _require(_canonical(routes[4]) == _canonical(EXPECTED_BITQUERY_ROUTE), "BITQUERY_ROUTE_DRIFT")
    return tuple(routes)


def resolve_provider_route_v4(registry: Mapping[str, Any], route_id: str) -> Mapping[str, Any]:
    """Resolve one observed route or preserve a fail-closed registry gap."""

    _require(type(route_id) is str and bool(route_id), "ROUTE_ID_REQUIRED")
    for route in validate_provider_route_capability_registry_v4(registry):
        if route["route_id"] == route_id:
            return route
    raise ProviderRouteRegistryError(f"REGISTRY_GAP:{route_id}")
