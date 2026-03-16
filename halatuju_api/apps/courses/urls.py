"""
URL patterns for the courses app.
"""
from django.urls import path
from . import views
from .views_admin import (
    AdminRoleView, PartnerDashboardView, PartnerStudentListView,
    PartnerStudentDetailView, PartnerStudentExportView,
)

urlpatterns = [
    # Partner admin
    path('admin/role/', AdminRoleView.as_view(), name='admin-role'),
    path('admin/dashboard/', PartnerDashboardView.as_view(), name='partner-dashboard'),
    path('admin/students/', PartnerStudentListView.as_view(), name='partner-students'),
    path('admin/students/export/', PartnerStudentExportView.as_view(), name='partner-export'),
    path('admin/students/<str:user_id>/', PartnerStudentDetailView.as_view(), name='partner-student-detail'),

    # Eligibility check (main engine endpoint)
    path('eligibility/check/', views.EligibilityCheckView.as_view(), name='eligibility-check'),

    # Ranking
    path('ranking/', views.RankingView.as_view(), name='ranking'),

    # Quiz
    path('quiz/questions/', views.QuizQuestionsView.as_view(), name='quiz-questions'),
    path('quiz/submit/', views.QuizSubmitView.as_view(), name='quiz-submit'),

    # Field taxonomy
    path('fields/', views.FieldListView.as_view(), name='field-list'),

    # Course catalog
    path('courses/search/', views.CourseSearchView.as_view(), name='course-search'),
    path('courses/', views.CourseListView.as_view(), name='course-list'),
    path('courses/<str:course_id>/', views.CourseDetailView.as_view(), name='course-detail'),

    # Institutions
    path('institutions/', views.InstitutionListView.as_view(), name='institution-list'),
    path('institutions/<str:institution_id>/', views.InstitutionDetailView.as_view(), name='institution-detail'),

    # User saved courses
    path('saved-courses/', views.SavedCoursesView.as_view(), name='saved-courses'),
    path('saved-courses/<str:course_id>/', views.SavedCourseDetailView.as_view(), name='saved-course-detail'),

    # User profile
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/sync/', views.ProfileSyncView.as_view(), name='profile-sync'),

    # Admission outcomes
    path('outcomes/', views.OutcomeListView.as_view(), name='outcome-list'),
    path('outcomes/<int:outcome_id>/', views.OutcomeDetailView.as_view(), name='outcome-detail'),

    # Calculate endpoints (TD-002: server-side calculations)
    path('calculate/merit/', views.CalculateMeritView.as_view(), name='calculate-merit'),
    path('calculate/cgpa/', views.CalculateCgpaView.as_view(), name='calculate-cgpa'),
    path('calculate/pathways/', views.CalculatePathwaysView.as_view(), name='calculate-pathways'),

    # STPM eligibility
    path('stpm/eligibility/check/', views.StpmEligibilityCheckView.as_view(), name='stpm-eligibility-check'),
    path('stpm/ranking/', views.StpmRankingView.as_view(), name='stpm-ranking'),
    path('stpm/search/', views.StpmSearchView.as_view(), name='stpm-search'),
    path('stpm/courses/<str:course_id>/', views.StpmCourseDetailView.as_view(), name='stpm-course-detail'),
]
