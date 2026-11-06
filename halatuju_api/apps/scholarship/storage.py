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
import re
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


_MAX_DOC_KEY = 500   # the serializer's storage_path max_length


def is_issued_doc_key(app, doc_type, path):
    """True only for a key the upload-URL step could have issued for THIS application and THIS
    doc_type: exactly ``build_doc_key(app, app.id, doc_type)`` + ``/`` + 32 lowercase hex (audit
    SEC-01). No ``..``, no leading slash, no extra segments — so a client can never point a
    document row at another application's file, a formal letter or a bursary PDF."""
    if not isinstance(path, str) or len(path) > _MAX_DOC_KEY or '..' in path or path.startswith('/'):
        return False
    prefix = build_doc_key(app, app.id, doc_type)
    return re.fullmatch(re.escape(prefix) + r'/[0-9a-f]{32}', path) is not None


def recorded_doc_key_refusal(app, doc_type, path):
    """The error code that refuses recording ``path`` as a ``doc_type`` document of ``app``, or
    None when it may be recorded: ``bad_storage_path`` for a key this app's upload step never
    issued (SEC-01), ``upload_incomplete`` when storage CONFIRMS the object is absent."""
    if not is_issued_doc_key(app, doc_type, path):
        return 'bad_storage_path'
    if object_exists(path) is False:
        return 'upload_incomplete'
    return None


def _is_legacy_own_doc_key(app, parts):
    """The pre-fence document key (before platform Sprint 4): exactly ``<app.id>/<doc_type>/<name>``
    with ``doc_type`` a real ``ApplicantDocument`` type. The first part is compared WHOLE (app 5 never
    matches 50) and the doc-type middle keeps it apart from an org-prefixed bursary key
    ``<org>/<app>/<file>`` (its middle part is an application id, never a doc type)."""
    from .models import ApplicantDocument   # lazy: storage stays importable without the models
    return (len(parts) == 3 and parts[0] == str(app.id)
            and parts[1] in {code for code, _label in ApplicantDocument.DOC_TYPES})


def is_inside_app_prefix(app, path):
    """True when ``path`` is this application's own: under its document prefix
    (``build_doc_key(app, app.id)`` + ``/``), or its legacy 3-part document key
    ``<app.id>/<doc_type>/<name>`` (the ~1,114 rows recorded before the org prefix, audit SEC-01 L1);
    never with a ``..``, ``.``, empty segment or leading slash."""
    if not isinstance(path, str) or not path or path.startswith('/') or '\\' in path:
        return False
    parts = path.split('/')
    if any(seg in ('', '.', '..') for seg in parts):
        return False
    return path.startswith(build_doc_key(app, app.id) + '/') or _is_legacy_own_doc_key(app, parts)


def delete_own_doc_objects(app, paths):
    """Delete only the blobs inside ``app``'s own prefix (SEC-01). A stored path outside it (a row
    recorded before the record step checked keys) is left in storage — the caller still deletes
    the row — and logged by count only, never by path."""
    paths = [p for p in (paths or []) if p]
    own = [p for p in paths if is_inside_app_prefix(app, p)]
    if len(own) < len(paths):
        logger.warning('AUDIT doc_delete_foreign_path app=%s count=%d (row deleted, blob kept)',
                       getattr(app, 'id', None), len(paths) - len(own))
    return delete_objects(own) if own else True


def build_request_attachment_key(org_id, request_id, uuid_hex):
    """The storage-key scheme for a Requests-space screenshot attachment (Sprint 15.1):
    ``requests/<org_id>/<request_id>/<uuid>``. The ``requests/`` prefix keeps it in its own
    namespace (never collides with a doc key, which starts with a bare org id) and lets
    ``resolve_org_for_path`` read the owning org straight off the key for the download fence."""
    return f'requests/{org_id}/{request_id}/{uuid_hex}'


def is_clean_key(path):
    """True for a non-empty storage key with no ``..``, no leading slash, no backslash and no empty
    or ``.`` segment — a key that can only name the object it spells (audit SEC-01 L2)."""
    if not isinstance(path, str) or not path or path.startswith('/') or '\\' in path or '..' in path:
        return False
    return all(seg not in ('', '.') for seg in path.split('/'))


def is_request_attachment_key(org_id, request_id, path):
    """True only for a clean key inside THIS request's attachment namespace
    (``build_request_attachment_key(org_id, request_id, '')`` + a name). The record, delete and
    sign-link steps of a Requests attachment all ask this (audit SEC-01 L2)."""
    prefix = build_request_attachment_key(org_id, request_id, '')
    return is_clean_key(path) and path.startswith(prefix) and path != prefix


def resolve_org_for_path(path):
    """The owning-organisation id encoded in a storage key, or None when it can't be read from the
    path alone. Two schemes carry the org: a Requests attachment key
    (``requests/<org>/<request>/<uuid>`` → ``parts[1]``) and a 4-segment DOC key
    (``<org>/<app>/<doc_type>/<uuid>`` → ``parts[0]``). Legacy 3-segment doc keys and 2/3-segment
    bursary keys return None, so the caller falls back to the row's FK (the real fence).
    Belt-and-braces for the signing seams — a blob whose key-org disagrees with its row-org is not
    signed."""
    parts = [p for p in (path or '').strip('/').split('/') if p]
    # Requests-space attachment: requests/<org_id>/<request_id>/<uuid>.
    if len(parts) >= 3 and parts[0] == 'requests':
        try:
            return int(parts[1])
        except (TypeError, ValueError):
            return None
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


def _post(path, payload, headers=None):
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
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, ValueError, TimeoutError):
        logger.warning('Supabase Storage request failed: %s', path, exc_info=True)
        return None


def create_signed_upload_url(path, upsert=None):
    """Signed URL the browser can PUT a file to (private bucket). None on failure. ``upsert=False``
    (development modules S10 review) signs it with `x-upsert: false`, so the URL can never overwrite an
    object already at the key — a file checked and recorded cannot be swapped later without a new check.
    Every caller passes ``upsert=False`` since audit A1.7 (the student documents and request
    attachments joined the development modules); the bucket's type / size limits are the live step
    in ``docs/security/2026-11-06-b40-documents-bucket-limits.sql`` (TD-467)."""
    headers = {'x-upsert': 'true' if upsert else 'false'} if upsert is not None else None
    result = _post(f'/object/upload/sign/{BUCKET}/{path}', {}, headers=headers)
    rel = (result or {}).get('url')
    return f'{_base_url()}/storage/v1{rel}' if rel else None


def create_signed_download_url(path, expires_in=3600):
    """Time-limited signed URL to view a private object. None on failure."""
    result = _post(f'/object/sign/{BUCKET}/{path}', {'expiresIn': expires_in})
    rel = (result or {}).get('signedURL') or (result or {}).get('signedUrl')
    return f'{_base_url()}/storage/v1{rel}' if rel else None


def create_signed_download_urls(paths, expires_in=3600):
    """Signed URLs for MANY private objects in ONE call (Supabase's batch sign,
    `POST /object/sign/{bucket}` with `paths`): ``{path: url}`` for every path signed, missing for
    a path Supabase refused, ``{}`` on any failure or with nothing to sign. A list page signs its
    rows with this, never with one call per row (common profile S2: the Team page's photos)."""
    paths = sorted({p for p in (paths or []) if p})
    if not paths:
        return {}
    result = _post(f'/object/sign/{BUCKET}', {'expiresIn': expires_in, 'paths': paths})
    if not isinstance(result, list):
        return {}
    out = {}
    for item in result:
        rel = (item or {}).get('signedURL') or (item or {}).get('signedUrl')
        if rel and not (item or {}).get('error') and item.get('path') in paths:
            out[item['path']] = f'{_base_url()}/storage/v1{rel}'
    return out


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


def download_object(path, max_bytes=None):
    """Fetch the raw bytes of one private object via the service key. None on failure.

    Used by the off-platform backup command (backup_documents). Best-effort; the
    path is never logged (it can embed application ids). ``max_bytes`` (development modules S10)
    stops reading after that many bytes, so a check of an upload's size and type never holds an
    oversize object in memory: the caller reads ``max_bytes + 1`` to tell "too big" from "exactly".
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
            return resp.read(max_bytes) if max_bytes else resp.read()
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
