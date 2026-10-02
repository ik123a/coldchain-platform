"""Redact credential shapes from every blob in git history.

Three API details, each learned by a failed rewrite:

1. --blob-callback receives a filter_repo.Blob OBJECT, not bytes. The payload
   is `blob.data`.
2. The snippet must assign back to `blob.data`. Defining a helper function is
   not enough - filter-repo reads the mutated attribute afterwards.
3. The callback must not write to stdout. Any print corrupts fast-import's
   stream and the rewrite dies with "could not write blob ... Broken pipe".

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

_data = blob.data
for _rx, _rep in _PATTERNS:
    _data = _re.sub(_rx, _rep, _data)
blob.data = _data
