param([string]$ArtifactHome = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
$NativeRoot = (Resolve-Path -LiteralPath $ArtifactHome).Path
$EvaluationRoot = Join-Path $NativeRoot 'evaluation-final-v1'
$PrimaryDataRoot = Join-Path $NativeRoot 'sources-final-repair/primary/plane'
$SnapshotPath = Join-Path $NativeRoot 'execution-snapshot-final.json'
$NativePython = Join-Path $EvaluationRoot '.venv/Scripts/python.exe'
$SnapshotCheck = 'import json,sys; from dataclasses import asdict; from pathlib import Path; root=Path(sys.argv[1]); sys.path.insert(0,str(root/"src")); from solana_alpha_lab.factory.git_write_fence import repository_git_snapshot; expected=json.loads(Path(sys.argv[2]).read_text(encoding="utf-8-sig")); actual=asdict(repository_git_snapshot(root)); assert actual==expected,"EXECUTION_SNAPSHOT_CHANGED"; print(json.dumps({"snapshot":"MATCH","head":actual["head_sha"],"composite":actual["composite_sha256"]}))'
& $NativePython -X utf8 -B -c $SnapshotCheck $EvaluationRoot $SnapshotPath
if ($LASTEXITCODE -ne 0) { throw 'STOP_EXACT_COMPATIBLE_SNAPSHOT_REQUIRED' }
$ForgeCli = Join-Path $EvaluationRoot 'scripts/hypothesis_forge.py'
$ReaderOutput = & $NativePython -X utf8 -B $ForgeCli --root $EvaluationRoot --data-root $PrimaryDataRoot show-session --session-id HFIC-SESS-2949E0B69BDF6189 --format json
if ($LASTEXITCODE -ne 0) { throw 'STOP_PUBLIC_READER_FAILED' }
$Session = $ReaderOutput | ConvertFrom-Json
if ($Session.session_state -ne 'SYNTHESIS_COMPLETE' -or $Session.critic_terminal -ne 'KILL_UNBOUND_EVIDENCE' -or $Session.spent_main_looks -ne 1 -or $Session.spent_preview_looks -ne 0 -or $Session.spent_adaptive_looks -ne 0) { throw 'STOP_STORED_STATE_MISMATCH' }
$Session | Select-Object session_id,session_state,critic_terminal,identity_status,provenance_time_status,spent_main_looks,spent_preview_looks,spent_adaptive_looks | ConvertTo-Json
# Stop here. No preflight, model invocation, finalize retry or scientific look.
