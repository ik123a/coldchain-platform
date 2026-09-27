"""ColdChain servo loop — the controller.

A servo loop with a hard retry cap. Each iteration: judge the repo, and if a
goal is failing, hand the concrete failure to a build agent to fix. Three
consecutive unfixed failures, or any boundary violation, escalates to a human
and stops. The loop is the worker, NOT the acceptance officer — it never
rewrites the judge, the baseline, or a protected test to make itself pass.

    python .loop/loop.py --max-iterations 5
    python .loop/loop.py --dry-run          # judge only, change nothing

Red lines enforced here (see loop-design-check):
  - the judge is deterministic and external to the build step;
  - the build agent may not edit acceptance conditions;
  - human keeps judgment: the loop stops and reports, it does not declare the
    work accepted.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
JUDGE = ROOT / ".loop" / "judge.py"
LOG = ROOT / ".loop" / "loop-log.jsonl"
MAX_REPEATED_IDENTICAL = 2   # same failure twice running = oscillation, stop


def judge(quick: bool) -> dict:
    cmd = [sys.executable, str(JUDGE), "--json"] + (["--quick"] if quick else [])
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=900)
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"releasable": False, "checks": [
            {"id": "JUDGE", "ok": False, "detail": p.stdout[-500:] + p.stderr[-500:]}
        ], "goals_passed": "?", "boundaries_held": "?"}


def log(rec: dict) -> None:
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({**rec, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}) + "\n")


def failing(checks: list[dict]) -> tuple[list[dict], list[dict]]:
    goals = [c for c in checks if c["id"].startswith("G") and not c["ok"]]
    bounds = [c for c in checks if c["id"].startswith("B") and not c["ok"]]
    return goals, bounds


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-iterations", type=int, default=5)
    ap.add_argument("--quick", action="store_true", help="skip the Playwright sweep")
    ap.add_argument("--dry-run", action="store_true", help="judge once, change nothing")
    args = ap.parse_args()

    prev_sig, repeats = None, 0
    for it in range(1, args.max_iterations + 1):
        print(f"\n=== iteration {it}/{args.max_iterations} " + "-" * 44)
        rep = judge(args.quick)
        goals, bounds = failing(rep.get("checks", []))

        for c in rep.get("checks", []):
            print(f"  [{'PASS' if c['ok'] else 'FAIL'}] {c['id']}: {c['detail'][:110]}")
        log({"iteration": it, "releasable": rep.get("releasable"),
             "goals": [c["id"] for c in goals], "boundaries": [c["id"] for c in bounds]})

        if rep.get("releasable"):
            print(f"\n  GOALS {rep['goals_passed']} | BOUNDARIES {rep['boundaries_held']}"
                  f"\n  ALL CHECKS PASS -> servo loop converged. Stopping for human review.")
            return 0

        # A boundary breach is never "fixable" by the build agent: it means the
        # acceptance conditions themselves were touched. Stop immediately.
        if bounds:
            print("\n  BOUNDARY VIOLATION — the judge, baseline, or a protected test "
                  "was modified.\n  This is a human decision, not something the loop may "
                  "resolve. STOPPING.")
            for b in bounds:
                print(f"    {b['id']}: {b['detail'][:200]}")
            return 2

        if args.dry_run:
            print("\n  --dry-run: not dispatching a build agent.")
            return 1

        sig = json.dumps([c["id"] + c["detail"][:80] for c in goals])
        if sig == prev_sig:
            repeats += 1
            if repeats >= MAX_REPEATED_IDENTICAL:
                print(f"\n  OSCILLATION: identical failure {repeats}x in a row. "
                      f"The loop is not making progress. STOPPING.")
                return 3
        else:
            repeats = 0
        prev_sig = sig

        print(f"\n  {len(goals)} goal(s) failing -> a build agent must fix: "
              f"{[c['id'] for c in goals]}")
        print("  [loop hands the failure list to the build agent; "
              "it may not touch .loop/ or backend/tests/]")
        # Dispatch point. Left explicit so the build agent is a separate
        # context from the judge -- the judge must never grade its own work.
        print("  -> dispatch build agent with:")
        print(json.dumps([{ "id": c["id"], "failure": c["detail"][:600] } for c in goals],
                         indent=2)[:1200])
        break   # one dispatch per invocation; the orchestrator re-invokes us

    return 1


if __name__ == "__main__":
    sys.exit(main())
