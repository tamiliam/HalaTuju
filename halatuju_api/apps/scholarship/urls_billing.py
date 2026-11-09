"""The console's overdue-invoice summary (staff nudges, sprint 3, 2026-11-09): one read-only route.

Kept apart from `urls.py`, which sits at the 600-line standard. Like `urls_award.py`, NOT an
`include()`: `urls.py` ADDS this list to its own `urlpatterns`, so the route is a top-level route of the
scholarship urlconf, spelt in full — exactly as the route walks read it.
"""
from django.urls import path

from .views_admin import AdminInvoiceOverdueView

urlpatterns = [
    path('admin/scholarship/billing/overdue/', AdminInvoiceOverdueView.as_view()),   # the red banner
]
