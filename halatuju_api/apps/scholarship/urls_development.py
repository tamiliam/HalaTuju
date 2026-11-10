"""Development modules' routes (student maintenance S10, 2026-11-02): Programme → Development, each module's
Progress, the scholar file's Growth tab and her Growth tab.

Kept apart from `urls.py`, which sits at the 600-line standard. Like `urls_surveys.py`, NOT an `include()`:
`urls.py` ADDS this list to its own `urlpatterns`, so every route is a top-level route of the scholarship
urlconf, spelt in full — exactly as the route walks read them.
"""
from django.urls import path

from .views_admin import (
    AdminModuleActionView, AdminModuleCsvView, AdminModuleLessonFileSignView, AdminModuleLessonFileView,
    AdminModuleProgressView, AdminModuleScholarView, AdminModulesView, AdminModuleView, AdminScholarGrowthFileView,
    AdminScholarGrowthView,
)
from .views_bursary import BursaryGrowthLessonView, BursaryGrowthTaskView, BursaryGrowthView

STAFF = 'admin/scholarship/development/'
MINE = 'scholarship/bursary/growth/'

urlpatterns = [
    path(STAFF, AdminModulesView.as_view()),
    path(f'{STAFF}<int:pk>/', AdminModuleView.as_view()),
    path(f'{STAFF}<int:pk>/progress/', AdminModuleProgressView.as_view()),
    path(f'{STAFF}<int:pk>/progress/<int:app_id>/<str:action>/', AdminModuleScholarView.as_view()),
    path(f'{STAFF}<int:pk>/csv/', AdminModuleCsvView.as_view()),
    path(f'{STAFF}<int:pk>/lessons/<int:lid>/file/', AdminModuleLessonFileView.as_view()),
    path(f'{STAFF}<int:pk>/lessons/<int:lid>/file/sign/', AdminModuleLessonFileSignView.as_view()),
    path(f'{STAFF}<int:pk>/<str:action>/', AdminModuleActionView.as_view()),
    path('admin/scholarship/scholars/<int:pk>/development/', AdminScholarGrowthView.as_view()),
    path('admin/scholarship/scholars/<int:pk>/development/<int:mid>/file/', AdminScholarGrowthFileView.as_view()),
    path(MINE, BursaryGrowthView.as_view()),
    path(f'{MINE}<int:pk>/', BursaryGrowthView.as_view()),
    path(f'{MINE}<int:pk>/lessons/<int:lid>/<str:action>/', BursaryGrowthLessonView.as_view()),
    path(f'{MINE}<int:pk>/task/', BursaryGrowthTaskView.as_view()),
    path(f'{MINE}<int:pk>/task/<str:step>/', BursaryGrowthTaskView.as_view()),
]
