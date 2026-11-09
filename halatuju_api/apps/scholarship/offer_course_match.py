"""An offer letter → ONE catalogue course, across BOTH catalogues (offer realignment, 2026-10-31).

`offer_pathway.resolve_catalogue_course` is a thin caller of `match_offer_course` below. Until this
sprint the matcher searched only `CourseInstitution` — the post-SPM catalogue (asasi, diploma) — so
no "Sarjana Muda" letter could ever resolve: the 1,112 post-STPM degrees live in `StpmCourse`, one
university each. `_campus_rows` already reads both tables; this follows it.

The contract is unchanged: a course comes back ONLY when exactly one qualifies, because a wrong
`course_id` is worse than none. The TD-332 / TD-150 refusals (`catalogue_levels`) all still apply.

What real letters print, and how each is read (live strings, 2026-10-31):

* **Our own course code** — "Sarjana Muda Ukur Bahan dengan Kepujian - UW6526001" (UNIMAS). A code
  that exists in either catalogue wins, unless the letter names a DIFFERENT institution.
* **UiTM's local code in front** — "BA272 SARJANA MUDA PERNIAGAAN KEWANGAN (KEPUJIAN)": dropped.
* **A faculty run on after the name** — "... (KEPUJIAN) FAKULTI SAINS SUKAN DAN ...": cut there.
* **The catalogue's own decorations** — a trailing " #" (the tokeniser drops it) and a campus
  parenthetical, "Diploma Pembangunan Manusia (Kampus Bintulu, Sarawak)": not part of the name.
* **A hostel in the institution line** — "KOLEJ SRI RAJANG", "KOLEJ KEDIAMAN PERWIRA - DEWAN SULTAN
  IBRAHIM": the university is in the ISSUER. `letter_place` decides when the issuer may stand in for
  the institution line, and every reader and writer of the letter's place calls it.
* **UiTM's campus line** — "UiTM CAWANGAN SABAH, KAMPUS KOTA KINABALU" names the university only by
  its ACRONYM, so an acronym held by ONE institution counts as naming it (never a shared one —
  GIATMARA, IKM — nor one that is a word of another name — MARA, inside "Universiti Teknologi MARA").

The adversarial review of 2026-10-31 tightened the institution test (`_institutions`): a name or a
unique acronym outranks shared words (a UTM letter is never UiTM), a place word alone names nothing
(UiTM Perlis is never UniMAP), a printed code must agree with the printed name, and a multi-campus
course carries a campus only when the letter names exactly one of its campuses.
"""
from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher

from .catalogue_levels import (
    course_levels, names_a_specialisation_the_letter_does_not, private_arm_letter)
from .offer_pathway import (
    PREU_COURSE_SLUG, _ALIRAN_SUFFIX_RE, _campus_rows, _name_aligns, _names_another_institution,
    _norm_inst_name, detect_pathway_type)
from .pathway_engine import distinctive_tokens
from .school_names import school_name_core

#: A UPU programme code, the shape BOTH catalogues key every university course by ("UW6526001").
COURSE_CODE_RE = re.compile(r'(?<![A-Za-z0-9])([A-Za-z]{2}\d{7})(?![A-Za-z0-9])')
#: UiTM's own short programme code in front of the name ("BA272 ", "SR241 ").
_LOCAL_CODE_RE = re.compile(r'^\s*[A-Z]{2,3}\d{3}\s+')
#: A faculty or school line the letter runs on after the programme.
_FACULTY_TAIL_RE = re.compile(r'\s(?:FAKULTI|FACULTY|KULLIYYAH|PUSAT PENGAJIAN)\b.*$', re.I | re.S)
#: The catalogue's campus parenthetical.
_CAMPUS_PAREN_RE = re.compile(r'\((?:kampus|cawangan|campus)\b[^)]*\)', re.I)
_TERTIARY = ('asasi', 'pismp', 'diploma', 'degree')


def letter_programme(programme: str) -> str:
    """The programme as a NAME: our code, UiTM's code, a dangling " - " and a faculty tail removed."""
    s = COURSE_CODE_RE.sub(' ', programme or '')
    s = _FACULTY_TAIL_RE.sub('', _LOCAL_CODE_RE.sub('', s))
    return re.sub(r'[\s\-–—]+$', '', s).strip()


def letter_institution(institution: str, campus: str = '') -> str:
    """The letter's institution LINE as every matcher reads it: ``institution`` with ``campus`` joined on.

    Offer reader S4 (2026-11-02) splits what one field used to hold: ``institution`` = the name only,
    ``campus`` = the campus / branch as printed ("KOLEJ KOMUNITI" + "KANGAR"). The catalogue keeps a
    row PER CAMPUS for polytechnics, KK, IPG, IKBN / IKM / KKTM, so the matcher must see both again or
    a multi-campus pin drops. THE one join, read by ``pathway_engine.student_offer_check`` (which feeds
    ``match_offer_course``, ``letter_place`` and ``CampusReader``) and by any raw reader of the stored
    fields. A campus already inside the name (or the reverse) is not repeated; a pre-S4 read has no
    ``campus`` key, so its line is returned unchanged. Joined with a SPACE, the pre-S4 shape: the
    exact-name test (``_names_another_institution``) keeps punctuation, so ", " turned a real clash
    ("KOLEJ KOMUNITI" + "KANGAR" against a polytechnic course) into "unknown" (review 2026-11-02).
    A bracketed campus "(KANGAR)" loses its brackets — the readers drop a parenthetical whole."""
    inst = ' '.join((institution or '').split())
    camp = ' '.join(re.sub(r'[()]', ' ', campus or '').split())
    pi, pc = (f' {" ".join(re.findall(r"[a-z0-9]+", v.lower()))} ' for v in (inst, camp))
    if not pc.strip() or pc in pi:
        return inst
    if not pi.strip() or pi in pc:
        return camp
    return f'{inst} {camp}'


def programme_line(programme: str, code: str = '') -> str:
    """The letter's programme LINE as the matcher reads it: ``programme`` with ``programme_code`` put
    back where the matcher looks for it — the twin of ``letter_institution``.

    Offer reader S4 (2026-11-02) moves a printed course code OUT of ``programme`` into
    ``programme_code``. ``_printed_course`` reads a UPU code ("UW6526001") from the programme text and
    UNIMAS / UMS letters resolve through it, so the code goes back in the pre-S4 shape: a UPU code
    after " - "; a UiTM local code ("BA272") in front, where ``_LOCAL_CODE_RE`` drops it; any other
    code ("AT06", "DRT") is left out — the matcher never used it and a stray token only blurs the
    name. Each code is looked for INSIDE the field (brackets, spaces or two codes survive: "UW 6526001"
    is not a code, "(UW6526001)" and "BA272 / UW6526001" are); a code already in the text is not
    repeated; a pre-S4 read has no code, so its line is returned unchanged."""
    prog = ' '.join((programme or '').split())
    c = (code or '').upper()
    upu = next(iter(COURSE_CODE_RE.findall(c)), '')
    local = _LOCAL_CODE_RE.match(f'{m.group(0)} ') and m.group(0) if (
        m := re.search(r'(?<![A-Z0-9])[A-Z]{2,3}\d{3}(?![A-Z0-9])', COURSE_CODE_RE.sub(' ', c))) else ''
    text = prog.upper()
    if upu and upu not in COURSE_CODE_RE.findall(text):
        prog = f'{prog} - {upu}' if prog else upu
    if local and not re.search(rf'(?<![A-Z0-9]){local}(?![A-Z0-9])', text) and prog:
        prog = f'{local} {prog}'
    return prog


def catalogue_name(name: str) -> str:
    """A catalogue course name without its campus parenthetical."""
    return ' '.join(_CAMPUS_PAREN_RE.sub(' ', name or '').split())


def letter_place(course_id: str, institution: str, issuer: str = '', rows=None, index=None) -> str:
    """WHERE the letter says the student is going, for ``course_id`` — the institution line, or the
    ISSUER standing in for it. THE one definition: `institution_agreement`,
    `offer_contradicts_course_institution` and the writer `sync_institution_from_catalogue` all read
    the letter through it (the #48 regression was a writer and a reader drifting apart).

    University letters often put a hostel in the institution line ("KOLEJ SRI RAJANG", "Kolej
    Cempaka") and the university in the letterhead. The issuer stands in only when (a) the
    institution line names NO campus of the course, (b) that line does not EXACTLY name another
    catalogue institution — so a polytechnic or a private college against a public course stays a
    clash (#11, #64, #86, #93, #113) — and (c) the issuer itself names a campus of the course."""
    inst, iss = (institution or '').strip(), (issuer or '').strip()
    if not iss or not (course_id or '').strip():
        return inst
    rows = _campus_rows(course_id) if rows is None else rows   # a caller's own read, reused
    if not rows:
        return inst
    index = index if index is not None else catalogue_index()      # one read for the whole call
    line = CampusReader(inst, index) if inst else None
    if inst and (any(line.names(n, a) for n, a in rows) or _names_another_institution('', '', inst)):
        return inst
    reader = CampusReader(iss, index)
    return iss if any(reader.names(n, a) for n, a in rows) else inst


def is_bumiputera_only(course_id: str) -> bool:
    """The COURSE's own Bumiputera-only flag, in whichever catalogue holds it. Never the student's
    answer, which is course-guide only (decisions.md 2026-10-28).

    ⚠ The ONE scholarship-side reader of the course flag, by the owner's realignment rule of
    2026-10-31 (decisions.md). `test_bumiputera_blind` allows this file by path and pins that the
    flag is read here and nowhere else; it is never used to filter what a student is shown."""
    from apps.courses.models import CourseRequirement, StpmRequirement
    cid = (course_id or '').strip()
    return bool(cid) and (
        CourseRequirement.objects.filter(course_id=cid, req_bumiputera=True).exists()
        or StpmRequirement.objects.filter(course_id=cid, req_bumiputera=True).exists())


def match_offer_course(programme: str, institution: str, issuer: str = ''):
    """``{course_id, course_name, institution}`` for the ONE catalogue course the letter names, else
    None. A printed course code first; then the name, at the first of these that holds the course:
    the institutions the LINE names by name or unique acronym; the issuer's, so named (only when the
    line names none so and exactly names no other catalogue institution); the line's by words; the
    issuer's by words. So an explicit letterhead outranks a centre or hostel line whose words merely
    sit inside a university's ("Pusat Persediaan Sains dan Teknologi" is not USM or UTM — round-2
    review 2026-10-31, #349 / #322). ``institution`` is the catalogue's own spelling."""
    if private_arm_letter(programme, f'{institution or ""} {issuer or ""}'):
        return None                                 # the issuer may be the only line naming SATU
    index = catalogue_index()                     # ONE read of the table for this whole call
    coded = _printed_course(programme, institution, issuer, index)
    if coded is not None:
        return coded or None                        # {} = the code names another place: no match
    name = letter_programme(programme)
    pj = distinctive_tokens(name)
    if not pj:
        return None
    ltype = detect_pathway_type(name, '') or detect_pathway_type(name, institution)
    line = _institutions(institution, index)
    borrow = bool((issuer or '').strip()) and not line[0] and not _names_another_institution('', '', institution)
    issued = _institutions(issuer, index) if borrow else ([], [])
    for insts in (line[0], issued[0], line[1], issued[1]):
        hits = _named_courses(pj, ltype, insts)
        if hits:
            return next(iter(hits.values())) if len(hits) == 1 else None
    return None


def pinned_match(programme, institution, issuer=''):
    """``(reason, match)`` — ``''`` and the ONE catalogue course the letter names at ONE campus, at the
    level the letter itself STATES; else ``'unresolved'`` (no one course, a pre-U virtual course, no
    level word on the letter or a course of another level) or ``'campus_unpinned'``. The one test the
    realignment, the offer link and the offer confirm share (round-3 review, 2026-11-01: an old pick
    with a letter reading only "SAINS" at a school had realigned to ``stpm-sains``, and "SAINS SUKAN"
    with no level word to a diploma). Round 4: the level is EXACT — the letter's own level words against
    the course's own ``level`` field — never a family: "SIJIL KEJURUTERAAN MEKANIKAL" is not the
    Diploma, and "DIPLOMA LANJUTAN …" is no catalogue level at all."""
    match = match_offer_course(programme, institution, issuer)
    if not match or match['course_id'] in set(PREU_COURSE_SLUG.values()):
        return 'unresolved', None
    level = letter_level(programme)
    if not level or level != course_level(match['course_id']):
        return 'unresolved', None
    if not (match.get('institution') or '').strip():
        return 'campus_unpinned', None
    return '', match


#: The letter's level words, most specific first, as the catalogue's own ``Course.level`` values
#: (lower-cased): Sijil, Sijil Lanjutan, Diploma, Asasi, Ijazah Sarjana Muda, Pra-U. "Diploma Lanjutan"
#: and a PISMP letter's "Perguruan" are levels no catalogue course carries, so they pin nothing.
_LETTER_LEVELS = (
    ('pismp', ('perguruan', 'pismp')),
    ('pra-u', ('tingkatan enam', 'tingkatan 6', 'stpm', 'matrikulasi', 'matriculation')),
    ('diploma lanjutan', ('diploma lanjutan',)),
    ('sijil lanjutan', ('sijil lanjutan',)),
    ('asasi', ('asasi', 'asasipintar', 'foundation')),
    ('diploma', ('diploma',)),
    ('sijil', ('sijil', 'certificate')),
    ('ijazah sarjana muda', ('ijazah', 'sarjana muda', 'bachelor', 'bacelor', 'degree')),
)


def letter_level(programme):
    """The level the letter STATES, exactly (``_LETTER_LEVELS``), or '' when it states none."""
    text = f' {_plain_words(programme)} '
    for level, words in _LETTER_LEVELS:
        if any(f' {w} ' in text for w in words):
            return level
    return ''


def course_level(course_id):
    """The course's OWN level: its ``Course.level`` lower-cased; an STPM degree is "ijazah sarjana muda"."""
    from apps.courses.models import Course, StpmCourse
    if StpmCourse.objects.filter(course_id=course_id).exists():
        return 'ijazah sarjana muda'
    level = Course.objects.filter(course_id=course_id).values_list('level', flat=True).first()
    return ' '.join((level or '').lower().split())


def _printed_course(programme, institution, issuer, index=None):
    """The course a printed code names: its row, ``{}`` when the letter contradicts it — its printed
    NAME is another course (review 2026-10-31: "Ukur Bahan … - UW6526002" is Kejuruteraan Awam's
    code) or it names another place — or None when no printed code is in either catalogue."""
    pj = distinctive_tokens(letter_programme(programme))
    for code in dict.fromkeys(c.upper() for c in COURSE_CODE_RE.findall(programme or '')):
        row = _course_row(code, institution, issuer, index)
        if row is None:
            continue
        if not _names(pj, row['course_name']):
            return {}
        rows = _campus_rows(code)
        place = letter_place(code, institution, issuer, rows=rows, index=index)
        reader = CampusReader(place, index) if place else None
        if place and not any(reader.names(n, a) for n, a in rows) \
                and _names_another_institution('', '', place):
            return {}
        return row
    return None


def _course_row(course_id, institution, issuer, index=None):
    from apps.courses.models import Course, StpmCourse
    stpm = StpmCourse.objects.filter(course_id=course_id).values_list('course_name', 'university').first()
    if stpm:
        return {'course_id': course_id, 'course_name': stpm[0], 'institution': (stpm[1] or '').strip()}
    name = Course.objects.filter(course_id=course_id).values_list('course', flat=True).first()
    if name is None:
        return None
    campuses = {n.strip() for n, _a in _campus_rows(course_id) if (n or '').strip()}
    if len(campuses) > 1:
        place = letter_place(course_id, institution, issuer, index=index)
        reader = CampusReader(place, index) if place else None
        named = {n.strip() for n, a in _campus_rows(course_id) if place and reader.names(n, a)}
        campuses = named if len(named) == 1 else set()
    return {'course_id': course_id, 'course_name': name,
            'institution': next(iter(campuses)) if len(campuses) == 1 else ''}


#: Words that name a PLACE, not an institution. Several universities' distinctive words are ONLY a
#: state ("Universiti Malaysia Perlis" → {perlis}), so "UiTM CAWANGAN PERLIS" once named UniMAP (review
#: 2026-10-31). A place word alone never names an institution; the states on file are added per call.
_PLACE_WORDS = frozenset({
    'johor', 'kedah', 'kelantan', 'melaka', 'malacca', 'negeri', 'sembilan', 'pahang', 'pulau', 'pinang',
    'penang', 'perak', 'perlis', 'sabah', 'sarawak', 'selangor', 'terengganu', 'kuala', 'lumpur',
    'putrajaya', 'labuan', 'wilayah', 'persekutuan'})

#: Towns (and the place nouns of town names) that host a campus. A campus whose own words are only
#: these is named by its name or acronym, never by the words: "…, UMS Kota Kinabalu" is not
#: Politeknik Kota Kinabalu (#168, 2026-11-01). Written out, not inferred from the table, so a new row
#: can never move a verdict.
_TOWN_WORDS = frozenset({
    'kota', 'bharu', 'bahru', 'kinabalu', 'kuching', 'kuantan', 'arau', 'kangar', 'batu', 'pahat', 'ipoh',
    'shah', 'alam', 'seremban', 'nilai', 'sandakan', 'tawau', 'miri', 'sibu', 'bintulu', 'mukah', 'samarahan',
    'segamat', 'muar', 'kluang', 'mersing', 'pagoh', 'dungun', 'kemaman', 'besut', 'marang', 'machang', 'jeli',
    'tumpat', 'bachok', 'pasir', 'gambang', 'pekan', 'temerloh', 'raub', 'bentong', 'jerantut', 'bangi',
    'serdang', 'skudai', 'sintok', 'alor', 'setar', 'jitra', 'kulim', 'gajah', 'kampar', 'malim', 'tanjong',
    'tanjung', 'jasin', 'merlimau', 'ayer', 'keroh', 'nibong', 'tebal', 'butterworth', 'balik', 'kerian',
    'kajang', 'klang', 'gombak', 'rawang', 'sepang', 'cyberjaya', 'petaling', 'jaya', 'subang', 'puchong',
    'seri', 'sri', 'bandar', 'teluk', 'sungai', 'parit', 'kampus', 'cawangan'})

#: Words that name a TYPE of institution, shared by every campus of that type: they never make a
#: campus "named" (round-4 review: "KOLEJ KOMUNITI", the ministry issuer "JABATAN PENDIDIKAN POLITEKNIK
#: DAN KOLEJ KOMUNITI", "INSTITUT PENDIDIKAN GURU" and "POLITEKNIK METRO KL" each named every campus of
#: their type). The generic list in ``pathway_engine`` already drops kolej / politeknik / institut /
#: universiti / pendidikan / jabatan; these are the type words it keeps.
_TYPE_WORDS = frozenset({
    'komuniti', 'metro', 'guru', 'pendidikan', 'jabatan', 'kemahiran', 'belia', 'negara', 'latihan',
    'perindustrian', 'vokasional', 'premier', 'mara', 'giatmara', 'adtec', 'ikbn', 'ikm', 'kktm', 'ilp',
    'ipg', 'kkom', 'profesional'})

#: Former names and common short forms of catalogue institutions whose own distinctive words are only
#: place words once the town is dropped — the one case the word tier cannot see. Keyed by the
#: catalogue's bracket-stripped, lower-cased name. Explicit on purpose: an alias is a fact, not a guess.
#: "Universiti Malaysia Pahang" was UMPSA's name until 2023 ({pahang} is a state).
_ALIASES = {
    'universiti malaysia pahang al-sultan abdullah': ('Universiti Malaysia Pahang', 'UMP'),
    # Request #66: IIUM's own English name and acronym (the catalogue holds the Malay name, acronym UIAM).
    'universiti islam antarabangsa malaysia': ('International Islamic University Malaysia', 'IIUM'),
}


#: A letter's short TYPE form at the start of a campus line, read as the type it stands for (TD-452,
#: A2.7a): "KK KLANG" is Kolej Komuniti Klang, "METRO KUANTAN" Politeknik METrO Kuantan. Whole word
#: only, so POLYTECHNIC / METROPOLITAN are left alone.
_SHORT_TYPE_RE = re.compile(r'^\s*(KK|POLY|METRO)\.?(?=[\s,]|$)', re.IGNORECASE)
_SHORT_TYPES = {'kk': 'Kolej Komuniti', 'poly': 'Politeknik', 'metro': 'Politeknik METrO'}
#: The types a line can OPEN with that filter the campus type (TD-451): a Kolej Komuniti line never
#: names a polytechnic by words, nor a polytechnic line a community college; other campuses are not filtered.
_LEAD_TYPES = ('kolej komuniti', 'politeknik')


def _plain_words(s: str) -> str:
    """Lower-case words; a bracketed part and an apostrophe dropped ("Mu'adzam" is "muadzam")."""
    return ' '.join(re.findall(r'[a-z0-9]+', re.sub(r"['’]", '', re.sub(r'\([^)]*\)', ' ', (s or '').lower()))))


def _lead_type(words: str) -> str:
    return next((t for t in _LEAD_TYPES if f' {words} '.startswith(f' {t} ')), '')


class CampusReader:
    """Which catalogue institutions does ONE letter line name? THE one definition (2026-11-01), read
    by the matcher (``_institutions``), ``letter_place``, ``institution_agreement`` and
    ``offer_contradicts_course_institution`` (``offer_pathway._refers_to_campus`` delegates here).

    1. **By name or unique acronym** (``named``) — the bracket-stripped name equals the line or sits
       whole inside it ("KOLEJ PERINDU, UNIVERSITI TEKNOLOGI MARA, …"), or an acronym held by ONE row
       and no word of any other row's name is a whole word of the line ("UiTM", "UMS"; never "MARA",
       a word of "Universiti Teknologi MARA", nor GIATMARA / IKM / KKTM, which many rows share). A new
       row can change this tier only by having its WHOLE name in the line, or by sharing an acronym in
       the line (or holding it as a word); a school row such as "SMK Sultan Azlan Shah" cannot.
    2. **By words** (``worded``, the matcher's whole-table search) — only when nothing is named by
       tier 1: the institution's OWN words, two or more, all inside the line, and not only place words
       (states, the towns in ``_TOWN_WORDS``).

    A short type form opening the line ("KK", "POLY", "METRO") is read as the type (``_SHORT_TYPES``),
    and a line that opens with a type names by words only a campus of that type (A2.7a, TD-451 / 452).

    ``names(name, acronym)`` asks it of ONE campus of the course being checked: tier 1 or a listed
    alias (``_ALIASES``) names it; a line that names ANOTHER institution by tier 1 never names it
    (#168: "…, UMS Kota Kinabalu"); else the words, either way round as before, with at least one
    word that is not a place. Judged against that campus only — no other row's words count, so a new
    catalogue row never flips a tick (round-3 review: a whole-table "word nobody else has" rule lost
    UTHM, UMPSA and most polytechnics, and a new school row could flip a verdict)."""

    def __init__(self, hint, index=None):
        self.index = index if index is not None else catalogue_index()
        h = _SHORT_TYPE_RE.sub(lambda m: _SHORT_TYPES[m.group(1).lower()], school_name_core(hint or ''), 1)
        self.ht, self.hn, self.hw = distinctive_tokens(h), _norm_inst_name(h), f' {_plain_words(h)} '
        self.lead = _lead_type(self.hw.strip())
        live = bool(self.ht or self.hn)
        self._named = [(iid, n, a) for iid, n, a, _s in self.index.rows if live and self._tier1(n, a)]
        self.named = [(iid, n) for iid, n, _a in self._named]
        self.worded = [] if self.named or not live else [
            (iid, n) for iid, n, _a, _s in self.index.rows if self._contained(n)]

    def _tier1(self, name, acronym):
        acr, nw = (acronym or '').strip().lower(), _plain_words(name)
        own = 1 if acr in nw.split() else 0
        unique_acr = bool(acr) and acr in self.ht and self.index.acr_rows[acr] == 1 \
            and self.index.word_rows[acr] - own == 0
        return bool((self.hn and _norm_inst_name(name) == self.hn)
                    or (len(nw.split()) > 1 and f' {nw} ' in self.hw) or unique_acr)

    def _contained(self, name):
        """The matcher's word tier: two or more of the institution's own words, all in the line, one
        of them neither a place nor a type word."""
        nt = distinctive_tokens(school_name_core(name or ''))
        return len(nt) > 1 and nt <= self.ht and bool(nt - self.index.place - _TYPE_WORDS) \
            and self._same_type(name)

    def _same_type(self, name):
        """A line that opens with a type (``_LEAD_TYPES``) never names by words a campus that opens with the
        OTHER type; a campus of no listed type (a university behind a "KK <hostel>," line) is not filtered."""
        other = _lead_type(_plain_words(name))
        return not self.lead or not other or other == self.lead

    def _aliased(self, name):
        for alias in _ALIASES.get(_norm_inst_name(name), ()):
            if ' ' not in alias and alias.lower() in self.ht:
                return True
            if ' ' in alias and f' {_plain_words(alias)} ' in self.hw:
                return True
        return False

    def names(self, name, acronym=''):
        """Does the line name this campus? (See the class.)"""
        if not (self.ht or self.hn) or not (name or '').strip():
            return False
        if self._tier1(name, acronym) or self._aliased(name):
            return True
        if self._named:                               # the line names an institution outright:
            nn, acr = _norm_inst_name(name), (acronym or '').strip().lower()   # this one, or another
            return any(_norm_inst_name(n) == nn or (acr and (a or '').strip().lower() == acr)
                       for _i, n, a in self._named)
        nt = distinctive_tokens(school_name_core(name))
        if not self._same_type(name):
            return False                              # TD-451: "KK BAGAN DATUK" is no polytechnic
        if not (self.ht - self.index.place - _TYPE_WORDS) or not _name_aligns(self.ht, nt):
            return False                              # a line of only place / type words names no campus
        return bool((nt if nt <= self.ht else self.ht) - self.index.place - _TYPE_WORDS)


class _Index:
    def __init__(self, rows):
        self.rows = rows
        self.place = _PLACE_WORDS | _TOWN_WORDS | {w for *_x, st in rows for w in _plain_words(st).split()}
        self.acr_rows, self.word_rows = Counter(), Counter()
        for _iid, name, acr, _st in rows:
            self.acr_rows[(acr or '').strip().lower()] += 1
            self.word_rows.update(set(_plain_words(name).split()))


def catalogue_index():
    """ONE read of the ``Institution`` table for every naming test of a call (see ``CampusReader``)."""
    from apps.courses.models import Institution
    return _Index(list(Institution.objects.values_list('institution_id', 'institution_name', 'acronym', 'state')))


def _institutions(hint, index=None):
    """``(named, worded)`` — the [(institution_id, name)] the hint names, by ``CampusReader``'s tiers."""
    reader = CampusReader(hint, index)
    return reader.named, reader.worded


def _named_courses(pj, ltype, institutions):
    """{course_id: row} for every course at ``institutions`` whose name the letter's words name.

    OUTVOTED (2026-11-02, #337): the letter "LINGUSTIK TERAPAN DAN PENTADBIRAN PERNIAGAAN" (its own
    typo) named plain "Pentadbiran Perniagaan", while "Linguistik Terapan dan Pentadbiran Perniagaan"
    was missed by one letter. See ``_outvoted``. Then the hits come back with no row (``None``), so
    the caller resolves nothing and searches no lower tier: a wrong ``course_id`` is worse than none."""
    from apps.courses.models import CourseInstitution, StpmCourse
    if not institutions:
        return {}
    ids = [iid for iid, _n in institutions]
    tertiary = ltype in _TERTIARY
    uniq, campuses, others = {}, {}, []
    offers = CourseInstitution.objects.filter(institution_id__in=ids)
    if tertiary:
        offers = offers.exclude(course_id__in=PREU_COURSE_SLUG.values())
    for off in offers.select_related('course', 'institution'):
        if tertiary and (fams := course_levels(off.course)) and ltype not in fams:
            continue
        if _names(pj, off.course.course):
            uniq[off.course.course_id] = {'course_id': off.course.course_id,
                                          'course_name': off.course.course, 'institution': ''}
            campuses.setdefault(off.course.course_id, set()).add(off.institution.institution_name)
        else:
            others.append(off.course.course)
    for cid, named in campuses.items():          # a campus only when the letter names exactly ONE
        uniq[cid]['institution'] = next(iter(named)) if len(named) == 1 else ''
    if ltype in ('degree', ''):                    # StpmCourse holds degrees only
        for cid, cname, uni in StpmCourse.objects.filter(institution_id__in=ids).values_list(
                'course_id', 'course_name', 'university'):
            if _names(pj, cname):
                uniq[cid] = {'course_id': cid, 'course_name': cname, 'institution': (uni or '').strip()}
            else:
                others.append(cname)
    if _outvoted(pj, [r['course_name'] for r in uniq.values()], others):
        return dict.fromkeys(uniq)                 # outvoted: named, but by no one course
    return uniq


def _outvoted(pj, named, others):
    """Is a named course only a SUBSET match that another course here explains better? Either
    (a) a course not named shares MORE of the letter's words, or (b) a letter word the named course
    lacks is a near-spelling of a word another course has ("LINGUSTIK" / "linguistik", "PEMASARRAN" /
    "pemasaran" — review 2026-11-02: a typo in the ONE word that tells two courses apart ties on
    (a)). A course the letter's words align with but that names a specialisation the letter does
    not state (TD-150) counts for neither: "Sains Komputer dengan Kepujian" is not outvoted by
    "Sains Komputer (Rangkaian Komputer) dengan Kepujian"."""
    rest = [t for t in (distinctive_tokens(catalogue_name(o)) for o in others) if not _name_aligns(pj, t)]
    for name in named:
        nt = distinctive_tokens(catalogue_name(name))
        extra = pj - nt
        if not extra:
            continue
        if any(len(pj & t) > len(pj & nt) for t in rest):
            return True
        words = {w for t in rest for w in t - nt - pj}
        if any(_near_spelling(e, w) for e in extra for w in words):
            return True
    return False


def _near_spelling(a, b):
    """One word a typo of the other: both 5+ letters, and ONE letter added, dropped or changed, or at
    least 85% alike (``difflib``). The one-edit test is for short words, where a single misread letter
    scores under 85% ("GUNAAM" / "gunaan", "ISIAM" / "islam" — round-2 review, 2026-11-02). Refusing
    is the safe side: the letter goes to a human, never to a wrong course."""
    if min(len(a), len(b)) < 5:
        return False
    return _one_edit(a, b) or SequenceMatcher(None, a, b).ratio() >= 0.85


def _one_edit(a, b):
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    short, long_ = sorted((a, b), key=len)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


def _names(pj, course_name):
    """Do the letter's words name this catalogue course? Aligned, and not a specialisation the
    letter never states (TD-150); the PISMP aliran suffix is not a specialisation."""
    base = catalogue_name(course_name)
    return (_name_aligns(pj, distinctive_tokens(base))
            and not names_a_specialisation_the_letter_does_not(
                pj, distinctive_tokens(_ALIRAN_SUFFIX_RE.sub('', base))))
