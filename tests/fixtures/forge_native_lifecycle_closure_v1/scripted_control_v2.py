"""Engineering reference only; no native model or authorial answer input."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--work',type=Path,required=True);a=p.parse_args();root=a.root.resolve();sys.path[:0]=[str(root),str(root/'src')]
from tests.test_forge_research_flow_reliability_v1 import EpisodeFlowTests
from tests.test_hfic_list_aware_vertical_v1 import draft,NUMERIC
from tests.test_hfic_ordinary_operation_acceptance_v1 import _operation
from tests.test_hfic_cli import critic_result_from_packet_only
from solana_alpha_lab.factory.research_store import ResearchStore
assert not a.work.exists(),'FRESH_DEVELOPMENT_CONTROL_REQUIRED';a.work.mkdir(parents=True);shutil.copytree(a.source,a.work/'plane');h=EpisodeFlowTests();h.work,h.plane,h.producer_root=a.work,a.work/'plane',root;ResearchStore(h.plane).prepare_write_lookup()
question='Among ALL same-decision eligible synthetic episodes, positive holder-count delta E300->E1800 predicts a higher mean PRICE_RELATIVE_PROXY E1800->E14400 than the full eligible baseline; descriptive, non-causal and tiny-N only.'
intent={'estimand':'mean PRICE_RELATIVE_PROXY E1800->E14400 in matched versus all same-decision eligible episodes','explanatory_condition':'delta(FIELD-HOLDER-COUNT-001,E300,E1800)>0'}
h.write('question-before-values.json',{'question':question,'authored_scope':intent,'query':draft('NUMERIC_IN_SCOPE',**NUMERIC)})
resolved=h.cli('research-scope-resolve','--spec',h.write('query.json',draft('NUMERIC_IN_SCOPE',**NUMERIC)))['canonical_query'];pre=h.preflight('LC_V2_SCRIPTED_SEMANTIC_CONTROL')
op=_operation(resolved,focus=pre['owner_focus'],journal=pre['search_key_sha256'],market=pre['market_evidence_epoch_sha256'],text=question,cap={'main':1,'preview':0,'adaptive':0},completion='LIMITED_RESULT')
e=h.cli('discovery-execute','--store',str(h.plane),'--spec',h.write('canonical.json',resolved),'--candidate-scope',h.write('scope-before-main.json',intent),'--journal-scope',pre['search_key_sha256'],'--operation',h.write('operation.json',op),'--format','json');h.write('control-evidence.json',e)
body,pre=h.authored_draft(e,e['candidate_scope'],pre['owner_focus']);body['candidates'][0]['claim']=question
h.write('control-original-card.json',body);_,frozen=h.persist_and_freeze(body,pre);h.write('control-frozen.json',frozen)
packet=frozen['critic_input_packet'];g=packet['grounded_evidence'];selected=packet['selected_candidate'];assert selected['claim']==question
assert all(selected[k]==g['candidate_scope'][k] for k in ('population','decision_timestamp','target','estimand','explanatory_condition'))
critic=critic_result_from_packet_only(packet,terminal='KILL_LOW_INFORMATION_VALUE');path=h.write('scripted-critic.json',critic);final=h.cli('finalize','--session-id',frozen['session_id'],'--critic-result',path);reader=h.cli('show-session','--session-id',frozen['session_id'],'--format','json')
h.write('summary.json',{'mode':'SCRIPTED_REFERENCE_NOT_NATIVE','session_id':frozen['session_id'],'session_state':final['session_state'],'readback_state':reader['session_state'],'scope_match':True,'claim_matches_prevalues_question':True,'main':1,'preview':0,'adaptive':0,'native_calls':0})
print(json.dumps({'status':'PASS_SCRIPTED_REFERENCE_NOT_NATIVE','session_id':frozen['session_id']}))
