param([Parameter(Mandatory=$true)][string]$ArtifactHome)
$ErrorActionPreference='Stop'
$NativeRoot=(Resolve-Path -LiteralPath $ArtifactHome).Path
$EvaluationRoot=Join-Path $NativeRoot 'evaluation-replan-v2-reviewed'
$NativePython=Join-Path $EvaluationRoot '.venv/Scripts/python.exe'
$SnapshotPath=Join-Path $NativeRoot 'execution-snapshot-replan-v2-reviewed.json'
$SnapshotCheck='import json,sys; from dataclasses import asdict; from pathlib import Path; root=Path(sys.argv[1]); sys.path.insert(0,str(root/"src")); from solana_alpha_lab.factory.git_write_fence import repository_git_snapshot; expected=json.loads(Path(sys.argv[2]).read_text(encoding="utf-8-sig")); actual=asdict(repository_git_snapshot(root)); assert actual==expected,"EXECUTION_SNAPSHOT_CHANGED"; assert actual["head_sha"]=="3ba655608098f6b1bb086f90037ac64bb092db27" and actual["composite_sha256"]=="ea9485a20bb42c495a98b88a4b5c700829735b93f3318c823b8d45841cb8fade","FINAL_EXECUTION_ANCHOR_MISMATCH"'
# stdin preserves Python quotes under Windows PowerShell native argv transport.
$SnapshotCheck | & $NativePython -X utf8 -B - $EvaluationRoot $SnapshotPath
if($LASTEXITCODE -ne 0){throw 'STOP_EXACT_COMPATIBLE_SNAPSHOT_REQUIRED'}
$Expected=@'
[{"case": "primary", "session_id": "HFIC-SESS-772AA79664D4C890", "candidate_id": "HFIC-CAND-738E0E758871", "critic_terminal": "KILL_STATISTICALLY_UNIDENTIFIABLE", "packet_sha256": "b0efa793f0059fd8e764ff55c20be5b75f80a1e6741bdcf43be4a8e2e1ea70ac"}, {"case": "transfer", "session_id": "HFIC-SESS-3ED5130357EC3D74", "candidate_id": "HFIC-CAND-9123918BD5A2", "critic_terminal": "KILL_STATISTICALLY_UNIDENTIFIABLE", "packet_sha256": "09cec029c14cfef170bdb82c7815d718f1b12073bea4268c54eb8c5be1e6853c"}]
'@ | ConvertFrom-Json
$Answer=@()
foreach($Case in $Expected){
  $DataRoot=Join-Path $NativeRoot ('sources-replan-v2-reviewed/'+$Case.case+'/plane')
  $Raw=& $NativePython -X utf8 -B (Join-Path $EvaluationRoot 'scripts/hypothesis_forge.py') --root $EvaluationRoot --data-root $DataRoot show-session --session-id $Case.session_id --format json
  if($LASTEXITCODE -ne 0){throw 'STOP_PUBLIC_READER_FAILED'}
  $Session=$Raw|ConvertFrom-Json
  if($Session.session_state -ne 'SYNTHESIS_COMPLETE' -or $Session.critic_terminal -ne $Case.critic_terminal -or $Session.critic_input_packet_sha256 -ne $Case.packet_sha256 -or $Session.selected_candidate_id -ne $Case.candidate_id){throw 'STOP_STORED_IDENTITY_OR_TERMINAL_MISMATCH'}
  if($Session.no_git_fence_receipt.git_composite_unchanged -ne $true -or $Session.no_git_fence_receipt.preflight_git_composite_sha256 -ne 'ea9485a20bb42c495a98b88a4b5c700829735b93f3318c823b8d45841cb8fade'){throw 'STOP_STORED_FENCE_MISMATCH'}
  if($Session.spent_main_looks -ne 1 -or $Session.spent_preview_looks -ne 0 -or $Session.spent_adaptive_looks -ne 0 -or $Session.identity_status -ne 'BOUND' -or $Session.provenance_time_status -ne 'VALID'){throw 'STOP_STORED_ACCOUNTING_OR_TIME_MISMATCH'}
  $Answer+=$Session|Select-Object session_id,session_state,critic_terminal,selected_candidate_id,identity_status,provenance_time_status,spent_main_looks,spent_preview_looks,spent_adaptive_looks
}
$Answer|ConvertTo-Json
# READ_ONLY: no preflight, finalize, model invocation or scientific look.
