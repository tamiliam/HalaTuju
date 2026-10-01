"""Supabase Auth admin calls for the partner-invite flow (moved from `views_admin.py`, TD-160).

`_service_headers` and `_create_supabase_user` moved here verbatim so the invite fix could be
built without growing `views_admin.py` past its size allowance. `views_admin` imports both back
under the same names, so every caller (`expire_temp_passwords` included) still resolves them
there. Tests patch `apps.courses.views_admin.http_requests.post` - that is the `requests`
module itself, the same object this module calls, so those patches still bite here.
"""
import logging

import requests as http_requests
from django.utils import timezone

logger = logging.getLogger(__name__)


def _service_headers(service_role_key):
    return {
        'apikey': service_role_key,
        'Authorization': f'Bearer {service_role_key}',
        'Content-Type': 'application/json',
    }


def _create_supabase_user(supabase_url, service_role_key, email, name, temp_password):
    """Create the partner's Supabase auth account directly, with a password we choose.

    We deliberately do NOT use /auth/v1/invite: its email carries a magic link that expires in 24
    hours (Supabase's maximum) and cannot be re-sent to an address that already has an auth user,
    so a partner who missed the window was permanently stuck. Creating the account outright means
    nothing expires, and we send our own email instead.

    `email_confirm` is load-bearing: PartnerAdminMixin.get_admin only links a PartnerAdmin row by
    email when the JWT's `email_verified` claim is true. Without it the partner would sign in
    successfully and still have no role.

    Returns (user_id, already_registered, error). `already_registered` means the address already
    had a HalaTuju account (student or Google) — not a failure: they keep their existing login and
    we just grant the role, matching them by verified email on next sign-in.
    """
    resp = http_requests.post(
        f'{supabase_url}/auth/v1/admin/users',
        json={
            'email': email,
            'password': temp_password,
            'email_confirm': True,
            # `temp_password_issued_at` starts the 7-day clock: the login gate refuses an unchanged
            # temp password past the TTL, and the daily `expire_temp_passwords` job rotates it dead.
            'user_metadata': {'name': name, 'must_change_password': True,
                              'temp_password_issued_at': timezone.now().isoformat()},
        },
        headers=_service_headers(service_role_key),
    )
    if resp.status_code in (200, 201):
        try:
            user_id = (resp.json() or {}).get('id')
        except ValueError:
            user_id = None
        if not user_id:
            # ⚠ TD-160: created, but the body gave us no UID. A row stored without one is never
            # rotated by Resend (no UID reads as "an account we did not create"), so ask for the
            # account back by email before the caller writes the row.
            user_id = _read_back_user_id(supabase_url, service_role_key, email)
        if not user_id:
            # Still nothing. The row is stored anyway (the account exists and the email carries
            # its password); the email-match backfill links it on first sign-in. Until then a
            # Resend sends the "sign in as usual" note and rotates nothing — say so loudly.
            logger.warning('Partner invite: Supabase created %s but no user id could be read '
                           '(TD-160); the admin row is stored WITHOUT supabase_user_id, so Resend '
                           'will not rotate its password until their first sign-in.', email)
        return user_id, False, None

    try:
        body = resp.json() or {}
    except ValueError:
        body = {}
    if resp.status_code in (400, 422) and (
        body.get('error_code') == 'email_exists' or body.get('code') == 'email_exists'
        or 'already been registered' in str(body.get('msg', ''))
    ):
        return None, True, None

    logger.error('Supabase user creation failed: %s %s', resp.status_code, resp.text)
    return None, False, 'create_failed'


def _read_back_user_id(supabase_url, service_role_key, email):
    """The UID of the auth account at ``email``, read back through the admin API — or None.

    TD-160. Used only when a create answered 2xx without a readable id. GoTrue's admin user list
    takes a ``filter`` that matches by substring, so the answer is accepted only when EXACTLY ONE
    returned user has this exact address (case-insensitive) — a near-miss is not our account.
    Best-effort: any failure is None, never raised (the caller logs the outcome).
    """
    try:
        resp = http_requests.get(
            f'{supabase_url}/auth/v1/admin/users',
            params={'filter': email, 'per_page': 50},
            headers=_service_headers(service_role_key), timeout=15,
        )
        if resp.status_code != 200:
            return None
        body = resp.json() or {}
        users = body.get('users') if isinstance(body, dict) else None
        wanted = (email or '').strip().lower()
        ids = [u.get('id') for u in users or []
               if isinstance(u, dict) and u.get('id')
               and (u.get('email') or '').strip().lower() == wanted]
        return ids[0] if len(ids) == 1 else None
    except Exception:
        logger.warning('Partner invite: read-back of %s failed', email, exc_info=True)
        return None
