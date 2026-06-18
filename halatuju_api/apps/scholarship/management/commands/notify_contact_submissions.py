"""Email new (unread) public contact-form submissions to the team, then mark them read.

The contact form (web /contact) posts to the Supabase `contact-submit` Edge Function,
which inserts a row into `contact_submissions` (name, contact, category, message, read).
Nothing alerted anyone, so messages sat unseen. This job — run frequently via the
internal cron endpoint 'notify-contact-submissions' — emails each unread row to
``settings.ADMIN_NOTIFY_EMAIL`` (contact@halatuju.xyz) and flips `read` so it's sent once.

`contact_submissions` is a Supabase-managed table (not a Django model); the api connects
as the `postgres` owner, so a plain raw-SQL read/update is the simplest reliable access.
Best-effort: a row stays unread (and is retried next run) if its email fails.
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection

from apps.scholarship.emails import send_contact_submission_admin_email


class Command(BaseCommand):
    help = 'Email unread contact-form submissions to the team, then mark them read.'

    def handle(self, *args, **options):
        to_email = getattr(settings, 'ADMIN_NOTIFY_EMAIL', '') or ''
        if not to_email:
            self.stdout.write('ADMIN_NOTIFY_EMAIL not set — nothing sent.')
            return
        try:
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT id, name, contact, category, message, created_at "
                    "FROM contact_submissions WHERE NOT read ORDER BY created_at")
                rows = cur.fetchall()
                sent, failed = [], []
                for (sid, name, contact, category, message, created_at) in rows:
                    ok = send_contact_submission_admin_email(
                        to_email=to_email, name=name, contact=contact,
                        category=category, message=message, created_at=created_at)
                    if ok:
                        cur.execute("UPDATE contact_submissions SET read = true WHERE id = %s", [sid])
                        sent.append(sid)
                    else:
                        failed.append(sid)
        except Exception as e:  # table missing / DB hiccup — never crash the scheduler
            self.stdout.write(f'contact-submissions notify skipped: {e}')
            return
        self.stdout.write(f'Contact submissions emailed={sent} failed={failed}')
