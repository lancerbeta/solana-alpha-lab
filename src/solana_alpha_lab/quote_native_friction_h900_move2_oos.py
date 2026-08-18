"""MOVE 2 WRAP: disjoint Free-key replication of the frozen H900 sign test."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from solana_alpha_lab.quote_native_admissible_friction_audition import (
    AUTHORITY_PHRASE as A1_AUTHORITY_PHRASE,
    ATOM_ID as A1_ATOM_ID,
    AuditionError,
    canonical_json,
    run_campaign,
    sha256_bytes,
    validate_policy as validate_audition_policy,
)
from solana_alpha_lab.quote_native_live_variation_campaign import select_cohort

ATOM_ID = "QUOTE_NATIVE_FRICTION_H900_MOVE2_OOS_V1"
AUTHORITY_PHRASE = (
    "OK QUOTE_NATIVE_FRICTION_H900_MOVE2_OOS_V1: one fresh Jupiter Free-key "
    "quote-native campaign; local process-environment key only; Tokens V2 "
    "/recent and /toptraded/1h plus quote-only /swap/v2/order; x-api-key header "
    "only; no .env; no key in URL/log/receipt/Git; no taker, /build, /execute, "
    "wallet, signer, transaction, paid plan, second provider, retry or "
    "fallback; cash cap $0; call cap 60; global pace >=3s; 6 RECENT + 6 TRADED "
    "live outcome-blind cohort excluding the 12 A1 frozen_cells mints "
    "hash-bound to runtime receipt "
    "75f60a155b7db6ddb8c801c9ff5060ce5e4e7fe641b836ff35edeb91534c308e; "
    "hash-bound row observed_at and attempt reservation before credential "
    "read required for capture PASS; freeze the same QuotedRoundTripFriction(t0) "
    "to QuotedLiquidationRecovery(H900) ordinal sign test; do not fit a "
    "concordance threshold on the A1 31/14 sample; H3600 robustness only not "
    "searchable Y; capture FAIL pauses with no recapture-only retry; capture "
    "PASS plus sample invalid does not close the family; capture PASS plus "
    "sample valid plus concordant <= discordant closes the exact mechanism; "
    "capture PASS plus sample valid plus concordant > discordant is "
    "REPLICATED_SIGN_NOT_ALPHA not alpha and not MOVE 3; no H13/H11/H07/H02 "
    "unpark; no NetReturn/alpha."
)
A1_RUNTIME_RELATIVE = (
    "docs/evidence/quote_native_admissible_friction_audition/"
    "a1_quote_native_admissible_friction_audition_runtime_receipt_v1.json"
)
A1_RUNTIME_SHA256 = "75f60a155b7db6ddb8c801c9ff5060ce5e4e7fe641b836ff35edeb91534c308e"
EXCLUDED_MINT_COUNT = 12
CONCORDANCE_RULE = "ORDINAL_SIGN_TEST_NO_RATE_FLOOR"
RECEIPT_SCHEMA = "smial.quote-native-friction-h900-move2-oos.runtime-receipt"
COHORT_SNAPSHOT_SCHEMA = "smial.quote-native-friction-h900-move2-oos.cohort-snapshot"
COHORT_SNAPSHOT_NAME = "cohort_snapshot.json"
WRAPPED_SOL_MINT = "So11111111111111111111111111111111111111112"


class Move2Error(AuditionError):
    """Raised when the MOVE 2 OOS contract is violated."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Move2Error(code)


def load_exclusion_set(root: Path, policy: Mapping[str, Any]) -> dict[str, object]:
    binding = policy.get("a1_runtime_receipt")
    _require(isinstance(binding, Mapping), "A1_RUNTIME_BINDING_INVALID")
    _require(binding.get("path") == A1_RUNTIME_RELATIVE, "A1_RUNTIME_PATH_DRIFT")
    _require(binding.get("sha256") == A1_RUNTIME_SHA256, "A1_RUNTIME_SHA_DRIFT")
    _require(binding.get("excluded_mint_count") == EXCLUDED_MINT_COUNT, "A1_EXCLUSION_COUNT_DRIFT")
    relative = Path(str(binding["path"]))
    _require(not relative.is_absolute() and ".." not in relative.parts, "A1_RUNTIME_PATH_INVALID")
    payload = (root / relative).read_bytes()
    digest = sha256_bytes(payload)
    _require(digest == A1_RUNTIME_SHA256, "A1_RUNTIME_RECEIPT_HASH_MISMATCH")
    receipt = json.loads(payload.decode("utf-8"))
    _require(isinstance(receipt, dict), "A1_RUNTIME_RECEIPT_INVALID")
    cells = receipt.get("frozen_cells")
    _require(isinstance(cells, list) and len(cells) == EXCLUDED_MINT_COUNT, "A1_FROZEN_CELLS_INVALID")
    mints: list[str] = []
    for cell in cells:
        _require(isinstance(cell, Mapping), "A1_FROZEN_CELL_INVALID")
        mint = cell.get("mint")
        _require(isinstance(mint, str) and bool(mint), "A1_FROZEN_MINT_INVALID")
        mints.append(mint)
    unique = sorted(set(mints))
    _require(len(unique) == EXCLUDED_MINT_COUNT, "A1_FROZEN_MINTS_NOT_UNIQUE")
    return {
        "path": A1_RUNTIME_RELATIVE,
        "sha256": digest,
        "excluded_mint_count": EXCLUDED_MINT_COUNT,
        "excluded_mints": unique,
        "excluded_mint_set_sha256": sha256_bytes(canonical_json({"mints": unique})),
    }


def filter_discovery_payload(
    rows: list[Mapping[str, Any]],
    excluded_mints: set[str],
) -> list[Mapping[str, Any]]:
    filtered: list[Mapping[str, Any]] = []
    for row in rows:
        mint = row.get("id")
        if isinstance(mint, str) and mint in excluded_mints:
            continue
        filtered.append(row)
    return filtered


def select_cohort_excluding_a1(
    recent_payload: list[Mapping[str, Any]],
    traded_payload: list[Mapping[str, Any]],
    *,
    excluded_mints: set[str],
) -> dict[str, object]:
    return select_cohort(
        filter_discovery_payload(recent_payload, excluded_mints),
        filter_discovery_payload(traded_payload, excluded_mints),
    )


def assert_cohort_excludes_a1(
    cells: list[Mapping[str, Any]] | list[object],
    excluded_mints: set[str],
) -> None:
    for cell in cells:
        _require(isinstance(cell, Mapping), "MOVE2_CELL_INVALID")
        mint = cell.get("mint")
        _require(isinstance(mint, str), "MOVE2_CELL_MINT_INVALID")
        _require(mint not in excluded_mints, "A1_MINT_REUSED_IN_COHORT")


def classify_move2_terminal(
    *,
    capture: Mapping[str, Any],
    campaign: Mapping[str, Any],
    mechanism: Mapping[str, Any],
    wrapped_terminal: str,
    discovery_rows: list[Mapping[str, Any]],
    frozen_cells: list[object],
) -> str:
    if capture.get("accepted") is not True:
        return "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE"
    discovery_ok = all(
        str(row.get("terminal") or "") == "TOKEN_LIST_OBSERVED" for row in discovery_rows
    )
    if (
        wrapped_terminal == "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE"
        and discovery_ok
        and len(frozen_cells) != 12
    ):
        return "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY"
    campaign_verdict = str(campaign.get("campaign_verdict") or "")
    if campaign_verdict == "VARIATION_ABSENT_ON_TRADED_CONTROL":
        return "SAMPLE_INVALID_TRADED_CONTROL_KILL"
    if campaign_verdict != "VARIATION_PRESENT_NOT_MECHANISM":
        if wrapped_terminal in {
            "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY",
            "PAUSE_CLOSE_QUOTE_NATIVE_CURRENT_ALPHA_ROUTE",
        }:
            return (
                "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY"
                if discovery_ok
                else wrapped_terminal
            )
        return (
            wrapped_terminal
            if wrapped_terminal != "DIRECTIONAL_HINT_NOT_CONFIRMATION"
            else "SAMPLE_INVALID_INSUFFICIENT_COMPLETE_XY"
        )
    mechanism_verdict = str(mechanism.get("verdict") or "")
    if mechanism_verdict == "DIRECTIONAL_HINT_NOT_CONFIRMATION":
        return "REPLICATED_SIGN_NOT_ALPHA"
    if mechanism_verdict == "MECHANISM_NOT_SUPPORTED_ON_THIS_SAMPLE":
        return "CLOSE_EXACT_QUOTE_FRICTION_MECHANISM"
    if wrapped_terminal == "DIRECTIONAL_HINT_NOT_CONFIRMATION":
        return "REPLICATED_SIGN_NOT_ALPHA"
    if wrapped_terminal == "CLOSE_EXACT_QUOTE_FRICTION_MECHANISM":
        return "CLOSE_EXACT_QUOTE_FRICTION_MECHANISM"
    return wrapped_terminal


def family_closed(terminal: str) -> bool:
    return terminal == "CLOSE_EXACT_QUOTE_FRICTION_MECHANISM"


def validate_policy(policy: Mapping[str, Any], *, root: Path) -> dict[str, object]:
    _require(policy.get("atom_id") == ATOM_ID, "ATOM_ID_DRIFT")
    authority = policy.get("external_authority")
    _require(isinstance(authority, Mapping), "AUTHORITY_INVALID")
    _require(authority.get("owner_phrase") == AUTHORITY_PHRASE, "AUTHORITY_PHRASE_DRIFT")
    _require(policy.get("concordance_rule") == CONCORDANCE_RULE, "CONCORDANCE_RULE_DRIFT")
    _require("concordance_min_rate" not in policy, "CONCORDANCE_RATE_FLOOR_FIT_ON_A1")
    _require("concordance_rate_floor" not in policy, "CONCORDANCE_RATE_FLOOR_FIT_ON_A1")
    exclusion = load_exclusion_set(root, policy)
    shadow = dict(policy)
    shadow["atom_id"] = A1_ATOM_ID
    shadowed_authority = dict(authority)
    shadowed_authority["owner_phrase"] = A1_AUTHORITY_PHRASE
    shadow["external_authority"] = shadowed_authority
    validate_audition_policy(shadow, root=root)
    return exclusion


def remap_move2_receipt(
    wrapped: Mapping[str, Any],
    *,
    exclusion: Mapping[str, Any],
) -> dict[str, object]:
    receipt = dict(wrapped)
    cells = receipt.get("frozen_cells")
    cell_list = list(cells) if isinstance(cells, list) else []
    excluded = set(str(item) for item in exclusion["excluded_mints"])
    assert_cohort_excludes_a1(cell_list, excluded)
    capture = receipt.get("capture")
    campaign = receipt.get("campaign")
    mechanism = receipt.get("mechanism")
    discovery = receipt.get("discovery_observations")
    _require(isinstance(capture, Mapping), "CAPTURE_MISSING")
    _require(isinstance(campaign, Mapping), "CAMPAIGN_MISSING")
    _require(isinstance(mechanism, Mapping), "MECHANISM_MISSING")
    _require(isinstance(discovery, list), "DISCOVERY_MISSING")
    wrapped_terminal = str(receipt.get("terminal_outcome") or "")
    if wrapped_terminal in {
        "API_KEY_IN_URL_LOG_RECEIPT_OR_GIT",
        "RAW_BODY_CONTAINS_CREDENTIAL",
        "CALL_CAP_EXCEEDED",
        "RESPONSE_BYTES_EXCEEDED",
        "CREDENTIAL_READ_BEFORE_ATTEMPT_RESERVATION",
        "A1_MINT_REUSED_IN_COHORT",
        "A1_RUNTIME_RECEIPT_HASH_MISMATCH",
        "TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED",
        "CREDENTIAL_INVALID_OR_SCOPE_MISSING_OWNER_ACTION_REQUIRED",
    }:
        terminal = wrapped_terminal
    else:
        terminal = classify_move2_terminal(
            capture=capture,
            campaign=campaign,
            mechanism=mechanism,
            wrapped_terminal=wrapped_terminal,
            discovery_rows=discovery,
            frozen_cells=cell_list,
        )
    receipt["schema"] = RECEIPT_SCHEMA
    receipt["schema_version"] = "1.0"
    receipt["atom_id"] = ATOM_ID
    receipt["terminal_outcome"] = terminal
    receipt["family_close"] = family_closed(terminal)
    receipt["exclusion"] = {
        "path": exclusion["path"],
        "sha256": exclusion["sha256"],
        "excluded_mint_count": exclusion["excluded_mint_count"],
        "excluded_mint_set_sha256": exclusion["excluded_mint_set_sha256"],
    }
    receipt["concordance_rule"] = CONCORDANCE_RULE
    receipt["wrapped_capture_atom_id"] = A1_ATOM_ID
    receipt["move_3_executed"] = False
    if "cohort_snapshot" not in receipt:
        discovery_rows = list(discovery)
        recent_sha = ""
        traded_sha = ""
        for row in discovery_rows:
            if not isinstance(row, Mapping):
                continue
            transport = row.get("transport")
            digest = ""
            if isinstance(transport, Mapping):
                digest = str(transport.get("response_sha256") or "")
            if row.get("observation_id") == "DISCOVERY:RECENT":
                recent_sha = digest
            elif row.get("observation_id") == "DISCOVERY:TRADED":
                traded_sha = digest
        if len(recent_sha) == 64 and len(traded_sha) == 64:
            receipt["cohort_snapshot"] = {
                "discovery_recent_body_sha256": recent_sha,
                "discovery_traded_body_sha256": traded_sha,
                "cells_sha256": sha256_bytes(canonical_json({"cells": cell_list})),
                "reselected": False,
            }
    receipt["non_claims"] = [
        "NO_EXECUTE",
        "NO_TAKER_OR_SIGNER",
        "NO_TRANSACTION_BYTES_IN_GIT",
        "NO_ALPHA",
        "NO_NETRETURN",
        "NO_MOVE_3",
        "NO_PAID_PLAN",
        "NO_SECOND_PROVIDER",
        "NO_H3600_SEARCHABLE_Y",
        "NO_RECAPTURE_ONLY_SUFFIX",
        "NO_THRESHOLD_FIT",
        "NO_A1_RUNTIME_REWRITE",
        "NO_A1_MINT_REUSE",
    ]
    return receipt


def envelope_stem(observation_id: str) -> str:
    return observation_id.replace(":", "_")


def write_cohort_snapshot(
    path: Path,
    *,
    cells: list[Mapping[str, Any]],
    discovery_recent_body_sha256: str,
    discovery_traded_body_sha256: str,
) -> dict[str, object]:
    payload = {
        "schema": COHORT_SNAPSHOT_SCHEMA,
        "schema_version": "1.0",
        "cells": list(cells),
        "discovery_recent_body_sha256": discovery_recent_body_sha256,
        "discovery_traded_body_sha256": discovery_traded_body_sha256,
    }
    document = {
        **payload,
        "snapshot_sha256": sha256_bytes(canonical_json(payload)),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(canonical_json(document))
    except FileExistsError as exc:
        raise Move2Error("CREATE_ONLY_EXISTS") from exc
    return document


def load_cohort_snapshot(path: Path) -> dict[str, object]:
    _require(path.is_file(), "COHORT_SNAPSHOT_MISSING")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(loaded, dict), "COHORT_SNAPSHOT_INVALID")
    snapshot_sha256 = loaded.get("snapshot_sha256")
    payload = {key: value for key, value in loaded.items() if key != "snapshot_sha256"}
    _require(payload.get("schema") == COHORT_SNAPSHOT_SCHEMA, "COHORT_SNAPSHOT_SCHEMA_DRIFT")
    _require(snapshot_sha256 == sha256_bytes(canonical_json(payload)), "COHORT_SNAPSHOT_HASH_MISMATCH")
    cells = payload.get("cells")
    _require(isinstance(cells, list), "COHORT_SNAPSHOT_CELLS_INVALID")
    recent_sha = payload.get("discovery_recent_body_sha256")
    traded_sha = payload.get("discovery_traded_body_sha256")
    _require(isinstance(recent_sha, str) and len(recent_sha) == 64, "COHORT_SNAPSHOT_RECENT_SHA_INVALID")
    _require(isinstance(traded_sha, str) and len(traded_sha) == 64, "COHORT_SNAPSHOT_TRADED_SHA_INVALID")
    return {**payload, "snapshot_sha256": snapshot_sha256}


def discovery_body_sha_from_run_dir(run_dir: Path, observation_id: str) -> str:
    envelope_path = run_dir / f"{envelope_stem(observation_id)}.envelope.json"
    _require(envelope_path.is_file(), "DISCOVERY_ENVELOPE_MISSING")
    loaded = json.loads(envelope_path.read_text(encoding="utf-8"))
    _require(isinstance(loaded, dict), "ENVELOPE_INVALID")
    body_sha256 = str(loaded.get("body_sha256") or "")
    _require(len(body_sha256) == 64, "ENVELOPE_BODY_SHA_INVALID")
    bind_body_file(run_dir, loaded)
    return body_sha256


def bind_body_file(run_dir: Path, envelope: Mapping[str, Any]) -> bytes | None:
    observation_id = str(envelope.get("observation_id") or "")
    expected = str(envelope.get("body_sha256") or "")
    _require(len(expected) == 64, "ENVELOPE_BODY_SHA_INVALID")
    body_path = run_dir / f"{envelope_stem(observation_id)}.body"
    if not body_path.is_file():
        return None
    body = body_path.read_bytes()
    _require(sha256_bytes(body) == expected, "RECOVERY_BODY_SHA_MISMATCH")
    return body


def quote_view_from_body(body: bytes) -> dict[str, object]:
    loaded = json.loads(body.decode("utf-8"))
    _require(isinstance(loaded, dict), "QUOTE_BODY_INVALID")
    _require(loaded.get("transaction") in (None, ""), "TRANSACTION_BYTES_IN_RECOVERY")
    return {
        "in_amount": loaded.get("inAmount"),
        "out_amount": loaded.get("outAmount"),
        "router": loaded.get("router"),
        "mode": loaded.get("mode"),
        "request_id_present": bool(loaded.get("requestId")),
    }


def consumed_row_from_envelope(
    envelope: Mapping[str, Any],
    *,
    cells_by_identity: Mapping[str, Mapping[str, Any]] | None = None,
    body: bytes | None = None,
    wrapped_sol_mint: str = WRAPPED_SOL_MINT,
) -> dict[str, object]:
    from solana_alpha_lab.quote_native_admissible_friction_audition import capture_envelope

    observation_id = str(envelope.get("observation_id") or "")
    observed_at = str(envelope.get("observed_at") or "")
    body_sha256 = str(envelope.get("body_sha256") or "")
    bound = capture_envelope(
        observation_id=observation_id,
        observed_at=observed_at,
        body_sha256=body_sha256,
    )
    kind = "DISCOVERY_RECENT" if observation_id == "DISCOVERY:RECENT" else (
        "DISCOVERY_TRADED" if observation_id == "DISCOVERY:TRADED" else observation_id.split(":")[-1]
    )
    row: dict[str, object] = {
        "observation_id": observation_id,
        "kind": kind,
        "observed_at": observed_at,
        "capture_envelope_sha256": bound["envelope_sha256"],
        "transport": {"response_sha256": body_sha256},
        "consumed_call": True,
    }
    if observation_id.startswith("DISCOVERY:"):
        if body is not None:
            payload = json.loads(body.decode("utf-8"))
            row["terminal"] = "TOKEN_LIST_OBSERVED" if isinstance(payload, list) else "TOKEN_LIST_SHAPE_INVALID"
        return row
    parts = observation_id.split(":")
    _require(len(parts) == 3, "OBSERVATION_ID_INVALID")
    identity_id, amount, kind_name = parts
    cell = None if cells_by_identity is None else cells_by_identity.get(identity_id)
    _require(cell is not None, "RECOVERY_IDENTITY_NOT_IN_SNAPSHOT")
    mint = str(cell["mint"])
    stratum = str(cell["stratum"])
    row.update(
        {
            "identity_id": identity_id,
            "amount": amount,
            "mint": mint,
            "stratum": stratum,
            "kind": kind_name,
        }
    )
    if kind_name == "BUY_T0":
        row["input_mint"] = wrapped_sol_mint
        row["output_mint"] = mint
        row["amount"] = amount
    else:
        row["input_mint"] = mint
        row["output_mint"] = wrapped_sol_mint
        row["amount"] = amount
    if body is not None:
        from solana_alpha_lab.quote_native_evidence_fit_panel import PanelError, project_quote

        try:
            quote = project_quote(body)
            row["quote"] = quote
            row["terminal"] = quote.get("surface")
        except PanelError:
            row["terminal"] = "PROVIDER_TYPED_FAILURE"
    return row


def attach_lineage_to_git_receipt(
    receipt: Mapping[str, Any],
    *,
    snapshot: Mapping[str, Any],
) -> dict[str, object]:
    updated = dict(receipt)
    cells = updated.get("frozen_cells")
    _require(isinstance(cells, list), "FROZEN_CELLS_MISSING")
    snapshot_cells = snapshot.get("cells")
    _require(isinstance(snapshot_cells, list), "COHORT_SNAPSHOT_CELLS_INVALID")
    _require(
        sha256_bytes(canonical_json({"cells": cells}))
        == sha256_bytes(canonical_json({"cells": snapshot_cells})),
        "SNAPSHOT_CELLS_SHA_MISMATCH",
    )
    cells_by_identity = {
        str(cell["identity_id"]): cell
        for cell in cells
        if isinstance(cell, Mapping) and isinstance(cell.get("identity_id"), str)
    }
    observations = []
    for row in updated.get("observations") or []:
        _require(isinstance(row, Mapping), "OBSERVATION_INVALID")
        observation_id = str(row.get("observation_id") or "")
        parts = observation_id.split(":")
        if len(parts) != 3:
            observations.append(dict(row))
            continue
        identity_id, amount, kind_name = parts
        cell = cells_by_identity.get(identity_id)
        _require(cell is not None, "GIT_IDENTITY_NOT_IN_FROZEN_CELLS")
        mint = str(cell["mint"])
        enriched = dict(row)
        enriched.update(
            {
                "identity_id": identity_id,
                "amount": amount,
                "mint": mint,
                "stratum": str(cell["stratum"]),
                "kind": kind_name,
                "input_mint": WRAPPED_SOL_MINT if kind_name == "BUY_T0" else mint,
                "output_mint": mint if kind_name == "BUY_T0" else WRAPPED_SOL_MINT,
            }
        )
        observations.append(enriched)
    updated["observations"] = observations
    discovery = list(updated.get("discovery_observations") or [])
    recent_sha = ""
    traded_sha = ""
    for row in discovery:
        _require(isinstance(row, Mapping), "DISCOVERY_ROW_INVALID")
        transport = row.get("transport")
        _require(isinstance(transport, Mapping), "DISCOVERY_TRANSPORT_INVALID")
        digest = str(transport.get("response_sha256") or "")
        if row.get("observation_id") == "DISCOVERY:RECENT":
            recent_sha = digest
        elif row.get("observation_id") == "DISCOVERY:TRADED":
            traded_sha = digest
    _require(len(recent_sha) == 64 and len(traded_sha) == 64, "DISCOVERY_SHA_MISSING")
    _require(recent_sha == snapshot.get("discovery_recent_body_sha256"), "SNAPSHOT_RECENT_SHA_MISMATCH")
    _require(traded_sha == snapshot.get("discovery_traded_body_sha256"), "SNAPSHOT_TRADED_SHA_MISMATCH")
    updated["cohort_snapshot"] = {
        "discovery_recent_body_sha256": recent_sha,
        "discovery_traded_body_sha256": traded_sha,
        "cells_sha256": sha256_bytes(canonical_json({"cells": cells})),
        "snapshot_sha256": snapshot.get("snapshot_sha256"),
        "reselected": False,
    }
    return updated


def receipt_from_incomplete_local_run(
    policy: Mapping[str, Any],
    *,
    root: Path,
    reservation: Mapping[str, Any],
    run_dir: Path,
    credential_reads: int,
) -> dict[str, object]:
    from solana_alpha_lab.quote_native_admissible_friction_audition import (
        attempt_reservation_document,
        classify_audition_terminal,
        evaluate_capture,
        sanitize_wrapped_score,
        searchable_y_observations,
        unscored_campaign,
        unscored_mechanism,
    )
    from solana_alpha_lab.quote_native_friction_h900_falsifier import score_mechanism
    from solana_alpha_lab.quote_native_live_variation_campaign import score_campaign

    exclusion = validate_policy(policy, root=root)
    excluded = set(str(item) for item in exclusion["excluded_mints"])
    if not isinstance(reservation.get("reservation_sha256"), str) or len(
        str(reservation.get("reservation_sha256") or "")
    ) != 64:
        reservation = attempt_reservation_document(
            started_at=str(reservation.get("started_at") or ""),
            policy_sha256=str(reservation.get("policy_sha256") or ""),
        )
    snapshot = load_cohort_snapshot(run_dir / COHORT_SNAPSHOT_NAME)
    cells = list(snapshot["cells"])
    assert_cohort_excludes_a1(cells, excluded)
    envelopes: list[dict[str, object]] = []
    for path in sorted(run_dir.glob("*.envelope.json")):
        loaded = json.loads(path.read_text(encoding="utf-8"))
        _require(isinstance(loaded, dict), "ENVELOPE_INVALID")
        envelopes.append(loaded)
    _require(bool(envelopes), "NO_LOCAL_ENVELOPES")
    recent_sha = ""
    traded_sha = ""
    cells_by_identity = {
        str(cell["identity_id"]): cell
        for cell in cells
        if isinstance(cell, Mapping)
    }
    consumed: list[dict[str, object]] = []
    for envelope in envelopes:
        body = bind_body_file(run_dir, envelope)
        observation_id = str(envelope.get("observation_id") or "")
        if observation_id == "DISCOVERY:RECENT":
            recent_sha = str(envelope.get("body_sha256") or "")
        elif observation_id == "DISCOVERY:TRADED":
            traded_sha = str(envelope.get("body_sha256") or "")
        consumed.append(
            consumed_row_from_envelope(
                envelope,
                cells_by_identity=None if observation_id.startswith("DISCOVERY:") else cells_by_identity,
                body=body,
            )
        )
    _require(recent_sha == snapshot["discovery_recent_body_sha256"], "SNAPSHOT_RECENT_SHA_MISMATCH")
    _require(traded_sha == snapshot["discovery_traded_body_sha256"], "SNAPSHOT_TRADED_SHA_MISMATCH")
    discovery_rows = [
        row for row in consumed if str(row["observation_id"]).startswith("DISCOVERY:")
    ]
    observation_rows = [
        row for row in consumed if not str(row["observation_id"]).startswith("DISCOVERY:")
    ]
    capture = evaluate_capture(reservation=reservation, consumed_rows=consumed)
    h900_present = any(str(row.get("kind")) == "SELL_H900" for row in observation_rows)
    h3600_present = any(str(row.get("kind")) == "SELL_H3600" for row in observation_rows)
    if capture.get("accepted") is True and h900_present:
        campaign = sanitize_wrapped_score(score_campaign(observation_rows))
        mechanism = sanitize_wrapped_score(score_mechanism(searchable_y_observations(observation_rows)))
        mechanism["scored"] = True
        mechanism["searchable_y_kind"] = "SELL_H900"
        campaign["h3600_role"] = "PREDECLARED_ROBUSTNESS_NOT_SEARCHABLE_Y"
        terminal = classify_audition_terminal(
            capture=capture,
            campaign=campaign,
            mechanism=mechanism,
        )
        incomplete = not h3600_present
    else:
        campaign = unscored_campaign(reason="NOT_SCORED_INCOMPLETE_TRANSPORT")
        mechanism = unscored_mechanism(reason="NOT_SCORED_INCOMPLETE_TRANSPORT")
        terminal = "TRANSPORT_UNKNOWN_OWNER_ACTION_REQUIRED"
        incomplete = True
    wrapped = {
        "schema": RECEIPT_SCHEMA,
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "terminal_outcome": terminal,
        "preflight": {"credential_reads": 0},
        "credential_reads": credential_reads,
        "provider_requests": len(consumed),
        "retries": 0,
        "fallbacks": 0,
        "execute_calls": 0,
        "frozen_cells": cells,
        "cohort_snapshot": {
            "discovery_recent_body_sha256": recent_sha,
            "discovery_traded_body_sha256": traded_sha,
            "cells_sha256": sha256_bytes(canonical_json({"cells": cells})),
            "snapshot_sha256": snapshot.get("snapshot_sha256"),
            "reselected": False,
        },
        "discovery_observations": discovery_rows,
        "observations": observation_rows,
        "attempt_reservation": dict(reservation),
        "capture": capture,
        "campaign": campaign,
        "mechanism": mechanism,
        "family_close": False,
        "foreground_run_incomplete": incomplete,
        "h900_observed": h900_present,
        "h3600_observed": h3600_present,
    }
    return remap_move2_receipt(wrapped, exclusion=exclusion)


def run_move2_campaign(
    policy: Mapping[str, Any],
    *,
    root: Path,
    reservation: Mapping[str, Any],
    credential_loader: Callable[[], str],
    preflight_fn: Callable[..., Mapping[str, Any]] | None = None,
    opener: object | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleeper: Callable[[float], None] | None = None,
    monotonic_clock: Callable[[], float] | None = None,
    raw_sink: Callable[[str, bytes, str, str], None] | None = None,
    cohort_snapshot_path: Path | None = None,
) -> dict[str, object]:
    exclusion = validate_policy(policy, root=root)
    excluded = set(str(item) for item in exclusion["excluded_mints"])
    shadow = dict(policy)
    shadow["atom_id"] = A1_ATOM_ID
    shadowed_authority = dict(policy["external_authority"])
    shadowed_authority["owner_phrase"] = A1_AUTHORITY_PHRASE
    shadow["external_authority"] = shadowed_authority

    def select_fn(
        recent_payload: list[Mapping[str, Any]],
        traded_payload: list[Mapping[str, Any]],
    ) -> dict[str, object]:
        cohort = select_cohort_excluding_a1(
            recent_payload,
            traded_payload,
            excluded_mints=excluded,
        )
        if cohort_snapshot_path is not None:
            run_dir = cohort_snapshot_path.parent
            cells = cohort.get("cells")
            _require(isinstance(cells, list), "COHORT_CELLS_INVALID")
            write_cohort_snapshot(
                cohort_snapshot_path,
                cells=cells,
                discovery_recent_body_sha256=discovery_body_sha_from_run_dir(run_dir, "DISCOVERY:RECENT"),
                discovery_traded_body_sha256=discovery_body_sha_from_run_dir(run_dir, "DISCOVERY:TRADED"),
            )
        return cohort

    run_kwargs: dict[str, object] = {
        "reservation": reservation,
        "credential_loader": credential_loader,
        "opener": opener,
        "clock": clock,
        "sleeper": sleeper,
        "raw_sink": raw_sink,
        "select_cohort_fn": select_fn,
    }
    if monotonic_clock is not None:
        run_kwargs["monotonic_clock"] = monotonic_clock
    if preflight_fn is not None:
        run_kwargs["preflight_fn"] = preflight_fn
    wrapped = run_campaign(shadow, **run_kwargs)
    return remap_move2_receipt(wrapped, exclusion=exclusion)
