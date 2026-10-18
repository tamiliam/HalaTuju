"""Sources — the referral organisations a student can arrive through.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.
"""
from rest_framework import status
from rest_framework.response import Response

from .base import _AdminBase
from .gift_programmes import AdminProgrammeListView


# ── Sources + witness assignment ─────────────────────────────────────────────────
# Sources-and-referrals Sprint B (2026-10-18): a source is its own row (`ReferralSource`) OWNED BY
# THE ORGANISATION THAT ADDED IT, and every surface here is FENCED by that owner — the list, the
# POST (the new row is the caller's organisation's), the PATCH (another organisation's source is a
# 404) and the witness choice. A super is global, as everywhere in `_AdminBase`, and narrows with
# the organisation crumb (`?org=<code>`, `_org_narrowing`); a NEW source belongs to `?org=`, else
# the caller's own organisation, else the sole tenant (`_new_source_owner`). The house organisation
# is not a source and no longer appears in the list; a platform referral partner never did.

def _source_dict(org, student_count=None, gift_count=0, gift_total=0):
    return {
        'id': org.id,
        'code': org.code,
        'name': org.name,
        # The owning organisation's code — one value for an organisation's own staff; it tells a
        # super's unnarrowed list apart.
        'organisation': org.organisation.code,
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


def _gift_totals(scope):
    """`{organisation id: its ACTIVE gifts inside the caller's scope}` — one query. A source's
    `gift_total` is its OWN organisation's gifts, so a super's list never counts another
    organisation's gifts against it (for an organisation's own staff this is exactly as before)."""
    from django.db.models import Count
    return dict(scope.filter(is_active=True).values('organisation_id')
                .annotate(n=Count('pk')).values_list('organisation_id', 'n'))


def _one_source_dict(admin, org):
    """One row, counted the same way as the list (a PATCH answers with the row it changed)."""
    from .. import gift_sources
    scope = _gift_scope(admin)
    counted = gift_sources.gift_counts(type(org).objects.filter(pk=org.pk), scope).first()
    return _source_dict(org, _source_application_counts().get(org.id, 0),
                        counted.gift_count if counted else 0,
                        _gift_totals(scope).get(org.organisation_id, 0))


# The platform's own bursary programme — the "house" organisation. Its code is RESERVED: no source
# may carry it (Sources POST 400 `code_reserved`), and partner emails never go to it. Since sources
# Sprint B it is not a source at all and leaves the Sources list (with the residual count it used
# to carry). Kept as a code, mirrored in `partner_comms` and `apps.courses.referral_links`.
HOUSE_ORG_CODE = 'brightpath'


def _source_application_counts():
    """{source id: bursary-APPLICATION count attributed to that source}.

    Counts scholarship *applications* (not the legacy course-selector referral registry, which
    holds hundreds of non-applicant profiles) by the applicant's raw referral chip
    (`profile.referral_source`) — the SAME signal the Applications-list Source filter uses —
    and, since sources Sprint B, only among the applications OF THE SOURCE'S OWN ORGANISATION
    (a code is unique per organisation). The stored `referred_by_org` FK is deliberately NOT
    used: it is the referral partner's column, not the bursary answer.
    """
    from ..models import ReferralSource
    from .. import partner_comms
    # The tally comes from `partner_comms.chip_tally()`, the SAME definition
    # `partner_comms.partner_applications(source)` filters on, so this screen and the partner
    # weekly digest cannot report different numbers (docs/lessons.md: ONE named predicate).
    tally = partner_comms.chip_tally()
    return {pk: tally.get((owner, code), 0) for pk, owner, code in
            ReferralSource.objects.values_list('pk', 'organisation_id', 'code')}


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

    def _sources_in_scope(self, request, admin):
        """`(sources the caller may see, error)` — THE fence for every source surface. An
        organisation's staff see their own organisation's sources and nothing else (an
        organisation-less one sees none); a super sees every organisation's, narrowed by `?org=`."""
        from ..models import ReferralSource
        if not self.has_role(admin, 'super'):
            return ReferralSource.objects.owned_by(admin.owning_organisation_id), None
        org, err = self._org_narrowing(request, admin)
        if err:
            return None, err
        qs = ReferralSource.objects.all()
        return (qs.filter(organisation=org) if org is not None else qs), None

    def _new_source_owner(self, request, admin):
        """`(the organisation a NEW source belongs to, error)`: the caller's own organisation; a
        super may name another with `?org=`, and an organisation-less super who names none gets
        the platform's SOLE tenant when there is exactly one (evidence, not a guess — the
        `signup_programme_for` rule; the Sources page sends no `?org=` today). It must be a
        TENANT — never a referral partner or another source's old row. Otherwise 400
        `organisation_required`, never a pick between several."""
        from apps.courses.models import PartnerOrganisation
        tenants = PartnerOrganisation.objects.tenants()
        org_id = admin.owning_organisation_id
        if self.has_role(admin, 'super'):
            org, err = self._org_narrowing(request, admin)
            if err:
                return None, err
            if org is not None:
                org_id = org.pk
            elif org_id is None:
                only = list(tenants.values_list('pk', flat=True)[:2])
                org_id = only[0] if len(only) == 1 else None
        owner = tenants.filter(pk=org_id).first() if org_id else None
        if owner is None:
            return None, Response({'error': 'Say which organisation this source belongs to.',
                                   'code': 'organisation_required'},
                                  status=status.HTTP_400_BAD_REQUEST)
        return owner, None


class AdminSourcesView(_SourcesBase):
    """GET  .../admin/scholarship/sources/ — the caller's organisation's sources + student counts.
    POST .../admin/scholarship/sources/ {code, name, contact_person?, contact_email?, phone?,
         show_in_apply?} — create a source owned by the caller's organisation."""
    def get(self, request):
        admin, err = self._sources_admin(request)
        if err:
            return err
        from .. import gift_sources
        sources, err = self._sources_in_scope(request, admin)
        if err:
            return err
        counts = _source_application_counts()
        scope = _gift_scope(admin)
        totals = _gift_totals(scope)
        # ONE annotated query for every row's gift count (never one per row).
        rows = (gift_sources.gift_counts(sources, scope).select_related('organisation')
                .order_by('name', 'pk'))
        return Response({
            'sources': [_source_dict(s, counts.get(s.id, 0), s.gift_count,
                                     totals.get(s.organisation_id, 0)) for s in rows],
        })

    def post(self, request):
        admin, err = self._sources_admin(request)
        if err:
            return err
        from ..models import ReferralSource
        owner, err = self._new_source_owner(request, admin)
        if err:
            return err
        code = (request.data.get('code') or '').strip().lower()
        name = (request.data.get('name') or '').strip()
        if not code or not name:
            return Response({'error': 'code_and_name_required', 'code': 'code_and_name_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        # ⚠ RESERVED CODES (review, 2026-10-08): the three fixed form choices are referral CHIPS on
        # every student who picked them. A source row named `other` would collect every "Other"
        # student (profile_sync links, partner_notify / partner_comms email on chip == code), and the
        # house org's code is ours. Refused before the clash check.
        from .. import gift_sources
        if code in gift_sources.FIXED_CODES or code == HOUSE_ORG_CODE:
            return Response({'error': 'code_reserved', 'code': 'code_reserved'},
                            status=status.HTTP_400_BAD_REQUEST)
        # Unique WITHIN the organisation (another organisation's `smc` is not a clash, and saying
        # "taken" would confirm it exists).
        if ReferralSource.objects.filter(organisation=owner, code=code).exists():
            return Response({'error': 'code_taken', 'code': 'code_taken'},
                            status=status.HTTP_400_BAD_REQUEST)
        org = ReferralSource.objects.create(
            organisation=owner, code=code, name=name,
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
        sources, err = self._sources_in_scope(request, admin)
        if err:
            return err
        # Another organisation's source is a 404, never a 403 — it must not confirm it exists.
        org = sources.filter(pk=pk).first()
        if org is None:
            return Response({'error': 'not_found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)
        # ⚠ `programme_id` IS REFUSED, NOT IGNORED (2026-10-08): a gift now chooses its sources in
        # its own Configuration, and a client still sending one gift would otherwise believe it
        # had been saved. Refused before anything is written (the old single-gift column is gone,
        # TD-379, sources Sprint B).
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
