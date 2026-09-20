"""
The Layer-0 catalogue: what a programme asks for, and the invitation to apply.

Moved here VERBATIM from `apps/scholarship/models.py` at code health H15 (2026-09-20).
Moves only: no field, no `Meta`, no `db_table`, no `related_name` was touched, so the
database is untouched too — `makemigrations --check` reports no changes. See `__init__.py`.
"""
from django.db import models

from .programmes import Programme

# ─────────────────────────────────────────────────────────────────────────────
# What a programme ASKS FOR — the Layer 0 catalogue (config roadmap, sprint 2)
# ─────────────────────────────────────────────────────────────────────────────

# Shared by the catalogue's DEFAULT and a programme's CHOICE, so the two can never drift into
# meaning different things. 'optional' is a real state, not a shade of off: four documents are
# offered today without ever blocking a submission.
ITEM_STATE_CHOICES = [
    ('off', 'Not asked for'),
    ('optional', 'Offered, never blocks'),
    ('required', 'Must be provided'),
]


class ApplicationItem(models.Model):
    """One thing an application can ask a student for — a document or a question.

    **THIS IS A CATALOGUE, NOT A FORM BUILDER, and the distinction is the whole design.**
    Every row here is OUR content: we write it, we translate it into en/ms/ta, we know what
    the engine does with it. An organisation chooses WHICH of these apply to its programme
    (``ProgrammeApplicationItem`` below). It never authors a new one.

    Why it cannot be otherwise:

    * **Documents are read, not merely stored.** Each ``doc_type`` has recognition logic, a
      versioned signature model and verification behaviour behind it. An organisation can
      switch on a document the engine already understands; it cannot invent "water bill" and
      have anything comprehend the result. Hence the hard rule below that ``code`` must name
      an EXISTING ``ApplicantDocument.DOC_TYPES`` value.
    * **Questions must exist in three languages.** ``scripts/check-i18n.js`` fails the build on
      a missing key, and the owner is the Tamil authority. An org-authored question would
      quietly become his homework or ship English to a Tamil-speaking student.
    * **New personal data lands on erasure.** A free-text field an organisation invented is a
      new category of applicant data that Sprint E must know how to delete.

    This is the shipped form of the recorded platform rule: *"tenants configure WHICH checks
    and documents apply to their programme; they never get bespoke logic."*
    """
    KIND_CHOICES = [('document', 'Document'), ('question', 'Question')]

    kind = models.CharField(max_length=20, choices=KIND_CHOICES)

    # ⚠ For kind='document' this MUST be a value in ApplicantDocument.DOC_TYPES. The catalogue
    # NAMES an existing type; it never invents one. Enforced by test, not by a DB constraint,
    # because DOC_TYPES is a Python list and a migration cannot follow it.
    code = models.CharField(max_length=50)

    # Full i18n key, resolved by the web app. Never a literal label — a label stored here would
    # be a fourth place translations live and would escape check-i18n.js entirely.
    label_key = models.CharField(max_length=200)

    # An organisation may NOT switch this off. The floor is a POLICY decision, not an
    # engineering one — owner 2026-07-28: identity card, results slip, offer letter, consent,
    # and the family/income block.
    is_core = models.BooleanField(default=False)

    # What a NEWLY created programme starts with, before anybody ticks anything.
    #
    # ⚠ Three states, not a boolean. The first cut of this column was `default_on: bool`, which
    # cannot express "offered by default but never blocking" — and four items are exactly that
    # today (water bill, electricity bill, statement of intent, photo). A flag that cannot
    # represent a state the system already has is a schema asserting something false; caught
    # while writing the seed, fixed before any row existed.
    default_state = models.CharField(max_length=20, choices=ITEM_STATE_CHOICES, default='off')

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'application_items'
        ordering = ['kind', 'code']
        constraints = [
            models.UniqueConstraint(fields=['kind', 'code'], name='uniq_application_item'),
        ]

    def __str__(self):
        return f'{self.kind}:{self.code}'


class ProgrammeApplicationItem(models.Model):
    """One programme's answer to one catalogue item: off, optional, or required.

    **On PROGRAMME, not on ScholarshipCohort** — owner-approved 2026-07-28, and a deliberate
    departure from the "new tunables go on the cohort" convention. That convention exists to
    stop tunables becoming module CONSTANTS; both models are data, so it is not violated in
    spirit. What a programme asks for is the gift's IDENTITY, not the year's: a cohort-level
    home would make every annual intake re-tick the same list, which is exactly the rot this
    work exists to prevent. ``ScholarshipApplication.programme`` is already denormalised and
    set once in ``save()``, so resolution is one hop with no join through the cohort.

    ⚠ **NOT A SECURITY BOUNDARY.** Which items a programme asks for is configuration, never
    access control. The organisation fence (``_AdminBase._org_scoped`` / ``_org_allows``,
    cross-org ⇒ 404) is untouched by anything here. Confusing a configuration surface with a
    fence is the 2026-07-15 surface-partition incident, and it is worth restating in every
    model that a tenant can edit.
    """
    programme = models.ForeignKey(
        Programme, on_delete=models.CASCADE, related_name='application_items',
    )
    item = models.ForeignKey(
        ApplicationItem, on_delete=models.PROTECT, related_name='programme_selections',
    )
    state = models.CharField(max_length=20, choices=ITEM_STATE_CHOICES)

    updated_at = models.DateTimeField(auto_now=True)
    updated_by_email = models.CharField(max_length=254, blank=True, default='')

    class Meta:
        db_table = 'programme_application_items'
        ordering = ['programme_id', 'item_id']
        constraints = [
            models.UniqueConstraint(fields=['programme', 'item'],
                                    name='uniq_programme_application_item'),
        ]

    def __str__(self):
        return f'programme={self.programme_id} {self.item_id}={self.state}'


class Invitation(models.Model):
    """Somebody was asked to join, and this is the record of the asking.

    ⚠ **BEFORE THIS TABLE, AN INVITATION WAS NOT A THING** — it was a side effect of creating a
    `PartnerAdmin`. So the staff screen could not tell an invitation nobody acted on from a
    colleague of a year (both read "Active"), the expiry sweep wrote its verdict only into Supabase
    `user_metadata` where nothing reads it back, and no invite email was ever logged. Every one of
    those is the same missing noun.

    **It addresses three audiences and they do not share a lifecycle**, which is why this is its own
    table rather than more columns on `PartnerAdmin`:

    - `staff` — the account already exists when the invitation is sent (invite provisions it), so
      accepting means SIGNING IN for the first time. Detected by `first_seen_at`.
    - `sponsor` — **nothing is created, and that is the point.** A sponsor invitation is a prompt
      with a link to the ordinary public registration; they still consent, sign the terms and are
      vetted. Owner's constraint: an invitation must never be a way around any of that.
    - `source_partner` — an ORGANISATION-level bursary referrer. ⚠ NOT the platform-level
      `partner` role, which is the HalaTuju course selector's **Referral Partner** and a different
      relationship entirely; one organisation can hold both (CUMIG does). See docs/decisions.md,
      2026-08-03.

    ⚠ **STATUS IS DERIVED, NEVER STORED** (`invitations.status_of`). A stored "expired" is only true
    while a cron keeps it true, and a cron that stops makes the screen lie — which is precisely how
    `temp_password_expired` already fails today. The only thing written by a sweep here is
    `pii_purged_at`, which records that we scrubbed the data, not that the invitation lapsed.

    ⚠ **`credential_issued` DISSOLVES THE GOOGLE BLIND SPOT.** Three invite branches produce three
    different truths — a fresh non-Google address gets a password, a Google address gets none (the
    account materialises on first Google sign-in), an already-registered address gets none — and
    afterwards they look identical. So "expired" is meaningful for the first and meaningless for the
    other two: nothing of theirs has expired, they simply have not come. Written at the one moment
    it is known, in the view that took the branch.
    """
    AUDIENCE_CHOICES = [
        ('staff', 'Staff'),
        ('sponsor', 'Sponsor'),
        ('source_partner', 'Source partner'),
    ]

    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default='staff')
    email = models.EmailField(blank=True, default='')          # cleared on PII purge
    name = models.CharField(max_length=200, blank=True, default='')   # cleared on PII purge
    #: The role a staff invitation grants. Blank for the other audiences, which grant no role.
    role = models.CharField(max_length=20, blank=True, default='')
    #: The tenant for `staff`; the referring organisation for `source_partner`.
    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invitations',
    )
    invited_by = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invitations_sent',
    )
    #: Opaque, non-guessable — the same shape `SponsorReferral` uses for its link.
    code = models.CharField(max_length=32, unique=True, db_index=True)

    #: The account a staff invitation provisioned. Present from the moment of invite, because for
    #: staff the row IS created up front — which is exactly why acceptance cannot be inferred from
    #: its existence and needs `first_seen_at`.
    partner_admin = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.CASCADE, null=True, blank=True,
        related_name='invitations',
    )
    #: The account a SPONSOR invitation eventually became. Null until they register themselves.
    sponsor = models.ForeignKey(
        'Sponsor', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    #: WHICH GIFT a sponsor invitation is into (S-ASSIGN, 2026-09-04).
    #:
    #: ⚠ IT GRANTS NOTHING, AND THAT RULE IS OLDER THAN THIS FIELD. A sponsor invitation creates
    #: no account: it is a prompt with a link to the ordinary public registration, and the invitee
    #: still consents, signs the terms and is vetted (owner's constraint, see the class docstring —
    #: "an invitation must never be a way around any of that"). This only records which gift the
    #: organisation MEANT, so that when they do register the pending membership opens against the
    #: right one instead of whichever gift happens to be the only active one.
    #:
    #: NULL is normal: every invitation sent before today has none, and with a single active gift
    #: the registration resolves it anyway. It is only load-bearing once an organisation runs two.
    programme = models.ForeignKey(
        'Programme', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        help_text='Sponsor invitations only: the gift the organisation is inviting them into. '
                  'NULL = not stated, and registration resolves it if it can.',
    )

    expires_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    pii_purged_at = models.DateTimeField(null=True, blank=True)
    #: Set when a genuinely DIFFERENT grant replaces this one (a new role, a new organisation).
    #: A plain re-send is not a supersede — it bumps the counters below and moves one clock.
    superseded_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )

    # ── the send record ──────────────────────────────────────────────────────────
    # "Invitations send email, but that is not shown to anyone" (owner, 2026-08-03). Until now
    # `send_partner_welcome_email` returned a bare bool that became a banner and vanished on reload,
    # so a bounced invitation was indistinguishable from a delivered one nobody had acted on.
    last_sent_at = models.DateTimeField(null=True, blank=True)
    send_count = models.PositiveSmallIntegerField(default=0)
    last_send_ok = models.BooleanField(null=True, blank=True)
    last_send_error = models.CharField(max_length=300, blank=True, default='')

    #: Whether a temporary password was actually issued — see the class docstring.
    credential_issued = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'invitations'
        ordering = ['-created_at']
        constraints = [
            # ⚠ ONE OPEN INVITATION PER (audience, email). A second invite to somebody already
            # invited must find the existing row, not start a rival one — otherwise the screen
            # shows two rows for one person and neither is wrong. Partial, so the history of
            # accepted and revoked invitations is unlimited.
            models.UniqueConstraint(
                fields=['audience', 'email'],
                condition=models.Q(accepted_at__isnull=True, revoked_at__isnull=True),
                name='uniq_open_invitation_per_audience_email',
            ),
        ]

    def __str__(self):
        return f'Invitation {self.audience}:{self.email or "(purged)"} [{self.code}]'
