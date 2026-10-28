"""Flag the STPM co-curriculum scores the C2 backfill could not work back cleanly — ONE-OFF,
STPM CGPA sprint C4 (owner ruling 2026-10-28).

`backfill_stpm_cgpa` derived each existing STPM student's co-curriculum score from the old stored
figure and marked some `KOKO NOT CLEAN`. Those students are now asked to confirm their score
(Check-2 ask `stpm_koko_confirm`, `apps/scholarship/stpm_asks.py`). The rule cannot be run again:
production's `stpm_cgpa` already holds the PNGK, so the old figure it worked from is gone. So this
command takes the APPLICATION ids explicitly and sets `StudentProfile.stpm_koko_unconfirmed = TRUE`
on each one's profile:

    python manage.py flag_stpm_koko_unconfirmed --applications 12,34      # preview
    python manage.py flag_stpm_koko_unconfirmed --applications 12,34 --apply

PREVIEW BY DEFAULT. One line per id: the id, the application's status and the action (no name,
NRIC or profile id, so the output may be pasted). Skipped, never written: an id with no
application, one not yet submitted, one in a final status (`review_sla.TERMINAL`, the list the
team's other commands use), no profile, or a profile not holding completed STPM results
(`stpm_asks.holds_completed_stpm` — the ask would never fire). Already flagged → left.
`--apply` writes with `.update()` (no other column, nor `updated_at`, moves), in one
transaction. Idempotent. The ask itself is raised by the next Check-2 sync.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.courses.models import StudentProfile
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.review_sla import TERMINAL
from apps.scholarship.stpm_asks import holds_completed_stpm


def _ids(raw):
    try:
        ids = [int(x) for x in str(raw).replace(' ', '').split(',') if x]
    except ValueError as exc:
        raise CommandError('--applications takes application ids separated by commas, e.g. 12,34') from exc
    if not ids:
        raise CommandError('--applications needs at least one application id')
    return list(dict.fromkeys(ids))


def _action(app):
    """What to do with one application (None = no such id): 'flag' or the reason it is skipped."""
    p = getattr(app, 'profile', None) if app else None
    if app is None:
        return 'no application'
    if app.profile_completed_at is None:
        return 'not submitted'
    if app.status in TERMINAL:
        return 'final status'
    if p is None:
        return 'no profile'
    if not holds_completed_stpm(p):
        return 'not STPM'
    return 'already flagged' if p.stpm_koko_unconfirmed is True else 'flag'


def plan(ids):
    """[(application id, status, action, profile pk | None)] — action 'flag', 'already flagged',
    'no application', 'not submitted', 'final status', 'no profile' or 'not STPM'. Only 'flag'
    rows carry a profile pk, and only they are written."""
    apps_ = {a.id: a for a in ScholarshipApplication.objects.select_related('profile').filter(id__in=ids)}
    out = []
    for i in ids:
        app = apps_.get(i)
        action = _action(app)
        out.append((i, app.status if app else '-', action, app.profile.pk if action == 'flag' else None))
    return out


class Command(BaseCommand):
    help = 'Flag named applications\' STPM co-curriculum score as unconfirmed (Check-2 ask). Preview unless --apply.'

    def add_arguments(self, parser):
        parser.add_argument('--applications', required=True, help='Application ids, comma-separated.')
        parser.add_argument('--apply', action='store_true', help='Write (default: preview only).')

    def handle(self, *args, **opts):
        rows = plan(_ids(opts['applications']))
        for app_id, status, action, _pk in rows:
            self.stdout.write(f'#{app_id}\t{status}\t{action}')
        todo = sorted({pk for _a, _s, action, pk in rows if action == 'flag'})
        self.stdout.write(f'{len(todo)} profile(s) to flag of {len(rows)} application id(s).')
        if not opts['apply']:
            self.stdout.write('PREVIEW — nothing written. Re-run with --apply to write.')
            return
        with transaction.atomic():
            n = StudentProfile.objects.filter(pk__in=todo).update(stpm_koko_unconfirmed=True)
        self.stdout.write(self.style.SUCCESS(f'Applied: {n} profile(s) flagged.'))
