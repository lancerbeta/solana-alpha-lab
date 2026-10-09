"""Executor-only source equality check, independent Decimal arithmetic."""
import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--root', type=Path, required=True)
p.add_argument('--home', type=Path, required=True)
a = p.parse_args()
root = a.root.resolve()
sys.path[:0] = [str(root), str(root / 'src')]
import pyarrow.parquet as pq
from tests.test_forge_research_flow_reliability_v1 import public_cli
from tests.test_hfic_list_aware_vertical_v1 import mint_of

proofs = []
for variant in ('primary', 'transfer'):
    work = a.home / variant
    description = json.loads((work / 'executor-source.json').read_text(encoding='utf-8'))
    code, binding = public_cli(work / 'plane', 'discovery-binding', '--collection', 'OPPORTUNITY_EPISODES', repo_root=root)
    assert code == 0, binding
    f = binding['cohorts'][0]
    census = pq.read_table(work / 'plane' / f['census_rel']).to_pylist()
    observations = pq.read_table(work / 'plane' / f['observations_rel']).to_pylist()
    assert len(census) == len(description['rows']) == 12
    hscale, pscale = description['holder_scale'], description['price_scale']
    actual = []
    for n, index in enumerate(description['order']):
        label = f'lc{variant[:1]}{n + 1:02d}'
        mint = mint_of(label)
        assert sum(row['mint'] == mint for row in census) == 1
        list_role, start_h, target = description['rows'][index]
        rows = [row for row in observations if row['mint'] == mint]

        def cell(point, field):
            found = [row for row in rows if row['point_id'] == point and row['field_id'] == field]
            assert len(found) == 1, (mint, point, field, len(found))
            row = found[0]
            return None if row['state'] != 'OBSERVED' else Decimal(str(row['typed_value']))

        start = cell('E300', 'FIELD-HOLDER-COUNT-001')
        end = cell('E1800', 'FIELD-HOLDER-COUNT-001')
        price = cell('E1800', 'FIELD-USD-PRICE-001')
        exit_price = cell('E14400', 'FIELD-USD-PRICE-001')
        assert start == (None if start_h is None else Decimal(start_h * hscale)), (mint, start, start_h)
        assert end == Decimal(90 * hscale)
        assert price == Decimal(pscale)
        assert cell('E1800', 'FIELD-LIQUIDITY-USD-001') == Decimal(10000)
        measured = None if exit_price is None else exit_price / price - 1
        if target is None:
            assert measured is None
        else:
            assert measured is not None and abs(measured - Decimal(target)) < Decimal('1e-12'), (mint, measured, target)
        actual.append({'neutral_seat': n + 1, 'start': str(start) if start is not None else None, 'end': str(end), 'proxy': str(measured) if measured is not None else None, 'expected_list_role': list_role})
    proofs.append({'variant': variant, 'status': 'PASS', 'source_rows': actual,
                   'census_sha256': f['census_sha256'], 'observations_sha256': f['observations_sha256'],
                   'metadata_cli_scientific_writes': binding['scientific_writes'], 'new_looks': 0})
output = a.home / 'source-verification.json'
output.write_text(json.dumps(proofs, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': 'PASS', 'variants': len(proofs), 'rows_each': 12, 'new_looks': 0, 'proof': str(output)}))
