"""Adversarial test for G7: prove the verifier-integrity gate actually BITES.

Three injections, each must produce RELEASABLE: False and exit 1:
  T1  weaken a verifier in tools/            -> V1 hash pin must fire
  T2  reintroduce the ImportError swallow    -> V2 pattern scan must fire
  T3  restore the placeholder-satisfying glob -> V3 must fire

Then restore and confirm green. A gate that does not fail on a real
injection is decoration, not a check.
"""
import pathlib
import shutil
import subprocess
import sys

REPO = pathlib.Path(r"D:\Projects\capstone project\coldchain-platform")
TOOLS = REPO / "tools"


def load_check_verifiers():
    """Import check_verifiers() straight out of the judge.

    Calling the gate directly keeps this test fast (milliseconds instead of a
    75-second full judge per injection) while still exercising the real code
    path. One full judge run at the end confirms end-to-end behaviour.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "judge_under_test", REPO / ".loop" / "judge.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.check_verifiers


def judge(quick=True) -> tuple[bool, str]:
    cmd = [sys.executable, str(REPO / ".loop" / "judge.py")]
    if quick:
        cmd.append("--quick")
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=900)
    return r.returncode == 0, (r.stdout + r.stderr)


def g7_line(out: str) -> str:
    # The judge INDENTS its check lines ("  [FAIL] G7: ..."), so match on the
    # stripped line. A previous version matched the unstripped line, found
    # nothing, and reported a working gate as silent.
    for ln in out.splitlines():
        s = ln.strip()
        if s.startswith("[FAIL] G7") or s.startswith("[PASS] G7"):
            return s
    return "(no G7 line found)"


def g7_direct() -> tuple[bool, str]:
    """Run the gate itself. Returns (ok, detail)."""
    try:
        res = load_check_verifiers()()
    except Exception as e:  # a gate that crashes is a gate that cannot pass
        return False, f"CRASH: {type(e).__name__}: {e}"
    return bool(res["ok"]), str(res.get("detail", ""))


def restore(backups: dict[str, pathlib.Path]) -> None:
    for name, tmp in backups.items():
        shutil.copyfile(tmp, TOOLS / name)
        tmp.unlink(missing_ok=True)


results = []
print("=" * 78)
print("ADVERSARIAL TEST: does G7 (verifier integrity) actually bite?")
print("=" * 78)

# baseline: green, and G7 must be present
g0_ok, g0_detail = g7_direct()
print(f"\n[0] baseline: G7 ok={g0_ok}")
print(f"    detail: {g0_detail[:150]}")
results.append(("baseline G7 green", g0_ok))

# ---- T1: weaken a verifier -------------------------------------------------
print("\n[T1] weaken tools/rubric_audit.py (flip a probe to always-true)")
target = TOOLS / "rubric_audit.py"
backup = pathlib.Path(str(target) + ".bak")
shutil.copyfile(target, backup)
src = target.read_text(encoding="utf-8")
# make a probe permissive without deleting the file
mutated = src.replace(
    "real_gaps = []",
    "real_gaps = []  # weakened by T1", 1)
mutated = mutated.replace(
    'if not looks_like_finished_report():',
    'if False and not looks_like_finished_report():', 1)
assert mutated != src
target.write_text(mutated, encoding="utf-8")
g1_ok, g1_detail = g7_direct()
print(f"    G7 ok={g1_ok}  (must be False)")
print(f"    detail: {g1_detail[:150]}")
restore({"rubric_audit.py": backup})
results.append(("T1 weakened verifier -> caught", not g1_ok and "V1" in g1_detail))

# ---- T2: reintroduce the ImportError swallow -------------------------------
print("\n[T2] reintroduce the ImportError swallow in a verifier")
target2 = TOOLS / "verify_report_outline.py"
if not target2.exists():
    target2 = next(p for p in TOOLS.glob("*.py") if p.name != "rubric_audit.py")
print(f"    target: {target2.name}")
backup2 = pathlib.Path(str(target2) + ".bak")
shutil.copyfile(target2, backup2)
src2 = target2.read_text(encoding="utf-8")
mut2 = src2 + "\n\ndef _bad():\n    try:\n        import nonexistent_module_xyz\n    except ImportError:\n        return True\n"
target2.write_text(mut2, encoding="utf-8")
g2_ok, g2_detail = g7_direct()
print(f"    G7 ok={g2_ok}  (must be False)")
print(f"    detail: {g2_detail[:150]}")
restore({target2.name: backup2})
results.append(("T2 error-swallowing -> caught", not g2_ok and "V2" in g2_detail))

# ---- T3: restore the placeholder-satisfying glob ---------------------------
print("\n[T3] restore the placeholder-satisfying Report glob")
target3 = TOOLS / "rubric_audit.py"
backup3 = pathlib.Path(str(target3) + ".bak")
shutil.copyfile(target3, backup3)
src3 = target3.read_text(encoding="utf-8")
mut3 = src3.replace(
    "if not looks_like_finished_report():",
    'if not list(REPO.glob("docs/*[Rr][Ee][Pp][Oo][Rr][Tt]*.md")):', 1)
assert mut3 != src3
target3.write_text(mut3, encoding="utf-8")
g3_ok, g3_detail = g7_direct()
print(f"    G7 ok={g3_ok}  (must be False)")
print(f"    detail: {g3_detail[:150]}")
restore({"rubric_audit.py": backup3})
results.append(("T3 placeholder-satisfiable gap -> caught",
                not g3_ok and ("V1" in g3_detail or "V3" in g3_detail)))

# ---- restored: G7 must be green again -------------------------------------
# Assert G7 specifically, NOT overall releasability. B4 (added in 18a8642)
# fails by design until the exposed keys are actually rotated, so
# `releasable` is False for a correct reason and this assertion could never
# pass. The property under test is "the injections were fully undone", which
# is about G7 alone.
ok4, out4 = judge()
line4 = g7_line(out4)
b4_line = next((ln.strip() for ln in out4.splitlines()
                if ln.strip().startswith("[FAIL] B4")), "(no B4 failure)")
print(f"\n[4] after restore: full judge releasable={ok4}")
print(f"    {line4}")
print(f"    expected non-G7 failure: {b4_line[:80]}")
results.append(("restored to green: G7 reported PASS",
                line4.startswith("[PASS] G7")))
results.append(("only the rotation gate (B4) is red",
                b4_line.startswith("[FAIL] B4")))
# Guard against a future gate being added and silently failing here. Any
# non-B4 failure after restore means an injection was not fully undone --
# or a new gate has appeared that these tests know nothing about.
other_fails = [ln.strip() for ln in out4.splitlines()
               if ln.strip().startswith("[FAIL]")
               and not ln.strip().startswith("[FAIL] B4")]
print(f"    unexpected other failures: {other_fails}")
results.append(("no unexpected gate failures", not other_fails))

# ---- tree must be clean ---------------------------------------------------
st = subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                    capture_output=True, text=True).stdout.strip()
lines = [l for l in st.splitlines() if l.strip()]
# baseline.py --write regenerates these two by design, so they are expected
# residue, not an injection leak.
GENERATED = {".loop/baseline.json", ".loop/verifier-hashes.json"}
unexpected = [l for l in lines
              if not any(g in l for g in GENERATED)]
baks = [p.name for p in TOOLS.glob("*.bak")]
print(f"\n[5] working tree after test: {st!r}")
print(f"    expected (regenerated) : "
      f"{[l for l in lines if any(g in l for g in GENERATED)]}")
print(f"    UNEXPECTED residue     : {unexpected}")
print(f"    .bak leftovers         : {baks}")
results.append(("no injection residue (generated re-pins allowed)",
                not unexpected and not baks))

print("\n" + "=" * 78)
for name, passed in results:
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
allok = all(p for _, p in results)
print("=" * 78)
print(f"VERDICT: {'PASS - G7 bites on all three injections' if allok else 'FAIL'}")
sys.exit(0 if allok else 1)
