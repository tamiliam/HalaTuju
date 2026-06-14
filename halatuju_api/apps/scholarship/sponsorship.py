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
    if application.status == 'sponsored':
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
    return Sponsorship.objects.create(
        sponsor=sponsor, application=application, amount=amount, status='offered',
        accept_deadline=timezone.now() + timezone.timedelta(days=ACCEPT_DEADLINE_DAYS),
    )


def current_offer(application):
    """The single open ('offered') award for this application, or None."""
    return application.sponsorships.filter(status='offered').order_by('-offered_at').first()


@transaction.atomic
def respond_to_award(application, *, action, locale='en', granted_by='self',
                     guardian_name='', guardian_relationship='', guardian_nric='', ip=None):
    """Student/guardian accepts or declines the open award offer.

    accept → (guardian gate for minors) record a consent + 'active' + app 'sponsored'.
    decline → 'lapsed' (the amount returns to the sponsor's balance).
    Raises SponsorshipError on a bad state."""
    sponsorship = current_offer(application)
    if sponsorship is None:
        raise SponsorshipError('no_offer')

    if action == 'decline':
        sponsorship.status = 'lapsed'
        sponsorship.decided_at = timezone.now()
        sponsorship.save(update_fields=['status', 'decided_at', 'updated_at'])
        return sponsorship

    if action != 'accept':
        raise SponsorshipError('bad_action')

    # A minor's guardian must accept (name + NRIC + relationship), mirroring the
    # share-consent guardian gate.
    if is_minor(application.profile):
        if (granted_by != 'guardian' or not guardian_name.strip()
                or not guardian_relationship.strip() or not guardian_nric.strip()):
            raise SponsorshipError('guardian_required')

    consent = record_consent(
        application, consent_type=SPONSORSHIP_CONSENT_TYPE, locale=locale,
        granted_by=granted_by, guardian_name=guardian_name,
        guardian_relationship=guardian_relationship, guardian_nric=guardian_nric, ip=ip,
    )
    sponsorship.status = 'active'
    sponsorship.consent = consent
    sponsorship.decided_at = timezone.now()
    sponsorship.save(update_fields=['status', 'consent', 'decided_at', 'updated_at'])

    application.status = 'sponsored'
    application.save(update_fields=['status'])

    # F8a: tell the student their funding is confirmed + point them to onboarding.
    # NO sponsor identity in the email (B4 two-way anonymity). Best-effort.
    name = getattr(application.profile, 'name', '') if application.profile else ''
    send_award_confirmed_email(
        to_email=application.notify_email, applicant_name=name,
        programme_name=application.cohort.name, lang=locale,
    )
    return sponsorship


def lapse_expired_offers():
    """Mark every 'offered' award past its accept_deadline as 'lapsed' (the amount
    returns to the sponsor's balance). Intended for a scheduled job; returns the
    count lapsed."""
    qs = Sponsorship.objects.filter(status='offered', accept_deadline__lt=timezone.now())
    return qs.update(status='lapsed', decided_at=timezone.now())
