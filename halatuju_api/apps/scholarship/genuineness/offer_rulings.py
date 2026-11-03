"""The owner's offer-letter genuineness rulings, applied AFTER the signature band (offer exact-read S6,
MODEL_VERSION 1.23.0).

A genuineness status is a BURSARY decision, not a document type (owner, 2026-11-01, `docs/decisions.md`):
`not_offer_letter` is a FAIL, `suspect` means "not sure, a person decides", `genuine` is a public offer we
can support. The signature families (`offer_signatures`) only know the five fingerprinted public issuers,
so on their own they failed letters the owner rules acceptable and let one private letter through as
merely "not sure". `ruled_offer` is the ONE place those rulings are applied; `results_doc.
signature_genuineness` hands every offer that did not band genuine here.

THE OWNER'S STANCE (2026-11-03): no hedging cap — a ruling-lifted letter reads GREEN when it meets the rule:
"Let us be guided by data. The corpus is sparse now but will fill. Let the model predict; if it is wrong, it
serves as a lesson." So the rules are STRUCTURAL (what a real letter is made of), not word lists, and every
lift is LEARNABLE: its `reason` starts with `[S6 ruling: <tag>]` (`ruling_of`) and a lifted genuine stores a
`doc_seen` of its own (`tvet_*`, `confirmation_*`), so a reviewer's override or a later corpus answer shows
which rule was wrong (`eval/offer_genuineness_check.py` counts them per tag; S8 mines it).

In order (the first that applies wins):
  1. A PUBLIC TVET OFFER (ruling 5; Q2) → `genuine` (`tvet_offer`): a closed-list body named on the
     letterhead (`offer_issuers.tvet_issuer`, the 2026-10-26 C1 rules 2-6); the FIRST institution the page
     names is a public TVET INSTITUTE (`_INSTITUTES`) — never another college / academy named before it (a
     private one "accredited by JPK" or "in collaboration with MARA"); no private sign; and the STRUCTURE of
     a real letter (`_letter_structure`: a reference line, a dated line, an offer title near the top, a
     candidate label, a signatory / closing block, no padding). A TVET page that calls itself a SLIP on its
     letterhead → `suspect` (`tvet_slip`, ruling 6).
  2. A CONFIRMATION OF STUDIES (ruling 4 + the default) → `genuine` (`confirmation`): its own title, a
     student / programme line, a score floor, no private sign, and the FIRST institution named is a
     no-private-wing public one (a polytechnic with its ministry line, UMS, a Form-6 college / SMK with its
     public mark). Another public university's → `suspect` (`confirmation_ua`).
  3. A suspect-band PRIVATE offer (rulings 2 + 7) → `not_offer_letter` (`private_offer`), only on POSITIVE
     private evidence (`_private_signs`, a named private MARA-owned college) or a private conditional.
  4. An ADMISSION PRINTOUT / PORTAL PAGE (ruling 3) that banded `not_offer_letter` → `suspect` (`printout`),
     on portal-only furniture or an e-Daftar slip — never over a private sign or a private letterhead.
ROUND 3 (2026-11-03): a TVET letterhead / a confirmation's letterhead may name ONLY the allowed bodies
(`_clean_letterhead`: no other organisation noun, no partner wording); the structure test asks for a
candidate label with a value and an IC number, a course line and (offers) a reporting line, and an offer of
12+ lines; below the suspect floor the body names the institute again. THE SAFETY RULE: a closed-list public
body on the page with NO positive private evidence that misses a rule reads `suspect` (`tvet_unverified` /
`confirmation_unverified`, a person decides) — never a fail. Another institution named first, with a private
letterhead, reads `not_offer_letter` by the private-college reason.
Anything else keeps the band it scored (`offer_issuers.unfingerprinted_offer`, unchanged).

Calibrated on the 287-letter offer corpus (S6): 14 letters move as ruled; none of the 237 genuine public
offers and none of the rightly rejected letters moves (`eval/offer_genuineness_check.py`). Pure.
"""
import re
import unicodedata

from .bands import GENUINE_MIN, SUSPECT_MAX
from .offer_issuers import (TVET_ISSUERS, _has_offer_words, _letterhead, private_college_reason, tvet_issuer,
                            unfingerprinted_offer)

# The page-reading helpers and word lists moved to `offer_reading` (S6 round 5 split; not verbatim - CHANGELOG).
from .offer_reading import *    # every name re-exported (`offer_reading.__all__`): tests and callers import them here


# ── The rulings ───────────────────────────────────────────────────────────────────────────
def ministry_letter_naming_a_company(ocr_text: str, r: dict) -> bool:
    """True when the private-arm veto (`results_doc._private_arm_offer`) fired ONLY on "Sdn Bhd" /
    "Sendirian Berhad", a ministry family's own issuer line is on the page, and EVERY such line is
    incidental (`_incidental`: a bank / vendor line, or the addressee's address in the candidate block) with
    no organisation noun on it or the line before. Anywhere else (the letterhead, a logo strip, a footer, a
    tuition centre, a fee "kepada X Sdn Bhd") keeps the veto. `_private_arm_offer` itself is unchanged."""
    from .offer_issuers import FAMILY_ISSUER_SIG
    from .results_doc import _PRIVATE_ARM_PHRASES
    lines = _folded_lines(ocr_text)
    page = _page(lines)
    hits = [p for p in _PRIVATE_ARM_PHRASES if p in page]
    if not hits or set(hits) - {'SDN BHD', 'SENDIRIAN BERHAD'} or ' SPACE ' in page:
        return False
    scores = r.get('scores') or {}
    if not any(FAMILY_ISSUER_SIG[f] in ((scores.get(f) or {}).get('present') or []) for f in _MINISTRY_FAMILIES):
        return False
    return _company_lines_incidental(lines)


def _company_lines_incidental(lines) -> bool:
    """Every "Sdn Bhd" / "Sendirian Berhad" line is incidental (`_incidental`), off the letterhead, with no
    organisation noun on it or the line before."""
    head = _letterhead_lines(lines)
    for i, ln in enumerate(lines):
        if ' SDN BHD ' in ln or ' SENDIRIAN BERHAD ' in ln:
            near = (lines[i - 1] if i else '') + ln + (lines[i + 1] if i + 1 < len(lines) else '')
            name = [w for w in ln.split(' SDN BHD ')[0].split(' SENDIRIAN BERHAD ')[0].split()
                    if w not in _LABEL_WORDS][-2:]
            phrase = f" {' '.join(name)} "  # round 6: a one-word name too ("MERCU" / "Penaja : Mercu Sdn Bhd")
            on_letterhead = bool(name) and any(phrase in h for h in head)
            if (ln in head or not _incidental(lines, i) or _ORG_RE_NO_COMPANY.search(_unstreeted(near))
                    or _NEAR_EXTRA.search(near) or on_letterhead):
                return False            # round 5 (Low 7): the company's own name on the letterhead keeps the veto
    return True


#: Words beside a company that still name an institution (Low 7), and labels that are not a company's name.
_NEAR_EXTRA = re.compile(r' (?:CAMPUS|TEKNOLOGI|TECHNOLOGY)(?= )')
_LABEL_WORDS = {'PENAJA', 'TAJAAN', 'DITAJA', 'SPONSOR', 'PEMBEKAL', 'SUPPLIER', 'PENCETAK', 'DICETAK', 'BAYARAN',
                'AKAUN', 'LADANG', 'ESTATE', 'KEPADA', 'OLEH'}


def tvet_letter_naming_a_company(ocr_text: str, r: dict) -> bool:
    """Round 4: the same excuse for a closed-list TVET body's letter (it prints no ministry issuer line): a
    real IKBN letter naming its uniform supplier, insurer, sponsor or the student's estate address keeps its
    rules; a "Sdn Bhd" on the letterhead still vetoes."""
    from .results_doc import _PRIVATE_ARM_PHRASES
    lines = _folded_lines(ocr_text)
    page = _page(lines)
    hits = [p for p in _PRIVATE_ARM_PHRASES if p in page]
    if not hits or set(hits) - {'SDN BHD', 'SENDIRIAN BERHAD'} or ' SPACE ' in page:
        return False
    return bool(tvet_issuer(_without_incidental_companies(ocr_text), r.get('scores'))) and \
        _company_lines_incidental(lines)


def _without_incidental_companies(ocr_text: str) -> str:
    """The text without its incidental "Sdn Bhd" lines (a supplier, an insurer, a sponsor, the student's
    estate address — `_incidental`), so the 600-character letterhead tests of `offer_issuers` do not read a
    short letter's body company as its letterhead."""
    from .results_doc import _norm_fold_upper_alnum
    raws = [raw for raw in unicodedata.normalize('NFKC', ocr_text or '').splitlines() if _norm_fold_upper_alnum(raw)]
    lines = [f' {_norm_fold_upper_alnum(raw)} ' for raw in raws]
    keep = [raw for i, (raw, ln) in enumerate(zip(raws, lines))
            if not ((' SDN BHD ' in ln or ' SENDIRIAN BERHAD ' in ln) and _incidental(lines, i))]
    return '\n'.join(keep)


def _unproven(r, seen, tag, what, model_version):
    """THE SAFETY RULE (round-3 review): a closed-list public body is on the page and there is NO positive
    private evidence, but the page misses a rule — a person decides, never a fail. In the suspect band the
    1.8.0 path answers (None → NOT CHECKED, no signal); below it, `suspect`."""
    if SUSPECT_MAX <= r['probability'] < GENUINE_MIN:
        return None
    return _ruled_status('suspect', r, seen, tag, f'{what}: a public body on the page but not a complete letter '
                         'by the rules - suspect, a person decides', model_version)


def _tvet(ocr_text, r, model_version):
    key = tvet_issuer(_without_incidental_companies(ocr_text), r.get('scores'))
    if not key:
        return None
    name, lines = TVET_ISSUERS[key][0], _folded_lines(ocr_text)
    if _private_signs(lines) or _private_mara_letterhead(ocr_text):
        return None                     # positive private evidence: the band (and its private reason) stands
    if _SLIP in _letterhead(ocr_text):
        return _ruled_status('suspect', r, key, 'tvet_slip', f'{name}: a TVET offer SLIP, not an offer letter - '
                             'suspect (owner ruling 6); a person checks it', model_version)
    if _first_institution(lines, _TVET_NAMES) == 'other':
        # Another organisation is named first — the issuer — and the TVET name is a partner / mention
        # (round-3 review): a private institution's letter, a fail by its own reason.
        why = private_college_reason(ocr_text, r) or (
            f'another institution issues this letter; {name} is named only beside it - not a public offer')
        return _ruled_status('not_offer_letter', r, r['type'], 'private_offer', f'{why} (owner rulings 2 + 7)',
                             model_version)
    if not _clean_letterhead(lines, _TVET_NAMES):
        return None                     # round 6: another organisation on the letterhead IS private evidence
    if _first_institution(lines, _INSTITUTES) != 'allowed':
        return _unproven(r, key, 'tvet_unverified', name, model_version)
    if not _letter_structure(lines, _TITLE, min_lines=_OFFER_MIN_LINES, reporting=True):
        return _unproven(r, key, 'tvet_unverified', name, model_version)
    if r['probability'] < SUSPECT_MAX:
        body = lines[len(_letterhead_lines(lines)):]
        if not any(i in ln for ln in body for i in _INSTITUTES):
            return _unproven(r, key, 'tvet_unverified', name, model_version)
    return _ruled_status('genuine', r, key, 'tvet_offer', f'{name}: a public TVET institute\'s offer letter - '
                         'a public offer (owner rulings 5 and Q2)', model_version)


def confirmation_kind(ocr_text: str, probability: float = 1.0) -> str:
    """The `confirmation_*` code of a confirmation-of-studies letter by its issuer, or '' (no title, below the
    score floor, positive private evidence, or no public issuer named first on a clean letterhead)."""
    lines = _folded_lines(ocr_text)
    page = _page(lines)
    if not _confirm_titled(lines, probability):
        return ''
    if _private_mara_letterhead(ocr_text) or _private_signs(lines):
        return ''
    scan = _without_poly_department(lines)                  # the department's name names no polytechnic
    for seen, names, marks in _NO_PRIVATE_WING:
        if (_first_institution(scan, names) == 'allowed' and any(m in page for m in marks)
                and _clean_letterhead(scan, names)):
            return seen
    from .results_doc import _UA_NAMES
    ua = tuple(f' {n} ' for n in _UA_NAMES)
    if _first_institution(scan, ua) == 'allowed' and _clean_letterhead(scan, ua):
        return 'confirmation_ua'
    return ''


def _confirmation(ocr_text, r, model_version):
    seen = confirmation_kind(ocr_text, r['probability'])
    if not seen:
        return None
    if seen == 'confirmation_ua':
        return _ruled_status('suspect', r, seen, 'confirmation_ua', 'a public university confirmation-of-studies '
                             'letter - suspect: confirm the government programme (owner ruling 4)', model_version)
    raw = _folded_lines(ocr_text)
    lines, glued = _unglued(raw), any(len(ln.split()) > 40 for ln in raw)
    if not (_letter_structure(lines, _CONFIRM_TITLES, min_lines=_CONFIRM_MIN_LINES, glued=glued)
            and _own_identity_lines(lines, _CONFIRM_TITLES)):
        return _unproven(r, seen, 'confirmation_unverified', 'a confirmation of studies', model_version)
    return _ruled_status('genuine', r, seen, 'confirmation', 'a confirmation-of-studies letter from a public '
                         'institution with no private wing - an acceptable alternative (owner ruling 4)',
                         model_version)


def _printout(ocr_text, r) -> bool:
    lines = _folded_lines(ocr_text)
    page = _page(lines)
    if (_APPLICATION_SLIP in page or _private_signs(lines) or _private_mara_letterhead(ocr_text)
            or private_college_reason(ocr_text, r)):
        return False                    # never lift a page that is, or shows, a private institution
    if any(m in page for m in _EDAFTAR):
        return True
    return _has_offer_words(page) and sum(1 for m in _PORTAL_FURNITURE if m in page) >= 2


#: Round 5: the public bodies a ruled page may be FROM — what the safety rule asks to be named first.
_PUBLIC_FIRST = None


def _public_first_names():
    """Only the closed-list bodies' NAMES (round 6): the TVET bodies, the polytechnics, UMS and the Form-6
    names. A generic ministry / department / government word is no institution — its line is skipped and
    the institution after it is the one named first ("KEMENTERIAN PENDIDIKAN TINGGI / KOLEJ ABC")."""
    global _PUBLIC_FIRST
    if _PUBLIC_FIRST is None:
        names = list(_TVET_NAMES) + [n for _k, ns, _m in _NO_PRIVATE_WING for n in ns]
        _PUBLIC_FIRST = tuple(dict.fromkeys(names))
    return _PUBLIC_FIRST


def _without_poly_department(lines):
    out = []
    for ln in lines:
        for d in _POLY_DEPARTMENTS:
            ln = ln.replace(d, ' ')
        out.append(ln)
    return out


def _positive_private(ocr_text, lines, r) -> bool:
    """Positive private evidence (rounds 5 + 6): a private sign off the excused lines, a private MARA-owned name
    on the letterhead, partner wording on it, a fee paid to a company, a letterhead naming an organisation
    other than the closed-list bodies, or the private-college reason."""
    fee_to_company = any(' KEPADA ' in ln and (' SDN BHD ' in ln or ' BHD ' in ln) for ln in lines)
    partner = any(any(p in ln for p in _PARTNER) for ln in _letterhead_lines(lines))
    return (_private_signs(lines) or _private_mara_letterhead(ocr_text) or partner or fee_to_company
            or not _clean_letterhead(_without_poly_department(lines), _public_first_names())
            or bool(private_college_reason(ocr_text, r)))


def _safety_exit(ocr_text, r, out, model_version):
    """THE SAFETY RULE AT ONE EXIT (round 5): a page a ruling engaged on — a closed-list TVET body or a
    confirmation-of-studies title at the top — whose FIRST institution is a closed-list body (TVET list,
    polytechnic, UMS, a Form-6 name; round 6: never a bare ministry word) and which shows NO positive private
    evidence (`_positive_private`, round 6: an unclean letterhead counts) may read
    genuine or suspect, NEVER not_offer_letter. A letter that misses a rule then reads suspect."""
    if out.get('status') != 'not_offer_letter':
        return out
    lines = _folded_lines(ocr_text)
    tvet = tvet_issuer(_without_incidental_companies(ocr_text), r.get('scores'))
    confirm = _confirm_titled(lines, r['probability'])      # round 6: the floor, and the title at the top
    if not (tvet or confirm):
        return out
    scan = _without_poly_department(lines)
    if _first_institution(scan, _public_first_names()) != 'allowed' or _positive_private(ocr_text, lines, r):
        return out
    tag = 'tvet_unverified' if tvet else 'confirmation_unverified'
    return _ruled_status('suspect', r, tvet or out.get('type') or r['type'], tag,
                         'a public body named first and no private evidence, but not a complete letter by the '
                         'rules - suspect, a person decides (the safety rule)', model_version)


def ruled_offer(ocr_text: str, r: dict, status: str, reason: str, model_version: str) -> dict:
    """The genuineness of an offer that did NOT band genuine, after the owner's rulings (module note). Every
    result passes `_safety_exit` (round 5)."""
    ocr_text = unicodedata.normalize('NFKC', ocr_text or '')
    return _safety_exit(ocr_text, r, _ruled_offer(ocr_text, r, status, reason, model_version), model_version)


def _ruled_offer(ocr_text: str, r: dict, status: str, reason: str, model_version: str) -> dict:
    ruled = _tvet(ocr_text, r, model_version) or _confirmation(ocr_text, r, model_version)
    if ruled:
        return ruled
    printout = _printout(ocr_text, r)
    if status == 'suspect' and SUSPECT_MAX <= r['probability'] < GENUINE_MIN and not printout:
        lines = _folded_lines(ocr_text)
        page = _page(lines)
        positive = (_private_signs(lines) or _private_mara_letterhead(ocr_text)
                    or any(c in page for c in _CONDITIONAL))
        why = private_college_reason(ocr_text, r) if positive else ''
        if why:
            return _ruled_status('not_offer_letter', r, r['type'], 'private_offer', f'{why} (owner rulings 2 + 7)',
                                 model_version)
    out = unfingerprinted_offer(ocr_text, r, status, reason, model_version)
    if out['status'] == 'not_offer_letter' and printout:
        return {**out, 'status': 'suspect',
                'reason': (_TAG.format('printout') + 'an admission printout / portal page, not the offer letter '
                           f"- suspect (owner ruling 3); {out['reason']}")[:300]}
    return out
