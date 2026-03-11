param(
    [string]$PythonExe = "python",
    [string]$ProjectName = "legal-architect-test",
    [string]$OutputDir = "",
    [string]$ProjectType = "custom",
    [string]$Description = "I want an AI agent that analyzes legal contracts for SMEs, detects risky clauses, and uses retrieval from documents.",
    [string]$ArchitectProvider = "openai",
    [string]$ArchitectModel = "gpt-4o-mini",
    [string]$ArchitectOpenAIMode = "auto",
    [switch]$NoArchitectCache,
    [switch]$SkipInstall,
    [switch]$SkipApiSmoke,
    [switch]$AllowExistingProject,
    [int]$ApiPort = 8010
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputDir) {
    $OutputDir = Join-Path $RepoRoot "playground"
}

$RunId = Get-Date -Format "yyyyMMdd-HHmmss"
$ArtifactsRoot = Join-Path $RepoRoot "artifacts"
$RunArtifacts = Join-Path $ArtifactsRoot ("smoke-architect-" + $RunId)
New-Item -ItemType Directory -Path $RunArtifacts -Force | Out-Null

function Run-Command {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory,
        [int[]]$ExpectedExitCodes = @(0)
    )
    Write-Host "==> $Name"
    Write-Host "    $FilePath $($Arguments -join ' ')"
    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        $exitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($ExpectedExitCodes -notcontains $exitCode) {
        throw "Step '$Name' failed with exit code $exitCode (expected: $($ExpectedExitCodes -join ','))."
    }
    return $exitCode
}

function Wait-ForApi {
    param(
        [string]$Url,
        [int]$Attempts = 50,
        [int]$SleepSeconds = 1
    )
    for ($i = 0; $i -lt $Attempts; $i++) {
        try {
            $null = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 2
            return $true
        } catch {
            Start-Sleep -Seconds $SleepSeconds
        }
    }
    return $false
}

function Get-EnvValue {
    param(
        [string]$Path,
        [string]$Key
    )
    if (-not (Test-Path $Path)) {
        return ""
    }
    $prefix = "$Key="
    $line = Get-Content $Path | Where-Object { $_.StartsWith($prefix) } | Select-Object -First 1
    if (-not $line) {
        return ""
    }
    return ($line.Substring($prefix.Length)).Trim()
}

function Write-JsonFile {
    param(
        [object]$Object,
        [string]$Path,
        [int]$Depth = 16
    )
    $json = $Object | ConvertTo-Json -Depth $Depth
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $json, $encoding)
}

$ProjectDir = Join-Path $OutputDir $ProjectName
$ServerProcess = $null

try {
    Write-Host "FastAgent Architect Smoke"
    Write-Host "Repo:       $RepoRoot"
    Write-Host "OutputDir:  $OutputDir"
    Write-Host "ProjectDir: $ProjectDir"
    Write-Host "Artifacts:  $RunArtifacts"

    if ($ArchitectProvider.Trim().ToLower() -eq "openai" -and [string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
        throw "OPENAI_API_KEY is required when --architect-provider openai is used."
    }

    if (-not (Test-Path $OutputDir)) {
        New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    }
    if (Test-Path $ProjectDir) {
        if (-not $AllowExistingProject) {
            throw "Project directory already exists: $ProjectDir. Use -AllowExistingProject to overwrite."
        }
        Remove-Item -Recurse -Force $ProjectDir
    }

    $CreateArgs = @(
        "-m", "fastagent.cli.main",
        "create", $ProjectName,
        "--type", $ProjectType,
        "--description", $Description,
        "--architect-provider", $ArchitectProvider,
        "--architect-model", $ArchitectModel,
        "--architect-openai-mode", $ArchitectOpenAIMode,
        "--yes",
        "--output-dir", $OutputDir
    )
    if ($NoArchitectCache) {
        $CreateArgs += "--no-architect-cache"
    }
    Run-Command -Name "Create project" -FilePath $PythonExe -Arguments $CreateArgs -WorkingDirectory $RepoRoot | Out-Null

    $EnvPath = Join-Path $ProjectDir ".env"
    if (-not (Test-Path $EnvPath)) {
        throw "Generated project missing .env file: $EnvPath"
    }

    $ActualArchitectProvider = (Get-EnvValue -Path $EnvPath -Key "ARCHITECT_PROVIDER").ToLower()
    $ExpectedArchitectProvider = $ArchitectProvider.Trim().ToLower()
    if ($ActualArchitectProvider -ne $ExpectedArchitectProvider) {
        throw "Architect provider mismatch. expected='$ExpectedArchitectProvider' actual='$ActualArchitectProvider'. This usually means remote architect failed and fallback was used."
    }

    if (-not $SkipInstall) {
        Run-Command -Name "Install project dependencies" -FilePath $PythonExe -Arguments @("-m", "pip", "install", "-r", "requirements.txt") -WorkingDirectory $ProjectDir | Out-Null
    }

    $Info = $null
    $Health = $null
    $Chat = $null

    if (-not $SkipApiSmoke) {
        $ServerStdout = Join-Path $RunArtifacts "uvicorn_stdout.log"
        $ServerStderr = Join-Path $RunArtifacts "uvicorn_stderr.log"
        $ServerProcess = Start-Process -FilePath $PythonExe -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$ApiPort") -WorkingDirectory $ProjectDir -PassThru -RedirectStandardOutput $ServerStdout -RedirectStandardError $ServerStderr
        $BaseUrl = "http://127.0.0.1:$ApiPort"
        if (-not (Wait-ForApi -Url "$BaseUrl/health")) {
            throw "API server did not become ready at $BaseUrl/health."
        }

        $Health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get -TimeoutSec 10
        $Info = Invoke-RestMethod -Uri "$BaseUrl/info" -Method Get -TimeoutSec 10
        $ChatPayload = @{ message = "Analyze the risks in a contract with auto-renewal and penalty clauses."; session_id = "smoke-session-1" } | ConvertTo-Json
        $Chat = Invoke-RestMethod -Uri "$BaseUrl/chat" -Method Post -ContentType "application/json" -Body $ChatPayload -TimeoutSec 30

        Write-JsonFile -Object $Health -Path (Join-Path $RunArtifacts "health.json")
        Write-JsonFile -Object $Info -Path (Join-Path $RunArtifacts "info.json")
        Write-JsonFile -Object $Chat -Path (Join-Path $RunArtifacts "chat.json")
    }

    $Summary = @{
        repo_root = $RepoRoot
        output_dir = $OutputDir
        project_dir = $ProjectDir
        artifacts_dir = $RunArtifacts
        architect = @{
            expected_provider = $ExpectedArchitectProvider
            actual_provider = $ActualArchitectProvider
            model_requested = $ArchitectModel
            openai_mode = $ArchitectOpenAIMode
            cache_disabled = [bool]$NoArchitectCache
        }
        api_smoke = @{
            skipped = [bool]$SkipApiSmoke
            health_status = if ($Health) { $Health.status } else { "" }
            info_architect_provider = if ($Info) { [string]$Info.architect.provider } else { "" }
            chat_response_present = if ($Chat) { -not [string]::IsNullOrWhiteSpace([string]$Chat.response) } else { $false }
        }
    }
    $SummaryPath = Join-Path $RunArtifacts "summary.json"
    Write-JsonFile -Object $Summary -Path $SummaryPath

    Write-Host ""
    Write-Host "Architect smoke completed successfully."
    Write-Host "Summary: $SummaryPath"
}
finally {
    if ($ServerProcess -and -not $ServerProcess.HasExited) {
        Stop-Process -Id $ServerProcess.Id -Force -ErrorAction SilentlyContinue
    }
}
