"""
Authored email copy and its send log, for partners and for sponsors, plus the
sponsor terms a sponsor accepts.

Moved here VERBATIM from `apps/scholarship/models.py` at code health H15 (2026-09-20).
Moves only: no field, no `Meta`, no `db_table`, no `related_name` was touched, so the
database is untouched too — `makemigrations --check` reports no changes. See `__init__.py`.
"""
from django.db import models

# ── Partner-organisation comms (2026-07-26) ───────────────────────────────────
# Weekly + milestone emails to the referral organisations that run this bursary
# alongside us. See docs/plans/2026-07-26-partner-comms-roadmap.md.

class PartnerEmailTemplate(models.Model):
    """One of the five partner emails: its wording AND its on/off switch.

    Enablement is a property of the TEMPLATE, not of an (organisation, kind) pair —
    owner ruling 2026-07-26: *"if the email template is active, it goes out to all
    qualifying partners. It is either, or."* So there is exactly one row per kind and
    no per-organisation selection anywhere in this feature.

    `body` is plain text with `{placeholder}` tokens (the allowlist per kind lives in
    `partner_comms.KINDS`); blank lines are paragraph breaks. Rendering wraps it in the
    shared HTML email shell — HTML is the primary part, with a plain-text alternative
    carrying the same information.
    """
    KIND_CHOICES = [
        ('weekly_summary', 'Weekly summary'),
        ('shortlisted_followup', 'Chase list'),
        ('awaiting_review', 'Awaiting review'),
        ('awarded', 'Awarded'),
        ('assigned', 'A student joins their list'),
        # Request #3 (2026-08-01). The ONE row here whose recipient is the STUDENT, not the
        # organisation — it is the other half of `assigned`, sent at the same moment. It lives on
        # this screen because that is where the owner looks for anything that sends, and every
        # surface must say who receives it. ⚠ It is NOT silenced by PARTNER_COMMS_ENABLED (owner,
        # 2026-08-01): that flag answers "what do ORGANISATIONS receive?", and a student's notice
        # about access to their own details must not disappear with it.
        ('student_assigned', 'The student is told'),
        # Request #10 (2026-08-02). Five emails our REVIEWERS already receive, moved out of
        # hard-coded prose so the organisation can edit what its own volunteers are told. They are
        # edited on the Reviewers screen, not Sources — a reviewer is not a referral partner — but
        # they live in this table because the machinery (a stored body, one switch, a send log) is
        # the same, and a third family would be three copies of it. ⚠ The MODEL NAME is now wrong
        # for three of its four audiences; TD-212 tracks the rename.
        ('reviewer_assigned', 'A case is assigned to a reviewer'),
        ('qc_returned', 'QC returns a case for revision'),
        ('qc_rejected', 'QC rejects a case'),
        ('verdict_due_soon', 'A verdict is due soon'),
        ('verdict_overdue', 'A verdict is overdue'),
        # 2026-08-04. The INVITATION emails, made editable on the owner's instruction. Edited on
        # Organisation → Invitations.
        #
        # ⚠ THESE HAVE NO SWITCH, and that is a deliberate departure from every other row here.
        # An invitation email that can be turned off means pressing "Send invite" creates the
        # account, issues the password and tells nobody — a silence nothing reports. Wording is the
        # organisation's; whether an invitation is delivered at all is not a setting.
        #
        # ⚠ ONE PER GROUP ON THE PAGE, and the mapping is DATA, not prose: `emails._invite_kind_for_role`
        # reads `invitations.KIND_ROLES` — the same map that decides which table a person is listed
        # in. So finance is written to as an admin and qc as a reviewer, and the letter can never
        # disagree with the table somebody is sitting in.
        ('invite_admin', 'Joining the team — admin'),
        ('invite_reviewer', 'Joining the team — reviewer'),
        # ⚠ NOTHING SENDS THIS YET. No Source Partner has a login and the page offers no way to
        # invite one; it is agreed wording waiting for the Source console (owner, 2026-08-04). It is
        # here rather than in the console sprint so the words are settled before the screen is
        # built — but do not read its existence as a working invitation route.
        ('invite_source', 'Inviting a source organisation'),
        ('invite_sponsor', 'Inviting a sponsor'),
    ]

    #: Kinds whose recipient is the STUDENT. Everything else on this screen goes to the partner
    #: organisation, so the distinction has to be data rather than something a reader remembers.
    STUDENT_KINDS = frozenset({'student_assigned'})

    #: Kinds whose recipient is one of OUR REVIEWERS — internal staff mail, English-only, edited on
    #: Organisation → Reviewers. Like `STUDENT_KINDS` they are exempt from `PARTNER_COMMS_ENABLED`:
    #: that flag answers "what do ORGANISATIONS receive?", and taking partner comms dark must never
    #: silently stop the mail that tells a volunteer they have been given a case.
    REVIEWER_KINDS = frozenset({
        'reviewer_assigned', 'qc_returned', 'qc_rejected',
        'verdict_due_soon', 'verdict_overdue',
    })
    #: The four invitation kinds, one per group on Organisation → Invitations. Exempt from
    #: `PARTNER_COMMS_ENABLED` for the same reason as the reviewer kinds, and additionally exempt
    #: from their OWN `enabled` flag — see the note in KIND_CHOICES. `emails._invite_render` never
    #: asks whether they are switched on.
    INVITE_KINDS = frozenset({
        'invite_admin', 'invite_reviewer', 'invite_source', 'invite_sponsor',
    })

    kind = models.CharField(max_length=32, choices=KIND_CHOICES, unique=True)
    enabled = models.BooleanField(default=False)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    updated_by_email = models.CharField(max_length=254, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'partner_email_templates'
        ordering = ['kind']

    def __str__(self):
        return f'{self.kind} ({"on" if self.enabled else "off"})'


class PartnerEmailLog(models.Model):
    """Every partner email we attempted — the audit trail, the "last sent" the admin
    screen shows, AND the fingerprint the weekly skip compares against.

    Deliberately the only home for send state: the most recent row for an
    (organisation, kind) pair answers both "when did we last write to them?" and "did
    anything change since?", so there is no second copy of that state to drift.

    A row is written even when the send FAILS (`ok=False`) and when it is skipped for
    having no recipient — silence must be visible, not indistinguishable from success.
    """
    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.CASCADE,
        related_name='partner_email_log',
    )
    kind = models.CharField(max_length=32, choices=PartnerEmailTemplate.KIND_CHOICES)
    # The addresses actually written to, as stored (already lower-cased + de-duplicated).
    recipients = models.JSONField(default=list, blank=True)
    subject = models.CharField(max_length=255, blank=True, default='')
    # Set for the per-student kinds; NULL for the two weekly digests.
    application = models.ForeignKey(
        'ScholarshipApplication', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='partner_emails',
    )
    # Short hash of the payload (the stage counts) — the weekly-summary skip test.
    fingerprint = models.CharField(max_length=64, blank=True, default='')
    students = models.IntegerField(default=0, help_text='How many students the email covered.')
    ok = models.BooleanField(default=False)
    note = models.CharField(max_length=200, blank=True, default='',
                            help_text="Why nothing was sent, e.g. 'no_recipient', 'unchanged'.")
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'partner_email_log'
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['organisation', 'kind', '-sent_at'],
                         name='partner_email_org_kind_idx'),
        ]

    def __str__(self):
        return f'{self.kind} → org={self.organisation_id} @ {self.sent_at:%Y-%m-%d %H:%M}'


class SponsorEmailTemplate(models.Model):
    """One of the nine sponsor emails: its wording AND its on/off switch.

    The sibling of `PartnerEmailTemplate`, and deliberately the same shape — one row per kind,
    enablement on the TEMPLATE rather than on a (sponsor, kind) pair. A per-sponsor switch was
    never considered: a sponsor is not a tenant, and "which of my donors hear about a new
    student" is not a decision anyone should be making one donor at a time.

    `body` is plain text with `{placeholder}` tokens (the allowlist per kind lives in
    `sponsor_comms.PLACEHOLDERS`); blank lines are paragraph breaks and a block that is exactly
    `{student_cards}` becomes the rich per-student cards. Rendering goes through
    `email_templates.render`, shared with the partner family.

    Nine kinds, not eleven: `low_balance` and `annual_statement` were deferred by the owner on
    2026-07-28 because they edge from transactional account mail into marketing, and what a
    sponsor consented to at registration is not currently reviewable (TD-186).
    """
    KIND_CHOICES = [
        ('welcome', 'Welcome — registered, awaiting vetting'),
        ('approved', 'Approved'),
        ('rejected', 'Not approved'),
        ('suspended', 'Suspended'),
        ('reinstated', 'Reinstated'),
        ('credit_confirmed', 'Credit confirmed'),
        ('new_students', 'New students to consider'),
        ('weekly_digest', 'Weekly digest'),
        ('referral_invite', 'Invitation to a prospective sponsor'),
    ]
    kind = models.CharField(max_length=32, choices=KIND_CHOICES, unique=True)
    enabled = models.BooleanField(default=False)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    updated_by_email = models.CharField(max_length=254, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sponsor_email_templates'
        ordering = ['kind']

    def __str__(self):
        return f'{self.kind} ({"on" if self.enabled else "off"})'


class SponsorEmailLog(models.Model):
    """Every sponsor email we attempted — the audit trail and the "last sent" the panel shows.

    A row is written even when the send FAILS and when it is SKIPPED for having no recipient or
    a switched-off template: silence must be visible, not indistinguishable from success. That
    rule is inherited from partner comms, where it exists because an unreachable organisation
    looked exactly like a quiet one.

    `sponsor` is nullable for one reason: `referral_invite` goes to a prospective sponsor who has
    no account yet, so the row records the INVITER and the recipient address separately.
    """
    sponsor = models.ForeignKey(
        'Sponsor', on_delete=models.SET_NULL, null=True, blank=True, related_name='email_log',
    )
    kind = models.CharField(max_length=32, choices=SponsorEmailTemplate.KIND_CHOICES)
    # The addresses actually written to, as stored (already lower-cased + de-duplicated).
    recipients = models.JSONField(default=list, blank=True)
    subject = models.CharField(max_length=255, blank=True, default='')
    ok = models.BooleanField(default=False)
    note = models.CharField(max_length=200, blank=True, default='',
                            help_text="Why nothing was sent, e.g. 'no_recipient', 'disabled'.")
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sponsor_email_log'
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['sponsor', 'kind', '-sent_at'],
                         name='sponsor_email_kind_idx'),
        ]

    def __str__(self):
        return f'{self.kind} → sponsor={self.sponsor_id} @ {self.sent_at:%Y-%m-%d %H:%M}'


class SponsorTermsVersion(models.Model):
    """One version of the terms a sponsor accepts when they join.

    The sibling of `ContractTemplate` in intent and deliberately a fraction of its size. What is
    kept from there: draft immutability, a publish that archives the previous active row inside one
    transaction, and a version string that a past acceptance can point at forever. What is dropped:
    the payment schedule, the counterparty/signing apparatus, the lawyer-vetting attestation, .docx
    import, PDF rendering, and the three-level clause hierarchy — sections here are a FLAT numbered
    list, because a thirteen-section document does not need an outline tree.

    PLATFORM-LEVEL, with no `organisation` FK, matching `Sponsor` and `SponsorEmailTemplate` (both
    classified `cross-org-by-design` in test_org_fence.py). A sponsor account is not a tenant's
    property, so neither are the terms it accepts. A second tenant wanting its own terms is a
    documented later decision, not a field guessed at now.

    ⚠ These are NOT the bursary agreement. That is a 94-clause instrument between BrightPath and a
    STUDENT, and a sponsor is not a party to it (see TD-191). Do not merge the two.
    """
    STATUS_DRAFT = 'draft'
    STATUS_ACTIVE = 'active'
    STATUS_ARCHIVED = 'archived'
    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_ARCHIVED, 'Archived'),
    )

    version = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    # English is authoritative; ms/ta are courtesy translations and may lag (warning W1).
    title_en = models.CharField(max_length=255, blank=True, default='')
    title_ms = models.CharField(max_length=255, blank=True, default='')
    title_ta = models.CharField(max_length=255, blank=True, default='')
    intro_en = models.TextField(blank=True, default='')
    intro_ms = models.TextField(blank=True, default='')
    intro_ta = models.TextField(blank=True, default='')

    created_by_email = models.CharField(max_length=254, blank=True, default='')
    published_by_email = models.CharField(max_length=254, blank=True, default='')
    published_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sponsor_terms_versions'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.version} ({self.status})'

    @property
    def languages_available(self):
        """Locales a sponsor may be served WHOLE. English is always available.

        A locale only counts when the title, the intro AND every section heading and body carry
        it — a half-translated document would otherwise silently fall back mid-page, which reads
        as a bug to the person it happens to.
        """
        out = ['en']
        sections = list(self.sections.all())
        for loc in ('ms', 'ta'):
            if not (getattr(self, f'title_{loc}').strip() and getattr(self, f'intro_{loc}').strip()):
                continue
            if all(getattr(sec, f'heading_{loc}').strip() and getattr(sec, f'body_{loc}').strip()
                   for sec in sections) and sections:
                out.append(loc)
        return out


class SponsorTermsSection(models.Model):
    """One numbered section of a `SponsorTermsVersion`, and optionally its quiz checkpoint.

    FLAT — there is no `level`. Sections are numbered 1..N by `order`, contiguously, and the number
    shown is the order itself rather than a computed outline label. That single choice removes the
    whole hierarchy apparatus the contract module needs (`normalise_levels`, `clause_numbers`,
    `MAX_QUIZ_LEVEL`, ancestor/descendant resolution, indent/outdent and their guards).

    Headings are TextField rather than CharField(255) on purpose: the contract module needed a
    `_fit_heading` guard on every write path because an over-long heading could overflow the
    varchar and 500 a save. A TextField cannot.

    `quiz_{en,ms,ta}` reuses the payload shape the student bursary quiz already uses —
    ``{tag, plain, question, options: [3 strings], correct: 0-2, why}`` — so the authoring editor
    and the sponsor-facing quiz component both port from working code. An empty dict means no quiz
    in that language; `en` is mandatory whenever `is_quiz_candidate` is set.
    """
    terms = models.ForeignKey(
        SponsorTermsVersion, on_delete=models.CASCADE, related_name='sections',
    )
    order = models.PositiveIntegerField()

    heading_en = models.TextField(blank=True, default='')
    heading_ms = models.TextField(blank=True, default='')
    heading_ta = models.TextField(blank=True, default='')
    body_en = models.TextField(blank=True, default='')
    body_ms = models.TextField(blank=True, default='')
    body_ta = models.TextField(blank=True, default='')

    is_quiz_candidate = models.BooleanField(default=False)
    quiz_en = models.JSONField(default=dict, blank=True)
    quiz_ms = models.JSONField(default=dict, blank=True)
    quiz_ta = models.JSONField(default=dict, blank=True)
    # Blank = hand-written. Otherwise the model that drafted it, kept as provenance.
    quiz_generated_model = models.CharField(max_length=80, blank=True, default='')

    class Meta:
        db_table = 'sponsor_terms_sections'
        ordering = ['terms_id', 'order']
        constraints = [
            models.UniqueConstraint(fields=['terms', 'order'],
                                    name='uniq_sponsor_terms_section_order'),
        ]

    def __str__(self):
        return f'{self.terms_id}.{self.order} {self.heading_en[:40]}'


class SponsorTermsAcceptance(models.Model):
    """That a given sponsor accepted a given VERSION — or was deliberately not asked.

    One row per (sponsor, version), and a HISTORY table rather than a latest-value field on
    `Sponsor`: publishing a new version can then re-ask without destroying the record of what was
    agreed before. `terms` is PROTECT so a version that has governed an acceptance can never be
    deleted out from under it.

    ⚠ `basis` is load-bearing and must never be collapsed to a boolean. `grandfathered` means WE DID
    NOT ASK THIS PERSON, which is the opposite of "they agreed" — every surface that reads it must
    say so. Same principle as `SponsorEmailLog` writing a row for a skip: silence has to be visible,
    not indistinguishable from success.

    ⚠ This is NOT `Sponsor.consent_at` / `consent_version`. Those hold the PDPA privacy consent — a
    permission the sponsor GRANTS US, imposing no duty on them. Merging the two is the error TD-191
    exists to prevent.
    """
    BASIS_ACCEPTED = 'accepted'
    BASIS_GRANDFATHERED = 'grandfathered'
    BASIS_CHOICES = (
        (BASIS_ACCEPTED, 'Accepted by the sponsor'),
        (BASIS_GRANDFATHERED, 'Grandfathered — never asked'),
    )

    sponsor = models.ForeignKey(
        'Sponsor', on_delete=models.CASCADE, related_name='terms_acceptances',
    )
    terms = models.ForeignKey(
        SponsorTermsVersion, on_delete=models.PROTECT, related_name='acceptances',
    )
    basis = models.CharField(max_length=20, choices=BASIS_CHOICES, default=BASIS_ACCEPTED)

    # Typing a name IS the signature here, matching `BursaryAgreement.student_signed_name` and the
    # credit chain's `admin_signed_name` / `finance_signed_name` / `org_admin_signed_name`.
    # `registered_name_at_acceptance` freezes the account name at that moment so a divergence stays
    # visible to an admin forever — we never REFUSE a variant spelling, because there is no IC to
    # match against and rejecting someone their own name is a worse failure than storing a
    # difference.
    signed_name = models.CharField(max_length=200, blank=True, default='')
    registered_name_at_acceptance = models.CharField(max_length=200, blank=True, default='')

    accepted_at = models.DateTimeField(null=True, blank=True)
    quiz_passed_at = models.DateTimeField(null=True, blank=True)
    locale = models.CharField(max_length=5, blank=True, default='en')
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    # Grandfathering only: who granted the exemption and why.
    granted_by_email = models.CharField(max_length=254, blank=True, default='')
    reason = models.CharField(max_length=300, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sponsor_terms_acceptances'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['sponsor', 'terms'],
                                    name='uniq_sponsor_terms_acceptance'),
        ]

    def __str__(self):
        return f'sponsor={self.sponsor_id} {self.terms_id} ({self.basis})'
