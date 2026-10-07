"""Offline exact-base owner replay through the public CLI; no provider access."""
import json
import subprocess
import sys
import tempfile
import types
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from tests.test_opportunity_episodes_harness_v1 import EpisodeScenario, cli_tick, nominate, synth_mint
from tests.test_opportunity_episodes_producer_v1 import S, obj, steady, search_calls
from solana_alpha_lab.factory import opportunity_episode_tick as owner
from solana_alpha_lab.factory.observation_provider_pacing import AdvancingClock

BASE = "77eb427afbc9bb687c6a1fe3a7f3ca4ad2cf3417"
code = subprocess.check_output(["git", "show", BASE + ":src/solana_alpha_lab/factory/opportunity_episode_tick.py"], cwd=ROOT)
base = types.ModuleType("exact_base_episode_tick")
exec(compile(code, "exact_base_episode_tick.py", "exec"), base.__dict__)
with tempfile.TemporaryDirectory() as tmp, patch.object(owner, "tick_episode_schedule", base.tick_episode_schedule):
    sc = EpisodeScenario(Path(tmp) / "rdp", start=S, stops=S + timedelta(hours=1))
    mint = synth_mint("RedReplay")
    nominate(sc.market, S, {"toporganicscore": [obj(mint)], "toptraded": [], "toptrending": []})
    sc.market.series[mint] = steady(mint)
    sc.tick(S + timedelta(seconds=5))
    episode = sc.admissions()[0]["episode_id"]
    assigned = S + timedelta(minutes=10)
    entry = assigned - timedelta(seconds=1.372118)
    clock = AdvancingClock(entry)
    disk_usage = base.shutil.disk_usage
    def work(path):
        actual = disk_usage(path)
        clock.sleep(1.550943)
        return actual
    with patch.object(base.shutil, "disk_usage", side_effect=work):
        first = cli_tick(sc.data_root, sc.market, entry, pacing_clock=clock)
    state_before = sc.slot_states(episode)["E300"]
    second = sc.tick(assigned + timedelta(seconds=60.389428))
    terminal = sc.slot_states(episode)["E300"]
    assert not search_calls(first) and not search_calls(second)
    assert state_before == ("PENDING", None)
    assert terminal == ("CENSORED", "SLOT_NOT_EXECUTED")
    print(json.dumps({"base": BASE, "entry_offset_seconds": -1.372118,
                      "work_crossing_offset_seconds": 0.178825,
                      "next_pass_offset_seconds": 60.389428,
                      "first_terminal": first["terminal"], "initial_slot": state_before,
                      "final_slot": terminal, "search_requests": 0,
                      "outbox_unpublished": sc.unpublished()}, sort_keys=True))
