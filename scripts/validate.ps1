$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-NativeResult {
    param(
        [Parameter(Mandatory)] [string]$File,
        [Parameter(Mandatory)] [string[]]$Arguments
    )

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $raw = @(& $File @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
    }
    catch {
        $raw = @("NATIVE_EXCEPTION_" + $_.Exception.GetType().Name)
        $exitCode = 999
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }

    $lines = @($raw | ForEach-Object { [string]$_ })
    return [pscustomobject]@{
        ExitCode = $exitCode
        Lines = $lines
        Text = ($lines -join "`n")
    }
}

function Write-NativeOutput {
    param([Parameter(Mandatory)] [pscustomobject]$Result)
    $Result.Lines | ForEach-Object { Write-Output $_ }
}

$priorBytecode = Get-Item Env:PYTHONDONTWRITEBYTECODE -ErrorAction SilentlyContinue
$priorManaged = Get-Item Env:UV_MANAGED_PYTHON -ErrorAction SilentlyContinue
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:UV_MANAGED_PYTHON = "1"

try {
    if (
        $PSVersionTable.PSEdition -ne "Core" -or
        $PSVersionTable.PSVersion.ToString() -ne "7.6.3" -or
        $PSVersionTable.Platform -ne "Win32NT" -or
        -not [Environment]::Is64BitProcess
    ) {
        throw "POWERSHELL_RUNTIME_MISMATCH"
    }
    Write-Output "SHELL_RUNTIME: PASS"

    $root = Invoke-NativeResult -File "git.exe" -Arguments @("rev-parse", "--show-toplevel")
    if ($root.ExitCode -ne 0) { throw "NOT_INSIDE_GIT_REPOSITORY" }

    Push-Location $root.Text.Trim()
    try {
        $lock = Invoke-NativeResult -File "uv.exe" -Arguments @("lock", "--check", "--managed-python")
        Write-NativeOutput $lock
        if ($lock.ExitCode -ne 0) { throw "PYTHON_LOCK_FAILED" }
        Write-Output "PYTHON_LOCK: PASS"

        $secretResult = Invoke-NativeResult -File "uv.exe" -Arguments @(
            "run", "--locked", "--managed-python", "python", "-B",
            ".\scripts\secret_scan.py", "--self-test", "--scan-repository"
        )
        Write-NativeOutput $secretResult
        if ($secretResult.ExitCode -ne 0) { throw "SECRET_REJECTION_FAILED" }
        Write-Output "SECRET_REJECTION: PASS"

        $catalog = Invoke-NativeResult -File "uv.exe" -Arguments @(
            "run", "--locked", "--managed-python", "python", "-B",
            ".\scripts\validate_catalog.py"
        )
        Write-NativeOutput $catalog
        if ($catalog.ExitCode -ne 0) { throw "CATALOG_VALIDATION_FAILED" }
        Write-Output "CATALOG_VALIDATION: PASS"

        $resolve = Invoke-NativeResult -File "uv.exe" -Arguments @(
            "run", "--locked", "--managed-python", "python", "-B",
            ".\scripts\catalog_cli.py", "resolve-asset", "CATALOG-ROOT-001", "--json"
        )
        if ($resolve.ExitCode -ne 0 -or $resolve.Text -notmatch '"asset_id": "CATALOG-ROOT-001"') {
            throw "CATALOG_RESOLUTION_FAILED"
        }
        Write-Output "CATALOG_RESOLUTION: PASS"

        $policy = Invoke-NativeResult -File "uv.exe" -Arguments @(
            "run", "--locked", "--managed-python", "python", "-B",
            ".\scripts\validate_baseline.py"
        )
        Write-NativeOutput $policy
        if ($policy.ExitCode -ne 0) { throw "REPOSITORY_POLICY_FAILED" }
        Write-Output "REPOSITORY_POLICY: PASS"

        $hooks = Invoke-NativeResult -File "git.exe" -Arguments @(
            "config", "--local", "--get", "core.hooksPath"
        )
        if ($hooks.ExitCode -ne 0 -or $hooks.Text.Trim() -ne ".githooks") {
            throw "PRE_COMMIT_HOOK_CONFIG_FAILED"
        }
        Write-Output "PRE_COMMIT_HOOK: PASS"
        Write-Output "RESULT: PASS"
    }
    finally {
        Pop-Location
    }
}
catch {
    Write-Output "RESULT: FAIL"
    Write-Output ("ERROR_CODE: " + $_.Exception.Message)
    exit 1
}
finally {
    if ($null -eq $priorBytecode) {
        Remove-Item Env:PYTHONDONTWRITEBYTECODE -ErrorAction SilentlyContinue
    }
    else { $env:PYTHONDONTWRITEBYTECODE = $priorBytecode.Value }

    if ($null -eq $priorManaged) {
        Remove-Item Env:UV_MANAGED_PYTHON -ErrorAction SilentlyContinue
    }
    else { $env:UV_MANAGED_PYTHON = $priorManaged.Value }
}
