"""Mentors' routes (student maintenance S7a, 2026-10-31): the Mentors page and its staff actions. The
invite itself is `POST admin/invitations/` with `audience='mentor'` (`views_admin/mentors.py`).

Kept apart from `urls.py`, which sits at the 600-line standard. Like `urls_letters.py`, NOT an
`include()`: `urls.py` ADDS this list to its own `urlpatterns`, so every route is a top-level route
of the scholarship urlconf, spelt in full — exactly as the route walks read them.
"""
from django.urls import path

from .views_admin import AdminMentorActionView, AdminMentorView, AdminMentorsView

urlpatterns = [
    path('admin/mentors/', AdminMentorsView.as_view()),
    path('admin/mentors/<int:pk>/', AdminMentorView.as_view()),
    path('admin/mentors/<int:pk>/<str:action>/', AdminMentorActionView.as_view()),
]
