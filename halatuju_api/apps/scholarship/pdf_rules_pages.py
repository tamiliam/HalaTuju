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
