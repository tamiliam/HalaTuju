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
    dropped), zero-width / soft-hyphen characters removed, Cyrillic / Greek lookalikes read as Latin."""
    text = unicodedata.normalize('NFKC', text or '').translate(_INVISIBLE).translate(_LOOKALIKE)
    text = ''.join(ch for ch in unicodedata.normalize('NFKD', text) if not unicodedata.combining(ch))
    return unicodedata.normalize('NFKC', text)


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
#: At a token's START only the institution nouns glue ("KOLEJMERCU"); short words there begin ordinary ones
#: ("HUBUNGI", "INCLUDE", "TECHNICAL").
_GLUED_START = re.compile(r'(?:KOLEJ|COLLEGE|AKADEMI|ACADEMY|UNIVERSITI|UNIVERSITY|INSTITUT|INSTITUTE|INSTITUSI|'
                          r'SEKOLAH|SCHOOL|POLITEKNIK|POLYTECHNIC|MAKTAB|PUSAT|YAYASAN|PERSATUAN|KOPERASI|'
                          r'SYARIKAT)(?=[A-Z]{3,}$)')
_GLUED_END = re.compile(rf'(?<=[A-Z]{{3}})(?:{_GLUE_WORDS})$')
#: Real words that start with a noun ("AKADEMIK…", "PUSATNYA"); measured on the corpus (round 12).
_NOT_GLUED = re.compile(r'^(?:AKADEMIK|PUSATKAN|SEKOLAHNYA|PUSATNYA|KOLEJNYA|INSTITUSINYA|MAJLISNYA)')


def glued_org(word, allowed=()) -> bool:
    """Round 12: ONE glued-organisation test: an organisation word at the start or end of a token (no space), the
    rest 3+ letters. Never a token that is itself an organisation word, a listed real word, or holds an allowed /
    closed-list name written without its spaces ("UNIVERSITIMALAYSIASABAH")."""
    word = (word or '').upper()
    from .offer_reading import is_org_token
    if len(word) < 6 or not word.isalpha() or _NOT_GLUED.match(word) or is_org_token(word):
        return False
    if any(''.join(n.split()) in word for n in tuple(allowed) + _joined_public()):
        return False
    return bool(_GLUED_START.match(word) or _GLUED_END.search(word))


@functools.lru_cache(maxsize=1)
def _joined_public():
    from .offer_reading import _NO_PRIVATE_WING, _TVET_NAMES
    from .offer_signatures import _UA_NAMES
    names = list(_TVET_NAMES) + [n for _k, ns, _m in _NO_PRIVATE_WING for n in ns] + [f' {n} ' for n in _UA_NAMES]
    return tuple(''.join(n.split()) for n in names if len(n.split()) > 1)
