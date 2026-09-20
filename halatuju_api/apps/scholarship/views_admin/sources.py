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

def _source_dict(org, student_count=None):
    return {
        'id': org.id,
        'code': org.code,
        'name': org.name,
        'contact_person': org.contact_person or '',
        'contact_email': org.contact_email or '',
        'phone': org.phone or '',
        'show_in_apply': bool(org.show_in_apply),
        # WHICH GIFT'S apply form lists this source (S-ASSIGN, 2026-09-04). NULL = every gift,
        # which is what all seven live referral organisations have and what needs no backfill.
        #
        # ⚠ IT NARROWS `show_in_apply`, and `show_in_apply` DOES NOT YET REACH THE STUDENT FORM.
        # The apply form's referring-organisation list is still the hard-coded
        # `REFERRING_ORG_OPTIONS` constant in `lib/scholarship.ts`; nothing reads this flag on
        # the student side yet. So setting a gift here records the organisation's intent and
        # changes NOTHING a visitor sees — do not read a value in this column as proof that the
        # form is narrowed. Wiring the form to the registry is its own change, and it is what
        # makes this field bite.
        #
        # ⚠ NOT ACCESS CONTROL. A referral organisation is an ATTRIBUTION relationship, never a
        # scope — the same warning `PartnerAdmin.org` and `referred_by_org` carry.
        'programme_id': org.programme_id,
        'programme_name': (org.programme.name_en or org.programme.code)
                          if org.programme_id else '',
        'is_active': bool(org.is_active),
        'student_count': student_count,
    }


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
        counts = _source_application_counts()
        orgs = PartnerOrganisation.objects.select_related('programme').order_by('name')
        return Response({
            'sources': [_source_dict(o, counts.get(o.id, 0)) for o in orgs],
            # The gift choices behind the per-source picker. ACTIVE only: this narrows which
            # apply form lists the source, and a form that is not open lists nothing.
            'programmes': [
                {'id': p.id, 'code': p.code, 'name': p.name_en or p.code}
                for p in AdminProgrammeListView()._programmes_for(admin)
                                                 .filter(is_active=True).order_by('code')
            ],
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
        return Response(_source_dict(org, 0), status=status.HTTP_201_CREATED)


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
        if 'programme_id' in request.data:
            # Blank/null CLEARS it, and clearing means EVERY gift — the permissive default all
            # seven live sources carry. A gift outside the caller's organisation is refused, so
            # a tenant cannot list a source on somebody else's form.
            asked = request.data.get('programme_id')
            if asked in (None, ''):
                org.programme = None
            else:
                programme = AdminProgrammeListView()._programmes_for(admin).filter(
                    pk=asked).first()
                if programme is None:
                    return Response({'error': 'not_found', 'code': 'not_found'},
                                    status=status.HTTP_404_NOT_FOUND)
                org.programme = programme
            fields.append('programme')
        if 'is_active' in request.data:
            org.is_active = bool(request.data.get('is_active'))
            fields.append('is_active')
        if fields:
            org.save(update_fields=fields)
        return Response(_source_dict(org, _source_application_counts().get(org.id, 0)))
