"""
Business logic for B40 Assistance Programme intake.

Pure-ish functions kept out of the view (mirrors apps/courses/eligibility_service.py).
"""
from datetime import timedelta

from django.utils import timezone

from .emails import (
    send_acknowledgement_email, send_pass_email, send_fail_email,
    send_decline_email, send_profile_complete_admin_email,
    send_submission_received_email,
)
from .models import (
    ApplicantDocument, Consent, FundingNeed, OnboardingResponse,
    ScholarshipApplication, ScholarshipCohort,
)


class IncompleteProfileError(Exception):
    """Raised when a student tries to confirm a Step-4 profile that isn't complete.
    Carries the completeness dict so the view can tell the FE what's missing."""
    def __init__(self, completeness):
        self.completeness = completeness
        super().__init__('Profile is not complete.')


class OnboardingError(Exception):
    """Raised when a student tries to complete onboarding out of order (e.g. before
    their award has been accepted). Carries a short ``code`` for the view."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


# B40 Phase E/F (F8a): the consent a student records when they finish post-award
# onboarding (acknowledging the programme terms). A free string consent_type — no
# model migration needed (Consent.consent_type is an open CharField).
ONBOARDING_CONSENT_TYPE = 'student_onboarding_ack'


# Post-shortlist states in which the student can still edit Step 4 (add documents,
# revise narrative). Completion is NOT a freeze — the student keeps these abilities
# after confirming, and while an interview is in progress, so an admin can ask for
# more documentation. Excludes terminal states (accepted/rejected/withdrawn).
POST_SHORTLIST_EDITABLE = ('shortlisted', 'profile_complete', 'interviewing', 'interviewed')
# count_spm_a_grades + the A-grade set now live with the shortlisting engine
# (the single place that scores academics). Re-exported here for callers that
# still import it from services.
from .shortlisting import A_GRADES, count_spm_a_grades, evaluate  # noqa: F401

# Financial fields the apply form may collect/refresh. Their canonical home is
# the StudentProfile (HalaTuju onboarding doesn't gather income), so the form
# writes them back to the profile rather than duplicating them on the
# application — avoiding a clash on the hierarchy of truth.
_PROFILE_WRITEBACK_FIELDS = (
    'household_income', 'household_size', 'receives_str', 'receives_jkm',
)

# About Me + My Family scalar fields the apply form now edits inline and commits
# on submit (S9). Same write-back-to-profile rule as the financial fields. NRIC
# is intentionally excluded — it changes only via the validated claim path,
# never an unchecked write (see docs/decisions.md, soft-NRIC).
_PROFILE_ABOUTME_FIELDS = (
    'name', 'school', 'preferred_state', 'contact_phone',
    'preferred_call_language', 'referral_source',
)

# Per-application fields that genuinely belong on the ScholarshipApplication row.
_APP_FIELDS = (
    'intended_pathway', 'intends_tertiary_2026', 'consent_to_contact', 'form_data',
    # Plans + Support intake (Sprint 7); mentoring_candidate is coordinator-set, not collected here.
    'field_of_study', 'pathways_considered', 'top_choices', 'upu_status',
    'other_scholarships', 'other_scholarships_text',
    'help_university', 'help_scholarship', 'anything_else',
    # Plans redesign (context-aware step) — all optional/additive
    'pathway_certainty', 'chosen_pathway', 'pre_u_track', 'pre_u_institution',
    'chosen_programme', 'uncertainty_reasons', 'uncertainty_note',
    # Truthfulness declaration signature (declared_at stamped separately below)
    'declaration_name',
)


def sync_profile_fields(profile, data):
    """
    Write the form's financial + About Me/My Family fields back to the canonical
    profile (commit-on-submit, S9). Only keys that are present and non-None
    overwrite (the form may legitimately omit a field that is already on the
    profile). Parent/guardian details land in the ``guardians`` JSON list, and
    the referring-organisation code resolves to the ``referred_by_org`` FK
    (mirrors ProfileView). NRIC is never written here — claim path only.
    Returns the fields actually changed.
    """
    if profile is None:
        return []
    updated = []
    for field in _PROFILE_WRITEBACK_FIELDS + _PROFILE_ABOUTME_FIELDS:
        if field in data and data[field] is not None:
            if getattr(profile, field, None) != data[field]:
                setattr(profile, field, data[field])
                updated.append(field)

    # Parent/guardian name + phone live in the guardians JSON list.
    if 'guardians' in data and data['guardians'] is not None:
        if profile.guardians != data['guardians']:
            profile.guardians = data['guardians']
            updated.append('guardians')

    # Changing the contact phone invalidates any prior verification (mirrors PUT /profile/).
    if 'contact_phone' in updated:
        profile.contact_phone_verified = False
        updated.append('contact_phone_verified')

    if updated:
        profile.save(update_fields=list(dict.fromkeys(updated)) + ['updated_at'])

    # Resolve the referring-organisation code to a PartnerOrganisation FK. A
    # generic source (whatsapp/google/other) has no row and leaves the FK unset.
    referral = data.get('referral_source')
    if referral:
        from apps.courses.models import PartnerOrganisation
        org = PartnerOrganisation.objects.filter(code=referral, is_active=True).first()
        if org and profile.referred_by_org_id != org.pk:
            profile.referred_by_org = org
            profile.save(update_fields=['referred_by_org'])
            updated.append('referred_by_org')

    return updated


def build_intake_snapshot(profile, app_data):
    """
    Freeze what the applicant declared at submit time — profile-derived academic
    + financial values plus the per-application fields. This is immutable audit
    evidence, NOT the live source of truth (the profile remains canonical).
    """
    p = profile
    return {
        'captured_at': timezone.now().isoformat(),
        'profile': {
            'name': getattr(p, 'name', '') if p else '',
            'school': getattr(p, 'school', '') if p else '',
            'preferred_state': getattr(p, 'preferred_state', '') if p else '',
            'contact_phone': getattr(p, 'contact_phone', '') if p else '',
            'preferred_call_language': getattr(p, 'preferred_call_language', '') if p else '',
            'guardians': getattr(p, 'guardians', []) if p else [],
            'referral_source': getattr(p, 'referral_source', '') if p else '',
            'exam_type': getattr(p, 'exam_type', '') if p else '',
            'grades': getattr(p, 'grades', {}) if p else {},
            'stpm_cgpa': getattr(p, 'stpm_cgpa', None) if p else None,
            'spm_a_count': count_spm_a_grades(getattr(p, 'grades', None) if p else None),
            'household_income': getattr(p, 'household_income', None) if p else None,
            'household_size': getattr(p, 'household_size', None) if p else None,
            'receives_str': bool(getattr(p, 'receives_str', False)) if p else False,
            'receives_jkm': bool(getattr(p, 'receives_jkm', False)) if p else False,
        },
        'application': {
            'intended_pathway': app_data.get('intended_pathway', ''),
            'intends_tertiary_2026': app_data.get('intends_tertiary_2026', True),
            'consent_to_contact': app_data.get('consent_to_contact', False),
            'form_data': app_data.get('form_data', {}),
            'field_of_study': app_data.get('field_of_study', ''),
            'pathways_considered': app_data.get('pathways_considered', []),
            'top_choices': app_data.get('top_choices', []),
            'upu_status': app_data.get('upu_status', ''),
            'other_scholarships': app_data.get('other_scholarships', []),
            'other_scholarships_text': app_data.get('other_scholarships_text', ''),
            'help_university': app_data.get('help_university', ''),
            'help_scholarship': app_data.get('help_scholarship', ''),
            'anything_else': app_data.get('anything_else', ''),
            # Plans redesign (context-aware step)
            'pathway_certainty': app_data.get('pathway_certainty', ''),
            'chosen_pathway': app_data.get('chosen_pathway', ''),
            'pre_u_track': app_data.get('pre_u_track', ''),
            'pre_u_institution': app_data.get('pre_u_institution', ''),
            'chosen_programme': app_data.get('chosen_programme', {}),
            'uncertainty_reasons': app_data.get('uncertainty_reasons', []),
            'uncertainty_note': app_data.get('uncertainty_note', ''),
        },
    }


def resolve_open_cohort(cohort_code=''):
    """
    Return the cohort to apply to. An explicit code wins; otherwise the most
    recent active + open cohort. Returns None if nothing matches.
    """
    if cohort_code:
        return ScholarshipCohort.objects.filter(code=cohort_code).first()
    return (
        ScholarshipCohort.objects
        .filter(is_active=True, is_open=True)
        .order_by('-year', 'code')
        .first()
    )


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
    data.pop('cohort_code', None)

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


# ── Completion reminders + auto-close (the daily reminder job) ────────────────
# Cadence in DAYS from reminder_anchor_at: R1 +2, R2 +9, R3 +23, R4/final +53.
# After the final reminder, a 5-day grace then auto-close (status → 'expired').
REMINDER_THRESHOLDS_DAYS = (2, 9, 23, 53)   # index 0 → R1 … index 3 → R4 (final)
FINAL_REMINDER_GRACE_DAYS = 5               # close this long after R4 was sent


def _elapsed_days_local(now, anchor):
    """Whole CALENDAR days from ``anchor`` to ``now`` in the project timezone
    (Asia/KL). We compare local dates rather than flooring ``(now - anchor)`` so the
    cadence lands on the named day regardless of the anchor's time-of-day vs the fixed
    09:00 daily tick — a 14:30 anchor's R2 (+9) fires on the 9th calendar day at the
    09:00 tick, not the 10th (TD-087)."""
    return (timezone.localtime(now).date() - timezone.localtime(anchor).date()).days


def send_application_reminders(now=None):
    """Send the next due completion reminder to each shortlisted-but-incomplete
    application, and auto-close those that ignored the final reminder. Returns
    ``{'reminded': n, 'closed': n}``.

    Idempotent + burst-proof: a stage is never re-sent (guarded by reminder_stage),
    a completed/expired app drops out of the query, and at most ONE stage advances
    per run — only when its day-threshold is crossed — so even a back-dated anchor
    (the launch backfill) sends one email, not four. The close is gated on
    ``last_reminder_at`` (when the final reminder actually went out), never on raw
    elapsed days, so no application is closed without having received the warning."""
    from .emails import send_reminder_email, send_application_closed_email
    now = now or timezone.now()
    final_stage = len(REMINDER_THRESHOLDS_DAYS)             # 4
    reminded = closed = 0
    qs = (ScholarshipApplication.objects
          .filter(status='shortlisted', profile_completed_at__isnull=True,
                  reminder_anchor_at__isnull=False)
          .select_related('cohort', 'profile'))
    for app in qs:
        name = getattr(app.profile, 'name', '') if app.profile else ''
        common = dict(to_email=app.notify_email, applicant_name=name,
                      programme_name=app.cohort.name, lang=app.locale)
        # Auto-close: the final reminder has been sent AND its 5-day grace elapsed.
        if (app.reminder_stage >= final_stage and app.last_reminder_at
                and (now - app.last_reminder_at).days >= FINAL_REMINDER_GRACE_DAYS):
            app.status = 'expired'
            app.expired_at = now
            app.save(update_fields=['status', 'expired_at'])
            send_application_closed_email(**common)
            closed += 1
            continue
        # Otherwise, send the next stage if its day-threshold is crossed (one per run).
        next_stage = app.reminder_stage + 1                # 1..4
        if next_stage <= final_stage and _elapsed_days_local(now, app.reminder_anchor_at) >= REMINDER_THRESHOLDS_DAYS[next_stage - 1]:
            send_reminder_email(stage=next_stage, **common)
            app.reminder_stage = next_stage
            app.last_reminder_at = now
            app.save(update_fields=['reminder_stage', 'last_reminder_at'])
            reminded += 1
    return {'reminded': reminded, 'closed': closed}


# ── Check 2 STEP 2/3 — the query SLA clock (design §5) ───────────────────────
# Statuses where the post-submit query clock is live (submitted, not yet decided).
QUERY_SLA_ACTIVE_STATUSES = ('profile_complete', 'interviewing', 'interviewed')


def open_clarify_queries(application):
    """The student's still-open Check-2 AI clarify queries (the ones the SLA governs)."""
    return application.resolution_items.filter(source='check2', kind='clarify', status='open')


def query_sla_days(application):
    return getattr(application.cohort, 'query_response_sla_days', 5) or 5


def query_sla(application, now=None):
    """The Check-2 query SLA clock. Starts at submit (``profile_completed_at``).
    Returns ``{active, deadline, lapsed, open_count, days_left}``:
      - active     — there are open clarify queries (the clock is meaningfully running)
      - deadline   — submit + the cohort's SLA days (None before submit)
      - lapsed     — the deadline has passed
      - open_count — open clarify queries
      - days_left  — whole days remaining (negative once lapsed; None before submit)."""
    from datetime import timedelta
    now = now or timezone.now()
    start = application.profile_completed_at
    if start is None:
        return {'active': False, 'deadline': None, 'lapsed': False,
                'open_count': 0, 'days_left': None}
    deadline = start + timedelta(days=query_sla_days(application))
    open_count = open_clarify_queries(application).count()
    return {
        'active': open_count > 0,
        'deadline': deadline,
        'lapsed': now >= deadline,
        'open_count': open_count,
        'days_left': (timezone.localtime(deadline).date() - timezone.localtime(now).date()).days,
    }


def is_ready_for_assignment(application, now=None):
    """STEP 3 trigger / the Check-3 assignment gate (design intro): an application is
    ready when there are NO open clarify queries OR the SLA window has lapsed
    (proceed-as-is, flagged for the reviewer). Never ready before submission."""
    if application.profile_completed_at is None:
        return False
    sla = query_sla(application, now)
    return sla['open_count'] == 0 or sla['lapsed']


# How long after submission to hold the "we have a few questions" email, so it reads as
# a human review rather than an instant bot reply (the owner's call).
QUERY_EMAIL_DELAY_HOURS = 2


def send_due_query_emails(now=None):
    """Frequent sweep (hourly): ~``QUERY_EMAIL_DELAY_HOURS`` after a student submits,
    email them ONCE that a few clarify questions are waiting in their Action Centre — but
    only if questions are actually open (if they answered everything in the form, none).
    The delay is deliberate so it feels like someone reviewed the application. Idempotent
    via ``query_raised_notified_at``. Returns ``{'sent': n}``."""
    from datetime import timedelta
    from django.conf import settings as _settings
    from .check2_queries import sync_check2_queries
    from .emails import send_query_raised_email
    if not getattr(_settings, 'CHECK2_STUDENT_QUERIES_ENABLED', False):
        return {'sent': 0}   # student queries held until the questions are reviewed
    now = now or timezone.now()
    cutoff = now - timedelta(hours=QUERY_EMAIL_DELAY_HOURS)
    sent = 0
    qs = (ScholarshipApplication.objects
          .filter(status__in=QUERY_SLA_ACTIVE_STATUSES,
                  profile_completed_at__isnull=False, profile_completed_at__lte=cutoff,
                  query_raised_notified_at__isnull=True)
          .select_related('cohort', 'profile'))
    for app in qs:
        clarify = [r for r in sync_check2_queries(app) if r.kind == 'clarify']
        if not clarify:
            continue
        name = getattr(app.profile, 'name', '') if app.profile else ''
        send_query_raised_email(
            to_email=app.notify_email, applicant_name=name,
            programme_name=app.cohort.name, n_queries=len(clarify), lang=app.locale)
        app.query_raised_notified_at = now
        app.save(update_fields=['query_raised_notified_at'])
        sent += 1
    return {'sent': sent}


def send_query_reminders(now=None):
    """Daily sweep: nudge submitted students who still have open Check-2 clarify
    queries, once, ~2 days before the SLA deadline. Reuses the trilingual email
    infra. Idempotent via ``query_reminder_at`` (one reminder per application).
    Lapsed apps are NOT emailed (they already proceed-as-is). Returns ``{'reminded': n}``."""
    from django.conf import settings as _settings
    from .emails import send_query_reminder_email
    if not getattr(_settings, 'CHECK2_STUDENT_QUERIES_ENABLED', False):
        return {'reminded': 0}   # student queries held until the questions are reviewed
    now = now or timezone.now()
    sent = 0
    qs = (ScholarshipApplication.objects
          .filter(status__in=QUERY_SLA_ACTIVE_STATUSES,
                  profile_completed_at__isnull=False, query_reminder_at__isnull=True)
          .select_related('cohort', 'profile'))
    for app in qs:
        sla = query_sla(app, now)
        if not sla['active'] or sla['lapsed']:
            continue
        # one nudge, from ~2 days before the deadline onwards.
        if _elapsed_days_local(now, app.profile_completed_at) < max(query_sla_days(app) - 2, 0):
            continue
        name = getattr(app.profile, 'name', '') if app.profile else ''
        send_query_reminder_email(
            to_email=app.notify_email, applicant_name=name,
            programme_name=app.cohort.name, n_queries=sla['open_count'],
            days_left=max(sla['days_left'], 0), lang=app.locale)
        app.query_reminder_at = now
        app.save(update_fields=['query_reminder_at'])
        sent += 1
    return {'reminded': sent}


# ── Check 2 STEP 3 — generate the sponsor-facing profile from available info ──

def generate_ready_profile(application, language=None):
    """STEP 3: generate the (claim-gated) sponsor profile from currently-available
    info and store it as the SponsorProfile draft. Returns ``(sponsor_profile, None)``
    or ``(None, error)``. Shared by the admin 'generate' action and the STEP-3
    auto-trigger so both store identically. Unresolved claims are omitted by the
    generator's claim-gating contract (profile_engine §6)."""
    from .models import SponsorProfile
    from .profile_engine import generate_sponsor_profile
    result = generate_sponsor_profile(application, language=language)
    if 'error' in result:
        return None, result['error']
    sp, _ = SponsorProfile.objects.get_or_create(application=application)
    sp.draft_markdown = result['markdown']
    sp.model_used = result.get('model_used', '')
    sp.generated_at = timezone.now()
    if sp.status == 'published':
        sp.status = 'draft'  # regenerating a published profile reverts it to draft
    sp.save()
    return sp, None


def autogenerate_ready_profiles(now=None):
    """STEP-3 auto-trigger sweep: draft a profile for each submitted application that
    is ready for assignment (no open queries OR SLA lapsed) and has no profile yet.
    **Gated behind ``CHECK2_AUTO_GENERATE`` (default off)** — it makes billable Gemini
    calls, so it stays a manual admin action until deliberately switched on. Idempotent:
    an application with a generated profile is skipped. Returns ``{'generated': n}``."""
    from django.conf import settings as _settings
    if not getattr(_settings, 'CHECK2_AUTO_GENERATE', False):
        return {'generated': 0}
    now = now or timezone.now()
    generated = 0
    qs = (ScholarshipApplication.objects
          .filter(status__in=QUERY_SLA_ACTIVE_STATUSES, profile_completed_at__isnull=False)
          .select_related('cohort', 'profile'))
    for app in qs:
        sp = getattr(app, 'sponsor_profile', None)
        if sp is not None and sp.generated_at is not None:
            continue  # already drafted — never regenerate automatically
        if not is_ready_for_assignment(app, now):
            continue
        _, error = generate_ready_profile(app)
        if error is None:
            generated += 1
    return {'generated': generated}


# Statuses from which an admin may decline a *reviewed* application (bucket 3,
# 'interview'): anyone who cleared the engine and reached the post-shortlist funnel
# but is not yet accepted. Poor documentation is grounds — no formal interview needed.
INTERVIEW_REJECT_FROM = ('shortlisted', 'profile_complete', 'interviewing', 'interviewed')


def admin_reject(application, admin, category):
    """Post-shortlist admin rejection (buckets 3 & 4). Sets status='rejected', stamps
    the category + who/when, and sends the bucket's decline email immediately:
      - 'interview'   (reviewed but not selected) — allowed from a post-shortlist,
                       not-yet-accepted status; sends the extra-thankful email.
      - 'contractual' (failed post-award steps) — allowed only from 'accepted'; sends
                       the generic decline email (admin-typed reason deferred).
    Raises ValueError on a bad category/status combination. Returns True."""
    if category == 'interview':
        if application.status not in INTERVIEW_REJECT_FROM:
            raise ValueError('bad_status')
    elif category == 'contractual':
        if application.status != 'accepted':
            raise ValueError('bad_status')
    else:
        raise ValueError('bad_category')

    now = timezone.now()
    application.status = 'rejected'
    application.rejection_category = category
    application.rejected_at = now
    application.rejected_by = getattr(admin, 'email', '') or ''
    application.save(update_fields=['status', 'rejection_category', 'rejected_at', 'rejected_by'])

    name = getattr(application.profile, 'name', '') if application.profile else ''
    if send_decline_email(
        to_email=application.notify_email or getattr(application.profile, 'contact_email', '') or '',
        applicant_name=name, programme_name=application.cohort.name,
        category=category, lang=application.locale,
    ):
        application.decision_email_sent_at = now
        application.save(update_fields=['decision_email_sent_at'])
    return True


def confirm_profile(application):
    """Phase C: the student explicitly confirms a complete Step-4 profile.

    Flips status shortlisted → profile_complete, stamps ``profile_completed_at``,
    and notifies the admin. Idempotent: a second call on an already-confirmed (or
    further-along) application is a no-op returning False. Raises
    ``IncompleteProfileError`` (carrying the completeness dict) if the profile
    isn't complete. Completion is NOT a freeze — the student keeps editing rights
    (see POST_SHORTLIST_EDITABLE).
    """
    if application.status != 'shortlisted':
        return False  # already confirmed / further along — idempotent no-op
    completeness = application_completeness(application)
    if not completeness['complete']:
        raise IncompleteProfileError(completeness)
    application.status = 'profile_complete'
    application.profile_completed_at = timezone.now()
    application.save(update_fields=['status', 'profile_completed_at'])
    # Best-effort admin notification (never blocks the confirm).
    name = getattr(application.profile, 'name', '') if application.profile else ''
    send_profile_complete_admin_email(application_id=application.id, applicant_name=name,
                                      programme_name=application.cohort.name)
    # Check 2: acknowledge the submission NOW (warm "we've got it, we'll review and
    # revert") and raise the clarify queries SILENTLY. The "we have a few questions"
    # email is deliberately delayed (send_due_query_emails, ~2h later) so it reads as a
    # human review, not an instant bot reply. All best-effort — never blocks the confirm.
    send_submission_received_email(to_email=application.notify_email, applicant_name=name,
                                   programme_name=application.cohort.name, lang=application.locale)
    try:
        from .check2_queries import sync_check2_queries
        sync_check2_queries(application)
    except Exception:  # noqa: BLE001 — query raising must never fail a submission
        import logging
        logging.getLogger(__name__).warning(
            'Check-2 query raise failed for app %s', application.id, exc_info=True)
    return True


def confirm_pathway(application):
    """Record the student's latest offer letter as their FINAL chosen pathway.

    Driven by the student answering the AI-raised ``pathway_confirm`` Action-Centre
    query Yes (no human officer). Writes the offer's programme + institution into
    ``chosen_programme`` and stamps ``pathway_confirmed_at`` so the Pathway verdict
    reads 'verified'. Idempotent-ish (re-confirming just refreshes the snapshot).
    Returns False when there's no offer letter to confirm."""
    from .models import ApplicantDocument
    from .pathway_engine import student_offer_check
    offer = (ApplicantDocument.objects.filter(application=application, doc_type='offer_letter')
             .order_by('-uploaded_at').first())
    if offer is None:
        return False
    chk = student_offer_check(offer)
    cp = dict(application.chosen_programme) if isinstance(application.chosen_programme, dict) else {}
    cp.update({'course_name': chk['programme'], 'institution': chk['institution'],
               'source': 'offer_letter_confirmed'})
    application.chosen_programme = cp
    application.pathway_confirmed_at = timezone.now()
    application.save(update_fields=['chosen_programme', 'pathway_confirmed_at'])
    return True


def revert_if_profile_incomplete(application):
    """Honest-funnel guard: if a ``profile_complete`` application is edited back
    into an incomplete state (e.g. the student deletes a compulsory document, or
    clears a required story field), roll the status back to ``shortlisted`` and
    clear ``profile_completed_at`` so the funnel never shows "complete" on an
    incomplete profile. Only touches ``profile_complete`` — interviewing /
    interviewed / accepted are the admin's to own. Returns True if it reverted.
    """
    if application.status != 'profile_complete':
        return False
    if application_completeness(application)['complete']:
        return False
    application.status = 'shortlisted'
    application.profile_completed_at = None
    application.save(update_fields=['status', 'profile_completed_at'])
    return True


def submit_interview(session):
    """Phase C: finalise an interview session. Marks it submitted and advances the
    application profile_complete/interviewing → interviewed. Idempotent on the
    session status. Returns True if it advanced the application."""
    now = timezone.now()
    if session.status != 'submitted':
        session.status = 'submitted'
        session.submitted_at = now
        session.save(update_fields=['status', 'submitted_at'])
    app = session.application
    if app.status in ('profile_complete', 'interviewing'):
        app.status = 'interviewed'
        app.save(update_fields=['status'])
        return True
    return False


def application_completeness(application):
    """
    Report STEP 1A / STEP 2 progress for a (typically shortlisted) application:
    quiz done (the linked profile has quiz signals), story done (incl. address),
    funding done, documents done, consent done, guardian docs done.
    The sponsor stage (Phase 2) will gate on ``complete``.

    funding_done (S3 redesign + S23): at least one category ticked AND
    programme_months set.
    documents_done (gate v2, 2026-06-05): route-aware + STRICT for a not-yet-
    submitted app — ic + results_slip + offer_letter + the route's compulsory
    income docs (income_doc_blockers). An ALREADY-submitted app keeps the old
    looser bar (grandfathered; see the inline note).
    consent_done (S5): an active Consent row exists.
    address_done (S14): profile has street + postal_code + city (state already
    came from /apply). Stored on the profile, captured in the Story tab.
    guardian_docs_done: always True now — the guardianship letter (non-parent
    guardian of a minor) is optional, not required. (parent_ic stays compulsory
    for everyone via documents_done.)
    complete (S17 finalise): all seven parts done.
    """
    profile = application.profile
    quiz_done = bool(profile and profile.student_signals)
    # Story narrative: aspirations + plans + daily life + worries/support all
    # required (the latter two made compulsory per request — they carry the
    # need-context an interviewer relies on).
    details_done = bool(
        application.aspirations.strip() and application.plans.strip()
        and application.daily_life.strip() and application.fears.strip()
    )
    try:
        fn = application.funding_need
        # S23: programme_months is now compulsory too (the radio group on the
        # Funding tab). The exact figure isn't load-bearing; what matters is
        # the student picked one — otherwise admin can't size the assistance.
        funding_done = bool(fn.categories) and fn.programme_months is not None
    except FundingNeed.DoesNotExist:
        funding_done = False
    present = set(application.documents.values_list('doc_type', flat=True))
    # Gate v2 (2026-06-05): the documents bar is route-aware and STRICT for a not-yet-
    # submitted application — ic + results_slip + offer_letter (now compulsory for all)
    # + the route's compulsory income docs (income_doc_blockers, sourced from the wizard
    # requirement engine). GRANDFATHER: an already-submitted app (profile_completed_at
    # set) keeps the OLD, looser bar (any one of str/salary/epf, no offer letter) so a
    # later edit never trips revert_if_profile_incomplete on the new rules — those 6 are
    # resolved at Check 2 / interview instead.
    if application.profile_completed_at is None:
        # A results slip in a different name is unusable (we can't attribute the results
        # to the student), so it does NOT satisfy the bar — the student must re-upload the
        # correct slip before submitting. 'pending'/'unreadable'/'match' all pass here;
        # only a positive name MISMATCH blocks.
        from .academic_engine import _slip_name_status
        slip = (application.documents.filter(doc_type='results_slip')
                .order_by('-uploaded_at').first())
        slip_name_ok = slip is None or _slip_name_status(slip) != 'mismatch'
        documents_done = (
            {'ic', 'results_slip', 'offer_letter'}.issubset(present)
            and slip_name_ok
            and not income_doc_blockers(application)
        )
    else:
        documents_done = (
            {'ic', 'results_slip', 'parent_ic'}.issubset(present)
            and bool(present & {'str', 'salary_slip', 'epf'})
        )
    consent_done = application.consents.filter(is_active=True).exists()
    address_done = bool(
        profile
        and (profile.address or '').strip()
        and (profile.postal_code or '').strip()
        and (profile.city or '').strip()
    )
    guardian_docs_done = _guardian_docs_done(application, profile, present)
    family_done = _family_done(application)
    return {
        'quiz_done': quiz_done,
        'details_done': details_done,
        'funding_done': funding_done,
        'documents_done': documents_done,
        'consent_done': consent_done,
        'address_done': address_done,
        'guardian_docs_done': guardian_docs_done,
        'family_done': family_done,
        'complete': (quiz_done and details_done and funding_done
                     and documents_done and consent_done and address_done
                     and guardian_docs_done and family_done),
    }


def _family_done(application):
    """Redesign 2026-06: the structured family roster is compulsory. Father + mother
    profession set; their name set UNLESS the profession is deceased/no_contact (an
    absent parent can't always be named); and both sibling counts answered (not None,
    so "0" is a deliberate answer). Already-submitted apps are grandfathered (they
    carry the legacy free-text answers) — mirrors the documents-gate grandfather."""
    if application.profile_completed_at is not None:
        return True
    f_occ = application.father_occupation
    m_occ = application.mother_occupation
    if not f_occ or not m_occ:
        return False
    name_exempt = {'deceased', 'no_contact'}
    if f_occ not in name_exempt and not (application.father_name or '').strip():
        return False
    if m_occ not in name_exempt and not (application.mother_name or '').strip():
        return False
    if application.siblings_in_school is None or application.siblings_in_tertiary is None:
        return False
    return True


def _guardian_docs_done(application, profile, present_doc_types):
    """Always True now. The guardianship letter (for non-parent guardians of a
    minor) used to be a hard requirement, but it is no longer required — a student
    MAY upload one optionally. Kept as a function (and a completeness key) so the
    shape of `application_completeness` is unchanged for the frontend.
    """
    return True


# Vision errors that mean the FILE couldn't be decoded/fetched (a PDF/video/corrupt
# upload, or a storage-fetch glitch) — re-uploading a clear photo/scan fixes it.
# Distinct from a genuine OCR-SERVICE outage (quota/network/unconfigured), where
# re-uploading won't help. Drives the ic_unreadable vs ic_service_down split AND is
# excluded from the outage detector's service-failure count. (TD-080)
_IC_DECODE_ERROR_MARKERS = ('empty image', 'bad image data', 'could not fetch')


def _is_ic_decode_error(err: str) -> bool:
    e = (err or '').lower()
    return any(m in e for m in _IC_DECODE_ERROR_MARKERS)


def _ic_identity_blockers(application):
    """Identity gate on the student's OWN uploaded IC (doc_type='ic').

    The IC is OCR'd once at upload (run_vision_for_document, synchronous), so by
    consent time the vision_* fields are populated or carry an error. Returns the
    relevant blocker code(s):
      - 'ic_service_down'  : the OCR service errored (Vision down / quota / config)
                             → re-uploading won't help; tell the student to retry later.
      - 'ic_unreadable'    : OCR ran but couldn't read the IC (poor image) → re-upload.
      - 'ic_nric_mismatch' : the IC's NRIC doesn't match the profile NRIC.
      - 'ic_name_mismatch' : the IC's name is a different person's (disjoint tokens).
    A 'partial' name (one set a subset of the other — same person, shorter/longer
    form) is NOT blocked: the NRIC is the hard identity key. Empty profile NRIC/name
    are skipped (can't compare). Caller guarantees an 'ic' document exists.
    """
    from .vision import nric_match, name_match
    ic = application.documents.filter(doc_type='ic').order_by('-uploaded_at').first()
    if ic is None or not ic.vision_run_at:
        return ['ic_service_down']  # never processed — treat as a system issue
    if ic.vision_error:
        # A decode/fetch error ("Bad image data." from a PDF/video, "empty image",
        # "could not fetch") means the FILE is the problem → re-upload (ic_unreadable).
        # A genuine service error (module/API/network/quota) → retry later
        # (ic_service_down). Pre-TD-080 this lumped "Bad image data." into
        # service_down, stranding PDF-IC students with a false "system down".
        return ['ic_unreadable'] if _is_ic_decode_error(ic.vision_error) else ['ic_service_down']
    if not (ic.vision_nric or ic.vision_name):
        return ['ic_unreadable']  # OCR succeeded but read nothing usable (poor image)
    out = []
    pnric = (getattr(application.profile, 'nric', '') or '').strip()
    pname = (getattr(application.profile, 'name', '') or '').strip()
    nric_verified = bool(ic.vision_nric and pnric and nric_match(ic.vision_nric, pnric))
    if ic.vision_nric and pnric and not nric_match(ic.vision_nric, pnric):
        out.append('ic_nric_mismatch')
    # Name is a SOFT cross-check. When the NRIC already verifies identity, a name
    # 'mismatch' is almost always an OCR name-extraction miss (the MyKad name line
    # read imperfectly) — NOT a different person — so it must not block consent;
    # the NRIC is the hard identity key. Only block on a name mismatch when the
    # NRIC did NOT verify (a genuine wrong-IC risk). The admin still sees the soft
    # name-mismatch chip either way.
    if not nric_verified and ic.vision_name and pname and name_match(ic.vision_name, pname) == 'mismatch':
        out.append('ic_name_mismatch')
    return out


def detect_vision_outage(window_hours=24):
    """Passive Google-Vision health signal from recent IC / parent_ic OCR outcomes.

    Returns ``(is_down, stats)``. ``is_down`` is True when there were OCR attempts
    in the window and EVERY one carried a service-level error with NOT ONE success
    — i.e. the OCR *service* (not a single blurry image) has been failing for
    everyone who tried. A poor image ('empty image' / read-nothing) is NOT counted
    as a service failure, so a run of bad uploads alone never trips the alert.

    Read-only; no Vision API calls (so the check itself costs nothing). Pair with a
    daily scheduled run so the admin is alerted once a day while an outage persists.
    """
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(hours=window_hours)
    docs = ApplicantDocument.objects.filter(
        doc_type__in=['ic', 'parent_ic'], vision_run_at__gte=cutoff,
    ).only('vision_error', 'vision_nric', 'vision_name')
    attempts = successes = service_failures = 0
    for d in docs:
        attempts += 1
        if not d.vision_error and (d.vision_nric or d.vision_name):
            successes += 1
        elif d.vision_error and not _is_ic_decode_error(d.vision_error):
            service_failures += 1
    is_down = attempts >= 1 and successes == 0 and service_failures >= 1
    return is_down, {
        'window_hours': window_hours, 'attempts': attempts,
        'successes': successes, 'service_failures': service_failures,
    }


def income_doc_blockers(application):
    """The route + selection aware COMPULSORY income documents still missing, as blocker
    codes (gate v2, 2026-06-05). Sourced from ``income_engine`` so the consent gate and
    the student's wizard checklist can never disagree (one source of truth).
      - blank route / no earner-or-member chosen → ``income_incomplete`` (walk the wizard);
      - STR route → STR doc + the earner IC + relationship doc (mother→BC, guardian→letter);
      - salary route → for EVERY selected member: their IC + their salary slip (EPF does
        NOT substitute) + the relationship doc.
    The per-PERSON codes are member-qualified — ``parent_ic_missing:<member>`` and
    ``salary_slip_missing:<member>`` (member = father/mother/guardian/brother/sister) — so
    the consent checklist names each person ("Upload Father's IC"). The frontend splits on
    ``:`` and renders the member name; the household relationship docs (BC / guardianship
    letter) stay un-suffixed. The POST gate only cares that the list is non-empty.
    """
    from .income_engine import (working_members, relationship_doc_for,
                                _member_ic_doc, _cluster_docs)
    route = (getattr(application, 'income_route', '') or '').strip()
    if not route:
        return ['income_incomplete']
    present = set(application.documents.values_list('doc_type', flat=True))
    out = []
    if route == 'str':
        earner = (getattr(application, 'income_earner', '') or '').strip()
        if not earner:
            return ['income_incomplete']
        # Order: STR doc first (the primary income proof), then the earner IC, then the
        # relationship doc — matches the Documents-UI DISPLAY_ORDER (str before parent_ic).
        if 'str' not in present:
            out.append('str_missing')
        if _member_ic_doc(application, earner) is None:
            out.append(f'parent_ic_missing:{earner}')   # names the single STR earner
        rel = relationship_doc_for(earner)          # birth_certificate / guardianship_letter / ''
        if rel and rel not in present:
            out.append(f'{rel}_missing')            # birth_certificate_missing / guardianship_letter_missing
        return out
    # Salary route — every selected working member needs IC + salary slip (+ rel doc).
    members = working_members(application)
    if not members:
        return ['income_incomplete']
    need_bc = need_guard = False
    for m in members:
        # Member-qualified codes so the checklist names each person — IC then salary slip,
        # grouped per member to match the Documents-UI member blocks.
        if _member_ic_doc(application, m) is None:
            out.append(f'parent_ic_missing:{m}')
        if not _cluster_docs(application, m, 'salary_slip').exists():
            out.append(f'salary_slip_missing:{m}')
        rel = relationship_doc_for(m)
        if rel == 'birth_certificate' and 'birth_certificate' not in present:
            need_bc = True
        elif rel == 'guardianship_letter' and 'guardianship_letter' not in present:
            need_guard = True
    if need_bc:
        out.append('birth_certificate_missing')
    if need_guard:
        out.append('guardianship_letter_missing')
    return out


def consent_blockers(application):
    """Every gate that must pass BEFORE consent can be given, as a list of blocker
    codes (empty list = ready). Consent is the final step: the profile must be
    complete, the required documents uploaded (route-aware income docs + a compulsory
    offer letter), and the uploaded IC must be machine-readable AND match the student's
    name + NRIC. Each code has a matching i18n label on the frontend, so the student
    sees ALL outstanding items at once and can fix them in one pass. The ConsentView
    POST enforces this list; the minor guardian-field checks (typed name/NRIC vs the
    parent's IC) are separate and run on the submitted consent data.
    """
    c = application_completeness(application)
    blockers = []
    if not c['quiz_done']:
        blockers.append('quiz_incomplete')
    if not c['details_done']:
        blockers.append('story_incomplete')
    if not c['family_done']:                          # structured family roster (Your Story)
        blockers.append('family_incomplete')
    if not c['address_done']:
        blockers.append('address_incomplete')
    if not c['funding_done']:
        blockers.append('funding_incomplete')
    present = set(application.documents.values_list('doc_type', flat=True))
    if 'ic' not in present:
        blockers.append('ic_missing')
    if 'results_slip' not in present:
        blockers.append('results_slip_missing')
    if 'offer_letter' not in present:                 # gate v2: compulsory for everyone
        blockers.append('offer_letter_missing')
    blockers.extend(income_doc_blockers(application))  # route-aware (replaces parent_ic + income_proof)
    # Identity check only once the IC is actually uploaded (else 'ic_missing' leads).
    if 'ic' in present:
        blockers.extend(_ic_identity_blockers(application))
    # POLICY (owner): do not receive applications with ANY red document check — every
    # "Doesn't match" the student sees in the Documents tab must clear before consent.
    blockers.extend(document_red_blockers(application))
    # …and a COMPULSORY doc that's present but UNREADABLE (a bad photo the student can
    # re-take) must be re-uploaded too — but never block on OUR OCR-service outages.
    blockers.extend(document_unreadable_blockers(application))
    return blockers


def document_red_blockers(application):
    """Every RED ('Doesn't match' / rejected / stale) per-document check that must
    clear before consent. Reads the SAME stored verification the student sees in the
    Documents tab (the student_*_check engines — no new OCR). Only a CONFIRMED
    `mismatch` (or STR rejected/stale) blocks; 'pending' / 'unreadable' / 'no_ref' do
    not. IC identity reds are covered separately by _ic_identity_blockers. Utility
    bills (soft hardship signal) are deliberately NOT gated. Returns blocker codes."""
    from . import income_engine
    from .academic_engine import student_slip_check
    from .pathway_engine import student_offer_check
    codes = set()

    def has(d, *keys):
        return any(d.get(k) == 'mismatch' for k in keys)

    for doc in application.documents.all():
        dt = doc.doc_type
        if dt == 'results_slip':
            chk = student_slip_check(doc)
            if chk.get('name') == 'mismatch':
                codes.add('results_slip_name_mismatch')
            if chk.get('subjects') == 'mismatch' or chk.get('results') == 'mismatch':
                codes.add('results_slip_grades_mismatch')
        elif dt == 'offer_letter':
            # Name / IC are hard identity reds; the pathway-clash is a SOFT "is this
            # where you're going?" signal and is deliberately not gated here.
            if has(student_offer_check(doc), 'name', 'ic'):
                codes.add('offer_letter_mismatch')
        elif dt == 'parent_ic':
            chk = income_engine.student_income_ic_check(doc)
            if has(chk, 'name_status', 'proof_name_status', 'proof_nric_status'):
                codes.add('income_document_mismatch')
        elif dt in ('salary_slip', 'epf'):
            if has(income_engine.student_income_proof_check(doc), 'name_status', 'nric_status'):
                codes.add('income_document_mismatch')
        elif dt == 'str':
            chk = income_engine.student_str_check(doc)
            if has(chk, 'name_status', 'nric_status') or chk.get('current_status') in ('rejected', 'stale'):
                codes.add('income_document_mismatch')
        elif dt == 'birth_certificate':
            if has(income_engine.student_bc_check(doc), 'child_status', 'mother_status', 'father_status'):
                codes.add('income_document_mismatch')
        elif dt == 'guardianship_letter':
            if has(income_engine.student_guardianship_check(doc), 'guardian_status', 'ward_status'):
                codes.add('income_document_mismatch')
    return list(codes)


def document_unreadable_blockers(application):
    """Compulsory documents that were uploaded but are UNREADABLE — a bad/blurry/skewed
    photo the student can simply re-take (Gopal already says exactly this). Owner policy:
    don't accept what we can't verify. EXCLUDES our own OCR-service outages: the Gemini
    docs (slip/offer/relationship) surface an outage as 'pending' (not processed), not
    'unreadable'; the Vision IC path is guarded with _is_ic_decode_error (a service error
    is not the student's fault). Returns blocker codes."""
    from .academic_engine import student_slip_check
    from .pathway_engine import student_offer_check
    from .income_engine import (income_cluster_advice, working_members,
                                _member_ic_doc, student_income_ic_check)
    codes = set()
    slip = application.documents.filter(doc_type='results_slip').order_by('-uploaded_at').first()
    if slip and student_slip_check(slip).get('name') == 'unreadable':
        codes.add('results_slip_unreadable')
    offer = application.documents.filter(doc_type='offer_letter').order_by('-uploaded_at').first()
    if offer and student_offer_check(offer).get('name') == 'unreadable':
        codes.add('offer_letter_unreadable')
    # Income cluster — per earner.
    route = (getattr(application, 'income_route', '') or '').strip()
    if route == 'str':
        earner = (getattr(application, 'income_earner', '') or '').strip()
        members = [earner] if earner else []
    elif route == 'salary':
        members = working_members(getattr(application, 'income_working_members', None) or [])
    else:
        members = []
    for member in members:
        ic = _member_ic_doc(application, member)
        if ic is not None:
            ran = bool(getattr(ic, 'vision_run_at', None))
            err = getattr(ic, 'vision_error', '') or ''
            service_down = bool(err) and not _is_ic_decode_error(err)   # OUR outage → don't block
            if ran and not service_down and not student_income_ic_check(ic).get('readable'):
                codes.add('income_document_unreadable')
        # The relationship doc (BC / guardianship letter) is a Gemini field-extraction doc,
        # so an outage shows as 'pending' — only a genuine bad scan returns this code.
        if income_cluster_advice(application, member) == 'income_rel_doc_unreadable':
            codes.add('income_document_unreadable')
    return list(codes)


_DEEPER_FIELDS = (
    'aspirations', 'plans', 'fears', 'justification',
    # "Your story" guided narrative fields (S2 redesign)
    'first_in_family', 'parents_occupation',
    # TD-061: siblings_studying boolean dropped; only the count remains (S15).
    'siblings_studying_count',
    'family_context', 'daily_life',
    # Income Check-1 wizard answers (Documents → Household income).
    'income_route', 'income_earner', 'income_working_members', 'earner_work_status',
    'household_other_earners', 'siblings_in_school', 'siblings_in_tertiary',
    # Structured family roster (redesign 2026-06) — the new inputs. first_in_family
    # + parents_occupation above are DERIVED from these on save (see below).
    'father_name', 'father_occupation', 'father_occupation_other',
    'mother_name', 'mother_occupation', 'mother_occupation_other',
    'other_family_members',
)


_PROFILE_ADDRESS_FIELDS = ('address', 'postal_code', 'city')


def save_application_details(application, data):
    """Persist deeper-info fields, upsert funding-need, and sync address to profile.

    Address lives on the student profile (alongside preferred_state set during
    /apply), not on the application. The Story tab on /scholarship/application
    sends it here so the student saves everything with one button.
    """
    from . import family
    deeper = {k: data[k] for k in _DEEPER_FIELDS if k in data}
    # Normalise the optional member pool to a safe shape before persisting.
    if 'other_family_members' in deeper:
        deeper['other_family_members'] = family.clean_other_members(deeper['other_family_members'])
    if deeper:
        for k, v in deeper.items():
            setattr(application, k, v)
        # The structured roster is now the INPUT; keep the two legacy columns
        # (first_in_family, parents_occupation) in sync as OUTPUTS so every
        # downstream reader (profile_engine, anomaly_engine, ledger) works unchanged.
        # Only takes over once the student has entered structured data — grandfathered
        # apps keep their existing free text / toggle until they re-enter.
        derived = []
        if family.has_structured_roster(application):
            application.first_in_family = family.derive_first_in_family(application)
            derived.append('first_in_family')
            summary = family.parents_occupation_summary(application)
            if summary:
                application.parents_occupation = summary
                derived.append('parents_occupation')
        update_fields = list(dict.fromkeys(list(deeper.keys()) + derived)) + ['updated_at']
        application.save(update_fields=update_fields)
    fn_data = data.get('funding_need')
    if fn_data is not None:
        FundingNeed.objects.update_or_create(application=application, defaults=fn_data)
    addr = {k: data[k] for k in _PROFILE_ADDRESS_FIELDS if k in data}
    if addr and application.profile:
        for k, v in addr.items():
            setattr(application.profile, k, v)
        application.profile.save(update_fields=list(addr.keys()))
    return application


# ── Consent / minor logic (Sprint 5a, hardened in S17) ──────────────────

# DRAFT — replace the version string when the lawyer-reviewed consent text lands.
# S19 (2026-05-29) — bumped to 2026-draft-3. The minor flow now interpolates
# student name/NRIC/pronoun into the consent body, captures the guardian's own
# NRIC, hard-gates on name+NRIC match against parent_ic OCR, and refines the
# relationship list (older_sibling → brother+sister; other_relative → relative).
# 0 existing consents on prod at bump time, so this is purely forward-looking.
CONSENT_VERSION = '2026-draft-4'  # bumped for the F8a student_onboarding_ack consent


# S17/S19 — structured guardian relationship codes. Father/mother only need
# the parent's IC; everyone else also needs a guardianship_letter (pragmatic:
# parent's authorisation letter OR court-issued guardianship order — both
# accepted, the lawyer call). 'Other' was intentionally excluded.
_PARENT_RELATIONSHIPS = frozenset({'father', 'mother'})


def needs_guardianship_letter(relationship: str) -> bool:
    """True iff the relationship requires the additional guardianship_letter
    document on top of the parent_ic upload. Father/mother only need the IC;
    legal_guardian / grandparent / brother / sister / relative need both."""
    return bool(relationship) and relationship not in _PARENT_RELATIONSHIPS


# S19 — Malaysian NRIC last digit encodes sex: odd = male, even = female.
# Used to interpolate the right pronoun into the consent text without asking
# the student to pick again (the profile.gender field exists, but deriving
# from NRIC keeps the consent text self-consistent with the IC the parent
# is signing about — no possibility of a mismatch between "his/her" and the
# IC the admin reviews).
def gender_from_nric(nric: str):
    """Return 'male', 'female', or None when the NRIC is unparseable."""
    digits = ''.join(c for c in (nric or '') if c.isdigit())
    if len(digits) < 12:
        return None
    last = int(digits[-1])
    return 'male' if last % 2 == 1 else 'female'


def age_from_nric(nric):
    """Best-effort age from a Malaysian NRIC (YYMMDD-PB-###G). None if unparseable."""
    digits = ''.join(c for c in (nric or '') if c.isdigit())
    if len(digits) < 6:
        return None
    from datetime import date
    yy, mm, dd = int(digits[0:2]), int(digits[2:4]), int(digits[4:6])
    today = date.today()
    century = 2000 if (2000 + yy) <= today.year else 1900
    try:
        dob = date(century + yy, mm, dd)
    except ValueError:
        return None
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def is_minor(profile):
    """True if the profile's NRIC indicates an age under 18."""
    age = age_from_nric(getattr(profile, 'nric', '') if profile else '')
    return age is not None and age < 18


def record_consent(application, *, consent_type, locale, granted_by,
                   guardian_name, guardian_relationship, ip, guardian_nric=''):
    """Record a consent, superseding any prior active consent of the same type."""
    Consent.objects.filter(
        application=application, consent_type=consent_type, is_active=True,
    ).update(is_active=False)
    return Consent.objects.create(
        application=application,
        consent_type=consent_type,
        version=CONSENT_VERSION,
        locale=locale if locale in ('en', 'ms', 'ta') else 'en',
        granted_by=granted_by,
        guardian_name=guardian_name,
        guardian_relationship=guardian_relationship,
        guardian_nric=guardian_nric,
        ip_address=ip,
    )


def complete_onboarding(application, *, answers=None, locale='en', ip=None):
    """B40 Phase E/F (F8a): the student finishes post-award onboarding.

    Records the ``student_onboarding_ack`` consent (granted_by='self' — the award
    itself was accepted earlier, with the guardian gate for minors), stores the
    questionnaire answers on the (created-or-updated) OnboardingResponse, and stamps
    ``onboarded_at`` — the hard gate the disbursement flow checks. Re-running updates
    the answers and re-stamps (idempotent enough for a "save" button).

    Onboarding only makes sense once the award is accepted, so it requires the
    application to be 'sponsored'; otherwise raises ``OnboardingError('not_awarded')``.
    """
    if application.status != 'sponsored':
        raise OnboardingError('not_awarded')
    consent = record_consent(
        application, consent_type=ONBOARDING_CONSENT_TYPE, locale=locale,
        granted_by='self', guardian_name='', guardian_relationship='', ip=ip,
    )
    response, _ = OnboardingResponse.objects.update_or_create(
        application=application,
        defaults={'answers': answers or {}, 'consent': consent},
    )
    application.onboarded_at = timezone.now()
    application.save(update_fields=['onboarded_at'])
    return response
