"""A funded student's semester results — recorded, reviewed, and the ONE rule for which count
(student maintenance Sprint 4a, 2026-10-29).

⚠ ONLY AN ACCEPTED RESULT COUNTS. A student types her CGPA and attaches her slip; it is
``pending`` until an officer ACCEPTS it (or QUERIES it, with a note she sees). Every reader that
judges or reports progress reads ``accepted(...)`` and nothing else — standing (``standing.py``),
the sponsor progress band (``pool.derive_progress_state``), the sponsor's portfolio badge and
semester count, the impact total and the activity feed. A self-reported number never reaches a
sponsor unreviewed (S1 review M2). The doors are listed in ``docs/decisions.md`` (2026-10-29, S4a).

THE SLIP. The student signs an upload (``scholarship/documents/sign-upload/``, doc type
``semester_result``) and PUTs the file; the result POST then names that storage path and THIS
module records the document — NOT the general document door, whose pre-award pipeline (the
Gemini read, the Check-2 asks, the slot that supersedes the previous copy) belongs to an
application under review, not to a funded student's tenth slip. The row carries
``request_code='in_programme'`` so it is its own slot and never resolves a pre-award request.
"""
from django.db import transaction
from django.utils import timezone

from . import activity
from .models import ApplicantDocument, SemesterResult
from .models.activity import EVENT_RESULT_REVIEWED

ACCEPTED = 'accepted'
QUERIED = 'queried'
PENDING = 'pending'
DECISIONS = (ACCEPTED, QUERIED)
#: The slot code an in-programme slip carries (never an officer request's `officer_N`).
SLIP_REQUEST_CODE = 'in_programme'


class ResultsError(Exception):
    """A refused results write: `code` is machine-readable for the view."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def accepted(qs):
    """THE rule: the results that count — accepted ones. `qs` is a SemesterResult queryset or a
    related manager (`application.semester_results`)."""
    return qs.filter(review_status=ACCEPTED)


def latest_accepted(application):
    return accepted(application.semester_results).order_by('-created_at', '-id').first()


def record_slip(application, upload):
    """Record a slip the student has PUT to storage. `upload` = {storage_path, original_filename,
    content_type, size}. Refuses a path outside this application's own prefix (`bad_slip`), a
    file that is not an image or a PDF (`unsupported_format`), one over the organisation's size cap
    (`file_too_large`), or a blob that never landed (`upload_incomplete`)."""
    from apps.courses import org_config
    from .storage import build_doc_key, object_exists
    from .views import _is_allowed_upload
    if not isinstance(upload, dict):
        raise ResultsError('bad_slip')
    path = str(upload.get('storage_path') or '')
    if not path.startswith(build_doc_key(application, application.id, 'semester_result') + '/'):
        raise ResultsError('bad_slip')
    name = str(upload.get('original_filename') or '')[:255]
    content_type = str(upload.get('content_type') or '')[:100]
    if not _is_allowed_upload(content_type, name):
        raise ResultsError('unsupported_format')
    size = upload.get('size') if isinstance(upload.get('size'), int) else 0
    if size > org_config.max_doc_size_bytes(application.owning_organisation):
        raise ResultsError('file_too_large')
    if object_exists(path) is False:
        raise ResultsError('upload_incomplete')
    return ApplicantDocument.objects.create(
        application=application, doc_type='semester_result', storage_path=path,
        original_filename=name, content_type=content_type, size=size,
        request_code=SLIP_REQUEST_CODE)


def review(result, *, decision, note='', by_email=''):
    """An officer ACCEPTS or QUERIES a result. A query needs a note (the student is told why); an
    accept may carry one. Re-reviewing is allowed (a queried result the student explained may be
    accepted). Writes `result_reviewed` to the activity log in the same transaction."""
    if decision not in DECISIONS:
        raise ResultsError('bad_decision')
    text = (note or '').strip()[:500]
    if decision == QUERIED and not text:
        raise ResultsError('note_required')
    with transaction.atomic():
        old = result.review_status
        result.review_status = decision
        result.review_note = text
        result.reviewed_by = (by_email or '')[:254]
        result.reviewed_at = timezone.now()
        result.save(update_fields=['review_status', 'review_note', 'reviewed_by', 'reviewed_at'])
        activity.log_event(result.application, EVENT_RESULT_REVIEWED, actor_email=by_email, meta={
            'result_id': result.id, 'semester': result.semester, 'old': old, 'new': decision,
            'cgpa': str(result.cgpa) if result.cgpa is not None else None})
    return result


def results_for_file(application):
    """Every result, newest first, for the officer's Results tab."""
    return (SemesterResult.objects.filter(application=application)
            .select_related('results_slip').order_by('-created_at', '-id'))
