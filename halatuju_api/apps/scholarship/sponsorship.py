"""Phase E3 — the sponsor wallet + match/consent state machine.

Money model (decided with the user): a sponsor DONATES into myNADI (final, no bank
refund); their internal balance = donations − allocations that still hold (offered
/active). A sponsor funds a student IN FULL for the admin-set award amount → an
'offered' Sponsorship + an award letter; the student/guardian accepts within a
deadline → 'active', app → 'sponsored', the student leaves the pool. Not accepted
in time (or cancelled) → the allocation stops holding and the amount is back in the
sponsor's balance to redirect — never a bank refund. Tranches/disbursement = E3b.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from . import pool
from .emails import send_award_confirmed_email
from .models import Sponsorship, SponsorProfile
from .services import is_minor, record_consent

# Days a student/guardian has to accept an award before it lapses.
ACCEPT_DEADLINE_DAYS = 14
SPONSORSHIP_CONSENT_TYPE = 'consent_to_sponsorship'


class SponsorshipError(Exception):
    """Raised by fund_student/respond_to_award with a machine code for the view."""
    def __init__(self, code, message=''):
        self.code = code
        super().__init__(message or code)


def sponsor_balance(sponsor):
    """A sponsor's spendable directed-giving balance = total donated − allocations
    that still hold (offered/active). Lapsed/cancelled allocations free up again."""
    donated = sponsor.donations.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    held = (sponsor.sponsorships.filter(status__in=Sponsorship.HOLDING)
            .aggregate(s=Sum('amount'))['s'] or Decimal('0'))
    return donated - held


def sponsor_impact(sponsor):
    """R2 — aggregate giving impact for the My Giving dashboard. Counts + money only,
    **allowlist-safe by construction** (no student identity ever crosses): derived
    from the ledger (`sponsor_balance`) + the sponsor's ACTIVE allocations and their
    SemesterResults. A graduated student's allocation stays 'active' (graduation is a
    result flag, not a sponsorship status), so we split active giving into
    `completed` (graduated) vs `committed` (ongoing) via `pool.derive_progress_state`.
    """
    active = list(sponsor.sponsorships.filter(status='active').select_related('application'))
    committed = Decimal('0')
    completed = Decimal('0')
    graduated_count = 0
    semesters_completed = 0
    for sp in active:
        app = sp.application
        if pool.derive_progress_state(app) == 'graduated':
            completed += sp.amount
            graduated_count += 1
        else:
            committed += sp.amount
        semesters_completed += app.semester_results.count()
    return {
        'total_given': str(committed + completed),
        'students_supported': len(active),
        'students_active': len(active) - graduated_count,
        'students_graduated': graduated_count,
        'semesters_completed': semesters_completed,
        'balance': {
            'committed': str(committed),
            'completed': str(completed),
            'available': str(sponsor_balance(sponsor)),
        },
    }


def sponsor_statement(sponsor):
    """R4 — the giving statement's two ledgers. **Donations INTO the trust** (the
    sponsor's own deposit records — fine to show back to them) and **gifts OUT to
    students** (active allocations carrying the anonymous ``ref`` only — never the
    student's identity). Allowlist-safe; counts + money + refs only."""
    donations = [
        {'amount': str(d.amount), 'reference': d.reference, 'at': d.created_at}
        for d in sponsor.donations.order_by('-created_at')
    ]
    gifts = []
    out_total = Decimal('0')
    for sp in (sponsor.sponsorships.filter(status='active')
               .select_related('application').order_by('-decided_at')):
        gifts.append({'ref': pool.pool_ref(sp.application_id), 'amount': str(sp.amount), 'at': sp.decided_at})
        out_total += sp.amount
    in_total = sum((Decimal(d['amount']) for d in donations), Decimal('0'))
    return {
        'donations': donations,
        'gifts': gifts,
        'total_in': str(in_total),
        'total_out': str(out_total),
    }


def is_fundable(application):
    """A student can be funded iff they're in the pool (anon profile published +
    active share consent), an admin has set an award amount, they're not already
    sponsored, and no holding sponsorship exists yet (1:1 for now)."""
    try:
        sp = application.sponsor_profile  # reverse OneToOne: raises if absent
    except SponsorProfile.DoesNotExist:
        return False
    if not sp.anon_published:
        return False
    if application.award_amount is None or application.award_amount <= 0:
        return False
    if application.status in pool.IN_PROGRAMME_OR_BEYOND:  # already awarded / funded / closed
        return False
    if application.sponsorships.filter(status__in=Sponsorship.HOLDING).exists():
        return False
    return pool.has_active_share_consent(application)


@transaction.atomic
def fund_student(sponsor, application):
    """Sponsor funds a student IN FULL for the award amount. Creates an 'offered'
    Sponsorship and issues the award (deadline = now + ACCEPT_DEADLINE_DAYS).
    Raises SponsorshipError on a bad state."""
    if not is_fundable(application):
        raise SponsorshipError('not_fundable')
    amount = application.award_amount
    if sponsor_balance(sponsor) < amount:
        raise SponsorshipError('insufficient_balance')
    sp = Sponsorship.objects.create(
        sponsor=sponsor, application=application, amount=amount, status='offered',
        accept_deadline=timezone.now() + timezone.timedelta(days=ACCEPT_DEADLINE_DAYS),
    )
    # Post-award lifecycle: a funder has committed → the application enters 'awarded' (the offer is
    # out + the tri-partite agreement signing begins) and leaves the discovery pool.
    application.status = 'awarded'
    application.save(update_fields=['status'])
    return sp


def current_offer(application):
    """The single open ('offered') award for this application, or None."""
    return application.sponsorships.filter(status='offered').order_by('-offered_at').first()


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
    behaviour is exactly as before."""
    sponsorship = current_offer(application)
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
        from . import bursary
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
    sponsorship.save(update_fields=['status', 'consent', 'decided_at', 'updated_at'])

    # Flag-ON (bursary signing) path: the app stays 'awarded' until the Foundation counter-signs
    # (the binding, last signature) — bursary.countersign_foundation flips 'awarded' → 'active'.
    # The student + guarantor have just signed; the witness + Foundation follow via admin endpoints.
    if getattr(_settings, 'BURSARY_AGREEMENT_ENABLED', False):
        return sponsorship

    # Flag-OFF path: no signing step — acceptance + the #14 cool-off confirms the award → 'active'.
    # The flip + funding-confirmed email + onboarding wait AWARD_COOLOFF_DAYS so we can reconsider /
    # hold within the window (hold_pending_award reverts it; the student never saw confirmation).
    days = getattr(_settings, 'AWARD_COOLOFF_DAYS', 2)
    if days and days > 0:
        from datetime import timedelta
        application.award_due_at = timezone.now() + timedelta(days=days)
        application.save(update_fields=['award_due_at'])
    else:
        _finalise_award(application, locale)
    return sponsorship


def _revert_to_pool(application):
    """An offer was declined / held / expired BEFORE it became active → the application returns to
    'recommended' (re-enters the discovery pool) and any award cool-off marker clears. No-op if the
    app already moved on (e.g. it was finalised to 'active')."""
    fields = []
    if application.status == 'awarded':
        application.status = 'recommended'
        fields.append('status')
    if application.award_due_at is not None:
        application.award_due_at = None
        fields.append('award_due_at')
    if fields:
        application.save(update_fields=fields)


def _finalise_award(application, locale='en'):
    """The actual effect of an accepted award (flag-OFF path): flip to 'active' + send the
    funding-confirmed email (no sponsor identity, B4) + clear the cool-off marker. Shared by the
    immediate path (cool-off disabled) and the release cron (cool-off elapsed). Best-effort email.
    ('active' = executed/funded; the first disbursement later flips it to 'maintenance' — S4.)"""
    application.status = 'active'
    application.award_due_at = None
    application.save(update_fields=['status', 'award_due_at'])
    name = getattr(application.profile, 'name', '') if application.profile else ''
    send_award_confirmed_email(
        to_email=application.notify_email, applicant_name=name,
        programme_name=application.cohort.name, lang=locale,
    )


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
    funding-confirmed email + open onboarding. Intended for the scheduler. Returns the count."""
    from .models import ScholarshipApplication
    now = now or timezone.now()
    qs = (ScholarshipApplication.objects
          .filter(award_due_at__isnull=False, award_due_at__lte=now)
          .exclude(status='active').select_related('cohort', 'profile'))
    released = 0
    for app in qs:
        # Only finalise if the acceptance still holds (not held/lapsed in the window).
        if not app.sponsorships.filter(status='active').exists():
            _revert_to_pool(app)
            continue
        _finalise_award(app, app.locale)
        released += 1
    return released


def lapse_expired_offers():
    """Mark every 'offered' award past its accept_deadline as 'lapsed' (the amount
    returns to the sponsor's balance). Intended for a scheduled job; returns the
    count lapsed."""
    now = timezone.now()
    expired = list(Sponsorship.objects.filter(status='offered', accept_deadline__lt=now)
                   .select_related('application'))
    for sp in expired:
        sp.status = 'lapsed'
        sp.decided_at = now
        sp.save(update_fields=['status', 'decided_at', 'updated_at'])
        _revert_to_pool(sp.application)   # offer expired unaccepted → back in the pool
    return len(expired)
