"""The document chip standard, Sprint 1: the STUDENT's chips, one server-side home.

DISPLAY ONLY, like ``doc_chips`` (the officer's chips): nothing here decides a verdict, a band, an
award or eligibility, no engine may import it (``tests/test_doc_chips_import_fence.py``), and it reads
the student SERIALIZER OUTPUT only, so it runs no DB query.

Sprint 1 reproduces TODAY's student states and badge words (a plain value, a grey chip with no words, is
not drawn by the student screen any more): each rule is a line-for-line port of the badges
the student checklists draw under an upload card, checked against the web by the shared parity
fixture (``tests/fixtures/doc_chip_parity.json`` ``student_cases``):

- ``halatuju-web/src/components/ScholarshipDocuments/checklists.tsx``  ICChecklist, IncomeIcChecklist,
  IncomeProofChecklist, UtilityChecklist, StrChecklist, BcChecklist, GuardianshipChecklist,
  ResultsSlipChecklist, GenuinenessNote
- ``.../checklistsPathway.tsx``  OfferLetterChecklist, SupportingDocChip
- ``.../cards.tsx``  which checklist a document gets (the dispatch in ``chips_for``)

The student rules are NOT the officer rules (``doc_chips``); where they differ that is today's code,
copied as it is and listed in ``docs/document-chip-standard.md``. Not ported (drawn by lazy components
outside the two files): a higher result on the SPM slot and the higher results' own checklist; for
those only the genuineness note is served.

A chip is the officer dict plus ``label``:
  key             the row it sits on (the last part of today's row-label i18n key), or ``assist`` /
                  ``match`` (the supporting-document chip) or ``genuineness`` (the amber note)
  status          verified / partial / not / unknown (the officer words, from the colour)
  state           green / amber / red / grey (today's student colour)
  student_action  'none' for every chip in Sprint 1
  reason          the engine word the badge was drawn from
  kind            fact (a status badge) | plain (a grey "from the document" tag) | note (the amber
                  genuineness note)
  label           today's badge word, as its full i18n key (the student badge word is not
                  derivable from the colour, so it travels with the chip)
"""
from .doc_chips import STATES, _check_obj, _coalesce, _get, _truthy, _word

# ICCheckKind -> (status, state). 'unreadable' and 'none' are both grey (two greys on the web).
_TONE = {'match': 'verified', 'partial': 'partial', 'mismatch': 'not', 'unreadable': 'unknown',
         'none': 'unknown'}
# SupportingDocChip palette tones -> status.
_SUPPORT_TONE = {'good': 'verified', 'warn': 'partial', 'info': 'unknown', 'name-missing': 'partial',
                 'address-missing': 'partial', 'unreadable': 'unknown'}
_D = 'scholarship.docs.'
_NOT_FINAL = frozenset({'matric_result_slip', 'poly_result_slip', 'poly_portal_page',
                        'matric_transcript_not_final', 'poly_transcript_not_final'})
_NOT_RESULTS = frozenset({'matric_offer_letter'})
_SLIP_NO_BADGE = frozenset({'not_spm', 'not_compared'})


def _js(v):
    """JS ``String(v)`` inside a template literal, for the few i18n keys built from a value."""
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    return str(v)


def _tpl(obj, key):
    """``${obj.key}``: a missing key reads 'undefined', a null 'null'."""
    if not isinstance(obj, dict) or key not in obj:
        return 'undefined'
    return _js(obj[key])


def _chip(key, status, reason, label, kind='fact'):
    return {'key': key, 'status': status, 'state': STATES[status], 'student_action': 'none',
            'reason': '' if reason is None else str(reason), 'kind': kind, 'label': label}


def _badge(key, tone, reason, label):
    return _chip(key, _TONE[tone], reason, label)


def _plain(key, label, reason=''):
    return _chip(key, 'unknown', reason, label, kind='plain')


def _note(label, reason):
    return _chip('genuineness', 'partial', reason, label, kind='note')


# ── the shared badge words ──────────────────────────────────────────────────────────────────

def _display_pill(status):
    """``displayPill``: the served link words beyond match / mismatch / no_ref, or None."""
    if status == 'not_read':
        return 'none', _D + 'incomeProofCheck.notRead'
    if status == 'check_name':
        return 'partial', _D + 'relCheck.checkName'
    if status == 'check_near':
        return 'partial', _D + 'relCheck.checkNumberOneDigit'
    return None


def _vs_ic(key, status):
    """``vsIc`` (IncomeProofChecklist and StrChecklist: the same rule twice)."""
    shown = _display_pill(status)
    if shown:
        tone, label = shown
    elif status == 'match':
        tone, label = 'match', _D + 'incomeProofCheck.matchesIc'
    elif status == 'mismatch':
        tone, label = 'mismatch', _D + 'incomeProofCheck.mismatchIc'
    else:
        tone, label = 'none', _D + 'incomeProofCheck.addIc'
    return _badge(key, tone, status, label)


_REL_LABEL = {'match': 'relCheck.confirmed', 'mismatch': 'relCheck.mismatch',
              'check_near': 'relCheck.checkNumberOneDigit', 'check': 'relCheck.checkNumber',
              'check_name': 'relCheck.checkName', 'check_both': 'relCheck.checkBoth',
              'not_read': 'incomeProofCheck.notRead'}


def _rel(key, status):
    """``relPill`` (birth certificate, guardianship letter)."""
    if status in ('match', 'mismatch'):
        tone = status
    elif status in ('check', 'check_near', 'check_name', 'check_both'):
        tone = 'partial'
    else:
        tone = 'none'
    return _badge(key, tone, status, _D + _REL_LABEL.get(_word(status), 'relCheck.reviewing'))


def genuineness_note_key(doc_seen, doc_type='', status=''):
    """``genuinenessNoteKey``."""
    if doc_seen == 'sample_document':
        return _D + 'genuineness.sampleDoc'
    if doc_type == 'offer_letter':
        fake = isinstance(status, str) and status.startswith('not_')
        return _D + ('genuineness.offerNotOffer' if fake else 'genuineness.offerSuspect')
    if _truthy(doc_seen) and _word(doc_seen) in _NOT_FINAL:
        return _D + 'genuineness.askFinal'
    if _truthy(doc_seen) and _word(doc_seen) in _NOT_RESULTS:
        return _D + 'genuineness.notResults'
    return _D + 'genuineness.note'


def _genuineness_note(doc):
    """``GenuinenessNote``: the amber note under every listed document that is not genuine."""
    auth = _get(doc, 'authenticity')
    s = _get(auth, 'status')
    if not _truthy(s) or s == 'genuine':
        return []
    return [_note(genuineness_note_key(_get(auth, 'doc_seen'), _get(doc, 'doc_type'), s), s)]


# ── per checklist ───────────────────────────────────────────────────────────────────────────

def _ic_kind(v):
    return v if v in ('match', 'partial', 'mismatch', 'unreadable') else 'none'


def _ic_checklist(doc):
    """``ICChecklist`` (the identity card that has been read). Its own amber note, not the shared one:
    any status but 'genuine' shows it (so 'likely_genuine' does too, unlike the officer drawer)."""
    if not _truthy(_get(doc, 'vision_run_at')):
        return []
    nr, nm = _get(doc, 'vision_nric_verdict'), _get(doc, 'vision_name_verdict')
    chips = [_badge('icNo', _ic_kind(nr), nr, _D + 'icCheck.' + _ic_kind(nr)),
             _badge('name', _ic_kind(nm), nm, _D + 'icCheck.' + _ic_kind(nm))]
    if _truthy(_get(doc, 'vision_address')):
        chips.append(_plain('address', _D + 'icCheck.fromIc'))
    auth = _get(doc, 'authenticity')
    s = _get(auth, 'status')
    if _truthy(s) and s != 'genuine':
        sample = _get(auth, 'doc_seen') == 'sample_document'
        chips.append(_note(_D + ('genuineness.sampleDoc' if sample else 'icCheck.notGenuine'), s))
    return chips


def _income_ic_checklist(doc, c):
    """``IncomeIcChecklist``: the earner's card against the household's income proof."""
    if not _truthy(_get(doc, 'vision_run_at')):
        return []
    proof = _truthy(_get(c, 'proof_kind'))

    def tag(key, status):
        tone = status if status in ('match', 'mismatch') else 'none'
        if status == 'mismatch' and _truthy(_get(c, 'display_wrong_card')):
            label = 'incomeIcCheck.wrongCard'
        elif status == 'match' and proof:
            label = 'incomeIcCheck.matchesProof'
        elif status == 'mismatch' and proof:
            label = 'incomeIcCheck.proofMismatch'
        else:
            label = 'icCheck.fromTheirIc'
        return _badge(key, tone, status, _D + label)

    chips = []
    if _truthy(_get(c, 'nric')):
        chips.append(tag('icNo', _coalesce(_get(c, 'display_proof_nric_status'), _get(c, 'proof_nric_status'))))
    chips.append(tag('name', _coalesce(_get(c, 'display_proof_name_status'), _get(c, 'proof_name_status'))))
    if _truthy(_get(c, 'address')):
        chips.append(_plain('address', _D + 'icCheck.fromTheirIc'))
    return chips


def _income_proof_checklist(c):
    """``IncomeProofChecklist``: Name and IC No against that member's own IC; each point plain."""
    chips = [_vs_ic('name', _coalesce(_get(c, 'display_name_status'), _get(c, 'name_status')))]
    if _truthy(_get(c, 'nric')):
        chips.append(_vs_ic('icNo', _coalesce(_get(c, 'display_nric_status'), _get(c, 'nric_status'))))
    points = _get(c, 'points')
    for p in points if isinstance(points, list) else []:     # the web: a non-list throws
        chips.append(_plain(_tpl(p, 'key'), _D + 'incomeProofCheck.fromDoc'))
    return chips


def _utility_checklist(c):
    """``UtilityChecklist``. NB 'not_found' is RED here but amber in the officer drawer."""
    a = _get(c, 'address_status')
    if a == 'found':
        chips = [_badge('address', 'match', a, _D + 'utilityCheck.addressOk')]
    elif a == 'not_found':
        chips = [_badge('address', 'mismatch', a, _D + 'utilityCheck.addressMismatch')]
    else:
        chips = [_plain('address', _D + 'incomeProofCheck.fromDoc', a)]
    for key, field in (('monthlyBill', 'monthly_bill'), ('unpaidBalance', 'unpaid_balance')):
        if _truthy(_get(c, field)):
            chips.append(_plain(key, _D + 'incomeProofCheck.fromDoc'))
    return chips


def _str_checklist(c):
    """``StrChecklist``: Recipient · IC No · Status · Year. A page of another year (stale / future)
    draws NO status badge (TD-403)."""
    chips = [_vs_ic('recipient', _coalesce(_get(c, 'display_name_status'), _get(c, 'name_status')))]
    if _truthy(_get(c, 'nric')):
        chips.append(_vs_ic('icNo', _coalesce(_get(c, 'display_nric_status'), _get(c, 'nric_status'))))
    cur = _get(c, 'current_status')
    s = _D + 'strCheck.'
    if cur in ('current', 'unconfirmed'):
        chips.append(_badge('status', 'match', cur, s + 'approved'))
    elif cur == 'unknown':
        chips.append(_badge('status', 'none', cur, s + 'unknown'))
    elif cur not in ('future', 'stale'):
        chips.append(_badge('status', 'mismatch', cur, s + _tpl(c, 'current_status')))
    year = {'current': ('match', 'current'), 'unconfirmed': ('partial', 'unconfirmed'),
            'stale': ('mismatch', 'stale'), 'future': ('partial', 'future')}.get(_word(cur), ('none', 'unknown'))
    chips.append(_badge('year', year[0], cur, s + year[1]))
    return chips


def _birth_certificate_checklist(c):
    """``BcChecklist``. No 'unreadable' row of its own (the officer drawer has one)."""
    chips = [_rel('child', _get(c, 'child_status')),
             _rel('mother', _coalesce(_get(c, 'display_mother_status'), _get(c, 'mother_status')))]
    if _truthy(_get(c, 'father_name')):
        chips.append(_rel('father', _get(c, 'father_status')))
    return chips


def _guardianship_checklist(c):
    return [_rel('guardian', _get(c, 'guardian_status')), _rel('ward', _get(c, 'ward_status'))]


def _slip_kind(s):
    if s == 'match':
        return 'match'
    if s in ('partial', 'uncertain'):
        return 'partial'
    return s if s in ('mismatch', 'unreadable') else 'none'


def _results_slip_checklist(c):
    """``ResultsSlipChecklist``: Name · Subjects · Results, plus the exam as a plain tag. A status of
    not_spm / not_compared draws no badge; not_compared also drops the Subjects / Results row."""
    def badge(key, s):
        if _word(s) in _SLIP_NO_BADGE:
            return []
        return [_badge(key, _slip_kind(s), s, _D + 'slipCheck.status.' + _tpl(c, key))]

    chips = badge('name', _get(c, 'name'))
    for key in ('subjects', 'results'):
        if _get(c, key) != 'not_compared':
            chips += badge(key, _get(c, key))
    if _truthy(_get(c, 'exam_year')) or _truthy(_get(c, 'exam')):
        chips.append(_plain('exam', _D + 'slipCheck.fromSlip'))
    return chips


def _path_kind(s):
    if s == 'match':
        return 'match'
    if s in ('partial', 'uncertain'):
        return 'partial'
    return s if s in ('mismatch', 'unreadable') else 'none'


def _offer_letter_checklist(c):
    """``OfferLetterChecklist``. A pathway mismatch is AMBER on the student's Programme / Institution
    rows (the officer's Pathway chip carries it too); the declared note and the start-year line are
    text lines, not badges, so they carry no chip."""
    p = _D + 'pathwayCheck.'

    def badge(key, s):
        label = p + 'ic' if s == 'not_printed' else p + 'status.' + _tpl(c, key)
        return _badge(key, _path_kind(s), s, label)

    chips = [badge('name', _get(c, 'name')), badge('ic', _get(c, 'ic'))]
    mismatch = _get(c, 'pathway') == 'mismatch'
    for key in ('programme', 'institution'):
        if _truthy(_get(c, key)):
            chips.append(_badge(key, 'partial', 'mismatch', p + 'status.mismatch') if mismatch
                         else _plain(key, p + 'fromLetter'))
    date = _get(c, 'offer_date') if _truthy(_get(c, 'offer_date')) else _get(c, 'intake')
    for key, v in (('issuer', _get(c, 'issuer')), ('date', date), ('address', _get(c, 'address'))):
        if _truthy(v):
            chips.append(_plain(key, p + 'fromLetter'))
    return chips


def _supporting_checklist(doc):
    """``SupportingDocChip``: the one soft chip every other listed document earns."""
    av = _get(_get(doc, 'vision_fields'), 'student_verdict')
    if _truthy(av):
        tone = 'good' if av == 'ok' else ('info' if av in ('unreadable', 'review_manually') else 'warn')
        return [_chip('assist', _SUPPORT_TONE[tone], av, _D + 'assist.' + _js(av))]
    nm = _get(doc, 'vision_name_match')
    if not _truthy(nm):
        return []
    am = _get(doc, 'vision_address_match')
    if nm == 'unreadable' or am == 'unreadable':
        variant = 'unreadable'
    elif nm == 'not_found':
        variant = 'name-missing'
    elif am == 'not_found':
        variant = 'address-missing'
    else:
        variant = 'good'
    return [_chip('match', _SUPPORT_TONE[variant], nm, _D + 'match.' + variant)]


def _listed(doc):
    """The per-document branch of ``cards.tsx`` for a listed (not the read identity card) document."""
    dt = _get(doc, 'doc_type')
    if dt == 'results_slip' and _truthy(_get(_get(doc, 'academic_check'), 'higher_kind')):
        return []                                     # LazySlipHigherNote: not ported
    if dt == 'higher_results' and _truthy(_get(doc, 'higher_check')):
        return []                                     # LazyHigherDetails: not ported
    pairs = (
        (('results_slip',), 'academic_check', _results_slip_checklist),
        (('offer_letter',), 'pathway_check', _offer_letter_checklist),
        (('salary_slip', 'epf'), 'income_proof_check', _income_proof_checklist),
        (('str',), 'str_check', _str_checklist),
        (('water_bill', 'electricity_bill'), 'utility_check', _utility_checklist),
        (('birth_certificate',), 'bc_check', _birth_certificate_checklist),
        (('guardianship_letter',), 'guardianship_check', _guardianship_checklist),
    )
    if dt == 'parent_ic' and _truthy(_get(doc, 'income_ic_check')):
        c = _check_obj(doc, 'income_ic_check')
        return _income_ic_checklist(doc, c) if c is not None else []
    for types, field, fn in pairs:
        if dt in types and _truthy(_get(doc, field)):
            c = _check_obj(doc, field)
            return fn(c) if c is not None else []
    return _supporting_checklist(doc)


# ── the public face ─────────────────────────────────────────────────────────────────────────

def chips_for(payload):
    """Every badge the student sees under one document today, in screen order."""
    if not isinstance(payload, dict):
        return []
    if _get(payload, 'doc_type') == 'ic' and _truthy(_get(payload, 'vision_run_at')):
        return _ic_checklist(payload)
    return _listed(payload) + _genuineness_note(payload)


def pill_for(chips):
    """The student has no pill today, so nothing draws this. It is the officer's rule on the student's
    status badges (plain tags and notes left out): none left -> 'unread'; any red -> 'problem'; all
    green -> 'verified'; else 'check'. Unlike ``doc_chips.pill_for`` (which skips only year chips),
    this counts fact chips only."""
    counted = [c for c in chips if c['kind'] == 'fact' and c['state'] != 'grey']
    if not counted:
        return 'unread'
    if any(c['state'] == 'red' for c in counted):
        return 'problem'
    return 'verified' if all(c['state'] == 'green' for c in counted) else 'check'
