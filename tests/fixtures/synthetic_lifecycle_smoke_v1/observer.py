"""Read-only numerical observer and conservative coverage assembler."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from decimal import Decimal
from pathlib import Path

def combine(records):
    if not records or any(x.get('status')!='PASS' or not x.get('reached') for x in records):
        return 'NOT_PROVED'
    if any(x.get('fidelity')!='FULL_PRODUCT_PATH' or x.get('bridge_id') for x in records):
        return 'SEGMENT_ONLY_LONG_PATH_BLOCKED'
    if len({x.get('lineage_id') for x in records})!=1 or any(not x.get('lineage_id') for x in records):
        return 'NOT_PROVED'
    if any(not isinstance(x.get(key),str) or not x[key].strip()
           for x in records for key in ('left_boundary','right_boundary')):
        return 'NOT_PROVED'
    if any(x.get('oracle_exercised') is not True or x.get('consumer_accepted') is not True for x in records):
        return 'NOT_PROVED'
    if any(left.get('right_boundary')!=right.get('left_boundary') for left,right in zip(records,records[1:])):
        return 'NOT_PROVED'
    return 'FULL_PRODUCT_PATH'

def stats(rows):
    values=sorted(Decimal(x['p_exit'])/Decimal(x['p1'])-1 for x in rows)
    n=len(values)
    def q(fraction):
        index=(n-1)*Decimal(fraction); low=int(index)
        return values[low]+(values[min(low+1,n-1)]-values[low])*(index-low)
    mass=Decimal(n)/10; whole=int(mass)
    tail=(sum(values[:whole])+((mass-whole)*values[whole] if whole<n else 0))/mass
    return {'mean':sum(values)/n,'median':q('.5'),'p05':q('.05'),'p10':q('.10'),'p25':q('.25'),'es10_return':tail}

def verify(rows,result,family):
    def selected(x):
        if family=='SIMPLE': return Decimal(x['h1'])/Decimal(x['h0'])-1>=Decimal('.20')
        return Decimal(x['p1'])/Decimal(x['p0'])-1<=Decimal('-.02') and Decimal(x['l1'])/Decimal(x['l0'])>=Decimal('1.05')
    chosen=[x for x in rows if selected(x)]
    assert len(rows)==result['decision_eligible_n']==result['base_x_n']==128
    assert len(chosen)==result['matched_n'] and result['missing_target_n']==0
    matched,base=stats(chosen),stats(rows)
    def equal(actual,expected): assert abs(Decimal(str(actual))-expected)<Decimal('1e-12'),(actual,str(expected))
    for field,expected in [('mean_target',matched['mean']),('median_target',matched['median'])]: equal(result[field],expected)
    equal(result['baseline']['mean_target'],base['mean']);equal(result['baseline']['median_target'],base['median'])
    for field in ('p05','p10','p25','es10_return'):
        equal(result['downside'][field],matched[field]);equal(result['baseline']['downside'][field],base[field])
    cohorts=sorted({x['cohort'] for x in rows})
    assert len(result['by_cohort'])==len(cohorts)
    for index,item in zip(cohorts,result['by_cohort']):
        members=[x for x in chosen if x['cohort']==index]
        assert item['matched_n']==len(members) and item['decision_eligible_n']==32
        equal(item['mean_target'],stats(members)['mean'])
    return {'family':family,'status':'PASS','matched_n':len(chosen),'population_n':len(rows),
        'mean':str(matched['mean']),'baseline':str(base['mean']),'contrast':str(matched['mean']-base['mean']),
        'checks':['DENOMINATOR','POOLED_MEAN','MEDIAN','TYPE7_QUANTILES','FRACTIONAL_ES10','BASELINE','FOUR_COHORT_MEANS'],
        'selected_membership_observed_in_product':False,
        'membership_limit':'Product summary exposes cohort counts; selected identities not independently emitted.'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--world-root',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);a=parser.parse_args()
    world=a.world_root/'native-world'
    rows=json.loads((world/'sealed-world/POS-DISCOVERY.json').read_text())
    results=[];pins=[]
    for family in ('SIMPLE','COMPOUND'):
        path=world/f'{family}-context.json';body=json.loads(path.read_text());actual=body['evidence']['result']
        results.append(verify(rows,actual,family))
        corrupt=copy.deepcopy(actual);corrupt['mean_target']+=.01
        try: verify(rows,corrupt,family)
        except AssertionError: pass
        else: raise AssertionError('CORRUPT_NUMERIC_CANARY_FALSE_PASS')
        pins.append({'artifact':f'{family}-context.json','sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    assert combine([])=='NOT_PROVED'
    assert combine([{'status':'PASS','reached':False,'fidelity':'FULL_PRODUCT_PATH'}])=='NOT_PROVED'
    assert combine([{'status':'PASS','reached':True,'fidelity':'SEGMENT_PRODUCT_PATH','bridge_id':'BR-01'}]*2)=='SEGMENT_ONLY_LONG_PATH_BLOCKED'
    assert combine([{'status':'FAIL','reached':True}])=='NOT_PROVED'
    full={'status':'PASS','reached':True,'fidelity':'FULL_PRODUCT_PATH','lineage_id':'control',
        'left_boundary':'A','right_boundary':'B','oracle_exercised':True,'consumer_accepted':True}
    assert combine([full,dict(full,left_boundary='B',right_boundary='C')])=='FULL_PRODUCT_PATH'
    for key in ('left_boundary','right_boundary','oracle_exercised','consumer_accepted'):
        missing=copy.deepcopy(full);missing.pop(key)
        assert combine([missing])=='NOT_PROVED'
    receipt={'status':'PASS','observer':'INDEPENDENT_DECIMAL_ARITHMETIC_NO_PRODUCT_IMPORT',
        'new_main_calls':0,'source_pins':pins,'results':results,
        'canaries':{'numeric_corruption':'PASS','empty_denominator':'PASS','unvisited_boundary':'PASS','segment_aggregation':'PASS',
            'failed_attempt':'PASS','missing_full_boundary_or_oracle_metadata':'PASS','connected_full_control':'PASS'}}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))

if __name__=='__main__':main()
