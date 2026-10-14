"""Audit-owned IO; no product authority or scientific carriers."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path('/repo')
OUT = Path('/audit')
BASE = 'fbac5449f6dd22a7bc066114109be8bbed830447'
LIMITS = {'main': 6, 'evaluator': 12, 'confirmation': 3}

def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str, allow_nan=False)+'\n')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load(path):
    return json.loads(Path(path).read_text())

def charge(kind, **details):
    """Single campaign orchestrator; charge before calling, never refund failure."""
    path = OUT/'attempts.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    count = sum(r['kind'] == kind for r in rows)
    if kind in LIMITS and count >= LIMITS[kind]:
        raise AssertionError('CAMPAIGN_ENVELOPE_EXCEEDED:'+kind)
    body = {'sequence': len(rows)+1, 'kind': kind, 'pid': os.getpid(), **details}
    with path.open('a') as handle:
        handle.write(json.dumps(body, sort_keys=True)+'\n')
        handle.flush()
        os.fsync(handle.fileno())
    return body
