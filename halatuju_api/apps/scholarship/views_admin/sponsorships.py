"""A sponsor's detail page, its memberships, its award amounts and its sponsorships.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.
"""
import logging

from rest_framework import status
from rest_framework.response import Response
from .. import pool
from ..models import Sponsor, Sponsorship
from ..serializers_admin import AdminApplicationDetailSerializer
from .. import sponsorship as sponsorship_service

from .base import _AdminBase
from .gift_programmes import AdminProgrammeListView

from .sponsors import _SponsorScope, _sponsor_detail_dict


# ⚠ THE PACKAGE'S name, spelled out — never `__name__`. A submodule logger reads
# `apps.scholarship.views_admin.<module>` and drops every audit line it carries out
# of the Cloud Logging scrape metric. Guarded by `AuditLoggerNameTest` (H11).
logger = logging.getLogger('apps.scholarship.views_admin')


class AdminSponsorDetailView(_AdminBase):
    """GET .../admin/sponsors/<pk>/ — everything an admin needs about ONE sponsor.

    Same role gate as the list (super / org_admin / admin / finance). The ACCOUNT is
    platform-level and shown whole; the money and the students are org-fenced — see
    `_sponsor_detail_dict`.
    """
    def get(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not (admin.is_super or admin.role in ('org_admin', 'admin', 'finance')):
            return self._deny_role()
        sponsor = Sponsor.objects.filter(pk=pk).first()
        if sponsor is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        scope = _SponsorScope(sponsor, admin.owning_organisation_id,
                              self.has_role(admin, 'super'))
        return Response(_sponsor_detail_dict(sponsor, admin, scope))


class AdminSponsorMembershipView(_AdminBase):
    """POST .../admin/sponsors/<pk>/membership/ {programme_id, status} — accept a benefactor into
    one of THIS organisation's gifts, or take it back (S-ASSIGN, 2026-09-04).

    ⚠ THIS IS THE ENDPOINT THAT UNBLOCKS THE MONEY. `record_admin_credit` refuses
    `sponsor_not_in_programme` unless an approved membership exists, and until now the only writer
    was `sync_account_membership` with a hard-coded `'brightpath-flagship'`. A second gift's first
    benefactor could not be recorded without an engineer writing SQL — the one thing the owner's
    acceptance test forbids.

    ⚠ TWO GATES, AND THIS IS ONLY THE SECOND. `Sponsor.status` is the ACCOUNT gate ("is this a real,
    legitimate person"), settled once, platform-wide, by `AdminSponsorReviewView`. This is the
    per-gift acceptance, and the owner's rule is that a sponsor sees a gift's students only if
    *"specifically onboarded into both and accepted into both — and that is not a given"*. The
    service refuses `account_not_approved` rather than letting a row say yes while the account
    says no.

    ⚠ THE FENCE IS THE PROGRAMME'S ORGANISATION, resolved through `_ProgrammeScopedBase`'s own
    `_programmes_for`, so a cross-org gift is **404, never 403** — a 403 would confirm the tenant
    exists. The SPONSOR is deliberately unfenced: an account is platform-level by design (one
    login, one identity, one vetting), which is exactly why the money and the students hanging off
    it are fenced instead.

    Who may write: `super` and `org_admin`. Deciding who may fund your students is the
    organisation's own decision, held by its administrator — the same gate as sponsor vetting, one
    role narrower than the sponsor LIST (which `admin` and `finance` also read).
    """
    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not (admin.is_super or self.has_role(admin, 'org_admin')):
            return self._deny_role()

        sponsor = Sponsor.objects.filter(pk=pk).first()
        if sponsor is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        # Reuse the programme fence rather than re-deriving it — `_programmes_for` already answers
        # "which gifts may this admin touch", INCLUDING inactive ones, which matters here: a gift
        # is configured and staffed before it is switched on.
        programmes = AdminProgrammeListView()._programmes_for(admin)
        programme = programmes.filter(pk=request.data.get('programme_id')).first()
        if programme is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            m = sponsorship_service.set_programme_membership(
                sponsor, programme, (request.data.get('status') or '').strip(),
                vetted_by=admin.email or '')
        except sponsorship_service.MembershipError as e:
            code = str(e)
            return Response({'error': code, 'code': code}, status=status.HTTP_400_BAD_REQUEST)

        logger.info('AUDIT sponsor_membership_set sponsor=%s programme=%s status=%s by=%s',
                    sponsor.id, programme.code, m.status, admin.email or '')
        return Response({'programme_id': programme.id, 'programme': programme.code,
                         'status': m.status})


class AdminSetAwardAmountView(_AdminBase):
    """POST .../applications/<pk>/award-amount/ {amount} — OVERRIDE the standardised
    assistance amount. SUPER-ONLY (owner decision 2026-06-29: reviewers no longer set the
    amount; it's fixed by pathway via the award rule and auto-applied on approve). A super
    may adjust it to one of the allowed slider stops (RM1,000–3,000 in RM500 steps), or
    clear it with null/blank. Gates fundability + shows on the anonymised pool card."""
    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'super'):
            return self._deny_role()
        app, _err = self._scoped_application(request, pk)
        if _err:
            return _err
        from decimal import Decimal, InvalidOperation
        from .. import award as award_rule
        raw = request.data.get('amount')
        try:
            amount = Decimal(str(raw)) if raw not in (None, '') else None
        except (InvalidOperation, TypeError):
            return Response({'error': 'invalid_amount'}, status=status.HTTP_400_BAD_REQUEST)
        # A set value must be one of the permitted slider stops (clearing is allowed).
        if amount is not None and not award_rule.is_allowed_amount(amount):
            return Response({'error': 'invalid_amount'}, status=status.HTTP_400_BAD_REQUEST)
        app.award_amount = amount
        app.save(update_fields=['award_amount'])
        return Response(AdminApplicationDetailSerializer(app).data)


def _sponsorship_dict(s):
    profile = getattr(s.application, 'profile', None)
    return {
        'id': s.id, 'status': s.status, 'amount': str(s.amount),
        'offered_at': s.offered_at, 'accept_deadline': s.accept_deadline, 'decided_at': s.decided_at,
        # Admin oversight sees BOTH sides (not anonymised) — this is the back office.
        'sponsor': {'id': s.sponsor_id, 'name': s.sponsor.name, 'email': s.sponsor.email},
        'application': {
            'id': s.application_id,
            'name': (getattr(profile, 'name', '') or '') if profile else '',
            'ref': pool.pool_ref(s.application_id),
        },
    }


class AdminSponsorshipListView(_AdminBase):
    """Phase E3: GET .../admin/sponsorships/[?status] — oversight of all matches
    (sponsor ↔ student + amount + status)."""
    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        # org-fence: _org_scoped on the application join, applied below.
        qs = (Sponsorship.objects.select_related('sponsor', 'application', 'application__profile')
              .order_by('-id'))  # deterministic ordering (TD audit 2026-06-14)
        qs = self._org_scoped(qs, admin, field='application__owning_organisation_id')
        st = request.query_params.get('status')
        if st:
            qs = qs.filter(status=st)
        return Response({'sponsorships': [_sponsorship_dict(s) for s in qs]})
