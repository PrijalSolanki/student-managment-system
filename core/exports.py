"""Export helpers: CSV, Excel (.xlsx) and PDF.

Excel and PDF support degrade gracefully when the optional third party
libraries are not installed - the caller receives a clear message instead of
an exception.
"""

from __future__ import annotations

import logging
from typing import Iterable, Sequence

from django.http import HttpResponse

from core.utils import filename_timestamp, rows_to_csv

logger = logging.getLogger("sms.export")

try:  # pragma: no cover - optional dependency
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    OPENPYXL_AVAILABLE = True
except ImportError:  # pragma: no cover
    OPENPYXL_AVAILABLE = False

try:  # pragma: no cover - optional dependency
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    REPORTLAB_AVAILABLE = True
except ImportError:  # pragma: no cover
    REPORTLAB_AVAILABLE = False


HEADER_FILL = PatternFill("solid", fgColor="1F3C88") if OPENPYXL_AVAILABLE else None


class ExportError(Exception):
    """Raised when an export format cannot be produced."""


def export_csv(filename_prefix: str, headers: Sequence[str], rows: Iterable[Sequence]) -> HttpResponse:
    payload = rows_to_csv(headers, rows)
    response = HttpResponse(payload, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="{filename_timestamp(filename_prefix, "csv")}"'
    )
    return response


def export_excel(
    filename_prefix: str,
    headers: Sequence[str],
    rows: Iterable[Sequence],
    sheet_title: str = "Report",
    meta: Sequence[tuple] | None = None,
) -> HttpResponse:
    if not OPENPYXL_AVAILABLE:  # pragma: no cover
        raise ExportError(
            "Excel export needs the 'openpyxl' package. "
            "Install it with: pip install openpyxl"
        )
    rows = [list(row) for row in rows]
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = (sheet_title or "Report")[:31]

    row_offset = 1
    if meta:
        for label, value in meta:
            sheet.cell(row=row_offset, column=1, value=str(label)).font = Font(bold=True)
            sheet.cell(row=row_offset, column=2, value=str(value))
            row_offset += 1
        row_offset += 1

    header_row = row_offset
    for column, header in enumerate(headers, start=1):
        cell = sheet.cell(row=header_row, column=column, value=str(header))
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for index, row in enumerate(rows, start=header_row + 1):
        for column, value in enumerate(row, start=1):
            sheet.cell(row=index, column=column, value="" if value is None else value)

    widths = []
    for column in range(1, len(list(headers)) + 1):
        longest = 10
        for row in rows[:200]:
            value = row[column - 1] if column - 1 < len(row) else ""
            longest = max(longest, len(str(value or "")))
        widths.append(min(max(longest + 2, 12), 45))
        sheet.column_dimensions[get_column_letter(column)].width = widths[-1]

    sheet.freeze_panes = sheet.cell(row=header_row + 1, column=1)
    sheet.auto_filter.ref = (
        f"A{header_row}:{get_column_letter(len(list(headers)))}{header_row + len(rows)}"
    )

    import io

    stream = io.BytesIO()
    workbook.save(stream)
    payload = stream.getvalue()
    response = HttpResponse(
        payload,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{filename_timestamp(filename_prefix, "xlsx")}"'
    )
    return response


def export_pdf(
    filename_prefix: str,
    headers: Sequence[str],
    rows: Iterable[Sequence],
    title: str = "Report",
    meta: Sequence[tuple] | None = None,
    landscape_mode: bool = True,
) -> HttpResponse:
    if not REPORTLAB_AVAILABLE:  # pragma: no cover
        raise ExportError(
            "PDF export needs the 'reportlab' package. "
            "Install it with: pip install reportlab"
        )
    rows = [[("" if cell is None else str(cell))[:60] for cell in row] for row in rows]
    headers = [str(header) for header in headers]

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SMSReportTitle", parent=styles["Heading2"], fontSize=15, spaceAfter=6
    )
    meta_style = ParagraphStyle("SMSReportMeta", parent=styles["Normal"], fontSize=9)

    buffer = _pdf_buffer()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4) if landscape_mode else A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=title,
    )
    story = [Paragraph(title, title_style)]
    if meta:
        story.append(
            Paragraph(" &nbsp;&nbsp;|&nbsp;&nbsp; ".join(f"<b>{k}:</b> {v}" for k, v in meta), meta_style)
        )
        story.append(Spacer(1, 6 * mm))

    table_data = [headers] + rows
    table = Table(table_data, repeatRows=1, hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3c88")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9d1e0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6fb")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    table.setStyle(TableStyle(style))
    story.append(table)
    document.build(story)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{filename_timestamp(filename_prefix, "pdf")}"'
    )
    return response


def _pdf_buffer():
    import io

    return io.BytesIO()


def export_data(
    request,
    filename_prefix: str,
    headers: Sequence[str],
    rows: Iterable[Sequence],
    default: str = "xlsx",
    title: str = "Report",
    meta: Sequence[tuple] | None = None,
) -> HttpResponse:
    """Dispatch to the requested export format (``?format=csv|xlsx|pdf``)."""
    export_format = (request.GET.get("format") or default).strip().lower()
    rows = [list(row) for row in rows]
    if export_format in {"csv", "excel-csv"}:
        return export_csv(filename_prefix, headers, rows)
    if export_format in {"xlsx", "excel", "xls"}:
        return export_excel(filename_prefix, headers, rows, sheet_title=title, meta=meta)
    if export_format == "pdf":
        return export_pdf(filename_prefix, headers, rows, title=title, meta=meta)
    raise ExportError(f"Unsupported export format '{export_format}'.")
