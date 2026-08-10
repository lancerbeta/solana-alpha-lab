from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solana_alpha_lab.task30_route_availability_probe import evaluate_probe


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"YAML object required: {path.name}")
    return value


def _frozen_group() -> dict[str, Any]:
    registry = _load_yaml(ROOT / "configs" / "task28_rc001_registry_freeze_v1.yaml")
    groups = registry.get("hypothesis_groups")
    if not isinstance(groups, list):
        raise ValueError("frozen registry groups required")
    for group in groups:
        if isinstance(group, dict) and group.get("group_id") == "RC001-H07-H01-LIQUIDITY-RETENTION":
            return group
    raise ValueError("frozen H07/H01 group required")


def readout() -> dict[str, Any]:
    policy = _load_yaml(ROOT / "configs" / "task30_route_availability_probe_v1.yaml")
    fixture = json.loads(
        (ROOT / "tests" / "fixtures" / "task30" / "route_availability_probe_v1.json").read_text(
            encoding="utf-8"
        )
    )
    if not isinstance(fixture, dict) or not isinstance(fixture.get("records"), list):
        raise ValueError("synthetic fixture records required")
    return evaluate_probe(policy, _frozen_group(), fixture["records"])


def markdown(result: dict[str, Any]) -> str:
    delay = result["recommended_fixed_delay_seconds"]
    lines = [
        "# TASK-30 A11A — offline readout доступности маршрута",
        "",
        f"Synthetic result: `{result['decision']}`.",
        "",
        f"Рекомендованная фиксированная задержка публикации: **{delay} секунд**.",
        "Результат получен только на синтетических записях трёх 15-минутных границ.",
        "",
        "Следующая граница — отдельный owner packet на двухслотовый live shakedown.",
        "Если monitoring потерян, процесс не стартовал, receipt не записан или prior manifest не читается,",
        "состояние должно быть `STOP_RUN`; это не market/provider gap.",
        "",
        "Этот offline-пакет не разрешает внешний запрос, credential, raw write, scheduler,",
        "wallet, transaction, cash spend, 24-hour capture или TASK-30 acceptance.",
        "",
        "Не доказано: PIT-admissibility, evidence H07/H01, research trial, execution, settlement и NetReturn.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the offline TASK-30 availability-probe readout.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()
    result = readout()
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(markdown(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
