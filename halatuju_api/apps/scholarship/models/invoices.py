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
            return 'part_paid'
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'invoice_receipts'
        ordering = ['invoice', 'received_on', 'id']

    def __str__(self):
        return f'{self.number} for {self.invoice_id}: RM{self.amount_myr}'
