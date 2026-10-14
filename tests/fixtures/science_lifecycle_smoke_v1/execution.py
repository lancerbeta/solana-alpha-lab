"""Real public runner and HFIC methods with pass-through audit observers."""
import copy
import hashlib
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from common import ROOT, OUT, charge, dump, load, sha

def clone_plane(source,destination):
    from solana_alpha_lab.factory.research_store import ResearchStore
    shutil.copytree(source,destination)
    before=state(destination)
    prepared=ResearchStore(destination).prepare_write_lookup()
    assert state(destination)==before,'LOOKUP_PREPARATION_CHANGED_SCIENCE'
    dump(destination.parent/'overlay-preparation.json',{'native_public_method':'ResearchStore.prepare_write_lookup',
        'committed_records_unchanged':True,'fidelity':'MUTABLE_STORE_COPY_INITIALIZATION_NOT_PRODUCT_REPAIR'})

def state(plane):
    from solana_alpha_lab.factory.research_store import ExistingResearchStoreReader
    rows=tuple(ExistingResearchStoreReader(plane).iter_committed_records())
    inventory=sorted((r.record_id,str(r.record_kind),r.payload_sha256,r.transaction_id) for r in rows)
    return {'logical_sha256':hashlib.sha256(json.dumps(inventory,separators=(',',':')).encode()).hexdigest(),
        'record_counts':dict(Counter(str(r.record_kind) for r in rows)),
        'completion_ids':sorted(r.record_id for r in rows if str(r.record_kind)=='RUN_COMPLETED'),
        'records':inventory}

class Reads:
    def __init__(self,plane,spec,phase):
        import pyarrow.parquet as pq
        self.original=pq.read_table
        self.phase=phase
        self.allowed={(plane/r[k]).resolve() for r in spec['parameters']['temporal_recipe']['frozen_input']
                      for k in ('census_rel','observations_rel')}
        self.trace=[]
        self.evaluations=0
        self.target_projections=0
        self.targets=0
    def read(self,path,*args,**kwargs):
        value=Path(path).resolve()
        if value.name in ('observations.parquet','census.parquet'):
            assert value in self.allowed, 'FOREIGN_SOURCE_READER'
        columns=kwargs.get('columns')
        filters=kwargs.get('filters',[])
        if value.name=='observations.parquet' and (columns is None or 'typed_value' in columns):
            if self.phase!='NUMERIC':
                exact={k:v for k,op,v in filters if op in ('=','==')}
                assert columns is not None and all(k in exact for k in ('episode_id','field_id','point_id')), 'UNBOUNDED_VALUE_READER'
                assert exact['point_id'].startswith('E') and int(exact['point_id'][1:])<=1800, 'EARLY_TARGET_READER'
                assert any(k=='first_reliable_available_at' and op=='<=' for k,op,v in filters), 'UNBOUND_PREFIX_CLOCK'
        result=self.original(path,*args,**kwargs)
        target_n=0
        if value.name=='observations.parquet' and 'typed_value' in result.column_names and 'point_id' in result.column_names:
            target_n=sum(str(r['point_id']).startswith('E') and int(str(r['point_id'])[1:])>1800 for r in result.select(['point_id']).to_pylist())
            assert self.phase=='NUMERIC' or target_n==0, 'EARLY_TARGET_MATERIALIZATION'
        self.targets+=target_n
        self.trace.append({'file':value.name,'phase':self.phase,'columns':columns,'filters':filters,
            'rows':result.num_rows,'target_value_rows':target_n})
        return result
    def snapshot(self):
        return {'phase':self.phase,'parquet_reads':self.trace,'evaluator_invocations':self.evaluations,
            'target_projection_calls':self.target_projections,'decoded_target_value_rows':self.targets,
            'opaque_hash_bytes':'UNKNOWN_NOT_INSTRUMENTED',
            'fidelity':'REAL_READ_TABLE_AND_EVALUATOR_ENTRYPOINTS; A bulk explored-source reads allowed'}

def case(world,kind):
    base=OUT/world/kind
    return load(base/'spec.json'),load(base/'frozen.json')

def packet(spec,frozen):
    return {'experiment_spec':spec,'hypothesis_definition_sha256':frozen['selected_definition_sha256'],
        'classifier_evaluated_at':(datetime.fromisoformat(spec['as_of'].replace('Z','+00:00'))+timedelta(minutes=2)).isoformat()}

def classify_world(world, retain_pre_run=True):
    from solana_alpha_lab.factory.hfic_session import finalize_session,apply_classification,load_session_bundle
    from solana_alpha_lab.factory.episode_required_outcomes import project_episode_required_outcomes
    from solana_alpha_lab.factory.research_store import ResearchStore
    from tests.test_hfic_session import _critic_result
    plane=OUT/world/'plane'
    prepare_definition_ingress(world)
    rows=load(OUT/world/'membership-numeric-oracle.json')
    receipts={}
    for kind in ('LIST_CONTRAST','MIXED_LIST_NUMERIC'):
        spec,frozen=case(world,kind)
        reader=Reads(plane,spec,'CLASSIFY')
        # Observer falsifier, before any real source read.
        try:reader.read(Path('/foreign/observations.parquet'),columns=['typed_value'])
        except AssertionError:pass
        else:raise AssertionError('FOREIGN_CANARY_ACCEPTED')
        store=ResearchStore(plane)
        with patch('pyarrow.parquet.read_table',reader.read),patch(
            'solana_alpha_lab.factory.hfic_temporal_discovery.execute_temporal_discovery',side_effect=AssertionError('EARLY_EVALUATOR')):
            projection=project_episode_required_outcomes(spec,data_root=plane,definition_sha256=frozen['selected_definition_sha256'])
            expected=[{k:r[k] for k in ('episode_id','decision_eligible','matched','comparator')} for r in rows]
            if kind=='MIXED_LIST_NUMERIC':
                for r in expected:r['comparator']=r['decision_eligible']
            actual=[{k:r[k] for k in ('episode_id','decision_eligible','matched','comparator')} for r in projection['membership']]
            assert actual==expected, 'MEMBERSHIP_ORACLE_MISMATCH'
            corrupt=copy.deepcopy(actual);corrupt[0]['matched']=not corrupt[0]['matched']
            assert corrupt!=expected, 'CORRUPT_MASK_CANARY_ACCEPTED'
            critic=_critic_result(frozen,'PASS_TO_CLASSIFICATION')
            critic['non_claims'].append('SCRIPTED_UPSTREAM_FIXTURE_NOT_BLIND_ACTOR_OR_SCIENCE_ACCEPTANCE')
            finalized=finalize_session(frozen,critic,store=store,repo_root=ROOT,data_root=plane)
            persisted=apply_classification(frozen,packet(spec,frozen),store=store,repo_root=ROOT,data_root=plane)
        bundle=load_session_bundle(store,frozen['session_id'])
        assert bundle['classifier_receipt']['lane_classifier_terminal']=='FAST_LANE_READY', bundle
        dump(OUT/world/kind/'classified.json',bundle)
        receipts[kind]={'finalize':finalized,'classification':persisted,'reads':reader.snapshot(),
            'membership':actual,'coverage':{k:projection[k] for k in ('readiness','admissions_n','decision_n','matched_n','comparator_n')}}
    dump(OUT/world/'classification.json',receipts)
    if retain_pre_run:
        shutil.copytree(plane,OUT/world/'classified-plane')
    return {'status':'PASS','world':world,'state':state(plane)}

def prepare_definition_ingress(world):
    """Same final Spec bytes, registered before final classification; manual edge declared."""
    import subprocess
    from solana_alpha_lab.factory.run_passport import experiment_spec_sha256
    root=OUT/'definition-ingress'
    fresh=not root.exists()
    if fresh:
        result=subprocess.run(['git','clone','--no-hardlinks','--depth','1','file:///repo',str(root)],
            capture_output=True,text=True,timeout=60)
        assert result.returncode==0,'DEFINITION_CLONE_FAILED'
    pins=[]
    for kind in ('LIST_CONTRAST','MIXED_LIST_NUMERIC'):
        source=OUT/world/kind/'spec.json'
        destination=root/'configs'/'experiment_specs'/('science-'+('' if world=='base-v2' else world+'-')+kind.lower()+'.yaml')
        assert not destination.exists(),'REGISTERED_DEFINITION_ALREADY_EXISTS'
        shutil.copy2(source,destination)
        assert sha(source)==sha(destination),'DEFINITION_BYTES_CHANGED'
        pins.append({'experiment_id':load(source)['experiment_id'],'file_sha256':sha(source),
            'canonical_sha256':experiment_spec_sha256(load(source)),'slot':destination.relative_to(root).as_posix()})
    foreign=copy.deepcopy(load(OUT/world/'LIST_CONTRAST'/'spec.json'))
    foreign['experiment_id']='EXP-SCIENCE-'+('' if fresh else world.upper()+'-')+'FOREIGN-SAME-HYPOTHESIS'
    dump(root/'configs/experiment_specs'/('science-'+('' if fresh else world+'-')+'foreign.yaml'),foreign)
    dump(OUT/('definition-ingress'+('' if fresh else '-'+world)+'.json'),{'fidelity':'DEFINITION_INGRESS_FIXTURE',
        'registration_edge':'SEGMENT/UNKNOWN','created_before_final_classification':True,
        'product_source_imports':'IMMUTABLE /repo; copied definition view is not runtime code',
        'pins':pins,'foreign_experiment_id':foreign['experiment_id']})

def run(world='base',kind='LIST_CONTRAST',overlay=None,fault=None,mutate=None,retained=None):
    from solana_alpha_lab.factory.document_runner import DocumentRunner,RunContext
    from solana_alpha_lab.factory.lane_classifier import classify_lane
    from solana_alpha_lab.factory.run_passport import experiment_spec_sha256
    from solana_alpha_lab.factory.operational_store import OperationalStore
    from solana_alpha_lab.factory import hfic_temporal_discovery as temporal
    from solana_alpha_lab.factory.research_store import ResearchStore
    if retained is None:
        spec,frozen=case(world,kind)
        plane=OUT/world/'plane' if overlay is None else OUT/overlay/'plane'
    else:
        spec=load(Path(retained)/kind/'spec.json');frozen=load(Path(retained)/kind/'frozen.json')
        plane=Path(retained)/'plane'
    reader=Reads(plane,spec,'CLASSIFY')
    before=state(plane)
    args=packet(spec,frozen)
    asof=datetime.fromisoformat(args['classifier_evaluated_at'])
    with patch('pyarrow.parquet.read_table',reader.read):
        lane=classify_lane(args,root=ROOT,data_root=plane,as_of=asof)
    context_definition=frozen['selected_definition_sha256']
    if mutate is not None:
        assert lane.terminal in ('FAST_LANE_READY','REPLAY_AVAILABLE'), lane
        changes=mutate(plane,spec) or {}
        context_definition=changes.get('definition_override',context_definition)
    original=temporal.execute_temporal_discovery
    target=temporal._target_projection
    def evaluator(*a,**kw):
        charge('evaluator',world=world,kind_name=kind,overlay=overlay,fault=fault)
        reader.evaluations+=1
        assert reader.phase=='NUMERIC','EVALUATOR_ON_REPLAY_OR_DENIAL'
        return original(*a,**kw)
    def target_observer(*a,**kw):
        reader.target_projections+=1
        assert reader.phase=='NUMERIC','TARGET_ON_REPLAY_OR_DENIAL'
        return target(*a,**kw)
    reader.phase='REPLAY' if lane.terminal=='REPLAY_AVAILABLE' else 'CLASSIFY'
    adapter=temporal.run_temporal_fixed_time_from_spec
    def adapter_observer(*a,**kw):
        assert reader.phase!='REPLAY','ADAPTER_ON_COMPLETED_REPLAY'
        reader.phase='NUMERIC'
        return adapter(*a,**kw)
    original_write=Path.write_text
    original_append=ResearchStore.append
    result_base=OUT/(overlay or world)
    tag=kind+('-'+fault if fault else '')
    def write(path,*a,**kw):
        result=original_write(path,*a,**kw)
        if fault=='before-commit' and path.parent.name=='results':
            dump(result_base/(tag+'-interruption.json'),{'boundary':'RESULT_FILE_WRITTEN_BEFORE_COMPLETION_COMMIT',
                'artifact':path.name,'artifact_sha256':sha(path),'state':state(plane),'reads':reader.snapshot()})
            os._exit(71)
        return result
    def append(store,records,*a,**kw):
        result=original_append(store,records,*a,**kw)
        if fault=='after-commit' and any(str(r.record_kind)=='RUN_COMPLETED' for r in records):
            dump(result_base/(tag+'-interruption.json'),{'boundary':'COMPLETION_COMMITTED_BEFORE_CALLER_RESPONSE',
                'state':state(plane),'reads':reader.snapshot()})
            os._exit(72)
        return result
    ops=OperationalStore(result_base/(tag+'-ops.sqlite'))
    try:
        with (patch('pyarrow.parquet.read_table',reader.read),patch.object(temporal,'execute_temporal_discovery',evaluator),
            patch.object(temporal,'run_temporal_fixed_time_from_spec',adapter_observer),
            patch.object(temporal,'_target_projection',target_observer),patch.object(Path,'write_text',write),
            patch.object(ResearchStore,'append',append)):
            response=DocumentRunner(root=ROOT,store=ops).start_document(spec,spec_sha256=experiment_spec_sha256(spec),
                run_context=RunContext(plane,context_definition,lane,asof))
    finally:
        ops.close()
    receipt={'response':response,'before':before,'after':state(plane),'reads':reader.snapshot(),
        'entry_lane':lane.terminal,'spec_sha256':experiment_spec_sha256(spec),'fault':fault}
    suffix='replay' if lane.terminal=='REPLAY_AVAILABLE' else 'run'
    dump(result_base/(tag+'-'+suffix+'.json'),receipt)
    return receipt
