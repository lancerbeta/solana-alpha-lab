from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import duckdb
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from query_task05 import (  # noqa: E402
    MAX_RECORDS,
    RELATION_POLICIES,
    QueryContractError,
    connect_readonly,
    parse_limit,
    parse_utc_timestamp,
    query_decision_safe_observations,
    query_pit_relation,
    resolve_database_path,
)
from validate_catalog import load_and_validate  # noqa: E402

SCHEMA_PATH = ROOT / "schemas" / "schema_v1.sql"
FIXTURE_PATH = (
    ROOT / "tests" / "fixtures" / "task05" / "schema_contract_fixture_v1.json"
)
QUERY_SCRIPT_PATH = ROOT / "scripts" / "query_task05.py"
MANIFEST_PATH = ROOT / "catalog" / "catalog_manifest.yaml"
CORE_ASSETS_PATH = ROOT / "catalog" / "assets" / "core.yaml"
QUERY_RECIPES_PATH = ROOT / "catalog" / "query_recipes.yaml"
PROJECT_MAP_PATH = ROOT / "docs" / "PROJECT_MAP.md"
EDGE_PROJECTION_PATH = ROOT / "catalog" / "generated" / "asset_edges.json"

EXPECTED_RELATIONS = {
    "raw_api_events",
    "canonical_observations",
    "token_lifecycle_events",
    "pool_state_snapshots",
    "trade_orderflow_inputs",
    "entity_input_snapshots",
    "feature_observations",
    "regime_observations",
    "signal_decision_events",
    "quote_attempts",
    "execution_attempts",
    "strategy_outcomes",
    "dataset_manifests",
    "partition_manifests",
    "migration_manifests",
}

RELATION_ASSET_IDS = {
    "raw_api_events": "SCHEMA-T05-REL-RAW-API-EVENTS-001",
    "canonical_observations": "SCHEMA-T05-REL-CANONICAL-OBSERVATIONS-001",
    "token_lifecycle_events": "SCHEMA-T05-REL-TOKEN-LIFECYCLE-EVENTS-001",
    "pool_state_snapshots": "SCHEMA-T05-REL-POOL-STATE-SNAPSHOTS-001",
    "trade_orderflow_inputs": "SCHEMA-T05-REL-TRADE-ORDERFLOW-INPUTS-001",
    "entity_input_snapshots": "SCHEMA-T05-REL-ENTITY-INPUT-SNAPSHOTS-001",
    "feature_observations": "SCHEMA-T05-REL-FEATURE-OBSERVATIONS-001",
    "regime_observations": "SCHEMA-T05-REL-REGIME-OBSERVATIONS-001",
    "signal_decision_events": "SCHEMA-T05-REL-SIGNAL-DECISION-EVENTS-001",
    "quote_attempts": "SCHEMA-T05-REL-QUOTE-ATTEMPTS-001",
    "execution_attempts": "SCHEMA-T05-REL-EXECUTION-ATTEMPTS-001",
    "strategy_outcomes": "SCHEMA-T05-REL-STRATEGY-OUTCOMES-001",
    "dataset_manifests": "SCHEMA-T05-REL-DATASET-MANIFESTS-001",
    "partition_manifests": "SCHEMA-T05-REL-PARTITION-MANIFESTS-001",
    "migration_manifests": "SCHEMA-T05-REL-MIGRATION-MANIFESTS-001",
}

FILE_ASSET_IDS = {
    "CTRL-LATEST-HANDOFF-001",
    "CTRL-TASK-05-001",
    "CONTRACT-T05-DATA-001",
    "SCHEMA-T05-CANONICAL-DDL-001",
    "SCHEMA-T05-PYDANTIC-BOUNDARIES-001",
    "SCRIPT-T05-MIGRATION-LEDGER-001",
    "MIGRATION-T05-0001-001",
    "LEDGER-T05-MIGRATIONS-001",
    "FIXTURE-T05-SCHEMA-CONTRACT-001",
    "FIXTURE-T05-SCHEMA-MODEL-ROUNDTRIP-001",
    "TEST-T05-SCHEMA-CONTRACT-001",
    "TEST-T05-MODELS-001",
    "TEST-T05-MIGRATIONS-001",
    "QUERY-RUNNER-T05-PIT-001",
    "TEST-T05-CATALOG-QUERIES-001",
}

TASK05_ASSET_IDS = (
    FILE_ASSET_IDS - {"CTRL-LATEST-HANDOFF-001"}
) | set(RELATION_ASSET_IDS.values())
TASK05_QUERY_IDS = {
    "QUERY-T05-PIT-RELATION-001",
    "QUERY-T05-DECISION-SAFE-OBSERVATIONS-001",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def insert_row(
    connection: duckdb.DuckDBPyConnection,
    relation: str,
    row: dict[str, object],
) -> None:
    prepared = dict(row)
    if "redacted_body_hex" in prepared:
        prepared["redacted_body"] = bytes.fromhex(
            str(prepared.pop("redacted_body_hex"))
        )
    columns = list(prepared)
    connection.execute(
        f"""
        INSERT INTO {relation} ({", ".join(columns)})
        VALUES ({", ".join("?" for _ in columns)})
        """,
        [prepared[column] for column in columns],
    )


class Task05BoundedQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.database_path = Path(self.temporary.name) / "task05-fixture.duckdb"
        self.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        connection = duckdb.connect(str(self.database_path))
        try:
            connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
            for raw in self.fixture["raw_events"]:
                insert_row(connection, "raw_api_events", raw)
            for observation in self.fixture["observations"]:
                insert_row(connection, "canonical_observations", observation)
            for name, relation in (
                ("dataset", "dataset_manifests"),
                ("partition", "partition_manifests"),
                ("migration", "migration_manifests"),
            ):
                insert_row(connection, relation, self.fixture["manifests"][name])
        finally:
            connection.close()
        self.initial_hash = sha256(self.database_path)

    def tearDown(self) -> None:
        self.assertEqual(sha256(self.database_path), self.initial_hash)
        self.assertFalse(
            self.database_path.with_suffix(".duckdb.wal").exists(),
            "read-only query left a WAL side effect",
        )

    def test_static_allowlist_covers_exact_schema_inventory(self) -> None:
        self.assertEqual(set(RELATION_POLICIES), EXPECTED_RELATIONS)
        self.assertEqual(MAX_RECORDS, 100)

    def test_pit_relation_excludes_future_availability_and_is_bounded(self) -> None:
        result = query_pit_relation(
            str(self.database_path),
            "canonical_observations",
            "2026-07-23T12:00:00Z",
            100,
        )
        self.assertEqual(result["record_count"], 4)
        self.assertNotIn(
            "obs-future",
            {row["observation_id"] for row in result["rows"]},
        )

        bounded = query_pit_relation(
            str(self.database_path),
            "canonical_observations",
            "2026-07-23T12:00:00Z",
            2,
        )
        self.assertEqual(bounded["record_count"], 2)
        self.assertEqual(
            [row["observation_id"] for row in bounded["rows"]],
            sorted(row["observation_id"] for row in bounded["rows"]),
        )

    def test_decision_safe_macro_matches_direct_pit_policy(self) -> None:
        direct = query_pit_relation(
            str(self.database_path),
            "canonical_observations",
            "2026-07-23T12:00:00Z",
            100,
        )
        macro = query_decision_safe_observations(
            str(self.database_path),
            "2026-07-23T12:00:00Z",
            100,
        )
        self.assertEqual(macro["record_count"], direct["record_count"])
        self.assertEqual(
            [row["observation_id"] for row in macro["rows"]],
            [row["observation_id"] for row in direct["rows"]],
        )

    def test_raw_blob_is_excluded_from_query_output(self) -> None:
        result = query_pit_relation(
            str(self.database_path),
            "raw_api_events",
            "2026-07-23T12:00:00Z",
            100,
        )
        self.assertEqual(result["record_count"], 2)
        self.assertTrue(
            all("redacted_body" not in row for row in result["rows"])
        )

    def test_manifest_visibility_uses_creation_and_first_reliable_time(self) -> None:
        before = query_pit_relation(
            str(self.database_path),
            "dataset_manifests",
            "2026-07-23T12:00:00Z",
            100,
        )
        after = query_pit_relation(
            str(self.database_path),
            "dataset_manifests",
            "2026-07-23T12:00:01Z",
            100,
        )
        self.assertEqual(before["record_count"], 0)
        self.assertEqual(after["record_count"], 1)

    def test_readonly_connection_and_external_access_are_enforced(self) -> None:
        connection = connect_readonly(self.database_path)
        try:
            self.assertFalse(
                connection.execute(
                    "SELECT current_setting('enable_external_access')"
                ).fetchone()[0]
            )
            with self.assertRaises(duckdb.Error):
                connection.execute("CREATE TABLE forbidden_write(value INTEGER)")
        finally:
            connection.close()

    def test_input_validation_rejects_injection_local_time_and_bad_bounds(self) -> None:
        with self.assertRaisesRegex(QueryContractError, "relation_not_allowed"):
            query_pit_relation(
                str(self.database_path),
                'canonical_observations"; DROP TABLE canonical_observations; --',
                "2026-07-23T12:00:00Z",
                1,
            )
        with self.assertRaisesRegex(QueryContractError, "as_of_must_be_utc"):
            parse_utc_timestamp("2026-07-23T12:00:00")
        for value in ("0", "101", "01", "not-an-integer"):
            with self.subTest(value=value):
                with self.assertRaises(QueryContractError):
                    parse_limit(value)
        with self.assertRaisesRegex(
            QueryContractError,
            "database_parent_traversal",
        ):
            resolve_database_path("../fixture.duckdb")

    def test_cli_returns_bounded_json_without_machine_path(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(QUERY_SCRIPT_PATH),
                "decision-safe-observations",
                "--database-path",
                str(self.database_path),
                "--as-of",
                "2026-07-23T12:00:00Z",
                "--limit",
                "3",
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["record_count"], 3)
        self.assertNotIn(str(self.database_path), completed.stdout)


class Task05CatalogTransactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = load_and_validate()
        cls.manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.core = yaml.safe_load(CORE_ASSETS_PATH.read_text(encoding="utf-8"))
        cls.query_registry = yaml.safe_load(
            QUERY_RECIPES_PATH.read_text(encoding="utf-8")
        )

    def test_catalog_version_counts_and_task05_inventory_are_exact(self) -> None:
        self.assertEqual(self.snapshot.manifest["catalog_version"], "0.7.0")
        self.assertEqual(len(self.snapshot.assets), 158)
        self.assertEqual(len(self.snapshot.queries), 7)
        self.assertEqual(
            {
                asset_id
                for asset_id, asset in self.snapshot.assets.items()
                if asset["truth_owner"] == "TASK-05"
            },
            TASK05_ASSET_IDS,
        )
        self.assertTrue(
            TASK05_ASSET_IDS
            <= set(self.manifest["mandatory_asset_ids"])
        )
        self.assertEqual(
            TASK05_QUERY_IDS,
            set(self.snapshot.queries) & TASK05_QUERY_IDS,
        )

    def test_file_assets_resolve_and_match_exact_sha256(self) -> None:
        for asset_id in FILE_ASSET_IDS:
            with self.subTest(asset_id=asset_id):
                asset = self.snapshot.assets[asset_id]
                self.assertEqual(asset["location"]["kind"], "git_path")
                path = ROOT / asset["location"]["repository_path"]
                self.assertTrue(path.is_file())
                self.assertEqual(asset["integrity"]["kind"], "sha256")
                self.assertEqual(asset["integrity"]["sha256"], sha256(path))
                self.assertFalse(asset["access"]["network_required"])
                self.assertFalse(asset["access"]["secrets_required"])

    def test_every_relation_and_model_pair_has_one_stable_asset(self) -> None:
        self.assertEqual(set(RELATION_ASSET_IDS), set(RELATION_POLICIES))
        for relation, asset_id in RELATION_ASSET_IDS.items():
            with self.subTest(relation=relation):
                asset = self.snapshot.assets[asset_id]
                self.assertEqual(asset["asset_type"], "schema")
                self.assertEqual(asset["location"]["kind"], "logical_only")
                self.assertIn(f"/{relation}#model=", asset["location"]["logical_uri"])
                self.assertEqual(
                    asset["access"]["recipe_id"],
                    "QUERY-T05-PIT-RELATION-001",
                )
                targets = {
                    item["target_asset_id"] for item in asset["relations"]
                }
                self.assertTrue(
                    {
                        "SCHEMA-T05-CANONICAL-DDL-001",
                        "SCHEMA-T05-PYDANTIC-BOUNDARIES-001",
                        "TEST-T05-MODELS-001",
                    }
                    <= targets
                )
                self.assertTrue(asset["consumers"])

    def test_query_recipes_are_offline_bounded_and_patterns_match_cli(self) -> None:
        generic = self.snapshot.queries["QUERY-T05-PIT-RELATION-001"]
        macro = self.snapshot.queries[
            "QUERY-T05-DECISION-SAFE-OBSERVATIONS-001"
        ]
        for recipe in (generic, macro):
            with self.subTest(recipe=recipe["recipe_id"]):
                self.assertTrue(recipe["read_only"])
                self.assertTrue(recipe["bounded"])
                self.assertFalse(recipe["network_required"])
                self.assertEqual(recipe["write_effects"], "NONE")
                self.assertEqual(recipe["output_contract"]["max_records"], 100)
                self.assertIn("--offline", recipe["command"])
                self.assertIn("--locked", recipe["command"])
                self.assertIn("--managed-python", recipe["command"])

        patterns = {
            item["name"]: item["pattern"] for item in generic["parameters"]
        }
        self.assertRegex("fixture.duckdb", patterns["database_path"])
        self.assertNotRegex("../fixture.duckdb", patterns["database_path"])
        for relation in RELATION_POLICIES:
            self.assertRegex(relation, patterns["relation"])
        self.assertNotRegex(
            "canonical_observations;DROP TABLE x",
            patterns["relation"],
        )
        self.assertRegex("2026-07-23T12:00:00Z", patterns["as_of"])
        self.assertNotRegex("2026-07-23T12:00:00+03:00", patterns["as_of"])
        self.assertRegex("100", patterns["limit"])
        self.assertNotRegex("101", patterns["limit"])

    def test_generated_navigation_contains_every_task05_asset(self) -> None:
        project_map = PROJECT_MAP_PATH.read_text(encoding="utf-8")
        for asset_id in TASK05_ASSET_IDS:
            self.assertIn(f"| {asset_id} |", project_map)

        edge_projection = json.loads(
            EDGE_PROJECTION_PATH.read_text(encoding="utf-8")
        )
        known_ids = set(self.snapshot.assets)
        for edge in edge_projection["edges"]:
            self.assertIn(edge["source_asset_id"], known_ids)
            self.assertIn(edge["target_asset_id"], known_ids)


if __name__ == "__main__":
    unittest.main()
