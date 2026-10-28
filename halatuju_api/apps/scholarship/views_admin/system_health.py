"""GET /api/v1/admin/scholarship/system-health/ — the admin System health light (2026-10-28).

SUPER-ONLY: a platform surface (Gemini, Vision, email, the scheduler and the AI bill are the
platform's, not an organisation's). Every other admin — org admin, reviewer, QC, finance — gets 403,
and the web never asks for it on their behalf. Read-only; it calls no API.

Cached for `CACHE_SECONDS`, one entry for the whole platform (the answer is the same for every
super admin). `?fresh=1` — the panel's refresh button — recomputes and refills the cache.
"""
from django.core.cache import cache
from rest_framework.response import Response

from ..services.system_health import snapshot
from .base import _AdminBase

CACHE_KEY = 'admin_system_health_v1'
CACHE_SECONDS = 60


class AdminSystemHealthView(_AdminBase):
    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not admin.is_super:
            return Response({'error': 'forbidden'}, status=403)
        payload = None if request.query_params.get('fresh') else cache.get(CACHE_KEY)
        if payload is None:
            payload = snapshot()
            cache.set(CACHE_KEY, payload, CACHE_SECONDS)
        return Response(payload)
