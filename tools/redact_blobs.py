"""Redact credential shapes from every blob in git history.

--blob-callback is invoked once per blob with `blob` bound to the bytes; the
snippet MUST assign the substitution back to `blob`. Defining a helper function
is NOT enough: filter-repo executes the snippet and reads the `blob` variable
back, so an uncalled function leaves every key in place while the rewrite still
reports success and preserves all commits.

Patterns are shapes, never literal secrets, so this file is safe to commit.
"""
import re as _re

_PATTERNS = [
    (rb"AIza[0-9A-Za-z_\-]{35}", b"***REDACTED-GOOGLE-API-KEY***"),
    (rb"AQ\.Ab[0-9A-Za-z_\-]{40,}", b"***REDACTED-VERTEX-SERVICE-ACCOUNT-KEY***"),
    (rb"sk-ant-[0-9A-Za-z_\-]{32,}", b"***REDACTED-ANTHROPIC-KEY***"),
    (rb"sk-(?:proj-)?[0-9A-Za-z_\-]{32,}", b"***REDACTED-OPENAI-KEY***"),
    (rb"gh[pousr]_[0-9A-Za-z]{36,}", b"***REDACTED-GITHUB-TOKEN***"),
    (rb"***REDACTED-JWT-PLACEHOLDER***", b"***REDACTED-JWT-PLACEHOLDER***"),
]
_RX = [(_re.compile(a), b) for a, b in _PATTERNS]
for _rx, _rep in _RX:
    blob = _rx.sub(_rep, blob)
