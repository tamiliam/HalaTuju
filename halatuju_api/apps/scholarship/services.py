"""
Business logic for B40 Assistance Programme intake.

Pure-ish functions kept out of the view (mirrors apps/courses/eligibility_service.py).
"""
from django.utils import timezone

from .emails import send_acknowledgement_email
from .models import ScholarshipApplication, ScholarshipCohort

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
        cohort=cohort, profile=profile, **data,
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
