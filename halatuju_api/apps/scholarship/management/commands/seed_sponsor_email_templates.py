"""Seed the nine sponsor-email templates (S3, 2026-07-28).

Idempotent: creates a missing kind, leaves an existing row's wording ALONE (an org_admin may have
edited it) unless `--reset` is passed. **Never flips `enabled`** — that is the owner's switch, and
every seed arrives OFF.

THE VOICE, and why it is enforced rather than suggested (`sponsor_comms.banned_phrases` refuses a
save that breaks it, and a test asserts these seeds pass):

  * **Never claim tax relief.** HalaTuju holds no LHDN s44(6) approval and the entity question
    behind it is open. It is the one line here that could cost a donor money.
  * **A sponsor funds a student; they do not acquire one.** No "your student" — it is false, and
    it cuts against the anonymity the whole pool rests on.
  * **No urgency.** Consent taken at registration covers account correspondence. Pressure copy
    turns it into marketing.

Copy is British English, plain, and addressed to an adult who has given real money.
"""
from django.core.management.base import BaseCommand

from apps.scholarship import sponsor_comms
from apps.scholarship.models import SponsorEmailTemplate

SEEDS = {
    'welcome': {
        'subject': 'We have your {programme_name} sponsor registration',
        'body': (
            'Dear {sponsor_name},\n'
            '\n'
            'Thank you for registering as a sponsor for the {programme_name}. We have your '
            'details and a member of our team is reviewing them now.\n'
            '\n'
            'We check every sponsor before opening up the students’ information, because those '
            'students trust us with a great deal about their circumstances. It usually takes a '
            'day or two, and we will write to you either way.\n'
            '\n'
            '{team_signoff}'
        ),
    },
    'approved': {
        'subject': 'You are approved as a {programme_name} sponsor',
        'body': (
            'Dear {sponsor_name},\n'
            '\n'
            'Your sponsor account for the {programme_name} has been approved. You can sign in '
            'now and see the students waiting for support:\n'
            '\n'
            '{portal_link}\n'
            '\n'
            'Each student is shown without their name — you will see their course, their '
            'results and what they need, and the reference code is how you and we refer to the '
            'same person. That anonymity is theirs, not ours to waive.\n'
            '\n'
            'If anything is unclear, reply to this email and a person will answer.\n'
            '\n'
            '{team_signoff}'
        ),
    },
    'rejected': {
        'subject': 'About your {programme_name} sponsor registration',
        'body': (
            'Dear {sponsor_name},\n'
            '\n'
            'Thank you for offering to support students through the {programme_name}. After '
            'reviewing your registration we are not able to approve the account at this time.\n'
            '\n'
            'This is not a judgement of you or your intentions. If you would like to understand '
            'the decision or think we have it wrong, reply to this email and we will look at it '
            'again properly.\n'
            '\n'
            '{team_signoff}'
        ),
    },
    'suspended': {
        'subject': 'Your {programme_name} sponsor account has been paused',
        'body': (
            'Dear {sponsor_name},\n'
            '\n'
            'We have paused your sponsor account for the {programme_name}. While it is paused '
            'you will not be able to sign in or support a new student.\n'
            '\n'
            'Any support you have already committed to a student continues — pausing an account '
            'never withdraws money from a student who is counting on it.\n'
            '\n'
            'If this is unexpected, please reply to this email so we can sort it out.\n'
            '\n'
            '{team_signoff}'
        ),
    },
    'reinstated': {
        'subject': 'Your {programme_name} sponsor account is active again',
        'body': (
            'Dear {sponsor_name},\n'
            '\n'
            'Your sponsor account for the {programme_name} is active again, and you can sign in '
            'as before:\n'
            '\n'
            '{portal_link}\n'
            '\n'
            'Thank you for your patience while we sorted this out.\n'
            '\n'
            '{team_signoff}'
        ),
    },
    'credit_confirmed': {
        'subject': 'Your {programme_name} gift of RM {amount} is recorded',
        'body': (
            'Dear {sponsor_name},\n'
            '\n'
            'We have received and recorded your gift of RM {amount} to the {programme_name}. '
            'Two of our team have checked it against the transfer, which is why this email '
            'comes now rather than the moment the money arrived.\n'
            '\n'
            'Bank reference: {bank_ref}\n'
            '\n'
            'You now have RM {available} available to put behind a student. You can see your '
            'giving and choose a student here:\n'
            '\n'
            '{portal_link}\n'
            '\n'
            'If any of these figures do not match your own records, reply to this email and we '
            'will reconcile it with you.\n'
            '\n'
            '{team_signoff}'
        ),
    },
    'new_students': {
        'subject': '{count} student(s) waiting for a {programme_name} sponsor',
        'body': (
            'Dear {sponsor_name},\n'
            '\n'
            'These students have just been approved for the {programme_name} and are waiting '
            'for someone to fund them.\n'
            '\n'
            '{student_cards}\n'
            '\n'
            '{portal_link}\n'
            '\n'
            '{team_signoff}'
        ),
    },
    'weekly_digest': {
        'subject': 'This week: {count} student(s) waiting for a {programme_name} sponsor',
        'body': (
            'Dear {sponsor_name},\n'
            '\n'
            'Here are the students waiting for support through the {programme_name} this week.\n'
            '\n'
            '{student_cards}\n'
            '\n'
            '{portal_link}\n'
            '\n'
            'You can change how often you hear from us, or stop these emails entirely, from '
            'your sponsor account.\n'
            '\n'
            '{team_signoff}'
        ),
    },
    'referral_invite': {
        'subject': '{inviter_name} thinks you might want to support a student',
        'body': (
            'Dear {invitee_name},\n'
            '\n'
            '{inviter_name} supports students through the {programme_name} and thought you '
            'might want to as well.\n'
            '\n'
            '{note}\n'
            '\n'
            'The {programme_name} helps Malaysian students from low-income families through '
            'their first years of study. Sponsors see each student’s course, results and what '
            'they need — never their name — and choose who to support.\n'
            '\n'
            'If you would like to look, start here:\n'
            '\n'
            '{invite_link}\n'
            '\n'
            'If this is not for you, you can simply ignore this email; we will not write again.\n'
            '\n'
            '{team_signoff}'
        ),
    },
}


class Command(BaseCommand):
    help = "Seed the nine sponsor email templates (all OFF). Idempotent; --reset rewrites wording."

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Overwrite the wording of templates that already exist.')

    def handle(self, *args, **options):
        reset = options['reset']
        created = updated = skipped = 0

        for kind, seed in SEEDS.items():
            # The seeds must satisfy the same guards a hand-edited save does — otherwise the
            # panel would ship with copy an org_admin could not re-save after touching it.
            bad = sponsor_comms.unknown_placeholders(kind, seed['subject'], seed['body'])
            if bad:
                self.stderr.write(self.style.ERROR(
                    f'{kind}: seed uses tokens this kind does not supply: {", ".join(bad)}'))
                continue
            voice = sponsor_comms.banned_phrases(seed['subject'], seed['body'])
            if voice:
                self.stderr.write(self.style.ERROR(
                    f'{kind}: seed breaks the voice rule: {", ".join(voice)}'))
                continue

            row = SponsorEmailTemplate.objects.filter(kind=kind).first()
            if row is None:
                SponsorEmailTemplate.objects.create(
                    kind=kind, enabled=False,          # never on by seeding — the owner decides
                    subject=seed['subject'], body=seed['body'])
                created += 1
                self.stdout.write(f'  created {kind} (off)')
            elif reset:
                row.subject, row.body = seed['subject'], seed['body']
                row.save(update_fields=['subject', 'body', 'updated_at'])
                updated += 1
                self.stdout.write(f'  reset {kind} (switch untouched: '
                                  f'{"on" if row.enabled else "off"})')
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f'{created} created, {updated} reset, {skipped} left alone. '
            f'Every template is OFF unless somebody switched it on; '
            f'SPONSOR_COMMS_ENABLED is {"set" if sponsor_comms.comms_enabled() else "unset"}.'))
