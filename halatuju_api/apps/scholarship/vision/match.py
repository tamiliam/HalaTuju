"""Name / address presence on a supporting document, and the match verdicts stored on the row
(moved verbatim from ``vision.py``, audit sprint A3.1)."""

import logging
import re

from django.utils import timezone

from .names import canonical_name_tokens
from .. import vision as _v   # seams resolve on the package: one patch target reaches every caller

logger = logging.getLogger(__package__)   # 'apps.scholarship.vision', one name as before the split


def name_present(text: str, names) -> bool:
    """True if any of ``names`` (token-set, MyKad connectors stripped) is fully
    contained in the OCR ``text``. Order / case / extra words in the doc are fine."""
    text_tokens = canonical_name_tokens(text)
    if not text_tokens:
        return False
    for n in names:
        nt = canonical_name_tokens(n)
        if nt and nt.issubset(text_tokens):
            return True
    return False


# Common Malaysian address-word abbreviations → canonical, applied to BOTH the profile and the
# bill before comparison so "JLN/ABD/TMN/LRG/SG/BKT" match "Jalan/Abdul/Taman/Lorong/Sungai/Bukit".
_ADDR_ABBREV = {
    'jln': 'jalan', 'jl': 'jalan', 'lrg': 'lorong', 'lbh': 'lebuh', 'lbuh': 'lebuh',
    'psn': 'persiaran', 'lkg': 'lengkok', 'tmn': 'taman', 'bdr': 'bandar', 'bkt': 'bukit',
    'kg': 'kampung', 'kpg': 'kampung', 'kmpg': 'kampung', 'sg': 'sungai', 'pkn': 'pekan',
    'blk': 'blok', 'tkt': 'tingkat', 'abd': 'abdul', 'abdl': 'abdul',
    'moh': 'mohamad', 'mhd': 'mohamad', 'muhd': 'mohamad',
}
# Road / structural words carrying NO identity — dropped from the STREET-NAME comparison so a
# match hinges on the road NAME + numbers + taman (not the word "jalan"). Stored canonical.
_ADDR_GENERIC = {
    'no', 'jalan', 'taman', 'lorong', 'lebuh', 'lebuhraya', 'persiaran', 'lengkok', 'bandar',
    'kampung', 'lot', 'blok', 'block', 'tingkat', 'aras', 'unit', 'fasa', 'phase', 'seksyen',
    'presint', 'precinct', 'pt', 'ptd', 'pekan',
}
# Road words that mark the END of the leading house/lot-number zone (everything BEFORE the first
# of these is the house number; after it is the road name + road number).
_ROAD_HEAD = {'jalan', 'lorong', 'lebuh', 'lebuhraya', 'persiaran', 'lengkok', 'taman',
              'bandar', 'kampung'}


def _addr_norm(tok: str) -> str:
    return _ADDR_ABBREV.get(tok, tok)


def _norm_house_no(tok: str) -> str:
    """Normalise a house/lot number for comparison: split on separators, strip leading zeros per
    segment, re-join. So '100-03-03' and '100-3-3' both → '100_3_3'; '3' → '3'."""
    segs = [s.lstrip('0') or '0' for s in re.split(r'[^a-z0-9]+', tok.lower()) if s]
    return '_'.join(segs)


def _house_numbers(s: str) -> set:
    """The leading house/lot number(s) — the alnum chunks containing a digit that sit BEFORE the
    first road word. 'No 3 Jalan…'→{'3'}; '7 Jln Gangsa 9'→{'7'} (the road number '9' is after
    'jalan'); '100-3-3 Puncak Jalan…'→{'100_3_3'}."""
    out = set()
    for raw in re.findall(r'[a-z0-9][a-z0-9/\-]*', (s or '').lower()):
        if _addr_norm(raw) in _ROAD_HEAD:
            break
        if any(ch.isdigit() for ch in raw):
            out.add(_norm_house_no(raw))
    return out


def _street_name_tokens(s: str) -> set:
    """Distinctive street/taman NAME tokens: abbrev-normalised, alnum (road numbers like '9' /
    '5','8' from '5/8' / '3a' kept), generic road words dropped — so only the road NAME + taman
    name + numbers remain ('Jalan Sultan Abdul Samad 11' → {sultan, abdul, samad, 11})."""
    toks = {_addr_norm(t) for t in re.findall(r'[a-z0-9]+', (s or '').lower())}
    return {t for t in toks if t and t not in _ADDR_GENERIC}


def address_match(doc_text: str, *, postcode: str = '', city: str = '', street: str = '') -> str:
    """Weighted home-address verdict for a utility bill — ``'found'`` | ``'unconfirmed'`` |
    ``'mismatch'``.

    The HOUSE NUMBER is the anchor; the STREET name confirms the road; the POSTCODE **or** CITY
    confirms the locality (either one — a bill prints one or the other, and a town has two names:
    Port/Pelabuhan Klang, Skudai/Johor Bahru, Georgetown/P.Pinang). Any TWO of the three matching
    is a confident ``found``; exactly one is ``unconfirmed`` (eyeball at interview, never a hard
    miss); a genuinely different home (none match AND the bill prints a DIFFERENT 5-digit postcode)
    is ``mismatch``. Abbreviations are normalised on both sides (Jln/Jalan, Abd/Abdul, SG/Sungai…).
    When no street is on file, fall back to locality only: postcode AND city → found."""
    doc = doc_text or ''
    pc = re.sub(r'\D', '', postcode or '')
    pc_ok = len(pc) == 5 and pc in re.sub(r'\D', '', doc)
    city_toks = {_addr_norm(t) for t in re.findall(r'[a-z]+', (city or '').lower())}
    doc_words = {_addr_norm(t) for t in re.findall(r'[a-z]+', doc.lower())}
    city_ok = bool(city_toks) and bool(city_toks & doc_words)
    doc_pcs = set(re.findall(r'\b\d{5}\b', doc))
    different_pc = len(pc) == 5 and bool(doc_pcs) and pc not in doc_pcs

    prof_house = _house_numbers(street)
    prof_street = _street_name_tokens(street)

    if not prof_house and not prof_street:
        # No street on file — locality-only fallback: require BOTH postcode and city to confirm.
        if pc_ok and city_ok:
            return 'found'
        if pc_ok or city_ok:
            return 'unconfirmed'
        return 'mismatch' if different_pc else 'unconfirmed'

    house_ok = bool(prof_house & _house_numbers(doc))
    overlap = prof_street & _street_name_tokens(doc)
    street_ok = bool(prof_street) and len(overlap) >= max(2, (len(prof_street) + 1) // 2)
    locality_ok = pc_ok or city_ok

    score = int(house_ok) + int(street_ok) + int(locality_ok)
    if score >= 2:
        return 'found'
    if score == 1:
        return 'unconfirmed'
    return 'mismatch' if different_pc else 'unconfirmed'


def address_present(text: str, *, postcode: str = '', city: str = '', street: str = '') -> bool:
    """Back-compat bool wrapper — True only on a confident ``found``."""
    return address_match(text, postcode=postcode, city=city, street=street) == 'found'


def run_vision_match_for_document(doc, *, names, postcode='', city='', street='', check_address=False, ocr=None) -> dict:
    """OCR a supporting document and record soft verdicts: does an expected name
    appear (``vision_name_match``), and — for bills — does the home address appear
    (``vision_address_match``)? Verdicts: 'found' / 'not_found' / 'unreadable'.
    Never blocks, never raises. Pass ``ocr`` to reuse a prior OCR pass."""
    r = ocr if ocr is not None else _v.ocr_document(doc)
    if r['error'] or not (r['text'] or '').strip():
        # Clobber guard (code-health S2 #5): the blob is immutable — a no-text read where a
        # previous run reached a real verdict is OUR failure (Storage/OCR outage). Keep the
        # stored verdicts (a re-run must never downgrade 'found' to 'unreadable' on an outage).
        if doc.vision_name_match not in ('', 'unreadable'):
            logger.warning('run_vision_match: kept stored verdicts for doc %s (re-run failed: %s)',
                           doc.id, r['error'] or 'no text read')
            return {'name_match': doc.vision_name_match, 'address_match': doc.vision_address_match,
                    'error': r['error'] or 'no text read', 'stale_kept': True}
        doc.vision_name_match = 'unreadable'
        doc.vision_address_match = 'unreadable' if check_address else ''
        doc.vision_error = r['error'] or 'no text read'
    else:
        doc.vision_name_match = 'found' if name_present(r['text'], names) else 'not_found'
        doc.vision_address_match = (
            address_match(r['text'], postcode=postcode, city=city, street=street)
            if check_address else ''
        )
        doc.vision_error = ''
    doc.vision_run_at = timezone.now()
    doc.save(update_fields=['vision_name_match', 'vision_address_match', 'vision_error', 'vision_run_at'])
    return {'name_match': doc.vision_name_match, 'address_match': doc.vision_address_match, 'error': doc.vision_error}
