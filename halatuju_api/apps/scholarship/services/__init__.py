"""
Business logic for B40 Assistance Programme intake.

Pure-ish functions kept out of the view (mirrors apps/courses/eligibility_service.py).
"""

# ── THE services PACKAGE (code health H15, 2026-09-20) ───────────────────────────
# This file holds NO code. Every function, class and constant that used to live here
# was moved VERBATIM into a module beside it, and every module-level name each one
# defines is re-exported below — so `from apps.scholarship.services import <anything>`
# and `services.<anything>` still resolve exactly as they did. 69 names are imported
# from here by 21 files, plus 21 more that import this module as an object; not one of
# them changed.
#
# ⚠ WHAT IS NO LONGER AN ATTRIBUTE OF THIS MODULE. The old import block at the top of
# this file put `timezone`, `parse_date`, `timedelta`, `ScholarshipApplication` and the
# five `send_*_email` senders into this namespace, and a
# `mock.patch('apps.scholarship.services.<dep>')` string addressed them here. Those
# dependencies now live in the module that READS them, so a patch string must name that
# module — `…services.confirmation.send_profile_complete_admin_email`, not
# `…services.send_profile_complete_admin_email`. H15 moved the nine such strings that
# patch a dependency a moved body reads. The two that patch a name looked up through
# THIS module at call time (`serializers_admin` re-imports `is_ready_for_assignment`
# inside the method; the cron dispatcher does `getattr(services, job)`) still work and
# were left alone.
#
# ⛔ `application_completeness` lives in `completeness.py` and was moved BYTE-IDENTICALLY.
# Its legacy document-type arm is deliberately more permissive and may only ever widen;
# replacing it un-submits students and nulls `requirements_snapshot` (H8).
#
# count_spm_a_grades + the A-grade set live with the shortlisting engine (the single
# place that scores academics). Re-exported here for callers that still import it from
# services — as they did before the split.
from .. import requirements
from ..shortlisting import A_GRADES, count_spm_a_grades, evaluate  # noqa: F401

from .errors import (
    AmbiguousOpenCohort, AssignmentError, IncompleteProfileError, OnboardingError,
    PauseError, RoundFinishedError,
)
from .constants import (
    ONBOARDING_CONSENT_TYPE, POST_SHORTLIST_EDITABLE,
)
from .profile_sync import (
    _APP_FIELDS, _PROFILE_ABOUTME_FIELDS, _PROFILE_WRITEBACK_FIELDS,
    build_intake_snapshot, sync_profile_fields,
)
from .queries_sla import (
    QUERY_SLA_ACTIVE_STATUSES, is_ready_for_assignment, open_clarify_queries,
    open_student_tasks, query_sla, query_sla_days,
)
from .blockers import (
    _IC_DECODE_ERROR_MARKERS, _INCOME_CLUSTER_DOC_TYPES, _offer_blocks,
    detect_vision_outage, document_red_blockers, document_unreadable_blockers,
    ic_identity_blockers, income_doc_blockers, is_ic_decode_error,
    reprocess_unread_ic_documents,
)
from .completeness import (
    _family_done, _guardian_docs_done, application_completeness,
)
from .consent_blockers import (
    consent_blockers,
)
from .intake import (
    create_application, release_decision, rescore_pending_decisions,
    resolve_open_cohort, resolve_programme_by_code, score_application,
)
from .reminders import (
    FINAL_REMINDER_GRACE_DAYS, REMINDER_THRESHOLDS_DAYS, _elapsed_days_local,
    send_application_reminders,
)
from .ready_profiles import (
    autogenerate_ready_profiles, generate_ready_profile,
)
from .assignment import (
    ASSIGNABLE_STATUSES, REVIEW_ROLES, _UNASSIGN_BLOCKED_STATUSES, _can_review,
    assign_reviewer, is_assignable, reconcile_income_route, set_paused,
    switch_income_route,
)
from .query_emails import (
    QUERY_EMAIL_DELAY_HOURS, _query_email_due_window, bump_query_notify_on_new_item,
    send_due_query_emails, send_query_reminders,
)
from .decline import (
    CASE_CLOSED_STATES, INTERVIEW_REJECT_FROM, ORG_REJECT_FROM, _finalise_reject,
    _record_reject, _send_decline_for, admin_reject, cancel_pending_decline,
    org_admin_reject, release_pending_declines, review_writes_closed,
)
from .confirmation import (
    confirm_pathway, confirm_profile,
)
from .offer_sync import (
    autofill_pathway_from_offer, revert_if_profile_incomplete,
    set_reporting_date_by_officer, sync_institution_from_catalogue,
    sync_reporting_date_from_offer,
)
from .querying import (
    AUTO_QUERY_STATUSES, OFFICER_QUERY_STATUSES, QUERYING_LOCKED_STATUSES,
    _maybe_autofinalise, auto_queries_allowed, officer_queries_allowed,
    querying_locked, submit_interview,
)
from .details import (
    _DEEPER_FIELDS, _PROFILE_ADDRESS_FIELDS, save_application_details,
)
from .consent import (
    CONSENT_VERSION, _PARENT_RELATIONSHIPS, age_from_nric, complete_onboarding,
    gender_from_nric, is_minor, needs_guardianship_letter, record_consent,
)

