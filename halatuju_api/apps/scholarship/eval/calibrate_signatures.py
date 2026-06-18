"""Calibrate the signature-genuineness thresholds against the labelled corpus.

Scores every document of a doc-type (fixtures/ = genuine, counter_examples/ = known fake/
wrong-type) with apps.scholarship.genuineness, using cached Cloud Vision OCR text
(snapshots/<doctype>__<key>.ocr.txt; falls back to the PDF text layer for slips). Prints the
probability + canonical STATUS each document gets, a per-status breakdown, and (for single-issuer
types) a suggested threshold band.

Text signatures only (deterministic, reliable). QR/crest/seal are bonus margin in production and
are not credited here, so this is the conservative floor.

Usage:  python apps/scholarship/eval/calibrate_signatures.py [doc_type]   (default results_slip;
        e.g. offer_letter | epf | birth_certificate — after capture_ocr.py for that type)
"""
import glob
import os
import sys
import django

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', '..')))   # halatuju_api/
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'halatuju.settings.development')
django.setup()
from apps.scholarship.genuineness.results_doc import score_signatures, signature_genuineness  # noqa: E402

DOC_TYPE = sys.argv[1] if len(sys.argv) > 1 else 'results_slip'
SNAP = os.path.join(HERE, 'snapshots')
SETS = [('genuine', os.path.join(HERE, 'fixtures', DOC_TYPE)),
        ('FAKE',    os.path.join(HERE, 'counter_examples', DOC_TYPE))]


def ocr_text_for(path, key):
    cached = os.path.join(SNAP, f'{DOC_TYPE}__{key}.ocr.txt')
    if os.path.exists(cached):
        return open(cached, encoding='utf-8').read(), 'vision'
    if path.lower().endswith('.pdf'):                 # PDF text-layer fallback (slips)
        import fitz
        t = fitz.open(path)[0].get_text()
        if len(t.strip()) > 40:
            return t, 'pdf-text'
    return '', 'NONE'


def main():
    rows = []
    for label, folder in SETS:
        for p in sorted(glob.glob(folder + '/*')):
            if p.endswith('.gitkeep'):
                continue
            key = os.path.basename(p).replace(f'{DOC_TYPE}__', '').rsplit('.', 1)[0]
            text, src = ocr_text_for(p, key)
            r = score_signatures(text, doc_type=DOC_TYPE)
            status = signature_genuineness(text, doc_type=DOC_TYPE)['status']
            rows.append((label, key, src, r['type'], r['probability'], status,
                         len(r['present']), len(r['present']) + len(r['missing'])))

    rows.sort(key=lambda x: (x[0] != 'FAKE', x[4]))   # fakes first, then by probability
    print(f"calibrating doc_type = {DOC_TYPE}\n")
    print(f"{'label':8} {'key':14} {'ocr':9} {'type':14} {'prob':>5} {'status':16} present")
    print('-' * 78)
    for label, key, src, typ, prob, status, pres, tot in rows:
        print(f"{label:8} {key:14} {src:9} {typ:14} {prob:5.2f} {status:16} {pres}/{tot}")

    # Canonical-status breakdown per label (the meaningful summary — esp. for multi-issuer types
    # like offer_letter, where an 'unrecognised' tail deferring to holistic is EXPECTED, not a fail).
    from collections import Counter
    for label, _ in SETS:
        c = Counter(r[5] for r in rows if r[0] == label and r[2] != 'NONE')
        if c:
            print(f"\n{label} status breakdown: {dict(c)}")

    gen = [r[4] for r in rows if r[0] == 'genuine' and r[2] != 'NONE' and r[5] == 'genuine']
    fake = [r[4] for r in rows if r[0] == 'FAKE']
    none = [r[1] for r in rows if r[2] == 'NONE']
    if gen:
        gen.sort()
        print(f"\nGENUINE-status (n={len(gen)}): min={min(gen):.2f}  median={gen[len(gen)//2]:.2f}  max={max(gen):.2f}")
    if fake:
        print(f"FAKE folder (n={len(fake)}): probs={sorted(fake)}")
    if none:
        print(f"\nNo OCR yet for {len(none)} docs (run capture_ocr.py {DOC_TYPE}): {none}")


if __name__ == '__main__':
    main()
