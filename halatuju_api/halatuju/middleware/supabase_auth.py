"""
Supabase JWT Authentication Middleware.

Verifies JWT tokens issued by Supabase Auth and attaches user info to request.
"""
import logging
import jwt
from django.conf import settings
from django.http import JsonResponse
from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)


class SupabaseAuthMiddleware:
    """
    Middleware to verify Supabase JWT tokens.

    - Extracts Bearer token from Authorization header
    - Verifies signature using SUPABASE_JWT_SECRET
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
                # Verify and decode the JWT
                payload = jwt.decode(
                    token,
                    self.jwt_secret,
                    algorithms=['HS256'],
                    audience='authenticated',
                )

                # Attach user info to request
                request.user_id = payload.get('sub')
                request.supabase_user = {
                    'id': payload.get('sub'),
                    'email': payload.get('email'),
                    'phone': payload.get('phone'),
                    'role': payload.get('role'),
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


class SupabaseIsAuthenticated(BasePermission):
    """
    DRF permission class for class-based views that require Supabase auth.

    Returns 403 Forbidden if request.user_id is not set by the middleware.
    (DRF standard: 403 when no WWW-Authenticate header is configured.)
    """

    def has_permission(self, request, view):
        return request.user_id is not None
