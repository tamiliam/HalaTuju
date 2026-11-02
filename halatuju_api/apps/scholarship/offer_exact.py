"""The Exact offer read — the ONE entry point for the fixed-format reader (offer exact-read S5, 2026-11-03).

`vision._run_field_extraction_impl` (upload, Re-run, sweep, `reextract_documents`, `release-decisions`) and the
eval (`offer_replay`, `offer_parse_check`) call `exact_offer_read`; it returns the stored-read dict, or None
(→ the AI reader, `offer_reader`). Three steps:

  1. **Parse** (`offer_parse.parse_govt_offer`) the text production holds; the identity from PAGE 1 only (owner
     rule 2026-11-01) — a digital PDF's page-1 text layer, else the OCR text (Vision reads page 1 only).
  2. **The IC guard** (`offer_ic.guard_nric`, exactly as on the AI path, with the profile IC and the page-1
     text): the parser labels its IC source (`label` for "No. Kad Pengenalan:", "K/P:", the polytechnic
     "NAME (IC)" line; `other` for the first-IC-anywhere fallback, corroborate-only). **A blanked IC means NO
     lock**: a blank IC merged over a prior read would keep the prior AI number under an "Exact" chip, and
     the AI read has its own guard. No text-layer backstop here (the parser either read an IC or did not lock).
  3. **The merge** over the prior read. The parser OWNS the identity and shape keys (`OWNED`) and writes them
     whole, blank included, so a stale AI campus / code / IC source cannot survive under an "Exact" chip.
     The reporting date (with its label) and the offer date keep merge-preserve (decision 2026-07-10): a
     blank keeps the prior value — the reporting-date bonus depends on it.
"""
from __future__ import annotations

#: The keys the parser owns — written whole on a lock, blank or not.
OWNED = ('candidate_name', 'candidate_nric', 'candidate_nric_source', 'programme', 'programme_code',
         'institution', 'campus', 'stream', 'intake', 'issuer', '_offer_parser_version')
#: Merge-preserve: the parser's value wins only when it read one (the label travels with its date).
PRESERVED = (('reporting_date', 'reporting_date_label'), ('offer_date',))


def page1_text_layer(image, content_type='') -> str:
    """A digital PDF's page-1 text layer ('' for a photo, a scan, or no usable layer)."""
    if image is None:
        return ''
    from . import vision
    from .pdf_pages import pdf_page_texts, usable_text_layer
    if not vision._is_pdf(content_type, image):
        return ''
    pages = pdf_page_texts(image, 1)
    return usable_text_layer(pages[0]) if pages else ''


def merge_over(prior_fields, govt: dict) -> dict:
    """The lock merged over the prior read: `OWNED` whole, `PRESERVED` only where the parser read it."""
    out = dict(prior_fields) if isinstance(prior_fields, dict) else {}
    out.update({k: govt.get(k, '') or '' for k in OWNED})
    for group in PRESERVED:
        if (govt.get(group[0]) or '').strip():
            out.update({k: govt.get(k, '') or '' for k in group})
    return out


def exact_offer_read(text, *, prior=None, page1_text=None, image=None, content_type='',
                     profile_nric='', page1_ocr='') -> dict | None:
    """The Exact read → ``{fields, warnings, error, capture, offer_reader_inputs}``, or None (→ AI).
    ``prior`` is the document's stored ``vision_fields``; ``page1_text`` overrides the page-1 text (the
    eval passes the corpus's own); ``page1_ocr`` is accepted for `vision._offer_context`'s shape."""
    from .offer_ic import guard_nric
    from .offer_parse import parse_govt_offer
    page1 = page1_text if page1_text is not None else page1_text_layer(image, content_type)
    govt = parse_govt_offer(text, page1_text=page1 or None)
    if govt is None:
        return None
    govt.pop('_family', None)
    check = guard_nric(govt, profile_nric=profile_nric, page1_text=page1 or text or '')
    if not (govt.get('candidate_nric') or '').strip():
        return None
    prior_fields = prior.get('fields') if isinstance(prior, dict) else None
    return {'fields': merge_over(prior_fields, govt), 'warnings': [], 'error': '', 'capture': 'deterministic',
            'offer_reader_inputs': {'reader': 'deterministic', 'nric_check': check}}
