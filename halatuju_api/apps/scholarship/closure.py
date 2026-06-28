"""Post-award lifecycle S6 — manual closure (the terminal step).

A funded application (active / maintenance) is CLOSED by hand by an admin, with a
``closure_reason`` recorded. Closure is deliberately manual (owner decision): there is
no auto-close on graduation or on the last tranche — a human confirms the programme
relationship has ended and WHY.

``closure_reason`` distinguishes the positive endings (``graduated`` = finished the
programme; ``completed`` = the contractual support period was fulfilled, the programme may
continue) from the negative ones (``withdrawn`` / ``lapsed`` / ``terminated``). The field
itself was added in S2; this module is the writer + the gate.

Closure is terminal within this lifecycle (no reopen path here). The graduation thank-you
relay is re-gated to remain available AFTER closure (see ``in_programme`` —
``submit_graduation_message`` accepts ``closed`` too), so a graduated student can still
write to their sponsor once the file is closed.
"""
from django.db import transaction
from django.utils import timezone

from .models import ScholarshipApplication

# A close is only valid from a funded state. (A withdrawal/termination can happen at
# 'active' before any tranche, or at 'maintenance'.)
CLOSEABLE_FROM = ('active', 'maintenance')

# The valid closure reasons (mirror ScholarshipApplication.CLOSURE_REASONS).
VALID_REASONS = {code for code, _label in ScholarshipApplication.CLOSURE_REASONS}

# Positive closures (finished well) vs negative — used for student/sponsor copy.
POSITIVE_REASONS = ('graduated', 'completed')


class ClosureError(Exception):
    """Raised by close_application with a machine code for the view
    (e.g. 'not_closeable', 'bad_reason')."""
    def __init__(self, code, message=''):
        self.code = code
        super().__init__(message or code)


@transaction.atomic
def close_application(application, *, closure_reason, by_email=''):
    """Manually close a funded application. Requires ``status`` in CLOSEABLE_FROM and a
    valid (non-blank) ``closure_reason``. Stamps closed_at / closed_by and flips status to
    'closed'. Returns the application. No money side-effects — the disbursement ledger is
    historical, and ``disbursement.release_tranche`` already refuses to pay a non-funded
    (closed) student, so any leftover scheduled tranche simply becomes un-releasable."""
    if application is None or application.status not in CLOSEABLE_FROM:
        raise ClosureError('not_closeable')
    if closure_reason not in VALID_REASONS:
        raise ClosureError('bad_reason')
    application.status = 'closed'
    application.closure_reason = closure_reason
    application.closed_at = timezone.now()
    application.closed_by = (by_email or '')[:254]
    application.save(update_fields=['status', 'closure_reason', 'closed_at', 'closed_by'])
    return application
