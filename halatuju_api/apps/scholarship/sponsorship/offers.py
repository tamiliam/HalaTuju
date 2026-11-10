"""Sponsorship: funding a student, the award email release, the sign deadline and
cancelling an offer.

Moved unchanged out of ``sponsorship.py`` when audit A3.8 (2026-11-10) made it a package.
"""
from django.db import transaction
from django.utils import timezone

from .. import branding as _branding
from .. import pool
from .. import status_lock as _status_lock
from .. import usage as _usage
# An award that falls through lands back in the pool, or, on a failed "Born in" rule, at QC
# (TD-376). Its own module since `sponsorship.py` sat at its `oversize_files` allowance.
from ..award_revert import revert_to_pool as _revert_to_pool
from ..emails import send_award_offer_email, send_award_offer_sign_email
from ..models import Sponsorship, SponsorProfile
from ..vircle import raise_setup_task
from .errors import SponsorshipError
from .wallet import sponsor_balance


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
    # Fundable ONLY at the QC-cleared 'recommended' stage — not before QC clears them
    # (under review / awaiting QC), not after a funder commits (awarded/active/…/closed).
    # Mirrors pool.is_pool_eligible / eligible_pool_queryset exactly.
    if application.status != 'recommended':
        return False
    if application.sponsorships.filter(status__in=Sponsorship.HOLDING).exists():
        return False
    return pool.has_active_share_consent(application)


@transaction.atomic
def fund_student(sponsor, application):
    """Sponsor funds a student IN FULL for the award amount. Creates an 'offered'
    Sponsorship and issues the award.

    Offer-lapse rework (go-live transition, 2026-07-19): NO accept_deadline is armed here.
    Under contract mode the lapse clock arms only when the sign-invitation email is actually
    sent (``arm_sign_deadline`` / the ``send_sign_invitation_emails`` command) and is cleared
    when the agreement binds — so a fresh offer has a NULL deadline and can never lapse until a
    student has actually been invited to sign. The old offer+14d semantics are dead.
    Raises SponsorshipError on a bad state."""
    # ⚠ THE NULL BUCKET IS NOT A WALLET (TD-258). `sponsor_balance(sponsor, None)` scopes to
    # the NULL programme so bare fixtures self-partition — a safe partition that becomes a
    # back door the moment something can SPEND from it, because a NULL-programme application
    # matches a NULL-programme donation exactly (which is what the mock donation minted). So
    # an application belonging to no gift can never be bought. Refused HERE, the single spend
    # choke point (`award_and_notify`, standing gifts and the admin batch all arrive through
    # this function), BEFORE any arithmetic, so the NULL wallet is never even consulted.
    if application.programme_id is None:
        raise SponsorshipError('programme_required')
    # TD-365 / TD-383: lock and re-read the application FIRST (the same row a close locks), so a
    # close, a reject or a second fund that committed since the caller read it is seen here.
    from ..status_lock import StatusRefused, lock_application_for, lock_sponsor_wallet
    try:
        lock_application_for(application, ('recommended',))
    except StatusRefused:
        raise SponsorshipError('not_fundable')
    if not is_fundable(application):
        raise SponsorshipError('not_fundable')
    amount = application.award_amount
    lock_sponsor_wallet(sponsor)   # A1.5: two funds by one sponsor cannot both pass the balance
    # Spend authority is the wallet for THIS student's programme — never a cross-programme
    # total. A sponsor with money in the flagship cannot fund a Sabah student with it.
    if sponsor_balance(sponsor, application.programme) < amount:
        raise SponsorshipError('insufficient_balance')
    sp = Sponsorship.objects.create(
        sponsor=sponsor, application=application, amount=amount, status='offered',
    )
    # Post-award lifecycle: a funder has committed → the application enters 'awarded' (the offer is
    # out + the tri-partite agreement signing begins) and leaves the discovery pool.
    application.status = 'awarded'
    fields = ['status']
    if application.stamp_first('awarded_at'):
        fields.append('awarded_at')
    application.save(update_fields=fields)
    return sp


def award_and_notify(sponsor, application):
    """Award entry point for the sponsor 'Support' button AND the admin batch: fund the student
    (an 'offered' Sponsorship + status 'awarded'). It does NOT email inline — the good-news email
    is sent later by ``release_award_offer_emails`` once the award is the organisation's
    ``award_email_delay_hours`` old, leaving a window to reconsider (cancelling the award
    before then stops the email). Kept as the named single entry point so the button and the batch
    behave identically."""
    return fund_student(sponsor, application)   # atomic; raises SponsorshipError on a bad state


def release_award_offer_emails(now=None, held=None):
    """Send the award email for every HOLDING award whose cool-off has elapsed and that hasn't been
    emailed yet (``offered_at + the org's award_email_delay_hours <= now``; ``offer_emailed_at`` is
    NULL). A cancelled/lapsed award (no longer offered/active) is skipped, so reconsidering within
    the window stops the email. Hourly scheduler (job ``release-award-offer-emails``). Returns the
    count sent. Request #26: a student whose parent phone needs a call WAITS (ids into ``held``).

    ``offer_emailed_at`` is stamped ONLY ON SUCCESS (2026-07-12; as ``send_award_offer_emails``,
    code-health S3 #7): stamping a failed send suppressed the email for good, so the student never
    learnt she had won. An undeliverable address now retries hourly, visibly, instead.

    On a successful send it also raises the Vircle setup task, because the email now carries the
    Vircle instructions and the task it points at must exist by the time the student reads it."""
    from django.conf import settings as _settings
    from ..award_timing import award_email_release_window
    from ..parent_call import held_for_parent_call
    now = now or timezone.now()
    # Contract mode (2026-07-19): flag ON → the email invites the student to REVIEW & SIGN, with NO
    # Vircle content or task (those fire at EXECUTION, bursary.distribute_executed_agreement). Flag
    # OFF → the Vircle-flavoured award email + raise_setup_task, as before.
    bursary_on = getattr(_settings, 'BURSARY_AGREEMENT_ENABLED', False)
    due = list(Sponsorship.objects
               .filter(award_email_release_window(now),   # per organisation: award_timing.py
                       status__in=Sponsorship.HOLDING, offer_emailed_at__isnull=True)
               .order_by('pk').values_list('pk', flat=True))
    sent = 0
    for pk in due:
        # A1.13 review F4: RE-READ each row under its lock and send + stamp under it, so a cancel /
        # withdrawal that landed after the list was read stops the email. Re-review 1: the case
        # first (the usage / task rows below share-lock it), as the withdrawal and the cancel do.
        with transaction.atomic():
            _status_lock.lock_case_of_sponsorship(pk=pk)
            sp = (Sponsorship.objects.select_for_update(of=('self',))
                  .select_related('application', 'application__profile')
                  .filter(pk=pk, status__in=Sponsorship.HOLDING, offer_emailed_at__isnull=True)
                  .first())
            if sp is None:
                continue
            app = sp.application
            name = getattr(app.profile, 'name', '') if app.profile else ''
            if held_for_parent_call(app, held):
                continue   # request #26: the email waits for the parent call; unstamped, so retried
            if bursary_on:
                # Bill the tenant — an unwrapped send meters org-NULL (see emails._meter_email).
                with _usage.usage_context(application=app):
                    ok = send_award_offer_sign_email(
                        to_email=app.notify_email, applicant_name=name,
                        lang=getattr(app, 'locale', '') or 'en')
                if not ok:
                    continue   # stamp only on success (see below); retry next run
                sp.offer_emailed_at = now
                sp.save(update_fields=['offer_emailed_at', 'updated_at'])
                sent += 1
                continue   # NO Vircle task on the contract-mode path — it's raised at execution
            from ..vircle import can_register
            with _usage.usage_context(application=app):
                ok = send_award_offer_email(
                    to_email=app.notify_email, applicant_name=name,
                    lang=getattr(app, 'locale', '') or 'en',
                    guardian_note=not can_register(app), branding=_branding.for_application(app))
            if not ok:
                continue   # stamp ONLY on success (2026-07-12, the docstring): next run retries
            sp.offer_emailed_at = now
            sp.save(update_fields=['offer_emailed_at', 'updated_at'])
            # The award email now CARRIES the Vircle instructions, so the task it refers to must
            # exist the moment the student reads it — but never for a student whose email failed.
            raise_setup_task(app)
            sent += 1
    return sent


def current_offer(application):
    """The single open ('offered') award for this application, or None."""
    return application.sponsorships.filter(status='offered').order_by('-offered_at').first()


def arm_sign_deadline(application, *, now=None):
    """Offer-lapse rework (go-live transition): ARM the accept clock on this application's open
    offer — ``accept_deadline = now + the organisation's `sign_accept_deadline_days``` (Org Config
    Sprint F; platform default 30). Called when the sign-invitation
    email is actually sent (see the ``send_sign_invitation_emails`` command), so the student then
    has that window to sign before the offer may lapse. No-op (returns None) if there is no open
    offer. Re-arming an already-armed offer simply resets the window (a resend extends the clock)."""
    from apps.courses import org_config
    sp = current_offer(application)
    if sp is None:
        return None
    now = now or timezone.now()
    days = org_config.value(application.owning_organisation, 'sign_accept_deadline_days')
    sp.accept_deadline = now + timezone.timedelta(days=days)
    sp.save(update_fields=['accept_deadline', 'updated_at'])
    return sp.accept_deadline


@transaction.atomic
def cancel_offer(sponsor, sponsorship_id):
    """Sponsor withdraws an award they've made — allowed ONLY inside the cool-off, i.e. while the
    good-news email has NOT gone out (``offer_emailed_at`` is NULL). Once the student has been told,
    there is no turning back: ``already_notified``. The application reverts 'awarded' → 'recommended'
    (back in the pool, fundable by another sponsor) and the held amount returns to the balance (a
    'cancelled' row is not HOLDING).

    ``offer_emailed_at`` — not an elapsed-hours calculation — is the gate, because it IS the fact
    that matters (the student has been told); a separate clock could drift from the cron that sends
    the email. Locked FOR UPDATE so a cancel can't race ``release_award_offer_emails`` (it sends +
    stamps under the same row lock) and land on the wrong side of that line. A1.13 review F5: the
    APPLICATION is locked first, as the withdrawal does. Raises SponsorshipError on a bad state."""
    _status_lock.lock_case_of_sponsorship(id=sponsorship_id, sponsor=sponsor, status='offered')
    sp = (Sponsorship.objects.select_for_update()
          .filter(id=sponsorship_id, sponsor=sponsor, status='offered')
          .select_related('application').first())
    if sp is None:
        raise SponsorshipError('not_found')
    if sp.offer_emailed_at is not None:
        raise SponsorshipError('already_notified')
    sp.status = 'cancelled'
    sp.decided_at = timezone.now()
    sp.save(update_fields=['status', 'decided_at', 'updated_at'])
    _revert_to_pool(sp.application)
    return sp
