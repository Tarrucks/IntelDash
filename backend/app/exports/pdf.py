"""PDF export for the Analyst Case File.

ReportLab "Platypus" flow layout — boring, deterministic, no native
deps. The output is intentionally information-dense rather than
brochure-pretty: this is an investigator's hand-off document, not a
marketing piece.

Layout:
  Header  case title / status / dates / owner
  Summary if present
  Pins    one row per pin (kind chip, label, ref_id, pinned_at, notes,
          relevant extras like lat/lon or vessel-type)
  Footer  case UUID + "Aperture v0.1.0" + page number
"""

from __future__ import annotations

import io
from datetime import UTC, datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.entities import Case, User

# Aperture-flavoured palette (matches the frontend Tailwind tokens).
PALETTE = {
    "bg": colors.HexColor("#0f172a"),
    "panel": colors.HexColor("#1e293b"),
    "border": colors.HexColor("#334155"),
    "fg": colors.HexColor("#1e293b"),
    "muted": colors.HexColor("#64748b"),
    "accent": colors.HexColor("#0ea5e9"),
    "kind_vessel": colors.HexColor("#38bdf8"),
    "kind_aircraft": colors.HexColor("#fbbf24"),
    "kind_host": colors.HexColor("#c084fc"),
    "kind_url": colors.HexColor("#10b981"),
    "kind_domain": colors.HexColor("#10b981"),
}


def _kind_colour(kind: str) -> colors.Color:
    return PALETTE.get(f"kind_{kind}", colors.HexColor("#94a3b8"))


def _fmt_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontSize=22,
            leading=26,
            textColor=PALETTE["fg"],
            spaceAfter=8,
        ),
        "muted": ParagraphStyle(
            "muted",
            parent=base["BodyText"],
            fontSize=9,
            textColor=PALETTE["muted"],
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            textColor=PALETTE["fg"],
            spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontSize=13,
            textColor=PALETTE["fg"],
            spaceBefore=10,
            spaceAfter=6,
        ),
        "kindchip": ParagraphStyle(
            "kindchip",
            parent=base["BodyText"],
            fontSize=8,
            fontName="Courier-Bold",
            textColor=colors.white,
            alignment=TA_LEFT,
            leading=10,
        ),
        "mono": ParagraphStyle(
            "mono",
            parent=base["BodyText"],
            fontSize=9,
            fontName="Courier",
            textColor=PALETTE["fg"],
            leading=11,
        ),
    }


def _header_block(case: Case, owner: User | None, st: dict) -> list:
    flow: list = []
    flow.append(Paragraph(case.title, st["title"]))

    bits = [
        f"<b>Status</b>&nbsp;{case.status.value}",
        f"<b>Pins</b>&nbsp;{len(case.pins)}",
        f"<b>Created</b>&nbsp;{_fmt_dt(case.created_at)}",
        f"<b>Updated</b>&nbsp;{_fmt_dt(case.updated_at)}",
    ]
    if owner:
        bits.insert(0, f"<b>Owner</b>&nbsp;{owner.email}")
    flow.append(Paragraph(" &nbsp;&middot;&nbsp; ".join(bits), st["muted"]))

    if case.summary:
        flow.append(Spacer(1, 0.15 * inch))
        flow.append(Paragraph("<b>Summary</b>", st["h2"]))
        flow.append(Paragraph(case.summary, st["body"]))

    return flow


def _pins_table(case: Case, st: dict) -> list:
    flow: list = []
    flow.append(Paragraph("<b>Pinned Entities</b>", st["h2"]))

    if not case.pins:
        flow.append(Paragraph("<i>No pins yet.</i>", st["muted"]))
        return flow

    rows = [["Kind", "Label / Ref ID", "Pinned", "Notes"]]
    for p in sorted(case.pins, key=lambda x: x.pinned_at):
        kind_para = Paragraph(p.entity.kind.upper(), st["kindchip"])
        label_text = (
            f"<b>{_escape(p.entity.label)}</b><br/>"
            f"<font name='Courier' size='8' color='#64748b'>"
            f"{_escape(p.entity.ref_id)}"
            f"</font>"
        )
        extras = _extras_summary(p.entity.extra or {})
        if extras:
            label_text += f"<br/><font size='8' color='#64748b'>{_escape(extras)}</font>"
        rows.append(
            [
                kind_para,
                Paragraph(label_text, st["body"]),
                Paragraph(_fmt_dt(p.pinned_at), st["mono"]),
                Paragraph(_escape(p.notes or ""), st["body"]),
            ]
        )

    table = Table(
        rows,
        colWidths=[0.7 * inch, 3.0 * inch, 1.3 * inch, 2.2 * inch],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PALETTE["panel"]),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, PALETTE["border"]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 1), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
            ]
            + [
                # Row-by-row kind-chip background colour.
                (
                    "BACKGROUND",
                    (0, idx),
                    (0, idx),
                    (
                        _kind_colour(case.pins_sorted[idx - 1].entity.kind)
                        if hasattr(case, "pins_sorted")
                        else _kind_colour(
                            sorted(case.pins, key=lambda x: x.pinned_at)[idx - 1].entity.kind
                        )
                    ),
                )
                for idx in range(1, len(rows))
            ]
        )
    )
    flow.append(table)
    return flow


def _extras_summary(extra: dict) -> str:
    """Pull a few high-signal fields out of an entity's ``extra`` blob.

    We avoid dumping the whole jsonb — much of it is verbose Shodan
    payload — and surface only fields the analyst usually wants to see
    on the printed page.
    """
    keys = ("lat", "lon", "imo", "vessel_type", "type", "registration", "country")
    bits = []
    for k in keys:
        v = extra.get(k)
        if v in (None, "", []):
            continue
        bits.append(f"{k}={v}")
    return " · ".join(bits)


def _escape(s: str | None) -> str:
    if not s:
        return ""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _footer(canvas, doc, *, case_id: str):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(PALETTE["muted"])
    width, _height = LETTER
    text = f"Aperture v0.1.0  ·  case {case_id}  ·  page {doc.page}"
    canvas.drawRightString(width - 0.5 * inch, 0.4 * inch, text)
    canvas.restoreState()


def render_case_pdf(case: Case, owner: User | None) -> bytes:
    """Render a ``Case`` to PDF bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.6 * inch,
        title=f"Aperture — {case.title}",
        author=(owner.email if owner else "aperture"),
    )
    st = _styles()
    flow = []
    flow.extend(_header_block(case, owner, st))
    flow.extend(_pins_table(case, st))

    case_id = str(case.id)

    def on_page(canvas, doc):
        _footer(canvas, doc, case_id=case_id)

    doc.build(flow, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()
