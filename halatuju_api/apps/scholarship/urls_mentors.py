"""Mentors' routes (student maintenance S7a, 2026-10-31): the Mentors page and its staff actions. The
invite itself is `POST admin/invitations/` with `audience='mentor'` (`views_admin/mentors.py`).
S7b (2026-11-01): the scholar file's Mentoring tab and the student's own (`scholarship/bursary/mentoring/`).
S7c (2026-11-01): a mentor's own students (`admin/mentor/students/`).
S7d (2026-11-01): a staff member added as a mentor (`admin/mentors/staff/`).
Team tables T2 (2026-11-03): Team -> Admins / Reviewers -> Add and Remove from (`admin/team/<table>/`,
`admin/team/<table>/candidates/`) — the Team page's routes live beside the mentors' (Mentors joins Team in T3).
Team tables T4 (2026-11-03): Team -> Emails -> Admin emails (`admin/admin-emails/`, read-only).

Kept apart from `urls.py`, which sits at the 600-line standard. Like `urls_letters.py`, NOT an
`include()`: `urls.py` ADDS this list to its own `urlpatterns`, so every route is a top-level route
of the scholarship urlconf, spelt in full — exactly as the route walks read them.
"""
from django.urls import path

from .views_admin import (
    AdminMentorActionView, AdminMentorStudentModuleFileView, AdminMentorStudentSessionsView, AdminMentorStudentView,
    AdminMentorStudentsView, AdminMentorView, AdminMentorsView, AdminScholarMentoringActionView,
    AdminScholarMentoringSessionsView, AdminScholarMentoringView, AdminStaffMentorsView, AdminTeamCandidatesView,
    AdminTeamAdminEmailsView, AdminTeamTableView,
)
from .views_bursary import BursaryMentoringView

urlpatterns = [
    path('admin/mentors/', AdminMentorsView.as_view()),
    path('admin/mentors/staff/', AdminStaffMentorsView.as_view()),
    path('admin/mentors/<int:pk>/', AdminMentorView.as_view()),
    path('admin/mentors/<int:pk>/<str:action>/', AdminMentorActionView.as_view()),
    path('admin/scholarship/scholars/<int:pk>/mentoring/', AdminScholarMentoringView.as_view()),
    path('admin/scholarship/scholars/<int:pk>/mentoring/sessions/', AdminScholarMentoringSessionsView.as_view()),
    path('admin/scholarship/scholars/<int:pk>/mentoring/<str:action>/', AdminScholarMentoringActionView.as_view()),
    path('scholarship/bursary/mentoring/', BursaryMentoringView.as_view()),
    path('admin/mentor/students/', AdminMentorStudentsView.as_view()),
    path('admin/mentor/students/<int:pk>/', AdminMentorStudentView.as_view()),
    path('admin/mentor/students/<int:pk>/sessions/', AdminMentorStudentSessionsView.as_view()),
    path('admin/mentor/students/<int:pk>/modules/<int:mid>/file/', AdminMentorStudentModuleFileView.as_view()),
    path('admin/admin-emails/', AdminTeamAdminEmailsView.as_view()),   # T4: Team -> Emails -> Admin emails
    path('admin/team/<str:table>/', AdminTeamTableView.as_view()),
    path('admin/team/<str:table>/candidates/', AdminTeamCandidatesView.as_view()),
]
