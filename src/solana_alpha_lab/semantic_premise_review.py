"""Deterministic semantic-premise review profile over ARCHITECTURE_CRITIC."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

PROFILE_RELATIVE = "configs/semantic_premise_review_profile_v1.yaml"
PACKET_SCHEMA_RELATIVE = "catalog/schemas/semantic_premise_review_packet.schema.json"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
CLAIM_SCOPE_PACKET_PATH = "PACKET_INFORMATION_PATH"
LAUNCH_ISOLATION_PROCESS = "PROCESS_OBLIGATION"
PACKET_FINGERPRINT_FINDING_PREFIX = "packet_fingerprint_sha256="


class SemanticPremiseReviewError(ValueError):
    """Fail-closed semantic-premise review error."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def normalize_repo_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def load_profile(repo_root: Path) -> dict[str, Any]:
    path = Path(repo_root) / PROFILE_RELATIVE
    if not path.is_file():
        raise SemanticPremiseReviewError("SEMANTIC_PREMISE_PROFILE_MISSING")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SemanticPremiseReviewError("SEMANTIC_PREMISE_PROFILE_INVALID")
    if raw.get("authority_granted") is not False:
        raise SemanticPremiseReviewError("SEMANTIC_PREMISE_AUTHORITY_MUST_BE_FALSE")
    if raw.get("new_permanent_review_role") is not False:
        raise SemanticPremiseReviewError("SEMANTIC_PREMISE_FOURTH_ROLE_FORBIDDEN")
    if raw.get("architecture_owner") != "ARCHITECTURE_CRITIC":
        raise SemanticPremiseReviewError("SEMANTIC_PREMISE_OWNER_MUST_BE_ARCHITECTURE")
    return raw


def load_packet_schema(repo_root: Path) -> dict[str, Any]:
    path = Path(repo_root) / PACKET_SCHEMA_RELATIVE
    return json.loads(path.read_text(encoding="utf-8"))


def task_requests_semantic_premise(task_text: str, *, marker: str) -> bool:
    return marker in task_text


def classify_review_profile(
    *,
    changed_paths: list[str],
    task_text: str | None = None,
    force_profile: str | None = None,
    profile: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    cfg = profile if profile is not None else load_profile(Path(repo_root or "."))
    if force_profile in {"STANDARD", "SEMANTIC_PREMISE"}:
        selected = force_profile
        reason = "FORCE_PROFILE"
        dimensions: list[str] = (
            list(cfg.get("risk_dimensions") or [])
            if selected == "SEMANTIC_PREMISE"
            else []
        )
        return {
            "profile": selected,
            "reason": reason,
            "risk_dimensions": dimensions,
            "matched_paths": [],
            "authority_granted": False,
        }

    marker = str((cfg.get("packet") or {}).get("exact_task_body_marker") or "")
    matched_paths: list[str] = []
    prefixes = [str(item) for item in cfg.get("trigger_path_prefixes") or []]
    for path in changed_paths:
        normalized = normalize_repo_path(path)
        if any(normalized.startswith(prefix) for prefix in prefixes):
            matched_paths.append(normalized)

    marker_hit = bool(
        task_text and marker and task_requests_semantic_premise(task_text, marker=marker)
    )
    if matched_paths or marker_hit:
        return {
            "profile": "SEMANTIC_PREMISE",
            "reason": "PATH_PREFIX" if matched_paths else "TASK_BODY_MARKER",
            "risk_dimensions": list(cfg.get("risk_dimensions") or []),
            "matched_paths": sorted(set(matched_paths)),
            "authority_granted": False,
        }
    return {
        "profile": "STANDARD",
        "reason": "NO_SEMANTIC_TRIGGER",
        "risk_dimensions": [],
        "matched_paths": [],
        "authority_granted": False,
    }


def map_semantic_verdict_to_architecture(verdict: str, profile_cfg: dict[str, Any]) -> str:
    mapping = (
        ((profile_cfg.get("profiles") or {}).get("SEMANTIC_PREMISE") or {}).get(
            "verdict_map"
        )
        or {}
    )
    key = str(verdict or "").strip().upper()
    mapped = mapping.get(key)
    if mapped not in {"PASS", "NOT_READY"}:
        raise SemanticPremiseReviewError("SEMANTIC_VERDICT_UNMAPPED")
    return str(mapped)


def _reject_forbidden_keys(payload: dict[str, Any], forbidden: list[str]) -> None:
    stack: list[Any] = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                if key in forbidden:
                    raise SemanticPremiseReviewError(
                        f"SEMANTIC_PACKET_FORBIDDEN_KEY:{key}"
                    )
                stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)


def _require_model_diversity(
    model_diversity: str, model_diversity_identity: str | None
) -> str | None:
    if model_diversity not in {"PROVEN", "UNPROVEN"}:
        raise SemanticPremiseReviewError("MODEL_DIVERSITY_INVALID")
    identity = (model_diversity_identity or "").strip() or None
    if model_diversity == "PROVEN":
        if identity is None:
            raise SemanticPremiseReviewError("MODEL_DIVERSITY_PROVEN_REQUIRES_IDENTITY")
        return identity
    if identity is not None:
        raise SemanticPremiseReviewError("MODEL_DIVERSITY_IDENTITY_ONLY_WHEN_PROVEN")
    return None


def build_semantic_premise_packet(
    *,
    repo_root: Path,
    task_id: str,
    task_contract_bytes: bytes,
    base: str,
    head: str,
    diff_bytes: bytes,
    semantic_claims: list[dict[str, str]],
    non_claims: list[str],
    evidence: list[dict[str, Any]],
    risk_dimensions: list[str] | None = None,
    model_diversity: str = "UNPROVEN",
    model_diversity_identity: str | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = profile if profile is not None else load_profile(repo_root)
    if not HEX40.fullmatch(base) or not HEX40.fullmatch(head):
        raise SemanticPremiseReviewError("SEMANTIC_CANDIDATE_SHA_INVALID")
    identity = _require_model_diversity(model_diversity, model_diversity_identity)
    questions = list(
        ((cfg.get("profiles") or {}).get("SEMANTIC_PREMISE") or {}).get(
            "mandatory_questions"
        )
        or []
    )
    dims = list(risk_dimensions or cfg.get("risk_dimensions") or [])
    if not semantic_claims:
        raise SemanticPremiseReviewError("SEMANTIC_CLAIMS_REQUIRED")
    # Independence fields describe the *packet information path* only.
    # They do not attest that a parent agent withheld chat from the critic.
    packet: dict[str, Any] = {
        "schema": "smial.semantic-premise-review-packet",
        "schema_version": "1.0",
        "task": {
            "task_id": task_id,
            "task_contract_sha256": _sha256_bytes(task_contract_bytes),
        },
        "candidate": {
            "base": base,
            "head": head,
            "diff_sha256": _sha256_bytes(diff_bytes),
        },
        "review": {
            "profile": "SEMANTIC_PREMISE",
            "risk_dimensions": dims,
            "architecture_owner": "ARCHITECTURE_CRITIC",
        },
        "semantic_claims": semantic_claims,
        "non_claims": list(non_claims),
        "evidence": evidence,
        "questions": questions,
        "independence": {
            "claim_scope": CLAIM_SCOPE_PACKET_PATH,
            "context_isolated": True,
            "implementation_transcript_seen": False,
            "packet_bound": True,
            "readonly": True,
            "launch_isolation": LAUNCH_ISOLATION_PROCESS,
            "model_diversity": model_diversity,
            "model_diversity_identity": identity,
        },
    }
    forbidden = list((cfg.get("packet") or {}).get("forbidden_keys") or [])
    _reject_forbidden_keys(packet, forbidden)
    fingerprint_material = {
        "task": packet["task"],
        "candidate": packet["candidate"],
        "review": packet["review"],
        "semantic_claims": packet["semantic_claims"],
        "non_claims": packet["non_claims"],
        "evidence": packet["evidence"],
    }
    packet["packet_fingerprint_sha256"] = _sha256_bytes(
        _canonical_json_bytes(fingerprint_material)
    )
    schema = load_packet_schema(repo_root)
    Draft202012Validator(schema).validate(packet)
    encoded = _canonical_json_bytes(packet)
    max_bytes = int((cfg.get("packet") or {}).get("max_bytes") or 16384)
    if len(encoded) > max_bytes:
        raise SemanticPremiseReviewError("SEMANTIC_PACKET_TOO_LARGE")
    return packet


def packet_is_stale(
    packet: dict[str, Any],
    *,
    task_contract_bytes: bytes,
    base: str,
    head: str,
    diff_bytes: bytes,
    semantic_claims: list[dict[str, str]],
    non_claims: list[str],
    evidence: list[dict[str, Any]],
    risk_dimensions: list[str],
) -> bool:
    expected = {
        "task": {
            "task_id": packet.get("task", {}).get("task_id"),
            "task_contract_sha256": _sha256_bytes(task_contract_bytes),
        },
        "candidate": {
            "base": base,
            "head": head,
            "diff_sha256": _sha256_bytes(diff_bytes),
        },
        "review": {
            "profile": "SEMANTIC_PREMISE",
            "risk_dimensions": list(risk_dimensions),
            "architecture_owner": "ARCHITECTURE_CRITIC",
        },
        "semantic_claims": semantic_claims,
        "non_claims": list(non_claims),
        "evidence": evidence,
    }
    observed = _sha256_bytes(_canonical_json_bytes(expected))
    return observed != str(packet.get("packet_fingerprint_sha256") or "")


def validate_packet_against_candidate(
    packet: dict[str, Any],
    *,
    repo_root: Path,
    task_contract_bytes: bytes,
    base: str,
    head: str,
    diff_bytes: bytes,
    semantic_claims: list[dict[str, str]],
    non_claims: list[str],
    evidence: list[dict[str, Any]],
    risk_dimensions: list[str],
) -> dict[str, Any]:
    schema = load_packet_schema(repo_root)
    Draft202012Validator(schema).validate(packet)
    independence = packet.get("independence") or {}
    if independence.get("claim_scope") != CLAIM_SCOPE_PACKET_PATH:
        raise SemanticPremiseReviewError("SEMANTIC_PACKET_CLAIM_SCOPE_INVALID")
    if independence.get("launch_isolation") != LAUNCH_ISOLATION_PROCESS:
        raise SemanticPremiseReviewError("SEMANTIC_PACKET_LAUNCH_ISOLATION_INVALID")
    _require_model_diversity(
        str(independence.get("model_diversity") or ""),
        independence.get("model_diversity_identity"),
    )
    if packet_is_stale(
        packet,
        task_contract_bytes=task_contract_bytes,
        base=base,
        head=head,
        diff_bytes=diff_bytes,
        semantic_claims=semantic_claims,
        non_claims=non_claims,
        evidence=evidence,
        risk_dimensions=risk_dimensions,
    ):
        raise SemanticPremiseReviewError("SEMANTIC_PACKET_STALE")
    return {
        "ok": True,
        "profile": "SEMANTIC_PREMISE",
        "packet_fingerprint_sha256": packet["packet_fingerprint_sha256"],
        "independence_claim_scope": CLAIM_SCOPE_PACKET_PATH,
        "launch_isolation": LAUNCH_ISOLATION_PROCESS,
        "model_diversity": independence.get("model_diversity"),
    }


def validate_launch_inputs(
    *,
    classification: dict[str, Any],
    packet: dict[str, Any] | None,
    repo_root: Path,
    task_contract_bytes: bytes | None = None,
    base: str | None = None,
    head: str | None = None,
    diff_bytes: bytes | None = None,
    semantic_claims: list[dict[str, str]] | None = None,
    non_claims: list[str] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    risk_dimensions: list[str] | None = None,
) -> dict[str, Any]:
    """Fail-closed gate for delivery-review before architecture critic launch."""

    profile = str(classification.get("profile") or "")
    if profile == "STANDARD":
        if packet is not None:
            raise SemanticPremiseReviewError("STANDARD_PROFILE_MUST_OMIT_PACKET")
        return {
            "ok": True,
            "profile": "STANDARD",
            "packet_required": False,
            "authority_granted": False,
        }
    if profile != "SEMANTIC_PREMISE":
        raise SemanticPremiseReviewError("REVIEW_PROFILE_UNKNOWN")
    if packet is None:
        raise SemanticPremiseReviewError("SEMANTIC_PACKET_REQUIRED")
    if (
        task_contract_bytes is None
        or base is None
        or head is None
        or diff_bytes is None
        or semantic_claims is None
        or non_claims is None
        or evidence is None
        or risk_dimensions is None
    ):
        raise SemanticPremiseReviewError("SEMANTIC_PACKET_BINDING_INCOMPLETE")
    validated = validate_packet_against_candidate(
        packet,
        repo_root=repo_root,
        task_contract_bytes=task_contract_bytes,
        base=base,
        head=head,
        diff_bytes=diff_bytes,
        semantic_claims=semantic_claims,
        non_claims=non_claims,
        evidence=evidence,
        risk_dimensions=risk_dimensions,
    )
    validated["packet_required"] = True
    validated["authority_granted"] = False
    return validated


def require_packet_fingerprint_in_findings(
    findings_text: str, packet: dict[str, Any]
) -> None:
    """Architecture findings must bind the exact frozen packet fingerprint."""

    expected = (
        f"{PACKET_FINGERPRINT_FINDING_PREFIX}"
        f"{packet.get('packet_fingerprint_sha256')}"
    )
    if expected not in findings_text:
        raise SemanticPremiseReviewError("ARCHITECTURE_FINDINGS_MISSING_PACKET_FINGERPRINT")


def evaluate_fixture_premise(
    *,
    claims: list[dict[str, str]],
    non_claims: list[str],
) -> dict[str, Any]:
    """Deterministic smoke evaluator for synthetic fixtures (not an LLM)."""

    claim_blob = " ".join(
        f"{item.get('claim', '')} {item.get('scope', '')}" for item in claims
    ).casefold()
    non_blob = " ".join(non_claims).casefold()
    findings: list[str] = []
    if "reopen_forbidden" in claim_blob and "global" in claim_blob:
        if "broader family remains" not in non_blob and "family remains unknown" not in non_blob:
            findings.append("SCOPE_AUTHORITY_WIDENING:global_reopen_forbidden")
    if "unknown" in claim_blob and (
        "negative evidence" in claim_blob
        or "negative scientific" in claim_blob
        or " as negative" in claim_blob
        or "count as false" in claim_blob
        or "count as zero" in claim_blob
    ):
        findings.append("UNKNOWN_AS_NEGATIVE_EVIDENCE")
    if findings:
        return {
            "semantic_verdict": "FAIL",
            "architecture_verdict": "NOT_READY",
            "findings": findings,
        }
    return {
        "semantic_verdict": "PASS",
        "architecture_verdict": "PASS",
        "findings": ["BOUNDED_CLAIM_WITH_EXPLICIT_NON_CLAIMS"],
    }
