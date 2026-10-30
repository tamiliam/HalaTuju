"""EVERY email the platform sends to a STUDENT, from applying to the end of her file — as data
(student maintenance S6a, 2026-10-30; owner rulings the same day).

The owner's ask: "All [student communications] should be [documented], under proper headings ... If
there is an option to switch on and off the comms (provided it won't break the workflow), the switch
could be provided there itself." This module is the one list Organisation → Settings → Student
communications reads, and the one place that says which of them an organisation may silence.

Each entry says:

  * ``group``      — the heading it sits under (``GROUPS``, in the order the page reads);
  * ``senders``    — the ``send_*`` function(s) that send it. The meter (`emails.shared._meter_email`)
                     names each usage row after the nearest ``send_*`` caller, so these names are also
                     how "last sent" is read back out of `usage_events`;
  * ``status``     — when two entries share a sender, the application status that tells them apart
                     (the closed notice: ``expired`` = the reminder sweep, ``closed`` = an officer);
  * ``languages``  — ``en_ms_ta`` (one email in her language), ``en_ms`` (English, or English with a
                     Malay mirror, in ONE email — the interview family), ``en`` (English only);
  * ``switchable`` — the owner's list (rows 4, 12, 13/14, 15, 19, 26-28 of the S6 pre-flight; 23,
                     award confirmed, was locked by the owner on 2026-10-30 — it carries her onboarding link).
                     Everything else has a ``lock`` — a reason code the page words — because it
                     carries a credential, a decision, an offer, or a clock or stamp a workflow waits on;
  * ``flag``       — ``(setting, sends_when)``: the platform env switch that OUTRANKS the
                     organisation's. It is read at the send site, before `may_send`;
  * ``tracked``    — ``'meter'`` (last sent from `usage_events`), ``'log'`` (`StudentEmailLog`, the
                     organisation-worded family) or ``None`` (we cannot say per organisation);
  * ``wording``    — ``(module, subjects, bodies)`` in `apps.scholarship.emails` when the email's copy
                     is a plain per-language dict: the page shows THAT dict, so it cannot drift from
                     the mail (the `reviewer_system_emails` rule). ``None`` when the copy is built in
                     code (the page says so) or is the organisation's own (``editable``).

⚠ A NEW STUDENT EMAIL MUST BE ADDED HERE. `test_student_email_catalogue` partitions every ``send_*``
function in `apps.scholarship.emails` into this list or ``NOT_STUDENT_SENDERS``; an unlisted one
fails the suite, so no student mail ships undocumented — and none ships switchable by accident.
"""
import logging
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger('apps.scholarship.student_email_catalogue')

GROUPS = ('account', 'applying', 'interview', 'award', 'results', 'closure')


@dataclass(frozen=True)
class Entry:
    key: str
    group: str
    senders: tuple = ()
    status: str = ''
    languages: str = 'en_ms_ta'
    switchable: bool = False
    lock: str = ''
    flag: tuple = ()
    tracked: str = 'meter'
    wording: tuple = ()
    editable: bool = False
    managed_on: str = ''


_E = Entry
_FLAG_CHECK2 = ('CHECK2_STUDENT_QUERIES_ENABLED', True)
_FLAG_INTERVIEW = ('INTERVIEW_SCHEDULING_ENABLED', True)
_FLAG_CONTRACT = ('BURSARY_AGREEMENT_ENABLED', True)
_FLAG_RESULTS = ('MAINTENANCE_REMINDERS_ENABLED', True)

CATALOGUE = (
    # ── Account ─────────────────────────────────────────────────────────────────────────────
    _E('verify_email', 'account', lock='credential', tracked=None),        # courses.views: bare send_mail
    _E('claim_code', 'account', ('send_claim_code_email',), lock='credential', tracked=None),  # no org
    _E('sign_in', 'account', lock='outside_platform', languages='en', tracked=None),          # Supabase Auth
    # ── Applying ────────────────────────────────────────────────────────────────────────────
    _E('application_received', 'applying', ('send_acknowledgement_email',), switchable=True,
       wording=('student_decisions', 'ACK_SUBJECTS', 'ACK_BODIES')),
    _E('shortlisted', 'applying', ('send_pass_email',), lock='next_step',
       wording=('student_decisions', 'PASS_SUBJECTS', 'PASS_BODIES')),
    _E('declined', 'applying', ('send_decline_email',), lock='decision',
       wording=('student_decisions', 'FAIL_SUBJECTS', 'FAIL_BODIES')),
    _E('completion_reminders', 'applying', ('send_reminder_email',), lock='close_warning'),
    _E('application_expired', 'applying', ('send_application_closed_email',), status='expired',
       lock='closure_notice', wording=('student_reminders', 'CLOSED_SUBJECTS', 'CLOSED_BODIES')),
    _E('submit_nudge', 'applying', ('send_application_nudge_email',), languages='en_ms',
       lock='officer_unlock'),
    _E('info_requested', 'applying', ('send_request_info_email',), lock='officer_request',
       wording=('student_queries', 'REQUEST_INFO_SUBJECTS', 'REQUEST_INFO_BODIES')),
    _E('questions_raised', 'applying', ('send_query_raised_email',), lock='action_needed',
       flag=_FLAG_CHECK2, wording=('student_queries', 'QUERY_RAISED_SUBJECTS', 'QUERY_RAISED_BODIES')),
    _E('question_reminder', 'applying', ('send_query_reminder_email',), switchable=True,
       flag=_FLAG_CHECK2,
       wording=('student_queries', 'QUERY_REMINDER_SUBJECTS', 'QUERY_REMINDER_BODIES')),
    _E('submission_received', 'applying', ('send_submission_received_email',), switchable=True,
       flag=('PROFILE_COMPLETE_EMAIL_ENABLED', False),
       wording=('student_decisions', 'SUBMISSION_ACK_SUBJECTS', 'SUBMISSION_ACK_BODIES')),
    _E('profile_complete', 'applying', ('send_profile_complete_student_email',), languages='en_ms',
       switchable=True, flag=('PROFILE_COMPLETE_EMAIL_ENABLED', True)),
    # ── Interview ───────────────────────────────────────────────────────────────────────────
    _E('interviewer_assigned', 'interview', ('send_student_assigned_reviewer_email',),
       languages='en_ms', switchable=True, flag=('STUDENT_ASSIGNMENT_EMAIL_ENABLED', True)),
    # Its wording AND its switch live on Sources (`PartnerEmailTemplate.student_assigned`); the page
    # links there rather than showing a second copy (the reviewer panel's 2026-08-04 rule).
    _E('partner_access', 'interview', languages='en', lock='managed_elsewhere', tracked=None,
       managed_on='sources'),
    _E('interview_times', 'interview', ('send_interview_slots_proposed_email',), languages='en_ms',
       lock='action_needed', flag=_FLAG_INTERVIEW),
    _E('interview_booked', 'interview', ('send_interview_booked_email',), languages='en_ms',
       lock='join_link', flag=_FLAG_INTERVIEW),
    _E('interview_reminders', 'interview', ('send_interview_reminder_email',), languages='en_ms',
       switchable=True, flag=_FLAG_INTERVIEW),
    _E('interview_cancelled', 'interview',
       ('send_interview_cancelled_email', 'send_interview_released_email'), languages='en_ms',
       lock='cancellation', flag=_FLAG_INTERVIEW),
    # ── Award and contract ──────────────────────────────────────────────────────────────────
    _E('award_offer', 'award', ('send_award_offer_email', 'send_award_offer_sign_email'), lock='offer',
       wording=('award_offer', 'AWARD_OFFER_SUBJECTS', 'AWARD_OFFER_BODIES')),
    _E('sign_invitation', 'award', ('send_sign_invitation_email',), lock='offer_clock',
       flag=_FLAG_CONTRACT, wording=('signing', 'SIGN_INVITE_SUBJECTS', 'SIGN_INVITE_BODIES')),
    # LOCKED (owner, 2026-10-30, S6a review): on the live path it carries her onboarding link.
    _E('award_confirmed', 'award', ('send_award_confirmed_email',), lock='next_step',
       flag=('BURSARY_AGREEMENT_ENABLED', False),
       wording=('student_decisions', 'AWARD_CONFIRMED_SUBJECTS', 'AWARD_CONFIRMED_BODIES')),
    _E('agreement_executed', 'award', ('send_agreement_executed_email',), lock='contract_copy',
       flag=_FLAG_CONTRACT,
       wording=('signing', 'AGREEMENT_EXECUTED_SUBJECTS', 'AGREEMENT_EXECUTED_BODIES')),
    _E('vircle_setup', 'award', ('send_vircle_install_email',), lock='wallet_task',
       wording=('vircle_install', 'VIRCLE_INSTALL_SUBJECTS', 'VIRCLE_INSTALL_BODIES')),
    # ── Results (the organisation's own wording, `student_comms`) ───────────────────────────
    _E('results_due', 'results', switchable=True, flag=_FLAG_RESULTS, tracked='log', editable=True),
    _E('results_overdue', 'results', switchable=True, flag=_FLAG_RESULTS, tracked='log', editable=True),
    _E('result_queried', 'results', switchable=True, flag=_FLAG_RESULTS, tracked='log', editable=True),
    # ── Closure ─────────────────────────────────────────────────────────────────────────────
    _E('closed_by_officer', 'closure', ('send_application_closed_email',), status='closed',
       lock='closure_notice', wording=('student_reminders', 'CLOSED_SUBJECTS', 'CLOSED_BY_OFFICER_BODIES')),
)

BY_KEY = {e.key: e for e in CATALOGUE}
SWITCHABLE = frozenset(e.key for e in CATALOGUE if e.switchable)

#: Every other ``send_*`` in `apps.scholarship.emails`: its recipient is NOT the student (a reviewer,
#: a sponsor, a partner, the organisation's staff or the platform owner). The drift test partitions
#: the package between this set and `CATALOGUE`; a sender in neither fails it.
NOT_STUDENT_SENDERS = frozenset({
    'send_reviewer_assigned_email', 'send_partner_welcome_email', 'send_qc_returned_email',
    'send_qc_rejected_email', 'send_reviewer_interview_booked_email',
    'send_reviewer_interview_reminder_email', 'send_reviewer_alternatives_requested_email',
    'send_reviewer_student_message_email', 'send_reviewer_interview_cancelled_email',
    'send_reviewer_verdict_due_email', 'send_verdict_escalation_email',
    'send_sponsor_interest_admin_email', 'send_org_request_submitted_email',
    'send_org_request_questions_email', 'send_org_request_answered_email',
    'send_org_request_quote_email', 'send_org_request_accepted_email',
    'send_sponsor_referral_invite', 'send_vision_outage_alert_email', 'send_profile_complete_admin_email',
    'send_payment_countersign_email', 'send_payment_finance_check_email', 'send_payment_run_email',
    'send_executed_copy_email', 'send_witness_pending_email', 'send_countersign_pending_email',
    'send_sponsor_email', 'send_spending_alert_email', 'send_vircle_wallet_alert_email',
    'send_contact_submission_admin_email', 'send_sponsor_invitation_email',
    'send_source_invitation_email',     # a source's person (source sign-in S2)
    'send_sponsor_new_student_email', 'send_sponsor_digest_email', 'send_invoice_email',
    'send_receipt_email', 'send_payment_declared_email', 'send_invoicing_alert_email',
    # `send_partner_email` is the shared partner sender. Its ONE student-facing use (the partner
    # access notice) is `partner_access` above, managed on Sources.
    'send_partner_email',
})


class NotSwitchable(Exception):
    """A switch was asked of an email that is not on the owner's list (or does not exist)."""


def flag_on(entry):
    """Does the platform env flag let this email go? True when it has none."""
    if not entry.flag:
        return True
    name, sends_when = entry.flag
    return bool(getattr(settings, name, False)) is sends_when


def _org_id(application_or_org):
    """The organisation's id without loading it: an application's `owning_organisation_id`, else the
    organisation's own pk (review L4: the interview job calls this once per due reminder)."""
    if hasattr(application_or_org, 'owning_organisation_id'):
        return application_or_org.owning_organisation_id
    return getattr(application_or_org, 'pk', None)


def may_send(application_or_org, key):
    """THE ONE GATE every switchable email's send site asks. True unless the email is on the owner's
    list AND its organisation has switched it off. An email that is not switchable always answers
    True — its lock is the statement that it goes. An unknown key raises (a typo is a bug, not a
    silent send).

    ⚠ BEST-EFFORT (review L2): a failure reading the switch LOGS and answers True. These are notices
    the student would otherwise receive, so a broken read must never silence her — and must never
    raise into a submit, a confirm or a sweep."""
    entry = BY_KEY[key]
    if not entry.switchable:
        return True
    try:
        org_id = _org_id(application_or_org)
        if org_id is None:
            return True
        from .models import StudentEmailSwitch
        row = (StudentEmailSwitch.objects.filter(organisation_id=org_id, key=key)
               .values_list('enabled', flat=True).first())
        return True if row is None else bool(row)
    except Exception:   # see the docstring: a broken read sends, never raises
        logger.exception('student_email_catalogue.may_send failed (key=%s); sending', key)
        return True


def set_switch(organisation, key, enabled, *, by_email=''):
    """Store the organisation's on/off for ``key``. Refuses anything not on the owner's list."""
    if key not in SWITCHABLE or not isinstance(enabled, bool):
        raise NotSwitchable(key)
    from .models import StudentEmailSwitch
    StudentEmailSwitch.objects.update_or_create(
        organisation=organisation, key=key,
        defaults={'enabled': enabled, 'updated_by_email': (by_email or '')[:254]})


def wording(entry):
    """``{lang: {subject, body}}`` straight from the sending module's own dicts — the tokens left in
    place, so a reader sees which parts are filled in per student. ``{}`` when there is none."""
    if not entry.wording:
        return {}
    import importlib
    module_name, subjects_name, bodies_name = entry.wording
    module = importlib.import_module(f'apps.scholarship.emails.{module_name}')
    subjects, bodies = getattr(module, subjects_name), getattr(module, bodies_name)
    return {lang: {'subject': subjects[lang], 'body': bodies[lang]} for lang in ('en', 'ms', 'ta')
            if lang in subjects and lang in bodies}


def last_sent(organisation):
    """``{key: datetime}`` — when each tracked email last went to one of THIS organisation's students.

    Two reads, one query each: the meter (`usage_events`, service email, this organisation, the
    catalogue's senders — split by application status where two entries share a sender) and the
    worded family's own log (`StudentEmailLog`, successful sends only). The meter counts an ATTEMPT
    (it runs before the send), so a failed send can read as sent here; the log does not.
    """
    from django.db.models import Max
    from . import usage
    from .models import StudentEmailLog, UsageEvent
    senders = {s for e in CATALOGUE if e.tracked == 'meter' for s in e.senders}
    metered = {}
    for row in (UsageEvent.objects.filter(organisation=organisation, service=usage.EMAIL,
                                          source__in=senders)
                .values('source', 'application__status').annotate(last=Max('created_at'))):
        metered.setdefault(row['source'], []).append((row['application__status'], row['last']))
    logged = dict(StudentEmailLog.objects.filter(organisation=organisation, ok=True)
                  .values_list('key').annotate(last=Max('sent_at')))
    out = {}
    for e in CATALOGUE:
        if e.tracked == 'log':
            stamps = [logged[e.key]] if e.key in logged else []
        elif e.tracked == 'meter':
            stamps = [last for s in e.senders for status, last in metered.get(s, ())
                      if not e.status or status == e.status]
        else:
            stamps = []
        if stamps:
            out[e.key] = max(stamps)
    return out


def payload(organisation):
    """Every entry, in page order, with this organisation's switch, the platform flag and last sent."""
    from .models import StudentEmailSwitch
    switches = dict(StudentEmailSwitch.objects.filter(organisation=organisation)
                    .values_list('key', 'enabled'))
    sent = last_sent(organisation)
    rows = []
    for e in sorted(CATALOGUE, key=lambda x: GROUPS.index(x.group)):
        rows.append({
            'key': e.key, 'group': e.group, 'languages': e.languages, 'editable': e.editable,
            'switchable': e.switchable, 'enabled': switches.get(e.key, True) if e.switchable else True,
            'lock': e.lock or None, 'platform_flag': e.flag[0] if e.flag else None,
            'platform_on': flag_on(e), 'tracked': e.tracked is not None,
            'last_sent_at': sent.get(e.key), 'managed_on': e.managed_on or None,
            'wording': wording(e),
        })
    return rows
