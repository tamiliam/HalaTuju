"""The UMS letter's refusal checks — split out of `offer_parse_university` (S1c owner words, 2026-11-20).

Since the owner's method change (20 Nov) a UMS letter locks only when it shows ALL the owner's words
(`offer_owner_words`). These older checks stay as an EXTRA layer, because refusing more is always safe:

* a status letter ("SURAT PENGESAHAN") never locks;
* a withdrawal, deferral, refusal or reply word (`_NOT_AN_OFFER` at or above the title; `_WITHDRAWN`, spaced
  or squeezed, anywhere) refuses ('not_an_offer');
* TERBATAL / TARIK BALIK said of the letter refuses (`_cancel_said`). "akan terbatal" and "terbatal dengan
  sendirinya" are excused ONLY in a sentence that holds SEKIRANYA / JIKA / JIKALAU / APABILA, and never right
  after "telah", nor after "Status" or a colon earlier in that sentence (round 3 blocker 1);
* a page after page 1 that shows a second offer refuses ('second_offer', round 3 MED 3, `later_pages_refusal`;
  owner words review round 1: any spacing, another session, programme code or label value, a reporting date
  however its label or day is printed);
* a digital letter with no page texts, more than `MAX_PAGES` pages, or one of its first 3 pages showing no
  drawn text, refuses ('no_page_texts' / 'too_many_pages' / 'hidden_page', round 3 MED 4 and review round 1,
  `page_texts_refusal`): the owner's words are matched on drawn text (render-mode visible; colour, size,
  covering and off-page placement are not checked yet), so a page we cannot see sends the letter to the AI.

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
#: Round 3 MED 3, matched on a later page's KEY (`_page_key`: every character that is not a letter or digit taken
#: out), so any spacing, a line break, an indent, glued or spaced letters all match (owner words review round 1).
#: A second offer's title (any "TAWARAN KEMASUKAN"), its programme sentence ("untuk mendapat" / "untuk
#: mengikuti") or its "telah ditawarkan tempat". Measured 20 Nov: none of them is on any genuine page 2 outside
#: the heading below; a bare "ditawarkan" is on all 36, so it is not a refusal word.
_OFFER_KEYS = ('TAWARANKEMASUKAN', 'UNTUKMENDAPAT', 'UNTUKMENGIKUTI', 'TELAHDITAWARKANTEMPAT')
#: The template's own page 2 heading "SYARAT-SYARAT TAWARAN KEMASUKAN SESI 2031/2032" (on all 36 genuine
#: two-page UMS letters, no programme code, no "Program :" label beside it) is skipped ONLY with a session whose
#: years are page 1's (and its series, "I-", when it prints one): another session is a second offer.
_HEADING_KEY = re.compile(r'SYARATSYARATTAWARANKEMASUKAN(?:KEUNIVERSITIMALAYSIASABAH)?SESI([0-9IV]{0,3}?)(20\d{2})(20\d{2})')
_SESSION_KEY = re.compile(r'SESI([0-9IV]{0,3}?)(20\d{2})(20\d{2})')
_UPU_KEY = re.compile(r'U[A-Z]\d{7}')
#: A later page's "Program :" / "Kod Program :" label (any spacing, glued or not) and its value.
_PROGRAM_LABEL = re.compile(r'(?<![^\W_])(KOD\s{0,40})?PROGRAM\s{0,40}[:：;]\s{0,40}(.*)$', re.IGNORECASE)
#: The reporting-date label, also split over lines or spaced ("Tarikh\nLapor\nDiri"); its key form counts too.
_REPORT_ANY = re.compile(r'Tarikh[\W_]{1,40}Lapor[\W_]{1,40}Diri', re.IGNORECASE)
#: "5hb Oktober 2031", "5 hb. Oktober": the day's "hb" taken out before the date is read.
_HB = re.compile(r'(?<!\d)(\d{1,2})\s{0,3}HB\b\.?', re.IGNORECASE)


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


#: Round 3 MED 4: the first pages whose drawn text must not be empty (a hidden or scanned page there may hold
#: the withdrawal, the status or a second offer the rules cannot see).
CHECKED_PAGES = 3
#: Owner words review round 1 (LOW 3): a UMS letter with more pages than this never locks, so no page the
#: checks do not read can carry a second offer. All 36 genuine digital UMS letters have exactly 2 pages.
MAX_PAGES = 3


def page_texts_refusal(page_texts) -> str:
    """Why a DIGITAL letter's page texts (`pdf_pages.pdf_page_texts`, one drawn text per page) refuse its lock:
    'no_page_texts' when there are none; 'too_many_pages' past `MAX_PAGES`; 'hidden_page' when any of its first
    `CHECKED_PAGES` pages is empty (a page whose text is not drawn or cannot be checked reads ''; a one-page
    letter's page 1 is never empty here, its layout needs it); '' when every one of them shows text."""
    pages = list(page_texts or ())
    if not pages:
        return 'no_page_texts'
    if len(pages) > MAX_PAGES:
        return 'too_many_pages'
    return 'hidden_page' if any(not (t or '').strip() for t in pages[:CHECKED_PAGES]) else ''


def _page_key(s: str) -> str:
    """``s`` upper-cased and accent-folded with every character that is not a letter or digit taken out."""
    from .offer_owner_words import _norm
    return _norm(s).replace(' ', '')


def _other_session(key: str, intake: str) -> bool:
    """True when a later page's conditions heading names a session other than page 1's ``intake``."""
    want = _SESSION_KEY.search(_page_key(intake))
    for m in _HEADING_KEY.finditer(key):
        if want is None or m.group(2, 3) != want.group(2, 3) or (m.group(1) and m.group(1) != want.group(1)):
            return True
    return False


def _other_programme(page: str, code: str, programme: str) -> bool:
    """True when a later page prints a programme code (UH...) or a "Program :" / "Kod Program :" value other
    than page 1's ``code`` / ``programme`` (letters and digits compared)."""
    from .offer_parse_university import _text_lines
    if set(_UPU_KEY.findall(_page_key(page))) - {_page_key(code)}:
        return True
    for ln in _text_lines(page):
        m = _PROGRAM_LABEL.search(ln)
        if m and _page_key(m.group(2)) != _page_key(code if m.group(1) is not None else programme):
            return True
    return False


def _other_date(page: str, reporting_date: str) -> bool:
    """True when a later page's "Tarikh Lapor Diri" (any spacing, also over lines) is followed, on its own line
    or the six after it, by a date other than page 1's ``reporting_date`` ("5hb Oktober 2031" read as a date),
    or when the label's letters show (spaced, glued) more often than the label itself can be read."""
    from .offer_parse import first_date, house_date
    from .offer_parse_university import _text_lines
    found = list(_REPORT_ANY.finditer(page))
    if _page_key(page).count('TARIKHLAPORDIRI') != len(found):
        return True
    for m in found:
        window = _text_lines(page[m.end():])[:7]
        if any(got and house_date(got) != reporting_date for got in (first_date(_HB.sub(r'\1', w)) for w in window)):
            return True
    return False


def later_pages_refusal(later_pages, nric: str, reporting_date: str, intake: str = '', code: str = '',
                        programme: str = '') -> str:
    """'second_offer' when any page after page 1 (``later_pages``, each page's drawn text) shows a second offer
    (round 3 MED 3; owner words review round 1): an offer title, programme sentence or "telah ditawarkan tempat"
    in any spacing (`_OFFER_KEYS`; the template's conditions heading skipped only with page 1's session), a
    programme code or programme label value other than page 1's, an IC other than page 1's ``nric``, or a
    reporting date other than page 1's; '' when none. A confirmation page that repeats them refuses too."""
    from .offer_parse import _decimal_digits
    from .offer_parse_university import _IC_RE, _SENTENCE
    want = _decimal_digits(nric or '')
    for page in later_pages or ():
        page = page or ''
        key = _page_key(page)
        if (page.strip() and not key) or _other_session(key, intake):   # no letter or digit, or too long unpacked
            return 'second_offer'
        rest = _HEADING_KEY.sub('', key)
        if any(k in rest for k in _OFFER_KEYS) or _SENTENCE.search(page):
            return 'second_offer'
        if any(_decimal_digits(m.group(1)) != want for m in _IC_RE.finditer(page)):
            return 'second_offer'
        if _other_programme(page, code, programme) or _other_date(page, reporting_date):
            return 'second_offer'
    return ''
