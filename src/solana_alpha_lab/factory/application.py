"""Command gateway over existing contracts. The UI must not write registries directly."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

import yaml

from solana_alpha_lab.factory.cockpit import pinned_produced_gaps, project_cockpit
from solana_alpha_lab.factory.experiment_spec import load_experiment_spec, requirement_map
from solana_alpha_lab.factory.operational_store import OperationalStore, OperationalStoreError
from solana_alpha_lab.factory.paper_plane import PaperPlaneError, PaperPlaneStore
from solana_alpha_lab.factory.paper_shadow_commands import apply_operator_command
from solana_alpha_lab.factory.paper_shadow_operations import (
    build_economics_projection,
    build_operations_projection,
)
from solana_alpha_lab.factory.read_model import project_read_model
from solana_alpha_lab.factory.trading_operations import compose_trading_operations
from solana_alpha_lab.factory.runner import ExperimentRunner, ExperimentRunnerError

HYPOTHESES_RELATIVE = "registries/hypotheses.yaml"
RESEARCH_CYCLES_RELATIVE = "registries/research_cycles.yaml"
KERNEL_CONFIG_RELATIVE = "configs/factory_v1_product_kernel_v1.yaml"
COMMISSIONING_CONFIG_RELATIVE = "configs/factory_v1_commissioning_v1.yaml"
FRICTION_VETO_CONFIG_RELATIVE = "configs/factory_v1_friction_veto_v1.yaml"
T0_FRICTION_SCREEN_CONFIG_RELATIVE = "configs/factory_v1_prior_git_t0_friction_screen_v1.yaml"
RETENTION_CONFIG_RELATIVE = "configs/factory_v1_quote_surface_retention_falsifier_v1.yaml"
CONFIRMATORY_CONFIG_RELATIVE = "configs/factory_v1_quote_surface_retention_confirmatory_v1.yaml"
RUNTIME_CONFIG_RELATIVE = "configs/factory_v1_production_lite_runtime_v1.yaml"
PAPER_PLANE_STORE_RELATIVE = "local/factory_v1/paper_plane_state.sqlite"
GOLDEN_SPEC_RELATIVE = (
    "configs/experiment_specs/quote_native_admissible_friction_audition_offline_v1.yaml"
)


class ApplicationError(ValueError):
    """Raised when a bounded owner command cannot execute fail-closed."""

    def __init__(self, code: str) -> None:
        self.code = str(code)
        super().__init__(code)


def _load_yaml(root: Path, relative: str) -> dict[str, Any]:
    loaded = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ApplicationError("REGISTRY_INVALID")
    return loaded


def kernel_config(root: Path) -> dict[str, Any]:
    return _load_yaml(root, KERNEL_CONFIG_RELATIVE)


def commissioning_spec_relative(root: Path) -> str:
    confirmatory_path = root / CONFIRMATORY_CONFIG_RELATIVE
    if confirmatory_path.is_file():
        loaded = _load_yaml(root, CONFIRMATORY_CONFIG_RELATIVE)
        return str(loaded["experiment_spec_relative"])
    retention_path = root / RETENTION_CONFIG_RELATIVE
    if retention_path.is_file():
        loaded = _load_yaml(root, RETENTION_CONFIG_RELATIVE)
        return str(loaded["experiment_spec_relative"])
    t0_path = root / T0_FRICTION_SCREEN_CONFIG_RELATIVE
    if t0_path.is_file():
        loaded = _load_yaml(root, T0_FRICTION_SCREEN_CONFIG_RELATIVE)
        return str(loaded["experiment_spec_relative"])
    veto_path = root / FRICTION_VETO_CONFIG_RELATIVE
    if veto_path.is_file():
        loaded = _load_yaml(root, FRICTION_VETO_CONFIG_RELATIVE)
        return str(loaded["experiment_spec_relative"])
    path = root / COMMISSIONING_CONFIG_RELATIVE
    if not path.is_file():
        return GOLDEN_SPEC_RELATIVE
    loaded = _load_yaml(root, COMMISSIONING_CONFIG_RELATIVE)
    return str(loaded["experiment_spec_relative"])


def ops_store_path(root: Path) -> Path:
    relative = str(kernel_config(root)["operational_store"]["relative_path"])
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ApplicationError("OPS_STORE_PATH_UNSAFE")
    return (root / relative).resolve()


def paper_plane_store_path(root: Path) -> Path:
    relative = PAPER_PLANE_STORE_RELATIVE
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ApplicationError("PAPER_PLANE_STORE_PATH_UNSAFE")
    return (root / relative).resolve()


class FactoryApplication:
    def __init__(
        self,
        *,
        root: Path,
        store: OperationalStore | None = None,
        paper_plane_store: PaperPlaneStore | None = None,
        spec_relative: str | None = None,
        authority_phrase: str | None = None,
        research_data_root: Path | None = None,
    ) -> None:
        self.root = root
        self._operational_store = store
        self._operational_readonly = None
        self._paper_plane_store = paper_plane_store
        self._paper_plane_readonly = None
        self._paper_plane_source_status = "NOT_PRESENT"
        self._runner: ExperimentRunner | None = None
        self._research_data_root = research_data_root
        self._research_reader = None
        self._research_discovery = None
        self.spec_relative = spec_relative or commissioning_spec_relative(root)
        self.authority_phrase = authority_phrase

    def existing_operational_store(self) -> OperationalStore | None:
        if self._operational_store is not None:
            return self._operational_store
        if self._operational_readonly is not None:
            return self._operational_readonly
        path = ops_store_path(self.root)
        if not path.is_file():
            return None
        try:
            self._operational_readonly = OperationalStore(path, readonly=True)
        except (OperationalStoreError, sqlite3.Error, OSError):
            return None
        return self._operational_readonly

    @property
    def store(self) -> OperationalStore:
        if self._operational_store is not None and not getattr(
            self._operational_store, "readonly", False
        ):
            return self._operational_store
        path = ops_store_path(self.root)
        self._operational_store = OperationalStore(path)
        return self._operational_store

    @property
    def runner(self) -> ExperimentRunner:
        if self._runner is None:
            self._runner = ExperimentRunner(root=self.root, store=self.store)
        return self._runner

    def existing_paper_plane(self) -> PaperPlaneStore | None:
        if self._paper_plane_store is not None:
            self._paper_plane_source_status = "PRESENT"
            return self._paper_plane_store
        if self._paper_plane_readonly is not None:
            self._paper_plane_source_status = "PRESENT"
            return self._paper_plane_readonly
        path = paper_plane_store_path(self.root)
        if not path.is_file():
            self._paper_plane_source_status = "NOT_PRESENT"
            return None
        try:
            self._paper_plane_readonly = PaperPlaneStore(path, readonly=True)
        except (PaperPlaneError, sqlite3.Error, OSError):
            self._paper_plane_source_status = "UNAVAILABLE"
            return None
        self._paper_plane_source_status = "PRESENT"
        return self._paper_plane_readonly

    def paper_plane(self) -> PaperPlaneStore:
        if self._paper_plane_store is not None and not getattr(
            self._paper_plane_store, "readonly", False
        ):
            return self._paper_plane_store
        path = paper_plane_store_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._paper_plane_store = PaperPlaneStore(path)
        self._paper_plane_source_status = "PRESENT"
        return self._paper_plane_store

    def _missing_runtime_error(self) -> ApplicationError:
        if self._paper_plane_source_status == "UNAVAILABLE":
            return ApplicationError("RUNTIME_SOURCE_UNAVAILABLE")
        return ApplicationError("SOURCE_NOT_PRESENT")

    def operations_projection(self) -> dict[str, Any]:
        store = self.existing_paper_plane()
        if store is None:
            raise self._missing_runtime_error()
        return build_operations_projection(store)

    def economics_projection(self) -> dict[str, Any]:
        store = self.existing_paper_plane()
        if store is None:
            raise self._missing_runtime_error()
        return build_economics_projection(store)

    def trading_operations_projection(
        self, *, last_command: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        store = self.existing_paper_plane()
        return compose_trading_operations(
            self.root,
            store,
            last_command=last_command,
            source_status=self._paper_plane_source_status,
        )

    def research_discovery(self) -> Any:
        if self._research_discovery is None:
            from solana_alpha_lab.factory.data_root import resolve_existing_data_root

            self._research_discovery = resolve_existing_data_root(
                self.root, explicit_data_root=self._research_data_root
            )
        return self._research_discovery

    def existing_research_store(self) -> Any:
        if self._research_reader is not None:
            return self._research_reader
        discovery = self.research_discovery()
        if discovery.status != "PRESENT" or discovery.root is None:
            return None
        from solana_alpha_lab.factory.research_store import (
            ExistingResearchStoreReader,
            ResearchStoreError,
        )

        try:
            self._research_reader = ExistingResearchStoreReader(discovery.root)
        except ResearchStoreError:
            return None
        return self._research_reader

    def research_projection_discovery(self) -> tuple[str | None, str | None]:
        discovery = self.research_discovery()
        store = self.existing_research_store()
        if store is not None:
            return None, None
        if discovery.status == "PRESENT":
            return "INVALID", discovery.error or "RESEARCH_STORE_OPEN_FAILED"
        if discovery.status != "PRESENT":
            return discovery.status, discovery.error
        return None, discovery.error

    def lifecycle_projection(self) -> dict[str, Any]:
        from solana_alpha_lab.factory.lifecycle_projection import build_lifecycle_projection

        status, error = self.research_projection_discovery()
        return build_lifecycle_projection(
            self.root,
            paper_plane_store=self._paper_plane_store,
            research_store=self.existing_research_store(),
            research_discovery_status=status,
            research_discovery_error=error,
        )

    def research_overview(self, **filters: Any) -> dict[str, Any]:
        from solana_alpha_lab.factory.research_workbench import build_research_overview

        status, error = self.research_projection_discovery()
        return build_research_overview(
            self.root,
            paper_plane_store=self._paper_plane_store,
            research_store=self.existing_research_store(),
            research_discovery_status=status,
            research_discovery_error=error,
            **filters,
        )

    def research_write_capability(self) -> dict[str, str | None]:
        discovery = self.research_discovery()
        if discovery.status != "PRESENT" or discovery.root is None:
            return {
                "read": "AVAILABLE",
                "write": "UNAVAILABLE",
                "reason": discovery.error or discovery.status,
            }
        if self.existing_research_store() is None:
            return {
                "read": "AVAILABLE",
                "write": "UNAVAILABLE",
                "reason": "RESEARCH_STORE_OPEN_FAILED",
            }
        return {"read": "AVAILABLE", "write": "AVAILABLE", "reason": None}

    def research_detail(self, locator: Any) -> dict[str, Any]:
        from solana_alpha_lab.factory.research_workbench import build_research_detail

        status, error = self.research_projection_discovery()
        return build_research_detail(
            self.root,
            locator,
            paper_plane_store=self._paper_plane_store,
            research_store=self.existing_research_store(),
            research_discovery_status=status,
            research_discovery_error=error,
            write_capability=self.research_write_capability(),
        )

    def _producer_git_sha(self) -> str:
        import subprocess

        try:
            sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=self.root,
                text=True,
                timeout=5,
            ).strip()
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise ApplicationError("PRODUCER_GIT_SHA_UNAVAILABLE") from exc
        if len(sha) != 40:
            raise ApplicationError("PRODUCER_GIT_SHA_UNAVAILABLE")
        return sha

    def _committed_decision_event(self, event_id: str) -> Any | None:
        from solana_alpha_lab.factory.research_store import (
            ExistingResearchStoreReader,
            ResearchStoreError,
        )

        discovery = self.research_discovery()
        if discovery.root is None:
            return None
        try:
            for record in ExistingResearchStoreReader(discovery.root).iter_committed_records():
                if record.record_id == event_id:
                    return record
        except ResearchStoreError:
            return None
        return None

    def _decision_matches(
        self,
        record: Any,
        *,
        kind: str,
        snapshot: str,
        locator: Any,
    ) -> bool:
        try:
            committed = json.loads(record.payload_json)
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
        return (
            isinstance(committed, dict)
            and committed.get("decision_kind") == kind
            and committed.get("evidence_snapshot_sha256") == snapshot
            and committed.get("target_entity_id") == locator.entity_id
        )

    def record_research_decision(self, command: Mapping[str, Any]) -> dict[str, Any]:
        from datetime import UTC, datetime

        from solana_alpha_lab.factory.experiment_evidence import (
            OWNER_DECISION_KINDS,
            decision_payload,
            logical_decision_ids,
        )
        from solana_alpha_lab.factory.promotion_handoff import (
            PromotionHandoffError,
            freeze_promotion_handoff_manifest,
        )
        from solana_alpha_lab.factory.research_store import (
            ExistingResearchStoreReader,
            ResearchEvent,
            ResearchStore,
            ResearchStoreError,
        )
        from solana_alpha_lab.factory.research_workbench import (
            ResearchWorkbenchError,
            parse_locator,
        )

        try:
            locator = parse_locator(
                command.get("entity_id"),
                command.get("truth_plane"),
                command.get("native_kind"),
            )
        except ResearchWorkbenchError as exc:
            raise ApplicationError(str(exc)) from exc
        if locator is None or locator.native_kind != "EXPERIMENT_SPEC":
            raise ApplicationError("LOCATOR_REJECTED")
        capability = self.research_write_capability()
        if capability.get("write") != "AVAILABLE":
            raise ApplicationError("WRITE_UNAVAILABLE")
        kind = str(command.get("decision_kind") or "")
        if kind not in OWNER_DECISION_KINDS:
            raise ApplicationError("DECISION_KIND_REJECTED")
        expected = str(command.get("expected_evidence_snapshot_sha256") or "")
        reread = self.research_detail(locator)
        reread_dossier = reread.get("dossier") if isinstance(reread.get("dossier"), dict) else {}
        live_snapshot = str(reread_dossier.get("evidence_snapshot_sha256") or "")
        if not expected or expected != live_snapshot:
            txn_id, event_id = logical_decision_ids(
                locator=locator,
                decision_kind=kind,
                snapshot_sha256=expected,
            )
            existing = self._committed_decision_event(event_id)
            if existing is not None and self._decision_matches(
                existing, kind=kind, snapshot=expected, locator=locator
            ):
                self._research_reader = None
                refreshed = self.research_detail(locator)
                refreshed["decision_result"] = {
                    "status": "DECISION_RECORDED",
                    "disposition": "REPLAY_IDENTICAL",
                    "decision_event_id": event_id,
                    "transaction_id": txn_id,
                    "creates_strategy_version": False,
                }
                return refreshed
            raise ApplicationError("STALE_EVIDENCE_SNAPSHOT")
        if kind == "PROMOTE":
            guard = reread_dossier.get("science_guard") if isinstance(
                reread_dossier.get("science_guard"), dict
            ) else {}
            if not guard.get("allowed"):
                raise ApplicationError("PROMOTE_BLOCKED")
            confirm = str(command.get("promote_scientific_only") or "")
            if confirm != "1":
                raise ApplicationError("PROMOTE_BOUNDARY_CONFIRMATION_REQUIRED")
        txn_id, event_id = logical_decision_ids(
            locator=locator,
            decision_kind=kind,
            snapshot_sha256=expected,
        )
        manifest = None
        now = datetime.now(UTC).replace(microsecond=0)
        stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        if kind == "PROMOTE":
            try:
                manifest = freeze_promotion_handoff_manifest(
                    reread_dossier,
                    root=self.root,
                    decision_event_id=event_id,
                    decision_effective_at=stamp,
                )
            except PromotionHandoffError as exc:
                raise ApplicationError(str(exc) or "EXPERIMENT_SPEC_BINDING_GAP") from exc
        try:
            payload = decision_payload(
                locator=locator,
                decision_kind=kind,
                snapshot_sha256=expected,
                hypothesis_version_id=(reread_dossier.get("tested") or {}).get(
                    "hypothesis_version_id"
                ),
                rationale=command.get("rationale"),
                next_condition=command.get("next_condition"),
                decision_event_id=event_id,
                promotion_handoff_manifest=manifest,
            )
        except ResearchWorkbenchError as exc:
            raise ApplicationError(str(exc)) from exc
        payload_json = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        event = ResearchEvent(
            record_id=event_id,
            record_kind="DECISION_EVENT",
            entity_id=event_id,
            hypothesis_version_id=payload.get("hypothesis_version_id"),
            run_id=None,
            transaction_id=txn_id,
            effective_at=now,
            first_reliable_available_at=now,
            supersedes_record_id=None,
            payload_json=payload_json,
            payload_sha256=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
            schema_version="1.0",
            producer_capability_id="FACTORY-APPLICATION-RESEARCH-DECISION-V1",
            producer_git_sha=self._producer_git_sha(),
            created_at=now,
        )
        discovery = self.research_discovery()
        if discovery.root is None:
            raise ApplicationError("WRITE_UNAVAILABLE")
        try:
            writer = ResearchStore(discovery.root, create_if_missing=False)
            receipt = writer.append([event], transaction_id=txn_id)
        except ResearchStoreError as exc:
            code = getattr(exc, "code", None) or str(exc)
            if code == "WRITER_BUSY":
                raise ApplicationError("WRITER_BUSY") from exc
            raise ApplicationError(code) from exc
        found = None
        try:
            for record in ExistingResearchStoreReader(discovery.root).iter_committed_records():
                if record.record_id == event_id:
                    found = record
                    break
        except ResearchStoreError as exc:
            raise ApplicationError("DECISION_WRITE_UNVERIFIED") from exc
        if found is None:
            raise ApplicationError("DECISION_WRITE_UNVERIFIED")
        try:
            committed = json.loads(found.payload_json)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ApplicationError("DECISION_WRITE_UNVERIFIED") from exc
        if (
            not isinstance(committed, dict)
            or committed.get("decision_kind") != kind
            or committed.get("evidence_snapshot_sha256") != expected
            or committed.get("target_entity_id") != locator.entity_id
        ):
            raise ApplicationError("DECISION_WRITE_UNVERIFIED")
        self._research_reader = None
        refreshed = self.research_detail(locator)
        refreshed["decision_result"] = {
            "status": "DECISION_RECORDED",
            "disposition": str(receipt.disposition),
            "decision_event_id": event_id,
            "transaction_id": txn_id,
            "creates_strategy_version": False,
        }
        return refreshed

    def apply_paper_operator_command(self, command: dict[str, Any]) -> dict[str, Any]:
        if self._paper_plane_store is not None and not getattr(
            self._paper_plane_store, "readonly", False
        ):
            store = self._paper_plane_store
        else:
            path = paper_plane_store_path(self.root)
            if not path.is_file():
                raise ApplicationError("SOURCE_NOT_PRESENT")
            try:
                store = PaperPlaneStore(path)
            except (PaperPlaneError, sqlite3.Error, OSError) as exc:
                raise ApplicationError("RUNTIME_SOURCE_UNAVAILABLE") from exc
        try:
            return apply_operator_command(store, command)
        except PaperPlaneError as exc:
            raise ApplicationError(str(exc)) from exc
        except KeyError as exc:
            raise ApplicationError("COMMAND_FIELD_REQUIRED") from exc

    def recent_execution_changes(
        self, store: PaperPlaneStore, *, limit: int = 12
    ) -> list[dict[str, Any]]:
        events = store.execution_events()
        return list(reversed(events[-limit:]))

    def read_model(
        self, *, surface: str | None = None, last_command: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        hypotheses = _load_yaml(self.root, HYPOTHESES_RELATIVE)
        ops_store = self.existing_operational_store()
        model = project_read_model(
            root=self.root,
            store=ops_store,
            spec_relative=self.spec_relative,
            hypothesis_registry=hypotheses,
        )
        if (self.root / RUNTIME_CONFIG_RELATIVE).is_file() and ops_store is not None:
            from solana_alpha_lab.factory.runtime import project_runtime_health

            model["runtime"] = project_runtime_health(
                root=self.root,
                store=ops_store,
                process_alive=True,
            )
        spec = load_experiment_spec(self.root, self.spec_relative)
        gaps = pinned_produced_gaps(spec, self.root)
        acceptance_item = requirement_map(spec).get("ACCEPTANCE")
        acceptance = None
        if acceptance_item is not None and "ACCEPTANCE" not in gaps and not any(
            item.startswith("ACCEPTANCE:") for item in gaps
        ):
            acceptance_path = self.root / str(acceptance_item["path"])
            expected = str(acceptance_item.get("sha256") or "")
            if acceptance_path.is_file():
                payload = acceptance_path.read_bytes()
                if not expected or hashlib.sha256(payload).hexdigest() == expected:
                    loaded = json.loads(payload.decode("utf-8"))
                    acceptance = loaded if isinstance(loaded, dict) else None
        cockpit = project_cockpit(
            model,
            acceptance=acceptance,
            runtime=model.get("runtime") if isinstance(model.get("runtime"), dict) else None,
            pinned_produced_gaps=gaps,
        )
        paper_store = self.existing_paper_plane()
        trading = compose_trading_operations(
            self.root,
            paper_store,
            last_command=last_command,
            source_status=self._paper_plane_source_status,
        )
        model["trading_operations"] = trading
        operator_attention = []
        for item in trading.get("attention") or []:
            if not isinstance(item, dict):
                continue
            operator_attention.append(
                {
                    "id": str(item.get("code") or "OPERATOR"),
                    "WHY_NOW": item.get("WHY_NOW"),
                    "IMPACT": item.get("IMPACT"),
                    "EVIDENCE": item.get("EVIDENCE"),
                    "NEXT_SAFE_ACTION": item.get("NEXT_SAFE_ACTION"),
                }
            )
        if surface == "OPERATIONS":
            cockpit["attention"] = list(cockpit.get("attention") or []) + operator_attention
        if paper_store is not None:
            operations = trading.get("operations") or build_operations_projection(paper_store)
            model["operations"] = operations
            model["economics"] = trading.get("economics") or build_economics_projection(
                paper_store, operations=operations
            )
            model["recent_changes"] = trading.get("recent_changes") or []
            cockpit["terminal"] = "OWNER_OPERATIONS_COCKPIT_PASS"
        else:
            status = str(trading.get("source_status") or self._paper_plane_source_status)
            model["operations"] = {
                "source_status": status,
                "bots": None,
                "attention": trading.get("attention") or [],
            }
            model["economics"] = {
                "source_status": status,
                "reconciled_net_pnl_usd": None,
                "reconciled_net_pnl_status": status,
                "pnl_known_count": None,
                "pnl_unknown_count": None,
                "known_open_exposure_usd": None,
                "known_open_exposure_status": status,
                "non_claims": [
                    "NO_REALIZED_LIVE_PNL",
                    "NO_OWNER_FCF",
                    "NO_LIVE_CAPITAL",
                    "NO_NETRETURN_CLAIM",
                ],
            }
            model["recent_changes"] = []
        model["cockpit"] = cockpit
        model["git_archaeology_required"] = bool(cockpit["git_archaeology_required"])
        return model

    def freeze_hypothesis(self) -> dict[str, Any]:
        spec = load_experiment_spec(self.root, self.spec_relative)
        cycle_id = str(spec["parameters"]["research_cycle_id"])
        hypothesis_id = str(spec["hypothesis_version"])
        cycles = _load_yaml(self.root, RESEARCH_CYCLES_RELATIVE)
        hypotheses = _load_yaml(self.root, HYPOTHESES_RELATIVE)
        if not any(record.get("record_id") == cycle_id for record in cycles.get("records") or []):
            raise ApplicationError("RESEARCH_CYCLE_MISSING")
        found = None
        for record in hypotheses.get("records") or []:
            if record.get("record_id") == hypothesis_id:
                found = record
                break
        if found is None:
            raise ApplicationError("HYPOTHESIS_MISSING")
        self.store.record_command(
            job_id=f"JOB-{spec['experiment_id']}",
            kind="FREEZE",
            payload={"hypothesis_id": hypothesis_id, "status": found.get("status")},
        )
        return self.read_model()

    def start(
        self,
        authority_phrase: str | None = None,
        capture_hooks: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        phrase = self.authority_phrase if authority_phrase is None else authority_phrase
        try:
            self.runner.start(
                self.spec_relative,
                authority_phrase=phrase,
                capture_hooks=capture_hooks,
            )
        except ExperimentRunnerError as exc:
            raise ApplicationError(str(exc)) from exc
        return self.read_model()

    def stop(self) -> dict[str, Any]:
        spec = load_experiment_spec(self.root, self.spec_relative)
        try:
            self.runner.stop(str(spec["experiment_id"]))
        except ExperimentRunnerError as exc:
            raise ApplicationError(str(exc)) from exc
        return self.read_model()

    def park(self) -> dict[str, Any]:
        spec = load_experiment_spec(self.root, self.spec_relative)
        try:
            self.runner.park(str(spec["experiment_id"]))
        except ExperimentRunnerError as exc:
            raise ApplicationError(str(exc)) from exc
        return self.read_model()

    def record_decision(self, note: str) -> dict[str, Any]:
        model = self.read_model()
        if model["status"] != "COMPLETE":
            raise ApplicationError("DECISION_NOT_AVAILABLE")
        self.store.acknowledge(note)
        self.store.record_command(
            job_id=f"JOB-{load_experiment_spec(self.root, self.spec_relative)['experiment_id']}",
            kind="RECORD_DECISION",
            payload={"note": note, "terminal": model["terminal_result"]},
        )
        return self.read_model()
