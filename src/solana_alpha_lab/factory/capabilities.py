"""Allowlisted Factory capabilities. Hypothesis logic lives here as WRAP, not in the runner."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable

from solana_alpha_lab.quote_native_admissible_friction_audition import (
    classify_audition_terminal,
)

CAP_OFFLINE_CANONICAL_RECEIPT_REPLAY = "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"


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
    for item in spec["data_requirements"]:
        relative = str(item["path"])
        path = root / relative
        if not path.is_file():
            missing.append(str(item["requirement_id"]))
            continue
        digest = _sha256(path)
        if digest != str(item["sha256"]):
            missing.append(f"{item['requirement_id']}:HASH_MISMATCH")
            continue
        available.append(str(item["requirement_id"]))
    return {
        "available": available,
        "missing": missing,
        "sufficient": not missing,
    }


def replay_canonical_receipts(
    spec: Mapping[str, Any],
    *,
    root: Path,
) -> dict[str, Any]:
    coverage = resolve_data_requirements(spec, root=root)
    if not coverage["sufficient"]:
        return {
            "status": "BLOCKED_DATA",
            "blocker": "MISSING_OR_MISMATCHED_EVIDENCE",
            "coverage": coverage,
            "terminal": None,
            "provider_api_rpc_wss_calls": 0,
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
    }


CAPABILITY_ROUTER: dict[str, Callable[..., dict[str, Any]]] = {
    CAP_OFFLINE_CANONICAL_RECEIPT_REPLAY: replay_canonical_receipts,
}


def execute_capability(
    spec: Mapping[str, Any],
    *,
    root: Path,
) -> dict[str, Any]:
    capabilities = list(spec.get("capabilities") or [])
    if len(capabilities) != 1:
        raise CapabilityError("CAPABILITY_SET_NOT_SINGLE")
    capability_id = str(capabilities[0])
    handler = CAPABILITY_ROUTER.get(capability_id)
    if handler is None:
        raise CapabilityError("CAPABILITY_NOT_ALLOWLISTED")
    if int(spec["evidence_budget"]["provider_api_rpc_wss_calls"]) != 0:
        raise CapabilityError("PROVIDER_BUDGET_NOT_ZERO")
    return handler(spec, root=root)
