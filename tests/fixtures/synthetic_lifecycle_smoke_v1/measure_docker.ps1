param([Parameter(Mandatory=$true)][string]$OutputPath,[string]$Docker='docker')
$ErrorActionPreference='Stop'
$imageId='sha256:82dc449ba0e62a8cd2dd864a5b8130b93fe78dca4de6690d01a6332dda29c071'
$runtime=& $Docker image inspect $imageId | ConvertFrom-Json | Select-Object -First 1
if ($LASTEXITCODE -ne 0 -or $runtime.Id -ne $imageId) {throw 'EXISTING_RUNTIME_IMAGE_UNAVAILABLE'}
$label='sls.campaign=SMIAL_SYNTHETIC_LIFECYCLE_SMOKE_V1'
$names=@(& $Docker container ls --all --filter "label=$label" --format '{{.Names}}')
$rows=@()
$logBytes=0L
$logAllocated=0L
$logFailures=0
foreach ($name in $names) {
  $raw=& $Docker inspect --size --format '{{json .}}' $name | ConvertFrom-Json
  if ($raw.Config.Labels.'sls.campaign' -ne 'SMIAL_SYNTHETIC_LIFECYCLE_SMOKE_V1') {throw 'OWNERSHIP_CONFLICT'}
  $rows += [ordered]@{name=$name;running=$raw.State.Running;image=$raw.Image;writable_layer_bytes=$raw.SizeRw;log_driver=$raw.HostConfig.LogConfig.Type}
  if ($raw.LogPath -and $raw.Id -match '^[0-9a-f]{64}$' -and $raw.LogPath.StartsWith('/var/lib/docker/containers/'+$raw.Id+'/')) {
    $logStat=& wsl --distribution docker-desktop --user root -- stat -c '%s %b' -- $raw.LogPath 2>$null
    if ($LASTEXITCODE -ne 0) {
      $mapped=$raw.LogPath.Replace('/var/lib/docker/','/mnt/docker-desktop-disk/data/docker/')
      $logStat=& wsl --distribution docker-desktop --user root -- stat -c '%s %b' -- $mapped 2>$null
    }
    if ($LASTEXITCODE -eq 0 -and $logStat -match '^(\d+) (\d+)$') {$logBytes += [long]$Matches[1];$logAllocated += [long]$Matches[2]*512} else {$logFailures++}
  } else {$logFailures++}
}
if (@($rows | Where-Object {$_.running}).Count -ne 0) {throw 'AUDIT_PRODUCT_PROCESS_STILL_RUNNING'}
foreach($volume in @('sls-v1-product','sls-v1-scratch')) {
  $info=& $Docker volume inspect $volume | ConvertFrom-Json | Select-Object -First 1
  if ($info.Labels.'sls.campaign' -ne 'SMIAL_SYNTHETIC_LIFECYCLE_SMOKE_V1') {throw 'VOLUME_OWNERSHIP_CONFLICT'}
}
$helper='sls-v1-footprint-'+[DateTime]::UtcNow.ToString('yyyyMMddHHmmss')
$code='import pathlib,json,subprocess; roots={"product":"/product","scratch":"/scratch"}; print(json.dumps({name:{"logical_bytes":sum(p.stat().st_size for p in pathlib.Path(root).rglob("*") if p.is_file()),"allocated_bytes":int(subprocess.check_output(["du","-s","-B1",root],text=True).split()[0])} for name,root in roots.items()}))'
& $Docker create --name $helper --label $label --pull never --network none --read-only --user 1000:1000 --cap-drop ALL --security-opt no-new-privileges --memory 256m --pids-limit 32 --mount type=volume,source=sls-v1-product,target=/product,readonly --mount type=volume,source=sls-v1-scratch,target=/scratch,readonly $imageId /opt/venv/bin/python -B -c $code | Out-Null
if($LASTEXITCODE -ne 0){throw 'MEASUREMENT_CREATE_FAILED'}
$volumeResult=& $Docker start --attach $helper
if($LASTEXITCODE -ne 0){throw 'MEASUREMENT_FAILED'}
$volumes=$volumeResult | ConvertFrom-Json
$helperBytes=[long](& $Docker inspect --size --format '{{.SizeRw}}' $helper)
$layers=$helperBytes
foreach($row in $rows){$layers += [long]$row['writable_layer_bytes']}
$receipt=[ordered]@{measured_at=[DateTime]::UtcNow.ToString('o');volumes=$volumes;containers=$rows;measurement_helper=$helper;container_writable_layers_bytes=$layers;
  reused_image='smial-baa-v1:local';image_id=$runtime.Id;new_image_bytes=0;existing_image_reported_size_bytes=$runtime.Size;
  all_campaign_containers_stopped=$true;deleted=$false;logs_logical_bytes=if($logFailures -eq 0){$logBytes}else{$null};logs_allocated_bytes=if($logFailures -eq 0){$logAllocated}else{$null};log_stat_failures=$logFailures;
  logs_limit='Exact owned Docker log paths only; failed read remains UNKNOWN. The final measurement helper log and directory metadata are excluded (one small JSON line).'}
[IO.File]::WriteAllText([IO.Path]::GetFullPath($OutputPath),($receipt|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
$receipt | ConvertTo-Json -Depth 8
