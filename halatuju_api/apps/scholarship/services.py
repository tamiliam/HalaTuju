"""
Business logic for B40 Assistance Programme intake.

Pure-ish functions kept out of the view (mirrors apps/courses/eligibility_service.py).
"""
from datetime import timedelta

from django.utils import timezone

from .emails import send_acknowledgement_email, send_pass_email, send_fail_email
from .models import Consent, FundingNeed, ScholarshipApplication, ScholarshipCohort
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
    application.decision_due_at = base + timedelta(hours=delay_h)
    application.save(update_fields=[
        'verdict', 'bucket', 'shortlist_reason', 'decision_due_at',
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
    application.save(update_fields=['status', 'decision_released_at', 'shortlisted_at'])

    name = getattr(application.profile, 'name', '') if application.profile else ''
    send = send_pass_email if application.verdict == 'shortlisted' else send_fail_email
    if send(
        to_email=application.notify_email,
        applicant_name=name,
        programme_name=application.cohort.name,
        lang=application.locale,
    ):
        application.decision_email_sent_at = now
        application.save(update_fields=['decision_email_sent_at'])
    return True


def application_completeness(application):
    """
    Report STEP 1A / STEP 2 progress for a (typically shortlisted) application:
    quiz done (the linked profile has quiz signals), story done, funding done,
    documents done (compulsory IC + results slip), consent done. The sponsor
    stage (Phase 2) will gate on ``complete``.

    funding_done (S3 redesign): at least one category ticked in categories.
    documents_done (S4): both compulsory documents (ic + results_slip) present.
    consent_done (S5): an active Consent row exists.
    complete (S5 finalise): all five parts done.
    """
    profile = application.profile
    quiz_done = bool(profile and profile.student_signals)
    details_done = bool(application.aspirations.strip() and application.plans.strip())
    try:
        funding_done = bool(application.funding_need.categories)
    except FundingNeed.DoesNotExist:
        funding_done = False
    present = set(application.documents.values_list('doc_type', flat=True))
    documents_done = {'ic', 'results_slip'}.issubset(present)
    consent_done = application.consents.filter(is_active=True).exists()
    return {
        'quiz_done': quiz_done,
        'details_done': details_done,
        'funding_done': funding_done,
        'documents_done': documents_done,
        'consent_done': consent_done,
        'complete': (quiz_done and details_done and funding_done
                     and documents_done and consent_done),
    }


_DEEPER_FIELDS = (
    'aspirations', 'plans', 'fears', 'justification',
    # "Your story" guided narrative fields (S2 redesign)
    'first_in_family', 'parents_occupation', 'siblings_studying', 'family_context', 'daily_life',
)


def save_application_details(application, data):
    """Persist deeper-info fields and upsert the funding-need breakdown."""
    deeper = {k: data[k] for k in _DEEPER_FIELDS if k in data}
    if deeper:
        for k, v in deeper.items():
            setattr(application, k, v)
        application.save(update_fields=list(deeper.keys()) + ['updated_at'])
    fn_data = data.get('funding_need')
    if fn_data is not None:
        FundingNeed.objects.update_or_create(application=application, defaults=fn_data)
    return application


# ── Consent / minor logic (Sprint 5a) ────────────────────────────────────

# DRAFT — replace the version string when the lawyer-reviewed consent text lands.
CONSENT_VERSION = '2026-draft-1'


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
                   guardian_name, guardian_relationship, ip):
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
        ip_address=ip,
    )
