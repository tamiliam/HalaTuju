"""
Proxy-aware rate throttles for HalaTuju.

HalaTuju runs behind Google Cloud Run, so
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
import ipaddress

from django.core.cache import cache
from rest_framework.throttling import SimpleRateThrottle


def forwarded_client_ip(request):
    """The caller's address as Cloud Run saw it: the RIGHTMOST ``X-Forwarded-For`` hop, else
    ``REMOTE_ADDR``, else None. ONE home for every reader (TD-514 / SEC-03, TD-429).

    Cloud Run (domain mapping, no load balancer, no Cloudflare) APPENDS the address it received
    the connection from to whatever ``X-Forwarded-For`` the client sent. So only the LAST hop is
    written by our side; every hop to its left is whatever the caller typed. Reading the first
    hop let a caller pick a new address per request (a fresh throttle bucket each time, and a
    made-up address on a signature). ``CF-Connecting-IP`` is not trusted for the same reason:
    nothing in front of us sets it, so only a caller could.
    """
    hops = [h.strip() for h in (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')]
    hops = [h for h in hops if h]
    if hops:
        return hops[-1]
    return request.META.get('REMOTE_ADDR') or None


def client_ip(request):
    """The throttle key's address (see ``forwarded_client_ip``), or 'unknown'. Throttling is
    best-effort abuse mitigation, not an auth boundary; what matters is that a caller cannot
    choose its own bucket and that distinct real clients are not lumped together."""
    return forwarded_client_ip(request) or 'unknown'


def throttle_key_ip(ip):
    """The address to use as a throttle / lockout KEY: an IPv6 address is cut to its /64 network
    (one home link owns a whole /64, so rotating addresses inside it must not buy a fresh bucket);
    IPv4 is unchanged. Bad or empty input comes back as given. Use ONLY for keys, never for
    evidence (signer_ip and audit logs keep the full address)."""
    try:
        addr = ipaddress.ip_address((ip or '').strip())
    except ValueError:
        return ip
    if addr.version == 6:
        if addr.ipv4_mapped:
            return str(addr.ipv4_mapped)
        return str(ipaddress.ip_network('%s/64' % addr, strict=False))
    return str(addr)


def throttle_ip(request):
    """``client_ip`` cut for use as a throttle key (see ``throttle_key_ip``)."""
    return throttle_key_ip(client_ip(request))


def take_slot(key, limit, seconds):
    """Use one of ``limit`` uses of ``key`` in a rolling ``seconds`` window. True = allowed.

    ATOMIC (SEC-08, A1.9): each use is its own cache entry ``<key>:<n>`` claimed with
    ``cache.add``, which only one caller can win (a unique row in the production DatabaseCache).
    A get-then-set counter let two parallel requests read the same count and both pass, and
    ``incr`` on the DatabaseCache is the same get-then-set. Each slot frees itself ``seconds``
    after it was taken, so no window ever holds more than ``limit`` uses. One read finds the free
    slots; a refusal consumes nothing.
    """
    names = ['%s:%d' % (key, n) for n in range(limit)]
    taken = cache.get_many(names)
    for name in names:
        if name not in taken and cache.add(name, 1, seconds):
            return True
    return False


def _ident(request):
    """Authenticated → the Supabase user id; otherwise the real client IP."""
    uid = getattr(request, 'user_id', None)
    if uid:
        return 'user:%s' % uid
    return 'ip:%s' % throttle_ip(request)


class ClientAnonRateThrottle(SimpleRateThrottle):
    """Generous global anti-scrape ceiling for ANONYMOUS traffic, keyed on the
    real client IP (not the shared proxy IP). Authenticated requests are not
    throttled by this class — they're protected per-endpoint where it matters."""
    scope = 'anon'

    def get_cache_key(self, request, view):
        if getattr(request, 'user_id', None):
            return None  # authenticated → this throttle does not apply
        return self.cache_format % {'scope': self.scope, 'ident': throttle_ip(request)}


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
        return self.cache_format % {'scope': self.scope, 'ident': throttle_ip(request)}

