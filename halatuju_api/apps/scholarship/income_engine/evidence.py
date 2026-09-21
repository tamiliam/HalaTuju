"""Whether the household has proved its income: `has_valid_str`, `household_str_status`,
`str_not_breached`, `member_income_evidenced`, `salary_income_satisfied`,
`income_established`, and the declared amount beside them.

⛔ ELIGIBILITY. Every verdict the income rule reaches passes through this module. It was
moved byte-identically at code health H16 and NOT touched; the owner rulings behind it are
TD-262 chunks 1-3, rule-4 items 1 and 1b, F8, and the 2026-09-20 ruling that the cash door
stays off the STR route.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from __future__ import annotations

from .identity_checks import _cluster_docs, _member_ic_doc, student_income_ic_check, student_income_proof_check
from .relationships import effective_working_members, relationship_doc_for
from .salary_figures import _doc_fields, _epf_monthly_salary
from .str_route import student_str_check


def has_valid_str(application):
    """True when the household has a VALID STR DOCUMENT on file — approved and at least
    'unconfirmed' currency (a genuine, un-rejected STR), on either income route. A valid STR
    is the household's own means-test, so it lets a working member's DECLARED informal income
    be ACCEPTED without a payslip (the STR already establishes B40 need — P5b). Reads the STR
    *document* via ``student_str_check``, never the ``receives_str`` self-tick."""
    docs = getattr(application, 'documents', None)
    if docs is None:
        return False
    str_doc = docs.filter(doc_type='str', superseded_at__isnull=True).order_by('-uploaded_at').first()
    if str_doc is None:
        return False
    sc = student_str_check(str_doc)
    return bool(sc and sc['current_status'] in ('current', 'unconfirmed'))


def household_str_status(application):
    """Owner 2026-07-07 — the single, ROUTE-AGNOSTIC "does this household hold a dispositive STR?".
    A genuine, approved, non-breached STR is the government's own means-test, so it settles B40 —
    on EITHER income route, before the route is even considered (STR PRECEDENCE; the CALLER hoists
    it above the route split). Returns ``(grade, member)`` where grade ∈ {'current','unconfirmed'}
    and member is the parent/guardian the recipient resolves to — or ``(None, None)`` when the STR
    is missing, BREACHED (rejected / wrong_type / stale / unreadable, or judged non-genuine), or its
    recipient matches NO household member (a stranger's STR proves nothing here).

    Supersedes ``salary_route_str``: the recipient match is now exhaustive across EVERY parent/
    guardian (name OR nric, independently — done inside ``student_str_check``), so "breached" is a
    LAST resort reached only when all matching attempts fail — not a first read off the declared
    earner. The CALLER still confirms the matched member's relationship to the student before it
    greens (so a matched-but-unrelated recipient can't settle B40)."""
    docs = getattr(application, 'documents', None)
    if docs is None:
        return None, None
    str_doc = docs.filter(doc_type='str', superseded_at__isnull=True).order_by('-uploaded_at').first()
    if str_doc is None:
        return None, None
    # Genuineness guard: a positively non-genuine STR is breached (mirrors str_not_breached).
    vf = getattr(str_doc, 'vision_fields', None) or {}
    auth = (vf.get('authenticity') or {}).get('status', '') if isinstance(vf, dict) else ''
    if auth and auth not in ('genuine', 'likely_genuine'):
        return None, None
    sc = student_str_check(str_doc)
    if not sc or sc['current_status'] not in ('current', 'unconfirmed'):
        return None, None
    if sc['name_status'] == 'match' or sc['nric_status'] == 'match':
        return sc['current_status'], sc['member']
    return None, None


def str_not_breached(application):
    """True when a genuine, NON-BREACHED STR is on file — approved-ish (any currency state EXCEPT
    wrong_type / rejected / unread) and not judged non-genuine. Mirrors the officer cockpit's
    ``strNotBreached`` (officerCockpit.ts): a non-breached STR makes the salary-route documents
    SUPPORTIVE, not compulsory, on EITHER route (owner 2026-07-05: "STR not breached → no full salary
    docs needed"). BROADER than ``has_valid_str`` (currency-only current/unconfirmed): a stale-but-
    genuine STR is also 'not breached'. Keeps the consent gate + the student's wizard checklist in step
    with what the student is SHOWN — otherwise the docs box says "not required" while the gate blocks."""
    docs = getattr(application, 'documents', None)
    if docs is None:
        return False
    str_doc = docs.filter(doc_type='str', superseded_at__isnull=True).order_by('-uploaded_at').first()
    if str_doc is None:
        return False
    sc = student_str_check(str_doc)
    cs = (sc or {}).get('current_status', '')
    if not cs or cs in ('wrong_type', 'rejected'):     # no read at all, or a failed STR → breached
        return False
    vf = getattr(str_doc, 'vision_fields', None) or {}
    auth = (vf.get('authenticity') or {}).get('status', '') if isinstance(vf, dict) else ''
    return not (auth and auth not in ('genuine', 'likely_genuine'))   # a positive non-genuine call → breached


def str_confirmed_current(application):
    """True when the household's latest live STR reads as CURRENT — approved AND showing a payment
    this cycle. This is the exact criterion the Action-Centre ``str_not_current`` request asks the
    student to satisfy ("confirm it's approved AND being paid"). An 'unconfirmed' (Lulus but no
    payment date), 'unreadable', 'stale' or rejected STR is NOT current — so re-uploading one must not
    silence that ask (the SUBMISSION gate still accepts it as Probable; only the request stays open)."""
    docs = getattr(application, 'documents', None)
    if docs is None:
        return False
    str_doc = docs.filter(doc_type='str', superseded_at__isnull=True).order_by('-uploaded_at').first()
    if str_doc is None:
        return False
    sc = student_str_check(str_doc)
    return bool(sc and sc['current_status'] == 'current')


def _salary_slip_not_wrongtype(doc) -> bool:
    """True unless the doc's stored genuineness says it isn't a salary slip at all ('not_salary' —
    a MyKad/other doc in the slot, #47). FAIL-OPEN: no authenticity signal (unscored / pre-model),
    'genuine', or 'suspect' (informal) → True. So an unscored legacy slip counts unchanged; only a
    slip EXPLICITLY scored not_salary is excluded."""
    from ..genuineness.bands import canonical_status
    vf = doc.vision_fields if isinstance(getattr(doc, 'vision_fields', None), dict) else {}
    raw = (vf.get('authenticity') or {}).get('status', '')
    return not canonical_status(raw, 'salary_slip').startswith('not_')


def usable_salary_slip(application, member) -> bool:
    """A salary_slip tagged to *member* that reads as an actual payslip — the #47 fix: a doc scored
    'not_salary' (a MyKad/other doc in the salary-slip slot) no longer satisfies the income-proof
    requirement. SOFT: the miss becomes a Check-2 're-upload the payslip' item, never a hard trap
    (fail-open on any doc without a not_salary signal)."""
    return any(_salary_slip_not_wrongtype(d)
               for d in _cluster_docs(application, member, 'salary_slip'))


def _member_has_epf_value(application, member) -> bool:
    """A readable EPF statement tagged to *member* — a monthly-salary figure could be derived
    (including 0.0 for an all-zeros / lapsed account). It documents the member's income situation,
    so it counts as income evidence for the gate (owner 2026-07-25)."""
    return any(_epf_monthly_salary(_doc_fields(e)) is not None
               for e in _cluster_docs(application, member, 'epf'))


def member_income_evidenced(application, member) -> bool:
    """True when a working member's income is SHOWN — ANY ONE way (owner 2026-07-25):
      - a usable salary slip (not a wrong-type doc), OR
      - a readable EPF (KWSP) statement, OR
      - a DECLARED average amount backed by a supporting letter (``income_support_doc`` — a school /
        ketua-kampung / penghulu / employer letter), OR
      - a non-breached household STR (the government means-test standing in, P3 precedence).

    ⚠ THE FOURTH ARM IS A SUBMISSION-GATE SHORTCUT ABOUT THE HOUSEHOLD, NOT A STATEMENT ABOUT
    THIS MEMBER (owner 2026-09-19, ``docs/decisions.md``). An STR is evidence that the HOUSEHOLD
    is B40; it says nothing about what this earner earns, and a working adult's income proof is
    ADDITIONAL to a proven STR, never replaced by it. So a PER-EARNER cue — the student's green
    tick, the officer's per-member slot — must NOT read this predicate as "this member's income
    is shown". The web's student-side cue deliberately carries only the first three arms.

    The SINGLE source for the salary-route "income proof" requirement — read by both
    ``member_cluster_complete`` and ``services.income_doc_blockers`` so the gate and the wizard
    can never disagree. A declared amount ALONE (no letter) does NOT count: it stays 'unproven'
    (Unsure) until the letter lands (owner decision, mirroring ``earner_monthly_income``'s
    ``declared_unproven``) — the assessment never inflates income on an unbacked self-report.

    ⚠ THE FIRST THREE ARMS NOW LIVE IN ``income_shown`` AND THIS IS A PURE RE-EXPRESSION (TD-262
    chunks 2+3). The gate's answer did not move by a single row — ``income_shown(...).shown`` IS
    the OR of the same three predicates, in the same order, and the fourth arm is still OR-ed on
    here and ONLY here. That split is the whole point: the per-earner answer has no STR arm, so
    every per-earner reader (the officer's slot, the chase list, the verdict's evidence line)
    gets the owner's rule, while the household gate keeps the shortcut it has always had."""
    from ..income_shown import income_shown
    return income_shown(application, member).shown or str_not_breached(application)


def any_member_income_evidenced(application) -> bool:
    """True when AT LEAST ONE working member's income is SHOWN any one way
    (``member_income_evidenced``). Deliberately WEAKER than ``member_cluster_complete``: it asks only
    *has this household shown what it earns?*, not *is the earner's relationship to the student
    proven?*.

    It exists for ONE caller — the GRANDFATHERED branch of ``services.application_completeness``
    (BrightPath request #21). That branch is a 5-June-2026 copy of the income bar, frozen as
    ``bool(present & {'str', 'salary_slip', 'epf'})`` — three DOCUMENT TYPES. On 25 July 2026 the
    live rule became "income shown ANY ONE WAY", which added a fourth way with no document of its
    own: a DECLARED average amount backed by an ``income_support_doc`` (a school / ketua-kampung /
    penghulu / employer letter). The frozen copy cannot see that fourth way, so a household that
    proved its income the modern way was told its profile was incomplete — application 144 sat at
    Interview with every officer verdict recorded and could not be accepted (measured on production
    2026-09-07: she was the ONLY submitted application lacking all three legacy proof types).

    ⚠ THIS IS AN OR-ARM, NEVER A REPLACEMENT — see the call site. Every document set the frozen
    rule accepted must keep passing, or a fix for one stuck student un-submits a cohort. Widening
    here can only ever UNBLOCK; it can never newly block.

    ⚠ AND IT MUST NOT BECOME ``member_cluster_complete``. That predicate also demands the earner's
    IC read cleanly AND link to the student (for a mother, through the birth certificate). Applicant
    144's birth certificate scored ``not_birth_certificate`` with every field blank, so her cluster
    is NOT complete and never will be until that document is re-read — and the relationship is the
    REVIEWER's judgement at interview, not a precondition for the reviewer being allowed to work the
    case. Tightening this to the cluster rule re-traps her."""
    return any(member_income_evidenced(application, m)
               for m in effective_working_members(application, any_route=True))


def member_cluster_complete(application, member):
    """True when this working member's salary-route income cluster is COMPLETE and COHERENT on its
    own — the unit behind the "one complete, clean earner cluster is enough to submit" gate (owner
    2026-07-08). Requires:
      - the earner's IC present, readable, and LINKING to the student (name_status 'match' — the
        shared patronymic for a father/sibling, the birth certificate for a mother, the letter for
        a guardian);
      - this earner's income SHOWN any one way (``member_income_evidenced``: a usable salary slip,
        a readable EPF, a declared amount + a supporting letter, OR a non-breached household STR);
      - the relationship doc present where required (mother -> birth certificate, guardian ->
        letter; father/sibling need none);
      - NO person-mismatch between the IC and the salary slip.
    A member whose cluster clears this carries the application through the income gate; every OTHER
    member's missing docs or document errors then become soft Check-2 follow-ups (see
    `salary_income_satisfied`)."""
    if not member:
        return False
    ic = _member_ic_doc(application, member)
    if ic is None:
        return False
    icc = student_income_ic_check(ic)
    if not icc or not icc.get('readable') or icc.get('name_status') != 'match':
        return False
    if not member_income_evidenced(application, member):
        return False
    for p in _cluster_docs(application, member, 'salary_slip'):
        pc = student_income_proof_check(p)
        if pc and 'mismatch' in (pc.get('name_status'), pc.get('nric_status')):
            return False
    rel = relationship_doc_for(member)
    if rel and not application.documents.filter(
            doc_type=rel, superseded_at__isnull=True).exists():
        return False
    return True


def salary_income_satisfied(application):
    """True when AT LEAST ONE working member has a complete, clean cluster
    (`member_cluster_complete`). This is the "one clean cluster is enough to submit" gate (owner
    2026-07-08): once one earner is fully and coherently documented, every OTHER member's missing
    docs AND document errors (e.g. an extraneous, misread second-parent IC) become soft Check-2
    follow-ups, never submission blockers.

    ROUTE-AGNOSTIC since 2026-07-22 (owner: "it is either STR or salary — either one is fine;
    students may fulfil both but are not required to"). It used to return False off the declared
    salary route, which asked *which radio button did they tick?* instead of *what did they
    actually prove* — so a student who declared STR, had the STR fail the format gate, yet fully
    documented an earner (#116: mother's IC + genuine payslip + a birth certificate linking her to
    the student) was trapped with her salary evidence never even inspected. Earners are resolved
    with ``any_route=True`` because such a student never touches the salary checkboxes.

    NO LONGER confined to the submission gate (2026-08-01). It was — and the sentence that used to
    stand here said so, adding "so widening it moves no verdict and no band". That confinement was
    exactly what let the gate and the verdict disagree about one household: the gate accepted #106's
    salary cluster and let her submit, while `verdict_engine._verdict_income` filed her declared-but-
    absent STR as a hard gap and painted the same household RED. The verdict now calls this
    predicate too (str-proof-spec.md §6 rule 2, the ABSENT-STR case), so **widening it MOVES A
    BAND** — measure the blast radius on production before you touch it. Callers today:
    `services.income_doc_blockers` / `document_red_blockers` (the gate) and
    `verdict_engine._verdict_income` (the band)."""
    return any(member_cluster_complete(application, m)
               for m in effective_working_members(application, any_route=True))


def income_established(application):
    """True when the household's income is ALREADY established by a clean, dispositive document, on
    EITHER route: a complete salary cluster (`salary_income_satisfied`) OR a valid household STR
    (`household_str_status` — the government's means-test, matched to a parent/guardian). Owner
    2026-07-08: in either case an EXTRANEOUS or misread income document must NOT hard-block
    submission — it becomes a soft Check-2 follow-up. This is the route-agnostic form of "one clean
    cluster is enough"; it also covers the STR twin where the OTHER parent's IC is cross-checked
    against a single-recipient STR and 'mismatches' meaninglessly (a valid father's STR + an
    extraneous mother IC, #28).

    Genuinely route-agnostic since 2026-07-22: `salary_income_satisfied` no longer returns False
    off the declared salary route, so a FAILED STR plus a complete salary cluster now establishes
    income (#116) — which is what this docstring promised all along."""
    if salary_income_satisfied(application):
        return True
    grade, _member = household_str_status(application)
    return grade is not None


def declared_amount(application, member):
    """A working member's DECLARED average monthly income (RM, int > 0) from the income
    wizard, or None. Stored in ``ScholarshipApplication.income_declared = {member: amount}``.
    Tolerant of a blank/None/garbage value."""
    raw = getattr(application, 'income_declared', None)
    if not isinstance(raw, dict):
        return None
    try:
        amt = int(raw.get(member))
    except (TypeError, ValueError):
        return None
    return amt if amt > 0 else None


def has_income_support_doc(application, member):
    """True when a supporting income document is on file for this member AND IT READ —
    an ``income_support_doc`` (an employer/wage letter, bank statements showing income, OR a
    community/penghulu letter; D1 flexible evidence, any ONE suffices). Backs a DECLARED
    amount for a non-STR household. Accepts a doc tagged to the member OR untagged
    (household-level) — an Action-Centre request upload may land without a member tag, and
    one family-level supporting letter is enough under the flexible-evidence rule.

    **V1 (finding #2):** mere PRESENCE no longer counts — a blank/wrong image used to "prove"
    a declared informal income. The doc must have been READ: its stored ``student_verdict``
    (from the field-extraction on upload) is ``'ok'`` (a real support document with at least
    one field). A doc that read nothing (``'wrong_doc'``) or was never scanned does NOT clear
    the gap, so Check 2 keeps asking for real evidence.

    The reading lives in ``income_shown`` (TD-262 chunks 2+3) so the per-earner answer and this
    predicate can never disagree about which letters are in scope."""
    from ..income_shown import income_support_doc_read, income_support_docs
    return any(income_support_doc_read(d) for d in income_support_docs(application, member))
