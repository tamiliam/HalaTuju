"""Help H2 review 7 (lead's rule, 2026-11-15): what keeps a NEWLY covered confirmation of studies out, and the
campus line under its name. Split from `offer_rulings` (the 600-line limit, `test_code_standards.py`);
`offer_rulings` imports the four it calls. Pure.

Every suspect is checked by a person, so a wrong block of a real student's letter hurts more than a non-study
letter reaching a person: only a CLEAR phrase in a sentence that is no condition blocks (`not_studying`), and a
hostel / internship / staff word blocks only on the letter's subject (`non_study_subject`).
"""
import re

from .offer_confirmations import (_CONDITIONAL, _CONFIRM_TITLES_EN, _CONFIRM_TITLES_EN_GENERIC,
                                  _NOT_STUDIES_SUBJECT, _NOT_STUDYING, _OFFER_UNDONE, _SUBJECT_STARTS)
from .offer_reading import (_COMPANY_HEAD, _CONFIRM_TITLES, _ORG_RE, _PRIVATE_BODIES, _SB, _letterhead_region,
                            normalise_s6)

#: "was formerly" - but never "the college, formerly known as ..." (that names the issuer, not the person).
_WAS_FORMERLY = re.compile(r' WAS FORMERLY (?!KNOWN )')


def _clauses(lines, ocr_text=''):
    """The page's sentences, folded: the raw text split at . ! ? ; (a sentence may run over lines), or each
    folded line when there is no raw text."""
    if not ocr_text:
        return list(lines)
    from .results_doc import _norm_fold_upper_alnum
    out = []
    for part in re.split(r'[.!?;]', normalise_s6(ocr_text)):
        f = _norm_fold_upper_alnum(part)
        if f:
            out.append(f' {f} ')
    return out


def _says(lines, ocr_text, phrases, pattern=None) -> bool:
    """A sentence holding one of `phrases` (or `pattern`) that is no condition or footnote (`_CONDITIONAL`)."""
    for c in _clauses(lines, ocr_text):
        if any(w in c for w in _CONDITIONAL):
            continue                    # "terbatal sekiranya ...", "void if ..." never blocks
        if any(w in c for w in phrases) or (pattern is not None and pattern.search(c)):
            return True
    return False


def _not_studying(lines, ocr_text='') -> bool:
    """A sentence CLEARLY saying the person finished, was refused, was dismissed or had the offer withdrawn
    (`_NOT_STUDYING`, `_OFFER_UNDONE`, `_WAS_FORMERLY`). Bare words ("TAMAT", "COMPLETED", "ALUMNI", "STAFF")
    and the end date's label ("Tarikh Mula dan Tamat Pengajian") never block: they read suspect."""
    return (_says(lines, ocr_text, _NOT_STUDYING, _OFFER_UNDONE)
            or _says(lines, ocr_text, (), _WAS_FORMERLY))


def _non_study_subject(lines) -> bool:
    """A hostel / internship / staff / convocation / interview word (`_NOT_STUDIES_SUBJECT`) on the letter's
    SUBJECT - a PERKARA / RE / SUBJECT / "Per:" line, or the title line (a long line: 4 words before the title to
    14 after). In the body these words never block."""
    titles = _CONFIRM_TITLES + _CONFIRM_TITLES_EN + _CONFIRM_TITLES_EN_GENERIC
    for ln in lines:
        words = ln.split()
        if ln.startswith(_SUBJECT_STARTS):
            seg = words[:16]
        else:
            at = [ln.find(t) for t in titles if t in ln]
            if not at:
                continue
            if len(words) <= 15:
                seg = words
            else:
                before = ln[:min(at)].split()
                seg = before[-4:] + ln[min(at):].split()[:14]
        if any(w in f" {' '.join(seg)} " for w in _NOT_STUDIES_SUBJECT):
            return True
    return False


def _campus_line(ln) -> str:
    """"KAMPUS GOPENG" under "KOLEJ MATRIKULASI PERAK": 'own' for KAMPUS / CAMPUS and 1-5 more words with no
    organisation noun, company sign or private word (the old drop restored: "KAMPUS MERCU PRESTIGE" is dropped
    too and reads suspect - a person checks); 'other' for a campus line that holds one ("KAMPUS MERCU COLLEGE",
    "CAMPUS MERCU PRIVATE", "... SDN BHD": a fail); '' for no campus line."""
    words = ln.split()
    if not (2 <= len(words) <= 6 and words[0] in ('KAMPUS', 'CAMPUS')):
        return ''
    rest = f" {' '.join(words[1:])} "
    if (_ORG_RE.search(rest) or _SB.search(rest) or any(c in rest for c in _COMPANY_HEAD)
            or any(b in rest for b in _PRIVATE_BODIES) or ' PRIVATE ' in rest or ' SWASTA ' in rest):
        return 'other'
    return 'own'


def _campus_dropped(lines, names):
    """`lines` without a campus line (`_campus_line`) straight under a letterhead line naming one of `names`: the
    college's own campus, not another organisation (the KAMPUS noun had made it no confirmation at all). None
    when such a line names an organisation or a private body (no confirmation)."""
    head_n = len(_letterhead_region(lines))
    out = []
    for i, ln in enumerate(lines):
        kind = _campus_line(ln) if 0 < i < head_n and any(n in lines[i - 1] for n in names) else ''
        if kind == 'other':
            return None
        if kind != 'own':
            out.append(ln)
    return out
