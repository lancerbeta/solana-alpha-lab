"""Ordinary native dossier/decision on actual A records; definition ingress is declared."""
from unittest.mock import patch
from common import OUT,dump,load,sha
from execution import state,case
WORLD='base-v2'

def configure(world):
    global WORLD
    assert world in ('base-v2','base-v3')
    WORLD=world

def receipt(name):
    return OUT/(('' if WORLD=='base-v2' else WORLD+'-')+name)

def foreign_id():
    return 'EXP-SCIENCE-'+('' if WORLD=='base-v2' else WORLD.upper()+'-')+'FOREIGN-SAME-HYPOTHESIS'

def application():
    from solana_alpha_lab.factory.application import FactoryApplication
    return FactoryApplication(root=OUT/'definition-ingress',
        spec_relative='configs/experiment_specs/science-'+('' if WORLD=='base-v2' else WORLD+'-')+'list_contrast.yaml',
        research_data_root=OUT/WORLD/'plane')

def locator(experiment_id):
    from solana_alpha_lab.factory.research_workbench import LifecycleEntityLocatorV1
    return LifecycleEntityLocatorV1(experiment_id,'GIT','EXPERIMENT_SPEC')

def command(experiment_id,snapshot,kind):
    return {'entity_id':experiment_id,'truth_plane':'GIT','native_kind':'EXPERIMENT_SPEC',
        'decision_kind':kind,'expected_evidence_snapshot_sha256':snapshot,
        'rationale':'Численный replay проверен; независимое подтверждение не установлено.',
        'next_condition':'Accepted chronological producer, source-bound reservation and independent validation evidence.'}

def protected_inventory():
    root=OUT/'definition-ingress'
    files={}
    for directory in ('configs/strategy_versions','local/factory_v1','registries'):
        path=root/directory
        if path.exists():
            for item in path.rglob('*'):
                if item.is_file():files[item.relative_to(root).as_posix()]=sha(item)
    return files

def consume():
    from solana_alpha_lab.factory.application import ApplicationError
    from solana_alpha_lab.factory.experiment_evidence import compose_experiment_dossier
    spec,frozen=case(WORLD,'LIST_CONTRAST')
    plane=OUT/WORLD/'plane'
    app=application()
    protected=protected_inventory()
    before=state(plane)
    with patch('solana_alpha_lab.factory.experiment_evidence.compose_experiment_dossier',wraps=compose_experiment_dossier) as native_compose:
        detail=app.research_detail(locator(spec['experiment_id']))
        assert native_compose.call_count>0,'ORDINARY_DOSSIER_NOT_REACHED'
    dump(receipt('dossier-before-pause.json'),detail)
    dossier=detail['dossier']
    assert dossier['planes']['execution']=='COMPLETED',dossier
    assert any(c['record_kind']=='RUN_COMPLETED' for c in dossier['direct_evidence']), 'ACTUAL_RUN_NOT_DIRECT'
    assert dossier['science_guard']['allowed'] is False,'UNSUPPORTED_SCIENTIFIC_PROMOTION'
    stale=command(spec['experiment_id'],dossier['evidence_snapshot_sha256'],'REJECT')
    pause=command(spec['experiment_id'],dossier['evidence_snapshot_sha256'],'PAUSE')
    recorded=app.record_research_decision(pause)
    assert recorded['decision_result']['status']=='DECISION_RECORDED'
    assert recorded['dossier']['planes']['decision']=='PAUSE'
    after=state(plane)
    assert after['record_counts'].get('DECISION_EVENT',0)==before['record_counts'].get('DECISION_EVENT',0)+1
    dump(receipt('pause-command.json'),pause)
    dump(receipt('pause-recorded.json'),recorded)
    refusals={}
    for name,body in [('stale',stale),('promote',command(spec['experiment_id'],
        recorded['dossier']['evidence_snapshot_sha256'],'PROMOTE'))]:
        initial=state(plane)
        try:app.record_research_decision(body)
        except ApplicationError as exc:refusals[name]=exc.code
        else:raise AssertionError('UNSUPPORTED_DECISION_ACCEPTED:'+name)
        assert initial==state(plane),'NEGATIVE_DECISION_WROTE_RECORD'
    assert refusals=={'stale':'STALE_EVIDENCE_SNAPSHOT','promote':'PROMOTE_BLOCKED'},refusals
    foreign=app.research_detail(locator(foreign_id()))
    dump(receipt('foreign-dossier.json'),foreign)
    assert not any(c['record_kind']=='RUN_COMPLETED' for c in foreign['dossier']['direct_evidence'])
    assert any(c['record_id']==recorded['decision_result']['decision_event_id']
        and c['relation']=='RELATED' for c in foreign['dossier']['related_prior_memory']),'FOREIGN_DECISION_NOT_RELATED'
    assert protected==protected_inventory(),'PROTECTED_STRATEGY_OR_ACTIVATION_FILES_CHANGED'
    dump(receipt('consumption-check.json'),{'status':'PASS','definition_fidelity':'DEFINITION_INGRESS_FIXTURE',
        'registration_edge':'SEGMENT/UNKNOWN','native_compose_calls':native_compose.call_count,
        'refusals':refusals,'before':before,'after':after,'protected_files_unchanged':True,
        'creates_strategy_version':False,'activation_or_PAPER_calls':0})
    return {'status':'PASS','planes':recorded['dossier']['planes'],'refusals':refusals}

def finish_saved():
    """Read-only finish after the overly broad RUN-as-RELATED assertion failed."""
    import subprocess
    spec,_=case(WORLD,'LIST_CONTRAST')
    app=application();plane=OUT/WORLD/'plane'
    before=state(plane)
    recorded=load(receipt('pause-recorded.json'))
    foreign=app.research_detail(locator(foreign_id()))
    assert not any(c['record_kind']=='RUN_COMPLETED' for c in foreign['dossier']['direct_evidence'])
    assert any(c['record_id']==recorded['decision_result']['decision_event_id'] and c['relation']=='RELATED'
        for c in foreign['dossier']['related_prior_memory'])
    results={}
    initial=load(receipt('dossier-before-pause.json'))['dossier']
    from solana_alpha_lab.factory.application import ApplicationError
    for name,body in [('stale',command(spec['experiment_id'],initial['evidence_snapshot_sha256'],'REJECT')),
        ('promote',command(spec['experiment_id'],recorded['dossier']['evidence_snapshot_sha256'],'PROMOTE'))]:
        try:app.record_research_decision(body)
        except ApplicationError as exc:results[name]=exc.code
        else:raise AssertionError('NEGATIVE_DECISION_ACCEPTED')
    assert results=={'stale':'STALE_EVIDENCE_SNAPSHOT','promote':'PROMOTE_BLOCKED'}
    assert state(plane)==before
    root=OUT/'definition-ingress'
    assert not (root/'local').exists(),'UNEXPECTED_ACTIVATION_OR_PAPER_STATE'
    assert subprocess.run(['git','diff','--exit-code','HEAD'],cwd=root,capture_output=True).returncode==0
    dump(receipt('consumption-check.json'),{'status':'PASS','definition_fidelity':'DEFINITION_INGRESS_FIXTURE',
        'registration_edge':'SEGMENT/UNKNOWN','refusals':results,'state':before,
        'foreign_run':'OMITTED_ON_EXPLICIT_IDENTITY_CONFLICT; NOT_DIRECT',
        'actual_same_hypothesis_decision':'RELATED_NOT_SCIENTIFIC_SUPPORT',
        'product_files_unchanged':True,'creates_strategy_version':False,'activation_or_PAPER_calls':0,
        'invalidated_audit_assertion':'Expected foreign RUN in RELATED; native contract relates only Trial/Decision/Hypothesis, excludes conflicting execution'})
    return {'status':'PASS','new_business_records':0}

def cold():
    spec,_=case(WORLD,'LIST_CONTRAST')
    app=application();plane=OUT/WORLD/'plane'
    before=state(plane)
    detail=app.research_detail(locator(spec['experiment_id']))
    history=detail['dossier']['decision_history']
    repeated=app.record_research_decision(load(receipt('pause-command.json')))
    assert repeated['decision_result']['disposition']=='REPLAY_IDENTICAL',repeated
    assert repeated['dossier']['decision_history']==history
    assert state(plane)==before,'COLD_DECISION_REPLAY_WROTE_RECORD'
    dump(receipt('cold-dossier.json'),detail)
    dump(receipt('cold-pause-replay.json'),{'status':'PASS','result':repeated['decision_result'],
        'decision_history':history,'business_state_unchanged':True,'state':before})
    return {'status':'PASS','decision':'PAUSE','new_business_records':0}
