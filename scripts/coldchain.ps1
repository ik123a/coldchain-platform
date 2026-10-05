<#
    ColdChain Rescue - one-click launcher.

    Double-click START.bat. Or from a terminal:

        .\scripts\coldchain.ps1 start          start both
        .\scripts\coldchain.ps1 stop           stop both
        .\scripts\coldchain.ps1 status         report what is running
        .\scripts\coldchain.ps1 restart
        .\scripts\coldchain.ps1 tunnel         start + public URL
        .\scripts\coldchain.ps1 logs           tail both logs
        .\scripts\coldchain.ps1 demo           one-click demo fleet

    Why this exists: the backend needs APP_ENV, an optional .env, and a
    venv interpreter, and the frontend needs a production build plus
    API_ORIGIN before `npm start` will serve anything. Getting any of that
    wrong produces a 404-ing blank UI rather than an error, so the steps are
    encoded here instead of being retyped.
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "status", "restart", "tunnel", "logs", "demo", "test", "help")]
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"

$Root       = Split-Path -Parent $PSScriptRoot
$RunDir     = Join-Path $Root ".run"
$StateFile  = Join-Path $RunDir "coldchain.pids.json"
$BackendDir = Join-Path $Root "backend"
$FrontendDir= Join-Path $Root "frontend"
$BackendPy  = Join-Path $BackendDir ".venv\Scripts\python.exe"
$EnvExample = Join-Path $BackendDir ".env.example"
$EnvFile    = Join-Path $BackendDir ".env"

# Cold world by default: nothing spawns, nothing moves, until the operator
# adds and starts trucks. FLEET_AUTOSTART=1 would boot a 12-truck demo fleet
# that the operator did not ask for.
$BackendEnv = @{
    APP_ENV               = "development"
    ESCALATE_AFTER_SIM_MIN = "6"
}

function Write-Section($text) {
    Write-Host ""
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host "  $(('-' * [Math]::Min($text.Length, 62)))" -ForegroundColor DarkGray
}

function Get-State {
    if (Test-Path -LiteralPath $StateFile) {
        try { return Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json }
        catch { }
    }
    return [pscustomobject]@{ backend = $null; frontend = $null; tunnel = $null }
}

function Set-State($state) {
    if (-not (Test-Path -LiteralPath $RunDir)) {
        New-Item -ItemType Directory -Path $RunDir -Force | Out-Null
    }
    $state | ConvertTo-Json | Set-Content -LiteralPath $StateFile -Encoding UTF8
}

function Test-PidAlive($procId) {
    if (-not $procId) { return $false }
    return [bool](Get-Process -Id $procId -ErrorAction SilentlyContinue)
}

function Get-PortPid($port) {
    $line = netstat -ano | Select-String ":$port\s.*LISTENING" | Select-Object -First 1
    if ($line) {
        $parts = $line.ToString().Trim() -split '\s+'
        $candidate = $parts[-1]
        if ($candidate -match '^\d+$') { return [int]$candidate }
    }
    return $null
}

function Test-PortOpen($port) {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $iar = $c.BeginConnect("127.0.0.1", $port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(600, $false)
        if ($ok) { try { $c.EndConnect($iar) } catch { return $false }; return $true }
        return $false
    } catch { return $false } finally { if ($c) { $c.Close() } }
}

function Stop-Tracked([string]$name, $procId, [int]$port) {
    if (Test-PidAlive $procId) {
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        Write-Host "  [$name] stopped pid $procId" -ForegroundColor DarkGray
    }
    $portPid = Get-PortPid $port
    if ($portPid -and $portPid -ne $procId) {
        Stop-Process -Id $portPid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 400
        Write-Host "  [$name] freed port $port (pid $portPid)" -ForegroundColor DarkGray
    }
}

function Get-LanIp {
    try {
        $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
              Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254*" -and $_.InterfaceAlias -notmatch "Loopback|vEthernet|WSL|VMware|VirtualBox" } |
              Sort-Object { if ($_.InterfaceAlias -match "Wi-Fi|Wireless") { 0 } else { 1 } } |
              Select-Object -First 1
        if ($ip) { return $ip.IPAddress }
    } catch { }
    return $null
}

function Assert-Prereqs {
    $problems = @()

    if (-not (Test-Path -LiteralPath $BackendPy)) {
        $problems += "backend venv missing - run: cd backend; python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir "package.json"))) {
        $problems += "frontend/package.json missing"
    }
    if (-not (Get-PortPid 8000) -and -not (Test-PortOpen 8000)) {
        # not an error, just noting first-run behaviour
    }

    if ($problems.Count) {
        Write-Section "Cannot start"
        $problems | ForEach-Object { Write-Host "  x $_" -ForegroundColor Red }
        exit 1
    }
}

function Start-Backend {
    $state = Get-State
    if (Test-PidAlive $state.backend) {
        Write-Host "  [backend] already running (pid $($state.backend))" -ForegroundColor DarkYellow
        return
    }
    if (Test-PortOpen 8000) {
        $portPid = Get-PortPid 8000
        $state.backend = $portPid
        Set-State $state
        Write-Host "  [backend] port 8000 already listening (pid $portPid) - reusing" -ForegroundColor DarkYellow
        return
    }

    if (-not (Test-Path -LiteralPath $EnvFile) -and (Test-Path -LiteralPath $EnvExample)) {
        Copy-Item -LiteralPath $EnvExample -Destination $EnvFile -Force
        Write-Host "  [backend] created .env from .env.example" -ForegroundColor DarkGray
    }

    # Set the env in this process; Start-Process inherits it. -Environment only
    # exists on PS7+, and an inline `if` as an argument is a parse error on 5.1.
    foreach ($kv in $BackendEnv.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($kv.Key, $kv.Value, "Process")
    }

    $bOut = Join-Path $RunDir "backend.log"
    $bErr = Join-Path $RunDir "backend.err.log"
    # Detach: cmd /c start creates a separate process group, so the launcher's
    # pipeline closes immediately. Without this, Start-Process with redirected
    # output blocks until the server exits and the launcher looks frozen.
    $p = Start-Detached $BackendPy @("-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000") $BackendDir $bOut $bErr

    $state.backend = $p
    Set-State $state
    if ($p) { Write-Host "  [backend] started pid $p  ->  http://localhost:8000" -ForegroundColor Green }
    else    { Write-Host "  [backend] starting, port not open yet - check .run\backend.err.log" -ForegroundColor Yellow }
}

function Start-Frontend {
    $state = Get-State

    if (Test-PidAlive $state.frontend) {
        Write-Host "  [frontend] already running (pid $($state.frontend))" -ForegroundColor DarkYellow
        return
    }
    if (Test-PortOpen 3000) {
        $portPid = Get-PortPid 3000
        $state.frontend = $portPid
        Set-State $state
        Write-Host "  [frontend] port 3000 already listening (pid $portPid) - reusing" -ForegroundColor DarkYellow
        return
    }

    # `npm start` serves an existing production build. With no build it exits
    # immediately and the UI 404s on /api, which looks like a dead app rather
    # than a missing build, so check before starting.
    $hasBuild = Test-Path -LiteralPath (Join-Path $FrontendDir ".next\BUILD_ID")
    if (-not $hasBuild) {
        Write-Host "  [frontend] no production build found - building (this takes ~30s)..." -ForegroundColor Yellow
        Push-Location $FrontendDir
        try {
            $null = & "node_modules\.bin\next.cmd" build 2>&1
            if ($LASTEXITCODE -ne 0) {
                Write-Host "  x build failed - see output above" -ForegroundColor Red
                Pop-Location
                return
            }
        } finally { Pop-Location }
        Write-Host "  [frontend] build complete" -ForegroundColor Green
    }

    [Environment]::SetEnvironmentVariable("API_ORIGIN", "http://127.0.0.1:8000", "Process")

    # Invoke next directly. `npm start` runs the package script, which is
    # already `next start -p 3000`; any extra args are appended as bare words
    # and next parses them as project directories, e.g.
    #   next start -p 3000 3000 0.0.0.0  -> "Invalid project directory: ...\3000"
    $nextBin = Join-Path $FrontendDir "node_modules\.bin\next.cmd"
    if (-not (Test-Path -LiteralPath $nextBin)) { $nextBin = "next.cmd" }

    $fOut = Join-Path $RunDir "frontend.log"
    $fErr = Join-Path $RunDir "frontend.err.log"
    $p = Start-Detached $nextBin @("start","-p","3000","--hostname","0.0.0.0") $FrontendDir $fOut $fErr

    $state.frontend = $p
    Set-State $state
    if ($p) { Write-Host "  [frontend] started pid $p  ->  http://localhost:3000" -ForegroundColor Green }
    else    { Write-Host "  [frontend] starting, port not open yet - check .run\frontend.err.log" -ForegroundColor Yellow }
}

function Start-Detached($exe, [string[]]$exeArgs, $workDir, $outLog, $errLog) {
    # Launch in its own process group with output going to files, then read
    # back the real listener PID from the port. Returns the pid that actually
    # owns the port, which is more useful than the cmd.exe wrapper's.
    if (-not (Test-Path -LiteralPath $RunDir)) {
        New-Item -ItemType Directory -Path $RunDir -Force | Out-Null
    }
    $inner = '"' + $exe + '" ' + ($exeArgs -join " ") +
             ' > "' + $outLog + '" 2> "' + $errLog + '"'
    Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/c", "start", "/b", "/min", "/d", "`"$workDir`"", "cmd.exe", "/c", $inner `
        -WindowStyle Hidden | Out-Null

    $deadline = (Get-Date).AddSeconds(25)
    while ((Get-Date) -lt $deadline) {
        $p = Get-PortPid $(if ($workDir -eq $BackendDir) { 8000 } else { 3000 })
        if ($p) { return $p }
        Start-Sleep -Milliseconds 400
    }
    return $null
}

function Wait-Ready($port, $label, $timeoutSec = 90) {
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortOpen $port) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Show-Status {
    $state = Get-State
    Write-Section "Status"
    foreach ($name in @("backend", "frontend")) {
        $port = if ($name -eq "backend") { 8000 } else { 3000 }
        $alive = Test-PidAlive $state.$name
        $open  = Test-PortOpen $port
        $pidTxt = if ($state.$name) { "pid $($state.$name)" } else { "untracked" }
        if ($alive -and $open) {
            Write-Host "  [$name] RUNNING  port $port  $pidTxt" -ForegroundColor Green
        } elseif ($open) {
            Write-Host "  [$name] port $port listening but pid not tracked" -ForegroundColor Yellow
        } else {
            Write-Host "  [$name] STOPPED" -ForegroundColor DarkGray
        }
    }
    $lan = Get-LanIp
    if ($lan) { Write-Host "  [lan] http://$lan`:3000" -ForegroundColor DarkGray }
}

function Show-Urls {
    Write-Section "Open this"
    Write-Host "  http://localhost:3000" -ForegroundColor White
    $lan = Get-LanIp
    if ($lan) {
        Write-Host "  http://$lan`:3000        (other devices on this wifi)" -ForegroundColor DarkGray
    }
    Write-Host "  http://localhost:3000/dashboard" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------- commands

switch ($Command) {

    "start" {
        Write-Section "ColdChain Rescue"
        Assert-Prereqs
        Start-Backend
        Start-Frontend

        $b = Wait-Ready 8000 "backend" 60
        $f = Wait-Ready 3000 "frontend" 120
        if (-not $b) { Write-Host "  x backend did not open port 8000 - check .run\backend.err.log" -ForegroundColor Red }
        if (-not $f) { Write-Host "  x frontend did not open port 3000 - check .run\frontend.err.log" -ForegroundColor Red }
        if ($b -and $f) {
            Show-Urls
            Write-Host ""
            Write-Host "  Cold world: no trucks until you add them. Simulation -> Add Truck." -ForegroundColor DarkGray
            Write-Host "  Stop everything:  .\scripts\coldchain.ps1 stop" -ForegroundColor DarkGray
        }
    }

    "stop" {
        $state = Get-State
        Stop-Tracked "backend"  $state.backend  8000
        Stop-Tracked "frontend" $state.frontend 3000
        Set-State ([pscustomobject]@{ backend = $null; frontend = $null; tunnel = $null })
        Write-Section "Stopped"
    }

    "status" { Show-Status }

    "restart" {
        & $PSCommandPath stop
        Start-Sleep -Seconds 1
        & $PSCommandPath start
    }

    "test" {
        Write-Section "Backend suites"
        Push-Location $BackendDir
        try {
            $suites = @("test_fleet_ops","test_fleet_ai","test_world_events","test_fleet_twin",
                        "test_scenario_analytics","test_scenarios_suite","test_escalation","test_lessons")
            $pass = 0; $fail = 0; $failed = @()
            foreach ($s in $suites) {
                # Several suites print progress to stderr. PowerShell wraps any
                # native stderr output in an ErrorRecord and treats it as a
                # terminating error under $ErrorActionPreference="Stop", which
                # aborted the whole loop after test_escalation even though the
                # suite was fine. Merge the streams and inspect the text.
                $ErrorActionPreference = "Continue"
                $out = (& $BackendPy "tests\$s.py" 2>&1 | Out-String)
                $ErrorActionPreference = "Stop"
                # `^OK$` alone never matches: unittest prints OK on its own line
                # but Out-String joins everything into one multiline string, and
                # PowerShell's ^/$ anchors are not multiline by default. That made
                # test_escalation and test_lessons report FAIL while both exited 0.
                # Match a bare OK/FAILED line, or any explicit pass wording.
                $isPass = ($out -match "(?m)^OK\s*$") -or
                          ($out -match "ALL PASS") -or
                          ($out -match "(?m)^passed\b") -or
                          (($LASTEXITCODE -eq 0) -and -not ($out -match "(?m)^FAILED"))
                if ($isPass) {
                    Write-Host "  PASS  $s" -ForegroundColor Green; $pass++
                } else {
                    Write-Host "  FAIL  $s" -ForegroundColor Red; $fail++; $failed += $s
                }
            }
            if ($failed.Count) {
                Write-Host ""
                Write-Host "  re-run one directly:" -ForegroundColor DarkGray
                Write-Host "    cd backend; APP_ENV=development PYTHONPATH=. .venv\Scripts\python tests\$($failed[0]).py" -ForegroundColor DarkGray
            }
            Write-Host ""
            Write-Host "  $pass passed, $fail failed" -ForegroundColor $(if ($fail) { "Red" } else { "Green" })
        } finally { Pop-Location }
    }

    "demo" {
        Write-Section "Demo fleet"
        $env:FLEET_AUTOSTART = "1"
        Write-Host "  Restarting backend with a populated demo fleet..." -ForegroundColor Yellow
        $state = Get-State
        Stop-Tracked "backend" $state.backend 8000
        Start-Sleep -Seconds 1
        [Environment]::SetEnvironmentVariable("APP_ENV", "development", "Process")
        [Environment]::SetEnvironmentVariable("FLEET_AUTOSTART", "1", "Process")
        [Environment]::SetEnvironmentVariable("ESCALATE_AFTER_SIM_MIN", "6", "Process")

        $p = Start-Detached $BackendPy @("-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000") `
                $BackendDir (Join-Path $RunDir "backend.log") (Join-Path $RunDir "backend.err.log")
        $state.backend = $p
        Set-State $state
        Write-Host "  [backend] restarted with demo fleet (pid $p)" -ForegroundColor Green
    }

    "tunnel" {
        Write-Section "Public tunnel"
        & $PSCommandPath start | Out-Null

        $cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
        if (-not $cf) {
            $candidate = Join-Path $Root "tools\cloudflared.exe"
            if (Test-Path -LiteralPath $candidate) { $cf = $candidate }
        }
        if (-not $cf) {
            Write-Host "  x cloudflared not found." -ForegroundColor Red
            Write-Host "    Install:  winget install --id Cloudflare.cloudflared" -ForegroundColor Yellow
            Write-Host "    Or drop the exe at:  tools\cloudflared.exe" -ForegroundColor Yellow
            exit 1
        }

        Write-Host "  starting tunnel to http://localhost:3000 ..." -ForegroundColor Yellow
        Write-Host "  your laptop must stay awake, or the URL dies." -ForegroundColor DarkGray
        Write-Host "  the URL is unauthenticated - anyone with it can drive the sim." -ForegroundColor DarkYellow
        Write-Host ""
        & $cf tunnel --url http://localhost:3000 --no-autoupdate
    }

    "logs" {
        Write-Section "Logs (Ctrl+C to exit)"
        Get-Content (Join-Path $RunDir "backend.log")  -Tail 20 -Wait -ErrorAction SilentlyContinue
    }

    "help" {
        Write-Section "ColdChain Rescue"
        Write-Host "  start     start backend + frontend"
        Write-Host "  stop      stop both"
        Write-Host "  status    what is running"
        Write-Host "  restart   stop then start"
        Write-Host "  demo      restart backend with a populated demo fleet"
        Write-Host "  test      run the 8 backend suites"
        Write-Host "  tunnel    start + public https URL (free, needs cloudflared)"
        Write-Host "  logs      tail backend log"
        Write-Host ""
        Write-Host "  Or just double-click START.bat" -ForegroundColor DarkGray
    }
}