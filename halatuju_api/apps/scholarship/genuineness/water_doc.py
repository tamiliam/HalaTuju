"""Water-bill genuineness — the deterministic signature scorer.

Design + calibration: docs/scholarship/water-bill-catalogue.md (validated on 28 live OCR'd bills,
2026-07-10). Unlike electricity (electricity_doc.py), water has NO single national operator — it is
state-run, so ~13 different utilities issue bills (Air Selangor, SAJ/Ranhill Johor, SADA Kedah,
SAINS N.Sembilan, LAP Perak, PAIP Pahang, PBAPP Penang, SAMB Melaka, + the East-Malaysia / smaller
peninsular siblings). No issuer is dominant (the largest is ~20% of the corpus, vs TNB's ~92% for
electricity). So the fingerprint is **grammar-first, issuer-as-bonus** — the shape of the salary
model (salary_doc.py), NOT the issuer-anchored electricity cascade:

  * the shared WATER-BILL GRAMMAR decides genuine / suspect / not_water_bill — 'Bil Air' /
    'Bekalan Air', usage in m³ (meter padu — water's kWh), 'No. Akaun', 'Tunggakan', 'Tarif',
    'Jumlah Perlu Dibayar'. This is common to every operator, so a bill from an UNLISTED operator
    still scores genuine (family 'unrecognised').
  * the OPERATOR identity is a bonus signal — it names the family for the officer and lifts
    confidence, but it never gates 'genuine'. 26/28 live bills carried a recognised operator marker;
    the 2 that didn't are (a) a genuine bill from an operator we hadn't listed → 'unrecognised'
    genuine, and (b) a TNB ELECTRICITY bill misfiled into the water slot → the wrong-type reject.
  * not_water_bill → a MyKad in the slot (the #47 class), an ELECTRICITY bill misfiled into the
    water slot (family 'electricity_bill' — the reverse of the #83 swap, caught symmetrically), or
    nothing bill-shaped at all.

Calibration (n=28, real OCR): water-term 96% · m³/meter-padu 96% · NO AKAUN 96% · JUMLAH 100% ·
TUNGGAKAN 93% · TARIF 82% · a recognised operator 93%. TARIKH BIL is only 25% (water bills lean on
TEMPOH BIL — the period — not a point-in-time bill date, so currency stays period-anchored upstream).
Distribution: 27 genuine · 1 not_water_bill (a TNB electricity bill in the water slot) · **0
false-rejects**. Guarantee (mirrors electricity's "issuer ⟹ never rejected"): **any water signal —
a water term OR an m³ unit OR a recognised operator — guarantees the doc is never rejected**; the
reject branches fire only when NO water signal is present. So the two genuine bills that merely
*mention* 'elektrik' (a PBAPP and a SAMB bill) are protected by their water term, while the pure
TNB bill with no water signal is correctly rejected. Conservative by design: a thin/cropped read
lands in 'suspect' (officer confirms), never a false 'genuine' or a false reject.

Returns the canonical soft vocabulary ('genuine' / 'suspect' / 'not_water_bill') shared with every
other genuineness type (bands.canonical_status). SOFT throughout — the reviewer/officer is the
authority; nothing here hard-blocks. Pure + deterministic given the OCR text.

BUMP MODEL_VERSION on ANY change to the marker groups, thresholds, or the decision cascade (same
discipline as electricity_doc.MODEL_VERSION / salary_doc.MODEL_VERSION) — it is persisted on the
document and gates re-scoring.
"""
from .results_doc import _norm

# Version of the water-bill signature model. History:
#   1.0.0 (2026-07-10) — initial grammar-first + operator-bonus cascade; 13 operator families +
#                        unrecognised, with the electricity-in-water-slot wrong-type backstop.
MODEL_VERSION = '1.0.0'

# ── Operator identity (bonus signal — names the family, never gates 'genuine') ───────────────────
# In corpus-prevalence order. Markers are chosen to be DISTINCTIVE after _norm (uppercased, accents
# stripped, non-alphanumerics → single space) so they don't collide with ordinary Malay words —
# hence 'AIR TERENGGANU' not the bare 'SATU' (= "one"), 'LEMBAGA AIR PERAK' not the bare 'LAP',
# 'KUCHING WATER' not the bare 'LAKU' (substring of "berlaku"). Peninsular first, then East Malaysia.
_OPERATORS = [
    ('air_selangor',  ['AIR SELANGOR', 'PENGURUSAN AIR SELANGOR', 'SYABAS']),               # 6/28
    ('sada_kedah',    ['SADA', 'SYARIKAT AIR DARUL AMAN', 'AIR DARUL AMAN']),                # 5/28
    ('lap_perak',     ['LEMBAGA AIR PERAK', 'AIR PERAK']),                                   # 5/28
    ('sains_ns',      ['SAINS', 'SYARIKAT AIR NEGERI SEMBILAN', 'AIR NEGERI SEMBILAN']),     # 4/28
    ('paip_pahang',   ['PENGURUSAN AIR PAHANG', 'AIR PAHANG', 'PAIP PAHANG']),               # 4/28
    ('saj_johor',     ['RANHILL', 'SAJ', 'AIR JOHOR', 'SYARIKAT AIR JOHOR']),                # 3/28
    ('pbapp_penang',  ['PBAPP', 'PBA PULAU PINANG', 'PERBADANAN BEKALAN AIR PULAU PINANG']),  # 2/28
    ('samb_melaka',   ['SAMB', 'SYARIKAT AIR MELAKA', 'AIR MELAKA']),                        # 2/28
    # ── Future-proof siblings (0 in the current cohort — distinctive multi-word markers only) ─────
    ('aksb_kelantan', ['AIR KELANTAN', 'SYARIKAT AIR KELANTAN']),
    ('satu_tganu',    ['AIR TERENGGANU', 'SYARIKAT AIR TERENGGANU']),
    ('pba_perlis',    ['AIR PERLIS', 'PERBADANAN BEKALAN AIR PERLIS']),
    ('jans_sabah',    ['JABATAN AIR NEGERI SABAH', 'AIR NEGERI SABAH']),
    ('laku_sarawak',  ['KUCHING WATER', 'LAKU MANAGEMENT', 'SIBU WATER', 'AIR SARAWAK']),
]
# ── Water-type terms — "is this a water bill?" (separates from electricity; the wrong-type backstop) ─
_WATER_TERM = ['BIL AIR', 'BEKALAN AIR', 'METER AIR', 'CAJ AIR', 'PENGGUNAAN AIR', 'AIR TERAWAT',
               'JABATAN BEKALAN AIR', 'AIR TIDAK BERHASIL']
# Water usage unit — m³ / meter padu (water's kWh). NFKD folds '³'→'3', so 'M³' reads as 'M3'.
_M3 = ['METER PADU', 'M3', 'METERPADU']
# ── Bill-field grammar — "is this a bill at all?". Each GROUP counts once (hit-rate n=28) ─────────
_BILL_LABELS = [
    ['NO AKAUN', 'NOMBOR AKAUN', 'ACCOUNT NO', 'ACCOUNT NUMBER'],                # 96%
    ['JUMLAH PERLU DIBAYAR', 'JUMLAH PERLU', 'AMOUNT PAYABLE', 'JUMLAH BIL'],    # 100%
    ['TUNGGAKAN', 'BAKI TERDAHULU', 'BAKI TERTUNGGAK', 'ARREARS'],               # 93%
    ['TARIF', 'TARIFF'],                                                          # 82%
    ['SILA BAYAR SEBELUM', 'BAYAR SEBELUM', 'TARIKH AKHIR BAYARAN', 'DUE DATE'],  # 71%
    ['TEMPOH BIL', 'TEMPOH BACAAN', 'BILLING PERIOD'],                            # 61%
    ['CAJ SEMASA', 'CAJ AIR SEMASA', 'CURRENT CHARGE'],                           # 54%
    ['BACAAN METER', 'BACAAN SEBENAR', 'METER READING'],                          # 29%
    ['TARIKH BIL', 'BILL DATE'],                                                  # 25%
]
# ── Electricity markers — an electricity bill misfiled into the water slot (family 'electricity_bill').
# Only rejects when NO water signal is present (a genuine water bill that merely mentions 'elektrik'
# keeps its water term and is safe — a62/a9 in the corpus).
_ELECTRICITY_TERM = ['ELEKTRIK', 'ELECTRICITY', 'TENAGA NASIONAL', 'KWJ', 'KWH', 'KILOWATT', 'TNB']
# MyKad-distinctive markers that never appear on a genuine bill (mirrors salary/electricity #47).
_MYKAD = ['WARGANEGARA', 'PENGARAH PENDAFTARAN', 'PENDAFTARAN NEGARA']


def _any(tokens, tn):
    return any(_norm(t) in tn for t in tokens)


def score_markers(ocr_text: str) -> dict:
    """The raw marker tallies for OCR text (transparent, for tests + calibration):
    ``{operator, labels, water, m3, electricity, mykad}``. ``operator`` names the recognised utility
    or ''. Pure."""
    tn = _norm(ocr_text)
    operator = ''
    for name, markers in _OPERATORS:
        if _any(markers, tn):
            operator = name
            break
    return {
        'operator': operator,
        'labels': sum(1 for g in _BILL_LABELS if _any(g, tn)),
        'water': _any(_WATER_TERM, tn),
        'm3': _any(_M3, tn),
        'electricity': _any(_ELECTRICITY_TERM, tn),
        'mykad': _any(_MYKAD, tn),
    }


def water_genuineness(ocr_text: str) -> dict:
    """Soft genuineness signal for a water bill → ``{status, family, probability, reason,
    model_version, markers}``. ``status`` ∈ {'genuine', 'suspect', 'not_water_bill'} (the canonical
    cap vocabulary); ``family`` names the recognised operator (air_selangor/saj_johor/…), or
    'unrecognised' (genuine water grammar, unknown operator), or a reject family (electricity_bill/
    not_water_bill). Pure + deterministic; never raises."""
    m = score_markers(ocr_text)
    operator, labels = m['operator'], m['labels']
    # Any water signal — a water term, an m³ unit, or a recognised operator — anchors the doc as a
    # water bill and guarantees it is never rejected (corpus: every genuine bill carried one).
    is_water = bool(m['water'] or m['m3'] or operator)

    def out(status, family, prob, reason):
        return {'status': status, 'family': family, 'probability': round(prob, 3),
                'reason': reason[:300], 'model_version': MODEL_VERSION,
                'markers': {'operator': operator or 'none', 'labels': labels,
                            'water': m['water'], 'm3': m['m3']}}

    # ── Reject floor (not_water_bill) — only when NO water signal anchors the doc ────────────────
    if not is_water:
        if m['mykad'] and labels == 0:
            return out('not_water_bill', 'not_water_bill', 0.05,
                       'MyKad markers, no bill fields — not a water bill')
        if m['electricity']:
            return out('not_water_bill', 'electricity_bill', 0.10,
                       'electricity-utility markers (not water) — wrong bill type in the slot')
        if labels < 2:
            return out('not_water_bill', 'not_water_bill', 0.12,
                       'no water signal, no bill fields — not a water bill')

    # ── Genuine / suspect (a water bill) ────────────────────────────────────────────────────────
    if operator:
        if labels >= 2:
            return out('genuine', operator, min(0.95, 0.65 + 0.05 * labels),
                       f'{operator.replace("_", " ").title()} + {labels} bill-field labels — genuine water bill')
        # Operator header but thin field grammar (a cropped photo / app screenshot) → soft suspect.
        return out('suspect', operator, 0.55,
                   f'{operator.replace("_", " ").title()} but only {labels} bill-field labels — thin read, confirm')

    # No recognised operator, but water grammar (an unlisted operator, or a cropped letterhead).
    if labels >= 2:
        return out('genuine', 'unrecognised', min(0.90, 0.60 + 0.05 * labels),
                   f'water-bill grammar ({labels} labels + water/m³ terms) without a listed operator '
                   '— genuine (likely an operator we have not catalogued yet)')
    # Water-shaped but weak / unconfirmed → suspect (never a false genuine, never a false reject).
    return out('suspect', 'unrecognised', 0.45,
               f'{labels} bill-field labels, water terms but no recognised operator — confirm')
