"""
What the platform costs and what a tenant is charged for it.

Moved here VERBATIM from `apps/scholarship/models.py` at code health H15 (2026-09-20).
Moves only: no field, no `Meta`, no `db_table`, no `related_name` was touched, so the
database is untouched too — `makemigrations --check` reports no changes. See `__init__.py`.
"""
from django.db import models

from .applications import ScholarshipApplication

class UsageEvent(models.Model):
    """Per-tenant usage meter (Billing & usage v1 — Sprint 13a).

    ONE row per billable provider call at a sanctioned seam (Gemini / Cloud Vision /
    OpenAI / Brevo email / Twilio WhatsApp). Written UNCONDITIONALLY from deploy, ABSOLUTELY
    best-effort (see ``apps.scholarship.usage.record_usage`` — a metering failure can never
    break the user-facing call). Read only by the super/org_admin usage screen. Units and
    token counts ONLY — v1 carries NO prices (there is no price table yet).

    ``organisation`` is NULL for platform-base work (course-selector reports, ops mail) — the
    tenancy attribution kept for reconciliation, per the billing-sources investigation.
    """
    SERVICE_CHOICES = [
        ('gemini', 'Gemini'),
        ('vision_ocr', 'Cloud Vision OCR'),
        ('openai', 'OpenAI'),
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
    ]

    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT, null=True, blank=True,
        related_name='usage_events',
        help_text='The tenant this billable call is attributed to. NULL = platform-base '
                  'work (course-selector reports, ops mail), kept for reconciliation.')
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='usage_events',
        help_text='The application in hand when known (SET_NULL so purging a case never '
                  'deletes its billing history).')
    service = models.CharField(max_length=20, choices=SERVICE_CHOICES)
    model = models.CharField(max_length=80, blank=True, default='',
                             help_text='The provider model name (AI only), e.g. gemini-2.5-flash.')
    source = models.CharField(max_length=40, blank=True, default='',
                              help_text='The call-path tag, e.g. doc_extract, ic_fallback, '
                                        'profile_draft, report, or an email/whatsapp function tag.')
    quantity = models.IntegerField(default=1)
    input_tokens = models.IntegerField(null=True, blank=True,
                                       help_text='Prompt token count (AI only), from the '
                                                 "provider response's usage metadata.")
    output_tokens = models.IntegerField(null=True, blank=True,
                                        help_text='Completion token count (AI only).')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'usage_events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organisation', 'created_at'], name='usage_org_created_idx'),
        ]

    def __str__(self):
        who = self.organisation_id or 'platform'
        return f'{self.service}:{self.source or "-"} org={who} @ {self.created_at:%Y-%m-%d}'


class PlatformCost(models.Model):
    """What the PLATFORM actually cost, per month, per SKU — the cost side of billing.

    Deliberately a SEPARATE ledger from ``UsageEvent``, because the two answer different
    questions and are true at different grains:

      * ``UsageEvent``  — "what did this ORGANISATION consume?"  per event, per tenant.
      * ``PlatformCost`` — "what did the PLATFORM cost?"          per month, per SKU.

    Measured 2026-07-26 against the June invoice: the meter accounts for ~RM20 of an RM88
    bill. The rest is infrastructure whose driver is our own cron schedule and deploy pace,
    not tenant activity. Metering it per-org would invent precision that does not exist, so
    this ledger records the INVOICE and marks each line attributable or not, rather than
    smearing untraceable cost across tenants.

    **Every row is an invoice fact, never an estimate.** ``provenance`` is what enforces that:
    a hand-typed Supabase figure must never be indistinguishable from a measured GCP one.
    (Lesson: "before importing a spreadsheet as payment history, confirm the money moved".)

    **Scope is the HalaTuju GCP project only.** The billing export covers the whole billing
    account; other products live under it (Lentera cost RM0.30 in June). The owner's ruling
    (2026-07-26) is that HalaTuju carries ~99.7% of GCP and 100% of Supabase — verified against
    the June bill — but the sync still FILTERS by project, because the filter is what keeps
    that ruling true if a sibling product ever grows.
    """
    SOURCE_CHOICES = [
        ('gcp', 'Google Cloud Platform'),
        ('supabase', 'Supabase'),
        # 2026-09-11. Its OWN source, not `other`. Google Workspace is a standing monthly line
        # (the halatuju.xyz mailboxes) and it will be on every invoice from here on. Left in
        # `other` it becomes indistinguishable from every future one-off, and the by-source
        # breakdown — the whole reason the column exists — stops answering "what is this?".
        ('workspace', 'Google Workspace'),
        ('brevo', 'Brevo'),
        ('twilio', 'Twilio'),
        # 2026-09-11, owner: *"My biggest cost is Claude, which needs to be included via the
        # request hours."* It is a cost of DELIVERING DEVELOPMENT HOURS, not of running the
        # platform, so `platform_cost.cost_bucket` files it under development and it never
        # reaches the infrastructure charge — recovering it twice would be the obvious mistake.
        ('anthropic', 'Anthropic (Claude)'),
        # `OPENAI_API_KEY` is set on the live service as the counsellor report's second
        # provider. The AI registry says it has never fired, so there is no bill yet — but it
        # bills OUTSIDE Google Cloud, so without a source here the first time it does fire the
        # cost would land nowhere at all.
        ('openai', 'OpenAI'),
        # ⚠ FREE TODAY, LISTED ANYWAY (owner, 2026-09-11). Cloudflare (Turnstile), Brevo above,
        # and GitHub (the repositories and every CI minute) all cost nothing on their current
        # plans. They are named here and in the page's free-services footnote because a
        # dependency nobody has written down is one nobody re-prices when its free tier ends —
        # and the ledger should have somewhere to put the first bill other than `other`.
        ('cloudflare', 'Cloudflare'),
        ('github', 'GitHub'),
        ('other', 'Other'),
    ]
    # How this row came to exist. The distinction is load-bearing: only MEASURED rows can be
    # re-derived and re-checked; an ENTERED row is somebody's reading of a PDF and carries
    # human error. A reconciliation that mixes them without saying so is not an audit.
    PROVENANCE_CHOICES = [
        ('measured', 'Measured — pulled from the provider\'s own billing data'),
        # 2026-09-11. Owner ruling: *"Don't use typed by hand. Everything should be extracted
        # from the relevant systems."* So a third state, and it is genuinely a third state
        # rather than a rename of `entered`.
        #
        # `extracted` is REPRODUCIBLE: the provider's own PDF is the input, a deterministic
        # parser is the method, and anybody holding the file gets the identical figure — and
        # the parser refuses outright unless its lines reconcile to the total printed on the
        # invoice. What separates it from `measured` is only that a layout change can break it,
        # where a billing API cannot. What separates it from `entered` is everything: an entered
        # row is one person's reading, checkable by nobody.
        ('extracted', "Extracted — parsed from the provider's own invoice, reconciled to its "
                      'printed total'),
        ('entered', 'Entered by hand from an invoice'),
    ]

    period_month = models.CharField(
        max_length=7,
        help_text="Billing month as 'YYYY-MM'. The grain of an invoice, not of an event.")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    service = models.CharField(
        max_length=120, blank=True, default='',
        help_text="Provider service, e.g. 'Cloud Run', 'Artifact Registry'.")
    sku = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Provider SKU — the grain that actually explains a bill. Reading June by "
                  "SKU is what revealed Cloud Run JOBS (RM33) outranked Artifact Registry.")
    # ── The money, in three parts ────────────────────────────────────────────
    # A first cut carried only `amount_myr`, which quietly assumed every provider invoices in
    # ringgit. GCP does; **Supabase invoices in USD** ($25.00/month). Converting needs a rate,
    # and a rate typed from memory is exactly the "estimate dressed as a fact" this ledger
    # exists to prevent — so the invoice is recorded in ITS OWN currency, and the conversion is
    # a separate, visible, auditable step.
    currency = models.CharField(
        max_length=3, default='MYR',
        help_text='ISO code the invoice is denominated in. GCP = MYR, Supabase = USD.')
    amount_original = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='The figure printed on the invoice, in `currency`. Null for MYR invoices '
                  'where amount_myr IS the invoiced figure.')
    fx_rate = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        help_text='Rate used to derive amount_myr from amount_original. Prefer the rate your '
                  'card was actually charged at — that is the real cost — over a spot rate.')
    amount_myr = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Cost in MYR — the common denominator every total is summed in. Decimal, '
                  'never float: this is money. **Nullable on purpose.** "We hold the invoice '
                  'but do not yet know what it cost us in ringgit" is a real and honest state; '
                  'a placeholder number in a money column gets quoted as if it were true. '
                  'Rows left null are counted and reported as incomplete, never silently '
                  'dropped from a total.')
    period_note = models.CharField(
        max_length=120, blank=True, default='',
        help_text='Set when the provider\'s billing period does not match the calendar month '
                  "— e.g. Supabase invoices on the 8th, so a period straddles two months. "
                  'Without this, a cross-provider reconciliation compares unlike periods.')
    attributable = models.BooleanField(
        default=False,
        help_text='True when this line moves with TENANT activity (per-document OCR, AI, '
                  'egress). False for platform-driven cost (cron compute, CI storage) — that '
                  'belongs in a platform fee, not a metered charge.')
    provenance = models.CharField(max_length=10, choices=PROVENANCE_CHOICES)
    invoice_ref = models.CharField(
        max_length=60, blank=True, default='',
        help_text="The provider's own invoice number (e.g. 'TPTHYS-00007'). Its own column, "
                  'not buried in a note: it is how a figure is traced back to the document it '
                  'came from, which is the whole point of an auditable ledger.')
    note = models.TextField(
        blank=True, default='',
        help_text='Anything a future reader needs in order to trust the figure — what was '
                  'excluded, an attribution caveat, why a rate was chosen.')
    recorded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'platform_costs'
        ordering = ['-period_month', 'source', '-amount_myr']
        constraints = [
            # One row per (month, source, service, sku) — makes the sync an idempotent UPSERT
            # rather than an append, so re-running a month corrects it instead of doubling it.
            models.UniqueConstraint(
                fields=['period_month', 'source', 'service', 'sku'],
                name='platform_cost_unique_line'),
        ]
        indexes = [
            models.Index(fields=['period_month', 'source'], name='platform_cost_month_idx'),
        ]

    def __str__(self):
        return f'{self.period_month} {self.source}/{self.sku or self.service}: RM{self.amount_myr}'


class BillingRate(models.Model):
    """PLATFORM-side, super-only: the editable numbers that turn cost + effort into a charge.

    Owner design (2026-07-27): hours are recorded on the ORG side; the conversion rate and the
    per-category margins live here, on the platform side, as editable values. One home, so a
    rate cannot drift between the screen that shows it and the code that bills on it.

    **Effective-dated, deliberately.** A rate is not a setting, it is a term — and a term has a
    date. Storing a single mutable number would mean editing the hourly rate in September
    silently re-prices August's invoice, which is the kind of quiet retroactive change that
    destroys trust in a bill. `rate_in_force()` therefore always asks "what was true on THAT
    day?", never "what is true now?".

    **There is no default and no fallback.** If no rate is in force, the charge calculation
    REFUSES rather than returning zero or a guess. An unbilled month is a visible problem
    somebody fixes; a month billed at an invented rate is an invoice you have to withdraw.
    """
    CATEGORY_INFRASTRUCTURE = 'infrastructure'   # what we pay Google/Supabase to keep it running
    CATEGORY_METERED = 'metered'                 # per-event usage the tenant actually drives
    CATEGORY_DEVELOPMENT = 'development'         # building the tenant's modules
    CATEGORY_CHOICES = [
        (CATEGORY_INFRASTRUCTURE, 'Infrastructure (platform fee)'),
        (CATEGORY_METERED, 'Metered usage'),
        (CATEGORY_DEVELOPMENT, 'Development hours'),
    ]

    KIND_MARGIN_PCT = 'margin_pct'
    KIND_HOURLY_RATE = 'hourly_rate'
    KIND_CHOICES = [
        (KIND_MARGIN_PCT, 'Margin (%) added to the category'),
        (KIND_HOURLY_RATE, 'Hourly rate (RM per hour)'),
    ]

    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    value = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Percent for margin_pct (15 = +15%), RM/hour for hourly_rate. Decimal, '
                  'never float — this ends up on an invoice.')
    effective_from = models.DateField(
        help_text='The day this value takes effect. A month is billed on the value in force '
                  'during that month, so changing a rate never re-prices a closed month.')
    updated_by_email = models.EmailField(
        blank=True, default='',
        help_text='Who set it. A rate change is a commercial act and should have a name on it.')
    note = models.TextField(
        blank=True, default='',
        help_text='Why this value. A future reader asking "why 15%?" deserves an answer here '
                  'rather than in somebody\'s memory.')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'billing_rates'
        ordering = ['category', 'kind', '-effective_from']
        constraints = [
            # One value per (category, kind) per start date — a new value is a NEW ROW with a
            # later date, never an edit of the old one. The history is the audit trail.
            models.UniqueConstraint(
                fields=['category', 'kind', 'effective_from'],
                name='billing_rate_unique_effective'),
        ]

    def __str__(self):
        unit = '%' if self.kind == self.KIND_MARGIN_PCT else ' RM/h'
        return f'{self.category}.{self.kind} = {self.value}{unit} from {self.effective_from}'


class OrgBuildHours(models.Model):
    """ORG-side: hours spent building THIS organisation's modules, in a given month.

    Owner requirement (2026-07-27): the billing must include the hours spent building the
    tenant's modules. This is the record of those hours — deliberately separate from
    `PlatformCost`, which holds money we PAY OUT. Hours are money we CHARGE. Summing the two
    in one table would make every total meaningless.

    **`basis` is required and is the point of the model.** No time-tracking system has ever
    existed here, so every hours figure is somebody's reconstruction — from working days, from
    a sprint count, from memory. That is legitimate input, but only if the reconstruction
    travels with the number. "70 working days at 4h" is auditable; "280" is not.
    """
    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT,
        related_name='build_hours',
        help_text='The tenant whose modules were built. PROTECT: billing history must outlive '
                  'any tidy-up of the organisation record.')
    period_month = models.CharField(max_length=7, help_text="'YYYY-MM' the work is billed in.")
    module = models.CharField(
        max_length=200,
        help_text="What was built, in the owner's words — e.g. 'Payments module', "
                  "'Programme layer P1a-P4b'. This is what the tenant reads on the invoice.")
    hours = models.DecimalField(
        max_digits=8, decimal_places=1,
        help_text='Hours spent. One decimal place: nobody can honestly reconstruct minutes.')
    basis = models.TextField(
        help_text='REQUIRED. How this figure was arrived at — the working-day count, the '
                  'sprint span, whatever it was. There is no time tracker, so the number is a '
                  'reconstruction and is only trustworthy if it says so.')
    recorded_by_email = models.EmailField(blank=True, default='')
    recorded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'org_build_hours'
        ordering = ['-period_month', 'organisation']
        indexes = [
            models.Index(fields=['organisation', 'period_month'], name='build_hours_org_idx'),
        ]

    def __str__(self):
        return f'{self.period_month} {self.organisation_id}: {self.hours}h {self.module}'


class OrgBillingAdjustment(models.Model):
    """A discount applied to ONE organisation's bill for ONE month.

    Owner requirement 2026-09-11: *"we do not bill anything for July. 100% discount. But show
    the values."* Those two sentences are the whole design. July is computed in full, every
    line visible, and THEN reduced to zero by a row that says so — subtotal, discount, charged.

    ⚠ **A boolean "not billed" flag was rejected.** It loses why, loses who, and above all makes
    a deliberate waiver indistinguishable from a bug that happened to produce zero. Six months
    later nobody can tell the difference, and the only way to find out is to re-derive the month
    — which is exactly the work an audit trail exists to avoid.

    **Separate from `BillingRate`, and the difference is the grain.** A rate is platform-wide
    and effective-DATED: it applies to everyone from a day onward. A discount is a commercial
    term agreed with ONE tenant for ONE named month. Storing it as an effective-dated rate would
    mean a July waiver silently continued into August until somebody remembered to end it.

    `reason` is required, for the same purpose `OrgBuildHours.basis` serves: a number nobody can
    explain later is not auditable. "Pre-launch goodwill period" is a term; "0" is a mystery.
    """
    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT,
        related_name='billing_adjustments',
        help_text='The tenant whose bill is reduced. PROTECT: a billing decision must outlive '
                  'any tidy-up of the organisation record.')
    period_month = models.CharField(
        max_length=7,
        help_text="The single month this applies to, 'YYYY-MM'. Never a range: a waiver that "
                  'rolls forward on its own is how an unbilled year happens.')
    discount_pct = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text='Percent off the computed charge. 100 = the month is shown in full and '
                  'charged nothing. Decimal, never float — this lands on an invoice.')
    reason = models.TextField(
        help_text='REQUIRED. Why this month was discounted, in words a stranger reading the '
                  'ledger next year can act on.')
    set_by_email = models.EmailField(
        blank=True, default='',
        help_text='Who decided it. Waiving a charge is a commercial act and needs a name.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'org_billing_adjustments'
        ordering = ['-period_month', 'organisation']
        constraints = [
            # One adjustment per (org, month). Two rows would mean two answers to "what was
            # charged?", and the code would have to pick one — silently.
            models.UniqueConstraint(
                fields=['organisation', 'period_month'],
                name='org_billing_adjustment_unique_month'),
        ]

    def __str__(self):
        return f'{self.period_month} {self.organisation_id}: -{self.discount_pct}%'


# ── Tenant invoices and receipts (2026-09-14) ─────────────────────────────────
# The billing screen computed a charge and ISSUED nothing: `charge_for` re-ran on every page load,
# so a rate edit or a late ledger row silently rewrote a month somebody had already been told
# about. These models are the other half — a bill that, once issued, never changes.
#
# Owner rulings, 2026-09-14: issued on the 15th FOR THE PREVIOUS MONTH (suppliers bill late —
# Supabase runs 8th-to-8th — so the 15th is when a month's cost is actually known); and HELD, not
# sent — a super presses Send, and a tenant sees nothing until then.

class InvoiceIssuer(models.Model):
    """WHO is billing — the one block every invoice and receipt prints at the top. One row.

    ⚠ **DELIBERATELY EMPTY UNTIL THE OWNER FILLS IT IN.** HalaTuju has no registered legal entity
    yet (it is run in a personal capacity; the entity decision is open). An invoice naming an
    invented company, or a bank account typed from memory, is worse than no invoice. So there is
    no seed row and no default, and `invoicing.readiness` refuses to issue anything while the
    required fields are blank — the same "refuse, never guess" rule `BillingRate` follows.

    Printed onto each invoice as a SNAPSHOT at issue time (`Invoice.issuer_snapshot`), so changing
    the bank account in March never rewrites the account printed on January's invoice.
    """
    #: What must be present before anything is issued. `registration_no` and `phone` are absent
    #: on purpose: an unregistered issuer is a real state today, and refusing on it would block
    #: billing on a decision that is not the platform's to make.
    REQUIRED = ('legal_name', 'address', 'email', 'bank_name', 'bank_account_name',
                'bank_account_no')

    legal_name = models.CharField(max_length=200, blank=True, default='')
    registration_no = models.CharField(
        max_length=60, blank=True, default='',
        help_text='Company or society registration number, when one exists. Printed if set.')
    address = models.TextField(blank=True, default='')
    email = models.EmailField(blank=True, default='',
                              help_text='Printed on the invoice and used as the reply-to on Send.')
    phone = models.CharField(max_length=30, blank=True, default='')
    bank_name = models.CharField(max_length=120, blank=True, default='')
    bank_account_name = models.CharField(max_length=200, blank=True, default='')
    bank_account_no = models.CharField(max_length=40, blank=True, default='')
    payment_terms_days = models.PositiveSmallIntegerField(
        default=30,
        help_text='Days from the issue date to the due date. Snapshotted: changing it never moves '
                  'the due date of an invoice already issued.')
    updated_by_email = models.EmailField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'invoice_issuer'

    def missing(self):
        """The required fields still blank, in form order. Empty list = ready to issue."""
        return [f for f in self.REQUIRED if not (getattr(self, f, '') or '').strip()]

    def snapshot(self):
        return {f: getattr(self, f) for f in (
            'legal_name', 'registration_no', 'address', 'email', 'phone',
            'bank_name', 'bank_account_name', 'bank_account_no')}

    def __str__(self):
        return self.legal_name or '(issuer not set)'


class OrgBillingDetails(models.Model):
    """WHO is being billed — one row per tenant: the name, address and inboxes an invoice goes to.

    Separate from `PartnerOrganisation` because that table is dual-role (ten rows on production,
    one tenant) and lives in another app; a billing address has no meaning for a referral school.
    Snapshotted onto each invoice at issue time for the same reason as the issuer.
    """
    organisation = models.OneToOneField(
        'courses.PartnerOrganisation', on_delete=models.PROTECT,
        related_name='billing_details')
    bill_to_name = models.CharField(
        max_length=200, blank=True, default='',
        help_text='The name printed under "Bill to" — the legal name, which may differ from the '
                  'display name the platform uses.')
    address = models.TextField(blank=True, default='')
    emails = models.JSONField(
        default=list, blank=True,
        help_text='Where Send delivers the invoice. A list: finance inboxes are often two people.')
    updated_by_email = models.EmailField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'org_billing_details'

    def clean_emails(self):
        return [e for e in (str(x).strip() for x in (self.emails or [])) if e]

    def missing(self):
        out = []
        if not (self.bill_to_name or '').strip():
            out.append('bill_to_name')
        if not (self.address or '').strip():
            out.append('address')
        if not self.clean_emails():
            out.append('emails')
        return out

    def snapshot(self):
        return {'bill_to_name': self.bill_to_name, 'address': self.address,
                'emails': self.clean_emails()}

    def __str__(self):
        return f'{self.organisation_id}: {self.bill_to_name}'


class OrganisationOverviewLayout(models.Model):
    """Which Overview widgets an organisation shows, and in what order (phase 2, 2026-09-18).

    One row per organisation; `sections` is the ORDERED list `[{key, on}]` over exactly the five
    customisable widgets (`overview_layout.CUSTOMISABLE`). No row means the default: every widget
    on, default order. Set by the org admin from the Overview's Customise mode; read by
    `programme_overview.build` for every role in the organisation — as a NARROWING of what the
    role may see, never a widening (see `overview_layout.apply`).

    ⚠ THE FENCE IS ON THE MODEL. `save()` validates through `overview_layout.validate_sections`,
    the `OrganisationConfiguration.save()` seam: a shell caller cannot store an unknown key, a
    duplicate, or a list with a widget missing.
    """
    organisation = models.OneToOneField(
        'courses.PartnerOrganisation', on_delete=models.CASCADE,
        related_name='overview_layout')
    sections = models.JSONField(
        default=list,
        help_text='Ordered list of {key, on} over the five customisable Overview widgets.')
    updated_by_email = models.CharField(max_length=254, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organisation_overview_layouts'

    def __str__(self):
        return f'Overview layout for {self.organisation.code}'

    def save(self, *args, **kwargs):
        from .. import overview_layout
        self.sections = overview_layout.normalised(self.sections)
        return super().save(*args, **kwargs)


class BillingSequence(models.Model):
    """The last number used, per document kind per year — what makes numbering GAP-FREE.

    `max(number) + 1` is not gap-free under concurrency and it is not safe after a void either,
    because a voided number must stay used for ever. A counter row locked with
    `select_for_update` inside the issuing transaction is: a rolled-back issue rolls the counter
    back with it, so a failed attempt never burns a number.
    """
    KIND_INVOICE = 'INV'
    KIND_RECEIPT = 'RCP'
    kind = models.CharField(max_length=3)
    year = models.PositiveSmallIntegerField()
    last = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'billing_sequences'
        constraints = [
            models.UniqueConstraint(fields=['kind', 'year'], name='billing_sequence_unique'),
        ]
