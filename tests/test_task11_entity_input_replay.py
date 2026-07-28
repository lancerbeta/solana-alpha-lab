from __future__ import annotations

import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.run_task11_entity_input_probe import main  # noqa: E402
from solana_alpha_lab.entity_input_replay import (  # noqa: E402
    EntityReplayContractError,
    replay_entity_probe,
)
from solana_alpha_lab.entity_input_transport import (  # noqa: E402
    EXTERNAL_AUTHORITY_PHRASE,
    AccessAttestation,
    BoundedEntityTransport,
    DurableEntityProbeSink,
    EntityProbeRunner,
    ExternalExecutionGate,
    HeliusCredential,
    load_entity_pilot_plan,
)
from solana_alpha_lab.provider_smoke_transport import (  # noqa: E402
    BoundRequest,
    TransportResponse,
)

PLAN_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task11"
    / "entity_input_pilot_plan_v1.json"
)
EVIDENCE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "task11"
    / "entity_input_live_evidence_v1.json"
)
EVIDENCE_SHA256 = (
    "2c0e00c1aacb32a75cbe5807517e5e514751cec0271a540594147390e8fbf7b2"
)
RECEIPT_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task11"
    / "entity_input_pilot_execution_receipt_v1.json"
)
RECEIPT_SHA256 = (
    "324c9ace8c49668864c274de19c09d42a7e794169f9a5ad619df8b47f3209ff4"
)
SUMMARY_PATH = (
    ROOT
    / "docs"
    / "evidence"
    / "task11"
    / "entity_input_pilot_execution_summary_v1.md"
)
SUMMARY_SHA256 = (
    "457215a87621c858312c15a2b2963a0e8bf0e7857bbf4d1f7230c9b901ad0657"
)
MINT = "4vXNhA6ncbx8usZ14CfxkYeQKdaQYgrLfJXNyWcVpump"
RUN_ID = "t11a3-20260728T140000Z"
BASE_TIME = datetime(2026, 7, 28, 14, 0, tzinfo=UTC)


def _body(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _response(value: object, *, offset: int) -> TransportResponse:
    started = BASE_TIME + timedelta(seconds=offset)
    return TransportResponse(
        status_code=200,
        body=_body(value),
        safe_headers=(("content-type", "application/json"),),
        terminal_class="SUCCESS",
        error_class=None,
        request_started_at=started,
        request_sent_at=started,
        response_headers_at=started + timedelta(milliseconds=10),
        response_complete_at=started + timedelta(milliseconds=20),
    )


def _supply_body() -> dict[str, object]:
    return {
        "id": 1,
        "jsonrpc": "2.0",
        "result": {
            "context": {"apiVersion": "2.3.0", "slot": 100},
            "value": {
                "amount": "1000000",
                "decimals": 6,
                "uiAmount": 1.0,
                "uiAmountString": "1",
            },
        },
    }


def _largest_body() -> dict[str, object]:
    return {
        "id": 2,
        "jsonrpc": "2.0",
        "result": {
            "context": {"apiVersion": "2.3.0", "slot": 101},
            "value": [
                {
                    "address": "synthetic-token-account-a",
                    "amount": "400000",
                    "decimals": 6,
                    "uiAmount": 0.4,
                    "uiAmountString": "0.4",
                },
                {
                    "address": "synthetic-token-account-b",
                    "amount": "200000",
                    "decimals": 6,
                    "uiAmount": 0.2,
                    "uiAmountString": "0.2",
                },
            ],
        },
    }


def _owner_account(owner: str, amount: str) -> dict[str, object]:
    return {
        "data": {
            "parsed": {
                "info": {
                    "mint": MINT,
                    "owner": owner,
                    "tokenAmount": {
                        "amount": amount,
                        "decimals": 6,
                        "uiAmount": int(amount) / 1_000_000,
                        "uiAmountString": str(int(amount) / 1_000_000),
                    },
                },
                "type": "account",
            },
            "program": "spl-token",
            "space": 165,
        },
        "executable": False,
        "lamports": 2039280,
        "owner": "TokenProgramSynthetic1111111111111111111111",
        "rentEpoch": 18446744073709551615,
        "space": 165,
    }


def _owners_body() -> dict[str, object]:
    return {
        "id": 3,
        "jsonrpc": "2.0",
        "result": {
            "context": {"apiVersion": "2.3.0", "slot": 102},
            "value": [
                _owner_account("synthetic-owner-a", "400000"),
                _owner_account("synthetic-owner-b", "200000"),
            ],
        },
    }


class FakeExchange:
    def __init__(self) -> None:
        self.responses = [
            _response(_supply_body(), offset=1),
            _response(_largest_body(), offset=2),
            _response(_owners_body(), offset=3),
        ]
        self.requests: list[BoundRequest] = []

    def __call__(
        self,
        request: BoundRequest,
        *,
        max_response_bytes: int,
    ) -> TransportResponse:
        self.requests.append(request)
        response = self.responses.pop(0)
        if len(response.body) > max_response_bytes:
            raise RuntimeError("response_too_large")
        return response


def _create_synthetic_run(root: Path) -> None:
    plan = load_entity_pilot_plan(PLAN_PATH)
    credential = HeliusCredential("fixture-helius-key")
    gate = ExternalExecutionGate(EXTERNAL_AUTHORITY_PHRASE)
    transport = BoundedEntityTransport(
        plan=plan,
        credential=credential,
        gate=gate,
        http_exchange=FakeExchange(),
        clock=lambda: 0.0,
    )
    sink = DurableEntityProbeSink(
        raw_root=root,
        run_id=RUN_ID,
        plan=plan,
        credential=credential,
        now=lambda: BASE_TIME + timedelta(seconds=10),
    )
    result = EntityProbeRunner(
        plan=plan,
        transport=transport,
        sink=sink,
        access=AccessAttestation(True, 30),
    ).run()
    if result["terminal"] != "RAW_TOP20_FEASIBILITY_CAPTURED":
        raise AssertionError(result)


def _receipt_path(root: Path) -> Path:
    return (
        root
        / "task11_entity_input_probe_v1"
        / f"run={RUN_ID}"
        / "receipts"
        / "probe.receipt.json"
    )


class Task11EntityInputReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = load_entity_pilot_plan(PLAN_PATH)
        cls.evidence_bytes = EVIDENCE_PATH.read_bytes()
        cls.evidence = json.loads(cls.evidence_bytes)
        cls.receipt_bytes = RECEIPT_PATH.read_bytes()
        cls.receipt = json.loads(cls.receipt_bytes)
        cls.summary_bytes = SUMMARY_PATH.read_bytes()

    def test_portable_live_evidence_identity_and_boundary(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.evidence_bytes).hexdigest(),
            EVIDENCE_SHA256,
        )
        self.assertEqual(self.evidence["task_id"], "TASK-11")
        self.assertEqual(
            self.evidence["status"],
            "PASS_RAW_TOP20_ACCOUNT_CONCENTRATION_FEASIBILITY",
        )
        replay = self.evidence["replay_result"]
        self.assertEqual(replay["provider_calls"], 3)
        self.assertEqual(replay["retries"], 0)
        self.assertEqual(replay["modeled_credits"], 30)
        self.assertEqual(replay["cash_spend_usd_cents"], 0)
        self.assertEqual(replay["owner_resolution_count"], 20)
        self.assertEqual(replay["unresolved_exclusion_account_count"], 20)
        self.assertIsNone(replay["adjusted_top_accounts_supply_share"])
        self.assertEqual(
            replay["deployer_funder_bundler"],
            "NOT_TESTED",
        )
        self.assertFalse(
            self.evidence["decision_boundary"][
                "strategy_veto_or_alpha_established"
            ]
        )
        self.assertEqual(
            self.receipt["tracked_fixture"]["sha256"],
            EVIDENCE_SHA256,
        )
        self.assertEqual(
            self.receipt["source_run"]["runtime_receipt_sha256"],
            self.evidence["replay_result"]["receipt_sha256"],
        )
        self.assertEqual(
            self.receipt["accepted_result"]["raw_top_accounts_supply_share"],
            self.evidence["replay_result"][
                "raw_top_accounts_supply_share"
            ],
        )
        self.assertEqual(
            self.receipt["canonical_status_candidate"],
            "TECHNICAL_DOD_CANDIDATE_TASK11_REMAINS_IN_PROGRESS_UNTIL_MERGE_AND_FINISH_GATE",
        )
        self.assertEqual(
            hashlib.sha256(self.receipt_bytes).hexdigest(),
            RECEIPT_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(self.summary_bytes).hexdigest(),
            SUMMARY_SHA256,
        )
        summary = self.summary_bytes.decode("utf-8")
        self.assertIn(RECEIPT_SHA256, summary)
        self.assertIn("Adjusted concentration: `null`", summary)
        self.assertIn("TASK-11 remains `IN_PROGRESS`", summary)

    def test_catalog_registration_is_exact_and_raw_is_logical_only(
        self,
    ) -> None:
        manifest = yaml.safe_load(
            (ROOT / "catalog" / "catalog_manifest.yaml").read_text(
                encoding="utf-8"
            )
        )
        registry = yaml.safe_load(
            (ROOT / "catalog" / "assets" / "core.yaml").read_text(
                encoding="utf-8"
            )
        )
        records = {
            record["asset_id"]: record
            for record in registry["records"]
        }
        expected = {
            "CONTRACT-T11-ENTITY-INPUT-OBSERVATION-001",
            "MODULE-T11-ENTITY-INPUT-REDUCER-001",
            "MODULE-T11-ENTITY-INPUT-TRANSPORT-001",
            "MODULE-T11-ENTITY-INPUT-REPLAY-001",
            "SCRIPT-T11-ENTITY-INPUT-PROBE-001",
            "FIXTURE-T11-ENTITY-INPUT-OBSERVATION-001",
            "FIXTURE-T11-ENTITY-INPUT-PILOT-PLAN-001",
            "DATA-T11-ENTITY-INPUT-PILOT-RAW-001",
            "FIXTURE-T11-ENTITY-INPUT-LIVE-EVIDENCE-001",
            "EVIDENCE-T11-ENTITY-INPUT-RECEIPT-001",
            "EVIDENCE-T11-ENTITY-INPUT-SUMMARY-001",
            "TEST-T11-ENTITY-INPUT-OBSERVATION-001",
            "TEST-T11-ENTITY-INPUT-TRANSPORT-001",
            "TEST-T11-ENTITY-INPUT-REPLAY-001",
        }
        self.assertEqual(manifest["catalog_version"], "0.16.0")
        self.assertTrue(expected.issubset(records))
        self.assertTrue(
            expected.issubset(set(manifest["mandatory_asset_ids"]))
        )
        raw = records["DATA-T11-ENTITY-INPUT-PILOT-RAW-001"]
        self.assertEqual(raw["location"]["kind"], "logical_only")
        self.assertNotIn("repository_path", raw["location"])

    def test_fixture_is_sanitized_and_clean_clone_portable(self) -> None:
        text = self.evidence_bytes.decode("utf-8")
        lowered = text.lower()
        self.assertNotIn('"redacted_body"', lowered)
        self.assertNotIn('"response_headers"', lowered)
        self.assertNotIn('"request_headers"', lowered)
        self.assertNotIn('"api_key"', lowered)
        self.assertNotIn('"authorization"', lowered)
        self.assertNotIn("c:\\users\\", lowered)
        self.assertNotIn("/home/", lowered)
        self.assertEqual(
            self.evidence["sanitization"]["provider_bodies_in_fixture"],
            0,
        )
        self.assertEqual(
            self.evidence["sanitization"]["owner_addresses_in_fixture"],
            0,
        )

    def test_synthetic_run_replays_to_five_entity_rows(self) -> None:
        with tempfile.TemporaryDirectory(prefix="task11_replay_ok_") as tmp:
            root = Path(tmp).resolve()
            _create_synthetic_run(root)
            result = replay_entity_probe(
                raw_root=root,
                plan=self.plan,
                run_id=RUN_ID,
            )
        self.assertEqual(
            result["accepted_claim"],
            "RAW_TOP20_ACCOUNT_CONCENTRATION_FEASIBILITY",
        )
        self.assertEqual(result["raw_top_accounts_amount_atomic"], 600_000)
        self.assertEqual(result["raw_top_accounts_supply_share"], "0.6")
        self.assertEqual(result["owner_resolution_count"], 2)
        self.assertEqual(result["unresolved_exclusion_account_count"], 2)
        self.assertIsNone(result["adjusted_top_accounts_supply_share"])
        self.assertEqual(result["projection"]["row_count"], 5)

    def test_receipt_summary_tamper_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="task11_replay_receipt_") as tmp:
            root = Path(tmp).resolve()
            _create_synthetic_run(root)
            path = _receipt_path(root)
            document = json.loads(path.read_text(encoding="utf-8"))
            document["completed_calls"] = 2
            path.write_text(
                json.dumps(
                    document,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(
                EntityReplayContractError,
                "receipt_completed_calls_drift",
            ):
                replay_entity_probe(
                    raw_root=root,
                    plan=self.plan,
                    run_id=RUN_ID,
                )

    def test_partition_byte_tamper_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="task11_replay_parquet_") as tmp:
            root = Path(tmp).resolve()
            _create_synthetic_run(root)
            document = json.loads(
                _receipt_path(root).read_text(encoding="utf-8")
            )
            path = root / document["attempts"][0]["logical_location"]
            data = bytearray(path.read_bytes())
            data[-1] ^= 1
            path.write_bytes(data)
            with self.assertRaisesRegex(
                EntityReplayContractError,
                "partition_file_hash_mismatch",
            ):
                replay_entity_probe(
                    raw_root=root,
                    plan=self.plan,
                    run_id=RUN_ID,
                )

    def test_unknown_receipt_key_and_unsafe_run_id_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="task11_replay_shape_") as tmp:
            root = Path(tmp).resolve()
            _create_synthetic_run(root)
            path = _receipt_path(root)
            document = json.loads(path.read_text(encoding="utf-8"))
            changed = copy.deepcopy(document)
            changed["credential"] = "forbidden"
            path.write_text(
                json.dumps(
                    changed,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(
                EntityReplayContractError,
                "receipt_unknown_keys",
            ):
                replay_entity_probe(
                    raw_root=root,
                    plan=self.plan,
                    run_id=RUN_ID,
                )
        with self.assertRaisesRegex(
            EntityReplayContractError,
            "run_id_invalid",
        ):
            replay_entity_probe(
                raw_root=ROOT.resolve(),
                plan=self.plan,
                run_id="../escape",
            )

    def test_cli_replay_path_is_offline_and_sanitized(self) -> None:
        with tempfile.TemporaryDirectory(prefix="task11_replay_cli_") as tmp:
            root = Path(tmp).resolve()
            _create_synthetic_run(root)
            stream = io.StringIO()
            with redirect_stdout(stream):
                code = main(
                    ["--replay-run", RUN_ID],
                    input_fn=lambda _: self.fail("input_forbidden"),
                    secret_input_fn=lambda _: self.fail(
                        "secret_input_forbidden"
                    ),
                    raw_root=root,
                )
            output = stream.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("TASK11_ENTITY_REPLAY: PASS", output)
        self.assertNotIn("fixture-helius-key", output)


if __name__ == "__main__":
    unittest.main()
