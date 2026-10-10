"""Compact retained runs; archives are read without extracting paths or symlinks."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import tarfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tests.fixtures.big_agentic_audit_v1.oracles import grade


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def collect(root, output, *, refresh_baseline=False):
    if (root / '.baa-evidence-owner').read_text() != 'BAA-2026-10-10-V1':
        raise ValueError('EVIDENCE_NOT_CAMPAIGN_OWNED')
    if (output / 'run-ledger.json').exists() and not refresh_baseline:
        raise ValueError('OUTPUT_ALREADY_EXISTS_USE_NEW_REPLAY_OUTPUT')
    output.mkdir(parents=True, exist_ok=True)
    runs, tests, proofs, retention = [], [], [], []
    for receipt in sorted(root.glob('baa-*-containment.json')):
        name = receipt.name.removesuffix('-containment.json')
        retained = root / (name + '-retained')
        archive = retained / 'evidence.tar.gz'
        blobs = {}
        if archive.exists():
            retention.append({'ref': f'{name}-retained/evidence.tar.gz',
                              'bytes': archive.stat().st_size, 'sha256': sha(archive)})
            with tarfile.open(archive) as bundle:
                for member in bundle.getmembers():
                    if member.isfile() and member.name.endswith(('-summary.json', '-trace.jsonl')):
                        if member.size > 64 * 1024 * 1024:
                            raise ValueError('EVIDENCE_MEMBER_SIZE_BOUND')
                        blobs[member.name] = bundle.extractfile(member).read()
        else:
            for directory in (retained, root / name.removeprefix('baa-')):
                if directory.exists():
                    for path in directory.glob('**/*'):
                        if path.is_file() and path.name.endswith(('-summary.json', '-trace.jsonl')):
                            blobs[path.relative_to(directory).as_posix()] = path.read_bytes()
        terminal_path = root / (name + '-terminal.json')
        terminal = json.loads(terminal_path.read_text()) if terminal_path.exists() else None
        summaries = [json.loads(b) for p, b in blobs.items() if p.endswith('-summary.json')]
        traces = [[json.loads(line) for line in b.splitlines() if line] for p, b in blobs.items() if p.endswith('-trace.jsonl')]
        trace = traces[0] if traces else []
        # Only unittest phases have observer traces; bespoke probes carry their
        # own schedules and independent inventories in summary proofs.
        trace_valid = grade(visited=True, expected=0, state=0, readout=0, trace=trace)['trace_complete'] if trace else None
        row = {'attempt': name, 'containment': json.loads(receipt.read_text()),
               'terminal': terminal, 'summary_present': bool(summaries),
               'trace_complete': trace_valid, 'trace_header': trace[0] if trace else None,
               'status': 'COMPLETE' if terminal and not terminal['running'] and summaries else 'INCOMPLETE',
               'summary_bindings': [{'ref': p, 'sha256': hashlib.sha256(b).hexdigest()}
                                    for p, b in blobs.items() if p.endswith('-summary.json')]}
        for summary in summaries:
            for item in summary.get('rows', []):
                tests.append({'attempt': name, 'test_id': item['test_id'], 'status': item['status'],
                              'valid_for_coverage': row['status'] == 'COMPLETE' and trace_valid is True,
                              'wall_seconds': item.get('wall_seconds'),
                              'independent_readback': item.get('independent_readback'),
                              'error_class': 'HARNESS_GIT_SOURCE_OWNERSHIP' if item['status'] == 'ERROR' and 'git' in str(item.get('detail')) else None,
                              'detail_sha256': hashlib.sha256(str(item.get('detail')).encode()).hexdigest()})
            for item in summary.get('proofs', []):
                # Keep actual reduced evidence, suppress bulk file inventories.
                proofs.append({'attempt': name, **{k: v for k, v in item.items()
                    if k not in ('before_inventory', 'after_inventory', 'records')}})
            if summary.get('schema') == 'baa.producer-consumer-bridge.v1':
                proofs.append({'attempt': name, 'id': 'F08-PRODUCER-DOSSIER-LINK', **summary})
        if not summaries:
            for item in trace:
                if item.get('kind') == 'TERMINAL':
                    tests.append({'attempt': name, 'test_id': item['test_id'], 'status': item['status'],
                        'wall_seconds': item.get('wall_seconds'),
                        'independent_readback': item.get('independent_readback'),
                        'origin': 'TRACE_BEFORE_INTERRUPTION', 'valid_for_coverage': False})
        runs.append(row)
    payload = {'schema': 'baa.run-ledger.v1', 'runs': runs, 'test_attempts': tests,
               'probes': proofs, 'retention': retention,
               'test_attempt_counts': dict(Counter(r['status'] for r in tests)),
               'unique_test_ids': len({r['test_id'] for r in tests}),
               'retained_archives_bytes': sum(r['bytes'] for r in retention)}
    (output / 'run-ledger.json').write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({k: payload[k] for k in ('test_attempt_counts', 'unique_test_ids', 'retained_archives_bytes')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence-root', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--refresh-baseline', action='store_true',
                        help='Explicit builder refresh; replay must use a new output root')
    args = parser.parse_args()
    collect(args.evidence_root, args.output_root, refresh_baseline=args.refresh_baseline)
