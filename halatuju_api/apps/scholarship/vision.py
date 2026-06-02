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
import json
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


# Parentage markers (A/L, A/P, S/O, D/O, BIN, BINTI) appear in the NAME on a MyKad
# and NEVER in the address — the strongest anchor for the name line. OCR sometimes
# spaces the slash, so tolerate "A / L".
_PARENTAGE_MARKER = re.compile(r'\b(a\s*/\s*[lp]|s\s*/\s*o|d\s*/\s*o|bin|binti)\b', re.IGNORECASE)


def _is_name_line(line: str) -> bool:
    """A plausible MyKad name line: all-caps letters + spaces (no digits), not a
    header/label, reasonable length."""
    if not line or len(line) < 6 or any(ch.isdigit() for ch in line):
        return False
    letters = sum(1 for ch in line if ch.isalpha())
    if letters < 4 or letters / max(len(line), 1) < 0.6:
        return False
    if line.upper() != line:
        return False
    words = [w for w in re.split(r'[^A-Za-z]+', line) if w]
    return not (words and all(w.upper() in _MYKAD_HEADER_TOKENS for w in words))


def _extract_name(text: str, nric_match_str: str = '') -> str:
    """Find the holder's name on a MyKad. Most-reliable strategy first:
      1. A line carrying a **parentage marker** (A/L, A/P, S/O, D/O, BIN, BINTI) —
         that is the name; addresses/localities never carry these. Fixes the old
         "longest all-caps line" trap where a locality like "TAMAN SRI LAYANG"
         out-ran the real name.
      2. Otherwise (e.g. a Chinese name with no marker) the first name-line right
         AFTER the NRIC line — the MyKad prints the name directly under the NRIC.
      3. Fallback: the longest all-caps name-line anywhere.
    Returns '' if nothing plausible is found."""
    if not text:
        return ''
    lines = [ln.strip() for ln in text.splitlines()]
    candidates = [ln for ln in lines
                  if _is_name_line(ln) and not (nric_match_str and nric_match_str in ln)]
    if not candidates:
        return ''
    marked = [ln for ln in candidates if _PARENTAGE_MARKER.search(ln)]
    if marked:
        return max(marked, key=len)
    nric_idx = next((i for i, ln in enumerate(lines) if _NRIC_REGEX.search(ln)), -1)
    if nric_idx >= 0:
        for ln in lines[nric_idx + 1:]:
            if ln in candidates:
                return ln
    return max(candidates, key=len)


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


# ── PDF document intake (document-intake hardening) ────────────────────────────
# Students upload scan-to-PDF (CamScanner) and native digital PDFs (EPF, payslip,
# offer letter). Google Vision's inline image OCR cannot decode PDF bytes ("Bad
# image data."), so we handle PDFs ourselves:
#   - DIGITAL PDF → read the embedded text layer (pypdf) — free, perfect fidelity.
#   - SCANNED PDF → rasterise page 1 (pypdfium2 + Pillow) → feed the image to Vision.
# Both libs are OPTIONAL: if absent (or the PDF is corrupt/encrypted), a PDF
# degrades to "unreadable" — today's behaviour — rather than crashing.
_PDF_MAGIC = b'%PDF-'
_MIN_PDF_TEXT = 25      # chars of real text → treat as a digital PDF (skip Vision)
_RASTER_DPI = 200


def _is_pdf(content_type: str, data: bytes) -> bool:
    if (content_type or '').lower().split(';')[0].strip() == 'application/pdf':
        return True
    return bool(data) and data[:5] == _PDF_MAGIC


def _pdf_text_layer(data: bytes) -> str:
    """The concatenated text layer of a PDF (all pages). '' if none / encrypted /
    library missing — caller then falls back to rasterise+OCR."""
    try:
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt('')
            except Exception:  # noqa: BLE001
                return ''
        return '\n'.join((p.extract_text() or '') for p in reader.pages).strip()
    except Exception as e:  # noqa: BLE001
        logger.warning('PDF text-layer extraction failed: %s', e)
        return ''


def _pdf_first_page_png(data: bytes) -> Optional[bytes]:
    """Rasterise page 1 of a PDF to PNG bytes (~200 DPI). None on failure /
    library missing. Page 1 only — bounds the Vision cost to 1 unit per doc."""
    try:
        import io

        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(data)
        try:
            if len(pdf) == 0:
                return None
            pil = pdf[0].render(scale=_RASTER_DPI / 72.0).to_pil()
            buf = io.BytesIO()
            pil.convert('RGB').save(buf, format='PNG')
            return buf.getvalue()
        finally:
            pdf.close()
    except Exception as e:  # noqa: BLE001
        logger.warning('PDF rasterise failed: %s', e)
        return None


def _vision_document_text(image_bytes: bytes) -> dict:
    """Google Vision DOCUMENT_TEXT_DETECTION on *image* bytes → ``{'text', 'error'}``.
    The single seam the OCR functions share (and tests patch). Graceful — returns
    an error dict, never raises. ``error`` is None on success."""
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
        logger.warning('Vision OCR failed: %s', e)
        return {'text': '', 'error': str(e)[:200]}


def extract_mykad(data: bytes, content_type: str = '') -> dict:
    """
    OCR a MyKad and return ``{'nric', 'name', 'address', 'error'}``. Accepts an
    image OR a PDF (a scanned MyKad — never a text PDF, so it is rasterised to an
    image first). Never raises.
    """
    if not data:
        return {'nric': '', 'name': '', 'address': '', 'error': 'empty image'}
    if _is_pdf(content_type, data):
        img = _pdf_first_page_png(data)
        if img is None:
            return {'nric': '', 'name': '', 'address': '', 'error': 'Bad image data.'}
        data = img
    r = _vision_document_text(data)
    if r['error']:
        return {'nric': '', 'name': '', 'address': '', 'error': r['error']}
    text = r['text']
    nric = _extract_nric(text)
    return {
        'nric': nric,
        'name': _extract_name(text, nric),
        'address': _extract_address(text),
        'error': None,
    }


def _fetch_image_bytes(storage_path: str) -> Optional[bytes]:
    """Download a document's raw bytes from Supabase Storage (image OR PDF).
    Returns None on failure."""
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
        result = extract_mykad(image, doc.content_type)
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

def extract_text(data: bytes, content_type: str = '') -> dict:
    """Generic full-text OCR. Accepts an image OR a PDF: a DIGITAL PDF is read via
    its text layer (no Vision call — free); a SCANNED PDF is rasterised (page 1) →
    Vision. ``{'text': str, 'error': str|None}``. Never raises."""
    if not data:
        return {'text': '', 'error': 'empty image'}
    if _is_pdf(content_type, data):
        text = _pdf_text_layer(data)
        if len(text) >= _MIN_PDF_TEXT:
            return {'text': text, 'error': None}   # digital PDF — no billable Vision call
        img = _pdf_first_page_png(data)
        if img is None:
            return {'text': '', 'error': 'Bad image data.'}
        data = img
    return _vision_document_text(data)


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


def ocr_document(doc) -> dict:
    """Fetch + OCR a document once. Returns {text, error}. Pass the result to
    run_vision_match_for_document / run_field_extraction_for_document as ``ocr=``
    so the same upload OCRs only once."""
    image = _fetch_image_bytes(doc.storage_path)
    return {'text': '', 'error': 'could not fetch image'} if image is None else extract_text(image, doc.content_type)


def run_vision_match_for_document(doc, *, names, postcode='', city='', check_address=False, ocr=None) -> dict:
    """OCR a supporting document and record soft verdicts: does an expected name
    appear (``vision_name_match``), and — for bills — does the home address appear
    (``vision_address_match``)? Verdicts: 'found' / 'not_found' / 'unreadable'.
    Never blocks, never raises. Pass ``ocr`` to reuse a prior OCR pass."""
    r = ocr if ocr is not None else ocr_document(doc)
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


# ── Document-assist: Gemini field extraction over messy supporting docs ────────
# Gemini PICKS the fields from arbitrary layouts (better than token-presence on
# the raw text); the deterministic matchers then DECIDE the verdict (so the
# student-facing verdict can never be a Gemini hallucination). Runs automatically
# on upload (see DocumentListCreateView), soft + never blocking.

GEMINI_EXTRACT_DOC_TYPES = frozenset({
    'salary_slip', 'epf', 'water_bill', 'electricity_bill', 'results_slip', 'offer_letter',
})

_STR = {'type': 'string'}


def _doc_schema(props: dict) -> dict:
    """An object schema with the given string fields + a shared warnings array."""
    out = dict(props)
    out['warnings'] = {'type': 'array', 'items': {'type': 'string'}}
    return {'type': 'object', 'properties': out}


_FIELD_SCHEMAS = {
    'salary_slip': _doc_schema({'name': _STR, 'employer': _STR, 'gross_income': _STR,
                                'net_income': _STR, 'period': _STR}),
    'epf': _doc_schema({'name': _STR, 'employer': _STR, 'latest_balance': _STR,
                        'last_contribution': _STR}),
    'water_bill': _doc_schema({'name': _STR, 'address': _STR, 'amount': _STR, 'billing_period': _STR}),
    'electricity_bill': _doc_schema({'name': _STR, 'address': _STR, 'amount': _STR, 'billing_period': _STR}),
    # S2: read the GRADE against each subject (not just the subject list) so the
    # academic engine can verify the typed grades against the slip.
    'results_slip': _doc_schema({'candidate_name': _STR, 'exam': _STR,
                                 'results': {'type': 'array', 'items': {'type': 'object',
                                             'properties': {'subject': _STR, 'grade': _STR}}}}),
    'offer_letter': _doc_schema({'candidate_name': _STR, 'institution': _STR,
                                 'programme': _STR, 'intake': _STR}),
}

# Which extracted field holds the person's name (for the deterministic verdict).
_NAME_FIELD = {
    'salary_slip': 'name', 'epf': 'name', 'water_bill': 'name', 'electricity_bill': 'name',
    'results_slip': 'candidate_name', 'offer_letter': 'candidate_name',
}

# Optional per-doc-type instruction appended to the extraction prompt.
_DOC_HINTS = {
    'results_slip': (' For "results", list EVERY subject row with its exact grade '
                     'as printed (e.g. A+, A, A-, B+, B, C+, C, D, E, G) — one entry '
                     'per subject.'),
}


def _call_gemini_json(prompt: str, schema: dict) -> dict:
    """Structured-output Gemini call → parsed JSON dict, or {'_error': msg}. This is
    the single seam tests @patch. Reuses profile_engine's model cascade + key guard."""
    api_key = getattr(settings, 'GEMINI_API_KEY', '') or ''
    if not api_key:
        return {'_error': 'AI service not configured (missing API key)'}
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return {'_error': 'AI module not installed'}
    from .profile_engine import MODEL_CASCADE
    client = genai.Client(api_key=api_key)
    last_error = None
    for model_name in MODEL_CASCADE:
        try:
            resp = client.models.generate_content(
                model=model_name, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json', response_schema=schema, temperature=0.1),
            )
            return json.loads(resp.text)
        except Exception as e:  # noqa: BLE001 — graceful: never propagate to a 500
            last_error = str(e)
            logger.warning('Gemini JSON call failed with %s: %s', model_name, e)
            continue
    return {'_error': f'All AI models failed: {last_error}'}


def extract_document_fields(ocr_text: str, doc_type: str) -> dict:
    """Gemini extracts the per-doc-type fields from a supporting doc's OCR text.
    Returns {fields, warnings, error}. No Gemini call when there's no text. Never raises."""
    schema = _FIELD_SCHEMAS.get(doc_type)
    if schema is None:
        return {'fields': {}, 'warnings': [], 'error': f'no extractor for {doc_type}'}
    if not (ocr_text or '').strip():
        return {'fields': {}, 'warnings': [], 'error': 'no text'}
    hint = _DOC_HINTS.get(doc_type, '')
    prompt = (
        f'Here is the OCR text from a Malaysian {doc_type.replace("_", " ")}. '
        'Extract the listed fields exactly as printed. If a field is missing or '
        'unclear, leave it empty and add a short note to "warnings". Do NOT invent '
        f'values.{hint}\n\nOCR TEXT:\n{(ocr_text or "")[:6000]}'
    )
    data = _call_gemini_json(prompt, schema)
    if '_error' in data:
        return {'fields': {}, 'warnings': [], 'error': data['_error']}
    warnings = data.pop('warnings', []) or []
    return {'fields': data, 'warnings': warnings, 'error': ''}


def _any_field_filled(fields: dict) -> bool:
    for v in fields.values():
        if isinstance(v, str):
            if v.strip():
                return True
        elif v:
            return True
    return False


def doc_student_verdict(doc_type, fields, *, names, postcode='', city='', check_address=False) -> str:
    """Deterministic verdict from the Gemini-extracted fields (never hallucinated):
    'ok' | 'name_mismatch' | 'address_mismatch' | 'wrong_doc'."""
    if not _any_field_filled(fields):
        return 'wrong_doc'   # nothing of the expected shape was found
    extracted_name = (fields.get(_NAME_FIELD.get(doc_type, 'name')) or '').strip()
    if extracted_name:
        matched = any(name_match(extracted_name, n) in ('match', 'partial') for n in names if n)
        if not matched:
            return 'name_mismatch'
    if check_address:
        addr = (fields.get('address') or '').strip()
        if addr and not address_present(addr, postcode=postcode, city=city):
            return 'address_mismatch'
    return 'ok'


def run_field_extraction_for_document(doc, *, names, postcode='', city='', check_address=False, ocr=None) -> dict:
    """Extract fields + a deterministic student-facing verdict, store on the doc.
    Never blocks, never raises. Pass ``ocr`` to reuse a prior OCR pass."""
    r = ocr if ocr is not None else ocr_document(doc)
    if r['error'] or not (r['text'] or '').strip():
        result = {'fields': {}, 'warnings': [], 'student_verdict': 'unreadable',
                  'error': r['error'] or 'no text read'}
    else:
        ex = extract_document_fields(r['text'], doc.doc_type)
        if ex['error']:
            result = {'fields': {}, 'warnings': [], 'student_verdict': 'unreadable', 'error': ex['error']}
        else:
            verdict = doc_student_verdict(doc.doc_type, ex['fields'], names=names,
                                          postcode=postcode, city=city, check_address=check_address)
            result = {'fields': ex['fields'], 'warnings': ex['warnings'],
                      'student_verdict': verdict, 'error': ''}
    doc.vision_fields = result
    doc.vision_fields_run_at = timezone.now()
    doc.save(update_fields=['vision_fields', 'vision_fields_run_at'])
    return result
