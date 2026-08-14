"""Append-only provider-route registry successor for TASK-30 A22."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from .provider_route_capability_registry import ProviderRouteRegistryError
from .provider_route_capability_registry_v2 import NON_CLAIMS, UPDATE_POLICY
from .provider_route_capability_registry_v4 import (
    V3_ROUTE_HASHES,
    V3_SHA256,
    validate_provider_route_capability_registry_v4,
)


V4_SHA256 = "329d2590ff799688dfbe674ce34f5fa6cd2aa85230dfa6d8dcc22fa4980594e4"
V4_ROUTE_HASHES = {
    "DEXSCREENER-SOLANA-TOKEN-PAIRS-KEYLESS-001": "c5d7861a4f3074784d1ecfa5614e1617be37dde2fb3e7c28f03ec5d3dd8e0055",
    "HELIUS-SOLANA-GET-SIGNATURES-001": "8852673f88c310d9e9c098a03fdcb2360150a2cfc242cf346637ac5fdd44f46d",
    "HELIUS-SOLANA-LOGS-SUBSCRIBE-001": "97cef2d76835cf484ddd24a378db3a7cb47a91eac6d5d6f179a8090c4c9514cb",
    "SOLANA-STANDARD-GET-TRANSACTION-001": "b00b7c58edebd331e6908ff19b1a4b066678b9b371362d55157c599633db4ae7",
    "BITQUERY-SOLANA-PUMPSWAP-OHLCV-001": "07140d5c257b00b9769be6d908f8e69f31739b7dfabeca1b69e0176dc410915a",
}
RUNTIME_RECEIPT_SHA256 = "bbb29e932ff2c2d68703f2f1693e8fe07a57b7ef24ffabea71c1a95436f97b15"
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


EXPECTED_HELIUS_ROUTE: dict[str, Any] = {
    "route_id": "HELIUS-SOLANA-GET-TRANSACTIONS-FOR-ADDRESS-001",
    "provider": "HELIUS",
    "endpoint_family": "helius-rpc/getTransactionsForAddress",
    "network": "solana",
    "access_class": "LOCAL_ENV_CREDENTIAL",
    "operation": "GET_TRANSACTIONS_FOR_ADDRESS_FULL",
    "protocol": "HTTPS_POST_JSON_RPC_2_0",
    "runtime": {
        "client": "PYTHON_STDLIB_URLLIB",
        "version_source": "CODEX_WORKSPACE_DEPENDENCY",
        "tls_engine": "OPENSSL",
        "observed_result": "HTTP_200_PAGINATION_REQUIRED_STOP",
    },
    "preflight": {
        "kind": "DNS_TCP_TLS",
        "steps": ["DNS", "TCP_443", "TLS_HANDSHAKE"],
        "consumes_credential": False,
        "consumes_attempt": False,
    },
    "last_success": {
        "observed_at": "2026-08-14T18:42:09Z",
        "http_status": 200,
        "response_bytes": 9_012_030,
        "response_sha256": "7244a4c049c7ebe5f77d6136513d402c9af568dd0ccabb3a842160ab61a72bcc",
        "evidence_id": "EVIDENCE-T30-A22P-HELIUS-GET-TRANSACTIONS-FOR-ADDRESS-001",
    },
    "last_observation": {
        "observed_at": "2026-08-14T18:42:09Z",
        "terminal_class": "PAGINATION_REQUIRED_STOP",
        "layer": "DATA_COVERAGE",
        "http_status": 200,
        "response_bytes": 9_012_030,
        "response_sha256": "7244a4c049c7ebe5f77d6136513d402c9af568dd0ccabb3a842160ab61a72bcc",
        "transaction_count": 520,
        "pagination_token_present": True,
        "error_fingerprint": "PAGINATION_TOKEN_PRESENT_AFTER_520_FULL_TRANSACTIONS",
        "evidence_id": "EVIDENCE-T30-A22P-HELIUS-GET-TRANSACTIONS-FOR-ADDRESS-001",
    },
    "known_failures": [
        {
            "fingerprint": "PAGINATION_TOKEN_PRESENT_AFTER_520_FULL_TRANSACTIONS",
            "layer": "DATA_COVERAGE",
            "interpretation": "One successful response retained 520 full transactions for the exact pool and window but returned a pagination token; the bounded one-shot cannot establish a complete batch and no second request is authorized.",
        }
    ],
    "execution_policy": {
        "retry": False,
        "fallback": False,
        "automatic_selection": False,
        "authority_granted": False,
    },
    "evidence": {
        "last_observation_receipt": "docs/evidence/task30/a22_helius_get_transactions_for_address_runtime_receipt_v1.json",
        "last_observation_receipt_sha256": RUNTIME_RECEIPT_SHA256,
        "raw_retention": "A4_OUTSIDE_GIT",
    },
    "non_claims": NON_CLAIMS,
}


def validate_provider_route_capability_registry_v5(
    registry: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    """Validate exact v4 carry-forward plus the observed Helius one-shot."""

    _require(isinstance(registry, Mapping), "REGISTRY_ROOT_REQUIRED")
    _require(all(type(key) is str for key in registry), "REGISTRY_ROOT_FIELDS_DRIFT")
    _require(frozenset(registry) == ROOT_FIELDS, "REGISTRY_ROOT_FIELDS_DRIFT")
    for key, expected in {
        "schema": "smial.provider-route-capability-registry",
        "schema_version": "5.0",
        "registry_id": "PROVIDER-ROUTE-CAPABILITY-REGISTRY-005",
        "as_of": "2026-08-14",
    }.items():
        _require(type(registry.get(key)) is str and registry.get(key) == expected, "REGISTRY_IDENTITY_DRIFT")
    expected_supersedes = {
        "registry_id": "PROVIDER-ROUTE-CAPABILITY-REGISTRY-004",
        "path": "configs/provider_route_capability_registry_v4.yaml",
        "sha256": V4_SHA256,
        "preserved_route_semantic_sha256": V4_ROUTE_HASHES,
    }
    _require(_canonical(registry.get("supersedes")) == _canonical(expected_supersedes), "SUPERSEDES_BINDING_DRIFT")
    _require(_canonical(registry.get("update_policy")) == _canonical(UPDATE_POLICY), "UPDATE_POLICY_DRIFT")
    _require(_canonical(registry.get("non_claims")) == _canonical(NON_CLAIMS), "NON_CLAIM_PROMOTION")
    routes = registry.get("routes")
    _require(type(routes) is list and len(routes) == 6, "ROUTE_SET_DRIFT")
    legacy = routes[:5]
    for route, (route_id, expected_hash) in zip(legacy, V4_ROUTE_HASHES.items(), strict=True):
        _require(isinstance(route, Mapping) and route.get("route_id") == route_id, "LEGACY_ROUTE_ORDER_DRIFT")
        _require(_semantic_sha256(route) == expected_hash, "LEGACY_ROUTE_SEMANTICS_DRIFT")
    projected_v4 = {
        "schema": "smial.provider-route-capability-registry",
        "schema_version": "4.0",
        "registry_id": "PROVIDER-ROUTE-CAPABILITY-REGISTRY-004",
        "as_of": "2026-08-14",
        "supersedes": {
            "registry_id": "PROVIDER-ROUTE-CAPABILITY-REGISTRY-003",
            "path": "configs/provider_route_capability_registry_v3.yaml",
            "sha256": V3_SHA256,
            "preserved_route_semantic_sha256": V3_ROUTE_HASHES,
        },
        "update_policy": registry["update_policy"],
        "routes": legacy,
        "non_claims": registry["non_claims"],
    }
    validate_provider_route_capability_registry_v4(projected_v4)
    _require(_canonical(routes[5]) == _canonical(EXPECTED_HELIUS_ROUTE), "HELIUS_ROUTE_DRIFT")
    return tuple(routes)


def resolve_provider_route_v5(registry: Mapping[str, Any], route_id: str) -> Mapping[str, Any]:
    """Resolve one observed route or preserve a fail-closed registry gap."""

    _require(type(route_id) is str and bool(route_id), "ROUTE_ID_REQUIRED")
    for route in validate_provider_route_capability_registry_v5(registry):
        if route["route_id"] == route_id:
            return route
    raise ProviderRouteRegistryError(f"REGISTRY_GAP:{route_id}")
