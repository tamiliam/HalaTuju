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
