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
ROUND 3 (2026-11-03): a TVET letterhead / a confirmation's letterhead may name ONLY the allowed bodies
(`_clean_letterhead`: no other organisation noun, no partner wording); the structure test asks for a
candidate label with a value and an IC number, a course line and (offers) a reporting line, and an offer of
12+ lines; below the suspect floor the body names the institute again. THE SAFETY RULE: a closed-list public
body on the page with NO positive private evidence that misses a rule reads `suspect` (`tvet_unverified` /
`confirmation_unverified`, a person decides) — never a fail. Another institution named first, with a private
letterhead, reads `not_offer_letter` by the private-college reason.
Anything else keeps the band it scored (`offer_issuers.unfingerprinted_offer`, unchanged).

Calibrated on the 287-letter offer corpus (S6): 14 letters move as ruled; none of the 237 genuine public
offers and none of the rightly rejected letters moves (`eval/offer_genuineness_check.py`). Pure.
"""
import re
import unicodedata
from collections import Counter

from .bands import GENUINE_MIN, SUSPECT_MAX
from .offer_issuers import (_PUBLIC_WORDS, TVET_ISSUERS, _has_offer_words, _letterhead,
                            private_college_reason, private_mara_on_letterhead, tvet_issuer,
                            unfingerprinted_offer)

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
#: "TVET" spelt out (an offer title "… Technical and Vocational Education and Training") names the sector,
#: never another institution — its EDUCATION / TRAINING are not organisation nouns.
_TVET_SPELT = (' TECHNICAL AND VOCATIONAL EDUCATION AND TRAINING ', ' TECHNICAL VOCATIONAL EDUCATION AND TRAINING ',
               ' PENDIDIKAN DAN LATIHAN TEKNIKAL DAN VOKASIONAL ', ' PENDIDIKAN DAN LATIHAN TEKNIK DAN VOKASIONAL ')
#: The closed-list bodies' own names (agencies + institutes): what a TVET letterhead may name.
_TVET_NAMES = tuple(dict.fromkeys(_INSTITUTES + tuple(
    f' {x} ' for _d, names, acr in TVET_ISSUERS.values() for x in names + acr)))
#: Nouns that name an organisation. The FIRST one a page names is its issuer; on a LETTERHEAD every one must be
#: a name the rule allows (round-3 review: "ABC TRAINING CENTRE" / "ABC EDUCATION GROUP" / "ABC TECH PLT").
_ORG_WORDS = (r'KOLEJ|COLLEGES?|AKADEMI|ACADEM(?:Y|IES|IC)|UNIVERSITI|UNIVERSIT(?:Y|IES)|INSTITUT|INSTITUTES?|'
              r'INSTITUTIONS?|TUISYEN|TUITION|SEKOLAH|SCHOOLS?|POLITEKNIK|POLYTECHNICS?|MAKTAB|'
              r'PUSAT (?:LATIHAN|KEMAHIRAN|PEMBELAJARAN|PENDIDIKAN|BAHASA)|TRAINING|TRAINERS?|CENTR[A-Z]*|CENTERS?|'
              r'HUBS?|GROUPS?|PLT|EDU[A-Z]*|LEARNING|SKILLS?|ENTERPRIS[A-Z]*|RESOURCES?|INTERNATIONAL|GLOBAL|'
              r'SERVIC[A-Z]*|SOLUTIONS?|HOLDINGS?|CORP[A-Z]*|CONSULT[A-Z]*|KONSULT[A-Z]*|VENTURES?|LTD|LIMITED|INC|'
              r'PERSATUAN|PERTUBUHAN|TECH|KAMPUS|YAYASAN')
#: An organisation noun, matched by STEM on a folded line (round-4 review: ENTERPRISES, CENTRES, EDUCATIONAL …).
_ORG_RE = re.compile(rf' (?:{_ORG_WORDS}|SDN|BHD|BERHAD)(?= )')
#: The same without the company words (the Sdn Bhd excuse asks for an organisation BESIDE the company).
_ORG_RE_NO_COMPANY = re.compile(rf' (?:{_ORG_WORDS})(?= )')
#: Partner wording on a letterhead: a private institution trading on a public one's name.
_PARTNER = (' PARTNER ', ' RAKAN ', ' BERSAMA ', ' AFFILIATED ', ' FRANCAIS ', ' FRANCHISE ', ' STRATEGIK ',
            ' STRATEGIC ', ' KERJASAMA ', ' USAHASAMA ', ' COLLABORATION ', ' ACCREDITED ', ' DIIKTIRAF ',
            ' ASSOCIATION ', ' MEMBER ')   # round 4: + the tie-up words
_PERSON_LABELS = (' NAMA ', ' KAD PENGENALAN ', ' NO K P ', ' MYKAD ', ' NO KP ', ' NAME ')
_LABEL_VALUE = re.compile(r' (?:NAMA|NAME|KAD PENGENALAN|NO K P|NO KP|MYKAD) [A-Z0-9]')
_IC = re.compile(r'\b\d{6}\s?\d{2}\s?\d{4}\b')
_SALUTE = (' TUAN ', ' PUAN ', ' SAUDARA ', ' SAUDARI ', ' SESIAPA ', ' DEAR ')
#: A contact line (web / e-mail / telephone / fax): "edu.my" in an address names no other institution.
_CONTACT = re.compile(r' (?:WWW|HTTP|HTTPS|E MEL|EMEL|EMAIL|E MAIL|TEL|TELEFON|FAKS|FAX|EDU MY|GOV MY|COM MY) ')
#: POSITIVE private evidence, read per line, never on an excused line (`_incidental`).
_PRIVATE_SIGNS = (' SDN BHD ', ' BHD ', ' BERHAD ', ' SENDIRIAN BERHAD ', ' SWASTA ', ' PERSENDIRIAN ',
                  ' IPTS ', ' KPT JPT ')
#: A bank / insurer / co-operative named on a payment line (its "Berhad" holds the fees, it issues nothing).
_FINANCE = (' BANK ', ' MAYBANK ', ' CIMB ', ' RHB ', ' AMBANK ', ' AFFIN ', ' BSN ', ' AGROBANK ', ' HONG LEONG ',
            ' BANK ISLAM ', ' ISLAMIC ', ' TAKAFUL ', ' INSURANS ', ' INSURANCE ', ' KOPERASI ', ' AKAUN ')
_VENDOR = (' PEMBEKAL ', ' PENCETAK ', ' DICETAK ', ' PRINTED BY ', ' SUPPLIER ', ' DIBEKALKAN ')
#: A sponsor line names who pays (round 4: "Penaja : ABC Sdn Bhd" on a real IKBN letter), never the issuer.
_SPONSOR_LINE = (' PENAJA ', ' TAJAAN ', ' DITAJA ', ' SPONSOR ', ' SPONSORED BY ')
#: An ISO / SIRIM certification line names a standard, not an organisation (round 4).
_CERTIFICATION = re.compile(r' (?:ISO|SIRIM|MS ISO|IQNET) ')
_ADDRESS = re.compile(r' (?:PETI SURAT|P O BOX|JALAN|LOT|KAMPUNG|TAMAN|LADANG|ESTATE|MILL) |\b\d{5}\b')
_CONDITIONAL = (' BERSYARAT ', ' CONDITIONAL ')
#: A real letter's parts (`_letter_structure`).
_REFERENCE = (' RUJUKAN ', ' RUJ ', ' NO RUJ ', ' REF ', ' RUJUKAN KAMI ', ' OUR REF ')
#: A date (folded: '12 06 2026'); its left edge is "not a digit", not a word boundary — a glued text layer
#: prints "TARIKH28 10 2025".
_DATE_RE = re.compile(r'(?<!\d)\d{1,2}\s*(?:JAN|FEB|MAC|MAR|APR|MEI|MAY|JUN|JUL|OGO|AUG|SEP|OKT|OCT|NOV|DIS|DEC)'
                      r'[A-Z]*\s*20\d\d(?!\d)|(?<!\d)\d{1,2}\s*[./ -]\s*\d{1,2}\s*[./ -]\s*20\d\d(?!\d)')
_TITLE = (' TAWARAN ', ' OFFER ')
_CLOSING = (' YANG BENAR ', ' MENJALANKAN AMANAH ', ' PENGARAH ', ' B P ', ' MENURUT PERINTAH ', ' SEKIAN ',
            ' TIMBALAN ', ' YANG IKHLAS ', ' YOURS SINCERELY ', ' DIRECTOR ')
_COURSE = (' PROGRAM ', ' KURSUS ', ' BIDANG ', ' SIJIL ', ' DIPLOMA ', ' SEMESTER ', ' PENGAJIAN ')
_REPORTING = (' LAPOR DIRI ', ' PENDAFTARAN ', ' MENDAFTAR ', ' DAFTAR ', ' HADIR ')   # not the title's KEMASUKAN
_OFFER_MIN_LINES = 12        # round-3 review: a real offer letter is a page, not five lines
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


def _is_person_line(ln) -> bool:
    return any(lb in ln for lb in _PERSON_LABELS) or bool(_IC.search(ln))


def _incidental(lines, i) -> bool:
    """Is line `i` one where a company name says nothing about who ISSUED the letter: a bank / insurer /
    co-operative's own payment line (never "bayaran … kepada X Sdn Bhd" — a fee to a company), a vendor or
    printer line, or the ADDRESSEE's address — within the candidate block (the two lines after her name / IC
    line)?"""
    ln = lines[i]
    if any(w in ln for w in _FINANCE) or any(w in ln for w in _VENDOR) or any(w in ln for w in _SPONSOR_LINE):
        return True                     # a bank / insurer / co-operative or a printer — "kepada X Sdn Bhd"
                                        # names none of them, so a fee to a company is never excused
    in_candidate_block = any(_is_person_line(lines[j]) for j in range(max(0, i - 3), i))
    nxt = lines[i + 1] if i + 1 < len(lines) else ''
    return in_candidate_block and bool(_ADDRESS.search(ln) or _ADDRESS.search(nxt))


def _private_signs(lines) -> bool:
    """POSITIVE private evidence on a line that is not incidental (a bank "Berhad" is not the issuer)."""
    return any(any(s in ln for s in _PRIVATE_SIGNS) and not _incidental(lines, i) for i, ln in enumerate(lines))


def _private_mara_letterhead(ocr_text) -> bool:
    """A MARA-owned PRIVATE institution on the LETTERHEAD (`offer_issuers.private_mara_on_letterhead`)."""
    return private_mara_on_letterhead(ocr_text)


#: A street name ("Jalan Kolej", "Lorong Universiti") names a road, not an institution.
_STREET = re.compile(r' (?:JALAN|JLN|LORONG|PERSIARAN|LEBUH|LEBUHRAYA|TAMAN|BANDAR|SEKSYEN|PRESINT) '
                     r'[A-Z0-9]+(?: [A-Z0-9]+)?(?= )')   # up to two words: "Presint 1 Kolej", "Jalan Kolej Baru"
#: Web / e-mail tails ("edu.my") inside a long glued line name no institution either.
_WEB_TAIL = re.compile(r' (?:EDU|GOV|COM|ORG) M ?Y(?= )')   # OCR can space it: 'EDU M Y'


def _unstreeted(ln) -> str:
    """The line without what names no institution: a street name, a web tail, a certification line."""
    if _CERTIFICATION.search(ln) and len(ln.split()) <= 12:
        return ' '
    return _WEB_TAIL.sub(' ', _STREET.sub(' ', ln))


def _untitled(ln) -> str:
    """On a TITLE line only, "TVET" spelt out ("… Technical and Vocational Education and Training") names the
    sector, not an institution (app 329). Never stripped on the letterhead (round 4: "ABC TECHNICAL AND
    VOCATIONAL EDUCATION AND TRAINING" is an organisation's name there)."""
    if any(t in ln for t in _TITLE + _CONFIRM_TITLES):
        for phrase in _TVET_SPELT:
            ln = ln.replace(phrase, ' ')
    return ln


def _is_contact(ln) -> bool:
    """A short contact line (a glued text layer's whole page is one long line, and is never one)."""
    return len(ln.split()) <= 12 and bool(_CONTACT.search(ln))


def _first_institution(lines, allowed) -> str:
    """'allowed' when the FIRST organisation the page names is one of `allowed`, 'other' when another comes
    first, '' when none is named. A line beside a public word (a ministry, a department, the federal
    administration) is the public body, not another organisation."""
    for ln in lines:
        if _is_contact(ln):
            continue                    # a web / e-mail / phone line names no institution
        ln = _untitled(_unstreeted(ln))
        spans = [(ln.find(a), ln.find(a) + len(a)) for a in allowed if a in ln]
        first_allowed = min((s for s, _e in spans), default=None)
        public = any(w in ln for w in _PUBLIC_WORDS)
        others = [] if public else [m.start() for m in _ORG_RE.finditer(ln)
                                    if not any(s <= m.start() < e for s, e in spans)]
        first_other = min(others, default=None)
        if first_allowed is None and first_other is None:
            continue
        if first_other is None:
            return 'allowed'
        if first_allowed is None:
            return 'other'
        return 'allowed' if first_allowed <= first_other else 'other'
    return ''


def _letterhead_lines(lines):
    """The letterhead: the lines before the letter proper — its title, a salutation or the candidate's
    line. A reference or date line on the way is SKIPPED, not a stop (round 4: "Tarikh : 1 Jun 2026" above
    "INSTITUT KEMAHIRAN MARA / GERMAN MALAYSIAN INSTITUTE" hid the letterhead)."""
    stops = _TITLE + _CONFIRM_TITLES + _SALUTE
    head = []
    for ln in lines:
        if any(s in ln for s in stops) or _is_person_line(ln):
            break
        if any(r in ln for r in _REFERENCE) or _DATE_RE.search(ln):
            continue
        head.append(ln)
    return head


def _clean_letterhead(lines, allowed) -> bool:
    """Round-3 review: EVERY letterhead line may name only an allowed body — after the allowed names are taken
    out, no organisation noun may remain (unless the line is a public body's) — and no partner wording."""
    for ln in _letterhead_lines(lines):
        if any(p in ln for p in _PARTNER):
            return False
        if _is_contact(ln):
            continue
        ln = _unstreeted(ln)
        rest = ln
        for a in allowed:
            rest = rest.replace(a, ' ')
        if _ORG_RE.search(rest) and not any(w in ln for w in _PUBLIC_WORDS):
            return False
    return True


def _letter_structure(lines, titles_words, *, min_lines=0, reporting=False, glued=False) -> bool:
    """Does the page carry what a real letter is made of, IN A LETTER'S ORDER — a reference line, a dated
    line, a candidate label WITH a value and an IC number, a course / programme line (and, for an offer, a
    reporting line), its title, and a signatory / closing block AFTER the title and the reference — with no
    padding (a page of repeated lines or one repeated token)? (Order, not a fixed line number: a photo can
    hold two letters side by side, the offer below another's closing — corpus.)"""
    if len(lines) < max(min_lines, 5):
        return False
    tokens = ' '.join(lines).split()
    if len(set(lines)) / len(lines) < _UNIQUE_LINES_MIN or (
            tokens and Counter(tokens).most_common(1)[0][1] / len(tokens) > _TOKEN_SHARE_MAX):
        return False
    page = _page(lines)

    def at(words):
        return [i for i, ln in enumerate(lines) if any(w in ln for w in words)]
    # A glued text layer (one very long line) runs "RUJUKAN" into its neighbours; there 'RUJ' anywhere counts.
    refs = at(_REFERENCE) or [i for i, ln in enumerate(lines)
                               if (glued or len(ln.split()) > 40) and _GLUED_RUJ.search(ln)]
    titles, closings = at(titles_words), at(_CLOSING)
    return (bool(refs and titles and closings) and any(_DATE_RE.search(ln) for ln in lines)
            and bool(_LABEL_VALUE.search(page)) and bool(_IC.search(page))
            and any(c in page for c in _COURSE) and (not reporting or any(r in page for r in _REPORTING))
            and max(closings) >= min(titles) and max(closings) >= min(refs))


#: A glued layer's reference: "RUJ" starting a run of letters — never inside a word ("dirujuk").
_GLUED_RUJ = re.compile(r'(?<![A-Z])RUJ')    # glued after a phone number ('...0000RUJUKAN'), never 'DIRUJUK'
#: The labels a glued text layer runs together; split on them before counting a confirmation's lines.
_GLUED_LABELS = re.compile(r' (?=(?:NAMA|NO KAD PENGENALAN|KAD PENGENALAN|NO MATRIK|NO PELAJAR|PROGRAM|FAKULTI|'
                           r'SEMESTER|SESI|TARIKH|RUJUKAN|RUJ|PENGESAHAN|YANG BENAR|SEKIAN|STATUS|TEMPOH|KAMPUS) )')
#: The fewest lines (glued layers split on their labels) a real confirmation of studies has: the corpus's five
#: hold 42 / 58 / 64 lines and, glued, 15 / 16 segments (round 4, measured).
_CONFIRM_MIN_LINES = 12


def _unglued(lines):
    """A glued text layer's lines split on the labels it runs together (a photo's lines stay as they are)."""
    out = []
    for ln in lines:
        if len(ln.split()) > 40:
            out += [f' {seg.strip()} ' for seg in _GLUED_LABELS.split(ln) if seg.strip()]
        else:
            out.append(ln)
    return out


def _own_identity_lines(lines, title_words) -> bool:
    """Round 4: the candidate's NAME label and her IC number sit on lines of their own — never both inside the
    title line (the "PENGESAHAN PELAJAR NAMA ALI 080808105566 PROGRAM …" one-liner)."""
    name = [i for i, ln in enumerate(lines) if _LABEL_VALUE.search(ln) and not any(t in ln for t in title_words)]
    ic = [i for i, ln in enumerate(lines) if _IC.search(ln) and not any(t in ln for t in title_words)]
    return bool(name and ic)


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
    incidental (`_incidental`: a bank / vendor line, or the addressee's address in the candidate block) with
    no organisation noun on it or the line before. Anywhere else (the letterhead, a logo strip, a footer, a
    tuition centre, a fee "kepada X Sdn Bhd") keeps the veto. `_private_arm_offer` itself is unchanged."""
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
    return _company_lines_incidental(lines)


def _company_lines_incidental(lines) -> bool:
    """Every "Sdn Bhd" / "Sendirian Berhad" line is incidental (`_incidental`), off the letterhead, with no
    organisation noun on it or the line before."""
    head = set(_letterhead_lines(lines))
    for i, ln in enumerate(lines):
        if ' SDN BHD ' in ln or ' SENDIRIAN BERHAD ' in ln:
            near = ln + (lines[i - 1] if i else '')
            if ln in head or not _incidental(lines, i) or _ORG_RE_NO_COMPANY.search(_unstreeted(near)):
                return False
    return True


def tvet_letter_naming_a_company(ocr_text: str, r: dict) -> bool:
    """Round 4: the same excuse for a closed-list TVET body's letter (it prints no ministry issuer line): a
    real IKBN letter naming its uniform supplier, insurer, sponsor or the student's estate address keeps its
    rules; a "Sdn Bhd" on the letterhead still vetoes."""
    from .results_doc import _PRIVATE_ARM_PHRASES
    lines = _folded_lines(ocr_text)
    page = _page(lines)
    hits = [p for p in _PRIVATE_ARM_PHRASES if p in page]
    if not hits or set(hits) - {'SDN BHD', 'SENDIRIAN BERHAD'} or ' SPACE ' in page:
        return False
    return bool(tvet_issuer(_without_incidental_companies(ocr_text), r.get('scores'))) and \
        _company_lines_incidental(lines)


def _without_incidental_companies(ocr_text: str) -> str:
    """The text without its incidental "Sdn Bhd" lines (a supplier, an insurer, a sponsor, the student's
    estate address — `_incidental`), so the 600-character letterhead tests of `offer_issuers` do not read a
    short letter's body company as its letterhead."""
    from .results_doc import _norm_fold_upper_alnum
    raws = [raw for raw in unicodedata.normalize('NFKC', ocr_text or '').splitlines() if _norm_fold_upper_alnum(raw)]
    lines = [f' {_norm_fold_upper_alnum(raw)} ' for raw in raws]
    keep = [raw for i, (raw, ln) in enumerate(zip(raws, lines))
            if not ((' SDN BHD ' in ln or ' SENDIRIAN BERHAD ' in ln) and _incidental(lines, i))]
    return '\n'.join(keep)


def _unproven(r, seen, tag, what, model_version):
    """THE SAFETY RULE (round-3 review): a closed-list public body is on the page and there is NO positive
    private evidence, but the page misses a rule — a person decides, never a fail. In the suspect band the
    1.8.0 path answers (None → NOT CHECKED, no signal); below it, `suspect`."""
    if SUSPECT_MAX <= r['probability'] < GENUINE_MIN:
        return None
    return _ruled_status('suspect', r, seen, tag, f'{what}: a public body on the page but not a complete letter '
                         'by the rules - suspect, a person decides', model_version)


def _tvet(ocr_text, r, model_version):
    key = tvet_issuer(_without_incidental_companies(ocr_text), r.get('scores'))
    if not key:
        return None
    name, lines = TVET_ISSUERS[key][0], _folded_lines(ocr_text)
    if _private_signs(lines) or _private_mara_letterhead(ocr_text):
        return None                     # positive private evidence: the band (and its private reason) stands
    if _SLIP in _letterhead(ocr_text):
        return _ruled_status('suspect', r, key, 'tvet_slip', f'{name}: a TVET offer SLIP, not an offer letter - '
                             'suspect (owner ruling 6); a person checks it', model_version)
    if _first_institution(lines, _TVET_NAMES) == 'other':
        # Another organisation is named first — the issuer — and the TVET name is a partner / mention
        # (round-3 review): a private institution's letter, a fail by its own reason.
        why = private_college_reason(ocr_text, r) or (
            f'another institution issues this letter; {name} is named only beside it - not a public offer')
        return _ruled_status('not_offer_letter', r, r['type'], 'private_offer', f'{why} (owner rulings 2 + 7)',
                             model_version)
    if not _clean_letterhead(lines, _TVET_NAMES):
        return _unproven(r, key, 'tvet_unverified', name, model_version)
    if _first_institution(lines, _INSTITUTES) != 'allowed':
        return _unproven(r, key, 'tvet_unverified', name, model_version)
    if not _letter_structure(lines, _TITLE, min_lines=_OFFER_MIN_LINES, reporting=True):
        return _unproven(r, key, 'tvet_unverified', name, model_version)
    if r['probability'] < SUSPECT_MAX:
        body = lines[len(_letterhead_lines(lines)):]
        if not any(i in ln for ln in body for i in _INSTITUTES):
            return _unproven(r, key, 'tvet_unverified', name, model_version)
    return _ruled_status('genuine', r, key, 'tvet_offer', f'{name}: a public TVET institute\'s offer letter - '
                         'a public offer (owner rulings 5 and Q2)', model_version)


def confirmation_kind(ocr_text: str, probability: float = 1.0) -> str:
    """The `confirmation_*` code of a confirmation-of-studies letter by its issuer, or '' (no title, below the
    score floor, positive private evidence, or no public issuer named first on a clean letterhead)."""
    lines = _folded_lines(ocr_text)
    page = _page(lines)
    if not any(t in page for t in _CONFIRM_TITLES) or probability < CONFIRM_MIN:
        return ''
    if _private_mara_letterhead(ocr_text) or _private_signs(lines):
        return ''
    scan = [ln.replace(_JPPKK, ' ') for ln in lines]       # the department's name names no polytechnic
    for seen, names, marks in _NO_PRIVATE_WING:
        if (_first_institution(scan, names) == 'allowed' and any(m in page for m in marks)
                and _clean_letterhead(scan, names)):
            return seen
    from .results_doc import _UA_NAMES
    ua = tuple(f' {n} ' for n in _UA_NAMES)
    if _first_institution(scan, ua) == 'allowed' and _clean_letterhead(scan, ua):
        return 'confirmation_ua'
    return ''


def _confirmation(ocr_text, r, model_version):
    seen = confirmation_kind(ocr_text, r['probability'])
    if not seen:
        return None
    if seen == 'confirmation_ua':
        return _ruled_status('suspect', r, seen, 'confirmation_ua', 'a public university confirmation-of-studies '
                             'letter - suspect: confirm the government programme (owner ruling 4)', model_version)
    raw = _folded_lines(ocr_text)
    lines, glued = _unglued(raw), any(len(ln.split()) > 40 for ln in raw)
    if not (_letter_structure(lines, _CONFIRM_TITLES, min_lines=_CONFIRM_MIN_LINES, glued=glued)
            and _own_identity_lines(lines, _CONFIRM_TITLES)):
        return _unproven(r, seen, 'confirmation_unverified', 'a confirmation of studies', model_version)
    return _ruled_status('genuine', r, seen, 'confirmation', 'a confirmation-of-studies letter from a public '
                         'institution with no private wing - an acceptable alternative (owner ruling 4)',
                         model_version)


def _printout(ocr_text, r) -> bool:
    lines = _folded_lines(ocr_text)
    page = _page(lines)
    if (_APPLICATION_SLIP in page or _private_signs(lines) or _private_mara_letterhead(ocr_text)
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
        positive = (_private_signs(lines) or _private_mara_letterhead(ocr_text)
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
