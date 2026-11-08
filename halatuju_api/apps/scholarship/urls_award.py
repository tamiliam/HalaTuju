"""The award withdrawal routes (A1.13b, TD-198): a MAKER asks, a different CHECKER approves or refuses,
the maker may cancel (`award_withdrawal_chain`).

Kept apart from `urls.py`, which sits at the 600-line standard. Like `urls_development.py`, NOT an
`include()`: `urls.py` ADDS this list to its own `urlpatterns`, so the routes are top-level routes of the
scholarship urlconf, spelt in full — exactly as the route walks read them.
"""
from django.urls import path

from .views_admin import (
    AdminWithdrawalApproveView, AdminWithdrawalCancelView, AdminWithdrawalRefuseView,
    AdminWithdrawalRequestView,
)

urlpatterns = [
    path('admin/scholarship/applications/<int:pk>/withdrawal-request/', AdminWithdrawalRequestView.as_view()),
    path('admin/scholarship/withdrawal-requests/<int:pk>/approve/', AdminWithdrawalApproveView.as_view()),
    path('admin/scholarship/withdrawal-requests/<int:pk>/refuse/', AdminWithdrawalRefuseView.as_view()),
    path('admin/scholarship/withdrawal-requests/<int:pk>/cancel/', AdminWithdrawalCancelView.as_view()),
]
