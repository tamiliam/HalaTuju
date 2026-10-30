"""The caller's IP for a signature record — ONE home (review L4, source sign-in S4, 2026-10-30).

`forwarded_ip` is the sponsor terms acceptance's rule, moved here unchanged from
`views_sponsor._client_ip` (which now calls it): Cloud Run sits behind a proxy, so the FIRST
`X-Forwarded-For` hop is the real client; with no header, `REMOTE_ADDR`.

⚠ ONE ADDITION, for the columns that are `GenericIPAddressField` / Postgres `inet`: `valid_ip` turns a
value that is not an address into None, because Django does not validate on `save()` and Postgres
would refuse it — a forged header must not fail a signature. The sponsor acceptance does not call it
(its behaviour is unchanged on purpose; see TD-429).

⚠ The student's and the guarantor's signing still record `REMOTE_ADDR` — the proxy's address behind
Cloud Run (TD-429). Left alone here: changing it changes what the student's record says.
"""
import ipaddress


def forwarded_ip(request):
    """Best-effort caller IP: the first `X-Forwarded-For` hop, else `REMOTE_ADDR`, else None."""
    fwd = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip()
    return fwd or request.META.get('REMOTE_ADDR') or None


def valid_ip(value):
    """``value`` when it is an IPv4 / IPv6 address, else None."""
    try:
        ipaddress.ip_address(value)
    except (TypeError, ValueError):
        return None
    return value


def signer_ip(request):
    """The forwarded IP, kept only when it is an address (for an `inet` column)."""
    return valid_ip(forwarded_ip(request))
