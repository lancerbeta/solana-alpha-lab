from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.factory.data_resolver import (  # noqa: E402
    EvidenceResolutionError,
    resolve_evidence_bindings,
    resolve_query_recipe_hashes,
)
from solana_alpha_lab.factory.lane_classifier import (  # noqa: E402
    Lane,
    LaneDecision,
    classify_lane,
)
from solana_alpha_lab.factory.research_store import (  # noqa: E402
    RecordKind,
    ResearchEvent,
    ResearchStore,
    ResearchStoreError,
)
from solana_alpha_lab.factory.run_passport import (  # noqa: E402
    RunPassport,
    canonical_json_bytes,
    canonical_sha256,
    compute_run_key_sha256,
    experiment_spec_sha256,
)


AS_OF = datetime(2026, 8, 25, tzinfo=UTC)
OFFLINE_CAPABILITY = "CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001"
LIVE_CAPABILITY = "CAP-FIXTURE-PROVIDER-READ-ONLY-001"
JUPITER_CAPABILITY = "CAP-JUPITER-FREE-KEY-QUOTE-NATIVE-BOUNDED-CAPTURE-001"
GIT_WRITING_CAPABILITY = "CAP-FIXTURE-GIT-RECEIPT-WRITER-001"
DATA_BINDING_ID = "BINDING-CANONICAL-RECEIPT-001"
HYPOTHESIS_DEFINITION_SHA256 = "1" * 64
CATALOG_ASSET_CONTENT_SHA256 = hashlib.sha256(
    (ROOT / "catalog/schemas/experiment_spec.schema.json").read_bytes()
).hexdigest()
RUN_KEY_INPUTS = {
    "hypothesis_definition_sha256": HYPOTHESIS_DEFINITION_SHA256,
    "capability_closure_sha256": "2" * 64,
    "runner_git_sha": "3" * 40,
    "uv_lock_sha256": "4" * 64,
    "ordered_input_dataset_manifest_ids": ["DATASET-MANIFEST-001"],
    "ordered_input_dataset_fingerprints": ["5" * 64],
    "ordered_query_recipe_sha256s": [],
    "config_sha256": "6" * 64,
    "holdout_consumption_ids": ["HOLDOUT-CONSUMPTION-001"],
    "random_seed_or_null": None,
}


def experiment_spec(*, capability_id: str = OFFLINE_CAPABILITY) -> dict[str, object]:
    return {
        "schema": "smial.experiment-spec",
        "schema_version": "1.1",
        "experiment_id": "EXP-HYPOTHESIS-FAST-LANE-001",
        "hypothesis_version": "HYP-VERSION-FAST-LANE-V1",
        "question": "Does the accepted offline receipt support this falsifier?",
        "estimand": "Typed terminal agreement",
        "population": "Accepted canonical receipt fixture",
        "data_requirements": [
            {
                "requirement_id": "CANONICAL_RECEIPT",
                "kind": "CATALOG_ASSET",
                "path": "catalog/catalog_manifest.yaml",
                "sha256": "0" * 64,
            }
        ],
        "capabilities": [capability_id],
        "falsifier": "The typed terminal does not agree",
        "method": "classify_audition_terminal",
        "parameters": {},
        "evidence_budget": {
            "provider_api_rpc_wss_calls": (
                60
                if capability_id == JUPITER_CAPABILITY
                else 1
                if capability_id == LIVE_CAPABILITY
                else 0
            )
        },
        "holdout_policy": "No holdout is opened by classification",
        "terminal_outcomes": ["SUPPORTED", "FALSIFIED", "INCONCLUSIVE"],
        "data_bindings": [
            {
                "binding_id": DATA_BINDING_ID,
                "source_kind": "CATALOG_ASSET",
                "stable_id": "SCHEMA-EXPERIMENT-SPEC-001",
                "expected_content_sha256_or_dataset_fingerprint": (
                    CATALOG_ASSET_CONTENT_SHA256
                ),
            }
        ],
        "query_recipe_ids": [],
        "capability_id": capability_id,
        "parameter_schema_asset_id": "SCHEMA-EXPERIMENT-SPEC-001",
        "as_of": "2026-08-25T00:00:00Z",
        "availability_cutoff": "2026-08-25T00:00:00Z",
        "what_changed": ["INITIAL_FAST_LANE_FIXTURE"],
    }


def submission(
    *,
    capability_id: str = OFFLINE_CAPABILITY,
    available: bool = True,
    promotion_requested: bool = False,
    completed_runs: dict[str, str] | None = None,
    run_key_inputs: dict[str, object] | None = None,
) -> dict[str, object]:
    packet = {
        "experiment_spec": experiment_spec(capability_id=capability_id),
        "hypothesis_definition_sha256": HYPOTHESIS_DEFINITION_SHA256,
        "available_data_binding_ids": [DATA_BINDING_ID] if available else [],
        "completed_runs": dict(completed_runs or {}),
        "promotion_requested": promotion_requested,
    }
    if run_key_inputs is not None:
        packet["run_key_inputs"] = dict(run_key_inputs)
    return packet


def expected_run_key(
    spec: dict[str, object],
    run_key_inputs: dict[str, object],
) -> str:
    spec_without_prose = dict(spec)
    spec_without_prose.pop("what_changed", None)
    for field in ("capabilities", "required_feature_ids", "terminal_outcomes"):
        if field in spec_without_prose:
            spec_without_prose[field] = sorted(spec_without_prose[field])
    spec_canonical = json.dumps(
        spec_without_prose,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    payload = {
        **run_key_inputs,
        "experiment_spec_sha256": hashlib.sha256(spec_canonical).hexdigest(),
        "capability_id": spec["capability_id"],
        "ordered_query_recipe_ids": spec["query_recipe_ids"],
        "as_of": spec["as_of"],
        "availability_cutoff": spec["availability_cutoff"],
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def run_key_inputs_for(
    spec: dict[str, object],
    *,
    capability_closure_sha256: str = "2" * 64,
    uv_lock_sha256: str = "4" * 64,
) -> dict[str, object]:
    return {
        "hypothesis_definition_sha256": HYPOTHESIS_DEFINITION_SHA256,
        "experiment_spec_sha256": experiment_spec_sha256(spec),
        "capability_id": str(spec["capability_id"]),
        "capability_closure_sha256": capability_closure_sha256,
        "runner_git_sha": "3" * 40,
        "uv_lock_sha256": uv_lock_sha256,
        "ordered_input_dataset_manifest_ids": [],
        "ordered_input_dataset_fingerprints": [],
        "ordered_query_recipe_ids": [],
        "ordered_query_recipe_sha256s": [],
        "config_sha256": canonical_sha256(spec["parameters"]),
        "as_of": str(spec["as_of"]),
        "availability_cutoff": str(spec["availability_cutoff"]),
        "holdout_consumption_ids": [],
        "random_seed_or_null": None,
    }


def completed_run_payload(run_id: str, run_key_sha256: str) -> dict[str, object]:
    return {
        "run_id": run_id,
        "run_key_sha256": run_key_sha256,
        "trial_id": "TRIAL-FAST-LANE-DUPLICATE-001",
        "hypothesis_version_id": "HYP-VERSION-FAST-LANE-V1",
        "hypothesis_definition_sha256": HYPOTHESIS_DEFINITION_SHA256,
        "experiment_spec_sha256": "2" * 64,
        "runner_capability_id": OFFLINE_CAPABILITY,
        "runner_git_sha": "3" * 40,
        "capability_closure_sha256": "4" * 64,
        "uv_lock_sha256": "5" * 64,
        "dataset_manifest_ids": [],
        "dataset_fingerprints": [],
        "query_recipe_ids": [],
        "query_recipe_sha256s": [],
        "config_sha256": "6" * 64,
        "as_of": "2026-08-25T00:00:00Z",
        "availability_cutoff": "2026-08-25T00:00:00Z",
        "holdout_consumption_ids": [],
        "random_seed_or_null": None,
        "started_at": "2026-08-25T00:00:00Z",
        "completed_at": "2026-08-25T00:01:00Z",
        "first_reliable_available_at": "2026-08-25T00:01:00Z",
        "provider_calls_planned": 0,
        "provider_calls_actual": 0,
        "cash_spend_usd_cents": 0,
        "execution_status": "COMPLETE",
        "trial_outcome": "INCONCLUSIVE",
        "scientific_terminal": "INCONCLUSIVE",
        "result_digest_sha256": "7" * 64,
        "artifact_manifest_sha256": "8" * 64,
        "limitations": [],
        "non_claims": [],
    }


def completed_run_event(run_id: str, run_key_sha256: str) -> ResearchEvent:
    payload = completed_run_payload(run_id, run_key_sha256)
    payload_json = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return ResearchEvent(
        record_id="RUN-COMPLETED-FAST-LANE-DUPLICATE-001",
        record_kind=RecordKind.RUN_COMPLETED,
        entity_id=run_id,
        hypothesis_version_id="HYP-VERSION-FAST-LANE-V1",
        run_id=run_id,
        transaction_id="RESEARCH-TXN-FAST-LANE-DUPLICATE-001",
        effective_at=AS_OF,
        first_reliable_available_at=AS_OF,
        supersedes_record_id=None,
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        schema_version="1.0",
        producer_capability_id=OFFLINE_CAPABILITY,
        producer_git_sha="9" * 40,
        created_at=AS_OF,
    )


def dataset_manifest_payload(
    *,
    manifest_id: str,
    fingerprint: str,
    first_reliable_available_at: str = "2026-08-25T00:00:00Z",
) -> dict[str, object]:
    return {
        "dataset_manifest_id": manifest_id,
        "dataset_id": "fast-lane-fixture",
        "dataset_version": "1.0",
        "schema_id": "SCHEMA-EXPERIMENT-SPEC-001",
        "schema_sha256": "a" * 64,
        "dataset_fingerprint": fingerprint,
        "generation_task_id": "TASK-4",
        "generation_run_id": "RUN-DATASET-FIXTURE-001",
        "validation_receipt_sha256": "b" * 64,
        "first_reliable_available_at": first_reliable_available_at,
        "created_at": "2026-08-25T00:00:00Z",
        "content_sha256": "c" * 64,
    }


def write_dataset_manifest(
    data_root: Path,
    payload: dict[str, object],
) -> Path:
    target = (
        data_root
        / "datasets"
        / "manifests"
        / f"{payload['dataset_manifest_id']}.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return target


class FastLaneContractTests(unittest.TestCase):
    def classify(self, packet: dict[str, object]) -> LaneDecision:
        with tempfile.TemporaryDirectory() as tmp:
            return classify_lane(
                packet,
                root=ROOT,
                data_root=Path(tmp),
                as_of=AS_OF,
            )

    def test_v1_1_schema_preserves_v1_fields_and_validates_fast_lane_fixture(self) -> None:
        schema = json.loads(
            (ROOT / "catalog/schemas/experiment_spec_v1_1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        jsonschema.validate(experiment_spec(), schema)
        self.assertEqual(schema["properties"]["schema_version"]["const"], "1.1")
        for required in (
            "data_requirements",
            "capabilities",
            "data_bindings",
            "query_recipe_ids",
            "capability_id",
            "parameter_schema_asset_id",
            "as_of",
            "availability_cutoff",
            "what_changed",
        ):
            self.assertIn(required, schema["required"])

    def test_capability_registry_descriptors_validate_and_freeze_required_fixtures(
        self,
    ) -> None:
        descriptor_schema = json.loads(
            (
                ROOT / "catalog/schemas/experiment_capability_descriptor.schema.json"
            ).read_text(encoding="utf-8")
        )
        registry = yaml.safe_load(
            (ROOT / "configs/experiment_capability_registry_v1.yaml").read_text(
                encoding="utf-8"
            )
        )
        descriptors = {
            item["capability_id"]: item for item in registry["capabilities"]
        }
        for descriptor in descriptors.values():
            jsonschema.validate(descriptor, descriptor_schema)
        self.assertEqual(descriptors[OFFLINE_CAPABILITY]["status"], "ACCEPTED")
        self.assertEqual(
            descriptors[OFFLINE_CAPABILITY]["effect_class"], "OFFLINE_READ_ONLY"
        )
        self.assertEqual(
            descriptors[OFFLINE_CAPABILITY]["output_zone"], "DATA_ROOT_ONLY"
        )
        self.assertEqual(
            descriptors[GIT_WRITING_CAPABILITY]["output_zone"], "GIT_REPOSITORY"
        )
        self.assertEqual(
            descriptors[LIVE_CAPABILITY]["effect_class"],
            "PROVIDER_READ_ONLY_BOUNDED",
        )
        self.assertEqual(
            descriptors[JUPITER_CAPABILITY]["effect_class"],
            "PROVIDER_READ_ONLY_BOUNDED",
        )
        self.assertEqual(descriptors[JUPITER_CAPABILITY]["max_provider_calls"], 60)
        self.assertEqual(
            descriptors[JUPITER_CAPABILITY]["provider_policy_asset_id"],
            "CONFIG-PROVIDER-ROUTE-CAPABILITY-REGISTRY-009",
        )

    def test_non_provider_descriptor_cannot_claim_provider_calls(self) -> None:
        descriptor_schema = json.loads(
            (
                ROOT / "catalog/schemas/experiment_capability_descriptor.schema.json"
            ).read_text(encoding="utf-8")
        )
        registry = yaml.safe_load(
            (ROOT / "configs/experiment_capability_registry_v1.yaml").read_text(
                encoding="utf-8"
            )
        )
        descriptor = dict(registry["capabilities"][0])
        descriptor["max_provider_calls"] = 1
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(descriptor, descriptor_schema)

    def test_fast_lane_config_is_logical_and_freezes_two_rung(self) -> None:
        config = yaml.safe_load(
            (ROOT / "configs/hypothesis_fast_lane_v1.yaml").read_text(
                encoding="utf-8"
            )
        )
        rendered = json.dumps(config, sort_keys=True)
        self.assertEqual(
            config["two_rung_live_h900_v1"]["status"],
            "FROZEN_PENDING_FAST_LANE",
        )
        self.assertEqual(config["foundation_authority"]["provider_calls"], 0)
        self.assertEqual(
            config["writer_lease_policy"], "CREATE_EXCLUSIVE_SINGLE_WRITER_V1"
        )
        self.assertNotIn("C:\\", rendered)
        self.assertNotIn("/Users/", rendered)
        self.assertNotIn("/home/", rendered)
        self.assertNotIn("SMIAL_DATA_ROOT:", rendered)

    def test_lane_decision_is_frozen(self) -> None:
        decision = self.classify(submission())
        with self.assertRaises(FrozenInstanceError):
            decision.terminal = "MUTATED"  # type: ignore[misc]

    def test_existing_offline_capability_is_fast_lane(self) -> None:
        decision = self.classify(submission())
        self.assertIs(decision.lane, Lane.FAST_LANE)
        self.assertEqual(decision.terminal, "FAST_LANE_READY")
        self.assertEqual(decision.reason_codes, ())
        self.assertIsNotNone(decision.run_key_sha256)
        self.assertIsNone(decision.prior_run_id)

    def test_owner_gated_live_capability_requires_authority_without_calling_provider(
        self,
    ) -> None:
        decision = self.classify(submission(capability_id=LIVE_CAPABILITY))
        self.assertIs(decision.lane, Lane.FAST_LANE)
        self.assertEqual(decision.terminal, "FAST_LANE_OWNER_GATE_REQUIRED")
        self.assertEqual(decision.reason_codes, ("OWNER_AUTHORITY_REQUIRED",))

    def test_jupiter_bounded_capture_requires_owner_gate_without_calling_provider(
        self,
    ) -> None:
        decision = self.classify(submission(capability_id=JUPITER_CAPABILITY))
        self.assertIs(decision.lane, Lane.FAST_LANE)
        self.assertEqual(decision.terminal, "FAST_LANE_OWNER_GATE_REQUIRED")
        self.assertEqual(decision.reason_codes, ("OWNER_AUTHORITY_REQUIRED",))
        self.assertEqual(decision.next_action, "PROVIDE_EXACT_OWNER_AUTHORITY")

    def test_two_rung_commissioning_packet_reaches_owner_gate_without_provider_entrypoint(
        self,
    ) -> None:
        packet = json.loads(
            (
                ROOT
                / "tests/fixtures/fast_lane/two_rung_live_h900_classify_packet_v1.json"
            ).read_text(encoding="utf-8")
        )
        with patch(
            "solana_alpha_lab.factory.capabilities.capture_quote_native_free_key"
        ) as capture:
            decision = self.classify(packet)
        capture.assert_not_called()
        self.assertIs(decision.lane, Lane.FAST_LANE)
        self.assertEqual(decision.terminal, "FAST_LANE_OWNER_GATE_REQUIRED")
        self.assertEqual(decision.reason_codes, ("OWNER_AUTHORITY_REQUIRED",))
        self.assertEqual(decision.next_action, "PROVIDE_EXACT_OWNER_AUTHORITY")
        self.assertEqual(
            packet["experiment_spec"]["evidence_budget"]["provider_api_rpc_wss_calls"],
            60,
        )

    def test_offline_capability_rejects_requested_provider_calls(self) -> None:
        packet = submission()
        packet["experiment_spec"]["evidence_budget"][  # type: ignore[index]
            "provider_api_rpc_wss_calls"
        ] = 1
        decision = self.classify(packet)
        self.assertIs(decision.lane, Lane.CHANGE_LANE)
        self.assertEqual(decision.reason_codes, ("GUARDRAIL_CHANGE_REQUIRED",))

    def test_missing_capability_requires_change_lane(self) -> None:
        decision = self.classify(
            submission(capability_id="CAP-FIXTURE-NOT-REGISTERED-001")
        )
        self.assertIs(decision.lane, Lane.CHANGE_LANE)
        self.assertEqual(decision.terminal, "CHANGE_LANE_CAPABILITY_GAP")
        self.assertEqual(decision.reason_codes, ("CAPABILITY_NOT_REGISTERED",))

    def test_repo_writing_capability_requires_change_lane(self) -> None:
        decision = self.classify(submission(capability_id=GIT_WRITING_CAPABILITY))
        self.assertIs(decision.lane, Lane.CHANGE_LANE)
        self.assertEqual(decision.terminal, "CHANGE_LANE_CAPABILITY_GAP")
        self.assertEqual(decision.reason_codes, ("OUTPUT_SINK_NOT_DATA_PLANE",))

    def test_invalid_spec_is_denied_before_other_lanes(self) -> None:
        packet = submission(
            capability_id="CAP-FIXTURE-NOT-REGISTERED-001",
            promotion_requested=True,
        )
        del packet["experiment_spec"]["estimand"]  # type: ignore[index]
        decision = self.classify(packet)
        self.assertIs(decision.lane, Lane.DENY)
        self.assertEqual(decision.terminal, "DENY_INVALID_SPEC")

    def test_absolute_spec_input_path_is_denied(self) -> None:
        for physical_path in (
            "C:\\private\\receipt.json",
            "\\private\\receipt.json",
            "C:private\\receipt.json",
            "/private/receipt.json",
        ):
            with self.subTest(physical_path=physical_path):
                packet = submission()
                packet["experiment_spec"]["data_requirements"][0][  # type: ignore[index]
                    "path"
                ] = physical_path
                decision = self.classify(packet)
                self.assertIs(decision.lane, Lane.DENY)
                self.assertEqual(
                    decision.reason_codes,
                    ("EXPERIMENT_SPEC_INVALID",),
                )

    def test_missing_immutable_binding_is_blocked_data(self) -> None:
        packet = submission()
        packet["experiment_spec"]["data_bindings"] = [  # type: ignore[index]
            {
                "binding_id": "BINDING-DATASET-MISSING-001",
                "source_kind": "DATASET_MANIFEST",
                "stable_id": "DATASET-MANIFEST-MISSING-001",
                "expected_content_sha256_or_dataset_fingerprint": "a" * 64,
            }
        ]
        decision = self.classify(packet)
        self.assertIs(decision.lane, Lane.FAST_LANE)
        self.assertEqual(decision.terminal, "BLOCKED_DATA")
        self.assertEqual(
            decision.reason_codes,
            ("DATA_BINDING_UNAVAILABLE",),
        )

    def test_exact_duplicate_returns_replay_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            initial = classify_lane(
                submission(),
                root=ROOT,
                data_root=data_root,
                as_of=AS_OF,
            )
            self.assertIsNotNone(initial.run_key_sha256)
            run_id = "RUN-FAST-LANE-DUPLICATE-001"
            ResearchStore(data_root).append(
                [completed_run_event(run_id, str(initial.run_key_sha256))],
                transaction_id="RESEARCH-TXN-FAST-LANE-DUPLICATE-001",
            )
            decision = classify_lane(
                submission(),
                root=ROOT,
                data_root=data_root,
                as_of=AS_OF,
            )
        self.assertIs(decision.lane, Lane.FAST_LANE)
        self.assertEqual(decision.terminal, "REPLAY_AVAILABLE")
        self.assertEqual(decision.run_key_sha256, initial.run_key_sha256)
        self.assertEqual(decision.prior_run_id, run_id)

    def test_completed_lookup_returns_a_validated_run_passport(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            run_id = "RUN-FAST-LANE-PASSPORT-001"
            run_key_sha256 = "a" * 64
            store = ResearchStore(data_root)
            store.append(
                [completed_run_event(run_id, run_key_sha256)],
                transaction_id="RESEARCH-TXN-FAST-LANE-DUPLICATE-001",
            )
            passport = store.find_completed_run(run_key_sha256)
        self.assertIsInstance(passport, RunPassport)
        self.assertEqual(passport.run_id, run_id)  # type: ignore[union-attr]
        self.assertNotIn("physical_path", passport.payload)  # type: ignore[union-attr]

    def test_completed_lookup_rejects_incomplete_run_passport(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            payload = {
                "run_id": "RUN-INCOMPLETE-PASSPORT-001",
                "run_key_sha256": "a" * 64,
            }
            payload_json = json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            store = ResearchStore(data_root)
            store.append(
                [
                    ResearchEvent(
                        record_id="RUN-COMPLETED-INCOMPLETE-PASSPORT-001",
                        record_kind=RecordKind.RUN_COMPLETED,
                        entity_id="RUN-INCOMPLETE-PASSPORT-001",
                        hypothesis_version_id=None,
                        run_id="RUN-INCOMPLETE-PASSPORT-001",
                        transaction_id="RESEARCH-TXN-INCOMPLETE-PASSPORT-001",
                        effective_at=AS_OF,
                        first_reliable_available_at=AS_OF,
                        supersedes_record_id=None,
                        payload_json=payload_json,
                        payload_sha256=hashlib.sha256(
                            payload_json.encode("utf-8")
                        ).hexdigest(),
                        schema_version="1.0",
                        producer_capability_id=OFFLINE_CAPABILITY,
                        producer_git_sha="9" * 40,
                        created_at=AS_OF,
                    )
                ],
                transaction_id="RESEARCH-TXN-INCOMPLETE-PASSPORT-001",
            )
            with self.assertRaisesRegex(
                ResearchStoreError,
                "RUN_COMPLETED_PASSPORT_INVALID",
            ):
                store.find_completed_run("a" * 64)

    def test_prose_only_what_changed_does_not_change_run_key(self) -> None:
        first_packet = submission(run_key_inputs=RUN_KEY_INPUTS)
        second_packet = submission(run_key_inputs=RUN_KEY_INPUTS)
        second_packet["experiment_spec"]["what_changed"] = [  # type: ignore[index]
            "PROSE_ONLY_DIFFERENCE"
        ]
        first = self.classify(first_packet)
        second = self.classify(second_packet)
        self.assertEqual(first.run_key_sha256, second.run_key_sha256)

    def test_capability_closure_change_changes_run_key(self) -> None:
        spec = experiment_spec()
        first = compute_run_key_sha256(run_key_inputs_for(spec))
        second = compute_run_key_sha256(
            run_key_inputs_for(spec, capability_closure_sha256="7" * 64)
        )
        self.assertNotEqual(first, second)

    def test_arbitrary_binding_path_is_denied(self) -> None:
        packet = submission()
        packet["experiment_spec"]["data_bindings"][0]["physical_path"] = (  # type: ignore[index]
            "C:\\private\\dataset.json"
        )
        decision = self.classify(packet)
        self.assertIs(decision.lane, Lane.DENY)
        self.assertEqual(decision.reason_codes, ("EXPERIMENT_SPEC_INVALID",))

    def test_catalog_asset_resolves_to_logical_evidence_without_physical_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            resolved = resolve_evidence_bindings(
                experiment_spec(),
                root=ROOT,
                data_root=Path(tmp),
            )
        self.assertEqual(len(resolved), 1)
        evidence = resolved[0]
        self.assertEqual(evidence.stable_id, "SCHEMA-EXPERIMENT-SPEC-001")
        self.assertEqual(evidence.content_sha256, CATALOG_ASSET_CONTENT_SHA256)
        self.assertEqual(
            evidence.logical_uri,
            "repo://catalog/schemas/experiment_spec.schema.json",
        )
        self.assertNotIn("physical_path", evidence.to_payload())

    def test_dataset_manifest_fingerprint_resolves_from_data_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            manifest_id = "DATASET-MANIFEST-FAST-LANE-001"
            fingerprint = "d" * 64
            physical_path = write_dataset_manifest(
                data_root,
                dataset_manifest_payload(
                    manifest_id=manifest_id,
                    fingerprint=fingerprint,
                ),
            )
            spec = experiment_spec()
            spec["data_bindings"] = [
                {
                    "binding_id": "BINDING-DATASET-FAST-LANE-001",
                    "source_kind": "DATASET_MANIFEST",
                    "stable_id": manifest_id,
                    "expected_content_sha256_or_dataset_fingerprint": fingerprint,
                }
            ]
            resolved = resolve_evidence_bindings(
                spec,
                root=ROOT,
                data_root=data_root,
            )
        self.assertEqual(resolved[0].dataset_fingerprint, fingerprint)
        self.assertEqual(resolved[0].physical_path, physical_path)
        self.assertIsNone(resolved[0].content_sha256)

    def test_dataset_fingerprint_mismatch_is_an_integrity_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            manifest_id = "DATASET-MANIFEST-FAST-LANE-001"
            write_dataset_manifest(
                data_root,
                dataset_manifest_payload(
                    manifest_id=manifest_id,
                    fingerprint="d" * 64,
                ),
            )
            spec = experiment_spec()
            spec["data_bindings"] = [
                {
                    "binding_id": "BINDING-DATASET-FAST-LANE-001",
                    "source_kind": "DATASET_MANIFEST",
                    "stable_id": manifest_id,
                    "expected_content_sha256_or_dataset_fingerprint": "e" * 64,
                }
            ]
            with self.assertRaisesRegex(
                EvidenceResolutionError,
                "EVIDENCE_HASH_MISMATCH",
            ):
                resolve_evidence_bindings(spec, root=ROOT, data_root=data_root)

    def test_query_recipe_hash_uses_canonical_catalog_recipe_bytes(self) -> None:
        recipe_id = "QUERY-CATALOG-VALIDATE-001"
        recipes = yaml.safe_load(
            (ROOT / "catalog/query_recipes.yaml").read_text(encoding="utf-8")
        )["recipes"]
        recipe = next(item for item in recipes if item["recipe_id"] == recipe_id)
        self.assertEqual(
            resolve_query_recipe_hashes([recipe_id], root=ROOT),
            ((recipe_id, canonical_sha256(recipe)),),
        )

    def test_evidence_after_pit_cutoff_is_blocked_data(self) -> None:
        packet = submission()
        packet["experiment_spec"]["availability_cutoff"] = "2026-08-18T00:00:00Z"  # type: ignore[index]
        decision = self.classify(packet)
        self.assertIs(decision.lane, Lane.FAST_LANE)
        self.assertEqual(decision.terminal, "BLOCKED_DATA")
        self.assertEqual(
            decision.reason_codes,
            ("EVIDENCE_UNAVAILABLE_AT_CUTOFF",),
        )

    def test_canonical_decimal_and_set_fields_are_deterministic(self) -> None:
        self.assertEqual(
            canonical_json_bytes({"amount": Decimal("1.2300")}),
            b'{"amount":"1.23"}',
        )
        first = experiment_spec()
        second = experiment_spec()
        second["terminal_outcomes"] = list(
            reversed(second["terminal_outcomes"])  # type: ignore[index]
        )
        second["what_changed"] = ["PROSE_ONLY_DIFFERENCE"]
        self.assertEqual(
            experiment_spec_sha256(first),
            experiment_spec_sha256(second),
        )

    def test_uv_lock_hash_participates_in_canonical_run_key(self) -> None:
        spec = experiment_spec()
        actual = hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest()
        self.assertNotEqual(
            compute_run_key_sha256(
                run_key_inputs_for(spec, uv_lock_sha256=actual)
            ),
            compute_run_key_sha256(
                run_key_inputs_for(spec, uv_lock_sha256="f" * 64)
            ),
        )

    def test_run_passport_rejects_physical_path_leak(self) -> None:
        payload = completed_run_payload("RUN-PASSPORT-001", "a" * 64)
        payload["physical_path"] = "C:\\private\\passport.json"
        with self.assertRaises(ValueError):
            RunPassport.model_validate(payload)

    def test_dirty_referenced_implementation_requires_change_lane(self) -> None:
        with patch(
            "solana_alpha_lab.factory.lane_classifier._git_show_bytes",
            return_value=b"dirty implementation",
        ):
            decision = self.classify(submission())
        self.assertIs(decision.lane, Lane.CHANGE_LANE)
        self.assertEqual(
            decision.reason_codes,
            ("IMPLEMENTATION_HASH_MISMATCH",),
        )

    def test_promotion_request_cannot_enter_fast_lane(self) -> None:
        decision = self.classify(submission(promotion_requested=True))
        self.assertIs(decision.lane, Lane.PROMOTION_LANE)
        self.assertEqual(decision.terminal, "PROMOTION_LANE_REQUIRED")
        self.assertEqual(decision.reason_codes, ("PROMOTION_REQUESTED",))


if __name__ == "__main__":
    unittest.main()
