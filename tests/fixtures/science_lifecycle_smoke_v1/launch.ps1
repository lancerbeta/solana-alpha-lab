param([Parameter(Mandatory=$true)][string]$RuntimeRoot,
      [Parameter(Mandatory=$true)][string]$Phase,
      [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9-]+$')][string]$Attempt,
      [switch]$UseVolumes,
      [string]$MissingRoot,
      [switch]$TelemetryFailureProbe)
$ErrorActionPreference='Stop'
# Bound every Docker client operation; timeout kills only this owned client.
function docker {
 param([Parameter(ValueFromRemainingArguments=$true)][string[]]$DockerArguments)
 $info=[Diagnostics.ProcessStartInfo]::new('docker.exe')
 $info.UseShellExecute=$false; $info.CreateNoWindow=$true
 $info.RedirectStandardOutput=$true; $info.RedirectStandardError=$true
 foreach($argument in $DockerArguments){[void]$info.ArgumentList.Add($argument)}
 $client=[Diagnostics.Process]::new(); $client.StartInfo=$info
 try {
  if(-not $client.Start()){throw 'DOCKER_CLIENT_START_FAILED'}
  $stdout=$client.StandardOutput.ReadToEndAsync(); $stderr=$client.StandardError.ReadToEndAsync()
  if(-not $client.WaitForExit(15000)){$client.Kill();throw 'DOCKER_CLIENT_TIMEOUT'}
  $global:LASTEXITCODE=$client.ExitCode
  $result=$stdout.GetAwaiter().GetResult()
  $errorText=$stderr.GetAwaiter().GetResult()
  if($result){Write-Output $result.TrimEnd("`r","`n")}
  if($errorText){Write-Information $errorText -InformationAction Continue}
 } finally {$client.Dispose()}
}
function Measure-HostBound {
 $bound=0L
 foreach($file in @(Get-ChildItem -LiteralPath @($root,$checkout) -Recurse -File -Force -ErrorAction Stop)){
  $bound += [long]([Math]::Ceiling($file.Length/4096.0)*4096)
 }
 return $bound
}
function Measure-ContainerRw {
 $bound=0L
 $identities=@(docker ps -aq --filter 'label=science.campaign=SMIAL_SCIENCE_LIFECYCLE_SMOKE_V1')
 if($LASTEXITCODE -ne 0){throw 'OWNED_CONTAINER_INVENTORY_UNKNOWN'}
 foreach($identity in $identities){
  foreach($line in ([string]$identity).Split("`n",[StringSplitOptions]::RemoveEmptyEntries)){
   $value=docker inspect --size --format '{{.SizeRw}}' $line.Trim()
   $parsed=0L
   if($LASTEXITCODE -ne 0 -or -not [long]::TryParse([string]$value,[ref]$parsed) -or $parsed -lt 0){throw 'OWNED_CONTAINER_ALLOCATION_UNKNOWN'}
   $bound += $parsed
  }
 }
 return $bound
}
$runtime='sha256:82dc449ba0e62a8cd2dd864a5b8130b93fe78dca4de6690d01a6332dda29c071'
$root=(Resolve-Path -LiteralPath $RuntimeRoot).Path
if ((Get-Content -LiteralPath (Join-Path $root '.science-owner') -Raw) -ne 'SMIAL_SCIENCE_LIFECYCLE_SMOKE_V1') {throw 'UNOWNED_RUNTIME'}
$product=Join-Path $root 'product'
$out=Join-Path $root 'output'
$manifest=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json
$allocationCap=[long]$manifest.budget.owned_retained_allocation_bytes
if($allocationCap -ne 671088640 -or $manifest.budget_replan.forward_only -ne $true){throw 'UNAUTHORIZED_ALLOCATION_CAP'}
$checkout=Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent
$kit=Join-Path $root ('kit-'+$Attempt)
if (Test-Path -LiteralPath $kit) {throw 'IMMUTABLE_ATTEMPT_ALREADY_PRESENT'}
Copy-Item -LiteralPath $PSScriptRoot -Destination $kit -Recurse
$name='science-lifecycle-v1-'+$Attempt
$mountProduct="type=bind,source=$product,target=/repo,readonly"
$mountOutput="type=bind,source=$out,target=/audit"
if($UseVolumes){
 foreach($volume in @('science-lifecycle-v1-product','science-lifecycle-v1-output')){
  $v=docker volume inspect $volume | ConvertFrom-Json | Select-Object -First 1
  if($LASTEXITCODE -ne 0 -or $v.Labels.'science.campaign' -ne 'SMIAL_SCIENCE_LIFECYCLE_SMOKE_V1'){throw 'UNOWNED_VOLUME'}
 }
 $mountProduct='type=volume,source=science-lifecycle-v1-product,target=/repo,readonly'
 $mountOutput='type=volume,source=science-lifecycle-v1-output,target=/audit'
}
$containerArgs=@('create','--name',$name,'--label','science.campaign=SMIAL_SCIENCE_LIFECYCLE_SMOKE_V1',
 '--network','none','--read-only','--user','1000:1000','--cap-drop','ALL',
 '--security-opt','no-new-privileges','--pids-limit','128','--memory','2g','--cpus','2',
 '--init','--tmpfs','/tmp:rw,nosuid,noexec,size=134217728',
 '--mount',$mountProduct,
 '--mount',"type=bind,source=$kit,target=/kit,readonly",
 '--mount',$mountOutput,
 '--env','HOME=/audit/home','--env','TMPDIR=/audit/tmp','--env','XDG_CONFIG_HOME=/audit/config',
 '--env','PYTHONPATH=/repo:/repo/src:/kit','--env','PYTHONDONTWRITEBYTECODE=1',
 '--env','SMIAL_ALLOW_TEST_CLOCK=1','--env','OMP_NUM_THREADS=1','--env','OPENBLAS_NUM_THREADS=1',
 '--env','GIT_CONFIG_COUNT=1','--env','GIT_CONFIG_KEY_0=safe.directory','--env','GIT_CONFIG_VALUE_0=/repo')
if($MissingRoot){
 $missing=(Resolve-Path -LiteralPath $MissingRoot).Path
 $descriptor=Get-Content -LiteralPath (Join-Path $missing 'fixture.json') -Raw | ConvertFrom-Json
 if($descriptor.benchmark -ne 'EPISODE-NATIVE-REQUIRED-OUTCOMES-V1' -or -not $descriptor.missing_target){throw 'NOT_EXACT_RETAINED_MISSING_SPECIMEN'}
 $containerArgs+=@('--mount',"type=bind,source=$missing,target=/missing,readonly")
}
$hostBound=Measure-HostBound
$rwBound=Measure-ContainerRw
if($hostBound+$rwBound -gt $allocationCap){throw 'PRESTART_HOST_ALLOCATION_CAP_EXCEEDED'}
$containerArgs+=@('--env',"SMIAL_AUDIT_ATTEMPT=$Attempt",'--env',"SMIAL_ALLOCATION_CAP=$allocationCap",
 '--env',"SMIAL_HOST_ALLOCATION_BOUND=$hostBound",'--env',"SMIAL_CONTAINER_RW_BOUND=$rwBound")
$entry='/kit/campaign.py'
if($Phase -eq 'resource-probe'){$entry='/kit/resource_guard_probe.py'}
$containerArgs+=@('--workdir','/repo',$runtime,'/opt/venv/bin/python','-B',$entry)
if($Phase -ne 'resource-probe'){$containerArgs+=$Phase}
docker @containerArgs | Out-Null
if($LASTEXITCODE -ne 0){throw 'CREATE_FAILED'}
$actual=docker inspect $name | ConvertFrom-Json | Select-Object -First 1
$facts=[ordered]@{image=$actual.Image;network=$actual.HostConfig.NetworkMode;readonly=$actual.HostConfig.ReadonlyRootfs;
 user=$actual.Config.User;privileged=$actual.HostConfig.Privileged;caps=$actual.HostConfig.CapDrop;
 security=$actual.HostConfig.SecurityOpt;memory=$actual.HostConfig.Memory;pids=$actual.HostConfig.PidsLimit;
 nano_cpus=$actual.HostConfig.NanoCpus;mounts=@($actual.Mounts | Select-Object Destination,RW,Type)}
if($facts.image -ne $runtime -or $facts.network -ne 'none' -or -not $facts.readonly -or $facts.privileged -or
 $facts.user -ne '1000:1000' -or 'ALL' -notin $facts.caps -or 'no-new-privileges' -notin $facts.security -or
 @($facts.mounts | Where-Object {$_.RW -and $_.Destination -ne '/audit'}).Count) {throw 'CONTAINMENT_DENIED'}
[IO.File]::WriteAllText((Join-Path $out ($Attempt+'-container.json')),($facts|ConvertTo-Json -Depth 6),[Text.UTF8Encoding]::new($false))
$started=$false
$resourceAfter=Join-Path $out ($Attempt+'-resource-after.json')
try {
 $started=$true
 docker start $name | Out-Null
 if($LASTEXITCODE -ne 0){throw 'START_FAILED'}
 Write-Output $name
 if($TelemetryFailureProbe){throw 'EXPECTED_TELEMETRY_FAILURE_PROBE'}
 $deadline=[DateTime]::UtcNow.AddSeconds($(if($Phase.StartsWith('prepare')){600}else{180}))
 do {
  Start-Sleep -Seconds 1
  $state=docker inspect --format '{{json .State}}' $name | ConvertFrom-Json
  if($LASTEXITCODE -ne 0){throw 'OWNED_STATE_UNKNOWN'}
  $upper=(Measure-HostBound)+(Measure-ContainerRw)
  if($state.Running){
   $volumeBytes=docker exec $name /opt/venv/bin/python -B -c 'from footprint import measure; print(measure()["allocated_unique_bytes"])'
   $measured=0L
   if($LASTEXITCODE -ne 0){
    # Child may exit between state read and exec; require confirmed exit and
    # the mandatory post receipt below. A still-running unknown remains DENY.
    $state=docker inspect --format '{{json .State}}' $name | ConvertFrom-Json
    if($LASTEXITCODE -ne 0 -or $state.Running){throw 'OWNED_VOLUME_ALLOCATION_UNKNOWN'}
   } else {
    if(-not [long]::TryParse([string]$volumeBytes,[ref]$measured) -or $measured -lt 0){throw 'OWNED_VOLUME_ALLOCATION_UNKNOWN'}
    $upper += $measured
   }
  }
  if([DateTime]::UtcNow -gt $deadline -or $upper -gt $allocationCap){throw 'OWNED_PROCESS_RESOURCE_ENVELOPE'}
 } while($state.Running)
 # A short-lived child checks mounted allocation before any phase and in finally.
 # Its post measurement is mandatory even when the first poll sees exited state.
 docker cp ($name+':/audit/resource-'+$Attempt+'-after.json') $resourceAfter | Out-Null
 if($LASTEXITCODE -ne 0){throw 'FINAL_VOLUME_ALLOCATION_UNKNOWN'}
 $after=Get-Content -LiteralPath $resourceAfter -Raw | ConvertFrom-Json
 if($after.stage -ne 'after' -or $after.cap_bytes -ne $allocationCap){throw 'FINAL_RESOURCE_RECEIPT_INVALID'}
 $finalBound=(Measure-HostBound)+(Measure-ContainerRw)+[long]$after.owned_volumes.allocated_unique_bytes+4096
 if($finalBound -gt $allocationCap){throw 'FINAL_ALLOCATION_CAP_EXCEEDED'}
 if($state.ExitCode -ne 0){throw 'PHASE_FAILED'}
} finally {
 # Any filesystem, telemetry, Docker-client or phase error stops only this owned child.
 if($started){
  docker stop --time 2 $name | Out-Null
  if($LASTEXITCODE -ne 0){throw 'OWNED_STOP_UNCONFIRMED'}
  $state=docker inspect --format '{{json .State}}' $name | ConvertFrom-Json
  if($LASTEXITCODE -ne 0 -or $state.Running){throw 'OWNED_STOP_READBACK_UNCONFIRMED'}
  docker logs $name 2>&1 | Out-File -LiteralPath (Join-Path $out ($Attempt+'-log.txt')) -Encoding utf8
  [IO.File]::WriteAllText((Join-Path $out ($Attempt+'-state.json')),($state|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
 }
}
