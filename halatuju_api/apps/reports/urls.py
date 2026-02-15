"""
URL patterns for the reports app.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('reports/generate/', views.GenerateReportView.as_view(), name='generate-report'),
    path('reports/<int:report_id>/', views.ReportDetailView.as_view(), name='report-detail'),
]
