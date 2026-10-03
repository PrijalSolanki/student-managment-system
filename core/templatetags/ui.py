"""Presentation helpers shared by every template.

The project keeps templates DRY: list pages describe their columns in Python
(see ``FilterableListView.get_table_columns``) and render them through
``templates/base_list.html``.  ``attr`` is what makes that possible, since
Django templates cannot resolve a dotted attribute path from a variable.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation

from django import template
from django.core.paginator import Page
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

STATUS_BADGES = {
    "ACTIVE": "success",
    "INACTIVE": "secondary",
    "PENDING": "warning",
    "PAID": "success",
    "PARTIAL": "info",
    "OVERDUE": "danger",
    "CANCELLED": "secondary",
    "PRESENT": "success",
    "ABSENT": "danger",
    "LEAVE": "warning",
    "HOLIDAY": "info",
    "GRADUATED": "primary",
    "ON_LEAVE": "warning",
    "ON_LEAVE_TEACHER": "warning",
    "PUBLISHED": "success",
    "DRAFT": "secondary",
    "MALE": "primary",
    "FEMALE": "danger",
    "OTHER": "secondary",
    "TRUE": "success",
    "FALSE": "secondary",
    "URGENT": "danger",
    "HIGH": "warning",
    "NORMAL": "info",
    "LOW": "secondary",
    "PASS": "success",
    "FAIL": "danger",
    "ABS": "warning",
    "A": "success",
    "B+": "success",
    "B": "primary",
    "C": "info",
    "D": "warning",
    "E": "danger",
    "F": "danger",
}

FIELD_CLASSES = {
    "text": "form-control",
    "number": "form-control",
    "email": "form-control",
    "url": "form-control",
    "password": "form-control",
    "date": "form-control",
    "datetime-local": "form-control",
    "time": "form-control",
    "tel": "form-control",
    "select": "form-select",
    "textarea": "form-control",
    "checkbox": "form-check-input",
    "radio": "form-check-input",
    "file": "form-control",
    "clearable": "form-select",
}


# ---------------------------------------------------------------------------
# attribute resolution
# ---------------------------------------------------------------------------
@register.filter
def attr(obj, path):
    """Resolve ``path`` (``"student.full_name"``) against ``obj``."""
    if obj is None or not path:
        return None
    current = obj
    for part in str(path).split("."):
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
            continue
        if isinstance(current, (list, tuple, Page)) and part.isdigit():
            try:
                current = current[int(part)]
            except IndexError:
                return None
            continue
        current = getattr(current, part, None)
        if current is None:
            try:
                current = current[part]  # type: ignore[index]
            except (TypeError, KeyError, IndexError):
                return None
        if callable(current):
            try:
                current = current()
            except TypeError:
                return None
    return current


@register.filter
def get_item(mapping, key):
    if mapping is None:
        return None
    try:
        return mapping.get(key)
    except AttributeError:
        return None


# ---------------------------------------------------------------------------
# formatting
# ---------------------------------------------------------------------------
@register.filter
def money(value, symbol="₹"):
    """Format a number/currency value as ``₹1,23,456.00``."""
    try:
        amount = Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        return value
    return f"{symbol}{amount:,.2f}"


@register.filter
def pct(value, digits=1):
    try:
        return f"{float(value or 0):.{int(digits)}f}%"
    except (TypeError, ValueError):
        return value


@register.filter
def dash(value, replacement="—"):
    return replacement if value in (None, "", "None") else value


@register.filter
def yesno(value, true="Yes", false="No"):
    if value is None or value == "":
        return "—"
    return true if value else false


@register.filter
def truncate_words_text(value, count=6):
    words = str(value or "").split()
    return " ".join(words[: int(count)])


@register.filter
def status_class(value):
    return STATUS_BADGES.get(str(value or "").upper(), "secondary")


@register.filter
def field_class(field):
    """Bootstrap class for a bound/unbound form field."""
    if field is None:
        return ""
    form_field = getattr(field, "field", None)
    widget = getattr(form_field, "widget", None)
    if widget is None:
        return FIELD_CLASSES.get(str(getattr(field, "widget_type", "")), "form-control")
    if getattr(widget, "is_hidden", False):
        return "d-none"
    widget_name = widget.__class__.__name__
    if widget_name == "RadioSelect":
        return "form-check-input"
    if widget_name == "CheckboxSelectMultiple":
        return "form-check-input"
    if widget_name == "SelectMultiple":
        return "form-select"
    input_type = str(getattr(widget, "input_type", "") or "").lower()
    if input_type == "checkbox":
        return "form-check-input"
    if input_type == "radio":
        return "form-check-input"
    if input_type == "select" or widget_name in {"Select", "NullBooleanSelect"}:
        return "form-select"
    return FIELD_CLASSES.get(input_type, "form-control")


@register.filter
def placeholder(field, default=""):
    return field.field.widget.attrs.get("placeholder", default)


# ---------------------------------------------------------------------------
# widgets
# ---------------------------------------------------------------------------
@register.filter
def add_class(field, css=""):
    """Render the widget with Bootstrap classes (plus any extra ``css``)."""
    base = field_class(field)
    existing = field.field.widget.attrs.get("class", "")
    combined = " ".join(part for part in (existing.strip(), base, css.strip()) if part)
    return field.as_widget(attrs={"class": combined})


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    """Current query string with ``kwargs`` applied (no leading ``?``).

    Usage in templates: ``href="?{% querystring page=2 %}"``.
    """
    request = context.get("request")
    params = request.GET.copy() if request else None
    if params is None:
        return ""
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()


@register.simple_tag
def query_param(request, key, default=""):
    return request.GET.get(key, default)


@register.simple_tag
def progress_class(value, good=75, warn=60):
    number = float(value or 0)
    if number >= good:
        return "bg-success"
    if number >= warn:
        return "bg-warning"
    return "bg-danger"


@register.simple_tag
def width_percent(value, maximum=100):
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0
    if number < 0:
        number = 0
    return min(100, round(number / float(maximum or 100) * 100, 2))


@register.simple_tag(takes_context=True)
def field(context, name, css=""):
    """Render one form field (label, control and errors) as a form group."""
    form = context.get("form")
    if not form or name not in form.fields:
        return ""
    bound = form[name]
    errors = bound.errors
    return format_html(
        '<div class="mb-3">'
        '<label class="form-label" for="{}">{}</label>'
        '{}'
        "{}"
        "</div>",
        bound.id_for_label,
        bound.label,
        add_class(bound, css),
        mark_safe("".join(f'<div class="invalid-feedback d-block">{error}</div>' for error in errors))
        if errors
        else "",
    )


@register.simple_tag
def status_badge(value, label=""):
    text = label or (value if value not in (None, "") else "—")
    return format_html('<span class="badge bg-{}">{}</span>', status_class(value), text)


@register.simple_tag
def month_name(month_number):
    try:
        return dt.date(2000, int(month_number), 1).strftime("%B")
    except (TypeError, ValueError):
        return month_number