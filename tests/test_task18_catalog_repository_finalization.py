from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task18"
    / "catalog_repository_finalization_receipt_v1.json"
)

EXPECTED_IDS = {
    "CONTRACT-T18-NARROW-DATA-QUALITY-001",
    "FIXTURE-T18-NARROW-DATA-QUALITY-001",
    "TEST-T18-NARROW-DATA-QUALITY-CONTRACT-001",
    "MODULE-T18-DATA-QUALITY-001",
    "SCRIPT-T18-DATA-QUALITY-AUDIT-001",
    "EVIDENCE-T18-NARROW-DATA-QUALITY-AUDIT-001",
    "EVIDENCE-T18-NARROW-DATA-QUALITY-SUMMARY-001",
    "TEST-T18-DATA-QUALITY-AUDIT-001",
    "CONTRACT-T18-CONTENT-ADDRESSED-BACKUP-RESTORE-001",
    "FIXTURE-T18-CONTENT-ADDRESSED-BACKUP-RESTORE-001",
    "MODULE-T18-BACKUP-RESTORE-001",
    "SCRIPT-T18-BACKUP-PACKAGER-001",
    "EVIDENCE-T18-CONTENT-ADDRESSED-BACKUP-RESTORE-001",
    "EVIDENCE-T18-CONTENT-ADDRESSED-BACKUP-RESTORE-SUMMARY-001",
    "TEST-T18-BACKUP-RESTORE-001",
    "BUNDLE-T18-CONTENT-ADDRESSED-RAW-BACKUP-001",
    "EVIDENCE-T18-CATALOG-REPOSITORY-FINALIZATION-001",
    "TEST-T18-CATALOG-REPOSITORY-FINALIZATION-001",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _catalog() -> tuple[dict, dict[str, dict]]:
    manifest = yaml.safe_load(
        (ROOT / "catalog" / "catalog_manifest.yaml").read_text(encoding="utf-8")
    )
    documents = [
        yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
        for relative in manifest["root_resolver"]["asset_registries"]
    ]
    records = {
        record["asset_id"]: record
        for document in documents
        for record in document["records"]
    }
    return manifest, records


def test_task18_catalog_transaction_is_exact_and_hash_bound() -> None:
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    manifest, records = _catalog()

    assert receipt["status"] == "PASS"
    assert receipt["catalog"]["registered_asset_ids"] == sorted(
        EXPECTED_IDS,
        key=receipt["catalog"]["registered_asset_ids"].index,
    )
    assert set(receipt["catalog"]["registered_asset_ids"]) == EXPECTED_IDS
    assert tuple(map(int, manifest["catalog_version"].split("."))) >= (0, 23, 0)
    historical = {
        "assets": 321,
        "asset_registries": 4,
        "schemas": 4,
        "queries": 8,
        "lifecycle_registries": 9,
        "lifecycle_records": 52,
    }
    for field, value in historical.items():
        assert manifest["current_checkpoint"][field] >= value
    assert len(records) == manifest["current_checkpoint"]["assets"]
    assert EXPECTED_IDS.issubset(records)

    for asset_id in EXPECTED_IDS - {
        "BUNDLE-T18-CONTENT-ADDRESSED-RAW-BACKUP-001"
    }:
        record = records[asset_id]
        relative = record["location"]["repository_path"]
        assert record["location"]["kind"] == "git_path"
        assert _sha256(ROOT / relative) == record["integrity"]["sha256"]

    bundle = records["BUNDLE-T18-CONTENT-ADDRESSED-RAW-BACKUP-001"]
    assert bundle["asset_type"] == "external_bundle"
    assert bundle["origin"] == "EXTERNAL"
    assert bundle["location"] == {
        "kind": "external_bundle",
        "logical_uri": (
            "gdrive://1msCdh2niGoh5wcGD7Ofiq9Dz9WBIFifn/"
            "TASK18_RAW_BACKUP_v1_"
            "8b016b38096d87e182aa7d41e549fd6d97eb7008777e5c9dfe59b3b15178b838.zip"
        ),
    }
    assert bundle["integrity"]["sha256"] == (
        "8b016b38096d87e182aa7d41e549fd6d97eb7008777e5c9dfe59b3b15178b838"
    )
    assert bundle["access"]["network_required"] is True
    assert bundle["access"]["secrets_required"] is False


def test_task18_recoverability_and_quality_claims_remain_bounded() -> None:
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    accepted = receipt["accepted_result"]

    assert accepted["quality_verdict"] == "FIT_FOR_NARROW_QUOTE_ONLY_ESTIMAND"
    assert (
        accepted["recoverability"]
        == "CONTENT_ADDRESSED_BACKUP_AND_RESTORE_PROVEN"
    )
    assert accepted["source_raw_files"] == 12
    assert accepted["source_raw_bytes"] == 179208
    assert accepted["source_mutation_or_deletion"] is False
    assert "NOT_FULL_STORAGE_RELIABILITY" in receipt["nonclaims"]
    assert "NOT_AUTOMATED_PERIODIC_BACKUP" in receipt["nonclaims"]
    assert "NOT_TASK19_AUTHORITY" in receipt["nonclaims"]

    authority = receipt["authority"]
    assert authority["local_write_only"] is True
    assert authority["network_calls"] == 0
    assert authority["provider_api_rpc_calls"] == 0
    assert authority["cash_spend"] == 0
    assert authority["wallet_signer_transaction_actions"] == 0
    assert authority["commit_push_pr_merge"] is False


def test_generated_navigation_exposes_task18_finalized_assets() -> None:
    project_map = (ROOT / "docs" / "PROJECT_MAP.md").read_text(encoding="utf-8")
    edges = json.loads(
        (ROOT / "catalog" / "generated" / "asset_edges.json").read_text(
            encoding="utf-8"
        )
    )
    edge_ids = {edge["source_asset_id"] for edge in edges["edges"]}

    assert EXPECTED_IDS.issubset(edge_ids)
    for asset_id in EXPECTED_IDS:
        assert asset_id in project_map
