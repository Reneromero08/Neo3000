param(
    [ValidateSet("stable", "candidate")]
    [string]$Variant = "stable",
    [string]$CudaArchitectures = "86",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BuildDir = Join-Path $Root "build/$Variant"

if (-not (Test-Path (Join-Path $Root "CMakeLists.txt"))) {
    throw "Imported runtime source is missing. Run: python scripts/import_upstream.py"
}

if ($Clean -and (Test-Path $BuildDir)) {
    Remove-Item -Recurse -Force $BuildDir
}

$configure = @(
    "-S", $Root,
    "-B", $BuildDir,
    "-DGGML_CUDA=ON",
    "-DCMAKE_CUDA_ARCHITECTURES=$CudaArchitectures",
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

Write-Host "Neo3000 $Variant CUDA build complete: $BuildDir"
