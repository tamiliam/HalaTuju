"""INFORMAL income documents — the owner's rule (2026-10-27, after #374; widened 2026-10-28, ruling 2A).

*"An informal income document counts ONLY if it carries a HEADER (issuing body) AND an APPROVER (signed
or stamped by someone — ketua kampung, penghulu, headmaster, employer…). A self-declaration form with no
approver does NOT count. Even when it counts, a declared amount is never Certain."* (Ruling 1A: the cap
covers every declared amount.) Ruling 2A: EVERY informal document, not only a recognised declaration form.

**Which documents are informal** (`is_informal`): every supporting income document (`income_support_doc`
— a penghulu / JKKK / employer letter, a bank statement, a declaration); and a payslip the salary model
reads as the INFORMAL family or as a DECLARATION form (`authenticity.doc_seen`). A formal payslip, an EPF
statement and an unscored payslip are not (no genuineness signal is our gap, not the family's — TD-410).

**What the read must find**, in four fields the extraction schema gained for both slots (`APPROVAL_FIELDS`):
an issuing body (`issuer_header`) and an approver — a named or titled person (`approver_name` /
`approver_title`) whose signature or stamp is visible (`has_stamp_or_signature`).

**Never checked is not "missing"** (TD-394: never pass on what nobody has read — and never blame the
family for OUR gap). A document read before these fields existed carries none of them (`approval_unchecked`):
it does not count, and the family is told we are still checking (the gate's existing "try again later"),
never "get it signed"; Check 2 asks nothing about it until it is re-read. Every read since stores all four
keys (`vision._sanitize_extracted_fields`), so the two states stay tellable apart.

One reader for every door: `income_shown.proof_flagged` (so the gate, the cluster, the verdict, Check 2 and
TD-409's hold), the student's blocker (`member_approval_state`), the coach (`approval_coach`) and the
officer's drawer reason (`missing_reason`).
"""
from .genuineness.declaration_doc import DECLARATION

_STR = {'type': 'string'}
#: Added to the `salary_slip` and `income_support_doc` extraction schemas (`vision._FIELD_SCHEMAS`).
APPROVAL_FIELDS = {'issuer_header': _STR, 'approver_name': _STR, 'approver_title': _STR,
                   'has_stamp_or_signature': _STR}
#: Appended to both slots' extraction prompts.
APPROVAL_HINT = (
    ' Also return: "issuer_header" = the issuing body printed as the document\'s letterhead / header '
    '(an employer, school, village committee, government office) — empty if there is none, and never '
    'the form\'s own title; "approver_name" = the name of the person who CONFIRMED / APPROVED the '
    'document (not the person declaring the income); "approver_title" = their position (e.g. Ketua '
    'Kampung, Penghulu, Guru Besar, Pengurus); "has_stamp_or_signature" = "yes" if that approver\'s '
    'signature or an official stamp/chop is visible, else "no".')

#: The payslip families that are informal income documents (`genuineness.salary_doc` / `declaration_doc`).
_INFORMAL_SLIP_FAMILIES = frozenset({'informal', DECLARATION})


def _seen(doc) -> str:
    from .genuineness.bands import stored_authenticity
    return (stored_authenticity(getattr(doc, 'vision_fields', None)).get('doc_seen') or '').strip().lower()


def is_declaration(doc) -> bool:
    return _seen(doc) == DECLARATION


def is_informal(doc) -> bool:
    """Ruling 2A: a supporting income document, or a payslip read as informal / a declaration form."""
    dt = getattr(doc, 'doc_type', '')
    return dt == 'income_support_doc' or (dt == 'salary_slip' and _seen(doc) in _INFORMAL_SLIP_FAMILIES)


def _fields(doc) -> dict:
    vf = getattr(doc, 'vision_fields', None)
    f = vf.get('fields') if isinstance(vf, dict) else None
    return f if isinstance(f, dict) else {}


def approval_unchecked(doc) -> bool:
    """An informal document whose read predates the approval fields — NOT judged yet (none of the keys)."""
    return is_informal(doc) and not any(k in _fields(doc) for k in APPROVAL_FIELDS)


def approval_missing(doc) -> tuple:
    """What a CHECKED informal document lacks to count: a subset of ``('header', 'approver')``, in that
    order; ``()`` when it carries both, when it is not informal, or when it was never checked
    (`approval_unchecked` answers that). The approver is a named or titled person whose signature or
    stamp is visible (a name with no mark, or a mark nobody owns, is not one)."""
    if not is_informal(doc) or approval_unchecked(doc):
        return ()
    f = _fields(doc)

    def filled(key):
        v = f.get(key)
        return isinstance(v, str) and bool(v.strip())

    marked = str(f.get('has_stamp_or_signature') or '').strip().lower() in ('yes', 'ya', 'true')
    approver = marked and (filled('approver_name') or filled('approver_title'))
    return tuple(part for part, ok in (('header', filled('issuer_header')), ('approver', approver)) if not ok)


def approval_counts(doc) -> bool:
    """May this document carry income, as far as the approver rule goes? (Always, for a formal one.)"""
    return not (approval_unchecked(doc) or approval_missing(doc))


#: The officer's documents-drawer reason (`income_shown.unusable`), naming what is missing.
_REASON = {('header',): 'approval_no_header', ('approver',): 'approval_no_approver',
           ('header', 'approver'): 'approval_no_header_approver'}
UNCHECKED_REASON = 'approval_unchecked'


def missing_reason(doc) -> str:
    """The drawer reason for an informal document the approver rule refuses, '' otherwise."""
    return UNCHECKED_REASON if approval_unchecked(doc) else _REASON.get(approval_missing(doc), '')


#: The student's blocker code and the coach code: "upload it signed and stamped by an approver".
UNAPPROVED = 'income_doc_unapproved'
COACH = 'income_doc_needs_approver'


def member_approval_state(application, member) -> str:
    """Why *member*'s informal income documents do not carry their income, read only where the gate
    has already found it NOT shown: ``'unchecked'`` (a document we have not checked yet — the family is
    told to try later, never blamed), ``'unapproved'`` (checked, no header / approver — ask for it signed
    and stamped), or ``''`` (neither — the ordinary "show their income" ask)."""
    from .income_engine import _cluster_docs
    from .income_shown import income_support_doc_read, income_support_docs
    docs = list(_cluster_docs(application, member, 'salary_slip')) + [
        d for d in income_support_docs(application, member) if income_support_doc_read(d)]
    if any(approval_unchecked(d) for d in docs):
        return 'unchecked'
    return 'unapproved' if any(approval_missing(d) for d in docs) else ''


def approval_coach(doc) -> str:
    """The coach's code for a checked informal document that lacks its header or approver, else ''."""
    return COACH if approval_missing(doc) else ''
