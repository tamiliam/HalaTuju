"""Layer-A OCR capture for the eval corpus (billable, idempotent).

Reads every document in a fixtures folder the way PRODUCTION feeds the reader and caches the
result in snapshots/ (gitignored — real student documents, PII):

- ``<key>.ocr.txt``        the flattened text (all pages, page order).
- ``<key>.ocr.words.json`` per-page Vision word boxes, only when Vision was used.
- ``<key>.ocr.meta.json``  which path was used (``text_layer`` | ``vision``), pages, calls.

The path choice mirrors ``vision.ocr_document_full`` (apps/scholarship/vision.py ~L1187-1212):
a DIGITAL PDF whose text layer (pypdf, all pages — ``pdf_pages.pdf_text_layer``) holds at least
``_MIN_PDF_TEXT`` (25) characters is read from that layer for free, with no word boxes
(production's ``words`` is None). Anything else goes to Vision DOCUMENT_TEXT_DETECTION, whose
one response carries both the text and the word boxes (``vision._vision_words``). Production
rasterises only PAGE 1 of a scanned PDF; this capture OCRs every page (one Vision call each) so
later sprints can see the whole document — page 1 is always ``pages[0]`` in the words file, so
a replay can still feed the reader exactly what production sees. The rule is replicated here
rather than imported, because vision.py pulls Django settings at import.

Re-runs skip already-cached keys (a key counts as cached when its ``.ocr.txt`` exists), so each
document is billed at most once. The cached text is then replayed offline and free.

Credentials: GOOGLE_CLOUD_VISION_API_KEY from the environment, halatuju_api/.env or the repo
root .env (never on a command line); otherwise gcloud Application Default Credentials.

Usage (from halatuju_api/):
    python apps/scholarship/eval/capture_ocr.py                        # results_slip (default)
    python apps/scholarship/eval/capture_ocr.py ic                     # any doc_type folder
    python apps/scholarship/eval/capture_ocr.py results_split/stpm_cert   # nested, relative to fixtures/
"""
import glob
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))   # halatuju_api/
REPO = os.path.abspath(os.path.join(ROOT, '..'))                # repo root
SNAP = os.path.join(HERE, 'snapshots')

# Mirrors vision._MIN_PDF_TEXT and pdf_pages.RASTER_DPI / MAX_RASTER_SIDE_PX / MAX_PAGE_SIDE_PT.
MIN_PDF_TEXT = 25
RASTER_DPI = 200
MAX_RASTER_SIDE_PX = 4000
MAX_PAGE_SIDE_PT = 20000
PDF_MAGIC = b'%PDF-'


# ── Pure helpers (unit-tested in tests/test_capture_ocr.py) ──────────────────────────────────
def is_pdf(path: str, data: bytes) -> bool:
    """Same test as vision._is_pdf: the .pdf extension (stands in for content_type) or magic."""
    return path.lower().endswith('.pdf') or (bool(data) and data[:5] == PDF_MAGIC)


def choose_path(pdf: bool, text_layer: str) -> str:
    """'text_layer' for a digital PDF with enough real text, else 'vision' (ocr_document_full)."""
    return 'text_layer' if pdf and len(text_layer or '') >= MIN_PDF_TEXT else 'vision'


def raster_scale(width_pt: float, height_pt: float):
    """pdf_pages.raster_scale: 200 DPI, shrunk to the pixel budget; None for an absurd page."""
    longer = max(width_pt, height_pt)
    if not (width_pt > 0 and height_pt > 0) or longer > MAX_PAGE_SIDE_PT:
        return None
    return min(RASTER_DPI / 72.0, MAX_RASTER_SIDE_PX / longer)


def word_box(text: str, vertices) -> dict:
    """One word in production's shape (vision._vision_words): {text, cx, cy, h, angle}, plus
    the raw x0,y0,x1,y1 bounds. ``vertices`` is a list of (x, y)."""
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    angle = None
    if len(vertices) >= 2:
        angle = math.degrees(math.atan2(vertices[1][1] - vertices[0][1],
                                        vertices[1][0] - vertices[0][0]))
    return {'text': text, 'cx': sum(xs) / len(xs), 'cy': sum(ys) / len(ys),
            'h': max(ys) - min(ys), 'angle': angle,
            'x0': min(xs), 'y0': min(ys), 'x1': max(xs), 'y1': max(ys)}


def doc_folders(arg: str):
    """The folders a run reads: fixtures/<arg> and counter_examples/<arg> (arg may be nested)."""
    rel = arg.replace('\\', '/').strip('/')
    return [os.path.join(HERE, 'fixtures', *rel.split('/')),
            os.path.join(HERE, 'counter_examples', *rel.split('/'))]


# ── IO ───────────────────────────────────────────────────────────────────────────────────────
def _api_key():
    k = os.environ.get('GOOGLE_CLOUD_VISION_API_KEY', '').strip()
    if k:
        return k
    for envp in (os.path.join(ROOT, '.env'), os.path.join(REPO, '.env')):
        if os.path.exists(envp):
            for line in open(envp, encoding='utf-8'):
                line = line.strip()
                if line.startswith('GOOGLE_CLOUD_VISION_API_KEY='):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    return ''


def _pdf_text_layer(data: bytes) -> str:
    """pdf_pages.pdf_text_layer: all pages joined by newlines; '' on any failure."""
    try:
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt('')        # a failure here lands in the except below → ''
        return '\n'.join((p.extract_text() or '') for p in reader.pages).strip()
    except Exception:  # noqa: BLE001 — any unreadable PDF degrades to the Vision path
        return ''


def _pdf_page_pngs(data: bytes):
    """Every page as PNG bytes, rendered like pdf_pages.pdf_first_page_png (None = refused)."""
    import io
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(data)
    out = []
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            scale = raster_scale(page.get_width(), page.get_height())
            if scale is None:
                out.append(None)
                continue
            buf = io.BytesIO()
            page.render(scale=scale).to_pil().convert('RGB').save(buf, format='PNG')
            out.append(buf.getvalue())
    finally:
        pdf.close()
    return out


def _vision_page(client, vision, img: bytes) -> dict:
    resp = client.document_text_detection(image=vision.Image(content=img))
    if resp.error and resp.error.message:
        return {'text': '', 'words': [], 'error': resp.error.message[:200]}
    text = resp.full_text_annotation.text if resp.full_text_annotation else ''
    words = []
    for ann in resp.text_annotations[1:]:      # [0] is the whole text; [1:] are words
        vs = [(v.x, v.y) for v in ann.bounding_poly.vertices]
        if vs:
            words.append(word_box(ann.description, vs))
    return {'text': text, 'words': words, 'error': None}


def _client():
    from google.auth.exceptions import DefaultCredentialsError
    from google.cloud import vision
    key = _api_key()
    if key:
        print('Using GOOGLE_CLOUD_VISION_API_KEY.')
        return vision, vision.ImageAnnotatorClient(client_options={'api_key': key})
    try:                                  # fall back to gcloud Application Default Credentials
        c = vision.ImageAnnotatorClient()
        print('No API key found — using Application Default Credentials (gcloud).')
        return vision, c
    except DefaultCredentialsError as e:
        print(f'No API key in .env AND no ADC available ({type(e).__name__}). '
              'Either add GOOGLE_CLOUD_VISION_API_KEY to halatuju_api/.env, '
              'or run: gcloud auth application-default login')
        return vision, None


def capture_one(path, vision_mod, client):
    """Read one document. Returns (text, words_pages_or_None, meta, vision_calls)."""
    data = open(path, 'rb').read()
    pdf = is_pdf(path, data)
    layer = _pdf_text_layer(data) if pdf else ''
    route = choose_path(pdf, layer)
    if route == 'text_layer':
        return layer, None, {'path': 'text_layer', 'pages': None, 'vision_calls': 0}, 0
    images = _pdf_page_pngs(data) if pdf else [data]
    pages, texts, calls, errors = [], [], 0, []
    for i, img in enumerate(images, start=1):
        if img is None:
            errors.append(f'page {i}: raster refused')
            pages.append({'page': i, 'text': '', 'words': [], 'error': 'raster refused'})
            continue
        r = _vision_page(client, vision_mod, img)
        calls += 1
        if r['error']:
            errors.append(f"page {i}: {r['error']}")
        pages.append({'page': i, 'text': r['text'], 'words': r['words'], 'error': r['error']})
        texts.append(r['text'])
    meta = {'path': 'vision', 'pages': len(images), 'vision_calls': calls,
            'production_reads_page': 1, 'errors': errors}
    return '\n'.join(t for t in texts if t), pages, meta, calls


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    target = argv[0] if argv else 'results_slip'
    docs = []
    for folder in doc_folders(target):
        for p in sorted(glob.glob(os.path.join(folder, '*'))):
            if os.path.isfile(p) and not p.endswith('.gitkeep'):
                docs.append(p)
    pending = [p for p in docs if not os.path.exists(
        os.path.join(SNAP, os.path.basename(p).rsplit('.', 1)[0] + '.ocr.txt'))]
    vision_mod = client = None
    if pending:
        vision_mod, client = _client()
        if client is None:
            return
    done = failed = total_calls = 0
    for p in pending:
        key = os.path.basename(p).rsplit('.', 1)[0]   # full key incl. doc-type prefix
        try:
            text, pages, meta, calls = capture_one(p, vision_mod, client)
            total_calls += calls
            if meta.get('errors') and not text:
                failed += 1
                print(f"  FAIL {key}: {meta['errors'][0][:80]}")
                continue
            with open(os.path.join(SNAP, f'{key}.ocr.txt'), 'w', encoding='utf-8') as f:
                f.write(text)
            if pages is not None:
                with open(os.path.join(SNAP, f'{key}.ocr.words.json'), 'w', encoding='utf-8') as f:
                    json.dump({'pages': pages}, f, ensure_ascii=False)
            with open(os.path.join(SNAP, f'{key}.ocr.meta.json'), 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=1)
            done += 1
            print(f"  ocr {key} [{meta['path']}, {calls} call(s), {len(text)} chars]")
        except Exception as e:  # noqa: BLE001 — one bad file must not stop the batch
            failed += 1
            print(f'  FAIL {key}: {type(e).__name__}: {str(e)[:80]}')
    print(f'\nOCR capture: {done} new, {len(docs) - len(pending)} cached, {failed} failed '
          f'(of {len(docs)} docs). Vision calls made: {total_calls}.')


if __name__ == '__main__':
    main()
