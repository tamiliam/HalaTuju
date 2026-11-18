"""Reject before interview (request #75): one admin route.

Kept apart from `urls.py`, which sits at the 600-line standard. Like `urls_billing.py`, NOT an
`include()`: `urls.py` ADDS this list to its own `urlpatterns`, so the route is a top-level route of the
scholarship urlconf, spelt in full — exactly as the route walks read it.
"""
from django.urls import path

from .views_admin import AdminRejectBeforeInterviewView

urlpatterns = [
    path('admin/scholarship/applications/<int:pk>/reject-before-interview/', AdminRejectBeforeInterviewView.as_view()),
]
