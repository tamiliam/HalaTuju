"""
A tenant invoice, its lines and its receipts — issued once, never rewritten.

Moved here VERBATIM from `apps/scholarship/models.py` at code health H15 (2026-09-20).
Moves only: no field, no `Meta`, no `db_table`, no `related_name` was touched, so the
database is untouched too — `makemigrations --check` reports no changes. See `__init__.py`.
"""
from django.db import models

class Invoice(models.Model):
    """A tenant's bill for ONE month, frozen at the moment it was issued.

    ⚠ **NOTHING ON THIS ROW IS EVER RECOMPUTED.** The lines, the discount, the issuer and the
    bill-to are copied in at issue time. A later rate change, a late ledger row or an edited
    address changes the NEXT invoice, never this one. A wrong invoice is VOIDED with a reason and
    a replacement is issued; it is never edited. That is the whole difference between a bill and
    the readout the billing screen already had.

    ⚠ **THE TENANT COPY CARRIES NO COST AND NO MARGIN.** Lines hold what is charged, and for
    development the hours at the billed rate, so every line multiplies out. What the platform paid
    and the margin on top stay on the super-only costs screen, as they always have.

    Status is DERIVED (`status`), not stored: void if voided, paid when the receipts cover the
    total, part paid when some do, sent once Send succeeded, else issued. A stored status is a
    second answer to "has this been paid?", and two answers eventually disagree.
    """
    number = models.CharField(max_length=20, unique=True,
                              help_text="'INV-YYYY-NNNN', numbered by the year of issue.")
    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT, related_name='invoices')
    period_month = models.CharField(max_length=7, help_text="The month billed, 'YYYY-MM'.")
    issued_on = models.DateField()
    due_on = models.DateField()
    currency = models.CharField(max_length=3, default='MYR')
    subtotal_myr = models.DecimalField(max_digits=12, decimal_places=2)
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_myr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_reason = models.TextField(blank=True, default='')
    # ── Corrections of EARLIER months, frozen here the way the discount is ──
    # ⚠ FIELDS, NOT LINES, and deliberately so. `build_lines` proves the lines add up to the
    # SUBTOTAL; a correction belongs AFTER the discount, so putting it among the lines would break
    # that check or quietly change what it means. The discount already works exactly this way.
    # The month reads: subtotal -> discount -> corrections -> total.
    #
    # ⚠ NULLABLE for the same mechanical reason as `InvoiceReceipt.emailed_to`: a NOT NULL column
    # added to an EXISTING table cannot be rendered offline for Postgres (Django adapts the
    # default through the live driver, or composes a `db_default` literal through a real cursor),
    # and migrate-first depends on that offline render. NULL reads as "none", through `or`.
    corrections_myr = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='SIGNED total of the corrections carried onto this invoice. Negative reduces '
                  'what is owed. NULL = none.')
    corrections_snapshot = models.JSONField(
        null=True, blank=True, default=None,
        help_text='The corrections as they read WHEN ISSUED — amount, reason, which invoice they '
                  'put right. Frozen like issuer_snapshot: editing the source row later must '
                  'never rewrite a document already sent.')
    total_myr = models.DecimalField(max_digits=12, decimal_places=2)
    issuer_snapshot = models.JSONField(default=dict)
    bill_to_snapshot = models.JSONField(default=dict)
    issued_by_email = models.EmailField(
        blank=True, default='',
        help_text='Blank = issued by the monthly job on the 15th.')
    override_reason = models.TextField(
        blank=True, default='',
        help_text='Set only when a super issued it despite a readiness warning — the warning and '
                  'why it was overridden, so the decision survives the person who made it.')
    replaces = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True, related_name='replaced_by',
        help_text='The voided invoice this one was issued to replace.')
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by_email = models.EmailField(blank=True, default='')
    sent_to = models.JSONField(default=list, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by_email = models.EmailField(blank=True, default='')
    void_reason = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'invoices'
        ordering = ['-period_month', '-issued_on', '-id']
        constraints = [
            # One LIVE invoice per tenant per month. A voided one does not count, which is what
            # lets its replacement exist.
            models.UniqueConstraint(
                fields=['organisation', 'period_month'],
                condition=models.Q(voided_at__isnull=True),
                name='invoice_one_live_per_org_month'),
        ]
        indexes = [
            models.Index(fields=['organisation', 'period_month'], name='invoice_org_month_idx'),
        ]

    def amount_paid(self):
        from decimal import Decimal
        return sum((r.amount_myr for r in self.receipts.all()), Decimal('0.00'))

    def balance(self):
        from decimal import Decimal
        return (Decimal(self.total_myr) - self.amount_paid()).quantize(Decimal('0.01'))

    def has_open_payment_declaration(self):
        """Has the tenant said it paid, with nobody having checked yet?

        Walks the PREFETCHED rows rather than filtering, so a page of invoices does not fire one
        query per row — the same reason `amount_paid` sums `self.receipts.all()`.
        """
        return any(d.confirmed_at is None and d.rejected_at is None
                   for d in self.payment_declarations.all())

    @property
    def status(self):
        if self.voided_at:
            return 'void'
        paid = self.amount_paid()
        # A fully discounted month (July: "100% discount, but show the values") owes nothing, but
        # calling it PAID would claim money arrived. It stays issued/sent with a zero balance.
        if self.total_myr > 0 and paid >= self.total_myr:
            return 'paid'
        if paid > 0:
            # ⚠ MONEY BEATS A CLAIM. A receipt exists, so the honest word is `part_paid` even if
            # the tenant has also declared the rest. The open declaration is still carried in the
            # payload as its own object, so the screen can show both — but the STATUS says what
            # the bank says, never what somebody told us about the bank.
            return 'part_paid'
        if self.sent_at and self.has_open_payment_declaration():
            # ⚠ NOT `paid`, and deliberately nowhere near it. Nothing has been verified: this is
            # the tenant's word, awaiting a look at the statement. See `payment_declarations`.
            return 'payment_declared'
        return 'sent' if self.sent_at else 'issued'

    def __str__(self):
        return f'{self.number} {self.organisation_id} {self.period_month} RM{self.total_myr}'


class InvoiceLine(models.Model):
    """One frozen line. Tenant-safe by construction: there is no cost or margin column to leak."""
    CATEGORY_CHOICES = [
        ('infrastructure', 'Platform infrastructure'),
        ('metered', 'Metered usage'),
        ('development', 'Development'),
    ]
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lines')
    # ⚠ A SUB-ITEM CARRIES DETAIL, NEVER MONEY. Owner, 2026-10-29: the individual requests belong
    # *under* a "Feature requests" line rather than beside the two cost lines. The parent holds the
    # group's hours, the billed rate and the whole group's amount; a child holds only its own
    # hours, and its `amount_myr` is always 0.00. That is deliberate, not a gap: a reader who adds
    # the Amount column with a calculator must reach the subtotal, and money at both levels would
    # make the column total twice. `build_lines` checks exactly that before an invoice can exist.
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE,
                               related_name='children')
    position = models.PositiveSmallIntegerField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(
        max_digits=8, decimal_places=1, null=True, blank=True,
        help_text='Hours, for development. Null for the two cost-share lines.')
    unit_amount_myr = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='The BILLED hourly rate (margin included), so quantity x unit = amount.')
    amount_myr = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = 'invoice_lines'
        ordering = ['invoice', 'position']


class InvoiceReceipt(models.Model):
    """Money that ARRIVED against an invoice — and only money that arrived.

    ⚠ **THE BANK REFERENCE IS REQUIRED.** A receipt is a statement that money changed hands. The
    project's standing rule for money is that nothing is recorded until it has actually moved and
    there is a reference to prove it; a receipt without one is a promise wearing a receipt's
    number. Overpayment is refused rather than stored as a credit nobody asked for.
    """
    METHOD_CHOICES = [
        ('bank_transfer', 'Bank transfer'),
        ('cheque', 'Cheque'),
        ('other', 'Other'),
    ]
    number = models.CharField(max_length=20, unique=True,
                              help_text="'RCP-YYYY-NNNN', numbered by the year received.")
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='receipts')
    received_on = models.DateField()
    amount_myr = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='bank_transfer')
    reference = models.CharField(max_length=120)
    note = models.TextField(blank=True, default='')
    recorded_by_email = models.EmailField(blank=True, default='')
    # ⚠ WHETHER THE CUSTOMER ACTUALLY GOT IT, recorded the same way the invoice records its own
    # send (2026-10-29). The owner asked whether a receipt is emailed; it was not, and a receipt
    # the customer has to come and fetch is a receipt they do not know exists. Blank means it was
    # never emailed — stated on the screen, never left to be assumed either way.
    emailed_at = models.DateTimeField(null=True, blank=True)
    # ⚠ NULL, not an empty list, and the pair says one thing: NULL on both means never emailed.
    # A `default=list` would also have forced the DDL renderer to open a real Postgres connection
    # to adapt the default for the backfill, which the offline render cannot do; readers go
    # through `list(... or [])` either way.
    emailed_to = models.JSONField(null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'invoice_receipts'
        ordering = ['invoice', 'received_on', 'id']

    def __str__(self):
        return f'{self.number} for {self.invoice_id}: RM{self.amount_myr}'


class InvoicePaymentDeclaration(models.Model):
    """The TENANT'S word that they have paid — a claim, not a receipt (2026-10-29).

    ⚠ **A DECLARATION IS NOT MONEY AND MUST NEVER MINT A RECEIPT.** The owner read BrightPath's
    own billing screen on 2026-10-29 and found no way for a customer to say "we have paid this".
    The gap is real, and the obvious fix is the dangerous one: letting the tenant's claim create a
    receipt would let the customer mark their own invoice paid. A receipt is still minted in
    exactly one place, by a super, after looking at the bank — `invoicing.record_receipt`. This
    row records who said what and when, so the owner has something to check against.

    ⚠ **NO AMOUNT, AND NO SLIP.** The owner's choice, 2026-10-29: *"Date and bank reference
    only."* The amount is not asked for because the invoice already states it and a tenant-typed
    figure would only invite a dispute about which number is right; the owner reads the real
    amount off the bank. No file is accepted either — a payment slip is a document to store,
    scan, serve and eventually purge, and the bank reference already identifies the transfer.

    One OPEN declaration at a time (the partial unique constraint). A tenant who declared and was
    told the money never arrived may declare again with the right reference.
    """
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE,
                                related_name='payment_declarations')
    paid_on = models.DateField(help_text='The date the tenant says the money left their account.')
    reference = models.CharField(
        max_length=120,
        help_text='The bank reference the tenant gives. Required — the whole point of the row is '
                  'to give the owner something to look up on the statement.')
    declared_at = models.DateTimeField(auto_now_add=True)
    declared_by_email = models.EmailField(blank=True, default='')
    # ── Settled one way or the other ────────────────────────────────────────
    # ⚠ Exactly one of these is set once the owner has looked. Both blank = still open, which is
    # what the derived `payment_declared` status reads.
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by_email = models.EmailField(blank=True, default='')
    receipt = models.ForeignKey(
        InvoiceReceipt, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='declarations',
        help_text='The receipt the owner raised on confirming. SET_NULL so a receipt that is '
                  'ever removed cannot delete the tenant\'s claim with it.')
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by_email = models.EmailField(blank=True, default='')
    reject_reason = models.TextField(
        blank=True, default='',
        help_text='Why the owner could not find it. Shown to the tenant — being told "not found" '
                  'with no reason is how a customer is left guessing at their own bank.')

    class Meta:
        db_table = 'invoice_payment_declarations'
        ordering = ['invoice', '-declared_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['invoice'],
                condition=models.Q(confirmed_at__isnull=True, rejected_at__isnull=True),
                name='invoice_one_open_payment_declaration'),
        ]
        indexes = [
            models.Index(fields=['invoice', 'declared_at'], name='invoice_decl_invoice_idx'),
        ]

    @property
    def is_open(self):
        return self.confirmed_at is None and self.rejected_at is None

    def __str__(self):
        state = 'open' if self.is_open else ('confirmed' if self.confirmed_at else 'rejected')
        return f'declaration for {self.invoice_id} on {self.paid_on} ({state})'


class OrgBillingCorrection(models.Model):
    """A fixed ringgit amount putting right an EARLIER month, carried onto a later invoice.

    ⚠ **THE OWNER'S RULE, 2026-10-29:** *"When we have overcharged or undercharged, this should be
    deducted or added (or written off) in the following month."* An invoice already sent is never
    rewritten — that is `Invoice`'s whole design — so a mistake travels forward as its own line
    with its own words, and the customer can read what happened.

    The first one is why this exists. August's INV-2026-0002 billed request 10 at its 15.0-hour
    QUOTE against 11.5 hours actually spent, and billed request 14 at 2.0 hours after its closing
    report told BrightPath *"none of it is charged"* — 5.5 hours at RM23.00, RM126.50 too much,
    on a document already in their inbox.

    ⚠ **SEPARATE FROM `OrgBillingAdjustment`, and the difference is grain AND meaning.** That one
    is a PERCENTAGE off one month, agreed in advance as a commercial term. This is a SIGNED
    AMOUNT fixing a named past invoice, decided afterwards because something was wrong. Folding
    them together would make a discount and an apology indistinguishable in the ledger — the same
    reasoning that kept a "not billed" boolean out of the discount model.

    ⚠ **SIGNED, and negative is the common case.** Negative reduces what the tenant owes (we
    over-charged); positive increases it (we under-charged). It is NOT stored as an absolute with
    a direction flag: two fields that must agree are two fields that can disagree.

    ⚠ It lives HERE, beside `Invoice`, rather than next to the discount in `billing.py` — it names
    an invoice and rides on one, and `billing.py` is four lines under the 600 standard.
    """
    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT,
        related_name='billing_corrections',
        help_text='The tenant whose bill is corrected. PROTECT, like the discount: a billing '
                  'decision must outlive any tidy-up of the organisation record.')
    period_month = models.CharField(
        max_length=7,
        help_text="The month whose invoice CARRIES this correction, 'YYYY-MM' — not the month "
                  'that was wrong. One live invoice per org per month already makes it apply '
                  'once; a re-issue after a void correctly applies it again.')
    amount_myr = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='SIGNED. Negative = the tenant owes less (we over-charged); positive = more. '
                  'Decimal, never float — this lands on an invoice.')
    reason = models.TextField(
        help_text='REQUIRED, and it is PRINTED ON THE TENANT\'S INVOICE. Name the month, the '
                  'requests and the arithmetic, so the line answers itself without anyone having '
                  'to ask us what it was for.')
    corrects_invoice = models.ForeignKey(
        Invoice, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='corrected_by',
        help_text='The invoice being put right, for provenance. SET_NULL so removing an invoice '
                  'can never delete the record that it was corrected.')
    set_by_email = models.EmailField(
        blank=True, default='',
        help_text='Who decided it. Moving money is a commercial act and needs a name.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'org_billing_corrections'
        ordering = ['-period_month', 'organisation', 'id']
        indexes = [
            models.Index(fields=['organisation', 'period_month'],
                         name='org_billing_corr_org_month_idx'),
        ]

    def __str__(self):
        return f'{self.period_month} {self.organisation_id}: {self.amount_myr:+}'
