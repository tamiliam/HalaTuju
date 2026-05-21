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

urlpatterns = [
    path('scholarship/applications/', ApplicationListCreateView.as_view()),
    path('scholarship/applications/<int:pk>/', ApplicationDetailView.as_view()),
    path('scholarship/documents/sign-upload/', DocumentSignUploadView.as_view()),
    path('scholarship/documents/', DocumentListCreateView.as_view()),
    path('scholarship/documents/<int:pk>/', DocumentDetailView.as_view()),
    path('scholarship/referees/', RefereeListCreateView.as_view()),
    path('scholarship/consent/', ConsentView.as_view()),
]
