"""S-visible fix round 5 (2026-11-19): pdfium, the engine that PAINTS the page, judges each page pypdf read.

Four review rounds each found one more place where pypdf (which reads the text layer) and pdfium (which
paints the page image) parse one PDF differently, so pypdf extracted text pdfium never paints. The walk in
``pdf_pages`` mirrors pypdf and stays (defence in depth); this check closes the class by asking pdfium for its
OWN reading of every page whose pypdf text would be used. pdfium's page objects are walked (forms' contents
too, recursively), and the page is hidden (the Vision route) when:

a. any TEXT object has a render mode that does not paint (3, 7, or anything not 0-2 / 4-6);
b. any TEXT object, or a form object holding it, carries a marked-content mark named ``OC`` (pdfium's own
   view of optional content) — unless, exactly as the walk's ``oc_hides``, the mark is a plain /OCG (its
   parameters only Type, a name, and Name) and the document's configuration switches nothing off. One real
   genuine corpus document draws text in such a plain layer that is on, so "any OC mark" would push it off
   its free layer. An /OCMD, a /Usage, an unreadable mark: hidden;
c. pypdf extracted letters or digits from the page but pdfium finds NO text object on it at all;
d. pdfium cannot open the PDF, sees another page count, fails on the page, or the document's pages hold
   more than `MAX_OBJECTS` page objects between them.

Per OBJECT, not per character: a text-page character count was tried first and REJECTED — pdfium's text
page drops overlapping duplicate characters (a repeated draw, fake bold), so 6 real genuine documents lost
their free layer. Known limit: pdfium's API does not show a form XObject's own /OC entry; the walk judges it.
"""
import ctypes

from .pdf_layer_guards import PLAIN_OCG_KEYS, OverBudget
from .pdf_pdfium_load import load_check
from .pdfium_lock import pdfium_document

#: Page objects pdfium lists on the judged pages of ONE document, forms' contents included (each form call
#: is its own object tree). Corpus max (533 PDFs, measured 2026-11-19): 9,101 on one document (doc 1409:
#: 4,099). Past it every page still being judged is hidden.
MAX_OBJECTS = 20_000
#: Text render modes that paint (as in ``pdf_pages._DRAWN_MODES``).
_DRAWN_MODES = frozenset((0, 1, 2, 4, 5, 6))
#: The parameters of an OC mark for a provably shown /OCG (`pdf_layer_guards.PLAIN_OCG_KEYS`, unslashed).
_PLAIN_OCG_PARAMS = frozenset(k[1:] for k in PLAIN_OCG_KEYS)


def hidden_pages(data: bytes, page_count: int, judged: dict, oc_may_be_off: bool, reader=None) -> set:
    """The page indices in ``judged`` ({page index: pypdf's text of it}) that pdfium says do not paint all
    their text (a-d above; e, fix round 6: a page outside `pdf_pdfium_load`'s whitelist). A page whose pypdf text is blank is not judged: nothing of it is used. ALL judged
    pages are hidden when pdfium cannot open the PDF or sees another page count — never the hidden text.
    ``oc_may_be_off``: the document's optional-content configuration may switch a layer off
    (`pdf_layer_guards._doc_may_switch_off`). ``reader`` (fix round 6): pypdf's reader of ``data``; each page
    must first pass `pdf_pdfium_load.load_check` (its resources whitelisted and charged) or it is hidden and
    pdfium never loads it. pdfium runs under `pdfium_lock.PDFIUM_LOCK`, one document at a time."""
    wanted = {i: any(c.isalnum() for c in t) for i, t in judged.items() if t and not t.isspace()}
    hidden, state = set(), {}
    for i in list(wanted) if reader is not None else ():
        try:
            load_check(reader.pages[i], reader, state)
        except Exception:  # outside the whitelist or past the load budget: hidden, never loaded
            hidden.add(i)
            del wanted[i]
    if not wanted:
        return hidden
    budget = [MAX_OBJECTS]
    try:
        with pdfium_document(data) as pdf:
            if len(pdf) != page_count:
                return hidden | set(wanted)
            for i, has_alnum in wanted.items():
                try:
                    if not _paints(pdf, i, has_alnum, oc_may_be_off, budget):
                        hidden.add(i)
                except Exception:  # a page pdfium cannot judge is hidden (OverBudget included)
                    hidden.add(i)
    except Exception:  # pdfium cannot open what pypdf read: undecidable is hidden
        return hidden | set(wanted)
    return hidden


def _paints(pdf, index: int, has_alnum: bool, oc_may_be_off: bool, budget: list) -> bool:
    """True when every text object pdfium places on the page paints, outside optional content, and (when
    pypdf found letters or digits there) pdfium places at least one text object."""
    import pypdfium2.raw as raw
    page = pdf[index]
    try:
        texts, todo = 0, [(page.raw, False, False)]          # (page or form object, is a form, under an OC mark)
        while todo:
            holder, is_form, under_oc = todo.pop()
            count = raw.FPDFFormObj_CountObjects(holder) if is_form else raw.FPDFPage_CountObjects(holder)
            if count < 0:
                raise ValueError('pdfium cannot count the objects')
            budget[0] -= count
            if budget[0] < 0:
                raise OverBudget('past the pdfium page-object cap')
            for j in range(count):
                obj = raw.FPDFFormObj_GetObject(holder, j) if is_form else raw.FPDFPage_GetObject(holder, j)
                if not obj:
                    raise ValueError('pdfium lost a page object')
                kind = raw.FPDFPageObj_GetType(obj)
                if kind == raw.FPDF_PAGEOBJ_TEXT:
                    texts += 1
                    if (under_oc or _oc_marked(obj, oc_may_be_off)
                            or raw.FPDFTextObj_GetTextRenderMode(obj) not in _DRAWN_MODES):
                        return False
                elif kind == raw.FPDF_PAGEOBJ_FORM:
                    todo.append((obj, True, under_oc or _oc_marked(obj, oc_may_be_off)))
        return texts > 0 or not has_alnum
    finally:
        page.close()


def _oc_marked(obj, oc_may_be_off: bool) -> bool:
    """True when a page object carries an ``OC`` mark that may hide it (see b above), or a mark pdfium cannot
    read (undecidable)."""
    import pypdfium2.raw as raw
    for m in range(raw.FPDFPageObj_CountMarks(obj)):
        mark = raw.FPDFPageObj_GetMark(obj, m)
        name = _mark_text(raw.FPDFPageObjMark_GetName, mark) if mark else None
        if name is None:
            return True
        if name != 'OC':
            continue
        keys = {_mark_text(raw.FPDFPageObjMark_GetParamKey, mark, k) for k in range(raw.FPDFPageObjMark_CountParams(mark))}
        if (oc_may_be_off or keys != _PLAIN_OCG_PARAMS
                or raw.FPDFPageObjMark_GetParamValueType(mark, b'Type') != raw.FPDF_OBJECT_NAME):
            return True
    return False


def _mark_text(call, mark, *index):
    """A mark's name or parameter key; None when pdfium cannot give it whole."""
    buf, size = ctypes.create_string_buffer(64), ctypes.c_ulong()
    if not call(mark, *index, buf, len(buf), ctypes.byref(size)) or size.value > len(buf):
        return None
    return buf.raw[:size.value].decode('utf-16-le', 'replace').rstrip('\x00')
