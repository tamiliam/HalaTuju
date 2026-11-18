"""LL2b - the QC's second look at the facts in doubt.

ONE home for which facts are "in doubt", the request validator, the keep-or-drop rule for the QC's
answers, and their counting. Pure apart from `record_answers` (one save of `officer_verdict`). No scoring, no
engine run: "the AI said green" is read from the STORED snapshot (`ai_verdict_snapshot`, written with
the reviewer's verdict), through `audit.ai_fact_pass` - the same basis as the LL1 green -> fail count,
so the QC block and the numbers can never disagree.

A fact is in doubt when the reviewer FAILED it and either
  1. the AI said green (`verified`)                    -> group ``ai_green_reviewer_fail``, or
  2. the reviewer's overall decision is accept         -> group ``failed_but_accepted``.
A fact in both groups is listed once, with both groups.

The answers live INSIDE `officer_verdict` under ``qc_fact_checks`` ({fact: 'agreed'|'disagreed'}):
they judge THAT reviewer verdict and THAT snapshot, which only `record-verdict` writes - and it writes
the whole dict afresh, so a re-recorded verdict drops answers that judged the old one. A later QC
decision that sends the key replaces the earlier answers whole (the latest QC decision stands).
A copy (fact names and fixed group codes only) also goes on the QC decision's own activity row
(`activity_meta`), so a second look from a send-back survives the reviewer's re-record.

The second look never changes a decision or an engine result. It is a record and a number only.
"""
from __future__ import annotations

from . import audit
from . import fail_reasons

FIELD = 'fact_checks'        # the qc-decision request key
KEY = 'qc_fact_checks'       # the key inside `officer_verdict`
AGREED = 'agreed'
DISAGREED = 'disagreed'
ANSWERS = (AGREED, DISAGREED)
AI_GREEN_REVIEWER_FAIL = 'ai_green_reviewer_fail'   # group 1
FAILED_BUT_ACCEPTED = 'failed_but_accepted'         # group 2


class BadFactChecks(ValueError):
    """The `fact_checks` payload is malformed; the view answers 400 and saves nothing."""


def in_doubt(ai_verdict_snapshot, officer_verdict) -> list:
    """The facts in doubt for one recorded verdict, in the fixed fact order:
    ``[{fact, ai_status, ai_green, reviewer, reason, groups}]``. Empty when none."""
    ov = officer_verdict if isinstance(officer_verdict, dict) else {}
    # a stored snapshot or status of any other shape reads as "no AI status", never an error
    snapshot = ai_verdict_snapshot if isinstance(ai_verdict_snapshot, list) else []
    statuses = audit._snapshot_status_map(snapshot)
    accept = ov.get('overall') == 'accept'
    out = []
    for fact in audit.FACTS:
        if ov.get(fact) != 'fail':
            continue
        status = statuses.get(fact) if isinstance(statuses.get(fact), str) else ''
        green = audit.ai_fact_pass(status)
        groups = [g for g, on in ((AI_GREEN_REVIEWER_FAIL, green), (FAILED_BUT_ACCEPTED, accept)) if on]
        if groups:
            out.append({'fact': fact, 'ai_status': status, 'ai_green': green,
                        'reviewer': 'fail', 'reason': fail_reasons.given(ov, fact) or None,
                        'groups': groups})
    return out


def for_application(app) -> list:
    """The in-doubt list for ``app``'s recorded verdict ([] when no verdict is recorded)."""
    if app.verdict_decided_at is None:
        return []
    return in_doubt(app.ai_verdict_snapshot, app.officer_verdict)


def stored(officer_verdict):
    """The QC's stored answers ({fact: answer}), or None when no QC answer was ever stored
    (no QC decision yet, or one from before LL2b: "not checked")."""
    raw = officer_verdict.get(KEY) if isinstance(officer_verdict, dict) else None
    if not isinstance(raw, dict):
        return None
    return {f: a for f, a in raw.items() if f in audit.FACTS and a in ANSWERS}


def validate(raw):
    """The request's `fact_checks` as a clean ``{fact: answer}``, or None when absent / null (the QC
    decision then works exactly as before LL2b). Anything else that is not an object of known fact ->
    known answer raises ``BadFactChecks``."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise BadFactChecks('fact_checks must be an object')
    for fact, answer in raw.items():
        if fact not in audit.FACTS:
            raise BadFactChecks('unknown fact in fact_checks')
        if not isinstance(answer, str) or answer not in ANSWERS:
            raise BadFactChecks('unknown answer in fact_checks')
    return dict(raw)


def answers(decision: str, sent: dict, doubt: list) -> dict:
    """What to store. The web sends an answer for EVERY fact its block showed ('agreed' untouched,
    'disagreed' tapped). Only facts in BOTH ``sent`` and the server's current in-doubt set (``doubt``)
    get an answer: an in-doubt fact missing from ``sent`` was not seen by the QC (a stale tab) and gets
    none; a sent fact not in doubt is dropped. ``accept`` keeps both answers. A send-back (reopen /
    reject) is not a silent yes: only the explicit 'disagreed' answers."""
    shown = [d['fact'] for d in doubt]
    if decision == 'accept':
        return {f: sent[f] for f in shown if f in sent}
    return {f: DISAGREED for f in shown if sent.get(f) == DISAGREED}


def activity_meta(given: dict, doubt: list) -> dict:
    """The second look for the QC decision's activity row: lists of fact names only (closed
    `staff_activity.META_KEYS` codes). It outlives a re-recorded verdict: the source to count from."""
    return {'qc_agreed': [f for f, a in given.items() if a == AGREED],
            'qc_disagreed': [f for f, a in given.items() if a == DISAGREED],
            'doubt_ai_green': [d['fact'] for d in doubt if AI_GREEN_REVIEWER_FAIL in d['groups']],
            'doubt_failed_accepted': [d['fact'] for d in doubt if FAILED_BUT_ACCEPTED in d['groups']]}


def record_answers(app, decision: str, taps) -> dict:
    """Store the QC's answers on ``app`` (call it on the LOCKED, re-read row, inside the decision's
    own transaction) and return `activity_meta` for the QC decision row. ``taps`` None (no key in the
    request) writes nothing and returns {}. A stored verdict that is not a dict (nor None) is left
    untouched: nothing is in doubt on it, and the QC decision never fails over it."""
    if taps is None:
        return {}
    doubt = for_application(app)
    given = answers(decision, taps, doubt)
    ov = app.officer_verdict
    if ov is None or isinstance(ov, dict):
        app.officer_verdict = {**(ov or {}), KEY: given}
        app.save(update_fields=['officer_verdict'])
    return activity_meta(given, doubt)


# ── the numbers ("checked by the QC") ───────────────────────────────────────────────────────────
def _block() -> dict:
    return {'in_doubt': 0, 'checked': 0, 'not_checked': 0, 'agreed': 0, 'disagreed': 0,
            'ai_green_checked': 0, 'ai_wrong_checked': 0, 'ai_right_reviewer_wrong_checked': 0}


def _finish_checked(block: dict) -> dict:
    block['few'] = block['checked'] < audit.FEW_BELOW
    block['few_ai_green'] = block['ai_green_checked'] < audit.FEW_BELOW
    return block


def walk(ai_verdict_snapshot, officer_verdict):
    """(fact, groups, answer or None) for each in-doubt fact of one recorded verdict."""
    given = stored(officer_verdict) or {}
    for d in in_doubt(ai_verdict_snapshot, officer_verdict):
        yield d['fact'], d['groups'], given.get(d['fact'])


def counts(decided_records) -> dict:
    """The "checked by the QC" counts over ``(snapshot, officer_verdict, ...)`` records:
    ``{total: block, facts: {fact: block}}``. An in-doubt fact with no stored answer (no QC decision
    yet, a send-back without a tap, or a QC decision from before LL2b) is ``not_checked``.
    For a group-1 fact (AI green, reviewer fail): QC agreed with the reviewer = ``ai_wrong_checked``;
    QC disagreed = ``ai_right_reviewer_wrong_checked``."""
    total, facts = _block(), {f: _block() for f in audit.FACTS}
    for record_ in decided_records:
        for fact, groups, answer in walk(record_[0], record_[1]):
            for block in (total, facts[fact]):
                block['in_doubt'] += 1
                if answer is None:
                    block['not_checked'] += 1
                    continue
                block['checked'] += 1
                block[answer] += 1
                if AI_GREEN_REVIEWER_FAIL in groups:
                    block['ai_green_checked'] += 1
                    block['ai_wrong_checked' if answer == AGREED
                          else 'ai_right_reviewer_wrong_checked'] += 1
    return {'total': _finish_checked(total), 'facts': {f: _finish_checked(b) for f, b in facts.items()}}


def reviewer_counts(ai_verdict_snapshot, officer_verdict) -> tuple:
    """(checked, overturned) for one reviewer verdict: how many of its in-doubt facts the QC checked,
    and how many of those the QC disagreed with."""
    checked = overturned = 0
    for _fact, _groups, answer in walk(ai_verdict_snapshot, officer_verdict):
        if answer is not None:
            checked += 1
            overturned += answer == DISAGREED
    return checked, overturned
