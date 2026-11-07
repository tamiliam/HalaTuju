"""The caller's IP for a signature record — ONE home (review L4, source sign-in S4, 2026-10-30).

`forwarded_ip` is the address Cloud Run saw: since A1.9 (TD-429 / TD-514) the RIGHTMOST
`X-Forwarded-For` hop, which is the only one our side writes (`halatuju.throttling.forwarded_client_ip`,
shared with the throttles). It was the FIRST hop, which the caller types. With no header, `REMOTE_ADDR`.

⚠ For the columns that are `GenericIPAddressField` / Postgres `inet`: `valid_ip` turns a value that is
not an address into None, because Django does not validate on `save()` and Postgres would refuse it —
a forged header must not fail a signature.

Every signature now records `signer_ip` (TD-429, A1.9): the student's and the guarantor's signing, the
consent, the onboarding and promotional consents, the source's witness and the sponsor terms acceptance.
Before A1.9 the student's side recorded `REMOTE_ADDR` (the proxy's address behind Cloud Run).
"""
import ipaddress

from halatuju.throttling import forwarded_client_ip


def forwarded_ip(request):
    """Best-effort caller IP: the rightmost `X-Forwarded-For` hop, else `REMOTE_ADDR`, else None."""
    return forwarded_client_ip(request)


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
