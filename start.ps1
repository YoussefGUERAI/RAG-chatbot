# start.ps1 - One-command setup and launch for the IR4LAB RAG Chatbot
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\start.ps1
#   powershell -ExecutionPolicy Bypass -File .\start.ps1 -SkipPull
#
param(
    [switch]$SkipPull
)

$ErrorActionPreference = "Continue"

function Write-Step { param($msg) Write-Host "" ; Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host "    [OK]  $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "    [!]   $msg" -ForegroundColor Yellow }
function Write-Err  { param($msg) Write-Host "    [ERR] $msg" -ForegroundColor Red }
function Write-Info { param($msg) Write-Host "          $msg" -ForegroundColor Gray }

# Banner
Write-Host ""
Write-Host "  +--------------------------------------+" -ForegroundColor Blue
Write-Host "  |  IR4LAB RAG Chatbot - Quick Start   |" -ForegroundColor Blue
Write-Host "  +--------------------------------------+" -ForegroundColor Blue
Write-Host ""

# ----- 1. Check prerequisites -----------------------------------------------
Write-Step "Checking prerequisites"

$python = $null
foreach ($cmd in @("python", "python3")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $ver = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $python = $cmd
            Write-Ok "$ver  (using: $cmd)"
            break
        }
    }
}
if (-not $python) {
    Write-Err "Python not found. Install from https://python.org"
    exit 1
}

if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
    Write-Err "Docker not found. Install Docker Desktop from https://docker.com"
    exit 1
}
docker info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Docker is installed but not running. Start Docker Desktop first."
    exit 1
}
Write-Ok "Docker is running"

if (-not (Get-Command "ollama" -ErrorAction SilentlyContinue)) {
    Write-Err "Ollama not found. Install from https://ollama.com"
    exit 1
}
Write-Ok "Ollama found"

# ----- 2. .env setup ---------------------------------------------------------
Write-Step "Setting up environment"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Ok ".env created from .env.example"
} else {
    Write-Ok ".env already exists - keeping it"
}

# ----- 3. Python dependencies ------------------------------------------------
Write-Step "Installing Python dependencies"

& $python -m pip install -r requirements.txt --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) {
    Write-Err "pip install failed. Check requirements.txt."
    exit 1
}
Write-Ok "All packages installed"

# ----- 4. MongoDB via Docker Compose -----------------------------------------
Write-Step "Starting MongoDB (Docker Compose)"

docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Err "docker compose failed. Check docker-compose.yml."
    exit 1
}

Write-Info "Waiting for MongoDB to be ready..."
$mongoReady = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 1
    $check = docker exec rag-mongo mongosh --eval "db.runCommand({ping:1})" --quiet 2>&1
    if ($check -match '"ok"') {
        $mongoReady = $true
        break
    }
}
if ($mongoReady) {
    Write-Ok "MongoDB ready on port 27017"
    Write-Ok "Mongo Express on http://localhost:8081"
} else {
    Write-Warn "MongoDB slow to start - it may still be coming up."
}

# ----- 5. Ollama models ------------------------------------------------------
Write-Step "Checking Ollama models"

if ($SkipPull) {
    Write-Warn "-SkipPull flag set - skipping model download."
} else {
    $ollamaRunning = $false
    try {
        Invoke-WebRequest -Uri "http://localhost:11434" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop | Out-Null
        $ollamaRunning = $true
    } catch {
        $ollamaRunning = $false
    }

    if (-not $ollamaRunning) {
        Write-Info "Starting Ollama in the background..."
        Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 3
    }

    foreach ($model in @("nomic-embed-text", "mistral:7b")) {
        Write-Info "Pulling $model ..."
        ollama pull $model
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "$model ready"
        } else {
            Write-Warn "Could not pull $model - API may fail without it."
        }
    }
}

# ----- 6. FastAPI server -----------------------------------------------------
Write-Step "Starting FastAPI server"

$apiArgs = "-m uvicorn api.main:app --reload --port 8000"
$apiProcess = Start-Process -FilePath $python -ArgumentList $apiArgs -PassThru -WindowStyle Minimized

Write-Info "Waiting for API at http://localhost:8000/health ..."
$apiReady = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) {
            $apiReady = $true
            break
        }
    } catch {
        # still starting
    }
}
if ($apiReady) {
    Write-Ok "API running at http://localhost:8000"
    Write-Ok "Swagger docs at http://localhost:8000/docs"
} else {
    Write-Warn "API did not respond in time - check the minimized window for errors."
}

# ----- 7. Serve UI -----------------------------------------------------------
Write-Step "Serving UI"

$uiArgs = "-m http.server 3000"
$uiProcess = Start-Process -FilePath $python -ArgumentList $uiArgs -PassThru -WindowStyle Minimized

Start-Sleep -Seconds 1
Write-Ok "UI available at http://localhost:3000"

# ----- 8. Open browser -------------------------------------------------------
Start-Process "http://localhost:3000"

# Summary
Write-Host ""
Write-Host "  +--------------------------------------+" -ForegroundColor Green
Write-Host "  |      All services are running!      |" -ForegroundColor Green
Write-Host "  +--------------------------------------+" -ForegroundColor Green
Write-Host "  |  UI          http://localhost:3000  |" -ForegroundColor White
Write-Host "  |  API         http://localhost:8000  |" -ForegroundColor White
Write-Host "  |  API docs    http://localhost:8000/docs  |" -ForegroundColor White
Write-Host "  |  Mongo UI    http://localhost:8081  |" -ForegroundColor White
Write-Host "  +--------------------------------------+" -ForegroundColor Green
Write-Host ""
Write-Host "  Ingest a PDF (in another terminal):" -ForegroundColor White
Write-Host "    python pipeline.py --file path\to\doc.pdf" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Press Ctrl+C to stop all services." -ForegroundColor Gray
Write-Host ""

# Keep alive and clean up on Ctrl+C
try {
    while ($true) {
        Start-Sleep -Seconds 30
    }
} finally {
    Write-Host ""
    Write-Host "Shutting down..." -ForegroundColor Yellow

    if ($null -ne $apiProcess -and -not $apiProcess.HasExited) {
        Stop-Process -Id $apiProcess.Id -Force -ErrorAction SilentlyContinue
        Write-Info "API stopped."
    }
    if ($null -ne $uiProcess -and -not $uiProcess.HasExited) {
        Stop-Process -Id $uiProcess.Id -Force -ErrorAction SilentlyContinue
        Write-Info "UI server stopped."
    }

    docker compose stop 2>&1 | Out-Null
    Write-Info "MongoDB stopped."
    Write-Host "Done." -ForegroundColor Cyan
}
