"""The second chip beside a case's status — owner 2026-11-23 (rejected cases: one status, one chip).

Every rejected case reads "Rejected" plus ONE chip saying where it was turned down; a case that
fails its intake's "Born in" rule but is NOT rejected keeps its own status plus a "state" chip.
Served as ONE field, ``rejection_chip``, on the list row and the cockpit payload, so the list, the
phone rows and the case header cannot disagree. Display only: nothing here decides anything.

The codes (the web's `lib/applicationStatus.rejectionChipKey` labels them):

* ``merit`` / ``need``      — the engine's academic / income floor (category `merit` / `need`).
* ``state``                 — category `ineligible` and the engine's reason is the birth-state rule
                              (`birth_state.RULE_REASON_MARK`, written by `birth_state.check`);
                              or, on a case that is not rejected, the CURRENT IC fails the intake's
                              CURRENT rule (`birth_state.meets_rule`, the cockpit's own answer).
* ``ineligible``            — any other `ineligible` reason (consent, intent, IPTS, private diploma).
* ``shortlisted``           — category `incomplete`: the org admin's "Reject this student".
* ``before_interview``      — category `pre_interview` (request #75).
* ``qc``                    — category `interview` and the case's LATEST `qc_decision` row is a QC
                              OUTRIGHT reject (`views_admin/verdict.py`, decision `reject`).
* ``interview``             — any other `interview` decline: QC confirmed the reviewer's decline,
                              or an older decline with no QC row at all.
* ``contractual``           — category `contractual`.
* ``rules_error``           — a case that is NOT rejected on an intake whose STORED criteria tree
                              is refused (`criteria.StoredTreeRefused`, TD-774): this row only.
* ``''``                  — no chip (a rejected case with a blank category, or nothing to say).

⚠ THE LIST NEVER ASKS PER ROW. `qc_rejected_ids` reads the qc rows for a whole page in ONE query,
and only for the page's `interview` declines; the list view hands the set to its serializer.
"""
from .criteria import StoredTreeRefused
from . import birth_state

#: The chip codes, in the order the Guide lists them.
CHIPS = ('merit', 'need', 'state', 'ineligible', 'shortlisted', 'before_interview', 'interview',
         'qc', 'contractual', 'rules_error')

_SIMPLE = {'merit': 'merit', 'need': 'need', 'incomplete': 'shortlisted',
           'pre_interview': 'before_interview', 'contractual': 'contractual'}


def _is_interview_decline(app):
    return app.status == 'rejected' and (app.rejection_category or '') == 'interview'


def qc_rejected_ids(apps):
    """The ids among ``apps`` whose LATEST `qc_decision` row is an outright reject. ONE query for
    the lot, and none when no row is an `interview` decline."""
    from .models import StaffActivity
    ids = [a.pk for a in apps if _is_interview_decline(a)]
    if not ids:
        return set()
    # Latest row is right after a super reopen too: `/reject/` refuses 'interview' at every status,
    # so any new interview decline after a reopen goes through the QC gate and writes a NEW
    # `qc_decision` row (accept or reject); no reopen is needed to filter rows by time.
    latest = {}
    rows = (StaffActivity.objects
            .filter(verb='qc_decision', subject_type='application', subject_id__in=ids)
            .order_by('created_at', 'id')
            .values_list('subject_id', 'meta'))
    for subject_id, meta in rows:      # oldest first, so the last one written wins
        latest[subject_id] = (meta or {}).get('decision')
    return {pk for pk, decision in latest.items() if decision == 'reject'}


def list_context(page):
    """The list serializer's context for one page: its QC rejects, read once (`qc_rejected_ids`)."""
    return {'qc_rejected_ids': qc_rejected_ids(page)}


def fails_state_rule_reason(reason):
    """Is this stored engine reason the birth-state rule's? Read through the rule's own marker."""
    return birth_state.RULE_REASON_MARK in (reason or '')


def chip(app, qc_rejected=None):
    """The chip code for ``app`` (see the module docstring). ``qc_rejected``: the page's
    `qc_rejected_ids`; omitted, this one case is looked up (the cockpit's single read)."""
    if app.status != 'rejected':
        profile = getattr(app, 'profile', None)
        try:
            rule = birth_state.cohort_rule(app.cohort)
        except StoredTreeRefused:
            # TD-774 (Sprint 3b): an intake whose STORED criteria tree is refused fails THIS ROW,
            # visibly ('rules_error', the refusal already logged at ERROR by `tree_of`) - never
            # the whole application list, which serves every intake's cases on one page.
            return 'rules_error'
        fails = birth_state.meets_rule(getattr(profile, 'nric', '') if profile else '', rule) is False
        return 'state' if fails else ''
    category = app.rejection_category or ''
    if category in _SIMPLE:
        return _SIMPLE[category]
    if category == 'ineligible':
        return 'state' if fails_state_rule_reason(app.shortlist_reason) else 'ineligible'
    if category == 'interview':
        if qc_rejected is None:
            qc_rejected = qc_rejected_ids([app])
        return 'qc' if app.pk in qc_rejected else 'interview'
    return ''
