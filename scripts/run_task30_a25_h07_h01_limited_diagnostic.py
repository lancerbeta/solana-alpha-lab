#!/usr/bin/env python3
"""Execute the authorized TASK-30 A25 offline H07/H01 measurability diagnostic."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from solana_alpha_lab.task30_h07_h01_limited_diagnostic import (  # noqa: E402
    ATOM_ID,
    A25Error,
    canonical_json,
    execute_diagnostic,
    format_utc,
    load_policy,
    sha256_bytes,
    write_local_projection,
)
from solana_alpha_lab.task30_raw_to_pit_admissibility import (  # noqa: E402
    load_policy as load_upstream_policy,
)

AUTHORITY_PHRASE = "OK T30-A25 H07_H01_FROZEN_LIMITED_DIAGNOSTIC_AND_MEASURABILITY_VERDICT"
CONFIG_PATH = ROOT / "configs/task30_a25_h07_h01_limited_diagnostic_v1.yaml"
RUNTIME_RECEIPT_PATH = (
    ROOT / "docs/evidence/task30/a25_h07_h01_limited_diagnostic_runtime_receipt_v1.json"
)
ACCEPTANCE_PATH = (
    ROOT / "docs/evidence/task30/a25_h07_h01_limited_diagnostic_acceptance_v1.json"
)
READOUT_PATH = (
    ROOT / "docs/reports/task30/a25_h07_h01_limited_diagnostic_owner_readout_v1.md"
)


def main() -> int:
    policy = load_policy(CONFIG_PATH)
    if policy["external_authority"]["owner_phrase"] != AUTHORITY_PHRASE:
        raise A25Error("OWNER_PHRASE_DRIFT")
    upstream = load_upstream_policy(ROOT / policy["upstream_panel"]["policy_path"])
    bindings = upstream["input_bindings"]
    a22_payload = (ROOT / bindings["a22_raw"]["path"]).read_bytes()
    a23_payload = (ROOT / bindings["a23_terminal_page"]["path"]).read_bytes()
    measured = datetime.now(UTC).replace(microsecond=0)
    result = execute_diagnostic(
        repo_root=ROOT,
        policy=policy,
        a22_payload=a22_payload,
        a23_payload=a23_payload,
        measured_as_of=measured,
    )
    identity_sha = sha256_bytes(
        (
            policy["frozen_definition"]["definition_sha256"]
            + bindings["a22_raw"]["sha256"]
        ).encode()
    )
    run_id = f"{measured.strftime('%Y%m%dT%H%M%SZ')}-{identity_sha[:8]}"
    local_paths = write_local_projection(
        result, ROOT / policy["retention"]["raw_root"] / f"run={run_id}", repo_root=ROOT
    )
    runtime = {
        "schema": "smial.task30.a25-h07-h01-limited-diagnostic.runtime",
        "schema_version": "1.0",
        "atom_id": ATOM_ID,
        "observed_at": format_utc(measured),
        "terminal_decision": result["terminal_decision"],
        "frozen_estimand": result["frozen_estimand"],
        "orientation": result["orientation"],
        "lane_field_supply": result["lane_field_supply"],
        "metric_computability": result["metric_computability"],
        "frozen_parameter_resolution": result["frozen_parameter_resolution"],
        "statistics": result["statistics"],
        "precision_and_power": result["precision_and_power"],
        "required_data_specification": result["required_data_specification"],
        "pit": result["pit"],
        "verdict": result["verdict"],
        "claims": result["claims"],
        "side_effects": result["side_effects"],
        "local_projection": local_paths,
    }
    RUNTIME_RECEIPT_PATH.write_bytes(canonical_json(runtime))
    acceptance = {
        "schema": "smial.task30.a25-h07-h01-limited-diagnostic.acceptance",
        "schema_version": "1.0",
        "receipt_id": "EVIDENCE-T30-A25-H07-H01-MEASURABILITY-001",
        "task_id": "TASK-30",
        "atom_id": ATOM_ID,
        "as_of": "2026-08-15",
        "decision": result["terminal_decision"],
        "task_state": "BLOCKED_DATA",
        "named_consumer": "RC001-H07-H01-LIQUIDITY-RETENTION",
        "runtime_receipt_sha256": sha256_bytes(RUNTIME_RECEIPT_PATH.read_bytes()),
        "frozen_estimand": result["frozen_estimand"],
        "orientation": result["orientation"],
        "metric_computability": result["metric_computability"],
        "frozen_parameter_resolution": result["frozen_parameter_resolution"],
        "statistics": result["statistics"],
        "precision_and_power": result["precision_and_power"],
        "required_data_specification": result["required_data_specification"],
        "pit": result["pit"],
        "limitations": result["verdict"].get("limitations"),
        "project_sources_disposition": {"kind": "NO_CHANGE"},
        "claims": result["claims"],
        "side_effects": result["side_effects"],
        "non_claims": [
            "NO_TASK30_ACCEPTANCE",
            "NO_RC001_PROMOTION",
            "NO_H07_H01_TRIAL",
            "NO_EFFECT_ESTIMATE",
            "NO_ALPHA",
            "NO_FORWARD_FILL",
            "NO_MISSING_TO_ZERO",
        ],
    }
    ACCEPTANCE_PATH.write_bytes(canonical_json(acceptance))
    READOUT_PATH.write_text(_readout(runtime), encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {"terminal_decision": result["terminal_decision"], "run_id": run_id},
            sort_keys=True,
        )
    )
    return 0


def _readout(runtime: dict[str, object]) -> str:
    verdict = dict(runtime["verdict"])  # type: ignore[arg-type]
    statistics = dict(runtime["statistics"])  # type: ignore[arg-type]
    power = dict(runtime["precision_and_power"])  # type: ignore[arg-type]
    specification = dict(runtime["required_data_specification"])  # type: ignore[arg-type]
    metrics = dict(runtime["metric_computability"])  # type: ignore[arg-type]
    parameters = dict(runtime["frozen_parameter_resolution"])  # type: ignore[arg-type]
    lines = [
        "# TASK-30 A25 — измеримость замороженного H07/H01",
        "",
        f"**Терминальное решение:** `{verdict['terminal_decision']}`",
        "",
        "Это диагностика **измеримости**, а не утверждение об эффекте.",
        "Вопрос был один: можно ли честно посчитать замороженный estimand",
        "`RC001-H07-H01-LIQUIDITY-RETENTION` на панели A24.",
        "",
        "## Метрики замороженного estimand",
        "",
    ]
    for metric in sorted(metrics):
        entry = dict(metrics[metric])  # type: ignore[arg-type]
        lines.append(f"- `{metric}`: `{entry['computability']}`")
        missing = entry.get("missing_fields") or []
        if isinstance(missing, list) and missing:
            lines.append(f"  - отсутствуют поля: `{', '.join(str(x) for x in missing)}`")
    lines.extend(
        [
            "",
            "## Что посчитано и на чём",
            "",
            f"- Слотов всего: `{statistics.get('slots_total')}`",
            f"- Потреблено как наблюдения: `{statistics.get('slots_consumed_as_observed')}`",
            f"- Потреблено как типизированные пропуски: `{statistics.get('slots_consumed_as_typed_gap')}`",
            f"- Неизвестное покрытие: `{statistics.get('slots_consumed_as_unknown')}`",
            f"- `MISSINGNESS_RATE` (OHLC): `{statistics.get('ohlc_missingness_rate')}`",
            f"- Свежие наблюдения ликвидности: `{statistics.get('fresh_liquidity_observation_slots')}`",
            f"- Перенесённые (carry-forward) слоты ликвидности: `{statistics.get('carried_forward_liquidity_slots')}`",
            "",
            "Слоты `STATE_PERSISTENCE_PROVEN` **не** считаются наблюдёнными сделками,",
            "а carry-forward резервы **не** считаются свежим наблюдением ликвидности.",
            "",
            "## Точность и мощность",
            "",
            f"- Единица кластера: `{power.get('cluster_unit')}`",
            f"- Независимых кластеров: `{power.get('independent_clusters')}`",
            f"- Степеней свободы между кластерами: `{power.get('between_cluster_degrees_of_freedom')}`",
            f"- Стандартная ошибка: `{power.get('standard_error_status')}`",
            (
                "- Наивная биномиальная SE "
                f"`{power.get('naive_binomial_se_if_slots_were_independent')}` — "
                f"`{power.get('naive_binomial_se_validity')}`"
            ),
            "",
            "Один пул за один день — это **один** кластер, а не 96 независимых",
            "наблюдений. Между кластерами дисперсия не идентифицируется, поэтому",
            "валидной стандартной ошибки и доверительного интервала здесь нет.",
            "",
            "## Какие данные нужны для решающего теста",
            "",
            f"- Единица набора: `{specification.get('cluster_unit')}`",
            (
                "- Минимум кластеров для определённой межкластерной дисперсии: "
                f"`{specification.get('minimum_clusters_for_defined_between_cluster_variance')}`"
            ),
            (
                "- Минимум кластеров для определённого двухгруппового теста: "
                f"`{specification.get('minimum_clusters_for_two_group_cluster_level_test')}`"
            ),
            (
                f"- Слотов на кластер: `{specification.get('slots_per_cluster')}` × "
                f"`{specification.get('slot_interval_seconds')}` с"
            ),
            f"- Покрытие слотов: `{specification.get('slot_coverage_policy')}`",
            (
                "- Оценок маршрута на кластер: "
                f"`{specification.get('route_evaluations_per_cluster_formula')}`"
            ),
            (
                "- Размер набора нотионалов: "
                f"`{specification.get('notional_bucket_count')}` "
                f"(параметр `{specification.get('notional_bucket_parameter')}`)"
            ),
            (
                "- Решающий масштаб выводим из этой панели: "
                f"`{specification.get('decisive_scale_derivable_from_this_panel')}` — "
                f"`{specification.get('decisive_scale_blocker')}`"
            ),
            f"- Цель следующего измерения: `{specification.get('next_measurement_purpose')}`",
            "",
            "### Отсутствующие поля",
            "",
        ]
    )
    absent = specification.get("required_fields_currently_absent") or []
    if isinstance(absent, list):
        lines.extend(f"- `{item}`" for item in absent)
    lines.extend(["", "### Неразрешённые замороженные параметры", ""])
    for name in sorted(parameters):
        entry = dict(parameters[name])  # type: ignore[arg-type]
        if entry.get("resolved") is False:
            lines.append(f"- `{name}`: `{entry.get('unresolved_code')}`")
    lines.extend(["", "## Ограничения", ""])
    limitations = verdict.get("limitations") or []
    if isinstance(limitations, list):
        lines.extend(f"- `{item}`" for item in limitations)
    lines.extend(
        [
            "",
            "## Что дальше",
            "",
            str(verdict.get("next_owner_decision", "")),
            "",
            "`TASK-30` остаётся `BLOCKED_DATA`. RC001 не продвигается.",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
