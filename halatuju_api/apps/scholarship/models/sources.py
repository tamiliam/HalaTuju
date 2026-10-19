"""Referral SOURCES — their own table, owned by an organisation (sources-and-referrals Sprint B).

Owner's model (decisions.md 2026-10-09, settled): three categories, never one table's three moods.

- An ORGANISATION (a tenant, e.g. BrightPath) runs gifts. `PartnerOrganisation.objects.tenants()`.
- A SOURCE is a name on one organisation's "Who referred you?" list, with contact details for the
  partner emails. **It BELONGS to the organisation that added it**: only that organisation sees,
  adds, edits or switches it off, and it is never shared with another organisation. THIS table.
- A REFERRAL PARTNER is PLATFORM level and owned by NO organisation: `partner`-role logins on the
  course-selector side, a `?ref=` link, and the students `StudentProfile.referred_by_org` names.
  It stays a `PartnerOrganisation` row marked `is_referral_partner` (`apps.courses.referral_links`).

Until this sprint all three were rows of `partner_organisations`. The rows that were sources were
COPIED here keeping their ids (scholarship migration 0173), so every foreign key that named a
source — `ProgrammeReferralSource.source`, `StudentProfile.source`, both `witness_org`s and
`PartnerEmailLog.organisation` — moved by swapping its constraint, not by rewriting a value. The
`partner_organisations` copies are kept: the image serving before this one read them, and old
intake snapshots name their codes; Sprint D (2026-10-19, courses 0082) switched them off, and
dropped `StudentProfile.source` (courses 0083) — the application carries its own source since C. CUMIG is BOTH: its referral
partner row stays on `partner_organisations` with its logins and its students, and its source row
lives here, owned by BrightPath, with the same id.

⚠ A CODE IS UNIQUE PER ORGANISATION, NOT GLOBALLY. Two organisations may each have an `smc`. So a
source is always looked up INSIDE an organisation (`owned_by`), never by its code alone.

⚠ NOT ACCESS CONTROL. A source is an ATTRIBUTION relationship, never a scope. Who may see a source
is decided by the owning-organisation fence in the views (`views_admin/sources.py`), not by this row.
"""
from django.db import models


class ReferralSourceQuerySet(models.QuerySet):
    def owned_by(self, organisation_id):
        """The sources ONE organisation owns. `None` (an organisation-less caller) → none at all,
        never every organisation's: a missing fence must narrow, not widen."""
        if organisation_id is None:
            return self.none()
        return self.filter(organisation_id=organisation_id)


class ReferralSource(models.Model):
    """One source on one organisation's "Who referred you?" list. See the module docstring."""

    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT, related_name='owned_sources',
        help_text='The organisation (tenant) that added this source and alone may see or edit it.',
    )
    code = models.CharField(max_length=50, help_text='Slug, unique within the organisation: smc')
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200, blank=True, default='')
    contact_email = models.EmailField(blank=True, default='')
    phone = models.CharField(max_length=30, blank=True, default='')
    #: Switched on in Sources: a gift's Configuration may offer it (`gift_sources.active_sources`).
    show_in_apply = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ReferralSourceQuerySet.as_manager()

    class Meta:
        db_table = 'referral_sources'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['organisation', 'code'],
                                    name='uniq_referral_source_org_code'),
        ]

    def __str__(self):
        return f'{self.name} ({self.code})'
