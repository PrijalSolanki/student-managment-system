"""Small, dependency free helpers shared across the project."""

from __future__ import annotations

import calendar
import csv
import datetime as dt
import io
import os
import uuid
from typing import Any, Iterable, Sequence

from django.conf import settings
from django.core.paginator import EmptyPage, Paginator
from django.utils import timezone
from django.utils.text import slugify


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
def paginate(request, queryset, per_page=None, page_param="page"):
    """Return a Django ``Page`` using project defaults + sane bounds."""
    sms = getattr(settings, "SMS", {})
    default_per_page = per_page or sms.get("DEFAULT_PER_PAGE", 10)
    try:
        default_per_page = int(default_per_page)
    except (TypeError, ValueError):
        default_per_page = 10
    max_per_page = int(sms.get("MAX_PER_PAGE", 100))
    default_per_page = max(1, min(default_per_page, max_per_page))

    paginator = Paginator(queryset, default_per_page)
    raw = request.GET.get(page_param) or request.POST.get(page_param) or 1
    try:
        page_number = int(raw)
    except (TypeError, ValueError):
        page_number = 1
    try:
        page = paginator.page(page_number)
    except EmptyPage:
        page = paginator.page(paginator.num_pages if paginator.num_pages else 1)
    return page


def querystring_without_page(request) -> str:
    params = request.GET.copy()
    params.pop("page", None)
    encoded = params.urlencode()
    return f"&{encoded}" if encoded else ""


def build_query_string(params: dict) -> str:
    cleaned = {k: v for k, v in params.items() if v not in (None, "", "all")}
    from django.utils.http import urlencode

    return urlencode(cleaned)


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------
def today():
    return timezone.localdate()


def now():
    return timezone.localtime() if timezone.is_aware(timezone.now()) else timezone.now()


def month_bounds(year: int, month: int) -> tuple[dt.date, dt.date]:
    last_day = calendar.monthrange(int(year), int(month))[1]
    return dt.date(int(year), int(month), 1), dt.date(int(year), int(month), last_day)


def parse_date(value):
    if not value:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_int(value, default=None):
    try:
        if value in (None, "", "all", "null"):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_decimal(value, default=0):
    from decimal import Decimal, InvalidOperation

    try:
        if value in (None, "", "all"):
            return Decimal(str(default))
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(str(default))


def date_range_params(request) -> tuple[dt.date | None, dt.date | None]:
    return parse_date(request.GET.get("date_from")), parse_date(request.GET.get("date_to"))


# ---------------------------------------------------------------------------
# Identifiers & uploads
# ---------------------------------------------------------------------------
def generate_code(prefix: str, model, field: str = "code", width: int = 4) -> str:
    """Generate the next sequential code such as ``STU0007``."""
    existing = model.objects.order_by("-id").values_list(field, flat=True).first()
    start = 1
    if existing:
        digits = "".join(ch for ch in str(existing) if ch.isdigit())
        if digits:
            start = int(digits) + 1
    candidate = f"{prefix}{start:0{width}d}"
    qs = model.objects.filter(**{field: candidate})
    while qs.exists():
        start += 1
        candidate = f"{prefix}{start:0{width}d}"
        qs = model.objects.filter(**{field: candidate})
    return candidate


def unique_receipt_number(prefix: str = "RCPT") -> str:
    from fees.models import Payment

    year = timezone.localdate().year
    base = f"{prefix}-{year}-"
    last = (
        Payment.objects.filter(receipt_no__startswith=base)
        .order_by("-id")
        .values_list("receipt_no", flat=True)
        .first()
    )
    start = 1
    if last:
        digits = "".join(ch for ch in str(last)[len(base):] if ch.isdigit())
        if digits:
            start = int(digits) + 1
    return f"{base}{start:05d}"


def upload_path(instance, filename, folder="uploads"):
    """Build a collision free upload path: ``<folder>/<pk or uuid>/<name>``."""
    extension = os.path.splitext(filename)[1].lower()
    stem = slugify(os.path.splitext(filename)[0])[:40] or "file"
    identifier = getattr(instance, "pk", None) or uuid.uuid4().hex[:12]
    return f"{folder}/{identifier}/{stem}{extension}"


def avatar_initials(first_name: str = "", last_name: str = "") -> str:
    initials = f"{first_name[:1]}{last_name[:1]}".upper()
    return initials or "?"


def full_name(first_name: str = "", last_name: str = "") -> str:
    return f"{first_name or ''} {last_name or ''}".strip() or "N/A"


def file_size_human(size) -> str:
    try:
        size = float(size or 0)
    except (TypeError, ValueError):
        return "0 KB"
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value, low: float, high: float) -> float:
    return max(low, min(high, value))


def percent(numerator, denominator, digits: int = 2) -> float:
    numerator = safe_float(numerator)
    denominator = safe_float(denominator)
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, digits)


def chunked(iterable: Sequence, size: int) -> Iterable[list]:
    for index in range(0, len(iterable), size):
        yield list(iterable[index: index + size])


# ---------------------------------------------------------------------------
# CSV (used by the export helper as a fallback and for streaming downloads)
# ---------------------------------------------------------------------------
def rows_to_csv(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(list(headers))
    for row in rows:
        writer.writerow(["" if value is None else value for value in row])
    return buffer.getvalue().encode("utf-8-sig")


def filename_timestamp(prefix: str = "export", extension: str = "csv") -> str:
    stamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}.{extension}"


def form_error_summary(form, separator: str = " ") -> str:
    """Flatten a bound form's errors into a single readable sentence."""
    messages_out = []
    for field_errors in form.errors.values():
        for error in field_errors:
            messages_out.append(str(error))
    return separator.join(messages_out)
