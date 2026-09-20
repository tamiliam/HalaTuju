"""
The bursary agreement and the contract templates, clauses and schedule behind it.

Moved here VERBATIM from `apps/scholarship/models.py` at code health H15 (2026-09-20).
Moves only: no field, no `Meta`, no `db_table`, no `related_name` was touched, so the
database is untouched too — `makemigrations --check` reports no changes. See `__init__.py`.
"""
from django.db import models

from .applications import ScholarshipApplication
from .funding import Sponsorship

class BursaryAgreement(models.Model):
    """The binding Conditional Bursary Award Agreement a student signs (with a
    parent/guardian as surety/guarantor) when they accept a sponsor's award.

    Parties: the STUDENT (primary), the PARENT/GUARDIAN (surety/guarantor), the
    FOUNDATION (counterparty — signatory from settings) and the PARTNER ORGANISATION
    (non-blocking witness). The DONOR is NEVER a party and is never named — anonymity
    is sacred, so there is no sponsor-name field here. The signed artefact is an
    immutable rendered HTML snapshot (+ its sha256) and a generated PDF in the private
    document bucket. v1: the parent co-signs in-session on the same device; the witness
    attestation is non-blocking. Behind BURSARY_AGREEMENT_ENABLED (default OFF)."""
    application = models.OneToOneField(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='bursary_agreement',
    )
    # The funded allocation this agreement binds (kept even if the sponsorship row is
    # later cleared — SET_NULL, never names the donor).
    sponsorship = models.ForeignKey(
        Sponsorship, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )
    version = models.CharField(max_length=20)
    locale = models.CharField(max_length=5, default='en')
    # Contract module: the versioned ContractTemplate this agreement was rendered from.
    # PROTECT — a deployed template that has governed a signed agreement can never be
    # deleted. Null for legacy agreements rendered from the hard-coded bursary.py
    # constants (pre-module); ``version`` above is filled from the template when present.
    template = models.ForeignKey(
        'ContractTemplate', null=True, blank=True,
        on_delete=models.PROTECT, related_name='agreements',
    )
    # Execution distribution (Sprint 5): the signed PDF is emailed to student + witness +
    # org admin and filed in Google Drive. Stamps guard idempotent best-effort delivery.
    executed_pdf_emailed_at = models.DateTimeField(null=True, blank=True)
    drive_file_url = models.URLField(blank=True, default='')

    # ── Particulars (the filled-in terms, frozen at signing) ──────────────────
    award_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_schedule = models.TextField(blank=True, default='')
    institution_name = models.CharField(max_length=255, blank=True, default='')
    course_name = models.CharField(max_length=255, blank=True, default='')
    commencement_date = models.DateField(null=True, blank=True)
    progress_standard = models.TextField(blank=True, default='')
    foundation_signatory_name = models.CharField(max_length=200, blank=True, default='')
    foundation_signatory_title = models.CharField(max_length=255, blank=True, default='')
    foundation_signatory_nric = models.CharField(max_length=20, blank=True, default='')

    # ── Student signature ─────────────────────────────────────────────────────
    student_signed_name = models.CharField(max_length=200, blank=True, default='')
    student_signed_nric = models.CharField(max_length=20, blank=True, default='')
    student_signed_at = models.DateTimeField(null=True, blank=True)
    student_ip = models.GenericIPAddressField(null=True, blank=True)

    # ── Guarantor (parent/guardian surety) signature ──────────────────────────
    guarantor_name = models.CharField(max_length=200, blank=True, default='')
    guarantor_nric = models.CharField(max_length=20, blank=True, default='')
    guarantor_relationship = models.CharField(max_length=50, blank=True, default='')
    guarantor_method = models.CharField(max_length=20, default='in_session')
    guarantor_signed_at = models.DateTimeField(null=True, blank=True)
    guarantor_ip = models.GenericIPAddressField(null=True, blank=True)

    # ── Foundation countersignature ───────────────────────────────────────────
    foundation_signed_by = models.CharField(max_length=200, blank=True, default='')
    foundation_signed_at = models.DateTimeField(null=True, blank=True)

    # ── Witness (partner/referring organisation; non-blocking) ────────────────
    witness_org = models.ForeignKey(
        'courses.PartnerOrganisation', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    witness_signed_by = models.CharField(max_length=200, blank=True, default='')
    witness_name = models.CharField(max_length=200, blank=True, default='')
    witness_signed_at = models.DateTimeField(null=True, blank=True)

    # ── Signing-chain reminder stamps (S6) — when the last nudge for a still-pending
    # signature went out, so the cron doesn't re-send daily (it waits the interval).
    witness_reminded_at = models.DateTimeField(null=True, blank=True)
    countersign_reminded_at = models.DateTimeField(null=True, blank=True)

    # ── Artefact (immutable snapshot) ─────────────────────────────────────────
    rendered_html = models.TextField(blank=True, default='')
    agreement_sha256 = models.CharField(max_length=64, blank=True, default='')
    pdf_storage_path = models.CharField(max_length=500, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bursary_agreements'
        ordering = ['-created_at']

    def __str__(self):
        return f'BursaryAgreement #{self.id} app={self.application_id} ({self.status})'

    @property
    def binds(self):
        """True once BOTH the student and the guarantor have signed — the point the
        contract is binding on the student side (the Foundation/witness follow)."""
        return bool(self.student_signed_at and self.guarantor_signed_at)

    @property
    def is_executed(self):
        """Fully executed: the student+guarantor bind it AND the Foundation has
        countersigned AND the witness has attested."""
        return bool(self.binds and self.foundation_signed_at and self.witness_signed_at)

    @property
    def status(self):
        """Derived lifecycle: draft → student_signed → binds → countersigned → executed."""
        if self.is_executed:
            return 'executed'
        if self.binds and self.foundation_signed_at:
            return 'countersigned'
        if self.binds:
            return 'binds'
        if self.student_signed_at:
            return 'student_signed'
        return 'draft'


# ─────────────────────────────────────────────────────────────────────────────
# Contract module (org-owned, versioned bursary agreement).
#
# Replaces the hard-coded bursary.py constants + the static FE quiz with an
# org-authored, versioned, deployable artifact. Lifecycle is DEPLOYMENT, not
# approval: draft → pending_deployment → active → archived. A non-draft template
# is IMMUTABLE (the contracts.py authoring calls refuse status != 'draft'), which
# is what lets a signed BursaryAgreement PROTECT-reference the exact version it
# was rendered from, forever. Module is INERT in Sprint 1 — nothing reads it yet.
# ─────────────────────────────────────────────────────────────────────────────
class ContractTemplate(models.Model):
    """A versioned bursary-agreement template owned by one organisation.

    English is authoritative (the lawyer vets English only); ms/ta are courtesy
    translations offered only when fully translated. Exactly one ACTIVE template
    per org at a time — deploying a new version atomically archives the previous
    active one (see ``contracts.deploy``)."""
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('pending_deployment', 'Pending deployment'),
        ('active', 'Active'),
        ('archived', 'Archived'),
    )
    PARENT_ROLE_CHOICES = (
        ('co_signer_all', 'Co-signer (all students)'),
        ('minor_only', 'Co-signer (minors only)'),
    )
    WITNESS_POLICY_CHOICES = (
        ('none', 'No witness'),
        ('optional', 'Witness optional'),
        ('required', 'Witness required'),
    )

    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT,
        related_name='contract_templates',
    )
    version = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Localised document chrome (en required; ms/ta blank until translated).
    title_en = models.CharField(max_length=255, blank=True, default='')
    title_ms = models.CharField(max_length=255, blank=True, default='')
    title_ta = models.CharField(max_length=255, blank=True, default='')
    preamble_en = models.TextField(blank=True, default='')
    preamble_ms = models.TextField(blank=True, default='')
    preamble_ta = models.TextField(blank=True, default='')
    progress_standard_en = models.TextField(blank=True, default='')
    progress_standard_ms = models.TextField(blank=True, default='')
    progress_standard_ta = models.TextField(blank=True, default='')

    # ── Flow config (party + signing rules) ───────────────────────────────────
    # NRIC is NEVER seeded/committed — the org admin fills it in the UI before deploy.
    counterparty_name = models.CharField(max_length=200, blank=True, default='')
    counterparty_title = models.CharField(max_length=255, blank=True, default='')
    counterparty_nric = models.CharField(max_length=20, blank=True, default='')
    # Free-text (multi-line) address — TextField so a long address can't overflow (cf. the
    # heading varchar(255) lesson). Pre-filled from the imported parties recital.
    counterparty_address = models.TextField(blank=True, default='')
    counterparty_notify_emails = models.JSONField(default=list, blank=True)
    parent_role = models.CharField(
        max_length=20, choices=PARENT_ROLE_CHOICES, default='co_signer_all',
    )
    parent_pin_required = models.BooleanField(default=True)
    witness_policy = models.CharField(
        max_length=10, choices=WITNESS_POLICY_CHOICES, default='optional',
    )

    # ── Attestation (the lawyer-vetting gate — T2) ────────────────────────────
    vetted_by_name = models.CharField(max_length=200, blank=True, default='')
    vetted_on = models.DateField(null=True, blank=True)
    vetting_attested_by_email = models.CharField(max_length=254, blank=True, default='')
    vetting_attested_at = models.DateTimeField(null=True, blank=True)

    # ── Lifecycle stamps ──────────────────────────────────────────────────────
    created_by_email = models.CharField(max_length=254, blank=True, default='')
    submitted_by_email = models.CharField(max_length=254, blank=True, default='')
    submitted_by_at = models.DateTimeField(null=True, blank=True)
    deployed_by_email = models.CharField(max_length=254, blank=True, default='')
    deployed_by_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'contract_templates'
        ordering = ['organisation_id', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['organisation', 'version'],
                name='uniq_contract_template_org_version',
            ),
        ]

    def __str__(self):
        return f'{self.organisation_id}/{self.version} ({self.status})'

    @property
    def languages_available(self):
        """en, plus each language whose title/preamble/progress AND every clause
        (heading+body) are fully translated. English is always available."""
        langs = ['en']
        for lang in ('ms', 'ta'):
            if not (getattr(self, f'title_{lang}') and getattr(self, f'preamble_{lang}')
                    and getattr(self, f'progress_standard_{lang}')):
                continue
            clauses = list(self.clauses.all())
            if clauses and all(
                getattr(c, f'heading_{lang}') and getattr(c, f'body_{lang}')
                for c in clauses
            ):
                langs.append(lang)
        return langs


class ContractClause(models.Model):
    """One numbered clause of a ContractTemplate. English is authoritative; bodies
    are PLAIN TEXT (a blank line is a paragraph break) — no rich text in v1, for
    xhtml2pdf safety. A clause may be flagged as a comprehension-quiz candidate,
    in which case it carries a per-language quiz payload."""
    template = models.ForeignKey(
        ContractTemplate, on_delete=models.CASCADE, related_name='clauses',
    )
    order = models.PositiveIntegerField()
    # Hierarchy depth (2026-07-19): 0 = clause (1., 2.), 1 = sub-clause (1.1), 2 = sub-sub-clause
    # (i), ii)). The flat `order` sequence + `level` encodes the tree; numbers are COMPUTED from the
    # (order, level) run (contracts.clause_numbers), never stored. A clause may only be one level
    # deeper than the one before it (no skipping). A comprehension quiz may sit on a clause (0) or
    # sub-clause (1) — never a sub-sub-clause (2) — and a clause + its own descendants are mutually
    # exclusive (contracts.MAX_QUIZ_LEVEL / _resolve_quiz_flags).
    level = models.PositiveSmallIntegerField(default=0)
    heading_en = models.CharField(max_length=255, blank=True, default='')
    heading_ms = models.CharField(max_length=255, blank=True, default='')
    heading_ta = models.CharField(max_length=255, blank=True, default='')
    body_en = models.TextField(blank=True, default='')
    body_ms = models.TextField(blank=True, default='')
    body_ta = models.TextField(blank=True, default='')

    is_quiz_candidate = models.BooleanField(default=False)
    # Each quiz payload: {tag, plain, question, options:[3 strings], correct:0-2, why}
    # (matches the FE QuizCheckpoint). Empty dict = no quiz for that language.
    quiz_en = models.JSONField(default=dict, blank=True)
    quiz_ms = models.JSONField(default=dict, blank=True)
    quiz_ta = models.JSONField(default=dict, blank=True)
    # Audit: which Gemini model drafted the quiz. Blank = hand-written/seeded.
    quiz_generated_model = models.CharField(max_length=80, blank=True, default='')

    class Meta:
        db_table = 'contract_clauses'
        ordering = ['template_id', 'order']
        constraints = [
            models.UniqueConstraint(
                fields=['template', 'order'],
                name='uniq_contract_clause_template_order',
            ),
        ]

    def __str__(self):
        return f'{self.template_id}#{self.order} {self.heading_en}'


class PaymentScheduleRow(models.Model):
    """One row of a template's versioned payment schedule. A student is governed by
    the schedule of the version they signed, forever. The total is DERIVED —
    ``len(paid_offsets) * monthly_amount`` — never stored, so it can never drift
    from the offsets. ``paid_offsets`` are sorted 0-based month offsets from
    ``start_month`` and encode start, count, and gap/exam months in one field."""
    template = models.ForeignKey(
        ContractTemplate, on_delete=models.CASCADE, related_name='schedule_rows',
    )
    pathway = models.CharField(max_length=40)
    # '' = the plain pathway row; 'continuing' = the continuing-student variant.
    variant = models.CharField(max_length=20, blank=True, default='')
    label_en = models.CharField(max_length=120, blank=True, default='')
    label_ms = models.CharField(max_length=120, blank=True, default='')
    label_ta = models.CharField(max_length=120, blank=True, default='')
    monthly_amount = models.DecimalField(max_digits=10, decimal_places=2)
    start_month = models.PositiveSmallIntegerField()  # 1-12
    paid_offsets = models.JSONField(default=list, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'contract_payment_schedule_rows'
        ordering = ['template_id', 'sort_order', 'pathway', 'variant']
        constraints = [
            models.UniqueConstraint(
                fields=['template', 'pathway', 'variant'],
                name='uniq_contract_schedule_template_pathway_variant',
            ),
        ]

    def __str__(self):
        return f'{self.template_id} {self.pathway}/{self.variant or "-"}'

    @property
    def total(self):
        from decimal import Decimal
        return (self.monthly_amount or Decimal('0')) * len(self.paid_offsets or [])
