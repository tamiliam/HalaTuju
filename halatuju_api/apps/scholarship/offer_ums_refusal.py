"""The UMS letter's refusal checks — split out of `offer_parse_university` (S1c owner words, 2026-11-20).

Since the owner's method change (20 Nov) a UMS letter locks only when it shows ALL the owner's words
(`offer_owner_words`). These older checks stay as an EXTRA layer, because refusing more is always safe:

* a status letter ("SURAT PENGESAHAN") never locks;
* a withdrawal, deferral, refusal or reply word (`_NOT_AN_OFFER` at or above the title; `_WITHDRAWN`, spaced
  or squeezed, anywhere) refuses ('not_an_offer');
* TERBATAL / TARIK BALIK said of the letter refuses (`_cancel_said`). "akan terbatal" and "terbatal dengan
  sendirinya" are excused ONLY in a sentence that holds SEKIRANYA / JIKA / JIKALAU / APABILA, and never right
  after "telah", nor after "Status" or a colon earlier in that sentence (round 3 blocker 1);
* a page after page 1 that shows a second offer refuses ('second_offer', round 3 MED 3, `later_pages_refusal`);
* a digital letter with no page texts, or with one of its first 3 pages showing no visible text, refuses
  ('no_page_texts' / 'hidden_page', round 3 MED 4, `page_texts_refusal`): the owner's words are matched on
  the visible pages, so a page we cannot see sends the letter to the AI.

Every lookup is linear in the text (round 3 MED 5: the excused spans are found by one bisect each). Pure.
"""
from __future__ import annotations

import bisect
import re

_STATUS = re.compile(r'SURAT\s{1,3}PENGESAHAN', re.IGNORECASE)
#: A letter that withdraws, defers, refuses or answers an offer (review round 1): any of these words in the head
#: or the title line means it is not the offer itself. TERBATAL / TIDAK BERJAYA (S1c): see `_CANCEL_WORD`.
_NOT_AN_OFFER = re.compile(r'\b(?:PEMBATALAN|PENANGGUHAN|PENOLAKAN|TARIK\s{1,3}BALIK|RAYUAN|MAKLUM\s{0,3}BALAS|'
                           r'TERBATAL|TIDAK\s{1,3}BERJAYA)\b', re.IGNORECASE)
#: A withdrawal said in the body ("Tawaran ini adalah DIBATALKAN", "telah DITARIK BALIK"), word-bounded: never
#: an offer to lock. Added by S1c (DITOLAK, DITARIK SEMULA, TIDAK LAGI SAH, SURAT TIDAK BERJAYA), its round 1
#: (TIDAK SAH, DIGUGURKAN, DIMANSUHKAN, LUPUT, GAGAL) and round 2 (DITAMATKAN ... DITARIK). Measured: no cached
#: UMS letter prints any of them on ANY page (their conditional clause says "Kegagalan", "terbatal").
_WITHDRAWN = re.compile(r'\b(?:(?:DI\s{0,3})?BATAL(?:KAN)?|PEMBATALAN|DI\s{0,3}TARIK\s{1,3}(?:BALIK|SEMULA)|'
                        r'DI\s{0,3}TOLAK|TIDAK\s{1,3}LAGI\s{1,3}SAH|SURAT\s{1,3}TIDAK\s{1,3}BERJAYA|TIDAK\s{1,3}SAH|'
                        r'DIGUGURKAN|DIMANSUHKAN|LUPUT|GAGAL|'
                        r'DITAMATKAN|PENAMATAN|TIDAK\s{1,3}(?:LAGI\s{1,3})?BERKUAT\s{0,3}KUASA|WITHDRAWN|CANCELL?ED|'
                        r'REVOKED|TIDAK\s{1,3}AKTIF|TIDAK\s{1,3}TERPAKAI|DITARIK)\b', re.IGNORECASE)
#: The same words with spaces, dots and dashes taken out ("D I B A T A L K A N", "TIDAK  .  BERJAYA"; S1c
#: round 1). Measured: none is in the squeezed text of ANY page of the 58 cached UMS letters. A bare DITARIK is
#: never a stem: squeezed, "DI TARIKH" holds it.
_WITHDRAWN_STEMS = ('DIBATALKAN', 'PEMBATALAN', 'TIDAKBERJAYA', 'DITARIKBALIK', 'DITARIKSEMULA', 'PENARIKANBALIK',
                    'TIDAKLAGISAH', 'DITAMATKAN', 'TIDAKBERKUATKUASA', 'TIDAKLAGIBERKUATKUASA', 'WITHDRAWN',
                    'CANCELLED', 'CANCELED', 'REVOKED', 'TIDAKAKTIF', 'TIDAKTERPAKAI')
_SQUEEZE_OUT = re.compile(r'[\s.\-–—]')
#: TERBATAL or TARIK BALIK SAID of this letter ("Status : TERBATAL", "adalah TERBATAL dan ..."; S1c rounds 1-2).
#: A clause ends at a line break, ';', ':' or '.'; a bare word escapes only when SEKIRANYA / JIKA / JIKALAU /
#: APABILA comes BEFORE it in its clause. "akan terbatal" / "terbatal dengan sendirinya": see `_excused`.
_CANCEL_WORD = re.compile(r'\bTERBATAL\b|\b(?:MENARIK|DITARIK|TARIK)\s{0,3}BALIK\b', re.IGNORECASE)
_CONDITION = re.compile(r'\b(?:SEKIRANYA|JIKA|JIKALAU|APABILA)\b', re.IGNORECASE)
_CONDITIONAL_CANCEL = re.compile(r'\bAKAN\s{1,3}TERBATAL\b|\bTERBATAL\s{1,3}DENGAN\s{1,3}SENDIRINYA\b', re.IGNORECASE)
_CLAUSE_END = re.compile(r'[\n;:.]')
#: A sentence ends at '.', ';', '!' or '?' — a line break does not end it (a letter wraps its sentences).
_SENTENCE_END = re.compile(r'[.;!?]')
_TELAH_BEFORE = re.compile(r'\bTELAH\s{1,3}$', re.IGNORECASE)
_STATUS_WORD = re.compile(r'\bSTATUS\b', re.IGNORECASE)
_CLAUSE_COLON = re.compile(r'[:：]')
#: The ONE space between two single letters ("D I B A T A L K A N" -> "DIBATALKAN"; "D I BATALKAN" -> "DI
#: BATALKAN"); a wider gap is the gap between two spaced words ("S U R A T  T I D A K" -> "SURAT  TIDAK").
_LETTER_GAP = re.compile(r'(?<![A-Za-z])([A-Za-z])[^\S\n](?=[A-Za-z](?![A-Za-z]))')
#: Round 3 MED 3: a second offer title on a later page (any "TAWARAN KEMASUKAN", the university named or not).
_OFFER_TITLE = re.compile(r'TAWARAN\s{1,3}KEMASUKAN', re.IGNORECASE)
#: The template's own page 2 heading "SYARAT-SYARAT TAWARAN KEMASUKAN SESI ..." (conditions of the offer, on every
#: genuine two-page UMS letter, 20 Nov measure) is not a second offer's title; its IC, sentence and date still judge.
_CONDITIONS_HEADING = re.compile(r'SYARAT\s{0,3}-?\s{0,3}SYARAT\s{1,3}TAWARAN\s{1,3}KEMASUKAN', re.IGNORECASE)


def _squeeze(s: str) -> str:
    """Spaced letters joined ("D I B A T A L K A N" -> "DIBATALKAN"), for the withdrawal words (S1c)."""
    return _LETTER_GAP.sub(r'\1', s or '')


def _excused(text: str, m) -> bool:
    """True when the "akan terbatal" / "terbatal dengan sendirinya" at ``m`` is a CONDITION (round 3 blocker 1):
    SEKIRANYA / JIKA / JIKALAU / APABILA in the same sentence (before or after it: "akan terbatal sekiranya ...");
    and never straight after "telah", nor after "Status" or a colon earlier in its sentence."""
    before = _SENTENCE_END.split(text[max(0, m.start() - 300):m.start()])[-1]
    after = _SENTENCE_END.split(text[m.end():m.end() + 300])[0]
    line = before.rsplit('\n', 1)[-1]                       # the phrase's own line, up to it
    if (_TELAH_BEFORE.search(before) or before.rstrip().endswith((':', '：')) or _CLAUSE_COLON.search(line)
            or _STATUS_WORD.search(line)):
        return False                                       # "telah terbatal ...", "Status :\nakan terbatal"
    cond = None
    for cond in _CONDITION.finditer(before):
        pass
    between = before[cond.end():] if cond is not None else ':'
    if not (_CLAUSE_COLON.search(between) or _STATUS_WORD.search(between)):
        return True                                       # "Sekiranya ..., tawaran ini akan terbatal"
    return bool(_CONDITION.search(after))                  # "Tawaran ini akan terbatal sekiranya ..."


def _cancel_said(text: str) -> bool:
    """True when TERBATAL or TARIK BALIK is said of the letter, not as a condition (`_CANCEL_WORD`, `_excused`)."""
    cond = [(m.start(), m.end(), _excused(text, m)) for m in _CONDITIONAL_CANCEL.finditer(text)]
    starts = [a for a, _b, _ok in cond]
    for m in _CANCEL_WORD.finditer(text):
        i = bisect.bisect_right(starts, m.start()) - 1
        if i >= 0 and cond[i][0] <= m.start() and m.end() <= cond[i][1]:
            if cond[i][2]:
                continue
            return True                          # "telah terbatal dengan sendirinya", "Status : akan terbatal"
        clause = _CLAUSE_END.split(text[max(0, m.start() - 300):m.start()])[-1]
        if not _CONDITION.search(clause):
            return True
    return False


def _withdrawn(source: str, head) -> bool:
    """True when the letter withdraws, defers, refuses or answers an offer rather than making one: a head word
    at or above the title, a withdrawal word anywhere (also with its letters spaced, or squeezed of spaces, dots
    and dashes), or TERBATAL / TARIK BALIK said with no condition (`_cancel_said`)."""
    key = _SQUEEZE_OUT.sub('', source.upper())
    squeezed = _squeeze(source)
    return bool(any(_NOT_AN_OFFER.search(ln) or _NOT_AN_OFFER.search(_squeeze(ln)) for ln in head)
                or _WITHDRAWN.search(source) or _WITHDRAWN.search(squeezed)
                or any(stem in key for stem in _WITHDRAWN_STEMS)
                or _cancel_said(source) or _cancel_said(squeezed))


def letter_refusal(text: str) -> str:
    """Why a digital letter's FULL text (every page) refuses its page-1 layout read's lock (S1c round 2):
    'status_letter' ("SURAT PENGESAHAN" anywhere), 'not_an_offer' (`_withdrawn` on any page; head words only
    above the title line), 'too_long' (past ``MAX_LETTER_CHARS``); '' when none."""
    from .offer_parse_university import _TITLE, MAX_LETTER_CHARS, _one_space, _text_lines
    text = text or ''
    if len(text) > MAX_LETTER_CHARS:
        return 'too_long'
    if _STATUS.search(text):
        return 'status_letter'
    lines = _text_lines(text)
    title_at = next((i for i, ln in enumerate(lines) if _TITLE.search(_one_space(ln))), -1)
    return 'not_an_offer' if _withdrawn(text, lines[:title_at + 1] if title_at >= 0 else []) else ''


#: Round 3 MED 4: the first pages whose visible text must not be empty (a hidden or scanned page there may hold
#: the withdrawal, the status or a second offer the rules cannot see).
CHECKED_PAGES = 3


def page_texts_refusal(page_texts) -> str:
    """Why a DIGITAL letter's page texts (`pdf_pages.pdf_page_texts`, one visible text per page) refuse its lock:
    'no_page_texts' when there are none; 'hidden_page' when any of its first `CHECKED_PAGES` pages is empty (a
    page whose text is invisible or cannot be checked reads ''; a one-page letter's page 1 is never empty here,
    its layout needs it); '' when every one of them shows text."""
    pages = list(page_texts or ())
    if not pages:
        return 'no_page_texts'
    return 'hidden_page' if any(not (t or '').strip() for t in pages[:CHECKED_PAGES]) else ''


def later_pages_refusal(later_pages, nric: str, reporting_date: str) -> str:
    """'second_offer' when any page after page 1 (``later_pages``, each page's visible text) shows a second offer
    (round 3 MED 3): a "TAWARAN KEMASUKAN" title (not the template's "SYARAT-SYARAT TAWARAN KEMASUKAN"), a programme sentence ("untuk mendapat ... dan sebanyak"), an
    IC other than page 1's ``nric``, or a date by a "Tarikh Lapor Diri" label (its line and the six after it)
    other than page 1's ``reporting_date``; '' when none. A confirmation page that repeats them refuses too."""
    from .offer_parse import _decimal_digits, first_date, house_date
    from .offer_parse_university import _IC_RE, _REPORT_LABEL, _SENTENCE, _text_lines
    want = _decimal_digits(nric or '')
    for page in later_pages or ():
        page = page or ''
        if _OFFER_TITLE.search(_CONDITIONS_HEADING.sub(' ', page)) or _SENTENCE.search(page):
            return 'second_offer'
        if any(_decimal_digits(m.group(1)) != want for m in _IC_RE.finditer(page)):
            return 'second_offer'
        lines = _text_lines(page)
        for i, ln in enumerate(lines):
            if not _REPORT_LABEL.search(ln):
                continue
            window = [_REPORT_LABEL.split(ln, maxsplit=1)[1]] + lines[i + 1:i + 7]
            if any(got and house_date(got) != reporting_date for got in map(first_date, window)):
                return 'second_offer'
    return ''
