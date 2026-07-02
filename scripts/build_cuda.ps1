param(
    [ValidateSet("stable", "candidate")]
    [string]$Variant = "stable",
    [string]$CudaArchitectures = "86",
    [string]$CudaToolkitRoot = $env:CUDAToolkit_ROOT,
    [switch]$CpuOnly,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BuildDir = Join-Path $Root "build/$Variant"

function Find-CudaToolkitRoot {
    param([string]$ExplicitRoot)

    $candidates = @()
    if (-not [string]::IsNullOrWhiteSpace($ExplicitRoot)) {
        $candidates += $ExplicitRoot
    }
    if (-not [string]::IsNullOrWhiteSpace($env:CUDA_PATH)) {
        $candidates += $env:CUDA_PATH
    }
    if (-not [string]::IsNullOrWhiteSpace($env:CUDA_HOME)) {
        $candidates += $env:CUDA_HOME
    }

    $base = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA"
    if (Test-Path $base) {
        $candidates += Get-ChildItem $base -Directory |
            Sort-Object Name -Descending |
            ForEach-Object { $_.FullName }
    }

    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }
        $nvcc = Join-Path $candidate "bin/nvcc.exe"
        if (Test-Path $nvcc) {
            return (Resolve-Path $candidate).Path
        }
    }

    $pathNvcc = Get-Command nvcc.exe -ErrorAction SilentlyContinue
    if ($pathNvcc) {
        return (Resolve-Path (Join-Path $pathNvcc.Source "../..")).Path
    }

    return $null
}

if (-not (Test-Path (Join-Path $Root "CMakeLists.txt"))) {
    throw "Imported runtime source is missing. Run: python scripts/import_upstream.py"
}

if ($Clean -and (Test-Path $BuildDir)) {
    Remove-Item -Recurse -Force $BuildDir
}

$CudaRoot = Find-CudaToolkitRoot -ExplicitRoot $CudaToolkitRoot
$EnableCuda = -not $CpuOnly

if ($EnableCuda -and -not $CudaRoot) {
    throw @"
CUDA Toolkit not found. The NVIDIA driver is not enough; Neo3000 needs nvcc from the CUDA Toolkit to build GGML_CUDA.

Fix options:
  1. Install the NVIDIA CUDA Toolkit, then reopen PowerShell.
  2. Or pass the toolkit root explicitly:
       powershell -ExecutionPolicy Bypass -File scripts/build_cuda.ps1 -CudaToolkitRoot "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\vXX.X"
  3. Or build a CPU-only baseline for smoke testing:
       powershell -ExecutionPolicy Bypass -File scripts/build_cuda.ps1 -CpuOnly

Expected file:
  C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\vXX.X\bin\nvcc.exe
"@
}

$configure = @(
    "-S", $Root,
    "-B", $BuildDir,
    "-DLLAMA_BUILD_TESTS=OFF",
    "-DLLAMA_BUILD_EXAMPLES=OFF",
    "-DLLAMA_BUILD_TOOLS=ON",
    "-DLLAMA_BUILD_SERVER=ON",
    "-DLLAMA_BUILD_APP=OFF",
    "-DLLAMA_BUILD_UI=OFF",
    "-DLLAMA_USE_PREBUILT_UI=OFF",
    "-DLLAMA_OPENSSL=OFF",
    "-DLLAMA_TOOLS_INSTALL=OFF"
)

if ($EnableCuda) {
    $configure += @(
        "-DGGML_CUDA=ON",
        "-DCMAKE_CUDA_ARCHITECTURES=$CudaArchitectures",
        "-DCUDAToolkit_ROOT=$CudaRoot"
    )
    Write-Host "CUDA Toolkit: $CudaRoot"
} else {
    $configure += "-DGGML_CUDA=OFF"
    Write-Host "CPU-only build requested. This is for smoke testing, not the Neo3000 performance baseline."
}

Write-Host "> cmake $($configure -join ' ')"
& cmake @configure
if ($LASTEXITCODE -ne 0) {
    throw "CMake configuration failed with exit code $LASTEXITCODE"
}

$build = @(
    "--build", $BuildDir,
    "--config", "Release",
    "--target", "llama-server", "llama-bench",
    "--parallel"
)

Write-Host "> cmake $($build -join ' ')"
& cmake @build
if ($LASTEXITCODE -ne 0) {
    throw "Build failed with exit code $LASTEXITCODE"
}

$Mode = if ($EnableCuda) { "CUDA" } else { "CPU-only" }
Write-Host "Neo3000 $Variant $Mode build complete: $BuildDir"
