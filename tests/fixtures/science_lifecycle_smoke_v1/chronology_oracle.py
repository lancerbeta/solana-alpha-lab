"""Independent schedule arithmetic over pinned, saved episode metadata; no target values."""
from datetime import datetime, timedelta, timezone

import pyarrow.parquet as pq

from common import OUT, load, sha


PRICE='FIELD-USD-PRICE-001'
POINTS=('E1800','E14400')
CLOCKS=('nominal_due_at','assigned_at','request_not_before','availability_deadline')


def utc(value):
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)


def independent_window(t0, point, schedule):
    seconds=int(point[1:])
    nominal=t0+timedelta(seconds=seconds)
    step=schedule['dense_step_seconds'] if seconds<=schedule['dense_until_seconds'] else schedule['hourly_step_seconds']
    epoch=datetime(1970,1,1,tzinfo=timezone.utc)
    elapsed=int((nominal-epoch).total_seconds())
    assigned=epoch+timedelta(seconds=((elapsed+step-1)//step)*step)
    return {'nominal_due_at':nominal,'assigned_at':assigned,'request_not_before':assigned,
        'availability_deadline':assigned+timedelta(seconds=schedule['availability_grace_seconds'])}


def verify(saved):
    assert saved['status']=='PASS_METADATA_ONLY', 'CHRONOLOGY_WITNESS_ABSENT'
    assert saved['target_value_cells_read']==saved['evaluator_invocations']==0
    assert saved['checked_points']==list(POINTS) and saved['checked_matched_episodes']==10
    assert saved['checked_cells']==20 and len(saved['examples'])==2
    cells=saved['cells']
    assert len(cells)==10 and len({x['episode_id'] for x in cells})==10
    expected_dates={'2026-10-01','2026-10-05'}
    assert {x['t0'][:10] for x in cells}==expected_dates
    assert {x['cohort_id'] for x in cells}==set(saved['schedule_bindings'])
    assert all(x in cells for x in saved['examples'])
    for example in cells:
        t0=utc(example['t0']);schedule=saved['schedule_bindings'][example['cohort_id']]
        assert schedule['schedule_contract']=='OPPORTUNITY_EPISODE_SCHEDULE_V1'
        assert schedule['dense_step_seconds']==300 and schedule['dense_until_seconds']>=14400
        assert schedule['availability_grace_seconds']==300
        for point in POINTS:
            row=example['points'][point]
            window=independent_window(t0,point,schedule)
            assert all(utc(row[key])==window[key] for key in CLOCKS), 'INDEPENDENT_TIME_GEOMETRY_MISMATCH'
            available=utc(row['first_reliable_available_at'])
            assert window['request_not_before']<=available<=window['availability_deadline'], 'ACTUAL_AVAILABILITY_OUTSIDE_WINDOW'
    return True


def build():
    from solana_alpha_lab.factory.hfic_grounded_discovery import resolve_published_episode_binding

    plane=OUT/'base-v3/plane'
    binding=resolve_published_episode_binding(plane)  # locator/identity only, no clock resolver
    sources=load(OUT/'base-v3/LIST_CONTRAST/classified.json')['classifier_receipt']['episode_outcome_binding']['sources']
    source_by_cohort={s['cohort_id']:s for s in sources}
    rows=load(OUT/'base-v3/membership-numeric-oracle.json')
    matched=[r for r in rows if r['matched']]
    assert len(matched)==10 and len({r['episode_id'] for r in matched})==10
    expected={r['episode_id']:r for r in matched}
    observations={}
    source_hashes=[]
    schedules={}
    for cohort in binding['cohorts']:
        cohort_id=cohort['cohort_id'];pin=source_by_cohort[cohort_id]
        assert cohort['schedule_binding']==pin['schedule_binding']
        assert sha(plane/cohort['census_rel'])==pin['census_sha256']
        assert sha(plane/cohort['observations_rel'])==pin['observations_sha256']
        source_hashes.append({'cohort_id':cohort_id,'census_sha256':pin['census_sha256'],
            'observations_sha256':pin['observations_sha256'],'schedule_sha256':pin['schedule_sha256']})
        schedules[cohort_id]=pin['schedule_binding']
        for row in pq.read_table(plane/cohort['observations_rel'],columns=[
            'episode_id','cohort_id','point_id','field_id','state','value_kind',*CLOCKS,
            'first_reliable_available_at','request_started_at','response_received_at']).to_pylist():
            if row['episode_id'] not in expected or row['point_id'] not in POINTS or row['field_id']!=PRICE:
                continue
            key=(row['episode_id'],row['point_id'])
            assert key not in observations, 'DUPLICATE_OBSERVATION_METADATA'
            observations[key]=row
    cells=[];examples=[]
    for row in matched:
        t0=utc(row['t0']);schedule=schedules[row['cohort_id']]
        point_receipts={}
        for point in POINTS:
            actual=observations[(row['episode_id'],point)]
            assert actual['cohort_id']==row['cohort_id'] and actual['state']=='OBSERVED' and actual['value_kind']=='DECIMAL'
            window=independent_window(t0,point,schedule)
            assert all(utc(actual[key])==window[key] for key in CLOCKS), 'INDEPENDENT_TIME_GEOMETRY_MISMATCH'
            available=utc(actual['first_reliable_available_at'])
            assert window['request_not_before']<=available<=window['availability_deadline'], 'ACTUAL_AVAILABILITY_OUTSIDE_WINDOW'
            assert utc(actual['request_started_at'])<=utc(actual['response_received_at'])<=available
            point_receipts[point]={key:actual[key] for key in (*CLOCKS,'first_reliable_available_at')}
        cell={'episode_id':row['episode_id'],'cohort_id':row['cohort_id'],'t0':row['t0'],'points':point_receipts}
        cells.append(cell)
        if not any(e['cohort_id']==row['cohort_id'] for e in examples):examples.append(cell)
    result={'status':'PASS_METADATA_ONLY','source_hashes':source_hashes,'checked_matched_episodes':len(matched),
        'checked_cells':len(matched)*len(POINTS),'checked_points':list(POINTS),'examples':examples,
        'cells':cells,'schedule_bindings':schedules,
        'target_value_cells_read':0,'evaluator_invocations':0,
        'method':'Independent epoch-grid arithmetic and actual observation clock metadata; no typed_value column'}
    verify(result)
    return result
