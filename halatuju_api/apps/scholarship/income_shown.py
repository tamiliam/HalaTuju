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
document the family sent does not.

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
# 'unreadable' and no 'flagged_not_genuine': `usable_salary_slip` asks ONE question of a payslip
# (does its stored genuineness say it is not a payslip at all — the #47 fix) and nothing about
# whether its figures read; `_member_has_epf_value` asks only whether a monthly figure could be
# derived and consults no genuineness signal. Inventing a finer vocabulary here would put words
# on the officer's screen that no code can ever produce.
REASON_NOT_SALARY = 'not_salary'                 # payslip slot: scored `not_*` (a MyKad, #47)
REASON_NO_VALUE = 'no_value'                     # EPF: no monthly figure could be derived
REASON_LETTER_UNREAD = 'letter_unread'           # support letter: student_verdict != 'ok' (V1 #2)
REASON_NO_DECLARED_AMOUNT = 'no_declared_amount'  # letter read, but nothing was declared to back
REASONS = (REASON_NOT_SALARY, REASON_NO_VALUE, REASON_LETTER_UNREAD, REASON_NO_DECLARED_AMOUNT)


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
    carry it, whether or not another document did."""
    shown: bool
    way: str | None
    documents: tuple
    unusable: tuple

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


def income_shown(application, member) -> IncomeShown:
    """Has *member*'s income been SHOWN, and by what? See the module docstring — no STR arm."""
    from . import income_engine as ie
    unusable = []

    slips = list(ie._cluster_docs(application, member, 'salary_slip'))
    usable_slips = [d for d in slips if ie._salary_slip_not_wrongtype(d)]
    unusable += _unusable([d for d in slips if d not in usable_slips],
                          'salary_slip', REASON_NOT_SALARY)

    epfs = list(ie._cluster_docs(application, member, 'epf'))
    readable_epfs = [e for e in epfs if ie._epf_monthly_salary(ie._doc_fields(e)) is not None]
    unusable += _unusable([e for e in epfs if e not in readable_epfs], 'epf', REASON_NO_VALUE)

    letters = income_support_docs(application, member)
    read_letters = [d for d in letters if income_support_doc_read(d)]
    declared = ie.declared_amount(application, member)
    unusable += _unusable([d for d in letters if d not in read_letters],
                          'income_support_doc', REASON_LETTER_UNREAD)
    if declared is None:
        unusable += _unusable(read_letters, 'income_support_doc', REASON_NO_DECLARED_AMOUNT)

    # Precedence matches ``member_income_evidenced``'s own arm order, so the two can never name
    # different winners for one household.
    if usable_slips:
        return IncomeShown(True, WAY_SALARY_SLIP, _ids(usable_slips), tuple(unusable))
    if readable_epfs:
        return IncomeShown(True, WAY_EPF, _ids(readable_epfs), tuple(unusable))
    if declared is not None and read_letters:
        return IncomeShown(True, WAY_DECLARED_LETTER, _ids(read_letters), tuple(unusable))
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
