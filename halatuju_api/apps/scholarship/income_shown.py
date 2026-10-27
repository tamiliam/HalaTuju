"""TD-262 chunks 2+3 — ONE per-earner answer to *has this earner's income been SHOWN?*

The owner's rule (2026-09-19, ``docs/decisions.md``): an earner's income is shown ANY ONE of
three PER-EARNER ways — a usable payslip · a readable EPF · a declared amount backed by a
supporting letter that READ.

⚠ A HOUSEHOLD STR IS NOT ONE OF THEM, AND THIS MODULE HAS NO STR ARM. An STR is evidence about
the HOUSEHOLD: it clears the submission gate and settles the verdict by precedence, and the
working adults' income proofs are ADDITIONAL to it, never replaced by it. The absence of a
fourth arm here IS the ruling — adding one silences the salary-picture asks the owner asked for
(F3, owner 2026-07-16) and turns a per-earner cue green on a fact about somebody else.

⚠ IT DECIDES NOTHING NEW. Every arm calls the predicate that already owned it —
``income_engine.usable_salary_slip``, ``income_engine._member_has_epf_value``,
``income_engine.declared_amount`` + ``income_engine.has_income_support_doc`` — so the answer is
the same answer the submission gate has given since 2026-07-25. What is new is that ONE place
gives it, that it names WHICH documents carry it, and that it names, in a STABLE CODE, why a
document the family sent does not. (TD-410, owner 2026-10-27, option A: a proof flagged as possibly
FAKE carries nothing — `proof_flagged`; an informal payslip still counts, EPF waits on TD-411.)

Its readers: ``income_engine.member_income_evidenced`` (the frozen gate answer, expressed as
``shown or str_not_breached``), ``income_engine._member_income_documented`` (the officer's chase
list), ``income_declared_gaps`` (the Check-2 ask about a declared wage — TD-262 F2),
``verdict_engine._verdict_income_salary`` (the verdict's financial-evidence line), and BOTH
screens — the officer cockpit and, since F2, the student's own income wizard — which read it
SERVED on their payloads rather than re-deriving it (``halatuju-web/src/lib/incomeShown.ts``).

⚠ THE STUDENT'S SCREEN READS IT FOR A REASON WORTH KEEPING (F2, the lockout). Her income wizard
used to decide from document PRESENCE whether to offer the cash/informal door — so the moment
ANY salary or EPF file existed for an earner, usable or not, the door closed. A family whose
only payslip was a blurred photo, or whose EPF statement nothing could be read off, was left in
a dead end: the server said their income was not shown, and the one screen that could fix it
had hidden the way. Presence is not evidence on either screen now.

It lives in its own module because ``income_engine.py`` sits on the oversize ledger
(``halatuju_api/code-standards.json``) and a file that may not grow is not where a new rule goes.
"""
from dataclasses import dataclass

from .document_snapshot import live_docs

# ── The three per-earner ways (the value of ``IncomeShown.way``) ─────────────────────────────
WAY_SALARY_SLIP = 'salary_slip'
WAY_EPF = 'epf'
WAY_DECLARED_LETTER = 'declared_letter'
WAYS = (WAY_SALARY_SLIP, WAY_EPF, WAY_DECLARED_LETTER)

# ── Why a document that WAS sent does not carry this earner's income ─────────────────────────
# ⚠ EVERY CODE HERE IS A STATE THE EXISTING PREDICATES ACTUALLY TEST. There is deliberately no
# 'unreadable': `usable_salary_slip` asks nothing about whether a payslip's figures read. Since TD-410
# (owner 2026-10-27) every arm also refuses a proof flagged as possibly fake (`proof_flagged`): a
# payslip scored `not_*` keeps `not_salary`; any other flagged proof reads `suspect`. Inventing a
# finer vocabulary here would put words on the officer's screen that no code can ever produce.
REASON_NOT_SALARY = 'not_salary'                 # payslip slot: scored `not_*` (a MyKad, #47)
REASON_NO_VALUE = 'no_value'                     # EPF: no monthly figure could be derived
REASON_LETTER_UNREAD = 'letter_unread'           # support letter: student_verdict != 'ok' (V1 #2)
REASON_NO_DECLARED_AMOUNT = 'no_declared_amount'  # letter read, but nothing was declared to back
REASON_SUSPECT = 'suspect'                       # TD-410: flagged as possibly fake (`proof_flagged`)
REASONS = (REASON_NOT_SALARY, REASON_NO_VALUE, REASON_LETTER_UNREAD, REASON_NO_DECLARED_AMOUNT,
           REASON_SUSPECT,   # + an informal document's own (#374 / 2A, `income_declaration`): what it lacks
           'approval_no_header', 'approval_no_approver', 'approval_no_header_approver', 'approval_unchecked',
           'approval_unreadable')


#: The salary model's FORMAL families (`genuineness.salary_doc`). Its `suspect` is ONLY `family='informal'`
#: ("not a standard payslip" — wage labels, no statutory scaffold); private / govt / singapore / gig are
#: always `genuine`. So a `suspect` naming one of THESE is a possibly-fake call (a legacy or future score),
#: listed explicitly so an unknown family is never read as one (TD-410 review).
_FORMAL_SLIP_FAMILIES = frozenset({'private', 'govt', 'singapore', 'gig'})


def proof_flagged(doc, doc_type) -> bool:
    """TD-410 (owner ruling 2026-10-27: *"Suspect shouldn't count"*, narrowed by option A the same day:
    only a proof flagged as possibly FAKE). True when an income proof carries no member's income, read at
    every door of this module (the gate, the cluster, the verdict band, the chase list, Check 2, TD-409's
    hold):
      * a ``not_<type>`` wrong-type score, on any arm (a payslip's ``not_salary`` already failed before);
      * a ``suspect`` payslip whose ``doc_seen`` names a FORMAL family (`_FORMAL_SLIP_FAMILIES`). The
        current model never emits one — every suspect slip is informal, a real B40 family's employer
        letter, and STILL COUNTS (the reviewer checks it as today), as does one naming no or an unknown
        family — so this catches a legacy score or a future formal-family band;
      * an INFORMAL document (a support letter, an informal payslip, a declaration form) with no issuing
        body or approver, or not checked for them yet (owner ruling 2A — see the last paragraph).
    ⚠ EPF IS EXCLUDED until TD-411: eight live statements the scorer itself names `epf` read ``not_epf``
    at p=0.00 — no signature matched at all, the shape of a text it could not read, not of a wrong document.

    ⚠ NO SIGNAL STILL COUNTS — an unscored document, ``unchecked``, the flag off, a read our outage
    deferred. Those are OUR gaps: TD-394's rule ("a money gate never passes on a document nobody has READ")
    is about the read, which this does not change, and the student's own wizard has always counted an
    unscored proof ("we never gate on our own missing scan"). The verdict still holds it at Probable.

    ⚠ AN INFORMAL DOCUMENT is judged on its own terms first (owner, after #374; ruling 2A: every support
    letter, informal payslip and declaration form): it counts only with an issuing body AND an approver,
    and not at all while that is unchecked (`income_declaration.approval_counts`), whatever its band."""
    from .income_declaration import approval_counts, is_informal
    if is_informal(doc):
        return not approval_counts(doc)
    if doc_type == 'epf':
        return False                                   # TD-411: the EPF scorer's not_epf is not trusted yet
    from .genuineness.bands import canonical_status, stored_authenticity, stored_status
    vf = getattr(doc, 'vision_fields', None)
    status = canonical_status(stored_status(vf), doc_type)
    if status in ('', 'genuine'):
        return False
    seen = (stored_authenticity(vf).get('doc_seen') or '').strip().lower()
    # TD-410 review: a suspect payslip flags only when it names a FORMAL family, listed explicitly — an
    # informal slip, one naming no family, or any family we do not know keeps the benefit of the doubt.
    return not (status == 'suspect' and doc_type == 'salary_slip' and seen not in _FORMAL_SLIP_FAMILIES)


@dataclass(frozen=True)
class Unusable:
    """One document that was offered as this earner's income evidence and cannot carry it."""
    doc_id: int
    doc_type: str
    reason: str

    def as_dict(self):
        return {'doc_id': self.doc_id, 'doc_type': self.doc_type, 'reason': self.reason}


@dataclass(frozen=True)
class IncomeShown:
    """One earner's answer. ``documents`` are the ids that CARRY the winning way (empty when
    nothing does); ``unusable`` names every income document on file for this earner that cannot
    carry it, whether or not another document did. ``declared`` (not served): the income rests on a
    DECLARED amount — an approved declaration form, or a declared figure backed by a letter — which the
    owner rules is never Certain (the verdict caps it at Probable)."""
    shown: bool
    way: str | None
    documents: tuple
    unusable: tuple
    declared: bool = False

    def as_dict(self):
        return {'shown': self.shown, 'way': self.way,
                'documents': list(self.documents),
                'unusable': [u.as_dict() for u in self.unusable]}


def income_support_docs(application, member):
    """The supporting income documents that could back *member*'s declared amount: tagged to them
    OR untagged (household-level). ONE home for that reading — ``has_income_support_doc`` and the
    per-earner answer must never disagree about which letters are in scope."""
    docs = getattr(application, 'documents', None)
    if docs is None:
        return []
    return list(live_docs(application, 'income_support_doc', members=[member, '']))


def income_support_doc_read(doc) -> bool:
    """True when a supporting income document actually READ — its stored ``student_verdict`` is
    ``'ok'`` (V1 finding #2: mere presence used to "prove" a declared informal income)."""
    vf = getattr(doc, 'vision_fields', None)
    return (vf or {}).get('student_verdict', '') == 'ok' if isinstance(vf, dict) else False


def _ids(docs):
    """The documents' ids, skipping any that HAS none.

    A document with no identity cannot be pointed at on an officer's screen or matched against
    the served payload, so it is named in neither list. The BOOLEAN answer — which is what every
    engine reads — never depends on this."""
    return tuple(i for i in (getattr(d, 'id', None) for d in docs) if i is not None)


def _unusable(docs, doc_type, reason):
    return [Unusable(getattr(d, 'id', None), doc_type, reason)
            for d in docs if getattr(d, 'id', None) is not None]


def _flagged(docs, doc_type):
    """A flagged proof's reason: the declaration's own (what it lacks) or `suspect`."""
    from .income_declaration import missing_reason
    return [u for d in docs for u in _unusable([d], doc_type, missing_reason(d) or REASON_SUSPECT)]


def income_shown(application, member) -> IncomeShown:
    """Has *member*'s income been SHOWN, and by what? See the module docstring — no STR arm."""
    from . import income_engine as ie
    unusable = []

    slips = list(ie._cluster_docs(application, member, 'salary_slip'))
    wrong_type = [d for d in slips if not ie._salary_slip_not_wrongtype(d)]
    usable_slips = [d for d in slips if not proof_flagged(d, 'salary_slip')]       # TD-410
    unusable += _unusable(wrong_type, 'salary_slip', REASON_NOT_SALARY)
    unusable += _flagged([d for d in slips if d not in usable_slips and d not in wrong_type], 'salary_slip')
    from .income_declaration import is_declaration
    forms = [d for d in usable_slips if is_declaration(d)]                         # an approved declaration
    payslips = [d for d in usable_slips if d not in forms]

    epfs = list(ie._cluster_docs(application, member, 'epf'))
    valued = [e for e in epfs if ie._epf_monthly_salary(ie._doc_fields(e)) is not None]
    readable_epfs = [e for e in valued if not proof_flagged(e, 'epf')]                # TD-410
    unusable += _unusable([e for e in epfs if e not in valued], 'epf', REASON_NO_VALUE)
    unusable += _unusable([e for e in valued if e not in readable_epfs], 'epf', REASON_SUSPECT)

    letters = income_support_docs(application, member)
    read = [d for d in letters if income_support_doc_read(d)]
    read_letters = [d for d in read if not proof_flagged(d, 'income_support_doc')]  # TD-410
    declared = ie.declared_amount(application, member)
    unusable += _unusable([d for d in letters if d not in read],
                          'income_support_doc', REASON_LETTER_UNREAD)
    unusable += _flagged([d for d in read if d not in read_letters], 'income_support_doc')
    if declared is None:
        unusable += _unusable(read_letters, 'income_support_doc', REASON_NO_DECLARED_AMOUNT)

    # Precedence matches ``member_income_evidenced``'s own arm order, so the two can never name
    # different winners for one household — save that an approved DECLARATION in the payslip slot
    # yields to a real payslip or a readable EPF, so a declared amount never outranks a document.
    if payslips:
        return IncomeShown(True, WAY_SALARY_SLIP, _ids(payslips), tuple(unusable))
    if readable_epfs:
        return IncomeShown(True, WAY_EPF, _ids(readable_epfs), tuple(unusable))
    if forms:
        return IncomeShown(True, WAY_SALARY_SLIP, _ids(forms), tuple(unusable), declared=True)
    if declared is not None and read_letters:
        return IncomeShown(True, WAY_DECLARED_LETTER, _ids(read_letters), tuple(unusable), declared=True)
    return IncomeShown(False, None, (), tuple(unusable))


def income_shown_map(application, members):
    """``{member: answer.as_dict()}`` for the officer payload — the cockpit reads this instead of
    re-deriving evidence from document PRESENCE (TD-262 W2/W3/W4).

    ⚠ IT COSTS THREE DATABASE QUERIES PER MEMBER (the slips, the EPFs, the letters), so the
    member list is a COST as well as a contract — see ``student_income_members``."""
    return {m: income_shown(application, m).as_dict() for m in members}


def student_income_members(application):
    """The members the STUDENT's own screen can ask about — and therefore the only ones her
    payload has any reason to carry (audit 2026-09-21).

    **What it was.** ``ApplicationReadSerializer`` served all five of ``_MEMBER_ORDER`` on every
    student read AND on the list, which is the call that actually feeds her Documents tab. Four
    of the five were almost always households nobody had declared, at three queries each.

    **What the screen asks.** ``IncomeWizard`` renders one ``MemberIncomeGroup`` per block of
    ``incomeWizard.salaryMemberBlocks(a.income_working_members)``, and salary route only. So the
    served keys the web can ever look up are that list — nothing else reads this field.

    **Why an ABSENT member is safe, and this is the load-bearing half.** ``incomeShown.answerFor``
    returns ``null`` for a key that is not there, and every caller treats ``null`` as *"no served
    answer — fall back to the old presence reading"*, never as *"nothing is shown"*. That
    fallback exists because the two services deploy together but not atomically. Narrowing the
    map therefore lands on a path the front end already handles by design. The answers that ARE
    served are byte-identical: this changes which keys the dict has, never what one says.

    ⚠ THE DECLARED EARNERS ARE INCLUDED even though today's screen reads blocks only. A member
    can carry a declared amount while the working-members list is being edited, and one extra key
    costs three queries only when such a member exists — whereas a key the screen wanted and did
    not get degrades an earner silently to the presence reading this whole module replaced.
    """
    from .income_engine import _MEMBER_ORDER
    declared = getattr(application, 'income_declared', None)
    chosen = set(getattr(application, 'income_working_members', None) or ())
    if isinstance(declared, dict):
        chosen |= {m for m, amount in declared.items() if amount}
    return [m for m in _MEMBER_ORDER if m in chosen]
