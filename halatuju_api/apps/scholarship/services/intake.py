"""
Resolving a programme/round, creating an application, scoring and releasing it.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from datetime import timedelta

from django.utils import timezone

from ..emails import (
    send_acknowledgement_email, send_decline_email, send_pass_email,
)
from ..models import ScholarshipApplication, ScholarshipCohort
from ..shortlisting import evaluate
from .errors import AmbiguousOpenCohort
from .profile_sync import _APP_FIELDS, build_intake_snapshot, sync_profile_fields



def resolve_programme_by_code(code):
    """Which GIFT does this code mean? Live code first, a retired ALIAS only as a fallback.

    ⚠ THE ONE HOME FOR THAT QUESTION. It was written inline inside `resolve_open_cohort`, which
    meant only the OPEN-ROUND path understood a retired code — so the apply page's own gate and
    its copy would have disagreed with the round it was about to file the student against. Both
    callers go through here now.

    ⚠ A RETIRED CODE STILL WORKS, AND THIS IS THE ONLY PLACE THAT IS TRUE. `Programme.code` may
    be renamed; the old code is kept as a `ProgrammeCodeAlias` so every poster and forwarded link
    already in circulation keeps resolving. Without it a rename would make those links read "no
    open round" — silently, with no error to notice.

    ⚠ LIVE CODE FIRST, ALIAS ONLY AS A FALLBACK. `code_is_free` forbids the collision, so the
    order cannot change an answer today; it is written this way so that if a collision ever did
    exist the CURRENT owner of a code wins, never a ghost of it.

    ⚠ IT ANSWERS ABOUT ANY GIFT, ACTIVE OR NOT, OPEN OR CLOSED. Narrowing is the CALLER's job —
    `resolve_open_cohort` still applies `is_active`, and the public intake endpoint needs a
    closed gift to stay identifiable so it can answer "closed" about the RIGHT one.

    Returns a `Programme` or None. Never raises, never widens anything: an alias resolves to
    exactly one programme.
    """
    from ..models import Programme, ProgrammeCodeAlias
    code = (code or '').strip()
    if not code:
        return None
    p = Programme.objects.filter(code=code).first()
    if p is not None:
        return p
    alias = (ProgrammeCodeAlias.objects
             .filter(code=code)
             .select_related('programme')
             .first())
    return alias.programme if alias else None


def resolve_open_cohort(cohort_code='', programme_code=''):
    """
    Return the cohort to apply to. An explicit code wins; otherwise THE one open round —
    narrowed to `programme_code` when the apply link named a programme.

    Returns None when nothing matches — a closed intake is a normal state with its own message.

    ⚠ PF-1. This used to answer "the most recent active+open cohort" with `.first()` on a
    `-year, code` sort, which is a platform-wide question. The caller uses the answer to decide
    which round a student JOINS, and `ScholarshipApplication.save()` denormalises
    `owning_organisation` from it — so with two organisations open, a student applying to B was
    filed under A: visible to A's staff, invisible to B's, funded from A's money, and **no error
    anywhere**. `.first()` over an unscoped set is not a tie-break, it is a guess about tenancy.

    It now RAISES on ambiguity rather than picking. A student who sees "we could not tell which
    programme you are applying to" writes a support message; a student filed under the wrong
    foundation is a refund and an apology.

    Deliberately NOT resolved by narrowing on the referring organisation: `PartnerAdmin.org` /
    `referred_by_org` mean the REFERRING org (attribution), never ownership — the model docstring
    on `ScholarshipCohort.owning_organisation` says so. A school that refers a student is not the
    foundation funding them.

    Ambiguity is counted across ALL open rounds, not per organisation, because "which round?" is
    equally unanswerable between two intakes of the SAME organisation. One rule, one layer.

    An explicit code is returned WITHOUT checking `is_open` — `views.py` re-checks and explains
    that the round has closed, which is a different and more useful message than "no open round".

    ── `programme_code` (PF-1 P2) ───────────────────────────────────────────────────────────
    The owner's answer to "how does an application know which organisation?": each organisation
    gets its own apply link carrying its PROGRAMME code (`Programme.code`, already a unique
    URL-safe slug). Programme, not cohort: a cohort code is year-specific (`b40-2026`), so a link
    pinned to one would rot every intake, whereas a programme never lapses — that is the level's
    whole purpose (`Programme` docstring).

    ⚠ It is OPTIONAL, which deliberately departs from the standing "make a new scoping dimension
    REQUIRED, never optional-with-a-default" lesson (`sponsor_balance`, P2a). That lesson is about
    a parameter whose ABSENCE SILENTLY CHANGES AN ANSWER — a pooled balance that still looks
    plausible. Here absence no longer produces an answer at all: it raises. The guard is the
    refusal above, not the signature, and making it required would break the bare `/apply` link
    that is correct and sufficient while one programme runs.

    Narrowing by programme does NOT make it a fence. The organisation fence is unchanged; this
    only decides which round a NEW application joins.
    """
    if cohort_code:
        return ScholarshipCohort.objects.filter(code=cohort_code).first()

    qs = ScholarshipCohort.objects.filter(is_active=True, is_open=True)
    if programme_code:
        p = resolve_programme_by_code(programme_code)
        # An unknown/inactive programme narrows to nothing → None → "no open round", which is
        # the honest answer for a link naming a programme that is not running.
        qs = qs.filter(programme=p, programme__is_active=True) if p else qs.none()
    qs = qs.order_by('-year', 'code')

    open_cohorts = list(qs[:2])
    if not open_cohorts:
        return None
    if len(open_cohorts) > 1:
        # Re-read unsliced so the error names every candidate, not just the two we fetched.
        raise AmbiguousOpenCohort(qs.values_list('code', flat=True))
    return open_cohorts[0]


def create_application(*, profile, cohort, validated_data, to_email, lang='en'):
    """
    Submit an application:
      1. write the form's financial fields back to the canonical profile,
      2. create the application with per-application fields only,
      3. freeze an intake snapshot (audit evidence),
      4. send the acknowledgement email and stamp ``acknowledged_at``.
    Returns the created application.
    """
    data = dict(validated_data)
    # Both are ROUTING inputs, not application data: they chose the cohort above and have no
    # place on the row or in the frozen intake snapshot (the cohort FK already records the answer).
    data.pop('cohort_code', None)
    data.pop('programme_code', None)

    # 1. Profile is the single source of truth — sync financial fields to it.
    sync_profile_fields(profile, data)

    # 2. Create the application from per-application fields only; academic +
    #    financial data is read live from the profile by the shortlist engine.
    app_fields = {k: data[k] for k in _APP_FIELDS if k in data}
    # Stamp when the truthfulness declaration was signed (only if a signature was given).
    signed = (app_fields.get('declaration_name') or '').strip()

    # Promote the declaration signature — the name the student deliberately typed
    # "as in their IC" on the truthfulness declaration — to the canonical profile
    # name. It is the most reliable name we hold: the About Me field is pre-filled
    # from the Google sign-in display name (often a handle like "Sharmila 1204") and
    # can ride through unchanged, whereas the declaration is a deliberate, gated
    # capture. Promoting it means profile.name carries the real legal name from
    # submit onward, so every identity check, email and sponsor profile reads it
    # correctly. Stored verbatim (the admin views upper-case it via _full_name).
    if signed and profile is not None and (getattr(profile, 'name', '') or '').strip() != signed:
        profile.name = signed
        profile.save(update_fields=['name', 'updated_at'])

    application = ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile,
        locale=lang if lang in ('en', 'ms', 'ta') else 'en',
        notify_email=to_email or '',
        intake_snapshot=build_intake_snapshot(profile, data),
        declared_at=timezone.now() if signed else None,
        **app_fields,
    )

    sent = send_acknowledgement_email(
        to_email=to_email,
        applicant_name=getattr(profile, 'name', '') if profile else '',
        programme_name=cohort.name,
        lang=lang,
    )
    if sent:
        application.acknowledged_at = timezone.now()
        application.save(update_fields=['acknowledged_at'])

    return application


def score_application(application):
    """
    Score a freshly-submitted application **silently** (S8 delayed reveal): run the
    engine, store verdict + bucket + reason, and set ``decision_due_at`` =
    submitted_at + the cohort's success/decline delay. Status stays ``submitted`` and
    NO email is sent — the scheduler reveals the verdict later via ``release_decision``.
    Returns the ShortlistResult.
    """
    cohort = application.cohort
    result = evaluate(application, cohort)
    delay_h = cohort.success_delay_hours if result.verdict == 'shortlisted' else cohort.decline_delay_hours
    base = application.submitted_at or timezone.now()
    application.verdict = result.verdict
    application.bucket = result.bucket
    application.shortlist_reason = result.reason
    # Engine-set rejection bucket (merit/need/ineligible) — drives the decline email
    # at reveal. Blank when shortlisted.
    application.rejection_category = result.category
    application.decision_due_at = base + timedelta(hours=delay_h)
    application.save(update_fields=[
        'verdict', 'bucket', 'shortlist_reason', 'rejection_category', 'decision_due_at',
    ])
    return result


def release_decision(application):
    """
    Reveal a scored application's verdict (called by the scheduler once
    ``decision_due_at`` has passed): flip status to the verdict, stamp timestamps,
    unlock the follow-up for shortlisted students, and send the verdict email
    (invitation for shortlisted, warm decline for rejected). Idempotent — a second
    call on an already-released or unscored application is a no-op. Returns True if it released.
    """
    if application.decision_released_at or application.status != 'submitted' or not application.verdict:
        return False
    now = timezone.now()
    application.status = application.verdict
    application.decision_released_at = now
    if application.verdict == 'shortlisted':
        application.shortlisted_at = now
        # Start the completion-reminder clock at the invitation (R1 fires +2 days).
        application.reminder_anchor_at = now
    application.save(update_fields=['status', 'decision_released_at', 'shortlisted_at',
                                    'reminder_anchor_at'])

    name = getattr(application.profile, 'name', '') if application.profile else ''
    common = dict(to_email=application.notify_email, applicant_name=name,
                  programme_name=application.cohort.name, lang=application.locale)
    # Bill the decision email to the application's owning organisation — this runs from the
    # release cron, which carries no ambient context, so the meter would otherwise record NULL.
    from .. import usage as _usage
    with _usage.usage_context(application=application):
        if application.verdict == 'shortlisted':
            sent = send_pass_email(**common)
        else:
            # Pre-shortlist decline: pick the bucket-specific email (merit/need) or the
            # generic one (ineligible). The engine set rejection_category at score time.
            sent = send_decline_email(category=application.rejection_category, **common)
    if sent:
        application.decision_email_sent_at = now
        application.save(update_fields=['decision_email_sent_at'])
    return True


def rescore_pending_decisions():
    """Re-score every application whose decision has NOT been released yet, applying
    the CURRENT shortlisting engine. Use after a threshold/policy change so pending
    applicants are judged by the new rule before their verdict goes out. Decisions
    already released (and emailed) are NEVER touched. Returns a summary of any flips."""
    pending = list(
        ScholarshipApplication.objects
        .filter(status='submitted', decision_released_at__isnull=True)
        .select_related('cohort', 'profile')
    )
    changed = []
    for application in pending:
        before = application.verdict
        result = score_application(application)
        if result.verdict != before:
            changed.append({
                'id': application.id, 'from': before or '(unscored)',
                'to': result.verdict, 'reason': result.reason,
            })
    return {'rescored': len(pending), 'changed': changed}
