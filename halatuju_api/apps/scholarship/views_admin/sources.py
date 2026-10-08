"""Sources — the referral organisations a student can arrive through.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.
"""
from rest_framework import status
from rest_framework.response import Response

from .base import _AdminBase
from .gift_programmes import AdminProgrammeListView


# ── Sources (referral organisations) + witness assignment (go-live transition) ────
# The Sources module is the first UI that edits organisation records as a registry (name,
# contact person/email/phone, active-in-apply, student count) — reusing the SAME
# PartnerOrganisation.phone/contact_* fields the existing AdminProfileView self-edit writes
# (no second contact_phone column, which would drift against that editor). Single-tenant
# today, so source rows are shared and NOT org-fenced (multi-tenant fencing of shared source
# rows is deliberately out of scope — see the plan's Out of scope / future).

def _source_dict(org, student_count=None, gift_count=0, gift_total=0):
    return {
        'id': org.id,
        'code': org.code,
        'name': org.name,
        'contact_person': org.contact_person or '',
        'contact_email': org.contact_email or '',
        'phone': org.phone or '',
        'show_in_apply': bool(org.show_in_apply),
        # HOW MANY GIFTS' apply forms list this source (per-gift referral sources, 2026-10-08):
        # links on the ACTIVE gifts in the caller's scope, of `gift_total` such gifts. Each gift
        # chooses its sources in its own Configuration (`gift_sources`); this page only counts.
        # The old single-gift `PartnerOrganisation.programme` is deprecated and no longer served.
        #
        # The count IS what students see (per-gift sources S2, 2026-10-08): each linked gift's
        # apply form lists this source while it stays switched on here (`gift_sources.offered_sources`).
        #
        # ⚠ NOT ACCESS CONTROL. A referral organisation is an ATTRIBUTION relationship, never a
        # scope — the same warning `PartnerAdmin.org` and `referred_by_org` carry.
        'gift_count': gift_count,
        'gift_total': gift_total,
        'is_active': bool(org.is_active),
        'student_count': student_count,
    }


def _gift_scope(admin):
    """The caller's gifts, for the per-source count — the same scope the gift list uses."""
    return AdminProgrammeListView()._programmes_for(admin)


def _one_source_dict(admin, org):
    """One row, counted the same way as the list (a PATCH answers with the row it changed)."""
    from .. import gift_sources
    scope = _gift_scope(admin)
    counted = gift_sources.gift_counts(type(org).objects.filter(pk=org.pk), scope).first()
    return _source_dict(org, _source_application_counts().get(org.id, 0),
                        counted.gift_count if counted else 0,
                        scope.filter(is_active=True).count())


# The platform's own bursary programme — the "house" organisation. Applicants who did
# not come through an external referral partner (self-referred via the apply form, or
# unattributed) count as the house org's own students. Kept as a code (not an id) so it
# survives reseeding; mirror of courses/views_admin.py owning-org default.
HOUSE_ORG_CODE = 'brightpath'


def _source_application_counts():
    """{org_id: bursary-APPLICATION count attributed to that organisation}.

    Counts scholarship *applications* (not the legacy course-selector referral
    registry, which holds hundreds of non-applicant profiles) and attributes each
    by the applicant's raw referral chip (`profile.referral_source`) — the SAME
    signal the Applications-list Source filter uses, so a source's count here
    equals its filtered applicant count. The stored `referred_by_org` FK is
    deliberately NOT used: it can drift (a self-referral chip left pointing at an
    old partner), which is what previously inflated CUMIG.

    Each external partner counts the applications whose chip == its `code`. The
    house org (`brightpath`) is the RESIDUAL: every application not claimed by an
    external partner (self-referral chips halatuju/other/social, blanks, or any
    unmapped chip). Single tenant today, so this is a global tally; revisit the
    residual split if applications ever span multiple house tenants.
    """
    from apps.courses.models import PartnerOrganisation
    from .. import partner_comms
    # chip -> number of applications carrying it (NULL/'' collapse to ''). The tally comes from
    # `partner_comms.chip_tally()`, the SAME definition `partner_comms.partner_applications(org)`
    # filters on, so this screen and the partner weekly digest cannot report different numbers
    # (docs/lessons.md: give the rule ONE named predicate both sides call).
    # org-fence: intentionally GLOBAL — see `chip_tally`'s own note.
    tally = partner_comms.chip_tally()
    total = sum(tally.values())
    orgs = list(PartnerOrganisation.objects.values('id', 'code'))
    partner_codes = {o['code'] for o in orgs if o['code'] != HOUSE_ORG_CODE}
    claimed = sum(tally.get(code, 0) for code in partner_codes)
    counts = {}
    for o in orgs:
        if o['code'] == HOUSE_ORG_CODE:
            counts[o['id']] = total - claimed          # residual → house org
        else:
            counts[o['id']] = tally.get(o['code'], 0)
    return counts


class _SourcesBase(_AdminBase):
    """Gate for the Sources + witness-assignment endpoints: super, admin, or org_admin
    (owner 2026-07-19 — the Admin role manages sources too). qc/reviewer/partner → 403.
    `has_role(admin, 'admin')` already passes super; org_admin is added explicitly."""
    def _sources_admin(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not (self.has_role(admin, 'admin') or admin.role == 'org_admin'):
            return None, self._deny_role()
        return admin, None


class AdminSourcesView(_SourcesBase):
    """GET  .../admin/scholarship/sources/ — every referral organisation + its student count.
    POST .../admin/scholarship/sources/ {code, name, contact_person?, contact_email?, phone?,
         show_in_apply?} — create a new source organisation."""
    def get(self, request):
        admin, err = self._sources_admin(request)
        if err:
            return err
        from apps.courses.models import PartnerOrganisation
        from .. import gift_sources
        counts = _source_application_counts()
        scope = _gift_scope(admin)
        total = scope.filter(is_active=True).count()
        # ONE annotated query for every row's gift count (never one per row).
        orgs = gift_sources.gift_counts(PartnerOrganisation.objects.all(), scope).order_by('name')
        return Response({
            'sources': [_source_dict(o, counts.get(o.id, 0), o.gift_count, total) for o in orgs],
        })

    def post(self, request):
        admin, err = self._sources_admin(request)
        if err:
            return err
        from apps.courses.models import PartnerOrganisation
        code = (request.data.get('code') or '').strip().lower()
        name = (request.data.get('name') or '').strip()
        if not code or not name:
            return Response({'error': 'code_and_name_required', 'code': 'code_and_name_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        # ⚠ RESERVED CODES (review, 2026-10-08): the three fixed form choices are referral CHIPS on
        # every student who picked them. A source row named `other` would collect every "Other"
        # student (profile_sync links, partner_notify / partner_comms email on chip == code), and the
        # house org's code is the Sources count's residual. Refused before the clash check.
        from .. import gift_sources
        if code in gift_sources.FIXED_CODES or code == HOUSE_ORG_CODE:
            return Response({'error': 'code_reserved', 'code': 'code_reserved'},
                            status=status.HTTP_400_BAD_REQUEST)
        if PartnerOrganisation.objects.filter(code=code).exists():
            return Response({'error': 'code_taken', 'code': 'code_taken'},
                            status=status.HTTP_400_BAD_REQUEST)
        org = PartnerOrganisation.objects.create(
            code=code, name=name,
            contact_person=(request.data.get('contact_person') or '').strip()[:200],
            contact_email=(request.data.get('contact_email') or '').strip()[:254],
            phone=(request.data.get('phone') or '').strip()[:30],
            show_in_apply=bool(request.data.get('show_in_apply', False)),
        )
        # A new source joins NO gift (owner, 2026-10-08) — each gift switches it on itself.
        return Response(_one_source_dict(admin, org), status=status.HTTP_201_CREATED)


class AdminSourceDetailView(_SourcesBase):
    """PATCH .../admin/scholarship/sources/<pk>/ — edit a source's name, contact details,
    active-in-apply flag, or is_active. Whitelisted fields only; the code slug is immutable."""
    def patch(self, request, pk):
        admin, err = self._sources_admin(request)
        if err:
            return err
        from apps.courses.models import PartnerOrganisation
        org = PartnerOrganisation.objects.filter(pk=pk).first()
        if org is None:
            return Response({'error': 'not_found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)
        # ⚠ `programme_id` IS REFUSED, NOT IGNORED (2026-10-08): a gift now chooses its sources in
        # its own Configuration, and a client still sending one gift would otherwise believe it
        # had been saved. Refused before anything is written; the deprecated
        # `PartnerOrganisation.programme` column is never written again.
        if 'programme_id' in request.data:
            return Response({'error': 'programme_id_retired', 'code': 'programme_id_retired'},
                            status=status.HTTP_400_BAD_REQUEST)
        fields = []
        if 'name' in request.data:
            org.name = (request.data.get('name') or '').strip()[:200]
            fields.append('name')
        if 'contact_person' in request.data:
            org.contact_person = (request.data.get('contact_person') or '').strip()[:200]
            fields.append('contact_person')
        if 'contact_email' in request.data:
            org.contact_email = (request.data.get('contact_email') or '').strip()[:254]
            fields.append('contact_email')
        if 'phone' in request.data:
            org.phone = (request.data.get('phone') or '').strip()[:30]
            fields.append('phone')
        if 'show_in_apply' in request.data:
            org.show_in_apply = bool(request.data.get('show_in_apply'))
            fields.append('show_in_apply')
        if 'is_active' in request.data:
            org.is_active = bool(request.data.get('is_active'))
            fields.append('is_active')
        if fields:
            org.save(update_fields=fields)
        return Response(_one_source_dict(admin, org))
