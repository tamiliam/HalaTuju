"""Announcements' routes (student maintenance S8, 2026-11-01): Programme → Announcements and her News tab.

Kept apart from `urls.py`, which sits at the 600-line standard. Like `urls_letters.py`, NOT an `include()`:
`urls.py` ADDS this list to its own `urlpatterns`, so every route is a top-level route of the scholarship
urlconf, spelt in full — exactly as the route walks read them.
"""
from django.urls import path

from .views_admin import AdminAnnouncementView, AdminAnnouncementWithdrawView, AdminAnnouncementsView
from .views_bursary import BursaryNewsReadView, BursaryNewsView

urlpatterns = [
    path('admin/scholarship/announcements/', AdminAnnouncementsView.as_view()),
    path('admin/scholarship/announcements/<int:pk>/', AdminAnnouncementView.as_view()),
    path('admin/scholarship/announcements/<int:pk>/withdraw/', AdminAnnouncementWithdrawView.as_view()),
    path('scholarship/bursary/news/', BursaryNewsView.as_view()),
    path('scholarship/bursary/news/read/', BursaryNewsReadView.as_view()),
]
