"""Durable HFIC post-NO_WORTHY selection-robustness gate.

Composes frozen Stage-1 CAP-HFIC-CENSORING-IGNORABILITY-DIAGNOSTIC-001 with
one Block-A L2-logistic OOF-AUC falsifier and a pure Forge router. Does not
certify MAR, ignorability, identification, MNAR, alpha, or a causal mechanism.
Never materializes Y-point typed values.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.factory.git_write_fence import (
    GitFenceError,
    repository_git_snapshot,
)
from solana_alpha_lab.factory.hfic_censoring_ignorability_diagnostic import (
    CANONICAL_DATA_ROOT_OR_EXPLICIT_PATHS_REQUIRED,
    CANONICAL_INPUT_MODE,
    CANONICAL_MODE_EXPLICIT_PATH_CONFLICT,
    CensoringDiagnosticError,
    EXPLICIT_PATH_INPUT_MODE,
    INCONCLUSIVE as STAGE1_INCONCLUSIVE,
    SCOPE_CANONICAL,
    SCOPE_NONCANONICAL,
    SHIFT_DETECTED,
    SHIFT_NOT_DETECTED,
    SPEC_RELATIVE as STAGE1_SPEC_RELATIVE,
    Y_POINT_READ,
    _as_float,
    _as_text,
    _group_label,
    _load_block_a_typed,
    _load_census,
    _load_x300_keys,
    _log1p,
    _retain_unique_mint_field,
    bind_canonical_censoring_inputs,
    load_diagnostic_spec,
    run_censoring_ignorability_diagnostic,
)
from solana_alpha_lab.factory.run_passport import canonical_sha256
from solana_alpha_lab.factory.tokens_v2_typed_projection import (
    STATE_OBSERVED,
    TOKENS_V2_FIELD_KINDS,
)

CAP_HFIC_SELECTION_ROBUSTNESS_GATE = "CAP-HFIC-SELECTION-ROBUSTNESS-GATE-001"
SPEC_RELATIVE = "configs/hfic_selection_robustness_gate_v1.yaml"
FROZEN_SPEC_SHA256 = "db4cdd40edf92e05a7a9ec6cabc181783c8729c3ac7079e80373797be0d0ac0d"
RECEIPT_SCHEMA = "smial.hfic-selection-robustness-gate-receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
STAGE2_DETECTED = "SELECTION_PREDICTABILITY_DETECTED"
STAGE2_NOT_DETECTED = "SELECTION_PREDICTABILITY_NOT_DETECTED"
STAGE2_INCONCLUSIVE = "SELECTION_PREDICTABILITY_INCONCLUSIVE"
STAGE2_SKIPPED = "SKIPPED"
STAGE2_RAN = "RAN"
BLOCK_FORGE_SELECTION_RISK = "BLOCK_FORGE_SELECTION_RISK"
BLOCK_FORGE_EVIDENCE_GAP = "BLOCK_FORGE_EVIDENCE_GAP"
FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT = "FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT"
GATE_ARTIFACT_RELATIVE = (
    "research/artifacts/hfic_selection_robustness_gate/latest.json"
)
KNOWN_STAGE1_TERMINALS = frozenset(
    {SHIFT_DETECTED, SHIFT_NOT_DETECTED, STAGE1_INCONCLUSIVE}
)
BLOCK_DECISIONS = frozenset({BLOCK_FORGE_SELECTION_RISK, BLOCK_FORGE_EVIDENCE_GAP})
LEAK_PREFIXES = ("FIELD-STATS5M-", "FIELD-R0-", "FIELD-QUOTE-")
NON_CLAIMS = (
    "NO_MAR",
    "NO_IGNORABILITY",
    "NO_IDENTIFIABILITY",
    "NO_RANDOM_SAMPLE_CERTIFICATION",
    "NO_MNAR",
    "NO_ALPHA",
    "NO_CAUSAL_MECHANISM",
    "NO_MARKET_HYPOTHESIS_VALIDITY",
    "NO_Y_POINT_READ",
    "NO_CANONICAL_ACTIVE_RDP_RUN_THIS_ATOM",
)


class SelectionRobustnessGateError(ValueError):
    """Fail-closed selection-robustness protocol error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _unsafe(relative: str) -> bool:
    return Path(relative).is_absolute() or ".." in Path(relative).parts


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_spec_relative(relative: str) -> str:
    return Path(str(relative).replace("\\", "/")).as_posix()


def route_selection_gate(
    stage1_terminal: str | None,
    *,
    stage2_terminal: str | None = None,
    stage2_status: str | None = None,
) -> dict[str, str]:
    """Pure deterministic Forge router. No I/O."""

    scientific = str(stage1_terminal or "")
    if scientific == SHIFT_DETECTED:
        return {
            "stage2_status": STAGE2_SKIPPED,
            "router_decision": BLOCK_FORGE_SELECTION_RISK,
        }
    if scientific == STAGE1_INCONCLUSIVE or scientific not in KNOWN_STAGE1_TERMINALS:
        return {
            "stage2_status": STAGE2_SKIPPED,
            "router_decision": BLOCK_FORGE_EVIDENCE_GAP,
        }
    if stage2_status == STAGE2_SKIPPED:
        return {
            "stage2_status": STAGE2_SKIPPED,
            "router_decision": BLOCK_FORGE_EVIDENCE_GAP,
        }
    if stage2_terminal == STAGE2_DETECTED:
        return {
            "stage2_status": STAGE2_RAN,
            "router_decision": BLOCK_FORGE_SELECTION_RISK,
        }
    if stage2_terminal == STAGE2_INCONCLUSIVE:
        return {
            "stage2_status": STAGE2_RAN,
            "router_decision": BLOCK_FORGE_EVIDENCE_GAP,
        }
    if stage2_terminal == STAGE2_NOT_DETECTED:
        return {
            "stage2_status": STAGE2_RAN,
            "router_decision": FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
        }
    return {
        "stage2_status": STAGE2_SKIPPED,
        "router_decision": BLOCK_FORGE_EVIDENCE_GAP,
    }


def apply_selection_gate_to_preflight(
    action: str,
    gate_receipt: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Smallest ordinary-Forge consumption seam. Resume paths stay unchanged."""

    if action != "START_NEW_SESSION" or not isinstance(gate_receipt, Mapping):
        return {"applicable": False, "action": action, "terminal": None}
    decision = str(gate_receipt.get("router_decision") or "")
    if decision in BLOCK_DECISIONS:
        return {
            "applicable": True,
            "action": "STOP",
            "terminal": decision,
            "router_decision": decision,
            "gate_receipt_sha256": str(gate_receipt.get("receipt_sha256") or ""),
        }
    if decision == FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT:
        return {
            "applicable": True,
            "action": action,
            "terminal": None,
            "router_decision": decision,
            "gate_receipt_sha256": str(gate_receipt.get("receipt_sha256") or ""),
            "caveat": True,
        }
    return {"applicable": False, "action": action, "terminal": None}


def load_gate_spec(root: Path, relative: str = SPEC_RELATIVE) -> dict[str, Any]:
    if _unsafe(relative):
        raise SelectionRobustnessGateError("GATE_SPEC_PATH_UNSAFE")
    path = root / relative
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SelectionRobustnessGateError("GATE_SPEC_MISSING") from exc
    if not isinstance(loaded, dict):
        raise SelectionRobustnessGateError("GATE_SPEC_INVALID")
    allowed = str(loaded.get("allowed_point_id") or "")
    y_prefix = str(loaded.get("y_point_prefix") or "Y")
    if not allowed or allowed.startswith(y_prefix):
        raise SelectionRobustnessGateError(Y_POINT_READ)
    block_a = loaded.get("block_a_omnibus")
    if not isinstance(block_a, list) or not block_a:
        raise SelectionRobustnessGateError("GATE_SPEC_INVALID")
    excluded = loaded.get("excluded_fields")
    if not isinstance(excluded, list) or not excluded:
        raise SelectionRobustnessGateError("GATE_SPEC_INVALID")
    excluded_ids = {str(item) for item in excluded}
    field_ids: list[str] = []
    for item in block_a:
        if not isinstance(item, Mapping):
            raise SelectionRobustnessGateError("GATE_SPEC_INVALID")
        field_id = str(item.get("field_id") or "")
        value_kind = str(item.get("value_kind") or "")
        role = str(item.get("role") or "")
        if not field_id.startswith("FIELD-") or not value_kind or not role:
            raise SelectionRobustnessGateError("GATE_SPEC_INVALID")
        if field_id in excluded_ids or field_id.startswith(LEAK_PREFIXES):
            raise SelectionRobustnessGateError("FEATURE_UNIVERSE_LEAK")
        if field_id.startswith(y_prefix) or value_kind.startswith(y_prefix):
            raise SelectionRobustnessGateError(Y_POINT_READ)
        registry_kind = TOKENS_V2_FIELD_KINDS.get(field_id)
        if registry_kind != value_kind:
            raise SelectionRobustnessGateError("FIELD_REGISTRY_MISMATCH")
        field_ids.append(field_id)
    if len(field_ids) != len(set(field_ids)):
        raise SelectionRobustnessGateError("GATE_SPEC_INVALID")
    try:
        lam = float(loaded.get("l2_lambda"))
        auc_floor = float(loaded.get("oof_auc_threshold"))
        p_floor = float(loaded.get("permutation_p_threshold"))
        folds = int(loaded.get("cv_folds"))
        perm_n = int(loaded.get("permutation_count"))
    except (TypeError, ValueError) as exc:
        raise SelectionRobustnessGateError("GATE_SPEC_INVALID") from exc
    if lam != 1.0 or auc_floor != 0.57 or p_floor != 0.05:
        raise SelectionRobustnessGateError("FROZEN_THRESHOLD_DRIFT")
    if folds != 5 or perm_n != 999:
        raise SelectionRobustnessGateError("FROZEN_THRESHOLD_DRIFT")
    if str(loaded.get("cv_seed") or "") != "A17C9E02":
        raise SelectionRobustnessGateError("FROZEN_THRESHOLD_DRIFT")
    if str(loaded.get("permutation_seed") or "") != "A17C9E02":
        raise SelectionRobustnessGateError("FROZEN_THRESHOLD_DRIFT")
    return loaded


def _require_frozen_gate_spec(root: Path, spec_relative: str) -> dict[str, Any]:
    if _canonical_spec_relative(spec_relative) != SPEC_RELATIVE:
        raise SelectionRobustnessGateError("FROZEN_SPEC_PATH_REQUIRED")
    path = root / SPEC_RELATIVE
    if not path.is_file() or path.is_symlink():
        raise SelectionRobustnessGateError("GATE_SPEC_MISSING")
    if _sha256_file(path) != FROZEN_SPEC_SHA256:
        raise SelectionRobustnessGateError("FROZEN_SPEC_HASH_MISMATCH")
    spec = load_gate_spec(root, SPEC_RELATIVE)
    stage1 = load_diagnostic_spec(root, STAGE1_SPEC_RELATIVE)
    gate_ids = [str(item["field_id"]) for item in spec["block_a_omnibus"]]
    stage1_ids = [str(item["field_id"]) for item in stage1["block_a_omnibus"]]
    if gate_ids != stage1_ids:
        raise SelectionRobustnessGateError("FEATURE_UNIVERSE_MISMATCH")
    for left, right in zip(spec["block_a_omnibus"], stage1["block_a_omnibus"], strict=True):
        if (
            str(left.get("feature_id")) != str(right.get("feature_id"))
            or str(left.get("value_kind")) != str(right.get("value_kind"))
            or str(left.get("transform")) != str(right.get("transform"))
            or str(left.get("role")) != str(right.get("role"))
        ):
            raise SelectionRobustnessGateError("FEATURE_UNIVERSE_MISMATCH")
    return spec


def _seed_int(seed: str) -> int:
    try:
        return int(str(seed), 16)
    except ValueError as exc:
        raise SelectionRobustnessGateError("PERMUTATION_SEED_INVALID") from exc


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        exp_neg = math.exp(-value)
        return 1.0 / (1.0 + exp_neg)
    exp_pos = math.exp(value)
    return exp_pos / (1.0 + exp_pos)


def _solve_linear(matrix: Sequence[Sequence[float]], rhs: Sequence[float]) -> list[float] | None:
    size = len(rhs)
    if size == 0 or any(len(row) != size for row in matrix):
        return None
    work = [list(row) + [rhs[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(work[row][column]))
        if abs(work[pivot][column]) < 1e-14:
            return None
        work[column], work[pivot] = work[pivot], work[column]
        divisor = work[column][column]
        for index in range(column, size + 1):
            work[column][index] /= divisor
        for row in range(size):
            if row == column:
                continue
            factor = work[row][column]
            if factor == 0.0:
                continue
            for index in range(column, size + 1):
                work[row][index] -= factor * work[column][index]
    return [work[index][size] for index in range(size)]


def fit_l2_logistic(
    design: Sequence[Sequence[float]],
    labels: Sequence[int],
    *,
    l2_lambda: float,
    max_iter: int = 25,
    tol: float = 1e-8,
) -> list[float] | None:
    if not design or len(design) != len(labels):
        return None
    width = len(design[0])
    if width < 1 or any(len(row) != width for row in design):
        return None
    weights = [0.0] * width
    for _ in range(max_iter):
        grad = [0.0] * width
        hessian = [[0.0] * width for _ in range(width)]
        for row, label in zip(design, labels, strict=True):
            eta = sum(weight * value for weight, value in zip(weights, row, strict=True))
            prob = _sigmoid(eta)
            resid = prob - float(label)
            mass = prob * (1.0 - prob)
            if mass < 1e-12:
                mass = 1e-12
            for col in range(width):
                grad[col] += resid * row[col]
                scale = mass * row[col]
                hessian_row = hessian[col]
                for inner in range(width):
                    hessian_row[inner] += scale * row[inner]
        for col in range(1, width):
            grad[col] += l2_lambda * weights[col]
            hessian[col][col] += l2_lambda
        delta = _solve_linear(hessian, grad)
        if delta is None:
            return None
        max_step = 0.0
        for col in range(width):
            weights[col] -= delta[col]
            max_step = max(max_step, abs(delta[col]))
        if max_step < tol:
            return weights
    return weights


def predict_proba(design: Sequence[Sequence[float]], weights: Sequence[float]) -> list[float]:
    return [
        _sigmoid(sum(weight * value for weight, value in zip(weights, row, strict=True)))
        for row in design
    ]


def roc_auc(labels: Sequence[int], scores: Sequence[float]) -> float | None:
    if len(labels) != len(scores) or len(labels) < 2:
        return None
    positives = sum(1 for label in labels if label == 1)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return None
    order = sorted(range(len(scores)), key=lambda index: scores[index])
    ranks = [0.0] * len(scores)
    index = 0
    while index < len(order):
        start = index
        value = scores[order[index]]
        while index < len(order) and scores[order[index]] == value:
            index += 1
        average = (start + index + 1) / 2.0
        for inner in range(start, index):
            ranks[order[inner]] = average
    rank_sum = sum(ranks[i] for i, label in enumerate(labels) if label == 1)
    return (rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def stratified_kfold(
    labels: Sequence[int],
    *,
    folds: int,
    rng: random.Random,
) -> list[list[int]] | None:
    buckets: dict[int, list[int]] = {0: [], 1: []}
    for index, label in enumerate(labels):
        if label not in buckets:
            return None
        buckets[label].append(index)
    if len(buckets[0]) < folds or len(buckets[1]) < folds:
        return None
    for label in (0, 1):
        rng.shuffle(buckets[label])
    assigned: list[list[int]] = [[] for _ in range(folds)]
    for label in (0, 1):
        for offset, index in enumerate(buckets[label]):
            assigned[offset % folds].append(index)
    for fold in assigned:
        present = {labels[index] for index in fold}
        if present != {0, 1}:
            return None
    return assigned


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _mean_std(values: Sequence[float]) -> tuple[float, float] | None:
    if not values:
        return None
    mean = sum(values) / len(values)
    if len(values) == 1:
        return mean, 1.0
    var = sum((item - mean) ** 2 for item in values) / (len(values) - 1)
    std = math.sqrt(var) if var > 0.0 else 1.0
    return mean, std


def _fit_preprocessor(
    members: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
) -> dict[str, Any] | None:
    min_joint_n = int(spec["rare_level_min_joint_n"])
    other_label = str(spec["rare_level_label"])
    continuous: dict[str, dict[str, float]] = {}
    for feature in spec["block_a_omnibus"]:
        if str(feature.get("role")) != "continuous":
            continue
        feature_id = str(feature["feature_id"])
        observed = [
            float(member["features"][feature_id])
            for member in members
            if member["observed_flags"].get(feature_id)
            and feature_id in member["features"]
        ]
        median = _median(observed)
        stats = _mean_std(observed)
        if median is None or stats is None:
            return None
        mean, std = stats
        continuous[feature_id] = {"median": median, "mean": mean, "std": std}
    categorical_keep: dict[str, set[str]] = {}
    dummy_levels: dict[str, list[str]] = {}
    for feature in spec["block_a_omnibus"]:
        if str(feature.get("role")) != "categorical":
            continue
        feature_id = str(feature["feature_id"])
        counts: dict[str, int] = {}
        for member in members:
            if not member["observed_flags"].get(feature_id):
                continue
            value = member["features"].get(feature_id)
            if value is None:
                continue
            text = str(value)
            counts[text] = counts.get(text, 0) + 1
        keep = {level for level, count in counts.items() if count >= min_joint_n}
        categorical_keep[feature_id] = keep
        dummy_levels[feature_id] = sorted(level for level in keep if level != other_label)
    return {
        "continuous": continuous,
        "categorical_keep": categorical_keep,
        "dummy_levels": dummy_levels,
        "other_label": other_label,
    }


def _transform_members(
    members: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
    preprocessor: Mapping[str, Any],
) -> list[list[float]]:
    other_label = str(preprocessor["other_label"])
    rows: list[list[float]] = []
    for member in members:
        row = [1.0]
        for feature in spec["block_a_omnibus"]:
            feature_id = str(feature["feature_id"])
            if str(feature.get("role")) == "continuous":
                stats = preprocessor["continuous"][feature_id]
                missing = 0.0 if member["observed_flags"].get(feature_id) else 1.0
                raw = member["features"].get(feature_id)
                value = float(raw) if raw is not None and missing == 0.0 else stats["median"]
                row.append(missing)
                row.append((value - stats["mean"]) / stats["std"])
                continue
            raw = member["features"].get(feature_id)
            mapped = other_label
            if member["observed_flags"].get(feature_id) and raw is not None:
                text = str(raw)
                keep = preprocessor["categorical_keep"][feature_id]
                mapped = text if text in keep else other_label
            for level in preprocessor["dummy_levels"][feature_id]:
                row.append(1.0 if mapped == level else 0.0)
        rows.append(row)
    return rows


def oof_logistic_auc(
    members: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
    *,
    rng: random.Random,
) -> tuple[float | None, list[float] | None, list[str]]:
    labels = [1 if member["group"] == "observed" else 0 for member in members]
    folds = stratified_kfold(labels, folds=int(spec["cv_folds"]), rng=rng)
    if folds is None:
        return None, None, ["STRATIFIED_FOLDS_INFEASIBLE"]
    oof = [0.0] * len(members)
    lam = float(spec["l2_lambda"])
    for fold_index, test_idx in enumerate(folds):
        train_idx = [
            index
            for other, fold in enumerate(folds)
            if other != fold_index
            for index in fold
        ]
        train = [members[index] for index in train_idx]
        test = [members[index] for index in test_idx]
        preprocessor = _fit_preprocessor(train, spec)
        if preprocessor is None:
            return None, None, ["PREPROCESS_UNDEFINED"]
        train_x = _transform_members(train, spec, preprocessor)
        test_x = _transform_members(test, spec, preprocessor)
        train_y = [labels[index] for index in train_idx]
        weights = fit_l2_logistic(train_x, train_y, l2_lambda=lam)
        if weights is None:
            return None, None, ["LOGISTIC_NONCONVERGENCE"]
        preds = predict_proba(test_x, weights)
        for local, index in enumerate(test_idx):
            oof[index] = preds[local]
    auc = roc_auc(labels, oof)
    if auc is None:
        return None, None, ["OOF_AUC_UNDEFINED"]
    return auc, oof, []


def _load_comparable_members(
    *,
    spec: Mapping[str, Any],
    census_path: Path,
    observations_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, int], int, list[str]]:
    allowed_point_id = str(spec["allowed_point_id"])
    y_prefix = str(spec["y_point_prefix"])
    block_a = list(spec["block_a_omnibus"])
    field_ids = [str(item["field_id"]) for item in block_a]
    for field_id in field_ids:
        if field_id.startswith(LEAK_PREFIXES) or field_id.startswith(y_prefix):
            raise SelectionRobustnessGateError("FEATURE_UNIVERSE_LEAK")
    census_rows = _load_census(census_path)
    obs_rows, y_unread = _load_x300_keys(
        observations_path,
        allowed_point_id=allowed_point_id,
        y_prefix=y_prefix,
    )
    unique_obs, duplicate_observations = _retain_unique_mint_field(obs_rows)
    typed_rows = _load_block_a_typed(
        observations_path,
        allowed_point_id=allowed_point_id,
        y_prefix=y_prefix,
        field_ids=field_ids,
    )
    unique_typed, duplicate_typed = _retain_unique_mint_field(typed_rows)
    if duplicate_observations or duplicate_typed:
        return [], {}, y_unread, ["DUPLICATE_X300_OBSERVATION"]
    obs_by_mint: dict[str, dict[str, dict[str, Any]]] = {}
    for row in unique_obs:
        mint = str(row.get("mint") or "")
        field_id = str(row.get("field_id") or "")
        if mint and field_id:
            obs_by_mint.setdefault(mint, {})[field_id] = row
    typed_by_mint: dict[str, dict[str, dict[str, Any]]] = {}
    for row in unique_typed:
        mint = str(row.get("mint") or "")
        field_id = str(row.get("field_id") or "")
        if mint and field_id:
            typed_by_mint.setdefault(mint, {})[field_id] = row
    x300_mints = {
        mint
        for row in obs_rows
        if (mint := str(row.get("mint") or "")) and str(row.get("field_id") or "")
    }
    diagnostic_rows = [
        row for row in census_rows if str(row.get("mint") or "") in x300_mints
    ]
    mint_row_n: dict[str, int] = {}
    for row in diagnostic_rows:
        mint = str(row.get("mint") or "")
        if mint:
            mint_row_n[mint] = mint_row_n.get(mint, 0) + 1
    counts = {
        "x_eligible_observed": 0,
        "x_eligible_censored_late": 0,
        "other_in_scope": 0,
    }
    members: list[dict[str, Any]] = []
    reasons: list[str] = []
    comparable: set[str] = set()
    value_kind_mismatch = False
    for row in diagnostic_rows:
        mint = str(row.get("mint") or "")
        group = _group_label(row)
        candidate = str(row.get("candidate_state") or "")
        denom = str(row.get("denominator_state") or "")
        if candidate == "X_ELIGIBLE" and denom == "observed":
            counts["x_eligible_observed"] += 1
        elif candidate == "X_ELIGIBLE" and denom == "censored_late":
            counts["x_eligible_censored_late"] += 1
        elif candidate not in {"ADMITTED", "X_POPULATION_INELIGIBLE"}:
            counts["other_in_scope"] += 1
        if group is None or not mint:
            continue
        if mint_row_n.get(mint, 0) > 1 or mint in comparable:
            reasons.append("DUPLICATE_COMPARABLE_MINT")
            continue
        comparable.add(mint)
        mint_obs = obs_by_mint.get(mint, {})
        mint_typed = typed_by_mint.get(mint, {})
        features: dict[str, float | str] = {}
        observed_flags: dict[str, bool] = {}
        for feature in block_a:
            feature_id = str(feature["feature_id"])
            field_id = str(feature["field_id"])
            expected_kind = str(feature.get("value_kind") or "")
            payload = mint_obs.get(field_id)
            typed_payload = mint_typed.get(field_id)
            present = (
                payload is not None
                and typed_payload is not None
                and str(payload.get("state") or "") == STATE_OBSERVED
                and str(typed_payload.get("state") or "") == STATE_OBSERVED
            )
            observed_flags[feature_id] = present
            if not present:
                continue
            observed_kind = str(typed_payload.get("value_kind") or "")
            if observed_kind != expected_kind:
                value_kind_mismatch = True
                observed_flags[feature_id] = False
                continue
            typed = typed_payload.get("typed_value")
            if str(feature.get("role")) == "continuous":
                number = _as_float(typed)
                if number is None:
                    observed_flags[feature_id] = False
                    continue
                transform = str(feature.get("transform") or "")
                features[feature_id] = _log1p(number) if transform == "log1p" else number
            else:
                text = _as_text(typed)
                if text is None:
                    observed_flags[feature_id] = False
                    continue
                features[feature_id] = text
        members.append(
            {
                "mint": mint,
                "group": group,
                "features": features,
                "observed_flags": observed_flags,
            }
        )
    if value_kind_mismatch:
        reasons.append("VALUE_KIND_MISMATCH")
    if counts["other_in_scope"] > 0:
        reasons.append("UNKNOWN_CENSUS_STATE")
    members.sort(key=lambda item: str(item["mint"]))
    return members, counts, y_unread, reasons


def _missingness_rows(
    members: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for feature in spec["block_a_omnibus"]:
        feature_id = str(feature["feature_id"])
        missing_observed = 0
        missing_censored = 0
        n_observed = 0
        n_censored = 0
        for member in members:
            present = bool(member["observed_flags"].get(feature_id))
            if member["group"] == "observed":
                n_observed += 1
                if not present:
                    missing_observed += 1
            else:
                n_censored += 1
                if not present:
                    missing_censored += 1
        rows.append(
            {
                "feature_id": feature_id,
                "field_id": str(feature["field_id"]),
                "n_observed": n_observed,
                "n_censored_late": n_censored,
                "missing_observed": missing_observed,
                "missing_censored_late": missing_censored,
            }
        )
    return rows


def _git_head(root: Path) -> str | None:
    try:
        snapshot = repository_git_snapshot(root)
    except (GitFenceError, OSError, ValueError):
        return None
    head = str(getattr(snapshot, "head_sha", "") or "")
    if len(head) != 40:
        return None
    return head.lower()


def _stage1_scientific(terminal: object) -> str:
    text = str(terminal or "")
    if "|" in text:
        return text.split("|", 1)[0]
    return text


def _run_stage2(
    members: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    if len(members) < int(spec["cv_folds"]) * 2:
        reasons.append("STRATIFIED_FOLDS_INFEASIBLE")
    labels = [1 if member["group"] == "observed" else 0 for member in members]
    if sum(labels) < int(spec["cv_folds"]) or (len(labels) - sum(labels)) < int(
        spec["cv_folds"]
    ):
        reasons.append("STRATIFIED_FOLDS_INFEASIBLE")
    if reasons:
        return {
            "terminal": STAGE2_INCONCLUSIVE,
            "inconclusive_reasons": list(dict.fromkeys(reasons)),
            "oof_roc_auc": None,
            "permutation_hits": None,
            "permutation_p": None,
            "oof_prediction_sha256": None,
        }
    observed_rng = random.Random(_seed_int(str(spec["cv_seed"])))
    auc, oof, auc_reasons = oof_logistic_auc(members, spec, rng=observed_rng)
    if auc is None or oof is None:
        return {
            "terminal": STAGE2_INCONCLUSIVE,
            "inconclusive_reasons": auc_reasons or ["CV_CLOSURE_FAILURE"],
            "oof_roc_auc": None,
            "permutation_hits": None,
            "permutation_p": None,
            "oof_prediction_sha256": None,
        }
    perm_rng = random.Random(_seed_int(str(spec["permutation_seed"])))
    perm_n = int(spec["permutation_count"])
    hits = 0
    base_members = [dict(member) for member in members]
    groups = [str(member["group"]) for member in base_members]
    for _ in range(perm_n):
        shuffled = groups[:]
        perm_rng.shuffle(shuffled)
        relabeled = []
        for member, group in zip(base_members, shuffled, strict=True):
            cloned = dict(member)
            cloned["group"] = group
            relabeled.append(cloned)
        fold_rng = random.Random(perm_rng.randrange(2**63))
        perm_auc, _, perm_reasons = oof_logistic_auc(relabeled, spec, rng=fold_rng)
        if perm_auc is None:
            return {
                "terminal": STAGE2_INCONCLUSIVE,
                "inconclusive_reasons": perm_reasons or ["PERMUTATION_CLOSURE_FAILURE"],
                "oof_roc_auc": auc,
                "permutation_hits": None,
                "permutation_p": None,
                "oof_prediction_sha256": canonical_sha256({"oof_scores": oof}),
            }
        if perm_auc >= auc:
            hits += 1
    p_value = (1 + hits) / (1 + perm_n)
    auc_floor = float(spec["oof_auc_threshold"])
    p_floor = float(spec["permutation_p_threshold"])
    if auc >= auc_floor and p_value <= p_floor:
        terminal = STAGE2_DETECTED
    else:
        terminal = STAGE2_NOT_DETECTED
    return {
        "terminal": terminal,
        "inconclusive_reasons": [],
        "oof_roc_auc": auc,
        "permutation_hits": hits,
        "permutation_p": p_value,
        "oof_prediction_sha256": canonical_sha256({"oof_scores": oof}),
    }


def _compose_receipt(
    *,
    spec: Mapping[str, Any],
    stage1: Mapping[str, Any] | None,
    stage1_terminal: str,
    stage1_error: str | None,
    stage2_status: str,
    stage2: Mapping[str, Any] | None,
    input_mode: str,
    population_scope: str,
    git_head: str | None,
    block_a_field_ids: Sequence[str],
    counts: Mapping[str, Any],
    missingness: Sequence[Mapping[str, Any]],
    y_unread: int,
    census_sha256: str | None,
    observations_sha256: str | None,
    extra_reasons: Sequence[str],
) -> dict[str, Any]:
    routed = route_selection_gate(
        stage1_terminal,
        stage2_terminal=None if stage2 is None else str(stage2.get("terminal") or ""),
        stage2_status=stage2_status,
    )
    stage2_terminal = None if stage2 is None else stage2.get("terminal")
    if stage2_status == STAGE2_RAN and stage2 is not None:
        routed = route_selection_gate(
            stage1_terminal,
            stage2_terminal=str(stage2.get("terminal") or ""),
            stage2_status=STAGE2_RAN,
        )
        stage2_terminal = stage2.get("terminal")
    reasons = list(extra_reasons)
    if stage2 is not None:
        reasons.extend(str(item) for item in (stage2.get("inconclusive_reasons") or []))
    corpus = spec.get("canonical_corpus") if isinstance(spec.get("canonical_corpus"), Mapping) else {}
    canonical = population_scope == SCOPE_CANONICAL
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "capability_id": CAP_HFIC_SELECTION_ROBUSTNESS_GATE,
        "git_head": git_head,
        "input_mode": input_mode,
        "terminal_population_scope": population_scope,
        "corpus_id": corpus.get("dataset_id") if canonical else None,
        "cohort_id": corpus.get("cohort_id") if canonical else None,
        "release_id": corpus.get("release_id") if canonical else None,
        "census_sha256": census_sha256 if canonical else census_sha256,
        "observations_sha256": observations_sha256,
        "scientific_context_session": (
            corpus.get("scientific_context_session") if canonical else None
        ),
        "stage1_capability_id": spec.get("stage1_capability_id"),
        "stage1_terminal": stage1_terminal,
        "stage1_receipt_sha256": None if stage1 is None else stage1.get("receipt_sha256"),
        "stage1_error": stage1_error,
        "stage2_status": routed["stage2_status"],
        "stage2_terminal": stage2_terminal,
        "block_a_field_ids": list(block_a_field_ids),
        "exclusion_policy_id": spec.get("exclusion_policy_id"),
        "exclusion_policy_version": spec.get("exclusion_policy_version"),
        "excluded_fields": list(spec.get("excluded_fields") or []),
        "counts": dict(counts),
        "missingness": [dict(item) for item in missingness],
        "cv_folds": int(spec["cv_folds"]),
        "cv_seed": str(spec["cv_seed"]),
        "preprocessing": dict(spec.get("preprocessing") or {}),
        "logistic": {"model": "l2_logistic", "l2_lambda": float(spec["l2_lambda"])},
        "oof_roc_auc": None if stage2 is None else stage2.get("oof_roc_auc"),
        "oof_auc_threshold": float(spec["oof_auc_threshold"]),
        "permutation_count": int(spec["permutation_count"]),
        "permutation_seed": str(spec["permutation_seed"]),
        "permutation_hits": None if stage2 is None else stage2.get("permutation_hits"),
        "permutation_p": None if stage2 is None else stage2.get("permutation_p"),
        "permutation_p_threshold": float(spec["permutation_p_threshold"]),
        "oof_prediction_sha256": (
            None if stage2 is None else stage2.get("oof_prediction_sha256")
        ),
        "inconclusive_reasons": list(dict.fromkeys(reasons)),
        "router_decision": routed["router_decision"],
        "non_claims": list(NON_CLAIMS),
        "y_point_rows_present_unread": y_unread,
        "provider_requests": 0,
        "credential_reads": 0,
        "spec_file_sha256": FROZEN_SPEC_SHA256,
        "spec_sha256": canonical_sha256(spec),
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def persist_gate_receipt(data_root: Path, receipt: Mapping[str, Any]) -> Path:
    path = Path(data_root) / GATE_ARTIFACT_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(dict(receipt), ensure_ascii=False, sort_keys=True, indent=2)
    path.write_text(encoded + "\n", encoding="utf-8")
    return path


def load_applicable_gate_receipt(data_root: Path) -> dict[str, Any] | None:
    path = Path(data_root) / GATE_ARTIFACT_RELATIVE
    if not path.is_file() or path.is_symlink():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, dict):
        return None
    if str(loaded.get("schema") or "") != RECEIPT_SCHEMA:
        return None
    decision = str(loaded.get("router_decision") or "")
    if decision not in {
        BLOCK_FORGE_SELECTION_RISK,
        BLOCK_FORGE_EVIDENCE_GAP,
        FORGE_ELIGIBLE_WITH_SELECTION_CAVEAT,
    }:
        return None
    stored = str(loaded.get("receipt_sha256") or "")
    body = {key: value for key, value in loaded.items() if key != "receipt_sha256"}
    if stored != canonical_sha256(body):
        return None
    return loaded


def run_selection_robustness_gate(
    *,
    root: Path,
    census_path: Path | None = None,
    observations_path: Path | None = None,
    data_root: Path | None = None,
    spec_relative: str = SPEC_RELATIVE,
    persist: bool = True,
) -> dict[str, Any]:
    spec = _require_frozen_gate_spec(root, spec_relative)
    block_a_field_ids = [str(item["field_id"]) for item in spec["block_a_omnibus"]]
    git_head = _git_head(root)
    explicit = census_path is not None or observations_path is not None
    if data_root is not None and explicit:
        raise SelectionRobustnessGateError(CANONICAL_MODE_EXPLICIT_PATH_CONFLICT)
    if data_root is None and (census_path is None or observations_path is None):
        raise SelectionRobustnessGateError(CANONICAL_DATA_ROOT_OR_EXPLICIT_PATHS_REQUIRED)

    stage1: dict[str, Any] | None = None
    stage1_error: str | None = None
    try:
        if data_root is not None:
            stage1 = run_censoring_ignorability_diagnostic(
                root=root,
                data_root=Path(data_root),
            )
            input_mode = CANONICAL_INPUT_MODE
            population_scope = SCOPE_CANONICAL
        else:
            stage1 = run_censoring_ignorability_diagnostic(
                root=root,
                census_path=Path(census_path),
                observations_path=Path(observations_path),
            )
            input_mode = EXPLICIT_PATH_INPUT_MODE
            population_scope = SCOPE_NONCANONICAL
    except CensoringDiagnosticError as exc:
        stage1_error = str(exc)
        receipt = _compose_receipt(
            spec=spec,
            stage1=None,
            stage1_terminal=stage1_error,
            stage1_error=stage1_error,
            stage2_status=STAGE2_SKIPPED,
            stage2=None,
            input_mode=(
                CANONICAL_INPUT_MODE if data_root is not None else EXPLICIT_PATH_INPUT_MODE
            ),
            population_scope=(
                SCOPE_CANONICAL if data_root is not None else SCOPE_NONCANONICAL
            ),
            git_head=git_head,
            block_a_field_ids=block_a_field_ids,
            counts={},
            missingness=[],
            y_unread=0,
            census_sha256=None,
            observations_sha256=None,
            extra_reasons=["STAGE1_INTEGRITY_INVALID"],
        )
        if persist and data_root is not None:
            persist_gate_receipt(Path(data_root), receipt)
        return receipt

    input_mode = str(stage1.get("input_mode") or input_mode)
    population_scope = str(stage1.get("terminal_population_scope") or population_scope)
    stage1_terminal = _stage1_scientific(stage1.get("scientific_terminal"))
    skip_stage2 = stage1_terminal != SHIFT_NOT_DETECTED
    y_unread = int(stage1.get("y_point_rows_present_unread") or 0)
    counts = dict(stage1.get("counts") or {})
    census_sha = stage1.get("census_sha256")
    obs_sha = stage1.get("observations_sha256")
    if skip_stage2:
        receipt = _compose_receipt(
            spec=spec,
            stage1=stage1,
            stage1_terminal=stage1_terminal,
            stage1_error=None,
            stage2_status=STAGE2_SKIPPED,
            stage2=None,
            input_mode=input_mode,
            population_scope=population_scope,
            git_head=git_head,
            block_a_field_ids=block_a_field_ids,
            counts=counts,
            missingness=[],
            y_unread=y_unread,
            census_sha256=None if census_sha is None else str(census_sha),
            observations_sha256=None if obs_sha is None else str(obs_sha),
            extra_reasons=[],
        )
        if persist and data_root is not None:
            persist_gate_receipt(Path(data_root), receipt)
        return receipt

    try:
        if data_root is not None:
            corpus = spec.get("canonical_corpus") if isinstance(spec.get("canonical_corpus"), Mapping) else {}
            binding = bind_canonical_censoring_inputs(
                Path(data_root),
                corpus if isinstance(corpus, Mapping) else {},
            )
            members, member_counts, stage2_y_unread, member_reasons = _load_comparable_members(
                spec=spec,
                census_path=binding.census_path,
                observations_path=binding.observations_path,
            )
            census_sha = binding.census_sha256
            obs_sha = binding.observations_sha256
        else:
            members, member_counts, stage2_y_unread, member_reasons = _load_comparable_members(
                spec=spec,
                census_path=Path(census_path),
                observations_path=Path(observations_path),
            )
    except CensoringDiagnosticError as exc:
        stage2 = {
            "terminal": STAGE2_INCONCLUSIVE,
            "inconclusive_reasons": [str(exc)],
            "oof_roc_auc": None,
            "permutation_hits": None,
            "permutation_p": None,
            "oof_prediction_sha256": None,
        }
        receipt = _compose_receipt(
            spec=spec,
            stage1=stage1,
            stage1_terminal=stage1_terminal,
            stage1_error=None,
            stage2_status=STAGE2_RAN,
            stage2=stage2,
            input_mode=input_mode,
            population_scope=population_scope,
            git_head=git_head,
            block_a_field_ids=block_a_field_ids,
            counts=counts,
            missingness=[],
            y_unread=y_unread,
            census_sha256=None if census_sha is None else str(census_sha),
            observations_sha256=None if obs_sha is None else str(obs_sha),
            extra_reasons=[],
        )
        if persist and data_root is not None:
            persist_gate_receipt(Path(data_root), receipt)
        return receipt
    y_unread = max(y_unread, stage2_y_unread)
    if int(stage1.get("comparable_x_subset_n") or -1) != len(members):
        member_reasons.append("COMPARABLE_N_MISMATCH_STAGE1")
    if member_counts.get("x_eligible_observed") != counts.get("x_eligible_observed"):
        member_reasons.append("GROUP_COUNT_MISMATCH_STAGE1")
    if member_counts.get("x_eligible_censored_late") != counts.get("x_eligible_censored_late"):
        member_reasons.append("GROUP_COUNT_MISMATCH_STAGE1")
    missingness = _missingness_rows(members, spec)
    if member_reasons:
        stage2 = {
            "terminal": STAGE2_INCONCLUSIVE,
            "inconclusive_reasons": list(dict.fromkeys(member_reasons)),
            "oof_roc_auc": None,
            "permutation_hits": None,
            "permutation_p": None,
            "oof_prediction_sha256": None,
        }
    else:
        stage2 = _run_stage2(members, spec)
    receipt = _compose_receipt(
        spec=spec,
        stage1=stage1,
        stage1_terminal=stage1_terminal,
        stage1_error=None,
        stage2_status=STAGE2_RAN,
        stage2=stage2,
        input_mode=input_mode,
        population_scope=population_scope,
        git_head=git_head,
        block_a_field_ids=block_a_field_ids,
        counts=counts,
        missingness=missingness,
        y_unread=y_unread,
        census_sha256=None if census_sha is None else str(census_sha),
        observations_sha256=None if obs_sha is None else str(obs_sha),
        extra_reasons=[],
    )
    if persist and data_root is not None:
        persist_gate_receipt(Path(data_root), receipt)
    return receipt


def run_from_capability_spec(
    spec: Mapping[str, Any],
    *,
    root: Path,
    capture_hooks: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    hooks = dict(capture_hooks or {})
    parameters = spec.get("parameters") if isinstance(spec.get("parameters"), Mapping) else {}
    census_relative = hooks.get("census_relative") or parameters.get("census_relative")
    observations_relative = hooks.get("observations_relative") or parameters.get(
        "observations_relative"
    )
    data_root_relative = hooks.get("data_root_relative") or parameters.get(
        "data_root_relative"
    )
    spec_relative = hooks.get("spec_relative") or parameters.get("spec_relative") or SPEC_RELATIVE
    if not isinstance(spec_relative, str) or _unsafe(spec_relative):
        raise SelectionRobustnessGateError("GATE_SPEC_PATH_UNSAFE")
    if _canonical_spec_relative(spec_relative) != SPEC_RELATIVE:
        raise SelectionRobustnessGateError("FROZEN_SPEC_PATH_REQUIRED")
    persist = bool(hooks.get("persist", True))
    if isinstance(data_root_relative, str) and data_root_relative:
        if isinstance(census_relative, str) or isinstance(observations_relative, str):
            raise SelectionRobustnessGateError(CANONICAL_MODE_EXPLICIT_PATH_CONFLICT)
        if _unsafe(data_root_relative):
            raise SelectionRobustnessGateError("CAPABILITY_PATH_UNSAFE")
        receipt = run_selection_robustness_gate(
            root=root,
            data_root=root / data_root_relative,
            spec_relative=spec_relative,
            persist=persist,
        )
    else:
        if not isinstance(census_relative, str) or not isinstance(observations_relative, str):
            raise SelectionRobustnessGateError("EXPLICIT_RELEASE_PATHS_REQUIRED")
        if _unsafe(census_relative) or _unsafe(observations_relative):
            raise SelectionRobustnessGateError("CAPABILITY_PATH_UNSAFE")
        receipt = run_selection_robustness_gate(
            root=root,
            census_path=root / census_relative,
            observations_path=root / observations_relative,
            spec_relative=spec_relative,
            persist=False,
        )
    return {
        "status": "COMPLETE",
        "blocker": "NONE",
        "terminal": receipt["router_decision"],
        "result": receipt["router_decision"],
        "router_decision": receipt["router_decision"],
        "provider_api_rpc_wss_calls": 0,
        "credential_reads": 0,
        "receipt": receipt,
    }
