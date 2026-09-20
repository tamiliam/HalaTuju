"""
A sponsor and its membership of a programme.

Moved here VERBATIM from `apps/scholarship/models.py` at code health H15 (2026-09-20).
Moves only: no field, no `Meta`, no `db_table`, no `related_name` was touched, so the
database is untouched too — `makemigrations --check` reports no changes. See `__init__.py`.
"""
from django.db import models

class Sponsor(models.Model):
    """Phase E: a self-registered sponsor ACCOUNT. A sponsor signs in via Supabase Auth — like a
    student — then registers here; an admin VETS them before they get any access
    to the anonymised student pool ("open to apply, approved to browse").

    Safety: a Sponsor never sees identifying student data (name/NRIC/address/phone/
    email/photo) anywhere — the marketplace is permanently anonymous (P2P model).
    This model only governs the sponsor's own account + vetting state.
    """
    STATUS = [
        ('pending', 'Pending review'),   # self-registered, awaiting admin vetting
        ('approved', 'Approved'),         # vetted — may browse the anonymised pool
        ('rejected', 'Rejected'),         # vetting declined
        ('suspended', 'Suspended'),       # access revoked after approval
    ]
    supabase_user_id = models.CharField(
        max_length=100, unique=True,
        help_text='Supabase Auth UID, set when the sponsor self-registers',
    )
    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True, default='')
    # "How did you find us?" — self-reported acquisition channel (free dropdown).
    source = models.CharField(max_length=50, blank=True, default='')
    organisation = models.CharField(max_length=200, blank=True, default='')
    # Light KYC context for the admin vetting decision (who they are / why they
    # want to sponsor). Never shown to students.
    note = models.TextField(blank=True, default='')
    # PDPA consent captured at registration (Personal Data Protection Act 2010).
    consent_at = models.DateTimeField(null=True, blank=True)
    consent_version = models.CharField(max_length=30, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    # Boundary decision (2026-06-07): a TRUSTED sponsor (known/vetted — the launch
    # default) may see institution-level detail on the anonymised card; a future
    # PUBLIC/untrusted sponsor does not. Default True so every existing + launch
    # sponsor is trusted; flip to False per-sponsor when public onboarding opens.
    is_trusted = models.BooleanField(default=True)
    # F3 (Phase E/F): how often this sponsor wants to hear about newly-published
    # anonymised students. 'realtime' = an hourly-batched alert, 'weekly' = a
    # weekly digest, 'off' = no emails. Default 'weekly' (a gentle cadence).
    NOTIFY_FREQUENCIES = [('realtime', 'Real-time'), ('weekly', 'Weekly digest'), ('off', 'Off')]
    notify_frequency = models.CharField(max_length=10, choices=NOTIFY_FREQUENCIES, default='weekly')
    # When the last weekly digest was sent to THIS sponsor; the next digest only
    # includes students published after it (so a sponsor never gets a duplicate).
    last_digest_sent_at = models.DateTimeField(null=True, blank=True)
    # Last time this sponsor was seen using their own portal — stamped by SponsorMeView,
    # the one call every sponsor page makes. Nothing recorded this before (no `last_login`
    # anywhere in the codebase), so an approved sponsor who never came back was
    # indistinguishable from an active one. NULL = not seen since this shipped.
    # Deliberately coarse: throttled to one write a day (`SPONSOR_SEEN_THROTTLE_HOURS`),
    # because "are they still with us" is a question about days, not minutes, and a write
    # on every portal request would put a needless UPDATE on a read path.
    last_seen_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.CharField(
        max_length=254, blank=True, default='',
        help_text='Email of the PartnerAdmin who vetted this sponsor',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sponsors'
        ordering = ['-created_at']

    @property
    def is_approved(self):
        return self.status == 'approved'

    def __str__(self):
        return f'Sponsor {self.email} ({self.status})'


class SponsorProgrammeMembership(models.Model):
    """A sponsor's acceptance into ONE gift programme (platform programme layer, 2026-07-26).

    The owner's rule: a sponsor sees a programme's students only if they *"specifically
    onboarded into both and accepted into both — and that is not a given"*. So the sponsor
    ACCOUNT stays platform-level (one login, one identity, one vetting of "is this a real,
    legitimate person") while **acceptance is per programme**, and it survives the year
    rollover because it attaches to the durable Programme, not to an intake.

    Two gates, both of which must pass before a sponsor sees a student:
      1. ``Sponsor.status == 'approved'`` — the ACCOUNT is vetted at all (unchanged);
      2. an ``approved`` membership row here — accepted into THIS programme.

    This narrows WHICH cards a funder sees. It must never touch the allowlist governing
    WHAT a card shows — anonymity is absolute and is enforced elsewhere (``pool.py`` +
    the allowlist serializers). See decisions.md, "Benefactor anonymity is absolute".
    """
    STATUS = [
        ('pending', 'Pending review'),   # onboarded into the programme, awaiting vetting
        ('approved', 'Approved'),         # accepted — may browse THIS programme's pool
        ('rejected', 'Rejected'),         # not accepted into this programme
        ('suspended', 'Suspended'),       # access to this programme revoked after approval
    ]
    sponsor = models.ForeignKey(
        Sponsor, on_delete=models.CASCADE, related_name='programme_memberships',
    )
    programme = models.ForeignKey(
        'Programme', on_delete=models.PROTECT, related_name='sponsor_memberships',
    )
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    # Who vetted this membership + when (the org admin acting for that programme).
    vetted_by = models.CharField(max_length=200, blank=True, default='')
    vetted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sponsor_programme_memberships'
        # One membership per (sponsor, programme) — acceptance is a state, not a log.
        constraints = [
            models.UniqueConstraint(fields=['sponsor', 'programme'],
                                    name='uniq_sponsor_programme_membership'),
        ]
        ordering = ['sponsor_id', 'programme_id']

    def __str__(self):
        return f'sponsor={self.sponsor_id} programme={self.programme_id} {self.status}'

    @property
    def is_approved(self):
        return self.status == 'approved'
