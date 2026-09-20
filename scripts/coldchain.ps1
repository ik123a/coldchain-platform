$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$StateFile = Join-Path $Root ".run\coldchain.pids.json"
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$BackendPy = Join-Path $BackendDir ".venv\Scripts\python.exe"

function Get-State {
    if (Test-Path -LiteralPath $StateFile) {
        return Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
    }
    return [pscustomobject]@{ backend = $null; frontend = $null }
}

function Set-State($state) {
    $dir = Split-Path -Parent $StateFile
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
    $state | ConvertTo-Json | Set-Content -LiteralPath $StateFile -Encoding UTF8
}

function Test-PidAlive($procId) {
    if (-not $procId) { return $false }
    return [bool](Get-Process -Id $procId -ErrorAction SilentlyContinue)
}

function Get-PortPid($port) {
    $line = netstat -ano | Select-String ":$port\s.*LISTENING"
    if ($line) {
        $parts = ($line | Select-Object -First 1).ToString().Trim() -split '\s+'
        return [int]$parts[-1]
    }
    return $null
}

function Stop-Tracked([string]$name, $procId) {
    if ($procId) {
        $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($p) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            Write-Host "[$name] stopped pid $procId"
        } else {
            Write-Host "[$name] pid $procId not running"
        }
    }
    $port = if ($name -eq "backend") { 8000 } else { 3000 }
    $portPid = Get-PortPid $port
    if ($portPid) {
        Stop-Process -Id $portPid -Force -ErrorAction SilentlyContinue
        Write-Host "[$name] freed port $port (pid $portPid)"
    }
}

switch ($args[0]) {

    "start" {
        $state = Get-State

        if (Test-PidAlive $state.backend) {
            Write-Host "[backend] already running (pid $($state.backend))"
        } else {
            $p = Start-Process -FilePath $BackendPy `
                -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000" `
                -WorkingDirectory $BackendDir `
                -RedirectStandardOutput (Join-Path $Root ".run\backend.log") `
                -RedirectStandardError (Join-Path $Root ".run\backend.err.log") `
                -WindowStyle Hidden -PassThru
            $state.backend = $p.Id
            Write-Host "[backend] started pid $($p.Id) -> http://localhost:8000"
        }

        if (Test-PidAlive $state.frontend) {
            Write-Host "[frontend] already running (pid $($state.frontend))"
        } else {
            $npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
            if (-not $npm) { $npm = "npm.cmd" }
            $p = Start-Process -FilePath $npm `
                -ArgumentList "start" `
                -WorkingDirectory $FrontendDir `
                -RedirectStandardOutput (Join-Path $Root ".run\frontend.log") `
                -RedirectStandardError (Join-Path $Root ".run\frontend.err.log") `
                -WindowStyle Hidden -PassThru
            $state.frontend = $p.Id
            Write-Host "[frontend] started pid $($p.Id) -> http://localhost:3000"
        }

        Set-State $state
    }

    "stop" {
        $state = Get-State
        Stop-Tracked "backend" $state.backend
        Stop-Tracked "frontend" $state.frontend
        Set-State ([pscustomobject]@{ backend = $null; frontend = $null })
    }

    "status" {
        $state = Get-State
        foreach ($name in @("backend", "frontend")) {
            $port = if ($name -eq "backend") { 8000 } else { 3000 }
            $alive = Test-PidAlive $state.$name
            $portPid = Get-PortPid $port
            if ($alive -and $portPid) {
                Write-Host "[$name] RUNNING pid $($state.$name), port $port listening"
            } elseif ($portPid) {
                Write-Host "[$name] port $port listening (pid $portPid) but not tracked"
            } else {
                Write-Host "[$name] STOPPED"
            }
        }
    }

    default {
        Write-Host "usage: .\scripts\serve.ps1 {start|stop|status}"
        exit 1
    }
}
