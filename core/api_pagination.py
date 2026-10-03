"""Pagination classes used by the REST API."""

from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 200


class LargeResultsSetPagination(StandardResultsSetPagination):
    page_size = 50
    max_page_size = 500
