"""The award withdrawal route (A1.13, TD-198): a super withdraws an awarded case's award.

Kept apart from `urls.py`, which sits at the 600-line standard. Like `urls_development.py`, NOT an
`include()`: `urls.py` ADDS this list to its own `urlpatterns`, so the route is a top-level route of the
scholarship urlconf, spelt in full — exactly as the route walks read it.
"""
from django.urls import path

from .views_admin import AdminWithdrawAwardView

urlpatterns = [
    path('admin/scholarship/applications/<int:pk>/withdraw-award/', AdminWithdrawAwardView.as_view()),
]
