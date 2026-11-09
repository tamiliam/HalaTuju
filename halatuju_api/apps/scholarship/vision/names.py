"""Name and NRIC matching: the canonical forms every vision verdict compares (moved verbatim
from ``vision.py``, audit sprint A3.1)."""

import re

from ..name_order import patronymic_reversed


# Stripped before name comparison — common MyKad name suffixes / parentage markers.
_NAME_NOISE = re.compile(
    # MyKad parentage tokens + Malay/English honorifics that prefix a name on official
    # letters (e.g. an offer addressed to "SDRI THEEPICAA …") — stripped so the name
    # matches the profile name regardless of the title.
    # The slash markers tolerate stray whitespace around the slash ("A/ P", "A / P",
    # "A /P") — a student who types their name that way otherwise leaves orphan single
    # letters "a"/"p" in the token set, which makes the EXACT name_match read a clean
    # subset → a false 'partial'/mismatch on the IC + offer letter (#20). TD-404: ANAK (Iban/Bidayuh/Kadazan
    # "child of") / AK, and BT / BTE for BINTI, are connectors like BIN — "JOHNNY AK GABRIEL" = "…ANAK…".
    r"\b(bin|binti|bt|bte|anak|ak|a\s*/\s*l|a\s*/\s*p|al|ap|d\s*/\s*o|s\s*/\s*o|@"
    r"|sdr|sdri|saudara|saudari|encik|puan|cik|tuan|dr|datuk|dato|datin)\b",
    flags=re.IGNORECASE,
)

# An OCR read that GLUES a slash parentage marker onto the name ("LAKSMITHAA/P VIJAYAN", #48)
# defeats _NAME_NOISE — its \b never fires mid-word, so the leftover "a"+"p" letters pollute the
# token set AND the glued comparison (name_match's boundary tolerance), producing a false red Name
# chip on the student's own document. These two patterns re-insert the lost space around a glued
# a/l, a/p, d/o or s/o (backward glue: marker stuck to the preceding name; forward glue: stuck to
# the following name). Slash-form markers ONLY — a '/' never legitimately occurs inside a name, so
# this cannot corrupt names that merely contain "al"/"ap" letters (e.g. KALAI).
_GLUED_MARKER_BEFORE = re.compile(r'([a-z])(a\s*/\s*[lp]|[ds]\s*/\s*o)\b', flags=re.IGNORECASE)
_GLUED_MARKER_AFTER = re.compile(r'\b(a\s*/\s*[lp]|[ds]\s*/\s*o)([a-z])', flags=re.IGNORECASE)


def _split_glued_markers(s: str) -> str:
    """Detach a slash parentage marker glued to a name token (both directions)."""
    s = _GLUED_MARKER_BEFORE.sub(r'\1 \2', s)
    return _GLUED_MARKER_AFTER.sub(r'\1 \2', s)


def _canonical_nric(s: str) -> str:
    """Strip hyphens, spaces, and non-digits. Returns ''-on-blank."""
    return re.sub(r'\D', '', s or '')


_MONTHS = {
    'jan': 1, 'januari': 1, 'january': 1,
    'feb': 2, 'februari': 2, 'february': 2,
    'mac': 3, 'mar': 3, 'march': 3,
    'apr': 4, 'april': 4,
    'mei': 5, 'may': 5,
    'jun': 6, 'june': 6,
    'jul': 7, 'julai': 7, 'july': 7,
    'ogo': 8, 'ogos': 8, 'aug': 8, 'august': 8,
    'sep': 9, 'sept': 9, 'september': 9,
    'okt': 10, 'oct': 10, 'oktober': 10, 'october': 10,
    'nov': 11, 'november': 11,
    'dis': 12, 'dec': 12, 'disember': 12, 'december': 12,
}


def _parse_dob(s: str):
    """Parse a printed date of birth → ``(yy, mm, dd)`` as 2-digit strings, else None.

    Accepts what a Malaysian birth certificate actually prints: ``17 JANUARI 2008``,
    ``17 JAN 2008``, ``17/01/2008``, ``17-01-2008`` and ``2008-01-17``. Pure; never raises.
    """
    if not s:
        return None
    txt = str(s).strip().lower()

    m = re.search(r'\b(\d{1,2})\s*[/\-. ]\s*([a-z]+)\s*[/\-. ]\s*(\d{4})\b', txt)
    if m and m.group(2) in _MONTHS:
        dd, mm, yyyy = int(m.group(1)), _MONTHS[m.group(2)], int(m.group(3))
    else:
        m = re.search(r'\b(\d{4})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{1,2})\b', txt)
        if m:                                   # ISO order: 2008-01-17
            yyyy, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            m = re.search(r'\b(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{4})\b', txt)
            if not m:                           # day-first: 17/01/2008
                return None
            dd, mm, yyyy = int(m.group(1)), int(m.group(2)), int(m.group(3))

    if not (1 <= mm <= 12 and 1 <= dd <= 31 and 1900 <= yyyy <= 2099):
        return None
    return f'{yyyy % 100:02d}', f'{mm:02d}', f'{dd:02d}'


def nric_dob_agrees(nric: str, dob: str) -> bool:
    """True iff a 12-digit NRIC's leading YYMMDD equals the printed date of birth.

    ⚠ THIS GUARD IS LOAD-BEARING, NOT BELT-AND-BRACES. ``bc_child_nric`` feeds
    ``academic/income`` engines that compare it to the student's OWN NRIC, so a MISREAD
    number (the register number ``BZ21723``, a parent's IC, a line of the barcode) produces
    a confident ``mismatch`` that newly BLOCKS a student — strictly worse than the blank
    this field held before. The certificate prints the date of birth beside the number, so
    the two must agree or we do not trust the read. Pure; never raises.

    ⚠ **IT VOUCHES FOR THE FIRST SIX DIGITS AND NOTHING MORE — do not read a pass as "the number
    is right".** The date can only speak for the date. Application 83 is the observed proof: a
    stained, creased barcode block read ``080306-07-0923`` against a MyKad of ``080306-07-0398``,
    the printed ``06 MAC 2008`` agreed, so the read was kept — and the last four digits still
    disagreed. That is WHY a number that survives this guard is compared row-wise and lands AMBER
    rather than green (`_combine_relationship`): the guard is what stops a misread creating a
    confident RED, not what makes the number trustworthy. Widening it is impossible — nothing on
    the certificate corroborates the last four digits — so the amber is the answer, and a person
    reads it. (Owner reviewed #83 on 2026-09-08 and confirmed the behaviour is correct.)
    """
    digits = _canonical_nric(nric)
    if len(digits) != 12:
        return False
    parts = _parse_dob(dob)
    if not parts:
        return False
    return digits[:6] == ''.join(parts)


def canonical_name_tokens(s: str) -> set:
    """Lowercase, strip MyKad parentage tokens + honorific prefixes, return a tokens set."""
    if not s:
        return set()
    cleaned = _NAME_NOISE.sub(' ', _split_glued_markers(s.lower()))
    return {t for t in re.split(r'[^a-z]+', cleaned) if t}


def _canonical_name_seq(s: str) -> list:
    """Like canonical_name_tokens but ORDER-PRESERVING (a list) — so the words can be
    glued back in their printed order. Needed to compare a name that an OCR space SPLIT
    inside a token (RUSHAINDRA → "RUSHAIND RA") or GLUED across a real space."""
    if not s:
        return []
    cleaned = _NAME_NOISE.sub(' ', _split_glued_markers(s.lower()))
    return [t for t in re.split(r'[^a-z]+', cleaned) if t]


def _glued_equal(a: str, b: str, *, fold: bool) -> bool:
    """True iff two names reduce to the SAME string once their word-boundaries are removed
    (order preserved). A spurious OCR space inside a name token, or two tokens glued
    together, shifts a boundary so the token SETS differ even though the printed name is
    identical — this comparison is agnostic to that. ``fold=True`` also applies the
    romanisation folding (cross-document use); ``fold=False`` keeps spelling exact
    (identity). Pure boundary tolerance — it can only turn a mismatch INTO a match."""
    def reduce(name: str) -> str:
        toks = _canonical_name_seq(name)
        return ''.join(_fold_name_token(t) for t in toks) if fold else ''.join(toks)
    ra, rb = reduce(a), reduce(b)
    return bool(ra) and ra == rb


def nric_match(extracted: str, profile_nric: str) -> bool:
    """True iff the two NRICs are equal after canonicalisation (digits only)."""
    a, b = _canonical_nric(extracted), _canonical_nric(profile_nric)
    return bool(a) and bool(b) and a == b


def nric_close(extracted: str, reference: str) -> bool:
    """True iff two NRICs are a SINGLE-digit edit apart (one substitution, or one inserted
    /dropped digit) after canonicalisation — i.e. a likely OCR slip on a security-printed
    document (e.g. 76-08 read as 76-09 over the green JPN guilloche), NOT a different number.
    False when either is blank, when they're equal (that's an exact match — use nric_match),
    or when they differ by more than one digit. RELATIONSHIP context only — used to phrase a
    soft 'check the number' nudge more precisely; it never relaxes the strict identity gate."""
    a, b = _canonical_nric(extracted), _canonical_nric(reference)
    if not a or not b or a == b:
        return False
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:                                   # one substitution
        return sum(1 for x, y in zip(a, b) if x != y) == 1
    short, long = (a, b) if la < lb else (b, a)    # one inserted/dropped digit
    i = j = 0
    skipped = False
    while i < len(short) and j < len(long):
        if short[i] == long[j]:
            i += 1
            j += 1
        elif skipped:
            return False
        else:
            skipped = True
            j += 1
    return True


def reference_names(application):
    """Every name that legitimately belongs to this household — the student, whoever they named
    as guardians, and the ROSTER parents/other members.

    This is the reference set for the student-facing document coach: a document carrying one of
    these names is not "somebody else's". It is NOT the wrong-person check that matters for income
    — that one is done properly in income_engine, against the tagged member's own IC.

    The roster parents are here because of #126 (2026-07-13): `guardians` holds whoever the student
    named as their contact, often ONE parent. His mother's own EPF read 'name_mismatch' purely
    because his FATHER was the recorded guardian — a genuine parent's income document flagged as a
    stranger's. The same class of false mismatch was already patched for bills and the STR by
    excluding them from the check; EPF and payslips were left behind, and excluding them would have
    thrown away a check we actually want. Widening the reference set fixes the cause instead.

    ONE definition, used by both the upload path and the re-extract path — they each built this
    list by hand and had already drifted once (the street line, code-health S2 #5c).
    """
    profile = getattr(application, 'profile', None)
    names = [getattr(profile, 'name', '') or '']
    names += [g.get('name', '') for g in (getattr(profile, 'guardians', None) or [])
              if isinstance(g, dict)]
    names += [getattr(application, 'father_name', '') or '',
              getattr(application, 'mother_name', '') or '']
    names += [m.get('name', '') for m in (getattr(application, 'other_family_members', None) or [])
              if isinstance(m, dict)]
    return [n for n in names if n]


def name_match(extracted: str, profile_name: str) -> str:
    """'match' if the token sets are equal after stripping MyKad parentage tokens; 'partial' if one is a
    strict subset of the other (a name omits a middle/surname); 'mismatch' otherwise, or on an empty input.
    TD-408: two names that BOTH carry a connector compare given name with given name and parent with parent."""
    a = canonical_name_tokens(extracted)
    b = canonical_name_tokens(profile_name)
    if not a or not b or patronymic_reversed(extracted, profile_name, name_match):
        return 'mismatch'
    if a == b:
        return 'match'
    if a < b or b < a:
        return 'partial'
    # An OCR space split or glued a name token (RUSHAINDRA ↔ "RUSHAIND RA"), shifting a
    # boundary so the token sets differ — compare the names glued (spelling-exact for
    # identity). Strictly boundary tolerance; spelling differences still mismatch.
    if _glued_equal(extracted, profile_name, fold=False):
        return 'match'
    return 'mismatch'


# ── Relationship / cross-document name matching (transliteration-tolerant) ────────────
# name_match above is EXACT token-set — correct for the student's OWN IC vs the name they
# typed (identity). But the income/relationship checks compare the SAME real person's name
# across TWO documents (the father's name in the student's IC patronymic vs the father's own
# IC; an STR recipient vs the earner's IC), where Malaysian-Tamil/Indian romanisation legit-
# imately varies — Sara**v**anan vs Sara**w**anan (v/w), a doubled letter, a trailing silent
# 'h', or a single-character OCR slip. A false 'mismatch' there wrongly red-flags a real
# family link (the "Sarawanan A/L Supramaniam" call), so those comparisons use the tolerant
# matcher below. It is STRICTLY more lenient than name_match (it can only turn a mismatch into
# a match, never the reverse), so identity — which keeps using name_match — is never weakened.

def _fold_name_token(tok: str) -> str:
    """Conservative romanisation folding so two spellings of ONE Tamil/Indian name agree:
    w→v, collapse a doubled letter (Pilaapparao≈Pilaaparao), drop a trailing silent 'h'."""
    t = tok.replace('w', 'v')
    folded = []
    for ch in t:
        if not folded or folded[-1] != ch:
            folded.append(ch)
    t = ''.join(folded)
    return t[:-1] if len(t) > 2 and t.endswith('h') else t


def _levenshtein(a: str, b: str) -> int:
    """Plain edit distance (no dependency) — used only to allow a single-char token slip."""
    if a == b:
        return 0
    if not a or not b:
        return len(a) or len(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _tokens_close(x: str, y: str) -> bool:
    """True iff two name tokens are the same person's name under romanisation / OCR variance."""
    fx, fy = _fold_name_token(x), _fold_name_token(y)
    if fx == fy:
        return True
    # a single-character difference between LONGER tokens (an OCR slip or spelling variant);
    # short tokens must fold-match exactly (keeps Siva≠Sira, Vani≠Vasu from merging).
    return min(len(fx), len(fy)) >= 5 and _levenshtein(fx, fy) <= 1


def relationship_name_match(extracted: str, reference: str) -> str:
    """Like name_match, but tolerant of Malaysian-Tamil/Indian romanisation + OCR variance —
    for comparing the SAME person's name across two documents (relationship / income-proof
    checks). 'match' when the token sets agree under folding; 'partial' when one is a tolerant
    subset of the other; 'mismatch' otherwise. STRICTLY more lenient than name_match."""
    a = list(canonical_name_tokens(extracted))
    b = list(canonical_name_tokens(reference))
    if not a or not b or patronymic_reversed(extracted, reference, relationship_name_match):   # TD-408
        return 'mismatch'
    small, large = (a, b) if len(a) <= len(b) else (b, a)
    used = [False] * len(large)
    matched = True
    for x in small:
        hit = next((i for i, y in enumerate(large) if not used[i] and _tokens_close(x, y)), None)
        if hit is None:
            matched = False
            break
        used[hit] = True
    if matched:
        return 'match' if len(a) == len(b) else 'partial'
    # Token-by-token failed: an OCR space split a name token (RUSHAINDRA → "RUSHAIND RA")
    # or glued two — the boundary moved, so the token sets can't line up. Compare the names
    # GLUED (folded), which is agnostic to where the spaces fell. Strictly mismatch→match.
    return 'match' if _glued_equal(extracted, reference, fold=True) else 'mismatch'
