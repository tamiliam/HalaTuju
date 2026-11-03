"""The offer-genuineness RULINGS' reading of a page — its folded lines, letterhead block, private proof, letter
structure — and the word lists they use. Moved out of `offer_rulings.py` in S6 round 5 (2026-11-03; that file
passed the 600-line standard). That move was NOT verbatim, though its commit said so: 8 moved names changed and
7 were added inside it (see CHANGELOG, S6 round 6). S6 round 7 (the narrowing) cut what only the guessing
middle logic used. `offer_rulings` imports every name back (`__all__`).
"""
import re
import unicodedata
from collections import Counter

from .offer_issuers import TVET_ISSUERS

__all__ = [
    'CONFIRMATION_SEEN',
    'CONFIRM_MIN',
    '_COMPANY_HEAD',
    '_ADDRESS',
    '_APPLICATION_SLIP',
    '_CERTIFICATION',
    '_CLOSING',
    '_CONFIRM_MIN_LINES',
    '_CONFIRM_TITLES',
    '_CONTACT',
    '_COURSE',
    '_DATE_RE',
    '_EDAFTAR',
    '_FINANCE',
    '_GLUED_KIND',
    '_GLUED_LABELS',
    '_GLUED_RUJ',
    '_HEAD_RE',
    '_IC',
    '_INSTITUTES',
    '_JPPKK',
    '_LABEL_VALUE',
    '_MINISTRY_FAMILIES',
    '_NAME_MARK',
    '_NO_PRIVATE_WING',
    '_OFFER_MIN_LINES',
    '_ORG_RE',
    '_ORG_RE_NO_COMPANY',
    '_ORG_WORDS',
    '_PARTNER',
    '_PERSON_LABELS',
    '_POLY_DEPARTMENTS',
    '_PORTAL_FURNITURE',
    '_PRIVATE_BODIES',
    '_PUBLIC_LINE_WORDS',
    '_POSTCODE',
    '_PRIVATE_SIGNS',
    '_REFERENCE',
    '_REPORTING',
    '_SALUTE',
    '_SLIP',
    '_SPONSOR_LINE',
    '_STREET',
    '_TAG',
    '_TAG_RE',
    '_TIE_UP',
    '_TITLE',
    '_TOKEN_SHARE_MAX',
    '_TVET_NAMES',
    '_TVET_SPELT',
    '_UNIQUE_LINES_MIN',
    '_UNIT_LINE',
    '_UNIT_TAIL',
    '_VENDOR',
    '_WEB_TAIL',
    '_allowed_spans',
    '_clean_letterhead',
    '_confirm_titled',
    '_excused',
    '_first_institution',
    '_folded_lines',
    '_in_addressee_block',
    '_incidental',
    '_is_contact',
    '_is_person_line',
    '_letter_structure',
    '_letterhead_block',
    '_letterhead_lines',
    '_letterhead_region',
    '_outside_orgs',
    '_own_identity_lines',
    '_page',
    '_private_marker',
    '_private_signs',
    'private_proof',
    '_ruled_status',
    '_untitled',
    '_unglued',
    '_unstreeted',
    'ruling_of',
]


#: The tag a ruling writes at the head of its `reason` (`ruling_of` reads it back).
_TAG = '[S6 ruling: {}] '
_TAG_RE = re.compile(r'^\[S6 ruling: ([a-z_]+)\] ')
#: A TVET page that calls itself a SLIP on its letterhead / title (a body's "slip bayaran" does not count).
_SLIP = ' SLIP '
#: Public TVET INSTITUTES — an agency (MARA, TVETMARA, JTM, JPK, the ministry, ILKBS) is not one.
_INSTITUTES = (' INSTITUT KEMAHIRAN BELIA NEGARA ', ' INSTITUT KEMAHIRAN TINGGI BELIA NEGARA ', ' IKBN ',
               ' IKTBN ', ' INSTITUT KEMAHIRAN MARA ', ' IKM ', ' KOLEJ KEMAHIRAN TINGGI MARA ', ' KKTM ',
               ' KOLEJ MARA ', ' KOLEJ PROFESIONAL MARA ', ' INSTITUT LATIHAN PERINDUSTRIAN ', ' ILP ',
               ' ADTEC ', ' PUSAT LATIHAN TEKNOLOGI TINGGI ', ' ILJTM ',
               # round 5 (H2): the same institutes on an English-first letterhead
               ' ADVANCED TECHNOLOGY TRAINING CENTRE ', ' INDUSTRIAL TRAINING INSTITUTE ',
               ' NATIONAL YOUTH SKILLS INSTITUTE ', ' NATIONAL YOUTH HIGH SKILLS INSTITUTE ', ' MARA SKILLS INSTITUTE ',
               ' MARA HIGHER SKILLS COLLEGE ', ' MARA PROFESSIONAL COLLEGE ',
               # owner 2026-11-03: JMTI and CIAST are government (JTM) institutes — S6 LIFT only (the pre-S6
               # 1.8.0 net, `offer_issuers.TVET_ISSUERS`, is the baseline's and unchanged)
               ' JMTI ', ' JAPAN MALAYSIA TECHNICAL INSTITUTE ', ' CIAST ',
               ' PUSAT LATIHAN PENGAJAR DAN KEMAHIRAN LANJUTAN ')
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
#: An institution's OWN unit (round 5, H1): a line naming a faculty / division / centre-for / unit / campus of
#: the institution is not another organisation ("UNIVERSITI MALAYSIA SABAH / ACADEMIC SERVICES DIVISION").
#: Round 6: its describing words lead the match ("ACADEMIC SERVICES DIVISION" is one unit, not an academy).
_UNIT_LINE = re.compile(r' (?:(?:ACADEMIC|STUDENT|SERVICES) )*'
                        r'(?:FACULTY|FAKULTI|DIVISION|BAHAGIAN|CENTRE FOR|CENTER FOR|PUSAT PENGAJIAN|UNIT|JABATAN|'
                        r'STUDENT SERVICES|HAL EHWAL|DEPARTMENT OF|SCHOOL OF|PUSAT ASASI|CENTRE FOR FOUNDATION)(?= )')
#: Words that, right after an allowed name on the same line, name its campus or unit (Low 4: "IKTBN KAMPUS
#: SEPANG", "KKTM TECH CAMPUS").
_UNIT_TAIL = re.compile(r' (?:KAMPUS|CAMPUS|SERVICES|TECH|CAWANGAN|BRANCH)(?= )')
#: Round 6 (H-A): the nouns that NAME an institution or a company (never a subject: EDUCATION, TRAINING …). After
#: a public / unit word on a line, one of these outside an allowed name is another organisation
#: ("FAKULTI PERNIAGAAN, KOLEJ UNIVERSITI ABC").
_HEAD_RE = re.compile(r' (?:KOLEJ|COLLEGES?|UNIVERSITI|UNIVERSIT(?:Y|IES)|INSTITUT|INSTITUTES?|AKADEMI|ACADEMY|'
                      r'POLITEKNIK|POLYTECHNICS?|MAKTAB|TUISYEN|TUITION|SEKOLAH|SCHOOLS?|SDN|BHD|BERHAD|PLT|LTD|'
                      r'LIMITED|INC|PUSAT (?:LATIHAN|KEMAHIRAN|PEMBELAJARAN|PENDIDIKAN|BAHASA))(?= )')
#: Public bodies' own words on a letterhead line (S6 lift gating only; `offer_issuers._PUBLIC_WORDS` is the
#: baseline's, unchanged).
_PUBLIC_LINE_WORDS = (' KEMENTERIAN ', ' JABATAN ', ' KERAJAAN ', ' MAJLIS ', ' SEKOLAH ', ' TINGKATAN ',
                      ' KOLEJ KOMUNITI ', ' KOLEJ MATRIKULASI ', ' KOLEJ VOKASIONAL ', ' ASWARA ', ' ILKKM ',
                      ' LEMBAGA ', ' PERBADANAN ', ' KOLEJ KEJURURAWATAN ', ' AKADEMI BINAAN MALAYSIA ', ' ABM ',
                      ' AKADEMI PERCUTIAN MALAYSIA ', ' MINISTRY ', ' DEPARTMENT ', ' GOVERNMENT ')
#: THE NAMED PRIVATE BODIES (owner rulings C + 2026-11-03): MARA-owned private institutions, UM's open
#: channel (SATU), UMS's self-funded centre (PPPL).
_PRIVATE_BODIES = (' KOLEJ POLY TECH MARA ', ' KOLEJ POLYTECH MARA ', ' KPTM ', ' KOLEJ UNIVERSITI POLY TECH MARA ',
                   ' KOLEJ UNIVERSITI POLYTECH MARA ', ' KUPTM ', ' UNIVERSITI POLY TECH MALAYSIA ',
                   ' UNIVERSITI POLYTECH MALAYSIA ', ' UPTM ', ' UNIVERSITI KUALA LUMPUR ', ' UNIKL ',
                   ' GERMAN MALAYSIAN INSTITUTE ', ' GMI ', ' SALURAN SATU ', ' SALURAN TERBUKA ',
                   ' PUSAT PENDIDIKAN PROFESIONAL DAN LANJUTAN ', ' PUSAT PENDIDIKAN LANJUTAN ', ' PPPL ')
#: EXPLICIT partner / tie-up words — the BLOCK overlay's (a private institution trading on a public name).
_TIE_UP = (' PARTNER ', ' RAKAN ', ' RAKAN STRATEGIK ', ' RAKAN KERJASAMA ', ' STRATEGIC PARTNER ', ' AFFILIATED ',
           ' FRANCAIS ', ' FRANCHISE ', ' KERJASAMA ', ' USAHASAMA ', ' COLLABORATION ', ' IN ASSOCIATION WITH ')
#: A company on a letterhead line (the BLOCK overlay's proof).
_COMPANY_HEAD = (' SDN BHD ', ' SENDIRIAN BERHAD ', ' BHD ', ' BERHAD ')
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
            ' BANK ISLAM ', ' TAKAFUL ', ' INSURANS ', ' INSURANCE ', ' KOPERASI ', ' AKAUN ')
_VENDOR = (' PEMBEKAL ', ' PENCETAK ', ' DICETAK ', ' PRINTED BY ', ' SUPPLIER ', ' DIBEKALKAN ')
#: A sponsor line names who pays (round 4: "Penaja : ABC Sdn Bhd" on a real IKBN letter), never the issuer.
_SPONSOR_LINE = (' PENAJA ', ' TAJAAN ', ' DITAJA ', ' SPONSOR ', ' SPONSORED BY ')
#: An ISO / SIRIM certification line names a standard, not an organisation (round 4).
_CERTIFICATION = re.compile(r' (?:ISO|SIRIM|MS ISO|IQNET) ')
_ADDRESS = re.compile(r' (?:PETI SURAT|P O BOX|JALAN|LOT|KAMPUNG|TAMAN|LADANG|ESTATE|MILL) |\b\d{5}\b')
_POSTCODE = re.compile(r'(?<!\d)\d{5}(?!\d)')
#: A personal name's patronymic marker ("ALI A/L MUTHU", "SITI BINTI AHMAD", "ANAK").
_NAME_MARK = re.compile(r' (?:BIN|BINTI|BTE|A L|A P|ANAK|AK) ')
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
    ('confirmation_polytechnic', (' POLITEKNIK ', ' POLYTECHNIC '), (_JPPKK, ' KEMENTERIAN PENDIDIKAN TINGGI ',
                                                    ' MINISTRY OF HIGHER EDUCATION ',
                                                    ' DEPARTMENT OF POLYTECHNIC AND COMMUNITY COLLEGE EDUCATION ')),
    ('confirmation_ums', (' UNIVERSITI MALAYSIA SABAH ', ' UMS '), (' UNIVERSITI MALAYSIA SABAH ',)),
    ('confirmation_form6', (' KOLEJ TINGKATAN ENAM ', ' SMK ', ' SEKOLAH MENENGAH KEBANGSAAN '),
     (' KEMENTERIAN PENDIDIKAN MALAYSIA ', ' MINISTRY OF EDUCATION MALAYSIA ', ' KOLEJ TINGKATAN ENAM ', ' SMK ',
      ' SEKOLAH MENENGAH KEBANGSAAN ')),
)
CONFIRMATION_SEEN = frozenset(k for k, _n, _m in _NO_PRIVATE_WING)   # round 7: no confirmation_ua (baseline)
#: The polytechnics' department, Malay and English: it names no polytechnic or college (blanked before a scan).
_POLY_DEPARTMENTS = (_JPPKK, ' DEPARTMENT OF POLYTECHNIC AND COMMUNITY COLLEGE EDUCATION ')
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
    islamic_finance = ' ISLAMIC ' in ln and (' BANK ' in ln or (' BERHAD ' in ln and not _ORG_RE_NO_COMPANY.search(
        ln)))                           # round 6: never beside an organisation noun ("ABC ISLAMIC COLLEGE BERHAD")
    if (any(w in ln for w in _FINANCE) or islamic_finance or any(w in ln for w in _VENDOR)
            or any(w in ln for w in _SPONSOR_LINE)):
        return True                     # a bank / insurer / co-operative or a printer — "kepada X Sdn Bhd"
                                        # names none of them, so a fee to a company is never excused
    in_candidate_block = any(_is_person_line(lines[j]) for j in range(max(0, i - 3), i))
    nxt = lines[i + 1] if i + 1 < len(lines) else ''
    if in_candidate_block and bool(_ADDRESS.search(ln) or _ADDRESS.search(nxt)):
        return True
    return _in_addressee_block(lines, i)                            # round 5, H3


def _in_addressee_block(lines, i) -> bool:
    """Round 5 (H3): line `i` sits in the ADDRESSEE block — below the letter's reference / date, with a postcode
    within its next three lines (an unlabelled "ALI A/L MUTHU / Ladang … Sdn Bhd / 31000 Batu Gajah")."""
    below = any(any(r in ln for r in _REFERENCE) or _DATE_RE.search(ln) for ln in lines[:i])
    return below and any(_POSTCODE.search(ln) for ln in lines[i:i + 4])


def _private_signs(lines) -> bool:
    """A private sign on a line that is not incidental (a bank "Berhad", a supplier, a sponsor, the addressee,
    an ISO / SIRIM certification line are not the issuer)."""
    return any(any(s in ln for s in _PRIVATE_SIGNS) and not _incidental(lines, i) and not _is_certification(ln)
               for i, ln in enumerate(lines))


def _is_certification(ln) -> bool:
    return bool(_CERTIFICATION.search(ln)) and len(ln.split()) <= 12


def private_proof(lines) -> str:
    """THE BLOCK OVERLAY'S PROOF (S6 round 7), read on the LETTERHEAD BLOCK only (`_letterhead_block`): a
    company ("Sdn Bhd" / "Berhad"), a named private body, or explicit tie-up wording. A bank / payment line
    and an ISO / SIRIM certification line are not proof. '' when there is none."""
    for ln in _letterhead_block(lines):
        if _is_certification(ln) or any(w in ln for w in _FINANCE):
            continue
        if any(c in ln for c in _COMPANY_HEAD):
            return 'company'
        if any(b in ln for b in _PRIVATE_BODIES):
            return 'named private body'
        if any(t in ln for t in _TIE_UP):
            return 'tie-up wording'
    return ''


def _private_marker(lines) -> bool:
    """Any private marker on the page — what stops a LIFT: the block's proof, a named private body anywhere,
    or a private sign off the incidental lines."""
    page = _page(lines)
    return bool(private_proof(lines)) or any(b in page for b in _PRIVATE_BODIES) or _private_signs(lines)


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


def _is_contact(ln) -> bool:
    """A short contact line (a glued text layer's whole page is one long line, and is never one)."""
    return len(ln.split()) <= 12 and bool(_CONTACT.search(ln))


def _letterhead_block(lines):
    """THE LETTERHEAD BLOCK (S6 round 7) — the BLOCK overlay's: the lines above the letter proper. It ends at the first title,
    salutation, "Kepada" or candidate line (the text before it on that line is kept — a glued text layer
    is one line), and at the ADDRESSEE block below the reference / date (a line with a postcode within its
    next four lines: a student's or a Yayasan's / Persatuan's address is never letterhead). A reference or
    date line on the way is SKIPPED, the text before "Ruj" / the date kept (round 4 / round 5)."""
    stops = _TITLE + _CONFIRM_TITLES + _SALUTE + (' KEPADA ',)
    head, dated = [], False
    for i, ln in enumerate(lines):
        cuts = [ln.find(s) for s in stops + _PERSON_LABELS if s in ln] + [m.start() for m in _IC.finditer(ln)]
        if cuts:
            before = _before_ref(ln[:min(cuts)] + ' ')
            for phrase in _TVET_SPELT:          # app 329: spelt-out TVET before a title names the sector
                before = before.replace(phrase, ' ')
            if before.strip():
                head.append(before)
            break
        if dated and any(_POSTCODE.search(x) for x in lines[i:i + 4]):
            break                       # the addressee block below the date
        ref = [ln.find(r) for r in _REFERENCE if r in ln]
        date = _DATE_RE.search(ln)
        if ref or date:
            dated = True
            before = _before_ref(ln)
            if before.strip():          # round 5 (Medium 5): keep what shares the line BEFORE "Ruj" / the date
                head.append(before)
            continue
        head.append(ln)
    return head


def _letterhead_lines(lines):
    """The LIFT's letterhead (round 6, unchanged): the lines before the letter proper — its title, a salutation
    or the candidate's line. A reference or date line on the way is SKIPPED, not a stop (round 4: "Tarikh : 1 Jun
    2026" above "INSTITUT KEMAHIRAN MARA / GERMAN MALAYSIAN INSTITUTE" hid the letterhead). Longer than the
    BLOCK's (`_letterhead_block`): a lift needs EVERY line of it clean, so more lines only lift less."""
    stops = _TITLE + _CONFIRM_TITLES + _SALUTE
    head, dated = [], False
    for i, ln in enumerate(lines):
        if any(s in ln for s in stops) or _is_person_line(ln):
            break
        if dated and _NAME_MARK.search(ln) and any(_POSTCODE.search(x) for x in lines[i + 1:i + 5]):
            break                       # round 5 (H3): the addressee's name, then her address, below the date
        ref = [ln.find(r) for r in _REFERENCE if r in ln]
        date = _DATE_RE.search(ln)
        if ref or date:
            dated = True
            cut = min(ref + ([date.start()] if date else []))
            before = ln[:cut]
            if before.strip():          # round 5 (Medium 5): keep what shares the line BEFORE "Ruj" / the date
                head.append(before + ' ')
            continue
        head.append(ln)
    return head


def _untitled(ln) -> str:
    """On a TITLE line only, "TVET" spelt out names the sector, not an institution (app 329)."""
    if any(t in ln for t in _TITLE + _CONFIRM_TITLES):
        for phrase in _TVET_SPELT:
            ln = ln.replace(phrase, ' ')
    return ln


def _first_institution(lines, allowed) -> str:
    """A LIFT gate (never a block): 'allowed' when the FIRST organisation the page names is one of `allowed`,
    'other' when another comes first, '' when none is named. A line led by a public or unit word is the public
    body or a unit (`_excused`)."""
    for ln in lines:
        if _is_contact(ln):
            continue                    # a web / e-mail / phone line names no institution
        ln = _untitled(_unstreeted(ln))
        spans = _allowed_spans(ln, allowed)
        first_allowed = min((s for s, _e in spans), default=None)
        others = _outside_orgs(ln, spans)
        first_other = None if _excused(ln, others) else min(others, default=None)
        if first_allowed is None and first_other is None:
            continue
        if first_other is None:
            return 'allowed'
        if first_allowed is None:
            return 'other'
        return 'allowed' if first_allowed <= first_other else 'other'
    return ''


def _before_ref(ln) -> str:
    """The part of a line before its reference / date, if any."""
    cut = [ln.find(r) for r in _REFERENCE if r in ln] + [m.start() for m in _DATE_RE.finditer(ln)]
    return (ln[:min(cut)] + ' ') if cut else ln


def _letterhead_region(lines):
    """The letterhead's lines WHOLE — reference / date lines included — up to the title, a salutation or the
    candidate's line."""
    stops = _TITLE + _CONFIRM_TITLES + _SALUTE
    out = []
    for ln in lines:
        if any(s in ln for s in stops) or _is_person_line(ln):
            break
        out.append(ln)
    return out


def _clean_letterhead(lines, allowed) -> bool:
    """Round-3 review: EVERY letterhead line may name only an allowed body — after the allowed names are taken
    out, no organisation noun may remain (unless the line is a public body's) — and no partner wording."""
    if any(any(p in ln for p in _PARTNER) for ln in _letterhead_region(lines)):
        return False                    # partner wording on any letterhead line, whole (round 5, Medium 5)
    for ln in _letterhead_lines(lines):
        if _is_contact(ln):
            continue
        ln = _unstreeted(ln)
        others = _outside_orgs(ln, _allowed_spans(ln, allowed))
        if others and not _excused(ln, others):
            return False
    return True


def _allowed_spans(ln, allowed):
    """Every place an allowed name sits on the line."""
    out = []
    for a in allowed:
        i = ln.find(a)
        while i >= 0:
            out.append((i, i + len(a)))
            i = ln.find(a, i + 1)
    return out


def _outside_orgs(ln, spans):
    """Where the line names an organisation noun OUTSIDE an allowed name — never inside one, nor a campus /
    unit word straight after one (Low 4: "IKTBN KAMPUS SEPANG", "KKTM TECH CAMPUS")."""
    ends = {e - 1 for _s, e in spans}
    for m in _UNIT_TAIL.finditer(ln):
        if m.start() in ends:
            ends.add(m.end())           # a run of tail words after the name
    def inside(o):                      # a name's trailing space starts the NEXT word ("IKBN KOLEJ ABC")
        return any(s <= o < e - 1 for s, e in spans)
    return [m.start() for m in _ORG_RE.finditer(ln)
            if not inside(m.start()) and not (m.start() in ends and _UNIT_TAIL.match(ln, m.start()))]


def _excused(ln, others) -> bool:
    """Round 6: a public or unit word excuses a line's organisation nouns ONLY when none of them comes BEFORE
    it ("KOLEJ ABC (KEMENTERIAN …)", "KOLEJ ABC UNIT KEMASUKAN" are KOLEJ ABC's) and no institution / company
    name (`_HEAD_RE`) comes after it outside the public words themselves ("FAKULTI PERNIAGAAN, KOLEJ
    UNIVERSITI ABC")."""
    covers = [(ln.find(w), ln.find(w) + len(w) - 1) for w in _PUBLIC_LINE_WORDS if w in ln] + [
        m.span() for m in _UNIT_LINE.finditer(ln)]
    if not covers:
        return False
    first = min(s for s, _e in covers)
    if any(o < first for o in others):
        return False
    return not any(_HEAD_RE.match(ln, o) and not any(s <= o < e for s, e in covers) for o in others)


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
_GLUED_KIND = re.compile(r' (NAMA|KAD PENGENALAN|PROGRAM|FAKULTI|SEMESTER|SESI|TARIKH|RUJUKAN|PENGESAHAN|YANG BENAR|'
                         r'STATUS|TEMPOH|KAMPUS) ')


def _unglued(lines):
    """A glued text layer's lines split on the labels it runs together (a photo's lines stay as they are)."""
    out = []
    for ln in lines:
        toks = ln.split()
        kinds = {m.group(1) for m in _GLUED_KIND.finditer(ln)}
        filler = sum(1 for t in toks if len(t) == 1) / max(1, len(toks))
        if len(toks) > 40 and len(kinds) >= 4 and filler < 0.3:     # round 5 (Low 6): a real labelled layer only
            out += [f' {seg.strip()} ' for seg in _GLUED_LABELS.split(ln) if seg.strip()]
        else:
            out.append(ln)
    return out


def _confirm_titled(lines, probability) -> bool:
    """Round 6: a confirmation-of-studies page — the score floor (`CONFIRM_MIN`), and its title in the TOP part
    of the letter: before any offer title, and in the page's first half or its first `_CONFIRM_TOP_CHARS`
    characters (a letterhead's length) — never a private offer's body "pengesahan pelajar"."""
    if probability < CONFIRM_MIN:
        return False
    page = _page(lines)
    at = min((page.find(t) for t in _CONFIRM_TITLES if t in page), default=-1)
    offer = min((page.find(t) for t in _TITLE if t in page), default=len(page))
    return 0 <= at < offer and at <= max(_CONFIRM_TOP_CHARS, len(page) // 2)


_CONFIRM_TOP_CHARS = 400


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
