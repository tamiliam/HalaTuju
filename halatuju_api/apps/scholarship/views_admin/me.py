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

`POST admin/me/password/` — the signed-in person changes their OWN password (see `AdminMePasswordView`).
"""
from rest_framework import status
from rest_framework.response import Response

from apps.courses import supabase_admin
from halatuju.middleware.supabase_auth import auth_sub
from halatuju.throttling import PasswordChangeRateThrottle

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


def _password_refusal(code, http=status.HTTP_400_BAD_REQUEST):
    return Response({'error': code, 'code': code}, status=http)


class AdminMePasswordView(_AdminBase):
    """POST /api/v1/admin/me/password/ `{current_password, new_password}` — a signed-in person
    changes their OWN password (common profile S1, 2026-10-31; the Profile page's Sign-in card).

    ⚠ WHY SERVER-SIDE. The project refuses a client `updateUser({password})` ("Current password
    required", `app/admin/set-password`), so the browser cannot do this itself. And it is NOT
    `admin/set-password/`: that endpoint sets a password with no current one, and is open only while
    a temporary password is owed or a recovery link was just followed (TD-207, TD-322). Here the
    current password IS the proof, checked by a password grant against the caller's own account.

    ⚠ THE ACCOUNT IS THE JWT'S, NEVER THE BODY'S. The user id is `auth_sub`; the email checked is the
    one Supabase holds for that id (read with the service role). Any `email` / `user_id` in the body
    is ignored. Refusals: 400 `current_password_required`, `password_too_short` (the shared
    `MIN_PASSWORD_LENGTH`), `same_password`, `no_password_sign_in` (a Google-only account),
    `weak_password` (the project's password policy), `wrong_current_password` (nothing more said); 429 after about five attempts in fifteen minutes
    (`PasswordChangeRateThrottle`); 503 `supabase_unavailable` when Supabase cannot be asked — never
    a 500. Success sets the password only (no metadata: `must_change_password` is untouched).
    Opted in for a source user, on POST only.
    """
    source_partner_methods = ('post',)
    throttle_classes = [PasswordChangeRateThrottle]

    def post(self, request):
        admin = self.get_admin(request)
        uid = auth_sub(request)
        if not admin or not uid:
            return self._deny()
        data = request.data if isinstance(request.data, dict) else {}
        current = data.get('current_password') or ''
        new = data.get('new_password') or ''
        if not isinstance(current, str) or not isinstance(new, str):
            return _password_refusal('bad_request')
        if not current:
            return _password_refusal('current_password_required')
        if len(new) < supabase_admin.MIN_PASSWORD_LENGTH:
            return _password_refusal('password_too_short')
        if new == current:
            return _password_refusal('same_password')
        unavailable = _password_refusal('supabase_unavailable', status.HTTP_503_SERVICE_UNAVAILABLE)
        account = supabase_admin.read_auth_user(uid)
        if not isinstance(account, dict) or not account.get('email'):
            return unavailable
        providers = (account.get('app_metadata') or {}).get('providers') or []
        if 'email' not in providers:
            return _password_refusal('no_password_sign_in')
        checked = supabase_admin.verify_password(account['email'], current)
        if checked is False:
            return _password_refusal('wrong_current_password')
        if checked is not True:
            return unavailable
        written = supabase_admin.set_password(uid, new)
        if written == supabase_admin.WEAK_PASSWORD:
            return _password_refusal('weak_password')
        if written is not True:
            return unavailable
        return Response({'ok': True})
