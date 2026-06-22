"""Send a one-off TEST email of a chosen template to a chosen address.

Operational utility (not part of any student flow) so the owner can preview a real
rendered email in their inbox via the production Brevo pipeline. Run on Cloud Run where
the EMAIL_* env is set, e.g. as a job execution override:

    python manage.py send_test_email --to admin@tamilfoundation.org --kind profile_complete

``--name`` sets the greeting; ``--english-only`` drops the Malay mirror.
"""
from django.core.management.base import BaseCommand

from apps.scholarship import emails


class Command(BaseCommand):
    help = "Send a test render of a student email to an address (preview only)."

    def add_arguments(self, parser):
        parser.add_argument('--to', required=True, help='Recipient email address')
        parser.add_argument('--kind', default='profile_complete',
                            help='Which email to send (currently: profile_complete)')
        parser.add_argument('--name', default='Shamalaa', help='Student first name for the greeting')
        parser.add_argument('--english-only', action='store_true',
                            help='Send the English-only variant (no Malay mirror)')

    def handle(self, *args, **opts):
        to = opts['to']
        kind = opts['kind']
        name = opts['name']
        en_only = opts['english_only']

        if kind == 'profile_complete':
            ok = emails.send_profile_complete_student_email(
                to, student_name=name, english_only=en_only)
        else:
            self.stderr.write(f'Unknown --kind: {kind}')
            return

        self.stdout.write(self.style.SUCCESS(f'send_test_email kind={kind} to={to} → sent={ok}'))
