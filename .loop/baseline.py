"""Write the reconciliation baseline. Run once, by hand, on a known-good tree.

    python .loop/baseline.py --write

Protected-file hashes are the anti-Goodhart anchor: if the loop edits a test to
make the goal pass, B1 fires. Re-writing the baseline is a HUMAN action and must
be a deliberate, reviewable commit — never something the build step does.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROTECTED = [
    "backend/tests/test_fleet_twin.py",
    "backend/tests/test_fleet_ai.py",
    "backend/tests/test_fleet_ops.py",
    "backend/tests/test_world_events.py",
    "backend/tests/test_scenario_analytics.py",
    "backend/tests/acceptance_sweep.py",
    ".loop/judge.py",
]


def sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    target = ROOT / ".loop" / "baseline.json"
    if not args.write:
        print(json.dumps(json.loads(target.read_text()), indent=2))
        return 0

    missing = [r for r in PROTECTED if not (ROOT / r).exists()]
    if missing:
        print(f"REFUSING to write baseline, missing: {missing}")
        return 1

    doc = {
        "_comment": "Anti-Goodhart anchor. Human-written. The build agent may NOT "
                    "edit this file or any path listed in protected_sha256.",
        "written_at_commit": __import__("subprocess").run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
            capture_output=True, text=True).stdout.strip(),
        "protected_sha256": {r: sha(ROOT / r) for r in PROTECTED},
    }
    target.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"baseline written at {doc['written_at_commit']}: "
          f"{len(PROTECTED)} protected files pinned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
