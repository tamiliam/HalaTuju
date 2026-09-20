"""
What a student files: documents, referees, consents, onboarding answers.

Moved here VERBATIM from `apps/scholarship/models.py` at code health H15 (2026-09-20).
Moves only: no field, no `Meta`, no `db_table`, no `related_name` was touched, so the
database is untouched too — `makemigrations --check` reports no changes. See `__init__.py`.
"""
from django.db import models

from .applications import ScholarshipApplication

class ApplicantDocument(models.Model):
    """A supporting document for an application, stored in a private Supabase
    Storage bucket. Only the storage path + metadata live here; file bytes never
    pass through Django."""
    DOC_TYPES = [
        ('ic', 'Identity Card'),
        ('results_slip', 'Results Slip'),
        ('photo', 'Photo'),
        ('epf', 'EPF Statement'),
        ('str', 'STR Document'),
        ('statement_of_intent', 'Statement of Intent'),
        ('reference_letter', 'Reference Letter'),
        ('salary_slip', 'Salary Slip'),
        # Phase 2A (P5b/D1): supporting proof for a DECLARED informal income when the family
        # has no valid STR — flexible, any ONE of an employer/wage letter, bank statements
        # showing income, or a community/penghulu letter. Tagged to the household member.
        ('income_support_doc', 'Income Support Document'),
        ('water_bill', 'Water Bill'),
        ('electricity_bill', 'Electricity Bill'),
        ('offer_letter', 'Offer Letter'),
        # S17 — minor consent flow. parent_ic is compulsory when the applicant
        # is under 18; guardianship_letter is compulsory when the consenting
        # adult is NOT the father or mother (e.g. legal guardian, grandparent,
        # older sibling, other relative).
        ('parent_ic', 'Parent/Guardian IC'),
        ('guardianship_letter', 'Guardianship Letter'),
        # Income Check-1: links the income earner to the student when the earner is the
        # MOTHER (the student-IC patronymic only names the father). OCR: child/mother/father.
        ('birth_certificate', 'Birth Certificate'),
        # Post-award: the student's bank statement / passbook proving the account the
        # bursary will be paid into. Gemini-extracts bank name + account number +
        # account holder; the holder MUST be the student (hard rule).
        ('bank_statement', 'Bank Statement'),
        # V4 — Check-2 academic-completeness docs promoted out of the 'other' catch-all (officers
        # were hand-requesting both). A school-leaving certificate (surat berhenti sekolah /
        # testimonial) for a post-SPM applicant; a current-semester result slip (latest CGPA) for
        # a student ALREADY studying (continuing STPM / college) — the model had no pre-award
        # current-performance box (SemesterResult is post-award only). Gemini-extracted; soft.
        ('school_leaving_cert', 'School Leaving Certificate'),
        ('semester_result', 'Semester Result Slip'),
        # Catch-all for a reviewer-requested document not in the fixed list. Lands under "Other".
        ('other', 'Other Document'),
    ]
    VERIFICATION_CHOICES = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    # Income Check-1 salary route: which household member this document belongs to,
    # so one application can hold father's AND mother's AND a sibling's IC/payslip/EPF
    # without them overwriting each other. '' for everything outside the multi-earner
    # flow (single-instance docs, STR-route parent_ic, IC/results slip/etc.). The
    # (doc_type, household_member) pair is the single-instance key for income docs.
    HOUSEHOLD_MEMBER_CHOICES = [
        ('', 'Not applicable'),
        ('father', 'Father'), ('mother', 'Mother'), ('guardian', 'Legal guardian'),
        ('brother', 'Elder brother'), ('sister', 'Elder sister'),
    ]
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='documents',
    )
    doc_type = models.CharField(max_length=30, choices=DOC_TYPES)
    household_member = models.CharField(
        max_length=10, blank=True, default='', choices=HOUSEHOLD_MEMBER_CHOICES,
        help_text="Salary-route income docs only — whose IC/salary slip/EPF this is. "
                  "Blank for all other documents.")
    # The officer ResolutionItem code (e.g. 'officer_3') this document satisfies — set
    # ONLY for a reviewer-requested upload via the Action Centre. It makes each request
    # its own single-instance slot: the slot key becomes (doc_type, household_member,
    # request_code). So multiple 'other' docs (4 separate "upload X" requests) coexist
    # instead of overwriting each other, and a reviewer-requested cross-person income
    # doc (e.g. father's IC on a mother-STR route) gets its own slot instead of
    # clobbering the student's route doc. '' = the student's own apply-form/route doc
    # (shared slot — unchanged behaviour).
    request_code = models.CharField(max_length=20, blank=True, default='')
    storage_path = models.CharField(max_length=500)
    original_filename = models.CharField(max_length=255, blank=True, default='')
    content_type = models.CharField(max_length=100, blank=True, default='')
    size = models.IntegerField(default=0)
    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_CHOICES, default='pending',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    # ── S13: Vision OCR (soft signal, never a hard block) ──────────────────
    # Populated only for doc_type='ic'. The admin verify-&-accept stays the
    # real identity gate; these fields are hints (and a UX nudge for typos).
    vision_nric = models.CharField(max_length=20, blank=True, default='')
    vision_name = models.CharField(max_length=200, blank=True, default='')
    # S18 (post-S14): MyKad address from OCR. Surfaced to the admin verify-&-accept
    # card alongside profile.address — no automated matcher (admin/interviewer
    # eyeballs it). Useful when the registered IC address differs from where the
    # student currently lives (e.g. relocated since IC issue).
    vision_address = models.CharField(max_length=500, blank=True, default='')
    vision_run_at = models.DateTimeField(null=True, blank=True)
    vision_error = models.CharField(max_length=200, blank=True, default='')
    # Soft supporting-document checks: does the student's OR a parent/guardian's
    # name appear in the document text (results_slip / str / salary_slip / epf /
    # water_bill / electricity_bill / offer_letter), and — for utility bills — does
    # the home address appear? Computed at upload against names + address on file.
    # SOFT signal only (never blocks); surfaced to the student and the interviewer.
    # '' = not run / not applicable; else 'found' / 'not_found' / 'unreadable'.
    vision_name_match = models.CharField(max_length=12, blank=True, default='')
    vision_address_match = models.CharField(max_length=12, blank=True, default='')
    # Document-assist: Gemini-extracted structured fields (admin-on-... no — runs
    # automatically on upload for the weak-OCR supporting docs). Shape:
    # {fields: {...per doc_type}, warnings: [...], student_verdict: 'ok'|
    # 'name_mismatch'|'address_mismatch'|'wrong_doc'|'unreadable'|'review_manually',
    # error: ''}. Empty dict = not run. SOFT signal, never blocks. Surfaced to the
    # student (corrective nudge) + the admin (extracted values). Additive, 0-row-safe.
    vision_fields = models.JSONField(default=dict, blank=True)
    vision_fields_run_at = models.DateTimeField(null=True, blank=True)
    # ── Version history (Documents-box reorg Phase 2) ──────────────────────
    # A re-upload no longer HARD-deletes the old copy — it stamps the old row
    # `superseded_at` and points `superseded_by` at the replacement, keeping an
    # audit trail of what was replaced (shown under the officer "Old / Replaced"
    # sub-list). `superseded_at IS NULL` = the live row.
    # CRITICAL: every verdict / gate / completeness / student-facing read MUST
    # exclude superseded rows — funnel through `ApplicantDocument.live(qs)`
    # below. The default manager is DELIBERATELY unfiltered so the admin
    # serializer still returns superseded rows to show the history (a filtering
    # default manager would hide them from `application.documents`).
    superseded_at = models.DateTimeField(null=True, blank=True)
    superseded_by = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='supersedes',
    )

    class Meta:
        db_table = 'applicant_documents'
        ordering = ['-uploaded_at']

    @staticmethod
    def live(qs):
        """Filter a documents queryset (e.g. `application.documents`) to the
        live rows only. The single helper every verdict/gate read funnels
        through — `superseded_at IS NULL`."""
        return qs.filter(superseded_at__isnull=True)

    def __str__(self):
        return f'{self.doc_type} for application #{self.application_id}'


class Referee(models.Model):
    """A person who can vouch for the applicant (teacher, counsellor, referring
    org contact). The B40 analysis flagged the absence of a referee."""
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='referees',
    )
    name = models.CharField(max_length=200)
    role = models.CharField(
        max_length=200, blank=True, default='',
        help_text='e.g. teacher, school counsellor, referring org contact',
    )
    relationship = models.CharField(max_length=100, blank=True, default='')
    phone = models.CharField(max_length=30, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'referees'

    def __str__(self):
        return f'Referee {self.name} for application #{self.application_id}'


class Consent(models.Model):
    """A versioned, withdrawable consent record. For a minor (<18), consent must
    be granted by a guardian. Replaces the verbal consent the B40 analysis
    flagged as insufficient for PDPA."""
    GRANTED_BY = [('self', 'Self'), ('guardian', 'Guardian')]
    # S19 — relationship list refined: older_sibling split into brother/sister
    # (no "older" qualifier — the existing parent_ic_underage rule already
    # blocks anyone <18 from acting as guardian, so age is enforced upstream);
    # other_relative shortened to relative. 'Other' remains intentionally
    # excluded — unusual cases route through legal_guardian + letter.
    GUARDIAN_RELATIONSHIPS = [
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('legal_guardian', 'Legal guardian (court-appointed)'),
        ('grandparent', 'Grandparent'),
        ('brother', 'Brother'),
        ('sister', 'Sister'),
        ('relative', 'Relative'),
    ]
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='consents',
    )
    consent_type = models.CharField(max_length=50, default='share_with_sponsors')
    version = models.CharField(max_length=20)
    locale = models.CharField(max_length=2, default='en')
    granted_by = models.CharField(max_length=20, choices=GRANTED_BY, default='self')
    guardian_name = models.CharField(max_length=200, blank=True, default='')
    # S17: now a code from GUARDIAN_RELATIONSHIPS (no DB-level enum change — chars
    # work; the choices list is enforced at the serializer + admin level). Pre-S17
    # rows that hold free text are kept as-is; they just won't pass the new validator
    # if re-saved. Backfill ad-hoc as needed; no migration needed for that.
    guardian_relationship = models.CharField(max_length=100, blank=True, default='')
    # S19 — guardian's own NRIC (typed by them). Validated at consent submit
    # against the OCR'd NRIC from the uploaded parent_ic; mismatch is a hard
    # gate (not a soft anomaly flag). Stored in masked YYMMDD-PB-#### form
    # for legibility; comparisons strip non-digits.
    guardian_nric = models.CharField(max_length=20, blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'consents'
        ordering = ['-granted_at']

    def __str__(self):
        return f'Consent {self.consent_type} v{self.version} for application #{self.application_id}'


class OnboardingResponse(models.Model):
    """B40 Phase E/F (F8a): the student's post-award onboarding — the questionnaire
    answers + the acknowledgement consent. One row per application (re-submitting
    updates it). Kept as a dedicated row rather than a JSON blob on the application
    for a clean audit trail of what was answered and when. The matching
    ``student_onboarding_ack`` Consent is the legal record; this holds the content."""
    application = models.OneToOneField(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='onboarding_response',
    )
    # Free-form questionnaire payload (the F8b frontend defines the shape); JSON so
    # the questions can evolve without a migration. Never holds identity documents.
    answers = models.JSONField(default=dict, blank=True)
    consent = models.ForeignKey(
        Consent, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'onboarding_responses'

    def __str__(self):
        return f'OnboardingResponse for application #{self.application_id}'
