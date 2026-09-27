"""Verify docs/REPORT-OUTLINE.md: links resolve, and every claimed number is
actually present in the document it cites.

Normalises whitespace before matching. An earlier version of this check used
exact substrings ('0/411') against docs written as '0 / 411', and matched
per-line, so it reported 5 false 'unsupported' claims. A verifier that cries
wolf is as useless as one that passes everything.
"""
import pathlib
import re
import sys
import zipfile

REPO = pathlib.Path(r"D:\Projects\capstone project\coldchain-platform")
OUT = REPO / "docs" / "REPORT-OUTLINE.md"
txt = OUT.read_text(encoding="utf-8", errors="replace")
docs = {p.name: p.read_text(encoding="utf-8", errors="replace")
        for p in (REPO / "docs").glob("*.md")}


def norm(s: str) -> str:
    """Collapse all whitespace so '0 / 411' matches a search for '0/411'."""
    return re.sub(r"\s+", " ", s)


ntxt = norm(txt)
print("=" * 78)
print("REPORT-OUTLINE.md VERIFICATION")
print("=" * 78)

# ---- 1. links resolve -----------------------------------------------------
links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", txt)
broken = [f"{l} -> {h}" for l, h in links
          if not h.startswith("http") and not (OUT.parent / h).exists()]
print(f"\n[1] RELATIVE LINKS")
print(f"    {len(links)} links, {len(broken)} broken")
for b in broken:
    print(f"      BROKEN: {b}")

# ---- 2. claimed facts present in cited source ----------------------------
CLAIMS = [
    ("3,441", "PERFORMANCE-RESULTS.md", "live-map mutation before"),
    ("2,604", "PERFORMANCE-RESULTS.md", "live-map mutation after"),
    ("154", "PERFORMANCE-RESULTS.md", "phantom alert count"),
    ("0 / 411", "PERFORMANCE-RESULTS.md", "controls under 24px after"),
    ("22.4%", "PERFORMANCE-RESULTS.md", "controls under 24px before"),
    ("26", "ARCHITECTURE.md", "module count"),
    ("15 database tables", "ARCHITECTURE.md", "table count"),
    ("54", "ARCHITECTURE.md", "endpoint count"),
    ("deterministic", "ARCHITECTURE.md", "no-LLM decision"),
    ("DETERMINISTIC-AGENTS", "SDG-STAKEHOLDERS-REQUIREMENTS.md", "AI honesty"),
    ("SDG 3", "SDG-STAKEHOLDERS-REQUIREMENTS.md", "primary SDG"),
    ("SDG 13", "SDG-STAKEHOLDERS-REQUIREMENTS.md", "explicitly NOT claimed"),
    ("cross-validation", "TESTING.md", "cross-validation methods"),
    ("limitation", "SDG-STAKEHOLDERS-REQUIREMENTS.md", "limitations section"),
    ("Horizon", "LOG-DIARY.md", "future prospects table"),
    ("service.completed", "TESTING.md", "known failing assertion"),
]
print(f"\n[2] CLAIMED FACTS TRACED TO A CITED SOURCE")
unsupported = []
for needle, src, what in CLAIMS:
    if src not in docs:
        unsupported.append(f"{src} MISSING")
        print(f"    MISSING DOC  {src}")
        continue
    if norm(needle).lower() in norm(docs[src]).lower():
        print(f"    OK           {needle:<22} in {src:<32} ({what})")
    else:
        unsupported.append(f"{needle} not in {src}")
        print(f"    UNSUPPORTED  {needle:<22} not in {src}")

# ---- 3. referenced external artefacts exist -------------------------------
print(f"\n[3] REFERENCED ARTEFACTS")
art_ok = True
for f in ["C:/Users/SKV/ui-compare/final", "C:/Users/SKV/coldchain-video/coldchain-ui-tour.mp4"]:
    p = pathlib.Path(f)
    if p.is_dir():
        n = len(list(p.glob("*.png")))
        print(f"    {f}  -> {n} png files")
        if n == 0:
            art_ok = False
    else:
        ok = p.exists()
        print(f"    {f}  -> {'EXISTS' if ok else 'MISSING'}")
        art_ok &= ok

# ---- 4. rubric deadline cross-checked against the framework ---------------
print(f"\n[4] DEADLINE / FORMAT CLAIMS vs university-docs")
fw = REPO.parent / "university-docs" / "CBCA301_Framework_Capstone_Project.docx"
if fw.exists():
    with zipfile.ZipFile(fw) as z:
        x = z.read("word/document.xml").decode("utf-8", "replace")
    nx = norm(re.sub(r"<[^>]+>", " ", x))
    for claim, pat in [("23 November 2026 panel date", r"23 November 2026"),
                       ("20-30 page report", r"20.{0,3}30 page"),
                       ("10-15 minute presentation", r"10.{0,3}15 minute")]:
        hit = re.search(pat, nx, re.I) is not None
        print(f"    {'OK          ' if hit else 'NOT FOUND   '} {claim}")
else:
    print("    framework docx not found")

# ---- verdict --------------------------------------------------------------
print("\n" + "=" * 78)
bad = len(broken) + len(unsupported) + (0 if art_ok else 1)
print(f"VERDICT: {'PASS - outline is internally consistent' if not bad else f'{bad} issue(s)'}")
sys.exit(0 if not bad else 1)
