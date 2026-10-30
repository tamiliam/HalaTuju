"""Letters' routes (student maintenance S6b, 2026-10-31): the scholar file's Letters tab, the
organisation's letter wording, and her own letters on My Bursary.

Kept apart from `urls.py`, which sits at the 600-line standard. Like `urls_source.py`, NOT an
`include()`: `urls.py` ADDS this list to its own `urlpatterns`, so every route is a top-level route
of the scholarship urlconf, spelt in full — exactly as the route walks read them.
"""
from django.urls import path

from .views_admin import (
    AdminLetterTemplatesView, AdminScholarLetterActionView, AdminScholarLetterPdfView,
    AdminScholarLetterPreviewView, AdminScholarLettersView,
)
from .views_bursary import BursaryLetterActionView, BursaryLetterPdfView, BursaryLettersView

urlpatterns = [
    path('admin/scholarship/scholars/<int:pk>/letters/', AdminScholarLettersView.as_view()),
    path('admin/scholarship/scholars/<int:pk>/letters/preview/', AdminScholarLetterPreviewView.as_view()),
    path('admin/scholarship/scholars/<int:pk>/letters/<int:lid>/pdf/', AdminScholarLetterPdfView.as_view()),
    path('admin/scholarship/scholars/<int:pk>/letters/<int:lid>/<str:action>/',
         AdminScholarLetterActionView.as_view()),
    path('admin/scholarship/organisation/letter-templates/', AdminLetterTemplatesView.as_view()),
    path('scholarship/bursary/letters/', BursaryLettersView.as_view()),
    path('scholarship/bursary/letters/<int:lid>/pdf/', BursaryLetterPdfView.as_view()),
    path('scholarship/bursary/letters/<int:lid>/<str:action>/', BursaryLetterActionView.as_view()),
]
