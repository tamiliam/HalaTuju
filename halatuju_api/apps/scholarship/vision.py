"""
Google Cloud Vision OCR for the IC (MyKad) upload — a SOFT signal, never a
hard block. The admin verify-&-accept (S11a) remains the real identity gate;
this module exists to (a) help the student spot typos at upload time, and
(b) give the admin a hint next to the manual checklist.

Pure helpers (``nric_match``, ``name_match``, the canonical normalisers) are
the testable core — they run pure and require no API key. The actual Vision
call (``extract_mykad``) is mocked in tests and degrades gracefully to an
error dict when the API is unavailable or the SDK isn't installed.
"""
import logging
import re
from typing import Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Stripped before name comparison — common MyKad name suffixes / parentage markers.
_NAME_NOISE = re.compile(
    r"\b(bin|binti|a/l|a/p|al|ap|d/o|s/o|@)\b",
    flags=re.IGNORECASE,
)


def _canonical_nric(s: str) -> str:
    """Strip hyphens, spaces, and non-digits. Returns ''-on-blank."""
    return re.sub(r'\D', '', s or '')


def _canonical_name_tokens(s: str) -> set:
    """Lowercase, strip MyKad parentage tokens, return a tokens set."""
    if not s:
        return set()
    cleaned = _NAME_NOISE.sub(' ', s.lower())
    return {t for t in re.split(r'[^a-z]+', cleaned) if t}


def nric_match(extracted: str, profile_nric: str) -> bool:
    """True iff the two NRICs are equal after canonicalisation (digits only)."""
    a, b = _canonical_nric(extracted), _canonical_nric(profile_nric)
    return bool(a) and bool(b) and a == b


def name_match(extracted: str, profile_name: str) -> str:
    """
    'match' if the token sets are equal after stripping MyKad parentage tokens;
    'partial' if one set is a strict subset of the other (so e.g. the profile
    name omits a middle/surname the IC carries, or vice versa);
    'mismatch' otherwise. Empty inputs return 'mismatch'.
    """
    a = _canonical_name_tokens(extracted)
    b = _canonical_name_tokens(profile_name)
    if not a or not b:
        return 'mismatch'
    if a == b:
        return 'match'
    if a < b or b < a:
        return 'partial'
    return 'mismatch'


_NRIC_REGEX = re.compile(r'\b(\d{6}[-\s]?\d{2}[-\s]?\d{4})\b')


def _extract_nric(text: str) -> str:
    """Return the first MyKad-shaped NRIC in the OCR text, or ''."""
    m = _NRIC_REGEX.search(text or '')
    return m.group(1) if m else ''


# MyKad header / label phrases printed on every card — never a person's name.
# Without this, _extract_name's "longest all-caps line" heuristic can grab a card
# label (e.g. "WARGANEGARA MALAYSIA", longer than a short name) instead of the
# name. A line made up ENTIRELY of these tokens is a label, so it's skipped.
_MYKAD_HEADER_TOKENS = frozenset({
    'KAD', 'PENGENALAN', 'MYKAD', 'MALAYSIA', 'WARGANEGARA',
    'LELAKI', 'PEREMPUAN', 'ISLAM',
})


def _extract_name(text: str, nric_match_str: str = '') -> str:
    """Best-effort: the longest line of ALL-CAPS letters (a typical MyKad
    rendering of the name), excluding the card's own header/label lines.
    Returns '' if no candidate found."""
    if not text:
        return ''
    best = ''
    for raw in text.splitlines():
        line = raw.strip()
        # MyKad names are uppercase letters + spaces + parentage markers.
        if not line or any(ch.isdigit() for ch in line):
            continue
        # Skip the NRIC line and short labels.
        if nric_match_str and nric_match_str in line:
            continue
        if len(line) < 6:
            continue
        letters = sum(1 for ch in line if ch.isalpha())
        if letters < 4 or letters / max(len(line), 1) < 0.6:
            continue
        # Skip MyKad header/label lines (e.g. "KAD PENGENALAN", "WARGANEGARA
        # MALAYSIA") — a line whose every word is a known card label is not a name.
        words = [w for w in re.split(r'[^A-Za-z]+', line) if w]
        if words and all(w.upper() in _MYKAD_HEADER_TOKENS for w in words):
            continue
        if line.upper() == line and len(line) > len(best):
            best = line
    return best


_MY_POSTCODE = re.compile(r'\b\d{5}\b')

# Words that prefix any MyKad address line — drop them so the displayed value
# is just the address itself. Case-insensitive, anchored at the start of a line.
_ADDRESS_PREFIX_NOISE = re.compile(
    r'^(alamat|address)\s*[:\-]?\s*',
    flags=re.IGNORECASE,
)

# The 13 Malaysian states + 3 federal territories, as printed on MyKad
# (uppercase, sometimes with the `W.P.` prefix). Matched against the line
# directly after the postcode to pull the state through the "looks like a
# one-word name" filter without false positives.
_MY_STATES = frozenset({
    'JOHOR', 'KEDAH', 'KELANTAN', 'MELAKA', 'NEGERI SEMBILAN',
    'PAHANG', 'PERAK', 'PERLIS', 'PULAU PINANG', 'SABAH',
    'SARAWAK', 'SELANGOR', 'TERENGGANU',
    'KUALA LUMPUR', 'PUTRAJAYA', 'LABUAN',
    'W.P. KUALA LUMPUR', 'W.P. PUTRAJAYA', 'W.P. LABUAN',
    'WP KUALA LUMPUR', 'WP PUTRAJAYA', 'WP LABUAN',
})


def _is_likely_state(ln: str) -> bool:
    """True iff ``ln`` reads as a Malaysian state line on a MyKad."""
    upper = ln.strip().upper()
    return upper in _MY_STATES


def _extract_address(text: str) -> str:
    """
    Best-effort MyKad address extraction. The MyKad front shows the holder's
    registered home address as 3 lines: street, ``<5-digit postcode> <city>``,
    and ``<state>``. Strategy: find the line containing a 5-digit Malaysian
    postcode; walk UP to gather the 1-2 preceding address lines, and also
    pick up the very next line if it matches a known Malaysian state.
    Returns ``''`` when no postcode-anchored block is found.

    Soft signal only — admin can spot e.g. an outdated registered address that
    differs from what the student typed in the Story tab. No verdict computed.
    """
    if not text:
        return ''
    lines = [ln.strip() for ln in text.splitlines()]
    # Find the postcode line.
    postcode_idx = -1
    for i, ln in enumerate(lines):
        if not ln:
            continue
        m = _MY_POSTCODE.search(ln)
        if m:
            postcode_idx = i
            break
    if postcode_idx < 0:
        return ''
    block: list[str] = []
    # Walk up at most 4 lines (address block can be 3-4 lines: street +
    # taman/kampung + postcode/city + state). The state line is captured
    # separately below (it lives BELOW the postcode line).
    for j in range(max(0, postcode_idx - 4), postcode_idx + 1):
        ln = lines[j]
        if not ln:
            continue
        # Skip the NRIC line.
        if _NRIC_REGEX.search(ln):
            continue
        # Skip the name line. We identify it by the presence of a Malaysian
        # parentage marker (A/L, A/P, BIN, BINTI, S/O, D/O, @) — addresses
        # never have these. NOTE: this misses Chinese names without markers
        # (e.g. "TAN AH KAU") which would slip into the address; acceptable
        # soft-signal noise. The earlier "all-caps no-digits → drop" filter
        # was too aggressive — it dropped legit address lines like
        # "TAMAN SEMANGAT" / "KAMPUNG ABC" / "BANDAR XYZ".
        if _NAME_NOISE.search(ln):
            continue
        # Strip a leading "Alamat" / "Address" label if Vision read one.
        ln = _ADDRESS_PREFIX_NOISE.sub('', ln).strip()
        if ln:
            block.append(ln)
    # Look one line DOWN for the state (MyKad puts it right after the postcode).
    if postcode_idx + 1 < len(lines):
        next_ln = lines[postcode_idx + 1].strip()
        if next_ln and _is_likely_state(next_ln):
            block.append(next_ln)
    # Deduplicate while preserving order (Vision occasionally repeats a line).
    seen: set = set()
    deduped: list[str] = []
    for ln in block:
        key = ln.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ln)
    return ', '.join(deduped)


def extract_mykad(image_bytes: bytes) -> dict:
    """
    Call Google Cloud Vision DOCUMENT_TEXT_DETECTION on the given image bytes
    and return ``{'nric': str, 'name': str, 'address': str, 'error': None}`` on
    success or the same shape with an ``error`` string otherwise. Never raises.
    """
    if not image_bytes:
        return {'nric': '', 'name': '', 'address': '', 'error': 'empty image'}
    try:
        from google.cloud import vision  # type: ignore
    except ImportError:
        return {'nric': '', 'name': '', 'address': '', 'error': 'AI module not installed'}

    api_key = getattr(settings, 'GOOGLE_CLOUD_VISION_API_KEY', '') or ''
    try:
        if api_key:
            client = vision.ImageAnnotatorClient(client_options={'api_key': api_key})
        else:
            # Falls back to Application Default Credentials (Cloud Run runtime SA).
            client = vision.ImageAnnotatorClient()
        image = vision.Image(content=image_bytes)
        resp = client.document_text_detection(image=image)
        if resp.error and resp.error.message:
            return {'nric': '', 'name': '', 'address': '', 'error': resp.error.message[:200]}
        text = resp.full_text_annotation.text if resp.full_text_annotation else ''
    except Exception as e:  # noqa: BLE001 — graceful: never propagate to a 500
        logger.warning('Vision OCR failed: %s', e)
        return {'nric': '', 'name': '', 'address': '', 'error': str(e)[:200]}

    nric = _extract_nric(text)
    return {
        'nric': nric,
        'name': _extract_name(text, nric),
        'address': _extract_address(text),
        'error': None,
    }


def _fetch_image_bytes(storage_path: str) -> Optional[bytes]:
    """Download the IC image from Supabase Storage. Returns None on failure."""
    if not storage_path:
        return None
    try:
        from urllib.request import urlopen
        from .storage import create_signed_download_url
        url = create_signed_download_url(storage_path)
        if not url:
            return None
        with urlopen(url, timeout=10) as r:
            return r.read()
    except Exception as e:  # noqa: BLE001
        logger.warning('IC image fetch failed for %s: %s', storage_path, e)
        return None


def run_vision_for_document(doc) -> dict:
    """
    Run Vision on an ``ApplicantDocument`` (expected ``doc_type='ic'``) and
    persist the result on the row. Returns the result dict. Never raises;
    failures land in ``vision_error`` and the doc still saves.
    """
    image = _fetch_image_bytes(doc.storage_path)
    if image is None:
        result = {'nric': '', 'name': '', 'address': '', 'error': 'could not fetch image'}
    else:
        result = extract_mykad(image)
    doc.vision_nric = result['nric'] or ''
    doc.vision_name = result['name'] or ''
    doc.vision_address = result.get('address', '') or ''
    doc.vision_error = result['error'] or ''
    doc.vision_run_at = timezone.now()
    doc.save(update_fields=['vision_nric', 'vision_name', 'vision_address', 'vision_error', 'vision_run_at'])
    return result


# ── Generic supporting-document soft checks (S: results slip / income / bills) ──
# Arbitrary documents aren't MyKad-structured, so instead of field extraction we
# do a *presence* check on the full OCR text: does an expected name (or address)
# appear anywhere? Tolerant + naturally soft — exactly right for a non-blocking
# nudge to the student + the interviewer.

def extract_text(image_bytes: bytes) -> dict:
    """Generic full-text OCR (no MyKad parsing). ``{'text': str, 'error': str|None}``.
    Never raises."""
    if not image_bytes:
        return {'text': '', 'error': 'empty image'}
    try:
        from google.cloud import vision  # type: ignore
    except ImportError:
        return {'text': '', 'error': 'AI module not installed'}
    api_key = getattr(settings, 'GOOGLE_CLOUD_VISION_API_KEY', '') or ''
    try:
        client = (vision.ImageAnnotatorClient(client_options={'api_key': api_key})
                  if api_key else vision.ImageAnnotatorClient())
        resp = client.document_text_detection(image=vision.Image(content=image_bytes))
        if resp.error and resp.error.message:
            return {'text': '', 'error': resp.error.message[:200]}
        return {'text': resp.full_text_annotation.text if resp.full_text_annotation else '', 'error': None}
    except Exception as e:  # noqa: BLE001 — graceful: never propagate to a 500
        logger.warning('Vision OCR (text) failed: %s', e)
        return {'text': '', 'error': str(e)[:200]}


def name_present(text: str, names) -> bool:
    """True if any of ``names`` (token-set, MyKad connectors stripped) is fully
    contained in the OCR ``text``. Order / case / extra words in the doc are fine."""
    text_tokens = _canonical_name_tokens(text)
    if not text_tokens:
        return False
    for n in names:
        nt = _canonical_name_tokens(n)
        if nt and nt.issubset(text_tokens):
            return True
    return False


def address_present(text: str, *, postcode: str = '', city: str = '') -> bool:
    """Soft home-address presence for utility bills. Postcode is the strong signal:
    if the 5-digit postcode appears in the doc AND the city token appears, call it
    found. With no postcode on file, require the city token alone (weak but soft)."""
    text_tokens = _canonical_name_tokens(text)
    city_ok = bool(city) and _canonical_name_tokens(city).issubset(text_tokens)
    pc = re.sub(r'\D', '', postcode or '')
    if pc:
        return pc in re.sub(r'\D', '', text or '') and (city_ok or not city)
    return city_ok


def run_vision_match_for_document(doc, *, names, postcode='', city='', check_address=False) -> dict:
    """OCR a supporting document and record soft verdicts: does an expected name
    appear (``vision_name_match``), and — for bills — does the home address appear
    (``vision_address_match``)? Verdicts: 'found' / 'not_found' / 'unreadable'.
    Never blocks, never raises."""
    image = _fetch_image_bytes(doc.storage_path)
    r = {'text': '', 'error': 'could not fetch image'} if image is None else extract_text(image)
    if r['error'] or not (r['text'] or '').strip():
        doc.vision_name_match = 'unreadable'
        doc.vision_address_match = 'unreadable' if check_address else ''
        doc.vision_error = r['error'] or 'no text read'
    else:
        doc.vision_name_match = 'found' if name_present(r['text'], names) else 'not_found'
        doc.vision_address_match = (
            ('found' if address_present(r['text'], postcode=postcode, city=city) else 'not_found')
            if check_address else ''
        )
        doc.vision_error = ''
    doc.vision_run_at = timezone.now()
    doc.save(update_fields=['vision_name_match', 'vision_address_match', 'vision_error', 'vision_run_at'])
    return {'name_match': doc.vision_name_match, 'address_match': doc.vision_address_match, 'error': doc.vision_error}
