"""URL routing for the B40 Assistance Programme API."""
from django.urls import path

from .views import (
    ApplicationDetailView,
    ApplicationListCreateView,
    ConsentView,
    DocumentDetailView,
    DocumentListCreateView,
    DocumentSignUploadView,
    RefereeListCreateView,
)
from .views_admin import (
    AdminApplicationDetailView,
    AdminApplicationListView,
    AdminGenerateProfileView,
    AdminProfileEditView,
    AdminPublishProfileView,
)

urlpatterns = [
    path('scholarship/applications/', ApplicationListCreateView.as_view()),
    path('scholarship/applications/<int:pk>/', ApplicationDetailView.as_view()),
    path('scholarship/documents/sign-upload/', DocumentSignUploadView.as_view()),
    path('scholarship/documents/', DocumentListCreateView.as_view()),
    path('scholarship/documents/<int:pk>/', DocumentDetailView.as_view()),
    path('scholarship/referees/', RefereeListCreateView.as_view()),
    path('scholarship/consent/', ConsentView.as_view()),

    # MyNadi admin (PartnerAdmin auth; /admin/ is NRIC-gate whitelisted)
    path('admin/scholarship/applications/', AdminApplicationListView.as_view()),
    path('admin/scholarship/applications/<int:pk>/', AdminApplicationDetailView.as_view()),
    path('admin/scholarship/applications/<int:pk>/generate-profile/', AdminGenerateProfileView.as_view()),
    path('admin/scholarship/applications/<int:pk>/profile/', AdminProfileEditView.as_view()),
    path('admin/scholarship/applications/<int:pk>/publish/', AdminPublishProfileView.as_view()),
]
