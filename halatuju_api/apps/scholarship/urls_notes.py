"""The bell line's count of new notes between org admins and reviewers (request #73, 2026-11-16): one route.

Kept apart from `urls.py`, which sits at the 600-line standard. Like `urls_billing.py`, NOT an `include()`:
`urls.py` ADDS this list to its own `urlpatterns`, so the route is a top-level route of the scholarship
urlconf, spelt in full — exactly as the route walks read it.
"""
from django.urls import path

from .views_admin import AdminStaffNotificationCountView

urlpatterns = [
    path('admin/scholarship/staff-notifications/count/', AdminStaffNotificationCountView.as_view()),
]
