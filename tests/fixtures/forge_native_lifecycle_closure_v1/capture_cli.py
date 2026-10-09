"""Lossless subprocess capture only; no authored semantic/binding projection."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--eval', type=Path, required=True)
p.add_argument('--data', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--name', required=True)
p.add_argument('command', nargs=argparse.REMAINDER)
a = p.parse_args()
command = a.command[1:] if a.command[:1] == ['--'] else a.command
if re.fullmatch(r'[A-Za-z0-9_-]+', a.name) is None:
    raise SystemExit('CAPTURE_NAME_INVALID')
if (a.out / (a.name + '.stdout.json')).exists():
    raise SystemExit('CAPTURE_EXISTS_USE_NEW_INVOCATION_NAME')
argv = [sys.executable, '-B', str(a.eval / 'scripts/hypothesis_forge.py'), '--root', str(a.eval), '--data-root', str(a.data), *command]
environment = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8', 'SMIAL_DATA_ROOT': str(a.data), 'PYTHONPATH': str(a.eval / 'src')}
a.out.mkdir(parents=True, exist_ok=True)
timed_out = False
try:
    result = subprocess.run(argv, cwd=a.eval, env=environment, capture_output=True, timeout=240)
    stdout, stderr, exit_code = result.stdout, result.stderr, result.returncode
except subprocess.TimeoutExpired as failure:
    # A timed-out response says nothing about whether the logical effect committed.
    # Preserve partial bytes and the invocation name before any saved-state read.
    timed_out = True
    stdout, stderr, exit_code = failure.stdout or b'', failure.stderr or b'', 124
(a.out / (a.name + '.stdout.json')).write_bytes(stdout)
(a.out / (a.name + '.stderr.txt')).write_bytes(stderr)
neutral = [str(x).replace(str(a.eval), '<EVAL>').replace(str(a.data), '<DATA>').replace(str(a.out), '<OUT>') for x in argv]
trace = {'name': a.name, 'argv': neutral, 'exit_code': exit_code, 'stdout_sha256': hashlib.sha256(stdout).hexdigest(), 'stderr_sha256': hashlib.sha256(stderr).hexdigest(), 'timed_out': timed_out, 'side_effect_status': 'UNKNOWN_READ_SAVED_STATE_FIRST' if timed_out else 'READ_ACTUAL_PUBLIC_RESPONSE'}
with (a.out / 'cli-actions.jsonl').open('a', encoding='utf-8') as stream:
    stream.write(json.dumps(trace, ensure_ascii=False) + '\n')
sys.stdout.buffer.write(stdout)
sys.stderr.buffer.write(stderr)
raise SystemExit(exit_code)
