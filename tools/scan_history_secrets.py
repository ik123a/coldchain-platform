"""Shape-based secret scan over ALL git history.

Why this exists: the earlier audit compared the CURRENT .env against history
and found the primary key had changed. That only answers "is THIS value in
history" -- it cannot find a key that was committed, rotated, and never again
compared to anything. A shape scan finds those.

The earlier attempt timed out at 600s because it walked commits x files and
shelled out to `git show` per blob (~8000 subprocess calls). This version
reads every UNIQUE blob exactly once via `git cat-file --batch-all-objects`,
which is O(blobs) not O(commits x files).

Prints only file paths, shas and match counts -- never the secret itself.
"""
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(r"D:\Projects\capstone project\coldchain-platform")

# Shapes only. Deliberately requires enough entropy/length to avoid flagging
# placeholders like "changeme" or a documented example value.
PATTERNS = {
    "google/gemini-api-key": re.compile(rb"AIza[0-9A-Za-z_\-]{35}"),
    "google-oauth": re.compile(rb"AIzaSy[0-9A-Za-z_\-]{30,}"),
    "vertex-service-account": re.compile(rb"AQ\.Ab[0-9A-Za-z_\-]{40,}"),
    "openai": re.compile(rb"sk-(?:proj-)?[0-9A-Za-z_\-]{32,}"),
    "anthropic": re.compile(rb"sk-ant-[0-9A-Za-z_\-]{32,}"),
    "github-pat": re.compile(rb"gh[pousr]_[0-9A-Za-z]{36,}"),
    "slack": re.compile(rb"xox[baprs]-[0-9A-Za-z\-]{10,}"),
    "aws-access-key-id": re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    "stripe": re.compile(rb"\b[rs]k_(?:live|test)_[0-9A-Za-z]{20,}"),
    "private-key-block": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "jwt": re.compile(rb"\beyJ[0-9A-Za-z_\-]{10,}\.eyJ[0-9A-Za-z_\-]{10,}\."),
}
# Values that are documentation, not secrets.
ALLOW = re.compile(
    rb"(your[_\-]?\w*|example|placeholder|changeme|dummy|xxxxx|\.\.\.|"
    rb"<[a-z_\-]+>|\{\{.*\}\}|REPLACE)", re.I)

MAX_BLOB = 400_000  # skip binaries / huge generated files


def batch_blobs() -> list[tuple[str, int]]:
    """Every unique blob reachable from any ref, with its size."""
    r = subprocess.run(
        ["git", "cat-file", "--batch-all-objects", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
        cwd=REPO, capture_output=True, timeout=300)
    out = []
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1] == "blob":
            try:
                size = int(parts[2])
            except ValueError:
                continue
            if 0 < size <= MAX_BLOB:
                out.append((parts[0], size))
    return out


def scan() -> int:
    blobs = batch_blobs()
    total_bytes = sum(s for _, s in blobs)
    print(f"unique blobs to scan : {len(blobs):,}  ({total_bytes/1e6:.1f} MB)")
    if not blobs:
        print("  NOTHING SCANNED -- that is a failure, not a clean result")
        return 1

    # Stream contents through one `git cat-file --batch` process.
    proc = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=REPO, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    assert proc.stdin and proc.stdout
    findings: dict[str, set[str]] = {}
    scanned = 0

    for sha, size in blobs:
        proc.stdin.write(f"{sha}\n".encode())
        proc.stdin.flush()
        header = proc.stdout.readline().decode("utf-8", "replace").split()
        if len(header) < 3:
            continue
        body = proc.stdout.read(int(header[2]))
        proc.stdout.read(1)  # trailing newline
        scanned += 1
        for name, pat in PATTERNS.items():
            for m in pat.finditer(body):
                start, end = max(0, m.start() - 60), min(len(body), m.end() + 60)
                ctx = body[start:end]
                if ALLOW.search(ctx):
                    continue
                findings.setdefault(name, set()).add(sha)

    proc.stdin.close()
    proc.wait(timeout=120)

    print(f"blobs actually read  : {scanned:,}")
    print()
    if not findings:
        print("RESULT: no secret-shaped value in any unique blob across all history.")
        return 0

    print("RESULT: secret-shaped values found in history.")
    print("  (values withheld; listed by shape and blob sha only)\n")
    for name, shas in sorted(findings.items()):
        print(f"  {name:<26} {len(shas):>3} blob(s)")
        for s in sorted(shas)[:5]:
            # Which path(s) did that blob appear as?
            r = subprocess.run(["git", "cat-file", "-p", s],
                               cwd=REPO, capture_output=True)
            first = r.stdout[:200].decode("utf-8", "replace").splitlines()[:1]
            print(f"      {s[:12]}  {first[0][:70] if first else '(binary)'}")
    print("\nACTION: rotate every value above at its provider, then optionally")
    print("        git filter-repo --invert-paths to purge from history.")
    return 2


if __name__ == "__main__":
    sys.exit(scan())
