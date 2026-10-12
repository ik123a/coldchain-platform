"""Report-download tickets: bound, short-lived, and rejected on substitution.

WHY THESE EXIST
---------------
Phase 1 introduced `POST /api/reports/{iid}/ticket` so a plain `<a href>` could
carry authorization. Reviewing it against what a link-borne credential actually
needs turned up two real weaknesses, both fixed here:

  1. The ticket was the SAME 12-hour session token. A credential that rides in a
     URL (access logs, browser history, Referer) must not live for 12 hours.
  2. The ticket carried no incident id, so a ticket minted for report 1 would
     download report 2 — resource substitution.

These tests assert the fixed properties, and each can fail against the old code.
"""
import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.security import create_token, decode_token  # noqa: E402

# The route module reads its TTL at import; mirror it so the test asserts the
# configured value rather than a hardcoded number.
os.environ.setdefault("APP_ENV", "development")


class TicketPropertiesTests(unittest.TestCase):

    def setUp(self):
        # Import lazily: the module needs a JWT secret resolvable, which dev mode
        # provides.
        from app.api.routes.reports import REPORT_TICKET_TTL_S
        self.ttl = REPORT_TICKET_TTL_S

    def test_ttl_is_short_not_a_session_lifetime(self):
        """A URL-borne credential must not live for hours."""
        self.assertLessEqual(
            self.ttl, 900,
            f"report ticket TTL is {self.ttl}s; a link-borne credential should be "
            f"minutes, not the 12h session lifetime")
        self.assertGreater(self.ttl, 0)

    def test_ticket_carries_the_incident_binding(self):
        """The payload must name the incident it authorizes."""
        tok = create_token(7, "op@test.local", "operator", None,
                           ttl_seconds=self.ttl, extra={"iid": 42, "typ": "report_ticket"})
        claims = decode_token(tok)
        self.assertIsNotNone(claims, "ticket did not verify")
        self.assertEqual(claims["iid"], 42, "ticket is not bound to an incident")
        self.assertEqual(claims["typ"], "report_ticket")

    def test_ticket_expires_within_its_ttl(self):
        """exp must be ~now + ttl, not the 12h default."""
        tok = create_token(7, "op@test.local", "operator", None,
                           ttl_seconds=self.ttl, extra={"iid": 1, "typ": "report_ticket"})
        claims = decode_token(tok)
        remaining = claims["exp"] - int(time.time())
        self.assertLessEqual(remaining, self.ttl + 5,
                             f"ticket lives {remaining}s, longer than its TTL")
        self.assertGreater(remaining, 0)

    def test_a_session_token_has_no_incident_binding(self):
        """Distinguishes a session token from a ticket, which the route relies on."""
        tok = create_token(7, "op@test.local", "operator", None)
        claims = decode_token(tok)
        self.assertNotIn("iid", claims)
        self.assertNotIn("typ", claims)

    def test_tampered_ticket_fails_verification(self):
        tok = create_token(7, "op@test.local", "operator", None,
                           ttl_seconds=self.ttl, extra={"iid": 1, "typ": "report_ticket"})
        forged = tok[:-1] + ("a" if tok[-1] != "a" else "b")
        self.assertIsNone(decode_token(forged), "a tampered ticket verified")

    def test_default_ttl_unchanged_for_logins(self):
        """The session token must keep its normal lifetime — only tickets are short."""
        tok = create_token(7, "op@test.local", "operator", None)
        claims = decode_token(tok)
        remaining = claims["exp"] - int(time.time())
        self.assertGreater(remaining, self.ttl + 60,
                           "login tokens were accidentally shortened to the ticket TTL")


class SubstitutionGuardTests(unittest.TestCase):
    """The route-level check that a ticket for incident A cannot fetch B."""

    def _authorize(self, ticket, authorization, iid):
        from app.api.routes.reports import _authorize_report_read
        return _authorize_report_read(iid, ticket, authorization)

    def test_ticket_for_another_incident_is_forbidden(self):
        from fastapi import HTTPException
        from app.api.routes.reports import REPORT_TICKET_TTL_S
        tok = create_token(7, "op@test.local", "operator", None,
                           ttl_seconds=REPORT_TICKET_TTL_S,
                           extra={"iid": 1, "typ": "report_ticket"})
        with self.assertRaises(HTTPException) as ctx:
            self._authorize(tok, None, 2)
        self.assertEqual(ctx.exception.status_code, 403,
                         "a ticket for incident 1 was accepted for incident 2")

    def test_ticket_for_its_own_incident_is_allowed(self):
        from app.api.routes.reports import REPORT_TICKET_TTL_S
        tok = create_token(7, "op@test.local", "operator", None,
                           ttl_seconds=REPORT_TICKET_TTL_S,
                           extra={"iid": 5, "typ": "report_ticket"})
        self._authorize(tok, None, 5)   # must not raise

    def test_a_session_token_in_the_query_string_is_not_a_ticket(self):
        """A full session token passed as ?ticket= must be refused.

        It is not resource-bound, so accepting it in the ticket position would
        reintroduce the substitution hole.
        """
        from fastapi import HTTPException
        session = create_token(7, "op@test.local", "operator", None)
        with self.assertRaises(HTTPException) as ctx:
            self._authorize(session, None, 1)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_no_credential_is_unauthorized(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            self._authorize(None, None, 1)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_bearer_header_still_authorizes_any_report(self):
        from app.api.routes.reports import _authorize_report_read
        session = create_token(7, "op@test.local", "operator", None)
        # Header path is the account credential, not a per-resource ticket.
        _authorize_report_read(3, None, f"Bearer {session}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
