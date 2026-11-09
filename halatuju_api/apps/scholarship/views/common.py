"""Helpers every student view shares: the caller's own application, the funded states, the
ambiguity refusal and the coach telemetry line."""
import logging

from rest_framework.exceptions import APIException

from apps.courses.models import StudentProfile
from ..models import ScholarshipApplication
from ..services import POST_SHORTLIST_EDITABLE
from ..student_status import live_q

logger = logging.getLogger(__name__)


def _log_coach_serve(kind, app_id, source, verdict):
    """V6 (F1): one telemetry line per Gopal serve so his performance is measurable in Cloud
    Run logs (``served``). `source` = ai | fallback | none. Query:
    ``resource.labels.service_name="halatuju-api" AND "AUDIT coach_serve"``."""
    logger.info('AUDIT coach_serve kind=%s app_id=%s source=%s verdict=%s',
                kind, app_id, source, verdict or '-')


def _get_profile(user_id):
    return StudentProfile.objects.filter(supabase_user_id=user_id).first()


# The funded post-award states. A funded student must still reach the document-upload +
# Action Centre surface — e.g. to upload their bank statement (post-award bank-details
# capture). This is SAFE on the shared surface: revert_if_profile_incomplete only acts on
# 'profile_complete', and switch_income_route never un-submits, so a funded student touching
# these endpoints can't fall out of their funded status.
_FUNDED_STATES = ('awarded', 'active', 'maintenance')


# From RECOMMENDED onward nobody may ask the student anything (see services.auto_queries_allowed /
# officer_queries_allowed), so whatever is still open was the review's to-do list and is no longer
# the student's. Those items are SET ASIDE — shown struck-through/amber, not as a to-do, and not as
# "done" either. Deliberately a SEPARATE constant from _FUNDED_STATES: that one also decides which
# applications a student may reach at all, and widening it would hand recommended students the
# post-award endpoints. (Owner, 2026-07-13: set-aside starts at recommended, not awarded.)
SET_ASIDE_STATES = ('recommended',) + _FUNDED_STATES


class AmbiguousApplication(APIException):
    """The caller holds more than one live application and the request did not say which.

    ⚠ Deliberately an `APIException` rather than the explicit `Response(..., status=409)` this
    module uses everywhere else. The house style would mean a `try/except` at each of the
    thirteen call sites, and the failure mode of forgetting one is a 500 — while the entire point
    of this class is that a FOURTEENTH call site cannot reintroduce the bug. DRF's own handler
    turns this into a 409 without any call site knowing it exists, so new code is safe by default
    rather than by remembering.
    """
    status_code = 409
    default_detail = 'You have more than one application; this request did not say which.'
    default_code = 'application_ambiguous'

    def __init__(self):
        # DRF's handler renders `detail` as the body, and a bare string would give
        # `{"detail": "..."}` — which a client can only string-match on. Passing a dict keeps the
        # `{error, code}` shape every other 409 in this module returns (see `programme_required`),
        # so the front end can branch on the code when M4 gives it a chooser to offer.
        super().__init__({'error': self.default_detail, 'code': self.default_code})


def _current_application(user_id):
    """The caller's ONE live application, or a refusal if that question has no single answer.

    Spans the whole editable funnel (POST_SHORTLIST_EDITABLE) PLUS the funded post-award
    states, so the student can keep uploading documents after confirming their profile,
    while an interview is in progress, AND once funded (to upload bank details etc.).

    ⚠ This used to be `.order_by('-submitted_at').first()`, with "latest wins" written in the
    docstring as though it were a rule. It was not a rule; it was an assumption that held only
    because one cohort had ever existed. It is the same defect PF-1 fixed one layer up
    (`resolve_open_cohort`), and it fails the same way: silently.

    What it costs when it breaks. This resolves "which application is this request about" for
    THIRTEEN endpoints — document sign-upload and listing, consent, bank details, the Action
    Centre. A student holding applications to two programmes uploads their IC for programme B and
    it attaches to whichever they submitted most recently. No error, and the wrong organisation's
    reviewers now hold their document.

    Unreachable today, and the reason is worth stating so nobody "simplifies" this back: the
    unique constraint `(cohort, profile)` excludes only `expired`, so within one cohort a student
    can hold at most one non-expired application — and one cohort exists. Two live applications
    become possible the moment a second programme opens an intake, which is precisely what the
    multi-programme roadmap is for.

    Refusing is not the end state. `docs/plans/2026-07-28-multi-programme-applications-roadmap.md`
    M2 gives the client a way to NAME the application; until something can choose, refusing is the
    honest answer and the safe one — a locked-out upload is recoverable, a document filed under
    another foundation is not. TD-350 (lead ruling): an embargoed decline counts as one of the two, so it plus a live application elsewhere still refuses.
    """
    live = list(
        ScholarshipApplication.objects
        .filter(live_q(POST_SHORTLIST_EDITABLE + _FUNDED_STATES), profile_id=user_id)
        .select_related('profile')
        .order_by('-submitted_at')[:2]
    )
    if not live:
        return None
    if len(live) > 1:
        logger.error(
            'Ambiguous live application for profile %s — multi-programme roadmap M1', user_id,
        )
        raise AmbiguousApplication()
    return live[0]
