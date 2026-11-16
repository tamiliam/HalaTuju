"""Help H2: what a confirmation of studies is read on - its TITLE BLOCK only - and the campus line under its name.
Split from `offer_rulings` (the 600-line limit, `test_code_standards.py`); `offer_rulings` imports what it calls.
Pure.

Lead's decision, 16 Nov 2026 (H2 review 8 failed again on body-word blocks): no body word ever blocks a
confirmation. Every confirmation reads suspect at best and a person checks it, so a non-study letter that reaches
suspect is accepted (decisions.md ruling 4). Only the title block is read for the confirmation reading: the generic
title's study word (`generic_titled`) and the letter's subject (`non_study_subject`). The CAP (`cap_confirmation`)
reads the WHOLE page as well, as main's `_confirm_titled` does (`page_titled`; H2 review 9).
"""
import re

from .offer_confirmations import (_BODY_CUTS, _BODY_STARTS, _CONFIRM_TITLES_EN, _CONFIRM_TITLES_EN_GENERIC,
                                  _INTERNSHIP, _MATRIC_EN_TITLES, _NOT_STUDIES_SUBJECT, _STUDY_WORDS, _SUBJECT_STARTS,
                                  CONFIRM_MIN, CONFIRMATION_SEEN, MATRIC_OFFER_EN)
from .offer_reading import (_COMPANY_HEAD, _CONFIRM_TITLES, _CONFIRM_TOP_CHARS, _IC, _ORG_RE, _PERSON_LABELS,
                            _PRIVATE_BODIES, _SB, _TAG, _TITLE, _letterhead_region, _page, _ruled_status)

_SPECIFIC = _CONFIRM_TITLES + _CONFIRM_TITLES_EN
_ALL_TITLES = _SPECIFIC + _CONFIRM_TITLES_EN_GENERIC
#: H2 review 10: an admission decision's own titles (an offer title line, `offer_title_line`).
_OFFER_TITLES = (' KEPUTUSAN PERMOHONAN ', ' KEMASUKAN KE PROGRAM ')
#: The words a title line may start with before the confirmation title ("SURAT PENGESAHAN PELAJAR", "PERKARA:").
_TITLE_PREFIXES = ('SURAT',) + tuple(s.strip() for s in _SUBJECT_STARTS)
#: A glued body after the title ("PENGESAHAN PELAJAR DENGAN HORMATNYA ..."): the title stops there.
_GLUED_BODY = (' DENGAN HORMATNYA ', ' DENGAN SEGALA HORMATNYA ', ' TUAN PUAN ', ' DENGAN INI DISAHKAN ',
               ' ADALAH DISAHKAN ', ' THIS IS TO CERTIFY ', ' THIS IS TO CONFIRM ')
#: A title's own words after the confirmation title: the issuer, a session, "(LATIHAN INDUSTRI)" - a few words.
_TITLE_REST_MAX = 8
#: ... and never a sentence's verbs / joining words ("... akan dikeluarkan selepas pendaftaran", "... will be
#: issued after registration").
_SENTENCE = re.compile(r' (?:AKAN|TELAH|HENDAKLAH|PERLU|WAJIB|BOLEH|DAPAT|SELEPAS|SEBELUM|JIKA|SEKIRANYA|APABILA|'
                       r'BAHAWA|INI|ADALAH|IALAH|DI[A-Z]{3,}KAN|WILL|SHALL|MUST|SHOULD|CAN|IS|ARE|WAS|BE|BEEN|HAS|'
                       r'HAVE|ISSUED|AFTER|BEFORE|UPON|WITHIN|IF|PLEASE|THAT|THIS)(?= )')


def _body_line(ln) -> bool:
    """The first body sentence ("Dengan hormatnya ...", "2. Adalah disahkan ...", "This is to confirm ...")."""
    words = ln.split()
    while words and words[0].isdigit():
        words = words[1:]                # a paragraph number
    return f" {' '.join(words)} ".startswith(_BODY_STARTS)


def _cut(seg: str) -> str:
    """`seg` up to the first body word, person label or IC number (a glued line), at most 14 words."""
    cuts = [seg.find(w) for w in _BODY_CUTS + _PERSON_LABELS if w in seg] + [m.start() for m in _IC.finditer(seg)]
    seg = seg[:min(cuts)] if cuts else seg
    return f" {' '.join(seg.split()[:14])} "


def title_block(lines):
    """[(kind, segment, next_line)] of the title block: the lines above the first body sentence and the first
    offer title line (`offer_title_line`), in the first half of the page (review 10: no character floor, so a
    short letter's whole page is never its title block). kind 'title' for a line holding a confirmation title (4
    words before it, then the title onward, `_cut`), 'subject' for a PERKARA / RE / SUBJECT line (`_cut`).
    `next_line` is the following line when it is short (6 words or fewer)."""
    top = sum(len(ln) for ln in lines) // 2
    out, at = [], 0
    for i, ln in enumerate(lines):
        if at > top or _body_line(ln) or offer_title_line(ln):
            break
        at += len(ln)
        nxt = lines[i + 1] if i + 1 < len(lines) and len(lines[i + 1].split()) <= 6 else ''
        if nxt and _body_line(nxt):
            nxt = ''
        if ln.startswith(_SUBJECT_STARTS) and not ln.startswith(' PERKARA DI ATAS '):
            out.append(('subject', _cut(ln), nxt))
            continue
        found = [ln.find(t) for t in _ALL_TITLES if t in ln]
        if found:
            first = min(found)
            out.append(('title', ' '.join(ln[:first].split()[-4:]) + _cut(ln[first:]), nxt))
    return out


def generic_titled(lines) -> bool:
    """A generic title ("CONFIRMATION LETTER") with a study word in its own segment, the short line under it, or
    a subject line of the title block (lead, 16 Nov 2026)."""
    block = title_block(lines)
    study = any(w in seg + f' {nxt} ' for _k, seg, nxt in block for w in _STUDY_WORDS
                if _k == 'subject' or any(t in seg for t in _CONFIRM_TITLES_EN_GENERIC))
    return study and any(t in seg for _k, seg, _n in block for t in _CONFIRM_TITLES_EN_GENERIC)


def non_study_subject(lines) -> bool:
    """The title block's title / subject segment is a hostel, staff / employment, study-leave, convocation or
    interview matter, or an internship with no study word in the same segment ("PERKARA: LATIHAN INDUSTRI";
    "PENGESAHAN PELAJAR (LATIHAN INDUSTRI)" is a student's own confirmation). A body word never counts."""
    for _k, seg, _n in title_block(lines):
        if any(w in seg for w in _NOT_STUDIES_SUBJECT):
            return True
        if any(w in seg for w in _INTERNSHIP) and not any(w in seg for w in _STUDY_WORDS):
            return True
    return False


#: The CAP's confirmation code for a family / institute code: never a course pick (`CONFIRMATION_SEEN`).
_CAP_SEEN = {'matriculation': 'confirmation_matriculation', 'polytechnic': 'confirmation_polytechnic',
             'pismp': 'confirmation_ipg', 'stpm': 'confirmation_form6'}


def offer_title_line(ln) -> bool:
    """H2 review 10: an offer's title line - TAWARAN (also OCR-glued: "SURATTAWARAN") / OFFER, or the admission
    decision's own title (KEPUTUSAN PERMOHONAN, KEMASUKAN KE PROGRAM). "DITAWARKAN" holds no TAWARAN."""
    return (any('TAWARAN' in w for w in ln.split()) or any(t in ln for t in _TITLE + _OFFER_TITLES))


def _title_line(ln, titles) -> bool:
    """`ln` IS a confirmation title (lead, 16 Nov 2026: a title is a LINE, not a phrase in a sentence): after an
    optional SURAT / PERKARA / RE it starts with one of `titles`, and the rest up to a person label / IC number (a
    glued name line) is short and no sentence (`_SENTENCE`: "... akan dikeluarkan selepas pendaftaran")."""
    words = ln.split()
    while words and words[0] in _TITLE_PREFIXES:
        words = words[1:]
    ln = f" {' '.join(words)} "
    t = next((t for t in titles if ln.startswith(t)), None)
    if t is None:
        return False
    rest = ln[len(t) - 1:]
    cuts = [rest.find(w) for w in _PERSON_LABELS + _GLUED_BODY if w in rest] + [m.start() for m in _IC.finditer(rest)]
    rest = rest[:min(cuts)] if cuts else rest
    return len(rest.split()) <= _TITLE_REST_MAX and not _SENTENCE.search(rest)


def page_titled(lines, probability: float = 1.0) -> bool:
    """H2 review 10: the page's confirmation TITLE LINE (`_title_line`), as main's `_confirm_titled` places it - in
    the top half (or first `_CONFIRM_TOP_CHARS` characters), above the first offer title line
    (`offer_title_line`), at or above main's score floor (`CONFIRM_MIN`). Two short lines join (a title split over
    two lines); an English title counts as the Malay one, a generic one only with a study word in its title block
    (`generic_titled`). Every line above the title is read past (an addressee, "Tuan/Puan,", "Kami ...": review 9).
    The recognition path passes the family score (main's floor); the CAP does not (a lift is genuine at 0.0).
    A confirmation phrase inside a body sentence is never a title line, so it never caps (decisions.md ruling 4)."""
    if probability < CONFIRM_MIN:
        return False
    titles = _CONFIRM_TITLES + _CONFIRM_TITLES_EN + (_CONFIRM_TITLES_EN_GENERIC if generic_titled(lines) else ())
    top, at = max(_CONFIRM_TOP_CHARS, len(_page(lines)) // 2), 0
    for i, ln in enumerate(lines):
        if at > top or offer_title_line(ln):
            return False
        nxt = lines[i + 1] if i + 1 < len(lines) else ''
        pair = (len(ln.split()) <= 6 and nxt and len(nxt.split()) <= 6 and not offer_title_line(nxt))
        if _title_line(ln, titles) or (pair and _title_line(f' {ln.strip()} {nxt.strip()} ', titles)):
            return True
        at += len(ln.strip()) + 1
    return False


def _matric_en_page(lines) -> bool:
    """KPM's English matriculation offer on the page: the Division, the ministry and an English matric title."""
    page = _page(lines)
    return (' MATRICULATION DIVISION ' in page and ' MINISTRY OF EDUCATION ' in page
            and any(t in page for t in _MATRIC_EN_TITLES))


def cap_confirmation(lines, result, r, model_version):
    """Gate (d), the CAP (lead, 16 Nov 2026), run last: a page with a confirmation TITLE LINE (`page_titled`;
    review 10: never a phrase in a body sentence) reads SUSPECT at best, whatever ruled it genuine (a TVET /
    agency lift, a genuine baseline such as `ua_offer`). Review 9: a suspect one keeps its status but takes the
    confirmation code (H2), so it never writes a course pick (`pathway_engine.is_confirmation_letter`); a
    `not_offer_letter` is left as it is. An English matriculation offer the family read as `matriculation` takes
    `MATRIC_OFFER_EN`, suspect at best (M1). Review 10 (L): a GENUINE result with a confirmation code reads
    suspect whatever ruled it, title or none."""
    status, seen = result.get('status'), result.get('type') or ''
    if status not in ('genuine', 'suspect'):
        return result
    if seen in CONFIRMATION_SEEN:
        if status == 'suspect':
            return result
        return _ruled_status('suspect', r, seen, 'matric_offer_en' if seen == MATRIC_OFFER_EN else
                             'confirmation_ua' if seen == 'confirmation_ua' else 'confirmation_check',
                             'a confirmation of studies - a person checks; never genuine by itself (owner ruling 4, '
                             '16 Nov 2026)', model_version)
    if seen == 'matriculation' and _matric_en_page(lines):
        return _ruled_status('suspect', r, MATRIC_OFFER_EN, 'matric_offer_en', "KPM's English matriculation offer - "
                             'a person checks; never genuine by itself and never a course pick (help H2 option B)',
                             model_version)
    if not page_titled(lines):         # no score floor here: a TVET lift reads genuine at a 0.0 family score
        return result
    seen = _CAP_SEEN.get(seen) or ('confirmation_tvet' if seen.startswith('tvet') else 'confirmation_ua')
    tag = 'confirmation_ua' if seen == 'confirmation_ua' else 'confirmation_check'
    why = ('a confirmation of studies (its title) - a person checks; never genuine by itself (owner ruling 4, '
           '16 Nov 2026)')
    if status == 'suspect':                 # review 9 (H2): the status stays; only the code changes
        return {**result, 'type': seen, 'reason': (_TAG.format(tag) + why + '; ' + (result.get('reason') or ''))[:300]}
    return _ruled_status('suspect', r, seen, tag, why, model_version)


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
