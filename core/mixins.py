"""Reusable class based view mixins (filtering, sorting, messages, audit)."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.http import HttpResponseRedirect
from django.views.generic import ListView

from core.models import AuditLog  # noqa: F401  (re-exported for convenience)
from core.permissions import log_action  # noqa: F401  (re-exported for convenience)
from core.utils import parse_date, parse_int  # noqa: F401


class FilterableListView(ListView):
    """ListView with search, multiple filters, sorting and pagination.

    Subclasses declare ``search_fields``, ``filter_fields`` (query params),
    ``filter_lookups`` (param -> ORM lookup) and ``ordering_fields``
    (param -> ORM ordering).
    """

    paginate_by = 10
    search_fields: list[str] = []
    filter_fields: list[str] = []
    filter_lookups: dict[str, str] = {}
    date_range_fields: list[str] = []
    ordering_fields: dict[str, str] = {}
    default_ordering = "-created_at"
    template_name = None
    list_title = ""
    #: checkbox group name rendered in the first table column (bulk actions).
    select_field: str = ""
    #: URL name of the POST endpoint handling ``select_field`` in bulk.
    bulk_action_url: str = ""

    # ------------------------------------------------------------------ query
    def get_filters(self) -> dict:
        params = self.request.GET
        return {name: (params.get(name) or "").strip() for name in self.filter_fields}

    def get_search_term(self) -> str:
        return (self.request.GET.get("q") or "").strip()

    def get_ordering(self) -> str:
        requested = self.request.GET.get("ordering") or ""
        if requested in self.ordering_fields:
            return self.ordering_fields[requested]
        if requested in self.ordering_fields.values():
            return requested
        return self.default_ordering

    def filter_queryset(self, queryset):
        term = self.get_search_term()
        if term and self.search_fields:
            from django.db.models import Q

            condition = Q()
            for field in self.search_fields:
                condition |= Q(**{f"{field}__icontains": term})
            queryset = queryset.filter(condition)

        for param, value in self.get_filters().items():
            if value in ("", None):
                continue
            lookup = self.filter_lookups.get(param, param)
            if isinstance(value, (list, tuple)):  # pragma: no cover
                queryset = queryset.filter(**{f"{lookup}__in": value})
            else:
                queryset = queryset.filter(**{lookup: value})

        date_from = parse_date(self.request.GET.get("date_from"))
        date_to = parse_date(self.request.GET.get("date_to"))
        for field in self.date_range_fields:
            if date_from:
                queryset = queryset.filter(**{f"{field}__gte": date_from})
            if date_to:
                queryset = queryset.filter(**{f"{field}__lte": date_to})
        return queryset

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.filter_queryset(queryset)
        return queryset.order_by(self.get_ordering())

    # ---------------------------------------------------------------- context
    def get_filter_choices(self) -> dict:
        return {}

    def get_table_columns(self) -> list[dict]:
        """Columns rendered by ``templates/base_list.html``.

        Each column is a dict with ``label`` plus either ``attr`` (a dotted
        attribute path resolved by the ``attr`` filter) and the optional
        flags ``badge`` / ``money`` / ``pct`` / ``date`` / ``bool`` / ``align``.
        """
        return []

    def get_table_actions(self) -> dict:
        """URL names used for the row action buttons (``""`` disables one)."""
        return {}

    def get_table_config(self) -> dict:
        columns = self.get_table_columns()
        actions = self.get_table_actions()
        has_actions = bool(actions.get("detail") or actions.get("edit") or actions.get("delete") or actions.get("extra"))
        return {
            "columns": columns,
            "actions": actions,
            "ordering_fields": self.ordering_fields,
            "current_ordering": self.request.GET.get("ordering", ""),
            "list_title": self.list_title,
            "add_url": getattr(self, "add_url_name", ""),
            "extra_url": getattr(self, "extra_url_name", ""),
            "select": self.select_field,
            "bulk_action": self.bulk_action_url,
            "empty_colspan": len(columns) + (1 if self.select_field else 0) + (1 if has_actions else 0),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": self.list_title,
                "active_menu": getattr(self, "active_menu", ""),
                "breadcrumb_parent": getattr(self, "breadcrumb_parent", ""),
                "filters": self.request.GET,
                "filter_choices": self.get_filter_choices(),
                "ordering_fields": self.ordering_fields,
                "current_ordering": self.request.GET.get("ordering", ""),
                "search_term": self.get_search_term(),
                "table": self.get_table_config(),
                "columns": self.get_table_columns(),
                "result_count": context.get("paginator").count if context.get("paginator") else 0,
                "has_active_filters": bool(
                    self.get_search_term()
                    or any(self.get_filters().values())
                    or self.request.GET.get("date_from")
                    or self.request.GET.get("date_to")
                ),
            }
        )
        return context

    # ------------------------------------------------------------------ extra
    def get(self, request, *args, **kwargs):
        """Honour ``?export=1&format=csv|xlsx|pdf`` on every list page."""
        if request.GET.get("export"):
            return self.export(request)
        return super().get(request, *args, **kwargs)

    def get_export_rows(self, queryset=None):  # pragma: no cover - overridden
        return [], []

    def export(self, request):
        from core.exports import ExportError, export_data

        queryset = self.get_queryset()
        headers, rows = self.get_export_rows(queryset)
        module = getattr(self, "module_name", self.model._meta.verbose_name_plural)
        try:
            response = export_data(
                request,
                filename_prefix=str(module).replace(" ", "_"),
                headers=headers,
                rows=rows,
                title=str(self.list_title or module),
            )
        except ExportError as exc:
            messages.error(request, str(exc))
            return HttpResponseRedirect(request.get_full_path())
        log_action(
            request,
            AuditLog.Action.EXPORT,
            module=str(module),
            description=f"Exported {len(rows)} {module} rows",
        )
        return response


class FormSuccessMixin:
    """Flash messages on successful form submission.

    Audit logging for create/update is handled automatically by the
    ``core.signals`` receivers, so it is intentionally not duplicated here.
    """

    success_message = "Changes saved successfully."
    created_message = "Record created successfully."

    def form_valid(self, form):
        is_create = "pk" not in self.kwargs
        response = super().form_valid(form)
        message = self.created_message if is_create else self.success_message
        if message:
            messages.success(self.request, message % {"object": self.object})
        return response


class ProtectedDeleteMixin:
    """Turn ``ProtectedError`` / ``ValidationError`` into friendly messages."""

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except (ProtectedError, ValidationError) as exc:
            detail = getattr(exc, "message", None) or "; ".join(
                str(message) for message in getattr(exc, "messages", [])
            ) or "This record is still in use and cannot be deleted."
            messages.error(self.request, f"Unable to delete record. {detail}")
            return HttpResponseRedirect(self.get_success_url())
        messages.success(
            self.request,
            f"{self.model._meta.verbose_name.capitalize()} deleted successfully.",
        )
        return response
