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


def build_doc_key(app, *segments):
    """The ONE home for the document storage-key scheme. Org-prefixes the key for the
    tenant fence (platform Sprint 4): ``<org_id>/<segments...>``. When the application
    has no owning organisation (bare test fixtures only — prod apps are all backfilled),
    the prefix is omitted → the legacy layout, which ``resolve_org_for_path`` treats as
    org #1. Used by BOTH the document upload (``<org>/<app>/<doc_type>/<uuid>``) and the
    bursary PDF (``<org>/<app>/<file>``) so the scheme can never drift between sites."""
    tail = '/'.join(str(s) for s in segments if s not in (None, ''))
    org_id = getattr(app, 'owning_organisation_id', None)
    return f'{org_id}/{tail}' if org_id else tail


def resolve_org_for_path(path):
    """The owning-organisation id encoded in a document storage key, or None when it
    can't be read from the path alone. Only a 4-segment DOC key
    (``<org>/<app>/<doc_type>/<uuid>``) unambiguously carries the org prefix; legacy
    3-segment doc keys and 2/3-segment bursary keys return None, so the caller falls
    back to the row's application FK (the real fence). Belt-and-braces for the two
    signing seams — a doc whose key-org disagrees with its row-org is not signed."""
    parts = [p for p in (path or '').strip('/').split('/') if p]
    if len(parts) >= 4:
        try:
            return int(parts[0])
        except (TypeError, ValueError):
            return None
    return None


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


def list_objects(prefix='', limit=1000):
    """Best-effort listing of one level under ``prefix`` in the private bucket.

    Returns a list of item dicts (Supabase shape: ``{name, id, metadata, ...}``)
    or [] on failure / when unconfigured. Folders come back with ``id`` = None
    (no file metadata); files have a non-null ``id``. Not recursive — the caller
    walks levels. Used by the orphan-blob cleanup command (TD-062).
    """
    base, key = _base_url(), _service_key()
    if not base or not key:
        logger.warning('Supabase Storage not configured (SUPABASE_URL / service key missing)')
        return []
    payload = {
        'prefix': prefix,
        'limit': limit,
        'offset': 0,
        'sortBy': {'column': 'name', 'order': 'asc'},
    }
    req = urllib.request.Request(
        f'{base}/storage/v1/object/list/{BUCKET}',
        data=json.dumps(payload).encode(),
        method='POST',
        headers={
            'Authorization': f'Bearer {key}',
            'apikey': key,
            'Content-Type': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            return result if isinstance(result, list) else []
    except (urllib.error.URLError, ValueError, TimeoutError):
        logger.warning('Supabase Storage list failed for prefix %r', prefix, exc_info=True)
        return []


def object_exists(path):
    """Tri-state existence check for a blob: True (present), False (CONFIRMED absent),
    or None (couldn't verify — unconfigured or a storage error). Callers must treat
    only False as "missing" and never block on None, so a storage hiccup during the
    check can't reject a legitimate upload. Lists the object's folder and looks for its
    exact name (signing can't be used — it returns None for BOTH missing and transient
    failure, which we must distinguish)."""
    path = (path or '').strip().strip('/')
    if '/' not in path:
        return None
    base, key = _base_url(), _service_key()
    if not base or not key:
        return None
    prefix, name = path.rsplit('/', 1)
    payload = {'prefix': prefix, 'limit': 1000, 'offset': 0,
               'sortBy': {'column': 'name', 'order': 'asc'}}
    req = urllib.request.Request(
        f'{base}/storage/v1/object/list/{BUCKET}',
        data=json.dumps(payload).encode(),
        method='POST',
        headers={'Authorization': f'Bearer {key}', 'apikey': key, 'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            items = json.loads(resp.read().decode())
            if not isinstance(items, list):
                return None
            return any((o or {}).get('name') == name for o in items)
    except (urllib.error.URLError, ValueError, TimeoutError):
        logger.warning('Supabase Storage exists-check failed', exc_info=True)
        return None


def download_object(path):
    """Fetch the raw bytes of one private object via the service key. None on failure.

    Used by the off-platform backup command (backup_documents). Best-effort; the
    path is never logged (it can embed application ids).
    """
    base, key = _base_url(), _service_key()
    if not base or not key:
        logger.warning('Supabase Storage not configured (SUPABASE_URL / service key missing)')
        return None
    req = urllib.request.Request(
        f'{base}/storage/v1/object/authenticated/{BUCKET}/{path}',
        method='GET',
        headers={'Authorization': f'Bearer {key}', 'apikey': key},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except (urllib.error.URLError, ValueError, TimeoutError):
        logger.warning('Supabase Storage download failed', exc_info=True)
        return None


def delete_objects(paths):
    """Best-effort batch DELETE of private objects from the bucket. Returns
    True on success, False on any failure (logged). No-op if paths is empty.

    Used when a single-instance document type (IC / results_slip / etc.) gets
    a fresh upload — the old object should not linger in Storage. Caller is
    expected to also delete the matching DB row(s).
    """
    paths = [p for p in (paths or []) if p]
    if not paths:
        return True
    base, key = _base_url(), _service_key()
    if not base or not key:
        logger.warning('Supabase Storage not configured (SUPABASE_URL / service key missing)')
        return False
    req = urllib.request.Request(
        f'{base}/storage/v1/object/{BUCKET}',
        data=json.dumps({'prefixes': paths}).encode(),
        method='DELETE',
        headers={
            'Authorization': f'Bearer {key}',
            'apikey': key,
            'Content-Type': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as _:
            return True
    except (urllib.error.URLError, ValueError, TimeoutError):
        logger.warning('Supabase Storage DELETE failed for %s', paths, exc_info=True)
        return False


def upload_object(path, data, content_type):
    """Upsert raw bytes to the private bucket (overwrites the object at ``path``). Used to replace
    a HEIC upload with its JPEG conversion. True on success, False on any failure (logged)."""
    base, key = _base_url(), _service_key()
    if not base or not key:
        logger.warning('Supabase Storage not configured (SUPABASE_URL / service key missing)')
        return False
    req = urllib.request.Request(
        f'{base}/storage/v1/object/{BUCKET}/{path}',
        data=data, method='POST',
        headers={
            'Authorization': f'Bearer {key}',
            'apikey': key,
            'Content-Type': content_type or 'application/octet-stream',
            'x-upsert': 'true',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as _:
            return True
    except (urllib.error.URLError, ValueError, TimeoutError):
        logger.warning('Supabase Storage upload failed for %s', path, exc_info=True)
        return False
