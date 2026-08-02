"""The reviewer emails NOBODY can edit — rendered, so at least everybody can READ them.

Request #10 gave BrightPath five reviewer emails they own: wording they can change, switches they
can turn off. These seven are the rest. They are code-owned prose, and that is deliberate — one
carries a temporary password, one goes to organisation admins as well as the reviewer, and all of
them say something operational that a wording edit could quietly break.

⚠ THE POINT OF THIS MODULE IS THAT THE PREVIEW CANNOT DRIFT FROM THE MAIL. Each entry renders
through the SAME ``emails.build_*`` function the sender calls, with sample particulars. A second
copy of the prose, kept "in sync" by hand, would be worse than showing nothing: it would tell an
org_admin something true today and false after the next edit. If you change one of these emails,
this list changes with it, because there is only one copy.

The values below are sample particulars — a made-up applicant, a made-up reference. `SAMPLE_START`
is a fixed instant rather than "now" so the rendered text is stable between reads (a preview that
changes every minute reads as unreliable, and the screen is comparing wording, not clocks).
"""

import datetime

from . import emails

#: A fixed sample interview time. Deliberately NOT `timezone.now()` — see the module docstring.
SAMPLE_START = datetime.datetime(2026, 9, 15, 10, 30, tzinfo=datetime.timezone.utc)

_SAMPLE_REVIEWER = 'Reviewer'
_SAMPLE_APPLICANT = 'the applicant'
_SAMPLE_REF = 'HT-0000'


def _welcome():
    return emails.build_partner_welcome_email(
        'reviewer@example.com', _SAMPLE_REVIEWER, 'reviewer',
        temp_password='••••••••', google=False)


def _booked():
    return emails.build_reviewer_interview_booked_email(
        reviewer_name=_SAMPLE_REVIEWER, applicant_name=_SAMPLE_APPLICANT, start=SAMPLE_START,
        meeting_url='https://meet.google.com/…', ref=_SAMPLE_REF, duration_min=30,
        calendar_invite_sent=True)


def _reminder():
    return emails.build_reviewer_interview_reminder_email(
        reviewer_name=_SAMPLE_REVIEWER, applicant_name=_SAMPLE_APPLICANT, start=SAMPLE_START,
        meeting_url='https://meet.google.com/…', when='1day', ref=_SAMPLE_REF,
        verdict_due='25/09/2026')


def _cancelled():
    return emails.build_reviewer_interview_cancelled_email(
        reviewer_name=_SAMPLE_REVIEWER, applicant_name=_SAMPLE_APPLICANT, ref=_SAMPLE_REF,
        reason='Something came up at home.')


def _alternatives():
    return emails.build_reviewer_alternatives_requested_email(
        reviewer_name=_SAMPLE_REVIEWER, applicant_name=_SAMPLE_APPLICANT, ref=_SAMPLE_REF,
        note='I have class at both of those times.')


def _student_message():
    return emails.build_reviewer_student_message_email(
        reviewer_name=_SAMPLE_REVIEWER, applicant_name=_SAMPLE_APPLICANT,
        message='I am running about ten minutes late.', ref=_SAMPLE_REF,
        interview_start=SAMPLE_START)


def _escalation():
    return emails.build_verdict_escalation_email(
        applicant_name=_SAMPLE_APPLICANT, ref=_SAMPLE_REF, reviewer_name=_SAMPLE_REVIEWER,
        due_by='25/09/2026')


#: ``(key, builder)`` in the order the screen reads them: joining, then the interview in sequence,
#: then the one that is not about an interview at all.
SYSTEM_EMAILS = (
    ('partner_welcome', _welcome),
    ('interview_booked', _booked),
    ('interview_reminder', _reminder),
    ('interview_cancelled', _cancelled),
    ('alternatives_requested', _alternatives),
    ('student_message', _student_message),
    ('verdict_escalation', _escalation),
)

#: Keys whose email carries something an org_admin should notice. `partner_welcome` carries a new
#: reviewer's temporary password — the sample shows dots, never a real one.
SENSITIVE_KEYS = frozenset({'partner_welcome'})

#: Keys that reach somebody besides the reviewer. The escalation also goes to the organisation's
#: own admins, which is exactly the sort of fact that is invisible until it surprises somebody.
WIDER_AUDIENCE_KEYS = frozenset({'verdict_escalation'})


def rendered():
    """Every system reviewer email as ``{key, subject, body, sensitive, wider_audience}``.

    A builder that raises is skipped rather than taking the screen down with it — this is a
    reference list, and half a list beats an error page on a working Emails tab.
    """
    out = []
    for key, build in SYSTEM_EMAILS:
        try:
            subject, body = build()
        except Exception:  # pragma: no cover - defensive; a builder has no reason to raise
            continue
        out.append({
            'key': key,
            'subject': subject,
            'body': body,
            'sensitive': key in SENSITIVE_KEYS,
            'wider_audience': key in WIDER_AUDIENCE_KEYS,
        })
    return out
