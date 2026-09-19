"""
Supabase JWT Authentication Middleware.

Verifies JWT tokens issued by Supabase Auth and attaches user info to request.
Supports both HS256 (legacy JWT secret) and ES256 (JWKS-based signing keys).
"""
import logging
import jwt
from jwt import PyJWKClient
from django.conf import settings
from django.http import JsonResponse
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)

# JWKS client (caches keys automatically)
_jwks_client = None


def _get_jwks_client():
    """Lazy-initialised JWKS client for ES256 token verification."""
    global _jwks_client
    if _jwks_client is None:
        supabase_url = getattr(settings, 'SUPABASE_URL', '')
        if supabase_url:
            _jwks_client = PyJWKClient(f"{supabase_url}/auth/v1/.well-known/jwks.json")
    return _jwks_client


def auth_sub(request):
    """The REAL JWT subject of this request — never an alias target.

    ⚠ **STAFF AND SPONSOR IDENTITY MUST RESOLVE ON THIS, NEVER ON `request.user_id`.**
    `PartnerAdmin` and `Sponsor` key on the same Supabase uid as a student profile, so reading
    the aliased id would let a student's profile claim (TD-254) reach a console lookup. Falls
    back to `user_id` so a hand-built test request that sets only that still behaves.
    """
    return getattr(request, 'auth_sub', None) or getattr(request, 'user_id', None)


def is_staff_or_sponsor_sub(sub):
    """True when `sub` belongs to a `PartnerAdmin` or a `Sponsor`.

    ⚠ Such an identity may NEVER be redirected by a profile alias, and may never BE one
    (TD-254). This lives in the middleware rather than in `apps/courses` because it is the one
    place that legitimately has to see both apps — and because the app-boundary standard exists
    precisely to stop `courses` growing more edges into `scholarship`.
    """
    if not sub:
        return False
    from apps.courses.models import PartnerAdmin
    from apps.scholarship.models import Sponsor
    return (PartnerAdmin.objects.filter(supabase_user_id=sub).exists()
            or Sponsor.objects.filter(supabase_user_id=sub).exists())


def resolve_login_alias(sub):
    """The profile `sub` acts as: itself, unless a `ProfileLoginAlias` says otherwise (TD-254).

    ⚠ **THIS IS WHY A CLAIM NEEDS NO ENDPOINT CHANGES.** One row here redirects every
    authenticated student endpoint at once — including endpoints that do not exist yet, which
    is the half a per-endpoint fix could never cover.

    ⚠ **ONE INDEXED PRIMARY-KEY LOOK-UP PER AUTHENTICATED REQUEST, DELIBERATELY NOT CACHED.**
    A cache whose staleness outlived a revoked alias would keep a withdrawn login working, and
    revocation has to be instant — deleting the row IS the undo. (Query budgets arrive with
    sprint H18; this is a knowing, recorded entry.)

    Fails to the real sub on any error: the failure mode of this function must be "you are
    yourself", never "you are somebody else".
    """
    if not sub:
        return sub
    from apps.courses.models import ProfileLoginAlias
    try:
        target = (ProfileLoginAlias.objects.filter(alias_uid=sub)
                  .values_list('profile_id', flat=True).first())
    except Exception:
        logger.exception('Profile alias look-up failed; falling back to the real subject')
        return sub
    if not target or target == sub:
        return sub
    # A staff row can be created AFTER an alias (an admin is invited by email and backfilled on
    # first login), so the creation-time refusal is not the whole guard — re-check here. Costs
    # two queries only on the rare request that actually carries an alias.
    if is_staff_or_sponsor_sub(sub):
        logger.warning('Profile alias ignored: the subject is a staff or sponsor identity')
        return sub
    return target


class SupabaseAuthMiddleware:
    """
    Middleware to verify Supabase JWT tokens.

    - Extracts Bearer token from Authorization header
    - Verifies signature using HS256 (JWT secret) or ES256 (JWKS)
    - Attaches user_id to request object
    - Does NOT block unauthenticated requests (let views handle that)
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_secret = settings.SUPABASE_JWT_SECRET

    def __call__(self, request):
        # Initialize as anonymous
        request.user_id = None
        request.auth_sub = None
        request.supabase_user = None

        # Extract token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]  # Remove 'Bearer ' prefix

            try:
                # Check which algorithm the token uses
                header = jwt.get_unverified_header(token)
                alg = header.get('alg', 'HS256')

                if alg == 'HS256':
                    # Legacy: verify with JWT secret
                    payload = jwt.decode(
                        token,
                        self.jwt_secret,
                        algorithms=['HS256'],
                        audience='authenticated',
                    )
                else:
                    # ES256/RS256: verify with JWKS public key
                    jwks_client = _get_jwks_client()
                    if not jwks_client:
                        logger.warning("JWKS client not configured (SUPABASE_URL missing)")
                        payload = None
                    else:
                        signing_key = jwks_client.get_signing_key_from_jwt(token)
                        # Pin a fixed asymmetric allowlist rather than echoing the token's own
                        # alg header (TD audit 2026-06-14 — avoids any alg-confusion foot-gun).
                        payload = jwt.decode(
                            token,
                            signing_key.key,
                            algorithms=['ES256', 'RS256'],
                            audience='authenticated',
                        )

                if payload:
                    # Attach user info to request. email_verified gates admin email-backfill
                    # (TD audit 2026-06-14); Supabase carries it top-level or in user_metadata.
                    _um = payload.get('user_metadata') or {}
                    email_verified = bool(payload.get('email_verified', _um.get('email_verified', False)))
                    # ⚠ TWO IDENTITIES FROM HERE ON, AND THEY ARE NOT THE SAME THING.
                    # `auth_sub` is the REAL JWT subject — who is holding the token. `user_id`
                    # is WHICH STUDENT PROFILE that login acts as, which a `ProfileLoginAlias`
                    # may redirect (TD-254). Staff and sponsor identity resolve on `auth_sub`
                    # (see `auth_sub()` below); student data resolves on `user_id`.
                    request.auth_sub = payload.get('sub')
                    request.user_id = resolve_login_alias(request.auth_sub)
                    request.supabase_user = {
                        'id': payload.get('sub'),
                        'email': payload.get('email'),
                        'email_verified': email_verified,
                        'phone': payload.get('phone'),
                        'role': payload.get('role'),
                        'is_anonymous': payload.get('is_anonymous', False),
                    }
                    logger.debug(f"Authenticated user: {request.user_id}")

            except jwt.ExpiredSignatureError:
                logger.warning("JWT token expired")
                # Don't block - let the view decide how to handle

            except jwt.InvalidTokenError as e:
                logger.warning(f"Invalid JWT token: {e}")
                # Don't block - let the view decide how to handle

        response = self.get_response(request)
        return response


def require_auth(view_func):
    """
    Decorator for function-based views that require authentication.

    Usage:
        @require_auth
        def my_view(request):
            # request.user_id is guaranteed to be set
            ...
    """
    def wrapper(request, *args, **kwargs):
        if not request.user_id:
            return JsonResponse(
                {'error': 'Authentication required'},
                status=401
            )
        return view_func(request, *args, **kwargs)
    return wrapper


class SupabaseAuthentication(BaseAuthentication):
    """
    DRF authentication class that provides WWW-Authenticate header.

    Does not perform actual authentication (the middleware handles that).
    Its purpose is to make DRF return 401 instead of 403 for unauthenticated
    requests by providing the authenticate_header() method.
    """

    def authenticate(self, request):
        # Authentication is handled by SupabaseAuthMiddleware.
        # Return None to indicate this authenticator doesn't handle the request
        # (allows other authenticators or permission classes to decide).
        return None

    def authenticate_header(self, request):
        return 'Bearer'


class SupabaseIsAuthenticated(BasePermission):
    """
    DRF permission class for class-based views that require Supabase auth.

    Raises 401 Unauthorized if request.user_id is not set by the middleware.
    """

    def has_permission(self, request, view):
        if request.user_id is None:
            raise NotAuthenticated('Authentication required.')
        return True


# Endpoints that work without NRIC (identity establishment + admin)
# Exact-match paths checked with == ; prefix-match paths checked with startswith
NRIC_GATE_EXACT = [
    '/api/v1/profile/',           # GET to check NRIC status
    '/api/v1/profile/claim-nric/',# POST to claim NRIC
    # TD-254: the two challenge doors. A student with no NRIC of their own is EXACTLY who needs
    # them — gating these behind "you must already have an NRIC" would lock out the case.
    '/api/v1/profile/claim-nric/send-code/',
    '/api/v1/profile/claim-nric/confirm-code/',
    '/api/v1/sponsor-interest/',  # public sponsor-interest lead capture (no NRIC)
    '/api/v1/scholarship/intake/',# public "are applications open?" flag (no NRIC)
]
NRIC_GATE_PREFIX = [
    '/api/v1/admin/',             # All admin endpoints (prefix match)
    '/api/v1/sponsor/',          # Phase E: sponsor accounts (authenticated, but no NRIC — not students)
]


class NricGateMiddleware:
    """
    Hard gate: non-anonymous authenticated users MUST have NRIC
    to access any protected endpoint. Whitelist allows identity
    establishment endpoints through.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip if no auth (public endpoints) or anonymous user
        user_id = getattr(request, 'user_id', None)
        if not user_id:
            return self.get_response(request)

        supabase_user = getattr(request, 'supabase_user', None) or {}
        if supabase_user.get('is_anonymous', False):
            return self.get_response(request)

        # Skip whitelisted paths (exact match)
        path = request.path
        if path in NRIC_GATE_EXACT:
            return self.get_response(request)

        # Skip whitelisted paths (prefix match)
        for allowed in NRIC_GATE_PREFIX:
            if path.startswith(allowed):
                return self.get_response(request)

        # Check if user has NRIC
        from apps.courses.models import StudentProfile
        try:
            profile = StudentProfile.objects.only('nric').get(
                supabase_user_id=user_id
            )
            if not profile.nric:
                return JsonResponse(
                    {'error': 'NRIC verification required', 'code': 'nric_required'},
                    status=403
                )
        except StudentProfile.DoesNotExist:
            return JsonResponse(
                {'error': 'NRIC verification required', 'code': 'nric_required'},
                status=403
            )

        return self.get_response(request)
