param(
    [string]$PythonExe = "python",
    [string]$WorkDir = "",
    [string]$ProjectName = "demo-agent",
    [switch]$SkipRepoTests,
    [switch]$SkipProjectInstall,
    [switch]$CleanupWorkDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $WorkDir) {
    $WorkDir = Join-Path $env:TEMP ("fastagent-e2e-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
}
$RunId = Get-Date -Format "yyyyMMdd-HHmmss"
$ArtifactsRoot = Join-Path $RepoRoot "artifacts"
$RunArtifacts = Join-Path $ArtifactsRoot ("e2e-" + $RunId)
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

function Run-FastAgent {
    param(
        [string]$Name,
        [Alias("Args")]
        [string[]]$CommandArgs,
        [int[]]$ExpectedExitCodes = @(0),
        [string]$WorkingDirectory = $RepoRoot
    )
    return Run-Command -Name $Name -FilePath $PythonExe -Arguments (@("-m", "fastagent.cli.main") + $CommandArgs) -WorkingDirectory $WorkingDirectory -ExpectedExitCodes $ExpectedExitCodes
}

function Wait-ForApi {
    param(
        [string]$Url,
        [int]$Attempts = 40,
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

function Copy-ArtifactFile {
    param(
        [string]$Source,
        [string]$DestinationDir
    )
    if (-not (Test-Path $Source)) {
        return ""
    }
    $name = Split-Path $Source -Leaf
    $destination = Join-Path $DestinationDir $name
    Copy-Item -Path $Source -Destination $destination -Force
    return $destination
}

function Write-JsonFile {
    param(
        [object]$Object,
        [string]$Path,
        [int]$Depth = 12
    )
    $json = $Object | ConvertTo-Json -Depth $Depth
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $json, $encoding)
}

$ProjectDir = Join-Path $WorkDir $ProjectName
$ServerProcess = $null

try {
    Write-Host "FastAgent E2E"
    Write-Host "Repo:      $RepoRoot"
    Write-Host "WorkDir:   $WorkDir"
    Write-Host "Artifacts: $RunArtifacts"

    if (-not $SkipRepoTests) {
        Run-Command -Name "Run repo tests" -FilePath $PythonExe -Arguments @("-m", "pytest", "-q") -WorkingDirectory $RepoRoot | Out-Null
    }

    $releaseReport = Join-Path $RunArtifacts "release_ready.json"
    Run-FastAgent -Name "Release readiness (repo)" -Args @("release-ready", "--project-path", $RepoRoot, "--output-json", $releaseReport) | Out-Null

    $sampleValidation = Join-Path $RunArtifacts "sample_artifacts_validation.json"
    Run-FastAgent -Name "Validate sample artifacts" -Args @(
        "validate-artifacts",
        "--artifact", "eval_config:$RepoRoot\examples\fastagent.eval.sample.json",
        "--artifact", "plugin_registry:$RepoRoot\examples\plugin_registry.sample.json",
        "--output-json", $sampleValidation
    ) | Out-Null

    if (Test-Path $WorkDir) {
        Remove-Item -Recurse -Force $WorkDir
    }
    New-Item -ItemType Directory -Path $WorkDir | Out-Null

    Run-FastAgent -Name "Create project" -Args @("create", $ProjectName, "--yes", "--output-dir", $WorkDir) | Out-Null
    if (-not (Test-Path (Join-Path $ProjectDir "app\main.py"))) {
        throw "Generated project missing app\main.py ($ProjectDir)."
    }

    if (-not $SkipProjectInstall) {
        Run-Command -Name "Install generated project dependencies" -FilePath $PythonExe -Arguments @("-m", "pip", "install", "-r", "requirements.txt") -WorkingDirectory $ProjectDir | Out-Null
    }

    Run-FastAgent -Name "Init CI files" -Args @("init-ci", "--project-path", $ProjectDir) | Out-Null

    $ConfigPath = Join-Path $ProjectDir "fastagent.eval.json"
    $BaselineEval = Join-Path $ProjectDir "baseline_eval.json"
    $CandidateEval = Join-Path $ProjectDir "candidate_eval.json"
    $CanaryReport = Join-Path $ProjectDir "canary_report.json"
    $ShadowReport = Join-Path $ProjectDir "shadow_report.json"
    $RolloutState = Join-Path $ProjectDir "rollout.state.json"
    $RolloutDecision = Join-Path $ProjectDir "rollout_decision.json"
    $RolloutApply = Join-Path $ProjectDir "rollout_apply.json"
    $AutopilotOk = Join-Path $ProjectDir "autopilot_ok.json"
    $AutopilotPending = Join-Path $ProjectDir "autopilot_pending.json"
    $AutopilotApproved = Join-Path $ProjectDir "autopilot_approved.json"
    $AutopilotPending2 = Join-Path $ProjectDir "autopilot_pending_2.json"
    $AutopilotExpired = Join-Path $ProjectDir "autopilot_expired.json"
    $AutopilotExpired2 = Join-Path $ProjectDir "autopilot_expired_deduped.json"
    $ApprovalState = Join-Path $ProjectDir "rollout.approvals.json"

    Run-FastAgent -Name "Eval baseline" -Args @("eval", "--config", $ConfigPath, "--judge", "--judge-seed", "42", "--output-json", $BaselineEval) | Out-Null
    Run-FastAgent -Name "Eval candidate" -Args @("eval", "--config", $ConfigPath, "--judge", "--judge-seed", "42", "--output-json", $CandidateEval) | Out-Null
    Run-FastAgent -Name "Canary check" -Args @("canary-check", "--baseline-report", $BaselineEval, "--candidate-report", $CandidateEval, "--output-json", $CanaryReport) | Out-Null
    Run-FastAgent -Name "Shadow check (simulate)" -Args @("canary-shadow", "--simulate", "--simulate-count", "20", "--simulate-degradation", "0.05", "--output-json", $ShadowReport) | Out-Null
    Run-FastAgent -Name "Rollout decision" -Args @("rollout-controller", "--state-file", $RolloutState, "--adaptive", "--canary-report", $CanaryReport, "--shadow-report", $ShadowReport, "--deployment-id", "demo-001", "--output-json", $RolloutDecision) | Out-Null
    Run-FastAgent -Name "Rollout apply (dry-run)" -Args @("rollout-apply", "--decision-report", $RolloutDecision, "--provider", "argo", "--resource", "demo-rollout", "--output-json", $RolloutApply) | Out-Null

    $ServerStdout = Join-Path $RunArtifacts "uvicorn_stdout.log"
    $ServerStderr = Join-Path $RunArtifacts "uvicorn_stderr.log"
    $ServerProcess = Start-Process -FilePath $PythonExe -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") -WorkingDirectory $ProjectDir -PassThru -RedirectStandardOutput $ServerStdout -RedirectStandardError $ServerStderr
    if (-not (Wait-ForApi -Url "http://127.0.0.1:8000/health")) {
        throw "API server did not become ready."
    }

    $Health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method Get -TimeoutSec 5
    Write-JsonFile -Object $Health -Path (Join-Path $RunArtifacts "health.json") -Depth 12

    $ChatPayload = @{ message = "Hola FastAgent E2E" } | ConvertTo-Json
    $Chat = Invoke-RestMethod -Uri "http://127.0.0.1:8000/chat" -Method Post -ContentType "application/json" -Body $ChatPayload -TimeoutSec 10
    Write-JsonFile -Object $Chat -Path (Join-Path $RunArtifacts "chat.json") -Depth 12

    Run-FastAgent -Name "Autopilot dry-run (no gate)" -Args @(
        "autopilot",
        "--baseline-report", $BaselineEval,
        "--candidate-report", $CandidateEval,
        "--shadow-mode", "simulate",
        "--simulate-count", "20",
        "--simulate-degradation", "0.0",
        "--apply-provider", "argo",
        "--apply-resource", "demo-rollout",
        "--webhook",
        "--webhook-mode", "dry-run",
        "--webhook-url", "https://example.com/deploy",
        "--webhook-secret", "demo-secret",
        "--webhook-environment", "staging",
        "--output-json", $AutopilotOk
    ) | Out-Null

    Run-FastAgent -Name "Autopilot approval pending" -ExpectedExitCodes @(5) -Args @(
        "autopilot",
        "--baseline-report", $BaselineEval,
        "--candidate-report", $CandidateEval,
        "--shadow-mode", "none",
        "--approval-gate",
        "--approval-state-file", $ApprovalState,
        "--webhook-environment", "prod",
        "--output-json", $AutopilotPending
    ) | Out-Null

    $PendingPayload = Get-Content $AutopilotPending -Raw | ConvertFrom-Json
    $RequestId = [string]$PendingPayload.approval.request_id
    if (-not $RequestId) {
        throw "Pending approval request_id not found."
    }

    Run-FastAgent -Name "Approval list" -Args @("approval-list", "--state-file", $ApprovalState) | Out-Null
    Run-FastAgent -Name "Approval resolve (approve)" -Args @("approval-resolve", "--state-file", $ApprovalState, "--request-id", $RequestId, "--decision", "approve", "--approver", "ops-lead") | Out-Null

    Run-FastAgent -Name "Autopilot with approved request" -Args @(
        "autopilot",
        "--baseline-report", $BaselineEval,
        "--candidate-report", $CandidateEval,
        "--shadow-mode", "none",
        "--approval-gate",
        "--approval-state-file", $ApprovalState,
        "--approval-request-id", $RequestId,
        "--webhook-environment", "prod",
        "--output-json", $AutopilotApproved
    ) | Out-Null

    Run-FastAgent -Name "Autopilot approval pending (for expiry test)" -ExpectedExitCodes @(5) -Args @(
        "autopilot",
        "--baseline-report", $BaselineEval,
        "--candidate-report", $CandidateEval,
        "--shadow-mode", "none",
        "--approval-gate",
        "--approval-state-file", $ApprovalState,
        "--webhook-environment", "prod",
        "--output-json", $AutopilotPending2
    ) | Out-Null

    $Pending2 = Get-Content $AutopilotPending2 -Raw | ConvertFrom-Json
    $RequestId2 = [string]$Pending2.approval.request_id
    if (-not $RequestId2) {
        throw "Second pending approval request_id not found."
    }

    $Approvals = Get-Content $ApprovalState -Raw | ConvertFrom-Json
    foreach ($item in $Approvals.requests) {
        if ([string]$item.id -eq $RequestId2) {
            $item.expires_at = "2000-01-01T00:00:00+00:00"
            $item.status = "pending"
            $item.last_escalated_at = ""
        }
    }
    Write-JsonFile -Object $Approvals -Path $ApprovalState -Depth 100

    $EscalationTargets = "https://hooks.slack.com/services/XXX/YYY/ZZZ,https://outlook.office.com/webhook/AAA/BBB"
    Run-FastAgent -Name "Autopilot expired + escalation dry-run" -ExpectedExitCodes @(7) -Args @(
        "autopilot",
        "--baseline-report", $BaselineEval,
        "--candidate-report", $CandidateEval,
        "--shadow-mode", "none",
        "--approval-gate",
        "--approval-state-file", $ApprovalState,
        "--approval-request-id", $RequestId2,
        "--approval-escalation-urls", $EscalationTargets,
        "--approval-escalation-mode", "dry-run",
        "--approval-escalation-dedupe",
        "--webhook-environment", "prod",
        "--output-json", $AutopilotExpired
    ) | Out-Null

    $Approvals2 = Get-Content $ApprovalState -Raw | ConvertFrom-Json
    foreach ($item in $Approvals2.requests) {
        if ([string]$item.id -eq $RequestId2) {
            $item.last_escalated_at = "2000-01-01T00:00:00+00:00"
        }
    }
    Write-JsonFile -Object $Approvals2 -Path $ApprovalState -Depth 100

    Run-FastAgent -Name "Autopilot expired + escalation dedupe check" -ExpectedExitCodes @(7) -Args @(
        "autopilot",
        "--baseline-report", $BaselineEval,
        "--candidate-report", $CandidateEval,
        "--shadow-mode", "none",
        "--approval-gate",
        "--approval-state-file", $ApprovalState,
        "--approval-request-id", $RequestId2,
        "--approval-escalation-urls", $EscalationTargets,
        "--approval-escalation-mode", "dry-run",
        "--approval-escalation-dedupe",
        "--webhook-environment", "prod",
        "--output-json", $AutopilotExpired2
    ) | Out-Null

    $GeneratedValidation = Join-Path $RunArtifacts "generated_artifacts_validation.json"
    Run-FastAgent -Name "Validate generated artifacts" -Args @(
        "validate-artifacts",
        "--artifact", "eval_report:$BaselineEval",
        "--artifact", "eval_report:$CandidateEval",
        "--artifact", "canary_report:$CanaryReport",
        "--artifact", "shadow_report:$ShadowReport",
        "--artifact", "rollout_decision:$RolloutDecision",
        "--artifact", "autopilot_report:$AutopilotOk",
        "--output-json", $GeneratedValidation
    ) | Out-Null

    $ProjectArtifactsDir = Join-Path $RunArtifacts "project"
    New-Item -ItemType Directory -Path $ProjectArtifactsDir -Force | Out-Null

    $Collected = @{
        baseline_eval = Copy-ArtifactFile -Source $BaselineEval -DestinationDir $ProjectArtifactsDir
        candidate_eval = Copy-ArtifactFile -Source $CandidateEval -DestinationDir $ProjectArtifactsDir
        canary_report = Copy-ArtifactFile -Source $CanaryReport -DestinationDir $ProjectArtifactsDir
        shadow_report = Copy-ArtifactFile -Source $ShadowReport -DestinationDir $ProjectArtifactsDir
        rollout_decision = Copy-ArtifactFile -Source $RolloutDecision -DestinationDir $ProjectArtifactsDir
        rollout_apply = Copy-ArtifactFile -Source $RolloutApply -DestinationDir $ProjectArtifactsDir
        autopilot_ok = Copy-ArtifactFile -Source $AutopilotOk -DestinationDir $ProjectArtifactsDir
        autopilot_pending = Copy-ArtifactFile -Source $AutopilotPending -DestinationDir $ProjectArtifactsDir
        autopilot_approved = Copy-ArtifactFile -Source $AutopilotApproved -DestinationDir $ProjectArtifactsDir
        autopilot_expired = Copy-ArtifactFile -Source $AutopilotExpired -DestinationDir $ProjectArtifactsDir
        autopilot_expired_deduped = Copy-ArtifactFile -Source $AutopilotExpired2 -DestinationDir $ProjectArtifactsDir
        approval_state = Copy-ArtifactFile -Source $ApprovalState -DestinationDir $ProjectArtifactsDir
    }

    $Summary = @{
        repo_root = $RepoRoot
        work_dir = $WorkDir
        project_dir = $ProjectDir
        artifacts_dir = $RunArtifacts
        files = @{
            release_ready = $releaseReport
            sample_validation = $sampleValidation
            baseline_eval = $Collected.baseline_eval
            candidate_eval = $Collected.candidate_eval
            canary_report = $Collected.canary_report
            shadow_report = $Collected.shadow_report
            rollout_decision = $Collected.rollout_decision
            rollout_apply = $Collected.rollout_apply
            autopilot_ok = $Collected.autopilot_ok
            autopilot_pending = $Collected.autopilot_pending
            autopilot_approved = $Collected.autopilot_approved
            autopilot_expired = $Collected.autopilot_expired
            autopilot_expired_deduped = $Collected.autopilot_expired_deduped
            generated_validation = $GeneratedValidation
            approval_state = $Collected.approval_state
        }
    }
    $SummaryPath = Join-Path $RunArtifacts "summary.json"
    Write-JsonFile -Object $Summary -Path $SummaryPath -Depth 12
    Write-Host "E2E completed successfully."
    Write-Host "Summary: $SummaryPath"
}
finally {
    if ($ServerProcess -and -not $ServerProcess.HasExited) {
        Stop-Process -Id $ServerProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($CleanupWorkDir) {
        if (Test-Path $WorkDir) {
            Remove-Item -Recurse -Force $WorkDir -ErrorAction SilentlyContinue
        }
    }
}
