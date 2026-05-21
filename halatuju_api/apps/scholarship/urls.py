"""URL routing for the B40 Assistance Programme API."""
from django.urls import path

from .views import ApplicationDetailView, ApplicationListCreateView

urlpatterns = [
    path('scholarship/applications/', ApplicationListCreateView.as_view()),
    path('scholarship/applications/<int:pk>/', ApplicationDetailView.as_view()),
]
