"""Equal medians with distinct tails through the actual admitted mean metric."""
import json
from pathlib import Path
from statistics import median
import sys
sys.path[:0] = ['/repo', '/repo/src', '/kit']
from safety_preflight import check
from solana_alpha_lab.factory.hfic_grounded_discovery import execute_discovery_from_rows
from tests.test_hfic_temporal_discovery_v1 import _spec, _census, _path, _binding, PRICE


def main():
    assert check()['pass']
    spec = _spec(search_tier='SIMPLE_SCREEN',
        features=[{'name': 'mark', 'op': 'point_value', 'field_id': PRICE, 'point': 'Y3600'}],
        all=[{'feature': 'mark', 'op': 'gte', 'value': 1.0}], cost_profile=None)
    worlds = [[-.9, 0., .1, .9], [-.1, 0., .1, .2]]
    output = []
    for returns in worlds:
        census = [_census(f'BAA-METRIC-{i}') for i in range(4)]
        observations = [row for i, value in enumerate(returns)
            for row in _path(f'BAA-METRIC-{i}', [1., 1., 1., 1.], (1000., 1000.), 1. + value)]
        summary = execute_discovery_from_rows(census, observations, spec, _binding())['summary']
        output.append({'input_returns': returns, 'median': median(returns),
            'expected_mean': sum(returns) / 4, 'actual_mean': summary['mean_target'],
            'population_n': summary['population_n'], 'observed_n': summary['observed_target_n']})
    ok = output[0]['median'] == output[1]['median'] and output[0]['actual_mean'] != output[1]['actual_mean']
    ok = ok and all(abs(row['expected_mean'] - row['actual_mean']) < 1e-12 and row['observed_n'] == 4 for row in output)
    proof = {'id': 'E06-SAME-MEDIAN-DIFFERENT-TAILS', 'fidelity': 'CONTRACT_ONLY',
        'status': 'PASS' if ok else 'FAIL', 'worlds': output,
        'scope': 'Actual supported mean-return evaluator on declared row/binding inputs; no independent statistical validity or chronological experiment claim',
        'schedule': ['fixed admitted point query', 'synthetic world A', 'synthetic world B',
                     'paired comparison with independently calculated means and equal medians']}
    (Path('/audit') / 'metrics-summary.json').write_text(json.dumps({'proofs': [proof]}, indent=2))
    print(json.dumps(proof))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
