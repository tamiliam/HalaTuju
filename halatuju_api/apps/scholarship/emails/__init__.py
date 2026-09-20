"""
Trilingual emails for the BrightPath Bursary Programme.

Phase 1 uses email (every HalaTuju account has a verified Google address).
WhatsApp is a Phase 2 enhancement.

⚠ THIS IS A RE-EXPORT SHELL AND NO CODE (code health H16, 2026-09-20). `emails.py` was 4,242
lines; its bodies are the modules beside this file, every line byte-identical to the line it
came from. Import from `apps.scholarship.emails` exactly as before — every name the old
module defined is re-exported here, and no importing file was changed.

Two things to know before you edit anything here:

⛔ THE EMAIL GOLDEN MASTER (`tests/test_email_branding.py`) pins the rendered bytes of every
`send_*`. It stayed byte-unchanged through this split and it is the whole safety net for this
package. NEVER set `UPDATE_EMAIL_GOLDEN` to make a failure go away — a change there is a
change to what a student receives, and it needs the owner, not an environment variable.

⚠ A `mock.patch('apps.scholarship.emails.<dependency>')` string may no longer resolve. This
shell re-exports what the old module DEFINED, not what it imported, and a send primitive
(`_send`, `_send_html`, `_send_plain`) is now an attribute of the module that READS it —
patching it here rebinds only this shell and the real send still happens. Patch it where it
lives: `emails.student_decisions._send`, `emails.sending._send_html`, and so on. Search for
`patch.object(emails, ...)` as well as the dotted string; they are the same hazard.

The import order below is the dependency order the cut computed, and it is acyclic. Keep it
that way: `shared` first (the branding seam and the logger), then `sending` and
`student_decisions` (the primitives), then everything that builds on them.
"""

# ⚠ The logger keeps its ORIGINAL name, `apps.scholarship.emails`, set EXPLICITLY in
# `shared.py` rather than from `__name__`. The Cloud Logging scrape metric counts by logger
# name, so a submodule taking `__name__` would move every audit line off the metric with
# nothing going red (H11, and again at H15). `AuditLoggerNameTest` holds this.

from .shared import (
    SUPPORT_EMAIL, _DEFAULT_NAME, _P, _PROG_EN, _PROG_MS, _TEAM_EN, _TEAM_MS, _meter_email,
    logger
)
from .invoice_mail import send_invoice_email, send_invoicing_alert_email
from .ops_alerts import send_profile_complete_admin_email, send_vision_outage_alert_email
from .org_request_mail import (
    _fmt_hours, _org_request_link, _requests_owner_email, send_org_request_accepted_email,
    send_org_request_answered_email, send_org_request_questions_email,
    send_org_request_quote_email, send_org_request_submitted_email,
    send_sponsor_interest_admin_email
)
from .payment_mail import (
    _rm_amount, _run_month_label, _run_totals, send_payment_countersign_email,
    send_payment_finance_check_email, send_payment_run_email
)
from .sending import (
    _email_button, _fmt_myt, _fmt_myt_time, _gcal_url, _html_email_shell, _interview_ics,
    _interview_unsub_headers, _join_line, _send_bilingual, _send_html, _send_plain,
    english_only_email
)
from .spend_alerts import send_spending_alert_email, send_vircle_wallet_alert_email
from .student_decisions import (
    ACK_BODIES, ACK_SUBJECTS, AWARD_CONFIRMED_BODIES, AWARD_CONFIRMED_SUBJECTS, FAIL_BODIES,
    FAIL_SUBJECTS, INTERVIEW_BODIES, INTERVIEW_SUBJECTS, MERIT_BODIES, MERIT_SUBJECTS,
    NEED_BODIES, NEED_SUBJECTS, PASS_BODIES, PASS_SUBJECTS, SUBMISSION_ACK_BODIES,
    SUBMISSION_ACK_SUBJECTS, _DECLINE_TEMPLATES, _send, normalise_lang,
    send_acknowledgement_email, send_award_confirmed_email, send_pass_email,
    send_submission_received_email
)
from .decline_mail import _decline_html, send_decline_email
from .interview_mail import (
    send_interview_booked_email, send_interview_cancelled_email, send_interview_released_email,
    send_interview_reminder_email, send_interview_slots_proposed_email
)
from .referral_mail import (
    REFERRAL_INVITE_BODIES, REFERRAL_INVITE_SUBJECTS, _REFERRAL_NOTE_PREFIX,
    send_sponsor_referral_invite
)
from .reviewer_mail import (
    _ADMIN_WELCOME_BODY, _PARTNER_ROLE_LABELS, _REVIEWER_LEGACY, _REVIEWER_SENT,
    _REVIEWER_SIGNOFF, _REVIEWER_STOPPED, _REVIEWER_WELCOME_BODY, _invite_kind_for_role,
    _invite_render, _reviewer_dashboard_cta, _reviewer_render, _reviewer_subject,
    _welcome_access_block, build_partner_welcome_email, send_partner_welcome_email,
    send_qc_rejected_email, send_qc_returned_email, send_reviewer_assigned_email
)
from .signing import (
    AGREEMENT_EXECUTED_BODIES, AGREEMENT_EXECUTED_SUBJECTS, SIGN_INVITE_BODIES,
    SIGN_INVITE_SUBJECTS, send_agreement_executed_email, send_countersign_pending_email,
    send_executed_copy_email, send_partner_email, send_sign_invitation_email, send_sponsor_email,
    send_witness_pending_email
)
from .sponsor_cards import (
    FIELD_IMAGE_BASE, FIELD_IMAGE_CONCEPT_BASE, SPONSOR_DIGEST_SUBJECTS, SPONSOR_NEW_SUBJECTS,
    _SPONSOR_ACCOUNT, _SPONSOR_CTA, _SPONSOR_DIGEST_INTRO, _SPONSOR_FOOTER, _SPONSOR_FREQ_WORD,
    _SPONSOR_GREETING, _SPONSOR_GREETING_GENERIC, _SPONSOR_HOOK, _SPONSOR_NEW_INTRO,
    _SPONSOR_READ_STORY, _SPONSOR_REGISTERS, _SPONSOR_SIGNOFF, _acad_score, _facts_bits,
    _field_image_url, _pick_standout, _programme_of, _registers_line, _rm_whole,
    _send_sponsor_notify, _sponsor_card_html, _sponsor_card_text, _sponsor_email_max_cards,
    _sponsor_subject, _tax_name_map, send_sponsor_digest_email, send_sponsor_new_student_email
)
from .student_notices import (
    send_application_nudge_email, send_contact_submission_admin_email,
    send_profile_complete_student_email, send_student_assigned_reviewer_email
)
from .student_queries import (
    QUERY_RAISED_BODIES, QUERY_RAISED_SUBJECTS, QUERY_REMINDER_BODIES, QUERY_REMINDER_SUBJECTS,
    REQUEST_INFO_BODIES, REQUEST_INFO_SUBJECTS, send_query_raised_email,
    send_query_reminder_email, send_request_info_email
)
from .student_reminders import (
    CLOSED_BODIES, CLOSED_SUBJECTS, CLOSURE_HELP, HELP_LINE, REMINDER_BODIES, REMINDER_SUBJECTS,
    _help_line, send_application_closed_email, send_reminder_email
)
from .vircle_install import (
    VIRCLE_CTA_LABELS, VIRCLE_INSTALL_BODIES, VIRCLE_INSTALL_SUBJECTS, _VIRCLE_BOLD_PHRASES,
    _VIRCLE_GUIDE_FILENAME, _VIRCLE_GUIDE_PATH, _VIRCLE_LINK_PHRASES,
    _vircle_guide_bytes_from_asset, _vircle_guide_bytes_from_drive, _vircle_install_html,
    send_vircle_install_email, vircle_guide_attachment
)
from .award_offer import (
    AWARD_OFFER_BODIES, AWARD_OFFER_GUARDIAN_NOTES, AWARD_OFFER_SIGN_BODIES,
    AWARD_OFFER_SIGN_SUBJECTS, AWARD_OFFER_SUBJECTS, _BOLD_PHRASES, _award_offer_html,
    send_award_offer_email, send_award_offer_sign_email
)
from .invitation_mail import (
    build_source_invitation_email, build_sponsor_invitation_email, send_sponsor_invitation_email
)
from .reviewer_interviews import (
    build_reviewer_alternatives_requested_email, build_reviewer_interview_booked_email,
    build_reviewer_interview_cancelled_email, build_reviewer_interview_reminder_email,
    build_reviewer_student_message_email, build_verdict_escalation_email,
    send_reviewer_alternatives_requested_email, send_reviewer_interview_booked_email,
    send_reviewer_interview_cancelled_email, send_reviewer_interview_reminder_email,
    send_reviewer_student_message_email, send_reviewer_verdict_due_email,
    send_verdict_escalation_email
)

__all__ = [n for n in dir() if not n.startswith("__")]
