"""
Reviewing a case: resolution items, reviewers, assignments, results, referrals.

Moved here VERBATIM from `apps/scholarship/models.py` at code health H15 (2026-09-20).
Moves only: no field, no `Meta`, no `db_table`, no `related_name` was touched, so the
database is untouched too — `makemigrations --check` reports no changes. See `__init__.py`.
"""
from django.db import models

from .applications import ScholarshipApplication
from .documents import ApplicantDocument
from .sponsors import Sponsor

class ResolutionItem(models.Model):
    """A discrete, independently-resolvable action raised against an application
    (the IBKR model — see docs/scholarship/verification-verdict-plan.md, S3).

    Most items are GENERATED from the verification verdict's ``unresolved`` list
    (``verdict_engine.build_verdict``) by ``resolution.sync_resolution_items`` —
    one ``source='system'`` item per (application, code), created once and
    auto-resolved when the underlying gap clears. An officer may also raise a
    ``source='officer'`` item by hand (the structured successor to the freeform
    ``info_request_note``). Each item closes by a **document**, a typed
    **explanation**, or a one-tap **confirm** — so the student clears the queue
    self-service and a phone call stays the exception.
    """
    KIND = [
        ('doc', 'Upload a document'),
        ('confirm', 'Confirm / correct a value'),
        ('explanation', 'Explain in your own words'),
        # Check 2 STEP 2:
        ('clarify', 'Answer a question'),          # AI student query (one-line, non-sensitive)
        ('human', 'For the reviewer'),             # AI-triaged to the human; never shown to the student
    ]
    STATUS = [
        ('open', 'Open'),
        ('resolved', 'Resolved'),
        ('waived', 'Waived'),     # officer decided it isn't needed
    ]
    # 'check2' = an AI clarify/human query raised by the Check-2 submission review;
    # kept OUT of the verdict-driven sync (which only reconciles source='system').
    SOURCE = [('system', 'System'), ('officer', 'Officer'), ('check2', 'Check 2')]

    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='resolution_items',
    )
    # The verdict fact this item belongs to (identity/academic/income/pathway),
    # or 'other' for an officer-raised item that isn't tied to a fact.
    fact = models.CharField(max_length=20, default='other')
    # The verdict item code (e.g. 'income_proof_missing') or, for officer items,
    # a synthetic 'officer_<n>'. Drives the i18n copy + the resolution UI (S4).
    code = models.CharField(max_length=60)
    # The verdict item's params, frozen for display (so the queue reads the same
    # even if the underlying data later changes).
    params = models.JSONField(default=dict, blank=True)
    prompt = models.TextField(
        blank=True, default='',
        help_text='Officer-written ask (officer items); system items resolve copy from code via i18n.',
    )
    kind = models.CharField(max_length=20, choices=KIND, default='doc')
    # For kind='doc': which ApplicantDocument.doc_type the student should upload.
    doc_type = models.CharField(max_length=30, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS, default='open')
    source = models.CharField(max_length=20, choices=SOURCE, default='system')
    # The student's response: a typed explanation/confirmation, and/or the
    # document they uploaded to satisfy a 'doc' item.
    resolution_text = models.TextField(blank=True, default='')
    resolution_doc = models.ForeignKey(
        ApplicantDocument, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resolves_items',
    )
    created_by = models.CharField(
        max_length=254, blank=True, default='',
        help_text="Email of the PartnerAdmin for officer items; '' for system items.",
    )
    resolved_by = models.CharField(
        max_length=254, blank=True, default='',
        help_text="'student' / 'system' / a PartnerAdmin email.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'resolution_items'
        ordering = ['-created_at']
        constraints = [
            # One SYSTEM item per (application, code), ever — generation is
            # idempotent and never re-nags. Officer items aren't constrained.
            models.UniqueConstraint(
                fields=['application', 'code'], condition=models.Q(source='system'),
                name='uniq_system_resolution_per_code'),
            # Same idempotence for Check-2 AI queries: one per (application, code), ever.
            models.UniqueConstraint(
                fields=['application', 'code'], condition=models.Q(source='check2'),
                name='uniq_check2_resolution_per_code'),
        ]

    def __str__(self):
        return f'ResolutionItem #{self.id} app={self.application_id} {self.code} ({self.status})'


class ReviewerProfile(models.Model):
    """A reviewer's own credentials + contact details (F6, Phase E/F Sprint 5).

    OneToOne to courses.PartnerAdmin (a cross-app FK, like the rest of this app's
    references to the courses domain). Lives here, not on PartnerAdmin, so the
    sensitive staff PII (phone/address) sits in its own table with its own RLS and
    is edited only via the self-scoped /admin/reviewer-profile/ endpoint — it can
    never reach the student/sponsor allowlist serializers. NO password field
    (authentication is Supabase's; passwords are never modelled).
    """
    partner_admin = models.OneToOneField(
        'courses.PartnerAdmin', on_delete=models.CASCADE,
        related_name='reviewer_profile',
    )
    highest_qualification = models.CharField(max_length=120, blank=True, default='')
    university = models.CharField(max_length=200, blank=True, default='')
    graduation_year = models.PositiveSmallIntegerField(null=True, blank=True)
    field_of_study = models.CharField(max_length=200, blank=True, default='')
    # Language fluency — used to match a reviewer to a student's preferred call language
    # (StudentProfile.preferred_call_language). 'conversational' or 'fluent' = can review in it.
    LANG_FLUENCY = [('', 'None'), ('conversational', 'Conversational'), ('fluent', 'Fluent')]
    english_fluency = models.CharField(max_length=20, blank=True, default='', choices=LANG_FLUENCY)
    bm_fluency = models.CharField(max_length=20, blank=True, default='', choices=LANG_FLUENCY)
    tamil_fluency = models.CharField(max_length=20, blank=True, default='', choices=LANG_FLUENCY)
    # Whether the reviewer's phone may be shared with students assigned to them (in the advance
    # "your interviewer will contact you" email). Opt-in by DEFAULT (True); a reviewer can opt out.
    share_phone_with_students = models.BooleanField(default=True)
    # Sensitive staff PII — reviewer + super only, never exposed to students/sponsors.
    phone = models.CharField(max_length=30, blank=True, default='')
    address = models.TextField(blank=True, default='')   # legacy single-line; kept for back-compat
    # Structured address (2026-06 redesign), mirroring the student address split.
    street_address = models.CharField(max_length=255, blank=True, default='')
    postcode = models.CharField(max_length=10, blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    state = models.CharField(max_length=50, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reviewer_profiles'

    def __str__(self):
        return f'ReviewerProfile for {self.partner_admin_id}'


class AssignmentEvent(models.Model):
    """An audit row for each (re)assignment of an application to a reviewer (F7).

    `from_admin`/`to_admin` are nullable FKs (admins are soft-deactivated, never
    hard-deleted, so the identity survives); `by_email` snapshots who performed it.
    A `to_admin` of None records an unassignment.
    """
    application = models.ForeignKey(
        'ScholarshipApplication', on_delete=models.CASCADE,
        related_name='assignment_events',
    )
    from_admin = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    to_admin = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    by_email = models.CharField(
        max_length=254, blank=True, default='',
        help_text="Email of the super-admin who performed the (re)assignment.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'assignment_events'
        ordering = ['-created_at']

    def __str__(self):
        return f'AssignmentEvent app={self.application_id} -> {self.to_admin_id} ({self.created_at})'


class SemesterResult(models.Model):
    """B40 Phase E/F (F9a): an in-programme student's latest-semester academic
    result. This is the IN-PROGRAMME progress signal — distinct from the pre-award
    ``results_slip`` (the SPM slip captured at application). The uploaded slip is
    **myNADI-only** (never crosses to a sponsor); only the DERIVED, non-identifying
    ``cgpa``/``graduated`` band feeds ``pool.derive_progress_state`` (the coarse
    ``progress_state`` a sponsor sees). The latest row (by ``created_at``) wins."""
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE,
        related_name='semester_results',
    )
    # Free label for the semester, e.g. "2026 Sem 1" / "Year 1 Sem 2". Display-only;
    # ordering uses created_at, not this string.
    semester = models.CharField(max_length=50, blank=True, default='')
    # 0.00–4.00 (Malaysian CGPA). Nullable — a student may record completion before
    # the official CGPA is published.
    cgpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    graduated = models.BooleanField(
        default=False,
        help_text="True when this result marks the student's graduation.",
    )
    # The myNADI-only proof slip. SET_NULL + related_name='+' — the slip is internal
    # evidence; deleting the doc must never cascade-delete the progress record.
    results_slip = models.ForeignKey(
        ApplicantDocument, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    note = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'semester_results'
        ordering = ['-created_at']

    def __str__(self):
        return f'SemesterResult app={self.application_id} {self.semester} cgpa={self.cgpa}'


class GraduationMessage(models.Model):
    """B40 Phase E/F (F9a): a student's anonymity-preserving graduation thank-you.

    Pipeline (owner decision 2026-06-09): the student submits ``raw_text`` →
    ``pool.scan_anon_for_identifiers`` runs as a STRUCTURAL gate (any leak of the
    student's own name/school/city/NRIC/phone/email → ``status='blocked'`` with the
    leaked ``scan_result`` fields, the student must edit) → a clean message is
    ``pending`` → myNADI staff approve (``approved``) or reject. An approved message
    is surfaced to the funding sponsor as *"a message from a student you supported"*
    linked ONLY to the anonymous ``pool.pool_ref`` — never a direct channel, never
    the student's identity. ``scrubbed_text`` is what the sponsor sees (defaults to
    ``raw_text`` on approval; staff may lightly redact)."""
    STATUS_CHOICES = [
        ('pending', 'Pending review'),     # clean scan, awaiting staff approval
        ('blocked', 'Blocked — identifiers'),  # scan found the student's own tokens
        ('approved', 'Approved'),          # staff-approved, sponsor-visible
        ('rejected', 'Rejected'),          # staff declined
    ]
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE,
        related_name='graduation_messages',
    )
    raw_text = models.TextField()
    scrubbed_text = models.TextField(blank=True, default='')
    # List of identifying field names the scan flagged (e.g. ['name', 'city']);
    # empty when the message is clean.
    scan_result = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    # Email of the staff member who approved/rejected (admins are soft-deactivated,
    # so a snapshot string is kept rather than an FK).
    approved_by = models.CharField(max_length=254, blank=True, default='')
    review_note = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'graduation_messages'
        ordering = ['-created_at']

    def __str__(self):
        return f'GraduationMessage app={self.application_id} [{self.status}]'


class SponsorReferral(models.Model):
    """B40 Phase E/F (F4): one sponsor inviting a prospective sponsor to the F1
    landing. The full guest-book model (owner decision 2026-06-09): each invite is a
    row, so the inviter sees their invitations + conversion. The invitee's email/name
    is PII for someone who has NOT consented — a 60-day purge (``purge_expired_referrals``)
    scrubs ``invitee_email``/``invitee_name`` and flips a still-``invited`` row to
    ``expired`` (the row stays for the inviter's count, minus the personal data)."""
    STATUS_CHOICES = [
        ('invited', 'Invited'),    # email sent, not yet joined
        ('joined', 'Joined'),      # the invitee registered as a sponsor (attributed)
        ('expired', 'Expired'),    # 60 days passed without joining; PII purged
    ]
    inviter = models.ForeignKey(
        Sponsor, on_delete=models.CASCADE, related_name='referrals_sent',
    )
    invitee_email = models.EmailField(blank=True, default='')   # cleared on purge
    invitee_name = models.CharField(max_length=200, blank=True, default='')
    note = models.CharField(max_length=500, blank=True, default='')   # the inviter's personal message
    # Opaque, non-guessable invite code carried by the /sponsor?ref=<code> link.
    code = models.CharField(max_length=32, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='invited')
    # The account the invitee became, once they register (attribution). SET_NULL so
    # deleting a sponsor never cascades away the referral history.
    registered_sponsor = models.ForeignKey(
        Sponsor, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    joined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sponsor_referrals'
        ordering = ['-created_at']

    def __str__(self):
        return f'SponsorReferral {self.code} by sponsor={self.inviter_id} [{self.status}]'
