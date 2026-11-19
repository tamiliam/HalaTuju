"""LL2 - the one-tap reason for failing a fact the engine called green.

ONE home for the fixed code list, the request validator and the keep-or-drop filter, so the record-verdict
view and the metrics read the same list. Pure: no database, no scoring. Only codes and fact names.

The reason is the REVIEWER's answer to "why did you fail what the engine called verified?". The server
keeps it only where that is true in this very request (human fail AND the fresh snapshot says `verified`);
a missing reason never blocks a decision (an old browser tab must still save).
"""
from __future__ import annotations

from . import audit

ENGINE_WRONG = 'engine_wrong'          # the rule is wrong
READ_WRONG = 'read_wrong'              # the document was read wrong
NEW_INFORMATION = 'new_information'    # interview, call, outside the documents
PROGRAMME_RULE = 'programme_rule'
OTHER = 'other'
CODES = (ENGINE_WRONG, READ_WRONG, NEW_INFORMATION, PROGRAMME_RULE, OTHER)

KEY = 'fail_reasons'   # the key inside `officer_verdict`


class BadFailReasons(ValueError):
    """The `fail_reasons` payload is malformed; the view answers 400 and saves nothing."""


def validate(raw) -> dict:
    """``raw`` (the request's `fail_reasons`, or None) as a clean ``{fact: code}``.
    Absent / None is empty. Anything not an object of known fact -> known code raises ``BadFailReasons``."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise BadFailReasons('fail_reasons must be an object')
    for fact, code in raw.items():
        if fact not in audit.FACTS:
            raise BadFailReasons('unknown fact in fail_reasons')
        if not isinstance(code, str) or code not in CODES:
            raise BadFailReasons('unknown reason code in fail_reasons')
    return dict(raw)


def keep(reasons: dict, officer_verdict: dict, ai_verdict_snapshot) -> dict:
    """Only the reasons whose fact the human failed AND the snapshot calls green (`verified`)."""
    statuses = audit._snapshot_status_map(ai_verdict_snapshot)
    return {fact: code for fact, code in reasons.items()
            if officer_verdict.get(fact) == 'fail' and audit.ai_fact_pass(statuses.get(fact))}


def given(officer_verdict, fact):
    """The stored reason code for ``fact`` in an `officer_verdict`, or '' (old rows, bad values)."""
    stored = officer_verdict.get(KEY) if isinstance(officer_verdict, dict) else None
    code = stored.get(fact) if isinstance(stored, dict) else None
    return code if isinstance(code, str) and code in CODES else ''
