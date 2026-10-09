"""Grader-owned synthetic sources and fixed allocation; never a native read input."""
from __future__ import annotations
import copy, hashlib, json, shutil, sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from tests import test_hfic_list_aware_vertical_v1 as lav
from tests.test_forge_research_flow_reliability_v1 import public_cli
from tests.test_hfic_critic_prior_memory_closure_v1 import _event
from solana_alpha_lab.factory.research_store import ResearchStore, RecordKind
from solana_alpha_lab.factory.hfic_research_universe_policy import preview_universe_policy, apply_universe_policy
from solana_alpha_lab.factory.run_passport import canonical_sha256, canonical_json_bytes

HOME = ROOT/'local/forge_evidence_guided_generation_v1/native'
# Neutral identifiers are permuted before publication. Three unavailable starts
# use missing source cells; late/conflict clocks are attacked in machine probes.
# This declared adaptation preserves the PRD arithmetic, without forging a
# provider conflict/late timestamp inside a sealed result.
ROWS = [
    ('A',(50,70,90),.20), ('B',(50,70,90),.10), ('C',(50,70,90),.30),
    ('A',(130,110,90),-.20), ('B',(130,110,90),-.10), ('C',(130,110,90),-.30),
    ('A',(90,90,90),0.), ('B',(90,90,90),0.),
    ('C',(None,70,90),.50), ('C',(None,70,90),-.50),
    ('C',(50,70,90),None), ('C',(None,70,90),.40),
]
QUESTIONS = {
    'P1': 'Какая доступная характеристика holders заслуживает следующей фиксированной проверки относительно будущего price-relative downside? Назови сильную mundane alternative и различающий тест.',
    'P2': 'Что установил сохранённый результат прежнего вопроса о конечном уровне holders и что можно обоснованно делать следующим шагом в тех же границах?',
    'P3': 'Можно ли сформулировать новый поддерживаемый различающий вопрос из двух частичных прежних наблюдений, сохранив их ограничения и parent refs?',
    'P4a': 'В этом небольшом synthetic corpus оцени доступное основание для следующего вопроса. Допустим scoped отказ; независимость и достаточность информации неизвестны.',
    'P4b': 'Сравни доступные области list A и B: какой фиксированный вопрос о неблагоприятном хвосте полезен для решения о дальнейшей проверке?',
}

def emit(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')

def capture(variant, tiny=False):
    work = HOME/('sources-'+variant+('-small' if tiny else ''))
    if (work/'ready.json').exists():
        return work/'plane'
    order = list(range(len(ROWS))) if variant == 'a' else [5,2,9,6,0,11,4,8,1,10,7,3]
    if tiny:
        order = [6,7]  # two neutral null seats; too small for scientific selection
    table, paths = {}, {}
    for n,index in enumerate(order):
        labels,holders,target=ROWS[index]
        label=f'z{n+1:02d}{variant}'
        table[label]=(labels,False,0. if tiny else target)
        paths[lav.mint_of(label)]=holders
    def market(mint,now,start,_signal,target):
        from tests.test_opportunity_episodes_harness_v1 import token_object
        offset=(now-start).total_seconds()
        holds=paths.get(mint,(90,90,90))
        if offset < 1100: price, holder=1., holds[0]
        elif offset < 1500: price, holder=1., holds[1]
        elif offset < 10000: price, holder=1., holds[2]
        elif target is None: return None
        else: price, holder=1.+target,90
        return token_object(mint,price=price,liquidity=10000,holders=holder)
    work.mkdir(parents=True,exist_ok=True)
    with patch.object(lav,'COHORT_A',table),patch.object(lav,'COHORT_B',{'auxiliary':('C',False,0.)}),patch.object(lav,'market_row',market):
        source,packets=lav._capture_fresh(work)
    plane=work/'plane';plane.mkdir()
    store=ResearchStore(plane);store.prepare_write_lookup()
    imported=lav._consume(packets[:1],source=source,mirror=work/'mirror',plane=plane)
    if imported['_exit_code']!=0: raise AssertionError(imported)
    proposal=preview_universe_policy(store,min_holders=50,min_liquidity_usd=5000)['proposal']
    apply_universe_policy(store,repo_root=ROOT,proposal=proposal,confirm_append_only=True)
    emit(work/'ready.json',{'table':table,'paths':paths,'rows':len(table),'mode':'SYNTHETIC_PRODUCTION_CAPTURE_IMPORT','packet_sha256':hashlib.sha256(Path(packets[0]).read_bytes()).hexdigest()})
    return plane

def seed(plane,probe,variant):
    if probe not in {'P1','P2','P3'}: return
    records=[];at=datetime(2026,10,8,tzinfo=UTC)
    for i in range(2 if probe=='P3' else 1):
        hyp=f'HYP-OBS-{i+1:02d}'
        body={'hypothesis_version_id':hyp,'claim':'Конечный уровень holders не отличал группы при одинаковом конечном уровне.' if i==0 else 'List scope и прежний price move ограничивали применимость прежнего контраста.',
              'population':'OPPORTUNITY_EPISODES','decision_timestamp':'E1800',
              'primary_x_family':'FIELD-HOLDER-COUNT-001 point_value E1800' if i==0 else 'LIST_MEMBERSHIP',
              'primary_y':'PRICE_RELATIVE_PROXY E1800 -> E14400','horizon_notional':'E1800 -> E14400 / no executable notional',
              'negative_control':'Declared eligible complement','cheapest_falsifier':'One fixed admitted contrast',
              'legacy_definition':{'primary_question':'Exact older fixed scope; no family-wide generalization','falsifier':'Insufficient independent support','data_semantics':'Synthetic source history; current data not scientific confirmation'}}
        body['definition_sha256']=canonical_sha256(body)
        records.append(_event(record_id=hyp,kind=RecordKind.HYPOTHESIS_VERSION,entity_id=hyp,hypothesis_version_id=hyp,payload=body,created=at,transaction_id='RESEARCH-TXN-NATIVE-HISTORY'))
        reason='KILL_UNBOUND_EVIDENCE' if probe=='P2' and variant=='a' else ('CLOSE_SYNTHETIC_EXACT_QUESTION' if probe=='P2' else 'PARK_UNTIL_EVIDENCE')
        records.append(_event(record_id='DEC-'+hyp,kind=RecordKind.DECISION_EVENT,entity_id='DEC-'+hyp,hypothesis_version_id=hyp,payload={'hypothesis_version_id':hyp,'decision_kind':'REJECT','reason_code':reason},created=at,transaction_id='RESEARCH-TXN-NATIVE-HISTORY'))
    normalized=[]
    for record in records:
        raw=canonical_json_bytes(json.loads(record.payload_json))
        normalized.append(record.model_copy(update={'payload_json':raw.decode('utf-8'),'payload_sha256':hashlib.sha256(raw).hexdigest()}))
    ResearchStore(plane).append(normalized,transaction_id='RESEARCH-TXN-NATIVE-HISTORY')

def prepare(arm):
    cases=[('P1','a'),('P1','b'),('P2','a'),('P2','b'),('P3','a'),('P3','b'),('P4','a'),('P4','b')]
    for index,(probe,variant) in enumerate(cases):
        source=capture(variant,tiny=probe=='P4' and variant=='a')
        case=HOME/arm/f'case-{index+1:02d}'
        plane=case/'plane'
        if (case/'input.json').exists(): continue
        if not plane.exists(): shutil.copytree(source,plane)
        ResearchStore(plane).prepare_write_lookup();seed(plane,probe,variant)
        question=QUESTIONS[probe+variant if probe=='P4' else probe]
        focus=f'EGG_SCOPE_{index+1:02d}' if arm=='baseline' or index+1 not in (4,5,6) else f'EGG_BUILD_INPUT_{index+1:02d}'
        code,pre=public_cli(plane,'preflight','--discovery-contract','--collection','OPPORTUNITY_EPISODES','--owner-focus',focus,'--format','json')
        if code: raise AssertionError(pre)
        emit(case/'input.json',{'question':question,'preflight':pre,'authority':{'data_class':'DISPOSABLE_SYNTHETIC','main_max':2,'preview_max':2,'adaptive_max':0,'no_provider':True,'no_live':True}})
        print(json.dumps({'prepared':str(case.relative_to(ROOT)),'packet_bytes':len(json.dumps(pre['forge_context_packet'],ensure_ascii=False).encode())}),flush=True)

def upgrade_unlaunched_history(arm='baseline'):
    """Publish real partial looks before the affected native inputs are read."""
    from tests import test_forge_research_flow_reliability_v1 as flow
    from solana_alpha_lab.factory.hfic_preflight import enumerate_rdp_datasets, enumerate_closed_park_terminals
    for index in (4,5,6):
        case=HOME/arm/f'case-{index:02d}'
        if (case/'history-upgrade.json').exists(): continue
        if (case/'draft.json').exists(): raise AssertionError('NATIVE_ALREADY_AUTHORED')
        plane=case/'plane'
        harness=flow.EpisodeFlowTests()
        harness.plane=plane;harness.work=case/'grader-history';harness.work.mkdir(exist_ok=True)
        queries=[lav.draft('NUMERIC_IN_SCOPE',features=[{'name':'end_holders','op':'point_value','field_id':lav.HOLD,'point':'E1800'}],all=[{'feature':'end_holders','op':'gte','value':90}])]
        if index!=4: queries.append(lav.draft('LIST_CONTRAST',list_condition={'clauses':[{'all_of':['A']}]}))
        sources=[]
        for number,query in enumerate(queries,1):
            hyp=f'HYP-SAVED-PARTIAL-{number:02d}'
            existing=ResearchStore(plane).find_record(hyp)
            if existing is not None:
                prior=json.loads(existing.payload_json);evidence=prior['saved_observation_evidence'];scope={k:prior[k] for k in ('population','decision_timestamp','target','estimand','explanatory_condition','evidence_surface_mode')}
                sources.append({'hypothesis_version_id':hyp,'result_refs':evidence['result_refs'],'result_sha256':evidence['result_sha256'],'research_scope':scope})
                continue
            evidence,scope,_,pre=harness.look(f'EGG_SAVED_PARTIAL_{index}_{number}',query)
            # A source result is a computed partial observation, not acceptance.
            payload={**scope,'hypothesis_version_id':hyp,'session_id':f'SYNTHETIC-PRIOR-{index}-{number}',
                     'claim':'Saved fixed partial observation; limitations retained, no family-wide inference.',
                     'primary_x_family': 'FIELD-HOLDER-COUNT-001 point_value E1800' if number==1 else 'LIST_MEMBERSHIP A',
                     'primary_y':scope['target'],'horizon_notional':'E1800 -> E14400 / no execution',
                     'cheapest_falsifier':'A distinct prespecified comparison, no threshold retuning',
                     'saved_observation_evidence':evidence,'definition_sha256':canonical_sha256(scope)}
            at=datetime.now(UTC);record=_event(record_id=hyp,kind=RecordKind.HYPOTHESIS_VERSION,entity_id=hyp,hypothesis_version_id=hyp,payload=payload,created=at)
            raw=canonical_json_bytes(payload);record=record.model_copy(update={'payload_json':raw.decode(),'payload_sha256':hashlib.sha256(raw).hexdigest(),'transaction_id':'RESEARCH-TXN-NATIVE-PARTIAL-'+str(number)})
            ResearchStore(plane).append([record],transaction_id='RESEARCH-TXN-NATIVE-PARTIAL-'+str(number))
            sources.append({'hypothesis_version_id':hyp,'result_refs':evidence['result_refs'],'result_sha256':evidence['result_sha256'],'research_scope':scope})
        typed=None
        if index==4:
            dataset=next(row for row in enumerate_rdp_datasets(plane)[0] if (plane/'datasets/manifests'/(row['dataset_manifest_id']+'.published')).is_file())
            typed={'schema':'smial.egg-valid-close.runtime-receipt','schema_version':'1.0','atom_id':'EGG_EXACT_ENDPOINT_HOLDERS_RULE','rule_id':'EGG_EXACT_ENDPOINT_HOLDERS_RULE','scientific_terminal':'CLOSE_EGG_EXACT_ENDPOINT_HOLDERS_RULE','outcome_consumed':True,'dataset_fingerprint':dataset['dataset_fingerprint'],'score':{'source_result_sha256':sources[0]['result_sha256']},'synthetic_only':True}
            emit(plane/'datasets/manifests'/(dataset['dataset_manifest_id']+'.decision.json'),typed)
            ledger=enumerate_closed_park_terminals(ROOT,plane)
            if not any(row.get('terminal')==typed['scientific_terminal'] and row.get('scope_kind')=='RULE' and row.get('reopen_forbidden') is True for row in ledger): raise AssertionError('TYPED_EXACT_CLOSE_NOT_VALIDATED')
        initial=case/'input.json';initial.rename(case/'input-before-history-upgrade.json')
        code,pre=public_cli(plane,'preflight','--discovery-contract','--collection','OPPORTUNITY_EPISODES','--owner-focus',f'EGG_SCOPE_{index:02d}','--format','json')
        if code: raise AssertionError(pre)
        original=json.loads((case/'input-before-history-upgrade.json').read_text(encoding='utf-8'))
        emit(initial,{**original,'preflight':pre})
        emit(case/'history-upgrade.json',{'source_kind':'PRODUCTION_DISCOVERY_LOOKS','sources':sources,'typed_close':typed,'native_generation_started':False,'scripted_quality_numerator':False})
        print(json.dumps({'upgraded_history':index,'saved_looks':len(sources),'typed_close':bool(typed)}),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='upgrade':
        upgrade_unlaunched_history(sys.argv[2] if len(sys.argv)>2 else 'baseline')
    else:
        prepare(sys.argv[1])
        if sys.argv[1]=='candidate':upgrade_unlaunched_history('candidate')
