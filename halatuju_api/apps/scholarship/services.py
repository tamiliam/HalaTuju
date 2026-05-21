"""
Business logic for B40 Assistance Programme intake.

Pure-ish functions kept out of the view (mirrors apps/courses/eligibility_service.py).
"""
from django.utils import timezone

from .emails import send_acknowledgement_email, send_pass_email
from .models import Consent, FundingNeed, ScholarshipApplication, ScholarshipCohort
from .shortlisting import evaluate

# SPM grades that count as an "A" for shortlisting (A+, A and A- all count,
# matching how the B40 candidate profiles tally "10 A's incl. A+ and A-").
A_GRADES = {'A+', 'A', 'A-'}


def count_spm_a_grades(grades):
    """Count A+/A/A- across an SPM grades dict like {'bm': 'A+', ...}."""
    if not isinstance(grades, dict):
        return 0
    return sum(
        1 for g in grades.values()
        if isinstance(g, str) and g.strip().upper() in A_GRADES
    )


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
    Create an application, snapshot the SPM A-count from the profile if the
    client didn't supply one, send the acknowledgement email, and stamp
    ``acknowledged_at``. Returns the created application.
    """
    data = dict(validated_data)
    data.pop('cohort_code', None)

    if data.get('spm_a_count') is None and profile is not None:
        data['spm_a_count'] = count_spm_a_grades(getattr(profile, 'grades', None))

    application = ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile,
        locale=lang if lang in ('en', 'ms', 'ta') else 'en',
        notify_email=to_email or '',
        **data,
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


def shortlist_application(application):
    """
    Run the mechanical shortlist on a freshly-created application, persist the
    outcome (status / bucket / reason / shortlisted_at), and for a PASS send the
    congratulations email immediately. The FAIL email is deferred to the
    ``send_pending_decision_emails`` management command (cohort-configured delay).
    """
    result = evaluate(application, application.cohort)
    application.status = result.status
    application.bucket = result.bucket
    application.shortlist_reason = result.reason
    application.shortlisted_at = timezone.now()
    application.save(update_fields=[
        'status', 'bucket', 'shortlist_reason', 'shortlisted_at',
    ])

    if result.status == 'shortlisted':
        sent = send_pass_email(
            to_email=application.notify_email,
            applicant_name=getattr(application.profile, 'name', '') if application.profile else '',
            programme_name=application.cohort.name,
            lang=application.locale,
        )
        if sent:
            application.decision_email_sent_at = timezone.now()
            application.save(update_fields=['decision_email_sent_at'])

    return application


def application_completeness(application):
    """
    Report STEP 1A / STEP 2 progress for a (typically shortlisted) application:
    quiz done (the linked profile has quiz signals), deeper info done, funding
    need done. The sponsor stage (Phase 2) will gate on ``complete``.
    """
    profile = application.profile
    quiz_done = bool(profile and profile.student_signals)
    details_done = bool(application.aspirations.strip() and application.justification.strip())
    try:
        funding_done = application.funding_need.total > 0
    except FundingNeed.DoesNotExist:
        funding_done = False
    return {
        'quiz_done': quiz_done,
        'details_done': details_done,
        'funding_done': funding_done,
        'complete': quiz_done and details_done and funding_done,
    }


_DEEPER_FIELDS = ('aspirations', 'plans', 'fears', 'justification')


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
