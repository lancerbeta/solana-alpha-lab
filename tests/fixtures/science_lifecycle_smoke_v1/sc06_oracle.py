"""Compare captured decision-prefix values independently of product role evaluation."""
import pyarrow.parquet as pq
from common import OUT, load, sha
from verify_saved import digest


def prefix(world):
    plane=OUT/world/'plane'
    sources=load(OUT/world/'LIST_CONTRAST/classified.json')['classifier_receipt']['episode_outcome_binding']['sources']
    recipe=load(OUT/world/'LIST_CONTRAST/spec.json')['parameters']['temporal_recipe']['frozen_input']
    columns=['episode_id','point_id','field_id','state','value_kind','typed_value',
             'nominal_due_at','assigned_at','request_not_before','availability_deadline','first_reliable_available_at']
    rows=[]
    for source in recipe:
        path=plane/source['observations_rel']
        pin=next(s for s in sources if s['cohort_id']==source['cohort_id'])
        assert sha(path)==pin['observations_sha256'], 'SC06_SOURCE_CHANGED'
        selected=pq.read_table(path,columns=columns,filters=[('point_id','in',
            ['E'+str(i) for i in range(0,1801,300)])]).to_pylist()
        assert selected, 'SC06_PREFIX_EMPTY'
        rows.extend(selected)
    rows.sort(key=lambda r:(r['episode_id'],r['point_id'],r['field_id']))
    assert len({r['episode_id'] for r in rows})==24, 'SC06_PREFIX_CENSUS_INCOMPLETE'
    assert all(int(r['point_id'][1:])<=1800 for r in rows)
    return {'prefix_rows':len(rows),'prefix_episode_count':24,'prefix_sha256':digest(rows),
            'source_pins':sources,'target_value_cells_read':0,'evaluator_invocations':0}


def build():
    original=prefix('base-v3');changed=prefix('changed')
    assert original['prefix_rows']==changed['prefix_rows']
    assert original['prefix_sha256']==changed['prefix_sha256'], 'SC06_DECISION_PREFIX_CHANGED'
    assert [s['observations_sha256'] for s in original['source_pins']] != [s['observations_sha256'] for s in changed['source_pins']], 'SC06_FUTURE_SOURCE_UNCHANGED'
    return {'status':'PASS_CAPTURED_PREFIX_INVARIANCE','base':original,'changed':changed,
            'method':'Filtered native Parquet rows E0..E1800; independent canonical row digest; no future typed_value decode'}
