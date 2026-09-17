"""Synthetic-only proofs for the HFIC censoring ignorability diagnostic."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.capabilities import (
    CAPABILITY_ROUTER,
    CapabilityError,
    execute_capability,
)
from solana_alpha_lab.factory.hfic_censoring_ignorability_diagnostic import (
    ADMITTED_NOT_X_ELIGIBLE,
    ANCHOR_UNRESOLVED,
    CAP_HFIC_CENSORING_IGNORABILITY_DIAGNOSTIC,
    FROZEN_SPEC_SHA256,
    IGNORABILITY_UNPROVEN,
    INCONCLUSIVE,
    RANDOM_SAMPLE_UNPROVEN,
    SCOPE_NONCANONICAL,
    SHIFT_DETECTED,
    SHIFT_NOT_DETECTED,
    Y_POINT_READ,
    CensoringDiagnosticError,
    _proportion_smd,
    load_diagnostic_spec,
    run_censoring_ignorability_diagnostic,
)
from solana_alpha_lab.factory.hfic_preflight import assert_capability_registry_v2_superset
from solana_alpha_lab.factory.live_cohort_source_bundle import (
    CENSUS_RELEASE_SCHEMA,
    OBS_RELEASE_SCHEMA,
)

CLI = ROOT / "scripts" / "hypothesis_forge.py"
SPEC = ROOT / "configs" / "hfic_censoring_ignorability_diagnostic_v1.yaml"

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
) -> dict[str, str | None]:
    return _census_row(
        mint=mint,
        candidate_state=candidate,
        denominator_state=denom,
        authoritative_anchor=anchor,
        discovery_first_reliable_available_at="2026-09-02T12:00:00Z",
        inclusion_probability="0.0425",
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
        self.assertEqual(receipt["counts"]["census_rows"], 57)
        self.assertEqual(receipt["counts"]["discovered_in_observation_partition"], 53)
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
            receipt = _run(census, observations)
        self.assertEqual(receipt["terminal"], _atomic(INCONCLUSIVE))
        self.assertIn("UNKNOWN_CENSUS_STATE", receipt["inconclusive_reasons"])
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

    def test_canonical_scope_unreachable_without_identity_columns_or_sha_pins(self) -> None:
        spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
        corpus = spec["canonical_corpus"]
        self.assertFalse(corpus.get("census_sha256"))
        self.assertFalse(corpus.get("observations_sha256"))
        census_names = set(CENSUS_RELEASE_SCHEMA.names)
        obs_names = set(OBS_RELEASE_SCHEMA.names)
        self.assertNotIn("dataset_id", census_names)
        self.assertNotIn("scientific_context_session", census_names)
        self.assertNotIn("dataset_id", obs_names)
        self.assertNotIn("scientific_context_session", obs_names)
        self.assertIn("cohort_id", census_names)
        self.assertIn("cohort_id", obs_names)


if __name__ == "__main__":
    unittest.main()
