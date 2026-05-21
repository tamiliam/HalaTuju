"""
Supabase Storage helpers for the B40 document vault.

Generates signed upload + download URLs for a PRIVATE bucket using the service
role key, so file bytes go straight between the browser and Supabase Storage —
never through Django. Best-effort: returns None on any failure so callers can
degrade gracefully.

Uses stdlib urllib (no extra dependency). The private bucket itself is created
at deploy time (carry-forward), and these calls are mocked in tests.
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

BUCKET = 'b40-documents'


def _base_url():
    return getattr(settings, 'SUPABASE_URL', '').rstrip('/')


def _service_key():
    return getattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', '')


def _post(path, payload):
    base, key = _base_url(), _service_key()
    if not base or not key:
        logger.warning('Supabase Storage not configured (SUPABASE_URL / service key missing)')
        return None
    req = urllib.request.Request(
        f'{base}/storage/v1{path}',
        data=json.dumps(payload or {}).encode(),
        method='POST',
        headers={
            'Authorization': f'Bearer {key}',
            'apikey': key,
            'Content-Type': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, ValueError, TimeoutError):
        logger.warning('Supabase Storage request failed: %s', path, exc_info=True)
        return None


def create_signed_upload_url(path):
    """Signed URL the browser can PUT a file to (private bucket). None on failure."""
    result = _post(f'/object/upload/sign/{BUCKET}/{path}', {})
    rel = (result or {}).get('url')
    return f'{_base_url()}/storage/v1{rel}' if rel else None


def create_signed_download_url(path, expires_in=3600):
    """Time-limited signed URL to view a private object. None on failure."""
    result = _post(f'/object/sign/{BUCKET}/{path}', {'expiresIn': expires_in})
    rel = (result or {}).get('signedURL') or (result or {}).get('signedUrl')
    return f'{_base_url()}/storage/v1{rel}' if rel else None
