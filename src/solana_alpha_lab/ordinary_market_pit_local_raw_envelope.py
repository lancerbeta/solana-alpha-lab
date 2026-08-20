"""Join hash-verified local Tokens V2 envelopes onto Git cohort cells.

Raw bodies stay A4_OUTSIDE_GIT. Not Factory core. Not live capture.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from solana_alpha_lab.ordinary_market_pit_primary_x import (
    AVAILABILITY_CLASS,
    FACTORY_RUNNER,
    FORBIDDEN_SUBSTITUTES,
    PRIMARY_X_BOUND,
    bind_primary_x,
    sha256_bytes,
)

BIND_ID = "ORDINARY-MARKET-PIT-LOCAL-RAW-ENVELOPE-BIND-001"
PRODUCT_TERMINAL = "LOCAL_RAW_ENVELOPES_BIND_PRIMARY_X"
CONFIG_RELATIVE = "configs/ordinary_market_pit_local_raw_envelope_bind_v1.yaml"
FORBIDDEN_OUTPUT_KEYS = frozenset(
    {
        "audit",
        "circSupply",
        "dev",
        "fdv",
        "firstPool",
        "holderCount",
        "icon",
        "launchpad",
        "name",
        "organicScore",
        "organicScoreLabel",
        "priceBlockId",
        "raw_body",
        "stats1h",
        "stats24h",
        "stats5m",
        "stats6h",
        "symbol",
        "tags",
        "tokenProgram",
        "totalSupply",
        "twitter",
        "usdPrice",
        "website",
    }
)
STRATUM_BY_SOURCE = {
    "LIVE_TOKENS_V2_RECENT": "RECENT",
    "LIVE_TOKENS_V2_TOPTRADED": "TRADED",
}


class LocalRawEnvelopeBindError(ValueError):
    """Raised when local envelopes or the Git cohort cannot be joined."""


def load_local_raw_config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_RELATIVE
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise LocalRawEnvelopeBindError("BIND_CONFIG_INVALID")
    primary = loaded.get("primary_x")
    if not isinstance(primary, dict):
        raise LocalRawEnvelopeBindError("BIND_CONFIG_INVALID")
    if primary.get("numerator_field") != "liquidity":
        raise LocalRawEnvelopeBindError("NUMERATOR_NOT_LIQUIDITY")
    if primary.get("denominator_field") != "mcap":
        raise LocalRawEnvelopeBindError("DENOMINATOR_NOT_MCAP")
    forbidden = tuple(primary.get("forbidden_substitutes") or ())
    if forbidden != FORBIDDEN_SUBSTITUTES:
        raise LocalRawEnvelopeBindError("FORBIDDEN_SUBSTITUTES_DRIFT")
    if loaded.get("availability_class") != AVAILABILITY_CLASS:
        raise LocalRawEnvelopeBindError("AVAILABILITY_CLASS_DRIFT")
    if loaded.get("raw_retention") != "A4_OUTSIDE_GIT":
        raise LocalRawEnvelopeBindError("RAW_RETENTION_DRIFT")
    if int(loaded.get("evidence_budget", {}).get("provider_api_rpc_wss_calls", 1)) != 0:
        raise LocalRawEnvelopeBindError("LIVE_CAPTURE_NOT_IN_SCOPE")
    envelopes = loaded.get("envelopes")
    if not isinstance(envelopes, list) or len(envelopes) != 2:
        raise LocalRawEnvelopeBindError("ENVELOPE_BINDINGS_INVALID")
    return loaded


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LocalRawEnvelopeBindError(code)


def _load_qualification_receipt(root: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    retained = config.get("qualification_receipt")
    _require(isinstance(retained, Mapping), "QUALIFICATION_RECEIPT_INVALID")
    relative = retained.get("path")
    expected = retained.get("sha256")
    _require(type(relative) is str and type(expected) is str, "QUALIFICATION_RECEIPT_INVALID")
    payload = (root / relative).read_bytes()
    digest = sha256_bytes(payload)
    _require(digest == expected, "QUALIFICATION_RECEIPT_HASH_MISMATCH")
    receipt = json.loads(payload.decode("utf-8"))
    _require(isinstance(receipt, dict), "QUALIFICATION_RECEIPT_INVALID")
    return receipt


def _manifest_index(receipt: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw_retention = receipt.get("raw_retention")
    _require(isinstance(raw_retention, Mapping), "RAW_RETENTION_MISSING")
    manifests = raw_retention.get("manifests")
    _require(isinstance(manifests, list) and manifests, "RAW_MANIFESTS_MISSING")
    index: dict[str, dict[str, Any]] = {}
    for row in manifests:
        _require(isinstance(row, Mapping), "RAW_MANIFEST_INVALID")
        observation_id = row.get("observation_id")
        _require(type(observation_id) is str and observation_id, "RAW_MANIFEST_INVALID")
        _require(observation_id not in index, "RAW_MANIFEST_DUPLICATE")
        index[observation_id] = dict(row)
    return index


def _parse_envelope_list(payload: object) -> list[Mapping[str, Any]]:
    _require(isinstance(payload, list) and payload, "ENVELOPE_NOT_LIST")
    items: list[Mapping[str, Any]] = []
    for item in payload:
        _require(isinstance(item, Mapping), "ENVELOPE_ITEM_INVALID")
        items.append(item)
    return items


def _index_by_mint(items: list[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for item in items:
        mint = item.get("id")
        _require(type(mint) is str and mint, "ENVELOPE_ITEM_ID_INVALID")
        _require(mint not in index, "ENVELOPE_DUPLICATE_MINT")
        index[mint] = item
    return index


def _cell_stratum(cell: Mapping[str, Any]) -> str:
    stratum = cell.get("stratum")
    if type(stratum) is str and stratum:
        return stratum
    source_kind = cell.get("source_kind")
    mapped = STRATUM_BY_SOURCE.get(source_kind) if type(source_kind) is str else None
    _require(mapped is not None, "CELL_STRATUM_INVALID")
    return str(mapped)


def load_verified_envelopes(
    root: Path,
    config: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    manifests = _manifest_index(receipt)
    local_root_rel = config.get("local_raw_root")
    _require(type(local_root_rel) is str and local_root_rel, "LOCAL_RAW_ROOT_INVALID")
    bindings = config.get("envelopes")
    _require(isinstance(bindings, list), "ENVELOPE_BINDINGS_INVALID")
    loaded: dict[str, dict[str, Any]] = {}
    for binding in bindings:
        _require(isinstance(binding, Mapping), "ENVELOPE_BINDING_INVALID")
        observation_id = binding.get("observation_id")
        expected = binding.get("expected_sha256")
        stratum = binding.get("stratum")
        _require(type(observation_id) is str, "ENVELOPE_BINDING_INVALID")
        _require(type(expected) is str, "ENVELOPE_BINDING_INVALID")
        _require(type(stratum) is str, "ENVELOPE_BINDING_INVALID")
        manifest = manifests.get(observation_id)
        _require(manifest is not None, "ENVELOPE_MANIFEST_MISSING")
        _require(manifest.get("sha256") == expected, "ENVELOPE_MANIFEST_SHA_DRIFT")
        relative = manifest.get("path")
        _require(type(relative) is str and relative, "ENVELOPE_MANIFEST_PATH_INVALID")
        path = root / local_root_rel / relative
        _require(path.is_file(), "LOCAL_RAW_ABSENT")
        raw = path.read_bytes()
        digest = sha256_bytes(raw)
        _require(digest == expected, "LOCAL_RAW_HASH_MISMATCH")
        items = _parse_envelope_list(json.loads(raw.decode("utf-8")))
        loaded[stratum] = {
            "observation_id": observation_id,
            "path": relative,
            "sha256": digest,
            "bytes": len(raw),
            "by_mint": _index_by_mint(items),
        }
    return loaded


def _projection_row(
    cell: Mapping[str, Any],
    envelope: Mapping[str, Any],
    item: Mapping[str, Any],
) -> dict[str, Any]:
    git_liquidity = cell.get("liquidity")
    bound = bind_primary_x(item, observed_at=None)
    if bound["status"] == PRIMARY_X_BOUND:
        _require(bound["liquidity"] == git_liquidity, "GIT_CELL_LIQUIDITY_DRIFT")
    row = {
        "identity_id": cell.get("identity_id"),
        "mint": cell.get("mint"),
        "stratum": _cell_stratum(cell),
        "status": bound["status"],
        "value": bound["value"],
        "liquidity": bound["liquidity"],
        "mcap": bound["mcap"],
        "availability_class": bound["availability_class"],
        "substitute_rejected": bound["substitute_rejected"],
        "pit_ready": False,
        "observation_id": envelope["observation_id"],
        "envelope_sha256": envelope["sha256"],
        "envelope_bytes": envelope["bytes"],
    }
    overlap = FORBIDDEN_OUTPUT_KEYS.intersection(row)
    _require(not overlap, "RAW_FIELDS_LEAKED")
    return row


def bind_local_raw_envelopes(root: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    receipt = _load_qualification_receipt(root, config)
    cells = receipt.get("frozen_cells")
    _require(isinstance(cells, list) and cells, "FROZEN_CELLS_MISSING")
    envelopes = load_verified_envelopes(root, config, receipt)
    rows: list[dict[str, Any]] = []
    for cell in cells:
        _require(isinstance(cell, Mapping), "FROZEN_CELL_INVALID")
        mint = cell.get("mint")
        _require(type(mint) is str and mint, "FROZEN_CELL_MINT_INVALID")
        stratum = _cell_stratum(cell)
        envelope = envelopes.get(stratum)
        _require(envelope is not None, "STRATUM_ENVELOPE_MISSING")
        item = envelope["by_mint"].get(mint)
        _require(item is not None, "COHORT_MINT_MISSING")
        rows.append(_projection_row(cell, envelope, item))
    bound = sum(1 for row in rows if row["status"] == PRIMARY_X_BOUND)
    unknown = len(rows) - bound
    git_mcap = sum(1 for cell in cells if isinstance(cell, Mapping) and "mcap" in cell)
    terminal = PRODUCT_TERMINAL if bound == len(rows) and unknown == 0 else "LOCAL_RAW_ENVELOPES_INCOMPLETE"
    return {
        "bind_id": BIND_ID,
        "hypothesis_version": config.get("hypothesis_version"),
        "product_terminal": terminal,
        "next_safe_action": config.get("next_safe_action"),
        "cell_count": len(rows),
        "primary_x_bound_count": bound,
        "primary_x_unknown_count": unknown,
        "git_frozen_cell_mcap_key_count": git_mcap,
        "availability_class": AVAILABILITY_CLASS,
        "pit_ready_count": 0,
        "provider_api_rpc_wss_calls": 0,
        "raw_retention": "A4_OUTSIDE_GIT",
        "qualification_receipt_path": config["qualification_receipt"]["path"],
        "qualification_receipt_sha256": config["qualification_receipt"]["sha256"],
        "envelopes": [
            {
                "observation_id": envelopes[stratum]["observation_id"],
                "stratum": stratum,
                "sha256": envelopes[stratum]["sha256"],
                "bytes": envelopes[stratum]["bytes"],
                "path": envelopes[stratum]["path"],
            }
            for stratum in ("RECENT", "TRADED")
            if stratum in envelopes
        ],
        "factory_runner_sha256": sha256_bytes((root / FACTORY_RUNNER).read_bytes()),
        "rows": rows,
    }
