"""The one text normaliser every offer exact-read S6 check reads (round 11, Low): what OCR or a forger can put
in a word to hide it from the word tests. Pure."""
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
