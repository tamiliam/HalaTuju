"""An offer from a private college or university (IPTS) — the platform-wide rule (owner, 2026-11-18).

"HalaTuju only caters to public courses. We cannot process IPTS courses today." An offer letter from an
IPTS — a private university or college, or a public university's PRIVATE wing (UTM SPACE, Pendidikan
Berterusan, UM SATU, UMS PPPL, a Sdn Bhd operator) — breaks the rule for EVERY gift. So the Pathway fact
turns RED ('gap') with `pathway_offer_private`, an `award.CONFIDENT_DISQUALIFIER`: the cockpit shows
"Rule not met". The owner's answers (decisions.md, 2026-11-18):

  * Q1 = A, FLAG ONLY. It never blocks submission (`consent_blockers` is unchanged) and the amount does
    not move (a pure function of the pathway). The reviewer decides.
  * Q2 = A, REVIEWERS ONLY. No student line, no ticket (`resolution.CODE_TO_TICKET`), no e-mail title.

Two signals, both read off a letter that has been READ (`read_deferred`, the TD-396 rule; no letter or
an unread one gives no line, as `start_year`):

  1. NAME — the read programme, institution or issuer names a private wing or a named private body
     (`results_doc._PRIVATE_ARM_PHRASES`, `offer_reading._PRIVATE_BODIES`, the private names that hold a
     public one such as IUMW; the bare word SPACE on the institution / issuer only). No public-name veto:
     "UTM SPACE" names a public university AND its private wing, and it is the wing that teaches.
  2. SAVED REASON — the letter's stored genuineness reason opens with one of the three IPTS openings
     (`IPTS_REASON_OPENINGS`). It counts ONLY when the read institution / issuer names NO known public
     body (the genuineness public lists, the public-university names, short forms, English names and
     catalogue aliases, the wingless public types such as Kolej Komuniti or IPG, and the course
     catalogue's institutions by `CampusReader`; only a bare type stops vetoing, and only on a
     company-owned line with no partner word), and when there IS a read institution or issuer: a
     public place is never flagged for a gap in our own lists, and a letter we cannot classify keeps
     today's behaviour.

⚠ WHY THIS IS NOT A SHORTLISTING GATE: the letter arrives after the shortlist (as `start_year`). The
shortlist's own `upu_status == 'ipts'` gate is a different, declared answer and is unchanged.

Not caught (TD, docs/technical-debt.md): an offer scored before MODEL_VERSION 1.8.0 or never scored has
no IPTS reason, and a private college named on no list is caught only by its reason.
"""
import functools

from .genuineness.offer_issuers import PRIVATE_ARM_OPENING, PRIVATE_COLLEGE_OPENING, PRIVATE_OFFER_TAG, _UA_SHORT
from .genuineness.offer_reading import _PRIVATE_BODIES, _TAG, _public_names

CODE = 'pathway_offer_private'

#: The set openings of a saved IPTS genuineness reason: the S6 BLOCK's tag, the 1.8.0 private-college
#: reason, and the 1.6.0 private-arm veto. Built from the genuineness modules' own constants.
IPTS_REASON_OPENINGS = (_TAG.format(PRIVATE_OFFER_TAG), PRIVATE_COLLEGE_OPENING, PRIVATE_ARM_OPENING)


def _folded(text):
    from .genuineness.results_doc import _norm_fold_upper_alnum
    return f' {_norm_fold_upper_alnum(text or "")} '


def _letter_lines(offer):
    """``(programme, institution, issuer)`` as the matcher reads a read letter's fields."""
    from .offer_course_match import letter_institution, programme_line
    f = (getattr(offer, 'vision_fields', None) or {}).get('fields')
    f = f if isinstance(f, dict) else {}
    # A stored field may be None or a number.
    programme, code, institution, campus, issuer = (str(f.get(k) or '').strip() for k in
                                                    ('programme', 'programme_code', 'institution', 'campus', 'issuer'))
    return programme_line(programme, code), letter_institution(institution, campus), issuer


#: Private universities whose name CONTAINS a public one (review 2026-11-19): "International University
#: of Malaya-Wales" (IUMW) folds to "... UNIVERSITI MALAYA WALES", which holds " UNIVERSITI MALAYA ", so the
#: reason's public veto would spare it. Read as a NAME signal, which no veto reaches.
_PRIVATE_NAMED_LIKE_PUBLIC = (' UNIVERSITY OF MALAYA WALES ', ' UNIVERSITI MALAYA WALES ', ' IUMW ')


def names_private_body(programme, institution, issuer):
    """Signal 1: the letter's own lines name a private wing or a named private body. The phrases of
    `results_doc._PRIVATE_ARM_PHRASES`, `_PRIVATE_BODIES` and `_PRIVATE_NAMED_LIKE_PUBLIC` are read on
    every line, but the bare word SPACE only on the institution / issuer: a programme such as "Space
    Science" names no wing."""
    from .genuineness.results_doc import _PRIVATE_ARM_PHRASES
    every = _folded(f'{programme} ; {institution} ; {issuer}')
    return (any(p in every for p in _PRIVATE_ARM_PHRASES) or ' SPACE ' in _folded(f'{institution} ; {issuer}')
            or any(b in every for b in _PRIVATE_BODIES + _PRIVATE_NAMED_LIKE_PUBLIC))


#: Public TYPES with no private wing, read even when no catalogue campus matches (a public place is
#: never flagged for a gap in our lists): community, matriculation and vocational colleges, the teacher
#: training institutes (IPG, "IPG Kampus X") and the polytechnics, Malay and English.
_PUBLIC_TYPES = (' KOLEJ KOMUNITI ', ' COMMUNITY COLLEGE ', ' KOLEJ MATRIKULASI ', ' MATRICULATION COLLEGE ',
                 ' KOLEJ VOKASIONAL ', ' VOCATIONAL COLLEGE ', ' INSTITUT PENDIDIKAN GURU ',
                 ' INSTITUTE OF TEACHER EDUCATION ', ' IPG ', ' IPGM ', ' POLITEKNIK ', ' POLYTECHNIC ')
#: English names that the University -> Universiti fold (`_english_folded`) does not reach.
_ENGLISH_UA = (' NATIONAL UNIVERSITY OF MALAYSIA ', ' UNIVERSITY OF SCIENCE MALAYSIA ',
               ' UNIVERSITY OF TECHNOLOGY MALAYSIA ', ' NATIONAL DEFENCE UNIVERSITY OF MALAYSIA ')


@functools.lru_cache(maxsize=1)
def _public_markers():
    """Every padded public name the reason veto reads: the genuineness public lists, the public-university
    short forms, IIUM's English name, the catalogue's aliases, the public types and the English names."""
    from .genuineness.offer_signatures import _IIUM_EN
    from .offer_course_match import _ALIASES
    aliases = tuple(_folded(n) for names in _ALIASES.values() for n in names)
    return (tuple(_public_names()) + tuple(f' {a} ' for a in _UA_SHORT) + (f' {_IIUM_EN} ',) + aliases
            + _PUBLIC_TYPES + _ENGLISH_UA)


def _english_folded(text):
    """A folded line with "University (of)" read as "Universiti": "University of Malaya" names UM."""
    return text.replace(' UNIVERSITY OF ', ' UNIVERSITI ').replace(' UNIVERSITY ', ' UNIVERSITI ')


def _company_owned(text):
    """The line is a company's own ("IPG Academy Berhad", "Kolej Komuniti Swasta X"): a genuineness
    `_PRIVATE_SIGNS` word and NO tie-up word (`_TIE_UP`). "Kolej Komuniti Selayang, rakan industri: Proton
    Berhad" names its company only as a partner, so it is not company-owned."""
    from .genuineness.offer_reading import _PRIVATE_SIGNS, _TIE_UP
    return any(w in text for w in _PRIVATE_SIGNS) and not any(w in text for w in _TIE_UP)


def names_public_body(institution, issuer):
    """True when the read institution or issuer names a known public body (signal 2's veto). Read line by
    line. Only a bare public TYPE (`_PUBLIC_TYPES`) is dropped, and only on a company-owned line
    (`_company_owned`); every public NAME, English ones and the University -> Universiti fold included,
    always vetoes, whatever company or partner word sits beside it (final review 2026-11-19: a miss is
    safer than a false flag, so "Contoh College, partner of University of Science Malaysia" is spared)."""
    for line in (institution, issuer):
        text = _folded(line)
        skip = _PUBLIC_TYPES if _company_owned(text) else ()
        hit = any(m in t for t in (text, _english_folded(text)) for m in _public_markers() if m not in skip)
        if hit:
            return True
    from .offer_course_match import CampusReader, catalogue_index
    index = catalogue_index()                     # one read of the table, only when it is needed
    for line in (institution, issuer):
        if line:
            reader = CampusReader(line, index)
            if reader.named or reader.worded:
                return True
    return False


def ipts_reason(offer) -> bool:
    """True when the letter's saved genuineness reason opens with an IPTS opening."""
    from .genuineness.bands import stored_authenticity
    reason = str(stored_authenticity(getattr(offer, 'vision_fields', None)).get('reason') or '')
    return reason.startswith(IPTS_REASON_OPENINGS)


def private_offer_signal(offer):
    """``(signal, place)`` for an IPTS letter — signal 'name' or 'reason', place the line it names —
    else None. None for no letter and for a letter not read yet."""
    from .read_errors import read_deferred
    if offer is None or read_deferred(getattr(offer, 'vision_fields', None)):
        return None
    programme, institution, issuer = _letter_lines(offer)
    place = institution or issuer or programme
    if names_private_body(programme, institution, issuer):
        return 'name', place
    if (institution or issuer) and ipts_reason(offer) and not names_public_body(institution, issuer):
        return 'reason', place
    return None


def flag_private_offer(fact, offer):
    """The Pathway fact, RED with `pathway_offer_private` when the read letter is from an IPTS. Returns it."""
    hit = private_offer_signal(offer)
    if hit is None:
        return fact
    from .verdict_engine import _item
    fact['status'] = 'gap'
    fact['unresolved'].append(_item('pathway_offer_private', institution=hit[1], signal=hit[0]))   # == CODE; a literal for the i18n gate
    return fact
