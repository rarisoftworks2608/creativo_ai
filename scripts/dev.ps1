# Starts the whole development stack on Windows - each process in its own PowerShell window:
#   Django API, Celery worker, Celery beat, Vite frontend (+ the Redis container if Docker is running).
#
#   powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
#
# Stop everything by closing the windows (or Ctrl+C in each).
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$python = Join-Path $backend 'venv\Scripts\python.exe'
$celery = Join-Path $backend 'venv\Scripts\celery.exe'
$beatSchedule = Join-Path $env:TEMP 'creativo-celerybeat-schedule'

if (-not (Test-Path $python)) {
    Write-Host 'backend\venv not found - create it first (see README "Local setup").' -ForegroundColor Red
    exit 1
}

if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker info --format '{{.ServerVersion}}' *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Docker Desktop is not running - start it, then run: docker start creativo-redis' -ForegroundColor Yellow
    } else {
        $existing = docker ps -a --filter 'name=^creativo-redis$' --format '{{.Names}}'
        if ($existing) { docker start creativo-redis | Out-Null }
        else { docker run -d --name creativo-redis -p 6379:6379 redis:7-alpine | Out-Null }
        if ($LASTEXITCODE -eq 0) { Write-Host 'Redis container running on port 6379.' -ForegroundColor Green }
        else { Write-Host 'Could not start the Redis container - check Docker Desktop.' -ForegroundColor Yellow }
    }
} else {
    Write-Host 'Docker not found - make sure Redis is running on localhost:6379.' -ForegroundColor Yellow
}

function Start-Window($title, $workdir, $command) {
    Start-Process powershell -ArgumentList '-NoExit', '-Command', "`$host.UI.RawUI.WindowTitle='$title'; Set-Location '$workdir'; $command"
}

Start-Window 'Django API' $backend "& '$python' manage.py runserver"
Start-Window 'Celery worker' $backend "& '$celery' -A config worker -l info --pool=solo"
Start-Window 'Celery beat' $backend "& '$celery' -A config beat -l info -s '$beatSchedule'"
Start-Window 'Frontend' $frontend 'npm run dev'

Write-Host ''
Write-Host 'Started: API http://127.0.0.1:8000  |  App http://localhost:5173  |  API docs http://127.0.0.1:8000/api/docs/' -ForegroundColor Cyan
