"""INFORMAL income documents — the owner's rule (2026-10-27, after #374; widened 2026-10-28, ruling 2A).

*"An informal income document counts ONLY if it carries a HEADER (issuing body) AND an APPROVER (signed
or stamped by someone — ketua kampung, penghulu, headmaster, employer…). A self-declaration form with no
approver does NOT count. Even when it counts, a declared amount is never Certain."* (Ruling 1A: the cap
covers every declared amount.) Ruling 2A: EVERY informal document, not only a recognised declaration form.

**Which documents are informal** (`is_informal`): every supporting income document (`income_support_doc`
— a penghulu / JKKK / employer letter, a bank statement, a declaration); and a payslip the salary model
reads as the INFORMAL family or as a DECLARATION form (`authenticity.doc_seen`). A formal payslip, an EPF
statement and an unscored payslip are not (no genuineness signal is our gap, not the family's — TD-410).

**What the read must find**, in four fields read off the document's IMAGE by one multimodal call
(`APPROVAL_FIELDS`, `read_approval` — review round 2: OCR text cannot tell a stamped box from an empty one
whose label is printed, nor see a hand signature): an issuing body (`issuer_header`) and an approver — a visible official stamp / company chop on its own
(owner ruling 3A, 2026-10-28), or a hand signature by a named or titled person (`approver_name` /
`approver_title`; `has_stamp_or_signature` reads "stamp" / "signature" / "no").

**Never checked is not "missing"** (TD-394: never pass on what nobody has read — and never blame the
family for OUR gap). A document read before these fields existed carries none of them (`approval_unchecked`):
it does not count, and the family is told we are still checking (the gate's existing "try again later"),
never "get it signed"; Check 2 asks nothing about it until it is re-read. A successful image read stores
all four keys and a failed one (our side) stores none, so the two states stay tellable apart.

One reader for every door: `income_shown.proof_flagged` (so the gate, the cluster, the verdict, Check 2 and
TD-409's hold), the student's blocker (`member_approval_state`), the coach (`approval_coach`) and the
officer's drawer reason (`missing_reason`).
"""
import re
from datetime import timedelta

from .genuineness.declaration_doc import DECLARATION

_STR = {'type': 'string'}
#: The four approval fields — read from the document's IMAGE (`read_approval`), never from its OCR text.
APPROVAL_FIELDS = {'issuer_header': _STR, 'approver_name': _STR, 'approver_title': _STR,
                   'has_stamp_or_signature': {'type': 'string', 'enum': ['stamp', 'signature', 'no']}}
_APPROVAL_SCHEMA = {'type': 'object', 'properties': APPROVAL_FIELDS, 'required': list(APPROVAL_FIELDS)}
#: Review round 2: a TEXT read cannot see ink. Real forms print their box labels ("Cop dan tandatangan",
#: "Tandatangan dan Cop Rasmi") whether the box is stamped or EMPTY, and a hand signature has no text at
#: all — so the approval is read from the picture, in its own multimodal call.
APPROVAL_PROMPT = (
    'This image is a Malaysian income document (an employer\'s or village head\'s letter, an informal '
    'payslip, or an income declaration form). Look at the PICTURE, not just the words. Return: '
    '"issuer_header" = the issuing body printed as the letterhead / header (an employer, school, village '
    'committee, government office) — empty if there is none, and never the form\'s own title; '
    '"approver_name" = the name of the person who CONFIRMED / APPROVED it (not the person declaring the '
    'income), empty if none; "approver_title" = their position (e.g. Ketua Kampung, Penghulu, Guru Besar, '
    'Pengurus), empty if none; "has_stamp_or_signature" = "stamp" ONLY if an actual ink or rubber-stamp '
    'impression / company chop is visible on the page (with or without a signature), "signature" ONLY if '
    'a HANDWRITTEN signature is visible and no stamp, else "no". Printed labels such as "Cop dan '
    'tandatangan", printed logos, QR codes and EMPTY signature or stamp boxes are NOT a stamp and NOT a '
    'signature.')
_INFORMAL_TEXT_FAMILIES = frozenset({'informal', 'declaration'})


def read_approval(doc, ex, ocr_text, image_fn):
    """Add the four approval fields to a fresh read ``ex`` of an INFORMAL income document — every
    `income_support_doc`, and a payslip whose OCR text the salary model reads as informal or a declaration
    (`genuineness.declaration_doc.income_doc_genuineness`, deterministic, no call) — from ONE multimodal
    Gemini call on the document's image (`image_fn`, the read's own fetch-once helper). ⚠ COST: one extra
    Gemini image call per such document (formal payslips, EPF and every other type: none).

    A read that failed, or a document of another kind, comes back unchanged. If the image cannot be had or
    the call fails — our side, never the family's — the fields are NOT added and the read is marked
    (`APPROVAL_ERROR`, with a window `APPROVAL_UNTIL` stamped at the FIRST failure, TD-390's shape): the
    document stays "not yet checked" (`approval_unchecked`) and the hourly sweep retries it within the window;
    after it, `approval_expired` — the officer checks by eye and the family is asked again."""
    if ex.get('error') or not isinstance(ex.get('fields'), dict) or \
            getattr(doc, 'doc_type', '') not in ('salary_slip', 'income_support_doc'):
        return ex

    def failed(why):
        from django.utils import timezone
        prior = getattr(doc, 'vision_fields', None)
        until = prior.get(APPROVAL_UNTIL) if isinstance(prior, dict) else None
        return {**ex, APPROVAL_ERROR: why,
                APPROVAL_UNTIL: until or int((timezone.now() + APPROVAL_RETRY_WINDOW).timestamp())}
    from .genuineness.declaration_doc import income_doc_genuineness
    family = income_doc_genuineness(ocr_text or '', doc.doc_type).get('family')
    if doc.doc_type == 'salary_slip' and family not in _INFORMAL_TEXT_FAMILIES:
        return ex
    if _bank_statement(ex['fields'].get('kind'), family, ex['fields'].get('issuer')):
        return ex                                   # owner ruling 4A: the bank's header is enough — no call
    from . import vision
    from .pdf_pages import pdf_pages_png
    data = image_fn()
    if data and vision._is_pdf(getattr(doc, 'content_type', ''), data):
        # Round 3: a form's approval box is often on its LAST page — send the pages stacked (first two +
        # the last, `pdf_pages.MAX_STACKED_PAGES`), still ONE call. Other callers keep page 1 only.
        stacked = pdf_pages_png(data)
        img, mime = (stacked, 'image/png') if stacked else (None, '')
    else:
        img, mime = vision._as_image_for_gemini(data, getattr(doc, 'content_type', '')) if data else (None, '')
    if img is None:
        return failed('no image')
    got = vision._call_gemini_json(APPROVAL_PROMPT, _APPROVAL_SCHEMA, image=img, mime_type=mime)
    if not isinstance(got, dict) or got.get('_error'):
        return failed(str((got or {}).get('_error') or 'no answer')[:200] if isinstance(got, dict) else 'no answer')
    approval = {k: (got.get(k) if isinstance(got.get(k), str) else '') for k in APPROVAL_FIELDS}
    return {**ex, 'fields': {**ex['fields'], **approval}}


#: Round 3 (TD-390's pattern): an approval image read that failed on OUR side is retried by the hourly sweep
#: within this window, stamped at the first failure; after it the read is given up (`approval_expired`).
APPROVAL_ERROR = 'approval_read_error'
APPROVAL_UNTIL = 'approval_read_until'          # epoch seconds, a number on SQLite and Postgres alike
APPROVAL_RETRY_WINDOW = timedelta(hours=72)


def _vf(doc) -> dict:
    vf = getattr(doc, 'vision_fields', None)
    return vf if isinstance(vf, dict) else {}


def approval_expired(doc) -> bool:
    """An informal document whose approval read failed on our side for the whole retry window: no longer
    "still checking" — the officer checks it by eye and the family is asked again (the normal ask)."""
    import time
    vf = _vf(doc)
    return (is_informal(doc) and APPROVAL_ERROR in vf and not any(k in _fields(doc) for k in APPROVAL_FIELDS)
            and float(vf.get(APPROVAL_UNTIL) or 0) <= time.time())

#: The payslip families that are informal income documents (`genuineness.salary_doc` / `declaration_doc`).
_INFORMAL_SLIP_FAMILIES = frozenset({'informal', DECLARATION})


def _seen(doc) -> str:
    from .genuineness.bands import stored_authenticity
    return (stored_authenticity(getattr(doc, 'vision_fields', None)).get('doc_seen') or '').strip().lower()


def is_declaration(doc) -> bool:
    return _seen(doc) == DECLARATION


#: Ruling 4A's banks: the header that makes a bank statement acceptable must NAME one of these (whole words,
#: case-insensitive, matched on the normalised text like every marker list; "BANK" alone is not a bank).
KNOWN_BANKS = ('MAYBANK', 'MALAYAN BANKING', 'CIMB', 'PUBLIC BANK', 'RHB', 'HONG LEONG', 'AMBANK',
               'BANK ISLAM', 'BANK RAKYAT', 'BSN', 'BANK SIMPANAN NASIONAL', 'AGROBANK', 'AFFIN', 'ALLIANCE BANK',
               'OCBC', 'HSBC', 'UOB', 'STANDARD CHARTERED', 'BANK MUAMALAT', 'MBSB', 'AL RAJHI',
               'KUWAIT FINANCE HOUSE')


def _names_a_known_bank(issuer) -> bool:
    import re
    from .genuineness.results_doc import _norm_fold_upper_alnum
    tn = f' {_norm_fold_upper_alnum(issuer or "")} '
    return any(re.search(rf'\b{re.escape(b)}\b', tn) for b in KNOWN_BANKS)


def _bank_statement(kind, seen, issuer) -> bool:
    """Owner ruling 4A (2026-10-28): a bank statement (the text read's own `kind`) is exempt from the approver
    rule — the bank's header is enough — when that header (the text read's `issuer`) NAMES a known Malaysian
    bank (`KNOWN_BANKS`; a self-typed "PENYATA BANK" names none), and unless the scorer reads it as a
    DECLARATION form."""
    return (str(kind or '').strip().lower() == 'bank_statement' and (seen or '') != DECLARATION
            and _names_a_known_bank(issuer))


def is_informal(doc) -> bool:
    """Ruling 2A: a supporting income document, or a payslip read as informal / a declaration form — save a
    bank statement (ruling 4A, `_bank_statement`)."""
    dt = getattr(doc, 'doc_type', '')
    f = _fields(doc)
    if dt == 'income_support_doc':
        # The bank's name may be read from the text (`issuer`) OR off the image (`issuer_header`, hotfix
        # 2026-10-28: a live statement's text read named no issuer, its letterhead did).
        return not (_bank_statement(f.get('kind'), _seen(doc), f.get('issuer'))
                    or _bank_statement(f.get('kind'), _seen(doc), f.get('issuer_header')))
    if dt != 'salary_slip' or _seen(doc) not in _INFORMAL_SLIP_FAMILIES:
        return False
    return not (_seen(doc) == 'informal' and _names_a_government_body(f.get('issuer_header')))


#: Hotfix 2026-10-28: a printed payslip / pension statement whose letterhead (read off the IMAGE) names a
#: GOVERNMENT body — a Jabatan / Kementerian / statutory body or the armed forces — is an official statement,
#: not an informal one (live: JHEV veteran pension statements, a Dewan Bahasa dan Pustaka payslip, both scored
#: 'informal' by the text model). Only the INFORMAL family is exempted: a DECLARATION form printed on a
#: ministry's form (a matriculation "Borang Pengesahan Pendapatan") keeps the approver rule, and #374's
#: village forms read no such header.
_GOVERNMENT_BODY = re.compile(r'\b(JABATAN|KEMENTERIAN|DEWAN BAHASA DAN PUSTAKA|LEMBAGA|MAJLIS|PERBADANAN'
                              r'|ANGKATAN TENTERA|ATM)\b')


def _names_a_government_body(header) -> bool:
    from .genuineness.results_doc import _norm_fold_upper_alnum
    return bool(_GOVERNMENT_BODY.search(_norm_fold_upper_alnum(header or '')))


def _fields(doc) -> dict:
    vf = getattr(doc, 'vision_fields', None)
    f = vf.get('fields') if isinstance(vf, dict) else None
    return f if isinstance(f, dict) else {}


def approval_unchecked(doc) -> bool:
    """An informal document NOT judged yet (none of the keys): read before the approval fields, or its image
    read failed on our side and is still inside its retry window (`approval_expired` takes over after)."""
    return is_informal(doc) and not any(k in _fields(doc) for k in APPROVAL_FIELDS) and not approval_expired(doc)


def approval_missing(doc) -> tuple:
    """What a CHECKED informal document lacks to count: a subset of ``('header', 'approver')``, in that
    order; ``()`` when it carries both, when it is not informal, or when it was never checked
    (`approval_unchecked` answers that).

    The APPROVER (owner ruling 3A, 2026-10-28): a visible official STAMP / company chop is enough on its
    own — a small shop's chopped payslip counts with no named signer; a hand SIGNATURE without a stamp
    still needs a named or titled signer (`approver_name` / `approver_title`); a letter with neither — a
    QR code or logo only, or unmarked — has none. ``has_stamp_or_signature`` reads "stamp" / "signature" /
    "no"; a bare "yes" (an older wording) is taken as a signature, the stricter of the two."""
    if not is_informal(doc) or approval_unchecked(doc):
        return ()
    if approval_expired(doc):
        return ('header', 'approver')            # nothing could be confirmed: the normal rule asks again
    f = _fields(doc)

    def filled(key):
        v = f.get(key)
        return isinstance(v, str) and bool(v.strip())

    mark = str(f.get('has_stamp_or_signature') or '').strip().lower()
    stamped = mark in ('stamp', 'chop', 'cop', 'both')
    signed = mark in ('signature', 'yes', 'ya', 'true')
    named = filled('approver_name') or filled('approver_title')
    approver = stamped or (signed and named)
    # Hotfix 2026-10-28 (live re-read): a village form has no letterhead — a STAMP with a named / titled
    # approver (Ketua Kampung, Pengerusi JKKK, Pesuruhjaya Sumpah…) IS the issuing authority. So approved =
    # (stamp + named) or (header + signature + named) or (header + stamp); header-only or unmarked still fails.
    header = filled('issuer_header') or (stamped and named)
    return tuple(part for part, ok in (('header', header), ('approver', approver)) if not ok)


def approval_counts(doc) -> bool:
    """May this document carry income, as far as the approver rule goes? (Always, for a formal one.)"""
    return not (approval_unchecked(doc) or approval_missing(doc))


#: The officer's documents-drawer reason (`income_shown.unusable`), naming what is missing.
_REASON = {('header',): 'approval_no_header', ('approver',): 'approval_no_approver',
           ('header', 'approver'): 'approval_no_header_approver'}
UNCHECKED_REASON = 'approval_unchecked'
UNREADABLE_REASON = 'approval_unreadable'        # round 3: the image read failed for the whole window


def missing_reason(doc) -> str:
    """The drawer reason for an informal document the approver rule refuses, '' otherwise."""
    if approval_unchecked(doc):
        return UNCHECKED_REASON
    return UNREADABLE_REASON if approval_expired(doc) else _REASON.get(approval_missing(doc), '')


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
