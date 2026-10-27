"""Income DECLARATIONS — the owner's rule (2026-10-27, after #374).

*"An informal income document counts ONLY if it carries a HEADER (issuing body) AND an APPROVER (signed
or stamped by someone — ketua kampung, penghulu, headmaster, employer…). A self-declaration form with no
approver does NOT count. Even when it counts, a declared amount is never Certain."*

A declaration is RECOGNISED by its scorer (`genuineness.declaration_doc`: stored `authenticity.doc_seen
== 'declaration'`, in the salary-slip or the support-document slot) and JUDGED here, off what the read
found on it — four fields the extraction schema gains for both slots (`APPROVAL_FIELDS`). One reader for
every door: `income_shown.proof_flagged` (so the gate, the cluster, the verdict, Check 2 and TD-409's
hold), the student's blocker (`unapproved_declaration_member`), the coach (`declaration_coach`) and the
officer's drawer reason (`missing_reason`). A document read before these fields existed has none of them
— but it was also scored before declarations were recognised, so it is not one until it is re-read.
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


def is_declaration(doc) -> bool:
    from .genuineness.bands import stored_authenticity
    seen = (stored_authenticity(getattr(doc, 'vision_fields', None)).get('doc_seen') or '')
    return seen.strip().lower() == DECLARATION


def declaration_missing(doc) -> tuple:
    """What a DECLARATION lacks to count: a subset of ``('header', 'approver')``, in that order; ``()``
    when it carries both — or when it is not a declaration at all. The approver is a named or titled
    person whose signature or stamp is visible (a name with no mark, or a mark nobody owns, is not one)."""
    if not is_declaration(doc):
        return ()
    vf = getattr(doc, 'vision_fields', None)
    f = (vf.get('fields') if isinstance(vf, dict) else None) or {}

    def filled(key):
        v = f.get(key)
        return isinstance(v, str) and bool(v.strip())

    marked = str(f.get('has_stamp_or_signature') or '').strip().lower() in ('yes', 'ya', 'true')
    approver = marked and (filled('approver_name') or filled('approver_title'))
    return tuple(part for part, ok in (('header', filled('issuer_header')), ('approver', approver)) if not ok)


#: The officer's documents-drawer reason (`income_shown.unusable`), naming what is missing.
_REASON = {('header',): 'declaration_no_header', ('approver',): 'declaration_no_approver',
           ('header', 'approver'): 'declaration_no_header_approver'}


def missing_reason(doc) -> str:
    """The drawer reason for a declaration that does not count, '' for one that does (or no declaration)."""
    return _REASON.get(declaration_missing(doc), '')


#: The student's blocker code and the coach code: "upload the form signed and stamped by an approver".
UNAPPROVED = 'income_declaration_unapproved'
COACH = 'declaration_needs_approver'


def unapproved_declaration_member(application, member) -> bool:
    """Does *member*'s income proof include a declaration that lacks its header or approver? Read only
    where the gate has already found the member's income NOT shown, to pick the ask's words."""
    from .income_engine import _cluster_docs
    from .income_shown import income_support_docs
    docs = list(_cluster_docs(application, member, 'salary_slip')) + income_support_docs(application, member)
    return any(declaration_missing(d) for d in docs)


def declaration_coach(doc) -> str:
    """The coach's code for a declaration that lacks its header or approver, else ''."""
    return COACH if declaration_missing(doc) else ''
