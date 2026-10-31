"""
Which stages may still be queried, and submitting an interview.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.utils import timezone


# S4: querying (officer queries + doc requests) closes once the interview is concluded.
QUERYING_LOCKED_STATUSES = ('interviewed', 'recommended', 'awarded', 'active', 'maintenance', 'closed', 'rejected', 'withdrawn', 'expired')


def querying_locked(application):
    """True once the interview is concluded — decision time, no more queries/documents.
    Fires when the application has advanced past the interview OR a submitted interview
    session exists (covers the moment of submit before any further status change).
    EXCEPTION: a REOPENED decision reopens the whole case for revision, so querying is
    unlocked again (mirrors the cockpit's decisionReopened)."""
    if application.decision_reopened_at is not None:
        return False
    if application.status in QUERYING_LOCKED_STATUSES:
        return True
    return application.interview_sessions.filter(status='submitted').exists()


# ── WHO MAY ASK THE STUDENT ANYTHING, AND WHEN (owner, 2026-07-13) ────────────
# The single source of truth. Read the two predicates together:
#
#   Shortlisted            —  nobody. The student is still filling in Step 4, and the Action
#                             Centre doesn't even render until they submit, so an officer ticket
#                             raised here would be invisible — a question nobody can see or answer.
#   Completed              —  MACHINE + OFFICER. The only stage the machine may ask.
#   Interviewing           —  OFFICER only. The case now belongs to a human; auto-generated
#                             questions stop, so the reviewer isn't fighting the system.
#   Awaiting QC (interviewed) — nobody. The interview is concluded; it's decision time.
#   Recommended onward     —  nobody, and whatever is still open is SET ASIDE (struck through,
#                             not a to-do) — see views.SET_ASIDE_STATES.
#   Rejected / withdrawn / expired / closed — nobody.
#
# A REOPENED decision lands the case back in `interviewing` (or `interviewed`), so it follows the
# same rules by status alone — deliberately NOT via the querying_locked reopen exception, which
# would otherwise let the machine start asking a reopened case fresh questions.
AUTO_QUERY_STATUSES = ('profile_complete',)
OFFICER_QUERY_STATUSES = ('profile_complete', 'interviewing')


def auto_queries_allowed(application):
    """May the SYSTEM raise a new query / document request? Only during the Completed stage.

    Gates the CREATE branches of ``resolution.sync_resolution_items`` and
    ``check2_queries.sync_check2_queries``. Housekeeping (auto-resolving an open item once its gap
    clears) is NOT gated — it runs at every stage, so a student who supplies a missing document
    still sees the task tick green. An item already open when the student moves on stays open and
    answerable; we asked it in good faith and we don't withdraw it (owner, 2026-07-13).
    """
    return (application.profile_completed_at is not None
            and application.status in AUTO_QUERY_STATUSES)


def officer_queries_allowed(application):
    """May an OFFICER raise a query / document request? Completed + Interviewing only.

    Blocks `shortlisted` (the student cannot see the Action Centre yet, so the ask would be a dead
    end) and everything from `interviewed` onward (the interview is concluded — decision time).
    """
    return (application.profile_completed_at is not None
            and application.status in OFFICER_QUERY_STATUSES)


def officer_requests_state(application):
    """What the cockpit's raise-a-query / request-a-document controls should offer, SERVED so the
    web never re-derives the stage list (request #40). One of:

      * ``'open'``           — ``officer_queries_allowed``: the endpoint will accept a request.
      * ``'documents_step'`` — refused because the student has not finished their own Documents
                               step (no ``profile_completed_at``, case still live). What they owe is on the
                               Blockers list and they are already being asked for it.
      * ``'closed'``         — refused for any other stage reason.

    Read off the SAME predicate the endpoint refuses on, so the two cannot disagree.
    """
    if officer_queries_allowed(application):
        return 'open'
    # A case that ended before finishing documents (expired, rejected) is closed, not waiting.
    if application.profile_completed_at is None and not querying_locked(application):
        return 'documents_step'
    return 'closed'


def _maybe_autofinalise(application, session):
    """S4: on interview submit, refine the draft into the final polished profile from the
    findings — gated behind CHECK2_AUTO_GENERATE (dark by default; billable Gemini call),
    idempotent (skips with no draft or an existing final), best-effort (never raises)."""
    from django.conf import settings as _settings
    if not getattr(_settings, 'CHECK2_AUTO_GENERATE', False):
        return
    try:
        from ..models import SponsorProfile
        from ..profile_engine import refine_sponsor_profile
        sp = SponsorProfile.objects.filter(application=application).first()
        if sp is None or not sp.current_markdown.strip() or sp.final_markdown.strip():
            return  # need a draft; never re-finalise an existing final
        result = refine_sponsor_profile(application, draft=sp.current_markdown, session=session)
        if 'error' in result:
            return
        sp.final_markdown = result['markdown']
        sp.final_model_used = result.get('model_used', '')
        sp.prompt_version = result.get('prompt_version', '')
        sp.finalised_at = timezone.now()
        sp.save()
    except Exception:
        pass  # never let auto-finalise break interview submission


def submit_interview(session, actor=None):
    """Phase C: finalise an interview session. Marks it submitted and moves the
    application into the reviewer's working state ('interviewing'). Idempotent on the
    session status. Returns True if it advanced the application.

    QC (2026-07): submitting FINDINGS no longer advances to 'interviewed'. 'interviewed'
    is now the AWAITING-QC stage, reached only when the reviewer submits the full verdict
    (verify-accept). A findings-submitted case sits in 'interviewing' until then — querying
    still locks here via ``querying_locked``'s submitted-session check (no regression).

    S4: submitting also auto-finalises the polished profile from the findings (gated +
    best-effort — see _maybe_autofinalise) and is the point querying locks.

    ``actor`` — the admin who pressed Submit (the view passes it), who is NOT always the session's
    ``interviewer`` (lessons.md 2026-08-02) — gets an `interview_submitted` row on their own activity
    list (common profile S3), once: a re-submit of a submitted session writes nothing."""
    now = timezone.now()
    submitted_now = session.status != 'submitted'
    if submitted_now:
        session.status = 'submitted'
        session.submitted_at = now
        session.save(update_fields=['status', 'submitted_at'])
    app = session.application
    advanced = False
    # Submitting the session is the OFFLINE-interview fallback trigger for 'interviewing'
    # (when no times were proposed in-app). Same precondition as the propose trigger: an
    # ACCOUNTABLE assigned reviewer must exist — never advance an unassigned case (keeps the
    # invariant "interviewing ⇒ assigned_to set"). See docs/decisions.md.
    if app.status == 'profile_complete' and app.assigned_to_id is not None:
        app.status = 'interviewing'
        app.save(update_fields=['status'])
        advanced = True
    if submitted_now:
        from .. import staff_activity
        staff_activity.record(actor, staff_activity.INTERVIEW_SUBMITTED, app, meta=lambda: {
            'session': session, 'interviewer': session.interviewer_id})
    _maybe_autofinalise(app, session)
    return advanced
