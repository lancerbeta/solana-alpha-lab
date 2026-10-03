"""Synthetic public execution -> production freeze packets; never reads real RDP.

Run from the repo with PYTHONPATH=src;. and an explicit disposable output dir.
The four fixed packets are written once, before the isolated blind reviewer.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from solana_alpha_lab.factory.hfic_session import freeze_draft
from solana_alpha_lab.factory.hfic_temporal_discovery import temporal_target_label
from solana_alpha_lab.factory.research_store import ResearchStore
from tests.test_hfic_cli import bind_draft, run_cli
from tests.test_hfic_ordinary_operation_acceptance_v1 import _forge, _operation, _publish_focus
from tests.test_hfic_temporal_discovery_v1 import LIQ, PRICE, _binding, _census, _obs, _spec

ROOT = Path(__file__).resolve().parents[3]


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=False)
    operator = (ROOT / "docs/operator/HYPOTHESIS_FORGE_AND_INDEPENDENT_CRITIC_OPERATOR_V1.md").read_text(encoding="utf-8")
    prompt = operator.split("## BEGIN PROMPT B", 1)[1].split("## END PROMPT B", 1)[0]
    (out / "prompt_b.txt").write_text(prompt, encoding="utf-8")
    summaries = {}
    for name in ("K1", "K2", "K3", "K4"):
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            focus = f"FIXED_DOWNSIDE_{name}"
            data_root, receipt = _publish_focus(workspace, focus)
            empty = workspace / "explicit"
            empty.mkdir()
            spec = _spec(tier="SIMPLE_SCREEN", features=[{"name": "mark", "op": "point_value", "field_id": LIQ, "point": "Y3600"}], all=[{"feature": "mark", "op": "gte", "value": 0.5}], cost_profile=None)
            scope = {"population": "BASE_X", "decision_timestamp": "Y3600", "target": temporal_target_label(spec), "estimand": "price_relative_proxy", "explanatory_condition": "mark", "evidence_surface_mode": "ORDINARY_GROUNDED_DISCOVERY_V1", "representation_scope": "TEMPORAL_PRICE_LIQUIDITY"}
            census, rows = [], []
            for i in range(40):
                mint = f"fixture-{i:02}"
                census.append(_census(mint))
                matched = i < (2 if name == "K4" else 10)
                r = -0.5 if name == "K1" and i in (0, 1, 2, 10) else -0.9 if name == "K4" and i == 0 else 0.0
                rows.extend([_obs(mint, "X300", LIQ, 1000), _obs(mint, "X300", PRICE, 1), _obs(mint, "Y3600", LIQ, int(matched)), _obs(mint, "Y3600", PRICE, 1)])
                if name != "K3":
                    rows.append(_obs(mint, "Y7200", PRICE, 1 + r))
            paths = {key: workspace / f"{key}.json" for key in ("spec", "scope", "binding", "op")}
            census_path, obs_path = workspace / "census.parquet", workspace / "observations.parquet"
            pq.write_table(pa.Table.from_pylist(census), census_path)
            pq.write_table(pa.Table.from_pylist(rows), obs_path)
            binding = _binding()
            binding[0].update(census_sha256=hashlib.sha256(census_path.read_bytes()).hexdigest(), observations_sha256=hashlib.sha256(obs_path.read_bytes()).hexdigest(), census_rel=census_path.name, observations_rel=obs_path.name)
            write(paths["spec"], spec)
            write(paths["scope"], scope)
            write(paths["binding"], {"cohorts": binding})
            write(paths["op"], _operation(spec, focus=focus, journal=receipt["search_key_sha256"], market=receipt["market_evidence_epoch_sha256"], text="Describe future downside of an early liquidity-mark group for a possible abstention policy.", cap={"main": 1, "adaptive": 0, "preview": 0}))
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = _forge().cmd_discovery_execute(ROOT, store_root=data_root, census_path=None, observations_path=None, binding_path=paths["binding"], spec_path=paths["spec"], journal_scope=receipt["search_key_sha256"], candidate_scope_path=paths["scope"], cohort_partitions=[(binding[0]["cohort_id"], census_path, obs_path)], explicit_data_root=empty, operation_path=paths["op"])
            evidence = json.loads(stream.getvalue().splitlines()[-1])
            assert code == 0, evidence
            cold = run_cli("preflight", "--discovery-contract", "--owner-focus", focus, "--format", "json", data_root=data_root)
            assert cold.returncode == 0, cold.stderr
            receipt = json.loads(cold.stdout)
            template = json.loads((ROOT / "tests/fixtures/hypothesis_forge/draft_v1_2_valid.json").read_text(encoding="utf-8"))
            card = dict(template["candidates"][0])
            card.update(scope)
            card.update(claim="The early liquidity-mark group may have different subsequent downside relevant to abstention.", mechanism="Early liquidity state may distinguish later adverse price paths.", primary_x_family="FIELD-LIQUIDITY-USD-001 point_value Y3600 mark>=0.5", primary_y="PRICE_RELATIVE_PROXY", horizon_notional="Y3600 to Y7200 PRICE_RELATIVE_PROXY; no executable notional", state_transition="early liquidity mark to later adverse price path", required_feature_ids=[], unresolved_requirements=["DECISION_LIQUIDITY_FEAT_NOT_DECLARED_READOUT_ONLY"], kill_if=["Saved spec/input mismatch"], required_capability_ids=["CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001"], material_difference_from_prior="Existing decision liquidity mark and fixed later price target; no ratio or route-unavailability claim.", negative_control="Same-decision BASE_X baseline may include matched.", decision_unlocked="Whether a separate baseline-policy economic test is justified.", disconfirming_prediction="The same-decision comparison provides no useful downside distinction.", cheapest_falsifier="Read the fixed matched and same-decision baseline downside description before choosing a separate economic test.")
            draft = bind_draft({**template, "owner_focus": focus, "candidates": [card]}, receipt)
            for key in ("runner_up_candidate_ref", "strongest_rejected_alternative"):
                draft.pop(key, None)
            draft["selected_candidate_ref"] = card["label"]
            draft["grounded_evidence"] = evidence
            frozen = freeze_draft(draft, preflight_receipt=receipt, store=ResearchStore(data_root), repo_root=ROOT)
            packet = frozen["critic_input_packet"]
            assert packet["grounded_evidence"]["descriptive_readout"] == evidence["descriptive_readout"]
            write(out / f"{name}.json", packet)
            summaries[name] = {"result": evidence["result"], "owner": evidence["ordinary_operation"], "prompt_a": receipt["forge_context_packet"], "critic_packet_sha256": frozen["critic_input_packet_sha256"]}
    write(out / "transport_summary.json", summaries)
    print(json.dumps({"status": "PASS", "cases": list(summaries)}))


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
