"""Authenticated WebSocket access.

HISTORY
-------
`/ws` used to call `websocket.accept()` unconditionally and register every
connection on the global broadcast hub. A client needed no credential of any
kind: an anonymous request received the `hello` payload and then the entire
fleet event stream — vehicle positions, cargo temperatures, incident
diagnostics, escalation decisions.

THE CONTRACT
------------
A client now mints a single-use ticket over the authenticated REST API
(`POST /api/ws/ticket`) and presents it during the handshake. The ticket is:

  * bound to the authenticated principal AND to a telemetry scope derived from
    the server-side role — never from anything the client claims;
  * opaque, cryptographically random (secrets.token_urlsafe), and short-lived;
  * single-use, enforced atomically in the ticket store, so a replay of a
    captured ticket is rejected;
  * delivered in the WebSocket HANDSHAKE HEADERS, not the query string:
    uvicorn logs `WebSocket /ws?ticket=...` verbatim on every accept, so a
    query parameter would write the credential straight into access logs.

Scopes enforce least privilege for the whole connection:
  * `fleet`   (operator): every broadcast, unfiltered.
  * `vehicle` (driver):  only messages attributable to the driver's own vehicle.
                         The driver console needs one truck's telemetry; it has no
                         reason to see other operators' incidents or approvals.
"""
import asyncio, json, logging
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status

from ..core.authz import require_auth
from ..core.ws_tickets import STORE, TicketRejected, _fingerprint
from ..simulation.runner import BROADCAST, RUNNERS

log = logging.getLogger("coldchain.ws")

router = APIRouter()

# The subprotocol the browser uses to carry the ticket. Defined by us; the server
# echoes the chosen value back, so the handshake completes normally.
TICKET_PROTOCOL_PREFIX = "cc-ticket."
TICKET_PROTOCOL = "cc-ticket"
QUERY_FALLBACK = "ticket"


def _ticket_from(websocket: WebSocket) -> str | None:
    """Extract the ticket WITHOUT ever logging it.

    Preference order:
      1. `Sec-WebSocket-Protocol: cc-ticket.<ticket>` — never logged by uvicorn.
      2. `?ticket=` — supported for non-browser clients, but it does reach the
         access log (uvicorn logs the path with its query string), so it is a
         documented trade-off rather than the recommended path.
    """
    raw = websocket.headers.get("sec-websocket-protocol") or ""
    for part in (p.strip() for p in raw.split(",")):
        if part.startswith(TICKET_PROTOCOL_PREFIX):
            return part[len(TICKET_PROTOCOL_PREFIX):]
    return websocket.query_params.get(QUERY_FALLBACK)


def _narrow(ticket, msg) -> dict | None:
    """Decide a parsed message's fate. Returns the dict to send, or None.

    Operating on the parsed dict (rather than on the raw string) matters: the
    position frame carries the WHOLE fleet, so it has to be reduced in place and
    the reduced version is what gets serialized. Deciding visibility from one
    parse and re-serializing another would hand the driver every vehicle.
    """
    if not isinstance(msg, dict):
        return None

    if ticket.scope == "fleet":
        return msg                       # operator: full fleet visibility

    vid = ticket.vehicle_id
    if not vid:
        return None                      # a vehicle-scoped ticket with no vehicle

    if msg.get("type") == "vehicle.position.updated":
        own = [v for v in (msg.get("vehicles") or [])
               if isinstance(v, dict) and v.get("vehicle_id") == vid]
        if not own:
            return None
        return {**msg, "vehicles": own}  # narrowed for this driver

    # Single-vehicle frames: forward only if they name the driver's vehicle.
    if "vehicle_id" in msg:
        return msg if msg.get("vehicle_id") == vid else None

    # Nothing identifies whose data this is (sensor_update, alert, agent_event,
    # weather.changed, ...). Those are simulation-wide telemetry for operator
    # screens; a driver session has no authorized view of them, so drop.
    return None


def _filter_frame(ticket, message: str) -> str | None:
    """Return the message to send, or None to withhold it.

    One parse, one decision, one serialization — so what the scope check approved
    is exactly what the client receives.
    """
    if ticket.scope == "fleet":
        return message                   # operator: pass through byte-identical
    try:
        msg = json.loads(message)
    except (ValueError, TypeError):
        return None
    narrowed = _narrow(ticket, msg)
    if narrowed is None:
        return None
    # Re-serialize only when something was actually removed.
    if narrowed is msg:
        return message
    return json.dumps(narrowed)


def _visible_to(ticket, message: str) -> bool:
    """Is this message within the connection's scope? (Narrowing ignored.)"""
    try:
        msg = json.loads(message)
    except (ValueError, TypeError):
        return False
    return _narrow(ticket, msg) is not None


@router.post("/api/ws/ticket")
async def issue_ws_ticket(claims: dict = Depends(require_auth)):
    """Mint a single-use ticket for the calling session.

    Requires a valid session — an anonymous caller cannot obtain one, which is
    what closes the original hole. Role and vehicle scope are read from the
    verified token claims (server-side truth), not from the request body.
    """
    from fastapi import HTTPException

    role = claims.get("role", "operator")
    vehicle_id = claims.get("vehicle_id")

    try:
        user_id = int(claims.get("sub") or 0)
    except (TypeError, ValueError):
        user_id = 0

    try:
        value, expires_at = STORE.mint(
            user_id=user_id, email=claims.get("email", ""),
            role=role, vehicle_id=vehicle_id)
    except TicketRejected as e:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"cannot issue a ticket right now ({e.reason})")

    scope = "vehicle" if role == "driver" and vehicle_id else "fleet"
    return {
        "ticket": value,
        "expires_in": STORE.ttl_s,
        "protocol": f"{TICKET_PROTOCOL_PREFIX}{value}",
        "scope": scope,
    }


@router.websocket("/ws")
async def ws(websocket: WebSocket):
    """Authenticated fleet telemetry stream.

    Nothing — not even `hello` — is sent before a ticket is validated, so a
    rejected client cannot infer anything from the response.
    """
    raw_ticket = _ticket_from(websocket)

    # --- authenticate BEFORE accept ----------------------------------------
    try:
        if not raw_ticket:
            raise TicketRejected("missing", "no ticket presented")
        client = websocket.client
        consumer = f"{client.host}:{client.port}" if client else "?"
        ticket = STORE.consume(raw_ticket, consumer=consumer)
    except TicketRejected as e:
        # Close WITHOUT accepting: no hello, no telemetry, and no close reason
        # that leaks whether the ticket was unknown, expired or replayed.
        log.warning("ws rejected reason=%s", e.reason)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    except Exception:
        log.exception("ws ticket validation failed")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    # Echo our subprotocol so the browser's `new WebSocket(url, [proto])`
    # handshake completes; without this the client fails the protocol check and
    # the socket errors before a single frame arrives.
    selected = None
    offered = websocket.headers.get("sec-websocket-protocol") or ""
    parts = [p.strip() for p in offered.split(",")]
    if TICKET_PROTOCOL in parts:
        selected = TICKET_PROTOCOL
    elif any(p.startswith(TICKET_PROTOCOL_PREFIX) for p in parts):
        selected = f"{TICKET_PROTOCOL_PREFIX}{raw_ticket}"

    await websocket.accept(subprotocol=selected)

    q: asyncio.Queue = asyncio.Queue(maxsize=500)
    # Registered AFTER authentication, and the scope travels with the queue, so
    # no filtering decision has to re-read mutable state later.
    BROADCAST.add(q)
    try:
        await websocket.send_text(json.dumps({
            "type": "hello", "sims": list(RUNNERS), "scope": ticket.scope}))
        while True:
            msg = await q.get()
            out = _filter_frame(ticket, msg)
            if out is not None:
                await websocket.send_text(out)
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("ws stream error fp=%s", _fingerprint(raw_ticket))
    finally:
        # Always release the queue: a leaked subscriber grows the broadcast set
        # for the life of the process and every emit pays for it.
        BROADCAST.discard(q)
        log.info("ws closed fp=%s", _fingerprint(raw_ticket))


@router.get("/api/ws/status")
async def ws_status(_auth: dict = Depends(require_auth)):
    """Operational counters for the ticket store (authenticated)."""
    return {"tickets": STORE.stats(), "subscribers": len(BROADCAST.subs)}
