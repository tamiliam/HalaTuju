"""
URL patterns for the courses app.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Eligibility check (main engine endpoint)
    path('eligibility/check/', views.EligibilityCheckView.as_view(), name='eligibility-check'),

    # Ranking
    path('ranking/', views.RankingView.as_view(), name='ranking'),

    # Course catalog
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
]
