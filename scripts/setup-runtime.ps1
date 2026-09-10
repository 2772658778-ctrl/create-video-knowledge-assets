param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$CacheRoot,
    [string]$TempRoot
)

if (-not $CacheRoot) {
    $CacheRoot = Join-Path $RepoRoot ".cache"
}
if (-not $TempRoot) {
    $TempRoot = Join-Path $RepoRoot ".tmp"
}

$paths = @(
    $CacheRoot,
    (Join-Path $CacheRoot "whisper"),
    (Join-Path $CacheRoot "hf"),
    (Join-Path $CacheRoot "hf\transformers"),
    (Join-Path $CacheRoot "torch"),
    (Join-Path $CacheRoot "yt-dlp"),
    $TempRoot
)

foreach ($path in $paths) {
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

$env:XDG_CACHE_HOME = $CacheRoot
$env:HF_HOME = (Join-Path $CacheRoot "hf")
$env:TRANSFORMERS_CACHE = (Join-Path $CacheRoot "hf\transformers")
$env:TORCH_HOME = (Join-Path $CacheRoot "torch")
$env:VKA_YTDLP_CACHE_DIR = (Join-Path $CacheRoot "yt-dlp")
$env:TEMP = $TempRoot
$env:TMP = $TempRoot
$env:TMPDIR = $TempRoot

Write-Host "Runtime prepared."
Write-Host "RepoRoot: $RepoRoot"
Write-Host "CacheRoot: $CacheRoot"
Write-Host "TempRoot: $TempRoot"
