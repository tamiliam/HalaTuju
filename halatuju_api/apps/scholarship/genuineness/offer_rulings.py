"""The owner's offer-letter genuineness rulings, applied AFTER the signature band (offer exact-read S6,
MODEL_VERSION 1.23.0).

A genuineness status is a BURSARY decision, not a document type (owner, 2026-11-01, `docs/decisions.md`):
`not_offer_letter` is a FAIL, `suspect` means "not sure, a person decides", `genuine` is a public offer we
can support. The signature families (`offer_signatures`) only know the five fingerprinted public issuers,
so on their own they failed letters the owner rules acceptable and let one private letter through as
merely "not sure". `ruled_offer` is the ONE place those rulings are applied; `results_doc.
signature_genuineness` hands every offer that did not band genuine here.

THE OWNER'S STANCE (2026-11-03): no hedging cap — a ruling-lifted letter reads GREEN when it meets the rule:
"Let us be guided by data. The corpus is sparse now but will fill. Let the model predict; if it is wrong, it
serves as a lesson." So the rules are STRUCTURAL (what a real letter is made of), not word lists, and every
lift is LEARNABLE: its `reason` starts with `[S6 ruling: <tag>]` (`ruling_of`) and a lifted genuine stores a
`doc_seen` of its own (`tvet_*`, `confirmation_*`), so a reviewer's override or a later corpus answer shows
which rule was wrong (`eval/offer_genuineness_check.py` counts them per tag; S8 mines it).

In order (the first that applies wins):
  1. A PUBLIC TVET OFFER (ruling 5; Q2) → `genuine` (`tvet_offer`): a closed-list body named on the
     letterhead (`offer_issuers.tvet_issuer`, the 2026-10-26 C1 rules 2-6); the FIRST institution the page
     names is a public TVET INSTITUTE (`_INSTITUTES`) — never another college / academy named before it (a
     private one "accredited by JPK" or "in collaboration with MARA"); no private sign; and the STRUCTURE of
     a real letter (`_letter_structure`: a reference line, a dated line, an offer title near the top, a
     candidate label, a signatory / closing block, no padding). A TVET page that calls itself a SLIP on its
     letterhead → `suspect` (`tvet_slip`, ruling 6).
  2. A CONFIRMATION OF STUDIES (ruling 4 + the default) → `genuine` (`confirmation`): its own title, a
     student / programme line, a score floor, no private sign, and the FIRST institution named is a
     no-private-wing public one (a polytechnic with its ministry line, UMS, a Form-6 college / SMK with its
     public mark). Another public university's → `suspect` (`confirmation_ua`).
  3. A suspect-band PRIVATE offer (rulings 2 + 7) → `not_offer_letter` (`private_offer`), only on POSITIVE
     private evidence (`_private_signs`, a named private MARA-owned college) or a private conditional.
  4. An ADMISSION PRINTOUT / PORTAL PAGE (ruling 3) that banded `not_offer_letter` → `suspect` (`printout`),
     on portal-only furniture or an e-Daftar slip — never over a private sign or a private letterhead.
Anything else keeps the band it scored (`offer_issuers.unfingerprinted_offer`, unchanged).

Calibrated on the 287-letter offer corpus (S6): 14 letters move as ruled; none of the 237 genuine public
offers and none of the rightly rejected letters moves (`eval/offer_genuineness_check.py`). Pure.
"""
import re
import unicodedata

from .bands import GENUINE_MIN, SUSPECT_MAX
from .offer_issuers import (_PRIVATE_MARA, _PUBLIC_WORDS, TVET_ISSUERS, _has_offer_words, _letterhead,
                            private_college_reason, tvet_issuer, unfingerprinted_offer)

#: The tag a ruling writes at the head of its `reason` (`ruling_of` reads it back).
_TAG = '[S6 ruling: {}] '
_TAG_RE = re.compile(r'^\[S6 ruling: ([a-z_]+)\] ')
#: A TVET page that calls itself a SLIP on its letterhead / title (a body's "slip bayaran" does not count).
_SLIP = ' SLIP '
#: Public TVET INSTITUTES — an agency (MARA, TVETMARA, JTM, JPK, the ministry, ILKBS) is not one.
_INSTITUTES = (' INSTITUT KEMAHIRAN BELIA NEGARA ', ' INSTITUT KEMAHIRAN TINGGI BELIA NEGARA ', ' IKBN ',
               ' IKTBN ', ' INSTITUT KEMAHIRAN MARA ', ' IKM ', ' KOLEJ KEMAHIRAN TINGGI MARA ', ' KKTM ',
               ' KOLEJ MARA ', ' KOLEJ PROFESIONAL MARA ', ' INSTITUT LATIHAN PERINDUSTRIAN ', ' ILP ',
               ' ADTEC ', ' PUSAT LATIHAN TEKNOLOGI TINGGI ', ' ILJTM ')
#: Words that name an institution. The FIRST institution a page names is its issuer: a line naming one
#: before the institute the rule is about (and with no public word on the line) is another institution.
_STRONG = (' KOLEJ ', ' COLLEGE ', ' AKADEMI ', ' ACADEMY ', ' UNIVERSITI ', ' UNIVERSITY ', ' INSTITUT ',
           ' INSTITUTE ', ' TUISYEN ', ' TUITION ', ' SEKOLAH ', ' SCHOOL ')
_PERSON_LABELS = (' NAMA ', ' KAD PENGENALAN ', ' NO K P ', ' MYKAD ', ' NO KP ', ' NAME ')
#: POSITIVE private evidence, read per line, never on a payment / bank / vendor line or an address line.
_PRIVATE_SIGNS = (' SDN BHD ', ' BHD ', ' BERHAD ', ' SENDIRIAN BERHAD ', ' SWASTA ', ' PERSENDIRIAN ',
                  ' IPTS ', ' KPT JPT ')
_PAYMENT = (' BAYARAN ', ' AKAUN ', ' BANK ', ' PEMBEKAL ', ' PENCETAK ', ' DICETAK ', ' PRINTED BY ')
_ADDRESS = re.compile(r' (?:PETI SURAT|P O BOX|JALAN|LOT|KAMPUNG|TAMAN|LADANG|ESTATE|MILL) |\b\d{5}\b')
_CONDITIONAL = (' BERSYARAT ', ' CONDITIONAL ')
#: A real letter's parts (`_letter_structure`).
_REFERENCE = (' RUJUKAN ', ' RUJ ', ' NO RUJ ', ' REF ', ' RUJUKAN KAMI ', ' OUR REF ')
_DATE_RE = re.compile(r'\b\d{1,2}\s*(?:JAN|FEB|MAC|MAR|APR|MEI|MAY|JUN|JUL|OGO|AUG|SEP|OKT|OCT|NOV|DIS|DEC)[A-Z]*'
                      r'\s*20\d\d\b|\b\d{1,2}\s*[./ -]\s*\d{1,2}\s*[./ -]\s*20\d\d\b')   # folded: '12 06 2026'
_TITLE = (' TAWARAN ', ' OFFER ')
_CLOSING = (' YANG BENAR ', ' MENJALANKAN AMANAH ', ' PENGARAH ', ' B P ', ' MENURUT PERINTAH ', ' SEKIAN ',
            ' TIMBALAN ', ' YANG IKHLAS ', ' YOURS SINCERELY ', ' DIRECTOR ')
_UNIQUE_LINES_MIN = 0.6      # a padded page repeats its lines
_TOKEN_SHARE_MAX = 0.25      # ... or one token
#: The confirmation-of-studies title, and the no-private-wing issuers (owner default 2026-11-03).
_CONFIRM_TITLES = (' PENGESAHAN PELAJAR ', ' PENGESAHAN SEBAGAI PELAJAR ', ' PENGESAHAN BELAJAR ',
                   ' PENGESAHAN STATUS PELAJAR ')
_JPPKK = ' JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI '
_NO_PRIVATE_WING = (
    # (doc_seen, the institution's own names, its public mark anywhere on the page)
    ('confirmation_polytechnic', (' POLITEKNIK ',), (_JPPKK, ' KEMENTERIAN PENDIDIKAN TINGGI ')),
    ('confirmation_ums', (' UNIVERSITI MALAYSIA SABAH ', ' UMS '), (' UNIVERSITI MALAYSIA SABAH ',)),
    ('confirmation_form6', (' KOLEJ TINGKATAN ENAM ', ' SMK ', ' SEKOLAH MENENGAH KEBANGSAAN '),
     (' KEMENTERIAN PENDIDIKAN MALAYSIA ', ' KOLEJ TINGKATAN ENAM ', ' SMK ', ' SEKOLAH MENENGAH KEBANGSAAN ')),
)
CONFIRMATION_SEEN = frozenset(k for k, _n, _m in _NO_PRIVATE_WING) | {'confirmation_ua'}
_CONFIRM_BODY = _PERSON_LABELS + (' PROGRAM ', ' KURSUS ', ' BIDANG ')
#: The least a real confirmation scores on the families (every corpus one: 0.13-0.30).
CONFIRM_MIN = 0.10
#: Portal-only furniture (never TAHNIAH / BERJAYA, which offer letters print, nor URL chrome).
_PORTAL_FURNITURE = (' SEMAKAN KEPUTUSAN ', ' KEPUTUSAN PERMOHONAN ', ' MUAT TURUN ', ' CETAK ', ' LOG KELUAR ')
_EDAFTAR = (' SLIP E DAFTAR ', ' SLIP EDAFTAR ')
_APPLICATION_SLIP = ' SLIP PERMOHONAN '
#: The ministry-body families (a government department has no private wing; a university's arm prints the
#: parent's name, so the UA family is not here).
_MINISTRY_FAMILIES = ('stpm', 'matriculation', 'polytechnic', 'pismp')


# ── Reading the page ──────────────────────────────────────────────────────────────────────
def _folded_lines(ocr_text):
    """The page's non-empty lines, NFKC-normalised (full-width letters are letters) and folded."""
    from .results_doc import _norm_fold_upper_alnum
    out = []
    for raw in unicodedata.normalize('NFKC', ocr_text or '').splitlines():
        f = _norm_fold_upper_alnum(raw)
        if f:
            out.append(f' {f} ')
    return out


def _page(lines):
    return ' ' + ' '.join(ln.strip() for ln in lines) + ' '


def _incidental(lines, i):
    """Is line `i` a payment / bank / vendor line, or the ADDRESSEE's address (an address-shaped line, or
    one followed by a postcode / PO box, BELOW the letter's reference or date — the letterhead's own address
    sits above them) — where a company name says nothing about who ISSUED the letter?"""
    if any(w in lines[i] for w in _PAYMENT):
        return True
    nxt = lines[i + 1] if i + 1 < len(lines) else ''
    below_the_date = any(any(r in ln for r in _REFERENCE) or _DATE_RE.search(ln) for ln in lines[:i])
    return below_the_date and bool(_ADDRESS.search(lines[i]) or _ADDRESS.search(nxt))


def _private_signs(lines) -> bool:
    """POSITIVE private evidence on a line that is not incidental (a bank "Berhad" is not the issuer)."""
    return any(any(s in ln for s in _PRIVATE_SIGNS) and not _incidental(lines, i) for i, ln in enumerate(lines))


def _first_institution(lines, allowed) -> str:
    """'allowed' when the FIRST institution the page names is one of `allowed`, 'other' when another
    institution comes first, '' when none is named. A line naming an institution beside a public word (a
    ministry, a department, the federal administration) is the public body, not another institution."""
    for ln in lines:
        spans = [(ln.find(a), ln.find(a) + len(a)) for a in allowed if a in ln]
        first_allowed = min((s for s, _e in spans), default=None)
        public = any(w in ln for w in _PUBLIC_WORDS)
        others = [] if public else [ln.find(w) for w in _STRONG if w in ln
                                    and not any(s <= ln.find(w) < e for s, e in spans)]
        first_other = min(others, default=None)
        if first_allowed is None and first_other is None:
            continue
        if first_other is None:
            return 'allowed'
        if first_allowed is None:
            return 'other'
        return 'allowed' if first_allowed <= first_other else 'other'
    return ''


def _letter_structure(lines) -> bool:
    """Does the page carry what a real offer letter is made of, IN A LETTER'S ORDER — a reference line, a
    dated line, a candidate label, an offer title, and a signatory / closing block AFTER the title (and after
    the reference) — with no padding (a page of repeated lines or one repeated token)? The S6 review's
    padded / typed probes have none of it. (Order, not a fixed line number: a photo can hold two letters
    side by side, the offer below another's closing — corpus.)"""
    if len(lines) < 5:
        return False
    tokens = ' '.join(lines).split()
    if len(set(lines)) / len(lines) < _UNIQUE_LINES_MIN or (
            tokens and max(tokens.count(t) for t in set(tokens)) / len(tokens) > _TOKEN_SHARE_MAX):
        return False
    page = _page(lines)
    def at(words):
        return [i for i, ln in enumerate(lines) if any(w in ln for w in words)]
    refs, titles, closings = at(_REFERENCE), at(_TITLE), at(_CLOSING)
    return (bool(refs and titles and closings) and any(_DATE_RE.search(ln) for ln in lines)
            and any(lb in page for lb in _PERSON_LABELS)
            and max(closings) > min(titles) and max(closings) > min(refs))


def ruling_of(authenticity) -> str:
    """The S6 ruling that set a stored genuineness, from its reason's tag ('' when no ruling did)."""
    m = _TAG_RE.match(str((authenticity or {}).get('reason') or ''))
    return m.group(1) if m else ''


def _ruled_status(status, r, seen, tag, reason, model_version):
    return {'status': status, 'probability': r['probability'], 'type': seen, 'present': r['present'],
            'missing': r['missing'], 'reason': (_TAG.format(tag) + reason)[:300], 'model_version': model_version}


# ── The rulings ───────────────────────────────────────────────────────────────────────────
def ministry_letter_naming_a_company(ocr_text: str, r: dict) -> bool:
    """True when the private-arm veto (`results_doc._private_arm_offer`) fired ONLY on "Sdn Bhd" /
    "Sendirian Berhad", a ministry family's own issuer line is on the page, and EVERY such line is
    incidental (a payment / bank / vendor line, or the addressee's address — a student living on a company
    estate) with no institution word on it or the line before. Then the letter is scored by its band. A
    company named anywhere else (the letterhead, a logo strip, a footer, a tuition centre) keeps the veto.
    `_private_arm_offer` itself is unchanged (`catalogue_levels`, `offer_reporting_bonus` gate 3b read it)."""
    from .offer_issuers import FAMILY_ISSUER_SIG
    from .results_doc import _PRIVATE_ARM_PHRASES
    lines = _folded_lines(ocr_text)
    page = _page(lines)
    hits = [p for p in _PRIVATE_ARM_PHRASES if p in page]
    if not hits or set(hits) - {'SDN BHD', 'SENDIRIAN BERHAD'} or ' SPACE ' in page:
        return False
    scores = r.get('scores') or {}
    if not any(FAMILY_ISSUER_SIG[f] in ((scores.get(f) or {}).get('present') or []) for f in _MINISTRY_FAMILIES):
        return False
    for i, ln in enumerate(lines):
        if ' SDN BHD ' in ln or ' SENDIRIAN BERHAD ' in ln:
            near = ln + (lines[i - 1] if i else '')
            if not _incidental(lines, i) or any(w in near for w in _STRONG):
                return False
    return True


def _tvet(ocr_text, r, model_version):
    key = tvet_issuer(ocr_text, r.get('scores'))
    if not key:
        return None
    name, lines = TVET_ISSUERS[key][0], _folded_lines(ocr_text)
    if _SLIP in _letterhead(ocr_text):
        return _ruled_status('suspect', r, key, 'tvet_slip', f'{name}: a TVET offer SLIP, not an offer letter - '
                             'suspect (owner ruling 6); a person checks it', model_version)
    if (_first_institution(lines, _INSTITUTES) != 'allowed' or _private_signs(lines)
            or not _letter_structure(lines)):
        return None                     # another institution first, a private sign, or no letter → 1.8.0
    return _ruled_status('genuine', r, key, 'tvet_offer', f'{name}: a public TVET institute\'s offer letter - '
                         'a public offer (owner rulings 5 and Q2)', model_version)


def confirmation_kind(ocr_text: str, probability: float = 1.0) -> str:
    """The `confirmation_*` code of a confirmation-of-studies letter, or ''."""
    lines = _folded_lines(ocr_text)
    page = _page(lines)
    if not any(t in page for t in _CONFIRM_TITLES) or probability < CONFIRM_MIN:
        return ''
    if (any(p in page for p in _PRIVATE_MARA) or _private_signs(lines)
            or not any(b in page for b in _CONFIRM_BODY)):
        return ''
    scan = [ln.replace(_JPPKK, ' ') for ln in lines]       # the department's name names no polytechnic
    for seen, names, marks in _NO_PRIVATE_WING:
        if _first_institution(scan, names) == 'allowed' and any(m in page for m in marks):
            return seen
    from .results_doc import _UA_NAMES
    if _first_institution(scan, tuple(f' {n} ' for n in _UA_NAMES)) == 'allowed':
        return 'confirmation_ua'
    return ''


def _confirmation(ocr_text, r, model_version):
    seen = confirmation_kind(ocr_text, r['probability'])
    if not seen:
        return None
    if seen == 'confirmation_ua':
        return _ruled_status('suspect', r, seen, 'confirmation_ua', 'a public university confirmation-of-studies '
                             'letter - suspect: confirm the government programme (owner ruling 4)', model_version)
    return _ruled_status('genuine', r, seen, 'confirmation', 'a confirmation-of-studies letter from a public '
                         'institution with no private wing - an acceptable alternative (owner ruling 4)',
                         model_version)


def _printout(ocr_text, r) -> bool:
    lines = _folded_lines(ocr_text)
    page = _page(lines)
    if (_APPLICATION_SLIP in page or _private_signs(lines) or any(p in page for p in _PRIVATE_MARA)
            or private_college_reason(ocr_text, r)):
        return False                    # never lift a page that is, or shows, a private institution
    if any(m in page for m in _EDAFTAR):
        return True
    return _has_offer_words(page) and sum(1 for m in _PORTAL_FURNITURE if m in page) >= 2


def ruled_offer(ocr_text: str, r: dict, status: str, reason: str, model_version: str) -> dict:
    """The genuineness of an offer that did NOT band genuine, after the owner's rulings (module note)."""
    ocr_text = unicodedata.normalize('NFKC', ocr_text or '')
    ruled = _tvet(ocr_text, r, model_version) or _confirmation(ocr_text, r, model_version)
    if ruled:
        return ruled
    printout = _printout(ocr_text, r)
    if status == 'suspect' and SUSPECT_MAX <= r['probability'] < GENUINE_MIN and not printout:
        lines = _folded_lines(ocr_text)
        page = _page(lines)
        positive = (_private_signs(lines) or any(p in page for p in _PRIVATE_MARA)
                    or any(c in page for c in _CONDITIONAL))
        why = private_college_reason(ocr_text, r) if positive else ''
        if why:
            return _ruled_status('not_offer_letter', r, r['type'], 'private_offer', f'{why} (owner rulings 2 + 7)',
                                 model_version)
    out = unfingerprinted_offer(ocr_text, r, status, reason, model_version)
    if out['status'] == 'not_offer_letter' and printout:
        return {**out, 'status': 'suspect',
                'reason': (_TAG.format('printout') + 'an admission printout / portal page, not the offer letter '
                           f"- suspect (owner ruling 3); {out['reason']}")[:300]}
    return out
