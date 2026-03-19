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
                        payload = jwt.decode(
                            token,
                            signing_key.key,
                            algorithms=[alg],
                            audience='authenticated',
                        )

                if payload:
                    # Attach user info to request
                    request.user_id = payload.get('sub')
                    request.supabase_user = {
                        'id': payload.get('sub'),
                        'email': payload.get('email'),
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
