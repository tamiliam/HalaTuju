"""The owner's offer-letter genuineness rulings, applied AFTER the signature band (offer exact-read S6,
MODEL_VERSION 1.23.0).

A genuineness status is a BURSARY decision, not a document type (owner, 2026-11-01, `docs/decisions.md`):
`not_offer_letter` is a FAIL, `suspect` means "not sure, a person decides", `genuine` is a public offer we
can support. The signature families (`offer_signatures`) only know the five fingerprinted public issuers,
so on their own they failed letters the owner rules acceptable and let one private letter through as
merely "not sure". `ruled_offer` is the ONE place those rulings are applied; `results_doc.
signature_genuineness` hands every offer that did not band genuine here.

In order (the first that applies wins):
  1. A PUBLIC TVET OFFER (ruling 5; owner 2026-11-03, Q2) — a closed-list issuer (`offer_issuers.
     TVET_ISSUERS`) named on the LETTERHEAD of a page with offer wording, no sponsor line naming it, no
     private company / private MARA institution (`offer_issuers.tvet_issuer`, the 2026-10-26 C1 rules
     2-6), and an offer BODY (a course line and a registration / date line) → `genuine`, at ANY band
     (the 1.8.0 "suspect band only" precondition is lifted). A TVET offer
     SLIP (a page that calls itself a slip) → `suspect` (ruling 6).
  2. A CONFIRMATION-OF-STUDIES letter (ruling 4; default 2026-11-03) — its own title ("Pengesahan
     Pelajar" / "Pengesahan Sebagai Pelajar" / "Pengesahan Belajar") from a public institution with no
     private wing named on the letterhead — a polytechnic, Universiti Malaysia Sabah, or a Form-6
     college — → `genuine` (`doc_seen` `confirmation_*`: an acceptable alternative to an offer, but it
     never writes a course pick — `pathway_engine.is_confirmation_letter`). Any other public
     university's confirmation → `suspect` (`confirmation_ua`: confirm the government programme).
  3. A PRIVATE college offer that banded `suspect` (rulings 2 + 7: an IPTS offer, conditional or not, is
     `not_offer_letter`) → `not_offer_letter`, by the honest private-college reason.
  4. An ADMISSION PRINTOUT / PORTAL PAGE (ruling 3) that banded `not_offer_letter` → `suspect`: we cannot
     say outright it is not an offer. Recognised on POSITIVE evidence only — two pieces of a result /
     download page's own furniture beside offer wording, or an e-Daftar registration slip — and never
     an application slip ("Slip Permohonan": no offer was made).
Anything else keeps the band it scored (`offer_issuers.unfingerprinted_offer`, unchanged).

Calibrated on the 287-letter offer corpus (S6): 14 letters move as ruled; none of the 237 genuine
public offers and none of the rightly rejected letters moves (`eval/offer_genuineness_check.py`). Pure.
"""
from .bands import GENUINE_MIN, SUSPECT_MAX
from .offer_issuers import (TVET_ISSUERS, _fold, _has_offer_words, _letterhead, private_college_reason,
                            tvet_issuer, unfingerprinted_offer)

#: A TVET page that calls itself a SLIP (e.g. the JPK UP_TVET "Slip Tawaran") is not an offer letter.
_SLIP = ' SLIP '
#: A confirmation-of-studies letter's own title.
_CONFIRM_TITLES = (' PENGESAHAN PELAJAR ', ' PENGESAHAN SEBAGAI PELAJAR ', ' PENGESAHAN BELAJAR ',
                   ' PENGESAHAN STATUS PELAJAR ')
#: The JPPKK department's own name prints "POLITEKNIK" without naming a polytechnic.
_JPPKK = ' JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI '
#: Public institutions with no private wing (owner default, 2026-11-03), as named on a letterhead.
_NO_PRIVATE_WING = (('confirmation_polytechnic', (' POLITEKNIK ',)),
                    ('confirmation_ums', (' UNIVERSITI MALAYSIA SABAH ',)),
                    ('confirmation_form6', (' TINGKATAN ENAM ',)))
CONFIRMATION_SEEN = frozenset(k for k, _ in _NO_PRIVATE_WING) | {'confirmation_ua'}
#: A result / download page's own furniture (portal pages print several; a letter prints none of them
#: as a pair).
_PORTAL_FURNITURE = (' SEMAKAN KEPUTUSAN ', ' KEPUTUSAN PERMOHONAN ', ' TAHNIAH ', ' MUAT TURUN ',
                     ' CETAK ', ' LOG KELUAR ', ' BERJAYA ')
#: An e-Daftar registration slip printed in front of (or instead of) the offer.
_EDAFTAR = (' SLIP E DAFTAR ', ' SLIP EDAFTAR ')
#: An APPLICATION slip: the student applied, nobody offered anything.
_APPLICATION_SLIP = ' SLIP PERMOHONAN '


#: The ministry-body families (their issuer line is a government department, which has no private
#: wing). The UA family is deliberately NOT here: a university's private arm prints the parent's name.
_MINISTRY_FAMILIES = ('stpm', 'matriculation', 'polytechnic', 'pismp')


def ministry_letter_naming_a_company(ocr_text: str, r: dict) -> bool:
    """1.23.0 (S6): True when the private-arm veto (`results_doc._private_arm_offer`) fired ONLY on
    "Sdn Bhd" and a ministry family's own issuer line is on the page — a polytechnic offer photographed
    beside a company's sign, or naming the bank its fees are paid into, is not a private operator's
    letter (a private college never prints a ministry department as its issuer). Then the veto is skipped and the letter is scored by its band. `_private_arm_offer` itself
    is unchanged (`catalogue_levels`, `pathway_engine.offer_reporting_bonus` gate 3b read it)."""
    from .offer_issuers import FAMILY_ISSUER_SIG
    from .results_doc import _PRIVATE_ARM_PHRASES
    page = _fold(ocr_text)
    hits = [p for p in _PRIVATE_ARM_PHRASES if p in page]
    if hits != ['SDN BHD'] or ' SPACE ' in page:
        return False
    scores = r.get('scores') or {}
    return any(FAMILY_ISSUER_SIG[f] in ((scores.get(f) or {}).get('present') or []) for f in _MINISTRY_FAMILIES)


def _ruled_status(status, r, seen, reason, model_version):
    return {'status': status, 'probability': r['probability'], 'type': seen, 'present': r['present'],
            'missing': r['missing'], 'reason': reason[:300], 'model_version': model_version}


#: An offer's BODY, beyond the offer word itself: a course line and a registration / date line. Q2's
#: genuine needs both, so a three-line typed page under an institute's name (the 2026-10-26 C1 review
#: probe) is not lifted to green; such a page keeps the 1.8.0 path (NOT CHECKED in the suspect band).
_COURSE_WORDS = (' PROGRAM ', ' KURSUS ', ' SIJIL ', ' DIPLOMA ', ' BIDANG ')
_DATE_WORDS = (' LAPOR DIRI ', ' PENDAFTARAN ', ' MENDAFTAR ', ' DAFTAR ', ' HADIR ', ' TARIKH ')


def _tvet(ocr_text, r, model_version):
    key = tvet_issuer(ocr_text, r.get('scores'))
    if not key:
        return None
    name = TVET_ISSUERS[key][0]
    page = _fold(ocr_text)
    if _SLIP in page:
        return _ruled_status('suspect', r, key, f'{name}: a TVET offer SLIP, not an offer letter - suspect '
                       '(owner ruling 6, 2026-11-01); a person checks it', model_version)
    if not (any(w in page for w in _COURSE_WORDS) and any(w in page for w in _DATE_WORDS)):
        return None
    return _ruled_status('genuine', r, key, f'{name}: a public TVET offer named on the letterhead - a public '
                   'offer (owner rulings 5, 2026-11-01, and Q2, 2026-11-03)', model_version)


def confirmation_kind(ocr_text: str) -> str:
    """The `confirmation_*` code of a confirmation-of-studies letter, or ''."""
    page = _fold(ocr_text)
    if not any(t in page for t in _CONFIRM_TITLES):
        return ''
    from .offer_issuers import _PRIVATE_HEAD, _PRIVATE_MARA
    head = _letterhead(ocr_text).replace(_JPPKK, ' ')
    if any(p in page for p in _PRIVATE_MARA) or any(p in head for p in _PRIVATE_HEAD):
        return ''                       # a private (or MARA-owned private) institution's letter
    for seen, names in _NO_PRIVATE_WING:
        if any(n in head for n in names):
            return seen
    from .offer_issuers import _UA_SHORT
    from .results_doc import _UA_NAMES
    if any(f' {n} ' in page for n in _UA_NAMES) or any(f' {a} ' in head for a in _UA_SHORT):
        return 'confirmation_ua'
    return ''


def _confirmation(ocr_text, r, model_version):
    seen = confirmation_kind(ocr_text)
    if not seen:
        return None
    if seen == 'confirmation_ua':
        return _ruled_status('suspect', r, seen, 'a public university confirmation-of-studies letter - suspect: '
                       'confirm the student is on the government programme (owner ruling 4)', model_version)
    return _ruled_status('genuine', r, seen, 'a confirmation-of-studies letter from a public institution with no '
                   'private wing - an acceptable alternative to an offer (owner ruling 4)', model_version)


def _printout(ocr_text) -> bool:
    page = _fold(ocr_text)
    if _APPLICATION_SLIP in page:
        return False
    if any(m in page for m in _EDAFTAR):
        return True
    return _has_offer_words(page) and sum(1 for m in _PORTAL_FURNITURE if m in page) >= 2


def ruled_offer(ocr_text: str, r: dict, status: str, reason: str, model_version: str) -> dict:
    """The genuineness of an offer that did NOT band genuine, after the owner's rulings (module note)."""
    ruled = _tvet(ocr_text, r, model_version) or _confirmation(ocr_text, r, model_version)
    if ruled:
        return ruled
    if status == 'suspect' and SUSPECT_MAX <= r['probability'] < GENUINE_MIN and not _printout(ocr_text):
        why = private_college_reason(ocr_text, r)
        if why:
            return _ruled_status('not_offer_letter', r, r['type'], f'{why} (owner rulings 2 + 7)', model_version)
    out = unfingerprinted_offer(ocr_text, r, status, reason, model_version)
    if out['status'] == 'not_offer_letter' and _printout(ocr_text):
        return {**out, 'status': 'suspect',
                'reason': (f'an admission printout / portal page, not the offer letter - suspect (owner '
                           f"ruling 3); {out['reason']}")[:300]}
    return out
