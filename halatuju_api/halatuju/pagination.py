"""Shared DRF pagination for partner-admin list endpoints.

Server-side, page-number pagination with a client-overridable page size
(``?page`` and ``?page_size=N``). Applied *per view* — deliberately NOT wired
in as a global ``REST_FRAMEWORK`` default — so the many existing endpoints that
return full, unpaginated lists keep working unchanged.

Use it from a plain ``APIView`` like so::

    paginator = FlexiblePageNumberPagination()
    page = paginator.paginate_queryset(queryset, request, view=self)
    data = MySerializer(page, many=True).data
    return paginator.envelope(data, results_key='students', org_name=org.name)
"""
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class FlexiblePageNumberPagination(PageNumberPagination):
    """Page-number pagination; size overridable via ``?page_size`` up to a cap."""

    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100

    def envelope(self, results, results_key='results', **extra):
        """Build a paginated response, merging in any extra envelope fields.

        Standard pagination metadata (``count``/``total_pages``/``page``/
        ``page_size``/``next``/``previous``) is always present. ``extra`` lets a
        view keep its own top-level metadata (e.g. ``org_name``) alongside it.
        ``results_key`` names the list field so callers can preserve their
        existing response shape (e.g. ``students`` instead of ``results``).
        """
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'page': self.page.number,
            'page_size': self.get_page_size(self.request),
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            results_key: results,
            **extra,
        })
