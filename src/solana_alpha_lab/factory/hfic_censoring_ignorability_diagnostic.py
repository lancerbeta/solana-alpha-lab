"""Offline X300 selection diagnostic for census censored_late membership.

Does not certify MAR, ignorability, identification, alpha, or a market
hypothesis. Never materializes Y-point typed values into the working matrix.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.contracts.schema_v1 import DatasetManifest, PartitionManifest
from solana_alpha_lab.factory.live_cohort_discovery_release import (
    _corpus_lineage_path,
    _load_lineage,
)
from solana_alpha_lab.factory.live_cohort_source_bundle import sha256_file_streaming
from solana_alpha_lab.factory.run_passport import canonical_sha256
from solana_alpha_lab.factory.tokens_v2_typed_projection import STATE_OBSERVED
from solana_alpha_lab.storage.manifests import verify_partition_manifest

CAP_HFIC_CENSORING_IGNORABILITY_DIAGNOSTIC = (
    "CAP-HFIC-CENSORING-IGNORABILITY-DIAGNOSTIC-001"
)
SPEC_RELATIVE = "configs/hfic_censoring_ignorability_diagnostic_v1.yaml"
FROZEN_SPEC_SHA256 = "47668ad5a7316b4bdb1a78be0bbc9bd1caed24ba597f10c6cf966dfaa05d556c"
Y_POINT_READ = "Y_POINT_READ"
EXPLICIT_RELEASE_PATHS_REQUIRED = "EXPLICIT_RELEASE_PATHS_REQUIRED"
CANONICAL_MODE_EXPLICIT_PATH_CONFLICT = "CANONICAL_MODE_EXPLICIT_PATH_CONFLICT"
CANONICAL_DATA_ROOT_OR_EXPLICIT_PATHS_REQUIRED = (
    "CANONICAL_DATA_ROOT_OR_EXPLICIT_PATHS_REQUIRED"
)
CANONICAL_HASH_PIN_MISSING = "CANONICAL_HASH_PIN_MISSING"
CANONICAL_LINEAGE_MISSING = "CANONICAL_LINEAGE_MISSING"
CANONICAL_LOGICAL_DATASET_MISMATCH = "CANONICAL_LOGICAL_DATASET_MISMATCH"
CANONICAL_COHORT_ABSENT = "CANONICAL_COHORT_ABSENT"
CANONICAL_COHORT_DUPLICATE = "CANONICAL_COHORT_DUPLICATE"
CANONICAL_RELEASE_MISMATCH = "CANONICAL_RELEASE_MISMATCH"
CANONICAL_DATASET_MANIFEST_MISSING = "CANONICAL_DATASET_MANIFEST_MISSING"
CANONICAL_PARTITION_MISSING = "CANONICAL_PARTITION_MISSING"
CANONICAL_PARTITION_LOCATION_MISMATCH = "CANONICAL_PARTITION_LOCATION_MISMATCH"
CANONICAL_PARTITION_HASH_MISMATCH = "CANONICAL_PARTITION_HASH_MISMATCH"
CANONICAL_CENSUS_HASH_MISMATCH = "CANONICAL_CENSUS_HASH_MISMATCH"
CANONICAL_OBSERVATIONS_HASH_MISMATCH = "CANONICAL_OBSERVATIONS_HASH_MISMATCH"
CANONICAL_CENSUS_IDENTITY_INVALID = "CANONICAL_CENSUS_IDENTITY_INVALID"
CANONICAL_OBSERVATIONS_IDENTITY_INVALID = "CANONICAL_OBSERVATIONS_IDENTITY_INVALID"
CANONICAL_INPUT_MODE = "CANONICAL"
EXPLICIT_PATH_INPUT_MODE = "EXPLICIT_PATH"
SHIFT_DETECTED = "CENSORING_OBSERVED_X_SHIFT_DETECTED"
SHIFT_NOT_DETECTED = "CENSORING_OBSERVED_X_SHIFT_NOT_DETECTED"
INCONCLUSIVE = "CENSORING_DIAGNOSTIC_INCONCLUSIVE"
OBSERVATION_MINT_MISSING_FROM_CENSUS = "OBSERVATION_MINT_MISSING_FROM_CENSUS"
# Receipt 1.1: counts["census_rows"] and counts["other"] keep 1.0 full-file
# meaning. UNKNOWN_CENSUS_STATE keys off other_in_scope. Diagnostic census is
# X300 observation mints after bind, not Y-only membership.
RECEIPT_SCHEMA_VERSION = "1.1"
ANCHOR_UNRESOLVED = "CENSORING_NO_COMPARABLE_X300_ANCHOR_UNRESOLVED"
ADMITTED_NOT_X_ELIGIBLE = "CENSORING_ADMITTED_NOT_X_ELIGIBLE"
IGNORABILITY_UNPROVEN = "IGNORABILITY_UNPROVEN"
IDENTIFICATION_UNPROVEN = "IDENTIFICATION_UNPROVEN"
RANDOM_SAMPLE_UNPROVEN = "RANDOM_SAMPLE_UNPROVEN"
SCOPE_CANONICAL = "CANONICAL_COMPARABLE_X_SUBSET"
SCOPE_NONCANONICAL = "SYNTHETIC_OR_NONCANONICAL_POPULATION"
VARIANCE_EPSILON = 1e-18
CENSUS_REQUIRED = ("mint", "candidate_state", "denominator_state")
OBS_KEY_REQUIRED = ("mint", "point_id", "field_id", "state")
OBS_TYPED_REQUIRED = ("mint", "field_id", "typed_value", "state")
CATEGORICAL_SMD_FROZEN = {
    "statistic": "pairwise_proportion",
    "pooled": "joint_hits_over_joint_n",
    "denominator": "sqrt_max_pooled_complement_epsilon",
    "omnibus_reduction": "max_abs",
}

NON_CLAIMS = (
    "NO_MAR",
    "NO_IGNORABILITY",
    "NO_IDENTIFIABILITY",
    "NO_ALPHA",
    "NO_MARKET_HYPOTHESIS_VALIDITY",
    "NO_Y_POINT_READ",
    "NO_CANONICAL_ACTIVE_RDP_RUN_THIS_ATOM",
)


class CensoringDiagnosticError(ValueError):
    """Fail-closed diagnostic protocol error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _unsafe(relative: str) -> bool:
    return Path(relative).is_absolute() or ".." in Path(relative).parts


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_spec_relative(relative: str) -> str:
    return Path(str(relative).replace("\\", "/")).as_posix()


def load_diagnostic_spec(root: Path, relative: str = SPEC_RELATIVE) -> dict[str, Any]:
    if _unsafe(relative):
        raise CensoringDiagnosticError("DIAGNOSTIC_SPEC_PATH_UNSAFE")
    path = root / relative
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CensoringDiagnosticError("DIAGNOSTIC_SPEC_MISSING") from exc
    if not isinstance(loaded, dict):
        raise CensoringDiagnosticError("DIAGNOSTIC_SPEC_INVALID")
    allowed = str(loaded.get("allowed_point_id") or "")
    y_prefix = str(loaded.get("y_point_prefix") or "Y")
    if not allowed or allowed.startswith(y_prefix):
        raise CensoringDiagnosticError(Y_POINT_READ)
    block_a = loaded.get("block_a_omnibus")
    if not isinstance(block_a, list) or not block_a:
        raise CensoringDiagnosticError("DIAGNOSTIC_SPEC_INVALID")
    for item in block_a:
        if not isinstance(item, Mapping):
            raise CensoringDiagnosticError("DIAGNOSTIC_SPEC_INVALID")
        field_id = str(item.get("field_id") or "")
        if field_id.startswith("FIELD-") is False:
            raise CensoringDiagnosticError("DIAGNOSTIC_SPEC_INVALID")
        if not str(item.get("value_kind") or ""):
            raise CensoringDiagnosticError("DIAGNOSTIC_SPEC_INVALID")
    categorical = loaded.get("categorical_smd")
    if not isinstance(categorical, Mapping) or dict(categorical) != CATEGORICAL_SMD_FROZEN:
        raise CensoringDiagnosticError("DIAGNOSTIC_SPEC_INVALID")
    try:
        epsilon = float(loaded.get("variance_epsilon"))
    except (TypeError, ValueError) as exc:
        raise CensoringDiagnosticError("DIAGNOSTIC_SPEC_INVALID") from exc
    if epsilon <= 0.0:
        raise CensoringDiagnosticError("DIAGNOSTIC_SPEC_INVALID")
    return loaded


def _require_frozen_spec(root: Path, spec_relative: str) -> dict[str, Any]:
    if _canonical_spec_relative(spec_relative) != SPEC_RELATIVE:
        raise CensoringDiagnosticError("FROZEN_SPEC_PATH_REQUIRED")
    path = root / SPEC_RELATIVE
    if not path.is_file() or path.is_symlink():
        raise CensoringDiagnosticError("DIAGNOSTIC_SPEC_MISSING")
    if _sha256_file(path) != FROZEN_SPEC_SHA256:
        raise CensoringDiagnosticError("FROZEN_SPEC_HASH_MISMATCH")
    return load_diagnostic_spec(root, SPEC_RELATIVE)


BLOCK_A_TYPED_READ_CALLS = 0


def reset_block_a_typed_read_probe() -> None:
    global BLOCK_A_TYPED_READ_CALLS
    BLOCK_A_TYPED_READ_CALLS = 0


@dataclass(frozen=True)
class CanonicalCorpusBinding:
    census_path: Path
    observations_path: Path
    dataset_id: str
    cohort_id: str
    release_id: str
    census_sha256: str
    observations_sha256: str
    dataset_manifest_id: str
    census_logical_location: str
    observations_logical_location: str


def _require_hash64(value: object, code: str) -> str:
    text = str(value or "")
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise CensoringDiagnosticError(code)
    return text


def _require_relative_parquet(location: object, code: str) -> str:
    text = str(location or "").replace("\\", "/")
    if not text or _unsafe(text) or not text.endswith(".parquet"):
        raise CensoringDiagnosticError(code)
    return text


def _require_row_release_cohort(
    path: Path,
    *,
    release_id: str,
    cohort_id: str,
    code: str,
) -> None:
    if not path.is_file() or path.is_symlink():
        raise CensoringDiagnosticError(code)
    connection = _duckdb_connect()
    try:
        columns = _parquet_columns(connection, path)
        if "release_id" not in columns or "cohort_id" not in columns:
            raise CensoringDiagnosticError(code)
        pairs = connection.execute(
            (
                "SELECT CAST(release_id AS VARCHAR), CAST(cohort_id AS VARCHAR), "
                "COUNT(*) FROM read_parquet(?) GROUP BY 1, 2"
            ),
            [str(path)],
        ).fetchall()
        if len(pairs) != 1:
            raise CensoringDiagnosticError(code)
        got_release, got_cohort, count = pairs[0]
        if (
            not got_release
            or not got_cohort
            or int(count) < 1
            or str(got_release) != release_id
            or str(got_cohort) != cohort_id
        ):
            raise CensoringDiagnosticError(code)
    except CensoringDiagnosticError:
        raise
    except Exception as exc:
        raise CensoringDiagnosticError(code) from exc
    finally:
        connection.close()


def _load_partition(
    data_root: Path,
    *,
    dataset_manifest_id: str,
    partition_id: str,
) -> PartitionManifest:
    part_dir = Path(data_root) / "datasets" / "manifests" / "partitions"
    matches: list[PartitionManifest] = []
    if part_dir.is_dir():
        for path in sorted(part_dir.glob("partition-*.json")):
            if path.is_symlink() or not path.is_file():
                continue
            try:
                part = PartitionManifest.model_validate_json(path.read_bytes())
            except Exception:
                continue
            if (
                part.dataset_manifest_id == dataset_manifest_id
                and part.partition_id == partition_id
            ):
                matches.append(part)
    if len(matches) != 1:
        raise CensoringDiagnosticError(CANONICAL_PARTITION_MISSING)
    try:
        verify_partition_manifest(matches[0])
    except CensoringDiagnosticError:
        raise
    except Exception as exc:
        raise CensoringDiagnosticError(CANONICAL_PARTITION_HASH_MISMATCH) from exc
    return matches[0]


def bind_canonical_censoring_inputs(
    data_root: Path,
    corpus: Mapping[str, Any] | None,
) -> CanonicalCorpusBinding:
    """Fail closed before any Block A X300 typed_value read."""

    pins = corpus if isinstance(corpus, Mapping) else {}
    frozen_dataset = str(pins.get("dataset_id") or "")
    frozen_cohort = str(pins.get("cohort_id") or "")
    frozen_release = str(pins.get("release_id") or "")
    frozen_census = _require_hash64(
        pins.get("census_sha256"), CANONICAL_HASH_PIN_MISSING
    )
    frozen_obs = _require_hash64(
        pins.get("observations_sha256"), CANONICAL_HASH_PIN_MISSING
    )
    if not frozen_dataset or not frozen_cohort or not frozen_release:
        raise CensoringDiagnosticError(CANONICAL_HASH_PIN_MISSING)
    root = Path(data_root)
    lineage_path = _corpus_lineage_path(root)
    if not lineage_path.is_file() or lineage_path.is_symlink():
        raise CensoringDiagnosticError(CANONICAL_LINEAGE_MISSING)
    try:
        lineage = _load_lineage(root)
    except CensoringDiagnosticError:
        raise
    except Exception as exc:
        raise CensoringDiagnosticError(CANONICAL_LINEAGE_MISSING) from exc
    if str(lineage.get("corpus_dataset_id") or "") != frozen_dataset:
        raise CensoringDiagnosticError(CANONICAL_LOGICAL_DATASET_MISMATCH)
    matches = [
        item
        for item in (lineage.get("cohorts") or [])
        if isinstance(item, Mapping) and str(item.get("cohort_id") or "") == frozen_cohort
    ]
    if not matches:
        raise CensoringDiagnosticError(CANONICAL_COHORT_ABSENT)
    if len(matches) != 1:
        raise CensoringDiagnosticError(CANONICAL_COHORT_DUPLICATE)
    component = matches[0]
    if str(component.get("release_id") or "") != frozen_release:
        raise CensoringDiagnosticError(CANONICAL_RELEASE_MISMATCH)
    census_rel = _require_relative_parquet(
        component.get("census_rel"), CANONICAL_PARTITION_LOCATION_MISMATCH
    )
    obs_rel = _require_relative_parquet(
        component.get("obs_rel"), CANONICAL_PARTITION_LOCATION_MISMATCH
    )
    lineage_census = _require_hash64(
        component.get("census_sha256"), CANONICAL_CENSUS_HASH_MISMATCH
    )
    lineage_obs = _require_hash64(
        component.get("observations_sha256"), CANONICAL_OBSERVATIONS_HASH_MISMATCH
    )
    if lineage_census != frozen_census:
        raise CensoringDiagnosticError(CANONICAL_CENSUS_HASH_MISMATCH)
    if lineage_obs != frozen_obs:
        raise CensoringDiagnosticError(CANONICAL_OBSERVATIONS_HASH_MISMATCH)
    current_mid = str(lineage.get("current_dataset_manifest_id") or "")
    manifest_path = root / "datasets" / "manifests" / f"{current_mid}.json"
    if not current_mid or not manifest_path.is_file() or manifest_path.is_symlink():
        raise CensoringDiagnosticError(CANONICAL_DATASET_MANIFEST_MISSING)
    try:
        dataset = DatasetManifest.model_validate_json(manifest_path.read_bytes())
    except Exception as exc:
        raise CensoringDiagnosticError(CANONICAL_DATASET_MANIFEST_MISSING) from exc
    if dataset.dataset_id != frozen_dataset or dataset.dataset_manifest_id != current_mid:
        raise CensoringDiagnosticError(CANONICAL_LOGICAL_DATASET_MISMATCH)
    census_part = _load_partition(
        root,
        dataset_manifest_id=current_mid,
        partition_id=f"PARTITION-LIVE-COHORT-{frozen_cohort}-CENSUS",
    )
    obs_part = _load_partition(
        root,
        dataset_manifest_id=current_mid,
        partition_id=f"PARTITION-LIVE-COHORT-{frozen_cohort}-OBS",
    )
    if census_part.logical_location != census_rel:
        raise CensoringDiagnosticError(CANONICAL_PARTITION_LOCATION_MISMATCH)
    if obs_part.logical_location != obs_rel:
        raise CensoringDiagnosticError(CANONICAL_PARTITION_LOCATION_MISMATCH)
    if census_part.file_sha256 != frozen_census:
        raise CensoringDiagnosticError(CANONICAL_PARTITION_HASH_MISMATCH)
    if obs_part.file_sha256 != frozen_obs:
        raise CensoringDiagnosticError(CANONICAL_PARTITION_HASH_MISMATCH)
    census_path = root / census_rel
    obs_path = root / obs_rel
    if not census_path.is_file() or census_path.is_symlink():
        raise CensoringDiagnosticError(CANONICAL_CENSUS_HASH_MISMATCH)
    if not obs_path.is_file() or obs_path.is_symlink():
        raise CensoringDiagnosticError(CANONICAL_OBSERVATIONS_HASH_MISMATCH)
    actual_census = sha256_file_streaming(census_path)
    actual_obs = sha256_file_streaming(obs_path)
    if actual_census != frozen_census:
        raise CensoringDiagnosticError(CANONICAL_CENSUS_HASH_MISMATCH)
    if actual_obs != frozen_obs:
        raise CensoringDiagnosticError(CANONICAL_OBSERVATIONS_HASH_MISMATCH)
    _require_row_release_cohort(
        census_path,
        release_id=frozen_release,
        cohort_id=frozen_cohort,
        code=CANONICAL_CENSUS_IDENTITY_INVALID,
    )
    _require_row_release_cohort(
        obs_path,
        release_id=frozen_release,
        cohort_id=frozen_cohort,
        code=CANONICAL_OBSERVATIONS_IDENTITY_INVALID,
    )
    return CanonicalCorpusBinding(
        census_path=census_path,
        observations_path=obs_path,
        dataset_id=frozen_dataset,
        cohort_id=frozen_cohort,
        release_id=frozen_release,
        census_sha256=frozen_census,
        observations_sha256=frozen_obs,
        dataset_manifest_id=current_mid,
        census_logical_location=census_rel,
        observations_logical_location=obs_rel,
    )


def _duckdb_connect() -> Any:
    import duckdb

    try:
        return duckdb.connect(database=":memory:")
    except Exception as exc:
        raise CensoringDiagnosticError("DUCKDB_UNAVAILABLE") from exc


def _parquet_columns(connection: Any, path: Path) -> set[str]:
    rows = connection.execute(
        "DESCRIBE SELECT * FROM read_parquet(?)",
        [str(path)],
    ).fetchall()
    return {str(row[0]) for row in rows}


def _require_columns(columns: set[str], required: Sequence[str], code: str) -> None:
    missing = [name for name in required if name not in columns]
    if missing:
        raise CensoringDiagnosticError(code)


def _fetch_maps(connection: Any, sql: str, params: list[Any]) -> list[dict[str, Any]]:
    relation = connection.execute(sql, params)
    names = [item[0] for item in relation.description]
    return [dict(zip(names, row, strict=True)) for row in relation.fetchall()]


def _as_float(value: object) -> float | None:
    if value is None or value is True or value is False:
        return None
    if isinstance(value, (int, float)):
        parsed = float(value)
        if not math.isfinite(parsed) or parsed < 0:
            return None
        return parsed
    if not isinstance(value, str) or value == "":
        return None
    try:
        parsed = float(value)
    except ValueError:
        try:
            loaded = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        if isinstance(loaded, bool) or not isinstance(loaded, (int, float, str)):
            return None
        try:
            parsed = float(loaded)
        except (TypeError, ValueError):
            return None
    if not math.isfinite(parsed) or parsed < 0:
        return None
    return parsed


def _as_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return None
        if text[:1] in {"\"", "'", "{", "["}:
            try:
                loaded = json.loads(text)
            except (TypeError, ValueError, json.JSONDecodeError):
                return text
            if isinstance(loaded, str) and loaded.strip():
                return loaded.strip()
        return text
    return str(value)


def _log1p(value: float) -> float:
    return math.log1p(value)


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _sample_variance(values: Sequence[float], mean: float) -> float:
    if len(values) < 2:
        return 0.0
    return sum((item - mean) ** 2 for item in values) / (len(values) - 1)


def _percentile(sorted_values: Sequence[float], fraction: float) -> float:
    if not sorted_values:
        raise CensoringDiagnosticError("PERCENTILE_EMPTY")
    last = len(sorted_values) - 1
    index = last * fraction
    low = math.floor(index)
    high = math.ceil(index)
    if low == high:
        return sorted_values[low]
    weight = index - low
    return sorted_values[low] * (1.0 - weight) + sorted_values[high] * weight


def _cohen_d(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) < 2 or len(right) < 2:
        return None
    mean_l = _mean(left)
    mean_r = _mean(right)
    var_l = _sample_variance(left, mean_l)
    var_r = _sample_variance(right, mean_r)
    pooled = ((len(left) - 1) * var_l + (len(right) - 1) * var_r) / (
        len(left) + len(right) - 2
    )
    if pooled <= 0.0:
        return 0.0 if mean_l == mean_r else math.inf
    return (mean_l - mean_r) / math.sqrt(pooled)


def _variance_ratio(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) < 2 or len(right) < 2:
        return None
    var_l = _sample_variance(left, _mean(left))
    var_r = _sample_variance(right, _mean(right))
    high = max(var_l, var_r)
    low = max(min(var_l, var_r), VARIANCE_EPSILON)
    return high / low


def _iqr_overlap(left: Sequence[float], right: Sequence[float]) -> bool | None:
    if len(left) < 4 or len(right) < 4:
        return None
    left_sorted = sorted(left)
    right_sorted = sorted(right)
    q1_l = _percentile(left_sorted, 0.25)
    q3_l = _percentile(left_sorted, 0.75)
    q1_r = _percentile(right_sorted, 0.25)
    q3_r = _percentile(right_sorted, 0.75)
    return not (q3_l < q1_r or q3_r < q1_l)


def _proportion_smd(
    left_n: int,
    right_n: int,
    left_hits: int,
    right_hits: int,
    *,
    variance_epsilon: float,
) -> float | None:
    if left_n < 1 or right_n < 1:
        return None
    p_l = left_hits / left_n
    p_r = right_hits / right_n
    pooled = (left_hits + right_hits) / (left_n + right_n)
    denom = math.sqrt(max(pooled * (1.0 - pooled), variance_epsilon))
    return (p_l - p_r) / denom


def _seed_int(seed: str) -> int:
    try:
        return int(str(seed), 16)
    except ValueError as exc:
        raise CensoringDiagnosticError("PERMUTATION_SEED_INVALID") from exc


def _load_census(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or path.is_symlink():
        raise CensoringDiagnosticError("CENSUS_PARQUET_MISSING")
    connection = _duckdb_connect()
    try:
        columns = _parquet_columns(connection, path)
        _require_columns(columns, CENSUS_REQUIRED, "CENSUS_SCHEMA_INVALID")
        selected = [
            name
            for name in (
                *CENSUS_REQUIRED,
                "authoritative_anchor",
                "discovery_first_reliable_available_at",
                "inclusion_probability",
                "cohort_id",
                "release_id",
                "dataset_id",
                "corpus_id",
                "scientific_context_session",
            )
            if name in columns
        ]
        quoted = ", ".join(f'"{name}"' for name in selected)
        order = "mint" if "mint" in selected else selected[0]
        return _fetch_maps(
            connection,
            f'SELECT {quoted} FROM read_parquet(?) ORDER BY "{order}"',
            [str(path)],
        )
    except CensoringDiagnosticError:
        raise
    except Exception as exc:
        raise CensoringDiagnosticError("CENSUS_PARQUET_UNREADABLE") from exc
    finally:
        connection.close()


def _load_x300_keys(
    path: Path,
    *,
    allowed_point_id: str,
    y_prefix: str,
) -> tuple[list[dict[str, Any]], int]:
    if not path.is_file() or path.is_symlink():
        raise CensoringDiagnosticError("OBSERVATIONS_PARQUET_MISSING")
    if allowed_point_id.startswith(y_prefix):
        raise CensoringDiagnosticError(Y_POINT_READ)
    connection = _duckdb_connect()
    try:
        columns = _parquet_columns(connection, path)
        _require_columns(columns, OBS_KEY_REQUIRED, "OBSERVATIONS_SCHEMA_INVALID")
        selected = [
            name
            for name in (
                *OBS_KEY_REQUIRED,
                "cohort_id",
                "release_id",
                "dataset_id",
                "corpus_id",
                "scientific_context_session",
            )
            if name in columns
        ]
        quoted = ", ".join(f'"{name}"' for name in selected)
        order_sql = (
            'ORDER BY "mint", "field_id"' if "field_id" in selected else 'ORDER BY "mint"'
        )
        y_unread = int(
            connection.execute(
                "SELECT COUNT(*) FROM read_parquet(?) WHERE CAST(point_id AS VARCHAR) LIKE ?",
                [str(path), f"{y_prefix}%"],
            ).fetchone()[0]
        )
        rows = _fetch_maps(
            connection,
            (
                f"SELECT {quoted} FROM read_parquet(?) "
                "WHERE CAST(point_id AS VARCHAR) = ? "
                f"{order_sql}"
            ),
            [str(path), allowed_point_id],
        )
        for row in rows:
            point_id = str(row.get("point_id") or "")
            if point_id.startswith(y_prefix) or point_id != allowed_point_id:
                raise CensoringDiagnosticError(Y_POINT_READ)
            if "typed_value" in row:
                raise CensoringDiagnosticError(Y_POINT_READ)
        return rows, y_unread
    except CensoringDiagnosticError:
        raise
    except Exception as exc:
        raise CensoringDiagnosticError("OBSERVATIONS_PARQUET_UNREADABLE") from exc
    finally:
        connection.close()


def _load_block_a_typed(
    path: Path,
    *,
    allowed_point_id: str,
    y_prefix: str,
    field_ids: Sequence[str],
) -> list[dict[str, Any]]:
    if not field_ids:
        raise CensoringDiagnosticError("DIAGNOSTIC_SPEC_INVALID")
    if allowed_point_id.startswith(y_prefix):
        raise CensoringDiagnosticError(Y_POINT_READ)
    global BLOCK_A_TYPED_READ_CALLS
    BLOCK_A_TYPED_READ_CALLS += 1
    connection = _duckdb_connect()
    try:
        columns = _parquet_columns(connection, path)
        _require_columns(columns, OBS_TYPED_REQUIRED, "OBSERVATIONS_SCHEMA_INVALID")
        selected = [
            name
            for name in (*OBS_TYPED_REQUIRED, "value_kind")
            if name in columns
        ]
        quoted = ", ".join(f'"{name}"' for name in selected)
        placeholders = ", ".join(["?"] * len(field_ids))
        rows = _fetch_maps(
            connection,
            (
                f"SELECT {quoted} FROM read_parquet(?) "
                "WHERE CAST(point_id AS VARCHAR) = ? "
                f"AND CAST(field_id AS VARCHAR) IN ({placeholders}) "
                'ORDER BY "mint", "field_id"'
            ),
            [str(path), allowed_point_id, *field_ids],
        )
        for row in rows:
            point_id = str(row.get("point_id") or "")
            if point_id.startswith(y_prefix):
                raise CensoringDiagnosticError(Y_POINT_READ)
        return rows
    except CensoringDiagnosticError:
        raise
    except Exception as exc:
        raise CensoringDiagnosticError("OBSERVATIONS_PARQUET_UNREADABLE") from exc
    finally:
        connection.close()


def _retain_unique_mint_field(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    retained: dict[tuple[str, str], dict[str, Any]] = {}
    duplicates: set[tuple[str, str]] = set()
    for row in rows:
        mint = str(row.get("mint") or "")
        field_id = str(row.get("field_id") or "")
        if not mint or not field_id:
            continue
        key = (mint, field_id)
        if key in duplicates:
            continue
        if key in retained:
            duplicates.add(key)
            del retained[key]
            continue
        retained[key] = dict(row)
    return list(retained.values()), bool(duplicates)


def _unique_identity(
    rows: Sequence[Mapping[str, Any]], key: str
) -> tuple[str | None, bool]:
    values: set[str] = set()
    seen_empty = False
    for row in rows:
        text = str(row.get(key) or "")
        if not text:
            seen_empty = True
            continue
        values.add(text)
        if len(values) > 1:
            return None, True
    if values and seen_empty:
        return None, True
    if not values:
        return None, False
    return next(iter(values)), False


def _parquet_unique_identity(path: Path, key: str) -> tuple[str | None, bool]:
    connection = _duckdb_connect()
    try:
        columns = _parquet_columns(connection, path)
        if key not in columns:
            return None, False
        rows = connection.execute(
            f'SELECT DISTINCT CAST("{key}" AS VARCHAR) FROM read_parquet(?)',
            [str(path)],
        ).fetchall()
    except CensoringDiagnosticError:
        raise
    except Exception as exc:
        raise CensoringDiagnosticError("OBSERVATIONS_PARQUET_UNREADABLE") from exc
    finally:
        connection.close()
    values: set[str] = set()
    seen_empty = False
    for row in rows:
        text = str(row[0] or "")
        if not text:
            seen_empty = True
            continue
        values.add(text)
        if len(values) > 1:
            return None, True
    if values and seen_empty:
        return None, True
    if not values:
        return None, False
    return next(iter(values)), False


def _parquet_distinct_mints(path: Path) -> set[str]:
    connection = _duckdb_connect()
    try:
        columns = _parquet_columns(connection, path)
        if "mint" not in columns:
            return set()
        rows = connection.execute(
            'SELECT DISTINCT CAST("mint" AS VARCHAR) FROM read_parquet(?)',
            [str(path)],
        ).fetchall()
    except CensoringDiagnosticError:
        raise
    except Exception as exc:
        raise CensoringDiagnosticError("OBSERVATIONS_PARQUET_UNREADABLE") from exc
    finally:
        connection.close()
    return {str(row[0]) for row in rows if str(row[0] or "")}


def _census_four_way(candidate: str, denom: str) -> bool:
    if candidate == "X_ELIGIBLE" and denom in {"observed", "censored_late"}:
        return True
    if candidate == "ADMITTED" and denom == "censored_late":
        return True
    return candidate == "X_POPULATION_INELIGIBLE"


def _group_label(row: Mapping[str, Any]) -> str | None:
    candidate = str(row.get("candidate_state") or "")
    denom = str(row.get("denominator_state") or "")
    if candidate == "X_ELIGIBLE" and denom == "observed":
        return "observed"
    if candidate == "X_ELIGIBLE" and denom == "censored_late":
        return "censored_late"
    return None


def _feature_values(
    members: Sequence[Mapping[str, Any]],
    feature_id: str,
) -> tuple[list[float], list[float]]:
    left: list[float] = []
    right: list[float] = []
    for member in members:
        value = member["features"].get(feature_id)
        if value is None:
            continue
        if member["group"] == "observed":
            left.append(float(value))
        else:
            right.append(float(value))
    return left, right


def _categorical_values(
    members: Sequence[Mapping[str, Any]],
    feature_id: str,
) -> tuple[list[str], list[str]]:
    left: list[str] = []
    right: list[str] = []
    for member in members:
        value = member["features"].get(feature_id)
        if value is None:
            continue
        if member["group"] == "observed":
            left.append(str(value))
        else:
            right.append(str(value))
    return left, right


def _collapse_levels(
    left: Sequence[str],
    right: Sequence[str],
    *,
    min_joint_n: int,
    other_label: str,
) -> tuple[list[str], list[str], dict[str, int]]:
    counts: dict[str, int] = {}
    for value in (*left, *right):
        counts[value] = counts.get(value, 0) + 1
    keep = {level for level, count in counts.items() if count >= min_joint_n}

    def _map(values: Sequence[str]) -> list[str]:
        return [value if value in keep else other_label for value in values]

    return _map(left), _map(right), counts


def _continuous_smd(
    members: Sequence[Mapping[str, Any]],
    feature: Mapping[str, Any],
) -> dict[str, Any]:
    feature_id = str(feature["feature_id"])
    left, right = _feature_values(members, feature_id)
    smd = _cohen_d(left, right)
    return {
        "feature_id": feature_id,
        "role": "continuous",
        "n_observed": len(left),
        "n_censored_late": len(right),
        "smd": smd,
        "abs_smd": None if smd is None else abs(smd),
        "variance_ratio": _variance_ratio(left, right),
        "iqr_overlap": _iqr_overlap(left, right),
    }


def _categorical_smd(
    members: Sequence[Mapping[str, Any]],
    feature: Mapping[str, Any],
    *,
    min_joint_n: int,
    other_label: str,
    variance_epsilon: float,
) -> dict[str, Any]:
    feature_id = str(feature["feature_id"])
    left_raw, right_raw = _categorical_values(members, feature_id)
    left, right, raw_counts = _collapse_levels(
        left_raw,
        right_raw,
        min_joint_n=min_joint_n,
        other_label=other_label,
    )
    levels = sorted(set(left) | set(right))
    level_smds: list[dict[str, Any]] = []
    abs_values: list[float] = []
    for level in levels:
        smd = _proportion_smd(
            len(left),
            len(right),
            sum(1 for item in left if item == level),
            sum(1 for item in right if item == level),
            variance_epsilon=variance_epsilon,
        )
        level_smds.append({"level": level, "smd": smd})
        if smd is not None:
            abs_values.append(abs(smd))
    feature_smd = max(abs_values) if abs_values else None
    signed = None
    if feature_smd is not None:
        for item in level_smds:
            value = item["smd"]
            if value is not None and abs(value) == feature_smd:
                signed = value
                break
    return {
        "feature_id": feature_id,
        "role": "categorical",
        "n_observed": len(left),
        "n_censored_late": len(right),
        "smd": signed,
        "abs_smd": feature_smd,
        "levels": level_smds,
        "raw_level_counts": raw_counts,
        "variance_ratio": None,
        "iqr_overlap": None,
    }


def _omnibus_rows(
    members: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
) -> list[dict[str, Any]]:
    min_joint_n = int(spec["rare_level_min_joint_n"])
    other_label = str(spec["rare_level_label"])
    variance_epsilon = float(spec["variance_epsilon"])
    rows: list[dict[str, Any]] = []
    for feature in spec["block_a_omnibus"]:
        role = str(feature.get("role") or "")
        if role == "continuous":
            rows.append(_continuous_smd(members, feature))
        elif role == "categorical":
            rows.append(
                _categorical_smd(
                    members,
                    feature,
                    min_joint_n=min_joint_n,
                    other_label=other_label,
                    variance_epsilon=variance_epsilon,
                )
            )
        else:
            raise CensoringDiagnosticError("DIAGNOSTIC_SPEC_INVALID")
    return rows


def _max_abs_smd(rows: Sequence[Mapping[str, Any]]) -> float | None:
    values = [
        float(row["abs_smd"])
        for row in rows
        if row.get("abs_smd") is not None and math.isfinite(float(row["abs_smd"]))
    ]
    inf_present = any(
        row.get("abs_smd") is not None and math.isinf(float(row["abs_smd"]))
        for row in rows
    )
    if inf_present:
        return math.inf
    if not values:
        return None
    return max(values)


def _relabel(
    members: Sequence[Mapping[str, Any]],
    labels: Sequence[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for member, label in zip(members, labels, strict=True):
        cloned = dict(member)
        cloned["group"] = label
        out.append(cloned)
    return out


def _spec_pins_match_binding(
    spec: Mapping[str, Any], binding: CanonicalCorpusBinding
) -> bool:
    corpus = spec.get("canonical_corpus")
    pins = corpus if isinstance(corpus, Mapping) else {}
    return (
        binding.dataset_id == str(pins.get("dataset_id") or "")
        and binding.cohort_id == str(pins.get("cohort_id") or "")
        and binding.release_id == str(pins.get("release_id") or "")
        and binding.census_sha256 == str(pins.get("census_sha256") or "")
        and binding.observations_sha256 == str(pins.get("observations_sha256") or "")
    )


def _run_with_verified_binding(
    *,
    root: Path,
    binding: CanonicalCorpusBinding,
    spec_relative: str = SPEC_RELATIVE,
) -> dict[str, Any]:
    """Test helper after bind PASS. Not a production input mode."""

    spec = _require_frozen_spec(root, spec_relative)
    return _execute_censoring_diagnostic(
        spec=spec,
        census_path=binding.census_path,
        observations_path=binding.observations_path,
        binding=binding,
        population_scope=SCOPE_CANONICAL,
        input_mode=CANONICAL_INPUT_MODE,
    )


def run_censoring_ignorability_diagnostic(
    *,
    root: Path,
    census_path: Path | None = None,
    observations_path: Path | None = None,
    data_root: Path | None = None,
    spec_relative: str = SPEC_RELATIVE,
) -> dict[str, Any]:
    spec = _require_frozen_spec(root, spec_relative)
    explicit = census_path is not None or observations_path is not None
    if data_root is not None and explicit:
        raise CensoringDiagnosticError(CANONICAL_MODE_EXPLICIT_PATH_CONFLICT)
    if data_root is not None:
        corpus = spec.get("canonical_corpus")
        binding = bind_canonical_censoring_inputs(
            Path(data_root),
            corpus if isinstance(corpus, Mapping) else {},
        )
        return _execute_censoring_diagnostic(
            spec=spec,
            census_path=binding.census_path,
            observations_path=binding.observations_path,
            binding=binding,
            population_scope=SCOPE_CANONICAL,
            input_mode=CANONICAL_INPUT_MODE,
        )
    if census_path is None or observations_path is None:
        raise CensoringDiagnosticError(CANONICAL_DATA_ROOT_OR_EXPLICIT_PATHS_REQUIRED)
    return _execute_censoring_diagnostic(
        spec=spec,
        census_path=Path(census_path),
        observations_path=Path(observations_path),
        binding=None,
        population_scope=SCOPE_NONCANONICAL,
        input_mode=EXPLICIT_PATH_INPUT_MODE,
    )


def _execute_censoring_diagnostic(
    *,
    spec: Mapping[str, Any],
    census_path: Path,
    observations_path: Path,
    binding: CanonicalCorpusBinding | None,
    population_scope: str,
    input_mode: str,
) -> dict[str, Any]:
    census_path = Path(census_path)
    observations_path = Path(observations_path)
    allowed_point_id = str(spec["allowed_point_id"])
    y_prefix = str(spec["y_point_prefix"])
    block_a = list(spec["block_a_omnibus"])
    field_ids = [str(item["field_id"]) for item in block_a]
    for item in spec.get("block_b_descriptive_not_omnibus") or []:
        field_id = str(item.get("field_id") or "")
        if field_id and field_id in field_ids:
            raise CensoringDiagnosticError("BLOCK_B_IN_OMNIBUS")
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
    duplicate_observations = duplicate_observations or duplicate_typed
    census_cohort, census_cohort_mixed = _unique_identity(census_rows, "cohort_id")
    census_dataset, census_dataset_mixed = _unique_identity(census_rows, "dataset_id")
    census_session, census_session_mixed = _unique_identity(
        census_rows, "scientific_context_session"
    )
    obs_cohort, obs_cohort_mixed = _parquet_unique_identity(
        observations_path, "cohort_id"
    )
    obs_dataset, obs_dataset_mixed = _parquet_unique_identity(
        observations_path, "dataset_id"
    )
    obs_session, obs_session_mixed = _parquet_unique_identity(
        observations_path, "scientific_context_session"
    )
    observation_mints = _parquet_distinct_mints(observations_path)
    x300_mints = {
        str(row.get("mint") or "")
        for row in unique_obs
        if str(row.get("mint") or "")
    }
    rng = random.Random(_seed_int(str(spec["permutation_seed"])))
    census_rows_total = len(census_rows)
    census_distinct_mints_total = len(
        {
            str(row.get("mint") or "")
            for row in census_rows
            if str(row.get("mint") or "")
        }
    )
    census_mints = {
        str(row.get("mint") or "")
        for row in census_rows
        if str(row.get("mint") or "")
    }
    observation_mint_missing_from_census = any(
        mint not in census_mints for mint in x300_mints
    )
    diagnostic_rows = [
        row
        for row in census_rows
        if str(row.get("mint") or "") in x300_mints
    ]
    diagnostic_distinct_mints = {
        str(row.get("mint") or "")
        for row in diagnostic_rows
        if str(row.get("mint") or "")
    }
    eligible_missing_from_observations = False
    for row in census_rows:
        mint = str(row.get("mint") or "")
        if (
            mint
            and str(row.get("candidate_state") or "") == "X_ELIGIBLE"
            and mint not in x300_mints
        ):
            eligible_missing_from_observations = True

    counts = {
        "census_rows": census_rows_total,
        "census_rows_total": census_rows_total,
        "census_distinct_mints_total": census_distinct_mints_total,
        "discovered_in_observation_partition": len(observation_mints),
        "diagnostic_population_census_rows": len(diagnostic_rows),
        "diagnostic_population_distinct_mints": len(diagnostic_distinct_mints),
        "out_of_scope_census_rows": census_rows_total - len(diagnostic_rows),
        "x_eligible_observed": 0,
        "x_eligible_censored_late": 0,
        "admitted_censored_late_no_x300": 0,
        "x_population_ineligible": 0,
        "other_in_scope": 0,
        "other": sum(
            1
            for row in census_rows
            if not _census_four_way(
                str(row.get("candidate_state") or ""),
                str(row.get("denominator_state") or ""),
            )
        ),
    }
    members: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    admitted_coverage: list[dict[str, Any]] = []
    obs_by_mint: dict[str, dict[str, dict[str, Any]]] = {}
    for row in unique_obs:
        mint = str(row.get("mint") or "")
        field_id = str(row.get("field_id") or "")
        if not mint or not field_id:
            continue
        obs_by_mint.setdefault(mint, {})[field_id] = row
    typed_by_mint: dict[str, dict[str, dict[str, Any]]] = {}
    for row in unique_typed:
        mint = str(row.get("mint") or "")
        field_id = str(row.get("field_id") or "")
        if not mint or not field_id:
            continue
        typed_by_mint.setdefault(mint, {})[field_id] = row
    value_kind_mismatch = False

    comparable_mints: set[str] = set()
    mint_row_n: dict[str, int] = {}
    for row in diagnostic_rows:
        mint = str(row.get("mint") or "")
        if mint:
            mint_row_n[mint] = mint_row_n.get(mint, 0) + 1
    duplicate_comparable = False
    duplicate_census = any(count > 1 for count in mint_row_n.values())
    empty_mint = False
    for row in diagnostic_rows:
        mint = str(row.get("mint") or "")
        candidate = str(row.get("candidate_state") or "")
        denom = str(row.get("denominator_state") or "")
        mint_obs = obs_by_mint.get(mint, {})
        has_x300 = any(
            str((mint_obs.get(str(feature["field_id"])) or {}).get("state") or "")
            == STATE_OBSERVED
            for feature in block_a
        )
        has_anchor = bool(str(row.get("authoritative_anchor") or ""))
        if candidate == "X_ELIGIBLE" and denom == "observed":
            counts["x_eligible_observed"] += 1
        elif candidate == "X_ELIGIBLE" and denom == "censored_late":
            counts["x_eligible_censored_late"] += 1
        elif candidate == "ADMITTED" and denom == "censored_late":
            if not has_x300:
                counts["admitted_censored_late_no_x300"] += 1
        elif candidate == "X_POPULATION_INELIGIBLE":
            counts["x_population_ineligible"] += 1
        else:
            counts["other_in_scope"] += 1
        if not mint:
            empty_mint = True
            continue
        if mint_row_n.get(mint, 0) > 1:
            if _group_label(row) is not None:
                duplicate_comparable = True
            continue
        group = _group_label(row)
        if group is None:
            if candidate == "ADMITTED" and denom == "censored_late":
                coverage_class = (
                    ANCHOR_UNRESOLVED if not has_anchor and not has_x300 else ADMITTED_NOT_X_ELIGIBLE
                )
                admitted_coverage.append(
                    {
                        "coverage_class": coverage_class,
                        "candidate_state": candidate,
                        "denominator_state": denom,
                        "authoritative_anchor_present": has_anchor,
                        "x300_block_a_present": has_x300,
                    }
                )
                if coverage_class == ANCHOR_UNRESOLVED:
                    unresolved.append(admitted_coverage[-1])
            continue
        if mint in comparable_mints:
            duplicate_comparable = True
            continue
        comparable_mints.add(mint)
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
                "group": group,
                "features": features,
                "observed_flags": observed_flags,
            }
        )

    comparable_n = len(members)
    coverage: list[dict[str, Any]] = []
    coverage_fail = False
    floor = float(spec["coverage_floor_joint_observed"])
    for feature in block_a:
        feature_id = str(feature["feature_id"])
        observed_n = sum(
            1 for member in members if member["observed_flags"].get(feature_id)
        )
        share = (observed_n / comparable_n) if comparable_n else 0.0
        if share < floor:
            coverage_fail = True
        coverage.append(
            {
                "feature_id": feature_id,
                "field_id": str(feature["field_id"]),
                "observed_n": observed_n,
                "comparable_n": comparable_n,
                "joint_observed_share": share,
            }
        )

    inconclusive: list[str] = []
    if comparable_n < 4:
        inconclusive.append("COMPARABLE_X_SUBSET_TOO_SMALL")
    if counts["x_eligible_observed"] < 2 or counts["x_eligible_censored_late"] < 2:
        inconclusive.append("GROUP_N_TOO_SMALL")
    if coverage_fail:
        inconclusive.append("COVERAGE_FLOOR_BREACH")
    if counts["other_in_scope"] > 0:
        inconclusive.append("UNKNOWN_CENSUS_STATE")
    if duplicate_comparable:
        inconclusive.append("DUPLICATE_COMPARABLE_MINT")
    if duplicate_census:
        inconclusive.append("DUPLICATE_CENSUS_MINT")
    if duplicate_observations:
        inconclusive.append("DUPLICATE_X300_OBSERVATION")
    if empty_mint:
        inconclusive.append("EMPTY_MINT")
    if census_cohort_mixed:
        inconclusive.append("MIXED_CENSUS_COHORT")
    if obs_cohort_mixed:
        inconclusive.append("MIXED_OBSERVATION_COHORT")
    if census_dataset_mixed:
        inconclusive.append("MIXED_CENSUS_DATASET")
    if obs_dataset_mixed:
        inconclusive.append("MIXED_OBSERVATION_DATASET")
    if census_session_mixed:
        inconclusive.append("MIXED_CENSUS_SESSION")
    if obs_session_mixed:
        inconclusive.append("MIXED_OBSERVATION_SESSION")
    if (
        census_cohort
        and obs_cohort
        and census_cohort != obs_cohort
    ):
        inconclusive.append("CENSUS_OBSERVATION_COHORT_MISMATCH")
    if (
        census_dataset
        and obs_dataset
        and census_dataset != obs_dataset
    ):
        inconclusive.append("CENSUS_OBSERVATION_DATASET_MISMATCH")
    if (
        census_session
        and obs_session
        and census_session != obs_session
    ):
        inconclusive.append("CENSUS_OBSERVATION_SESSION_MISMATCH")
    if value_kind_mismatch:
        inconclusive.append("VALUE_KIND_MISMATCH")
    if eligible_missing_from_observations:
        inconclusive.append("CENSUS_MINT_MISSING_FROM_OBSERVATIONS")
    if observation_mint_missing_from_census:
        inconclusive.append(OBSERVATION_MINT_MISSING_FROM_CENSUS)

    feature_rows = _omnibus_rows(members, spec) if not inconclusive else []
    if not inconclusive:
        for row in feature_rows:
            if row.get("abs_smd") is None:
                inconclusive.append("FEATURE_SMD_UNDEFINED")
                break
    observed_max = _max_abs_smd(feature_rows) if not inconclusive else None
    permutation_count = int(spec["permutation_count"])
    perm_hits = 0
    permutation_p: float | None = None
    if not inconclusive and observed_max is not None:
        labels = [str(member["group"]) for member in members]
        for _ in range(permutation_count):
            shuffled = labels[:]
            rng.shuffle(shuffled)
            perm_rows = _omnibus_rows(_relabel(members, shuffled), spec)
            perm_max = _max_abs_smd(perm_rows)
            if perm_max is not None and perm_max >= observed_max:
                perm_hits += 1
        permutation_p = (1 + perm_hits) / (1 + permutation_count)

    overlap_warning = False
    if not inconclusive:
        for row in feature_rows:
            if row.get("role") == "continuous" and row.get("iqr_overlap") is False:
                overlap_warning = True

    smd_threshold = float(spec["smd_threshold"])
    p_threshold = float(spec["permutation_p_threshold"])
    if inconclusive:
        terminal = INCONCLUSIVE
    elif (
        observed_max is not None
        and observed_max >= smd_threshold
        and permutation_p is not None
        and permutation_p <= p_threshold
    ):
        terminal = SHIFT_DETECTED
    else:
        terminal = SHIFT_NOT_DETECTED

    warnings = ["SUPPORT_OVERLAP_WARNING"] if overlap_warning else []
    corpus = spec.get("canonical_corpus") if isinstance(spec.get("canonical_corpus"), Mapping) else {}
    frozen_session = str(corpus.get("scientific_context_session") or "")
    census_sha = (
        binding.census_sha256 if binding is not None else _sha256_file(census_path)
    )
    observations_sha = (
        binding.observations_sha256
        if binding is not None
        else _sha256_file(observations_path)
    )
    canonical = population_scope == SCOPE_CANONICAL
    spec_pin_match = binding is not None and _spec_pins_match_binding(spec, binding)
    atomic_terminal = f"{terminal}|{population_scope}"
    receipt = {
        "schema": "smial.hfic-censoring-ignorability-diagnostic-receipt",
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "capability_id": CAP_HFIC_CENSORING_IGNORABILITY_DIAGNOSTIC,
        "terminal": atomic_terminal,
        "scientific_terminal": terminal,
        "terminal_with_scope": atomic_terminal,
        "terminal_population_scope": population_scope,
        "input_mode": input_mode,
        "corpus_id": (
            binding.dataset_id if canonical and binding is not None else None
        ),
        "cohort_id": (
            binding.cohort_id if canonical and binding is not None else None
        ),
        "release_id": binding.release_id if binding is not None else None,
        "dataset_manifest_id": (
            binding.dataset_manifest_id if binding is not None else None
        ),
        "scientific_context_session": (
            frozen_session if canonical and spec_pin_match else None
        ),
        "input_census_cohort_id": census_cohort,
        "input_observations_cohort_id": obs_cohort,
        "ignorability_status": IGNORABILITY_UNPROVEN,
        "identification_status": IDENTIFICATION_UNPROVEN,
        "complete_case_random_sample_certified": False,
        "complete_case_random_sample_status": RANDOM_SAMPLE_UNPROVEN,
        "counts": counts,
        "comparable_x_subset_n": comparable_n,
        "unresolved_anchor_n": len(unresolved),
        "unresolved_anchor_class": ANCHOR_UNRESOLVED if unresolved else None,
        "admitted_coverage": [
            {
                "coverage_class": item["coverage_class"],
                "authoritative_anchor_present": item["authoritative_anchor_present"],
                "x300_block_a_present": item["x300_block_a_present"],
            }
            for item in admitted_coverage
        ],
        "y_point_rows_present_unread": y_unread,
        "allowed_point_id": allowed_point_id,
        "coverage": coverage,
        "block_a_features": [
            {
                "feature_id": row["feature_id"],
                "role": row["role"],
                "n_observed": row["n_observed"],
                "n_censored_late": row["n_censored_late"],
                "smd": row["smd"] if row["smd"] is None or math.isfinite(row["smd"]) else "inf",
                "abs_smd": (
                    row["abs_smd"]
                    if row["abs_smd"] is None or math.isfinite(float(row["abs_smd"]))
                    else "inf"
                ),
                "variance_ratio": row.get("variance_ratio"),
                "iqr_overlap": row.get("iqr_overlap"),
            }
            for row in feature_rows
        ],
        "observed_max_abs_smd": (
            observed_max
            if observed_max is None or math.isfinite(observed_max)
            else "inf"
        ),
        "permutation_count": permutation_count,
        "permutation_seed": str(spec["permutation_seed"]),
        "permutation_hits": perm_hits if permutation_p is not None else None,
        "permutation_p": permutation_p,
        "smd_threshold": smd_threshold,
        "permutation_p_threshold": p_threshold,
        "inconclusive_reasons": inconclusive,
        "warnings": warnings,
        "census_sha256": census_sha,
        "observations_sha256": observations_sha,
        "spec_sha256": canonical_sha256(spec),
        "spec_file_sha256": FROZEN_SPEC_SHA256,
        "provider_requests": 0,
        "credential_reads": 0,
        "non_claims": list(NON_CLAIMS),
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
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
        raise CensoringDiagnosticError("DIAGNOSTIC_SPEC_PATH_UNSAFE")
    if _canonical_spec_relative(spec_relative) != SPEC_RELATIVE:
        raise CensoringDiagnosticError("FROZEN_SPEC_PATH_REQUIRED")
    if isinstance(data_root_relative, str) and data_root_relative:
        if isinstance(census_relative, str) or isinstance(observations_relative, str):
            raise CensoringDiagnosticError(CANONICAL_MODE_EXPLICIT_PATH_CONFLICT)
        if _unsafe(data_root_relative):
            raise CensoringDiagnosticError("CAPABILITY_PATH_UNSAFE")
        receipt = run_censoring_ignorability_diagnostic(
            root=root,
            data_root=root / data_root_relative,
            spec_relative=spec_relative,
        )
    else:
        if not isinstance(census_relative, str) or not isinstance(observations_relative, str):
            raise CensoringDiagnosticError(EXPLICIT_RELEASE_PATHS_REQUIRED)
        if _unsafe(census_relative) or _unsafe(observations_relative):
            raise CensoringDiagnosticError("CAPABILITY_PATH_UNSAFE")
        receipt = run_censoring_ignorability_diagnostic(
            root=root,
            census_path=root / census_relative,
            observations_path=root / observations_relative,
            spec_relative=spec_relative,
        )
    atomic = str(receipt["terminal_with_scope"])
    return {
        "status": "COMPLETE",
        "blocker": "NONE",
        "terminal": atomic,
        "result": atomic,
        "terminal_population_scope": receipt["terminal_population_scope"],
        "scientific_terminal": receipt["scientific_terminal"],
        "provider_api_rpc_wss_calls": 0,
        "credential_reads": 0,
        "receipt": receipt,
    }
