"""The agency-letterhead lift's CLOSED-WORLD condition 4 (offer exact-read S6, decisions.md S6 item 9; owner ruling
2026-11-04: app 329 green; the lead's rulings of the same day).

A TVET offer on an agency's own letterhead (`offer_rulings._agency_lift`) lifts only when every body line, after its
ALLOWED spans are taken out, holds NO organisation word at all — wherever it sits, a name before or after it alike.

  Allowed spans: the matched institute's closed-list names (`offer_rulings._INSTITUTE_KEY`) followed only by that
  institute family's catalogued campus / place words; the letterhead agency and its umbrella names
  (`offer_rulings._AGENCIES`); the spelt-out TVET sector name; a field label (PUSAT PENGAJIAN / PUSAT LATIHAN /
  TEMPAT / LOKASI / INSTITUSI, an optional bracket) when the allowed institute follows it on the line; a line made
  ONLY of label words (a table's label column); a closed-list bank line; the addressee block; a campus residence
  ("Kolej Kediaman", TD-495) when no name follows it.
  The only exception: a bare generic noun in LOWERCASE raw OCR followed by a function word or punctuation
  ("pihak institut berhak", "di institusi/kolej"). At a line's end, the next line's first word is read: a
  title-case word, or an all-caps one that is no function word, is a name. A glued "KolejMercu" is split first.
  Another agency's full name, an operator phrase ("dikendalikan oleh", "in collaboration with") anywhere, or a
  name line on the letterhead below the agency = no lift. The agency must stand first on the letterhead
  (`_agency_first`); WAKIL / EJEN / AGEN anywhere = no lift.

The campus words come from the API's own TVET catalogue — `apps.courses.tvet_institutions.HELD` and the UP_TVET
catalogue snapshots `data/tvet/uptvet_F1_source.json` / `uptvet_F2_source.json` (Bumi coverage F1 / F2), by
provider family (`apps.courses.tvet_families.family_of`) — plus the states and KAMPUS / CAWANGAN. Pure.
KNOWN GAP (TD-493): a private name with NO organisation word ("Mercu Engineering Works") is not caught.
"""
import functools
import json
import os
import re

from .offer_reading import (_COMPANY_HEAD, _PRIVATE_BODIES, _POSTCODE, _SB, _TIE_UP, _TVET_NAMES, _TVET_SPELT,
                            _bank_line, _in_addressee_block, _is_contact, _letterhead_lines, _page, glued_org,
                            is_org_token)
from .offer_rulings import _ADDRESS_LINE, _AGENCIES, _FUNCTION_WORDS, _GOVERNMENT_LINE, _INSTITUTE_KEY, _WORD

#: Organisation words: ONE shared list with the letterhead tests (`offer_reading.is_org_token`, round 11 H1).
is_org_word = is_org_token
#: The institution nouns a glued token is split on ("KolejMercu" -> "Kolej" "Mercu").
_GLUE_NOUNS = ('INSTITUSI', 'INSTITUTE', 'INSTITUT', 'UNIVERSITI', 'UNIVERSITY', 'POLITEKNIK', 'POLYTECHNIC',
               'COLLEGE', 'AKADEMI', 'ACADEMY', 'SEKOLAH', 'MAKTAB', 'KOLEJ')
#: The agencies' one-word names: organisation words unless the letterhead agency's own.
AGENCY_TOKENS = {'tvet_mara': {'MARA', 'TVETMARA', 'IPMA'}, 'tvet_belia_sukan': {'KBS', 'ILKBS'},
                 'tvet_jtm': {'JTM', 'ILJTM', 'KSM'}}
OTHER_AGENCY_TOKENS = frozenset({'JPK', 'KPT', 'KPM'})
#: (3) The agencies' FULL names: organisation names unless the letterhead agency's own (or its parent).
AGENCY_FULL_NAMES = {'tvet_mara': (' MAJLIS AMANAH RAKYAT ',),
                     'tvet_belia_sukan': (' KEMENTERIAN BELIA DAN SUKAN ',),
                     'tvet_jtm': (' JABATAN TENAGA MANUSIA ', ' KEMENTERIAN SUMBER MANUSIA ')}
OTHER_FULL_NAMES = (' JABATAN PEMBANGUNAN KEMAHIRAN ', ' KEMENTERIAN PENDIDIKAN TINGGI ', ' KEMENTERIAN PENDIDIKAN ')
#: (4) An operator / partner phrase anywhere on the page.
OPERATOR_PHRASES = (' DIKENDALIKAN OLEH ', ' DIKELOLAKAN OLEH ', ' DIURUSKAN OLEH ', ' DENGAN KERJASAMA ',
                    ' KERJASAMA DENGAN ', ' OPERATED BY ', ' MANAGED BY ', ' IN COLLABORATION WITH ',
                    ' IN PARTNERSHIP WITH ', ' RAKAN STRATEGIK ')
#: TD-495: a campus residence named with an institution noun; taken out as an allowed span when no name follows it.
FACILITIES = ('KOLEJ KEDIAMAN',)
#: (1) The words a table's label column is made of, and its enumerators.
LABEL_WORDS = frozenset({'TEMPAT', 'PUSAT', 'LOKASI', 'INSTITUSI', 'PENGAJIAN', 'LATIHAN', 'PROGRAM', 'TEMPOH'})
_ENUMERATOR = re.compile(r'^(?:[A-Z]|[IVX]{1,4}|\d{1,2})$')
#: The words any institute's campus may give: the states, KAMPUS / CAWANGAN.
STATE_AND_CAMPUS = frozenset({'KAMPUS', 'CAWANGAN', 'CAMPUS', 'BRANCH', 'JOHOR', 'KEDAH', 'KELANTAN', 'MELAKA',
                              'NEGERI', 'SEMBILAN', 'PAHANG', 'PERAK', 'PERLIS', 'PULAU', 'PINANG', 'PENANG', 'SABAH',
                              'SARAWAK', 'SELANGOR', 'TERENGGANU', 'KUALA', 'LUMPUR', 'LABUAN', 'PUTRAJAYA', 'WILAYAH',
                              'PERSEKUTUAN', 'WP'})
#: A field label that introduces the institute ("Pusat Pengajian : IKBN Miri", "Tempat (IKBN/IKTBN) : ...").
_LABEL_BEFORE = re.compile(r'(?i)(?:PUSAT\s+PENGAJIAN|PUSAT\s+LATIHAN|PUSAT|TEMPAT|LOKASI|INSTITUSI)'
                           r'\s*(?:\([^)]*\))?\s*[:\-]?\s*\(?\s*$')     # ... or the bracket opening on the institute
_AGENT_WORDS = re.compile(r' (?:WAKIL|EJEN|AGEN)(?= )')
_ADDRESS_WORDS = re.compile(r' (?:WISMA|MENARA|JALAN|BANGUNAN)(?= )')
#: (6) The letterhead lines below the agency: address / contact / web / division lines only.
_MORE_ADDRESS = re.compile(r' (?:WISMA|MENARA|ARAS|TINGKAT|BLOK|BANGUNAN|KOMPLEKS|PRESINT|PERSIARAN|PUSAT '
                           r'PENTADBIRAN|KERAJAAN PERSEKUTUAN|LEVEL|FLOOR|KAWASAN|PERINDUSTRIAN|INDUSTRIAL|'
                           r'SEKSYEN)(?= )')
#: What a reference / date line leaves on the letterhead ("Tarikh :" before its date): a label, no name.
_REF_DATE_LABELS = frozenset({'TARIKH', 'RUJ', 'RUJUKAN', 'KAMI', 'TUAN', 'DATE', 'REF', 'NO', 'OUR', 'YOUR', 'FAIL'})
_DIVISION_START = re.compile(r'^ (?:BAHAGIAN|UNIT|PEJABAT|IBU PEJABAT)(?= )')
_FAMILY_KEY = {'iljtm': 'tvet_jtm', 'ilkbs': 'tvet_belia_sukan', 'mara': 'tvet_mara'}
_CATALOGUE_FILES = ('uptvet_F1_source.json', 'uptvet_F2_source.json')
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'data', 'tvet')


def _fold_words(text):
    return re.sub(r'[^A-Z0-9]+', ' ', (text or '').upper()).split()


@functools.lru_cache(maxsize=1)
def catalogue_places():
    """{closed-list key: the place words of that family's catalogued campuses} — from the API's TVET catalogue
    (`apps.courses.tvet_institutions.HELD` + the UP_TVET catalogue snapshots), organisation words taken out."""
    from apps.courses.tvet_families import family_of
    from apps.courses.tvet_institutions import HELD
    names = [name for name, _sub, _state in HELD.values()]
    for fname in _CATALOGUE_FILES:
        try:
            with open(os.path.join(_DATA_DIR, fname), encoding='utf-8') as fh:
                names += [row.get('institution', '') for row in (json.load(fh).get('catalogue') or {}).values()]
        except (OSError, ValueError):
            continue
    out = {key: set() for key in _FAMILY_KEY.values()}
    for name in names:
        key = _FAMILY_KEY.get(family_of(name))
        if key:
            out[key].update(_fold_words(name))
    return {key: frozenset(w for w in words if not is_org_word(w)) for key, words in out.items()}


@functools.lru_cache(maxsize=1)
def catalogue_campuses():
    """{closed-list key: the campus place PHRASES of that family's catalogued campuses ("PETALING JAYA", "MIRI")} —
    the word runs of each catalogue name that are no institute / agency / organisation word."""
    from apps.courses.tvet_families import family_of
    from apps.courses.tvet_institutions import HELD
    names = [name for name, _sub, _state in HELD.values()]
    for fname in _CATALOGUE_FILES:
        try:
            with open(os.path.join(_DATA_DIR, fname), encoding='utf-8') as fh:
                names += [row.get('institution', '') for row in (json.load(fh).get('catalogue') or {}).values()]
        except (OSError, ValueError):
            continue
    family_words = {w for phrase in _TVET_NAMES for w in phrase.split()} | {
        w for phrases in _AGENCIES.values() for phrase in phrases for w in phrase.split()} | {
        w for ts in AGENCY_TOKENS.values() for w in ts} | {'KAMPUS', 'CAWANGAN', 'GIATMARA', 'JTM', 'MJII', 'TECH'}
    out = {key: set() for key in _FAMILY_KEY.values()}
    for name in names:
        key = _FAMILY_KEY.get(family_of(name))
        if not key:
            continue
        run = []
        for w in _fold_words(name) + ['']:
            if w and w not in family_words and not is_org_word(w) and not w.isdigit():
                run.append(w)
            elif run:
                out[key].add(' '.join(run))
                run = []
    return {key: frozenset(p) for key, p in out.items()}


def _campus_end(up, k, covered, key, places):
    """(e) Past an allowed span at token `k`: its catalogued campus phrases, state / campus words and the address
    words of OTHER lines; returns where they end."""
    phrases = sorted(catalogue_campuses().get(key, ()), key=lambda p: -len(p.split()))
    while k < len(up) and not covered[k]:
        hit = next((p for p in phrases if up[k:k + len(p.split())] == p.split()), None)
        if hit:
            n = len(hit.split())
        elif up[k] in STATE_AND_CAMPUS or up[k] in places:
            n = 1
        else:
            break
        for x in range(k, k + n):
            covered[x] = True
        k += n
    return k


def _is_fragment(ln, echoes=frozenset()) -> bool:
    """(2) + round 11 (M7, the lead's ruling): a one-token fragment that is JUNK (no alphabetic run of four or more
    letters) or an OCR ECHO of an address word below (a 5+ letter substring shared with one of `echoes`) — and no
    organisation word (glued or not), no company / private body / tie-up word."""
    words = ln.split()
    junk = not re.search(r'[A-Z]{4,}', ln)
    return (len(words) == 1 and (junk or _echoes(words[0], echoes)) and not glued_org(words[0])
            and not is_org_word(words[0]) and not any(c in ln for c in _COMPANY_HEAD)
            and not _SB.search(ln) and not any(b in ln for b in _PRIVATE_BODIES) and not any(t in ln for t in _TIE_UP))


def _echoes(word, echoes) -> bool:
    """`word` shares a substring of five or more letters with one of `echoes` (a broken town name)."""
    return any(word[i:i + 5] in e for e in echoes for i in range(len(word) - 4))


def _head_address(lines, key) -> list:
    """Round 12 (M1 / M3): the letterhead's OWN address lines — after the agency line, through its first postcode."""
    head = _letterhead_lines(lines)
    at = next((i for i, ln in enumerate(head) if any(n in ln for n in _AGENCIES[key])), None)
    out = []
    for ln in head[at + 1:] if at is not None else []:
        out.append(ln)
        if _POSTCODE.search(ln):
            break
    return out


def _addressee_block(lines) -> list:
    """The ADDRESSEE lines: a KEPADA line's block on the letterhead through its postcode, and every block between a
    reference / date line and the next title line with the candidate's name / IC line between them (a two-letter
    scan has one per letter), through its postcode."""
    from .offer_reading import _CONFIRM_TITLES, _DATE_RE, _REFERENCE, _TITLE, _is_person_line
    out, head = [], _letterhead_lines(lines)
    at = next((i for i, ln in enumerate(head) if ' KEPADA ' in ln), None)
    for ln in head[at + 1:at + 6] if at is not None else []:
        out.append(ln)
        if _POSTCODE.search(ln):
            break
    titles = [i for i, ln in enumerate(lines) if any(t in ln for t in _TITLE + _CONFIRM_TITLES)]
    for i, ln in enumerate(lines):
        if any(r in ln for r in _REFERENCE) or _DATE_RE.search(ln):
            stop = next((t for t in titles if t > i), None)
            if stop is not None and stop - i <= 6 and any(_is_person_line(x) for x in lines[i + 1:stop]):
                for x in lines[i + 1:stop]:
                    out.append(x)
                    if _POSTCODE.search(x):
                        break
    return out


def _echo_words(lines, key) -> frozenset:
    """The words a fragment may echo: the letterhead's own address and the addressee block(s) (5+ letters)."""
    def words(block):
        return frozenset(w for ln in block for w in ln.split() if len(w) >= 5 and w.isalpha())
    return words(_head_address(lines, key)) | words(_addressee_block(lines))


def _agency_first(lines, key) -> bool:
    """(f) The letterhead agency stands first on the letterhead: above its line only crest / government lines, junk
    lines (no alphabetic word of 3+ letters), up to three one-token junk / address-echo fragments, and a KEPADA
    line with its address
    block — never inside an address (Wisma / Menara / Jalan / Bangunan); no WAKIL / EJEN / AGEN on the page; and
    (6) below it, up to the first postcode line, only address / contact / web / division / agency lines."""
    if _AGENT_WORDS.search(_page(lines)):
        return False
    head, i, fragments = _letterhead_lines(lines), 0, 0
    echoes = _echo_words(lines, key)
    if any(glued_org(w, _AGENCIES[key]) for ln in head for w in ln.split()):
        return False                # round 11 (M3): a glued organisation word on the letterhead
    while i < len(head):
        ln = head[i]
        if any(n in ln for n in _AGENCIES[key]) and not _ADDRESS_WORDS.search(ln):
            return _below_agency_ok(head[i + 1:], key)
        if _GOVERNMENT_LINE.search(ln) or not re.search(r'[A-Z]{3,}', ln):
            i += 1
            continue
        if ' KEPADA ' in ln:            # the addressee block, read first by OCR: up to its postcode line
            j = i + 1
            while j < min(len(head), i + 5) and not any(n in head[j] for n in _AGENCIES[key]):
                if any(is_org_word(w) for w in head[j].split()):
                    return False
                if _POSTCODE.search(head[j]):
                    j += 1
                    break
                j += 1
            i = j
            continue
        if _is_fragment(ln, echoes) and fragments < 3:   # junk, or an echo of the letterhead / addressee address
            fragments += 1
            i += 1
            continue
        return False
    return False


def _below_agency_ok(rest, key) -> bool:
    """(6) The letterhead lines below the agency line, up to the first postcode line."""
    places = catalogue_places().get(key, frozenset()) | STATE_AND_CAMPUS
    for ln in rest:
        ok = (_ADDRESS_LINE.search(ln) or _MORE_ADDRESS.search(ln) or _is_contact(ln) or _DIVISION_START.search(ln)
              or any(n in ln for n in _AGENCIES[key]) or all(w in places for w in ln.split())
              or not re.search(r'[A-Z]{3,}', ln) or all(w in _REF_DATE_LABELS for w in ln.split()))
        if not ok:
            return False                # another name line ("MERCU JAYA") on the letterhead
        if _POSTCODE.search(ln):
            break
    return True


def _bracket_ok(bracket, key) -> bool:
    """Round 11 (M1): a label's bracket may hold only label words or the matched family's closed-list acronyms."""
    acronyms = {w for n in _INSTITUTE_KEY[key] + _AGENCIES[key] for w in n.split() if len(w) <= 6}
    return all(w in LABEL_WORDS or w in acronyms for w in _fold_words(bracket))


def _tokens(raw):
    """The raw line's words with their spans, OCR 0 / 1 read as O / I (case kept); (5) a glued institution noun is
    split off ("KolejMercu", "KOLEJMERCU")."""
    out = []
    for word, start, end in _letters_joined(raw or ''):
        if not word.isdigit():                         # round 14: a number stays a number ("IKM 1 Kuantan")
            word = word.replace('0', 'O').replace('1', 'I')
        up = word.upper()
        noun = next((n for n in _GLUE_NOUNS if up.startswith(n) and len(up) > len(n)), '')
        rest = word[len(noun):]
        if noun and not is_org_word(up) and (rest[:1].isupper() and not word.isupper()
                                             or word.isupper() and len(rest) >= 3 and rest.isalpha()
                                             and rest != 'NYA'):
            out += [(word[:len(noun)], start, start + len(noun)), (rest, start + len(noun), end)]
        else:
            out.append((word, start, end))
    return out


def _letters_joined(raw):
    """The raw words with their spans, a run of three or more single spaced letters read as one word ("K O L E J"
    -> "KOLEJ", round 11)."""
    words = [(m.group(0), m.start(), m.end()) for m in _WORD.finditer(raw)]
    out, i = [], 0
    while i < len(words):
        j = i
        while j < len(words) and len(words[j][0]) == 1 and words[j][0].isalpha():
            j += 1
        if j - i >= 3:
            out.append((''.join(w for w, _s, _e in words[i:j]), words[i][1], words[j - 1][2]))
            i = j
        else:
            out.append(words[i])
            i += 1
    return out


def _cover(up, phrases, covered):
    """Mark every token run equal to one of `phrases`; returns the (start, end) token runs marked."""
    runs = []
    for phrase in sorted(phrases, key=len, reverse=True):
        p = phrase.split()
        for j in range(len(up) - len(p) + 1):
            if up[j:j + len(p)] == p and not any(covered[j:j + len(p)]):
                covered[j:j + len(p)] = [True] * len(p)
                runs.append((j, j + len(p)))
    return runs


def _names_word(tok) -> bool:
    """(d) A next-line word that names: title-case, or all-caps and no function word."""
    word = tok[0]
    return word.upper() not in _FUNCTION_WORDS and (word.istitle() or word.isupper())


def _label_only(ln) -> bool:
    """(1) A line made only of label words and enumerators (a table's label column, its value on a later line)."""
    words = ln.split()
    return bool(words) and all(w in LABEL_WORDS or _ENUMERATOR.match(w) for w in words) and any(
        w in LABEL_WORDS for w in words)


def closed_world_blocker(lines, raws, head_n, key) -> str:
    """Condition 4: the first token that names another organisation in the body, or '' when none (module note)."""
    page = _page(lines)
    for phrase in OPERATOR_PHRASES:
        if phrase in page:
            return f'operator phrase:{phrase.rstrip()}'                     # (4)
    org_extra = OTHER_AGENCY_TOKENS | {t for k, ts in AGENCY_TOKENS.items() if k != key for t in ts}
    other_full = OTHER_FULL_NAMES + tuple(n for k, ns in AGENCY_FULL_NAMES.items() if k != key for n in ns)
    umbrella = tuple(n for n in _AGENCIES[key] if any(is_org_word(w) for w in n.split()))
    head_places = {w for ln in _head_address(lines, key) for w in ln.split() if not is_org_word(w)}
    for i in range(head_n, len(lines)):
        if (_bank_line(lines[i]) or _in_addressee_block(lines, i) or i >= len(raws)
                or _label_only(lines[i])):
            continue
        raw, toks = raws[i], _tokens(raws[i])
        up = [t.upper() for t, _s, _e in toks]
        places = head_places                                   # round 12 (M3): the letterhead's own address
        covered = [False] * len(toks)
        _cover(up, _TVET_SPELT, covered)                       # the sector's name, spelt out
        for start, end in _cover(up, _INSTITUTE_KEY[key], covered):
            off = max(0, toks[start][1] - 200)                    # round 14 (perf): a label sits just before
            label = _LABEL_BEFORE.search(raw[off:toks[start][1]]) if start else None
            if label:                                             # its field label ("Pusat Pengajian : IKBN …")
                br = re.search(r'\(([^)]*)\)', label.group(0))
                bad = br and not _bracket_ok(br.group(1), key)
                l0 = off + label.start()
                b0, b1 = (l0 + br.start(), l0 + br.end()) if br else (0, 0)
                for k in range(start):
                    if toks[k][1] >= l0 and not (bad and b0 <= toks[k][1] < b1):
                        covered[k] = True                         # round 11 (M1): an odd bracket stays tested
            k = _campus_end(up, end, covered, key, places)
            while k < len(toks) and not covered[k] and up[k] in _FUNCTION_WORDS:
                k += 1                                            # round 12: "IKM Kuantan Sila Mercu Jaya"
            if k < len(toks) and not covered[k] and toks[k][0][:1].isupper():
                return f'after the institute: {up[k]}'            # (e) "IKM Mercu"
        for _start, end in _cover(up, FACILITIES, covered):          # TD-495: a residence, no organisation
            if (end < len(toks) and not covered[end] and toks[end][0][:1].isupper() and up[end] not in _FUNCTION_WORDS
                    and up[end] not in places and up[end] not in _any_place()):
                return f'after a residence: {up[end]}'            # "Kolej Kediaman Mercu Jaya" may be a company's
        for start, end in _cover(up, _AGENCIES[key], covered):
            if any(' '.join(up[start:end]) == n.strip() for n in umbrella):     # round 11 (M2): after an umbrella
                k = _campus_end(up, end, covered, key, places)
                if k < len(toks) and not covered[k] and toks[k][0][:1].isupper() and up[k] not in _FUNCTION_WORDS:
                    return f'after the umbrella: {up[k]}'
        for start, _end in _cover(up, other_full, covered):
            return f"another agency: {' '.join(up[start:_end])}"  # (3)
        allowed_names = _INSTITUTE_KEY[key] + _AGENCIES[key]
        for j, w in enumerate(up):
            if not covered[j] and w not in places and glued_org(w, allowed_names):
                return f'glued organisation word: {len(w)} letters'   # round 12 (H1) "MercuAcademy"
        nxt_toks = _tokens(raws[i + 1]) if i + 1 < len(raws) else []
        for j, w in enumerate(up):
            if covered[j] or not (is_org_word(w) or w in org_extra):
                continue
            named_after = (j + 1 < len(toks) and not covered[j + 1] and toks[j + 1][0][:1].isupper()
                           and up[j + 1] not in _FUNCTION_WORDS)
            if w in WEAK_SUFFIXES and j + 1 == len(toks) and not raw[toks[j][2]:].strip():
                named_after = _name_beside(lines, raws, i + 1, key, places, above=False)   # TD-494 (c)
            if (w in WEAK_SUFFIXES and not named_after and _after_descriptor(
                    up, j, toks, covered, i - 1 >= head_n and _name_beside(lines, raws, i - 1, key, places, True))):
                continue                                          # "& Pendidikan Global" (a slogan), never a name
            if _numbered(j, toks, up, covered, places) and not _named_before(j, toks, up, covered, raw, places):
                continue                                          # round 14: "KOLEJ 1", "PUSAT 1013", "Kampus 2"
            if toks[j][0].islower() and is_org_word(w):          # (c) a bare generic noun, lowercase
                # round 11 (M4): only when no name follows within three tokens, across punctuation / the line end
                ahead = [(t, covered[x]) for x, t in enumerate(toks) if x > j][:3]
                ahead += [(t, False) for t in nxt_toks][:max(0, 3 - len(ahead))]
                if not any(not cov and t[0].upper() not in _FUNCTION_WORDS and not is_org_word(t[0].upper())
                           and (t[0].istitle() or t[0].isupper()) for t, cov in ahead):
                    continue
            return f'organisation word: {w}'
    return ''


def _numbered(j, toks, up, covered, places) -> bool:
    """Round 14 (Low): a noun followed by a NUMBER is a room / block / college number ("Kolej 13", "PUSAT 1013",
    "PUSAT 1013 di Aras 1"), unless a capitalised word that is no function word stands right after the number
    ("Akademi 21 Mercu", "Edu360 Kuantan"); only a campus word may take a place there ("Kampus 2 Labuan")."""
    if not (j + 1 < len(toks) and not covered[j + 1] and up[j + 1].isdigit()):
        return False
    x = j + 2
    if not (x < len(toks) and not covered[x] and toks[x][0][:1].isupper() and up[x] not in _FUNCTION_WORDS
            and up[x] != 'MALAYSIA'):                             # "#KBS1Malaysia", the 1Malaysia slogan
        return True
    return up[j] in STATE_AND_CAMPUS and (up[x] in places or up[x] in _any_place())


#: Round 14: the words a room / block number stands after ("Bilik PUSAT 1013").
_ROOM_WORDS = frozenset({'BILIK', 'BLOK', 'ARAS', 'TINGKAT', 'DEWAN', 'MAKMAL', 'BENGKEL', 'STUDIO', 'KOD', 'NO',
                         'ROOM', 'BLOCK', 'LEVEL', 'HALL', 'LAB', 'CODE'})


def _named_before(j, toks, up, covered, raw, places) -> bool:
    """A capitalised NAME stands right before the noun, nothing between ("Mercu Academy 2")."""
    x = j - 1
    if x < 0 or covered[x] or raw[toks[x][2]:toks[j][1]].strip():
        return False
    w = up[x]
    return bool(toks[x][0][:1].isupper() and w not in _FUNCTION_WORDS and not is_org_word(w)
                and w not in LABEL_WORDS and w not in _ROOM_WORDS and w not in places and w not in _any_place())


@functools.lru_cache(maxsize=1)
def _any_place():
    """Every catalogued campus place word of any family, the states and campus words, and MALAYSIA."""
    return frozenset(STATE_AND_CAMPUS | {'MALAYSIA'}).union(*catalogue_places().values())


#: The lead's ruling (a329): words that name an organisation only after a NAME, never after a descriptor.
WEAK_SUFFIXES = frozenset({'GLOBAL', 'INTERNATIONAL', 'TECH', 'SKILLS', 'SOLUTIONS', 'VENTURES', 'EDU'})
DESCRIPTORS = frozenset({'PENDIDIKAN', 'LATIHAN', 'KEMAHIRAN', 'TEKNIKAL', 'VOKASIONAL', 'KEUSAHAWANAN', 'EDUCATION',
                         'TRAINING', 'TECHNICAL', 'VOCATIONAL'})


#: TD-494 (a): a descriptor run holding one of each is the TVET sector spelt out where a name would stand.
_TECHNICAL = frozenset({'TEKNIKAL', 'TECHNICAL'})
_VOCATIONAL = frozenset({'VOKASIONAL', 'VOCATIONAL'})


def _name_beside(lines, raws, i, key, places, above) -> bool:
    """TD-494 (b, c): a NAME stands on the body line above (the words after its last punctuation, the line ending
    on them) or below (the whole line) a descriptor run: one to four `_names_word` words, at least one of them no
    descriptor, label, reference / date label, place, nor the letterhead agency's or institute's own word. Never the
    letterhead or the addressee block, a closing line ("PENGARAH") or a course name ("Sijil Kemahiran …")."""
    from .offer_reading import _CLOSING, _COURSE
    if not (0 <= i < len(raws) and i < len(lines)) or _in_addressee_block(lines, i):
        return False
    if any(c in lines[i] for c in _CLOSING):
        return False
    raw, toks = raws[i], _tokens(raws[i])
    if not toks:
        return False
    if above:
        if raw[toks[-1][2]:].strip():
            return False                                   # the line above ends on punctuation: a sentence ended
        cut = max((m.end() for m in re.finditer(r'[^\w\s&]', raw)), default=0)
        toks = [t for t in toks if t[1] >= cut]
    elif re.search(r'[^\w\s&]', raw):
        return False                                       # the line below is a name line, nothing else
    own = {w for n in _INSTITUTE_KEY[key] + _AGENCIES[key] for w in n.split()} | AGENCY_TOKENS.get(key, set())
    words = [t[0].upper() for t in toks]
    if any(f' {w} ' in _COURSE for w in words):
        return False                                       # a course name ("Kursus : Sijil Kemahiran …")
    return 0 < len(toks) <= 4 and all(_names_word(t) for t in toks) and any(
        not w.isdigit() and w not in DESCRIPTORS and w not in LABEL_WORDS and w not in _REF_DATE_LABELS
        and w not in own and w not in places and w not in _any_place()
        for w in words)


def _after_descriptor(up, j, toks=None, covered=None, above=None) -> bool:
    """The word before `up[j]` is a descriptor (or DAN / AND after one; "&" is no token) — and (round 12, H2) no
    capitalised word that is no function word and no descriptor stands before that descriptor run on the line
    ("Mercu Technical Solutions" names Mercu; "Ke arah Pendidikan & Latihan Global" names nothing). TD-494: nor is
    the run the sector spelt out ("Teknikal Vokasional Solutions"), nor does an allowed name stand right before it
    ("MARA Technical Solutions"), nor, when it starts the line, a name end the line above (`above`, a token)."""
    k = j - 1
    while k >= 0 and (up[k] in DESCRIPTORS or up[k] in ('DAN', 'AND')):
        k -= 1
    if k == j - 1 or up[k + 1] not in DESCRIPTORS:
        return False
    run = set(up[k + 1:j])
    if run & _TECHNICAL and run & _VOCATIONAL:
        return False                                      # TD-494 (a): the sector where the name would be
    if k >= 0 and toks and covered and covered[k] and toks[k][0][:1].isupper():
        return False                                      # TD-494 (a): "MARA Technical Solutions"
    if k < 0 and above:
        return False                                      # TD-494 (b): "Penyedia latihan : Mercu" / "Technical …"
    for x in range(k + 1):
        if covered and covered[x]:
            continue
        word = toks[x][0] if toks else up[x]
        if (word[:1].isupper() and up[x] not in _FUNCTION_WORDS and up[x] not in DESCRIPTORS):
            return False
    return True
