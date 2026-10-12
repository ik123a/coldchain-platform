"""Reports: regenerate for any incident and download as JSON or PDF."""
import io, json, os
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import select
from ...core.authz import require_auth, require_auth_read
from ...core.security import create_token, decode_token
from ...database.engine import get_db
from ...models.entities import Incident, AIAnalysis, RecommendedAction, SensorReading
from ...simulation.agents_d import ReporterAgent
from ...simulation import lessons as LNS

router = APIRouter(prefix="/api/reports", tags=["reports"])

# A download ticket rides in a URL query string, so it is exposed to access logs,
# browser history and Referer headers. It must therefore be short-lived — the
# 12-hour session TTL is not appropriate for a link-borne credential.
REPORT_TICKET_TTL_S = int(os.environ.get("REPORT_TICKET_TTL_S", 300))


async def _build_report(inc: Incident, db) -> dict:
    analy = (await db.execute(select(AIAnalysis).where(AIAnalysis.incident_id == inc.id)
                              .order_by(AIAnalysis.id))).scalars().all()
    acts = (await db.execute(select(RecommendedAction).where(RecommendedAction.incident_id == inc.id))) \
        .scalars().all()
    readings = (await db.execute(select(SensorReading)
                                 .where(SensorReading.simulation_id == inc.simulation_id,
                                        SensorReading.tick >= max(0, inc.detected_tick - 10),
                                        SensorReading.tick <= (inc.resolved_tick or inc.detected_tick) + 10)
                                 .order_by(SensorReading.tick))).scalars().all()

    analyses = {a.agent_name: (json.loads(a.analysis) if a.analysis else {}) for a in analy}
    reporter = analyses.get("reporter")

    ctx = {
        "root_cause": inc.root_cause, "root_cause_confidence": inc.root_cause_confidence,
        "severity": inc.severity, "status": inc.status,
        "detected_tick": inc.detected_tick, "resolved_tick": inc.resolved_tick,
        "peak_temperature": inc.peak_temperature,
        "peak_over_by": round(max(0.0, inc.peak_temperature - 8.0), 2),
        "risk_at_peak": (analyses.get("risk") or {}).get("score", 0),
        "cargo_health": readings[-1].cargo_health if readings else 100,
        "actions_executed": [a.action for a in acts if a.status == "EXECUTED"],
        "timeline": [],  # timeline condensed below by reporter
        "root_cause_label": inc.root_cause.replace("_", " ") if inc.root_cause else "thermal excursion",
        "score_bonus": 6.0 if inc.type != "sensor_fault" else 0.0,
        "time_to_plan_ticks": 4,
        # Requirement 12: the reporter renders a Lesson line per entry, but the
        # fleet path never supplied this key, so fleet incident reports had no
        # lessons section at all — not even the empty one. Prefer the derived
        # lessons persisted at transfer time; fall back to deriving them now for
        # incidents that predate this, so no report silently loses the section.
        "lessons": (analyses.get("lessons") or {}).get("lessons") or
                   LNS.derive(
                       {"refrigeration": {"temperature": inc.peak_temperature},
                        "cargo": {"mx": 8.0, "trend_c_per_min": 0.0}},
                       analyses.get("diagnosis"),
                       {"observed": inc.status in ("RESOLVED", "ESCALATED")
                                     or "recovery_verifier" in analyses,
                        "resolved": inc.status == "RESOLVED",
                        "verified": "recovery_verifier" in analyses,
                        "peak_temperature": inc.peak_temperature}),
    }
    if reporter:
        report_text = reporter.get("report", "")
        score = reporter.get("score", 0)
        summary = reporter.get("summary", {})
    else:
        # regenerate reporter deterministically
        rep = ReporterAgent().run(ctx)
        report_text, score, summary = rep["report"], rep["score"], rep["summary"]

    return {
        "incident": {
            "id": inc.id, "simulation_id": inc.simulation_id, "type": inc.type,
            "severity": inc.severity, "status": inc.status, "detected_at": inc.detected_at.isoformat(),
            "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
            "detected_tick": inc.detected_tick, "resolved_tick": inc.resolved_tick,
            "root_cause": inc.root_cause, "root_cause_confidence": inc.root_cause_confidence,
            "peak_temperature": inc.peak_temperature,
        },
        "diagnosis": analyses.get("diagnosis"),
        "risk": analyses.get("risk"),
        "actions": [{"action": a.action, "label": a.label, "priority": a.priority, "reason": a.reason,
                     "status": a.status, "expected_effect": a.expected_effect,
                     "executed_at": a.executed_at.isoformat() if a.executed_at else None} for a in acts],
        "readings_window": [{"tick": r.tick, "t": r.temperature, "hum": r.humidity,
                             "risk": r.risk_score, "cargo": r.cargo_health,
                             "door": r.door_open, "power": r.power_ok, "batt": r.battery_level}
                            for r in readings],
        "report": {"text": report_text, "score": score, "summary": summary},
    }


def _authorize_report_read(iid: int, ticket: str | None, authorization: str | None) -> None:
    """Authorize a report read from either transport.

    WHY TWO TRANSPORTS
    ------------------
    The UI reaches these files through plain `<a href="/api/reports/1.pdf">`
    links, and a browser navigation cannot attach an `Authorization` header. So
    there are two supported ways in, and both are checked server-side:

      1. `Authorization: Bearer <token>` — for fetch()/XHR and API clients.
      2. `?ticket=<signed token>` — for link navigations. The frontend obtains
         this from `POST /api/reports/{iid}/ticket` and appends it to the href.

    The ticket is the SAME signed JWT as the bearer token, not a new weaker
    credential: same HMAC, same expiry, same claims. No new trust surface is
    introduced, and an unsigned or tampered ticket is rejected exactly like a bad
    bearer token. Both paths fail closed.

    Note the ticket may appear in server logs and browser history because it is
    in the query string; that is inherent to link-based downloads. It is
    short-lived (REPORT_TICKET_TTL_S, default 5 min) and bound to one incident,
    which bounds the window and the blast radius.
    """
    raw = None
    from_ticket = False
    if authorization and authorization.lower().startswith("bearer "):
        raw = authorization.split(None, 1)[1]
    elif ticket:
        raw = ticket
        from_ticket = True
    if not raw:
        raise HTTPException(
            401,
            "Report download requires authentication. Send an Authorization: "
            "Bearer <token> header, or fetch a ticket from "
            f"POST /api/reports/{iid}/ticket and pass it as ?ticket=<token>.",
        )
    claims = decode_token(raw)
    if not claims:
        raise HTTPException(401, "Invalid or expired token.")

    # A ticket is BOUND to one incident. Without this a ticket minted for any
    # report would download any other report the holder can name — resource
    # substitution. A full bearer token is a session credential, not a ticket,
    # so it is not resource-scoped (it authorizes the account, checked elsewhere).
    if from_ticket:
        bound = claims.get("iid")
        if bound is None:
            raise HTTPException(401, "This token is not a report ticket.")
        if int(bound) != int(iid):
            raise HTTPException(
                403,
                f"This ticket authorizes incident {bound}, not incident {iid}.",
            )
    return claims


@router.post("/{iid}/ticket")
async def report_ticket(iid: int, claims: dict = Depends(require_auth), db=Depends(get_db)):
    """Mint a download ticket for `iid` so a plain link can carry authorization.

    The ticket is a freshly-signed JWT for the SAME identity, not a bespoke
    weaker credential — one signing path, one expiry rule, one thing to audit.

    The incident must exist, so the endpoint cannot be used to probe which ids
    are valid without a token in the first place.
    """
    inc = await db.get(Incident, iid)
    if not inc:
        raise HTTPException(404, "incident not found")
    # SHORT-LIVED and RESOURCE-BOUND. The session token lives 12h, which is far too
    # long for a credential that rides in a URL (logs, history, Referer). 5 minutes
    # is enough for a click-through download, and `iid` makes the ticket useless
    # for any other report.
    ticket = create_token(
        int(claims["sub"]) if str(claims.get("sub", "")).isdigit() else 0,
        claims.get("email", ""),
        claims.get("role", "operator"),
        claims.get("vehicle_id"),
        ttl_seconds=REPORT_TICKET_TTL_S,
        extra={"iid": iid, "typ": "report_ticket"},
    )
    return {"iid": iid, "ticket": ticket, "expires_in": REPORT_TICKET_TTL_S}


@router.get("/{iid}.json")
async def report_json(iid: int, ticket: str | None = Query(None),
                      authorization: str | None = Header(None), db=Depends(get_db)):
    _authorize_report_read(iid, ticket, authorization)
    inc = await db.get(Incident, iid)
    if not inc: raise HTTPException(404, "incident not found")
    data = await _build_report(inc, db)
    payload = json.dumps(data, indent=2, default=str).encode()
    return Response(payload, media_type="application/json",
                    headers={"Content-Disposition": f"attachment; filename=incident-{iid}.json"})


@router.get("/{iid}.pdf")
async def report_pdf(iid: int, ticket: str | None = Query(None),
                     authorization: str | None = Header(None), db=Depends(get_db)):
    _authorize_report_read(iid, ticket, authorization)
    inc = await db.get(Incident, iid)
    if not inc: raise HTTPException(404, "incident not found")
    data = await _build_report(inc, db)

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"ColdChain Incident #{iid}")
    st = getSampleStyleSheet()
    h1 = ParagraphStyle("h1c", parent=st["Heading1"], textColor=colors.HexColor("#0B2545"), spaceAfter=8)
    h2 = ParagraphStyle("h2c", parent=st["Heading2"], textColor=colors.HexColor("#13315C"), spaceAfter=4)
    body = ParagraphStyle("b", parent=st["BodyText"], leading=14)
    small = ParagraphStyle("s", parent=st["BodyText"], fontSize=8, leading=11, textColor=colors.HexColor("#334"))

    parts = [
        Paragraph("COLDCHAIN RESCUE — Incident Report", h1),
        Paragraph(f"Incident #{data['incident']['id']} · SIMULATION MODE · Generated deterministically from stored evidence", small),
        Spacer(1, 8),
    ]
    key_table = [
        ["Severity", data["incident"]["severity"], "Status", data["incident"]["status"]],
        ["Type", data["incident"]["type"], "Root cause", str(data["incident"]["root_cause"])],
        ["Peak temp", f"{data['incident']['peak_temperature']} °C",
         "Root cause conf", f"{data['incident']['root_cause_confidence']}"],
        ["Detected @ tick", str(data["incident"]["detected_tick"]),
         "Resolved @ tick", str(data["incident"]["resolved_tick"])],
        ["Detected at", data["incident"]["detected_at"],
         "Response score", str(data["report"]["score"])],
    ]
    t = Table(key_table, colWidths=[90, 200, 90, 140])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2F7")),
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8.5),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C6D0DF")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    parts.append(t)
    parts.append(Spacer(1, 8))

    if data["diagnosis"]:
        parts.append(Paragraph("Diagnosis", h2))
        alt = "; ".join(f"{a['cause']} ({a['probability']})" for a in data["diagnosis"].get("alternatives", []))
        parts.append(Paragraph(f"Root cause: <b>{data['diagnosis'].get('root_cause')}</b> "
                               f" — confidence {data['diagnosis'].get('confidence')} "
                               f" — reasoning: {data['diagnosis'].get('reasoning', '')}", body))
        parts.append(Paragraph(f"Alternatives: {alt}", body))
        parts.append(Spacer(1, 4))
    if data["risk"]:
        parts.append(Paragraph("Risk analysis", h2))
        parts.append(Paragraph(f"Score: <b>{data['risk'].get('score')}/100 ({data['risk'].get('level')})</b> "
                               f" — explain: {data['risk'].get('explain', '')}", body))
        parts.append(Spacer(1, 4))
    if data["actions"]:
        parts.append(Paragraph("Response plan", h2))
        items = [ListItem(Paragraph(
            f"<b>{a['label']}</b> [{a['priority']}] — {a['reason']} — status {a['status']}", body))
            for a in data["actions"]]
        parts.append(ListFlowable(items, bulletType="bullet"))
        parts.append(Spacer(1, 4))

    if data["readings_window"]:
        parts.append(Paragraph("Sensor window (around incident)", h2))
        rows = [["tick", "temp", "hum", "risk", "cargo", "door", "power"]]
        for r in data["readings_window"][-14:]:
            rows.append([str(r["tick"]), str(r["t"]), str(r["hum"]), str(r["risk"]),
                         str(r["cargo"]), "OPEN" if r["door"] else "--", "OK" if r["power"] else "BATTERIES"])
        tbl = Table(rows, colWidths=[45, 60, 56, 58, 62, 58, 62])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2F7")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C6D0DF")),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
            ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), 3),
        ]))
        parts.append(tbl)
        parts.append(Spacer(1, 8))

    parts.append(Paragraph("Reporter output", h2))
    for line in (data["report"]["text"] or "").split("\n"):
        parts.append(Paragraph(line.replace("<", "&lt;").replace(">", "&gt;"), body))

    doc.build(parts)
    buf.seek(0)
    return Response(buf.read(), media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=incident-{iid}.pdf"})
