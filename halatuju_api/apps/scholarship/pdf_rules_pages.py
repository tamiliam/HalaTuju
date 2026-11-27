"""The page texts a RULES lane reads (the UMS offer reader, OCR-first S1 / S1c): split out of `pdf_pages`
(OCR-8, 2026-11-21, no behaviour change) when main's PDF safety fixes and these two readers together passed the
600-line limit. Both read through `pdf_pages` by module attribute, so its visible-page check (and a test's patch
of `pdf_pages.pdf_page_texts` or `pdf_pages._open_pdf`) applies here unchanged."""
import logging
import re
from collections import Counter

from . import pdf_pages, pdfium_run
from .pdf_layer_guards import page_tree_refusal

logger = logging.getLogger(__name__)


def pdf_rules_page_texts(data: bytes, max_pages: int) -> list:
    """`pdf_page_texts` for a rules lane (UMS, owner words review round 2): [] — no page texts, so no lock —
    when the PDF is encrypted or its page tree's counts disagree (`page_tree_refusal`), or it cannot be opened."""
    try:
        why = page_tree_refusal(pdf_pages._open_pdf(data))
    except Exception as e:  # unopenable is no page texts, so no lock
        why = f'unreadable ({type(e).__name__})'
    if why:
        logger.warning('PDF page tree refused for a rules lane: %s', why)
        return []
    return pdf_pages.pdf_page_texts(data, max_pages)


def pdf_page1_layout(data: bytes) -> str:
    """Page 1's text in LAYOUT order (pypdf ``extraction_mode='layout'``: a label and its value on one line,
    columns kept apart) — read by the UMS offer reader only (OCR-first S1, 2026-11-19), whose plain layer
    glues the name into the address. '' unless page 1 passes the same visibility check as its plain layer
    (`pdf_page_texts`) AND the layout holds exactly the same characters as that checked layer (spacing
    aside), so the layout can never show text the visible-page check did not see. Any failure is ''.
    Layout mode pads each line by x-position, so it runs in the pdfium CHILD (op ``layout``, review round 1)
    under its time limit, memory cap and the document's budget: no answer, no layout, no lock."""
    texts = pdf_pages.pdf_page_texts(data, 1)
    plain = texts[0] if texts else ''
    if not plain:
        return ''
    from .pdf_ink import ink_ops                 # S-visible 2: page 1's ink in the same child (`pdf_ink.page1_ink`)
    got = pdfium_run.ask(data, [{'op': 'layout'}] + ink_ops(data))
    layout = (got[0] or {}).get('text') if got else ''
    if not isinstance(layout, str) or not layout:
        return ''
    same = Counter(re.sub(r'\s', '', layout)) == Counter(re.sub(r'\s', '', plain))
    return layout if same else ''


#: OCR-14b-3: the operators a FULLY blank page may hold. Each paints nothing: graphics-state save, restore and
#: settings, colour choice and marked content. `Do` is allowed only for a Form XObject whose own operators pass the
#: same test. No text object (not even an empty BT/ET), no path, no paint, no shading, no image.
_PAINTS_NOTHING = frozenset((b'q', b'Q', b'cm', b'w', b'J', b'j', b'M', b'd', b'ri', b'i', b'g', b'G', b'rg', b'RG',
                             b'k', b'K', b'cs', b'CS', b'sc', b'scn', b'SC', b'SCN', b'BMC', b'BDC', b'EMC', b'MP',
                             b'DP'))


def fully_blank_page2(data: bytes, page_texts) -> bool:
    """True only when the letter's page 2 is FULLY blank (OCR-14b-3, the UniMAP excuse; owner decision B1, 27 Nov):
    its drawn text (``page_texts``, `pdf_rules_page_texts`) is '', the shared S-visible read judged it DRAWN with
    pypdf's raw text exactly '' (no whitespace run; pdfium placed no text object on it, `pdf_pdfium_check` rule f),
    the page lists no /Annots at all (not even a plain /Link or an empty list), and every operator on it, read by the
    shared parser (`pdf_pages._parsed_ops`, with its byte, token and operator guards and a budget), is one that paints
    nothing (`_PAINTS_NOTHING`; a Form XObject is walked, depth-bounded). Review round 1: then pdfium too, on its
    own, must see NO page object and no annotation on page 2 (the child's ``empty`` op, `pdfium_place.empty_pages`);
    no pdfium, a pdfium error or a spent budget (`pdfium_run.ask` None) is not blank. Any failure is False."""
    pages = list(page_texts or ())
    if len(pages) < 2 or pages[1] != '':
        return False
    try:
        read = pdf_pages._layer(data, 0)
        if not (read.visible and read.texts and len(read.seen) >= 2 and read.seen[1] == pdf_pages.DRAWN
                and read.texts[1] == ''):
            return False
        reader = pdf_pages._open_pdf(data)
        page = reader.pages[1]
        if '/Annots' in page:
            return False
        contents = page.get('/Contents')
        contents = contents.get_object() if contents is not None else None
        if not (pdf_pages._is_null(contents) or _paints_nothing(contents, pdf_pages._resources(page), reader, {},
                                                                pdf_pages._Budget(), 0)):
            return False
        answer = pdfium_run.ask(data, [{'op': 'empty', 'pages': [1], 'count': len(reader.pages)}])
        return bool(answer) and isinstance(answer[0], dict) and answer[0].get('empty') == [1]
    except Exception as e:  # undecidable is not blank: the page refuses as before
        logger.warning('PDF page 2 blank check failed: %s', e)
        return False


def _paints_nothing(content, resources, reader, cache: dict, budget, depth: int) -> bool:
    from pypdf.generic import StreamObject
    xobjects = pdf_pages._resolved(resources, '/XObject') if isinstance(resources, dict) else None
    for operands, operator in pdf_pages._parsed_ops(content, reader, cache, budget):
        if operator == b'Do':
            xobj = xobjects.get(operands[0]) if isinstance(xobjects, dict) and operands else None
            xobj = xobj.get_object() if xobj is not None else None
            if (not isinstance(xobj, StreamObject) or pdf_pages._resolved(xobj, '/Subtype') != '/Form'
                    or depth >= pdf_pages._MAX_FORM_DEPTH):
                return False
            budget.spend('operations', pdf_pages._DO_COST)
            if not _paints_nothing(xobj, pdf_pages._resources(xobj) or resources, reader, cache, budget, depth + 1):
                return False
        elif operator not in _PAINTS_NOTHING:
            return False
    return True
