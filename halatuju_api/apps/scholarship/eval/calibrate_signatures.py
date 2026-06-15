"""Calibrate the signature-genuineness thresholds against the labelled corpus.

Scores every results_slip document (fixtures/ = genuine, counter_examples/ = known fake)
with apps.scholarship.doc_signatures, using cached Cloud Vision OCR text
(snapshots/<key>.ocr.txt; falls back to the PDF text layer when present). Prints the
probability each document gets, the genuine-vs-fake split, and a suggested threshold band.

Text signatures only (deterministic, reliable). QR/crest are bonus margin in production and
are not credited here, so this is the conservative floor.

Usage:  python apps/scholarship/eval/calibrate_signatures.py   (after capture_ocr.py)
"""
import glob
import os
import sys
import django

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', '..')))   # halatuju_api/
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'halatuju.settings.development')
django.setup()
from apps.scholarship.doc_signatures import score_signatures  # noqa: E402
SNAP = os.path.join(HERE, 'snapshots')
SETS = [('genuine', os.path.join(HERE, 'fixtures', 'results_slip')),
        ('FAKE',    os.path.join(HERE, 'counter_examples', 'results_slip'))]


def ocr_text_for(path, key):
    cached = os.path.join(SNAP, f'results_slip__{key}.ocr.txt')
    if os.path.exists(cached):
        return open(cached, encoding='utf-8').read(), 'vision'
    if path.lower().endswith('.pdf'):
        import fitz
        t = fitz.open(path)[0].get_text()
        if 'PEPERIKSAAN' in t.upper():
            return t, 'pdf-text'
    return '', 'NONE'


def main():
    rows = []
    for label, folder in SETS:
        for p in sorted(glob.glob(folder + '/*')):
            if p.endswith('.gitkeep'):
                continue
            key = os.path.basename(p).replace('results_slip__', '').rsplit('.', 1)[0]
            text, src = ocr_text_for(p, key)
            r = score_signatures(text)
            rows.append((label, key, src, r['type'], r['probability'], len(r['present']),
                         len(r['present']) + len(r['missing'])))

    rows.sort(key=lambda x: (x[0] != 'FAKE', x[4]))   # fakes first, then by probability
    print(f"{'label':8} {'key':14} {'ocr':9} {'type':12} {'prob':>5}  present")
    print('-' * 62)
    for label, key, src, typ, prob, pres, tot in rows:
        print(f"{label:8} {key:14} {src:9} {typ:12} {prob:5.2f}  {pres}/{tot}")

    gen = [r[4] for r in rows if r[0] == 'genuine' and r[2] != 'NONE']
    fake = [r[4] for r in rows if r[0] == 'FAKE']
    none = [r[1] for r in rows if r[2] == 'NONE']
    if gen:
        gen.sort()
        print(f"\nGENUINE (n={len(gen)}): min={min(gen):.2f}  median={gen[len(gen)//2]:.2f}  max={max(gen):.2f}")
    if fake:
        print(f"FAKE    (n={len(fake)}): {sorted(fake)}")
    if gen and fake:
        lo, hi = max(fake), min(gen)
        print(f"\nSeparation: highest fake={lo:.2f}  vs  lowest genuine={hi:.2f}  "
              + (f"-> clean gap, suggest threshold ~{(lo+hi)/2:.2f}" if lo < hi
                 else "-> OVERLAP, signatures alone insufficient; need QR/crest credit"))
    if none:
        print(f"\nNo OCR yet for {len(none)} docs (run capture_ocr.py): {none}")


if __name__ == '__main__':
    main()
