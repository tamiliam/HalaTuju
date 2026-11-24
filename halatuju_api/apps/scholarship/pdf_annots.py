"""OCR-20 (2026-11-24): annotations that paint over the page text (the "sticker" gap).

An annotation is drawn ON TOP of the page by the renderer (pdfium: the page image Vision and a person see), but
pypdf's text extraction never reads it. A /Square, /Stamp or /FreeText (or any annotation with an /AP appearance
stream, a /Link with one too) can paint a white box and the word FORGED over GENUINE, and the text layer still
reads GENUINE. pdfium also draws some annotations with NO /AP: it makes their appearance itself (a /Square with a
white /IC fill covers the text; a /Text note draws its icon). Probed 24 Nov (OCR-20).

Owner rule (strict; a refusal is safe and goes to the AI / Vision reader): a page's text is read only when every
annotation it lists is a /Link with no /AP — the one kind that paints nothing. Anything else hides the page
(`pdf_pages._page_visibility`): a missing, odd or non-name /Subtype, a /Link with an /AP key (any value), a
/Widget (form fields; /NeedAppearances or not), a /Popup, a hidden-flagged or optional-content annotation, a null
or non-dictionary entry, /Annots that is not an array (direct or indirect), and /Annots on any /Parent of the
page (neither reader inherits it today; a viewer may). The /Annots read goes through the `GateReader` (metered),
and the number of annotations is charged to the document budget BEFORE any entry is read. pdfium checks the same
rule on its own reading of each judged page (`pdfium_worker._plain_link`), so a disagreement is hidden too.
"""
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NullObject

#: Annotations listed on the walked pages of ONE document. Past it the PDF has no layer (the Vision route).
MAX_DOC_ANNOTS = 2_000
#: A /Parent chain longer than this is broken or hostile (as `pdf_pages._MAX_PARENT_DEPTH`).
_MAX_PARENT_DEPTH = 64


def _resolved(obj):
    return obj.get_object() if obj is not None else None


def _plain_link(entry) -> bool:
    """True only for a /Link annotation dictionary with no /AP key: it paints nothing over the page."""
    annot = _resolved(entry)
    if not isinstance(annot, DictionaryObject) or '/AP' in annot:
        return False
    subtype = _resolved(annot.get('/Subtype'))
    return isinstance(subtype, NameObject) and subtype == '/Link'


def annots_hide(page, budget) -> bool:
    """True when an annotation may paint over this page's text (the module rule), or that cannot be decided.
    ``budget``: the document's `pdf_pages._Budget`, charged one 'annotations' unit per listed entry before any
    is read (an over-budget raise is the caller's `OVER_BUDGET`)."""
    node = _resolved(page.get('/Parent'))
    for _ in range(_MAX_PARENT_DEPTH):
        if not isinstance(node, DictionaryObject):
            break
        if '/Annots' in node:
            return True
        node = _resolved(node.get('/Parent'))
    else:
        return True
    if '/Annots' not in page:
        return False
    annots = _resolved(page['/Annots'])
    if annots is None or isinstance(annots, NullObject):
        return False
    if not isinstance(annots, ArrayObject):
        return True
    budget.spend('annotations', len(annots))
    return not all(_plain_link(entry) for entry in annots)
