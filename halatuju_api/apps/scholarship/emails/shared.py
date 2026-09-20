"""The metering seam, the platform branding block and the logger every mail module shares.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
import logging
import sys

from .. import branding as _branding


def _meter_email():
    """Best-effort billing meter for ONE Brevo send. Source = the nearest ``send_*``
    caller (so the row names the mail kind, no signature changes); org is inherited from
    any surrounding usage_context (else NULL — acceptable for v1 per the brief). NEVER
    raises: metering can't break a send."""
    try:
        from .. import usage
        source = 'email'
        f = sys._getframe(2)   # skip _meter_email + the calling _send primitive
        for _ in range(8):
            if f is None:
                break
            name = f.f_code.co_name
            if name.startswith('send_'):
                source = name
                break
            f = f.f_back
        usage.record_usage(usage.EMAIL, source=source, quantity=1)
    except Exception:  # noqa: BLE001
        pass

# Per-org branding is read ONLY through the branding seam (decision D1). Sender identity,
# sign-off, programme name, persona, support/reply-to, topical aliases (interview@ / sponsor@)
# and the display domain all resolve there. ``_P`` is the platform branding (BrightPath / today's
# constants) — the default for internal/ops mail and the byte-identical fallback for every
# student-facing send that isn't handed a tenant ``branding``.
_P = _branding.platform()

# Back-compat alias for the platform support address (derived from the seam, not a literal).
# Kept because it is a documented public name of this module (imported by tests / callers).
SUPPORT_EMAIL = _P.email_support

# Platform brand tokens, resolved from the seam (NOT string literals) — the readable form used in
# the internal/ops + bilingual interview mail, which is platform-branded English/BM and takes no
# tenant ``branding``. _PROG_* is the programme name; _TEAM_* the full team sign-off line.
_PROG_EN = _P.programme_name('en')   # 'BrightPath Bursary'
_PROG_MS = _P.programme_name('ms')   # 'Bursari BrightPath'
_TEAM_EN = _P.team_signoff('en')     # 'The BrightPath Bursary Team'
_TEAM_MS = _P.team_signoff('ms')     # 'Pasukan Program Bursari BrightPath'

# ⚠ ONE DECLARED EDIT (code health H16). This was `logging.getLogger(__name__)` in `emails.py`,
# where `__name__` WAS `apps.scholarship.emails`. In this module `__name__` is
# `apps.scholarship.emails.shared`, so keeping the original line would rename the logger and
# every `Failed to send ...` warning would drop out of the Cloud Logging scrape metric, which
# counts by logger name — with nothing going red. Writing the name out in full is what keeps
# the behaviour identical. Every other module in this package imports THIS logger.
# `AuditLoggerNameTest` holds it (H11, H15, and this package since H16).
logger = logging.getLogger('apps.scholarship.emails')

_DEFAULT_NAME = {'en': 'applicant', 'ms': 'pemohon', 'ta': 'விண்ணப்பதாரர்'}
