"""The source console's routes (source sign-in S3 + S4, 2026-10-30), all under `api/v1/admin/source/`.

Kept apart from `urls.py`, which sits at the 600-line standard (`test_code_standards.py`). They are
NOT an `include()`: `urls.py` ADDS this list to its own `urlpatterns`, so every route here is a
top-level route of the scholarship urlconf, spelt in full — exactly as the route walks read them
(`test_endpoint_exercise.wired_routes` reads `urls.urlpatterns` flat; the source-user deny-by-default
sweep walks the resolver).
"""
from django.urls import path

from .views_admin import (
    AdminSourceAgreementView, AdminSourceApplicationDetailView, AdminSourceApplicationListView,
    AdminSourceOverviewView, AdminSourceProfileView, AdminSourceScholarDetailView,
    AdminSourceScholarListView, AdminSourceWitnessView,
)

urlpatterns = [
    path('admin/source/profile/', AdminSourceProfileView.as_view()),
    path('admin/source/overview/', AdminSourceOverviewView.as_view()),
    path('admin/source/applications/', AdminSourceApplicationListView.as_view()),
    path('admin/source/applications/<int:pk>/', AdminSourceApplicationDetailView.as_view()),
    # S4: the witness source reads the full contract, and records its witness.
    path('admin/source/applications/<int:pk>/agreement/', AdminSourceAgreementView.as_view()),
    path('admin/source/applications/<int:pk>/witness/', AdminSourceWitnessView.as_view()),
    path('admin/source/scholars/', AdminSourceScholarListView.as_view()),
    path('admin/source/scholars/<int:pk>/', AdminSourceScholarDetailView.as_view()),
]
