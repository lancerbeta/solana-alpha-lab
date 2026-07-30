from __future__ import annotations

import base64
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task21_real_nomination_source import (  # noqa: E402
    ATOM_ID,
    COHORT_ID,
    EXTERNAL_AUTHORITY_PHRASE,
    SOURCE_ATOM_ID,
    TOKEN_2022_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    Task21NominationSourceAuthorityRequired,
    Task21NominationSourceError,
    Task21NominationSourceGate,
    build_offline_acceptance,
    replay_t1_from_retained_partition,
    select_profile_mints,
    validate_config,
    validate_rpc_mints,
)

CONFIG = ROOT / "configs/task21_real_nomination_source_v1.yaml"
FIXTURE = ROOT / "tests/fixtures/task21/geckoterminal_new_pools_offline_v1.json"
RECOVERY = ROOT / "docs/evidence/task21/runtime_recovery_gate_receipt_v1.json"
ACCEPTANCE = (
    ROOT / "docs/evidence/task21/real_nomination_source_offline_acceptance_v1.json"
)
FIXED_NOW = datetime(2026, 7, 30, 16, 0, tzinfo=UTC)
SOURCE_CAPTURED_AT = "2026-07-30T15:49:09.133Z"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def capture(
    *,
    kind: str,
    method: str,
    url: str,
    request: bytes,
    response: bytes,
    captured_at: str,
) -> dict:
    return {
        "request_kind": kind,
        "method": method,
        "url": url,
        "request_bytes": len(request),
        "request_sha256": hashlib.sha256(request).hexdigest(),
        "request_body_base64": base64.b64encode(request).decode("ascii"),
        "status": 200,
        "content_type": "application/json; charset=utf-8",
        "response_bytes": len(response),
        "response_sha256": hashlib.sha256(response).hexdigest(),
        "response_body_base64": base64.b64encode(response).decode("ascii"),
        "captured_at": captured_at,
    }


def rpc_request_bytes(mints: list[str]) -> bytes:
    return canonical(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getMultipleAccounts",
            "params": [
                mints,
                {
                    "commitment": "finalized",
                    "encoding": "base64",
                    "dataSlice": {"offset": 0, "length": 82},
                },
            ],
        }
    )


def copy_frozen_inputs(repo: Path, config: dict) -> None:
    for item in config["frozen_inputs"]:
        target = repo / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / item["path"]).read_bytes())


def prepare_temp_repo(temporary: str) -> tuple[Path, Path, dict, Path]:
    repo = Path(temporary)
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    copy_frozen_inputs(repo, config)
    profiles = fixture["dexscreener_response"]
    requested = select_profile_mints(profile_document=profiles, config=config)
    dex_response = canonical(profiles)
    rpc_response = canonical(fixture["solana_rpc_response"])
    observation = {
        "schema": "smial.task21.dexscreener-solana-source-observation",
        "schema_version": "1.0",
        "provider_sequence": ["DEXSCREENER", "SOLANA_PUBLIC_RPC"],
        "cohort_id": COHORT_ID,
        "network": "solana",
        "observed_at": SOURCE_CAPTURED_AT,
        "rpc_context_slot": 371000000,
        "superseded_source_attempts": [],
        "captures": [
            capture(
                kind="DEXSCREENER_LATEST_TOKEN_PROFILES",
                method="GET",
                url="https://api.dexscreener.com/token-profiles/latest/v1",
                request=b"",
                response=dex_response,
                captured_at="2026-07-30T15:49:08.843Z",
            ),
            capture(
                kind="SOLANA_GET_MULTIPLE_ACCOUNTS",
                method="POST",
                url="https://api.mainnet-beta.solana.com",
                request=rpc_request_bytes(requested),
                response=rpc_response,
                captured_at=SOURCE_CAPTURED_AT,
            ),
        ],
    }
    observation_sha = hashlib.sha256(canonical(observation)).hexdigest()
    source_partition = {
        "schema": "smial.task21.t1-nomination-partition",
        "schema_version": "1.0",
        "task_id": "TASK-21",
        "atom_id": SOURCE_ATOM_ID,
        "status": "T1_SOURCE_INSUFFICIENT_STOPPED",
        "contains_secrets": False,
        "source_observation": observation,
        "source_observation_sha256": observation_sha,
    }
    source_bytes = canonical(source_partition)
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    source_relative = (
        "local/task21_forward/t1_nomination/"
        f"TASK21_T1_NOMINATION_PARTITION_v1_{source_sha}.json"
    )
    config["replay"]["retained_source_partition"].update(
        {
            "path": source_relative,
            "bytes": len(source_bytes),
            "sha256": source_sha,
            "drive_file_id": "SYNTHETIC_OFFLINE_FIXTURE",
        }
    )
    source_path = repo / source_relative
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(source_bytes)
    config_target = repo / CONFIG.relative_to(ROOT)
    config_target.parent.mkdir(parents=True, exist_ok=True)
    config_target.write_text(
        yaml.safe_dump(config, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )
    return repo, config_target, config, source_path


class Task21RealNominationSourceTests(unittest.TestCase):
    def test_contract_and_live_retained_identity_are_exact(self) -> None:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        validate_config(config, ROOT)
        self.assertEqual(config["atom_id"], ATOM_ID)
        self.assertEqual(config["source_atom_id"], SOURCE_ATOM_ID)
        self.assertEqual(config["source"]["cohort_id"], COHORT_ID)
        retained = config["replay"]["retained_source_partition"]
        self.assertEqual(
            retained["sha256"],
            "b334eac617fefdfcd6b6f51e41697c7e1c56daff873b6a8587328c66dcfa759d",
        )
        self.assertEqual(retained["bytes"], 47195)
        self.assertTrue(retained["drive_exact_raw_readback"])
        self.assertEqual(
            config["budget_reconciliation"]["source_requests_whole_task_max"]
            + config["budget_reconciliation"]["quote_requests_whole_task_max"],
            192,
        )
        for item in config["frozen_inputs"]:
            self.assertEqual(digest(ROOT / item["path"]), item["sha256"])

    def test_external_gate_is_exact(self) -> None:
        with self.assertRaisesRegex(
            Task21NominationSourceAuthorityRequired, "phrase_mismatch"
        ):
            Task21NominationSourceGate("WRONG")
        self.assertEqual(
            Task21NominationSourceGate(
                EXTERNAL_AUTHORITY_PHRASE
            ).authority_phrase,
            "T21-A6S_T1_TOKEN2022_REPLAY_AND_BACKUP_V1",
        )

    def test_profile_selection_is_identity_only_order_independent(self) -> None:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        original = select_profile_mints(
            profile_document=fixture["dexscreener_response"],
            config=config,
        )
        mutated = copy.deepcopy(fixture["dexscreener_response"])
        mutated.reverse()
        for row in mutated:
            row["url"] = "changed"
            row["icon"] = "changed"
            row["header"] = "changed"
            row["description"] = "changed"
            row["links"] = [{"label": "changed"}]
        changed = select_profile_mints(
            profile_document=mutated,
            config=config,
        )
        self.assertEqual(original, changed)
        self.assertEqual(
            original,
            [
                "11111111111111111111111111111111",
                "4vJ9JU1bJJE96FWSJKvHsmmFADCg4gpZQff4P3bkLKi",
                "8qbHbw2BbbTHBW1sbeqakYXVKRQM8Ne7pLK7m6CVfeR",
                "CktRuQ2mttgRGkXJtyksdKHjUdc2C4TgDzyB98oEzy8",
            ],
        )

    def test_rpc_validation_accepts_legacy_and_token2022_mints(self) -> None:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        requested = select_profile_mints(
            profile_document=fixture["dexscreener_response"],
            config=config,
        )
        selected, slot = validate_rpc_mints(
            rpc_document=fixture["solana_rpc_response"],
            requested_mints=requested,
            config=config,
        )
        self.assertEqual(slot, 371000000)
        self.assertEqual([item.mint for item in selected], requested[1:])
        self.assertEqual([item.mint_decimals for item in selected], [6, 6, 9])
        self.assertEqual(
            [item.token_program for item in selected],
            [TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID, TOKEN_2022_PROGRAM_ID],
        )

    def test_uninitialized_token2022_header_is_rejected(self) -> None:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        requested = select_profile_mints(
            profile_document=fixture["dexscreener_response"],
            config=config,
        )
        rpc = copy.deepcopy(fixture["solana_rpc_response"])
        raw = bytearray(base64.b64decode(rpc["result"]["value"][2]["data"][0]))
        raw[45] = 0
        rpc["result"]["value"][2]["data"][0] = base64.b64encode(raw).decode("ascii")
        selected, _ = validate_rpc_mints(
            rpc_document=rpc,
            requested_mints=requested,
            config=config,
        )
        self.assertEqual(len(selected), 2)

    def test_replay_creates_three_events_without_network_or_backdating(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo, config_target, _, source_path = prepare_temp_repo(temporary)
            result = replay_t1_from_retained_partition(
                gate=Task21NominationSourceGate(EXTERNAL_AUTHORITY_PHRASE),
                repo_root=repo,
                config_path=config_target,
                recovery_receipt_path=repo / RECOVERY.relative_to(ROOT),
                now=FIXED_NOW,
            )
            self.assertEqual(result.nomination_count, 3)
            self.assertEqual(result.anchor_at, "2026-07-30T16:00:00.000Z")
            self.assertEqual(result.t1_close_at, "2026-08-06T16:00:00.000Z")
            self.assertTrue(source_path.is_file())
            self.assertTrue(result.partition_path.is_file())
            self.assertEqual(digest(result.partition_path), result.partition_sha256)
            partition = json.loads(result.partition_path.read_text("utf-8"))
            self.assertEqual(
                partition["status"],
                "T1_NOMINATIONS_FROZEN_AWAITING_CLOSE",
            )
            self.assertEqual(
                partition["timeline"]["source_capture_completed_at"],
                SOURCE_CAPTURED_AT,
            )
            self.assertEqual(
                partition["timeline"]["anchor_at"],
                "2026-07-30T16:00:00.000Z",
            )
            self.assertFalse(partition["timeline"]["backdating_allowed"])
            for event in partition["nomination_events"]:
                self.assertEqual(
                    event["first_reliable_available_at"],
                    "2026-07-30T16:00:00.000Z",
                )
            actions = partition["actual_actions"]
            self.assertEqual(actions["provider_api_rpc_wss_calls_this_stage"], 0)
            self.assertEqual(actions["dexscreener_api_calls_this_stage"], 0)
            self.assertEqual(actions["solana_public_rpc_calls_this_stage"], 0)
            self.assertEqual(actions["real_candidate_admissions"], 0)
            self.assertEqual(actions["jupiter_api_calls"], 0)

    def test_retained_hash_drift_blocks_before_derived_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo, config_target, config, source_path = prepare_temp_repo(temporary)
            source_path.write_bytes(source_path.read_bytes() + b" ")
            with self.assertRaisesRegex(
                Task21NominationSourceError, "hash_or_size_drift"
            ):
                replay_t1_from_retained_partition(
                    gate=Task21NominationSourceGate(
                        EXTERNAL_AUTHORITY_PHRASE
                    ),
                    repo_root=repo,
                    config_path=config_target,
                    recovery_receipt_path=repo / RECOVERY.relative_to(ROOT),
                    now=FIXED_NOW,
                )
            output = repo / config["replay"]["output_root"]
            self.assertFalse(output.exists())

    def test_stale_recovery_blocks_before_derived_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo, config_target, config, _ = prepare_temp_repo(temporary)
            with self.assertRaisesRegex(
                Task21NominationSourceError, "backup_stale"
            ):
                replay_t1_from_retained_partition(
                    gate=Task21NominationSourceGate(
                        EXTERNAL_AUTHORITY_PHRASE
                    ),
                    repo_root=repo,
                    config_path=config_target,
                    recovery_receipt_path=repo / RECOVERY.relative_to(ROOT),
                    now=FIXED_NOW + timedelta(hours=25),
                )
            output = repo / config["replay"]["output_root"]
            self.assertFalse(output.exists())

    def test_existing_output_blocks_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo, config_target, config, _ = prepare_temp_repo(temporary)
            output = repo / config["replay"]["output_root"]
            output.mkdir(parents=True)
            (output / "existing.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(
                Task21NominationSourceError, "output_already_exists"
            ):
                replay_t1_from_retained_partition(
                    gate=Task21NominationSourceGate(
                        EXTERNAL_AUTHORITY_PHRASE
                    ),
                    repo_root=repo,
                    config_path=config_target,
                    recovery_receipt_path=repo / RECOVERY.relative_to(ROOT),
                    now=FIXED_NOW,
                )

    def test_offline_acceptance_is_pass_and_has_zero_external_actions(self) -> None:
        receipt = build_offline_acceptance(
            repo_root=ROOT,
            config_path=CONFIG,
            fixture_path=FIXTURE,
        )
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["selected_count"], 3)
        self.assertEqual(
            receipt["selected_by_program"],
            {
                TOKEN_2022_PROGRAM_ID: 2,
                TOKEN_PROGRAM_ID: 1,
            },
        )
        self.assertTrue(receipt["selection_ignores_profile_marketing_fields"])
        self.assertTrue(receipt["selection_ignores_response_order"])
        for value in receipt["actual_actions"].values():
            self.assertEqual(value, 0)

    def test_tracked_offline_acceptance_matches_current_bytes(self) -> None:
        self.assertTrue(ACCEPTANCE.is_file())
        tracked = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
        expected = build_offline_acceptance(
            repo_root=ROOT,
            config_path=CONFIG,
            fixture_path=FIXTURE,
        )
        self.assertEqual(tracked["offline_receipt"], expected)
        self.assertEqual(
            tracked["offline_receipt_sha256"],
            hashlib.sha256(canonical(expected)).hexdigest(),
        )
        for artifact in tracked["artifacts"]:
            self.assertEqual(digest(ROOT / artifact["path"]), artifact["sha256"])


if __name__ == "__main__":
    unittest.main()
