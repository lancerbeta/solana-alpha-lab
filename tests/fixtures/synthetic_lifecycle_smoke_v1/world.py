"""Private deterministic lab world; never an actor or scientific producer."""
from __future__ import annotations
import hashlib
import json
import random
from decimal import Decimal
from pathlib import Path

def generate(kind='POS', seed=74109):
    rng=random.Random(seed)
    rows=[]
    for cohort in range(10):
        factors=[(s,a,b) for s in (0,1) for a in (0,1) for b in (0,1) for _ in range(4)]
        rng.shuffle(factors)
        for ordinal,(s,a,b) in enumerate(factors):
            h0=rng.randrange(150,1001)
            hg=Decimal(rng.randrange(220,361) if s else rng.randrange(-50,101))/1000
            h1=int(Decimal(h0)*(1+hg))
            prior=Decimal(rng.randrange(-50,-29) if a else rng.randrange(0,21))/1000
            lr=Decimal(rng.randrange(1080,1201) if b else rng.randrange(940,991))/1000
            p0=Decimal(rng.randrange(50,500))/100
            p1=p0*(1+prior)
            l0=Decimal(rng.randrange(10000,25001))
            noise=Decimal(rng.randrange(-8,9))/1000
            effect=Decimal('0.12')*s+Decimal('0.16')*(a*b)
            if kind=='NULL': effect=Decimal(0)
            if kind=='DECOY' and cohort>=4: effect=-effect
            ret=Decimal('-.025')+effect+noise
            identity=hashlib.sha256(f'{seed}:neutral:{cohort}:{ordinal}'.encode()).hexdigest()
            rows.append({'id':identity,'cohort':cohort,'partition':'DISCOVERY' if cohort<4 else 'VALIDATION' if cohort<7 else 'PAPER_FORWARD',
                'h0':h0,'h1':h1,'p0':str(p0),'p1':str(p1),'p_exit':str(p1*(1+ret)),
                'l0':str(l0),'l1':str(l0*lr),'hidden':[s,a,b]})
    return rows

def selected(row, family):
    if family=='SIMPLE': return Decimal(row['h1'])/row['h0']-1 >= Decimal('.20')
    return Decimal(row['p1'])/Decimal(row['p0'])-1 <= Decimal('-.02') and Decimal(row['l1'])/Decimal(row['l0']) >= Decimal('1.05')

def oracle(rows, family, partition):
    values=[r for r in rows if r['partition']==partition]
    marked=[r for r in values if selected(r,family)]
    returns=lambda data:[Decimal(r['p_exit'])/Decimal(r['p1'])-1 for r in data]
    mean=lambda data:sum(returns(data))/len(data)
    by=[]
    for cohort in sorted({r['cohort'] for r in values}):
        group=[r for r in values if r['cohort']==cohort]
        matches=[r for r in group if selected(r,family)]
        by.append({'cohort':cohort,'n':len(matches),'contrast':str(mean(matches)-mean(group))})
    contrast=mean(marked)-mean(values)
    return {'family':family,'partition':partition,'comparator':'SAME_DECISION_ELIGIBLE','n':len(marked),
        'population_n':len(values),'selected_mean':str(mean(marked)),'baseline_mean':str(mean(values)),
        'contrast':str(contrast),'by_cohort':by,'lab_positive':len(marked)>=12 and contrast>=Decimal('.05') and all(Decimal(x['contrast'])>0 for x in by)}

def prepare(output):
    recipe={'version':'1.0','tokens_per_world':320,'cohorts':10,'partition_cohorts':[4,3,3],
        'seed':74109,'decisions':['X300','Y900'],'target':'Y14400','lab_floor':'0.05',
        'lab_min_matched':12,'baseline':'SAME_DECISION_ELIGIBLE','external_world':'SYNTHETIC',
        'scientific_scope':'SYNTHETIC_LAB_ONLY','actor_fidelity':'NONE'}
    output.mkdir(parents=True,exist_ok=True)
    (output/'recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
    summary=[]
    for kind in ('POS','NULL','DECOY'):
        rows=generate(kind)
        assert len(rows)==320 and len({r['id'] for r in rows})==320
        for r in rows:
            assert selected(r,'SIMPLE')==bool(r['hidden'][0])
            assert selected(r,'COMPOUND')==bool(r['hidden'][1]*r['hidden'][2])
        for part in ('DISCOVERY','VALIDATION','PAPER_FORWARD'):
            data=[{k:v for k,v in r.items() if k!='hidden'} for r in rows if r['partition']==part]
            (output/f'{kind}-{part}.json').write_text(json.dumps(data,sort_keys=True)+'\n')
            for family in ('SIMPLE','COMPOUND'):
                result=oracle(rows,family,part)
                if part=='VALIDATION': assert result['lab_positive']==(kind=='POS')
                summary.append({'world':kind,**result})
    # Explicit four-cell interaction; marginal A is not compound discovery.
    pos=generate()
    cells={}
    for a in (0,1):
        for b in (0,1):
            group=[r for r in pos if r['hidden'][1:]==[a,b]]
            cells[f'{a}{b}']=sum(Decimal(r['p_exit'])/Decimal(r['p1'])-1 for r in group)/len(group)
    assert cells['11']-cells['10']>Decimal('.15') and abs(cells['01']-cells['00'])<Decimal('.01')
    result={'schema':'sls.world-oracle.v1','status':'PASS','worlds':summary,
        'factorial_cells':{k:str(v) for k,v in cells.items()},'hidden_membership_checked':True,
        'lab_only':True,'not_discovery':True,'recipe':recipe}
    (output/'oracle.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
