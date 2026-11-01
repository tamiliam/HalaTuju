"""Layer-A OCR capture for the eval corpus (billable, idempotent).

Reads every document in a fixtures folder the way PRODUCTION feeds the reader and caches the
result in snapshots/ (gitignored — real student documents, PII):

- ``<key>.ocr.txt``        the flattened text (all pages, page order).
- ``<key>.ocr.words.json`` per-page Vision word boxes, only when Vision was used.
- ``<key>.ocr.meta.json``  which path was used (``text_layer`` | ``vision``), pages, calls.

The path choice mirrors ``vision.ocr_document_full`` (apps/scholarship/vision.py ~L1187-1212):
a DIGITAL PDF whose text layer (pypdf, all pages — ``pdf_pages.pdf_text_layer``) holds at least
``_MIN_PDF_TEXT`` (25) characters of REAL text — production's own ``pdf_pages.usable_text_layer``
(TD-411: a layer that is only a scanner app's stamp, "CamScanner", is no layer) — is read from that
layer for free, with no word boxes
(production's ``words`` is None). Anything else goes to Vision DOCUMENT_TEXT_DETECTION, whose
one response carries both the text and the word boxes (``vision._vision_words``). Production
rasterises only PAGE 1 of a scanned PDF; this capture OCRs every page (one Vision call each) so
later sprints can see the whole document — page 1 is always ``pages[0]`` in the words file, so
a replay can still feed the reader exactly what production sees. The rule is replicated here
rather than imported, because vision.py pulls Django settings at import. The PDF readers themselves
(text layer, raster scale) ARE production's own ``pdf_pages`` functions (Django-free), never a copy.

⚠ LIBRARY VERSIONS (2026-10-28). pypdf and pypdfium2 lay out a text layer differently from one
version to the next (pypdf 6.19 kept an STPM certificate's columns one item per line; production's
5.9.0 merges them). A cache captured under other versions describes a document production never
sees, so every run prints a WARNING when the installed versions differ from ``requirements.lock``.
``--recapture-text-layer`` rewrites every cached TEXT-LAYER read (meta ``text_layer``) under the
installed libraries — free, no Vision call; a doc whose layer would now route to Vision is reported
and left alone.

Re-runs skip already-cached keys (a key counts as cached when its ``.ocr.txt`` exists), so each
document is billed at most once. The cached text is then replayed offline and free.

Credentials: GOOGLE_CLOUD_VISION_API_KEY from the environment, halatuju_api/.env or the repo
root .env (never on a command line); otherwise gcloud Application Default Credentials.

A CORPUS FOLDER (offer exact-read S2, 2026-11-01). ``--corpus DIR`` reads the documents from
``DIR/fixtures/<target>`` and writes the caches to ``DIR/snapshots`` (e.g. the offer corpus
``fixtures/offer_letters_2026-11-01``). ``--reuse-from DIR`` takes an EARLIER capture
(``DIR/<key>.ocr.txt``) for a document that would otherwise need Vision: it is copied in with meta
``path: earlier_vision`` — the June/July 2026 capture OCR'd page 1 only (PyMuPDF raster, 2x), which
is the page production reads, so no second Vision call is made for it. A digital PDF always takes
its free text layer, whatever an earlier capture holds. ``--dry-run`` writes nothing and calls
nothing: it prints how many documents are cached, free (text layer), reusable (earlier capture) and
need Vision, with the Vision calls (one per page) and their cost.

Usage (from halatuju_api/):
    python apps/scholarship/eval/capture_ocr.py                        # results_slip (default)
    python apps/scholarship/eval/capture_ocr.py ic                     # any doc_type folder
    python apps/scholarship/eval/capture_ocr.py results_split/stpm_cert   # nested, relative to fixtures/
    python apps/scholarship/eval/capture_ocr.py results_split/stpm_cert --recapture-text-layer
    python -I apps/scholarship/eval/capture_ocr.py offer_letter \\
        --corpus apps/scholarship/eval/fixtures/offer_letters_2026-11-01 \\
        --reuse-from apps/scholarship/eval/snapshots --dry-run       # then again without --dry-run
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
LOCK = os.path.join(ROOT, 'requirements.lock')
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from apps.scholarship import pdf_pages  # noqa: E402 - production's own PDF readers (Django-free)

# Production's own threshold (vision._MIN_PDF_TEXT is this same constant).
MIN_PDF_TEXT = pdf_pages.MIN_TEXT_LAYER_CHARS
PDF_MAGIC = b'%PDF-'
PDF_LIBS = ('pypdf', 'pypdfium2')


# ── Pure helpers (unit-tested in tests/test_capture_ocr.py) ──────────────────────────────────
def is_pdf(path: str, data: bytes) -> bool:
    """Same test as vision._is_pdf: the .pdf extension (stands in for content_type) or magic."""
    return path.lower().endswith('.pdf') or (bool(data) and data[:5] == PDF_MAGIC)


def choose_path(pdf: bool, text_layer: str) -> str:
    """'text_layer' for a digital PDF with enough real text, else 'vision' (ocr_document_full).
    ``text_layer`` is the RAW layer; the TD-411 sanity check is applied here, as production does."""
    return 'text_layer' if pdf and len(usable_text_layer(text_layer or '')) >= MIN_PDF_TEXT else 'vision'


raster_scale = pdf_pages.raster_scale
usable_text_layer = pdf_pages.usable_text_layer   # TD-411 — production's own rule, never a copy


def locked_versions(lock_text: str) -> dict:
    """{library: pinned version} for the PDF libraries in a requirements.lock text."""
    out = {}
    for line in lock_text.splitlines():
        name, sep, ver = line.split('#', 1)[0].strip().partition('==')
        if sep and name.strip().lower() in PDF_LIBS:
            out[name.strip().lower()] = ver.strip()
    return out


def version_mismatches(installed: dict, locked: dict) -> list:
    """'lib installed X, requirements.lock Y' for each PDF library that differs (or is missing)."""
    return [f'{lib} installed {installed.get(lib)}, requirements.lock {locked[lib]}'
            for lib in PDF_LIBS if lib in locked and installed.get(lib) != locked[lib]]


def warn_on_version_drift():
    """Print a WARNING when the installed PDF libraries differ from requirements.lock."""
    from importlib import metadata
    installed = {}
    for lib in PDF_LIBS:
        try:
            installed[lib] = metadata.version(lib)
        except metadata.PackageNotFoundError:
            installed[lib] = None
    try:
        with open(LOCK, encoding='utf-8') as fh:
            locked = locked_versions(fh.read())
    except OSError:
        print(f'WARNING: {LOCK} not found - cannot check the PDF library versions.')
        return
    for msg in version_mismatches(installed, locked):
        print(f'WARNING: {msg} - text-layer caches will NOT match production.')


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


def doc_folders(arg: str, corpus: str = None):
    """The folders a run reads: fixtures/<arg> and counter_examples/<arg> (arg may be nested);
    with ``corpus``, only ``<corpus>/fixtures/<arg>``."""
    rel = arg.replace('\\', '/').strip('/')
    if corpus:
        return [os.path.join(corpus, 'fixtures', *rel.split('/'))]
    return [os.path.join(HERE, 'fixtures', *rel.split('/')),
            os.path.join(HERE, 'counter_examples', *rel.split('/'))]


#: Vision DOCUMENT_TEXT_DETECTION list price per page (the first 1,000 units a month are free).
VISION_USD_PER_PAGE = 1.50 / 1000
EARLIER_META = {'path': 'earlier_vision', 'pages': None, 'vision_calls': 0, 'production_reads_page': 1,
                'note': 'earlier capture (Jun/Jul 2026): Vision on page 1 only, PyMuPDF 2x raster'}


def doc_key(path: str) -> str:
    return os.path.basename(path).rsplit('.', 1)[0]


def _pdf_page_count(data: bytes):
    """Pages in a PDF (pypdfium2, as the raster uses), or None when it cannot be opened."""
    import pypdfium2 as pdfium
    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError:   # a broken file is counted, not fatal
        return None
    try:
        return len(pdf)
    finally:
        pdf.close()


def plan_one(path: str, snap: str, reuse_from: str = None) -> dict:
    """What a capture would do for one document — free, no call, nothing written:
    ``{'route': cached | text_layer | earlier | vision | unreadable, 'vision_calls': n}``.
    ``unreadable`` = a PDF that cannot be opened (Vision would get nothing to read)."""
    key = doc_key(path)
    if os.path.exists(os.path.join(snap, f'{key}.ocr.txt')):
        return {'route': 'cached', 'vision_calls': 0}
    with open(path, 'rb') as fh:
        data = fh.read()
    pdf = is_pdf(path, data)
    if choose_path(pdf, _pdf_text_layer(data) if pdf else '') == 'text_layer':
        return {'route': 'text_layer', 'vision_calls': 0}
    if reuse_from and os.path.exists(os.path.join(reuse_from, f'{key}.ocr.txt')):
        return {'route': 'earlier', 'vision_calls': 0}
    if not pdf:
        return {'route': 'vision', 'vision_calls': 1}
    pages = _pdf_page_count(data)
    return {'route': 'unreadable', 'vision_calls': 0} if not pages else {'route': 'vision',
                                                                         'vision_calls': pages}


def plan_summary(plans: list) -> dict:
    """Counts per route, Vision calls and their list-price cost (US$)."""
    routes = {}
    for p in plans:
        routes[p['route']] = routes.get(p['route'], 0) + 1
    calls = sum(p['vision_calls'] for p in plans)
    return {'docs': len(plans), 'routes': dict(sorted(routes.items())), 'vision_calls': calls,
            'vision_usd': round(calls * VISION_USD_PER_PAGE, 4)}


def reuse_earlier(key: str, snap: str, reuse_from: str) -> int:
    """Copy an earlier capture's text in as ``<key>.ocr.txt`` + an ``earlier_vision`` meta.
    Returns its length in characters."""
    with open(os.path.join(reuse_from, f'{key}.ocr.txt'), encoding='utf-8') as fh:
        text = fh.read()
    with open(os.path.join(snap, f'{key}.ocr.txt'), 'w', encoding='utf-8') as f:
        f.write(text)
    with open(os.path.join(snap, f'{key}.ocr.meta.json'), 'w', encoding='utf-8') as f:
        json.dump(EARLIER_META, f, indent=1)
    return len(text)


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


_pdf_text_layer = pdf_pages.pdf_text_layer   # production's own reader, all pages


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
        return usable_text_layer(layer), None, {'path': 'text_layer', 'pages': None, 'vision_calls': 0}, 0
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


def recapture_text_layer(docs, snap=SNAP):
    """Rewrite each cached TEXT-LAYER read under the installed libraries (free, no Vision)."""
    changed = same = skipped = 0
    for p in docs:
        key = os.path.basename(p).rsplit('.', 1)[0]
        meta_path = os.path.join(snap, f'{key}.ocr.meta.json')
        if not os.path.exists(meta_path):
            continue
        with open(meta_path, encoding='utf-8') as fh:
            if json.load(fh).get('path') != 'text_layer':
                continue
        with open(p, 'rb') as fh:
            layer = usable_text_layer(_pdf_text_layer(fh.read()))
        if choose_path(True, layer) != 'text_layer':
            skipped += 1
            print(f'  SKIP {key}: the layer would now route to Vision - cache left as it was')
            continue
        txt_path = os.path.join(snap, f'{key}.ocr.txt')
        old = open(txt_path, encoding='utf-8').read() if os.path.exists(txt_path) else None
        if old == layer:
            same += 1
            continue
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(layer)
        changed += 1
        print(f'  rewrote {key} [{len(layer)} chars]')
    print(f'\nText-layer recapture: {changed} rewritten, {same} unchanged, {skipped} skipped.')


def _flag_value(argv, name):
    """The value after ``name`` (``--x VALUE``), or None. Removes both from ``argv``."""
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            value = argv[i + 1]
            del argv[i:i + 2]
            return os.path.abspath(value)
        del argv[i]
    return None


def _print_plan(summary):
    r = summary['routes']
    print(f"\nDRY RUN (nothing written, no call made) - {summary['docs']} docs: "
          + '  '.join(f'{k} {v}' for k, v in r.items()))
    print(f"Vision needed for {r.get('vision', 0)} docs = {summary['vision_calls']} calls "
          f"(one per page) = about US${summary['vision_usd']:.3f} at list price "
          f"(inside the 1,000 free units a month).")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    corpus = _flag_value(argv, '--corpus')
    reuse_from = _flag_value(argv, '--reuse-from')
    flags = [a for a in argv if a.startswith('--')]
    argv = [a for a in argv if not a.startswith('--')]
    snap = os.path.join(corpus, 'snapshots') if corpus else SNAP
    warn_on_version_drift()
    target = argv[0] if argv else 'results_slip'
    docs = []
    for folder in doc_folders(target, corpus):
        for p in sorted(glob.glob(os.path.join(folder, '*'))):
            if os.path.isfile(p) and not p.endswith('.gitkeep'):
                docs.append(p)
    if '--recapture-text-layer' in flags:
        recapture_text_layer(docs, snap)
        return
    if '--dry-run' in flags:
        _print_plan(plan_summary([plan_one(p, snap, reuse_from) for p in docs]))
        return
    pending = [p for p in docs if not os.path.exists(os.path.join(snap, doc_key(p) + '.ocr.txt'))]
    reused = 0
    if reuse_from:   # an earlier capture stands in for Vision; a text layer still wins (free)
        still = []
        for p in pending:
            if plan_one(p, snap, reuse_from)['route'] == 'earlier':
                n = reuse_earlier(doc_key(p), snap, reuse_from)
                reused += 1
                print(f'  ocr {doc_key(p)} [earlier_vision, 0 calls, {n} chars]')
            else:
                still.append(p)
        pending = still
    vision_mod = client = None
    if any(plan_one(p, snap)['route'] != 'text_layer' for p in pending):
        vision_mod, client = _client()
        if client is None:
            return
    done = failed = total_calls = 0
    for p in pending:
        key = doc_key(p)   # full key incl. doc-type prefix
        try:
            text, pages, meta, calls = capture_one(p, vision_mod, client)
            total_calls += calls
            if meta.get('errors') and not text:
                failed += 1
                print(f"  FAIL {key}: {meta['errors'][0][:80]}")
                continue
            with open(os.path.join(snap, f'{key}.ocr.txt'), 'w', encoding='utf-8') as f:
                f.write(text)
            if pages is not None:
                with open(os.path.join(snap, f'{key}.ocr.words.json'), 'w', encoding='utf-8') as f:
                    json.dump({'pages': pages}, f, ensure_ascii=False)
            with open(os.path.join(snap, f'{key}.ocr.meta.json'), 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=1)
            done += 1
            print(f"  ocr {key} [{meta['path']}, {calls} call(s), {len(text)} chars]")
        except Exception as e:  # noqa: BLE001 — one bad file must not stop the batch
            failed += 1
            print(f'  FAIL {key}: {type(e).__name__}: {str(e)[:80]}')
    print(f'\nOCR capture: {done} new, {reused} from an earlier capture, '
          f'{len(docs) - len(pending) - reused} cached, {failed} failed '
          f'(of {len(docs)} docs). Vision calls made: {total_calls}.')


if __name__ == '__main__':
    main()
