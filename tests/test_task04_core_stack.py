from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
validator_spec = importlib.util.spec_from_file_location(
    "validate_task04_for_tests",
    ROOT / "scripts/validate_task04.py",
)
assert validator_spec and validator_spec.loader
task04_validator = importlib.util.module_from_spec(validator_spec)
sys.modules[validator_spec.name] = task04_validator
validator_spec.loader.exec_module(task04_validator)


def prepare_replay(root: Path, order: str = "source") -> dict[str, object]:
    items, excluded = task04_validator.accepted_observations(order)
    parquet_path, manifest_path, ledger_path, hashes = (
        task04_validator.write_replay_artifacts(items, root / "artifacts")
    )
    return {
        "items": items,
        "excluded": excluded,
        "parquet_path": parquet_path,
        "manifest_path": manifest_path,
        "ledger_path": ledger_path,
        "hashes": hashes,
    }


class Task04CoreStackTests(unittest.TestCase):
    def test_strict_model_rejects_coercion_and_extra_fields(self) -> None:
        _, observations = task04_validator.load_replay_fixture()
        invalid = observations[0].model_dump()
        invalid["revision"] = "1"
        invalid["unexpected"] = True
        with self.assertRaises(ValidationError):
            task04_validator.Observation.model_validate(invalid)

    def test_pit_filter_binary_null_timestamps_and_identity(self) -> None:
        accepted, excluded = task04_validator.accepted_observations()
        self.assertEqual(
            [item.observation_id for item in accepted],
            ["obs-a", "obs-b", "obs-null"],
        )
        self.assertEqual(excluded, ["obs-future"])
        self.assertIsNone(
            next(item for item in accepted if item.observation_id == "obs-null").value
        )
        self.assertEqual(
            next(item for item in accepted if item.observation_id == "obs-a").payload,
            b"\x00\x01\x02\xfe",
        )
        for item in accepted:
            self.assertEqual(item.source, "synthetic_offline_fixture")
            self.assertEqual(item.source_version, "1.0")
            self.assertIsNotNone(item.event_time.tzinfo)
            self.assertLessEqual(
                item.first_reliable_available_at,
                item.available_to_strategy_at,
            )

    def test_full_replay_is_input_order_independent_and_hash_bound(self) -> None:
        with tempfile.TemporaryDirectory(prefix="task04_replay_source_") as first:
            source = task04_validator.run_replay_contract("source", Path(first))
        with tempfile.TemporaryDirectory(prefix="task04_replay_reverse_") as second:
            reverse = task04_validator.run_replay_contract("reverse", Path(second))
        self.assertEqual(source, reverse)
        receipt = json.loads(source)
        for key in (
            "canonical_input_sha256",
            "parquet_sha256",
            "dataset_manifest_sha256",
            "migration_ledger_sha256",
            "first_fresh_duckdb_result_sha256",
            "second_fresh_duckdb_result_sha256",
        ):
            self.assertRegex(receipt[key], r"^[0-9a-f]{64}$")
        self.assertEqual(
            receipt["canonical_input_sha256"],
            receipt["first_fresh_duckdb_result_sha256"],
        )
        self.assertEqual(
            receipt["first_fresh_duckdb_result_sha256"],
            receipt["second_fresh_duckdb_result_sha256"],
        )
        self.assertEqual(receipt["excluded_observation_ids"], ["obs-future"])
        self.assertEqual(receipt["network_policy"], "DENY")

    def test_parquet_artifact_is_the_rebuild_source_and_preserves_schema(self) -> None:
        with tempfile.TemporaryDirectory(prefix="task04_parquet_source_") as temporary:
            root = Path(temporary)
            prepared = prepare_replay(root)
            table = pq.read_table(prepared["parquet_path"])
            self.assertEqual(table.schema, task04_validator.ARROW_SCHEMA)
            ids = table["observation_id"].to_pylist()
            values = table["value"].to_pylist()
            payloads = table["payload"].to_pylist()
            self.assertIsNone(values[ids.index("obs-null")])
            self.assertEqual(payloads[ids.index("obs-a")], b"\x00\x01\x02\xfe")
            for field in (
                "event_time",
                "observed_at",
                "available_to_strategy_at",
                "ingested_at",
                "first_reliable_available_at",
            ):
                self.assertEqual(table.schema.field(field).type.tz, "UTC")
                self.assertTrue(
                    all(
                        value is not None
                        for value in table[field].cast(pa.int64()).to_pylist()
                    )
                )

    def test_parquet_manifest_and_ledger_bytes_are_deterministic_and_immutable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="task04_artifact_first_") as first:
            first_prepared = prepare_replay(Path(first))
            first_bytes = {
                name: Path(first_prepared[name]).read_bytes()
                for name in ("parquet_path", "manifest_path", "ledger_path")
            }
            task04_validator.write_replay_artifacts(
                first_prepared["items"], Path(first) / "artifacts"
            )
            with self.assertRaisesRegex(
                task04_validator.Task04ValidationError, "replacement_denied"
            ):
                task04_validator.immutable_write(
                    Path(first_prepared["manifest_path"]),
                    first_bytes["manifest_path"] + b"drift",
                )
        with tempfile.TemporaryDirectory(prefix="task04_artifact_second_") as second:
            second_prepared = prepare_replay(Path(second), "reverse")
            second_bytes = {
                name: Path(second_prepared[name]).read_bytes()
                for name in ("parquet_path", "manifest_path", "ledger_path")
            }
        self.assertEqual(first_bytes, second_bytes)

    def test_migration_ledger_has_exact_order_sql_hash_and_states(self) -> None:
        ledger = json.loads(task04_validator.migration_ledger_bytes())
        self.assertTrue(ledger["immutable"])
        self.assertEqual(
            [item["order"] for item in ledger["migrations"]],
            [1, 2],
        )
        self.assertIn("read_parquet(?)", ledger["migrations"][1]["sql"])
        for item in ledger["migrations"]:
            self.assertEqual(
                item["sql_sha256"],
                hashlib.sha256(item["sql"].encode("utf-8")).hexdigest(),
            )
            self.assertEqual(item["schema_version"], "1.0")
            self.assertEqual(item["applied_state"], "APPLIED")
            self.assertEqual(item["result_state"], "PASS")

    def test_two_fresh_databases_rebuild_from_same_parquet_and_ledger(self) -> None:
        with tempfile.TemporaryDirectory(prefix="task04_two_rebuilds_") as temporary:
            root = Path(temporary)
            prepared = prepare_replay(root)
            isolated = root / "isolated_extensions"
            first = task04_validator.rebuild_from_artifacts(
                prepared["parquet_path"],
                prepared["manifest_path"],
                prepared["ledger_path"],
                root / "first.duckdb",
                isolated / "first",
                isolated,
            )
            second = task04_validator.rebuild_from_artifacts(
                prepared["parquet_path"],
                prepared["manifest_path"],
                prepared["ledger_path"],
                root / "second.duckdb",
                isolated / "second",
                isolated,
            )
        self.assertEqual(first, prepared["hashes"]["canonical_input_sha256"])
        self.assertEqual(first, second)

    def test_unsafe_bigint_to_integer_narrowing_fails(self) -> None:
        connection = duckdb.connect(":memory:")
        try:
            connection.execute("CREATE TABLE narrowing(value BIGINT)")
            connection.execute("INSERT INTO narrowing VALUES (2147483648)")
            with self.assertRaises(duckdb.ConversionException):
                connection.execute("ALTER TABLE narrowing ALTER value TYPE INTEGER")
        finally:
            connection.close()

    def test_extension_directory_is_isolated_and_httpfs_load_is_denied(self) -> None:
        with tempfile.TemporaryDirectory(prefix="task04_extension_policy_") as temporary:
            root = Path(temporary)
            isolated_root = root / "isolated"
            connection = duckdb.connect(":memory:")
            try:
                task04_validator.configure_duckdb(
                    connection,
                    isolated_root / "one",
                    isolated_root,
                )
                observed = {
                    row[0]: str(row[1]).lower()
                    for row in connection.execute(
                        "SELECT name, value FROM duckdb_settings() WHERE name IN "
                        "('allow_community_extensions','autoinstall_known_extensions',"
                        "'autoload_known_extensions')"
                    ).fetchall()
                }
                self.assertEqual(observed, task04_validator.EXTENSION_SETTINGS)
            finally:
                connection.close()

    def test_rebuild_bypass_of_parquet_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="task04_bypass_") as temporary:
            root = Path(temporary)
            prepared = prepare_replay(root)
            isolated = root / "isolated"
            with self.assertRaisesRegex(
                task04_validator.Task04ValidationError, "parquet_source_required"
            ):
                task04_validator.rebuild_from_artifacts(
                    prepared["parquet_path"],
                    prepared["manifest_path"],
                    prepared["ledger_path"],
                    root / "bypass.duckdb",
                    isolated / "bypass",
                    isolated,
                    source_mode="ARROW_MEMORY",
                )

    def test_missing_parquet_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="task04_missing_parquet_") as temporary:
            root = Path(temporary)
            prepared = prepare_replay(root)
            Path(prepared["parquet_path"]).unlink()
            isolated = root / "isolated"
            with self.assertRaisesRegex(
                task04_validator.Task04ValidationError, "parquet_artifact_required"
            ):
                task04_validator.rebuild_from_artifacts(
                    prepared["parquet_path"],
                    prepared["manifest_path"],
                    prepared["ledger_path"],
                    root / "missing.duckdb",
                    isolated / "missing",
                    isolated,
                )

    def test_missing_migration_ledger_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="task04_missing_ledger_") as temporary:
            root = Path(temporary)
            prepared = prepare_replay(root)
            Path(prepared["ledger_path"]).unlink()
            isolated = root / "isolated"
            with self.assertRaisesRegex(
                task04_validator.Task04ValidationError, "migration_ledger_required"
            ):
                task04_validator.rebuild_from_artifacts(
                    prepared["parquet_path"],
                    prepared["manifest_path"],
                    prepared["ledger_path"],
                    root / "missing.duckdb",
                    isolated / "missing",
                    isolated,
                )

    def test_reused_migration_id_with_changed_sql_or_hash_is_rejected(self) -> None:
        ledger = json.loads(task04_validator.migration_ledger_bytes())
        ledger["migrations"][1]["sql"] += " -- changed"
        changed_sql = task04_validator.canonical_json_bytes(ledger) + b"\n"
        with self.assertRaisesRegex(
            task04_validator.Task04ValidationError, "migration_redefinition_denied"
        ):
            task04_validator.validate_migration_ledger(changed_sql)

        ledger = json.loads(task04_validator.migration_ledger_bytes())
        ledger["migrations"][1]["sql_sha256"] = "0" * 64
        changed_hash = task04_validator.canonical_json_bytes(ledger) + b"\n"
        with self.assertRaisesRegex(
            task04_validator.Task04ValidationError, "migration_redefinition_denied"
        ):
            task04_validator.validate_migration_ledger(changed_hash)

    def test_external_global_extension_cache_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="task04_external_cache_") as temporary:
            root = Path(temporary)
            prepared = prepare_replay(root)
            global_cache = root / "global_cache"
            global_cache.mkdir()
            (global_cache / "httpfs.duckdb_extension").write_bytes(b"external-cache")
            isolated = root / "isolated"
            with self.assertRaisesRegex(
                task04_validator.Task04ValidationError,
                "external_extension_directory_not_allowed",
            ):
                task04_validator.rebuild_from_artifacts(
                    prepared["parquet_path"],
                    prepared["manifest_path"],
                    prepared["ledger_path"],
                    root / "global.duckdb",
                    global_cache,
                    isolated,
                )

    def test_pipeline_runs_with_python_network_entrypoint_denied(self) -> None:
        with mock.patch.object(
            socket,
            "create_connection",
            side_effect=AssertionError("network_denied"),
        ):
            with tempfile.TemporaryDirectory(prefix="task04_offline_") as temporary:
                receipt = json.loads(
                    task04_validator.run_replay_contract(
                        "source", Path(temporary)
                    )
                )
        self.assertEqual(receipt["network_policy"], "DENY")

    def test_solana_packages_import_without_provider_call(self) -> None:
        import solana
        import solders

        self.assertIsNotNone(solana)
        self.assertIsNotNone(solders)


class Task04ContractNegativeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.matrix = task04_validator.load_json(task04_validator.MATRIX_PATH)
        self.registry = task04_validator.load_yaml(task04_validator.REGISTRY_PATH)

    def test_wrong_security_dependency_group_fails(self) -> None:
        with (ROOT / "pyproject.toml").open("rb") as handle:
            document = __import__("tomllib").load(handle)
        document["dependency-groups"]["security"] = ["pip-audit==2.10.0"]
        with self.assertRaisesRegex(
            task04_validator.Task04ValidationError,
            "security_dependency_group",
        ):
            task04_validator.validate_dependency_contract(document)

    def test_wrong_verdict_count_fails(self) -> None:
        changed = copy.deepcopy(self.matrix)
        changed["rows"][0]["verdict"] = "REJECT"
        with self.assertRaisesRegex(
            task04_validator.Task04ValidationError, "verdict_count"
        ):
            task04_validator.validate_matrix(changed)

    def test_duplicate_registry_id_fails(self) -> None:
        changed = copy.deepcopy(self.registry)
        changed["records"][1]["record_id"] = changed["records"][0]["record_id"]
        with self.assertRaisesRegex(
            task04_validator.Task04ValidationError, "duplicate_record_id"
        ):
            task04_validator.validate_registry(changed, self.matrix)

    def test_matrix_registry_reconciliation_fails(self) -> None:
        changed = copy.deepcopy(self.registry)
        changed["records"][0]["pin"] = "9.9.9"
        with self.assertRaisesRegex(
            task04_validator.Task04ValidationError,
            "matrix_registry_reconciliation",
        ):
            task04_validator.validate_registry(changed, self.matrix)

    def test_exact_version_critical_pin_errors_fail(self) -> None:
        ids = (
            "REUSE-T04-UV-001",
            "REUSE-T04-JSONSCHEMA-001",
            "REUSE-T04-LOGGING-001",
            "REUSE-T04-UNITTEST-001",
            "REUSE-T04-UV-CYCLONEDX-001",
        )
        for candidate_id in ids:
            with self.subTest(candidate_id=candidate_id):
                changed = copy.deepcopy(self.matrix)
                row = next(
                    item
                    for item in changed["rows"]
                    if item["candidate_id"] == candidate_id
                )
                row["pin"] = "9.9.9"
                with self.assertRaisesRegex(
                    task04_validator.Task04ValidationError,
                    f"matrix_critical_pin_mismatch:{candidate_id}",
                ):
                    task04_validator.validate_matrix(changed)

    def test_accidental_duckdb_pin_on_nonversion_rows_fails(self) -> None:
        ids = (
            "REUSE-T04-DUCKDB-MULTIWRITER-001",
            "REUSE-T04-ALEMBIC-001",
        )
        for candidate_id in ids:
            with self.subTest(candidate_id=candidate_id):
                changed = copy.deepcopy(self.matrix)
                row = next(
                    item
                    for item in changed["rows"]
                    if item["candidate_id"] == candidate_id
                )
                row["pin"] = "1.5.5"
                with self.assertRaisesRegex(
                    task04_validator.Task04ValidationError,
                    f"matrix_critical_pin_mismatch:{candidate_id}",
                ):
                    task04_validator.validate_matrix(changed)

    def test_full_row_digest_detects_semantic_drift(self) -> None:
        changed = copy.deepcopy(self.matrix)
        original_decision_digest = task04_validator.matrix_decision_digest(
            changed["rows"]
        )
        original_full_digest = task04_validator.matrix_full_row_digest(
            changed["rows"]
        )
        changed["rows"][0]["next_validation"] += "_DRIFT"
        self.assertEqual(
            original_decision_digest,
            task04_validator.matrix_decision_digest(changed["rows"]),
        )
        self.assertNotEqual(
            original_full_digest,
            task04_validator.matrix_full_row_digest(changed["rows"]),
        )

    def test_candidate_receipt_full_row_digest_mismatch_fails(self) -> None:
        receipt = task04_validator.load_json(
            task04_validator.CANDIDATE_RECEIPT_PATH
        )
        receipt["matrix_full_row_sha256"] = "0" * 64
        with mock.patch.object(task04_validator, "load_json", return_value=receipt):
            with self.assertRaisesRegex(
                task04_validator.Task04ValidationError,
                "candidate_matrix_full_row_digest_mismatch",
            ):
                task04_validator.validate_candidate_receipt(
                    receipt["candidate_sbom_raw_sha256"],
                    receipt["candidate_sbom_normalized_graph_sha256"],
                    task04_validator.matrix_full_row_digest(self.matrix["rows"]),
                    receipt.get("replay_receipt_sha256", ""),
                )

    def test_license_discrepancy_omission_fails(self) -> None:
        text = task04_validator.ADR_PATH.read_text(encoding="utf-8")
        with self.assertRaisesRegex(
            task04_validator.Task04ValidationError, "license_discrepancy"
        ):
            task04_validator.validate_license_disclosures(
                text.replace("jsonalias==0.1.1", "omitted")
            )

    def test_provider_effect_claim_fails(self) -> None:
        receipt = task04_validator.load_json(
            task04_validator.CANDIDATE_RECEIPT_PATH
        )
        receipt["provider_api_rpc_calls"] = 1
        with self.assertRaisesRegex(
            task04_validator.Task04ValidationError, "external_effect_claim"
        ):
            task04_validator.validate_zero_effect_receipt(receipt)


if __name__ == "__main__":
    unittest.main()
