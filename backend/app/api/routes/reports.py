"""Reports: regenerate for any incident and download as JSON or PDF."""
import io, json
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from ...database.engine import get_db
from ...models.entities import Incident, AIAnalysis, RecommendedAction, SensorReading
from ...simulation.agents_d import ReporterAgent

router = APIRouter(prefix="/api/reports", tags=["reports"])


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


@router.get("/{iid}.json")
async def report_json(iid: int, db=Depends(get_db)):
    inc = await db.get(Incident, iid)
    if not inc: raise HTTPException(404, "incident not found")
    data = await _build_report(inc, db)
    payload = json.dumps(data, indent=2, default=str).encode()
    return Response(payload, media_type="application/json",
                    headers={"Content-Disposition": f"attachment; filename=incident-{iid}.json"})


@router.get("/{iid}.pdf")
async def report_pdf(iid: int, db=Depends(get_db)):
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
