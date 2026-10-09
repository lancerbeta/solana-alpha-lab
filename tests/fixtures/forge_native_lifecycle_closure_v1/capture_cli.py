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
result = subprocess.run(argv, cwd=a.eval, env=environment, capture_output=True, timeout=240)
a.out.mkdir(parents=True, exist_ok=True)
(a.out / (a.name + '.stdout.json')).write_bytes(result.stdout)
(a.out / (a.name + '.stderr.txt')).write_bytes(result.stderr)
neutral = [str(x).replace(str(a.eval), '<EVAL>').replace(str(a.data), '<DATA>').replace(str(a.out), '<OUT>') for x in argv]
trace = {'name': a.name, 'argv': neutral, 'exit_code': result.returncode, 'stdout_sha256': hashlib.sha256(result.stdout).hexdigest(), 'stderr_sha256': hashlib.sha256(result.stderr).hexdigest()}
with (a.out / 'cli-actions.jsonl').open('a', encoding='utf-8') as stream:
    stream.write(json.dumps(trace, ensure_ascii=False) + '\n')
sys.stdout.buffer.write(result.stdout)
sys.stderr.buffer.write(result.stderr)
raise SystemExit(result.returncode)
