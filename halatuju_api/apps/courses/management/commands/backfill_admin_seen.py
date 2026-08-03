"""Seed `first_seen_at` / `last_seen_at` from Supabase's own `last_sign_in_at`, once.

Staff sign-in has only been recorded since 2026-08-03. Without this, the day the Invitations page
ships every colleague of a year reads "never signed in" beside the genuine cases — and a screen
that cries wolf on its first day is never trusted again.

⚠ **A COMMAND, NEVER A MIGRATION.** It makes one HTTP call per admin against Supabase; a migration
that reaches the network cannot be re-run, cannot be rolled back, and fails a deploy for a reason
that has nothing to do with schema.

⚠ **IT SEEDS BOTH COLUMNS FROM ONE FACT, AND THAT IS AN APPROXIMATION.** Supabase records
`last_sign_in_at` only — there is no first. So `first_seen_at` is seeded to the same instant, which
is right for the question being asked ("did they ever arrive?") and wrong as a date ("when did they
first arrive?"). It is a floor: the true first sign-in is that date or earlier. Never presented as
precise, and never overwritten once the live stamp starts recording real visits.

⚠ **SILENCE IS NOT ABSENCE.** An admin with no Supabase user (a Google or already-registered
invitee who has never signed in, so `supabase_user_id` is NULL) is skipped and stays NULL, which
reads as "not recorded" — the honest answer. Do not let a later change turn that into "never".

    python manage.py backfill_admin_seen              # report only
    python manage.py backfill_admin_seen --apply
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.courses.models import PartnerAdmin


class Command(BaseCommand):
    help = "Seed staff first/last-seen from Supabase's last_sign_in_at (one-off)."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **o):
        url = (getattr(settings, 'SUPABASE_URL', '') or '').rstrip('/')
        key = getattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', '') or ''
        if not (url and key):
            self.stdout.write('Supabase is not configured here — nothing to read. No changes.')
            return

        import requests as http
        from django.utils.dateparse import parse_datetime

        headers = {'apikey': key, 'Authorization': f'Bearer {key}'}
        rows = PartnerAdmin.objects.filter(
            supabase_user_id__isnull=False, first_seen_at__isnull=True).order_by('id')

        seeded = skipped_no_signin = failed = 0
        for a in rows:
            try:
                r = http.get(f'{url}/auth/v1/admin/users/{a.supabase_user_id}',
                             headers=headers, timeout=30)
            except Exception as e:                      # noqa: BLE001
                self.stdout.write(f'  ! {a.email}: {e}')
                failed += 1
                continue
            if r.status_code != 200:
                self.stdout.write(f'  ! {a.email}: HTTP {r.status_code}')
                failed += 1
                continue
            stamp = parse_datetime(((r.json() or {}).get('last_sign_in_at') or '') or '')
            if not stamp:
                # Provisioned but never signed in — genuinely nothing to record.
                skipped_no_signin += 1
                continue
            seeded += 1
            self.stdout.write(f'  {a.email}: {stamp.isoformat()}')
            if o['apply']:
                # Conditional on still being NULL, so a real visit recorded while this ran always
                # wins over the approximation.
                PartnerAdmin.objects.filter(pk=a.pk, first_seen_at__isnull=True).update(
                    first_seen_at=stamp, last_seen_at=stamp)

        never = PartnerAdmin.objects.filter(supabase_user_id__isnull=True).count()
        self.stdout.write('')
        self.stdout.write(f'seeded {seeded} · provisioned but never signed in {skipped_no_signin} '
                          f'· unreadable {failed} · no Supabase account at all {never}')
        if not o['apply']:
            self.stdout.write('Report only — re-run with --apply to write.')
