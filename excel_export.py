"""Excel export of a completed onboarding intake."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

import interview

HEADER_FILL = PatternFill("solid", fgColor="1F3A5F")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
SECTION_FILL = PatternFill("solid", fgColor="E8ECF1")
TITLE_FONT = Font(bold=True, size=14)
WRAP_TOP = Alignment(wrap_text=True, vertical="top")
THIN = Side(style="thin", color="D0D5DB")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _style_header(ws: Worksheet, widths: list[int]) -> None:
    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 22
    for index, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def _finish(ws: Worksheet) -> None:
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = WRAP_TOP
            cell.border = BORDER


def _answer_sheet(
    wb: Workbook,
    title: str,
    schema: dict[str, Any],
    state: dict[str, Any],
    audience: str,
) -> None:
    by_id = {s["id"]: s for s in schema["slots"]}
    sections = {s["id"]: s["name"] for s in schema["sections"]}

    rows = [
        (by_id[sid], entry)
        for sid, entry in state["answers"].items()
        if by_id[sid]["audience"] == audience
    ]
    if not rows:
        return

    order = {s["id"]: i for i, s in enumerate(schema["sections"])}
    rows.sort(key=lambda r: order.get(r[0]["section"], 99))

    ws = wb.create_sheet(title)
    ws.append(["Section", "Question", "Answer", "Flagged for review"])
    for slot, entry in rows:
        ws.append(
            [
                sections[slot["section"]],
                slot["question"],
                interview.render(entry["value"]),
                entry.get("review", ""),
            ]
        )
    _style_header(ws, [26, 58, 60, 44])
    _finish(ws)


def build(schema: dict[str, Any], state: dict[str, Any]) -> bytes:
    by_id = {s["id"]: s for s in schema["slots"]}
    sections = {s["id"]: s["name"] for s in schema["sections"]}

    wb = Workbook()
    summary = wb.active
    summary.title = "Summary"

    submitted = state.get("submitted_at", "")
    summary.append(["ISC Source Onboarding Requirements"])
    summary["A1"].font = TITLE_FONT
    summary.append([])
    meta = [
        ("Application", state["name"]),
        ("Reference", state["slug"]),
        ("Intake started", state.get("created", "")),
        ("Submitted", submitted or "not submitted"),
        ("Exported", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")),
        ("Schema version", schema.get("version", "")),
    ]
    for label, value in meta:
        summary.append([label, value])

    summary.append([])
    summary.append(["Audience", "Answered", "Outstanding"])
    header_row = summary.max_row
    for audience, label in schema["audiences"].items():
        answered = sum(
            1 for sid in state["answers"] if by_id[sid]["audience"] == audience
        )
        summary.append(
            [label, answered, len(interview.pending(schema, state, audience))]
        )
    summary.append(["Flagged for follow-up", len(state["open_questions"])])

    for cell in summary[header_row]:
        cell.fill = SECTION_FILL
        cell.font = Font(bold=True)
    for row in summary.iter_rows(min_row=3, max_row=3 + len(meta) - 1, max_col=1):
        row[0].font = Font(bold=True)
    summary.column_dimensions["A"].width = 26
    summary.column_dimensions["B"].width = 46
    summary.column_dimensions["C"].width = 16

    _answer_sheet(wb, "Intake", schema, state, "owner")
    _answer_sheet(wb, "ISC Design", schema, state, "iam")

    if state["open_questions"]:
        ws = wb.create_sheet("Open questions")
        ws.append(["Section", "Question", "Who will follow up"])
        for sid, item in state["open_questions"].items():
            ws.append(
                [
                    sections[by_id[sid]["section"]],
                    by_id[sid]["question"],
                    item.get("reason", "") or "unassigned",
                ]
            )
        _style_header(ws, [26, 62, 38])
        _finish(ws)

    gaps = [
        s
        for s in interview.pending(schema, state, "owner")
        if s.get("required")
    ]
    if gaps:
        ws = wb.create_sheet("Not answered")
        ws.append(["Section", "Question"])
        for slot in gaps:
            ws.append([sections[slot["section"]], slot["question"]])
        _style_header(ws, [26, 70])
        _finish(ws)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
