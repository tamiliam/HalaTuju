"""Held-out / corpus Layer-1 validation for OFFER LETTERS.

Tests the live offer-letter config on documents the signatures were NOT tuned on:
  Issue 1 (genuineness) — Cloud Vision OCR -> signature_genuineness   (FREE)
  Issue 2 (extraction)  — image-Gemini -> the 4-pathway/UA field contract  (billable Flash)

READ-ONLY on prod. PII stays in memory — nothing is persisted; candidate name/NRIC/address are
REDACTED in the printed report (NRIC shown only as match/✗ vs the applicant's profile NRIC).

Usage (from halatuju_api/):
  python apps/scholarship/eval/heldout_eval.py unseen   # offer letters NOT in the local corpus
  python apps/scholarship/eval/heldout_eval.py local    # re-score + re-extract local fixtures
  add  --no-extract  to run Issue 1 only (free).
"""
import io
import os
import sys
import glob
import json
import urllib.parse
import urllib.request

import django

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))   # halatuju_api/
sys.path.insert(0, ROOT)


def _load_dotenv():
    """Load the gitignored .env (repo root, or halatuju_api/) into os.environ BEFORE Django
    settings import, so GEMINI_API_KEY / SUPABASE_* are available locally (dev only)."""
    for envp in (os.path.join(os.path.dirname(ROOT), '.env'), os.path.join(ROOT, '.env')):
        if os.path.exists(envp):
            for line in open(envp, encoding='utf-8'):
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return


_load_dotenv()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'halatuju.settings.development')
django.setup()
from apps.scholarship.genuineness.results_doc import signature_genuineness  # noqa: E402
from apps.scholarship.vision import extract_document_fields                 # noqa: E402

BUCKET = 'b40-documents'
# Offer-letter doc ids already in the local corpus (fixtures + counter_examples) — the "training" set.
CORPUS_IDS = {13,25,34,49,90,99,117,129,167,211,214,230,270,329,358,384,392,408,418,430,442,445,
              450,458,459,463,503,504,514,526,546,561,572,575,595,618,647,671,708,748,759,777,793,
              830,847,855}


def _env(name):
    v = os.environ.get(name)
    if v:
        return v
    # .env lives at the repo root (one level above halatuju_api/); also try halatuju_api/.env.
    for envp in (os.path.join(os.path.dirname(ROOT), '.env'), os.path.join(ROOT, '.env')):
        if os.path.exists(envp):
            for line in open(envp, encoding='utf-8'):
                line = line.strip()
                if line.startswith(name + '='):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    return ''


def _rest(base, key, table, select, params=None):
    q = {'select': select, 'limit': '5000', **(params or {})}
    url = f'{base}/rest/v1/{table}?' + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={'apikey': key, 'Authorization': f'Bearer {key}'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def _download(base, key, path):
    req = urllib.request.Request(
        f'{base}/storage/v1/object/authenticated/{BUCKET}/{path}',
        headers={'Authorization': f'Bearer {key}', 'apikey': key})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read()


def _png_of_pdf(data):
    import fitz
    d = fitz.open(stream=data, filetype='pdf')
    return d[0].get_pixmap(matrix=fitz.Matrix(2.0, 2.0)).tobytes('png')


def ocr_text(data, content_type):
    """Cloud Vision DOCUMENT_TEXT_DETECTION via gcloud ADC (free tier). PDFs rasterised first."""
    from google.cloud import vision
    img = _png_of_pdf(data) if (content_type or '').lower().endswith('pdf') else data
    client = vision.ImageAnnotatorClient()
    resp = client.document_text_detection(image=vision.Image(content=img))
    return (resp.full_text_annotation.text or '') if resp.full_text_annotation else ''


def _canon_nric(s):
    return ''.join(c for c in str(s or '') if c.isdigit())


def _fields_summary(fields, profile_nric):
    """Redacted one-line view: presence of identity fields + the (non-PII) academic/date fields."""
    f = fields or {}
    have = lambda k: 'Y' if (f.get(k) or '').strip() else '-'
    nr = _canon_nric(f.get('candidate_nric'))
    nric = 'none' if not nr else ('match' if nr == _canon_nric(profile_nric) else 'DIFFERS')
    bits = [f"name={have('candidate_name')}", f"nric={nric}", f"date={have('offer_date')}"]
    for k in ('programme', 'stream', 'bidang_pengkhususan', 'elektif', 'aliran', 'institution',
              'reporting_date'):
        v = (f.get(k) or '').strip()
        if v:
            bits.append(f"{k}={v[:24]}")
    return ' '.join(bits)


def run(rows, do_extract):
    print(f"{'doc':>6} {'app':>4} {'declared':12} {'detected':14} {'status':13} {'prob':>4}  extraction")
    print('-' * 110)
    g = Counter()
    for r in rows:
        data, ct = r['bytes'], r['content_type']
        try:
            text = ocr_text(data, ct)
        except Exception as e:  # noqa: BLE001
            print(f"{r['id']:>6} {r['app']:>4} {r['declared']:12} OCR-FAIL ({type(e).__name__})")
            continue
        sg = signature_genuineness(text, doc_type='offer_letter')
        g[sg['status']] += 1
        ex_str = ''
        if do_extract:
            ex = extract_document_fields('', 'offer_letter', image=data, content_type=ct)
            ex_str = ex.get('error') or _fields_summary(ex.get('fields'), r.get('profile_nric'))
        print(f"{r['id']:>6} {r['app']:>4} {r['declared']:12} {sg['type']:14} {sg['status']:13} "
              f"{sg['probability']:4.2f}  {ex_str}")
    print(f"\nIssue-1 status breakdown: {dict(g)}")


def main():
    from collections import Counter as _C
    global Counter
    Counter = _C
    mode = sys.argv[1] if len(sys.argv) > 1 else 'unseen'
    do_extract = '--no-extract' not in sys.argv
    rows = []
    if mode == 'unseen':
        # SUPABASE_URL is a prod-only env var; locally derive it from the known project ref
        # (public URL — only the SERVICE_ROLE_KEY is secret, read from .env).
        base = (_env('SUPABASE_URL') or 'https://pbrrlyoyyiftckqvzvvo.supabase.co').rstrip('/')
        key = _env('SUPABASE_SERVICE_ROLE_KEY')
        docs = _rest(base, key, 'applicant_documents',
                     'id,application_id,storage_path,content_type', {'doc_type': 'eq.offer_letter'})
        apps = {a['id']: a for a in _rest(base, key, 'scholarship_applications',
                                          'id,chosen_pathway,profile_id')}
        profs = {p['supabase_user_id']: p for p in _rest(base, key, 'api_student_profiles',
                                                         'supabase_user_id,nric')}
        for d in docs:
            if d['id'] in CORPUS_IDS or not (d.get('storage_path') or '').strip():
                continue
            a = apps.get(d['application_id'], {})
            p = profs.get(a.get('profile_id'), {})
            rows.append({'id': d['id'], 'app': d['application_id'],
                         'declared': a.get('chosen_pathway') or '(blank)',
                         'content_type': d['content_type'], 'profile_nric': p.get('nric'),
                         'bytes': _download(base, key, d['storage_path'])})
        rows.sort(key=lambda r: r['id'])
        print(f"HELD-OUT (unseen) offer letters: {len(rows)} docs not in the local corpus\n")
    else:  # local corpus fixtures
        for p in sorted(glob.glob(os.path.join(HERE, 'fixtures', 'offer_letter', '*'))):
            if p.endswith('.gitkeep'):
                continue
            ct = 'application/pdf' if p.lower().endswith('.pdf') else 'image/jpeg'
            rows.append({'id': os.path.basename(p).split('__')[2].split('.')[0], 'app':
                         os.path.basename(p).split('__')[1], 'declared': '(corpus)',
                         'content_type': ct, 'profile_nric': '', 'bytes': open(p, 'rb').read()})
        print(f"LOCAL corpus offer letters: {len(rows)} docs\n")
    run(rows, do_extract)


if __name__ == '__main__':
    main()
