"""Public per-org branding endpoint (platform Sprint 6, decision D1).

``GET /api/v1/branding/<code>/`` returns the 8 brand strings the web app needs to render a
tenant's identity (programme name, coach persona, short name, colour, logo, support/sponsor
addresses, display domain). It is PUBLIC (a pre-login page reads it) and TOTAL — an unknown,
inactive or garbage code resolves to the PLATFORM payload, never a 404, so there is no
enumeration oracle and no student data is ever reachable (the response is 8 fixed keys of brand
copy only).

BrightPath (env unset / code 'brightpath') resolves to the platform block, so the endpoint
returns today's constants; the web app in platform mode never even calls this (zero flash).

Precedent: ``SponsorPoolCountView`` — AllowAny + the public-count throttle.
"""
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import PartnerOrganisation
from halatuju.throttling import PublicCountRateThrottle

from . import branding

_LANGS = ('en', 'ms', 'ta')


def _org_by_code(code):
    """Resolve a URL code to an ACTIVE tenant org, or None. Total: any lookup problem (missing,
    inactive, DB hiccup, or the platform code itself) → None → the platform branding."""
    if not code or code == branding.PLATFORM_ORG_CODE:
        return None
    try:
        return PartnerOrganisation.objects.filter(code=code, is_active=True).first()
    except Exception:
        return None


class BrandingView(APIView):
    """GET /api/v1/branding/<code>/ — PUBLIC, tenant brand strings only (no student data).

    Registered beside ``sponsor/pool/count/`` with the same public rails (AllowAny + throttle).
    The response is an EXACT key-set: programme_name/persona_name (each en/ms/ta), org_short_name,
    brand_colour, logo_url, email_support, sponsor_email, frontend_domain."""
    permission_classes = [AllowAny]
    throttle_classes = [PublicCountRateThrottle]

    def get(self, request, code):
        b = branding.for_organisation(_org_by_code(code))
        return Response({
            'programme_name': {lang: b.programme_name(lang) for lang in _LANGS},
            'persona_name': {lang: b.persona_name(lang) for lang in _LANGS},
            'org_short_name': b.org_short_name,
            'brand_colour': b.brand_colour,
            'logo_url': b.logo_url,
            'email_support': b.email_support,
            'sponsor_email': b.sponsor_reply_to,
            'frontend_domain': b.frontend_domain,
        })
