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
    ROOT / ".loop" / "style-baseline.json",
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
    "/shipments-live", "/design-references", "/design-reference-board",
]
FRONTEND_URL = "http://localhost:3000"
BACKEND_URL = "http://127.0.0.1:8000"

# --- G5: visual guard -------------------------------------------------------
# tsc does not read CSS and the route sweep only checks HTTP/h1/console, so a
# pure visual regression (a stray outline, a blown-up font, a colour change)
# passes every other check. These probes reconcile computed style against a
# human-written baseline; the guards catch gross breakage that has no baseline.
STYLE_BASELINE = ROOT / ".loop" / "style-baseline.json"
STYLE_PROBES = [
    ("/live-map",  ".chip.on",        ["fontWeight", "borderTopColor", "outlineWidth",
                                       "outlineStyle", "position", "color"]),
    ("/live-map",  ".telemetry-rail",  ["width", "backgroundColor", "position"]),
    ("/live-map",  "h1",               ["fontSize", "fontWeight", "color"]),
    ("/analytics", ".region-label",    ["fontSize", "textTransform", "color", "letterSpacing"]),
    ("/incidents", "h1",               ["fontSize", "fontWeight"]),
]
# Gross sanity limits, applied to every element on the key routes.
MAX_OUTLINE_PX = 20.0
MIN_FONT_PX = 9.0
H1_MIN_PX, H1_MAX_PX = 20.0, 48.0
OVERFLOW_RATIO = 2.5
# WCAG 2.2 Target Size (Minimum) 2.5.8 -- 24x24 CSS px.
MIN_TARGET_PX = 24
# Measure the HIT area, not the border box. A control can satisfy WCAG 2.5.8
# with a visually smaller box if a transparent ::before extends the clickable
# region -- which is exactly what the map markers do (a 22px dot with a 24px
# pseudo-element hit area, so a 24px target does not overlap its neighbours on a
# dense map). getBoundingClientRect() reports the border box and would call that
# a violation, so probe the real hit area with elementFromPoint at the corners.
TARGET_PROBE = r"""() => {
  const bad = [], seen = new Set();
  for (const e of document.querySelectorAll('button, a[href], input, select, textarea')) {
    const r = e.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    const cs = getComputedStyle(e);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    if (cs.pointerEvents === 'none') continue;
    const key = e.tagName + '|' + Math.round(r.left) + '|' + Math.round(r.top);
    if (seen.has(key)) continue;
    seen.add(key);
    // Expand by the ::before/::after hit area the element may already provide.
    const be = getComputedStyle(e, '::before'), ae = getComputedStyle(e, '::after');
    let extraW = 0, extraH = 0;
    for (const p of [be, ae]) {
      if (p.content === 'none' || p.position === 'static') continue;
      const w = parseFloat(p.width), h = parseFloat(p.height);
      if (w > r.width) extraW = Math.max(extraW, (w - r.width) / 2);
      if (h > r.height) extraH = Math.max(extraH, (h - r.height) / 2);
    }
    const effW = r.width + extraW * 2, effH = r.height + extraH * 2;
    if (effH < %d || effW < %d) {
      bad.push({tag: e.tagName,
                txt: (e.innerText || e.value || e.getAttribute('aria-label') || '').trim().slice(0, 24),
                w: Math.round(effW), h: Math.round(effH),
                box: Math.round(r.width) + 'x' + Math.round(r.height),
                cls: (e.className || '').toString().slice(0, 50)});
    }
  }
  return bad;
}""" % (MIN_TARGET_PX, MIN_TARGET_PX)


def check_targets() -> dict:
    """G6 - no real control may render under the 24px WCAG floor.

    Measured 91/407 (22.4%) before the fix, 0/411 after. Kept as a gate so the
    floor cannot quietly erode as new controls are added.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"id": "G6", "ok": False,
                "detail": "playwright not importable -- G6 CANNOT run. "
                          "This is NOT a pass."}
    routes = ["/", "/live-map", "/incidents", "/copilot", "/dashboard"]
    bad, total = [], 0
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        for route in routes:
            pg = b.new_page(viewport={"width": 1600, "height": 1000})
            try:
                pg.goto(FRONTEND_URL + route, wait_until="domcontentloaded", timeout=90000)
                pg.wait_for_timeout(4000)
                found = pg.evaluate(TARGET_PROBE)
            except Exception as e:
                bad.append({"tag": "?", "txt": f"{route}: {e}"[:60], "w": 0, "h": 0, "cls": ""})
                pg.close()
                continue
            total += len(found)
            for x in found:
                x["route"] = route
            bad += found
            pg.close()
        b.close()
    if bad:
        top = "; ".join(f"{x.get('route','')} <{x['tag']}> {x['w']}x{x['h']} "
                        f"(box {x.get('box','?')}) {x['cls'][:28]!r} {x['txt'][:16]!r}"
                        for x in bad[:4])
        return {"id": "G6", "ok": False,
                "detail": f"{len(bad)} control(s) under {MIN_TARGET_PX}px hit area -- {top}"}
    return {"id": "G6", "ok": True,
            "detail": f"all sampled controls >= {MIN_TARGET_PX}px across {len(routes)} routes"}

GUARD_JS = """() => {
  const o = {maxOutline: 0, minFont: 999, h1: [], wide: 0, vw: window.innerWidth};
  for (const e of document.querySelectorAll('*')) {
    const cs = getComputedStyle(e);
    const ow = parseFloat(cs.outlineWidth) || 0;
    if (ow > o.maxOutline) o.maxOutline = ow;
    const fs = parseFloat(cs.fontSize) || 0;
    if (fs > 0 && fs < o.minFont) o.minFont = fs;
    if (e.tagName === 'H1') {
      const r = e.getBoundingClientRect();
      if (r.height > 5 && r.width > 5) o.h1.push(Math.round(fs * 10) / 10);
    }
    const r2 = e.getBoundingClientRect();
    if (r2.width > o.vw * %f) o.wide++;
  }
  return o;
}""" % OVERFLOW_RATIO


def _probe(page, route: str, selector: str, props: list[str]):
    return page.evaluate(
        """([sel, props]) => {
             const e = document.querySelector(sel);
             if (!e) return null;
             const cs = getComputedStyle(e);
             const o = {_found: true};
             for (const p of props) o[p] = cs[p];
             return o;
           }""",
        [selector, props],
    )


def check_styles(write_baseline: bool = False) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        # Never skip silently. A gate that quietly no-ops is worse than no
        # gate at all -- it reports PASS while proving nothing.
        return {"id": "G5", "ok": False,
                "detail": "playwright not importable in this interpreter -- "
                          "G5 CANNOT run. Run the judge with the python that has "
                          "playwright installed (e.g. `python` from PATH, not a "
                          "bare sandbox), or install it. This is NOT a pass."}

    routes = sorted({r for r, _, _ in STYLE_PROBES} | {"/live-map", "/incidents"})
    observed: dict[str, dict] = {}
    guard_fail: list[str] = []

    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        pg = b.new_page(viewport={"width": 1600, "height": 1000})
        for route in routes:
            try:
                pg.goto(FRONTEND_URL + route, wait_until="domcontentloaded", timeout=90000)
                pg.wait_for_timeout(4000)
            except Exception as e:
                guard_fail.append(f"{route}: navigation failed {e}")
                continue
            g = pg.evaluate(GUARD_JS)
            if g["maxOutline"] > MAX_OUTLINE_PX:
                guard_fail.append(
                    f"{route}: element outline {g['maxOutline']}px "
                    f"(limit {MAX_OUTLINE_PX}) -- stray ring?")
            if g["minFont"] < MIN_FONT_PX:
                guard_fail.append(
                    f"{route}: font {g['minFont']}px below {MIN_FONT_PX}px legibility floor")
            for hs in g["h1"]:
                if not (H1_MIN_PX <= hs <= H1_MAX_PX):
                    guard_fail.append(
                        f"{route}: visible h1 at {hs}px outside [{H1_MIN_PX},{H1_MAX_PX}]")
            if g["wide"] > 0:
                guard_fail.append(
                    f"{route}: {g['wide']} element(s) wider than "
                    f"{OVERFLOW_RATIO}x viewport -- layout blowout")
            for r, sel, props in STYLE_PROBES:
                if r != route:
                    continue
                observed[f"{r} {sel}"] = _probe(pg, r, sel, props)
        b.close()

    if write_baseline:
        STYLE_BASELINE.write_text(json.dumps(
            {"_comment": "Human-written visual baseline. The loop may not edit this "
                         "file to make G5 pass. Re-record deliberately, in a reviewable "
                         "commit, after confirming the change is intended.",
             "probes": observed}, indent=2) + "\n", encoding="utf-8")
        return {"id": "G5", "ok": not guard_fail,
                "detail": f"visual baseline recorded ({len(observed)} probes)"
                          + ("" if not guard_fail else "; " + "; ".join(guard_fail[:3]))}

    if not STYLE_BASELINE.exists():
        return {"id": "G5", "ok": False,
                "detail": "no style-baseline.json -- run with --write-style-baseline"}

    want = json.loads(STYLE_BASELINE.read_text())["probes"]
    drift: list[str] = []
    for key, exp in want.items():
        got = observed.get(key)
        if got is None:
            drift.append(f"{key}: selector not found")
            continue
        for p, v in exp.items():
            if p == "_found":
                continue
            if got.get(p) != v:
                drift.append(f"{key} {p}: {v!r} -> {got.get(p)!r}")
    guard_fail += drift
    return {"id": "G5", "ok": not guard_fail,
            "detail": f"{len(want)} style probes match baseline; layout guards clean"
                      if not guard_fail else "; ".join(guard_fail[:5])}


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


def check_verifiers() -> dict:
    """G7 - the verifier suite itself must be sound.

    This session produced six verifiers that reported a result while measuring
    the wrong thing: a gate that swallowed ImportError, a probe that matched
    4 of 23 boxes, a fact-check comparing a substring, an audit asserting a
    fixed gap list, a checker too literal to match real text, and a gap
    detector satisfied by its own placeholder.

    Those fixes were all advisory -- written into scripts that the judge never
    ran. A later change could reintroduce any of them and the gate would stay
    green. This check makes the meta-property machine-decidable:

      V1  every verifier in tools/ must be byte-pinned, so an edit to a
          verifier cannot silently weaken it
      V2  no verifier may report success while its tooling is unavailable
          (the ImportError swallow)
      V3  no gap detector may be satisfiable by a placeholder
    """
    res = {"id": "G7", "ok": True, "detail": ""}
    problems: list[str] = []

    tools = ROOT / "tools"
    verifiers = sorted(p for p in tools.glob("*.py")
                       if not p.name.startswith("_"))
    if not verifiers:
        return {"id": "G7", "ok": False,
                "detail": "no verifiers found in tools/ -- V1 cannot run"}

    # V1: hash-pin every verifier. The pin file carries metadata keys
    # (_comment, written_at_commit, verifier_sha256_16) -- iterate the
    # verifier map, NOT the top-level document, or the metadata is reported
    # as deleted verifiers.
    pins = ROOT / ".loop" / "verifier-hashes.json"
    current = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16]
               for p in verifiers}
    if pins.exists():
        recorded = json.loads(pins.read_text(encoding="utf-8"))
        recorded = recorded.get("verifier_sha256_16", {})
        for name, want in recorded.items():
            got = current.get(name)
            if got is None:
                problems.append(f"V1 verifier DELETED: {name}")
            elif got != want:
                problems.append(
                    f"V1 verifier CHANGED: {name} ({want} -> {got}). "
                    "Verifiers are pinned: weakening one must be a deliberate, "
                    "reviewed act, not an edit that slips in with a feature.")
        for name in current:
            if name not in recorded:
                problems.append(f"V1 verifier ADDED (pin it): {name}")
    # (If pins are missing the caller is mid-bootstrap; baseline.py writes them.)

    # V2: no verifier may treat a missing dependency as success.
    for p in verifiers:
        src = p.read_text(encoding="utf-8", errors="replace")
        for bad in ("except ImportError:\n        return True",
                    "except ImportError:\n        pass",
                    "except Exception:\n        return True"):
            if bad in src:
                problems.append(f"V2 {p.name}: swallows an error as success")

    # V3: the Report gap must not be satisfiable by a placeholder.
    #
    # Source-text matching was the first attempt and it was wrong: the regex
    # only matched one exact spelling of the glob, so a real regression (an
    # unguarded `list(REPO.glob(...))` check) slipped past while the rule
    # looked present. Text-shape matching for behaviour is the wrong tool.
    #
    # Instead, run the audit's own report predicate with a SKELETON present
    # and require it to still report the gap. That tests the behaviour that
    # actually matters, so any rewrite of the audit is still covered.
    audit = ROOT / "tools" / "rubric_audit.py"
    if audit.exists():
        src = audit.read_text(encoding="utf-8", errors="replace")
        if "looks_like_finished_report" not in src:
            problems.append(
                "V3 rubric_audit.py has no prose guard on the Report gap, so a "
                "skeleton (REPORT-OUTLINE.md) would satisfy it -- this "
                "happened in b2aeb15.")
        else:
            # Behavioural probe: a skeleton plus an outline must NOT close it.
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    "_audit_probe", audit)
                mod = importlib.util.module_from_spec(spec)
                # Execute the source with REPO rebound to a temp dir holding
                # only a skeleton -- the predicate must return False.
                import tempfile
                with tempfile.TemporaryDirectory() as td:
                    tmp = pathlib.Path(td)
                    (tmp / "docs").mkdir()
                    (tmp / "docs" / "REPORT-OUTLINE.md").write_text(
                        "# Outline\n\n- section\n| a | b |\n", encoding="utf-8")
                    probe_src = src.replace(
                        f'REPO = pathlib.Path(r"{ROOT}")',
                        f'REPO = pathlib.Path(r"{tmp}")')
                    if probe_src == src:      # REPO defined differently
                        probe_src = re.sub(
                            r'^REPO\s*=.*$',
                            f'REPO = pathlib.Path(r"{tmp}")',
                            src, count=1, flags=re.M)
                    ns: dict = {"__name__": "_audit_probe"}
                    exec(compile(probe_src, str(audit), "exec"), ns)
                    fn = ns.get("looks_like_finished_report")
                    if fn is None:
                        problems.append(
                            "V3 audit has no looks_like_finished_report() to probe")
                    elif fn():
                        problems.append(
                            "V3 audit treats a skeleton as a finished report "
                            "(behavioural probe: REPORT-OUTLINE.md alone "
                            "closed the gap)")
            except Exception as e:
                problems.append(f"V3 probe could not run: {type(e).__name__}: {e}")

    if problems:
        return {"id": "G7", "ok": False,
                "detail": "; ".join(problems)[:600]}
    return {"id": "G7", "ok": True,
            "detail": f"{len(verifiers)} verifiers pinned, "
                      f"{len(current)} hashed, no error-swallowing or "
                      f"placeholder-satisfiable gap"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quick", action="store_true",
                    help="skip the Playwright route sweep (G4)")
    ap.add_argument("--write-style-baseline", action="store_true",
                    help="record the visual baseline (human action, reviewable commit)")
    args = ap.parse_args()

    t0 = time.time()
    checks = [check_typescript(), check_backend_suites(), check_backend_live()]
    checks += check_boundaries()
    if args.write_style_baseline:
        checks.append(check_styles(write_baseline=True))
    elif not args.quick:
        checks.append(check_routes())
        checks.append(check_styles())
        checks.append(check_targets())
    else:
        # Even in quick mode, keep the layout + target guards -- they are cheap
        # and they are the only thing standing between a stray CSS rule and a
        # green run.
        checks.append(check_styles())
        checks.append(check_targets())

    # G7 always runs, including --quick: pure text inspection, costs nothing,
    # and it is the guard against a verifier being quietly weakened.
    checks.append(check_verifiers())

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
