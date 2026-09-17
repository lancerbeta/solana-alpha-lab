"""Synthetic-only proofs for the HFIC censoring ignorability diagnostic."""

from __future__ import annotations

import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.contracts.schema_v1 import DatasetManifest
from solana_alpha_lab.factory.capabilities import (
    CAPABILITY_ROUTER,
    CapabilityError,
    execute_capability,
)
from solana_alpha_lab.factory import hfic_censoring_ignorability_diagnostic as censoring_mod
from solana_alpha_lab.factory.hfic_censoring_ignorability_diagnostic import (
    ADMITTED_NOT_X_ELIGIBLE,
    ANCHOR_UNRESOLVED,
    CANONICAL_CENSUS_HASH_MISMATCH,
    CANONICAL_CENSUS_IDENTITY_INVALID,
    CANONICAL_COHORT_ABSENT,
    CANONICAL_DATA_ROOT_OR_EXPLICIT_PATHS_REQUIRED,
    CANONICAL_HASH_PIN_MISSING,
    CANONICAL_INPUT_MODE,
    CANONICAL_LOGICAL_DATASET_MISMATCH,
    CANONICAL_MODE_EXPLICIT_PATH_CONFLICT,
    CANONICAL_OBSERVATIONS_IDENTITY_INVALID,
    CANONICAL_PARTITION_HASH_MISMATCH,
    CANONICAL_PARTITION_LOCATION_MISMATCH,
    CANONICAL_RELEASE_MISMATCH,
    CAP_HFIC_CENSORING_IGNORABILITY_DIAGNOSTIC,
    EXPLICIT_PATH_INPUT_MODE,
    FROZEN_SPEC_SHA256,
    IGNORABILITY_UNPROVEN,
    INCONCLUSIVE,
    RANDOM_SAMPLE_UNPROVEN,
    SCOPE_CANONICAL,
    SCOPE_NONCANONICAL,
    OBSERVATION_MINT_MISSING_FROM_CENSUS,
    RECEIPT_SCHEMA_VERSION,
    SHIFT_DETECTED,
    SHIFT_NOT_DETECTED,
    Y_POINT_READ,
    CensoringDiagnosticError,
    bind_canonical_censoring_inputs,
    _proportion_smd,
    _run_with_verified_binding,
    load_diagnostic_spec,
    reset_block_a_typed_read_probe,
    run_censoring_ignorability_diagnostic,
)
from solana_alpha_lab.factory.hfic_preflight import assert_capability_registry_v2_superset
from solana_alpha_lab.factory.live_cohort_source_bundle import (
    CENSUS_RELEASE_SCHEMA,
    OBS_RELEASE_SCHEMA,
    sha256_file_streaming,
)
from solana_alpha_lab.storage.manifests import (
    build_partition_manifest,
    canonical_manifest_bytes,
    compute_dataset_manifest_id,
)

CLI = ROOT / "scripts" / "hypothesis_forge.py"
SPEC = ROOT / "configs" / "hfic_censoring_ignorability_diagnostic_v1.yaml"
PINNED_PRODUCTION_CLOSURE = (
    ROOT
    / "docs"
    / "evidence"
    / "hfic_censoring_diagnostic_scope_repair"
    / "a1_pinned_production_closure_v1.json"
)
FROZEN_DATASET = "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001"
FROZEN_COHORT = "REL-20260902T111900Z-20260909T111900Z"
FROZEN_RELEASE = "633a57088a5eb16dcc75a56aa2eb2521bbc76d1874aeb75aceb1ecc795bf1154"

LIQUIDITY = "FIELD-LIQUIDITY-USD-001"
MCAP = "FIELD-MARKET-CAP-USD-001"
PRICE = "FIELD-USD-PRICE-001"
HOLDERS = "FIELD-HOLDER-COUNT-001"
LAUNCHPAD = "FIELD-LAUNCHPAD-001"
POOL_CREATED = "FIELD-FIRST-POOL-CREATED-AT-001"


def _census_row(**overrides: str | None) -> dict[str, str | None]:
    row = {name: None for name in CENSUS_RELEASE_SCHEMA.names}
    row.update(overrides)
    return row


def _obs_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {name: None for name in OBS_RELEASE_SCHEMA.names}
    row["confirmatory_reuse_forbidden"] = True
    row["release_id"] = "REL-SYN"
    row["cohort_id"] = "REL-SYN"
    row["point_id"] = "X300"
    row["state"] = "OBSERVED"
    row["primitive_id"] = "PRIM-SYN-001"
    row.update(overrides)
    return row


def _write_parquet(path: Path, rows: list[dict[str, object]], schema: pa.Schema) -> None:
    table = pa.Table.from_pylist(rows, schema=schema)
    pq.write_table(table, path)


def _member(
    mint: str,
    *,
    candidate: str,
    denom: str,
    anchor: str | None = None,
    cohort_id: str = "REL-SYN",
    release_id: str = "REL-SYN",
) -> dict[str, str | None]:
    return _census_row(
        mint=mint,
        candidate_state=candidate,
        denominator_state=denom,
        authoritative_anchor=anchor,
        discovery_first_reliable_available_at="2026-09-02T12:00:00Z",
        inclusion_probability="0.0425",
        cohort_id=cohort_id,
        release_id=release_id,
    )


def _identity_obs(mint: str) -> dict[str, object]:
    return _obs_row(
        mint=mint,
        field_id="FIELD-TOKEN-MINT-001",
        typed_value=mint,
        state="OBSERVED",
        point_id="X300",
        value_kind="TOKEN_MINT",
    )


def _x300(
    mint: str,
    field_id: str,
    value: object,
    *,
    state: str = "OBSERVED",
    point_id: str = "X300",
    value_kind: str = "DECIMAL",
) -> dict[str, object]:
    return _obs_row(
        mint=mint,
        field_id=field_id,
        typed_value=str(value),
        state=state,
        point_id=point_id,
        value_kind=value_kind,
    )


def _block_a_obs(
    mint: str,
    *,
    liquidity: float,
    mcap: float = 100.0,
    price: float = 0.01,
    holders: float = 50.0,
    launchpad: str = "pump",
    pool_created: str = "2026-09-02T11:00:00Z",
) -> list[dict[str, object]]:
    return [
        _x300(mint, LIQUIDITY, liquidity),
        _x300(mint, MCAP, mcap),
        _x300(mint, PRICE, price),
        _x300(mint, HOLDERS, holders),
        _x300(mint, LAUNCHPAD, launchpad, value_kind="TEXT"),
        _x300(mint, POOL_CREATED, pool_created, value_kind="TIMESTAMP"),
    ]


def _balanced_fixture(
    directory: Path,
    *,
    shift_liquidity: bool,
    holder_coverage: bool = True,
    include_y: bool = False,
    latency_shift: bool = False,
    cohort_id: str = "REL-SYN",
    release_id: str = "REL-SYN",
) -> tuple[Path, Path]:
    census: list[dict[str, object]] = []
    observations: list[dict[str, object]] = []
    observed_n = 24
    censored_n = 24
    for index in range(observed_n):
        mint = f"obs{index:03d}"
        census.append(_member(mint, candidate="X_ELIGIBLE", denom="observed", anchor="ANCHOR"))
        liquidity = 400.0 if shift_liquidity else 100.0 + (index % 3)
        pool = "2026-09-02T11:00:00Z"
        observations.extend(_block_a_obs(mint, liquidity=liquidity, pool_created=pool))
        if include_y:
            observations.append(
                _x300(mint, LIQUIDITY, 10**12, point_id="Y900")
            )
    for index in range(censored_n):
        mint = f"cen{index:03d}"
        census.append(
            _member(mint, candidate="X_ELIGIBLE", denom="censored_late", anchor="ANCHOR")
        )
        liquidity = 8.0 if shift_liquidity else 100.0 + (index % 3)
        pool = "2026-09-08T11:00:00Z" if latency_shift else "2026-09-02T11:00:00Z"
        rows = _block_a_obs(mint, liquidity=liquidity, pool_created=pool)
        if not holder_coverage and index >= 2:
            rows = [row for row in rows if row["field_id"] != HOLDERS]
        observations.extend(rows)
        if include_y:
            observations.append(_x300(mint, LIQUIDITY, 10**12, point_id="Y86400"))
    for index in range(5):
        mint = f"adm{index:03d}"
        census.append(_member(mint, candidate="ADMITTED", denom="censored_late"))
        observations.append(
            _obs_row(
                mint=mint,
                field_id="FIELD-TOKEN-MINT-001",
                typed_value=mint,
                state="OBSERVED",
                point_id="X300",
                value_kind="TOKEN_MINT",
            )
        )
    for index in range(4):
        census.append(
            _member(f"inel{index:03d}", candidate="X_POPULATION_INELIGIBLE", denom="excluded")
        )
    for row in census:
        row["cohort_id"] = cohort_id
        row["release_id"] = release_id
    for row in observations:
        row["cohort_id"] = cohort_id
        row["release_id"] = release_id
    census_path = directory / "census.parquet"
    observations_path = directory / "observations.parquet"
    _write_parquet(census_path, census, CENSUS_RELEASE_SCHEMA)
    _write_parquet(observations_path, observations, OBS_RELEASE_SCHEMA)
    return census_path, observations_path


def _atomic(scientific: str) -> str:
    return f"{scientific}|{SCOPE_NONCANONICAL}"


def _run(census: Path, observations: Path) -> dict:
    return run_censoring_ignorability_diagnostic(
        root=ROOT,
        census_path=census,
        observations_path=observations,
    )


def _run_with_spec(
    directory: Path,
    census: Path,
    observations: Path,
    spec: dict,
) -> dict:
    configs = directory / "configs"
    configs.mkdir(exist_ok=True)
    (configs / SPEC.name).write_text(
        yaml.safe_dump(spec, sort_keys=False),
        encoding="utf-8",
    )
    return run_censoring_ignorability_diagnostic(
        root=directory,
        census_path=census,
        observations_path=observations,
        spec_relative=f"configs/{SPEC.name}",
    )


def _partition_rels(cohort_id: str, release_id: str) -> tuple[str, str]:
    short = release_id[:16]
    census_rel = (
        "datasets/partitions/date=2026-09-13/"
        f"PARTITION-LIVE-COHORT-{cohort_id}-CENSUS-{short}.parquet"
    )
    obs_rel = (
        "datasets/partitions/date=2026-09-13/"
        f"PARTITION-LIVE-COHORT-{cohort_id}-OBS-{short}.parquet"
    )
    return census_rel, obs_rel


def _publish_dataset(
    data_root: Path,
    *,
    dataset_id: str,
    dataset_version: str,
    census_rel: str,
    obs_rel: str,
    census_sha: str,
    obs_sha: str,
    census_n: int,
    obs_n: int,
    cohort_id: str,
) -> str:
    created = datetime(2026, 9, 13, 11, 57, 49, tzinfo=UTC)
    manifest_id = compute_dataset_manifest_id(dataset_id, dataset_version)
    dataset = DatasetManifest(
        dataset_manifest_id=manifest_id,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        schema_id="SCHEMA-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
        schema_sha256="ab" * 32,
        dataset_fingerprint="cd" * 32,
        generation_task_id="LIVE_COHORT_DISCOVERY_RELEASE_SERIES_V1",
        generation_run_id=f"import-{manifest_id[-16:]}",
        validation_receipt_sha256="ef" * 32,
        first_reliable_available_at=created,
        created_at=created,
        content_sha256="11" * 32,
    )
    census_part = build_partition_manifest(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        partition_id=f"PARTITION-LIVE-COHORT-{cohort_id}-CENSUS",
        logical_location=census_rel,
        file_sha256=census_sha,
        content_sha256=census_sha,
        row_count=census_n,
        first_reliable_available_at=created,
        created_at=created,
        min_event_time=created,
        max_event_time=created,
        min_available_to_strategy_at=created,
        max_available_to_strategy_at=created,
    )
    obs_part = build_partition_manifest(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        partition_id=f"PARTITION-LIVE-COHORT-{cohort_id}-OBS",
        logical_location=obs_rel,
        file_sha256=obs_sha,
        content_sha256=obs_sha,
        row_count=obs_n,
        first_reliable_available_at=created,
        created_at=created,
        min_event_time=created,
        max_event_time=created,
        min_available_to_strategy_at=created,
        max_available_to_strategy_at=created,
    )
    manifests = data_root / "datasets" / "manifests"
    partitions = manifests / "partitions"
    partitions.mkdir(parents=True, exist_ok=True)
    (manifests / f"{manifest_id}.json").write_bytes(canonical_manifest_bytes(dataset))
    (partitions / f"{census_part.partition_manifest_id}.json").write_bytes(
        canonical_manifest_bytes(census_part)
    )
    (partitions / f"{obs_part.partition_manifest_id}.json").write_bytes(
        canonical_manifest_bytes(obs_part)
    )
    return manifest_id


def _write_lineage(
    data_root: Path,
    *,
    dataset_id: str,
    current_mid: str,
    cohorts: list[dict[str, object]],
) -> None:
    path = data_root / "datasets" / "live_lifecycle_corpus" / "lineage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "corpus_dataset_id": dataset_id,
        "current_corpus_version": len(cohorts),
        "current_dataset_manifest_id": current_mid,
        "cohorts": cohorts,
        "versions": [
            {
                "corpus_version": item.get("corpus_version"),
                "dataset_manifest_id": item.get("dataset_manifest_id"),
                "cohort_id": item.get("cohort_id"),
            }
            for item in cohorts
        ],
    }
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def _install_canonical_corpus(
    data_root: Path,
    *,
    dataset_id: str = FROZEN_DATASET,
    cohort_id: str = FROZEN_COHORT,
    release_id: str = FROZEN_RELEASE,
    dataset_version: str = "corpus-v1-REL-20260902T111900Z-20260909T111900Z",
) -> dict[str, str]:
    staging = data_root / "_fixture"
    staging.mkdir(parents=True, exist_ok=True)
    census_src, obs_src = _balanced_fixture(
        staging,
        shift_liquidity=False,
        cohort_id=cohort_id,
        release_id=release_id,
    )
    census_rel, obs_rel = _partition_rels(cohort_id, release_id)
    census_path = data_root / census_rel
    obs_path = data_root / obs_rel
    census_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(census_src, census_path)
    shutil.copyfile(obs_src, obs_path)
    census_sha = sha256_file_streaming(census_path)
    obs_sha = sha256_file_streaming(obs_path)
    census_n = pq.read_table(census_path).num_rows
    obs_n = pq.read_table(obs_path).num_rows
    manifest_id = _publish_dataset(
        data_root,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        census_rel=census_rel,
        obs_rel=obs_rel,
        census_sha=census_sha,
        obs_sha=obs_sha,
        census_n=census_n,
        obs_n=obs_n,
        cohort_id=cohort_id,
    )
    _write_lineage(
        data_root,
        dataset_id=dataset_id,
        current_mid=manifest_id,
        cohorts=[
            {
                "cohort_id": cohort_id,
                "release_id": release_id,
                "census_rel": census_rel,
                "obs_rel": obs_rel,
                "census_sha256": census_sha,
                "observations_sha256": obs_sha,
                "corpus_version": 1,
                "dataset_manifest_id": manifest_id,
                "dataset_version": dataset_version,
            }
        ],
    )
    return {
        "census_sha256": census_sha,
        "observations_sha256": obs_sha,
        "dataset_manifest_id": manifest_id,
        "census_rel": census_rel,
        "obs_rel": obs_rel,
        "census_path": str(census_path),
        "obs_path": str(obs_path),
    }


def _pins_from_installed(installed: dict[str, str]) -> dict[str, str]:
    return {
        "dataset_id": FROZEN_DATASET,
        "cohort_id": FROZEN_COHORT,
        "release_id": FROZEN_RELEASE,
        "census_sha256": installed["census_sha256"],
        "observations_sha256": installed["observations_sha256"],
    }


class HficCensoringIgnorabilityDiagnosticTests(unittest.TestCase):
    def test_frozen_spec_denies_y_and_keeps_block_b_out_of_omnibus(self) -> None:
        spec = load_diagnostic_spec(ROOT)
        self.assertEqual(spec["allowed_point_id"], "X300")
        self.assertEqual(spec["denominator"]["comparable_x_rule"], "census.candidate_state == X_ELIGIBLE")
        self.assertEqual(spec["denominator"]["comparable_x_subset"], 475)
        fields = [item["field_id"] for item in spec["block_a_omnibus"]]
        self.assertNotIn(POOL_CREATED, fields)
        self.assertEqual(
            spec["block_b_descriptive_not_omnibus"][0]["field_id"],
            POOL_CREATED,
        )
        self.assertEqual(spec["categorical_smd"]["statistic"], "pairwise_proportion")
        self.assertEqual(spec["variance_epsilon"], 1.0e-18)

    def test_shift_detected_does_not_claim_ignorability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=True)
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(SHIFT_DETECTED))
        self.assertEqual(receipt["scientific_terminal"], SHIFT_DETECTED)
        self.assertEqual(receipt["ignorability_status"], IGNORABILITY_UNPROVEN)
        self.assertEqual(receipt["complete_case_random_sample_status"], RANDOM_SAMPLE_UNPROVEN)
        self.assertNotIn("complete_case_not_random_sample_of_x_eligible", receipt)
        self.assertEqual(receipt["counts"]["x_eligible_observed"], 24)
        self.assertEqual(receipt["counts"]["x_eligible_censored_late"], 24)
        self.assertEqual(receipt["identification_status"], "IDENTIFICATION_UNPROVEN")
        self.assertFalse(receipt["complete_case_random_sample_certified"])
        self.assertEqual(receipt["unresolved_anchor_n"], 5)
        self.assertEqual(receipt["unresolved_anchor_class"], ANCHOR_UNRESOLVED)
        self.assertEqual(receipt["terminal_population_scope"], SCOPE_NONCANONICAL)
        self.assertEqual(
            receipt["terminal_with_scope"],
            f"{SHIFT_DETECTED}|{SCOPE_NONCANONICAL}",
        )
        self.assertIsNone(receipt["corpus_id"])
        self.assertIsNone(receipt["cohort_id"])
        self.assertEqual(receipt["input_observations_cohort_id"], "REL-SYN")
        self.assertIn("NO_MAR", receipt["non_claims"])
        self.assertGreaterEqual(float(receipt["observed_max_abs_smd"]), 0.25)
        self.assertLessEqual(float(receipt["permutation_p"]), 0.05)

    def test_no_shift_is_not_mar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(SHIFT_NOT_DETECTED))
        self.assertEqual(receipt["scientific_terminal"], SHIFT_NOT_DETECTED)
        self.assertEqual(receipt["ignorability_status"], IGNORABILITY_UNPROVEN)
        self.assertEqual(receipt["identification_status"], "IDENTIFICATION_UNPROVEN")
        self.assertFalse(receipt["complete_case_random_sample_certified"])
        self.assertEqual(receipt["complete_case_random_sample_status"], RANDOM_SAMPLE_UNPROVEN)
        self.assertNotIn("complete_case_not_random_sample_of_x_eligible", receipt)
        self.assertEqual(receipt["terminal_population_scope"], SCOPE_NONCANONICAL)
        self.assertEqual(
            receipt["terminal_with_scope"],
            f"{SHIFT_NOT_DETECTED}|{SCOPE_NONCANONICAL}",
        )
        self.assertIsNone(receipt["corpus_id"])
        self.assertIsNone(receipt["cohort_id"])
        self.assertEqual(receipt["spec_file_sha256"], FROZEN_SPEC_SHA256)

    def test_mutated_spec_hash_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            census, observations = _balanced_fixture(directory, shift_liquidity=False)
            spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
            spec["denominator"]["comparable_x_subset"] = 48
            with self.assertRaises(CensoringDiagnosticError) as raised:
                _run_with_spec(directory, census, observations, spec)
            self.assertEqual(raised.exception.code, "FROZEN_SPEC_HASH_MISMATCH")

    def test_mutated_spec_cannot_self_declare_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            census, observations = _balanced_fixture(directory, shift_liquidity=False)
            spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
            spec["denominator"]["comparable_x_subset"] = 48
            spec["denominator"]["x_eligible_observed"] = 24
            spec["denominator"]["x_eligible_censored_late"] = 24
            spec["canonical_corpus"]["cohort_id"] = "REL-SYN"
            with self.assertRaises(CensoringDiagnosticError) as raised:
                _run_with_spec(directory, census, observations, spec)
            self.assertEqual(raised.exception.code, "FROZEN_SPEC_HASH_MISMATCH")

    def test_alternate_spec_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            configs = directory / "configs"
            configs.mkdir()
            shutil.copy2(SPEC, configs / "other.yaml")
            census, observations = _balanced_fixture(directory, shift_liquidity=False)
            with self.assertRaises(CensoringDiagnosticError) as raised:
                run_censoring_ignorability_diagnostic(
                    root=directory,
                    census_path=census,
                    observations_path=observations,
                    spec_relative="configs/other.yaml",
                )
            self.assertEqual(raised.exception.code, "FROZEN_SPEC_PATH_REQUIRED")

    def test_eligible_mint_missing_from_observations_is_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            rows = [
                row
                for row in pq.read_table(observations).to_pylist()
                if row.get("mint") != "obs000"
            ]
            _write_parquet(observations, rows, OBS_RELEASE_SCHEMA)
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(INCONCLUSIVE))
        self.assertIn(
            "CENSUS_MINT_MISSING_FROM_OBSERVATIONS",
            receipt["inconclusive_reasons"],
        )

    def test_census_row_count_is_not_discovered_in_obs_partition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal_population_scope"], SCOPE_NONCANONICAL)
        self.assertEqual(receipt["schema_version"], RECEIPT_SCHEMA_VERSION)
        self.assertEqual(receipt["counts"]["census_rows"], 57)
        self.assertEqual(receipt["counts"]["census_rows_total"], 57)
        self.assertEqual(receipt["counts"]["census_distinct_mints_total"], 57)
        self.assertEqual(receipt["counts"]["discovered_in_observation_partition"], 53)
        self.assertEqual(receipt["counts"]["diagnostic_population_census_rows"], 53)
        self.assertEqual(receipt["counts"]["diagnostic_population_distinct_mints"], 53)
        self.assertEqual(receipt["counts"]["out_of_scope_census_rows"], 4)
        self.assertEqual(receipt["counts"]["other_in_scope"], 0)
        self.assertEqual(receipt["counts"]["other"], 0)
        self.assertEqual(receipt["counts"]["x_population_ineligible"], 0)
        self.assertIsNone(receipt["corpus_id"])

    def test_mixed_observation_cohort_is_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            rows = pq.read_table(observations).to_pylist()
            rows[0]["cohort_id"] = "REL-OTHER"
            _write_parquet(observations, rows, OBS_RELEASE_SCHEMA)
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(INCONCLUSIVE))
        self.assertIn("MIXED_OBSERVATION_COHORT", receipt["inconclusive_reasons"])

    def test_mixed_cohort_on_unread_y_row_is_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(
                Path(tmp),
                shift_liquidity=False,
                include_y=True,
            )
            rows = pq.read_table(observations).to_pylist()
            for row in rows:
                if str(row.get("point_id") or "").startswith("Y"):
                    row["cohort_id"] = "REL-OTHER"
                    break
            _write_parquet(observations, rows, OBS_RELEASE_SCHEMA)
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(INCONCLUSIVE))
        self.assertIn("MIXED_OBSERVATION_COHORT", receipt["inconclusive_reasons"])

    def test_latency_tautology_stays_out_of_omnibus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(
                Path(tmp),
                shift_liquidity=False,
                latency_shift=True,
            )
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(SHIFT_NOT_DETECTED))
        feature_ids = [item["feature_id"] for item in receipt["block_a_features"]]
        self.assertNotIn("first_pool_created_at", feature_ids)

    def test_y_point_values_are_not_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            without_y = base / "plain"
            with_y = base / "poison"
            without_y.mkdir()
            with_y.mkdir()
            census_a, obs_a = _balanced_fixture(without_y, shift_liquidity=True)
            census_b, obs_b = _balanced_fixture(
                with_y,
                shift_liquidity=True,
                include_y=True,
            )
            plain = _run(census_a, obs_a)
            poisoned = _run(census_b, obs_b)
        self.assertEqual(plain["terminal"], poisoned["terminal"])
        self.assertEqual(plain["observed_max_abs_smd"], poisoned["observed_max_abs_smd"])
        self.assertEqual(plain["permutation_p"], poisoned["permutation_p"])
        self.assertGreater(poisoned["y_point_rows_present_unread"], 0)
        self.assertEqual(plain["y_point_rows_present_unread"], 0)

    def test_coverage_floor_is_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(
                Path(tmp),
                shift_liquidity=True,
                holder_coverage=False,
            )
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(INCONCLUSIVE))
        self.assertIn("COVERAGE_FLOOR_BREACH", receipt["inconclusive_reasons"])

    def test_unknown_census_state_is_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            rows = pq.read_table(census).to_pylist()
            rows.append(
                _member("weird000", candidate="WEIRD", denom="observed", anchor="ANCHOR")
            )
            _write_parquet(census, rows, CENSUS_RELEASE_SCHEMA)
            obs_rows = pq.read_table(observations).to_pylist()
            obs_rows.append(_identity_obs("weird000"))
            _write_parquet(observations, obs_rows, OBS_RELEASE_SCHEMA)
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(INCONCLUSIVE))
        self.assertIn("UNKNOWN_CENSUS_STATE", receipt["inconclusive_reasons"])
        self.assertEqual(receipt["counts"]["other_in_scope"], 1)
        self.assertEqual(receipt["counts"]["other"], 1)
        self.assertEqual(receipt["identification_status"], "IDENTIFICATION_UNPROVEN")

    def test_duplicate_comparable_mint_is_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            rows = pq.read_table(census).to_pylist()
            rows.append(_member("obs000", candidate="X_ELIGIBLE", denom="observed", anchor="ANCHOR"))
            _write_parquet(census, rows, CENSUS_RELEASE_SCHEMA)
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(INCONCLUSIVE))
        self.assertIn("DUPLICATE_COMPARABLE_MINT", receipt["inconclusive_reasons"])

    def test_duplicate_x300_observation_is_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            rows = pq.read_table(observations).to_pylist()
            rows.append(_x300("obs000", LIQUIDITY, 999.0))
            _write_parquet(observations, rows, OBS_RELEASE_SCHEMA)
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(INCONCLUSIVE))
        self.assertIn("DUPLICATE_X300_OBSERVATION", receipt["inconclusive_reasons"])
        self.assertEqual(receipt["observed_max_abs_smd"], None)

    def test_duplicate_non_block_a_x300_is_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            rows = pq.read_table(observations).to_pylist()
            rows.append(_x300("obs000", POOL_CREATED, "2026-09-02T11:00:00Z", value_kind="TIMESTAMP"))
            _write_parquet(observations, rows, OBS_RELEASE_SCHEMA)
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(INCONCLUSIVE))
        self.assertIn("DUPLICATE_X300_OBSERVATION", receipt["inconclusive_reasons"])
        self.assertEqual(receipt["observed_max_abs_smd"], None)

    def test_admitted_with_x300_is_not_anchor_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            rows = pq.read_table(observations).to_pylist()
            rows.extend(_block_a_obs("adm000", liquidity=12.0))
            _write_parquet(observations, rows, OBS_RELEASE_SCHEMA)
            receipt = _run(census, observations)
        classes = {item["coverage_class"] for item in receipt["admitted_coverage"]}
        self.assertIn(ADMITTED_NOT_X_ELIGIBLE, classes)
        self.assertIn(ANCHOR_UNRESOLVED, classes)
        self.assertEqual(receipt["unresolved_anchor_n"], 4)
        self.assertEqual(receipt["counts"]["admitted_censored_late_no_x300"], 4)

    def test_seeded_repeat_is_identical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=True)
            first = _run(census, observations)
            second = _run(census, observations)
        self.assertEqual(first["receipt_sha256"], second["receipt_sha256"])
        self.assertEqual(first["permutation_p"], second["permutation_p"])

    def test_capability_budget_zero_and_explicit_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configs = root / "configs"
            configs.mkdir()
            shutil.copy2(SPEC, configs / SPEC.name)
            census, observations = _balanced_fixture(root, shift_liquidity=False)
            census.rename(root / "census.parquet")
            observations.rename(root / "observations.parquet")
            spec = {
                "capabilities": [CAP_HFIC_CENSORING_IGNORABILITY_DIAGNOSTIC],
                "evidence_budget": {"provider_api_rpc_wss_calls": 0},
                "parameters": {
                    "census_relative": "census.parquet",
                    "observations_relative": "observations.parquet",
                    "spec_relative": f"configs/{SPEC.name}",
                },
            }
            derived = execute_capability(spec, root=root, authority_phrase=None)
            self.assertEqual(
                derived["terminal"],
                f"{SHIFT_NOT_DETECTED}|{SCOPE_NONCANONICAL}",
            )
            self.assertEqual(derived["result"], derived["terminal"])
            self.assertEqual(derived["scientific_terminal"], SHIFT_NOT_DETECTED)
            self.assertEqual(derived["terminal_population_scope"], SCOPE_NONCANONICAL)
            self.assertEqual(derived["provider_api_rpc_wss_calls"], 0)
            with self.assertRaises(CapabilityError) as raised:
                execute_capability(
                    {
                        **spec,
                        "evidence_budget": {"provider_api_rpc_wss_calls": 1},
                    },
                    root=root,
                )
            self.assertEqual(str(raised.exception), "PROVIDER_BUDGET_NOT_ZERO")
            with self.assertRaises(CapabilityError) as missing:
                execute_capability(
                    {
                        "capabilities": [CAP_HFIC_CENSORING_IGNORABILITY_DIAGNOSTIC],
                        "evidence_budget": {"provider_api_rpc_wss_calls": 0},
                        "parameters": {},
                    },
                    root=root,
                )
            self.assertEqual(str(missing.exception), "EXPLICIT_RELEASE_PATHS_REQUIRED")
        self.assertIn(
            CAP_HFIC_CENSORING_IGNORABILITY_DIAGNOSTIC,
            CAPABILITY_ROUTER,
        )

    def test_v2_registry_lists_the_new_capability(self) -> None:
        proof = assert_capability_registry_v2_superset(ROOT)
        self.assertIn(
            CAP_HFIC_CENSORING_IGNORABILITY_DIAGNOSTIC,
            proof["intentional_v2_additions"],
        )
        schema = json.loads(
            (
                ROOT / "catalog/schemas/experiment_capability_descriptor.schema.json"
            ).read_text(encoding="utf-8")
        )
        registry = yaml.safe_load(
            (ROOT / "configs/experiment_capability_registry_v2.yaml").read_text(
                encoding="utf-8"
            )
        )
        import jsonschema

        descriptors = {item["capability_id"]: item for item in registry["capabilities"]}
        jsonschema.validate(
            descriptors[CAP_HFIC_CENSORING_IGNORABILITY_DIAGNOSTIC],
            schema,
        )
        self.assertEqual(
            descriptors[CAP_HFIC_CENSORING_IGNORABILITY_DIAGNOSTIC]["effect_class"],
            "OFFLINE_READ_ONLY",
        )
        self.assertEqual(
            descriptors[CAP_HFIC_CENSORING_IGNORABILITY_DIAGNOSTIC]["determinism_class"],
            "SEEDED_DETERMINISTIC",
        )
        self.assertEqual(
            descriptors[CAP_HFIC_CENSORING_IGNORABILITY_DIAGNOSTIC]["promotion_authority"],
            "NONE",
        )
        self.assertEqual(
            descriptors[CAP_HFIC_CENSORING_IGNORABILITY_DIAGNOSTIC]["max_provider_calls"],
            0,
        )

    def test_cli_requires_explicit_parquet_and_emits_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            env = dict(os.environ)
            env["PYTHONPATH"] = str(SRC)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(CLI),
                    "censoring-ignorability-diagnostic",
                    "--census",
                    str(census),
                    "--observations",
                    str(observations),
                ],
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["terminal"], _atomic(SHIFT_NOT_DETECTED))
            self.assertEqual(payload["scientific_terminal"], SHIFT_NOT_DETECTED)
            self.assertNotIn("C:\\\\", completed.stdout.replace("/", "\\"))
            missing = subprocess.run(
                [sys.executable, "-B", str(CLI), "censoring-ignorability-diagnostic"],
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn(CANONICAL_DATA_ROOT_OR_EXPLICIT_PATHS_REQUIRED, missing.stderr)

    def test_y_point_as_allowed_point_is_protocol_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configs = root / "configs"
            configs.mkdir()
            spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
            spec["allowed_point_id"] = "Y900"
            mutated = configs / SPEC.name
            mutated.write_text(
                yaml.safe_dump(spec, sort_keys=False),
                encoding="utf-8",
            )
            with self.assertRaises(CensoringDiagnosticError) as loaded:
                load_diagnostic_spec(root, f"configs/{SPEC.name}")
            self.assertEqual(loaded.exception.code, Y_POINT_READ)
            census, observations = _balanced_fixture(root, shift_liquidity=False)
            with self.assertRaises(CensoringDiagnosticError) as raised:
                run_censoring_ignorability_diagnostic(
                    root=root,
                    census_path=census,
                    observations_path=observations,
                    spec_relative=f"configs/{SPEC.name}",
                )
            self.assertEqual(raised.exception.code, "FROZEN_SPEC_HASH_MISMATCH")

    def test_categorical_smd_formula_is_frozen(self) -> None:
        observed = _proportion_smd(24, 24, 24, 0, variance_epsilon=1e-18)
        self.assertEqual(observed, 2.0)

    def test_wrong_block_a_value_kind_is_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            rows = pq.read_table(observations).to_pylist()
            for row in rows:
                if row.get("field_id") == LIQUIDITY and row.get("mint") == "obs000":
                    row["value_kind"] = "TEXT"
                    break
            _write_parquet(observations, rows, OBS_RELEASE_SCHEMA)
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(INCONCLUSIVE))
        self.assertIn("VALUE_KIND_MISMATCH", receipt["inconclusive_reasons"])

    def test_mixed_observation_dataset_is_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            rows = pq.read_table(observations).to_pylist()
            schema = OBS_RELEASE_SCHEMA
            if "dataset_id" not in schema.names:
                schema = schema.append(pa.field("dataset_id", pa.string()))
            for index, row in enumerate(rows):
                row["dataset_id"] = "DS-A" if index == 0 else "DS-B"
            _write_parquet(observations, rows, schema)
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(INCONCLUSIVE))
        self.assertIn("MIXED_OBSERVATION_DATASET", receipt["inconclusive_reasons"])

    def test_excluded_x300_typed_sentinel_does_not_change_smd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            plain_dir = base / "plain"
            poison_dir = base / "poison"
            plain_dir.mkdir()
            poison_dir.mkdir()
            census_a, obs_a = _balanced_fixture(plain_dir, shift_liquidity=True)
            census_b, obs_b = _balanced_fixture(poison_dir, shift_liquidity=True)
            rows = pq.read_table(obs_b).to_pylist()
            for row in rows:
                if row.get("field_id") == POOL_CREATED:
                    row["typed_value"] = "9999-12-31T00:00:00Z"
            _write_parquet(obs_b, rows, OBS_RELEASE_SCHEMA)
            plain = _run(census_a, obs_a)
            poisoned = _run(census_b, obs_b)
        self.assertEqual(plain["scientific_terminal"], poisoned["scientific_terminal"])
        self.assertEqual(plain["observed_max_abs_smd"], poisoned["observed_max_abs_smd"])

    def test_explicit_path_stays_noncanonical_even_with_identity_columns(self) -> None:
        spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
        corpus = spec["canonical_corpus"]
        self.assertEqual(
            corpus["census_sha256"],
            "cfa7d8404dc5400c4e223c4d5303193ad2209f92cac3af2d61862e384ebfd5bf",
        )
        self.assertEqual(
            corpus["observations_sha256"],
            "7b26425c69cc95baf8a9e0b9ea506de1042b98b83d48a2dae07f5a33a7d66d7d",
        )
        self.assertEqual(corpus["release_id"], FROZEN_RELEASE)
        census_names = set(CENSUS_RELEASE_SCHEMA.names)
        obs_names = set(OBS_RELEASE_SCHEMA.names)
        self.assertNotIn("dataset_id", census_names)
        self.assertNotIn("scientific_context_session", census_names)
        self.assertNotIn("dataset_id", obs_names)
        self.assertNotIn("scientific_context_session", obs_names)
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(
                Path(tmp),
                shift_liquidity=False,
                cohort_id=FROZEN_COHORT,
                release_id=FROZEN_RELEASE,
            )
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal_population_scope"], SCOPE_NONCANONICAL)
        self.assertEqual(receipt["input_mode"], EXPLICIT_PATH_INPUT_MODE)
        self.assertIsNone(receipt["corpus_id"])


class CanonicalBindingGateTests(unittest.TestCase):
    def test_exact_binding_allows_canonical_x_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data_plane"
            installed = _install_canonical_corpus(data_root)
            reset_block_a_typed_read_probe()
            binding = bind_canonical_censoring_inputs(
                data_root, _pins_from_installed(installed)
            )
            self.assertEqual(binding.release_id, FROZEN_RELEASE)
            receipt = _run_with_verified_binding(
                root=ROOT,
                binding=binding,
            )
        self.assertGreater(censoring_mod.BLOCK_A_TYPED_READ_CALLS, 0)
        self.assertEqual(receipt["terminal_population_scope"], SCOPE_CANONICAL)
        self.assertEqual(receipt["input_mode"], CANONICAL_INPUT_MODE)
        self.assertEqual(receipt["corpus_id"], FROZEN_DATASET)
        self.assertEqual(receipt["cohort_id"], FROZEN_COHORT)
        self.assertEqual(receipt["release_id"], FROZEN_RELEASE)
        self.assertEqual(
            receipt["dataset_manifest_id"], installed["dataset_manifest_id"]
        )
        self.assertIsNone(receipt["scientific_context_session"])
        self.assertEqual(receipt["scientific_terminal"], SHIFT_NOT_DETECTED)

    def test_altered_file_bytes_fail_before_typed_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data_plane"
            installed = _install_canonical_corpus(data_root)
            pins = _pins_from_installed(installed)
            census_path = data_root / installed["census_rel"]
            census_path.write_bytes(census_path.read_bytes() + b"\x00")
            reset_block_a_typed_read_probe()
            with self.assertRaises(CensoringDiagnosticError) as raised:
                bind_canonical_censoring_inputs(data_root, pins)
            self.assertEqual(raised.exception.code, CANONICAL_CENSUS_HASH_MISMATCH)
            self.assertEqual(censoring_mod.BLOCK_A_TYPED_READ_CALLS, 0)

    def test_frozen_sha_mismatch_fails_before_typed_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data_plane"
            installed = _install_canonical_corpus(data_root)
            pins = _pins_from_installed(installed)
            pins["census_sha256"] = "aa" * 32
            reset_block_a_typed_read_probe()
            with self.assertRaises(CensoringDiagnosticError) as raised:
                bind_canonical_censoring_inputs(data_root, pins)
            self.assertEqual(raised.exception.code, CANONICAL_CENSUS_HASH_MISMATCH)
            self.assertEqual(censoring_mod.BLOCK_A_TYPED_READ_CALLS, 0)
            reset_block_a_typed_read_probe()
            with self.assertRaises(CensoringDiagnosticError) as public:
                run_censoring_ignorability_diagnostic(
                    root=ROOT, data_root=data_root
                )
            self.assertEqual(public.exception.code, CANONICAL_CENSUS_HASH_MISMATCH)
            self.assertEqual(censoring_mod.BLOCK_A_TYPED_READ_CALLS, 0)

    def test_wrong_release_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data_plane"
            installed = _install_canonical_corpus(data_root)
            pins = _pins_from_installed(installed)
            pins["release_id"] = "00" * 32
            with self.assertRaises(CensoringDiagnosticError) as raised:
                bind_canonical_censoring_inputs(data_root, pins)
            self.assertEqual(raised.exception.code, CANONICAL_RELEASE_MISMATCH)

    def test_wrong_cohort_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data_plane"
            installed = _install_canonical_corpus(data_root)
            pins = _pins_from_installed(installed)
            pins["cohort_id"] = "REL-OTHER-WINDOW"
            with self.assertRaises(CensoringDiagnosticError) as raised:
                bind_canonical_censoring_inputs(data_root, pins)
            self.assertEqual(raised.exception.code, CANONICAL_COHORT_ABSENT)

    def test_wrong_logical_dataset_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data_plane"
            installed = _install_canonical_corpus(data_root)
            pins = _pins_from_installed(installed)
            pins["dataset_id"] = "DATASET-OTHER-001"
            with self.assertRaises(CensoringDiagnosticError) as raised:
                bind_canonical_censoring_inputs(data_root, pins)
            self.assertEqual(raised.exception.code, CANONICAL_LOGICAL_DATASET_MISMATCH)

    def test_mixed_row_identity_fails_before_typed_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data_plane"
            installed = _install_canonical_corpus(data_root)
            pins = _pins_from_installed(installed)
            census_path = data_root / installed["census_rel"]
            rows = pq.read_table(census_path).to_pylist()
            rows[0]["release_id"] = "ff" * 32
            _write_parquet(census_path, rows, CENSUS_RELEASE_SCHEMA)
            new_sha = sha256_file_streaming(census_path)
            lineage_path = data_root / "datasets" / "live_lifecycle_corpus" / "lineage.json"
            lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
            lineage["cohorts"][0]["census_sha256"] = new_sha
            lineage_path.write_text(
                json.dumps(lineage, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            pins["census_sha256"] = new_sha
            part_dir = data_root / "datasets" / "manifests" / "partitions"
            for path in list(part_dir.glob("partition-*.json")):
                path.unlink()
            _publish_dataset(
                data_root,
                dataset_id=FROZEN_DATASET,
                dataset_version="corpus-v1-REL-20260902T111900Z-20260909T111900Z",
                census_rel=installed["census_rel"],
                obs_rel=installed["obs_rel"],
                census_sha=new_sha,
                obs_sha=installed["observations_sha256"],
                census_n=len(rows),
                obs_n=pq.read_table(data_root / installed["obs_rel"]).num_rows,
                cohort_id=FROZEN_COHORT,
            )
            reset_block_a_typed_read_probe()
            with self.assertRaises(CensoringDiagnosticError) as raised:
                bind_canonical_censoring_inputs(data_root, pins)
            self.assertEqual(
                raised.exception.code, CANONICAL_CENSUS_IDENTITY_INVALID
            )
            self.assertEqual(censoring_mod.BLOCK_A_TYPED_READ_CALLS, 0)

    def test_partition_location_or_hash_disagrees_with_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data_plane"
            installed = _install_canonical_corpus(data_root)
            pins = _pins_from_installed(installed)
            part_dir = data_root / "datasets" / "manifests" / "partitions"
            for path in list(part_dir.glob("partition-*.json")):
                path.unlink()
            _publish_dataset(
                data_root,
                dataset_id=FROZEN_DATASET,
                dataset_version="corpus-v1-REL-20260902T111900Z-20260909T111900Z",
                census_rel="datasets/partitions/date=2026-09-13/wrong-census.parquet",
                obs_rel=installed["obs_rel"],
                census_sha=installed["census_sha256"],
                obs_sha=installed["observations_sha256"],
                census_n=1,
                obs_n=1,
                cohort_id=FROZEN_COHORT,
            )
            with self.assertRaises(CensoringDiagnosticError) as raised:
                bind_canonical_censoring_inputs(data_root, pins)
            self.assertEqual(
                raised.exception.code, CANONICAL_PARTITION_LOCATION_MISMATCH
            )

    def test_partition_hash_disagrees_with_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data_plane"
            installed = _install_canonical_corpus(data_root)
            pins = _pins_from_installed(installed)
            part_dir = data_root / "datasets" / "manifests" / "partitions"
            for path in list(part_dir.glob("partition-*.json")):
                path.unlink()
            _publish_dataset(
                data_root,
                dataset_id=FROZEN_DATASET,
                dataset_version="corpus-v1-REL-20260902T111900Z-20260909T111900Z",
                census_rel=installed["census_rel"],
                obs_rel=installed["obs_rel"],
                census_sha="aa" * 32,
                obs_sha=installed["observations_sha256"],
                census_n=1,
                obs_n=1,
                cohort_id=FROZEN_COHORT,
            )
            with self.assertRaises(CensoringDiagnosticError) as raised:
                bind_canonical_censoring_inputs(data_root, pins)
            self.assertEqual(raised.exception.code, CANONICAL_PARTITION_HASH_MISMATCH)

    def test_mixed_observation_identity_fails_before_typed_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data_plane"
            installed = _install_canonical_corpus(data_root)
            pins = _pins_from_installed(installed)
            obs_path = data_root / installed["obs_rel"]
            rows = pq.read_table(obs_path).to_pylist()
            rows[0]["cohort_id"] = "REL-OTHER"
            _write_parquet(obs_path, rows, OBS_RELEASE_SCHEMA)
            new_sha = sha256_file_streaming(obs_path)
            lineage_path = data_root / "datasets" / "live_lifecycle_corpus" / "lineage.json"
            lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
            lineage["cohorts"][0]["observations_sha256"] = new_sha
            lineage_path.write_text(
                json.dumps(lineage, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            pins["observations_sha256"] = new_sha
            part_dir = data_root / "datasets" / "manifests" / "partitions"
            for path in list(part_dir.glob("partition-*.json")):
                path.unlink()
            _publish_dataset(
                data_root,
                dataset_id=FROZEN_DATASET,
                dataset_version="corpus-v1-REL-20260902T111900Z-20260909T111900Z",
                census_rel=installed["census_rel"],
                obs_rel=installed["obs_rel"],
                census_sha=installed["census_sha256"],
                obs_sha=new_sha,
                census_n=pq.read_table(data_root / installed["census_rel"]).num_rows,
                obs_n=len(rows),
                cohort_id=FROZEN_COHORT,
            )
            reset_block_a_typed_read_probe()
            with self.assertRaises(CensoringDiagnosticError) as raised:
                bind_canonical_censoring_inputs(data_root, pins)
            self.assertEqual(
                raised.exception.code, CANONICAL_OBSERVATIONS_IDENTITY_INVALID
            )
            self.assertEqual(censoring_mod.BLOCK_A_TYPED_READ_CALLS, 0)

    def test_new_dataset_manifest_id_with_unchanged_bytes_still_binds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data_plane"
            installed = _install_canonical_corpus(data_root)
            pins = _pins_from_installed(installed)
            rebound = _publish_dataset(
                data_root,
                dataset_id=FROZEN_DATASET,
                dataset_version="corpus-v2-later-cohort-unchanged-bytes",
                census_rel=installed["census_rel"],
                obs_rel=installed["obs_rel"],
                census_sha=installed["census_sha256"],
                obs_sha=installed["observations_sha256"],
                census_n=pq.read_table(data_root / installed["census_rel"]).num_rows,
                obs_n=pq.read_table(data_root / installed["obs_rel"]).num_rows,
                cohort_id=FROZEN_COHORT,
            )
            lineage_path = data_root / "datasets" / "live_lifecycle_corpus" / "lineage.json"
            lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
            lineage["current_dataset_manifest_id"] = rebound
            lineage["current_corpus_version"] = 2
            lineage_path.write_text(
                json.dumps(lineage, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            binding = bind_canonical_censoring_inputs(data_root, pins)
            self.assertEqual(binding.dataset_manifest_id, rebound)
            self.assertNotEqual(rebound, installed["dataset_manifest_id"])
            self.assertEqual(binding.census_sha256, installed["census_sha256"])

    def test_missing_hash_pin_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data_plane"
            installed = _install_canonical_corpus(data_root)
            pins = _pins_from_installed(installed)
            pins["census_sha256"] = ""
            with self.assertRaises(CensoringDiagnosticError) as raised:
                bind_canonical_censoring_inputs(data_root, pins)
            self.assertEqual(raised.exception.code, CANONICAL_HASH_PIN_MISSING)

    def test_cli_rejects_mixed_canonical_and_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            env = dict(os.environ)
            env["PYTHONPATH"] = str(SRC)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(CLI),
                    "--data-root",
                    str(tmp),
                    "censoring-ignorability-diagnostic",
                    "--census",
                    str(census),
                    "--observations",
                    str(observations),
                ],
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(CANONICAL_MODE_EXPLICIT_PATH_CONFLICT, completed.stderr + completed.stdout)

    def test_public_run_has_no_canonical_binding_parameter(self) -> None:
        self.assertNotIn(
            "canonical_binding",
            inspect.signature(run_censoring_ignorability_diagnostic).parameters,
        )

    def test_public_data_root_uses_frozen_spec_pins_before_typed_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data_plane"
            _install_canonical_corpus(data_root)
            reset_block_a_typed_read_probe()
            with self.assertRaises(CensoringDiagnosticError) as raised:
                run_censoring_ignorability_diagnostic(root=ROOT, data_root=data_root)
            self.assertEqual(raised.exception.code, CANONICAL_CENSUS_HASH_MISMATCH)
            self.assertEqual(censoring_mod.BLOCK_A_TYPED_READ_CALLS, 0)

    def test_cli_help_names_parent_data_root(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC)
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(CLI),
                "censoring-ignorability-diagnostic",
                "--help",
            ],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        text = completed.stdout + completed.stderr
        self.assertIn("--data-root", text)
        self.assertIn("LIVE CORPUS", text)
        self.assertIn("Observation RDP", text)


class DiagnosticPopulationScopeTests(unittest.TestCase):
    def test_a_out_of_scope_capacity_hash_predicate_does_not_trigger_unknown(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            rows = pq.read_table(census).to_pylist()
            rows.extend(
                [
                    _member(
                        "cap000",
                        candidate="NOT_SELECTED_CAPACITY",
                        denom="excluded",
                    ),
                    _member(
                        "hash000",
                        candidate="NOT_SELECTED_HASH_SAMPLE",
                        denom="excluded",
                    ),
                    _member(
                        "pred000",
                        candidate="NOT_SELECTED_PREDICATE",
                        denom="excluded",
                    ),
                ]
            )
            _write_parquet(census, rows, CENSUS_RELEASE_SCHEMA)
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(SHIFT_NOT_DETECTED))
        self.assertNotIn("UNKNOWN_CENSUS_STATE", receipt["inconclusive_reasons"])
        self.assertEqual(receipt["counts"]["other_in_scope"], 0)
        self.assertEqual(receipt["counts"]["other"], 3)
        self.assertEqual(receipt["counts"]["out_of_scope_census_rows"], 7)
        self.assertEqual(receipt["counts"]["census_rows_total"], 60)
        self.assertEqual(receipt["counts"]["diagnostic_population_census_rows"], 53)
        self.assertEqual(receipt["counts"]["discovered_in_observation_partition"], 53)

    def test_b_in_scope_garbage_still_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            rows = pq.read_table(census).to_pylist()
            rows.append(
                _member("weird000", candidate="WEIRD", denom="observed", anchor="ANCHOR")
            )
            _write_parquet(census, rows, CENSUS_RELEASE_SCHEMA)
            obs_rows = pq.read_table(observations).to_pylist()
            obs_rows.append(_identity_obs("weird000"))
            _write_parquet(observations, obs_rows, OBS_RELEASE_SCHEMA)
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(INCONCLUSIVE))
        self.assertIn("UNKNOWN_CENSUS_STATE", receipt["inconclusive_reasons"])
        self.assertEqual(receipt["counts"]["other_in_scope"], 1)
        self.assertNotEqual(
            receipt["counts"]["out_of_scope_census_rows"],
            receipt["counts"]["other_in_scope"],
        )

    def test_d_observation_mint_missing_from_census_is_dedicated_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            obs_rows = pq.read_table(observations).to_pylist()
            obs_rows.append(_identity_obs("ghost000"))
            _write_parquet(observations, obs_rows, OBS_RELEASE_SCHEMA)
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(INCONCLUSIVE))
        self.assertIn(
            OBSERVATION_MINT_MISSING_FROM_CENSUS,
            receipt["inconclusive_reasons"],
        )
        self.assertNotIn("UNKNOWN_CENSUS_STATE", receipt["inconclusive_reasons"])
        self.assertEqual(receipt["counts"]["discovered_in_observation_partition"], 54)
        self.assertEqual(receipt["counts"]["diagnostic_population_census_rows"], 53)

    def test_e_in_scope_duplicate_census_is_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            rows = pq.read_table(census).to_pylist()
            rows.append(_member("adm000", candidate="ADMITTED", denom="censored_late"))
            _write_parquet(census, rows, CENSUS_RELEASE_SCHEMA)
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(INCONCLUSIVE))
        self.assertIn("DUPLICATE_CENSUS_MINT", receipt["inconclusive_reasons"])
        self.assertNotIn("DUPLICATE_COMPARABLE_MINT", receipt["inconclusive_reasons"])

    def test_f_out_of_scope_duplicate_does_not_invalidate_estimand(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            rows = pq.read_table(census).to_pylist()
            rows.append(
                _member(
                    "inel000",
                    candidate="X_POPULATION_INELIGIBLE",
                    denom="excluded",
                )
            )
            rows.extend(
                [
                    _member(
                        "cap000",
                        candidate="NOT_SELECTED_CAPACITY",
                        denom="excluded",
                    ),
                    _member(
                        "cap000",
                        candidate="NOT_SELECTED_CAPACITY",
                        denom="excluded",
                    ),
                ]
            )
            _write_parquet(census, rows, CENSUS_RELEASE_SCHEMA)
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(SHIFT_NOT_DETECTED))
        self.assertNotIn("DUPLICATE_CENSUS_MINT", receipt["inconclusive_reasons"])
        self.assertNotIn("UNKNOWN_CENSUS_STATE", receipt["inconclusive_reasons"])
        self.assertEqual(receipt["counts"]["other_in_scope"], 0)
        self.assertEqual(receipt["counts"]["other"], 2)
        self.assertEqual(receipt["comparable_x_subset_n"], 48)

    def test_y_only_mint_does_not_enter_diagnostic_population(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            rows = pq.read_table(census).to_pylist()
            rows.append(
                _member("yon000", candidate="WEIRD", denom="observed", anchor="ANCHOR")
            )
            _write_parquet(census, rows, CENSUS_RELEASE_SCHEMA)
            obs_rows = pq.read_table(observations).to_pylist()
            obs_rows.append(_x300("yon000", LIQUIDITY, 1, point_id="Y900"))
            _write_parquet(observations, obs_rows, OBS_RELEASE_SCHEMA)
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(SHIFT_NOT_DETECTED))
        self.assertNotIn("UNKNOWN_CENSUS_STATE", receipt["inconclusive_reasons"])
        self.assertEqual(receipt["counts"]["other_in_scope"], 0)
        self.assertEqual(receipt["counts"]["other"], 1)
        self.assertEqual(receipt["counts"]["discovered_in_observation_partition"], 54)
        self.assertEqual(receipt["counts"]["diagnostic_population_census_rows"], 53)
        self.assertEqual(receipt["y_point_rows_present_unread"], 1)

    def test_y_only_mint_missing_from_census_is_not_x300_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            census, observations = _balanced_fixture(Path(tmp), shift_liquidity=False)
            obs_rows = pq.read_table(observations).to_pylist()
            obs_rows.append(_x300("ghosty", LIQUIDITY, 1, point_id="Y900"))
            _write_parquet(observations, obs_rows, OBS_RELEASE_SCHEMA)
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(SHIFT_NOT_DETECTED))
        self.assertNotIn(
            OBSERVATION_MINT_MISSING_FROM_CENSUS,
            receipt["inconclusive_reasons"],
        )
        self.assertEqual(receipt["counts"]["discovered_in_observation_partition"], 54)
        self.assertEqual(receipt["counts"]["diagnostic_population_census_rows"], 53)

    def test_h_pinned_production_closure_is_read_only_without_permutations(
        self,
    ) -> None:
        payload = json.loads(
            PINNED_PRODUCTION_CLOSURE.read_text(encoding="utf-8")
        )
        self.assertEqual(payload["census_rows_total"], 138844)
        self.assertEqual(payload["census_distinct_mints_total"], 138844)
        self.assertEqual(payload["discovered_in_observation_partition"], 610)
        self.assertEqual(payload["diagnostic_population_census_rows"], 610)
        self.assertEqual(payload["diagnostic_population_distinct_mints"], 610)
        self.assertEqual(payload["out_of_scope_census_rows"], 138234)
        self.assertEqual(payload["other_in_scope"], 0)
        self.assertNotEqual(
            payload["out_of_scope_census_rows"], payload["other_in_scope"]
        )
        four_way = payload["four_way_in_scope_capable"]
        self.assertEqual(four_way["x_eligible_observed"], 148)
        self.assertEqual(four_way["x_eligible_censored_late"], 327)
        self.assertEqual(four_way["admitted_censored_late_no_x300"], 35)
        self.assertEqual(four_way["x_population_ineligible"], 100)
        self.assertEqual(four_way["comparable_x_subset_n"], 475)
        self.assertTrue(payload["did_not_run_permutations"])
        self.assertTrue(payload["did_not_run_scientific_diagnostic"])
        self.assertTrue(payload["ci_must_not_read_machine_local_data_plane"])
        self.assertTrue(payload["historical_receipt_not_mutated"])
        self.assertEqual(payload["derivation"], "RESEARCH_PIN_NOT_REPRODUCED_THIS_ATOM")
        self.assertEqual(
            payload["historical_receipt_other_meaning"],
            "schema_1_0_full_census_unexpected_states",
        )
        self.assertEqual(
            payload["a1_denominator_closure_gap"],
            "grouping SQL is FROM census without observation-mint / X300 intersection",
        )
        impl = Path(censoring_mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("local/factory_v1/data_plane", impl)


if __name__ == "__main__":
    unittest.main()
