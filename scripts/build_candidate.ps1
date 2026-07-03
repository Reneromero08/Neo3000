param(
    [string]$CudaArchitectures = "86",
    [string]$CudaToolkitRoot = $env:CUDAToolkit_ROOT,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BuildDir = Join-Path $Root "build/candidate"

if (-not (Test-Path (Join-Path $Root "CMakeLists.txt"))) {
    throw "Imported runtime source is missing. Run: python scripts/import_upstream.py"
}

if ($Clean -and (Test-Path $BuildDir)) {
    Remove-Item -Recurse -Force $BuildDir
}

$candidates = @()
if (-not [string]::IsNullOrWhiteSpace($CudaToolkitRoot)) { $candidates += $CudaToolkitRoot }
if (-not [string]::IsNullOrWhiteSpace($env:CUDA_PATH)) { $candidates += $env:CUDA_PATH }
if (-not [string]::IsNullOrWhiteSpace($env:CUDA_HOME)) { $candidates += $env:CUDA_HOME }
$base = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA"
if (Test-Path $base) {
    $candidates += Get-ChildItem $base -Directory | Sort-Object Name -Descending | ForEach-Object { $_.FullName }
}

$CudaRoot = $null
foreach ($c in $candidates) {
    if ([string]::IsNullOrWhiteSpace($c)) { continue }
    $nvcc = Join-Path $c "bin/nvcc.exe"
    if (Test-Path $nvcc) { $CudaRoot = (Resolve-Path $c).Path; break }
}
if (-not $CudaRoot) {
    $pathNvcc = Get-Command nvcc.exe -ErrorAction SilentlyContinue
    if ($pathNvcc) { $CudaRoot = (Resolve-Path (Join-Path $pathNvcc.Source "../..")).Path }
}
if (-not $CudaRoot) { throw "CUDA Toolkit not found" }

$configure = @(
    "-S", $Root, "-B", $BuildDir,
    "-DLLAMA_BUILD_TESTS=OFF", "-DLLAMA_BUILD_EXAMPLES=OFF",
    "-DLLAMA_BUILD_TOOLS=ON", "-DLLAMA_BUILD_SERVER=ON",
    "-DLLAMA_BUILD_APP=OFF", "-DLLAMA_BUILD_UI=OFF",
    "-DLLAMA_USE_PREBUILT_UI=OFF", "-DLLAMA_OPENSSL=OFF",
    "-DLLAMA_TOOLS_INSTALL=OFF",
    "-DGGML_CUDA=ON",
    "-DCMAKE_CUDA_ARCHITECTURES=$CudaArchitectures",
    "-DCUDAToolkit_ROOT=$CudaRoot"
)

Write-Host "CUDA Toolkit: $CudaRoot"
Write-Host "> cmake $($configure -join ' ')"
& cmake @configure
if ($LASTEXITCODE -ne 0) { throw "CMake configure failed" }

$build = @("--build", $BuildDir, "--config", "Release", "--target", "llama-server", "--parallel")
Write-Host "> cmake $($build -join ' ')"
& cmake @build
if ($LASTEXITCODE -ne 0) { throw "Build failed" }

Write-Host "Candidate build complete: $BuildDir"
