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
     (`catalogue_levels.private_arm_letter`, `offer_reading._PRIVATE_BODIES`). No public-name veto: "UTM
     SPACE" names a public university AND its private wing, and it is the wing that teaches.
  2. SAVED REASON — the letter's stored genuineness reason opens with one of the three IPTS openings
     (`IPTS_REASON_OPENINGS`). It counts ONLY when the read institution / issuer names NO known public
     body (the genuineness public lists, the public-university names and short forms, and the course
     catalogue's institutions by `CampusReader`), and when there IS a read institution or issuer: a
     public place is never flagged for a gap in our own lists, and a letter we cannot classify keeps
     today's behaviour.

⚠ WHY THIS IS NOT A SHORTLISTING GATE: the letter arrives after the shortlist (as `start_year`). The
shortlist's own `upu_status == 'ipts'` gate is a different, declared answer and is unchanged.

Not caught (TD, docs/technical-debt.md): an offer scored before MODEL_VERSION 1.8.0 or never scored has
no IPTS reason, and a private college named on no list is caught only by its reason.
"""
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


def names_private_body(programme, institution, issuer):
    """Signal 1: the letter's own lines name a private wing or a named private body."""
    from .catalogue_levels import private_arm_letter
    if private_arm_letter(programme, f'{institution} {issuer}'):
        return True
    text = _folded(f'{programme} ; {institution} ; {issuer}')
    return any(b in text for b in _PRIVATE_BODIES)


def names_public_body(institution, issuer):
    """True when the read institution or issuer names a known public body (signal 2's veto)."""
    text = _folded(f'{institution} ; {issuer}')
    if any(n in text for n in _public_names()) or any(f' {a} ' in text for a in _UA_SHORT):
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
