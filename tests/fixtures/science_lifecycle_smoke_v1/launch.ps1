param([Parameter(Mandatory=$true)][string]$RuntimeRoot,
      [Parameter(Mandatory=$true)][string]$Phase,
      [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9-]+$')][string]$Attempt,
      [switch]$UseVolumes,
      [string]$MissingRoot)
$ErrorActionPreference='Stop'
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
$containerArgs+=@('--workdir','/repo',$runtime,'/opt/venv/bin/python','-B','/kit/campaign.py',$Phase)
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
docker start $name | Out-Null
if($LASTEXITCODE -ne 0){throw 'START_FAILED'}
Write-Output $name
$deadline=[DateTime]::UtcNow.AddSeconds($(if($Phase.StartsWith('prepare')){600}else{180}))
do {
 Start-Sleep -Seconds 5
 $state=docker inspect --format '{{json .State}}' $name | ConvertFrom-Json
 if (-not $state.Running) {break}
 # Conservative host allocation bound includes the elected checkout as well.
 $files=@(Get-ChildItem -LiteralPath @($root,$checkout) -Recurse -File -Force)
 $upper=0L
 foreach($file in $files){$upper += [long]([Math]::Ceiling($file.Length/4096.0)*4096)}
 if($UseVolumes){
  $volumeBytes=docker exec $name /opt/venv/bin/python -B -c 'from footprint import measure; print(measure()["allocated_unique_bytes"])' 2>$null
  $measured=0L
  if($LASTEXITCODE -ne 0 -or @($volumeBytes).Count -ne 1 -or
     -not [long]::TryParse([string]$volumeBytes,[ref]$measured) -or $measured -lt 0){
   docker stop --time 2 $name | Out-Null
   docker logs $name 2>&1 | Out-File -LiteralPath (Join-Path $out ($Attempt+'-log.txt')) -Encoding utf8
   $state=docker inspect --format '{{json .State}}' $name | ConvertFrom-Json
   [IO.File]::WriteAllText((Join-Path $out ($Attempt+'-state.json')),($state|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
   throw 'OWNED_VOLUME_ALLOCATION_UNKNOWN_RESOURCE_ENVELOPE_DENIED'
  }
  $upper += $measured
 }
 $ownedContainers=@(docker ps -aq --filter 'label=science.campaign=SMIAL_SCIENCE_LIFECYCLE_SMOKE_V1')
 foreach($ownedContainer in $ownedContainers){
  $rwBytes=docker inspect --size --format '{{.SizeRw}}' $ownedContainer
  if($LASTEXITCODE -ne 0){throw 'OWNED_CONTAINER_ALLOCATION_UNKNOWN'}
  $upper += [long]$rwBytes
 }
 if([DateTime]::UtcNow -gt $deadline -or $upper -gt $allocationCap){
   docker stop --time 2 $name | Out-Null
   docker logs $name 2>&1 | Out-File -LiteralPath (Join-Path $out ($Attempt+'-log.txt')) -Encoding utf8
   $state=docker inspect --format '{{json .State}}' $name | ConvertFrom-Json
   [IO.File]::WriteAllText((Join-Path $out ($Attempt+'-state.json')),($state|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
   throw 'OWNED_PROCESS_STOPPED_RESOURCE_ENVELOPE'
 }
} while($state.Running)
docker logs $name 2>&1 | Out-File -LiteralPath (Join-Path $out ($Attempt+'-log.txt')) -Encoding utf8
[IO.File]::WriteAllText((Join-Path $out ($Attempt+'-state.json')),($state|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
if($state.ExitCode -ne 0){Get-Content -LiteralPath (Join-Path $out ($Attempt+'-log.txt')) -Tail 24; throw 'PHASE_FAILED'}
