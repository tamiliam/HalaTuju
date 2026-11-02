"""Development modules — the FILES (student maintenance Sprint 10, 2026-11-02): a lesson's file (staff) and a
scholar's uploaded task. The document vault's own pattern, reused, never a new path:

- THE BUCKET: the private `b40-documents` (`storage.py`). Bytes go browser -> Storage on a signed upload URL
  (`storage.create_signed_upload_url`, as the document and results-slip uploads do); only a short signed
  download URL (`SIGNED_FOR` seconds) is ever served, minted on a tap. NEVER a public URL.
- THE KEYS (organisation-prefixed, the tenant fence of `storage.build_doc_key`):
    lesson file  `<org>/development/<module>/<32 hex>`
    her task     `<org>/<app>/growth-<module>/<32 hex>`  (`build_doc_key(app, app.id, ...)` — HER own path)
  The record step accepts ONLY the exact shape this module issued for THAT module (and, for a task, THAT
  application) — no `..`, no other folder, no other student's or module's prefix.
- THE CHECK (`verify`): the object is read back (at most `MAX_BYTES + 1` bytes) and its TYPE is decided by
  the bytes (`sniff`: PDF, JPEG or PNG), never by the file name or the browser's word; its SIZE is the bytes'
  length. A file that fails either is DELETED and refused. Nothing is recorded before it passes.
- OLD FILES: a replaced or removed file is deleted once the change commits (`discard_after_commit`); if
  Storage refuses, the warning names it and the orphan sweep (`cleanup_orphan_blobs`, which knows both
  columns) finds it.
"""
import logging
import re
import uuid

from django.db import transaction

from . import storage
from .development import DevelopmentError, _locked_module
from .storage import build_doc_key

logger = logging.getLogger('apps.scholarship.development_files')

#: PDF / JPEG / PNG, up to 10 MB (owner ruling, 2026-11-02) — for a lesson file and her upload alike.
MAX_BYTES = 10 * 1024 * 1024
SIGNED_FOR = 300            # seconds a served file link lives
_MAX_PATH = 300
_HEX = r'[0-9a-f]{32}'


class FileError(DevelopmentError):
    """A refused file, with a stable code — a `DevelopmentError`, so every door answers it the same way."""


def sniff(data):
    """What the bytes ARE: `application/pdf`, `image/jpeg`, `image/png`, or None."""
    head = bytes(data[:8]) if data else b''
    if head.startswith(b'%PDF-'):
        return 'application/pdf'
    if head.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    return None


def clean_name(raw):
    """The name to show (never trusted for anything): one line, at most 255 characters."""
    name = raw.strip() if isinstance(raw, str) else ''
    name = ''.join(c for c in name if c.isprintable() and c not in '/\\')
    return name[:255] or 'file'


def lesson_prefix(m):
    return f'{m.organisation_id}/development/{m.id}'


def task_prefix(app, m):
    return build_doc_key(app, app.id, f'growth-{m.id}')


def _matches(prefix, path):
    return (isinstance(path, str) and len(path) <= _MAX_PATH and '..' not in path
            and re.fullmatch(re.escape(prefix) + '/' + _HEX, path) is not None)


def is_lesson_path(m, path):
    return _matches(lesson_prefix(m), path)


def is_task_path(app, m, path):
    return _matches(task_prefix(app, m), path)


def _upload_url(prefix, size):
    """`{upload_url, storage_path}` for one new object under ``prefix``. A size the browser already says is
    over the limit is refused before anything is signed (the bytes are checked again at the record step)."""
    if isinstance(size, int) and not isinstance(size, bool) and size > MAX_BYTES:
        raise FileError('file_too_large')
    path = f'{prefix}/{uuid.uuid4().hex}'
    url = storage.create_signed_upload_url(path)
    if not url:
        raise FileError('storage_unavailable')
    return {'upload_url': url, 'storage_path': path, 'max_bytes': MAX_BYTES}


def lesson_upload_url(m, size=None):
    return _upload_url(lesson_prefix(m), size)


def task_upload_url(app, m, size=None):
    return _upload_url(task_prefix(app, m), size)


def verify(path):
    """`(content_type, size)` of an uploaded object, decided by its BYTES; a failing object is deleted.
    Refusals: `upload_incomplete` (nothing there / Storage unreachable), `file_too_large`,
    `unsupported_format`."""
    data = storage.download_object(path, max_bytes=MAX_BYTES + 1)
    if not data:
        raise FileError('upload_incomplete')
    if len(data) > MAX_BYTES:
        discard([path])
        raise FileError('file_too_large')
    ctype = sniff(data)
    if ctype is None:
        discard([path])
        raise FileError('unsupported_format')
    return ctype, len(data)


def signed_url(path):
    """A `SIGNED_FOR`-second link to one private object, or None (no file / Storage could not sign)."""
    return storage.create_signed_download_url(path, expires_in=SIGNED_FOR) if path else None


def discard(paths):
    """Delete objects now, best-effort. A failure is logged as an orphan for the sweep."""
    paths = [p for p in (paths or []) if p]
    if paths and not storage.delete_objects(paths):
        logger.warning('development: %s object(s) left as orphans for cleanup_orphan_blobs', len(paths))


def discard_after_commit(paths):
    """Delete objects once the surrounding transaction commits (a rolled-back edit deletes nothing)."""
    paths = [p for p in (paths or []) if p]
    if paths:
        transaction.on_commit(lambda: discard(paths))


def attach_lesson_file(m, lesson, path, name):
    """Record a file staff PUT for ONE lesson (a lesson has a video link OR a file, never both). The old file,
    if any, goes after the commit. Refusals: bad_path, video_or_file, and `verify`'s."""
    from .models import ModuleLesson
    if not is_lesson_path(m, path) or ModuleLesson.objects.filter(file_path=path).exclude(pk=lesson.pk).exists():
        raise FileError('bad_path')   # not this module's key, or another lesson's file (one object, one owner)
    ctype, size = verify(path)
    try:
        with transaction.atomic():
            _locked_module(m.pk)
            lesson = ModuleLesson.objects.filter(pk=lesson.pk, module_id=m.pk).first()
            if lesson is None:
                raise DevelopmentError('not_found')
            if lesson.video_url:
                raise DevelopmentError('video_or_file')
            old = lesson.file_path if lesson.file_path != path else ''
            lesson.file_path, lesson.file_name, lesson.file_type, lesson.file_size = path, clean_name(name), ctype, size
            lesson.save()
            discard_after_commit([old])
    except DevelopmentError:
        if not ModuleLesson.objects.filter(file_path=path).exists():   # never the file already on record
            discard([path])
        raise
    return lesson


def remove_lesson_file(m, lesson):
    """Take a lesson's file off; the object goes after the commit."""
    from .models import ModuleLesson
    with transaction.atomic():
        _locked_module(m.pk)
        row = ModuleLesson.objects.filter(pk=lesson.pk, module_id=m.pk).select_for_update().first()
        if row is None or not row.file_path:
            return row
        discard_after_commit([row.file_path])
        row.file_path, row.file_name, row.file_type, row.file_size = '', '', '', 0
        row.save()
    return row
