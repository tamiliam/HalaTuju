"""
Google Cloud Vision OCR for the IC (MyKad) upload — a SOFT signal, never a
hard block. The admin verify-&-accept (S11a) remains the real identity gate;
this module exists to (a) help the student spot typos at upload time, and
(b) give the admin a hint next to the manual checklist.

Pure helpers (``nric_match``, ``name_match``, the canonical normalisers) are
the testable core — they run pure and require no API key. The actual Vision
call (``extract_mykad``) is mocked in tests and degrades gracefully to an
error dict when the API is unavailable or the SDK isn't installed.
"""
import json
import logging
import math
import re
from typing import Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Stripped before name comparison — common MyKad name suffixes / parentage markers.
_NAME_NOISE = re.compile(
    # MyKad parentage tokens + Malay/English honorifics that prefix a name on official
    # letters (e.g. an offer addressed to "SDRI THEEPICAA …") — stripped so the name
    # matches the profile name regardless of the title.
    # The slash markers tolerate stray whitespace around the slash ("A/ P", "A / P",
    # "A /P") — a student who types their name that way otherwise leaves orphan single
    # letters "a"/"p" in the token set, which makes the EXACT name_match read a clean
    # subset → a false 'partial'/mismatch on the IC + offer letter (#20).
    r"\b(bin|binti|a\s*/\s*l|a\s*/\s*p|al|ap|d\s*/\s*o|s\s*/\s*o|@"
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


def name_match(extracted: str, profile_name: str) -> str:
    """
    'match' if the token sets are equal after stripping MyKad parentage tokens;
    'partial' if one set is a strict subset of the other (so e.g. the profile
    name omits a middle/surname the IC carries, or vice versa);
    'mismatch' otherwise. Empty inputs return 'mismatch'.
    """
    a = canonical_name_tokens(extracted)
    b = canonical_name_tokens(profile_name)
    if not a or not b:
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
    if not a or not b:
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


_NRIC_REGEX = re.compile(r'\b(\d{6}[-\s]?\d{2}[-\s]?\d{4})\b')


def _extract_nric(text: str) -> str:
    """Return the first MyKad-shaped NRIC in the OCR text, or ''."""
    m = _NRIC_REGEX.search(text or '')
    return m.group(1) if m else ''


# MyKad header / label phrases printed on every card — never a person's name.
# Without this, _extract_name's "longest all-caps line" heuristic can grab a card
# label (e.g. "WARGANEGARA MALAYSIA", longer than a short name) instead of the
# name. A line made up ENTIRELY of these tokens is a label, so it's skipped.
_MYKAD_HEADER_TOKENS = frozenset({
    'KAD', 'PENGENALAN', 'MYKAD', 'MALAYSIA', 'WARGANEGARA',
    'LELAKI', 'PEREMPUAN', 'ISLAM',
})


# Parentage markers (A/L, A/P, S/O, D/O, BIN, BINTI) appear in the NAME on a MyKad
# and NEVER in the address — the strongest anchor for the name line. OCR sometimes
# spaces the slash, so tolerate "A / L".
_PARENTAGE_MARKER = re.compile(r'\b(a\s*/\s*[lp]|s\s*/\s*o|d\s*/\s*o|bin|binti)\b', re.IGNORECASE)

# A parentage marker at the END of the name line means the surname was line-broken
# onto the NEXT OCR line (e.g. "THERESA ARUL MARY A/P" then "A.PHILIPS"). When this
# fires we append that next line so the full name is captured, not the truncated one.
_TRAILING_PARENTAGE = re.compile(r'(?:a\s*/\s*[lp]|s\s*/\s*o|d\s*/\s*o|bin|binti)\s*$', re.IGNORECASE)

# OCR sometimes drops the slash entirely, so "...A/P" is read as a bare trailing "AP"
# (likewise A/L→AL, S/O→SO, D/O→DO). These map a mangled FINAL token back to its
# canonical printed form. Matched token-wise (the WHOLE last word), so a glued name
# like VIMAL / KAMAL / BILAL / FAISAL never trips it — only a standalone trailing token.
_MANGLED_MARKERS = {'ap': 'A/P', 'al': 'A/L', 'so': 'S/O', 'do': 'D/O'}


def _trailing_marker_canonical(name: str) -> str:
    """The canonical parentage marker a name ENDS with (real 'A/P', spaced 'A / P',
    BIN/BINTI, or an OCR-mangled slash-less 'AP'/'AL'/'SO'/'DO'), else ''. Token-based
    for the mangled forms so only a standalone final token counts."""
    m = _TRAILING_PARENTAGE.search(name or '')
    if m:
        return re.sub(r'\s+', '', m.group(0)).upper()      # 'A/P', 'BIN', …
    toks = (name or '').split()
    if toks and toks[-1].lower() in _MANGLED_MARKERS:
        return _MANGLED_MARKERS[toks[-1].lower()]
    return ''


def _replace_trailing_marker(name: str, canon: str) -> str:
    """Rewrite the name's trailing marker to its canonical form (fixes the mangled
    'AP' → 'A/P'; a no-op when it was already canonical)."""
    if _TRAILING_PARENTAGE.search(name):
        return _TRAILING_PARENTAGE.sub(canon, name).strip()
    toks = name.split()
    return ' '.join(toks[:-1] + [canon]) if toks else name


def _continuation_surname(name: str, lines: list[str]) -> str:
    """The next OCR line after ``name`` if it reads as a surname fragment (ALL-CAPS
    letters, no digits, not a card header), else '' (no spilled surname)."""
    try:
        idx = lines.index(name)
    except ValueError:
        return ''
    for ln in lines[idx + 1:]:
        if not ln:
            continue
        if any(ch.isdigit() for ch in ln) or ln.upper() != ln:
            return ''
        words = [w for w in re.split(r'[^A-Za-z]+', ln) if w]
        if not words or all(w.upper() in _MYKAD_HEADER_TOKENS for w in words):
            return ''
        return ln
    return ''


def _with_trailing_surname(name: str, lines: list[str]) -> str:
    """If ``name`` ends with a parentage marker (A/L, A/P, BIN, BINTI, S/O, D/O — or the
    OCR-mangled slash-less AP/AL/SO/DO), the surname spilled onto the next OCR line —
    append it and normalise the marker. Resolves the truncated-IC name deterministically
    ("THERESA ARUL MARY A/P" → "…A/P A.PHILIPS"; "THEEPICAA AP" → "THEEPICAA A/P
    SELVAVINAYAGAM"), so the value the student + admin SEE is the full, clean name.
    Only fires when a real continuation line exists — a dangling marker is left as-is."""
    canon = _trailing_marker_canonical(name)
    if not canon:
        return name
    surname = _continuation_surname(name, lines)
    if not surname:
        return name
    return f'{_replace_trailing_marker(name, canon)} {surname}'.strip()


# A parentage marker at the START of the name line means the GIVEN name was line-broken
# onto the PREVIOUS OCR line (e.g. "SARAWANAN" then "A/L SUPRAMANIAM") — the mirror of the
# trailing case. Prepend that previous line so the full name is captured.
_LEADING_PARENTAGE = re.compile(r'^(a\s*/\s*[lp]|s\s*/\s*o|d\s*/\s*o|bin|binti)\b', re.IGNORECASE)


def _preceding_givenname(name: str, lines: list[str]) -> str:
    """The OCR line BEFORE ``name`` if it reads as a given-name fragment (ALL-CAPS letters,
    no digits, not a card header, and NOT itself a marker line — that would be its own name),
    else ''. Mirror of _continuation_surname for the leading break."""
    try:
        idx = lines.index(name)
    except ValueError:
        return ''
    for ln in reversed(lines[:idx]):
        if not ln:
            continue
        if any(ch.isdigit() for ch in ln) or ln.upper() != ln or _PARENTAGE_MARKER.search(ln):
            return ''
        words = [w for w in re.split(r'[^A-Za-z]+', ln) if w]
        if not words or all(w.upper() in _MYKAD_HEADER_TOKENS for w in words):
            return ''
        return ln
    return ''


def _with_broken_name_parts(name: str, lines: list[str]) -> str:
    """Reassemble a line-broken MyKad name deterministically: append a surname spilled onto
    the NEXT line (trailing marker, "THERESA ARUL MARY A/P" → "…A/P A.PHILIPS") AND/OR prepend
    a given name spilled onto the PREVIOUS line (leading marker, "A/L SUPRAMANIAM" with
    "SARAWANAN" above → "SARAWANAN A/L SUPRAMANIAM" — app #61/#31). Both lookups use the
    ORIGINAL marked line, so they compose. Shared by the applicant IC + every parent_ic."""
    full = _with_trailing_surname(name, lines)
    if _LEADING_PARENTAGE.search(name or ''):
        given = _preceding_givenname(name, lines)
        if given:
            full = f'{given} {full}'.strip()
    return full


def _is_name_line(line: str) -> bool:
    """A plausible MyKad name line: all-caps letters + spaces (no digits), not a
    header/label, reasonable length."""
    if not line or len(line) < 6 or any(ch.isdigit() for ch in line):
        return False
    letters = sum(1 for ch in line if ch.isalpha())
    if letters < 4 or letters / max(len(line), 1) < 0.6:
        return False
    if line.upper() != line:
        return False
    words = [w for w in re.split(r'[^A-Za-z]+', line) if w]
    return not (words and all(w.upper() in _MYKAD_HEADER_TOKENS for w in words))


# MyKad header/chrome fragments that, when FUSED INTO a name token (not a standalone word),
# mean the OCR spliced card chrome into the name — e.g. "RAJAANMALAYS" (the "MALAYSIA" header
# bled into the name). The clean-token filter (_MYKAD_HEADER_TOKENS) can't catch this because
# the fragment is glued into one token, so we reject such a read and let the name read as
# UNREADABLE (a re-take) rather than a confident WRONG name (owner 2026-07-08).
_GLUED_HEADER_FRAGMENTS = ('MALAYSIA', 'MALAYS', 'WARGANEGARA', 'PENGENALAN', 'MYKAD')


def _name_looks_garbled(name: str) -> bool:
    """True when a name token carries a fused MyKad header fragment (see above) — a sign the OCR
    mis-read the name line. A standalone header WORD is handled by the clean-token filter and is
    ignored here; only a fragment glued into a longer token trips this."""
    for w in (name or '').upper().split():
        if w in _MYKAD_HEADER_TOKENS:
            continue
        if any(frag in w for frag in _GLUED_HEADER_FRAGMENTS):
            return True
    return False


def _guard_garbled(name: str) -> str:
    """Blank a name read that carries fused card chrome, so it flows to the 'unreadable' path."""
    return '' if _name_looks_garbled(name) else name


def _extract_name(text: str, nric_match_str: str = '') -> str:
    """Find the holder's name on a MyKad. Most-reliable strategy first:
      1. A line carrying a **parentage marker** (A/L, A/P, S/O, D/O, BIN, BINTI) —
         that is the name; addresses/localities never carry these. Fixes the old
         "longest all-caps line" trap where a locality like "TAMAN SRI LAYANG"
         out-ran the real name.
      2. Otherwise (e.g. a Chinese name with no marker) the first name-line right
         AFTER the NRIC line — the MyKad prints the name directly under the NRIC.
      3. Fallback: the longest all-caps name-line anywhere.
    Returns '' if nothing plausible is found."""
    if not text:
        return ''
    lines = [ln.strip() for ln in text.splitlines()]
    candidates = [ln for ln in lines
                  if _is_name_line(ln) and not (nric_match_str and nric_match_str in ln)]
    if not candidates:
        return ''
    # A line carrying a parentage marker — a real one ANYWHERE, or an OCR-mangled
    # slash-less one (AP/AL/SO/DO) as the TRAILING token — is the name line.
    marked = [ln for ln in candidates
              if _PARENTAGE_MARKER.search(ln) or _trailing_marker_canonical(ln)]
    if marked:
        # A marker MID-line is the full name; a marker at the END means the surname spilled
        # onto the next line, at the START means the given name spilled onto the previous line
        # — _with_broken_name_parts reassembles either break.
        return _guard_garbled(_with_broken_name_parts(max(marked, key=len), lines))
    nric_idx = next((i for i, ln in enumerate(lines) if _NRIC_REGEX.search(ln)), -1)
    if nric_idx >= 0:
        for ln in lines[nric_idx + 1:]:
            if ln in candidates:
                return _guard_garbled(_with_broken_name_parts(ln, lines))
    return _guard_garbled(_with_broken_name_parts(max(candidates, key=len), lines))


_MY_POSTCODE = re.compile(r'\b\d{5}\b')

# Words that prefix any MyKad address line — drop them so the displayed value
# is just the address itself. Case-insensitive, anchored at the start of a line.
_ADDRESS_PREFIX_NOISE = re.compile(
    r'^(alamat|address)\s*[:\-]?\s*',
    flags=re.IGNORECASE,
)

# The 13 Malaysian states + 3 federal territories, as printed on MyKad
# (uppercase, sometimes with the `W.P.` prefix). Matched against the line
# directly after the postcode to pull the state through the "looks like a
# one-word name" filter without false positives.
MY_STATES = frozenset({
    'JOHOR', 'KEDAH', 'KELANTAN', 'MELAKA', 'NEGERI SEMBILAN',
    'PAHANG', 'PERAK', 'PERLIS', 'PULAU PINANG', 'SABAH',
    'SARAWAK', 'SELANGOR', 'TERENGGANU',
    'KUALA LUMPUR', 'PUTRAJAYA', 'LABUAN',
    'W.P. KUALA LUMPUR', 'W.P. PUTRAJAYA', 'W.P. LABUAN',
    'WP KUALA LUMPUR', 'WP PUTRAJAYA', 'WP LABUAN',
})


def _is_likely_state(ln: str) -> bool:
    """True iff ``ln`` reads as a Malaysian state line on a MyKad."""
    upper = ln.strip().upper()
    return upper in MY_STATES


# Card-chrome labels printed on the MyKad face that the OCR can splice INTO the
# address block (e.g. "MyKad", "WARGANEGARA", "ISLAM", "LELAKI"/"PEREMPUAN"). A
# line made up ENTIRELY of these is the card's own label, never part of the home
# address — drop it. (Field report: address read as "MyKad, C65B JALAN SEJATI…".)
_ADDRESS_LABEL_TOKENS = frozenset({
    'MYKAD', 'KAD', 'PENGENALAN', 'MALAYSIA', 'WARGANEGARA',
    'LELAKI', 'PEREMPUAN', 'ISLAM', 'AGAMA',
    'PENDAFTARAN', 'NEGARA',
})


def _is_card_label_line(ln: str) -> bool:
    """True iff every word on the line is a MyKad card label (so the whole line is
    card chrome, not address). Case-insensitive."""
    words = [w for w in re.split(r'[^A-Za-z]+', ln or '') if w]
    return bool(words) and all(w.upper() in _ADDRESS_LABEL_TOKENS for w in words)


def _extract_address(text: str) -> str:
    """
    Best-effort MyKad address extraction. The MyKad front shows the holder's
    registered home address as 3 lines: street, ``<5-digit postcode> <city>``,
    and ``<state>``. Strategy: find the line containing a 5-digit Malaysian
    postcode; walk UP to gather the 1-2 preceding address lines, and also
    pick up the very next line if it matches a known Malaysian state.
    Returns ``''`` when no postcode-anchored block is found.

    Soft signal only — admin can spot e.g. an outdated registered address that
    differs from what the student typed in the Story tab. No verdict computed.
    """
    if not text:
        return ''
    lines = [ln.strip() for ln in text.splitlines()]
    # Find the postcode line.
    postcode_idx = -1
    for i, ln in enumerate(lines):
        if not ln:
            continue
        m = _MY_POSTCODE.search(ln)
        if m:
            postcode_idx = i
            break
    if postcode_idx < 0:
        return ''
    block: list[str] = []
    # Walk up at most 4 lines (address block can be 3-4 lines: street +
    # taman/kampung + postcode/city + state). The state line is captured
    # separately below (it lives BELOW the postcode line).
    for j in range(max(0, postcode_idx - 4), postcode_idx + 1):
        ln = lines[j]
        if not ln:
            continue
        # Skip the NRIC line.
        if _NRIC_REGEX.search(ln):
            continue
        # Skip card-chrome labels ("MyKad", "WARGANEGARA", "ISLAM", …) — never address.
        if _is_card_label_line(ln):
            continue
        # Skip the name line. We identify it by the presence of a Malaysian
        # parentage marker (A/L, A/P, BIN, BINTI, S/O, D/O, @) — addresses
        # never have these. NOTE: this misses Chinese names without markers
        # (e.g. "TAN AH KAU") which would slip into the address; acceptable
        # soft-signal noise. The earlier "all-caps no-digits → drop" filter
        # was too aggressive — it dropped legit address lines like
        # "TAMAN SEMANGAT" / "KAMPUNG ABC" / "BANDAR XYZ".
        if _NAME_NOISE.search(ln):
            continue
        # Strip a leading "Alamat" / "Address" label if Vision read one.
        ln = _ADDRESS_PREFIX_NOISE.sub('', ln).strip()
        if ln:
            block.append(ln)
    # Look one line DOWN for the state (MyKad puts it right after the postcode).
    if postcode_idx + 1 < len(lines):
        next_ln = lines[postcode_idx + 1].strip()
        if next_ln and _is_likely_state(next_ln):
            block.append(next_ln)
    # Deduplicate while preserving order (Vision occasionally repeats a line).
    seen: set = set()
    deduped: list[str] = []
    for ln in block:
        key = ln.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ln)
    return ', '.join(deduped)


# ── PDF document intake (document-intake hardening) ────────────────────────────
# Students upload scan-to-PDF (CamScanner) and native digital PDFs (EPF, payslip,
# offer letter). Google Vision's inline image OCR cannot decode PDF bytes ("Bad
# image data."), so we handle PDFs ourselves:
#   - DIGITAL PDF → read the embedded text layer (pypdf) — free, perfect fidelity.
#   - SCANNED PDF → rasterise page 1 (pypdfium2 + Pillow) → feed the image to Vision.
# Both libs are OPTIONAL: if absent (or the PDF is corrupt/encrypted), a PDF
# degrades to "unreadable" — today's behaviour — rather than crashing.
_PDF_MAGIC = b'%PDF-'
_MIN_PDF_TEXT = 25      # chars of real text → treat as a digital PDF (skip Vision)
_RASTER_DPI = 200


def _is_pdf(content_type: str, data: bytes) -> bool:
    if (content_type or '').lower().split(';')[0].strip() == 'application/pdf':
        return True
    return bool(data) and data[:5] == _PDF_MAGIC


def _pdf_text_layer(data: bytes) -> str:
    """The concatenated text layer of a PDF (all pages). '' if none / encrypted /
    library missing — caller then falls back to rasterise+OCR."""
    try:
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt('')
            except Exception:  # noqa: BLE001
                return ''
        return '\n'.join((p.extract_text() or '') for p in reader.pages).strip()
    except Exception as e:  # noqa: BLE001
        logger.warning('PDF text-layer extraction failed: %s', e)
        return ''


def _pdf_first_page_png(data: bytes) -> Optional[bytes]:
    """Rasterise page 1 of a PDF to PNG bytes (~200 DPI). None on failure /
    library missing. Page 1 only — bounds the Vision cost to 1 unit per doc."""
    try:
        import io

        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(data)
        try:
            if len(pdf) == 0:
                return None
            pil = pdf[0].render(scale=_RASTER_DPI / 72.0).to_pil()
            buf = io.BytesIO()
            pil.convert('RGB').save(buf, format='PNG')
            return buf.getvalue()
        finally:
            pdf.close()
    except Exception as e:  # noqa: BLE001
        logger.warning('PDF rasterise failed: %s', e)
        return None


def _vision_document_text(image_bytes: bytes) -> dict:
    """Google Vision DOCUMENT_TEXT_DETECTION on *image* bytes → ``{'text', 'error'}``.
    The single seam the OCR functions share (and tests patch). Graceful — returns
    an error dict, never raises. ``error`` is None on success."""
    try:
        from google.cloud import vision  # type: ignore
    except ImportError:
        return {'text': '', 'error': 'AI module not installed'}
    api_key = getattr(settings, 'GOOGLE_CLOUD_VISION_API_KEY', '') or ''
    try:
        client = (vision.ImageAnnotatorClient(client_options={'api_key': api_key})
                  if api_key else vision.ImageAnnotatorClient())
        resp = client.document_text_detection(image=vision.Image(content=image_bytes))
        if resp.error and resp.error.message:
            return {'text': '', 'error': resp.error.message[:200]}
        return {'text': resp.full_text_annotation.text if resp.full_text_annotation else '', 'error': None}
    except Exception as e:  # noqa: BLE001 — graceful: never propagate to a 500
        logger.warning('Vision OCR failed: %s', e)
        return {'text': '', 'error': str(e)[:200]}


def _vision_words(data: bytes, content_type: str = '') -> dict:
    """Google Vision DOCUMENT_TEXT_DETECTION → per-WORD boxes (kept, not flattened) for
    positional table parsing — used by the results-slip deterministic reader to pair
    each subject with the grade on its own row. Returns ``{'words': [{text, cx, cy, h}],
    'error'}``; rasterises a PDF first. Graceful — never raises. (A separate seam from
    ``_vision_document_text`` so tests can patch it independently.)"""
    img, _mime = _as_image_for_gemini(data, content_type)
    if img is None:
        return {'words': [], 'text': '', 'error': 'no image'}
    try:
        from google.cloud import vision  # type: ignore
    except ImportError:
        return {'words': [], 'text': '', 'error': 'AI module not installed'}
    api_key = getattr(settings, 'GOOGLE_CLOUD_VISION_API_KEY', '') or ''
    try:
        client = (vision.ImageAnnotatorClient(client_options={'api_key': api_key})
                  if api_key else vision.ImageAnnotatorClient())
        resp = client.document_text_detection(image=vision.Image(content=img))
        if resp.error and resp.error.message:
            return {'words': [], 'text': '', 'error': resp.error.message[:200]}
        # The SAME response carries the flattened text (full_text_annotation) — return it
        # too, so one billable call can serve both the positional parsers (words) and the
        # text consumers (name/address match, label parsers). See ocr_document_full.
        text = resp.full_text_annotation.text if resp.full_text_annotation else ''
        words = []
        # text_annotations[0] is the whole text; [1:] are individual words with boxes.
        for ann in resp.text_annotations[1:]:
            vs = ann.bounding_poly.vertices
            xs = [v.x for v in vs]
            ys = [v.y for v in vs]
            if not xs or not ys:
                continue
            # Baseline angle (top edge vertex0→vertex1, degrees): 0 upright, ~±90 when the
            # photo is sideways. The deterministic parser de-rotates the table by this so a
            # rotated slip still parses instead of falling back to Gemini (which transposes).
            angle = None
            if len(vs) >= 2:
                angle = math.degrees(math.atan2(vs[1].y - vs[0].y, vs[1].x - vs[0].x))
            words.append({'text': ann.description,
                          'cx': sum(xs) / len(xs), 'cy': sum(ys) / len(ys),
                          'h': max(ys) - min(ys), 'angle': angle})
        return {'words': words, 'text': text, 'error': None}
    except Exception as e:  # noqa: BLE001 — graceful
        logger.warning('Vision word OCR failed: %s', e)
        return {'words': [], 'text': '', 'error': str(e)[:200]}


def extract_mykad(data: bytes, content_type: str = '') -> dict:
    """
    OCR a MyKad and return ``{'nric', 'name', 'address', 'error'}``. Accepts an
    image OR a PDF (a scanned MyKad — never a text PDF, so it is rasterised to an
    image first). Never raises.
    """
    if not data:
        return {'nric': '', 'name': '', 'address': '', 'error': 'empty image'}
    if _is_pdf(content_type, data):
        img = _pdf_first_page_png(data)
        if img is None:
            return {'nric': '', 'name': '', 'address': '', 'error': 'Bad image data.'}
        data = img
    r = _vision_document_text(data)
    if r['error']:
        return {'nric': '', 'name': '', 'address': '', 'error': r['error']}
    text = r['text']
    nric = _extract_nric(text)
    return {
        'nric': nric,
        'name': _extract_name(text, nric),
        'address': _extract_address(text),
        'error': None,
    }


def _fetch_image_bytes(storage_path: str) -> Optional[bytes]:
    """Download a document's raw bytes from Supabase Storage (image OR PDF).
    Returns None on failure."""
    if not storage_path:
        return None
    try:
        from urllib.request import urlopen
        from .storage import create_signed_download_url
        url = create_signed_download_url(storage_path)
        if not url:
            return None
        with urlopen(url, timeout=10) as r:
            return r.read()
    except Exception as e:  # noqa: BLE001
        logger.warning('IC image fetch failed for %s: %s', storage_path, e)
        return None


# ── IC Gemini second-opinion (cost-gated) ──────────────────────────────────────
# The deterministic MyKad read (extract_mykad) is free but brittle: it can truncate
# marker-less names, leak card labels into the address, and trip on a single
# blurry/misread NRIC digit. When the cheap read is SHAKY (a core field missing, or
# it disagrees with what the student typed), we ask Gemini to read the card IMAGE as
# a clean second opinion. Cost-gated: it fires only on low-confidence reads, so the
# common clean upload stays free. Reuses the mockable ``_call_gemini_json`` seam.
_IC_GEMINI_SCHEMA = {'type': 'object', 'properties': {
    'nric': {'type': 'string'}, 'name': {'type': 'string'}, 'address': {'type': 'string'}}}

_IC_GEMINI_PROMPT = (
    'This is a photo of a Malaysian MyKad identity card. Read it carefully and return: '
    '"nric" = the holder\'s identity number (12 digits, formatted ######-##-####); '
    '"name" = their FULL name EXACTLY as printed, including any parentage marker '
    '(A/L, A/P, BIN, BINTI, S/O, D/O) AND the surname that follows it; '
    '"address" = their home address only (street, postcode, city, state) WITHOUT card '
    'labels such as "MyKad", "WARGANEGARA", "ISLAM", "LELAKI" or "PEREMPUAN". '
    'If a field is unclear, leave it empty. Do NOT invent or guess.'
)

# ── Genuineness fingerprint (verification-assurance roadmap, Sprint 1) ─────────
# A SEPARATE concern from field extraction: does the image look like a genuine photo/scan
# of a physical MyKad, or a typed sheet / screenshot / printout? Multimodal — Gemini inspects
# the picture for the card's standard fingerprints: the header words it can't omit AND the
# physical face/chip/card-look a typed fake can't carry. We don't claim certainty — we read a
# handful of independent markers and call it "highly probable" or not. SOFT: never blocks; the
# reviewer is the authority. Validated on our real ICs 2026-06-12 (genuine = all 8 markers; a
# typed fake carried only the words someone typed and failed every physical one → 'suspect').
# IC genuineness (constants + ic_genuineness) now lives in genuineness/ic.py and is
# re-exported at the end of this module (see the genuineness/ package).


def _as_image_for_gemini(data: bytes, content_type: str):
    """Return ``(image_bytes, mime_type)`` Gemini can read, or ``(None, '')``. A PDF
    (scanned MyKad) is rasterised to PNG page 1 first."""
    if not data:
        return None, ''
    if _is_pdf(content_type, data):
        png = _pdf_first_page_png(data)
        return (png, 'image/png') if png else (None, '')
    ct = (content_type or '').lower().split(';')[0].strip()
    return data, (ct if ct.startswith('image/') else 'image/jpeg')


def _should_gemini_ic(result: dict, profile) -> bool:
    """Escalate to the Gemini second opinion only when the deterministic read is
    low-confidence: a core field is missing, OR it disagrees with the profile the
    student typed (a likely OCR misread, not necessarily a real mismatch). A clean
    read that matches the profile never escalates — keeping most uploads free."""
    if not getattr(settings, 'IC_GEMINI_FALLBACK_ENABLED', True):
        return False
    nric = (result.get('nric') or '').strip()
    name = (result.get('name') or '').strip()
    if not nric or not name:
        return True
    p_nric = (getattr(profile, 'nric', '') or '') if profile else ''
    p_name = (getattr(profile, 'name', '') or '') if profile else ''
    if p_nric and not nric_match(nric, p_nric):
        return True
    if p_name and name_match(name, p_name) == 'mismatch':
        return True
    return False


def _gemini_ic_second_opinion(data: bytes, content_type: str) -> dict:
    """Ask Gemini to re-read the MyKad image → {'nric','name','address'} or {'_error'}.
    Never raises (the seam degrades gracefully)."""
    img, mime = _as_image_for_gemini(data, content_type)
    if img is None:
        return {'_error': 'no image for gemini'}
    return _call_gemini_json(_IC_GEMINI_PROMPT, _IC_GEMINI_SCHEMA, image=img, mime_type=mime)


def _merge_ic_reads(det: dict, g: dict, profile) -> dict:
    """Fold the Gemini read into the deterministic one — conservatively. Gemini wins a
    CORE field (nric/name) only when it agrees with the profile and the deterministic
    read did not (or the deterministic read was empty); the soft address always prefers
    the cleaner Gemini value when present. So a confident deterministic match is never
    overridden by the model."""
    p_nric = (getattr(profile, 'nric', '') or '') if profile else ''
    p_name = (getattr(profile, 'name', '') or '') if profile else ''
    out = dict(det)
    gn = (g.get('nric') or '').strip()
    if gn:
        if not out.get('nric'):
            out['nric'] = gn
        elif p_nric and nric_match(gn, p_nric) and not nric_match(out['nric'], p_nric):
            out['nric'] = gn   # Gemini recovered a digit the OCR misread
    gname = (g.get('name') or '').strip()
    if gname:
        if not out.get('name'):
            out['name'] = gname
        elif (p_name and name_match(gname, p_name) != 'mismatch'
              and name_match(out['name'], p_name) == 'mismatch'):
            out['name'] = gname
    gaddr = (g.get('address') or '').strip()
    if gaddr:
        out['address'] = gaddr   # cleaner read (no card labels / truncation)
    return out


# Supporting-document genuineness (str / birth_certificate / epf) now lives in
# genuineness/supporting_doc.py and is re-exported at the end of this module.


def run_vision_for_document(doc) -> dict:
    """
    Run Vision on an ``ApplicantDocument`` (expected ``doc_type='ic'``) and
    persist the result on the row. Returns the result dict. Never raises;
    failures land in ``vision_error`` and the doc still saves.

    When the deterministic read is low-confidence (see ``_should_gemini_ic``), a
    cost-gated Gemini second opinion re-reads the card image and is merged in.

    Flag-gated genuineness fingerprint (``DOC_GENUINENESS_CHECK_ENABLED``): a soft
    "does this look like a real MyKad?" multimodal read, stored in
    ``vision_fields['authenticity']`` (no migration). Never blocks.
    """
    image = _fetch_image_bytes(doc.storage_path)
    if image is None:
        result = {'nric': '', 'name': '', 'address': '', 'error': 'could not fetch image'}
    else:
        result = extract_mykad(image, doc.content_type)
        if not result.get('error'):
            profile = getattr(doc.application, 'profile', None)
            if _should_gemini_ic(result, profile):
                g = _gemini_ic_second_opinion(image, doc.content_type)
                if not g.get('_error'):
                    result = _merge_ic_reads(result, g, profile)
    doc.vision_nric = result['nric'] or ''
    doc.vision_name = result['name'] or ''
    doc.vision_address = result.get('address', '') or ''
    doc.vision_error = result['error'] or ''
    doc.vision_run_at = timezone.now()
    update_fields = ['vision_nric', 'vision_name', 'vision_address', 'vision_error', 'vision_run_at']
    if image is not None and getattr(settings, 'DOC_GENUINENESS_CHECK_ENABLED', False):
        auth = ic_genuineness(image, doc.content_type)
        if auth:
            vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
            vf['authenticity'] = auth
            doc.vision_fields = vf
            update_fields.append('vision_fields')
    doc.save(update_fields=update_fields)
    return result


# ── Generic supporting-document soft checks (S: results slip / income / bills) ──
# Arbitrary documents aren't MyKad-structured, so instead of field extraction we
# do a *presence* check on the full OCR text: does an expected name (or address)
# appear anywhere? Tolerant + naturally soft — exactly right for a non-blocking
# nudge to the student + the interviewer.

def extract_text(data: bytes, content_type: str = '') -> dict:
    """Generic full-text OCR. Accepts an image OR a PDF: a DIGITAL PDF is read via
    its text layer (no Vision call — free); a SCANNED PDF is rasterised (page 1) →
    Vision. ``{'text': str, 'error': str|None}``. Never raises."""
    if not data:
        return {'text': '', 'error': 'empty image'}
    if _is_pdf(content_type, data):
        text = _pdf_text_layer(data)
        if len(text) >= _MIN_PDF_TEXT:
            return {'text': text, 'error': None}   # digital PDF — no billable Vision call
        img = _pdf_first_page_png(data)
        if img is None:
            return {'text': '', 'error': 'Bad image data.'}
        data = img
    return _vision_document_text(data)


def name_present(text: str, names) -> bool:
    """True if any of ``names`` (token-set, MyKad connectors stripped) is fully
    contained in the OCR ``text``. Order / case / extra words in the doc are fine."""
    text_tokens = canonical_name_tokens(text)
    if not text_tokens:
        return False
    for n in names:
        nt = canonical_name_tokens(n)
        if nt and nt.issubset(text_tokens):
            return True
    return False


# Common Malaysian address-word abbreviations → canonical, applied to BOTH the profile and the
# bill before comparison so "JLN/ABD/TMN/LRG/SG/BKT" match "Jalan/Abdul/Taman/Lorong/Sungai/Bukit".
_ADDR_ABBREV = {
    'jln': 'jalan', 'jl': 'jalan', 'lrg': 'lorong', 'lbh': 'lebuh', 'lbuh': 'lebuh',
    'psn': 'persiaran', 'lkg': 'lengkok', 'tmn': 'taman', 'bdr': 'bandar', 'bkt': 'bukit',
    'kg': 'kampung', 'kpg': 'kampung', 'kmpg': 'kampung', 'sg': 'sungai', 'pkn': 'pekan',
    'blk': 'blok', 'tkt': 'tingkat', 'abd': 'abdul', 'abdl': 'abdul',
    'moh': 'mohamad', 'mhd': 'mohamad', 'muhd': 'mohamad',
}
# Road / structural words carrying NO identity — dropped from the STREET-NAME comparison so a
# match hinges on the road NAME + numbers + taman (not the word "jalan"). Stored canonical.
_ADDR_GENERIC = {
    'no', 'jalan', 'taman', 'lorong', 'lebuh', 'lebuhraya', 'persiaran', 'lengkok', 'bandar',
    'kampung', 'lot', 'blok', 'block', 'tingkat', 'aras', 'unit', 'fasa', 'phase', 'seksyen',
    'presint', 'precinct', 'pt', 'ptd', 'pekan',
}
# Road words that mark the END of the leading house/lot-number zone (everything BEFORE the first
# of these is the house number; after it is the road name + road number).
_ROAD_HEAD = {'jalan', 'lorong', 'lebuh', 'lebuhraya', 'persiaran', 'lengkok', 'taman',
              'bandar', 'kampung'}


def _addr_norm(tok: str) -> str:
    return _ADDR_ABBREV.get(tok, tok)


def _norm_house_no(tok: str) -> str:
    """Normalise a house/lot number for comparison: split on separators, strip leading zeros per
    segment, re-join. So '100-03-03' and '100-3-3' both → '100_3_3'; '3' → '3'."""
    segs = [s.lstrip('0') or '0' for s in re.split(r'[^a-z0-9]+', tok.lower()) if s]
    return '_'.join(segs)


def _house_numbers(s: str) -> set:
    """The leading house/lot number(s) — the alnum chunks containing a digit that sit BEFORE the
    first road word. 'No 3 Jalan…'→{'3'}; '7 Jln Gangsa 9'→{'7'} (the road number '9' is after
    'jalan'); '100-3-3 Puncak Jalan…'→{'100_3_3'}."""
    out = set()
    for raw in re.findall(r'[a-z0-9][a-z0-9/\-]*', (s or '').lower()):
        if _addr_norm(raw) in _ROAD_HEAD:
            break
        if any(ch.isdigit() for ch in raw):
            out.add(_norm_house_no(raw))
    return out


def _street_name_tokens(s: str) -> set:
    """Distinctive street/taman NAME tokens: abbrev-normalised, alnum (road numbers like '9' /
    '5','8' from '5/8' / '3a' kept), generic road words dropped — so only the road NAME + taman
    name + numbers remain ('Jalan Sultan Abdul Samad 11' → {sultan, abdul, samad, 11})."""
    toks = {_addr_norm(t) for t in re.findall(r'[a-z0-9]+', (s or '').lower())}
    return {t for t in toks if t and t not in _ADDR_GENERIC}


def address_match(doc_text: str, *, postcode: str = '', city: str = '', street: str = '') -> str:
    """Weighted home-address verdict for a utility bill — ``'found'`` | ``'unconfirmed'`` |
    ``'mismatch'``.

    The HOUSE NUMBER is the anchor; the STREET name confirms the road; the POSTCODE **or** CITY
    confirms the locality (either one — a bill prints one or the other, and a town has two names:
    Port/Pelabuhan Klang, Skudai/Johor Bahru, Georgetown/P.Pinang). Any TWO of the three matching
    is a confident ``found``; exactly one is ``unconfirmed`` (eyeball at interview, never a hard
    miss); a genuinely different home (none match AND the bill prints a DIFFERENT 5-digit postcode)
    is ``mismatch``. Abbreviations are normalised on both sides (Jln/Jalan, Abd/Abdul, SG/Sungai…).
    When no street is on file, fall back to locality only: postcode AND city → found."""
    doc = doc_text or ''
    pc = re.sub(r'\D', '', postcode or '')
    pc_ok = len(pc) == 5 and pc in re.sub(r'\D', '', doc)
    city_toks = {_addr_norm(t) for t in re.findall(r'[a-z]+', (city or '').lower())}
    doc_words = {_addr_norm(t) for t in re.findall(r'[a-z]+', doc.lower())}
    city_ok = bool(city_toks) and bool(city_toks & doc_words)
    doc_pcs = set(re.findall(r'\b\d{5}\b', doc))
    different_pc = len(pc) == 5 and bool(doc_pcs) and pc not in doc_pcs

    prof_house = _house_numbers(street)
    prof_street = _street_name_tokens(street)

    if not prof_house and not prof_street:
        # No street on file — locality-only fallback: require BOTH postcode and city to confirm.
        if pc_ok and city_ok:
            return 'found'
        if pc_ok or city_ok:
            return 'unconfirmed'
        return 'mismatch' if different_pc else 'unconfirmed'

    house_ok = bool(prof_house & _house_numbers(doc))
    overlap = prof_street & _street_name_tokens(doc)
    street_ok = bool(prof_street) and len(overlap) >= max(2, (len(prof_street) + 1) // 2)
    locality_ok = pc_ok or city_ok

    score = int(house_ok) + int(street_ok) + int(locality_ok)
    if score >= 2:
        return 'found'
    if score == 1:
        return 'unconfirmed'
    return 'mismatch' if different_pc else 'unconfirmed'


def address_present(text: str, *, postcode: str = '', city: str = '', street: str = '') -> bool:
    """Back-compat bool wrapper — True only on a confident ``found``."""
    return address_match(text, postcode=postcode, city=city, street=street) == 'found'


def ocr_document(doc) -> dict:
    """Fetch + OCR a document once. Returns {text, error}. Pass the result to
    run_vision_match_for_document / run_field_extraction_for_document as ``ocr=``
    so the same upload OCRs only once."""
    image = _fetch_image_bytes(doc.storage_path)
    return {'text': '', 'error': 'could not fetch image'} if image is None else extract_text(image, doc.content_type)


def ocr_document_full(doc) -> dict:
    """Fetch + OCR a document ONCE for the whole upload/re-run pipeline: at most one
    download and one billable Vision call serve every consumer. Returns
    ``{'text', 'words', 'image', 'error'}``:

    - ``text`` — flattened OCR text (name/address match, label parsers, genuineness).
    - ``words`` — per-word boxes for the positional slip/BC parsers, or **None when not
      computed** (digital-PDF text-layer path, or a pre-OCR failure) — a consumer that
      needs words then makes its own read, exactly as before.
    - ``image`` — the fetched bytes, so downstream never re-downloads the blob.

    A DIGITAL PDF keeps the free text-layer path (no Vision call at all — the historic
    behaviour of ``ocr_document``); one Vision ``document_text_detection`` response
    otherwise carries both the text and the word boxes (previously two identical
    billable calls per slip/BC upload — code-health S2 #22)."""
    image = _fetch_image_bytes(doc.storage_path)
    if image is None:
        return {'text': '', 'words': None, 'image': None, 'error': 'could not fetch image'}
    if _is_pdf(doc.content_type, image):
        text = _pdf_text_layer(image)
        if len(text) >= _MIN_PDF_TEXT:
            return {'text': text, 'words': None, 'image': image, 'error': None}
    r = _vision_words(image, doc.content_type)
    return {'text': r.get('text') or '', 'words': r.get('words'), 'image': image,
            'error': r.get('error')}


def read_text_document(doc, *, ocr=None) -> dict:
    """OCR a FREE-TEXT document (e.g. the statement_of_intent / letter of intent) and store
    its plain text in ``vision_fields['text']`` for downstream analysis (Check 2 reads it for
    motivation + clues the structured form doesn't capture). Soft — never blocks an upload.

    Clobber guard (code-health S2 #5): the blob on a row is immutable, so a run that reads
    NOTHING where a previous run read text is OUR failure (Storage/OCR outage) — keep the
    stored text instead of wiping it."""
    from django.utils import timezone
    ocr = ocr if ocr is not None else ocr_document(doc)
    new_text = (ocr.get('text') or '').strip()
    prior = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    if not new_text and (prior.get('text') or '').strip():
        logger.warning('read_text_document: kept stored text for doc %s (re-run read nothing: %s)',
                       doc.id, ocr.get('error') or 'empty read')
        return prior
    doc.vision_fields = {'text': new_text,
                         'student_verdict': 'read', 'error': ocr.get('error', '') or ''}
    doc.vision_fields_run_at = timezone.now()
    doc.save(update_fields=['vision_fields', 'vision_fields_run_at'])
    return doc.vision_fields


def run_vision_match_for_document(doc, *, names, postcode='', city='', street='', check_address=False, ocr=None) -> dict:
    """OCR a supporting document and record soft verdicts: does an expected name
    appear (``vision_name_match``), and — for bills — does the home address appear
    (``vision_address_match``)? Verdicts: 'found' / 'not_found' / 'unreadable'.
    Never blocks, never raises. Pass ``ocr`` to reuse a prior OCR pass."""
    r = ocr if ocr is not None else ocr_document(doc)
    if r['error'] or not (r['text'] or '').strip():
        # Clobber guard (code-health S2 #5): the blob is immutable — a no-text read where a
        # previous run reached a real verdict is OUR failure (Storage/OCR outage). Keep the
        # stored verdicts (a re-run must never downgrade 'found' to 'unreadable' on an outage).
        if doc.vision_name_match not in ('', 'unreadable'):
            logger.warning('run_vision_match: kept stored verdicts for doc %s (re-run failed: %s)',
                           doc.id, r['error'] or 'no text read')
            return {'name_match': doc.vision_name_match, 'address_match': doc.vision_address_match,
                    'error': r['error'] or 'no text read', 'stale_kept': True}
        doc.vision_name_match = 'unreadable'
        doc.vision_address_match = 'unreadable' if check_address else ''
        doc.vision_error = r['error'] or 'no text read'
    else:
        doc.vision_name_match = 'found' if name_present(r['text'], names) else 'not_found'
        doc.vision_address_match = (
            address_match(r['text'], postcode=postcode, city=city, street=street)
            if check_address else ''
        )
        doc.vision_error = ''
    doc.vision_run_at = timezone.now()
    doc.save(update_fields=['vision_name_match', 'vision_address_match', 'vision_error', 'vision_run_at'])
    return {'name_match': doc.vision_name_match, 'address_match': doc.vision_address_match, 'error': doc.vision_error}


# ── Document-assist: Gemini field extraction over messy supporting docs ────────
# Gemini PICKS the fields from arbitrary layouts (better than token-presence on
# the raw text); the deterministic matchers then DECIDE the verdict (so the
# student-facing verdict can never be a Gemini hallucination). Runs automatically
# on upload (see DocumentListCreateView), soft + never blocking.

GEMINI_EXTRACT_DOC_TYPES = frozenset({
    'salary_slip', 'epf', 'water_bill', 'electricity_bill', 'results_slip', 'offer_letter',
    'str', 'guardianship_letter', 'birth_certificate', 'bank_statement',
    # V1: the declared-informal-income supporting doc must be READ, not merely present.
    'income_support_doc',
    # V4: promoted academic-completeness docs — read the CGPA / school so the officer sees it.
    'school_leaving_cert', 'semester_result',
})

_STR = {'type': 'string'}
# #5: which of the three real STR artifacts this is (closed set — no open-ended "other"),
# so the extractor reads each layout's fields from the right place + the officer sees the source.
_STR_SOURCE = {'type': 'string', 'enum': ['letter', 'semakan_status', 'dashboard', 'unknown']}


def _doc_schema(props: dict) -> dict:
    """An object schema with the given string fields + a shared warnings array."""
    out = dict(props)
    out['warnings'] = {'type': 'array', 'items': {'type': 'string'}}
    return {'type': 'object', 'properties': out}


_FIELD_SCHEMAS = {
    # Income Check-1: read the earner's NRIC too, so a member-tagged slip can be
    # cross-checked against that member's IC (name + IC number), not the student.
    # Income Check-1 (STR): the recipient (name + NRIC) is the household earner, plus the
    # CURRENCY facts — status (Lulus/diluluskan/…) + the STR year — since a stale STR no
    # longer proves B40. Covers both the MOF letter and the MySTR portal screenshot.
    'str': _doc_schema({'recipient_name': _STR, 'recipient_nric': _STR, 'status': _STR,
                        'year': _STR, 'amount': _STR, 'source_type': _STR_SOURCE}),
    'salary_slip': _doc_schema({'name': _STR, 'nric': _STR, 'employer': _STR, 'currency': _STR,
                                'gross_income': _STR, 'net_income': _STR,
                                'gross_income_ytd': _STR, 'period': _STR}),
    'epf': _doc_schema({'name': _STR, 'nric': _STR, 'employer': _STR, 'employer_number': _STR,
                        'latest_balance': _STR, 'last_contribution': _STR,
                        'monthly_contribution': _STR, 'months_counted': _STR,
                        'employer_contribution_total': _STR, 'employee_contribution_total': _STR,
                        'contribution_status': _STR, 'statement_date': _STR, 'address': _STR,
                        'year': _STR}),
    # Income Check-1: utility bills carry the home address + the MONTHLY charge + any
    # UNPAID balance (a high outstanding amount is a soft hardship signal).
    'water_bill': _doc_schema({'name': _STR, 'address': _STR, 'amount': _STR,
                               'unpaid_balance': _STR, 'billing_period': _STR}),
    'electricity_bill': _doc_schema({'name': _STR, 'address': _STR, 'amount': _STR,
                                     'unpaid_balance': _STR, 'billing_period': _STR}),
    # S2: read the GRADE against each subject (not just the subject list) so the
    # academic engine can verify the typed grades against the slip.
    # Check-1 fix: also read the Malay BAND phrase per subject (Cemerlang Tertinggi /
    # Cemerlang Tinggi / …) — a SECOND, redundant encoding of the grade printed on the
    # slip. The academic engine cross-checks letter↔band to catch row-transposition
    # misreads (e.g. Matematik A vs Sains A+ swapped) and degrades to 'check' on conflict.
    'results_slip': _doc_schema({'candidate_name': _STR, 'exam': _STR,
                                 'results': {'type': 'array', 'items': {'type': 'object',
                                             'properties': {'subject': _STR, 'grade': _STR,
                                                            'band': _STR}}}}),
    # Pathway Check-1: the offer letter's facts, differentiated. candidate_nric is the
    # strong identity check (matched against the profile NRIC); offer_date is the ISSUE date
    # (for currency). Pathway type now comes free from the genuineness scorer, so the
    # per-pathway academic fields are captured explicitly (LOCKED contract 2026-06-18):
    # STPM/Matric → college (institution) + stream (Bidang/Jurusan); Poly → programme
    # (+ institusi); PISMP → bidang_pengkhususan (+ elektif + aliran). reporting_date is the
    # report/registration date. institution/programme/issuer kept for the live Layer-2 matcher.
    'offer_letter': _doc_schema({'candidate_name': _STR, 'candidate_nric': _STR,
                                 'programme': _STR, 'institution': _STR, 'issuer': _STR,
                                 'offer_date': _STR, 'intake': _STR, 'candidate_address': _STR,
                                 'stream': _STR, 'reporting_date': _STR, 'reporting_date_label': _STR,
                                 'bidang_pengkhususan': _STR, 'elektif': _STR, 'aliran': _STR}),
    # Income Check-1: the Birth Certificate links the income earner (mother) to the
    # student. Read the child + both parents' names AND their NRICs (the strong match).
    'birth_certificate': _doc_schema({'bc_child_name': _STR, 'bc_child_nric': _STR,
                                      'bc_mother_name': _STR, 'bc_mother_nric': _STR,
                                      'bc_father_name': _STR, 'bc_father_nric': _STR}),
    # Income Check-1: a guardianship order / authorisation letter ties the legal guardian
    # to the student (the ward). Read the guardian + ward names + the guardian's NRIC.
    'guardianship_letter': _doc_schema({'guardian_name': _STR, 'guardian_nric': _STR,
                                        'ward_name': _STR, 'doc_kind': _STR}),
    # Post-award bursary payout: the student's bank statement / passbook. Read the bank
    # name, the account number, and the account-holder name as printed — the holder MUST
    # be the student (checked deterministically, never by the AI).
    'bank_statement': _doc_schema({'bank_name': _STR, 'account_number': _STR,
                                   'account_holder': _STR}),
    # V1 — the declared-informal-income supporting doc (Phase 2A D1: employer/wage letter,
    # bank statements showing income, OR a community/penghulu letter). Read WHO it is for
    # (the earner, not the student), the amount + period it evidences, and WHAT kind of
    # letter it is. A blank/wrong image reads no fields → student_verdict 'wrong_doc' →
    # does NOT clear the declared-income gap (see income_engine.has_income_support_doc).
    'income_support_doc': _doc_schema({'name': _STR, 'nric': _STR, 'amount': _STR,
                                       'period': _STR, 'issuer': _STR, 'kind': _STR}),
    # V4 — a school-leaving certificate / testimonial (surat berhenti sekolah): the student's name,
    # the school, and the leaving year. The name is matched against the student (officer chip).
    'school_leaving_cert': _doc_schema({'name': _STR, 'school': _STR, 'year': _STR}),
    # V4 — a current-semester result slip for a continuing student: institution, programme, the
    # semester label, and the CGPA (the officer's current-performance read).
    'semester_result': _doc_schema({'name': _STR, 'nric': _STR, 'institution': _STR,
                                    'programme': _STR, 'semester': _STR, 'cgpa': _STR}),
}

# Which extracted field holds the person's name (for the deterministic verdict).
_NAME_FIELD = {
    'salary_slip': 'name', 'epf': 'name', 'water_bill': 'name', 'electricity_bill': 'name',
    'results_slip': 'candidate_name', 'offer_letter': 'candidate_name', 'str': 'recipient_name',
    'bank_statement': 'account_holder',
    # V4 — a school-leaving cert names the STUDENT (matched against them). A semester_result has
    # no student-name field (institution/programme/cgpa) → no name-match, the read is the signal.
    'school_leaving_cert': 'name',
}

# Optional per-doc-type instruction appended to the extraction prompt.
_DOC_HINTS = {
    # The slip is a TABLE; each row prints the grade TWICE (a letter + a Malay band).
    # Ask for both, ALIGNED to the same row — the academic engine cross-checks them to
    # catch a row-transposition misread. (The deterministic `_split_band` still strips
    # any band words that leak into the subject name.)
    'results_slip': (' This is an SPM results slip — a TABLE with one row per subject '
                     '(code · subject name · LETTER grade · Malay BAND phrase). For EACH '
                     'subject row return {subject, grade, band}: "subject" = the subject '
                     'NAME only (drop the leading code); "band" = the Malay band phrase on '
                     'THAT SAME row; "grade" = the grade the BAND means, using this EXACT '
                     'mapping (the band is the source of truth — the printed +/- letter is '
                     'small and easy to misread): Cemerlang Tertinggi=A+, Cemerlang '
                     'Tinggi=A, Cemerlang=A-, Kepujian Tertinggi=B+, Kepujian Tinggi=B, '
                     'Kepujian Atas=C+, Kepujian=C, Lulus Atas=D, Lulus=E, Gagal=G, Tidak '
                     'Hadir=TH. The printed letter MUST agree with the band — if they '
                     'differ, trust the BAND. Read strictly row by row: the grade and band '
                     'belong to the subject printed on the SAME line; NEVER carry a grade or '
                     'band up or down to a different subject, even if the slip is faint or '
                     'watermarked. Ignore the "Ujian Lisan" line and any watermark text.'),
    'offer_letter': (' This is a Malaysian post-SPM offer letter — a Form Six ("Tingkatan Enam"), '
                     'matriculation ("Program Matrikulasi"), polytechnic ("Politeknik"), PISMP '
                     '(teacher-training, "Ijazah Sarjana Muda Perguruan"), or a university '
                     'degree/diploma/foundation offer. The fields are arranged as a two-column '
                     'label/value list (e.g. "2.1 Bidang … 2.2 Pusat Tingkatan Enam …") — read it '
                     'VISUALLY and pair each value with its own label. '
                     '"candidate_name" = the offered student\'s full name; "candidate_nric" = their IC, '
                     'printed as "No. Kad Pengenalan" / "No. Pengenalan Diri" / "K/P" (keep the 12 '
                     'digits). "offer_date" = the date the letter was ISSUED ("Tarikh" in the reference '
                     'block) — NOT "Tarikh Cetakan" (the print date); used to judge currency. '
                     '"institution" = the college/campus/school the student reports to (Pusat Tingkatan '
                     'Enam, Kolej Matrikulasi, the Politeknik, or the IPG campus); "issuer" = the body '
                     'that issued the letter (Sektor Operasi Sekolah / Bahagian Matrikulasi / Jabatan '
                     'Pendidikan Politeknik dan Kolej Komuniti / Institut Pendidikan Guru / a university). '
                     'Per-pathway academic field: "programme" = the diploma/degree name (polytechnic or '
                     'university); "stream" = the Form-Six "Bidang" (Sains / Sains Sosial) OR the '
                     'matriculation "Jurusan"; "bidang_pengkhususan" = the PISMP specialisation (e.g. '
                     '"Bahasa Tamil Pendidikan Rendah"); "elektif" = the PISMP elective subject; "aliran" '
                     '= the PISMP school stream ("SK" / "SJKC" / "SJKT"). "reporting_date" = the report/'
                     'registration date — labelled "Tarikh Lapor Diri" (STPM, UKM), "Tarikh Kemasukan ke '
                     'Kolej" (matriculation), "Tarikh dan Masa Daftar" (polytechnic), "Tarikh Pendaftaran" '
                     '(PISMP, UPNM, UMP, UTeM), "Tarikh Mendaftar" (UPSI), or — UTHM style — a bare '
                     '"Tarikh" line INSIDE the "diminta untuk mendaftar pada tarikh, tempat dan masa" '
                     'clause (never the letter-issue "Tarikh" in the reference block). '
                     '"reporting_date_label" = the VERBATIM label heading the reporting date sits under, '
                     'exactly as printed on the letter (e.g. "Tarikh Mendaftar", "TARIKH LAPOR DIRI", '
                     '"Tarikh dan Masa Daftar", or just "Tarikh" for the UTHM clause style); empty when '
                     'no reporting date is shown. '
                     '"intake" = the session (e.g. "Sesi 2026/2027"); '
                     '"candidate_address" = the student\'s mailing address if shown. Leave any field empty '
                     'if absent — only fill the academic fields that this pathway\'s letter actually has.'),
    'str': (' This is meant to be a Malaysian STR (Sumbangan Tunai Rahmah) proof. It should be ONE '
            'of three recognised kinds — set "source_type" to: "letter" (an official Kementerian '
            'Kewangan STR APPROVAL letter — KEMENTERIAN KEWANGAN letterhead, a "No. Rujukan" + '
            'date, stating the STR application was approved/"diluluskan"); "semakan_status" (the '
            'MySTR "Semakan Status" check page — its distinctive markers are "Maklumat Pemohon" + '
            '"Status Permohonan Semasa" + a "Fasa Bayaran" phase table; desktop OR mobile); '
            '"dashboard" (the MySTR mobile-app HOME — its distinctive markers are the side/nav menu '
            '(Dashboard / Jadual Perkhidmatan / Kaunter / Soalan Lazim (FAQ) / Panduan Pengguna / '
            'Borang), a profile card with the name + IC in brackets, a "Status Permohonan STR" card, '
            'and a "Status Kelayakan SARA" card — and it does NOT have a "Fasa Bayaran" table); '
            'else "unknown". CRITICAL: SARA (Sumbangan Asas Rahmah) is a DIFFERENT programme from '
            'STR. A document that only concerns SARA and does NOT show STR approval — e.g. a '
            'Perdana Menteri greeting/congratulation letter saying the person is "terpilih untuk '
            '(terus) menerima bantuan SARA" — is NOT valid STR proof: set "source_type"="unknown" '
            'and leave "status" EMPTY (do NOT infer "approved"/"Lulus" from SARA-recipient '
            'wording). (The "Semakan Status" page\'s own "Sumbangan Asas Rahmah" section is fine — '
            'that whole page IS an STR artifact.) "recipient_name" = the recipient\'s full name '
            '("Nama Penerima" on the letter, "Nama" on the portal, or the dashboard profile-card '
            'name); "recipient_nric" = their IC / MyKad ("No Pengenalan" / "No. MyKad" / the '
            'number in brackets — keep ALL 12 digits even without dashes); "status" = the STR '
            'approval status: the VALUE shown beneath or beside the label "Status Permohonan STR" / '
            '"Status Permohonan Semasa" — i.e. "Lulus" / "diluluskan" (approved), "Ditolak" / '
            '"Tidak Layak" (rejected), "Dalam proses" (pending). CRITICAL: the status is that VALUE, '
            'NEVER the label — do NOT return the programme word "STR" itself as the status (on the '
            'dashboard the card reads "Status Permohonan STR" then "Lulus" on the next line → status '
            'is "Lulus"). "year" = the STR cycle year, taken ONLY from the letter date or a '
            '"Maklumat Pembayaran" / "Tarikh Kredit" payment date (e.g. "20/01/2026" → "2026"); '
            'NEVER read a year from page chrome such as the nav/menu (e.g. a "Soalan Lazim (FAQ) '
            '2026" menu item is NOT the STR year); if no such date is shown, leave it EMPTY. '
            '"amount" = the total STR in RM ("jumlah … STR … RM1,200" / "Jumlah Bayaran Keseluruhan '
            'STR"). Leave a field empty if it is not present.'),
    'salary_slip': (' This is a Malaysian salary slip / payslip — OR a government benefit / pension '
                    'payment statement (e.g. a PERKESO/SOCSO "Penyata Bayaran Faedah" survivor\'s '
                    'pension "Pencen Penakat"), which counts as household income too. "name" = the '
                    'EMPLOYEE\'s / recipient\'s full name; "nric" = their Malaysian IC number — look '
                    'for a label ("No. K/P" / "No. KP" / "K/P" / "IC No" / "No. Kad Pengenalan" / '
                    '"MyKad"), OR any 12-digit number shaped like a MyKad (YYMMDD-PB-#### — six '
                    'digits, then two, then four) sitting in the employee-details block even if it '
                    'is UNLABELLED; keep the 12 digits. Do NOT use the employee / staff / payroll '
                    'number (usually shorter and often prefixed with a letter, e.g. "F01677") as the '
                    'IC. "employer" = the company (leave empty for a benefit/pension statement); '
                    '"currency" = the pay currency. Set "SGD" if this is a SINGAPORE payslip — '
                    'tell-tale signs: an "S$" sign on the amounts, CPF (Central Provident Fund) or '
                    'SDL (Skills Development Levy) lines, an employer ending "Pte Ltd" / "Private '
                    'Limited", a Singapore address, or a Singapore work-pass / FIN number. Otherwise '
                    '"MYR" (a Malaysian slip shows RM, with EPF/KWSP and SOCSO/PERKESO); '
                    '"gross_income" = the GROSS monthly pay = the TOTAL earnings for the month = '
                    'basic salary PLUS all allowances and overtime (the "Total Payment" / "Jumlah '
                    'Pendapatan" / gross-earnings total). Do NOT use the "Basic Salary" line alone '
                    'when a higher total-earnings figure is shown — a job with overtime/allowances '
                    'earns more than its basic. For a benefit/pension statement, '
                    'the regular MONTHLY benefit amount (e.g. "Amaun Bayaran" RM687.50); "net_income" '
                    '= the net/take-home pay; "gross_income_ytd" = the YEAR-TO-DATE / cumulative '
                    'gross total — labelled "Year To Date" / "YTD" / "Jumlah Terkumpul" / '
                    '"Pendapatan Terkumpul" / "Terkumpul" / "Sehingga Kini" / "Cumulative"; OR, when '
                    'the earnings are laid out in TWO number columns (the current month vs a '
                    'cumulative / "Terkumpul" column), it is the CUMULATIVE column total — read BOTH '
                    'columns, do not stop at the first. It captures variable overtime a single month '
                    'misses; leave empty only if the slip truly shows one month with no cumulative '
                    'figure. "period" = the pay month/year (e.g. "March 2026"). '
                    'IMPORTANT for money fields: on a HAND-WRITTEN voucher the amount is often '
                    'ruled into TWO columns — ringgit (RM) and sen (cents) — separated by a '
                    'vertical line. Read that line as a DECIMAL POINT: "326 | 00" is RM326.00, '
                    '"4856 | 75" is RM4856.75. NEVER concatenate the two columns into one whole '
                    'number (RM326.00 must not become 32600). Also: the take-home pay (net) can '
                    'never exceed the gross — if your reading makes net > gross, you have likely '
                    'mis-read a column; re-read. '
                    'Leave a field empty if it is not present.'),
    'epf': (' This is a Malaysian EPF/KWSP statement ("PENYATA AHLI"). "name" = the member\'s '
            'full name; "nric" = "No. Kad Pengenalan" (keep the 12 digits). "employer_number" = '
            '"No. Majikan" EXACTLY as printed, INCLUDING when it is all zeros ("000000000" — that '
            'means no active employer / unemployed, so KEEP it, do NOT blank it); "employer" = the '
            'employer NAME if one is shown (often absent). "latest_balance" = the TOTAL savings '
            '"JUMLAH SIMPANAN" (RM); "year" = the statement year; "statement_date" = "Tarikh '
            'Penyata". The contribution table ("Caruman") shows, per month, an EMPLOYER share '
            '("Caruman Majikan") and a MEMBER share ("Caruman Ahli" / "Caruman Pekerja"). SUM each '
            'column over the months shown: "employer_contribution_total" = Σ Caruman Majikan (RM), '
            '"employee_contribution_total" = Σ Caruman Ahli (RM), and "months_counted" = how many '
            'months you summed. "monthly_contribution" = the most recent single month\'s total '
            'contribution from "CARUMAN SEMASA" (NOT the balance) — leave EMPTY if "Tiada Transaksi". '
            '"contribution_status" = "has" if there is at least one real monthly contribution; '
            '"zero" ONLY if it clearly shows NONE ("Tiada Transaksi" / all zero) — a real signal of '
            'no formal salary; "unknown" if the contributions section is unreadable/absent (do NOT '
            'guess "zero" when you simply cannot read it). "address" = the member\'s correspondence '
            'address if printed. Leave any field empty if it is not present.'),
    'water_bill': (' This is a Malaysian water utility bill (e.g. PAIP, SAJ, Air Selangor, '
                   'PBAPP, SADA). "name" = the account holder\'s name ("Nama"); "address" = '
                   'the supply/billing address; "amount" = ONLY the CURRENT month\'s charge '
                   '("Caj Air Semasa" / "Jumlah Caj Air Semasa" / "Jumlah Bil Semasa") — do '
                   'NOT use "Jumlah Bil Perlu Dibayar", which is the TOTAL including arrears; '
                   '"unpaid_balance" = the arrears carried forward ("Tunggakan" / "Baki '
                   'Tertunggak", RM) — empty if none; "billing_period" = the bill month. '
                   'Leave empty if absent.'),
    'electricity_bill': (' This is a Malaysian electricity bill (TNB / SESB / SESCO). "name" = '
                         'the account holder\'s name; "address" = the supply/billing address; '
                         '"amount" = ONLY the CURRENT month\'s charge ("Caj Semasa" / "Caj '
                         'Penggunaan Bulan Semasa") — do NOT use "Jumlah Perlu Dibayar", which '
                         'is the TOTAL including arrears; "unpaid_balance" = the arrears '
                         '("Tunggakan" / "Baki Tertunggak", RM) — empty if none; '
                         '"billing_period" = the bill month. Leave empty if absent.'),
    'birth_certificate': (' This is a Malaysian birth certificate (Sijil Kelahiran, JPN). It has '
                          'three labelled sections IN ORDER: "KANAK-KANAK / CHILD", then "BAPA / '
                          'FATHER", then "IBU / MOTHER". Read each name from WITHIN its section, '
                          'anchored on the SECTION HEADER — NOT on the field label: the name field '
                          'is labelled "Nama" on some certificates and "Nama Penuh" on others, so '
                          'accept EITHER. Return: "bc_child_name" = the name in the KANAK-KANAK / '
                          'CHILD block (the lines between the "KANAK-KANAK" header and the "BAPA" '
                          'header); "bc_child_nric" = the child IC if shown; "bc_father_name" + '
                          '"bc_father_nric" = the "Nama"/"Nama Penuh" and "No. Kad Pengenalan" in the '
                          'BAPA / FATHER block; "bc_mother_name" + "bc_mother_nric" = the "Nama"/'
                          '"Nama Penuh" and "No. Kad Pengenalan" in the IBU / MOTHER block (keep all '
                          '12 NRIC digits). IGNORE the "PEMBERITAHU / INFORMANT" block at the bottom '
                          'entirely — its "Nama" is the informant (often a grandparent), NOT the '
                          'child or a parent. Use names EXACTLY as printed (keep bin/binti/a/l/a/p). '
                          'Leave a field empty if absent. NOTE: a birth certificate normally shows NO '
                          'IC number for the child (only the parents have "No. Kad Pengenalan") — '
                          'leave "bc_child_nric" empty and do NOT add any warning about a missing/'
                          'unlabelled child IC.'),
    'guardianship_letter': (' This is EITHER a Malaysian court-issued guardianship order OR a '
                            'written authorisation letter from a parent placing the applicant '
                            '(the "ward") under someone\'s care. Return: "guardian_name" = the '
                            'guardian\'s full name; "guardian_nric" = the guardian\'s IC number '
                            'if shown (12 digits); "ward_name" = the child/ward the letter is '
                            'about (the applicant); "doc_kind" = "court_order" if it is a court '
                            'guardianship order, else "authorisation_letter". Leave a field '
                            'empty if it is not present or not legible.'),
    'income_support_doc': (' This is a SUPPORTING document for a household member\'s informal '
                           'or self-declared income — an employer/wage letter, a bank statement '
                           'showing income, or a community/village-head (penghulu/JKKK) letter. '
                           'Return: "name" = the person the document is about (a working household '
                           'member, NOT necessarily the applicant); "nric" = their IC number if '
                           'shown; "amount" = any monthly income / salary / payment figure stated '
                           '(as printed, e.g. "RM1,200"); "period" = the month/period it covers if '
                           'shown; "issuer" = who issued it (employer / bank / penghulu / JKKK); '
                           '"kind" = one of "employer_letter", "bank_statement", "community_letter", '
                           'else "other". Leave a field empty if it is not present or not legible.'),
    'semester_result': (' This is a post-SPM SEMESTER result — an STPM MPM slip ("Keputusan '
                        'Peperiksaan Semester"), a Matriculation/Politeknik/university semester '
                        'result slip, or a student-portal results screenshot. Return: "name" = the '
                        'STUDENT\'s full name ("Nama") as printed; "nric" = the student\'s IC number '
                        '("No. Kad Pengenalan", keep all 12 digits); "institution" = the '
                        'college/university/board; "programme" = the course/programme; "semester" = '
                        'the semester shown; "cgpa" = the CUMULATIVE grade point ONLY — labelled '
                        '"PNGK" / "HPNM" / "CGPA" / "Himpunan PNGK" / "Kumulatif" (the running '
                        'average across semesters). If the slip shows ONLY a single semester\'s '
                        'grades with NO cumulative figure (e.g. an STPM Semester 1 slip), LEAVE '
                        '"cgpa" EMPTY and add NO warning about it — a semester-only slip has no CGPA. '
                        'Do NOT use a single-semester GPA ("PNM" / "GPA Semester") as the cgpa.'),
}


def _call_gemini_json(prompt: str, schema: dict, *, image: Optional[bytes] = None,
                      mime_type: str = 'image/jpeg') -> dict:
    """Structured-output Gemini call → parsed JSON dict, or {'_error': msg}. This is
    the single seam tests @patch. Reuses profile_engine's model cascade + key guard.
    Pass ``image`` (raw bytes) for a multimodal read — Gemini sees the picture, not
    just OCR text (used by the IC second-opinion to recover blurry digits)."""
    api_key = getattr(settings, 'GEMINI_API_KEY', '') or ''
    if not api_key:
        return {'_error': 'AI service not configured (missing API key)'}
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return {'_error': 'AI module not installed'}
    from .profile_engine import MODEL_CASCADE
    client = genai.Client(api_key=api_key)
    contents = (prompt if image is None
                else [types.Part.from_bytes(data=image, mime_type=mime_type), prompt])
    last_error = None
    for model_name in MODEL_CASCADE:
        try:
            resp = client.models.generate_content(
                model=model_name, contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json', response_schema=schema, temperature=0.1),
            )
            return json.loads(resp.text)
        except Exception as e:  # noqa: BLE001 — graceful: never propagate to a 500
            last_error = str(e)
            logger.warning('Gemini JSON call failed with %s: %s', model_name, e)
            continue
    return {'_error': f'All AI models failed: {last_error}'}


def extract_document_fields(ocr_text: str, doc_type: str, *, image: Optional[bytes] = None,
                            content_type: str = '') -> dict:
    """Gemini extracts the per-doc-type fields. Pass ``image`` to read the document
    VISUALLY (the model sees the real 2-D layout — used for the results slip, whose
    table can't survive being flattened to OCR text); otherwise it reads ``ocr_text``.
    Returns {fields, warnings, error}. Never raises."""
    schema = _FIELD_SCHEMAS.get(doc_type)
    if schema is None:
        return {'fields': {}, 'warnings': [], 'error': f'no extractor for {doc_type}'}
    hint = _DOC_HINTS.get(doc_type, '')
    doc_label = doc_type.replace('_', ' ')
    if image is not None:
        img, mime = _as_image_for_gemini(image, content_type)
        if img is None:
            return {'fields': {}, 'warnings': [], 'error': 'no image for extraction'}
        prompt = (
            f'This is an image of a Malaysian {doc_label}. Read it carefully and extract '
            'the listed fields exactly as printed. If a field is missing or unclear, leave '
            f'it empty and add a short note to "warnings". Do NOT invent values.{hint}'
        )
        data = _call_gemini_json(prompt, schema, image=img, mime_type=mime)
    else:
        if not (ocr_text or '').strip():
            return {'fields': {}, 'warnings': [], 'error': 'no text'}
        prompt = (
            f'Here is the OCR text from a Malaysian {doc_label}. Extract the listed fields '
            'exactly as printed. If a field is missing or unclear, leave it empty and add a '
            f'short note to "warnings". Do NOT invent values.{hint}\n\nOCR TEXT:\n{(ocr_text or "")[:6000]}'
        )
        data = _call_gemini_json(prompt, schema)
    if '_error' in data:
        return {'fields': {}, 'warnings': [], 'error': data['_error']}
    warnings = _drop_expected_warnings(doc_type, data.pop('warnings', []) or [])
    data = _sanitize_extracted_fields(doc_type, data)
    return {'fields': data, 'warnings': warnings, 'error': ''}


# Headings / labels that are never a person's name. If the AI sweeps one into a NAME field
# (a cropped/skewed photo, a section mis-read), we must not let it masquerade as a real name
# and trigger a wrong-person mismatch downstream.
_NON_NAME_MARKERS = ('KERAJAAN MALAYSIA', 'SIJIL KELAHIRAN', 'KANAK-KANAK', 'KANAK KANAK',
                     'PEMBERITAHU', 'PENDAFTAR', 'MAKLUMAT')
# NB: leading field-label stripping ('NAMA :' …) is handled by the existing `_strip_name_label`
# (defined below, used by doc_student_verdict) — reused here, not re-implemented.


def _looks_like_non_name(value: str) -> bool:
    s = (value or '').strip().upper()
    return bool(s) and any(s == m or s.startswith(m + ' ') or s == m.replace('-', ' ')
                           for m in _NON_NAME_MARKERS)


# ── Reporting-date normalisation (offer letter) ───────────────────────────────
# Offers print the report/registration date a dozen ways — "22/06/2026", "20 JUN 2026 (SABTU)",
# "20 Julai 2026 Isnin", "8 HINGGA 9 JUN 2026", "22 JUN 2026 (9.00 PAGI - 2.00 PETANG)". Normalise
# to one clean "D Mon YYYY" (e.g. "22 Jun 2026"): strip the weekday + time/parenthetical, take a
# range's START date, accept DD/MM/YYYY or "D Month YYYY" (Malay or English month).
_RD_MONTHS = {
    'JANUARI': 'Jan', 'JANUARY': 'Jan', 'JAN': 'Jan', 'FEBRUARI': 'Feb', 'FEBRUARY': 'Feb', 'FEB': 'Feb',
    'MAC': 'Mar', 'MARCH': 'Mar', 'MAR': 'Mar', 'APRIL': 'Apr', 'APR': 'Apr', 'MEI': 'May', 'MAY': 'May',
    'JUN': 'Jun', 'JUNE': 'Jun', 'JULAI': 'Jul', 'JULY': 'Jul', 'JUL': 'Jul',
    'OGOS': 'Aug', 'OGO': 'Aug', 'AUGUST': 'Aug', 'AUG': 'Aug', 'SEPTEMBER': 'Sep', 'SEPT': 'Sep', 'SEP': 'Sep',
    'OKTOBER': 'Oct', 'OCTOBER': 'Oct', 'OKT': 'Oct', 'OCT': 'Oct', 'NOVEMBER': 'Nov', 'NOV': 'Nov',
    'DISEMBER': 'Dec', 'DECEMBER': 'Dec', 'DIS': 'Dec', 'DEC': 'Dec',
}
_RD_MONTH_NUM = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                 7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
_RD_WEEKDAY = re.compile(r'\b(ISNIN|SELASA|RABU|KHAMIS|JUMAAT|SABTU|AHAD|'
                         r'MON(?:DAY)?|TUE(?:SDAY)?|WED(?:NESDAY)?|THU(?:RSDAY)?|FRI(?:DAY)?|SAT(?:URDAY)?|SUN(?:DAY)?)\b')
_RD_TIME = re.compile(r'\d{1,2}[.:]\d{2}\s*(?:PAGI|PETANG|TENGAH HARI|MALAM|AM|PM)?')


def _normalise_reporting_date(raw: str) -> str:
    """An offer reporting date → 'D Mon YYYY' (e.g. '22 Jun 2026'). Returns the ORIGINAL string
    if it can't confidently parse a day + month + year (never destroys an unparseable value)."""
    s = (raw or '').strip()
    if not s:
        return s
    up = s.upper()
    m = re.search(r'\b(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(20\d{2})\b', up)   # DD/MM/YYYY
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f'{d} {_RD_MONTH_NUM[mo]} {m.group(3)}'
    cleaned = re.sub(r'\([^)]*\)', ' ', up)        # drop (SABTU) / (9.00 PAGI - ...)
    cleaned = _RD_TIME.sub(' ', cleaned)           # drop bare times (2:30 PETANG)
    cleaned = _RD_WEEKDAY.sub(' ', cleaned)        # drop weekday words
    mon = None                                     # first month token, by position
    for name, eng in _RD_MONTHS.items():
        hit = re.search(r'\b' + name + r'\b', cleaned)
        if hit and (mon is None or hit.start() < mon[0]):
            mon = (hit.start(), eng)
    ym = re.search(r'\b(20\d{2})\b', cleaned)
    if not mon or not ym:
        return s
    day = next((int(g.group(1)) for g in re.finditer(r'\b(\d{1,2})\b', cleaned)
                if 1 <= int(g.group(1)) <= 31), None)
    return f'{day} {mon[1]} {ym.group(1)}' if day else s


def _sanitize_extracted_fields(doc_type: str, data: dict) -> dict:
    """Deterministic post-extraction guards (item B): stop a header/label or a wrong-section
    name passing through as a person's name. Blanking a bad value yields 'unread' (SOFT)
    downstream — never a confident wrong-person mismatch. Pure; never raises."""
    if not isinstance(data, dict):
        return data
    if doc_type == 'results_slip' and data.get('candidate_name'):
        data['candidate_name'] = _strip_name_label(data['candidate_name'])
    elif doc_type == 'offer_letter' and data.get('reporting_date'):
        data['reporting_date'] = _normalise_reporting_date(data['reporting_date'])
    elif doc_type == 'birth_certificate':
        child = _strip_name_label(data.get('bc_child_name') or '')
        # The child name must come from the KANAK-KANAK block: never a heading, and never
        # identical to a parent's name (the classic section mis-read — BAPA's 'Nama' pulled
        # into the child slot, e.g. #10). Either case → blank ('couldn't read the child'),
        # which is soft, not a wrong-person red.
        if child and (_looks_like_non_name(child)
                      or name_match(child, data.get('bc_father_name') or '') == 'match'
                      or name_match(child, data.get('bc_mother_name') or '') == 'match'):
            child = ''
        data['bc_child_name'] = child
    return data


def _drop_expected_warnings(doc_type: str, warnings: list) -> list:
    """Strip warnings a document is EXPECTED to trip — noise that misleads the officer. Belt-and-
    braces with the prompt hint, since Gemini's free-text warnings aren't fully steerable.
      * birth_certificate — the child carries NO IC (issued one later), so a 'child NRIC missing'
        note is normal.
      * salary_slip — the NRIC and the year-to-date GROSS are OPTIONAL: many Malaysian SME payslips
        identify the employee by an employee number + name (no IC printed) and show only the current
        month's earnings (no YTD column). Flagging them 'missing' makes a perfectly valid slip look
        deficient (the earner is still cross-checked by NAME, and one month's gross still counts)."""
    if doc_type == 'birth_certificate':
        def _is_child_nric_noise(w) -> bool:
            s = (w or '').lower()
            return 'child' in s and any(k in s for k in
                                        ('nric', 'kad pengenalan', 'ic number', 'identity card', 'no. kad'))
        return [w for w in warnings if not _is_child_nric_noise(w)]
    if doc_type == 'salary_slip':
        def _is_optional_salary_noise(w) -> bool:
            s = (w or '').lower()
            if not any(k in s for k in ('missing', 'not found', 'not present', 'not printed',
                                        'not shown', 'absent', 'unavailable', 'no ')):
                return False
            nric = any(k in s for k in ('nric', 'ic number', 'ic no', 'kad pengenalan', 'k/p', 'mykad'))
            # Explicit year-to-date phrasing ONLY — a bare 'year' + 'date' anywhere over-matches a
            # legit "pay period (month/year)… pay date" warning (which must be kept).
            ytd = any(k in s for k in ('ytd', 'gross_income_ytd', 'terkumpul',
                                       'year to date', 'year-to-date', 'year to-date'))
            return nric or ytd
        return [w for w in warnings if not _is_optional_salary_noise(w)]
    if doc_type == 'offer_letter':
        # Supplementary DATA-POINT fields are OPTIONAL on an offer letter — not every issuer prints
        # an offer/reporting date, intake, candidate address, or stream/specialisation. Their absence
        # is not a problem (the chip just omits the data point); a "missing" note is noise. The CORE
        # facts — candidate name / NRIC (Name·IC), programme/institution (Pathway), issuer +
        # genuineness (Official) — are handled by the chip, NOT these warnings, so a warning about
        # THEM is never suppressed here.
        def _is_optional_offer_noise(w) -> bool:
            s = (w or '').lower()
            if not any(k in s for k in ('missing', 'not found', 'not present', 'not printed',
                                        'not shown', 'not specified', 'not stated', 'not explicitly',
                                        'not clearly', 'absent', 'unavailable', 'no ')):
                return False
            return any(k in s for k in ('offer_date', 'offer date', 'reporting_date', 'reporting date',
                                        'intake', 'address', 'stream', 'bidang', 'elektif', 'aliran',
                                        'specialis', 'specializ'))
        return [w for w in warnings if not _is_optional_offer_noise(w)]
    if doc_type == 'semester_result':
        # Only Name / NRIC / CGPA matter on a semester slip (owner): Name·IC drive the red/green
        # chip, CGPA is optional (a single-semester slip like STPM Sem 1 has no cumulative figure).
        # So a "missing FIELD" note — CGPA, institution, programme, semester, and even name/NRIC
        # (whose absence already reds the chip) — is noise. Keep only SUBSTANTIVE warnings (a wrong
        # document / an unreadable slip), which carry no field-name keyword.
        def _is_semester_field_noise(w) -> bool:
            s = (w or '').lower()
            if not any(k in s for k in ('missing', 'not found', 'not present', 'not printed',
                                        'not shown', 'not specified', 'not stated', 'not explicitly',
                                        'not clearly', 'not available', 'unclear', 'absent',
                                        'unavailable', 'semester-only', 'semester only', 'no ')):
                return False
            return any(k in s for k in ('name', 'nric', 'kad pengenalan', 'ic ', 'cgpa', 'pngk',
                                        'hpnm', 'gpa', 'kumulatif', 'cumulative', 'semester',
                                        'institution', 'college', 'university', 'programme',
                                        'program', 'course'))
        return [w for w in warnings if not _is_semester_field_noise(w)]
    return warnings


def _any_field_filled(fields: dict) -> bool:
    for v in fields.values():
        if isinstance(v, str):
            if v.strip():
                return True
        elif v:
            return True
    return False


_DOC_NAME_LABEL_RE = re.compile(r'^\s*(?:NAMA(?:\s+CALON)?|NAME|CALON)\s*[:.\-]?\s+', re.IGNORECASE)


def _strip_name_label(s: str) -> str:
    """Drop a leaked field label ('NAMA :', 'NAME -', 'CALON ') that Gemini sometimes prepends
    to an extracted candidate name, so it doesn't pollute the token-set name match (it turned a
    genuine slip — 'NAMA : SANJANA A/P KALIANA KUMAR' vs the typed 'SANJANA A/P KALIANAKUMAR' —
    into a false name_mismatch). Requires a trailing separator+space, so a real name is untouched."""
    return _DOC_NAME_LABEL_RE.sub('', s or '').strip()


def _bank_verdict(fields, student_name) -> str:
    """Deterministic verdict for a bank statement (never hallucinated):
    'ok' | 'name_mismatch' (holder isn't the student) | 'incomplete' (a required field
    couldn't be read) | 'wrong_doc' (nothing bank-shaped). The holder MUST be the STUDENT
    — a hard rule — so the name is matched ONLY against the student, never a guardian."""
    bank = _strip_name_label(fields.get('bank_name') or '').strip()
    acct = (fields.get('account_number') or '').strip()
    holder = _strip_name_label(fields.get('account_holder') or '').strip()
    if not (bank or acct or holder):
        return 'wrong_doc'
    if not (bank and acct and holder):
        return 'incomplete'   # a bank statement, but a required field couldn't be read
    if name_match(holder, student_name or '') == 'mismatch':
        return 'name_mismatch'   # the account is in someone else's name
    return 'ok'


def doc_student_verdict(doc_type, fields, *, names, postcode='', city='', street='', check_address=False) -> str:
    """Deterministic verdict from the Gemini-extracted fields (never hallucinated):
    'ok' | 'name_mismatch' | 'address_mismatch' | 'incomplete' | 'wrong_doc'."""
    if doc_type == 'bank_statement':
        # The holder must be the STUDENT only — names[0] is the applicant (guardians follow).
        return _bank_verdict(fields, names[0] if names else '')
    if doc_type == 'income_support_doc':
        # V1: a supporting income doc NAMES THE EARNER (a working household member), not the
        # student — so we do NOT name-match it against the applicant (that would false-red a
        # genuine employer letter for the father). It must simply READ as a real support
        # document: some field (name / amount / issuer / kind) present. A blank/wrong image
        # reads nothing → 'wrong_doc', which does NOT clear the declared-income gap. Whether
        # the named person is the right earner is an officer/interview judgement, not a red.
        return 'ok' if _any_field_filled(fields) else 'wrong_doc'
    if not _any_field_filled(fields):
        return 'wrong_doc'   # nothing of the expected shape was found
    # A UTILITY BILL is an ADDRESS anchor, held in a PARENT's name — never name-check it against the
    # student (owner 2026-07-09, #130: a father's-name water/electricity bill looped forever as
    # 'name_mismatch', with no coaching, because the reference names were student+guardians only).
    # This matches help_engine (bills deliberately un-name-checked) and doc_match_verdict (bills
    # accept); a genuine STRANGER's bill is still caught softly by the utility_holder_unknown
    # question, which knows the declared parents.
    if doc_type not in ('water_bill', 'electricity_bill'):
        extracted_name = _strip_name_label(fields.get(_NAME_FIELD.get(doc_type, 'name')) or '')
        if extracted_name:
            matched = any(name_match(extracted_name, n) in ('match', 'partial') for n in names if n)
            if not matched:
                return 'name_mismatch'
    if check_address:
        addr = (fields.get('address') or '').strip()
        # Only a genuinely DIFFERENT home is flagged to the student; a soft 'unconfirmed'
        # (abbreviation / bilingual town / partial OCR) stays quiet — the officer sees amber.
        if addr and address_match(addr, postcode=postcode, city=city, street=street) == 'mismatch':
            return 'address_mismatch'
    return 'ok'


def _extract_slip_deterministic(doc, image, words=None):
    """``(result|None, diag)``. Positional OCR parse of an SPM results slip →
    ``{fields, warnings, error}``, or None to fall back to Gemini (no image, an STPM
    slip, or the table didn't parse). SPM only for now. ``diag`` records WHY a parse was
    skipped/failed (incl. a sample of what Vision read) so a Gemini-fallback slip can be
    diagnosed from the stored record. Reading the table by Y/X geometry pairs each
    subject with the grade on its own row, which Gemini mis-transposes on a watermark.
    Pass ``words`` (from a prior ``_vision_words``/``ocr_document_full`` read of the SAME
    blob) to skip the second billable Vision call; None = compute here."""
    if image is None:
        return None, {'reason': 'no_image'}
    exam_type = (getattr(getattr(doc.application, 'profile', None), 'exam_type', '') or '').lower()
    if exam_type and exam_type != 'spm':
        return None, {'reason': 'not_spm_exam', 'exam_type': exam_type}
    wd = {'words': words, 'error': None} if words is not None else _vision_words(image, doc.content_type)
    if wd.get('error'):
        return None, {'reason': 'vision_error', 'error': wd['error']}
    if not wd.get('words'):
        return None, {'reason': 'no_words'}
    from .academic_engine import parse_spm_slip
    parsed = parse_spm_slip(wd['words'])
    if not parsed:
        # The deterministic parse couldn't lock onto the table (a format/orientation the
        # parser doesn't yet handle, or an unreadable photo) → Gemini reads it instead.
        # Keep the FULL word geometry (text + box + angle) on the fallback diag so this
        # slip can be frozen as a regression fixture and the parser extended — exactly how
        # the rotated-slip support was built. Only stored on failure, so no success bloat.
        capture = [{'text': w['text'], 'cx': round(w['cx'], 1), 'cy': round(w['cy'], 1),
                    'h': w['h'],
                    'angle': (round(w['angle'], 1) if w.get('angle') is not None else None)}
                   for w in wd['words']]
        return None, {'reason': 'parse_none', 'word_count': len(wd['words']), 'capture': capture}
    return {'fields': parsed, 'warnings': [], 'error': ''}, {'reason': 'ok'}


def run_field_extraction_for_document(doc, *, names, postcode='', city='', street='', check_address=False, ocr=None) -> dict:
    """Extract fields + a deterministic student-facing verdict, store on the doc.
    Never blocks, never raises. Pass ``ocr`` to reuse a prior OCR pass.

    The **results slip** is read DETERMINISTICALLY by positional OCR first (the
    standardised SPM table parses by geometry, immune to row-transposition); only if
    that can't lock onto the table does it fall back to reading the IMAGE with Gemini.
    Every other supporting doc reads the OCR text."""
    from .doc_parse import parse_by_labels      # deterministic-first for standardised docs
    # A full-pipeline ocr dict (ocr_document_full) may carry the fetched bytes + the word
    # boxes from its single Vision call — reuse them instead of re-downloading / re-billing.
    _o = ocr if isinstance(ocr, dict) else {}

    def _image():
        return _o['image'] if _o.get('image') is not None else _fetch_image_bytes(doc.storage_path)

    pre_words = _o.get('words')                 # None = not computed (compute if needed)
    if doc.doc_type == 'results_slip':
        image = _image()
        ex, diag = _extract_slip_deterministic(doc, image, words=pre_words)   # OCR-first (SPM); None → Gemini
        if ex is None:
            if image is not None:
                ex = extract_document_fields('', doc.doc_type, image=image, content_type=doc.content_type)
            else:
                r = ocr if ocr is not None else ocr_document(doc)
                ex = extract_document_fields(r.get('text', ''), doc.doc_type)
            ex['capture'] = 'ai'
            # Record WHY we fell back (+ what Vision read) so the slip can be diagnosed.
            if isinstance(ex.get('fields'), dict):
                ex['fields']['_slip_ocr_diag'] = diag
        else:
            ex['capture'] = 'deterministic'
    elif doc.doc_type == 'offer_letter':
        # The offer's 2-D label/value layout doesn't survive flattened OCR (labels and values
        # land in separate blocks), so read the IMAGE with Gemini for the per-pathway fields;
        # fall back to OCR text only if the image can't be fetched.
        image = _image()
        if image is not None:
            ex = extract_document_fields('', doc.doc_type, image=image, content_type=doc.content_type)
        else:
            r = ocr if ocr is not None else ocr_document(doc)
            ex = extract_document_fields(r.get('text', ''), doc.doc_type)
        ex['capture'] = 'ai'
    elif doc.doc_type == 'birth_certificate':
        # Geometry-first, like the results slip. The BC's KANAK-KANAK / BAPA / IBU blocks place the
        # child's "Nama" far from the parents'; flattened OCR cross-wires them (#10 read the father's
        # name as the child). `parse_bc` re-linearises the Vision WORD BOXES by position, classifies
        # the version (bilingual / mono), and reads each field from its label brackets — and returns
        # None for a cropped/odd doc (so it can't invent a missing section, #27). On None → the gated
        # Gemini-image fallback; OCR-text only if the image can't be fetched.
        from .bc_parse import parse_bc
        image = _image()
        if pre_words is not None:
            wd = {'words': pre_words, 'error': None}
        else:
            wd = _vision_words(image, doc.content_type) if image is not None else {'words': [], 'error': 'no image'}
        parsed = parse_bc(wd.get('words') or []) if not wd.get('error') else None
        if parsed is not None:
            ex = {'fields': parsed, 'warnings': [], 'error': '', 'capture': 'deterministic'}
        elif image is not None:
            ex = extract_document_fields('', doc.doc_type, image=image, content_type=doc.content_type)
            ex['capture'] = 'ai'
        else:
            r = ocr if ocr is not None else ocr_document(doc)
            ex = extract_document_fields(r.get('text', ''), doc.doc_type)
            ex['capture'] = 'ai'
    else:
        r = ocr if ocr is not None else ocr_document(doc)
        if r['error'] or not (r['text'] or '').strip():
            ex = {'fields': {}, 'warnings': [], 'error': r['error'] or 'no text read'}
        else:
            # Deterministic label-anchored capture first for the standardised-issuer docs;
            # None (unrecognised layout) → Gemini reads it. parse_by_labels never raises.
            parsed = parse_by_labels(doc.doc_type, r['text'])
            if parsed is not None:
                ex = {'fields': parsed, 'warnings': [], 'error': '', 'capture': 'deterministic'}
            else:
                ex = extract_document_fields(r['text'], doc.doc_type)
                ex['capture'] = 'ai'

    if ex['error']:
        result = {'fields': {}, 'warnings': [], 'student_verdict': 'unreadable',
                  'capture': ex.get('capture', 'ai'), 'error': ex['error']}
    else:
        verdict = doc_student_verdict(doc.doc_type, ex['fields'], names=names,
                                      postcode=postcode, city=city, street=street,
                                      check_address=check_address)
        result = {'fields': ex['fields'], 'warnings': ex['warnings'],
                  'student_verdict': verdict, 'capture': ex.get('capture', 'ai'), 'error': ''}
    # Genuineness fingerprint (flag-gated, soft): a multimodal "does this look like a real
    # official document?" read → vision_fields['authenticity']. One extra Gemini call per
    # supporting doc; never blocks. (The IC has its own in run_vision_for_document.) The
    # results-slip already fetched its image above; the others fetch here.
    if getattr(settings, 'DOC_GENUINENESS_CHECK_ENABLED', False):
        if doc.doc_type == 'results_slip':
            # Probabilistic SIGNATURE genuineness (deterministic + auditable) over the OCR text,
            # plus a focused multimodal read for the two VISUAL signatures (QR + crest) on the
            # already-fetched image. A failed/empty OCR read yields NO signal — we never penalise
            # a student for our failure.
            from .genuineness.results_doc import signature_genuineness, results_visual_markers
            rr = ocr if ocr is not None else ocr_document(doc)
            text = (rr or {}).get('text', '') or ''
            if text.strip() and not (rr or {}).get('error'):
                markers = results_visual_markers(image, doc.content_type) if image is not None else {}
                sg = signature_genuineness(text, has_qr=markers.get('has_qr', False),
                                           has_crest=markers.get('has_crest', False))
                result['authenticity'] = {
                    'status': sg['status'], 'reason': sg['reason'], 'doc_seen': sg['type'],
                    'probability': sg['probability'], 'present': sg['present'], 'missing': sg['missing'],
                    'model_version': sg.get('model_version'),
                }
        elif doc.doc_type == 'offer_letter':
            # SIGNATURE genuineness over the OCR text (MODEL_VERSION 1.4.0: scored purely by-score via
            # `band_for`, no issuer anchor) → genuine (≥0.70) / suspect (0.35–0.70) / not_offer_letter
            # (<0.35). Text-only — the crest/JPPKK seal are bonus and the text signatures already clear
            # the band. No text + no image → no signal.
            from .genuineness import assess
            rr = ocr if ocr is not None else ocr_document(doc)
            text = (rr or {}).get('text', '') or ''
            gimg = image if image is not None else _fetch_image_bytes(doc.storage_path)
            # The offer is scored TEXT-only (signatures). An empty/failed OCR is OUR failure →
            # no signal, never a 'suspect' penalty (mirrors the slip/BC/EPF branches).
            auth = (assess('offer_letter', image=gimg, content_type=doc.content_type, ocr_text=text)
                    if text.strip() and not (rr or {}).get('error') else None)
            if auth and auth.get('status'):
                # The by-score status is stored as-is (the pathway verdict + submission gate treat
                # anything != 'genuine' as not an official offer). A legacy 'unrecognised' (pre-1.4.0
                # stored value) is still folded to 'suspect' for badge/cap vocabulary.
                st = 'suspect' if auth['status'] == 'unrecognised' else auth['status']
                result['authenticity'] = {
                    'status': st,
                    'reason': auth.get('reason', ''),
                    'doc_seen': auth.get('type') or auth.get('doc_seen', ''),
                    **({'probability': auth['probability'], 'present': auth['present'],
                        'missing': auth['missing'], 'model_version': auth.get('model_version')}
                       if 'probability' in auth else {}),
                }
        elif doc.doc_type in ('birth_certificate', 'epf'):
            # Probabilistic SIGNATURE genuineness over the OCR text (deterministic + auditable;
            # TD-122). Text-dominant — the visual markers (BC barcode/crest, KWSP logo) are bonus
            # and the text signatures already clear the band; the EPF scorer also doubles as the
            # wrong-type backstop (tax form / withdrawal / STR-as-EPF → not_epf). A failed/empty
            # OCR read yields NO signal (never penalise a student for our failure).
            from .genuineness.results_doc import signature_genuineness
            rr = ocr if ocr is not None else ocr_document(doc)
            text = (rr or {}).get('text', '') or ''
            if text.strip() and not (rr or {}).get('error'):
                sg = signature_genuineness(text, doc_type=doc.doc_type)
                result['authenticity'] = {
                    'status': sg['status'], 'reason': sg['reason'], 'doc_seen': sg['type'],
                    'probability': sg['probability'], 'present': sg['present'], 'missing': sg['missing'],
                    'model_version': sg.get('model_version'),
                }
        elif doc.doc_type == 'str':
            # SIGNATURE genuineness over the OCR text for the three STR approval forms (MOF
            # letter / MySTR dashboard / Semakan Status); an LHDN SALINAN copy or a SARA letter
            # is unrecognised → holistic fallback on the image (which still accepts a genuine
            # MySTR screenshot). Approval vs SALINAN stays the extraction `status` field.
            from .genuineness import assess
            rr = ocr if ocr is not None else ocr_document(doc)
            text = (rr or {}).get('text', '') or ''
            gimg = _image()   # str field-extraction is text-based; bytes for the holistic fallback
            auth = assess('str', image=gimg, content_type=doc.content_type, ocr_text=text)
            if auth and auth.get('status'):
                result['authenticity'] = {
                    'status': auth['status'],
                    'reason': auth.get('reason', ''),
                    'doc_seen': auth.get('type') or auth.get('doc_seen', ''),
                    **({'probability': auth['probability'], 'present': auth['present'],
                        'missing': auth['missing'], 'model_version': auth.get('model_version')}
                       if 'probability' in auth else {}),
                }
        elif doc.doc_type == 'salary_slip':
            # No POSITIVE payslip fingerprint yet (layouts too varied — a full signature list is
            # future work). LIGHT NEGATIVE backstop: if the doc in the salary-slip slot reads
            # UNAMBIGUOUSLY as a DIFFERENT known document (an EPF statement, BC, results slip, STR),
            # flag not_salary_slip so the officer gets a wrong-type chip. Text-only + deterministic;
            # a genuine payslip matches no other family → no signal. A failed/empty OCR = no signal.
            from .genuineness.results_doc import misfiled_as
            rr = ocr if ocr is not None else ocr_document(doc)
            text = (rr or {}).get('text', '') or ''
            if text.strip() and not (rr or {}).get('error'):
                mis = misfiled_as('salary_slip', text)
                if mis:
                    result['authenticity'] = mis
        elif doc.doc_type in _GENUINENESS_DOCS:   # birth_certificate/epf holistic fallback (+ any other)
            gimg = _image()
            if gimg is not None:
                auth = doc_genuineness(gimg, doc.content_type, doc.doc_type)
                if auth:
                    result['authenticity'] = auth
    # Clobber guard (code-health S2 #5): the blob on a row is immutable, so a FAILED run
    # (fetch/OCR/model error → empty fields) where the row already holds a successful
    # extraction is OUR failure — a Storage outage or a checkout without Storage access.
    # Overwriting good fields with an empty error read is exactly the incident mode that
    # destroyed vision_fields in the past (memory: halatuju_never_reextract_locally).
    # Keep the stored read; report the failure to the caller without persisting it.
    prior = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    if result['error'] and (prior.get('fields') or (prior.get('text') or '').strip()):
        logger.warning('run_field_extraction: kept stored extraction for doc %s (re-run failed: %s)',
                       doc.id, result['error'])
        return {**result, 'stale_kept': True}
    doc.vision_fields = result
    doc.vision_fields_run_at = timezone.now()
    doc.save(update_fields=['vision_fields', 'vision_fields_run_at'])
    return result


# ── Genuineness checks live in the genuineness/ package (one home, per the architecture) ──
# Re-exported here so the upload path above and back-compatible imports
# (apps.scholarship.vision.ic_genuineness / .doc_genuineness) keep resolving unchanged.
from .genuineness.ic import ic_genuineness            # noqa: E402,F401
from .genuineness.supporting_doc import doc_genuineness, _GENUINENESS_DOCS  # noqa: E402,F401
