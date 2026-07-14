"""Expire (rotate) a partner's temporary password once it has gone unchanged past the TTL.

The partner-onboarding flow (2026-07-12) creates a Supabase account with a temp password that,
by design, does not expire natively — that durability is the whole point (the old Supabase invite
LINK expired in 24h and stranded people). The owner asked (2026-07-14) for a 7-day cap on the
UNUSED temp password specifically, without re-introducing that dead-end: recovery stays one click
(the owner presses Resend, which re-issues a fresh password AND a fresh 7-day clock).

Supabase has no password TTL, so this daily job IS the real boundary: for every partner whose temp
password is still unchanged (`must_change_password` true) and was issued more than the TTL ago, it
rotates the Supabase password to a long random value that is never emailed — so the emailed password
stops working everywhere, not just in the UI. A partner who has already set their own password
(`must_change_password` false) is never touched.

Scoped to PartnerAdmin rows (a handful of partners/reviewers), NOT the whole Supabase user base —
we only read/rotate accounts WE provisioned. Inert without Supabase config. Never raises into the
cron (it logs + continues).
"""
import datetime
import logging

import requests as http_requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.courses.views_admin import _service_headers, generate_temp_password

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Rotate partner temp passwords still unchanged after PARTNER_TEMP_PASSWORD_TTL_DAYS (default 7)."

    def handle(self, *args, **options):
        url = getattr(settings, 'SUPABASE_URL', '') or ''
        key = getattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', '') or ''
        if not url or not key:
            self.stdout.write('expire_temp_passwords: Supabase not configured — inert')
            return
        days = int(getattr(settings, 'PARTNER_TEMP_PASSWORD_TTL_DAYS', 7))
        cutoff = timezone.now() - datetime.timedelta(days=days)
        headers = _service_headers(key)

        checked = expired = 0
        # Only accounts WE created carry a temp password (a Google / already-registered invitee has
        # supabase_user_id=None and never had one).
        for admin in PartnerAdmin.objects.filter(supabase_user_id__isnull=False, is_active=True):
            checked += 1
            uid = admin.supabase_user_id
            try:
                r = http_requests.get(f'{url}/auth/v1/admin/users/{uid}', headers=headers, timeout=15)
                if r.status_code != 200:
                    continue
                meta = (r.json() or {}).get('user_metadata') or {}
            except Exception:  # noqa: BLE001 — one bad user must not stop the sweep
                logger.warning('expire_temp_passwords: could not read user %s', uid, exc_info=True)
                continue

            if not meta.get('must_change_password'):
                continue  # they set their own password → it is theirs now, never expire it
            issued_raw = meta.get('temp_password_issued_at')
            if not issued_raw:
                continue  # no clock (legacy account created before this field) → leave it
            try:
                issued = datetime.datetime.fromisoformat(issued_raw)
            except (ValueError, TypeError):
                continue
            if issued >= cutoff:
                continue  # still within the TTL

            # Expired: rotate to a long random password that is NEVER emailed, so the copy sitting in
            # the invitee's inbox stops working. must_change_password stays true (a Resend re-issues a
            # known one); null temp_password_issued_at so THIS run is the only one that acts on it
            # (Supabase merges user_metadata, so we clear by nulling, not omitting); mark expired.
            new_meta = {**meta, 'temp_password_issued_at': None, 'temp_password_expired': True}
            try:
                pr = http_requests.put(
                    f'{url}/auth/v1/admin/users/{uid}',
                    json={'password': generate_temp_password(groups=8), 'user_metadata': new_meta},
                    headers=headers, timeout=15,
                )
                if pr.status_code in (200, 201):
                    expired += 1
                else:
                    logger.warning('expire_temp_passwords: rotate failed %s %s', pr.status_code, pr.text)
            except Exception:  # noqa: BLE001
                logger.warning('expire_temp_passwords: rotate errored for %s', uid, exc_info=True)

        self.stdout.write(f'expire_temp_passwords: checked {checked}, expired {expired} (TTL {days}d)')
