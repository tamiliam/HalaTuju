"""Layer-A OCR capture for the signature-genuineness calibration (billable, idempotent).

Runs Google Cloud Vision DOCUMENT_TEXT_DETECTION over every results_slip document in the
eval set (fixtures/ + counter_examples/) and caches the raw text to snapshots/<key>.ocr.txt.
Re-runs skip already-cached docs, so it costs each document at most once. The cached text is
then replayed offline+free by the signature scorer (apps.scholarship.doc_signatures).

The Vision API key is read from a local gitignored .env (GOOGLE_CLOUD_VISION_API_KEY=...) so
the secret never appears on a command line. PDFs are rasterised (first page) before OCR.

Usage:  python apps/scholarship/eval/capture_ocr.py
"""
import glob
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))   # halatuju_api/
FOLDERS = [os.path.join(HERE, 'fixtures', 'results_slip'),
           os.path.join(HERE, 'counter_examples', 'results_slip')]
SNAP = os.path.join(HERE, 'snapshots')


def _api_key():
    k = os.environ.get('GOOGLE_CLOUD_VISION_API_KEY', '').strip()
    if k:
        return k
    envp = os.path.join(ROOT, '.env')
    if os.path.exists(envp):
        for line in open(envp, encoding='utf-8'):
            line = line.strip()
            if line.startswith('GOOGLE_CLOUD_VISION_API_KEY='):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    return ''


def _image_bytes(path):
    """Return (bytes, ok). PDFs are rasterised to a PNG of page 1 via PyMuPDF."""
    data = open(path, 'rb').read()
    if path.lower().endswith('.pdf'):
        import fitz
        d = fitz.open(path)
        pix = d[0].get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        return pix.tobytes('png'), True
    return data, True


def main():
    from google.cloud import vision
    key = _api_key()
    if key:
        client = vision.ImageAnnotatorClient(client_options={'api_key': key})
        print('Using GOOGLE_CLOUD_VISION_API_KEY.')
    else:
        try:                                  # fall back to gcloud Application Default Credentials
            client = vision.ImageAnnotatorClient()
            print('No API key found — using Application Default Credentials (gcloud).')
        except Exception as e:  # noqa: BLE001
            print(f'No API key in .env AND no ADC available ({type(e).__name__}). '
                  'Either add GOOGLE_CLOUD_VISION_API_KEY to halatuju_api/.env, '
                  'or run: gcloud auth application-default login')
            return

    docs = []
    for folder in FOLDERS:
        for p in sorted(glob.glob(folder + '/*')):
            if not p.endswith('.gitkeep'):
                docs.append(p)
    done = skipped = failed = 0
    for p in docs:
        key_name = os.path.basename(p).replace('results_slip__', '').rsplit('.', 1)[0]
        out = os.path.join(SNAP, f'results_slip__{key_name}.ocr.txt')
        if os.path.exists(out):
            skipped += 1
            continue
        try:
            img, _ = _image_bytes(p)
            resp = client.document_text_detection(image=vision.Image(content=img))
            if resp.error and resp.error.message:
                failed += 1
                print(f'  FAIL {key_name}: {resp.error.message[:80]}')
                continue
            text = resp.full_text_annotation.text if resp.full_text_annotation else ''
            with open(out, 'w', encoding='utf-8') as f:
                f.write(text)
            done += 1
            print(f'  ocr {key_name} ({len(text)} chars)')
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f'  FAIL {key_name}: {type(e).__name__}: {e}')
    print(f'\nOCR capture: {done} new, {skipped} cached, {failed} failed (of {len(docs)} docs).')


if __name__ == '__main__':
    main()
