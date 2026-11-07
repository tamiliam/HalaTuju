"""
URL configuration for HalaTuju API.
"""
from django.contrib import admin
from django.urls import path, include

from .admin_login import throttled_login

urlpatterns = [
    # SEC-06: the admin's own login path, throttled; listed first so it wins over admin.site.urls.
    path('admin/login/', throttled_login),
    path('admin/', admin.site.urls),
    path('api/v1/', include('apps.courses.urls')),
    path('api/v1/', include('apps.reports.urls')),
    path('api/v1/', include('apps.scholarship.urls')),
]
