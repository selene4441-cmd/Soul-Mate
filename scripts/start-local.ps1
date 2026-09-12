$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    python -m venv .venv
}
$Python = Join-Path $Root ".venv\Scripts\python.exe"
& $Python -m pip install -r requirements.txt

if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
    corepack enable
    corepack prepare pnpm@11.19.0 --activate
}

if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
}

& $Python -m alembic upgrade head
pnpm install --frozen-lockfile

$env:PYTHONPATH = Join-Path $Root "services\backend"

$Backend = Start-Process `
    -FilePath $Python `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -PassThru
try {
    Write-Host "同频 API: http://127.0.0.1:8000/docs"
    Write-Host "同频 Web: http://127.0.0.1:3000"
    pnpm --filter tongpin-web dev --hostname 0.0.0.0 --port 3000
}
finally {
    Stop-Process -Id $Backend.Id -Force -ErrorAction SilentlyContinue
}