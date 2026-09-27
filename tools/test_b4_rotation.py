"""Adversarial test for B4 (rotation gate) and .loop/rotation.py.

B4 must FAIL with no ack, and must PASS only with a credible record. The
recorder must REFUSE a pre-leak date, a future date, an empty author, and
an overwrite -- because a gate that can be satisfied by an obviously false
claim provides no protection at all.
"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path(r"D:\Projects\capstone project\coldchain-platform")
ACK = REPO / ".loop" / "rotation-ack.json"
JUDGE = REPO / ".loop" / "judge.py"
ROT = REPO / ".loop" / "rotation.py"

TODAY = "2026-09-28"   # today; a rotation cannot be dated in the future
results = []


def b4(quick=True) -> tuple[bool, str]:
    """Run just check_rotation_gate out of the judge."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("j", JUDGE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    r = m.check_rotation_gate()
    return bool(r["ok"]), str(r.get("detail", ""))


def rotate(*args) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(ROT), *args],
                       cwd=REPO, capture_output=True, text=True, timeout=120)
    return r.returncode, (r.stdout + r.stderr)


def write_ack(**kw) -> None:
    doc = {"rotated_at": TODAY, "rotated_by": "tester",
           "keys_revoked": 6, "exposed_in_commits": ["bd61605"],
           "_comment": "TEST"}
    doc.update(kw)
    ACK.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


had_ack = ACK.exists()
backup = None
if had_ack:
    backup = pathlib.Path(tempfile.mkdtemp()) / "ack.json"
    shutil.copyfile(ACK, backup)

try:
    print("=" * 78)
    print("ADVERSARIAL TEST: B4 rotation gate")
    print("=" * 78)

    # ---- 1. no ack -> must FAIL -------------------------------------------
    if ACK.exists():
        ACK.unlink()
    ok, d = b4()
    print(f"\n[1] no ack file            -> ok={ok}  (must be False)")
    print(f"    {d[:110]}")
    results.append(("no ack -> gate FAILS", not ok))

    # ---- 2. credible record -> must PASS ---------------------------------
    write_ack()
    ok, d = b4()
    print(f"\n[2] credible record        -> ok={ok}  (must be True)")
    print(f"    {d[:110]}")
    results.append(("credible record -> gate PASSES", ok))

    # ---- 3. record dated BEFORE the exposure -> must FAIL ----------------
    write_ack(rotated_at="2026-09-01")
    ok, d = b4()
    print(f"\n[3] dated before exposure  -> ok={ok}  (must be False)")
    print(f"    {d[:110]}")
    results.append(("pre-leak date rejected", not ok))

    # ---- 4. missing field -> must FAIL -----------------------------------
    write_ack(rotated_by="")
    ok, d = b4()
    print(f"\n[4] empty rotated_by       -> ok={ok}  (must be False)")
    print(f"    {d[:110]}")
    results.append(("unattributed record rejected", not ok))

    # ---- 5. unparseable date -> must FAIL --------------------------------
    ACK.write_text('{"rotated_at": "last tuesday", "rotated_by": "x"}\n',
                   encoding="utf-8")
    ok, d = b4()
    print(f"\n[5] unparseable date       -> ok={ok}  (must be False)")
    print(f"    {d[:110]}")
    results.append(("unparseable date rejected", not ok))

    # ---- 6. the RECORDER must refuse dishonest input ---------------------
    print(f"\n[6] recorder rejects bad input")
    rc, out = rotate("--rotated", "2026-09-01", "--by", "tester")
    print(f"    pre-leak date   -> exit {rc}  (must be 1)")
    results.append(("recorder rejects pre-leak date", rc == 1))
    rc, out = rotate("--rotated", "2099-01-01", "--by", "tester")
    print(f"    future date     -> exit {rc}  (must be 1)")
    results.append(("recorder rejects future date", rc == 1))
    rc, out = rotate("--rotated", "2026-09-29", "--by", "   ")
    print(f"    empty author    -> exit {rc}  (must be 1)")
    results.append(("recorder rejects empty author", rc == 1))
    rc, out = rotate("--rotated", "not-a-date", "--by", "tester")
    print(f"    malformed date  -> exit {rc}  (must be 1)")
    results.append(("recorder rejects malformed date", rc == 1))

    # ---- 7. recorder refuses to overwrite a good record ------------------
    # Clear any leftover ack first. Test [5] wrote a malformed one, and the
    # recorder then (correctly) refused to create a record on top of it --
    # which made this assertion fail for a reason unrelated to what it tests.
    ACK.unlink(missing_ok=True)
    rc, _ = rotate("--rotated", TODAY, "--by", "first")
    print(f"    first record    -> exit {rc}  (must be 0)")
    rc2, out2 = rotate("--rotated", TODAY, "--by", "second")
    print(f"    overwrite       -> exit {rc2}  (must be 1)")
    results.append(("recorder created a record", rc == 0))
    results.append(("recorder refuses to overwrite", rc2 == 1))

finally:
    ACK.unlink(missing_ok=True)
    if backup and backup.exists():
        shutil.copyfile(backup, ACK)

print("\n" + "=" * 78)
for n, p in results:
    print(f"  [{'PASS' if p else 'FAIL'}] {n}")
allok = all(p for _, p in results)
print("=" * 78)
print(f"VERDICT: {'PASS - B4 resists every false claim' if allok else 'FAIL'}")
sys.exit(0 if allok else 1)
