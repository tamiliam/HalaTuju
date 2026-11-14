"""The courses app's door to the staff activity list (common profile S3, 2026-10-31).

A few staff actions live in this app — the first sign-in (`views_admin.AdminRoleView`) and a referral
partner's profile save (`views_profile.AdminProfileView`). The list itself is the scholarship app's
(`apps/scholarship/staff_activity.py`), and the `courses -> scholarship` import budget is full
(`test_code_standards`, `counts.courses_to_scholarship_imports`). So this module imports NOTHING from
scholarship: the scholarship app REGISTERS its writer here at start-up (`ScholarshipConfig.ready`),
the same "registered, not imported" pattern as `exam_questions.STPM_DOCUMENT_WITNESS`.

``verb`` is the verb's string (``'first_sign_in'``); the writer checks it against the closed list.
Best-effort like the writer: it never raises, and with no writer registered it writes nothing.
"""
import logging

logger = logging.getLogger(__name__)

#: `apps.scholarship.staff_activity.record`, set by `ScholarshipConfig.ready`. None = not registered.
RECORDER = None


def record(actor, verb, subject=None, meta=None):
    """Hand the row to the registered writer. Never raises; see the module docstring."""
    try:
        if RECORDER is not None:
            return RECORDER(actor, verb, subject, meta)
    except Exception:   # the writer is best-effort already; this guards the hand-over itself
        logger.warning('staff activity hand-over failed for %r', verb, exc_info=True)
    return None


#: `apps.scholarship.staff_permissions_admin.record_role_reset`, which writes through the ONE writer of a
#: `staff_permission_changes` row; set by `ScholarshipConfig.ready` (M3a review, 2026-11-14: the Django admin
#: screen's role change is audited like the app's own writers). None = not registered.
PERMISSION_RECORDER = None


def record_role_reset(old, new, *, by):
    """Hand one 'role_change' history row to the registered writer, inside the caller's transaction: what
    ``old`` (the row as it was, locked) held, then what ``new`` (saved) holds. Unlike `record` it is NOT
    best-effort: a change to what somebody may do is never written without its audit row, so with no writer
    registered it raises and the caller's transaction rolls back."""
    if PERMISSION_RECORDER is None:
        raise RuntimeError('staff_activity_hook: no permission-change writer is registered')
    return PERMISSION_RECORDER(old, new, by=by)
