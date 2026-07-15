"""School-leaving certificate genuineness — the deterministic signature scorer.

A post-SPM applicant's *Sijil Berhenti Sekolah* (school-leaving certificate / testimonial). Unlike
the SPM slip/cert (ONE national issuer, fixed printed strings), this document is **school-issued**:
the widely-used standard is a numbered form titled "SIJIL BERHENTI SEKOLAH" with fixed field labels
(Nama Murid · No. Kad Pengenalan · Tingkatan Semasa Daftar/Berhenti · Kelakuan · Tarikh Berhenti
Sekolah · Sebab Berhenti Sekolah · Catatan), but a minority of schools issue a free-form testimonial
LETTER instead. So the model is **leaver-anchor-first, structural-labels-as-strength** (the shape of
the water model, water_doc.py — grammar-first, not a single issuer):

  * a LEAVER anchor ("Berhenti Sekolah" / "Tamat Persekolahan" / a leaving-certificate title) marks
    the document as a school-leaving cert and GUARANTEES it is never rejected (mirrors water's "any
    water signal ⟹ never rejected"). The distinctive structural field labels then decide
    genuine (the standard numbered form, several labels) vs suspect (a thin / cropped read).
  * a school-issued TESTIMONIAL with no numbered-form grammar (school name + leaving language but
    none of the field labels) scores 'unrecognised' — DEFER to the reviewer, never 'fake'. Owner
    rule: a genuine leaver's letter must NEVER be falsely rejected.
  * not_school_leaving_cert → a MyKad in the slot, or a DIFFERENT known document (results slip /
    certificate / EPF / birth cert / STR) misfiled here, or nothing school-shaped at all. The
    wrong-type reject fires ONLY when NO leaver signal anchors the doc.

Calibration: NO eval snapshots existed for this type (it was added 2026-07-03) and the raw OCR text
is not persisted, so the initial weights below are set from the standard-form spec + one live sample
(#66 THARUN). They are VALIDATED against the live corpus (19 certs) by a re-extraction pass that
stores `authenticity.present`/`missing` per doc — read those back and tune. Conservative by design:
a thin read lands in 'suspect' (officer confirms), never a false 'genuine' or a false reject.

Returns the canonical soft vocabulary ('genuine' / 'suspect' / 'unrecognised' /
'not_school_leaving_cert') shared with every other genuineness type. SOFT throughout — the reviewer
is the authority; nothing here hard-blocks (it feeds the officer chip + the keep-better ranking via
`income_engine._doc_genuine_rank`, NOT the submission gate). Pure + deterministic given the OCR text.

BUMP MODEL_VERSION on ANY change to the marker groups, thresholds, or the decision cascade (same
discipline as water_doc / electricity_doc / salary_doc MODEL_VERSION) — it is persisted on the
document and gates re-scoring.
"""
from .results_doc import _norm, misfiled_as

# Version of the school-leaving-cert signature model. History:
#   1.0.0 (2026-07-15) — initial leaver-anchor-first + structural-labels cascade; testimonial letters
#                        → unrecognised (never fake); wrong-type backstop (MyKad / another known doc
#                        in the slot). Owner-specified signature set: title (SIJIL BERHENTI SEKOLAH) +
#                        No. Kad Pengenalan · Tarikh Lahir · Tempat Lahir · Tarikh Masuk Sekolah ·
#                        Kelakuan · Tarikh Berhenti · Sebab Berhenti. Set from the standard form + one
#                        live sample; to be validated/tuned against the 19-cert live corpus.
MODEL_VERSION = '1.0.0'

# ── LEAVER anchor — "is this a school-leaving certificate?" (also the never-reject guarantee) ──────
# Near-unique to a leaver document; a results slip / testimonial-of-merit / MyKad carries none of
# these. 'BERHENTI SEKOLAH' is the dominant Malay phrase; the 'TARIKH/SEBAB BERHENTI' field labels
# (owner-specified) also anchor, and the English + alternate Malay wordings cover the free-form
# testimonial and the East-Malaysia / private-school variants.
_LEAVER_ANCHOR = [
    'BERHENTI SEKOLAH', 'TARIKH BERHENTI', 'SEBAB BERHENTI', 'AKUAN BERHENTI', 'SIJIL BERHENTI',
    'SURAT BERHENTI', 'TAMAT PERSEKOLAHAN', 'MENAMATKAN PERSEKOLAHAN', 'TAMAT TINGKATAN',
    'SCHOOL LEAVING', 'LEAVING CERTIFICATE',
]
# The explicit standard-form TITLE (a strong positive — the numbered Sijil Berhenti Sekolah).
_TITLE = ['SIJIL BERHENTI SEKOLAH', 'SURAT AKUAN BERHENTI SEKOLAH', 'SURAT PENGESAHAN BERHENTI SEKOLAH']

# ── Structural field-label grammar — "is this the standard numbered form?". Each GROUP counts once.
# The owner-specified signature set (2026-07-15): identity + birth + entry/leaving/conduct labels.
# The BERHENTI / conduct labels are near-unique to a leaver cert; Kad Pengenalan / Tarikh Lahir /
# Tempat Lahir are shared with other forms → ordinary (they corroborate the standard numbered form).
_FIELD_LABELS = [
    ['KAD PENGENALAN', 'NO KAD PENGENALAN', 'NO KP'],
    ['TARIKH LAHIR', 'TKH LAHIR'],
    ['TEMPAT LAHIR'],
    ['TARIKH MASUK SEKOLAH', 'TARIKH KEMASUKAN SEKOLAH', 'TARIKH KEMASUKAN'],
    ['KELAKUAN'],                                                     # conduct — distinctive
    ['TARIKH BERHENTI', 'TARIKH BERHENTI SEKOLAH'],
    ['SEBAB BERHENTI', 'SEBAB BERHENTI SEKOLAH'],
]
# School header words — corroborate "a school issued this" (weak; also present on a results slip, so
# NOT a leaver anchor). Bonus only.
_SCHOOL_WORDS = ['SEKOLAH MENENGAH', 'SMK', 'PENGETUA', 'TANDATANGAN PENGETUA', 'GURU BESAR',
                 'SEKOLAH KEBANGSAAN', 'MAKTAB']
# MyKad-distinctive markers that never appear on a genuine cert (mirrors salary/water #47 backstop).
_MYKAD = ['WARGANEGARA', 'PENGARAH PENDAFTARAN', 'PENDAFTARAN NEGARA', 'MYKAD']


def _any(tokens, tn):
    return any(_norm(t) in tn for t in tokens)


def score_markers(ocr_text: str) -> dict:
    """The raw marker tallies for OCR text (transparent, for tests + calibration):
    ``{title, leaver, labels, label_names, school, mykad}``. ``labels`` = how many of the standard
    field-label GROUPS are present; ``label_names`` names which ones (the calibration readout — the
    raw OCR text is not persisted, so this per-doc hit list is what we read back to tune). Pure."""
    tn = _norm(ocr_text)
    hit = [g[0] for g in _FIELD_LABELS if _any(g, tn)]
    return {
        'title': _any(_TITLE, tn),
        'leaver': _any(_LEAVER_ANCHOR, tn),
        'labels': len(hit),
        'label_names': hit,
        'school': _any(_SCHOOL_WORDS, tn),
        'mykad': _any(_MYKAD, tn),
    }


def school_leaving_genuineness(ocr_text: str) -> dict:
    """Soft genuineness signal for a school-leaving certificate → ``{status, family, probability,
    reason, model_version, markers}``. ``status`` ∈ {'genuine', 'suspect', 'unrecognised',
    'not_school_leaving_cert'} (the canonical cap vocabulary); ``family`` names the form
    ('sijil_berhenti' standard numbered / 'testimonial' free-form letter) or a reject family. Pure +
    deterministic; never raises."""
    m = score_markers(ocr_text)
    labels = m['labels']
    is_leaver = bool(m['title'] or m['leaver'])

    def out(status, family, prob, reason):
        return {'status': status, 'family': family, 'probability': round(prob, 3),
                'reason': reason[:300], 'model_version': MODEL_VERSION,
                'markers': {'title': m['title'], 'leaver': m['leaver'], 'labels': labels,
                            'label_names': m['label_names'], 'school': m['school']}}

    # ── Reject / defer floor — ONLY when NO leaver signal anchors the doc ─────────────────────────
    if not is_leaver:
        # A genuine cert always carries a leaver anchor (so never reaches here); the MyKad markers
        # (Warganegara / Ketua Pengarah Pendaftaran) never sit on one — so the marker alone rejects,
        # even though a MyKad also prints the shared 'Kad Pengenalan' label.
        if m['mykad']:
            return out('not_school_leaving_cert', 'not_school_leaving_cert', 0.05,
                       'MyKad markers, no leaver fields — not a school-leaving certificate')
        # A DIFFERENT known document misfiled in the slot (results slip / cert / EPF / BC / STR).
        mis = misfiled_as('school_leaving_cert', ocr_text)
        if mis.get('status'):
            return out('not_school_leaving_cert', mis.get('doc_seen', 'not_school_leaving_cert'),
                       mis.get('probability', 0.1),
                       f"reads as a {mis.get('doc_seen', 'different document')} — wrong type in the slot")
        if not m['school'] and labels == 0:
            return out('not_school_leaving_cert', 'not_school_leaving_cert', 0.12,
                       'no leaver signal and nothing school-shaped — not a school-leaving certificate')
        # School-ish but no leaver anchor and not clearly another doc: a free-form testimonial we
        # cannot structurally confirm. DEFER — never fake (owner rule).
        return out('unrecognised', 'testimonial', 0.5,
                   'school document without the standard leaver-form grammar — defer to reviewer')

    # ── Genuine / suspect (a leaver document) ─────────────────────────────────────────────────────
    # The standard numbered form carries several field labels; a cropped photo carries fewer. The
    # leaver anchor alone already establishes the type — labels grade the confidence.
    if m['title'] and labels >= 2:
        return out('genuine', 'sijil_berhenti', min(0.95, 0.70 + 0.05 * labels),
                   f'Sijil Berhenti Sekolah title + {labels} field labels — genuine leaver certificate')
    if labels >= 3:
        return out('genuine', 'sijil_berhenti', min(0.92, 0.65 + 0.05 * labels),
                   f'leaver grammar + {labels} field labels — genuine school-leaving certificate')
    if labels >= 1:
        return out('suspect', 'sijil_berhenti', 0.55,
                   f'leaver signal but only {labels} field label(s) — thin read, confirm')
    if m['title']:
        # The standard-form title is present (so it IS a Sijil Berhenti Sekolah) but no field labels
        # read — a very cropped/blurry scan → suspect (confirm), not a testimonial.
        return out('suspect', 'sijil_berhenti', 0.5,
                   'Sijil Berhenti Sekolah title but no readable field labels — very thin read, confirm')
    # A leaver phrase but no title and no structural labels (a free-form testimonial letter, or a
    # very cropped read) → defer to the reviewer, never fake.
    return out('unrecognised', 'testimonial', 0.5,
               'leaver language but no standard field labels — a testimonial letter; defer to reviewer')
