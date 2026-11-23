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

import logging

logger = logging.getLogger(__name__)

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
    """True when `pathway_engine.parse_reporting_date` reads ``date`` (a stored value that is not a string
    — a damaged record — reads as no date, never an exception up through `vision`)."""
    from .pathway_engine import parse_reporting_date
    return isinstance(date, str) and parse_reporting_date(date) is not None


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


def _note_ums_refusal(why, text, reason: str) -> None:
    """Fill ``why`` (the caller's dict, or None) with the UMS rules read's refusal (review round 2): the
    lane and ``read_<reason>`` ('read_no_layout', 'read_not_an_offer', 'read_empty:programme', ...), the
    same shape as `rules_lane_verdict`'s ``rules_fallback``. Only a letter with the UMS title: a letter no
    rules lane exists for records nothing."""
    from .offer_parse_university import LANE, is_ums
    if isinstance(why, dict) and is_ums((text or '').upper()):
        why.update(lane=LANE, reason=f'read_{reason}')


def _guard_reason(d: dict) -> str:
    """`offer_parse.diagnose`'s refusal as one word: its guard, ``empty:<fields>``, 'portal' or 'no_title'."""
    if d.get('guard'):
        return d['guard']
    if d.get('empty_required'):
        return 'empty:' + ','.join(d['empty_required'])
    return 'portal' if d.get('portal') else 'no_title'


def exact_read(text, *, from_text_layer=False, page1_layer='', prior=None, profile_nric='',
               page1_layout='', why=None, page_texts=None) -> dict | None:
    """The Exact read from what production derived: ``from_text_layer`` — ``text`` is a digital PDF's own
    text layer — and that PDF's ``page1_layer`` (and its LAYOUT text, ``page1_layout``, which only the UMS
    family reads — OCR-first S1). ``prior`` is the stored ``vision_fields``. A university lock names its
    lane (``rules_lane``, e.g. 'ua:UMS') on the result and in ``offer_reader_inputs``; '' otherwise. When a
    UMS letter does not lock, ``why`` (a dict, if given) gets the lane and the reason (`_note_ums_refusal`),
    and the missing owner phrases' NUMBERS (``owner_words_missing``; never text). ``page_texts``: that PDF's
    drawn text per page (render-mode visible; `pdf_pages.pdf_page_texts`), read by the UMS family only (S1c
    owner words)."""
    from .offer_ic import guard_nric
    from .offer_parse import diagnose
    if from_text_layer and not (page1_layer or '').strip():
        _note_ums_refusal(why, text, 'no_page1_layer')
        return None                              # page 1 is a scan: no page-1 identity to read (H2)
    page1 = page1_layer if from_text_layer else ''
    d = diagnose(text, page1_text=page1 or None, page1_layout=page1_layout if from_text_layer else '',
                 page_texts=page_texts if from_text_layer else None)
    govt = d['locked']
    if govt is None:
        _note_ums_refusal(why, text, _guard_reason(d))
        if isinstance(why, dict) and why.get('reason') == 'read_owner_words_missing':
            why['owner_words_missing'] = list(d.get('owner_words_missing') or ())
        return None
    govt.pop('_family', None)
    lane = govt.pop('rules_lane', '')
    check = guard_nric(govt, profile_nric=profile_nric, page1_text=page1 or text or '')
    if not (govt.get('candidate_nric') or '').strip():
        _note_ums_refusal(why, text, 'nric_guard')
        return None
    prior_fields = prior.get('fields') if isinstance(prior, dict) else None
    inputs = {'reader': 'deterministic', 'nric_check': check, **({'rules_lane': lane} if lane else {})}
    return {'fields': merge_over(prior_fields, govt), 'warnings': [], 'error': '', 'capture': 'deterministic',
            'rules_lane': lane, 'offer_reader_inputs': inputs}


def ocr_first_lanes() -> tuple:
    """The rules lanes switched ON (OCR-first S1, 2026-11-19): the env var ``OCR_FIRST_LANES``, a comma
    list ("ua:UMS"); a test sets ``settings.OCR_FIRST_LANES``. Empty by default: every lane starts OFF and
    is switched on only after it passes Gate 1 on held-out letters (docs/plans/ocr-first-roadmap.md).
    Read here, not in settings/base.py, which is at its size allowance (`test_code_standards`)."""
    import os
    from django.conf import settings
    got = getattr(settings, 'OCR_FIRST_LANES', None)
    if got is None:
        got = os.environ.get('OCR_FIRST_LANES', '').split(',')
    return tuple(v.strip() for v in got if v and v.strip())


def rules_lane_verdict(ex) -> str:
    """Gate 2's last checks for a UNIVERSITY rules read (OCR-first S1): '' when its lane is switched on
    (`ocr_first_lanes`, default none) AND the catalogue pins exactly ONE course, at the letter's own level
    and at one campus (`offer_course_match.pinned_match`; the UPU code is extra evidence only). Else WHY
    the AI reads the letter instead: 'lane_off', 'match_<pinned_match reason>', or 'match_error' when the
    match raised (logged; review round 1). A government-family read (no ``rules_lane``) is unaffected."""
    lane = (ex or {}).get('rules_lane') or ''
    if not lane:
        return ''
    if lane not in ocr_first_lanes():
        return 'lane_off'
    try:
        from .offer_course_match import letter_institution, pinned_match, programme_line
        f = ex.get('fields') or {}
        reason, _match = pinned_match(programme_line(f.get('programme'), f.get('programme_code')),
                                      letter_institution(f.get('institution'), f.get('campus')), f.get('issuer') or '')
    except Exception:  # any fault in the match: the AI reads the letter, as it always could
        logger.exception('rules lane %s: the catalogue match failed; the AI reads the letter', lane)
        return 'match_error'
    return f'match_{reason}' if reason else ''


def _ums_family(text) -> bool:
    """True when `offer_parse.diagnose` reads ``text`` as a UMS letter (the SAME helper,
    `offer_parse.family_of`: no government family, and the UMS title). `exact_offer_read` uses it twice:
    with the lane off such a letter goes to the AI before the page-1 layout child or `read_ums` runs
    (recording 'lane_off', the reason `rules_lane_verdict` gave before review round 3); with the lane on,
    only such a letter gets the layout child (a government letter that also prints the UMS title does not)."""
    from .offer_parse import family_of
    return family_of(text) == 'ums'


def rules_lane_open(ex) -> bool:
    """True when a rules read may stand (`rules_lane_verdict` is ''); False sends the letter to the AI."""
    return rules_lane_verdict(ex) == ''


def exact_offer_read(text, *, prior=None, image=None, content_type='', profile_nric='',
                     page1_ocr='', why=None) -> dict | None:
    """Production's Exact read → ``{fields, warnings, error, capture, offer_reader_inputs}``, or None (→ AI).
    ``text`` came from the PDF's text layer exactly when it IS that layer (`vision.ocr_document_full`'s
    rule); ``page1_ocr`` is accepted for `vision._offer_context`'s shape and not read. ``why``: see
    `exact_read` (a UMS letter's refusal, for ``offer_reader_inputs['rules_fallback']``)."""
    if image is None and 'pdf' in (content_type or '').lower():
        _note_ums_refusal(why, text, 'no_pdf_bytes')
        return None                              # a PDF whose bytes are not here: no page 1 to read (H2)
    layer, page1 = pdf_layers(image, content_type)
    from_layer = bool(layer.strip()) and layer.strip() == (text or '').strip()
    from .offer_parse_university import LANE
    lane_on, ums = LANE in ocr_first_lanes(), _ums_family(text)
    if not lane_on and ums:                      # review round 3 (option A): no layout child, no read_ums
        if isinstance(why, dict):
            why.update(lane=LANE, reason='lane_off')
        return None
    layout, page_texts = '', None
    if lane_on and ums and from_layer and page1.strip():
        from .pdf_pages import MAX_LAYER_PAGES
        from .pdf_rules_pages import pdf_page1_layout, pdf_rules_page_texts
        layout, page_texts = pdf_page1_layout(image), pdf_rules_page_texts(image, MAX_LAYER_PAGES)
    ex = exact_read(text, from_text_layer=from_layer, page1_layer=page1, prior=prior, profile_nric=profile_nric,
                    page1_layout=layout, why=why, page_texts=page_texts)
    lane = (ex or {}).get('rules_lane') or ''
    if lane and lane in ocr_first_lanes() and from_layer:
        missing = _not_inked(ex, image, layout, lane)
        if missing:                              # S-visible 2: the visible page judges; the AI reads it
            if isinstance(why, dict):
                why.update(lane=lane, reason='not_inked', ink_missing=missing)
            return None
    return ex


def _not_inked(ex, image, layout, lane) -> list:
    """S-visible 2 (owner rule, 20 Nov: "the visible page always judges"): the labels (`pdf_ink.ink_missing`)
    of the owner phrases and values a rules lock on a TEXT-LAYER PDF relied on that leave no real ink on the
    rendered page 1; [] when every one does. A lane with no `ink_targets` reader, or any fault, refuses."""
    try:
        from .offer_parse_university import LANE, ink_targets
        from .pdf_ink import ink_missing, page1_ink
        if lane != LANE:
            return ['no_targets']
        phrases, values = ink_targets(ex.get('fields'), layout)
        return ink_missing(page1_ink(image), phrases, values, lane=lane)   # a Type3 font: `TYPE3_LANES`
    except Exception:  # fail closed: the AI reads the letter, as it always could
        logger.exception('rules lane %s: the ink check failed; the AI reads the letter', lane)
        return ['ink_error']
