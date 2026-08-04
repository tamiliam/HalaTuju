"""The reviewer emails NOBODY can edit — rendered, so at least everybody can READ them.

Request #10 gave BrightPath five reviewer emails they own: wording they can change, switches they
can turn off. These six are the rest. They are code-owned prose, and that is deliberate — one goes
to organisation admins as well as the reviewer, and all of them say something operational that a
wording edit could quietly break.

⚠ **SIX, NOT SEVEN, SINCE 2026-08-04.** The joining email left this list when it became editable
under Organisation → Invitations; see the note on `SYSTEM_EMAILS`.

⚠ THE POINT OF THIS MODULE IS THAT THE PREVIEW CANNOT DRIFT FROM THE MAIL. Each entry renders
through the SAME ``emails.build_*`` function the sender calls. A second copy of the prose, kept
"in sync" by hand, would be worse than showing nothing: it would tell an org_admin something true
today and false after the next edit. If you change one of these emails, this list changes with it,
because there is only one copy.

⚠ **EACH ONE IS RENDERED TWICE — the SHAPE and an EXAMPLE** (owner, 2026-08-04). The list used to
show only worked samples, so a reader met `HT-0000` and a September date with no way to tell which
parts were real and which were filled in per send. Now the primary render substitutes `{ref}`,
`{applicant_name}`, `{interview_time}` and friends, and the sample sits beside it. **Both go
through the same builder**, so the anti-drift guarantee is untouched — the tokens are simply what
we pass as the particulars.

The sample values are a made-up applicant and reference. `SAMPLE_START` is a fixed instant rather
than "now" so the rendered text is stable between reads (a preview that changes every minute reads
as unreliable, and the screen is comparing wording, not clocks).
"""

import datetime

from . import emails

#: A fixed sample interview time. Deliberately NOT `timezone.now()` — see the module docstring.
SAMPLE_START = datetime.datetime(2026, 9, 15, 10, 30, tzinfo=datetime.timezone.utc)

#: The worked example: what one real send looks like.
SAMPLE = {
    'reviewer_name': 'Reviewer',
    'applicant_name': 'the applicant',
    'ref': 'HT-0000',
    'start': SAMPLE_START,
    'meeting_url': 'https://meet.google.com/…',
    'verdict_due': '25/09/2026',
    'cancel_reason': 'Something came up at home.',
    'alternatives_note': 'I have class at both of those times.',
    'student_message': 'I am running about ten minutes late.',
}

#: The SHAPE: the same fields, each carrying its own name.
#:
#: ⚠ `start` is a STRING here and reaches `emails._fmt_myt`, which passes an already-formatted
#: value through untouched. That one line in the formatter exists for this and nothing else — see
#: its docstring. Without it the token render would raise on the format spec and this catalogue
#: would need its own copy of the prose, which is the single thing it exists to avoid.
TOKENS = {
    'reviewer_name': '{reviewer_name}',
    'applicant_name': '{applicant_name}',
    'ref': '{ref}',
    'start': '{interview_time}',
    'meeting_url': '{meeting_link}',
    'verdict_due': '{verdict_due}',
    'cancel_reason': '{reason_they_gave}',
    'alternatives_note': '{note_they_wrote}',
    'student_message': '{their_message}',
}


def _booked(v):
    return emails.build_reviewer_interview_booked_email(
        reviewer_name=v['reviewer_name'], applicant_name=v['applicant_name'], start=v['start'],
        meeting_url=v['meeting_url'], ref=v['ref'], duration_min=30, calendar_invite_sent=True)


def _reminder(v):
    return emails.build_reviewer_interview_reminder_email(
        reviewer_name=v['reviewer_name'], applicant_name=v['applicant_name'], start=v['start'],
        meeting_url=v['meeting_url'], when='1day', ref=v['ref'], verdict_due=v['verdict_due'])


def _cancelled(v):
    return emails.build_reviewer_interview_cancelled_email(
        reviewer_name=v['reviewer_name'], applicant_name=v['applicant_name'], ref=v['ref'],
        reason=v['cancel_reason'])


def _alternatives(v):
    return emails.build_reviewer_alternatives_requested_email(
        reviewer_name=v['reviewer_name'], applicant_name=v['applicant_name'], ref=v['ref'],
        note=v['alternatives_note'])


def _student_message(v):
    return emails.build_reviewer_student_message_email(
        reviewer_name=v['reviewer_name'], applicant_name=v['applicant_name'],
        message=v['student_message'], ref=v['ref'], interview_start=v['start'])


def _escalation(v):
    return emails.build_verdict_escalation_email(
        applicant_name=v['applicant_name'], ref=v['ref'], reviewer_name=v['reviewer_name'],
        due_by=v['verdict_due'])


#: ``(key, builder)`` in the order the screen reads them: the interview in sequence, then the one
#: that is not about an interview at all.
#:
#: ⚠ `partner_welcome` WAS THE FIRST ENTRY AND WAS REMOVED ON 2026-08-04 (owner). The joining email
#: became editable under Organisation → Invitations the day before, so it was appearing in two
#: places at once — read-only here, editable there — which is worse than either alone: an org_admin
#: reading this list would conclude the wording was fixed. Invitations own it now. **Do not restore
#: it here**; if a reviewer-facing preview of the joining letter is ever wanted again, link to the
#: Invitations tab rather than rendering a second copy.
SYSTEM_EMAILS = (
    ('interview_booked', _booked),
    ('interview_reminder', _reminder),
    ('interview_cancelled', _cancelled),
    ('alternatives_requested', _alternatives),
    ('student_message', _student_message),
    ('verdict_escalation', _escalation),
)

#: Keys whose email carries something an org_admin should notice — a temporary password, say. EMPTY
#: since `partner_welcome` left (2026-08-04), and kept rather than deleted because it is the
#: mechanism, not the list: the next code-owned email carrying a credential needs a home to be
#: flagged from, and rebuilding this later is how one ships unflagged.
SENSITIVE_KEYS = frozenset()

#: Keys that reach somebody besides the reviewer. The escalation also goes to the organisation's
#: own admins, which is exactly the sort of fact that is invisible until it surprises somebody.
WIDER_AUDIENCE_KEYS = frozenset({'verdict_escalation'})


def rendered():
    """Every system reviewer email, as the SHAPE plus a worked example.

    ``{key, subject, body, sample_subject, sample_body, sensitive, wider_audience}`` — `subject`
    and `body` carry the tokens, so a reader sees which parts are filled in per send.

    A builder that raises is skipped rather than taking the screen down with it — this is a
    reference list, and half a list beats an error page on a working Emails tab.
    """
    out = []
    for key, build in SYSTEM_EMAILS:
        try:
            subject, body = build(TOKENS)
            sample_subject, sample_body = build(SAMPLE)
        except Exception:  # pragma: no cover - defensive; a builder has no reason to raise
            continue
        out.append({
            'key': key,
            'subject': subject,
            'body': body,
            'sample_subject': sample_subject,
            'sample_body': sample_body,
            'sensitive': key in SENSITIVE_KEYS,
            'wider_audience': key in WIDER_AUDIENCE_KEYS,
        })
    return out
