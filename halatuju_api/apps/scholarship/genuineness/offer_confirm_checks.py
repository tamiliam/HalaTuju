"""Help H2: what a confirmation of studies is read on - its TITLE BLOCK only - and the campus line under its name.
Split from `offer_rulings` (the 600-line limit, `test_code_standards.py`); `offer_rulings` imports what it calls.
Pure.

Lead's decision, 16 Nov 2026 (H2 review 8 failed again on body-word blocks): no body word ever blocks a
confirmation. Every confirmation reads suspect at best and a person checks it, so a non-study letter that reaches
suspect is accepted (decisions.md ruling 4). Only the title block is read: the confirmation title (`titled`, and the
CAP, `cap_confirmation`) and the letter's subject (`non_study_subject`).
"""
from .offer_confirmations import (_BODY_CUTS, _BODY_STARTS, _CONFIRM_TITLES_EN, _CONFIRM_TITLES_EN_GENERIC,
                                  _INTERNSHIP, _NOT_STUDIES_SUBJECT, _STUDY_WORDS, _SUBJECT_STARTS, CONFIRMATION_SEEN)
from .offer_reading import (_COMPANY_HEAD, _CONFIRM_TITLES, _CONFIRM_TOP_CHARS, _IC, _ORG_RE, _PERSON_LABELS,
                            _PRIVATE_BODIES, _SB, _letterhead_region, _ruled_status)

_SPECIFIC = _CONFIRM_TITLES + _CONFIRM_TITLES_EN
_ALL_TITLES = _SPECIFIC + _CONFIRM_TITLES_EN_GENERIC


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
    """[(kind, segment, next_line)] of the title block: the lines above the first body sentence, in the top part
    of the page (its first half or `_CONFIRM_TOP_CHARS` characters, like `_confirm_titled`). kind 'title' for a
    line holding a confirmation title (4 words before it, then the title onward, `_cut`), 'subject' for a
    PERKARA / RE / SUBJECT line (`_cut`). `next_line` is the following line when it is short (6 words or fewer)."""
    top = max(_CONFIRM_TOP_CHARS, sum(len(ln) for ln in lines) // 2)
    out, at = [], 0
    for i, ln in enumerate(lines):
        if at > top or _body_line(ln):
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


def titled(lines) -> bool:
    """The title block holds a confirmation title: a specific one, or a generic one with a study word."""
    return any(t in seg for _k, seg, _n in title_block(lines) for t in _SPECIFIC) or generic_titled(lines)


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


def cap_confirmation(lines, result, r, model_version):
    """Gate (d), the CAP (lead, 16 Nov 2026): a page whose title block holds a confirmation title reads SUSPECT
    at best, whatever ruled it genuine (a TVET / agency lift, a genuine baseline such as `ua_offer`)."""
    if result.get('status') != 'genuine' or not titled(lines):
        return result
    seen = result.get('type') or ''
    if seen not in CONFIRMATION_SEEN:
        seen = _CAP_SEEN.get(seen) or ('confirmation_tvet' if seen.startswith('tvet') else 'confirmation_ua')
    tag = 'confirmation_ua' if seen == 'confirmation_ua' else 'confirmation_check'
    return _ruled_status('suspect', r, seen, tag, 'a confirmation of studies (its title) - a person checks; never '
                         'genuine by itself (owner ruling 4, 16 Nov 2026)', model_version)


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
