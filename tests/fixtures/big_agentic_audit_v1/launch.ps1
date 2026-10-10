param(
  [Parameter(Mandatory=$true)][string]$SourceRoot,
  [Parameter(Mandatory=$true)][string]$EvidenceRoot,
  [Parameter(Mandatory=$true)][ValidateSet('smoke','core','spine','branches','recovery','probes','wal','science','bridge','critic','producer','interactions','metrics')][string]$Phase,
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9-]+$')][string]$Attempt,
  [ValidatePattern('^baa-[a-z0-9-]+-evidence$')][string]$ProducerVolume,
  [string]$Docker = 'docker'
)
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $SourceRoot).Path
$kit = $PSScriptRoot
$base = (& git -C $source rev-parse HEAD).Trim()
if ($base -ne '90ba76e37515b3d521478a6d05a149fb0f1d2b75') { throw 'AUDIT_BASE_MISMATCH' }
if (& git -C $source status --porcelain) { throw 'AUDIT_SOURCE_MUST_BE_CLEAN' }
foreach ($forbidden in @('.env','.venv','data','local','node_modules')) {
  if (Test-Path -LiteralPath (Join-Path $source $forbidden)) { throw "AUDIT_SOURCE_EXTRANEOUS_ROOT:$forbidden" }
}
$out = [System.IO.Path]::GetFullPath($EvidenceRoot)
if ($out -eq $source -or $out.StartsWith($source + [System.IO.Path]::DirectorySeparatorChar)) { throw 'AUDIT_OUTPUT_INSIDE_SOURCE' }
New-Item -ItemType Directory -Path $out -Force | Out-Null
$marker = Join-Path $out '.baa-evidence-owner'
if (-not (Test-Path -LiteralPath $marker)) {
  if ((Get-ChildItem -LiteralPath $out -Force | Measure-Object).Count -gt 0) { throw 'AUDIT_EVIDENCE_ROOT_NOT_EMPTY_OR_OWNED' }
  [System.IO.File]::WriteAllText($marker, 'BAA-2026-10-10-V1')
}
if ([System.IO.File]::ReadAllText($marker) -ne 'BAA-2026-10-10-V1') { throw 'AUDIT_EVIDENCE_OWNER_MISMATCH' }
$name = "baa-$Phase-$Attempt"
$volumeName = "$name-evidence"
$containers = @(& $Docker container ls --all --format '{{.Names}}')
if ($LASTEXITCODE -ne 0) { throw 'AUDIT_CONTAINER_DISCOVERY_FAILED' }
$volumes = @(& $Docker volume ls --format '{{.Name}}')
if ($LASTEXITCODE -ne 0) { throw 'AUDIT_VOLUME_DISCOVERY_FAILED' }
if ($name -in $containers -or $volumeName -in $volumes) { throw 'AUDIT_ATTEMPT_ALREADY_EXISTS' }
foreach ($prior in @("$name-containment.json", "$name-terminal.json", "$name-retained", $name, "$Phase-$Attempt")) {
  if (Test-Path -LiteralPath (Join-Path $out $prior)) { throw 'AUDIT_ATTEMPT_ARTIFACT_ALREADY_EXISTS' }
}
if ($Phase -eq 'bridge') {
  if (-not $ProducerVolume) { throw 'AUDIT_BRIDGE_REQUIRES_RETAINED_PRODUCER_VOLUME' }
  $producer = & $Docker volume inspect $ProducerVolume | ConvertFrom-Json | Select-Object -First 1
  if ($LASTEXITCODE -ne 0 -or $producer.Labels.'baa.campaign' -ne 'BAA-2026-10-10-V1') { throw 'AUDIT_PRODUCER_VOLUME_NOT_OWNED' }
}
& $Docker volume create --label baa.campaign=BAA-2026-10-10-V1 $volumeName | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'AUDIT_VOLUME_CREATE_FAILED' }
$created = & $Docker volume inspect $volumeName | ConvertFrom-Json | Select-Object -First 1
if ($LASTEXITCODE -ne 0 -or $created.Labels.'baa.campaign' -ne 'BAA-2026-10-10-V1') { throw 'AUDIT_CREATED_VOLUME_NOT_OWNED' }
# One bootstrap process changes only the new volume root's owner. Product
# processes below have no capabilities and use uid 1000, including children.
& $Docker run --rm --network none --read-only --user 0:0 --cap-drop ALL --cap-add CHOWN --mount "type=volume,source=$volumeName,target=/audit" smial-baa-v1-snapshot:local /bin/chown 1000:1000 /audit
if ($LASTEXITCODE -ne 0) { throw 'AUDIT_VOLUME_OWNER_FAILED' }
$entry = if ($Phase -eq 'bridge') { '/kit/bridge_probe.py' } elseif ($Phase -eq 'metrics') { '/kit/metric_probe.py' } elseif ($Phase -eq 'interactions') { '/kit/targeted_interactions.py' } elseif ($Phase -in @('probes','wal')) { '/kit/product_probes.py' } else { '/kit/run_campaign.py' }
$argv = @('create','--name',$name,'--label','baa.campaign=BAA-2026-10-10-V1',
  '--network','none','--read-only','--user','1000:1000','--cap-drop','ALL',
  '--security-opt','no-new-privileges','--pids-limit','128','--memory','2g',
  '--cpus','2','--init','--tmpfs','/tmp:rw,nosuid,noexec,size=134217728',
  '--mount',"type=bind,source=$kit,target=/kit,readonly",
  '--mount',"type=volume,source=$volumeName,target=/audit",
  '--env','SIMULATION_ONLY=1','--env','OMP_NUM_THREADS=1',
  '--env','OPENBLAS_NUM_THREADS=1','smial-baa-v1-snapshot:local',
  '/opt/venv/bin/python','-B',$entry,'--phase',$Phase,'--output',"/audit/$Phase-$Attempt")
if ($Phase -eq 'bridge') {
  $argv = $argv[0..($argv.Count-9)] + @('--mount',"type=volume,source=$ProducerVolume,target=/input,readonly") + $argv[($argv.Count-8)..($argv.Count-1)]
}
& $Docker @argv | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'AUDIT_CONTAINER_CREATE_FAILED' }
$actual = & $Docker inspect $name | ConvertFrom-Json | Select-Object -First 1
$receipt = [ordered]@{
  campaign='BAA-2026-10-10-V1'; container=$name; image=$actual.Image;
  network=$actual.HostConfig.NetworkMode; readonly_root=$actual.HostConfig.ReadonlyRootfs;
  user=$actual.Config.User; privileged=$actual.HostConfig.Privileged;
  cap_drop=$actual.HostConfig.CapDrop; security=$actual.HostConfig.SecurityOpt;
  memory=$actual.HostConfig.Memory; nano_cpus=$actual.HostConfig.NanoCpus;
  pids_limit=$actual.HostConfig.PidsLimit; restart=$actual.HostConfig.RestartPolicy.Name;
  mounts=@($actual.Mounts | Select-Object Destination,RW,Type)
}
if ($receipt.network -ne 'none' -or -not $receipt.readonly_root -or $receipt.privileged -or $receipt.user -ne '1000:1000') { throw 'AUDIT_CONTAINER_INSPECT_DENIED' }
[System.IO.File]::WriteAllText((Join-Path $out "$name-containment.json"),($receipt | ConvertTo-Json -Depth 8),[System.Text.UTF8Encoding]::new($false))
& $Docker start --attach $name
$exitCode=$LASTEXITCODE
$actual = & $Docker inspect $name | ConvertFrom-Json | Select-Object -First 1
[System.IO.File]::WriteAllText((Join-Path $out "$name-terminal.json"),([ordered]@{container=$name;exit_code=$actual.State.ExitCode;oom_killed=$actual.State.OOMKilled;running=$actual.State.Running} | ConvertTo-Json),[System.Text.UTF8Encoding]::new($false))
$retained = Join-Path $out "$name-retained"
New-Item -ItemType Directory -Path $retained -Force | Out-Null
$archiveCode = "import tarfile,pathlib; p=pathlib.Path('/archive/evidence.tar.gz'); t=tarfile.open(p,'w:gz'); [t.add(str(x),arcname=x.name) for x in sorted(pathlib.Path('/audit').iterdir())]; t.close()"
& $Docker run --rm --network none --read-only --user 1000:1000 --cap-drop ALL --security-opt no-new-privileges --mount "type=volume,source=$volumeName,target=/audit,readonly" --mount "type=bind,source=$retained,target=/archive" smial-baa-v1-snapshot:local /opt/venv/bin/python -c $archiveCode
if ($LASTEXITCODE -ne 0) { throw 'AUDIT_EVIDENCE_RETENTION_FAILED' }
exit $exitCode
