"""TD-740: where pdfium places each text object, for the pdfium child (`pdfium_worker._paints`).

pypdf reads every string a page shows, wherever it is placed; pdfium draws only what lies in the page box. So a
text object whose box reaches past the visible page box hides its page, judged on pdfium's OWN placement: the
object's box (`FPDFPageObj_GetBounds`, in the space of the form holding it; pdfium has already applied the form's
/Matrix there) taken through each enclosing form object's matrix (`FPDFPageObj_GetMatrix`: the CTM at its ``Do``)
into page space, against `FPDF_GetPageBoundingBox` (the CropBox cut to the MediaBox). /Rotate turns the picture,
not page space, so it needs nothing here.

Standard library only: the worker passes in its own ``pypdfium2.raw`` module as ``raw``, so pdfium stays in the child
(`test_no_request_path_module_opens_or_imports_pdfium`). `pdfium_worker` re-exports these names and loads this file
by path when it runs as a script (kept apart from the worker, which is at the line limit).
"""
import ctypes

#: How far (points) a text object's box may reach past the page box and still count as on the page, when its centre
#: is on the page. TD-740 measurement (870 fixtures, 917 read pages, docs/decisions.md 25 Nov): one genuine template
#: (6 files) has a 42-character line whose box reaches 1.9 pt past the right edge; the next reach is 44 pt (text
#: wholly off the page). A sliver narrower than this placed wholly off the page still has its centre off the page.
EDGE_PT = 3.0
IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def page_box(raw, page) -> tuple:
    """(left, bottom, right, top) of the box pdfium draws, in page space; ValueError when pdfium cannot give it."""
    box = raw.FS_RECTF()
    if not raw.FPDF_GetPageBoundingBox(page, ctypes.byref(box)):
        raise ValueError('pdfium gives no page box')
    return (min(box.left, box.right), min(box.bottom, box.top), max(box.left, box.right), max(box.bottom, box.top))


def bounds(raw, obj) -> tuple:
    """(left, bottom, right, top) of a page object in the space of its holder; ValueError when pdfium cannot give it."""
    v = [ctypes.c_float() for _ in range(4)]
    if not raw.FPDFPageObj_GetBounds(obj, *(ctypes.byref(x) for x in v)):
        raise ValueError('pdfium gives no object box')
    return tuple(x.value for x in v)


def matrix(raw, obj) -> tuple:
    """A form object's matrix (a b c d e f): its space to its holder's; ValueError when pdfium cannot give it."""
    m = raw.FS_MATRIX()
    if not raw.FPDFPageObj_GetMatrix(obj, ctypes.byref(m)):
        raise ValueError('pdfium gives no form matrix')
    return (m.a, m.b, m.c, m.d, m.e, m.f)


def times(m: tuple, n: tuple) -> tuple:
    """m then n (row vectors, as PDF matrices): the matrix that maps through ``m`` and then through ``n``."""
    a, b, c, d, e, f = m
    return (a * n[0] + b * n[2], a * n[1] + b * n[3], c * n[0] + d * n[2], c * n[1] + d * n[3],
            e * n[0] + f * n[2] + n[4], e * n[1] + f * n[3] + n[5])


def through(box: tuple, m: tuple) -> tuple:
    """The box around ``box``'s four corners taken through ``m``."""
    l, b, r, t = box
    xs, ys = [], []
    for x in (l, r):
        for y in (b, t):
            xs.append(x * m[0] + y * m[2] + m[4])
            ys.append(x * m[1] + y * m[3] + m[5])
    return (min(xs), min(ys), max(xs), max(ys))


def outside(box: tuple, area: tuple) -> bool:
    """True when ``box`` reaches past ``area`` by more than `EDGE_PT` on any side, or its centre is not in ``area``
    (a small box wholly off the page, within `EDGE_PT` of the edge), or it is not a number at all."""
    reach = max(area[0] - box[0], area[1] - box[1], box[2] - area[2], box[3] - area[3])
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    on = reach <= EDGE_PT and area[0] <= cx <= area[2] and area[1] <= cy <= area[3]
    return not on                          # a NaN (an infinite matrix) is outside too
