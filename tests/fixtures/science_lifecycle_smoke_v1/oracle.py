"""Independent Fraction arithmetic. No imports from the product evaluator."""
import math
from fractions import Fraction as F

TOLERANCE=1e-12

def mean(values):
    return sum(values,F())/len(values) if values else None

def median(values):
    ordered=sorted(values)
    n=len(ordered)
    return ordered[n//2] if n%2 else (ordered[n//2-1]+ordered[n//2])/2

def close(actual,expected):
    assert isinstance(actual,(float,int)) and math.isfinite(actual), 'NONFINITE_OR_MISSING_NUMBER'
    assert abs(actual-float(expected))<=TOLERANCE, (actual,str(expected))

def expected(rows,kind):
    selected=[r for r in rows if r['matched']]
    comparator=[r for r in rows if r['decision_eligible'] and (kind=='MIXED_LIST_NUMERIC' or r['comparator'])]
    m=[F(r['return']) for r in selected]
    c=[F(r['return']) for r in comparator]
    return {'admissions_n':len(rows),'decision_n':sum(r['decision_eligible'] for r in rows),
        'matched_n':len(m),'comparator_n':len(c),'matched_mean':mean(m),
        'comparator_mean':mean(c),'contrast':mean(m)-mean(c),'median':median(m)}

def check_downside(actual,values):
    ordered=sorted(values)
    n=len(values)
    assert actual['observed_n']==n and actual['missing_n']==0
    for key,expected_count in [('negative_n',sum(v<0 for v in values)),
        ('zero_n',sum(v==0 for v in values)),('le_minus_20_n',sum(v<=F(-1,5) for v in values)),
        ('le_minus_50_n',sum(v<=F(-1,2) for v in values))]:
        assert actual[key]==expected_count,(key,actual[key],expected_count)
    for key,q in [('p05',F(1,20)),('p10',F(1,10)),('p25',F(1,4))]:
        position=(n-1)*q
        left=int(position)
        weight=position-left
        close(actual[key],ordered[left]*(1-weight)+ordered[min(left+1,n-1)]*weight)
    mass=F(n,10)
    total=sum(v*min(F(1),max(F(0),mass-i)) for i,v in enumerate(ordered))
    close(actual['es10_return'],total/mass)
    close(actual['es10_tail_mass_n'],mass)
    negative=[-v for v in values if v<0]
    close(actual['negative_mass'],sum(negative,F()))
    if negative:close(actual['worst_negative_share'],max(negative)/sum(negative))
    else:assert actual['worst_negative_share'] is None

def check_summary(summary,rows,kind):
    e=expected(rows,kind)
    assert (summary['population_n'],summary['decision_eligible_n'],summary['matched_n'])==(24,20,10)
    assert summary['observed_target_n']==10 and summary['missing_target_n']==0
    assert summary['labeled_net_return'] is False and summary['target_kind']=='PRICE_RELATIVE_PROXY'
    close(summary['mean_target'],e['matched_mean'])
    close(summary['median_target'],e['median'])
    contrast=summary['research_scope']['contrast']
    assert contrast['comparator']['n']==e['comparator_n']
    close(contrast['comparator']['mean_target'],e['comparator_mean'])
    close(contrast['observed_target_difference'],e['contrast'])
    matched=[F(r['return']) for r in rows if r['matched']]
    all_d=[F(r['return']) for r in rows if r['decision_eligible']]
    close(summary['baseline']['mean_target'],mean(all_d))
    close(summary['baseline']['median_target'],median(all_d))
    assert summary['baseline']['observed_n']==20
    check_downside(summary['downside'],matched)
    check_downside(summary['baseline']['downside'],all_d)
    expected_cohorts={r['cohort_id'] for r in rows if r['matched']}
    assert len(expected_cohorts)==2
    assert {c['cohort_id'] for c in summary['by_cohort']}==expected_cohorts and len(summary['by_cohort'])==len(expected_cohorts), 'COHORT_COVERAGE_MISMATCH'
    for cohort in summary['by_cohort']:
        subset=[F(r['return']) for r in rows if r['matched'] and r['cohort_id']==cohort['cohort_id']]
        assert len(subset)==5 and cohort['matched_n']==5 and cohort['decision_eligible_n']==10
        close(cohort['mean_target'],mean(subset))
        close(cohort['median_target'],median(subset))
        check_downside(cohort['downside'],subset)
    expected_dates={r['t0'][:10] for r in rows if r['matched']}
    assert len(expected_dates)==2
    assert {b['view'] for b in summary['by_calendar_block']}==expected_dates and len(summary['by_calendar_block'])==len(expected_dates), 'CALENDAR_COVERAGE_MISMATCH'
    assert summary['block_count']==len(expected_dates)
    for block in summary['by_calendar_block']:
        dates={block['view']}
        subset=[F(r['return']) for r in rows if r['matched'] and r['t0'][:10] in dates]
        assert block['observed_n']==len(subset)
        close(block['mean_target'],mean(subset));close(block['median_target'],median(subset))
        check_downside(block['downside'],subset)
    stress=summary['missing_stress_model']
    assert stress['label']=='MODEL' and stress['writes_raw_history'] is False
    close(stress['mean_target'],mean(matched))
    return {**e,'numeric_verified':True,'downside_cohort_calendar_verified':True,
        'cost_status':summary['cost']['status'],'cost_fidelity':'NATIVE_RECIPE; NOT_MEASURED_TRADING_COST'}

def canaries():
    close(.11,F(11,100))
    for bad in (.055,float('nan'),float('inf')):
        try:
            close(bad,F(11,100))
        except AssertionError:
            continue
        raise AssertionError('NUMERIC_CORRUPTION_ACCEPTED')
    return {'corrupt_contrast_rejected':True,'nonfinite_rejected':True,'absolute_tolerance':TOLERANCE}
