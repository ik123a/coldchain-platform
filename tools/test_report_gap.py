"""Adversarial test: the Report gap must NOT close on a skeleton, and MUST
close on real prose. A gap detector that closes itself is worse than a fixed
gap list, because it manufactures a false all-clear on the single most
important remaining deliverable.
"""
import importlib.util
import pathlib
import subprocess
import sys
import tempfile

AUDIT = pathlib.Path(r"D:\Projects\capstone project\coldchain-platform\tools\rubric_audit.py")
REAL_PROSE = """# Capstone Mini-Report

""" + ("\n\n".join(
    "This paragraph is deliberately long prose written to stand in for a real "
    "chapter of the report, carrying more than eighteen words so that the "
    "detector counts it as prose rather than as a heading, a table row, or a "
    "bulleted list item of some kind. " * 3 for _ in range(30)
)) + "\n"


def run_audit(repo: pathlib.Path) -> str:
    """Run the audit against a temp copy of the repo with a given docs set."""
    src = AUDIT.read_text(encoding="utf-8")
    src = src.replace(r'D:\Projects\capstone project\coldchain-platform',
                      str(repo).replace("\\", "\\\\"))
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as f:
        f.write(src)
        name = f.name
    try:
        r = subprocess.run([sys.executable, name], capture_output=True,
                           text=True, timeout=600)
        return r.stdout + r.stderr
    finally:
        pathlib.Path(name).unlink(missing_ok=True)


def build_repo(with_report: bool) -> pathlib.Path:
    tmp = pathlib.Path(tempfile.mkdtemp())
    src_root = pathlib.Path(r"D:\Projects\capstone project\coldchain-platform")
    for sub in ("docs", "tools"):
        s = src_root / sub
        if s.exists():
            subprocess.run(["robocopy", str(s), str(tmp / sub), "/E", "/NFL",
                            "/NDL", "/NJH", "/NJS", "/NP"], capture_output=True)
    if with_report:
        (tmp / "docs" / "MINI-REPORT.md").write_text(REAL_PROSE, encoding="utf-8")
    return tmp


print("=" * 78)
print("ADVERSARIAL TEST: does the Report gap detect a skeleton correctly?")
print("=" * 78)

print("\n[1] only REPORT-OUTLINE.md present (the current real state)")
out1 = run_audit(build_repo(with_report=False))
has1 = "No mini-report draft" in out1
print(f"    Report gap reported: {has1}   -> {'PASS' if has1 else 'FAIL'}"
      f"  (outline must NOT count as the report)")

print("\n[2] a real prose report added")
out2 = run_audit(build_repo(with_report=True))
has2 = "No mini-report draft" in out2
print(f"    Report gap reported: {has2}   -> {'PASS' if not has2 else 'FAIL'}"
      f"  (prose must close the gap)")

print("\n" + "=" * 78)
ok = has1 and not has2
print(f"VERDICT: {'PASS - the gap opens on a skeleton and closes on prose' if ok else 'FAIL'}")
sys.exit(0 if ok else 1)
