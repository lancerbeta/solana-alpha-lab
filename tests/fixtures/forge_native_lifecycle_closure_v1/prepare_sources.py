"""Executor-only synthetic source preparation; never a native research input."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROWS = [
    ('A', 50, '.20'), ('B', 50, '.10'), ('C', 50, '.30'),
    ('A', 130, '-.20'), ('B', 130, '-.10'), ('C', 130, '-.30'),
    ('A', 90, '0'), ('B', 90, '0'), ('C', None, '.50'),
    ('C', None, '-.50'), ('C', 50, None), ('C', None, '.40'),
]
ORDER_B = [5, 2, 9, 6, 0, 11, 4, 8, 1, 10, 7, 3]


def emit(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def prepare(root, home, variant):
    sys.path[:0] = [str(root), str(root / 'src')]
    from tests import test_hfic_list_aware_vertical_v1 as lav
    from tests.test_opportunity_episodes_harness_v1 import SyntheticMarket, token_object
    from solana_alpha_lab.factory.research_store import ResearchStore, RecordKind
    from solana_alpha_lab.factory.hfic_research_universe_policy import preview_universe_policy, apply_universe_policy
    from solana_alpha_lab.factory.run_passport import canonical_json_bytes, canonical_sha256
    from tests.test_hfic_critic_prior_memory_closure_v1 import _event

    work = home / variant
    if work.exists():
        raise RuntimeError('FRESH_SOURCE_LOCATION_REQUIRED')
    work.mkdir(parents=True)
    order = list(range(12)) if variant == 'primary' else ORDER_B
    hscale, pscale = (1, 1) if variant == 'primary' else (2, 10)
    table, cells = {}, {}
    for n, index in enumerate(order):
        lists, start, target = ROWS[index]
        label = f'lc{variant[:1]}{n + 1:02d}'
        table[label] = (lists, False, None if target is None else float(Decimal(target)))
        cells[lav.mint_of(label)] = (start, target)

    def build_market():
        market = SyntheticMarket()
        for _, label, start_time, (lists, _, _) in lav.rounds():
            mint = lav.mint_of(label)
            start_h, target = cells.get(mint, (90, '0'))
            body = {lav.CATEGORY[x]: [] for x in 'ABC'}
            for letter in lists:
                body[lav.CATEGORY[letter]].append(token_object(mint, price=float(pscale), liquidity=10000, holders=60 * hscale))
            market.nominations[start_time] = body

            def series(now, start_time=start_time, mint=mint, start_h=start_h, target=target):
                offset = (now - start_time).total_seconds()
                if offset < 0:
                    return None
                if offset < 300:
                    price, holders = float(pscale), 60 * hscale
                elif offset < 1100:
                    price, holders = float(pscale), None if start_h is None else start_h * hscale
                elif offset < 1500:
                    middle = 110 if start_h == 130 else (90 if start_h == 90 else 70)
                    price, holders = float(pscale), middle * hscale
                elif offset < 10000:
                    price, holders = float(pscale), 90 * hscale
                elif target is None:
                    return None
                else:
                    price, holders = float(Decimal(pscale) * (1 + Decimal(target))), 90 * hscale
                return token_object(mint, price=price, liquidity=10000, holders=holders)

            market.series[mint] = series
        return market

    with patch.object(lav, 'COHORT_A', table), patch.object(lav, 'COHORT_B', {'lcaux': ('C', False, 0.)}), patch.object(lav, 'build_market', build_market):
        source, packets = lav._capture_fresh(work)
    plane = work / 'plane'
    plane.mkdir()
    store = ResearchStore(plane)
    store.prepare_write_lookup()
    imported = lav._consume(packets[:1], source=source, mirror=work / 'mirror', plane=plane)
    if imported['_exit_code'] != 0:
        raise RuntimeError(imported)
    proposal = preview_universe_policy(store, min_holders=50, min_liquidity_usd=5000)['proposal']
    apply_universe_policy(store, repo_root=root, proposal=proposal, confirm_append_only=True)
    # This is a technical historical question, not an invented numerical finding.
    hyp = 'HYP-LC-TECHNICAL-PRIOR-001'
    prior = {'hypothesis_version_id': hyp, 'claim': 'Вопрос о конечном уровне holders технически не подтверждён: evidence bindings отсутствовали. Численный результат UNKNOWN.',
             'population': 'OPPORTUNITY_EPISODES', 'decision_timestamp': 'E1800',
             'primary_x_family': 'FIELD-HOLDER-COUNT-001 point_value E1800',
             'primary_y': 'PRICE_RELATIVE_PROXY E1800 -> E14400',
             'horizon_notional': 'E1800 -> E14400 / no executable notional',
             'cheapest_falsifier': 'One supported source-bound comparison',
             'legacy_definition': {'primary_question': 'Endpoint holder level', 'falsifier': 'Technical bindings unresolved', 'data_semantics': 'Synthetic technical history, numerical finding UNKNOWN'}}
    prior['definition_sha256'] = canonical_sha256(prior)
    at = datetime(2026, 10, 8, tzinfo=UTC)
    transaction = 'RESEARCH-TXN-LC-SYNTHETIC-PRIOR'
    decision = {'hypothesis_version_id': hyp, 'decision_kind': 'REJECT', 'reason_code': 'KILL_UNBOUND_EVIDENCE'}
    events = [_event(record_id=hyp, kind=RecordKind.HYPOTHESIS_VERSION, entity_id=hyp, hypothesis_version_id=hyp, payload=prior, created=at, transaction_id=transaction),
              _event(record_id='DEC-' + hyp, kind=RecordKind.DECISION_EVENT, entity_id='DEC-' + hyp, hypothesis_version_id=hyp, payload=decision, created=at, transaction_id=transaction)]
    normalized = []
    for record in events:
        raw = canonical_json_bytes(json.loads(record.payload_json))
        normalized.append(record.model_copy(update={'payload_json': raw.decode(), 'payload_sha256': hashlib.sha256(raw).hexdigest()}))
    store.append(normalized, transaction_id=transaction)
    oracle = {'admissions': 12, 'target_observed': 11, 'target_missing': 1, 'feature_observed': 9,
              'delta_positive': {'members': 4, 'observed': 3, 'missing': 1, 'mean': str(sum(Decimal(v[2]) for v in ROWS[:3]) / 3)},
              'delta_negative': {'members': 3, 'observed': 3, 'mean': str(sum(Decimal(v[2]) for v in ROWS[3:6]) / 3)},
              'all_observed_sum': str(sum(Decimal(v[2]) for v in ROWS if v[2] is not None)),
              'comparator': 'MUST_DERIVE_FROM_ACTUAL_QUERY_NOT_ASSUMED'}
    emit(work / 'executor-source.json', {'variant': variant, 'rows': ROWS, 'order': order, 'holder_scale': hscale, 'price_scale': pscale, 'oracle': oracle,
         'packet_sha256': hashlib.sha256(Path(packets[0]).read_bytes()).hexdigest(), 'producer_git_sha': __import__('subprocess').check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip(), 'prior_semantics': 'TECHNICAL_NEGATIVE_NOT_NUMERIC_OR_FAMILY_CLOSE', 'native_calls': 0})
    print(json.dumps({'prepared': variant, 'plane': str(plane), 'oracle': oracle}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--home', type=Path, required=True)
    parser.add_argument('--variant', choices=['primary', 'transfer'], required=True)
    args = parser.parse_args()
    prepare(args.root.resolve(), args.home.resolve(), args.variant)
