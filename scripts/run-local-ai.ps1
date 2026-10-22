$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot "data/local-ai"
$server = Get-ChildItem -LiteralPath (Join-Path $runtimeRoot "llama-b11796") -Filter "llama-server.exe" -Recurse | Select-Object -First 1
if (-not $server) { throw "Local AI runtime is missing." }
$model = Join-Path $runtimeRoot "Qwen3-4B-Q4_K_M.gguf"
$keyFile = Join-Path $runtimeRoot "api-key.txt"
if (-not (Test-Path -LiteralPath $model)) { throw "Local model is missing." }
if (-not (Test-Path -LiteralPath $keyFile)) { throw "Local API key is missing." }
& $server.FullName -m $model --alias "duckmmo-qwen3-4b" --host "127.0.0.1" --port 8081 --ctx-size 16384 --parallel 1 --threads 8 --n-gpu-layers 99 --cache-type-k q8_0 --cache-type-v q8_0 --flash-attn on --reasoning off --api-key-file $keyFile
exit $LASTEXITCODE
