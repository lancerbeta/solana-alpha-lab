param(
  [Parameter(Mandatory=$true)][string]$SourceRoot,
  [Parameter(Mandatory=$true)][string]$BuildRoot,
  [Parameter(Mandatory=$true)][switch]$ApprovedBootstrap,
  [string]$Docker='docker'
)
$ErrorActionPreference='Stop'
if (-not $ApprovedBootstrap) { throw 'OFFICIAL_RUNTIME_BOOTSTRAP_REQUIRES_OWNER_AUTHORITY' }
$source=(Resolve-Path -LiteralPath $SourceRoot).Path
$build=[System.IO.Path]::GetFullPath($BuildRoot)
if ($build.StartsWith($source+[System.IO.Path]::DirectorySeparatorChar)) { throw 'BUILD_ROOT_INSIDE_SOURCE' }
if (Test-Path -LiteralPath $build) { throw 'BUILD_ROOT_MUST_BE_NEW' }
if ((& git -C $source rev-parse HEAD).Trim() -ne '90ba76e37515b3d521478a6d05a149fb0f1d2b75' -or (& git -C $source status --porcelain)) { throw 'SOURCE_BASE_MISMATCH_OR_DIRTY' }
New-Item -ItemType Directory -Path $build | Out-Null
$runtime=Join-Path $build 'runtime'
$snapshot=Join-Path $build 'snapshot'
New-Item -ItemType Directory -Path $runtime,$snapshot | Out-Null
foreach ($file in @('pyproject.toml','uv.lock','.python-version')) {
  Copy-Item -LiteralPath (Join-Path $source $file) -Destination $runtime
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Dockerfile') -Destination $runtime
& $Docker build --tag smial-baa-v1:local $runtime
if ($LASTEXITCODE -ne 0) { throw 'RUNTIME_BUILD_FAILED' }
& git clone --local --no-hardlinks $source (Join-Path $snapshot 'source')
if ($LASTEXITCODE -ne 0) { throw 'SNAPSHOT_CLONE_FAILED' }
& git -C $source archive --format=tar --output=(Join-Path $snapshot 'tracked.tar') HEAD
if ($LASTEXITCODE -ne 0) { throw 'TRACKED_BLOB_ARCHIVE_FAILED' }
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Snapshot.Dockerfile') -Destination (Join-Path $snapshot 'Dockerfile')
& $Docker build --tag smial-baa-v1-snapshot:local $snapshot
if ($LASTEXITCODE -ne 0) { throw 'SNAPSHOT_BUILD_FAILED' }
