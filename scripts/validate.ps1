param(
    [switch]$PreCommit
)

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

$priorBytecode = Get-Item Env:PYTHONDONTWRITEBYTECODE -ErrorAction SilentlyContinue
$priorManaged = Get-Item Env:UV_MANAGED_PYTHON -ErrorAction SilentlyContinue
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:UV_MANAGED_PYTHON = "1"

try {
    if (
        $PSVersionTable.PSEdition -ne "Core" -or
        $PSVersionTable.PSVersion -lt [version]"7.6.0" -or
        $PSVersionTable.PSVersion -ge [version]"8.0.0" -or
        $PSVersionTable.Platform -ne "Win32NT" -or
        -not [Environment]::Is64BitProcess
    ) {
        throw "POWERSHELL_RUNTIME_MISMATCH"
    }
    Write-Output "SHELL_RUNTIME: PASS"

    $root = Invoke-NativeResult -File "git.exe" -Arguments @(
        "rev-parse", "--show-toplevel"
    )
    if ($root.ExitCode -ne 0) { throw "NOT_INSIDE_GIT_REPOSITORY" }

    Push-Location $root.Text.Trim()
    try {
        if ($PreCommit) {
            $diffCheck = Invoke-NativeResult -File "git.exe" -Arguments @(
                "diff", "--cached", "--check"
            )
            $diffCheck.Lines | ForEach-Object { Write-Output $_ }
            if ($diffCheck.ExitCode -ne 0) {
                throw "STAGED_DIFF_CHECK_FAILED"
            }

            $secretCheck = Invoke-NativeResult -File "uv.exe" -Arguments @(
                "run", "--locked", "--managed-python", "python", "-B",
                ".\scripts\secret_scan.py", "--self-test", "--scan-repository"
            )
            $secretCheck.Lines | ForEach-Object { Write-Output $_ }
            if ($secretCheck.ExitCode -ne 0) {
                throw "PRE_COMMIT_SECRET_CHECK_FAILED"
            }

            $derivedSync = Invoke-NativeResult -File "uv.exe" -Arguments @(
                "run", "--locked", "--managed-python", "python", "-B",
                ".\scripts\harness_sync.py", "--check", "--paths-from-staging"
            )
            $derivedSync.Lines | ForEach-Object { Write-Output $_ }
            if ($derivedSync.ExitCode -ne 0) {
                throw "PRE_COMMIT_DERIVED_HASH_DRIFT"
            }

            Write-Output "PRE_COMMIT_DERIVED_SYNC: PASS"

            $contractCheck = Invoke-NativeResult -File "uv.exe" -Arguments @(
                "run", "--locked", "--managed-python", "python", "-B",
                ".\scripts\delivery_harness.py", "check-task-contracts", "--staged"
            )
            $contractCheck.Lines | ForEach-Object { Write-Output $_ }
            if ($contractCheck.ExitCode -ne 0) {
                throw "PRE_COMMIT_TASK_CONTRACT_SCHEMA_INVALID"
            }

            Write-Output "PRE_COMMIT_JIT: PASS"
            Write-Output "RESULT: PASS"
        }
        else {
            $validation = Invoke-NativeResult -File "uv.exe" -Arguments @(
                "run", "--locked", "--managed-python", "python", "-B",
                ".\scripts\validate_ci.py"
            )
            $validation.Lines | ForEach-Object { Write-Output $_ }
            if ($validation.ExitCode -ne 0) {
                throw "PLATFORM_NEUTRAL_VALIDATION_FAILED"
            }
            Write-Output "WINDOWS_COMPATIBILITY: PASS"
            Write-Output "RESULT: PASS"
        }
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
