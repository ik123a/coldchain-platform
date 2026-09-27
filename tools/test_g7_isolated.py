"""Isolated test: does each G7 rule fire INDEPENDENTLY?

The combined test showed V1 (the hash pin) catching everything, which masks
whether V2 and V3 work at all. V1 firing first is correct behaviour but it
means a combined test proves nothing about V2/V3.

Here each rule is exercised in isolation, with the hash pin re-written to
match the injected state so V1 stays quiet and the specific rule must fire.
"""
import hashlib
import importlib.util
import json
import pathlib
import shutil
import sys

REPO = pathlib.Path(r"D:\Projects\capstone project\coldchain-platform")
TOOLS = REPO / "tools"
PINS = REPO / ".loop" / "verifier-hashes.json"


def check():
    spec = importlib.util.spec_from_file_location(
        "j", REPO / ".loop" / "judge.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.check_verifiers()


def respin() -> None:
    """Re-pin verifiers to the CURRENT state so V1 is silent."""
    doc = {
        "written_at_commit": "test",
        "verifier_sha256_16": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16]
            for p in sorted(TOOLS.glob("*.py")) if not p.name.startswith("_")},
    }
    PINS.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def run(label: str, mutate, expect_tag: str):
    bak = {}
    try:
        for p in TOOLS.glob("*.py"):
            bak[p.name] = pathlib.Path(str(p) + ".bak")
            shutil.copyfile(p, bak[p.name])
        mutate()
        respin()                      # neutralise V1
        res = check()
        detail = str(res.get("detail", ""))
        fired = expect_tag in detail
        print(f"\n  {label}")
        print(f"    G7 ok={res['ok']}  (must be False)")
        print(f"    expect {expect_tag}: {'FIRED' if fired else 'DID NOT FIRE'}")
        print(f"    detail: {detail[:170]}")
        return (not res["ok"]) and fired
    finally:
        for name, b in bak.items():
            shutil.copyfile(b, TOOLS / name)
            b.unlink(missing_ok=True)
        respin()


results = []
print("=" * 78)
print("ISOLATED G7 RULE TEST (V1 neutralised so the specific rule must fire)")
print("=" * 78)

# V2: error swallowing
def m_v2():
    t = TOOLS / "verify_report_outline.py"
    t.write_text(t.read_text(encoding="utf-8") +
                 "\n\ndef _bad():\n    try:\n        import nope_xyz\n"
                 "    except ImportError:\n        return True\n", encoding="utf-8")
results.append(("V2 - reintroduce the ImportError swallow",
                run("V2 - reintroduce the ImportError swallow", m_v2, "V2")))

# V3: placeholder-satisfiable report gap
def m_v3():
    """Remove the prose guard entirely and decide the gap on a raw glob.

    Leaving looks_like_finished_report defined made this a no-op: the call
    site changed but the behavioural probe still ran the real predicate and
    correctly rejected the skeleton, so V3 passed -- for the wrong reason.
    The regression to simulate is the WHOLE guard being absent.
    """
    t = TOOLS / "rubric_audit.py"
    s = t.read_text(encoding="utf-8")
    # drop the guard function definition
    i = s.find("def looks_like_finished_report()")
    if i != -1:
        # find the next top-level statement after the function
        j = s.find('if not list(REPO.glob("**/*.pptx"))', i)
        s = s[:i] + s[j:]
    # decide the gap on a raw glob -> any *report*.md closes it
    s = s.replace("if not looks_like_finished_report():",
                  'if not list(REPO.glob("docs/*[Rr][Ee][Pp][Oo][Rr][Tt]*.md")):', 1)
    t.write_text(s, encoding="utf-8")
results.append(("V3 - unguarded placeholder-satisfiable report gap",
                run("V3 - unguarded placeholder-satisfiable report gap", m_v3, "V3")))

# V1 control: a verifier change WITHOUT re-pinning must be caught
t = TOOLS / "rubric_audit.py"
backup = pathlib.Path(str(t) + ".bak")
shutil.copyfile(t, backup)
t.write_text(t.read_text(encoding="utf-8") + "\n# tweak\n", encoding="utf-8")
res = check()
detail = str(res.get("detail", ""))
print("\n  V1 control - verifier edited without re-pinning")
print(f"    G7 ok={res['ok']}  (must be False)")
print(f"    V1 fired: {'V1' in detail}")
print(f"    detail: {detail[:170]}")
results.append(("V1 - verifier edited without re-pinning",
                (not res["ok"]) and "V1" in detail))
shutil.copyfile(backup, t)
backup.unlink(missing_ok=True)
respin()

print("\n" + "=" * 78)
for item in results:
    n, p = item if isinstance(item, tuple) else (str(item), item)
    print(f"  [{'PASS' if p else 'FAIL'}] {n}")
allok = all(p for item in results
            for p in (item if isinstance(item, tuple) else (item,)))
print("=" * 78)
print(f"VERDICT: {'PASS - each rule fires independently' if allok else 'FAIL'}")
sys.exit(0 if allok else 1)
