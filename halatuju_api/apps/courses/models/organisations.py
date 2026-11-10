"""Partner organisations, their themes and their configuration."""

from django.db import models


class PartnerOrganisationQuerySet(models.QuerySet):
    """Makes the SAFE read the obvious one — see `tenants()`."""

    def tenants(self):
        """Only TENANT organisations: those that own an active programme, or have an active
        `org_admin`.

        ⚠ THIS EXISTS BECAUSE THE PLAIN QUERYSET IS A TRAP. This table is dual-role (see the
        model docstring): it holds tenant organisations AND referral organisations — schools and
        NGOs that send us students — with **no flag telling a tenant apart**. Production has ten
        rows and exactly one tenant. So `PartnerOrganisation.objects.filter(is_active=True)`
        reads like "the organisations" and returns nine things that are not.

        That is not hypothetical: the console's organisation switcher shipped on 2026-07-28
        offering Sri Murugan Centre and Tara Foundation as tenants to switch into, written by
        someone who had verified this exact trap against production the same morning and written
        it down. A note in a knowledge base does not reach the moment the queryset is typed; a
        manager method does.

        Both conditions, not either alone: ownership alone loses a tenant created moments before
        its programme (the admin form makes organisation + programme + administrator together),
        and `org_admin` alone loses a live tenant whose administrator was revoked.

        `role='org_admin'` specifically, NOT "has a PartnerAdmin" — a referral organisation's
        logins are `partner`-role course-selector accounts, and counting those would readmit
        precisely the rows this excludes.
        """
        from django.db.models import Exists, OuterRef, Q
        from apps.scholarship.public import Programme
        from ..models_staff import PartnerAdmin   # was a module-level name of the old models.py

        owns_programme = Programme.objects.filter(
            organisation_id=OuterRef('pk'), is_active=True)
        has_org_admin = PartnerAdmin.objects.filter(
            owning_organisation_id=OuterRef('pk'), role='org_admin', is_active=True)
        return self.filter(Q(Exists(owns_programme)) | Q(Exists(has_org_admin)))


class PartnerOrganisation(models.Model):
    """Tenant organisation AND platform referral partner (TD-381). Since sources-and-referrals Sprint
    B (2026-10-18) a SOURCE is its own row, `scholarship.ReferralSource`, owned by an organisation;
    the rows here that used to be sources were copied there with their ids and are kept, unread by
    the source surfaces; Sprint D (courses 0082) switched them off (`is_active` false), never
    deleting one — old snapshots name their codes.

    - Referral registry (original role): `StudentProfile.referred_by_org` /
      `PartnerAdmin.org` point here to mean "the organisation that REFERRED a
      student/admin" — an attribution marker, NEVER an access-control boundary.
    - Platform organisation (platform Sprint 1, 2026-07): the tenant that OWNS a
      scholarship programme. Ownership hangs off `ScholarshipCohort.owning_organisation`
      (the source of truth for programme ownership); the branding/sender/module columns
      below are that tenant's configuration surface (PRD §2–§3). These columns are
      seeded but NOT yet read anywhere — the read seams land in later platform sprints
      (branding Sprint 5/6, module enforcement Sprint 10).
    `is_active` doubles as the tenant active/suspended switch (D-5: suspend, never delete).
    """
    code = models.CharField(max_length=50, unique=True, help_text='URL slug: cumig, partner2')
    name = models.CharField(max_length=200)
    contact_email = models.EmailField(blank=True)
    contact_person = models.CharField(max_length=200, blank=True, default='')
    # The contact person's phone (paired with contact_person/contact_email above; the
    # Sources module + AdminProfileView both edit this SAME field — deliberately not a
    # second `contact_phone` column, which would drift against the existing editor).
    phone = models.CharField(max_length=30, blank=True, default='')
    is_active = models.BooleanField(default=True)
    # `show_in_apply` (the old "offered on the apply form" flag) left the MODEL in sources Sprint D
    # (2026-10-19): sources carry their own since Sprint B. courses 0082 gives the column a database
    # default (migrate-first) and 0083 drops it AFTER the image without the field is live.
    # A PLATFORM REFERRAL PARTNER (2026-10-09; today `cumig` alone) — the only rows a `?ref=` link
    # writes into `StudentProfile.referred_by_org` (`referral_links`). A row may also be a source.
    is_referral_partner = models.BooleanField(default=False, db_default=False, help_text='A PLATFORM referral partner: its ?ref= link fills a student\'s referred_by_org (owned by no organisation).')
    # The old single-gift `programme` column left the MODEL in sources Sprint B (TD-379, 2026-10-18);
    # courses 0080 drops the column AFTER the image without it is live (contract, image-first).
    created_at = models.DateTimeField(auto_now_add=True)

    # ── Tenant identity & branding (platform Sprint 1; '' = use platform default) ──
    programme_name_en = models.CharField(max_length=200, blank=True, default='')
    programme_name_ms = models.CharField(max_length=200, blank=True, default='')
    programme_name_ta = models.CharField(max_length=200, blank=True, default='')
    logo_url = models.CharField(max_length=500, blank=True, default='')
    brand_colour = models.CharField(
        max_length=20, blank=True, default='',
        help_text="Hex colour, e.g. '#137fec'; '' = platform default",
    )
    persona_name_en = models.CharField(max_length=100, blank=True, default='')
    persona_name_ms = models.CharField(max_length=100, blank=True, default='')
    persona_name_ta = models.CharField(max_length=100, blank=True, default='')
    team_signoff_en = models.CharField(max_length=200, blank=True, default='')
    team_signoff_ms = models.CharField(max_length=200, blank=True, default='')
    team_signoff_ta = models.CharField(max_length=200, blank=True, default='')

    # ── Tenant sender identity (platform Sprint 1) ──
    email_from = models.EmailField(blank=True, default='')
    email_reply_to = models.EmailField(blank=True, default='')
    email_support = models.EmailField(blank=True, default='')
    frontend_url = models.CharField(max_length=200, blank=True, default='')

    # ── Module flags (platform Sprint 1; WRITTEN but NOT enforced until Sprint 10) ──
    module_scholarship = models.BooleanField(default=False)
    module_sponsor_pool = models.BooleanField(default=False)
    module_comms_whatsapp = models.BooleanField(default=False)
    module_payout = models.BooleanField(default=False)

    # Use `PartnerOrganisation.objects.tenants()` for anything that means "the
    # organisations we run" — the plain queryset also returns REFERRAL organisations.
    objects = PartnerOrganisationQuerySet.as_manager()

    class Meta:
        db_table = 'partner_organisations'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.code})'


class OrganisationTheme(models.Model):
    """An organisation's colours, STORED as the resolved token set (Layer 1 A1).

    Why a row rather than a wider `brand_colour` column: what is stored is the set of shades a
    tenant APPROVED, not an input we re-derive per request. See `theme_tokens` for the full
    argument — briefly, deriving on the way out means improving the derivation silently restyles
    every tenant, and it makes A4's full palette a migration instead of a second editor.

    ── Shape ──
    `tokens` is `{"light": {"brand-50": "247 250 254", ...}, "dark": {...}}`; values are the
    space-separated RGB triplets the CSS custom properties take, so painting is a straight write
    with no conversion. Every write passes `theme_tokens.validate_tokens` via `save()` — the fence
    is on the model, not on an endpoint, so a shell caller cannot go around it.

    ── Several rows per organisation, ONE of them live (Layer 1 A3) ──
    A1 shipped this as a `OneToOne` and said A3 would relax it. It has. An organisation now has a
    HISTORY of colour versions and at most one `active` — which is what makes changing a colour
    something other than a live experiment on applicants:

        draft     — being worked on. NEVER served. At most one per organisation.
        active    — what visitors see. At most one per organisation.
        archived  — what they used to see. Kept, because that is what makes Revert a real undo
                    rather than "try to remember the old hex".

    ⚠ **THE SERVE PATH READS `active` AND NOTHING ELSE**, at one seam — `active_for()` below, which
    `scholarship.branding` calls. If a draft could reach a visitor, the whole sprint is undone, so
    that is the single filter to protect. The lifecycle (publish, revert) lives in
    `courses.theme_versions`, not here: a model that both stores and transitions ends up with the
    transaction spread across its callers.

    ⚠ THE UNIQUENESS IS PER STATE, NOT PER ORGANISATION. Two partial constraints (`draft` and
    `active`) rather than one blanket rule — an organisation may hold many `archived` rows and must,
    or Revert has nothing to go back to.

    ── BrightPath deliberately has NO row ──
    The platform's light ramp in `globals.css` is the seeded brand hexes, not `brand_ramp()`'s
    output, so giving BrightPath a derived row would shift its own colours by a channel or two.
    No row → the web app keeps today's behaviour exactly.
    """
    STATUS_DRAFT = 'draft'
    STATUS_ACTIVE = 'active'
    STATUS_ARCHIVED = 'archived'
    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_ARCHIVED, 'Archived'),
    )

    organisation = models.ForeignKey(
        PartnerOrganisation, on_delete=models.CASCADE, related_name='themes')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    # The colour the set was derived FROM. Provenance, not the source of truth — a hand-written or
    # (later) per-token set may have no single colour behind it, hence blank-able.
    source_colour = models.CharField(
        max_length=20, blank=True, default='',
        help_text="The hex these tokens were derived from, e.g. '#a21caf'; '' = set by hand",
    )
    tokens = models.JSONField(default=dict)
    published_by_email = models.CharField(max_length=254, blank=True, default='')
    published_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organisation_themes'
        ordering = ['-created_at']
        constraints = [
            # PARTIAL, per state. An organisation may hold many `archived` rows and must — that
            # history IS the undo. Only "being worked on" and "what visitors see" are singular.
            models.UniqueConstraint(
                fields=['organisation'], condition=models.Q(status='draft'),
                name='one_draft_theme_per_organisation'),
            models.UniqueConstraint(
                fields=['organisation'], condition=models.Q(status='active'),
                name='one_active_theme_per_organisation'),
        ]

    @classmethod
    def active_for(cls, organisation):
        """⚠ THE SERVE SEAM. The one live theme for an organisation, or None.

        `scholarship.branding.Branding.theme` calls this and nothing else. Everything a visitor
        sees goes through here, so this filter is the whole of "a draft never reaches a student":
        `test_a_draft_never_reaches_a_visitor` breaks loudly if it is widened.
        """
        return cls.objects.filter(organisation=organisation, status=cls.STATUS_ACTIVE).first()

    def __str__(self):
        return f'Theme for {self.organisation.code}'

    def save(self, *args, **kwargs):
        # The seam every writer passes. `validate_tokens` raises ThemeTokenError (a ValueError) on
        # anything a tenant may not store — a tone, an unknown family, a malformed triplet, or a
        # `brand-500` that differs between the modes.
        from .. import theme_tokens
        theme_tokens.validate_tokens(self.tokens)
        return super().save(*args, **kwargs)


class OrganisationConfiguration(models.Model):
    """The values an organisation has CHANGED from the platform defaults (Org Config Sprint A).

    One row per organisation; `values` holds ONLY the keys the organisation set, e.g.
    `{"pool_funded_grace_days": 30}`. A missing key — or a missing row — means the platform
    default, read live from Django settings. What may be stored (keys, types, bounds) is the
    REGISTRY in `courses.org_config`; `save()` validates through it, so the fence is on the
    model, not on an endpoint (the `OrganisationTheme` precedent — a shell caller cannot go
    around it).

    ⚠ STORE ONLY WHAT WAS CHANGED, NEVER A COPY OF THE DEFAULTS. A copied default is correct on
    the day it is written and wrong the day the platform default moves — the same rot as a
    backfill without its write path. Blank is an ANSWER: "follow the platform".
    """
    organisation = models.OneToOneField(
        PartnerOrganisation, on_delete=models.CASCADE, related_name='configuration')
    values = models.JSONField(default=dict)
    updated_by_email = models.CharField(max_length=254, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organisation_configurations'

    def __str__(self):
        return f'Configuration for {self.organisation.code}'

    def save(self, *args, **kwargs):
        # The seam every writer passes. Raises OrgConfigError (a ValueError) on an unknown key,
        # a non-integer, or a value outside the registry's bounds.
        from .. import org_config
        org_config.validate_values(self.values)
        return super().save(*args, **kwargs)
