"""ColdChain loop judge — the deterministic acceptance gate.

This is NOT written by the build agent's judgement. It exits 0 only when the
repo satisfies the goal AND every boundary. Boundaries exist so the loop cannot
"win" by deleting or weakening what it is graded on (failure mode #3).

Run:  python .loop/judge.py --json
Exit: 0 = releasable, 1 = not releasable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"

# --- Boundaries: the loop must NOT do these. Each is machine-checkable. ------
# B1: the verification assets themselves are immutable.
PROTECTED = [
    BACKEND / "tests" / "test_fleet_twin.py",
    BACKEND / "tests" / "test_fleet_ai.py",
    BACKEND / "tests" / "test_fleet_ops.py",
    BACKEND / "tests" / "test_world_events.py",
    BACKEND / "tests" / "test_scenario_analytics.py",
    BACKEND / "tests" / "acceptance_sweep.py",
    ROOT / ".loop" / "judge.py",
    ROOT / ".loop" / "baseline.json",
]
# B2: no credential material may be introduced into tracked files.
SECRET_RE = re.compile(
    r"(?i)\b(?:AIza[0-9A-Za-z_\-]{20,}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,})"
)
# B3: no live secrets in the .env that git tracks.
TRACKED_ENV = [ROOT / ".env", BACKEND / ".env", FRONTEND / ".env"]

ROUTES = [
    "/", "/dashboard", "/live-map", "/incidents", "/analytics", "/simulation",
    "/twin", "/copilot", "/reports", "/settings", "/shipments",
    "/shipments-live", "/world-events", "/fleet",
]
FRONTEND_URL = "http://localhost:3000"
BACKEND_URL = "http://127.0.0.1:8000"


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _run(cmd: list[str], cwd: pathlib.Path, timeout: int) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, shell=False,
        )
        return p.returncode, (p.stdout + p.stderr)[-4000:]
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s"
    except FileNotFoundError as e:
        return 127, str(e)


def check_boundaries() -> list[dict]:
    """Machine-checkable anti-Goodhart boundaries."""
    out: list[dict] = []

    # B1 - protected files unchanged vs recorded baseline
    base = json.loads((ROOT / ".loop" / "baseline.json").read_text())
    b1_hits = []
    for rel, want in base["protected_sha256"].items():
        p = ROOT / rel
        if not p.exists():
            b1_hits.append(f"MISSING protected file: {rel}")
            continue
        got = _sha(p)
        if got != want:
            b1_hits.append(f"PROTECTED FILE MODIFIED: {rel} ({want[:12]} -> {got[:12]})")
    out.append({
        "id": "B1", "ok": not b1_hits,
        "detail": f"{len(base['protected_sha256'])} protected files unchanged"
                  if not b1_hits else "; ".join(b1_hits),
    })

    # B2 - no credential-shaped strings in tracked files
    try:
        files = _run(
            ["git", "ls-files"], ROOT, 60
        )[1].splitlines()
    except Exception:
        files = []
    hits = []
    for rel in files:
        p = ROOT / rel
        if p.suffix not in {".py", ".ts", ".tsx", ".js", ".json", ".md", ".css", ".yaml", ".yml", ".env"}:
            continue
        if p.stat().st_size > 2_000_000:
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for m in SECRET_RE.finditer(txt):
            line = txt[: m.start()].count("\n") + 1
            hits.append(f"{rel}:{line}")
    out.append({
        "id": "B2",
        "ok": not hits,
        "detail": "no credential material in tracked files" if not hits
                  else f"SECRETS in tracked files: {hits[:5]}",
    })

    # B3 - .env must not be tracked
    tracked = set(files)
    leaked = [str(p.relative_to(ROOT)) for p in TRACKED_ENV
              if p.exists() and str(p.relative_to(ROOT)).replace("\\", "/") in tracked]
    out.append({
        "id": "B3", "ok": not leaked,
        "detail": "no .env tracked" if not leaked else f".env IS TRACKED: {leaked}",
    })

    return out


def check_typescript() -> dict:
    rc, out = _run([str(FRONTEND / "node_modules" / ".bin" / "tsc.cmd"), "--noEmit"],
                   FRONTEND, timeout=420)
    if rc == 127:  # fall back to the cmd shim via the shell
        rc, out = _run(["cmd", "/c", "npx tsc --noEmit"], FRONTEND, timeout=420)
    return {"id": "G1", "ok": rc == 0,
            "detail": "tsc --noEmit clean" if rc == 0 else out.strip()[:400]}


def check_backend_suites() -> dict:
    """Reconciliation: every standalone suite must independently exit 0."""
    py = BACKEND / ".venv" / "Scripts" / "python.exe"
    suites = [
        "test_fleet_twin.py", "test_fleet_ai.py", "test_fleet_ops.py",
        "test_world_events.py", "test_scenario_analytics.py",
    ]
    fails = []
    for s in suites:
        f = BACKEND / "tests" / s
        if not f.exists():
            fails.append(f"{s}: MISSING")
            continue
        rc, out = _run([str(py), f"tests/{s}"], BACKEND, timeout=180)
        if rc != 0:
            fails.append(f"{s}: exit {rc} — {out.strip()[-250:]}")
    return {"id": "G2", "ok": not fails,
            "detail": f"{len(suites)}/{len(suites)} suites pass" if not fails
                      else "; ".join(fails)}


def check_backend_live() -> dict:
    """The backend must actually serve, not just import."""
    try:
        with urllib.request.urlopen(f"{BACKEND_URL}/api/status", timeout=10) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        return {"id": "G3", "ok": False, "detail": f"/api/status unreachable: {e}"}
    ai = str(data.get("ai_mode", "")).upper()
    ok_sys = str(data.get("system", "")).upper() in {"OPERATIONAL", "DEGRADED"}
    ok_ai = ai == "DETERMINISTIC-AGENTS"   # must never claim an LLM
    return {"id": "G3", "ok": ok_sys and ok_ai,
            "detail": f"system={data.get('system')} ai_mode={data.get('ai_mode')} "
                      f"running={data.get('simulations_running')} "
                      f"orphaned={data.get('simulations_orphaned')} "
                      f"incidents_open={data.get('incidents_open')}"}


def check_routes() -> dict:
    """Reconciliation against the real rendered DOM, not a self-report."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"id": "G4", "ok": False, "detail": "playwright not installed"}

    bad, errs_seen = [], []
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        for r in ROUTES:
            errs: list[str] = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errs.append("PAGEERR: " + str(e)))
            try:
                resp = pg.goto(FRONTEND_URL + r, wait_until="domcontentloaded", timeout=90000)
                pg.wait_for_timeout(2500)
            except Exception as e:
                bad.append(f"{r}: navigation failed {e}")
                continue
            code = resp.status if resp else 0
            h1 = pg.evaluate("() => document.querySelectorAll('h1').length")
            real = [e for e in errs if "DevTools" not in e and "favicon" not in e]
            if code != 200:
                bad.append(f"{r}: HTTP {code}")
            if h1 != 1:
                bad.append(f"{r}: {h1} <h1> (want exactly 1)")
            if real:
                bad.append(f"{r}: {len(real)} console error(s) — {real[0][:90]}")
            errs_seen += real
        b.close()
    return {"id": "G4", "ok": not bad,
            "detail": f"{len(ROUTES)} routes: HTTP 200, exactly one <h1>, 0 console errors"
                      if not bad else "; ".join(bad[:6])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quick", action="store_true",
                    help="skip the Playwright route sweep (G4)")
    args = ap.parse_args()

    t0 = time.time()
    checks = [check_typescript(), check_backend_suites(), check_backend_live()]
    checks += check_boundaries()
    if not args.quick:
        checks.append(check_routes())

    goals = [c for c in checks if c["id"].startswith("G")]
    bounds = [c for c in checks if c["id"].startswith("B")]
    ok = all(c["ok"] for c in checks)

    report = {
        "releasable": ok,
        "elapsed_s": round(time.time() - t0, 1),
        "goals_passed": f"{sum(c['ok'] for c in goals)}/{len(goals)}",
        "boundaries_held": f"{sum(c['ok'] for c in bounds)}/{len(bounds)}",
        "checks": checks,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for c in checks:
            print(f"  [{'PASS' if c['ok'] else 'FAIL'}] {c['id']}: {c['detail'][:120]}")
        print(f"\n  GOALS {report['goals_passed']} | BOUNDARIES {report['boundaries_held']} "
              f"| {report['elapsed_s']}s")
        print(f"  RELEASABLE: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
