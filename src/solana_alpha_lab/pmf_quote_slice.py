"""Offline PMF quote-slice binder. No provider calls or credentials."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.jupiter_quote_logger import (
    CONTRACT_VERSION as METIS_LOGGER_CONTRACT,
    NETWORK_ENABLED as METIS_NETWORK_ENABLED,
    PROVIDER as METIS_PROVIDER,
)
from solana_alpha_lab.provider_route_capability_registry import (
    ProviderRouteRegistryError,
)
from solana_alpha_lab.provider_route_capability_registry_v6 import (
    resolve_provider_route_v6,
)

ATOM_ID = "PMF-QUOTE-SLICE-OFFLINE-V1"
AUTHORITY_PHRASE = "OK PMF-QUOTE-SLICE"
CONFIG_RELATIVE = "configs/pmf_quote_slice_v1.yaml"
LIVE_REGISTRY_RELATIVE = "configs/provider_route_capability_registry_v6.yaml"
A26_RELATIVE = (
    "docs/evidence/task30/a26_h07_h01_owner_fork_packet_acceptance_v1.json"
)
A24_RELATIVE = (
    "configs/task30_a24_raw_to_pit_admissibility_owner_panel_v1.yaml"
)
H11_PARK_RELATIVE = (
    "docs/evidence/rc002_h11_park_from_priority/"
    "a1_h11_park_from_priority_acceptance_v1.json"
)
A27_RELATIVE = (
    "docs/evidence/task30/a27_h07_h01_liquidity_retention_park_acceptance_v1.json"
)
EXPECTED_LIVE_REGISTRY_SHA256 = (
    "b9642b77c300c81aedebc4aa464284fe244a7553bb3a37bdbb344d68594df580"
)
EXPECTED_A26_SHA256 = (
    "8d4755643c4f64f325e3d2986d928a93f9c1bf64e7694c47230440b8271aecd7"
)
EXPECTED_A24_SHA256 = (
    "96593c1448c0cfc8735b8bd94841de8e15245f06f22388a79bf12da99b58f47e"
)
EXPECTED_H11_PARK_SHA256 = (
    "de2fe1c1abf8bbe2f27b46ee8c23c6b1e1496d5355591a7274df2582ab4332e5"
)
EXPECTED_A27_SHA256 = (
    "b85ee3ff0a7553014977613c624f2295fee3082f7f6c9f5ddf4fa3d6fb64aa42"
)
INTENDED_ROUTE_ID = "JUPITER-SOLANA-SWAP-V2-ORDER-001"
EXPECTED_ENDPOINT = "https://api.jup.ag/swap/v2/order"
EXPECTED_METHOD = "GET"
EXPECTED_OUTPUT_MINT = "DMwbVy48dWVKGe9z1pcVnwF3HLMLrqWdDLfbvx8RchhK"
EXPECTED_INPUT_MINT = "So11111111111111111111111111111111111111112"
EXPECTED_POOL = "URqx24yyYxtXXhTbBQnbtPLhtLWYoaDaRxuQuLpNS3S"
EXPECTED_NOTIONAL = "10000000"
TERMINAL_OUTCOMES = (
    "PMF_QUOTE_SLICE_BOUND_CALL_NOT_AUTHORIZED",
    "PMF_QUOTE_SLICE_PREREQUISITES_DRIFT",
)
FORBIDDEN_FOLLOW_ONS = (
    "WRAP_TASK10_METIS_LOGGER",
    "JUPITER_EXECUTE_OR_BUILD",
    "SUPPLY_TAKER_OR_SIGNER",
    "FAKE_V7_WITHOUT_OBSERVED_RECEIPT",
    "H11_UNPARK_OR_SAMPLE_CAMPAIGN",
    "H13_TRIAL",
    "H02_H10_H14_TRIAL",
    "NOTIONAL_BUCKET_SET_V1_FREEZE",
    "LIVE_PIT_OR_CASHFLOW_CLAIM",
)
NEXT_OWNER_PHRASE = (
    "OK PMF-QUOTE-SLICE-ONE-SHOT: Jupiter Swap V2 /order without taker, "
    "SOL to A24 base mint 0.01 SOL, quote layer only, portal key allowed, "
    "no execute"
)


class PmfQuoteSliceError(ValueError):
    """A prerequisite receipt cannot be bound fail-closed."""


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PmfQuoteSliceError(code)
    return value


def _sha256_file(path: Path, code: str) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise PmfQuoteSliceError(code) from exc


def _load_yaml(path: Path, code: str) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise PmfQuoteSliceError(code) from exc
    return dict(_mapping(document, code))


def _load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PmfQuoteSliceError(code) from exc
    return dict(_mapping(document, code))


def _nested(mapping: Mapping[str, Any], key: str, code: str) -> Mapping[str, Any]:
    return _mapping(mapping.get(key), code)


def decide_slice_terminal(result: Mapping[str, Any]) -> str:
    if (
        result.get("owner_phrase") != AUTHORITY_PHRASE
        or result.get("intended_route_id") != INTENDED_ROUTE_ID
        or result.get("live_registry_status") != "REGISTRY_GAP"
        or result.get("a26_jupiter_or_quote_route_present") is not False
        or result.get("a26_route_feasibility_registry_status") != "REGISTRY_GAP"
        or result.get("output_mint") != EXPECTED_OUTPUT_MINT
        or result.get("input_mint") != EXPECTED_INPUT_MINT
        or result.get("pool_address") != EXPECTED_POOL
        or result.get("notional_atomic") != EXPECTED_NOTIONAL
        or result.get("notional_parameter_id") != "PMF_QUOTE_SLICE_NOTIONAL_V1"
        or result.get("taker") != "OMITTED_QUOTE_ONLY"
        or result.get("execute") != "FORBIDDEN"
        or result.get("build") != "FORBIDDEN"
        or result.get("persist_transaction_bytes") is not False
        or result.get("endpoint") != EXPECTED_ENDPOINT
        or result.get("method") != EXPECTED_METHOD
        or result.get("call_authorized") is not False
        or result.get("authority_granted") is not False
        or result.get("task26_layer") != "QUOTE"
        or result.get("adoption_route") != "ADOPT_JUPITER_SWAP_V2_ORDER_QUOTE_ONLY"
        or result.get("metis_logger_rejected") is not True
        or result.get("h11_park_terminal") != "H11_PARKED_FROM_PRIORITY_SCIENCE_RETAINED"
        or result.get("h07_park_terminal")
        != "RC001_H07_H01_PARKED_FROM_PRIORITY_SCIENCE_RETAINED"
        or result.get("h13_or_h02_started") is not False
        or result.get("h11_unparked") is not False
        or result.get("next_owner_phrase") != NEXT_OWNER_PHRASE
        or list(result.get("forbidden_follow_ons") or []) != list(FORBIDDEN_FOLLOW_ONS)
    ):
        return "PMF_QUOTE_SLICE_PREREQUISITES_DRIFT"
    return "PMF_QUOTE_SLICE_BOUND_CALL_NOT_AUTHORIZED"


def bind_pmf_quote_slice(repo_root: Path) -> dict[str, Any]:
    config_path = repo_root / CONFIG_RELATIVE
    registry_path = repo_root / LIVE_REGISTRY_RELATIVE
    a26_path = repo_root / A26_RELATIVE
    config = _load_yaml(config_path, "SLICE_CONFIG_INVALID")
    registry = _load_yaml(registry_path, "LIVE_REGISTRY_INVALID")
    a26 = _load_json(a26_path, "A26_ACCEPTANCE_INVALID")
    a24_path = repo_root / A24_RELATIVE
    h11_path = repo_root / H11_PARK_RELATIVE
    a27_path = repo_root / A27_RELATIVE
    a24 = _load_yaml(a24_path, "A24_CONFIG_INVALID")
    h11_park = _load_json(h11_path, "H11_PARK_ACCEPTANCE_INVALID")
    a27 = _load_json(a27_path, "A27_PARK_ACCEPTANCE_INVALID")
    observed_registry_sha = _sha256_file(registry_path, "LIVE_REGISTRY_UNREADABLE")
    observed_a26_sha = _sha256_file(a26_path, "A26_ACCEPTANCE_UNREADABLE")
    observed_a24_sha = _sha256_file(a24_path, "A24_CONFIG_UNREADABLE")
    observed_h11_sha = _sha256_file(h11_path, "H11_PARK_UNREADABLE")
    observed_a27_sha = _sha256_file(a27_path, "A27_PARK_UNREADABLE")
    if observed_registry_sha != EXPECTED_LIVE_REGISTRY_SHA256:
        raise PmfQuoteSliceError("LIVE_REGISTRY_DRIFT")
    if observed_a26_sha != EXPECTED_A26_SHA256:
        raise PmfQuoteSliceError("A26_ACCEPTANCE_DRIFT")
    if observed_a24_sha != EXPECTED_A24_SHA256:
        raise PmfQuoteSliceError("A24_CONFIG_DRIFT")
    if observed_h11_sha != EXPECTED_H11_PARK_SHA256:
        raise PmfQuoteSliceError("H11_PARK_DRIFT")
    if observed_a27_sha != EXPECTED_A27_SHA256:
        raise PmfQuoteSliceError("A27_PARK_DRIFT")
    a24_subject = _nested(a24, "reference_subject", "A24_SUBJECT_INVALID")
    if (
        a24_subject.get("pool_address") != EXPECTED_POOL
        or a24_subject.get("base_mint") != EXPECTED_OUTPUT_MINT
        or a24_subject.get("quote_mint") != EXPECTED_INPUT_MINT
    ):
        raise PmfQuoteSliceError("A24_IDENTITY_DRIFT")
    try:
        resolve_provider_route_v6(registry, INTENDED_ROUTE_ID)
    except ProviderRouteRegistryError as exc:
        if "REGISTRY_GAP" not in str(exc):
            raise PmfQuoteSliceError("LIVE_REGISTRY_UNEXPECTED") from exc
    else:
        raise PmfQuoteSliceError("LIVE_REGISTRY_UNEXPECTED_HIT")
    identity = _nested(config, "identity", "SLICE_IDENTITY_INVALID")
    notional = _nested(config, "notional", "SLICE_NOTIONAL_INVALID")
    intended = _nested(config, "intended_route", "SLICE_ROUTE_INVALID")
    a26_registries = _nested(a26, "registries", "A26_REGISTRIES_INVALID")
    metis_rejected = (
        METIS_NETWORK_ENABLED is False
        and METIS_PROVIDER == "JUPITER_METIS"
        and METIS_LOGGER_CONTRACT == "task10_jupiter_quote_observation_v1"
        and config.get("rejected_client") == "TASK10_JUPITER_METIS_V1_QUOTE_LOGGER"
    )
    result = {
        "owner_phrase": config.get("owner_phrase"),
        "adoption_route": config.get("adoption_route"),
        "intended_route_id": intended.get("route_id"),
        "endpoint": intended.get("endpoint"),
        "method": intended.get("method"),
        "official_docs": intended.get("official_docs"),
        "taker": intended.get("taker"),
        "execute": intended.get("execute"),
        "build": intended.get("build"),
        "persist_transaction_bytes": intended.get("persist_transaction_bytes"),
        "authority_granted": intended.get("authority_granted"),
        "live_registry_id": _nested(config, "live_registry", "SLICE_REGISTRY_INVALID").get(
            "registry_id"
        ),
        "live_registry_status": "REGISTRY_GAP",
        "live_registry_sha256": observed_registry_sha,
        "a26_jupiter_or_quote_route_present": a26_registries.get(
            "jupiter_or_quote_route_present"
        ),
        "a26_route_feasibility_registry_status": a26_registries.get(
            "route_feasibility_registry_status"
        ),
        "a26_acceptance_sha256": observed_a26_sha,
        "a24_config_sha256": observed_a24_sha,
        "h11_park_sha256": observed_h11_sha,
        "h11_park_terminal": h11_park.get("terminal"),
        "h07_park_sha256": observed_a27_sha,
        "h07_park_terminal": a27.get("decision"),
        "output_mint": identity.get("output_mint"),
        "input_mint": identity.get("input_mint"),
        "pool_address": identity.get("pool_address"),
        "pair": identity.get("pair"),
        "notional_parameter_id": notional.get("parameter_id"),
        "notional_atomic": notional.get("amount_atomic"),
        "slippage_bps": config.get("slippage_bps"),
        "task26_layer": config.get("task26_layer"),
        "call_authorized": config.get("call_authorized"),
        "metis_logger_rejected": metis_rejected,
        "next_owner_phrase": config.get("next_owner_phrase"),
        "forbidden_follow_ons": list(config.get("forbidden_follow_ons") or []),
        "h13_or_h02_started": False,
        "h11_unparked": h11_park.get("terminal")
        != "H11_PARKED_FROM_PRIORITY_SCIENCE_RETAINED",
        "credential_reads": 0,
        "provider_requests": 0,
    }
    result["terminal"] = decide_slice_terminal(result)
    return result


def format_owner_readout(result: Mapping[str, Any]) -> str:
    terminal = str(result.get("terminal"))
    bound = terminal == "PMF_QUOTE_SLICE_BOUND_CALL_NOT_AUTHORIZED"
    heading = (
        "# PMF — quote-slice bound, call not authorized\n"
        if bound
        else "# PMF — quote-slice prerequisites drifted\n"
    )
    identity_heading = "## Что привязано\n" if bound else "## Что прочитано при drift\n"
    return (
        heading
        + "\n"
        f"**Терминальное решение:** `{terminal}`\n"
        f"**Фраза владельца:** `{AUTHORITY_PHRASE}`\n"
        "\n"
        "Это **офлайн-привязка PMF-контура цены**, а не котировка с рынка, "
        "не execute, не alpha, не PIT и не canonical DONE.\n"
        "\n"
        + identity_heading
        + "\n"
        f"- intended route: `{result.get('intended_route_id')}`\n"
        f"- ADOPT: `{result.get('adoption_route')}`\n"
        f"- method/endpoint: `{result.get('method')}` `{result.get('endpoint')}` "
        "(без `taker`)\n"
        f"- слой TASK-26: `{result.get('task26_layer')}`\n"
        f"- pair: `{result.get('pair')}`\n"
        f"- A24 base mint: `{result.get('output_mint')}`\n"
        f"- input mint (SOL): `{result.get('input_mint')}`\n"
        f"- A24 pool: `{result.get('pool_address')}`\n"
        f"- notional: `{result.get('notional_atomic')}` lamports "
        f"(`{result.get('notional_parameter_id')}`)\n"
        f"- live registry: `{result.get('live_registry_id')}` = "
        f"`{result.get('live_registry_status')}`\n"
        f"- call_authorized: `{result.get('call_authorized')}`\n"
        f"- authority_granted: `{result.get('authority_granted')}`\n"
        f"- build: `{result.get('build')}`\n"
        f"- persist_transaction_bytes: `{result.get('persist_transaction_bytes')}`\n"
        "\n"
        "## Почему live registry не переписывали\n"
        "\n"
        "v6 требует observed receipt для обновления маршрута. "
        "Строка без наблюдения была бы фальшивой observation. "
        "A26 уже фиксирует `jupiter_or_quote_route_present=false` и "
        "`REGISTRY_GAP`. Gap закрывается только после отдельного one-shot.\n"
        "\n"
        "TASK-10 Metis logger отвергнут: это legacy `/swap/v1/quote`, "
        "`NETWORK_ENABLED=false`. Официальный quote-only путь — "
        "`GET /swap/v2/order` **без** `taker` (transaction = null).\n"
        "\n"
        "## Можно ли вызывать API?\n"
        "\n"
        "Нет. Нужна отдельная фраза и portal key. Этот атом ключ не читает.\n"
        "\n"
        f"`{result.get('next_owner_phrase')}`\n"
        "\n"
        "## Не делать\n"
        "\n"
        + "\n".join(f"- `{item}`" for item in result.get("forbidden_follow_ons") or [])
        + "\n"
        "\n"
        "H11 остаётся parked "
        f"(`{result.get('h11_park_terminal')}`). "
        "H07/H01 остаётся parked "
        f"(`{result.get('h07_park_terminal')}`). "
        "H13/H02 не стартуют. "
        "`NOTIONAL_BUCKET_SET_V1` не замораживается. "
        "Это не A18 Orca mint.\n"
        "\n"
        "## Что этим атомом не утверждается\n"
        "\n"
        "- живая цена / fill / NetReturn / cashflow\n"
        "- observed Jupiter route в capability registry\n"
        "- право читать portal API key\n"
    )
