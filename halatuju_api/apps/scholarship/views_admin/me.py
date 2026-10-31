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

Common profile S2 (2026-10-31): the GET also serves the person's card — `job_title`, `about`, `phone`,
`share_phone_with_team`, `share_phone_with_students`, `photo_url` (signed, ~1 h, only when a photo
exists; NEVER on `admin/role/`, which every page load reads) — and `PATCH admin/me/` writes it
(`AdminMeView.patch`); `POST / DELETE admin/me/photo/` change the photo (`AdminMePhotoView`).

Student maintenance S7a (2026-10-31): a MENTOR is opted in to all three (`mentor_methods`), and only a
mentor reads and writes `mentoring_area` — their own `Mentor.area`, required, at most 120 characters.
"Share my phone with students" and the phone being required follow `works_with_students` (a `review`
holder or a mentor; `staff_contact.py`).
"""
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from apps.courses import supabase_admin
from halatuju.middleware.supabase_auth import auth_sub
from halatuju.throttling import UploadRateThrottle

from .. import staff_photo
from ..staff_contact import new_profile_defaults, phone_refusal, works_with_students
from ..models import Mentor, StaffProfile
from .base import _AdminBase

#: What `PATCH admin/me/` may write, and nothing else (an unknown key is 400 `not_editable`, the
#: `admin/source/profile/` convention). `share_phone_with_students` only for somebody who works with
#: students (`works_with_students`); `mentoring_area` only for a mentor (S7a).
ME_FIELDS = ('name', 'job_title', 'about', 'phone', 'share_phone_with_team', 'share_phone_with_students',
             'mentoring_area')
ABOUT_MAX = 600
#: `Mentor.area`'s column width.
MENTORING_AREA_MAX = 120


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
    if not admin.is_super and admin.role in ('partner', 'mentor'):
        return []   # no gift work: a referral partner, or a mentor (S7a — mentoring is per scholar)
    if admin.programme_id and not admin.is_super:
        return [_named(admin.programme, lang)]
    return 'all'



def _profile_of(admin):
    return StaffProfile.objects.filter(partner_admin=admin).first()


def _card(profile):
    """The person's own card fields, blank when no profile row exists yet."""
    return {
        'job_title': getattr(profile, 'job_title', '') or '',
        'about': getattr(profile, 'about', '') or '',
        'phone': getattr(profile, 'phone', '') or '',
        'share_phone_with_team': bool(getattr(profile, 'share_phone_with_team', False)),
        'share_phone_with_students': bool(getattr(profile, 'share_phone_with_students', True)),
        'photo_url': staff_photo.signed_url(getattr(profile, 'photo_path', '')),
    }


def _card_text(value, limit, code):
    """`(clean, None)` or `(None, refusal)`: a string, stripped, at most `limit` characters."""
    if not isinstance(value, str):
        return None, _me_refusal('bad_request')
    value = value.strip()
    if len(value) > limit:
        return None, _me_refusal(code)
    return value, None


class AdminMeView(_AdminBase):
    """GET / PATCH /api/v1/admin/me/ — the caller's own account and card (see the module docstring).

    PATCH `{name?, job_title?, about?, phone?, share_phone_with_team?, share_phone_with_students?}`:
    only the keys sent are written. Refusals (400): `not_editable` + `fields` for any other key, or for
    `share_phone_with_students` from someone without `review`; `name_required`; `name_too_long`;
    `job_title_too_long` (120); `about_too_long` (600); `phone_too_long` (30, the column); and
    `phone_required` — a holder of `review` (or a mentor, S7a) must keep a phone (the onboarding
    rule), everybody else may clear theirs. The phone is otherwise stored as typed, exactly as the
    reviewer profile does. A source user's NAME saves here too (opted in, GET and PATCH). A MENTOR's
    `mentoring_area` too (S7a): `mentoring_area_required`, `mentoring_area_too_long` (120); any other
    role sending it is `not_editable`. Answers with the GET payload."""
    source_partner_methods = ('get', 'patch')
    mentor_methods = ('get', 'patch')

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        return Response(self._payload(request, admin))

    def patch(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        data = request.data if isinstance(request.data, dict) else None
        if data is None:
            return _me_refusal('bad_request')
        with_students = works_with_students(admin)
        refused = sorted(k for k in data if k not in ME_FIELDS
                         or (k == 'share_phone_with_students' and not with_students)
                         or (k == 'mentoring_area' and not admin.is_mentor))
        if refused:
            return _me_refusal('not_editable', fields=refused)
        clean = {}
        for key, limit in (('name', 200), ('job_title', 120), ('about', ABOUT_MAX), ('phone', 30),
                           ('mentoring_area', MENTORING_AREA_MAX)):
            if key in data:
                clean[key], bad = _card_text(data[key], limit, f'{key}_too_long')
                if bad:
                    return bad
        for key in ('share_phone_with_team', 'share_phone_with_students'):
            if key in data:
                if not isinstance(data[key], bool):
                    return _me_refusal('bad_request')
                clean[key] = data[key]
        if 'name' in clean and not clean['name']:
            return _me_refusal('name_required')
        if 'mentoring_area' in clean and not clean['mentoring_area']:
            return _me_refusal('mentoring_area_required')
        refused = phone_refusal(admin, clean)
        if refused is not None:
            return refused
        if 'name' in clean:
            admin.name = clean.pop('name')
            admin.save(update_fields=['name'])
        if 'mentoring_area' in clean:
            # The MENTOR's own record (S7a). Staff never write it; the login row names exactly one.
            Mentor.objects.filter(pk=admin.mentor_id).update(area=clean.pop('mentoring_area'))
        if clean:
            profile, _ = StaffProfile.objects.get_or_create(partner_admin=admin,
                                                            defaults=new_profile_defaults(admin))
            for key, value in clean.items():
                setattr(profile, key, value)
            profile.save(update_fields=[*clean, 'updated_at'])
        return Response(self._payload(request, admin))

    def _payload(self, request, admin):
        lang = (request.query_params.get('lang') or 'en').lower()
        if lang not in ('en', 'ms', 'ta'):
            lang = 'en'
        org = admin.owning_organisation if admin.owning_organisation_id else None
        return {
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
            **_card(_profile_of(admin)),
            # S7a: a mentor's own area of mentoring — for a mentor only (fresh read: a PATCH just
            # wrote it with an UPDATE).
            **({'mentoring_area': Mentor.objects.filter(pk=admin.mentor_id)
                .values_list('area', flat=True).first() or ''} if admin.is_mentor else {}),
        }


class AdminMePhotoView(_AdminBase):
    """POST / DELETE /api/v1/admin/me/photo/ — the caller's OWN photo (`apps/scholarship/staff_photo.py`).

    POST: multipart, ONE file (any field name). At most 2 MB; JPEG, PNG or WebP decided by the
    CONTENT; re-encoded to a metadata-free WebP of at most 512 x 512. Replacing a photo deletes the
    old object. Refusals (400): `no_file`, `one_file`, `too_large`, `not_an_image`,
    `unsupported_type`; 503 `storage_unavailable` when the bucket cannot take it (nothing changes).
    Throttled like a document upload (`UploadRateThrottle`). DELETE removes the object, then the
    path (503 and nothing changes if the object cannot be deleted). Both answer `{photo_url}`.
    Opted in for a source user, and for a mentor (S7a)."""
    source_partner_methods = ('post', 'delete')
    mentor_methods = ('post', 'delete')
    parser_classes = [MultiPartParser]
    throttle_classes = [UploadRateThrottle]

    def post(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        files = [f for name in request.FILES for f in request.FILES.getlist(name)]
        if not files:
            return _me_refusal('no_file')
        if len(files) > 1:
            return _me_refusal('one_file')
        upload = files[0]
        if upload.size > staff_photo.MAX_BYTES:
            return _me_refusal('too_large')
        profile, _ = StaffProfile.objects.get_or_create(partner_admin=admin,
                                                        defaults=new_profile_defaults(admin))
        try:
            key = staff_photo.replace(profile, upload.read())
        except staff_photo.PhotoError as e:
            return _me_refusal(e.code)
        if key is None:
            return _me_refusal('storage_unavailable', status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({'photo_url': staff_photo.signed_url(key)})

    def delete(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        profile = _profile_of(admin)
        if profile is not None and not staff_photo.remove(profile):
            return _me_refusal('storage_unavailable', status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({'photo_url': None})


def _me_refusal(code, http=status.HTTP_400_BAD_REQUEST, **extra):
    return Response({'error': code, 'code': code, **extra}, status=http)


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
    `weak_password` (the project's password policy), `wrong_current_password` (nothing more said); 429 `too_many_attempts` after five attempts in
    fifteen minutes (`supabase_admin.take_password_attempt`, atomic across workers and instances); 503 `supabase_unavailable` when Supabase cannot be asked — never
    a 500. Success sets the password (and, only when a temporary password is still owed, clears
    that flag in the same write — review H1), then signs every OTHER session out
    (`others_signed_out`: false when that could not be done — review M2).
    Opted in for a source user, and for a mentor (S7a), on POST only.
    """
    source_partner_methods = ('post',)
    mentor_methods = ('post',)

    def post(self, request):
        admin = self.get_admin(request)
        uid = auth_sub(request)
        if not admin or not uid:
            return self._deny()
        data = request.data if isinstance(request.data, dict) else {}
        current = data.get('current_password') or ''
        new = data.get('new_password') or ''
        if not isinstance(current, str) or not isinstance(new, str):
            return _me_refusal('bad_request')
        if not current:
            return _me_refusal('current_password_required')
        if len(new) < supabase_admin.MIN_PASSWORD_LENGTH:
            return _me_refusal('password_too_short')
        if new == current:
            return _me_refusal('same_password')
        unavailable = _me_refusal('supabase_unavailable', status.HTTP_503_SERVICE_UNAVAILABLE)
        account = supabase_admin.read_auth_user(uid)
        if not isinstance(account, dict) or not account.get('email'):
            return unavailable
        providers = (account.get('app_metadata') or {}).get('providers') or []
        if 'email' not in providers:
            return _me_refusal('no_password_sign_in')
        # Review fix M3: an ATOMIC per-person attempt count, taken before the password is tried.
        if not supabase_admin.take_password_attempt(uid):
            return _me_refusal('too_many_attempts', status.HTTP_429_TOO_MANY_REQUESTS)
        checked = supabase_admin.verify_password(account['email'], current)
        if checked is False:
            return _me_refusal('wrong_current_password')
        if checked is not True:
            return unavailable
        # Review fix H1: when a temporary password is still owed, the SAME write clears the flag, as
        # `AdminSetPasswordView` does — or the expiry job would later overwrite this password.
        written = supabase_admin.set_password(uid, new, account=account)
        if written == supabase_admin.WEAK_PASSWORD:
            return _me_refusal('weak_password')
        if written is not True:
            return unavailable
        # Review fix M2: every OTHER session ends; this tab keeps its own (`scope=others`).
        others = supabase_admin.sign_out_other_sessions(request.META.get('HTTP_AUTHORIZATION', ''))
        return Response({'ok': True, 'others_signed_out': others})
