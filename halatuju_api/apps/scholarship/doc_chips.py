"""The document chip standard, Sprint 0: ONE server-side home for each document's chips.

DISPLAY ONLY. Nothing here decides a verdict, a band, an award or eligibility, and no engine may
import this module (guarded by ``tests/test_doc_chips_import_fence.py``). It reads the document
SERIALIZER OUTPUT (the dict ``ApplicantDocumentSerializer`` builds), so it runs no DB query.

Sprint 0 reproduces TODAY's officer-drawer colours exactly. Each rule below is a line-for-line
port of the web functions that colour the chips today, and the shared parity fixture
(``tests/fixtures/doc_chip_parity.json``) is checked against both sides:

- ``halatuju-web/src/lib/cockpitDocFacts.ts``   ``documentFacts`` / ``documentPill``
- ``halatuju-web/src/lib/offerFacts.ts``        the offer letter
- ``halatuju-web/src/lib/higherResultsFacts.ts`` the higher results, and a higher result on the SPM slot
- ``halatuju-web/src/app/admin/scholarship/[id]/view/DocumentsDrawer.tsx``
  ``factClass`` (fact colour), ``yearChip`` / ``yearClass`` (the year chip)

Where a web rule looks odd it is copied as it is (the standard doc lists the odd ones), never
"fixed" here: Sprint 0 must change nothing a person sees.

A chip is a dict:
  key             the fact's i18n key suffix (``admin.scholarship.docsDrawer.fact.<key>``), or for a
                  year chip ``examYear`` / ``stpmExamYear`` / ``intakeYear``
  status          today's word: verified / partial / not / unknown
  state           green / amber / red / grey (today's web colour)
  student_action  'none' for every chip in Sprint 0 (allowed: none|reupload|fix_entry|add_doc|we_check)
  reason          the engine word the chip was coloured from
  kind            fact | year
  value           year chips only: the year read
"""

STATES = {'verified': 'green', 'partial': 'amber', 'not': 'red', 'unknown': 'grey'}
STUDENT_ACTIONS = ('none', 'reupload', 'fix_entry', 'add_doc', 'we_check')
PILLS = ('verified', 'check', 'unread')

_VERIFIED = frozenset({'match', 'found', 'ok', 'current'})
_PARTIAL = frozenset({'partial', 'uncertain', 'pending', 'stale', 'unconfirmed', 'check',
                      'check_near', 'check_name', 'check_one', 'check_both'})
_NOT = frozenset({'mismatch', 'unreadable', 'not_found', 'rejected'})
_PATRONYMIC_MEMBER = frozenset({'father', 'brother', 'sister'})


# ── small helpers (JS semantics: `!c`, `a ?? b`, `(s || '').trim()`) ────────────────────────
# Where the web would THROW (``.trim()`` / ``.startsWith()`` on a non-string, ``.some()`` on a
# non-list, a check object that is a truthy non-object), these helpers pick a quiet answer instead
# and never raise; those cases are pinned in ``test_doc_chips.py`` alone, not the shared fixture.

def _get(obj, key):
    return obj.get(key) if isinstance(obj, dict) else None


def _truthy(v):
    """JS truthiness: null, false, 0 and '' are falsy, but an EMPTY list or dict is truthy."""
    return True if isinstance(v, (list, dict)) else bool(v)


def _check_obj(doc, key):
    """A check object, or None. The web tests ``!c``, so an empty ``{}`` is still a check (its
    fields all read as missing); anything that is not a dict counts as no check."""
    c = _get(doc, key)
    return c if isinstance(c, dict) else None


def _coalesce(a, b):
    """JS ``a ?? b``: b only when a is null/undefined (an empty string still wins)."""
    return a if a is not None else b


def _trim(v):
    """JS ``(v || '').trim()``: only a string is trimmed; any other value reads as blank."""
    return v.strip() if isinstance(v, str) else ''


def _word(v):
    """A status word for a table lookup: a non-string never matches (JS ``===`` / ``switch``)."""
    return v if isinstance(v, str) else None


def _chip(key, status, reason, kind='fact', value=None):
    chip = {'key': key, 'status': status, 'state': STATES[status], 'student_action': 'none',
            'reason': '' if reason is None else str(reason), 'kind': kind}
    if kind == 'year':
        chip['value'] = value
    return chip


# ── the tone tables (cockpitDocFacts.ts) ────────────────────────────────────────────────────

def fact_status(s):
    """``factStatus``: the assorted check words onto one tone; anything unlisted is grey."""
    s = _word(s)
    if s in _VERIFIED:
        return 'verified'
    if s in _PARTIAL:
        return 'partial'
    if s in _NOT:
        return 'not'
    return 'unknown'


def _str_currency_status(s):
    """``strCurrencyFactStatus``: the STR Current chip (the cycle date only)."""
    if s == 'current':
        return 'verified'
    if s in ('stale', 'future'):
        return 'partial'
    return 'unknown'


def _str_status_status(s):
    """``strStatusFactStatus``: the STR approval Status chip. NB 'unreadable' is AMBER here but GREY
    on the Current chip above (today's code; the standard doc lists it)."""
    if s in ('current', 'unconfirmed'):
        return 'verified'
    if s in ('rejected', 'wrong_type', 'not_approved'):
        return 'not'
    if s == 'unreadable':
        return 'partial'
    return 'unknown'


def _utility_currency_chip(s, reason):
    if s == 'current':
        return _chip('current', 'verified', reason)
    if s == 'ageing':
        return _chip('ageing', 'partial', reason)
    if s == 'stale':
        return _chip('stale', 'not', reason)
    return _chip('current', 'unknown', reason)


def _address_status(s):
    if s == 'found':
        return 'verified'
    if s == 'mismatch':
        return 'not'
    if s in ('unconfirmed', 'unreadable', 'not_found'):
        return 'partial'
    return 'unknown'


def _reasonable_status(s):
    if s == 'reasonable':
        return 'verified'
    if s == 'high':
        return 'partial'
    return 'unknown'


def _genuineness_chip(doc):
    """``genuinenessFact``: a not-genuine verdict as its own chip; None when genuine / no signal."""
    s = _get(_get(doc, 'authenticity'), 'status')
    if not _truthy(s) or s in ('genuine', 'likely_genuine'):
        return None
    if s == 'final_owed':
        return _chip('finalOwed', 'unknown', s)
    if isinstance(s, str) and s.startswith('not_'):   # a non-string word: the web throws; amber here
        return _chip('wrongType', 'not', s)
    return _chip('genuine', 'partial', s)


def _capped(cap, status, reason, gf):
    """A wrong-type genuineness chip (red) caps a content chip red; its reason is then the cap."""
    return ('not', gf['reason']) if cap else (status, reason)


def _fc(key, cap, gf, status, reason):
    st, why = _capped(cap, status, reason, gf)
    return _chip(key, st, why)


# ── per document type (documentFacts) ───────────────────────────────────────────────────────

def _ic_chips(doc, gf, cap):
    nm, icn = _get(doc, 'vision_name_verdict'), _get(doc, 'vision_nric_verdict')
    chips = [_fc('name', cap, gf, fact_status(nm), nm), _fc('ic_no', cap, gf, fact_status(icn), icn)]
    return chips + ([gf] if gf else [])


def _parent_ic(doc, gf, cap):
    c = _check_obj(doc, 'income_ic_check')
    if c is None:
        return []
    readable = _truthy(_get(c, 'readable'))
    read = 'verified' if readable else 'not'
    why = 'readable' if readable else 'not_readable'
    chips = [_fc('name', cap, gf, read, why), _fc('ic_no', cap, gf, read, why)]
    if gf:
        chips.append(gf)
    elif _truthy(_coalesce(_get(c, 'display_wrong_card'), _get(c, 'wrong_card'))):
        chips.append(_chip('wrong_card', 'partial', 'wrong_card'))
    elif _word(_get(c, 'member')) in _PATRONYMIC_MEMBER:
        ns = _get(c, 'name_status')
        chips.append(_chip('relationship', fact_status(ns), ns))
    return chips


def _higher_results(c, gf):
    """``higherResultsFacts``: no genuineness cap here (today's code); the Genuine chip is appended."""
    if c is None:
        return []
    kind = _get(c, 'kind_status')
    chips = [
        _chip('name', fact_status(_get(c, 'name')), _get(c, 'name')),
        _chip('type', 'verified' if kind == 'match' else ('not' if _truthy(kind) else 'unknown'), kind),
        _chip('cgpa', fact_status(_get(c, 'cgpa_status')), _get(c, 'cgpa_status')),
    ]
    grades = _get(c, 'grades_status')
    if _truthy(grades):
        chips.append(_chip('results', fact_status(grades), grades))
    if gf:
        chips.append(gf)
    return chips


def _results_slip(doc, gf, cap):
    c = _check_obj(doc, 'academic_check')
    if c is None:
        return []
    if _truthy(_get(c, 'higher_kind')):          # S4 (#43): a higher result on the SPM slot
        nm = _get(c, 'name')
        chips = [_fc('name', cap, gf, fact_status(nm), nm), _chip('type', 'not', 'higher_kind')]
    else:
        chips = [_fc(k, cap, gf, fact_status(_get(c, k)), _get(c, k))
                 for k in ('name', 'subjects', 'results')]
    return chips + ([gf] if gf else [])


def _offer_letter(doc):
    """``offerFacts``: the owner's offer chip table. No Genuine chip; 'Official' carries it."""
    c = _check_obj(doc, 'pathway_check')
    if c is None:
        return []
    auth = _get(_get(doc, 'authenticity'), 'status')
    fake = isinstance(auth, str) and auth.startswith('not_')

    def identity(s):
        return 'partial' if s == 'unreadable' else fact_status(s)

    name, ic = _get(c, 'name'), _get(c, 'ic')
    chips = [_chip('name', identity(name), name), _chip('ic_no', identity(ic), ic)]
    pathway = _get(c, 'pathway')
    if _truthy(pathway):
        green = not fake and (pathway == 'match' or _truthy(_get(c, 'pathway_set_by_offer')))
        chips.append(_chip('pathway', 'verified' if green else 'partial', pathway))
    if _truthy(auth):
        chips.append(_chip('official', 'verified' if auth == 'genuine' else ('not' if fake else 'partial'), auth))
    if not (name == 'pending' and ic == 'pending'):
        dated = bool(_trim(_get(c, 'reporting_date')))
        chips.append(_chip('reportingDate', 'verified' if dated else 'partial', 'read' if dated else 'not_printed'))
    if _truthy(_get(c, 'switched_from')):
        chips.append(_chip('switched', 'partial', 'switched_from'))
    return chips


def _str(doc, gf, cap):
    c = _check_obj(doc, 'str_check')
    if c is None:
        return [gf] if gf else []
    ns = _coalesce(_get(c, 'display_name_status'), _get(c, 'name_status'))
    nr = _coalesce(_get(c, 'display_nric_status'), _get(c, 'nric_status'))
    cur = _get(c, 'current_status')
    chips = [
        _fc('recipient', cap, gf, fact_status(ns), ns),
        _fc('ic_no', cap, gf, fact_status(nr), nr),
        _fc('status', cap, gf, _str_status_status(cur), cur),
        _fc('current', cap, gf, _str_currency_status(cur), cur),
    ]
    return chips + ([gf] if gf else [])


def _income_proof(doc, gf, cap):
    dt = _get(doc, 'doc_type')
    c = _check_obj(doc, 'income_proof_check')
    if c is None:
        return [gf] if gf else []
    points = _get(c, 'points')
    points = points if isinstance(points, list) else []

    def has(k):
        return any(_get(p, 'key') == k and _trim(_get(p, 'value')) for p in points)

    ns = _coalesce(_get(c, 'display_name_status'), _get(c, 'name_status'))
    nr = _coalesce(_get(c, 'display_nric_status'), _get(c, 'nric_status'))
    chips = [_fc('name', cap, gf, fact_status(ns), ns)]
    verdict = _get(_get(doc, 'vision_fields'), 'student_verdict') or ''
    if _trim(_get(c, 'nric')):
        differs = not cap and nr == 'mismatch'
        chips.append(_fc('ic_no_mismatch' if differs else 'ic_no', cap, gf, fact_status(nr), nr))
    elif not cap and verdict in ('unreadable', 'wrong_doc'):
        chips.append(_chip('ic_no_unreadable', 'not', verdict))
    # `figure_refused` is served on the ADMIN payload only (sgd_conversion.py), so on the student
    # payload the Amount / Contribution chip always reads the points (see the standard doc).
    refused = _get(doc, 'figure_refused')

    def read(key, ok):
        return _chip(key, 'verified' if ok else 'unknown', 'read' if ok else 'not_read')

    if dt == 'salary_slip':
        chips.append(_chip('amount_unusable', 'partial', 'figure_refused') if refused
                     else read('amount', has('amount') or has('gross_income') or has('net_income')))
        chips.append(read('period', has('period')))
    else:
        chips.append(_chip('contribution_unusable', 'partial', 'figure_refused') if refused
                     else read('contribution', has('avgContribution')))
        chips.append(read('balance', has('totalAccumulated')))
        chips.append(read('current', has('statementDate')))
    return chips + ([gf] if gf else [])


def _birth_certificate(doc, gf, cap):
    c = _check_obj(doc, 'bc_check')
    if c is None:
        return []
    if _truthy(_get(c, 'unreadable')):
        return [_chip('unreadable', 'partial', 'unreadable')] + ([gf] if gf else [])
    ms = _coalesce(_get(c, 'display_mother_status'), _get(c, 'mother_status'))
    chips = [
        _fc('child', cap, gf, fact_status(_get(c, 'child_status')), _get(c, 'child_status')),
        _fc('mother', cap, gf, fact_status(ms), ms),
        _fc('father', cap, gf, fact_status(_get(c, 'father_status')), _get(c, 'father_status')),
    ]
    return chips + ([gf] if gf else [])


def _guardianship(doc):
    c = _check_obj(doc, 'guardianship_check')
    if c is None:
        return []
    if _truthy(_get(c, 'unreadable')):
        return [_chip('unreadable', 'partial', 'unreadable')]
    return [_chip(k, fact_status(_get(c, f'{k}_status')), _get(c, f'{k}_status')) for k in ('guardian', 'ward')]


def _semester(doc):
    """Owner 2026-07-05: Name + IC No green on match OR partial, red on anything else (incl.
    not_found); CGPA green when read, grey otherwise."""
    c = _check_obj(doc, 'semester_check')
    if c is None:
        return []

    def id_match(s):
        return 'verified' if s in ('match', 'partial') else 'not'

    cgpa = bool(_trim(_get(c, 'cgpa')))
    return [
        _chip('name', id_match(_get(c, 'name_status')), _get(c, 'name_status')),
        _chip('ic_no', id_match(_get(c, 'nric_status')), _get(c, 'nric_status')),
        _chip('cgpa', 'verified' if cgpa else 'unknown', 'read' if cgpa else 'not_read'),
    ]


def _school_leaving(doc):
    c = _check_obj(doc, 'school_leaving_check')
    if c is None:
        return []
    k = _get(c, 'kelakuan_status')
    behaviour = {'good': 'verified', 'concern': 'partial', 'bad': 'not'}.get(_word(k), 'unknown')
    return [_chip(key, fact_status(_get(c, f)), _get(c, f))
            for key, f in (('school', 'school_status'), ('name', 'name_status'), ('ic_no', 'nric_status'))
            ] + [_chip('behaviour', behaviour, k)]


def _support_doc(doc):
    c = _check_obj(doc, 'support_doc_check')
    if c is None:
        return []
    rs = _get(c, 'read_status')
    chips = [_chip('evidence', 'verified' if rs == 'read' else 'not', rs)]
    if _trim(_get(c, 'amount')):
        chips.append(_chip('amount', 'verified', 'read'))
    return chips


def _utility(doc, gf, cap):
    c = _check_obj(doc, 'utility_check')
    if c is None:
        return [gf] if gf else []
    addr, cur, rsn = _get(c, 'address_status'), _get(c, 'current_status'), _get(c, 'reasonable_status')
    chips = [
        _fc('address', cap, gf, _address_status(addr), addr),
        _chip('current', 'not', gf['reason']) if cap else _utility_currency_chip(cur, cur),
        _fc('reasonable', cap, gf, _reasonable_status(rsn), rsn),
    ]
    if not cap and _get(c, 'outstanding_status') == 'arrears':
        chips.append(_chip('outstanding', 'verified', 'arrears'))
    return chips + ([gf] if gf else [])


def fact_chips(doc):
    """``documentFacts``: the fact chips one document provides ([] = its check has not run)."""
    dt = _get(doc, 'doc_type')
    gf = _genuineness_chip(doc)
    cap = gf is not None and gf['status'] == 'not'
    if dt == 'ic':
        return _ic_chips(doc, gf, cap)
    if dt == 'parent_ic':
        return _parent_ic(doc, gf, cap)
    if dt == 'results_slip':
        return _results_slip(doc, gf, cap)
    if dt == 'higher_results':
        return _higher_results(_check_obj(doc, 'higher_check'), gf)
    if dt == 'offer_letter':
        return _offer_letter(doc)
    if dt == 'str':
        return _str(doc, gf, cap)
    if dt in ('salary_slip', 'epf'):
        return _income_proof(doc, gf, cap)
    if dt == 'birth_certificate':
        return _birth_certificate(doc, gf, cap)
    if dt == 'guardianship_letter':
        return _guardianship(doc)
    if dt == 'semester_result':
        return _semester(doc)
    if dt == 'school_leaving_cert':
        return _school_leaving(doc)
    if dt == 'income_support_doc':
        return _support_doc(doc)
    if dt in ('water_bill', 'electricity_bill'):
        return _utility(doc, gf, cap)
    return [gf] if gf else []


# ── the year chip (DocumentsDrawer.tsx yearChip / yearClass) ────────────────────────────────

_YEAR_SOURCES = (
    ('results_slip', 'academic_check', 'exam_year', 'examYear'),
    ('higher_results', 'higher_check', 'exam_year', 'stpmExamYear'),
    ('offer_letter', 'pathway_check', 'intake_year', 'intakeYear'),
)
_YEAR_STATUS = {'current': 'verified', 'off': 'partial'}


def year_chip(doc):
    """The year beside the facts: green current, amber off, grey anything else. Never in the pill."""
    dt = _get(doc, 'doc_type')
    for doc_type, check, field, key in _YEAR_SOURCES:
        if dt != doc_type:
            continue
        c = _get(doc, check)
        year = _get(c, field)
        if not _truthy(year):
            return None
        word = _get(c, f'{field}_status')
        word = word if _truthy(word) else ''
        return _chip(key, _YEAR_STATUS.get(_word(word), 'unknown'), word, kind='year', value=str(year))
    return None


# ── the public face ─────────────────────────────────────────────────────────────────────────

def chips_for(payload):
    """Every chip of one serialized document: its fact chips, then its year chip (if any)."""
    chips = fact_chips(payload)
    yc = year_chip(payload)
    return chips + [yc] if yc else chips


def pill_for(chips):
    """``documentPill``: ignore year chips and grey chips; none left → 'unread'; all green →
    'verified'; else 'check'."""
    counted = [c for c in chips if c['kind'] != 'year' and c['state'] != 'grey']
    if not counted:
        return 'unread'
    return 'verified' if all(c['state'] == 'green' for c in counted) else 'check'
