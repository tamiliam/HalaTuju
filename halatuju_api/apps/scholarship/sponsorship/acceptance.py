"""Sponsorship: the student or guardian answers the award; the cool-off hold and release.

Moved unchanged out of ``sponsorship.py`` when audit A3.8 (2026-11-10) made it a package.
"""
from django.db import transaction
from django.utils import timezone

from .. import usage as _usage
from ..award_revert import revert_to_pool as _revert_to_pool
from ..emails import send_award_confirmed_email
from ..services import is_minor, record_consent
from .errors import SponsorshipError

SPONSORSHIP_CONSENT_TYPE = 'consent_to_sponsorship'


@transaction.atomic
def respond_to_award(application, *, action, locale='en', granted_by='self',
                     guardian_name='', guardian_relationship='', guardian_nric='', ip=None,
                     student_signed_name='', student_signed_nric='',
                     guarantor_name='', guarantor_nric='', guarantor_relationship=''):
    """Student/guardian accepts or declines the open award offer.

    accept → (guardian gate for minors) record a consent + 'active' + app 'sponsored'.
    decline → 'lapsed' (the amount returns to the sponsor's balance).
    Raises SponsorshipError on a bad state.

    Bursary agreement (BURSARY_AGREEMENT_ENABLED, default OFF): on accept, the student
    + a parent/guardian surety sign the binding bursary CONTRACT in-session. For a MINOR
    the GUARDIAN is the guarantor (the guardian_* fields), so the student signature is
    optional; for an ADULT the student must type their own signature AND a parent surety
    (guarantor_name/_nric/_relationship). The agreement is signed INSIDE this atomic block
    BEFORE the consent + 'active' flip, so a BursaryError rolls the whole acceptance back.
    When the flag is OFF, none of the new fields are required and no agreement is created —
    behaviour is exactly as before. A1.13 review F2: the case, then the offer, is locked and re-read
    first, so an accept racing a withdrawal / cancel answers ``no_offer``, never 'active'."""
    from ..status_lock import StatusRefused, lock_application_for
    try:
        lock_application_for(application, ('awarded',))
    except StatusRefused:
        raise SponsorshipError('no_offer')
    sponsorship = (application.sponsorships.select_for_update().filter(status='offered')
                   .order_by('-offered_at').first())
    if sponsorship is None:
        raise SponsorshipError('no_offer')

    if action == 'decline':
        sponsorship.status = 'lapsed'
        sponsorship.decided_at = timezone.now()
        sponsorship.save(update_fields=['status', 'decided_at', 'updated_at'])
        _revert_to_pool(application)   # offer declined → back to 'recommended', re-enters the pool
        return sponsorship

    if action != 'accept':
        raise SponsorshipError('bad_action')

    minor = is_minor(application.profile)

    # A minor's guardian must accept (name + NRIC + relationship), mirroring the
    # share-consent guardian gate.
    if minor:
        if (granted_by != 'guardian' or not guardian_name.strip()
                or not guardian_relationship.strip() or not guardian_nric.strip()):
            raise SponsorshipError('guardian_required')

    # Bursary contract (flag-gated). Sign BEFORE recording consent / flipping to active
    # so a BursaryError aborts the whole acceptance (transaction.atomic rolls back).
    from django.conf import settings as _settings
    if getattr(_settings, 'BURSARY_AGREEMENT_ENABLED', False):
        from .. import bursary
        if minor:
            # The guardian IS the surety/guarantor for a minor; the student signature is
            # optional (the guardian signs on the student's behalf).
            g_name, g_nric, g_rel = guardian_name, guardian_nric, guardian_relationship
            s_name = student_signed_name or guardian_name
        else:
            # An adult signs their own name AND brings a parent surety.
            if not student_signed_name.strip():
                raise SponsorshipError('student_signature_required')
            if not (guarantor_name.strip() and guarantor_nric.strip()
                    and guarantor_relationship.strip()):
                raise SponsorshipError('guarantor_required')
            g_name, g_nric, g_rel = guarantor_name, guarantor_nric, guarantor_relationship
            s_name = student_signed_name
        try:
            bursary.sign_agreement(
                application, sponsorship=sponsorship,
                student_signed_name=s_name, student_signed_nric=student_signed_nric,
                guarantor_name=g_name, guarantor_nric=g_nric,
                guarantor_relationship=g_rel, locale=locale, ip=ip)
        except bursary.BursaryError as e:
            raise SponsorshipError(e.code)

    consent = record_consent(
        application, consent_type=SPONSORSHIP_CONSENT_TYPE, locale=locale,
        granted_by=granted_by, guardian_name=guardian_name,
        guardian_relationship=guardian_relationship, guardian_nric=guardian_nric, ip=ip,
    )
    sponsorship.status = 'active'
    sponsorship.consent = consent
    sponsorship.decided_at = timezone.now()
    # Offer-lapse rework: accepted → the accept clock is FULFILLED; clear any armed deadline (leaving
    # 'offered' already takes it out of the lapse query — this keeps the record honest).
    sponsorship.accept_deadline = None
    sponsorship.save(update_fields=['status', 'consent', 'decided_at', 'accept_deadline', 'updated_at'])

    # Flag-ON (bursary signing) path: the app stays 'awarded' until the Foundation counter-signs
    # (the binding, last signature) — bursary.countersign_foundation flips 'awarded' → 'active'.
    # The student + guarantor have just signed; notify the next party in the chain (partner
    # witness if a referring org exists, else the Foundation directly). Best-effort.
    if getattr(_settings, 'BURSARY_AGREEMENT_ENABLED', False):
        from .. import bursary
        bursary.notify_after_guarantor_signed(application)
        return sponsorship

    # Flag-OFF path: no signing step — acceptance + the #14 cool-off confirms the award → 'active'.
    # The flip + funding-confirmed email + onboarding wait the org's award_confirm_hold_days so we
    # can reconsider / hold (hold_pending_award reverts it; the student never saw confirmation).
    from ..award_timing import award_confirm_hold
    hold = award_confirm_hold(application)
    if hold.total_seconds() > 0:
        application.award_due_at = timezone.now() + hold
        application.save(update_fields=['award_due_at'])
    else:
        _finalise_award(application, locale)
    return sponsorship


def _finalise_award(application, locale='en'):
    """The actual effect of an accepted award (flag-OFF path): flip to 'active' + send the
    funding-confirmed email (no sponsor identity, B4) + clear the cool-off marker. Shared by the
    immediate path (cool-off disabled) and the release cron (cool-off elapsed). Best-effort email.
    ('active' = executed/funded; the first disbursement later flips it to 'maintenance' — S4.)"""
    application.status = 'active'
    application.award_due_at = None
    fields = ['status', 'award_due_at']
    if application.stamp_first('active_at'):
        fields.append('active_at')
    application.save(update_fields=fields)
    name = getattr(application.profile, 'name', '') if application.profile else ''
    # Always sent (owner, 2026-10-30: it carries her onboarding link); billed to her organisation (S6a).
    with _usage.usage_context(application=application):
        send_award_confirmed_email(to_email=application.notify_email, applicant_name=name,
                                   programme_name=application.cohort.name, lang=locale)


def hold_pending_award(application):
    """Reverse an accepted-but-unconfirmed award within the cool-off so the org can reconsider:
    the active sponsorship lapses (its amount returns to the sponsor's balance) and the app reverts
    'awarded' → 'recommended' (re-enters the pool); it was never flipped to a funded state and the
    student never saw a confirmation. Returns True if there was a pending award to hold."""
    if not application.award_due_at:
        return False
    sp = application.sponsorships.filter(status='active').order_by('-decided_at').first()
    if sp is not None:
        sp.status = 'lapsed'
        sp.decided_at = timezone.now()
        sp.save(update_fields=['status', 'decided_at', 'updated_at'])
    _revert_to_pool(application)
    return True


def release_pending_awards(now=None):
    """Finalise every accepted award whose cool-off has passed: flip 'sponsored' + send the
    funding-confirmed email + open onboarding. Intended for the scheduler. Returns the count.
    A1.13 review F3: each case is locked and re-read (awarded only) and re-checked before a write."""
    from ..models import ScholarshipApplication
    from ..status_lock import StatusRefused, lock_application_for
    now = now or timezone.now()
    qs = (ScholarshipApplication.objects
          .filter(award_due_at__isnull=False, award_due_at__lte=now)
          .exclude(status='active').select_related('cohort', 'profile'))
    released = 0
    for app in qs:
        with transaction.atomic():
            try:
                lock_application_for(app, ('awarded',))
            except StatusRefused:
                continue   # withdrawn / closed / already moved on since the list was read
            if app.award_due_at is None or app.award_due_at > now:
                continue   # held, withdrawn or re-timed since the list was read
            if not app.sponsorships.filter(status='active').exists():   # held / lapsed meanwhile
                _revert_to_pool(app)
                continue
            _finalise_award(app, app.locale)
            released += 1
    return released
