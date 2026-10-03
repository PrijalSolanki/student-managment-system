from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.models import AuditLog
from core.permissions import log_action, staff_required
from core.utils import paginate, parse_date
from reports.services import (
    academic_summary,
    admission_trend,
    attendance_by_department,
    attendance_summary,
    defaulters,
    enrollment_summary,
    everything,
    fee_snapshot,
    performance_summary,
    teacher_snapshot,
    toppers_report,
)


def _export(request, filename_prefix, headers, rows, title, meta=None):
    from core.exports import ExportError, export_data

    try:
        response = export_data(
            request,
            filename_prefix,
            headers,
            rows,
            title=title,
            meta=meta,
        )
    except ExportError as exc:
        messages.error(request, str(exc))
        return redirect(request.path)
    log_action(
        request,
        AuditLog.Action.EXPORT,
        module="reports",
        description=f"Exported {title} ({len(rows)} rows)",
    )
    return response


@staff_required
def report_index(request):
    """Landing page listing every available report."""
    cards = [
        {
            "key": "enrollment",
            "title": "Enrollment Report",
            "description": "Students by department, course, semester, status and gender.",
            "url": "/reports/enrollment/",
            "icon": "bi-people",
            "color": "primary",
        },
        {
            "key": "attendance",
            "title": "Attendance Report",
            "description": "Attendance percentages overall, by department and daily trend.",
            "url": "/reports/attendance/",
            "icon": "bi-calendar-check",
            "color": "success",
        },
        {
            "key": "performance",
            "title": "Performance Report",
            "description": "Exam results, grade distribution and toppers.",
            "url": "/reports/performance/",
            "icon": "bi-award",
            "color": "warning",
        },
        {
            "key": "fees",
            "title": "Fee Report",
            "description": "Billed, collected, pending and overdue amounts.",
            "url": "/reports/fees/",
            "icon": "bi-cash-coin",
            "color": "info",
        },
        {
            "key": "teachers",
            "title": "Teacher Report",
            "description": "Teacher strength, payroll and subject workload.",
            "url": "/reports/teachers/",
            "icon": "bi-person-badge",
            "color": "secondary",
        },
        {
            "key": "overview",
            "title": "Complete Overview",
            "description": "Every report combined into a printable summary.",
            "url": "/reports/overview/",
            "icon": "bi-clipboard-data",
            "color": "dark",
        },
    ]
    return render(
        request,
        "reports/report_index.html",
        {
            "cards": cards,
            "page_title": "Reports & Analytics",
            "active_menu": "reports",
            "quick_stats": {
                "enrollment": enrollment_summary()["total"],
                "attendance": attendance_summary()["percentage"],
                "performance": performance_summary()["pass_percentage"],
                "fees": fee_snapshot()["collection_percentage"],
            },
        },
    )


@require_GET
@staff_required
def enrollment_report(request):
    summary = enrollment_summary()
    trend = admission_trend()
    headers = ["Department", "Students", "Active", "Share %"]
    total = summary["total"] or 1
    rows = [
        [row.name, row.total, row.active, round((row.total / total) * 100, 2)]
        for row in summary["by_department"]
    ]
    rows.append(["TOTAL", summary["total"], summary["active"], 100.0])
    if request.GET.get("format"):
        return _export(
            request,
            "enrollment_report",
            headers,
            rows,
            "Enrollment Report",
            meta=[("Generated", timezone.localtime().strftime("%Y-%m-%d %H:%M"))],
        )

    return render(
        request,
        "reports/enrollment_report.html",
        {
            "summary": summary,
            "trend": trend,
            "page_title": "Enrollment Report",
            "active_menu": "reports",
        },
    )


@require_GET
@staff_required
def attendance_report(request):
    start = parse_date(request.GET.get("date_from"))
    end = parse_date(request.GET.get("date_to"))
    summary = attendance_summary(start, end)
    departments = attendance_by_department()
    low_attendance = defaulters()

    headers = ["Department", "Total", "Present", "Absent", "Leave", "Percentage %"]
    rows = [
        [row["department"], row["total"], row["present"], row["absent"], row["leave"], row["percentage"]]
        for row in departments
    ]
    if request.GET.get("format"):
        return _export(
            request,
            "attendance_report",
            headers,
            rows,
            "Attendance Report",
            meta=[
                ("Period", f"{start or 'All time'} to {end or 'today'}"),
                ("Overall %", summary["percentage"]),
            ],
        )

    return render(
        request,
        "reports/attendance_report.html",
        {
            "summary": summary,
            "departments": departments,
            "low_attendance": low_attendance,
            "start": start,
            "end": end,
            "page_title": "Attendance Report",
            "active_menu": "reports",
        },
    )


@require_GET
@staff_required
def performance_report(request):
    summary = performance_summary()
    toppers = toppers_report()
    headers = ["Rank", "Student", "Student ID", "Course", "Exam", "Total", "Max", "%", "Grade"]
    rows = [
        [
            index,
            entry["student"].full_name,
            entry["student"].student_id,
            entry["student"].course.name if entry["student"].course_id else "-",
            entry["exam"].code,
            entry["result"].total_marks,
            entry["result"].max_marks,
            entry["percentage"],
            entry["grade"],
        ]
        for index, entry in enumerate(toppers, start=1)
    ]
    if request.GET.get("format"):
        return _export(
            request,
            "performance_report",
            headers,
            rows,
            "Performance Report",
            meta=[("Average %", summary["average_percentage"])],
        )

    return render(
        request,
        "reports/performance_report.html",
        {
            "summary": summary,
            "toppers": toppers,
            "page_title": "Performance Report",
            "active_menu": "reports",
        },
    )


@require_GET
@staff_required
def fee_report(request):
    summary = fee_snapshot()
    from fees.services import collection_by_method

    methods = collection_by_method(
        parse_date(request.GET.get("date_from")), parse_date(request.GET.get("date_to"))
    )
    headers = ["Method", "Transactions", "Amount"]
    rows = [[item["method_display"], item["count"], item["total"]] for item in methods]
    if request.GET.get("format"):
        return _export(request, "fee_report", headers, rows, "Fee Report")

    return render(
        request,
        "reports/fee_report.html",
        {
            "summary": summary,
            "methods": methods,
            "page_title": "Fee Report",
            "active_menu": "reports",
        },
    )


@require_GET
@staff_required
def teacher_report(request):
    summary = teacher_snapshot()
    academics = academic_summary()
    headers = ["Employee ID", "Teacher", "Subjects"]
    rows = [[row["teacher_id"], row["name"], row["subjects"]] for row in summary["workload"]]
    if request.GET.get("format"):
        return _export(request, "teacher_report", headers, rows, "Teacher Report")

    return render(
        request,
        "reports/teacher_report.html",
        {
            "summary": summary,
            "academics": academics,
            "page_title": "Teacher Report",
            "active_menu": "reports",
        },
    )


@require_GET
@staff_required
def overview_report(request):
    data = everything()
    page = paginate(request, data["enrollment"]["by_department"], per_page=15)
    return render(
        request,
        "reports/overview_report.html",
        {
            "data": data,
            "page_title": "Complete Overview",
            "active_menu": "reports",
            "departments": page.object_list,
            "page_obj": page,
            "paginator": page.paginator,
            "is_paginated": page.has_other_pages(),
            "page_number": page.number,
        },
    )


@require_GET
@staff_required
def defaulters_report(request):
    rows = defaulters(limit=50, threshold=float(request.GET.get("threshold") or 75))
    headers = ["Student ID", "Name", "Course", "Total Classes", "Present", "Absent", "Attendance %"]
    export_rows = [
        [row["student_id"], row["name"], row["course"], row["total"], row["present"], row["absent"], row["percentage"]]
        for row in rows
    ]
    if request.GET.get("format"):
        return _export(request, "attendance_defaulters", headers, export_rows, "Attendance Defaulters")
    return render(
        request,
        "reports/defaulters_report.html",
        {
            "rows": rows,
            "threshold": request.GET.get("threshold") or 75,
            "page_title": "Low Attendance",
            "active_menu": "reports",
        },
    )


__all__ = [
    "report_index",
    "enrollment_report",
    "attendance_report",
    "performance_report",
    "fee_report",
    "teacher_report",
    "overview_report",
    "defaulters_report",
]