"""Seed the partner-email templates (2026-07-26; a sixth added 2026-08-01).

Five go to the partner ORGANISATION. The sixth, `student_assigned`, goes to the STUDENT — it is
the other half of `assigned`, sent at the same moment, and it lives here so the owner switches it
and edits its wording on the same screen as the rest. It is the only kind seeded switched ON.

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
    # The STUDENT's copy of the same moment (request #3, 2026-08-01). Bilingual in one body, EN
    # above MS, the way every student email here is written — the reader may not read English.
    # ⚠ The second paragraph is the point of the whole request: it says what the organisation may
    # DO and what it can SEE. The requester insisted on a notification precisely because of that
    # access, so a rewrite that drops it would leave the email sending and the request unmet.
    'student_assigned': {
        'subject': '{org_name} is now supporting your {programme_name} application',
        'body': (
            'Hi {student_name},\n'
            '\n'
            'We are writing to let you know that {org_name} has been assigned to support your '
            'application to the {programme_name} Programme.\n'
            '\n'
            'This means {org_name} may act as a witness when you sign your bursary contract, and '
            'that they can see certain details of your application in order to do that. Nothing '
            'about your application changes, and the decision on your application stays with us.\n'
            '\n'
            'You do not need to do anything, and there is nothing to reply to. We are simply '
            'telling you who else is now involved, because you have a right to know.\n'
            '\n'
            'One note for your peace of mind: we will never ask you for money, a bank password, '
            'or an OTP or PIN, and neither will {org_name}. If anyone does, it is not us — please '
            'tell us at {support_email}.\n'
            '\n'
            '{team_signoff}\n'
            '\n'
            '———\n'
            '\n'
            'Salam {student_name},\n'
            '\n'
            'Kami ingin memaklumkan bahawa {org_name} telah ditugaskan untuk menyokong permohonan '
            'anda kepada Program {programme_name_ms}.\n'
            '\n'
            'Ini bermakna {org_name} boleh bertindak sebagai saksi apabila anda menandatangani '
            'kontrak bursari anda, dan mereka dapat melihat butiran tertentu permohonan anda bagi '
            'tujuan itu. Tiada apa-apa pada permohonan anda yang berubah, dan keputusan ke atas '
            'permohonan anda kekal di tangan kami.\n'
            '\n'
            'Anda tidak perlu melakukan apa-apa, dan tiada apa-apa yang perlu dibalas. Kami '
            'sekadar memberitahu anda siapa lagi yang kini terlibat, kerana anda berhak tahu.\n'
            '\n'
            'Satu nota untuk ketenangan anda: kami tidak sekali-kali akan meminta wang, kata '
            'laluan bank, atau OTP atau PIN, dan begitu juga {org_name}. Jika sesiapa berbuat '
            'demikian, itu bukan kami — sila beritahu kami di {support_email}.\n'
            '\n'
            '{team_signoff_ms}'
        ),
    },
    # ── the five reviewer emails (request #10, 2026-08-02) ────────────────────────
    #
    # ⚠ THESE FIVE ARE LIVE MAIL, AND THIS COPY REPRODUCES WHAT WENT OUT YESTERDAY. They are
    # seeded ON. Adopting a live email into a switchable template and seeding it OFF is how a
    # feature ships as silence — a tidy panel of switches all correctly reading "off", and
    # reviewers simply never hearing from us again (lessons.md, sponsor S3, 2026-07-28). Reword
    # them freely afterwards; do not reword them HERE without comparing against `emails.py`,
    # because the seed is the wording an organisation inherits.
    #
    # English only: the recipients are our own volunteers, so there is no Malay half.
    'reviewer_assigned': {
        'subject': 'New applicant assigned to you — {ref}',
        'body': (
            'Dear {reviewer_name},\n'
            '\n'
            'A new applicant has been assigned to you for review.\n'
            '\n'
            'Reference: {ref}\n'
            'Programme: {programme}\n'
            'Please review by: {review_by}\n'
            '\n'
            'Everything you need — profile, documents, and the verification checks — is in your '
            'reviewer dashboard:\n'
            '\n'
            '{dashboard_link}\n'
            '\n'
            'Can’t take this one? Just reply and we’ll reassign it.\n'
            '\n'
            '{team_signoff}'
        ),
    },
    'qc_returned': {
        'subject': 'Case returned by QC — action needed — {ref}',
        'body': (
            'Dear {reviewer_name},\n'
            '\n'
            'Quality control has returned one of your cases for revision.\n'
            '\n'
            'Reference: {ref}\n'
            'Applicant: {applicant_name}\n'
            '\n'
            'What to address:\n'
            '\n'
            '{qc_comments}\n'
            '\n'
            'Please review the points above, update your findings and verdict, and resubmit. '
            'Everything you need is in your reviewer dashboard:\n'
            '\n'
            '{dashboard_link}\n'
            '\n'
            '{team_signoff}'
        ),
    },
    'qc_rejected': {
        'subject': 'Case rejected by QC — {ref}',
        'body': (
            'Dear {reviewer_name},\n'
            '\n'
            'After quality control review, one of your cases has been rejected. No further action '
            'is needed from you — this note is for your records.\n'
            '\n'
            'Reference: {ref}\n'
            'Applicant: {applicant_name}\n'
            '\n'
            'QC reason:\n'
            '\n'
            '{qc_comments}\n'
            '\n'
            'You can see the case in your reviewer dashboard:\n'
            '\n'
            '{dashboard_link}\n'
            '\n'
            '{team_signoff}'
        ),
    },
    # The old single `verdict_due` sender split in two. The engine has no conditionals, and the
    # overdue branch changes BOTH the subject and the opening sentence — one stored body cannot
    # say "due soon" and "overdue", so pretending it could would mean one of them reads wrongly.
    'verdict_due_soon': {
        'subject': 'Verdict due soon — {ref}',
        'body': (
            'Dear {reviewer_name},\n'
            '\n'
            'Your verdict for {applicant_name} is due soon — by {due_by}.\n'
            '\n'
            'Please open their record, complete your review, and record your verdict.\n'
            '\n'
            '{dashboard_link}\n'
            '\n'
            '{team_signoff}'
        ),
    },
    'verdict_overdue': {
        'subject': 'Verdict overdue — {ref}',
        'body': (
            'Dear {reviewer_name},\n'
            '\n'
            'Your verdict for {applicant_name} is overdue — it was due {due_by}.\n'
            '\n'
            'Please open their record, complete your review, and record your verdict.\n'
            '\n'
            '{dashboard_link}\n'
            '\n'
            '{team_signoff}'
        ),
    },
    # ── the two invitation emails (2026-08-04) ────────────────────────────────────
    #
    # WORD-FOR-WORD what `emails.build_partner_welcome_email` and
    # `build_sponsor_invitation_email` already send, so seeding changes nothing anybody receives.
    #
    # ⚠ `{access}` IS A STRUCTURAL BLOCK carrying the temporary password and the three shapes it
    # takes (a fresh password / Google / already-registered). It is OURS; the letter around it is
    # the organisation's. The save guard refuses a body that has dropped it, because an invitation
    # without it is a warm letter containing no way to sign in — and nothing would report that.
    'invite_staff': {
        'subject': 'Your HalaTuju partner access',
        'body': (
            'Dear {name},\n'
            '\n'
            'You have been added to HalaTuju as {role_label}.\n'
            '\n'
            'Sign in here:\n'
            '{login_link}\n'
            '\n'
            '{access}\n'
            '\n'
            'Any trouble at all, just reply to this email.\n'
            '\n'
            'Warm regards,\n'
            'The HalaTuju Team'
        ),
    },
    # `{note}` is the inviter's own words and is a block for the same reason `qc_comments` is:
    # a note that happens to contain a token must arrive verbatim, not be substituted.
    'invite_sponsor': {
        'subject': 'An invitation to sponsor a student with {org_name}',
        'body': (
            'Hello,\n'
            '\n'
            '{invited_by} has invited you to become a sponsor of {org_name}.\n'
            '\n'
            '{note}\n'
            '\n'
            'Sponsors here support one student through their studies. You can read how it works, '
            'and sign up, here:\n'
            '{link}\n'
            '\n'
            'There is nothing to pay to register, and you choose whether to go ahead after you '
            'have seen how it works.\n'
            '\n'
            'Thanks,\n'
            '{team_signoff}'
        ),
    },
}

#: Kinds seeded switched ON. Everything else arrives OFF so wording can be agreed while the
#: feature is dark — but this one was requested, quoted and paid for (request #3), and a paid
#: notification that arrives switched off is a non-delivery. Seeding it ON also makes the screen
#: agree with what production is already doing rather than silently changing behaviour.
#: The invitation kinds are seeded ON for tidiness, but their switch is NEVER READ — see
#: `emails._invite_render`, and the note in `PartnerEmailTemplate.KIND_CHOICES` for why an
#: invitation that can be switched off is an invitation nobody receives.
SEEDED_ON = (frozenset({'student_assigned'}) | PartnerEmailTemplate.REVIEWER_KINDS
             | PartnerEmailTemplate.INVITE_KINDS)


class Command(BaseCommand):
    help = 'Seed the partner-email templates (idempotent; --reset overwrites the wording).'

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
                    kind=kind, enabled=kind in SEEDED_ON,
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
