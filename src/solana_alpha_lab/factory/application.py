"""Command gateway over existing contracts. The UI must not write registries directly."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from solana_alpha_lab.factory.cockpit import pinned_produced_gaps, project_cockpit
from solana_alpha_lab.factory.experiment_spec import load_experiment_spec, requirement_map
from solana_alpha_lab.factory.operational_store import OperationalStore
from solana_alpha_lab.factory.read_model import project_read_model
from solana_alpha_lab.factory.runner import ExperimentRunner, ExperimentRunnerError

HYPOTHESES_RELATIVE = "registries/hypotheses.yaml"
RESEARCH_CYCLES_RELATIVE = "registries/research_cycles.yaml"
KERNEL_CONFIG_RELATIVE = "configs/factory_v1_product_kernel_v1.yaml"
COMMISSIONING_CONFIG_RELATIVE = "configs/factory_v1_commissioning_v1.yaml"
RUNTIME_CONFIG_RELATIVE = "configs/factory_v1_production_lite_runtime_v1.yaml"
GOLDEN_SPEC_RELATIVE = (
    "configs/experiment_specs/quote_native_admissible_friction_audition_offline_v1.yaml"
)


class ApplicationError(ValueError):
    """Raised when a bounded owner command cannot execute fail-closed."""


def _load_yaml(root: Path, relative: str) -> dict[str, Any]:
    loaded = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ApplicationError("REGISTRY_INVALID")
    return loaded


def kernel_config(root: Path) -> dict[str, Any]:
    return _load_yaml(root, KERNEL_CONFIG_RELATIVE)


def commissioning_spec_relative(root: Path) -> str:
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


class FactoryApplication:
    def __init__(
        self,
        *,
        root: Path,
        store: OperationalStore | None = None,
        spec_relative: str | None = None,
        authority_phrase: str | None = None,
    ) -> None:
        self.root = root
        self.store = store or OperationalStore(ops_store_path(root))
        self.runner = ExperimentRunner(root=root, store=self.store)
        self.spec_relative = spec_relative or commissioning_spec_relative(root)
        self.authority_phrase = authority_phrase

    def read_model(self) -> dict[str, Any]:
        hypotheses = _load_yaml(self.root, HYPOTHESES_RELATIVE)
        model = project_read_model(
            root=self.root,
            store=self.store,
            spec_relative=self.spec_relative,
            hypothesis_registry=hypotheses,
        )
        if (self.root / RUNTIME_CONFIG_RELATIVE).is_file():
            from solana_alpha_lab.factory.runtime import project_runtime_health

            model["runtime"] = project_runtime_health(
                root=self.root,
                store=self.store,
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
