"""Referral partners: list, mark and unmark — SUPER ONLY (sources-and-referrals Sprint D, 2026-10-19).

Roadmap item 1b. Until now marking an existing `partner_organisations` row a referral partner was a
reviewed SQL update. It is a platform decision — a referral partner's `?ref=` link puts students
on the list its `partner` logins read (NRIC, phone, address, income) — so only a super takes it,
and the rules live in ONE place, `referral_links.mark_refusal`. Its own module: `views_admin.py`
is in the oversize ledger.

- `GET  /api/v1/admin/referral-partners/` — every row that could be or is a referral partner:
  NEVER a tenant (an organisation that runs gifts is another category). Each row says whether it
  is marked, switched on, and how many active `partner` logins it has.
- `PATCH /api/v1/admin/referral-partners/<id>/` `{is_referral_partner: bool}` — mark / unmark;
  a refusal is 400 with its code and a sentence (`MARK_REFUSALS`). Logged as an AUDIT line.

No screen yet (TD-387): a new screen needs its Stitch prototype and new strings, and en.json is at
its bundle line (TD-360).
"""
import logging

from django.db.models import Count, Q
from rest_framework.response import Response
from rest_framework.views import APIView

from . import referral_links
from .models import PartnerOrganisation
from .views_admin import PartnerAdminMixin

logger = logging.getLogger('apps.courses.views_referral_partners')


def _row(org, logins):
    return {'id': org.pk, 'code': org.code, 'name': org.name, 'is_active': org.is_active,
            'is_referral_partner': org.is_referral_partner, 'partner_logins': logins}


class _SuperOnly(PartnerAdminMixin, APIView):
    def _super(self, request):
        admin = self.get_admin(request)
        return admin if admin is not None and admin.is_super else None


class AdminReferralPartnerListView(_SuperOnly):
    def get(self, request):
        if self._super(request) is None:
            return Response({'error': 'Super admin access required'}, status=403)
        rows = (PartnerOrganisation.objects
                .exclude(pk__in=PartnerOrganisation.objects.tenants().values('pk'))
                .annotate(logins=Count('admins', filter=Q(admins__role='partner',
                                                          admins__is_active=True)))
                .order_by('-is_referral_partner', '-is_active', 'name'))
        return Response({'organisations': [_row(o, o.logins) for o in rows]})


class AdminReferralPartnerDetailView(_SuperOnly):
    def patch(self, request, org_id):
        admin = self._super(request)
        if admin is None:
            return Response({'error': 'Super admin access required'}, status=403)
        value = request.data.get('is_referral_partner')
        if not isinstance(value, bool):
            return Response({'error': 'is_referral_partner must be true or false',
                             'code': 'bad_value'}, status=400)
        org = PartnerOrganisation.objects.filter(pk=org_id).first()
        if org is None:
            return Response({'error': 'Organisation not found', 'code': 'org_not_found'}, status=404)
        refusal = referral_links.mark_refusal(org, value)
        if refusal:
            return Response({'error': referral_links.MARK_REFUSALS[refusal], 'code': refusal},
                            status=400)
        if org.is_referral_partner != value:
            org.is_referral_partner = value
            org.save(update_fields=['is_referral_partner'])
            logger.info('AUDIT referral_partner_%s org_id=%s by_admin=%s',
                        'marked' if value else 'unmarked', org.pk, admin.pk)
        logins = org.admins.filter(role='partner', is_active=True).count()
        return Response(_row(org, logins))
