from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
PROJECT_SOURCES_ROOT = ROOT / "docs/project_sources"
REGISTRY_PATH = PROJECT_SOURCES_ROOT / "release_registry_v1.yaml"
SCHEMA_PATH = ROOT / "catalog/schemas/project_sources_release_registry.schema.json"
CATALOG_CORE_PATH = ROOT / "catalog/assets/core.yaml"
RELEASES_ROOT = PROJECT_SOURCES_ROOT / "releases"
A5_RECEIPT_PATH = ROOT / "docs/evidence/task27/a0a5_permanent_sources_reconciliation_acceptance_v1.json"
ACTIVATION_RECEIPT_PATH = ROOT / "docs/evidence/task27/a2r1_project_sources_activation_and_task_close_acceptance_v1.json"
FIRST_RELEASE_ID = "PSR-0001-T27-A0-A5"
ACTIVE_RELEASE_ID = "PSR-0002-T27-CLOSE"
CANDIDATE_STATUS = "VALIDATED_CANDIDATE_UI_ACTIVATION_PENDING"
ACTIVE_STATUS = "ACTIVATED_BY_OWNER_SMOKE"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def release_by_id(registry: dict, release_id: str) -> dict:
    return next(release for release in registry["releases"] if release["release_id"] == release_id)


def activation_receipt_errors(receipt: dict, release: dict) -> set[str]:
    errors: set[str] = set()
    if receipt.get("schema") != "smial.project_sources.activation.receipt":
        errors.add("ACTIVE_RECEIPT_SCHEMA_MISMATCH")
    if receipt.get("release_id") != release["release_id"]:
        errors.add("ACTIVE_RECEIPT_RELEASE_MISMATCH")
    if receipt.get("activation_evidence", {}).get("class") != "OWNER_ATTESTATION":
        errors.add("ACTIVE_RECEIPT_EVIDENCE_CLASS_MISMATCH")
    if receipt.get("activation_evidence", {}).get("smoke_outcome") != "PASS":
        errors.add("ACTIVE_RECEIPT_SMOKE_NOT_PASS")
    if receipt.get("manifest_binding") != release["artifact_bindings"]["canonical_manifest"]:
        errors.add("ACTIVE_RECEIPT_MANIFEST_BINDING_MISMATCH")
    return errors


def semantic_errors(registry: dict, root: Path = ROOT) -> set[str]:
    errors: set[str] = set()
    releases = registry.get("releases", [])
    release_ids = [release.get("release_id") for release in releases]
    releases_by_id = {release.get("release_id"): release for release in releases}
    candidate_releases = [release for release in releases if release.get("status") == CANDIDATE_STATUS]
    active_releases = [release for release in releases if release.get("status") == ACTIVE_STATUS]
    registered_bundle_paths = {release.get("bundle_path") for release in releases}

    if len(release_ids) != len(set(release_ids)):
        errors.add("DUPLICATE_RELEASE_ID")
    if len(candidate_releases) > 1:
        errors.add("MULTIPLE_CANDIDATES")
    if len(active_releases) > 1:
        errors.add("MULTIPLE_ACTIVE_RELEASES")
    if registry.get("latest_candidate_release_id") not in {None, *[release.get("release_id") for release in candidate_releases]}:
        errors.add("CANDIDATE_POINTER_MISMATCH")
    if active_releases:
        if registry.get("active_ui_release_id") != active_releases[0].get("release_id"):
            errors.add("ACTIVE_POINTER_MISMATCH")
        if registry.get("active_ui_state") != "REGISTRY_ACTIVATION_CONFIRMED":
            errors.add("ACTIVE_STATE_MISMATCH")
    else:
        if registry.get("active_ui_release_id") is not None:
            errors.add("ACTIVE_POINTER_MISMATCH")
        if registry.get("active_ui_state") != "PRE_REGISTRY_EXTERNAL_STATE":
            errors.add("PRE_REGISTRY_STATE_REQUIRED")

    releases_root = root / "docs/project_sources/releases"
    if releases_root.exists():
        actual_bundle_paths = {
            str(path.relative_to(root)).replace("\\", "/")
            for path in releases_root.iterdir()
            if path.is_dir()
        }
        if actual_bundle_paths != registered_bundle_paths:
            errors.add("UNREGISTERED_RELEASE_PAYLOAD")

    for release in releases:
        bundle_path = root / release["bundle_path"]
        manifest_binding = release["artifact_bindings"]["canonical_manifest"]
        checksums_binding = release["artifact_bindings"]["checksums"]
        manifest_path = root / manifest_binding["path"]
        checksums_path = root / checksums_binding["path"]
        if not bundle_path.is_dir() or not manifest_path.is_file() or not checksums_path.is_file():
            errors.add("RELEASE_ARTIFACT_MISSING")
            continue
        if manifest_path.parent != bundle_path or checksums_path.parent != bundle_path:
            errors.add("RELEASE_ARTIFACT_PATH_MISMATCH")
        if sha256(manifest_path) != manifest_binding["sha256"] or sha256(checksums_path) != checksums_binding["sha256"]:
            errors.add("RELEASE_ARTIFACT_HASH_MISMATCH")
        if release["status"] == ACTIVE_STATUS:
            activation_receipt = release.get("activation_receipt")
            if not activation_receipt or not (root / activation_receipt).is_file():
                errors.add("ACTIVE_RECEIPT_REQUIRED")
            else:
                errors.update(activation_receipt_errors(load_json(root / activation_receipt), release))
        if release["status"] == CANDIDATE_STATUS and release.get("activation_receipt") is not None:
            errors.add("CANDIDATE_CANNOT_HAVE_ACTIVATION_RECEIPT")
        if release["status"] == "SUPERSEDED":
            successor = releases_by_id.get(release.get("superseded_by_release_id"))
            if not successor or successor.get("status") != ACTIVE_STATUS or successor.get("supersedes_release_id") != release.get("release_id"):
                errors.add("SUPERSEDED_SUCCESSOR_REQUIRED")
        if release["status"] != "SUPERSEDED" and release.get("superseded_by_release_id") is not None:
            errors.add("UNEXPECTED_SUPERSEDED_BY_REFERENCE")
    return errors


def acceptance_errors(receipt: dict, registry: dict | None = None, changed_release_paths: set[str] | None = None) -> set[str]:
    errors: set[str] = set()
    disposition = receipt.get("project_sources_disposition")
    if not isinstance(disposition, dict):
        return {"SOURCE_DISPOSITION_REQUIRED"}
    kind = disposition.get("kind")
    if kind not in {"NO_CHANGE", "RELEASE_CANDIDATE", "ACTIVATION_RECEIPT"}:
        return {"SOURCE_DISPOSITION_INVALID"}
    changed_release_paths = changed_release_paths or set()
    if kind == "NO_CHANGE" and changed_release_paths:
        errors.add("NO_CHANGE_WITH_RELEASE_MUTATION")
    if kind == "RELEASE_CANDIDATE":
        if registry is None:
            errors.add("CANDIDATE_REGISTRY_REQUIRED")
        else:
            release_id = disposition.get("release_id")
            try:
                release = release_by_id(registry, release_id)
            except (KeyError, StopIteration):
                errors.add("CANDIDATE_RELEASE_UNKNOWN")
            else:
                if release["status"] == CANDIDATE_STATUS:
                    is_current_or_historical = registry.get("latest_candidate_release_id") == release_id
                elif release["status"] == ACTIVE_STATUS:
                    is_current_or_historical = registry.get("active_ui_release_id") == release_id
                elif release["status"] == "SUPERSEDED":
                    is_current_or_historical = True
                else:
                    is_current_or_historical = False
                if not is_current_or_historical:
                    errors.add("CANDIDATE_RELEASE_NOT_CURRENT")
                if disposition.get("registry_path") != "docs/project_sources/release_registry_v1.yaml":
                    errors.add("CANDIDATE_REGISTRY_PATH_MISMATCH")
    if kind == "ACTIVATION_RECEIPT":
        if registry is None:
            errors.add("ACTIVATION_REGISTRY_REQUIRED")
        else:
            release_id = disposition.get("release_id")
            try:
                release = release_by_id(registry, release_id)
            except (KeyError, StopIteration):
                errors.add("ACTIVATION_RELEASE_UNKNOWN")
            else:
                if release["status"] != ACTIVE_STATUS or registry.get("active_ui_release_id") != release_id:
                    errors.add("ACTIVATION_RELEASE_NOT_ACTIVE")
    return errors


def git_is_ancestor(ancestor: str, descendant: str) -> bool:
    return subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", ancestor, descendant],
        check=False,
        capture_output=True,
        text=True,
    ).returncode == 0


def changed_paths_since_enforcement(registry: dict) -> set[str]:
    merge_base = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "HEAD", "origin/main"],
        check=False,
        capture_output=True,
        text=True,
    )
    if merge_base.returncode != 0 or not merge_base.stdout.strip():
        raise RuntimeError("MERGE_BASE_UNAVAILABLE")
    policy_start = registry["enforcement_start_commit"]
    pr_merge_base = merge_base.stdout.strip()
    if git_is_ancestor(policy_start, pr_merge_base):
        comparison_base = pr_merge_base
    elif git_is_ancestor(policy_start, "HEAD"):
        comparison_base = policy_start
    else:
        raise RuntimeError("ENFORCEMENT_START_UNREACHABLE")
    diff = subprocess.run(
        ["git", "-C", str(ROOT), "diff", "--name-only", comparison_base],
        check=True,
        capture_output=True,
        text=True,
    )
    return {line.strip().replace("\\", "/") for line in diff.stdout.splitlines() if line.strip()}


class ProjectSourcesReleaseRegistryTests(unittest.TestCase):
    def test_latest_release_is_activated_and_prior_release_is_superseded(self) -> None:
        self.assertTrue(REGISTRY_PATH.is_file(), REGISTRY_PATH)
        self.assertTrue(SCHEMA_PATH.is_file(), SCHEMA_PATH)
        registry = load_yaml(REGISTRY_PATH)
        release = release_by_id(registry, ACTIVE_RELEASE_ID)
        prior_release = release_by_id(registry, FIRST_RELEASE_ID)
        self.assertEqual(registry["registry_version"], 1)
        self.assertEqual(registry["active_ui_release_id"], ACTIVE_RELEASE_ID)
        self.assertEqual(registry["active_ui_state"], "REGISTRY_ACTIVATION_CONFIRMED")
        self.assertIsNone(registry["latest_candidate_release_id"])
        self.assertEqual(release["status"], ACTIVE_STATUS)
        self.assertEqual(release["activation_receipt"], ACTIVATION_RECEIPT_PATH.relative_to(ROOT).as_posix())
        self.assertEqual(prior_release["status"], "SUPERSEDED")
        self.assertEqual(prior_release["superseded_by_release_id"], ACTIVE_RELEASE_ID)
        self.assertTrue((ROOT / release["bundle_path"] / "canonical_manifest.yaml").is_file())

    def test_active_release_receipt_rejects_wrong_smoke_or_manifest_binding(self) -> None:
        registry = load_yaml(REGISTRY_PATH)
        release = release_by_id(registry, ACTIVE_RELEASE_ID)
        self.assertTrue(ACTIVATION_RECEIPT_PATH.is_file(), ACTIVATION_RECEIPT_PATH)
        receipt = load_json(ACTIVATION_RECEIPT_PATH)
        self.assertEqual(activation_receipt_errors(receipt, release), set())

        failed_smoke = copy.deepcopy(receipt)
        failed_smoke["activation_evidence"]["smoke_outcome"] = "FAIL"
        self.assertIn("ACTIVE_RECEIPT_SMOKE_NOT_PASS", activation_receipt_errors(failed_smoke, release))

        wrong_manifest = copy.deepcopy(receipt)
        wrong_manifest["manifest_binding"]["sha256"] = "0" * 64
        self.assertIn(
            "ACTIVE_RECEIPT_MANIFEST_BINDING_MISMATCH",
            activation_receipt_errors(wrong_manifest, release),
        )

    def test_task27_close_activation_receipt_is_hash_bound_in_catalog(self) -> None:
        catalog_records = load_yaml(CATALOG_CORE_PATH)["records"]
        record = next(
            (
                item
                for item in catalog_records
                if item["asset_id"] == "EVIDENCE-T27-A2R1-SOURCE-ACTIVATION-CLOSE-001"
            ),
            None,
        )
        self.assertIsNotNone(record)
        self.assertEqual(
            record["location"]["repository_path"],
            ACTIVATION_RECEIPT_PATH.relative_to(ROOT).as_posix(),
        )
        self.assertEqual(record["integrity"]["sha256"], sha256(ACTIVATION_RECEIPT_PATH))

    def test_registry_rejects_unregistered_payload_and_two_candidates(self) -> None:
        registry = load_yaml(REGISTRY_PATH)
        unregistered = copy.deepcopy(registry)
        unregistered["releases"] = []
        self.assertIn("UNREGISTERED_RELEASE_PAYLOAD", semantic_errors(unregistered))

        two_candidates = copy.deepcopy(registry)
        two_candidates["active_ui_release_id"] = None
        two_candidates["active_ui_state"] = "PRE_REGISTRY_EXTERNAL_STATE"
        two_candidates["latest_candidate_release_id"] = FIRST_RELEASE_ID
        two_candidates["releases"][0]["status"] = CANDIDATE_STATUS
        two_candidates["releases"][0]["activation_receipt"] = None
        duplicate = copy.deepcopy(two_candidates["releases"][0])
        duplicate["release_id"] = "PSR-0002-TEST"
        two_candidates["releases"].append(duplicate)
        self.assertIn("MULTIPLE_CANDIDATES", semantic_errors(two_candidates))

    def test_registry_rejects_artifact_hash_drift_and_false_active_pointer(self) -> None:
        registry = load_yaml(REGISTRY_PATH)
        hash_drift = copy.deepcopy(registry)
        hash_drift["releases"][0]["artifact_bindings"]["canonical_manifest"]["sha256"] = "0" * 64
        self.assertIn("RELEASE_ARTIFACT_HASH_MISMATCH", semantic_errors(hash_drift))

        false_active = copy.deepcopy(registry)
        false_active["active_ui_release_id"] = None
        self.assertIn("ACTIVE_POINTER_MISMATCH", semantic_errors(false_active))

    def test_registry_rejects_a_superseded_release_without_its_successor(self) -> None:
        registry = load_yaml(REGISTRY_PATH)
        orphaned_supersession = copy.deepcopy(registry)
        orphaned_supersession["releases"][0]["superseded_by_release_id"] = "PSR-9999-MISSING"
        self.assertIn("SUPERSEDED_SUCCESSOR_REQUIRED", semantic_errors(orphaned_supersession))

    def test_a5_receipt_requires_registered_candidate_disposition(self) -> None:
        registry = load_yaml(REGISTRY_PATH)
        receipt = load_json(A5_RECEIPT_PATH)
        self.assertEqual(acceptance_errors(receipt, registry), set())

        missing_disposition = copy.deepcopy(receipt)
        del missing_disposition["project_sources_disposition"]
        self.assertIn("SOURCE_DISPOSITION_REQUIRED", acceptance_errors(missing_disposition, registry))

        no_change = copy.deepcopy(receipt)
        no_change["project_sources_disposition"]["kind"] = "NO_CHANGE"
        self.assertIn(
            "NO_CHANGE_WITH_RELEASE_MUTATION",
            acceptance_errors(no_change, registry, {"docs/project_sources/release_registry_v1.yaml"}),
        )

    def test_changed_acceptance_receipts_declare_source_disposition(self) -> None:
        registry = load_yaml(REGISTRY_PATH)
        changed_paths = changed_paths_since_enforcement(registry)
        changed_receipts = [
            ROOT / path
            for path in changed_paths
            if path.startswith("docs/evidence/") and "acceptance" in Path(path).name and path.endswith(".json")
        ]
        changed_release_paths = {path for path in changed_paths if path.startswith("docs/project_sources/")}
        for receipt_path in changed_receipts:
            with self.subTest(receipt=receipt_path):
                self.assertEqual(acceptance_errors(load_json(receipt_path), registry, changed_release_paths), set())

    def test_registry_matches_its_schema(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(load_yaml(REGISTRY_PATH))), [])
        self.assertEqual(semantic_errors(load_yaml(REGISTRY_PATH)), set())


if __name__ == "__main__":
    unittest.main()
