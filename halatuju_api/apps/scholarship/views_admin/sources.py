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

def _source_dict(org, student_count=None, gift_count=0, gift_total=0, sign_in=('none', 0)):
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
        # SOURCE SIGN-IN (S2, 2026-10-30): `none` | `invited` | `joined`, and how many ACTIVE people
        # sign in for this source (`source_invite.sign_in_states`). `joined` is also what locks the
        # source's own details here (`AdminSourceDetailView`, 409 `managed_by_source`).
        'sign_in': sign_in[0],
        'user_count': sign_in[1],
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
    from .. import gift_sources, source_invite
    scope = _gift_scope(admin)
    counted = gift_sources.gift_counts(type(org).objects.filter(pk=org.pk), scope).first()
    return _source_dict(org, _source_application_counts().get(org.id, 0),
                        counted.gift_count if counted else 0,
                        _gift_totals(scope).get(org.organisation_id, 0),
                        source_invite.sign_in_states([org.pk]).get(org.pk, ('none', 0)))


# The platform's own bursary programme — the "house" organisation. Its code is RESERVED: no source
# may carry it (Sources POST 400 `code_reserved`), and partner emails never go to it. Since sources
# Sprint B it is not a source at all and leaves the Sources list (with the residual count it used
# to carry). Kept as a code, mirrored in `partner_comms` and `apps.courses.referral_links`.
HOUSE_ORG_CODE = 'brightpath'


#: The text fields a source's details are made of, with the column width each is cut to. ONE table
#: for Add (now the source invite) and Edit, so the two cannot cut a value differently.
DETAIL_FIELDS = (('name', 200), ('contact_person', 200), ('contact_email', 254), ('phone', 30))


def new_source_fields(data, *, code_key='code', name_key='name'):
    """The cleaned columns of a NEW source from a request body. The keys default to the old Add
    source's; the source invite (source sign-in S2) names them `source_code` / `source_name`, since
    its own `name` is the person's."""
    fields = {'code': (data.get(code_key) or '').strip().lower(),
              'show_in_apply': bool(data.get('show_in_apply', False))}
    for field, width in DETAIL_FIELDS:
        fields[field] = (data.get(name_key if field == 'name' else field) or '').strip()[:width]
    return fields


def new_source_refusal(owner, fields):
    """None, or the 400 code a NEW source of ``owner`` is refused with. THE rules Add source
    applied (sources Sprint B); since source sign-in S2 the source invite applies them, because a
    source is now created by inviting its person (`views_admin/source_users.py`)."""
    from .. import gift_sources
    from ..models import ReferralSource
    if not fields['code'] or not fields['name']:
        return 'code_and_name_required'
    # ⚠ RESERVED CODES (review, 2026-10-08): the three fixed form choices are referral CHIPS on
    # every student who picked them. A source row named `other` would collect every "Other"
    # student (profile_sync links, partner_notify / partner_comms email on chip == code), and the
    # house org's code is ours. Refused before the clash check.
    if fields['code'] in gift_sources.FIXED_CODES or fields['code'] == HOUSE_ORG_CODE:
        return 'code_reserved'
    # Unique WITHIN the organisation (another organisation's `smc` is not a clash, and saying
    # "taken" would confirm it exists).
    if ReferralSource.objects.filter(organisation=owner, code=fields['code']).exists():
        return 'code_taken'
    return None


def _source_application_counts():
    """{source id: bursary-APPLICATION count attributed to that source}.

    Counts scholarship *applications* (not the legacy course-selector referral registry, which
    holds hundreds of non-applicant profiles) by the source EACH APPLICATION named at submit
    (`ScholarshipApplication.source`, sources Sprint C — owner's ruling: the answer given on that
    application, not the student's latest), which is always one of the application's own
    organisation's sources. The referral partner's `referred_by_org` is never used.
    """
    from .. import partner_comms
    # The tally comes from `partner_comms.source_tally()`, the SAME field
    # `partner_comms.partner_applications(source)` filters on, so this screen and the partner
    # weekly digest cannot report different numbers (docs/lessons.md: ONE named predicate).
    return partner_comms.source_tally()


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
    """GET  .../admin/scholarship/sources/ — the caller's organisation's sources + student counts
         and, since source sign-in S2, each one's `sign_in` and `user_count`.
    POST — RETIRED (410 `use_source_invitation`): a source is added by inviting its person."""
    def get(self, request):
        admin, err = self._sources_admin(request)
        if err:
            return err
        from .. import gift_sources
        sources, err = self._sources_in_scope(request, admin)
        if err:
            return err
        from .. import source_invite
        counts = _source_application_counts()
        scope = _gift_scope(admin)
        totals = _gift_totals(scope)
        # ONE query for every row's sign-in state, like the gift count below (never one per row).
        signed = source_invite.sign_in_states(sources.values('pk'))
        # ONE annotated query for every row's gift count (never one per row).
        rows = (gift_sources.gift_counts(sources, scope).select_related('organisation')
                .order_by('name', 'pk'))
        return Response({
            'sources': [_source_dict(s, counts.get(s.id, 0), s.gift_count,
                                     totals.get(s.organisation_id, 0),
                                     signed.get(s.id, ('none', 0))) for s in rows],
        })

    def post(self, request):
        """⚠ RETIRED (source sign-in S2, 2026-10-30, roadmap conflict C6): a source is now ADDED by
        inviting its person — `POST admin/invitations/` with `audience='source_partner'` and a new
        `source_name` + `source_code`, under exactly the rules this POST applied
        (`new_source_refusal`). 410 with a code rather than removing the method: a 405 would read
        as a bug to an old client, and says nothing about where the door went."""
        admin, err = self._sources_admin(request)
        if err:
            return err
        return Response({'error': 'Sources are added by inviting them, on Invitations → Source.',
                         'code': 'use_source_invitation'}, status=status.HTTP_410_GONE)


class AdminSourceNamesView(_AdminBase):
    """GET .../admin/scholarship/source-names/ — `{sources: [{code, name}]}` for the Applications
    list's Source filter, column and tooltips (sources Sprint C, TD-381 part 4). EVERY role that may
    open that list may call it — reviewer and QC too, who get 403 on Sources — and it serves names
    only (never a contact, a count or an id). Fenced like Sources: an organisation's staff get
    their own organisation's sources (switched-off ones too, so old applicants stay filterable;
    an organisation-less caller gets none); a super gets every organisation's, narrowed by `?org=`.

    `?programme=<gift code>` (request #41, 2026-10-22) — the SAME code the Applications list sends —
    narrows to THAT gift's sources: every source LINKED to it (a link row exists — switched off in
    Sources since or not, so old applicants stay filterable), plus any source of the gift's own
    organisation whose code one of the gift's applicants carries (an unlinked one included; other
    unlinked sources, switched off or not, are left out). "The gift's applicants" is
    `programme_student_queryset` — the cohort-aware predicate the list uses; "carries" is the
    application's own answer (`referral_code`), the field the list's Source filter matches. The
    student profile's chip (`referral_source`) is deliberately NOT read: a code only on a profile would be an
    option that can only return 0 rows. Sources are looked up INSIDE the gift's organisation only
    (codes are unique per organisation). The gift is resolved by `_gift_narrowing`: an unknown or
    another organisation's gift is a 404 for an organisation's staff, never a leak; a super may
    name any gift (then `?org=` is not read). No `?programme=` → exactly as before."""

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if self._b40_scope(admin) == 'none':
            return self._deny_role()
        from django.db.models import Q
        from ..models import ReferralSource
        from .gifts import programme_student_queryset
        programme, err = self._gift_narrowing(request, admin)
        if err:
            return err
        if programme is not None:
            applicants = programme_student_queryset(programme)
            qs = ReferralSource.objects.owned_by(programme.organisation_id).filter(
                Q(gift_links__programme=programme)
                | Q(code__in=applicants.values('referral_code'))).distinct()
        elif self.has_role(admin, 'super'):
            org, err = self._org_narrowing(request, admin)
            if err:
                return err
            qs = ReferralSource.objects.all()
            qs = qs.filter(organisation=org) if org is not None else qs
        else:
            qs = ReferralSource.objects.owned_by(admin.owning_organisation_id)
        return Response({'sources': [{'code': c, 'name': n} for c, n in
                                     qs.order_by('name', 'pk').values_list('code', 'name')]})


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
        details = {field: (request.data.get(field) or '').strip()[:width]
                   for field, width in DETAIL_FIELDS if field in request.data}
        # ⚠ ONCE THE SOURCE HAS SIGNED IN, ITS DETAILS ARE ITS OWN (owner ruling 2026-10-30, source
        # sign-in S2, roadmap C6): a CHANGE to name / contact person / contact email / phone is
        # refused 409 `managed_by_source` — the source edits them itself (S3's profile). The
        # organisation keeps `show_in_apply` (the Active toggle) and `is_active` (switching the
        # source off is how its sign-in is taken away). The same value sent back is not a change,
        # so a form that re-sends what it was given is not refused for it.
        changed = [field for field, value in details.items() if value != getattr(org, field)]
        if changed:
            from .. import source_invite
            if source_invite.has_joined(org):
                return Response({'error': 'This source has signed in and now keeps its own '
                                          'details.', 'code': 'managed_by_source',
                                 'fields': changed}, status=status.HTTP_409_CONFLICT)
        fields = []
        for field, value in details.items():
            setattr(org, field, value)
            fields.append(field)
        if 'show_in_apply' in request.data:
            org.show_in_apply = bool(request.data.get('show_in_apply'))
            fields.append('show_in_apply')
        if 'is_active' in request.data:
            org.is_active = bool(request.data.get('is_active'))
            fields.append('is_active')
        if fields:
            org.save(update_fields=fields)
        return Response(_one_source_dict(admin, org))
