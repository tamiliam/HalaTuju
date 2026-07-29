"""Phase E3 — the sponsor wallet + match/consent state machine.

Money model (decided with the user): a sponsor DONATES into myNADI (final, no bank
refund); their internal balance = donations − allocations that still hold (offered
/active). A sponsor funds a student IN FULL for the admin-set award amount → an
'offered' Sponsorship + an award letter; the student/guardian accepts within a
deadline → 'active', app → 'sponsored', the student leaves the pool. Not accepted
in time (or cancelled) → the allocation stops holding and the amount is back in the
sponsor's balance to redirect — never a bank refund. Tranches/disbursement = E3b.
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from . import pool

logger = logging.getLogger(__name__)
from .emails import (send_award_confirmed_email, send_award_offer_email,
                     send_award_offer_sign_email)
from .models import Donation, Programme, Sponsorship, SponsorProfile
from .services import is_minor, record_consent
from .vircle import raise_setup_task

SPONSORSHIP_CONSENT_TYPE = 'consent_to_sponsorship'


class SponsorshipError(Exception):
    """Raised by fund_student/respond_to_award with a machine code for the view."""
    def __init__(self, code, message=''):
        self.code = code
        super().__init__(message or code)


def sponsor_balance(sponsor, programme):
    """A sponsor's spendable balance **within one gift programme** = donated to that
    programme − allocations in that programme that still hold (offered/active).
    Lapsed/cancelled allocations free up again.

    ``programme`` is REQUIRED and is the whole point: money given to one programme is
    never spendable in another (decisions.md, "Restricted funds and sponsor acceptance
    attach to the Programme"). Passing ``None`` scopes to the NULL bucket — the same
    safe degenerate partition the org fence uses — so bare test fixtures self-partition
    rather than silently pooling with real money.

    **This is the only spend authority.** Anything choosing whether a sponsor can fund a
    student must call this with that student's application programme. For a
    cross-programme DISPLAY figure use ``sponsor_available_total`` — never for a spend
    decision.
    """
    donated = (sponsor.donations
               .filter(programme=programme, status=Donation.STATUS_CONFIRMED)
               .aggregate(s=Sum('amount'))['s'] or Decimal('0'))
    held = (sponsor.sponsorships
            .filter(status__in=Sponsorship.HOLDING, application__programme=programme)
            .aggregate(s=Sum('amount'))['s'] or Decimal('0'))
    return donated - held


def visible_donations(sponsor):
    """**The ONE narrowing seam for every sponsor-facing read of the money-in ledger.**

    A sponsor sees a credit only once it is CONFIRMED. Before P4a every donation row was
    confirmed-by-existence, so `sponsor.donations.all()` was a safe spelling; the credit
    chain ended that — a `draft` / `admin_signed` / `cancelled` row is money that has NOT
    been signed off, and showing it to the sponsor would state, on their own statement,
    that we hold money we have not agreed we hold.

    Same shape and same reason as `pool.for_sponsor()`: one seam, so the next surface that
    lists donations narrows by construction instead of by remembering. A source guard
    (tests/test_wallet_credit.py) asserts every sponsor-facing donation read goes through
    here.

    NOT the spend authority — that is `sponsor_balance(sponsor, programme)`, which applies
    the same status filter *and* the programme restriction.
    """
    return sponsor.donations.filter(status=Donation.STATUS_CONFIRMED)


class CreditError(Exception):
    """Raised by the wallet-credit chain with a machine code for the view."""
    def __init__(self, code, message=''):
        self.code = code
        super().__init__(message or code)


@transaction.atomic
def record_admin_credit(*, sponsor, programme, amount, external_reference, admin):
    """Record an OFF-PLATFORM gift into a sponsor's programme wallet (P4).

    **This is the sole creator of a ``source='admin_recorded'`` Donation** — a source guard
    test asserts nothing else creates one, so an unconfirmed credit can never appear by a
    side door. The row opens at ``draft`` and is NOT spendable until the chain completes.

    Context: until BrightPath's CLBG is registered every sponsor pays into a personal
    account and an org admin keys the credit in here — *"real money is off the platform,
    but the consequences aren't"*. ``external_reference`` (the bank-transfer ref) is
    therefore mandatory: it is the only thread back to the money, and it is what makes each
    credit reconcile 1:1 with a bank-statement line (owner: one row per bank transfer).

    Creates the row at ``draft`` and stamps NO signature — recording and signing are
    separate acts, exactly as ``payments.create_run`` is separate from ``payments.sign``.
    The maker's signature is collected by ``sign_admin_credit`` with a typed name.

    Role gate: the MAKER's role (``admin``) or a super — the same gate that opens the
    chain. ``org_admin`` is deliberately NOT admitted here: on prod the person who does
    this work is Poongulali Veeran, a plain ``admin`` (verified against live roles,
    2026-07-26), and the approver must stay free to countersign.
    """
    if not (getattr(admin, 'is_super', False) or getattr(admin, 'role', '') == 'admin'):
        raise CreditError('wrong_role')
    if amount is None or amount <= 0:
        raise CreditError('invalid_amount')
    if not (external_reference or '').strip():
        raise CreditError('external_reference_required')
    if programme is None:
        raise CreditError('programme_required')
    if not _is_accepted_into(sponsor, programme):
        # A credit into a gift the sponsor was never accepted into would be money they
        # could not spend — and a sign the wrong sponsor or programme was picked.
        raise CreditError('sponsor_not_in_programme')
    return Donation.objects.create(
        sponsor=sponsor, programme=programme, amount=amount,
        source=Donation.SOURCE_ADMIN, external_reference=external_reference.strip(),
        reference=external_reference.strip(),
        status=Donation.STATUS_DRAFT,
    )


def _is_accepted_into(sponsor, programme):
    from .models import SponsorProgrammeMembership
    return SponsorProgrammeMembership.objects.filter(
        sponsor=sponsor, programme=programme, status='approved').exists()


# The gift a sponsor is onboarded into when they register through the public form. There is
# exactly one today and the form does not ask which gift, so it cannot mean anything else. When
# a second gift opens its own onboarding the programme comes from the form and this retires —
# it is the DEFAULT for the one registration path, never a fallback to lean on elsewhere.
DEFAULT_PROGRAMME_CODE = 'brightpath-flagship'


def sync_account_membership(sponsor, vetted_by=''):
    """Create or refresh this sponsor's membership of the DEFAULT gift, mirroring their ACCOUNT status.

    Migration ``0123`` gave every sponsor alive on 2026-07-25 a flagship membership copied from
    their account status — and **nothing was ever written to do the same for a sponsor who
    registers afterwards**. The first one to arrive (28/07) landed with zero memberships, which
    made them invisible to ``pool.for_sponsor`` (an empty student pool, no digest — see
    ``sponsor_notifications``) and un-creditable, because ``record_admin_credit`` refuses
    ``sponsor_not_in_programme``. This is that missing write.

    It mirrors ``0123`` EXACTLY — same programme, same "the membership copies the account
    status" rule — so a sponsor who registers today ends in the state they would have been in
    had they registered a week earlier. Called from registration (which opens it ``pending``)
    and from vetting (which settles it), and it is idempotent, so calling it on an existing
    sponsor heals a missing row rather than duplicating one.

    **Only the default gift's row is touched.** A membership of a second gift is a separate
    acceptance decision by the organisation running it, and must never be flipped as a
    side-effect of platform-level account vetting.

    Best-effort in the sense that a missing programme row (a bare or partial test DB, exactly as
    ``0123`` allows for) returns None rather than inventing an acceptance — but it does NOT
    swallow database errors: a registration that silently loses its membership is the bug this
    exists to fix.
    """
    from .models import SponsorProgrammeMembership
    programme = Programme.objects.filter(code=DEFAULT_PROGRAMME_CODE).first()
    if programme is None:
        return None
    settled = sponsor.status != 'pending'
    membership, created = SponsorProgrammeMembership.objects.get_or_create(
        sponsor=sponsor, programme=programme,
        defaults={
            'status': sponsor.status,
            'vetted_by': vetted_by if settled else '',
            'vetted_at': timezone.now() if settled else None,
        },
    )
    if not created and membership.status != sponsor.status:
        membership.status = sponsor.status
        membership.vetted_by = vetted_by
        membership.vetted_at = timezone.now()
        membership.save(update_fields=['status', 'vetted_by', 'vetted_at', 'updated_at'])
    return membership


def _collected_signer_emails(credit):
    """Every email that has already signed this credit, casefolded — the basis of the
    three-distinct-signers rule. Keyed on EMAIL, never on the displayed name: prod has two
    active admins sharing the name "Ve. Elanjelian", so a name key would be wrong in both
    directions (see the 0125 migration docstring). Mirrors
    ``payments._collected_signer_emails``."""
    return {
        (e or '').strip().casefold()
        for e in (credit.recorded_by_email, credit.finance_checked_by_email,
                  credit.confirmed_by_email)
        if (e or '').strip()
    }


@transaction.atomic
def sign_admin_credit(credit, admin, typed_name):
    """The maker→[finance]→approver sign-off for a wallet credit.

    **Deliberately ONE function with the same shape and the same guard names as
    ``payments.sign``** — the two chains are one design (decisions.md), and a single
    mirrored function is what stops them drifting into two subtly different controls.

      * DRAFT → the MAKER (role ``admin``, or super) signs → ``admin_signed``.
      * ADMIN_SIGNED, finance ACTIVE → only the CHECKER (role ``finance``, or super) may
        sign → ``finance_checked``. An org_admin trying to countersign here gets
        ``finance_check_required`` (told WHY, not a bare wrong_role — from their seat
        nothing looks amiss).
      * ADMIN_SIGNED, finance DORMANT → the APPROVER (``org_admin``, or super)
        countersigns → ``confirmed``. This is BrightPath's live path today.
      * FINANCE_CHECKED → the APPROVER countersigns → ``confirmed``.

    ``confirmed`` is the step that makes the money spendable (``Donation.is_spendable``).

    Guards: ``bad_state``; ``name_mismatch`` (typed name vs ``PartnerAdmin.name`` — this is
    what closed TD-176: before P4b the signer was a free string, so the chain enforced
    distinctness but NOT identity); ``wrong_role``; and ``same_signer`` — pairwise
    distinctness across every signature already collected, which is what confines a
    ``super`` to one slot per credit without a special case for supers.

    ``finance_check_required`` is evaluated LIVE at every attempt and never stored, so
    appointing a finance admin ARMS the check for a credit already mid-chain, and revoking
    the last one degrades it back to two steps. Both are inherited from the payments chain
    rather than reimplemented. Returns the credit.
    """
    from . import payments
    if credit.status not in (Donation.STATUS_DRAFT, Donation.STATUS_ADMIN_SIGNED,
                             Donation.STATUS_FINANCE_CHECKED):
        raise CreditError('bad_state')
    if not payments._name_matches(admin, typed_name):
        raise CreditError('name_mismatch')
    is_super = bool(getattr(admin, 'is_super', False))
    email = (admin.email or '').strip().casefold()
    now = timezone.now()
    needs_finance = payments.finance_check_required(_credit_org(credit))

    if credit.status == Donation.STATUS_DRAFT:
        if not (is_super or admin.role == 'admin'):
            raise CreditError('wrong_role')
        credit.recorded_by = (admin.name or '').strip()[:200]
        credit.recorded_by_email = (admin.email or '')[:254]
        credit.recorded_at = now
        credit.status = Donation.STATUS_ADMIN_SIGNED
        credit.save(update_fields=[
            'recorded_by', 'recorded_by_email', 'recorded_at', 'status'])
        return credit

    if credit.status == Donation.STATUS_ADMIN_SIGNED and needs_finance:
        if not (is_super or admin.role == 'finance'):
            if admin.role == 'org_admin':
                raise CreditError('finance_check_required')
            raise CreditError('wrong_role')
        if email in _collected_signer_emails(credit):
            raise CreditError('same_signer')
        credit.finance_checked_by = (admin.name or '').strip()[:200]
        credit.finance_checked_by_email = (admin.email or '')[:254]
        credit.finance_checked_at = now
        credit.status = Donation.STATUS_FINANCE_CHECKED
        credit.save(update_fields=[
            'finance_checked_by', 'finance_checked_by_email', 'finance_checked_at', 'status'])
        return credit

    # admin_signed (finance dormant) or finance_checked → the approver countersigns.
    if not (is_super or admin.role == 'org_admin'):
        raise CreditError('wrong_role')
    if email in _collected_signer_emails(credit):
        raise CreditError('same_signer')
    credit.confirmed_by = (admin.name or '').strip()[:200]
    credit.confirmed_by_email = (admin.email or '')[:254]
    credit.confirmed_at = now
    credit.status = Donation.STATUS_CONFIRMED
    credit.save(update_fields=[
        'confirmed_by', 'confirmed_by_email', 'confirmed_at', 'status'])
    # S3: tell the donor, but ONLY here — this is the single line in the chain where the money
    # becomes spendable, and it is the only point at which saying "we hold it" is true. Fired
    # from the SERVICE rather than the endpoint so a shell-driven confirmation notifies too, and
    # imported locally to keep this money module free of a hard dependency on the sending layer.
    from . import sponsor_notify
    sponsor_notify.send_credit_confirmed(credit)
    return credit


@transaction.atomic
def cancel_admin_credit(credit, admin):
    """Void a credit that has not yet been confirmed — a mis-keyed amount or bank reference
    would otherwise be permanent (the row is never deleted; the audit trail is the point).

    Maker's role or super, and only before ``confirmed``: once money is spendable it is
    reversed by a compensating entry, never by editing history."""
    if not (getattr(admin, 'is_super', False) or getattr(admin, 'role', '') in
            ('admin', 'org_admin')):
        raise CreditError('wrong_role')
    if credit.status not in (Donation.STATUS_DRAFT, Donation.STATUS_ADMIN_SIGNED,
                             Donation.STATUS_FINANCE_CHECKED):
        raise CreditError('bad_state')
    credit.status = Donation.STATUS_CANCELLED
    credit.save(update_fields=['status'])
    return credit


def _credit_org(credit):
    """The organisation whose finance role governs this credit — the one running the gift."""
    return credit.programme.organisation if credit.programme_id else None


def _money(value):
    """Money as a 2-decimal string, ALWAYS.

    A `DecimalField` read gives `'3000.00'` but a `Sum()` aggregate over the same column
    gives `'20000'` — so a payload mixing the two renders "RM 20000" beside "RM 3,000.00"
    on the same card. Quantising here rather than in the template keeps every money string
    the API emits the same shape.
    """
    return str((value or Decimal('0')).quantize(Decimal('0.01')))


def _wallet_programmes(sponsor):
    """**The one home for "which wallets does this sponsor hold".** Every programme they
    have donated into or allocated within, resolved to `Programme` objects (None for the
    NULL bucket) and ordered by id so output is stable.

    Extracted so `sponsor_programme_balances` and `programme_ledger` cannot drift: the
    set of wallets a sponsor holds must be the same question wherever it is asked.
    """
    programme_ids = set(
        visible_donations(sponsor).values_list('programme_id', flat=True)
    ) | set(
        sponsor.sponsorships.filter(status__in=Sponsorship.HOLDING)
        .values_list('application__programme_id', flat=True)
    )
    by_id = {p.id: p for p in Programme.objects.filter(id__in=[i for i in programme_ids if i])}
    return [by_id.get(pid) for pid in sorted(programme_ids, key=lambda i: (i is None, i))]


def sponsor_programme_balances(sponsor):
    """Every wallet this sponsor holds: ``[(programme, balance), ...]``. Display +
    reconciliation; per-wallet figures here are each a real spend authority, the *sum*
    of them is not."""
    return [(p, sponsor_balance(sponsor, p)) for p in _wallet_programmes(sponsor)]


def programme_ledger(sponsor):
    """Per-wallet money, split three ways for an ADMIN reading one sponsor.

    ``[{'programme': p|None, 'given', 'committed', 'available', 'credits', 'students'}]``

    - **given** — CONFIRMED donations only (through `visible_donations`, so a draft or
      cancelled credit is money we have not agreed we hold and never appears).
    - **committed** — allocations still HOLDING (offered or active) in this programme.
    - **available** — `sponsor_balance`, i.e. given − committed. Recomputed by the
      authority rather than subtracted here, so this display can never disagree with
      the figure that actually authorises a spend.
    """
    out = []
    for programme in _wallet_programmes(sponsor):
        confirmed = visible_donations(sponsor).filter(programme=programme)
        holding = sponsor.sponsorships.filter(
            status__in=Sponsorship.HOLDING, application__programme=programme)
        out.append({
            'programme': programme,
            'given': _money(confirmed.aggregate(s=Sum('amount'))['s']),
            'committed': _money(holding.aggregate(s=Sum('amount'))['s']),
            'available': _money(sponsor_balance(sponsor, programme)),
            'credits': confirmed.count(),
            'students': holding.count(),
        })
    return out


def sponsor_available_total(sponsor):
    """DISPLAY ONLY — the sum of every wallet this sponsor holds. **Never a spend
    authority**: a total across programmes is not spendable anywhere, because each
    ringgit is restricted to the programme it was given to. Use ``sponsor_balance``
    with an explicit programme for any funding decision."""
    return sum((bal for _p, bal in sponsor_programme_balances(sponsor)), Decimal('0'))


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
            'available': str(sponsor_available_total(sponsor)),
        },
    }


def sponsor_statement(sponsor):
    """R4 — the giving statement's two ledgers. **Donations INTO the trust** (the
    sponsor's own deposit records — fine to show back to them) and **gifts OUT to
    students** (active allocations carrying the anonymous ``ref`` only — never the
    student's identity). Allowlist-safe; counts + money + refs only."""
    donations = [
        {'amount': str(d.amount), 'reference': d.reference, 'at': d.created_at}
        for d in visible_donations(sponsor).order_by('-created_at')
    ]
    gifts = []
    out_total = Decimal('0')
    for sp in (sponsor.sponsorships.filter(status='active')
               .select_related('application').order_by('-decided_at')):
        gifts.append({'ref': pool.pool_ref(sp.application_id), 'amount': str(sp.amount), 'at': sp.decided_at})
        out_total += sp.amount
    # Allocations that HOLD the balance but are not yet accepted by the student. Without
    # this line the statement contradicts the wallet: while award acceptance is switched
    # off nothing ever reaches 'active', so a sponsor with every ringgit allocated read
    # "RM172,000 in / RM0 out" beside a balance that said otherwise. Kept as its own
    # total rather than folded into `total_out` — committed is not yet given away, and
    # `gifts` is the settled record.
    committed = []
    committed_total = Decimal('0')
    for sp in (sponsor.sponsorships.filter(status='offered')
               .select_related('application').order_by('-offered_at')):
        committed.append({'ref': pool.pool_ref(sp.application_id),
                          'amount': str(sp.amount), 'at': sp.offered_at})
        committed_total += sp.amount
    in_total = sum((Decimal(d['amount']) for d in donations), Decimal('0'))
    return {
        'donations': donations,
        'gifts': gifts,
        'committed': committed,
        'total_in': str(in_total),
        'total_out': str(out_total),
        'total_committed': str(committed_total),
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
    if not is_fundable(application):
        raise SponsorshipError('not_fundable')
    amount = application.award_amount
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
    is sent later by ``release_award_offer_emails`` once the award is
    ``AWARD_OFFER_EMAIL_COOLOFF_HOURS`` old, leaving a window to reconsider (cancelling the award
    before then stops the email). Kept as the named single entry point so the button and the batch
    behave identically."""
    return fund_student(sponsor, application)   # atomic; raises SponsorshipError on a bad state


def release_award_offer_emails(now=None):
    """Send the award email for every HOLDING award whose cool-off has elapsed and that hasn't been
    emailed yet (``offered_at + AWARD_OFFER_EMAIL_COOLOFF_HOURS <= now`` and ``offer_emailed_at`` is
    NULL). A cancelled/lapsed award (no longer offered/active) is skipped, so reconsidering within
    the window stops the email. Hourly scheduler (job ``release-award-offer-emails``). Returns the
    count sent.

    ``offer_emailed_at`` is stamped ONLY ON SUCCESS (changed 2026-07-12). It previously stamped
    either way, on the reasoning that a transient failure "never re-floods" — but the query filters
    on ``offer_emailed_at IS NULL``, so a single failed send permanently suppressed that student's
    email and they would simply never learn they had won. That is a far worse outcome than a retry,
    and the same fix was already made in ``send_award_offer_emails`` (code-health S3 #7); this path
    was missed. A genuinely undeliverable address now retries hourly — visible in the logs, and
    fixable — rather than failing silently forever.

    On a successful send it also raises the Vircle setup task, because the email now carries the
    Vircle instructions and the task it points at must exist by the time the student reads it."""
    from django.conf import settings as _settings
    now = now or timezone.now()
    hours = getattr(_settings, 'AWARD_OFFER_EMAIL_COOLOFF_HOURS', 24)
    cutoff = now - timezone.timedelta(hours=hours)
    # Contract mode (go-live transition, 2026-07-19): when the bursary agreement flag is ON the
    # good-news email invites the student to REVIEW & SIGN the agreement, carries NO Vircle content,
    # and raises NO Vircle setup task here — the Vircle install email + task now fire automatically
    # at agreement EXECUTION (bursary.distribute_executed_agreement). When the flag is OFF the path
    # below is byte-identical to before (Vircle-flavoured award email + raise_setup_task).
    bursary_on = getattr(_settings, 'BURSARY_AGREEMENT_ENABLED', False)
    qs = (Sponsorship.objects
          .filter(status__in=Sponsorship.HOLDING, offer_emailed_at__isnull=True, offered_at__lte=cutoff)
          .select_related('application', 'application__profile'))
    sent = 0
    for sp in qs:
        app = sp.application
        name = getattr(app.profile, 'name', '') if app.profile else ''
        if bursary_on:
            ok = send_award_offer_sign_email(
                to_email=app.notify_email, applicant_name=name,
                lang=getattr(app, 'locale', '') or 'en')
            if not ok:
                continue   # stamp only on success (see below); retry next run
            sp.offer_emailed_at = now
            sp.save(update_fields=['offer_emailed_at', 'updated_at'])
            sent += 1
            continue   # NO Vircle task on the contract-mode path — it's raised at execution
        from .vircle import can_register
        ok = send_award_offer_email(
            to_email=app.notify_email, applicant_name=name, lang=getattr(app, 'locale', '') or 'en',
            guardian_note=not can_register(app))
        if not ok:
            # Stamp ONLY on success. This query filters offer_emailed_at__isnull=True, so stamping
            # a FAILED send would permanently suppress that student's award email — they'd simply
            # never hear they won. Leaving it unstamped means the next hourly run retries.
            # (The same fix was made in send_award_offer_emails; this path was missed.)
            continue
        sp.offer_emailed_at = now
        sp.save(update_fields=['offer_emailed_at', 'updated_at'])
        # The award email now CARRIES the Vircle instructions, so the task it refers to must exist
        # the moment the student reads it — but never for a student whose email failed.
        raise_setup_task(app)
        sent += 1
    return sent


def current_offer(application):
    """The single open ('offered') award for this application, or None."""
    return application.sponsorships.filter(status='offered').order_by('-offered_at').first()


def arm_sign_deadline(application, *, now=None):
    """Offer-lapse rework (go-live transition): ARM the accept clock on this application's open
    offer — ``accept_deadline = now + SIGN_ACCEPT_DEADLINE_DAYS``. Called when the sign-invitation
    email is actually sent (see the ``send_sign_invitation_emails`` command), so the student then
    has that window to sign before the offer may lapse. No-op (returns None) if there is no open
    offer. Re-arming an already-armed offer simply resets the window (a resend extends the clock)."""
    from django.conf import settings as _settings
    sp = current_offer(application)
    if sp is None:
        return None
    now = now or timezone.now()
    days = getattr(_settings, 'SIGN_ACCEPT_DEADLINE_DAYS', 30)
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
    the email. Locked FOR UPDATE so a cancel can't race ``release_award_offer_emails`` and land on
    the wrong side of that line. Raises SponsorshipError on a bad state."""
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
    # Offer-lapse rework: the agreement has bound (student + guarantor signed above, flag-ON) —
    # the accept clock is FULFILLED, so clear any armed deadline. (The status also leaves 'offered'
    # here, which alone takes it out of the lapse query; clearing the deadline keeps the record
    # honest and belt-and-braces.)
    sponsorship.accept_deadline = None
    sponsorship.save(update_fields=['status', 'consent', 'decided_at', 'accept_deadline', 'updated_at'])

    # Flag-ON (bursary signing) path: the app stays 'awarded' until the Foundation counter-signs
    # (the binding, last signature) — bursary.countersign_foundation flips 'awarded' → 'active'.
    # The student + guarantor have just signed; notify the next party in the chain (partner
    # witness if a referring org exists, else the Foundation directly). Best-effort.
    if getattr(_settings, 'BURSARY_AGREEMENT_ENABLED', False):
        from . import bursary
        bursary.notify_after_guarantor_signed(application)
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
    fields = ['status', 'award_due_at']
    if application.stamp_first('active_at'):
        fields.append('active_at')
    application.save(update_fields=fields)
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


def lapse_holding_sponsorships(application, *, now=None):
    """Lapse EVERY holding (offered/active) sponsorship on this application — each held
    amount returns to its sponsor's balance (balance = donations − holding allocations,
    so a lapsed row simply stops being subtracted). For a student who leaves the
    programme outside the normal offer-decline/closure flow — e.g. a contractual admin
    reject of a funded student (code-health S3 #6): without this, the sponsorship sat
    HOLDING forever, the sponsor's balance stayed reduced, and impact/statement surfaces
    kept reporting the rejected student as actively supported. Returns the rows lapsed."""
    now = now or timezone.now()
    lapsed = []
    for sp in application.sponsorships.filter(status__in=Sponsorship.HOLDING):
        sp.status = 'lapsed'
        sp.decided_at = now
        sp.save(update_fields=['status', 'decided_at', 'updated_at'])
        lapsed.append(sp)
    return lapsed


def reinstate_lapsed_sponsorship(application, *, since):
    """Best-effort undo of ``lapse_holding_sponsorships`` for a CANCELLED contractual
    decline: put the most recently lapsed sponsorship (lapsed at/after ``since``) back to
    'active' — but only when the sponsor's balance still covers the amount (they may have
    reallocated the returned money in the window). Returns the sponsorship on success,
    None when there is nothing to reinstate or the balance no longer covers it (the case
    then needs re-funding; the caller logs it)."""
    sp = (application.sponsorships.filter(status='lapsed', decided_at__gte=since)
          .order_by('-decided_at').select_related('sponsor').first())
    if sp is None:
        return None
    # Reinstatement spends from the wallet of the programme this student belongs to.
    if sponsor_balance(sp.sponsor, application.programme) < sp.amount:
        return None
    sp.status = 'active'
    sp.decided_at = timezone.now()
    sp.save(update_fields=['status', 'decided_at', 'updated_at'])
    return sp


def lapse_expired_offers():
    """Lapse every 'offered' award whose ARMED accept_deadline has passed (the amount returns to
    the sponsor's balance; the application reverts to the pool). Intended for a scheduled job.

    Offer-lapse rework (go-live transition, 2026-07-19, owner decision 3):
      • ARMED-ONLY. A NULL ``accept_deadline`` means the sign-invitation clock was never started,
        so the offer is NOT a lapse candidate. (Django's ``accept_deadline__lt=now`` already
        excludes NULLs; ``isnull=False`` makes the intent explicit.)
      • PAID APPS NEVER AUTO-LAPSE. An application with any released disbursement (e.g. the
        grandfather cohort, already being paid while their in-app acceptance is back-filled) is
        REFUSED — it is logged and returned in ``flagged`` for an admin to handle by hand, never
        silently lapsed out from under real money.

    Returns ``{'lapsed': <count>, 'flagged': [<application_id>, ...]}``. (The cron that calls this
    is still UNSCHEDULED — it may only ever be wired against THESE semantics; see
    docs/technical-debt.md (c).)"""
    now = timezone.now()
    expired = list(Sponsorship.objects
                   .filter(status='offered', accept_deadline__isnull=False, accept_deadline__lt=now)
                   .select_related('application'))
    lapsed = 0
    flagged = []
    for sp in expired:
        app = sp.application
        if app.disbursements.filter(status='released').exists():
            # Released money against this application → never auto-lapse. Flag for admin review.
            flagged.append(app.id)
            logger.warning(
                'lapse_expired_offers: REFUSED to lapse app %s (sponsorship %s) — it has released '
                'disbursements. Flagged for admin review.', app.id, sp.id)
            continue
        sp.status = 'lapsed'
        sp.decided_at = now
        sp.save(update_fields=['status', 'decided_at', 'updated_at'])
        _revert_to_pool(app)   # offer expired unaccepted → back in the pool
        lapsed += 1
    return {'lapsed': lapsed, 'flagged': flagged}
