<#
  SoulMate Demo 一键启动
  ---------------------
  做四件事：迁移数据库 → 灌演示数据 → 起后端(FastAPI) → 起前端(Next.js)
  然后打开浏览器。Ctrl+C 会同时结束后端。

  端口：前端固定 3000；后端默认从 8010 起自动挑一个空闲端口
  （8000 经常被别的服务占用，脚本不会去动别人的进程）。

  用法：
      cd <repo>\soulmate\demo
      .\start.ps1
#>

$ErrorActionPreference = 'Stop'

$demoDir = $PSScriptRoot
$soulmateDir = Split-Path $demoDir -Parent
$webDir = Join-Path $soulmateDir 'web'
$logDir = Join-Path $demoDir 'logs'
$frontendUrl = 'http://127.0.0.1:3000'

function Step([string]$title) {
    Write-Host ''
    Write-Host "=== $title ===" -ForegroundColor Cyan
}

function Get-BusyPorts {
    $busy = @{}
    foreach ($line in (netstat -ano)) {
        if ($line -match '^\s*TCP\s+\S+:(\d+)\s+\S+\s+LISTENING') {
            $busy[[int]$Matches[1]] = $true
        }
    }
    return $busy
}

function Find-FreePort([int]$from = 8010, [int]$to = 8019) {
    $busy = Get-BusyPorts
    for ($port = $from; $port -le $to; $port++) {
        if (-not $busy.ContainsKey($port)) { return $port }
    }
    throw "在 $from-$to 之间找不到空闲端口，请手动释放一个端口后重试。"
}

function Get-HealthJson([string]$baseUrl) {
    try {
        return (Invoke-WebRequest -UseBasicParsing "$baseUrl/health" -TimeoutSec 2).Content
    } catch {
        return $null
    }
}

function Test-OurBackendUp([string]$baseUrl) {
    $content = Get-HealthJson $baseUrl
    if (-not $content) { return $false }
    # 我们的 /health 只返回 {"status":"ok"}；别人的实现可能多带 service 等字段
    try {
        $parsed = $content | ConvertFrom-Json
        $names = @($parsed.PSObject.Properties.Name)
        return ($names -contains 'status') -and ($names -notcontains 'service')
    } catch {
        return $false
    }
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Step '检查依赖'
foreach ($cmd in @('python', 'node', 'npm')) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "找不到命令 $cmd，请先安装后重试。"
    }
}
Write-Host '  python / node / npm 都在'

Step '准备数据库（迁移 + 演示数据）'
Push-Location $soulmateDir
try {
    python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'alembic upgrade head 失败' }
    python -m scripts.seed_demo
    if ($LASTEXITCODE -ne 0) { throw 'seed_demo 失败' }
} finally {
    Pop-Location
}

Step '选择后端端口并写入前端环境变量'
$backendPort = $null
$backend = $null

if (Test-OurBackendUp 'http://127.0.0.1:8000') {
    $backendPort = 8000
    Write-Host '  8000 上已经有我们的后端在跑，直接复用'
} else {
    $backendPort = Find-FreePort
    Write-Host "  后端将使用端口 $backendPort"
}

$backendOrigin = "http://127.0.0.1:$backendPort"
$envPath = Join-Path $webDir '.env.local'
@(
    '# 由 demo/start.ps1 自动生成'
    "API_BASE_URL=$backendOrigin"
    'NEXT_PUBLIC_API_BASE=/api/proxy/v1'
    "NEXT_PUBLIC_BACKEND_ORIGIN=$backendOrigin"
) | Set-Content -Path $envPath -Encoding UTF8
Write-Host "  已写入 $envPath"

if ($backendPort -ne 8000) {
    Step "启动后端 $backendOrigin"
    $backend = Start-Process -FilePath 'python' `
        -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$backendPort") `
        -WorkingDirectory $soulmateDir -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDir 'backend.out.log') `
        -RedirectStandardError (Join-Path $logDir 'backend.err.log')

    $healthy = $false
    for ($i = 0; $i -lt 60; $i++) {
        if (Test-OurBackendUp $backendOrigin) { $healthy = $true; break }
        Start-Sleep -Milliseconds 500
    }
    if ($healthy) {
        Write-Host '  后端已就绪'
    } else {
        Write-Warning "后端没有在 30 秒内就绪，请看 $logDir\backend.err.log"
    }
}

Step '准备前端依赖'
Push-Location $webDir
try {
    if (-not (Test-Path (Join-Path $webDir 'node_modules'))) {
        Write-Host '  首次运行，安装依赖（可能要几分钟）…'
        npm install
        if ($LASTEXITCODE -ne 0) { throw 'npm install 失败' }
    } else {
        Write-Host '  依赖已存在，跳过安装'
    }
} finally {
    Pop-Location
}

Step "启动前端 $frontendUrl"
Write-Host '  浏览器会稍后自动打开；也可以手动访问上面的地址'
Write-Host '  ⚠️ 请用 127.0.0.1 打开，不要用 localhost —— cookie 落在哪个主机，WebSocket 就得连哪个主机'
Write-Host '  演示账号密码统一为 password123（首页有一键切换按钮）'
Write-Host '  按 Ctrl+C 结束后端与前端' -ForegroundColor Yellow

$openJob = Start-Job -ScriptBlock {
    param($url)
    Start-Sleep -Seconds 12
    Start-Process $url
} -ArgumentList $frontendUrl

Push-Location $webDir
try {
    npm run dev
} finally {
    Pop-Location
    if ($openJob) {
        Stop-Job $openJob -ErrorAction SilentlyContinue
        Remove-Job $openJob -Force -ErrorAction SilentlyContinue
    }
    if ($backend -and -not $backend.HasExited) {
        Write-Host '正在结束后端…' -ForegroundColor Yellow
        Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    }
}
