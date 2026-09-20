"""Reviewer-side interview mail and the verdict-due / escalation chasers. The primitive they
share, `_send_plain`, is in `sending`.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from .reviewer_mail import _REVIEWER_LEGACY, _REVIEWER_SENT, _REVIEWER_SIGNOFF, _reviewer_dashboard_cta, _reviewer_render, _reviewer_subject
from .sending import _fmt_myt, _gcal_url, _send_plain
from .shared import _PROG_EN


def build_reviewer_interview_booked_email(*, reviewer_name, applicant_name, start,
                                          meeting_url='', ref='', duration_min=None,
                                          calendar_invite_sent=False):
    """The wording → ``(subject, body)``. See `build_partner_welcome_email` for why this is split."""
    applicant = applicant_name or 'An applicant'
    details = [f'When: {_fmt_myt(start)}']
    if meeting_url:
        details.append(f'Meet link: {meeting_url}')
    if calendar_invite_sent:
        calendar_line = "It's on your calendar (a Google invite has been sent) and in their record."
    else:
        from apps.courses import org_config
        gcal = _gcal_url(start=start,
                         duration_min=duration_min or org_config.default('interview_duration_min'),
                         text=f'B40 interview — {applicant}',
                         details='' + _PROG_EN + ' Programme interview.', location=meeting_url or '')
        calendar_line = (
            "The booking is in their record. Add it to your calendar so you don't lose the time:\n"
            f'Add to your calendar:\n{gcal}')
    body = (
        f'Dear {reviewer_name or "there"},\n\n'
        f'{applicant} has booked their B40 interview with you.\n\n'
        + '\n'.join(details) + '\n\n'
        f'{calendar_line}\n\n'
        f'{_reviewer_dashboard_cta()}\n\n'
        f'{_REVIEWER_SIGNOFF}'
    )
    return _reviewer_subject('Interview booked', ref), body


def send_reviewer_interview_booked_email(to_email, *, reviewer_name, applicant_name, start,
                                         meeting_url='', ref='', duration_min=None,
                                         calendar_invite_sent=False):
    """Reviewer notice that a student booked one of their proposed times. Plain EN.

    Calendar: when the Google Meet/Calendar integration is on, both parties are added to one
    auto-created event (calendar_invite_sent=True) — so we DON'T offer a manual 'add to
    calendar' link (it would double-book). When it's off, no event exists, so we include an
    'Add to your calendar' Google link so the reviewer always ends up with the time held."""
    subject, body = build_reviewer_interview_booked_email(
        reviewer_name=reviewer_name, applicant_name=applicant_name, start=start,
        meeting_url=meeting_url, ref=ref, duration_min=duration_min,
        calendar_invite_sent=calendar_invite_sent)
    return _send_plain(to_email, subject, body)


def build_reviewer_interview_reminder_email(*, reviewer_name, applicant_name, start,
                                            meeting_url='', when='1day', ref='', verdict_due=''):
    """The wording → ``(subject, body)``."""
    soon = 'tomorrow' if when == '1day' else 'in about an hour'
    details = [f'When: {_fmt_myt(start)}']
    if meeting_url:
        details.append(f'Meet link: {meeting_url}')
    verdict_line = (f'After the interview, please record your verdict — it is due by {verdict_due}.\n\n'
                    if verdict_due else '')
    body = (
        f'Dear {reviewer_name or "there"},\n\n'
        f'Your B40 interview with {applicant_name or "an applicant"} is {soon}.\n\n'
        + '\n'.join(details) + '\n\n'
        f'{verdict_line}'
        f'{_reviewer_dashboard_cta()}\n\n'
        f'{_REVIEWER_SIGNOFF}'
    )
    base = ('Reminder: your interview is tomorrow' if when == '1day'
            else 'Reminder: your interview is in 1 hour')
    return _reviewer_subject(base, ref), body


def send_reviewer_interview_reminder_email(to_email, *, reviewer_name, applicant_name, start,
                                           meeting_url='', when='1day', ref='', verdict_due=''):
    """Reviewer reminder (1 day / 1 hour before). Plain EN. A nudge only — no calendar link,
    since the time was added when it was booked. ``verdict_due`` (a date string) adds a heads-up
    that the verdict for this applicant is due by then — the interview and verdict are different
    clocks, so a reviewer juggling cases sees both (TD-131)."""
    subject, body = build_reviewer_interview_reminder_email(
        reviewer_name=reviewer_name, applicant_name=applicant_name, start=start,
        meeting_url=meeting_url, when=when, ref=ref, verdict_due=verdict_due)
    return _send_plain(to_email, subject, body)


def build_reviewer_alternatives_requested_email(*, reviewer_name, applicant_name,
                                                note='', ref=''):
    """The wording → ``(subject, body)``."""
    note_block = f'\nWhat they said:\n  "{note}"\n' if note else ''
    body = (
        f'Dear {reviewer_name or "there"},\n\n'
        f'{applicant_name or "An applicant"} says none of the interview times you proposed will '
        f'work, and has asked for other options.\n'
        f'{note_block}\n'
        f'Open their record and use "Propose alternative times" to offer a fresh set — '
        f"they'll be emailed automatically.\n\n"
        f'{_reviewer_dashboard_cta()}\n\n'
        f'{_REVIEWER_SIGNOFF}'
    )
    return _reviewer_subject('Applicant needs different interview times', ref), body


def send_reviewer_alternatives_requested_email(to_email, *, reviewer_name, applicant_name,
                                               note='', ref=''):
    """Reviewer notice that the student said none of the proposed times work and wants other
    options. Routes the request to the right person (vs a reply lost in a shared inbox). Plain EN."""
    subject, body = build_reviewer_alternatives_requested_email(
        reviewer_name=reviewer_name, applicant_name=applicant_name, note=note, ref=ref)
    return _send_plain(to_email, subject, body)


def build_reviewer_student_message_email(*, reviewer_name, applicant_name,
                                         message, ref='', interview_start=None):
    """The wording → ``(subject, body)``."""
    when_line = ''
    if interview_start is not None:
        when_line = f'Their interview is booked for {_fmt_myt(interview_start)}.\n\n'
    body = (
        f'Dear {reviewer_name or "there"},\n\n'
        f'{applicant_name or "An applicant"} sent you a message about their interview:\n\n'
        f'  "{message}"\n\n'
        f'{when_line}'
        f'If it needs a reply, open their record — you can propose new times, reschedule, '
        f'or reach them through the contact details there.\n\n'
        f'{_reviewer_dashboard_cta()}\n\n'
        f'{_REVIEWER_SIGNOFF}'
    )
    return _reviewer_subject('Message from applicant', ref), body


def send_reviewer_student_message_email(to_email, *, reviewer_name, applicant_name,
                                        message, ref='', interview_start=None):
    """Reviewer notice that the student sent them a message (the always-open channel —
    fires in any interview state, INCLUDING inside the reschedule cutoff, e.g. "I'm
    running late" an hour before the call). Plain EN; the booked interview time is
    included when known so the reviewer can judge urgency from the email alone."""
    subject, body = build_reviewer_student_message_email(
        reviewer_name=reviewer_name, applicant_name=applicant_name, message=message,
        ref=ref, interview_start=interview_start)
    return _send_plain(to_email, subject, body)


def build_reviewer_interview_cancelled_email(*, reviewer_name, applicant_name, ref='', reason=''):
    """The wording → ``(subject, body)``."""
    reason_line = f'Reason they gave: "{reason.strip()}"\n\n' if (reason or '').strip() else ''
    body = (
        f'Dear {reviewer_name or "there"},\n\n'
        f'{applicant_name or "An applicant"} has cancelled their booked B40 interview.\n\n'
        f'{reason_line}'
        f'Their application is still open — only the interview slot was released. When you\'re '
        f'ready, open their record and use "Propose alternative times" to offer new ones.\n\n'
        f'{_reviewer_dashboard_cta()}\n\n'
        f'{_REVIEWER_SIGNOFF}'
    )
    return _reviewer_subject('Applicant cancelled their interview', ref), body


def send_reviewer_interview_cancelled_email(to_email, *, reviewer_name, applicant_name, ref='', reason=''):
    """Reviewer notice that a student cancelled. Plain EN. Includes the student's reason if given."""
    subject, body = build_reviewer_interview_cancelled_email(
        reviewer_name=reviewer_name, applicant_name=applicant_name, ref=ref, reason=reason)
    return _send_plain(to_email, subject, body)


def send_reviewer_verdict_due_email(to_email, *, reviewer_name, applicant_name, ref='',
                                    due_by='', overdue=False):
    """TD-131: nudge the assigned reviewer that a verdict is due soon / now overdue. Plain EN,
    consistent reviewer style (Dear / dashboard CTA / {ref} subject / BrightPath Bursary Team)."""
    # ⚠ ONE SENDER, TWO KINDS. The stored bodies have no conditionals, and the overdue branch
    # changes the subject AND the opening sentence — so the split lives here, at the only place
    # that knows which of the two this is.
    outcome = _reviewer_render('verdict_overdue' if overdue else 'verdict_due_soon', to_email, {
        'reviewer_name': reviewer_name, 'ref': ref, 'applicant_name': applicant_name,
        'due_by': due_by,
    })
    if outcome is not _REVIEWER_LEGACY:
        return outcome is _REVIEWER_SENT
    applicant = applicant_name or 'an applicant'
    if overdue:
        lead = (f'Your verdict for {applicant} is overdue'
                + (f' — it was due {due_by}' if due_by else '') + '.')
        base = 'Verdict overdue'
    else:
        lead = (f'Your verdict for {applicant} is due soon'
                + (f' — by {due_by}' if due_by else '') + '.')
        base = 'Verdict due soon'
    body = (
        f'Dear {reviewer_name or "there"},\n\n'
        f'{lead}\n\n'
        f'Please open their record, complete your review, and record your verdict.\n\n'
        f'{_reviewer_dashboard_cta()}\n\n'
        f'{_REVIEWER_SIGNOFF}'
    )
    return _send_plain(to_email, _reviewer_subject(base, ref), body)


def build_verdict_escalation_email(*, applicant_name, ref='', reviewer_name='', due_by=''):
    """The wording → ``(subject, body)``."""
    who = reviewer_name or 'the assigned reviewer'
    body = (
        f'Hi,\n\n'
        f'A B40 verdict is overdue and has been escalated.\n\n'
        f'Reference: {ref or "—"}\n'
        f'Applicant: {applicant_name or "—"}\n'
        f'Assigned reviewer: {who}\n'
        + (f'Was due: {due_by}\n' if due_by else '')
        + f'\nIt has passed the review deadline without a recorded verdict. Please record the '
        f'verdict, or reassign the case from the admin console.\n\n'
        f'{_reviewer_dashboard_cta()}\n\n'
        f'{_REVIEWER_SIGNOFF}'
    )
    return _reviewer_subject('Overdue verdict needs attention', ref), body


def send_verdict_escalation_email(to_email, *, applicant_name, ref='', reviewer_name='',
                                  due_by=''):
    """TD-131: escalate an overdue verdict — a verdict is well past the SLA with none recorded.
    Sent to the ORGANISATION's admin(s) and the assigned reviewer (NOT platform super-admins — a
    super is not an operator inside a tenant org). Recipient-neutral wording. Plain EN."""
    subject, body = build_verdict_escalation_email(
        applicant_name=applicant_name, ref=ref, reviewer_name=reviewer_name, due_by=due_by)
    return _send_plain(to_email, subject, body)
