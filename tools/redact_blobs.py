"""
Redact credential values from every blob in git history, without touching which
files exist in which commit.

WHY THIS INSTEAD OF `git filter-repo --replace-text`
----------------------------------------------------
`--replace-text` only applies to blobs already selected by `--path`, and `--path`
is an ALLOWLIST: naming paths keeps only those files and deletes the rest. Two
consequences, both hit the hard way during this cleanup:

  1. `--replace-text` alone (no --path) rewrites nothing -> 10 keys survived.
  2. `--path a.py --path b.py` (no --invert-paths) kept 5 files and deleted the
     other 280.
  3. `--invert-paths --path a.py` deleted a.py instead of redacting it.

`--blob-callback` sidesteps the selection question entirely: it is invoked for
every blob in the repository, so it rewrites contents everywhere while leaving
the file list of each commit untouched.

The patterns are shapes, never literal secrets, so this file is safe to commit.

Usage:
    git filter-repo --force --blob-callback '
        exec(open("tools/redact_blobs.py", encoding="utf-8").read())
    '
"""
import re

PATTERNS = [
    (rb"AIza[0-9A-Za-z_\-]{35}", b"***REDACTED-GOOGLE-API-KEY***"),
    (rb"AQ\.Ab[0-9A-Za-z_\-]{40,}", b"***REDACTED-VERTEX-SERVICE-ACCOUNT-KEY***"),
    (rb"sk-ant-[0-9A-Za-z_\-]{32,}", b"***REDACTED-ANTHROPIC-KEY***"),
    (rb"sk-(?:proj-)?[0-9A-Za-z_\-]{32,}", b"***REDACTED-OPENAI-KEY***"),
    (rb"gh[pousr]_[0-9A-Za-z]{36,}", b"***REDACTED-GITHUB-TOKEN***"),
    # Not a live credential, but it shipped in source as a JWT signing key.
    (rb"***REDACTED-JWT-PLACEHOLDER***", b"***REDACTED-JWT-PLACEHOLDER***"),
]

_COMPILED = [(re.compile(rx), rep) for rx, rep in PATTERNS]


def redact(blob: bytes) -> bytes:
    out = blob
    for rx, rep in _COMPILED:
        out = rx.sub(rep, out)
    return out
