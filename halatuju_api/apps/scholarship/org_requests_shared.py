"""The vocabulary an organisation request is written in: its error, and who may speak.

Moves only, split out of `org_requests.py` on 2026-10-29 alongside `org_requests_ai.py`. It exists
for one reason: both modules need these names, and putting them in either one would make the two
import each other at module level. A handful of constants with no behaviour is the right thing to
share; the services are not.

Nothing here has any logic. If a function lands in this file, it is in the wrong file.
"""


class OrgRequestError(Exception):
    """Raised by the service with a machine code for the view (e.g. 'bad_transition',
    'bug_is_free', 'bad_hours', 'reason_required', 'wrong_role')."""
    def __init__(self, code, message=''):
        self.code = code
        super().__init__(message or code)


# ── who is speaking in the discussion (TD-201, owner 2026-07-31) ─────────────────
AUTHOR_AI = 'ai'
AUTHOR_OWNER = 'owner'
AUTHOR_ORG = 'org'
# The engineer's analysis, posted by `approve_analysis` (TD-204). Distinct from AUTHOR_OWNER
# because the two carry different authority: the owner decides, the engineer read the code.
AUTHOR_ENGINEER = 'engineer'

VISIBILITY_SHARED = 'shared'
VISIBILITY_INTERNAL = 'internal'

# ── the limits both the service and the reviewer are held to ─────────────────────
# Auto-run cap (owner 2026-07-24) — the AI reviewer runs at most this many times per request
# (on create + on each clarification answer). A super may still trigger a manual re-run, which is
# also bounded by this cap. Guards against Gemini cost runaway.
AI_RUN_CAP = 3

# Screenshot attachments (Sprint 15.1, TD-172): images ONLY, at most this many per request. The cap
# is enforced at BOTH the sign-upload (before we mint a URL) and the record (after the PUT) seams.
MAX_ATTACHMENTS = 5

VALID_KINDS = ('bug', 'feature')
VALID_LANES = ('small_change', 'sprint')
