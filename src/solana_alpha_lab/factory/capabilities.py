"""Allowlisted Factory capabilities. Hypothesis logic lives here as WRAP, not in the runner."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import yaml

from solana_alpha_lab.factory.friction_veto import (
    apply_friction_veto_to_receipt,
    load_friction_veto_rule,
)
from solana_alpha_lab.quote_native_admissible_friction_audition import (
    FACTORY_COMMISSIONING_ATOM_ID,
    FRICTION_VETO_ATOM_ID,
    AuditionError,
    attempt_reservation_document,
    canonical_json,
    classify_audition_terminal,
    run_campaign,
    validate_policy,
)
from solana_alpha_lab.quote_native_evidence_channel_qualification import (
    QualificationError,
    load_process_credential,
)
from solana_alpha_lab.quote_native_live_variation_campaign import select_cohort

CAP_OFFLINE_CANONICAL_RECEIPT_REPLAY = "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"
CAP_JUPITER_FREE_KEY_QUOTE_NATIVE_BOUNDED_CAPTURE = (
    "CAP-JUPITER-FREE-KEY-QUOTE-NATIVE-BOUNDED-CAPTURE-001"
)
INPUT_KINDS = frozenset(
    {
        "GIT_CANONICAL_RECEIPT",
        "GIT_CANONICAL_ACCEPTANCE",
        "CATALOG_ASSET",
        "CAPTURE_POLICY",
    }
)
PRODUCED_KINDS = frozenset({"PROVIDER_BOUNDED_CAPTURE"})
FACTORY_NON_CLAIMS = [
    "NO_EXECUTE",
    "NO_TAKER_OR_SIGNER",
    "NO_TRANSACTION_BYTES_IN_GIT",
    "NO_ALPHA",
    "NO_NETRETURN",
    "NO_MOVE_3",
    "NO_A1_REPLAY_AS_NEW_RESULT",
    "NO_MOVE_2_AS_NEW_RESULT",
    "NO_PAID_PLAN",
    "NO_SECOND_PROVIDER",
    "SCIENTIFIC_FAIL_MAY_STILL_BE_PRODUCT_PASS",
]


class CapabilityError(ValueError):
    """Raised when an allowlisted capability cannot execute fail-closed."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(root: Path, relative: str) -> dict[str, Any]:
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise CapabilityError("CAPABILITY_PATH_UNSAFE")
    path = root / relative
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CapabilityError("REQUIRED_EVIDENCE_MISSING") from exc
    if not isinstance(loaded, dict):
        raise CapabilityError("REQUIRED_EVIDENCE_INVALID")
    return loaded


def resolve_data_requirements(
    spec: Mapping[str, Any],
    *,
    root: Path,
) -> dict[str, Any]:
    available: list[str] = []
    missing: list[str] = []
    produced_missing: list[str] = []
    for item in spec["data_requirements"]:
        relative = str(item["path"])
        path = root / relative
        kind = str(item["kind"])
        expected = item.get("sha256")
        if kind in PRODUCED_KINDS:
            if not path.is_file():
                produced_missing.append(str(item["requirement_id"]))
                continue
            if expected and _sha256(path) != str(expected):
                missing.append(f"{item['requirement_id']}:HASH_MISMATCH")
                continue
            available.append(str(item["requirement_id"]))
            continue
        if not path.is_file():
            missing.append(str(item["requirement_id"]))
            continue
        digest = _sha256(path)
        if expected and digest != str(expected):
            missing.append(f"{item['requirement_id']}:HASH_MISMATCH")
            continue
        available.append(str(item["requirement_id"]))
    return {
        "available": available,
        "missing": missing,
        "produced_missing": produced_missing,
        "sufficient": not missing,
    }


def replay_canonical_receipts(
    spec: Mapping[str, Any],
    *,
    root: Path,
    authority_phrase: str | None = None,
    capture_hooks: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    del authority_phrase, capture_hooks
    coverage = resolve_data_requirements(spec, root=root)
    if not coverage["sufficient"]:
        return {
            "status": "BLOCKED_DATA",
            "blocker": "MISSING_OR_MISMATCHED_EVIDENCE",
            "coverage": coverage,
            "terminal": None,
            "provider_api_rpc_wss_calls": 0,
            "credential_reads": 0,
        }
    requirements = {str(item["requirement_id"]): item for item in spec["data_requirements"]}
    runtime = _load_json(root, str(requirements["RUNTIME_RECEIPT"]["path"]))
    acceptance = _load_json(root, str(requirements["ACCEPTANCE"]["path"]))
    method = str(spec["method"])
    if method != "classify_audition_terminal":
        raise CapabilityError("CAPABILITY_METHOD_NOT_ALLOWLISTED")
    derived = classify_audition_terminal(
        capture=runtime.get("capture") if isinstance(runtime.get("capture"), Mapping) else {},
        campaign=runtime.get("campaign") if isinstance(runtime.get("campaign"), Mapping) else {},
        mechanism=runtime.get("mechanism") if isinstance(runtime.get("mechanism"), Mapping) else {},
    )
    accepted_terminal = str(acceptance.get("terminal") or "")
    if derived != accepted_terminal:
        return {
            "status": "FAILED",
            "blocker": "TERMINAL_MISMATCH",
            "coverage": coverage,
            "terminal": derived,
            "accepted_terminal": accepted_terminal,
            "provider_api_rpc_wss_calls": 0,
            "credential_reads": 0,
        }
    return {
        "status": "COMPLETE",
        "blocker": "NONE",
        "coverage": coverage,
        "terminal": derived,
        "accepted_terminal": accepted_terminal,
        "result": derived,
        "uncertainty": "SCREENING_HINT_NOT_OOS_CONFIRMATION",
        "robustness": str(runtime.get("h3600_role") or "UNKNOWN"),
        "failure_modes": list(acceptance.get("limitations") or []),
        "provider_api_rpc_wss_calls": 0,
        "credential_reads": 0,
    }


def excluded_mints_from_spec(spec: Mapping[str, Any], *, root: Path) -> set[str]:
    excluded: set[str] = set()
    for item in spec["data_requirements"]:
        if str(item.get("kind")) == "GIT_CANONICAL_RECEIPT":
            excluded.update(_frozen_mints(root, str(item["path"])))
    return excluded


def drop_excluded_rows(
    rows: list[Mapping[str, Any]],
    excluded: set[str],
) -> list[Mapping[str, Any]]:
    kept: list[Mapping[str, Any]] = []
    for row in rows:
        mint = row.get("id")
        if isinstance(mint, str) and mint in excluded:
            continue
        kept.append(row)
    return kept


def _overlay_veto_receipt(
    spec: Mapping[str, Any],
    *,
    root: Path,
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    if str(receipt.get("atom_id") or "") != FRICTION_VETO_ATOM_ID:
        return dict(receipt)
    requirements = {str(item["requirement_id"]): item for item in spec["data_requirements"]}
    rule_item = requirements.get("VETO_RULE")
    if rule_item is None:
        raise CapabilityError("VETO_RULE_MISSING")
    rule = load_friction_veto_rule(root, str(rule_item["path"]))
    return apply_friction_veto_to_receipt(receipt, rule=rule)


def _blocked_authority(coverage: Mapping[str, Any], blocker: str) -> dict[str, Any]:
    return {
        "status": "BLOCKED_AUTHORITY",
        "blocker": blocker,
        "coverage": dict(coverage),
        "terminal": "BLOCKED_AUTHORITY",
        "result": "BLOCKED_AUTHORITY",
        "uncertainty": "LIVE_CAPTURE_NOT_AUTHORIZED",
        "robustness": "NOT_RUN",
        "failure_modes": [blocker],
        "provider_api_rpc_wss_calls": 0,
        "credential_reads": 0,
    }


def _frozen_mints(root: Path, relative: str) -> set[str]:
    loaded = _load_json(root, relative)
    mints: set[str] = set()
    cells = loaded.get("frozen_cells")
    if isinstance(cells, list):
        for cell in cells:
            if isinstance(cell, Mapping):
                mint = cell.get("mint")
                if isinstance(mint, str) and mint:
                    mints.add(mint)
    return mints


def _write_create_only(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise CapabilityError("CREATE_ONLY_EXISTS") from exc


def capture_quote_native_free_key(
    spec: Mapping[str, Any],
    *,
    root: Path,
    authority_phrase: str | None = None,
    capture_hooks: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    coverage = resolve_data_requirements(spec, root=root)
    if not coverage["sufficient"]:
        return {
            "status": "BLOCKED_DATA",
            "blocker": "MISSING_OR_MISMATCHED_EVIDENCE",
            "coverage": coverage,
            "terminal": None,
            "provider_api_rpc_wss_calls": 0,
            "credential_reads": 0,
        }
    requirements = {str(item["requirement_id"]): item for item in spec["data_requirements"]}
    if "RUNTIME_RECEIPT" in coverage["available"]:
        runtime = _overlay_veto_receipt(
            spec,
            root=root,
            receipt=_load_json(root, str(requirements["RUNTIME_RECEIPT"]["path"])),
        )
        terminal = str(runtime.get("terminal_outcome") or runtime.get("terminal") or "")
        return {
            "status": "COMPLETE",
            "blocker": "NONE",
            "coverage": coverage,
            "terminal": terminal,
            "result": terminal,
            "uncertainty": "SCREENING_HINT_NOT_OOS_CONFIRMATION",
            "robustness": str(runtime.get("h3600_role") or "UNKNOWN"),
            "failure_modes": list(runtime.get("non_claims") or FACTORY_NON_CLAIMS),
            "provider_api_rpc_wss_calls": int(runtime.get("provider_requests") or 0),
            "credential_reads": int(runtime.get("credential_reads") or 0),
            "receipt_relative": str(requirements["RUNTIME_RECEIPT"]["path"]),
        }
    expected_phrase = str(spec["parameters"]["required_owner_phrase"])
    policy_relative = str(requirements["CAPTURE_POLICY"]["path"])
    policy = yaml.safe_load((root / policy_relative).read_text(encoding="utf-8"))
    if not isinstance(policy, dict):
        raise CapabilityError("CAPTURE_POLICY_INVALID")
    validate_policy(policy, root=root)
    atom_id = str(policy.get("atom_id") or "")
    policy_phrase = str((policy.get("external_authority") or {}).get("owner_phrase") or "")
    if expected_phrase != policy_phrase:
        raise CapabilityError("AUTHORITY_PHRASE_DRIFT")
    if atom_id not in {FACTORY_COMMISSIONING_ATOM_ID, FRICTION_VETO_ATOM_ID}:
        raise CapabilityError("ATOM_ID_NOT_ALLOWLISTED")
    if authority_phrase != expected_phrase:
        blocker = (
            "OWNER_PHRASE_MISSING"
            if not authority_phrase
            else "AUTHORITY_PHRASE_INVALID"
        )
        return _blocked_authority(coverage, blocker)
    excluded = excluded_mints_from_spec(spec, root=root)
    hooks = dict(capture_hooks or {})
    clock = hooks.get("clock", lambda: datetime.now(UTC))
    started_at = clock()
    policy_sha256 = _sha256(root / policy_relative)
    reservation = attempt_reservation_document(
        started_at=started_at.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        policy_sha256=policy_sha256,
        atom_id=atom_id,
    )
    import os

    environ = hooks.get("environ", os.environ)

    def credential_loader() -> str:
        return load_process_credential(environ)

    def select_excluding(
        recent_payload: list[Mapping[str, Any]],
        traded_payload: list[Mapping[str, Any]],
    ) -> dict[str, object]:
        def drop(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
            return drop_excluded_rows(rows, excluded)

        return select_cohort(drop(recent_payload), drop(traded_payload))

    run_kwargs: dict[str, Any] = {
        "reservation": reservation,
        "credential_loader": credential_loader,
        "select_cohort_fn": select_excluding,
    }
    for key in ("opener", "clock", "sleeper", "monotonic_clock", "preflight_fn", "raw_sink"):
        if key in hooks:
            run_kwargs[key] = hooks[key]
    try:
        receipt = run_campaign(policy, **run_kwargs)
    except (AuditionError, QualificationError) as exc:
        return {
            "status": "FAILED",
            "blocker": str(exc),
            "coverage": coverage,
            "terminal": str(exc),
            "result": str(exc),
            "uncertainty": "CAPTURE_TYPED_FAILURE",
            "robustness": "NOT_SCORED",
            "failure_modes": [str(exc)],
            "provider_api_rpc_wss_calls": int(getattr(exc, "provider_requests", 0) or 0),
            "credential_reads": 1,
        }
    receipt = dict(receipt)
    receipt["atom_id"] = atom_id
    receipt["non_claims"] = list(FACTORY_NON_CLAIMS)
    receipt["excluded_prior_mints"] = sorted(excluded)
    receipt = _overlay_veto_receipt(spec, root=root, receipt=receipt)
    frozen = receipt.get("frozen_cells")
    if isinstance(frozen, list):
        reused = [
            cell.get("mint")
            for cell in frozen
            if isinstance(cell, Mapping) and cell.get("mint") in excluded
        ]
        if reused:
            return {
                "status": "FAILED",
                "blocker": "PRIOR_MINT_REUSED",
                "coverage": coverage,
                "terminal": "PRIOR_MINT_REUSED",
                "result": "PRIOR_MINT_REUSED",
                "uncertainty": "COHORT_NOT_COMMISSIONING_FRESH",
                "robustness": "NOT_SCORED",
                "failure_modes": ["PRIOR_MINT_REUSED"],
                "provider_api_rpc_wss_calls": int(receipt.get("provider_requests") or 0),
                "credential_reads": int(receipt.get("credential_reads") or 0),
            }
    runtime_relative = str(requirements["RUNTIME_RECEIPT"]["path"])
    if "RUNTIME_RECEIPT" in coverage["produced_missing"]:
        _write_create_only(root / runtime_relative, canonical_json(receipt))
    terminal = str(receipt.get("terminal_outcome") or receipt.get("terminal") or "")
    return {
        "status": "COMPLETE",
        "blocker": "NONE",
        "coverage": resolve_data_requirements(spec, root=root),
        "terminal": terminal,
        "result": terminal,
        "uncertainty": "SCREENING_HINT_NOT_OOS_CONFIRMATION",
        "robustness": str(receipt.get("h3600_role") or "UNKNOWN"),
        "failure_modes": list(FACTORY_NON_CLAIMS),
        "provider_api_rpc_wss_calls": int(receipt.get("provider_requests") or 0),
        "credential_reads": int(receipt.get("credential_reads") or 0),
        "receipt_relative": runtime_relative,
    }


CAPABILITY_ROUTER: dict[str, Callable[..., dict[str, Any]]] = {
    CAP_OFFLINE_CANONICAL_RECEIPT_REPLAY: replay_canonical_receipts,
    CAP_JUPITER_FREE_KEY_QUOTE_NATIVE_BOUNDED_CAPTURE: capture_quote_native_free_key,
}


def execute_capability(
    spec: Mapping[str, Any],
    *,
    root: Path,
    authority_phrase: str | None = None,
    capture_hooks: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    capabilities = list(spec.get("capabilities") or [])
    if len(capabilities) != 1:
        raise CapabilityError("CAPABILITY_SET_NOT_SINGLE")
    capability_id = str(capabilities[0])
    handler = CAPABILITY_ROUTER.get(capability_id)
    if handler is None:
        raise CapabilityError("CAPABILITY_NOT_ALLOWLISTED")
    budget = int(spec["evidence_budget"]["provider_api_rpc_wss_calls"])
    if capability_id == CAP_OFFLINE_CANONICAL_RECEIPT_REPLAY and budget != 0:
        raise CapabilityError("PROVIDER_BUDGET_NOT_ZERO")
    if capability_id == CAP_JUPITER_FREE_KEY_QUOTE_NATIVE_BOUNDED_CAPTURE:
        if budget < 1 or budget > 60:
            raise CapabilityError("PROVIDER_BUDGET_INVALID")
    return handler(
        spec,
        root=root,
        authority_phrase=authority_phrase,
        capture_hooks=capture_hooks,
    )
