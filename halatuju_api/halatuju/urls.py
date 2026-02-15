"""
URL configuration for HalaTuju API.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('apps.courses.urls')),
    path('api/v1/', include('apps.reports.urls')),
]
