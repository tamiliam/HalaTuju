"""The signed-in admin's own-account routes (common profile S1, S2, S4), all under `api/v1/admin/me/`.

Kept apart from `urls.py`, which sits at the 600-line standard (`test_code_standards.py`). Like
`urls_award.py`, NOT an `include()`: `urls.py` ADDS this list to its own `urlpatterns`, so the routes
are top-level routes of the scholarship urlconf, spelt in full. Moved unchanged (G6 merge, 2026-11-08).
"""
from django.urls import path

from .views_admin import AdminMeActivityView, AdminMePasswordView, AdminMePhotoView, AdminMeView

urlpatterns = [
    path('admin/me/', AdminMeView.as_view()),   # common profile S1: own account, every role
    path('admin/me/password/', AdminMePasswordView.as_view()),   # own password, current one required
    path('admin/me/photo/', AdminMePhotoView.as_view()),   # S2: own photo (multipart POST / DELETE)
    path('admin/me/activity/', AdminMeActivityView.as_view()),   # S4: own activity list, every role
]
