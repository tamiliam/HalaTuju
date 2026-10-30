"""What a SOURCE USER may reach — source sign-in S1 (2026-10-30).

Roadmap: `docs/plans/2026-10-30-source-sign-in-roadmap.md`. A source user is a `PartnerAdmin` with
`role='source_partner'` and `source` set (the referral source it signs in for). Nothing serves
these sets yet: S1 is the foundation, and S3's `admin/source/` endpoints are their first readers.

⚠ THE ORGANISATION FENCE FIRST. Every set below is cut to the SOURCE's own organisation
(`ReferralSource.organisation`, which `PartnerAdmin.save` holds equal to the user's
`owning_organisation`) before the source narrows it — the same order `_org_scoped` then a filter
takes in the staff views. A source belongs to one organisation, so this should never bite; it is
there so a wrong row can only ever narrow.

⚠ NOTHING, NOT AN ERROR, FOR ANYONE ELSE. Somebody who is not an ACTIVE source user, whose source is
missing, or whose source has been switched off (`ReferralSource.is_active=False` — the roadmap's
"lose access" door) gets an empty queryset. `show_in_apply=False` only hides the source on the apply
form and does NOT reach here.

⚠ TWO SETS, ON PURPOSE (C14). `applications_for` also holds the cases where this source is the
WITNESS by override (`witness_org`), or has witnessed (S4 review M1), without being the applicant's
source: such a case shows the contract task only (S4), never a row on the Applications list — that list is
`listed_applications_for`, which is exactly the partner emails' own "this source's students"
(`partner_comms.partner_applications`), so the console and the emails cannot disagree.
"""
from django.db.models import Q

from .models import Programme, ProgrammeReferralSource, ScholarshipApplication
from .partner_comms import partner_applications


def source_of(admin):
    """The ACTIVE source ``admin`` signs in for, or None when they may see nothing."""
    if (admin is None or not admin.is_active or admin.is_super
            or not admin.is_source_user or admin.source_id is None):
        return None
    source = admin.source
    if not source.is_active or admin.owning_organisation_id != source.organisation_id:
        return None
    return source


def listed_applications_for(admin):
    """The applications this source user's lists show: those whose OWN answer named the source."""
    source = source_of(admin)
    if source is None:
        return ScholarshipApplication.objects.none()   # org-fence: the empty set
    return partner_applications(source)


def applications_for(admin):
    """Every application this source user may open: the listed ones, plus the cases it witnesses
    by override (`witness_org`), plus the contracts it HAS witnessed (`bursary_agreement.witness_org`,
    stamped by `record_witness`) — all inside the source's own organisation.

    ⚠ THE THIRD SET (review M1, 2026-10-30): a witness, once recorded, belongs to the source that
    signed it. An override moved AFTERWARDS must neither take the signed contract away from that
    source nor hand it to the new one (`source_console.is_the_witness` reads the same stamp)."""
    source = source_of(admin)
    if source is None:
        return ScholarshipApplication.objects.none()   # org-fence: the empty set
    # org-fence: the source's own organisation, in the same filter.
    by_override = ScholarshipApplication.objects.filter(
        witness_org_id=source.pk, owning_organisation_id=source.organisation_id)
    # org-fence: the source's own organisation, in the same filter.
    signed = ScholarshipApplication.objects.filter(
        bursary_agreement__witness_org_id=source.pk,
        bursary_agreement__witness_signed_at__isnull=False,
        owning_organisation_id=source.organisation_id)
    return partner_applications(source) | by_override | signed


def programmes_for(admin):
    """The gifts this source user may look at, inside the source's organisation: a gift that LISTS
    the source on its apply form (`ProgrammeReferralSource`), or one that holds a listed application.

    ⚠ An application reaches its gift through the cohort as well as its own column (a cohort moved
    between gifts leaves `programme` on the old one — the rule `programme_student_queryset` keeps),
    so both are read. Inactive gifts are included, as `AdminScopeListView` includes them for staff.
    """
    source = source_of(admin)
    if source is None:
        return Programme.objects.none()
    listed = listed_applications_for(admin)
    linked = ProgrammeReferralSource.objects.filter(source_id=source.pk).values('programme_id')
    return (Programme.objects.filter(organisation_id=source.organisation_id)
            .filter(Q(pk__in=linked) | Q(pk__in=listed.values('programme_id'))
                    | Q(pk__in=listed.values('cohort__programme_id'))))
