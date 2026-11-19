"""The ONLY place the api runs pdfium (pypdfium2) on an upload: a short-lived CHILD process (S-visible fix round 8).

Run as ``python -I <this file>`` by `pdfium_run` — never imported with pdfium by the web process. It reads one
request from stdin (a JSON line, then the PDF's bytes), opens the PDF ONCE, runs each requested operation in order
and writes the answers to stdout (a JSON line, then the PNG bytes it names). Operations: ``count`` (pages),
``paints`` (pdf_pdfium_check's per-object painted-text check), ``render`` (each page its own PNG), ``stack`` (pages
stacked into one PNG), ``words`` (page 1's word boxes for the SPM certificate reader).

Why a child: rounds 5-7 modelled what pdfium costs (load whitelists, render caps) and ran it under one process-wide
lock, and every review still found a tiny crafted PDF that kept pdfium busy for 10-40 s — freezing every upload in
the gunicorn worker. Here a slow or crashing pdfium is killed at `pdfium_run.TIMEOUT_S` and its memory is capped
(Linux), so the worst case is one upload getting the safe answer. The module's top level imports only the standard
library: the web process imports it for `raster_scale` alone.
"""
import ctypes
import io
import json
import sys

#: Text render modes that paint (as ``pdf_pages._DRAWN_MODES``).
DRAWN_MODES = frozenset((0, 1, 2, 4, 5, 6))


def raster_scale(width_pt: float, height_pt: float, dpi: float, max_side_px: float, max_page_pt: float):
    """The render scale for a page: ``dpi``, shrunk so the longer side stays within ``max_side_px``; None for a page
    box that is empty or past ``max_page_pt`` (``pdf_pages.raster_scale`` passes its constants)."""
    longer = max(width_pt, height_pt)
    if not (width_pt > 0 and height_pt > 0) or longer > max_page_pt:
        return None
    return min(dpi / 72.0, max_side_px / longer)


# ── The painted-text check (moved from pdf_pdfium_check; the rules are its docstring's a-d) ──

class _OverObjects(Exception):
    pass


def _paints(pdf, index: int, has_alnum: bool, oc_may_be_off: bool, budget: list, plain: frozenset) -> bool:
    """True when every text object pdfium places on the page paints, outside optional content, and (when pypdf
    found letters or digits there) pdfium places at least one text object."""
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
                raise _OverObjects('past the pdfium page-object cap')
            for j in range(count):
                obj = raw.FPDFFormObj_GetObject(holder, j) if is_form else raw.FPDFPage_GetObject(holder, j)
                if not obj:
                    raise ValueError('pdfium lost a page object')
                kind = raw.FPDFPageObj_GetType(obj)
                if kind == raw.FPDF_PAGEOBJ_TEXT:
                    texts += 1
                    if (under_oc or _oc_marked(obj, oc_may_be_off, plain)
                            or raw.FPDFTextObj_GetTextRenderMode(obj) not in DRAWN_MODES):
                        return False
                elif kind == raw.FPDF_PAGEOBJ_FORM:
                    todo.append((obj, True, under_oc or _oc_marked(obj, oc_may_be_off, plain)))
        return texts > 0 or not has_alnum
    finally:
        page.close()


def _oc_marked(obj, oc_may_be_off: bool, plain: frozenset) -> bool:
    """True when a page object carries an ``OC`` mark that may hide it, or a mark pdfium cannot read."""
    import pypdfium2.raw as raw
    for m in range(raw.FPDFPageObj_CountMarks(obj)):
        mark = raw.FPDFPageObj_GetMark(obj, m)
        name = _mark_text(raw.FPDFPageObjMark_GetName, mark) if mark else None
        if name is None:
            return True
        if name != 'OC':
            continue
        keys = {_mark_text(raw.FPDFPageObjMark_GetParamKey, mark, k) for k in range(raw.FPDFPageObjMark_CountParams(mark))}
        if (oc_may_be_off or keys != plain
                or raw.FPDFPageObjMark_GetParamValueType(mark, b'Type') != raw.FPDF_OBJECT_NAME):
            return True
    return False


def _mark_text(call, mark, *index):
    """A mark's name or parameter key; None when pdfium cannot give it whole."""
    buf, size = ctypes.create_string_buffer(64), ctypes.c_ulong()
    if not call(mark, *index, buf, len(buf), ctypes.byref(size)) or size.value > len(buf):
        return None
    return buf.raw[:size.value].decode('utf-16-le', 'replace').rstrip('\x00')


# ── The operations ──

def _op_paints(pdf, req, blobs):
    """{hidden: [page index, ...]}: every judged page pdfium does not paint in full, or cannot judge."""
    pages = [(int(i), bool(a)) for i, a in req['pages']]
    if len(pdf) != req['count']:
        return {'hidden': [i for i, _ in pages]}
    budget, hidden, plain = [int(req['max_objects'])], [], frozenset(req['plain'])
    for i, has_alnum in pages:
        try:
            if not _paints(pdf, i, has_alnum, bool(req['oc_off']), budget, plain):
                hidden.append(i)
        except Exception:   # a page pdfium cannot judge is hidden (the object cap included)
            hidden.append(i)
    return {'hidden': hidden}


def _png(image) -> bytes:
    buf = io.BytesIO()
    image.convert('RGB').save(buf, format='PNG')
    return buf.getvalue()


def _op_render(pdf, req, blobs):
    """Each page in ``pages`` its own PNG, in order, stopping at the first page box out of bounds or failure
    (what was rendered before it is kept). Nothing when pdfium sees another page count than pypdf."""
    out = {'pngs': [], 'stop': None}
    if len(pdf) == 0 or len(pdf) != req['count']:
        out['stop'] = 'page count'
        return out
    for i in req['pages']:
        try:
            page = pdf[i]
            width, height = page.get_width(), page.get_height()
            scale = raster_scale(width, height, *req['scale'])
            if scale is None:
                out['stop'] = 'page box %.0f x %.0f pt' % (width, height)
                break
            blobs.append(_png(page.render(scale=scale).to_pil()))
            out['pngs'].append(len(blobs) - 1)
        except Exception as e:   # the rest of the pages are not rendered; the caller logs it
            out['stop'] = type(e).__name__
            break
    return out


def _op_stack(pdf, req, blobs):
    """{png: blob index or None}: ``pages`` rendered to ONE vertical PNG within the pixel budget."""
    from PIL import Image
    indices = list(req['pages'])
    if len(pdf) == 0 or len(pdf) != req['count']:
        return {'png': None}
    pages = {i: pdf[i] for i in indices}
    boxes = [(pages[i].get_width(), pages[i].get_height()) for i in indices]
    dpi, max_side, max_page = req['scale']
    if any(raster_scale(w, h, dpi, max_side, max_page) is None for w, h in boxes):
        return {'png': None}
    total_h = sum(h for _w, h in boxes)
    scale = min(dpi / 72.0, max_side / max(total_h, max(w for w, _h in boxes)))
    images = [pages[i].render(scale=scale).to_pil().convert('RGB') for i in indices]
    sheet = Image.new('RGB', (max(im.width for im in images), sum(im.height for im in images)), 'white')
    y = 0
    for im in images:
        sheet.paste(im, (0, y))
        y += im.height
    buf = io.BytesIO()
    sheet.save(buf, format='PNG')
    blobs.append(buf.getvalue())
    return {'png': len(blobs) - 1}


def _op_words(pdf, req, blobs):
    """{words: [...]}: page 1 of a digital PDF as word boxes in the Vision shape (top-left origin, points)."""
    page = pdf[0]
    height, tp = page.get_height(), page.get_textpage()
    out, cur = [], []

    def flush():
        if cur:
            le, bo = min(c[1] for c in cur), min(c[2] for c in cur)
            ri, to = max(c[3] for c in cur), max(c[4] for c in cur)
            out.append({'text': ''.join(c[0] for c in cur), 'cx': (le + ri) / 2,
                        'cy': height - (bo + to) / 2, 'h': to - bo, 'angle': 0.0})
            cur.clear()
    for i in range(tp.count_chars()):
        ch = tp.get_text_range(i, 1)
        if not ch or ch.isspace():
            flush()
            continue
        cur.append((ch, *tp.get_charbox(i)))
    flush()
    return {'words': out}


_OPS = {'count': lambda pdf, req, blobs: {'count': len(pdf)}, 'paints': _op_paints, 'render': _op_render,
        'stack': _op_stack, 'words': _op_words}


def _limit_memory(budget: int) -> None:
    """Linux: cap this process's address space at what it holds now (interpreter, pypdfium2, Pillow) plus
    ``budget`` bytes, so a PDF that asks pdfium for more fails here (MemoryError / a pdfium error -> the safe
    answer) instead of pushing the instance past its memory. Elsewhere (Windows dev and tests): no cap."""
    if not budget or not sys.platform.startswith('linux'):
        return
    import os
    import resource
    try:
        with open('/proc/self/statm') as fh:
            held = int(fh.read().split()[0]) * os.sysconf('SC_PAGE_SIZE')
        resource.setrlimit(resource.RLIMIT_AS, (held + budget, held + budget))
    except (OSError, ValueError):   # no /proc or a hard limit already lower: the time limit still holds
        pass


def main() -> int:
    raw_in = sys.stdin.buffer.read()
    head, _, data = raw_in.partition(b'\n')
    request = json.loads(head)
    del raw_in
    sys.modules['numpy'] = None            # pypdfium2 imports numpy only for to_numpy (never used): ~90 ms saved
    from PIL import Image
    Image.preinit()                        # Pillow's PNG writer loaded before the memory cap is set
    import pypdfium2 as pdfium
    _limit_memory(int(request.get('memory') or 0))
    blobs, results = [], []
    pdf = pdfium.PdfDocument(data)
    try:
        for op in request['ops']:
            results.append(_OPS[op['op']](pdf, op, blobs))
    finally:
        pdf.close()
    out = sys.stdout.buffer
    out.write(json.dumps({'results': results, 'blobs': [len(b) for b in blobs]}).encode() + b'\n')
    for b in blobs:
        out.write(b)
    out.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
