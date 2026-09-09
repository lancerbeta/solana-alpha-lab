"""TradingRuntimePolicyV1: PAPER/SHADOW operating envelope over PaperPlane.

Current policy values live in the PaperPlane SQLite store. Git owns only the
capability contract. GET paths must never call the write helpers here.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

import yaml

from solana_alpha_lab.factory.paper_plane import OPEN_RISK_STATES, PaperPlaneStore
from solana_alpha_lab.factory.run_passport import canonical_sha256

SCHEMA = "smial.trading-runtime-policy"
SCHEMA_VERSION = "1.0"
CONFIG_RELATIVE = "configs/trading_runtime_policy_v1.yaml"
SUPPORTED_MODES = frozenset({"PAPER", "SHADOW"})
STATUS_NOT_CONFIGURED = "NOT_CONFIGURED_STRATEGY_ONLY"
STATUS_VALID = "VALID"
STATUS_INVALID = "RUNTIME_POLICY_INVALID"
GENESIS_POLICY_SHA256 = "0" * 64
COMMAND_APPLY = "TRADING_RUNTIME_POLICY_APPLY"
COMMAND_ROLLBACK = "TRADING_RUNTIME_POLICY_ROLLBACK"
OPTIONAL_MONEY = (
    "global_entry_notional_cap_usd",
    "max_total_open_notional_usd",
    "default_strategy_max_open_notional_usd",
    "max_open_notional_per_mint_usd",
)
OPTIONAL_COUNTS = (
    "max_total_open_positions",
    "default_strategy_max_open_positions",
    "max_open_positions_per_mint",
)
OVERRIDE_MONEY = ("entry_notional_cap_usd", "max_open_notional_usd")
OVERRIDE_COUNTS = ("max_open_positions",)


class TradingRuntimePolicyError(ValueError):
    """Fail-closed runtime policy error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_capability_config(root: Path) -> dict[str, Any]:
    loaded = yaml.safe_load((root / CONFIG_RELATIVE).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TradingRuntimePolicyError("POLICY_CAPABILITY_CONFIG_INVALID")
    phrase = str(loaded.get("owner_authorization_phrase") or "")
    if not phrase:
        raise TradingRuntimePolicyError("POLICY_AUTHORIZATION_PHRASE_MISSING")
    return loaded


def require_owner_authorization(root: Path, phrase: str | None) -> None:
    expected = str(load_capability_config(root)["owner_authorization_phrase"])
    if phrase != expected:
        raise TradingRuntimePolicyError("POLICY_OWNER_AUTHORIZATION_INVALID")


def _money(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise TradingRuntimePolicyError(f"POLICY_FIELD_INVALID:{field}") from exc
    if amount <= 0 or not amount.is_finite():
        raise TradingRuntimePolicyError(f"POLICY_FIELD_INVALID:{field}")
    return format(amount, "f")


def _count(value: Any, *, field: str) -> int | None:
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise TradingRuntimePolicyError(f"POLICY_FIELD_INVALID:{field}") from exc
    if number < 1 or str(value).strip() != str(number):
        raise TradingRuntimePolicyError(f"POLICY_FIELD_INVALID:{field}")
    return number


def _strategy_id(value: Any) -> str:
    token = str(value or "")
    if not token.startswith("STRAT-"):
        raise TradingRuntimePolicyError("POLICY_STRATEGY_ID_INVALID")
    return token


def normalize_policy_body(raw: Mapping[str, Any], *, mode: str) -> dict[str, Any]:
    if mode not in SUPPORTED_MODES:
        raise TradingRuntimePolicyError("LIVE_NOT_SUPPORTED" if mode == "LIVE" else "POLICY_MODE_INVALID")
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "new_entries_enabled": raw.get("new_entries_enabled"),
    }
    if not isinstance(body["new_entries_enabled"], bool):
        raise TradingRuntimePolicyError("POLICY_FIELD_INVALID:new_entries_enabled")
    for field in OPTIONAL_MONEY:
        body[field] = _money(raw.get(field), field=field)
    for field in OPTIONAL_COUNTS:
        body[field] = _count(raw.get(field), field=field)
    overrides_in = raw.get("strategy_overrides") or {}
    if overrides_in in ({}, None):
        body["strategy_overrides"] = {}
    else:
        if not isinstance(overrides_in, Mapping):
            raise TradingRuntimePolicyError("POLICY_FIELD_INVALID:strategy_overrides")
        overrides: dict[str, dict[str, Any]] = {}
        for key, spec in overrides_in.items():
            if not isinstance(spec, Mapping):
                raise TradingRuntimePolicyError("POLICY_FIELD_INVALID:strategy_overrides")
            sid = _strategy_id(key)
            item: dict[str, Any] = {}
            for field in OVERRIDE_MONEY:
                item[field] = _money(spec.get(field), field=f"strategy_overrides.{sid}.{field}")
            for field in OVERRIDE_COUNTS:
                item[field] = _count(spec.get(field), field=f"strategy_overrides.{sid}.{field}")
            overrides[sid] = item
        body["strategy_overrides"] = dict(sorted(overrides.items()))
    return body


def policy_content_sha256(body: Mapping[str, Any]) -> str:
    payload = {
        key: body[key]
        for key in (
            "schema",
            "schema_version",
            "mode",
            "new_entries_enabled",
            *OPTIONAL_MONEY,
            *OPTIONAL_COUNTS,
            "strategy_overrides",
        )
    }
    return canonical_sha256(payload)


def attach_revision_identity(
    body: Mapping[str, Any],
    *,
    revision: int,
    created_at: str,
    reason: str,
    previous_policy_sha256: str,
    policy_id: str | None = None,
) -> dict[str, Any]:
    content_hash = policy_content_sha256(body)
    policy = dict(body)
    policy["revision"] = int(revision)
    policy["created_at"] = created_at
    policy["reason"] = str(reason)
    policy["previous_policy_sha256"] = previous_policy_sha256
    policy["policy_id"] = policy_id or f"TRP-{body['mode']}-R{revision}"
    policy["policy_sha256"] = canonical_sha256(
        {
            "content_sha256": content_hash,
            "mode": body["mode"],
            "revision": int(revision),
            "previous_policy_sha256": previous_policy_sha256,
        }
    )
    return policy


def resolve_current_policy(store: PaperPlaneStore, mode: str) -> dict[str, Any]:
    if mode == "LIVE":
        raise TradingRuntimePolicyError("LIVE_NOT_SUPPORTED")
    if mode not in SUPPORTED_MODES:
        raise TradingRuntimePolicyError("POLICY_MODE_INVALID")
    row = store.latest_runtime_policy_row(mode)
    if row is None:
        return {
            "status": STATUS_NOT_CONFIGURED,
            "mode": mode,
            "policy": None,
            "revision": None,
            "policy_sha256": GENESIS_POLICY_SHA256,
        }
    try:
        loaded = json.loads(row["policy_json"])
        if not isinstance(loaded, Mapping):
            raise TradingRuntimePolicyError("RUNTIME_POLICY_INVALID")
        body = normalize_policy_body(loaded, mode=mode)
        expected = attach_revision_identity(
            body,
            revision=int(row["revision"]),
            created_at=str(row["created_at"]),
            reason=str(row["reason"]),
            previous_policy_sha256=str(row["previous_policy_sha256"]),
            policy_id=str(loaded.get("policy_id") or f"TRP-{mode}-R{row['revision']}"),
        )
        if str(row["policy_sha256"]) != expected["policy_sha256"]:
            raise TradingRuntimePolicyError("RUNTIME_POLICY_INVALID")
    except (TradingRuntimePolicyError, TypeError, ValueError, json.JSONDecodeError, KeyError):
        return {
            "status": STATUS_INVALID,
            "mode": mode,
            "policy": None,
            "revision": int(row["revision"]) if row.get("revision") is not None else None,
            "policy_sha256": str(row.get("policy_sha256") or ""),
        }
    return {
        "status": STATUS_VALID,
        "mode": mode,
        "policy": expected,
        "revision": expected["revision"],
        "policy_sha256": expected["policy_sha256"],
        "created_at": expected["created_at"],
        "reason": expected["reason"],
    }


def show_policy(store: PaperPlaneStore, mode: str) -> dict[str, Any]:
    current = resolve_current_policy(store, mode)
    history = store.runtime_policy_history(mode)
    return {
        "schema": SCHEMA,
        "operation": "SHOW",
        **current,
        "history_count": len(history),
        "history": history,
    }


def _override_for(policy: Mapping[str, Any] | None, strategy_id: str) -> Mapping[str, Any]:
    if not policy:
        return {}
    overrides = policy.get("strategy_overrides") or {}
    spec = overrides.get(strategy_id)
    return spec if isinstance(spec, Mapping) else {}


def runtime_entry_cap(policy: Mapping[str, Any] | None, strategy_id: str) -> Decimal | None:
    if not policy:
        return None
    override = _override_for(policy, strategy_id).get("entry_notional_cap_usd")
    if override is not None:
        return Decimal(str(override))
    global_cap = policy.get("global_entry_notional_cap_usd")
    if global_cap is not None:
        return Decimal(str(global_cap))
    return None


def effective_entry_notional(
    *,
    strategy_requested: Decimal,
    runtime_cap: Decimal | None,
) -> Decimal:
    if runtime_cap is None:
        return strategy_requested
    return min(strategy_requested, runtime_cap)


def classify_diff(current: Mapping[str, Any] | None, candidate: Mapping[str, Any]) -> str:
    tightening = False
    relaxation = False

    def _note(old: Any, new: Any, *, more_restrictive_when_smaller: bool) -> None:
        nonlocal tightening, relaxation
        if old == new:
            return
        if old is None and new is not None:
            tightening = True
            return
        if old is not None and new is None:
            relaxation = True
            return
        if more_restrictive_when_smaller:
            if Decimal(str(new)) < Decimal(str(old)):
                tightening = True
            elif Decimal(str(new)) > Decimal(str(old)):
                relaxation = True
        else:
            if int(new) < int(old):
                tightening = True
            elif int(new) > int(old):
                relaxation = True

    if current is None:
        tightening = True
    else:
        if current.get("new_entries_enabled") and not candidate.get("new_entries_enabled"):
            tightening = True
        if not current.get("new_entries_enabled") and candidate.get("new_entries_enabled"):
            relaxation = True
        for field in OPTIONAL_MONEY:
            _note(current.get(field), candidate.get(field), more_restrictive_when_smaller=True)
        for field in OPTIONAL_COUNTS:
            _note(current.get(field), candidate.get(field), more_restrictive_when_smaller=False)
        old_over = current.get("strategy_overrides") or {}
        new_over = candidate.get("strategy_overrides") or {}
        keys = set(old_over) | set(new_over)
        for key in keys:
            old_item = old_over.get(key) or {}
            new_item = new_over.get(key) or {}
            for field in OVERRIDE_MONEY:
                _note(old_item.get(field), new_item.get(field), more_restrictive_when_smaller=True)
            for field in OVERRIDE_COUNTS:
                _note(old_item.get(field), new_item.get(field), more_restrictive_when_smaller=False)
    if tightening and relaxation:
        return "MIXED"
    if tightening:
        return "TIGHTENING"
    if relaxation:
        return "RELAXATION"
    return "NO_CHANGE"


def check_policy(
    store: PaperPlaneStore,
    *,
    mode: str,
    candidate_raw: Mapping[str, Any],
) -> dict[str, Any]:
    current = resolve_current_policy(store, mode)
    candidate_body = normalize_policy_body(candidate_raw, mode=mode)
    current_policy = current.get("policy") if current["status"] == STATUS_VALID else None
    classification = (
        "BLOCKED_INVALID"
        if current["status"] == STATUS_INVALID
        else classify_diff(current_policy, candidate_body)
    )
    return {
        "schema": SCHEMA,
        "operation": "CHECK",
        "mode": mode,
        "current_status": current["status"],
        "current_policy": current_policy,
        "candidate": candidate_body,
        "classification": classification,
        "expected_current_revision": current.get("revision"),
        "expected_current_sha256": current.get("policy_sha256"),
        "effect": {
            "new_entries": candidate_body["new_entries_enabled"],
            "entry_size": candidate_body.get("global_entry_notional_cap_usd"),
            "position_limits": {
                "global": candidate_body.get("max_total_open_positions"),
                "strategy_default": candidate_body.get("default_strategy_max_open_positions"),
                "mint": candidate_body.get("max_open_positions_per_mint"),
            },
            "notional_limits": {
                "global": candidate_body.get("max_total_open_notional_usd"),
                "strategy_default": candidate_body.get("default_strategy_max_open_notional_usd"),
                "mint": candidate_body.get("max_open_notional_per_mint_usd"),
            },
        },
    }


def _request_fingerprint(request: Mapping[str, Any]) -> str:
    return json.dumps(dict(request), sort_keys=True, separators=(",", ":"))


def _replay_or_conflict(
    store: PaperPlaneStore,
    *,
    idempotency_key: str,
    command_type: str,
    request: Mapping[str, Any],
) -> dict[str, Any] | None:
    existing = store.get_operator_command(idempotency_key)
    if existing is None:
        return None
    stored_request = json.loads(existing["request_json"])
    if str(existing.get("command_type")) != command_type or _request_fingerprint(
        stored_request
    ) != _request_fingerprint(request):
        raise TradingRuntimePolicyError("POLICY_IDEMPOTENCY_REQUEST_MISMATCH")
    payload = json.loads(existing["result_json"])
    payload["idempotent"] = True
    payload["idempotency_key"] = idempotency_key
    return payload


def _persist_policy_revision(
    store: PaperPlaneStore,
    *,
    mode: str,
    body: dict[str, Any],
    expected_current_sha256: str,
    reason: str,
    command_type: str,
    idempotency_key: str,
    request: Mapping[str, Any],
) -> dict[str, Any]:
    current = resolve_current_policy(store, mode)
    if current["status"] == STATUS_INVALID:
        raise TradingRuntimePolicyError("RUNTIME_POLICY_INVALID")
    if str(expected_current_sha256) != str(current.get("policy_sha256")):
        raise TradingRuntimePolicyError("POLICY_STALE_WRITE_DENIED")
    revision = 1 if current["revision"] is None else int(current["revision"]) + 1
    policy = attach_revision_identity(
        body,
        revision=revision,
        created_at=_now(),
        reason=reason,
        previous_policy_sha256=str(current.get("policy_sha256") or GENESIS_POLICY_SHA256),
    )
    store.append_runtime_policy_revision(policy)
    result = {
        "command_type": command_type,
        "status": "APPLIED" if command_type == COMMAND_APPLY else "ROLLED_BACK",
        "mode": mode,
        "revision": policy["revision"],
        "policy_sha256": policy["policy_sha256"],
        "previous_policy_sha256": policy["previous_policy_sha256"],
        "readback": resolve_current_policy(store, mode),
    }
    store.record_operator_command(
        idempotency_key=idempotency_key,
        command_type=command_type,
        request=request,
        result=result,
    )
    result["idempotent"] = False
    result["idempotency_key"] = idempotency_key
    return result


def apply_policy(
    root: Path,
    store: PaperPlaneStore,
    *,
    mode: str,
    candidate_raw: Mapping[str, Any],
    expected_current_sha256: str,
    idempotency_key: str,
    owner_authorization_phrase: str,
    reason: str,
) -> dict[str, Any]:
    require_owner_authorization(root, owner_authorization_phrase)
    if not idempotency_key:
        raise TradingRuntimePolicyError("COMMAND_IDEMPOTENCY_KEY_REQUIRED")
    body = normalize_policy_body(candidate_raw, mode=mode)
    request = {
        "mode": mode,
        "expected_current_sha256": expected_current_sha256,
        "candidate": body,
        "reason": reason,
    }
    with store.immediate_write():
        replayed = _replay_or_conflict(
            store,
            idempotency_key=idempotency_key,
            command_type=COMMAND_APPLY,
            request=request,
        )
        if replayed is not None:
            return replayed
        return _persist_policy_revision(
            store,
            mode=mode,
            body=body,
            expected_current_sha256=expected_current_sha256,
            reason=reason,
            command_type=COMMAND_APPLY,
            idempotency_key=idempotency_key,
            request=request,
        )


def rollback_policy(
    root: Path,
    store: PaperPlaneStore,
    *,
    mode: str,
    expected_current_sha256: str,
    idempotency_key: str,
    owner_authorization_phrase: str,
) -> dict[str, Any]:
    require_owner_authorization(root, owner_authorization_phrase)
    if not idempotency_key:
        raise TradingRuntimePolicyError("COMMAND_IDEMPOTENCY_KEY_REQUIRED")
    request = {
        "mode": mode,
        "expected_current_sha256": expected_current_sha256,
        "reason": "ROLLBACK",
    }
    with store.immediate_write():
        replayed = _replay_or_conflict(
            store,
            idempotency_key=idempotency_key,
            command_type=COMMAND_ROLLBACK,
            request=request,
        )
        if replayed is not None:
            return replayed
        current = resolve_current_policy(store, mode)
        if current["status"] != STATUS_VALID or current["policy"] is None:
            raise TradingRuntimePolicyError("POLICY_ROLLBACK_NO_CURRENT")
        if str(expected_current_sha256) != str(current.get("policy_sha256")):
            raise TradingRuntimePolicyError("POLICY_STALE_WRITE_DENIED")
        previous_hash = str(current["policy"]["previous_policy_sha256"])
        if previous_hash == GENESIS_POLICY_SHA256:
            raise TradingRuntimePolicyError("POLICY_ROLLBACK_NO_PREVIOUS")
        previous = store.runtime_policy_by_sha256(mode, previous_hash)
        if previous is None:
            raise TradingRuntimePolicyError("POLICY_ROLLBACK_PREVIOUS_MISSING")
        previous_body = normalize_policy_body(json.loads(previous["policy_json"]), mode=mode)
        return _persist_policy_revision(
            store,
            mode=mode,
            body=previous_body,
            expected_current_sha256=expected_current_sha256,
            reason="ROLLBACK",
            command_type=COMMAND_ROLLBACK,
            idempotency_key=idempotency_key,
            request=request,
        )


def _as_decimal(value: Any) -> Decimal | None:
    if value in {None, ""}:
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite():
        return None
    return amount


def position_exposure(position: Mapping[str, Any]) -> tuple[Decimal | None, bool]:
    """Return (notional, unknown_required).

    Pre-fill uses admitted notional. After canonical entry fill uses entered
    notional. Unknown required exposure is never treated as zero.
    """

    entered = _as_decimal(position.get("entered_notional_usd_dec"))
    if entered is not None:
        return entered, False
    admitted = _as_decimal(position.get("admitted_entry_notional_usd_dec"))
    if admitted is not None:
        return admitted, False
    return None, True


def evaluate_admission(
    *,
    mode: str,
    strategy: Mapping[str, Any],
    bot: Mapping[str, Any],
    mint: str,
    policy_status: str,
    policy: Mapping[str, Any] | None,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    if mode == "LIVE":
        raise TradingRuntimePolicyError("LIVE_NOT_SUPPORTED")
    reason_codes: list[str] = []
    strategy_id = str(strategy["strategy_id"])
    strategy_requested = Decimal(str(strategy["notional_policy"]["notional_usd"]))
    strategy_max_open = int(strategy["risk_policy"]["max_open_positions"])
    cap = runtime_entry_cap(policy if policy_status == STATUS_VALID else None, strategy_id)
    effective = effective_entry_notional(strategy_requested=strategy_requested, runtime_cap=cap)

    def _block(code: str) -> dict[str, Any]:
        if code not in reason_codes:
            reason_codes.append(code)
        return _snapshot(
            decision=code if code.startswith("BLOCK") else f"BLOCK_{code}",
            reason_codes=reason_codes,
            mode=mode,
            strategy=strategy,
            mint=mint,
            bot=bot,
            policy_status=policy_status,
            policy=policy,
            strategy_requested=strategy_requested,
            effective=effective,
            inventory=inventory,
        )

    if str(bot.get("status")) in {"DRAINING", "STOPPED"}:
        return _block("BOT_STATUS_BLOCKS_ENTRY")
    if int(bot.get("entries_paused") or 0) == 1:
        return _block("ENTRIES_PAUSED")
    if policy_status == STATUS_INVALID:
        return _block("RUNTIME_POLICY_INVALID")
    if policy_status == STATUS_VALID and policy is not None and not policy.get("new_entries_enabled"):
        return _block("BLOCK_NEW_ENTRIES_DISABLED")

    override = _override_for(policy if policy_status == STATUS_VALID else None, strategy_id)
    runtime_strategy_max = override.get("max_open_positions")
    if runtime_strategy_max is None and policy_status == STATUS_VALID and policy is not None:
        runtime_strategy_max = policy.get("default_strategy_max_open_positions")
    effective_strategy_max = strategy_max_open
    if runtime_strategy_max is not None:
        effective_strategy_max = min(strategy_max_open, int(runtime_strategy_max))

    global_count = int(inventory["global_count"])
    strategy_count = int(inventory["strategy_count"])
    mint_count = int(inventory["mint_count"])
    bot_count = int(inventory.get("bot_count") or 0)
    if bot_count >= strategy_max_open:
        return _block("BLOCK_MAX_OPEN_POSITIONS")
    if runtime_strategy_max is not None:
        if inventory.get("strategy_identity_unknown"):
            return _block("RUNTIME_EXPOSURE_UNKNOWN")
        if strategy_count >= int(runtime_strategy_max):
            return _block("BLOCK_RUNTIME_STRATEGY_MAX_OPEN")
    if policy_status == STATUS_VALID and policy is not None:
        global_max = policy.get("max_total_open_positions")
        if global_max is not None and global_count >= int(global_max):
            return _block("BLOCK_GLOBAL_MAX_OPEN_POSITIONS")
        mint_max = policy.get("max_open_positions_per_mint")
        if mint_max is not None and mint_count >= int(mint_max):
            return _block("BLOCK_MINT_MAX_OPEN_POSITIONS")

        def _notional_block(
            current: Decimal | None,
            unknown: bool,
            limit: Any,
            code: str,
        ) -> dict[str, Any] | None:
            if limit is None:
                return None
            if unknown or current is None:
                return _block("RUNTIME_EXPOSURE_UNKNOWN")
            if current + effective > Decimal(str(limit)):
                return _block(code)
            return None

        blocked = _notional_block(
            inventory.get("global_notional"),
            bool(inventory.get("global_unknown")),
            policy.get("max_total_open_notional_usd"),
            "BLOCK_GLOBAL_OPEN_NOTIONAL",
        )
        if blocked:
            return blocked
        strategy_notional_limit = override.get("max_open_notional_usd")
        if strategy_notional_limit is None:
            strategy_notional_limit = policy.get("default_strategy_max_open_notional_usd")
        blocked = _notional_block(
            inventory.get("strategy_notional"),
            bool(inventory.get("strategy_unknown") or inventory.get("strategy_identity_unknown")),
            strategy_notional_limit,
            "BLOCK_STRATEGY_OPEN_NOTIONAL",
        )
        if blocked:
            return blocked
        blocked = _notional_block(
            inventory.get("mint_notional"),
            bool(inventory.get("mint_unknown")),
            policy.get("max_open_notional_per_mint_usd"),
            "BLOCK_MINT_OPEN_NOTIONAL",
        )
        if blocked:
            return blocked

    snapshot = _snapshot(
        decision="ALLOW",
        reason_codes=["WITHIN_LIMIT"],
        mode=mode,
        strategy=strategy,
        mint=mint,
        bot=bot,
        policy_status=policy_status,
        policy=policy,
        strategy_requested=strategy_requested,
        effective=effective,
        inventory=inventory,
    )
    snapshot["effective_entry_notional_usd_dec"] = format(effective, "f")
    snapshot["strategy_requested_notional_usd_dec"] = format(strategy_requested, "f")
    snapshot["effective_strategy_max_open_positions"] = effective_strategy_max
    return snapshot


def _snapshot(
    *,
    decision: str,
    reason_codes: list[str],
    mode: str,
    strategy: Mapping[str, Any],
    mint: str,
    bot: Mapping[str, Any],
    policy_status: str,
    policy: Mapping[str, Any] | None,
    strategy_requested: Decimal,
    effective: Decimal,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "decision": decision if decision.startswith("ALLOW") or decision.startswith("BLOCK") else decision,
        "reason_codes": list(reason_codes),
        "mode": mode,
        "strategy_id": strategy["strategy_id"],
        "strategy_version": strategy["strategy_version"],
        "bot_instance_id": bot.get("bot_instance_id"),
        "mint": mint,
        "strategy_requested_notional_usd_dec": format(strategy_requested, "f"),
        "effective_entry_notional_usd_dec": format(effective, "f"),
        "runtime_policy_status": policy_status,
        "runtime_policy_revision": None if policy is None else policy.get("revision"),
        "runtime_policy_sha256": None if policy is None else policy.get("policy_sha256"),
        "current_global_position_count": inventory.get("global_count"),
        "current_strategy_position_count": inventory.get("strategy_count"),
        "current_mint_position_count": inventory.get("mint_count"),
        "current_bot_position_count": inventory.get("bot_count"),
        "current_global_open_risk_notional_usd": (
            None if inventory.get("global_notional") is None else format(inventory["global_notional"], "f")
        ),
        "current_strategy_open_risk_notional_usd": (
            None
            if inventory.get("strategy_notional") is None
            else format(inventory["strategy_notional"], "f")
        ),
        "current_mint_open_risk_notional_usd": (
            None if inventory.get("mint_notional") is None else format(inventory["mint_notional"], "f")
        ),
        "open_risk_states": sorted(OPEN_RISK_STATES),
    }


def compose_runtime_envelope(store: PaperPlaneStore, git_strategies: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Owner-facing requested vs runtime vs effective envelope. Read-only."""

    from decimal import Decimal

    modes: dict[str, Any] = {}
    for mode in ("PAPER", "SHADOW"):
        current = resolve_current_policy(store, mode)
        inventory = store.open_risk_inventory(mode=mode, strategy_id="", mint="")
        policy = current.get("policy") if current["status"] == STATUS_VALID else None
        modes[mode] = {
            "status": current["status"],
            "revision": current.get("revision"),
            "changed_at": None if policy is None else policy.get("created_at"),
            "policy_sha256": current.get("policy_sha256"),
            "new_entries_enabled": None if policy is None else policy.get("new_entries_enabled"),
            "global_entry_notional_cap_usd": None if policy is None else policy.get("global_entry_notional_cap_usd"),
            "max_total_open_positions": None if policy is None else policy.get("max_total_open_positions"),
            "max_total_open_notional_usd": None if policy is None else policy.get("max_total_open_notional_usd"),
            "active_risk_positions": inventory["global_count"],
            "open_risk_notional_usd": (
                None if inventory["global_unknown"] else format(inventory["global_notional"], "f")
            ),
            "open_risk_notional_unknown": inventory["global_unknown"],
        }
    by_strategy: list[dict[str, Any]] = []
    for spec in git_strategies:
        strategy_id = str(spec.get("strategy_id") or "")
        requested = spec.get("notional_usd")
        if requested is None:
            requested = (spec.get("notional_policy") or {}).get("notional_usd")
        declared_max = spec.get("max_open_positions")
        if declared_max is None:
            declared_max = (spec.get("risk_policy") or {}).get("max_open_positions")
        for mode in ("PAPER", "SHADOW"):
            current = resolve_current_policy(store, mode)
            policy = current.get("policy") if current["status"] == STATUS_VALID else None
            inventory = store.open_risk_inventory(
                mode=mode, strategy_id=strategy_id, mint=""
            )
            cap = runtime_entry_cap(policy, strategy_id)
            requested_dec = Decimal(str(requested)) if requested is not None else None
            effective = (
                None
                if requested_dec is None
                else effective_entry_notional(strategy_requested=requested_dec, runtime_cap=cap)
            )
            runtime_max = None
            if policy is not None:
                override = (policy.get("strategy_overrides") or {}).get(strategy_id) or {}
                runtime_max = override.get("max_open_positions")
                if runtime_max is None:
                    runtime_max = policy.get("default_strategy_max_open_positions")
            effective_max = declared_max
            if declared_max is not None and runtime_max is not None:
                effective_max = min(int(declared_max), int(runtime_max))
            elif runtime_max is not None:
                effective_max = int(runtime_max)
            by_strategy.append(
                {
                    "mode": mode,
                    "strategy_id": strategy_id,
                    "strategy_version": spec.get("strategy_version"),
                    "requested_notional_usd": None if requested_dec is None else format(requested_dec, "f"),
                    "runtime_entry_cap_usd": None if cap is None else format(cap, "f"),
                    "effective_next_entry_notional_usd": None if effective is None else format(effective, "f"),
                    "active_positions": inventory["strategy_count"],
                    "effective_max_open_positions": effective_max,
                    "open_risk_notional_usd": (
                        None
                        if inventory["strategy_unknown"]
                        else format(inventory["strategy_notional"], "f")
                    ),
                    "blocker": (
                        "NEW_ENTRIES_DISABLED"
                        if policy is not None and not policy.get("new_entries_enabled")
                        else current["status"]
                    ),
                }
            )
    return {"modes": modes, "by_strategy": by_strategy}
