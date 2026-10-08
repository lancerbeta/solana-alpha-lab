"""A current-image RSS gate must ignore inherited peaks but retain real peaks."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from solana_alpha_lab.factory.live_cohort_source_bundle import peak_rss_bytes  # noqa: E402

MIB = 1024 * 1024

def hwm_bytes() -> int:
    match = re.search(r'^VmHWM:\s+(\d+)\s+kB$', Path('/proc/self/status').read_text(), re.MULTILINE)
    assert match and int(match[1]) > 0
    return int(match[1]) * 1024

def _child(real_allocation_mib: int) -> None:
    import gc
    import resource
    initial = hwm_bytes()
    held = bytearray(real_allocation_mib * MIB)
    for offset in range(0, len(held), 4096):
        held[offset] = 1
    del held
    gc.collect()
    before = hwm_bytes()
    measured = peak_rss_bytes()
    after = hwm_bytes()
    print(json.dumps({'initial_hwm_bytes': initial, 'oracle_before_bytes': before,
                      'measured_bytes': measured, 'oracle_after_bytes': after,
                      'ru_maxrss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                      'allocation_mib': real_allocation_mib}), flush=True)

class RssKernelBoundaryTests(unittest.TestCase):
    # Linux resource is unavailable on Windows; doubles represent kernel input,
    # not the owner logic. Literal expectations are independent of the parser.
    def _measure(self, proc, platform='linux', resource_peak=238604):
        fake = SimpleNamespace(RUSAGE_SELF=0, getrusage=lambda _: SimpleNamespace(ru_maxrss=resource_peak))
        with patch('sys.platform', platform), patch.dict(sys.modules, {'resource': fake}), \
             patch.object(Path, 'read_text', side_effect=proc if isinstance(proc, BaseException) else None,
                          return_value=proc if isinstance(proc, str) else ''):
            return peak_rss_bytes()

    def test_linux_gate_uses_child_peak_instead_of_inherited_parent_peak(self):
        self.assertEqual(self._measure('VmRSS:\t1234 kB\nVmHWM:\t95388 kB\n'), 97677312)

    def test_linux_true_over_limit_peak_is_retained_after_memory_release(self):
        measured = self._measure('VmHWM:\t614400 kB\nVmRSS:\t10000 kB\n')
        self.assertEqual(measured, 629145600)
        with self.assertRaises(AssertionError):
            self.assertLessEqual(measured, 512*MIB)

    def test_unavailable_or_invalid_linux_hwm_keeps_conservative_resource_peak(self):
        cases = [FileNotFoundError(), PermissionError(), UnicodeError(), '',
                 'VmHWM: 0 kB\n', 'VmHWM: -1 kB\n', 'VmHWM: 1 MB\n',
                 'VmHWM: 1.5 kB\n', 'VmHWM: 123 kB extra\n',
                 'VmHWM: 123 kB\nVmHWM: 456 kB\n']
        for proc in cases:
            with self.subTest(proc=str(proc)):
                self.assertEqual(self._measure(proc), 244330496)

    def test_macos_resource_bytes_remain_bytes(self):
        self.assertEqual(self._measure('VmHWM: 999 kB\n', platform='darwin'), 238604)

    def test_no_valid_linux_metric_cannot_zero_fill_the_gate(self):
        for peak in (0, -1):
            with self.subTest(peak=peak), self.assertRaises(RuntimeError):
                self._measure('', resource_peak=peak)

class RealLinuxRssProcessTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'linux', 'Real Linux /proc and fork/exec evidence required')
    def test_high_parent_peak_cannot_fail_small_child_gate(self):
        held = bytearray(560*MIB)
        for offset in range(0, len(held), 4096):
            held[offset] = 1
        self.assertGreater(hwm_bytes(), 512*MIB)
        body = self._run_child(0)
        del held
        self.assertGreater(body['ru_maxrss_bytes'], 512*MIB)
        self.assertLessEqual(body['oracle_after_bytes'], 512*MIB)
        self.assertLessEqual(body['measured_bytes'], 512*MIB)
        self._assert_oracle(body)

    @unittest.skipUnless(sys.platform == 'linux', 'Real Linux /proc evidence required')
    def test_genuine_child_peak_fails_unchanged_512mib_gate_after_free(self):
        body = self._run_child(600)
        self.assertLessEqual(body['initial_hwm_bytes'], 512*MIB)
        self.assertGreater(body['oracle_before_bytes'], 512*MIB)
        self.assertLessEqual(body['measured_bytes'], 768*MIB)
        with self.assertRaises(AssertionError):
            self.assertLessEqual(body['measured_bytes'], 512*MIB)
        self._assert_oracle(body)

    def _run_child(self, real_mib):
        completed = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--rss-child', str(real_mib)],
                                   cwd=ROOT, capture_output=True, text=True, check=True)
        body = json.loads(completed.stdout)
        print('LINUX_RSS_REGRESSION=' + json.dumps(body, sort_keys=True), flush=True)
        return body

    def _assert_oracle(self, body):
        self.assertGreaterEqual(body['measured_bytes'], body['oracle_before_bytes'])
        self.assertLessEqual(body['measured_bytes'], body['oracle_after_bytes'])

if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--rss-child':
        _child(int(sys.argv[2]))
    else:
        unittest.main()
