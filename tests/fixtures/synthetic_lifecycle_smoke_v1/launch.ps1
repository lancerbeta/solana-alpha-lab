param(
  [Parameter(Mandatory=$true)][string]$ProductRoot,
  [Parameter(Mandatory=$true)][string]$EvidenceRoot,
  [Parameter(Mandatory=$true)][ValidateSet('prepare','world','forge','forge-tail','trading','trading-tail','fortnight','spine','recovery','handoff','seams','finalize')][string]$Phase,
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9-]+$')][string]$Attempt,
  [string]$Docker='docker',
  [string]$InputRoot,
  [string]$ResumeRoot
)
$ErrorActionPreference='Stop'
$runtime='sha256:82dc449ba0e62a8cd2dd864a5b8130b93fe78dca4de6690d01a6332dda29c071'
& $Docker image inspect --format '{{.Id}}' $runtime | Out-Null
if($LASTEXITCODE -ne 0){throw 'EXISTING_PINNED_RUNTIME_UNAVAILABLE_NO_PULL'}
$product=(Resolve-Path -LiteralPath $ProductRoot).Path
$kit=$PSScriptRoot
$out=[IO.Path]::GetFullPath($EvidenceRoot)
function CampaignUsage {
  param([string]$RunningContainer)
  $seconds=0.0
  $names=@(& $Docker container ls --all --filter 'label=sls.campaign=SMIAL_SYNTHETIC_LIFECYCLE_SMOKE_V1' --format '{{.Names}}')
  foreach ($item in $names) {
    $times=& $Docker inspect --format '{{json .State}}' $item | ConvertFrom-Json
    if ($times.StartedAt -and -not $times.StartedAt.StartsWith('0001')) {
      $begin=[DateTimeOffset]::Parse($times.StartedAt)
      $end=if ($times.Running) {[DateTimeOffset]::UtcNow} elseif ($times.FinishedAt -and -not $times.FinishedAt.StartsWith('0001')) {[DateTimeOffset]::Parse($times.FinishedAt)} else {$begin}
      $seconds += [Math]::Max(0,($end-$begin).TotalSeconds)
    }
  }
  $bytes=0L
  if (Test-Path -LiteralPath $out) { Get-ChildItem -LiteralPath $out -File -Recurse | ForEach-Object {$bytes += $_.Length} }
  $scratchBytes=0L
  if ($RunningContainer) {
    $scratchPath=if ($Phase -eq 'finalize') {'/stage/tmp'} else {'/audit/tmp'}
    $size=& $Docker exec $RunningContainer /opt/venv/bin/python -B -c 'import pathlib,sys; print(sum(p.stat().st_size for p in pathlib.Path(sys.argv[1]).rglob("*") if p.is_file()))' $scratchPath 2>$null
    if ($LASTEXITCODE -eq 0) {$scratchBytes=[long]$size}
  }
  return [ordered]@{active_container_seconds=$seconds;retained_bytes=$bytes;scratch_bytes=$scratchBytes;seconds_limit=7200;bytes_limit=2147483648}
}
$initialUsage=CampaignUsage
if ($initialUsage.active_container_seconds -ge 7200 -or $initialUsage.retained_bytes -ge 2147483648) { throw 'CAMPAIGN_RESOURCE_LIMIT_BEFORE_START' }
if ($out.StartsWith($product+[IO.Path]::DirectorySeparatorChar) -or $out -eq $product) { throw 'EVIDENCE_INSIDE_PRODUCT' }
foreach ($bad in @('.env','data','local','.venv','node_modules')) {
  if (Test-Path -LiteralPath (Join-Path $product $bad)) { throw 'PRODUCT_EXTRANEOUS_ROOT' }
}
$name="sls-v1-$Phase-$Attempt"
$run=Join-Path $out $name
if (Test-Path -LiteralPath $run) { throw 'ATTEMPT_ALREADY_EXISTS' }
if ($name -in @(& $Docker container ls --all --format '{{.Names}}')) { throw 'CONTAINER_ALREADY_EXISTS' }
New-Item -ItemType Directory -Path $run | Out-Null
[IO.File]::WriteAllText((Join-Path $run '.sls-owner'),'SMIAL_SYNTHETIC_LIFECYCLE_SMOKE_V1')
$kitSnapshot=Join-Path $out ("kit-"+$name)
if (Test-Path -LiteralPath $kitSnapshot) { throw 'KIT_SNAPSHOT_ALREADY_EXISTS' }
Copy-Item -LiteralPath $kit -Destination $kitSnapshot -Recurse
$kitPins=@(Get-ChildItem -LiteralPath $kitSnapshot -File | ForEach-Object { [ordered]@{name=$_.Name;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()} })
[IO.File]::WriteAllText((Join-Path $run 'kit-pins.json'),($kitPins | ConvertTo-Json -Depth 4),[Text.UTF8Encoding]::new($false))
$argv=@('create','--name',$name,'--label','sls.campaign=SMIAL_SYNTHETIC_LIFECYCLE_SMOKE_V1',
  '--network','none','--read-only','--user','1000:1000','--cap-drop','ALL',
  '--security-opt','no-new-privileges','--pids-limit','128','--memory','2g','--cpus','2',
  '--init','--tmpfs','/tmp:rw,nosuid,noexec,size=134217728',
  '--mount','type=volume,source=sls-v1-product,target=/repo,readonly',
  '--mount',"type=bind,source=$kitSnapshot,target=/kit,readonly",
  '--env','SIMULATION_ONLY=1','--env','OMP_NUM_THREADS=1','--env','OPENBLAS_NUM_THREADS=1')
if ($InputRoot) {
  $inputPath=(Resolve-Path -LiteralPath $InputRoot).Path
  if (-not $inputPath.StartsWith($out+[IO.Path]::DirectorySeparatorChar)) {throw 'INPUT_OUTSIDE_CAMPAIGN'}
  $argv+=@('--mount',"type=bind,source=$inputPath,target=/input,readonly")
}
if ($Phase -eq 'finalize') {
  if (-not $ResumeRoot) {throw 'RESUME_ROOT_REQUIRED'}
  $resume=(Resolve-Path -LiteralPath $ResumeRoot).Path
  if (-not $resume.StartsWith($out+[IO.Path]::DirectorySeparatorChar) -or (Get-Content -LiteralPath (Join-Path $resume '.sls-owner') -Raw) -ne 'SMIAL_SYNTHETIC_LIFECYCLE_SMOKE_V1') {throw 'RESUME_ROOT_UNOWNED'}
  $argv+=@('--mount',"type=bind,source=$resume,target=/audit",'--mount',"type=bind,source=$run,target=/stage",'--env','SLS_OUTPUT_ROOT=/stage','--mount','type=volume,source=sls-v1-scratch,target=/stage/tmp')
} else {
  if ($ResumeRoot) {throw 'RESUME_PHASE_DENIED'}
  $argv+=@('--mount',"type=bind,source=$run,target=/audit",'--mount','type=volume,source=sls-v1-scratch,target=/audit/tmp')
}
$argv+=@($runtime,'/opt/venv/bin/python','-B','/kit/campaign.py','--phase',$Phase)
& $Docker @argv | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'CREATE_FAILED' }
$actual=& $Docker inspect $name | ConvertFrom-Json | Select-Object -First 1
$receipt=[ordered]@{campaign='SMIAL_SYNTHETIC_LIFECYCLE_SMOKE_V1';container=$name;image=$actual.Image;
  network=$actual.HostConfig.NetworkMode;readonly_root=$actual.HostConfig.ReadonlyRootfs;user=$actual.Config.User;
  privileged=$actual.HostConfig.Privileged;cap_drop=$actual.HostConfig.CapDrop;security=$actual.HostConfig.SecurityOpt;
  memory=$actual.HostConfig.Memory;nano_cpus=$actual.HostConfig.NanoCpus;pids_limit=$actual.HostConfig.PidsLimit;
  restart=$actual.HostConfig.RestartPolicy.Name;mounts=@($actual.Mounts | Select-Object Destination,RW,Type)}
if ($receipt.image -ne $runtime -or $receipt.network -ne 'none' -or -not $receipt.readonly_root -or $receipt.privileged -or $receipt.user -ne '1000:1000' -or $receipt.memory -ne 2147483648 -or $receipt.nano_cpus -ne 2000000000 -or $receipt.pids_limit -ne 128 -or 'ALL' -notin $receipt.cap_drop -or 'no-new-privileges' -notin $receipt.security) { throw 'CONTAINMENT_DENIED' }
[IO.File]::WriteAllText((Join-Path $run 'containment.json'),($receipt | ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
 $reason=$null
try {
  & $Docker start $name | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'START_FAILED' }
  $deadline=[DateTime]::UtcNow.AddMinutes(25)
  do {
    Start-Sleep -Seconds 10
    $state=& $Docker inspect --format '{{json .State}}' $name | ConvertFrom-Json
    $usage=if ($state.Running) {CampaignUsage -RunningContainer $name} else {CampaignUsage}
    if ($state.Running -and ($usage.active_container_seconds -ge 7200 -or ($usage.retained_bytes+$usage.scratch_bytes) -ge 2147483648 -or [DateTime]::UtcNow -ge $deadline)) {
      $reason='RESOURCE_WATCHDOG'
      & $Docker stop --time 5 $name | Out-Null
      throw $reason
    }
  } while ($state.Running)
} catch {
  if (-not $reason) { $reason='LAUNCHER_ERROR' }
  throw
} finally {
  $state=& $Docker inspect --format '{{json .State}}' $name | ConvertFrom-Json
  $logs=& $Docker logs $name 2>&1 | Out-String
  [IO.File]::WriteAllText((Join-Path $run 'process.log'),$logs,[Text.UTF8Encoding]::new($false))
  $terminal=[ordered]@{phase=$Phase;attempt=$Attempt;container=$name;exit_code=$state.ExitCode;oom_killed=$state.OOMKilled;running=$state.Running;stop_reason=$reason;resources=(CampaignUsage)}
  [IO.File]::WriteAllText((Join-Path $run 'terminal.json'),($terminal | ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
}
Write-Output $logs
exit $state.ExitCode
