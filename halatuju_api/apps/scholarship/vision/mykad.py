"""MyKad OCR-text parse: NRIC, name and address off the card (moved verbatim from ``vision.py``,
audit sprint A3.1)."""

import math
import re

from .names import _NAME_NOISE


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


# Five digits standing alone as a number. Not ``\b`` on the right: OCR often glues the town to the
# postcode ("47000SUNGAI BULOH"), and a word boundary never falls between a digit and a letter.
_MY_POSTCODE = re.compile(r'(?<![\d-])\d{5}(?!\d)')

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


def _extract_address(text: str, skip=()) -> str:
    """
    Best-effort MyKad address extraction. The MyKad front shows the holder's
    registered home address as 3 lines: street, ``<5-digit postcode> <city>``,
    and ``<state>``. Strategy: find the line containing a 5-digit Malaysian
    postcode; walk UP to gather the 1-2 preceding address lines, and also
    pick up the very next line if it matches a known Malaysian state.
    Returns ``''`` when no postcode-anchored block is found.

    ``skip``: the card's name lines as the layout read found them (request #67) — a name line
    with no A/L, A/P, BIN or "@" is otherwise taken for the first line of the address.

    Soft signal only — admin can spot e.g. an outdated registered address that
    differs from what the student typed in the Story tab. No verdict computed.
    """
    if not text:
        return ''
    skip_keys = {_compact(ln) for ln in skip if _compact(ln)}
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
        if _NAME_NOISE.search(ln) or _compact(ln) in skip_keys:
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


# ── The layout read (request #67) ─────────────────────────────────────────────────────────────
# The flattened OCR text keeps the ORDER of the lines but loses where they sit, so the text read
# above has to guess where the name ends — from A/L, A/P or BIN. A name that runs onto a second
# line after a mid-line marker, or that has no marker at all (many Chinese, Christian and Iban
# names), lost a line to the address. The card itself is unambiguous: the name is printed under
# the IC number, and a blank line separates it from the address. The word boxes from the same
# Vision call show that blank line, so the layout read uses it.

def _compact(s: str) -> str:
    """Letters and digits only, upper case — compares one read of a line with another however
    the OCR spaced or punctuated it ("A / L" and "A/L" are the same line)."""
    return re.sub(r'[^A-Z0-9]', '', (s or '').upper())


# A line that opens with one of these is the start of an address, never a name's second line —
# a guard for a card whose blank line the photo did not show.
_ADDRESS_OPENERS = frozenset({
    'NO', 'LOT', 'JALAN', 'JLN', 'TAMAN', 'TMN', 'KAMPUNG', 'KAMPONG', 'KG', 'BLOK', 'BLK',
    'LORONG', 'LRG', 'PERSIARAN', 'LENGKOK', 'APARTMENT', 'APT', 'PANGSAPURI', 'FLAT', 'RUMAH',
    'BANDAR', 'BDR', 'BATU', 'PPR', 'UNIT', 'TINGKAT', 'ESTATE', 'LADANG', 'MUKIM', 'SIMPANG',
})

_SPACED_MARKER = re.compile(r'\b([AaSsDd])\s*/\s*([LlPpOo])\b')


def _median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 0.0


def _card_lines(words) -> list[dict]:
    """The card's printed lines, from the word boxes: words that sit on the same baseline AND
    are close along it are one line; a wide horizontal gap starts another (the right-hand
    column — WARGANEGARA, LELAKI, ISLAM — never joins a name or address line). Each line is
    ``{'text', 'u0', 'v', 'h', 'n'}``: its start along the text, its height down the card, its
    letter height and word count. The card is de-rotated by the words' median baseline angle,
    so a tilted or sideways photo reads the same as an upright scan."""
    ws = [w for w in words if (w.get('text') or '').strip()]
    if not ws:
        return []
    theta = math.radians(_median([w['angle'] for w in ws if w.get('angle') is not None]))
    cos, sin = math.cos(theta), math.sin(theta)
    pts = []
    for w in ws:
        wh = w.get('wh') or w.get('h') or 0
        wlen = w.get('wlen') or 0.8 * wh * len(w['text'])
        u = w['cx'] * cos + w['cy'] * sin            # along the text
        v = -w['cx'] * sin + w['cy'] * cos           # down the card
        pts.append({'t': w['text'], 'u0': u - wlen / 2, 'u1': u + wlen / 2, 'v': v, 'h': wh})
    lh = _median([p['h'] for p in pts if p['h']]) or 12.0
    # Join each word to its neighbour on the same baseline (union-find over the close pairs).
    parent = list(range(len(pts)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, a in enumerate(pts):
        for j in range(i + 1, len(pts)):
            b = pts[j]
            if abs(a['v'] - b['v']) > 0.5 * lh:
                continue
            gap = max(b['u0'] - a['u1'], a['u0'] - b['u1'])
            if gap <= 1.5 * lh:
                parent[root(i)] = root(j)
    groups: dict = {}
    for i, p in enumerate(pts):
        groups.setdefault(root(i), []).append(p)
    lines = []
    for g in groups.values():
        g.sort(key=lambda p: p['u0'])
        text = g[0]['t']
        for a, b in zip(g, g[1:]):
            # A slash or a full stop the OCR boxed as its own word sits flush against its
            # neighbours ("A" "/" "L") — no space there; a real word gap gets one.
            text += ('' if b['u0'] - a['u1'] < 0.15 * lh else ' ') + b['t']
        lines.append({'text': text, 'u0': g[0]['u0'], 'v': _median([p['v'] for p in g]),
                      'h': _median([p['h'] for p in g]), 'n': len(g)})
    lines.sort(key=lambda ln: ln['v'])
    return lines


def _name_part_line(text: str) -> bool:
    """Could this line be part of a name: capitals, no digits, mostly letters, not card chrome,
    not an address opener. Looser than _is_name_line on length — a second line can be one short
    word ("LIM", "@ ALI")."""
    if not text or any(ch.isdigit() for ch in text) or text.upper() != text:
        return False
    letters = sum(1 for ch in text if ch.isalpha())
    if letters < 2 or letters / max(len(text.replace(' ', '')), 1) < 0.6:
        return False
    words = [w for w in re.split(r'[^A-Za-z]+', text) if w]
    if not words or all(w.upper() in _MYKAD_HEADER_TOKENS | _ADDRESS_LABEL_TOKENS for w in words):
        return False
    return words[0].upper() not in _ADDRESS_OPENERS


def _layout_read(words, text: str, nric: str):
    """The name and address from where the lines sit on the card, or None when the layout
    cannot be read with confidence (no word boxes, no IC number line, nothing name-like under
    it) — the caller then keeps the line-order read. Returns ``{'name', 'name_lines',
    'address'}``: ``name_lines`` as Vision's own text lines where they match (so the address
    read can skip them), ``address`` the lines after the blank line (used only when the
    postcode-anchored read finds nothing — a blurred or glued postcode)."""
    if not words or not nric:
        return None
    lines = _card_lines(words)
    key = _compact(nric)
    at = next((i for i, ln in enumerate(lines) if key and key in _compact(ln['text'])), -1)
    if at < 0:
        return None
    nric_ln = lines[at]
    below = [ln for ln in lines[at + 1:]
             if ln['v'] > nric_ln['v'] + 0.5 * (nric_ln['h'] or 1) and not _is_card_label_line(ln['text'])]
    if not below:
        return None
    # The name's first line: the top line under the IC number on the card's left. The photo
    # and its labels sit to the right, so a line far right of the IC number is not it.
    lh = _median([ln['h'] for ln in below if ln['h']]) or nric_ln['h'] or 12.0
    first = next((ln for ln in below if ln['u0'] <= nric_ln['u0'] + 6 * lh), None)
    if first is None or not _name_part_line(first['text']):
        return None
    left = [ln for ln in below if abs(ln['u0'] - first['u0']) <= 1.5 * lh and ln['v'] >= first['v']]
    # The ordinary line spacing on this card, and the blank line: a step clearly wider than it.
    steps = [b['v'] - a['v'] for a, b in zip(left, left[1:]) if b['v'] - a['v'] > 0.5 * lh]
    pitch = min(steps) if len(steps) >= 2 else 1.5 * lh
    gap_at = 1.6 * pitch
    block, rest = [left[0]], []
    for prev, ln in zip(left, left[1:]):
        if rest or ln['v'] - prev['v'] > gap_at or len(block) == 3 or not _name_part_line(ln['text']):
            rest.append(ln)
        else:
            block.append(ln)
    # The name must END at the blank line. A block cut short by the three-line cap or by an
    # address-like line, or with no blank line under it, may have taken the address's first
    # line (a corpus check, 2026-11-13: four cards gained a line that was the address's).
    end = block[-1]
    if not rest or rest[0]['v'] - end['v'] <= gap_at:
        return None
    # Every name line must be one Vision itself printed as a text line. Rebuilt from word boxes
    # alone, a line can glue two words or pick up a stray word on the same baseline; in the
    # corpus check every line Vision did not print made a good name worse, and none fixed one.
    by_key = {}
    for t in (text or '').splitlines():
        by_key.setdefault(_compact(t), t.strip())
    if any(_compact(ln['text']) not in by_key for ln in block):
        return None
    name_lines = [_SPACED_MARKER.sub(lambda m: f'{m.group(1)}/{m.group(2)}'.upper(),
                                     by_key[_compact(ln['text'])]) for ln in block]
    # A slash the OCR dropped ("THEEPICAA AP" then the surname) is closed up as the line-order
    # read does — only where a further name line follows the marker.
    fixed = []
    for i, ln in enumerate(name_lines):
        canon = _trailing_marker_canonical(ln) if i + 1 < len(name_lines) else ''
        fixed.append(_replace_trailing_marker(ln, canon) if canon else ln)
    name = _guard_garbled(re.sub(r'\s+', ' ', ' '.join(fixed)).strip())
    if not name:
        return None
    address = ', '.join(a for a in (_ADDRESS_PREFIX_NOISE.sub('', ln['text']).strip()
                                    for ln in rest[:5]) if a)
    return {'name': name, 'name_lines': name_lines, 'address': address}
