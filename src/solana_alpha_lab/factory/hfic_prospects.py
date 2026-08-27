"""Read-only HFIC scientific-discovery prospect portfolio loader and query."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

PORTFOLIO_RELATIVE = Path("docs/architecture/prospects/hfic_scientific_discovery_prospects_v1.yaml")
PORTFOLIO_SCHEMA_RELATIVE = Path(
    "catalog/schemas/hfic_scientific_discovery_prospects_v1.schema.json"
)
NEXT_ACTION_DRAFT_SCHEMA_RELATIVE = Path(
    "catalog/schemas/hfic_next_epistemic_action_draft_v1.schema.json"
)
NEXT_ACTION_SCHEMA_RELATIVE = Path("catalog/schemas/hfic_next_epistemic_action_v1.schema.json")
ALLOWED_TRIGGERS = frozenset(
    {
        "OWNER_DISCOVERY_REFRAME",
        "POST_NO_WORTHY_REVIEW",
        "MEASURED_DUPLICATE_COLLAPSE",
        "MEASURED_PREPARATORY_LOOP",
    }
)
_EXCLUDED_DISPOSITIONS = frozenset(
    {
        "PREREQUISITE_BLOCKED",
        "DEFERRED_CURRENT_HORIZON",
        "REJECTED_CURRENT_HORIZON",
    }
)
_DISPOSITION_RANK = {
    "ADOPT_NOW": 0,
    "WATCH_TRIGGERED_ONLY": 1,
}
_SUMMARY_KEYS = (
    "prospect_id",
    "rank",
    "title",
    "disposition",
    "implementation_state",
    "residual_gap",
    "minimal_first_atom",
    "activation_triggers",
    "named_consumers",
)
_MAX_DRAFT_BYTES = 32 * 1024
_AUTHORITY_FALSE_KEYS = (
    "provider_read",
    "credential_read",
    "git_mutation",
    "rdp_mutation",
    "experiment_execution",
    "holdout_consumption",
    "cash_spend",
    "wallet_signer_transaction",
    "roadmap_activation",
    "next_hypothesis_selection",
)


class HficProspectError(ValueError):
    """Fail-closed prospect/next-action contract error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


_PORTFOLIO_VALIDATOR: Draft202012Validator | None = None
_DRAFT_VALIDATOR: Draft202012Validator | None = None
_STORED_VALIDATOR: Draft202012Validator | None = None


def _validator(cache_name: str, schema_path: Path) -> Draft202012Validator:
    global _PORTFOLIO_VALIDATOR, _DRAFT_VALIDATOR, _STORED_VALIDATOR
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    if cache_name == "portfolio":
        _PORTFOLIO_VALIDATOR = validator
    elif cache_name == "draft":
        _DRAFT_VALIDATOR = validator
    else:
        _STORED_VALIDATOR = validator
    return validator


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def load_prospect_portfolio(repo_root: Path) -> dict[str, Any]:
    root = Path(repo_root)
    path = root / PORTFOLIO_RELATIVE
    schema_path = root / PORTFOLIO_SCHEMA_RELATIVE
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise HficProspectError("HFIC_PROSPECT_PORTFOLIO_INVALID") from exc
    if not isinstance(raw, dict):
        raise HficProspectError("HFIC_PROSPECT_PORTFOLIO_INVALID")
    validator = _PORTFOLIO_VALIDATOR or _validator("portfolio", schema_path)
    errors = list(validator.iter_errors(raw))
    if errors:
        raise HficProspectError("HFIC_PROSPECT_PORTFOLIO_INVALID")
    records = raw.get("records")
    if not isinstance(records, list) or len(records) != 23:
        raise HficProspectError("HFIC_PROSPECT_PORTFOLIO_INVALID")
    ids = [str(item.get("prospect_id") or "") for item in records]
    ranks = [item.get("rank") for item in records]
    if len(set(ids)) != 23 or len(set(ranks)) != 23:
        raise HficProspectError("HFIC_PROSPECT_PORTFOLIO_INVALID")
    authority = raw.get("authority")
    if not isinstance(authority, Mapping):
        raise HficProspectError("HFIC_PROSPECT_PORTFOLIO_INVALID")
    if any(authority.get(key) is not False for key in _AUTHORITY_FALSE_KEYS):
        raise HficProspectError("HFIC_PROSPECT_PORTFOLIO_INVALID")
    return raw


def query_prospects(
    repo_root: Path,
    *,
    trigger: str,
    max_results: int = 3,
    include_satisfied: bool = False,
) -> dict[str, Any]:
    if trigger not in ALLOWED_TRIGGERS:
        raise HficProspectError("HFIC_PROSPECT_PORTFOLIO_INVALID")
    if not isinstance(max_results, int) or not (1 <= max_results <= 3):
        raise HficProspectError("HFIC_PROSPECT_PORTFOLIO_INVALID")
    portfolio = load_prospect_portfolio(repo_root)
    visible: list[dict[str, Any]] = []
    for record in portfolio["records"]:
        if not isinstance(record, Mapping):
            continue
        disposition = str(record.get("disposition") or "")
        if disposition in _EXCLUDED_DISPOSITIONS:
            continue
        satisfied = record.get("satisfied_by") or []
        if satisfied and not include_satisfied:
            continue
        triggers = [str(item) for item in (record.get("activation_triggers") or [])]
        if trigger not in triggers:
            continue
        visible.append(dict(record))
    visible.sort(
        key=lambda item: (
            0 if trigger in [str(x) for x in (item.get("activation_triggers") or [])] else 1,
            _DISPOSITION_RANK.get(str(item.get("disposition") or ""), 99),
            int(item.get("rank") or 99),
            str(item.get("prospect_id") or ""),
        )
    )
    selected = visible[:max_results]
    summaries = [{key: item.get(key) for key in _SUMMARY_KEYS} for item in selected]
    raw_bytes = (Path(repo_root) / PORTFOLIO_RELATIVE).read_bytes()
    return {
        "portfolio_id": portfolio["portfolio_id"],
        "portfolio_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "query_trigger": trigger,
        "returned_count": len(summaries),
        "records": summaries,
        "authority": dict(portfolio["authority"]),
        "default_forge_visibility": portfolio["activation_policy"]["default_forge_visibility"],
        "execution_authority": portfolio["activation_policy"]["execution_authority"],
    }


def _reject_sensitive_text(value: object) -> None:
    if isinstance(value, Mapping):
        for item in value.values():
            _reject_sensitive_text(item)
        return
    if isinstance(value, list):
        for item in value:
            _reject_sensitive_text(item)
        return
    if not isinstance(value, str):
        return
    lowered = value.lower()
    if "c:\\users\\" in lowered or "/users/" in lowered or "\\users\\" in lowered:
        raise HficProspectError("HFIC_NEXT_ACTION_INVALID")
    if any(token in lowered for token in ("api_key", "secret", "password", "private_key", "seed")):
        raise HficProspectError("HFIC_NEXT_ACTION_INVALID")


def validate_next_action_draft(
    draft: Mapping[str, Any],
    *,
    repo_root: Path,
    known_candidate_ids: set[str] | None = None,
    known_prospect_ids: set[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(draft, Mapping):
        raise HficProspectError("HFIC_NEXT_ACTION_INVALID")
    try:
        raw = _canonical_bytes(draft)
    except (TypeError, ValueError) as exc:
        raise HficProspectError("HFIC_NEXT_ACTION_INVALID") from exc
    if len(raw) > _MAX_DRAFT_BYTES:
        raise HficProspectError("HFIC_NEXT_ACTION_PACKET_TOO_LARGE")
    schema_path = Path(repo_root) / NEXT_ACTION_DRAFT_SCHEMA_RELATIVE
    validator = _DRAFT_VALIDATOR or _validator("draft", schema_path)
    errors = list(validator.iter_errors(draft))
    if errors:
        raise HficProspectError("HFIC_NEXT_ACTION_INVALID")
    _reject_sensitive_text(draft)
    refs = [str(item) for item in (draft.get("basis_candidate_refs") or [])]
    if known_candidate_ids is not None:
        for ref in refs:
            if ref not in known_candidate_ids:
                raise HficProspectError("HFIC_NEXT_ACTION_INVALID")
    prospect_ids = [str(item) for item in (draft.get("prospect_ids") or [])]
    if known_prospect_ids is not None:
        for prospect_id in prospect_ids:
            if prospect_id not in known_prospect_ids:
                raise HficProspectError("HFIC_PROSPECT_REF_UNKNOWN")
    return dict(draft)


def validate_stored_next_action(
    action: Mapping[str, Any],
    *,
    repo_root: Path,
) -> dict[str, Any]:
    if not isinstance(action, Mapping):
        raise HficProspectError("HFIC_NEXT_ACTION_INVALID")
    schema_path = Path(repo_root) / NEXT_ACTION_SCHEMA_RELATIVE
    validator = _STORED_VALIDATOR or _validator("stored", schema_path)
    errors = list(validator.iter_errors(action))
    if errors:
        raise HficProspectError("HFIC_NEXT_ACTION_INVALID")
    _reject_sensitive_text(action)
    return dict(action)
