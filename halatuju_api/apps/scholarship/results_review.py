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
import re

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
#: A storage key longer than this is not one the sign-upload door issued.
_MAX_SLIP_PATH = 200


class ResultsError(Exception):
    """A refused results write: `code` is machine-readable for the view."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def accepted(qs):
    """THE rule: the results that count — accepted ones. `qs` is a SemesterResult queryset or a
    related manager (`application.semester_results`). Every judging reader goes through here; the
    doors test (`test_results_review.TestTheDoorsAreTheListedOnes`) fences the call sites."""
    return qs.filter(review_status=ACCEPTED)


def latest_accepted(application):
    """Her latest ACCEPTED result. "Latest" = latest SUBMITTED (newest `created_at`, `-id` breaking a
    tie) until S4b stamps `term_index`; then it becomes the latest TERM (roadmap 4b)."""
    return accepted(application.semester_results).order_by('-created_at', '-id').first()


def accepted_count(application):
    """How many results count — the sponsor's semester figures."""
    return accepted(application.semester_results).count()


def has_pending(application):
    """A result is waiting for an officer."""
    return application.semester_results.filter(review_status=PENDING).exists()


def slip_locked(document):
    """A results slip is EVIDENCE: once recorded the student can neither delete nor replace it,
    whatever the review says. True for any in-programme slip, and for any document a result names."""
    return (document.request_code == SLIP_REQUEST_CODE
            or SemesterResult.objects.filter(results_slip=document).exists())


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
    path = upload.get('storage_path')
    # The exact shape the sign-upload door issues: `<this application's slip prefix>/<32 hex>`.
    # Nothing else — no `..`, no sub-folder, no other student's or type's prefix, no long tail.
    prefix = build_doc_key(application, application.id, 'semester_result')
    if (not isinstance(path, str) or len(path) > _MAX_SLIP_PATH or '..' in path
            or not re.fullmatch(re.escape(prefix) + r'/[0-9a-f]{32}', path)):
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
    accepted). Writes `result_reviewed` to the activity log in the same transaction.

    ⚠ OWNER RULING 2026-10-29 ("Students must upload at the portal. Emailed docs are not allowed."):
    a result with no slip cannot be ACCEPTED (`slip_required`) — the officer QUERIES it instead, so
    she is asked to upload it. Nothing lets staff attach a document for her."""
    if decision not in DECISIONS:
        raise ResultsError('bad_decision')
    text = (note or '').strip()[:500]
    if decision == QUERIED and not text:
        raise ResultsError('note_required')
    if decision == ACCEPTED and result.results_slip_id is None:
        raise ResultsError('slip_required')
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
        # S4b: an accepted result meets her oldest open result term; one no longer accepted
        # reopens the term it met (`results_expectations`).
        from . import results_expectations
        if decision == ACCEPTED:
            results_expectations.reconcile(result.application)
        elif old == ACCEPTED:
            results_expectations.unlink(result)
    return result


def results_for_file(application):
    """Every result, newest first, for the officer's Results tab."""
    return (SemesterResult.objects.filter(application=application)
            .select_related('results_slip').order_by('-created_at', '-id'))
