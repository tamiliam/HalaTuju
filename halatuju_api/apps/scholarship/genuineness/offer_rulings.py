"""The owner's offer-letter genuineness rulings, applied ON TOP OF the pre-S6 call (offer exact-read S6,
MODEL_VERSION 1.25.0).

A genuineness status is a BURSARY decision, not a document type (owner, 2026-11-01, `docs/decisions.md`):
`not_offer_letter` is a FAIL, `suspect` means "not sure, a person decides", `genuine` is a public offer we
can support.

THE DESIGN (owner, 2026-11-03, option 1 — after seven review rounds swung the middle logic both ways): S6 may
change a genuineness call ONLY ON CLEAR PROOF. Every other page keeps the BASELINE — the call the pre-S6
engine gives (`results_doc.baseline_genuineness`, the 1.22.0 path, unchanged). Unclear = today's call: no
guessing, and no new cap to suspect either (owner rule: predict, don't hedge).

  1. BLOCK (→ `not_offer_letter`, tag `private_offer`) only on POSITIVE PRIVATE PROOF on the letterhead block
     (`offer_reading.private_proof`: "Sdn Bhd" / "Berhad", a named private body — GMI, UniKL, KPTM / KUPTM /
     UPTM, UM SATU, UMS PPPL — or explicit tie-up wording). The letterhead block ends at the title, the
     salutation or the addressee, so a Yayasan / Persatuan addressee, a supplier, a bank or a SIRIM footer is
     never letterhead. No other route newly blocks.
  2. LIFT (→ `genuine`) only when ALL hold: a closed-list public institution's exact name on the letterhead
     block (a public TVET INSTITUTE — `_INSTITUTES`; a polytechnic / UMS / a Form-6 college for a confirmation
     of studies); a letterhead naming no other organisation; the full shape of the letter (`_letter_structure`);
     and NO private marker anywhere on the page (`_private_marker`). Tags `tvet_offer` / `confirmation`, with
     the issuer as `doc_seen` (`tvet_*`, `confirmation_*`). A fingerprinted ministry family's own letter the
     pre-S6 veto blocked ONLY for an incidental company line (a supplier, a bank, the addressee) and that
     scores genuine is lifted too (tag `incidental_company`).
  3. Two owner rulings that SOFTEN a fail on its own proof, never block and never lift to genuine: an admission
     printout / portal page / e-Daftar slip → `suspect` (`printout`, ruling 3); a closed-list TVET page calling
     itself a SLIP on its letterhead → `suspect` (`tvet_slip`, ruling 6).
JMTI and CIAST are government (JTM) institutes (owner, 2026-11-03): on the LIFT's institute list, same rules.

Every call that differs from the baseline carries `[S6 ruling: <tag>]` (`ruling_of`), so a reviewer's
override or a later corpus answer shows which rule was wrong (`eval/offer_genuineness_check.py`). Pure.
"""
import re

from .bands import GENUINE_MIN, SUSPECT_MAX
from .offer_issuers import TVET_ISSUERS, _has_offer_words, private_college_reason, unfingerprinted_offer

# The page-reading helpers and word lists live in `offer_reading` (S6 round 5 split; not verbatim - CHANGELOG).
from .offer_reading import *    # every name re-exported (`offer_reading.__all__`): tests and callers import them here


# ── The incidental-company excuse (a lift over the pre-S6 veto) ───────────────────────────
def ministry_letter_naming_a_company(ocr_text: str, r: dict, lines=None) -> bool:
    """True when the pre-S6 private-arm veto (`results_doc._private_arm_offer`) fired ONLY on "Sdn Bhd",
    a ministry family's own issuer line is on the page, and EVERY such line is incidental (`_incidental`: a
    closed-list bank's own line, or the addressee block above the title — round 8) with no organisation noun
    on it or the line before, and not the letterhead's own name."""
    from .offer_issuers import FAMILY_ISSUER_SIG
    lines = _folded_lines(ocr_text) if lines is None else lines
    if not _veto_only_by_a_company(_page(lines)):
        return False
    scores = r.get('scores') or {}
    if not any(FAMILY_ISSUER_SIG[f] in ((scores.get(f) or {}).get('present') or []) for f in _MINISTRY_FAMILIES):
        return False
    return _company_lines_incidental(lines)


def _veto_only_by_a_company(page: str) -> bool:
    """The pre-S6 veto fired, and only its "Sdn Bhd" arm did (`page`: the folded page)."""
    from .results_doc import _PRIVATE_ARM_PHRASES
    hits = [p for p in _PRIVATE_ARM_PHRASES if p in page]
    return bool(hits) and not (set(hits) - {'SDN BHD'}) and ' SPACE ' not in page


def _company_lines_incidental(lines) -> bool:
    """Every "Sdn Bhd" / "Sendirian Berhad" line is incidental (`_incidental`), off the letterhead, with no
    organisation noun on it or the line before."""
    head = _letterhead_lines(lines)
    for i, ln in enumerate(lines):
        if any(c in ln for c in _COMPANY_SIGNS):      # round 8 (M3): every company spelling
            near = (lines[i - 1] if i else '') + ln + (lines[i + 1] if i + 1 < len(lines) else '')
            name = [w for w in ln.split(' SDN BHD ')[0].split(' SENDIRIAN BERHAD ')[0].split()
                    if w not in _LABEL_WORDS][-2:]
            phrase = f" {' '.join(name)} "  # round 6: a one-word name too ("MERCU" / "Penaja : Mercu Sdn Bhd")
            on_letterhead = bool(name) and any(phrase in h for h in head)
            if (ln in head or not _incidental(lines, i) or _ORG_RE_NO_COMPANY.search(_unstreeted(near))
                    or _NEAR_EXTRA.search(near) or on_letterhead):
                return False            # round 5 (Low 7): the company's own name on the letterhead keeps the veto
    return True


#: Words beside a company that still name an institution (Low 7), and labels that are not a company's name.
_NEAR_EXTRA = re.compile(r' (?:CAMPUS|TEKNOLOGI|TECHNOLOGY)(?= )')
_LABEL_WORDS = {'PENAJA', 'TAJAAN', 'DITAJA', 'SPONSOR', 'PEMBEKAL', 'SUPPLIER', 'PENCETAK', 'DICETAK', 'BAYARAN',
                'AKAUN', 'LADANG', 'ESTATE', 'KEPADA', 'OLEH'}


# ── LIFT ──────────────────────────────────────────────────────────────────────────────────
#: Each public TVET institute's closed-list key (`offer_issuers.TVET_ISSUERS`), English names included.
_INSTITUTE_KEY = {
    'tvet_belia_sukan': (' INSTITUT KEMAHIRAN BELIA NEGARA ', ' INSTITUT KEMAHIRAN TINGGI BELIA NEGARA ', ' IKBN ',
                         ' IKTBN ', ' NATIONAL YOUTH SKILLS INSTITUTE ', ' NATIONAL YOUTH HIGH SKILLS INSTITUTE '),
    'tvet_mara': (' INSTITUT KEMAHIRAN MARA ', ' IKM ', ' KOLEJ KEMAHIRAN TINGGI MARA ', ' KKTM ', ' KOLEJ MARA ',
                  ' KOLEJ PROFESIONAL MARA ', ' MARA SKILLS INSTITUTE ', ' MARA HIGHER SKILLS COLLEGE ',
                  ' MARA PROFESSIONAL COLLEGE '),
    'tvet_jtm': (' INSTITUT LATIHAN PERINDUSTRIAN ', ' ILP ', ' ADTEC ', ' PUSAT LATIHAN TEKNOLOGI TINGGI ',
                 ' ILJTM ', ' ADVANCED TECHNOLOGY TRAINING CENTRE ', ' INDUSTRIAL TRAINING INSTITUTE ',
                 ' JMTI ', ' JAPAN MALAYSIA TECHNICAL INSTITUTE ', ' CIAST ',      # owner 2026-11-03
                 ' PUSAT LATIHAN PENGAJAR DAN KEMAHIRAN LANJUTAN '),
}
assert set(_INSTITUTE_KEY) <= set(TVET_ISSUERS) and {n for ns in _INSTITUTE_KEY.values() for n in ns} == set(
    _INSTITUTES)


#: Round 9 (H1): an offer of money, not of a place.
_NOT_ADMISSION = (' PEMBIAYAAN ', ' PINJAMAN ', ' BIASISWA ', ' TAJAAN ', ' ELAUN ', ' BANTUAN ', ' DERMASISWA ',
                  ' PENAJAAN ', ' LOAN ', ' LOANS ', ' SPONSORSHIP ', ' SCHOLARSHIP ', ' FINANCING ', ' FUNDING ',
                  ' ALLOWANCE ', ' GRANT ', ' BURSARY ')          # round 10 (M1): one list, both lifts
_PEMBIAYA = re.compile(r' PEMBIAYA[A-Z]*(?= )')             # any spelling of the stem ("PEMBIAYAN")
#: Round 10 (M1): a loan / financing word within two lines of an RM amount.
_LOAN_WORDS = re.compile(r' (?:PINJAMAN|PEMBIAYA[A-Z]*|LOANS?|FINANCING)(?= )')
_RM_AMOUNT = re.compile(r' RM ?\d')


def _money_offer(lines) -> bool:
    """Round 10 (M1): money words in the title or the first five body lines — an offer of money, not a place."""
    at = next((i for i, ln in enumerate(lines) if any(t in ln for t in _TITLE)), None)
    if at is None:
        return False
    return any(any(w in ln for w in _NOT_ADMISSION) or _PEMBIAYA.search(ln) for ln in lines[at:at + 6])


def _loan_amount(lines) -> bool:
    """Round 10 (M1): a loan / financing word within two lines of an RM amount."""
    return any(_LOAN_WORDS.search(ln) and any(_RM_AMOUNT.search(x) for x in lines[max(0, i - 2):i + 3])
               for i, ln in enumerate(lines))


def _institute_on_letterhead(lines) -> str:
    """The closed-list key of the public TVET INSTITUTE named on the letterhead, or ''."""
    head = _page(_letterhead_lines(lines))
    for key, names in _INSTITUTE_KEY.items():
        if any(n in head for n in names):
            return key
    return ''


def _first_named_institute(lines) -> str:
    """The closed-list key of the institute the page names FIRST, when an institute is named first ('' when
    another organisation comes before it — a private academy, an unlisted institute)."""
    if _first_institution(lines, _INSTITUTES) != 'allowed':
        return ''
    for ln in lines:
        hits = [(ln.find(n), key) for key, names in _INSTITUTE_KEY.items() for n in names if n in ln]
        if hits:
            return min(hits)[1]
    return ''


#: Round 11 (M5): a representative, never the issuer — no lift of any kind.
_AGENT_WORDS = re.compile(r' (?:WAKIL|EJEN|AGEN)(?= )')


def _tvet_lift(r, lines, model_version):
    if _AGENT_WORDS.search(_page(lines)):
        return None                     # round 11 (M5): WAKIL / EJEN / AGEN
    head = _page(_letterhead_lines(lines))
    if not any(n in head for n in _TVET_NAMES):
        return None                     # no closed-list body named on the letterhead
    key = _first_named_institute(lines)
    if not key or not _has_offer_words(_page(lines)) or not _clean_letterhead(lines, _TVET_NAMES):
        return None
    if _institute_on_letterhead(lines) != key:
        return None                     # round 9 (H1): the INSTITUTE on the letterhead, not an agency alone
    if _money_offer(lines):
        return None                     # rounds 9-10: a financing / loan / scholarship offer is no admission
    if not _named_first(lines, _INSTITUTE_KEY[key], _AGENCIES[key]):
        return None                     # round 10 (M4): the institute FIRST on the letterhead
    if _SLIP in _page(_letterhead_block(lines)):
        return None                     # a slip, not a letter (`_tvet_slip`)
    if not _letter_structure(lines, _TITLE, min_lines=_OFFER_MIN_LINES, reporting=True):
        return None
    if r['probability'] < SUSPECT_MAX:  # below the suspect floor the body names the institute again
        body = lines[len(_letterhead_lines(lines)):]
        if not any(i in ln for ln in body for i in _INSTITUTE_KEY[key]):
            return None
    return _ruled_status('genuine', r, key, 'tvet_offer', f'{TVET_ISSUERS[key][0]}: a public TVET institute\'s '
                         'offer letter - a public offer (owner rulings 5 and Q2)', model_version)


#: Owner ruling 2026-11-03 (decisions.md S6 item 9): the AGENCIES whose own letterhead may carry an institute's
#: admission offer, each with its own institutes (`_INSTITUTE_KEY`). JPK (it accredits private centres) and any
#: other ministry are not on it.
_AGENCIES = {
    'tvet_mara': (' MAJLIS AMANAH RAKYAT ', ' MARA ', ' TVETMARA ',
                  ' BAHAGIAN PENDIDIKAN DAN LATIHAN TEKNIKAL VOKASIONAL MARA ',
                  ' INSTITUSI PENDIDIKAN MARA ', ' IPMA '),                    # the agency's umbrella names
    'tvet_belia_sukan': (' KEMENTERIAN BELIA DAN SUKAN ', ' KBS ', ' MINISTRY OF YOUTH AND SPORTS ',
                         ' INSTITUSI LATIHAN KEMAHIRAN BELIA DAN SUKAN ', ' ILKBS '),
    'tvet_jtm': (' JABATAN TENAGA MANUSIA ', ' JTM ', ' KEMENTERIAN SUMBER MANUSIA ', ' KSM ',
                 ' DEPARTMENT OF MANPOWER ', ' MINISTRY OF HUMAN RESOURCES ',
                 ' INSTITUSI LATIHAN JABATAN TENAGA MANUSIA ', ' ILJTM '),
}
#: Condition 4's words that never NAME anything (`offer_agency`).
_FUNCTION_WORDS = frozenset({
    'BERHAK', 'INI', 'ITU', 'TERSEBUT', 'BERKENAAN', 'YANG', 'DAN', 'DI', 'KE', 'UNTUK', 'DARI', 'DARIPADA',
    'KEPADA', 'PADA', 'BAGI', 'OLEH', 'ATAU', 'AKAN', 'TELAH', 'IALAH', 'ADALAH', 'ANDA', 'KAMI', 'TUAN', 'PUAN',
    'SERTA', 'DENGAN', 'DALAM', 'SEBAGAI', 'SETIAP', 'SEMUA', 'BERIKUT', 'MASING', 'SEMASA', 'SELEPAS', 'SEBELUM',
    'SEPERTI', 'SEPERTIMANA', 'SILA', 'MOHON', 'HARAP',         # lead's ruling 2026-11-04 (4); round 11
    'THE', 'OF', 'AND', 'TO', 'AT', 'IN', 'FOR', 'A', 'AN', 'THIS', 'THAT', 'IS', 'ARE', 'WILL', 'MAY', 'BY', 'ON',
    'WITH', 'AS', 'YOUR', 'OUR'})
_WORD = re.compile(r'[^\W_]+')                # letters with any digits ('K0LEJ')


def _raw_lines(ocr_text):
    """The raw OCR lines aligned with `_folded_lines` (the same non-empty filter), case kept."""
    from .results_doc import _norm_fold_upper_alnum
    return [raw for raw in normalise_s6(ocr_text).splitlines() if _norm_fold_upper_alnum(raw)]
#: Another public body on the line (a ministry / department / council / board not on `_AGENCIES`).
_OTHER_BODY = re.compile(r' (?:KEMENTERIAN|MINISTRY|JABATAN|DEPARTMENT|MAJLIS|LEMBAGA|PERBADANAN|BAHAGIAN) [A-Z]')
#: Item 9 (3): money words in the title or the first body lines — no admission.


def _agency_on_head(lines) -> str:
    """Item 9 (1): the ONE agency the letterhead names, when it names that agency and no other organisation or
    public body ('' otherwise)."""
    keys = set()
    for ln in _letterhead_lines(lines):
        ln = _unstreeted(_decontact(ln))
        for key, names in _AGENCIES.items():
            for n in names:
                if n in ln:
                    keys.add(key)
                    ln = ln.replace(n, ' ')
        if _ORG_RE.search(ln) or _OTHER_BODY.search(ln) or any(n in ln for n in _TVET_NAMES):
            return ''                   # another organisation, JPK, or an unlisted ministry on the letterhead
    return keys.pop() if len(keys) == 1 else ''


def _agency_lift(ocr_text, r, lines, model_version):
    """Item 9: an agency's letterhead + its OWN institute named in the body + an admission title + the full shape
    (no private marker: `_lift`). Tag `tvet_offer`; the reason says `agency_letterhead`."""
    from .offer_agency import _agency_first, closed_world_blocker      # condition 4, closed world (2026-11-04)
    key = _agency_on_head(lines)
    if not key or not _agency_first(lines, key):
        return None                     # (1) + (f): the agency first on the letterhead, never an agent
    head_n = len(_letterhead_lines(lines))
    body = lines[head_n:]
    named = {k for ln in body for k, names in _INSTITUTE_KEY.items() if any(n in ln for n in names)}
    if named != {key}:
        return None                     # (2) no institute, or another agency's (a parent mismatch)
    at = next((i for i, ln in enumerate(lines) if any(t in ln for t in _TITLE)), None)
    if at is None or _money_offer(lines):
        return None                     # (3) no admission title, or money in the title / first five body lines
    if not (_has_offer_words(_page(lines)) and _letter_structure(lines, _TITLE, min_lines=_OFFER_MIN_LINES,
                                                                  reporting=True)):
        return None                     # (4) the full offer shape
    if _SLIP in _page(_letterhead_block(lines)):
        return None
    if closed_world_blocker(lines, _raw_lines(ocr_text), head_n, key):
        return None                     # (4) closed world: another organisation word in the body
    return _ruled_status('genuine', r, key, 'tvet_offer', f'agency_letterhead: {TVET_ISSUERS[key][0]}: the agency\'s '
                         'own letterhead, its public TVET institute named in the body - a public offer (owner '
                         'ruling 2026-11-03, S6 item 9)', model_version)


def confirmation_kind(ocr_text: str, probability: float = 1.0, lines=None) -> str:
    """The `confirmation_*` code of a confirmation-of-studies letter from a no-private-wing public institution
    named on its letterhead block, or '' (no title at the top, below the score floor, a private marker, or a
    letterhead naming another organisation)."""
    lines = _folded_lines(ocr_text) if lines is None else lines
    if not _confirm_titled(lines, probability) or _private_marker(lines):
        return ''
    scan = _without_poly_department(lines)                 # the department's name names no polytechnic
    head, page = _page(_letterhead_lines(scan)) + _title_segment(scan), _page(lines)
    for seen, names, marks in _NO_PRIVATE_WING:
        if seen == 'confirmation_form6' and not (any(m in page for m in _FORM6_MARKS)
                                                 or ' KOLEJ TINGKATAN ENAM ' in head):
            continue                    # round 9 (H2): an SMK confirmation of Forms 1-5 is no Form 6
        if (any(n in head for n in names) and _first_institution(scan, names) == 'allowed'
                and any(m in page for m in marks) and _clean_letterhead(scan, names)
                and _named_first(scan, names, divisions=True, then=[_title_segment(scan)])):     # round 10 (M4)
            return seen
    return ''


def _title_segment(lines) -> str:
    """The confirmation title's own words up to the candidate's label ("SURAT PENGESAHAN PELAJAR UNIVERSITI
    MALAYSIA SABAH NAMA ..." names its issuer in the title)."""
    for ln in lines:
        at = [ln.find(t) for t in _CONFIRM_TITLES if t in ln]
        if at:
            seg = ln[min(at):]
            cut = [seg.find(lb) for lb in _PERSON_LABELS if lb in seg] + [m.start() for m in _IC.finditer(seg)]
            return ' ' + ' '.join((seg[:min(cut)] if cut else seg).split()[:12]) + ' '
    return ''


#: Round 10 (M4): the lines a closed-list name may follow on its letterhead — the crest / government lines.
_GOVERNMENT_LINE = re.compile(r'^ (?:KERAJAAN MALAYSIA|KEMENTERIAN|JABATAN|MINISTRY|DEPARTMENT|GOVERNMENT|JATA NEGARA)(?= )')
#: ... and the address / contact lines.
_ADDRESS_LINE = re.compile(r' (?:JALAN|JLN|LORONG|PERSIARAN|LEBUH|LOT|NO|PETI SURAT|P O BOX|TAMAN|KAMPUNG|BANDAR|'
                           r'TEL|TELEFON|FAKS|FAX|WWW|EMEL|E MEL|EMAIL|MALAYSIA|JOHOR|KEDAH|KELANTAN|MELAKA|'
                           r'NEGERI SEMBILAN|PAHANG|PERAK|PERLIS|PULAU PINANG|PENANG|SABAH|SARAWAK|SELANGOR|'
                           r'TERENGGANU|KUALA LUMPUR|LABUAN|PUTRAJAYA|WILAYAH PERSEKUTUAN)(?= )|(?<!\d)\d{5}(?!\d)')


#: Lead's ruling 2026-11-04 (confirmations): an institution's own DIVISION line may precede its name.
_DIVISION_LINE = re.compile(r'^ (?:BAHAGIAN|PEJABAT|UNIT|SEKSYEN|JABATAN|PUSAT|DIVISION|OFFICE|DEPARTMENT|CENTRE FOR)(?= )')


def _own_division_or_crest(ln) -> bool:
    """A division line of the institution itself (its remaining words name no company, no private body, no other
    institution), or a short crest / motto line (at most two words, no institution noun, no company, no digit)."""
    if any(c in ln for c in _COMPANY_HEAD) or _SB.search(ln) or any(b in ln for b in _PRIVATE_BODIES):
        return False
    m = _DIVISION_LINE.search(ln)
    if m:
        return not _HEAD_RE.search(ln[m.end():])
    return len(ln.split()) <= 2 and not _ORG_RE.search(ln) and not any(ch.isdigit() for ch in ln)


def _named_first(lines, names, agency_names=(), divisions=False, then=()) -> bool:
    """Round 10 (M4): a closed-list name is on the FIRST letterhead line, or comes only after crest / government
    lines (KERAJAAN MALAYSIA, a ministry / department, the matching agency) and address lines. Any other line before
    it ("MERCU JAYA" above the institute) = no lift."""
    for ln in _letterhead_lines(lines) + list(then):        # `then`: a confirmation's own title segment
        if any(n in ln for n in names):
            return True
        rest = ln
        for a in agency_names:
            rest = rest.replace(a, ' ')
        if not rest.strip() or _GOVERNMENT_LINE.search(ln) or _ADDRESS_LINE.search(ln) or _is_contact(ln):
            continue
        if divisions and _own_division_or_crest(ln):
            continue                    # confirmations (lead's ruling 2026-11-04)
        return False
    return False


def _without_poly_department(lines):
    out = []
    for ln in lines:
        for d in _POLY_DEPARTMENTS:
            ln = ln.replace(d, ' ')
        out.append(ln)
    return out


def _confirmation_lift(r, raw, model_version):
    if _AGENT_WORDS.search(_page(raw)):
        return None                     # round 11 (M5): WAKIL / EJEN / AGEN
    seen = confirmation_kind('', r['probability'], lines=raw)
    if not seen:
        return None
    lines, glued = _unglued(raw), any(len(ln.split()) > 40 for ln in raw)
    if not (_letter_structure(lines, _CONFIRM_TITLES, min_lines=_CONFIRM_MIN_LINES, glued=glued)
            and _own_identity_lines(lines, _CONFIRM_TITLES)):
        return None
    return _ruled_status('genuine', r, seen, 'confirmation', 'a confirmation-of-studies letter from a public '
                         'institution with no private wing - an acceptable alternative (owner ruling 4)',
                         model_version)


def _company_lift(ocr_text, r, lines, model_version):
    """A ministry family's own letter, scoring genuine, that the pre-S6 veto blocked only for an incidental
    company line."""
    if r['probability'] < GENUINE_MIN or not ministry_letter_naming_a_company(ocr_text, r, lines):
        return None
    return _ruled_status('genuine', r, r['type'], 'incidental_company', f"{r['type'].replace('_', ' ')} letter: "
                         'its only "Sdn Bhd" is an incidental line (a bank\'s own, the addressee) - the '
                         'family scores genuine', model_version)


def _lift(ocr_text, r, lines, page, vetoed, model_version, baseline_status=''):
    """LIFT → genuine, only on the full proof (module note 2); None when any part is unclear."""
    if _private_marker(lines):
        return None
    if baseline_status == 'not_offer_letter' and _loan_amount(lines):
        return None                     # round 10 (M1): a loan / financing beside an RM amount
    if vetoed:
        if not (_veto_only_by_a_company(page) and _company_lines_incidental(lines)):
            return None                 # a SPACE / SATU / letterhead company veto stands
        lifted = _company_lift(ocr_text, r, lines, model_version)
        if lifted:
            return lifted
    return (_tvet_lift(r, lines, model_version) or _agency_lift(ocr_text, r, lines, model_version)
            or _confirmation_lift(r, lines, model_version))


# ── BLOCK ─────────────────────────────────────────────────────────────────────────────────
def _block(r, lines, model_version):
    proof = private_proof(lines)
    if not proof:
        return None
    return _ruled_status('not_offer_letter', r, r['type'], 'private_offer', f'private college / university (IPTS): '
                         f'{proof} on the letterhead - not a supported public offer (owner rulings 2 + 7)',
                         model_version)


# ── SOFTENING a fail on its own proof (owner rulings 3 + 6) ───────────────────────────────
def _tvet_slip(r, lines, model_version):
    key = _institute_on_letterhead(lines) or _agency_on_letterhead(lines)
    if not key or _SLIP not in _page(_letterhead_block(lines)) or not _has_offer_words(_page(lines)):
        return None
    return _ruled_status('suspect', r, key, 'tvet_slip', f'{TVET_ISSUERS[key][0]}: a TVET offer SLIP, not an offer '
                         'letter - suspect (owner ruling 6); a person checks it', model_version)


def _agency_on_letterhead(lines) -> str:
    head = _page(_letterhead_lines(lines))
    for key, (_d, names, acronyms) in TVET_ISSUERS.items():
        if any(f' {n} ' in head for n in names) or any(f' {a} ' in head for a in acronyms if len(a) > 3):
            return key
    return ''


def _printout(ocr_text, r, lines) -> bool:
    page = _page(lines)
    if (_APPLICATION_SLIP in page or _private_marker(lines)
            or private_college_reason(ocr_text, r, public_words=_PUBLIC_LINE_WORDS)):
        return False                    # never soften a page that is, or shows, a private institution
    if any(m in page for m in _EDAFTAR):
        return True
    return _has_offer_words(page) and sum(1 for m in _PORTAL_FURNITURE if m in page) >= 2


def _soften(ocr_text, r, baseline, lines, page, vetoed, model_version):
    if baseline.get('status') != 'not_offer_letter' or private_proof(lines):
        return None
    if vetoed and not _veto_only_by_a_company(page):
        return None
    slip = _tvet_slip(r, lines, model_version) if not _private_marker(lines) else None
    if slip:
        return slip
    if _printout(ocr_text, r, lines):
        return {**baseline, 'reason': (_TAG.format('printout') + 'an admission printout / portal page, '
                                                f"not the offer letter - suspect (owner ruling 3); "
                                                f"{baseline['reason']}")[:300], 'status': 'suspect'}
    return None


def _vetoed(ocr_text) -> bool:
    """The pre-S6 private-arm veto set the baseline."""
    from .results_doc import _private_arm_offer
    return _private_arm_offer(ocr_text)


# ── The one entry ─────────────────────────────────────────────────────────────────────────
def ruled_offer(ocr_text: str, r: dict, status: str, reason: str, model_version: str) -> dict:
    """`apply_rulings` on the pre-S6 call of an offer that banded `status` (no private-arm veto): the 1.8.0
    net's result below the genuine band (`offer_issuers.unfingerprinted_offer`), else the band itself."""
    if status == 'genuine':
        baseline = {'status': status, 'probability': r['probability'], 'type': r['type'], 'present': r['present'],
                    'missing': r['missing'], 'reason': reason[:300], 'model_version': model_version}
    else:
        baseline = unfingerprinted_offer(ocr_text, r, status, reason, model_version)
    return apply_rulings(ocr_text, r, baseline, model_version)


def apply_rulings(ocr_text: str, r: dict, baseline: dict, model_version: str) -> dict:
    """The genuineness of an offer: the BASELINE (`results_doc.baseline_genuineness`), changed only by the
    BLOCK, a LIFT or a softening ruling (module note). A changed call always carries its ruling tag."""
    ocr_text = normalise_s6(ocr_text)                       # round 11: the one S6 normaliser
    lines = _folded_lines(ocr_text)                         # round 8 (perf): the page is folded ONCE
    if baseline.get('status') != 'not_offer_letter':
        blocked = _block(r, lines, model_version)
        if blocked:
            return blocked
    if baseline.get('status') != 'genuine':
        page, vetoed = _page(lines), _vetoed(ocr_text)
        lifted = _lift(ocr_text, r, lines, page, vetoed, model_version, baseline.get('status'))
        if lifted:
            return lifted
        softened = _soften(ocr_text, r, baseline, lines, page, vetoed, model_version)
        if softened:
            return softened
    return baseline
