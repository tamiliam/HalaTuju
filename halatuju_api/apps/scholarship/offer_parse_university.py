"""Deterministic read of the Universiti Malaysia Sabah (UMS) offer letter — OCR-first S1 (2026-11-19).

The first UNIVERSITY family of the Exact read (`offer_parse.diagnose` hands a UMS letter here). The
UMS letter is one fixed template ("TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA SABAH, SESI ..."), seen
two ways:

* a digital PDF: read from page 1's LAYOUT text (`pdf_rules_pages.pdf_page1_layout`), where each label and
  its value share a line and the name stands alone under the offer date. The plain text layer glues
  the IC, the student number, the name and the address into one run, so a name read from it could
  swallow an address word: a text-layer letter WITHOUT its layout text never locks here;
* a scanned letter (Vision OCR): one item per line, the blocks often out of order — so every field
  below is read by a rule that does not depend on the order of the label block.

CONSERVATIVE (owner rule: "the visible page always judges"; a wrong fact is worse than the AI):
every field has ONE source, and any doubt returns no lock, so the letter goes to the AI as before.

* title — "TAWARAN KEMASUKAN ..." at a LINE START; a cancellation, deferral, rejection, withdrawal,
  appeal or reply word (PEMBATALAN, PENANGGUHAN, PENOLAKAN, TARIK BALIK, RAYUAN, MAKLUMBALAS, TERBATAL,
  TIDAK BERJAYA) at or above the title refuses (``not_an_offer``), and so does DIBATALKAN / BATAL /
  DITARIK BALIK / DITARIK SEMULA / DITOLAK / TIDAK LAGI SAH / SURAT TIDAK BERJAYA anywhere, spaced
  letters ("D I B A T A L K A N") included. TERBATAL counts only in the head: genuine letters print it
  in a conditional clause.
* institution — the title only, never a hostel line; the hostel / venue goes to ``reporting_venue``.
* intake — "SESI ..." from the title.
* IC — ONLY from the "No. Kad Pengenalan" label (same line, or the next lines that hold nothing but
  the student number / a colon); never the first IC anywhere; any other IC on the page refuses.
* name — the line straight after the ONE offer-date line ("Tarikh : 15 Ogos 2026"; two such lines
  above the title — a stamp's date — read no name), by the strict shared name rules; a certifier's or
  officer's line (PENDAFTAR, CANSELOR, NAIB, TIMBALAN, PEJABAT ...) is never a name, and a next line
  that may be a wrapped name (a name connector or '@', a name-like column beside another, name-like with
  no street word, or name-like words before a comma or KG / KAMPUNG) reads no name.
* programme — from the label block between the title and the sentence: the "Program : ..." line (or,
  in a scan, the degree line after a bare "Program" label; a value may wrap onto ONE next line). It
  must AGREE, letter for letter, with the sentence "... untuk mendapat <programme> dan sebanyak ...";
  any value there or on any other programme label line ("Program : X", "Program Baharu : X", "Nama
  Program : X") that disagrees, or no label at all, reads no programme. It starts "Sarjana Muda" /
  "Ijazah Sarjana Muda" / "Diploma". The UPU code ("UH0000001") is extra evidence only, read with a
  glued-safe pattern bounded on the left (``offer_course_match.COURSE_CODE_RE`` misses a glued code).
* reporting date — the first date after "Tarikh Lapor Diri"; a range ("28 - 29 September", "28
  September - 1 Oktober 2031", "... hingga ...") gives its FIRST day, with its own month or the end's,
  the year borrowed from the end; a range that cannot be placed, or a date with a day number before
  it (any other joiner, a list), or a range wrapped across lines (a day number or a joiner on a line
  above the date), reads no date. Sane against the intake and the offer date.
* campus — only from the "Kampus" label (same line, or the line after a bare label) below the title,
  and only a value in the closed list of UMS campuses.

Status letters ("SURAT PENGESAHAN PELAJAR") and text longer than a page 1 (``MAX_CHARS`` / ``MAX_LINES``)
never lock. Pure; never raises on text input.
"""
from __future__ import annotations

import re

from .offer_parse import (_DMY_RE, _IC, _IC_END, _MALAY_MONTH, _NUM_DATE_RE, _decimal_digits, _name_ok, _norm_nric,
                          first_date)
from .offer_parse_families import _ENDS_MARKER, _blocked
#: The refusal checks live in `offer_ums_refusal` since the owner-words split (2026-11-20).
from .offer_ums_refusal import _squeeze, _withdrawn, fold_lookalikes, status_said

#: Recorded on a rules read (`rules_lane`) — the lane switch (`offer_exact.ocr_first_lanes`) names it.
LANE = 'ua:UMS'
INSTITUTION = 'Universiti Malaysia Sabah'
ISSUER = INSTITUTION                      # the letterhead's university (the answers' own convention)
#: The campuses a UMS letter prints ("Kampus : Kota Kinabalu"). A value outside this list is not read.
CAMPUSES = ('Kota Kinabalu', 'Antarabangsa Labuan', 'Labuan', 'Sandakan')
#: The most text a UMS page 1 holds (S1c): the 58 cached letters' largest page-1 text is under 5,000
#: characters and 100 lines, so these caps leave a wide margin. Longer text is refused before any rule
#: runs (200,000 hostile characters: about 2.5 s before, under 0.001 s now).
MAX_CHARS = 20_000
MAX_LINES = 250
MAX_LETTER_CHARS = 10 * MAX_CHARS          # the whole letter, every page (S1c round 2: `letter_refusal`)

_TITLE_WORDS = r'TAWARAN\s{1,3}KEMASUKAN\s{1,3}KE\s{1,3}UNIVERSITI\s{1,3}MALAYSIA\s{1,3}SABAH'
_DETECT = re.compile(_TITLE_WORDS, re.IGNORECASE)
#: The title STARTS its line (whitespace normalised): "PEMBATALAN TAWARAN KEMASUKAN ..." is not an offer.
_TITLE = re.compile(r'^' + _TITLE_WORDS + r'\s{0,3},?\s{0,3}(SESI\s{1,3}[0-9IV]{1,3}\s{0,2}-\s{0,2}20\d{2}\s{0,2}/\s{0,2}20\d{2})'
                    r'\s*$', re.IGNORECASE)
_DATE = r'\d{1,2}\s{1,3}' + _MALAY_MONTH + r'\s{1,3}20\d{2}'
#: The offer-date line ("Tarikh : 15 Ogos 2026"; Vision reads "Tankh"), or the label alone with the
#: date on the next line (":08 September 2025").
_OFFER_DATE = re.compile(r'^Ta[rn][il1]?[kc]h\s{0,3}:?\s{0,3}(' + _DATE + r')$', re.IGNORECASE)
_OFFER_LABEL = re.compile(r'^Ta[rn][il1]?[kc]h\s{0,3}:?$', re.IGNORECASE)
_DATE_ONLY = re.compile(r'^:?\s{0,3}(' + _DATE + r')$', re.IGNORECASE)
_IC_LABEL = re.compile(r'No\.?\s{0,3}Kad\s{1,3}Pengenalan\s{0,3}:?\s{0,3}(.*)$', re.IGNORECASE)
_IC_RE = re.compile(r'(?<!\d)' + _IC + _IC_END)
_STUDENT_NO = re.compile(r'^:?\s{0,3}[A-Z][A-Z0-9]\d{8}$')     # "BK00000001" (OCR may read a letter as a digit)
#: The label's own remainder when it is ONLY the IC, which the layout text may split ("01   0203145678").
_IC_ONLY = re.compile(r'^:?[\d 	-]{12,40}$')
#: A UPU programme code, glued-safe ("Program UH0000001Fakulti", "Fakulti:UH0000001Bayaran"): U + a letter
#: + seven digits, no 8th, and no digit or capital letter just before it ("1UH0000001", "XUH0000001": no code).
_UPU_ANY = re.compile(r'U[A-Z]\d{7}(?!\d)')
_UPU_CODE = re.compile(r'(?<![0-9A-Z])U[A-Z]\d{7}(?!\d)')
#: Layout text pads words with long space runs; each run is bounded (no polynomial backtracking).
_SENTENCE = re.compile(r'untuk\s{1,80}mendapat\s{1,80}(\S.{4,400}?)\s{1,80}dan\s{1,80}sebanyak', re.IGNORECASE | re.DOTALL)
_DEGREE = re.compile(r'^(?:IJAZAH\s)?SARJANA\sMUDA\s.+\sDENGAN\sKEPUJIAN(?:\s\(.+\))?$|^DIPLOMA\s', re.IGNORECASE)
#: The programme's own label line ("Program : X"; a scanned letter prints "Program" alone, the value elsewhere).
_PROGRAM_LINE = re.compile(r'^Program\s{0,3}(?::\s{0,3}(.*))?$', re.IGNORECASE)
#: ANY programme label ("Program :", "Nama Program :", "1. Program :", "Kursus :", "Course :", a bare "Program"
#: or "Program Baru"; S1c rounds 1-2): group 1 is its value (None or '' when on the next line). Never "Kod Program".
_ANY_PROGRAM = re.compile(r'^(?:\(?\d{1,2}[.)]?\s{0,3}|\(?[A-Za-z][.)]\s{0,3})?(?:(?:NAMA|BUTIRAN)\s{0,3})?'
                          r'(?:PROGRAM(?:ME)?|KURSUS|BIDANG(?:\s{1,3}PENGAJIAN)?|COURSE|JURUSAN)(?![A-Za-z])'
                          r'(?:[^:]{0,60}:\s{0,3}(.*)|\s{0,3}(' + r'BAHARU|BARU|DITAWARKAN' + r')?)$',
                          re.IGNORECASE)
#: S1c round 2: ';', a full-width colon or a spaced dash after the label words is its colon ("Program - X").
_LABEL_SEP = re.compile(r'^([^:;\-–]{1,60}?)\s{0,3}(?:[;：]|\s[-–](?=\s|$))')
_SEPS = (':', '：', ';', '-', '–')
#: A line that starts a programme name (a scanned letter's programme value line).
_DEGREE_START = re.compile(r'^(?:IJAZAH\s)?SARJANA\sMUDA\b|^DIPLOMA\b', re.IGNORECASE)
#: A range separator between two date parts: a dash or "(se)hingga" with a digit after it.
_RANGE_SEP = re.compile(r'[0-9A-Za-z]\s{0,3}(?:[-–]|\b(?:SE)?HINGGA\b)\s{0,3}\d', re.IGNORECASE)
#: "28-29 September 2024", "28 September - 1 Oktober 2031", "30 Disember 2031 hingga 2 Januari 2032".
_DAY_RANGE = re.compile(r'(?<!\d)(\d{1,2})(?:\s{1,3}(' + _MALAY_MONTH + r'))?(?:\s{1,3}(20\d{2}))?\s{0,3}'
                        r'(?:[-–]|(?:SE)?HINGGA)\s{0,3}(\d{1,2})\s{1,3}(' + _MALAY_MONTH + r')\s{1,3}(20\d{2})',
                        re.IGNORECASE)
#: The END of a range whose start is a whole date ("28 September 2031 (Ahad) - 29 September 2031"): not a
#: second date in the reporting window (S1c review round 1, LOW-E).
_RANGE_END = re.compile(r'^\s{0,3}(?:\([^)\n]{0,20}\)\s{0,3})?(?:[-–]|(?:SE)?HINGGA)\s{0,3}' + _DATE, re.IGNORECASE)
_REPORT_LABEL = re.compile(r'Tarikh\s{1,3}Lapor\s{1,3}Diri', re.IGNORECASE)
#: S1c round 2: a reporting date not yet fixed ("Akan dimaklumkan", "TBA") gives no date, and another label line
#: ("Tarikh Akhir Bayaran : ...") ends the window (a lone ':' value line and the venue line are not labels).
_NO_DATE = re.compile(r'\b(?:AKAN\s{1,3}(?:DI)?(?:MAKLUM(?:KAN)?|UMUM(?:KAN)?|TETAPKAN|BERITAHU|HUBUNGI)|'
                      r'DIMAKLUMKAN\s{1,3}KEMUDIAN|BELUM\s{1,3}(?:DI)?TETAP(?:KAN)?|TBA|TBC|TBD|DITENTUKAN|'
                      r'TO\s{1,3}BE\s{1,3}(?:ANNOUNCED|CONFIRMED|ADVISED))\b', re.IGNORECASE)
_FIELD_LABEL = re.compile(r'^[A-Za-z][A-Za-z/().\'& ]{0,60}?\s{0,40}[:：]')
#: A second date `first_date` misses (S1c round 2): "29 September", "29hb", "29.09.2031", "29-9-31".
_LOOSE_DATE = re.compile(r'(?<!\d)\d{1,2}\s{0,3}(?:HB\.?\s{0,3})?' + _MALAY_MONTH + r'\b|(?<!\d)\d{1,2}\s{0,3}HB\b|'
                         r'(?<![\d.])\d{1,2}[./-]\d{1,2}[./-]\d{2,4}(?![\d.])', re.IGNORECASE)
_VENUE = re.compile(r'^Tempat(?:\s{0,3}/\s{0,3}Kolej|\s{1,3}Lapor\s{1,3}Diri)?\s{0,3}:\s{0,3}(\S.*)$', re.IGNORECASE)
_CAMPUS = re.compile(r'^Kampus\s{0,3}:\s{0,3}(\S.*)$', re.IGNORECASE)
_CAMPUS_LABEL = re.compile(r'^Kampus\s{0,3}:?$', re.IGNORECASE)
_SESI_YEARS = re.compile(r'(20\d{2})\s{0,2}/\s{0,2}(20\d{2})')
#: A STREET word (review round 2): a name-like line holding one is the address under the name, never the
#: name's wrapped tail. Town, state and region words (KOTA, BANDAR, SABAH, LABUAN, PULAU ...) are not here:
#: they are names too ("HAKIM BIN BANDAR"). A line with a digit (house number, postcode) is never name-like.
_STREET_WORD = re.compile(r'\b(?:KG|KAMPUNG|JALAN|JLN|LORONG|LRG|TAMAN|TMN|LOT|PETI|RUMAH|BLOK|'
                          r'PERUMAHAN|LADANG|ESTET)\b', re.IGNORECASE)
#: A name connector: a line holding one is (part of) a name, whatever else it holds (review round 2).
#: '@' (an alias: "MUHAMMAD AMIRUL" / "@ HAKIM") joins a name too (S1c).
_CONNECTOR = re.compile(r'\b(?:BIN|BINTI|ANAK|A\s{0,2}/\s{0,2}[LP]|[SD]\s{0,2}/\s{0,2}O)\b|@', re.IGNORECASE)
#: Where a line under the name may cut a name's tail from its address (S1c rounds 1-2): "HAKIM, KG ...".
_CUT = re.compile(r'[,;\-–—/(]')
#: S1c round 2: a line under the name whose FIRST word is name-like and that later holds a digit or a label colon
#: ("HAKIM SIMPANG 3", "HAKIM 88 000 KOTA") may be the name's tail; it is an address only when that word is here.
_ADDRESS_START = re.compile(r'(?:NO|NOMBOR|LOT|BATU|BT|BLOK|BLOCK|SIMPANG|SIMP|PEKAN|FELDA|FELCRA|KUARTERS|QUARTERS|KUARTER|'
                            r'P\.?\s?O\.?|PO|PETI|KG|KPG|KAMPUNG|KAMPONG|JALAN|JLN|LORONG|LRG|TAMAN|TMN|UNIT|ARAS|TINGKAT|'
                            r'TKT|KM|RUMAH|PERUMAHAN|LADANG|ESTET|MUKIM|BANDAR|KOTA|PUSAT|WISMA|MENARA|PANGSAPURI|APARTMENT|'
                            r'APT|FLAT|PPR|KONDO|KONDOMINIUM|BANGUNAN|BLK|BOX|BAG|LOCKED|BEG|MILE|MILES|SEKSYEN|SEK|SECTION|'
                            r'DESA|ROAD|RD|STREET|ST|LANE|PERSIARAN|LEBUH|LEBUHRAYA|JABATAN|SEKOLAH|SK|SMK)\.?$', re.IGNORECASE)
#: A postcode, whole or split. "WORD 1234 JLN 12" stays an address: one genuine scanned letter's has that shape.
_POSTCODE = re.compile(r'(?<!\d)\d{2}\s?\d{3}(?!\d)')
#: A day number standing alone ("27", "28/" — not inside "2031").
_DAY_NUMBER = re.compile(r'(?<!\d)\d{1,2}(?!\d)')
#: A word or mark that joins two days into a range or a list (S1c, MED-1): on a line ABOVE the date in the
#: reporting-date window ("28 -" / "29 September 2031"), or starting the date's own line ("- 29 September").
_JOIN = r'(?:[-‐‑‒–—―,&]|\b(?:SE)?HINGGA\b|\bSAMPAI\b|\bDAN\b|\bKE\b|\bS\s{0,2}/\s{0,2}D\b)'
_JOINER = re.compile(_JOIN, re.IGNORECASE)
#: Starting the date's line, a few more marks join too ("~ 29 ...", "/ 29 ...", "atau 29 ...", "to 29 ...";
#: S1c review round 1) — not counted above the date, where a venue line may hold them.
_JOINER_START = re.compile(r'^\s{0,3}(?:' + _JOIN + r'|[~/]|\b(?:ATAU|TO|OR)\b)', re.IGNORECASE)
#: Two columns on one layout line (the name must stand alone).
_GAP = re.compile(r'\S\s{3,}\S')
_COLUMNS = re.compile(r'\s{3,}')
#: A certifier's stamp ("SALINAN DISAHKAN BENAR", with its OCR misreads) or an officer's title / office
#: ("PENDAFTAR", "TIMBALAN NAIB CANSELOR", "PEJABAT ...") — never a name.
_STAMP = re.compile(r'\b(?:SALINAN|DISAHKAN|DISALKAN|BENAR|BEHAR|SEBENAR|COP|PEGAWAI|PENGETUA|SAH|PENDAFTAR|'
                    r'CANSELOR|NAIB|TIMBALAN|PEJABAT)\b', re.IGNORECASE)


def is_ums(up: str) -> bool:
    """The UMS offer title anywhere in the (upper-cased) text — `offer_parse._detect`'s fourth family."""
    return bool(_DETECT.search(up or ''))


def _text_lines(text: str) -> list:
    return [ln.strip() for ln in (text or '').splitlines() if ln.strip()]


def _one_space(s: str) -> str:
    return ' '.join((s or '').split())


def _alnum_key(s: str) -> str:
    return re.sub(r'[^A-Z0-9()]', '', (s or '').upper())


def _title(lines):
    """(index, intake) of the one title line; (-1, '') when absent or printed twice differently."""
    hits = [(i, _one_space(m.group(1)).upper()) for i, ln in enumerate(lines) for m in [_TITLE.search(_one_space(ln))] if m]
    intakes = {re.sub(r'\s', '', v) for _i, v in hits}
    if len(intakes) != 1:
        return -1, ''
    i, intake = hits[0]
    return i, re.sub(r'\s{0,2}-\s{0,2}', '-', re.sub(r'\s{0,2}/\s{0,2}', '/', intake))


#: A house word (and its number) ending the words before a cut ("HAKIM NO 12 | JALAN", "UNIT 3"): the
#: address's, not the name's — taken off before the words are judged name-like.
_HOUSE_WORD = re.compile(r'\s*\b(?:NO|NOMBOR|UNIT|ARAS|TINGKAT|TKT|BATU|BT|KM)\.?(?:\s{0,3}\d+[A-Z]?)?$', re.IGNORECASE)


def _may_wrap(raw: str) -> bool:
    """True when the line under the name may hold the rest of it (review rounds 1 and 2): it holds a name
    connector (BIN, BINTI, A/L, A/P, ANAK, S/O, D/O) anywhere, or its FIRST column (a layout line splits at a
    column gap) is name-like with no street word of its own — a street word in a second column never
    clears it ("HAKIM ABDULLAH      JALAN ..."). A label line (the IC), a first column with a digit, or a
    street line ("KG ZANTHARION", "PETI ...") is what follows a whole name. S1c: '@' is a connector, and a
    street line that STARTS with name-like words and then a street word, after a comma or not ("HAKIM, KG
    ZANTHARION", "HAKIM KG ZANTHARION", "HAKIM, JALAN ..."), may hold the name's tail too. A place name
    before a comma with no street word after it ("TAMAN SERI, ...", a town) is an address line (measured:
    the wider rule cost two genuine locks). S1c review round 1 (MED-B): the cut is made at a comma, ';' or
    a dash, at ANY street word (JALAN, LORONG, TAMAN, LOT, PETI ...), or at a postcode (five digits):
    name-like words before a street word or a postcode may be the name's tail (a house word ending them,
    "NO", "UNIT", is the address's own). A cut at ANY digit (a house number: "HAKIM 12 JALAN 5") was
    measured and dropped: one genuine scanned letter's address line starts with a word and a house number."""
    if _CONNECTOR.search(raw or ''):
        return True
    first = _one_space(_COLUMNS.split((raw or '').strip())[0])
    if _name_ok(first) and not _STREET_WORD.search(first):
        return True
    word, whole = re.match(r"([A-Za-z][A-Za-z'.]*)(?=[\s/(,;]|$)", first), _one_space(raw)
    if word and len(word.group(1).strip('.')) >= 2 and not _ADDRESS_START.match(word.group(1)):
        second = whole[word.end():].lstrip(' /(,;')
        if (re.search(r'[:：]', whole) or _POSTCODE.search(whole)
                or (second[:1].isalpha() and re.search(r'\d', second))):
            return True                          # "HAKIM SIMPANG 3", "HAKIM 88 000 ...", "HAKIM No. Kad ... :"
    street, digit = _STREET_WORD.search(first), re.search(r'(?<!\d)\d{5}(?!\d)', first)
    cuts = [m.start() for m in _CUT.finditer(first)] + [m.start() for m in (street, digit) if m]
    for cut in cuts:
        head = _HOUSE_WORD.sub('', first[:cut].strip(' ,;-–—/(')) if cut > 0 else ''
        rest = first[cut:].lstrip(' ,;-–—/(') if cut > 0 else ''
        if (head and _name_ok(head) and not _STREET_WORD.search(head)
                and (_STREET_WORD.match(rest) or rest[:1].isdigit())):
            return True
    return False


def _offer_date_and_name(lines, title_at):
    """(offer date, name) from the head above the title: the name is the line right after the date. Both
    '' when the head prints more than one "Tarikh" line (a stamp's own date: which one is the offer's?).
    The name is '' when the line after it may be its wrapped tail (`_may_wrap`)."""
    dated = [ln for ln in lines[:title_at] if _OFFER_DATE.match(_one_space(ln)) or _OFFER_LABEL.match(_one_space(ln))]
    if len(dated) > 1:
        return '', ''
    for i, ln in enumerate(lines[:title_at]):
        one = _one_space(ln)
        m = _OFFER_DATE.match(one)
        at = i + 1
        if not m and _OFFER_LABEL.match(one) and at < title_at:
            m = _DATE_ONLY.match(_one_space(lines[at]))
            at += 1
        if not m:
            continue
        raw = lines[at] if at < title_at else ''
        name = _one_space(raw)
        after = lines[at + 1] if at + 1 < title_at else ''
        if (_GAP.search(raw) or _blocked(name) or _STAMP.search(name) or not _name_ok(name)
                or _ENDS_MARKER.search(name) or _may_wrap(after)):
            name = ''
        return _one_space(m.group(1)), name
    return '', ''


def _squash(s: str) -> str:
    return re.sub(r'\s', '', s or '')


def name_in_plain(name: str, plain: str, layout: str) -> bool:
    """True when the layout's name stands as its OWN words in the page's PLAIN text layer (S1c review round 1,
    MED-A). pypdf 6's layout joins two text objects drawn under ~2pt apart with no space, so a right-hand word
    can glue onto the name ("ZORBEX A/L QUENTAROSULIT"); the plain layer keeps them apart. The name, spaces
    removed, must sit inside exactly ONE plain line, spaces removed; there each of its words must stand whole
    (a plain "QUENTARO SULIT" is not the name "QUENTAROSULIT"), with no letter glued before it and none
    glued after it — unless what follows is the start of ANOTHER layout line (pypdf 5's plain layer runs the
    name into the address line under it: the layout shows the two apart). No plain layer: False."""
    want, lines = _squash(name), [ln for ln in (plain or '').splitlines() if ln.strip()]
    hits = [_one_space(ln) for ln in lines if want and want in _squash(ln)]
    if len(hits) != 1:
        return False
    starts = {s[:8] for ln in _text_lines(layout) for s in [_squash(_COLUMNS.split(ln.strip())[0])]
              if len(s) >= 2 and _squash(name) not in s}
    pattern = re.compile(r'\s{0,3}'.join(re.escape(w) for w in name.split()))   # no space inside a word
    for m in pattern.finditer(hits[0]):
        before, after = hits[0][max(0, m.start() - 1):m.start()], _squash(hits[0][m.end():])
        glued_after = hits[0][m.end():m.end() + 1].isalpha()
        if before.isalpha() or (glued_after and not any(after.startswith(s) for s in starts)):
            continue
        return True
    return False


def _ic(lines, title_at):
    """The IC printed by the "No. Kad Pengenalan" label (same line, or the next lines holding only a
    colon / the student number). '' unless exactly one, and no OTHER IC in the letter's head (above
    the title; a certifier's stamp lower down may carry the certifier's own IC — never read)."""
    found = set()
    for i, ln in enumerate(lines[:title_at]):
        m = _IC_LABEL.search(ln)
        if not m:
            continue
        rest = m.group(1).strip()
        if _IC_ONLY.match(rest) and len(_decimal_digits(rest)) == 12:
            found.add(_norm_nric(_decimal_digits(rest)))
            continue
        for part in [rest] + lines[i + 1:min(i + 4, title_at)]:
            part = part.strip()
            hit = _IC_RE.search(part)
            if hit:
                found.add(_norm_nric(hit.group(1)))
                break
            if part and part != ':' and not _STUDENT_NO.match(part):
                break
    head = {_decimal_digits(m.group(1)) for ln in lines[:title_at] for m in _IC_RE.finditer(ln)}
    if len(found) != 1 or not head <= {_decimal_digits(next(iter(found)))}:
        return ''
    return next(iter(found))


def _tidy(s: str) -> str:
    return re.sub(r'\s+([)-])', r'\1', re.sub(r'([(-])\s+', r'\1', s))


def _ums_programme(lines, title_at):
    """The programme from its LABEL block (review round 1): the "Program : X" value (X may wrap onto the
    next line), or, in a scanned letter whose "Program" label stands alone, the line(s) that start a
    programme name ("Sarjana Muda ...", "Diploma ...") between the title and the sentence. It must AGREE,
    letter for letter, with the "untuk mendapat <programme> dan sebanyak" sentence, whose own lines are
    never a source. '' when there is no Program label, no value, or ANY value line that disagrees — and
    any "Program : X" line ANYWHERE else in the letter must agree too (review round 2)."""
    joined = '\n'.join(lines)
    found = list(_SENTENCE.finditer(joined))
    said = {_alnum_key(m.group(1)) for m in found}
    if len(said) != 1 or not next(iter(said)):
        return ''
    want = next(iter(said))
    stop = min(joined.count('\n', 0, m.start()) for m in found)     # the label block ends where the sentence starts
    labelled, values = False, set()
    for i in range(title_at + 1, stop):
        one = _one_space(lines[i])
        lab = _PROGRAM_LINE.match(one)
        labelled = labelled or bool(lab)
        value = _one_space(lab.group(1) or '') if lab else (one if _DEGREE_START.match(one) else '')
        if not value:
            continue
        hit = _agreeing(value, lines[i + 1] if i + 1 < stop else '', want)
        if not hit:
            return ''                            # a Program value that is not the sentence's programme
        values.add(_tidy(hit))
    if not _every_label_agrees(lines, want):
        return ''
    values = {v for v in values if _DEGREE.match(v)}
    return next(iter(values)) if labelled and len(values) == 1 else ''


#: Another label of the scanned label block, printed between a bare "Program" label and its value ("Program" /
#: "Kod Program" / ":" / value): skipped, never compared (S1c review round 1).
_OTHER_LABEL = re.compile(r'^(?:KOD|FAKULTI|TEMPOH|SESI|MOD|TARAF|KAMPUS|PUSAT)\b[A-Za-z ]{0,30}:?$', re.IGNORECASE)


def _every_label_agrees(lines, want: str) -> bool:
    """True when every programme label in the letter names the sentence's programme ``want`` (S1c; review round
    1, LOW/MED-D): each COLUMN of each line is checked ("Fakulti : X      Program : Y"; a label column's value
    may be the next column, the layout's padding splitting "Program :      X"), the label may carry a
    number ("1. Program :") or a lead word ("Nama", "Butiran"; "NamaProgram" glued), and Program, Programme,
    Kursus and Bidang Pengajian all count; a label is a label only when a colon follows it (a colon-less
    "Program" is a prose word, or a scanned block's bare label, whose value lines `_ums_programme` already
    checks). A value split over columns may be the first column or all of them. A label whose value is not
    on its line ("Program Baru :") is compared with the next line (a lone ':' line and another label such
    as "Kod Program" skipped; the value may wrap onto one more line); a value that cannot be compared
    there refuses."""
    for i, ln in enumerate(lines):
        cols = _COLUMNS.split(ln.strip())
        for k, col in enumerate(cols):
            lab = (_ANY_PROGRAM.match(_LABEL_SEP.sub(r'\1 :', _one_space(col), count=1))
                   or _ANY_PROGRAM.match(_LABEL_SEP.sub(r'\1 :', _squeeze(_one_space(col)), count=1)))
            if not lab:
                continue
            nxt_sep = k + 1 == len(cols) and lines[i + 1].lstrip().startswith(_SEPS) if i + 1 < len(lines) else False
            if lab.group(1) is None and not (k + 1 < len(cols) and (cols[k + 1].startswith(_SEPS) or lab.group(2))
                                             or (lab.group(2) and nxt_sep)):
                continue                         # no colon: a prose word, or a scanned block's bare label (above)
            after = [_one_space(c).lstrip(''.join(_SEPS) + ' ') for c in cols[k + 1:]
                     if _one_space(c) not in _SEPS]
            nxt_line = lines[i + 1] if i + 1 < len(lines) else ''
            if _one_space(lab.group(1) or ''):
                if not _agreeing(_one_space(lab.group(1)), nxt_line, want):
                    return False
                continue
            if after:
                if not (_agreeing(after[0], nxt_line, want) or _agreeing(' '.join(after), nxt_line, want)):
                    return False
                continue
            rest = [ln2 for ln2 in lines[i + 1:i + 5]
                    if _one_space(ln2) != ':' and not _OTHER_LABEL.match(_one_space(ln2))][:2] + ['', '']
            nxt = _one_space(rest[0]).lstrip(': ')
            if not (_agreeing(nxt, rest[1], want) or _agreeing(_COLUMNS.split(rest[0].strip())[0].lstrip(': '),
                                                                rest[1], want)):
                return False
    return True


def _agreeing(value: str, nxt: str, want: str) -> str:
    """``value`` (or ``value`` + its wrapped next line) when it names the sentence's programme ``want``; ''."""
    nxt = _one_space(nxt)
    return next((c for c in (value, f'{value} {nxt}' if nxt else '') if c and _alnum_key(c) == want), '')


def _range_start(m) -> str:
    """A date range's FIRST day (``m`` a `_DAY_RANGE` match: "28-29 September 2024", "28 September - 1
    Oktober 2031" -> 28 September 2031): its own month, or the end's when it prints only a day; the end's
    year when it prints none. '' unless that first day reads and is not after the end."""
    from .offer_parse import house_date
    from .pathway_engine import parse_reporting_date
    if not m or (m.group(3) and not m.group(2)):
        return ''
    first = f'{m.group(1)} {m.group(2) or m.group(5)} {m.group(3) or m.group(6)}'
    a = parse_reporting_date(house_date(first))
    b = parse_reporting_date(house_date(f'{m.group(4)} {m.group(5)} {m.group(6)}'))
    return first if (a is not None and b is not None and a <= b) else ''


def _reporting_date(lines):
    """The first date in the six lines after the "Tarikh Lapor Diri" label (label, colon and venue lines
    sit between them in a scanned letter); '' when the label is absent or printed twice. A dash or
    "hingga" between two dates is a range: its first day (`_range_start`), or no date at all. The date
    read must start at the line's FIRST day number (review round 2): a day before it means a range or a
    list joined some other way ("28 September — 1 Oktober", "sampai", "s/d", "27, 28 dan 29 September",
    "28 & 29", "28/29") whose first day this rule cannot place, so no date. A range WRAPPED across lines
    ("28 -" / "29 September 2031", the venue line between them or not) would read its LAST day, so a day
    number or a joiner on any part above the date, or a joiner starting the date's line, reads no date (S1c).
    A SECOND whole date anywhere in the window after the one read (a range's own end apart) is a list
    ("Kumpulan A ... / Kumpulan B ...", two dates on one line, a separate date for international students),
    and reads no date (S1c review round 1)."""
    at = [i for i, ln in enumerate(lines) if _REPORT_LABEL.search(ln)]
    if len(at) != 1:
        return ''
    i = at[0]
    tail = _REPORT_LABEL.split(lines[i], maxsplit=1)[1]
    if tail.strip(' \t:：') and not first_date(tail):
        return ''                                # the label's own value is not a date ("TBD"; round 3 blocker 2)
    held = False                                # an earlier part held a day number or a joiner (S1c, MED-1)
    window = [tail] + lines[i + 1:i + 7]
    for k, part in enumerate(window):
        if _NO_DATE.search(part):
            return ''                            # "Akan dimaklumkan kemudian": no date yet (review round 2)
        if k and _FIELD_LABEL.match(part) and not _VENUE.match(_one_space(part)):
            return ''                            # another field's label: its date is not this one (review round 2)
        got = first_date(part)
        if not got:
            held = held or bool(_DAY_NUMBER.search(part) or _JOINER.search(part))
            continue
        if held or _JOINER_START.match(part.lstrip(' \t:')):
            return ''                            # a range or list wrapped across lines: its first day is above
        if _RANGE_SEP.search(part):
            m = _DAY_RANGE.search(part)
            got, start = _range_start(m), (m.start() if m else -1)
        else:
            m = _DMY_RE.search(part) or _NUM_DATE_RE.search(part)
            start = m.start(1) if m else -1
        day = _DAY_NUMBER.search(part)
        rest = _RANGE_END.sub('', part[m.end():], count=1) if m else part
        if any(first_date(later) or _LOOSE_DATE.search(later) for later in [rest] + window[k + 1:]):
            return ''                            # a second date in the window: a list (S1c review round 1, LOW-E)
        return got if day and day.start() == start else ''
    return ''


def _same_line(pattern, lines):
    vals = {_one_space(m.group(1)) for ln in lines for m in [pattern.match(_one_space(ln))] if m}
    return next(iter(vals)) if len(vals) == 1 else ''


def _campus(lines, title_at):
    """The campus from the "Kampus" label below the title: "Kampus : X", or X on the line after a bare
    "Kampus" label (a scanned letter), when X is exactly one UMS campus. Never a line elsewhere (an address
    line "Labuan" is not the campus); '' when the label is absent or names two values."""
    vals = set()
    for i in range(title_at + 1, len(lines)):
        one = _one_space(lines[i])
        m = _CAMPUS.match(one)
        if m:
            vals.add(_one_space(m.group(1)).lower())
        elif _CAMPUS_LABEL.match(one) and i + 1 < len(lines):
            vals.add(_one_space(lines[i + 1]).lower())
    named = {c for c in CAMPUSES for v in vals if v == c.lower()}
    return next(iter(named)) if len(vals) == 1 and len(named) == 1 else ''


def _sane(fields) -> bool:
    """The reporting date falls in the intake's years, and the offer date is not after it."""
    from .pathway_engine import parse_reporting_date
    years = _SESI_YEARS.search(fields['intake'])
    report = parse_reporting_date(fields['reporting_date'])
    if not years or report is None or not (int(years.group(1)) <= report.year <= int(years.group(2))):
        return False
    offered = parse_reporting_date(fields['offer_date']) if fields['offer_date'] else None
    return offered is None or offered <= report


def read_ums(source: str):
    """``(fields, reason)`` for one UMS letter's text: ``fields`` is the read (None before the title
    holds), ``reason`` '' when every required field is read and sane, else why it must not lock."""
    from .offer_parse import house_date
    if len(source or '') > MAX_CHARS or len((source or '').splitlines()) > MAX_LINES:
        return None, 'too_long'                  # more than a page 1 holds: no rule runs (S1c; every line break)
    if status_said(source) or status_said(fold_lookalikes(source)):   # raw OR folded, any spacing (rounds 2-5)
        return None, 'status_letter'
    lines = _text_lines(source)
    title_at, intake = _title(lines)
    if title_at < 0:
        return None, 'no_title'
    if _withdrawn(source, lines[:title_at + 1]):
        return None, 'not_an_offer'
    offer_date, name = _offer_date_and_name(lines, title_at)
    nric = _ic(lines, title_at)
    codes, bounded = _UPU_ANY.findall(source), _UPU_CODE.findall(source)
    code = codes[0] if len(set(codes)) == 1 and len(bounded) == len(codes) else ''   # any unbounded one: none
    fields = {
        'candidate_name': name, 'candidate_nric': nric, 'candidate_nric_source': 'label' if nric else 'none',
        'programme': _ums_programme(lines, title_at), 'programme_code': code,
        'institution': INSTITUTION, 'campus': _campus(lines, title_at), 'stream': '', 'intake': intake,
        'reporting_date': house_date(_reporting_date(lines)), 'reporting_date_label': 'Tarikh Lapor Diri',
        'reporting_venue': _same_line(_VENUE, lines), 'offer_date': offer_date, 'issuer': ISSUER,
    }
    empty = [k for k in ('candidate_name', 'candidate_nric', 'programme', 'intake', 'reporting_date') if not fields[k]]
    if empty:
        return fields, 'empty:' + ','.join(empty)
    if not _sane(fields):
        return fields, 'dates_not_sane'
    return fields, ''
