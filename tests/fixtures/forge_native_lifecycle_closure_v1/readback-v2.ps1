param([Parameter(Mandatory=$true)][string]$ArtifactHome)
$ErrorActionPreference='Stop'
$NativeRoot=(Resolve-Path -LiteralPath $ArtifactHome).Path
$EvaluationRoot=Join-Path $NativeRoot 'evaluation-replan-v2-final'
$NativePython=Join-Path $EvaluationRoot '.venv/Scripts/python.exe'
$SnapshotPath=Join-Path $NativeRoot 'execution-snapshot-replan-v2-final.json'
$SnapshotCheck='import json,sys; from dataclasses import asdict; from pathlib import Path; root=Path(sys.argv[1]); sys.path.insert(0,str(root/"src")); from solana_alpha_lab.factory.git_write_fence import repository_git_snapshot; expected=json.loads(Path(sys.argv[2]).read_text(encoding="utf-8-sig")); actual=asdict(repository_git_snapshot(root)); assert actual==expected,"EXECUTION_SNAPSHOT_CHANGED"; assert actual["head_sha"]=="2cace49f8443e3cd25f243ac0b740c9f1b290b29" and actual["composite_sha256"]=="4c9ed13d6624d49f0819069f646f1977d57152b2f9e375431970bd88002769a9","FINAL_EXECUTION_ANCHOR_MISMATCH"'
& $NativePython -X utf8 -B -c $SnapshotCheck $EvaluationRoot $SnapshotPath
if($LASTEXITCODE -ne 0){throw 'STOP_EXACT_COMPATIBLE_SNAPSHOT_REQUIRED'}
$Expected=@'
[{"case": "primary", "session_id": "HFIC-SESS-0A904ED27BA2B142", "candidate_id": "HFIC-CAND-EF0827DE49C2", "critic_terminal": "KILL_STATISTICALLY_UNIDENTIFIABLE", "packet_sha256": "2d6ccdd1a31f795c987ab3605527356bc133c1c2a921ab472936d92f36cb9935"}, {"case": "transfer", "session_id": "HFIC-SESS-746BAEDBA5146130", "candidate_id": "HFIC-CAND-EE030DA200F0", "critic_terminal": "KILL_LOW_INFORMATION_VALUE", "packet_sha256": "72d85004abb2e975b8f1cf41f7849f4e653184e02c0bb4a79c6d15be0ac782cd"}]
'@ | ConvertFrom-Json
$Answer=@()
foreach($Case in $Expected){
  $DataRoot=Join-Path $NativeRoot ('sources-replan-v2-final/'+$Case.case+'/plane')
  $Raw=& $NativePython -X utf8 -B (Join-Path $EvaluationRoot 'scripts/hypothesis_forge.py') --root $EvaluationRoot --data-root $DataRoot show-session --session-id $Case.session_id --format json
  if($LASTEXITCODE -ne 0){throw 'STOP_PUBLIC_READER_FAILED'}
  $Session=$Raw|ConvertFrom-Json
  if($Session.session_state -ne 'SYNTHESIS_COMPLETE' -or $Session.critic_terminal -ne $Case.critic_terminal -or $Session.critic_input_packet_sha256 -ne $Case.packet_sha256 -or $Session.selected_candidate_id -ne $Case.candidate_id){throw 'STOP_STORED_IDENTITY_OR_TERMINAL_MISMATCH'}
  if($Session.no_git_fence_receipt.git_composite_unchanged -ne $true -or $Session.no_git_fence_receipt.preflight_git_composite_sha256 -ne '4c9ed13d6624d49f0819069f646f1977d57152b2f9e375431970bd88002769a9'){throw 'STOP_STORED_FENCE_MISMATCH'}
  if($Session.spent_main_looks -ne 1 -or $Session.spent_preview_looks -ne 0 -or $Session.spent_adaptive_looks -ne 0 -or $Session.identity_status -ne 'BOUND' -or $Session.provenance_time_status -ne 'VALID'){throw 'STOP_STORED_ACCOUNTING_OR_TIME_MISMATCH'}
  $Answer+=$Session|Select-Object session_id,session_state,critic_terminal,selected_candidate_id,identity_status,provenance_time_status,spent_main_looks,spent_preview_looks,spent_adaptive_looks
}
$Answer|ConvertTo-Json
# READ_ONLY: no preflight, finalize, model invocation or scientific look.
