"""
Money in and money out: donations, sponsorships, disbursements, payment runs.

Moved here VERBATIM from `apps/scholarship/models.py` at code health H15 (2026-09-20).
Moves only: no field, no `Meta`, no `db_table`, no `related_name` was touched, so the
database is untouched too — `makemigrations --check` reports no changes. See `__init__.py`.
"""
from django.db import models

from .applications import ScholarshipApplication
from .documents import ApplicantDocument, Consent
from .sponsors import Sponsor

class Donation(models.Model):
    """Phase E3: money a sponsor donates into myNADI (via toyyibPay; mocked until
    the gateway is wired). A donation is FINAL — it is myNADI's money. It credits
    the sponsor's internal **directed-giving balance** (donations − active
    allocations); the sponsor can only redirect that balance within the platform,
    never withdraw it to a bank. Outbound disbursement is a later, gated phase."""
    sponsor = models.ForeignKey(
        Sponsor, on_delete=models.CASCADE, related_name='donations',
    )
    # Platform programme layer (2026-07-26): the gift programme this money was given TO.
    # Funds given to one programme are never visible or spendable in another — a donor
    # gives to "Sabah", not to the platform at large (decisions.md, "Restricted funds and
    # sponsor acceptance attach to the Programme"). The wallet is therefore per
    # (sponsor, programme), never one pool. NULL only for bare test fixtures; prod is
    # backfilled to the flagship. Balance reads go through sponsorship.sponsor_balance().
    programme = models.ForeignKey(
        'Programme', on_delete=models.PROTECT,
        null=True, blank=True, related_name='donations',
        help_text='The gift programme this donation is restricted to.',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    # toyyibPay billCode/ref once real; 'mock' for dev/dummy donations.
    reference = models.CharField(max_length=100, blank=True, default='mock')
    created_at = models.DateTimeField(auto_now_add=True)

    # ── Provenance + sign-off (P4, 2026-07-26) ────────────────────────────────────
    # ONE record, different provenance — an admin-recorded credit today and a gateway
    # donation post-CLBG are the same row with a different `source`, never two parallel
    # money systems (decisions.md, "Money is OFF-platform until the CLBG exists").
    SOURCE_LEGACY = 'legacy'                # pre-P4 rows; provenance not recorded
    SOURCE_ADMIN = 'admin_recorded'         # off-platform gift, keyed in by an org admin
    SOURCE_GATEWAY = 'gateway'              # paid through the platform (post-CLBG)
    SOURCE_MOCK = 'mock'                    # dev/self-service stub — never real money
    SOURCES = [
        (SOURCE_LEGACY, 'Legacy'), (SOURCE_ADMIN, 'Admin-recorded'),
        (SOURCE_GATEWAY, 'Gateway'), (SOURCE_MOCK, 'Mock'),
    ]
    source = models.CharField(max_length=20, choices=SOURCES, default=SOURCE_LEGACY)
    # The bank-transfer reference. MANDATORY for an admin-recorded credit — it is the only
    # thread back to real money while the cash sits in an account the platform cannot see,
    # and what lets each credit reconcile 1:1 with a line on the bank statement (owner:
    # "one row per bank transfer").
    external_reference = models.CharField(max_length=120, blank=True, default='')

    # Sign-off chain — DELIBERATELY the same shape as PaymentRun's
    # (`draft → admin_signed → [finance_checked] → confirmed`), and the finance step is
    # likewise CONDITIONAL and never stored: payments.finance_check_required(organisation)
    # is evaluated live, so appointing a finance admin arms the check even for a credit
    # already mid-chain. ⚠ A change to the payment-run chain must update this one in the
    # same commit — they are one design (decisions.md).
    STATUS_DRAFT = 'draft'
    STATUS_ADMIN_SIGNED = 'admin_signed'
    STATUS_FINANCE_CHECKED = 'finance_checked'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUSES = [
        (STATUS_DRAFT, 'Draft'), (STATUS_ADMIN_SIGNED, 'Admin signed'),
        (STATUS_FINANCE_CHECKED, 'Finance checked'), (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]
    # Default 'confirmed': money that arrived by gateway/legacy IS confirmed by arrival.
    # ONLY the admin-recorded path opens at 'draft' — see sponsorship.record_admin_credit,
    # which is the sole creator of a SOURCE_ADMIN row (asserted by a source guard test).
    status = models.CharField(max_length=20, choices=STATUSES, default=STATUS_CONFIRMED)
    # Each signature is a (name, email) PAIR, exactly as PaymentRun stores it. The EMAIL is
    # the identity key — pairwise distinctness is computed on it, never on the name. This is
    # not theoretical tidiness: prod carries TWO active admins both named "Ve. Elanjelian"
    # (a super and an org_admin, different accounts), so a name-keyed rule would BOTH let one
    # person fill two slots under two names AND wrongly refuse two genuinely different people
    # who share one. The name is stored for display and for the typed-name match only.
    recorded_by = models.CharField(max_length=200, blank=True, default='')
    recorded_by_email = models.CharField(max_length=254, blank=True, default='')
    recorded_at = models.DateTimeField(null=True, blank=True)
    finance_checked_by = models.CharField(max_length=200, blank=True, default='')
    finance_checked_by_email = models.CharField(max_length=254, blank=True, default='')
    finance_checked_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.CharField(max_length=200, blank=True, default='')
    confirmed_by_email = models.CharField(max_length=254, blank=True, default='')
    confirmed_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_spendable(self):
        """Only a CONFIRMED credit raises spendable balance. A recorded-but-unconfirmed
        credit is visible to admins and invisible to the sponsor, so it can never be
        allocated to a student before the second signature."""
        return self.status == self.STATUS_CONFIRMED

    class Meta:
        db_table = 'sponsor_donations'
        ordering = ['-created_at']

    def __str__(self):
        return f'Donation {self.amount} by sponsor={self.sponsor_id}'


class Sponsorship(models.Model):
    """Phase E3: a sponsor's ALLOCATION of their donated balance to one (anonymous)
    student, for that student's admin-set award amount.

    Flow (1:1, full-or-nothing for now; many-sponsor plumbing underneath):
    sponsor funds in full → 'offered' (award letter issued) → student/guardian
    accepts within the deadline → 'active' (app → 'sponsored', leaves the pool);
    if not accepted in time → 'lapsed' and the amount returns to the sponsor's
    balance (a lapsed/cancelled allocation simply stops being subtracted — no
    bank refund). **Anonymity holds both ways:** the sponsor never sees the
    student's identity (allowlist card/blurb), and the student never sees the
    sponsor's identity (decided with the user). No tranches/disbursement this
    slice — that is E3b."""
    STATUS = [
        ('offered', 'Offered'),     # funded in full; award letter issued; awaiting acceptance
        ('active', 'Active'),        # student/guardian accepted; the match is live
        ('lapsed', 'Lapsed'),        # not accepted in time → amount returned to balance
        ('cancelled', 'Cancelled'),  # sponsor withdrew the offer before acceptance
    ]
    # Allocations that still hold the sponsor's balance (subtracted from donations).
    HOLDING = ('offered', 'active')

    sponsor = models.ForeignKey(
        Sponsor, on_delete=models.CASCADE, related_name='sponsorships',
    )
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='sponsorships',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS, default='offered')
    # The consent recorded when the student/guardian accepted. Null until accepted —
    # a Sponsorship is never 'active' without one.
    consent = models.ForeignKey(
        Consent, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    accept_deadline = models.DateTimeField(null=True, blank=True)
    offered_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    # When the award good-news email was sent (or the award was handled without one, e.g.
    # a pre-existing/embargoed award backfilled so the cool-off cron never re-emails it).
    # NULL = still pending; the release cron emails once offered_at + the cool-off elapses.
    offer_emailed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sponsorships'
        ordering = ['-offered_at']
        constraints = [
            # 1 sponsor per student (for now): at most one HOLDING (offered/active)
            # sponsorship per application.
            models.UniqueConstraint(
                fields=['application'], condition=models.Q(status__in=['offered', 'active']),
                name='uniq_holding_sponsorship_per_app'),
        ]

    @property
    def is_active(self):
        return self.status == 'active'

    def __str__(self):
        return f'Sponsorship #{self.id} sponsor={self.sponsor_id} app={self.application_id} {self.amount} ({self.status})'


class Disbursement(models.Model):
    """Post-award lifecycle S4: the money-OUT ledger — a single tranche of a funded
    award, paid (eventually) to the student.

    This is a LEDGER, not custody: real disbursement via toyyibPay is deferred
    (TD-075), so ``release_tranche`` records a 'released' row with a mock reference
    rather than moving real money. A tranche is scheduled against a funded
    application; an admin marks it disbursed. **The first ``released`` tranche flips
    the application ``active`` → ``maintenance``** (it enters the recurring funded
    loop — see ``disbursement.release_tranche``).

    ``sponsorship`` is the allocation that funds the tranche (nullable + SET_NULL so a
    future Foundation-direct award with no Sponsorship row still works, and deleting a
    Sponsorship never erases the disbursement history). Anonymity is unaffected: this
    row never crosses to a sponsor surface, and the student's award view never names a
    sponsor."""
    STATUS = [
        ('scheduled', 'Scheduled'),  # planned tranche, not yet payable
        ('due', 'Due'),              # payable now (admin/cron) — awaiting release
        ('released', 'Released'),    # marked disbursed (mock until TD-075)
        ('withheld', 'Withheld'),    # admin held it back (probation / failed results — S5)
        ('returned', 'Returned'),    # money returned (withdrawal / termination)
    ]
    # Tranches that represent money actually paid out (for "has any release happened").
    PAID = ('released',)

    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='disbursements',
    )
    # The allocation funding this tranche. Nullable for a future Foundation-direct
    # award; SET_NULL so disbursement history survives a Sponsorship delete.
    sponsorship = models.ForeignKey(
        Sponsorship, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='disbursements',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS, default='scheduled')
    # 1-based tranche number within the award (Semester 1, 2, …) — drives ordering and
    # the "first release" flip.
    sequence = models.PositiveSmallIntegerField(default=1)
    label = models.CharField(max_length=100, blank=True, default='')
    scheduled_for = models.DateField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    # Admin email who released/withheld/returned it — audit (mirrors verified_by etc.).
    actioned_by = models.CharField(max_length=254, blank=True, default='')
    # toyyibPay billCode/ref once real; 'mock' for the dark ledger.
    reference = models.CharField(max_length=100, blank=True, default='mock')
    note = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'disbursements'
        ordering = ['sequence', 'id']

    def __str__(self):
        return f'Disbursement #{self.id} app={self.application_id} seq={self.sequence} {self.amount} ({self.status})'


class BankAccount(models.Model):
    """The student's bank account for the bursary payout — captured post-award via the
    Action Centre (upload a bank statement → Gemini pre-fills → the student confirms).

    The three CONFIRMED fields are authoritative (the student reviews/corrects the
    Gemini read before saving, because a misread account digit would misdirect money).
    The HOLDER MUST BE THE STUDENT — a hard rule (no parent/joint accounts); the save
    endpoint re-checks ``account_holder`` against the application name and refuses a
    mismatch. ``source_doc`` links the bank statement the data came from (SET_NULL so
    a re-upload of the proof never erases the confirmed account).

    Financial PII → its own table + RLS (service-role only), not stuffed in
    ``OnboardingResponse.answers``. Stored only; not shown on any surface yet — an
    officer payout view is a later step (real disbursement = TD-075)."""
    HOLDER_VERDICTS = [('ok', 'Holder matches the student')]

    application = models.OneToOneField(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='bank_account',
    )
    bank_name = models.CharField(max_length=120)
    account_number = models.CharField(max_length=40)
    account_holder = models.CharField(max_length=200)
    # The bank statement the fields were read from. Nullable + SET_NULL so the account
    # survives a re-upload/removal of the proof document.
    source_doc = models.ForeignKey(
        ApplicantDocument, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bank_accounts',
    )
    # Recorded at confirm time — only 'ok' ever persists (the holder==student gate is
    # hard), kept for an audit trail + future tolerance changes.
    holder_verdict = models.CharField(max_length=20, choices=HOLDER_VERDICTS, default='ok')
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bank_accounts'

    def __str__(self):
        return f'BankAccount app={self.application_id} {self.bank_name} ****{self.account_number[-4:]}'


class PaymentRun(models.Model):
    """A monthly Vircle payment run for one organisation (Payments module, D1/D2).

    Holds the WORKING state — draft amounts, per-student include/exclude, the two typed
    signatures — on TOP of the immutable Disbursement ledger. Released Disbursement rows are
    created ONLY at countersignature (``payments.complete``), so "paid to date" is always
    ``SUM(released disbursements)`` — one source of truth for history, the backfill, and
    future runs alike (D1).

    Sign-off is a maker→checker chain (D2): ``draft → admin_signed → [finance_checked] →
    completed`` (+ ``cancelled``). The status field + a per-step signature TRIPLE
    (name/email/at) — not a boolean pair — is what let the finance 'checker' step land
    additively (Sprint 14, 2026-07-23) exactly where this docstring parked it.

    **The finance step is CONDITIONAL and its requirement is never stored here.**
    ``payments.finance_check_required(organisation)`` is evaluated LIVE at each sign attempt
    (the org has ≥1 active ``finance`` PartnerAdmin). With none, the chain runs as the
    original two steps, byte-identical. Deliberately not a column: storing it would freeze a
    run's shape at creation, and the owner's rule is that activating finance DOES arm the
    check for a run already sitting at ``admin_signed``. A historical ``completed`` run
    simply carries an empty finance triple — read it as "no finance admin existed", not as
    "the step was skipped".

    Backfill runs (D8) are first-class ``completed`` runs with no signatures (the signature
    fields are nullable/blank)."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('admin_signed', 'Admin signed'),
        ('finance_checked', 'Finance checked'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT, related_name='payment_runs',
    )
    # The GIFT this run pays from (P2b). A run pays students of ONE programme, so a benefactor's
    # money can never leave the gift it was given to and each programme reconciles on its own.
    # NULLABLE for history: every run created before P2b is backfilled to its items' programme,
    # and the column stays nullable so a legacy row is never rewritten into a claim it cannot
    # support. New runs REQUIRE it — enforced in `payments.create_run`, not by the column, so
    # the rule lives with the behaviour rather than in a schema constraint that would also
    # refuse the backfill.
    programme = models.ForeignKey(
        'Programme', on_delete=models.PROTECT, related_name='payment_runs',
        null=True, blank=True,
    )
    payment_date = models.DateField(help_text="The Vircle payment date; validated >= today at creation.")
    # The MONTH this run pays for (1st of that month). A run dated 30 Jun can pay for July, so the
    # covered month is explicit, not derived from payment_date. A student already paid for a month
    # (via a completed run with the same period_month) is excluded — no double-paying a month.
    period_month = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    reference = models.CharField(
        max_length=50, unique=True,
        help_text="e.g. 'PR-2026-08-001'; 'backfill-YYYY-MM-DD' for imports.")
    created_by = models.CharField(max_length=254, blank=True, default='')
    # Maker (first signature, role admin), then approver (countersignature, role org_admin) — D2.
    admin_signed_name = models.CharField(max_length=200, blank=True, default='')
    admin_signed_email = models.CharField(max_length=254, blank=True, default='')
    admin_signed_at = models.DateTimeField(null=True, blank=True)
    # Finance checker (middle signature, role finance) — Sprint 14. Empty on every run made
    # before the role existed, and on every run in an org with no active finance admin.
    finance_signed_name = models.CharField(max_length=200, blank=True, default='')
    finance_signed_email = models.CharField(max_length=254, blank=True, default='')
    finance_signed_at = models.DateTimeField(null=True, blank=True)
    org_admin_signed_name = models.CharField(max_length=200, blank=True, default='')
    org_admin_signed_email = models.CharField(max_length=254, blank=True, default='')
    org_admin_signed_at = models.DateTimeField(null=True, blank=True)
    # The CSV handed to Vircle (best-effort Drive write, D7); blank if the upload failed.
    drive_file_url = models.URLField(blank=True, default='')
    note = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payment_runs'
        ordering = ['-payment_date', '-id']

    def __str__(self):
        return f'PaymentRun {self.reference} {self.payment_date} ({self.status})'


class PaymentRunItem(models.Model):
    """One student's line in a PaymentRun. Amounts + the award/paid/vircle SNAPSHOTS freeze
    at creation so the signed record can't drift after signatures are collected; the
    ``disbursement`` is linked when the run completes."""
    run = models.ForeignKey(PaymentRun, on_delete=models.CASCADE, related_name='items')
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.PROTECT, related_name='payment_run_items',
    )
    included = models.BooleanField(default=True)
    exclude_reason = models.CharField(max_length=200, blank=True, default='')  # required when excluded
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)   # editable in draft; capped at remaining
    credit_applied = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="How much payment_credit this item consumed (audit; decremented at completion).")
    # Snapshots at creation (so the signed record can't drift):
    award_amount_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_to_date_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    vircle_id_snapshot = models.CharField(max_length=30, blank=True, default='')
    # Set at completion — the released Disbursement this item produced. SET_NULL so deleting a
    # Disbursement never erases the run history.
    disbursement = models.ForeignKey(
        Disbursement, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_run_items',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payment_run_items'
        unique_together = ('run', 'application')
        ordering = ['id']

    def __str__(self):
        return f'PaymentRunItem run={self.run_id} app={self.application_id} {self.amount}'
