"""`GET admin/me/` — the signed-in person's own account, for the common Profile page (2026-10-31).

Common profile S1 (roadmap `docs/plans/2026-10-31-common-profile-roadmap.md`). One payload every
admin-platform person reads about THEMSELVES — staff of every role and a source user alike — so the
Profile page's "Your access" and "Sign-in" cards need no per-role endpoint:

    {id, name, email, role, is_super, organisation: {id, name} | null, source: {id, name} | null,
     referral_partner: {name} | null, programmes: [{id, code, name}] | 'all', permissions: [...],
     first_seen_at, last_seen_at}

⚠ WHY THIS LIVES IN `apps.scholarship`, NOT `apps.courses` (the roadmap first said `courses`). A
source user's gifts come from `source_access.programmes_for`, a scholarship rule, and the
`courses -> scholarship` import count sits AT its budget (17 of 17, `test_code_standards.py`): a
courses view would have needed one more cross-app import. The scholarship app already reads
`apps.courses` freely, so the view sits here and the boundary does not move.

⚠ SELF-SCOPED, AND OPTED IN FOR A SOURCE USER (`source_partner_methods`, deny by default). It
reads only the caller's own row (`get_admin` on the JWT subject) and writes nothing; the source's
programme list is the same one its scope switcher already serves (`AdminScopeListView`).
`permissions` is the RESOLVED set (`PartnerAdmin.permission_set`), the one `admin/role/` serves.
"""
from rest_framework.response import Response

from .base import _AdminBase


def _named(p, lang):
    """A gift as the page lists it: the trilingual name with the en fallback (`AdminScopeListView`)."""
    return {'id': p.id, 'code': p.code, 'name': getattr(p, f'name_{lang}', '') or p.name_en}


def programmes_of(admin, lang='en'):
    """The gifts this person works within: a list, or `'all'` for every gift their organisation runs.

    super / org-wide staff with no gift binding → 'all'; staff bound to ONE gift
    (`PartnerAdmin.programme`, a narrowing, never a fence) → that gift; a source user → the gifts
    `source_access` lets it see; a referral partner → [] (it has no gift work at all, the answer
    `AdminScopeListView` gives it too).
    """
    if admin.is_source_user:
        from .. import source_access
        return [_named(p, lang) for p in source_access.programmes_for(admin).order_by('code')]
    if not admin.is_super and admin.role == 'partner':
        return []
    if admin.programme_id and not admin.is_super:
        return [_named(admin.programme, lang)]
    return 'all'


class AdminMeView(_AdminBase):
    """GET /api/v1/admin/me/ — the caller's own account (see the module docstring)."""
    source_partner_methods = ('get',)

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        lang = (request.query_params.get('lang') or 'en').lower()
        if lang not in ('en', 'ms', 'ta'):
            lang = 'en'
        org = admin.owning_organisation if admin.owning_organisation_id else None
        return Response({
            'id': admin.id,
            'name': admin.name,
            'email': admin.email,
            'role': 'super' if admin.is_super else admin.role,
            'is_super': admin.is_super,
            'organisation': {'id': org.id, 'name': org.name} if org else None,
            'source': ({'id': admin.source_id, 'name': admin.source.name}
                       if admin.source_id else None),
            'referral_partner': {'name': admin.org.name} if admin.org_id else None,
            'programmes': programmes_of(admin, lang),
            'permissions': list(admin.permission_set),
            'first_seen_at': admin.first_seen_at,
            'last_seen_at': admin.last_seen_at,
        })
