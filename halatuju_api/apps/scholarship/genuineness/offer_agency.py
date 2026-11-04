"""The agency-letterhead lift's CLOSED-WORLD condition 4 (offer exact-read S6, decisions.md S6 item 9; owner ruling
2026-11-04: app 329 green; the lead's rulings of the same day).

A TVET offer on an agency's own letterhead (`offer_rulings._agency_lift`) lifts only when every body line, after its
ALLOWED spans are taken out, holds NO organisation word at all — wherever it sits, a name before or after it alike.

  Allowed spans: the matched institute's closed-list names (`offer_rulings._INSTITUTE_KEY`) followed only by that
  institute family's catalogued campus / place words; the letterhead agency and its umbrella names
  (`offer_rulings._AGENCIES`); the spelt-out TVET sector name; a field label (PUSAT PENGAJIAN / PUSAT LATIHAN /
  TEMPAT / LOKASI / INSTITUSI, an optional bracket) when the allowed institute follows it on the line; a line made
  ONLY of label words (a table's label column); a closed-list bank line; the addressee block.
  The only exception: a bare generic noun in LOWERCASE raw OCR followed by a function word or punctuation
  ("pihak institut berhak", "di institusi/kolej"). At a line's end, the next line's first word is read: a
  title-case word, or an all-caps one that is no function word, is a name. A glued "KolejMercu" is split first.
  Another agency's full name, an operator phrase ("dikendalikan oleh", "in collaboration with") anywhere, or a
  name line on the letterhead below the agency = no lift. The agency must stand first on the letterhead
  (`_agency_first`); WAKIL / EJEN / AGEN anywhere = no lift.

The campus words come from the API's own TVET catalogue — `apps.courses.tvet_institutions.HELD` and the UP_TVET
catalogue snapshots `data/tvet/uptvet_F1_source.json` / `uptvet_F2_source.json` (Bumi coverage F1 / F2), by
provider family (`apps.courses.tvet_families.family_of`) — plus the states and KAMPUS / CAWANGAN. Pure.
KNOWN GAP (TD-491): a private name with NO organisation word ("Mercu Engineering Works") is not caught.
"""
import functools
import json
import os
import re

from .offer_reading import (_COMPANY_HEAD, _PRIVATE_BODIES, _POSTCODE, _SB, _TIE_UP, _TVET_SPELT, _bank_line,
                            _in_addressee_block, _is_contact, _letterhead_lines, _page)
from .offer_rulings import _ADDRESS_LINE, _AGENCIES, _FUNCTION_WORDS, _GOVERNMENT_LINE, _INSTITUTE_KEY, _WORD

#: Organisation words: what is left of a body line may hold none of them.
ORG_WORDS = frozenset({'INSTITUT', 'INSTITUTE', 'INSTITUTES', 'INSTITUSI', 'KOLEJ', 'COLLEGE', 'COLLEGES', 'AKADEMI',
                       'ACADEMY', 'UNIVERSITI', 'UNIVERSITY', 'POLITEKNIK', 'POLYTECHNIC', 'PUSAT', 'CENTRE', 'CENTER',
                       'SEKOLAH', 'SCHOOL', 'MAKTAB', 'TRAINING', 'LEARNING', 'HUB', 'GROUP', 'EDU', 'EDUCATION', 'PLT',
                       'HOLDINGS', 'ENTERPRISE', 'ENTERPRISES', 'RESOURCES', 'SERVICES', 'CONSULTANCY', 'AGENSI',
                       'AGENCY', 'MAJLIS'})
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
    return {key: frozenset(words - ORG_WORDS) for key, words in out.items()}


def _is_fragment(ln) -> bool:
    """(2) A one-token OCR fragment that names nothing (no organisation / company / private body / tie-up word)."""
    words = ln.split()
    return (len(words) == 1 and words[0] not in ORG_WORDS and not any(c in ln for c in _COMPANY_HEAD)
            and not _SB.search(ln) and not any(b in ln for b in _PRIVATE_BODIES) and not any(t in ln for t in _TIE_UP))


def _agency_first(lines, key) -> bool:
    """(f) The letterhead agency stands first on the letterhead: above its line only crest / government lines, junk
    lines (no alphabetic word of 3+ letters), up to three one-token fragments, and a KEPADA line with its address
    block — never inside an address (Wisma / Menara / Jalan / Bangunan); no WAKIL / EJEN / AGEN on the page; and
    (6) below it, up to the first postcode line, only address / contact / web / division / agency lines."""
    if _AGENT_WORDS.search(_page(lines)):
        return False
    head, i, fragments = _letterhead_lines(lines), 0, 0
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
                if any(w in ORG_WORDS for w in head[j].split()):
                    return False
                if _POSTCODE.search(head[j]):
                    j += 1
                    break
                j += 1
            i = j
            continue
        if _is_fragment(ln) and fragments < 3:
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


def _tokens(raw):
    """The raw line's words with their spans, OCR 0 / 1 read as O / I (case kept); (5) a glued institution noun is
    split off ("KolejMercu", "KOLEJMERCU")."""
    out = []
    for m in _WORD.finditer(raw or ''):
        word, start = m.group(0).replace('0', 'O').replace('1', 'I'), m.start()
        up = word.upper()
        noun = next((n for n in _GLUE_NOUNS if up.startswith(n) and len(up) > len(n)), '')
        rest = word[len(noun):]
        if noun and up not in ORG_WORDS and (rest[:1].isupper() and not word.isupper()
                                             or word.isupper() and len(rest) >= 3 and rest.isalpha()
                                             and rest != 'NYA'):
            out += [(word[:len(noun)], start, start + len(noun)), (rest, start + len(noun), m.end())]
        else:
            out.append((word, start, m.end()))
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
    places = catalogue_places().get(key, frozenset()) | STATE_AND_CAMPUS | _letterhead_places(lines)
    org = ORG_WORDS | OTHER_AGENCY_TOKENS | {t for k, ts in AGENCY_TOKENS.items() if k != key for t in ts}
    other_full = OTHER_FULL_NAMES + tuple(n for k, ns in AGENCY_FULL_NAMES.items() if k != key for n in ns)
    for i in range(head_n, len(lines)):
        if (_bank_line(lines[i]) or _in_addressee_block(lines, i) or i >= len(raws)
                or _label_only(lines[i])):
            continue
        raw, toks = raws[i], _tokens(raws[i])
        up = [t.upper() for t, _s, _e in toks]
        covered = [False] * len(toks)
        _cover(up, _TVET_SPELT, covered)                       # the sector's name, spelt out
        for start, end in _cover(up, _INSTITUTE_KEY[key], covered):
            label = _LABEL_BEFORE.search(raw[:toks[start][1]]) if start else None
            if label:                                             # its field label ("Pusat Pengajian : IKBN …")
                for k in range(start):
                    if toks[k][1] >= label.start():
                        covered[k] = True
            k = end
            while k < len(toks) and not covered[k] and up[k] in places:
                covered[k] = True                                 # its catalogued campus / place words
                k += 1
            if k < len(toks) and not covered[k] and toks[k][0][:1].isupper() and up[k] not in _FUNCTION_WORDS:
                return f'after the institute: {up[k]}'            # (e) "IKM Mercu"
        _cover(up, _AGENCIES[key], covered)
        for start, _end in _cover(up, other_full, covered):
            return f"another agency: {' '.join(up[start:_end])}"  # (3)
        for j, w in enumerate(up):
            if covered[j] or w not in org:
                continue
            if toks[j][0].islower() and w in ORG_WORDS:          # (c) a bare generic noun, lowercase
                rest = raw[toks[j][2]:]
                if not rest.strip():                              # (d) the line's end: read the next line
                    nxt = _tokens(raws[i + 1]) if i + 1 < len(raws) else []
                    if nxt and _names_word(nxt[0]):
                        return f'line end: {w} + next line {nxt[0][0].upper()}'
                    continue
                if not rest[:1].isalnum() and not rest[:1].isspace() or rest.lstrip()[:1] in '/.,;:()-':
                    continue                                      # punctuation follows
                if j + 1 < len(toks) and up[j + 1] in _FUNCTION_WORDS:
                    continue                                      # a function word follows
            return f'organisation word: {w}'
    return ''


def _letterhead_places(lines) -> set:
    """The words of the letterhead and of every address line on the page (a postcode on it)."""
    out = set()
    for ln in _letterhead_lines(lines) + [ln for ln in lines if _POSTCODE.search(ln)]:
        out.update(ln.split())
    return out - ORG_WORDS
