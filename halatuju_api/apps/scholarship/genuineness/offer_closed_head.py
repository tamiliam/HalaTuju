"""THE CLOSED LETTERHEAD of a confirmation's (and KPM's English matric offer's) GENUINE result (help H2 round 3,
Opus re-review, 2026-11-15). Rounds 1-2 read a letterhead by a BLOCKLIST (an organisation noun, a word before the
name, a stray unit word): every word the lists missed passed ("KPT MERCU EDUCATION GROUP", "MAJLIS MERCU
EDUCATION", "MERCU JAYA" read genuine). Now it is an ALLOWLIST: a letterhead line may hold ONLY

  * a KNOWN public name of the type (`offer_confirmations._KNOWN_PUBLIC_NAMES`) and the type's own acronyms;
  * the ministry's name or acronym (KPM / KPT / JPPKK / MOE / MOHE), the crest words (KERAJAAN MALAYSIA, JATA
    NEGARA, the national motto);
  * a unit line made ONLY of unit and function words (`_UNIT_WORDS`, `_UNIT_FUNCTIONS`, "SCHOOL OF");
  * an address / postcode / phone / fax / e-mail / web tail, naming no institution or public body;
  * a state (13 states, 3 federal territories, their short forms and DARUL titles) at the line's end or before
    the address;
  * a "KAMPUS / CAMPUS + 1-3 place words" line straight under the known name's line;
  * the label of a date line ("TARIKH", "DATE").

ANY other word on ANY letterhead line = suspect, never genuine (a person checks): a town is no exception, and
a second institution name or word is never allowed. Pure. Moved here from `offer_rulings` with `_known_names`
(that file stood at 577 lines); `offer_rulings` imports every name back.
"""
import functools
import re

from .offer_confirmations import (_KNOWN_PUBLIC_NAMES, _KPM, _KPT, _OWN_ACRONYMS, _PUBLIC_PATTERN, _UNIT_FUNCTIONS,
                                  _UNIT_WORDS)
from .offer_reading import _HEAD_RE, _ORG_RE, _WEB_TAIL, _is_contact


@functools.lru_cache(maxsize=1)
def _known_names():
    """`_KNOWN_PUBLIC_NAMES` folded like a page, longest first ("... CAWANGAN SEPANG" before "KUALA LANGAT"); an
    IPG campus by its own short form too ("IPG KAMPUS IPOH")."""
    from .results_doc import _norm_fold_upper_alnum
    out = {}
    for seen, names in _KNOWN_PUBLIC_NAMES.items():
        short = [n.replace('INSTITUT PENDIDIKAN GURU ', 'IPG ') for n in names] if seen == 'confirmation_ipg' else []
        folded = {f" {' '.join(_norm_fold_upper_alnum(n).split())} " for n in list(names) + short}
        out[seen] = tuple(sorted(folded, key=len, reverse=True))
    return out


#: The ministries and the crest, blanked like a known name (longest first: "MINISTRY OF EDUCATION MALAYSIA"
#: before "MINISTRY OF EDUCATION").
_PUBLIC_MARKS = tuple(sorted(set(_KPM + _KPT + (
    ' KPM ', ' KPT ', ' MOE ', ' MOHE ', ' JPPKK ', ' KERAJAAN MALAYSIA ', ' GOVERNMENT OF MALAYSIA ',
    ' JATA NEGARA ', ' BERSEKUTU BERTAMBAH MUTU ')), key=len, reverse=True))
#: The states and federal territories (folded), with their short forms and titles: allowed only at a line's end
#: or before the address. NO town list: a town on a letterhead stays suspect.
_STATES = tuple(sorted({tuple(s.split()) for s in (
    'JOHOR', 'KEDAH', 'KELANTAN', 'MELAKA', 'MALACCA', 'NEGERI SEMBILAN', 'N SEMBILAN', 'PAHANG', 'PERAK',
    'PERLIS', 'PULAU PINANG', 'P PINANG', 'PENANG', 'SABAH', 'SARAWAK', 'SELANGOR', 'TERENGGANU',
    'WILAYAH PERSEKUTUAN', 'WP', 'W P', 'KUALA LUMPUR', 'LABUAN', 'PUTRAJAYA', 'MALAYSIA',
    'DARUL TAKZIM', 'DARUL TA ZIM', 'DARUL AMAN', 'DARUL NAIM', 'DARUL KHUSUS', 'DARUL MAKMUR', 'DARUL RIDZUAN',
    'DARUL EHSAN', 'DARUL IMAN', 'DARUL REDZUAN', 'INDERA KAYANGAN')}, key=len, reverse=True))
#: The words an address may start with (a free street / place name may follow; never an institution word).
_ADDRESS_START = frozenset({'JALAN', 'JLN', 'LORONG', 'PERSIARAN', 'LEBUH', 'LEBUHRAYA', 'PETI', 'PO', 'TAMAN',
                            'KAMPUNG', 'KG', 'BANDAR', 'ARAS', 'BLOK', 'TINGKAT', 'KOMPLEKS', 'PRESINT', 'PARCEL',
                            'KAWASAN', 'SEKSYEN', 'BEG', 'KARUNG', 'LOCKED', 'MUKIM'})
#: ... the ones that need a number next ("LOT 5", "BATU 3", "KM 12", "NO 5").
_NUMBERED_START = frozenset({'LOT', 'BATU', 'KM', 'NO'})
#: ... and the contact words a contact tail starts with.
_CONTACT_START = frozenset({'TEL', 'TELEFON', 'FAKS', 'FAX', 'WWW', 'HTTP', 'HTTPS', 'EMEL', 'EMAIL', 'LAMAN',
                            'WEB', 'WEBSITE', 'PHONE', 'TELEPHONE'})
#: The heads a unit line names its unit by (with `_UNIT_WORDS`).
_UNIT_HEADS = (('SCHOOL', 'OF'), ('STUDENT', 'SERVICES'), ('HAL', 'EHWAL'))
#: A date line's label, kept above its date by `_letterhead_lines` ("Tarikh : 1 Jun 2026").
_DATE_LABELS = frozenset({'TARIKH', 'DATE', 'BERTARIKH'})
#: An institution, company or public body word: never in an address tail, a campus line or a title's rest.
_BODY_RE = re.compile(r' (?:MAJLIS|LEMBAGA|PERBADANAN|KEMENTERIAN|JABATAN|MINISTRY|DEPARTMENT|AGENSI|AGENCY|'
                      r'INSTITUSI|BAHAGIAN|DIVISION|PUSAT|YAYASAN|GOVERNMENT|KERAJAAN|IPG|KMK?(?! \d))(?= )')
#: "KM <name>" / "KMK <name>" left after the known names: an unlisted college ("KM 12" is a kilometre).
_KM_NAME = re.compile(r' KMK? (?![\d#])')
#: The title's own words a known name may follow in the title segment ("PENGESAHAN PELAJAR KOLEJ MATRIKULASI ...").
_TITLE_WORDS = frozenset({'SURAT', 'PENGESAHAN', 'SEBAGAI', 'PELAJAR', 'BELAJAR', 'STATUS', 'CONFIRMATION',
                          'LETTER', 'OF', 'STUDENT', 'STUDIES', 'DI', 'DARI', 'DARIPADA', 'AT', 'FROM', 'THE', 'IN',
                          'BAGI', 'UNTUK', 'FOR'})
#: ... and the words that may come straight after it there.
_AFTER_TITLE_NAME = frozenset({'SESI', 'SESSION', 'SEMESTER', 'TAHUN', 'BAGI', 'UNTUK', 'FOR', 'PROGRAM',
                               'KURSUS', 'DENGAN', 'ADALAH', 'IS'})


def _blank(ln, phrases) -> tuple:
    """`ln` with every phrase replaced by ' # ' (longest first, as given), and whether any was there."""
    hit = False
    for p in phrases:
        while p in ln:
            ln, hit = ln.replace(p, ' # ', 1), True
    return ln, hit


def _institution_word(words, seen) -> bool:
    s = _WEB_TAIL.sub(' ', f" {' '.join(w for w in words if w != '#')} ")     # "edu.my" names no college
    return bool(_ORG_RE.search(s) or _HEAD_RE.search(s) or _BODY_RE.search(s)
                or any(p in s for p in _PUBLIC_PATTERN.get(seen, ())))


def _state_at(words, i) -> int:
    for st in _STATES:
        if tuple(words[i:i + len(st)]) == st:
            return len(st)
    return 0


def _address_at(words, i, contact) -> bool:
    w, nxt = words[i], (words[i + 1] if i + 1 < len(words) else '')
    if (w.isdigit() and len(w) == 5) or w in _ADDRESS_START or w in _CONTACT_START:
        return True
    if w == 'P' and words[i + 1:i + 3] == ['O', 'BOX'] or w == 'E' and nxt in ('MEL', 'MAIL'):
        return True
    if w in _NUMBERED_START and nxt[:1].isdigit():
        return True
    return w[:1].isdigit() and (nxt in _ADDRESS_START or contact)   # "5 JALAN ...", a phone number


def _unit_segment(words) -> bool:
    """Only unit and function words, naming its unit ("UNIT HAL EHWAL PELAJAR", "SCHOOL OF ...")."""
    pairs = set(zip(words, words[1:]))
    if not (any(w in _UNIT_WORDS for w in words) or any(h in pairs for h in _UNIT_HEADS)):
        return False
    return all(w in _UNIT_WORDS or w in _UNIT_FUNCTIONS or (w == 'SCHOOL' and ('SCHOOL', 'OF') in pairs)
               for w in words)


def _line_closed(ln, seen, contact) -> bool:
    """Every '#'-separated part of a blanked letterhead line is allowed (module note)."""
    words = ln.split()
    segs, cur = [], []
    for w in words + ['#']:
        if w == '#':
            segs.append(cur)
            cur = []
        else:
            cur.append(w)
    start = 0                           # where the current part starts in `words` (the address tail reads on)
    for k, seg in enumerate(segs):
        at, start = start, start + len(seg) + 1
        if not seg or _unit_segment(seg) or all(w in _DATE_LABELS for w in seg):
            continue
        rest = list(seg)
        while k == len(segs) - 1 and rest and _state_end(rest):
            rest = rest[:-_state_end(rest)]             # states at the line's end ("... PERAK DARUL RIDZUAN")
        if not rest:
            continue
        i = 0
        while i < len(rest) and _state_at(rest, i):
            i += _state_at(rest, i)
        if i < len(rest) and _address_at(rest, i, contact):
            return not _institution_word(words[at + i:], seen)        # the rest of the line is the address
        return False
    return True


def _state_end(words) -> int:
    """The length of a state phrase ending `words` (0 when none)."""
    for st in _STATES:
        if len(words) >= len(st) and tuple(words[-len(st):]) == st:
            return len(st)
    return 0


def _campus_line(ln) -> bool:
    """"KAMPUS GOPENG": KAMPUS / CAMPUS and 1-3 place words, no digit, no institution word."""
    words = ln.split()
    return (len(words) in (2, 3, 4) and words[0] in ('KAMPUS', 'CAMPUS') and all(w.isalpha() for w in words)
            and not _institution_word(words[1:], ''))


def campus_dropped(lines, names):
    """`lines` without a campus line (`_campus_line`) straight under a letterhead line naming one of `names`
    (known public names): what `offer_rulings.confirmation_kind`'s clean-letterhead gate reads, so "KOLEJ
    MATRIKULASI PERAK / KAMPUS GOPENG" is a candidate (the KAMPUS noun had made it no confirmation at all)."""
    from .offer_reading import _letterhead_region
    head_n = len(_letterhead_region(lines))
    return [ln for i, ln in enumerate(lines)
            if not (0 < i < head_n and _campus_line(ln) and any(n in lines[i - 1] for n in names))]


def _known_name(head_lines, seen) -> bool:
    """THE CLOSED LETTERHEAD (module note): a KNOWN public name of the type is on the letterhead, and every word
    of every letterhead line is allowed. Anything else - a town, a second name, a stray word - is no proof."""
    names, acronyms = _known_names().get(seen, ()), _OWN_ACRONYMS.get(seen, frozenset())
    found, named_above = False, False
    for ln in head_lines:
        if named_above and _campus_line(ln):
            named_above = False
            continue
        contact = _is_contact(ln)
        ln, named = _blank(ln, names)
        ln, _m = _blank(ln, _PUBLIC_MARKS)
        ln, _a = _blank(ln, tuple(f' {a} ' for a in sorted(acronyms, key=len, reverse=True)))
        if not _line_closed(ln, seen, contact):
            return False
        found, named_above = found or named, named
    return found


def _title_clean(title, seen) -> bool:
    """The title segment names no other institution: a known name there follows only title words and is followed
    by nothing, a number or a session word; no institution / pattern word and no "KM <name>" is left."""
    ln, _hit = _blank(title, _known_names().get(seen, ()))
    words = ln.split()
    for j, w in enumerate(words):
        if w != '#':
            continue
        before = words[:j]
        cut = max((x for x, b in enumerate(before) if b == '#'), default=-1)
        nxt = words[j + 1] if j + 1 < len(words) else ''
        if any(b not in _TITLE_WORDS for b in before[cut + 1:]) or (
                nxt and nxt != '#' and not nxt[:1].isdigit() and nxt not in _AFTER_TITLE_NAME):
            return False
    return not (_institution_word(words, seen) or _KM_NAME.search(f" {' '.join(words)} "))
