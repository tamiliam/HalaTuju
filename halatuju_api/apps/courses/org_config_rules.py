"""Cross-field rules for organisation configuration — timings checked TOGETHER.

Split out of `org_config.py` (org-timing Sprint 1, 2026-10-07); the one pair that lived here
(`_ORDERED_PAIRS`, the interview window) became the first row of `RULES`, and R1–R7 joined it
(roadmap `docs/plans/2026-10-07-org-timing-settings-roadmap.md`, owner 2026-10-07: "if any are
dependent on another timing, this should be managed as well"). `org_config.validate_values`
calls `check_rules`; nothing else should.

⚠ EACH RULE IS CHECKED ON THE MERGED SETTINGS — the stored value, else the platform default —
never on the changed keys alone: an organisation that stores only one side of a rule is still
describing a pair whose other side is the platform default. A rule none of whose keys is stored
is skipped, so an organisation is never refused for a combination it did not choose (and a
platform default changed by env var is held to the rules by the guard test instead).

⚠ WITH THE NARROW RANGES ONLY R3 AND R5 CAN BE BROKEN. R1, R2, R4, R6 and R7 are always met
inside today's min/max; they are kept as guards so that a range widened later is already
fenced, and `test_org_timing.py` makes each one bite with inputs placed outside the ranges.
"""
from collections import namedtuple

from .org_config_registry import OrgConfigError, default

#: `code` is what the endpoint returns; `blames` is the key whose box the refusal is shown
#: under — the one the person was most likely editing; `keys` are every key the check reads;
#: `ok(v)` takes the merged values and is True when the rule holds.
Rule = namedtuple('Rule', 'code blames keys ok')


def _reminders_apart(earlier, later):
    """R2 for one pair of rungs: the later reminder at least two days after the earlier one."""
    return Rule('reminders_too_close', later, (earlier, later),
                lambda v: v[later] >= v[earlier] + 2)


# Ordered: the first broken rule is the one reported. R4 sits before R3 because a reminder
# outside the answer window breaks R3 too, and the more basic fault is the one to name.
RULES = (
    # The interview window must open before it closes; an inverted window would offer the
    # reviewer an empty picker with nothing on screen saying why.
    Rule('window_inverted', 'interview_window_end_min',
         ('interview_window_start_min', 'interview_window_end_min'),
         lambda v: v['interview_window_start_min'] < v['interview_window_end_min']),
    # R1 — the not-shortlisted email never goes before the shortlisted one (it would read as
    # the faster, i.e. the "real", answer).
    Rule('decline_before_shortlist', 'not_shortlisted_email_delay_hours',
         ('shortlist_email_delay_minutes', 'not_shortlisted_email_delay_hours'),
         lambda v: v['not_shortlisted_email_delay_hours'] * 60 >= v['shortlist_email_delay_minutes']),
    # R2 — each completion reminder at least two days after the one before.
    _reminders_apart('reminder_1_days', 'reminder_2_days'),
    _reminders_apart('reminder_2_days', 'reminder_3_days'),
    _reminders_apart('reminder_3_days', 'reminder_4_days'),
    # R4 — the query reminder lands inside the answer window, not on or after its end.
    Rule('reminder_outside_window', 'query_reminder_lead_days',
         ('query_reminder_lead_days', 'query_answer_days'),
         lambda v: v['query_reminder_lead_days'] < v['query_answer_days']),
    # R3 — the "a few questions" email reaches the student at least a day before the reminder
    # about those same questions is due.
    Rule('questions_after_reminder', 'query_email_delay_hours',
         ('query_email_delay_hours', 'query_answer_days', 'query_reminder_lead_days'),
         lambda v: v['query_email_delay_hours'] + 24
         <= (v['query_answer_days'] - v['query_reminder_lead_days']) * 24),
    # R5 — a student may change a booking until the cut-off, so the cut-off cannot reach past
    # the earliest slot a reviewer may offer (the slot would be unchangeable from the start).
    Rule('cutoff_beyond_lead', 'interview_reschedule_cutoff_hours',
         ('interview_reschedule_cutoff_hours', 'interview_min_lead_hours'),
         lambda v: v['interview_reschedule_cutoff_hours'] <= v['interview_min_lead_hours']),
    # R6 — the QC-confirmed hold is the SHORTER one (two people already agreed).
    Rule('qc_hold_too_long', 'qc_decline_hold_hours',
         ('qc_decline_hold_hours', 'decline_hold_days'),
         lambda v: v['qc_decline_hold_hours'] <= v['decline_hold_days'] * 24),
    # R7 — the "due soon" nudge must fall before the due date it warns about.
    Rule('nudge_after_due', 'review_nudge_soon_days',
         ('review_nudge_soon_days', 'review_sla_days'),
         lambda v: v['review_nudge_soon_days'] < v['review_sla_days']),
)


def merged(values, keys):
    """`keys` resolved: the value in `values` (what will be STORED), else the platform default."""
    return {k: default(k) if values.get(k) is None else values[k] for k in keys}


def check_rules(values):
    """Raise `OrgConfigError(code, blamed key)` for the first rule the merged settings break.

    ⚠ Runs on a WHOLE settings dict, never on a diff (see the module docstring)."""
    for rule in RULES:
        if all(values.get(k) is None for k in rule.keys):
            continue
        if not rule.ok(merged(values, rule.keys)):
            raise OrgConfigError(rule.code, rule.blames)
