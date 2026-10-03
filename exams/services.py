"""Grading, mark validation and result calculation."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

GRADE_SCALE = [
    {"grade": "A+", "min": 90, "max": 100, "point": Decimal("5.00"), "description": "Outstanding"},
    {"grade": "A", "min": 80, "max": 89.99, "point": Decimal("4.50"), "description": "Excellent"},
    {"grade": "B+", "min": 70, "max": 79.99, "point": Decimal("4.00"), "description": "Very Good"},
    {"grade": "B", "min": 60, "max": 69.99, "point": Decimal("3.50"), "description": "Good"},
    {"grade": "C", "min": 50, "max": 59.99, "point": Decimal("3.00"), "description": "Average"},
    {"grade": "D", "min": 40, "max": 49.99, "point": Decimal("2.00"), "description": "Below Average"},
    {"grade": "F", "min": 0, "max": 39.99, "point": Decimal("0.00"), "description": "Fail"},
]


def calculate_grade(percentage) -> dict:
    """Return the grade band for a percentage."""
    try:
        value = float(percentage or 0)
    except (TypeError, ValueError):
        value = 0.0
    for band in GRADE_SCALE:
        if value >= band["min"]:
            return band
    return GRADE_SCALE[-1]


def grade_description(grade: str) -> str:
    for band in GRADE_SCALE:
        if band["grade"] == grade:
            return band["description"]
    return "-"


def grade_point(grade: str) -> Decimal:
    for band in GRADE_SCALE:
        if band["grade"] == grade:
            return band["point"]
    return Decimal("0.00")


def exam_students(exam):
    """Students eligible to write the exam (same course & semester)."""
    from students.models import Student

    return Student.objects.filter(
        course=exam.course, semester=exam.semester, status=Student.Status.ACTIVE
    ).with_details()


@transaction.atomic
def recalculate_result(exam, student) -> dict:
    """(Re)compute and persist the :class:`~exams.models.Result` for a student."""
    from exams.models import MarkEntry, Result

    entries = list(
        MarkEntry.objects.filter(exam=exam, student=student).select_related("exam_subject")
    )
    exam_subjects = list(exam.exam_subjects.all())

    if not exam_subjects:
        return {"created": 0, "updated": 0, "skipped": 1}

    by_subject = {entry.exam_subject_id: entry for entry in entries}
    total_marks = Decimal("0")
    max_marks = Decimal("0")
    failed = 0
    absent = 0

    for exam_subject in exam_subjects:
        max_marks += Decimal(str(exam_subject.max_marks))
        entry = by_subject.get(exam_subject.pk)
        if entry is None or entry.marks_obtained is None:
            absent += 1
            continue
        if entry.is_absent:
            absent += 1
            continue
        obtained = Decimal(str(entry.marks_obtained))
        total_marks += obtained
        if obtained < Decimal(str(exam_subject.pass_marks)):
            failed += 1

    percentage = Decimal("0")
    if max_marks > 0:
        percentage = (total_marks / max_marks * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    band = calculate_grade(percentage)
    is_pass = failed == 0 and absent == 0 and percentage >= Decimal(str(exam.passing_percentage))

    result, created = Result.objects.update_or_create(
        exam=exam,
        student=student,
        defaults={
            "total_marks": total_marks,
            "max_marks": max_marks,
            "percentage": percentage,
            "grade": band["grade"],
            "grade_point": band["point"],
            "is_pass": is_pass,
            "failed_subjects": failed,
            "absent_subjects": absent,
        },
    )
    # Keep the exam header totals in sync.
    exam.total_marks = max_marks
    exam.passing_marks = (max_marks * Decimal(str(exam.passing_percentage)) / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    exam.save(update_fields=["total_marks", "passing_marks", "updated_at"])
    return {"created": 1 if created else 0, "updated": 0 if created else 1, "skipped": 0, "result": result}


def recalculate_exam_results(exam, students=None) -> dict:
    """Recompute results for every eligible student of an exam."""
    students = students if students is not None else exam_students(exam)
    summary = {"created": 0, "updated": 0, "skipped": 0, "students": 0}
    for student in students:
        outcome = recalculate_result(exam, student)
        summary["created"] += outcome["created"]
        summary["updated"] += outcome["updated"]
        summary["skipped"] += outcome["skipped"]
        summary["students"] += 1
    return summary


def result_sheet(exam, student) -> list[dict]:
    """Subject-wise marks rows used by the marksheet / result detail page."""
    from exams.models import MarkEntry

    entries = {
        entry.exam_subject_id: entry
        for entry in MarkEntry.objects.filter(exam=exam, student=student).select_related(
            "exam_subject"
        )
    }
    rows = []
    for exam_subject in exam.exam_subjects.select_related("subject"):
        entry = entries.get(exam_subject.pk)
        obtained = None
        is_absent = False
        if entry:
            obtained = entry.marks_obtained
            is_absent = entry.is_absent
        max_marks = Decimal(str(exam_subject.max_marks))
        pass_marks = Decimal(str(exam_subject.pass_marks))
        percentage = (
            round((float(obtained) / float(max_marks)) * 100, 2)
            if obtained is not None and max_marks and not is_absent
            else 0.0
        )
        band = calculate_grade(percentage) if obtained is not None else None
        subject_pass = bool(
            obtained is not None and not is_absent and Decimal(str(obtained)) >= pass_marks
        )
        rows.append(
            {
                "exam_subject": exam_subject,
                "subject": exam_subject.subject,
                "max_marks": max_marks,
                "pass_marks": pass_marks,
                "obtained": obtained,
                "is_absent": is_absent,
                "percentage": percentage,
                "grade": band["grade"] if band else "-",
                "is_pass": subject_pass,
                "credits": exam_subject.subject.credits,
                "remarks": entry.remarks if entry else "",
            }
        )
    return rows


def exam_progress(exam) -> dict:
    """How many marks have been entered for this exam."""
    from exams.models import MarkEntry

    subjects = exam.exam_subjects.count()
    students = exam_students(exam).count()
    expected = subjects * students
    entered = MarkEntry.objects.filter(exam=exam).exclude(marks_obtained=None).count()
    absent_marked = MarkEntry.objects.filter(exam=exam, is_absent=True).count()
    return {
        "subjects": subjects,
        "students": students,
        "expected": expected,
        "entered": entered,
        "absent_marked": absent_marked,
        "percentage": round((entered / expected) * 100, 2) if expected else 0.0,
    }


def overall_percentage(student) -> float:
    from django.db.models import Avg

    from exams.models import Result

    average = Result.objects.filter(student=student).aggregate(value=Avg("percentage"))["value"]
    return round(float(average or 0), 2)


def rank_of_student(exam, student) -> int:
    """Rank (1 = highest percentage) of a student inside an exam."""
    from exams.models import Result

    own = (
        Result.objects.filter(exam=exam, student=student)
        .values_list("percentage", flat=True)
        .first()
    )
    if own is None:
        return 0
    return Result.objects.filter(exam=exam, percentage__gt=own).count() + 1
