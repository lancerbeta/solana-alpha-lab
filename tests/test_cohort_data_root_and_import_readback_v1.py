from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.cohort_import_readback import (  # noqa: E402
    PASS_ALREADY_PRESENT_EXACT,
    STOP_IDENTITY_CONFLICT,
    build_cohort_import_readback,
    owner_import_terminal,
)
from solana_alpha_lab.factory.data_root import (  # noqa: E402
    DEFAULT_DATA_PLANE_RELATIVE,
    DataRootError,
    resolve_data_root,
    resolve_existing_data_root,
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.check_call(["git", *args], cwd=cwd, stdout=subprocess.DEVNULL)


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "a2@test")
    _git(path, "config", "user.name", "a2")
    (path / "README.md").write_text("a2\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "init")


class CanonicalDataRootTests(unittest.TestCase):
    def test_linked_worktree_resolves_principal_data_plane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            principal = Path(tmp) / "principal"
            linked = Path(tmp) / "linked"
            _init_repo(principal)
            _git(principal, "worktree", "add", str(linked), "-b", "linked-a2")
            try:
                from_principal = resolve_data_root(principal, env={})
                from_linked = resolve_data_root(linked, env={})
                expected = (principal / DEFAULT_DATA_PLANE_RELATIVE).resolve()
                self.assertEqual(from_principal, expected)
                self.assertEqual(from_linked, expected)
                self.assertEqual(from_principal, from_linked)
            finally:
                _git(principal, "worktree", "remove", "--force", str(linked))

    def test_non_git_without_explicit_or_env_is_typed_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "not-git"
            repo.mkdir()
            with self.assertRaises(DataRootError) as raised:
                resolve_data_root(repo, env={})
            self.assertEqual(raised.exception.code, "DATA_ROOT_NON_GIT_CONTEXT")
            discovered = resolve_existing_data_root(repo, env={})
            self.assertEqual(discovered.status, "UNAVAILABLE")
            self.assertEqual(discovered.error, "DATA_ROOT_NON_GIT_CONTEXT")


class CohortImportReadbackTests(unittest.TestCase):
    def test_readback_counts_c1_c2_once_without_absolute_path(self) -> None:
        lineage = {
            "corpus_dataset_id": "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
            "current_corpus_version": 2,
            "current_dataset_manifest_id": "MID-CURRENT",
            "cohorts": [
                {
                    "cohort_id": "REL-C1",
                    "release_id": "rel-c1",
                    "content_sha256": "a" * 64,
                    "schedule_sha256": "b" * 64,
                    "source_sha256": "c" * 64,
                },
                {
                    "cohort_id": "REL-C2",
                    "release_id": "rel-c2",
                    "content_sha256": "d" * 64,
                    "schedule_sha256": "e" * 64,
                    "source_sha256": "f" * 64,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data_plane"
            data_root.mkdir()
            payload = build_cohort_import_readback(
                data_root,
                lineage=lineage,
                fingerprint="ab" * 32,
            )
        self.assertEqual(payload["schema"], "smial.cohort-import-readback")
        self.assertEqual(payload["corpus_version"], 2)
        self.assertEqual(len(payload["visible_cohorts"]), 2)
        self.assertEqual(payload["duplicate_cohort_count"], 0)
        self.assertEqual(payload["lineage_integrity"], "PASS")
        rendered = json.dumps(payload)
        self.assertNotIn("C:\\", rendered)
        self.assertNotIn(str(data_root), rendered)
        counts = {item["cohort_id"]: item["lineage_count"] for item in payload["visible_cohorts"]}
        self.assertEqual(counts["REL-C1"], 1)
        self.assertEqual(counts["REL-C2"], 1)
        self.assertTrue(all(item["status"] == "PRESENT_ONCE" for item in payload["visible_cohorts"]))
        self.assertEqual(payload["visible_cohorts"][0]["source_sha256"], "c" * 64)

    def test_missing_source_hash_is_not_filled_from_content(self) -> None:
        lineage = {
            "current_corpus_version": 1,
            "cohorts": [
                {
                    "cohort_id": "REL-C1",
                    "release_id": "rel-c1",
                    "content_sha256": "a" * 64,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data_plane"
            data_root.mkdir()
            payload = build_cohort_import_readback(
                data_root,
                lineage=lineage,
                fingerprint="ef" * 32,
            )
        self.assertIsNone(payload["visible_cohorts"][0]["source_sha256"])

    def test_owner_terminals_for_reimport_and_conflict(self) -> None:
        self.assertEqual(
            owner_import_terminal("IDEMPOTENT_REIMPORT"),
            PASS_ALREADY_PRESENT_EXACT,
        )
        self.assertEqual(
            owner_import_terminal("COHORT_ALREADY_IMPORTED"),
            STOP_IDENTITY_CONFLICT,
        )
        self.assertEqual(
            owner_import_terminal("CANONICAL_TARGET_CONFLICT"),
            STOP_IDENTITY_CONFLICT,
        )
        self.assertEqual(
            owner_import_terminal("IDENTITY_CONFLICT"),
            STOP_IDENTITY_CONFLICT,
        )
        self.assertEqual(
            owner_import_terminal("IMPORT_CONFLICT"),
            STOP_IDENTITY_CONFLICT,
        )

    def test_duplicate_exact_cohort_row_is_not_present_once(self) -> None:
        lineage = {
            "corpus_dataset_id": "DATASET-LIVE-LIFECYCLE-DISCOVERY-CORPUS-001",
            "current_corpus_version": 2,
            "current_dataset_manifest_id": "MID-CURRENT",
            "cohorts": [
                {
                    "cohort_id": "REL-C1",
                    "release_id": "rel-c1",
                    "content_sha256": "a" * 64,
                    "source_sha256": "c" * 64,
                },
                {
                    "cohort_id": "REL-C1",
                    "release_id": "rel-c1-dup",
                    "content_sha256": "d" * 64,
                    "source_sha256": "e" * 64,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data_plane"
            data_root.mkdir()
            payload = build_cohort_import_readback(
                data_root,
                lineage=lineage,
                fingerprint="cd" * 32,
            )
        self.assertEqual(payload["duplicate_cohort_count"], 1)
        self.assertEqual(payload["lineage_integrity"], "DUPLICATE_LINEAGE")
        self.assertEqual(payload["visible_cohorts"][0]["status"], "DUPLICATE")
        self.assertEqual(payload["visible_cohorts"][0]["lineage_count"], 2)
        self.assertEqual(payload["next_owner_action"], STOP_IDENTITY_CONFLICT)
        self.assertIsNone(payload["visible_cohorts"][0].get("content_sha256"))


class ImportLiveCliReadbackTests(unittest.TestCase):
    def test_cli_omitted_data_root_uses_canonical_default(self) -> None:
        parser_src = (ROOT / "scripts" / "discovery_evidence_release.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "omit to use the Git principal checkout local/factory_v1/data_plane",
            parser_src,
        )
        self.assertRegex(
            parser_src,
            r'import_live.add_argument\(\s*"--data-root",\s*type=Path,\s*default=None',
        )
        self.assertNotRegex(
            parser_src,
            r'import_live.add_argument\(\s*"--data-root", type=Path, required=True',
        )
        self.assertRegex(
            parser_src,
            r'publish.add_argument\(\s*"--data-root",\s*type=Path,\s*default=None',
        )
        self.assertNotRegex(
            parser_src,
            r'publish.add_argument\(\s*"--data-root", type=Path, required=True',
        )
        self.assertIn(
            '"CENSUS_SCHEDULE_SHA_MISMATCH": "STOP_DO_NOT_IMPORT"',
            parser_src,
        )

    def test_cli_prints_readback_and_exact_reimport_terminal(self) -> None:
        import importlib.util
        from contextlib import redirect_stdout
        from io import StringIO

        spec = importlib.util.spec_from_file_location(
            "discovery_evidence_release_cli_a2",
            ROOT / "scripts" / "discovery_evidence_release.py",
        )
        assert spec is not None and spec.loader is not None
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp) / "data_plane"
            data_root.mkdir()
            buf = StringIO()
            with redirect_stdout(buf):
                cli._print_import_success({"status": "IDEMPOTENT_REIMPORT"}, data_root)
            envelope = json.loads(buf.getvalue())
        self.assertEqual(envelope["status"], PASS_ALREADY_PRESENT_EXACT)
        self.assertEqual(envelope["readback"]["schema"], "smial.cohort-import-readback")
        self.assertEqual(envelope["next"], envelope["readback"]["next_owner_action"])
        self.assertNotIn("next", envelope["result"])
        self.assertNotIn("C:\\", json.dumps(envelope["readback"]))

    def test_cli_data_root_error_is_typed_json(self) -> None:
        import importlib.util
        from contextlib import redirect_stdout
        from io import StringIO

        spec = importlib.util.spec_from_file_location(
            "discovery_evidence_release_cli_a2_err",
            ROOT / "scripts" / "discovery_evidence_release.py",
        )
        assert spec is not None and spec.loader is not None
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)

        def _boom(_value: Path | None) -> Path:
            raise cli.DataRootError("DATA_ROOT_NON_GIT_CONTEXT")

        cli._resolved_data_root = _boom
        buf = StringIO()
        with redirect_stdout(buf):
            code = cli.main(["import-live", "--release-root", str(ROOT)])
        self.assertEqual(code, 2)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["status"], "FAIL")
        self.assertEqual(payload["code"], "DATA_ROOT_NON_GIT_CONTEXT")
        self.assertEqual(payload["next"], "STOP_USE_GIT_CHECKOUT_OR_EXPLICIT_DATA_ROOT")


class ExactReimportLineageTests(unittest.TestCase):
    def test_second_exact_import_keeps_lineage_count_one(self) -> None:
        from contextlib import redirect_stdout
        from datetime import timedelta
        from io import StringIO

        from solana_alpha_lab.factory.live_cohort_discovery_release import (
            import_live_cohort,
        )
        from tests.test_live_cohort_to_forge_operational_closure_v1 import (
            AS_OF_C1,
            C1_ADMIT,
            COHORT1,
            PRODUCER_A,
            PUBLISH_C1,
            _entity,
            _schedule,
            _seed_ops,
        )
        from tests.test_self_contained_live_cohort_release_v1 import (
            _build_and_seal,
            _seed_rdp,
        )

        schedule = _schedule(ROOT)
        digest = schedule["schedule_sha256"]
        members = [_entity("A", i) for i in range(3)]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            observation_rdp = base / "observation_rdp"
            observation_rdp.mkdir()
            ops = base / "ops.sqlite"
            release = base / "release"
            data_root = base / "data_plane"
            data_root.mkdir()
            _seed_rdp(
                observation_rdp,
                schedule=schedule,
                entities=members,
                admission=C1_ADMIT,
                producer=PRODUCER_A,
                now=PUBLISH_C1,
            )
            _seed_ops(ops, digest=digest, cohort1=members, cohort2=[])
            _build_and_seal(
                observation_rdp=observation_rdp,
                ops=ops,
                digest=digest,
                cohort_id=COHORT1,
                as_of=AS_OF_C1,
                release_root=release,
            )
            first = import_live_cohort(
                release_root=release,
                data_root=data_root,
                import_time=AS_OF_C1 + timedelta(hours=1),
            )
            second = import_live_cohort(
                release_root=release,
                data_root=data_root,
                import_time=AS_OF_C1 + timedelta(hours=2),
            )
            self.assertEqual(first["status"], "IMPORTED")
            self.assertEqual(second["status"], "IDEMPOTENT_REIMPORT")
            after_first = build_cohort_import_readback(data_root)
            after_second = build_cohort_import_readback(data_root)
            counts_first = {
                item["cohort_id"]: item["lineage_count"]
                for item in after_first["visible_cohorts"]
            }
            counts_second = {
                item["cohort_id"]: item["lineage_count"]
                for item in after_second["visible_cohorts"]
            }
            self.assertEqual(counts_first[COHORT1], 1)
            self.assertEqual(counts_second[COHORT1], 1)
            self.assertEqual(after_second["duplicate_cohort_count"], 0)
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "discovery_evidence_release_cli_a2_reimport",
                ROOT / "scripts" / "discovery_evidence_release.py",
            )
            assert spec is not None and spec.loader is not None
            cli = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cli)
            buf = StringIO()
            with redirect_stdout(buf):
                cli._print_import_success(second, data_root)
            envelope = json.loads(buf.getvalue())
        self.assertEqual(envelope["status"], PASS_ALREADY_PRESENT_EXACT)
        self.assertEqual(envelope["next"], "STOP_BEFORE_HYPOTHESIS_FORGE")
        self.assertEqual(
            envelope["readback"]["visible_cohorts"][0]["lineage_count"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
