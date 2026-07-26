"""Seed the five partner-email templates (2026-07-26).

Idempotent: creates a missing kind, leaves an existing row's wording ALONE (an org_admin may have
edited it) unless `--reset` is passed. Never flips `enabled` — that is the owner's switch.

THE VOICE IS A REQUIREMENT, NOT A DRAFT (owner, 2026-07-26): a referral organisation co-owns this
bursary and may market it as its own, so the students are the ORGANISATION's — never "the students
you send us" (conduit), and never "your students" (which hands them to whoever happens to read the
email; the reader is a representative, not the owner). Every possessive names the organisation.
`partner_comms.banned_phrases` refuses a save that breaks either rule, and a test asserts these
seeds pass it.
"""
from django.core.management.base import BaseCommand

from apps.scholarship import partner_comms
from apps.scholarship.models import PartnerEmailTemplate

SEEDS = {
    'weekly_summary': {
        'subject': '{org_name} — bursary students this week',
        'body': (
            'Dear {contact_person},\n'
            '\n'
            'Here is how {org_name}’s bursary students are getting on this week.\n'
            '\n'
            '{counts_table}\n'
            '\n'
            '{org_name} runs this bursary alongside us, so if any of these figures look wrong, '
            'reply to this email and we will look into it together.\n'
            '\n'
            '{team_signoff}'
        ),
    },
    'shortlisted_followup': {
        'subject': '{count} of {org_name}’s students have not finished applying',
        'body': (
            'Dear {contact_person},\n'
            '\n'
            'These {count} students of {org_name} were shortlisted for the bursary but have not '
            'yet completed their application.\n'
            '\n'
            '{student_table}\n'
            '\n'
            'Your team knows them far better than we do, and a word from {org_name} usually '
            'carries further than another email from us. We will keep reminding them as well.\n'
            '\n'
            '{team_signoff}'
        ),
    },
    'awaiting_review': {
        'subject': '{count} of {org_name}’s students have completed their application',
        'body': (
            'Dear {contact_person},\n'
            '\n'
            'Good news — {count} of {org_name}’s students have completed their bursary '
            'application:\n'
            '\n'
            '{student_list}\n'
            '\n'
            'Everything we asked for is in, and their cases are now with the review panel. We will '
            'write again as soon as there is an outcome.\n'
            '\n'
            '{team_signoff}'
        ),
    },
    'awarded': {
        'subject': '{org_name} — a bursary has been awarded',
        'body': (
            'Dear {contact_person},\n'
            '\n'
            '{count} of {org_name}’s students has been awarded a bursary:\n'
            '\n'
            '{student_list}\n'
            '\n'
            'A funder has committed to supporting them through their studies. This is '
            '{org_name}’s achievement as much as ours — please do share the news as your '
            'own.\n'
            '\n'
            'The agreement is being prepared now, and we may write separately to ask {org_name} to '
            'witness the signing.\n'
            '\n'
            '{team_signoff}'
        ),
    },
    'assigned': {
        'subject': 'A student has joined {org_name}’s bursary students',
        'body': (
            'Dear {contact_person},\n'
            '\n'
            '{student_name} applied for the bursary without naming an organisation, and has been '
            'placed with {org_name}. They now count among {org_name}’s bursary students and '
            'will appear in its weekly summary.\n'
            '\n'
            'If they are awarded, we may ask {org_name} to witness the signing of their '
            'agreement.\n'
            '\n'
            '{team_signoff}'
        ),
    },
}


class Command(BaseCommand):
    help = 'Seed the five partner-email templates (idempotent; --reset overwrites the wording).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='Overwrite an existing template’s subject/body with the seed wording. '
                 'Never touches its enabled switch.',
        )

    def handle(self, *args, **options):
        reset = options['reset']
        created = updated = kept = 0
        for kind in partner_comms.KINDS:
            seed = SEEDS[kind]
            # Fail loudly here rather than shipping a template the API would then refuse to save.
            unknown = partner_comms.unknown_placeholders(kind, seed['subject'], seed['body'])
            if unknown:
                self.stderr.write(f'{kind}: unknown placeholder(s) {unknown} — fix the seed')
                return
            banned = partner_comms.banned_phrases(seed['subject'], seed['body'])
            if banned:
                self.stderr.write(f'{kind}: conduit phrasing {banned} — fix the seed')
                return

            tpl = PartnerEmailTemplate.objects.filter(kind=kind).first()
            if tpl is None:
                PartnerEmailTemplate.objects.create(
                    kind=kind, enabled=False,
                    subject=seed['subject'], body=seed['body'],
                )
                created += 1
                self.stdout.write(f'created  {kind}')
            elif reset:
                tpl.subject = seed['subject']
                tpl.body = seed['body']
                tpl.save(update_fields=['subject', 'body', 'updated_at'])
                updated += 1
                self.stdout.write(f'reset    {kind}')
            else:
                kept += 1
                self.stdout.write(f'kept     {kind} (use --reset to overwrite the wording)')
        self.stdout.write(f'\ncreated={created} reset={updated} kept={kept}')
