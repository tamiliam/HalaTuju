"""The one text normaliser every offer exact-read S6 check reads (round 11, Low): what OCR or a forger can put
in a word to hide it from the word tests. Pure."""
import functools
import re
import unicodedata

#: Round 11 (Low): characters that hide a word from the tests — zero-width marks, the soft hyphen — and the
#: Cyrillic / Greek letters OCR or a forger puts for Latin ones.
_INVISIBLE = dict.fromkeys(map(ord, '\u00ad\u200b\u200c\u200d\u2060\ufeff'))
_LOOKALIKE = str.maketrans('АВЕКМНОРСТХаеорсухіјѕԁΑΒΕΖΗΙΚΜΝΟΡΤΥΧαεικνορτυχ',
                           'ABEKMHOPCTXaeopcyxijsdABEZHIKMNOPTYXaeiknoptux')


def normalise_s6(text) -> str:
    """The one normaliser every S6 check reads: NFKC (full-width letters), accents folded (NFKD, combining marks
    dropped), zero-width / soft-hyphen characters removed, Cyrillic / Greek lookalikes read as Latin; then (round
    13) a word mixing letters and digits is read as OCR when the digits make it an organisation word ("K0LEJ",
    "Ko1ej", "ACAD3MY"), else split where letters meet digits ("AKADEMI21" -> "AKADEMI 21")."""
    text = unicodedata.normalize('NFKC', text or '').translate(_INVISIBLE).translate(_LOOKALIKE)
    text = ''.join(ch for ch in unicodedata.normalize('NFKD', text) if not unicodedata.combining(ch))
    text = unicodedata.normalize('NFKC', text)
    return _MIXED.sub(_read_mixed, text)


#: A word with both letters and digits.
_MIXED = re.compile(r'[^\W_]*(?:[^\W\d_]\d|\d[^\W\d_])[^\W_]*')
_OCR_DIGITS = ({'0': 'O', '1': 'I', '3': 'E'}, {'0': 'O', '1': 'L', '3': 'E'})


def _read_mixed(m) -> str:
    """One mixed word: an OCR spelling of an organisation word (whole, or glued to a name), else split."""
    from .offer_reading import is_org_token
    word = m.group(0)
    for table in _OCR_DIGITS:
        read = ''.join(table[ch].lower() if ch in table and i and word[i - 1].islower() else table.get(ch, ch)
                       for i, ch in enumerate(word))
        if read.isalpha() and (is_org_token(read.upper()) or glued_org(read)):
            return read
    return re.sub(r'(?<=[^\W\d_])(?=\d)|(?<=\d)(?=[^\W\d_])', ' ', word)


#: Round 11 (M6): the acronyms a logo strip lists ("IKM KKTM KPM GMI").
_LOGO_ACRONYMS = frozenset({'IKM', 'KKTM', 'KPM', 'KPT', 'JPK', 'MARA', 'TVETMARA', 'GMI', 'UNIKL', 'KPTM', 'KUPTM',
                            'UPTM', 'IKBN', 'IKTBN', 'ILKBS', 'KBS', 'JTM', 'ILP', 'ADTEC', 'JMTI', 'CIAST', 'KSM',
                            'UMS', 'UM', 'UKM', 'UPM', 'USM', 'UITM', 'UTM', 'IPMA', 'PPPL', 'SATU'})


def logo_strip(ln) -> bool:
    """A line listing three or more acronyms (a strip of partner logos), not an issuer."""
    return sum(1 for w in ln.split() if w in _LOGO_ACRONYMS) >= 3


def own_issuer_line(ln, bodies) -> bool:
    """A named private body standing on its own line as the issuer (nothing but its name on the line)."""
    rest = ln
    for b in sorted(bodies, key=len, reverse=True):
        rest = rest.replace(b, ' ')
    return not rest.strip()


#: Round 12 (H1): an organisation word glued to a name ("MERCUACADEMY", "KOLEJMERCU", "MercuSkills"): the shared
#: list's words as whole words (a stem's open tail - CENTR*, EDU*, CORP* - would swallow ordinary words).
_GLUE_WORDS = (r'KOLEJ|COLLEGES?|AKADEMI|ACADEM(?:Y|IES)|UNIVERSITI|UNIVERSIT(?:Y|IES)|INSTITUT|INSTITUTES?|'
               r'INSTITUTIONS?|INSTITUSI|TUISYEN|TUITION|SEKOLAH|SCHOOLS?|POLITEKNIK|POLYTECHNICS?|MAKTAB|PUSAT|'
               r'TRAINING|TRAINERS?|CENTRES?|CENTERS?|HUBS?|GROUPS?|PLT|EDU|EDUCATION|LEARNING|SKILLS?|'
               r'ENTERPRISES?|RESOURCES?|INTERNATIONAL|GLOBAL|SERVICES?|SOLUTIONS?|HOLDINGS?|CORP|CORPORATION|'
               r'CONSULTANCY|CONSULTANTS?|VENTURES?|LTD|LIMITED|INC|PERSATUAN|PERTUBUHAN|TECH|KAMPUS|YAYASAN|'
               r'KOPERASI|SYARIKAT|CONSORTIUM|MAJLIS')
#: At a token's START only the institution nouns (and, round 13, the training words) glue ("KOLEJMERCU",
#: "SKILLSPRIMA"); short words there begin ordinary ones ("HUBUNGI", "INCLUDE", "TECHNICAL").
_START_WORDS = (r'KOLEJ|COLLEGE|AKADEMI|ACADEMY|UNIVERSITI|UNIVERSITY|INSTITUT|INSTITUTE|INSTITUSI|SEKOLAH|SCHOOL|'
                r'POLITEKNIK|POLYTECHNIC|MAKTAB|PUSAT|YAYASAN|PERSATUAN|KOPERASI|SYARIKAT|SKILLS|TRAINING|'
                r'TUISYEN|TUITION|EDU')
#: Round 13 (Medium): an institution noun INSIDE a glued token ("MERCUACADEMYKUANTAN").
_INSIDE_WORDS = (r'KOLEJ|COLLEGE|AKADEMI|ACADEMY|UNIVERSITI|UNIVERSITY|INSTITUT|INSTITUTE|INSTITUSI|SEKOLAH|'
                 r'POLITEKNIK|POLYTECHNIC|MAKTAB|TUISYEN|TUITION')
#: Round 13 (Low): what a glued name is NOT — a Malay prefix / suffix ("BERSEKOLAH", "SEKOLAHNYA") or the head of
#: an ordinary English compound ("HIGHSCHOOL", "LIFESKILLS", "DATACENTRE").
_AFFIXES = frozenset({'BER', 'TER', 'PRA', 'PASCA', 'ANTARA', 'PER', 'PE', 'ME', 'DI', 'KE', 'MEN', 'MENG', 'PEN',
                      'PENG', 'NYA', 'LAH', 'KU', 'MU', 'AN', 'KAN', 'ISASI', 'ING', 'AL', 'S', 'ES'})
_COMPOUND_HEADS = frozenset({'HIGH', 'LOW', 'LIFE', 'SOFT', 'WORK', 'MULTI', 'UP', 'RE', 'PRE', 'SUB', 'SUPER', 'MEGA',
                             'INTER', 'INTRA', 'DATA', 'CALL', 'MALL', 'SUMMER', 'SUNDAY', 'PRIMARY', 'BOARDING',
                             'GRADUATE', 'HOME', 'KEY', 'LAND', 'SHARE', 'STAKE', 'CLUB', 'SPACE', 'GIT', 'INFO',
                             'AGRO', 'NANO', 'BIO', 'FIN', 'ED', 'HI', 'SELF', 'IN', 'EPI', 'MIS', 'AD', 'UN', 'E',
                             'CO', 'NON', 'CROSS', 'ROMAN', 'AT', 'WITH', 'DIS', 'AB', 'THIN', 'Z', 'SIN', 'PRIN',
                             'PROVIN', 'CONVIN', 'EVIN', 'MED', 'SCHED', 'C', 'TRAIN', 'KOMUNITI', 'INTRAKAMPUS',
                             'ANTARABANGSA', 'KELAS', 'ONAL', 'IONAL', 'SECONDARY', 'PRACTICAL', 'TEACHER',
                             'VOCATIONAL', 'TECHNICAL', 'INDUSTRIAL', 'CONTACT'})
_NOT_GLUED_WORDS = frozenset({'INSTITUTIONAL', 'SCHOOLING', 'PRESCHOOL', 'WITHHOLDING', 'DISSOLUTION',
                              'SCHOOLTEACHER', 'SCHOOLBAG', 'SCHOOLHOUSE', 'SCHOOLWIDE', 'COLLEGEWIDE',
                              'UNIVERSITYWIDE', 'KINDERGARTEN', 'ANTARABANGSA', 'INSTITUTIONALISE', 'INSTITUSIONAL',
                              'MISADVENTURE', 'MISADVENTURES', 'CONSTRAINING'})


def _names_part(part, noun='') -> bool:
    """A glued token's other part is a NAME: four or more letters, not made only of Malay affixes ("ANNYA"), no
    compound head, not the noun again ("SEKOLAHSEKOLAH")."""
    return (len(part) >= 4 and not _affixes_only(part) and part not in _COMPOUND_HEADS and part != noun)


def _affixes_only(part) -> bool:
    """`part` is one or more affixes in a row ("AN" + "NYA")."""
    ok = [True] + [False] * len(part)
    for i in range(len(part)):
        if ok[i]:
            for a in _AFFIXES:
                if part.startswith(a, i):
                    ok[i + len(a)] = True
    return ok[len(part)]


def glued_org(word, allowed=()) -> bool:
    """Round 12 + 13: ONE glued-organisation test. An organisation word glued to a NAME, no space: an institution /
    training noun at the start, any shared-list word at the end, an institution noun inside; the name part four or
    more letters and no Malay affix or compound head. A token holding an allowed / closed-list name ("MARASKILLS",
    "IKMSKILLS", "KBSACADEMY") is tested on what is LEFT once the name is taken out — skipped only when nothing,
    or a catalogued campus word, is left ("UNIVERSITIMALAYSIASABAH")."""
    word = (word or '').upper()
    from .offer_reading import is_org_token
    if len(word) < 6 or not word.isalpha() or word in _NOT_GLUED_WORDS or is_org_token(word):
        return False
    for name in sorted(set(_joined(allowed) + _joined_public()), key=len, reverse=True):
        if name in word:
            rest = word.replace(name, '')
            if not rest or rest in _campus_words():
                return False
            return bool(is_org_token(rest) or _glued(rest, loose=True) or _glued(word))
    return _glued(word)


def _glued(word, loose=False) -> bool:
    """An organisation word at the start / end / inside of `word` with a NAME part (`loose`: any 2+ letters)."""
    def ok(part, noun):
        return len(part) >= 2 if loose else _names_part(part, noun)
    m = re.match(rf'(?:{_START_WORDS})', word)
    if m and m.end() < len(word) and ok(word[m.end():], m.group(0)):
        return True
    m = re.search(rf'(?:{_GLUE_WORDS})$', word)
    if m and m.start() > 0 and ok(word[:m.start()], m.group(0)):
        return True
    for m in re.finditer(rf'(?:{_INSIDE_WORDS})', word):
        if m.start() > 0 and m.end() < len(word) and (ok(word[:m.start()], m.group(0)) or ok(word[m.end():],
                                                                                              m.group(0))):
            return True
    return False


def _joined(names):
    return tuple(''.join(n.split()) for n in names if len(''.join(n.split())) >= 3)


@functools.lru_cache(maxsize=1)
def _campus_words():
    from .offer_agency import STATE_AND_CAMPUS, catalogue_campuses
    words = set(STATE_AND_CAMPUS)
    for phrases in catalogue_campuses().values():
        words.update(''.join(p.split()) for p in phrases)
    return frozenset(words)


@functools.lru_cache(maxsize=1)
def _joined_public():
    """Every closed-list / public institution name and agency name, written without its spaces."""
    from .offer_reading import _NO_PRIVATE_WING, _TVET_NAMES
    from .offer_rulings import _AGENCIES
    from .offer_signatures import _UA_NAMES
    names = list(_TVET_NAMES) + [n for _k, ns, _m in _NO_PRIVATE_WING for n in ns] + [f' {n} ' for n in _UA_NAMES]
    names += [n for ns in _AGENCIES.values() for n in ns]
    return _joined(names)
