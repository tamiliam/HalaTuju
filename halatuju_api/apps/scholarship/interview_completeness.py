"""TD-253 — every interview agenda item must carry an answer the reviewer CHOSE (owner, 2026-09-18).

*"The reviewer could simply say: See conclusion. I want this to be a conscious decision on their
part, and I want it to be complete."* The per-item record IS wanted; a short answer is a legitimate
answer; what is refused is SILENCE. Before this, an interview with `findings = {}` (application
#32) passed every gate up to a recorded decline, because `_validate_findings` validates each
finding it is given and an empty dict gives it none.

⚠ **WHAT "ANSWERED" MEANS, AND WHY A RATIONALE ALONE COUNTS.** An item is answered when its finding
carries a verdict (`resolved` / `still_unclear` / `new_concern`) OR a non-blank rationale. The
cockpit offers exactly ONE verdict button (Resolved) beside a one-line answer box — so a reviewer
whose honest answer is "not resolved" has only the box to say it in. Requiring a verdict would
force her to press Resolved on something that is not; requiring a rationale would refuse the
Resolved click the screen has always treated as a full answer (its read-only view shows "Resolved
✓" for one). Either reading alone would make the screen lie or block. `deleted` is the reviewer
taking the question OFF the agenda — also a choice, never silence — so it is not owed an answer.

⚠ **"THE AGENDA" IS THE LIST THE COCKPIT DRAWS, KEY FOR KEY** (`view.tsx` `agendaItems`): the
pre-interview anomalies the payload serves (less the two identity mismatches the serializer
dedupes, less any anomaly whose question Check 2 is already asking — the cockpit's
`ANOMALY_CHECK2_OWNER`), then every non-anomaly entry of `interview_agenda_full` keyed
`kind:code`, then the AI gaps stored on the application. A narrower list would let an item the
reviewer can see go unanswered; a wider one would refuse a submit over an item she cannot see.
`CHECK2_OWNED_ANOMALIES` below is the server's copy of the cockpit's map and
`tests/test_interview_completeness.py` fails if the two ever differ.

⚠ **WHERE THE GATE BINDS** (`decision_gate_applies`): only where the REVIEWER decides — a case
with no recorded decision (an Approve or a Decline — a hold is not one) still at the reviewer's
stage, or any case whose decision a super has
REOPENED (a reopen hands the decision back and unlocks the interview, so it can be completed).
QC's accept/reject and everything after a recorded decision are deliberately out of reach: on
2026-09-18, 33 decided cases and 2 awaiting QC (#32, #140) carried an empty submitted interview,
and the owner's rule binds from the day it ships — it does not reopen closed work.
"""
import re

from django.db.models import Q

#: What does NOT count as a typed answer: Unicode whitespace and the zero-width/BOM characters,
#: spelled out character by character so it means the same thing in both languages (review F6:
#: Python's `str.strip` and JS's `trim` disagree — U+FEFF is whitespace to one and not the other).
#: The cockpit's `BLANK` must have this exact source; `interviewCompleteness.test.ts` compares them.
_BLANK = re.compile(r'[\t\n\v\f\r \x1c-\x1f\x85\xa0\u1680\u2000-\u200d\u2028\u2029\u202f\u205f\u3000\ufeff]')

#: The verdicts that are an answer on their own. '' is "not classified yet"; 'deleted' is handled
#: separately (the item leaves the agenda).
_ANSWER_VERDICTS = frozenset({'resolved', 'still_unclear', 'new_concern'})

#: anomaly code -> the Check-2 query code that, while open (or answered by the student and not yet
#: actioned), already asks the same thing — so the cockpit leaves the anomaly off the agenda.
#: The cockpit's copy is `ANOMALY_CHECK2_OWNER` in
#: `halatuju-web/src/app/admin/scholarship/[id]/view/shared.tsx`; the test named above compares them.
CHECK2_OWNED_ANOMALIES = {
    'utility_holder_unknown': 'utility_holder_unknown',
    'utility_address_mismatch': 'utility_address_mismatch',
    'device_in_funding': 'device_status_unknown',
    'first_in_family_with_siblings_studying': 'sibling_level_unknown',
}

#: The statuses at which a case with NO recorded decision is in the reviewer's hands.
#: 'interviewed' is AWAITING QC and is not here on purpose.
_REVIEWER_STAGE = ('shortlisted', 'profile_complete', 'interviewing')


def agenda_keys(application):
    """The finding keys of every item on the cockpit's interview agenda, in the cockpit's order."""
    from .serializers_admin import AdminApplicationDetailSerializer
    from .views_admin.interviews import interview_agenda_full
    deduped = AdminApplicationDetailSerializer._DEDUPED_ANOMALIES
    # The same queue the cockpit's `resolution_items` field serves: open, or answered by the
    # student and not yet actioned by an officer.
    owned = set(application.resolution_items.filter(
        Q(status='open') | Q(status='resolved', resolved_by='student'),
    ).values_list('code', flat=True))
    keys = []
    for entry in interview_agenda_full(application):
        code, kind = entry['code'], entry['kind']
        if kind == 'anomaly':
            if code in deduped:
                continue
            owner = CHECK2_OWNED_ANOMALIES.get(code)
            if owner and owner in owned:
                continue
            keys.append(code)
        else:
            keys.append(f'{kind}:{code}')
    for gap in (application.interview_gaps or []):
        if isinstance(gap, dict) and gap.get('code'):
            keys.append(gap['code'])
    return keys


def is_answered(finding):
    """A verdict the reviewer pressed, or an answer she typed — see the module docstring."""
    if not isinstance(finding, dict):
        return False
    if finding.get('verdict') in _ANSWER_VERDICTS:
        return True
    return bool(_BLANK.sub('', finding.get('rationale') or ''))


def missing_agenda_items(application, findings):
    """The agenda keys that are neither answered nor deleted, in agenda order (no duplicates)."""
    findings = findings if isinstance(findings, dict) else {}
    missing = []
    for key in agenda_keys(application):
        finding = findings.get(key)
        if isinstance(finding, dict) and finding.get('verdict') == 'deleted':
            continue
        if not is_answered(finding) and key not in missing:
            missing.append(key)
    return missing


#: The outcomes that ARE a decision. ⚠ `record-verdict` stamps `verdict_decided_at` for ANY outcome,
#: `hold` and '' included, so the stamp alone is not "a decision is recorded" (review F1: a hold,
#: then an accept, walked round the gate on an empty interview).
_DECISIONS = ('accept', 'decline')


def decision_recorded(application):
    """Has the reviewer recorded an Approve or a Decline (not a hold, not a blank)?"""
    verdict = application.officer_verdict if isinstance(application.officer_verdict, dict) else {}
    return application.verdict_decided_at is not None and verdict.get('overall') in _DECISIONS


def decision_gate_applies(application):
    """Is a decision recorded NOW the reviewer's own? See "WHERE THE GATE BINDS" above."""
    if application.decision_reopened_at is not None:
        return True
    return not decision_recorded(application) and application.status in _REVIEWER_STAGE


def decision_refusal(application):
    """The 400 body refusing a reviewer's Approve/Decline, or None when the interview is complete.

    Reads the LATEST SUBMITTED session — the one the cockpit's buttons wait for. No submitted
    session at all is refused too: the screen has never offered the buttons without one.
    """
    session = (application.interview_sessions.filter(status='submitted')
               .order_by('-submitted_at').first())
    if session is None:
        return {'error': 'Submit the interview findings before recording the decision.',
                'code': 'interview_not_submitted'}
    missing = missing_agenda_items(application, session.findings)
    if not missing:
        return None
    return {'error': 'Every interview question needs an answer before the decision is recorded.',
            'code': 'interview_incomplete', 'missing': missing}
