"""Executor-only literal-cell rational oracle; never a Generator input."""
import argparse,hashlib,json
from fractions import Fraction
from pathlib import Path
import pyarrow.parquet as pq

p=argparse.ArgumentParser()
for name in ('plane','query','binding','main','out'): p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();assert not a.out.exists()
q=json.loads(a.query.read_text(encoding='utf-8-sig'))
b=json.loads(a.binding.read_text(encoding='utf-8-sig'))
main=json.loads(a.main.read_text(encoding='utf-8-sig'));s=main['result']
assert q['population']=='OPPORTUNITY_EPISODES' and q['hypothesis_kind']=='NUMERIC_IN_SCOPE'
assert len(b['cohorts'])==1 and not q.get('diagnostic_slices')
f=b['cohorts'][0];paths=[a.plane/f[x] for x in ('census_rel','observations_rel')]
assert [hashlib.sha256(x.read_bytes()).hexdigest() for x in paths]==[f['census_sha256'],f['observations_sha256']]
census=pq.read_table(paths[0]).to_pylist();obs=pq.read_table(paths[1]).to_pylist()
def cell(mint,point,field):
    rows=[r for r in obs if r['mint']==mint and r['point_id']==point and r['field_id']==field]
    assert len(rows)==1
    r=rows[0]
    return Fraction(str(r['typed_value'])) if r['state']=='OBSERVED' else None
def feature(mint,expr):
    if expr['op']=='point_value': return cell(mint,expr['point'],expr['field_id'])
    assert expr['op'] in ('delta','return_ratio')
    x=cell(mint,expr['start'],expr['field_id']);y=cell(mint,expr['end'],expr['field_id'])
    if x is None or y is None: return None
    return y-x if expr['op']=='delta' else (None if x==0 else y/x-1)
def predicate(value,pred):
    if value is None: return None
    threshold=Fraction(str(pred['value']))
    return {'gt':value>threshold,'gte':value>=threshold,'lt':value<threshold,'lte':value<=threshold,'eq':value==threshold}[pred['op']]
rows=[];matched=[];baseline=[];unknown=0;missing=0
for row in census:
    assert row['membership_state']=='ADMITTED'
    mint=row['mint'];values={e['name']:feature(mint,e) for e in q['features']}
    decisions=[predicate(values[e['feature']],e) for e in q['all']]
    joint_known=all(v is not None for v in values.values());unknown+=not joint_known
    selected=joint_known and all(decisions)
    target=q['target'];entry=cell(mint,target['reference_point'],target['field_id']);exit=cell(mint,target['exit_point'],target['field_id'])
    y=None if entry is None or exit is None else exit/entry-1
    if y is not None: baseline.append(y)
    if selected:
        if y is None: missing+=1
        else: matched.append(y)
    rows.append({'mint':mint,'features':{k:None if v is None else str(v) for k,v in values.items()},'joint_known':joint_known,'matched':selected,'target':None if y is None else str(y)})
expected={'population_n':len(census),'feature_unknown_n':unknown,'matched_n':sum(x['matched'] for x in rows),'observed_target_n':len(matched),'missing_target_n':missing,'mean_target':None if not matched else float(sum(matched)/len(matched))}
for k,v in expected.items():
    # Floating mean serialization is approximate; counts/predicates remain exact.
    assert s[k]==v or (k=='mean_target' and v is not None and s[k] is not None and abs(s[k]-v)<1e-14),(k,s[k],v)
base=s['baseline'];base_expected={'observed_n':len(baseline),'mean_target':float(sum(baseline)/len(baseline))}
for k,v in base_expected.items(): assert base[k]==v or (isinstance(v,float) and abs(base[k]-v)<1e-14),(k,base[k],v)
assert base['downside']['missing_n']==len(census)-len(baseline)
assert base['downside']['le_minus_20_n']==sum(v<=Fraction('-0.2') for v in baseline)
assert base['downside']['le_minus_50_n']==sum(v<=Fraction('-0.5') for v in baseline)
proof={'status':'PASS','oracle':'LITERAL_VERIFIED_CELLS_STANDARD_FRACTION_NO_PRODUCTION_FORMULA','query_sha256':hashlib.sha256(a.query.read_bytes()).hexdigest(),'main_raw_sha256':hashlib.sha256(a.main.read_bytes()).hexdigest(),'source_hashes':[f['census_sha256'],f['observations_sha256']],'actual_expected':expected,'baseline_expected':base_expected,'rows':rows,'new_scientific_looks':0,'native_input':False,'missing_is_not_zero':True}
a.out.write_bytes((json.dumps(proof,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({k:v for k,v in proof.items() if k!='rows'}))
