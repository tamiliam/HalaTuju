"""Mentors' routes (student maintenance S7a, 2026-10-31): the Mentors page and its staff actions. The
invite itself is `POST admin/invitations/` with `audience='mentor'` (`views_admin/mentors.py`).
S7b (2026-11-01): the scholar file's Mentoring tab and the student's own (`scholarship/bursary/mentoring/`).

Kept apart from `urls.py`, which sits at the 600-line standard. Like `urls_letters.py`, NOT an
`include()`: `urls.py` ADDS this list to its own `urlpatterns`, so every route is a top-level route
of the scholarship urlconf, spelt in full — exactly as the route walks read them.
"""
from django.urls import path

from .views_admin import (
    AdminMentorActionView, AdminMentorView, AdminMentorsView, AdminScholarMentoringActionView,
    AdminScholarMentoringSessionsView, AdminScholarMentoringView,
)
from .views_bursary import BursaryMentoringView

urlpatterns = [
    path('admin/mentors/', AdminMentorsView.as_view()),
    path('admin/mentors/<int:pk>/', AdminMentorView.as_view()),
    path('admin/mentors/<int:pk>/<str:action>/', AdminMentorActionView.as_view()),
    path('admin/scholarship/scholars/<int:pk>/mentoring/', AdminScholarMentoringView.as_view()),
    path('admin/scholarship/scholars/<int:pk>/mentoring/sessions/', AdminScholarMentoringSessionsView.as_view()),
    path('admin/scholarship/scholars/<int:pk>/mentoring/<str:action>/', AdminScholarMentoringActionView.as_view()),
    path('scholarship/bursary/mentoring/', BursaryMentoringView.as_view()),
]
