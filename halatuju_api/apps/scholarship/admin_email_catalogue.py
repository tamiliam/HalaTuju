"""EVERY email the platform sends to an ORGANISATION'S OWN PEOPLE about running it, as data (Team tables T4,
2026-11-03; owner ruling 9: "listed in the Admin section now; editable later").

Team -> Emails -> Admin emails reads this list (`GET admin/admin-emails/`). It is READ-ONLY: none of these
has a template row, a switch or an editor. The wording is code-owned until a later sprint makes it editable.

Each entry names:

  * ``key``     — the row's id; the web words it (`admin.team.emails.admin.kind/when/to.<key>`, en/ms/ta);
  * ``senders`` — the ``send_*`` function(s) in `apps.scholarship.emails` that send it, and which decide its
                  recipients. Each row's "who receives it" was read off THAT code (T4), not off the design
                  board, whose six lines were wrong in four places (see decisions.md "Team tables T4").

The rows describe recipients by ROLE ("the organisation admins", "the billing addresses"), never by an
address: the screen must not show anybody's inbox.

⚠ A NEW EMAIL CANNOT SKIP THIS LIST. `student_email_catalogue.NOT_STUDENT_SENDERS` names every ``send_*`` whose
recipient is not a student; `test_admin_email_catalogue` partitions THAT set into this list's senders or
``NOT_ADMIN_SENDERS`` (each with the reason it is not an organisation's admin email). The student catalogue's
own test already fails on a ``send_*`` it does not classify, so a new sender is classified twice: once for the
student, once here.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    key: str
    senders: tuple


#: In the order the screen reads: money first (it moves when somebody signs), then requests, the review
#: clock, agreements, and the bill.
CATALOGUE = (
    # Approvers who have not signed this run (`payments.eligible_approvers`); none -> the organisation
    # admins who have not signed it (`payments.fallback_approvers`).
    Entry('payment_approval', ('send_payment_countersign_email',)),
    # The `payments_check` holders who have not signed this run (`payments.eligible_checkers`).
    Entry('payment_check', ('send_payment_finance_check_email',)),
    # To VIRCLE, copied to the approver and the organisation's active org admins (`_instruction_cc`).
    Entry('payment_instruction', ('send_payment_run_email',)),
    # To the org admin who SUBMITTED the request (`req.submitted_by`).
    Entry('request_question', ('send_org_request_questions_email',)),
    Entry('request_quote', ('send_org_request_quote_email',)),
    # `send_review_nudges` escalation: the organisation's active org admins + the assigned reviewer (no org
    # admin on record -> HalaTuju's inbox). Also listed under Reviewer emails as one "we maintain".
    Entry('verdict_escalation', ('send_verdict_escalation_email',)),
    # `bursary.foundation_notify_emails`: the gift's agreement's `counterparty_notify_emails` (the
    # organisation sets them on Contracts), else HalaTuju's countersigners / inbox. Re-sent as a reminder.
    Entry('countersign_pending', ('send_countersign_pending_email',)),
    # The same addresses (and the witnessing source's contact gets its own copy).
    Entry('agreement_executed', ('send_executed_copy_email',)),
    # The bill-to inboxes frozen on the invoice (`bill_to_snapshot['emails']`).
    Entry('invoice', ('send_invoice_email',)),
    Entry('receipt', ('send_receipt_email',)),
)

BY_KEY = {e.key: e for e in CATALOGUE}

_HALATUJU = 'sent to HalaTuju, not to your team'

#: Every other non-student ``send_*``, with why it is not an organisation's admin email.
NOT_ADMIN_SENDERS = {
    # Reviewer emails (Team -> Emails -> Reviewer emails: the five editable, the six we maintain).
    'send_reviewer_assigned_email': 'reviewer email (editable)',
    'send_qc_returned_email': 'reviewer email (editable)',
    'send_qc_rejected_email': 'reviewer email (editable)',
    'send_reviewer_verdict_due_email': 'reviewer email (editable: due soon / overdue)',
    'send_reviewer_interview_booked_email': 'reviewer email (we maintain)',
    'send_reviewer_interview_reminder_email': 'reviewer email (we maintain)',
    'send_reviewer_alternatives_requested_email': 'reviewer email (we maintain)',
    'send_reviewer_student_message_email': 'reviewer email (we maintain)',
    'send_reviewer_interview_cancelled_email': 'reviewer email (we maintain)',
    # Invitations (Organisation -> Invitations -> Emails; the mentor one also on Team -> Emails).
    'send_partner_welcome_email': 'invitation (the staff joining letter)',
    'send_mentor_invitation_email': 'invitation (the mentor letter)',
    'send_source_invitation_email': "invitation (a source's person)",
    'send_sponsor_invitation_email': 'invitation (a sponsor)',
    # Sponsors, sources and partner organisations.
    'send_sponsor_referral_invite': 'to a sponsor',
    'send_sponsor_email': 'to a sponsor',
    'send_sponsor_new_student_email': 'to a sponsor',
    'send_sponsor_digest_email': 'to a sponsor',
    'send_partner_email': 'to a partner organisation or source',
    'send_witness_pending_email': "to the witnessing source's contact",
    # HalaTuju's own inbox (`ADMIN_NOTIFY_EMAIL`) — lead ruling 2026-11-03: not shown.
    'send_org_request_submitted_email': _HALATUJU,
    'send_org_request_answered_email': _HALATUJU,
    'send_org_request_accepted_email': _HALATUJU,
    'send_profile_complete_admin_email': _HALATUJU,
    'send_contact_submission_admin_email': _HALATUJU,
    'send_sponsor_interest_admin_email': _HALATUJU,
    'send_vision_outage_alert_email': _HALATUJU,
    'send_spending_alert_email': _HALATUJU,
    'send_vircle_wallet_alert_email': _HALATUJU,
    'send_payment_declared_email': _HALATUJU,
    'send_invoicing_alert_email': _HALATUJU,
}


def rows():
    """What the Team page draws: the keys, in order. No recipient address, no organisation data."""
    return [{'key': e.key} for e in CATALOGUE]
