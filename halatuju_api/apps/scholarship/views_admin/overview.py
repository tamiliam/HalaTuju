"""The programme Overview: its panels, and the order an org admin puts them in.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.
"""
import logging

from rest_framework import status
from rest_framework.response import Response

from .base import _AdminBase


# ⚠ THE PACKAGE'S name, spelled out — never `__name__`. A submodule logger reads
# `apps.scholarship.views_admin.<module>` and drops every audit line it carries out
# of the Cloud Logging scrape metric. Guarded by `AuditLoggerNameTest` (H11).
logger = logging.getLogger('apps.scholarship.views_admin')


class AdminProgrammeOverviewView(_AdminBase):
    """GET /api/v1/admin/scholarship/programme-overview/ — "how is this gift doing?"

    The page a person lands on after clicking a gift card. **Open to every console role and
    SHAPED by role**: a reviewer lands on their own cases, a QC on their queue, a finance admin
    on the money, an org admin on all of it. Everything is computed by `programme_overview`,
    which holds the organisation fence.

    ⚠⚠ **THERE ARE TWO GATES HERE, AND THE SECOND IS NOT COSMETIC.** The first is the ORG FENCE
    (`programme_overview.application_scope`, re-asserted per query inside that module). The second
    is ROLE SHAPING: `SECTIONS_BY_ROLE` decides SERVER-SIDE which keys are built at all, so a
    reviewer's response has no money key to hide and a finance admin's has no funnel. The menu
    already withholds Payments and Spending from reviewer/qc; an Overview that served their
    figures anyway would have made that withholding decorative.

    ⚠ **FINANCE IS ADMITTED HERE THOUGH ITS PRESET LACKS `spending`, THE SPENDING PAGE'S GATE.**
    Deliberate widening, owner 2026-09-15, recorded in `docs/decisions.md` and the role matrix:
    finance gets TOTALS — committed, paid, remaining, spent, by month, by category — and never a
    name, a file or a verdict, because none of those is in a section it is given.

    ⚠ **A ROLE WITH NO SECTIONS IS REFUSED, NOT SERVED AN EMPTY PAGE.** `partner` is the one such
    role today (a referral organisation is attribution, never a scope). A future role added to
    `ROLE_CHOICES` without a decision in `SECTIONS_BY_ROLE` lands here too — a 403 is a question
    somebody answers, an empty page is a bug nobody notices.

    ⚠ A SUPER GETS `spend_report.ALL_ORGS`, the same platform scope the Spending and
    funding-summary screens hand them (2026-09-11/12) — `admin.is_super` must mean the same thing
    on every Programme page, or the console teaches people that some pages "just do not work for
    you". An `org_admin` with no organisation is still `no_org`: that is a broken account, not a
    scope.

    tenancy: org-fenced in `programme_overview.application_scope`; role-shaped by
    `SECTIONS_BY_ROLE`. Classified in test_org_fence.py.
    """

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        from .. import programme_overview, spend_report
        if not programme_overview.sections_for(admin):
            return self._deny_role()
        programme, gift_err = self._gift_narrowing(request, admin)
        if gift_err:
            return gift_err
        cohort, intake_err = self._intake_narrowing(request, admin, programme)
        if intake_err:
            return intake_err
        if admin.is_super:
            org = spend_report.ALL_ORGS
        else:
            org = admin.owning_organisation
            if org is None:
                return Response({'error': 'no_org', 'code': 'no_org'},
                                status=status.HTTP_400_BAD_REQUEST)
        return Response(programme_overview.build(admin, org, programme, cohort=cohort))


class AdminOverviewLayoutView(_AdminBase):
    """GET/PUT/DELETE `admin/scholarship/organisation/overview-layout/` — which Overview widgets an
    organisation shows, and in what order (Programme Overview phase 2, 2026-09-18).

    Edited from the Overview's Customise mode by the org admin; read by
    `programme_overview.build` for every role in the organisation as a NARROWING of what the
    role may see (`overview_layout.apply` — never a widening; `mine`/`qc` are pages, not
    widgets, and are not in the list at all).

    ⚠ THE ORGANISATION IS DERIVED, NEVER SENT — the `AdminOrganisationConfigurationView` fence,
    mirrored (same 404-not-403, same refusal to pick silently between two, `?org=` for a super).
    A third copy of `_gate`/`_organisation_for`; extracting a verb-less base for the three is
    noted as debt rather than done inside a feature sprint.

    Request #42 (2026-10-22): `?programme=<gift code>` reads and writes THAT GIFT's own layout
    (`ProgrammeOverviewLayout`), resolved by `_gift_narrowing` — another tenant's gift is a 404,
    a super may name any. A gift with no row serves the organisation's layout; `source` says
    which (`gift` | `organisation` | `default`). DELETE with `?programme=` removes the gift's row
    ("Use the organisation layout"); DELETE without it is a 400 `programme_required`. Without
    `?programme=` everything is as before: the organisation's layout, now the gifts' default.

    Who may write: `org_admin` and super — the layout changes what every colleague sees.

    PUT is ALL-OR-NOTHING: the body must be the FULL ordered list of the five widgets with a
    boolean each (`overview_layout.validate_sections`), refused with `{error, code, key}`; one
    `AUDIT overview_layout_set` line per save in the compact `funnel+,money-,…` form.

    tenancy: org-fenced on the derived organisation. Classified in test_org_fence.py.
    """

    ROLES = ('org_admin',)

    def _gate(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not self.has_role(admin, *self.ROLES):
            return None, self._deny_role()
        return admin, None

    def _organisation_for(self, admin, code):
        """Mirrors `AdminOrganisationConfigurationView._organisation_for` — see its docstring."""
        from apps.courses.models import PartnerOrganisation
        qs = PartnerOrganisation.objects.filter(is_active=True).tenants()
        if not self.has_role(admin, 'super'):
            org_id = admin.owning_organisation_id
            qs = qs.filter(id=org_id) if org_id else qs.none()
        if code:
            org = qs.filter(code=code).first()
            if org is None:
                return None, Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
            return org, None
        orgs = list(qs.order_by('code')[:2])
        if not orgs:
            return None, Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        if len(orgs) > 1:
            return None, Response(
                {'error': 'organisation_required', 'code': 'organisation_required',
                 'organisations': [o.code for o in qs.order_by('code')]},
                status=status.HTTP_400_BAD_REQUEST)
        return orgs[0], None

    def _scope(self, request, admin):
        """`(org, programme|None, error)`. With `?programme=<gift code>` the gift is resolved by
        `_gift_narrowing` (inside the caller's fence: another tenant's gift is a 404, a super may
        name any) and the organisation is the gift's owner; without it, the organisation is
        derived as before (`?org=` for a super)."""
        programme, err = self._gift_narrowing(request, admin)
        if err:
            return None, None, err
        if programme is not None:
            return programme.organisation, programme, None
        org, err = self._organisation_for(
            admin, (request.query_params.get('org') or '').strip())
        return org, None, err

    def _payload(self, org, programme=None):
        from .. import overview_layout
        from ..models import OrganisationOverviewLayout, ProgrammeOverviewLayout
        if programme is not None:
            sections, source = overview_layout.for_programme_with_source(programme)
            # org-fence: `programme` came through `_gift_narrowing` above.
            row = (ProgrammeOverviewLayout.objects.filter(programme=programme).first()
                   if source == 'gift' else
                   OrganisationOverviewLayout.objects.filter(organisation=org).first())
        else:
            sections, source = overview_layout.for_org_with_source(org)
            # org-fence: `org` is the derived organisation above.
            row = OrganisationOverviewLayout.objects.filter(organisation=org).first()
        return {
            'organisation': {'code': org.code, 'name': org.name},
            'programme': ({'code': programme.code, 'name': programme.name_en}
                          if programme is not None else None),
            # 'gift' (this gift's own) | 'organisation' | 'default' - request #42. The screen
            # shows "Use the organisation layout" only on 'gift'.
            'source': source,
            'sections': sections,
            'updated_by_email': row.updated_by_email if row else '',
            'updated_at': row.updated_at.isoformat() if row else None,
        }

    def get(self, request):
        admin, err = self._gate(request)
        if err:
            return err
        org, programme, err = self._scope(request, admin)
        if err:
            return err
        return Response(self._payload(org, programme))

    @staticmethod
    def _compact(sections):
        return ','.join(f"{s['key']}{'+' if s['on'] else '-'}" for s in sections)

    def put(self, request):
        from .. import overview_layout
        from ..models import OrganisationOverviewLayout, ProgrammeOverviewLayout

        admin, err = self._gate(request)
        if err:
            return err
        org, programme, err = self._scope(request, admin)
        if err:
            return err
        try:
            sections = overview_layout.normalised(request.data.get('sections'))
        except overview_layout.OverviewLayoutError as exc:
            return Response({'error': exc.code, 'code': exc.code, 'key': exc.key},
                            status=status.HTTP_400_BAD_REQUEST)
        by = admin.email or ''
        if programme is not None:
            was, source = overview_layout.for_programme_with_source(programme)
            # org-fence: as above. A gift's save writes ONLY the gift's row, never the org's.
            row, created = ProgrammeOverviewLayout.objects.get_or_create(
                programme=programme, defaults={'sections': sections, 'updated_by_email': by})
        else:
            was, source = overview_layout.for_org(org), None
            # org-fence: as above. ⚠ `defaults=` carries the list INTO the create: the model's
            # `save()` validates, and a row created empty first would be refused before the update.
            row, created = OrganisationOverviewLayout.objects.get_or_create(
                organisation=org, defaults={'sections': sections, 'updated_by_email': by})
        if not created:
            row.sections = sections
            row.updated_by_email = by
            row.save()
        # ⚠ A gift's FIRST save is always a change of state (it now has a layout of its own),
        # even when the list equals the organisation's it was showing - so it is audited.
        if was != sections or (programme is not None and source != 'gift'):
            gift = f' programme={programme.id}' if programme is not None else ''
            logger.info('AUDIT overview_layout_set org=%s%s was=%s now=%s by=%s',
                        org.code, gift, self._compact(was), self._compact(sections), by)
        return Response(self._payload(org, programme))

    def delete(self, request):
        """Request #42: "Use the organisation layout" - delete ONE GIFT's own layout, so the gift
        falls back to the organisation's. ⚠ Needs `?programme=`: without it this is a 400, never
        "delete the organisation's layout" (that is the default every gift falls back to)."""
        from .. import overview_layout
        from ..models import ProgrammeOverviewLayout

        admin, err = self._gate(request)
        if err:
            return err
        programme, err = self._gift_narrowing(request, admin)
        if err:
            return err
        if programme is None:
            return Response({'error': 'programme_required', 'code': 'programme_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        was, source = overview_layout.for_programme_with_source(programme)
        # org-fence: `programme` came through `_gift_narrowing`; only this gift's row goes.
        deleted, _ = ProgrammeOverviewLayout.objects.filter(programme=programme).delete()
        if deleted:
            logger.info('AUDIT overview_layout_reset org=%s programme=%s was=%s by=%s',
                        programme.organisation.code, programme.id,
                        self._compact(was) if source == 'gift' else '-', admin.email or '')
        return Response(self._payload(programme.organisation, programme))
