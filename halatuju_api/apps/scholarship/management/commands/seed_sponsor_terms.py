# -*- coding: utf-8 -*-
"""Seed sponsor terms v1 from the owner-approved draft.

The content here is the machine-readable twin of `docs/scholarship/sponsor-terms-draft.md`, which
stays the place the WORDS are edited and reviewed. Keeping both is deliberate: the markdown carries
the editor notes explaining which sentences are load-bearing and why, and those notes must not ship
to a sponsor.

Idempotent. Creates the version as a DRAFT and never publishes — publishing is a super-only action
taken deliberately in the panel, after someone has read it. Re-running does nothing unless
``--reset`` is passed, so this can be run safely on production more than once.

⚠ English only. Malay and Tamil are left blank on purpose: the owner is the Tamil authority and
machine drafts of a document people are BOUND by is not a risk worth taking for a courtesy
translation. Validation warning W1 will fire, honestly saying those sponsors will read English.
"""
from django.core.management.base import BaseCommand

from apps.scholarship import sponsor_terms
from apps.scholarship.models import SponsorTermsVersion

VERSION = '2026-sponsor-1'

TITLE = 'Joining BrightPath as a sponsor'
INTRO = ('Thank you for wanting to help. This page explains how it works and what we ask of you. '
         'It is short on purpose.')

# (heading, body, quiz_or_None)
SECTIONS = [
    ('Your gift is a gift',
     'What you give is a donation, not a loan or an investment. Nothing is repaid to you — not '
     'the money, not interest, not a share of anything. A student owes you nothing.',
     {'tag': 'Your gift',
      'plain': 'What you give is a donation, not a loan or an investment.',
      'question': "You've given RM10,000, and the student you helped graduates and starts work. "
                  'What comes back to you?',
      'options': ['The money, once they can afford to repay it',
                  'Nothing — it was a gift',
                  'A small share of what they earn'],
      'correct': 1,
      'why': 'Nothing is repaid — not the money, not interest, not a share of anything. '
             'A student owes you nothing.'}),

    ('You give to the programme, not to a student',
     'Your donation goes to the BrightPath Programme, which administers the funds. We record it '
     'as credit in your account, which you then use to nominate a student. Money never passes '
     'directly from you to a student.',
     None),

    ('You choose, and we make the award',
     'You nominate a student from those we have already vetted. We follow your choice wherever we '
     'can. Sometimes we cannot — a student withdraws, their university place falls through, or an '
     'award would breach our own rules — and then we will tell you, and your credit returns to '
     'your balance for another student. The final decision on every award rests with us. This is '
     'what keeps your gift a gift.\n\n'
     'If you turn on AutoSponsor, you are asking us to make these nominations for you, using the '
     'preferences you set. We will only ever do so while your balance covers it, and the student '
     'still accepts it themselves. You can change it or switch it off whenever you like.',
     {'tag': 'Who decides',
      'plain': 'You nominate a student; the programme makes the award.',
      'question': 'You nominate a student, but their university place falls through before term '
                  'starts. What happens?',
      'options': ['We tell you, and your credit returns to your balance for another student',
                  'The money is lost — it was already committed',
                  'We quietly move it to a different student and let you know at year end'],
      'correct': 0,
      'why': 'We follow your choice wherever we can. When we cannot, we tell you and the credit '
             'comes straight back to your balance. The final decision on every award rests with '
             'us — that is what keeps your gift a gift.'}),

    ('The commitment is full and upfront',
     'When you nominate a student you commit their whole amount at once, not month by month. That '
     'is what lets us promise a student their funding is secure for the year ahead, which is the '
     'single most useful thing we can tell them.',
     {'tag': 'The commitment',
      'plain': 'A nomination commits the whole amount at once.',
      'question': 'When you nominate a student, how much are you committing?',
      'options': ['The first month, then monthly as you go',
                  'Whatever you can manage each month',
                  'The whole amount, upfront'],
      'correct': 2,
      'why': 'That is what lets us promise a student their funding is secure for the year ahead — '
             'the single most useful thing we can tell them.'}),

    ('How the money reaches a student',
     'Monthly, through Vircle — an app that can only be spent on education. Never as cash. This '
     'is how we keep a gift on the purpose it was given for.',
     None),

    ('What we ask of a student',
     'Steady progress. We confirm each student is genuinely enrolled and we follow their results. '
     'If a student stops progressing we may pause or stop payments, and anything unspent returns '
     'to your balance.',
     None),

    ('We will tell you how it was used',
     "You will see your students' progress and how the funds were spent. Enrolment is verified "
     "independently, and the programme's money is audited annually.",
     None),

    ('You will not know who they are, and that is deliberate',
     'You see an anonymous profile — field of study, region, academic band. Never a name, IC, '
     'address, photograph, or contact details. Please do not try to identify or contact a '
     'student. If a student wants to write to you, we will pass it on. This protects a young '
     'person who had no choice about needing help.',
     {'tag': 'Anonymity',
      'plain': 'You see an anonymous profile, and never the student behind it.',
      'question': "It's your student's birthday and you'd like to send them a note. Can you?",
      'options': ['Yes, through their profile page',
                  'Yes, once they have accepted your support',
                  'No — you never see who they are, and should not try to find out'],
      'correct': 2,
      'why': 'You see field of study, region and academic band — never a name, IC, address, photo '
             'or contact details. If a student wants to write to you, we pass it on.'}),

    ('Please do not use a student for publicity',
     'You are very welcome to say that you support the programme. Please do not name, picture or '
     'identify a student you have funded, in anything public.',
     None),

    ('Your money must be clean',
     'We ask you to confirm that what you give is your own and lawfully obtained. We may ask you '
     'to identify yourself or to explain where funds came from, and we may decline or return a '
     'donation. This protects the programme and every other sponsor in it.',
     {'tag': 'Clean funds',
      'plain': 'We may ask you to show where the money came from.',
      'question': 'Might we ever ask you to explain where your donation came from?',
      'options': ['Yes — and we may decline or return a donation',
                  'No, that would be an odd thing to ask a donor',
                  'Only for unusually large gifts'],
      'correct': 0,
      'why': 'We ask you to confirm the funds are your own and lawfully obtained, and we may ask '
             'you to identify yourself. It protects the programme and every other sponsor in it.'}),

    ('Refunds, and credit you do not use',
     'Once given, a donation cannot be refunded — that is what makes it a completed gift. We will '
     'of course put right a genuine error. Credit that sits unused for two years is reallocated '
     'by us to other students in the programme rather than left idle.',
     {'tag': 'Unused credit',
      'plain': 'Credit left unused is eventually reallocated.',
      'question': "You've had credit sitting in your balance for two years without nominating "
                  'anyone. What happens to it?',
      'options': ['It is refunded to you',
                  'It stays yours indefinitely until you use it',
                  'We reallocate it to other students in the programme'],
      'correct': 2,
      'why': 'Once given, a donation cannot be refunded — that is what makes it a completed gift. '
             'We will of course put right a genuine error.'}),

    ('Your own information, and tax',
     'We hold your name, contact details and giving history to administer your account, as set '
     'out in our privacy notice. You can ask to see, correct or delete it. Separately, and we '
     'want to be straightforward about this: we are not yet an approved institution for tax '
     'deduction, so we cannot issue a tax-deductible receipt. We will tell you if that changes.',
     None),

    ('Ending, changes, and getting in touch',
     'You may close your account at any time; gifts already made stand. We may suspend or close '
     'an account if these terms are broken, if we cannot verify where funds came from, or if '
     'someone tries to identify or contact a student. When these terms change materially we will '
     'ask you to read and accept the new version. Questions or complaints: use the contact form.',
     None),
]


class Command(BaseCommand):
    help = 'Seed sponsor terms v1 as a DRAFT (idempotent; never publishes).'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Overwrite the intro and sections of an existing DRAFT.')

    def handle(self, *args, **opts):
        existing = SponsorTermsVersion.objects.filter(version=VERSION).first()

        if existing and not opts['reset']:
            self.stdout.write(self.style.WARNING(
                f'{VERSION} already exists ({existing.status}) — nothing done. '
                'Pass --reset to overwrite a draft.'))
            return

        if existing:
            if existing.status != SponsorTermsVersion.STATUS_DRAFT:
                self.stdout.write(self.style.ERROR(
                    f'{VERSION} is {existing.status} and therefore immutable. '
                    'Create a new version instead of resetting this one.'))
                return
            terms = existing
            terms.title_en = TITLE
            terms.intro_en = INTRO
            terms.save(update_fields=['title_en', 'intro_en', 'updated_at'])
        else:
            terms = sponsor_terms.create_version(version=VERSION, by_email='seed')
            terms.title_en = TITLE
            terms.intro_en = INTRO
            terms.save(update_fields=['title_en', 'intro_en', 'updated_at'])

        rows = []
        for heading, body, quiz in SECTIONS:
            rows.append({
                'heading_en': heading,
                'body_en': body,
                'is_quiz_candidate': quiz is not None,
                'quiz_en': quiz or {},
            })
        sponsor_terms.replace_sections(terms, rows)

        # Prove the seed would survive the gate a hand edit has to pass. A seed that could not be
        # published is a trap for whoever tries.
        result = sponsor_terms.validate_for_publish(terms)
        quizzed = sum(1 for _h, _b, q in SECTIONS if q)
        self.stdout.write(self.style.SUCCESS(
            f'{VERSION}: {len(SECTIONS)} sections, {quizzed} checkpoints — status {terms.status}.'))
        if result.ok:
            self.stdout.write('Validation: OK' + (
                f' (warnings: {", ".join(result.warnings)})' if result.warnings else ''))
        else:
            self.stdout.write(self.style.ERROR(
                'Validation FAILED: ' + ', '.join(result.errors)))
        self.stdout.write('Not published — publish from the Terms tab when you are happy with it.')
