"""Record that the exposed API keys have been rotated at the provider.

    python .loop/rotation.py --rotated 2026-09-29 --by "your name"

READ THIS FIRST. This script does not rotate anything. It writes a record
asserting that YOU did. Running it to make the judge go green -- without
going to Google AI Studio and actually revoking the keys -- is worse than
leaving B4 red, because it converts a visible, unresolved security risk into
an invisible false claim.

Order of operations, genuinely:

  1. Go to Google AI Studio -> API Keys.
  2. Revoke / disable every key that appears in this repo's history.
  3. Create replacement keys and put the new ones in backend/.env.
  4. THEN run this script with today's date.

The 6 keys to revoke are listed in docs/LOG-DIARY.md under the 2026-09-28
security entry. tools/scan_history_secrets.py will confirm what is exposed;
it never prints the values.

Why the gate exists: removing a literal from source stops NEW exposure.
Rotating the value is what makes the HISTORICAL copy harmless. The second act
is the one that is easy to forget, and a clone of this repo still carries
every one of them.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ACK = ROOT / ".loop" / "rotation-ack.json"

# Date of bd61605, the first commit containing a live key. A rotation record
# predating this is not a rotation of these keys.
FIRST_EXPOSED_COMMIT = "2026-09-27"
EXPOSED_COMMITS = ["bd61605", "dfcd959", "bf84963"]
KEY_COUNT = 6


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Record a credential rotation you have actually performed.")
    ap.add_argument("--rotated", required=True, metavar="YYYY-MM-DD",
                    help="date you revoked the keys at the provider")
    ap.add_argument("--by", required=True, metavar="WHO",
                    help="who performed the rotation")
    ap.add_argument("--force", action="store_true",
                    help="allow a date on/after today even if you meant otherwise")
    args = ap.parse_args()

    # --- validate the date -------------------------------------------------
    try:
        when = _dt.date.fromisoformat(args.rotated)
    except ValueError:
        print(f"Not an ISO date: {args.rotated!r}. Use YYYY-MM-DD.")
        return 1

    if args.rotated < FIRST_EXPOSED_COMMIT:
        print(f"REFUSING: {args.rotated} is before {FIRST_EXPOSED_COMMIT}, the "
              f"date the keys were first committed (bd61605).")
        print("         A rotation cannot predate the leak it remediates.")
        return 1

    today = _dt.date.today()
    if when > today and not args.force:
        print(f"REFUSING: {args.rotated} is in the future (today is {today}).")
        return 1

    if not args.by.strip():
        print("REFUSING: --by is empty. An unattributed rotation is not a record.")
        return 1

    # --- refuse to overwrite a good record with a worse one -----------------
    if ACK.exists():
        try:
            prev = json.loads(ACK.read_text(encoding="utf-8"))
        except Exception:
            prev = {}
        if prev.get("rotated_at"):
            print(f"REFUSING: a rotation is already recorded "
                  f"({prev['rotated_at']} by {prev.get('rotated_by')}).")
            print("         Delete .loop/rotation-ack.json first if this is a "
                  "correction, so the change is visible in the diff.")
            return 1

    doc = {
        "_comment": "Assertion that the exposed keys were revoked AT THE "
                    "PROVIDER. Written by a human, not performed by this "
                    "script. B4 fails the judge until this file exists.",
        "rotated_at": args.rotated,
        "rotated_by": args.by.strip(),
        "keys_revoked": KEY_COUNT,
        "exposed_in_commits": EXPOSED_COMMITS,
        "note": "Removal from source (4767514) is NOT rotation. Rotation is "
                "what makes the historical copies harmless.",
    }
    ACK.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded: {KEY_COUNT} keys confirmed rotated on {args.rotated} "
          f"by {args.by.strip()}.")
    print(f"Written: {ACK.relative_to(ROOT)}")
    print("\nIf you have NOT actually revoked them yet, delete this file now:")
    print(f"    rm {ACK.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
