from __future__ import annotations

import copy
import csv
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task23_diagnostic_projection import (
    ATOM_ID,
    RECEIPT_SCHEMA,
    SCHEMA_VERSION,
    Task23ProjectionError,
    build_projection,
    sha256_file,
    validate_config,
)


CONFIG = ROOT / "configs/task23_bounded_diagnostics_v1.yaml"
CONTRACT = ROOT / "docs/contracts/task23_bounded_diagnostics_contract_v1.md"
MODULE = ROOT / "src/solana_alpha_lab/task23_diagnostic_projection.py"
MATERIALIZED = ROOT / "docs/evidence/task23/a3_projection_v1_attempt_02"
PARTIAL_ATTEMPT = ROOT / "docs/evidence/task23/a3_projection_v1"
MEMBERS = [
    "T21-WATCH-29e2b75994975253bd74",
    "T21-WATCH-6f21dec76d05f5831216",
    "T21-WATCH-61ce24fc3fa04e3eaba7",
]
NOTIONALS = ((10, 10_000_000), (25, 25_000_000), (50, 50_000_000), (100, 100_000_000))
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)


def make_event(
    *,
    member_id: str,
    panel_id: str,
    ordinal: int,
    side: str,
    input_mint: str,
    input_atomic: int,
    input_decimals: int,
    output_mint: str,
    output_atomic: int | None,
    output_decimals: int,
    status: str = "QUOTE_AVAILABLE",
) -> dict:
    moment = f"2026-08-01T12:{int(panel_id[1]) * 10:02d}:{ordinal:02d}Z"
    request_hash = digest_text(f"request:{member_id}:{panel_id}:{ordinal}")
    raw_event_id = f"RAW-{digest_text(f'raw:{member_id}:{panel_id}:{ordinal}')[:24]}"
    idempotency_key = f"idem-{member_id}-{panel_id}-{ordinal}"
    if status == "QUOTE_AVAILABLE":
        body = {
            "inputMint": input_mint,
            "inAmount": str(input_atomic),
            "outputMint": output_mint,
            "outAmount": str(output_atomic),
            "otherAmountThreshold": str(max(0, int(output_atomic or 0) - 1)),
            "swapMode": "ExactIn",
            "slippageBps": 100,
            "platformFee": None,
            "priceImpactPct": "0.001" if side == "BUY" else "0.002",
            "routePlan": [{"synthetic": f"{member_id}:{panel_id}:{ordinal}"}],
            "contextSlot": 410_000_000 + ordinal,
            "timeTaken": 0.01,
        }
        route_id = digest_text(json.dumps(body["routePlan"], sort_keys=True))
        route_count = 1
    else:
        body = {"error": "Could not find any route"}
        route_id = None
        route_count = 0
        output_atomic = None
    body_text = json.dumps(body, sort_keys=True, separators=(",", ":"))
    content_hash = digest_text(body_text)
    raw_event = {
        "raw_event_id": raw_event_id,
        "idempotency_key": idempotency_key,
        "source": "JUPITER_METIS",
        "source_version": "legacy_metis_v1_quote",
        "endpoint_or_method": "/swap/v1/quote",
        "request_hash": request_hash,
        "response_status": "SUCCESS",
        "error_class": None,
        "redacted_body": body_text,
        "content_sha256": content_hash,
        "redaction_version": "task10-jupiter-raw-v1",
        "event_time": None,
        "observed_at": moment,
        "available_to_strategy_at": moment,
        "ingested_at": moment,
        "first_reliable_available_at": moment,
        "provider_version": "legacy_metis_v1_quote",
        "schema_version": "1.0.0",
        "protocol_version": None,
        "revision_number": 1,
        "revision_of": None,
        "quality_flags": None,
    }
    quote_attempt = {
        "quote_attempt_id": f"QUOTE-{digest_text(f'quote:{member_id}:{panel_id}:{ordinal}')[:24]}",
        "idempotency_key": idempotency_key,
        "business_key": f"{member_id}:{panel_id}:{ordinal}",
        "request_hash": request_hash,
        "provider": "JUPITER_METIS",
        "provider_version": "legacy_metis_v1_quote",
        "side": side,
        "input_mint": input_mint,
        "input_requested_atomic": input_atomic,
        "input_decimals": input_decimals,
        "output_mint": output_mint,
        "output_quoted_atomic": output_atomic,
        "output_decimals": output_decimals,
        "route_id": route_id,
        "route_count": route_count,
        "context_slot": 410_000_000 + ordinal if status == "QUOTE_AVAILABLE" else None,
        "requested_at": moment,
        "response_at": moment,
        "available_to_strategy_at": moment,
        "ingested_at": moment,
        "first_reliable_available_at": moment,
        "quote_age_ms": 0,
        "provider_latency_ms": 1,
        "provider_fee_atomic": None,
        "platform_fee_atomic": None,
        "fee_mint": None,
        "included_in_output_amount": None,
        "status": status,
        "error_class": None,
        "raw_event_id": raw_event_id,
        "response_content_sha256": content_hash,
        "schema_version": "1.0.0",
        "revision_number": 1,
        "revision_of": None,
        "quality_flags": None,
    }
    return {
        "schema": "smial.task21.forward-quote-panel-raw",
        "schema_version": "1.0.0",
        "task_id": "TASK-21",
        "atom_id": f"T21-SYNTHETIC-{panel_id}",
        "hypothesis_version_id": "HYP-VERSION-EXECUTION-CAPACITY-CURVATURE-V1",
        "batch_id": "T21-R2",
        "member_id": member_id,
        "nomination_event_id": f"NOM-{member_id}",
        "horizon_id": panel_id,
        "window_id": f"{member_id}-{panel_id}",
        "call_ordinal": ordinal,
        "provider": "JUPITER_METIS",
        "provider_version": "legacy_metis_v1_quote",
        "request_hash": request_hash,
        "idempotency_key": idempotency_key,
        "raw_content_sha256": content_hash,
        "requested_at": moment,
        "response_at": moment,
        "first_reliable_available_at": moment,
        "available_to_strategy_at": moment,
        "ingested_at": moment,
        "latency_ms": 1,
        "response_status": "SUCCESS",
        "terminal_class": status,
        "error_class": None,
        "route_id": route_id,
        "route_count": route_count,
        "context_slot": quote_attempt["context_slot"],
        "stop_reason": None,
        "raw_event": raw_event,
        "quote_attempt": quote_attempt,
    }


class SyntheticRepository:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        roots = [
            "local/task21_forward/final_cohort/r2/p0/run=synthetic",
            "local/task21_forward/final_cohort/r2/p1/run=synthetic",
            "local/task21_forward/final_cohort/r2/p2/run=synthetic",
        ]
        self.config["r2_read_boundary"]["allowed_roots_after_a3_pre_read_receipt"] = roots
        self.config["r2_read_boundary"]["root_bindings"] = [
            {"panel_id": panel, "root": root}
            for panel, root in zip(("P0", "P1", "P2"), roots, strict=True)
        ]
        for item in self.config["frozen_inputs"]:
            source = ROOT / item["path"]
            target = root / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        self.contract_path = root / "docs/contracts/task23_bounded_diagnostics_contract_v1.md"
        self.contract_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(CONTRACT, self.contract_path)
        self.module_path = root / "src/solana_alpha_lab/task23_diagnostic_projection.py"
        self.module_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MODULE, self.module_path)
        self.config_path = root / "configs/task23_bounded_diagnostics_v1.yaml"
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(yaml.safe_dump(self.config, sort_keys=False), encoding="utf-8", newline="\n")
        self._write_raw_inputs()
        self.receipt_path = root / "docs/evidence/task23/a3_r2_development_read_receipt_v1.json"
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self.receipt_path.write_text(
            json.dumps(self.receipt(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def _write_raw_inputs(self) -> None:
        for binding in self.config["r2_read_boundary"]["root_bindings"]:
            panel_id = binding["panel_id"]
            for member_index, member_id in enumerate(MEMBERS):
                events = []
                ordinal = 1
                token_mint = f"TOKEN-{member_index}"
                for usd, atomic in NOTIONALS:
                    no_route = member_index == 0 and panel_id == "P1" and usd == 100
                    buy_output = atomic * 100
                    buy = make_event(
                        member_id=member_id,
                        panel_id=panel_id,
                        ordinal=ordinal,
                        side="BUY",
                        input_mint=USDC,
                        input_atomic=atomic,
                        input_decimals=6,
                        output_mint=token_mint,
                        output_atomic=buy_output,
                        output_decimals=9,
                        status="NO_ROUTE" if no_route else "QUOTE_AVAILABLE",
                    )
                    events.append(buy)
                    ordinal += 1
                    if no_route:
                        continue
                    events.append(
                        make_event(
                            member_id=member_id,
                            panel_id=panel_id,
                            ordinal=ordinal,
                            side="SELL",
                            input_mint=token_mint,
                            input_atomic=buy_output,
                            input_decimals=9,
                            output_mint=USDC,
                            output_atomic=atomic * 98 // 100,
                            output_decimals=6,
                        )
                    )
                    ordinal += 1
                path = (
                    self.root
                    / binding["root"]
                    / f"member={member_id}"
                    / f"horizon={panel_id}"
                    / "raw_events.jsonl"
                )
                payload = b"".join(
                    json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
                    for event in events
                )
                write_bytes(path, payload)

    def receipt(self) -> dict:
        return {
            "schema": RECEIPT_SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "receipt_id": "T23-R2-FIRST-DEVELOPMENT-READ-TEST-001",
            "task_id": "TASK-23",
            "atom_id": ATOM_ID,
            "status": "SEALED_BEFORE_FIRST_R2_VALUE_READ",
            "created_at": "2026-08-02T12:00:00Z",
            "actor": "LOCAL_WORK_PRIMARY",
            "reason": "TEST_DETERMINISTIC_R2_DIAGNOSTIC_PROJECTION",
            "bindings": {
                "contract": {
                    "path": "docs/contracts/task23_bounded_diagnostics_contract_v1.md",
                    "sha256": sha256_file(self.contract_path),
                },
                "config": {
                    "path": "configs/task23_bounded_diagnostics_v1.yaml",
                    "sha256": sha256_file(self.config_path),
                },
                "projection_code": {
                    "path": "src/solana_alpha_lab/task23_diagnostic_projection.py",
                    "sha256": sha256_file(self.module_path),
                },
                "frozen_inputs": [
                    {"path": item["path"], "sha256": item["sha256"]}
                    for item in self.config["frozen_inputs"]
                ],
                "dataset_identity": self.config["dataset_identity"],
                "member_set": MEMBERS,
                "root_bindings": self.config["r2_read_boundary"]["root_bindings"],
                "allowed_value_filename": "raw_events.jsonl",
                "holdout_ledger": {
                    "path": "docs/evidence/task22/holdout_access_ledger_v2.json",
                    "sha256": sha256_file(self.root / "docs/evidence/task22/holdout_access_ledger_v2.json"),
                },
            },
            "r3_boundary": {
                "split": "R3",
                "state": "UNTOUCHED",
                "access": "DENY",
                "path_discovery": False,
                "value_read": False,
                "outcome_read": False,
            },
            "authority": {
                "r2_value_read": True,
                "r2_value_files_max": 9,
                "network": False,
                "provider_call": False,
                "credential_use": False,
                "drive_read": False,
                "external_api": False,
                "dependency_change": False,
                "r3_read": False,
                "outcome_path_read_outside_r2": False,
                "wallet_or_signer": False,
                "cash_or_credits": False,
            },
            "ordering": {"receipt_written_before_value_open": True},
        }


class Task23DiagnosticProjectionTests(unittest.TestCase):
    def test_materialized_projection_is_bound_complete_and_r3_free(self) -> None:
        manifest_path = MATERIALIZED / "projection_manifest_v1.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "MATERIALIZED_DETERMINISTIC_R2_ONLY")
        self.assertEqual(
            manifest["bindings"]["projection_code"]["sha256"],
            sha256_file(MODULE),
        )
        self.assertEqual(
            manifest["bindings"]["config"]["sha256"],
            sha256_file(CONFIG),
        )
        self.assertEqual(
            manifest["summary"],
            {
                "capture_clusters": 1,
                "eligible_dependent_sell_legs": 36,
                "inference_mode": "DESCRIPTIVE_ONLY",
                "members": 3,
                "observed_buy_legs": 36,
                "observed_dependent_sell_legs": 36,
                "observed_panels": 9,
                "outcome_paths_outside_r2_opened": 0,
                "planned_buy_legs": 36,
                "planned_panels": 9,
                "r2_value_files_opened": 9,
                "r3_paths_discovered": 0,
                "r3_value_files_opened": 0,
                "validation_population": "NONE",
            },
        )
        self.assertEqual(len(manifest["raw_inputs"]), 9)
        for item in manifest["raw_inputs"]:
            lowered = f"/{item['path'].lower().strip('/')}/"
            self.assertIn("/r2/", lowered)
            self.assertNotIn("/r1/", lowered)
            self.assertNotIn("/r3/", lowered)
            self.assertNotIn("outcomes", lowered)
            self.assertEqual(item["line_count"], 8)
        for item in manifest["outputs"]:
            path = ROOT / item["path"]
            self.assertEqual(path.stat().st_size, item["bytes"])
            self.assertEqual(sha256_file(path), item["sha256"])
        with (MATERIALIZED / "quote_pair_availability_v1.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            pairs = list(csv.DictReader(handle))
        self.assertEqual(len(pairs), 36)
        self.assertTrue(all(row["buy_status"] == "QUOTE_AVAILABLE" for row in pairs))
        self.assertTrue(all(row["sell_status"] == "QUOTE_AVAILABLE" for row in pairs))
        with (MATERIALIZED / "panel_diagnostics_v1.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            diagnostics = list(csv.DictReader(handle))
        self.assertEqual(len(diagnostics), 9)
        self.assertTrue(
            all(row["quote_notional_capacity_proxy_usd"] == "100" for row in diagnostics)
        )
        self.assertEqual(
            {row["actual_elapsed_from_member_p0_seconds"] for row in diagnostics if row["panel_id"] == "P0"},
            {"0.0"},
        )
        for name in (
            "panel_inventory_v1.csv",
            "quote_pair_availability_v1.csv",
            "panel_diagnostics_v1.csv",
        ):
            self.assertEqual(
                sha256_file(PARTIAL_ATTEMPT / name),
                sha256_file(MATERIALIZED / name),
            )
        failure = json.loads(
            (ROOT / "docs/evidence/task23/a3_projection_attempt_01_failure_receipt_v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(failure["status"], "FAILED_RETAINED_NOT_ACCEPTED")
        self.assertEqual(failure["result_use"], "FORBIDDEN")

    def test_projection_materializes_exact_r2_tables_and_retains_no_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = SyntheticRepository(Path(directory))
            output = repo.root / "docs/evidence/task23/a3_projection_v1"
            manifest = build_projection(
                repo_root=repo.root,
                config_path=repo.config_path,
                receipt_path=repo.receipt_path,
                output_dir=Path("docs/evidence/task23/a3_projection_v1"),
            )
            self.assertEqual(manifest["status"], "MATERIALIZED_DETERMINISTIC_R2_ONLY")
            self.assertEqual(manifest["summary"]["planned_panels"], 9)
            self.assertEqual(manifest["summary"]["observed_panels"], 9)
            self.assertEqual(manifest["summary"]["planned_buy_legs"], 36)
            self.assertEqual(manifest["summary"]["observed_buy_legs"], 36)
            self.assertEqual(manifest["summary"]["eligible_dependent_sell_legs"], 35)
            self.assertEqual(manifest["summary"]["observed_dependent_sell_legs"], 35)
            self.assertEqual(manifest["summary"]["r2_value_files_opened"], 9)
            self.assertEqual(manifest["summary"]["r3_paths_discovered"], 0)
            self.assertEqual(manifest["summary"]["r3_value_files_opened"], 0)
            self.assertEqual(sorted(path.name for path in output.iterdir()), [
                "panel_diagnostics_v1.csv",
                "panel_inventory_v1.csv",
                "projection_manifest_v1.json",
                "quote_pair_availability_v1.csv",
            ])
            with (output / "quote_pair_availability_v1.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 36)
            no_route = [row for row in rows if row["buy_status"] == "NO_ROUTE"]
            self.assertEqual(len(no_route), 1)
            self.assertEqual(no_route[0]["sell_status"], "SELL_NOT_ATTEMPTED")
            self.assertEqual(no_route[0]["sell_eligible"], "false")
            with (output / "panel_diagnostics_v1.csv").open(encoding="utf-8", newline="") as handle:
                diagnostics = list(csv.DictReader(handle))
            affected = next(
                row for row in diagnostics
                if row["member_id"] == MEMBERS[0] and row["panel_id"] == "P1"
            )
            self.assertEqual(affected["quote_notional_capacity_proxy_usd"], "50")
            self.assertEqual(affected["inference_mode"], "DESCRIPTIVE_ONLY")

    def test_projection_is_create_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = SyntheticRepository(Path(directory))
            output = repo.root / "docs/evidence/task23/a3_projection_v1"
            build_projection(
                repo_root=repo.root,
                config_path=repo.config_path,
                receipt_path=repo.receipt_path,
                output_dir=Path("docs/evidence/task23/a3_projection_v1"),
            )
            with self.assertRaisesRegex(Task23ProjectionError, "output_directory_not_empty"):
                build_projection(
                    repo_root=repo.root,
                    config_path=repo.config_path,
                    receipt_path=repo.receipt_path,
                    output_dir=Path("docs/evidence/task23/a3_projection_v1"),
                )

    def test_r3_root_is_rejected_before_receipt_or_value_read(self) -> None:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        changed = copy.deepcopy(config)
        changed["r2_read_boundary"]["allowed_roots_after_a3_pre_read_receipt"][0] = (
            "local/task21_forward/final_cohort/r3/run=forbidden"
        )
        changed["r2_read_boundary"]["root_bindings"][0]["root"] = (
            "local/task21_forward/final_cohort/r3/run=forbidden"
        )
        with self.assertRaisesRegex(Task23ProjectionError, "root_not_r2|forbidden_root_fragment"):
            validate_config(changed)

    def test_wrong_code_hash_rejects_projection_before_raw_open(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = SyntheticRepository(Path(directory))
            receipt = json.loads(repo.receipt_path.read_text(encoding="utf-8"))
            receipt["bindings"]["projection_code"]["sha256"] = "0" * 64
            repo.receipt_path.write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(Task23ProjectionError, "receipt_projection_code_hash_mismatch"):
                build_projection(
                    repo_root=repo.root,
                    config_path=repo.config_path,
                    receipt_path=repo.receipt_path,
                    output_dir=repo.root / "docs/evidence/task23/a3_projection_v1",
                )


if __name__ == "__main__":
    unittest.main()
