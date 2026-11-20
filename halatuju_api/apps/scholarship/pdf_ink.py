"""S-visible 2 — the ink check (owner rule: "the visible page always judges", 20 Nov 2026).

A rules lane (UMS first) locks only when the words it relied on are in the text layer and drawn in a painting
render mode (S-visible). White, covered, tiny, clipped, off-page or squeezed text still passed that. Here pdfium,
which paints the page, says what each page-1 character adds to the PICTURE (`pdfium_worker._op_ink`: the page
rendered as is, minus the same page with every text object made invisible), and `ink_missing` asks, for every
word of every owner phrase and every printed value the lock used, at EVERY place it occurs on page 1:

* every character leaves ink (`INK_DELTA` in the child: a pixel the text changes by >= 96 of 255; mid grey counts,
  lighter does not) — at least `MIN_CHAR_SHARE` of its box, and its ink spans at least `MIN_H_COVER` of the box's
  height and `MIN_W_COVER` of its width (review round 1, B2: a word covered all but a thin strip);
* the word's tallest glyph is at least `MIN_H_PT` high, and not squeezed (`MIN_W_RATIO`: width per character
  against its height);
* every character's box lies inside the rendered page;
* no OTHER character covers more than `MAX_OVERLAP` of its own box with the word's box, and the other characters
  together cover at most `MAX_OVERLAP` of each target character's OWN box (review round 1, B1: a hidden word under
  other visible text, or under a row of large black glyphs, would borrow that text's ink); a space in the text
  with a real box and ink in it counts as another character (review round 2: a glyph ToUnicode calls a space);
* the page: text objects only fill (render mode 0: another line's stroke paints past its glyph boxes), every
  annotation is a /Link (pdfium does not draw a FreeText with no appearance; another viewer might), at most
  `MAX_STRAY_PX` of ink lies away from every character's box (text drawing outside the box pdfium gives it), no
  page-1 content is optional content, the document has no XFA form (a viewer may show another page), and page 1
  reaches no Type3 font at all (fix round 3, owner 20 Nov: "refuse home-made fonts on UMS letters"; a lane in
  `TYPE3_LANES` may carry one when every glyph paints only inside its own box, review round 2).

Known residuals (S-visible 3, owner decision): a font whose ToUnicode lies (its glyphs drawn as other letters) still
passes; only reading the word crops closes it. (Black glyphs touching a white character put ink in its +1 px ring:
closed in review round 2b, `pdfium_worker._ink` counts only ink the other characters cannot explain.)

The words are found in PDFIUM's own text of the page (the same engine as the boxes), normalised as the owner words
are (`offer_owner_words._norm`: NFKD, accents off, upper case, each run of non-letters/digits one space), with two
tolerances real letters need: the space BETWEEN a phrase's words is optional (pdfium glues "KE UNIVERSITI"), and a
value may carry a separator between any two characters (the IC is stored as printed 6-2-4 digits; pdfium may split
words). Word edges stay strict. A target pdfium cannot find refuses (pypdf found it; pdfium did not).

Thresholds measured on the genuine corpus (counts only): the 33 UMS letters the lane locks (330 phrase targets, 165
values) and the owner-phrase-lockable UiTM (3 on pypdf 5.9, 8 on 6.21), UUM 4, UPSI 2 and UM 2 letters: 0 fail, on
both pypdf versions. Pure (no pdfium here): `page1_ink` asks the child, the rest is arithmetic on its answer.
Labels only (``p<n>``, ``v:<field>``, ``page:<rule>``, ``no_answer``, ``no_targets``), never text.
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
#: Another character covering more than this share of its own box with the word's box refuses the word; so do the
#: other characters together covering more than this share of a target character's box. Review round 2, B1: at
#: 0.30, tall narrow black bars (Tz-squeezed ZapfDingbats) each covering 29 % of a white character lent it their
#: ink. Genuine: the most any target character is covered is 0.0 on UMS (33 locks), UUM and UM, 0.053 on UPSI
#: (the brief's 0.05 cost both UPSI letters). Kept below `MIN_CHAR_SHARE`, so what other glyphs may lend never
#: reaches the ink a character needs.
MAX_OVERLAP = 0.08
#: The ring (review round 2, the builder's own probe): black glyphs TOUCHING a white character from above and below
#: put their edge pixels in its box +1 px (share 0.79, full height) and a white IC passed. Widening this lending
#: rule by 2 px cost every genuine letter, so it stays 0; review round 2b closed the ring in the child instead
#: (`pdfium_worker._ink`: a pixel another character's box can explain is not this character's ink).
RING_PX = 0
#: The least share of a character's box (+1 px) that must be ink (open risk 2: a character covered all but a
#: sliver). Genuine minimum 0.130 (UUM; UMS 0.159) after review round 2b's attribution; 0.10 costs none.
MIN_CHAR_SHARE = 0.10
#: The least share of a character box's height (+1 px) its ink spans (review round 1, B2). Genuine minimum per
#: issuer: UMS 0.727 (16,945 characters), UiTM 0.545, UM 0.70, UPSI 0.667, UUM 0.667; a 1-2 pt strip: 0.2-0.3.
MIN_H_COVER = 0.5
#: The same across its width (genuine minimum 0.25 on every issuer: a narrow I or l in its padded box).
MIN_W_COVER = 0.15
#: The most ink pixels allowed farther than `pdfium_worker.STRAY_PAD` from every character box (genuine: 0).
MAX_STRAY_PX = 4
#: A target found more often than this on page 1 refuses (bounds the work; a genuine letter prints any one of
#: its phrases a handful of times).
MAX_OCCURRENCES = 20
#: The rules lanes whose letters may carry a Type3 (home-made) font on page 1; every other lane's letter refuses
#: one outright (``page:type3``). Fix round 3 (review round 3's BLOCKER: a flat Type3 glyph painted a block onto a
#: white IC within `pdfium_worker.T3_TOLERANCE` and locked). Empty while the rules lane is UMS-only (0 of the 58
#: UMS letters carry one); S2 adds a lane here only once that tolerance is fixed (decisions.md, 20 Nov).
TYPE3_LANES: frozenset = frozenset()
_NOT_WORD = re.compile(r'[\W_]')
_ROW = 11           # [codepoint, generated, l, b, r, t, ink_px, area_px, inside, cover_h, cover_w]


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


def _ink_norm(s: str) -> str:
    return _norm_map([[ord(c), 0] for c in (s or '')])[0].strip()


def _ink_pattern(target: str, value: bool):
    """A phrase: its words with an optional space between them; a value: an optional space between any two
    characters. Strict word edges both ends. None when nothing is left to find."""
    n = _ink_norm(target)
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


def _word_ok(ci, chars, solid, pad=0.0) -> bool:
    """The word rules (module docstring) for the char indices ``ci``; ``solid``: every drawn char's index (not
    generated; a space only with a real box); ``pad``: `RING_PX` in points (what the lending rule widens by)."""
    rows = [chars[i] for i in ci]
    if not rows or any(r[1] or not r[8] or r[6] <= 0 or r[7] <= 0 for r in rows):
        return False
    if any(r[6] < MIN_CHAR_SHARE * r[7] or r[9] < MIN_H_COVER or r[10] < MIN_W_COVER for r in rows):
        return False
    height = max(r[5] - r[3] for r in rows)
    left, bottom = min(r[2] for r in rows), min(r[3] for r in rows)
    right, top = max(r[4] for r in rows), max(r[5] for r in rows)
    if height < MIN_H_PT or (right - left) < MIN_W_RATIO * len(rows) * height:
        return False
    own, near = set(ci), []
    for j in solid:
        if j in own:
            continue
        r = chars[j]
        ix, iy = min(right, r[4]) - max(left, r[2]), min(top, r[5]) - max(bottom, r[3])
        if ix > 0 and iy > 0 and ix * iy > MAX_OVERLAP * _area(r):
            return False                           # another character mostly inside the word's box
        if min(right + pad, r[4]) > max(left - pad, r[2]) and min(top + pad, r[5]) > max(bottom - pad, r[3]):
            near.append(r)
    return all(_covered(w, near) <= MAX_OVERLAP * _area(w)
               for w in ([a[0], a[1], a[2] - pad, a[3] - pad, a[4] + pad, a[5] + pad] for a in rows))


def _boxed(r) -> bool:
    """A real (non-empty) box."""
    return r[4] > r[2] and r[5] > r[3]


def _drawn_space(r) -> bool:
    """Review round 2, #3: a space in the text with a real box and ink in that box (the child counts a space's
    ink in its own box, no ring) is a drawn glyph — a glyph ToUnicode calls a space — and joins every overlap rule.
    A genuine space draws nothing (0 of the genuine corpus's boxed spaces holds ink)."""
    return _boxed(r) and r[6] > 0


def _area(r) -> float:
    return max(1e-6, (r[4] - r[2]) * (r[5] - r[3]))


def _covered(a, others) -> float:
    """How much of char ``a``'s box the ``others`` cover, summed (at least their union: refuses more, never less)."""
    total = 0.0
    for r in others:
        ix, iy = min(a[4], r[4]) - max(a[2], r[2]), min(a[5], r[5]) - max(a[3], r[3])
        if ix > 0 and iy > 0:
            total += ix * iy
    return total


def _ink_rows(ink):
    """The answer's char rows, or None when it is not a well-formed answer."""
    if not isinstance(ink, dict) or ink.get('error') or not isinstance(ink.get('chars'), list):
        return None
    px = ink.get('px_pt')
    if isinstance(px, bool) or not isinstance(px, (int, float)) or not 0 < px <= 10:
        return None
    rows = ink['chars']
    for r in rows:
        if not (isinstance(r, list) and len(r) == _ROW and all(isinstance(v, (int, float)) for v in r)
                and 0 <= r[0] <= 0x10FFFF):
            return None
    return rows


def _page_labels(ink, type3_allowed: bool) -> list:
    """The page rules (module docstring) the answer breaks; a missing or malformed flag breaks its rule. Type3:
    none at all, or (``type3_allowed``) every glyph inside its box."""
    stray = ink.get('stray_px')
    return [lab for lab, ok in (
        ('page:modes', ink.get('modes_ok') is True), ('page:annots', ink.get('annots_ok') is True),
        ('page:stray', isinstance(stray, int) and not isinstance(stray, bool) and 0 <= stray <= MAX_STRAY_PX),
        ('page:optional', ink.get('optional') is False), ('page:xfa', ink.get('xfa') is False),
        ('page:type3', ink.get('type3_ok') is True and (type3_allowed or ink.get('type3') is False))) if not ok]


def ink_missing(ink, phrases, values, lane: str = '') -> list:
    """The labels of the targets that do not leave real ink on page 1 ([] = every one does). ``ink``: the child's
    answer (`page1_ink`; None or an error refuses: ``no_answer``). ``phrases`` / ``values``: (label, text) pairs —
    a phrase may lose the space between its words, a value may gain a separator between any two characters. A
    target absent from pdfium's text, found more than `MAX_OCCURRENCES` times, or with ANY occurrence failing a
    word rule gives its label; each page rule broken gives ``page:<rule>``. No targets: ``no_targets``. ``lane``:
    the rules lane asking; a Type3 font on page 1 refuses unless it is in `TYPE3_LANES`."""
    chars = _ink_rows(ink)
    if chars is None:
        return ['no_answer']
    targets = [(lab, t, False) for lab, t in phrases or ()] + [(lab, t, True) for lab, t in values or ()]
    if not targets:
        return ['no_targets']
    out = _page_labels(ink, lane in TYPE3_LANES)
    normed, idx = _norm_map(chars)
    solid = [i for i, r in enumerate(chars) if not r[1] and (not chr(int(r[0])).isspace() or _drawn_space(r))]
    pad = RING_PX * ink['px_pt']
    for label, target, value in targets:
        pat = _ink_pattern(target, value)
        found = list(pat.finditer(normed)) if pat else []
        if not found or len(found) > MAX_OCCURRENCES or not all(
                _word_ok(w, chars, solid, pad) for m in found for w in _words(m, idx)):
            if label not in out:
                out.append(label)
    return out
