"""
Proxy-aware rate throttles for HalaTuju.

HalaTuju runs behind Google Cloud Run (and may sit behind Cloudflare), so
``request.META['REMOTE_ADDR']`` is the *proxy* IP, not the visitor's. DRF's
stock throttles would therefore bucket every anonymous visitor under that one
proxy IP and could rate-limit the whole public site as a single client. These
throttles instead resolve the real client IP, and key authenticated requests on
the Supabase user id (``request.user_id``, set by ``SupabaseAuthMiddleware``) —
this project does not populate Django's ``request.user``.

Rates live in ``settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']``.
Limits are deliberately generous: the goal is to stop runaway scraping/abuse
and protect the billable Vision-OCR upload path, NOT to police normal use
(shared school/library NATs put many real students behind one IP).
"""
from rest_framework.throttling import SimpleRateThrottle


def client_ip(request):
    """Best-effort real client IP behind the Cloudflare/Cloud Run proxy chain.

    Order: Cloudflare's ``CF-Connecting-IP`` (if ever fronted by CF) → the first
    hop of ``X-Forwarded-For`` (Cloud Run sets ``client, proxy1, ...``) →
    ``REMOTE_ADDR`` as a last resort. Throttling is best-effort abuse mitigation,
    not an auth boundary, so an occasional imperfect read is acceptable — what
    matters is that distinct real clients get distinct buckets (never lumped).
    """
    cf = request.META.get('HTTP_CF_CONNECTING_IP')
    if cf:
        return cf.strip()
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or 'unknown'


def _ident(request):
    """Authenticated → the Supabase user id; otherwise the real client IP."""
    uid = getattr(request, 'user_id', None)
    if uid:
        return 'user:%s' % uid
    return 'ip:%s' % client_ip(request)


class ClientAnonRateThrottle(SimpleRateThrottle):
    """Generous global anti-scrape ceiling for ANONYMOUS traffic, keyed on the
    real client IP (not the shared proxy IP). Authenticated requests are not
    throttled by this class — they're protected per-endpoint where it matters."""
    scope = 'anon'

    def get_cache_key(self, request, view):
        if getattr(request, 'user_id', None):
            return None  # authenticated → this throttle does not apply
        return self.cache_format % {'scope': self.scope, 'ident': client_ip(request)}


class UploadRateThrottle(SimpleRateThrottle):
    """Caps document uploads — each one triggers a billable Vision-OCR call and
    a storage write. Only mutating requests (POST/PUT) are counted; reading the
    document list (GET) is free. Keyed on the Supabase user id (falls back to
    client IP)."""
    scope = 'upload'

    def get_cache_key(self, request, view):
        if request.method not in ('POST', 'PUT'):
            return None  # listing/reading documents is not rate-limited
        return self.cache_format % {'scope': self.scope, 'ident': _ident(request)}


class PublicCountRateThrottle(SimpleRateThrottle):
    """Modest per-client cap on the public (AllowAny) sponsor-count endpoint."""
    scope = 'public_count'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': client_ip(request)}
