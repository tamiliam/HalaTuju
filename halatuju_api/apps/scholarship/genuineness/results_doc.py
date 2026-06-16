"""Probabilistic genuineness for SPM results documents (slip + certificate) via SIGNATURE
presence. Moved here from apps/scholarship/doc_signatures.py (which is now a back-compat shim).

Unlike the IC / supporting-doc checks (which ask a model a holistic question), almost every
distinctive feature of an SPM slip/cert is a fixed PRINTED STRING, so we detect it
deterministically in the OCR text — no model guess, fully auditable, identical every run.
Only two signatures are visual (the JATA NEGARA crest and the QR code), passed in as flags.

We score against TWO lists — a results SLIP and a CERTIFICATE — and take the better fit, which
also tells us WHICH one it is. The score is a PROBABILITY (weighted fraction of expected
signatures present), not a yes/no: a student may photograph a slip with the bottom cut off, so
a genuine document can be missing its trailing signatures (QR / PENGARAH / disclaimer) and must
still score as likely-genuine on everything else. Forge-hard signatures carry more weight, so
their PRESENCE lifts confidence while their ABSENCE alone never condemns a complete document.

SOFT signal only; the reviewer is the authority.
"""
import re
import unicodedata

from .bands import GENUINE_MIN, SUSPECT_MAX, band_for  # noqa: F401  (re-exported for callers)

# Each signature: (label, [match patterns], weight, kind). kind 'text' is matched against the
# OCR text; kind 'visual' is satisfied by a passed-in flag (crest / QR). Weights: 1 = ordinary
# label, 2 = distinctive, 3 = forge-hard / near-unique to the genuine document.
SLIP_SIGNATURES = [
    ('JATA NEGARA',                  ['__crest__'],                          2, 'visual'),
    ('KEMENTERIAN PENDIDIKAN',       ['KEMENTERIAN PENDIDIKAN'],             1, 'text'),
    ('LEMBAGA PEPERIKSAAN',          ['LEMBAGA PEPERIKSAAN'],                2, 'text'),
    ('SIJIL PELAJARAN MALAYSIA',     ['SIJIL PELAJARAN MALAYSIA'],           1, 'text'),
    ('NO. PENGENALAN DIRI',          ['PENGENALAN DIRI'],                    1, 'text'),
    ('ANGKA GILIRAN',                ['ANGKA GILIRAN'],                      2, 'text'),
    ('SEKOLAH',                      ['SEKOLAH'],                            1, 'text'),
    ('JUMLAH MATA PELAJARAN',        ['JUMLAH MATA PELAJARAN'],              1, 'text'),
    ('KOD',                          ['KOD'],                                1, 'text'),
    ('NAMA MATA PELAJARAN',          ['NAMA MATA PELAJARAN'],                1, 'text'),
    ('GRED',                         ['GRED'],                               1, 'text'),
    ('LAYAK MENDAPAT SIJIL',         ['LAYAK MENDAPAT SIJIL'],               2, 'text'),
    ('UJIAN LISAN BAHASA MELAYU',    ['UJIAN LISAN BAHASA MELAYU'],          1, 'text'),
    ('disclaimer (bukan sijil)',     ['SLIP KEPUTUSAN INI BUKAN SIJIL',
                                      'BUKAN SIJIL/PERNYATAAN',
                                      'BUKAN SIJIL PERNYATAAN'],             3, 'text'),
    ('QR CODE',                      ['__qr__'],                             3, 'visual'),
    ('PENGARAH PEPERIKSAAN',         ['PENGARAH PEPERIKSAAN'],               2, 'text'),
]

CERT_SIGNATURES = [
    ('JATA NEGARA',                  ['__crest__'],                          2, 'visual'),
    ('KEMENTERIAN PENDIDIKAN MALAYSIA', ['KEMENTERIAN PENDIDIKAN MALAYSIA',
                                         'KEMENTERIAN PENDIDIKAN'],          1, 'text'),
    ('MINISTRY OF EDUCATION MALAYSIA', ['MINISTRY OF EDUCATION'],            2, 'text'),
    ('LEMBAGA PEPERIKSAAN',          ['LEMBAGA PEPERIKSAAN'],                1, 'text'),
    ('EXAMINATIONS SYNDICATE',       ['EXAMINATIONS SYNDICATE'],             2, 'text'),
    ('Calon yang namanya',           ['CALON YANG NAMANYA'],                 2, 'text'),
    ('SIJIL PELAJARAN MALAYSIA',     ['SIJIL PELAJARAN MALAYSIA'],           1, 'text'),
    ('Mata Pelajaran',               ['MATA PELAJARAN'],                     1, 'text'),
    ('Gred',                         ['GRED'],                               1, 'text'),
    ('Subject',                      ['SUBJECT'],                            1, 'text'),
    ('Grade',                        ['GRADE'],                              1, 'text'),
    ('UJIAN LISAN BAHASA MELAYU',    ['UJIAN LISAN BAHASA MELAYU'],          1, 'text'),
    ('JUMLAH MATA PELAJARAN',        ['JUMLAH MATA PELAJARAN'],              1, 'text'),
    ('PEPERIKSAAN TAHUN',            ['PEPERIKSAAN TAHUN'],                   1, 'text'),
    ('QR CODE',                      ['__qr__'],                             3, 'visual'),
    ('Director of Examinations',     ['DIRECTOR OF EXAMINATIONS'],           2, 'text'),
]

# Birth certificate (JPN Sijil Kelahiran) — standard document, so same signature approach.
# Mostly fixed printed strings; the JATA NEGARA crest + the barcode (which encodes the child's
# IC) are the two visual markers (the barcode is the BC's machine token, ~ the slip's QR).
BC_SIGNATURES = [
    ('JATA NEGARA',                   ['__crest__'],                                    2, 'visual'),
    ('KERAJAAN MALAYSIA',             ['KERAJAAN MALAYSIA'],                            1, 'text'),
    ('SIJIL KELAHIRAN',               ['SIJIL KELAHIRAN'],                              2, 'text'),
    ('Akta Pendaftaran 1957',         ['PENDAFTARAN KELAHIRAN DAN KEMATIAN'],           3, 'text'),
    ('KANAK-KANAK',                   ['KANAK KANAK'],                                  2, 'text'),
    ('BAPA',                          ['BAPA'],                                         1, 'text'),
    ('IBU',                           ['IBU'],                                          1, 'text'),
    ('No. Kad Pengenalan',            ['KAD PENGENALAN'],                               1, 'text'),
    ('Taraf Kewarganegaraan',         ['KEWARGANEGARAAN', 'WARGANEGARA'],               1, 'text'),
    ('Kawasan Pendaftaran',           ['KAWASAN PENDAFTARAN'],                          2, 'text'),
    ('Tempat Kelahiran',              ['TEMPAT KELAHIRAN'],                             1, 'text'),
    ('No. Daftar',                    ['NO DAFTAR'],                                    2, 'text'),
    ('certification line',            ['DISAHKAN BAHAWA MAKLUMAT'],                     2, 'text'),
    ('PENDAFTAR BESAR',               ['PENDAFTAR BESAR'],                              2, 'text'),
    ('Kelahiran & Kematian Malaysia', ['KELAHIRAN DAN KEMATIAN MALAYSIA',
                                       'KELAHIRAN KEMATIAN MALAYSIA'],                  1, 'text'),
    ('barcode',                       ['__barcode__'],                                  3, 'visual'),
]

# A doc_type is scored against its FAMILY of candidate lists (best fit wins + names the type).
# results_slip + certificate are scored together (auto-detect); birth_certificate is its own.
_RESULTS_LISTS = {'results_slip': SLIP_SIGNATURES, 'certificate': CERT_SIGNATURES}
_FAMILIES = {'results_slip': _RESULTS_LISTS, 'certificate': _RESULTS_LISTS,
             'birth_certificate': {'birth_certificate': BC_SIGNATURES}}
_LISTS = _RESULTS_LISTS   # back-compat default (slip/cert)


def _norm(s: str) -> str:
    """Upper-case, strip accents, collapse runs of non-alphanumerics to a single space."""
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^A-Z0-9]+', ' ', s.upper()).strip()


def _score_list(signatures, text_norm, has_qr, has_crest):
    present, missing, got, total = [], [], 0, 0
    for label, patterns, weight, kind in signatures:
        total += weight
        if kind == 'visual':
            # __crest__ → the crest flag; __qr__/__barcode__ → the machine-token flag (has_qr).
            hit = has_crest if patterns == ['__crest__'] else has_qr
        else:
            hit = any(_norm(p) in text_norm for p in patterns)
        (present if hit else missing).append(label)
        if hit:
            got += weight
    return {'weight_got': got, 'weight_total': total,
            'probability': round(got / total, 3) if total else 0.0,
            'present': present, 'missing': missing}


def score_signatures(ocr_text: str, has_qr: bool = False, has_crest: bool = False,
                     doc_type: str = None) -> dict:
    """Score OCR text against the slip + certificate signature lists. Returns
    ``{type, probability, weight_got, weight_total, present, missing, scores}`` for the
    better-fitting list. Pure + deterministic for the text signatures."""
    tn = _norm(ocr_text)
    lists = _FAMILIES.get(doc_type, _LISTS)
    scores = {name: _score_list(sig, tn, has_qr, has_crest) for name, sig in lists.items()}
    best = max(scores, key=lambda k: scores[k]['probability'])
    b = scores[best]
    return {'type': best, 'probability': b['probability'],
            'weight_got': b['weight_got'], 'weight_total': b['weight_total'],
            'present': b['present'], 'missing': b['missing'], 'scores': scores}


# The two NON-text signatures (QR + crest) are visual, so a tiny multimodal read reports
# them — far more robust than decoding the QR (a model sees "a QR is present" even on a blurry
# photo where a decoder fails). Soft: an AI outage / no image → both absent, never a penalty.
_VISUAL_SCHEMA = {'type': 'object', 'properties': {
    'has_qr_code': {'type': 'boolean'}, 'has_jata_negara_crest': {'type': 'boolean'}},
    'required': ['has_qr_code', 'has_jata_negara_crest']}
_VISUAL_PROMPT = (
    'This image was uploaded as a Malaysian SPM results slip or certificate. Ignore the text '
    'and report two VISUAL features: has_qr_code — is a QR code / 2D barcode present anywhere on '
    'the document? has_jata_negara_crest — is the Malaysian national crest (Jata Negara, the '
    'tiger-and-shield coat of arms) present in the header?')


def results_visual_markers(data: bytes, content_type: str = '') -> dict:
    """Soft multimodal read of the two visual signatures → ``{'has_qr', 'has_crest'}``, or
    ``{}`` on no image / AI outage (both then treated as absent — never penalising). The Gemini
    seam is reached via ``vision._call_gemini_json`` (lazy import keeps this module's top pure)."""
    from apps.scholarship import vision
    img, mime = vision._as_image_for_gemini(data, content_type)
    if img is None:
        return {}
    r = vision._call_gemini_json(_VISUAL_PROMPT, _VISUAL_SCHEMA, image=img, mime_type=mime)
    if not isinstance(r, dict) or r.get('_error'):
        return {}
    return {'has_qr': bool(r.get('has_qr_code')), 'has_crest': bool(r.get('has_jata_negara_crest'))}


def signature_genuineness(ocr_text: str, has_qr: bool = False, has_crest: bool = False,
                          doc_type: str = None) -> dict:
    """The soft genuineness signal for a standard document from its signatures:
    ``{status, probability, type, present, missing, reason}``. ``status`` maps onto the cap
    vocabulary via ``band_for``. ``doc_type`` selects the signature family (slip/cert by default,
    'birth_certificate' for the BC). Pure + deterministic given the inputs; never raises."""
    r = score_signatures(ocr_text, has_qr=has_qr, has_crest=has_crest, doc_type=doc_type)
    status = band_for(r['probability'])
    if status == 'not_type':                       # <0.35 → not recognisably that document
        status = 'not_' + (doc_type or r['type'])
    n_have, n_all = len(r['present']), len(r['present']) + len(r['missing'])
    reason = (f"{n_have}/{n_all} {r['type'].replace('_', ' ')} signatures present "
              f"(p={r['probability']:.2f}); missing: {', '.join(r['missing'][:4]) or 'none'}")
    return {'status': status, 'probability': r['probability'], 'type': r['type'],
            'present': r['present'], 'missing': r['missing'], 'reason': reason[:300]}
