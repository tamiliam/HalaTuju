"""Surveys' routes (student maintenance S9, 2026-11-02): Programme → Surveys, the scholar file's Surveys tab
and her Surveys tab.

Kept apart from `urls.py`, which sits at the 600-line standard. Like `urls_announcements.py`, NOT an
`include()`: `urls.py` ADDS this list to its own `urlpatterns`, so every route is a top-level route of the
scholarship urlconf, spelt in full — exactly as the route walks read them.
"""
from django.urls import path

from .views_admin import (
    AdminScholarSurveysView, AdminSurveyActionView, AdminSurveyCsvView, AdminSurveyResultsView, AdminSurveyView,
    AdminSurveysView,
)
from .views_bursary import BursarySurveyAnswersView, BursarySurveysView

urlpatterns = [
    path('admin/scholarship/surveys/', AdminSurveysView.as_view()),
    path('admin/scholarship/surveys/<int:pk>/', AdminSurveyView.as_view()),
    path('admin/scholarship/surveys/<int:pk>/results/', AdminSurveyResultsView.as_view()),
    path('admin/scholarship/surveys/<int:pk>/csv/', AdminSurveyCsvView.as_view()),
    path('admin/scholarship/surveys/<int:pk>/<str:action>/', AdminSurveyActionView.as_view()),
    path('admin/scholarship/scholars/<int:pk>/surveys/', AdminScholarSurveysView.as_view()),
    path('scholarship/bursary/surveys/', BursarySurveysView.as_view()),
    path('scholarship/bursary/surveys/<int:pk>/answers/', BursarySurveyAnswersView.as_view()),
]
