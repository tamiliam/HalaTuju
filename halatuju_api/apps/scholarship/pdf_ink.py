"""S-visible 2 — the ink check (owner rule: "the visible page always judges", 20 Nov 2026).

A rules lane (UMS first) locks only when the words it relied on are in the text layer and drawn in a painting
render mode (S-visible). White, covered, tiny, clipped, off-page or squeezed text still passed that. Here pdfium,
which paints the page, says what each page-1 character adds to the PICTURE (`pdfium_worker._op_ink`: the page
rendered as is, minus the same page with every text object made invisible), and `ink_missing` asks, for every
word of every owner phrase and every printed value the lock used, at EVERY place it occurs on page 1:

* every character leaves ink (`INK_DELTA` in the child: a pixel the text changes by >= 96 of 255; mid grey counts,
  lighter does not) — and at least `MIN_CHAR_SHARE` of its box;
* the word's tallest glyph is at least `MIN_H_PT` high, and not squeezed (`MIN_W_RATIO`: width per character
  against its height);
* every character's box lies inside the rendered page;
* no OTHER character covers more than `MAX_OVERLAP` of its own box with the word's box (a hidden word placed
  under other visible text would borrow that text's ink);
* the page: text objects use render modes 0-2 only, and every annotation is a /Link (pdfium does not draw a
  FreeText with no appearance; another viewer might).

The words are found in PDFIUM's own text of the page (the same engine as the boxes), normalised as the owner words
are (`offer_owner_words._norm`: NFKD, accents off, upper case, each run of non-letters/digits one space), with two
tolerances real letters need: the space BETWEEN a phrase's words is optional (pdfium glues "KE UNIVERSITI"), and a
value may carry a separator between any two characters (the IC is stored as printed 6-2-4 digits; pdfium may split
words). Word edges stay strict. A target pdfium cannot find refuses (pypdf found it; pdfium did not).

Thresholds measured on the genuine corpus (counts only): the 33 UMS letters the lane locks (330 phrase targets, 165
values) and the owner-phrase-lockable UiTM (3 on pypdf 5.9, 8 on 6.21), UUM 4, UPSI 2 and UM 2 letters: 0 fail, on
both pypdf versions. Pure (no pdfium here): `page1_ink` asks the child, the rest is arithmetic on its answer.
Labels only (``p<n>``, ``v:<field>``, ``page:modes``, ``page:annots``, ``no_answer``, ``no_targets``), never text.
"""
from __future__ import annotations

import re
import unicodedata

#: Render resolution of the ink op (dots per inch). Every attack was caught at 72, 100 and 150; 100 is the cheaper
#: of the two that also catch a Tz 3 squeeze by ink (the width rule catches it at any resolution).
DPI = 100
#: A pixel is ink when the text changes its luminance (0-255) by at least this. Genuine per-word maximum: 121 at
#: the lowest (p1 216); a 0.93 grey 16, 0.5 pt text 19, a Tz 3 squeeze 86, white / covered / clipped 0.
INK_DELTA = 96
#: The tallest glyph of a word, in points (genuine minimum 4.66; 0.5 pt text: 0.32).
MIN_H_PT = 3.0
#: A word's width over (characters x height) (genuine minimum 0.12; Tz 3: 0.028).
MIN_W_RATIO = 0.06
#: Another character covering more than this share of its own box with the word's box refuses the word.
MAX_OVERLAP = 0.30
#: The least share of a character's box (+1 px) that must be ink (open risk 2: a character covered all but a
#: sliver). Genuine minimum 0.143 over 16,647 characters of every target word (p0.1 0.159); 0.10 costs none.
MIN_CHAR_SHARE = 0.10
#: A target found more often than this on page 1 refuses (bounds the work; a genuine letter prints any one of
#: its phrases a handful of times).
MAX_OCCURRENCES = 20
_NOT_WORD = re.compile(r'[\W_]')
_ROW = 9            # [codepoint, generated, l, b, r, t, ink_px, area_px, inside]


def ink_op(count: int) -> dict:
    """The child request for page 1's ink (`pdfium_worker._op_ink`); ``count`` is pypdf's page count. The raster
    bounds are `pdf_pages`' own, at `DPI`."""
    from .pdf_pages import MAX_PAGE_SIDE_PT, MAX_RASTER_SIDE_PX
    return {'op': 'ink', 'page': 0, 'count': int(count), 'delta': INK_DELTA,
            'scale': [DPI, MAX_RASTER_SIDE_PX, MAX_PAGE_SIDE_PT]}


def ink_ops(data: bytes) -> list:
    """[the ink op] for a PDF whose page 1 passes `pdf_render_check` (the render pre-filter), else []."""
    from .pdf_pages import _checked
    n = _checked(data, lambda n: [0])
    return [ink_op(n)] if n > 0 else []


def page1_ink(data: bytes):
    """Page 1's ink answer, or None (no answer: refused). `pdf_rules_pages.pdf_page1_layout` asks the same op in the
    layout's own child, so this is normally the child memo's answer and spawns nothing."""
    from . import pdfium_run
    ops = ink_ops(data) if data else []
    got = pdfium_run.ask(data, ops) if ops else None
    return got[0] if got else None


def _norm_map(chars) -> tuple:
    """(normalised text, for each of its characters the char index it came from or None for a space)."""
    out, idx = [], []
    for i, row in enumerate(chars):
        ch = ' ' if row[1] else chr(int(row[0]))
        part = ''.join(c for c in unicodedata.normalize('NFKD', ch) if not unicodedata.combining(c)).upper()
        for c in part or ' ':
            if _NOT_WORD.match(c) or c.isspace():
                if out and out[-1] != ' ':
                    out.append(' ')
                    idx.append(None)
            else:
                out.append(c)
                idx.append(i)
    return ''.join(out), idx


def _norm(s: str) -> str:
    return _norm_map([[ord(c), 0] for c in (s or '')])[0].strip()


def _pattern(target: str, value: bool):
    """A phrase: its words with an optional space between them; a value: an optional space between any two
    characters. Strict word edges both ends. None when nothing is left to find."""
    n = _norm(target)
    parts = list(n.replace(' ', '')) if value else n.split(' ')
    if not n:
        return None
    return re.compile(r'(?<!\w)' + ' ?'.join(re.escape(p) for p in parts) + r'(?!\w)')


def _words(m, idx) -> list:
    """The char-index groups (words) of one match."""
    words, cur = [], []
    for k in range(m.start(), m.end()):
        if idx[k] is None:
            if cur:
                words.append(cur)
                cur = []
        elif not cur or cur[-1] != idx[k]:
            cur.append(idx[k])
    if cur:
        words.append(cur)
    return words


def _word_ok(ci, chars, solid) -> bool:
    """The word rules (module docstring) for the char indices ``ci``; ``solid``: every non-space char's index."""
    rows = [chars[i] for i in ci]
    if not rows or any(r[1] or not r[8] or r[6] <= 0 or r[7] <= 0 for r in rows):
        return False
    if any(r[6] < MIN_CHAR_SHARE * r[7] for r in rows):
        return False
    height = max(r[5] - r[3] for r in rows)
    left, bottom = min(r[2] for r in rows), min(r[3] for r in rows)
    right, top = max(r[4] for r in rows), max(r[5] for r in rows)
    if height < MIN_H_PT or (right - left) < MIN_W_RATIO * len(rows) * height:
        return False
    own = set(ci)
    for j in solid:
        if j in own:
            continue
        r = chars[j]
        ix, iy = min(right, r[4]) - max(left, r[2]), min(top, r[5]) - max(bottom, r[3])
        if ix > 0 and iy > 0 and ix * iy > MAX_OVERLAP * max(1e-6, (r[4] - r[2]) * (r[5] - r[3])):
            return False
    return True


def _rows(ink):
    """The answer's char rows, or None when it is not a well-formed answer."""
    if not isinstance(ink, dict) or ink.get('error') or not isinstance(ink.get('chars'), list):
        return None
    rows = ink['chars']
    for r in rows:
        if not (isinstance(r, list) and len(r) == _ROW and all(isinstance(v, (int, float)) for v in r)
                and 0 <= r[0] <= 0x10FFFF):
            return None
    return rows


def ink_missing(ink, phrases, values) -> list:
    """The labels of the targets that do not leave real ink on page 1 ([] = every one does). ``ink``: the child's
    answer (`page1_ink`; None or an error refuses: ``no_answer``). ``phrases`` / ``values``: (label, text) pairs —
    a phrase may lose the space between its words, a value may gain a separator between any two characters. A
    target absent from pdfium's text, found more than `MAX_OCCURRENCES` times, or with ANY occurrence failing a
    word rule gives its label; the page rules give ``page:modes`` / ``page:annots``. No targets: ``no_targets``."""
    chars = _rows(ink)
    if chars is None:
        return ['no_answer']
    targets = [(lab, t, False) for lab, t in phrases or ()] + [(lab, t, True) for lab, t in values or ()]
    if not targets:
        return ['no_targets']
    out = [lab for lab, ok in (('page:modes', ink.get('modes_ok')), ('page:annots', ink.get('annots_ok'))) if ok is not True]
    normed, idx = _norm_map(chars)
    solid = [i for i, r in enumerate(chars) if not r[1] and not chr(int(r[0])).isspace()]
    for label, target, value in targets:
        pat = _pattern(target, value)
        found = list(pat.finditer(normed)) if pat else []
        if not found or len(found) > MAX_OCCURRENCES or not all(
                _word_ok(w, chars, solid) for m in found for w in _words(m, idx)):
            if label not in out:
                out.append(label)
    return out
