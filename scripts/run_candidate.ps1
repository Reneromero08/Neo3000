param(
    [string]$Model = $env:NEO3000_MODEL,
    [int]$Port = 9393,
    [int]$Context = 4096,
    [int]$Threads = 12,
    [int]$ThreadsBatch = 12,
    [int]$Batch = 512,
    [int]$UBatch = 128,
    [int]$FitTargetMiB = 1024,
    [string]$CacheTypeK = "f16",
    [string]$CacheTypeV = "f16",
    [switch]$CpuMoe,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

if ([string]::IsNullOrWhiteSpace($Model)) {
    throw "Set NEO3000_MODEL or pass -Model with the exact Agents-A1 GGUF path"
}
if (-not (Test-Path $Model)) {
    throw "Model file not found: $Model"
}

$Server = Join-Path $Root "build/candidate/bin/Release/llama-server.exe"
if (-not (Test-Path $Server)) {
    throw "Candidate binary not found: $Server. Run scripts/build_candidate.ps1 first."
}

$arguments = @(
    "--model", $Model, "--alias", "agents-a1-candidate",
    "--host", "127.0.0.1", "--port", "$Port",
    "--ctx-size", "$Context",
    "--threads", "$Threads", "--threads-batch", "$ThreadsBatch",
    "--batch-size", "$Batch", "--ubatch-size", "$UBatch",
    "--gpu-layers", "auto", "--fit", "on", "--fit-target", "$FitTargetMiB",
    "--flash-attn", "auto",
    "--cache-type-k", $CacheTypeK, "--cache-type-v", $CacheTypeV,
    "--cache-prompt", "--metrics", "--no-webui", "--reasoning", "auto"
)

if ($CpuMoe) { $arguments += "--cpu-moe" }
if ($ExtraArgs) { $arguments += $ExtraArgs }

Write-Host "Candidate endpoint: http://127.0.0.1:$Port/v1"
Write-Host "Model: $Model"
Write-Host "> $Server $($arguments -join ' ')"

& $Server @arguments
exit $LASTEXITCODE
