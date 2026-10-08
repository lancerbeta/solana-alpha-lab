#!/usr/bin/env python3
"""Bounded, offline unchanged-worker Linux RSS diagnostic; not an acceptance CI."""
from __future__ import annotations

import argparse
import hashlib
import json
import resource
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANCHOR = '20294a7677f14e93f8bb5dd6b4d339f2e15302d5'
LEAF = 'tests/test_legacy_fat_open_bounded_artifacts_resume_v1.py'
OWNERS = [LEAF, 'src/solana_alpha_lab/factory/live_cohort_source_bundle.py',
          'src/solana_alpha_lab/factory/observation_panel_publisher.py']
MIB = 1024 * 1024

def metrics() -> dict:
    fields = {}
    for line in Path('/proc/self/status').read_text(encoding='ascii').splitlines():
        if line.startswith(('VmRSS:', 'VmHWM:')):
            key, value, unit = line.split()
            assert unit == 'kB' and int(value) > 0
            fields[key.rstrip(':').lower() + '_bytes'] = int(value) * 1024
    assert len(fields) == 2
    return {**fields, 'ru_maxrss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}

def child(payload: Path, result: Path) -> None:
    entry = metrics()
    module = runpy.run_path(str(ROOT / LEAF), run_name='rss_diagnostic_unchanged_leaf')
    imported = metrics()
    module['_memory_child'](str(payload), str(result))
    body = json.loads(result.read_text(encoding='utf-8'))
    body['rss_diagnostic'] = {'at_entry': entry, 'after_import': imported, 'after_workload': metrics()}
    result.write_text(json.dumps(body), encoding='utf-8')

def run() -> None:
    assert sys.platform == 'linux', 'Linux evidence required'
    parser = argparse.ArgumentParser()
    parser.add_argument('--child', nargs=2, type=Path)
    parser.add_argument('--output', type=Path, default=Path('local/linux-rss-probe.json'))
    args = parser.parse_args()
    if args.child:
        child(*args.child)
        return
    pins = {}
    for relative in OWNERS:
        raw = (ROOT / relative).read_bytes()
        original = subprocess.check_output(['git', 'show', f'{ANCHOR}:{relative}'], cwd=ROOT)
        assert raw == original, f'Workload owner changed: {relative}'
        pins[relative] = hashlib.sha256(raw).hexdigest()
    report = {'kind': 'UNCHANGED_WORKLOAD_DIAGNOSTIC_NOT_ACCEPTANCE',
              'producer_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'anchor': ANCHOR, 'source_pins': pins, 'limits': {'comfortable_bytes': 512*MIB, 'soft_bytes': 768*MIB},
              'historical_ci': 37709815254, 'historical_ci_conclusion': 'FAILURE', 'cases': []}
    for parent_mib in (0, 600):
        held = bytearray(parent_mib * MIB)
        # Touch every page before fork; retain allocation until child completes.
        for index in range(0, len(held), 4096):
            held[index] = 1
        parent = metrics()
        with tempfile.TemporaryDirectory(prefix='linux-rss-probe-') as tmp:
            payload, result = Path(tmp)/'payload.json', Path(tmp)/'result.json'
            payload.write_text(json.dumps({'tmp': tmp, 'schedule_rel': 'tests/fixtures/observation_schedule/x300_y900.yaml'}), encoding='utf-8')
            completed = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--child', str(payload), str(result)],
                                       cwd=ROOT, capture_output=True, text=True)
            assert completed.returncode == 0, completed.stderr
            body = json.loads(result.read_text(encoding='utf-8'))
        del held
        assert body['terminal'] == 'FAT_ARTIFACTS_RESUME_COMPLETED' and body['provider_calls'] == 0
        assert body['source_size'] > 16*MIB
        report['cases'].append({'parent_allocation_mib': parent_mib, 'parent': parent, 'child': body,
                                'original_comfortable_assertion_pass': body['max_rss_bytes'] <= 512*MIB,
                                'child_hwm_comfortable_assertion_pass': body['rss_diagnostic']['after_workload']['vmhwm_bytes'] <= 512*MIB})
    high = report['cases'][1]
    report['hypothesis_confirmed_for_controlled_ci_workload'] = (
        high['child']['max_rss_bytes'] > 512*MIB
        and high['child']['rss_diagnostic']['after_workload']['vmhwm_bytes'] < 512*MIB
        and high['child']['rss_diagnostic']['at_entry']['ru_maxrss_bytes'] >= 600*MIB)
    report['historical_failed_child_hwm'] = 'UNKNOWN_NOT_RECORDED_IN_RUN37709815254'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, sort_keys=True), flush=True)
    assert all(case['child_hwm_comfortable_assertion_pass'] for case in report['cases']), 'REAL_CHILD_RSS_OVER512MIB'
    assert report['hypothesis_confirmed_for_controlled_ci_workload'], 'INHERITED_PEAK_HYPOTHESIS_NOT_CONFIRMED'

if __name__ == '__main__':
    run()
