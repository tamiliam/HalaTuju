"""The owner's words: what a genuine offer letter of one issuer ALWAYS shows (owner method change, 2026-11-20).

The same method as SPM, NRIC and EPF: the owner looked at sample letters of one issuer and gave the exact words
every genuine letter prints. A university rules lane may lock a letter only when its VISIBLE text (S-visible: a
digital PDF's checked layout / layer text, or a scan's OCR) shows ALL of them; otherwise the AI reads it. This is
an allow-list: it replaces trying to list every way a letter can say "withdrawn" (S1c review rounds 1-3).

Matching (owner's rule, 20 Nov, option 1): the way the genuineness markers match
(`results_doc._norm_fold_upper_alnum`, ONE rule shared): the phrase AND the text are upper-cased, accents folded,
and every run of characters that are not letters or digits becomes one space. So case, line breaks, spacing and
the spaces around "," "/" "." do not matter ("Tahniah , sukacita", "Saudara / i" match). Kept:

* a phrase is whole words: no letter or digit glued on either side ("Programme" is not "Program",
  "Rujukankami" is not "Rujukan");
* a ONE-word phrase ("Program", "Rujukan") does not count where it sits inside another listed phrase's match
  ("Kod Program", "program pengajian"): the label must be printed on its own;
* no OCR misreading is forgiven.

Per issuer, as DATA (`OWNER_WORDS`), keyed by the rules lane: S2 / S3 add UPSI, UUM and the rest as new rows.
Pure; never raises on text input; linear in the text (each phrase is literal words joined by bounded spaces).
"""
from __future__ import annotations

import re

#: The rules lane -> the owner's required phrases, numbered from 1 in this order (the refusal records numbers only).
OWNER_WORDS = {
    # Universiti Malaysia Sabah (owner, 20 Nov). 4: the owner typed "UNIVERSII", the typo of UNIVERSITI. 5 and 6
    # were given as one line; the student's name sits between "bahawa" and "telah", so they are two phrases.
    'ua:UMS': (
        'BAHAGIAN PERKHIDMATAN AKADEMIK',
        'Rujukan',
        'No. Kad Pengenalan',
        'TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA SABAH',
        'Tahniah, sukacita dimaklumkan bahawa',
        'telah ditawarkan tempat',
        'Program',
        'Kod Program',
        'Sekiranya saudara/saudari menerima tawaran ini',
        'Tarikh Lapor Diri',
        'Saudara/i akan mengikuti program pengajian',
    ),
}

#: Per issuer (rules lane): the phrase numbers NOT required on a PDF read from its TEXT LAYER, because that
#: issuer prints them as part of its letterhead picture (owner, 20 Nov: UMS phrase 1). A scan (OCR of the page
#: image) still needs every phrase.
OPTIONAL_ON_TEXT_PDF = {'ua:UMS': (1,)}


def _norm(text: str) -> str:
    """The genuineness markers' rule (`results_doc._norm_fold_upper_alnum`), applied to phrase and text alike."""
    from .genuineness.results_doc import _norm_fold_upper_alnum
    return _norm_fold_upper_alnum(text)


def _pattern(phrase: str):
    """The normalised phrase as whole words in the normalised text (single spaces, so a literal match)."""
    return re.compile(r'(?<![A-Z0-9])' + re.escape(_norm(phrase)) + r'(?![A-Z0-9])')


_PATTERNS = {lane: tuple(_pattern(p) for p in phrases) for lane, phrases in OWNER_WORDS.items()}


def _shown(lane: str, text: str) -> set:
    """The 0-based indices of ``lane``'s phrases that ``text`` shows (the one-word rule in the module docstring)."""
    pats = _PATTERNS.get(lane, ())
    text = _norm(text) if pats else ''
    spans = [[m.span() for m in p.finditer(text)] for p in pats]
    multi = _merged(sorted(s for k, p in enumerate(OWNER_WORDS.get(lane, ())) if len(p.split()) > 1 for s in spans[k]))
    shown = set()
    for k, phrase in enumerate(OWNER_WORDS.get(lane, ())):
        own = spans[k]
        if len(phrase.split()) == 1:
            own = [s for s in own if not _inside(s, multi)]
        if own:
            shown.add(k)
    return shown


def _merged(spans) -> list:
    """Sorted spans merged into disjoint ones (two overlapping phrases cover their union: refusing more is safe)."""
    out = []
    for a, b in spans:
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _inside(span, merged) -> bool:
    """True when ``span`` lies within one of the disjoint, sorted ``merged`` spans (one bisect: linear overall)."""
    import bisect
    i = bisect.bisect_right(merged, (span[0], float('inf'))) - 1
    return i >= 0 and merged[i][0] <= span[0] and span[1] <= merged[i][1]


def missing(lane: str, text: str, text_pdf: bool = False) -> list:
    """The 1-based numbers of ``lane``'s owner phrases that ``text`` does NOT show ([] = all shown). A lane with
    no owner list misses nothing here; the caller decides whether such a lane may lock at all. ``text_pdf`` (the
    visible text of a PDF read from its text layer) excuses the lane's `OPTIONAL_ON_TEXT_PDF` phrases only."""
    shown = _shown(lane, text)
    excused = set(OPTIONAL_ON_TEXT_PDF.get(lane, ())) if text_pdf else set()
    return [k + 1 for k in range(len(OWNER_WORDS.get(lane, ()))) if k not in shown and k + 1 not in excused]


def page_of_each(lane: str, pages) -> dict:
    """{phrase number: the 1-based page that first shows it, or 0 when no ONE page does} — for the eval (counts)."""
    out = {}
    for k in range(len(OWNER_WORDS.get(lane, ()))):
        out[k + 1] = next((n + 1 for n, page in enumerate(pages or ()) if k in _shown(lane, page)), 0)
    return out
