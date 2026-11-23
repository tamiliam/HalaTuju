"""F3 (I-11) - the one-tap reason the reviewer gives for EVERY fact she marks Fail.

ONE home for the fixed code list, the request validator and the keep-or-drop filter, so the
record-verdict view, the reject-before-interview door and the metrics read the same list. Pure: no
database, no scoring. Only codes and fact names.

The reason is about the STUDENT, never about the AI: the reviewer says why the fact is not true or not
proven. (LL2's first list asked only on a fact the engine showed green, with reasons about the engine;
live data held no stored reason when F3 replaced it, so no data step was needed.)

Server rules (``keep``): a Fail with no reason is stored as Other; a reason on a Pass (or a blank fact)
is dropped. An UNKNOWN code is REFUSED (``validate`` raises, the view answers 400 and saves nothing):
a code nobody chose must never be counted as a real answer, and only a hand-made request sends one.
For one release only, LL2's old codes are read as Other (``OLD_CODES_READ_AS_OTHER``, review fix 3).

drift-test: halatuju-web/src/lib/__tests__/failReasonsDrift.test.ts - the web's chips are this list.
"""
from __future__ import annotations

from . import audit

PROOF_MISSING = 'proof_missing'            # Proof is missing or unclear
DOCUMENT_FALSE = 'document_false'          # A document looks false or altered
DOCUMENTS_DIFFER = 'documents_differ'      # The documents show something different
INTERVIEW_DIFFERS = 'interview_differs'    # The interview or a call showed something different
OTHER = 'other'
#: In the order the chips show. Written as literals so the web's drift test can read it.
CODES = ('proof_missing', 'document_false', 'documents_differ', 'interview_differs', 'other')
#: A Fail with no reason chosen is stored as this (the chip the cockpit pre-selects).
DEFAULT = OTHER
#: F3 review fix 3: LL2's old codes, which a browser tab opened before the F3 deploy still sends. For
#: this one release they are read as Other, so that tab can still save; any other unknown code is
#: still refused. Remove after one release; tracked as TD-704.
OLD_CODES_READ_AS_OTHER = frozenset({'engine_wrong', 'read_wrong', 'new_information', 'programme_rule'})

KEY = 'fail_reasons'   # the key inside `officer_verdict`


class BadFailReasons(ValueError):
    """The `fail_reasons` payload is malformed; the view answers 400 and saves nothing."""


def validate(raw) -> dict:
    """``raw`` (the request's `fail_reasons`, or None) as a clean ``{fact: code}``.
    Absent / None is empty. Anything not an object of known fact -> known code raises ``BadFailReasons``
    (an unknown code is refused, never mapped to Other). The one exception, for one release: an OLD
    LL2 code (``OLD_CODES_READ_AS_OTHER``) is read as Other."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise BadFailReasons('fail_reasons must be an object')
    clean = {}
    for fact, code in raw.items():
        if fact not in audit.FACTS:
            raise BadFailReasons('unknown fact in fail_reasons')
        if isinstance(code, str) and code in OLD_CODES_READ_AS_OTHER:
            code = OTHER
        if not isinstance(code, str) or code not in CODES:
            raise BadFailReasons('unknown reason code in fail_reasons')
        clean[fact] = code
    return clean


def keep(reasons: dict, officer_verdict: dict) -> dict:
    """One reason for every fact the human failed (the one given, else Other); none for any other fact."""
    return {fact: (reasons.get(fact) or DEFAULT)
            for fact in audit.FACTS if officer_verdict.get(fact) == 'fail'}


def given(officer_verdict, fact):
    """The stored reason code for ``fact`` in an `officer_verdict`, or '' (old rows, bad values)."""
    stored = officer_verdict.get(KEY) if isinstance(officer_verdict, dict) else None
    code = stored.get(fact) if isinstance(stored, dict) else None
    return code if isinstance(code, str) and code in CODES else ''
