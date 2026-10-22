param([switch]$LiveWeb)

$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    & uv sync --group dev
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
    & uv run playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw 'Chromium installation failed' }
    $testArguments = @('e2e', '--browser', 'chromium', '--tracing', 'on', '--video', 'on',
        '--screenshot', 'on', '--output', 'test-results/e2e',
        '--junitxml', 'artifacts/e2e/results.xml', '-q')
    if (-not $LiveWeb) { $testArguments += @('-m', 'not live') }
    & uv run pytest @testArguments
    $testExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $testExitCode
