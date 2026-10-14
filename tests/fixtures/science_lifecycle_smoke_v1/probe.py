"""Current Git metadata and AST probe; no sample values or product invocation."""
import ast
from common import ROOT,BASE,sha

def confirmation():
    import yaml
    registry=yaml.safe_load((ROOT/'configs/experiment_capability_registry_v2.yaml').read_text())
    config=yaml.safe_load((ROOT/'configs/list_a_chronological_confirmation_v1.yaml').read_text())
    routes=[]
    for row in registry['capabilities']:
        routes.append({k:row.get(k) for k in ('capability_id','status','entrypoint','input_kinds',
            'output_kinds','max_provider_calls','promotion_authority')})
    source=ROOT/'src/solana_alpha_lab/factory/capabilities.py'
    tree=ast.parse(source.read_text())
    router=next(n.value for n in tree.body if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id=='CAPABILITY_ROUTER')
    dispatch=[{'key':ast.unparse(k),'handler':ast.unparse(v)} for k,v in zip(router.keys,router.values)]
    contract=(ROOT/'docs/contracts/list_a_chronological_confirmation_v1.md').read_text()
    assert 'Обязательства следующего producer, вне текущей реализации' in contract
    assert 'Их реализации здесь нет.' in contract
    assert config['sample_binding']['status']=='UNBOUND'
    assert not any('CHRONOLOGICAL' in str(r['capability_id']) or 'confirmation' in str(r['entrypoint']).lower() for r in routes)
    paths=['configs/experiment_capability_registry_v2.yaml','configs/list_a_chronological_confirmation_v1.yaml',
        'docs/contracts/list_a_chronological_confirmation_v1.md','src/solana_alpha_lab/factory/capabilities.py',
        'src/solana_alpha_lab/factory/document_runner.py','src/solana_alpha_lab/factory/hfic_temporal_discovery.py',
        'src/solana_alpha_lab/factory/experiment_evidence.py','src/solana_alpha_lab/factory/application.py']
    return {'status':'METADATA_PROBE_COMPLETE','tested_git_sha':BASE,'audit_gap_tag':'MISSING_CONFIRMATION_PRODUCER',
        'native_terminal':None,'source_pins':{p:sha(ROOT/p) for p in paths},'registry_routes':routes,'actual_dispatch':dispatch,
        'missing_bindings':config['sample_binding']['missing_bindings'],
        'not_only_sample_unbound':True,
        'existing_route':'DocumentRunner.start_document -> execute_capability -> run_temporal_fixed_time_proxy -> run_temporal_fixed_time_from_spec -> bind_frozen_fixed_time_inputs -> explored-source loader -> execute_temporal_discovery',
        'existing_input':'Frozen exploratory HFIC recipe/releases, not accepted new immutable confirmation sample/reservation',
        'existing_output':'COMPLETE / INCONCLUSIVE / EXPLORATORY_PROXY; result/passport/RUN_COMPLETED; no new scientific look',
        'reservation_gap':'DocumentRunner writes result file and commits RUN_STARTED/COMPLETED after capability/evaluator; not a pre-values reservation',
        'consumer':'compose_experiment_dossier + science_guard consume source-owned EXPERIMENT_METRIC/EVIDENCE_BINDING/PROMOTION_CANDIDATE; technical COMPLETE does not satisfy scientific obligations',
        'alternatives':[
            {'route':'CAP-OFFLINE-CANONICAL-RECEIPT-REPLAY-001','why_not_equivalent':'Saved canonical receipt replay does not execute accepted independent List A confirmation'},
            {'route':'CAP-HFIC-TEMPORAL-FIXED-TIME-PROXY-001','why_not_equivalent':'Same explored frozen sources, exploratory proxy, no durable confirmation reservation'},
            {'route':'observation schedule compile/reuse','why_not_equivalent':'Schedule/panel binding, not inference or source-owned confirming metric'},
            {'route':'censoring/selection robustness gates','why_not_equivalent':'Other registered diagnostic estimands, not frozen List A confirmation protocol'},
            {'route':'provider quote/forward capture','why_not_equivalent':'Different entry/exit/quote contract and external authority; not episode E14400 confirmation'}],
        'conditional_scenarios':{'SC10':'BLOCKED_PRODUCT/CONTRACT','SC11':'BLOCKED_PRODUCT/CONTRACT','SC12':'BLOCKED_PRODUCT/CONTRACT'},
        'sample_value_reads':0,'B_attempts':0,'scope':'Bounded accepted registry/public dispatch owners, not a claim that no statistical code exists anywhere'}
