"""Seed the partner-email templates (2026-07-26; a sixth added 2026-08-01).

Five go to the partner ORGANISATION. The sixth, `student_assigned`, goes to the STUDENT — it is
the other half of `assigned`, sent at the same moment, and it lives here so the owner switches it
and edits its wording on the same screen as the rest. It is the only kind seeded switched ON.

Idempotent: creates a missing kind, leaves an existing row's wording ALONE (an org_admin may have
edited it) unless a reset is asked for. Never flips `enabled` — that is the owner's switch.

⚠ **"LEAVES IT ALONE" CUTS BOTH WAYS, AND IT BIT ON 2026-08-04.** It also means REWRITING A BUILT-IN
BODY HERE CHANGES NOTHING ANYBODY RECEIVES once the row exists — the stored row wins, the deploy is
green, and the seed prints `kept`. The sponsor letter was rewritten into a donor pitch and the old
wording stayed live until it was pushed through deliberately.

To push a rewrite through, name the kinds: `--reset --kind invite_sponsor`, or on the deployed
service (where the cron endpoint passes no arguments) set `PARTNER_EMAIL_RESET_KINDS`. **Never a
bare `--reset` on production — six rows there carry real human edits and it would flatten all of
them.**

THE VOICE IS A REQUIREMENT, NOT A DRAFT (owner, 2026-07-26): a referral organisation co-owns this
bursary and may market it as its own, so the students are the ORGANISATION's — never "the students
you send us" (conduit), and never "your students" (which hands them to whoever happens to read the
email; the reader is a representative, not the owner). Every possessive names the organisation.
`partner_comms.banned_phrases` refuses a save that breaks either rule, and a test asserts these
seeds pass it.
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.scholarship import partner_comms
from apps.scholarship.models import PartnerEmailTemplate


def _env_reset_kinds():
    """Kinds whose stored wording this run may overwrite, from `PARTNER_EMAIL_RESET_KINDS`.

    ⚠ **THIS EXISTS BECAUSE THE CRON ENDPOINT CANNOT PASS ARGUMENTS** — `CronRunView` calls
    `call_command(name, stdout=…)` and nothing else — and because a rewritten built-in otherwise
    never reaches a production row (the seed keeps what is already there, by design). Same shape as
    every other one-off scope on this platform: `AWARD_EMAIL_APP_IDS`, `SIGN_INVITE_APP_IDS`,
    `PATHWAY_REPAIR_APP_IDS`.

    ⚠ **SET IT, RUN IT, THEN UNSET IT.** While it is set, every deploy's seed run rewrites those
    kinds — which would silently undo an org_admin's edit made in between. Comma-separated.
    """
    raw = getattr(settings, 'PARTNER_EMAIL_RESET_KINDS', '') or ''
    return [k.strip() for k in raw.split(',') if k.strip()]

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
    # ── the four invitation emails, one per group on the page (2026-08-04) ────────
    #
    # WORD-FOR-WORD what the matching `emails.build_*` function already sends, so seeding changes
    # nothing anybody receives. `test_the_seed_is_byte_identical_to_what_already_sends` holds this.
    #
    # ⚠ `{access}` IS A STRUCTURAL BLOCK carrying the temporary password and the three shapes it
    # takes (a fresh password / Google / already-registered). It is OURS; the letter around it is
    # the organisation's. The save guard refuses a body that has dropped it, because an invitation
    # without it is a warm letter containing no way to sign in — and nothing would report that.
    #
    # ⚠ ADMIN AND REVIEWER ARE SEEDED IDENTICALLY, ON PURPOSE. They were one template until today
    # and `{role_label}` already made the one letter read correctly for both, so identical seeds
    # are what "changes nothing anybody receives" means here. The split buys the ORGANISATION the
    # ability to make them differ — it is not a claim that they already do.
    'invite_admin': {
        'subject': 'Your access to {org_name}',
        'body': (
            'Dear {name},\n'
            '\n'
            'You have been added to {org_name} as {role_label}.\n'
            '\n'
            'Sign in here:\n'
            '{login_link}\n'
            '\n'
            '{access}\n'
            '\n'
            'The console is where {org_name}\u2019s bursary work happens: applications and where '
            'each one has got to, the students being supported, and the people who help run it. '
            'What you can see and change depends on your role, so some areas may be read-only '
            'for you.\n'
            '\n'
            'There is a guide and a set of frequently asked questions in the dashboard, under '
            'Guide and FAQ.\n'
            '\n'
            'Any trouble at all, just reply to this email.\n'
            '\n'
            'Warm regards,\n'
            '{team_signoff}'
        ),
    },
    'invite_reviewer': {
        'subject': 'Your access to {org_name}',
        'body': (
            'Dear {name},\n'
            '\n'
            'You have been added to {org_name} as {role_label}.\n'
            '\n'
            'Sign in here:\n'
            '{login_link}\n'
            '\n'
            '{access}\n'
            '\n'
            'Once you are in, you will see the applicants assigned to you. For each one you read '
            'their application and the documents they have uploaded, meet them for a short '
            'interview, and record what you find. The system proposes interview times and emails '
            'the student, so you are not chasing anybody.\n'
            '\n'
            'There is a guide and a set of frequently asked questions in the dashboard, under '
            'Guide and FAQ. They cover what to look for, how to record a verdict, and what '
            'happens after you do.\n'
            '\n'
            'If a case is not one you can take \u2014 you know the family, or the timing does '
            'not work \u2014 just reply and we will reassign it. That is a normal thing to do.\n'
            '\n'
            'Any trouble at all, just reply to this email.\n'
            '\n'
            'Warm regards,\n'
            '{team_signoff}'
        ),
    },
    # ⚠ NOTHING SENDS THIS YET — no Source Partner has a login and the page offers no way to invite
    # one. It is wording agreed ahead of the Source console (owner, 2026-08-04), and it describes
    # that console, so it must not be wired to a sender before the console exists.
    'invite_source': {
        'subject': 'Access to the {programme_name} for {org_name}',
        'body': (
            'Dear {contact_person},\n'
            '\n'
            '{org_name} has been referring students to the {programme_name}, and until now the '
            'only word you have had on how they are getting on is the summaries we email across.\n'
            '\n'
            'We would like to give {org_name} its own access, so your team can look at any time — '
            'who has applied, who is still finishing their application, and who has been awarded '
            'a bursary.\n'
            '\n'
            'Sign in here:\n'
            '{login_link}\n'
            '\n'
            '{access}\n'
            '\n'
            'Nothing about how {org_name} refers students changes, and the summary emails carry '
            'on as before.\n'
            '\n'
            'Any trouble at all, just reply to this email.\n'
            '\n'
            'Warm regards,\n'
            '{team_signoff}'
        ),
    },
    # `{note}` is the inviter's own words and is a block for the same reason `qc_comments` is:
    # a note that happens to contain a token must arrive verbatim, not be substituted.
    #
    # ⚠ THIS IS THE ORGANISATION PITCHING, NOT A PEER (owner, 2026-08-04). The sponsor-to-sponsor
    # letter — `emails.send_sponsor_referral_invite`, sent from a sponsor's own account page — says
    # "a friend is already doing this, come and join them" and is deliberately NOT shown on the
    # admin Invitations page. This one is the organisation asking a stranger, so it has to make the
    # case: what the gap is, what a gift does about it, and what happens next.
    #
    # ⚠ THE READER IS INVITED TO BECOME A **DONOR OF THE ORGANISATION**, NOT "a sponsor of" it, and
    # never a person who buys a particular student. Two settled rules meet in this paragraph:
    #   * owner, 2026-08-04 — *"They are invited to become a donor of the organisation so they could
    #     sponsor deserving students. They do not become the sponsor of the org."*
    #   * decisions.md, 2026-07-28 — a sponsor NOMINATES and the programme AWARDS. Directive
    #     framing ("your money goes to the student you pick") would make this a conduit passing
    #     earmarked money to a named beneficiary, which is a different legal animal from a charity
    #     receiving a completed gift, and it would undercut both reallocation and AutoSponsor.
    # Hence "tell us who you would like your gift to help; we follow your choice wherever we can,
    # and the final decision on each award rests with the programme" — keep all three clauses.
    #
    # ⚠ NO TAX CLAIM, EVER. HalaTuju holds no LHDN s44(6) approval, so "tax deductible" here is a
    # false statement about the reader's own tax position — the one sentence available on this
    # surface that can cost them money. `partner_comms.banned_phrases` now refuses it on save
    # (it did not until 2026-08-04, which is precisely why this letter was a risk).
    'invite_sponsor': {
        'subject': 'An invitation to become a donor of {org_name}',
        'body': (
            'Hello,\n'
            '\n'
            '{invited_by} has invited you to become a donor of {org_name}.\n'
            '\n'
            '{note}\n'
            '\n'
            'Every year, students finish school with the results to go further and no way to pay '
            'for it. A place is offered, the family works out what it would cost, and the place '
            'goes unclaimed. Closing that gap is what {org_name} is for.\n'
            '\n'
            'A donor gives to the {programme_name}, and that gift puts a student through their '
            'studies — the fees, and the ordinary costs of living away from home that quietly '
            'decide whether somebody can stay. You can see the students waiting for support and '
            'tell us who you would like your gift to help; we follow your choice wherever we can, '
            'and the final decision on each award rests with the programme.\n'
            '\n'
            'You can read how it works, and register, here:\n'
            '{link}\n'
            '\n'
            'Registering costs nothing and commits you to nothing. You will be asked to agree to '
            'our terms and confirm a few details, and we get to know you a little before anything '
            'goes ahead — the same for everybody, however they reach us.\n'
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
    """⚠ **A REWRITTEN BUILT-IN DOES NOT REACH PRODUCTION BY ITSELF** (found the hard way,
    2026-08-04). "Kept" is the right default — an org_admin may have edited the wording, and a
    deploy must never silently overwrite it — but it also means changing a body in `SEEDS` changes
    nothing anybody receives on a system where the row already exists. The stored row wins.

    That is what `--kind` is for. `--reset` alone rewrites EVERY template, which on this production
    is destructive: six rows carry real human edits. Scope the reset to the kinds you actually
    rewrote and the owner's wording survives.
    """

    help = ('Seed the partner-email templates (idempotent). --reset overwrites the wording; '
            'scope it with --kind so other templates keep their edits.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='Overwrite an existing template’s subject/body with the seed wording. '
                 'Never touches its enabled switch.',
        )
        parser.add_argument(
            '--kind', action='append', default=None, metavar='KIND',
            help='Limit the run to this kind (repeatable). ⚠ Use it with --reset: a bare --reset '
                 'rewrites every template, including any an org_admin has edited by hand.',
        )

    def handle(self, *args, **options):
        only = options.get('kind') or None
        env_reset = _env_reset_kinds()
        names = set(partner_comms.KINDS)
        unknown_kinds = sorted((set(only or ()) | set(env_reset)) - names)
        if unknown_kinds:
            self.stderr.write(f'unknown kind(s) {unknown_kinds} — nothing was written')
            return

        # Which kinds may have their stored wording OVERWRITTEN. `--reset` alone still means
        # everything (unchanged behaviour); `--kind` narrows it; the env var is how the cron
        # endpoint scopes it, since `call_command` there takes no arguments.
        if options['reset']:
            reset_kinds = set(only) if only else set(names)
        else:
            reset_kinds = set(env_reset)
        if reset_kinds:
            self.stdout.write(f'resetting wording for: {", ".join(sorted(reset_kinds))}')

        created = updated = kept = 0
        for kind in partner_comms.KINDS:
            if only and kind not in only:
                continue
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
            elif kind in reset_kinds:
                tpl.subject = seed['subject']
                tpl.body = seed['body']
                tpl.save(update_fields=['subject', 'body', 'updated_at'])
                updated += 1
                self.stdout.write(f'reset    {kind}')
            else:
                kept += 1
                self.stdout.write(f'kept     {kind} (use --reset to overwrite the wording)')
        self.stdout.write(f'\ncreated={created} reset={updated} kept={kept}')
