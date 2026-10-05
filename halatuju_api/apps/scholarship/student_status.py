"""The status a STUDENT is shown for her own application — one home (2026-10-05).

It lived inside ``ApplicationReadSerializer.get_status``. The apply gate
(``services/apply_gate.py``) must decide on exactly the same answer: a gate that read the raw
status would let an embargoed-rejected student back into the form, and "the form suddenly lets me
in" would tell her the outcome before the decline email does. So the masking moved here and both
callers read it.

Pure: reads three fields off the row, touches no database.
"""


def student_facing_status(app):
    """The student-facing status is deliberately masked at two points (the admin cockpit uses a
    different serializer and always sees the real status):

    1. Immediate-rejection model: the decision flips to 'rejected' at once, but the student email
       is EMBARGOED for the cool-off to soften the news. Until that email goes (the pending marker
       is still set), the STUDENT sees the stage she was declined FROM (TD-164, 2026-10-03) —
       except 'shortlisted', the one stage that re-opens a write surface, shown as
       'profile_complete' (locked; decisions.md 2026-10-03). Blank -> 'interviewed'.
    2. 'recommended' (formerly 'accepted') is an INTERNAL verification decision a super-admin can
       still reverse (reopen -> interviewed -> possibly declined). The student must NOT perceive
       the jump — a reversal would otherwise be visible (and embarrassing). Good news reaches them
       only via a concrete, non-reversible AWARD OFFER (the award panel keys off the award object,
       not this status); an accepted award is 'active' (not masked).
    """
    status = app.status
    if status == 'rejected' and (app.pending_rejection_category or ''):
        pre = app.pre_decline_status or 'interviewed'   # then rule 2 masks 'recommended'
        status = 'profile_complete' if pre == 'shortlisted' else pre
    return 'interviewed' if status == 'recommended' else status
