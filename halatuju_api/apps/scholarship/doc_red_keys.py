"""WHICH CHECK KEYS MAKE A DOCUMENT RED — the one home (TD-110, 2026-10-04).

Two readers ask "is this uploaded document a confirmed person-mismatch?":

  * `resolution.doc_match_verdict` — the Action Centre: may this upload close the task it answers?
  * `services.blockers.document_red_blockers` — the consent gate: may she submit?

Until 2026-10-04 each spelled out, per document type, which `student_*_check` keys count, and the
two lists had to be kept in lockstep by a paired comment. They now both read `PERSON_RED_KEYS`.

⚠ ONLY THE KEYS LIVE HERE, NOT THE POLICY. Each reader still decides WHEN the rule applies —
the gate skips the income cluster once income is established, blocks a salary slip only when it
is compulsory and never blocks on EPF; the Action Centre lets the IC-number chain rescue a parent
IC and also refuses a non-official offer. Those are deliberate differences between two different
questions, each pinned with its reason in `tests/test_doc_red_keys_drift.py`. A key added here
reaches BOTH readers at once — which is the point.

`results_slip` is NOT in the table: the two readers deliberately disagree about a GRADE mismatch
(the gate stopped blocking on it, owner 2026-07-08; the Action Centre still holds the task), so
each names its own keys beside its reason. See the drift test.
"""

#: doc_type -> the check keys whose value 'mismatch' makes that document a confirmed person-red.
PERSON_RED_KEYS = {
    'offer_letter': ('name', 'ic'),
    'parent_ic': ('name_status', 'proof_name_status', 'proof_nric_status'),
    'salary_slip': ('name_status', 'nric_status'),
    'epf': ('name_status', 'nric_status'),
    'str': ('name_status', 'nric_status'),
    # The FATHER row is deliberately absent (BrightPath #23, owner 2026-09-08): a father with no
    # Malaysian IC must never be what holds the door. Child and mother still do.
    'birth_certificate': ('child_status', 'mother_status'),
    'guardianship_letter': ('guardian_status', 'ward_status'),
}


def person_red(doc_type, check):
    """True when `check` (a `student_*_check` dict, or None) carries 'mismatch' on any of the
    person keys for `doc_type`. A type not in the table is never red here."""
    keys = PERSON_RED_KEYS.get(doc_type, ())
    return any((check or {}).get(k) == 'mismatch' for k in keys)
