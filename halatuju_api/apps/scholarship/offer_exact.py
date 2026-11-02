"""The Exact offer read — the ONE entry point for the fixed-format reader (offer exact-read S5, 2026-11-03).

`vision._run_field_extraction_impl` (upload, Re-run, sweep, `reextract_documents`, `release-decisions`) calls
`exact_offer_read`; the eval (`offer_replay`, `offer_parse_check`) calls `exact_read` with what production
would derive. Each returns the stored-read dict, or None (→ the AI reader, `offer_reader`). Three steps:

  1. **Parse** (`offer_parse.parse_govt_offer`) the text production holds. The identity comes from PAGE 1
     only (owner rule 2026-11-01), from the SAME source as the body (review H1):
       * the text is a digital PDF's own text layer → page 1's layer; when page 1 has NO usable layer (a
         scanned page 1 in front of digital pages) there is no page-1 identity to read → None (review H2);
         and when page 1's identity and the whole layer's disagree → None;
       * otherwise (a photo, a scan: Vision read page 1 only) → that text itself, never a PDF layer.
  2. **The IC guard** (`offer_ic.guard_nric`, exactly as on the AI path, with the profile IC and the page-1
     text): the parser labels its IC source (`label` for "No. Kad Pengenalan:", "K/P:", the polytechnic
     "NAME (IC)" line; `other` for the first-IC-anywhere fallback, corroborate-only). **A blanked IC means NO
     lock**: a blank IC merged over a prior read would keep the prior AI number under an "Exact" chip, and
     the AI read has its own guard. No text-layer backstop here (the parser either read an IC or did not lock).
  3. **The merge** over the prior read. The parser OWNS the identity and shape keys (`OWNED`) and writes them
     whole, blank included, so a stale AI campus / code / IC source / address / venue cannot survive under an
     "Exact" chip (review L2). The reporting date (with its label) and the offer date keep merge-preserve
     (decision 2026-07-10): a blank keeps the prior value — the reporting-date bonus depends on it — and so
     does a parser date `pathway_engine.parse_reporting_date` cannot read when the prior one it can (M4).
"""
from __future__ import annotations

#: The keys the parser owns — written whole on a lock, blank or not. The last five are AI-only fields the
#: parser never reads (review L2): blank under an Exact read; every reader takes them with `or ''`.
OWNED = ('candidate_name', 'candidate_nric', 'candidate_nric_source', 'programme', 'programme_code',
         'institution', 'campus', 'stream', 'intake', 'issuer', '_offer_parser_version',
         'candidate_address', 'reporting_venue', 'aliran', 'bidang_pengkhususan', 'elektif')
#: Merge-preserve: the parser's value wins only when it read one (the label travels with its date).
PRESERVED = (('reporting_date', 'reporting_date_label'), ('offer_date',))


def pdf_layers(image, content_type='') -> tuple:
    """(the whole usable text layer, page 1's usable layer) of a digital PDF — what `vision.ocr_document_full`
    reads first — or ('', '') for a photo, a scan or no image."""
    if image is None:
        return '', ''
    from . import vision
    from .pdf_pages import pdf_page_texts, pdf_text_layer, usable_text_layer
    if not vision._is_pdf(content_type, image):
        return '', ''
    pages = pdf_page_texts(image, 1)
    return usable_text_layer(pdf_text_layer(image)), (usable_text_layer(pages[0]) if pages else '')


def page1_text_layer(image, content_type='') -> str:
    """A digital PDF's page-1 text layer ('' for a photo, a scan, or no usable layer)."""
    return pdf_layers(image, content_type)[1]


def _reads(date) -> bool:
    from .pathway_engine import parse_reporting_date
    return parse_reporting_date(date) is not None


def merge_over(prior_fields, govt: dict) -> dict:
    """The lock merged over the prior read: `OWNED` whole, `PRESERVED` only where the parser read it — and a
    reporting date only when it parses, or the prior one does not (review M4)."""
    out = dict(prior_fields) if isinstance(prior_fields, dict) else {}
    out.update({k: govt.get(k, '') or '' for k in OWNED})
    for group in PRESERVED:
        mine = (govt.get(group[0]) or '').strip()
        if not mine:
            continue
        if group[0] == 'reporting_date' and not _reads(mine) and _reads(out.get('reporting_date')):
            continue
        out.update({k: govt.get(k, '') or '' for k in group})
    return out


def exact_read(text, *, from_text_layer=False, page1_layer='', prior=None, profile_nric='') -> dict | None:
    """The Exact read from what production derived: ``from_text_layer`` — ``text`` is a digital PDF's own
    text layer — and that PDF's ``page1_layer``. ``prior`` is the stored ``vision_fields``."""
    from .offer_ic import guard_nric
    from .offer_parse import parse_govt_offer
    if from_text_layer and not (page1_layer or '').strip():
        return None                              # page 1 is a scan: no page-1 identity to read (H2)
    page1 = page1_layer if from_text_layer else ''
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


def exact_offer_read(text, *, prior=None, image=None, content_type='', profile_nric='',
                     page1_ocr='') -> dict | None:
    """Production's Exact read → ``{fields, warnings, error, capture, offer_reader_inputs}``, or None (→ AI).
    ``text`` came from the PDF's text layer exactly when it IS that layer (`vision.ocr_document_full`'s
    rule); ``page1_ocr`` is accepted for `vision._offer_context`'s shape and not read."""
    layer, page1 = pdf_layers(image, content_type)
    from_layer = bool(layer.strip()) and layer.strip() == (text or '').strip()
    return exact_read(text, from_text_layer=from_layer, page1_layer=page1, prior=prior, profile_nric=profile_nric)
