param(
    [string]$Python = "python",
    [string]$PytestArgs = "-q"
)

Write-Host "Running unit and integration tests..." -ForegroundColor Cyan
& $Python -m pytest $PytestArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "Tests failed." -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host "All tests passed." -ForegroundColor Green
